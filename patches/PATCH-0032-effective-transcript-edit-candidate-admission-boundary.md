# PATCH-0032

- Title: Effective-Transcript Edit Candidate Admission Boundary (042)
- Status: Accepted
- Priority: High
- Trigger: Architect Decision (GOAL-026 completion report — the scope boundary left by `PATCH-0030`
  D-12 and `PATCH-0031` S-13, resolved documentation-only)
- Created: 2026-07-29
- Target Blueprint: `docs/042_LECTURE_INTELLIGENCE_PIPELINE.md` (§5.1.1 extension; §9.1 generation
  qualification; new §9.3; §8.2 D-12 and §7.2 S-13 forward notes; §18 confirming note),
  `docs/030_DATA_MODEL.md` (§9 cross-reference)

---

## Status

Accepted. **Documentation only.** This PATCH encodes the Architect Decision that unblocks the first
Edit Candidate milestone of the effective-transcript generation. It adds no implementation, no
schema change, no migration, no application code, no repository, no validator, no CLI, and creates
no Edit Candidates. The SQLite schema remains **v49**.

## Context

`PATCH-0030` re-scoped `042 §8.1` (Analysis Finding) and `PATCH-0031` re-scoped `042 §7.1` (Lecture
Segmentation) for the effective-transcript generation; GOAL-025 and GOAL-026 implemented them
(schema v48 and v49). The current generation now runs:

```text
Explicit Analysis Input Admission (GOAL-023, v47)
        |
        +----> Analysis Finding (042 §8.2 / PATCH-0030, GOAL-025, v48)
        |
        +----> Lecture Segmentation (042 §7.2 / PATCH-0031, GOAL-026, v49)
```

Both `PATCH-0030` D-12 and `PATCH-0031` S-13 explicitly declined to generalize themselves to `§9.1`
(Edit Candidate). GOAL-026's completion report therefore recommended a targeted PATCH for `§9.1` as
the next step. This is that PATCH; it completes the current generation's analysis graph by hanging
Edit Candidate off the Finding branch.

## Trigger

`042 §9.1`'s Canonical Anchor, Minimum Payload, Application Foundation, and Admission Boundary are
fixed to the terms of the **legacy execution-coupled generation**: the anchoring Analysis Finding is
the `§8.1` one, admission requires a **running unit execution**, and the payload requires a
`DomainResultReference` whose sole direct upstream is the anchoring Finding's DomainResult.
Implementing Edit Candidate in the current generation under the literal text would reproduce the
Blocking that GOAL-024 identified for Findings — a Blueprint contradiction, which `AGENTS.md` makes
a Stop Condition.

## Problem

**P-01 — The anchor names a superseded Finding generation.** `§9.1` anchors every Candidate to
exactly one Analysis Finding of `§8.1` (the legacy v24 family). The current generation's Finding is
the `§8.2` one (v48 `lecture_analysis_findings`). The anchor's *cardinality and direction* are
generation-neutral; only which Finding generation fills the slot needed deciding.

**P-02 — The admission precondition requires an execution lifecycle the current generation does not
have.** `§9.1` requires a **running unit execution**. Satisfying it literally would mean fabricating
a `ProcessingRun`/`UnitExecution`/RUNNING state — precisely what `040 §18` H-10 and `041 §15` E6
prohibit.

**P-03 — The `DomainResultReference` requirement is not merely awkward here; it is unsatisfiable.**
This is the element that makes `§9.1` harder than `§8.1` or `§7.1`. `§9.1`'s Canonical Anchor
requires the Candidate's `DomainResultReference` to use "the anchoring Analysis Finding's
DomainResult as the sole direct upstream result", and Minimum Payload lists it as a payload item.
The `§8.2` Finding **creates no DomainResult at all** — verified against the released
implementation, which contains zero DomainResult references. There is therefore no upstream result
to point at, and the only way to satisfy the clause literally would be to fabricate one.

**P-04 — The Minimum Payload fixes a *form* of provenance, not only its presence.** `§9.1` requires
mandatory Source Media and Source Timeline provenance as payload items, which the legacy relation
stores as columns. The current generation obtains upstream provenance through the anchor chain
rather than duplicating it (the precedent set by `§8.2` D-2 and `§7.2` S-2). Whether the requirement
survives, and in what form, had to be decided explicitly rather than reinterpreted silently.

**P-05 — `§9.1` has a dependent subsection.** `§9.2` (Concrete Edit Candidate Generation Provider,
`PATCH-0013`) is built on `§9.1` and is itself execution-coupled. Re-scoping `§9.1` must not be read
as re-scoping `§9.2` by implication.

## Architect Decision (Confirmed)

Thirteen decisions, encoded normatively in `042 §9.3`, with the generation distinction recorded in
`§5.1.1` and the scope of the legacy anchor and boundary recorded in `§9.1`.

**Section number:** the new subsection is **§9.3**, not §9.2, because §9.2 already exists and
renumbering it would break every existing reference in `042 §18`, `PATCH-0013`, the implementation
documents, and the released code comments. The ordering carries no dependency meaning.

**Decision prefix:** `C-1…C-13` rather than `D-n`, because `§9.2` already carries a `D-` series
(PATCH-0013) and the two subsections sit inside the same section. The prefix is notation, not
contract.

1. **C-1 Contract Generation.** The Edit Candidate admission boundary exists in two contract
   generations: `§9.1`'s Canonical Anchor, Minimum Payload, Application Foundation, and Admission
   Boundary paragraphs are the **legacy execution-coupled generation**; `§9.3` is the
   **effective-transcript generation**. Legacy contracts and records are preserved as valid history.
   Exactly one canonical Edit Candidate admission boundary exists per generation; no cross-generation
   anchoring.
2. **C-2 Canonical Anchor.** Every Candidate of this generation anchors to **exactly one canonical
   `§8.2` Analysis Finding**. `§9.1`'s anchor cardinality and direction are unchanged — the Finding
   is mandatory, a Candidate cannot exist without one, one Finding may ground several Candidates,
   and each Candidate references exactly one Finding. **Only the Finding's generation changes.** The
   Candidate does not anchor directly to the Lecture Analysis Input Admission.
3. **C-3 Segmentation Is a Sibling, Never a Parent.** As `§9.1` already states, **Lecture Segment is
   neither anchor nor reference** in this generation either. Segmentation (`§7.2`) and Finding
   (`§8.2`) are siblings over the same kind of durable analysis input; Edit Candidate hangs off the
   **Finding branch only**. Segmentation may be absent entirely and Candidates remain fully valid,
   and vice versa. Segment linkage and cross-Segment targets stay deferred.
4. **C-4 Current-Only Admission Standing.** A stored Finding's mere existence never suffices. The
   **root of the anchor chain** — the `Lecture Analysis Input Admission` that the anchoring Finding
   hangs from — must have derived standing **`current`** at prepare or admission time.
   `superseded_by_authority_change` and `current_authority_ineligible` are explicit refusals; the
   released three-value vocabulary is not extended; a missing or malformed Finding reference is a
   refusal of the reference itself, failing before standing is evaluated.
5. **C-5 No Stored Currentness.** Standing is a derived observation, never stored. No mutable status,
   current flag, stale flag, lifecycle state, or Review state is added to the Candidate or its
   anchor — consistent with `§9.1`'s own "no lifecycle state, no Review status, no mutable state".
6. **C-6 Historical Semantics.** A superseded chain — Admission, its Findings, and their Candidates —
   remains valid immutable history, never deleted, invalidated, or rewritten. Existing Candidates are
   never mutated because upstream authority changed, which is exactly how `§9.1`'s Reprocessing
   clause keeps prior Candidate identities addressable for Review provenance. Only *new* admission
   against a non-`current` chain is refused. Returning authority restores admissibility by the
   derived rule.
7. **C-7 Execution-Free Deterministic Provenance.** No `ProcessingRun`, `ProcessingUnit`,
   `UnitExecution`, RUNNING state, execution lifecycle, **or `DomainResultReference` provenance** is
   required. The last item is what distinguishes this decision from `§8.2` D-6 and `§7.2` S-7: the
   `§8.2` Finding creates no DomainResult, so no upstream result exists to reference. Fabricated
   execution records, synthetic Processing Runs, synthetic RUNNING state, and synthetic DomainResults
   are prohibited (`040 §18` H-10, `041 §15` E6). Provenance must instead be deterministic, local,
   replay-safe, identity-owning, provider-independent at the canonical boundary, free of wall-clock
   dependency and of random execution identity. Derived execution markers (`040 §14` A-3 / `040 §17`
   K-4) versus marker-free provenance (`041 §15` E6) remains an implementation choice.
8. **C-8 Upstream Provenance Through the Anchor.** The mandatory Source Media and Source Timeline
   provenance of `§9.1`'s Minimum Payload **is still required** — it does not disappear. What changes
   is its *form*: in this generation it is secured through the chain `Edit Candidate → Analysis
   Finding → Lecture Analysis Input Admission → current applicable Corrected Revision → parent Raw
   Transcript → Source Timeline → Source Media`, and the Candidate record is not obliged to duplicate
   those values as columns (the `§8.2` D-2 / `§7.2` S-2 precedent). Denormalizing for query
   convenience is an implementation choice. Either way, EC-008 Source Timeline traceability and
   `§9.1`'s timeline-lineage agreement requirement stand.
9. **C-9 Candidate Record Contract Preserved.** `§9.1`'s canonical record meaning is inherited
   unchanged: optional, evaluative, advisory; immutable, identity-owning, provenance-bearing,
   replay-safe, provider-independent, insert-only; no lifecycle, Review, mutable, revision,
   supersession, or rejected state. **The Source Timeline Time Range is preserved verbatim** —
   exactly one required range, finite, non-negative, `start <= end`, need not equal the Finding's
   optional range, required even when the Finding has none, whole-recording valid, zero-duration
   structurally valid. The required open Candidate Type and the required rationale keep their meaning
   and their boundaries. No media-duration validation, transcript-boundary alignment,
   Candidate-to-Finding containment check, or range reconciliation is added.
10. **C-10 Identity Direction.** Application-owned; provider, execution-framework, UUID, timestamp,
    rowid, path, and mutable currentness never participate; identity derives from the immutable
    anchor plus stable Candidate semantics. Exact hash composition is delegated to the implementation
    milestone (`041 §15` E7, `§8.2` D-8, `§7.2` S-10 precedent), which must additionally state which
    persisted fields participate and whether C-11's conflict branch is reachable. Two cases: **(A)**
    some persisted canonical field does not participate, so a semantic mismatch on one identity is
    reachable from normal input and must be an explicit conflict; **(B)** every persisted canonical
    field participates, so the mismatch is structurally unreachable short of a hash collision. **Even
    under (B) the semantic-equality check is not removed** — it is the only defence against a
    corrupted or hand-edited row. The choice and its justification are recorded in the
    implementation document. (This requirement is stated inline rather than cited: no `042`
    subsection carries an Option A/B framing, and the Blueprint must not point at an implementation
    artifact for a normative requirement.)
11. **C-11 Replay and Conflict.** Same Finding + same contract version + same canonical Candidate
    content → the same identity, with no duplicate record. A different Finding, Candidate Type,
    rationale, Time Range, or other identity-participating content may be a distinct Candidate. A
    semantically divergent payload for an existing identity is an **explicit conflict**, never an
    overwrite. Near-concurrent identical admissions converge. If several Candidates are admitted for
    one Finding in order, the `§7.2` S-9 ordered-batch idiom may be reused; whether it is, and
    whether the ordinal participates in identity, is stated by the implementation under C-10.
12. **C-12 Persisted Representation.** The legacy `edit_candidates` relation is **not reused** — its
    mandatory legacy Finding anchor, `processing_run_id`, `unit_execution_id`, and `domain_result_id`
    could only be satisfied by fabricating what C-7 prohibits. Any storage this generation needs
    arrives as a **strictly additive new versioned representation** (`041 §15` E1, `§8.2` D-11,
    `§7.2` S-12 precedent). The legacy relation and its rows stay canonical for their own generation.
13. **C-13 Sections Not Re-scoped.** `§9.2` (Concrete Edit Candidate Generation Provider) is **not**
    re-scoped and keeps its legacy execution-coupled contract, including its running-execution and
    `retry_of` requirements. A concrete Candidate Generation Provider operating on `§9.3` is not
    decided here. Review (`043`), Export (`044`), Final Selection, Approved Edit Decision, Analysis
    Execution, and the Processing Model are likewise untouched.

## Affected Contracts

- `docs/042 §5.1.1` — one sentence extended to name `§9.3` and to record the current generation's
  shape: Finding and Segmentation are siblings, Edit Candidate hangs off Finding only.
- `docs/042 §9.1` — all Confirmed text preserved verbatim; one added block scopes the **universal
  quantification** of its Canonical Anchor, Minimum Payload, Application Foundation, and Admission
  Boundary paragraphs to the legacy generation, naming the **four** legacy-only elements (the `§8.1`
  Finding generation, the running unit execution, the `DomainResultReference`, and the column-form of
  the media/timeline provenance) and listing what stays common to both generations.
- `docs/042 §9.3` — new normative contract (C-1…C-13).
- `docs/042 §8.2` D-12 and `docs/042 §7.2` S-13 — forward notes: both correctly declined to re-scope
  `§9.1`, and their "keeps its legacy contract" wording is now generation-scoped. D-12's note is
  written as a single merged statement covering both `§7.1` and `§9.1`, so it cannot be read in
  isolation as saying either subsection's legacy contract has lapsed — C-1 and S-1 keep both valid
  for their own generation.
- `docs/042 §18` — one Confirmed note recording the above and the surviving deferrals.
- `docs/030 §9` — one clause noting the Candidate anchor rule is generation-neutral while the Finding
  record and admission preconditions filling it differ per generation.
- Unchanged in meaning: `§9`, `§9.2`, `§8.1`, `§8.2`, `§7.1`, `§7.2`, `§12`, `§20`, and all of `040`,
  `041`, `043`, `044`.

## Required Blueprint Changes

- `docs/042_LECTURE_INTELLIGENCE_PIPELINE.md` — `§5.1.1` extension; a generation-scope block inside
  `§9.1`; new `§9.3` (C-1…C-13); forward notes on `§8.2` D-12 and `§7.2` S-13; one `§18` Confirmed
  bullet; header `Amended By` reference added.
- `docs/030_DATA_MODEL.md §9` — one generation-neutrality clause, mirroring the `§6.3` and `§8.1`
  clauses added by PATCH-0030 and PATCH-0031.

## Legacy Compatibility

- `§9.1`'s historical text and the legacy Analysis Finding anchor are **not deleted and not
  retroactively reinterpreted**; the legacy `UnitExecution` and `DomainResult` relationships are not
  retroactively removed.
- The legacy `edit_candidates` schema is **not changed**; no backfill, dual-write, migration of legacy
  rows, or reinterpretation as effective-generation records.
- `§9.2`'s concrete-provider contract is untouched and stays bound to the legacy generation.
- Existing migration history and acceptance fixtures are preserved; this PATCH requires **no schema
  change** and the schema remains **v49**.

## Deferred (unchanged by this PATCH)

Review workflow, Review status, Accept/Reject/Modify, Review CandidateReference and Review Item, and
Approved Edit Decision (`043`); Final Selection and Export (`044`); Candidate ranking, conflict
resolution, and merge policy; Candidate revision, supersession, stale detection, Review
reconciliation, and current-candidate selection; Segment Label linkage and label taxonomy; multi-
Finding, multi-Segment, and many-to-many provenance; multi-range, discontinuous, non-timeline, and
cross-Segment targets; confidence, uncertainty, priority, severity, expected time savings, structured
evidence, source/replacement text, proposed treatment operations, and executable edit commands; GUI
and human editing; this generation's concrete Candidate Generation Provider, prompt, model, and AI
invocation; Analysis Execution lifecycle.

None is a precondition of the admission boundary confirmed here: the anchor (C-2) is a single existing
immutable record, the precondition (C-4) is a derived observation already released by GOAL-023, the
provenance rules (C-7, C-8) remove or re-form dependencies rather than adding them, and the record
contract (C-9) is inherited unchanged from `§9.1`.

## Explicit Non-goals

No implementation of any kind: no application, domain, or persistence code; no schema v50; no
migration; no repository, validator, CLI, demo, golden, or test; no Edit Candidate table; no change
to legacy `edit_candidates`; no change to Analysis Finding or Lecture Segmentation; no AI, LLM,
provider, or prompt; no `ProcessingRun`, `UnitExecution`, or RUNNING state; no Review, Export, or
Final Selection work; no Goal document; no data-model redesign or structural-drift cleanup; no
unrelated Blueprint edits.

## Acceptance Criteria

- [x] `042 §9.3` states C-1…C-13 as normative Confirmed contracts, explicit enough for an
  implementation agent to proceed without further product decisions.
- [x] The `§8.2` Analysis Finding is named as the canonical Candidate anchor of the effective-
  transcript generation, with `§9.1`'s anchor cardinality and direction preserved.
- [x] Lecture Segmentation is stated to be a sibling and never a parent, and Segment remains neither
  anchor nor reference — no relationship is invented.
- [x] Candidate admission requires derived standing `current` at the **root of the anchor chain**,
  re-evaluated at command time, with the two refusal values explicit and the released vocabulary
  unextended.
- [x] Superseded chains and existing Candidates are preserved as immutable history; returning
  authority is reconciled with GOAL-023's convergence contract.
- [x] The legacy RUNNING `UnitExecution` **and** the `DomainResultReference` requirement are removed
  for the current generation, with the unsatisfiability of the latter stated and grounded in the
  released `§8.2` implementation, and without deleting `§9.1`'s historical text.
- [x] The mandatory Source Media / Source Timeline provenance is explicitly preserved in substance
  and re-formed only in its representation — not silently dropped.
- [x] `§9.1`'s canonical record contract — including the Time Range rules verbatim, the open Candidate
  Type, and the rationale — is preserved; no range rule is strengthened and no extent, containment, or
  reconciliation validation is invented.
- [x] `§9.2` Concrete Provider, Review, Export, Final Selection, Approved Edit Decision, and Analysis
  Execution are explicitly **not** re-scoped.
- [x] `§8.2` D-12 and `§7.2` S-13 carry forward notes so no stale statement claims `§9.1` still keeps
  its legacy contract universally.
- [x] Deferred items are preserved and none is accidentally confirmed.
- [x] Schema remains v49; no code file changes; one documentation commit with a clean working tree.

## Result

- Status: **Accepted**
- Changed Blueprint Files: `docs/042_LECTURE_INTELLIGENCE_PIPELINE.md` (§5.1.1 extension; §9.1
  generation-scope block; new §9.3 with C-1…C-13; §8.2 D-12 and §7.2 S-13 forward notes; §18
  Confirmed note; header amended) and `docs/030_DATA_MODEL.md §9` (one generation-neutrality clause).
- Notes: Completes the current generation's analysis graph at the contract level — Admission →
  {Finding → Edit Candidate, Segmentation}. No schema, code, or Goal is introduced. The next step is
  the implementation milestone — Edit Candidate Foundation for the effective-transcript generation —
  with this contract as its basis. A concrete Candidate Generation Provider for this generation
  remains undecided (C-13).

## Related Documents

- `PATCH-0012-edit-candidate-application-foundation.md`
- `PATCH-0013-concrete-edit-candidate-generation-provider.md`
- `PATCH-0030-effective-transcript-analysis-finding-admission-boundary.md`
- `PATCH-0031-effective-transcript-lecture-segmentation-admission-boundary.md`
- `../docs/042_LECTURE_INTELLIGENCE_PIPELINE.md`
- `../docs/030_DATA_MODEL.md`
- `../docs/040_TRANSCRIPT_PIPELINE.md`
- `../docs/041_SUBTITLE_PIPELINE.md`
