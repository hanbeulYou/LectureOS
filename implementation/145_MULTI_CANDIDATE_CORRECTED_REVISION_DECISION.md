# Multi-Candidate Corrected Revision — Architect Decision

- Status: Architect Decision (no PATCH, no Blueprint change, no implementation)
- Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` §17 K-1…K-14 / TC-1…TC-21, §18 H-1…H-14,
  §19 V-1…V-14, §20 S2-1…S2-14, §21 S3-1; `docs/041_SUBTITLE_PIPELINE.md` §7, §16
- Production impact: **none** — no PATCH, no Blueprint change, no schema change, no code change
- Related: `139`, `140`, `141`, `142`, `143`, `144`; `PATCH-0047`, `PATCH-0048`

## Decision summary

| | question | answer |
|---|---|---|
| **Q1** | Is multi-candidate application needed? | **Yes** — and it is **not a timing-only problem**. The one-candidate ceiling is general to `§19` generation; text correction has it identically (§4). |
| **Owner** | Where does it belong? | **`§19` generation (P1)** — an explicit request naming a set of accepted candidates, producing one persisted revision. Not chaining, not selection merge. |
| **Authority** | New Human Decision needed? | **No** (Authority A). The Accepts supply content authority; naming the set is V-2's explicit-request idiom at a higher cardinality. |
| **Atomicity** | Partial application? | **No.** All-or-nothing, with an explicit error naming what failed. |
| **Scope** | Timing only or same-kind general? | **Scope G — same-kind aggregation**, with one disclosure (§9). Cross-kind stays `PATCH-0048`-gated. |

**Gate: `PATCH_READY`.**

One thing this decision found that changes the design: **individual admission does not guarantee
pairwise safety** (§7). Any multi-candidate contract must revalidate the resulting snapshot.

## 1. The evidence

`144` completed the real-media E2E. One lecture (MVI_0147, 1.96 h, 2,370 segments):

```text
human review          8 findings → 4 ALIGNED, 4 corrections wanted
admitted              3 canonical Human Timing Corrections
generated             3 corrected revisions
deliverable together  1
```

Measured, not argued: selecting R05 after R03 dropped R03's correction out of the effective
transcript. Start drift the person measured: **+22.11 s, +19.16 s, +6.00 s**. All three were judged
necessary; the released model ships one.

At `137`'s ~8 material cases per lecture-hour, this is the operating ceiling, not an edge case.

## 2. What V-2 actually protects

> **V-2:** 수락은 권한 부여이고 생성은 적용이다 — 별개의 authority 경계다. Accept만으로 revision이
> 생기지 않으며 생성은 정확히 **하나의** 후보를 지명하는 **명시적 요청**이다. apply-all/best/latest·
> 암묵적 후보 발견·multiple-candidate merge·ranking·overlap 해소는 없다.

Read carefully, V-2 bundles two separate things:

- **A principle** — generation is an *explicitly named* request. No implicit discovery, no
  apply-all, no best, no latest, no ranking. This is what protects Human Authority.
- **A cardinality** — exactly one.

The principle is what makes the boundary safe. The cardinality is what this decision reconsiders.
An explicit request naming *three* candidates violates nothing in the first list: nothing is
discovered, ranked, or chosen by the system.

But V-2 does name "multiple-candidate merge", and `§19` V-14 defers **"multiple-candidate 적용"** —
application, listed separately from merge — while `§20` S2-14 defers "multi-candidate revision".
**So P1 is un-deferring a named deferral, not discovering permission.** It needs a PATCH; it cannot
be read into the released text.

## 3. The aggregate already models it

```text
CorrectedTranscriptRevision.correction_candidate_ids : tuple[CorrectionCandidateId, ...]
corrected_transcript_revision_candidates             : (revision, ordinal) → candidate
corrected_transcript_revision_segments               : (revision, ordinal) → segment
```

V-1 lists `correction_candidate_ids` — **plural** — as part of the canonical aggregate it reuses
unchanged. The relation is ordinal-keyed for an ordered membership. **The persistence is already
multi-candidate capable**; only the generation services write a one-element tuple:

```python
correction_candidate_ids=(candidate_identity,)      # text
correction_candidate_ids=()                          # timing (no text candidate participates)
```

So P1 requires **no schema change**. That is a strong argument for it over every alternative.

## 4. This is not a timing problem — Q1 answered

Driven directly: three text corrections on three different segments of one transcript.

```text
accepted text corrections 3 → revisions 3
  revision 0: corrected segments 1 / 3   candidate_ids = 1
  revision 1: corrected segments 1 / 3   candidate_ids = 1
  revision 2: corrected segments 1 / 3   candidate_ids = 1
```

**A lecture with ten typos can deliver one corrected typo.** The ceiling is in `§19` generation, not
in the timing sibling. `144` surfaced it through timing because that is where the human review
happened, not because timing is special.

This reframes the question: it is not "should timing corrections aggregate?" but **"should a
Corrected Revision be able to carry more than one correction?"** — and V-1's own plural field says
the aggregate was always shaped for yes.

## 5. Options

| | approach | verdict |
|---|---|---|
| **P0** | keep one-candidate siblings | **Rejected.** It cannot express what a person decided. Three necessary corrections, one deliverable, is not a defensible product state now that it is measured rather than hypothetical. |
| **P1** | explicit multi-candidate generation at `§19` | **Decided.** Smallest surface: no schema change, aggregate already plural, set-identity idiom already released (§8), `§20` untouched. |
| **P2** | revision chaining | **Rejected**, and `140` CC-5 stands. It needs K-1, V-4, S2-8 and V-12/V-14 changed plus cycle and depth contracts, to reach what P1 reaches inside `§19`. Introducing P1 does **not** open chaining. |
| **P3** | merge at `§20` selection | **Rejected outright.** S2-3 fixes two authority actions; the record holds one nullable revision under a `CHECK`. Merging there would invert the `§19 → §20` direction, produce an effective transcript matching **no persisted revision**, and break `§21` S3-1's separation of resolution from consumption. |
| **P4** | another released idiom | None found. |

## 6. Human Authority — Authority A

**No new Human Decision is required.**

The reasoning is `140` CC-3's, applied to a different axis. Each candidate's Accept already carries
the content authority: "this segment's interval should be X." The corrections target **disjoint
segments**, so combining them creates no meaning that neither person approved — unlike cross-kind
composition, where the combination is a third state.

V-2 already separates the two boundaries: Accept authorizes, generation applies, and generation is
an *explicit request* — **not** a `§18` record. Naming a set fits that shape exactly.

**What must not follow from this:** no `apply-all`, no "every currently accepted candidate", no
latest-wins, no ranking. The set is named, every time, in full. If a caller wants all of them, the
caller enumerates all of them.

## 7. Cross-candidate validation is required — the design-changing finding

`TC-7` validates a proposal against the **original** Raw Transcript neighbours
(`raw_transcript.segment_ids`). Two individually valid corrections can therefore collide. Constructed
and executed:

```text
original   S1=[0.0, 2.5]   S2=[10.0, 20.0]        gap 7.5 s

T1: S1 → [0.0, 8.0]    ADMITTED   (next original neighbour starts 10.0 — no overlap)
T2: S2 → [4.0, 20.0]   ADMITTED   (prev original neighbour ends 2.5 — no overlap)

applied together:  S1=[0.0, 8.0]  S2=[4.0, 20.0]  →  4.0–8.0 OVERLAPS
```

**Individual admission does not imply pairwise safety.** A multi-candidate contract must revalidate
the **resulting complete snapshot** for ordering and non-overlap.

Critically, this needs **no new rule**: `§14` A-10's structural vocabulary and the released
`PATCH-0039` ε already define ordering and non-overlap, and `041` §16 already refuses overlapping
cues. The revalidation reuses them. **No new threshold is introduced, and none may be.**

This also means P1 is *safer* than P0 in one respect: today nothing checks the pair, because the pair
can never be delivered together. P1 makes the check both possible and mandatory.

## 8. Identity and ordering — a released idiom already exists

The repository already derives an identity from an anchor **plus an exact membership**:

```python
derive_edit_export_assembly_identity(source_timeline_id, approved_edit_decision_ids)
    digest = sha256({contract, contract_version, timeline, "members": [...]})
```

with the documented reasoning that *"binding the membership makes an identical re-admission converge
and a genuinely different scope a new immutable record."* That is precisely what
`revision(T1) ≠ revision(T1,T2) ≠ revision(T1,T2,T3)` needs. **No new hash recipe is invented.**

**Canonical order.** The corrections target disjoint segments, so `[T1,T3,T2]` and `[T3,T2,T1]` are
the same logical request and must converge on one identity. The canonical order is the **source
segment's ordinal in the Raw Transcript** — already canonical, already the revision's own segment
order, and meaningful rather than arbitrary. Caller order is normalised, not preserved.

**Replacement segment identity is already revision-independent.** Today it derives from the
generation digest of `(candidate, authorizing decision)`:

```python
digest = derive_timing_generation_digest(candidate_id, decision_id)
replacement = TranscriptSegmentId(f"transcript-segment:{digest}:0")
```

Nothing about the revision participates. So the replacement produced by T1 is the **same entity**
whether it appears in `revision(T1)` or `revision(T1,T2,T3)` — which is correct, because the
corrected segment is a function of the correction, not of which revision carries it. A segment may
belong to several revisions; `corrected_transcript_revision_segments` is keyed by
`(revision, ordinal)`. One implementation consequence for the PATCH: the generation persistence
currently treats an existing replacement segment as a collision and must instead reuse it.

`§19` V-8's entity-identity / content-identity separation is preserved unchanged.

## 9. Scope — G, with a disclosure

**Scope G (same-kind aggregation, both correction kinds), not T (timing only).**

Why: §4 proved the ceiling is structurally identical for text and timing — same generation shape,
same aggregate, same plural field, same persistence. A timing-only rule would leave `§19` with two
different cardinality rules for two sibling paths, which is exactly the asymmetry that produced the
`141` defect. The mechanism is one mechanism.

**The disclosure, because a reviewer should push here:** the *operational need* is evidenced only for
timing. Nobody has hit the text ceiling in practice. Scope G is chosen for structural coherence, not
because text multi-correction demand is demonstrated. A reader who weighs evidence-alignment above
structural coherence would choose Scope D and defer text — that is a defensible reading, and it is
recorded rather than argued away.

**Cross-kind remains forbidden.** A set mixing a text candidate and a timing candidate is rejected,
whether the targets are the same segment or different ones. `PATCH-0048`'s composition gate stays
`MORE_EVIDENCE_REQUIRED` and **this decision does not move it** — that question is *which text
correction pairs with which timing correction on one segment*, and it remains unanswered.

## 10. Same-segment plurality

Confirmed executable: **two accepted timing candidates on one segment coexist** (the K-8 idiom, which
`PATCH-0047` TC-15 inherits). So a set may not contain two candidates targeting the same segment —
applying both is meaningless and choosing between them would be the system deciding.

**That must be an explicit conflict, refused by name.** Not latest-wins, not first-wins, not
highest-sequence. If a person wants a particular one, they name it and omit the other.

## 11. Atomicity — all or nothing

Given `[T1, T2, T3]` where T3 is stale or no longer Accepted: **the whole generation fails**, with an
error naming T3.

The reason is authority, not convenience. The caller explicitly named three corrections. Producing a
revision containing two of them would be the system deciding which corrections a person's request
actually meant — the precise thing V-2's "apply-all/best/latest 없음" forbids, arriving through the
back door. A partial result would also be provenance-ambiguous: the revision would claim a membership
the request did not ask for.

The caller re-issues with the set they want.

## 12. Complete snapshot semantics unchanged

```text
Raw:       S1  S2  S3  S4  S5
accepted:  T2 → R2,  T4 → R4
revision:  S1  R2  S3  R4  S5
```

Exactly V-1's complete snapshot — ordered segment references, unchanged source segments keeping their
identity, corrected segments carrying `replaces_segment_id`. **No patch/delta representation**, which
V-1 forbids. The only difference from today is the number of replaced positions.

## 13. `§20` and chaining stay where they are

`§20` remains a selector over one persisted revision. P1 deliberately produces the aggregate **before**
selection so that `§20`, `§21` and `041` need no change at all — the revision they consume is a
normal revision that happens to carry three corrections.

Revision-on-revision chaining stays Deferred (`140` CC-5, V-14, S2-14). **Introducing P1 does not
open it**, and the PATCH must say so: `parent_revision_id` stays unused, and a multi-candidate
revision's parent remains the Raw Transcript.

## 14. Architect Decisions

**MC-1 (Decided)** — Multi-candidate application is needed. One real lecture produced three necessary
corrections and can deliver one; the ceiling is `§19`-wide, not timing-specific.

**MC-2 (Decided)** — The owner is `§19` generation (P1). An explicit request naming a set of accepted
candidates produces one persisted `CorrectedTranscriptRevision`. Not chaining (P2), not selection
merge (P3).

**MC-3 (Decided)** — No new Human Authority (Authority A). Accepts supply content authority; naming
the set is V-2's explicit-request idiom at higher cardinality. No `apply-all`, no implicit discovery,
no ranking, no latest-wins.

**MC-4 (Decided)** — The resulting complete snapshot must be revalidated for ordering and non-overlap,
because individual admission does not imply pairwise safety (§7, counterexample executed). Reuses
A-10 and the released `PATCH-0039` ε. **No new threshold.**

**MC-5 (Decided)** — Generation is **atomic**. Any ineligible member fails the whole request with an
explicit error naming it. No partial application.

**MC-6 (Decided)** — Identity binds the anchor and the **exact membership**, following the released
Edit Export Assembly idiom. Canonical order is source-segment ordinal, so permutations of one logical
request converge. Replacement segment identity stays revision-independent and is reused across
revisions.

**MC-7 (Decided)** — Two candidates targeting the same segment in one set is an **explicit conflict**,
refused by name.

**MC-8 (Decided)** — Scope G: same-kind aggregation for both correction kinds, with §9's disclosure.
**Cross-kind sets are refused**, and `PATCH-0048`'s gate is unmoved.

**MC-9 (Decided)** — `§20`, `§21` and `041` are unchanged; revision chaining stays Deferred.

**MC-10 (Decided)** — **No schema change is anticipated.** The aggregate, both membership relations,
and the generation binding relations already carry what P1 needs. The generation binding relation may
need its cardinality reconsidered at implementation time — it currently holds one candidate per
generation — and that is the one place a PATCH should check before claiming "no migration".

## 15. Deferred

- Cross-kind (text + timing) composition — `PATCH-0048`, `MORE_EVIDENCE_REQUIRED`, untouched.
- Revision-on-revision chaining — `140` CC-5, V-14, S2-14.
- Which correction a person *should* pick when two target one segment — MC-7 refuses the set; it does
  not decide the product answer.
- Any batch or bulk authoring surface. MC-3 requires an enumerated set; how an operator assembles one
  is tooling, not contract.
- Provider timing refinement — `PATCH-0047` TC-21.

## 16. Gate

**`PATCH_READY`.**

Everything the gate requires is closed: the need is evidenced and measured, the owner is decided with
the alternatives refuted on released contract, the authority question is answered without inventing
one, ordering and identity reuse a released idiom, conflict and atomicity semantics are fixed, the
cross-candidate validation requirement is proven by counterexample, and schema impact is anticipated
as none.

### Proposed PATCH scope (not written here)

```text
PATCH-0049 — Multi-Candidate Corrected Revision Generation
Target      docs/040_TRANSCRIPT_PIPELINE.md
            §19 — V-2 cardinality amended by additive note; V-14 "multiple-candidate 적용"
                  un-deferred; new subsection carrying MC-1…MC-10
            §20 — forward note stating selection is unchanged and still selects one revision
            §17 — forward note recording that admission is unchanged and that TC-7 remains an
                  individual check, with cross-candidate revalidation owned by §19
Not amended docs/041, docs/030
Preserved   V-1 complete snapshot, V-8 identity separation, K-8 / TC-15 candidate plurality,
            PATCH-0048 composition gate, V-14 / S2-14 chaining deferral
```

## 17. Result

```text
Capability needed:                       Yes — measured, one lecture, 3 needed / 1 deliverable
Timing-only problem:                     No — text correction has the identical ceiling (proven)
Chosen owner:                            §19 generation, explicit multi-candidate request (P1)
Revision chaining:                       Deferred, unchanged (P2 rejected)
Selection-layer merge:                   Rejected (P3) — would invert §19→§20 and break §21 S3-1
New Human Authority required:            No (Authority A)
Automatic candidate discovery:           Forbidden — no apply-all, no latest-wins, no ranking
Cross-candidate revalidation:            Required — individual admission proven insufficient
New threshold:                           None — reuses A-10 and the released PATCH-0039 ε
Atomicity:                               All-or-nothing, explicit error naming the failed member
Same-segment candidates in one set:      Explicit conflict, refused by name
Identity:                                Anchor + exact membership, released Assembly idiom,
                                         canonical order = source segment ordinal
Replacement segment identity:            Revision-independent, reused across revisions
Scope:                                   G — same-kind, both correction kinds (disclosure in §9)
Cross-kind composition:                  Still forbidden; PATCH-0048 gate unmoved
Schema change anticipated:               None — aggregate and relations already plural
                                         (one item for the PATCH to verify: MC-10)
Existing records changed:                No; no backfill

Decision gate:                           PATCH_READY
Next milestone:                          PATCH-0049 (scope above), then implementation

Requires Architect Decision:             No — MC-1…MC-10 are this record
Requires Blueprint Clarification:        No
Requires Blueprint PATCH:                Yes — PATCH-0049
Requires Schema Change:                  Not anticipated (MC-10)
Requires Migration:                      Not anticipated
Requires additional human review:        No
Requires additional measurement:         No
```
