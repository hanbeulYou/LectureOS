# AGENTS.md

# LectureOS Agent Operating Manual

## Project Principles

- Blueprint is authoritative.
- Domain defines product meaning.
- Application computes lifecycle and business decisions.
- Persistence serializes approved Domain state.
- Composition Root assembles concrete implementations.
- Schema follows Domain; never the reverse.
- Preserve approved behavior rather than inventing new behavior.

## Architect Checklist

Before every implementation slice verify:

- No approved Domain contract changes.
- No released schema meaning changes.
- No lifecycle authority changes.
- No responsibility shifts across Domain/Application/Persistence.
- No new identity semantics.
- No new migration requirement.
- No Blueprint contradiction.

If every answer is **No**, continue automatically.
Otherwise stop and escalate.

## Responsibility Boundaries

Domain:
- Models
- Invariants
- Identity semantics

Application:
- Lifecycle
- Eligibility
- Final snapshot computation
- Command orchestration

Persistence:
- Serialization
- Deserialization
- Transactions
- Rollback
- Feature gates
- Error mapping

Composition Root:
- Concrete dependency construction only.

## Review Workflow

Follow implementation/050_IMPLEMENTATION_WORKFLOW.md.

Allowed classifications:

- Required — Executed
- Required — Blocked
- Optional — Executed
- Optional — Skipped

Never report PASS for skipped reviews.

## Commit Policy

Every implementation slice must:

1. Pass focused tests.
2. Pass regressions.
3. Pass complete suite.
4. Pass compile/static checks.
5. Produce a clean Working Tree.
6. Create exactly one logical commit.

## Goal Execution

When a Goal document is supplied:

1. Read AGENTS.md.
2. Read the Goal.
3. Determine current repository capability.
4. Resume from the first unfinished milestone.
5. Keep the Goal synchronized.
6. Continue automatically.
7. Stop only on documented Stop Conditions.
8. Produce one consolidated report when complete.

## Goal Self-Maintenance

After every successful slice:

- Mark milestone complete.
- Move it to Completed Capabilities.
- Remove it from Remaining Milestones.
- Update repository capability summary.
- Preserve history.
