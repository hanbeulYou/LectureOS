# Real Media Calibration Corpus Expansion — Two New Lectures (E2E + Evaluation)

- Status: Evaluation Record
- Blueprint: unchanged. `docs/040` §14/§15, `docs/041` §16, `PATCH-0040/0043/0044/0045` as released
- Production impact: **none** — no PATCH, no threshold, no firing rule, no schema, no code change
- Related: `122_FULL_LENGTH_REAL_MEDIA_E2E_VALIDATION.md`,
  `126_LOCAL_ASR_PROVIDER_QUALITY_EVIDENCE.md`,
  `127_TRANSCRIPT_QUALITY_THRESHOLD_CALIBRATION.md` (**not** rewritten; its conclusions stand)

## 1. Summary

Two lectures recorded today were driven through the released production pipeline and added to the
calibration corpus. Both completed end to end with `healthy` validation and no workaround.

| | result |
|---|---|
| lectures processed | 2 of 2, complete |
| corpus after expansion | **3 lectures, 5.86 h, 760 decode windows, 5,487 segments** |
| provider evidence coverage | **100 %** on both (3,756 / 3,756 segments) |
| readable v2 blocking findings | **0** on both |
| repository validation | healthy, 16,147 objects, schema v53, 0 errors, 0 warnings |
| human-labelled positives | **0** — the queue is built, the listening has not happened |
| production changes | none |

Three findings are worth reading before the tables:

1. **The same hallucination template recurs across lectures.** `이곳은 …에서 가장 유명한 …입니다`
   appeared in the prior lecture's absence region and appears twice more in Lecture A. This is the
   first cross-lecture reproducible pattern in the corpus.
2. **`temperature > 0` now exists.** `127` recorded zero non-zero-temperature windows in a whole
   lecture; the new lectures carry 6 and 5. The signal `127` could not evaluate is now evaluable.
3. **There is no digital silence in this corpus.** Measured directly: a 168-second no-speech gap has
   mean volume −26.8 dB against −20.3 dB for speech, and `ffmpeg silencedetect` finds **zero**
   intervals at −35 dB across either lecture. The failure condition is *no speech in a noisy room*,
   not silence — which changes how candidates must be found.

## 2. Input media

| | Lecture A | Lecture B |
|---|---|---|
| filename | `MVI_0146.MP4` | `MVI_0147.MP4` |
| size | 29,380,920,963 B (27.4 GiB) | 31,115,678,160 B (29.0 GiB) |
| duration | 6,672.17 s (**1.85 h**) | 7,066.06 s (**1.96 h**) |
| container / video | mp4 · h264 1920×1080 @ 30000/1001 | identical |
| audio | aac 48 000 Hz stereo | identical |
| Source Media identity | `sha256:a898b7d3…60bf` | `sha256:19aa01b5…4723` |
| Transcript Source Intake | `transcript-source-intake:sha256:a898b7d3…` | `transcript-source-intake:sha256:19aa01b5…` |
| subject (from transcript) | Korean literature — narrative structure, 역순행적 구성, 허구성 | Korean grammar — 문법 단위, 품사, 구와 절, 조사/형용사/용언 |

Both files were processed in **one repository**, and their media, intake, provider-result, raw
transcript, candidate, selection and artifact identities are all distinct — the §11 identity
separation check passes.

### Instructor identity — not determined

The three corpus files share a camera naming series (`MVI_0144/0146/0147`) and identical codec,
resolution and frame rate, so they come from the same recording setup. **Whether they are the same
instructor cannot be determined from the media or the transcripts**, and it is not inferred here.

This matters: "≥ 2 instructors" is one of `127`'s stated readiness conditions, and recording it as
satisfied on the strength of a filename would be exactly the kind of unverified claim that record
exists to prevent. It is left open in §8 pending the Product Owner's answer.

## 3. Lecture A end-to-end

| # | stage | outcome |
|---|---|---|
| 1 | Media Import (SHA-256 over 27.4 GiB) | pass |
| 2 | Transcript Source Intake | pass |
| 3 | Local ASR (`local_asr_cli`, large-v3, ko) | **pass — 1,392 segments** |
| 4 | Current Raw Transcript Selection (sequence 0) | pass |
| 5 | Effective Transcript resolution | pass — `raw_transcript` |
| 6 | Consumption binding | pass |
| 7 | Passthrough Subtitle Candidate | pass — 1,392 cues |
| 8 | **Readable Candidate (params v2)** | pass — 1,707 cues, **0 blocking**, 72 warnings |
| 9 | Review Preparation → Accept → Final Selection | pass |
| 10 | SRT Artifact (`canonical_srt` v1) | pass — 1,707 cues |
| 11 | Materialization | pass — **139,241 B** |

ASR wall time **2,945 s (49 min)** for 1.85 h of audio; CPU time 3 h 13 m. Execution mode `fresh`,
checkpoint written under the approved scratch root and **removed after successful admission**.

```text
provider result reference: local-asr:v2:model=large-v3:lang=ko:cond_prev_text=false:media=sha256:a898b7d3…
raw transcript: raw-transcript:f4a28ca6…
real ASR execution occurred: yes      execution mode: fresh
```

### Transcript shape

| measure | value |
|---|---|
| segments | 1,392 |
| span | 0.0 – 6,692.2 s |
| average segment duration | 4.11 s |
| longest / shortest segment | 29.98 s / 0.240 s |
| `U+FFFD` count | **0** |
| exact adjacent repetition runs | 3 (longest ×6, `아`) |
| no-speech gaps ≥ 10 s | **12, totalling 725 s (10.9 % of the lecture)** |
| largest gaps | 168 s, 90 s, 86 s, 74.6 s, 60 s |

Lecture A carries far more no-speech time than the prior lecture (10.9 % vs 2.0 %), which is the
condition that generates hallucination. It is the most productive lecture in the corpus for this
purpose.

## 4. Lecture B end-to-end

| # | stage | outcome |
|---|---|---|
| 1–2 | Media Import + Intake | pass |
| 3 | Local ASR | **pass — 2,364 segments** |
| 4–6 | Selection → Effective (`raw_transcript`) → Consumption | pass |
| 7 | Passthrough Candidate | pass — 2,364 cues |
| 8 | **Readable Candidate (params v2)** | pass — 2,577 cues, **0 blocking**, 360 warnings |
| 9 | Review Preparation → Accept → Final Selection | pass |
| 10–11 | SRT Artifact → Materialization | pass — **198,394 B** |

ASR wall time **3,345 s (56 min)** for 1.96 h; CPU 3 h 40 m. Execution mode `fresh`, checkpoint
cleaned up.

```text
raw transcript: raw-transcript:aea1b22d…
real ASR execution occurred: yes      execution mode: fresh
```

### Transcript shape

| measure | value |
|---|---|
| segments | 2,364 |
| span | 0.0 – 7,065.8 s |
| average segment duration | 2.63 s |
| longest / shortest segment | 29.98 s / 0.120 s |
| `U+FFFD` count | **0** |
| exact adjacent repetition runs | 22 (longest ×4) |
| no-speech gaps ≥ 10 s | 8, totalling 229 s (3.2 %) |

B is much denser than A — 2,364 segments in 1.96 h against 1,392 in 1.85 h, average segment 2.63 s
against 4.11 s. Two lectures of near-identical length with a 1.7× difference in segment density is
useful corpus diversity in itself.

**No `U+FFFD` in either lecture.** `122` recorded replacement characters as remaining problem 3; they
did not recur here. That is one observation, not a resolution.

## 5. Provider evidence

Verified through the released `original_content` inspection path.

| check | Lecture A | Lecture B |
|---|---|---|
| evidence available | yes | yes |
| decode windows | 235 | 252 |
| segment coverage | **1,392 / 1,392** | **2,364 / 2,364** |
| evidence-uncovered segments | 0 | 0 |
| window ordering non-decreasing | yes | yes |
| window indices distinct / disjoint | yes | yes |

### Distributions (window level)

**Lecture A** (n = 235)

| signal | min | p01 | p05 | p25 | median | p75 | p95 | p99 | max |
|---|---|---|---|---|---|---|---|---|---|
| `avg_logprob` | −1.173 | −1.083 | −0.685 | −0.336 | −0.266 | −0.215 | −0.164 | −0.131 | −0.124 |
| `no_speech_prob` | 0.004 | 0.005 | 0.012 | 0.055 | 0.141 | 0.274 | 0.584 | 0.875 | 0.897 |
| `compression_ratio` | 0.571 | 0.727 | 1.109 | 1.356 | 1.472 | 1.545 | 1.665 | 1.940 | 2.213 |
| `temperature` | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 | 1.0 |

**Lecture B** (n = 252)

| signal | min | p01 | p05 | p25 | median | p75 | p95 | p99 | max |
|---|---|---|---|---|---|---|---|---|---|
| `avg_logprob` | −1.013 | −0.828 | −0.669 | −0.388 | −0.298 | −0.218 | −0.150 | −0.107 | −0.092 |
| `no_speech_prob` | 0.007 | 0.015 | 0.023 | 0.105 | 0.200 | 0.343 | 0.521 | 0.596 | 0.926 |
| `compression_ratio` | 0.609 | 0.813 | 1.230 | 1.513 | 1.633 | 1.736 | 1.900 | 2.048 | 2.155 |
| `temperature` | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.6 | 1.0 |

### `temperature` discrete frequency

| lecture | 0.0 | 0.2 | 0.6 | 0.8 | 1.0 | non-zero |
|---|---|---|---|---|---|---|
| A | 229 | 1 | 2 | — | 3 | **6 / 235 (2.6 %)** |
| B | 247 | 2 | 1 | 1 | 1 | **5 / 252 (2.0 %)** |
| prior (`127`) | 273 | — | — | — | — | 0 / 273 |

`127` could not evaluate `temperature` because a whole lecture produced none. It now has 11 events.

## 6. Label-free candidate queue

No threshold was applied and no Quality Warning was fired. The queue exists to bound how much audio a
person must listen to; every cut in it is a scratch evaluation query.

| type | Lecture A | Lecture B | basis |
|---|---|---|---|
| A — transcript island between long gaps | 7 | 2 | ≤ 4 segments isolated by ≥ 20 s no-speech gaps on both sides |
| B — exact adjacent repetition | 3 | 22 | any run ≥ 2, run length recorded, no cut chosen |
| C — evidence extremes | 36 | 35 | top 10 per signal, plus all `temperature > 0` |
| **priority total** | **46** | **59** | **105 items, ≈ 42 min of listening** |
| D — short fragments (appendix) | 80 | 175 | listed only, never labelled |

Each queue item carries lecture, source start/end, transcript text, ±2 segments of context, the full
decode-window evidence, the candidate reason, an `audio_review_range` with 8 s of padding on each
side, and a `label` field left `null` for the human pass. Vocabulary: `HALLUCINATION`,
`REAL_SPEECH`, `AMBIGUOUS`.

Type D is deliberately kept out of the priority queue and un-ranked. `응`, `네`, `저요` are ordinary
lecture speech, and putting 255 of them in front of a reviewer would train the reviewer to dismiss
the queue.

### Candidate type A could not be built as specified

The specification asks for *long silence where a transcript segment nonetheless exists*, reusing an
existing harness and adding no audio-analysis capability. The repository has no such harness, so
`ffmpeg silencedetect` was used as a **scratch evaluation tool only** — the same tool
`fixtures/PROVENANCE.md` already documents for slice extraction, writing to no repository and
producing no label.

It returned **zero** silence intervals ≥ 3 s at −35 dB on both lectures. Direct measurement explains
why:

| region (Lecture A) | mean volume | max volume |
|---|---|---|
| inside the 168 s no-speech gap (3060–3120 s) | **−26.8 dB** | −1.1 dB |
| ordinary speech (600–660 s) | −20.3 dB | −0.9 dB |

Only 6.5 dB separates them and the peaks are identical: these rooms carry continuous ambient noise
and contain no digital silence. Amplitude gating cannot supply this candidate type on this corpus.

Type A was therefore built from **transcript islands** — a short run of segments isolated by long
no-speech gaps on both sides — which is transcript-derived, needs no audio analysis, and matches the
shape of every confirmed hallucination so far. This substitution is recorded rather than silently
made, and it also refines a phrase in `127`/`PROVENANCE.md`: what was described there as "complete
silence" is **decoder silence — no segments emitted**, not an absence of audio.

### The highest-value items

Reported as evidence, **not as labels**. Nobody has listened to any of this.

Lecture A, all five windows at `avg_logprob ≤ −0.967`:

```text
6632.2-6634.2  logp -1.173  nsp 0.467  cr 0.72  T 1.0   글씨가 찍어져있네요
3727.8-3756.8  logp -1.085  nsp 0.546  cr 0.83  T 1.0   3시간 정도만 자면 기상세까지 안되는데
3026.8-3038.8  logp -1.083  nsp 0.335  cr 1.04  T 1.0   시험장에 오신 것을 환영합니다. /
                                                        오늘의 수업은 여기까지입니다. /
                                                        다음 영상에서 만나요.
3236.8-3266.8  logp -0.985  nsp 0.897  cr 2.21  T 0.0   제주도에서 가장 유명한 곳은 대한민국 ×9 입니다.
3587.8-3607.8  logp -0.971  nsp 0.874  cr 2.01  T 0.0   이곳은 대한민국에서 가장 유명한 도로로 유명한 도로로 …
```

Two observations about this set, both about text and evidence rather than truth:

- **The template recurs across lectures.** `127` recorded `이곳은 한국에서 가장 유명한 곳입니다` in the prior
  lecture's absence region. The last two rows are the same template in a different lecture. A textual
  pattern that reproduces across lectures is the single most valuable thing this expansion produced,
  and it is the first item the human pass should resolve.
- **The two morphologies separate cleanly here.** The three `T = 1.0` rows have *low* compression
  (0.72–1.04); the two repetition-shaped rows have *high* compression (2.01–2.21) with `T = 0.0`.
  `127` inferred this opposition from two events in one lecture; five events in a second lecture are
  consistent with it. `avg_logprob` is extreme for **both**.

Lecture B's two windows at the same cut are `우리는 기본적으로 생각하는 것들은 …` (logp −1.013, T 1.0) and
`너무 쉽지?` (logp −0.983, cr 0.61, T 0.0) — the second reads as ordinary lecture speech, so this cut
appears to produce a false positive in B. That too is for the human pass to settle.

## 7. Readability regression

| measure | Lecture A | Lecture B | expectation |
|---|---|---|---|
| parameter version | **v2** | **v2** | v2 |
| generator | `readable_cue_composition` v1 | same | — |
| source cues → readable cues | 1,392 → **1,707** | 2,364 → **2,577** | — |
| **blocking findings** | **0** | **0** | **0** |
| warnings | 72 | 360 | — |
| maximum lines per cue | 2 | 2 | ≤ 2 |
| maximum line characters | **24** | **24** | ≤ 24 |
| maximum cue characters | **43** | **43** | ≤ 44 |
| cues < 100 ms | **0** | **0** | 0 |
| cues > 7 s | 10 | 8 | warning only |
| overlapping cues | **0** | **0** | 0 |
| SRT | 139,241 B, UTF-8, LF | 198,394 B, UTF-8, LF | — |

Warning mix is dominated by `READABILITY_DURATION_BELOW_TARGET` (cue shorter than the 1.000 s target)
with a few `READABILITY_DURATION_ABOVE_MAXIMUM` and `READABILITY_READING_RATE_HIGH`. All are
non-blocking by contract.

### One measurement that looked like a defect and is not

A raw `len(line)` over the materialized SRT reports a maximum line of **26** characters, above the v2
limit of 24, while the validator reports **0** blocking findings. That apparent contradiction was
checked rather than assumed away.

The contract measures `display_length(line) = len(line.strip())`. faster-whisper prefixes every
segment's text with a space, `§14` A-11 requires that text be preserved **exactly**, and a leading
space carries no display width at the start of a line. Re-measuring with the contract's own function
gives a maximum line of exactly **24** and a maximum cue of **43** in both lectures, with zero lines
over 24 and zero cues over 44.

**No defect.** The validator and the artifact agree; the naive measurement was wrong.

## 8. Corpus inventory

| | prior (`127`) | after expansion |
|---|---|---|
| lectures | 1 | **3** |
| instructors | 1 | **undetermined** (see §2) |
| total audio | 2.04 h | **5.86 h** |
| decode windows | 273 | **760** |
| segments | 1,731 | **5,487** |
| no-speech gaps ≥ 10 s | 2 (144 s) | **22 (1,098 s)** |
| exact repetition runs | 8 | **33** |
| `temperature > 0` windows | 0 | **11** |
| **human-labelled positives** | 0 | **0** |
| **human-labelled negatives** | 0 | **0** |
| **ambiguous** | 0 | **0** |
| priority candidate queue | — | **105 items, ≈ 42 min** |

Against `127`'s stated readiness conditions:

| condition | target | status |
|---|---|---|
| lectures | ≥ 5 | 3 — **not met** |
| total audio | ≥ 5 h | **5.86 h — met** |
| instructors | ≥ 2 | **undetermined** |
| independent positive windows | ≥ 20 | **0 labelled** — candidates exist, listening has not happened |
| lecture-level holdout | ≥ 3 lectures | **now arithmetically possible** |
| both morphologies represented | yes | candidates for both present, unlabelled |

The corpus crossed the duration threshold and made lecture-level holdout possible for the first time.
It did not produce a single labelled positive, because labelling requires listening and no listening
has occurred.

## 9. Cross-lecture evidence comparison

| signal | statistic | MVI_0144 | A (0146) | B (0147) |
|---|---|---|---|---|
| `avg_logprob` | p05 / median / p95 | −0.544 / −0.295 / −0.188 | −0.685 / −0.266 / −0.164 | −0.669 / −0.298 / −0.150 |
| `no_speech_prob` | p05 / median / p95 | 0.024 / 0.169 / 0.550 | 0.012 / 0.141 / 0.584 | 0.023 / 0.200 / 0.521 |
| `compression_ratio` | p05 / median / p95 | 1.241 / **1.464** / 1.656 | 1.109 / **1.472** / 1.665 | 1.230 / **1.633** / 1.900 |

`avg_logprob` and `no_speech_prob` are stable across all three lectures. **`compression_ratio` is
not**: B's median (1.633) sits above A's and the prior lecture's p75-ish region, and B's p95 (1.900)
exceeds the prior lecture's maximum. Compression tracks something lecture-specific — plausibly
speaking density, given B's 2.63 s average segment against A's 4.11 s — and any absolute cut on it
will not port between lectures.

## 10. Calibration hypotheses — offline stress-test

Applied offline to window counts only. **Nothing fired, no threshold is contracted, and this is not a
recommendation.**

| candidate cut from `127` | MVI_0144 | A (0146) | B (0147) |
|---|---|---|---|
| `avg_logprob ≤ −0.716` | 3 w / 0.6 % | 9 w / 2.2 % | 9 w / 3.5 % |
| `avg_logprob ≤ −0.967` | 0 w / 0.0 % | **5 w / 0.6 %** | **2 w / 0.1 %** |
| `no_speech_prob ≥ 0.813` | 1 w / 0.1 % | 4 w / 0.4 % | 1 w / 0.0 % |
| `compression_ratio ≥ 1.480` | 127 w / 55.7 % | 107 w / 55.0 % | **203 w / 88.5 %** |
| `compression_ratio ≥ 2.368` | 0 w / 0.0 % | 0 w / 0.0 % | 0 w / 0.0 % |
| `temperature > 0` | 0 w / 0.0 % | 6 w / 2.0 % | 5 w / 2.0 % |

Read against `127`'s per-signal verdicts:

- **`avg_logprob` — still the most promising, and now it has something to find.** `127` noted the
  −0.967 cut fired zero times on a whole lecture; here it fires 5 and 2 times at 0.6 % and 0.1 %
  burden, and what it surfaces includes the recurring template. Burden stays low across all three
  lectures. Unchanged verdict, better evidence.
- **`compression_ratio` — confirmed unusable as an absolute cut.** 55.7 / 55.0 / **88.5 %**. `127`
  called the direction unstable across morphologies; this adds instability of the *distribution*
  across lectures. Any future use needs to be lecture-relative or morphology-specific.
- **`temperature` — no longer unevaluable, still not usable alone.** 2.0 % of windows in both new
  lectures. It misses the two repetition-shaped candidates entirely (both `T = 0.0`), so as a sole
  rule its recall would be 0 on exactly the morphology that recurs across lectures.
- **`no_speech_prob` — burden is tolerable, precision unknown.** 0.0–0.4 %. `127`'s one firing in the
  prior lecture was real speech (`감사합니다`). Whether A's four are better is a question for the
  human pass.

## 11. Repository validation

```text
schema version   : 53
objects checked  : 16147
warnings         : 0
errors           : 0
health           : healthy
```

Both lectures live in one repository with fully distinct identity chains. Checkpoints were written
under the approved scratch root during both runs and **removed after successful admission**; the
checkpoint root is empty. Working tree clean apart from the untracked media, which is not committed.

## 12. New findings

| # | finding | classification |
|---|---|---|
| 1 | No digital silence exists in this corpus (−26.8 dB vs −20.3 dB); amplitude gating cannot locate no-speech regions | **Evaluation constraint** — not a defect; it changes how candidates are found and refines the wording in `127`/`PROVENANCE.md` |
| 2 | The `이곳은 …에서 가장 유명한 …입니다` template recurs across two lectures | **Calibration evidence** — first cross-lecture reproducible pattern; highest-priority item for the human pass |
| 3 | `compression_ratio` distribution shifts materially between lectures (median 1.464 / 1.472 / 1.633) | **Calibration evidence** — an absolute cut on it will not port |
| 4 | Raw `len(line)` on the SRT suggests a 26-character line against a 24 limit | **Not a defect** — the contract measures `len(line.strip())` and `§14` A-11 preserves the provider's leading space; re-measured at exactly 24 |
| 5 | `U+FFFD` (remaining problem 3 of `122`) did not recur in either lecture | **Observation only** — not a resolution |

No Implementation Defect, Blueprint Gap, or Product Decision was found. Nothing was worked around,
and no run was made to succeed by hand.

## 13. Files changed

This evaluation record only. No production code, test, schema, Blueprint, PATCH, or prior report was
modified. `127`'s conclusions stand unaltered.

Media files are not committed. Evidence sets, candidate queues, SRTs and the scratch repository live
in the session scratchpad; the extraction and queue-building scripts are scratch-only and implement
no firing rule.

## 14. Result

Both lectures completed the released production path end to end with no workaround, `healthy`
validation, full provider evidence preservation, and zero readability blocking findings at parameter
version v2. The calibration corpus is now **3 lectures / 5.86 h / 760 windows / 5,487 segments**, with
a 105-item candidate queue ready for a human listening pass.

The readiness decision is unchanged, and deliberately so:

```text
MORE_DATA_REQUIRED
```

Two conditions still block a threshold PATCH, and neither is about volume of compute:

1. **Zero human-labelled positives.** The queue is built and takes about 42 minutes to listen to.
   Until someone does, every confusion matrix would rest on proxy labels — the limitation `127`
   already named.
2. **Instructor count undetermined**, so `127`'s "≥ 2 instructors" condition can be neither claimed
   nor dismissed.

What did change is that the evidence is now worth labelling: a hallucination template that reproduces
across lectures, both morphologies represented, `temperature` evaluable for the first time, and
`avg_logprob` holding a low warning burden across three lectures.

```text
Requires Architect Decision: No
Requires Blueprint Clarification: No
Requires Blueprint PATCH: No
```
