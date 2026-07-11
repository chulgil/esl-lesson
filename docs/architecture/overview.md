# 시스템 아키텍처 개요

> 최종 수정: 2026-07-11

eng-lesson은 프론트엔드(Next.js) + 백엔드(FastAPI) + 기존 PostgreSQL 17을 사용하는 2-컨테이너 웹 서비스다. codenavi 서버의 기존 Traefik 1.7 리버스 프록시 뒤에 배포된다.

## 시스템 구성도

```
                        [사용자 브라우저]
                              |
                    https (esl / esladmin.lessonaza.app)
                              |
                    +---------v----------+
                    |   Traefik 1.7      |  (기존 컨테이너, 80/443, traefiknet)
                    +---------+----------+
              Host:esl        |        Host:esl,esladmin ; PathPrefix:/api,/ws
              Host:esladmin   |        (priority 높음 — path 우선)
             +----------------+------------------+
             |                                   |
   +---------v---------+              +----------v----------+
   | frontend (Next.js)|              | backend (FastAPI)   |
   |  - 서비스 페이지   |              |  - REST API (/api)  |
   |  - 백오피스 화면   |              |  - WebSocket (/ws)  |
   |  (호스트별 분기)   |              |  - 추출 워커        |
   +-------------------+              +----+-----------+----+
                                           |           |
                                +----------v---+   +---v-----------------+
                                | PostgreSQL 17|   | 외부 API            |
                                | (기존 컨테이너|   |  - YouTube (자막)   |
                                |  DB: englesson)|  |  - Claude API      |
                                +--------------+   |  - Google OAuth     |
                                                   +---------------------+
```

## 컴포넌트 책임

| 컴포넌트 | 책임 | 비고 |
|----------|------|------|
| frontend (Next.js 15) | 학습 UI, 퀴즈 렌더링, 백오피스 화면, 게임 클라이언트 | 호스트명으로 서비스/백오피스 분기 (middleware) |
| backend (FastAPI) | 인증(JWT 발급/검증), 콘텐츠/학습 REST API, FSRS 스케줄링, AI 추출 파이프라인, 게임 WebSocket | 단일 컨테이너 안에서 API + 백그라운드 워커 실행 |
| PostgreSQL 17 | 전 데이터 영속화 | 서버 기존 `postgres` 컨테이너에 DB `englesson` 추가 |
| Traefik 1.7 | TLS 종료, 도메인/경로 라우팅 | 기존 인프라 그대로 사용, 라벨만 추가 |

## 도메인/라우팅 규칙

| 요청 | 라우팅 대상 |
|------|-------------|
| `esl.lessonaza.app/*` (아래 제외) | frontend — 학습자 서비스 |
| `esladmin.lessonaza.app/*` (아래 제외) | frontend — 백오피스 (호스트 기반 분기) |
| `*.lessonaza.app/api/*` | backend REST API |
| `*.lessonaza.app/ws/*` | backend WebSocket (페이즈 2 게임) |

설계 의도: `/api`를 두 도메인 모두에서 backend로 보내 **프론트가 항상 same-origin으로 API 호출** → CORS 설정과 서드파티 쿠키 이슈를 원천 제거한다. 세션 쿠키는 `Domain=.lessonaza.app`으로 발급해 두 도메인에서 공유한다.

## 주요 데이터 흐름

### 흐름 1: 유튜브 콘텐츠 등록 (백오피스)

```
관리자 -- URL 입력 --> frontend --> POST /api/admin/contents
  --> backend: 콘텐츠 행 생성 (status=pending) --> 202 즉시 응답
  --> [백그라운드 워커]
        1. 유튜브 메타데이터 조회 (제목 자동 기입)
        2. 자막 추출 (en 필수, ko 있으면 함께)
        3. ko 자막 없으면 Claude API로 번역 생성
        4. Claude API로 학습 항목 4종 추출 (단어/숙어/패턴/문장)
        5. status=ready, 항목은 review_status=pending(검수 대기)로 저장
관리자 -- 추출 결과 검수(승인/수정/제외) --> 학습 풀에 편입
```

### 흐름 2: 학습 세션 (서비스)

```
학습자 --> GET /api/study/queue
  backend: FSRS due 카드 조회 + 신규 카드 일일 한도 내 편입
        --> 퀴즈 문항 생성 (레벨별 형식, 오답 보기 샘플링)
학습자 -- 답안 제출 --> POST /api/study/answer
  backend: 채점 --> FSRS rating 매핑 --> 다음 복습 시각 계산 --> 카드 갱신 + 로그 적재
```

### 흐름 3: 워드 테트리스 대전 (페이즈 2)

```
플레이어 --> WS /ws/game (JWT 인증)
  matchmaking: 방 코드 매칭(PvP) 또는 AI 봇 배정(PvE)
  게임 루프: 서버 권위(server-authoritative) 상태 --> 단어 낙하 틱 브로드캐스트
  플레이어 타이핑 --> 서버 검증 --> 클리어/콤보/공격(garbage) --> 상대에게 전파
  종료 --> 매치 결과 DB 저장
```

## 모노레포 구조

```
eng-lesson/
├── frontend/                  # Next.js 15 (TypeScript)
│   ├── src/app/               # App Router (서비스 페이지)
│   ├── src/app/admin/         # 백오피스 라우트
│   ├── src/middleware.ts      # 호스트 기반 서비스/백오피스 분기
│   └── Dockerfile
├── backend/                   # FastAPI (Python 3.12, uv)
│   ├── app/api/               # 라우터 (auth, contents, study, game, admin)
│   ├── app/core/              # 설정, 보안(JWT), DB 세션
│   ├── app/models/            # SQLAlchemy 모델
│   ├── app/services/          # 추출 파이프라인, FSRS, 채점
│   ├── app/workers/           # 백그라운드 추출 워커
│   ├── alembic/               # 마이그레이션
│   └── Dockerfile
├── docs/                      # 본 설계/스펙 문서
├── docker-compose.prod.yml    # 배포용 (traefik 라벨 포함)
├── docker-compose.yml         # 로컬 개발용 (postgres 포함)
└── .github/workflows/         # ci.yml, deploy.yml
```

## 비기능 요구사항

| 항목 | 방침 |
|------|------|
| 타임존 | DB 저장 UTC, 표시 KST (프로젝트 공통 규칙) |
| 로깅 | 구조화 JSON 로그(stdout) → `docker logs`. 추출 파이프라인은 콘텐츠별 단계 로그를 DB에도 기록 |
| 백업 | 서버 기존 postgres 백업 체계에 편승 (`~/backups`), DB 단위 pg_dump 크론 추가 |
| 시크릿 | 서버 `.env` 파일 (git 미포함), GitHub Actions Secrets. 코드 하드코딩 금지 |
| 확장성 | 단일 서버 규모(개인 프로젝트). 추출 워커는 프로세스 내 큐로 시작, 부하 증가 시 분리 |
| 장애 격리 | AI 추출 실패가 콘텐츠 저장을 막지 않음 (상태 머신으로 재시도) |

## 관련 문서

- 기술 선정 근거: [tech-stack.md](tech-stack.md)
- DB 스키마: [database.md](database.md)
- 배포 파이프라인: [deployment.md](deployment.md)
