# Readable Subtitle Cue Composition and Readability Validation

- Status: Implementation Reference
- Blueprint: `docs/041_SUBTITLE_PIPELINE.md` §16 R-1…R-14, L-1…L-5 / `PATCH-0041`
- Schema: unchanged (**v53**; no migration, no new table, no new column, no new identity kind)
- Related: `123_LOCAL_ASR_PROVIDER_CONFIGURATION.md`, `122_FULL_LENGTH_REAL_MEDIA_E2E_VALIDATION.md`

## What it is

The second generator of the effective-transcript subtitle contract generation. It consumes the same
`EffectiveTranscriptInput` as `deterministic_segment_passthrough` and produces a **separate**
Candidate whose cues are display units: over-long cues split, character-identical adjacent duplicates
merge, sub-second cues extend into real gaps, and cues wider than one line carry a single canonical
`LF`.

It is a proposal. It creates no review record, decision, selection, or export eligibility, and never
promotes, ranks, supersedes, or modifies the passthrough Candidate.

## Why no schema change was needed

Two released structures already carried what the policy requires, and the investigation confirmed
both before any code was written:

- `derive_effective_candidate_identity` already takes `generator_kind`, `generator_version`, and
  `generation_parameters_version` (`§15` E7), so identity separation needed **no change to identity
  derivation**.
- `EffectiveSubtitleCue.source_segment_ids` is an ordered tuple of length ≥ 1, documented as being
  "for permanent compatibility with future non-1:1 segmentation contracts". Split (one segment → many
  cues) and merge (many segments → one cue) are therefore both representable, and
  `subtitle_effective_candidate_cue_segments` already stores the ordered relation.
- The cue `text` column's only constraint is `length(trim(text)) > 0`, so the canonical `LF` needs no
  schema change (L-1).

## Structure

| file | role |
|---|---|
| `application/readable_cue_composition.py` | parameter set, composition algorithm, generator spec |
| `application/readable_subtitle_validation.py` | readability codes, two-severity evaluator |
| `application/effective_subtitle_generation.py` | `SubtitleGeneratorSpec` seam (additive) |
| `composition.py` | `compose_sqlite_readable_subtitle_generation_service` |
| `effective_subtitle_cli.py` | `generate-readable`, `readability` |

### The generator seam

`SubtitleGeneratorSpec` names the facts `§15` E7 already hashes — kind, version, parameters version —
plus the cue builder. `PASSTHROUGH_GENERATOR` binds exactly the released kind, versions, and
`build_passthrough_cues`, and a test asserts that binding, so "the passthrough is unchanged" is
enforced rather than claimed. The service holds one spec; two generators are two composed services.

### Composition stages

1. **Merge (R-6)** — adjacent cues whose text is *character-identical* become one cue spanning the
   union of both ranges and carrying both lineages. Similar text, whitespace-only differences,
   non-adjacent repeats, and semantic closeness never merge: without diarization no evidence
   separates one speaker continuing from two speakers' turns.
2. **Split (R-5)** — a cue over `7.000 s` or over `44` display characters splits at the best
   available tier (terminator → comma → word boundary), recursively, never inside a word. If no
   admissible point exists, or a child would fall below the hard minimum, the cue is emitted
   unchanged and diagnosed. Forcing a split is prohibited.
3. **Timing interpolation (R-8)** — the interior boundary is proportional to display characters
   within the parent's own range. The parent's `start` and `end` are reused **verbatim**, so float
   accumulation cannot push a child outside the source range. The value is derived presentation
   timing, not an observed speech boundary.
4. **Extension (R-7)** — a cue below `1.000 s` extends forward into the real gap only, capped at the
   next cue's start. Neighbours are never moved. The last cue is never extended, because the timeline
   end is not known at this boundary and extending on an assumption would invent one.
5. **Line composition (L-1/L-2)** — at most one `LF`, inserted **after a whitespace run** so the
   second line starts on a word and no character is consumed. If no break yields two conforming
   lines, the flat text is kept and blocking validation reports it (`§7` of the milestone brief).

### Two measurement decisions worth stating

**Character counts are taken on `str.strip()`-ed text.** The corpus prefixes nearly every segment
with a space; counting stored whitespace would inflate every measurement against thresholds that are
about display width. The same rule makes a whitespace-only line an "empty line" violation, which is
the intended reading.

**Durations are compared with the released `PATCH-0039` tolerance.** The fixture contains a cue whose
true duration is exactly `0.100 s` stored as `0.09999999999990905`, because its bounds came from
different float paths. An exact comparison reports the product minimum violated by `9e-14` seconds.
The same tolerance keeps the three known `PATCH-0039` boundary pairs from being reported as overlaps.
This is representation handling, not a new threshold.

### Text preservation, stated precisely

R-4 requires the source text to be recoverable; R-6 authorizes carrying an identical-adjacent
duplicate's text **once**. Recovery is therefore exact against the **merge-normalized** source — the
source sequence with authorized duplicates collapsed — and `merge_normalized_source_text` computes
that reference so the invariant is executable.

**This is derived from the contract, not added to it.** R-6 is a Confirmed decision in the same
Decision section as R-4 and states in terms that the merged cue "carries the text once". On a
duplicated pair the two clauses cannot both hold literally: if R-4's "recover the source text
exactly" were read against the *raw* sequence, R-6 would be inoperative in every case it governs,
because carrying the text once necessarily yields one copy where the source held two. A reading that
nullifies an explicit Confirmed decision is not available. The only reading under which both operate
is recovery against the source with R-6's authorized merges applied — which is what
"merge-normalized" names. The term is a label for the derived reference, not a new permission: it
widens nothing, since every deviation it admits is one R-6 already authorizes by name, and any
deviation R-6 does not authorize still fails `READABILITY_TEXT_NOT_RECOVERABLE`.

## Validation

`evaluate_readable_cues` returns findings in two severities. Fourteen blocking codes cover duration
below the hard minimum, non-positive duration, non-increasing order, overlap, line count, line
length, cue length, the four line-break grammar rules, text-recovery failure, lineage mismatch, and
serialized/approved line disagreement. Four warning codes cover duration below target, duration above
maximum with no safe split, reading rate over 12 CPS, and unavailable line composition.

Severity is fixed per code and enforced in `ReadabilityFinding.__post_init__`; constructing a finding
with the wrong severity raises. **A duration over the maximum is a warning, never corruption** — the
corpus contains genuine long explanations and one 13.4-second cue holding three characters with
nothing to split.

The legacy `subtitle_structural_validation` boundary is a different contract generation and is
untouched; these codes are additive and scoped to readable candidates.

## Real fixture results

Composition over the preserved 2,564-cue corpus (`e2e-results/segments.jsonl`):

| property | passthrough | readable |
|---|---|---|
| cues | 2,564 | **2,574** |
| text recovery against merge-normalized source | — | **exact (39,870 chars)** |
| lineage covers every segment once, in order | — | **yes** |
| minimum duration (millisecond precision) | **20 ms** | **100 ms** |
| cues under 100 ms | 2 | **0** |
| cues over 44 characters | 52 | **0** |
| two-line cues | 1 | **469** |
| cues with three or more lines | 0 | **0** |
| overlapping cues | 0 | **0** |
| blocking findings | n/a | **3** |
| warnings | n/a | 91 |
| Final Selection admission (post `PATCH-0042`) | eligible | **refused** |

Warnings break down as 34 below the one-second target (no gap available), 51 above 12 CPS, 3 above
seven seconds with nothing to split, and 3 line-composition-unavailable.

**The two `0.020 s` duplicates that stopped Final Cut Pro import are merged.** The readable payload's
shortest cue is exactly `100 ms` at millisecond precision.

**The three blocking findings are all `READABILITY_LINE_TOO_LONG`, and they share one cause worth
recording.** They are cues of 42–43 display characters for which no admissible break point yields two
lines of ≤ 22. With `maximum_cue_characters = 2 × maximum_line_characters`, a 43-character cue
requires the break to land at exactly 21 or 22 characters, and natural Korean text rarely obliges.
This is a property of the parameter set, not a defect in the algorithm: the split rule does not fire
(the cue is under 44 characters and under seven seconds), and splitting it anyway would exceed R-5's
contracted trigger. Resolving it needs a parameter version that gives line placement slack, which is
a `PATCH` decision and not this milestone's to make.

Short conversational cues are preserved as distinct turns: `저요?` and `응` remain separate cues.

## Downstream and enforcement

`PATCH-0042` resolved the question this record previously left open. Final Selection admission is the
one enforcement boundary; every other boundary is explicitly out of scope.

| stage | behaviour under a blocking finding | contract |
|---|---|---|
| Candidate generation | proceeds | EN-2 |
| Review Preparation | proceeds | EN-2, §4.6 |
| Human Review Decision | proceeds | EN-3 |
| **Final Selection admission** | **refused, findings enumerated** | **EN-4, EN-5** |
| SRT Artifact → publication | unreachable; never re-evaluates | EN-7 |

Enforcement extends the released eligibility idiom: `EligibilityBlockingReason` gains
`READABILITY_BLOCKING` and `READABILITY_CONTRACT_UNKNOWN`, and `SelectionEligibility` carries the
blocking findings and the parameter version they were derived under. No new aggregate, lifecycle,
authority, or command exists, and nothing is persisted — readability is derived from the immutable
cue graph every time it is needed.

**The gate runs after the released decision conditions**, so a subject already blocked by a missing
or inapplicable Accept never reaches it and never reads the cue graph. Readability is an *additional*
condition, not a replacement, and a test asserts the ordering by counting cue reads rather than by
outcome — the two are indistinguishable from the outside otherwise.

**Version dispatch is explicit while only v1 exists.** `readability_contract_for` resolves the
parameter set from the Candidate's **own** generator and parameter versions and raises rather than
falling back, so introducing v2 later cannot re-evaluate released v1 Candidates under thresholds they
were never composed under. An unknown contract refuses the selection instead of guessing: guessing
would silently judge a Candidate by a policy it never claimed.

**Passthrough Candidates are out of scope entirely** (EN-9) — not evaluated, and their cue graph is
not even read. `is_readable_candidate` answers the scope question in one place so a generator-kind
literal is never repeated across boundaries.

### Existing records

The Final Selection, SRT Artifact and materialization produced during earlier validation — made while
the readable Candidate carried three blocking findings — are **unchanged**. EN-8 governs new
admissions only, and re-running selection against that same subject now refuses without touching a
single row.

## CLI

```text
effective_subtitle_cli generate-readable --intake <id> --database <db>
effective_subtitle_cli readability --candidate <id> [--max-warnings N] --database <db>
```

Output identifies the generator, both versions, the parameter version, the Candidate identity, the
cue count, blocking count, warning count, and states that the Candidate is separate from the
passthrough Candidate and that nothing was promoted or selected. **No threshold override exists**:
the parameter set participates in identity, so an override would produce a Candidate whose identity
misdescribes what produced it. `--max-warnings` controls printing only.

## Not implemented

Per the milestone scope and `§16` Deferred: no Review comparison interface, no Modify decision that
edits cue structure, no retroactive conversion of existing Candidates, no re-selection or re-issue of
released output, no diarization, no word timestamps, no pause detection, no morphological analysis,
and no new subtitle format. Nothing in this milestone selects a Candidate.
