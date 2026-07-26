# First Transcript Correction Candidate Admission

- Status: Implementation Reference
- Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` §17 (realizes §4.4 Correction, first slice) / `patches/PATCH-0024`
- Schema: v34 (one additive table `correction_candidate_admissions`; reuses the v5 `correction_candidates` records)

## What it is (and is not)

Records a **proposed** correction for one segment of the intake's **currently selected** Raw Transcript (040 §16)
**without applying it**. A Correction Candidate is a suggestion, not canonical transcript content.

- It **never** mutates Raw Transcript text, changes the current selection, creates a corrected revision or a
  candidate decision, implies acceptance, ranks candidates, triggers review, runs an LLM/ASR engine, or reads
  media.
- It reuses the existing canonical `CorrectionCandidate` (transcript domain, v5) — no second correction
  hierarchy — and binds it to its admission context (intake, target segment, immutable source-text snapshot,
  source metadata) with the additive v34 `correction_candidate_admissions` record.

## Admission flow

`CorrectionCandidateAdmissionService.admit(intake_id, candidate)`:

1. resolve the intake (malformed/unknown → error);
2. require **readiness** — a valid current Raw Transcript selection (`IntakeNotReadyError` otherwise);
3. require the target Raw Transcript to be that current selection (`RawTranscriptNotCurrentError`);
4. resolve the target segment and verify it belongs to the target Raw Transcript (`SegmentLineageError`);
5. verify the supplied `source_text_snapshot` equals the persisted segment text (`SourceTextMismatchError` —
   stale target);
6. reject empty and **no-op** proposed text;
7. derive deterministic identities + a content fingerprint; on an existing anchor, return reused or raise
   `CorrectionCandidateConflictError`;
8. persist atomically; return created/reused.

## Candidate input (strict JSON / native)

```json
{
  "raw_transcript_id": "raw-transcript:<digest>",       (must be the intake current selection)
  "segment_id": "transcript-segment:<digest>:<n>",
  "candidate_ref": "<distinguishes this suggestion>",
  "source_type": "manual | external | rule",
  "source_reference": "<who/what proposed it>",
  "model_reference": "<optional model/rule id>",
  "proposed_text": "<corrected text>",
  "source_text_snapshot": "<must equal the current segment text>",
  "rationale": "<why>"
}
```

Unknown fields are rejected. No confidence/quality/grammar-category/ranking/auto-approval fields.

## Identity, idempotency, and conflict

All identities are derived deterministically from the anchor `(intake, raw_transcript, segment, source_type,
source_reference, candidate_ref)` (SHA-256). Admission is idempotent by a content fingerprint over the full
payload; the same anchor with an identical payload returns reused; the same anchor with a **different** payload is
a conflict, rejected without overwrite. Multiple distinct suggestions per segment coexist via distinct
`candidate_ref`. No wall-clock/randomness participates.

## Provenance

External/manual: `source_type`, `source_reference`, `candidate_ref`, optional `model_reference`. Execution markers
(`run_id`/`unit_execution_id`/`domain_result_id`) are derived from the anchor (no internal RUNNING execution), and
the candidate's `DomainResultReference` (kind `transcript_correction_candidate`, upstream = the Raw Transcript's
domain result) is persisted, so an admitted candidate is structurally identical to a generated one.

## Staleness and applicability

Validity is anchored to the current Raw Transcript at admission time. After a later selection switch, existing
candidates remain immutable historical evidence — never deleted or retargeted — and are surfaced as no longer
**applicable** to the new current Raw Transcript. This is applicability/history, **not** repository corruption.

## Architecture

- `application/correction_candidate_admission.py` — `CorrectionCandidateInput` (+
  `build_correction_candidate_input`), `CorrectionCandidateSourceType`, `CorrectionCandidateAdmission`,
  `CorrectionCandidateAdmissionResult`, `CorrectionCandidateView`, `CorrectionCandidateAdmissionService`, typed
  errors, `require_canonical_segment_id`. Reuses the v5 `CorrectionCandidate` domain record.
- `persistence/correction_candidate_admission.py` — `SQLiteCorrectionCandidateAdmissionRepository` (get +
  `candidate` + `candidates_for_intake`) and `SQLiteCorrectionCandidateAdmissionCommandPersistence` (one atomic
  `BEGIN IMMEDIATE` writing the candidate + its `DomainResultReference` + the admission binding row, reusing the
  existing insert helpers).
- `composition.py::compose_sqlite_correction_candidate_admission_service`.
- `correction_candidate_cli.py` — the `lectureos.correction_candidate_cli` entry point.

## CLI

```bash
PYTHONPATH=src python3 -m lectureos.correction_candidate_cli admit --intake <id> --input <candidate.json> --database <db>
PYTHONPATH=src python3 -m lectureos.correction_candidate_cli list  --intake <id> --database <db>
```

`admit` records a suggestion (prints candidate/intake/raw/segment identities, source metadata, created/reused, and
"the correction candidate was NOT applied"); there is **no** `--apply` option. `list` shows admitted candidates
with applicability to the current selection — **not ranked**. Exit `0` on success; `1` on malformed/not-ready/
unrelated/stale/no-op/conflicting/missing input, leaving the repository unchanged.

## Persistence (schema v34)

```sql
CREATE TABLE correction_candidate_admissions (
    identity TEXT PRIMARY KEY,
    correction_candidate_id TEXT NOT NULL,
    transcript_source_intake_id TEXT NOT NULL,
    raw_transcript_id TEXT NOT NULL,
    segment_id TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK (source_type IN ('manual', 'external', 'rule')),
    source_reference TEXT NOT NULL CHECK (length(trim(source_reference)) > 0),
    candidate_ref TEXT NOT NULL CHECK (length(trim(candidate_ref)) > 0),
    model_reference TEXT,
    source_text_snapshot TEXT NOT NULL,
    content_fingerprint TEXT NOT NULL CHECK (length(content_fingerprint) = 64),
    UNIQUE (correction_candidate_id),
    FOREIGN KEY (correction_candidate_id) REFERENCES correction_candidates(identity),
    FOREIGN KEY (transcript_source_intake_id) REFERENCES transcript_source_intakes(identity),
    FOREIGN KEY (raw_transcript_id) REFERENCES raw_transcripts(identity),
    FOREIGN KEY (segment_id) REFERENCES transcript_segments(identity)
)
```

The migration is strictly additive; every released version v1..v33 chains single-step to v34 preserving rows, and
downgrade / direct-skip / unsupported-target migrations are rejected.

## Validation

`validate_repository` adds read-only `correction_candidate_admissions` checks:
`CORRECTION_CANDIDATE_DANGLING_CANDIDATE`/`_DANGLING_INTAKE`/`_DANGLING_RAW_TRANSCRIPT`/`_DANGLING_SEGMENT`
(broken references), `_RAW_TRANSCRIPT_NOT_IN_INTAKE`, `_SEGMENT_NOT_IN_RAW_TRANSCRIPT`, `_SOURCE_TEXT_DISAGREEMENT`
(snapshot drifted from the segment text), `_ADMISSION_LINEAGE_DISAGREEMENT` (candidate transcript/segment disagree
with the admission), and `_EMPTY_PROPOSED_TEXT`. It does **not** diagnose a historical candidate as corruption
merely because a different Raw Transcript is currently selected. See `implementation/070_REPOSITORY_VALIDATION.md`.

## Deferred

Candidate acceptance/rejection/modification, ranking/recommended selection, automatic correction, LLM/grammar/
punctuation/dictionary engines, corrected transcript revision, current corrected revision selection, transcript
validation, review, subtitle/export/rendering changes, ASR changes, additional adapters, and provider registries
— all deferred (040 §17 K-14). No placeholders are introduced.
