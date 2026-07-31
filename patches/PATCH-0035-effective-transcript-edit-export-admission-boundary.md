# PATCH-0035

- Title: Effective-Transcript Generation Edit Export Admission Boundary (044)
- Status: Accepted
- Priority: High
- Trigger: Architect Decision (Final Selection Gate Evaluation — verdict "C: Architect Decision or
  Blueprint Clarification required", resolved as **Decision B — Final Selection is not a product
  concept of the Edit Pipeline; Export Assembly owns membership**)
- Created: 2026-08-01
- Target Blueprint: `docs/044_EXPORT_PIPELINE.md` (new §23; one forward note on §20; §15.1 confirming
  note; §15.3 and §15.4 scope notes; header amended), `docs/043_REVIEW_PIPELINE.md` (forward notes on
  §7.5's "Sections Not Re-scoped", on §7.6 AH-10, and on §7.6's Deferred list),
  `docs/042_LECTURE_INTELLIGENCE_PIPELINE.md` (notes on §9.3 C-13, the §9.3 Deferred list, and the
  §18 Confirmed summary), `docs/030_DATA_MODEL.md` (§11.1 cross-reference)

---

## Status

Accepted. **Documentation only.** This PATCH encodes the Architect Decision that unblocks the Edit
Export milestone for the effective-transcript generation. It adds no implementation, no schema
change, no migration, no application code, no repository, no validator, no serializer, no CLI, no
demo, no golden, no Goal, and creates no records. The SQLite schema remains **v52**.

It also introduces **no new aggregate, no new product domain, no new human authority, no approval
layer, no selection stage, and no new identity, history, or replay contract.** Where a physical form
is eventually required, this PATCH fixes meaning only and delegates the form to the implementing
milestone, following the precedent of `043 §7.5` R-12 and `§7.6` AH-12.

## Context

`PATCH-0032`, `PATCH-0033`, and `PATCH-0034` scoped the Edit branch of the effective-transcript
generation as far as a derivable current human judgment, and GOAL-027/028/029 implemented it at
schema v52:

```text
Lecture Analysis Input Admission (GOAL-023 chain root)
  → Analysis Finding            (042 §8.2, GOAL-025)
    → Edit Candidate            (042 §9.3, GOAL-027)
      → ReviewDecision (+ at most one ApprovedEditDecision)   (043 §7.5, GOAL-028)
        → Review Authority Position (append-only)             (043 §7.6, GOAL-029)
          → current operative judgment, derived per (Candidate, actor)
```

Beyond that point the branch has no consumer. `043 §7.5`'s **Sections Not Re-scoped** clause states
that `044`'s Export contracts — "§19·§20·§21과 그에 의존하는 §22를 포함해 전체" — are not re-scoped,
and that connecting this generation's approved records to Export "requires a separate generation
scope decision". `§7.6` AH-10 repeats it in the strongest available form: "현재 유효한 판단이라는
사실은 그 자체로 Export 적격성이 아니다 — 이 세대의 승인 기록을 `044`에 연결하는 결정은 `§7.5`가
명시한 대로 여전히 별도 결정이다." Both `§7.5` and `§7.6` list that link in their Deferred sections.

This PATCH is that separate decision.

## Trigger

The Final Selection Gate Evaluation returned **C — Architect Decision or Blueprint Clarification
required**, on three verified grounds:

1. **No Final Selection contract exists for the Edit Pipeline in any generation.** A full sweep of
   `docs/` and `patches/` finds the term only (a) as a Subtitle-Pipeline concept (`041 §15` E11/E13,
   `PATCH-0029`), and (b) as an undefined label inside negative clauses in `042 §9.3` C-13, `042`'s
   Deferred list, `042 §18`, and the non-goals of `PATCH-0032`/`PATCH-0033`. There is therefore no
   released text to re-scope, so the versioned-generation idiom of `PATCH-0030`…`0034` — which
   presupposes an existing legacy contract — cannot apply. The gate's verdict was **not** B.
2. **The one genuinely open item is membership, and the Blueprint says so in its own words.**
   `044 §20` A-3: "Assembly는 scope-selection(membership) 정책을 소유하지 않는다 … membership 정책은
   독립적이고 여전히 열린 제품 결정으로 유보된다." `PATCH-0016:49` goes further and enumerates the
   two candidate answers: "whether an Assembly denotes **all current approved edits or an explicit
   subset** is not fixed here". This PATCH therefore does not invent an option; it selects one of the
   two the Blueprint already recorded.
3. **`§20` A-13 anticipated the same answer without conferring it.** It permits a first
   implementation slice to realize "그 timeline의 모든 현재 승인 편집" but states expressly that this
   is "canonical 정책이 **아니라** Goal 수준의 scope 경계". The policy status the implementation would
   need was withheld on purpose, and only an approved PATCH can grant it.

The subsequent Architect Decision session resolved the product question as **Decision B**: Final
Selection does not exist as a product concept of the Edit Pipeline, and Export Assembly carries the
membership responsibility. This PATCH encodes that decision and nothing beyond it.

## Problem

Five problems had to be resolved together.

**P-01 A second approval gate would split Human Authority.** An independent Final Selection aggregate
would let a person exclude an edit they had already accepted. That exclusion is semantically a weak
`reject`, and `043 §7.2` assigns `reject` to Review while `§13` fixes Review as the **only** place
Human Authority is exercised. It would also create a path around the authority history that
`§7.6` had just established: the history would record `accept` while the deliverable omitted the
edit. `044 §2.8` and `§13` independently bar Export from holding approval authority.

**P-02 The `§19` atom cannot be reproduced in this generation.** `§19` D-2 requires the
`ApprovedEditExportRepresentation` to own its **Domain Result identity**, **execution provenance**,
and a **per-admission `sequence`**, and D-8/D-9/D-10 require a **running unit execution** and
**caller-owned identity**. Those are precisely the requirements `§7.5` R-6 declared unsatisfiable
here (this generation's Candidate produces no Domain Result, so there is nothing to own or
reference) and R-9 declared meaningless here (a per-admission ordinal is structurally single-valued).
Reproducing `§19` verbatim would require fabricating the execution records and synthetic Domain
Results that `040 §18` H-10 and `041 §15` E6 prohibit. Its purpose is also already served: D-3 has
the atom own a copied approved snapshot, but `§7.5` R-8 confirms the `ApprovedEditDecision` **already
owns** that complete snapshot, and `042 §8.2` D-2, `§9.3` C-8, and `§7.5` R-7 established for this
generation that meaning is inherited through the anchor and never duplicated.

**P-03 "All current" is not always defined.** `§7.6` AH-9 derives a Candidate's current operative
judgment only when exactly **one** actor holds history; with two or more it derives **none** and
declares a `§3.12` Review Conflict, while prohibiting priority, recency, and role ranking and
explicitly declining `§15.3`. A timeline-wide membership rule must therefore be well-defined for such
a Candidate **without** answering the question `§7.6` refused. It is: the eligibility predicate
(EA-4) already excludes it, because no current operative judgment exists to own an eligible approval,
so no separate arbitration or exclusion rule is required. What that leaves open — how the conflict is
surfaced at export time — is a distinct product question, and this PATCH deliberately does not answer
it (see Deferred and Remaining Risk).

**P-04 Currentness is not, by itself, export eligibility.** AH-10 states this and leaves the actual
condition unstated. Three separate observations bear on it — the derived current judgment (AH-8), the
single-actor precondition (AH-9), and the chain-root admission standing (`§7.5` R-3) — and none of
them alone is the answer. The eligibility predicate had to be stated once, in one place.

**P-05 Records admitted before `PATCH-0034` carry no history position.** AH-12 rules that their
absence "is not corruption" and prohibits retroactive backfill; `current_review` yields nothing for
them. A membership rule built on the derived current judgment must classify them explicitly, or an
implementer will read the absence either as an error or as an eligible edit.

## Architect Decision (Confirmed)

Eleven decisions, to be encoded normatively as `044 §23`, EA-1…EA-11. Summarized here; `§23` is
authoritative once applied.

1. **EA-1 Scope and Instrument.** This subsection applies to the **effective-transcript generation
   only**. `§19`, `§20`, `§21`, and `§22` remain the legacy execution-coupled generation's contracts,
   valid for their own generation and neither deleted, rewritten, nor retroactively reinterpreted;
   their released records stay valid history. The two generations remain permanently distinguishable
   and one generation's records are never cross-used as another's export input. Within one contract
   generation there is exactly one canonical Edit Export admission boundary.

2. **EA-2 Export Admission Anchor.** In this generation, the Edit Export Assembly gathers this
   generation's **`ApprovedEditDecision` records (`043 §7.5`) directly**. The `§19`
   `ApprovedEditExportRepresentation` stage is **not reproduced** in this generation, for the reason
   recorded as P-02: its D-2 minimum (owned Domain Result identity, execution provenance,
   per-admission ordinal) is unsatisfiable under `§7.5` R-6/R-9, and its D-3 purpose is already
   discharged by the `ApprovedEditDecision`'s owned approved snapshot. `§20` A-1's **cardinality and
   direction are unchanged** — an Assembly is anchored to exactly one Source Timeline, gathers the
   approved edits belonging to that timeline, and consumes them **immutable and read-only**. What
   changes is only which generation's record occupies the member position, exactly as `§7.5` R-2
   changed only the Candidate's generation. This adds no aggregate: the Assembly is an existing
   Blueprint concept (`§3.7`, `§20`), scoped here as `PATCH-0032`/`0033`/`0034` scoped Candidate,
   Review, and authority history.

3. **EA-3 Membership Is All Current Approved Edits of One Source Timeline.** `§20` A-3's reservation
   is **resolved for this generation**: one Assembly denotes **every export-eligible approved edit
   (EA-4) belonging to that one Source Timeline**, and nothing else. Of the two options
   `PATCH-0016:49` enumerated, "all current approved edits" is selected and "an explicit subset" is
   not adopted. Membership is therefore **not chosen** by anyone — it is **determined** by the
   eligibility predicate. No subset, filter, user selection, ranking, or priority participates.
   `§20` A-1's prohibition on cross-timeline and cross-media aggregation stands unchanged.

4. **EA-4 Export Eligibility.** AH-10's open condition is closed. One `ApprovedEditDecision` of this
   generation is export-eligible when **all three** hold:
   - **(i) Current authority.** It is the approval owned by the Candidate's **current operative
     judgment**, derived per `§7.6` AH-8 from persisted positions only, never stored and never a
     latest-row heuristic. A superseded judgment's approval is **not** eligible; it remains valid
     immutable history (`§7.5` R-5, `§7.6` AH-8).
   - **(ii) Single actor.** Exactly one actor holds authority history for that Candidate, so a
     current operative judgment exists at all (`§7.6` AH-9). See EA-5.
   - **(iii) Current standing.** The derived admission standing at the root of the anchor chain
     (`§7.5` R-3) is `current`. `superseded_by_authority_change` and `current_authority_ineligible`
     make the approval ineligible for export. The released three-value vocabulary is **not extended**
     and no fourth value is introduced; a missing or malformed reference is refused before standing is
     evaluated. Observing an ineligible chain remains permitted and mutates nothing (`§7.6` AH-10),
     and a superseded chain is never corruption (`040 §18` H-12 idiom).

   A `reject` produces no `ApprovedEditDecision` and is therefore outside the predicate by
   construction, preserving `§19` D-7's rule without restating it as a filter.

5. **EA-5 Multi-actor Conflict Is Never Arbitrated.** When a Candidate on the timeline holds
   authority history for two or more actors, `§7.6` AH-9 derives **no** current operative judgment.
   Export **does not resolve it**: priority among actors, recency across actors, role or permission
   ranking, automatic merge, and automatic selection are **prohibited**, and Export may not derive an
   operative judgment where AH-9 derives none. No further rule is needed for membership: such a
   Candidate simply fails EA-4(i)/(ii) and contributes no member. `§15.3`'s multi-user question is
   **not answered**; it stays open and `§15.4`'s multi-user conflict resolution stays deferred.
   Resolution belongs to Review, where a person judges again. **What this subsection does not
   decide:** how the conflict is surfaced at export time, and whether its presence should affect the
   admission of the rest of the timeline. `§3.12` governs the Conflict itself in Review; the export
   time treatment is deferred (see Deferred).

6. **EA-6 No New Authority.** Constructing an Assembly is **not an approval act**. It creates no
   human decision, re-approves nothing, and may not modify, reject, filter, reinterpret, or
   supersede any Review record (`044 §2.8`, `§13`; `043 §13`). Review remains the **only** stage at
   which Human Authority is exercised. A person may trigger an export, but triggering exercises no
   authority: the meaning admitted is entirely determined by decisions already recorded in Review.
   `ApprovedEditDecision` remains the single canonical authority for approved edit intent
   (`§7.4` Modify Ownership, `§7.5` R-8, `§19` D-4).

7. **EA-7 Membership Is Derived, Never Selected or Stored as Selection.** There is **no Final
   Selection record, aggregate, stage, or authority** in this generation. Eligibility is a **derived
   observation** over persisted rows, in the idiom of `§7.5` R-4 and `§7.6` AH-8: no mutable current
   flag, stale flag, selection flag, lifecycle state, or status field is introduced anywhere, and
   introducing one is prohibited. That an Assembly durably records which approved edits it gathered
   is **membership provenance of that Assembly**, not a stored selection and not an authority over
   what is approved.

8. **EA-8 Execution-Free Deterministic Provenance.** This generation's Edit Export admission does
   **not** require `ProcessingRun`, `ProcessingUnit`, `UnitExecution`, RUNNING state, an execution
   lifecycle, ownership of a Domain Result identity, or Domain Result chaining. `§19` D-2/D-8/D-11
   and `§20` A-9's multi-upstream Domain Result lineage are **legacy-generation requirements** and are
   scoped as such, for the reason `§7.5` R-6 recorded: no Domain Result exists in this generation to
   own or reference. Fabricated execution records, synthetic Processing Runs, synthetic RUNNING
   state, and synthetic Domain Results are **prohibited** as provenance (`040 §18` H-10, `041 §15`
   E6). `§20` A-8's determinism and replay-safety are **retained unchanged**: the same persisted state
   yields the same Assembly, with no wall-clock and no randomness. Source Media and Source Timeline
   provenance is **retained** and secured through the anchor chain
   `ApprovedEditDecision → ReviewDecision → Edit Candidate (042 §9.3) → Analysis Finding (042 §8.2) →
   Lecture Analysis Input Admission → current applicable Corrected Revision → parent Raw Transcript →
   Source Timeline → Source Media`, following `§7.5` R-7; whether an implementation denormalizes part
   of it for lookup is an implementation choice, and `§2.9` Source Timeline traceability must hold
   under either form.

9. **EA-9 Judgments Without a History Position.** A `ReviewDecision` admitted before `PATCH-0034`
   may hold **no** authority position, and that is **not corruption** (`§7.6` AH-12). No current
   operative judgment is derivable for it, so its approval is **not export-eligible** under EA-4(i).
   It must be reported as "no recorded authority history", never as an error and never as "no
   judgment exists". **Retroactive backfill of positions remains prohibited**, and export must not
   become the occasion to synthesize one.

10. **EA-10 Persisted Representation.** This subsection fixes **meaning only** and does not fix a
    physical form. Where one is required, it is introduced as a **strictly additive new versioned
    representation**, following `041 §15` E1, `042 §8.2` D-11 / `§7.2` S-12 / `§9.3` C-12, `043 §7.5`
    R-12, and `§7.6` AH-12. The legacy `edit_export_*` relations of `§19`–`§22` are **not reused** —
    their mandatory legacy anchors and execution provenance could only be satisfied by fabricating
    what EA-8 prohibits — and are left exactly as they are: no backfill, no dual-write, no
    reinterpretation, released rows keeping their identities and columns. Identity direction is
    inherited, not newly authored: Application-owned and deterministic from immutable anchors, with
    no provider identifier, execution identifier, `DomainResult`, UUID, timestamp, wall-clock, rowid,
    path, or mutable currentness participating (`§7.5` R-10, `§7.6` AH-11). The exact composition,
    the conflict-branch reachability accounting, and the atomicity boundary are **delegated to the
    implementing milestone**; this PATCH authors no identity, history, or replay contract of its own.

11. **EA-11 Final Selection Does Not Exist.** For the Edit Pipeline, **Final Selection is not a
    product concept** — not in the legacy generation, not in this generation, and not as future work.
    Where `042 §9.3` C-13, `042`'s Deferred list, and `042 §18` name it alongside Export, the label
    denotes nothing that will be built; the Export half of those clauses is real and is scoped here.
    The released sentences are **not deleted**; a note records that the concept was investigated and
    determined not to exist. `041`'s Final Subtitle and its selection are a **different pipeline's**
    contract and are entirely unaffected: there, competing whole-document candidates make exactly one
    the approved subtitle, whereas approved edits are complementary members of a set and their
    operative judgment is already derived per Candidate by `§7.6`.

## Affected Contracts

- `docs/044 §23` — new subsection, EA-1…EA-11 plus "Sections Not Re-scoped" and "Deferred".
- `docs/044 §20` — one forward note, added without deleting or rewriting a single existing sentence:
  A-3's reserved membership policy is resolved **for the effective-transcript generation** by `§23`
  EA-3, and A-13's "Goal-level, not canonical policy" caveat is superseded for that generation only.
  A-3 stands unchanged for the legacy generation.
- `docs/044 §15.1` — one Confirmed note recording the above.
- `docs/044 §15.3` — one note: the completeness question ("일부 승인 결과만 export할 때…") does not
  arise in this generation because membership is total; it stays open for any future subset contract.
- `docs/044 §15.4` — one note: this generation's Export admission boundary is confirmed; concrete
  formats, NLE integration, and the rest of the list stay deferred.
- `docs/043 §7.5` — one forward note on the **Sections Not Re-scoped** clause: the separate
  generation-scope decision it required for linking this generation's approved records to `044` is
  made by this PATCH, for `§19`/`§20` only.
- `docs/043 §7.6` — one forward note on AH-10 (the Export-eligibility condition it left open is
  fixed by `044 §23` EA-4) and one on its Deferred list (the `044` link is no longer deferred for the
  admission boundary; `§21`/`§22` remain).
- `docs/042 §9.3` C-13, `§9.3` Deferred, `§18` Confirmed — three notes recording EA-11.
- `docs/030 §11.1` — one cross-reference clause: which approved edits reach Export, and under what
  conditions, is per-generation and fixed for this generation by `044 §23`.
- Unchanged in meaning: `044 §1`–`§18`, `§19`, `§21`, `§22`; `043 §1`–`§7.4`, `§8`–`§17`; all of
  `040` and `041`; every released record of either generation.

## Required Blueprint Changes

- `docs/044_EXPORT_PIPELINE.md` — new `§23` (EA-1…EA-11); one `§20` forward note; one `§15.1`
  Confirmed bullet; the `§15.3` and `§15.4` notes; header `Amended By` reference added.
- `docs/043_REVIEW_PIPELINE.md` — one `§7.5` forward note; two `§7.6` notes.
- `docs/042_LECTURE_INTELLIGENCE_PIPELINE.md` — three notes recording that Final Selection does not
  exist.
- `docs/030_DATA_MODEL.md §11.1` — one cross-reference clause.

## Legacy Compatibility

`§19`–`§22`'s legacy execution-coupled contracts are untouched and their records stay valid history;
the legacy generation gains nothing from this subsection and its `§20` A-3 reservation stands (EA-1).
The released v52 relations of this generation are not altered, re-keyed, or backfilled, and every
released identity keeps its exact value (EA-10). Nothing in this PATCH requires a migration; the
implementing milestone's migration must be strictly additive.

## Deferred (unchanged or newly recorded by this PATCH)

`§21` Edit Export Artifact and `§22` concrete serialization/materialization **for this generation** —
their released text anchors to the legacy Assembly and each needs its own generation-scope decision,
exactly as `§19`→`§20`→`§21`→`§22` each required its own PATCH in the legacy branch.

Three product policies adjacent to this boundary are **deliberately left undecided**, because the
admission boundary is well-defined without them and each is a separate product decision:

- **Conflict treatment at export time.** EA-5 fixes only that Export never arbitrates, and EA-4 fixes
  only that a conflicted Candidate contributes no member. The resulting product behaviour is **not**
  decided here: whether an Assembly is admitted at all for a timeline holding a cross-actor Conflict,
  whether the remaining eligible edits of that timeline are admitted without it, whether the
  timeline's admission is refused outright, and whether and how the Conflict must be surfaced at
  export time. `§3.12` governs the Conflict itself in Review, and `§15.4`'s multi-user conflict
  resolution stays deferred.
- **Overlap.** Whether two eligible approved edits whose approved Source Timeline ranges overlap
  require any adjudication — merge, split, precedence, or refusal — is not decided here, exactly as
  `§19` D-15 and `§20` A-13 left it. This subsection introduces **no** overlap rule: EA-4's
  eligibility predicate does not consider overlap, so nothing here excludes an overlapping approved
  edit, and an implementation may not invent an overlap filter under this contract. Inter-decision
  ordering semantics stay deferred with it; the deterministic construction that `§20` A-8 already
  requires is retained by EA-8 and its canonical member order is delegated by EA-10 as a
  presentation matter, never an execution, timeline, or overlap order (`§22` C-3 idiom).
- **Empty scope.** Whether a Source Timeline with no export-eligible approved edit yields a
  zero-member Assembly, an explicit refusal, or something else is not decided here. Note the
  interaction with the previous item: a timeline whose Candidates are all conflicted likewise yields
  no eligible member, so whichever policy governs the no-eligible-member case will have to govern
  that situation too.

Also deferred and unchanged: explicit subset selection and filtering, Export Profile and Export
Configuration, partial-scope completeness UX,
cross-representation equivalence, provider and NLE adapters, executable edit semantics,
output-timeline transformation, rendering, delivery/download/upload/URLs, Export Package, retry and
failure lifecycle, Assembly replacement or revision; and on the Review side, cross-actor arbitration
and the interpretation of authority across actors (`043 §15.3`), the same-kind/different-approval
history representation, withdrawal, revocation, stale detection, Review Session persistence, a
separate full Review History model, multi-Candidate Review Items, Review UI and external API,
provider-assisted Review, and confidence/priority/severity/quality score.

## Explicit Non-goals

- No implementation, schema, migration, application code, repository, validator, serializer, CLI,
  demo, golden, test, or Goal is added; the schema stays at **v52**.
- **No new aggregate, product domain, or pipeline stage is created.** The Assembly is an existing
  Blueprint concept being scoped, not a new one, and no Final Selection aggregate is revived.
- **No new human authority, approval layer, re-approval, export approval, or export selection is
  introduced**, and Review's exclusive Human Authority is not weakened.
- No new identity composition, immutable-history contract, replay contract, projection, query
  contract, configuration, or serializer is authored; all such requirements are inherited and their
  form is delegated.
- No mutable current, stale, selection, or status flag is introduced anywhere.
- No released identity composition is changed and no released row is reinterpreted or backfilled.
- No automatic ranking among actors is introduced, and `043 §15.3` is not answered.
- **No conflict-treatment, overlap, or empty-scope policy is fixed.** This PATCH closes the Export
  admission boundary — which approved edits are members — and nothing beyond it. It does not decide
  how a Conflict is surfaced at export time, whether a Conflict on a timeline affects the rest of
  that timeline, whether overlapping approved edits require adjudication, or whether a zero-member
  scope is admissible. Each is a separate product decision requiring its own approved PATCH.
- `§19`, `§21`, `§22`, `043 §7.4`'s legacy contract, `042`'s subsections, and `041`'s Final Subtitle
  contract are not re-scoped.

## Acceptance Criteria

- [x] The Edit Export admission boundary of the effective-transcript generation is Confirmed in the
  Blueprint, without deleting or rewriting a single existing sentence of `§19`–`§22`, `043 §7.4`,
  `§7.5`, or `§7.6`.
- [x] `044 §20` A-3's reserved membership policy is resolved **for this generation only**, and the
  selection between the two options `PATCH-0016:49` enumerated is recorded together with its reason
  (EA-3).
- [x] `043 §7.6` AH-10's open Export-eligibility condition is closed by a single stated predicate with
  three conjuncts, and the fact that currentness alone was never sufficient is preserved (EA-4).
- [x] Automatic priority, recency, role ranking, merge, and selection among actors are prohibited;
  deriving an operative judgment where AH-9 derives none is prohibited; membership is shown to be
  well-defined for a conflicted Candidate through EA-4 alone, with no separate arbitration or
  exclusion rule; and `§15.3` is explicitly **not** answered (EA-5).
- [x] It is stated normatively that constructing an Assembly exercises no Human Authority and that
  Review remains the sole approval stage (EA-6).
- [x] The non-existence of Final Selection is recorded in `042` without deleting released text, and
  the asymmetry with `041`'s Final Subtitle is stated so the Subtitle precedent cannot be cited back
  (EA-11).
- [x] The reason `§19`'s representation stage is not reproduced is stated from `§7.5` R-6/R-9 and
  `§7.4`/R-8 rather than asserted, and `§20` A-1's cardinality and direction are preserved (EA-2).
- [x] Positionless pre-`PATCH-0034` judgments are classified explicitly as ineligible but not corrupt,
  with backfill still prohibited (EA-9).
- [x] Conflict treatment at export time, overlap adjudication, and empty-scope policy are recorded as
  **not decided** by this PATCH, with the reason that the admission boundary is well-defined without
  them, and each is left to its own approved PATCH.
- [x] No aggregate, authority, identity, history, replay, or schema contract is authored; schema
  remains v52; no code file changes; one documentation commit with a clean working tree.

## Remaining Risk

**`§21`/`§22` are still unreachable in this generation.** After this PATCH an implementation can admit
an Assembly but cannot produce an Artifact or a file, because `§21` B-1 anchors to the legacy
`EditExportAssembly` and `§22` projects `§21`. This is deliberate and mirrors the legacy branch's four
separate PATCHes, but it means the first Goal built on this contract ends at a durable Assembly with
no external output. That must be stated in the Goal so the absence of a file is not read as a defect.

**The product behaviour of Export Admission on a Source Timeline that holds a cross-actor Conflict is
not yet defined.** What this PATCH fixes is membership only: EA-4 makes such a Candidate ineligible,
so it contributes no member, and EA-5 forbids Export from arbitrating between the actors. What it
does **not** fix is the resulting product behaviour — whether an Assembly is admitted at all for such
a timeline, whether the conflicted Candidate alone contributes nothing while the remaining eligible
edits are admitted, whether the timeline's admission is refused outright, and whether and how the
Conflict must be surfaced at export time. An implementation may not settle any of these by choosing
one and shipping it: the chosen behaviour would be read back as the contract. It is a Product
Decision requiring its own approved PATCH, and until then this situation is a documented boundary of
the contract rather than a licence for implementer judgment. An earlier draft of this PATCH decided
it (by refusing the whole timeline's admission); that decision was withdrawn as product policy
exceeding the admission boundary, and the question is recorded here rather than silently resolved in
either direction.

**Total membership makes export sensitive to upstream authority changes.** Because membership is
derived and total, an authority change upstream can change which edits a *new* Assembly would gather.
Already-admitted Assemblies are immutable and are never rewritten (`§20` A-1 and the insert-only
idiom), so this is a difference between successive Assemblies, not a mutation — but an
implementation must present it that way rather than as drift or corruption.

## Result

- Status: **Accepted**
- Changed Blueprint Files: `docs/044_EXPORT_PIPELINE.md` (new §23 with EA-1…EA-11, "Sections Not
  Re-scoped", "Deferred", and twenty canonical invariants; one §20 forward note after A-3; one §15.1
  Confirmed bullet; §15.3 and §15.4 notes; header amended to Blueprint 0.8 / Amended By PATCH-0035),
  `docs/043_REVIEW_PIPELINE.md` (one §7.5 forward note before its Deferred paragraph plus a
  parenthetical on that paragraph; one §7.6 AH-10 note; one §7.6 Deferred note),
  `docs/042_LECTURE_INTELLIGENCE_PIPELINE.md` (one §9.3 C-13 parenthetical; one §9.3 Deferred note;
  one §18 Confirmed parenthetical — all three recording that Final Selection does not exist), and
  `docs/030_DATA_MODEL.md §11.1` (one cross-reference paragraph).
- Released Text Preserved: verified mechanically. The applied diff is +61/−6 lines; of the six
  replaced lines, four are paragraphs whose original text is preserved verbatim with additions
  appended or inserted (checked by reconstruction), and two are the `044` header's `Version` and
  `Last Updated` metadata fields. No released sentence was deleted or reworded.
- Notes: Resolves the Final Selection Gate Evaluation's verdict C at the contract level only, as
  **Decision B**. No schema, code, or Goal is introduced. The next step after acceptance is an
  implementation milestone — Edit Export Assembly for the effective-transcript generation — with this
  contract as its basis. Linking this generation to `044 §21` Artifact and `§22` serialization
  remains undecided and still needs its own gate.

## Related Documents

- `PATCH-0015-edit-pipeline-export-application-foundation.md`
- `PATCH-0016-edit-export-assembly-scope.md`
- `PATCH-0017-edit-export-artifact-representation.md`
- `PATCH-0032-effective-transcript-edit-candidate-admission-boundary.md`
- `PATCH-0033-effective-transcript-review-admission-boundary.md`
- `PATCH-0034-effective-transcript-review-authority-history-boundary.md`
- `../docs/044_EXPORT_PIPELINE.md`
- `../docs/043_REVIEW_PIPELINE.md`
- `../docs/042_LECTURE_INTELLIGENCE_PIPELINE.md`
- `../docs/030_DATA_MODEL.md`
- `../docs/041_SUBTITLE_PIPELINE.md`
