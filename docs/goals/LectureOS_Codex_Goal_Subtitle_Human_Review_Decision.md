# LectureOS Codex Goal — Subtitle Human Review Decision

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

Establish the durable **Subtitle Human Review Decision** stage — the prerequisite to
`041_SUBTITLE_PIPELINE.md §4.7 Decision Application`. It records a Human reviewer's Accept, Reject
or Modify judgement against **exactly one** common `ReviewItem` produced by Subtitle Review
Preparation (§4.6), as an immutable durable aggregate `SubtitleReviewDecision`. It exercises Human
Authority **only** — it never applies the decision, produces no Subtitle revision, no Final Subtitle,
no applicability/selection, and no automatic approval. Lifecycle: `… → Subtitle Structural Validation
→ Subtitle Review Preparation → **Subtitle Human Review Decision** (this milestone) → Decision
Application (§4.7) → Final Subtitle`. This stage exists because the repository has no durable,
subtitle-consumable Review Decision: the common `ReviewDecision` is in-memory only, and the durable
`TranscriptReviewDecision` is transcript-coupled and rejects `subtitle_validation_finding` candidate
references.

## 2. Baseline

Start `HEAD 1ac378e`, branch `main`, `SQLITE_SCHEMA_VERSION 16`. Authority order inherited from
`AGENTS.md`.

## 3. Bounded Assessment & Architect Decision

**Admission boundary.** The canonical admission authority is the **supplied common `ReviewItem`**
produced by Subtitle Review Preparation. Human Authority is always exercised against **exactly one
`ReviewItem`**. The `SubtitleReviewPreparation` aggregate is **not** the review target — it exists
only as the immutable container, ordering and provenance boundary for those Review Items. This stage
**never** operates directly on Validation Findings or on the Preparation aggregate as a target: the
preparation is loaded only to validate that the supplied Review Item belongs to it and to carry
subtitle provenance (source validation / time revision / finding / rule).

**Architect Decision (subtitle-scoped durable decision, common vocabulary).** Add one new
Application-owned durable aggregate `SubtitleReviewDecision` (identity `SubtitleReviewDecisionId`)
reusing the common Review vocabulary (`ReviewItem`, `CandidateReference`, `ReviewContext`,
`ReviewDecision` semantics, `DecisionKind`, `HumanActorReference`). It **mirrors** the transcript v7
precedent (`TranscriptReviewDecision`) but is **subtitle-scoped** — it admits Review Items whose
candidate reference kind is `subtitle_validation_finding` and carries subtitle provenance instead of
transcript-revision coupling. It does **not** reuse `TranscriptReviewDecision` (which is coupled to
transcript correction candidates). No provider/capability boundary. Additive schema **v17**. The
in-memory `subtitle/` domain and `application/subtitle_decision.py` (legacy in-memory) are untouched.

**Architect Decision (record only, deterministic).** The decision timestamp is a caller-supplied,
timezone-aware command input; the Application never reads a wall-clock, so reconstruction and replay
are deterministic. The stage records; it never applies, derives, selects, or approves. **Architect
Checklist result: all No — additive.**

## 4. Scope

- **Included:**
  - canonical `SubtitleReviewDecision` aggregate recording one Human Accept/Reject/Modify against one
    common `ReviewItem`
  - reuse of the common Review vocabulary (ReviewItem, CandidateReference, ReviewContext, DecisionKind,
    HumanActorReference)
  - admission solely from a supplied common `ReviewItem`; the `SubtitleReviewPreparation` is the
    container/provenance boundary (validated for membership, never the target)
  - ReviewItem + CandidateReference linkage; subtitle provenance (source preparation / validation /
    time revision / finding + stable rule)
  - reviewer is a Human actor; `DecisionKind` (Accept/Reject/Modify); Modify requires non-empty
    modified text; Accept/Reject carry none
  - caller-supplied timezone-aware decision timestamp (deterministic replay)
  - execution provenance; DomainResult linkage (`upstream = review preparation DomainResult`)
  - append-only `sequence`/`previous_decision_id`
  - atomic SQLite **v17** persistence; restart reconstruction; deterministic replay; idempotency
  - migration compatibility (v1..v16 → v17)
  - fake-review / fake-transcript acceptance recording Accept/Reject/Modify
- **Excluded (later stages / other authority):**
  - Decision Application (§4.7): applying the decision, connecting it to candidate/revision
  - Subtitle revision generation reflecting a Modify; Final Subtitle selection (§4.8)
  - applicability, current selection, readiness, or any derivation from the decision
  - automatic approval; AI-generated decisions; any provider or capability port
  - mutation of Preparation/Validation/Time/Reading/Candidate records; changes to the common `review/`
    contracts or the in-memory subtitle domain

Recording a decision mutates no upstream record and applies nothing.

## 5. Canonical Model

- **Identity:** `SubtitleReviewDecisionId` (`OpaqueIdentity`, in `application/identities.py`).
- **Aggregate `SubtitleReviewDecision`:** `identity`; `domain_result_id`; `review_item_id` (the target);
  `candidate_reference_id`; `source_preparation_id`; `source_validation_id`; `source_time_revision_id`;
  `source_finding_id`; `rule` (non-blank stable rule id); `reviewer` (`HumanActorReference`);
  `kind` (`DecisionKind`); `decided_at` (tz-aware datetime); `run_id`; `unit_execution_id`; `sequence`;
  `previous_decision_id`; `rationale` (optional, non-blank); `modified_text` (optional). Invariants:
  reviewer is Human; non-negative sequence; tz-aware timestamp; Modify requires non-empty modified text
  and Accept/Reject carry none; non-blank rationale/rule; first has no previous decision.
- **Identity plan:** `SubtitleReviewDecisionIdentityPlan(decision_id, decision_result_id, decided_at)`
  (caller-supplied tz-aware timestamp).

## 6. Persistence

Additive SQLite **v17**: one flat table `subtitle_review_decisions` (identity, DomainResult, review
item, candidate reference, source preparation/validation/time-revision/finding, rule, reviewer, kind
CHECK IN accept/reject/modify, decided_at, run/unit, sequence, previous, rationale, modified_text; the
Modify⇔modified_text and sequence/previous CHECKs mirror the transcript decision table). Co-persist a
`DomainResultReference` (kind `subtitle_review_decision`, `upstream = (review preparation DomainResult,)`,
media/timeline from the preparation) in one `BEGIN IMMEDIATE` transaction with linkage +
identity-absence checks and complete rollback. `_migrate_v16_to_v17` additive; downgrades and direct
skips rejected; every released version v1..v16 chains to v17 preserving existing data and meaning.

## 7. Slice Sequence

### Slice 1 — Goal Baseline and Assessment
Review: Optional — Skipped. Commit: `docs: add subtitle human review decision goal`

### Slice 2 — Subtitle Human Review Decision Records
`SubtitleReviewDecisionId`, `SubtitleReviewDecision`, `SubtitleReviewDecisionIdentityPlan`,
`SUBTITLE_REVIEW_DECISION_RESULT_KIND`, exports, focused record tests (Modify requires text; Accept/
Reject carry none; reviewer human; tz-aware timestamp; append-only lineage). Review: Required —
Executed. Commit: `feat: add subtitle human review decision records`

### Slice 3 — Deterministic Human Review Decision Service
`SubtitleReviewDecisionService.prepare_decision(...)` admits the supplied Review Item, validates it
belongs to the supplied preparation, resolves its candidate reference (kind `subtitle_validation_finding`),
records the Human Accept/Reject/Modify with subtitle provenance, and builds the `PreparedSubtitleReviewDecision`
(no write). Review: Required — Executed. Commit: `feat: record subtitle human review decision from review item`

### Slice 4 — Atomic SQLite Persistence, Restart, Replay and Migration Compatibility
Additive schema v17, repository, atomic command, composition, `record_decision` path, restart/replay,
v1..v16 → v17 compatibility, idempotency. Review: Required — Executed. Commit:
`feat: persist subtitle human review decision atomically`

### Slice 5 — Fake-Review / Fake-Transcript Acceptance
End-to-end: validation → review preparation → record Accept, an append-only Modify (with text), and
Reject against distinct Review Items; persist → reopen → identical reconstruction → identical replay →
idempotent upstream preparation → nothing applied (no subtitle revision / final / artifact). Review:
Optional — Skipped (harness/test only). Commit: `test: verify subtitle human review decision acceptance`

## 8. Milestone-Specific Verify

Decision recorded only against a supplied common `ReviewItem` that belongs to the supplied
`SubtitleReviewPreparation`; the preparation is never the target and is not mutated; the candidate
reference kind must be `subtitle_validation_finding`; reviewer must be a Human actor; Accept/Reject/Modify
recorded with Modify requiring non-empty modified text; subtitle provenance (preparation/validation/time
revision/finding/rule) and DomainResult linkage (`upstream = preparation DomainResult`) preserved; the
caller-supplied tz-aware timestamp is stored verbatim (no wall-clock); immutable records; append-only
sequence/previous lineage (a second decision on the same item supersedes without mutating the first);
duplicate-identity / DomainResult collisions roll back atomically; identical canonical input + identity
plan → byte-identical decision; replay after restart → byte-equivalent; repeated recording mutates no
upstream record; **nothing is applied — no subtitle revision, no applicability/selection, no final
subtitle, no provider, no artifact behavior is produced**. (Generic validation inherited.)

## 9. Status (living)

### Completed Capabilities
```text
Slice 1 — Goal Baseline and Assessment
- commit `752fe4b` — `docs: add subtitle human review decision goal`
- bounded assessment: no substantive blocker; the supplied common ReviewItem is the admission
  authority (the SubtitleReviewPreparation is the container/provenance boundary, never the target);
  reuses the common Review vocabulary; introduces a subtitle-scoped durable SubtitleReviewDecision
  (mirrors transcript v7, does not reuse the transcript-coupled aggregate); records only, applies
  nothing; caller-supplied deterministic timestamp; additive schema v17
- Review: Optional — Skipped (documentation only)

Slice 2 — Subtitle Human Review Decision Records
- commit `1a0c841` — `feat: add subtitle human review decision records`
- `SubtitleReviewDecisionId` added to application identities
- `SubtitleReviewDecision` aggregate: identity, DomainResult linkage, review item + candidate
  reference, subtitle provenance (source preparation/validation/time-revision/finding + stable rule),
  reviewer (HumanActorReference), DecisionKind, caller-supplied tz-aware decided_at, execution
  provenance, append-only sequence/previous linkage, optional rationale/modified_text; invariants:
  reviewer human, non-blank rule, non-negative sequence, tz-aware timestamp, Modify requires text and
  Accept/Reject carry none, non-blank rationale, first has no previous
- `SubtitleReviewDecisionIdentityPlan` (decision id, result id, tz-aware timestamp)
- 14 focused record tests passed; complete suite 1075 passed
- Required Claude Review: Inconclusive — no critical findings identified (additive immutable records;
  transcript-parity invariants + subtitle provenance; no defect)

Slice 3 — Deterministic Human Review Decision Service
- commit `32b5be0` — `feat: record subtitle human review decision from review item`
- `SubtitleReviewDecisionService.prepare_decision(...)` admits the supplied common Review Item (the
  target), loads the SubtitleReviewPreparation only as the container/provenance boundary, validates the
  item belongs to it, resolves the candidate reference (kind must be `subtitle_validation_finding`) and
  its `subtitle_time_revision:` provenance, requires a Human actor + running execution, and records the
  Accept/Reject/Modify with subtitle provenance carried from the preparation's item link (finding + rule)
- no wall-clock (caller-supplied timestamp); performs no write; mutates no upstream record; applies
  nothing
- `PreparedSubtitleReviewDecision`, `AtomicSubtitleReviewDecisionPersistence` port,
  `SubtitleReviewPreparationQuery` + `ReviewItemQuery` + `CandidateReferenceQuery` protocols,
  `SubtitleReviewDecisionError`
- 15 focused service tests (Accept/Reject/Modify; Modify requires text; Accept carries none; non-human
  reviewer; item not in preparation; wrong candidate kind; provenance mismatch; unknown preparation/item;
  running-execution; append-only supersession; determinism; no-persistence) passed; complete suite 1090 passed
- Required Claude Review: Inconclusive — no critical findings identified (records against one Review
  Item; no application, no persistence, no upstream mutation, Human Authority exercised)

Slice 4 — Atomic SQLite Persistence, Restart, Replay and Migration Compatibility
- commit `d73d4e5` — `feat: persist subtitle human review decision atomically`
- additive SQLite schema v17: one flat table `subtitle_review_decisions` (subtitle provenance columns +
  reviewer/kind/decided_at/sequence/previous/rationale/modified_text; Modify⇔modified_text and
  sequence/previous CHECKs mirror the transcript decision table)
- `_migrate_v16_to_v17` additive; downgrades and direct skips rejected; existing v1–v16 unchanged
- `SQLiteSubtitleReviewDecisionCommandPersistence.persist_subtitle_review_decision(...)` writes the
  decision and its co-persisted DomainResultReference in one `BEGIN IMMEDIATE` transaction; validates
  linkage and identity absence; rolls back completely on collision/linkage/write/commit failure; the
  caller-supplied timestamp is stored verbatim via isoformat/fromisoformat; no upstream mutation
- `SQLiteSubtitleReviewDecisionRepository` reconstructs the exact decision after restart
- composition `compose_sqlite_subtitle_review_decision_service` wires the durable preparation +
  common review-item + common candidate-reference repositories + decision persistence
- migration compatibility verified: every released version v1..v16 chains to v17 preserving data;
  idempotency verified (upstream preparation + review items byte-identical); superseded-latest test
  expectations updated (v2/v3/v4/v5/processing_units 16→17; v6..v16 unsupported-target guards 17→18;
  v9..v16 chain helpers extended with the v16 addition block; v16 no-op/fresh-init/version realigned)
- 13 focused v17 tests (migration, full v1..v16→v17 chain, restart, replay incl. Modify, idempotency,
  atomic rollback) passed; complete suite 1103 passed
- Required Claude Review: PASS — independent bounded review verified atomicity/rollback,
  identity-collision atomicity, provenance linkage, additive migration + chain compatibility,
  18-column DDL/expected-columns exactness, the decided_at isoformat round-trip, and the
  Modify⇔modified_text/sequence CHECK↔dataclass consistency; no critical findings

Slice 5 — Fake-Review / Fake-Transcript Acceptance
- commit `5b8b701` — `test: verify subtitle human review decision acceptance`
- `lectureos.subtitle_review_decision_acceptance` drives the full pipeline (fake correction provider and
  fake reviewer, no network, no credential, fixed timestamps) through candidate → reading → time →
  validation → review preparation, then records Accept, an append-only Modify (with text), and Reject
  against the prepared Review Items → atomic v17 persistence → reopen → exact restart reconstruction →
  identical deterministic replay
- verifies the three decisions are recorded with subtitle provenance + DomainResult chaining, each
  traced to its review item's source finding + rule; append-only supersession (Modify references the
  Accept, sequence 1); recording mutates no upstream preparation/items and applies nothing — the review
  items remain OPEN (no automatic approval); restart reconstruction; deterministic replay; and no
  downstream final / artifact table produced
- acceptance summary: decision_count 3, and every kind / append-only / provenance / finding-traced /
  idempotency / items-open / restart / replay / no-downstream flag true
- focused acceptance test passed; complete suite 1104 passed
- Blueprint Drift Check: PASS — dependency direction unchanged, no provider owns decision identity/
  lifecycle, no existing enum/aggregate/service meaning changed (the common `review/` contracts and
  in-memory subtitle domain are untouched; the transcript-coupled TranscriptReviewDecision is not
  reused), schema strictly additive, nothing applied (no decision application/selection/final/artifact),
  Human Authority exercised (Human actor records the decision), append-only immutable lifecycle
- Migration Compatibility: PASS — every released version v1..v16 chains to v17 preserving data
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

Beyond the inherited base skeleton, add: Canonical Decision Model; Admission Boundary (ReviewItem is
the authority; Preparation is container); Record-Only Human Authority (no application); Common Review
Vocabulary Reuse; Subtitle Provenance & DomainResult Chaining; Deterministic Timestamp; Persistence
Model; Restart and Replay Acceptance; Migration Compatibility; Idempotency Verification;
Provider-Boundary Deferral Note; Deferred Decision-Application/Selection Register.

## 11. Milestone Overrides (optional)

None — this milestone uses the inherited critical-only review policy and all default execution behavior
without deviation.

---

### Deliberately deferred capabilities (recorded for the completion report)
**Decision Application (§4.7)** — applying the decision, connecting Accept/Reject/Modify to the Subtitle
Candidate/revision, and producing a Modify-reflecting Subtitle revision; **Final Subtitle (§4.8)**;
applicability/current-selection/readiness derivation from the decision; automatic approval; AI-generated
decisions; and any conflict/reconciliation adjudication. This stage records Human judgement only.
