# 배포 아키텍처

> 최종 검증: 2026-07-30 (코드 대조 완료)

git push(main) → CI → GitHub Actions 러너에서 이미지 빌드 → scp 전송 → SSH 로 서버에서 `scripts/deploy.sh` (load → 카나리 검증 → 승격, red-green). 실패 시 `:prev` 이미지로 자동 롤백.

## 서버 현황 (codenavi, 2026-07-11 확인)

| 항목 | 값 |
|------|-----|
| 호스트 | Vultr VPS, Ubuntu 22.04 LTS |
| 접속 | `ssh codenavi` (로컬 ~/.ssh/config 별칭) |
| 컨테이너 런타임 | Docker 20.10 + docker-compose 1.29 |
| 리버스 프록시 | Traefik 1.7 컨테이너 (80/443), 도커 네트워크 `traefiknet`, 라벨 기반 라우팅 |
| DB | `postgres` 컨테이너 (pgvector/pg17), 5432 |
| 배포 위치 | `~/apps/eng-lesson` (git clone) |

기존 참조 사례: `~/apps/lesson-app-backend` → traefik 라벨 `Host:lesson.chulgil.me`로 서비스 중.

## 도메인/DNS

| 도메인 | 대상 | 용도 |
|--------|------|------|
| `esl.lessonaza.app` | A 레코드 → 108.61.162.25 | 서비스 + 백오피스(`/admin`, 관리자만) + API |
| `esladmin.lessonaza.app` | (하위호환) | `/` → `/admin` 유도만. 신규 설계는 단일 도메인 (2026-07-12) |

단일 도메인 통합(2026-07-12): 백오피스는 `esl.lessonaza.app/admin` 경로 하나로 접근하고, 역할 검증(AdminLayout + 백엔드 admin 가드)으로 관리자만 사용한다. 별도 admin 도메인은 불필요.

TLS는 기존 Traefik의 Let's Encrypt(ACME) 설정에 편승 — DNS 레코드 생성 후 첫 요청 시 자동 발급. (배포 전 traefik.toml의 ACME 설정 확인 필요)

## 컨테이너 토폴로지

```
traefik (기존) ── traefiknet ──┬── englesson-web  (Next.js, :3000)
                               └── englesson-api  (FastAPI, :8000)
postgres (기존) ── 기존 db 네트워크 ── englesson-api
```

## docker-compose.prod.yml (요지 — 정본은 리포 루트 파일)

```yaml
version: "3.7"
services:
  web:
    build: { context: ./frontend, args: { GIT_SHA: ${GIT_SHA:-dev} } }  # 이미지 신선도 마커
    container_name: englesson-web
    restart: unless-stopped
    env_file: .env.web
    networks: [traefiknet]
    labels:
      traefik.enable: "true"
      traefik.docker.network: "traefiknet"
      traefik.frontend.rule: "Host:esl.lessonaza.app,esladmin.lessonaza.app"
      traefik.frontend.priority: "10"
      traefik.port: "3000"

  api:
    build: ./backend
    container_name: englesson-api
    restart: unless-stopped
    env_file: .env.api
    environment:
      CHAT_UPLOAD_DIR: /data/chat-uploads
    volumes:
      - ./data/chat-uploads:/data/chat-uploads   # 채팅 이미지 영속 (docs/specs/chat.md)
    networks: [traefiknet, postgresql_internal]
    labels:
      traefik.enable: "true"
      traefik.docker.network: "traefiknet"
      traefik.frontend.rule: "Host:esl.lessonaza.app,esladmin.lessonaza.app;PathPrefix:/api,/ws"
      traefik.frontend.priority: "100"
      traefik.port: "8000"

networks:
  traefiknet:
    external: true
  postgresql_internal:
    external: true   # 기존 postgres 컨테이너 네트워크 (서버 확인 완료)
```

라우팅 원리: PathPrefix 규칙(priority 100)이 Host 규칙(priority 10)보다 먼저 평가되어 `/api`, `/ws`는 api 컨테이너로, 나머지는 web 컨테이너로 간다. 두 도메인 모두에서 same-origin API 호출이 가능해 CORS가 필요 없다.

postgres 컨테이너 네트워크는 `postgresql_internal`로 확인 완료 (2026-07-11, `docker inspect postgres`). api 컨테이너는 이 네트워크에 조인해 컨테이너명 `postgres`로 직결한다.

## 환경변수 (.env.api — 서버에만 존재, git 미포함)

전체 정의는 `backend/app/core/config.py` (pydantic-settings) — 아래는 운영 필수/주요 변수.

| 변수 | 용도 |
|------|------|
| DATABASE_URL | `postgresql+asyncpg://englesson:***@postgres:5432/englesson` |
| GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET | Google OAuth |
| JWT_SECRET | 세션 JWT 서명 키 (운영에서 미설정 시 기동 차단) |
| ANTHROPIC_API_KEY | AI 추출 |
| ANTHROPIC_MODEL / ANTHROPIC_TRANSLATE_MODEL / ANTHROPIC_INSIGHT_MODEL | 기본 `claude-sonnet-5` / 번역·인사이트 `claude-haiku-4-5-20251001` |
| VOYAGE_EMBEDDING_SECRET / VOYAGE_EMBEDDING_MODEL | 단어 임베딩 (`voyage-3.5-lite`). 미설정 시 임베딩 기능 스킵 |
| YOUTUBE_API_KEY | 라이선스 조회·CC 검색 (미설정 시 스킵) |
| VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY / VAPID_SUBJECT | 웹 푸시. 미설정 시 푸시 비활성 |
| WEBSHARE_PROXY_USERNAME / WEBSHARE_PROXY_PASSWORD / YT_PROXY_URL | 유튜브 자막 프록시 |
| AGENT_TOKEN | 로컬 자막 수집기 인증 (미설정 시 `/api/agent/*` 비활성) |
| CHAT_UPLOAD_DIR | 채팅 이미지 저장 경로 (운영: `/data/chat-uploads` 볼륨) |
| ADMIN_EMAILS | 최초 관리자 이메일 (콤마 구분) |
| COOKIE_DOMAIN | `.lessonaza.app` |
| PUBLIC_SERVICE_URL / PUBLIC_ADMIN_URL | OAuth redirect 구성 |

`.env.web`: `NEXT_PUBLIC_*` 최소한만 (API는 same-origin이므로 베이스 URL 불필요).

## CI/CD 파이프라인 (.github/workflows/)

### ci.yml — PR/push 게이트

```
frontend: npm ci → lint → typecheck → test → next build
backend:  uv sync → ruff check → pytest
```

### deploy.yml — main push 시 배포 (red-green 검증된 승격 + 러너 빌드, 2026-07-28)

배포 본체는 리포의 **`scripts/deploy.sh`** — `git reset` 직후 실행되므로 항상 커밋과 같은 버전의 스크립트가 돈다. **이미지 빌드는 GitHub Actions 러너(7GB)에서 수행** — 2GB 서버에서 빌드하면 4~6분간 라이브 서비스가 질식한다(2026-07-28 실사용 보고로 이전). 서버는 load→카나리→교체만 하므로 배포 중에도 서비스가 정상 응답하고, 중단은 승격 스왑 수 초뿐이다.

```
push(main) → CI 성공 → [deploy.yml]
  A. (러너) checkout @ CI 통과 SHA → docker buildx (linux/amd64)
     api=eng-lesson_api:ci, web=eng-lesson_web:ci(GIT_SHA 마커), GHA 캐시
  B. (러너) docker save|gzip → scp 로 서버 ~/apps/eng-lesson/.deploy/images.tar.gz
  C. (서버 SSH) git reset --hard <빌드된 SHA> → bash scripts/deploy.sh
     1. 디스크 정리 (image prune + builder prune --keep-storage 2GB)
     2. 롤백 포인트 캡처 — 서빙 중 컨테이너의 이미지 ID를 :prev 로 태그
     3. .deploy/images.tar.gz load + :ci→:latest 재태그 (부재 시 로컬 빌드 폴백)
     4. 카나리(green) 검증 — docker-compose.canary.yml 로 트래픽 밖 부팅
        · api-canary: postgresql_internal 만 가입(traefik 미노출), /api/health 폴링 60s
        · web-canary: HOSTNAME:3000 200 확인. 순차 1개씩(RAM 보호), 검증 즉시 제거
        · 실패 → 로그 출력 + 중단. 프로덕션 무접촉(red 유지)
     5. alembic upgrade head (카나리 통과 후)
     6. 승격: up -d --force-recreate (검증된 이미지 스왑 — 유일한 수 초 다운타임)
→ [deploy.yml] 공개 헬스체크 12×10s
→ 실패 시 [자동 롤백]: bash scripts/deploy.sh --rollback (:prev 재태그+재생성) 후 재검증
```

**"파드 2개 동시 전환" 구조가 아닌 이유**: 카나리는 트래픽 밖 검증용 임시 컨테이너로, 검증 후 제거된다. api 는 인프로세스 채팅 허브·게임 세션의 단일 인스턴스 전제(Redis 금지)라 두 인스턴스가 동시에 트래픽을 받으면 스플릿브레인 — traefik 1.7/compose v1 의 정적 라벨도 무중단 전환을 지원하지 않는다. 러너 빌드 이전으로 체감 문제(빌드 중 질식)가 제거되면 스왑 수 초는 허용 범위.

- **트래픽 중첩형 blue-green 을 쓰지 않는 이유**: api 는 인프로세스 채팅 허브·게임 세션의 단일 인스턴스 전제(Redis 금지, 2026-07-27 결정) — 이중 기동 시 스플릿브레인. traefik 1.7 + compose v1(`container_name` 고정) 도 라벨 전환을 지원하지 않는다. traefik 2+/compose v2 이전 시 web(무상태)만 중첩형 재검토.
- **서버 RAM 2GB 제약(2026-07-12)**: api+web 동시 빌드 OOM 이력 — 순차 빌드 + 카나리도 순차 1개씩.

GitHub Secrets 등록 목록: `DEPLOY_HOST`(108.61.162.25), `DEPLOY_USER`(admin), `DEPLOY_SSH_KEY`(배포 전용 키 신규 발급 권장).

## 배포 순서 (최초 1회 수동 준비)

1. DNS: esl / esladmin A 레코드 → 108.61.162.25
2. 서버: `git clone git@github.com:chulgil/eng-lesson.git ~/apps/eng-lesson`
3. 서버: postgres에 롤/DB 생성 ([database.md](database.md) 초기화 SQL)
4. 서버: `.env.api`, `.env.web` 작성
5. Google Cloud Console: OAuth 클라이언트 생성, redirect URI 등록
   (`https://esl.lessonaza.app/api/auth/callback`, `https://esladmin.lessonaza.app/api/auth/callback`)
6. GitHub Secrets 등록 → main push로 첫 배포

## 헬스체크/롤백

- `GET /api/health`: DB ping 포함. 카나리(내부)와 배포 워크플로 마지막(공개) 두 번 검증.
- **자동 롤백**: 공개 헬스체크 실패 시 워크플로가 `scripts/deploy.sh --rollback` 을 호출 — `:prev` 이미지 재태그 + force-recreate + 재검증. `:prev` = 직전 배포에서 실제 서빙하던 이미지 ID (배포마다 빌드 전에 캡처).
- **수동 롤백**: `ssh codenavi → cd ~/apps/eng-lesson && bash scripts/deploy.sh --rollback`. 재빌드 없이 즉시 복귀라 `git reset && build` 방식보다 빠르고 OOM 리스크 없음.
- **마이그레이션 하위호환 규칙(필수)**: alembic 은 구버전이 아직 서빙 중일 때(승격 전) 적용되고, 롤백 시에도 스키마는 남는다 — **컬럼/테이블 제거·rename 은 "코드에서 참조 제거 배포 → 다음 배포에서 스키마 제거" 2단계**로. 추가(add column nullable/default)는 자유. ([database.md](database.md) 파괴적 변경 금지 정책과 동일 축)
- 로그: `docker logs -f englesson-api` / `englesson-web`. 카나리 실패 로그는 액션 로그에 tail 50 출력됨.

## 백업

기존 서버 백업 체계(`~/backups`)에 크론 1줄 추가:

```
0 18 * * * docker exec postgres pg_dump -U englesson englesson | gzip > ~/backups/englesson_$(date +\%Y\%m\%d).sql.gz
```

(UTC 18:00 = KST 03:00, 보존 주기는 기존 정책에 맞춤)
