#!/usr/bin/env bash
# codenavi 서버 배포 — red-green(검증된 승격) 전략 (docs/architecture/deployment.md)
#
# 흐름: 디스크 정리 → 롤백 포인트(:prev) 캡처 → 순차 빌드+신선도 게이트
#       → 카나리(green) 검증 → alembic → 승격(force-recreate) → 자동 롤백 훅
# 공개 헬스체크는 GitHub Actions 의 별도 스텝이 수행하고, 실패 시
# `bash scripts/deploy.sh --rollback` 을 호출한다.
#
# 사용법:
#   bash scripts/deploy.sh             # 정상 배포 (deploy.yml 이 호출)
#   bash scripts/deploy.sh --rollback  # :prev 이미지로 즉시 복귀
set -euo pipefail

cd "$(dirname "$0")/.."
PROD="docker-compose -f docker-compose.prod.yml"
# 카나리는 독립 파일로 기동 — prod 서비스에 절대 영향 없음 (orphan 경고는 무해)
CANARY="docker-compose -f docker-compose.canary.yml"
export DOCKER_BUILDKIT=1 COMPOSE_DOCKER_CLI_BUILD=1

rollback() {
  # :prev = 직전 배포에서 실제 서빙하던 이미지 (capture_rollback_point 가 기록)
  if ! docker image inspect esl-lesson_api:prev >/dev/null 2>&1; then
    echo "[rollback] :prev 태그 없음 — 첫 배포이거나 캡처 전 실패. 수동 복구 필요"
    return 1
  fi
  echo "[rollback] :prev 이미지로 복귀"
  docker tag esl-lesson_api:prev esl-lesson_api:latest
  docker tag esl-lesson_web:prev esl-lesson_web:latest
  $PROD up -d --force-recreate
  echo "[rollback] 완료 — 공개 헬스체크로 확인 필요"
}

if [ "${1:-}" = "--rollback" ]; then
  rollback
  exit $?
fi

echo "== 1. 디스크 선확보 =="
# dangling 이미지·BuildKit 캐시 누적으로 배포 3회 만에 디스크 풀 실패 이력
# (2026-07-15). 빌드 후 prune 만으로는 실패한 빌드의 캐시가 남아 연쇄 실패한다.
docker image prune -f
docker builder prune -f --keep-storage 2GB
df -h / | tail -1

echo "== 2. 롤백 포인트 캡처 =="
# 빌드가 :latest 를 덮어쓰기 전에, 지금 실제 서빙 중인 이미지 ID를 :prev 로 고정
for svc in api web; do
  img=$(docker inspect "englesson-$svc" --format '{{.Image}}' 2>/dev/null || true)
  if [ -n "$img" ]; then
    docker tag "$img" "esl-lesson_$svc:prev"
    echo "  esl-lesson_$svc:prev <- $img"
  else
    echo "  englesson-$svc 미실행 — :prev 캡처 생략 (첫 배포)"
  fi
done

IMAGES_TAR=".deploy/images.tar.gz"
if [ -f "$IMAGES_TAR" ]; then
  echo "== 3. 러너 빌드 이미지 load (서버 무부하 — 2026-07-28 빌드 질식 해소) =="
  gunzip -c "$IMAGES_TAR" | docker load
  docker tag esl-lesson_api:ci esl-lesson_api:latest
  docker tag esl-lesson_web:ci esl-lesson_web:latest
  rm -f "$IMAGES_TAR"
  # 러너가 CI 통과 SHA 로 빌드했고 서버도 같은 SHA 로 리셋됨 — 신선도 게이트 불필요
else
  echo "== 3. 순차 로컬 빌드 (폴백 — 수동 배포 등 러너 이미지 부재 시) =="
  # 이미지 소스 해시로 신선도 확인, 불일치 시 무캐시 재빌드 (스테일 캐시 이력)
  build_fresh() {
    svc="$1"; img="$2"
    $PROD build "$svc"
    IMG=$(docker run --rm --entrypoint sh "$img" -c "find app -name '*.py' 2>/dev/null | sort | xargs cat 2>/dev/null | md5sum" | cut -d' ' -f1)
    SRC=$(cd backend && find app -name '*.py' | sort | xargs cat | md5sum | cut -d' ' -f1)
    if [ "$svc" = "api" ] && [ "$IMG" != "$SRC" ]; then
      echo "[!] stale $svc image - rebuilding --no-cache"
      $PROD build --no-cache "$svc"
    fi
  }
  build_fresh api esl-lesson_api
  GIT_SHA=$(git rev-parse HEAD)
  export GIT_SHA
  $PROD build web
  IMG_SHA=$(docker run --rm --entrypoint cat esl-lesson_web /app/BUILD_SHA 2>/dev/null || echo none)
  if [ "$IMG_SHA" != "$GIT_SHA" ]; then
    echo "[!] stale web image ($IMG_SHA != $GIT_SHA) - rebuilding --no-cache"
    $PROD build --no-cache web
  fi
fi

echo "== 4. 카나리(green) 검증 — 트래픽 밖 부팅 실증 =="
# 순차 1개씩만 기동해 RAM 스파이크 최소화. 실패 시 프로덕션 무접촉 중단(red 유지).
canary_check() {
  svc="$1"; name="$2"; probe="$3"
  $CANARY up -d "$svc"
  for i in $(seq 1 12); do
    sleep 5
    if docker exec "$name" sh -c "$probe" >/dev/null 2>&1; then
      echo "  [green] $svc 헬스 통과 (${i}회차)"
      docker rm -f "$name" >/dev/null
      return 0
    fi
  done
  echo "  [RED] $svc 카나리 헬스 실패 — 배포 중단 (프로덕션 무접촉). 최근 로그:"
  docker logs --tail 50 "$name" || true
  docker rm -f "$name" >/dev/null 2>&1 || true
  return 1
}
canary_check api-canary englesson-api-canary \
  "python -c \"import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/health', timeout=3).status==200 else 1)\""
# Next standalone 은 Docker 가 주입한 HOSTNAME 인터페이스에만 바인딩 (localhost 불가,
# 첫 red-green 런 30330657867 실측) — traefik 도 컨테이너 IP 로 붙는 것과 동일하게 확인
canary_check web-canary englesson-web-canary \
  "node -e \"fetch('http://'+(process.env.HOSTNAME||'localhost')+':3000').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))\""

echo "== 5. DB 마이그레이션 (하위호환 규칙 — deployment.md) =="
$PROD run --rm api uv run --no-dev alembic upgrade head

echo "== 6. 승격 — 검증된 이미지로 교체 =="
# 1회 이행(2026-08-03 eng-lesson → esl-lesson): compose 프로젝트명이 디렉토리에서
# 오므로 옛 프로젝트(eng-lesson)가 소유한 동명 컨테이너가 남아 있으면 새 프로젝트의
# up 이 이름 충돌로 실패한다. force-recreate 가 어차피 지우는 대상이라 무해.
docker rm -f englesson-api englesson-web >/dev/null 2>&1 || true
# up -d 가 이미지 갱신에도 재생성 안 하는 v1 버그 → 항상 force-recreate
$PROD up -d --force-recreate
docker image prune -f
echo "== 배포 완료 (공개 헬스체크는 워크플로 다음 스텝) =="
