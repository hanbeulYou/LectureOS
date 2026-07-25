# Transcript Source Intake

- Status: Implementation Reference
- Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` §13 (implements §4.1 Source Intake) / `patches/PATCH-0020`
- Schema: v31 (one additive table `transcript_source_intakes`)

## What it is (and is not)

Source Intake is the first application slice of `040 §4.1`. It answers only one question: **can an
already-imported canonical Source Media record (045 §1) be admitted as an input to the Transcript Pipeline?**

- Media Import and Transcript Intake are **separate steps**. Intake accepts a **`SourceMediaId`, not a
  filesystem path** (paths belong to Media Import).
- Admission does **not** decode, probe, play, or transcribe media; it does **not** prove an audio stream exists;
  it asserts nothing about codecs, duration, resolution, language, or transcription success.
- Eligibility is a **repository/application-contract decision from persisted facts only**: a Source Media is
  eligible iff its id resolves to a persisted `source_media` record.
- Intake **does not check physical file existence**. A moved/deleted reference-in-place original is a
  later-execution concern, not an eligibility failure (consistent with 045 §1 M-11). Operational file
  availability and persisted-domain integrity stay distinct.
- Admission produces **no transcript content or execution result** and never mutates the Source Media record.

## Intake identity & idempotency

- Intake identity is content-derived: `transcript-source-intake:<source_media_id>` (the domain enforces the
  derivation), so there is exactly **one canonical intake per Source Media**.
- Repeated admission of the same Source Media resolves and returns the existing record (`created=False`); a
  near-concurrent duplicate converges on a persistence collision.
- A malformed Source Media identity (not `<algorithm>:<64 hex>`) is rejected before the repository is touched; an
  unknown (unresolvable) Source Media is rejected explicitly.

## Architecture

- `application/transcript_source_intake.py` — `TranscriptSourceIntake`, `TranscriptSourceIntakeResult`,
  `TranscriptSourceIntakeService`, `TranscriptSourceIntakeError`, `derive_intake_identity`,
  `require_canonical_source_media_id`, and the `SourceMediaQuery` / `TranscriptSourceIntakeQuery` /
  `AtomicTranscriptSourceIntakePersistence` ports. No execution provenance / DomainResult (an eligibility
  question, not an execution step).
- `persistence/transcript_source_intake.py` — `SQLiteTranscriptSourceIntakeRepository` +
  `SQLiteTranscriptSourceIntakeCommandPersistence` (atomic `BEGIN IMMEDIATE` insert; identity PK +
  `UNIQUE(source_media_id)` + FK to `source_media`).
- `composition.py::compose_sqlite_transcript_source_intake_service` — resolves an existing Source Media
  read-only and records the intake.
- `transcript_intake_cli.py` — the `lectureos.transcript_intake_cli` entry point.

## CLI

```bash
PYTHONPATH=src python3 -m lectureos.transcript_intake_cli --media <source-media-id> --database <db-path>
```

Requires an existing repository (import the media first with `media_import_cli`). Prints whether the intake was
`created` or `reused`, the intake identity, the Source Media identity, and `no transcription was executed`. Exit
`0` on success; exit `1` on a malformed/unknown media identity or any error, leaving the repository unchanged.

## Persistence (schema v31)

```sql
CREATE TABLE transcript_source_intakes (
    identity TEXT PRIMARY KEY,
    source_media_id TEXT NOT NULL,
    UNIQUE (source_media_id),
    FOREIGN KEY (source_media_id) REFERENCES source_media(identity)
)
```

The migration is strictly additive; every released version v1..v30 chains single-step to v31 preserving
existing rows, and downgrade / direct-skip / unsupported-target migrations are rejected.

## Validation

`validate_repository` adds a read-only `transcript_source_intakes` check:
`TRANSCRIPT_INTAKE_DANGLING_SOURCE_MEDIA` (references a missing `source_media`; also enforced by the FK),
`TRANSCRIPT_INTAKE_IDENTITY_DISAGREEMENT` (identity not derived from the Source Media reference), and
`TRANSCRIPT_INTAKE_DUPLICATE` (more than one intake per Source Media). It never checks physical file existence.
See `implementation/070_REPOSITORY_VALIDATION.md`.

## Deferred

ffmpeg/ffprobe, media probing, duration/codec/resolution/stream extraction, audio-stream verification, audio
extraction, transcoding, waveform/thumbnail, playback, Whisper/transcription providers, model selection,
language detection, transcript generation/segmentation, background jobs, queues, retries, remote media, uploads,
object storage, managed media copy, provider/plugin registries, multiple transcript-intakes per Source Media,
and the actual transcript execution linked to an intake — all deferred (see `040 §13` S-14).
