# PATCH-0024

- Title: First Transcript Correction Candidate Admission (First Slice) (040)
- Status: Accepted
- Priority: Medium
- Trigger: Architect / Product Owner Decision (first correction candidate admission against the current Raw Transcript)
- Created: 2026-07-26
- Target Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` (§4.4 Correction — first application slice)

---

## Status

Accepted. Establishes the first application contract for recording a **proposed** correction against one segment
of the **currently selected** Raw Transcript (040 §16) **without applying it**. It reuses the existing canonical
`CorrectionCandidate` (transcript domain, schema v5) as the suggestion record and binds it to its admission
context with one additive record — the **Correction Candidate Admission** — at schema **v34**. It creates no
corrected revision, no candidate decision, and no acceptance; it never mutates Raw Transcript text, the current
selection, or ranks candidates.

## Trigger

Current Raw Transcript Selection (040 §16, PATCH-0023) established the single downstream input per intake and a
readiness gate, but §4.4 Correction was unimplemented: LectureOS could not record even a proposed correction. The
first Correction slice is the smallest capability that records suggestions as immutable evidence while preserving
Human Authority (nothing is applied). A bounded Product decision settled that admission and this PATCH promotes
it.

## Context

The existing `CorrectionCandidate` was designed for internal generation (execution-provenance carrying, targeting
a transcript/revision). This slice admits an **externally or manually** produced candidate against the current
Raw Transcript segment — mirroring the External ASR Boundary admission (PATCH-0021): the canonical record is
reused, external provenance markers are derived (no fake internal RUNNING execution), and an additive admission
record binds the candidate to its intake, target segment, source-text snapshot, and source metadata. A
Correction Candidate is a suggestion — never canonical transcript content, and never a trigger for review,
decision, or revision.

## First-Slice Product Decision

### Target and lineage

A candidate targets **one immutable Raw Transcript segment**. Admission requires the intake to be **ready** (a
valid current Raw Transcript selection) and the target Raw Transcript to be **that current selection**; the target
segment must belong to that Raw Transcript, which must belong to the intake. Unknown, unrelated, malformed, or
stale references are rejected explicitly.

### Proposed text and source snapshot

`proposed_text` is required, non-blank, and preserved exactly (Korean/non-ASCII preserved); a **no-op** candidate
(proposed text equal to the source text) is rejected. A **source-text snapshot** is required and must equal the
persisted segment text at admission time (stale detection). Admission **never** changes the Raw Transcript text —
the segment remains immutable evidence.

### Provenance and source type

Provenance is external/manual: a `source_type` (`manual` | `external` | `rule`), a non-blank `source_reference`
(who/what proposed it), a required `candidate_ref` discriminator, and an optional `model_reference`. Execution
markers (`run_id`/`unit_execution_id`/`domain_result_id`) are derived deterministically from the anchor — no
internal RUNNING execution is created — and the candidate's `DomainResultReference` (kind
`transcript_correction_candidate`, upstream = the Raw Transcript's domain result) is persisted, so an admitted
candidate is structurally identical to a generated one. Candidate **source** is kept distinct from candidate
**authority**: admission implies no acceptance.

### Identity, idempotency, and conflict

All identities are derived deterministically from the anchor `(intake, raw_transcript, segment, source_type,
source_reference, candidate_ref)` (SHA-256). Admission is idempotent by a content fingerprint over the full
payload (proposed text, snapshot, rationale, model); re-admitting the same anchor with an identical payload
returns the existing records, and re-admitting the same anchor with a **different** payload is a **conflict**,
rejected without overwrite. **Multiple distinct** suggestions may coexist for one segment (distinct
`candidate_ref`). No wall-clock/randomness defines identity.

### Staleness and applicability

Candidate validity is anchored to the selected Raw Transcript **at admission time**. After a later
current-Raw-Transcript switch, existing candidates remain **immutable historical evidence**: they are never
deleted, never retargeted to another transcript, and are surfaced as no longer **applicable** to the new current
Raw Transcript. A historical candidate is **not** repository corruption merely because a different Raw Transcript
is now selected — that is applicability/history, not integrity.

### Failure atomicity and authority

Admission is a single atomic transaction; any failure leaves no partial candidate, provenance, or admission
state and mutates neither the Raw Transcript, the current selection, the Source Media, nor the intake. Admission
does not produce a corrected revision, create a candidate decision, imply acceptance, rank competing candidates,
or trigger review.

## Explicit Deferred Scope

Candidate acceptance / rejection / modification, ranking / recommended selection, automatic correction, LLM /
grammar / punctuation / dictionary engines, corrected transcript revision, current corrected revision selection,
transcript validation, review, subtitle/export/rendering changes, ASR changes, additional adapters, and provider
registries — all deferred. No placeholders are introduced.

## Consequences

- 040 §4.4 gains a confirmed first-slice Correction Candidate admission contract (`040 §17`).
- Schema advances additively to **v34** (one new table `correction_candidate_admissions`); the v5
  `correction_candidates` records are reused unchanged; every released version v1..v33 reaches v34 through the
  supported single-step chain with no data loss.
- Current Raw Transcript Selection, Provider Transcript Admission, Raw Transcript identity, and the §4.8
  corrected current selection are unchanged; no second correction hierarchy is introduced.
