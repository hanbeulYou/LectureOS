# Media Import

- Status: Implementation Reference
- Blueprint: `docs/045_MEDIA_IMPORT_PIPELINE.md` §1 / `patches/PATCH-0019`
- Schema: v30 (one additive table `source_media`)

## What it is (and is not)

Media Import registers a local file as a canonical, **content-addressed** Source Media record — the first owner
of `SourceMediaId`. It records **file identity and provenance only**:

- It does **not** decode, transcode, probe, play, or transcribe media.
- **Source paths are not Media identity**; filename and extension are not proof of media type.
- If the original file later **moves or disappears**, the persisted record is unchanged — LectureOS is **not
  authoritative for the file's continued physical availability**, and validation never checks physical
  existence.

## Media identity & fingerprint

- Identity is derived from content: `SourceMediaId = "sha256:<hexdigest>"`.
- The fingerprint is a **streaming SHA-256** of the file bytes (fixed 1 MiB chunks; the file is never loaded
  whole into memory), represented as a lowercase 64-hex digest with an `sha256` algorithm marker.
- The domain enforces the derivation (`identity == "<algorithm>:<digest>"`), so a record can never disagree
  with its content.

## Idempotency & duplicate semantics

- **Repeated import** of identical content resolves and returns the existing record (`created=False`) — never a
  duplicate.
- **Same content, different path/filename** → the same identity (converge); the recorded observed path stays
  the first import's (the record is immutable).
- **Same path, changed content** → a different fingerprint → a different identity → a new record (differing
  records coexist, insert-only).
- **Near-concurrent duplicate** imports converge idempotently (a persistence collision is resolved to the
  existing record).

## Source location & lifecycle

- The original file is **referenced in place** (no managed copy, move, or deletion).
- The record stores the resolved absolute observed source path, byte length (> 0), and the content fingerprint
  as immutable provenance.
- Empty (0-byte) files, missing paths, directories, non-regular files, and unreadable files are rejected with
  an explicit `MediaImportError`. A symlink is accepted only when it resolves to a readable regular file; the
  resolved real path is recorded.

## Architecture

- `application/media_import.py` — `SourceMediaRecord`, `SourceMediaFingerprint`, `MediaImportResult`,
  `MediaImportService`, `MediaImportError`, `derive_media_identity`, and the `SourceMediaInspector` /
  `SourceMediaQuery` / `AtomicSourceMediaPersistence` ports.
- `infrastructure/local_source_media_inspector.py` — `LocalSourceMediaInspector` (read-only stat + streaming
  SHA-256).
- `persistence/source_media.py` — `SQLiteSourceMediaRepository` + `SQLiteSourceMediaCommandPersistence`
  (atomic `BEGIN IMMEDIATE` insert; identity + `UNIQUE(fingerprint_algorithm, fingerprint_digest)` uniqueness).
- `composition.py::compose_sqlite_media_import_service` — wires the inspector, repository, and persistence.
- `media_import_cli.py` — the `lectureos.media_import_cli` entry point.

## CLI

```bash
PYTHONPATH=src python3 -m lectureos.media_import_cli <source-path> --database <db-path>
```

Prints the canonical Media identity, the content fingerprint, the byte length, and whether the record was
`created` or an existing identical-content record was `reused`. The database is created if it does not exist.
Exit `0` on success; exit `1` on any error (with an explicit stderr message), leaving the database and the
source file unchanged.

## Persistence (schema v30)

```sql
CREATE TABLE source_media (
    identity TEXT PRIMARY KEY,
    fingerprint_algorithm TEXT NOT NULL CHECK (length(trim(fingerprint_algorithm)) > 0),
    fingerprint_digest TEXT NOT NULL CHECK (length(fingerprint_digest) = 64),
    byte_length INTEGER NOT NULL CHECK (byte_length > 0),
    observed_source_path TEXT NOT NULL CHECK (length(trim(observed_source_path)) > 0),
    UNIQUE (fingerprint_algorithm, fingerprint_digest)
)
```

The migration is strictly additive; every released version v1..v29 chains single-step to v30 preserving
existing rows, and downgrade / direct-skip / unsupported-target migrations are rejected.

## Validation

`validate_repository` adds a read-only `source_media` check: `MEDIA_FINGERPRINT_MALFORMED` (digest not 64
lowercase hex), `MEDIA_IDENTITY_FINGERPRINT_DISAGREEMENT` (identity not derived from the fingerprint), and
`MEDIA_FINGERPRINT_DUPLICATE` (a content fingerprint shared by more than one record). It never checks whether a
recorded source path still physically exists. See `implementation/070_REPOSITORY_VALIDATION.md`.

## Deferred

ffmpeg/ffprobe, codec/duration/resolution/stream extraction, audio extraction, transcoding, thumbnail/waveform,
playback, Whisper/transcription, remote/upload/object storage, provider adapters, background jobs, retries,
managed content-addressable storage as a subsystem, automatic source deletion, rendering, and media revision
history — all deferred (see `docs/045_MEDIA_IMPORT_PIPELINE.md` M-14).
