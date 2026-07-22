# LectureOS Codex Goal — Subtitle Time Representation

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

Establish the fourth Subtitle Pipeline stage (`041_SUBTITLE_PIPELINE.md §4.4 Time
Representation`, §7): from a canonical `SubtitleReadingRevision` and its ordered reading
units, deterministically compose one **new immutable subtitle time revision** whose
**timed units** carry an **authoritative, Source-Timeline-anchored display Time Range**
**derived** from each unit's ordered source cues — the minimal enclosing source-timeline
extent for merged units, the cue's range for one-to-one units, and an explicit
**UNRESOLVED** state where the basis is untimed. This is the stage that materializes a
coherent per-unit Time Range that Reading Representation could not (merge/split broke the
1:1 correspondence with timed segments). Lifecycle: `… → Subtitle Reading Representation →
**Time Representation** (this milestone) → Subtitle Structural Validation → …`. Time
Representation owns timing **representation** only; it produces a new revision that never
overwrites the reading revision, preserves text/line composition and display order exactly,
and performs no timing **validation**, review, decision, final selection, artifact, or
export.

## 2. Baseline

Start `HEAD 7efbbc4`, branch `main`, `SQLITE_SCHEMA_VERSION 13`. Authority order inherited
from `AGENTS.md`.

## 3. Bounded Assessment & Architect Decision

The canonical `SubtitleReadingRevision` (v13) is the **sole admission authority** (you
compose timing *for* a reading revision). Its **Source-Timeline basis** is resolved
**read-only** through each reading unit's ordered `source_cue_ids` → the immutable
`SubtitleCandidateCue` records, whose `source_timeline_id`/`start`/`end` are the surfaced
source-timeline ranges. Time Representation must **not** access Transcript, Intake,
Readiness, Selection, Applicability, or Review records, and mutates nothing. Non-timing
lineage (candidate/intake/readiness/selection/applicability/decision/review_item/
candidate_reference/transcript/revision/media/timeline/`validation_id`) is inherited from
the reading revision and carried forward.

**Architect Decision (types & boundary):** add new Application-owned durable types —
`SubtitleTimeRevision` (identity `SubtitleTimeRevisionId`) and ordered child
`SubtitleTimedUnit` (identity `SubtitleTimedUnitId`), plus enum `SubtitleTimingStatus`
(`ANCHORED` | `UNRESOLVED`) — in `application/` and `application/identities.py`, never
cross-importing the in-memory `subtitle/` domain. Read the reading revision (admission) and
the source cues (basis) via existing repositories; no provider/capability boundary (§4.4
excludes AI-finalized timestamps). Additive schema **v14**.

**Time Representation produces a new immutable representation, not a mutation.** The reading
revision, reading units, and candidate cues are immutable and unchanged; the time revision
is a new append-only aggregate linked to the reading revision (§8.4 forbids overwrite).

**Architect Decision (anchoring is provenance representation, not optimization).** The
baseline anchoring strategy derives the **minimal enclosing Source-Timeline extent** of a
unit's source cues. This baseline is a **deterministic representation of provenance, not a
timing optimization strategy**. Future timing policies (padding, snapping, overlap
resolution, gap insertion, duration adjustment, redistribution after merge/split, etc.) may
**refine** the resulting interval, but they never **redefine** the provenance-derived
baseline established here. Therefore, as a durable architectural boundary:

- **Source-Timeline anchoring is a canonical representation responsibility** (this stage).
- **Timing optimization is a later policy responsibility** (deferred; undefined by the
  Blueprint).
- **Structural Validation (§4.5) evaluates the represented timing rather than constructing
  it.**

**Baseline is deterministic and threshold-free.** For each reading unit the baseline gathers
its source cues and resolves an **ANCHORED** Time Range = `[min(start), max(end)]` over the
source cues **iff** every source cue is timed and shares one `source_timeline_id`; otherwise
marks the unit **UNRESOLVED** with no range. For a one-to-one unit this equals the single
cue's range; for a merged unit it is the genuine span; for a split unit each unit anchors
from its own cue basis. The span is a derivation from the basis (the objective extent of the
constituents), not a boundary *adjustment*: the baseline performs no inference of missing
timestamps, no padding/snapping, no overlap resolution, no gap insertion, no interval
extension/shrink, no cross-unit reordering, and no normalization beyond the enclosing extent.
Display order is preserved exactly; text/line composition is preserved by reference to the
reading unit. **Architect Checklist result: all No — additive.**

## 4. Scope

- **Included:**
  - canonical `SubtitleTimeRevision` aggregate + ordered `SubtitleTimedUnit` collection
  - `SubtitleTimingStatus` enum (`ANCHORED` | `UNRESOLVED`) making unresolved timing first-class
  - deterministic, provider-free **Source-Timeline anchoring**: for each reading unit, derive its
    authoritative display Time Range as the minimal enclosing source-timeline extent of its ordered
    source cues (span for merged units, cue range for one-to-one units), or `UNRESOLVED` when any
    source cue is untimed or the cues do not share one timeline
  - admission solely from a canonical `SubtitleReadingRevision`; Source-Timeline basis resolved
    read-only from the immutable candidate cues via the reading units' `source_cue_ids`
  - exact preservation of `display_order` and of text/line composition (by reference to the reading unit)
  - per-unit `source_reading_unit_id`; ordered source-cue/segment provenance preserved transitively
    through the immutable reading unit and cues
  - carried reading/candidate/intake lineage; media/timeline; carried `validation_id`; execution
    provenance; DomainResult linkage (`upstream = reading revision DomainResult`)
  - support for partially timed aggregates (mix of `ANCHORED`/`UNRESOLVED`) and multiple time
    revisions per reading revision via append-only `sequence`/`previous_time_revision_id`
  - atomic SQLite **v14** persistence; restart reconstruction; deterministic replay
  - migration compatibility (v1..v13 → v14)
  - fake-review / fake-transcript acceptance driving reading → time representation, including a
    constructed merged-unit case proving span derivation
- **Excluded (later policy responsibility / §4.5 validation):**
  - inference of missing timestamps; boundary adjustment/padding/snapping; overlap resolution; gap
    insertion; interval extension/shrink; cross-unit reordering; any normalization beyond the
    minimal enclosing extent (all require undefined policy)
  - reading-speed/CPS validation; min/max display-duration validation; Subtitle structural
    Validation (§4.5); readability/uncertainty adjudication; ordering/consistency judgement
  - Subtitle Review Preparation/Decision (§4.6–4.7); Final Subtitle (§4.8)
  - artifact generation; SRT/other export; playback/rendering UI
  - any AI provider or capability port; concrete timing thresholds not defined by the Blueprint
  - mutation of Candidate, Cue, or Reading records; changes to any upstream contract or the in-memory
    subtitle domain

Composing a time revision mutates no upstream record and starts no downstream capability.

## 5. Canonical Model

- **Identities:** `SubtitleTimeRevisionId`, `SubtitleTimedUnitId` (`OpaqueIdentity`, in
  `application/identities.py`).
- **Enum `SubtitleTimingStatus`:** `ANCHORED` | `UNRESOLVED`.
- **Aggregate `SubtitleTimeRevision`:** `identity`; `domain_result_id`;
  `source_reading_revision_id`; carried lineage (`source_candidate_id`, `source_intake_id`,
  `source_readiness_id`, `source_selection_id`, `source_applicability_id`, `source_decision_id`,
  `review_item_id`, `candidate_reference_id`); `source_transcript_id`, `source_revision_id`,
  `source_media_id`, `source_timeline_id`, `validation_id`; ordered `timed_unit_ids`; `run_id`,
  `unit_execution_id`; `sequence`, `previous_time_revision_id`; `reason`. Invariants: non-empty
  ordered units; unique unit ids; non-negative sequence; non-blank reason; first has no previous
  reference; no human-decision/applicability/final field.
- **Record `SubtitleTimedUnit`:** `identity`; `time_revision_id`; `source_reading_unit_id`;
  `display_order` (≥0); `timing_status`; `source_timeline_id | None`; `start | None`; `end | None`.
  Invariant: `ANCHORED` ⇒ timeline+start+end present, finite, `0≤start≤end`; `UNRESOLVED` ⇒ all
  null. Text/lines are not stored (preserved by reference to the reading unit).
- **Baseline anchoring strategy (deterministic provenance representation, not optimization; not a
  domain invariant):** for each ordered reading unit, resolve its source cues via `source_cue_ids`;
  if every source cue is timed and shares one `source_timeline_id`, emit one `ANCHORED` timed unit
  with Time Range `[min(start), max(end)]` over those cues on that timeline; otherwise emit one
  `UNRESOLVED` timed unit with null range. Preserve `display_order`; reference exactly one reading
  unit; no inference/adjustment/reordering. This baseline records the provenance-derived interval;
  later timing policies may refine it but never redefine it, and §4.5 evaluates it rather than
  constructing it.
- **Identity plan:** `SubtitleTimeIdentityPlan(time_revision_id, time_result_id, timed_unit_ids:
  tuple[...])`, caller-owned; cardinality/uniqueness validated against the reading revision's unit
  count.

## 6. Persistence

Additive SQLite **v14**: `subtitle_time_revisions` parent; ordered `subtitle_timed_units` child
(ordinal, `source_reading_unit_id`, `timing_status` CHECK `IN ('anchored','unresolved')`, timing
cols with the status/range CHECK `((timing_status='anchored' AND start/end/timeline present, finite,
0≤start≤end) OR (timing_status='unresolved' AND start/end/timeline all null))`, `display_order`;
`UNIQUE(subtitle_time_revision_id, ordinal)`). Co-persist a `DomainResultReference` (kind
`subtitle_time_revision`, `upstream = (reading revision DomainResult,)`,
`source_media`/`source_timeline` from the reading revision) in one `BEGIN IMMEDIATE` transaction
with linkage + identity-absence checks and complete rollback on any collision/linkage/write/commit
failure. `_migrate_v13_to_v14` additive; downgrades and direct skips rejected; every released
version v1..v13 chains to v14 preserving existing data and meaning.

## 7. Slice Sequence

### Slice 1 — Goal Baseline and Assessment
Review: Optional — Skipped. Commit: `docs: add subtitle time representation goal`

### Slice 2 — Time Records
`SubtitleTimeRevisionId`, `SubtitleTimedUnitId`, `SubtitleTimingStatus`, `SubtitleTimeRevision`,
`SubtitleTimedUnit`, `SubtitleTimeIdentityPlan`, `SUBTITLE_TIME_REVISION_RESULT_KIND`, exports,
focused record tests (ANCHORED requires valid range; UNRESOLVED requires null range; ordering;
lineage). Review: Required — Executed. Commit: `feat: add subtitle time records`

### Slice 3 — Deterministic Time Representation Service
`SubtitleTimeRepresentationService.compose_timing(...)` loads the reading revision + its ordered
units, resolves each unit's source cues (basis) read-only, requires a running execution, derives the
minimal enclosing source-timeline extent (ANCHORED) or marks UNRESOLVED, preserves display order,
validates the identity plan, and builds the `PreparedSubtitleTiming` (no write). Includes a
merged-unit (multi-cue) span case. Review: Required — Executed. Commit:
`feat: derive subtitle time revision from reading revision`

### Slice 4 — Atomic SQLite Persistence, Restart, Replay and Migration Compatibility
Additive schema v14, parent + timed-unit child repositories, atomic command, composition,
`record_timing` path, restart/replay, v1..v13 → v14 compatibility, idempotency. Review: Required —
Executed. Commit: `feat: persist subtitle time revision atomically`

### Slice 5 — Fake-Review / Fake-Transcript Acceptance
End-to-end: reading revision → time revision + ordered ANCHORED timed units (1:1 pipeline), plus a
constructed merged reading unit proving span derivation and an untimed basis proving UNRESOLVED;
persist → reopen → identical reconstruction → identical replay → idempotent upstream reading revision
→ no downstream (no validation/review/final/artifact table). Review: Optional — Skipped
(harness/test only). Commit: `test: verify subtitle time representation acceptance`

## 8. Milestone-Specific Verify

Time revision composed only from a canonical `SubtitleReadingRevision`; each timed unit's Time Range
is **derived from the Source-Timeline basis of its reading unit's source cues** — for a one-to-one
unit equal to the cue range, for a **merged unit equal to the minimal enclosing span** `[min start,
max end]`, and **UNRESOLVED** (null range) when any source cue is untimed or the cues span different
timelines; no fabricated timestamps and no threshold-based adjustment; each timed unit references
exactly one reading unit and preserves its `display_order` exactly; text/line composition and ordered
source-cue provenance are preserved by reference (unchanged); the reading revision, reading units, and
candidate cues are unchanged (byte-identical before/after); the durable model round-trips partially
timed aggregates and both `ANCHORED`/`UNRESOLVED` states; immutable records; duplicate-identity /
DomainResult / unit-cardinality mismatches roll back atomically; identical canonical input + identity
plan → byte-identical time revision + ordered timed units; replay after restart → byte-equivalent;
repeated composition mutates no upstream record; **no timing inference/adjustment, validation, review,
final subtitle, provider, or artifact behavior is produced**. (Generic validation inherited.)

## 9. Status (living)

### Completed Capabilities
```text
Slice 1 — Goal Baseline and Assessment
- commit `4736bf1` — `docs: add subtitle time representation goal`
- bounded assessment: no substantive blocker; time composition consumes the canonical
  SubtitleReadingRevision (v13) as sole admission authority and resolves the Source-Timeline basis
  read-only from the immutable candidate cues via source_cue_ids; provider-free; additive schema v14;
  produces a new immutable representation (not a mutation); baseline anchors the minimal enclosing
  Source-Timeline extent (span for merged units, cue range for one-to-one, UNRESOLVED when untimed);
  Architect Decision recorded: anchoring is provenance representation, not timing optimization —
  later policies may refine but never redefine the baseline, and §4.5 evaluates rather than constructs
- Review: Optional — Skipped (documentation only)

Slice 2 — Time Records
- commit `e9a9913` — `feat: add subtitle time records`
- `SubtitleTimeRevisionId`, `SubtitleTimedUnitId` added to application identities
- `SubtitleTimingStatus` enum (ANCHORED | UNRESOLVED)
- `SubtitleTimedUnit`: identity, revision linkage, source_reading_unit reference, non-negative
  display order, timing status, optional timeline+range; invariant ANCHORED ⇒ timeline+start+end
  present and 0≤start≤end, UNRESOLVED ⇒ all null (unresolved timing first-class, never hidden)
- `SubtitleTimeRevision`: identity, DomainResult linkage, reading revision + full carried candidate
  lineage, transcript/revision/media/timeline, carried validation_id, ordered unique timed_unit_ids,
  execution provenance, append-only sequence/previous linkage, deterministic reason
- `SubtitleTimeIdentityPlan` (revision id, result id, ordered unique timed unit ids)
- no human-decision / applicability / final field
- 18 focused record tests passed; complete suite 960 passed
- Required Claude Review: Inconclusive — no critical findings identified (additive immutable records;
  status↔range invariant enforced; partially timed aggregate supported; no Blueprint/lifecycle/contract defect)

Slice 3 — Deterministic Time Representation Service
- commit `f608dd5` — `feat: derive subtitle time revision from reading revision`
- `SubtitleTimeRepresentationService.compose_timing(...)` loads the reading revision (admission)
  and, read-only, each reading unit's source cues (Source-Timeline basis), requires a running
  execution, and derives each timed unit via `anchor_source_timeline_extent`
- anchoring: ANCHORED `[min(start), max(end)]` iff every source cue is timed and shares one timeline
  (cue range for one-to-one, genuine span for merged), else UNRESOLVED; display order preserved
  exactly; provenance representation only — no inference/adjustment/reordering; no time logic beyond
  the enclosing extent
- carries the full reading lineage into the revision; revision DomainResult upstream = the reading
  revision DomainResult; no wall-clock; performs no write; mutates no upstream record; triggers no
  downstream capability
- `PreparedSubtitleTiming` return; `AtomicSubtitleTimePersistence` port; `SubtitleReadingRevisionQuery`
  + `SubtitleCandidateCueQuery` protocols; `SubtitleTimeRepresentationError` for unsafe input
- 10 focused service tests (one-to-one cue range, merged span, untimed→UNRESOLVED,
  mixed-timeline→UNRESOLVED, partially timed aggregate, cardinality, unknown revision, unknown cue,
  running-execution, determinism, no-persistence) passed; complete suite 970 passed
- Required Claude Review: Inconclusive — no critical findings identified (pure deterministic
  derivation; genuine span anchoring; no persistence, no upstream mutation, no downstream trigger)

Slice 4 — Atomic SQLite Persistence, Restart, Replay and Migration Compatibility
- commit `e6a80ea` — `feat: persist subtitle time revision atomically`
- additive SQLite schema v14: `subtitle_time_revisions` parent + ordered `subtitle_timed_units`
  child (UNIQUE(revision, ordinal); CHECK binding timing_status to range presence — anchored ⇒
  timeline+start+end present and 0≤start≤end, unresolved ⇒ all null)
- `_migrate_v13_to_v14` additive; downgrades and direct skips rejected; existing v1–v13 unchanged
- `SQLiteSubtitleTimeCommandPersistence.persist_subtitle_timing(...)` writes the revision, its
  ordered timed units and the DomainResultReference in one `BEGIN IMMEDIATE` transaction; validates
  linkage/unit-ordering and identity absence; rolls back completely on collision/linkage/write/commit
  failure; no upstream mutation
- `SQLiteSubtitleTimeRevisionRepository` reconstructs the exact revision + ordered timed units after
  restart
- composition `compose_sqlite_subtitle_time_representation_service` wires the durable reading
  repository (admission) + candidate repository (cue basis) + time persistence
- migration compatibility verified: every released version v1..v13 chains to v14 preserving data;
  idempotency verified (upstream reading row byte-identical); superseded-latest test expectations
  updated (v2/v3/v4/v5/processing_units 13→14; v6..v13 unsupported-target guards 14→15;
  v9/v10/v11/v12/v13 chain helpers extended with the v13 addition block; v13 no-op/fresh-init/version
  realigned to the superseded-version pattern)
- 13 focused v14 tests (migration, full v1..v13→v14 chain, restart, replay, idempotency, atomic
  rollback of revision + timed units) passed; complete suite 983 passed
- Required Claude Review: PASS — independent bounded review verified atomicity/rollback, ordered
  timed-unit reconstruction, identity-collision atomicity, provenance linkage, additive migration,
  migration-chain compatibility, and the timing_status↔range CHECK↔dataclass consistency; no critical findings

Slice 5 — Fake-Review / Fake-Transcript Acceptance
- commit `80c529b` — `test: verify subtitle time representation acceptance`
- `lectureos.subtitle_time_acceptance` drives the full pipeline (fake correction provider and fake
  reviewer, no network, no credential, fixed timestamps) through candidate → reading → time
  representation → atomic v14 persistence → reopen → exact restart reconstruction → identical
  deterministic replay
- verifies the durable one-to-one pipeline (each timed unit ANCHORED to its own cue range on the
  source timeline), a durable merged-unit case (one reading unit over two source cues anchors the
  minimal enclosing span [min,max]), and the UNRESOLVED derivation for an untimed basis; timed-unit
  ordering and display order preserved; each timed unit references its reading unit; revision
  candidate lineage and source media/timeline; execution provenance; result upstream = reading
  revision DomainResult; idempotency (upstream reading row byte-identical); restart reconstruction;
  deterministic replay; and no downstream validation / review / final / artifact table produced
- acceptance summary: time_revision_count 1, unit_count 2, and every anchoring / span / unresolved /
  linkage / provenance / restart / replay / idempotency / no-downstream flag true
- focused acceptance test passed; complete suite 984 passed
- Blueprint Drift Check: PASS — dependency direction unchanged, no provider owns timing identity/
  lifecycle, no existing enum/aggregate/service meaning changed (the in-memory subtitle domain is
  untouched), schema strictly additive, no validation/review/final/artifact responsibility pulled in,
  Human Authority intact, Time Representation owns timing representation only (anchoring = provenance,
  optimization deferred, validation is §4.5)
- Migration Compatibility: PASS — every released version v1..v13 chains to v14 preserving data
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

Beyond the inherited base skeleton, add: Canonical Time Model; Source-Timeline Anchoring &
Merged-Unit Span Derivation vs Deferred Timing-Adjustment Operations; Provenance-Representation vs
Optimization vs Validation boundary; Timing Authority Transition (inherited metadata → derived
authoritative display timing); Merge/Split & Unresolved Handling; Basis Resolution (read-only source
cues) & Provenance; Persistence Model (parent + timed-unit child); Restart and Replay Acceptance;
Migration Compatibility; Idempotency Verification; Provider-Boundary Deferral Note; Deferred
Timing-Policy Register.

## 11. Milestone Overrides (optional)

None — this milestone uses the inherited critical-only review policy and all default execution
behavior without deviation.

---

### Deliberately deferred timing policies (recorded for the completion report)
Missing-timestamp **inference**; boundary **adjustment/padding/snapping**; **overlap resolution**;
**gap insertion**; display-interval **extension/shrink**; cross-unit **reordering**; any
**normalization beyond the minimal enclosing extent**; and every concrete numeric threshold
(minimum/maximum display duration, CPS/reading-rate, inter-cue gap, frame tolerance, overlap
tolerance). All require product policy undefined by the current Blueprint (§4.4/§7) and may only
**refine** — never **redefine** — the provenance-derived baseline. Timing **quality validation**
(consistency, ordering, traceability judgement) belongs to §4.5.
