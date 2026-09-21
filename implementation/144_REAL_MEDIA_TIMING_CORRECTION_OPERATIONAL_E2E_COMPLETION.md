# Real-Media Timing Correction Operational E2E — Completion

- Status: Operational Verification Record — **continuation of `implementation/142`** (which is not
  rewritten or deleted; it recorded the PENDING HUMAN REVIEW state this record resumes from)
- Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` §15 TD, §17 K / TC-1…TC-21, §18, §19, §20;
  `docs/041_SUBTITLE_PIPELINE.md` §7, §16 — **all unchanged**
- Schema: unchanged (**v54**; no migration, no relation, no column)
- Production impact: **none** — no code change, no Blueprint change, no PATCH
- Related: `139`, `140`, `141`, `142`, `143`; `PATCH-0045`…`PATCH-0048`

## Summary

A person listened to 8 real diagnostic findings from MVI_0147 and recorded their judgement. Three
corrections went the whole way — candidate → decision → corrected revision → explicit selection →
corrected SRT — and the delivered subtitle moved by **22.11 seconds** with its text byte-identical.

Two findings matter more than the happy path:

1. **The diagnostic was right.** Human-measured start drift: **+22.11 s, +19.16 s, +6.00 s, +4.76 s**
   on the four segments a person judged mis-timed. Half the sample needed no correction at all.
2. **Only one correction can reach the SRT at a time.** Three accepted corrections became three
   sibling revisions, and `§20` selects exactly one. Measured, not argued.

One correction (R08) could not be admitted and is recorded as architecture evidence rather than
worked around.

## 1. Git preflight

```text
branch main, upstream origin/main, tracked clean
local HEAD == origin/main == 14bf15f, schema v54, migration chain unchanged
untracked: MVI_0144.MP4 (pre-existing); evaluation/ excluded via .git/info/exclude
```

## 2. Human review input

`evaluation/timing-correction-review/manifest_blind.csv`, filled by the person through the local
listening page, exported and returned. Integrity checked before use: review-id mapping intact,
**zero cells altered outside the four human-input columns**.

```text
ALIGNED   4   (R01, R02, R04, R07)   — no correction necessary
LATE      4   (R03, R05, R06, R08)   — start and end both supplied
EARLY     0        UNCLEAR  0        incomplete  0
```

The analysis manifest was opened only **after** the human result was read, and only for comparison.
No human value was moved toward a provider estimate at any point.

## 3. Review integrity — the diagnostic is confirmed

| | provider start | human start | drift | segment |
|---|---|---|---|---|
| R03 | 3365.78 | 3387.89 | **+22.11 s** | `너무 쉽지?` |
| R05 | 4254.86 | 4274.02 | **+19.16 s** | `얘들아 사전 잘 볼 줄 알죠?` |
| R06 | 4343.16 | 4349.16 | **+6.00 s** | `다 했나요?` |
| R08 | 6714.24 | 6719.00 | **+4.76 s** | `자 문제 술술술술술…` |

These agree independently with `131` §5's earlier approximate notes (~24 s, ~19 s) and are the first
measurements carrying an **end** boundary as well.

## 4. Canonical identity reconstruction

`implementation/143`'s `timing_correction_cli inspect` supplied intake identity, ordinal, canonical
interval and both neighbours for every row. **SQLite was never opened by hand** — `143`'s success
condition held under real use.

## 5. Candidate admission — first attempt refused all four

Submitted verbatim to the released admission service, which is the authority:

```text
R03 / R05 / R06 / R08
  error: proposed interval ends after the next segment starts
         (an overlapping correction cannot be delivered as a subtitle)
```

Cause, measured per row:

| | human end | next segment starts | overshoot | next segment |
|---|---|---|---|---|
| R03 | 3390.26 | 3389.58 | +0.68 s | `대답이 없네` (2.60 s) |
| R05 | 4276.35 | 4275.58 | +0.77 s | `네` (0.56 s) |
| R06 | 4350.99 | 4350.82 | +0.17 s | `다 선생님이 말한 거…` (2.28 s) |
| R08 | 6722.66 | 6721.08 | +1.58 s | `네` (0.12 s) |

A consistent shape: the drifted utterance is immediately followed by a short reply, and the
listener's end marking crossed into it. TC-7 refused correctly — `READABILITY_CUES_OVERLAP` is
BLOCKING and `PATCH-0042` enforces it at Final Selection, so an overlapping correction would be
admitted, accepted, generated and then refused delivery.

**This was partly a packaging failure, and it is classified as ours.** The blind manifest carried
`next_segment_start_seconds` as a column but neither the README nor the listening page ever told the
listener it was a *bound*. The constraint was in the data and absent from the instructions. The page
was then corrected to display the bound and warn on violation.

## 6. Human decision

The person revised the end values themselves, in conversation, after being shown each bound. The
agent proposed no value and filled nothing in.

```text
R03  end → 3389.58   (touching the neighbour; explicitly chosen over keeping 3390.21)
R05  end → 4275.58   ("땡겨도 될 거 같은데")
R06  end → 4350.52   (within bound on the listener's own re-judgement)
R08  withheld — see §8
```

`§18` ACCEPT was then recorded through the released decision service for the three admitted
candidates. This is **Path A** of the task's gate, and the basis is specific rather than convenient:
the person did not merely annotate a clip, they were shown the admissible range and stated the
interval they wanted applied. That is the act H-1 describes. No new Human Authority concept was
introduced, and no annotation was silently promoted.

## 7. Corrected revision generation

```text
R03  candidate abae936c…  → revision …894dc90b
R05  candidate 9b4db178…  → revision …8e50eda7
R06  candidate 78b38e1c…  → revision …8fc201f1
```

Each verified: 2,370 segments in the snapshot, exactly **one** corrected segment, replacement text
**byte-identical** to the source, `replaces_segment_id` correct, `parent_raw_transcript_id` set and
`parent_revision_id` `None` (no chaining), and the Raw Transcript's source segment unchanged —
`[3365.78, 3389.58] '너무 쉽지?'` still reads exactly that after generation.

## 8. Multi-correction reality check — the session's main finding

**Three accepted timing corrections cannot be delivered together.** Measured three ways:

```text
code      generate(self, *, candidate_id: str)        — exactly one candidate
record    each revision contains 1 / 3 corrected segments
selection CorrectedRevisionSelection.corrected_revision_id is a single nullable under a CHECK
executed  select R03 → current = …894dc90b
          select R05 → outcome "changed", current = …8e50eda7
          R03's correction is no longer in the effective transcript
```

`§19` V-2 states it plainly: *"생성은 정확히 하나의 후보를 지명하는 명시적 요청이다.
apply-all/best/latest·암묵적 후보 발견·multiple-candidate merge·ranking·overlap 해소는 없다."*
V-14 defers multi-candidate application; S2-14 defers multi-candidate revisions.

**Classification: Expected Deferred Behaviour.** The contract says this, deliberately, and nothing
was invented to route around it. What is new is that it is no longer hypothetical: **one lecture
produced three corrections a person wanted, and the released model can deliver one.** At `137`'s
~8 material cases per lecture, that gap is operationally significant.

This is a *same-kind aggregate* question, distinct from `PATCH-0048`'s text+timing composition. The
composition gate is not moved by it.

### R08 — a second, different kind of blocker

R08's end could not be brought inside its bound, because the person reports **the blocking neighbour
is not audible**: segment 2223 is `네` spanning `[6721.08, 6721.20]` — 0.12 s — and the listener heard
no speech there at all. Capping R08 at 6721.08 would mean truncating a real utterance at a boundary
the listener believes is spurious.

Verified that no ordering helps: a corrected revision never mutates the Raw Transcript, so correcting
segment 2223 first would still leave R08's candidate comparing against the original `[6721.08, …]`.
The pair is not correctable under the released contract.

**Classification: Deferred Architecture Evidence**, plus a possible **content** issue (a 0.12 s `네`
that a listener does not hear is what `PATCH-0045`'s hallucination diagnostic exists to surface).
R08 was left unadmitted. No candidate was created for it.

## 9. Final selection

Explicit, through the released `§20` service. Never automatic — generation left `corrected_revision_selections`
untouched until a selection was commanded. Selection treated the timing revision exactly like any
other: no special-casing, no merge, and switching selections superseded only the previous *selection*
authority while both revisions remained intact (S2-13).

## 10. Corrected SRT

```text
before  Raw fallback         artifact …e0e7181e6a   sha256 32ccb362…   190,960 bytes
after   R03 revision selected artifact …3f3c31a1a7   sha256 b9d92573…   190,960 bytes

cue count   2,370 → 2,370
cues changed  1

  cue #1135   before  00:56:05,780 --> 00:56:29,580   너무 쉽지?
              after   00:56:27,890 --> 00:56:29,580   너무 쉽지?
              text identical: True
  cue #1134 unchanged      cue #1136 unchanged
```

Exactly one cue moved, by 22.11 s, with its text byte-identical and both neighbours untouched. No
hidden retiming: the cue's start equals the revision segment's start, value for value.

Readability delta:

```text
findings   1,654 → 1,653      blocking   626 → 626  (unchanged)
READABILITY_DURATION_ABOVE_MAXIMUM   111 → 110   (−1)
every other code unchanged
```

The correction removed exactly the over-long-cue warning it should have — the 23.80 s cue became
1.69 s — and introduced no blocking finding.

## 11. Artifact immutability

```text
previous artifact bytes on disk unchanged: True
artifact identity differs:                 True
materialized path differs:                 True
```

Nothing was overwritten, nothing auto-regenerated, and the released artifact stayed valid as the
output of the revision selected when it was made (TC-17).

## 12. Human-verified timing references — now real

Reconstructed from **released relations only**, single join, no calibration table:

| | provider | human | Δstart | Δend | Δduration |
|---|---|---|---|---|---|
| R03 | [3365.78, 3389.58] | [3387.89, 3389.58] | +22.11 | −0.00 | −22.11 |
| R05 | [4254.86, 4275.58] | [4274.02, 4275.58] | +19.16 | +0.00 | −19.16 |
| R06 | [4343.16, 4349.88] | [4349.16, 4350.52] | +6.00 | +0.64 | −5.36 |

Each row carries its candidate author, decision reviewer, decision identity, corrected revision,
media fingerprint (`sha256:19aa01b5…`) and provider reference (`faster-whisper`). `PATCH-0047`
TC-21's side effect is now an actual dataset: **provider timing vs human timing is directly
comparable per segment.** Three references from one lecture — enough to prove the path, far too few
to evaluate any refinement mechanism.

## 13. Quantitative summary

```text
reviewed              8
ALIGNED               4      LATE 4      EARLY 0      UNCLEAR 0      incomplete 0
candidates created    3      admissions refused 4 (first pass) + 1 withheld (R08)
accepted decisions    3      rejected decisions 0
revisions generated   3      simultaneously deliverable 1
SRTs generated        1
```

Start deltas `+22.11 / +19.16 / +6.00` seconds. **These are evaluation evidence and are not promoted
to any product threshold.** Eight findings from one lecture, selected to span the anchor-gap range,
are not a population.

## 14. Diagnostic review yield

**4 of 8 reviewed findings needed correction.** This is a *review correction yield*, not precision:
the eight were deliberately sampled across large and small anchor gaps and included two previously
human-observed cases, so the selection is biased by construction and recall is not computable from it.

No threshold is proposed or changed. The four ALIGNED outcomes are exactly what `PATCH-0046` TD-2
anticipated — the diagnostic claims *review-worthy*, never *drift confirmed*.

## 15. Composition evidence

**Zero** reviewed source segments carry an existing accepted text correction. `PATCH-0048`'s
composition gate stays **`MORE_EVIDENCE_REQUIRED`** and is not moved.

One adjacent observation, recorded and not acted on: R05's and R08's blocking neighbours are 0.56 s
and 0.12 s `네` segments, and the listener reports not hearing R08's. If such a segment later needs a
text correction *and* its neighbour needs a timing correction, that is the concrete case `140` CC-8
is waiting for. It has not happened yet.

## 16. Operational tooling validation (`143`)

| question | answer |
|---|---|
| SQLite opened by hand? | **No**, not once |
| diagnostic → inspect identity bridge | **Sufficient** |
| human values → admit copy/paste | **Yes** |
| float precision problems | **None** — `3389.5800000000004` carried through exactly |
| candidate ID → decide → generate | **Yes**, uninterrupted |
| batch absence a blocker at 8? | No, but three corrections took three full loops |
| inspect reusable for text correction | Yes incidentally — it prints the text snapshot too |

`143` held up under real use. The gap that actually hurt was in the **evaluation package**, not the
production tooling.

## 17. Defects and gaps

| finding | classification |
|---|---|
| TC-7 refusing all four first-pass proposals | **Expected Released Behaviour** — correct, and for a delivery reason |
| Review package never surfaced the neighbour bound to the listener | **Operational Tooling Gap** (evaluation package; fixed this session) |
| Three accepted corrections, one deliverable | **Expected Deferred Behaviour** (V-2, V-14, S2-14) — now with concrete operational evidence |
| R08 blocked by a neighbour the listener cannot hear | **Deferred Architecture Evidence**, and a candidate content issue for the `PATCH-0045` diagnostic |

No Implementation Defect, no Blueprint Gap, no Product Decision required. No Stop Condition forced a
workaround: composition, chaining, latest-wins, multi-candidate generation and selection merge were
all left untouched.

## 18. Schema / migration

`SQLITE_SCHEMA_VERSION` **54**, no migration, no relation, no column, no index. The E2E ran on a
**copy** of the preserved measurement repository, migrated v53 → v54 through the released single-step
path; the original evaluation artifact is untouched (mtime unchanged since 2026-08-21).

## 19. Validation

```text
repository validator      healthy, 0 diagnostics, schema_version 54
                          (after 3 candidates, 3 decisions, 3 revisions, 3 selections)
production code changed   none — no test run was required by a change
tracked working tree      clean
docs/ and patches/        0 changes
```

## 20. Repository impact

No production, test, schema, `docs/` or `patches/` change. The review package — audio clips, the
human manifest, the analysis manifest, the local page and server, the E2E database — all live under
`evaluation/`, which git excludes. This report records identities, aggregate counts and provenance;
the few transcript fragments quoted are the minimum needed to make the finding legible.

## 21. Remaining risks

- **Three references is not a dataset.** They prove the path, not any drift distribution.
- **The end boundary remains the hard part.** All four listeners' end marks crossed the neighbour on
  first pass. R03's final value (3389.58) is a *bound*, not what the person heard — they judged
  3390.21 and accepted the truncation to make the correction deliverable. That compromise is recorded
  here rather than hidden in the data.
- **R08 is unfixable under the current contract** and remains uncorrected.
- **One-at-a-time delivery is the real operational ceiling.** A lecture needing eight corrections can
  ship one. Nothing in this session changes that, and nothing should until it is decided.
- **The E2E database is scratch.** It is not the canonical production repository and was never
  intended to be; the three references live only there.

## 22. Result

```text
Human review rows: 8     ALIGNED: 4   LATE: 4   EARLY: 0   UNKNOWN: 0   Incomplete: 0

Timing candidates created:               3
Candidate admissions rejected:           4 first-pass (TC-7 neighbour overlap); 1 withheld (R08)

Human decisions created: 3               Accepted: 3     Rejected: 0

Corrected revisions generated:           3
Multiple accepted timing corrections
  on one Raw Transcript:                 Yes — 3

Can released architecture represent all
  accepted timing corrections in one
  selected revision:                     No — V-2 forbids multi-candidate application, §20 holds
                                         one revision. Measured by selecting R05 and watching R03's
                                         correction leave the effective transcript.
                                         Expected Deferred Behaviour (V-14 / S2-14)

Corrected revision selected:             1 (explicit, §20)
Corrected SRT generated:                 1 — cue #1135 moved 00:56:05,780 → 00:56:27,890,
                                         text byte-identical, neighbours unchanged

Existing SRT overwritten:                No — previous bytes verified unchanged
Raw Transcript changed:                  No
Existing artifacts changed:              No

Human-verified timing references:        3
Provider vs human timing comparison:     Yes — single join over released relations, executed

Diagnostic review correction yield:      4 / 8
Formal precision claimed:                No — the sample is deliberately biased

Existing accepted text + timing overlap: 0
Composition decision gate:               MORE_EVIDENCE_REQUIRED (unchanged)

SQLite required:                         No
Operational tooling sufficient:          Production (143) yes; the evaluation package omitted the
                                         TC-7 bound and was corrected

Automatic timing proposal: None     Automatic decision: None
Automatic composition:     None     Revision chaining:  None

Schema: v54 (unchanged)             Migration: None
Tests: no production change, so no new tests; repository validator healthy
Working tree: clean                 Remote push: this report only

Requires Architect Decision:             Not yet — but the one-deliverable-correction ceiling is now
                                         evidenced and is the natural next decision
Requires Blueprint Clarification:        No
Requires Blueprint PATCH:                No
Requires Schema Change:                  No
Requires Migration:                      No
Requires additional human review:        Optional — R08, and more lectures if references are wanted
Requires additional measurement:         No
```
