# Post-Silence Timing Quality Diagnostic — Architect Decision / PATCH Gate (Evaluation)

- Status: Evaluation Record
- Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` §14 A-10/A-11/A-14, §15 L-6/L-16, `PATCH-0045` QD-1…QD-20
- Production impact: **none** — no PATCH, no Blueprint change, no schema change, no code change
- Related: `131`, `132_POST_SILENCE_TIMESTAMP_DRIFT_MEASUREMENT.md` (commit `ae60e40`)

## PATCH Gate Result

```text
MORE_EVIDENCE_REQUIRED
```

No PATCH was written. The diagnostic's *meaning* closes cleanly; its *firing predicate* does not,
and the missing measurement is specific and obtainable (§15).

The blocking finding, stated plainly: the obvious predicate is **not specific**, and the corrected
predicate's corpus-wide firing rate **cannot be measured from surviving evidence** — the bound spans
roughly 8 to 230 warnings per lecture. Contracting a firing rule inside a 30× uncertainty band would
repeat, a third time, the selection-bias error this investigation has already documented twice.

## 1. Repository investigation

Read: `040` §4.2/§4.3, §8, §9, §14 A-4/A-8/A-10/A-11/A-14, §15 L-5/L-6/L-16 and the `PATCH-0045`
Transcript Quality Diagnostic subsection (QD-1…QD-20 + Canonical Invariants); `041` §7 and §16;
`PATCH-0039/0040/0044/0045`; reports `122`, `124`, `129`, `130`, `131`, `132`.

Reusable abstraction found: `PATCH-0045` already contracts a derived, non-persisted Quality Warning
with provider-specific evidence behind a provider-neutral vocabulary, versioned algorithm anchors, and
explicit non-blocking / no-automatic-correction guarantees. **A timing diagnostic needs no new
framework** — QD-2/QD-3/QD-10/QD-16/QD-18 apply almost verbatim. That part of the design is settled
and is recorded in §12 for whenever the evidence arrives.

Data constraint (from `131` §9, `132` §1): the scratchpad was cleared by the OS. Decode-window
boundaries survive **only** for the 221 structural candidates, in
`evaluation/transcript-quality-structural-labeling/manifest_analysis.csv`. This is the constraint that
decides the gate.

## 2. Empirical evidence interpretation

`132` (commit `ae60e40`) proves:

- 20 of 23 post-silence first segments start exactly at their decode-window boundary; 7 of the 8
  large-drift cases do.
- Drift is not proportional to gap length (r = −0.070, n = 19).
- Controls separate: ordinary speech median 1.62 s with no case above 5 s, against post-silence
  median 4.10 s with 8 of 19 above 5 s.
- 72 % of `READABILITY_DURATION_ABOVE_MAXIMUM` warnings originate in these segments.

`132` does **not** prove: the magnitude of drift for any individual segment (energy onset is a lower
bound), that window anchoring implies late speech, or that the behaviour generalises beyond
`large-v3` with the approved configuration.

## 3. Problem classification

Unchanged from the standing decision: **provider behaviour that exposes a Blueprint gap in Transcript
Timing Quality.** No released clause is violated. `§14` A-10 constrains ordering, positivity and
non-overlap; nothing states that `segment.start` marks acoustic onset; A-14's "media 파일을 읽지
않는다" means admission structurally cannot observe it.

## 4. Diagnostic meaning

The evidence supports exactly one claim, and it is narrower than the phenomenon:

> This segment's start coincides with the decode-window boundary, and that window opened after an
> interval in which the provider emitted no speech. Its start may therefore precede the actual
> utterance.

It does **not** support "the utterance begins N seconds later", because that requires audio, and
`132` §3 showed the audio-free estimate failing by 23 s in one of four validation cases.

Vocabulary candidates were assessed against the released naming convention (`PROVIDER_LOW_CONFIDENCE`,
`READABILITY_DURATION_ABOVE_MAXIMUM` — subject-then-condition, no severity in the name):

| candidate | assessment |
|---|---|
| `POST_SILENCE_WINDOW_ANCHORED_TIMING` | accurate but "post-silence" restates the predicate's second half |
| `TIMING_START_AT_DECODE_WINDOW_BOUNDARY` | most literal; says only what is observed |
| `PROVIDER_WINDOW_ANCHORED_TIMING` | **preferred** — `PROVIDER_` prefix matches QD-12's provider-derived family and marks it as provider evidence rather than a product verdict |

Recorded as a recommendation, not contracted.

## 5. Firing predicate — where the gate closes

### P1 alone is not specific

```text
segment.start == window.start
```

| | rate |
|---|---|
| post-silence first segments | 20 / 23 = **87.0 %** |
| all other structural candidates | 26 / 198 = **13.1 %** |

The 13.1 % is not noise, it is arithmetic: **the first segment of any decode window starts at that
window's boundary by construction.** With a median of 7 and a mean of 8 segments per window, ~12 % of
*all* segments satisfy P1 automatically. The observed 13.1 % matches that base rate.

**P1 alone would fire on roughly one segment in eight, everywhere.** §5 of the governing prompt
disposes of this case directly.

### P1 ∧ P2 is threshold-free and looks specific

```text
P1 : segment.start == window.start
P2 : window.start  >  previous segment.end        (the window opened after non-speech)
```

P2 uses no number — only a strict inequality against the preceding segment's end.

| | P1 | P2 | P1 ∧ P2 |
|---|---|---|---|
| post-silence (n=23) | 87.0 % | 87.0 % | **87.0 %** |
| other (n=188) | 12.8 % | 3.7 % | **3.7 %** |

The gap distribution behind P2 is strikingly clean:

```text
exactly 0.000000 s   17 cases   — continuous speech, window opens where the last segment ended
        0.020000 s    3 cases   — one Whisper timestamp tick; quantisation, not a pause
       >= 1.0     s   24 cases   — 20 of them post-silence
```

Seventeen continuous-speech cases sit at **exactly** zero. Whisper advances its seek to the end of
the last segment, so in continuous speech P2 is false by construction. That is a real structural
signal, not a fitted one.

### Why this still does not close

Four of the seven "off-target" firings are, on inspection, the phenomenon rather than false
positives — `시험장에 오신 것을 환영합니다` (9.0 s gap, just under the structural rule's 10 s),
`고춧가루`, `아`, `얘들아 사전 잘 볼 줄 알죠?`. The predicate is finding cases the `≥ 10 s` proxy
label missed.

That is encouraging and it is beside the point. **The 3.7 % was measured inside the structural
population, which is 4 % of the corpus and was deliberately selected for proximity to long gaps.**
Extrapolating a firing rate from a gap-enriched sample to the whole corpus is the exact error
documented in `129` §5 and again in `131` §8.

The corpus-wide rate cannot be measured from what survives:

- P2 needs each segment's decode-window boundary. Those are preserved for **221 of 5,487** segments.
- An upper bound from the released SRTs — how often any non-speech interval exists at all — is
  **10.0 %** of cues in MVI_0146 and **29.4 %** in MVI_0147. If the predicate fired at that rate it
  would produce 170 and 758 warnings per lecture.
- A lower bound is the 23 observed post-silence segments, ~8 per lecture.

**The honest interval is roughly 8 to 230 warnings per lecture.** Nothing in the surviving evidence
narrows it, and a diagnostic whose volume is unknown within 30× cannot be contracted.

### False-positive semantics (settled, for the record)

Window-boundary coincidence does not prove drift; speech may genuinely begin as the window opens. So
the warning would mean **"timing requires review"**, never **"drift confirmed"** — which is why the
`PATCH-0045` safety envelope (non-blocking, no automatic correction, no automatic deletion, Human
Authority) is a precondition rather than a nicety.

## 6. Provider boundary

`PATCH-0045` QD-5/QD-6 set the precedent: provider-specific evidence preserved under the provider's
own field names, interpreted by a provider-neutral diagnostic vocabulary. The same split works here —
`decode window boundary` is a faster-whisper concept (`seek`), while "this segment's start coincides
with the boundary of the decode unit that produced it" is expressible provider-neutrally.

No assumption is made that other providers expose `seek` or share Whisper's window semantics. A
provider without preserved window boundaries would report **evidence unavailable**, never *clean* —
QD-9's rule, applying unchanged.

## 7. Persistence and versioning

Settled, and no new mechanism is needed.

- **Not persisted.** Deterministic from `original_content` (window boundaries, QD-6) plus the
  immutable Raw Transcript. QD-10's reasoning applies without modification, and `070`'s deferral of a
  canonical Diagnostic record is untouched.
- **Versioned anyway.** Even a threshold-free structural detector needs an algorithm kind and version
  under QD-11, because the predicate itself can change. The provider parameter version stays `None`
  — no threshold participates.
- **Legacy.** A result without preserved decode-window evidence yields **unavailable**, never
  *clean* (QD-9).
- **Identity.** Read-time derivation touches no identity: `content_fingerprint`, `provider_result_ref`
  and Raw Transcript identity are unaffected. Deriving observations over already-stored evidence is
  not backfill.

## 8. Admission / Raw Transcript impact

| | |
|---|---|
| Validation Failure | **No** — structurally valid: ordering, positivity, non-overlap, lineage all intact |
| Admission blocking | **No** — refusing would discard the provider evidence A-4 exists to preserve |
| Raw Transcript creation blocking | **No** |
| Raw Transcript rewrite | **No** |

Consistent with A-10 (structural validity only), A-11 (submitted values preserved exactly) and A-14
(admission reads no media). `PATCH-0039`'s ε = 1e-6 is a *representation* tolerance and is unrelated
to this seconds-scale semantic issue; conflating them would be a category error.

## 9. Human review / correction relationship

`§17` Correction Candidate admission was examined for reuse. It is built on `segment_id`,
`proposed_text` and `source_text_snapshot`, and `§19` applies a corrected **revision** — the entire
boundary is text-shaped. **It does not model a timing change**, and bending it into one would distort
released semantics.

Therefore: timing correction stays Deferred, with no correction path to connect to. The diagnostic
would surface a segment for human attention and stop there. No automatic timestamp change, no
automatic Final Subtitle change, no automatic Correction Candidate — QD-16 applies unchanged.

## 10. Downstream and readability relationship

Visibility, never a gate. The `§12` requirement that Uncertainty not be hidden "정상 승인 결과처럼"
binds; no new publication, export or Final Selection gate is proposed.

Both warnings should coexist and neither should suppress the other. `READABILITY_DURATION_ABOVE_MAXIMUM`
is **correct** when it fires — the cue really is that long. `132` §9's finding that 72 % of those
warnings trace to this artefact explains their *cause*; it does not make them wrong. Suppressing a
duration warning because a timing warning exists would hide a real display problem, and `041`
must not re-time source segments on the strength of an upstream warning.

## 11. Existing artifact impact

Nothing rewritten, nothing regenerated: Raw Transcripts, Provider Results, Final Selections, SRT
Artifacts and Materializations all unchanged. Read-time derivation over stored evidence would apply to
past records without touching them.

## 12. Architect decisions

Recorded as reached. **TD-5 is the one that is not closed**, and it holds the gate.

| id | decision | status |
|---|---|---|
| TD-1 | Timing quality is a **Quality Warning**, never a Validation Failure | closed |
| TD-2 | Non-blocking at every boundary: admission, Raw Transcript, selection, subtitle, publication | closed |
| TD-3 | The claim is **structural coincidence with a decode-window boundary**, never a drift magnitude | closed |
| TD-4 | Reuse the `PATCH-0045` framework as a sibling reason family; no new aggregate or lifecycle | closed |
| TD-5 | **Firing predicate** | **OPEN — see §5** |
| TD-6 | Derived, not persisted; versioned algorithm anchor; no threshold parameter version | closed |
| TD-7 | Provider-specific detector behind provider-neutral vocabulary; missing evidence ⇒ *unavailable*, never *clean* | closed |
| TD-8 | No automatic correction, deletion, or Correction Candidate; `§17` is text-shaped and is not reused | closed |
| TD-9 | Timing and readability warnings coexist; neither suppresses the other | closed |
| TD-10 | Timing and hallucination reasons stay separate; no signal crosses between them | closed |
| TD-11 | No schema change | closed |

On TD-10, one observation that must **not** become a rule: four of the seven off-target P1 ∧ P2
firings are human-confirmed hallucinations. Timing risk and fabrication risk co-occur because both
arise where a window opens on non-speech. They remain separate reasons with separate evidence, per
the strict separation this session was instructed to keep.

## 13. Blueprint impact (if the gate later closes)

Additive only; no released sentence deleted or rewritten.

- `040` §15 — a sibling subsection beside the `PATCH-0045` diagnostic block carrying TD-1…TD-11.
- `040` §14 A-10 — forward note: structural timing validity is not acoustic alignment quality.
- `040` §9 — forward note: a timing Quality Warning is not an ASR Failure and not a Validation Failure.
- `040` §4.2/§4.3 — forward notes on timing evidence and on preserving questionable-timing transcripts.
- `041` — **no change.** §10's reasoning removes the need; a forward note would only restate what
  §7 already implies.

## 14. Schema impact

**None.** Decode-window boundaries are already preserved in `original_content` under QD-6, and the
derived warning is not persisted. No generic column is repurposed.

## 15. Required additional measurement

One measurement decides the gate.

**Measure the corpus-wide firing rate of P1 ∧ P2.** Concretely: preserve decode-window boundaries for
**every** segment of at least one full lecture — not merely the 4 % structural sample — then compute

- how many segments satisfy P1 ∧ P2 per lecture and per hour;
- their distribution of `window.start − previous.end`, to see whether the clean 0 / ≥ 1 s split
  observed here holds corpus-wide or is an artefact of gap-enriched sampling;
- how many fall outside the structural population, and whether those are the phenomenon (as the four
  cases in §5 suggest) or ordinary speech.

Cost: one ASR re-run per lecture (~1 hour each). The evidence already flows through the released
`PATCH-0045` path — this needs no new capability, only that the extracted evidence be **kept outside
the scratchpad** this time.

Two smaller questions worth settling in the same pass:

- Does the 0.02 s tick (three cases) represent a real pause or timestamp quantisation? If quantisation,
  P2 needs a representation-tolerance guard analogous to `PATCH-0039` T-2 — which would be a
  representation decision, not a product threshold.
- Does window anchoring reproduce under a second model or configuration (`132` §14)?

## 16. PATCH output

None. `MORE_EVIDENCE_REQUIRED`.

## 17. Result

```text
Diagnostic contract decided:   Partially — TD-1…TD-4, TD-6…TD-11 closed; TD-5 (firing predicate) open
Diagnostic meaning:            Structural coincidence with a decode-window boundary that opened
                               after provider-emitted non-speech; "timing requires review",
                               never "drift confirmed", never a drift magnitude
Firing predicate:              NOT CONTRACTED — P1 alone has a ~13% base rate by construction;
                               P1 ∧ P2 is threshold-free and measures 87% vs 3.7% inside the
                               structural population, but its corpus-wide rate is unmeasurable
                               from surviving evidence (bound ≈ 8–230 per lecture)
Automatic correction:          No
Admission blocking:            No
Raw Transcript rewrite:        No
Derived diagnostic persisted:  No
Schema changed:                No
Blueprint changed:             No
Production changed:            No

Decision gate:                 MORE_EVIDENCE_REQUIRED

Requires Architect Decision:      No — the standing decision is confirmed
Requires Blueprint Clarification: No
Requires Blueprint PATCH:         Yes, but not yet — blocked on TD-5
Requires additional measurement:  Yes — corpus-wide P1 ∧ P2 firing rate over a full lecture
                                  with decode-window boundaries preserved for every segment (§15)
```
