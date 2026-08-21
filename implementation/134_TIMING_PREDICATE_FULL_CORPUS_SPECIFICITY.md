# Timing Diagnostic Predicate — Full-Corpus Specificity Measurement (Evaluation)

- Status: Evaluation Record
- Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` §14 A-10, §15 L-6; `PATCH-0045` QD-6/QD-7/QD-11
- Production impact: **none** — no PATCH, no Blueprint change, no schema change, no code change
- Related: `131`, `132`, `133_POST_SILENCE_TIMING_DIAGNOSTIC_GATE.md` (commit `c0361d2`)

## Gate reassessment

```text
PATCH_READY
```

The predicate is deterministic from persisted evidence, needs no threshold, fires on **1.31 % of
segments (15.8 per hour)**, and captured **4 of 4** human-confirmed timing-drift observations. No
PATCH was written this session; the next session may write one.

**A correction comes first**, because it changes what `132` established.

## 1. Correction to report 132

`132` §5 reported "20 of 23 post-silence segments begin at the exact instant their decode window
opens" and read it as evidence of decode-window anchoring. **That comparison was an identity of the
representation, not an observation.**

`PATCH-0045`'s `_decode_windows_of` sets a window's `start` to the first segment's own start:

```python
current = {"window_ref": evidence.window_ref,       # provider anchor (seek)
           "start": float(segment.start),           # <- the first segment's own start
           ...}
```

So `segment.start == window.start` is true for every window-first segment by construction and says
nothing about the decoder. `132`'s 20/23 actually measured *"20 of 23 post-silence segments are the
first segment of their decode window"* — meaningful, but far weaker than claimed.

The provider's real anchor survives in `window_ref` as faster-whisper's `seek`, in centiseconds. The
predicate was rebuilt on it, and the measurement below is the first non-tautological test.

`132` is not rewritten; this record carries the correction.

## 2. Selected lecture

**MVI_0147** (장혜정 선생님, 1.96 h).

| criterion | why this lecture |
|---|---|
| human observations | **4 of the 5** timing-drift observations in `131` §5 are from it |
| population size | 2,370 segments — the largest of the three |
| silence profile | 3.2 % no-speech, against MVI_0146's 10.9 % — the **conservative** choice, since less silence gives the predicate fewer easy positives |
| instructor coverage | the only lecture from the second instructor |

The 10.9 % lecture would have flattered the result; this one does not.

## 3. Evidence reconstruction

Full decode-window evidence was unrecoverable (scratchpad cleared, `131` §9), and the structural
manifest preserves `window_index/start/end/segment_count` but **not `window_ref`** — so the corrected
predicate could not be computed from surviving artefacts at all.

The lecture was re-run through the released production path with configuration unchanged:

```text
local_asr_cli --intake transcript-source-intake:sha256:19aa01b5… --model large-v3 --language ko
provider result reference: local-asr:v2:model=large-v3:lang=ko:cond_prev_text=false:media=sha256:19aa01b5…
condition_on_previous_text = False      vad_filter not enabled
execution mode: fresh                   segments: 2370     wall 3448 s
```

ASR is non-deterministic (`122`), so this run yields 2,370 segments where the earlier one gave 2,364.
Human observations are therefore joined by **time proximity**, not by ordinal (§8).

## 4. Population definition

**Every admitted segment of the lecture**, with no filtering whatever — no silence, readability,
text, label or provider-signal condition participates.

```text
total segments                                     2,370
excluded: first segment (no predecessor)                1
excluded: no preserved anchor                           0
evaluable                                           2,369
```

## 5. Predicate definition

```text
P1 : |segment.start − seek/100| ≤ ε        the segment begins AT the provider's decode anchor
P2 : seek/100 > previous_segment.end + ε   the window opened after emitted non-speech
P  : P1 ∧ P2
```

`ε` is the released `PATCH-0039` `TIMING_BOUNDARY_TOLERANCE_SECONDS = 1e-6`, used only for
same-instant comparison. **No gap threshold exists anywhere in P** — P2 is a strict inequality, not a
duration test.

`seek/100` converts centiseconds to seconds, confirmed against the preserved fixtures
(`seek=2880 → 28.80 s`).

## 6. Full-corpus base rate

| predicate | count | rate | per hour |
|---|---|---|---|
| P1 | 251 | 10.60 % | 127.9 |
| P2 | 31 | 1.31 % | 15.8 |
| **P** | **31** | **1.31 %** | **15.8** |

### P1 is real but carries no discriminating information

```text
window-first segments      251     of which P1 true : 251  (100.0 %)
non-window-first segments 2,118    of which P1 true :   0
```

**Every one of 251 decode windows emits its first segment starting exactly at the seek anchor — no
exceptions.** That is a genuine and strong property of the decoder: faster-whisper never places the
first segment of a window at detected speech onset; it always places it at the window boundary.

It is also why P1 alone is useless as a warning: it fires on 10.6 % of all segments, 128 per hour.
`133` reached the same conclusion from the derived-window figure; the corrected measurement confirms
it on the provider's own anchor and makes the base rate exact rather than estimated.

### P2 is what discriminates

Of the 251 window-first segments, **220 have the anchor exactly equal to the previous segment's end** —
continuous speech, where Whisper advances `seek` to where the last segment finished. Only 31 have an
anchor beyond it, i.e. a window that opened over emitted non-speech.

`133`'s worry — that the corpus-wide rate might reach the 10–29 % upper bound implied by
cue-gap frequency — is **resolved and rejected**. The bound was loose because a non-speech interval
does not by itself open a decode window; a window opens only when the previous window is exhausted.
The two conditions coincide 31 times in two hours.

## 7. Case characterization

Distribution of `anchor − previous end` across the 31 firings:

```text
0 – 1 s     16      1 – 3 s      6      3 – 10 s     3      ≥ 10 s      6
min 0.10 s        median 0.94 s        max 85.50 s
```

The six largest are the phenomenon in its clearest form:

```text
85.50s  얘들아 사전 잘 볼 줄 알죠?          segment 20.7s
60.00s  다 했나요?                         segment  6.7s
30.00s  너무 쉽지?                         segment 23.8s
21.00s  자 문제 술술술술술 풀려야 될텐데      segment  6.8s
18.00s  오늘 얼마나 알차게 지금 수업중이니     segment  5.0s
17.00s  마찬가지로 생략가능해요              segment  5.8s
```

The sixteen smallest sit between 0.10 s and 1.0 s — a window opening across an ordinary inter-utterance
pause. These are structurally identical to the large cases and are **not** separated by P. Whether
they deserve a warning is a product question, and answering it with a duration cut would be exactly
the threshold this work refuses to invent.

**No threshold was applied to produce any number above.**

## 8. Human-label join

Population and predicate were frozen before joining.

| earlier observation | drift reported in `131` | P fired | anchor − prev |
|---|---|---|---|
| `너무 쉽지?` @ 3362.2 | ~27 s | ✓ | 30.00 s |
| `오늘 얼마나 알차게…` @ 3419.6 | ~7 s | ✓ | 18.00 s |
| `얘들아 사전 잘 볼 줄 알죠?` @ 4264.7 | ~10 s | ✓ | 85.50 s |
| `다 했나요?` @ 4324.7 | ~24 s | ✓ | 60.00 s |

**4 of 4 captured.**

Against normal controls: of 75 segments in this lecture that a human labelled `REAL_SPEECH` in the
structural population, **5 fall within P**. Three of those five are among the six large-anchor cases,
which is consistent rather than contradictory — a segment can be real speech *and* have a start
pinned ahead of the utterance. That is precisely why the warning must mean *"timing requires review"*
and never *"this text is wrong"*.

**Precision is not claimed.** The four observations are not a random sample of drift, and no
exhaustive timing ground truth exists for this lecture. What the join shows is that P did not miss any
case a human had independently flagged.

## 9. Warning burden

| measure | value |
|---|---|
| P firings | **31 per 1.96 h = 15.8 per hour** |
| share of transcript | **1.31 %** of segments |
| of those, anchor gap ≥ 10 s | 6 (3.1 per hour) |
| for comparison — `READABILITY_DURATION_ABOVE_MAXIMUM` on this lecture | 8 |

Roughly sixteen warnings per lecture-hour, against a released readability warning stream of similar
order. Reported for the Architect to judge; **no acceptability cut is proposed here**, per the
instruction not to invent one after seeing the number.

## 10. Cross-lecture sanity check

**Not performed.** `window_ref` is absent from the structural manifest, so P cannot be computed for
MVI_0144 or MVI_0146 without another full ASR run (~1 h each). One lecture, one instructor, one model
and one configuration is the entire basis, and nothing here should be generalised beyond it — the
strongest reason the next PATCH should contract the predicate's *meaning* while treating its
generality as provisional.

## 11. Gate reassessment

```text
PATCH_READY
```

Against `133`'s criteria:

| requirement | status |
|---|---|
| deterministic from persisted evidence | ✓ `seek` is preserved in `original_content` under QD-6 |
| no threshold number needed | ✓ P2 is a strict inequality |
| separated from ordinary window-first segments | ✓ 31 of 251; the other 220 sit at exactly zero |
| corpus-wide burden quantified | ✓ 1.31 %, 15.8/h — measured, not extrapolated |
| meaning limited to "timing requires review" | ✓ §8 shows real speech can fire it |
| no automatic correction | ✓ unchanged from `133` TD-8 |

`133` left exactly one decision open — TD-5, the firing predicate — and blocked on a 30× uncertainty
band. That band is now closed by direct measurement: **1.31 %**, at the low end of the interval.

The next session may write the Timing Quality Diagnostic PATCH, carrying `133`'s TD-1…TD-4 and
TD-6…TD-11 unchanged, with TD-5 contracted as P and with §10's single-lecture basis stated as a
limitation rather than hidden.

## 12. Evidence durability

Kept outside the scratchpad this time, under `evaluation/timing-diagnostic-full-corpus/`
(git-excluded, `e2e-results/` precedent):

```text
source.json             media + intake identity, byte length
run.sh                  the exact released-path command
asr.log / run.log       execution record, wall time, execution mode
measurement.sqlite3     the scratch repository (not canonical)
windows.jsonl           252 windows with seek anchor and span
segments.jsonl          2,370 segments with anchor, previous end, P1/P2/P
predicate-results.csv   the same, flat
measure.py              the measurement, re-runnable
```

Not committed: the directory contains classroom transcript text. Reproducible from `run.sh` plus
`measure.py`.

## 13. Files changed

This report only. No production code, test, schema, Blueprint, PATCH or released artifact changed.
The measurement repository is scratch and canonical to nothing.

## 14. Result

```text
Lecture:                    MVI_0147 (장혜정 선생님, 1.96 h, re-run through the released path)
Total segments:             2,370   (2,369 evaluable)
P1 count/rate:              251  / 10.60 %   — 251/251 window-first segments, 0/2,118 others
P2 count/rate:               31  /  1.31 %
P  count/rate:               31  /  1.31 %
P events/hour:              15.8

Known timing-drift observations captured:   4 / 4
Known normal observations captured:         5 / 75 REAL_SPEECH segments (3 of them large-anchor)

Decision gate:              PATCH_READY

PATCH created: No
Blueprint changed: No
Production rule changed: No
Schema changed: No

Requires Architect Decision:      No — 133's decisions stand; TD-5 is now closed by measurement
Requires Blueprint Clarification: No
Requires Blueprint PATCH:         Yes — Timing Quality Diagnostic, next session
Requires additional measurement:  Not blocking. Two lectures remain unmeasured for P, and the
                                  single-lecture basis should be stated as a limitation in the PATCH
                                  rather than resolved before it.
```
