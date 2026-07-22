# LectureOS Codex Goal — Subtitle Review Preparation

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

Establish the sixth Subtitle Pipeline stage (`041_SUBTITLE_PIPELINE.md §4.6 Subtitle Review
Preparation`, §10): from the supplied canonical `SubtitleValidation` revision and its ordered
findings, deterministically **materialize canonical human-review work** — one **common `ReviewItem`**
(with its `CandidateReference` and a shared `ReviewContext`) per validation finding — wrapped by a new
immutable `SubtitleReviewPreparation` aggregate that traces each item to its source finding and stable
`rule`. Review Preparation's unique responsibility is to **turn deterministic diagnoses into
addressable, open human-review work units in the common Review activity**, without making any judgment.
Lifecycle: `… → Subtitle Structural Validation → **Subtitle Review Preparation** (this milestone) →
Decision Application → Final Subtitle`. It records **no** Review Decision, changes no upstream record,
creates review work in the **open** common lifecycle, and starts nothing downstream.

## 2. Baseline

Start `HEAD 603a64c`, branch `main`, `SQLITE_SCHEMA_VERSION 15`. Authority order inherited from
`AGENTS.md`.

## 3. Bounded Assessment & Architect Decision

**Admission boundary.** Review Preparation **consumes the supplied canonical `SubtitleValidation`
revision** (v15) and its ordered findings (`SQLiteSubtitleValidationRepository.get` / `get_finding`);
media/timeline and lineage are carried on the validation, and each finding carries `rule` and
`target_timed_unit_id`. Whether that validation is the latest, currently selected, superseded, or
otherwise eligible for execution is **outside the responsibility of this stage**: Review Preparation
neither determines nor enforces currency, selection, or supersession. Selection of which Validation
revision enters this stage belongs to an **upstream lifecycle authority** and remains outside the
Review Preparation boundary. It does not access Time/Reading/Candidate/Transcript/upstream records and
mutates nothing.

**Architect Decision (reuse the common Review activity).** Review Preparation **creates the existing
common `review/` records** — `ReviewItem`, `CandidateReference`, `ReviewContext` — into the shared
`review_items` / `review_candidate_references` / `review_contexts` tables (mirroring
`TranscriptReviewPreparation`), plus a new Application-owned aggregate `SubtitleReviewPreparation`
(identity `SubtitleReviewPreparationId`) and child linking each Review Item to its source finding +
`rule`. It reuses the common Review lifecycle: items are created **OPEN** (empty `decision_references`);
**no new status enum** is introduced; allowed actions are the common `DecisionKind`. No
provider/capability boundary. Additive schema **v16**. The in-memory `subtitle/` domain and
`application/subtitle_review.py` are untouched.

**Architect Decision (Finding→Review-Item cardinality = 1:1).** Each validation finding produces
**exactly one** common Review Item (and one CandidateReference), in the source finding's order, each
carrying the source finding identity and stable `rule`. No grouping, prioritization, scoring,
summarization, or AI-generated text. Review necessity is a **fixed deterministic baseline** (every
finding is review work); rule-id/blocking-based eligibility filtering is deferred.

**Architect Decision (empty preparation is valid).** A structurally valid validation (0 findings)
produces a **valid empty preparation** (item_count 0, a context, no items). Unlike
`TranscriptReviewPreparation` (which requires ≥1 item), the subtitle aggregate allows an empty item
set — so a subtitle-specific aggregate is used while the common Review records are reused.

**Architect Decision (no decision, no currency check).** Preparation makes no Accept/Reject/Modify and
performs no supersession/currency/selection check on the validation; multiple preparations per
validation are allowed (append-only). **Architect Checklist result: all No — additive.**

## 4. Scope

- **Included:**
  - Application-owned `SubtitleReviewPreparation` aggregate + ordered per-item finding-traceability links
  - deterministic, provider-free materialization: one common `ReviewItem` + `CandidateReference` per
    validation finding (1:1, finding order), a shared `ReviewContext`, all in the common review tables
  - valid **empty preparation** for a clean validation (0 findings)
  - per-item traceability: source `SubtitleValidation` id, source finding id, stable `rule`, target
    timed unit id, display order
  - Review Items created OPEN in the common lifecycle (no new status enum; allowed actions =
    `DecisionKind`)
  - carried validation lineage; media/timeline; execution provenance; DomainResult linkage
    (`upstream = validation DomainResult`)
  - append-only `sequence`/`previous_preparation_id`; multiple preparations per validation
  - atomic SQLite **v16** persistence (reuse common review tables + new subtitle prep parent/child);
    restart reconstruction; deterministic replay
  - migration compatibility (v1..v15 → v16)
  - fake-review / fake-transcript acceptance driving validation → review preparation (clean → empty;
    defective → one item per finding)
- **Excluded (later stages / deferred policy):**
  - any Review Decision (Accept/Reject/Modify); automatic approval; Decision Application (§4.7)
  - determining or enforcing validation currency, selection, or supersession (upstream authority)
  - grouping, prioritization, scoring, ranking, summarization, review-necessity/eligibility policy,
    review-item question/prompt text, allowed-action lists, priority, UI copy or presentation formatting
  - AI-generated review questions/explanations/priorities/summaries; any provider or capability port
  - altering validation findings; repairing timing; modifying reading representation; changing
    `structural_valid`
  - Final Subtitle selection (§4.8); artifact generation; export; playback/rendering
  - mutation of Validation/Time/Reading/Candidate records; changes to the common `review/` contracts or
    the in-memory subtitle domain

Producing a preparation mutates no upstream record and records no decision.

## 5. Canonical Model

- **Identity:** `SubtitleReviewPreparationId` (`OpaqueIdentity`, in `application/identities.py`).
- **Reused common records:** `ReviewItem`, `CandidateReference`, `ReviewContext` (from `review/`), plus
  their `ReviewItemId` / `CandidateReferenceId` / `ReviewContextId`.
- **Value `SubtitleReviewItemLink`:** `review_item_id`; `candidate_reference_id`; `source_finding_id`
  (`SubtitleValidationFindingId`); `rule` (non-blank stable rule id); `target_timed_unit_id`
  (`SubtitleTimedUnitId | None`).
- **Aggregate `SubtitleReviewPreparation`:** `identity`; `domain_result_id`; `source_validation_id`;
  carried lineage (`source_time_revision_id`, `source_reading_revision_id`, `source_candidate_id`,
  `source_intake_id`, `source_readiness_id`, `source_selection_id`, `source_applicability_id`,
  `source_decision_id`, `source_review_item_id`, `source_candidate_reference_id`, `source_transcript_id`,
  `source_revision_id`, `source_media_id`, `source_timeline_id`, `source_transcript_validation_id`);
  `context_id`; ordered `item_links: tuple[SubtitleReviewItemLink,…]` (may be empty); `item_count`
  (== len(item_links)); `source_structural_valid`; `provenance_complete`; `run_id`; `unit_execution_id`;
  `sequence`; `previous_preparation_id`; `reason`. Invariants: `item_count == len(item_links)`; unique
  review-item / candidate-reference / source-finding ids; non-negative sequence; non-blank reason; first
  has no previous reference; no decision/approval/final field.
- **Baseline mapping (deterministic; not a domain invariant):** for each validation finding in order,
  create a `CandidateReference` (kind `subtitle_validation_finding`, source_domain `subtitle`,
  `domain_result_id` = validation DomainResult, media/timeline from validation, `revision_reference`
  encoding the source time revision, `applicability` `undetermined`) whose identity equals a
  caller-supplied candidate-reference id, and one OPEN `ReviewItem` referencing it and the shared
  context; record a `SubtitleReviewItemLink` with the source finding id + `rule` + target timed unit.
  Zero findings → empty preparation (context only).
- **Identity plan:** `SubtitleReviewPreparationIdentityPlan(preparation_id, preparation_result_id,
  context_id, targets: tuple[SubtitleReviewTargetIdentityPlan(candidate_reference_id, review_item_id),…])`;
  `targets` count == validation finding count (0 allowed); ids unique.

## 6. Persistence

Additive SQLite **v16**, reusing the common `review_items`, `review_candidate_references`,
`review_contexts` (+ ordinal children) tables for the materialized review records, plus new
`subtitle_review_preparations` parent + ordered `subtitle_review_preparation_items` child (ordinal,
`review_item_id`, `candidate_reference_id`, `source_finding_id`, `rule` non-blank, nullable
`target_timed_unit_id`; `PRIMARY KEY(subtitle_review_preparation_id, ordinal)`; FK to parent). Co-persist
a `DomainResultReference` (kind `subtitle_review_preparation`, `upstream = (validation DomainResult,)`,
media/timeline from the validation) in one `BEGIN IMMEDIATE` transaction with linkage + identity-absence
checks and complete rollback on any collision/linkage/write/commit failure (including the empty case,
which still writes the parent + context + DomainResult). `_migrate_v15_to_v16` additive; downgrades and
direct skips rejected; every released version v1..v15 chains to v16 preserving existing data and meaning.

## 7. Slice Sequence

### Slice 1 — Goal Baseline and Assessment
Review: Optional — Skipped. Commit: `docs: add subtitle review preparation goal`

### Slice 2 — Review Preparation Records
`SubtitleReviewPreparationId`, `SubtitleReviewItemLink`, `SubtitleReviewPreparation`,
`SubtitleReviewTargetIdentityPlan`, `SubtitleReviewPreparationIdentityPlan`,
`SUBTITLE_REVIEW_PREPARATION_RESULT_KIND`, exports, focused record tests (invariants, empty preparation
valid, unique ids, finding traceability). Review: Required — Executed. Commit:
`feat: add subtitle review preparation records`

### Slice 3 — Deterministic Review Preparation Service
`SubtitleReviewPreparationService.prepare_review(...)` consumes the supplied validation + its ordered
findings, requires a running execution, creates one CandidateReference + OPEN ReviewItem per finding
(1:1, finding order) + a shared context, builds the `PreparedSubtitleReview` (no write), and handles the
empty case. Review: Required — Executed. Commit: `feat: derive subtitle review preparation from validation`

### Slice 4 — Atomic SQLite Persistence, Restart, Replay and Migration Compatibility
Additive schema v16 (reuse common review tables + subtitle prep parent/child), atomic command reusing
the common review insert helpers, repository, composition, `generate_review` path, restart/replay,
v1..v15 → v16 compatibility, idempotency, empty-case persistence. Review: Required — Executed. Commit:
`feat: persist subtitle review preparation atomically`

### Slice 5 — Fake-Review / Fake-Transcript Acceptance
End-to-end: clean validation → empty preparation (0 items); defective validation → one OPEN Review Item
per finding with source-finding + rule traceability; persist → reopen → identical reconstruction →
identical replay → idempotent upstream validation → no decision recorded → no downstream. Review:
Optional — Skipped (harness/test only). Commit: `test: verify subtitle review preparation acceptance`

## 8. Milestone-Specific Verify

Preparation created only from the supplied canonical `SubtitleValidation` (no currency/selection/
supersession check performed); a clean validation yields a **valid empty preparation** (0 items) and an
invalid validation yields **exactly one OPEN common Review Item per finding** in finding order; each
Review Item references a CandidateReference (kind `subtitle_validation_finding`) and the shared context,
and each is traced by a `SubtitleReviewItemLink` to its source finding id + stable `rule` + target timed
unit; Review Items are created OPEN (empty `decision_references`) and **no Review Decision is recorded**;
Preparation **modifies nothing** (validation/time/reading records byte-identical before/after); the
common `review/` contracts are unchanged (rows added, meaning unchanged); immutable records;
duplicate-identity / DomainResult collisions roll back atomically (empty and non-empty); identical
canonical input + identity plan → byte-identical preparation + review rows; replay after restart →
byte-equivalent; repeated preparation mutates no upstream record (appends a new preparation revision);
**no decision, final subtitle, provider, or artifact behavior is produced**. (Generic validation
inherited.)

## 9. Status (living)

### Completed Capabilities
```text
Slice 1 — Goal Baseline and Assessment
- commit `ef206b6` — `docs: add subtitle review preparation goal`
- bounded assessment: no substantive blocker; Review Preparation consumes the supplied canonical
  SubtitleValidation revision (currency/selection/supersession are an upstream authority's concern);
  reuses the common Review activity (creates common ReviewItem/CandidateReference/ReviewContext);
  1:1 finding→Review Item; valid empty preparation; open common lifecycle (no new status enum); no
  decision; provider-free; additive schema v16
- Review: Optional — Skipped (documentation only)

Slice 2 — Review Preparation Records
- commit `e8488b9` — `feat: add subtitle review preparation records`
- `SubtitleReviewPreparationId` added to application identities
- `SubtitleReviewItemLink` (review_item_id, candidate_reference_id, source_finding_id, non-blank
  stable rule, optional target_timed_unit_id) — per-item finding traceability
- `SubtitleReviewPreparation` aggregate: identity, DomainResult linkage, source validation + full
  carried lineage, context id, ordered item_links (may be empty), item_count, source_structural_valid,
  provenance_complete, execution provenance, append-only sequence/previous linkage, deterministic
  reason; unique review-item/candidate-reference/source-finding ids; empty preparation allowed; no
  decision/approval/final field
- `SubtitleReviewTargetIdentityPlan` + `SubtitleReviewPreparationIdentityPlan` (targets may be empty)
- 16 focused record tests passed; complete suite 1039 passed
- Required Claude Review: Inconclusive — no critical findings identified (additive immutable records;
  empty preparation valid; stable rule traceability; reuses common review identities; no defect)

Slice 3 — Deterministic Review Preparation Service
- commit `a199309` — `feat: derive subtitle review preparation from validation`
- `SubtitleReviewPreparationService.prepare_review(...)` consumes the supplied validation + its ordered
  findings, requires a running execution, and creates one common `CandidateReference` (kind
  `subtitle_validation_finding`, source_domain `subtitle`) + one OPEN `ReviewItem` per finding (1:1,
  finding order) referencing a shared `ReviewContext`, recording a `SubtitleReviewItemLink` per item;
  a clean validation (0 findings) yields a valid empty preparation
- consumes only the validation (currency/selection/supersession left to upstream authority); carries
  the full validation lineage; preparation DomainResult upstream = the validation DomainResult; no
  wall-clock; performs no write; mutates no upstream record; records no decision
- `PreparedSubtitleReview`, `AtomicSubtitleReviewPreparationPersistence` port, `SubtitleValidationQuery`
  protocol, `SubtitleReviewPreparationError`
- 8 focused service tests (1:1 open items traced; empty preparation; target-count mismatch; unknown
  validation/finding; running-execution; determinism; no-persistence) passed; complete suite 1047 passed
- Required Claude Review: Inconclusive — no critical findings identified (pure deterministic
  materialization; reuses the common Review model; no decision, no persistence, no upstream mutation)

Slice 4 — Atomic SQLite Persistence, Restart, Replay and Migration Compatibility
- commit `ff9ea68` — `feat: persist subtitle review preparation atomically`
- additive SQLite schema v16: `subtitle_review_preparations` parent + ordered
  `subtitle_review_preparation_items` child (composite PK; per-item review_item_id/candidate_reference_id/
  source_finding_id/rule/target); the common `review_items` / `review_candidate_references` /
  `review_contexts` tables are reused (no duplication)
- `_migrate_v15_to_v16` additive; downgrades and direct skips rejected; existing v1–v15 unchanged
- `SQLiteSubtitleReviewPreparationCommandPersistence.persist_subtitle_review_preparation(...)` writes
  the common candidate references + context + open review items (via the common insert helpers) + the
  preparation parent + item-link child + the DomainResultReference in one `BEGIN IMMEDIATE` transaction;
  validates linkage/cardinality and identity absence (in the shared tables too); rolls back completely
  on collision/linkage/write/commit failure, including the empty case; no upstream mutation
- `SQLiteSubtitleReviewPreparationRepository` reconstructs the exact preparation + ordered item links
  after restart
- composition `compose_sqlite_subtitle_review_preparation_service` wires the durable validation
  repository + review preparation persistence
- the `ReviewContext` carries no validation/diagnostic references (would be rejected by the common
  helper) and items carry empty decision references (open lifecycle)
- migration compatibility verified: every released version v1..v15 chains to v16 preserving data;
  idempotency verified (upstream validation row byte-identical); superseded-latest test expectations
  updated (v2/v3/v4/v5/processing_units 15→16; v6..v15 unsupported-target guards 16→17; v9..v14 chain
  helpers extended with the v15 addition block; v15 no-op/fresh-init/version realigned)
- 13 focused v16 tests (migration, full v1..v15→v16 chain, restart, replay, idempotency, atomic
  rollback of the empty preparation) passed; complete suite 1060 passed
- Required Claude Review: PASS — independent bounded review verified atomicity/rollback across the shared
  common tables (incl. the empty case), ordered item-link reconstruction, identity-collision atomicity,
  preparation↔item↔reference linkage, additive migration + chain compatibility, DDL/expected-columns
  exactness, and the required `validation_references` removal; no critical findings

Slice 5 — Fake-Review / Fake-Transcript Acceptance
- commit `90222b0` — `test: verify subtitle review preparation acceptance`
- `lectureos.subtitle_review_preparation_acceptance` drives the full pipeline (fake correction provider
  and fake reviewer, no network, no credential, fixed timestamps) through candidate → reading → time →
  validation → review preparation → atomic v16 persistence → reopen → exact restart reconstruction →
  identical deterministic replay
- verifies a clean validation yields a valid empty preparation (0 items), and a defective validation
  yields exactly one OPEN common Review Item per finding (kind `subtitle_validation_finding`), each
  traced to its source finding + stable rule; review items remain OPEN after restart (no decision
  recorded); result upstream = validation DomainResult; idempotency (upstream validation byte-identical
  before/after); restart reconstruction (preparation + common review items); deterministic replay; and
  no downstream final / artifact table produced
- acceptance summary: every empty / one-item-per-finding / open / traced / candidate-kind / provenance /
  idempotency / no-decision / restart / replay / no-downstream flag true
- focused acceptance test passed; complete suite 1061 passed
- Blueprint Drift Check: PASS — dependency direction unchanged, no provider owns review-preparation
  identity/lifecycle, no existing enum/aggregate/service meaning changed (the common `review/` contracts
  and in-memory subtitle domain are untouched; rows added, meaning unchanged), schema strictly additive,
  no decision/final/artifact responsibility pulled in, Human Authority intact, Review Preparation creates
  open review work and decides nothing
- Migration Compatibility: PASS — every released version v1..v15 chains to v16 preserving data
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

Beyond the inherited base skeleton, add: Canonical Preparation Model (aggregate + reused common Review
records); Admission Boundary (supplied validation; currency/selection/supersession upstream);
Finding→Review-Item Mapping (1:1); Review Necessity (fixed baseline); Empty-Preparation Behavior;
Existing Common Review Integration (reuse, no duplication, no new status enum); Review Item Semantics
(canonical vs deferred UI fields); Persistence Model (common review tables + subtitle prep parent/child);
Restart and Replay Acceptance; Migration Compatibility; Idempotency Verification; Provider-Boundary
Deferral Note; Deferred Grouping/Prioritization/UI/Eligibility Register.

## 11. Milestone Overrides (optional)

None — this milestone uses the inherited critical-only review policy and all default execution behavior
without deviation.

---

### Deliberately deferred capabilities (recorded for the completion report)
Finding **grouping** (multiple findings / one item; per-timed-unit grouping); **prioritization / ranking
/ scoring**; **review-necessity / eligibility policy** (rule-id- or blocking-based filtering of which
findings become items); **review-item question/prompt text**, allowed-action lists, **priority**, and any
**UI copy / presentation formatting**; **AI-assisted** question/explanation/summary generation; validation
**currency / selection / supersession** determination (upstream authority); and any **decision, or
final-gating** behavior. All belong to later workflow (§4.7/§4.8) or undefined product policy; a coherent
deterministic 1:1 baseline is implemented now.
