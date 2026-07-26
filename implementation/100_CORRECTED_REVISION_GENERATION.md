# First Corrected Transcript Revision — One-Candidate Explicit Application

- Status: Implementation Reference
- Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` §19 (first application of §4.4; GOAL-010) / `patches/PATCH-0026`
- Schema: v36 (one additive table `corrected_revision_generations`; reuses the v5
  `corrected_transcript_revisions` / segment / domain-result records unchanged)

## Purpose

Applies exactly **one currently Accepted** Correction Candidate (§17/§18) to its authoritative source Raw
Transcript and persists the result as one **immutable** canonical `CorrectedTranscriptRevision`:

```text
Current Raw Transcript + Accepted Candidate + Current Human Authority
    → explicit Generate → immutable Corrected Transcript Revision
```

Acceptance authorizes; generation applies — separate boundaries. Accepting never creates a revision; the
generated revision is **never** selected as current (GOAL-011). Nothing mutates the Raw Transcript, the
candidate, the decision history, or the current Raw Transcript selection.

## Generation flow

`CorrectedRevisionGenerationService.generate(candidate_id)`:

1. resolve the candidate through its §17 admission (its own authoritative lineage);
2. require the candidate's **current** §18 authority to be Accepted (`CandidateNotAcceptedError` for
   Undecided/Rejected — historical acceptance is insufficient);
3. verify structural applicability (`CandidateNotApplicableError`): the candidate's Raw Transcript is the
   intake's current selection; the target segment belongs to it; the persisted segment text equals the
   candidate's source-text snapshot (stale detection — never fuzzy-matched or rebased);
4. derive the deterministic anchor `(candidate, authorizing_accepted_decision)`; on an existing anchor return
   reused or raise `CorrectedRevisionConflictError` (content diverged — no overwrite);
5. apply deterministically: one new replacement `TranscriptSegment` (candidate's exact proposed text;
   `replaces_segment_id` → source segment; timing/order/timeline/speaker preserved), all unaffected segments
   referenced unchanged;
6. persist atomically; return created/reused.

## Representation (reused v5 contract)

The revision is a **complete snapshot via ordered segment references** — the repository's established corrected-
transcript representation, not a patch: unchanged source segments retain their identities; the corrected segment
is a new revision-scoped segment carrying `replaces_segment_id`; `parent_raw_transcript_id` anchors the parent;
`correction_candidate_ids = (candidate,)`; `applicability` stays `undetermined` (no current-flag). Corrected-text
provenance stays human (candidate/decision lineage); provider provenance stays on the source segments. The
`DomainResultReference` (kind `corrected_transcript_revision`, upstream = the raw transcript's domain result)
preserves §6.2 provenance; execution markers are derived (no RUNNING execution, no fake Processing Run).

## Identity, replay, conflict, authority change

All identities derive from SHA-256 of `(candidate, authorizing_decision)` — no wall-clock/UUID/randomness.
Identical replay reuses (after restart, from the CLI, and under near-concurrent duplicates). Distinct authorizing
Accepted Decisions (Accept#1 vs Accept#2 after a Reject) yield **distinct revisions** (immutable records cannot
acquire new provenance); entity identity ≠ content identity — a content fingerprint (order/text/timing, no
entity ids) records that such revisions may carry identical content. `Accept → Generate → Reject` leaves the
revision persisted, immutable, and queryable; the Reject only blocks new generation.

## Architecture

- `application/corrected_revision_generation.py` — `CorrectedRevisionGeneration`, generation result/outcome,
  `CorrectedRevisionGenerationService`, typed errors, `derive_generation_digest`, `content_fingerprint_for`.
- `persistence/corrected_revision_generation.py` — repository (get / revision / generations_for_candidate) and
  one atomic `BEGIN IMMEDIATE` command persistence reusing the v5 insert helpers.
- `composition.py::compose_sqlite_corrected_revision_generation_service`.
- `corrected_revision_cli.py` — the `lectureos.corrected_revision_cli` entry point.

## CLI

```bash
PYTHONPATH=src python3 -m lectureos.corrected_revision_cli generate --candidate <id> --database <db>
PYTHONPATH=src python3 -m lectureos.corrected_revision_cli show --revision <id> --database <db>
PYTHONPATH=src python3 -m lectureos.corrected_revision_cli list --candidate <id> --database <db>
```

`generate` reports the revision/candidate/authorizing-decision/source identities, created/reused, and that the
revision was **not** selected as current. No `--force`, `--apply-all`, `--auto`, `--best`, or `--select`. Exit
`0` on success; `1` on undecided/rejected/stale/unknown/conflicting input, leaving the repository unchanged.

## Persistence (schema v36)

```sql
CREATE TABLE corrected_revision_generations (
    identity TEXT PRIMARY KEY,
    corrected_revision_id TEXT NOT NULL,
    correction_candidate_id TEXT NOT NULL,
    authorizing_decision_id TEXT NOT NULL,
    parent_raw_transcript_id TEXT NOT NULL,
    replaced_segment_id TEXT NOT NULL,
    replacement_segment_id TEXT NOT NULL,
    content_fingerprint TEXT NOT NULL CHECK (length(content_fingerprint) = 64),
    UNIQUE (corrected_revision_id),
    UNIQUE (correction_candidate_id, authorizing_decision_id),
    CHECK (replaced_segment_id <> replacement_segment_id),
    FOREIGN KEY (corrected_revision_id) REFERENCES corrected_transcript_revisions(identity),
    FOREIGN KEY (correction_candidate_id) REFERENCES correction_candidates(identity),
    FOREIGN KEY (authorizing_decision_id) REFERENCES correction_candidate_decisions(identity),
    FOREIGN KEY (parent_raw_transcript_id) REFERENCES raw_transcripts(identity),
    FOREIGN KEY (replaced_segment_id) REFERENCES transcript_segments(identity),
    FOREIGN KEY (replacement_segment_id) REFERENCES transcript_segments(identity)
)
```

Strictly additive; every released version v1..v35 chains single-step to v36 preserving rows; downgrade /
direct-skip / unsupported-target migrations are rejected. No existing table altered; no cascade deletion.

## Validation (integrity vs applicability)

`validate_repository` adds read-only checks: `CORRECTED_REVISION_DANGLING_REVISION`/`_DANGLING_CANDIDATE`/
`_DANGLING_DECISION`/`_DANGLING_PARENT`, `CORRECTED_REVISION_AUTHORIZING_DECISION_NOT_ACCEPT` (the **specific
authorizing decision** must be an Accept — the candidate's *current* authority is deliberately not checked, so a
historical revision after a later Reject is never corruption), `CORRECTED_REVISION_DECISION_CANDIDATE_MISMATCH`,
`CORRECTED_REVISION_PARENT_MISMATCH`, and `CORRECTED_REVISION_MEMBERSHIP_DISAGREEMENT` (revision must contain
the replacement and not the replaced segment). No linguistic checks. See
`implementation/070_REPOSITORY_VALIDATION.md`.

## Deferred (GOAL-011+)

Current Corrected Revision Selection, multiple-candidate application/merge, overlap resolution, revision
chaining (modeled by the existing `parent_revision_id`, unused here), ranking, automatic/LLM correction,
linguistic validation, mutable editing, segment deletion/splitting/merging, timing correction, subtitle
regeneration, and export changes. No placeholders are introduced.
