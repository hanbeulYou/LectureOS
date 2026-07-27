# Effective SRT Physical Materialization

- Status: Implementation Reference
- Blueprint: the released record-first materialization discipline (044 §17 / PATCH-0007) + the
  hardened released local writer, applied to GOAL-017 logical artifacts (GOAL-018); no new
  Blueprint PATCH required
- Schema: v44 (two additive insert-only tables `subtitle_effective_srt_materializations` /
  `subtitle_effective_srt_materialization_outcomes`)

## Purpose

The physical materialization boundary of the effective-transcript subtitle contract generation:
an explicit request realizes one exact logical `EffectiveSubtitleSrtArtifact` payload as a
physical file beneath one approved Storage Root.

```text
logical artifact → explicit materialize(artifact, location?, overwrite?)
                → immutable intent (PENDING, durable BEFORE the write)
                → contained atomic file write (exact canonical bytes: UTF-8, LF, no BOM)
                → immutable terminal outcome (MATERIALIZED | FAILED)
```

**Artifact ≠ Materialization ≠ delivery.** Artifact identity never depends on any path; the
relative location is operational provenance of one write event; a later deleted or diverged file
never mutates any record — filesystem state and logical history are separate. No delivery,
publication, upload, or URL exists here.

## Record-first lifecycle (released discipline, reused)

State is derived, never stored: an intent without an outcome is PENDING (an honest crash residue,
completed — not duplicated — by the next explicit request); write failures (collision,
containment escape, I/O) are honest FAILED outcomes, never hidden exceptions and never silent
retries. Identity is deterministic: `subtitle-effective-srt-materialization:<sha256(artifact,
relative location, per-pair sequence)>` — one immutable record per write attempt; append-only
supersession (`UNIQUE(artifact, location, sequence)` + validated previous linkage).

## Writer (released hardened writer, extended additively)

`LocalEffectiveSrtFileWriter` subclasses the released `LocalSrtFileWriter` unchanged: approved
absolute root, symlink rejection, containment resolution, atomic temp-file + fsync + link
discipline, identical-bytes idempotence, different-bytes refusal. The only addition is an explicit
``replace`` (used solely for an explicit ``overwrite=True`` request) that atomically replaces an
existing regular file — foreign non-regular objects are still refused.

## Replay and overwrite policy

- Replay: latest act MATERIALIZED + fingerprint matches + the file still holds the exact payload
  → **reused**, no rewrite, no new record.
- Existing different file, no overwrite → FAILED outcome recorded, file untouched (default
  `overwrite = false`).
- Explicit overwrite → a NEW append-only write event (sequence+1) atomically replaces the file.
- Deleted file → records immutable; a new explicit request re-realizes the payload as sequence+1.

## Architecture

- `application/effective_srt_materialization.py` — models, deterministic identity, default
  location policy (`<artifact-id>.srt`), `EffectiveSrtMaterializationService`
  (materialize / get / state / outcome / file_matches / list_for_artifact), typed errors.
- `persistence/effective_srt_materialization.py` — repository + the two atomic transactions of
  the record-first lifecycle.
- `infrastructure/local_effective_srt_file_writer.py` — the released writer + explicit replace.
- `composition.py::compose_sqlite_effective_srt_materialization_service(connection, storage_root)`.
- `effective_materialize_cli.py` — the `lectureos.effective_materialize_cli` entry point.

## CLI

```bash
PYTHONPATH=src python3 -m lectureos.effective_materialize_cli materialize --artifact <id> --storage-root <dir> [--location <rel>] [--overwrite] --database <db>
PYTHONPATH=src python3 -m lectureos.effective_materialize_cli show --materialization <id> --storage-root <dir> --database <db>
PYTHONPATH=src python3 -m lectureos.effective_materialize_cli status --materialization <id> --storage-root <dir> --database <db>
PYTHONPATH=src python3 -m lectureos.effective_materialize_cli list --artifact <id> --storage-root <dir> --database <db>
```

A FAILED write outcome exits 1 while the honest record remains. Output always distinguishes
artifact / materialization / physical path and states `delivery state: not part of this contract`.

## Persistence (schema v44)

Two insert-only tables: intents (identity PK; artifact FK; storage kind CHECK `local_file`; safe
relative location; 64-hex payload fingerprint — validated against the artifact; per-pair
`UNIQUE(artifact, location, sequence)`; supersession CHECKs) and outcomes (materialization PK/FK;
state CHECK `materialized|failed` with byte_length/failure_reason exclusivity). Every released
version v1..v43 chains single-step to v44 preserving all rows; new tables start empty;
downgrade/direct-skip/unsupported-target rejected.

## Validation (integrity only)

Six `EFFECTIVE_SRT_MATERIALIZATION_*` codes: dangling artifact, payload-fingerprint disagreement,
identity re-derivation, per-pair sequence contiguity, broken supersession, orphan outcome.
Deliberately never flagged: PENDING intents, FAILED outcomes, missing or diverged physical files,
stale/superseded artifacts — a repository whose materialized file was deleted validates healthy
(tested). See `implementation/070_REPOSITORY_VALIDATION.md`.

## Deferred (later goals)

Delivery, publication, download/upload, URL generation, archive management, and any workflow
beyond the write event. The effective-source pipeline is now complete through a user-visible
`.srt` file; further goals should move beyond subtitle generation itself.
