---
description: Phase 5 journal 의 "결정:" 블록에서 git trailer 미기록 의사결정을 candidate 로 제안. cg-lore-proposal 스킬 호출.
---

# /lore-propose

## 용도

`.harness/journal/` 에 누적된 **"결정:" 블록** 중 git trailer 로 아직
기록되지 않은 결정을 자동 감지해 `.harness/lore/{slug}.md` 로 candidate 작성.

## 실행

```bash
# 기본 — git log Lore-* trailer 와 비교 후 미기록 결정만
cg lore propose

# JSON (CI/스크립트)
cg lore propose --json
```

## 검토 → trailer 커밋 → 승격

```bash
# 1. candidate 검토
$EDITOR .harness/lore/{slug}.md

# 2. 적합한 커밋 메시지에 trailer 추가 (사용자가 직접)
git commit --amend
# 메시지 본문 마지막 빈 줄 뒤에:
#   Lore-directive: <결정 한 줄>
#   Lore-rejected: <대안> — 이유

# 3. trailer 가 커밋되면 archive 로 이동
cg lore promote {slug}
```

## 호출 시점

- Phase 5 종료 후, journal 에 "결정:" 블록이 작성된 직후.
- 아키텍처 선택 / 라이브러리 채택 / 범위 제한 결정 발생 시.
- 90일 이상 된 directive 재검토 후 필요 시 새 결정으로 재기록.

## trailer 포맷 (필수)

```
Lore-directive: <결정 한 줄>          # 채택된 결정
Lore-constraint: <제약 한 줄>          # 의식적 범위 제한
Lore-rejected: <거절된 대안> — 이유    # 배제된 옵션 (이유 필수)
```

`Lore-why`, `Lore-because` 같은 임의 키 금지.

## 관련 스킬

`.claude/skills/cg-lore-proposal/SKILL.md` — 상세 가이드.

## 금지

- `cg` 가 자동으로 trailer 를 커밋 → 사람 게이트 위반.
- 단순 작업 / docs 변경을 trailer 로 승격 → trailer 잡음.
- 거절(rejected) 에 이유 누락 → `lore-commit.md` 위반.
