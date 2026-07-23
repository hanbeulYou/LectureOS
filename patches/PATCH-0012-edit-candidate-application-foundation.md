# PATCH-0012

- Title: Edit Candidate Application Foundation (042 Milestone 4)
- Status: Completed
- Priority: Medium
- Trigger: Architect / Product Owner Decision (042 Milestone 4 architecture-first investigation, D-1…D-7)
- Created: 2026-07-23
- Target Blueprint: `docs/042_LECTURE_INTELLIGENCE_PIPELINE.md`

---

## Context

An architecture-first investigation of the fourth dependency-ordered 042 milestone — **Edit Candidate** —
found that `042 §3.6`/`§9` and `030 §9` fix what an Edit Candidate *means* (an optional, evaluative,
advisory proposal derived from Analysis Finding, distinct from Review Decision, Approved Edit Decision, and
applied edits) but leave its durable-record contract, mandatory anchor, Finding/Segment multiplicity, Time
Range ownership, payload, type/taxonomy, Review relationship, and reprocessing stance as Requires-Validation
/ Deferred / unconfirmed. A complication: `020 §5.6` lists EC-001…010 as eventual product Musts, yet several
(Segment Label, expected time savings, Review status) depend on concepts the Blueprint has explicitly
deferred, so "which EC-Musts belong to the first milestone" is itself an unresolved scope decision. The
Product Owner approved the minimal decision (D-1…D-7) resolving exactly the contracts the first Candidate
milestone needs, reusing the durable-stage precedent of Eligible Analysis Input (`§5.1`, PATCH-0009),
Analysis Finding (`§8.1`, PATCH-0010), and Lecture Segment (`§7.1`, PATCH-0011).

This PATCH records that decision by promoting the first Candidate milestone into a **Confirmed** normative
contract (new `§9.1`). It defines **no** implementation, SQL, repository, execution, provider, or Review
behavior, and resolves nothing belonging to later milestones. `042` remains the single source of truth.

## Findings

- **F-01 — The Edit Candidate durable-record contract was undefined.** `§9`/`§3.6` fix the meaning, but the
  record's durability/immutability/identity, mandatory anchor, boundary, payload, type, and reprocessing
  stance were unconfirmed (§18 Requires-Validation / Deferred; `030 §9`).
- **F-02 — Candidate generation is provider-driven; the provider boundary and milestone scope needed
  fixing.** A provider's classification/operation name is never canonical (`§2.10`, NFR-005); the milestone
  had to be scoped as an Application Foundation with a provider-independent boundary that stops at Review
  handoff, and bounded so undecided concepts (Labels, confidence, time savings, Review status, multi-range/
  multi-Finding references) are not silently introduced.

## Decision Basis (Confirmed D-1…D-7)

Recorded as `042 §9.1`:

- **D-1 — Canonical Meaning and Durable Record:** Edit Candidate is optional, evaluative, advisory, derived
  from analysis, and distinct from Analysis Finding, Review Decision, Approved Edit Decision, applied edit,
  and executable NLE operation. Its record is **durable, immutable, identity-owning, provenance-bearing,
  insert-only, replay-safe, provider-independent, canonical** — with **no** lifecycle state, Review status,
  mutable state, delete behavior, revision field, supersession field, or rejected-candidate state. A rejected
  Candidate remains a durable historical record; the rejection belongs to Review (043).
- **D-2 — Canonical Anchor and Provenance:** every Candidate is anchored to **exactly one Analysis Finding**
  (mandatory); a Candidate may not exist without a Finding; **Lecture Segment is neither anchor nor reference
  in this milestone**. One Finding may support many Candidates; each Candidate references exactly one Finding.
  Multi-Finding references, Segment linkage, multi-Segment references, and many-to-many provenance are
  deferred. Provenance is inherited through the Finding (`Edit Candidate → Analysis Finding →
  EligibleAnalysisInput → transcript lineage → Source Timeline → Source Media`); the Candidate's
  DomainResultReference uses the anchoring Finding's DomainResult as its **sole direct upstream result**, and
  the Candidate carries no second direct `EligibleAnalysisInput` anchor and requires no Lecture Segment.
- **D-3 — Source Timeline Time Range:** every Candidate carries **exactly one required Source Timeline Time
  Range** on the Finding's inherited Source Timeline (finite, non-negative, `start <= end`). It belongs to
  the Candidate, identifies the region proposed for human review, **need not equal** the Finding's optional
  range (may be narrower or broader), and is **required even when the Finding has no range**. Whole-recording
  ranges are valid; zero-duration ranges are structurally valid with no special meaning. Multiple/
  discontinuous ranges, non-timeline Candidates, cross-Segment targets, overlap/adjacency/containment,
  range reconciliation, and Segment-range equality are deferred.
- **D-4 — Minimum Payload:** identity, Analysis Finding anchor, Source Media provenance, Source Timeline
  provenance, exactly one Time Range, a required **Candidate Type**, a required **rationale**, deterministic
  ordering metadata only as the durable-stage admission pattern requires, and DomainResultReference
  provenance. The rationale is canonical, provider-independent, non-empty, human-reviewable text — the
  recorded analytical reason supporting the advisory proposal (not necessarily human-authored, and never
  provider internal reasoning, chain of thought, raw model explanation, executable edit instruction, or
  Review modification content). Confidence, uncertainty, priority, severity, expected time savings,
  structured evidence, source/replacement text, proposed treatment operation, executable instructions, NLE
  operations, and any provider explanation/metadata/raw response are deferred.
- **D-5 — Candidate Type:** a required, **open, stable, provider-independent, Application-owned** canonical
  key — **not** a closed enum, fixed taxonomy, provider classification, provider operation name, or NLE
  command. Examples (retain, remove, condense, review, emphasize) remain illustrative and are not promoted to
  normative values. The exact key grammar is an implementation choice following the existing canonical
  Application-key precedent (§8.1 Finding Type). A concrete provider must map its output into an
  Application-owned Candidate Type before admission; the canonical record admits only the normalized value;
  runtime validation is not required to infer a valid string's historical source.
- **D-6 — Review Handoff Boundary:** the milestone produces **only** durable, identity-owning,
  provenance-bearing, DomainResult-bearing, Source-Timeline-traceable Candidate records. It does **not**
  create Review CandidateReferences or Review Items, assign Review status, support Accept/Reject/Modify, or
  create Approved Edit Decisions; Review modification is entirely deferred to `043`. Stable identity,
  provenance, and Source Timeline traceability are the complete Review-handoff guarantee.
- **D-7 — Reprocessing:** immutable, insert-only, provenance-preserving. Reruns produce new Candidate
  identities and records; existing records are never overwritten or deleted; prior/future Review provenance
  on older Candidate identities remains addressable. Candidate revision, supersession, replacement
  relationships, stale-candidate detection, Review reconciliation, and current-candidate selection are
  deferred to `043` or a later approved milestone.

**Admission Boundary (Confirmed):** a Candidate is admitted only from exactly one canonical Analysis Finding,
a running unit execution, and complete upstream provenance, with the normalized result's Source Timeline
matching the Finding's lineage; all upstream records are consumed read-only.

## Expected Blueprint Changes

- Records the approved Edit Candidate Application Foundation contract as normative `042 §9.1` and a confirming
  note in `§18`.
- Adds a minimal cross-reference in `030_DATA_MODEL.md §9` (Edit Candidate Model) promoting the now-confirmed
  record contract while leaving Labels / multi-range / confidence / revision / Review status deferred.

## Out of Scope (Deferred to later 042 / 043 / other milestones)

Segment Label linkage and label taxonomy; multi-Finding / multi-Segment / many-to-many provenance;
multiple/discontinuous/non-timeline/cross-Segment ranges and overlap/adjacency/containment; confidence,
uncertainty, priority, severity, expected time savings, structured evidence, source/replacement text,
proposed treatment operation, executable edit instructions, NLE operations; Candidate revision, supersession,
stale-candidate detection, Review reconciliation, current-candidate selection; Review CandidateReferences,
Review Items, Review status, Accept/Reject/Modify, Approved Edit Decisions (`043`); concrete Candidate
Generation Providers, prompts, model selection, token usage, raw provider responses, provider explanations,
internal reasoning (§18). Also out of scope: any implementation, SQL, schema, migration, repository,
execution code, provider API, lifecycle state, or Goal.

## Acceptance Criteria

- [x] The first Candidate milestone (Edit Candidate Application Foundation) is promoted to a confirmed
  normative contract (`§9.1`).
- [x] Edit Candidate is a durable, immutable, identity-owning, provenance-bearing, replay-safe,
  provider-independent, insert-only canonical record with no lifecycle/Review-status/mutable/revision/
  supersession/rejected-candidate state.
- [x] Every Candidate anchors to exactly one Analysis Finding (mandatory); Segment is neither anchor nor
  reference; DomainResult upstream is the Finding's DomainResult alone; no second `EligibleAnalysisInput`
  anchor; provenance chain deterministic.
- [x] Exactly one required Source Timeline Time Range on the Finding's Source Timeline, own to the Candidate,
  required even when the Finding has none, need not equal the Finding range; multi/discontinuous/non-timeline
  deferred.
- [x] Minimum payload = identity, Finding anchor, media/timeline provenance, one range, required Candidate
  Type, required rationale, DomainResultReference; enrichment fields deferred.
- [x] Candidate Type is a required open Application-owned key (no closed enum/taxonomy); provider values must
  be mapped before admission; retain/remove/condense/review remain illustrative.
- [x] Application Foundation stops at Review handoff; no Review artifact, status, Accept/Reject/Modify,
  Approved Edit Decision, provider invocation, or applied edit; concrete provider deferred.
- [x] Reprocessing is immutable insert-only; revision/supersession/stale/reconciliation/current-selection
  deferred; prior Review provenance not overwritten.
- [x] EC-001…010 mapped (implemented / structurally guaranteed / explicitly deferred), with deferral
  sequencing rather than cancelling the eventual Must.
- [x] Existing deferrals preserved (`§9.1`, `§18`); `030 §9` cross-reference added.
- [x] No implementation, schema, repository, provider, Review, or Goal is introduced.

## EC-001 through EC-010 Mapping

**Implemented now:** EC-001 (one required Source Timeline Time Range), EC-005 (required recorded rationale),
EC-008 (Source Timeline traceability).

**Structurally guaranteed now:** EC-003 (the open Candidate Type provides the canonical structural slot;
specific retain/delete/review recommendation categories remain deferred and are **not** implemented merely
because Candidate Type exists), EC-009 (Candidate is advisory; no automatic deletion behavior exists),
EC-010 (Candidate is non-executable; the milestone stops before automatic application).

**Explicitly deferred:** EC-002 (Segment Label linkage; deferred with Segment Labels), EC-004 (confidence or
uncertainty; deferred to later Candidate enrichment / provider contract), EC-006 (expected time savings;
remains Requires-Validation / later enrichment), EC-007 (Review status; owned by `043` Review).

Deferral **sequences** each eventual Must to a named later responsibility and does **not** cancel its Must
status; the additive, insert-only record leaves structural room to satisfy each without contradiction.

## Compatibility Notes

- **No canonical concept added; no released meaning changed.** `§9.1` confirms a durable-record contract for
  the Candidate already described by `§9`/`§3.6`; it does not re-define `§9`, and §9's illustrative "future
  purposes" list and eventual-Must connections remain deferred, not removed.
- **Consistent with prior PATCHes:** does not contradict PATCH-0009/0010/0011; the Candidate's **required**
  single range is deliberately distinct from Analysis Finding's **optional** range (§8.1) and mirrors Lecture
  Segment's **required** range (§7.1); anchoring to one Analysis Finding (not directly to both Finding and
  `EligibleAnalysisInput`) preserves a single-upstream DomainResultReference; provider-independence and the
  Application-Foundation → Concrete-Provider split are inherited unchanged.
- **Review ownership preserved:** Accept/Reject/Modify, Review status, priority, and reconciliation remain
  owned by `043`; the no-overwrite/reprocessing guarantee (§18) is met by insert-only immutability.
- **No change** to `040`, `041`, `043`, `044`, or the completed v1..v25 records/meanings; `020` EC-001…010
  retain their eventual Must status.
- **Additive only:** the subsequent implementation milestone is expected to add strictly additive persistence
  (a new schema version) for the Edit Candidate record, preserving every released meaning.
- `042` remains the single source of truth; `030` carries a cross-reference only.

## Result

- Status: **Completed**
- Changed Blueprint Files: `docs/042_LECTURE_INTELLIGENCE_PIPELINE.md` (new §9.1; §18 confirming note; header
  amended). Cross-reference: `docs/030_DATA_MODEL.md §9`.
- Notes: Records the Product Owner's approved decision (D-1…D-7) for 042 Milestone 4. Product policy/
  clarification only; no schema, code, Review behavior, provider behavior, or Goal. The next step is
  implementation of the Edit Candidate Application Foundation milestone; all later 042/043 concerns remain
  deferred.

## Related Documents

- `PATCH-0009-lecture-analysis-input-eligibility.md`
- `PATCH-0010-analysis-finding-application-foundation.md`
- `PATCH-0011-lecture-segmentation-application-foundation.md`
- `../docs/042_LECTURE_INTELLIGENCE_PIPELINE.md`
- `../docs/030_DATA_MODEL.md`
