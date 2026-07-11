# eng-lesson

유튜브 스크립트 기반 영어 학습 웹 서비스. 유튜브 영상의 영어/한글 스크립트에서 단어·숙어·패턴·문장을 AI로 추출하고, 망각곡선(FSRS) 기반 복습 스케줄로 학습한다. 듀오링고처럼 가볍게, 안키처럼 과학적으로.

- 서비스(학습자): `https://esl.lessonaza.com`
- 백엔드 API + 백오피스(관리자): `https://esladmin.lessonaza.com`
- 배포: git push → GitHub Actions → codenavi 서버 (Docker + Traefik)

---

## 핵심 기능

### 1. 콘텐츠 등록 (백오피스, 관리자 전용)

| 방식 | 동작 |
|------|------|
| 유튜브 URL 입력 | 영상 제목 자동 기입 + 영어/한글 스크립트 자동 추출 → DB 저장 |
| 수기 입력 | 제목 + 영어/한글 스크립트를 직접 붙여넣어 저장 |

스크립트가 저장되면 AI(Claude API)가 학습 항목 4종을 자동 추출한다.
쉬운 표현(thank you, sorry, got it 등 기초 레벨)은 추출에서 제외한다.

| # | 추출 항목 | 학습 레벨 |
|---|-----------|-----------|
| 1 | 중요 단어 | 레벨 1 |
| 2 | 핵심 숙어 | 레벨 2 |
| 3 | 자주 반복되는 영어 패턴 | 레벨 3 |
| 4 | 문장 | 레벨 4 |

### 2. 학습 (서비스 페이지, 로그인 사용자)

안키(Anki)와 같은 인지과학 기반 간격 반복(Spaced Repetition). FSRS 알고리즘으로 "잊어버릴 만한 시점"에 항목이 자동으로 복습 큐에 나타난다.

| 레벨 | 퀴즈 형식 |
|------|-----------|
| 레벨 1 | 단어 맞추기 퀴즈 (4지선다) |
| 레벨 2 | 핵심 숙어 맞추기 퀴즈 (문맥 빈칸) |
| 레벨 3 | 영어 패턴 맞추기 퀴즈 (패턴 완성) |
| 레벨 4 | 문장 통암기 — 한글 문제 + 괄호 안 "영어식 사고" 힌트(예: "그 나무가 있다, 저기에") → 영어 문장 입력 |

콘텐츠 라이브러리에서는 유튜브 원본 음성을 문장 단위로 들을 수 있다 — 스크립트 문장을 클릭하면 해당 구간(시작-종료)이 재생되고, **구간 반복(A-B 루프)** 토글로 반복 청취할 수 있다.

### 3. 인증

- Google SSO 로그인 (사용자/관리자 공통)
- 역할 분리: `admin`(백오피스 접근 가능) / `learner`(서비스 페이지)

### 4. 워드 테트리스 (페이즈 2)

테트리스 스타일 UI/이펙트를 적용한 네트워크 영어 게임.

- 단어가 블록처럼 내려오고, 빠르게 타이핑해서 쳐내는 대전 게임
- 사람 vs AI, 사람 vs 사람 모두 지원 (실시간 WebSocket)
- 콤보/라인 클리어/KO 등 테트리스식 이펙트 적용
- 학습 DB의 단어를 게임 소재로 재사용 → 학습과 게임의 선순환

## UI 컨셉

**노트(공책) x 레고**: 줄노트 질감의 배경 + 레고 브릭 스타일의 버튼/카드/진행도. 상세: [docs/specs/ui-design.md](docs/specs/ui-design.md)

---

## 기술 스택

| 계층 | 선택 | 근거 요약 |
|------|------|-----------|
| 프론트엔드 | Next.js 15 (App Router) + TypeScript + Tailwind CSS | 안정성, 유지보수성, SSR/CSR 유연성 |
| 백엔드 | FastAPI (Python 3.12, uv) | 유튜브 자막/AI 파이프라인의 Python 생태계, 타입 기반 API |
| DB | PostgreSQL 17 (서버 기존 컨테이너, DB `englesson` 추가) | 요구사항: 기존 postgres에 스키마만 추가 |
| 마이그레이션 | Alembic | SQLAlchemy 2 기반 버전 관리 |
| 인증 | Google OAuth 2.0 + JWT (httpOnly 쿠키) | 백오피스/서비스 공용 세션 |
| AI | Claude API (Anthropic) | 스크립트 번역 보완 + 학습 항목 4종 추출 |
| 복습 알고리즘 | FSRS (py-fsrs) | 안키 차세대 알고리즘, 논문 기반 |
| 실시간(페이즈 2) | WebSocket (FastAPI) | 워드 테트리스 대전 |
| 배포 | Docker Compose + Traefik 라벨 + GitHub Actions(SSH) | 서버 기존 패턴 준수 |

선정 근거와 기각한 대안: [docs/architecture/tech-stack.md](docs/architecture/tech-stack.md)

---

## 문서 인덱스

### 아키텍처 (docs/architecture/)

| 문서 | 내용 |
|------|------|
| [overview.md](docs/architecture/overview.md) | 시스템 구성도, 컴포넌트 책임, 주요 데이터 흐름 |
| [tech-stack.md](docs/architecture/tech-stack.md) | 기술 선정 근거 + 기각된 대안 |
| [database.md](docs/architecture/database.md) | ERD, 테이블 정의, 인덱스, 마이그레이션 정책 |
| [deployment.md](docs/architecture/deployment.md) | 서버 인프라, CI/CD 파이프라인, Traefik 라우팅, 롤백 |

### 기능 스펙 (docs/specs/)

| 문서 | 내용 |
|------|------|
| [auth.md](docs/specs/auth.md) | Google SSO 흐름, 역할 모델, 세션/토큰 |
| [backoffice.md](docs/specs/backoffice.md) | 관리자 화면 명세 (콘텐츠 등록/추출 검수/사용자 관리) |
| [content-pipeline.md](docs/specs/content-pipeline.md) | 유튜브 스크립트 추출 + AI 4종 추출 파이프라인 |
| [learning.md](docs/specs/learning.md) | FSRS 복습 스케줄링 + 레벨 1-4 퀴즈 상세 |
| [ui-design.md](docs/specs/ui-design.md) | 노트 x 레고 디자인 시스템 (토큰/컴포넌트) |
| [word-tetris.md](docs/specs/word-tetris.md) | 페이즈 2 게임 규칙, 네트워크 프로토콜, AI 봇 |

---

## 저장소 구조 (구현 시)

```
eng-lesson/
├── frontend/          # Next.js 15 앱 (서비스 + 백오피스)
├── backend/           # FastAPI 앱 (REST API + WebSocket + 추출 워커)
├── docs/              # 설계/스펙 문서 (본 문서 인덱스 참조)
├── docker-compose.prod.yml
└── .github/workflows/ # CI + 배포 파이프라인
```

## 개발 로드맵

| 페이즈 | 범위 |
|--------|------|
| 1a | 저장소 스캐폴딩, DB 스키마, Google SSO, 백오피스 콘텐츠 등록(유튜브/수기) |
| 1b | AI 추출 파이프라인 + 추출 검수 화면 |
| 1c | FSRS 복습 큐 + 레벨 1-4 퀴즈 학습 화면 |
| 1d | 배포 파이프라인 (git push → codenavi 자동 배포), 도메인 연결 |
| 2 | 워드 테트리스 (PvE → PvP), 매치 기록/랭킹 |

## 도메인 구성

| 도메인 | 역할 |
|--------|------|
| `esl.lessonaza.com` | 학습자 서비스 페이지 |
| `esladmin.lessonaza.com` | 백오피스(관리자 화면) + 백엔드 API (`/api`, `/ws`) |

두 도메인 모두 `/api` 경로는 백엔드 컨테이너로 라우팅되어 프론트는 항상 same-origin으로 API를 호출한다 (CORS 불필요). 상세: [docs/architecture/deployment.md](docs/architecture/deployment.md)
