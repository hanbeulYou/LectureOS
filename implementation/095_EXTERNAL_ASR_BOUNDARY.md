# External ASR Boundary — Provider Transcript Result Admission

- Status: Implementation Reference
- Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` §14 (implements §4.2 External ASR Boundary, §4.3 Raw Transcript
  Preservation) / `patches/PATCH-0021`
- Schema: v32 (one additive table `provider_transcript_admissions`)

## What it is (and is not)

The External ASR Boundary admission is the first application realization of `040 §4.2`/`§4.3`. It answers one
question: **how does LectureOS admit an externally produced ASR result for an already-admitted Source Media
intake?**

- It consumes a canonical `TranscriptSourceIntakeId` (`040 §13`) and a provider-neutral (LectureOS-native) ASR
  result document — **not** a media path.
- It **executes no ASR engine** and reads no media file: the provider result is *supplied*, not computed. No
  ffmpeg/ffprobe, Whisper, audio extraction, decoding, or network.
- It preserves the provider evidence as a `ProviderTranscriptResult` (un-normalized) and projects **exactly one**
  canonical `RawTranscript` (with its `TranscriptSegment`s). The provider result is referenced as provenance and
  is never the transcript's identity (`040 §4.2`).

## Input document (provider-neutral)

```json
{
  "provider": "<provider-reference>",
  "model": "<optional-model>",
  "language": "<optional-declared-language>",
  "provider_result_ref": "<external-result-reference>",
  "segments": [ { "start": 0.0, "end": 2.5, "text": "..." }, ... ]
}
```

- `provider` and `provider_result_ref` are required and non-blank; `model`/`language` are optional (a *declared*
  passthrough language — no language **detection**).
- Segments carry `start`/`end` in **seconds** (finite, `start >= 0`, `end > start` — zero-length spans rejected),
  must be non-decreasing in `start` and non-overlapping (touching boundaries allowed), and `text` is required,
  non-blank, and preserved exactly (Korean/non-ASCII preserved). An **empty** (zero-segment) result is rejected.

## Identity, idempotency, and conflict

- All LectureOS identities are derived deterministically from the anchor
  `(intake_id, provider, model, provider_result_ref)` (SHA-256 → `<digest>`): `ProviderTranscriptAdmissionId`,
  `ProviderTranscriptResultId`, `TranscriptId` (raw), `DomainResultId`, `ProcessingRunId`, `UnitExecutionId`,
  and per-segment `TranscriptSegmentId`. No wall-clock/randomness participates.
- An intake **may** hold multiple provider results (distinct anchors); one provider result → **one** Raw
  Transcript.
- Admission is idempotent by content: a SHA-256 `content_fingerprint` over the full payload (every segment's
  timing and exact text) decides reuse. Same anchor + identical payload → `created = false`; same anchor +
  **different** payload → conflict, rejected without mutation (never a silent overwrite).

## External execution provenance

This slice creates **no** internal `ProcessingRun`/`UnitExecution` and requires **no** RUNNING unit execution
(that would be fake execution semantics for an external boundary). The `run_id`/`unit_execution_id`/
`domain_result_id` on the canonical records are deterministic external-execution provenance markers derived from
the anchor; the transcript tables carry them as plain references (no cross-table foreign key requires internal
execution rows). The raw transcript's `DomainResultReference` (kind `raw_transcript`) is created and persisted.

## Architecture

- `application/provider_transcript_admission.py` — `ProviderTranscriptDocument` /
  `ProviderTranscriptSegmentInput` (+ `build_provider_transcript_document`), `ProviderTranscriptAdmission`,
  `ProviderTranscriptAdmissionResult`, `ProviderTranscriptAdmissionService`, `ProviderTranscriptAdmissionError`
  / `ProviderTranscriptAdmissionConflictError`, and the query/persistence ports. Reuses the existing
  `ProviderTranscriptResult`, `TranscriptSegment`, and `RawTranscript` domain records unchanged.
- `persistence/provider_transcript_admission.py` — `SQLiteProviderTranscriptAdmissionRepository` +
  `SQLiteProviderTranscriptAdmissionCommandPersistence`: one atomic `BEGIN IMMEDIATE` writing the provider
  result, segments, raw transcript (+ membership), domain result, and the admission binding row, reusing the
  existing transaction-free insert helpers.
- `composition.py::compose_sqlite_provider_transcript_admission_service`.
- `transcript_result_admit_cli.py` — the `lectureos.transcript_result_admit_cli` entry point.

## CLI

```bash
PYTHONPATH=src python3 -m lectureos.transcript_result_admit_cli \
    --intake <transcript-source-intake-id> --input <provider-result.json> --database <db-path>
```

Requires an existing repository with the intake already admitted. Prints the admission identity, the provider
transcript result identity, the canonical Raw Transcript identity, the segment count, whether it was `created`
or `reused`, and `LectureOS did not execute an ASR engine`. Exit `0` on success; exit `1` on malformed/unknown/
conflicting/invalid input, leaving the repository unchanged.

## Persistence (schema v32)

```sql
CREATE TABLE provider_transcript_admissions (
    identity TEXT PRIMARY KEY,
    transcript_source_intake_id TEXT NOT NULL,
    source_media_id TEXT NOT NULL,
    provider_transcript_result_id TEXT NOT NULL,
    raw_transcript_id TEXT NOT NULL,
    provider_reference TEXT NOT NULL CHECK (length(trim(provider_reference)) > 0),
    provider_model TEXT,
    declared_language TEXT,
    provider_result_ref TEXT NOT NULL CHECK (length(trim(provider_result_ref)) > 0),
    segment_count INTEGER NOT NULL CHECK (segment_count > 0),
    content_fingerprint TEXT NOT NULL CHECK (length(content_fingerprint) = 64),
    UNIQUE (provider_transcript_result_id),
    UNIQUE (raw_transcript_id),
    FOREIGN KEY (transcript_source_intake_id) REFERENCES transcript_source_intakes(identity),
    FOREIGN KEY (source_media_id) REFERENCES source_media(identity)
)
```

The migration is strictly additive; every released version v1..v31 chains single-step to v32 preserving existing
rows, and downgrade / direct-skip / unsupported-target migrations are rejected. The existing provider result,
segment, raw transcript, and domain result tables (v5) are reused unchanged.

## Validation

`validate_repository` adds read-only `provider_transcript_admissions` checks:
`PROVIDER_TRANSCRIPT_ADMISSION_DANGLING_INTAKE` / `_DANGLING_SOURCE_MEDIA` / `_DANGLING_PROVIDER_RESULT` /
`_DANGLING_RAW_TRANSCRIPT` (broken references), `_PROVENANCE_DISAGREEMENT` (intake not derived from the Source
Media), `_RAW_PROVIDER_DISAGREEMENT` (raw transcript and provider result provenance disagree),
`_SEGMENT_COUNT_DISAGREEMENT` (recorded count vs raw transcript membership), and `_DUPLICATE_PROVIDER_RESULT` /
`_DUPLICATE_RAW_TRANSCRIPT` (also UNIQUE-enforced). A general `RAW_TRANSCRIPT_SEGMENT_ORDINAL_NONCONTIGUOUS`
check verifies raw transcript segment ordinals form a contiguous 0..n-1 sequence. None check provider
availability, model installation, network reachability, or physical media existence. See
`implementation/070_REPOSITORY_VALIDATION.md`.

## Deferred

ffmpeg/ffprobe, media decoding, audio extraction, codec/duration/stream inspection, Whisper / faster-whisper /
whisper.cpp / cloud ASR, model download/selection, GPU/device selection, credentials, provider installation, a
provider/plugin registry, background jobs, queues, retries, progress, cancellation, streaming, diarization,
speaker identification, word/token-level timestamps, confidence-based correction, language detection, correction
candidates, corrected revisions, raw-transcript structural validation, review, and subtitle/export changes — all
deferred (see `040 §14` A-15). No placeholders are introduced.
