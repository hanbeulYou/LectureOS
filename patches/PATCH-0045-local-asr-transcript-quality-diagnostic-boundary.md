# PATCH-0045

- Title: Local ASR Transcript Quality Diagnostic Boundary (040 §14/§15)
- Status: Proposed
- Priority: Medium
- Trigger: Architect Decision on the residual hallucination recorded in
  `implementation/122_FULL_LENGTH_REAL_MEDIA_E2E_VALIDATION.md` and left open by `PATCH-0040` P-9
- Created: 2026-08-09
- Target Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` (§14 A-4 and A-8 forward notes; new §14 and
  §15 quality-diagnostic decisions; §4.2/§4.3 and §11 forward notes; header amended).
  `docs/030_DATA_MODEL.md` is **not** amended — see QD-20.

---

## Status

**Proposed.** This document exists; `docs/040_TRANSCRIPT_PIPELINE.md` has not yet been amended.

It introduces **no schema change, no migration, no new aggregate, no new Product Domain record, no
new lifecycle, no new authority, no threshold, and no downstream gate**. It rewrites no released
record, changes no released identity, and backfills nothing.

## Context

`PATCH-0040` set `condition_on_previous_text=False` and recorded in P-9 that hallucination is
*reduced, not contracted away*, routing the residue to `§17`, `§18` and `042`. Full-length validation
left it observable: fabricated sentences over an instructor-absent region, repeated output, and short
fragments, all of which reached the published SRT.

The question this PATCH answers is not how to remove them. It is how to **preserve the quality
evidence the provider already returns** and derive a reproducible warning from it, so a person can
find suspect regions in a 2,564-segment transcript without reading all of it.

## Blueprint evidence

**This is an unmet released responsibility, not a new product domain.** Four released sentences
already assign it:

- **§4.2 ASR** — "**Produces:** provider 원본 결과와 출처, 제공 가능한 발화·단어 시간 정보, **confidence
  또는 Uncertainty**, provider failure."
- **§4.3 Raw Transcript** — "**Produces:** 출처와 가능한 시간 정보 및 **Uncertainty**를 유지한 Raw
  Transcript revision."
- **§4.x Review Preparation** — "교정 후보, **Uncertainty**, Validation Failure, 누락과 의미 위험을
  Review Item으로 연결" — and `§11` lists "**낮은 confidence 또는 Uncertainty가 있는 ASR 결과**" among
  the states that must reach Review.
- **§14 downstream constraint** — "**Validation Failure와 Uncertainty를 정상 승인 결과처럼 숨기지
  않아야 한다.**"

The Blueprint therefore already separates **Uncertainty** from **Validation Failure**, already
requires the ASR stage to produce it, already requires Raw Transcript to preserve it, and already
forbids hiding it. The first `§14`/`§15` slices simply did not realize it.

**`§14` A-4** requires `original_content` to preserve "제출된 provider 증거 … **정규화 이전 상태**"
and states "제출된 provider 증거를 조용히 버리지 않는다."

## Provider evidence — what actually exists

`faster-whisper 1.2.0` returns per segment: `id`, `seek`, `start`, `end`, `text`, `tokens`,
`avg_logprob`, `compression_ratio`, `no_speech_prob`, `temperature`, `words`. The released adapter
converts only `start`, `end`, `text` into `LocalAsrSegment`, and `ProviderTranscriptSegmentInput`
carries only those three — so the quality evidence is discarded **before** it reaches the `§14`
boundary. A-4 is not violated (nothing *submitted* is dropped), but `§4.2`'s obligation is unmet.

Measured on the preserved fixtures with the approved configuration:

| signal | hallucination cluster | worst normal value |
|---|---|---|
| `no_speech_prob` | **0.813** | 0.467 |
| `avg_logprob` | **-0.967** | -0.571 |
| `compression_ratio` | **2.37** | 1.48 |
| `temperature` | **0.4** | 0.0 (all normal) |

All four fire together on the repeated fabrication, and the classical-terminology region — which
contains real *recognition errors* — fires none of them, so misrecognition and hallucination are
distinguishable.

**The decisive structural finding: these values are decode-window evidence, not segment evidence.**
Across 32 fixture segments there are only 6 distinct values of each, with up to 8 consecutive
segments sharing one. Two real utterances and one fabrication in the same window carry identical
values, so provider evidence alone cannot separate them — which is why no single score is admissible.

## Provider evidence persistence — alternatives

**M2 — `transcript_segments.confidence` / `uncertainty`. Rejected.** The columns exist, but writing a
window value into a per-segment `confidence` states something untrue: that this segment carries that
confidence. Eight segments would claim the same figure while one of them is a fabrication and the
others are speech. A provider-specific log-probability is also not a generic confidence. Released
column semantics must not be bent to fit an available slot.

**M3 — a new provider evidence representation. Rejected for this generation.** It would add an
aggregate, a schema version, an identity and an ordering contract to carry data that A-4 already
assigns to `original_content`, and it would pull faster-whisper field names into the provider-neutral
core.

**M4 — `provider_transcript_result_diagnostics`. Rejected.** That relation holds ordered opaque
`DiagnosticId` references, and `070_DIAGNOSTIC_PERSISTENCE_ASSESSMENT` deferred canonical Diagnostic
content deliberately. More importantly it would **merge two different things**: provider evidence is
a fact the provider reported and cannot be recomputed; a diagnostic is a derived interpretation. They
must not share a representation.

**M1 — `original_content`. Adopted.** A-4 already defines `original_content` as the un-normalized
preserved provider evidence, and decode evidence is exactly that. It requires no new aggregate, no
new identity, and no schema change: the column already holds a canonical serialization of whatever
was submitted.

## Fingerprint and identity analysis

This is the part that had to be proved before M1 could be adopted.

`content_fingerprint` is computed as `_sha256(_admission_payload(...))` and `original_content` is set
to `_admission_payload(...)` — **the same function**. Their equality today is an implementation
coincidence, not a contract: A-4 describes what `original_content` preserves, A-8 describes what the
fingerprint covers, and no released sentence requires the two strings to be identical.

If evidence simply joined that single payload, then for one anchor the enriched and non-enriched
documents would serialize differently and A-9 would treat them as a **conflict**. `§15` L-8's
reuse-before-rerun hides that in the adapter path, but the `§14` admission CLI reaches it directly.
It would also mean an already-admitted lecture could never gain evidence, since reuse returns the old
record before the engine runs.

**The resolution is to separate the two, not to version the reference.** A-8's stated purpose is
identifying "동일한 논리적 결과" — the same logical result. Two runs producing identical text and
timing with different log-probabilities **are** the same logical result; the decode statistics are
provenance about how it was produced, not what it is. Excluding evidence from the fingerprint
therefore serves A-8's own criterion rather than weakening it.

A new `provider_result_ref` version is **not** introduced. `§15` L-7 defines that reference as the
*semantic execution request*, and capturing more of the provider's response is not a different
request. Minting `v3` for it would misuse L-7's stated meaning to solve a problem that separating
`original_content` from the fingerprint already solves.

## Decision

### Scope and meaning

**QD-1 (Confirmed) — Scope.** This contract governs quality evidence preservation at the `§14`
boundary and a derived quality diagnostic over admitted Raw Transcripts. It changes no stage's
authority and adds no gate anywhere.

**QD-2 (Confirmed) — A quality diagnostic is a Quality Warning, never a Validation Failure.** A
hallucinated segment is **structurally valid** — ordered, non-overlapping, within range, with intact
lineage. It is `§4.x`/`§11` **Uncertainty**, which the Blueprint already treats as a distinct
category. It is not a validation code, not a repository integrity finding, and never reported by
repository validation.

**QD-3 (Confirmed) — Admission and Raw Transcript are unaffected.** No quality signal refuses an
admission, refuses a Raw Transcript, or alters admission atomicity. Refusing would destroy the
provider evidence `§14` A-4 exists to preserve. Raw Transcript text is never deleted, edited,
trimmed, or rewritten on the strength of a diagnostic.

**QD-4 (Confirmed) — Derived after admission.** A diagnostic is computed from the **immutable**
admitted Raw Transcript and the preserved provider evidence. Computing it earlier would make
admission depend on interpretation.

### Provider evidence

**QD-5 (Confirmed) — Provider decode evidence is `§14` A-4 evidence.** It is a fact the provider
reported during one execution and cannot be recomputed from the transcript. It is **not** a
diagnostic, and the two never share a representation. Preserving it realizes `§4.2`'s released
obligation to produce "confidence 또는 Uncertainty", which the first slice left unmet.

**QD-6 (Confirmed) — Stored in `original_content`.** The submitted provider document may carry decode
evidence alongside each segment's timing and text, and A-4's `original_content` preserves it
un-normalized. `transcript_segments.confidence`/`uncertainty` are **not** used for it, no new
aggregate is introduced, and the diagnostics relation is not repurposed.

**QD-7 (Confirmed) — Window-derived evidence must declare its scope.** `avg_logprob`,
`no_speech_prob`, `compression_ratio` and `temperature` are decode-window values shared by several
segments. Whatever is stored must record that scope, and **nothing may present a window value as that
segment's own confidence**. Segment-scoped evidence, where a provider offers it, is recorded as
segment-scoped; the distinction is contract, not presentation.

**QD-8 (Confirmed) — Evidence does not join the fingerprint basis.** `content_fingerprint` stays
computed over the canonical admission payload — intake, provider, model, declared language,
provider-result reference, and each segment's timing and exact text. Decode evidence is preserved in
`original_content` but does not participate. Consequently a released fingerprint is **bit-identical**
before and after this contract, A-8 idempotency and A-9 conflict behaviour are unchanged, and two
runs whose text and timing agree remain the same logical result.

**QD-9 (Confirmed) — No new reference version, no backfill, legacy stays readable.** No
`provider_result_ref` version is minted (see the analysis above). Released Provider Results and Raw
Transcripts are **not** rewritten, re-derived, or back-filled with evidence, and a result recorded
without evidence remains fully valid and readable forever. A diagnostic over such a result reports
the provider-derived reasons as **unavailable** rather than absent-therefore-clean — the difference
is material and must be visible.

### Diagnostic

**QD-10 (Confirmed) — Derived, never persisted.** A diagnostic result is not stored. It is
deterministic from immutable inputs and a versioned algorithm, so storing it would duplicate
recomputable content and create the possibility of a stale diagnostic disagreeing with its own
inputs. It is not a canonical record, carries no Product identity, has no lifecycle, and no
downstream stage may consume it as content.

**QD-11 (Confirmed) — The algorithm is versioned even before thresholds exist.** A diagnostic
computation declares its algorithm kind, algorithm version, and provider-specific parameter version,
over an immutable anchor (the Provider Result and its Raw Transcript). The same inputs under the same
versions converge on the same result. This mirrors the released `§15` L-7/`PATCH-0040` P-3 idiom and
introduces no new identity mechanism.

**QD-12 (Confirmed) — Independent reasons, never a single score.** The reason vocabulary is fixed;
the thresholds are not:

| reason | evidence family | scope |
|---|---|---|
| `PROVIDER_LOW_CONFIDENCE` | decode confidence | decode window |
| `PROVIDER_HIGH_NO_SPEECH` | no-speech evidence | decode window |
| `PROVIDER_HIGH_COMPRESSION` | compression evidence | decode window |
| `PROVIDER_DECODE_FALLBACK` | decode fallback / temperature | decode window |
| `REPEATED_TEXT` | transcript sequence | transcript |

Each reason states its own ground and is independently explicable. **Combining them into one
hallucination score is prohibited**: the measured evidence shows two real utterances and one
fabrication sharing identical window values, so a score would assert a certainty the evidence cannot
support, and a person cannot act on a number they cannot decompose.

**QD-13 (Confirmed) — Several reasons may attach to one segment.** The fixture's clearest fabrication
fired four simultaneously, and that co-occurrence is itself the evidence a reader needs.

**QD-14 (Confirmed) — Thresholds are deferred, deliberately.** One lecture, two fixture regions and a
single hallucination cluster establish that the signals separate; they do not establish where to cut.
Even `temperature > 0`, which separated perfectly here, cannot be generalized from one cluster. This
contract fixes **signal availability, reason vocabulary and algorithm versioning**; the
provider-specific threshold parameter set is a later empirical PATCH with a broader corpus.

**QD-15 (Confirmed) — A finding names its anchor, its reason, and its evidence scope.** At minimum a
finding identifies the affected segment, the reason, the evidence family, and whether the evidence is
decode-window or transcript scoped. A window-scoped reason must never be readable as a claim about
that segment alone.

### Authority and downstream

**QD-16 (Confirmed) — No automatic deletion, no automatic correction.** A diagnostic never removes,
edits or rewrites transcript text, and never creates a Correction Candidate. Proposing a replacement
requires knowing what is correct, which a diagnostic does not know. False positives are acceptable
**precisely because** they can never act on their own; that acceptability is conditional on this
prohibition and disappears without it.

**QD-17 (Confirmed) — The correction path is the released one.**

```text
Raw Transcript → Quality Diagnostic → human inspection
              → §17 Correction Candidate admission → §18 Human Decision → §19 Corrected Revision
```

An Application-level convenience that carries a person from a finding into the released `§17`
boundary is permitted. **No new Human Authority is created**, and `§17`'s existing requirements —
current Raw Transcript, target segment membership, source-text snapshot match — are unchanged.

**QD-18 (Confirmed) — Downstream is not blocked, but is not hidden either.** A Raw Transcript with
quality warnings may be selected as effective, may produce subtitles, and may be published. No gate
is introduced at any boundary. But `§14`'s requirement that Uncertainty "정상 승인 결과처럼 숨기지
않아야 한다" binds: the diagnostic must be reachable as an observable boundary. How much of it any
interface displays is an Interface concern this contract does not decide.

**QD-19 (Confirmed) — `070` reassessed, split in two.** The assessment deferred canonical Diagnostic
persistence for want of "an executable consumer" and asked that it be revisited "using that consumer
as evidence". This consumer is now real, and the answer is **split**:

- **Provider evidence persistence: required.** It cannot be recomputed and A-4 already assigns it a
  home. QD-6 satisfies it inside the released representation.
- **Derived Diagnostic persistence: still deferred.** This consumer needs the *evidence*, not a
  Diagnostic row. QD-10 makes the diagnostic recomputable, so the assessment's own reasoning — do not
  freeze a record shape and retention policy without a consumer that needs it — still holds. Meeting
  the reopening condition does not oblige introducing the record.

**QD-20 (Confirmed) — No schema change, no `030` amendment.** `original_content` is an existing
column holding a canonical serialization; enriching what is serialized into it changes no relation,
column, constraint or migration. `docs/030_DATA_MODEL.md` describes the persistent structures, and
none of them change.

## Non-goals

Not decided and each requiring its own gate evaluation: threshold values for any signal; audio-aware
diagnostics; word-level `words`/`probability` evidence; automatic correction proposals; a diagnostic
interface; publication or export gating; thresholds for providers other than faster-whisper; a
canonical Diagnostic record; and every item already deferred by `PATCH-0040` L-14/L-16.

## Required Blueprint Changes

Applied to `docs/040_TRANSCRIPT_PIPELINE.md` only.

1. **Header** — Blueprint version and Last Updated advanced; `PATCH-0045` added to `Amended By`.
2. **§14 A-4** — released sentence kept verbatim; forward note recording that provider decode
   evidence is A-4 evidence and is preserved in `original_content` with its scope (QD-5…QD-7).
3. **§14 A-8** — released sentence kept verbatim; forward note recording that the fingerprint basis
   is the canonical admission payload and that decode evidence does not participate, so released
   fingerprints and A-9 conflict behaviour are unchanged (QD-8, QD-9).
4. **§14 or §15** — a new subsection carrying QD-1…QD-20 and its own Canonical Invariants.
5. **§4.2 / §4.3** — released text kept verbatim; forward note recording that the "confidence 또는
   Uncertainty" obligation is realized for this generation by QD-5…QD-7.
6. **§11** — released text kept verbatim; forward note recording that "낮은 confidence 또는
   Uncertainty가 있는 ASR 결과" is surfaced as a derived Quality Warning, not a Validation Failure.

`docs/030_DATA_MODEL.md` is not amended (QD-20). `070_DIAGNOSTIC_PERSISTENCE_ASSESSMENT.md` gains a
reassessment note recording QD-19's split outcome.

## PATCH Acceptance Criteria

Verified against the Blueprint amendment, before this PATCH may be marked `Accepted`.

- [ ] §14/§15 carry QD-1…QD-20 as written here.
- [ ] No released sentence in `docs/040` is deleted or rewritten; prior PATCH notes are treated as
      released text and are likewise untouched; verified line by line.
- [ ] A-4, A-8, §4.2, §4.3 and §11 gain **additive forward notes only**.
- [ ] The diagnostic is stated a Quality Warning and explicitly not a Validation Failure.
- [ ] Admission, Raw Transcript, and every downstream boundary are stated unblocked.
- [ ] Provider evidence and derived diagnostic are stated as distinct, never sharing a representation.
- [ ] Window-derived scope is stated, with the prohibition on presenting it as segment confidence.
- [ ] The fingerprint basis is stated unchanged and released records stated untouched and un-backfilled.
- [ ] Thresholds are stated deferred and **no numeric threshold appears anywhere**.
- [ ] `070` records the split reassessment: evidence persistence required, Diagnostic record still
      deferred.
- [ ] The change set contains no implementation, schema, migration, or test change.

## Implementation Requirements

Required validation for the implementing milestone. **Not satisfied by this PATCH.**

1. The adapter carries provider decode evidence from the engine to the `§14` document instead of
   discarding it, and the engine port stays provider-neutral in shape.
2. `original_content` preserves the evidence with its scope; `transcript_segments.confidence` and
   `uncertainty` are not written with window values.
3. `content_fingerprint` for a given text/timing payload is **bit-identical** to the released value —
   asserted against a record produced before this change.
4. A released Provider Result without evidence still loads, and a diagnostic over it reports
   provider-derived reasons as unavailable rather than clean.
5. Diagnostic results are computed on demand and stored nowhere; no table, column or row is added.
6. The same inputs and versions produce the same diagnostic; a version change produces a different
   one.
7. Each reason is emitted independently, several may attach to one segment, and no combined score
   exists anywhere in the code.
8. No code path deletes or edits transcript text, and none creates a Correction Candidate.
9. Admission, selection, subtitle generation and publication are unaffected by any warning.
10. Repository validation neither knows nor reports quality warnings.
11. Schema version is unchanged and the complete test suite passes.

## Consequences

- `§14`/`§15` gain a quality diagnostic contract; A-4, A-8, §4.2, §4.3 and §11 gain forward notes;
  nothing else moves.
- One implementation slice carries the evidence through and adds a derived diagnostic. **No schema
  change is expected.**
- Released records keep their fingerprints and identities exactly, gain no evidence, and stay valid.
- `§4.2`'s "confidence 또는 Uncertainty" obligation, unmet since the first slice, becomes met for new
  admissions.
- Hallucination is made **findable**, not removed. `PATCH-0040` P-9 stands unchanged.
