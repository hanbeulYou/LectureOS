# PATCH-0017

- Title: Edit-Pipeline Export Artifact — Canonical Approved Edit Decision Representation (First Slice) (044)
- Status: Accepted
- Priority: Medium
- Trigger: Architect / Product Owner Decision (First Edit Export Artifact Representation Architect Decision)
- Created: 2026-07-24
- Target Blueprint: `docs/044_EXPORT_PIPELINE.md`

---

## Status

Accepted. Product policy/clarification only; no schema, code, migration, tests, serializer, concrete format, or
Goal. Implementation becomes authorized only after this PATCH is reviewed and accepted.

## Trigger

A Blueprint-first investigation identified the first Edit Export Artifact as the next dependency-ordered
frontier after the completed Edit Export Assembly (044 §20 / PATCH-0016), but concluded the Artifact could not
yet be defined because its Product meaning depended on an unresolved decision: 044 defines the Artifact only
abstractly (§3.3, §7.2 — "a human can read or an external system can process," without choosing which),
Representation Failure is defined relative to "the selected representation" (§11.4) that does not yet exist, the
concrete export schema and file format are deferred (§15.4) and specific syntax is a non-goal (§16), and a
future serializer is stated to introduce its own format/version contract (§19 D-14) which does not exist. A
subsequent Architect Decision resolved the Product meaning of the first Artifact. This PATCH promotes it.

## Context

The canonical implemented path is `EditCandidate → EditReviewDecision → ApprovedEditDecision →
ApprovedEditExportRepresentation → EditExportAssembly` (042 §9.1, 043 §7.4, 044 §19, 044 §20). The next export
transition — `EditExportAssembly → canonical Edit Export Artifact` — is the sole in-scope frontier. Aggregation
precedes serialization (§8); an explicitly-supplied Assembly is already a complete, coherent, serializable
input, so Assembly membership-selection policy is not the blocker. Concrete serializers/formats, Export
Profile/Configuration, physical materialization, and delivery remain later, separately-gated stages.

## Confirmed Architect Decision Basis (B-1…B-15)

Recorded as `044 §21`:

- **B-1 Existence/anchor:** one Edit Export Artifact is derived from exactly one `EditExportAssembly` and
  represents that Assembly's complete approved edit meaning; no cross-Assembly Artifact.
- **B-2 External-representation transition:** the Artifact introduces the Product transition from internal
  canonical records to an external derived representation; the Assembly references its members, the Artifact
  presents their approved meaning as one self-contained external product — this external presentation is the
  new meaning appearing first at the Artifact stage.
- **B-3 Canonical external representation:** the Artifact is the canonical external representation of approved
  edit meaning, presenting each member's approved range, label/type, rationale, decision kind, and human actor
  in the Assembly's canonical order with provenance/traceability; LectureOS owns exactly one canonical Product
  representation.
- **B-4 External representation vs concrete syntax:** the Artifact fixes *what* it communicates (approved
  decision meaning), not *how* it is written; concrete human-readable/machine-readable syntaxes are additive
  serializer projections (§7.3, §19 D-14) that do not change the canonical meaning; the Artifact is not a named
  interchange format.
- **B-5 Derived and regenerable:** derived from the approved sources, regenerable, and its loss does not damage
  any approved record (§3.3, §13).
- **B-6 Non-authoritative:** authoritative for nothing canonical; the Approved Edit Decision / Representation /
  Assembly remain authoritative for their own meaning; the Artifact creates/alters/reinterprets no approved
  meaning and replaces no upstream.
- **B-7 Descriptive, non-executable:** presents approved editorial decisions, not executable
  cut/keep/delete/transform commands, output-timeline coordinates, or NLE/rendering instructions (§7.2).
- **B-8 Upstream:** consumes one `EditExportAssembly` read-only; aggregation precedes serialization; the
  Artifact is downstream of the Assembly.
- **B-9 Downstream:** serializer, concrete format/syntax, Export Profile, Export Configuration, physical
  materialization, delivery, and Export Package are strictly downstream and undefined here; a future serializer
  projects the canonical Artifact into concrete formats without changing its meaning.
- **B-10 Provenance/traceability:** provenance-bearing; traceable to the Assembly, its members, and through
  them to Source Timeline and Source Media (§8), without duplicating earlier-stage records.
- **B-11 Representation Failure:** inability to represent the approved meaning completely and faithfully in the
  canonical Artifact representation is an explicit Export Failure that names what could not be represented and
  preserves the sources, never a silently lossy Artifact (§11.4, §9, §3.10); format-specific representability
  is deferred to the serializer stage.
- **B-12 Relationship to Assembly/Representation:** the Representation is the atom; the Assembly is the coherent
  grouping (references); the Artifact is the derived external presentation — it introduces external
  representation and is not the Assembly restated.
- **B-13 Cardinality:** one Artifact represents exactly one Assembly's complete meaning; multiple derived
  Artifacts may represent the same Assembly (regenerable, §7.3), each carrying its complete meaning.
- **B-14 Status/Profile:** none — no status field, lifecycle, or state machine; no Export Profile or
  Configuration.
- **B-15 Deferrals:** the full list (below), with no placeholder abstraction.

## Affected Blueprint Files

- `docs/044_EXPORT_PIPELINE.md` — new normative §21 (sole owner); header amended to Blueprint 0.6 / Amended By
  PATCH-0017.

## Expected Normative Changes

- A single confirmed §21 "Edit-Pipeline Export Artifact — Canonical Approved Edit Decision Representation
  (First Slice)" recording B-1…B-15 and the fourteen canonical invariants.
- §3.3/§7.2 Artifact meaning and §11.4 Representation Failure are realized at the canonical level for the edit
  branch; the external-representation vs concrete-syntax distinction is made normative.
- §17 (Physical Materialization) remains Final-Subtitle-SRT-specific and is neither broadened nor reinterpreted.
- §19 and §20 are unchanged and remain the sole owners of the Representation and Assembly contracts.
- No change to the document's overall Draft status (a Draft document may contain confirmed subsections).

## Non-Goals

Any implementation, SQL, schema, storage, database, migration, repository, execution/admission code,
interface/UI/API, serializer, provider/NLE adapter, or Goal; concrete export schemas, external file formats,
serialization grammar, JSON/XML/EDL/FCPXML/AAF/CSV/Markdown/PDF/NLE mapping, file extension, MIME type,
checksum, filename; Artifact creation mechanics, physical materialization, delivery/download/upload/URLs, Export
Package; Export Profile/Configuration; cross-representation equivalence and format-specific representability;
executable edit semantics or output-timeline transformation; status/lifecycle. No modification to 042 §9.1/§9.2,
043 §7.4, 044 §19, 044 §20, the subtitle Approved Assembly / SRT Artifact / SRT Materialization contracts, or
PATCH-0007/0008/0013/0014/0015/0016.

## Acceptance Criteria

- [x] One confirmed first-slice subsection exists in 044 (`§21`).
- [x] The Edit Export Artifact is normatively established as the canonical external representation of one
  Assembly's complete approved edit meaning.
- [x] Derived from exactly one `EditExportAssembly`; regenerable; non-authoritative; descriptive and
  non-executable.
- [x] The external-representation (what) vs concrete-serialization-syntax (how) distinction is normative;
  concrete syntax is deferred to additive serializer projections; LectureOS owns exactly one canonical
  representation.
- [x] Wording prevents the Artifact from appearing equivalent to the Assembly — the Artifact introduces
  external presentation; the Assembly references members.
- [x] Aggregation-precedes-serialization preserved; serializer/format/Profile/Configuration/materialization/
  delivery/Export Package remain downstream and undefined.
- [x] Upstream Assembly (and its members) consumed read-only; authority boundaries preserved.
- [x] Provenance/traceability to Assembly, members, Source Timeline, and Source Media confirmed.
- [x] Representation Failure defined at Product level independently of any concrete syntax; no silent loss;
  format-specific representability deferred.
- [x] No status/lifecycle; no Export Profile/Configuration; no serializer/concrete format; no materialization.
- [x] Deferrals exhaustive and explicit; no deferred placeholder introduced.
- [x] Completed 042/043, 044 §19, 044 §20, and subtitle §17 contracts unchanged.
- [x] No code, schema, migration, or test changes; `SQLITE_SCHEMA_VERSION` remains 29.

## Validation Performed

- Changes limited to `docs/044_EXPORT_PIPELINE.md` and this PATCH — no `src/`, `tests/`, schema, or migration.
- `SQLITE_SCHEMA_VERSION` unchanged at 29; 042 §9.1/§9.2, 043 §7.4, 044 §19, and 044 §20 untouched; §17 remains
  subtitle-specific.
- §21 is the sole normative owner; every B-1…B-15 decision and all deferrals are promoted; the
  external-representation vs concrete-syntax distinction is explicit; no deferred placeholder introduced.
- Whitespace check passes; the change is additive and preserves every previous Blueprint contract.

## Result

- Status: **Accepted**
- Changed Blueprint Files: `docs/044_EXPORT_PIPELINE.md` (new §21; header).
- Notes: Records the accepted Architect Decision (B-1…B-15) for the first Edit Export Artifact, defining the
  canonical external representation of approved edit meaning while deferring all concrete serialization syntax.
  Product policy/clarification only; no schema, code, or Goal; no implementation commit (implementation has not
  begun). The next step is implementation of the Edit Export Artifact Application Foundation, authorized only
  after this PATCH is reviewed and accepted.

## Related Documents

- `PATCH-0015-edit-pipeline-export-application-foundation.md`
- `PATCH-0016-edit-export-assembly-scope.md`
- `../docs/044_EXPORT_PIPELINE.md`
- `../docs/043_REVIEW_PIPELINE.md`
- `../docs/030_DATA_MODEL.md`
