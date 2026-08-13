# Transcript Quality Diagnostic — Human Labeling Results (Evaluation)

- Status: Evaluation Record
- Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` §15 QD-12/QD-14 (threshold Deferred) / `PATCH-0045`
- Production impact: **none** — no PATCH, no threshold, no firing rule, no schema, no code change
- Related: `127_TRANSCRIPT_QUALITY_THRESHOLD_CALIBRATION.md`,
  `128_REAL_MEDIA_CALIBRATION_CORPUS_EXPANSION.md` (**neither rewritten**; corrections recorded in §7)

## 1. Summary

The first human audio labeling in this project. Two rounds, 32 clips, ~14 minutes of listening,
**9 confirmed hallucinations** — the corpus's first verified positives.

```text
THRESHOLD READINESS: MORE_DATA_REQUIRED
```

The reason changed. `127` said *"we do not have enough data to know."* This record says *"we now know
one signal alone does not work, and we know why."*

The single most important result is methodological. Round 1 (20 clips) showed `no_speech_prob`
separating hallucination from real speech **perfectly** — precision 1.00, recall 1.00, a 0.235 gap
between the classes. Round 2 (12 clips), designed specifically to attack that finding, destroyed it:
the same rule scores **precision 0.78, recall 0.78**.

Round 1 looked perfect because its 20 clips had been **selected using `no_speech_prob` as one of the
candidate criteria**. Measuring a rule on a set the rule helped choose is circular. Round 2 was
stratified to break that circularity, and it did.

## 2. Labeling protocol as executed

Blind labeling. The labeler saw audio, transcript text and ±2 segments of context. Provider signals,
selection category and selection reason were withheld in a separate analysis manifest joined by
`candidate_id`, and item order was deterministically shuffled so numbering carried no signal.

Vocabulary: `HALLUCINATION` / `REAL_SPEECH` / `ASR_ERROR` / `AMBIGUOUS`, with the
hallucination-vs-error line drawn on one question — *was there speech corresponding to this text?*

| | round 1 | round 2 |
|---|---|---|
| clips | 20 | 12 |
| listening | 8.9 min | 4.8 min |
| `HALLUCINATION` | 5 | 4 |
| `REAL_SPEECH` | 9 | 5 |
| `ASR_ERROR` | 4 | 3 |
| `AMBIGUOUS` | 2 | 0 |

Two `AMBIGUOUS` items are excluded from every matrix below rather than forced to a side, leaving
**9 positives and 21 negatives**.

## 3. Round 1 — an apparent perfect separation

| signal | hallucination (n=5) | real speech / ASR error (n=13) | separates |
|---|---|---|---|
| `no_speech_prob` | 0.759 – 0.926 | 0.090 – 0.524 | **yes**, gap 0.235 |
| `avg_logprob` | −0.985 – −0.441 | −0.983 – −0.092 | no |
| `compression_ratio` | 0.727 – 2.213 | 0.609 – 2.155 | no |
| `temperature` | 4 of 5 at 0.0 | 4 of 13 non-zero | no |

Any cut in 0.60–0.75 gave precision 1.00 and recall 1.00, in **both** instructors' lectures. Applied
to the whole corpus, `nsp ≥ 0.70` fires on 10 windows / 24 segments — **0.44 % of the transcript,
1.71 warnings per hour**. A tolerable burden with apparently perfect accuracy.

That combination is what made round 2 necessary rather than optional.

## 4. Round 2 — the design that broke it

Two strata, chosen so that neither could flatter the hypothesis:

| stratum | n | question |
|---|---|---|
| **P** — every `nsp ≥ 0.70` window not yet labelled | 4 | does the rule fire on real speech? |
| **R** — low-`nsp` regions where hallucination is structurally plausible | 8 | does the rule miss hallucination? |

Stratum R was built from **structure, not signal**: segments isolated between long no-speech gaps, and
first segments after gaps of 30 s to 178 s. Both strata produced counterexamples.

**Missed by the rule (`nsp < 0.70`, yet hallucination):**

```text
R12  고춧가루               nsp 0.616   logp -0.876   cr 0.57   T 0.0
R05  글씨가 찍어져있네요     nsp 0.467   logp -1.173   cr 0.72   T 1.0
```

**Falsely flagged (`nsp ≥ 0.70`, yet speech existed):**

```text
R09  멀리 떨어져서 그 어느 바람 쐬인 쓸쓸한 거리 끝에 헤매였다.   nsp 0.716   REAL_SPEECH
R08  그리고                                                  nsp 0.733   ASR_ERROR
```

R09 is **poem recitation**. That is the mechanism behind the false positives: `no_speech_prob`
measures how unlike ordinary speech a window sounds, and recitation, quiet delivery and distant
voices all raise it. Round 1 contained no recitation, so the failure mode was invisible.

## 5. Combined results (n = 30)

```text
hallucination  0.467  0.616  0.727  0.759  0.836  0.872  0.886  0.896  0.926
real speech    0.090 … 0.504  0.524  0.546  0.603  0.716  0.733
                                                    ^^^^^^^^^^^^  overlap
```

| rule | TP | FP | FN | precision | recall |
|---|---|---|---|---|---|
| `nsp ≥ 0.45` | 9 | 7 | 0 | 0.56 | 1.00 |
| `nsp ≥ 0.60` | 8 | 3 | 1 | 0.73 | 0.89 |
| `nsp ≥ 0.70` | 7 | 2 | 2 | **0.78** | **0.78** |
| `nsp ≥ 0.75` | 6 | 0 | 3 | 1.00 | 0.67 |
| `avg_logprob ≤ −0.80` | 5 | 3 | 4 | 0.62 | 0.56 |
| `avg_logprob ≤ −0.90` | 2 | 2 | 7 | 0.50 | 0.22 |

No single-signal cut achieves both. `nsp ≥ 0.75` reaches precision 1.00 only by missing a third of the
hallucinations.

### Combination rules — fitted, not validated

The two misses have `avg_logprob` of −0.876 and −1.173; the two false positives have −0.466 and
−0.300. The signals are complementary, and combinations do better on this set:

| rule | TP | FP | FN | precision | recall |
|---|---|---|---|---|---|
| `nsp ≥ 0.55` OR `logp ≤ −1.00` | 9 | 4 | 0 | 0.69 | **1.00** |
| `nsp ≥ 0.75` OR `logp ≤ −0.85` | 8 | 2 | 1 | 0.80 | 0.89 |
| `nsp ≥ 0.75` OR `logp ≤ −1.20` | 6 | 0 | 3 | 1.00 | 0.67 |

**These are hypotheses, not measurements.** Nine positives fitted against four signals overfits by
construction, and round 1 already demonstrated what a fitted-looking number is worth here. They are
recorded to shape the next sampling design, not to be adopted.

## 6. Confirmed findings independent of any threshold

**A hallucination template reproduces across lectures and instructors' recordings.** The string
`마포구청 인터넷 방송국 홈페이지` occurs three times in the corpus — twice in MVI_0146, once in
MVI_0144 — and **all three are labelled `HALLUCINATION`**. `128` reported the recurrence as a text
pattern; it is now verified.

This matters because a confirmed-string match needs no numeric threshold. It is the one part of this
investigation that could become a rule without inventing a number, though whether a
provider-independent contract should encode provider-specific strings is an open question and not
decided here.

**Neighbouring templates.** `한국국토정보공사`, `제주도에서 가장 유명한 곳은 대한민국 ×9`, and
`시험장에 오신 것을 환영합니다 / 다음 영상에서 만나요` were all confirmed hallucination — the
institution-name and video-outro families Whisper is known to emit over non-speech.

**Speaker identity does not change the label, but explains signal behaviour.** Two labeler notes
record that the speaker was a student rather than the instructor, and one records inaudibility.
Combined with R09's recitation, the pattern is consistent: `no_speech_prob` rises with acoustic
atypicality, not with fabrication.

## 7. Corrections to `127` and `128`

Neither prior record is rewritten. Both contain claims the labels now contradict, and the corrections
belong here.

| where | prior claim | verified result |
|---|---|---|
| `127` §readiness, §8 | "`no_speech_prob ≥ 0.813` fires once, on `감사합니다.` — **real speech**. Precision 0 %" | **`감사합니다.` is `HALLUCINATION`** (round 2, R03). That cut's precision on the full lecture was 1.00, not 0. |
| `127` §12 | "`no_speech_prob` — **not usable alone** … full-lecture maximum is real speech" | The stated *reason* was wrong. The conclusion — not usable alone — survives, on the evidence in §4 above. |
| `127` §11, §12 | "`avg_logprob` — most promising" | Weakest of the two on labelled data: precision 0.62, recall 0.56 at its best single cut. |
| `128` §10 | "`avg_logprob` — still the most promising, and now it has something to find" | Same correction. What it "found" included real speech. |

The common cause is stated plainly because it is the transferable lesson: **both records judged
transcripts by reading them.** `감사합니다.` was assumed real because a closing pleasantry is
plausible; `너무 쉽지?` (`avg_logprob` −0.983, the lowest in its lecture) was assumed suspicious
because its signal was extreme, and it is real speech. Text plausibility and signal extremity both
failed as proxies for listening.

`127`'s own framing — that perfect separation on one positive measures a gap, not a rule — was
correct, and applies equally to round 1's five.

## 8. What the next calibration needs

Random sampling is not viable: the hallucination base rate is 0.1–0.6 % of segments, so 100 random
clips would yield roughly one positive.

The efficient frame is **structural, not signal-based**, which is what keeps it free of the
circularity that spoiled round 1:

| stratum | segments | % of corpus | covers of the 9 known positives |
|---|---|---|---|
| gap ≥ 10 s, within 30 s either side | **221** | **4.0 %** | **8 / 9** |
| gap ≥ 20 s, within 30 s | 151 | 2.8 % | 7 / 9 |
| gap ≥ 20 s, within 120 s | 471 | 8.6 % | 7 / 9 |

Exhaustively labelling the first stratum — about 75 minutes of listening — would yield an estimated
30–50 positives, a clean denominator for the first true recall measurement, and a sample no signal
helped select.

A 50-minute variant labels only MVI_0146 and MVI_0147 and holds MVI_0144 back entirely, which would
answer the question neither round could: **does a rule fitted on some lectures hold on a lecture it
never saw?**

Neither was run. The session ended here by decision.

## 9. Repository impact

No canonical data created, modified or back-filled. No production code, test, schema, Blueprint or
PATCH changed. Labeling ran read-only over scratch evidence.

The labeling packages (clips, manifests, README, local labeling page) contain real classroom audio
including student voices and transcript text, and live under `evaluation/`, excluded from Git via
`.git/info/exclude` following the `e2e-results/` precedent. **Nothing from them is committed** — the
repository stores no classroom audio or transcript content.

## 10. Result

```text
Human labels assigned by agent: 0
Confirmed hallucinations: 9
Threshold selected: No
PATCH created: No
Blueprint changed: No
Production diagnostic rule changed: No

THRESHOLD READINESS: MORE_DATA_REQUIRED
```

The corpus now holds its first verified positives, a confirmed cross-lecture hallucination template,
a mechanical explanation for the leading signal's false positives, and a sampling design that would
produce an unbiased measurement. What it does not hold is enough labelled positives to fix a number,
and this record declines to invent one.

```text
Requires Architect Decision: No
Requires Blueprint Clarification: No
Requires Blueprint PATCH: No
```
