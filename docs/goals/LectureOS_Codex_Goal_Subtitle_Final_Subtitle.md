# LectureOS Codex Goal — Subtitle Final Subtitle

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

Establish the final Subtitle Pipeline stage (`041_SUBTITLE_PIPELINE.md §4.8 Final Subtitle`): from
exactly one canonical `SubtitleDecisionRevision`, deterministically **distinguish the authoritative,
approved-state Subtitle representation** — the Final Subtitle — reflecting the applicable Review
Decision, and preserve provenance to the Corrected Transcript, Source Timeline, subtitle revision, and
user decision. Final Subtitle is a **deterministic selection** stage, not a transformation: it
establishes which representation is authoritative after human decisions have been applied. Lifecycle:
`… → Subtitle Human Review Decision → Subtitle Decision Application → **Subtitle Final Subtitle** (this
milestone)`. The Final state is the logical "Artifact Generation Ready State" (a status, not an
artifact); this stage never records or applies a decision, performs no structural validation, generates
no export or playback artifact, and performs no AI inference.

## 2. Baseline

Start `HEAD 3d0b10b`, branch `main`, `SQLITE_SCHEMA_VERSION 18`. Authority order inherited from
`AGENTS.md`.

## 3. Bounded Assessment & Architect Decision

**Admission boundary.** The canonical admission authority is **exactly one `SubtitleDecisionRevision`**
(v18). It carries everything Final needs (applied outcome, applied text, target unit, and the full
lineage to the review decision / validation / time & reading revision / candidate / transcript / media &
timeline), so Final admits only the decision revision and reads nothing else. The `SubtitleDecisionRevision`,
`SubtitleReviewDecision`, `ReviewItem`, `SubtitleReviewPreparation` and `SubtitleValidation` are **never
mutated**. The only newly created canonical artifact is the Final Subtitle (`SubtitleFinalSubtitle`) and
its `DomainResultReference`.

**Architect Decision (deterministic selection; no separate content entity).** Add one new
Application-owned durable aggregate `SubtitleFinalSubtitle` (identity `SubtitleFinalSubtitleId`) and enum
`SubtitleFinalOutcome` (`FINAL` | `NOT_FINAL`, a pure deterministic function of the applied outcome:
`ACCEPTED → FINAL`, `MODIFIED → FINAL`, `REJECTED → NOT_FINAL`). Per §4.8 it produces **no separate
approved-Subtitle content entity** — the Final Subtitle is a finalization/selection record that
distinguishes the authoritative representation and preserves provenance, not a copy of the subtitle
content. It reuses the common Review vocabulary (`DecisionKind`) via the carried decision-revision fields.
No provider/capability boundary. Additive schema **v19**. The in-memory `subtitle/` domain (including its
`FinalSubtitleSelectionId` / `final_selection.py`) is untouched.

**Architect Decision (append-only; deterministic).** Applying one decision revision produces one
`SubtitleFinalSubtitle` with the deterministic `final_outcome`, carrying the decision-revision lineage and
chaining its DomainResult upstream to the decision revision. Append-only `sequence`/`previous_final_id`.
No wall-clock; deterministic replay. **Architect Checklist result: all No — additive.**

## 4. Scope

- **Included:**
  - canonical `SubtitleFinalSubtitle` aggregate + `SubtitleFinalOutcome` enum (FINAL / NOT_FINAL)
  - deterministic selection from one `SubtitleDecisionRevision` (ACCEPTED/MODIFIED → FINAL, REJECTED →
    NOT_FINAL)
  - admission solely from one canonical `SubtitleDecisionRevision`; nothing else read
  - carried lineage: applied outcome + applied text + decision kind; review decision / review item /
    candidate reference / preparation / validation / time & reading revision / candidate / finding + rule /
    target timed unit / transcript & revision / media & timeline; execution provenance; DomainResult
    linkage (`upstream = decision revision DomainResult`)
  - append-only `sequence`/`previous_final_id`
  - atomic SQLite **v19** persistence; restart reconstruction; deterministic replay; idempotency
  - migration compatibility (v1..v18 → v19)
  - fake-review / fake-transcript acceptance selecting Final from Accept/Modify and NOT_FINAL from Reject
- **Excluded (other authority / later pipelines):**
  - recording or applying decisions; structural validation; current selection / readiness / applicability
    derivation beyond the deterministic Final mapping
  - a separate approved-Subtitle content entity; external subtitle files; export; playback/screen
    rendering; Artifact Generation (`044` Export Pipeline)
  - AI inference; any provider or capability port
  - mutation of the `SubtitleDecisionRevision`, `SubtitleReviewDecision`, `ReviewItem`,
    `SubtitleReviewPreparation`, `SubtitleValidation`, or any earlier revision; changes to the common
    `review/` contracts or the in-memory subtitle domain

Establishing the Final Subtitle mutates no existing canonical artifact and generates no artifact/export.

## 5. Canonical Model

- **Identity:** `SubtitleFinalSubtitleId` (`OpaqueIdentity`, in `application/identities.py`).
- **Enum `SubtitleFinalOutcome`:** `FINAL` | `NOT_FINAL`; `final_outcome_for_applied_outcome` maps
  `ACCEPTED → FINAL`, `MODIFIED → FINAL`, `REJECTED → NOT_FINAL`.
- **Aggregate `SubtitleFinalSubtitle`:** `identity`; `domain_result_id`; `source_decision_revision_id`;
  `decision_kind`; `applied_outcome`; `final_outcome`; carried lineage (`source_review_decision_id`,
  `review_item_id`, `candidate_reference_id`, `source_preparation_id`, `source_validation_id`,
  `source_time_revision_id`, `source_reading_revision_id`, `source_candidate_id`, `source_finding_id`,
  `rule`, `source_transcript_id`, `source_revision_id`, `source_media_id`, `source_timeline_id`);
  `run_id`; `unit_execution_id`; `sequence`; `reason`; `target_timed_unit_id` (optional); `applied_text`
  (optional, Modify only); `previous_final_id` (optional). Invariants: `applied_outcome ==
  applied_outcome_for_kind(decision_kind)`; `final_outcome == final_outcome_for_applied_outcome(applied_outcome)`;
  `MODIFIED` requires non-empty `applied_text` and `ACCEPTED`/`REJECTED` carry none; non-blank rule/reason;
  non-negative sequence; first has no previous.
- **Identity plan:** `SubtitleFinalSubtitleIdentityPlan(final_id, final_result_id)`.

## 6. Persistence

Additive SQLite **v19**: one flat table `subtitle_final_subtitles` (identity, DomainResult, decision
revision, decision_kind CHECK IN accept/reject/modify, applied_outcome CHECK IN accepted/rejected/modified
with a kind⇔applied_outcome CHECK, final_outcome CHECK IN final/not_final with an applied_outcome⇔final
CHECK and a MODIFIED⇔applied_text CHECK, applied_text, review decision / review item / candidate reference /
preparation / validation / time & reading revision / candidate / finding / rule / target timed unit /
transcript & revision / media & timeline, run/unit, sequence, reason, previous_final_id). Co-persist a
`DomainResultReference` (kind `subtitle_final_subtitle`, `upstream = (decision revision DomainResult,)`,
media/timeline from the decision revision) in one `BEGIN IMMEDIATE` transaction with linkage +
identity-absence checks and complete rollback. `_migrate_v18_to_v19` additive; downgrades and direct skips
rejected; every released version v1..v18 chains to v19 preserving existing data and meaning.

## 7. Slice Sequence

### Slice 1 — Goal Baseline and Assessment
Review: Optional — Skipped. Commit: `docs: add subtitle final subtitle goal`

### Slice 2 — Final Subtitle Records
`SubtitleFinalSubtitleId`, `SubtitleFinalOutcome`, `final_outcome_for_applied_outcome`,
`SubtitleFinalSubtitle`, `SubtitleFinalSubtitleIdentityPlan`, `SUBTITLE_FINAL_SUBTITLE_RESULT_KIND`,
exports, focused record tests (applied⇔final mapping; kind⇔applied; Modify requires applied text;
append-only lineage). Review: Required — Executed. Commit: `feat: add subtitle final subtitle records`

### Slice 3 — Deterministic Final Subtitle Service
`SubtitleFinalSubtitleService.select_final(...)` admits one `SubtitleDecisionRevision`, requires a running
execution, derives the final outcome, carries the decision-revision lineage, and builds the
`PreparedSubtitleFinalSubtitle` (no write, no upstream mutation). Review: Required — Executed. Commit:
`feat: select final subtitle from decision revision`

### Slice 4 — Atomic SQLite Persistence, Restart, Replay and Migration Compatibility
Additive schema v19, repository, atomic command, composition, `record_final` path, restart/replay,
v1..v18 → v19 compatibility, idempotency. Review: Required — Executed. Commit:
`feat: persist subtitle final subtitle atomically`

### Slice 5 — Fake-Review / Fake-Transcript Acceptance
End-to-end: decisions → decision revisions → select Final from Accept and Modify (FINAL) and Reject
(NOT_FINAL); persist → reopen → identical reconstruction → identical replay → idempotent upstream
(decision revision unchanged) → no downstream (no artifact/export). Review: Optional — Skipped
(harness/test only). Commit: `test: verify subtitle final subtitle acceptance`

## 8. Milestone-Specific Verify

The Final Subtitle is produced only from one canonical `SubtitleDecisionRevision`; `final_outcome` is the
deterministic function of the applied outcome (ACCEPTED/MODIFIED → FINAL, REJECTED → NOT_FINAL); the
applied outcome matches the decision kind and Modify carries the applied text (Accept/Reject carry none);
full decision-revision lineage and DomainResult chaining (`upstream = decision revision DomainResult`)
preserved; **no existing canonical artifact is modified** — the `SubtitleDecisionRevision`,
`SubtitleReviewDecision`, `ReviewItem`, `SubtitleReviewPreparation`, and `SubtitleValidation` are
byte-identical before/after; no separate approved-Subtitle content entity, no export, and no artifact is
produced; immutable records; append-only sequence/previous lineage; duplicate-identity / DomainResult
collisions roll back atomically; identical canonical input + identity plan → byte-identical Final Subtitle;
replay after restart → byte-equivalent; repeated selection mutates no upstream record; **no decision
recording/application, structural validation, export, playback, provider, or AI behavior is produced**.
(Generic validation inherited.)

## 9. Status (living)

### Completed Capabilities
```text
None yet
```
### Remaining Milestones
```text
Slice 1 — Goal Baseline and Assessment
Slice 2 — Final Subtitle Records
Slice 3 — Deterministic Final Subtitle Service
Slice 4 — Atomic SQLite Persistence, Restart, Replay and Migration Compatibility
Slice 5 — Fake-Review / Fake-Transcript Acceptance
```
### Immediate Next Slice
```text
Slice 1 — Goal Baseline and Assessment
```

## 10. Completion Report — Milestone Additions

Beyond the inherited base skeleton, add: Canonical Final-Subtitle Model; Admission Boundary (one
SubtitleDecisionRevision; nothing else read); Deterministic Selection (applied outcome → FINAL/NOT_FINAL);
No-Mutation & No-Content-Entity Guarantee; Provenance & DomainResult Chaining; Persistence Model; Restart
and Replay Acceptance; Migration Compatibility; Idempotency Verification; Provider-Boundary Deferral Note;
Blueprint Completion Status; Remaining Pipeline Work (Export §044).

## 11. Milestone Overrides (optional)

None — this milestone uses the inherited critical-only review policy and all default execution behavior
without deviation.

---

### Deliberately deferred capabilities (recorded for the completion report)
**Artifact Generation / Export (`044` Export Pipeline)** — external subtitle files (SRT etc.), export, and
playback/screen rendering; a separate approved-Subtitle content entity; conflict/reconciliation
adjudication; and any AI inference. Final Subtitle only distinguishes the authoritative representation and
preserves provenance; the Artifact Generation Ready State is a logical status of the FINAL outcome.
