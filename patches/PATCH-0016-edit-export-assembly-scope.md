# PATCH-0016

- Title: Edit-Pipeline Export Assembly — Approved Edit Export Scope (First Slice) (044)
- Status: Accepted
- Priority: Medium
- Trigger: Architect / Product Owner Decision (Edit Export Assembly Architect Decision + focused scope-policy review)
- Created: 2026-07-24
- Target Blueprint: `docs/044_EXPORT_PIPELINE.md`

---

## Status

Accepted. Product policy/clarification only; no schema, code, migration, tests, serializer, Artifact/format, or
Goal. Implementation becomes authorized only after this PATCH is reviewed and accepted.

## Trigger

A Blueprint-first investigation identified the next dependency-ordered frontier after the completed
Edit-Pipeline Export Application Foundation (044 §19 / PATCH-0015). The durable `ApprovedEditExportRepresentation`
is an atom of exported meaning (one per `ApprovedEditDecision`) with no downstream consumer: there is no
canonical way to express "the set of approved edits for a lecture," yet that set — not an isolated decision —
is what an external editor consumes. A subsequent Architect Decision resolved the next canonical stage, and a
focused review narrowed it to own existence-and-coherence only (not scope-selection policy). This PATCH
promotes that decision.

## Context

The canonical implemented path is `EditCandidate → EditReviewDecision → ApprovedEditDecision →
ApprovedEditExportRepresentation` (042 §9.1, 043 §7.4, 044 §19). The next export transition —
`ApprovedEditExportRepresentation → coherent Edit Export Assembly (Export Scope)` — is the sole in-scope
frontier. Aggregation precedes serialization (§8: approved results → Scope → Artifact); the subtitle branch
already proves this ordering (`ApprovedDocument → SRT Artifact → SRT Materialization`, §17 / PATCH-0007).
Concrete serializers/formats, Artifact creation, physical materialization, and delivery remain later,
separately-gated stages.

## Confirmed Architect Decision Basis (A-1…A-13)

Recorded as `044 §20`:

- **A-1 Existence/anchor:** the Edit Export Assembly canonically establishes the existence of a coherent Export
  Scope anchored to exactly one Source Timeline; it gathers the `ApprovedEditExportRepresentation` records
  belonging to that timeline into one coherent export unit; no cross-timeline/cross-media aggregation.
- **A-2 Purpose:** an external edit deliverable is inherently timeline-scoped and multi-representation; a single
  representation is a building block, not a deliverable; the Assembly makes the coherence and existence of the
  approved-edit set a first-class, provenance-bearing product fact before any format concern (§8 places Scope
  between approved results and Artifact).
- **A-3 Ownership boundary:** the Assembly owns the existence of a coherent Export Scope only; it does not own
  scope-selection (membership) policy; whether an Assembly denotes all current approved edits or an explicit
  subset is not fixed here (§3.7 all-or-subset duality; §15.3 completeness question) and remains deferred.
- **A-4 Upstream:** consumes `ApprovedEditExportRepresentation` records read-only; creates no new approved edit
  intent and never mutates/replaces/reinterprets/re-derives upstream; `ApprovedEditDecision` and
  `ApprovedEditExportRepresentation` stay authoritative for their own meaning; the Assembly is authoritative
  only for the coherent grouping.
- **A-5 Downstream:** serializer, Artifact, physical materialization, delivery, and Export Package are strictly
  downstream and undefined here; a future serializer consumes the Assembly and introduces its own
  format/version contract additively without changing the Assembly's meaning.
- **A-6 Semantics:** structured, canonical, format-neutral, provider/NLE-independent, non-executable; no
  serialization, file format, byte payload, edit/transformation command, output-timeline coordinate, or
  NLE/rendering instruction.
- **A-7 Coherence:** coherence is defined by a single Source Timeline; no mixing of timelines or media.
- **A-8 Determinism/replay:** construction is deterministic and replay-safe; same inputs produce the same
  Assembly; no wall-clock/random; reconstructable from preserved inputs.
- **A-9 Lineage/provenance:** provenance-bearing; the Assembly's Domain Result has multi-upstream lineage over
  the member representations' Domain Results, preserving lineage through `ApprovedEditDecision → … →
  SourceTimeline → SourceMedia`; denormalizes Source Timeline + execution provenance per durable-stage
  convention; duplicates no earlier-stage record.
- **A-10 Relationship to representation:** the representation is the atom (one per `ApprovedEditDecision`); the
  Assembly is the coherent set of atoms for one timeline; the Assembly references representations and does not
  copy or restate their owned snapshots as new authority.
- **A-11 Relationship to future Artifact:** the Assembly is the input a future serializer/Artifact will consume;
  aggregation precedes serialization; Artifact/materialization are later milestones whose form/existence is not
  defined here.
- **A-12 Status/Profile:** none — no status field, lifecycle, or state machine; no Export Profile or
  Configuration record.
- **A-13 Deferrals:** the full list (below), with no placeholder abstraction; a first implementation slice may
  realize only the "all current approved edits for the timeline" case as a Goal-level scope boundary, not a
  canonical policy, leaving user-selectable subsetting to later additive decisions.

## Affected Blueprint Files

- `docs/044_EXPORT_PIPELINE.md` — new normative §20 (sole owner); header amended to Blueprint 0.5 / Amended By
  PATCH-0016.

## Expected Normative Changes

- A single confirmed §20 "Edit-Pipeline Export Assembly — Approved Edit Export Scope (First Slice)" recording
  A-1…A-13 and the seventeen canonical invariants.
- §3.7 Export Scope is promoted from concept to a canonical Edit-Pipeline stage; §8's Scope-before-Artifact
  ordering is realized for the edit branch.
- §17 (Physical Materialization) remains Final-Subtitle-SRT-specific and is neither broadened nor reinterpreted.
- §19 (`ApprovedEditExportRepresentation`) is unchanged and remains the sole owner of the atom contract.
- No change to the document's overall Draft status (a Draft document may contain confirmed subsections).

## Non-Goals

Any implementation, SQL, schema, storage, database, migration, repository, execution/admission code,
interface/UI/API, serializer, provider adapter, or Goal; concrete export schemas, external file formats,
serialization grammar, JSON/EDL/FCPXML/NLE mapping; Artifact creation, physical file materialization,
path/filename/checksum policy, delivery/download/upload/URLs, Export Package; Export Profile/Configuration;
membership/scope-selection policy, subset selection, filtering, current-selection, supersession, reconciliation,
overlap handling, inter-decision ordering, partial-scope completeness UX, cross-representation equivalence;
executable edit semantics or output-timeline transformation; status/lifecycle. No modification to 042 §9.1/§9.2,
043 §7.4, 044 §19, the subtitle Approved Assembly / SRT Artifact / SRT Materialization contracts, or
PATCH-0007/0008/0013/0014/0015.

## Acceptance Criteria

- [x] One confirmed first-slice subsection exists in 044 (`§20`).
- [x] Edit Export Assembly is normatively established as durable/immutable/insert-only/identity-owning/
  provenance-bearing/replay-safe and format-neutral.
- [x] Anchored to exactly one Source Timeline; no cross-timeline/cross-media aggregation.
- [x] Assembly owns the existence of a coherent Export Scope only; scope-selection (membership) policy is NOT
  decided and is explicitly deferred.
- [x] Aggregation-precedes-serialization is normative; Artifact/serializer/materialization/delivery/Export
  Package remain downstream and undefined.
- [x] Upstream `ApprovedEditExportRepresentation` consumed read-only; authority boundaries preserved
  (Approved Edit Decision and representation stay authoritative for their own meaning).
- [x] Multi-upstream DomainResult lineage over the member representations confirmed; Source Timeline + execution
  provenance traceability confirmed.
- [x] No status/lifecycle; no Export Profile/Configuration; no executable semantics; no serializer/external
  format; no Artifact/physical file.
- [x] Deferrals exhaustive and explicit; no deferred placeholder introduced.
- [x] Completed 042/043, 044 §19, and subtitle §17 contracts unchanged.
- [x] No code, schema, migration, or test changes; `SQLITE_SCHEMA_VERSION` remains 28.

## Validation Performed

- Changes limited to `docs/044_EXPORT_PIPELINE.md` and this PATCH — no `src/`, `tests/`, schema, or migration.
- `SQLITE_SCHEMA_VERSION` unchanged at 28; 042 §9.1/§9.2, 043 §7.4, and 044 §19 untouched; §17 remains
  subtitle-specific.
- §20 is the sole normative owner; every A-1…A-13 decision and all deferrals are promoted; scope-selection
  policy is left deferred per the focused review; no deferred placeholder introduced.
- Whitespace check passes; the change is additive and preserves every previous Blueprint contract.

## Result

- Status: **Accepted**
- Changed Blueprint Files: `docs/044_EXPORT_PIPELINE.md` (new §20; header).
- Notes: Records the accepted Architect Decision (A-1…A-13) for the first Edit Export Assembly slice, promoting
  §3.7 Export Scope to a canonical Edit-Pipeline stage. Product policy/clarification only; no schema, code, or
  Goal; no implementation commit (implementation has not begun). The next step is implementation of the Edit
  Export Assembly Application Foundation, authorized only after this PATCH is reviewed and accepted.

## Related Documents

- `PATCH-0007-physical-materialization.md`
- `PATCH-0008-delivery-deferral.md`
- `PATCH-0015-edit-pipeline-export-application-foundation.md`
- `../docs/044_EXPORT_PIPELINE.md`
- `../docs/043_REVIEW_PIPELINE.md`
- `../docs/030_DATA_MODEL.md`
