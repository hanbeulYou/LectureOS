# LectureOS Codex Goal — Subtitle Reading Representation

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

Establish the third Subtitle Pipeline stage (`041_SUBTITLE_PIPELINE.md §4.3 Reading
Representation`, §6): from a canonical `SubtitleCandidate` and its ordered cues,
deterministically compose one **new immutable subtitle reading revision** plus an
ordered collection of **reading units** that carry an explicit, reading-oriented text
form (line composition) produced by a deterministic, meaning-preserving normalization,
while preserving complete provenance back to the source cues and transcript segments.
Lifecycle: `… → Subtitle Candidate Generation → **Reading Representation** (this
milestone) → Time Representation → Subtitle Structural Validation → …`. Reading
Representation is a responsibility perspective of subtitle composition (§13); it
produces a new revision that never overwrites the candidate, owns no time semantics, and
carries no validation, no review, no human decision, and starts nothing downstream.

## 2. Baseline

Start `HEAD e16e667`, branch `main`, `SQLITE_SCHEMA_VERSION 12`. Authority order
inherited from `AGENTS.md`.

## 3. Bounded Assessment & Architect Decision

The canonical `SubtitleCandidate` (v12) is the **sole admission authority**; reading
composition reads it and its ordered cues (`SQLiteSubtitleCandidateRepository.get` /
`get_cue`) and re-consults nothing upstream (the candidate carries the lineage; the
immutable cues carry `source_segment_ids`, timeline and time range). Reading operates
purely on cues — no transcript access is needed.

**Architect Decision:** add new Application-owned durable types —
`SubtitleReadingRevision` (identity `SubtitleReadingRevisionId`) and ordered child
`SubtitleReadingUnit` (identity `SubtitleReadingUnitId`) — in `application/` and
`application/identities.py`, never cross-importing the in-memory `subtitle/` domain.
No provider/capability boundary (a future AI-assisted reading generator is a separate
later Goal). Additive schema **v13**.

**Reading optimization produces a new immutable representation, not a mutation.** The
candidate and its cues are immutable and unchanged; the reading revision is a new
append-only aggregate linked to the parent candidate (§8.4 forbids overwrite).

**The baseline performs a deterministic reading transformation, not a pure structural
copy.** It applies threshold-independent, meaning-preserving normalization — whitespace
normalization (collapse internal whitespace runs, trim) and line composition that
preserves the source text's existing hard-line structure — to produce each unit's
ordered `lines`. It does **not** apply policy-driven merge/split or readability-threshold
logic, which §4.3/§6 defer.

**Merge/split cardinality is not a domain invariant.** The durable model **permanently
supports** cue merge (a unit references an ordered tuple of ≥1 source cues) and split
(distinct units reference the same cue) with complete deterministic provenance; only
policy-based merge/split is deferred. The baseline emits one reading unit per candidate
cue as an implementation-strategy default.

**Timing is inherited metadata, not time authority.** Reading Representation must not own
time semantics (§4.4 Time Representation owns time). Each unit **inherits** its source
cue's timeline and time range as provenance-only metadata; the milestone computes,
infers, and reorders no timestamps. **Architect Checklist result: all No — additive.**

## 4. Scope

- **Included:**
  - canonical `SubtitleReadingRevision` aggregate + ordered `SubtitleReadingUnit` collection
  - a durable model that supports cue merge (many cues → one unit) and split (one cue →
    many units) with complete provenance to source cues and transcript segments
  - explicit reading structure: ordered non-blank `lines` per unit (line composition)
  - a deterministic, provider-free, meaning-preserving baseline transformation:
    whitespace normalization and line composition preserving existing hard-line structure
    (threshold-independent; not a pure copy); one reading unit per ordered source cue as
    an implementation-strategy default
  - admission solely from a canonical `SubtitleCandidate`
  - per-unit source lineage: ordered `source_cue_ids` (≥1); carried transcript/revision;
    **inherited** timeline and time-range metadata from the single source cue (baseline),
    left unpopulated where a unit does not map to exactly one cue (time owned by §4.4)
  - carried candidate/intake lineage; media/timeline; carried `validation_id`; execution
    provenance; DomainResult linkage (`upstream = candidate DomainResult`)
  - append-only `sequence`/`previous_reading_revision_id`
  - atomic SQLite **v13** persistence; restart reconstruction; deterministic replay
  - migration compatibility (v1..v12 → v13)
  - fake-review / fake-transcript acceptance driving candidate → reading representation
- **Excluded:**
  - Time Representation logic (§4.4): owning, computing, inferring, or reordering time ranges
  - reading-speed validation; Subtitle structural Validation (§4.5)
  - policy-based / threshold-driven cue merge, split, or line-wrapping (model supports the
    structure; this milestone applies no policy)
  - Subtitle Review Preparation/Decision (§4.6–4.7); Final Subtitle (§4.8)
  - human decision / applicability / final selection; artifact generation / export
  - any AI provider or capability port; concrete readability thresholds
  - changes to the candidate, intake, transcript, or in-memory subtitle contracts

Composing a reading revision mutates no upstream record and starts no downstream capability.

## 5. Canonical Model

- **Identities:** `SubtitleReadingRevisionId`, `SubtitleReadingUnitId` (`OpaqueIdentity`,
  in `application/identities.py`).
- **Aggregate `SubtitleReadingRevision`:** `identity`; `domain_result_id`;
  `source_candidate_id`; carried candidate lineage (`source_intake_id`,
  `source_readiness_id`, `source_selection_id`, `source_applicability_id`,
  `source_decision_id`, `review_item_id`, `candidate_reference_id`); `source_transcript_id`,
  `source_revision_id`, `source_media_id`, `source_timeline_id`, `validation_id`; ordered
  `unit_ids`; `run_id`, `unit_execution_id`; `sequence`, `previous_reading_revision_id`;
  `reason`. Invariants: non-empty ordered units; unique unit ids; non-negative sequence;
  non-blank reason; first has no previous reference; no human-decision/applicability/final field.
- **Record `SubtitleReadingUnit`:** `identity`; `reading_revision_id`; ordered
  `source_cue_ids` (≥1, unique); `source_transcript_id`, `source_revision_id`; ordered
  `lines` (≥1, each non-blank); `display_order` (≥0); inherited timing metadata
  `source_timeline_id | None`, `start | None`, `end | None` (both-null or both-present with
  timeline and 0≤start≤end). The ordered `source_cue_ids` carries merge provenance; distinct
  units referencing the same cue carry split provenance; transcript-segment provenance is
  reachable via the immutable source cues.
- **Baseline reading transformation (deterministic, meaning-preserving; not a domain
  invariant):** for each ordered candidate cue, emit exactly one reading unit with
  `source_cue_ids = (cue.identity,)`, `display_order = cue.display_order`, inherited timing
  metadata from the cue, and `lines =` the normalization of `cue.text` — split on existing
  hard line breaks (preserving author structure), collapse internal whitespace runs and trim
  each line, drop empty lines (a non-blank cue always yields ≥1 non-empty line). No
  threshold-driven merge/split/wrap is applied.
- **Identity plan:** `SubtitleReadingIdentityPlan(reading_revision_id, reading_result_id,
  unit_ids: tuple[...])`, caller-owned; cardinality/uniqueness validated against the derived
  unit count.

## 6. Persistence

Additive SQLite **v13**: `subtitle_reading_revisions` parent; ordered
`subtitle_reading_units` child (ordinal, inherited-timing cols with the timed/untimed CHECK,
`display_order`); `subtitle_reading_unit_source_cues` ordinal grandchild (provenance /
merge-split); `subtitle_reading_unit_lines` ordinal grandchild (line composition). Co-persist
a `DomainResultReference` (kind `subtitle_reading_revision`, `upstream = (candidate
DomainResult,)`, `source_media`/`source_timeline` from the candidate) in one `BEGIN IMMEDIATE`
transaction with linkage + identity-absence checks and complete rollback on any collision/
linkage/write/commit failure. `_migrate_v12_to_v13` additive; downgrades and direct skips
rejected; every released version v1..v12 chains to v13 preserving existing data and meaning.

## 7. Slice Sequence

### Slice 1 — Goal Baseline and Assessment
Review: Optional — Skipped. Commit: `docs: add subtitle reading representation goal`

### Slice 2 — Reading Records
`SubtitleReadingRevisionId`, `SubtitleReadingUnitId`, `SubtitleReadingRevision`,
`SubtitleReadingUnit`, `SubtitleReadingIdentityPlan`, `SUBTITLE_READING_REVISION_RESULT_KIND`,
exports, focused record tests (invariants, multi-line unit, merge many:1, split 1:many,
untimed unit). Review: Required — Executed. Commit: `feat: add subtitle reading records`

### Slice 3 — Deterministic Reading Representation Service
`SubtitleReadingRepresentationService.compose_reading(...)` loads the candidate + its ordered
cues, requires a running execution, applies the deterministic meaning-preserving normalization
to derive one reading unit per cue (baseline), validates the identity plan, and builds the
`PreparedSubtitleReading` (no write). Review: Required — Executed. Commit:
`feat: derive subtitle reading revision from candidate`

### Slice 4 — Atomic SQLite Persistence, Restart, Replay and Migration Compatibility
Additive schema v13, parent + unit + source-cue + line repositories, atomic command,
composition, `record_reading` path, restart/replay, v1..v12 → v13 compatibility, idempotency.
Review: Required — Executed. Commit: `feat: persist subtitle reading revision atomically`

### Slice 5 — Fake-Review / Fake-Transcript Acceptance
End-to-end: candidate → reading revision + ordered normalized units; persist → reopen →
identical reconstruction → identical replay → idempotent upstream candidate → no downstream
(no time/validation/review/final/artifact table). Review: Optional — Skipped (harness/test
only). Commit: `test: verify subtitle reading representation acceptance`

## 8. Milestone-Specific Verify

Reading revision composed only from a canonical `SubtitleCandidate`; the baseline performs a
deterministic meaning-preserving normalization (whitespace normalization + hard-line-structure
preservation), not a pure copy; each unit traces to ≥1 ordered source cue and (via the immutable
cues) to the originating transcript segments; the candidate and its cues are unchanged
(byte-identical before/after); the durable model round-trips merge (multi-cue unit) and split
(multiple units per cue) provenance and multi-line composition; timing is inherited metadata
only — no timestamp is computed, inferred, or reordered; immutable records; duplicate-identity /
DomainResult / unit-cardinality mismatches roll back atomically; identical canonical input +
identity plan → byte-identical reading revision + ordered units; replay after restart →
byte-equivalent; repeated composition mutates no upstream record; **no time-representation,
validation, review, final subtitle, provider, or artifact behavior is produced**. (Generic
validation inherited.)

## 9. Status (living)

### Completed Capabilities
```text
Slice 1 — Goal Baseline and Assessment
- commit `3e75120` — `docs: add subtitle reading representation goal`
- bounded assessment: no substantive blocker; reading composition consumes the canonical
  SubtitleCandidate (v12) + its cues; provider-free; additive schema v13; produces a new
  immutable representation (not a mutation); baseline is a deterministic meaning-preserving
  normalization (not a pure copy); merge/split is durable-model capability with policy deferred;
  timing is inherited metadata, not time authority
- Review: Optional — Skipped (documentation only)

Slice 2 — Reading Records
- commit `f5f0068` — `feat: add subtitle reading records`
- `SubtitleReadingRevisionId`, `SubtitleReadingUnitId` added to application identities
- `compose_reading_lines(text)`: deterministic, meaning-preserving line composition — preserves
  existing hard-line structure, normalizes whitespace, drops empty lines (non-blank text → ≥1 line)
- `SubtitleReadingUnit`: identity, revision linkage, ordered unique `source_cue_ids` (≥1), ordered
  non-blank `lines` (≥1), non-negative display order, inherited optional timing metadata (untimed
  allowed; timed requires timeline and 0≤start≤end)
- `SubtitleReadingRevision`: identity, DomainResult linkage, candidate + full carried lineage,
  transcript/revision/media/timeline, carried `validation_id`, ordered unique `unit_ids`, execution
  provenance, append-only sequence/previous linkage, deterministic reason
- `SubtitleReadingIdentityPlan` (revision id, result id, ordered unique unit ids)
- durable unit model supports many-to-one (merge: multi-cue unit) and one-to-many (split: multiple
  units per cue) provenance; no human-decision / applicability / final field
- 27 focused record tests passed; complete suite 921 passed
- Required Claude Review: Inconclusive — no critical findings identified (additive immutable
  records; genuine deterministic normalization; merge/split/multi-line model support; no
  Blueprint/lifecycle/contract defect)

Slice 3 — Deterministic Reading Representation Service
- commit `e622267` — `feat: derive subtitle reading revision from candidate`
- `SubtitleReadingRepresentationService.compose_reading(...)` loads the canonical candidate
  (admission authority), requires a running execution, loads its ordered cues, and derives one
  reading unit per cue applying `compose_reading_lines` (deterministic meaning-preserving
  normalization, not a pure copy), inheriting each cue's timing metadata unchanged
- carries the full candidate lineage into the revision; revision DomainResult upstream = the
  candidate DomainResult; no wall-clock; performs no write; mutates no upstream record; triggers no
  downstream capability; owns no time semantics
- `PreparedSubtitleReading` return; `AtomicSubtitleReadingPersistence` port; `SubtitleCandidateQuery`
  protocol; `SubtitleReadingRepresentationError` for unsafe input
- 7 focused service tests (2-unit normalization incl. whitespace + hard-line cases, untimed unit,
  identity-plan cardinality, unknown candidate, running-execution, determinism, no-persistence)
  passed; complete suite 928 passed
- Required Claude Review: Inconclusive — no critical findings identified (pure deterministic
  derivation; no persistence, no upstream mutation, no downstream trigger, no time logic)

Slice 4 — Atomic SQLite Persistence, Restart, Replay and Migration Compatibility
- commit `1de9ab8` — `feat: persist subtitle reading revision atomically`
- additive SQLite schema v13: `subtitle_reading_revisions` parent + ordered `subtitle_reading_units`
  child (UNIQUE(revision, ordinal), timed/untimed CHECK) + `subtitle_reading_unit_source_cues`
  ordinal grandchild (provenance / merge-split) + `subtitle_reading_unit_lines` ordinal grandchild
  (line composition)
- `_migrate_v12_to_v13` additive; downgrades and direct skips rejected; existing v1–v12 unchanged
- `SQLiteSubtitleReadingCommandPersistence.persist_subtitle_reading(...)` writes the revision, its
  ordered units (+ source-cue + line children) and the DomainResultReference in one `BEGIN IMMEDIATE`
  transaction; validates linkage/unit-ordering and identity absence; rolls back completely on
  collision/linkage/write/commit failure; no upstream mutation
- `SQLiteSubtitleReadingRevisionRepository` reconstructs the exact revision + ordered units after
  restart
- composition `compose_sqlite_subtitle_reading_representation_service` wires the durable candidate
  repository + reading persistence
- migration compatibility verified: every released version v1..v12 chains to v13 preserving data;
  idempotency verified (upstream candidate row byte-identical); superseded-latest test expectations
  updated (v2/v3/v4/v5/processing_units 12→13; v6..v12 unsupported-target guards 13→14; v9/v10/v11/v12
  chain helpers extended with the v12 addition block; v12 no-op/fresh-init/version realigned to the
  superseded-version pattern)
- 13 focused v13 tests (migration, full v1..v12→v13 chain, restart, replay, idempotency, atomic
  rollback of revision + units + source-cue + line children) passed; complete suite 941 passed
- Required Claude Review: PASS — independent bounded review verified atomicity/rollback, ordered
  unit + source-cue + line reconstruction, identity-collision atomicity, provenance linkage, additive
  migration, migration-chain compatibility, and DDL/expected-columns exactness; no critical findings

Slice 5 — Fake-Review / Fake-Transcript Acceptance
- commit `6bfd386` — `test: verify subtitle reading representation acceptance`
- `lectureos.subtitle_reading_acceptance` drives the full pipeline with a fake correction provider
  and fake reviewer (no network, no credential, fixed timestamps): fake proposals → proposed
  Revision → Review Preparation → Accept/Reject → applicability → selection → readiness → subtitle
  transcript intake → subtitle candidate generation → subtitle reading representation → atomic v13
  persistence → reopen → exact restart reconstruction → identical deterministic replay
- verifies one reading revision, 2 ordered units; unit lines equal the deterministic normalization
  of each cue's text; unit→source-cue lineage; unit ordering; timing inherited (identical to the
  source cue — nothing computed); revision candidate lineage and media/timeline; execution
  provenance; result upstream = candidate DomainResult; idempotency (upstream candidate byte-
  identical); restart reconstruction; deterministic replay; and no downstream time / validation /
  review / final / artifact table produced
- acceptance summary: reading_revision_count 1, unit_count 2, every linkage / provenance / restart /
  replay / idempotency / normalization / no-downstream flag true
- focused acceptance test passed; complete suite 942 passed
- Blueprint Drift Check: PASS — dependency direction unchanged, no provider owns reading identity/
  lifecycle, no existing enum/aggregate/service meaning changed (the in-memory subtitle domain is
  untouched), schema strictly additive, no time/validation/review/final/artifact responsibility
  pulled in, Human Authority intact, Reading Representation owns no time semantics
- Migration Compatibility: PASS — every released version v1..v12 chains to v13 preserving data
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

Beyond the inherited base skeleton, add: Canonical Reading Model; Deterministic Normalization
(meaning-preserving) vs Deferred Policy Merge/Split; Line Composition; Provenance / Lineage
through Merge/Split; Inherited Timing Metadata (no time authority); Persistence Model (parent +
unit + source-cue + line children); Restart and Replay Acceptance; Migration Compatibility;
Idempotency Verification; Provider-Boundary Deferral Note.

## 11. Milestone Overrides (optional)

None — this milestone uses the inherited critical-only review policy and all default execution
behavior without deviation.
