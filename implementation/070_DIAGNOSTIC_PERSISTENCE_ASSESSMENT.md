# Diagnostic Persistence Assessment

- Status: Completed Assessment
- Assessed on: 2026-07-19
- Decision: **Diagnostic Persistence: DEFERRED**
- Blueprint Baseline: v1

## Summary

LectureOS currently has a minimal immutable `Diagnostic` Domain record and typed
`DiagnosticId`, but no production command creates canonical Diagnostic records
and no Application path resolves a Diagnostic identity. Existing durable records
correctly preserve ordered opaque Diagnostic references without claiming
ownership of canonical Diagnostic content.

Canonical Diagnostic persistence is not required by the completed terminal
Failure, Retry, or Result durability milestones. Adding it now would require
settling unresolved retention and product-consumer semantics and releasing a new
schema version without an executable consumer. The safe decision is continued
deferral.

## Current Contract and Model

The current execution model defines exactly:

```python
@dataclass(frozen=True, slots=True)
class Diagnostic:
    identity: DiagnosticId
    summary: str
```

The constructor rejects a blank or whitespace-only summary. `DiagnosticId` is
an opaque typed identity. The frozen record shape indicates immutable value
semantics, while the generic `DiagnosticRepository` protocol exposes `get` and
`save` mechanically through the shared repository contract.

Those facts do not establish a complete durable-record contract. In particular,
the approved Storage Model still lists this question under Requires Validation:

```text
Diagnostic은 장기 provenance인가, 운영 정보인가?
```

No approved contract currently defines retention, correction or supersession,
producer authority, review linkage ownership, or whether the two-field record is
the complete long-term diagnostic representation.

## Existing Durable Representation

Schema v4 has no canonical Diagnostic parent table. It intentionally stores only
ordered opaque references in owned child structures:

- `unit_execution_diagnostics`
- `failure_diagnostics`

The SQLite UnitExecution and Failure repositories preserve these tuples in exact
ordinal order. No external foreign key requires a canonical Diagnostic row.
Transcript validation, Subtitle validation, transcript records, subtitle records,
and Review records likewise carry `DiagnosticId` references in their Domain
models without owning or resolving the referenced record.

This means:

```text
DiagnosticId reference durability
!=
canonical Diagnostic record durability
```

The current representation is internally consistent with the approved v4
external-reference policy and must not be reinterpreted as embedded Diagnostic
storage.

## Producers and Consumers

Repository inspection found no production producer that constructs and saves a
canonical `Diagnostic`. There is also no production Application service,
query boundary, review workflow, export path, UI, CLI, or real-media path that
loads a Diagnostic through `DiagnosticRepository`.

Current consumers use identity references only:

- Failure records preserve ordered diagnostic references.
- UnitExecution snapshots preserve ordered diagnostic references.
- Transcript and Subtitle validation records can reference diagnostics.
- Review records can reference diagnostics.

These are relationship placeholders, not canonical-record resolution paths.
The Blueprint describes a logical Diagnostic Manager responsibility, but
explicitly does not make it a deployment unit or define a persistence API.

## Retry and Recovery Dependency

Durable Retry authority does not consult Diagnostic records. Its current rule is:

```text
FAILED UnitExecution
+ at least one Failure reference
+ at least one resolved retryable Failure
-> Retry allowed
```

The completed Failure repository and Retry wiring use canonical Failure data.
They neither resolve Diagnostic IDs nor inspect diagnostic summaries. Therefore
Diagnostic persistence is not a prerequisite for terminal Failure persistence,
Retry authority, recovery state preservation, or terminal Result persistence.

## Review, Export, and User-Visible Diagnostics

Blueprint documents require failures, validation issues, uncertainty, and
diagnostics to remain visible rather than becoming empty success. They do not yet
define a concrete V1 read model or artifact for presenting canonical Diagnostic
records. Current Review and export implementations do not resolve Diagnostic IDs.

Physical logs are not Domain Diagnostics. Runtime logs, provider responses,
exception traces, and temporary measurements must not be stored as canonical
Diagnostic records merely because a future operator may find them useful. A
future design must explicitly define the translation and authority boundary.

## Persistence Necessity Decision

**Diagnostic Persistence: DEFERRED**

Deferral is safe because:

- all currently authoritative transaction commands are durable without it;
- ordered Diagnostic IDs already survive in records that reference them;
- no current Application consumer loses executable behavior after restart;
- no Retry or recovery decision depends on Diagnostic content;
- schema v4 was deliberately released without a canonical Diagnostic table;
- implementing now would create unused schema and repository infrastructure.

Deferral must not be interpreted as permission to drop, reorder, or silently
resolve existing Diagnostic references. Missing canonical resolution remains an
explicit unavailable capability.

## Future Preconditions

Before proposing canonical Diagnostic persistence, a concrete product milestone
must establish at least:

1. the producer and authority that creates a Diagnostic;
2. the consumer that resolves it and the user-visible or operational action;
3. whether `identity + summary` is the complete authoritative record;
4. immutable insert-only, revision, or retention semantics;
5. provenance and linkage required beyond existing opaque references;
6. the boundary between Domain Diagnostic, Validation Finding, and physical log;
7. schema-version and migration policy, likely a separately reviewed v5;
8. repository and command transaction boundaries.

These are future Architect decisions. A Blueprint Clarification or PATCH is only
needed if the proposed consumer reveals two plausible product meanings or needs
a new canonical concept. Missing SQLite mechanics alone would not require a
Blueprint change.

## Risks

Continuing deferral means Diagnostic summaries cannot currently be reconstructed
from SQLite after restart, and a future UI cannot resolve the stored opaque IDs.
That is an acknowledged unavailable capability, not a partial durability defect
in the completed commands.

Implementing prematurely carries the larger immediate risk: freezing an
insufficient record shape, retention policy, or Diagnostic/Validation-Finding
boundary in a released schema without a consumer-driven contract.

## Recommendation and Next Candidate

Do not implement `SQLiteDiagnosticRepository`, a Diagnostic schema table, or a
Diagnostic transaction port now. Select the next product milestone first. If it
requires resolved diagnostics, perform a focused Diagnostic contract and schema
assessment using that consumer as evidence.

There is no further implementation candidate inside the current Durability Goal.
The Goal is complete after this assessment, validation, documentation sync, and
commit.

```text
Requires Architect Decision: No
Requires Blueprint Clarification: No
Requires Blueprint PATCH: No
```

## Reassessment — 2026-08-09 (`PATCH-0045`)

Nothing above is deleted or rewritten. This note records the outcome of the
reopening condition stated in *Recommendation and Next Candidate*.

**The reopening condition is met.** `PATCH-0045` (Local ASR Transcript Quality
Diagnostic Boundary, `docs/040` §15) is an executable consumer that needs ASR
quality information, so the focused assessment this document asked for was
performed with that consumer as evidence.

**The conclusion splits in two.** The original question — "should Diagnostics be
persisted?" — turned out to contain two different questions:

| | outcome | reason |
|---|---|---|
| **Provider evidence persistence** | **Justified — required** | Obtainable only during provider execution, not recomputable afterwards, required to reproduce any Quality Diagnostic, and already contracted as `original_content` provider evidence by `docs/040` §14 A-4. |
| **Derived Diagnostic persistence** | **Still deferred** | Recomputable from immutable evidence + Raw Transcript + a versioned algorithm; storing it creates stale-diagnostic risk; no consumer yet requires a canonical Diagnostic row. |

The consumer needs the **evidence**, not a Diagnostic record. This document's own
reasoning — do not freeze a record shape, retention policy, or
Diagnostic/Validation-Finding boundary without a consumer-driven contract — is
therefore unchanged and still governs the derived side.

**Meeting the reopening condition does not by itself introduce a canonical
Diagnostic record.** The decision in the header (`Diagnostic Persistence:
DEFERRED`) stands for derived Diagnostics. `PATCH-0045` adds no table, no column,
no `SQLiteDiagnosticRepository`, and no Diagnostic transaction port.
