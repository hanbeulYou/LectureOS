# PATCH-0020

- Title: Source Intake Application Foundation — Source Media Transcription Intake Eligibility (First Slice) (040)
- Status: Accepted
- Priority: Medium
- Trigger: Architect / Product Owner Decision (first implementation of 040 §4.1 Source Intake; delegated bounded decisions)
- Created: 2026-07-25
- Target Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md`

---

## Status

Accepted. Establishes the first application contract for `040 §4.1 Source Intake` — confirming that an already
persisted `SourceMedia` record (045 §1) is eligible to be admitted as a Transcript Pipeline input. Introduces
one additive persisted record at schema **v31**; no media decoding, probing, or transcription.

## Trigger

`045 §1` (PATCH-0019) created the first owning `source_media` record (Media Import), but the transcript side
still references Source Media only as an unvalidated free-TEXT `source_media_id`, and `040 §4.1 Source Intake`
("confirm a Source Media reference and prepare a processing context") has never been implemented. The smallest
missing connection is a record that resolves a persisted `source_media` row by `SourceMediaId` and confirms it
is an eligible transcription input. A bounded, delegated Product decision settled that boundary and this PATCH
promotes it.

## Context

Source Intake is the transcript pipeline's first stage (`040 §4.1`), downstream of Media Import (045) and
upstream of the External ASR Boundary (§4.2). This slice implements only the eligibility/confirmation facet: it
consumes a `SourceMediaId`, resolves the persisted record read-only, and persists a deterministic intake record.
It produces no ASR result, Raw Transcript, or transcript content (consistent with §4.1 "Does Not Produce").

## First-Slice Product Decision

Eligibility is evaluated from **persisted facts only**: a `SourceMediaId` is eligible iff it resolves to a
persisted `source_media` record. Intake identity is **content-derived** from the Source Media
(`transcript-source-intake:<source_media_id>`), giving exactly one canonical intake per Source Media and
idempotency by construction. The intake is **persisted, durable, immutable, insert-only**, and carries only the
intake identity and the confirmed `SourceMediaId` reference — **no execution provenance/DomainResult** (the
slice answers a repository/application eligibility question, not an execution step; the CLI takes only
`--media`/`--database`). Intake **never checks physical file existence** (consistent with 045 §1 M-11), so a
moved/deleted reference-in-place original is not an eligibility failure. Malformed identities and unknown
(unresolvable) Source Media are rejected explicitly and distinctly.

## Confirmed Architect Decision Basis (S-1…S-14)

Recorded as `040 §13`:

- **S-1 Scope:** Media Import and Source Intake are separate steps; intake confirms eligibility of an existing
  `SourceMediaId`; no ffmpeg/probe/duration/codec/audio/transcode/transcription/provider/job.
- **S-2 Input:** a canonical `SourceMediaId`, not a filesystem path (paths belong to Media Import).
- **S-3 Eligibility:** a repository/application decision from persisted facts — eligible iff the id resolves to
  a persisted `source_media` record; unknown → ineligible; malformed identity → rejected before resolving.
- **S-4 No decoding claim:** admission asserts no audio stream, playability, or transcription success; language
  is "admitted transcription input" / "Source Media reference confirmed", not "transcription-ready media".
- **S-5 Physical availability:** intake does not check physical file existence; a moved/deleted original is a
  later-execution concern, not an eligibility failure; validation does not check physical existence; operational
  availability and persisted-domain integrity stay distinct.
- **S-6 Intake identity:** derived deterministically from the Source Media
  (`transcript-source-intake:<source_media_id>`); one canonical intake per Source Media.
- **S-7 Persistence:** admission is persisted, durable, immutable, insert-only, atomic; carries the intake
  identity and the `SourceMediaId` reference only — no codec/duration/audio/provider/model/language/path.
- **S-8 Idempotency:** repeated admission of the same Source Media resolves and returns the existing record
  (reused); near-concurrent duplicates converge idempotently.
- **S-9 Single canonical intake:** one canonical intake per Source Media (derived identity + uniqueness);
  distinct Source Media get distinct intakes.
- **S-10 Provenance:** the intake carries the confirmed `SourceMediaId` reference; `SourceMediaId` remains the
  canonical media identity; path is provenance, not identity.
- **S-11 Relationship to execution:** confirms eligibility only; produces no ASR result / Raw Transcript /
  transcript content; an already-associated transcript does not affect eligibility or idempotency.
- **S-12 Failure atomicity:** malformed identity / missing Source Media / persistence failure leave no partial
  state and preserve existing and Source Media records; the Source Media record is unchanged if the file moves.
- **S-13 Authority:** authoritative only for "this persisted Source Media is admitted as a transcript input";
  asserts no decodability/audio/transcribability; mutates no Source Media record or source bytes; existing
  Transcript identity/execution contracts take precedence.
- **S-14 Deferred:** the full deferred list (below), with no placeholder abstraction.

## Affected Blueprint Files

- `docs/040_TRANSCRIPT_PIPELINE.md` — new normative §13 (sole owner of the Source Intake application contract);
  header `Amended By` extended with PATCH-0020.

## Expected Normative Changes

- A single confirmed §13 recording S-1…S-14 and the fourteen canonical invariants, implementing §4.1's
  eligibility/confirmation facet.
- §4.1's existing text is not rewritten; §13 records the confirmed first-slice application contract.
- No change to 041–045; downstream `SourceMediaId` references are unchanged.

## Non-Goals

ffmpeg/ffprobe, media probing, duration/codec/resolution/stream extraction, audio-stream verification, audio
extraction, transcoding/normalization, waveform/thumbnail, playback, Whisper/transcription providers, model
selection, language detection, transcript generation/segmentation, background jobs, queues, retries, progress
reporting, remote media, uploads, object storage, managed media copy, provider/plugin registries, workflow
engines, NLE integration, export-format changes, multiple transcript-intakes per Source Media, and the actual
transcript execution linked to an intake. No placeholder for any deferred concept. No modification to 041–045 or
prior work.

## Acceptance Criteria

- [x] `040 §13` exists recording the first Source Intake application slice (S-1…S-14 + invariants).
- [x] Input is a canonical `SourceMediaId`, not a path; malformed identities and unknown Source Media are
  rejected explicitly and distinctly.
- [x] Eligibility is a persisted-facts repository/application decision; no codec/audio/decode claim.
- [x] Intake identity is content-derived; one canonical intake per Source Media.
- [x] Admission is persisted, durable, immutable, insert-only, atomic; idempotent on repeat; near-concurrent
  duplicates converge.
- [x] Intake does not check physical file existence; a moved/deleted original is not an eligibility failure.
- [x] No transcript content or execution result is produced; the Source Media record is never mutated.
- [x] Deferrals exhaustive and explicit; no placeholder introduced.
- [x] 041–045 and prior work unchanged.

## Validation Performed

- Blueprint change limited to `docs/040_TRANSCRIPT_PIPELINE.md` (new §13 + header); implementation adds
  application, persistence (schema v31, one additive table), CLI, validation, demo, and test modules.
- §4.1 text untouched; 041–045 untouched; downstream `SourceMediaId` references unchanged.
- Whitespace and UTF-8/mojibake checks pass; the change is additive and preserves every previous contract.

## Result

- Status: **Accepted**
- Changed Blueprint Files: `docs/040_TRANSCRIPT_PIPELINE.md` (new §13; header).
- Notes: Establishes the first implementation of §4.1 Source Intake as a persisted, content-derived, execution-
  independent eligibility record over an existing `source_media` reference; all decoding/probing/transcription
  concerns remain deferred.

## Related Documents

- `PATCH-0019-media-import-application-foundation.md`
- `../docs/040_TRANSCRIPT_PIPELINE.md`
- `../docs/045_MEDIA_IMPORT_PIPELINE.md`
- `../docs/030_DATA_MODEL.md`
