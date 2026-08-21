# PATCH-0046

- Title: Post-Silence Transcript Timing Quality Diagnostic Boundary (040 §14/§15)
- Status: Accepted
- Priority: Medium
- Trigger: `implementation/131` §5 (labeler-reported post-silence drift), `implementation/132`
  (drift measurement), `implementation/133` (`MORE_EVIDENCE_REQUIRED` gate),
  `implementation/134` (full-corpus predicate specificity, `PATCH_READY`)
- Created: 2026-08-21
- Target Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` (§4.2/§4.3/§8/§9 forward notes; §14 A-10
  forward note; new §15 timing-diagnostic subsection; header amended).
  `docs/041_SUBTITLE_PIPELINE.md` is **not** amended — see TD-14.

---

## Status

**Accepted (2026-08-21).** `docs/040_TRANSCRIPT_PIPELINE.md` is amended (Blueprint 0.4): §15 carries
TD-1…TD-20 and its Canonical Invariants as a sibling subsection beside the `PATCH-0045` diagnostic
block, and §4.2, §4.3, §8, §9 and §14 A-10 gained additive forward notes. Every PATCH Acceptance
Criterion below was verified mechanically against the applied diff.

**Implementation Requirements remain intentionally incomplete** — they belong to the subsequent
implementation milestone and are deliberately left unchecked.

Acceptance does not retire the measurement limitation in TD-20. Full-corpus specificity was measured
on **one lecture, one instructor, one model and one configuration**, and that remains true. What
acceptance means is narrower: at the present level of evidence, a non-blocking structural Quality
Warning contract is adopted into the released Blueprint.

It introduces **no schema change, no migration, no new aggregate, no new Product Domain record, no
new lifecycle, no new authority, no numeric threshold, and no downstream gate**. It rewrites no
released record, changes no released identity, regenerates no released artifact, and back-fills
nothing.

## Context

Human labeling of the structural population (`131` §5) surfaced something nobody was looking for: on
five occasions the labeler reported, unprompted, that the utterance began 7–27 seconds later than the
transcript claimed. Every case was the first segment after a long no-speech gap, and the labeler
confirmed the effect was absent in ordinary speech.

`132` measured it. `133` decided the contract shape but could not close the firing predicate — the
obvious one had a ~13 % base rate and the corrected one could not be sized from surviving evidence.
`134` re-ran a full lecture and closed it at **1.31 %**.

This PATCH contracts the diagnostic. It contracts **no correction**: the corrective layer remains
`§15` provider execution / future audio-grounded refinement, and that work stays Deferred.

## Correction of a prior interpretation

`132` §5 reported that "20 of 23 post-silence segments begin at the exact instant their decode window
opens" and read it as evidence of anomalous anchoring. **That comparison was an identity of the
preserved representation, not an observation.** `PATCH-0045`'s window projection sets a window's
`start` to its first segment's own start, so `segment.start == window.start` holds for every
window-first segment by construction.

`134` rebuilt the test on the provider's own anchor — faster-whisper's `seek`, preserved in
`window_ref` under QD-6 — and measured over a full lecture:

```text
window-first segments        251     start == seek anchor :   251  (100.0 %)
non-first segments         2,118     start == seek anchor :     0
```

**Every decode window emits its first segment exactly at its seek anchor, without exception.**
faster-whisper never places that segment at detected speech onset. This is **normal provider decode
semantics, not an anomaly**, and this PATCH must not inherit the earlier reading. TD-4 states it as
contract.

`132` is not rewritten; `134` §1 records the correction and this section carries it into the Blueprint
lineage.

## Blueprint evidence

Four released clauses already frame this, and none is violated.

- **§14 A-10** constrains `start`/`end` to finite seconds, `start >= 0`, `end > start`, non-decreasing
  and non-overlapping. It is a **structural** contract. **No released sentence states that
  `segment.start` marks acoustic speech onset.**
- **§14 A-11** requires submitted text preserved exactly; **A-14** states admission
  "media 파일을 읽지 않는다" — so the admission boundary structurally *cannot* observe this, which is
  why the gap is real rather than a defect.
- **§8 Review Connection** already lists "Source Timeline 연결 문제" among what the pipeline may hand
  to Review. A timing-alignment risk is exactly that.
- **§9.1 ASR Failure** covers a provider that "결과를 만들지 못하거나 사용할 수 없는 결과를 반환한"
  state. A segment with a questionable start is neither: it is well-formed and usable.

`PATCH-0045` QD-1…QD-20 already contract a derived, non-persisted Quality Warning with
provider-specific evidence behind provider-neutral vocabulary, versioned algorithm anchors, and
explicit non-blocking / no-automatic-correction guarantees. **This PATCH reuses that framework rather
than building another** (TD-3).

## Empirical evidence

From `134`, on MVI_0147 (장혜정 선생님, 1.96 h, 2,370 segments, released path re-run with
`condition_on_previous_text=False`, no VAD):

| predicate | count | rate | per hour |
|---|---|---|---|
| P1 — window-first **and** `start == seek` | 251 | 10.60 % | 127.9 |
| P2 — `seek > previous segment end` | 31 | 1.31 % | 15.8 |
| **P = P1 ∧ P2** | **31** | **1.31 %** | **15.8** |

Of the 251 window-first segments, **220 have the anchor exactly equal to the previous segment's end** —
continuous speech, where `seek` advances to where the last segment finished. Only 31 open across
emitted non-speech.

Human join (population and predicate frozen first): **4 of 4** previously human-confirmed timing-drift
observations fired. Of 75 segments a human labelled `REAL_SPEECH` in this lecture, **5 also fired**,
three of them among the six largest anchor gaps.

That last number is the reason for TD-2's wording: **real speech can fire P.** The warning cannot mean
"drift confirmed".

Anchor-gap distribution across the 31: 16 under 1 s, 6 between 1–3 s, 3 between 3–10 s, 6 at 10 s or
more (max 85.5 s). **No cut anywhere in this PATCH uses those figures.**

## Decision

### Scope and meaning

**TD-1 (Confirmed) — Scope.** This contract governs a derived timing-quality diagnostic over admitted
Raw Transcripts for this generation's Local ASR. It changes no stage's authority, adds no gate, and
introduces no Product Domain record.

**TD-2 (Confirmed) — A Quality Warning meaning "alignment review-worthy", never a verdict.** The
warning states that a segment's start coincides with a provider decode-window anchor that opened over
non-speech, so its alignment with acoustic onset is **worth a person's attention**. It does **not**
assert that drift exists, how large it is, where speech actually begins, that the text is
hallucinated, or that anything should be changed. `134` §8 showed real speech firing P; a stronger
name or meaning would misdescribe the detector. Reason names such as `DRIFT_CONFIRMED`,
`WRONG_TIMESTAMP` or `EARLY_BY_N_SECONDS` are **prohibited**.

**TD-3 (Confirmed) — Reuse the `PATCH-0045` framework.** This is a sibling reason family inside the
released Transcript Quality Diagnostic, not a new subsystem. QD-2 (Quality Warning, not Validation
Failure), QD-3 (admission unaffected), QD-4 (derived after admission), QD-10 (not persisted), QD-11
(versioned algorithm), QD-16 (no automatic deletion or correction), QD-17 (released correction path)
and QD-18 (non-blocking but not hidden) apply unchanged. **No new aggregate, lifecycle or authority.**

**TD-4 (Confirmed) — P1 alone is normal provider semantics and is never a warning.** A window's first
segment starting exactly at its `seek` anchor occurred in **251 of 251** windows and **0 of 2,118**
non-first segments. It is how faster-whisper represents a decode window, fires on 10.6 % of segments,
and **must not** produce a warning on its own.

### Firing predicate

**TD-5 (Confirmed) — The predicate is structural and threshold-free.**

```text
P1  segment is the first segment of its provider decode window
    AND segment.start == provider window anchor          (within ε)
P2  provider window anchor > previous admitted segment end   (within ε)
P   P1 AND P2
```

`ε` is the released `PATCH-0039` `TIMING_BOUNDARY_TOLERANCE_SECONDS = 1e-6`, used **only** for
same-instant comparison (T-2's stated purpose). **No new tolerance is introduced.**

**TD-6 (Confirmed) — No gap-duration threshold.** P2 is a strict inequality, not a duration test.
`gap ≥ 3 s`, `≥ 5 s`, `≥ 10 s`, `duration ≥ 7 s` and `window == 30 s` are **measurement observations,
never firing conditions**. A segment 0.10 s past the previous coverage fires exactly as one 85.5 s
past does; whether that is desirable is a product question this contract does not answer, and
answering it with a cut would be inventing the threshold this work has refused three times.

**TD-7 (Confirmed) — What P claims, stated exactly.**

> This segment begins at a provider decode-window anchor, and that anchor lies after the end of the
> previous admitted transcript coverage. Whether the provider timestamp aligns with acoustic speech
> onset is therefore worth human review.

P does **not** claim: drift exists; drift is N seconds; where speech begins; that the text is
fabricated; that the segment should be corrected.

### Provider boundary

**TD-8 (Confirmed) — Provider-neutral vocabulary, provider-specific detector.** Following QD-5/QD-6's
precedent: the reason is provider-neutral, while the detector reads faster-whisper's `seek` anchor
preserved in `window_ref`. **No assumption** is made that another provider exposes `seek`, uses
30-second windows, or shares Whisper's anchoring behaviour. A provider without preserved window
anchors yields **unavailable**, never *clean* (QD-9).

**TD-9 (Confirmed) — Reason vocabulary.** One reason this generation, matching the released
subject-then-condition convention of QD-12:

| reason | evidence family | scope |
|---|---|---|
| `TIMING_ALIGNMENT_REVIEW_REQUIRED` | provider decode-window anchor vs previous transcript coverage | segment |

Its scope is **segment**, unlike QD-12's window-scoped provider reasons: the anchor relationship is a
property of one segment's position, not a value shared across a window. No score, combined or
otherwise, is produced.

### Persistence, identity, versioning

**TD-10 (Confirmed) — Derived, never persisted.** Deterministic from the preserved decode-window
anchor (QD-6), segment timing and ordering. QD-10's reasoning applies unchanged; no canonical
Diagnostic record is introduced, and `070`'s deferral stands.

**TD-11 (Confirmed) — Versioned even without thresholds.** The detector declares an algorithm kind
and version over an immutable anchor. The provider parameter version is **`None`** — no threshold
participates, and the predicate itself can still change.

**TD-12 (Confirmed) — Legacy is unavailable, never clean.** A result admitted before decode-window
anchors were preserved yields `unavailable`. **Nothing is back-filled**, no released record is
rewritten, and `content_fingerprint`, `provider_result_ref` and Raw Transcript identity are unaffected
— read-time derivation over stored evidence is not backfill.

### Boundaries preserved

**TD-13 (Confirmed) — Admission and Raw Transcript unaffected; nothing blocks.** A timing warning
refuses no admission, no Raw Transcript, no Effective Transcript Selection, no subtitle generation and
no publication. **Raw Transcript timestamps are never modified** — A-11's exact-preservation
requirement and §2 Raw Before Corrected bind unchanged. Repository validation neither knows nor
reports timing warnings.

**TD-14 (Confirmed) — `041` is not amended and never re-times source segments.** Subtitle Time
Representation does not reinterpret transcript timing on the strength of an upstream warning. §7's
released principles already require that unverifiable time links and Uncertainty not be hidden as
normal results, which covers coexistence without new text.

**TD-15 (Confirmed) — Readability warnings coexist; neither suppresses the other.**
`READABILITY_DURATION_ABOVE_MAXIMUM` is **correct** when it fires — the cue really is that long. A
timing warning explains a possible upstream cause; it grants no exemption. Prohibited in both
directions: `readability > 7 s → timing warning`, and `timing warning → suppress duration warning`.
Readability v2 parameters are unchanged.

**TD-16 (Confirmed) — Hallucination and timing stay separate.** One segment may carry both. Neither
signal decides the other: `no_speech_prob` never confirms drift, `avg_logprob` never justifies a
timing change, and window-anchored timing never confirms fabrication. They co-occur because both
arise where a window opens over non-speech; they remain distinct reasons with distinct evidence.

**TD-17 (Confirmed) — No automatic correction, and no correction path to reuse.** No automatic
timestamp change, Final Subtitle adjustment, Raw Transcript rewrite, or Correction Candidate. `§17`
Correction Candidate admission is built on `segment_id`, `proposed_text` and `source_text_snapshot`
and `§19` applies a corrected **revision** — the boundary is text-shaped and **does not model a timing
change**. Bending it into one would distort released semantics, so timing correction stays Deferred
with no path to connect to.

**TD-18 (Confirmed) — Released artifacts are immutable history.** Existing Raw Transcripts, Provider
Results, Final Selections, SRT Artifacts and Materializations are unchanged and **not regenerated**.

**TD-19 (Confirmed) — No schema change.** The anchor is already preserved in `original_content` under
QD-6 and the derived warning is not stored. No table, column, constraint or migration; no generic
column repurposed. `docs/030_DATA_MODEL.md` is not amended.

### Measurement basis

**TD-20 (Confirmed) — The specificity figure is evidence, not a contract term.** `134`'s 1.31 % /
15.8 per hour was measured on **one lecture, one instructor, one model, one configuration**. It is
recorded as the basis on which TD-5 was judged usable and is **not** a threshold, an acceptability
criterion, or a guarantee for other providers, instructors or models.

That basis does not block this contract, because P is a structural observation rather than a numeric
cut, the warning means only *review-worthy*, nothing blocks, no correction follows, and the detector
is declared provider-specific. Measuring P on the remaining lectures is worthwhile and is **not** a
precondition.

## Non-goals

Not decided here, each requiring its own gate: VAD adoption; audio-grounded alignment or refinement;
acoustic speech-onset detection; drift magnitude; correction amount; any gap-duration threshold;
automatic timing correction; a timing-specific Human Modify workflow; regeneration of released SRTs;
publication or export gating; a provider-independent detector; word timestamps; adoption of any new
provider or tool; hallucination thresholds; readability parameter changes; and everything already
deferred by `PATCH-0040` L-14/L-16 and `PATCH-0045`.

## Required Blueprint Changes

Applied to `docs/040_TRANSCRIPT_PIPELINE.md` only.

1. **Header** — Blueprint version and Last Updated advanced; `PATCH-0046` added to `Amended By`.
2. **§4.2** — released text kept verbatim; forward note recording that a decode-window anchor is
   provider timing evidence, that a window's first segment starting at that anchor is normal provider
   semantics (TD-4), and that provider timestamps are preserved unchanged.
3. **§4.3** — released text kept verbatim; forward note recording that a Raw Transcript with
   questionable timing is still preserved and created, that timestamps are never rewritten, and that
   *timing evidence unavailable* is not *timing clean*.
4. **§8** — released list kept verbatim; forward note recording that a timing-alignment risk is
   offered to Review under the existing "Source Timeline 연결 문제" entry, with no new Review Item
   type and no new Human Authority.
5. **§9** — released failure classes kept verbatim; forward note recording that a timing Quality
   Warning is neither §9.1 ASR Failure nor §9.3 Validation Failure, since the segment is structurally
   valid and usable.
6. **§14 A-10** — released sentence kept verbatim; forward note separating **structural timing
   validity** (what A-10 contracts) from **acoustic alignment quality** (what this diagnostic
   observes), and stating that `PATCH-0039`'s ε is a representation tolerance unrelated to this
   seconds-scale semantic question.
7. **§15** — a new subsection beside the `PATCH-0045` Transcript Quality Diagnostic block carrying
   TD-1…TD-20 and its own Canonical Invariants.

`docs/041_SUBTITLE_PIPELINE.md` is not amended (TD-14). `docs/030_DATA_MODEL.md` is not amended
(TD-19).

## PATCH Acceptance Criteria

Verified mechanically against the applied Blueprint amendment.

- [x] The warning's meaning is limited to **review-worthy alignment risk**; `DRIFT_CONFIRMED`,
      `WRONG_TIMESTAMP` and `EARLY_BY_N_SECONDS` style names appear nowhere.
- [x] It is stated **not** a Validation Failure and **not** an Admission Failure.
- [x] P1 alone is stated to be **normal provider decode semantics and never a warning**, with the
      251/251 vs 0/2,118 evidence recorded.
- [x] The threshold-free predicate P is defined exactly, using only the released `PATCH-0039` ε.
- [x] **No gap-duration threshold** is introduced anywhere.
- [x] Automatic correction, deletion and Correction Candidate creation are prohibited.
- [x] Raw Transcript preservation is intact; timestamps are stated never modified.
- [x] Provider-neutral reason and provider-specific detector are stated as separate.
- [x] Derived diagnostic non-persistence is stated; no canonical Diagnostic record appears.
- [x] Coexistence with `READABILITY_DURATION_ABOVE_MAXIMUM` is stated in both directions.
- [x] Separation from the hallucination diagnostic is stated, with no cross-signal inference.
- [x] No schema change, no migration, and `docs/030` unamended.
- [x] Released artifacts are stated immutable and not regenerated.
- [x] Correction and refinement are stated Deferred.
- [x] No released sentence in `docs/040` is deleted or rewritten — prior PATCH notes included —
      verified line by line; §4.2, §4.3, §8, §9 and A-10 gain **additive forward notes only**.

## Implementation Requirements

Required validation for the implementing milestone. **Not satisfied by this PATCH.**

1. P is recomputed deterministically from the preserved decode-window anchor, segment timing and
   ordering; identical inputs and detector version yield an identical result.
2. The detector declares its algorithm kind and version; the provider parameter version is `None`.
3. A result without preserved window anchors reports `unavailable`, never *clean*, and a legacy
   record still loads.
4. `P1 ∧ ¬P2` produces **no** warning — asserted on a window-first segment whose anchor equals the
   previous segment's end.
5. Nothing is persisted: no table, column or row is added, and schema version stays **53**.
6. No code path modifies a transcript timestamp, a subtitle cue time, or creates a Correction
   Candidate.
7. Admission, Raw Transcript creation, selection, subtitle generation and publication are unaffected
   by any warning; repository validation neither knows nor reports it.
8. Timing and hallucination reasons are emitted independently; no combined score exists.
9. A readability duration warning is neither suppressed nor exempted by a timing warning.
10. The warning is reachable through an observable boundary (CLI or Review preparation) without
    introducing a gate.
11. Released `content_fingerprint`, `provider_result_ref` and Raw Transcript identities are unchanged;
    the complete test suite passes.

## Consequences

- `§15` gains a timing-quality diagnostic beside the `PATCH-0045` hallucination diagnostic; §4.2,
  §4.3, §8, §9 and A-10 gain forward notes; nothing else moves.
- One implementation slice adds a derived detector. **No schema change is expected.**
- Released records keep their identities exactly, gain nothing, and stay valid.
- A phenomenon a human noticed while doing something else becomes **findable** — roughly 16 segments
  per lecture-hour flagged for alignment review, against a released readability warning stream of
  similar order.
- Correction remains Deferred, and `§15` L-16's two conditions — timestamp improvement **and**
  real-speech preservation — remain the gate any future refinement must pass.
