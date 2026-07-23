# PATCH-0015

- Title: Edit-Pipeline Export Application Foundation — Approved Edit Decision Export Representation (First Slice) (044)
- Status: Completed
- Priority: Medium
- Trigger: Architect / Product Owner Decision (First Edit-Pipeline Export Foundation investigation + Architect Decision)
- Created: 2026-07-24
- Target Blueprint: `docs/044_EXPORT_PIPELINE.md`

---

## Status

Completed. Product policy/clarification only; no schema, code, migration, tests, Artifact/format, or Goal.
Implementation becomes authorized only after this PATCH is reviewed and accepted.

## Trigger

A Blueprint-first investigation identified the next dependency-ordered frontier after the completed
Edit-Pipeline Review Application Foundation (043 §7.4). The durable `ApprovedEditDecision` has no downstream
consumer: the Subtitle export branch of 044 is implemented (Approved Subtitle Assembly → SRT Artifact → SRT
Physical Materialization, §17 / PATCH-0007), but the Edit-Pipeline export branch is entirely absent (no
representation record, repository, service, table, serializer, or acceptance placeholder). 044 §5.2/§7.2
describe Approved Edit Decision export at the meaning level only, and the durable record contract, scope,
and minimum payload were Draft / §15.3 Requires-Validation / §15.4 Deferred. The Architect Decision resolved
the minimum contract; this PATCH promotes it.

## Context

The canonical implemented path is `EditCandidate → EditReviewDecision → ApprovedEditDecision` (042 §9.1,
043 §7.4). The first Edit-Pipeline export transition — `ApprovedEditDecision → canonical Edit-Pipeline Export
Representation` — is the sole in-scope frontier; concrete serializers/formats, Artifact creation, physical
materialization, and delivery are later, separately-gated stages.

## Confirmed Architect Decision Basis (D-1…D-15)

Recorded as `044 §19`:

- **D-1 Anchor/cardinality:** each `ApprovedEditExportRepresentation` anchors to exactly one durable
  `ApprovedEditDecision`; one explicit approved-decision identity per admission; no Export Scope aggregate,
  multi-decision request, ordering, all-current/current-selection, or grouped plan; grouping deferred and
  additive.
- **D-2 Canonical record:** `ApprovedEditExportRepresentation` — durable, immutable, insert-only,
  identity-owning, provenance-bearing, replay-safe, canonical; minimum categories = own identity, own
  DomainResult identity, one `ApprovedEditDecision` reference, direct `EditReviewDecision` and `EditCandidate`
  references, Source Media/Timeline identities, execution provenance, per-admission ordinal, owned snapshot.
- **D-3 Owned snapshot:** owns approved Source Timeline range, approved Candidate Type/label, approved
  rationale, approving decision kind (accept|modify), human actor reference; references the Approved Edit
  Decision / Review Decision / Candidate; does not duplicate Finding/Input/transcript/source content.
- **D-4 Authority:** the `ApprovedEditDecision` stays the sole authority for approved edit intent; the
  representation is authoritative only for the exported form; it copies faithfully, creates no new decision,
  and never mutates/replaces/reinterprets upstream.
- **D-5 Semantics:** structured, canonical, format-neutral, provider/NLE-independent, non-executable; no
  delete/cut/keep/edit/transformation command, output-timeline coordinate, NLE/rendering instruction, or
  serialized payload; a Candidate Type/label is descriptive, never an operation.
- **D-6 Accept/Modify:** exports the final approved snapshot (Accept == accepted values; Modify == approved
  values from the `ApprovedEditDecision`, original Candidate values lineage-only, no delta/comparison); the
  approving kind stays traceable as accept or modify.
- **D-7 Reject exclusion:** only `ApprovedEditDecision` records are inputs; Reject produces no representation;
  no rejection/negative export.
- **D-8/D-9/D-10 Admission:** Application-owned, running-execution-gated, deterministic, replay-safe,
  caller-identity-owned, interface/provider-independent, atomic all-or-nothing; load Approved Edit Decision
  read-only → validate lineage → verify execution → derive snapshot → construct record + DomainResult →
  persist atomically; identity collision rejects with no duplicate/partial write; no external provider; no
  content dedup/update/overwrite/compensating write.
- **D-11 Lineage:** single-direct-upstream DomainResult = the Approved Edit Decision's DomainResult; the
  representation directly stores the Approved Edit Decision / Review Decision / Candidate identities,
  denormalizes Source Media/Timeline + execution provenance, and duplicates no earlier-stage record.
- **D-12 Status:** none — no status field, no lifecycle, no state machine; one immutable fact.
- **D-13 Artifact/format boundary:** a canonical domain record, not an Artifact/Artifact-Record/physical
  file/materialization outcome/path/URL; ends at the durable structured representation; no JSON/CSV/XML/EDL/
  FCPXML/NLE/textual serialization/bytes/MIME/extension/checksum/filename/path/URL.
- **D-14 Export Profile:** none — no profile identity/persistence/variant/destination/serializer/NLE settings,
  user-selectable configuration, or implicit format/version marker; one fixed format-neutral meaning.
- **D-15 Deferrals:** the full list (below), with no placeholder abstraction/field/table/enum/protocol/
  interface for any of them.

## Affected Blueprint Files

- `docs/044_EXPORT_PIPELINE.md` — new normative §19 (sole owner); header amended to Blueprint 0.4 / Amended By
  PATCH-0015.
- `docs/030_DATA_MODEL.md` — one minimal cross-reference near §11.1 (Approved Edit Decision).

## Expected Normative Changes

- A single confirmed §19 "Edit-Pipeline Export Application Foundation — Approved Edit Decision Export
  Representation (First Slice)" recording D-1…D-15 and the twenty canonical invariants.
- §17 (Physical Materialization) remains Final-Subtitle-SRT-specific and is neither broadened nor reinterpreted.
- No change to the document's overall Draft status (a Draft document may contain a confirmed subsection).

## Non-Goals

Any implementation, SQL, schema, migration, repository, execution/admission code, interface/UI/API, serializer,
provider adapter, or Goal; concrete export schemas, external file formats, serialization grammar, JSON/EDL/
FCPXML/NLE mapping; Artifact creation, physical file materialization, path/filename/checksum policy, delivery/
download/upload/URLs; Export Scope/Profile/Configuration; current-selection/supersession/reconciliation;
executable edit semantics or output-timeline transformation; status/lifecycle. No modification to 042 §9.1/§9.2,
043 §7.4, the subtitle Approved Assembly / SRT Artifact / SRT Materialization contracts, or PATCH-0007/0008/
0013/0014.

## Acceptance Criteria

- [x] One confirmed first-slice subsection exists in 044 (`§19`).
- [x] `ApprovedEditExportRepresentation` is normatively established (durable/immutable/insert-only/identity-
  owning/provenance-bearing/replay-safe).
- [x] Exactly-one Approved Edit Decision anchoring confirmed; no multi-decision scope; no current-selection.
- [x] Owned exported-meaning snapshot (range, type/label, rationale, approving kind, actor) confirmed.
- [x] Direct Review Decision and Candidate traceability confirmed; Source Media/Timeline + execution
  provenance confirmed.
- [x] `ApprovedEditDecision` authority remains explicit; Reject produces no representation.
- [x] No Export Profile; no status/lifecycle; no executable semantics; no serializer/external format; no
  Artifact/physical file.
- [x] Application-owned running-execution admission, caller-owned identities, replay, and atomic all-or-nothing
  persistence confirmed; single-direct-upstream DomainResult confirmed.
- [x] Deferrals exhaustive and explicit; no deferred placeholder introduced.
- [x] Completed 042/043 and subtitle §17 contracts unchanged; cross-references minimal and non-duplicative.
- [x] No code, schema, migration, or test changes; `SQLITE_SCHEMA_VERSION` remains 27.

## Validation Performed

- Changes limited to `docs/044`, `docs/030`, and this PATCH — no `src/`, `tests/`, schema, or migration.
- `SQLITE_SCHEMA_VERSION` unchanged at 27; 042 §9.1/§9.2 and 043 §7.4 untouched; §17 remains subtitle-specific.
- §19 is the sole normative owner; the 030 note is a non-duplicative cross-reference; every D-1…D-15 decision
  and all deferrals are promoted; no deferred placeholder introduced.
- Whitespace check passes; working tree clean after commit.

## Result

- Status: **Completed**
- Changed Blueprint Files: `docs/044_EXPORT_PIPELINE.md` (new §19; header). Cross-reference:
  `docs/030_DATA_MODEL.md §11.1`.
- Notes: Records the Product Owner's approved D-1…D-15 decision for the first Edit-Pipeline Export slice.
  Product policy/clarification only; no schema, code, or Goal; no implementation commit (implementation has not
  begun). The next step is implementation of the Edit-Pipeline Export Application Foundation, authorized only
  after this PATCH is reviewed and accepted.

## Related Documents

- `PATCH-0007-physical-materialization.md`
- `PATCH-0008-delivery-deferral.md`
- `PATCH-0014-edit-pipeline-review-application-foundation.md`
- `../docs/044_EXPORT_PIPELINE.md`
- `../docs/030_DATA_MODEL.md`
- `../docs/043_REVIEW_PIPELINE.md`
