---
name: cg-ui-loop
description: "Flutter/UI 변경을 시각 증거로 검증하는 루프. 골든 비전 비교 + (옵트인) hot reload·E2E. 트리거: UI 루프, 골든 테스트, 화면 검증, 픽셀 퍼펙트, 시안 맞추기, 디자인 회귀."
---

# cg-ui-loop — 루프에 눈을 단다 (UI 관측 루프)

## 개요

기계 게이트(lint/test/build)는 "코드가 컴파일되고 로직이 맞다"까지만 보장한다.
UI 는 **보이는 것이 정답** — 검증자가 화면을 직접 봐야 루프가 수렴한다.
이 스킬은 UI 작업의 검증 루프를 정의한다(ralph 구성도 설치되어 있다면 cg-ralph 의 VERIFY 단계를 확장한다): 코드 수정 → 렌더 →
시각 증거(골든 PNG/스크린샷) 획득 → 비전 비평 → 재수정.

> 2026 수렴 사례: Dart MCP agentic hot reload(공식) · VGV 골든 비전 비교 루프 ·
> Maestro/Patrol E2E 게이트. 핵심 통찰: "에이전트의 자기보고를 믿지 말고,
> 검증자가 화면을 직접 열어 본다(browser/device-verified evaluator)."

## UI 검증 사다리 (아래칸부터, 멈추는 칸이 검증 수준)

| 단 | 검증 | 도구 | 비용 | 적용 |
|---|---|---|---|---|
| 1 | 정적+위젯 테스트 | `flutter analyze` + `flutter test` (기존 게이트) | 낮음 | 모든 UI 변경 (fast~) |
| 2 | 골든 회귀 | 골든 테스트 — mechanical `ui` 게이트 (opt-in) | 낮음 | 디자인 시스템·공용 위젯 (balanced~) |
| 3 | 비전 비평 루프 | 골든 PNG 를 에이전트가 Read 로 직접 보고 시안과 비교 | 중간 | 새 화면·시안 구현 (balanced~) |
| 4 | 실기 관측 | Dart MCP hot reload + 런타임 에러 조회 (옵트인 companion) | 중간 | 상호작용·상태 흐름 (ultra) |
| 5 | E2E 플로우 | Maestro / Patrol / `integration_test` — mechanical `e2e` 게이트 (opt-in) | 높음 | 핵심 여정, 릴리스 전 (ultra) |

- adaptive-quality 매핑: fast=1단, balanced=1~3단, ultra=1~5단.
- 1~3단은 **의존성 0** (flutter test 만으로 동작). 4~5단은 옵트인 도구 (`cg companion doctor`).

## 골든 비전 비교 루프 (3단 — 핵심 절차)

```
반복 (max_iterations 명시, ralph 구성도 설치되어 있다면 cg-ralph 규약 동일):
  1. 시안 확보 — .harness/visuals/{feature}/ 목업 또는 디자인 export PNG
  2. 대상 위젯의 골든 테스트 작성 → 골든 생성:
     flutter test --no-pub --update-goldens test/golden/{feature}_golden_test.dart
     (이 시점의 골든은 "임시" — 아직 정답이 아니라 현재 상태의 스냅샷)
  3. 골든 PNG 를 Read 도구로 직접 열어 본다 (비전) → 시안 대비 차이를
     레이아웃 / 색·타이포 / 간격·정렬 축으로 서술
  4. 차이가 있으면 코드 수정 → 2 로 (골든 재생성) · 없으면 수렴
  5. 수렴 시 사람 확인 후 골든 확정(커밋) — 확정 전 골든은 정답이 아니다
```

- 판정 기록: `.harness/status/loop-trace.jsonl` 에 `"gate": "ui"` 로 append (cg-ralph 규약).
- **비전의 한계**: 1px 오차·그림자·미세 색차는 놓친다. 정밀도가 중요하면 픽셀 diff
  (골든 테스트의 기본 비교기)를 함께 신뢰 — 비전은 "무엇이 왜 다른가" 서술용,
  픽셀 diff 는 "다르다/같다" 판정용.
- 뷰포트 2종 이상: phone(390x844) + tablet(1024x768) — 반응형 깨짐이 최다 회귀.

## 적대적 방어 — 골든은 검증자산이다 (pump-and-pass 차단)

골든 파일을 루프 안에서 `--update-goldens` 로 덮어쓰면 **어떤 UI 회귀든 통과**한다.
이것은 테스트 삭제와 같은 검증 해킹이다. ralph 구성도 설치되어 있다면 cg-ralph 이중 제약 게이트가 그대로 적용된다:

- 루프 안에서 **기존(확정된) 골든 파일 갱신 금지** — 갱신이 diff 에 있으면 verdict 무효(FAIL).
- 3단 루프의 "임시 골든"은 예외 — 아직 확정 전이므로 재생성이 곧 진행. 단 **확정(커밋)은
  사람 게이트**를 통과해야 한다.
- 의도된 디자인 변경으로 확정 골든을 갱신해야 하면: 루프를 멈추고 변경 사유 + before/after
  를 보고 → 사람 승인 후 갱신.
- 독립 critic(cg-evaluation)은 작성 세션의 "화면 확인했다" 자기보고를 믿지 않는다 —
  골든 PNG/스크린샷을 **직접 열어** 판정한다.

## 기계 게이트 연결 (opt-in)

`.cg/mechanical.toml` `[frontend]` 에 주석 해제로 편입:

```toml
ui  = "flutter test --no-pub --tags golden"      # 2단 — 결정적 UI 회귀
e2e = "flutter test integration_test --no-pub"   # 5단 — 또는 "maestro test .maestro/"
```

실행: `cg diagnose --section frontend --gate ui` (ralph 구성도 설치되어 있다면 cg-ralph VERIFY 의 UI 작업 시 포함).
골든 테스트에는 `@Tags(['golden'])` 를 달아 일반 test 게이트와 분리한다.

## 옵트인 도구 (4~5단)

| 도구 | 용도 | 확인 |
|---|---|---|
| Dart MCP 서버 (공식) | hot reload·런타임 에러·위젯트리를 에이전트 도구로 | `claude mcp add dart -- dart mcp-server` (Dart 3.12+/Flutter 3.44+) |
| mcp_flutter | 시맨틱 스냅샷 + tap/type/scroll 구동 (서드파티) | github.com/Arenukvern/mcp_flutter |
| Maestro | YAML E2E 플로우 + 실기기 스크린샷 | `cg companion doctor` — maestro |
| Patrol | Dart 네이티브 E2E (권한·생체·푸시) | pub.dev/packages/patrol — CI flaky 주의 |

Flutter web 기반 관측은 불안정 — iOS/Android 에뮬레이터를 기본으로 한다.

## 종료 처리

| 종료 사유 | 다음 단계 |
|---|---|
| 수렴 (시안 일치 + ui 게이트 green) | 사람 확인 → 골든 확정 커밋 → cg-evaluation |
| max_iterations 도달 | 미해소 차이 목록 보고 — 시안 자체의 모호함이면 cg-interview 로 |
| 정체·진동 감지 | cg-ralph 에스컬레이션 사다리 (ralph 구성 설치 시; 같은 재시도 금지) |

## 관계

- [cg-ralph](../cg-ralph/SKILL.md) (ralph 구성 설치 시): 루프 본체(사다리·이중 제약·trace) — 이 스킬은 VERIFY 의 UI 확장
- [cg-visuals](../cg-visuals/SKILL.md): 3단 루프의 시안 소스 (`.harness/visuals/`)
- [frontend-verify.md](../../rules/frontend-verify.md): UI 회귀 검증 룰 — Flutter 네이티브 절차의 정본
- [cg-evaluation](../cg-evaluation/SKILL.md): 독립 critic 의 시각 증거 직접 확인
