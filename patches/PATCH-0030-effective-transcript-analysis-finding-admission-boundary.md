# PATCH-0030

- Title: Effective-Transcript Analysis Finding Admission Boundary (042)
- Status: Accepted
- Priority: High
- Trigger: Architect Decision (GOAL-024 Lecture Intelligence Analysis Foundation Gate Evaluation —
  documentation-only resolution of the single identified Blocking)
- Created: 2026-07-29
- Target Blueprint: `docs/042_LECTURE_INTELLIGENCE_PIPELINE.md` (new §5.1.1; §8.1 generation
  qualification; new §8.2; §18 confirming note)

---

## Status

Accepted. **Documentation only.** This PATCH encodes the Architect Decision that unblocks the first
Analysis Finding milestone of the effective-transcript generation. It adds no implementation, no schema
change, no migration, no application code, no repository, no validator, no CLI, and creates no Analysis
Findings. The SQLite schema remains **v47**.

## Context

GOAL-013…GOAL-021 established the effective-transcript contract generation and closed Effective Subtitle
Pipeline v1. GOAL-022 and GOAL-023 then resumed the Lecture Intelligence pipeline on that same generation:

```text
Transcript Source Intake
↓
Canonical Effective Transcript Authority (040 §20)
↓
Derived Analysis Input Eligibility (GOAL-022, derived only, nothing persisted)
↓
Explicit Analysis Input Admission (GOAL-023, immutable append-only record, schema v47)
↓
Immutable Analysis Input Snapshot
```

GOAL-023 completed 042 Milestone 1 for this generation: one explicit command revalidates the derived
eligibility at command time and appends one immutable, identity-owning, provenance-bearing record binding
the exact authority snapshot (intake, Source Media, current applicable corrected revision, parent Raw
Transcript, both observed selection records, the `040 §19` content fingerprint, segment count). Admission
identity derives from the exact immutable admitted source only; same-authority re-admission converges
idempotently; a changed authority appends a new record; prior records remain valid immutable history.
Whether a record still binds the current authority is **derived, never stored**.

The dependency-ordered next step is the Analysis Finding Application Foundation. GOAL-024's Gate
Evaluation confirmed that the canonical Finding record contract (`§8.1`, PATCH-0010) is sufficient and
reusable, but that its **Admission Boundary** is not.

## Trigger

GOAL-024 identified exactly one Blocking finding and stopped without implementing:

`042 §8.1`'s Admission Boundary is fixed to the terms and structure of the **legacy execution-coupled
generation** — it requires an `EligibleAnalysisInput` whose eligibility is `ELIGIBLE`, plus a **running
unit execution**. The effective-transcript generation creates neither. Applying `§8.1` literally in the
current generation would require reviving the legacy execution model and anchoring to a superseded record
family; following the current generation's released idiom would violate Confirmed `§8.1` text. Under
`AGENTS.md`, a Blueprint contradiction is a Stop Condition.

## Problem

**P-01 — The Finding anchor is bound to a superseded record family.** `§8.1` anchors every Finding to
exactly one `EligibleAnalysisInput` (the v23 legacy family). The effective-transcript generation's durable
analysis input is the GOAL-023 `Lecture Analysis Input Admission` (v47). The Blueprint never states which
canonical record performs `§5.1`'s durable role in the current generation, so engineering would either
invent the mapping or cross-wire two generations.

**P-02 — The admission precondition requires an execution lifecycle the current generation does not
have.** `§8.1` requires a **running unit execution**. The effective-transcript generation is deliberately
execution-free: `040 §14` (A-3) admits external results without creating internal
`ProcessingRun`/`UnitExecution` and without requiring a RUNNING unit execution; `040 §17` (K-4) derives
execution markers deterministically from the anchor and creates no internal RUNNING execution; `040 §18`
(H-10) states there is no fake execution, synthetic Processing Run, or RUNNING state; `041 §15` (E6) fixes
deterministic local provenance expressed **without** `ProcessingRun`/`UnitExecution` and prohibits fake
execution lifecycle records. Satisfying `§8.1` literally would mean fabricating exactly what these
released contracts prohibit.

**P-03 — Admission standing was undefined as a Finding precondition.** GOAL-023 derives
`current` / `superseded_by_authority_change` / `current_authority_ineligible` for an admission, but no
contract states whether a Finding may be anchored to a *superseded* admission, nor what happens to
existing Findings when upstream authority changes. Absent a decision, engineering would invent durable
product meaning about analysis currentness.

## Architect Decision (Confirmed)

Twelve decisions, encoded normatively in `042 §8.2`, with the generation distinction recorded in `§5.1.1`
and the scope of the legacy anchor and boundary recorded in `§8.1`:

1. **D-1 Contract Generation.** The Analysis Finding admission boundary exists in two contract
   generations: `§8.1`'s boundary paragraph is the **legacy execution-coupled generation**; `§8.2` is the
   **effective-transcript generation**. Legacy contracts and records are preserved as valid history — never
   deleted, backfilled, reinterpreted, or retroactively changed. The two are permanently distinguishable,
   and within one generation there is exactly one canonical Finding admission boundary. No cross-generation
   anchoring. This mirrors the versioned-architecture precedent set by `041 §15` / PATCH-0029.
2. **D-2 Canonical Finding Anchor.** In the effective-transcript generation every Analysis Finding anchors
   to **exactly one immutable `Lecture Analysis Input Admission`** (`§5.1`'s durable role; released as
   GOAL-023's v47 `lecture_analysis_input_admissions`), never to the legacy `EligibleAnalysisInput`. The
   anchor secures **by reference, not duplication**: the exact effective transcript authority snapshot,
   Source Media lineage, current applicable corrected revision, parent Raw Transcript, selection
   provenance, and the `040 §19` content fingerprint. The Finding references the canonical Admission
   identity and obtains meaning through it. One Admission may anchor many distinct Findings. `§8.1`'s
   anchor cardinality rules (exactly one durable analysis input; optional, at most one Source Timeline
   range; no Lecture Segment; multi-range deferred) are unchanged.
3. **D-3 Current-Only Admission Standing.** A stored Admission record's mere existence never suffices. The
   anchoring Admission's **current authority standing must be re-evaluated at prepare or admission time**,
   and a Finding is admitted only when that derived standing is **`current`**.
   `superseded_by_authority_change` and `current_authority_ineligible` are explicit refusals. The released
   derived vocabulary is exactly those three values and this PATCH adds none. A missing or malformed
   Admission reference is a refusal of the reference itself — **not a fourth standing value** — and fails
   before standing is evaluated.
4. **D-4 No Stored Currentness.** Standing is a derived observation, never stored. This PATCH adds no
   mutable status, current flag, stale flag, or lifecycle state to the Admission record and prohibits that
   direction. Observing standing mutates nothing; the Admission record stays append-only.
5. **D-5 Historical Admission Semantics.** Superseded Admissions remain valid immutable history — never
   deleted, invalidated, or rewritten. Existing Analysis Findings are **never mutated, deleted, or
   rewritten because upstream authority changed**; a Finding legitimately anchored to a then-`current`
   Admission remains a valid immutable record afterwards. Only *new* Findings anchored to a superseded
   Admission are refused. Because Admission identity derives from the exact immutable admitted source
   only, authority returning to a previously admitted revision makes **the same canonical Admission
   identity** `current` again and admissibility is restored by the derived rule, with no new Admission
   identity — exactly GOAL-023's returning-authority convergence contract.
6. **D-6 Execution-Free Deterministic Provenance.** The effective-transcript Finding Foundation requires no
   `ProcessingRun`, `ProcessingUnit`, `UnitExecution`, RUNNING state, or execution lifecycle. The released
   precedent is cited in two distinct groups, because they say different things: **(a) the no-internal-row
   idiom** — `040 §14` A-3 (admits external results, creates no internal `ProcessingRun`/`UnitExecution`,
   requires no RUNNING unit execution) and `040 §17` K-4 (derives execution markers deterministically from
   the anchor while creating no internal RUNNING execution); and **(b) the explicit prohibitions** —
   `040 §18` H-10 (no fake execution, synthetic Processing Run, or RUNNING state) and `041 §15` E6 (fake
   execution lifecycle records are prohibited). Fabricated execution provenance is therefore prohibited in
   this generation. Whether the implementation records deterministically derived execution markers (the (a)
   idiom) or marker-free generator provenance (the E6 idiom) is an **implementation choice**; this PATCH
   mandates neither, but either must create no internal execution row, fabricate no RUNNING state, and be
   **deterministic, local, replay-safe, identity-owning, provider-independent at the canonical record
   boundary, and sufficient to distinguish the generation contract from the immutable source binding**.
   Concrete provider invocation, model, prompt, remote request, token usage, and execution lifecycle are
   **not** fixed here.
7. **D-7 Finding Record Contract Preserved.** `§8.1`'s canonical Finding record meaning is inherited
   unchanged: durable canonical domain record — immutable, identity-owning, provenance-bearing,
   insert-only; a required provider-independent, stable, Application-owned canonical Finding Type (no
   taxonomy, no closed enum); recorded evidence with provenance; optional recorded confidence or
   uncertainty; an optional, at most one, Source Timeline Time Range; raw provider output, provider-specific
   classifications, and provider internal reasoning never enter the canonical domain. Revision and
   supersession remain deferred. **Only the anchor and the admission preconditions are re-scoped.**
8. **D-8 Identity Direction.** Finding identity is Application-owned; a provider-returned identifier is
   never canonical identity; identity derives from the immutable admitted source plus stable canonical
   Finding content; timestamps, rowids, physical paths, output filenames, mutable currentness state, and
   auto-increment sequence alone never participate; replay of the same canonical Finding converges on the
   same identity. The **exact hash composition is delegated to the implementation milestone**, following
   `041 §15` E7's precedent. This delegation does **not** block implementation, because the identity
   principles above are already normatively closed.
9. **D-9 Replay and Conflict.** Same Admission + same canonical Finding content + same Finding contract
   version → the same canonical Finding identity, with no duplicate record. A different Admission, Finding
   Type, evidence content, stable source range, or any other semantic content included in identity by
   contract may be a distinct Finding. A semantically divergent payload submitted for an existing identity
   is an **explicit conflict**, never an overwrite (the released collision-convergence idiom, `040 §18`
   H-9). Near-concurrent identical admissions converge without duplicate canonical Findings.
10. **D-10 No Finding Currentness State.** No stored `finding_is_current`, `finding_is_stale`, `ready`,
    `active`, or supersession flag is introduced. Finding applicability, staleness, and current-Finding
    selection policy are out of scope absent a separate contract. **Finding integrity ≠ Admission
    currentness ≠ analysis applicability ≠ Review eligibility.** A Finding becoming stale is never
    corruption and mutates or regenerates nothing.
11. **D-11 Persisted Representation.** This PATCH fixes canonical Finding *meaning*, not physical storage
    form. But the legacy `analysis_findings` relation requires the legacy anchor and execution provenance
    as mandatory columns, so recording an effective-generation Finding there would require fabricating
    exactly what D-6 prohibits. This generation therefore **does not reuse the legacy relation**; any
    storage it needs arrives as a **strictly additive new versioned representation**, following `041 §15`
    E1's precedent. The legacy relation and its rows remain canonical for their own generation with no
    backfill, dual-write, or reinterpretation. Exact names and columns are chosen by the implementation
    milestone.
12. **D-12 Sections Not Re-scoped.** `§8.2` does **not** re-scope the admission boundaries of `§7.1`
    (Lecture Segmentation) or `§9.1` (Edit Candidate) and does not generalize to them implicitly. Each
    retains its own contract, and each will require its own equivalent generation-scope decision in its own
    approved PATCH when its milestone is scheduled for the effective-transcript generation.

## Affected Contracts

- `docs/042 §5.1` — conceptual meaning unchanged; a new `§5.1.1` records that the durable analysis input
  role exists in two contract generations and names the canonical record of each.
- `docs/042 §8.1` — all Confirmed text preserved verbatim; one added paragraph scopes the **universal
  quantification** of its Canonical Anchor and Admission Boundary paragraphs to the legacy generation,
  naming the two legacy-only elements (the `EligibleAnalysisInput` anchor *target record* and the running
  unit execution requirement) and the Evidence paragraph's record naming, while listing what stays common
  to both generations (record properties, anchor **cardinality** rules, Finding Type, the requirement to
  record evidence with provenance, Confidence, the Application Foundation boundary). Per `041 §15` E1's
  precedent this narrowing is named honestly as a generation scoping, not described as leaving a
  universally quantified sentence untouched.
- `docs/030 §6.3` — one added clause noting that the Finding minimum-reference-unit rule is
  generation-neutral while the canonical record occupying that slot differs per generation, pointing to
  `042 §5.1.1` / `§8.2`. This is the one place outside `042` that normatively states the Finding anchor, and
  PATCH-0010 set the precedent of keeping it in sync; leaving it unqualified would let a reviewer read
  Admission-anchored Findings as a `030` contradiction.
- `docs/042 §8.2` — new normative contract (D-1…D-10) for the effective-transcript generation.
- `docs/042 §18` — one Confirmed note recording the above and the surviving deferrals.
- Unchanged in meaning: `§7.1`, `§9.1`, `§9.2`, `§12`, `§20`, and all of `040`, `041`, `043`, `044`.

### Sections deliberately not re-scoped (D-12)

`§7.1` (Lecture Segmentation) and `§9.1` (Edit Candidate) carry structurally identical legacy-generation
admission boundaries — an `ELIGIBLE EligibleAnalysisInput` or canonical `AnalysisFinding` anchor plus a
running unit execution. This PATCH **does not** re-scope them, and `§8.2` does not generalize to them
implicitly; `§8.2` states this explicitly so no future agent reads it as blanket permission. Those
milestones are not scheduled for the effective-transcript generation yet, and re-scoping contracts before
their milestone is needed would confirm product meaning without a triggering decision. When either
milestone is scheduled, it will require its own equivalent generation-scope decision in its own approved
PATCH. This is a known, deliberate scope boundary — not an oversight — and it does not affect the Finding
Foundation, which depends on neither section.

## Required Blueprint Changes

- `docs/042_LECTURE_INTELLIGENCE_PIPELINE.md` — new `§5.1.1` (two contract generations + the
  spaced-vs-code-font notation convention); a generation-scope paragraph inside `§8.1`; new `§8.2`
  (D-1…D-12); one `§18` Confirmed bullet; header `Amended By` reference added.
- `docs/030_DATA_MODEL.md §6.3` — one added clause qualifying the Finding minimum-reference-unit statement
  as generation-neutral, pointing to `042 §5.1.1` / `§8.2`.

No other Blueprint file is changed. See **Non-blocking Drift** below.

## Legacy Compatibility

- The legacy `EligibleAnalysisInput` contract and its records are **not deleted and not retroactively
  reinterpreted**; `§8.1`'s historical text is preserved verbatim.
- The legacy `analysis_findings` contract and schema are **not changed**; no backfill, no dual-write, no
  migration of legacy rows, no reinterpretation as effective-generation records.
- The legacy RUNNING `UnitExecution` path is **not reused** by the current generation and is **not
  reintroduced under a different name**.
- Existing migration history and acceptance fixtures are preserved; this PATCH requires **no schema
  change** and the schema remains **v47**.
- Both generations remain permanently distinguishable in the Blueprint.

## Non-blocking Drift (not addressed here)

GOAL-024 recorded three non-blocking drift items. This PATCH deliberately leaves all three, because none
is a precondition of the admission boundary and each would exceed minimal, cohesive change:

- `docs/030` omits Analysis Finding from its overview diagram, relationship table, and invariants. This is
  pre-existing structural drift, not a consequence of this decision; correcting it properly touches
  concept relationships beyond this PATCH's scope. Deferred to a separate documentation PATCH.
- `020 §5.5` LI-001…LI-012 versus the open Finding Type contract remains unreconciled. Reconciliation is a
  **product taxonomy policy decision** and is explicitly out of scope; it does not block the Foundation,
  which admits an open Application-owned key.
- The `ProcessingRun` / Analysis Execution lifetime boundary (`030 §16` Requires Validation) remains open.
  Designing an execution lifecycle is explicitly prohibited in this PATCH; D-6 removes the dependency
  rather than resolving the open question.

## Deferred (unchanged by this PATCH)

Canonical Analysis Unit; Analysis Execution lifecycle and its long-term relationship to `ProcessingRun`;
concrete Analysis Provider, prompt schema, model selection, remote invocation, provider-response
persistence; Finding taxonomy closure and the LI-001…LI-012 reconciliation; confidence calculation;
Finding revision, supersession, and reconciliation; multi-range evidence; segmentation view; Review
workflow; current-Finding selection; Analysis Result aggregate; Analysis Snapshot beyond the GOAL-023
input snapshot.

None of these is a precondition of the admission boundary confirmed here: the anchor (D-2) is a single
existing immutable record, the precondition (D-3) is a derived observation already released by GOAL-023,
the provenance rule (D-6) removes rather than adds an execution dependency, and the record contract (D-7)
is inherited unchanged from `§8.1`. Each therefore remains deferred without blocking the effective-
transcript Finding Foundation.

## Explicit Non-goals

No implementation of any kind: no application, domain, or persistence code; no schema v48; no migration;
no repository, validator, CLI, demo, golden output, or test; no new Analysis Finding table; no change to
legacy `analysis_findings`; no Analysis Provider; no AI or LLM invocation; no prompt design; no
`ProcessingRun` or `UnitExecution` creation; no Findings created; no Lecture Segment or Edit Candidate
work; no Goal document; no unrelated Blueprint edits.

## Acceptance Criteria

- [x] `042 §8.2` states D-1…D-12 as normative Confirmed contracts, explicit enough for an implementation
  agent to proceed without further product decisions.
- [x] The GOAL-023 `Lecture Analysis Input Admission` is named as the canonical Finding anchor of the
  effective-transcript generation, by canonical domain name, with its released v47 generation identified
  in the relationship description.
- [x] Finding admission requires derived standing `current`, re-evaluated at command time; the two refusal
  values are explicit; the released three-value vocabulary is not extended.
- [x] Superseded Admissions and existing Findings are preserved as immutable history; returning authority
  is reconciled with GOAL-023's convergence contract without contradiction.
- [x] The legacy RUNNING `UnitExecution` requirement is removed for the current generation without
  deleting or reinterpreting `§8.1`'s historical text.
- [x] Fake `ProcessingRun`, fake `UnitExecution`, and synthetic RUNNING state are prohibited as provenance.
- [x] `§8.1`'s canonical Finding record contract is preserved unchanged; no taxonomy, confidence
  calculation, or multi-range model is introduced.
- [x] Deferred items are preserved and none is accidentally confirmed.
- [x] Schema remains v47; no code file changes; one documentation commit with a clean working tree.

## Result

- Status: **Accepted**
- Changed Blueprint Files: `docs/042_LECTURE_INTELLIGENCE_PIPELINE.md` (new §5.1.1; §8.1 generation-scope
  paragraph; new §8.2 with D-1…D-12; §18 Confirmed note; header amended) and `docs/030_DATA_MODEL.md §6.3`
  (one generation-neutrality clause).
- Notes: Resolves the single Blocking finding of GOAL-024 at the contract level only. No schema, code, or
  Goal is introduced. The next step is the implementation milestone — Analysis Finding Application
  Foundation for the effective-transcript generation — with this contract as its basis; all later 042
  concerns remain deferred.

## Related Documents

- `PATCH-0009-lecture-analysis-input-eligibility.md`
- `PATCH-0010-analysis-finding-application-foundation.md`
- `PATCH-0029-effective-transcript-sourced-subtitle-candidate-contract.md`
- `../docs/030_DATA_MODEL.md`
- `../docs/042_LECTURE_INTELLIGENCE_PIPELINE.md`
- `../docs/040_TRANSCRIPT_PIPELINE.md`
- `../docs/041_SUBTITLE_PIPELINE.md`
