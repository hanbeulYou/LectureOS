# First Human Authority Decision on a Correction Candidate

- Status: Implementation Reference
- Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` §18 (first pre-revision candidate decision; GOAL-009) /
  `patches/PATCH-0025`
- Schema: v35 (one additive append-only table `correction_candidate_decisions`; reuses the v5
  `correction_candidates` records)

## Purpose

Answers exactly one question: **has a human explicitly accepted or rejected this correction candidate?** It is the
first explicit Human Authority layer for Transcript Correction. A suggestion is only evidence; authority exists
only when a human explicitly decides. This layer records that decision as an **append-only, immutable,
deterministic** fact — it applies nothing, mutates nothing, and creates no corrected revision.

## Authority lifecycle

Three states — **Undecided** (no decision record; derived by absence, never stored), **Accepted**, **Rejected**.
No Modify in this slice. Only Human Authority creates decisions (no LLM/rule/ASR/automation). Each decision
references exactly one admitted `CorrectionCandidate` (040 §17); all lineage derives through the candidate.

- **Append-only semantics** — INSERT-only; no UPDATE/DELETE. Each authority change is a new immutable row with a
  per-candidate `sequence` whose `previous_decision_id` supersedes the prior current row.
- **Current authority derivation** — the current decision is the highest-`sequence` row for the candidate, always
  derived from persisted state, never stored redundantly. History reconstruction depends only on persisted rows.
- **Eligibility** — only candidates whose current authority is **Accepted** are eligible for future
  corrected-revision generation (established here, not implemented). Rejected/Undecided are never eligible.

## Decision matrix

| Previous | New | Result (outcome) |
|----------|-----|------------------|
| None | Accept/Reject | Insert — `recorded` (sequence 0) |
| Accept | Accept | Reuse — `reused` |
| Reject | Reject | Reuse — `reused` |
| Accept | Reject | Append — `changed` (sequence + 1) |
| Reject | Accept | Append — `changed` (sequence + 1) |

## Identity, replay, conflict

Identity is deterministic from `(correction_candidate_id, kind, sequence)` (SHA-256) — no wall-clock/UUID/
randomness. Replay is idempotent (re-submitting the current kind reuses, no new row). Re-submitting the same
anchor with **different** provenance is a conflict, rejected without overwrite; a near-concurrent duplicate
converges. Provenance is the deciding `HumanActorReference` (reviewer) — no fake execution/RUNNING state.

## Reuse (GOAL-009 investigation)

Neither `application/transcript_review_decision.py` (§4.6/§4.7 — requires a revision + review preparation + RUNNING
execution + Modify) nor `review/models.py::ReviewDecision` (references a review-domain `CandidateReference` +
`ReviewItem`, not a `CorrectionCandidateId`) can reference an admitted §17 candidate without pulling in machinery
GOAL-009 forbids. So this is a **smallest additive aggregate**, reusing `review.models.DecisionKind` (accept/reject)
and `review.identities.HumanActorReference`, and the 040 §16 append-only supersession pattern. No second candidate
or review hierarchy is introduced.

## Architecture

- `application/correction_candidate_decision.py` — `CorrectionCandidateDecision`, `CorrectionCandidateAuthority`
  (derived), `HumanDecisionStatus` (undecided/accepted/rejected), `DecisionOutcome` (recorded/reused/changed),
  `CorrectionCandidateDecisionService`, typed errors, `derive_decision_identity`,
  `require_canonical_correction_candidate_id`, `require_decision_kind`.
- `persistence/correction_candidate_decision.py` — `SQLiteCorrectionCandidateDecisionRepository`
  (`is_admitted_candidate`, `get`, `get_current`, `history`) and
  `SQLiteCorrectionCandidateDecisionCommandPersistence` (one atomic `BEGIN IMMEDIATE` append with supersession
  validation).
- `composition.py::compose_sqlite_correction_candidate_decision_service`.
- `correction_candidate_decision_cli.py` — the `lectureos.correction_candidate_decision_cli` entry point (a thin
  application boundary with no authority logic).

## CLI

```bash
PYTHONPATH=src python3 -m lectureos.correction_candidate_decision_cli decide --candidate <id> --kind accept|reject --reviewer <who> [--rationale <text>] --database <db>
PYTHONPATH=src python3 -m lectureos.correction_candidate_decision_cli status  --candidate <id> --database <db>
PYTHONPATH=src python3 -m lectureos.correction_candidate_decision_cli history --candidate <id> --database <db>
```

Accepts identities (never paths). `decide` records a human accept/reject (there is no `--apply`), reports the
outcome (recorded/reused/changed) and the derived current authority, and states nothing was applied. `status`
reports undecided/accepted/rejected and revision eligibility; `history` lists the append-only decisions. Exit `0`
on success; `1` on malformed/unknown/unsupported/conflicting/missing input, leaving the repository unchanged.

## Persistence (schema v35)

```sql
CREATE TABLE correction_candidate_decisions (
    identity TEXT PRIMARY KEY,
    correction_candidate_id TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('accept', 'reject')),
    reviewer TEXT NOT NULL CHECK (length(trim(reviewer)) > 0),
    sequence INTEGER NOT NULL CHECK (sequence >= 0),
    previous_decision_id TEXT,
    rationale TEXT CHECK (rationale IS NULL OR length(trim(rationale)) > 0),
    content_fingerprint TEXT NOT NULL CHECK (length(content_fingerprint) = 64),
    UNIQUE (correction_candidate_id, sequence),
    CHECK ((sequence = 0 AND previous_decision_id IS NULL) OR
           (sequence > 0 AND previous_decision_id IS NOT NULL)),
    FOREIGN KEY (correction_candidate_id) REFERENCES correction_candidates(identity)
)
```

Append-only; current = `MAX(sequence)` per candidate. Strictly additive; every released version v1..v34 chains
single-step to v35 preserving rows, and downgrade / direct-skip / unsupported-target migrations are rejected.

## Validation

`validate_repository` adds read-only `correction_candidate_decisions` checks:
`CORRECTION_DECISION_DANGLING_CANDIDATE` (missing candidate), `CORRECTION_DECISION_SEQUENCE_NONCONTIGUOUS`
(per-candidate sequences not a contiguous 0..n-1 set), `CORRECTION_DECISION_BROKEN_SUPERSESSION` (a non-initial
decision does not supersede its candidate's immediately prior sequence). It checks **integrity only** — a
historical decision is never flagged as corruption merely because it is no longer applicable. See
`implementation/070_REPOSITORY_VALIDATION.md`.

## Deferred

Applying an accepted decision, corrected transcript revision generation, current corrected revision selection,
candidate Modify/merge/ensemble, ranking/recommended selection, automatic correction, LLM/rule engines, transcript
mutation, and subtitle/export/review-UI changes — all deferred (040 §18 H-14). This layer is the stable upstream
authority contract for GOAL-010, which consumes it without redesigning these semantics.
