---
name: matt-zoom-out
version: 1.0.0
description: "Matt Pocock의 zoom-out 패턴을 cg-harness에 맞춘 시스템 맥락 설명 스킬"
last_updated: 2026-05-09
source: "Adapted from mattpocock/skills (MIT): skills/engineering/zoom-out"
---

# Matt Zoom Out

## Purpose

Use this when a file, module, bug, or feature feels locally understandable but system context is missing. The output is a concise explanation of how the current area fits into the larger architecture.

## Inputs To Read

Prefer this order:

1. The file or module under discussion
2. Nearby tests
3. `CLAUDE.md`
4. relevant `docs/specs/**`
5. `.harness/knowledge/glossary.md`
6. relevant ADRs

Do not scan the whole repository unless the local context is insufficient.

## Output Shape

```markdown
## Zoomed Out View

### What This Area Is For

### Upstream Callers

### Downstream Dependencies

### Domain Terms In Play

### Invariants To Preserve

### Likely Change Boundary

### Verification To Trust
```

## Rules

- Explain the system, do not edit code.
- Prefer domain vocabulary from `.harness/knowledge/glossary.md`.
- Call out missing docs or stale docs as findings, not silent assumptions.
- If the module boundary looks wrong, propose an architecture follow-up instead of mixing refactor work into the current task.

