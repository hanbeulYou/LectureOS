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

Independent review exists only to detect verified critical architectural and
correctness defects. It is not a general style, naming, formatting, documentation
wording, refactoring, optional abstraction, future-design, or architecture
brainstorming review.

Only the following may block implementation:

- Blueprint violations
- architectural responsibility inversion
- lifecycle or Human Authority violations
- transaction atomicity or migration correctness defects
- rollback failures, data corruption, or data loss
- identity or provenance corruption
- public contract violations
- security or privacy defects
- missing tests for realistic critical failure paths

Everything else is non-blocking.

The default required review policy is:

- exactly one bounded review
- default budget of 6 turns
- staged diff only
- directly relevant Blueprint and contracts only

Run an additional review only to verify an actual critical finding or when the
reviewer requests clarification of a critical issue. Never rerun merely to obtain
a `PASS` line.

An explicit verdict is preferred but not required. If no verified critical issue
was identified, record:

```text
Inconclusive — no critical findings identified
```

and continue. Reviewer silence, formatting, verbosity, or omission of a verdict
line never blocks implementation. A review blocks only when a verified critical
defect remains unresolved.

Preferred review output:

```text
Verdict:
PASS | CRITICAL_CHANGES_REQUIRED | BLOCKED

Critical Issues:
- ...

Critical Missing Tests:
- ...

Blueprint Conflict:
Yes/No

Review Basis:
- ...
```

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
5. For required review, have no unresolved verified critical defect.
6. Produce a clean Working Tree.
7. Create exactly one logical commit.

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

Future Goal documents inherit this global review policy. A Goal should define a
stronger or different independent-review process only when its milestone has a
documented reason requiring stronger review. Requirements equivalent to “review
must explicitly PASS” are not inherited; the default gate is “review identified
no unresolved verified critical defect.”

## Goal Self-Maintenance

After every successful slice:

- Mark milestone complete.
- Move it to Completed Capabilities.
- Remove it from Remaining Milestones.
- Update repository capability summary.
- Preserve history.
