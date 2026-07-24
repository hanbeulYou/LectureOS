# PATCH-0018

- Title: Edit-Pipeline Export — First Concrete Serialization and Local Materialization (LectureOS Edit Export JSON v1) (044)
- Status: Accepted
- Priority: Medium
- Trigger: Architect / Product Owner Decision (delegated first-concrete-format selection for the first runnable Edit Export slice)
- Created: 2026-07-24
- Target Blueprint: `docs/044_EXPORT_PIPELINE.md`

---

## Status

Accepted. Product policy/clarification plus the first concrete serializer + local materialization contract. No
database persistence of derived Artifact or serialized output; no schema/migration; `SQLITE_SCHEMA_VERSION`
stays 29.

## Trigger

The Edit Export Artifact Foundation (044 §21 / PATCH-0017) established the canonical, format-neutral external
representation but left concrete serialization syntax and physical materialization deferred (§21 B-15; §19
D-14 stated a future serializer introduces its own format/version contract). Producing the first real, runnable
edit-export file requires selecting one concrete format and defining local file materialization. A bounded,
delegated Product decision selected the first format and this PATCH promotes the serializer + local
materialization contract as one cohesive first runnable slice.

## Context

The implemented path is `... → EditExportAssembly → EditExportArtifact` (044 §20, §21). §21 fixes *what* the
Artifact communicates; this slice adds the first projection of *how* it is written (a concrete format) plus safe
local file materialization and a runnable entry point. It is additive over §21 and changes no §21 meaning.

## First-Format Product Decision

The `EditExportArtifact` carries descriptive approved editorial decisions (per member: approved Source Timeline
range, approved Candidate Type/label, approved rationale, approving decision kind accept|modify, human actor) —
not executable timeline operations. NLE interchange formats (EDL, FCPXML, AAF, OTIO) require executable /
output-timeline semantics (record timecodes, reels, tracks, frame rates) and cannot carry the rationale,
decision kind, actor, or label without inventing missing timeline semantics or silently dropping meaning; they
therefore cannot represent the current Artifact meaning completely and faithfully and are rejected for the
first slice. The selected first format is **LectureOS-native JSON** (`lectureos-edit-export-json`, version
`v1`, identifier `application/vnd.lectureos.edit-export+json`), the smallest stable format that represents every
Artifact field losslessly, deterministically, and inspectably, introduces no executable semantics, and admits
future additive projection into other formats.

## Confirmed Architect Decision Basis (C-1…C-14)

Recorded as `044 §22`:

- **C-1 Selected format:** LectureOS-native JSON `lectureos-edit-export-json` v1 (identifier
  `application/vnd.lectureos.edit-export+json`); not an NLE interchange format.
- **C-2 Complete faithful field mapping:** top-level format id/version, artifact identity, source assembly /
  media / timeline identities, and the ordered edit list; each edit carries source representation identity,
  decision kind, approved range start/end, approved Candidate Type/label, approved rationale, and human actor —
  nothing omitted, truncated, normalized away, reinterpreted, or invented.
- **C-3 Ordering:** entries preserve the §20/§21 canonical member order (stable identity order); storage/replay
  order, not an edit-execution/timeline/overlap order.
- **C-4 Deterministic serialization:** byte-identical output for the same Product meaning; fixed field order,
  no wall-clock/locale/randomness, UTF-8, LF newlines, single trailing newline, non-ASCII preserved unescaped.
- **C-5 Format-specific Representation Failure:** unrepresentable values (e.g. non-finite numbers) cause an
  explicit failure, never silent loss or an invalid document; §11.4 applied against the selected representation.
- **C-6 Local physical materialization:** write the serialized bytes to a caller-selected local destination as
  one complete file via temporary-file write + flush + fsync + atomic placement; no partial final file on
  failure; caller owns destination selection.
- **C-7 Collision/overwrite:** identical existing bytes → idempotent success; different bytes → explicit
  collision failure by default (no overwrite); overwrite only on explicit request, performed atomically; a
  symlink or non-regular existing object is never overwritten; necessary parent directories may be created.
- **C-8 Successful result:** structured result with final path, format identifier, format version, realized
  byte length, and encoding; success reported only after the complete file is durably placed.
- **C-9 Non-executable/descriptive:** no cut/keep/delete/transform command, output-timeline coordinate, or
  NLE/rendering instruction; ranges are approved Source Timeline ranges, not output-timeline coordinates.
- **C-10 Authority/provenance:** serializer and materializer are non-authoritative projections; they create /
  alter / reinterpret no approved decision; the Approved Edit Decision / Representation / Assembly remain
  authoritative; the document carries provenance to the Artifact/Assembly and Source Timeline/Media; approved
  upstream data is preserved on every failure.
- **C-11 Regenerability:** the serialized result is derived/regenerable; re-running from the same valid upstream
  yields the same Product meaning and byte-identical document; neither the serialized result nor the file is an
  authoritative canonical record, and its loss damages no approved source.
- **C-12 Persistence boundary:** no durable DB storage of the derived Artifact or serialized output; no new
  table/schema/migration; `SQLITE_SCHEMA_VERSION` unchanged; side effects only on the local filesystem when
  materializing.
- **C-13 Runnable entry point:** a real application entry point identifies a valid Assembly, derives its
  Artifact, serializes, materializes locally, reports the final path and format/version, and fails explicitly
  without a false success or a final file on error.
- **C-14 Deferrals:** the full list (below), with no placeholder abstraction.

## Affected Blueprint Files

- `docs/044_EXPORT_PIPELINE.md` — new normative §22 (sole owner); header amended to Blueprint 0.7 / Amended By
  PATCH-0018.

## Expected Normative Changes

- A single confirmed §22 recording C-1…C-14 and the fourteen canonical invariants: the first concrete format,
  deterministic serialization, complete faithful field mapping, format-specific Representation Failure, safe
  local materialization with collision/overwrite semantics, the successful-result contract, and the runnable
  entry point.
- §22 is additive over §21 and changes no §21 (or §17/§19/§20) meaning; §17 remains Final-Subtitle-SRT-specific.
- No change to the document's overall Draft status.

## Non-Goals

Other concrete formats (EDL/FCPXML/AAF/OTIO/CSV/…); multiple formats; serializer registry or plugin discovery;
cross-format equivalence; Export Profile/Configuration; provider/NLE adapter; executable cut/delete/keep/edit
commands; applying edits to source media; output-timeline transformation; rendering; remote upload/download,
URLs, object storage, or delivery lifecycle; retry lifecycle; replacement/revision/history of the serialized
result or file; database persistence of the derived Artifact or serialized output; schema migration; generalized
package/bundle export; checksum policy (not required for safe local materialization); speculative abstractions
or placeholders for future formats. No modification to 042/043, 044 §19/§20/§21, or the subtitle contracts.

## Acceptance Criteria

- [x] One confirmed §22 exists recording the first concrete serialization + local materialization slice.
- [x] First format is `lectureos-edit-export-json` v1, explicitly not an NLE interchange format, with a stated
  faithful-representation rationale.
- [x] Complete faithful field mapping from `EditExportArtifact` with no omission/truncation/reinterpretation.
- [x] Deterministic serialization (UTF-8, LF, single trailing newline, fixed field order, non-ASCII preserved).
- [x] Explicit format-specific Representation Failure; no silent loss; approved sources preserved.
- [x] Local materialization is atomic with no partial final file on failure; explicit collision, no default
  overwrite, explicit-overwrite only, foreign-object safety, permitted parent-dir creation.
- [x] Structured successful result (final path, format, version, byte length, encoding), reported only after
  durable placement.
- [x] Serializer/materializer are non-authoritative projections; descriptive/non-executable; regenerable.
- [x] No DB persistence of the derived Artifact or serialized output; no schema/migration; `SQLITE_SCHEMA_VERSION`
  remains 29.
- [x] A runnable entry point exists and fails explicitly without a false success or final file.
- [x] Deferrals exhaustive and explicit; no placeholder introduced.
- [x] §21 and prior contracts unchanged.

## Validation Performed

- Blueprint change limited to `docs/044_EXPORT_PIPELINE.md` and this PATCH; implementation adds application,
  infrastructure, entry-point, and test modules only — no schema, table, or migration.
- `SQLITE_SCHEMA_VERSION` unchanged at 29; §17/§19/§20/§21 untouched; §22 is additive.
- §22 is the sole normative owner; every C-1…C-14 decision and all deferrals are promoted; no deferred
  placeholder introduced.
- Whitespace and UTF-8/mojibake checks pass; the change is additive and preserves every previous contract.

## Result

- Status: **Accepted**
- Changed Blueprint Files: `docs/044_EXPORT_PIPELINE.md` (new §22; header).
- Notes: Records the delegated first-concrete-format Product decision and the first runnable Edit Export slice
  contract (serializer + local materialization + entry point). Concrete syntax is now fixed for one format only;
  all other formats and delivery/storage concerns remain deferred.

## Related Documents

- `PATCH-0015-edit-pipeline-export-application-foundation.md`
- `PATCH-0016-edit-export-assembly-scope.md`
- `PATCH-0017-edit-export-artifact-representation.md`
- `../docs/044_EXPORT_PIPELINE.md`
- `../docs/043_REVIEW_PIPELINE.md`
