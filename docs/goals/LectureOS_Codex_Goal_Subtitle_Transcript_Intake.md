# LectureOS Codex Goal — Subtitle Transcript Intake

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

Establish the first Subtitle Pipeline stage (`041_SUBTITLE_PIPELINE.md §4.1
Transcript Intake`): certify, from a canonical READY Corrected Transcript, that the
transcript revision is eligible to begin subtitle work. Lifecycle:
`… → Current Selection → Transcript Ready → **Subtitle Transcript Intake** (this
milestone) → Subtitle Candidate Generation → …`. Subtitle is a derived viewing
representation, not a transcript store; intake only gates entry — it produces no
candidates and starts nothing downstream.

## 2. Baseline

Start `HEAD e8f185e`, branch `main`, `SQLITE_SCHEMA_VERSION 10`. Authority order
inherited from `AGENTS.md`.

## 3. Bounded Assessment & Architect Decision

The `TranscriptReadinessEvaluation` (v10) is the canonical certificate of readiness
(it required SELECTED + APPLICABLE + structural_valid); intake is its first
downstream consumer. It carries the selection/applicability/decision/item/candidate/
revision lineage and the structural `validation_id`. Source media/timeline are not
on the readiness record; they are obtained deterministically from the durable
Corrected Transcript revision → Raw Transcript (v5).

**Architect Decision:** add one Application-owned aggregate `SubtitleTranscriptIntake`
plus a focused `SubtitleIntakeOutcome` enum (`ELIGIBLE` iff readiness `READY`, else
`NOT_ELIGIBLE`); recompute nothing (readiness already certifies validity — carry its
`validation_id` for provenance); additive schema v11. The existing in-memory
`subtitle/` domain is left unchanged. **Architect Checklist result: all No — additive.**

## 4. Scope

**Included:**

- canonical Subtitle Transcript Intake model
- deterministic eligibility derivation from a canonical readiness evaluation
- immutable intake records; explicit ELIGIBLE / NOT_ELIGIBLE outcome + deterministic reason
- readiness / current-selection / applicability / review-decision / review-item /
  candidate / revision linkage
- source media and timeline connection (from the durable revision/raw transcript)
- structural Validation reference; execution provenance; DomainResult linkage
- atomic SQLite v11 persistence; restart reconstruction; deterministic replay
- migration compatibility (v1..v10 → v11)
- fake-review / fake-transcript acceptance

**Excluded:**

- Subtitle Candidate Generation; Reading/Time Representation; Subtitle Revision
- Subtitle structural Validation; Subtitle Review Preparation/Decision; Final Subtitle
- Artifact generation / export; downstream execution
- provider changes; redesign of the transcript, readiness, or in-memory subtitle contracts

Recording intake mutates no upstream record and starts no downstream capability.

## 5. Canonical Model

- **Identity:** `SubtitleTranscriptIntakeId` (`OpaqueIdentity`).
- **Enum:** `SubtitleIntakeOutcome` = `ELIGIBLE` | `NOT_ELIGIBLE`; deterministic map
  from `ReadinessOutcome` (`READY → ELIGIBLE`, `NOT_READY → NOT_ELIGIBLE`).
- **Aggregate `SubtitleTranscriptIntake`:** `identity`; `domain_result_id`;
  `source_readiness_id`; `readiness_outcome`; `outcome`; carried lineage
  (`source_selection_id`, `source_applicability_id`, `source_decision_id`,
  `review_item_id`, `candidate_reference_id`); `source_transcript_id`,
  `source_revision_id`; `source_media_id`, `source_timeline_id`; `validation_id`;
  `run_id`, `unit_execution_id`; `sequence`, `previous_intake_id`; `reason`.
  Invariant (defense in depth): `ELIGIBLE ⇔ readiness_outcome == READY`; non-negative
  sequence; non-blank reason; first has no previous reference.
- **Identity plan:** `SubtitleIntakeIdentityPlan(intake_id, intake_result_id)`.

## 6. Persistence

Additive SQLite **v11**: one flat table `subtitle_transcript_intakes` (no FK
children) with a CHECK mirroring the `ELIGIBLE ⇔ readiness READY` invariant and the
sequence/previous invariant. Co-persist a `DomainResultReference` (kind
`subtitle_transcript_intake`, upstream = the readiness DomainResult) in one
`BEGIN IMMEDIATE` transaction. `_migrate_v10_to_v11` additive; downgrades and
direct skips rejected; every released version v1..v10 chains to v11 preserving data.

## 7. Slice Sequence

### Slice 1 — Goal Baseline and Assessment

Review: Optional — Skipped. Commit: `docs: add subtitle transcript intake goal`

### Slice 2 — Intake Records

`SubtitleTranscriptIntakeId`, `SubtitleIntakeOutcome`, `intake_for_readiness_outcome`,
`SubtitleTranscriptIntake` aggregate, `SubtitleIntakeIdentityPlan`, exports, focused
tests. Review: Required — Executed. Commit: `feat: add subtitle transcript intake records`

### Slice 3 — Deterministic Intake Service

`SubtitleTranscriptIntakeService.evaluate_intake(...)` loads the durable readiness
evaluation and the source revision/raw transcript, derives ELIGIBLE/NOT_ELIGIBLE,
and builds the aggregate. Review: Required — Executed. Commit:
`feat: derive subtitle transcript intake from readiness`

### Slice 4 — Atomic SQLite Persistence, Restart, Replay and Migration Compatibility

additive schema v11, repository, atomic command, composition, `record_intake` path,
restart/replay, v1..v10 → v11 compatibility. Review: Required — Executed. Commit:
`feat: persist subtitle transcript intake atomically`

### Slice 5 — Fake-Review / Fake-Transcript Acceptance

end-to-end: READY revision → ELIGIBLE, NOT_READY → NOT_ELIGIBLE; persist → reopen →
identical reconstruction → identical replay → idempotent upstream → no downstream.
Review: Optional — Skipped (harness/test only). Commit:
`test: verify subtitle transcript intake acceptance`

## 8. Milestone-Specific Verify

Eligibility derived only from a canonical readiness evaluation; **ELIGIBLE cannot be
produced for a NOT_READY readiness**; exact revision + readiness lineage preserved;
source media/timeline resolved from the durable revision/raw transcript; immutable
records; duplicate-identity and DomainResult collisions roll back atomically;
identical canonical input + identity plan → deterministic output; replay after
restart → byte-equivalent records; repeated evaluation does not mutate upstream
state; **no subtitle candidate or downstream operation is produced**. (Generic
validation inherited.)

## 9. Status (living)

### Completed Capabilities

```text
Slice 1 — Goal Baseline and Assessment
- commit `c3272b7` — `docs: add subtitle transcript intake goal`
- bounded assessment: no substantive blocker; intake derives from the canonical READY
  Transcript Readiness Evaluation; additive schema v11 planned; in-memory subtitle domain
  left unchanged
- Review: Optional — Skipped (documentation only)

Slice 2 — Intake Records
- `SubtitleTranscriptIntakeId` added to application identities
- `SubtitleIntakeOutcome` enum (ELIGIBLE / NOT_ELIGIBLE) with `intake_for_readiness_outcome`
  deterministic mapping (READY→ELIGIBLE, NOT_READY→NOT_ELIGIBLE)
- `SubtitleTranscriptIntake` aggregate: identity, DomainResult linkage, readiness linkage
  (+ readiness outcome), derived intake outcome, carried selection/applicability/decision/
  review-item/candidate lineage, transcript+revision linkage, source media/timeline,
  structural Validation reference, execution provenance, append-only sequence/previous
  linkage, deterministic reason
- `SubtitleIntakeIdentityPlan` (intake id, result id)
- invariants: outcome must match the readiness mapping; ELIGIBLE requires READY; non-negative
  sequence; non-blank reason; first has no previous reference
- 10 focused record tests passed; complete suite 832 passed
- Required Claude Review: Inconclusive — no critical findings identified
  (additive immutable records; ELIGIBLE⇔READY enforced at the record level; no Blueprint/
  lifecycle/contract defect)
```

### Remaining Milestones

```text
Slice 3 — Deterministic Intake Service
Slice 4 — Atomic SQLite Persistence, Restart, Replay and Migration Compatibility
Slice 5 — Fake-Review / Fake-Transcript Acceptance
```

### Immediate Next Slice

```text
Slice 3 — Deterministic Intake Service
```

## 10. Completion Report — Milestone Additions

Beyond the inherited base skeleton, add: Canonical Subtitle Intake Model; Eligibility
Rule; Validation/Readiness Linkage; Persistence Model; Provenance; Restart and Replay
Acceptance; Migration Compatibility; Idempotency Verification.

## 11. Milestone Overrides (optional)

None — this milestone uses the inherited critical-only review policy and all default
execution behavior without deviation.
