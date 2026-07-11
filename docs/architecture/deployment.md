# 배포 아키텍처

> 최종 수정: 2026-07-11

git push(main) → GitHub Actions → SSH → codenavi 서버에서 pull + docker-compose 재기동. 서버의 기존 배포 패턴(lessonaza)과 동일한 방식을 따른다.

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
| `esl.lessonaza.com` | A 레코드 → 108.61.162.25 | 학습자 서비스 |
| `esladmin.lessonaza.com` | A 레코드 → 108.61.162.25 | 백오피스 + API |

TLS는 기존 Traefik의 Let's Encrypt(ACME) 설정에 편승 — DNS 레코드 생성 후 첫 요청 시 자동 발급. (배포 전 traefik.toml의 ACME 설정 확인 필요)

## 컨테이너 토폴로지

```
traefik (기존) ── traefiknet ──┬── englesson-web  (Next.js, :3000)
                               └── englesson-api  (FastAPI, :8000)
postgres (기존) ── 기존 db 네트워크 ── englesson-api
```

## docker-compose.prod.yml (설계)

```yaml
version: "3.7"
services:
  web:
    build: ./frontend
    container_name: englesson-web
    restart: unless-stopped
    env_file: .env.web
    networks: [traefiknet]
    labels:
      traefik.enable: "true"
      traefik.docker.network: "traefiknet"
      traefik.frontend.rule: "Host:esl.lessonaza.com,esladmin.lessonaza.com"
      traefik.frontend.priority: "10"
      traefik.port: "3000"

  api:
    build: ./backend
    container_name: englesson-api
    restart: unless-stopped
    env_file: .env.api
    networks: [traefiknet, dbnet]
    labels:
      traefik.enable: "true"
      traefik.docker.network: "traefiknet"
      traefik.frontend.rule: "Host:esl.lessonaza.com,esladmin.lessonaza.com;PathPrefix:/api,/ws"
      traefik.frontend.priority: "100"
      traefik.port: "8000"

networks:
  traefiknet:
    external: true
  dbnet:
    external: true   # postgres 컨테이너가 속한 네트워크명으로 배포 시 확정
```

라우팅 원리: PathPrefix 규칙(priority 100)이 Host 규칙(priority 10)보다 먼저 평가되어 `/api`, `/ws`는 api 컨테이너로, 나머지는 web 컨테이너로 간다. 두 도메인 모두에서 same-origin API 호출이 가능해 CORS가 필요 없다.

주의: `postgres` 컨테이너가 속한 실제 네트워크명은 배포 시 `docker inspect postgres`로 확인해 `dbnet`을 치환한다. postgres가 호스트 포트 5432를 공개 중이므로 최악의 경우 호스트 게이트웨이 경유도 가능하지만, 컨테이너 네트워크 직결을 우선한다.

## 환경변수 (.env.api — 서버에만 존재, git 미포함)

| 변수 | 용도 |
|------|------|
| DATABASE_URL | `postgresql+asyncpg://englesson:***@postgres:5432/englesson` |
| GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET | Google OAuth |
| JWT_SECRET | 세션 JWT 서명 키 |
| ANTHROPIC_API_KEY | AI 추출 |
| ANTHROPIC_MODEL | 기본 `claude-sonnet-5` |
| ADMIN_EMAILS | 최초 관리자 이메일 (콤마 구분) |
| COOKIE_DOMAIN | `.lessonaza.com` |
| PUBLIC_SERVICE_URL / PUBLIC_ADMIN_URL | OAuth redirect 구성 |

`.env.web`: `NEXT_PUBLIC_*` 최소한만 (API는 same-origin이므로 베이스 URL 불필요).

## CI/CD 파이프라인 (.github/workflows/)

### ci.yml — PR/push 게이트

```
frontend: npm ci → lint → typecheck → test → next build
backend:  uv sync → ruff check → pytest
```

### deploy.yml — main push 시 배포

```
on: push(main), CI 성공 후
jobs:
  deploy:
    - appleboy/ssh-action (secrets: DEPLOY_HOST, DEPLOY_USER, DEPLOY_SSH_KEY)
    - script: |
        cd ~/apps/eng-lesson
        git fetch origin main && git reset --hard origin/main
        docker-compose -f docker-compose.prod.yml build
        docker-compose -f docker-compose.prod.yml run --rm api alembic upgrade head
        docker-compose -f docker-compose.prod.yml up -d
        docker image prune -f
    - 헬스체크: curl -sf https://esladmin.lessonaza.com/api/health
```

GitHub Secrets 등록 목록: `DEPLOY_HOST`(108.61.162.25), `DEPLOY_USER`(admin), `DEPLOY_SSH_KEY`(배포 전용 키 신규 발급 권장).

## 배포 순서 (최초 1회 수동 준비)

1. DNS: esl / esladmin A 레코드 → 108.61.162.25
2. 서버: `git clone git@github.com:chulgil/eng-lesson.git ~/apps/eng-lesson`
3. 서버: postgres에 롤/DB 생성 ([database.md](database.md) 초기화 SQL)
4. 서버: `.env.api`, `.env.web` 작성
5. Google Cloud Console: OAuth 클라이언트 생성, redirect URI 등록
   (`https://esl.lessonaza.com/api/auth/callback`, `https://esladmin.lessonaza.com/api/auth/callback`)
6. GitHub Secrets 등록 → main push로 첫 배포

## 헬스체크/롤백

- `GET /api/health`: DB ping 포함. 배포 워크플로 마지막에 검증 — 실패 시 워크플로 실패로 표면화.
- 롤백: `git reset --hard <직전 태그|커밋> && docker-compose up -d --build`. 마이그레이션이 포함된 릴리스는 파괴적 변경 금지 정책([database.md](database.md))으로 하위 호환 보장.
- 로그: `docker logs -f englesson-api` / `englesson-web`.

## 백업

기존 서버 백업 체계(`~/backups`)에 크론 1줄 추가:

```
0 18 * * * docker exec postgres pg_dump -U englesson englesson | gzip > ~/backups/englesson_$(date +\%Y\%m\%d).sql.gz
```

(UTC 18:00 = KST 03:00, 보존 주기는 기존 정책에 맞춤)
