# P Population Drift Distribution — Gating Measurement (Evaluation)

- Status: Evaluation Record
- Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` §15 TD-2/TD-5/TD-7 / `PATCH-0046`
- Production impact: **none** — no PATCH, no Blueprint change, no schema change, no code change
- Related: `132`, `134`, `135`, `136_TIMING_REFINEMENT_AND_CORRECTION_BOUNDARY_DECISION.md` §5/§7

## Purpose

`136` §7 named one measurement as the gate on everything downstream:

> Measure the drift distribution across the P population. If nearly all are sub-second, the
> correction boundary may not be worth building and the whole line reduces to a diagnostic.

This record is that measurement. It answers the gate and nothing else. No PATCH, no implementation.

## 1. Method

Reused unchanged from `132` §3 — energy-based acoustic onset, as scratch evaluation tooling with no
repository write and no production capability:

```text
local floor : 10th percentile RMS over the 15 s preceding the segment's claimed start
threshold   : floor + 8 dB
onset       : first of 3 consecutive 50 ms frames above threshold
drift       : onset − segment.start
```

Applied to all **31** P firings of MVI_0147, from the persisted evidence of the `134` measurement
repository. One firing produced no detection (§2).

**This measures acoustic onset, which is a lower bound on speech onset.** Where the adjacent class
bleeds through, the level rises before the instructor speaks, so the figures below are conservative
in the direction of *understating* drift.

## 2. Method validation — weaker here than in `132`

`132` validated this method against four human observations and got 3 of 4 within ±5 s. Repeated on
the same four cases inside the P population:

| human (`131` §5) | measured here | agreement |
|---|---|---|
| `너무 쉽지?` ~27 s | 18.65 s | −8.4 s |
| `얘들아 사전 잘 볼 줄 알죠?` ~10 s | 19.05 s | +9.1 s |
| `다 했나요?` ~24 s | 5.60 s | −18.4 s |
| `오늘 얼마나 알차게…` ~7 s | 0.10 s | −6.9 s |

**Only 0 of 4 land within ±5 s.** That is materially worse than `132` reported, and the difference is
explained by the change in floor estimation: `132` derived the floor from the preceding *no-speech
gap*, which was always long for its post-silence population. Here the P population is dominated by
sub-second gaps, so the floor is taken from a 15-second window that mostly contains speech — which
raises the threshold and moves the detected onset.

Two further caveats compound: this run's segmentation differs from the run the humans listened to
(ASR is non-deterministic, `122`), so the matched segments are not always the same utterance; and the
human figures were themselves approximate ("대략 30초쯤").

**Consequence: individual drift values below are not reliable.** The distribution's *shape* is
usable — the method separates near-zero from clearly-late with the right sign in every case — but no
single number should be quoted as that segment's drift, and none is quoted as such in §4.

## 3. Distribution

n = 30 measured, 1 undetected.

```text
min 0.00 s    median 0.68 s    mean 2.64 s    max 19.05 s
```

| band | count | share of the 31 |
|---|---|---|
| < 0.5 s | 12 | 38.7 % |
| 0.5 – 1 s | 4 | 12.9 % |
| 1 – 2 s | 6 | 19.4 % |
| 2 – 5 s | 4 | 12.9 % |
| ≥ 5 s | 4 | 12.9 % |
| undetected | 1 | 3.2 % |

**Roughly half (16 of 31, 51.6 %) are under one second.** Eight are 2 s or more; four are 5 s or more.

## 4. What separates the material cases

The anchor gap — how far the decode window opened past the previous coverage — predicts drift far
better than anything else available:

| | n | median drift | max | ≥ 2 s |
|---|---|---|---|---|
| anchor gap ≥ 10 s | 6 | **5.00 s** | 19.05 s | **5 of 6** |
| anchor gap < 10 s | 24 | **0.50 s** | 6.60 s | 3 of 24 |

The eight cases at 2 s or more:

```text
19.05s   gap 85.50s   얘들아 사전 잘 볼 줄 알죠?
18.65s   gap 30.00s   너무 쉽지?
 6.60s   gap  0.90s   나중에 우리 높임 표현할 때 같이 할 거야.
 5.60s   gap 60.00s   다 했나요?
 4.40s   gap 21.00s   자 문제 술술술술술 풀려야 될텐데
 4.30s   gap 17.00s   마찬가지로 생략가능해요
 3.70s   gap  0.18s   자 뒤로 넘겨서 아 아 그리고 …
 3.65s   gap  0.94s   쉬운거 써도 되요
```

Five of the six large-gap firings are material. But **three of the eight have gaps under one second** —
so a large anchor gap is a good indicator and not a sufficient one, and the converse fails too.

This matters for what it does *not* license. It is tempting to read the table as "cut at 10 s". That
would be inventing the duration threshold `PATCH-0046` TD-6 refuses, on 30 points from one lecture,
and it would miss the 6.60 s case whose gap is 0.90 s. **No cut is proposed.**

## 5. Answering the gate

`136` §5 framed the open question as: *is this a 6-segments-per-lecture problem or a
31-segments-per-lecture problem?*

**Neither, and the answer is closer to the smaller number.** About **8 per lecture** carry drift of
2 s or more, and about **4 per lecture** carry 5 s or more. The rest are sub-second — within the range
a subtitle would show anyway, and not worth a person's time.

The gate condition in `136` §7 was "if nearly all are sub-second, the line reduces to a diagnostic".
That condition is **not met**: half are sub-second, but a quarter are 2 s or more and an eighth exceed
5 s, reaching 19 s. Two subtitles per lecture-hour appearing five or more seconds early is a real
defect, not noise.

**The correction boundary remains justified.** At ~8 material cases per lecture it is also
comfortably human-scale — a few minutes of listening per lecture, not an afternoon.

## 6. What this does not establish

- **No individual drift value is reliable** (§2). Only the distribution's shape is.
- **One lecture, one instructor, one model** — `PATCH-0046` TD-20's limitation is unchanged.
- **No threshold is proposed**, and the gap/drift relationship in §4 is an observation about this
  corpus, not a rule.
- **Nothing here evaluates a refinement mechanism.** L-16's two conditions remain unmeasured, exactly
  as `136` TR-4 left them.
- The measurement says nothing about the ~2,339 segments outside P; it characterises the diagnostic's
  output, not the transcript.

## 7. Next gate

`136` §7's ordering stands, with step 1 now closed:

```text
1. ✅ measure the drift distribution across P          — this record
2. →  PATCH the timing correction candidate boundary   (136 TC-1…TC-6)
3.    evaluate refinement mechanisms against accumulated human corrections (L-16, both conditions)
4.    refinement PATCH                                 (136 TR-1…TR-4)
```

**Step 2 is now the next gate.** Its scope is unchanged from `136` TC-2: one candidate kind proposing
a time range instead of a text, targeting one segment of the current Raw Transcript, carrying a
snapshot of the timing it replaces, flowing through unchanged `§18` and `§19`.

One thing this measurement adds to that scope: since half the firings are sub-second, the correction
workflow should expect most findings to be dismissed rather than corrected. That is an argument for
making *rejection* as cheap as acceptance — which `§18` H-2's accept/reject model already provides,
and which is worth stating explicitly when the PATCH is written.

A second measurement, not blocking: repeating this on MVI_0144 or MVI_0146 would test whether the
~8-material-cases-per-lecture figure holds across instructors. It costs one ASR run per lecture and
should not gate step 2.

## 8. Result

```text
Population measured:        31 P firings, MVI_0147 (1.96 h)
Method:                     energy-based acoustic onset (132 §3), lower bound
Method reliability here:    0/4 human observations within ±5 s — individual values unreliable,
                            distribution shape usable (§2)
Distribution:               median 0.68 s, mean 2.64 s, max 19.05 s
                            < 1 s: 16 (51.6 %)   ≥ 2 s: 8 (25.8 %)   ≥ 5 s: 4 (12.9 %)
Gate condition:             "nearly all sub-second" — NOT met
Timing correction needed:   Yes — ~8 material cases per lecture, human-scale

PATCH created: No
Blueprint changed: No
Schema changed: No
Production changed: No
Threshold proposed: No

Requires Architect Decision:      No — 136's decisions stand
Requires Blueprint Clarification: No
Requires Blueprint PATCH:         Yes — timing correction candidate boundary (136 TC), next session
Requires additional measurement:  Not blocking — a second lecture would test cross-instructor
                                  stability but should not gate the PATCH
```
