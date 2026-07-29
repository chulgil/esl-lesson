---
name: cg-resume
description: "이전 세션이 끊겼거나 새 세션에서 컨텍스트가 비어 있을 때 .harness/ 의 handoff + spec + journal + drift.json 을 읽어 1분 안에 재개점을 복원. 트리거: resume, 이어서, 어디까지 했지, where was i, 이어가기, restore context."
---

# cg-resume — 세션 재개점 복원

## 트리거 키워드

`resume`, `이어서`, `어디까지 했지`, `where was i`, `이어가기`,
`restore context`, `세션 복원`, `다시 시작`.

## 목적

새 세션을 열거나 `/compact` 후 컨텍스트가 비어 있을 때, `.harness/` 의
파일들을 읽어 다음 3가지를 1분 안에 복원:
1. **마지막에 무엇을 하고 있었는가** (active feature, 진행 단계).
2. **다음에 무엇을 해야 하는가** (단 하나의 다음 액션).
3. **떨어진 컨텍스트가 있는가** (drift 신호).

## 입력 우선순위

1. `.harness/status/handoff.md` — **가장 최근 working-set 스냅샷** (PreCompact/SessionEnd 훅이 자동 기록). 있으면 여기부터: 브랜치·미커밋 수·활성 spec·journal tail 이 한 곳에 모여 있다.
2. `.harness/status/drift.json` — 가장 최근 세션의 변경 스냅샷.
3. `.harness/journal/{today}.md` 또는 가장 최근 journal — 최근 결정.
4. `.harness/spec/` 의 가장 최근 `*-{feature}.md` — active feature.
5. `.harness/spec/ac-tree-*-{feature}.md` — 마지막 AC 진행도.
6. `.harness/lore/*.md` — **미해결 lore candidate** (trailer 미커밋 결정).
7. `.harness/recipes/*.md` — **미승격 recipe candidate** (반복 패턴 미스킬).

## 절차

1. **active feature 식별**
   - `ac-tree-*.md` 중 `in_progress` 상태가 1개 이상인 파일 = 현재 feature.
   - 없으면 가장 최근에 수정된 `spec/*.md` 의 feature slug.

2. **진행 단계 추정** (Phase 0~6)
   - spec 없음 → Phase 0/1
   - spec 있고 decomposition 없음 → Phase 2/3
   - decomposition 있고 journal 없음 → Phase 4
   - journal 1+ 엔트리 → Phase 5
   - 모든 AC `passed` → Phase 6 (cg-evaluation)

3. **drift 점검**
   - drift.json 의 `summary.warnings` 가 비어 있지 않으면 cg-status 추천.

4. **저널 마지막 3 엔트리 요약**
   - 가장 최근 journal 의 마지막 3개 bullet 만 발췌.

5. **누적 학습 미해결 항목 점검** (조용히 스킵 가능)
   - `.harness/lore/*.md` (archive/ 제외) — 검토 대기 중인 결정 candidate.
   - `.harness/recipes/*.md` — 검토 대기 중인 반복 패턴 candidate.
   - 둘 다 0개면 출력 생략. 1개 이상이면 "다음 행동" 다음 줄에 한 줄 안내.

## 출력 포맷

```
세션 복원 리포트
============================================================
Active feature: {feature-slug}
추정 단계: Phase 5 (cg-execution-loop)

마지막 3 엔트리 (.harness/journal/2026-04-24.md):
  - 13:42 cg-execution-loop: AC-2.1 passed (테스트 7개 추가)
  - 14:05 lore-commit: SSE 채택 (rejected: WebSocket — 양방향 불필요)
  - 14:30 cg-evaluation Critic 1: PASS, Critic 2 진행 중

AC Tree 진행도:
  passed 5 / 12, in_progress 1, pending 6, failed 0

Drift: ON-TRACK (경고 없음)

다음 단 하나의 행동:
  cg-evaluation 의 Critic 2 (Test Critic) 결과 확인 후
  failed/pending 처리 결정.

미해결 학습 항목 (선택):
  lore candidate 2건, recipe candidate 1건 — `cg lore propose` /
  `cg recipe propose` 로 검토 후 promote.
```

## 원칙

- `.harness/` 파일을 읽기만 한다 (write 금지).
- 추정이 모호하면 "추정" 임을 명시. 단정하지 않는다.
- spec 본문 전체를 다시 읽지 않는다 — 헤더 + AC Tree 만으로 1분 안에.
- drift 경고가 있으면 곧바로 다음 액션을 cg-status 로 위임.
