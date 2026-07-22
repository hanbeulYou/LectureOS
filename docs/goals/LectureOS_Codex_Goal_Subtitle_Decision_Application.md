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
Slice 1 — Goal Baseline and Assessment
- commit `50d093c` — `docs: add subtitle decision application goal`
- bounded assessment: no substantive blocker; admits exactly one SubtitleReviewDecision; validation +
  finding read read-only for lineage and the target unit; the only new artifact is the next revision;
  no existing artifact modified; distinct names from the legacy in-memory subtitle_decision.py;
  additive schema v18
- Review: Optional — Skipped (documentation only)

Slice 2 — Subtitle Decision Application Records
- commit `30e8e82` — `feat: add subtitle decision revision records`
- `SubtitleDecisionRevisionId` added to application identities
- `SubtitleAppliedOutcome` enum (ACCEPTED/REJECTED/MODIFIED) + `applied_outcome_for_kind` deterministic
  mapping (ACCEPT→ACCEPTED, REJECT→REJECTED, MODIFY→MODIFIED)
- `SubtitleDecisionRevision` aggregate: identity, DomainResult linkage, source review decision, decision
  kind, derived outcome, optional applied_text, review item + candidate reference, preparation/validation/
  time & reading revision/candidate/finding + stable rule, optional target timed unit, transcript & revision,
  media & timeline, execution provenance, append-only sequence/previous linkage, deterministic reason;
  invariants: outcome matches the kind mapping, MODIFIED requires applied text and ACCEPTED/REJECTED carry
  none, non-blank rule/reason, non-negative sequence, first has no previous
- `SubtitleDecisionRevisionIdentityPlan` (revision id, result id); names distinct from the legacy
  in-memory `SubtitleDecisionApplication*`
- 14 focused record tests passed; complete suite 1118 passed
- Required Claude Review: Inconclusive — no critical findings identified (additive immutable records;
  kind⇔outcome⇔applied_text enforced; no defect)

Slice 3 — Deterministic Decision Application Service
- commit `bbb5b5d` — `feat: apply subtitle review decision into next revision`
- `SubtitleDecisionRevisionService.apply_decision(...)` admits exactly one `SubtitleReviewDecision`,
  requires a running execution, reads the validation + finding read-only (for lineage + target timed
  unit), derives the outcome (Accept→ACCEPTED, Reject→REJECTED, Modify→MODIFIED), carries the modified
  text for Modify, and builds the next `SubtitleDecisionRevision`
- pure deterministic transformation; no wall-clock; performs no write; mutates no upstream record (the
  decision, review item, preparation and validation are untouched); revision DomainResult upstream = the
  decision DomainResult
- `PreparedSubtitleDecisionRevision`, `AtomicSubtitleDecisionRevisionPersistence` port,
  `SubtitleReviewDecisionQuery` + `SubtitleValidationQuery` protocols, `SubtitleDecisionApplicationError`
- 8 focused service tests (Accept/Reject/Modify outcomes + applied text; lineage from the validation;
  unknown decision/finding; running-execution; determinism; no-persistence) passed; complete suite 1126 passed
- Required Claude Review: Inconclusive — no critical findings identified (pure deterministic application;
  admits one decision; no upstream mutation, no persistence, no selection/final)

Slice 4 — Atomic SQLite Persistence, Restart, Replay and Migration Compatibility
- commit `28200de` — `feat: persist subtitle decision revision atomically`
- additive SQLite schema v18: one flat table `subtitle_decision_revisions` (kind⇔outcome and
  MODIFIED⇔applied_text and sequence/previous CHECKs)
- `_migrate_v17_to_v18` additive; downgrades and direct skips rejected; existing v1–v17 unchanged
- `SQLiteSubtitleDecisionRevisionCommandPersistence.persist_subtitle_decision_revision(...)` writes the
  revision and its co-persisted DomainResultReference in one `BEGIN IMMEDIATE` transaction; validates
  linkage and identity absence; rolls back completely on collision/linkage/write/commit failure; no
  upstream mutation
- `SQLiteSubtitleDecisionRevisionRepository` reconstructs the exact revision after restart
- composition `compose_sqlite_subtitle_decision_application_service` wires the durable review-decision +
  validation repositories + decision-revision persistence
- migration compatibility verified: every released version v1..v17 chains to v18 preserving data;
  idempotency verified (upstream decision byte-identical); superseded-latest test expectations updated
  (v2/v3/v4/v5/processing_units 17→18; v6..v17 unsupported-target guards 18→19; v9..v17 chain helpers
  extended with the v17 addition block; v17 no-op/fresh-init/version realigned)
- 13 focused v18 tests (migration, full v1..v17→v18 chain, restart, replay incl. Modify applied text,
  idempotency, atomic rollback) passed; complete suite 1139 passed
- Required Claude Review: PASS — independent bounded review verified atomicity/rollback,
  identity-collision atomicity, provenance linkage, additive migration + chain compatibility, the full
  25-column DDL↔expected-columns↔INSERT↔restore index mapping, and the kind⇔outcome⇔applied_text
  CHECK↔dataclass consistency; no critical findings

Slice 5 — Fake-Review / Fake-Transcript Acceptance
- commit `be8bee1` — `test: verify subtitle decision application acceptance`
- `lectureos.subtitle_decision_application_acceptance` drives the full pipeline (fake correction provider
  and fake reviewer, no network, no credential, fixed timestamps) through candidate → reading → time →
  validation → review preparation → human review decision, then applies the recorded Accept, Modify and
  Reject decisions → next revisions → atomic v18 persistence → reopen → exact restart reconstruction →
  identical deterministic replay
- verifies the three next revisions' outcomes (ACCEPTED/REJECTED/MODIFIED), the Modify applied text and
  Accept/Reject carrying none, subtitle provenance + DomainResult chaining (upstream = decision result)
  and finding/rule traceability; that application mutates no existing canonical artifact (decision /
  review item / preparation / validation byte-identical before and after); restart reconstruction;
  deterministic replay; and no downstream final / artifact table produced
- acceptance summary: revision_count 3, and every outcome / applied-text / provenance / target-traced /
  no-upstream-mutation / restart / replay / no-downstream flag true
- focused acceptance test passed; complete suite 1140 passed
- Blueprint Drift Check: PASS — dependency direction unchanged, no provider owns revision identity/
  lifecycle, no existing enum/aggregate/service meaning changed (the common `review/` contracts, the
  durable review-decision/validation contracts, and the legacy in-memory subtitle domain are untouched),
  schema strictly additive, no existing canonical artifact modified, no final selection/current selection/
  readiness/applicability produced, Human Authority preserved (only recorded decisions are applied)
- Migration Compatibility: PASS — every released version v1..v17 chains to v18 preserving data
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
