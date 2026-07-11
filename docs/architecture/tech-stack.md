# 기술 스택 선정

> 최종 수정: 2026-07-11

선정 기준: (1) 유지보수성과 안정성 — 사용자 요구사항 명시 (2) 서버 기존 인프라(Traefik 1.7, PostgreSQL 17, docker-compose 1.29) 재사용 (3) 운영자 1인 프로젝트 — 익숙한 생태계(Python/uv) 우선.

## 요약

| 계층 | 선택 | 버전 |
|------|------|------|
| 프론트엔드 | Next.js (App Router) + TypeScript | 15.x |
| 스타일 | Tailwind CSS | 4.x |
| 백엔드 | FastAPI + SQLAlchemy 2 + Alembic | Python 3.12, uv |
| DB | PostgreSQL (기존 컨테이너) | 17 |
| 인증 | Google OAuth 2.0 (Authorization Code) + 자체 JWT | - |
| AI | Claude API (`claude-sonnet-5` 기본) | - |
| 복습 알고리즘 | FSRS (py-fsrs) | v5 파라미터 |
| 유튜브 자막 | youtube-transcript-api (1차) + yt-dlp (폴백) | - |
| 실시간 | FastAPI WebSocket | 페이즈 2 |
| 배포 | Docker Compose + GitHub Actions (SSH) | - |

## 계층별 선정 근거

### 프론트엔드: Next.js 15 + TypeScript

- 채택 이유: App Router 기반 파일 라우팅으로 서비스/백오피스를 한 앱에서 관리, `middleware`로 호스트 기반 분기 가능. React 생태계의 안정적 주류 — 장기 유지보수에 유리. SSG/SSR 혼합으로 학습 페이지 초기 로드 최적화.
- 기각: **SvelteKit** — 번들 작고 빠르지만 생태계/레퍼런스가 상대적으로 작아 장기 유지보수 리스크. **Vue/Nuxt** — 서버에 nuxt-landing-page가 이미 있으나 이 프로젝트는 게임(캔버스/키 입력)과 복잡한 상태를 다루므로 React 생태계(zustand, framer-motion)가 유리. **Flutter Web** — lesson-app에서 사용 중이지만 웹 SEO/접근성/텍스트 입력 UX가 브라우저 네이티브 대비 불리.

### 스타일: Tailwind CSS 4

- 채택 이유: "노트 x 레고" 커스텀 디자인 시스템을 토큰(색/그림자/보더)으로 정의하기에 적합. 컴포넌트 라이브러리 종속 없음.
- 기각: **MUI/Chakra** — 기성 디자인이 강해 노트x레고 컨셉과 충돌, 오버라이드 비용이 더 큼.

### 백엔드: FastAPI (Python 3.12, uv)

- 채택 이유:
  - 유튜브 자막(youtube-transcript-api, yt-dlp), FSRS(py-fsrs), Anthropic SDK 등 **핵심 파이프라인 라이브러리가 모두 Python 성숙 생태계**.
  - Pydantic 기반 요청/응답 검증 = 시스템 경계 검증 원칙과 일치.
  - WebSocket 내장 → 페이즈 2 게임 서버를 같은 프레임워크로 확장.
  - 운영자의 주력 언어(Python + uv) — 서버의 stock-alert도 동일 패턴.
- 기각: **Next.js 풀스택(API Routes)** — 배포 단순하나 유튜브 자막/FSRS의 JS 라이브러리(ts-fsrs 등)는 존재해도 파이프라인 전체(자막, 번역, 추출 워커)를 Node로 재구성하는 비용이 큼. WebSocket도 커스텀 서버 필요. **NestJS** — 구조는 좋으나 동일한 Python 생태계 이점 부재. **Django** — admin 내장이 매력적이나 백오피스를 커스텀 UI(노트x레고)로 만들 것이므로 이점 상실, async 파이프라인은 FastAPI가 더 자연스러움.

### DB: 기존 PostgreSQL 17 컨테이너 + DB `englesson`

- 채택 이유: 요구사항 명시("서버에 이미 postgresql이 있으며 디비 스키마만 추가"). pgvector 이미지라 향후 예문 유사도 검색(중복 제거 고도화)도 가능.
- 방침: 별도 데이터베이스 `englesson` + 전용 롤 `englesson` 생성 (기존 서비스와 권한 격리). 컨테이너/포트는 공유.
- 기각: **신규 postgres 컨테이너** — 요구사항 위반 + 메모리 낭비. **스키마(namespace)만 추가** — 같은 DB 내 스키마 공유는 기존 서비스와 롤/백업 경계가 얽힘. "DB 추가"가 실질적으로 요구사항 취지(기존 postgres 인스턴스 재사용)에 부합하면서 격리가 깨끗함.

### 인증: Google OAuth 2.0 + 자체 JWT (httpOnly 쿠키)

- 채택 이유: 백엔드(FastAPI)가 Authorization Code 흐름을 직접 처리하고 자체 JWT를 `Domain=.lessonaza.com` httpOnly 쿠키로 발급 → 서비스/백오피스 두 도메인에서 세션 공유, 프론트/백 모두 같은 토큰 검증.
- 기각: **Auth.js(next-auth)** — 프론트 편의는 높으나 세션 소유권이 Next.js에 생겨 FastAPI가 매 요청 이중 검증 구조가 됨. 게임 WebSocket 인증(백엔드 직결)까지 고려하면 백엔드 소유 세션이 단순. **Firebase Auth** — 외부 종속 추가, 자체 서버 인프라 방침과 불일치.

### AI: Claude API

- 채택 이유: 번역 + 4종 추출(단어/숙어/패턴/문장)을 구조화 출력(JSON)으로 안정 수행. 기본 모델 `claude-sonnet-5` (비용/품질 균형), 대량 배치 시 Haiku 다운시프트 옵션.
- 기각: **로컬 LLM** — 서버 사양(단일 VPS) 부족. **OpenAI** — 품질 동급이나 운영자 기존 키/생태계가 Anthropic.

### 복습 알고리즘: FSRS

- 채택 이유: 안키 차세대 기본 알고리즘. SM-2 대비 리뷰 횟수 20-30% 절감(동일 기억률 기준) 연구 결과. py-fsrs 공식 구현 존재 — 직접 구현 리스크 제거.
- 기각: **SM-2** — 구현 단순하나 고정 간격 공식의 한계. **Leitner 박스** — 데모 수준에 적합, "인지과학적으로 잊어버릴 만한 주기" 요구에 미달.

### 유튜브 자막: youtube-transcript-api + yt-dlp 폴백

- 채택 이유: youtube-transcript-api는 자막 전용 경량 라이브러리(수동/자동 자막, 다국어). 차단/실패 시 yt-dlp로 폴백. 자막이 아예 없는 영상은 "수기 입력" 경로로 안내 (오디오 STT는 범위 외 — 페이즈 3 후보).
- 기각: **YouTube Data API 공식** — 자막 다운로드(captions.download)는 영상 소유자만 가능해 용도 불충족. 메타데이터(제목)는 oEmbed/yt-dlp로 충분.

### 실시간(페이즈 2): FastAPI WebSocket

- 채택 이유: 백엔드 단일 컨테이너 유지. 방(room) 상태는 인메모리(단일 프로세스) — 개인 프로젝트 규모에 충분.
- 기각: **Socket.IO 별도 Node 서버** — 재접속/룸 편의 기능은 좋으나 컨테이너/언어 추가 비용이 규모 대비 과함. **Redis pub/sub** — 다중 프로세스 확장 시점에 도입(현재 불필요).

### 배포: Docker Compose + GitHub Actions SSH

- 채택 이유: 서버 기존 패턴(lessonaza: `~/apps/<repo>` + docker-compose.prod.yml + traefik 라벨)과 동일 — 운영 일관성. main push → Actions가 SSH로 `git pull && docker-compose up -d --build`.
- 기각: **Jenkins(서버 내 존재)** — 유지 중인지 불명확, GitHub Actions가 저장소와 밀착. **레지스트리 경유(GHCR pull)** — 이미지 push/pull 왕복보다 서버 빌드가 단순(단일 서버라 빌드 캐시 이점).

## 버전 고정 정책

- Python/Node 버전, 주요 라이브러리는 lockfile(uv.lock, package-lock.json)로 고정.
- Claude 모델 ID는 환경변수(`ANTHROPIC_MODEL`)로 주입 — 코드 하드코딩 금지.
