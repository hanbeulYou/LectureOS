# Full-Length Real Media End-to-End Validation

- Status: Implementation Record
- Blueprint Baseline: v1
- Validated on: 2026-08-04
- Schema: v53 (unchanged by this validation)
- Related: `PATCH-0039`, `095_EXTERNAL_ASR_BOUNDARY.md`, `096_LOCAL_ASR_ADAPTER.md`,
  `060_IMPLEMENTATION_STATUS.md`

## What this is

The first end-to-end validation of the complete released pipeline against **full-length real
classroom media**, from Media Import through Edit Export. It supersedes the M1 record's 96-second
scope (`060 §M1`) as the reference for what the pipeline does at production length.

It is a validation record, not a contract. It defines no product meaning, changes no Domain
contract, and introduces no policy. Where it records a defect, the resolving instrument is named.

No input media, transcript content, subtitle text, or classroom audio is stored in this repository.

## Input

| field | value |
|---|---|
| duration | 7355.845 s (2 h 02 m 36 s) |
| size | 32,391,572,455 bytes (30.2 GiB) |
| container | MP4, overall bitrate 35.2 Mbit/s |
| video | h264, 1920x1080, 30000/1001 fps |
| audio | aac, 48000 Hz, stereo |
| data stream | one unknown-codec data stream (camera metadata), ignored throughout |
| SourceMediaId | `sha256:a7aed0bc…9d2ae9` |
| subject matter | Korean literature lecture (이효석 「메밀꽃 필 무렵」, 고전시가, 이육사 「광야」, 사군자) |

Execution host: Apple M5 Pro, 15 cores, 48 GiB RAM, macOS 25.5.0, CPython 3.10.0.
Provider: `faster-whisper` 1.2.0 over `ctranslate2` 4.6.0, model `large-v3`, `language=ko`,
`device=cpu`, `compute_type=int8`.

## Stage results

| # | stage | outcome | wall time |
|---|---|---|---|
| 1 | Media Import (streaming SHA-256 over 30.2 GiB) | pass | 17.4 s (≈1.86 GiB/s) |
| 2 | Transcript Source Intake | pass | <1 s |
| 3 | Local ASR (`local_asr_cli`, large-v3) | **pass** — 2448 segments | 85–95 min |
| 4 | Current Raw Transcript Selection → readiness `ready` | pass | <1 s |
| 5 | Correction Candidate admission | pass | <1 s |
| 6 | Correction Candidate Human Decision (`accept`) | pass | <1 s |
| 7 | Corrected Revision generation | pass | <1 s |
| 8 | Current Corrected Revision Selection → effective `corrected` | pass | <1 s |
| 9 | Effective Transcript Consumption binding | pass | 0.17 s |
| 10 | Effective Subtitle Candidate generation (2564 cues) | pass | 0.20 s |
| 11 | Review Preparation → Human Decision `accept` → Final Selection | pass | <1 s |
| 12 | Effective SRT Artifact | pass | 0.30 s |
| 13 | Physical Materialization | pass — 189,388 bytes | 0.29 s |
| 14 | Delivery (exact-byte copy, verified) | pass — 189,388 bytes | <1 s |
| 15 | Publication authority (sequence 0) | pass | <1 s |
| 16 | Analysis Input Eligibility → Admission | pass | <1 s |
| 17 | Analysis Finding admission | pass | <1 s |
| 18 | Lecture Segmentation (3 segments) | pass | <1 s |
| 19 | Analysis Edit Candidate admission | pass | <1 s |
| 20 | Lecture Review `accept` (authority position seq 0) | pass | <1 s |
| 21 | Edit Export scope → assembly → serialization → materialization | pass — 923 bytes | <1 s |
| 22 | Repository Validation | **healthy** | 0.32 s |

Every stage after ASR completes in well under one second at 2564-cue scale. The pipeline's cost at
production length is **entirely** the ASR execution; no released contract shows scale sensitivity.

## Repository validation

Three independent repositories were built during validation and all validate clean:

| repository | purpose | objects | warnings | errors | health |
|---|---|---|---|---|---|
| `lectureos.sqlite3` | full E2E incl. correction, publication, edit export | 5162 | 0 | 0 | healthy |
| `verify.sqlite3` | un-normalized engine output, post-fix | 5143 | 0 | 0 | healthy |
| `adapter.sqlite3` | `local_asr_cli` re-run, post-fix, real engine execution | 4911 | 0 | 0 | healthy |

Schema v53 throughout. This validation required no schema change and no migration.

## PATCH-0039 — before and after

The first attempt did **not** complete. `local_asr_cli` transcribed the full media and then exited
`1` at the `040 §14` admission boundary:

```text
error: local ASR engine produced inadmissible output:
       segments must be ordered by start and must not overlap
```

Three adjacent boundaries were responsible, each an `end` and the following `start` denoting one
instant but differing in the last representable bits of float64. `§14` A-10 stated the rule as an
exact inequality over submitted values and `§15` L-6 forbids the adapter from adjusting the timing
it submits, so no implementation-level fix existed. `PATCH-0039` amended A-10 to compare instants
within a `1e-6 s` representation tolerance; see `060` and `095` for the resolved contract.

**The defect recurs on every run, at different places.** Two independent transcriptions of the same
media produced disjoint offending boundaries with different magnitudes:

| run | offending boundaries | deltas |
|---|---|---|
| 1 (2564 segments) | #1082, #1221, #1384 | `-4.547e-13` (all three) |
| 2 (2448 segments) | #133, #778, #1144 | `-1.137e-13`, `-4.547e-13`, `-9.095e-13` |

94 % of run 2's adjacent boundaries (2294 of 2447) sit within `1e-6 s` of touching. No per-file
workaround was available; the contract was the only place it could be resolved.

## Proof the automatic path completes without a workaround

The pre-fix run was continued by hand: the captured engine output was minimally normalized (three
values, `4.5e-13 s` each) and submitted through `transcript_result_admit_cli`. **That path is not
what this record claims.** After `PATCH-0039` the released adapter was re-run from an empty
repository with no normalization, no hand-editing, and no alternate entry point:

```bash
PYTHONPATH=src python3 -m lectureos.media_import_cli MVI_0144.MP4 --database adapter.sqlite3
PYTHONPATH=src python3 -m lectureos.transcript_intake_cli --media sha256:a7aed0bc…9d2ae9 \
    --database adapter.sqlite3
PYTHONPATH=src python3 -m lectureos.local_asr_cli \
    --intake transcript-source-intake:sha256:a7aed0bc…9d2ae9 \
    --database adapter.sqlite3 --model large-v3 --language ko
```

```text
created provider transcript admission provider-transcript-admission:8aab6b1d… for intake …
canonical raw transcript: raw-transcript:8aab6b1d…
provider/model: faster-whisper/large-v3
segments: 2448
real ASR execution occurred: yes
EXIT=0
```

`real ASR execution occurred: yes` distinguishes this from `§15` L-8 reuse: the engine ran. The
stored segments were then confirmed to contain three boundaries the pre-`PATCH-0039` rule would have
rejected, and the repository was driven through selection, consumption, subtitle generation, review,
Final Selection, SRT artifact and materialization (185,640 bytes, 2448 cues) with validation
`healthy` over 4911 objects.

The materialized SRT is the observable proof the tolerance changes nothing: all three offending
boundaries render as **identical** millisecond timestamps, each appearing once as a cue's end and
once as the next cue's start.

## Artifacts produced

| artifact | size | shape |
|---|---|---|
| SRT (corrected transcript, published) | 189,388 B | 2564 cues, `00:00:00,000` → `02:02:34,540` |
| SRT (adapter re-run) | 185,640 B | 2448 cues |
| Edit Export JSON v1 | 923 B | 1 approved edit |

The SRT decodes as strict UTF-8, holds contiguous cue numbers 1..N, uses LF only, ends with a
trailing LF, and carries no CR — the released `canonical_srt` v1 form.

Artifacts live in the session scratchpad. Nothing produced from this media is committed.

## Remaining problems

Three defects observed during validation are **not** resolved by `PATCH-0039`, which records all
three as explicit non-goals. Severity is stated against current released behaviour.

### 1 — Complete transcription loss on rejection

- **Severity: High.** Operational, not correctness.
- `§15` L-10 requires the adapter to write nothing before a valid result is admitted, so any
  post-execution rejection discards the entire run. Observed twice: 95 minutes and 85.5 minutes of
  compute lost, with no recoverable material in the repository.
- Current impact: with `PATCH-0039` applied, the specific trigger is gone. The structure is not —
  any future inadmissible-output condition costs the full transcription, and cost scales with media
  length.
- Resolving it touches L-10's failure-atomicity guarantee and needs its own gate evaluation.

### 2 — Hallucination and repetition on silent / non-lecture regions

- **Severity: High.** Correctness of delivered output.
- `infrastructure/faster_whisper_engine.py:73` calls `transcribe(path, language=...)` and leaves
  every other parameter at library default, so `vad_filter` is `False` and
  `condition_on_previous_text` is `True`.
- Observed across a 195-second instructor-absent region (source 2717.2–2912.8 s): foreign-language
  fragments (`urday`, `it`, `other`, `a`, `o`), single-character segments, and a four-fold
  repetition of `고기와 함께 먹는 김치찌개`. All of it reached the published SRT.
- The region was recorded through the released pipeline as an Analysis Finding and an approved
  `non_lecture_region` Edit Candidate, so the contracts describe it correctly — but the subtitle
  delivered to a viewer contains fabricated text.
- A 4-way diagnostic was run for this record; see below. It is evidence only and decides nothing.

### 3 — `U+FFFD` replacement characters in engine output

- **Severity: Low.** Cosmetic; no contract violated.
- Four `U+FFFD` occurrences appear in engine output (Whisper BPE splitting a multi-byte character at
  a segment boundary) and reach the SRT verbatim — e.g. cue 2563 `' 어�'`.
- The pipeline behaved correctly: `§14` A-11 requires text to be preserved exactly, and it was. The
  SRT is still valid UTF-8. There is no sanitization point anywhere, and introducing one would
  contradict A-11.

## Diagnostic evidence recorded for problem 2

A 4-way comparison was run on a preserved 305-second slice of the instructor-absence region and a
55-second slice of the classical-terminology region, holding model, language, device, compute type,
beam size, temperature schedule and thresholds fixed and varying only `vad_filter` and
`condition_on_previous_text`. Raw runs, the extraction provenance, and the analysis harness are
retained in the session scratchpad; no fixture is registered as Source Media or committed.

Findings recorded without recommendation:

- `vad_filter=True` removed **all** hallucinated segments from the silent region, but **dropped real
  instructor speech** at the speech/silence boundary (`나 화장실 좀 갔다 올게` lost) and emitted
  segments spanning removed silence — a single cue of **212 seconds** for a two-second utterance.
- `condition_on_previous_text=False` removed the repetition loop while preserving that same speech
  and keeping every segment under 7.4 s, at roughly 1.3× the baseline's execution time.
- The **baseline is not reproducible**: two runs over byte-identical audio in one process produced
  23 and 60 segments. `§15` L-8's reuse-before-rerun rule already anticipates ASR non-determinism,
  so no released contract is violated, but it means no configuration can be evaluated from a single
  run.
- Both `condition_on_previous_text=False` variants recovered `사군자` and `메란 국죽`, which the
  baseline did not — the same terminology class the M1 record flagged and the correction candidate
  targeted.

Because the two parameters trade a real-speech loss against a hallucination reduction, this is not a
settled configuration change and no default was altered.

## Out of scope for this milestone

This validation deliberately did not: change any production ASR default; add heuristic hallucination
filtering; sanitize `U+FFFD`; introduce intermediate checkpointing; alter Raw Transcript content,
schema, migration, or provider configuration identity; modify the canonical E2E repository after the
fact; or re-transcribe the full media under alternate settings. It authored no PATCH beyond the
already-released `PATCH-0039` and decided no product policy.
