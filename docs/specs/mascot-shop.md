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
| GET `/api/shop` | 지갑(available_xp)+활성 마스코트+마스코트/악세 목록(owned)+책갈피 상태 |
| POST `/api/shop/purchase` | `{item_key: "mascot:x"\|"outfit:x"}` — 404 미존재 / 409 보유 / 422 잔액 부족. 마스코트는 구매 시 자동 활성 |
| PATCH `/api/shop/mascot` | `{key\|null}` 활성 변경 — 403 미보유, null=끄기("쉬게 하기") |
| POST `/api/shop/streak-saver/purchase` | 422 `saver_full`(최대 2)/`insufficient_xp` |

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

## 설정 화면

테마 섹션 아래 "캐릭터 상점"(`MascotShopSection`): 보유 XP 배지, 마스코트 카드
(미리보기 SVG — 미보유는 흑백+실루엣 느낌, 수집 도감식), 데려오기/쉬게 하기,
악세 칩(사면 "착용 중"), 책갈피 충전. 구매 실패 카피: XP 부족/이미 보유/책갈피 최대.
