# LectureOS Goal Authoring Workflow

This directory holds milestone **Goal** documents. A Goal selects one product
milestone and records its milestone-specific implementation details. It does not
define durable operating policy.

## Document hierarchy

```text
AGENTS.md          → repository-wide durable operating policy (auto-loaded via CLAUDE.md)
docs/goals/_TEMPLATE.md → the canonical form for a new Goal (milestone-specific only)
docs/goals/*.md    → completed Goal documents = immutable audit records
```

## Rules

- **Always create a new milestone Goal from `docs/goals/_TEMPLATE.md`.**
- **Never clone an existing completed Goal.** Cloning re-copies inherited policy
  and reintroduces the duplication this workflow removes.
- **Completed Goal documents are historical audit records and must remain
  unchanged.** They record what governed each milestone at the time; do not edit,
  trim, or "modernize" them.
- **Durable operating policy is inherited from `AGENTS.md`.** The autonomous slice
  loop, Stop Conditions, additive-migration compatibility, Blueprint Drift Check,
  review policy, validation checklist, Goal Self-Maintenance mechanics, and the
  base Completion Report skeleton live in `AGENTS.md → "Milestone Execution
  Protocol"` and are auto-loaded — a Goal does not restate them.
- **A Goal document contains only milestone-specific content:** mission and
  lifecycle position, bounded assessment and the Architect Decision, scope,
  canonical model, persistence specifics, slice sequence, milestone-specific
  verification, living status, and any report additions. Deliberate deviations
  from an inherited default go under **"Milestone Overrides"** — never as a
  restatement of the inherited policy.

## Authority

Product meaning is owned by the Blueprint (`docs/`, `patches/`). Detailed
implementation workflow is owned by
`implementation/050_IMPLEMENTATION_WORKFLOW.md`. Durable operating policy is owned
by `AGENTS.md`. A Goal inherits all of the above and adds only the milestone.
