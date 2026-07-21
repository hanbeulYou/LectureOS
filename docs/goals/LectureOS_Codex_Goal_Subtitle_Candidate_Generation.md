# LectureOS Codex Goal — Subtitle Candidate Generation

> **Inheritance notice.** Governed by `AGENTS.md` (auto-loaded via `CLAUDE.md`).
> Do **not** restate durable operating policy here. The autonomous slice loop,
> Stop Conditions, additive-migration compatibility, Blueprint Drift Check, review
> policy, validation checklist, Goal Self-Maintenance mechanics, and the base
> Consolidated Completion Report skeleton are **inherited** from
> `AGENTS.md → "Milestone Execution Protocol"`. This Goal specifies only what is
> unique to this milestone.
>
> ```text
> AGENTS.md          → repository-wide durable operating policy (inherited)
> Goal Template      → milestone selection and implementation details only
> Historical Goal    → immutable audit record (never edited)
> ```
>
> Authored from `docs/goals/_TEMPLATE.md`. See `docs/goals/README.md`.

## How to read this document

- **Inherited repository policy** — the inheritance notice above; owned by `AGENTS.md`.
- **Milestone-specific implementation** — sections 1–7.
- **Milestone-specific validation** — section 8.
- **Milestone-specific completion-report additions** — section 10.

Section 9 tracks living status; section 11 records deliberate overrides.

## 1. Mission & Lifecycle Position

Establish the second Subtitle Pipeline stage (`041_SUBTITLE_PIPELINE.md §4.2 Subtitle
Candidate Generation`): from a canonical **ELIGIBLE** `SubtitleTranscriptIntake`,
deterministically propose one durable **Subtitle Candidate** plus an ordered collection
of candidate **Subtitle Units (cues)** derived from the source Corrected Transcript
revision's ordered segments, preserving transcript-revision and source-timeline lineage.
Lifecycle: `… → Transcript Ready → Subtitle Transcript Intake → **Subtitle Candidate
Generation** (this milestone) → Reading Representation → Time Representation → …`. A
candidate is an unapproved proposal (§4.2): it carries no reading/time refinement, no
validation, no review, no revision, no human decision, and starts nothing downstream.

## 2. Baseline

Start `HEAD c3cffaa`, branch `main`, `SQLITE_SCHEMA_VERSION 11`. Authority order
inherited from `AGENTS.md`.

## 3. Bounded Assessment & Architect Decision

The canonical **ELIGIBLE** `SubtitleTranscriptIntake` (v11) is the **sole admission
authority**; generation refuses a NOT_ELIGIBLE intake and does not re-derive
readiness/selection/applicability (that lineage is carried on the intake). Raw material
is the intake's `source_revision_id` → `CorrectedTranscriptRevision.segment_ids`
(ordered) via `get_segment(...)`, all durable v5 records; `source_media_id` /
`source_timeline_id` / `validation_id` are carried from the intake for provenance
(nothing recomputed).

**Architect Decision:** add new Application-owned durable types — aggregate
`SubtitleCandidate` (identity `SubtitleCandidateId`) and ordered child
`SubtitleCandidateCue` (identity `SubtitleCandidateCueId`), placed in `application/` and
`application/identities.py` and **never** cross-importing the in-memory `subtitle/`
domain (whose same-named identities remain unchanged and unused). No provider/capability
boundary — a provider-independent capability contract and a concrete AI provider are
deferred to later, separate Goals. Additive schema **v12** (first subtitle child table).
**Architect Checklist result: all No — additive.**

**Segment↔cue cardinality is not a domain invariant.** §4.2 forbids assuming a 1:1
Transcript-Unit → Subtitle-Unit correspondence, and §4.3–4.4 (Reading / Time
Representation) may later merge or split cues. Therefore the **durable data model must
permanently support one-to-many and many-to-one** relationships between transcript
segments and subtitle cues: a cue references an ordered tuple of ≥1 source segments
(many-to-one), and several cues may each reference the same segment (one-to-many). The
**initial deterministic, provider-free implementation** emits one cue per ordered source
segment purely as an **implementation strategy** for this milestone's baseline — it is
**not** a canonical contract and downstream stages must be free to depart from it without
any schema or model change.

## 4. Scope

- **Included:**
  - canonical `SubtitleCandidate` aggregate + ordered `SubtitleCandidateCue` collection
  - a durable cue model that supports one-to-many and many-to-one segment↔cue relationships
  - deterministic, provider-free baseline generation from a canonical **ELIGIBLE**
    `SubtitleTranscriptIntake` (one cue per ordered source segment — an implementation
    strategy, not a domain invariant)
  - refusal to generate for a NOT_ELIGIBLE intake
  - per-cue source lineage: ordered `source_segment_ids` (≥1), source timeline range,
    `source_revision_id`, `source_transcript_id`, `display_order`
  - carried readiness/intake lineage; `source_media_id`/`source_timeline_id`; carried
    `validation_id`; execution provenance; DomainResult linkage (`upstream = intake DomainResult`)
  - append-only `sequence`/`previous_candidate_id`
  - atomic SQLite **v12** persistence (parent + ordered cue child + co-persisted
    `DomainResultReference`); restart reconstruction; deterministic replay
  - migration compatibility (v1..v11 → v12)
  - fake-review / fake-transcript acceptance driving intake → candidate generation
- **Excluded:**
  - Reading Representation (§4.3); Time Representation refinement (§4.4); Subtitle
    structural Validation (§4.5); Subtitle Review Preparation/Decision (§4.6–4.7); Final
    Subtitle (§4.8)
  - subtitle revisions; human decision / applicability / final selection
  - any AI provider or capability port; reading-policy thresholds; timing recalculation
  - actual cue merging or splitting logic (the model must support it; this milestone
    does not implement it)
  - Artifact generation / export; downstream execution
  - changes to the transcript, readiness, intake, or in-memory subtitle contracts

Generating a candidate mutates no upstream record and starts no downstream capability.

## 5. Canonical Model

- **Identities:** `SubtitleCandidateId`, `SubtitleCandidateCueId` (`OpaqueIdentity`, in
  `application/identities.py`; distinct from the in-memory `subtitle/` identities).
- **Aggregate `SubtitleCandidate`:** `identity`; `domain_result_id`; `source_intake_id`;
  `source_transcript_id`; `source_revision_id`; `source_media_id`; `source_timeline_id`;
  `validation_id` (carried); carried intake lineage (`source_readiness_id`,
  `source_selection_id`, `source_applicability_id`, `source_decision_id`, `review_item_id`,
  `candidate_reference_id`); ordered `cue_ids`; `run_id`; `unit_execution_id`; `sequence`;
  `previous_candidate_id`; `reason`. Invariants: non-empty ordered cues; unique cue ids;
  non-negative sequence; non-blank reason; first has no previous reference; no
  human-decision / applicability / final field (a candidate is an unapproved proposal).
- **Record `SubtitleCandidateCue` (Subtitle Unit):** `identity`; `candidate_id`;
  `source_transcript_id`; `source_revision_id`; ordered `source_segment_ids` (≥1);
  `source_timeline_id`; `start`/`end` (finite, `0 ≤ start ≤ end`); `text` (non-blank);
  `display_order` (non-negative). The ordered `source_segment_ids` tuple carries
  many-to-one provenance; distinct cues referencing the same segment carry one-to-many
  provenance. No reading-optimization / line-wrap / merge / split fields (deferred to
  §4.3–4.4).
- **Baseline generation strategy (not a domain invariant):** for each ordered source
  segment of the revision, emit exactly one cue carrying that segment as its sole source,
  its own time range, its text, and its ordinal as display order.
- **Identity plan:** `SubtitleCandidateIdentityPlan(candidate_id, candidate_result_id,
  cue_ids: tuple[...])`, caller-owned; cardinality/uniqueness validated against the
  derived cue count.

## 6. Persistence

Additive SQLite **v12**: `subtitle_candidates` parent table + ordered
`subtitle_candidate_cues` child table (ordinal-indexed, FK to parent; the first subtitle
child table), plus an owned ordinal child for each cue's `source_segment_ids` so the
one-to-many / many-to-one provenance is stored losslessly. Co-persist a
`DomainResultReference` (kind `subtitle_candidate`, `upstream = (intake DomainResult,)`,
`source_media`/`source_timeline` from intake) in one `BEGIN IMMEDIATE` transaction with
linkage + identity-absence checks and complete rollback on any collision/linkage/write/
commit failure. `_migrate_v11_to_v12` additive; downgrades and direct skips rejected;
every released version v1..v11 chains to v12 preserving existing data and meaning.

## 7. Slice Sequence

### Slice 1 — Goal Baseline and Assessment

Review: Optional — Skipped. Commit: `docs: add subtitle candidate generation goal`

### Slice 2 — Candidate Records

`SubtitleCandidateId`, `SubtitleCandidateCueId`, `SubtitleCandidate`,
`SubtitleCandidateCue`, `SubtitleCandidateIdentityPlan`, `SUBTITLE_CANDIDATE_RESULT_KIND`,
exports, focused record tests (invariants, ordering, lineage, multi-segment cue).
Review: Required — Executed. Commit: `feat: add subtitle candidate records`

### Slice 3 — Deterministic Candidate Generation Service

`SubtitleCandidateGenerationService.generate_candidate(...)` loads the ELIGIBLE intake +
source revision/segments, requires a running execution, refuses NOT_ELIGIBLE intake,
deterministically derives ordered cues (baseline strategy), validates the identity plan,
and builds the `PreparedSubtitleCandidate` (no write). Review: Required — Executed.
Commit: `feat: derive subtitle candidate from eligible intake`

### Slice 4 — Atomic SQLite Persistence, Restart, Replay and Migration Compatibility

Additive schema v12, parent + ordered cue child (+ cue-segment child) repositories, atomic
command, composition, `record_candidate` path, restart/replay, v1..v11 → v12 compatibility,
idempotency. Review: Required — Executed. Commit: `feat: persist subtitle candidate atomically`

### Slice 5 — Fake-Review / Fake-Transcript Acceptance

End-to-end: ELIGIBLE intake → candidate + ordered cues; NOT_ELIGIBLE intake → refused;
persist → reopen → identical reconstruction → identical replay → idempotent upstream → no
downstream (no reading/time/validation/review/revision/final/artifact table). Review:
Optional — Skipped (harness/test only). Commit: `test: verify subtitle candidate generation acceptance`

## 8. Milestone-Specific Verify

Candidate generated only from a canonical **ELIGIBLE** `SubtitleTranscriptIntake`; **a
NOT_ELIGIBLE intake yields no candidate**; each cue traces to ≥1 ordered source segment,
the source timeline range, and the source revision; candidate carries exact
intake/readiness lineage and carried `validation_id`; the durable model round-trips
many-to-one (multi-segment cue) and one-to-many (multiple cues per segment) provenance;
immutable records; duplicate-identity / DomainResult / cue-cardinality mismatches roll
back atomically; identical canonical input + identity plan → byte-identical candidate +
ordered cues; replay after restart → byte-equivalent; repeated generation mutates no
upstream (intake/readiness/revision/segment) record; **no reading/time refinement,
validation, review, revision, final subtitle, provider, or artifact behavior is
produced**. (Generic validation inherited.)

## 9. Status (living)

### Completed Capabilities

```text
None yet
```

### Remaining Milestones

```text
Slice 1 — Goal Baseline and Assessment
Slice 2 — Candidate Records
Slice 3 — Deterministic Candidate Generation Service
Slice 4 — Atomic SQLite Persistence, Restart, Replay and Migration Compatibility
Slice 5 — Fake-Review / Fake-Transcript Acceptance
```

### Immediate Next Slice

```text
Slice 1 — Goal Baseline and Assessment
```

## 10. Completion Report — Milestone Additions

Beyond the inherited base skeleton, add: Canonical Subtitle Candidate Model; Baseline
Generation Strategy vs Non-Invariant Cardinality; Cue Provenance / Lineage; Persistence
Model (parent + ordered child + cue-segment child); Restart and Replay Acceptance;
Migration Compatibility; Idempotency Verification; Provider-Boundary Deferral Note.

## 11. Milestone Overrides (optional)

None — this milestone uses the inherited critical-only review policy and all default
execution behavior without deviation.
</content>
</invoke>
<invoke name="Read">
<parameter name="file_path">/Users/hanbyeol/Desktop/LectureOS/src/lectureos/persistence/subtitle_intake.py