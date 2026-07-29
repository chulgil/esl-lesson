---
name: cg-plan-check
description: Phase 4.5 — 실행 전 계획 검증 게이트. cg-decomposition 산출(DAG+AC Tree)이 spec 목표를 실제로 달성하는지 fresh-context 로 goal-backward 검증하고 PASS/REVISE 판정. Phase 5 진입 전 필수. 트리거: plan check, 계획 검증, 실행 전 점검, decomposition 검토.
---

# Phase 4.5 — Plan Check (실행 전 계획 검증 게이트)

## 목적

**한 줄: 잘못된 계획을 실행으로 옮기기 전에 잡는다.**

cg 의 다른 검증은 전부 사후(post-hoc) — 코드를 짠 뒤 본다. 이 게이트는 Phase 4(분해)와
Phase 5(실행) 사이에서, 아직 코드가 없을 때 **계획 자체**가 spec 목표를 달성하는지
검증한다. 실행 컨텍스트를 태우기 전에 되돌리는 비용이 가장 싸다.

> 비유: 출발 전에 지도를 거꾸로 짚어보는 것 — 도착지(목표)에서 출발해 각
> 갈림길(job)이 정말 그 길로 이어지는지 역으로 확인한다(goal-backward).

## 입력

- `.harness/spec/{date}-{feature}.md` (성공 기준)
- `.harness/spec/decomposition-{date}-{feature}.md` (DAG)
- `.harness/spec/ac-tree-{date}-{feature}.md` (AC Tree)
- `.harness/spec/constitution.md` (프로젝트 불변원칙 — 있으면 §Constitution Check 수행)

## 격리 (필수)

이 검증을 **계획을 쓴 세션이 하면 편향된다**. `plan-checker` 에이전트(별개 컨텍스트)
로 호출한다 — test-critic 과 같은 Oracle Problem 방어.

## goal-backward 체크리스트

도착지(spec 성공기준 / AC Tree leaf)에서 출발해 거꾸로 짚는다:

| # | 질문 | REVISE 신호 |
|---|------|------------|
| 1 | spec 의 각 성공기준마다 담당 job 이 있는가? | 커버 안 되는 기준 존재 |
| 2 | **key link(와이어링)가 명시 job 인가?** | 통합/연결 지점이 어느 job 에도 없음 |
| 3 | 범위를 넘는 job(scope creep)이 있는가? | spec 에 없는 기능 job |
| 4 | 단일 job 이 한 세션 컨텍스트(50%)를 넘기는가? | 너무 큰 job — 쪼개야 함 |
| 5 | DAG 의존성에 빠진 엣지가 있는가? | 암묵적 선행관계 누락 |
| 6 | eval job 이 dev job 과 분리됐는가? | 섞임 (Oracle Problem) |

> #2 가 핵심: 연구상 **스텁의 80%는 "만들었지만 연결 안 한" 미연결 링크에 숨는다**.
> A 만들고 B 만들었는데 A↔B 를 잇는 job 이 없으면 실행 후에도 동작하지 않는다.

## Constitution Check (MUST 게이트)

> spec-kit 패턴 흡수: 오류를 생성 후 검증이 아니라 **계획 단계에서 차단**한다.

`.harness/spec/constitution.md` 가 존재하면, 계획(DAG 의 각 job)이 각 MUST 를
위반하는지 **항목별로** 검사한다. constitution.md 가 없으면 이 검사는 스킵하고
"constitution.md 없음 — Constitution Check 스킵" 1줄만 출력한다.

| 검사 결과 | 판정 |
|----------|------|
| 위반 없음 | goal-backward 결과에 따라 PASS/REVISE |
| 위반 발견 | 기본 **REVISE** — 위반 원칙(MUST #)과 해당 job 을 명시해 Phase 4 복귀 |
| 위반이 의도적·불가피 | **정당화 기록 강제** — 계획 문서에 `## Complexity Tracking` 이 있으면 **PASS-with-justification** |

### Complexity Tracking (정당화 기록)

위반을 안고 가려면 계획 문서(decomposition)에 다음 3슬롯을 기록해야 한다:

```markdown
## Complexity Tracking
- 위반 원칙: {constitution MUST #N — 원칙 한 줄 인용}
- 왜 불가피한가: {제약/트레이드오프 설명}
- 더 단순한 대안을 기각한 이유: {대안 + 기각 사유}
```

3슬롯 중 하나라도 비면 정당화로 인정하지 않는다 → REVISE.

## 판정

- **PASS** → Phase 5(cg-execution-loop) 진입.
- **PASS-with-justification** → constitution 위반이 있으나 Complexity Tracking
  정당화가 기록됨. Phase 5 진입 가능 — 출력에 위반 원칙과 정당화 위치를 명시.
- **REVISE** → 구체적 갭 목록과 함께 Phase 4(cg-decomposition)로 복귀. 최대 3회.
- 3회 후에도 REVISE → 사용자에게 보고(스펙 자체가 모호할 가능성 — Phase 2 복귀 검토).

## 출력 포맷 (Verifier 역할, 200단어 이내)

```
**요약**: {feature} 계획 검증 — job {N}개 / 성공기준 {M}개
**판정**: PASS / PASS-with-justification / REVISE
**커버리지**: 성공기준 {M}개 중 {k}개 담당 job 확인
**Constitution**: 위반 0건 / 위반 {n}건(정당화 {m}건) / constitution.md 없음 — 스킵
**미연결 링크** (있으면): {A→B 연결 job 없음}
**REVISE 항목** (REVISE 시): {구체적 갭 + 어느 job 을 추가/수정}
```

## 금지

- 계획 작성 세션에서 인라인 평가 (격리 위반).
- "job 이 많으니 괜찮겠지" — 커버리지는 개수가 아니라 성공기준 대응으로 판정.
- REVISE 인데 "사소하니 진행" — 미연결 링크 1개가 기능 전체를 죽인다.
- constitution 위반을 정당화 기록 없이 "합리적이니 PASS" — Complexity Tracking
  3슬롯이 없는 위반은 예외 없이 REVISE.

## 관련

- 입력: `cg-decomposition` (Phase 4) · 후행: `cg-execution-loop` (Phase 5)
- 에이전트: `plan-checker` (별개 컨텍스트)
- 게이트 입력: `.harness/spec/constitution.md` — `cg-interview` (Phase 1) 가 생성·갱신
- 사후 검증: `cg-evaluation` (Phase 6, 코드 작성 후)
