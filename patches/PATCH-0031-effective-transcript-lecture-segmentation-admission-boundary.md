# PATCH-0031

- Title: Effective-Transcript Lecture Segmentation Admission Boundary (042)
- Status: Accepted
- Priority: High
- Trigger: Architect Decision (GOAL-025 completion report — the deliberate scope boundary left by
  `PATCH-0030` D-12, resolved documentation-only)
- Created: 2026-07-29
- Target Blueprint: `docs/042_LECTURE_INTELLIGENCE_PIPELINE.md` (§5.1.1 extension; §7.1 generation
  qualification; new §7.2; §18 confirming note), `docs/030_DATA_MODEL.md` (§8.1 cross-reference)

---

## Status

Accepted. **Documentation only.** This PATCH encodes the Architect Decision that unblocks the first
Lecture Segmentation milestone of the effective-transcript generation. It adds no implementation, no
schema change, no migration, no application code, no repository, no validator, no CLI, and creates
no Lecture Segments. The SQLite schema remains **v48**.

## Context

`PATCH-0030` re-scoped `042 §8.1`'s Analysis Finding admission boundary for the effective-transcript
generation, and GOAL-025 implemented it (schema v48, `lecture_analysis_findings`). The current
generation now runs:

```text
Transcript Source Intake
↓
Canonical Effective Transcript Authority (040 §20)
↓
Derived Analysis Input Eligibility (GOAL-022)
↓
Explicit Analysis Input Admission (GOAL-023, immutable append-only, schema v47)
↓
Analysis Finding Admission (042 §8.2 / PATCH-0030, GOAL-025, schema v48)
```

`PATCH-0030` D-12 explicitly declined to generalize itself to `§7.1` (Lecture Segmentation) or
`§9.1` (Edit Candidate), and `042 §8.2` states that non-generalization normatively. GOAL-025's
completion report therefore recommended a targeted PATCH for `§7.1` as the next step. This is that
PATCH.

## Trigger

`042 §7.1`'s Canonical Anchor and Admission Boundary are fixed to the terms of the **legacy
execution-coupled generation**: every Lecture Segment must anchor to an `EligibleAnalysisInput`
whose eligibility is `ELIGIBLE`, and admission requires a **running unit execution**. The
effective-transcript generation creates neither. Implementing Lecture Segmentation there under the
literal text would reproduce exactly the Blocking that GOAL-024 identified for Findings — a
Blueprint contradiction, which `AGENTS.md` makes a Stop Condition.

## Problem

**P-01 — The Segmentation anchor is bound to a superseded record family.** `§7.1` anchors every
Segment to exactly one `EligibleAnalysisInput` (the v23 legacy family, held at zero rows). The
effective-transcript generation's durable analysis input is the GOAL-023
`Lecture Analysis Input Admission` (v47). Nothing in the Blueprint stated which canonical record
performs that role for Segmentation in the current generation.

**P-02 — The admission precondition requires an execution lifecycle the current generation does not
have.** `§7.1` requires a **running unit execution**. Satisfying it literally would mean fabricating
a `ProcessingRun`/`UnitExecution`/RUNNING state — precisely what `040 §18` H-10 ("fake
execution·synthetic Processing Run·RUNNING state는 없다") and `041 §15` E6 ("가짜 실행 lifecycle
record는 금지된다") prohibit.

**P-03 — The legacy relation cannot hold current-generation rows.** The released `lecture_segments`
table (schema v25) declares `source_input_id`, `processing_run_id`, `unit_execution_id`, and
`domain_result_id` all `NOT NULL`. Recording an effective-generation Segment there would require
fabricating every one of them.

**P-04 — Segmentation's independence from Analysis Finding needed to be preserved explicitly.**
Because Findings were implemented first (GOAL-025), an implementer could wrongly infer that
Segmentation derives from or depends on Findings. `§7.1` says the opposite in as many words, and
that independence had to be carried into the current generation rather than left to inference.

## Architect Decision (Confirmed)

Thirteen decisions, encoded normatively in `042 §7.2`, with the generation distinction recorded in
`§5.1.1` and the scope of the legacy anchor and boundary recorded in `§7.1`. They are numbered
**S-1…S-13** rather than `D-n` only because `042` already carries two distinct `D-` series (`§8.2`
from PATCH-0030 and `§9.2` from PATCH-0013); the prefix is notation, not contract. S-13 is the
non-generalization clause, numbered so a future Edit Candidate milestone has a label to cite.

1. **S-1 Contract Generation.** The Segmentation admission boundary exists in two contract
   generations: `§7.1`'s Canonical Anchor and Admission Boundary paragraphs are the **legacy
   execution-coupled generation**; `§7.2` is the **effective-transcript generation**. Legacy
   contracts and records are preserved as valid history — never deleted, backfilled, reinterpreted,
   or retroactively changed. Exactly one canonical Segmentation admission boundary exists per
   generation, and no cross-generation anchoring is permitted.
2. **S-2 Canonical Anchor.** Every Lecture Segment of this generation anchors to **exactly one
   immutable `Lecture Analysis Input Admission`**, never to the legacy `EligibleAnalysisInput`.
   Source Timeline and Source Media are provenance **inherited through** that anchor, not direct
   anchor targets, and are not duplicated onto the Segment. One Admission may anchor many distinct
   Segments.
3. **S-3 Sibling, Not Derived.** Lecture Segmentation and Analysis Finding (`§8.2`) are **sibling
   application records that independently anchor the same *kind* of Admission** — sharing the record
   kind, not necessarily the same instance: a Segment on an Admission with no Finding anywhere is
   fully valid, and the converse too. Neither is the parent of the other and neither presupposes the
   other. `§7.1` fixes one direction ("Segment는 어떤 Analysis Finding에도 anchor되지 않으며 Finding의
   존재를 요구하지 않는다") and `§8.1` the other (Lecture Segment 관계는 그 milestone의 범위가 아니다).
   Segment-Finding linkage and Segment Labels are not introduced and remain deferred.
4. **S-4 Current-Only Admission Standing.** A stored Admission's mere existence never suffices; its
   derived standing is re-evaluated at prepare or admission time and only **`current`** admits.
   `superseded_by_authority_change` and `current_authority_ineligible` are explicit refusals. The
   released three-value vocabulary is not extended, and a missing or malformed Admission reference
   is a refusal of the reference itself — not a fourth standing value — failing before standing is
   evaluated.
5. **S-5 No Stored Currentness.** Standing is a derived observation, never stored. No mutable
   status, current flag, stale flag, or lifecycle state is added to the Admission or to a Segment,
   consistent with `§7.1`'s "lifecycle state를 도입하지 않는다".
6. **S-6 Historical Semantics.** Superseded Admissions and existing Segments remain valid immutable
   history — never deleted, invalidated, or rewritten — which is how `§7.1`'s Reprocessing clause
   already satisfies §7 at the minimum. Only *new* Segmentation admissions anchored to a superseded
   Admission are refused. Authority returning to a previously admitted revision re-marks the same
   canonical Admission identity `current` and restores admissibility by the derived rule.
7. **S-7 Execution-Free Deterministic Provenance.** No `ProcessingRun`, `ProcessingUnit`,
   `UnitExecution`, RUNNING state, execution lifecycle, or `DomainResult` chaining is required, and
   fabricated execution provenance is prohibited (`040 §18` H-10, `041 §15` E6). Provenance must be
   deterministic, local, replay-safe, identity-owning, provider-independent at the canonical
   boundary, free of wall-clock dependency, and free of random execution identity. Whether the
   implementation records deterministically derived execution markers (`040 §14` A-3 / `040 §17` K-4) or
   marker-free generator provenance (`041 §15` E6) is an implementation choice.
8. **S-8 Segment Record Contract Preserved.** `§7.1`'s canonical Segment meaning is inherited
   unchanged, **including the Minimum Boundary verbatim**: exactly one required single Source
   Timeline Time Range (`finite`, non-negative, `start <= end`), whole-recording ranges valid, no
   modelled overlap/adjacency/nesting/hierarchy/containment/multi-range, and the stated meaning of
   the per-admission `sequence`. This PATCH adds **no** media-duration validation, transcript
   boundary alignment, full-coverage requirement, overlap prohibition, or gap prohibition, and
   introduces no canonical-set/uniqueness constraint or named view. Only the anchor and admission
   preconditions are re-scoped.
9. **S-9 Segment Identity and Ordered Admission.** The identity-owning canonical object is the
   **individual Lecture Segment**. No segmentation aggregate, collection, perspective group, or view
   identity is introduced; those stay deferred. Per `§7.1`, one admission admits an **ordered set of
   one or more Segments** whose per-admission `sequence` provides a stable ordinal and participates
   in deterministic identity without implying semantic order or adjacency. That ordered batch is
   therefore recorded **atomically**: a partially recorded segmentation may never appear valid.
10. **S-10 Identity Direction.** Segment identity is Application-owned; provider and execution-
    framework identifiers are never canonical identity; identity derives only from the immutable
    admitted source and stable segmentation semantics; timestamps, rowids, physical paths, mutable
    currentness, and auto-increment sequence alone never participate; exact replay converges. The
    exact hash composition is delegated to the implementation milestone (`041 §15` E7, `§8.2` D-8
    precedent) and does not block it, because the principles and the identity-owning object are
    already normatively closed.
11. **S-11 Replay and Conflict.** Same Admission + same contract version + same **ordered** canonical
    segment content → convergence on the same canonical Segment identities, with no duplicate
    records. A different Admission, Time Range, other identity-participating semantics, or a
    different position within the batch may be a distinct Segment. A semantically divergent payload
    for an existing identity is an **explicit conflict**, never an overwrite. Near-concurrent
    identical admissions converge.
12. **S-12 Persisted Representation.** The legacy `lecture_segments` relation is **not reused** —
    its mandatory legacy anchor and execution provenance could only be satisfied by fabricating what
    S-7 prohibits. Any storage this generation needs arrives as a **strictly additive new versioned
    representation** (`041 §15` E1, `§8.2` D-11 precedent). The legacy relation and its rows remain
    canonical for their own generation with no backfill, dual-write, or reinterpretation. Exact
    names and columns are chosen by the implementation milestone.
13. **S-13 No Implicit Re-scoping.** `§9.1` (Edit Candidate), Review (`043`), Export (`044`),
    Analysis Execution, and the Processing Model are **not** re-scoped and `§7.2` does not
    generalize to them; each needs its own approved generation-scope decision when scheduled.

Two of S-9's rules are **new decisions of this PATCH, not inheritance**, and are labelled as such in
`§7.2`: that one admission admits an ordered batch of one or more Segments recorded atomically, and
that the per-admission `sequence` participates in identity. `§7.1` fixed only the *purpose* of the
`sequence` ("안정적 ordinal과 deterministic identity를 위한 것"), and the legacy service took identity
from a caller-supplied plan rather than deriving it from the sequence. Stating these as inherited
would have disguised a new contract as a restatement.

## Affected Contracts

- `docs/042 §5.1.1` — one sentence extended to name `§7.2` alongside `§8.2` and to record that the
  two effective-generation boundaries are siblings over the same durable analysis input.
- `docs/042 §7.1` — all Confirmed text preserved verbatim; one added block scopes the **universal
  quantification** of its Canonical Anchor and Admission Boundary paragraphs to the legacy
  generation, naming the two legacy-only elements (the `EligibleAnalysisInput` anchor target with
  its `ELIGIBLE` requirement, and the running unit execution), and listing what stays common to both
  generations — including, explicitly, the whole Minimum Boundary and the Finding-independence rule.
- `docs/042 §7.2` — new normative contract (S-1…S-13), S-13 being the explicit non-generalization
  clause for `§9.1`, Review, Export, Analysis Execution, and the Processing Model.
- `docs/042 §18` — one Confirmed note recording the above and the surviving deferrals.
- `docs/030 §8.1` — one clause scoping anchor **cardinality** as generation-neutral while naming the
  `Eligible Analysis Input` record name and its `ELIGIBLE` eligibility requirement as legacy-only, so
  the data model never implies a stored eligibility state on the current-generation Admission.
- `docs/042 §8.2` D-12 — one forward note: it correctly did not re-scope `§7.1`, but its "both
  subsections keep their legacy contracts" wording now applies to `§9.1` alone.
- Unchanged in meaning: `§7`, `§8.1`, `§8.2`, `§9.1`, `§9.2`, `§12`, `§20`, and all of `040`, `041`,
  `043`, `044`.

## Required Blueprint Changes

- `docs/042_LECTURE_INTELLIGENCE_PIPELINE.md` — `§5.1.1` extension; a generation-scope block inside
  `§7.1`; new `§7.2` (S-1…S-13); a forward note on `§8.2` D-12; one `§18` Confirmed bullet; header `Amended By` reference added.
- `docs/030_DATA_MODEL.md §8.1` — one generation-neutrality clause, mirroring the `§6.3` clause
  `PATCH-0030` added for the Finding anchor.

## Legacy Compatibility

- The legacy `EligibleAnalysisInput` anchor and `§7.1`'s historical text are **not deleted and not
  retroactively reinterpreted**; the legacy `UnitExecution` relationship is not retroactively
  removed.
- The legacy `lecture_segments` schema is **not changed**; no backfill, dual-write, migration of
  legacy rows, or reinterpretation as effective-generation records. Its rows being currently zero is
  irrelevant — the historical schema and contract stand.
- The legacy RUNNING path is **not reused** by the current generation and is **not reintroduced
  under a different name**.
- Existing migration history and acceptance fixtures are preserved; this PATCH requires **no schema
  change** and the schema remains **v48**.

## Deferred (unchanged by this PATCH)

Concrete segmentation algorithm, provider, prompt schema, model selection, remote invocation, and
provider-response persistence; Analysis Execution lifecycle and its relationship to `ProcessingRun`;
Segment revision, supersession, and reconciliation; current-segmentation selection; Segment Labels
and taxonomy closure; multi-view, hierarchical, and overlapping segmentation layers; boundary
uncertainty; confidence/uncertainty/rationale semantics; Segment-Finding linkage; user-editable
segmentation; Review workflow, Edit Candidate generation, and export representation.

None is a precondition of the admission boundary confirmed here: the anchor (S-2) is a single
existing immutable record, the precondition (S-4) is a derived observation already released by
GOAL-023, the provenance rule (S-7) removes rather than adds an execution dependency, and the record
contract (S-8) is inherited unchanged from `§7.1`. Each therefore remains deferred without blocking
the effective-transcript Segmentation Foundation.

## Explicit Non-goals

No implementation of any kind: no application, domain, or persistence code; no schema v49; no
migration; no repository, validator, CLI, demo, golden, or test; no Lecture Segment table; no change
to legacy `lecture_segments`; no change to Analysis Finding; no Edit Candidate work; no AI, LLM,
provider, or prompt; no `ProcessingRun`, `UnitExecution`, or RUNNING state; no Goal document; no
data-model diagram redesign, structural-drift cleanup, Analysis Execution design, or Finding
taxonomy change; no unrelated Blueprint edits.

## Acceptance Criteria

- [x] `042 §7.2` states S-1…S-13 as normative Confirmed contracts, explicit enough for an
  implementation agent to proceed without further product decisions.
- [x] The GOAL-023 `Lecture Analysis Input Admission` is named as the canonical Segmentation anchor
  of the effective-transcript generation.
- [x] `§7.1`'s Finding-independence is carried forward explicitly rather than left to inference, and
  no Finding dependency is invented.
- [x] Segmentation admission requires derived standing `current`, re-evaluated at command time, with
  the two refusal values explicit and the released vocabulary unextended.
- [x] Superseded Admissions and existing Segments are preserved as immutable history; returning
  authority is reconciled with GOAL-023's convergence contract.
- [x] The legacy RUNNING `UnitExecution` requirement is removed for the current generation without
  deleting or reinterpreting `§7.1`'s historical text, and fake execution provenance is prohibited.
- [x] `§7.1`'s canonical Segment record contract — including the Minimum Boundary range rules
  verbatim — is preserved; no range rule is strengthened and no extent, coverage, or overlap
  validation is invented.
- [x] The identity-owning object is stated (individual Segment), no aggregate is invented, and the
  ordered-batch atomicity implied by the per-admission `sequence` is recorded.
- [x] `§9.1` Edit Candidate, Review, Export, Analysis Execution, and the Processing Model are
  explicitly **not** re-scoped.
- [x] Deferred items are preserved and none is accidentally confirmed.
- [x] Schema remains v48; no code file changes; one documentation commit with a clean working tree.

## Result

- Status: **Accepted**
- Changed Blueprint Files: `docs/042_LECTURE_INTELLIGENCE_PIPELINE.md` (§5.1.1 extension; §7.1
  generation-scope block; new §7.2 with S-1…S-13; §18 Confirmed note; header amended) and
  `docs/030_DATA_MODEL.md §8.1` (one generation-neutrality clause).
- Notes: Resolves the scope boundary `PATCH-0030` D-12 deliberately left for `§7.1`, at the contract
  level only. No schema, code, or Goal is introduced. The next step is the implementation milestone
  — Lecture Segmentation Foundation for the effective-transcript generation — with this contract as
  its basis. `§9.1` Edit Candidate still carries its legacy-generation boundary and will require its
  own equivalent decision when its milestone is scheduled.

## Related Documents

- `PATCH-0011-lecture-segmentation-application-foundation.md`
- `PATCH-0030-effective-transcript-analysis-finding-admission-boundary.md`
- `PATCH-0029-effective-transcript-sourced-subtitle-candidate-contract.md`
- `../docs/042_LECTURE_INTELLIGENCE_PIPELINE.md`
- `../docs/030_DATA_MODEL.md`
- `../docs/040_TRANSCRIPT_PIPELINE.md`
- `../docs/041_SUBTITLE_PIPELINE.md`
