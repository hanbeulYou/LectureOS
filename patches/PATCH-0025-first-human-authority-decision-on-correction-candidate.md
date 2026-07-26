# PATCH-0025

- Title: First Human Authority Decision on a Correction Candidate (First Slice) (040)
- Status: Accepted
- Priority: Medium
- Trigger: Architect / Product Owner Decision (GOAL-009 — first Human Authority layer for Transcript Correction)
- Created: 2026-07-26
- Target Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` (§4.4/§4.6/§4.7 — first pre-revision candidate decision)

---

## Status

Accepted. Establishes the first **Human Authority** decision on an admitted Transcript Correction Candidate
(040 §17): whether a human explicitly **accepts** or **rejects** it. It is an authority record only — it applies
nothing, creates no corrected revision, and mutates no candidate or Raw Transcript. Introduces one additive
append-only record — the **Correction Candidate Decision** — at schema **v35**. It reuses the canonical
`CorrectionCandidate` (v5) and the Review domain's `DecisionKind`/`HumanActorReference` value types; it introduces
no second candidate or review hierarchy.

## Trigger

Correction Candidate Admission (040 §17, PATCH-0024) records proposed corrections as immutable evidence. A
suggestion is not authority — authority exists only when a human explicitly decides. GOAL-009 requires the first
explicit Human Authority layer for correction candidates, which future corrected-revision generation (GOAL-010)
will depend on as a stable upstream contract. A bounded Product decision settled it and this PATCH promotes it.

## Reuse investigation (required by GOAL-009)

- **`application/transcript_review_decision.py` (§4.6/§4.7)** records Accept/Reject/Modify, but **requires** a
  `ReviewPreparation` + `ReviewItem` + `CandidateReference` + a **`source_revision_id` (corrected transcript
  revision)** + a **RUNNING unit execution** + a decision timestamp. GOAL-009 forbids revision context, fake/
  RUNNING execution, and Modify, and requires the decision to reference the correction candidate directly — so it
  is **not reusable** for this pre-revision candidate decision.
- **`review/models.py::ReviewDecision`** is lean and append-only but references a review-domain
  `CandidateReferenceId` + a required `ReviewItemId`, not a `CorrectionCandidateId`; reusing it would require
  wrapping each §17 candidate in a `CandidateReference`/`ReviewItem` — a **second candidate hierarchy / duplicated
  lineage**, which GOAL-009 forbids.
- **Reused value types**: `review.models.DecisionKind` (accept/reject) and `review.identities.HumanActorReference`
  (reviewer). No parallel value types are introduced.
- **Reused pattern**: the append-only supersession model (per-candidate `sequence` + `previous_decision_id`,
  current = highest sequence, deterministic identity) already established by 040 §16 (PATCH-0023).

## Relationship to the existing Review path

The existing §4.6/§4.7 review path reviews candidates **within a corrected-revision review preparation**
(post-revision). This slice records a distinct, **pre-revision** Human Authority: deciding accept/reject on an
admitted correction candidate, which determines eligibility for future revision generation. §4.6 explicitly
leaves it **unconfirmed** whether every correction needs a Review Item ("모든 변경이 반드시 독립된 Review Item을
가져야 하는지는 이 문서에서 확정하지 않는다"; §11 marks it "Requires Validation"). This slice resolves that open
question in the smallest additive way — a decision may be recorded directly on a candidate — without weakening
§4.6/§4.7. No confirmed contract is contradicted.

## First-Slice Product Decision

### Question and states

Answers exactly one question: *has a human explicitly accepted or rejected this correction candidate?* Only three
states exist — **Undecided** (no decision record; derived by **absence**, never stored), **Accepted**,
**Rejected**. No other states; **Modify is deferred**.

### Authority, ownership, and immutability

Only Human Authority creates decisions (no LLM/rule/ASR/automation). One decision references **exactly one**
admitted `CorrectionCandidate`; all lineage is derived through the candidate — no duplicated lineage is persisted.
A decision **never** mutates the candidate, the Raw Transcript, any segment, or the current selection, and creates
no corrected revision, no candidate decision beyond itself, and applies nothing.

### Append-only history and derived current authority

History is **append-only** (INSERT-only; no UPDATE/DELETE): each authority change is a new immutable record with a
per-candidate `sequence` whose `previous_decision_id` supersedes the prior current record. The **current**
authority is the highest-`sequence` record, always **derived** from persisted state, never stored redundantly.
History reconstruction depends only on persisted rows.

### Deterministic identity, replay, and conflict

Identity is deterministic from `(correction_candidate_id, kind, sequence)` (SHA-256) — no wall-clock, UUID,
randomness, path, or process identity. The decision matrix is normative:

| Previous | New | Result |
|----------|-----|--------|
| None | Accept | Insert (sequence 0) |
| None | Reject | Insert (sequence 0) |
| Accept | Accept | **Reuse** (authority already this kind) |
| Reject | Reject | **Reuse** |
| Accept | Reject | **Append** (sequence + 1) |
| Reject | Accept | **Append** (sequence + 1) |

Replay is idempotent (submitting the current kind again reuses, no new record). A re-submission of the same anchor
with **different** provenance (content) is a **conflict**, rejected without overwrite. A near-concurrent duplicate
converges.

### Provenance and eligibility

Each decision preserves deterministic provenance: the deciding `HumanActorReference` (reviewer), the candidate, the
judgement kind, and its place in history (`sequence`/`previous`). No fake execution rows, synthetic Processing
Run, or RUNNING state. **Only** candidates whose current authority is **Accepted** are eligible for future
corrected-revision generation; Rejected and Undecided are never eligible. This eligibility is established here, not
implemented — GOAL-010 consumes it without redesigning these authority semantics.

### Staleness vs integrity, and failure atomicity

A decision never becomes repository corruption; it may become historically non-applicable (that is query/
applicability semantics, not integrity). Repository validation checks integrity only. Every decision operation is a
single atomic transaction; any failure leaves no partial authority state and mutates nothing upstream.

## Explicit Deferred Scope

Applying an accepted decision, corrected transcript revision generation, current corrected revision selection,
candidate Modify, candidate merge/ensemble, ranking/recommended selection, automatic correction, LLM/rule/grammar/
punctuation/dictionary engines, transcript mutation, subtitle/export/rendering changes, and review UI — all
deferred. No placeholders are introduced.

## Consequences

- 040 gains a confirmed first pre-revision Human Authority contract (`040 §18`) between §17 (candidate admission)
  and future revision generation; §4.6/§4.7 remain intact for the revision-scoped review path.
- Schema advances additively to **v35** (one new append-only table `correction_candidate_decisions`); the v5
  `correction_candidates` records are reused unchanged; every released version v1..v34 reaches v35 through the
  supported single-step chain with no data loss.
- Correction Candidate Admission (§17), Current Raw Transcript Selection (§16), Raw Transcript identity, and the
  existing Review architecture are unchanged.
