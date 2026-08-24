# Text + Timing Correction Composition and Revision Chaining — Architect Decision

- Status: Architect Decision (no PATCH, no Blueprint change, no implementation)
- Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` §17 K-1…K-4 / Human Timing Correction Candidate
  (TC-1…TC-21), §18 H-1…H-14, §19 V-1…V-14, §20 S2-1…S2-14; `docs/041_SUBTITLE_PIPELINE.md` §16
- Production impact: **none** — no PATCH, no Blueprint change, no schema change, no code change
- Related: `136`, `137`, `138`, `139_HUMAN_TRANSCRIPT_TIMING_CORRECTION.md`; `PATCH-0042`,
  `PATCH-0046`, `PATCH-0047`

## Decision summary

| | question | answer |
|---|---|---|
| **TC-18's stale rationale** | is it true? | **No.** Empirically disproved (§3). The conclusion stands; the reason given for it does not. |
| **Problem A — composition** | should accepted text + timing corrections be combinable? | **The boundary is decided; the necessity is not.** If ever built it belongs at `§19` generation as an explicit request naming one text and one timing candidate — never at `§17`, `§20`, or `041`. Whether to build it needs usage evidence that does not yet exist. |
| **Problem B — chaining** | should a Corrected Revision's segment be correctable? | **No, and it stays `V-14` Deferred.** It is a strictly larger contract change than composition and solves the same problem worse (§7). |

One defect was found on the way (§12) and is reported rather than fixed here.

## 1. What was investigated

Released contracts read in full: `§17` K-1…K-4 and the `PATCH-0047` subsection, `§18` H-1…H-14,
`§19` V-1…V-14, `§20` S2-1…S2-14, `041` §16 readability severities. Production code traced:
`correction_candidate_admission`, `timing_correction_candidate_admission`, both decision services,
both generation services, `corrected_revision_selection`, `readable_subtitle_validation`,
`TranscriptSegment`, `CorrectedTranscriptRevision`, and the v54 relations.

**Nothing below is inferred from documents.** Every structural claim was executed against a real
repository built through the released chain, and the probe results are quoted where they matter.

## 2. Current sibling revision semantics — measured

For one source segment S with an accepted text candidate T and an accepted timing candidate M:

```text
RT : parent_raw_transcript set, parent_revision_id = None, correction_candidate_ids = 1
RM : parent_raw_transcript set, parent_revision_id = None, correction_candidate_ids = 0
source segment S : text unchanged, start/end unchanged
RT replay -> reused        RM replay -> reused
```

Both are children of the Raw Transcript. Neither is a child of the other. Neither invalidates the
other, and `§20` selects exactly one — its record carries a single nullable `corrected_revision_id`
under a `CHECK`, so "both" is not expressible in the selection vocabulary at all.

**Competing corrections are real, and the problem is N×M, not 1×1.** Driving two accepted text
candidates and two accepted timing candidates against one segment produced **four** sibling
revisions, all valid, all selectable:

```text
accepted text candidates on S   : 2
accepted timing candidates on S : 2
corrected revisions             : 4
```

Nothing in `§18` limits a segment to one accepted candidate. H-6's *current authority* is derived
**per candidate**, not per segment, so the phrase "the segment's accepted text correction" has no
referent in the released model.

## 3. TC-18 correction — the rationale is false, the conclusion is not

`PATCH-0047` TC-18 and the `§17` subsection both state:

> Once either is accepted, the other's snapshot no longer matches the current segment, and TC-9's and
> K-3's stale checks refuse it — which is detection, not resolution.

**This does not happen.** Generation never mutates the source segment; it creates a *new* replacement
segment inside a new revision (V-1's complete-snapshot model). The probe above confirms S is
byte-identical after both generations, and both candidates replay as `reused` rather than failing
stale. `139` recorded this; this record makes it the canonical correction.

So the safety property TC-18 wanted holds, but for a different and stronger reason:

```text
claimed : composition is prevented because one correction makes the other stale
actual  : composition never occurs because each generation applies exactly one candidate
          to the Raw Transcript (V-2), so the two results are siblings that no code path merges
```

The actual gap is therefore **not** a staleness gap. It is:

> There is no canonical rule for combining two independently accepted corrections into one corrected
> state — specifically, no released way to say *which* text candidate and *which* timing candidate a
> combined result is made of, because `§18` derives authority per candidate and `§19` V-2 requires an
> explicit request naming exactly one.

That is the real subject of Problem A, and it is a naming problem before it is a merging problem.

## 4. Human Authority — is composition a new judgment?

Two facts decide most of this.

**4.1 The two axes provably do not touch each other.** Text generation copies `start`/`end` from the
source segment; timing generation copies `text` byte-identically. Both are asserted by tests in `139`.
So the content of a composed segment is fully determined by its inputs — `(T.proposed_text,
M.proposed_start, M.proposed_end)`. **No information would be invented.**

**4.2 Composition creates no new delivery risk.** This was the decisive check, because TC-7's whole
justification was that an unusable correction must be refused early rather than at Final Selection.
Reading `041`'s severity sets:

```text
BLOCKING and text-axis only    : CUE_TEXT_TOO_LONG, LINE_TOO_LONG, LINE_COUNT_EXCEEDED,
                                 LEADING/TRAILING/CONSECUTIVE line breaks, EMPTY_LINE, …
BLOCKING and timing-axis only  : DURATION_BELOW_HARD_MINIMUM, DURATION_NOT_POSITIVE,
                                 ORDER_NOT_INCREASING, CUES_OVERLAP
genuinely combinatorial        : READING_RATE_HIGH  — and it is a WARNING, not blocking
```

Every **blocking** code depends on the text axis alone or the timing axis alone, and each axis is
already exercised by its own sibling revision. The one code that genuinely depends on both — reading
rate — is advisory, and `PATCH-0042` enforces only blocking findings at Final Selection. **A composed
revision cannot fail delivery in a way RT or RM would not have failed on its own.** TC-7's argument
therefore does not transfer, and composition needs no new admission gate.

**4.3 So composition is a deterministic derivation, not a new Human Authority.** V-2 already
separates the two: *"수락은 권한 부여이고 생성은 적용이다"*, and generation is *"정확히 하나의
후보를 지명하는 명시적 요청"* — an explicit command, **not** a `§18` record. Naming a *pair* fits that
released shape exactly. Two authorities already exist; the request names which two are applied.

**No new Human Decision kind is required, and none may be invented.** What *is* required is that the
pair be named explicitly, because §2 showed there is no released notion of "the" accepted correction.

## 5. Problem A — alternatives

| | approach | verdict |
|---|---|---|
| **A0** | no composition; siblings only, one selectable | **Current state. Survivable, not a dead end.** A person who needs both must choose the more important axis. Real limitation, no data loss, no corruption. |
| **A1** | a third combined candidate aggregate proposing text + timing together | **Rejected.** It duplicates two released aggregates, forces a person who already made two judgments to author a third proposal, and its Accept would re-decide what `§18` already decided. Auto-promoting existing accepted candidates into a combined one is exactly the automatic composition TC-18 forbids. |
| **A2** | an explicit composition request naming one accepted text decision and one accepted timing decision, producing one revision through `§19` | **The correct owner if composition is ever built** (§4). No new candidate, no new authority, no new aggregate; identity would follow the released `(candidate, decision)` idiom extended to a pair. |
| **A3** | achieve composition via revision chaining | **Rejected as the vehicle** — see §7. It changes four released rules to reach a result A2 reaches by changing one. |

**A2 is the decided owner. Whether to build it is not decided here** (§9).

## 6. Order and identity — answered by released contract

If composition were reached by chaining (A3), text→timing and timing→text would produce:

- **the same final content** — each step preserves the other axis (§4.1), so the resulting
  `(text, start, end)` and therefore `content_fingerprint_for` are identical;
- **different entity identities** — every identity derives from the `(candidate, authorizing
  decision)` anchor, and the two orders consume different anchors in different sequence;
- **different provenance graphs** — the intermediate revision differs.

Are two revisions with identical content and different identity legal? **Yes, and it is released
policy, not a gap.** V-8: *"entity identity와 content identity는 구분되며 별도 content
fingerprint(순서/text/timing)가 동일 content의 공존을 기록한다."* So Q9 needs no new contract.

Under A2 the question dissolves: one request, one revision, no order to choose. **That is an
additional argument for A2 over A3** — A3 forces a person to pick an order that provably does not
affect the result but does affect the record.

## 7. Problem B — revision-on-revision chaining

**7.1 What the released contract says.** V-12: *"미래 chaining은 기존 `parent_revision_id` field가
이미 모델링하며 여기서 구현하지 않는다."* V-14 defers *"multiple-candidate 적용/merge/구성 · overlap
해소 · revision-on-revision chaining"*. S2-14 defers *"multi-candidate revision · revision chaining"*.
Both Problem A and Problem B are therefore **already named as Deferred by released contract** — this
session is not filling an unnamed hole, it is deciding whether to un-defer.

**7.2 What the code actually does.** Probed directly:

```text
timing candidate targeting a replacement segment -> refused at admission
text   candidate targeting a replacement segment -> ADMITTED, then refused at generation (V-4)
```

So chaining is blocked, but by generation, not by a coherent lineage rule — and the two admission
paths disagree (§12).

**7.3 What un-deferring would cost.** Four released rules would have to change:

- **K-1** — a candidate targets a segment of the intake's *current Raw Transcript*. Chaining requires
  targeting a revision's segment.
- **V-4** — applicability requires `segment_id ∈ raw_transcript.segment_ids`. Would become
  membership in the *source revision*.
- **S2-8** — write-time eligibility requires the revision's parent raw transcript to be the intake's
  current Raw selection. A chained revision's parent is a revision; `parent_raw_transcript_id` would
  have to be re-contracted as "root raw transcript" or the rule re-scoped.
- **V-12/V-14** — the deferral itself.

Plus two things no released sentence covers: **cycle prevention** and **depth policy**. Cycles are
structurally impossible today (a child's identity derives from a parent that must already exist, so a
revision cannot be its own ancestor) — but *structurally impossible* and *contracted* are different
things, and nothing states it.

| | approach | verdict |
|---|---|---|
| **B0** | keep chaining Deferred | **Decided.** |
| **B1** | one-step chaining | Rejected — "one step" is a depth number with no evidence behind it, exactly the kind of constant this line of work has refused three times. |
| **B2** | arbitrary chaining | Rejected — largest surface, needs cycle and depth contracts, and no product need names it. |
| **B3** | composition-only chaining | Rejected — a special case that is more artificial than A2 and still touches K-1 and V-4. |

## 8. Selection boundary — what `§20` may not become

`§20` is an **authority choice, not a derivation layer**. S2-3 fixes exactly two authority actions
(select a revision, select Raw fallback); S2-13 states that selecting B supersedes only the previous
*selection authority* and never touches revision A; the persisted record carries one nullable revision
under a `CHECK`.

**Merging RT and RM at selection is therefore forbidden**, and not merely unwise: it would make
`§20` derive content it does not own, invert the `§19 → §20` responsibility direction, and produce an
effective transcript that corresponds to no persisted revision — breaking `§21` S3-1's distinction
between resolution and consumption. Any composition must produce a **real revision** upstream of
selection.

## 9. Is composition actually needed? — evidence

Read-only, from committed evaluation records; no ASR run.

`evaluation/timing-diagnostic-full-corpus/predicate-results.csv` (2,370 segments, 31 P firings) was
joined against `evaluation/transcript-quality-structural-labeling/manifest_analysis.csv` (221 items,
17 human labels), restricted to the one lecture both cover and matched on transcript text:

```text
MVI_0147 segments carrying a human content label : 4
  HALLUCINATION  자세히 알아보세요.          — not in P
  REAL_SPEECH    다 했나요?                  — in P
  REAL_SPEECH    너무 쉽지?                  — in P
  REAL_SPEECH    대답이 없네? 너무 쉽지 않니? — not in P

segments needing BOTH a text correction and a timing correction : 0
```

Both P-population segments with a content label were labelled **REAL_SPEECH** — the text is right and
only the timing is suspect. That is the shape `137` predicted and it is what A0 handles perfectly.

**What this does and does not establish.** The overlap is 2 segments out of a 4-label sample in one
lecture, so this is weak evidence of absence, not evidence of impossibility. It does not remove the
architecture gap. What it does establish is that **no observed case yet requires composition**, and
that the capability whose usage would produce such cases shipped today with zero usage history.

This repository has three times contracted a rule from an under-powered sample and had measurement
overturn it (`131` §8, `134` §1, and `136` §8's correction of `133`/`135`). Committing a composition
contract now, on zero usage and a 4-label overlap, would be the fourth.

## 10. Architect Decisions

**CC-1 (Decided) — TC-18's conclusion stands; its rationale is corrected.** Two sibling corrections do
**not** make each other stale; they remain independently applicable and each generates its own
revision. Automatic composition is forbidden because **no canonical rule names which pair composes**
and because generation applies exactly one candidate (V-2) — not because of staleness. `139` recorded
this; this record is the canonical correction.

**CC-2 (Decided) — Composition, if ever built, is owned by `§19` generation.** An explicit request
naming one accepted text decision and one accepted timing decision, producing one `CorrectedTranscript
Revision` through the released aggregate. Not `§17` (A1 rejected), not `§20` (§8), not `041`.

**CC-3 (Decided) — Composition requires no new Human Authority.** The two axes are provably disjoint,
the composed content is fully determined by its inputs, and composition introduces no new **blocking**
readability risk (§4.2). V-2's explicit-request idiom already covers naming what is applied. **No new
`DecisionKind`, no combined candidate Accept, and no re-decision may be introduced.**

**CC-4 (Decided) — Automatic composition remains forbidden, and "latest wins" is forbidden with it.**
`§18` derives authority per candidate, so with N accepted text and M accepted timing candidates there
is no released referent for "the" correction. Any composition request must name both members
explicitly. An implementation may not pick by recency, sequence, or any other rule.

**CC-5 (Decided) — Revision-on-revision chaining stays Deferred (B0).** It requires changing K-1, V-4,
S2-8 and V-12/V-14, plus new cycle and depth contracts, to reach a result A2 reaches inside `§19`.
Nothing in current evidence justifies that surface.

**CC-6 (Decided) — `§20` never merges.** Selection is an authority choice over one existing revision.
Composition must produce a persisted revision upstream of selection.

**CC-7 (Decided) — Order is not a product question under A2.** Text→timing and timing→text produce
identical content; differing entity identity for identical content is already released policy (V-8).
A2 has no order to choose, which is an argument for it over A3.

**CC-8 (Deferred) — Whether to build composition at all.** Necessity is unmeasured (§9). Resume
condition in §11.

**CC-9 (Decided) — No backfill, ever.** Existing text corrections, timing corrections, sibling
revisions, Final Selections, SRT Artifacts and Materializations are immutable history. If composition
is later built, no existing sibling pair may be auto-composed, and no existing record may be
reinterpreted as composed or as needing composition.

## 11. What would close CC-8

Not a new corpus and not a new ASR run — **usage**:

```text
required : N segments where a person authored AND accepted BOTH a text correction and a
           timing correction against the same source segment
source   : real correction usage of the capability released today
threshold: none proposed — the question is whether the count is 0 or non-zero, and a single
           genuine case is enough to make composition a product need
```

Until then A0 stands, and its cost is stated honestly: **a person who needs both corrections on one
segment must currently choose one.** That limitation should be surfaced to the person rather than
hidden — a `§20` selection that shows sibling revisions for the same segment already makes it visible.

If usage produces such cases, the follow-up is a narrow PATCH implementing CC-2/CC-3/CC-4: one
composition relation, one explicit request, no new candidate type, no new authority, no chaining.

## 12. Defect found — asymmetric admission of a revision-scoped segment

Reported, not fixed (this session changes no code).

```text
text   candidate targeting a replacement segment : ADMITTED  (K-1 checks segment.transcript_id,
                                                   and replacement segments carry the RAW
                                                   transcript's id), then refused at V-4
timing candidate targeting a replacement segment : refused at admission
```

`§17` K-1 states the target segment must **belong to** the Raw Transcript; the released text
implementation checks only that it *names* that transcript, which a replacement segment also does.
The result is a dead-end candidate that can be admitted and accepted but never applied.

**Severity: low, and not corruption.** K-9 explicitly makes non-applicable historical candidates legal
and not repository damage, and V-4 blocks application, so nothing incorrect can be produced. It is a
gate that is weaker than its own contract, and it predates `PATCH-0047` — the timing path is the
stricter one only because TC-7's neighbour check happens to require ordered membership.

It should be closed by tightening text admission to membership in `raw_transcript.segment_ids`, in its
own `fix:` commit. It does **not** gate anything in this record.

## 13. Schema and persistence impact — anticipated only

No schema change this session. v54 stands unmodified.

| contract | anticipated impact |
|---|---|
| A0 (current) | none |
| A2 composition | one additive relation binding (text decision, timing decision) → revision; no change to any released or v54 relation; no column made nullable |
| A1 combined candidate | a fourth candidate relation + its decision + its generation — three relations to A2's one |
| B1/B2 chaining | `parent_revision_id` write path, source-revision membership in the generation relations, S2-8 re-scoping, cycle/depth validation |

A2 is the smallest of these by a wide margin, which reinforces CC-2.

## 14. Deferred deliberately

- Whether composition is built (CC-8).
- Revision chaining in any form (CC-5).
- Multiple-candidate merge beyond a named pair — three or more corrections on one segment is not
  analysed here and would need its own decision.
- Provider refinement, VAD, word timestamps, automatic timing proposal — unchanged from `PATCH-0047`
  TC-21, and deliberately not started: correction lineage must be stable before accepted human
  corrections can serve as refinement reference.

## 15. Result

```text
PATCH-0047 implementation pushed:     Yes — 4f68dd7, 3905e03, 20cd66b (fast-forward, no force)
TC-18 stale rationale valid:          No — disproved by execution (§3); conclusion unaffected
Current text+timing composition:      None — independent sibling revisions, §20 selects one
Revision-on-revision chaining:        Deferred (V-14 unchanged, CC-5)
Automatic composition:                Forbidden (CC-4), and "latest wins" forbidden with it
Existing Human Decisions sufficient:  Yes for a named pair (CC-3)
New Human Authority required:         No
Schema change anticipated:            Yes, if CC-8 is ever answered yes — one additive relation
Existing records changed:             No, and no backfill ever (CC-9)

Decision gate:                        MORE_EVIDENCE_REQUIRED

Next milestone:                       none in this line — accumulate correction usage (§11).
                                      A separate small `fix:` closes the §12 admission asymmetry.

Requires Architect Decision:          No — CC-1…CC-9 are this record
Requires Blueprint Clarification:     No — §17/§18/§19/§20 are internally consistent
Requires Blueprint PATCH:             Yes — one narrow additive note correcting TC-18's rationale in
                                      the released §17 subsection, which currently states a
                                      falsehood about the implementation (§3). It changes no
                                      behaviour and is independent of the gate above.
Requires Schema Change:               No
Requires Migration:                   No
Requires additional measurement:      Yes — real correction usage (§11), not a new corpus or ASR run
```
