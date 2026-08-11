# 스펙: 캐릭터 상점 — 마스코트·악세사리·책갈피 (XP 소비)

> 작성: 2026-08-11 (구현 동시) · 기획: [proposal/xp-shop-mascot-2026-08.md](../proposal/xp-shop-mascot-2026-08.md)

XP 로 움직이는 캐릭터(마스코트)와 악세사리를 사서 **좌하단에 상시 노출**한다.
벤치마크 원칙(Habitica/Forest): 꾸민 결과는 별도 화면이 아니라 매일 보는 화면에
있어야 동기가 된다. 테마몰과 같은 엔타이틀먼트 패턴 — 카탈로그·가격은 코드가
단일 근거(`services/mascots.py`), 보유는 `item_grants` 행 존재, 소비는 `xp_spends`.

## 카탈로그 (가격 = 일일 획득량 ~500XP 기준 층위화)

| 종류 | 키 | 가격 | 비고 |
|---|---|---|---|
| 마스코트 | henyang 헤냥이 2000 / bricky 브리키 1500 / mongi 몽이 1500 | | 1개 활성(`user_settings.mascot_key`), 구매 즉시 자동 활성 — 산 캐릭터가 바로 화면에 |
| 악세사리 | ribbon 300 / glasses 400 / scarf 500 / crown 1000 | | **all-on**: 보유하면 활성 마스코트에 전부 착용 (착용 토글 없음 — 2026-08-11 사용자 결정) |
| 책갈피 충전 | 500 XP | | 주 1회 무료 지급과 별개, 최대 보유 `SAVER_MAX`(2) 동일 — 손실 회피 상품(벤치마크 1순위) |

테마 가격도 같은 마이그레이션(3d4c34e2c8d9)이 시드했다 — candy/lego 500,
school/academy 800, ocean/excel 1200, cat 2000 (백오피스 기입 가격은 덮지 않음).
"XP 로 살 수 있는 게 없다"(2026-08-11 보고)의 원인은 가격 미입력이었다.

## API

| 메서드/경로 | 역할 |
|---|---|
| GET `/api/shop` | 지갑(available_xp)+활성 마스코트+마스코트/악세 목록(owned·유효가·sale)+책갈피 상태 |
| POST `/api/shop/purchase` | `{item_key: "mascot:x"\|"outfit:x"}` — 404 미존재 / 409 보유 / 422 잔액 부족·`event_only_item`. 마스코트는 구매 시 자동 활성 |
| PATCH `/api/shop/mascot` | `{key\|null}` 활성 변경 — 403 미보유, null=끄기("쉬게 하기") |
| POST `/api/shop/streak-saver/purchase` | 422 `saver_full`(최대 2)/`insufficient_xp` |
| GET `/api/shop/purchases` | 내 구매 이력 최신 50건 — 품목·결제수단·금액·시각 |

## 구매 이력 (2026-08-11)

`purchases` 원장 — 사용자별 무엇을 언제 어떤 결제수단으로 얼마에 샀는가.
`xp_spends` 는 지갑(가용 XP 차감) 원장, `purchases` 는 구매 내역 원장으로 분리 —
`method`("xp", 현금·카드 도입 대비)·`currency` 컬럼 보유. 테마·마스코트·악세·
책갈피 구매 3경로 모두 기록하며, 기존 `xp_spends` 전량을 XP 결제로 백필했다
(마이그레이션 7107c0984dc7). **어드민 지급은 구매가 아니므로 기록하지 않는다.**
설정 화면 "구매 내역" 접기에서 조회 (`PurchaseHistory`, 펼칠 때 로드).

## 백오피스 관리 (`/admin/shop`, 2026-08-11)

테마 몰과 같은 관리 모델 — `item_settings` 오버라이드 (행 없음 = 카탈로그 기본):

| 메서드/경로 | 역할 |
|---|---|
| GET `/api/admin/shop` | 카탈로그+유효가+판매 방식+보유자 수 |
| PATCH `/api/admin/shop/{item_key}` | `{price_xp?}` 가격 오버라이드(null=기본가 복귀) / `{sale?}` "xp"\|"event" |
| GET·POST `/api/admin/shop/{item_key}/grants` | 보유자 목록 / 이메일 지급 (409 중복, `item_granted` 벨 알림) |
| DELETE `/api/admin/shop/grants/{id}` | 회수 — 다음 조회부터 미보유 |

`sale="event"` = 이벤트 한정: 잔액과 무관하게 XP 구매 422, 상점 카드는
"이벤트 한정" 배지(구매 버튼 없음). 유효 정책은 `services/mascots.item_policies`
가 단일 근거 — 카탈로그 조회와 구매 검증이 같은 값을 본다.

## 렌더링 계약

- `MascotPeek`(layout 전역, 구 HenyangPeek 대체): GET /api/shop 로 활성+보유 악세를
  읽어 `MascotSvg` 렌더. 미로그인/실패 = 테마 폴백만. **cat 테마 하위호환**:
  활성 마스코트 없어도 헤냥이 노출(테마 정체성). 구매·활성 변경 시 `SHOP_EVENT`
  (`shop-api.ts`)로 즉시 갱신.
- 슬롯: 좌하단 고정 (ui-design.md — 우하단은 채팅 런처 전용). 기존 `.henyang-peek`
  CSS 훅 재사용 — game-focus/chat-focus 숨김, 모바일 탭바 회피 그대로.
- `MascotSvg(kind, outfits, flip)`: 104x88 공통 캔버스, 악세는 캐릭터별 명시
  앵커로 겹쳐 그림. **flip**: 표시 컨테이너가 좌우 반전이라 말풍선만 SVG 내부
  역반전 — 글자가 뒤집히던 버그(1차 시각 검증에서 발견, 구 헤냥이도 동일했음).
- idle 애니메이션: 헤냥이=giggle(3.2s) / 브리키=bounce(2.6s) / 몽이=float(4s) —
  globals.css `mascot-anim-*`.

## 검증 절차 (새 마스코트/악세 추가 시 필수)

`/design/mascots` QA 픽스처(네비 미등록)에서 캐릭터 x 악세 조합을 원본/반전
양방향으로 확인한다 — ① 말풍선 글자 정방향 ② 악세가 입·눈을 가리지 않음
③ idle 애니메이션 3종 작동(시간차 좌표 측정). 2026-08-11 초도 검증 4회에서
말풍선 반전·브리키/몽이 목도리 입 가림·리본 부유를 발견해 수정했다.

## 플레이어 배지 (2026-08-11 — 경쟁 동기)

마스코트와 **대표 업적 칭호**가 대전·대기실·리더보드에서 프로필로 보인다:

- 대표 업적: 학습 탭 업적 스티커(달성분)를 탭해 지정 — `user_settings.
  featured_achievement`, PATCH `/api/settings` (미달성 422, "" = 해제).
  칭호 = 업적 제목 (`profiles.ACHIEVEMENT_TITLES`)
- 서버 부착: `services/game/profiles.safe_player_badges` — 방 브로드캐스트
  (`tp/sc/dt/bg.room` `profiles`, `qr.room` players 인라인), `tp.start`,
  테트리스 `match.found.opponent_profile`, 리더보드 2종(`/game/leaderboard`,
  `/game/leaderboards`). 조회 실패는 빈 dict 폴백 — 게임을 막지 않는다
- 프론트: `PlayerBadge`(아바타 `MascotSvg avatar` + 이름 + 칭호) — 대기실
  칩·결과 행·테트리스 헤더/PiP/결과·주간 명예의 전당 공용

## 설정 화면

테마 섹션 아래 "캐릭터 상점"(`MascotShopSection`): **XpWallet 지갑 카드**(테마
섹션과 공용 — "보유 XP 가 안 보인다" 2026-08-11 보고로 강조 배치, 부족 시 버튼에
부족분 표기), 마스코트 카드(미리보기 SVG — 미보유는 흑백+실루엣 느낌, 수집
도감식), 데려오기/쉬게 하기, 악세 칩(사면 "착용 중"), 책갈피 충전, 구매 내역
접기. 구매 실패 카피: XP 부족/이미 보유/책갈피 최대.
