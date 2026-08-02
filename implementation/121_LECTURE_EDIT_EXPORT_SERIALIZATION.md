# Edit Export Serialization and Local Materialization — Effective-Transcript Generation

- Status: Implementation Reference
- Blueprint: `docs/044` §25 + `PATCH-0037` (S-1…S-11, Confirmed) — this generation's concrete format
  and local file boundary over the GOAL-031 Artifact (GOAL-032); `§22`'s legacy contract, `§23`
  EA-1…EA-11, and `§24` AR-1…AR-11 are inherited unchanged
- Schema: **v53, unchanged** — no table, no migration, no validator code (S-10)

## Purpose

`§24` ended at a canonical external representation with no concrete syntax. `§25` decides how that
representation becomes bytes and, optionally, one local file.

```text
LectureEditExportArtifact (derived, not stored — GOAL-031)
  → serialize_lecture_edit_export_json(artifact)     deterministic bytes, not stored
    → materialize(serialized, destination, overwrite) one complete local file, not stored
```

This completes the effective-transcript Edit Export branch: **Review → file**, end to end.

## One format, separately identified (S-2, S-3)

`lectureos-lecture-edit-export-json` `v1`,
media type `application/vnd.lectureos.lecture-edit-export+json`, UTF-8.

The legacy `lectureos-edit-export-json` `v1` is **not** reused, and this is not a version bump of it.
Two payload fields make the shapes necessarily different — the legacy document carries a top-level
`source_media_id` and a per-edit `source_representation_id`, and neither exists here (`§23` EA-2
dropped `§19`'s atom; `§24` AR-6 keeps Source Media out of the Artifact) — so one identifier and
version would denote two shapes and make every consumer's parse ambiguous. A bump was rejected
separately: both generations stay valid and the legacy serializer keeps producing `v1` for legacy
Artifacts, so `v2` would falsely describe it as superseded. Tests pin both the distinctness and the
version.

## Field mapping, and what it deliberately omits (S-4)

```json
{ "format", "version", "artifact_id", "source_assembly_id", "source_timeline_id",
  "edits": [ { "source_approved_edit_decision_id", "decision_kind",
               "approved_range_start", "approved_range_end",
               "approved_label", "approved_rationale", "actor" } ] }
```

Key order is asserted exactly, at both levels. Values are copied verbatim from the Artifact, which
copied them verbatim from the `ApprovedEditDecision` and the `ReviewDecision`.

**No `source_media_id`.** `§22` does not require it in the document — C-2's completeness is
Artifact-relative, its prohibition covers *approved* fields, Canonical Invariant (2) speaks of
approved meaning, and C-3/C-4 govern only ordering and determinism. Source Media stays reachable
through the anchor chain from the `source_assembly_id` the document carries, and `§2.9` Source
Timeline traceability is satisfied by `source_timeline_id` directly. Adding it would push a
repository query into a layer C-10 defines as a non-authoritative projection. Whether the document
should carry it anyway is **deferred**, not settled — a test pins its absence so the question stays
visible.

## Determinism (S-5)

Fixed key order (Python dict insertion order), the Artifact's canonical entry order, UTF-8, LF only,
exactly one trailing newline, `ensure_ascii=False` so Korean survives unescaped. Tests assert
byte-stability across repeated serialization, across re-derivation of the Artifact, and **across a
working-directory change** — the last one pins that no process or filesystem state leaks into the
bytes. Nothing reads a wall clock, randomness, UUID, path, execution or provider identifier, mutable
currentness, or locale.

Member order carried into the document is presentation only — never an execution,
edit-application, output-timeline, overlap, or authority order.

## Local materialization (S-6, S-7)

C-6/C-7/C-8 are inherited in meaning, not reinvented:

| Rule | Behaviour |
| --- | --- |
| destination | **caller-supplied**; this layer chooses no path |
| write | temp file in the destination's parent → flush → fsync → atomic placement (`os.link`, or `os.replace` only on explicit overwrite) |
| partial file | never left at the final path; the temp file is removed in a `finally` |
| identical bytes | idempotent success, no rewrite |
| different bytes | explicit collision, **not** overwritten |
| overwrite | only on explicit request, then atomic |
| symlink / non-regular | never overwritten |
| success | reported only after durable placement, as a structured result (path, format, version, media type, byte length, encoding) |

**The file is not the identity (S-6).** A test materializes one payload at two destinations and
asserts the Artifact identity is unchanged. Destination validation beyond S-7's named rules
(absolute-path requirement, parent resolution) is an implementation choice, as it was in the legacy
realization.

## Three failure layers, kept distinct (S-8)

| Layer | Error | Reached by |
| --- | --- | --- |
| derivation | `ArtifactRepresentationFailureError` (GOAL-031) | member unresolvable, lineage mismatch |
| serialization | `LectureEditExportSerializationError` | a value JSON cannot express (`allow_nan=False`) |
| materialization | `LectureEditExportMaterializationError` and its three subtypes | containment, collision, write |

A serialization failure is asserted to leave **no file at the destination**, and a write failure to
leave neither the final file nor any temporary residue. In every case the upstream Artifact,
Assembly, `ApprovedEditDecision`, Review records, and authority history are untouched.

## Generation separation

This generation declares its **own** error family and its own writer rather than importing the legacy
`application.edit_export_*` modules — the idiom GOAL-028 established for the Review vocabulary. An
`ast`-based test asserts none of the three new modules imports a legacy Export module. The writer's
file mechanics are deliberately identical to the hardened legacy writer, because S-7 inherits
C-6/C-7/C-8 unchanged and weakening them would be changing a product contract; the duplication buys
the separation.

## Nothing is persisted, and nothing is approved (S-10, S-11)

Neither the payload nor the file outcome is stored: no table, no migration, no validator code, and
`SQLITE_SCHEMA_VERSION` stays **v53**. The composition for materialization takes **no database
connection at all**, which is the structural proof that nothing here requires the `§24` Artifact to
be persisted. Tests assert seven relations are unchanged across a materialization, that no
serialization or materialization table exists, and that the legacy Export relations stay empty.

Serializing and materializing approve nothing: no member is added, dropped, filtered, or modified;
no re-approval, Final Selection, Export Approval, or publication authority exists; Review remains the
only stage at which Human Authority is exercised.

## Architecture

- `application/lecture_edit_export_serialization.py` — format constants,
  `SerializedLectureEditExport`, `serialize_lecture_edit_export_json`, and the serialization error.
- `application/lecture_edit_export_materialization.py` — the error family, the
  `LectureEditExportFileWriter` port, `LectureEditExportMaterializationResult`, and the service.
- `infrastructure/local_lecture_edit_export_file_writer.py` — the hardened atomic local writer.
- `composition.compose_lecture_edit_export_materialization_service()` — no connection required.
- `lecture_edit_export_cli.py` — gains `serialize` and `materialize`; the `_NOT_PART` banner drops
  "serializer and export file" (now part of the contract) and names **other** concrete formats.

## Status

Complete: 35 focused new tests (format identity, field mapping, determinism, serialization failure,
materialization rules, persistence separation, import-graph separation, CLI); the complete
**3329**-test suite passes; schema **v53 unchanged**.

**The branch is now complete and the remaining work is policy, not stages.** `§23`'s three undecided
policies — the product behaviour on a Source Timeline holding a cross-actor Conflict, overlap
adjudication, and the treatment of a scope with no eligible member — are unaffected by this milestone
and sit at the **start** of the pipeline: a repository in any of those states still cannot begin an
export, however complete these downstream stages are. Also unchanged: whether the document must carry
Source Media identity, other concrete formats, cross-format equivalence, Export Profile and
Configuration, provider and NLE adapters, delivery, packaging, publication, and every `043 §15.4`
deferred item.
