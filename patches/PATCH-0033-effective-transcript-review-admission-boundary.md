# PATCH-0033

- Title: Effective-Transcript Review Admission Boundary (043)
- Status: Accepted
- Priority: High
- Trigger: Architect Decision (Review Foundation Gate Evaluation — verdict "B: targeted Blueprint
  PATCH required first", resolved documentation-only)
- Created: 2026-07-30
- Target Blueprint: `docs/043_REVIEW_PIPELINE.md` (§7.4 generation qualification; new §7.5; §15.1
  confirming note), `docs/042_LECTURE_INTELLIGENCE_PIPELINE.md` (§9.3 C-13 forward note),
  `docs/030_DATA_MODEL.md` (§11.1 cross-reference)

---

## Status

Accepted. **Documentation only.** This PATCH encodes the Architect Decision that unblocks the first
Review milestone of the effective-transcript generation. It adds no implementation, no schema
change, no migration, no application code, no repository, no validator, no CLI, and creates no
Review records. The SQLite schema remains **v50**.

## Context

`PATCH-0030`, `PATCH-0031`, and `PATCH-0032` re-scoped `042 §8.1`, `§7.1`, and `§9.1` for the
effective-transcript generation; GOAL-025, GOAL-026, and GOAL-027 implemented them (schema v48, v49,
v50). The current generation's analysis graph is complete:

```text
Explicit Analysis Input Admission (GOAL-023, v47)
        |
        +----> Analysis Finding (042 §8.2, GOAL-025, v48) ----> Edit Candidate (042 §9.3, GOAL-027, v50)
        |
        +----> Lecture Segmentation (042 §7.2, GOAL-026, v49)
```

`PATCH-0032` C-13 explicitly declined to re-scope Review. The Review Foundation Gate Evaluation then
investigated `043 §7.4` and returned verdict **B**: the record contract is closed and reusable, but
the admission boundary is legacy-coupled and one of its requirements is not merely awkward — it is
unsatisfiable. This PATCH is the targeted re-scoping that Gate recommended.

## Trigger

`043 §7.4`'s `ReviewDecision` Record, `ApprovedEditDecision` Record, Admission Boundary, and Lineage
paragraphs are fixed to the terms of the **legacy execution-coupled generation**. Implementing Review
in the current generation under the literal text would require fabricating execution records and
synthetic Domain Results — a Blueprint contradiction, which `AGENTS.md` makes a Stop Condition.

## Problem

**P-01 — The anchor names a superseded Candidate generation.** `§7.4` anchors every `ReviewDecision`
to exactly one durable `EditCandidate` of `042 §9.1` (the legacy v26 family). The current
generation's Candidate is the `042 §9.3` one (v50 `lecture_analysis_edit_candidates`). The anchor's
cardinality and direction are generation-neutral; only which Candidate generation fills the slot
needed deciding.

**P-02 — The admission precondition requires an execution lifecycle the current generation does not
have.** `§7.4`: "admission은 running unit execution을 요구한다". Satisfying it literally would mean
fabricating a `ProcessingRun`/`UnitExecution`/RUNNING state, which `040 §18` H-10 and `041 §15` E6
prohibit.

**P-03 — The Domain Result requirement is unsatisfiable, and it is stronger than §9.1's was.** This
is what makes `§7.4` harder than `042 §9.1`. `§9.1` listed a `DomainResultReference` as a payload
item; `§7.4` requires **both** records to *own* their own Domain Result identity **and** to chain
directly (`ReviewDecision` upstream = the Candidate's Domain Result, `ApprovedEditDecision` upstream
= the `ReviewDecision`'s). The `§9.3` Edit Candidate creates no Domain Result at all — verified
against the released v50 table, whose columns are `identity, finding_id, candidate_type, range_start,
range_end, rationale, candidate_contract_version` with no `domain_result_id`. There is therefore
nothing to own and nothing to point at.

**P-04 — Both records must own execution provenance.** `§7.4` lists "execution provenance" in the
`ReviewDecision`'s minimum canonical information and among the `ApprovedEditDecision`'s owned values.
The current generation has none.

**P-05 — Identity ownership is stated as caller-owned.** `§7.4`: "identity는 caller-owned이고". The
current generation derives identity deterministically from content. Which applies had to be decided
explicitly rather than assumed from precedent.

**P-06 — A per-admission `sequence` is listed as minimum canonical information.** `§7.4` lists
"per-admission `sequence`(결정적 순서)" in the `ReviewDecision`'s minimum canonical information and
"결정적 per-admission `sequence`" among the `ApprovedEditDecision`'s owned values. This is textually
stronger than `042 §9.1`'s soft "ordering metadata", and `043` contains no counterpart to `042
§9.2`'s "order is transport order only, carrying no product meaning". The Gate resolved it against
the released implementation rather than by inference: one Review admission produces one
`ReviewDecision` and at most one `ApprovedEditDecision`, so the per-admission ordinal is structurally
single-valued, and `application/edit_review.py` assigns a constant for both records. It is a
durable-stage shape artifact, not a canonical ordering.

The decisive complication, which `§7.5` now addresses explicitly: `040 §18` — the closest released
contract, *First Human Authority Decision on a Correction Candidate* — fixes the **opposite** for a
human decision over a candidate. H-5 makes each authority change a new immutable record superseding
the previous current via `previous_decision_id`; H-6 **derives current authority as the highest
`sequence`**; H-7 derives identity from `(correction_candidate_id, kind, sequence)`; H-8 appends at
`sequence + 1` on Accept -> Reject. `§7.5` already cites that same section twice for other purposes
(H-9 collision convergence, H-10 the fake-execution ban), so leaving H-5...H-8 unaddressed would have
been a reasoning gap. The two ordinals are different concepts: `040 §18`'s is a **per-anchor
authority-history position**, which is precisely what makes supersession and current derivation
possible, while `§7.4`'s is explicitly **per-admission** and single-valued in an admission producing
at most two records. Only the latter is declined here; the former is neither introduced nor denied
and remains in `§15.4`'s deferred set.

**P-07 — The lineage names a legacy record.** `§7.4`'s provenance chain runs
`… → EditCandidate → AnalysisFinding → EligibleAnalysisInput → …`, naming the legacy analysis input.

## Architect Decision (Confirmed)

Twelve decisions, encoded normatively in `043 §7.5`, with the scope of the legacy anchor, payload,
and boundary recorded in `§7.4`. They are numbered **R-1…R-12**; the prefix is notation, not
contract.

1. **R-1 Contract Generation.** The Review admission boundary exists in two contract generations:
   `§7.4`'s Record, Admission Boundary, and Lineage paragraphs are the **legacy execution-coupled
   generation**; `§7.5` is the **effective-transcript generation**. Legacy contracts and records are
   preserved as valid history. Exactly one canonical Review admission boundary exists per
   generation; no cross-generation anchoring.
2. **R-2 Canonical Anchor.** Every `ReviewDecision` of this generation anchors to **exactly one
   canonical `042 §9.3` Edit Candidate**. `§7.4`'s cardinality and direction are unchanged — the
   Candidate is mandatory, upstream is consumed immutable and read-only. **Only the Candidate's
   generation changes.** No direct anchor to Analysis Finding, Lecture Analysis Input Admission, or
   Lecture Segment.
3. **R-3 Current-Only Admission Standing.** A stored Candidate's mere existence never suffices. The
   **root of the chain** — the `Lecture Analysis Input Admission` that the Candidate's Analysis
   Finding anchors — must have derived standing **`current`** at prepare or admission time.
   `superseded_by_authority_change` and `current_authority_ineligible` are explicit refusals; the
   released three-value vocabulary is not extended; a missing or malformed Candidate reference is a
   refusal of the reference itself, failing before standing is evaluated. Chain:
   `ReviewDecision → Edit Candidate → Analysis Finding → Lecture Analysis Input Admission`.
4. **R-4 No Stored Currentness.** `§7.4`'s Status Representation (Alternative A) is preserved
   verbatim — no durable status field, no state machine, no transitions, no placeholder. This PATCH
   additionally forbids adding a mutable current, stale, selection, or lifecycle state. Chain
   standing is a derived observation that mutates nothing, and Review writes no state onto the
   anchoring Candidate (consistent with `042 §9.3` C-5).
5. **R-5 Historical Semantics.** A superseded chain — Admission, Finding, Candidate,
   `ReviewDecision`, `ApprovedEditDecision` — remains valid immutable history, never deleted,
   invalidated, or rewritten, which is how `§7.4` already keeps a reject durable and auditable and
   preserves history through insert-only immutability. Only *new* Review admission against a
   non-`current` chain is refused. Returning authority restores admissibility by the derived rule.
   Revision, withdrawal, and revocation stay deferred.
6. **R-6 Execution-Free Deterministic Provenance.** No `ProcessingRun`, `ProcessingUnit`,
   `UnitExecution`, RUNNING state, execution lifecycle, **ownership of a Domain Result identity by
   either record, or direct Domain Result chaining** is required. The last two go one step beyond
   `042 §9.3` C-7, for the reason given in P-03. Fabricated execution records, synthetic Processing
   Runs, synthetic RUNNING state, and **synthetic Domain Results** are prohibited (`040 §18` H-10,
   `041 §15` E6). Provenance must be deterministic, local, replay-safe, identity-owning,
   provider-independent at the canonical boundary, free of wall-clock dependency and of random
   execution identity. Derived execution markers versus marker-free provenance remains an
   implementation choice.
7. **R-7 Upstream Provenance Through the Anchor Chain.** The inherited Source Media and Source
   Timeline provenance `§7.4` requires **is still required** — only its form changes. It is secured
   through `ReviewDecision → Edit Candidate → Analysis Finding → Lecture Analysis Input Admission →
   corrected revision → parent raw transcript → Source Timeline → Source Media`, and the record is
   not obliged to duplicate those values as columns. This is consistent with `§7.4`'s own wording,
   which already made denormalization permissive ("denormalize될 수 있으며"), and follows the
   `042 §8.2` D-2 / `§7.2` S-2 / `§9.3` C-8 precedent. Source Timeline traceability (`043 §2.9`)
   stands either way, and the `EligibleAnalysisInput` slot in `§7.4`'s lineage is filled in this
   generation by the `Lecture Analysis Input Admission` (`042 §5.1.1`).
8. **R-8 Record Contract Preserved.** `§7.4`'s two canonical records are inherited unchanged:
   durable, immutable, insert-only, identity-owning, provenance-bearing, replay-safe, independently
   identified. The closed decision kind `{accept, reject, modify}` with its semantics and its bans on
   alias, coercion, lowercasing, and interface-native mapping; the rule that none of the three
   auto-executes an edit; the statement that this closed human-action vocabulary does **not** change
   the open canonical Candidate Type contract; the `ApprovedEditDecision` creation rule (accept one,
   modify one, reject none, at most one per `ReviewDecision`, no split/merge/multi-output); the values
   it **owns** and those it **references**; Modify Ownership; the human actor reference and Human
   Authority; the list of things a `ReviewDecision` does not have; no separate durable Review Item
   record; and the prohibition on executable edit semantics — all preserved. No media-duration,
   transcript-boundary, containment, or reconciliation validation is added to the approved range
   (consistent with `042 §9.3` C-9). Only the anchor generation, admission preconditions, and
   provenance/identity/ordinal representation are re-scoped.
9. **R-9 No Canonical Ordinal.** This generation stores no per-admission `sequence`. One Review
   admission produces one `ReviewDecision` and at most one `ApprovedEditDecision`, so the ordinal is
   structurally single-valued and carries no product meaning — confirmed by the released legacy
   implementation assigning a constant to both records, not inferred. Prohibited: row-count ordinals,
   `MAX(sequence) + 1`, wall-clock order, insertion order, race-dependent order. A deterministic
   listing order is permitted but is not a canonical ordinal. `§7.5` explicitly distinguishes
   `040 §18` H-5...H-8, whose per-anchor authority-history ordinal *does* carry product meaning, from
   `§7.4`'s per-admission ordinal; the authority-history concept is neither introduced nor denied here
   and stays deferred. **Two recorded consequences.** (1) Re-submitting the same canonical Review
   judgment converges on one record instead of being preserved twice, while different actors, kinds,
   or approved values remain distinct records. (2) More consequentially: when a person reverses a
   judgment on one Candidate (`accept` -> `reject` -> `accept`), the third submission converges on the
   first identity, and the repository then holds two contradicting records with **no ordinal, no
   `previous` link, and no timestamp**. This contract does not answer which one is operative, and R-4
   forbids any field that could express it. `§7.4`'s Alternative A suffices only when a Candidate
   carries a single judgment, and R-11 permits several, so the gap is real rather than hypothetical.
   It belongs to `§15.4`'s deferred current-selection, revision, supersession, and reconciliation, and
   it is **not introduced here**: the released legacy path has the identical gap because its
   `sequence` is a constant. Closing it in this generation requires a separate approved PATCH
   establishing an authority-history contract analogous to `040 §18` H-5/H-6; until then an
   implementation may expose only that several judgments coexist as history, and must adjudicate
   none.
10. **R-10 Identity Direction.** Application-owned; provider, execution-framework, `DomainResult`,
    UUID, timestamp, rowid, path, and mutable currentness never participate. `§7.4`'s **caller-owned
    identity does not apply to this generation**; identity derives deterministically from the
    immutable anchor and stable Review meaning. **The human actor reference must participate in
    identity** — otherwise two different people making the same kind of decision would collide,
    contradicting `§7.4`'s "a new human judgment is a new insert-only record with a new identity".
    Exact hash composition is delegated to the implementation milestone (`041 §15` E7, `042 §8.2`
    D-8 / `§7.2` S-10 / `§9.3` C-10 precedent), which must state which persisted fields participate
    and whether R-11's conflict branch is reachable: **(A)** some persisted canonical field does not
    participate, so a semantic mismatch is reachable and must be an explicit conflict; **(B)** every
    persisted canonical field participates, so it is structurally unreachable short of a hash
    collision. **Even under (B) the semantic-equality check is not removed.**
11. **R-11 Replay and Conflict.** Same Candidate + same contract version + same human actor + same
    decision kind + same approved content → the same canonical identity, no duplicate. A different
    Candidate, actor, kind, approved range, Candidate Type/label, or rationale may be a distinct
    record. A semantically divergent payload for an existing identity is an **explicit conflict**,
    never an overwrite. Near-concurrent identical admissions converge. `§7.4`'s all-or-nothing
    requirement stands: accept and modify admit both records atomically, reject admits one, and a
    partially recorded Review admission may never appear valid.
12. **R-12 Persisted Representation.** The legacy `edit_review_decisions` and
    `approved_edit_decisions` relations are **not reused** — their mandatory legacy Candidate anchor,
    `domain_result_id`, `processing_run_id`, `unit_execution_id`, and `sequence` could only be
    satisfied by fabricating what R-6 and R-9 prohibit. Any storage this generation needs arrives as
    a **strictly additive new versioned representation** (`041 §15` E1, `042 §8.2` D-11 / `§7.2`
    S-12 / `§9.3` C-12 precedent). Because `§7.4` requires at most one `ApprovedEditDecision` per
    `ReviewDecision`, that uniqueness **is contract-backed** and may be expressed as a constraint —
    the **opposite in character** to `042 §7.1`, which declines canonical-set/uniqueness constraints so
    as not to force one canonical segmentation and therefore barred one there. The two uniqueness
    notions also differ in kind — set-level canonicalization of a segmentation versus 1:1
    parent-child cardinality — so this clause must not be read as authority for, or against, any
    constraint elsewhere in `042`. Exact names and columns are chosen by the implementation
    milestone, which must also name the persisted contract-version field `§7.5` leaves to it while
    requiring it in R-11's convergence key (the v48/v49/v50 precedent carries it as a stored
    column).

Additionally, `§7.5` carries an unnumbered **Sections Not Re-scoped** clause: `044` Export (its
whole document — §19, §20, §21 and the dependent §22), Review Session persistence, Review History, multi-Candidate Review Items and grouping,
multi-user conflict resolution, comprehensive human authority policy, Candidate reconciliation,
revision, supersession, withdrawal, revocation, stale detection, current-selection, Review Context
quality criteria, Review UI and external API, provider-assisted Review, and confidence/priority/
severity/quality scores are **not** re-scoped.

## Affected Contracts

- `docs/043 §7.4` — all Confirmed text preserved verbatim; one added block scopes the **universal
  quantification** of its Record, Admission Boundary, and Lineage paragraphs to the legacy
  generation, naming the **eight** legacy-only elements — including the direct-column form of the inherited
  Source Media / Source Timeline provenance, whose *requirement* is retained while only its form
  changes — and listing what stays common to both generations.
- `docs/043 §7.5` — new normative contract (R-1…R-12) plus the non-generalization clause.
- `docs/043 §15.1` — one Confirmed note recording the above and the surviving deferrals.
- `docs/042 §9.3` C-13 — forward note: it correctly did not re-scope Review, and `§7.4`'s legacy
  contract remains valid for its own generation under R-1.
- `docs/030 §11.1` — one clause separating the generation-neutral record contract from the
  per-generation anchor and admission preconditions.
- Unchanged in meaning: `043 §1`–`§6`, `§8`–`§17` apart from the `§15.1` note, `042 §7.1`–`§9.3`,
  and all of `040`, `041`, `044`.

## Required Blueprint Changes

- `docs/043_REVIEW_PIPELINE.md` — a generation-scope block inside `§7.4`; new `§7.5` (R-1…R-12); one
  `§15.1` Confirmed bullet; header `Amended By` reference added.
- `docs/042_LECTURE_INTELLIGENCE_PIPELINE.md §9.3` — one forward note on C-13.
- `docs/030_DATA_MODEL.md §11.1` — one generation-neutrality clause, mirroring the `§6.3`, `§8.1`,
  and `§9` clauses added by PATCH-0030, PATCH-0031, and PATCH-0032.

## Legacy Compatibility

- `§7.4`'s historical text, its legacy Candidate anchor, and its execution and Domain Result
  relationships are **not deleted and not retroactively reinterpreted**.
- The legacy `edit_review_decisions` and `approved_edit_decisions` schemas are **not changed**; no
  backfill, dual-write, migration of legacy rows, or reinterpretation as effective-generation
  records.
- `044`'s released Export representations, which consume `ApprovedEditDecision` and require legacy
  execution provenance, are untouched and stay bound to the legacy generation.
- Existing migration history and acceptance fixtures are preserved; this PATCH requires **no schema
  change** and the schema remains **v50**.

## Deferred (unchanged by this PATCH)

The whole of `043 §15.4` — Review Session persistence, a separate Review History model,
multi-Candidate Review Items, multi-user conflict resolution, comprehensive human authority policy,
Candidate reconciliation, revision and supersession, withdrawal and revocation, stale detection,
current-selection semantics, sufficient Review Context criteria, Review UI, external Review API,
export format, NLE integration, automatic edit application, edit rendering, provider-assisted Review,
and confidence/priority/severity/quality scores — plus, added here, this generation's link to `044`
Export and the downstream consumption of its `ApprovedEditDecision`.

None is a precondition of the admission boundary confirmed here: the anchor (R-2) is a single
existing immutable record, the precondition (R-3) is a derived observation already released by
GOAL-023, the provenance rules (R-6, R-7) remove or re-form dependencies rather than adding them,
and the record contract (R-8) is inherited unchanged from `§7.4`.

## Explicit Non-goals

No implementation of any kind: no application, domain, or persistence code; no schema v51; no
migration; no repository, validator, CLI, demo, golden, or test; no Review tables; no change to the
legacy Review or Export relations; no change to Analysis Finding, Lecture Segmentation, or Edit
Candidate; no AI, LLM, provider, or prompt; no `ProcessingRun`, `UnitExecution`, or RUNNING state; no
Export, Final Selection, Review Session, or UI work; no Goal document; no data-model redesign or
structural-drift cleanup; no unrelated Blueprint edits.

## Acceptance Criteria

- [x] `043 §7.5` states R-1…R-12 as normative Confirmed contracts, explicit enough for an
  implementation agent to proceed without further product decisions.
- [x] The `042 §9.3` Edit Candidate is named as the canonical Review anchor of the effective-
  transcript generation, with `§7.4`'s anchor cardinality and direction preserved.
- [x] Review admission requires derived standing `current` at the **root of the chain**, re-evaluated
  at command time, with the two refusal values explicit and the released vocabulary unextended.
- [x] Superseded chains and existing Review records are preserved as immutable history; returning
  authority is reconciled with GOAL-023's convergence contract.
- [x] The legacy RUNNING `UnitExecution`, the **ownership of a Domain Result identity by both
  records**, and the **direct Domain Result chaining** are removed for this generation, with the
  unsatisfiability of the latter two grounded in the released v50 Candidate table, and without
  deleting `§7.4`'s historical text.
- [x] The inherited Source Media / Source Timeline provenance is explicitly preserved in substance
  and re-formed only in representation — not silently dropped.
- [x] `§7.4`'s canonical record contract — closed decision kind, `ApprovedEditDecision` creation rule
  and owned snapshot, Modify Ownership, Alternative A, human actor reference, atomic admission, and
  the ban on executable edit semantics — is preserved verbatim in substance.
- [x] The ordinal decision is recorded with its grounding (structurally single-valued; the released
  legacy implementation assigns a constant), with `040 §18` H-5…H-8 explicitly distinguished as a
  per-anchor authority-history ordinal rather than a per-admission one, and with **both** recorded
  consequences stated: convergence on re-submission, and the unadjudicated coexistence of reversed
  judgments — which is `§15.4`-deferred and inherited from the legacy constant-`sequence` path rather
  than introduced here.
- [x] Identity direction states that caller-owned identity is legacy-only and that the **human actor
  reference must participate**, with hash composition and conflict reachability delegated.
- [x] The contract-backed at-most-one-Approved uniqueness is called out as the **opposite** of
  `042 §7.1`'s prohibition, so the two are not conflated.
- [x] `044` Export and every `§15.4` deferred item are explicitly **not** re-scoped.
- [x] `042 §9.3` C-13 carries a forward note so no stale statement claims `§7.4` still keeps its
  legacy contract universally.
- [x] Schema remains v50; no code file changes; one documentation commit with a clean working tree.

## Result

- Status: **Accepted**
- Changed Blueprint Files: `docs/043_REVIEW_PIPELINE.md` (§7.4 generation-scope block; new §7.5 with
  R-1…R-12; §15.1 Confirmed note; header amended), `docs/042_LECTURE_INTELLIGENCE_PIPELINE.md` (§9.3
  C-13 forward note), and `docs/030_DATA_MODEL.md §11.1` (one generation-neutrality clause).
- Notes: Resolves the Review Foundation Gate Evaluation's verdict B at the contract level only. No
  schema, code, or Goal is introduced. The next step is the implementation milestone — Review
  Foundation for the effective-transcript generation — with this contract as its basis. Linking this
  generation's `ApprovedEditDecision` to `044` Export remains undecided and needs its own gate.

## Related Documents

- `PATCH-0014-edit-pipeline-review-application-foundation.md`
- `PATCH-0030-effective-transcript-analysis-finding-admission-boundary.md`
- `PATCH-0031-effective-transcript-lecture-segmentation-admission-boundary.md`
- `PATCH-0032-effective-transcript-edit-candidate-admission-boundary.md`
- `../docs/043_REVIEW_PIPELINE.md`
- `../docs/042_LECTURE_INTELLIGENCE_PIPELINE.md`
- `../docs/030_DATA_MODEL.md`
- `../docs/040_TRANSCRIPT_PIPELINE.md`
- `../docs/041_SUBTITLE_PIPELINE.md`
