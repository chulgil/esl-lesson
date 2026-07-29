---
name: cg-execution-loop
description: Phase 5 — DAG 의 각 job 을 순서대로 구현하고 커밋합니다. Steer 메시지를 주기적으로 확인하고, 실패 시 재시도 컨텍스트와 함께 루프.
---

# Phase 5 — Execution Loop

## 목적

Phase 4 의 DAG 를 **실행** 합니다. 각 job 단위로 구현 → 커밋 → 다음 job 을 반복합니다.

> **진입 전제**: `cg-plan-check`(Phase 4.5) 게이트가 PASS 여야 한다. REVISE 면 코드를 짜기 전에 Phase 4 로 복귀해 계획을 고친다 (실행 컨텍스트를 태우기 전 되돌리는 비용이 가장 싸다).

## 입력

- Phase 4 의 `decomposition-{...}.md`
- `harness/current.md` (품질 계약)

## 출력

- 각 job 단위 커밋
- `.harness/journal/{YYYY-MM-DD}.md` 엔트리

## 루프

```
for job in topological_order(DAG):
    1. Steer inbox 확인 (.harness/steer/inbox.md)
       - emergency → 중단
       - directive → 우선순위 재계산
       - context → 기록만
    2. Job 컨텍스트 로드 (spec + 관련 이전 job 산출물)
    3. 구현
    4. 로컬 검증 (lint + 단위 테스트)
    5. 커밋 (한국어 Conventional Commits)
       - 실패 시 최대 3회 재시도 (실패 컨텍스트 포함)
    6. Journal 엔트리 추가
```

## 커밋 메시지 포맷

```
<type>(<scope>): <한 줄 요약>

- 무엇을 왜 바꿨는지 본문에 설명
- 스펙의 어느 성공 기준을 충족하는지 명시

Refs: .harness/spec/{YYYY-MM-DD}-{feature}.md#J1
```

## 실패 처리

| 실패 유형 | 조치 |
|---------|------|
| Lint 실패 | 자동 수정 후 재시도 |
| 단위 테스트 실패 | 원인 파악 → 코드 수정 → 재시도 (최대 3회) |
| 3회 실패 | 해당 job blocked 표시, 사용자 보고, 다음 독립 job 으로 진행 |

## 원칙

- **surgical changes**: 요청된 것만 변경. 주변 리팩토링 금지.
- **커밋 단위 = 검증 단위**: 커밋 전에 반드시 로컬 검증.
- **Journal 은 간결하게**: 무엇을 했고, 무슨 결정을 했는지 3-5줄.

## 경량 모드 — PGE (Plan-Generate-Evaluate)

간단 변경 (3 파일 미만 · 새 도메인 없음 · 마이그레이션 없음 · 보안/billing 무관 · 외부
인터페이스 불변) 은 7-Phase 대신 **Plan → Generate → Evaluate** 3단계로. 진입 조건을
하나라도 어기거나 진행 중 신호가 잡히면 즉시 7-Phase 로 회귀. Evaluate 도 격리(Agent
도구) 강제 — 인라인 평가 금지.

## 종료 후 누적 (선택)

Phase 5 종료 후 학습 자산을 누적합니다 (둘 다 **사람 게이트 필수**, 자동 적재 금지):

- **Recipe Promotion** — 반복된 명령(3회+) 을 스킬로. `cg recipe propose` → 검토 → `cg recipe promote`.
- **Lore Proposal** — journal `결정:` 블록을 git trailer 후보로. `cg lore propose` → 검토 → 커밋 trailer 추가 → `cg lore promote`.

## Journal 엔트리

각 job 완료 시 `{HH:MM} — {job-id}: {요약}` 헤더 + `결정` / `산출물(commit·files)` / `비고` 블록을 추가.

> 상세: [reference.md](reference.md) — PGE 진입조건·3단계·회귀 트리거 / Recipe·Lore 전체 절차 / Journal 포맷 템플릿.
