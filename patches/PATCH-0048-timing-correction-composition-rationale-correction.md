# PATCH-0048

- Title: Human Timing Correction Composition Rationale Correction (040 §17 TC-18)
- Status: Accepted
- Priority: Low
- Trigger: `PATCH-0047`'s implementation (`implementation/139`) and the follow-up Architect Decision
  (`implementation/140`) disproved two factual premises inside the released TC-18 paragraph
- Created: 2026-08-25
- Target Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` (one additive follow-up note after the §17
  Human Timing Correction Candidate subsection's Composition paragraph; header amended).
  `docs/041_SUBTITLE_PIPELINE.md` and `docs/030_DATA_MODEL.md` are **not** amended.

---

## Status

**Accepted.** Applied to `docs/040_TRANSCRIPT_PIPELINE.md` (Blueprint 0.6, 2026-08-25) as one additive
follow-up note after the §17 Human Timing Correction Candidate subsection's Composition paragraph,
carrying RC-1…RC-8. The released TC-18 paragraph is preserved verbatim, including both sentences the
note corrects. `docs/041_SUBTITLE_PIPELINE.md` and `docs/030_DATA_MODEL.md` are not amended.

**Acceptance means the correction has been applied to the Blueprint.** Because this PATCH changes no
behaviour, there is no implementing milestone to follow: `SQLITE_SCHEMA_VERSION` stays **54**, no
migration exists, and no production code or test was changed by the application. The three
Implementation Requirements below are documentation invariants already asserted by released tests,
not outstanding work.

Composition and revision chaining remain Deferred, and their Product Decision gate remains
`MORE_EVIDENCE_REQUIRED` (`implementation/140`). This PATCH does not move that gate.

**This is a factual correction, not a policy change.** TC-18's conclusion — no automatic composition,
no implementation-chosen ordering — is preserved exactly. Only the reasoning offered for it is
corrected. It introduces no composition rule, no pairing rule, no candidate type, no Human Authority,
no schema change, no migration, and no behavioural change. It rewrites no released sentence.

## Context

`PATCH-0047` TC-18 fixed a safe boundary around competing text and timing corrections on one source
segment. The boundary was right. Two statements of fact inside the same paragraph were not, and both
were disproved by the implementation that `PATCH-0047` itself required.

Leaving them in place would be worse than a stylistic problem: they describe mechanisms a future
implementer would reasonably rely on. One claims a protection that does not fire; the other claims a
capability that does not exist.

## Blueprint evidence

Both errors were reproduced by executing the released chain against a real repository — not inferred
from documents. `implementation/139` §7 recorded the first; `implementation/140` §3 and §7.2 confirmed
both.

### The first error — the staleness premise

TC-18 states:

> Once either is accepted, the other's snapshot no longer matches the current segment, and TC-9's and
> K-3's stale checks refuse it.

**This never happens.** `§19` V-1's model is a complete snapshot: generation creates a **new**
replacement segment inside a **new** revision and never mutates the source segment. Executed:

```text
source S                       : text='둘째 문장'  start=10.0  end=20.0
after generating RT (text)     : S unchanged; M's timing snapshot still matches S
after generating RM (timing)   : created — no stale refusal; S still unchanged; RT ≠ RM
```

Both candidates remain independently applicable after either generation. Neither stale check fires,
because neither has anything to fire on.

### The second error — the sequential-correction claim

The same paragraph states:

> Sequential correction through the released lineage is available, since `§19` already supports a
> revision whose parent is another revision — a person may correct text, then author a fresh timing
> candidate against the resulting revision.

**It is not available.** `§17` K-1 requires a candidate's target segment to belong to the intake's
**current Raw Transcript**, and `§19` V-14 defers revision-on-revision chaining. A revision's
replacement segment is neither. Executed:

```text
timing candidate targeting RT's replacement segment -> refused at admission
```

V-12 says `parent_revision_id` *models* future chaining; it does not make chaining reachable. The
released contract is internally consistent — TC-18's sentence simply described a path the contract
does not open.

### What the safety property actually rests on

`§19` V-2: generation is *"정확히 하나의 후보를 지명하는 명시적 요청"*. Each generation applies exactly
one candidate to the Raw Transcript, so two accepted corrections produce two siblings and **no code
path merges them**. The prohibition holds for a structural reason, not a protective one.

## Decision

**RC-1 (Confirmed) — TC-18's conclusion is unchanged.** No automatic composition, no implicit merge,
no implementation-chosen application order, no latest-wins, no silent merge at `§20`, and no ad-hoc
activation of revision chaining. Nothing in this PATCH weakens any of these.

**RC-2 (Confirmed) — The staleness premise is disproved and is recorded as such.** A sibling
correction's generation does not mutate the source segment, so it does not make the other candidate's
snapshot stale. Both remain independently applicable and each may generate its own revision. TC-9's
and K-3's stale checks are real and unchanged; they simply do not fire in this situation.

**RC-3 (Confirmed) — The sequential-correction claim is disproved and is recorded as such.**
Correcting text and then authoring a timing candidate against the resulting revision is **not**
available: K-1 anchors a candidate to the current Raw Transcript and V-14 defers chaining. This
records what the released contract already says; it changes neither rule and un-defers nothing.

**RC-4 (Confirmed) — The real reason automatic composition is forbidden is the absence of a canonical
composition rule.** Not staleness. Specifically uncontracted, and left so:

- which accepted text correction and which accepted timing correction form a pair — `§18` H-6 derives
  current authority **per candidate**, so "the segment's accepted correction" has no referent, and a
  segment may carry several accepted candidates of each kind;
- which combination to use when more than one of either kind is accepted;
- whether composition is a distinct operation or revision chaining;
- composition provenance and identity;
- whether composition requires a new Human Decision;
- the identity policy for semantically equivalent composed revisions;
- the responsibility boundary between composition and `§20` selection.

**RC-5 (Confirmed) — Composition and revision chaining remain Deferred.** `§19` V-14 and `§20` S2-14
are unchanged. The composition Product Decision's gate is **`MORE_EVIDENCE_REQUIRED`**
(`implementation/140`): no observed case yet requires both corrections on one segment, and the
capability that would produce such cases has no usage history. A single genuine case reopens it.

**RC-6 (Confirmed) — Until that decision, an implementation may not compose or choose an order.** It
may not merge two corrections, apply them in an order of its choosing, select a pair by recency or
sequence, re-target a candidate on its own, or merge revisions at selection. `§20` selects one
persisted revision and never derives content.

**RC-7 (Confirmed) — Existing records are normal immutable history.** Text corrections, timing
corrections, sibling corrected revisions, Final Selections, SRT Artifacts and Materializations
created under `PATCH-0047` remain valid and are **not** reinterpreted, re-derived, marked incomplete,
or treated as awaiting composition. Nothing is back-filled. Two sibling revisions for one segment are
a correct state, not a defect.

**RC-8 (Confirmed) — Behaviour, schema and implementation are unchanged.** `SQLITE_SCHEMA_VERSION`
stays **54**. No relation, column, constraint or migration changes; no production code or test changes.
The current implementation already exhibits everything recorded here: independently applicable sibling
revisions, no automatic composition, and a selection path that chooses one persisted revision rather
than merging revisions.

## Non-goals

Not decided here, each requiring its own gate: adopting a composition operation; a combined
text+timing candidate; revision-on-revision chaining in any form, including a composition-only
special case; an application order; latest-wins or any pairing rule; accepted-candidate uniqueness; a
new Human Authority; a composition relation, schema or migration; automatic merge; merging at `§20`;
backfill; and any reinterpretation of existing sibling revisions.

Also out of scope, deliberately: the **text candidate admission replacement-segment asymmetry**
recorded in `implementation/140` §12. It is an implementation defect predating `PATCH-0047`, it
produces nothing incorrect (V-4 blocks application and K-9 makes such a candidate legal history), and
it belongs to its own `fix:` milestone.

## Required Blueprint Changes

Applied to `docs/040_TRANSCRIPT_PIPELINE.md` only.

1. **Header** — Blueprint version and Last Updated advanced; `PATCH-0048` added to `Amended By`.
2. **§17 Human Timing Correction Candidate subsection** — the released Composition (TC-18) paragraph
   is kept **verbatim**, followed by one additive follow-up note carrying RC-1…RC-8: the two
   disproved premises, the structural reason the prohibition holds, the real uncontracted gap, the
   preserved conclusion, the unchanged deferrals, and the immutability of existing records.

No other section is amended. `docs/041_SUBTITLE_PIPELINE.md` is not amended (no subtitle contract is
touched). `docs/030_DATA_MODEL.md` is not amended (no new data-model concept appears).

## PATCH Acceptance Criteria

Verified against the Blueprint amendment, before this PATCH may be marked `Accepted`.

- [x] The staleness premise is stated **disproved by implementation evidence**, with the reason
      (generation does not mutate the source segment) recorded.
- [x] The released TC-18 paragraph is present **verbatim**, deleted and rewritten nowhere.
- [x] The prohibition on automatic composition is stated **unchanged**.
- [x] The real gap is stated as the **absence of a canonical composition / pairing / provenance
      rule**, not staleness.
- [x] Sibling corrections are stated **independently applicable** after either generation.
- [x] **No latest-wins**, recency, or sequence-based pairing is introduced.
- [x] **No application order** is chosen.
- [x] Revision-on-revision chaining is stated **Deferred**, and the released claim that sequential
      correction is available is recorded as disproved.
- [x] **No new composition authority** is invented, and no new Human Decision kind appears.
- [x] Schema is stated unchanged (**v54**), with no relation, column or constraint touched.
- [x] No migration is introduced.
- [x] No production or test behaviour changes.
- [x] Existing records and artifacts are stated **not reinterpreted** and never back-filled.
- [x] **No released sentence in `docs/040` is deleted or rewritten** — prior PATCH notes included —
      verified line by line; `§17` gains an **additive note only**.

## Implementation Requirements

**None.** This PATCH changes no behaviour, so it creates no implementing milestone.

The following are **documentation invariants** — statements of what the released implementation
already does, asserted by tests that exist today (`implementation/139` §2). They are not new work:

1. Sibling text and timing revisions for one source segment coexist and are independently applicable.
2. No code path composes two corrections or chooses an application order.
3. `§20` selection resolves to exactly one persisted revision and never merges revisions.

## Consequences

- `§17` gains one additive note; every released sentence, including TC-18's own, is untouched.
- The Blueprint stops asserting two mechanisms that do not exist — a stale check that never fires and
  a sequential-correction path that admission refuses.
- The prohibition a future implementer must respect is unchanged, but it now rests on the reason that
  actually holds it up, so it cannot be argued away by observing that nothing goes stale.
- Composition and chaining remain Deferred at `MORE_EVIDENCE_REQUIRED`; existing sibling revisions,
  selections and artifacts are unaffected; schema stays v54.
