# Current Raw Transcript Selection and Downstream Readiness

- Status: Implementation Reference
- Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` §16 (between §4.3 and §4.4) / `patches/PATCH-0023`
- Schema: v33 (one additive append-only table `current_raw_transcript_selections`)

## What it is (and is not)

Decides **which admitted `RawTranscript` is the current authoritative downstream input for a
`TranscriptSourceIntake`**, and whether the intake is **ready** to begin downstream Correction. A single intake
may hold several admitted Raw Transcripts (040 §14/§15); this slice selects one.

- Selection is an **explicit repository authority** decision — never inferred from provider name, model size,
  wall-clock, transcript length, or confidence, and **no candidate is ranked or labelled "best"**.
- It **does not** compare ASR quality, alter Raw Transcript content, delete non-selected transcripts, or run
  Correction (Correction is not implemented here). No transcript / provider result / Source Media / intake row is
  mutated.
- Candidates are exactly the intake's admitted Raw Transcripts, read from `provider_transcript_admissions`,
  enumerated deterministically by identity.

## Authority model

- **Explicit initial selection** — admitting a provider result does not auto-select it (Provider Transcript
  Admission is unchanged); readiness stays `not_ready` until an explicit selection.
- **Append-only supersession** — each selection is an immutable row with a per-intake `sequence` (0-based) whose
  `previous_selection_id` supersedes the prior current row. The **current** selection is the highest-`sequence`
  row for the intake (ordered by `sequence`, never wall-clock). Switching appends a new row (`sequence` + 1) and
  preserves all prior rows.
- **Idempotent** — selecting the already-current Raw Transcript returns `reused` with no new row; a near-concurrent
  duplicate converges on the existing current selection.
- **Deterministic identity** — `raw-transcript-selection:<sha256(intake, raw_transcript, sequence)>`.

## Readiness

Derived from current persisted facts (not persisted itself): `not_ready` (no current selection), `ready` (a valid
current Raw Transcript is selected), `error` (the persisted current selection is inconsistent — its Raw Transcript
is no longer an admitted candidate of the intake). Never depends on source-file existence, ASR/provider
availability, model accuracy, confidence, or review. Later admissions never silently replace the current
selection, so a newer admission does not make it stale.

## Architecture

- `application/current_raw_transcript_selection.py` — `CurrentRawTranscriptSelection`, `RawTranscriptCandidate`,
  `TranscriptIntakeReadiness`/`TranscriptIntakeReadinessReport`, `SelectionOutcome`,
  `CurrentRawTranscriptSelectionService`, `RawTranscriptSelectionError`, `derive_selection_identity`,
  `require_canonical_raw_transcript_id`, and the candidate / selection / persistence ports.
- `persistence/current_raw_transcript_selection.py` — `SQLiteRawTranscriptSelectionRepository` (candidates +
  `owning_intake` + `get`/`get_current`) and `SQLiteRawTranscriptSelectionCommandPersistence` (one atomic
  `BEGIN IMMEDIATE` append with supersession validation).
- `composition.py::compose_sqlite_current_raw_transcript_selection_service`.
- `raw_transcript_selection_cli.py` — the `lectureos.raw_transcript_selection_cli` entry point.

## CLI

```bash
PYTHONPATH=src python3 -m lectureos.raw_transcript_selection_cli candidates --intake <id> --database <db>
PYTHONPATH=src python3 -m lectureos.raw_transcript_selection_cli select --intake <id> --transcript <rt> --database <db> [--reason <text>]
PYTHONPATH=src python3 -m lectureos.raw_transcript_selection_cli readiness --intake <id> --database <db>
```

Accepts intake and Raw Transcript identities (never paths). `candidates` lists each candidate's provider/model
metadata (marking the current one) — **not ranked**. `select` reports `created`/`reused`/`switched`, the
superseded transcript (on a switch), and readiness. `readiness` reports the state, candidate count, and current
selection. Exit `0` on a successful query or valid selection; `1` on malformed/unknown/unrelated/dangling input,
leaving the repository unchanged.

## Persistence (schema v33)

```sql
CREATE TABLE current_raw_transcript_selections (
    identity TEXT PRIMARY KEY,
    transcript_source_intake_id TEXT NOT NULL,
    raw_transcript_id TEXT NOT NULL,
    sequence INTEGER NOT NULL CHECK (sequence >= 0),
    previous_selection_id TEXT,
    reason TEXT CHECK (reason IS NULL OR length(trim(reason)) > 0),
    UNIQUE (transcript_source_intake_id, sequence),
    CHECK ((sequence = 0 AND previous_selection_id IS NULL) OR
           (sequence > 0 AND previous_selection_id IS NOT NULL)),
    FOREIGN KEY (transcript_source_intake_id) REFERENCES transcript_source_intakes(identity),
    FOREIGN KEY (raw_transcript_id) REFERENCES raw_transcripts(identity)
)
```

Append-only; the current selection is `MAX(sequence)` per intake. The migration is strictly additive; every
released version v1..v32 chains single-step to v33 preserving rows, and downgrade / direct-skip /
unsupported-target migrations are rejected.

## Validation

`validate_repository` adds read-only `current_raw_transcript_selections` checks:
`RAW_TRANSCRIPT_SELECTION_DANGLING_INTAKE` / `_DANGLING_RAW_TRANSCRIPT` (broken references),
`RAW_TRANSCRIPT_SELECTION_LINEAGE_MISMATCH` (selected transcript is not an admitted candidate of the intake),
`RAW_TRANSCRIPT_SELECTION_SEQUENCE_NONCONTIGUOUS` (per-intake sequences not a contiguous 0..n-1 set),
`RAW_TRANSCRIPT_SELECTION_BROKEN_SUPERSESSION` (a non-initial selection does not supersede its intake's
immediately prior sequence). None check ASR/model availability or source-file existence. See
`implementation/070_REPOSITORY_VALIDATION.md`.

## Deferred

Transcript correction and candidates, structural validation, review, automatic scoring/ranking, model/provider
comparison, automatic best-transcript selection, merging/ensemble, word-level alignment, diarization,
subtitle/export/rendering changes, queues, retries, progress, cloud ASR, additional adapters, provider
registries, and generic workflow status engines — all deferred (040 §16 R-13). No placeholders are introduced.
