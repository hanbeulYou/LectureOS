# Transcript Timing Refinement and Human Correction Boundary — Architect Decision

- Status: Architect Decision (no PATCH, no implementation)
- Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` §14 A-7, §15 L-7/L-16/TD-1…TD-20, §17 K-1/K-2,
  §18 H-1/H-2, §19, §20
- Production impact: **none** — no PATCH, no Blueprint change, no schema change, no code change
- Related: `131`, `132`, `133`, `134`, `135_TRANSCRIPT_TIMING_QUALITY_DIAGNOSTIC.md`;
  `PATCH-0045`, `PATCH-0046`

## Decision summary

Two questions were asked. Both are answered **yes**, and the investigation changed the expected
ordering.

| | question | decision |
|---|---|---|
| **Q1** | Should LectureOS provide audio-grounded timing refinement? | **Yes**, and it belongs at **§15 provider execution**, producing a **distinct Raw Transcript** under the released A-7 / L-7 pattern. The *mechanism* stays Deferred behind L-16's two conditions. |
| **Q2** | Is a canonical Human Authority boundary needed for timing correction? | **Yes**, and it is **far narrower than it looks** — the correction lineage is already timing-capable; only the *candidate vocabulary* is text-only. |

**Sequencing: human correction first, refinement second.** That inverts the intuitive order, and §6
gives the reason — building the human boundary first is what produces the evidence refinement needs
in order to be evaluated at all.

## 1. What the investigation found in the released code

Three facts decided almost everything, and two of them were not what I expected.

### 1.1 The correction lineage already carries timing

`§19`'s revision generation builds a replacement segment like this:

```python
replacement_segment = TranscriptSegment(
    identity=TranscriptSegmentId(f"{_SEGMENT_PREFIX}:{digest}:0"),
    text=candidate.proposed_text,
    start=source_segment.start,          # <- copied, not fixed
    end=source_segment.end,              # <- copied, not fixed
    replaces_segment_id=source_segment.identity,
)
```

`TranscriptSegment` carries `start`/`end`; `CorrectedTranscriptRevision` carries `segment_ids`; the
replacement declares `replaces_segment_id`. **Nothing in the lineage requires a revision's segment to
keep its parent's timing.** It does today only because the candidate proposes text and the generator
therefore has nothing else to change.

So `PATCH-0046` TD-17's statement — that `§17` is a text contract and must not be bent — is correct
about the *candidate*, and I over-generalised it in `133` §9 and `135` when I wrote that timing
correction has "no path to connect to". The revision, decision and selection machinery is
timing-capable. **Only the candidate vocabulary is not.** That is a materially smaller gap than
previously recorded, and this record corrects it.

### 1.2 Human Authority is already candidate-shaped, not text-shaped

`§18` H-1 introduced a decision aggregate deliberately separate from `TranscriptReviewDecision`,
reusing `DecisionKind(accept/reject)` and `HumanActorReference`. H-2 fixes three states —
Undecided / Accepted / Rejected — with Modify deferred.

**None of that mentions text.** It records "a person accepted or rejected *this candidate*". A timing
candidate would flow through it unchanged.

### 1.3 A second Raw Transcript from a different execution is already released behaviour

`§14` A-7: one intake may hold several provider results, since "서로 다른 provider/model/execution은
서로 다른 anchor를 만든다", consistent with §10.1 reprocessing. `PATCH-0040` P-4/P-5 exercised exactly
this: a configuration change produced a distinct `provider_result_ref`, a second Raw Transcript was
admitted alongside the first, and `§16` Selection decided which is authoritative — with **no automatic
re-selection**.

An audio-grounded refinement *is* a different execution. It needs no new pattern.

## 2. Q1 — Refinement belongs at §15, as a distinct execution

**TR-1 (Decided).** Audio-grounded timing refinement is within LectureOS's responsibility. The
diagnostic released in `PATCH-0046` finds ~15.8 structures per lecture-hour worth reviewing and
currently offers no way to act on any of them. Detecting indefinitely without any path forward is not
a stable end state.

**TR-2 (Decided) — The layer is `§15` provider execution.** A refinement run is a provider execution
that reads audio and emits timings; its output is admitted through the unchanged `§14` boundary as a
**distinct Raw Transcript** under a distinct `provider_result_ref`, and `§16` Selection decides which
is authoritative. No automatic re-selection (P-5).

Why not the alternatives:

| candidate layer | rejected because |
|---|---|
| `§14` Admission | A-14 states admission reads no media. Refinement requires audio. Already rejected in `133`. |
| `041` Subtitle Time Representation | `PATCH-0046` TD-14. Re-timing at the subtitle layer would make the SRT disagree with the transcript it claims to render. |
| A derived timing revision produced by machine | It would enter the `§19` lineage without a `§18` decision, giving a machine the authority `§18` reserves for a person — or it would need its own candidate machinery anyway, which is Q2's answer, not a separate design. |

**TR-3 (Decided) — Raw stays Raw.** The original provider result and its timings are never rewritten,
re-admitted or superseded in place. A refinement produces a *sibling*, and `§16` chooses. This
follows A-4/A-11 and `PATCH-0046` TD-13/TD-18 without amendment.

**TR-4 (Deferred) — The mechanism.** VAD, word timestamps, forced alignment and any other approach
remain Deferred. `§15` L-16 declined VAD for two reasons — real-speech deletion and unusable segment
durations — and stated the deferral is reasoned, not permanent, and revisitable by a contract solving
**both**. `132` quantified only the second. **No mechanism may be adopted before both are measured
against the same corpus.** This decision fixes the layer, not the technique, precisely so the next
session cannot slide into "let's just turn VAD on".

## 3. Q2 — A timing correction boundary is needed, and it is a candidate-vocabulary extension

**TC-1 (Decided).** A canonical Human Authority boundary for timing correction is needed. Without it
`PATCH-0046` produces observations a person can confirm but not record, and a confirmed finding has
nowhere to go.

**TC-2 (Decided) — The gap is the candidate, not the lineage.** From §1.1 and §1.2:

```text
Correction Candidate    text-only        ← the gap
Human Authority (§18)   candidate-shaped ← already works
Revision (§19)          timing-capable   ← already works
Selection (§20)         revision-shaped  ← already works
Effective (§21)         revision-shaped  ← already works
```

A timing correction needs a candidate that proposes **a time range instead of a text**, targeting one
segment of the current Raw Transcript, carrying a snapshot of the timing it replaces — the exact
analogue of K-1's lineage rules and K-2's `source_text_snapshot` guard.

**TC-3 (Decided) — `§17` is extended, not reused as-is and not duplicated.** `PATCH-0046` TD-17 stands:
a timing correction must not be smuggled through `proposed_text`. But the correct reading is that the
candidate **vocabulary** needs a sibling kind, not that a second candidate subsystem is required.
`§18` H-1 already rejected wrapping one candidate layer in another; the same reasoning applies here.

**TC-4 (Decided) — A timing correction states a time range, never a magnitude.** It records what the
segment's boundaries should be, not how wrong they were. This keeps `PATCH-0046` TD-2's limit intact:
the diagnostic never claimed a drift size, and the correction does not retroactively supply one.

**TC-5 (Decided) — No automatic proposal.** A timing candidate is created only from a human judgment,
never generated by the diagnostic. `PATCH-0045` QD-16's reasoning carries: false positives are
tolerable **because** nothing acts automatically, and that tolerance disappears the moment the
detector proposes.

**TC-6 (Deferred) — Modify.** `§18` H-2 defers Modify for text candidates. Timing inherits that
deferral: accept/reject only, no in-place amendment of a proposed range.

## 4. What neither decision permits

Restated because the boundary is easy to erode:

- No timestamp is ever rewritten in place. Both paths produce **new** records — a sibling Raw
  Transcript (TR-2) or a corrected revision (TC-2).
- No automatic correction, no automatic selection, no automatic re-generation of released SRTs.
- No threshold, no drift magnitude, no correction amount.
- `PATCH-0046`'s diagnostic remains non-blocking and non-persistent, and gains no new authority from
  either decision.
- `041` is untouched by both.

## 5. What is still unknown, and what it costs

Stated plainly, because the sequencing in §6 turns on it.

**How much of the diagnostic's output is materially wrong is unmeasured.** `134` found 31 firings in
MVI_0147, of which only 6 had an anchor gap of 10 s or more; 16 were under one second. `132` measured
drift on *post-silence* segments — a different population — and found a median of 4.1 s. **The drift
distribution across the 31 has never been measured**, and `PATCH-0046` TD-2 deliberately refuses to
estimate it.

So today nobody knows whether this is a 6-segments-per-lecture problem or a 31-segments-per-lecture
problem. That matters for refinement's value and not at all for the correction boundary's
correctness.

**Refinement feasibility is entirely unmeasured** (TR-4). L-16's first condition — no real-speech loss
— has never been tested for any candidate mechanism.

## 6. Sequencing — correction first

The intuitive order is refinement first: fix it automatically, and manual correction becomes rare.
**The evidence points the other way.**

1. **The correction boundary is the smaller change.** It needs a candidate kind. Refinement needs a
   provider capability, an L-16 resolution, and a second full execution per lecture.
2. **It needs no audio, no new provider, and no deferred question resolved.** It can be built on
   released contracts today.
3. **It gives the released diagnostic somewhere to go.** `PATCH-0046` currently detects and stops.
4. **It generates the evidence refinement requires.** This is the decisive one. Every human timing
   correction is a **human-verified speech onset** for a segment the detector flagged. Accumulate
   those and you have exactly the ground truth needed to test L-16's two conditions — does a
   mechanism move timestamps toward the human answer, and does it delete speech the human heard? Today
   that ground truth does not exist, which is why `133` and `134` could not evaluate any candidate.

Building refinement first would mean choosing a mechanism with no reference to compare it against —
and this investigation has already twice adopted a plausible reading that measurement then overturned
(`131` §8, `134` §1).

**One measurement could change this ordering**, and it is cheap: measure the drift distribution across
the 31 firings (§5). If nearly all are sub-second, the correction boundary may not be worth building
and the whole line reduces to a diagnostic. That measurement needs no new capability — the
energy-based method validated in `132` §3 already exists as scratch tooling.

## 7. Next steps, in order

1. **Measure the drift distribution across the P population** (§5). Cheap, no new capability, and it
   is the one result that could retire either decision.
2. **If it justifies action: PATCH the timing correction candidate boundary** (TC-1…TC-6). Scope: one
   candidate kind, targeting one segment of the current Raw Transcript, carrying a replaced-timing
   snapshot, flowing through unchanged `§18` and `§19`.
3. **Then, and only then, evaluate refinement mechanisms** against the accumulated human corrections,
   testing **both** L-16 conditions on the same corpus.
4. **Only after that, a refinement PATCH** (TR-1…TR-4).

## 8. Corrections to earlier records

Additive; nothing rewritten.

| where | prior statement | corrected |
|---|---|---|
| `133` §9, `135` | "timing correction stays Deferred **with no path to connect to**" | The `§18`/`§19`/`§20` lineage is timing-capable; only the candidate vocabulary is text-only. The gap is one candidate kind, not a subsystem. |
| `PATCH-0046` TD-17 | (as written, correct) | Unchanged in substance — `§17` must not be bent through `proposed_text`. The over-generalisation was mine in the reports, not the PATCH's. |

## 9. Result

```text
Q1 audio-grounded timing refinement:   Yes — §15 provider execution, distinct Raw Transcript
                                       under released A-7 / L-7 / P-5; mechanism Deferred (L-16)
Q2 human timing correction boundary:   Yes — a candidate-vocabulary sibling; §18/§19/§20 unchanged
Sequencing:                            correction first, refinement second (§6)
Blocking measurement:                  drift distribution across the P population (§5)

PATCH created: No
Blueprint changed: No
Schema changed: No
Production changed: No
VAD adopted: No
Threshold or correction amount decided: No

Requires Architect Decision:      No — this record is the decision
Requires Blueprint Clarification: No
Requires Blueprint PATCH:         Yes, eventually — timing correction candidate (TC), then
                                  refinement (TR); neither before §7's measurement
Requires additional measurement:  Yes — §5, and it gates step 2
```
