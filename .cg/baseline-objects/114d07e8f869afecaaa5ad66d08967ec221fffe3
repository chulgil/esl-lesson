---
name: cg-trace-analyzer
description: Analyze local harness traces from `.harness/journal/` and `.harness/status/` to find repeated agent failure modes and propose targeted changes to prompts, rules, hooks, skills, or mechanical gates.
---

# Trace Analyzer Skill

This skill ports the LangChain harness-engineering improvement loop to local
cg-harness projects. It treats `.harness/journal/`, `.harness/status/`, failed
mechanical gates, and reviewer reports as local traces.

## Goal

Find repeated agent failure modes and propose **targeted changes** to the
harness. Do not blindly add rules. Generalization matters more than fixing a
single incident.

## Inputs

Read, in this order:

1. `.harness/status/drift.json`
2. `.harness/status/loop-detection.json`
3. `.harness/journal/*.md` from the requested period
4. `.harness/spec/*.md` for the affected feature
5. Recent mechanical gate output if the user provides it

## Analysis Flow

1. Fetch local traces from `.harness/journal` and `.harness/status`.
2. Group failures by mode:
   - missing verification
   - not following task instructions
   - repeated edits to the same file
   - weak environment discovery
   - timeout or poor time budgeting
   - insufficient tests or happy-path-only tests
3. Spawn parallel error analysis agents when there are 2+ independent failure
   groups.
4. Synthesize findings into a short table.
5. Propose targeted harness changes:
   - prompt/rule change
   - hook or middleware change
   - skill addition
   - mechanical gate change
   - no change, if the trace is one-off or task-specific

## Output Format

```markdown
## Trace Analyzer Report

| Failure mode | Evidence | Frequency | Proposed harness change | Risk |
|---|---|---:|---|---|

## Recommended Next Experiment

One narrowly scoped change to try next, plus the verification command.
```

## Guardrails

- Do not overfit a rule to one task.
- Prefer deterministic hooks for repeated mechanical failures.
- Prefer skills for repeatable reasoning workflows.
- Prefer rules for stable project policy.
- If the fix is just "try again", reject it and ask what signal the retry adds.
