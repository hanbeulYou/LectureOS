# LectureOS Codex Goal — <Milestone Name>

> **Inheritance notice.** This document is governed by `AGENTS.md`, which is
> auto-loaded via `CLAUDE.md`. Do **not** restate durable operating policy here.
> The autonomous slice loop, Stop Conditions, additive-migration compatibility,
> Blueprint Drift Check, the review policy, the validation checklist, Goal
> Self-Maintenance mechanics, and the base Consolidated Completion Report skeleton
> are **inherited** from `AGENTS.md → "Milestone Execution Protocol"`. A Goal
> specifies only what is **unique to this milestone**.
>
> ```text
> AGENTS.md          → repository-wide durable operating policy (inherited)
> Goal Template      → milestone selection and implementation details only
> Historical Goal    → immutable audit record (never edited)
> ```
>
> Author every new milestone Goal from this template. Never clone a completed
> Goal. See `docs/goals/README.md` for the authoring workflow.

## 1. Mission & Lifecycle Position

<What this milestone builds and why. State the lifecycle position, e.g.
`… → Previous Stage → THIS MILESTONE → Next Stage → …`.>

## 2. Baseline

<Start `HEAD`, branch, and `SQLITE_SCHEMA_VERSION` at Goal start. The authority
order (Blueprint → active PATCH → approved Goals → Domain/Application contracts →
implementation) is inherited from `AGENTS.md`; do not re-list it.>

## 3. Bounded Assessment & Architect Decision

<Milestone-specific findings. The bounded Architect Decision for this milestone.
Record the Architect Checklist **result** only (e.g. "all No — additive"); do not
re-list the checklist items owned by `AGENTS.md`.>

## 4. Scope

- **Included:** <the capabilities this milestone delivers>
- **Excluded:** <what is explicitly out of scope for this milestone>

## 5. Canonical Model

<New identity type(s); new enum(s) as value classifications; the aggregate and its
fields; the deterministic evaluation/derivation rules; the Application-owned
identity plan.>

## 6. Persistence

<New table(s); new `DomainResultReference` kind; new additive schema version;
upstream linkage. The additive-migration and migration-compatibility policy is
inherited from `AGENTS.md`; state only what is new.>

## 7. Slice Sequence

<One bounded logical slice per commit. For each slice: a short description, the
exact commit message, and the review classification
(Required — Executed / Optional — Skipped / …).>

## 8. Milestone-Specific Verify

<Only the invariants unique to this milestone. The generic validation
(focused tests, full suite, compileall, tabnanny, `git diff --check`, staged-diff
review) is inherited from `AGENTS.md` and `implementation/050_IMPLEMENTATION_WORKFLOW.md`.>

## 9. Status (living)

### Completed Capabilities

```text
None yet
```

### Remaining Milestones

```text
Slice 1 — …
Slice 2 — …
```

### Immediate Next Slice

```text
Slice 1 — …
```

## 10. Completion Report — Milestone Additions

<Only the report sections beyond the base skeleton owned by `AGENTS.md →
"Consolidated Completion Report"` (for example a Canonical Model section,
domain-specific Rules, Validation Linkage, Idempotency Verification). The base
sections and the `Requires Architect Decision / Blueprint Clarification /
Blueprint PATCH` trailer are inherited; do not restate them.>

## 11. Milestone Overrides (optional)

<Omit unless this milestone deliberately deviates from an inherited durable
default (for example, requiring a stronger explicit review than the default
critical-only gate). State each override explicitly and why. Do **not** repeat
inherited policy here — record only the deviation.>
