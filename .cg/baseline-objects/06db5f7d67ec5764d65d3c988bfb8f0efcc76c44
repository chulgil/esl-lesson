---
name: cg-status
description: "현재 하네스 세션 상태 + 드리프트 리포트. `.harness/status/drift.json` 을 읽어 AC Tree · spec · journal 정합성을 확인. Adapted from Q00/ouroboros (MIT)."
---

# cg-status — 세션 상태 & 드리프트 조회

**트리거 키워드**: "드리프트", "drift", "status", "내가 벗어나고 있나?", "session status"

## 목적

ouroboros 의 `ooo status` 패턴을 파일 기반으로 재현. 현재 세션이 원 spec
으로부터 얼마나 벗어났는지, AC Tree 가 정상적으로 갱신되고 있는지,
journal 이 최신인지를 한 번에 보여준다.

## 입력

- `.harness/status/drift.json` (drift-monitor 훅이 기록)
- `.harness/spec/ac-tree-{YYYY-MM-DD}-{feature}.md` (최신 AC Tree)
- `.harness/journal/{YYYY-MM-DD}.md` (최신 journal)

## 절차

1. **drift.json 읽기**
   - 파일 없음 → "Phase 5 (cg-execution-loop) 부터 시작하세요" 안내
   - 파일 있음 → `summary` 섹션 파싱

2. **AC Tree 상태 집계**
   - 최신 `ac-tree-*.md` 에서 `pending / in_progress / passed / failed` 카운트
   - `failed` 1개 이상 → 경고

3. **journal fresh 체크**
   - 최신 journal 파일이 있는가? (오늘 날짜)
   - 마지막 엔트리 시각 비교

4. **Drift Verdict 산출**

   | 조건 | Verdict | 다음 행동 |
   |---|---|---|
   | failed AC 없음 + journal fresh + drift 경고 없음 | ON-TRACK | 계속 진행 |
   | drift 경고 1-2건 | WATCH | 다음 커밋 전 점검 |
   | failed AC 있음 또는 drift 경고 3+ 건 | DRIFTING | /cg-unstuck 또는 spec 재작성 |

## 출력 포맷

```
Status Report — {YYYY-MM-DD HH:MM}
============================================================
Project: {project-slug}
Active feature: {feature-slug}

AC Tree:
  passed:       5 / 12
  in_progress:  2
  pending:      5
  failed:       0

Journal:
  Latest entry: 3 분 전 (fresh)
  Today's file: .harness/journal/2026-04-24.md

Drift signals:
  - changed_spec_files: 0
  - spec_changed_without_ac_update: false
  - journal_stale: false

Verdict: ON-TRACK
📍 다음: cg-execution-loop 계속
```

## 경고 행동

- **DRIFTING** 시 자동으로 `/cg-unstuck` 페르소나 "contrarian" 을 추천
- **WATCH** 시 "AC Tree 재갱신 후 다음 커밋" 안내
- **data missing** 시 Phase 4 (cg-decomposition) 부터 AC Tree 작성 권고

## 원칙

- 상태 조회만 하고 파일을 **수정하지 않는다** (drift-monitor 만 기록)
- drift.json 에 누적된 세션 간 비교는 **AC Tree 파일명 변경** 으로도 추적
- LLM 기반 세만틱 비교는 이 스킬의 범위 외. 필요 시 cg-evaluation 호출
