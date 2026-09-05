# Timing Correction Operational Tooling

- Status: Implementation Reference (operational tooling)
- Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` §15 TD, §17 K-1 / TC-1…TC-21 — **all unchanged**
- Schema: unchanged (**v54**; no migration, no table, no column, no index)
- Related: `139`, `140`, `141`, `142` §7; `PATCH-0046`, `PATCH-0047`, `PATCH-0048`

## What this is

`implementation/142` found two Operational Tooling Gaps that made the released timing-correction
workflow unusable without opening SQLite by hand. Both are closed by **one read-only subcommand** and
**one lineage query method**. No contract, semantics, schema, or service behaviour changed.

## 1. Git preflight

```text
branch main, upstream origin/main, tracked working tree clean
local HEAD == origin/main == d5d9463, schema v54, migration chain unchanged
untracked: MVI_0144.MP4 (pre-existing); evaluation/ excluded via .git/info/exclude
```

Matches the stated baseline.

## 2. Gap reproduction — verified against the current CLI, not assumed

**Gap A.** `timing_correction_cli admit` requires nine fields. The diagnostic supplies two of them
(`segment_id`, and `raw_transcript_id` from its header). It does **not** supply
`source_start_snapshot` / `source_end_snapshot`, and **no released command printed a segment's
persisted interval**:

- `transcript_quality_cli inspect` — evidence coverage only; zero lines mention timing;
- `transcript_quality_cli timing` — prints the decode-window **anchor**, which is not the segment's
  start, and never an end;
- `timing_correction_cli list` — shows the snapshot only *after* a candidate exists;
- `corrected_revision_cli show` — prints segment intervals, but of a **corrected revision**, which
  does not exist before any correction has been made.

TC-9 makes the snapshot caller-supplied, so this blocked the workflow outright.

**Gap B.** The diagnostic keys on `ProviderTranscriptAdmissionId` while `admit` needs an intake id
plus a raw transcript id. The raw transcript **was** already printed by the diagnostic — so that half
was not a gap. The **intake identity was**: no CLI in the loop printed it, and
`transcript_intake_cli` has no listing subcommand.

## 3. Classification — **A. Operational Tooling Gap** (both)

The released contracts already say everything needed: K-1 defines membership, TC-9 makes the snapshot
caller-supplied, and the provider admission relation binds a Raw Transcript to its intake under
`UNIQUE (raw_transcript_id)`. Only the CLI surface was missing. **No Implementation Defect, no
Blueprint Gap, no Product Decision** — so no Blueprint, PATCH, or schema change.

## 4. Architecture

No new domain service, no new persistence field, no new schema, no new state.

- **CLI: thin orchestration.** `_run_inspect` opens the repository, reads two released repositories,
  and formats. It performs **no admission judgement** — K-1 lineage, TC-7 adjacency, TC-8 no-op, TC-9
  staleness and Human Authority all stay with the admission service, and a test drives a no-op through
  the service to prove the CLI taught the rule to nobody.
- **One read-model addition:** `SQLiteProviderTranscriptAdmissionRepository.get_by_raw_transcript`,
  mirroring the released `SQLiteCorrectedRevisionGenerationRepository.get_by_revision` idiom including
  its "well-defined: the schema enforces UNIQUE" reasoning. It is a lineage read over a released
  relation and introduces no meaning.

One judgement call, recorded rather than hidden: **inspect refuses a segment that is not in the Raw
Transcript's canonical membership.** That is not a re-implementation of K-1 — it is a truthfulness
requirement. Describing a corrected revision's replacement segment as "segment 1350 of this Raw
Transcript" would be reporting the canonical state falsely, and a person would then author a proposal
that admission (and `141`'s guard) refuses.

## 5. Implementation

```text
timing_correction_cli inspect --raw-transcript <id> --segment <id> --database <db>
                              [--format text|json]
```

Reports: intake identity, raw transcript identity, segment identity, **ordinal and membership size**,
text, **current interval**, and both neighbours' identities and intervals. `--format json` follows the
repository's existing `validate_cli` convention.

Deliberately **not** reported: the diagnostic reason, the decode anchor, any gap, and any estimate.
The operator already has the reason from `transcript_quality_cli timing`, and keeping inspect to pure
canonical state preserves the TD-10 / TC-5 separation — the diagnostic is a cue, never a proposal.

**Precision.** `json.dumps` renders floats with `repr`, so values round-trip exactly. A test carries
`4276.139999999999` through the JSON output and back; another carries inspect's output straight into
`admit` and asserts admission accepts it, which is the command's entire reason for existing. No
rounding policy was invented.

**The snapshot is not auto-filled.** TC-9 makes it the person's assertion of what they were looking
at; capturing it inside the service would make the stale check vacuous. Inspect prints the values to
carry; `admit` still receives them from the caller. The contract is exposed, not hidden.

## 6. Contract preservation

| contract | relationship |
|---|---|
| **K-1** | unchanged; inspect reports membership truthfully and refuses non-members |
| **TC-4 / TC-5** | unchanged; inspect proposes no interval, names no diagnostic, and offers no `--suggest`/`--auto`/`--estimate`/`--propose` flag — asserted by source-level tests |
| **TC-7 / TC-8 / TC-9** | unchanged; enforced only by the admission service, proven by driving a no-op through it |
| **TD-10** | unchanged; no finding is persisted and no finding identity is invented |
| **§18 / §19 / §20** | untouched; `decide` and `generate` already sufficed, so no wrapper was added |
| **`PATCH-0048`** | composition gate unmoved; no composition, no chaining |
| **`141` guard** | complementary — inspect refuses the same target earlier, admission still refuses it |

## 7. Operational workflow after the fix

```text
1  transcript_quality_cli timing   --admission <id>      → raw transcript id + segment ids
2  timing_correction_cli inspect   --raw-transcript --segment
                                                          → intake id + current interval + neighbours
3  (human listens to the media externally and decides both boundaries)
4  timing_correction_cli admit     --intake --input proposal.json
5  timing_correction_cli decide    --candidate --kind accept|reject
6  timing_correction_cli generate  --candidate            (accepted only)
7  corrected_selection_cli         (explicit selection, released)
```

Answering `142` §7's questions:

- **Q1** — two commands to review one finding (steps 1–2), down from "one command plus a SQLite session".
- **Q2** — **SQLite is no longer required**, for either review or intake.
- **Q3** — every identity is copy-pasteable; step 1's output feeds step 2's arguments verbatim, and
  step 2's output supplies the intake id step 4 needs. Verified on real media (§8).
- **Q4** — yes: with the human interval, steps 4–6 complete without further lookup.
- **Q5** — yes: `admit` prints the candidate id that `decide` and `generate` consume.
- **Q6** — yes: `decide --kind reject` was already sufficient, and no wrapper was added for it.

## 8. Real-media smoke test — read-only

Against the preserved MVI_0147 measurement repository (2,370 segments, 31 findings), on a **copy**:

```text
diagnostic → raw-transcript:aea1b22d…  +  transcript-segment:aea1b22d…:14
inspect    → intake transcript-source-intake:sha256:19aa01b5…
             ordinal 14 of 2370, current interval [50.0, 53.0]
             previous [45.0, 46.0]   next [53.0, 58.0]
```

The bridge works end to end on real data **without opening the database**. No candidate was authored,
no timing value invented, no audio analysed — the human boundary of `142` is untouched. The original
evaluation artifact is byte-identical (`cmp` clean); only the scratch copy was read.

## 9. Tests

20 new tests in `tests/test_timing_correction_inspect_cli.py`:

- **reports** — canonical snapshot, intake id, both neighbours, first-segment and last-segment edges,
  the snapshot fields to carry;
- **errors** — unknown raw transcript, unknown segment, segment of another transcript, and a
  replacement segment (which carries the Raw Transcript's identity yet is not a member);
- **precision** — JSON values equal the stored values; awkward float `4276.139999999999` survives;
  inspect output round-trips into a successful `admit`;
- **must-not** — inspection writes nothing (six relations counted before and after), the Raw segment
  rows are unchanged, the CLI source names no diagnostic constant / anchor / drift / ffmpeg, and offers
  no proposal flag;
- **the loop** — inspect → admit → decide → generate reaches `created corrected revision`; reject
  needs no extra tooling; a no-op is still refused by the **service**.

## 10. Validation

```text
new focused                   20 tests   OK
complete suite             3,700 tests   OK (1 skipped — faster-whisper absent, pre-existing)
compile                    compileall src/lectureos   OK
git diff --check           clean
schema                     v54 (unchanged)     migrations added   0
docs/ and patches/         0 changes
repository validator       unaffected (no persistence change)
```

## 11. Repository impact

```text
src/lectureos/timing_correction_cli.py                        inspect subcommand + docs
src/lectureos/persistence/provider_transcript_admission.py    get_by_raw_transcript
tests/test_timing_correction_inspect_cli.py                   new, 20 tests
implementation/143_TIMING_CORRECTION_OPERATIONAL_TOOLING.md   new
```

No `docs/`, `patches/`, schema, migration, existing candidate, revision, or artifact change. The
`evaluation/timing-correction-review` package is untouched and remains outside git.

## 12. Remaining gaps

- **Text correction has the same gap.** Authoring a *text* candidate needs `source_text_snapshot`, and
  no command prints a segment's text either — except this one, which prints it as part of the
  snapshot. So the text path is now incidentally served, but no text-specific entry point was added.
  Out of this milestone's scope; worth naming as a candidate for its own small change.
- **No batch surface.** `142` §7 Q6's repetition concern stands: eight findings still mean eight
  `inspect` invocations and eight hand-written proposals. Deliberately not addressed — batching is a
  workflow design question, not a gap.
- **Inspect requires the raw transcript id.** It could have derived it from the segment identity's
  digest, but that would be parsing an identity for meaning rather than reading a relation. Requiring
  both keeps it a lookup; the diagnostic supplies both anyway.
- **The measurement repository still has no current Raw Transcript selection**, so candidates cannot be
  admitted there. That is expected released behaviour (`142` §10), unchanged here.

## 13. Result

```text
Operational Tooling Gap reproduced:        Yes — both, against the current CLI
Classification:                            A. Operational Tooling Gap (both)

SQLite required for timing review:         No (was: yes)
SQLite required for timing candidate
  intake:                                  No (was: yes)

Diagnostic → inspect bridge:               Yes — verified on real media, identities copy-pasteable
Inspect → human timing → candidate intake: Yes — inspect output round-trips into a successful admit
Finding automatically persisted:           No (TD-10 unchanged)
Finding automatically converted to
  candidate:                               No
Automatic timing proposal:                 None — inspect proposes nothing and reads no media
Automatic decision:                        None
Automatic revision selection:              None

Raw Transcript changed:                    No
Existing candidates changed:               No
Existing revisions changed:                No
Existing artifacts changed:                No

Composition changed:                       No
Revision chaining changed:                 No

Schema:                                    v54 (unchanged)
Migration:                                 None
Tests:                                     3,700 passing (20 new, 1 pre-existing skip)
Working tree:                              clean apart from pre-existing untracked media
Remote push:                               performed this session

Human review can now proceed without
  direct DB access:                        Yes

Requires Architect Decision:               No
Requires Blueprint Clarification:          No
Requires Blueprint PATCH:                  No
Requires Schema Change:                    No
Requires Migration:                        No
Requires additional human review:          Yes — the 8-clip package from `142` is still unlistened
Requires additional measurement:           No
```
