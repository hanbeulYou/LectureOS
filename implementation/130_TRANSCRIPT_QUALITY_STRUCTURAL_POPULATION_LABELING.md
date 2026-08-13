# Transcript Quality — Signal-Independent Structural Population Labeling Package (Evaluation)

- Status: Evaluation Record
- Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` §15 QD-12/QD-14 (threshold Deferred) / `PATCH-0045`
- Production impact: **none** — no PATCH, no threshold, no firing rule, no schema, no code change
- Related: `127`, `128`, `129_TRANSCRIPT_QUALITY_HUMAN_LABELING.md` (**none rewritten**)

## 1. Repository investigation

`129` §8 names the stratum and its parameters — *gap ≥ 10 s, within 30 s either side* — and the
evaluation harness that produced its `221 / 4.0 % / 8 of 9` row is preserved in the session
scratchpad. The predicate was recovered from it and reimplemented cleanly; nothing was invented.

Reused rather than rebuilt: the evidence extraction path (released `original_content` inspection,
read-only), the clip extraction method validated in `129` (fast seek, proven sample-aligned against
accurate seek), the blind/analysis manifest split, and the local labeling page.

## 2. Structural population definition

```text
gap        a no-speech interval between consecutive transcript segments, >= 10.0 s
reach      30.0 s on each side of a gap
included   a segment whose [start, end) span overlaps (gap_start - reach, gap_end + reach)
           for ANY gap in the same lecture
excluded   every other segment
identity   (lecture, segment_ordinal) — the canonical Raw Transcript segment position
dedup      identity is a set; a segment reached by several gaps is included once
adjacency  membership is by span overlap, evaluated per gap, with strict inequality on both sides
context    ±2 transcript segments shown to the labeler; not part of the membership test
```

The strict inequality matters and is preserved exactly as `129` used it — see §6.

## 3. Signal-independence proof

Three independent guarantees, strongest first.

**Structural erasure.** `structural_view()` projects each segment onto `(ordinal, start, end, text)`
before selection runs. The selector is handed data that physically does not contain provider
evidence, so no coding mistake can leak a signal into membership.

**AST audit.** An evaluation-only checker walks the selection module's syntax tree and rejects any
reference to `avg_logprob`, `no_speech_prob`, `compression_ratio`, `temperature`, `human_label`,
`selection_category`, `candidate_reason`, `confidence`, `uncertainty`, any known-positive string
(`마포구청`, `가장 유명한`, `감사합니다`), any label vocabulary term, and any import at all:

```text
forbidden references : NONE
dict keys read       : ['end', 'ordinal', 'start']
outside allowed set  : NONE
RESULT: SIGNAL-INDEPENDENT
```

Note the selector reads only `end`, `ordinal` and `start` — it does not even consult `text`.

**Perturbation test.** Every provider signal in a lecture was overwritten with extreme values
(`no_speech_prob = 0.99`, `avg_logprob = -9.9`, `compression_ratio = 9.9`, `temperature = 1.0`) and
selection re-run. **The population is byte-identical.** A rule that cannot be moved by setting every
signal to its most suspicious value cannot have been guided by one.

No known human label, prior candidate category, or confirmed hallucination string participates.
Known positives are in the population **because they sit near no-speech gaps**, not because they are
known.

## 4. Population result

| lecture | instructor | segments | gaps ≥ 10 s | selected | % of lecture | speech seconds |
|---|---|---|---|---|---|---|
| MVI_0144 | 원장님 | 1,731 | 3 | **36** | 2.1 % | 114 |
| MVI_0146 | 원장님 | 1,392 | 12 | **86** | 6.2 % | 337 |
| MVI_0147 | 장혜정 선생님 | 2,364 | 8 | **99** | 4.2 % | 408 |
| **TOTAL** | | **5,487** | **23** | **221** | **4.0 %** | **859** |

By instructor: 원장님 122, 장혜정 선생님 99.

`129`'s `221 / 4.0 %` is reproduced exactly. MVI_0146 contributes disproportionately because it holds
725 s of no-speech time (10.9 % of that lecture) against MVI_0144's 144 s.

Population frozen before any label was joined; fingerprint `5b2115c32a44144c`.

## 5. Known positive coverage

Joined **after** the freeze, in that order.

```text
human-confirmed hallucinations : 9
inside the population          : 8
outside                        : 1
```

`129`'s `8 / 9` is reproduced. Inside: the three `마포구청 인터넷 방송국 홈페이지` occurrences across
two lectures, `제주도에서 가장 유명한 곳은 대한민국 ×9`, `한국국토정보공사`, `고춧가루`,
`글씨가 찍어져있네요`, `자세히 알아보세요.`

Of the 32 previously labelled items, **18** fall inside the population: 8 `HALLUCINATION`,
5 `REAL_SPEECH`, 4 `ASR_ERROR`, 1 `AMBIGUOUS`.

## 6. The excluded positive

`MVI_0144 @ 7353.9 — 감사합니다.`, the lecture's final utterance.

```text
nearest gap  : 7307.8 - 7323.9  (16.1 s)
gap end      : 7323.9
reach        : 30.0 s  ->  membership window ends at 7353.9
segment start: 7353.9
predicate    : start < gap_end + reach  ->  7353.9 < 7353.9  ->  False
```

It misses by **exactly zero seconds**, excluded by the strict inequality at the reach boundary. Its
immediate predecessor — the `마포구청` hallucination at 7323.9–7353.8 — *is* included.

**The rule is not changed to capture it.** Widening the reach to admit a known positive is precisely
the selection bias this population exists to avoid, and `129` §12 forbids it. Recorded instead as
recall-ceiling evidence: a structural frame keyed on gap proximity will miss hallucinations that
occur far enough from any gap, and at least one real case sits exactly on that boundary.

Practical note: the labeler will *hear* this utterance, because it falls inside the padding of a
neighbouring clip. It is not a labeling candidate and carries no row.

## 7. Blind package

```text
evaluation/transcript-quality-structural-labeling/
  README.md
  manifest_blind.csv       221 rows
  manifest_analysis.csv    221 rows
  labeling.html            local page, 26 clips with per-line label buttons
  clips/C001.wav … C026.wav
```

Located beside the two earlier packages under `evaluation/`, excluded from Git via
`.git/info/exclude` on the `e2e-results/` precedent. Nothing is committed: the clips are classroom
audio containing student voices and the manifests carry transcript text.

**Candidate identity and audio clip are separate**, per the prompt's §21. The 221 candidates each
keep their own identity and their own label; adjacent candidates share one coalesced clip so the
same audio is not heard repeatedly. Each row carries `clip_file`, `clip_position` (`3/9`) and
`offset_in_clip`, and the page seeks to that offset on click.

Blind manifest columns: `candidate_id`, `clip_file`, `clip_position`, `offset_in_clip`, `lecture`,
`instructor`, `audio_start`, `audio_end`, `transcript_text`, `previous_context`, `next_context`,
`human_label`, `human_note`.

Withheld to the analysis manifest: all four provider signals, `structural_inclusion_reason`,
`window_index`/`window_start`/`window_end`/`window_segment_count`, `segment_ordinal`,
`repetition_run_length`, **`prior_human_label`** and `prior_labeling_provenance`.

**Ordering.** Clips are ordered by a stable SHA-256 of `(lecture, first segment ordinal)` —
independent of lecture, instructor, structural category, signal, known label and timestamp, and
identical on re-run. Within a clip, candidates stay in time order, which audio forces; that residual
ordering carries no selection information.

## 8. Workload

| | |
|---|---|
| candidates | **221** |
| clips | **26** |
| unique audio | **23.9 min** |
| clip length | min 18 s · median 48 s · max 102 s |
| already labelled | 18 |
| not yet labelled | 203 |

`129` estimated ~75 minutes. The package needs **24**, and the difference is not a scope reduction:
`129` assumed 221 independent clips at ~20 s each, but the segments cluster around 23 gaps, so
coalescing removes the redundant re-listening. Coverage is identical — every one of the 221
candidates is heard.

Summing per-candidate clips without coalescing would be 73.2 minutes, which matches `129`'s estimate
and confirms the difference is packaging rather than population.

## 9. Existing-label reuse recommendation

**Recommendation: relabel all 221.** The 18 previously-labelled items are not marked in the blind
package.

Reasoning. Reuse would save roughly 2 minutes of the 24 — the 18 items sit inside clips that must be
played anyway for their neighbours, so the saving is nearly zero. Against that, relabelling buys a
genuine test-retest measurement: whether the same listener reproduces the same judgment when the
earlier answer is not visible. Given that this investigation has twice been misled by a
plausible-looking result, an independent reproduction of 18 judgments is worth two minutes.

Marking them in the blind manifest was rejected outright: "you called this one hallucination last
time" is exactly the kind of prior that the signal-independent design exists to exclude.

The README offers the alternative — leave those rows blank and they will be filled from the earlier
labels. Either way the analysis distinguishes newly-heard from reused judgments, since
`prior_labeling_provenance` records round and candidate id for all 18.

## 10. Validation

| check | result |
|---|---|
| structural selection reproducible (same input → same output) | PASS |
| AST audit: no provider signal, label, or known-positive reference | PASS |
| selection invariant under extreme signal perturbation | PASS |
| 221 candidates, unique `(lecture, segment_ordinal)` | PASS |
| three lecture identities distinct, none mixed | PASS |
| instructor mapping correct | PASS |
| blind ↔ analysis `candidate_id` exact match, unique | PASS |
| blind labels empty | PASS |
| signals / inclusion reason / prior labels hidden from blind | PASS |
| prior label provenance preserved in analysis (18 rows) | PASS |
| transcript text identical across manifests | PASS |
| 26 clips, missing 0, orphan 0 | PASS |
| clip duration == manifest | PASS |
| every candidate's existing audio contained in its clip | PASS |
| `offset_in_clip` accurate | PASS |
| clip order not grouped by lecture, not chronological | PASS |
| known labels joined only after population freeze | PASS |
| canonical DB unchanged, read-only access | PASS |
| schema v53, `src/` `tests/` `docs/` `patches/` unchanged | PASS |

### One observation from validation

`C022-01` (`MVI_0146 @ 6662.2`, text `다음 영상에서 만나요.`) has a transcript end of 6692.18 s while
the media is 6672.166 s long — the segment extends **20 seconds past the end of the media**. Its clip
contains all audio that exists for it.

This is not a contract violation. `§14` A-14 states admission "media 파일을 읽지 않는다", so the
boundary has no media duration to check against, and A-10 constrains only ordering and positivity.
It is recorded because it affects how a labeler should read that row, and because a future
duration-aware validation would have to be contracted before it could exist.

## 11. Repository impact

```text
Production code changed: No
Schema changed:          No
Blueprint changed:       No
PATCH created:           No
Canonical records changed: No
```

Evaluation-only changes: the labeling package under `evaluation/` (git-excluded), and scratch-only
harnesses in the session scratchpad — `structural_population.py` (selection), `audit.py` (AST check),
`build.py` (package build). None is importable from `src/`, and none implements a firing rule.

Canonical repositories were opened read-only (`file:…?mode=ro`) and are unchanged.

## 12. Threshold readiness

```text
THRESHOLD READINESS: PENDING STRUCTURAL POPULATION HUMAN LABELS
```

No threshold was selected, no cut evaluated, no rule ranked. Signal distributions were not computed
over the population, deliberately: with 203 rows unlabelled, any distribution statement would invite
exactly the premature conclusion that `129` documented twice.

## 13. Next step

After the 221 rows are labelled:

```text
structural-population human labels
+ provider evidence (joined by candidate_id)
↓ unbiased signal evaluation          ← first measurement on a sample no signal helped select
↓ per-signal confusion matrices
↓ cross-lecture / cross-instructor validation
↓ hallucination subtype analysis      ← template vs isolated vs repetition morphology
↓ combined-rule evaluation
↓ threshold readiness decision
```

The recall denominator is honest for the first time: whatever the labels say, the sample was fixed
before any signal was consulted, and provably so.

Two limits will survive this round regardless of outcome. The corpus is 3 lectures against `127`'s
stated ≥ 5, and the structural frame's own recall ceiling is now demonstrated — one confirmed
hallucination sits outside it by zero seconds.

## 14. Result

```text
Human labels assigned by agent: 0
Threshold selected: No
Diagnostic firing rule activated: No
PATCH created: No
Blueprint changed: No

Requires Architect Decision: No
Requires Blueprint Clarification: No
Requires Blueprint PATCH: No
```
