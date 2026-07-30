# PATCH-0034

- Title: Effective-Transcript Review Authority History and Current Selection Boundary (043)
- Status: Accepted
- Priority: High
- Trigger: Architect Decision (Review Authority History / Current Selection Gate Evaluation — verdict
  "B: targeted Blueprint PATCH required first", resolved documentation-only)
- Created: 2026-07-30
- Target Blueprint: `docs/043_REVIEW_PIPELINE.md` (§3.5 representation note; §7.5 forward notes on
  R-4, on the `040 §18` distinction, and on the recorded consequence; new §7.6; §15.1 confirming
  note; §15.3 and §15.4 scope notes; header amended), `docs/030_DATA_MODEL.md` (§11.1
  cross-reference)

---

## Status

Accepted. **Documentation only.** This PATCH encodes the Architect Decision that unblocks a Current
Selection milestone for the effective-transcript generation. It adds no implementation, no schema
change, no migration, no application code, no repository, no validator, no CLI, no demo, no golden,
and creates no records. The SQLite schema remains **v51**.

## Context

`PATCH-0033` fixed the effective-transcript generation's Review admission boundary (`043 §7.5`,
R-1…R-12) and GOAL-028 implemented it at schema v51:

```text
Lecture Analysis Input Admission (GOAL-024/025 chain root)
  → Analysis Finding (042 §8.2, GOAL-025)
    → Edit Candidate (042 §9.3, GOAL-027)
      → ReviewDecision (+ at most one ApprovedEditDecision) (043 §7.5, GOAL-028)
```

`§7.5` deliberately left one gap open and recorded it as a Confirmed consequence: because R-9 stores
no ordinal and R-4 forbids any field that could express currentness, a person who reverses a judgment
on one Candidate (`accept` → `reject` → `accept`) produces a repository holding two contradicting
records **with no ordinal, no `previous` link, and no timestamp**, and the contract does not answer
which one is operative. `§7.5` stated that closing the gap requires "an authority-history contract
analogous to `040 §18` H-5/H-6, fixed by a separate approved PATCH". This PATCH is that instrument.

## Trigger

The Review Authority History / Current Selection Gate Evaluation returned **B — targeted Blueprint
PATCH required first**, on three verified grounds:

1. `§7.5` R-4 does not merely omit currentness; it states that mutable current, stale, and selection
   flags and lifecycle state are not added and that **adding in that direction is prohibited**.
2. `§7.5`'s **Sections Not Re-scoped** clause names "revision·supersession" and "current-selection
   semantics" among the decisions it does not make, and states that they are made by "the approved
   PATCH of that time" — the Blueprint itself names a PATCH as the instrument.
3. The released v51 persistence carries **no ordering input at all** — no `sequence`, no previous
   link, no timestamp — and R-9 prohibits row counts, `MAX(sequence) + 1`, wall-clock, insertion
   order, and race-dependent order, while R-10 prohibits rowid participation. A derived current
   selection is therefore impossible over released persistence, so new persisted state is required,
   which is exactly the direction R-4 prohibits without an approved decision.

The gate also established why this is **not** a matter requiring a fresh product decision: the
requirement is already Confirmed in `§3.5` ("결정이 현재 유효한지, 이후 판단으로 대체되었는지 …
구분할 수 있어야 한다"), only its representation was deferred (`§15.4`), and the mechanism already
exists twice in released form — `040 §18` H-5…H-8, and the effective generation's own subtitle Review
decisions, which reuse that idiom exactly and persist it as `subtitle_effective_review_decisions`
(`sequence`, `previous_decision_id`, `UNIQUE(subject, sequence)`, `sequence = 0` ⟺ no previous).

## Problem

Four problems had to be resolved together, and the gate's route (ii) — keep R-10, scope the history
per (Candidate, actor), decline cross-actor arbitration — is the one adopted here.

**P-01 The ordinal cannot enter the released identities.** `§7.5` R-10 fixes the `ReviewDecision`
identity as anchor + decision kind + **human actor**, and R-11 fixes its convergence. Both are
released. Adding a `sequence` to that composition would change the identity **value** of every
existing record, mutating released meaning — prohibited by the additive-evolution contract
(`041 §15` E1, `042 §8.2` D-11 / `§7.2` S-12 / `§9.3` C-12, `043 §7.5` R-12). Conversely, an ordinal
that does **not** participate in a content-derived identity cannot distinguish two positions at all,
because the third submission of `accept` converges on the first identity. Neither route works by
modifying the two canonical records.

**P-02 The actor makes the history non-linear.** Both released precedents derive identity from
`(anchor, kind, sequence)` and keep the actor as *provenance only*, producing one linear history per
anchor where the latest change wins regardless of who made it. `§7.5` R-10 requires the **opposite**
for this generation — the actor must participate — and states the reason as a product one: `§7.4`
includes the human actor reference in the `ReviewDecision`'s minimal canonical information and fixes
Human Authority as the record's meaning, so two people's judgments must stay distinguishable.
Adopting the released composition verbatim would therefore overturn a Confirmed product decision
released one commit earlier, and would additionally answer `§15.3`'s open multi-user question by
implication ("two people's differing judgments are one linear history in which the latest wins").
That is a product decision this PATCH declines to make.

**P-03 The multi-actor case must be closed without answering `§15.3`.** `§15.3` lists "여러 사용자가
같은 Review 대상에 판단할 경우 권위와 Conflict를 어떻게 해석해야 하는가" as an open question
requiring validation, and `§15.4`/`§7.4` keep multi-user conflict resolution deferred. But `§3.12`
**already** fixes the policy for the case where the relationship among several users' judgments
cannot be safely determined: it is a Conflict, it is surfaced so a person can judge again, and it is
never auto-resolved. A bounded contract can therefore decline arbitration on Confirmed grounds.

**P-04 Existing released records cannot be retrofitted.** Records admitted under `§7.5` carry no
history position. Synthesizing positions for them would require an ordering that is not persisted
anywhere — any backfill would be fabrication, which is the same class of act that `040 §18` H-10 and
`041 §15` E6 prohibit for execution provenance.

## Architect Decision (Confirmed)

Twelve decisions, encoded normatively in `043 §7.6` as AH-1…AH-12. Summarized here; `§7.6` is
authoritative.

1. **AH-1 Scope and Instrument.** Effective-transcript generation only. `§7.4`'s legacy contract,
   `§7.5` R-1…R-12, and `§3`/`§7`'s concepts are neither deleted, rewritten, nor retroactively
   reinterpreted. The legacy generation gains no authority history from this subsection.
2. **AH-2 Requirement Basis.** No new product requirement is created: `§3.5` already required the
   current/superseded distinction and `§15.4` deferred only its representation. `§3.5`'s prohibition
   on a fixed status list and a transition model stands, and so does `§7.5` R-4's Alternative A.
3. **AH-3 Released Idiom Reused.** `040 §18` H-5 (append-only history, supersession via a previous
   link) and H-6 (current derived as the highest `sequence`, never stored twice) are reused as
   **domain meaning**, not as persistence columns (`041 §15` E3's semantic-reuse idiom). A
   latest-row heuristic, a bare auto-increment, and a mutable flag can never be the basis of current;
   that prohibition is grounded in H-6 and `§7.5` R-4, with `041 §15` E7 cited only as the adjacent
   precedent that bars the same items as **identity** inputs.
4. **AH-4 Separate History Record, Canonical Records Unchanged.** The history lives in a **new
   canonical record**; no ordinal, previous link, or status column is added to `ReviewDecision` or
   `ApprovedEditDecision`. This is what preserves P-01: the two released records keep their exact
   identity composition and convergence behaviour.
5. **AH-5 Authority History Entry.** Durable, immutable, insert-only, identity-owning,
   provenance-bearing, replay-safe. Minimal canonical information: its identity, exactly one anchor
   Edit Candidate (`042 §9.3`), one human actor reference, the position `sequence`, exactly one
   referenced `ReviewDecision`, and for `sequence > 0` the previous position it supersedes. It
   **duplicates no referenced payload** — kind, approved range, approved label, and approved
   rationale stay owned by the two canonical records and are reached through the anchor. No status,
   currentness, wall-clock, execution provenance, or Domain Result.
6. **AH-6 History Scope Is Per Candidate and Actor.** Because R-10 keeps the actor in the decision
   identity, history exists per **(Candidate, actor)**: `sequence` contiguous from 0, `sequence = 0`
   ⟺ no previous, `sequence > 0` requires one, no self-reference, at most one record per
   (Candidate, actor, sequence). **One `ReviewDecision` may occupy several positions** — in
   `accept` → `reject` → `accept` the canonical records converge to two while the history holds
   three positions, with positions 0 and 2 referencing the same `accept` record. A per-decision
   uniqueness constraint on the history relation (the shape `§7.4` uses for `ApprovedEditDecision`)
   is therefore **prohibited**: it would make reversal history unrepresentable, which is the very
   case this subsection exists to close.
7. **AH-7 Append Rule.** No history → insert at `sequence` 0. Referenced decision identical to the
   current head → **reuse**, no new position. Different → **append** at `sequence + 1`, superseding
   the head. This `sequence + 1` derivation is **explicitly authorized here** and is not what R-9
   prohibits: R-9 governs the **per-admission** ordinal, which still does not exist. Wall-clock,
   insertion order, rowid, row count, race-dependent order, and any ordinal derived from anything
   other than that exact history's persisted head remain prohibited.
8. **AH-8 Derived Current, Never Stored.** Per (Candidate, actor), the current judgment is the
   highest `sequence`, derived from persisted rows only. Superseded positions remain valid immutable
   history and are never deleted, rewritten, or re-numbered (`§2.8`, `§3.9`, `§13`, `§7.5` R-5).
9. **AH-9 Current Selection per Candidate and the Multi-actor Boundary.** Exactly one actor with
   history → that actor's current judgment **is** the Candidate's current operative judgment. Two or
   more → **no current operative judgment is derived**; the situation is a `§3.12` Review Conflict,
   surfaced and never auto-resolved. Priority among actors, recency across actors, role or permission
   ranking, and every other automatic authority ordering are **prohibited**. `§15.3`'s question is
   **not answered** — it is explicitly declined, and `§15.4`'s multi-user conflict resolution stays
   deferred. This resolves P-02 and P-03 without overturning R-10.
10. **AH-10 Standing Orthogonality.** Appending requires `§7.5` R-3's standing to be `current`;
    existing positions are never modified or re-numbered by an authority change (`§7.5` R-5), and a
    superseded chain is never corruption. Being the current judgment is **not** Export eligibility —
    linking this generation's approved records to `044` remains a separate decision.
11. **AH-11 Identity Direction and Reachability.** Application-owned and deterministic from the
    immutable anchor and the stable position; no provider, execution, `DomainResult`, UUID,
    timestamp, wall-clock, rowid, path, or mutable currentness participates. Exact hash composition
    is delegated to the implementation milestone (`041 §15` E7, `042 §8.2` D-8 / `§7.2` S-10 /
    `§9.3` C-10, `§7.5` R-10 precedent), which must state which persisted fields participate and
    record the conflict-branch reachability under `§7.5` R-10's (A)/(B) accounting — and must keep
    the semantic-equality check even under (B). A semantically different record for an existing
    identity is refused as an explicit conflict, never overwritten (`040 §18` H-9).
12. **AH-12 Persisted Representation and Atomicity.** Meaning only; the physical form is a
    **strictly additive new versioned representation**. Legacy relations and this generation's
    released v51 relations stay exactly as they are — no backfill, no dual-write, no
    reinterpretation, and released rows keep their identities and columns. A judgment's decision, its
    optional approval, and its history position are recorded as **one atomic all-or-nothing unit**
    (extending `§7.5` R-11); no partially recorded admission may look valid. Resolving P-04: a
    `ReviewDecision` admitted before this contract may carry **no** position and that is **not
    corruption** — absence means no recorded authority history for that (Candidate, actor)
    (`040 §18` H-2's "derived from absence" idiom), validation never flags it, **retroactive backfill
    of positions is prohibited**, and the next admission for that pair starts the history at
    `sequence` 0. The two rules attach to **different points in time** and therefore do not collide:
    all-or-nothing is a write-time transactional obligation, so no post-contract admission can
    produce a positionless judgment, while the tolerance is a read-time classification rule that
    gives a validator exactly one answer for the row shape it can observe. The converse shape — a
    position with no judgment — is structurally impossible because AH-5 makes the `ReviewDecision`
    reference mandatory. An implementation must record both enforcement points together and must not
    read the atomicity rule as licence to flag pre-existing positionless judgments.

## Affected Contracts

- `docs/043 §3.5` — one note: the current generation's representation of the distinction lives in
  `§7.6` and is derived, not a stored status field. The fixed-status-list prohibition is retained.
- `docs/043 §7.5` — three forward notes, added without deleting or rewriting a single existing
  sentence: R-4's prohibition is scoped to mutable state **on the two canonical records** and stands;
  the authority-history ordinal that the `040 §18` distinction left "neither introduced nor denied"
  is now introduced by the approved PATCH that same block required; and the recorded consequence's
  gap is closed **for kind reversal only**.
- `docs/043 §7.6` — new subsection, AH-1…AH-12 plus "Sections Not Re-scoped" and "Deferred".
- `docs/043 §15.1` — one Confirmed note recording the above.
- `docs/043 §15.3` — one note: `§7.6` declines the multi-user question, which stays open.
- `docs/043 §15.4` — one note: the representation of the current/superseded distinction is confirmed
  for this generation; everything else in the list stays deferred.
- `docs/030 §11.1` — one clause separating the generation-neutral record contract from the
  per-generation authority-history and current-selection representation.
- Unchanged in meaning: `043 §1`–`§3.4`, `§3.6`–`§7.4`, `§8`–`§14`, `§16`–`§17`, all of `042`, all of
  `044`, and all of `040`/`041`.

## Required Blueprint Changes

- `docs/043_REVIEW_PIPELINE.md` — the `§3.5` note; three `§7.5` forward notes; new `§7.6`
  (AH-1…AH-12); one `§15.1` Confirmed bullet; the `§15.3` and `§15.4` notes; header `Amended By`
  reference added.
- `docs/030_DATA_MODEL.md §11.1` — one generation-neutrality clause, minimally extended.

## Legacy Compatibility

`§7.4`'s legacy execution-coupled contract is untouched and its records stay valid history; the
legacy generation gains no authority history (AH-1). The released v51 relations of this generation
are not altered, re-keyed, or backfilled, and every released identity keeps its exact value (AH-4,
AH-12). Nothing in this PATCH requires a migration; the implementing milestone's migration must be
strictly additive.

## Deferred (unchanged by this PATCH)

Review Session persistence, a separate full Review History model, multi-Candidate Review Items and
grouping, **multi-user conflict resolution and the interpretation of authority across actors**
(`§15.3`), comprehensive human authority policy, Candidate reconciliation, **withdrawal and
revocation of a human judgment**, stale detection, Review Context quality criteria, Review UI and
external Review API, provider-assisted Review, confidence/priority/severity/quality score, the
history representation of a **same-kind, different-approval** resubmission, and linking this
generation's `ApprovedEditDecision` to `044` Export.

## Explicit Non-goals

- No implementation, schema, migration, application code, repository, validator, CLI, demo, golden,
  or test is added; the schema stays at v51.
- No fixed Decision Status list, state machine, or transition model is introduced.
- No mutable current, stale, or selection flag is introduced anywhere.
- No released identity composition is changed and no released row is reinterpreted or backfilled.
- No automatic ranking among actors is introduced, and `§15.3` is not answered.
- `044` Export, `042`'s subsections, and `§7.4`'s legacy contract are not re-scoped.

## Acceptance Criteria

- [x] The authority-history and current-selection boundary of the effective-transcript generation is
  Confirmed in the Blueprint, without deleting or rewriting `§7.4`'s or `§7.5`'s existing text.
- [x] The reason the ordinal cannot enter the released `ReviewDecision`/`ApprovedEditDecision`
  identities is stated, and the separate-record decision that follows from it is recorded (AH-4).
- [x] `§7.5` R-4's prohibition and R-9's per-admission prohibition are explicitly preserved and
  scoped rather than silently overridden, and the `sequence + 1` authorization is confined to the
  per-anchor history ordinal (AH-7).
- [x] The per-(Candidate, actor) scope is recorded together with its cause — R-10's Confirmed
  requirement that the actor participate in identity (AH-6).
- [x] The multi-actor outcome is recorded as a `§3.12` Conflict with **no** derived current, and
  `§15.3`'s question is explicitly declined rather than answered by implication (AH-9).
- [x] The treatment of records admitted before this contract is recorded, with retroactive backfill
  prohibited, its absence declared not to be corruption, and the write-time versus read-time split of
  the atomicity rule stated so a validator author cannot misread it (AH-12).
- [x] It is stated normatively that one `ReviewDecision` may occupy several history positions and
  that a per-decision uniqueness constraint on the history relation is prohibited — without it, the
  reversal case this PATCH exists to close would be unrepresentable (AH-6).
- [x] The remaining gap — a same-kind, different-approval resubmission stays an explicit conflict —
  is stated in both `§7.5` and `§7.6` rather than left for the implementer to discover.
- [x] Schema remains v51; no code file changes; one documentation commit with a clean working tree.

## Remaining Risk

**Same-kind, different-approval resubmission.** A second `modify` by the same actor with different
approved values still converges on one `ReviewDecision` identity whose single `ApprovedEditDecision`
already holds different values, so `§7.5` R-11 refuses it and no history position can be appended.
This PATCH deliberately does not close that case: representing it as history would require
re-scoping either `§7.4`'s "at most one `ApprovedEditDecision` per `ReviewDecision`" or R-10's
released identity composition, and the second would again mutate released identity values. The
consequence is that a person who wants to revise the *content* of an approval must be told it is
refused, not silently recorded. Both `§7.5` and `§7.6` state this, and closing it needs its own
approved PATCH.

**Derived current across a history-less record.** Because backfill is prohibited, a Candidate may
hold a released judgment with no history position, for which no current is derived. The implementing
milestone must expose that as "no recorded authority history", never as an error and never as
"no judgment exists".

## Result

- Status: **Accepted**
- Changed Blueprint Files: `docs/043_REVIEW_PIPELINE.md` (§3.5 note; three §7.5 forward notes; new
  §7.6 with AH-1…AH-12; §15.1 Confirmed note; §15.3 and §15.4 notes; header amended) and
  `docs/030_DATA_MODEL.md §11.1` (one generation-neutrality clause).
- Notes: Resolves the Review Authority History / Current Selection Gate Evaluation's verdict B at the
  contract level only. No schema, code, or Goal is introduced. The next step is an implementation
  milestone — Review Authority History and Current Selection for the effective-transcript generation
  — with this contract as its basis. Linking this generation's `ApprovedEditDecision` to `044` Export
  remains undecided and still needs its own gate.

## Related Documents

- `PATCH-0014-edit-pipeline-review-application-foundation.md`
- `PATCH-0025-first-human-authority-decision-on-correction-candidate.md`
- `PATCH-0029-effective-transcript-sourced-subtitle-candidate-contract.md`
- `PATCH-0033-effective-transcript-review-admission-boundary.md`
- `../docs/043_REVIEW_PIPELINE.md`
- `../docs/042_LECTURE_INTELLIGENCE_PIPELINE.md`
- `../docs/030_DATA_MODEL.md`
- `../docs/040_TRANSCRIPT_PIPELINE.md`
- `../docs/041_SUBTITLE_PIPELINE.md`
