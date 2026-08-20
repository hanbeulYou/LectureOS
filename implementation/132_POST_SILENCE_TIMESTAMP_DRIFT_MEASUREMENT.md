# Post-Silence Transcript Timestamp Drift — Focused Empirical Measurement (Evaluation)

- Status: Evaluation Record
- Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` §14 A-10/A-11/A-14, §15 L-5/L-6/L-16;
  `docs/041_SUBTITLE_PIPELINE.md` §7, §16
- Production impact: **none** — no PATCH, no threshold, no firing rule, no schema, no code change
- Related: `122`, `124`, `129`, `130`, `131_STRUCTURAL_POPULATION_LABEL_ANALYSIS.md` (**none rewritten**)

## 1. Repository investigation

Read: `040` §4.1–§4.3, §14 A-10/A-11/A-14, §15 L-5/L-6/L-16 and the `PATCH-0045` diagnostic
subsection; `041` §7 and §16; `PATCH-0039/0040/0041/0043/0045`; reports `122`, `124`, `129`, `130`,
`131`.

**A constraint that shaped what was possible.** The session scratchpad was cleared by the OS between
sessions, taking the three lectures' extracted evidence JSON, the scratch repositories and the ASR
outputs (recorded in `131` §9). Surviving and used here:

| source | what it gave |
|---|---|
| `evaluation/transcript-quality-structural-labeling/manifest_analysis.csv` | 221 candidates with provider timestamps, decode-window bounds, all four signals, and a parseable `structural_inclusion_reason` |
| released SRTs (`MVI_0146`, `MVI_0147`) | full cue timing for readability attribution and controls |
| media files (all three) | audio for onset measurement |
| `131` §5 | four human speech-onset observations, used to validate the automated method |

The post-silence population was **reconstructed from the manifest**, not re-derived from a new rule:
`structural_inclusion_reason` records `"<N>s no-speech gap at <a>-<b>s (0.0s after)"` for exactly the
first segment following each qualifying gap. No number in the handoff prompt was used as source of
truth.

## 2. Population reconstruction

The `130` structural definition is unchanged: gap ≥ 10.0 s, reach 30.0 s. The post-silence subset is
every segment marked `(0.0s after)`.

| lecture | instructor | gaps ≥ 10 s | post-silence first segments |
|---|---|---|---|
| MVI_0144 | 원장님 | 3 | 3 |
| MVI_0146 | 원장님 | 12 | 12 |
| MVI_0147 | 장혜정 선생님 | 8 | 8 |
| **total** | | **23** | **23** |

Consistent with `130` §4's gap counts.

## 3. Ground-truth method

I cannot listen. Acoustic onset was therefore measured **objectively**, by energy, as a scratch
evaluation tool — no production capability, no repository write:

```text
noise floor  : median RMS over the 20 s preceding the gap end
threshold    : 90th percentile of that gap's RMS, +6 dB
onset        : first of 3 consecutive 50 ms frames above threshold
```

**This measures acoustic onset, which is a lower bound on speech onset.** In rooms with bleed-through
from an adjacent class — the condition `131` identified as the majority hallucination context — the
level rises on that bleed-through, not on the instructor's speech.

### Validation against human observation

`131` recorded four human onset observations for segments in this population. They were not used to
build or tune the method.

| segment | human | measured | difference |
|---|---|---|---|
| MVI_0147 @ 4324.7 | ~24 s | 24.1 s | **+0.1** |
| MVI_0147 @ 3419.6 | ~7 s | 7.7 s | **+0.7** |
| MVI_0147 @ 3362.2 | ~27 s | 22.2 s | −4.8 |
| MVI_0146 @ 3727.8 | ~24 s | 0.6 s | **−23.4** |

Three of four agree within ±5 s. The fourth is the predicted failure mode: bleed-through is audible
from the segment's start, so energy fires immediately while the instructor speaks 24 s later.

**Consequence for every number below: measured drift is a floor.** Where bleed-through is present the
true drift is larger. This biases against the drift hypothesis, so the effect reported is
conservative.

Four of 23 produced no detection at all — peak only 11–15 dB above floor, i.e. nothing distinct
happened. Two of those four (`고추냉이`, `글씨가 찍어져있네요`) are human-confirmed hallucinations.

## 4. Ground-truth results

Drift = acoustic onset − provider segment start, 19 of 23 measured.

```text
median  4.10 s      mean 7.74 s      max 39.20 s      > 5 s : 8 of 19
```

The distribution is bimodal rather than a smooth spread: eleven cases under 5 s, eight between 5.6 s
and 39.2 s.

## 5. Decode-window analysis

This is the clearest result in the measurement.

| observation | result |
|---|---|
| `provider_start == decode_window_start` | **20 / 23** |
| segment duration exactly 30.00 s | 6 / 23 |
| of the 8 cases with drift > 5 s, `provider_start == window_start` | **7 / 8** |

Twenty of twenty-three post-silence segments begin at the exact instant their decode window opens,
and six carry a duration of exactly 30.000 s — the Whisper decode window length. A 30-second segment
for a two-word utterance is the artefact in its plainest form.

**The decode-window anchoring hypothesis is supported.** When a window opens on silence, the emitted
segment's start is the window boundary, not speech onset.

Two qualifications. First, `provider_start == window_start` is also true for many low-drift cases, so
window anchoring is necessary but not sufficient to produce large drift — what varies is how long the
window waits before speech arrives. Second, `§15` CP-13 resume assembly could in principle re-base a
window anchor, but no lecture in this corpus was resumed (`128` records all three as `fresh`), so
checkpoint mechanics are excluded as a cause.

## 6. Gap-length relationship

```text
gap 12s → 0.15    30s → 22.25    58s → 0.55    86s →  2.85
    13s → 5.90    30s →  5.65    58s →  0.95   168s →  0.30
    16s → 2.40    42s → 24.10    60s →  1.80
    16s → 7.40    48s → 13.50    65s → 39.20
    17s → 3.65                   75s →  0.00
    21s → 4.60
    26s → 7.65
    28s → 4.10
```

```text
r = -0.070  (n = 19)
```

**H1 (proportional) is rejected.** Essentially zero correlation, and the extremes contradict it
directly: the 168 s gap drifts 0.3 s while a 65 s gap drifts 39.2 s.

**H2 (decode-window boundary) is the best-supported.** Drift is not a function of how long the silence
lasted but of where the window boundary happens to fall relative to the next utterance — consistent
with §5's finding that the start is pinned to the window.

**H4 is rejected** — the phenomenon is real and separates from controls (§7).

H3 cannot be excluded on 19 points, and the sample is too small to fit anything.

## 7. Negative controls

Same measurement, same threshold, three strata.

| stratum | n | detected | median drift | > 5 s |
|---|---|---|---|---|
| after gap ≥ 10 s | 23 | 19 | **4.10 s** | **8** |
| after short gap 3–8 s | 12 | 7 | 5.90 s | 4 |
| ordinary speech | 16 | 4 | **1.62 s** | **0** |

Ordinary speech shows **no case above 5 s** and a median under 2 s, most of which is the natural lag
between a cue boundary and the next syllable. The labeler's report that the effect is absent in
ordinary speech is independently confirmed.

The short-gap stratum sits between the two, which is what H2 predicts: shorter silence still opens a
window, just with less room for the boundary to land far from speech.

## 8. Candidate timing comparison

**Not evaluated — and this is a deliberate stop, not an omission.**

Candidate 1 (existing VAD) could not be assessed within this session's constraints. A meaningful
comparison requires re-transcribing at least one full lecture with `vad_filter=True` and diffing
against the released baseline for both onset error **and** real-speech loss. The baseline outputs were
lost with the scratchpad, so the comparison would need roughly two hours of ASR to rebuild both
sides. `122` already recorded that VAD "dropped real instructor speech" and produced a 212-second cue
for a two-second utterance; re-running would test whether that still holds, and nothing here
supersedes it.

Candidate 2 (existing audio-grounded alternatives): faster-whisper exposes `word_timestamps`, which
would give per-word alignment and is already in the installed dependency — no new library. It was
**not evaluated** here for the same reason: it changes the decode call and requires re-running ASR to
compare.

Recording both as `not evaluated` rather than guessing is the correct outcome under §9's rules. This
directly determines the decision gate.

## 9. Readability impact

Attributed to the **source segment**, not cue position — readable composition splits a long segment
into several cues, so position-based counting undercounts.

| lecture | `READABILITY_DURATION_ABOVE_MAXIMUM` (> 7 s) | from a post-silence segment |
|---|---|---|
| MVI_0146 | 10 | **8 (80 %)** |
| MVI_0147 | 8 | **5 (62 %)** |
| **total** | **18** | **13 (72 %)** |

**72 % of the duration warnings on these lectures originate in this artefact, not in editorial
content.** Twenty post-silence segments occupy 295 seconds of subtitle time across the two lectures.

No readability parameter was changed, no warning suppressed, and v2 is untouched. `124`'s figures
stand; this only attributes them.

## 10. Contract assessment

The Architect Decision is **confirmed, and sharpened at two points.**

Confirmed: this is a Transcript Timing Quality gap exposed by provider behaviour; no released clause
is violated. `§14` A-10 constrains ordering, positivity and non-overlap only; nothing states that
`segment.start` marks acoustic onset; A-14's "media 파일을 읽지 않는다" means admission structurally
cannot detect this.

Sharpened:

- **The corrective layer decision is reinforced by mechanism.** Drift is set at decode time by where
  the window boundary falls. It is not recoverable from the transcript, so §5 and §6 confirm that
  neither `§14` Admission nor `041` Time Representation can fix it without audio — exactly the
  prohibition the decision already made.
- **The `041` blast radius is larger than assumed.** The decision treated this as a timing-accuracy
  issue; it is also the dominant source of readability duration warnings (72 %). That does not move
  corrective ownership, but it does mean `041`'s warning burden is partly a symptom.

`§15` L-16 remains the governing constraint on any provider-side fix: it declined VAD for two reasons
— real-speech deletion and unusable segment durations — and stated the deferral is reasoned, not
permanent, and can be revisited by a contract that solves **both**. This measurement quantifies the
second. It says nothing about the first, and §8 explains why.

## 11. Decision gate result

```text
DIAGNOSTIC_ONLY_READY
```

The phenomenon is reproduced, localised and mechanically explained: 20 of 23 post-silence segments
are pinned to their decode-window boundary, drift reaches 39 s, controls separate cleanly, and gap
length does not predict it. That is enough to contract a **timing-quality diagnostic**.

It is not enough to choose a correction mechanism. Neither candidate was evaluated, so real-speech
loss under correction is unmeasured — and L-16 makes that measurement a precondition, not a detail.
`READY_FOR_TIMING_PATCH` would require asserting a mechanism this session did not test.

## 12. Required next PATCH scope

Only the diagnostic half. No PATCH is written here.

**Where.** `docs/040` §15, alongside the `PATCH-0045` Transcript Quality Diagnostic subsection, as an
additive forward note plus a new decision block. `§14` A-10 and A-11 keep their released text and gain
forward notes recording that neither claims onset semantics.

**Questions to contract.**

1. Is post-silence timestamp drift a **Quality Warning**, in the same sense QD-2 gives hallucination —
   never a Validation Failure, never blocking admission, Raw Transcript, selection or publication?
2. What is the evidence basis? Decode-window bounds are already preserved by `PATCH-0045` QD-6, so a
   warning could be derived with **no new evidence and no audio access** — but only a *structural*
   warning ("this segment is pinned to its window boundary"), not a drift magnitude.
3. Does the diagnostic report a **magnitude**? Doing so requires audio and therefore belongs to the
   refinement layer, not the diagnostic. Recommended framing: the diagnostic reports the structural
   condition; magnitude stays deferred.
4. Does `041` gain the ability to distinguish a duration warning caused by this from an editorial
   one? §9 shows 72 % attribution, which is a strong argument that it should — but that is an `041`
   contract question and may warrant its own decision.
5. Explicit non-goals: no correction, no offset, no threshold, no VAD adoption, no re-generation of
   released artifacts.

**Deliberately excluded from scope:** any corrective mechanism. That waits on the §8 measurement.

## 13. Repository impact

```text
PATCH created: No          Blueprint changed: No
Schema changed: No         Production timing rule changed: No
Released SRT regenerated: No
Canonical records changed: No
```

Changed: this report only. Measurement ran read-only over the media files and the surviving
manifests; scratch scripts live in `/tmp` and implement no production capability. No canonical
repository exists to mutate — they were lost with the scratchpad and were not rebuilt.

## 14. Remaining risks

- **Onset is measured by energy, not speech.** Where an adjacent class bleeds through, measured drift
  is a floor. One of four validation cases missed by 23 s for exactly this reason.
- **19 measured points across 3 lectures**, and 4 of 23 undetectable. Too few to fit anything; used
  here only to separate hypotheses, not to size an effect.
- **One model, one configuration.** `large-v3`, `condition_on_previous_text=False`, no VAD. Whether
  the anchoring behaviour holds for other models is untested.
- **The 30.000 s duration signature** is consistent with a 30-second decode window but was not
  confirmed against faster-whisper's implementation. §5's claim rests on observation, not source.
- **Correction feasibility is entirely unmeasured**, including whether word timestamps would resolve
  onset without the speech loss L-16 rejected.
- **Corpus rebuild cost.** Re-running all three lectures is ~3 hours of ASR. Any follow-up needing
  baseline outputs should budget it, and future evaluation artefacts should not live only in the
  scratchpad.

## 15. Result

```text
Timing phenomenon reproduced:            Yes — 23 post-silence segments, drift up to 39.2 s
Actual speech-onset ground truth obtained: Partially — energy-based, a lower bound;
                                           validated 3/4 against human observation
Decode-window hypothesis:                Supported — 20/23 pinned to window start;
                                           7/8 of the large-drift cases
Real-speech loss under candidate correction: Not measured — no candidate evaluated
Decision gate:                           DIAGNOSTIC_ONLY_READY

PATCH created: No
Blueprint changed: No
Schema changed: No
Production timing rule changed: No
Released SRT regenerated: No

Requires Architect Decision: No — the existing decision is confirmed
Requires Blueprint Clarification: No
Requires Blueprint PATCH: Yes — timing-quality diagnostic only (§12); correction stays Deferred
Requires additional measurement: Yes — VAD and word-timestamp candidates against
                                 onset error AND real-speech loss (L-16's two conditions)
```
