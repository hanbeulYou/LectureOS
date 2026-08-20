# Structural Population Human Labels — Unbiased Signal Analysis (Evaluation)

- Status: Evaluation Record
- Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` §15 QD-12/QD-14 (threshold Deferred) / `PATCH-0045`
- Production impact: **none** — no PATCH, no threshold, no firing rule, no schema, no code change
- Related: `127`, `128`, `129`, `130_TRANSCRIPT_QUALITY_STRUCTURAL_POPULATION_LABELING.md`
  (**none rewritten**; corrections recorded in §8)

## 1. Summary

All 221 candidates of the signal-independent structural population were labelled by ear. This is the
first measurement in this project taken on a sample that no provider signal helped select.

```text
HALLUCINATION  24      REAL_SPEECH 152      ASR_ERROR 26      AMBIGUOUS 19
```

Two findings dominate, and the second was not being looked for.

**`no_speech_prob` cannot detect most hallucinations here — not as a matter of threshold, but of
mechanism.** A follow-up listening pass over the 14 low-`no_speech_prob` hallucinations found audible
human speech in **11** of them, repeatedly annotated *"옆방 수업 소리"* — a class next door. The signal
was not wrong; it correctly reported that speech was present. Whisper then invented a sentence over
speech it could not resolve. On the whole population `nsp ≥ 0.70` scores **precision 1.00, recall
0.33**.

**Transcript timestamps run early after silence.** Five labeler notes independently report the target
utterance starting 7–27 s later than the transcript claims, always on the first segment after a long
no-speech gap. Measured on the released SRTs, cues in that position average **1.9× the normal
duration** and exceed the 7-second readability warning **21 %** of the time against **0.3 %**
elsewhere. This affects subtitle timing, not only diagnostics.

```text
THRESHOLD READINESS: MORE_DATA_REQUIRED
```

## 2. Labels

| lecture | instructor | candidates | hallucination | rate |
|---|---|---|---|---|
| MVI_0144 | 원장님 | 36 | 2 | 5.6 % |
| MVI_0146 | 원장님 | 86 | **15** | 17.4 % |
| MVI_0147 | 장혜정 선생님 | 99 | 7 | 7.1 % |
| **total** | | **221** | **24** | 10.9 % |

19 `AMBIGUOUS` are excluded from every matrix rather than forced to a side, leaving **24 positives
and 178 negatives**.

MVI_0146's rate is three times MVI_0144's. It is also the lecture with the most no-speech time
(725 s, 10.9 % of its length). Hallucination tracks silence, not the instructor: both these lectures
are 원장님's.

## 3. Hallucination subtypes

The 14 hallucinations with `no_speech_prob < 0.55` were re-heard, asked one question only — *is there
human speech at this point, or actual silence?*

```text
사람 소리 있음 (SPEECH)  11
진짜 무음 (SILENT)        2
모르겠음 (UNSURE)         1
```

Combined with the 10 high-`nsp` hallucinations, the positive population splits:

| subtype | count | `no_speech_prob` | detectable by `nsp` |
|---|---|---|---|
| **over distant speech** | **11** | 0.19 – 0.55 (ordinary) | **no, by construction** |
| over silence | 12 | 0.33, 0.55 – 0.93 | yes |
| unresolved | 1 | 0.34 | — |

Labeler notes name the source directly: `옆방 수업 소리`, `옆방 소리 추정`. The rooms are adjacent to
other classes, and Whisper transcribes that bleed-through as invented sentences.

**This is why lowering the threshold cannot work.** For these 11 the signal reports speech because
speech is genuinely present. The information needed to separate them is not in `no_speech_prob` at
all.

## 4. Signal evaluation (unbiased sample)

### Against all 24 hallucinations

| rule | TP | FP | FN | precision | recall |
|---|---|---|---|---|---|
| `nsp ≥ 0.55` | 10 | 27 | 14 | 0.27 | 0.42 |
| `nsp ≥ 0.60` | 9 | 16 | 15 | 0.36 | 0.38 |
| `nsp ≥ 0.70` | 8 | 0 | 16 | **1.00** | **0.33** |
| `nsp ≥ 0.75` | 7 | 0 | 17 | 1.00 | 0.29 |
| `avg_logprob ≤ −0.90` | 9 | 0 | 15 | **1.00** | 0.38 |
| `avg_logprob ≤ −0.80` | 15 | 15 | 9 | 0.50 | 0.62 |
| `avg_logprob ≤ −0.70` | 16 | 19 | 8 | 0.46 | 0.67 |

### Against the 12 over-silence hallucinations only

| rule | TP | FP | FN | precision | recall |
|---|---|---|---|---|---|
| `nsp ≥ 0.70` | 8 | 0 | 4 | 1.00 | **0.67** |
| `nsp ≥ 0.60` | 9 | 16 | 3 | 0.36 | 0.75 |
| `nsp ≥ 0.55` | 10 | 27 | 2 | 0.27 | 0.83 |

Recall roughly doubles once the undetectable subtype is removed from the denominator, which is the
clearest statement of what the signal actually measures: **silence, not fabrication.**

Both `nsp ≥ 0.70` and `avg_logprob ≤ −0.90` reach precision 1.00 with zero false positives across 178
negatives. That is a materially better result than any earlier round produced, and it is the first
such number taken on an unbiased sample. Neither is proposed as a threshold here.

## 5. Timestamp drift after silence — a separate defect

Five labeler notes, unprompted and consistent:

```text
S05  전사 3727.8s   실제 발화 ~24s 늦게
S10  전사 3362.2s   실제 발화 ~27s 늦게
S11  전사 3419.6s   실제 발화 ~7s 늦게
S12  전사 4264.7s   실제 발화 ~10s 늦게
S13  전사 4324.7s   실제 발화 ~24s 늦게
```

Every case is the first segment after a long no-speech gap, and the user confirms the effect does not
appear in ordinary speech. The mechanism is consistent with Whisper anchoring a segment's start to
the beginning of its decode window rather than to speech onset when the window opens on silence.

Measured independently on the two released SRTs — no labels needed:

| position | cues | mean duration | > 7 s |
|---|---|---|---|
| first cue after a ≥ 10 s gap | 19 | **5.3 s** | **21 %** |
| everywhere else | 4,265 | 2.8 s | 0.3 % |

A 1.9× duration inflation concentrated entirely in post-silence position, with the readability
warning rate 70× higher there.

### Why this matters beyond diagnostics

`124` recorded `READABILITY_DURATION_ABOVE_MAXIMUM` warnings on both new lectures (10 and 8). This
analysis suggests a substantial share of them are not editorial — they are this artefact. The
released SRTs place those subtitles up to 27 seconds early.

### What it is not

Not a `§14` contract violation. A-10 constrains ordering, positivity and non-overlap; A-11 requires
text preserved exactly; A-14 states admission "media 파일을 읽지 않는다". Nothing in the released
contract claims a segment's start marks speech onset, and nothing there could detect this, because the
boundary never reads the audio.

Classification: **provider behaviour with a downstream product consequence**, currently uncontracted.
Deciding whether LectureOS should have an opinion about it is an Architect Decision this record does
not take.

## 6. Cross-instructor

| | 원장님 | 장혜정 선생님 |
|---|---|---|
| candidates | 122 | 99 |
| hallucinations | 17 | 7 |
| `nsp ≥ 0.70` false positives | 0 | 0 |
| over-distant-speech subtype | present | present |

Both rules hold with zero false positives in both instructors' material. The subtype appears in both,
so the bleed-through condition is not specific to one room or one recording.

## 7. Test–retest reliability

18 candidates had been labelled in earlier rounds. Their prior labels were hidden.

```text
agreement 12/18 (67%)
```

All six disagreements move **toward** `HALLUCINATION`:

| | round 1/2 | this round |
|---|---|---|
| `너무 쉽지?` | REAL_SPEECH | HALLUCINATION |
| `다 했나요?` | REAL_SPEECH | HALLUCINATION |
| `고추냉이` | ASR_ERROR | HALLUCINATION |
| `3시간 정도만 자면…` | ASR_ERROR | HALLUCINATION |
| `이곳은 대한민국에서…` | AMBIGUOUS | HALLUCINATION |
| `네.` | ASR_ERROR | AMBIGUOUS |

The `고추냉이` case was resolved directly with the labeler and explains the pattern: distant human
speech was audible, so *"there was speech"* (→ `ASR_ERROR`) and *"nobody said that"* (→
`HALLUCINATION`) were both defensible readings of the rule as written. **The vocabulary had a gap at
exactly the subtype that turns out to be the majority class**, and the earlier, shorter clips gave
less of the surrounding silence to judge from.

The label definition should be tightened before the next round: `ASR_ERROR` requires an utterance the
transcript plausibly corresponds to, not merely audible speech nearby. This record does not
retroactively relabel anything.

Consequence for the earlier records: the 14 previously-labelled candidates that fall outside this
population carry the same ambiguity and should be treated as lower-confidence.

## 8. Corrections to earlier records

Additive, as before; nothing rewritten.

| where | prior claim | now |
|---|---|---|
| `129` §5 | `nsp ≥ 0.70` at precision 0.78 / recall 0.78 | On the unbiased sample: precision **1.00**, recall **0.33**. The earlier figure came from a signal-selected sample of 30. |
| `129` §6 | `고추냉이` labelled `ASR_ERROR`, cited as a weak-signal non-hallucination | Relabelled `HALLUCINATION` with the mechanism identified (distant speech). |
| `129` §8 | estimated 30–50 positives from this stratum | actual **24** |
| `130` §8 | listening estimate 24 min | actual effort substantially higher; the estimate counted audio duration, not the work of judging 221 lines |

The last one is a recurring error worth naming: audio length is not labeling effort.

## 9. Repository impact

```text
Production code changed: No
Schema changed:          No
Blueprint changed:       No
PATCH created:           No
Canonical records changed: No
```

Evaluation-only. The labeling packages remain under `evaluation/`, git-excluded.

**Data loss note.** The session scratchpad was cleared by the OS between sessions, taking the three
lectures' extracted evidence JSON, the scratch repositories, and the ASR outputs. Surviving: the
`evaluation/` manifests (which carry provider evidence for all 221 candidates), the released SRTs,
and the committed reports. The analyses above were reconstructed from those. Re-running the corpus
would cost roughly three hours of ASR. Future evaluation artefacts needed across sessions should not
live only in the scratchpad.

## 10. Next steps

Not decided here; listed with what each would settle.

1. **Tighten the `ASR_ERROR` / `HALLUCINATION` definition** for distant speech, then re-check the 6
   disagreements. Cheap, and everything downstream depends on the labels meaning one thing.
2. **Decide whether the post-silence timestamp drift is in scope.** It has a concrete product
   consequence — subtitles up to 27 s early — and is currently uncontracted. Architect Decision.
3. **A rule targeting the over-distant-speech subtype**, which no preserved signal currently
   separates. May require evidence LectureOS does not yet keep.
4. **More lectures** — `127`'s ≥ 5 remains unmet at 3. Lower priority than 1 and 2: with test–retest
   at 67 %, more labels of the same kind would widen confidence intervals rather than narrow them.

## 11. Result

```text
Human labels assigned by agent: 0
Confirmed hallucinations: 24 (structural population) 
Threshold selected: No
Diagnostic firing rule activated: No
PATCH created: No
Blueprint changed: No

THRESHOLD READINESS: MORE_DATA_REQUIRED

Requires Architect Decision: Yes — post-silence timestamp drift (§5), scope undecided
Requires Blueprint Clarification: No
Requires Blueprint PATCH: No
```
