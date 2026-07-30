# 스펙: 테마 몰 (테마 엔타이틀먼트)

> 최종 검증: 2026-07-30 (코드 대조 완료) · 설계 승인: 2026-07-30 (사용자)

앱 테마 5종(note/candy/lego/cat/excel — `frontend/src/lib/theme.ts` APP_THEMES)을 전원 무료에서 **엔타이틀먼트(보유권) 기반** 자산으로 전환한다. 이번 범위는 엔타이틀먼트 기반 + 백오피스 수동 지급/회수 + 헤냥이(cat) 제한이며, 결제(PG) 연동은 후속이다.

## 전략 3단

| 단계 | 상태 | 내용 |
|---|---|---|
| 무료 | 운영 중 | note/candy/lego/excel — 전원 사용 가능, grant 불필요 |
| 이벤트 지급 | **현재 (이번 범위)** | restricted 테마를 백오피스에서 이메일로 수동 지급/회수. cat 은 초기 2계정 전용 |
| 유료 판매 | 후속 | `THEME_ACCESS` 에 "paid" 값 추가 + PG 연동. purchases 테이블(결제 이력)·환불 정책은 **결제 수단 결정 후** 별도 스펙 |

- 유료 전환 시에도 `theme_grants` 가 "보유"의 단일 근거 — 구매 성공 = grant INSERT. 결제 이력(금액·PG 승인번호·환불)은 별도 purchases 테이블로 분리한다.

## 아키텍처 결정

| 결정 | 근거 | 기각한 대안 |
|---|---|---|
| 엔타이틀먼트 테이블(행 존재 = 보유) | 이벤트 지급·유료 판매·기간 한정을 하나의 모델로 수용. 회수 = 행 삭제 | User 에 컬럼 추가 — 테마 늘 때마다 스키마 변경 |
| 클라이언트 가드만 (서버 CSS 강제 없음) | 테마는 코스메틱(치장) 자산 — localStorage 조작으로 몰래 써도 학습 데이터·과금에 영향 없음. AppNav 전역 가드가 세션마다 원복해 실익도 없다 | 서버 렌더 시 테마 검증 — 구현 비용 대비 막을 가치가 없는 위협 |
| 카탈로그는 백엔드 `THEME_ACCESS` 가 단일 근거 | 지급/회수·allowed 판정이 전부 서버 — 프론트 APP_THEMES 는 라벨·순서 등 표시만 담당 | 프론트에 정책 중복 — 전환(무료→유료) 시 이중 수정 |

## 데이터 모델

```
theme_grants
  id                     -- BigInt PK
  user_id FK             -- users.id, ondelete CASCADE
  theme_key String(32)   -- THEME_ACCESS 의 키. unique(user_id, theme_key)
  note Text nullable     -- 지급 사유 (이벤트명 등) — 백오피스 감사용
  granted_by FK nullable -- 지급한 관리자 (users.id, SET NULL). 시드 지급은 null
  created_at
```

```
theme_settings (c8d9e0f1a2b3, 2026-07-30)
  theme_key String(32) PK -- THEME_ACCESS 의 키
  access String(16)       -- "free" | "restricted" (오버라이드)
```

- 접근 정책: `backend/app/services/themes.py` — 기본값 `THEME_ACCESS`(note/candy/lego/excel = free, cat = restricted) 에 `theme_settings` 오버라이드를 병합한 `effective_theme_access(db)` 가 판정의 단일 진입점. 행 없음 = 기본값. 유효 키 목록·기본값은 코드가 정본(프론트 APP_THEMES 와 드리프트 방지).
- 백오피스에서 테마별 무료<->제한 전환 가능. **note 는 잠금 복귀(fallback) 목적지라 제한 전환 금지** (`FALLBACK_THEME`).
- allowed 판정: free 전부 + 내 grants. **관리자는 grant 없이 전 테마 허용** (운영 확인용).
- 무료 전환 시 grants 행은 보존 — 재제한 시 다시 유효해진다.
- 회원탈퇴: `delete_me` 의 명시 삭제 목록에 포함 (sqlite 테스트에서 FK cascade 미작동 — Notification 전례).

## API

| 메서드/경로 | 역할 |
|---|---|
| GET `/api/themes` | (auth) 카탈로그 전체 `{items:[{key, access, allowed}]}` — 표시 순서·라벨은 프론트 APP_THEMES |
| GET `/api/admin/themes` | 카탈로그 + 테마별 보유자 수 `{items:[{key, access, grants}]}` |
| PATCH `/api/admin/themes/{theme_key}` | 무료/제한 전환 `{access: "free"\|"restricted"}` — 404 `theme_not_found` / 422 `fallback_theme_locked`(note 제한 금지) |
| GET `/api/admin/themes/{theme_key}/grants` | 보유자 목록 `{items:[{id, email, nickname, note, created_at}]}` |
| POST `/api/admin/themes/{theme_key}/grants` | 지급 `{email, note?}` — 이메일 소문자 조회. 404 `user_not_found` / 409 `already_granted` / 422 `theme_not_restricted`(free 는 지급 무의미) / 404 `theme_not_found` |
| DELETE `/api/admin/themes/grants/{grant_id}` | 회수 204 |

- 지급 성공 시 알림 적재: `notify(db, user_id, "theme_granted", {theme_key, note})` — 벨 문구 "새 테마가 열렸어요 — 설정에서 바꿔보세요", 탭 → `/settings`.

## 프론트 가드

| 위치 | 동작 |
|---|---|
| 설정 테마 카드 | 미허용 테마 = 스와치 흐림 + "이벤트·구매로 열려요" 배지 + 클릭 무시. 현재 테마가 회수돼 미허용이면 note 자동 복귀 + "사용 권한이 없는 테마라 기본으로 되돌렸어요" 1회 |
| AppNav 전역 | 로그인 세션마다 `/api/themes` 를 fetchMe 와 병렬 조회 — `getAppTheme()` 이 미허용이면 `setAppTheme("note")`. localStorage 우회 차단 |
| 백오피스 `/admin/themes` | 테마 목록(키·라벨·정책·전환 버튼·보유자 수) — 전환 버튼으로 무료<->제한(note 는 "기본 고정"), restricted 행 클릭 → 보유자 목록·지급 폼·회수. 무료 테마 선택 시 지급 패널 숨김(서버 422 방지) |

- 조회 실패(오프라인 등) 시 잠그지 않는다 — 코스메틱 자산이라 가용성 우선.

## 초기 지급

마이그레이션 `b7c8d9e0f1a2` 이 cat grant 를 시드한다 (사용자 지시 2026-07-30):

- 대상: `hyein.lim213@gmail.com`, `codenavi@gmail.com` (note = "초기 지급 (2026-07-30)")
- 유저 행이 아직 없으면(미로그인) 스킵 — 최초 로그인 후 백오피스에서 수동 지급
- NOT EXISTS 가드로 멱등 — 재실행해도 중복 없음

## 관전 화면 테마 (2026-07-30 — [study-spectate.md](study-spectate.md))

관전자는 호스트의 테마로 화면을 본다 — `st.event` payload 에 `theme?: string` 이
자동 동봉되고(`game-ws.ts stEvent` 가 `getAppTheme()` 첨부), `/study/watch` 는
`data-theme` 속성만 일시 오버라이드한다 (언마운트 시 복원, `setAppTheme` 미사용 —
관전자의 저장 테마·엔타이틀먼트를 오염시키지 않기 위함).
