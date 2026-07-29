---
name: matt-grill-with-docs
version: 1.0.0
description: "Matt Pocock의 grill-with-docs 패턴을 cg-harness 7-Phase에 맞춘 요구사항 인터뷰 + 유비쿼터스 언어 + ADR 기록 스킬"
last_updated: 2026-05-09
source: "Adapted from mattpocock/skills (MIT): skills/engineering/grill-with-docs"
---

# Matt Grill With Docs

## Purpose

Use this before writing a spec, PRD, issue, or implementation plan. The goal is to remove ambiguity, force domain language into shared docs, and preserve hard decisions as ADRs.

This is adapted for cg-harness. It writes into:

- `.harness/interview/{YYYY-MM-DD}-{slug}.md`
- `.harness/knowledge/glossary.md`
- `docs/adr/{NNNN}-{slug}.md` when a durable decision is made
- `.harness/spec/{YYYY-MM-DD}-{slug}.md` when the conversation is ready for Phase 2

## Hard Gate

Do not implement during this skill. The output is clarified intent, shared vocabulary, and decision records.

## Workflow

### 1. Load Existing Context

Read only the smallest useful set:

- `CLAUDE.md`
- `.harness/README.md`
- `.harness/knowledge/glossary.md`
- relevant `docs/specs/**`
- relevant `docs/adr/**`
- latest `.harness/journal/**`

Summarize what the project already calls this domain. Prefer existing terms over inventing new names.

### 2. Grill The Request

Ask focused questions until these are clear:

- User outcome: who benefits, what changes for them?
- Scope boundary: what is explicitly out of scope?
- State transitions and edge cases
- Data ownership and source of truth
- Compatibility or migration constraints
- Verification evidence expected at the end

Ask one question at a time when interacting with the user. If running autonomously, list assumptions and mark each as `accepted`, `rejected`, or `needs-user`.

### 3. Build Shared Language

Update `.harness/knowledge/glossary.md` when the discussion reveals:

- a domain term with a precise meaning
- a confusing synonym that should be avoided
- a term that should appear in code names, tests, routes, or docs

Use this shape:

```markdown
## {Term}

- Meaning: ...
- Avoid saying: ...
- Code naming: ...
- Related specs: ...
```

### 4. Capture Durable Decisions

Create an ADR when a decision would be expensive to rediscover later.

Use:

```markdown
# ADR {NNNN}: {Decision}

## Status

Accepted

## Context

## Decision

## Consequences

## Alternatives Considered
```

Do not create ADRs for transient implementation details.

### 5. Produce Interview Output

Write `.harness/interview/{YYYY-MM-DD}-{slug}.md` with:

- request summary
- clarified requirements
- accepted assumptions
- rejected assumptions
- open questions
- glossary updates
- ADRs created or touched
- recommended next phase

## Exit Criteria

You may leave this skill when:

- no material ambiguity remains, or open questions are explicitly listed
- glossary terms are updated or confirmed unchanged
- ADR-worthy decisions are captured
- the next action is either Phase 2 spec or a clearly bounded spike

