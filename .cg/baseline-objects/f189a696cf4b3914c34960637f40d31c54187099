---
origin_model: claude-fable-5
review_by: 2026-10-26
---

# Reasoning Budget Policy

Use a **reasoning sandwich**: spend more reasoning on planning and verification,
and keep implementation at the lowest level that can still execute the plan.

## Default Allocation

| Phase | Reasoning | Why |
|---|---|---|
| planning / discovery | high | Understand the task, environment, constraints, and verification strategy |
| implementation | medium | Execute the plan without burning tokens on every small edit |
| verification / repair | high | Compare output against the original spec, not against the written code |

## Rules

- Do not use maximum reasoning for every subtask. It wastes time and tokens.
- Raise reasoning for ambiguous specs, security, migrations, billing, and data loss.
- Lower reasoning for mechanical edits after the plan is locked.
- Verification must re-read the original task/spec and full command output.

## Multi-Agent Use

When using subagents, use stronger reasoning for planner/reviewer agents and
lighter reasoning for bounded implementation workers. Escalate only when a
worker hits repeated failures or uncovers a design conflict.
