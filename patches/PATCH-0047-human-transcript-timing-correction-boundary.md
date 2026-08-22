# PATCH-0047

- Title: Human Transcript Timing Correction Boundary (040 §17/§18/§19/§20)
- Status: Accepted
- Priority: Medium
- Trigger: `PATCH-0046` released a timing diagnostic with no way to act on it;
  `implementation/137` measured the population it flags; `implementation/138` closed the boundary
  decision at `PATCH_READY`
- Created: 2026-08-22
- Target Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` (§17/§18/§19 forward notes and sibling
  subsections; §20 timing-authority note; header amended) and `docs/030_DATA_MODEL.md` (three
  additive relations). `docs/041_SUBTITLE_PIPELINE.md` is **not** amended — see TC-13.

---

## Status

**Accepted.** Applied to `docs/040_TRANSCRIPT_PIPELINE.md` (Blueprint 0.5, 2026-08-22) as a `§17`
forward note, the `Human Timing Correction Candidate` sibling subsection carrying TC-1…TC-9 and
TC-16…TC-21 with its own Canonical Invariants, and forward notes on `§18` (TC-10, TC-11), `§19`
(TC-12, TC-15) and `§20` (TC-13, TC-14). `docs/030_DATA_MODEL.md` `§6.2` gains one conceptual
cross-reference clause. `docs/041_SUBTITLE_PIPELINE.md` is not amended (TC-14).

**Acceptance means the contract has been applied to the Blueprint. It does not mean the capability
has been implemented.** The Implementation Requirements below remain outstanding and are the
implementing milestone's gate: no schema relation exists, `SQLITE_SCHEMA_VERSION` stays **53**, and
no production code or test was changed by the application.

One divergence from *Required Blueprint Changes*, recorded rather than resolved silently: item 6
names `docs/030_DATA_MODEL.md` as gaining "the new relations", but `030`'s released Purpose states it
"is not a physical or logical storage schema" and "does not define tables, fields, ID formats". Every
prior PATCH that added relations (`PATCH-0030`…`PATCH-0037`) gave `030` a single conceptual
cross-reference clause instead, and that precedent was followed here. The three relations themselves
are contracted by TC-19 and written at implementation time, exactly as TC-19 states.

It introduces **no numeric threshold, no automatic proposal, no media access at admission, no new
Human Authority concept, no new revision aggregate, and no downstream gate**. It rewrites no released
record, changes no released identity, regenerates no released artifact, and back-fills nothing. It
requires a **strictly additive** schema evolution, written at implementation time.

## Context

`PATCH-0046` released `TIMING_ALIGNMENT_REVIEW_REQUIRED`: a person can now be told that a segment's
start coincides with a decode-window anchor that opened over non-speech and is worth listening to.
Nothing follows. There is no canonical way to record what the person concluded.

`implementation/137` measured that population: of 31 firings in one lecture, 16 are under a second
and would reasonably be dismissed, but 8 carry two seconds or more and 4 exceed five, reaching 19.
Roughly eight material cases per lecture — real, and human-scale.

This PATCH contracts the path from that finding to a canonical corrected timing. It contracts **no
automation**: the person authors the proposal, the person accepts or rejects it, and provider
refinement stays Deferred.

## Blueprint evidence

Four released facts shape every decision below, and two of them foreclose the obvious design.

**`§17` K-2 rejects a no-op**: *"`no-op`(제안 text가 source text와 동일)은 거부된다"*, enforced at
`correction_candidate_admission.py:143`. **`correction_candidates.proposed_text` is `TEXT NOT NULL`.**
Together these mean a timing correction cannot ride the existing candidate by carrying the source text
unchanged — released admission would reject it — and making the column nullable is not an additive
change in SQLite. Serialising timing into `proposed_text` is meaning distortion of exactly the kind
K-2 exists to prevent.

**`§18` is not text-bound.** `correction_candidate_decisions` is
`(identity, correction_candidate_id, kind, reviewer, sequence, previous_decision_id, rationale,
content_fingerprint)`. No text column, no text semantics. H-1 records the decision as authority over a
*candidate*; H-2 fixes three states with Modify deferred.

**`§19` is not text-bound either.** `TranscriptSegment` carries `start`/`end`;
`CorrectedTranscriptRevision` carries `segment_ids`; the generator writes
`start=source_segment.start, end=source_segment.end` **because the candidate proposes text**, not
because anything forbids otherwise. Replacement identity derives from
`derive_generation_digest(candidate_identity, decision_identity)` — from provenance, not content.

**Downstream already renders whatever the selected revision's segments carry.**
`effective_subtitle_generation.py:284` reads `start=segment.start, end=segment.end`. The mechanism is
in place; what is missing is a released sentence saying it is authoritative (TC-13).

## Empirical evidence

From `implementation/137`, over the 31-firing P population of one lecture:

```text
< 1 s : 16 (51.6 %)     1–2 s : 6     ≥ 2 s : 8 (25.8 %)     ≥ 5 s : 4 (12.9 %)     max 19.05 s
```

**What this justifies:** non-trivial cases exist, at roughly eight per lecture.

**What it does not justify:** any threshold. `137` §2 records that the energy estimator agreed with
**0 of 4** human observations within ±5 s, so individual values are not ground truth and none of
`0.68`, `2.64`, `19.05` or the band edges may become a product number. The anchor-gap correlation is
contradicted by a 6.60 s drift at a 0.90 s gap and must not become an eligibility rule.

**What it says about workflow:** about half will be dismissed. **Rejection is the expected outcome**,
which is why TC-10 refuses to invent a state for it.

## Decision

### Scope

**TC-1 (Confirmed) — Scope.** This contract governs one path: a human-authored proposal to replace one
source segment's presentation timing, a human accept/reject over it, and the corrected revision that
an accepted proposal generates. It adds no gate, changes no stage's authority, and creates no Product
Domain concept beyond the sibling records it names.

### The candidate

**TC-2 (Confirmed) — A sibling candidate aggregate, not an extension of the text candidate.** The
released text candidate cannot express a timing correction (see Blueprint evidence), so a timing
correction is admitted as its own record. **`§17`'s released text semantics are unchanged** — K-1
through K-4 keep their meaning, and no existing column becomes nullable or polymorphic.

**TC-3 (Confirmed) — The candidate proposes a complete replacement interval, never a start alone.**
A start-only proposal silently redefines duration, and duration is what `041` readability measures —
a person proposing a start would be changing a cue's reading rate without saying so. It also cannot
express the observed cases: `137`'s largest is a 20.7 s segment whose speech begins roughly 19 s in,
where holding the original end leaves a 1.6 s cue. A person who has listened knows both boundaries.

**TC-4 (Confirmed) — Human-authored only.** The proposal states a value, and nothing in current
evidence can supply that value: the energy estimator is not ground truth (`137` §2), the anchor gap is
not a correction amount, and `PATCH-0046` TD-2 limits the diagnostic to *review-worthy*. A
machine-suggested, human-approved proposal is **Deferred**, not refused.

**TC-5 (Confirmed) — The diagnostic is not a prerequisite.** A person may author a timing correction
for any segment they have reason to doubt. Requiring a `TIMING_ALIGNMENT_REVIEW_REQUIRED` finding
first would make a provider-specific derived observation gate a human judgment, and `PATCH-0046`
TD-2's own limits argue against giving it that weight. Equally, **a finding never becomes a candidate
automatically** — the separation is diagnostic → optional cue, candidate → explicit human proposal,
decision → canonical authority.

### Admission

**TC-6 (Confirmed) — Admission checks structure, never acoustic truth.** It verifies what it can know
without media: the target segment exists and belongs to the intake's current Raw Transcript (K-1's
lineage rules); the proposed values are finite; `start >= 0` and `end > start` (A-10's structural
vocabulary); and the interval lies on the segment's source timeline.

It does **not** verify that the proposed interval matches actual speech. `§14` A-14 keeps provider
admission away from media, and the same restraint applies here for a different reason: **that judgment
belongs to the person, and `§18` is where it becomes canonical.** No drift, anchor-gap or readability
threshold participates.

**TC-7 (Confirmed) — The proposed interval must not overlap its neighbours in the target transcript,
judged as instants.** Ordering and non-overlap are checked against the adjacent segments using the
released `PATCH-0039` ε, so touching boundaries remain allowed and no new tolerance appears.

This is contracted rather than left open because the consequence is concrete:
`READABILITY_CUES_OVERLAP` is **BLOCKING** severity, and `PATCH-0042` enforces blocking findings at
Final Selection. An overlapping corrected revision would be admitted, accepted, generated — and then
**refused delivery**. Admitting a correction that cannot reach a subtitle would be a worse failure
than refusing it at the point where the person can still adjust it.

`implementation/138` TC-8 recorded this as an open Blueprint gap. **This PATCH closes it**, on the
released enforcement above rather than on preference.

**TC-8 (Confirmed) — A timing no-op is rejected, mirroring K-2.** A proposed interval identical to the
source interval, compared within the released ε, proposes nothing. K-2's principle — a candidate must
be an actual correction proposal — is not text-specific, and admitting a no-op would create a decision
with nothing to decide.

**TC-9 (Confirmed) — Stale protection is a source timing snapshot, mirroring K-3.** The candidate
carries the interval it believes it is replacing, and admission requires an exact match against the
persisted segment. Same purpose as K-3's text snapshot, same failure prevented: a proposal authored
against a segment that has since changed is refused rather than applied to something else.

### Human decision

**TC-10 (Confirmed) — `§18`'s semantics apply unchanged; a sibling relation carries them.** The
decision records that a person accepted or rejected one timing candidate. `DecisionKind(accept/reject)`,
`HumanActorReference`, append-only supersession and H-2's three states — Undecided derived from
absence, Accepted, Rejected — all hold without amendment, and **Modify stays deferred** exactly as
H-2 left it.

A sibling persistence relation is required only because
`correction_candidate_decisions` foreign-keys to `correction_candidates(identity)`; a timing candidate
in its own record cannot be referenced by it. H-1 met the analogous problem, declined to wrap one
candidate layer in another, and introduced the smallest additive aggregate reusing the existing value
types. **The same move is taken here, and no new authority, role or hierarchy is created.**

**TC-11 (Confirmed) — Rejection is a normal outcome, and gets no special state.** About half of the
diagnostic's findings are expected to be dismissed (`137`). "The source timing is correct" is a
complete and useful human judgment, fully expressed by `reject`. No `ignored`, `dismissed` or
`false_positive` state is introduced — inventing one would imply the diagnostic had made a claim that
turned out wrong, and TD-2 is explicit that it made no claim at all.

### Corrected revision

**TC-12 (Confirmed) — An accepted candidate generates a replacement segment through the existing
`§19` model.** The replacement carries the **source segment's text exactly** — A-11's preservation
requirement, with no re-interpretation, normalisation or trimming — the accepted proposed interval as
its `start`/`end`, and `replaces_segment_id` pointing at its source. No new revision aggregate and no
new revision type: `CorrectedTranscriptRevision` is used as released.

A sibling generation relation is required for the same foreign-key reason as TC-10, preserving the
provenance chain candidate → decision → replaced segment → replacement segment → revision.

**TC-13 (Confirmed) — A corrected revision's segment timing is that segment's canonical corrected
timing.** When a downstream boundary selects that revision, it uses those values as the transcript
timing it derives from.

This closes a gap rather than adding behaviour: `effective_subtitle_generation.py:284` already reads
`segment.start`/`segment.end`, and `041` §7 already requires that a Subtitle Unit's Time Range be
traceable to "근거가 된 Transcript 시간 구조". **This states what that structure is when a correction
has been accepted.** `041` §7's allowance for reading-driven adjustment is unaffected — it adjusts
*from* the transcript structure, and this sentence only names which structure. **No `041` change is
required** (TC-14).

**TC-14 (Confirmed) — `041` is not amended.** `§20`'s selection remains correction-kind-agnostic and
`041` remains unaware of what produced a revision's timing. Subtitle Time Representation gains no
authority to re-time source segments — `PATCH-0046` TD-14 stands.

### Identity and lineage

**TC-15 (Confirmed) — Identity follows the released provenance idiom; no new hash recipe is
contracted.** Replacement segment identity derives from the (candidate, decision) generation digest as
today, so a timing-only replacement is distinguished from its source automatically and the released
`replaced_segment_id <> replacement_segment_id` invariant holds without special handling. Two
different timing proposals for one source segment are two candidates and therefore two identities;
**the Blueprint fixes that requirement and leaves the derivation to the released idiom.**

### Preserved boundaries

**TC-16 (Confirmed) — Raw Transcript is immutable.** Provider timing and text are never rewritten.
§2 Raw Before Corrected, A-11 and `PATCH-0046` TD-13 hold unchanged; a correction lives entirely in
the revision lineage and remains traceable to its source Raw Transcript.

**TC-17 (Confirmed) — Released artifacts do not become stale and are never regenerated
automatically.** An existing Final Selection, SRT Artifact or Materialization remains the valid output
of the revision selected when it was made. A new artifact appears only when a person selects the
corrected revision and materializes again, through the released identity chain. **No retroactive
mutation, no automatic re-selection, no automatic re-materialization.**

### Composition

**TC-18 (Confirmed, and deliberately narrow) — Competing corrections on one segment are not composed
by this contract.** Text and timing corrections may both be authored against the same source segment.
Once either is accepted, the other's snapshot no longer matches the current segment, and TC-9's and
K-3's stale checks refuse it — which is **detection, not resolution**.

This contract therefore fixes only the safe boundary:

- **No automatic composition.** An implementation may not merge two corrections, apply them in a
  chosen order, or re-target a stale candidate on its own.
- **Sequential correction through the released lineage is available**, since `§19` already supports a
  revision whose parent is another revision — a person may correct text, then author a fresh timing
  candidate against the resulting revision.
- **What the product should do with a candidate made stale by a competing correction** — re-target,
  re-author, or refuse — is **Deferred** to its own decision.

`implementation/138` TC-16 recorded this gap. It is named here and left open on purpose: resolving it
requires product evidence this investigation has not gathered, and guessing would exceed this
contract's scope.

### Schema

**TC-19 (Confirmed) — Strictly additive, three sibling relations.** Timing candidates, their
decisions, and their generation records. Existing correction relations keep their columns,
constraints and meaning; none becomes nullable or polymorphic. Names follow repository convention and
the migration is written at implementation time, not here.

**TC-20 (Confirmed) — No backfill, and no inference over legacy records.** Existing correction,
decision, revision and artifact rows are untouched. A record created before this capability existed is
**not** "timing corrected", "reviewed" or "clean" — it simply has no timing correction, and nothing may
infer otherwise.

### Refinement

**TC-21 (Confirmed) — Provider refinement stays Deferred and is not selected here.** No VAD, no word
timestamps, no forced alignment, no energy alignment, no refinement algorithm. `implementation/136`
TR-1…TR-4 placed refinement at `§15` provider execution producing a distinct Raw Transcript, behind
`§15` L-16's two conditions — timestamp improvement **and** real-speech preservation — of which only
the second has been quantified.

Accepted human corrections will incidentally form human-verified intervals usable as reference when a
mechanism is eventually evaluated. That is a **side effect, not a purpose**: this contract creates no
labeling programme and no new persistence obligation.

## Non-goals

Not decided here, each requiring its own gate: automatic timing proposals; any drift, anchor-gap or
readability threshold; a timing editor or interface; Modify; composition of competing corrections
(TC-18); regeneration or invalidation of released artifacts; publication or export policy; VAD, word
timestamps, alignment or any refinement mechanism; changes to the timing or hallucination diagnostics;
readability parameter changes; and everything already deferred by `PATCH-0045` and `PATCH-0046`.

## Required Blueprint Changes

Applied to `docs/040_TRANSCRIPT_PIPELINE.md`, plus `docs/030_DATA_MODEL.md` for the new relations.

1. **Header** — Blueprint version and Last Updated advanced; `PATCH-0047` added to `Amended By`.
2. **§17** — released text kept verbatim; forward note recording that K-1…K-4 govern **text**
   corrections and are unchanged, that a timing correction cannot be expressed by that record
   (K-2 no-op, `proposed_text NOT NULL`), and that a sibling candidate carries it — followed by a
   sibling subsection carrying TC-2…TC-9.
3. **§18** — released text kept verbatim; forward note recording that H-1/H-2 semantics apply to
   timing candidates unchanged, that a sibling persistence relation exists only for the foreign key,
   and that rejection is a normal outcome needing no new state (TC-10, TC-11).
4. **§19** — released text kept verbatim; forward note recording that the generator's timing copy
   reflects the text candidate rather than a restriction, and that an accepted timing candidate
   produces a replacement segment preserving source text with the proposed interval (TC-12, TC-15).
5. **§20** — forward note recording that a corrected revision's segment timing is canonical for that
   segment and is what a selecting downstream boundary derives from (TC-13), with `041` unamended.
6. **Canonical Invariants** for the new subsection.

`docs/041_SUBTITLE_PIPELINE.md` is not amended (TC-14).

## PATCH Acceptance Criteria

Verified against the Blueprint amendment, before this PATCH may be marked `Accepted`.

- [x] `§17`'s released text-correction semantics (K-1…K-4) are unchanged, and the timing candidate is
      stated a **sibling** with the K-2 / `NOT NULL` evidence recorded.
- [x] The candidate is stated to propose a **complete replacement interval**, with the start-only
      rejection reasoned rather than asserted.
- [x] The proposal is stated **human-authored**, and the diagnostic is stated **not a prerequisite**
      and never automatically converted into a candidate.
- [x] Admission is stated to check structure only and **never acoustic truth**, with no threshold of
      any kind.
- [x] Non-overlap against neighbours is contracted, using the released `PATCH-0039` ε and no new
      tolerance.
- [x] A timing no-op is rejected, and a source-timing snapshot guards staleness.
- [x] `§18` accept/reject semantics are stated unchanged, the sibling relation is stated to exist only
      for the foreign key, and **rejection is stated a normal outcome with no new state**.
- [x] An accepted candidate is stated to produce a replacement segment **preserving source text
      exactly**, with the proposed interval and `replaces_segment_id` lineage.
- [x] **Corrected revision timing authority is stated** (TC-13), and `041` is confirmed unamended.
- [x] Identity is stated to follow the released provenance idiom, with distinct proposals yielding
      distinct identities and no new hash recipe fixed in the Blueprint.
- [x] Raw Transcript immutability is stated intact.
- [x] Released artifacts are stated not stale, never auto-selected, never auto-regenerated.
- [x] Text + timing composition is stated **Deferred with an explicit safe boundary** — no automatic
      composition, no implementation-chosen ordering.
- [x] Schema evolution is stated **strictly additive**, with no existing column made nullable or
      polymorphic, and **no backfill or inference over legacy records**.
- [x] Provider refinement is stated Deferred and no mechanism is selected.
- [x] No released sentence in `docs/040` is deleted or rewritten — prior PATCH notes included —
      verified line by line; §17, §18, §19 and §20 gain **additive forward notes and subsections
      only**.

## Implementation Requirements

Required validation for the implementing milestone. **Not satisfied by this PATCH.**

1. A strictly additive migration adds the three sibling relations; every previously released schema
   version reaches the new one through the supported single-step chain with no row rewritten and no
   data or meaning lost.
2. Timing candidate admission enforces TC-6 through TC-9: lineage, finite positive interval, timeline
   membership, neighbour non-overlap within the released ε, no-op rejection, and snapshot staleness.
3. Admission reads no media, and consults no diagnostic, drift, anchor-gap or readability value.
4. A timing candidate can be admitted with **no** `TIMING_ALIGNMENT_REVIEW_REQUIRED` finding present.
5. No code path converts a diagnostic finding into a candidate.
6. Decision persistence reuses `DecisionKind` and `HumanActorReference` with append-only supersession;
   `reject` is exercised as a first-class outcome and introduces no state beyond H-2's three.
7. An accepted candidate generates a replacement segment whose text is **byte-identical** to the
   source and whose interval is the accepted proposal, with `replaces_segment_id` lineage and a
   distinct identity — asserted, including that two proposals for one source segment do not collide.
8. Raw Transcript rows, provider timing and existing correction/decision/revision records are
   unchanged by any timing correction — asserted.
9. Selecting a corrected revision produces subtitle cues carrying the corrected timing, end to end
   through SRT artifact and materialization, with released artifacts untouched until an explicit new
   selection and materialization.
10. Existing text correction, decision, revision, Final Selection and SRT behaviour regress cleanly.
11. Repository validation reports healthy; schema version advances by exactly one step; the complete
    test suite passes.

## Consequences

- `§17`, `§18` and `§19` gain sibling subsections; `§20` gains a timing-authority note; released text
  is untouched throughout.
- `docs/030` gains three additive relations; the schema version advances at implementation time.
- A person can, for the first time, record a canonical judgment about transcript timing — and record
  that the timing was **already right**, which about half the diagnostic's findings are expected to be.
- Raw Transcripts, released selections and released SRTs are entirely unaffected until someone
  explicitly selects a corrected revision and materializes again.
- `PATCH-0046`'s diagnostic stops being inert. It remains what TD-2 made it — an invitation to listen,
  not a verdict — and this contract adds no weight to it.
- Provider refinement remains Deferred, with L-16's two conditions still the gate, and accepted human
  corrections become available as reference evidence when that evaluation eventually happens.
