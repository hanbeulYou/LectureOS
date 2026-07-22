# LectureOS Codex Goal — Subtitle Structural Validation

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

Establish the fifth Subtitle Pipeline stage (`041_SUBTITLE_PIPELINE.md §4.5 Structural
Validation`, §9): from a canonical `SubtitleTimeRevision` and its ordered timed units,
deterministically **diagnose** the subtitle revision's structural correctness and produce one
**immutable Validation Result** (`SubtitleValidation`) plus a collection of **immutable Findings**
(`SubtitleValidationFinding`) traceable to affected timed units. Validation's unique responsibility
is **detection, not construction, repair, review, or decision**: it records structural defects
(provenance integrity, timeline traceability, unresolved timing, ordering, overlap) and a derived
`structural_valid` verdict, and changes nothing. Lifecycle: `… → Subtitle Time Representation →
**Structural Validation** (this milestone) → Subtitle Review Preparation → Decision Application →
Final Subtitle`. A Validation-Failure revision is not Final; Validation never silently repairs, never
creates Review Items, and never approves.

## 2. Baseline

Start `HEAD 3b15d29`, branch `main`, `SQLITE_SCHEMA_VERSION 14`. Authority order inherited from
`AGENTS.md`.

## 3. Bounded Assessment & Architect Decision

The canonical `SubtitleTimeRevision` (v14) is the **sole admission authority**; validation reads it
and its ordered timed units, and reads the **reading revision + reading units read-only** as the
provenance basis for structural-integrity checks. It must **not** access Candidate cues, Transcript,
Intake, Readiness, Selection, Applicability, or Review records, never re-validates transcript meaning,
and mutates nothing. Non-timing lineage is inherited from the time revision and carried forward.

**Architect Decision (types & boundary):** add new Application-owned durable types —
`SubtitleValidation` (identity `SubtitleValidationId`), ordered child `SubtitleValidationFinding`
(identity `SubtitleValidationFindingId`), and enum `SubtitleValidationCategory`
(`PROVENANCE_INTEGRITY` | `TIMELINE_TRACEABILITY` | `UNRESOLVED_TIMING` | `ORDERING` | `OVERLAP`) — in
`application/` and `application/identities.py`, never cross-importing the in-memory `subtitle/` domain
(whose same-named validation vocabulary is left unchanged and informs, but is not reused by, the
durable model). No provider/capability boundary (validation is entirely deterministic). Additive
schema **v15**.

**Architect Decision (canonical artifact = diagnosis, not booleans, not repair, not review).** The
artifact is an immutable Validation Result plus immutable, individually-addressable, traceable,
blocking-classified Findings, with an independent append-only revisioned lifecycle (one-to-many
Validations per Time Revision). Validation **diagnoses only**: it records findings and a derived
`structural_valid` (= no blocking finding); it does not repair data, create Review Items, adjudicate
uncertainty, score/rank, approve, or gate. Findings are separate from Review Decisions; the derived
verdict is separate from Final authority.

**Architect Decision (finding identity).** Because the finding count is defect-dependent (not known
from input size), each finding's identity is deterministically derived from the caller-owned
Validation identity plus its ordinal. Identities remain opaque; determinism and replay are preserved;
no lifecycle-identity semantic changes.

**Architect Decision (stable rule identifier).** Each `SubtitleValidationFinding` carries a stable
`rule` identifier independent of its human-readable `description`. The rule identifier represents the
deterministic validation rule that produced the finding; the description is explanatory text only and
is not part of the rule identity. Review Preparation, Decision Application, UI presentation, analytics,
statistics, filtering, and future policy layers consume the stable rule identifier rather than parsing
descriptions. The rule identifier is part of the canonical validation artifact and remains stable
across wording changes.

**Baseline is deterministic and threshold-free.** Checks: provenance integrity (timed unit → reading
unit resolves; exact coverage); timeline traceability (ANCHORED unit timeline equals the revision
timeline); unresolved timing (UNRESOLVED units); ordering (ANCHORED start times non-decreasing in
display order); overlap (consecutive ANCHORED units on one timeline where `earlier.end > later.start`,
strict/zero-tolerance). No numeric quality threshold is applied and nothing is modified. **Architect
Checklist result: all No — additive.**

## 4. Scope

- **Included:**
  - canonical `SubtitleValidation` aggregate + ordered `SubtitleValidationFinding` collection
  - `SubtitleValidationCategory` enum; per-finding stable `rule` identifier, `blocking` severity,
    explanatory `description`, and `target_timed_unit_id` (nullable for revision-level findings);
    derived category summary booleans + overall `structural_valid` (= no blocking finding)
  - deterministic, provider-free structural checks: provenance integrity, timeline traceability,
    unresolved timing, ordering, overlap (all threshold-free)
  - admission solely from a canonical `SubtitleTimeRevision`; reading revision/units read read-only
    for provenance integrity
  - carried time/reading/candidate/intake lineage; media/timeline; carried transcript `validation_id`
    (as `source_transcript_validation_id`); execution provenance; DomainResult linkage
    (`upstream = time revision DomainResult`)
  - append-only `sequence`/`previous_validation_id`; one-to-many Validations per Time Revision;
    empty-findings (valid) case supported
  - atomic SQLite **v15** persistence; restart reconstruction; deterministic replay
  - migration compatibility (v1..v14 → v15)
  - fake-review / fake-transcript acceptance driving time → validation, including a constructed
    defective time revision proving overlap/ordering/unresolved findings
- **Excluded (later stages / deferred quality policy):**
  - modifying subtitle timing or reading representation; any repair or optimization (duration, CPS,
    overlap, gap, boundary)
  - reading-speed/CPS validation; min/max display-duration validation; overlap-tolerance, gap, frame,
    or line-length thresholds; readability/pedagogical-correctness judgement; transcript-meaning
    re-validation
  - Review Item creation / review UI / review necessity policy (§4.6); Decision Application (§4.7)
  - Final Subtitle selection or gate enforcement (§4.8); artifact generation; export; playback/rendering
  - any AI provider or capability port
  - mutation of Time, Reading, Candidate, or Transcript records; changes to any upstream contract or the
    in-memory subtitle domain

Producing a validation mutates no upstream record and starts no downstream capability.

## 5. Canonical Model

- **Identities:** `SubtitleValidationId`, `SubtitleValidationFindingId` (`OpaqueIdentity`, in
  `application/identities.py`).
- **Enum `SubtitleValidationCategory`:** `PROVENANCE_INTEGRITY` | `TIMELINE_TRACEABILITY` |
  `UNRESOLVED_TIMING` | `ORDERING` | `OVERLAP`.
- **Stable rule identifiers (module constants):** e.g. `provenance.reading_revision_missing`,
  `provenance.reading_unit_missing`, `provenance.coverage_mismatch`, `traceability.timeline_mismatch`,
  `timing.unresolved`, `ordering.non_monotonic`, `overlap.adjacent`.
- **Aggregate `SubtitleValidation`:** `identity`; `domain_result_id`; `source_time_revision_id`;
  carried lineage (`source_reading_revision_id`, `source_candidate_id`, `source_intake_id`,
  `source_readiness_id`, `source_selection_id`, `source_applicability_id`, `source_decision_id`,
  `review_item_id`, `candidate_reference_id`, `source_transcript_id`, `source_revision_id`,
  `source_media_id`, `source_timeline_id`, `source_transcript_validation_id`); derived summaries
  `structural_valid`, `provenance_complete`, `timeline_traceable`, `ordering_consistent`,
  `time_consistent`; ordered `finding_ids`; `run_id`, `unit_execution_id`; `sequence`,
  `previous_validation_id`; `reason`. Invariants: unique finding ids; non-negative sequence; non-blank
  reason; first has no previous reference; no human-decision/approval/final field.
- **Record `SubtitleValidationFinding`:** `identity`; `validation_id`; `rule` (stable, non-blank);
  `category`; `blocking`; `description` (explanatory, non-blank); `target_timed_unit_id | None`.
  Findings are ordered within the validation. The `rule` is the finding's stable rule identity; the
  `description` is not part of the rule identity.
- **Baseline diagnosis (deterministic, threshold-free; not a domain invariant):** run the five
  structural checks over the timed units (and reading units for provenance), emit one ordered finding
  per detected defect with its stable `rule`, category, `blocking` flag, deterministic `description`,
  and affected timed unit; derive the summary booleans and `structural_valid` (= no blocking finding).
  Modify nothing; create no Review Item.
- **Identity plan:** `SubtitleValidationIdentityPlan(validation_id, validation_result_id)`; finding
  identities derived deterministically as `f(validation_id, ordinal)`.

## 6. Persistence

Additive SQLite **v15**: `subtitle_validations` parent (carried lineage, summary booleans, sequence/
previous) + ordered `subtitle_validation_findings` child (ordinal, `rule` non-blank, `category` CHECK
IN the five categories, `blocking`, `description` non-blank, nullable `target_timed_unit_id`;
`UNIQUE(subtitle_validation_id, ordinal)`; FK to parent). Co-persist a `DomainResultReference` (kind
`subtitle_validation`, `upstream = (time revision DomainResult,)`, `source_media`/`source_timeline`
from the time revision) in one `BEGIN IMMEDIATE` transaction with linkage + identity-absence checks,
a `structural_valid ⇔ no blocking finding` cross-check, and complete rollback on any collision/linkage/
write/commit failure. `_migrate_v14_to_v15` additive; downgrades and direct skips rejected; every
released version v1..v14 chains to v15 preserving existing data and meaning.

## 7. Slice Sequence

### Slice 1 — Goal Baseline and Assessment
Review: Optional — Skipped. Commit: `docs: add subtitle structural validation goal`

### Slice 2 — Validation Records
`SubtitleValidationId`, `SubtitleValidationFindingId`, `SubtitleValidationCategory`, rule-id
constants, `SubtitleValidation`, `SubtitleValidationFinding`, `SubtitleValidationIdentityPlan`,
`SUBTITLE_VALIDATION_RESULT_KIND`, exports, focused record tests (invariants, empty findings valid,
stable rule vs description, blocking classification). Review: Required — Executed. Commit:
`feat: add subtitle validation records`

### Slice 3 — Deterministic Structural Validation Service
`SubtitleStructuralValidationService.validate_timing(...)` loads the time revision + its timed units,
resolves the reading revision/units read-only, requires a running execution, runs the five structural
checks, derives findings + summaries, and builds the `PreparedSubtitleValidation` (no write). Includes
overlap/ordering/unresolved/provenance defect cases and a clean (valid) case. Review: Required —
Executed. Commit: `feat: derive subtitle validation from time revision`

### Slice 4 — Atomic SQLite Persistence, Restart, Replay and Migration Compatibility
Additive schema v15, parent + finding child repositories, atomic command (with structural_valid
cross-check), composition, `record_validation` path, restart/replay, v1..v14 → v15 compatibility,
idempotency. Review: Required — Executed. Commit: `feat: persist subtitle validation atomically`

### Slice 5 — Fake-Review / Fake-Transcript Acceptance
End-to-end: time revision → validation (clean pipeline → structurally valid, no findings), plus a
constructed defective time revision proving OVERLAP/ORDERING/UNRESOLVED findings and
`structural_valid=False`; persist → reopen → identical reconstruction → identical replay → idempotent
upstream time revision → no downstream (no review/final/artifact table). Review: Optional — Skipped
(harness/test only). Commit: `test: verify subtitle structural validation acceptance`

## 8. Milestone-Specific Verify

Validation composed only from a canonical `SubtitleTimeRevision`; the five structural checks are
deterministic and threshold-free; a clean time revision yields `structural_valid=True` with no
findings; overlap/ordering/unresolved/provenance defects each yield a traceable, category-classified
finding carrying a **stable `rule` identifier independent of its `description`**, and
`structural_valid=False` when blocking; each finding references its affected timed unit (or the
revision); Validation **modifies nothing** (time/reading/candidate records byte-identical
before/after) and creates **no Review Item**; `structural_valid ⇔ no blocking finding`; immutable
records; duplicate-identity / DomainResult collisions roll back atomically; identical canonical input
+ identity plan → byte-identical validation + ordered findings; replay after restart → byte-equivalent;
repeated validation mutates no upstream record (appends a new Validation); **no review, decision, final
subtitle, provider, or artifact behavior is produced**. (Generic validation inherited.)

## 9. Status (living)

### Completed Capabilities
```text
None yet
```
### Remaining Milestones
```text
Slice 1 — Goal Baseline and Assessment
Slice 2 — Validation Records
Slice 3 — Deterministic Structural Validation Service
Slice 4 — Atomic SQLite Persistence, Restart, Replay and Migration Compatibility
Slice 5 — Fake-Review / Fake-Transcript Acceptance
```
### Immediate Next Slice
```text
Slice 1 — Goal Baseline and Assessment
```

## 10. Completion Report — Milestone Additions

Beyond the inherited base skeleton, add: Canonical Validation Model (Result + Findings); Diagnosis vs
Repair vs Review vs Decision boundary; Structural Check Catalogue (provenance/traceability/unresolved/
ordering/overlap); Findings Model (immutable, traceable, blocking-classified, stable-rule-identified,
derived-identity); Stable Rule Identifier vs Description; Validation Semantics (structural pass/fail
only); Persistence Model (parent + finding child); Restart and Replay Acceptance; Migration
Compatibility; Idempotency Verification; Provider-Boundary Deferral Note; Deferred Quality-Policy
Register.

## 11. Milestone Overrides (optional)

None — this milestone uses the inherited critical-only review policy and all default execution
behavior without deviation.

---

### Deliberately deferred quality policies (recorded for the completion report)
Reading-speed / **CPS** validation; **minimum/maximum display-duration** validation; **overlap-tolerance**,
**inter-cue gap**, **frame-tolerance**, and **line-length** thresholds; **reading-structure quality**
(§9.1) judgement; readability / pedagogical-correctness judgement; **uncertainty adjudication** and
**review-necessity** policy (which findings require an explicit Review Item — §4.6); any **repair /
optimization** of timing; and **transcript-meaning re-validation**. All require product policy undefined
by the current Blueprint (§4.5/§9) and are out of scope; Review handoff belongs to §4.6, decisions to
§4.7, and Final gating to §4.8.
