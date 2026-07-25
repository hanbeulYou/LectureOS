# PATCH-0019

- Title: Media Import Application Foundation — Local Source Media Registration (First Slice) (045)
- Status: Accepted
- Priority: Medium
- Trigger: Architect / Product Owner Decision (first local Media Import slice; delegated bounded decisions)
- Created: 2026-07-25
- Target Blueprint: `docs/045_MEDIA_IMPORT_PIPELINE.md` (new)

---

## Status

Accepted. Establishes the first Media Import product/Application contract and the first owner of
`SourceMediaId`. Introduces one additive persisted record (Source Media) at schema **v30**; no media decoding,
probing, transcoding, copying, or remote transfer.

## Trigger

`SourceMediaId` has been an unowned leaf identity — referenced by transcript, subtitle, edit, review, and
export records, but never persisted as an owning record. `030_DATA_MODEL.md §5.1` defines Source Media as the
top physical evidence and marks the file-lifecycle responsibility split as **Requires Validation**;
`020_PRODUCT_REQUIREMENTS.md §5.1 (MIR-001…006)` requires media ingestion but defines no persisted record. The
first runnable Media Import slice needs a canonical boundary between an external local file and LectureOS's
internal Media identity. A bounded, delegated Product decision settled that boundary and this PATCH promotes it.

## Context

Media Import is the pipeline origin (upstream of `040_TRANSCRIPT_PIPELINE.md`). The first slice consumes one
local file and produces one canonical, durable Source Media record identified by its content — it is the first
capability to own `SourceMediaId`. Downstream pipelines continue to reference `SourceMediaId` unchanged.

## First-Slice Product Decision

Media identity is **content-addressed**: it is derived deterministically from a streaming SHA-256 fingerprint
of the file bytes (`sha256:<hexdigest>`). This makes identity independent of path/filename/extension, idempotent
for identical content by construction, and free of silent duplicate Media records. The original file is
**referenced in place** (not copied into managed storage); the record stores the content fingerprint, byte
length, and the resolved observed source path as immutable import provenance. Empty (0-byte) files are
ineligible. LectureOS is not authoritative for the file's continued physical availability (settling
`030 §5.1`'s Requires-Validation boundary for this slice).

## Confirmed Architect Decision Basis (M-1…M-14)

Recorded as `045 §1`:

- **M-1 Scope/origin:** pipeline origin; local file in → one canonical Source Media record out; no
  codec/duration/decode/transcode/ffmpeg/remote/managed-storage.
- **M-2 Source eligibility:** a readable local regular file; extension is not proof of media type; missing,
  directory, non-regular, unreadable, and 0-byte files are explicit failures; a symlink is allowed only when it
  resolves to a readable regular file, recording the resolved path.
- **M-3 Media identity boundary:** identity is content-derived (`sha256:<digest>`); path/filename/extension are
  not identity; identical content → identical identity.
- **M-4 Content fingerprint:** streaming SHA-256, lowercase 64-hex, with an `sha256` algorithm marker
  (future algorithms additive).
- **M-5 Observed source path:** the resolved absolute path is recorded as provenance; it is not identity and not
  an availability guarantee.
- **M-6 Reference in place:** the original file is referenced in place; no managed copy, move, or deletion.
- **M-7 Byte length:** byte length (> 0) is recorded as a stable filesystem fact; no decoded facts (duration…).
- **M-8 Idempotency:** re-importing identical content resolves and returns the existing record (reused); no
  duplicate record.
- **M-9 Same content, different path:** identical content converges on one identity regardless of path/filename;
  the recorded path stays the first import's and is immutable.
- **M-10 Same path, changed content:** changed content → different fingerprint → different identity → a new
  record; differing records coexist (insert-only).
- **M-11 Missing source after import:** a moved/deleted/changed original does not alter the persisted record;
  LectureOS is not authoritative for continued physical availability; validation does not check physical
  existence.
- **M-12 Persistence/atomicity:** durable, immutable, insert-only, one atomic transaction; failures leave no
  partial state and preserve existing records; canonical fingerprint uniqueness is enforced; near-concurrent
  duplicate imports converge idempotently.
- **M-13 Authority:** authoritative only for the original facts (content identity, fingerprint, byte length,
  first observed path); asserts no decodability/playability/transcription/duration; never mutates source bytes.
- **M-14 Deferred:** the full deferred list (below), with no placeholder abstraction.

## Affected Blueprint Files

- `docs/045_MEDIA_IMPORT_PIPELINE.md` — new normative doc (sole owner of the Media Import contract).

## Expected Normative Changes

- A single confirmed `045 §1` recording M-1…M-14 and the fourteen canonical invariants.
- `030 §5.1`'s Requires-Validation file-lifecycle boundary is settled for the first slice (LectureOS not
  authoritative for continued physical availability); `030 §5.1` text is not rewritten — `045` owns the
  refinement.
- No change to 040–044 contracts; downstream `SourceMediaId` references are unchanged.

## Non-Goals

ffmpeg/ffprobe, codec parsing, duration/frame-rate/resolution/stream extraction, audio extraction,
transcoding/normalization, thumbnail/waveform generation, playback, Whisper/transcription, speech-language
detection, remote URL import, uploads, object/cloud storage, provider adapters, background processing, job
queues, retries, progress reporting, managed content-addressable storage as a subsystem, automatic source
deletion, media rendering, NLE integration, additional export formats, and media revision history. No
placeholder for any deferred concept. No modification to 040–044 or the completed edit-export/validation work.

## Acceptance Criteria

- [x] `045 §1` exists recording the first Media Import slice (M-1…M-14 + invariants).
- [x] Media identity is content-addressed (`sha256:<digest>`); path/filename/extension are explicitly not
  identity.
- [x] Streaming SHA-256 fingerprint (lowercase 64-hex) with an `sha256` marker; byte length recorded (> 0);
  empty files ineligible.
- [x] Reference-in-place; the original is not copied, moved, deleted, or mutated.
- [x] Idempotent re-import; same-content/different-path convergence; same-path/changed-content → new record.
- [x] Not authoritative for continued physical availability; validation does not check physical existence.
- [x] Durable/immutable/insert-only atomic persistence; failures leave no partial state; fingerprint uniqueness
  enforced; near-concurrent duplicates converge.
- [x] Deferrals exhaustive and explicit; no placeholder introduced.
- [x] 040–044 and prior work unchanged.

## Validation Performed

- Blueprint change limited to `docs/045_MEDIA_IMPORT_PIPELINE.md` (new) and a `docs/README.md` index pointer;
  implementation adds application, infrastructure, persistence (schema v30, one additive table), CLI,
  validation, demo, and test modules.
- `030 §5.1` text untouched; 040–044 untouched; downstream `SourceMediaId` references unchanged.
- Whitespace and UTF-8/mojibake checks pass; the change is additive and preserves every previous contract.

## Result

- Status: **Accepted**
- Changed Blueprint Files: `docs/045_MEDIA_IMPORT_PIPELINE.md` (new).
- Notes: Establishes the first owner of `SourceMediaId` via a content-addressed, reference-in-place local Media
  Import; all decoding, probing, transcoding, and remote/managed-storage concerns remain deferred.

## Related Documents

- `PATCH-0009-lecture-analysis-input-eligibility.md`
- `../docs/045_MEDIA_IMPORT_PIPELINE.md`
- `../docs/030_DATA_MODEL.md`
- `../docs/020_PRODUCT_REQUIREMENTS.md`
- `../docs/040_TRANSCRIPT_PIPELINE.md`
