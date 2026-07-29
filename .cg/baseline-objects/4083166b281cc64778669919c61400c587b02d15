---
name: cg-recipe-promotion
description: |
  Phase 5 journal 에서 3회 이상 반복된 명령을 recipe candidate 로 제안하고,
  사용자 승인 후 정식 스킬로 승격합니다. 데몬 없음 · Auto-merge 금지.
  트리거: /recipe-propose, "반복 패턴", "스킬 누적", "recipe promote".
---

# Skill — Recipe Promotion (이벤트 기반 누적 학습)

## 목적

Phase 5 Execution Loop 의 journal 엔트리에서 **반복되는 명령 패턴** 을 감지해
재사용 가능한 학습 자산으로 누적합니다.

> Hermes Agent 의 "자가 진화 스킬" 메커니즘을 cg-harness 철학에 맞게 경량화한
> 패턴. **사람 게이트 강제** 로 자동 변형을 차단합니다.

## 입력

- `.harness/journal/*.md` — 반복 패턴 감지 대상.
- `.harness/recipes/{slug}.md` — 이미 작성된 candidate (status: candidate).

## 출력

- `.harness/recipes/{slug}.md` — 새 candidate (사용자 검토 대기).
- `.claude/skills/{slug}/SKILL.md` — 승격된 스킬 (사용자 명시 승인 후).

## 흐름

```
1. propose       — cg recipe propose [--threshold N] [--json]
                   → 임계 이상 반복된 명령을 candidate 로 작성
   ↓
2. 사람 검토      — .harness/recipes/{slug}.md 열어 체크리스트 확인
                   - 재사용 가치?
                   - 매개변수화 필요?
                   - 트리거 조건은?
   ↓
3. promote       — cg recipe promote {slug}
                   → .claude/skills/{slug}/SKILL.md 생성
                   → SKILL.md 직접 편집해 description / 매개변수 보강
```

## 사용 시점

| 시점 | 행동 |
|---|---|
| Phase 5 완료 후 | `cg recipe propose --json` 으로 후보 확인 |
| 새 journal 엔트리 10+ 누적 | propose 재실행 (이전 candidate 는 skipped) |
| 동일 명령이 PGE 모드에서 반복 | 7-Phase 회귀 트리거 아님 (단순 반복은 PGE 정상 패턴) |

## 원칙

- **데몬/스케줄러 사용 금지** — Hermes 와 달리 24/7 자율 실행 안 함.
- **Auto-promote 금지** — candidate 는 항상 사람 검토를 거친 후 promote.
- **로컬 파일만 사용** — 벡터 DB / Ollama / 외부 임베딩 의존성 0.
- **격리는 호출자 책임** — Code Critic 평가가 필요하면 `cg-evaluation` Writer ≠
  Evaluator 게이트를 따로 걸 것.

## 임계값 가이드

| 임계 (회) | 적합 상황 |
|---|---|
| 3 (기본) | 일상 개발 — 반복은 빠르게 자산화 |
| 5 | 대규모 프로젝트 — 진짜 빈번한 패턴만 |
| 2 | 작은 PoC — 초기 누적 가속 |

## 출력 포맷 (Researcher 역할, 200단어 이내)

```
**요약**: Phase 5 journal {N}개 스캔, 임계 {T} 회 이상 패턴 {M}개 발견
**작성 candidate**: run-pytest, flutter-analyze (총 2건)
**스킵 (existing)**: build-flutter (1건)
**다음 단계**: .harness/recipes/{slug}.md 검토 후 cg recipe promote
```

## 금지

- candidate 를 검토 없이 곧장 promote → 자동 변형 안티패턴.
- 보안/billing 영역 명령을 ultra 검증 없이 승격 → `adaptive-quality.md` 위반.
- promote 후 SKILL.md 를 그대로 두기 → description 을 구체화하지 않으면
  `skill-loading.md` 의 Stage 1 판단이 어려워짐.

## 관련

- 글로벌 규칙: `~/.../claude-forge/rules/golden-principles.md §12 Surgical Changes`
- 비교 대상: Hermes Agent (DEFER, CHANGELOG `[Unreleased]` 참조)
- 트리거 위치: `cg-execution-loop` SKILL.md `## 학습 누적 (Recipe Promotion)`
- 승격 스킬 품질: `skill-authoring.md` (description=WHEN not WHAT · 긍정 슬롯 · 무가이드 압박테스트)
