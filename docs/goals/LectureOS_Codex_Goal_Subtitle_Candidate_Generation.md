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
Slice 1 — Goal Baseline and Assessment
- commit `eaefea3` — `docs: add subtitle candidate generation goal`
- bounded assessment: no substantive blocker; candidate generation consumes the canonical
  ELIGIBLE SubtitleTranscriptIntake (v11); provider-free deterministic baseline; additive
  schema v12 planned; in-memory subtitle domain left unchanged; segment↔cue cardinality is
  not a domain invariant (durable model supports one-to-many and many-to-one)
- Review: Optional — Skipped (documentation only)

Slice 2 — Candidate Records
- commit `6157ac1` — `feat: add subtitle candidate records`
- `SubtitleCandidateId`, `SubtitleCandidateCueId` added to application identities
- `SubtitleCandidateCue`: identity, candidate linkage, ordered `source_segment_ids` (>=1),
  optional source timeline + optional finite time range (untimed allowed; timed requires
  timeline and 0<=start<=end), non-blank text, non-negative display order
- `SubtitleCandidate`: identity, DomainResult linkage, intake + readiness lineage, transcript
  + revision + media/timeline, carried `validation_id`, ordered unique `cue_ids`, execution
  provenance, append-only sequence/previous linkage, deterministic reason
- `SubtitleCandidateIdentityPlan` (candidate id, result id, ordered unique cue ids)
- durable cue model supports one-to-many (many cues per segment) and many-to-one (multi-segment
  cue) provenance; no human-decision / applicability / final field
- 21 focused record tests passed; complete suite 872 passed
- Required Claude Review: Inconclusive — no critical findings identified (additive immutable
  records; cardinality-non-invariant enforced; no Blueprint/lifecycle/contract defect)

Slice 3 — Deterministic Candidate Generation Service
- commit `4656f3b` — `feat: derive subtitle candidate from eligible intake`
- `SubtitleCandidateGenerationService.generate_candidate(...)` loads the canonical ELIGIBLE
  intake, requires a running execution, refuses a NOT_ELIGIBLE intake, loads the source
  revision's ordered segments, and deterministically derives one cue per ordered source segment
  (baseline strategy, not a domain invariant), preserving revision/timeline/segment lineage
- carries the full intake lineage into the candidate; candidate DomainResult upstream = the
  intake DomainResult; no wall-clock; performs no write; mutates no upstream record; triggers
  no downstream capability
- `PreparedSubtitleCandidate` return; `AtomicSubtitleCandidatePersistence` port;
  `SubtitleTranscriptIntakeQuery` protocol; `SubtitleCandidateGenerationError` for unsafe input
- 8 focused service tests (ELIGIBLE 2-cue lineage/ordering, untimed cues, NOT_ELIGIBLE refusal,
  identity-plan cardinality, unknown intake, running-execution, determinism, no-persistence)
  passed; complete suite 880 passed
- Required Claude Review: Inconclusive — no critical findings identified (pure deterministic
  derivation; no persistence, no upstream mutation, no downstream trigger)

Slice 4 — Atomic SQLite Persistence, Restart, Replay and Migration Compatibility
- commit `bb8ad13` — `feat: persist subtitle candidate atomically`
- additive SQLite schema v12: `subtitle_candidates` parent + ordered `subtitle_candidate_cues`
  child (UNIQUE(candidate, ordinal), timed/untimed CHECK) + `subtitle_candidate_cue_segments`
  ordinal child preserving one-to-many / many-to-one segment provenance losslessly
- `_migrate_v11_to_v12` additive; downgrades and direct skips rejected; existing v1–v11 tables
  and rows unchanged
- `SQLiteSubtitleCandidateCommandPersistence.persist_subtitle_candidate(...)` writes the
  candidate, its ordered cues (+ cue-segment children) and the DomainResultReference in one
  `BEGIN IMMEDIATE` transaction; validates linkage/cue-ordering and identity absence; rolls back
  completely on collision/linkage/write/commit failure; writes no upstream mutation
- `SQLiteSubtitleCandidateRepository` reconstructs the exact candidate + ordered cues after restart
- composition `compose_sqlite_subtitle_candidate_generation_service` wires the durable intake
  query + transcript service + candidate persistence
- migration compatibility verified: every released version v1..v11 chains to v12 preserving data;
  idempotency verified (upstream intake row byte-identical); superseded-latest test expectations
  updated (v2/v3/v4/v5/processing_units 11→12; v6..v11 unsupported-target guards 12→13; v9/v10/v11
  chain helpers extended with the v11 addition block; v11 no-op/fresh-init realigned to the
  superseded-version pattern); prior readiness/intake acceptance downstream checks adapted to the
  additive candidate tables (candidate rows must be zero)
- 13 focused v12 tests (migration, full v1..v11→v12 chain, restart, replay, idempotency, atomic
  rollback of candidate + cues + cue-segments) passed; complete suite 893 passed
- Required Claude Review: PASS — independent bounded review verified atomicity/rollback, ordered
  cue + segment reconstruction, identity-collision atomicity, provenance linkage, additive
  migration, migration-chain compatibility, and DDL/expected-columns exactness; no critical findings

Slice 5 — Fake-Review / Fake-Transcript Acceptance
- commit `1aec047` — `test: verify subtitle candidate generation acceptance`
- `lectureos.subtitle_candidate_acceptance` drives the full pipeline with a fake correction
  provider and fake reviewer (no network, no credential, fixed timestamps): fake proposals →
  proposed Revision → Review Preparation → Accept/Reject → applicability → selection → readiness →
  subtitle transcript intake → subtitle candidate generation → atomic v12 persistence → reopen →
  exact restart reconstruction → identical deterministic replay
- verifies only the ELIGIBLE intake yields a candidate and the NOT_ELIGIBLE intake is refused;
  1 candidate, 2 ordered cues; cue→segment/revision/transcript lineage; candidate intake lineage
  and media/timeline; execution provenance; result upstream = intake DomainResult; idempotency
  (upstream intake rows byte-identical); restart reconstruction; deterministic replay; and no later
  subtitle-revision / subtitle-cue / artifact table produced
- acceptance summary: candidate_count 1, cue_count 2, every linkage / provenance / restart /
  replay / idempotency / refusal / no-downstream flag true
- focused acceptance test passed; complete suite 894 passed
- Blueprint Drift Check: PASS — dependency direction unchanged, no provider owns candidate
  identity/lifecycle, no existing enum/aggregate/service meaning changed (the in-memory subtitle
  domain is untouched), schema strictly additive, no reading/time/validation/review/final/artifact
  responsibility pulled in, Human Authority intact, Subtitle remains distinct from Transcript
- Migration Compatibility: PASS — every released version v1..v11 chains to v12 preserving data
- Claude Review: Optional — Skipped (acceptance harness/test only; no production or contract change)
```

### Remaining Milestones

```text
None — Goal complete
```

### Immediate Next Slice

```text
Goal Complete
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