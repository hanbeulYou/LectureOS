# LectureOS Codex Goal — Subtitle Decision Application

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

Establish the seventh Subtitle Pipeline stage (`041_SUBTITLE_PIPELINE.md §4.7 Decision Application`):
from exactly one canonical `SubtitleReviewDecision`, deterministically **apply** the recorded Human
Accept/Reject/Modify and produce the **next Subtitle revision** — a new immutable
`SubtitleDecisionRevision` reflecting the applied outcome (and, for Modify, the user's modified text) —
together with its deterministic provenance. Application is a **pure deterministic transformation**: the
consumed decision remains immutable and **no existing canonical artifact is modified**. Lifecycle: `… →
Subtitle Review Preparation → Subtitle Human Review Decision → **Subtitle Decision Application** (this
milestone) → Final Subtitle`. It never records a decision, never selects a Final Subtitle, and derives no
current-selection / readiness / applicability.

## 2. Baseline

Start `HEAD b9ad674`, branch `main`, `SQLITE_SCHEMA_VERSION 17`. Authority order inherited from
`AGENTS.md`.

## 3. Bounded Assessment & Architect Decision

**Admission boundary.** The canonical admission authority is **exactly one `SubtitleReviewDecision`**
(v17). The `SubtitleValidation` (v15) and its finding are read **read-only** to resolve the full source
lineage and the target timed unit; the decision, its `ReviewItem`, its `SubtitleReviewPreparation`, and
the `SubtitleValidation` are **never mutated**. The only newly created canonical artifact is the next
Subtitle revision (`SubtitleDecisionRevision`) and its `DomainResultReference`.

**Architect Decision (new durable aggregate; distinct name).** Add one new Application-owned durable
aggregate `SubtitleDecisionRevision` (identity `SubtitleDecisionRevisionId`) and enum
`SubtitleAppliedOutcome` (`ACCEPTED` | `REJECTED` | `MODIFIED`, a pure deterministic function of
`DecisionKind`). Names are distinct from the **legacy in-memory** `application/subtitle_decision.py`
(`SubtitleDecisionApplicationService`), which is untouched. It reuses the common Review vocabulary
(`DecisionKind`, `ReviewItemId`, `CandidateReferenceId`). No provider/capability boundary. Additive
schema **v18**. The in-memory `subtitle/` domain remains untouched.

**Architect Decision (deterministic application; append-only next revision).** Applying one decision
produces one `SubtitleDecisionRevision`: outcome = `ACCEPTED`/`REJECTED`/`MODIFIED` (from
Accept/Reject/Modify); `applied_text` = the decision's modified text for Modify (null for Accept/Reject);
the targeted subtitle unit is the finding's `target_timed_unit_id` (nullable for revision-level
findings). It carries the decision + validation lineage and chains its DomainResult upstream to the
decision. Append-only `sequence`/`previous_revision_id`. No wall-clock; deterministic replay. **Architect
Checklist result: all No — additive.**

## 4. Scope

- **Included:**
  - canonical `SubtitleDecisionRevision` aggregate (the next Subtitle revision) + `SubtitleAppliedOutcome`
    enum
  - deterministic application of one `SubtitleReviewDecision`: Accept → ACCEPTED, Reject → REJECTED,
    Modify → MODIFIED with the applied modified text
  - admission solely from one canonical `SubtitleReviewDecision`; validation + finding read read-only for
    lineage and the target timed unit
  - carried lineage: review item / candidate reference / preparation / validation / time & reading
    revision / candidate / finding + stable rule / target timed unit / transcript & revision / media &
    timeline; execution provenance; DomainResult linkage (`upstream = review decision DomainResult`)
  - append-only `sequence`/`previous_revision_id`
  - atomic SQLite **v18** persistence; restart reconstruction; deterministic replay; idempotency
  - migration compatibility (v1..v17 → v18)
  - fake-review / fake-transcript acceptance applying Accept/Reject/Modify
- **Excluded (later stages / other authority):**
  - Final Subtitle selection (§4.8); current selection; readiness; applicability derivation
  - automatic approval; human decision recording (§ prior stage); AI-generated decisions; UI behavior; export
  - mutation of the `SubtitleReviewDecision`, `ReviewItem`, `SubtitleReviewPreparation`, or
    `SubtitleValidation`; changes to the common `review/` contracts or the in-memory subtitle domain
  - materializing a full multi-unit final subtitle, cue removal/reordering, or Corrected Transcript change

Applying a decision mutates no existing canonical artifact and records no decision.

## 5. Canonical Model

- **Identity:** `SubtitleDecisionRevisionId` (`OpaqueIdentity`, in `application/identities.py`).
- **Enum `SubtitleAppliedOutcome`:** `ACCEPTED` | `REJECTED` | `MODIFIED`; `applied_outcome_for_kind`
  maps `ACCEPT → ACCEPTED`, `REJECT → REJECTED`, `MODIFY → MODIFIED`.
- **Aggregate `SubtitleDecisionRevision`:** `identity`; `domain_result_id`; `source_review_decision_id`;
  `decision_kind`; `outcome`; `applied_text` (optional, Modify only); `review_item_id`;
  `candidate_reference_id`; `source_preparation_id`; `source_validation_id`; `source_time_revision_id`;
  `source_reading_revision_id`; `source_candidate_id`; `source_finding_id`; `rule`;
  `target_timed_unit_id` (optional); `source_transcript_id`; `source_revision_id`; `source_media_id`;
  `source_timeline_id`; `run_id`; `unit_execution_id`; `sequence`; `reason`; `previous_revision_id`.
  Invariants: `outcome == applied_outcome_for_kind(decision_kind)`; `MODIFIED` requires non-empty
  `applied_text` and `ACCEPTED`/`REJECTED` carry none; non-blank rule/reason; non-negative sequence;
  first has no previous revision.
- **Identity plan:** `SubtitleDecisionRevisionIdentityPlan(revision_id, revision_result_id)`.

## 6. Persistence

Additive SQLite **v18**: one flat table `subtitle_decision_revisions` (identity, DomainResult, review
decision, decision_kind CHECK IN accept/reject/modify, outcome CHECK IN accepted/rejected/modified with
a kind⇔outcome CHECK and a MODIFIED⇔applied_text CHECK, applied_text, review item / candidate reference /
preparation / validation / time & reading revision / candidate / finding / rule / target timed unit /
transcript & revision / media & timeline, run/unit, sequence, reason, previous_revision_id). Co-persist a
`DomainResultReference` (kind `subtitle_decision_revision`, `upstream = (review decision DomainResult,)`,
media/timeline from the validation) in one `BEGIN IMMEDIATE` transaction with linkage + identity-absence
checks and complete rollback. `_migrate_v17_to_v18` additive; downgrades and direct skips rejected; every
released version v1..v17 chains to v18 preserving existing data and meaning.

## 7. Slice Sequence

### Slice 1 — Goal Baseline and Assessment
Review: Optional — Skipped. Commit: `docs: add subtitle decision application goal`

### Slice 2 — Subtitle Decision Application Records
`SubtitleDecisionRevisionId`, `SubtitleAppliedOutcome`, `applied_outcome_for_kind`,
`SubtitleDecisionRevision`, `SubtitleDecisionRevisionIdentityPlan`, `SUBTITLE_DECISION_REVISION_RESULT_KIND`,
exports, focused record tests (kind⇔outcome; Modify requires applied text; Accept/Reject carry none;
append-only lineage). Review: Required — Executed. Commit: `feat: add subtitle decision revision records`

### Slice 3 — Deterministic Decision Application Service
`SubtitleDecisionRevisionService.apply_decision(...)` admits one `SubtitleReviewDecision`, reads the
validation + finding read-only, derives the outcome, carries the modified text for Modify, and builds the
`PreparedSubtitleDecisionRevision` (no write, no upstream mutation). Review: Required — Executed. Commit:
`feat: apply subtitle review decision into next revision`

### Slice 4 — Atomic SQLite Persistence, Restart, Replay and Migration Compatibility
Additive schema v18, repository, atomic command, composition, `record_application` path, restart/replay,
v1..v17 → v18 compatibility, idempotency. Review: Required — Executed. Commit:
`feat: persist subtitle decision revision atomically`

### Slice 5 — Fake-Review / Fake-Transcript Acceptance
End-to-end: validation → review preparation → decisions → apply Accept/Reject/Modify → next revisions with
correct outcome + applied text; persist → reopen → identical reconstruction → identical replay → idempotent
upstream (decision/item/preparation/validation unchanged) → no downstream (no final/artifact). Review:
Optional — Skipped (harness/test only). Commit: `test: verify subtitle decision application acceptance`

## 8. Milestone-Specific Verify

The next revision is produced only from one canonical `SubtitleReviewDecision`; outcome is the
deterministic function of the decision kind (Accept→ACCEPTED, Reject→REJECTED, Modify→MODIFIED); Modify
carries the decision's modified text and Accept/Reject carry none; the targeted timed unit is the
finding's `target_timed_unit_id`; full decision + validation lineage and DomainResult chaining
(`upstream = decision DomainResult`) preserved; **no existing canonical artifact is modified** — the
`SubtitleReviewDecision`, `ReviewItem`, `SubtitleReviewPreparation`, and `SubtitleValidation` are
byte-identical before/after; immutable records; append-only sequence/previous lineage; duplicate-identity /
DomainResult collisions roll back atomically; identical canonical input + identity plan → byte-identical
revision; replay after restart → byte-equivalent; repeated application mutates no upstream record; **no
final subtitle selection, current selection, readiness, applicability, provider, or artifact behavior is
produced**. (Generic validation inherited.)

## 9. Status (living)

### Completed Capabilities
```text
None yet
```
### Remaining Milestones
```text
Slice 1 — Goal Baseline and Assessment
Slice 2 — Subtitle Decision Application Records
Slice 3 — Deterministic Decision Application Service
Slice 4 — Atomic SQLite Persistence, Restart, Replay and Migration Compatibility
Slice 5 — Fake-Review / Fake-Transcript Acceptance
```
### Immediate Next Slice
```text
Slice 1 — Goal Baseline and Assessment
```

## 10. Completion Report — Milestone Additions

Beyond the inherited base skeleton, add: Canonical Decision-Revision Model; Admission Boundary (one
SubtitleReviewDecision; validation/finding read-only); Deterministic Application (Accept/Reject/Modify →
outcome + applied text); No-Mutation Guarantee; Common Review Vocabulary Reuse; Provenance & DomainResult
Chaining; Persistence Model; Restart and Replay Acceptance; Migration Compatibility; Idempotency
Verification; Provider-Boundary Deferral Note; Deferred Final-Subtitle/Selection Register.

## 11. Milestone Overrides (optional)

None — this milestone uses the inherited critical-only review policy and all default execution behavior
without deviation.

---

### Deliberately deferred capabilities (recorded for the completion report)
**Final Subtitle selection (§4.8)**; **current selection**, **readiness**, and **applicability** derivation;
full multi-unit final-subtitle materialization, cue removal/reordering, and Corrected Transcript change;
conflict/reconciliation adjudication; automatic approval; human decision recording; AI-generated decisions;
UI behavior; and export. This stage applies one recorded decision into the next revision only.
