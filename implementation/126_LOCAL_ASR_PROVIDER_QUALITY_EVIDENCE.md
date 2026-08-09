# Local ASR Provider Quality Evidence and Transcript Quality Diagnostic Foundation

- Status: Implementation Reference
- Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` §14 A-4/A-8 notes, §15 QD-1…QD-20 / `PATCH-0045`
- Schema: unchanged (**v53**; no migration, no table, no column, no identity kind)
- Related: `070_DIAGNOSTIC_PERSISTENCE_ASSESSMENT.md`, `122_FULL_LENGTH_REAL_MEDIA_E2E_VALIDATION.md`,
  `123_LOCAL_ASR_PROVIDER_CONFIGURATION.md`, `125_LOCAL_ASR_CHECKPOINT_AND_RESUME.md`

## What it is

Two things that must never be confused, and this milestone's main job is keeping them apart:

| | Provider Evidence | Derived Quality Diagnostic |
|---|---|---|
| what it is | values the provider reported during one execution | an interpretation of those values |
| recomputable? | **no** — obtainable only while the engine runs | yes, from immutable inputs |
| persisted? | **yes**, in `original_content` (A-4, QD-6) | **never** (QD-10) |
| in the fingerprint? | **no** (QD-8) | not applicable |

`PATCH-0040` P-9 recorded that hallucination is reduced, not contracted away. This milestone does not
remove it. It makes it **findable**: the evidence stops being discarded, and a versioned computation
can read it.

## The responsibility that was already released but unmet

`§4.2` has always listed "confidence 또는 Uncertainty" among the ASR stage's **Produces**. The first
`§15` slice converted only `start`, `end` and `text` into `LocalAsrSegment`, so the values were gone
*before* the `§14` boundary. A-4 was never violated — nothing *submitted* was dropped — but `§4.2`'s
obligation was unmet from the first slice until now.

## Why no schema change was needed

`original_content` is an existing column holding a canonical serialization of the submitted provider
evidence. Changing *what is serialized into it* changes no relation, column, constraint, or
migration. `docs/030_DATA_MODEL.md` is untouched and `SQLITE_SCHEMA_VERSION` stays 53 (QD-20).

## The fingerprint split — the defect this milestone had to avoid

Before this change:

```python
content_fingerprint = _sha256(_admission_payload(intake_identity, document))   # line 391
original_content    =         _admission_payload(intake_identity, document)   # line 429
```

**One helper, two purposes.** That coupling is not a contract — A-4 describes what `original_content`
preserves, A-8 describes what the fingerprint covers, and no released sentence requires the strings to
be equal. But while they shared a function, enriching the preserved evidence would have:

1. changed `content_fingerprint` for every result carrying evidence;
2. made the same anchor with richer evidence look like an **A-9 conflict**, rejected without mutation;
3. left already-admitted lectures permanently unable to gain evidence, because `§15` L-8 reuse returns
   the existing record before the engine ever runs.

They are now two functions:

| function | purpose |
|---|---|
| `_logical_admission_content` | the **A-8 fingerprint basis** — intake, provider, model, language, provider-result reference, and each segment's timing and exact text. Nothing else, ever. |
| `_original_provider_content` | the **A-4 preserved evidence** — the logical content plus whatever decode evidence the provider returned. |

The justification is A-8's own criterion. It identifies "동일한 논리적 결과"; two executions whose text
and timing agree but whose decode statistics differ **are** the same logical result, because the
statistics describe how the result was produced, not what it is. Excluding them serves A-8 rather than
weakening it.

Consequences, all asserted by tests: released fingerprints are byte-identical, `provider_result_ref`
stays **v2** (no `local-asr:v3`), Raw Transcript and Provider Result identities are unchanged, an
evidence-only difference resolves to the existing record instead of conflicting, and nothing is
back-filled.

## Evidence granularity — why it is not a segment confidence

Measured on the preserved fixtures, 32 segments carried only **6** distinct value sets, with up to 8
consecutive segments sharing one. Two real utterances and one fabrication in the same window had
identical values.

So a decode value is **not** a property of a segment, and QD-7 forbids storing it as one. Three
concrete refusals in the code:

- `transcript_segments.confidence` / `uncertainty` are not written — they stay `None`, asserted.
- `LocalAsrSegment` gained `decode_evidence`, not `confidence`. The provider's own field names
  (`avg_logprob`, `no_speech_prob`, `compression_ratio`, `temperature`) survive unrenamed: an
  `avg_logprob` is a mean token log-probability for a window, and calling it a confidence would assert
  a semantic the provider never stated.
- The preserved shape is **window-first**: the value lives on the window and the covered segment
  ordinals are listed, so the sharing is structural rather than something a reader must infer.

### Window identity

`seek` is the anchor. On the fixtures its distinct values partitioned the segments into exactly that
many groups, **no group ever carried two different value sets**, and the sequence was non-decreasing
with no window revisited.

Grouping is nevertheless by **run of adjacent segments**, not by `seek` value. A resumed execution
decodes from an explicit offset, so its anchors restart at zero and can repeat one the pre-resume half
already used; keying on the value would silently merge two genuinely different windows. Runs cannot,
and a repeated anchor after a resume simply becomes a second window entry — asserted by a resume test.

## Checkpoint compatibility

A `PATCH-0044` checkpoint stored only `start`/`end`/`text`. Resuming from one would have admitted a
result whose pre-resume half was silently evidence-free — evidence loss disguised as success.

`CHECKPOINT_FORMAT_VERSION` is therefore **1 → 2**, and `CheckpointSegment` carries `window_ref` and
`values`. CP-19 already contracts the outcome for a v1 checkpoint on disk: unknown format version →
discarded whole → fresh execution, disclosed through the released `checkpoint_discard_reason` output.
No repository state, no product identity, and no `provider_result_ref` is involved — a checkpoint
carries no Product identity (CP-2), so a scratch-format bump is categorically not a reference bump.

## The diagnostic, and why it fires nothing

`TranscriptQualityDiagnosticService` is read-only by construction: it holds queries and no persistence
port, so there is no code path through which a diagnostic could be stored (QD-10). It declares its
algorithm kind, algorithm version, and provider parameter version, and the same inputs under the same
versions converge on the same result (QD-11).

**No reason fires.** That is the contract, not an omission:

| reason | why it cannot be decided |
|---|---|
| `PROVIDER_LOW_CONFIDENCE` | threshold policy deferred (QD-14) |
| `PROVIDER_HIGH_NO_SPEECH` | threshold policy deferred |
| `PROVIDER_HIGH_COMPRESSION` | threshold policy deferred |
| `PROVIDER_DECODE_FALLBACK` | threshold policy deferred — including `temperature > 0`, which separated perfectly on one cluster and cannot be generalized from it |
| `REPEATED_TEXT` | **rule** not contracted: repeat count, exact-match, adjacency, and whitespace/punctuation handling are all undecided, and each answer changes which segments are flagged |

`REPEATED_TEXT` deserves the emphasis: it is the one reason needing no threshold, and it still cannot
fire. Vocabulary membership is not a firing rule. Implementing one here would have made a product
policy decision in code — exactly what `PATCH-0045` deferred.

### An empty result is not a clean result

Zero findings today means *nothing was decided*. The result carries `undetermined` — every reason with
its cause — and `reports_clean` returns `False` while any reason is undecided, so callers cannot use
`not findings` as a verdict. `completeness` is `UNAVAILABLE` in this generation for both a legacy
evidence-free record and an evidence-carrying one; the **cause** distinguishes them:

```text
evidence unavailable  → nothing can be read at all
threshold deferred    → the evidence is there, the cut is not contracted
```

`COMPLETE` and `PARTIAL` exist but are unreachable while every reason is deferred. They are the
completeness vocabulary for a later threshold PATCH, deliberately not a lifecycle attached to any
record.

## Human correction boundary

`correction_target_for` resolves a finding's segment ordinal to the canonical `TranscriptSegmentId`
that `§17` Correction Candidate admission **already** accepts. That is the entire connection. It
proposes no replacement text, creates no candidate, stores nothing, and makes no decision.

The released path is unchanged:

```text
Raw Transcript → Quality Diagnostic → 사람의 확인
              → §17 Correction Candidate admission → §18 Human Decision → §19 Corrected Revision
```

False positives are acceptable here **precisely because** QD-16 forbids automatic action. That
acceptability is conditional on the prohibition and disappears with it.

## Downstream

No gate is introduced anywhere. Admission, Raw Transcript creation, Current Raw Transcript Selection,
subtitle generation, and publication are all unaffected — asserted, including a source-level check
that neither the admission boundary nor either selection module so much as imports the diagnostic
module. Repository validation neither knows nor reports quality warnings.

## Real fixture validation

One run of the **released** local ASR path (`local_asr_cli`, faster-whisper 1.2.0, `large-v3`,
`condition_on_previous_text=False`, no VAD) over the preserved 305-second diagnostic fixture
`slice-A-absence.wav`, to confirm the production runner preserves real provider metadata:

```text
segments                        28
decode evidence windows          5
segments covered by evidence    28  (full coverage)
evidence kind                   faster-whisper/decode-window
```

| window | anchor | segments | span (s) | avg_logprob | no_speech_prob | compression_ratio | temperature |
|---|---|---|---|---|---|---|---|
| 0 | `seek=0` | 6 | 0.00–28.80 | -0.281 | 0.033 | 1.46 | 0.0 |
| 1 | `seek=2880` | 3 | 28.80–43.80 | -0.447 | 0.293 | 1.01 | 0.0 |
| 2 | `seek=23880` | 11 | 238.80–267.80 | -0.477 | **0.529** | 1.41 | **0.2** |
| 3 | `seek=26780` | 7 | 267.80–295.80 | -0.296 | 0.446 | 1.44 | 0.0 |
| 4 | `seek=29580` | 1 | 295.80–303.24 | -0.534 | 0.299 | 0.86 | 0.0 |

**Sharing is real and visible:** 28 segments over 5 windows — 23 more covered segments than windows.
Window 2 alone covers 11 segments that all carry the identical four values. This is exactly the
situation QD-7 exists for, and it is why no value here is written to
`transcript_segments.confidence`.

**Fingerprint proof on a real record.** The stored `content_fingerprint` equals the SHA-256 of the
logical content alone and **not** the SHA-256 of `original_content`:

```text
stored content_fingerprint       ee79b675f3b9dc6aafae72d987e7f8bf9f04e1058ced879746073746b8f3f892
sha256(logical content)          ee79b675f3b9dc6aafae72d987e7f8bf9f04e1058ced879746073746b8f3f892   ==
sha256(full original_content)    738b4bfda6677d110b6d1f2d8d1efba174e3939d0c20e803e06b546873ea7af2   !=
```

The evidence adds 1,205 bytes to `original_content` that the fingerprint never sees.

**Derived diagnostic on this result:** algorithm `local-asr-transcript-quality` v1, provider parameter
version `unavailable (threshold policy deferred)`, evidence available, completeness `unavailable`,
**0 findings, 5 undetermined reasons**, and the explicit line *"this result does NOT assert the
transcript is clean"*.

### What this run did **not** establish

This run's segmentation differs from the earlier capture of the same fixture with the same model: the
hallucination cluster previously observed at 178.8–196.8 s (`이곳은 한국의 한 정상의 장소입니다.` ×3,
`no_speech_prob = 0.813`, `avg_logprob = -0.967`, `compression_ratio = 2.37`, `temperature = 0.4`)
**did not reappear** — this run skipped 43.8–238.8 s entirely and produced 28 segments where the
earlier one produced 32.

Two consequences, both stated deliberately:

1. **No hallucination determination is claimed here.** Window 2 carries this run's highest
   `no_speech_prob` and the only non-zero `temperature`, and it covers a region containing a repeated
   `배고파`. That is an observation about evidence, not a verdict about the text. Nothing in this
   milestone decides whether any segment is hallucinated.
2. **It is direct support for QD-14.** Same media, same model, same approved configuration, different
   segmentation and different decode statistics. A threshold fitted to either run would be fitted to
   one sample of a non-deterministic process. Deferring the numbers to a later empirical PATCH with a
   broader corpus is the correct call, and this run is evidence for it rather than against it.

## Consistency with `070`

`070`'s reopening condition is met and its outcome splits, exactly as its `PATCH-0045` reassessment
note records: **provider evidence persistence** is justified (not recomputable, and A-4 already
assigns it a home), while **canonical derived Diagnostic persistence** remains deferred (recomputable,
stale-risk, no consumer needing a row). This milestone adds no table, no column, no
`SQLiteDiagnosticRepository`, and no Diagnostic transaction port. `070`'s conclusion is not revisited.

## What this milestone deliberately did not do

No numeric threshold, no hallucination score, no VAD, no audio analysis, no automatic correction or
deletion, no publication or subtitle gating, no schema migration, no canonical Diagnostic persistence,
no `provider_result_ref` version bump, no backfill, and no UI.
