# PATCH-0029

- Title: Effective-Transcript-Sourced Subtitle Candidate Contract (041/040)
- Status: Accepted
- Priority: High
- Trigger: Architect Decision (GOAL-013 Architect Decision Gate — documentation-only resolution)
- Created: 2026-07-26
- Target Blueprint: `docs/041_SUBTITLE_PIPELINE.md` (new §15; §4.2 legacy-generation qualification),
  `docs/040_TRANSCRIPT_PIPELINE.md` (§21 downstream-consumer cross-reference)

---

## Status

Accepted. **Documentation only.** This PATCH encodes the Architect Decision that unblocks GOAL-013. It adds no
implementation, no schema change, no migration, no application code, and creates no subtitle candidates. The
SQLite schema remains **v38**.

## Context

GOAL-009…GOAL-012 established the §13–§21 transcript chain: Human Authority Decisions, immutable Corrected
Revisions, explicit append-only Current Corrected Revision Selection with the deterministic effective-transcript
resolver, and the Effective Transcript Consumption Boundary (040 §21 / PATCH-0028) — the sole boundary through
which downstream operations acquire one immutable transcript source with exact identity, Raw parent lineage,
authority provenance, ordered snapshot, and content fingerprint.

GOAL-013 intended to make subtitle generation the first real product consumer of that boundary:

```text
Effective Transcript Consumption Binding
↓
Explicit Subtitle Generation
↓
Immutable Subtitle Candidate and Cue Set
↓
Exact Transcript Source Lineage
```

## Trigger

The GOAL-013 implementation agent correctly stopped at the Architect Decision Gate: the current Blueprint and
the released subtitle persistence contract cannot simultaneously support Raw-sourced candidates,
Corrected-sourced candidates, GOAL-012 as the sole acquisition boundary, reuse of the released candidate
representation, additive-only migration, no fabricated provenance, and no competing canonical representation.

## Problem

- The released legacy relation (`subtitle_candidates`, schema v12; 041 §4.2 first slice) hard-requires legacy
  lineage as NOT NULL: ELIGIBLE `SubtitleTranscriptIntake`, `TranscriptReadinessEvaluation`, legacy
  `TranscriptCurrentSelection` (§4.8), `TranscriptApplicabilityEvaluation`, `TranscriptReviewDecision`,
  `ReviewItem`, `CandidateReference`, structural `Validation`, and a RUNNING `ProcessingRun`/`UnitExecution`.
  None of these can be truthfully derived from the §13–§21 chain, which deliberately creates no legacy review,
  authority, validation, or execution objects. Integration would require fabricated provenance — prohibited.
- The released relation assumes a Corrected Transcript Revision source (`source_revision_id NOT NULL`) and has
  no source-kind concept: a **Raw Transcript source is unrepresentable**, while the effective transcript may
  legitimately be Raw (no corrected history, or explicit Raw fallback).
- Additive-only migration forbids relaxing released NOT NULL columns; the earlier in-memory subtitle domain
  model (`SubtitleCandidate`/`SubtitleCue` semantics) is not the canonical persisted representation used by the
  current review/decision/final-selection/export pipeline.

## Architect Decision

Seven decisions, encoded normatively in `041 §15` (and cross-referenced from `040 §21`):

1. **New canonical representation for the GOAL-012 pipeline.** Effective-transcript-sourced Subtitle Candidates
   use a **new additive, versioned persisted representation** (a likely persistence family is
   `subtitle_effective_candidates` / `subtitle_effective_candidate_cues` /
   `subtitle_effective_candidate_cue_segments`; the implementation goal may select more repository-consistent
   names). It is **canonical** for the effective-transcript-sourced pipeline — not a temporary adapter, not a
   shadow table. The released legacy representation remains canonical only for its legacy pipeline.
2. **Legacy records remain valid historical records.** Existing candidates are never rewritten, backfilled,
   reinterpreted as GOAL-012-sourced, assigned fabricated bindings or source kinds, migrated without truthful
   historical evidence, deleted, or silently superseded. The two representations are permanently
   distinguishable **by contract generation**; their coexistence is an intentional versioned architecture
   boundary. No competing canonical representation exists **within one contract generation**; any prior wording
   requiring a single physical representation across all historical generations is superseded.
3. **Semantic reuse, not column reuse.** Reusing `SubtitleCandidate`/`SubtitleCue` means reusing their domain
   semantics and invariants (generated proposal, ordered cue set, timing/text invariants, deterministic
   ordering, source segment lineage, candidate/cue immutability, generation provenance, structural cue
   validation) — not every released persistence column. Legacy readiness/current-selection/applicability/
   review-decision/review-item/candidate-reference/validation identities and mandatory
   ProcessingRun/UnitExecution identities are **not inherited** and must never be fabricated to resemble the
   old schema.
4. **Supported sources.** Exactly the GOAL-011/012 source kinds: `raw_transcript` and
   `corrected_transcript_revision`. The candidate preserves source kind, exact immutable source identity,
   intake identity, Raw parent identity, consumption-binding identity, and the consumed ordered snapshot
   identity/fingerprint. Corrected replacement-segment lineage stays traceable to Raw segment lineage where the
   effective input carries it. Same content ≠ same source ≠ same candidate.
5. **GOAL-012 is the sole source acquisition boundary.** Generation never independently resolves current Raw or
   corrected authority, never silently falls back to Raw, never re-resolves midway, never mixes snapshots, and
   never constructs a binding after generation merely for provenance. The binding exists before generation and
   pins the exact consumed source. Transcript authority ≠ effective resolution ≠ consumption ≠ subtitle
   generation.
6. **Deterministic local generator provenance.** The first canonical generator is a deterministic local
   generator whose provenance is expressible **without** `ProcessingRun`/`UnitExecution`: generator kind,
   generator version, algorithm/parameter version, consumption-binding identity, and a deterministic generation
   key. Fake execution lifecycle records are prohibited. Execution-backed generators may arrive later under a
   separate versioned contract. Generation provenance ≠ human correction provenance ≠ review authority ≠
   execution orchestration.
7. **Downstream integration is deferred.** The new representation does not automatically enter legacy review
   preparation, review records, Human Decisions, acceptance/rejection, final subtitle selection, SRT export, or
   physical materialization. An effective-source candidate may validly exist without yet being reviewable,
   selectable, or exportable; each bridge is a separately scoped GOAL. Candidate existence ≠ review preparation
   ≠ review authority ≠ Human Decision ≠ final selection ≠ export eligibility.

## Changed Blueprint Files

- `docs/041_SUBTITLE_PIPELINE.md` — new §15 (normative contract, decisions E1…E14); §4.2 qualified as the
  legacy contract generation; header patch reference added.
- `docs/040_TRANSCRIPT_PIPELINE.md` — one §21 cross-reference paragraph (S3-15): subtitle generation is an
  approved downstream consumer of the consumption boundary; header patch reference added.

## Contract Changes

041 gains the effective-transcript-sourced subtitle candidate contract (§15). 041 §4.2's
Corrected-Transcript-only basis is scoped to the legacy contract generation (historical text preserved, not
erased). 040 §21 records subtitle generation as an approved consumer without subtitle schema details. No other
sections change meaning.

## Legacy Compatibility

All released rows, meanings, and downstream behavior of the legacy subtitle pipeline
(v12 `subtitle_candidates` family through review, decision, final selection, and SRT export) are preserved
unchanged. No backfill, no dual-write, no reinterpretation, no deletion. Historical audit remains intact.

## Canonical Representation

Within the new contract generation there is exactly one canonical representation (Decision 1); the legacy
representation stays canonical for its own generation (Decision 2). Implementation selects final names.

## Source Kinds and Lineage

`raw_transcript` | `corrected_transcript_revision`; exact source identity + intake + Raw parent +
consumption-binding identity + snapshot fingerprint; corrected replacement lineage traceable; provider
confidence never fabricated for human-corrected text.

## Identity

Future candidate identity must be deterministic and **source-sensitive**, accounting for at least: the
consumer/generator contract, intake identity, consumption-binding identity, source kind, exact source identity,
generator version, and algorithm/parameter version. Identity must never derive from timestamps, mutable current
selection, content fingerprint alone, physical paths, output filenames, latest-row position, or auto-increment
sequences alone. Cue identity is deterministic within its immutable candidate and independent of insertion
timing. Exact hash composition is left to GOAL-013 implementation.

## Replay

Same exact source binding + same generator version + same parameters + same request semantics → reuse the same
candidate. Raw → Corrected → same Raw again → reuse the original Raw-source candidate. Different immutable
source entities with identical text produce distinct candidates. These are contract requirements even though
implementation is deferred.

## Concurrency Implications

Near-concurrent identical generation requests must converge without duplicate canonical candidates; divergent
requests are never merged merely because content is equal. Exact locking/uniqueness mechanisms are
implementation-owned.

## Atomicity Implications

Candidate, ordered cue set, cue-to-source-segment lineage, and generation provenance commit atomically; no
partially persisted candidate may be visible as valid. No implementation-specific transaction API is
prescribed here.

## Generation Provenance

Deterministic local (Decision 6). Truthful, execution-free; generator kind/version/parameters recorded;
execution-backed generation is a later, separately versioned contract.

## Human Authority Separation

Generation creates no Human Decision, review record, acceptance, rejection, or selection, and never fabricates
review/authority/validation/execution identities. A candidate becoming stale never mutates authority history.

## Currentness and Staleness

The candidate retains its historical exact source binding after authority changes. Becoming stale never
mutates, deletes, corrupts, or regenerates the candidate, never triggers Raw fallback, and never rewrites
provenance. Candidate integrity ≠ source currentness ≠ review applicability ≠ final-selection eligibility.

## Migration Implications

None in this PATCH. GOAL-013 implementation is expected to add the new representation strictly additively
(anticipated schema v39) with the full migration ritual; no legacy column changes; no historical backfill
without truthful evidence.

## Repository Validation Implications

None in this PATCH. Future validation for the new representation must be integrity-only (dangling refs,
lineage/fingerprint disagreement, cue membership) — staleness against current authority is never corruption.

## Explicit Non-goals

No GOAL-013 implementation; no Python/schema/migration/repository/CLI/test changes; no subtitle candidates
created; no second generator; no legacy candidate migration or provenance backfill; no fabricated authority or
execution records; no change to review, Human Decision, final selection, SRT export, or physical
materialization behavior; no subtitle pipeline redesign; no unrelated Blueprint edits.

## Acceptance Criteria

- 041 §15 states Decisions 1–7 with identity/replay/concurrency/atomicity/currentness requirements explicit
  enough for a future implementation agent.
- 041 §4.2 is qualified as legacy-generation without erasing historical text.
- 040 §21 records subtitle generation as an approved consumer with binding-before-generation and
  no-independent-resolution requirements, without subtitle schema details.
- Schema remains v38; working tree clean after one documentation commit.

## Result

Encoded as `041 §15` (E1…E14), the 041 §4.2 legacy qualification, and the 040 §21 S3-15 cross-reference.
No implementation or migration is included in this PATCH; GOAL-013 implementation resumes separately at its
§75 step 12 with this contract as its basis.
