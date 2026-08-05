# 스펙: 테마 몰 (테마 엔타이틀먼트)

> 최종 검증: 2026-07-30 (코드 대조 완료) · 설계 승인: 2026-07-30 (사용자)
> 2026-08-04 부분 갱신(코드 대조): 테마 레지스트리·은유 배타성
> 2026-08-05 갱신: 여름 바다(ocean) 테마 신설

앱 테마 8종(note/candy/lego/cat/excel/school/academy/ocean — `frontend/src/lib/theme.ts` APP_THEMES. school=학교수업(칠판), academy=학원(갱지 모의고사) — 2026-08-04 분리. **ocean=여름 바다(물거품 카드·파도 물결·산호 채점·수영 튜브 낙하물·유리병 편지, 2026-08-05 신설)** — 전부 restricted)을 전원 무료에서 **엔타이틀먼트(보유권) 기반** 자산으로 전환한다. 이번 범위는 엔타이틀먼트 기반 + 백오피스 수동 지급/회수 + 헤냥이(cat) 제한이며, 결제(PG) 연동은 후속이다.

## 전략 3단

| 단계 | 상태 | 내용 |
|---|---|---|
| 무료 | 운영 중 | note 하나만 전원 사용 가능 (2026-07-30 전환 — 기본 테마는 노트뿐) |
| 업적 보상 | **운영 중** | theme_reward_rules 매핑으로 업적 달성 시 자동 지급 (첫 친구→candy, 첫 게임→lego). 백오피스에서 규칙 관리 |
| 이벤트 지급 | 운영 중 | restricted 테마를 백오피스에서 이메일로 수동 지급/회수. cat 은 초기 2계정 전용 |
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

theme_reward_rules (d1e2f3a4b5c6, 2026-07-30)
  id PK
  achievement_key String(64) -- achievements.DEFINITIONS 의 키
  theme_key String(32)       -- unique(achievement_key, theme_key)
  created_at
```

- 접근 정책: `backend/app/services/themes.py` — 기본값 `THEME_ACCESS`(**note 만 free, candy/lego/excel/cat/school/academy/ocean = restricted** — 2026-07-30 전환: 기본 테마는 노트 하나, 나머지는 업적 보상·이벤트 지급으로만. ocean 은 여름 시즌 지급 후보) 에 `theme_settings` 오버라이드를 병합한 `effective_theme_access(db)` 가 판정의 단일 진입점. 행 없음 = 기본값. 유효 키 목록·기본값은 코드가 정본(프론트 APP_THEMES 와 드리프트 방지).
- **업적 보상 지급 엔진** (`services/theme_rewards.py sync_theme_rewards`): GET /api/themes(AppNav 가드·설정)와 GET /api/study/achievements(학습 홈)에서 allowed 판정 **전에** 실행 — 규칙의 업적을 달성했고 미보유면 theme_grants INSERT(note="업적 달성: {제목}" 이력) + theme_granted 알림. 업적이 로그 소급 집계라 과거 달성자도 자동 지급(백필 불필요). 비용 가드: 미지급 규칙 테마가 없으면 업적 집계 생략(정착 상태 2쿼리).
- **영속 보장**: 규칙 삭제/변경은 이후 지급에만 영향 — 이미 지급된 grants 는 유지, note 가 지급 사유 이력. 초기 시드 규칙: 첫 친구→candy, 첫 게임(first_game 신설)→lego.
- 백오피스에서 테마별 무료<->제한 전환 가능. **note 는 잠금 복귀(fallback) 목적지라 제한 전환 금지** (`FALLBACK_THEME`).
- allowed 판정: free 전부 + 내 grants. **관리자는 grant 없이 전 테마 허용** (운영 확인용).
- 무료 전환 시 grants 행은 보존 — 재제한 시 다시 유효해진다.
- 회원탈퇴: `delete_me` 의 명시 삭제 목록에 포함 (sqlite 테스트에서 FK cascade 미작동 — Notification 전례).

## API

| 메서드/경로 | 역할 |
|---|---|
| GET `/api/themes` | (auth) 카탈로그 전체 `{items:[{key, access, allowed, unlock}]}` — unlock = 해금 업적 제목(규칙 있을 때, 설정 배지 문구). 조회 전 보상 동기화 실행 |
| GET `/api/admin/themes/rewards` | 보상 규칙 목록 + 업적 카탈로그 `{items, achievements}` |
| POST `/api/admin/themes/rewards` | 규칙 추가 `{achievement_key, theme_key}` — 404 `achievement_not_found`/`theme_not_found` / 409 `already_mapped` / 422 `theme_not_restricted` |
| DELETE `/api/admin/themes/rewards/{rule_id}` | 규칙 삭제 204 — 기존 지급 유지 |
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

## 테마 컨셉 단일 레지스트리 (2026-07-31 — 유지보수 계약)

`frontend/src/lib/theme-surfaces.ts` 가 화면별 테마 분기의 단일 정의처:
`SURFACE_SKINS`(시험지·학습 세션 문항 카드 공용 표면), `CLOCK_OF`(경과 시계 컨셉),
`CHAT_LABEL_OF`(채팅 라벨) + `chatNotice`(채팅 알림 문구 — 파생, [chat.md](chat.md) 내용 없는 알림),
`NAV_LABEL_OF`(나머지 4탭 라벨, 2026-08-03),
`boardThemeOf`(게임 보드 폴백 — 전용 스킨은 note/candy/lego/cat/school/academy/ocean, excel 은 위장 유지로 노트 폴백. 보드 자체 렌더는 `BoardCanvas` 의 PALETTES·drawBrickBody·drawBackground). 퀴즈 선지·어순 칩은 `SURFACE_SKINS.choice` 재사용 (2026-07-31 게임 테마화). **새 테마 추가 =
theme.ts 카탈로그 + globals.css 토큰 + theme-surfaces + 백엔드 THEME_ACCESS + layout.tsx 부트 스크립트 화이트리스트 5곳** —
화면 컴포넌트에 테마 하드코딩 금지. 절차 전체는 `.claude/rules/theme-addition.md`.

**은유 배타성** (2026-08-04): 한 물체는 한 테마만 쓴다. 두 사례로 확정 —
① 헤냥이가 학습·시험 표면에서 칠판을 써서 학교수업과 구분이 사라졌다 → 헤냥이는
크림 고양이 카드(발도장·살구 젤리)로. ② 학교수업 하나가 칠판과 갱지를 겸해 정체가
흐렸다 → **학교수업=칠판 / 학원(academy)=갱지 모의고사**로 분리. 한 테마가 두 은유를
겸하면 그 테마도, 나중에 그 은유를 쓰려는 테마도 흐려진다.

## 멘탈모델 접점 4종 (2026-07-30 — "테마 = 업적 보상" 각인)

| 접점 | 구현 |
|---|---|
| 획득 순간 축하 | WS `notif.new type=theme_granted` 수신 시 InviteToaster 가 축하 토스트(스와치+사유+[바로 적용]) — 바로 적용은 setAppTheme (방금 지급이라 안전). 10초 자동 소멸 |
| 잠긴 테마 욕망 설계 | 설정 잠금 배지 "'첫 친구' 달성 시 열려요" + 진행률 "진행 0/1" (unlock_key 로 업적 API 와 조인) |
| 스티커 보상 예고 | 업적 스티커에 칩 — 미달성 "보상: 캔디 테마" / 달성 "캔디 테마 획득" (achievements API 의 reward_theme) |
| 멘탈모델 카피 | 설정 테마 섹션 부제 "새 테마는 업적을 달성하거나 이벤트로 받으면 열려요" |
| 대비 토큰 | 유색(brick-*) 배경 버튼의 글자는 `text-brick-label` 강제 — 파스텔 테마에서 잉크색으로 재정의되므로 `text-white` 하드코딩 금지 (2026-07-31 일괄 치환) |

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
