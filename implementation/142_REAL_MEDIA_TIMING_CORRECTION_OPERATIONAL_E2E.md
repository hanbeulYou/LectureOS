# Real-Media Timing Correction Operational E2E — PENDING HUMAN REVIEW

- Status: Operational Verification Record — **PENDING HUMAN REVIEW**
- Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` §15 TD-1…TD-20, §17 K-1…K-14 / TC-1…TC-21, §18, §19,
  §20; `docs/041_SUBTITLE_PIPELINE.md` §7, §16
- Production impact: **none** — no code change, no schema change, no Blueprint change, no PATCH
- Related: `135`, `137`, `139`, `140`, `141`; `PATCH-0045`…`PATCH-0048`

## Summary

The released timing diagnostic was run against **real lecture media** (MVI_0147, 1.96 h, 2,370
segments) and reproduced its recorded result exactly. A blind human review package for **8 findings**
with real audio clips was produced.

The session then stopped at the human boundary, deliberately. **No human-verified timing interval
exists in this repository**, so no timing correction candidate could be authored without the agent
inventing the value — which `PATCH-0047` TC-4 forbids and which is Stop Condition #1. This is
**Path B** of the task's own two outcomes, and it is not a failure.

Everything that does not depend on human listening was completed: workflow mapping, diagnostic
reproduction, review-package construction, refinement-reference reconstructability proof, and the
operational usability assessment — which found **two tooling gaps that would block a real operator**.

## 1. Git preflight

```text
branch main, upstream origin/main, tracked working tree clean
local HEAD == origin/main == 13444df
schema SQLITE_SCHEMA_VERSION = 54, migration chain unchanged
untracked: MVI_0144.MP4 (pre-existing input media, untouched)
```

Matches the stated baseline. No divergence, no unexpected tracked modification.

## 2. Repository investigation

Read `§4.2`, `§4.3`, `§14` A-10, `§15` QD/TD, `§17` K-1…K-14 and TC-1…TC-21 with the `PATCH-0048`
correction note, `§18`, `§19`, `§20`, `§21`, and `041` §7/§16. `PATCH-0045`…`PATCH-0048`.
Implementation reports `135`, `137`, `139`, `140`, `141` (actual filenames confirmed; the latest is
`141`, not a higher number).

## 3. Released workflow mapping

Traced in code end to end. Every arrow below is an **explicit** operation — nothing advances on its own.

| stage | input identity | output identity | persisted | human authority |
|---|---|---|---|---|
| Timing Diagnostic | `ProviderTranscriptAdmissionId` | findings (in memory) | **No** (TD-10) | — |
| Timing Candidate | intake + `TranscriptSegmentId` + **human interval** | `timing-correction-candidate:…` | Yes | **authoring** (TC-4) |
| Human Decision | candidate id | `timing-correction-candidate-decision:…` | Yes | **accept/reject** (H-1) |
| Revision Generation | candidate id | `corrected-revision:…` + replacement segment | Yes | explicit request (V-2) |
| Revision Selection | revision id | `corrected-revision-selection:…` | Yes | **explicit** (S2-3) |
| Subtitle → SRT → Materialization | selection | candidate → subject → final selection → artifact → file | Yes | review + final selection |

**Raw Transcript is never written after admission** at any stage. The finding→candidate arrow does
not exist in code: the admission module imports no diagnostic module and names no reason constant —
asserted by released tests (`139`).

## 4. Real-media timing diagnostic

Run against the preserved MVI_0147 measurement repository, on a scratch copy so the evaluation
artifact was not mutated.

```text
lecture              MVI_0147 (media sha256:19aa01b5…, 29 GB, present)
segments             2,370
decode anchors       available — 252 windows
completeness         complete
findings             31   TIMING_ALIGNMENT_REVIEW_REQUIRED, segment scope
ordinal set          identical to the recorded measurement (31/31, no extras, none missing)
```

Contract properties observed in the live output: the reason is the single released one; every finding
is segment-scoped; the CLI prints the anchor instant but **no drift magnitude**; and the output closes
by stating the result is "a structure worth reviewing, not confirmed drift". P1 alone fires on 251 of
251 windows and produces no warning — only the conjunction with a positive gap does, at 31 of 2,370
(1.31 %). No numeric cut beyond the released `PATCH-0039` ε participates.

## 5. Human review boundary — why this stopped here

The task allows two outcomes. This is **Path B**, and the reason is specific rather than procedural.

**The only human timing records in the repository are five approximate lateness notes** (`131` §5):

```text
S05 전사 3727.8s  실제 발화 ~24s 늦게      S12 전사 4264.7s  ~10s 늦게
S10 전사 3362.2s  ~27s 늦게                S13 전사 4324.7s  ~24s 늦게
S11 전사 3419.6s  ~7s 늦게
```

These cannot become proposed intervals, for three independent reasons:

1. **They are magnitudes, not instants.** "~24 s late" is an observation about lateness, not a
   verified onset time.
2. **No end boundary was ever recorded.** TC-3 requires a **complete** replacement interval, because
   a start-only proposal silently redefines duration and duration is what `041` readability measures.
3. **They are explicitly approximate.** `137` §2 recorded that the human figures were themselves
   approximate and that individual drift values are not reliable.

Converting them — or any energy estimate, anchor gap, or decode-window position — into a proposed
interval would be the agent authoring the human's judgement. TC-4 admits only human-authored
proposals; TC-5 forbids a finding becoming a candidate. **The boundary was not automated around.**

### The package produced instead

`evaluation/timing-correction-review/` — 8 of the 31 findings, chosen to span the range:

| review | ordinal | provider interval | duration | selection basis |
|---|---|---|---|---|
| R01 | 423 | [1380.74, 1382.24] | 1.50 s | small anchor gap |
| R02 | 440 | [1410.74, 1414.86] | 4.12 s | small anchor gap |
| R03 | 1134 | [3365.78, 3389.58] | 23.80 s | previously human-observed |
| R04 | 1143 | [3425.78, 3430.78] | 5.00 s | large anchor gap |
| R05 | 1350 | [4254.86, 4275.58] | 20.72 s | large anchor gap |
| R06 | 1355 | [4343.16, 4349.88] | 6.72 s | previously human-observed |
| R07 | 1677 | [5301.26, 5303.88] | 2.62 s | small anchor gap |
| R08 | 2222 | [6714.24, 6721.08] | 6.84 s | large anchor gap |

Eight is this session's review workload, **not a product threshold**.

Each case has an mp3 cut from the real media covering **8 s before the claimed start to 12 s after the
claimed end**, so the listener can judge both boundaries — TC-3 needs both.

**Blind and analysis views are separated.** `manifest_blind.csv` carries only what a listener needs:
clip, claimed interval, its offset inside the clip, the transcript text, and the neighbouring
segments' boundaries (which bound any admissible proposal under TC-7). It carries **no** anchor gap,
no P1/P2, no decode-window data, no prior drift estimate, and no selection reason.
`manifest_analysis.csv` holds those separately, with instructions not to open it before listening.

The two previously human-observed cases (R03, R06) were both labelled **REAL_SPEECH** in the earlier
content labelling — the text is right and only the timing is in question. Including them tests
whether a person confirms the source timing, which TC-11 makes a complete and normal outcome.

## 6. Timing correction E2E — not executed on real media

No candidate was authored, no decision recorded, no revision generated, no selection made, and no SRT
produced **from real media**, because step one requires a human interval that does not exist.

The same path is exercised end to end by released tests against a real released chain (`139`): the SRT
timestamp moves `00:00:10,000 --> 00:00:20,000` → `00:00:18,000 --> 00:00:24,000` with cue text
byte-identical, untouched cues unchanged, the released artifact's bytes unchanged on disk, and a new
artifact under a new identity. Those tests pass in this session's validation. **What is unverified is
the operational path with a real person's judgement, not the mechanism.**

## 7. Operational usability — two gaps that would block an operator

The mechanism works; the operator experience has holes. Classified per the task's taxonomy.

**Q1 — steps to correct one finding.** Run the diagnostic → read the segment identity and anchor →
locate that position in the media → listen → decide the interval → read the segment's *current*
start/end → write a JSON proposal → `admit` → `decide` → `generate` → `select-revision` → regenerate
the subtitle chain. Eleven steps, four of them CLI invocations.

**Q2/Q3 — can an operator do this with released tooling alone? No.**

> **Gap 1 — Operational Tooling Gap: no released command exposes a segment's persisted start/end.**
> Authoring a candidate requires `source_start_snapshot` and `source_end_snapshot` to match the
> persisted segment **exactly** (TC-9). No CLI prints them. `transcript_quality_cli inspect` reports
> evidence coverage and contains no timing at all; `timing` reports the decode anchor, which is *not*
> the segment's start; `timing_correction_cli list` shows the snapshot only after a candidate already
> exists. An operator must query SQLite directly — which is precisely the kind of hand-written access
> the CLI layer exists to remove. This blocks the workflow in practice.

> **Gap 2 — Operational Tooling Gap: the diagnostic and the correction path key on different
> identities.** `transcript_quality_cli timing` takes a `ProviderTranscriptAdmissionId`;
> `timing_correction_cli admit` takes an intake id plus a raw-transcript id. Neither prints the other,
> so the operator must translate. Minor next to Gap 1, but real.

**Q4 — can a person connect a finding to the audio? Yes.** The diagnostic prints the anchor instant
in seconds, which is directly seekable in the media. This session's package relies on exactly that.

**Q5 — is reject cheap? Yes.** One `decide --kind reject` invocation, and the CLI prints that reject
is a normal outcome recording that the source timing is correct. No state is invented (TC-11).

**Q6 — is repetition excessive? Yes, at scale.** Eight findings needed eight audio cuts and eight
manifest rows, all scripted by hand here. At ~8 material cases per lecture-hour (`137`) an operator
faces the eleven-step loop repeatedly with no batch surface. This is a tooling observation, not a
contract problem.

**None of these are Blueprint gaps or defects.** The contracts say what they should; the operator
surface is thin. No UI was designed, per scope.

## 8. Refinement reference readiness — proven

The reference a future refinement evaluation needs is reconstructable from **released relations only**,
with a single join and no new schema. Demonstrated by executing the query against a repository built
through the released chain:

```text
source segment          transcript-segment:a4cd6712…:1
provider_start/end      10.0 / 20.0          ← Raw Transcript, immutable
human_start/end         18.0 / 24.0          ← timing_correction_candidates
candidate author        human:editor-1        decision reviewer  human:editor-1
decision identity       timing-correction-candidate-decision:7a2b8698…
corrected revision      corrected-revision:f0d04abf…
media fingerprint       sha256:7be6a958…      provider reference  fake-asr
preserved provider decode evidence            present in original_content
```

So `provider timing vs human corrected timing` is directly comparable per segment, carrying its
decision provenance and its media fingerprint. **No calibration schema is needed**, matching
`PATCH-0047` TC-21's statement that accumulated corrections become reference evidence as a side effect
rather than a purpose.

Two limits worth stating: the **diagnostic reason is not persisted** (TD-10) and must be re-derived at
read time from the preserved evidence — which is possible, as §4 shows; and **instructor provenance is
not a released field**, so only the media fingerprint identifies the lecture.

No refinement mechanism was run. VAD, forced alignment, word timestamps and energy detection remain
Deferred (`PATCH-0047` TC-21), and `136` TR-4's rule stands: no mechanism before **both** L-16
conditions are measured.

## 9. Composition evidence

**Zero cases** in this operational set require both a text and a timing correction on one segment. The
8 selected findings are timing-only by construction, and the two carrying a prior content label were
both **REAL_SPEECH** — text correct, timing in question.

Per `PATCH-0048` RC-5 this is recorded as **absence evidence only**. The composition decision gate
stays **`MORE_EVIDENCE_REQUIRED`** and is not moved. Should the human review surface a case needing
both, the two corrections must remain sibling revisions — no composition, no chaining — and that case
becomes concrete evidence for reopening the `140` CC-8 decision, not a reason to write a PATCH.

## 10. Defects and gaps

| finding | classification |
|---|---|
| No CLI exposes a segment's persisted start/end (Gap 1) | **Operational Tooling Gap** |
| Diagnostic and correction key on different identities (Gap 2) | **Operational Tooling Gap** |
| Measurement repository has no current Raw Transcript selection, so K-1 readiness fails there | **Expected Released Behaviour** — it was built for read-only diagnostics; a selection must be recorded before any candidate can be admitted |
| Diagnostic is not persisted, so a finding cannot be cited by identity later | **Expected Released Behaviour** (TD-10), re-derivable |

**No Implementation Defect, no Blueprint Gap, and no Product Decision** was found. Nothing required a
Blueprint change, schema change, migration, composition, chaining, automatic proposal, new threshold,
or audio inference — so no Stop Condition was hit other than the intended human boundary.

## 11. Validation

```text
timing diagnostic focused                    OK
timing correction admission / decision /
  generation / downstream E2E                OK
corrected revision selection                 OK
readable cue composition / selection
  enforcement / subtitle generation /
  SRT artifact / materialization             OK
replacement-segment guard                    OK
v54 migration                                OK
complete suite                     3,680 tests   OK
git diff --check                             clean
tracked working tree                         0 modifications
SQLITE_SCHEMA_VERSION                        54 (unchanged)
migrations added                             0
```

## 12. Repository impact

No production, test, schema, `docs/` or `patches/` change. The review package lives under
`evaluation/`, which `.git/info/exclude` keeps out of git — so the lecture audio and transcript text
are not committed, following the established convention. This report records identities, aggregate
counts and provenance only; no classroom speech content beyond the eight short transcript strings
already needed to describe the selection, and none of those appear here.

The MVI_0147 measurement repository was **copied** to scratch before the diagnostic ran; the
evaluation artifact itself is byte-unchanged.

## 13. Remaining risks

- **The operational path is unverified with a real person.** The mechanism is test-verified; the
  eleven-step loop has never been walked by an operator. Gap 1 in particular may make it impractical
  before it makes it wrong.
- **The measurement repository cannot host the correction.** It has no current Raw Transcript
  selection, so when the human intervals arrive, a selection must first be recorded — a released
  operation, but one that writes to an evaluation artifact. That write should go to a copy, not to the
  preserved measurement DB.
- **Eight clips are a sample, not the population.** Whatever the human concludes describes these eight,
  not the 31 and certainly not the corpus.
- **Media lives outside the repository** (`~/Desktop/MVI_0147.MP4`). If it moves, the clips remain but
  new ones cannot be cut and the absolute-second mapping cannot be re-derived.

## 14. What the human needs to do

Fill `evaluation/timing-correction-review/manifest_blind.csv`:

```text
verdict                      ALIGNED | LATE | EARLY | UNCLEAR
human_speech_start_seconds   absolute seconds in the media
human_speech_end_seconds     absolute seconds in the media   ← required by TC-3, not optional
note                         free text
```

`ALIGNED` needs no times and is a complete, expected answer — roughly half the population is expected
to be dismissed (`137`). Listen before opening `manifest_analysis.csv`.

When the file comes back, the remaining session is short: admit each supplied interval, decide,
generate for accepted ones, select explicitly, and regenerate the subtitle chain to a corrected SRT —
comparing cue text, timings, neighbours and readability findings before and after, and confirming the
released artifact is untouched.

## 15. Result

```text
Operational E2E:                         PENDING HUMAN REVIEW (Path B)
Timing findings reviewed by human:       0 — package prepared, listening not yet done
Timing candidates created:               0
Accepted:                                0
Rejected:                                0
Corrected revisions generated:           0
Corrected revisions selected:            0
Corrected SRT generated:                 0 (from real media; test-level E2E passes)
Existing SRT overwritten:                No
Raw Transcript changed:                  No
Automatic timing proposal:               None — refused at the human boundary
Text+timing composition:                 None
Revision chaining:                       None
Human-verified timing references
  available:                             0 — the five recorded notes are approximate lateness
                                         magnitudes with no end boundary, unusable under TC-3/TC-4
Refinement evaluation ready:             Yes, structurally — provider vs human timing is a single
                                         join over released relations, proven by execution; awaiting data
Composition decision gate:               MORE_EVIDENCE_REQUIRED (unchanged; 0 cases observed)
Schema:                                  v54 (unchanged)
Migration:                               None
Tests:                                   3,680 passing
Working tree:                            clean (untracked MVI_0144.MP4 pre-existing)
Remote push:                             this report only

Requires Architect Decision:             No
Requires Blueprint Clarification:        No
Requires Blueprint PATCH:                No
Requires Schema Change:                  No
Requires Migration:                      No
Requires additional human review:        Yes — 8 clips, both boundaries per case (§14)
Requires additional measurement:         No new measurement; the two Operational Tooling Gaps in §7
                                         are candidates for their own tooling milestone
```
