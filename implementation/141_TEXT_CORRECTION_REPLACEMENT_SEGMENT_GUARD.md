# Text Correction Candidate Admission — Replacement-Segment Target Guard

- Status: Implementation Reference (defect fix)
- Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` §17 K-1 (unchanged), §19 V-1/V-4/V-14, §20 S2-14
- Schema: unchanged (**v54**; no migration, no table, no column, no index)
- Related: `139`, `140` §12; `PATCH-0047`, `PATCH-0048`

## What this is

`implementation/140` §12 reported an asymmetry: text Correction Candidate Admission accepted a
corrected revision's **replacement segment** as a candidate target, while generation later refused it
and the timing path refused it at admission. This record reproduces that, classifies it, and removes
the asymmetry with the smallest change that satisfies K-1 as written.

**It implements no new capability.** Composition and revision chaining remain exactly as
`PATCH-0048` left them.

## 1. Repository investigation

Read: `§17` K-1…K-14, the `PATCH-0047` Human Timing Correction Candidate subsection with the
`PATCH-0048` correction note, `§18`, `§19` V-1…V-14, `§20` S2-1…S2-14. Traced:
`correction_candidate_admission.py`, `correction_candidate_decision.py`,
`corrected_revision_generation.py`, `timing_correction_candidate_admission.py`,
`corrected_revision_selection.py`, `TranscriptSegment`, `RawTranscript`, and the v54 relations.

Two filename deviations from the task description, noted for accuracy: the reports are
`139_HUMAN_TRANSCRIPT_TIMING_CORRECTION.md` and
`140_CORRECTION_COMPOSITION_AND_REVISION_CHAINING_DECISION.md`.

## 2. Defect reproduction

Executed against a real repository built through the released chain — `140` §12's description was
re-verified rather than assumed.

```text
R = replacement segment of the corrected revision generated from source segment S

R.identity            transcript-segment:c8b099dc…:0
R.transcript_id       raw-transcript:a4cd6712…          == the Raw Transcript's identity
R.replaces_segment_id transcript-segment:a4cd6712…:1    == S
R ∈ raw.segment_ids   False                             ← not a member of the Raw Transcript
R ∈ RT.segment_ids    True                              ← a member of the corrected revision

text  candidate targeting R : ADMITTED, then accepted, then
                              generation refused (CandidateNotApplicableError, V-4)
timing candidate targeting R : refused at admission (TimingSegmentLineageError)
```

The asymmetry is real and reproduces exactly as reported.

## 3. Contract classification — **A. Implementation Defect**

K-1's released wording decides this already:

> 후보는 **하나의 immutable Raw Transcript segment**를 target한다. … target segment는 그 Raw Transcript에,
> Raw Transcript는 intake에 속해야 한다. unknown·unrelated·malformed·stale 참조는 명시적으로 거부된다.

**Q1 — how is "belongs to that Raw Transcript" determined?** By membership in the transcript's
canonical ordered segments, not by the segment naming it. K-1 says 속해야 한다 ("must belong to"),
and V-4 already spells out the same test for generation — `admission.segment_id not in
raw_transcript.segment_ids`. The Blueprint uses one notion of belonging; only admission implemented a
weaker one.

**Q2 — what is a replacement segment?** A **derived, revision-scoped** segment. V-1 names it exactly:
*"교정 segment는 `replaces_segment_id`를 가진 새 revision-scoped `TranscriptSegment`"*. It is not an
original Raw Transcript segment; it references one through its lineage. The reproduction above shows
all three properties at once — it carries the Raw Transcript's `transcript_id`, it is absent from
`raw.segment_ids`, and it points at S via `replaces_segment_id`.

**Q3 — what would allowing it be?** Revision-on-revision chaining. A candidate targeting a revision's
segment, applied, would produce a revision derived from a revision. V-14 and S2-14 defer that, and
`PATCH-0048` RC-3 records that the released contract does **not** open that path. Allowing it would
un-defer chaining by accident.

**Q4 — is admission the right place to refuse?** Yes, and this is the distinction that matters.
K-9's non-applicable history covers a candidate that **validly satisfied K-1 at admission** and later
stopped applying because the current Raw Transcript changed — legitimate immutable evidence. A
replacement-segment target **never satisfied K-1 at any moment**: it is K-1's own "unrelated
reference", which K-1 says is 명시적으로 거부된다. "Generation blocks it later" is not a reason to
admit it; it produces a candidate that can be accepted by a person and then never applied, which
wastes a human decision on something the contract already refuses.

Because the Blueprint decides the question, **no PATCH, no schema change and no migration are
needed** — only the check.

## 4. Root cause

`correction_candidate_admission.py` tested lineage with:

```python
if segment.transcript_id != transcript_identity:
    raise SegmentLineageError("segment does not belong to the target raw transcript")
```

`corrected_revision_generation.py` builds the replacement with
`transcript_id=raw_transcript.identity` — correct, because V-1's revision-scoped segment belongs to
that transcript's lineage — so the comparison passes for a segment that is not in the transcript's
membership. The timing path never had the hole because TC-7's neighbour check needs the segment's
position in `raw_transcript.segment_ids` and fails first.

## 5. Fix

One check added in `correction_candidate_admission.py`, plus moving the already-present
`raw_transcript` lookup three statements earlier so the membership test can use it:

```python
if segment_identity not in raw_transcript.segment_ids:
    raise SegmentLineageError(
        "segment is not part of the target raw transcript "
        "(a corrected revision's replacement segment is not a Raw Transcript segment)"
    )
```

It reuses the canonical membership the repository already holds. **No new abstraction, no new
persistence field, no new schema, no new candidate type, no new revision semantics.** The error joins
the existing `SegmentLineageError` family, which is K-1's own vocabulary for unrelated references.

The lookup move is behaviour-neutral: it is a read, and its only failure branch is a defensive
`RawTranscriptNotCurrentError` that the current-selection check already makes unreachable.

## 6. Contract mapping

| contract | relationship |
|---|---|
| **K-1** | now enforced as written — membership, not naming |
| **K-8** | unchanged — several distinct candidates per Raw segment still coexist (Test C) |
| **K-9** | **not narrowed** — a validly admitted candidate that later stops applying is still preserved as non-applicable history, asserted by its own test |
| **V-1** | unchanged — the replacement segment keeps its revision-scoped definition |
| **V-4** | unchanged — generation still performs its own membership check, and still refuses a pre-existing record (Test E's second case) |
| **V-14 / S2-14** | preserved — the accidental chaining path is closed, and no chaining is enabled |
| **PATCH-0047** | timing admission untouched — its refusal still comes from its own check |
| **PATCH-0048** | composition deferral untouched; `MORE_EVIDENCE_REQUIRED` unmoved |

## 7. Files changed

```text
src/lectureos/application/correction_candidate_admission.py   +18 / -6  (guard + docstring)
tests/test_correction_candidate_replacement_target_guard.py   new, 10 tests
implementation/141_TEXT_CORRECTION_REPLACEMENT_SEGMENT_GUARD.md  new
```

`docs/`, `patches/`, schema and migrations: **0 changes**.

## 8. Regression tests

| | test | asserts |
|---|---|---|
| **A** | original Raw segment admitted | all three fixture segments still admit |
| **B** | replacement segment refused **at admission** | `SegmentLineageError`, and no row written |
| **C** | original still admissible after a revision exists | K-8 + Raw immutability, through to generation |
| **D** | timing admission unchanged | Raw segment admits, replacement refused by its own check |
| **E** | no chaining introduced | both kinds refuse; no revision has a `parent_revision_id` |
| **F** | normal E2E | candidate → decision → generation → selection → corrected effective transcript |
| — | why the released check let it through | R names the transcript, is absent from its membership, and replaces S |
| — | pre-guard record still refused at V-4 | an already-persisted replacement-target candidate behaves exactly as before |
| — | K-9 untouched | a candidate admitted against a real Raw segment survives a Raw-selection switch as preserved, non-applicable history |

## 9. Preservation

Existing persisted records are **not** touched. No migration, no backfill, no rewrite, no delete, no
reinterpretation. A replacement-target candidate that a pre-guard repository may already hold stays
exactly where it is and keeps its existing behaviour — admitted, decidable, and refused at generation
by V-4 — which one test asserts directly. The guard changes only what happens at **new** admissions.

## 10. Full validation

```text
focused (new)             10 tests    OK
complete suite         3,680 tests    OK   (3,670 before + 10)
compile                python -m compileall src/lectureos   OK
git diff --check       clean
repository validator   healthy, 0 diagnostics, schema_version 54
SQLITE_SCHEMA_VERSION  54 (unchanged)
migrations added       0
docs/ and patches/     0 changes
working tree           clean apart from the pre-existing untracked input media
```

## 11. Remaining risks

- **Legacy replacement-target candidates are left in place.** If any repository already holds one, it
  remains admitted and acceptable but unapplicable. That is deliberate — rewriting persisted records
  would violate the immutability this whole subsystem rests on — but it means such a record can still
  consume a human decision. Detecting them is a validator question, not an admission one, and no
  diagnostic was added because `140` §12 established this is not corruption.
- **The guard is text-side only.** The timing path refuses the same target for an unrelated reason
  (TC-7 needs the ordinal). If TC-7's neighbour check were ever relaxed, the timing path would inherit
  the same hole. Making the membership test explicit there too was out of this fix's scope.
- **`V-4` and this guard now duplicate one condition.** That is intentional defence in depth — V-4
  must keep its own check for records admitted before the guard existed — but the two must stay in
  agreement if K-1's notion of membership ever changes.

## 12. What this fix deliberately did not do

No composition, no revision chaining, no un-deferral of V-14 or S2-14, no change to timing correction,
no change to Final Selection or the subtitle pipeline, no Raw Transcript mutation, no schema change,
no migration, no backfill, no Blueprint edit, and no PATCH.
