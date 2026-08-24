# Human Transcript Timing Correction

- Status: Implementation Reference
- Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` §17 Human Timing Correction Candidate (TC-1…TC-21),
  §18/§19/§20 `PATCH-0047` forward notes
- Schema: **v54** (was v53) — three additive relations, one single-step migration
- Related: `135`, `136`, `137`, `138`; `PATCH-0045`, `PATCH-0046`, `PATCH-0047`

## What it is

A person can now propose that one Raw Transcript segment's presentation interval should be different,
accept or reject that proposal, and — on accept — record the result as an immutable corrected
revision whose timing is canonical for that segment. When that revision is explicitly selected, the
corrected timing reaches the delivered SRT through the released path with no new subtitle logic.

`PATCH-0046` released a diagnostic that could tell a person where to listen and gave them nowhere to
put the conclusion. This closes that gap and nothing more.

## 1. Repository investigation — what decided the design

Four released facts, read out of the code rather than assumed:

| fact | consequence |
|---|---|
| `correction_candidates.proposed_text` is `TEXT NOT NULL`, and K-2 rejects a no-op (`correction_candidate_admission.py:143`) | A timing proposal cannot ride the released candidate. Carrying the source text unchanged is exactly what K-2 refuses, and making the column nullable is not additive in SQLite. **A sibling record is required, not a choice.** |
| `correction_candidate_decisions` foreign-keys `correction_candidates(identity)` | The decision *semantics* transfer unchanged, but the *relation* cannot reference a timing candidate. A sibling relation is needed for the foreign key alone. |
| `corrected_revision_generations` foreign-keys the same table | Same again for generation. |
| `TranscriptSegment` carries `start`/`end`; `CorrectedTranscriptRevision.correction_candidate_ids` defaults to `()`; `corrected_transcript_revision_candidates` has **no** FK to `correction_candidates` | The `§19` aggregate needed **no** change. A timing revision names no text candidate and the released field simply stays empty. |

One chokepoint was not obvious from the Blueprint and had to be found by reading:
`CorrectedRevisionSelectionService._revision_context` resolved a revision's owning intake **only**
through `corrected_revision_generations → correction_candidate_admissions`. A timing revision has no
row there, so selection would have refused it and `§20` could never have reached the SRT. The `§20`
forward note requires selection to be correction-kind-agnostic, so this is where the additive
extension belongs (§6 below).

## 2. Contract mapping

| TC | implementation | test |
|---|---|---|
| TC-1 scope | three services, no new lifecycle or gate | whole suite |
| TC-2 sibling, not extension | `timing_correction_candidates`; released text family untouched | `test_timing_candidates_are_stored_in_their_own_relation`, `test_proposed_text_stays_not_null` |
| TC-3 complete interval | `proposed_start` **and** `proposed_end` required; no start-only shape exists | `test_start_only_proposal_cannot_be_expressed` |
| TC-4 human-authored only | the record has an `author` (`HumanActorReference`) and **no** `source_type`, so a machine proposal has no representation | `test_machine_source_vocabulary_does_not_exist` |
| TC-5 diagnostic not a prerequisite | admission never reads a diagnostic; nothing converts a finding | `test_candidate_is_admitted_with_no_timing_finding_present`, `test_no_code_path_turns_a_finding_into_a_candidate` |
| TC-6 structural admission | lineage, timed segment, finite values, `start >= 0`, `end > start` | 8 admission tests |
| TC-7 neighbour non-overlap | strict comparison against the adjacent segments under the released ε | 4 overlap tests |
| TC-8 timing no-op rejected | both boundaries within ε of source ⇒ refused | `test_timing_no_op_is_rejected`, `…_within_the_released_epsilon…` |
| TC-9 source timing snapshot | exact interval match required at admission and again at generation | `test_stale_source_timing_snapshot_is_rejected` |
| TC-10 §18 unchanged, FK-only sibling | `DecisionKind`/`HumanActorReference` imported, never redefined | `test_released_value_types_are_reused_rather_than_redefined` |
| TC-11 rejection is normal | `reject` records cleanly; no fourth state anywhere | `test_reject_is_a_normal_first_class_outcome`, `test_no_state_beyond_the_released_three_exists` |
| TC-12 replacement segment | source text copied verbatim, accepted interval, `replaces_segment_id` | 5 generation tests |
| TC-13 corrected timing authority | end-to-end to the SRT with no retiming logic | `test_corrected_timing_reaches_the_delivered_srt`, `test_no_subtitle_retiming_logic_participates` |
| TC-14 `041` unamended | no file under `docs/041` changed; no subtitle module changed | scope check §12 |
| TC-15 released identity idiom | the `§19` anchor recipe, byte-for-byte | `test_generation_digest_follows_the_released_anchor_recipe` |
| TC-16 Raw immutability | provider/raw/segment rows compared before and after | `test_raw_transcript_and_provider_rows_are_unchanged` |
| TC-17 artifacts not stale | released SRT bytes unchanged by generation and by selection | `test_corrected_timing_reaches_the_delivered_srt` |
| TC-18 composition Deferred | structurally impossible to compose; order-independent | `test_competing_corrections_are_never_composed`, `test_generation_order_does_not_change_either_result` |
| TC-19 strictly additive | v54, three relations | `test_released_relations_are_byte_identical_across_the_step` |
| TC-20 no backfill | new relations empty after migration; a legacy repository gains nothing | `test_existing_text_correction_rows_survive_the_step_unchanged` |
| TC-21 refinement Deferred | no VAD, alignment, or estimator anywhere | `test_admission_consults_no_diagnostic_and_no_media` |

## 3. The candidate

```text
timing_correction_candidates
  identity  transcript_source_intake_id  raw_transcript_id  segment_id
  author  candidate_ref
  source_start_snapshot  source_end_snapshot
  proposed_start  proposed_end
  rationale  content_fingerprint
```

Two shape decisions are worth stating because they are where a contract could have been eroded.

**There is no `source_type`.** The released text candidate has `manual | external | rule`. Reproducing
that here would give a machine-generated timing proposal a representation, and TC-4 admits only
human-authored ones. Instead the record carries `author` as a `HumanActorReference`. The anchor is
therefore `(intake, raw_transcript, segment, author, candidate_ref)` — K-5's idiom with `author` in
the place of `(source_type, source_reference)`. A machine proposal is not *rejected by a check*; it
has nothing to be written into.

**Distinct proposals need distinct `candidate_ref`s.** TC-15 requires two proposals for one segment to
be two identities and leaves the derivation to the released idiom. That idiom (K-8) is a distinct
`candidate_ref`, with the anchor separate from the content fingerprint so that a *same* anchor with a
*different* payload is a K-7 conflict rather than a silent overwrite. Both behaviours are asserted.
Folding the interval into the anchor would have made conflict detection impossible, so it was not
done.

## 4. Admission, no-op, and staleness

Admission answers only what it can know without media. It verifies lineage (K-1's rules), that the
target segment is timed at all, that the values are finite with `start >= 0` and `end > start`
(A-10's vocabulary), that the interval does not overlap its neighbours, that it is not a no-op, and
that the carried snapshot still matches the persisted segment.

**Three comparisons use the released `PATCH-0039` ε and nothing else** — snapshot equality, no-op
detection, and neighbour touching. TC-7 and TC-8 name ε explicitly; TC-9 says "exact match" without
naming it, and ε was used there too because ε's released purpose (T-2) is precisely deciding whether
two values denote the same instant, which is exactly the question a float snapshot comparison asks.
No new tolerance exists, and a test asserts the admission module contains no numeric constant beyond
`{0, 1, 2, 64}` — index arithmetic and the digest length.

**The neighbour check is the one place this milestone chose to refuse early.** `READABILITY_CUES_OVERLAP`
is BLOCKING and `PATCH-0042` enforces blocking findings at Final Selection, so an overlapping
correction would be admitted, accepted, generated, and then refused delivery. TC-7 closes that at the
point where the person can still adjust the proposal. Touching boundaries stay legal and no duration
threshold participates: a 0.1 s overlap is refused exactly as a 10 s one is.

**No upper timeline bound is checked.** TC-6 requires the interval to lie on the segment's source
timeline; the released model has a `SourceTimelineId` but no timeline duration anywhere, so the
checkable content of that requirement is that the segment carries a timeline and the offsets on it are
non-negative. Inventing an upper bound would have meant inventing a number. Recorded here rather than
silently narrowed.

## 5. Human decision

A sibling relation with the released columns, the released append-only supersession, and the released
three derived states. `DecisionKind` and `HumanActorReference` are imported, never re-declared — a
test parses the module's AST and asserts it declares neither.

Rejection is exercised as a first-class outcome throughout, and no fourth state exists: a test greps
the module for `ignored`, `dismissed`, `false_positive`, `acknowledged`, and `auto_accept` and requires
all five absent. TC-11's reason matters — inventing such a state would imply the diagnostic had made a
claim that turned out wrong, and `PATCH-0046` TD-2 says it made no claim at all.

## 6. Corrected revision and the §20 extension

Generation reuses `CorrectedTranscriptRevision` unchanged. The replacement segment carries the source
text (asserted byte-identical), the accepted interval, the source's order/timeline/speaker, and
`replaces_segment_id`. `correction_candidate_ids` is `()`, and the persistence layer *requires* it to
be empty so a timing identity can never be written into the text field.

`CorrectedRevisionSelectionService` gained two **optional** constructor parameters and an internal
`_RevisionLineage` that normalises "this revision's parent raw transcript, its candidate, and the
decision history that owns it" across the two kinds. When the text generation relation has no binding,
the timing one is consulted; when the new parameters are absent, behaviour is exactly as released.
S2-8's write-time eligibility and S2-9's applicability rules then apply unchanged to both kinds —
including that a later Reject makes a selected timing revision *inapplicable* rather than corrupt, and
that it can no longer be newly selected.

The repository validator's `CORRECTED_SELECTION_CONTEXT_MISMATCH` needed the same treatment: it
resolved a selection's intake only through the text lineage. It now passes when *either* lineage
resolves, which on a repository with no timing rows is arithmetically the released condition. That was
found by running validation over a real timing flow, not by inspection.

## 7. Composition stays Deferred — and why it is safe

TC-18 forbids automatic composition and an implementation-chosen ordering. Both hold **structurally**,
which is stronger than a check:

- Each generation applies exactly one candidate to the source Raw Transcript. A text correction and a
  timing correction on the same segment therefore produce two independent sibling revisions, and `§20`
  selects one. There is no code path that merges them.
- Two tests pin this: one asserts the text revision changed only text and the timing revision changed
  only timing, neither carrying the other's change; the other runs both generations in both orders and
  asserts identical resulting identities.

**Correction on top of a correction is not available in this implementation.** TC-18 notes that `§19`
already models a revision whose parent is another revision, but K-1 anchors a candidate to the current
*Raw Transcript*, and V-14 leaves revision-on-revision chaining Deferred. Implementing it would have
required extending K-1's lineage rules — a Product Decision, not an implementation detail — so it was
not done. TC-18's "what the product should do with a candidate made stale by a competing correction"
therefore remains exactly as open as the PATCH left it.

One nuance the PATCH's reasoning does not quite match the code: TC-18 says accepting either correction
makes the other's snapshot stale. It does not, because generation never mutates the source segment —
both candidates stay applicable and both can generate. The *outcome* the PATCH wanted (no composition)
holds for a stronger reason than the one it gave. Recorded rather than glossed.

## 8. Schema and migration

```text
v53 → v54, strictly additive, one step

timing_correction_candidates              CHECK proposed_end > proposed_start, proposed_start >= 0
                                          UNIQUE (intake, segment, author, candidate_ref)
timing_correction_candidate_decisions     kind IN (accept, reject); UNIQUE (candidate, sequence)
                                          CHECK sequence 0 ⇔ no previous
timing_correction_revision_generations    UNIQUE (revision); UNIQUE (candidate, decision)
                                          CHECK replaced <> replacement
```

Every released relation is asserted byte-identical across the step by comparing `sqlite_master.sql`
before and after, and `correction_candidates.proposed_text` is asserted still `NOT NULL`. All 53
released versions chain single-step to v54 with the marker row preserved; downgrade, direct skip, and
an unsupported target are all rejected. No row is rewritten and the three new relations are empty
after migration — TC-20's no-backfill requirement, asserted rather than described.

## 9. Downstream E2E

Driven over the released chain with a fake provider result (no ASR run, no media decoding):

```text
timing candidate → accept → corrected revision
                 → explicit §20 selection → effective transcript → subtitle candidate
                 → review accept → Final Selection → SRT artifact → materialization

before   00:00:10,000 --> 00:00:20,000   둘째 문장
after    00:00:18,000 --> 00:00:24,000   둘째 문장     ← text identical, interval corrected
```

Also asserted: untouched segments keep their timing; the corrected cue's `start`/`end` equal the
revision segment's values exactly (so no retiming logic participates); generation alone selects
nothing, writes no artifact, and leaves the released SRT bytes on disk unchanged; the new artifact has
a new identity at a new location; and repository validation is healthy through the whole flow.

## 10. Validation

```text
focused (new)          113 tests   OK
complete suite       3,670 tests   OK   (3,557 released + 113)
compile              python -m compileall src/lectureos   OK
git diff --check     clean
repository validator healthy through the E2E flow, schema_version 54
```

Released version-pinned assertions were updated mechanically, following the pattern the v53 milestone
established: legacy-database builders learn `_V53_ADDITION_STATEMENTS`, the "beyond the chain" target
moves 54 → 55, and the v53 file's `test_schema_version_is_fifty_three` becomes
`test_v53_remains_a_supported_version` (the "is the maximum" assertion moves to the v54 file, which is
where it is true). Ten golden JSON files and two acceptance modules carry `schema_version` 53 → 54.

## 11. Remaining risks

- **`author` is a free-form `HumanActorReference`.** Nothing verifies the named person authored the
  proposal; that is the released Human Authority model's existing property, not a new gap.
- **No timeline upper bound** (§4). A proposal past the end of the media is admissible. Closing it
  needs a released timeline duration, which does not exist.
- **Sequential text-then-timing correction is unavailable** (§7). A person who wants both on one
  segment must currently choose. That is V-14's deferral, surfaced here as a real product limitation
  rather than hidden.
- **The `§20` selection service now has two optional dependencies.** A caller that constructs it
  directly without them silently cannot select timing revisions. The composition root always supplies
  them; a direct construction elsewhere would not be caught by a test.
- **No demo/golden** was added for this capability, unlike several released slices. The E2E is a test
  rather than a committed golden artifact.

## 12. Scope confirmation

Changed: `src/lectureos/application/` (3 new modules, `identities.py`, `corrected_revision_selection.py`,
`__init__.py`), `src/lectureos/persistence/` (3 new modules, `sqlite.py`),
`src/lectureos/validation/repository_validator.py`, `src/lectureos/composition.py`,
`src/lectureos/timing_correction_cli.py`, `src/lectureos/repository_validation_acceptance.py`,
`tests/` (7 new files + mechanical version pins), `examples/**/expected/*.json` (schema_version).

Unchanged: `docs/` and `patches/` (no Blueprint or PATCH edit), `docs/041` and every subtitle module,
the timing and hallucination diagnostics, the released text-correction modules, and every released
artifact under `e2e-results/`.

## 13. What this milestone deliberately did not do

No automatic timing proposal, no diagnostic-to-candidate conversion, no drift or anchor-gap or
readability threshold, no VAD, no word timestamps, no forced alignment, no energy estimator, no
timing editor UI, no Modify, no text+timing composition, no revision chaining, no Raw Transcript
mutation, no automatic selection, no automatic re-materialization, no change to any released SRT, no
Blueprint edit, and no PATCH edit.
