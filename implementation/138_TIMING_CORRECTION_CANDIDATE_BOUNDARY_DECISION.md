# Human Timing Correction Candidate Boundary — Architect Decision

- Status: Architect Decision (no PATCH, no implementation)
- Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` §2, §14 A-10/A-11/A-14, §15 TD-1…TD-20,
  §17 K-1…K-4, §18 H-1/H-2, §19, §20; `docs/041` §7
- Production impact: **none** — no PATCH, no Blueprint change, no schema change, no code change
- Related: `131`, `132`, `133`, `134`, `135`, `136`, `137_P_POPULATION_DRIFT_DISTRIBUTION.md`

## Gate

```text
PATCH_READY
```

Every question in §6–§14 closed against released contracts and production code. The proposed PATCH
scope is §16. **One decision is deliberately narrower than `136` anticipated**, and one released
constraint was found that `136` did not know about — see §4.

## 1. Repository investigation

Read: `040` §2, §4.2/§4.3, §8, §9, §14 A-4/A-10/A-11/A-14, §15 L-6/L-7/L-16 and both diagnostic
subsections (QD-1…QD-20, TD-1…TD-20), §17 K-1…K-4, §18 H-1/H-2, §19, §20; `041` §7, §16, Final
Selection / SRT Artifact / Materialization; `PATCH-0039/0040/0045/0046`; reports `131`–`137`.

Production code read rather than inferred: `correction_candidate_admission.py`,
`correction_candidate_decision.py`, `corrected_revision_generation.py`, `transcript/models.py`, and
the schema statements in `persistence/sqlite.py` for `correction_candidates`,
`correction_candidate_decisions`, `corrected_transcript_revisions`,
`corrected_transcript_revision_segments` and `corrected_revision_generations`.

## 2. The existing correction model, split by what is text-bound

| layer | text-bound? | evidence |
|---|---|---|
| `§17` Correction Candidate | **yes, hard** | `proposed_text TEXT NOT NULL`; K-2 requires it non-blank **and rejects a no-op**; K-3 requires a source-**text** snapshot |
| `§18` Human Decision | **no** | table is `(identity, correction_candidate_id, kind, reviewer, sequence, previous_decision_id, rationale, content_fingerprint)` — no text column, no text semantics |
| `§19` Corrected Revision | **no** | `TranscriptSegment` carries `start`/`end`; the generator copies them only because the candidate proposes text |
| `§19` generation record | **candidate-bound** | `corrected_revision_generations` FKs to `correction_candidates(identity)` **and** `correction_candidate_decisions(identity)` |
| `§20` Selection / `041` | **no** | selection and SRT operate on a revision's segments; neither knows what kind of correction produced it |

`136` §1.1 was right that the lineage is timing-capable. It missed two things this investigation
found, and both change the shape of the answer.

## 3. Replacement segment identity — already correct for timing

```python
digest = derive_generation_digest(candidate_identity, current_decision.identity)
replacement = TranscriptSegment(identity=TranscriptSegmentId(f"{_SEGMENT_PREFIX}:{digest}:0"), …)
```

Identity derives from **(candidate, decision)**, not from content. So a timing-only replacement gets a
distinct identity automatically — a distinct candidate produces a distinct digest — and
`CHECK (replaced_segment_id <> replacement_segment_id)` is satisfied without special handling.

Answering `136` §16's questions directly: the identity function does **not** include timing, and does
not need to. This is **neither a Blueprint gap nor a defect** — content-derived segment identity was
never the model here; provenance-derived identity was.

## 4. The constraint `136` did not know about

**`§17` K-2 rejects a no-op:** *"`no-op`(제안 text가 source text와 동일)은 거부된다"*, enforced at
`correction_candidate_admission.py:143`.

This forecloses the tempting cheap path. A timing candidate cannot ride the existing aggregate by
carrying the source text unchanged, because **released admission would reject it as a no-op**. Nor may
timing be serialised into `proposed_text` — that is meaning distortion, and the reason K-2 exists is
to prevent exactly this kind of smuggling.

Combined with `proposed_text TEXT NOT NULL`, which cannot be relaxed additively in SQLite without
rebuilding a released table:

> **The existing candidate aggregate cannot express a timing correction. A sibling is required.**

That is a firmer conclusion than `136` TC-3's "extend the vocabulary", and this record supersedes that
phrasing.

## 5. The consequence nobody had costed: `§18` cannot be reused as-is

`correction_candidate_decisions` declares

```sql
FOREIGN KEY (correction_candidate_id) REFERENCES correction_candidates(identity)
```

A timing candidate in a sibling table **cannot be decided by the existing decision table** — the
foreign key would fail. The same applies to `corrected_revision_generations`, which FKs to both.

So `136` TC-2's claim that "`§18`/`§19`/`§20` are unchanged" is **true semantically and false
physically**. `§18`'s *contract* accommodates timing without amendment (§2); its *table* does not.

This is not a blocker. `§18` H-1 already faced the analogous problem and recorded the answer: it
declined to wrap one candidate layer in another and instead introduced "smallest additive aggregate"
reusing `DecisionKind` and `HumanActorReference`. **The same precedent applies here** — a sibling
decision relation over timing candidates, reusing the value types, the accept/reject vocabulary and
the append-only supersession pattern, without inventing new authority semantics.

## 6. Empirical justification, and its limits

`137` measured the P population's drift distribution:

```text
< 1 s : 16 (51.6 %)     ≥ 2 s : 8 (25.8 %)     ≥ 5 s : 4 (12.9 %)     max 19.05 s
```

**What this justifies:** non-trivial cases exist. Roughly eight per lecture carry drift of two seconds
or more and four exceed five seconds. Detecting them while offering no canonical way to record a
correction is not a defensible end state, and ~8 per lecture is human-scale.

**What it does not justify:** any threshold. `137` §2 recorded that the energy method agreed with 0 of
4 human observations within ±5 s here, so **individual values are unreliable** and none of `0.68`,
`2.64`, `19.05` or the band edges may become product numbers. The anchor-gap correlation (§5 of `137`)
is an observation about one corpus, contradicted by a 6.60 s drift at a 0.90 s gap, and must not
become an eligibility rule — `PATCH-0046` TD-6's threshold-free character is not to be routed around.

**What it also tells us about workflow:** half the findings will be dismissed. Rejection is the
expected outcome, not a failure.

## 7. Alternatives

| | option | verdict |
|---|---|---|
| **A** | No correction capability; diagnostic only | **Rejected.** Inconsistent with Human Authority: `§8` already routes timing risk to Review, and `§18` exists so a person's judgment becomes canonical. `137` shows the cases are real. Detect-and-stop leaves the released diagnostic inert. |
| **B** | Extend the existing text candidate with optional timing | **Rejected on released contract**, not on taste — K-2's no-op rejection and `proposed_text NOT NULL` (§4). Also conflates two different proposals: "this text is wrong" and "this text is right but shown at the wrong time". |
| **C** | Sibling candidate kind inside the same correction subsystem, reusing decision and revision semantics | **Adopted.** Requires a sibling decision relation for FK reasons (§5), which `§18` H-1's own precedent already sanctions. |
| **D** | Wholly separate Timing Correction subsystem with its own revision lifecycle | **Rejected.** `§19`/`§20`/`041` are already timing-capable and correction-kind-agnostic (§2). A second revision lifecycle would create competing revision semantics and duplicate authority over the same transcript. |

## 8. Architect decisions

### Necessity and placement

**TC-1 (Decided).** LectureOS needs a canonical human timing correction path. `137` establishes the
cases are real and human-scale; `§8` already routes them to Review; `§18` exists precisely so human
judgment becomes canonical.

**TC-2 (Decided) — A sibling candidate, not a variant.** A timing correction is admitted as its own
candidate kind alongside the text candidate, because the released text candidate cannot express it
(§4). It is **not** a new subsystem: revision generation, selection and downstream stay shared.

**TC-3 (Decided) — A sibling decision relation, reusing `§18`'s semantics unchanged.** Forced by the
foreign key (§5), sanctioned by H-1's precedent. It reuses `DecisionKind(accept/reject)`,
`HumanActorReference`, append-only supersession, and H-2's three states with **Modify deferred**. No
new authority concept is introduced.

### What the candidate proposes

**TC-4 (Decided) — A complete replacement interval: both start and end.** Option 2/3 of `136`'s
framing; start-only is rejected.

Reasons, in order of weight. A start-only proposal silently redefines duration, and duration is what
`041` readability measures — a start-only change would move a cue's reading rate without anyone
proposing that. It also cannot express the observed cases: `137`'s largest, a 20.7 s segment whose
speech begins ~19 s in, needs its end reconsidered too, since keeping the original end would leave a
1.6 s cue. And a person listening already knows both boundaries; asking only for the start invents an
asymmetry the evidence does not have.

**TC-5 (Decided) — The proposal replaces timing only; text is carried through unchanged.** The
replacement segment reproduces the source text exactly, under A-11's preservation requirement. A
timing candidate that also changed text would be two proposals wearing one decision.

**TC-6 (Decided) — No-op is rejected, mirroring K-2.** A proposed interval identical to the source
interval is not admissible. Same-instant comparison uses the released `PATCH-0039` ε and **no new
tolerance**.

**TC-7 (Decided) — Structural validity only; admission reads no media.** Admission checks what it can
know: finite values, `start >= 0`, `end > start`, and the target segment's existence and membership,
mirroring A-10's structural vocabulary. It does **not** verify that the proposed interval matches
actual speech — that judgment is the person's, and `§18` is where it becomes canonical. This is
narrower than A-14's prohibition (which is about the provider admission boundary) but lands in the
same place: **no media access**.

**TC-8 (Deferred, explicitly) — Cross-segment ordering and overlap.** A corrected interval could
overlap its neighbours. A-10's non-overlap contract governs *provider admission*, and no released
sentence states whether a corrected revision's segments must satisfy it. **This is a genuine Blueprint
gap**, and it is recorded rather than filled: the PATCH must either contract the answer or state the
restriction that avoids the question. It is not guessed at here.

**TC-9 (Decided) — Stale protection is a timing snapshot, mirroring K-3.** The candidate carries the
source interval it believes it is replacing, and admission requires an exact match against the
persisted segment. Same purpose as K-3's text snapshot, same failure mode prevented.

### Who authors the proposal

**TC-10 (Decided) — Human-authored only. No automatic proposal.** The diagnostic identifies a segment
worth reviewing (`PATCH-0046` TD-2) and stops; a person listens and states the interval. Current
evidence justifies nothing more: the energy estimator is not ground truth (`137` §2), the anchor gap
is not a correction amount (`137` §5), and `PATCH-0045` QD-16's logic carries — false positives are
tolerable **because** nothing acts automatically.

Machine-suggested / human-approved is **Deferred**, not refused; it becomes evaluable once human
corrections accumulate (§12).

### Lineage and downstream

**TC-11 (Decided) — `§19` is reused with no new revision type.** An accepted timing candidate produces
a replacement `TranscriptSegment` carrying the source text, the proposed interval, and
`replaces_segment_id` to its source. Identity derives from (candidate, decision) as today (§3), so
timing-only replacements are distinguished automatically. The generation record needs a sibling
relation for the same FK reason as TC-3.

**TC-12 (Decided) — `§20` and `041` are unchanged and correction-kind-agnostic.** Selection chooses a
revision; SRT materialization renders whatever timing the selected revision's segments carry. Neither
learns what kind of correction produced it.

**TC-13 (Decided) — Raw Transcript is immutable.** Provider timestamps are never rewritten. §2 Raw
Before Corrected, A-11 and `PATCH-0046` TD-13 all hold unchanged; correction lives entirely in the
revision lineage.

**TC-14 (Decided) — Released artifacts do not become stale.** An existing SRT remains a valid artifact
of the revision selected when it was made. A new artifact appears only when a person accepts a
correction, selects the resulting revision, and materializes again — the released
selection → artifact → materialization identity chain, unchanged. **No retroactive mutation, no
automatic regeneration.**

### Combined text + timing on one segment

**TC-15 (Decided) — Sequential, through the existing lineage; no combined candidate.** `§19` already
supports a revision whose parent is another revision (`parent_revision_id`), so correcting text and
then timing is two candidates and two decisions producing two revisions in a chain.

**TC-16 (Deferred) — Staleness when both target the same source segment.** Once one correction is
applied, the other's snapshot no longer matches the current segment. K-3's mechanism *detects* this;
what the product should do about it — re-target, re-author, or reject — is not contracted. Recorded as
a **Blueprint gap**, deliberately unfilled. The narrow PATCH need not resolve it, but must not
silently pick a behaviour.

### Schema

**TC-17 (Decided) — Additive schema evolution is required, and its necessity is established rather
than assumed.** `proposed_text TEXT NOT NULL` cannot hold a timing proposal; making it nullable is not
additive in SQLite; serialising timing into it is meaning distortion (§4). Three sibling relations are
implied — timing candidates, their decisions, their generation records — mirroring the released
shapes. **No migration is written here**, and the exact statements belong to the PATCH.

## 9. Deferred

Cross-segment ordering/overlap for corrected revisions (TC-8); staleness between competing corrections
on one segment (TC-16); Modify (TC-3, inheriting H-2); machine-suggested proposals (TC-10); any
threshold, drift magnitude or eligibility rule; provider refinement and its mechanism (`136` TR-4);
`041` changes; regeneration of released artifacts.

## 10. Corrections to `136`

Additive; `136` is not rewritten.

| `136` said | corrected |
|---|---|
| TC-3: "`§17` is extended… the candidate **vocabulary** needs a sibling kind" | The existing aggregate cannot be extended: K-2 rejects a no-op and `proposed_text` is NOT NULL. A sibling **aggregate** is required (§4). |
| TC-2: "flowing through unchanged `§18` and `§19`" | Semantically true, physically false. Both relations FK to `correction_candidates`, so sibling relations are required — using H-1's own precedent (§5). |
| §7 step 2 scope: "one candidate kind" | Three sibling relations (candidate, decision, generation) plus an additive migration (TC-17). Still narrow, but larger than one table. |

## 11. Schema impact summary

Additive only. Existing relations, rows and meanings unchanged; `docs/030_DATA_MODEL.md` gains the new
relations when the PATCH is applied. Schema version advances from **53** at implementation time, not
now.

## 12. Refinement boundary

Unchanged from `136` TR-1…TR-4: refinement belongs to `§15` provider execution producing a distinct
Raw Transcript, and its **mechanism stays Deferred** behind L-16's two conditions. This decision
adopts no VAD, no word timestamps, no energy alignment, and no refinement algorithm.

The connection worth stating once and not over-claiming: accepted human timing corrections are
human-verified intervals for segments the detector flagged, so they can serve as reference material
when a refinement mechanism is eventually evaluated. That is a **useful side effect, not a purpose** —
this contract creates no labeling program and no new persistence obligation.

## 13. Proposed PATCH scope

Title: *Human Timing Correction Candidate Boundary*. Target: `docs/040_TRANSCRIPT_PIPELINE.md`
(additive), plus `docs/030_DATA_MODEL.md` for the new relations.

Must contract: TC-1…TC-17. Must state as Deferred: TC-8 and TC-16 with their gap character explicit,
Modify, machine-suggested proposals, thresholds, refinement. Must state the additive migration's
shape without writing it.

Must **not**: introduce a threshold or drift magnitude; grant admission media access; permit automatic
proposals; mutate Raw Transcripts or released artifacts; amend `041`; or alter `§17`/`§18`/`§19`'s
released text — the new relations are siblings, and the released clauses gain forward notes only.

## 14. Result

```text
Gate:                              PATCH_READY
Timing correction capability:      Needed (TC-1)
Existing §17 reuse:                Not possible — K-2 no-op rejection + proposed_text NOT NULL
Existing §18 semantics reuse:      Yes; sibling relation required for the foreign key
Existing §19/§20/041 reuse:        Yes, unchanged and correction-kind-agnostic
Candidate proposes:                A complete replacement interval, text carried through
Automatic proposal:                No
Raw Transcript mutation:           No
Released artifact regeneration:    No

Requires Architect Decision:       No — this record is the decision
Requires Blueprint Clarification:  No — TC-8 and TC-16 are recorded as gaps for the PATCH to
                                   contract or explicitly restrict, not as blockers
Requires Blueprint PATCH:          Yes — scope in §13
Requires Schema Change:            Yes — additive only (TC-17)
Requires Migration:                Yes, at implementation time; none written here
Requires additional measurement:   No
Production changed:                No
Existing artifacts changed:        No
Remote push:                       Yes — d092880, 9f3e251 pushed; local == origin/main == 9f3e251
```
