# PATCH-0041

- Title: Effective-Transcript Subtitle Readability and Editorial Timing Policy (041 §16)
- Status: Proposed
- Priority: High
- Trigger: Architect Decision on the full-length validation recorded in
  `implementation/122_FULL_LENGTH_REAL_MEDIA_E2E_VALIDATION.md`
- Created: 2026-08-06
- Target Blueprint: `docs/041_SUBTITLE_PIPELINE.md` (new §16; §6 forward note; §9.1 forward note;
  §13 Requires Validation — four items resolved; §15 E7 forward note; header amended)

---

## Status

**Proposed.** This document exists; `docs/041_SUBTITLE_PIPELINE.md` has not yet been amended. The
decisions below are not in force until the Blueprint changes in *Required Blueprint Changes* are
applied and the *PATCH Acceptance Criteria* are verified, at which point this Status becomes
`Accepted`.

Once accepted, this PATCH fixes the readability and editorial-timing policy for the
**effective-transcript subtitle generation** and requires a corresponding implementation slice. It
introduces **no schema change, no migration, no new aggregate, no new authority, and no new
lifecycle**. It removes nothing: the released `deterministic_segment_passthrough` generator, every
existing Candidate, Review Decision, Final Selection, SRT Artifact, materialization, delivery and
publication stay exactly as they are.

## Context

`041 §4.3` (Reading Representation) and `§4.4` (Time Representation) have contracted readability and
display timing as pipeline responsibilities since the Blueprint baseline, and `§5` has permitted a
Transcript portion to become several Subtitle Units and several Transcript Units to contribute to one
Subtitle Unit. What has never existed is the **policy**: `§6` states that "가독성 정책의 구체적인
수치, 언어별 기준과 판단 방법은 이 문서에서 확정하지 않는다", `§9.1` defers the thresholds to later
validation, and `§13 Requires Validation` lists the exact open questions this PATCH answers.

The released effective generator is `deterministic_segment_passthrough v1`: it maps ASR/effective
transcript segments to cues one-to-one and applies no readability policy. The legacy generation's
`compose_reading_lines` is explicitly documented as "threshold-independent — it applies no readability
policy". No minimum or maximum display duration, line length, or line count exists anywhere in the
repository.

## Trigger — validation evidence

Full-length validation produced 2,564 cues and 37,870 characters from a 7,355.845 s Korean literature
lecture. The distribution shows the problem is **narrow but real**, which is why this policy is
targeted rather than a wholesale re-composition:

| property | measurement |
|---|---|
| duration within 1–7 s | 94.2 % (2,416 of 2,564) |
| text within 44 characters | 98.0 % (2,512 of 2,564) |
| duration under 1 s | 60 cues |
| duration over 7 s | 88 cues |
| text over 44 characters | 52 cues |
| adjacent cues with identical text | 4 |
| cues shorter than one video frame | 2 |
| overlapping cues | **0** |
| touching boundaries | 2,257 of 2,563 (88 %) |
| characters per second | median 5.5, p90 9.0, p99 16.0 |

Three observations from the audio determine the shape of the policy.

**The sub-frame cues are duplication artefacts, not short speech.** Cue 61 (`0.020 s`) repeats cue
60's text verbatim, and cues 74/75 (`0.020 s`, `0.140 s`) repeat cue 73's. Final Cut Pro stopped
importing at cue 61. All four duplicate pairs behave this way.

**Sub-second cues are overwhelmingly legitimate.** `저요?`, `응`, `가요?`, `응?`, `수학?`, `응` at
0.5 s each are a real teacher-student exchange, as are `네?`, `그치?`, `자`, `어`. Forcing every cue
to one second would either merge distinct conversational turns or displace every following cue.

**Characters per second cannot detect this corpus's actual defect.** The worst cue — 145 characters
displayed for 23.0 s — has a CPS of 6.3, below any reasonable warning threshold. The problem is
display-unit size, not reading speed.

## Decision

### Scope and generator

**R-1 (Confirmed) — Scope.** This policy governs the **effective-transcript** subtitle generation
only. The legacy contract generation (`§4.x` first implementation, `subtitle_candidates` family) and
the released `deterministic_segment_passthrough` generator are not amended, re-scoped, or deprecated,
and no existing record acquires a new meaning.

**R-2 (Confirmed) — Generator.** `readable_cue_composition` is a **new additive generator version**
under the released `§15` E6/E7 provenance. It does not replace, wrap, supersede, or re-interpret the
passthrough generator, which remains a supported generator for this generation.

**R-3 (Confirmed) — Candidate competition.** One Effective Transcript Consumption Binding may hold a
passthrough Candidate and a readable Candidate simultaneously. This is ordinary `§15` E9 behaviour —
different requests are not merged merely because their content coincides — and requires no new
concept. **Neither is automatically promoted, preferred, ranked, or selected.** The released Review
Preparation, Human Decision, and Final Selection boundaries retain sole adoption authority.

### Transformation semantics

**R-4 (Confirmed) — Text preservation.** The generator preserves the input transcript text's exact
character sequence, order, and meaning. It does **not** add, delete, rewrite, normalize, trim,
re-order, translate, punctuate, or case-fold any character. **The single permitted insertion is the
line break defined in L-1**, and it is permitted because `§5` makes the Subtitle Unit a display unit
rather than a transcript unit. Removing every inserted line break must recover the source text
exactly; this is a testable invariant, not a stylistic aim.

**R-5 (Confirmed) — Split.** One source cue may become several display cues when it satisfies
`duration > 7.000 s` **or** `text length > 44 characters`, **and** a safe split point exists inside
it. Split points are chosen by fixed priority:

1. sentence-terminating punctuation (`.` `?` `!`)
2. comma or conjunctive boundary
3. word (whitespace) boundary

**Splitting inside a word is prohibited.** Morphological analysis is not used. Pause-based splitting
is unavailable and not approved: word-level timestamps do not exist under the `040 §15` L-15 approved
provider configuration, and enabling them is a different contract's decision.

If no split point satisfying the priority exists, or if splitting would produce a fragment violating
the thresholds, **the generator does not split**. It emits the cue unchanged and records a diagnostic
(R-11). Forcing a split is prohibited.

**R-6 (Confirmed) — Merge.** In this generation the generator merges **only adjacent cues whose text
is character-identical**. The merged cue spans the union of the two time ranges and carries the text
once. Merging cues with different text, or merging distinct utterances on semantic grounds, is
**prohibited** — speaker diarization does not exist, so no evidence distinguishes one speaker's
continued sentence from two speakers' turns. All source segment lineage of every merged cue is
preserved.

**R-7 (Confirmed) — Timing extension.** A cue shorter than the target minimum may be extended
**forward into the actual gap before the next cue**, toward `1.000 s` and no further. The generator
must not move the next cue, encroach on it, create an overlap, change order, or extend beyond the
Source Timeline. Extension into silence invents no speech; displacing a neighbour would falsify one.
If the gap is insufficient, the short cue is kept as it is and a diagnostic is recorded.

**R-8 (Confirmed) — Timing interpolation.** When a long cue is split without word timestamps, the
interior boundary is computed **proportionally to character count within the source cue's own time
range**. This value is **derived presentation timing**, explicitly not an observed speech boundary,
and must be recorded as derived. The original transcript time range and the cue-to-source-segment
lineage remain recoverable for every produced cue. Interpolated boundaries never leave the source
range.

**R-9 (Confirmed) — Ordering and non-overlap outrank readability.** Display order and non-overlap are
invariants; the readability targets are goals. Where they conflict, the invariant wins, the original
cue survives unchanged, and the unmet goal becomes a diagnostic. The validation corpus contains zero
overlaps, so this contract preserves an already-holding property rather than introducing one.

### Thresholds

**R-10 (Confirmed) — Readability parameter set, version 1.**

| parameter | value |
|---|---|
| hard minimum display duration | `0.100 s` |
| target minimum display duration | `1.000 s` |
| maximum display duration | `7.000 s` |
| maximum characters per line | `22` |
| maximum lines per cue | `2` |
| maximum characters per cue | `44` |
| CPS warning threshold | `> 12` |

These constitute one **versioned parameter set** that participates in Candidate identity (R-13).
Changing any value produces a new parameter version and therefore new Candidates; it never mutates an
existing one.

**On the `0.100 s` hard minimum — what is and is not being claimed.** LectureOS fixes `0.100 s` as
the **product-level hard minimum for readable subtitle cues produced by this generation**. It is
**not** asserted as a universal validity rule for SRT, for subtitle formats generally, or for every
external consumer, and this PATCH must not be cited for such a claim. The grounds are specific:
a `0.020 s` cue actually failed to import in Final Cut Pro, the target editing environment;
`0.100 s` is comfortably longer than one frame at 24, 25, 30, and 60 fps; and the legitimate short
conversational cues in the validation corpus sit at roughly `0.5 s`, so they are preserved rather
than swept up. **Existing passthrough cues below this value do not become retroactively corrupt** —
they were admitted under `040 §14` A-10 as amended by `PATCH-0039` and remain valid historical
records of what the provider produced.

**On CPS.** Characters per second is adopted as a **diagnostic indicator only**, never as a
generation rule, because the measured evidence shows it does not detect this corpus's defect: the
145-character cue reads at 6.3 CPS.

### Line representation

**L-1 (Confirmed) — Canonical line structure lives in the cue text as `LF`.** A cue's display lines
are represented by `U+000A` line breaks inside the canonical cue text. A cue text containing no line
break is a one-line cue; this is the existing degenerate case, so every released cue remains valid
without reinterpretation.

The decision criterion is what a person approves and what every serializer must project in common.
Under L-1 the approved artifact **is** the display form: no transformation stands between Human
Decision and delivered file. The common projection across formats is an ordered sequence of display
lines, canonically encoded with one separator; a format's serializer maps that separator to its own
syntax (SRT: a literal `LF`; a future format: its own line element) and decides nothing about
presentation.

Two alternatives were examined and rejected on that same criterion. A **separate ordered line
structure** would make the cue own its content twice, introduce a joining rule that necessarily lives
in the serializer — reinstating, in reduced form, the very problem of deciding presentation after
approval — and require changing the released `§15` E7 identity derivation to admit the new field.
**Flat text wrapped by the serializer** was rejected outright: it makes the serializer invent display
structure nobody approved, permits different formats to ship different line structures for one
approved Final Subtitle, and contradicts `§4.8`.

**L-2 (Confirmed) — Line break grammar.** Within one cue text: at most `maximum lines per cue − 1`
line breaks; **no consecutive line breaks**; **no leading or trailing line break**; and no other
control character. Consecutive line breaks are prohibited for a concrete reason — the released
canonical SRT serializer separates blocks with a blank line, so a blank line inside a cue would
corrupt block framing.

**L-3 (Confirmed) — Serializer responsibility is unchanged.** The released `canonical_srt` v1
serializer's "text preserved exactly" contract is satisfied literally: it emits the approved cue text
verbatim, and an embedded `LF` already yields correct multi-line SRT. **No serializer wraps,
re-wraps, splits, joins, or re-flows text.** No serializer change is authorized by this PATCH.

**L-4 (Confirmed) — Line structure participates in identity automatically.** Because the line breaks
are inside the cue text, and cue text already participates in Candidate identity and the content
fingerprint, the approved display structure participates in identity **with no change to the released
identity derivation**. Two Candidates differing only in line composition are distinct Candidates.

**L-5 (Confirmed) — Meaning of `text` is widened, deliberately and only here.** For this generation a
cue's `text` is its **display text**, not merely its utterance text. This is the cost of L-1 and it is
accepted knowingly: `§5` already defines the Subtitle Unit as a display responsibility, and R-4's
recoverability invariant plus L-2's grammar bound the widening. Legacy generation semantics are
unchanged.

### Authority, identity, preservation

**R-12 (Confirmed) — Review authority.** A readable Candidate is an automated **proposal**, exactly as
`§4.2` describes a Candidate and `§13 Confirmed` requires ("AI 또는 처리 규칙은 Subtitle 후보를
만들지만 사용자의 결정을 대신하지 않는다"). Generation creates no review record, no decision, no
selection, and no export eligibility. Adoption remains with Review and Final Selection.

**R-13 (Confirmed) — Identity and replay.** Candidate identity uses the released `§15` E7 composition
and reflects the generator kind, the generator version, the algorithm version, and the readability
parameter version, in addition to the binding, source kind, and exact source identity it already
reflects. The same binding, the same immutable input, and the same parameter set converge on the same
Candidate (`§15` E8). No new identity mechanism is introduced.

**R-14 (Confirmed) — Legacy and released preservation.** No released record is rewritten,
back-filled, dual-written, re-derived, migrated, or re-interpreted. Existing Candidates keep their
identities and content; existing Review Decisions, Final Selections, SRT Artifacts, materializations,
deliveries and publications are untouched. Per `§12.2`, a readability policy change may produce new
Candidates but **never** re-applies existing user Modifications or Review Decisions automatically,
and never re-writes an approved or published Final Subtitle.

### Validation

**R-11 (Confirmed) — Two severities, deliberately separated.**

Delivery-blocking (structural or contract violations):

- display duration `< 0.100 s`
- overlapping cues
- non-increasing display order
- line count `> 2`
- any line longer than `22` characters
- cue text longer than `44` characters
- line-break grammar violation (L-2)
- text loss, text addition, or lineage loss relative to the source (R-4)
- disagreement between the approved line structure and the serialized line structure

Non-blocking diagnostics (unmet readability goals, surfaced for Review):

- display duration `< 1.000 s`
- display duration `> 7.000 s` where no safe split point exists
- CPS `> 12`
- any other unmet readability target

**A duration over 7 seconds is not corruption.** The validation corpus contains legitimate long
explanations, and cue `#1505` (`애들을`, 3 characters over 13.4 s) is a long cue with nothing to
split. Treating length alone as a defect would flag genuine lecture material as broken.

## Non-goals

Not decided, not approved, and each requiring its own gate evaluation: speaker-diarization-based
merge; semantic merge of differing text; pause-based splitting; word-timestamp-based timing;
morphological analysis; retroactive transformation of existing Candidates; re-application of existing
Review Decisions; a Review comparison interface; a Modify decision that edits cue structure directly;
format-specific line wrapping; new formats such as iTT or FCPXML; ASR hallucination; transcription
checkpointing; `U+FFFD` handling; batch correction; and a terminology dictionary.

## Required Blueprint Changes

Applied to `docs/041_SUBTITLE_PIPELINE.md` only. No other Blueprint file requires amendment: no
released cross-reference to subtitle readability policy exists elsewhere.

1. **Header** — Blueprint version and Last Updated advanced; `PATCH-0041` added to `Amended By`.
2. **§6** — the released sentence deferring the concrete thresholds is **kept verbatim**; a forward
   note records that this generation's values are fixed in §16.
3. **§9.1** — the released deferral is **kept verbatim**; a forward note references §16.
4. **§13 Requires Validation** — the released questions are **kept verbatim**; a resolution note
   records that four are answered in §16 (readability thresholds, split priority, safe merge
   condition, timing adjustment range) and that the remainder stay open.
5. **§15 E7** — a forward note records that the readability parameter set participates in the
   already-contracted algorithm/parameter version.
6. **New §16** — R-1…R-14, L-1…L-5, Sections Not Re-scoped, Deferred, Canonical Invariants.

## PATCH Acceptance Criteria

Verified against the Blueprint amendment itself, before this PATCH may be marked `Accepted`. These
say nothing about code.

- [ ] §16 exists in `docs/041` and encodes R-1…R-14 and L-1…L-5 as written here.
- [ ] No released sentence in `docs/041` is deleted or rewritten; every prior PATCH note is treated
      as released text and is likewise untouched.
- [ ] §6, §9.1, §13 and §15 E7 gain **additive forward notes only**, verified line by line.
- [ ] Line representation is fixed as a Blueprint contract (L-1…L-5), not left as an implementation
      choice.
- [ ] The thresholds and transformation rules are encoded as a **versioned generation policy**, not
      as free-standing numbers.
- [ ] Review and Final Selection remain the sole adoption authority; no new authority appears.
- [ ] The passthrough generation and every released record are stated unchanged and are in fact
      unchanged.
- [ ] The Deferred list is present and no deferred item is silently decided.
- [ ] The change set contains **no implementation, schema, migration, or test change**.

## Implementation Requirements

Required validation for the implementing milestone. **Not satisfied by this PATCH** and not to be
marked complete here.

1. `readable_cue_composition` exists as a new generator version; the passthrough generator is
   unchanged and still usable.
2. Both Candidates coexist for one binding with distinct identities, and neither is auto-selected.
3. Removing every inserted line break from a readable Candidate recovers the source text exactly.
4. Splitting obeys the priority order and never splits inside a word.
5. An un-splittable over-long cue is emitted unchanged with a diagnostic, not force-split.
6. Only character-identical adjacent cues merge; lineage of both is preserved.
7. Extension never moves, encroaches on, or overlaps the next cue, and never leaves the timeline.
8. Interpolated boundaries stay inside the source range and are recorded as derived.
9. Line-break grammar (L-2) is enforced; a cue with consecutive, leading, or trailing breaks is
   refused.
10. The released `canonical_srt` v1 serializer is unmodified, and its output for a two-line cue is a
    two-line SRT block.
11. Blocking and non-blocking validation codes are separated exactly as R-11 requires.
12. Changing any parameter value yields a different Candidate identity.
13. Regression over the preserved 2,564-cue fixture: no overlap introduced, no text lost, and the
    four identical-text duplicate pairs resolved.
14. The complete test suite passes and the schema version is unchanged.

## Consequences

- `041` gains §16; §6, §9.1 and §15 E7 gain forward notes; four `§13 Requires Validation` items are
  resolved and the remaining three stay open.
- One implementation slice adds a generator and readability validation. **Schema is unchanged**: the
  released cue `text` column already permits the canonical line break, and cue-to-source-segment
  lineage already exists to carry split and merge provenance.
- The `0.100 s` minimum applies to newly generated readable cues only; existing passthrough cues
  below it remain valid historical records.
- Adopting a readable Candidate for an already-published lecture requires a **new human decision**,
  never an automatic re-issue.

## Changed Blueprint Files

- `docs/041_SUBTITLE_PIPELINE.md` — pending (see *Required Blueprint Changes*)

## Result

Pending. This PATCH is `Proposed`: the document exists and the Blueprint is not yet amended. This
section records the final state once the amendment is applied and the *PATCH Acceptance Criteria*
are verified.
