# Transcript Timing Quality Diagnostic

- Status: Implementation Reference
- Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` §15 TD-1…TD-20 / `PATCH-0046`
- Schema: unchanged (**v53**; no migration, no table, no column, no identity kind)
- Related: `126_LOCAL_ASR_PROVIDER_QUALITY_EVIDENCE.md`, `131`, `132`, `133`,
  `134_TIMING_PREDICATE_FULL_CORPUS_SPECIFICITY.md`

## What it is

A derived, read-time observation that a transcript segment begins at its provider's decode-window
anchor **and** that the anchor opened after the previous admitted segment ended. It says a person
might usefully listen there. It says nothing else.

It is a sibling of the `PATCH-0045` hallucination diagnostic inside the same framework — not a new
subsystem, not a new aggregate, not a new lifecycle.

## The boundary this exists to hold

```text
P1 alone   = a decode window's first segment starting at its provider anchor
           = normal faster-whisper decode semantics
           = NEVER a warning                                            (TD-4)

P1 + a positive gap from the previous admitted coverage
           = a structure worth reviewing
           = a non-blocking Quality Warning                             (TD-2, TD-5)
```

The first line is not a technicality. Measured over a full lecture (`134`), **251 of 251** decode
windows start their first segment exactly at the anchor and **0 of 2,118** non-first segments do.
Warning on that alone would fire on 10.6 % of every transcript — 128 times an hour. The discriminating
condition is the second half, and it fires on **1.31 %**.

## Predicate

```python
P1  segment is the first of its provider decode window
    AND |segment.start - anchor| <= ε
P2  anchor > previous_segment.end + ε
P   P1 AND P2
```

`ε` is the released `PATCH-0039` `TIMING_BOUNDARY_TOLERANCE_SECONDS = 1e-6`, used **only** to decide
whether two values denote the same instant (T-2). No new tolerance was introduced.

**No duration threshold exists** (TD-6). P2 is a strict inequality, so an anchor 0.02 s past the
previous coverage qualifies exactly as one 85 s past does. This is asserted twice: behaviourally, and
structurally by a test that parses `evaluate_timing_predicate`'s AST and rejects any numeric constant
beyond ordinal indexing. A duration cut cannot be reintroduced silently.

## Provider evidence and window reconstruction

The anchor is faster-whisper's `seek`, recorded in centiseconds, preserved verbatim in `window_ref`
by `PATCH-0045` QD-6. `provider_anchor_seconds()` parses exactly that grammar and returns `None` for
anything else — an unrecognised anchor is skipped rather than guessed at (TD-8).

Window membership uses the released grouping unchanged: `_decode_windows_of` groups **runs of adjacent
segments**, which is what keeps a resumed execution's re-based anchors from merging two genuinely
different windows. No new interpretation was invented.

### The trap that was avoided

`132` originally compared `segment.start` against the *preserved window's* `start`. That field is set
to the first segment's own start, so the comparison was an identity of the representation and carried
no information. `134` corrected it and this implementation uses the provider's `seek` anchor
throughout. The window's derived `start` is never consulted by the detector.

Reading segment boundaries back needed one new function, `parse_preserved_segment_timings`, beside
the existing evidence parser — the logical admission content already preserves every segment's
`start` and `end` under A-4, so no new evidence and no schema change were required.

## Why no schema change was needed

The anchor is already inside `original_content`, and the result is not stored. No relation, column,
constraint or migration changed; `SQLITE_SCHEMA_VERSION` stays **53**.

## Persistence and versioning

Not persisted (TD-10). The service holds queries and **no persistence port**, so there is no code path
through which a timing result could be written. It declares `local-asr-transcript-timing-quality` v1
with `provider_parameter_version = None` — the honest value, since no threshold participates (TD-11).

A record without a usable anchor reports `evidence_available = False`, completeness `unavailable`, and
`reports_clean = False`. **Unavailable is not clean** (TD-12), and callers cannot use `not findings`
as a verdict.

## Separation from the hallucination diagnostic

Enforced by type, not by convention (TD-16):

| | hallucination | timing |
|---|---|---|
| reason enum | `QualityReason` | `TimingQualityReason` |
| finding | `QualityFinding` | `TimingQualityFinding` |
| result | `TranscriptQualityDiagnosticResult` | `TranscriptTimingDiagnosticResult` |
| service | `TranscriptQualityDiagnosticService` | `TranscriptTimingDiagnosticService` |

Separate types make an accidental merge impossible. A test additionally asserts the timing detector's
source never mentions `avg_logprob`, `no_speech_prob`, `compression_ratio` or `temperature`, and that
neither result exposes a score, severity or confidence field.

## Downstream boundary

Nothing consults it. A test reads the source of admission, current raw transcript selection, effective
subtitle final selection, SRT artifact, materialization, publication, readability validation and
repository validation, and asserts none imports the timing diagnostic or names its reason.

No timestamp is mutated anywhere. `TranscriptTimingDiagnosticService` is parsed as an AST with
docstrings stripped — so prose about "no persistence port" can neither pass nor fail the check — and
asserted to contain no `persist`/`insert`/`update`/`commit`/`CorrectionCandidate`/`proposed_text`
identifier, and no attribute assignment to `start`, `end` or `segments`.

`§17` Correction Candidate is untouched. It is built on `segment_id`, `proposed_text` and
`source_text_snapshot` and `§19` applies a corrected **revision** — a text contract that does not model
a timing change (TD-17). Timing refinement remains Deferred with no path to connect to.

## Real fixture result

Re-derived from the persisted evidence of the MVI_0147 measurement repository (`134`), with no ASR
re-run:

```text
segments 2,370      decode windows with a usable anchor 252
findings 31         completeness complete
```

**The ordinal set matches `134`'s recorded measurement exactly** — 31 of 31, no extras, none missing —
and a regression test asserts that equality rather than the count. All **4 of 4** human-observed
timing cases from `131` fall inside the finding set.

No precision is claimed. Those four observations are not a random sample, and `134` §8 already
recorded that five segments a human labelled `REAL_SPEECH` also satisfy the predicate — which is
exactly why the warning means *review-worthy* and not *drift confirmed*.

## CLI

```text
transcript_quality_cli timing --admission <id> --database <path>
```

A third read-only subcommand beside `inspect` and `diagnose`; no new UI subsystem. It prints the
algorithm anchor, whether anchors were preserved, the finding count, and for each finding the segment
identity, reason and scope.

It prints **no drift magnitude**. The anchor gap is how far the window opened past the previous
coverage, which is *not* how late any speech is, and reporting it as one would be the claim TD-2
forbids. The output closes with an explicit statement that the result is a structure worth reviewing,
not confirmed drift.

## Limitations

- **Specificity rests on one lecture, one instructor, one model, one configuration** (TD-20). The
  1.31 % / 15.8-per-hour figure is the basis on which the predicate was judged usable — not a
  threshold, not an acceptability criterion, and not a guarantee elsewhere.
- The detector is **faster-whisper-specific**. Another provider yields *unavailable* until its anchor
  grammar is contracted.
- The warning cannot distinguish a genuine late start from speech that really did begin as the window
  opened. That is by design; distinguishing them requires audio, which belongs to the deferred
  refinement layer.
- Legacy results admitted before `PATCH-0045` preserved anchors will always report *unavailable*.
  Nothing is back-filled.

## What this milestone deliberately did not do

No timestamp correction, no subtitle retiming, no automatic Correction Candidate, no VAD, no speech
onset estimation, no drift magnitude, no gap threshold, no readability parameter change, no
hallucination threshold change, no schema or migration, no diagnostic persistence, no downstream gate,
and no regeneration of any released artifact.
