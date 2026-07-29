---
description: Phase 5 journal 의 반복 패턴을 recipe candidate 로 제안. cg-recipe-promotion 스킬 호출.
---

# /recipe-propose

## 용도

`.harness/journal/` 에 누적된 명령 중 **3회 이상 반복된 것**을 자동 감지해
`.harness/recipes/{slug}.md` 로 candidate 작성.

## 실행

```bash
# 기본 임계 3회
cg recipe propose

# 임계 변경
cg recipe propose --threshold 5

# JSON (CI/스크립트)
cg recipe propose --json
```

## 검토 → 승격

```bash
# 1. candidate 검토
$EDITOR .harness/recipes/{slug}.md

# 2. 가치 있으면 승격
cg recipe promote {slug}

# 3. SKILL.md 보강 (description 구체화)
$EDITOR .claude/skills/{slug}/SKILL.md
```

## 호출 시점

- Phase 5 종료 후, `cg-evaluation` 통과 직후.
- Journal 엔트리 10+ 새로 누적된 시점.
- 사용자가 "반복 작업이 많아진 것 같다" 고 느낄 때.

## 관련 스킬

`.claude/skills/cg-recipe-promotion/SKILL.md` — 상세 가이드.

## 금지

- candidate 검토 생략 → 곧장 promote 금지 (사람 게이트 보존).
- 보안/billing 명령을 ultra 모드 검증 없이 승격 → `adaptive-quality.md` 위반.
