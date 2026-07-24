# Implementation Milestones

- Status: Active Implementation Record
- Blueprint Baseline: v1

## M1 — Credentialed Real Media to SRT

- Verification status: **VERIFIED**
- Verified on: 2026-07-19
- Implementation commit: `f6416e45b4aef3319ef24ff4b0c399160bb522c9`
- Provider: `openai:whisper-1`
- Input: local `.mov` classroom validation video
- Media duration: 96.010 seconds
- Transcript segments: 38
- Subtitle cues: 38
- Physical SRT materialization: successful

The credentialed validation exercised real `ffmpeg` audio extraction, the actual
OpenAI transcription endpoint, provider-to-Transcript mapping, Transcript and
Subtitle review/validation, Final Selection, SRT export, and local file
materialization.

No input media, generated SRT, API credential, private student information, or
classroom transcript content is stored in this repository.

### Observed Quality Limitations

- Whisper segments currently map one-to-one to Subtitle Cues.
- Classroom and literary terminology included recognition errors.
- Classical Korean poetry quotations and refrain expressions were recognized poorly.
- Very short utterances can become isolated Subtitle Cues.
- Reading-rate optimization, line wrapping, semantic merging, and cue splitting
  are not implemented.
- Automatic review and approval remain demo-only behavior.

M1 proves execution viability. It does not approve current transcript or
subtitle quality for production. These observations are validation evidence,
not new Domain contracts.

## Durable Execution Persistence

Completed foundation and command capabilities:

- SQLite schema v4 with canonical DomainResultReference and Failure structures
- SQLite repositories for ProcessingUnit, ProcessingRun, UnitExecution, Failure,
  and DomainResultReference
- atomic Start, terminal Failure, and Retry persistence boundaries
- ExecutionService wiring for Start, terminal Failure, and Retry

`SQLiteDomainResultReferenceRepository` stores immutable canonical Result
references in the normalized v4 parent and ordered-lineage tables. It preserves
typed optional references, upstream ordering and duplicates, rejects identity
reuse, and remains unavailable without migration on schema v1-v3.

Atomic Result Persistence now stores every supplied new canonical Result plus
the final UnitExecution and ProcessingRun snapshots in one caller-connection
SQLite transaction. It is schema-v4 gated, preserves supplied ordering, rejects
any canonical Result identity collision, and rolls back the complete command on
linkage, write, or commit failure.

ExecutionService Result Wiring is complete. `record_results(...)` preserves its
existing lifecycle validation, final outcome and ordered references, then calls
the Application-owned atomic Result port exactly once. The v4 composition root
injects one SQLite command adapter for Start, Failure, Retry, and Result and a
canonical DomainResultReference repository for command validation and reads.

The Diagnostic Persistence Assessment is complete. Canonical Diagnostic
persistence remains explicitly deferred: existing records preserve ordered
opaque DiagnosticId references, but no production producer or resolving consumer
currently requires a canonical table or repository, and Retry authority does not
consult diagnostics. See `070_DIAGNOSTIC_PERSISTENCE_ASSESSMENT.md`.

The Durability Goal is complete. Durable SQLite execution now covers canonical
Failure and DomainResultReference records and atomic Start, terminal Failure,
Retry, and terminal Result commands through ExecutionService. A new product
milestone must be selected before further persistence scope is introduced.

## Canonical Transcript Foundation

- Goal: `docs/goals/LectureOS_Codex_Goal_Canonical_Transcript_Foundation.md`
- Status: **COMPLETE**
- Completed slices: Transcript Persistence Composition Assessment; Complete
  Transcript Schema and Migration; Provider Provenance Resolution and Segment
  Repository; Raw Transcript Atomic Persistence; Correction Candidate Persistence;
  Corrected Transcript Revision Persistence; Canonical Transcript Composition and
  Restart Acceptance
- Immediate next slice: None — select the next Blueprint-ordered product milestone

### Approved Architect Decisions

- The selected target schema is v5. It is the next released version after the
  frozen complete v4 and will introduce the complete canonical Transcript
  foundation in one version.
- `ProviderTranscriptResult` is a Transcript-owned immutable provenance record,
  not an independent product aggregate. Existing Execution/Result durability
  cannot reconstruct its provider content, capability, plugin, diagnostic, and
  uncertainty fields, so v5 requires normalized provider-result storage.
- Existing v4 `DomainResultReference` storage remains canonical. The producing
  Raw Transcript, Correction Candidate, or Corrected Revision command owns the
  first insertion of its generated reference in the same transaction as its
  concrete record. The same identity must not later be submitted to
  `ExecutionService.record_results()` as a new canonical Result.
- Approved atomic sets are: ProviderTranscriptResult alone; RawTranscript plus
  all supplied new TranscriptSegments plus its DomainResultReference;
  CorrectionCandidate plus its DomainResultReference; and
  CorrectedTranscriptRevision plus only absent supplied TranscriptSegments plus
  its DomainResultReference.
- Application performs execution, provenance, membership, ordering, and lineage
  validation before persistence. SQLite command adapters perform only schema,
  identity, serialization, and representation-linkage checks and own rollback.
- Public repository protocols remain unchanged. Command composition uses
  Application-owned ports and SQLite-package-internal non-committing writers.
- Combining Transcript production with Execution terminal Result orchestration
  is deferred beyond this canonical foundation. Existing Execution terminal
  Result behavior is not changed by this Goal.

### Schema v5 Foundation

SQLite schema v5 is the complete v4 schema plus normalized structures for
ProviderTranscriptResult provenance, TranscriptSegment, RawTranscript,
CorrectionCandidate, and CorrectedTranscriptRevision. Ordered diagnostic,
segment, evidence, and candidate references use owned ordinal child tables.

New databases initialize directly as complete v5. Migration supports only the
explicit v4-to-v5 step and v5 validated no-op at this target; direct v1-v3 to v5,
downgrade, and automatic chaining remain rejected. The migration performs no
canonical Transcript backfill and preserves every existing v4 record on success
or rollback.

Validation completed with 51 focused migration tests and 609 complete tests.
The Required Claude Review returned explicit `Verdict: PASS` using the final
20-turn focused budget after earlier 6-turn and 10-turn attempts ended without a
verdict. It reported no Blocking Issues, no Missing Tests, and no Blueprint
Clarification requirement.

### Durable Transcript Source Records

`SQLiteProviderTranscriptResultRepository` persists the Transcript-owned exact
provider provenance body, including ordered duplicate DiagnosticId references,
without treating it as a separate product aggregate. `SQLiteTranscriptSegmentRepository`
persists exact timed or untimed immutable Segment records. Both repositories are
schema-v5 gated, reject every identity reuse, own their standalone transaction,
preserve caller connections, and reconstruct exact Domain records after restart.

### Atomic Raw Transcript Persistence

`TranscriptService.create_raw_transcript(...)` retains all existing Application
validation and computes its canonical `DomainResultReference` before invoking
the Application-owned `AtomicRawTranscriptPersistence` port exactly once. The
SQLite adapter atomically inserts the RawTranscript, every supplied new Segment,
and the existing-v4 canonical Result reference using one caller-owned connection.
All identity collisions, linkage mismatches, write failures, and commit failures
roll back the complete set. The public RawTranscript repository remains
independently self-transactional, and Application code imports no SQLite types.
Focused tests and the complete 624-test suite passed. The Required Claude Review
returned explicit `Verdict: PASS` with no Blocking Issues or Missing Tests using
a 20-turn focused rerun after the initial 6-turn run ended without a verdict.

### Durable Correction Candidates

`TranscriptService.create_correction_candidate(...)` preserves existing source,
segment, target-revision, execution, and upstream-lineage validation, computes the
canonical Result reference, and invokes `AtomicCorrectionCandidatePersistence`
exactly once. SQLite atomically first-inserts the immutable Candidate with exact
ordered evidence and the existing-v4 canonical Result reference. Standalone
repository saves remain self-transactional; collision, write, result, and commit
failure paths preserve the complete previous state.
Focused Candidate tests and the complete 633-test suite passed after adding the
reviewer-suggested non-null target-revision round-trip case. The Required Claude
Review returned explicit `Verdict: PASS` with no Blocking Issues using a 20-turn
focused rerun after the initial 6-turn run ended without a verdict.

### Durable Corrected Transcript Revisions

`TranscriptService.create_corrected_revision(...)` preserves existing parent,
candidate, execution, Segment membership, order, and lineage validation, computes
the canonical Result reference, and invokes
`AtomicCorrectedTranscriptRevisionPersistence` exactly once. SQLite atomically
first-inserts the immutable Revision, inserts only absent supplied Segments while
reusing exact existing Segments, and first-inserts the existing-v4 canonical
Result reference. The standalone Revision repository remains self-transactional
and reconstructs the exactly-one parent plus ordered Segment and Candidate
references. Focused Revision tests and the complete 641-test suite passed before
the required independent review. The initial 6-turn review ended without a
verdict; the final focused 20-turn review returned explicit `Verdict: PASS` with
no Blocking Issues, no Missing Tests, and no Blueprint Clarification requirement.

### Canonical Transcript Composition and Restart Acceptance

`compose_sqlite_transcript_service(...)` constructs all v5 canonical Transcript
repositories and one `SQLiteTranscriptCommandPersistence` on a caller-owned
connection while accepting only an Application `ExecutionQueryBoundary`.
Acceptance coverage persists real Domain-shaped provider provenance, ordered Raw
Segments, a CorrectionCandidate, and two linked CorrectedTranscriptRevisions,
then closes and reopens SQLite and reconstructs the exact canonical lineage.
A deterministic failed second Revision proves rollback and prior-lineage
preservation across restart. This composition does not require durable Review,
Subtitle, Artifact, Diagnostic, or external correction-provider capabilities.

The Canonical Transcript Foundation Goal is complete. It establishes durable
canonical Transcript provenance, Segments, RawTranscript, CorrectionCandidate,
CorrectedTranscriptRevision, Result-reference composition, Application wiring,
and restart reconstruction. Review persistence, Subtitle persistence, Artifact
persistence, correction provider integration, and broader product milestones
remain separately deferred according to Blueprint dependency order.

## Transcript Correction Application Foundation

- Goal: `docs/goals/LectureOS_Codex_Goal_Transcript_Correction_Application_Foundation.md`
- Status: **COMPLETE**
- Completed slices: Correction Application Composition Assessment; Correction
  Capability Contract; Correction Proposal Validation and Canonical Construction;
  Atomic Correction Generation Persistence; Structural Validation Integration;
  In-Memory Acceptance and Restart Verification
- Immediate next slice: Goal Complete

### Approved Architect Decisions

- The Application request selects a canonical Raw Transcript and optional parent
  Revision, running execution, and correction Capability. Application resolves an
  immutable provider-neutral Segment context; providers receive no repositories or
  hidden global context.
- A proposal is one text replacement targeting one existing Segment, with rationale,
  ordered evidence and optional confidence, uncertainty and provenance hints. Split,
  merge, deletion and provider-controlled timestamp changes are unsupported.
- Providers never supply canonical identities. The caller supplies a deterministic
  identity plan for Candidate/Result/replacement Segment tuples plus the proposed
  Revision, Revision Result and Validation identities.
- The generation port returns zero or more ordered proposals. Duplicate targets are
  rejected. Zero proposals is a successful no-op with no canonical writes.
- Valid proposals form one proposed Revision with unchanged Segments reused and one
  traceable replacement Segment per proposal. It has no Human Decision, validation
  reference or applicability authority.
- All Candidates and Candidate Results, replacement Segments, the Revision and Revision
  Result form one atomic v5 command. Request and proposal DTOs are not persisted.
- Structural Validation runs after canonical proposal persistence because the existing
  validator queries stored revisions. Invalid structure remains explicit and unapproved;
  Validation persistence is deferred and no Transcript Ready State is claimed.
- Provider, proposal, persistence and validation-operation failures propagate without
  fallback, retry, alternate provider, false success or implicit Execution Failure write.

### Correction Capability Contract

The Application-owned `CorrectionGenerationPort` accepts an immutable canonical
request containing Raw/parent lineage, execution, Capability and provider-neutral
Segment context, and returns an ordered tuple of non-canonical
`CorrectionProposal` values. Proposals carry only a target Segment, proposed text,
rationale, evidence, uncertainty/confidence and optional opaque provenance hints.
An explicit `CorrectionGenerationFailure` represents capability failure. A separate
caller-owned identity plan supplies every future canonical identity, so provider
output cannot control Candidate, Segment, Revision, Result or Validation identity.
The contract imports no SQLite, network client, credential or concrete provider.
The one bounded 6-turn required review ended without a verdict and reported no
concrete critical issue; it is recorded as
`Inconclusive — no critical findings identified` under the global review policy.

### Correction Application Composition and Restart Acceptance

`compose_sqlite_transcript_correction_generation_service(...)` assembles a
provider-independent generation service from a caller-owned SQLite connection,
Application execution query, fake-or-future capability port, one shared Transcript
command adapter, canonical Transcript repositories and the existing structural validator.
Acceptance coverage sends two deterministic proposals through the complete Application
flow and reconstructs every Candidate, replacement Segment, proposed Revision and Result
exactly after restart. Validation remains non-durable and non-authoritative. No concrete
provider, network, credential, Review, Subtitle, Artifact or Diagnostic capability was
introduced.
The production composition boundary raised this slice to Required review. Its one bounded
6-turn review ended without a verdict and identified no concrete critical issue; it is
recorded as `Inconclusive — no critical findings identified`.

The Transcript Correction Application Foundation Goal is complete. It establishes the
provider-independent capability contract, canonical proposal construction, atomic durable
coordination, structural Validation boundary and restart-safe fake-provider acceptance.

## Concrete Transcript Correction Provider

- Goal: `docs/goals/LectureOS_Codex_Goal_Concrete_Transcript_Correction_Provider.md`
- Status: **COMPLETE**
- Selected provider: OpenAI Responses API, `gpt-5.6-terra`
- Completed slices: Provider Decision and Goal Baseline; OpenAI Correction Adapter;
  Credentialed Korean Acceptance
- Immediate next slice: Goal Complete

The provider choice is a bounded implementation Architect Decision. OpenAI is selected
because strict JSON Schema output satisfies the existing neutral proposal contract, the
repository already has a credential-safe `OPENAI_API_KEY` convention and credentialed API
acceptance experience, and a dependency-free REST adapter can avoid a new SDK dependency.
The adapter will send only correction context, set `store: false`, never persist raw provider
payloads, and use synthetic non-sensitive Korean text for credentialed acceptance.

### OpenAI Correction Adapter

`OpenAITranscriptCorrectionAdapter` implements the existing Application-owned port using
dependency-free HTTPS translation to the Responses API. It selects `gpt-5.6-terra`, sends
`store: false`, requests strict JSON Schema output, and deterministically reconstructs only
provider-neutral ordered proposals. Credential absence, transport/timeout/HTTP failure,
refusal, incomplete response, invalid JSON, wrong shapes and invalid numeric values map to
`CorrectionGenerationFailure` without exposing credentials or persisting raw payloads.
The one bounded 6-turn required review ended without a verdict and identified no concrete
critical issue; it is recorded as `Inconclusive — no critical findings identified`.

### Credentialed Korean Acceptance

The synthetic Korean acceptance module and no-network end-to-end restart test are
implemented and the complete 670-test suite passes. The credentialed Responses API
acceptance was executed successfully outside Codex with provider `openai:gpt-5.6-terra`,
`proposal_count: 1`, `structural_valid: true`, and
`canonical_restart_verified: true`. No additional paid request was made during resume.
No credential value, raw provider payload or sensitive Transcript was printed, persisted,
or committed. Review classification is Optional — Skipped because this slice adds only the
acceptance harness and tests without changing the adapter or production contracts.

The Concrete Transcript Correction Provider Goal is complete. One concrete OpenAI adapter
now reaches the existing provider-independent correction Application, canonical persistence,
structural Validation and restart reconstruction without introducing provider selection,
fallback, Review authority or downstream product capabilities.

### Structural Validation Integration

`TranscriptCorrectionGenerationService.generate_correction(...)` invokes the existing
provider-independent structural Validation boundary only after the complete canonical
proposal transaction commits. The returned prepared result carries the exact Validation
record. Structural invalidity is returned normally while the Revision remains unapproved,
and a Validation operation failure propagates without misrepresenting or rolling back the
already committed proposed correction. The zero-proposal path invokes neither persistence
nor Validation. No durable Validation, Review or Human Authority behavior was added.
The one bounded 6-turn required review returned no verdict and identified no concrete
critical issue; it is recorded as
`Inconclusive — no critical findings identified` under the global review policy.

### Correction Proposal Orchestration

`TranscriptCorrectionGenerationService.prepare_correction(...)` loads the canonical
Raw/parent Revision and running execution before invoking the capability exactly
once. It constructs immutable ordered Segment context, rejects unsupported,
unknown, duplicate, blank, non-finite or capability-mismatched proposals, validates
caller-owned identity cardinality/uniqueness/absence, and computes exact immutable
Candidates, traceable replacement Segments, one unapproved proposed Revision and
their Result references. Zero proposals is an explicit no-op. This slice performs
no canonical write; the complete prepared command is reserved for the next atomic
persistence boundary.
The one bounded 6-turn required review ended without a verdict and identified no
concrete critical issue; it is recorded as
`Inconclusive — no critical findings identified`.

### Atomic Correction Generation Persistence

`TranscriptCorrectionGenerationService.generate_correction(...)` invokes the
Application-owned `AtomicGeneratedCorrectionPersistence` port exactly once for a
non-empty prepared correction and performs no write for the explicit zero-proposal
case. `SQLiteTranscriptCommandPersistence` owns one v5 transaction containing every
Candidate, Candidate Result, replacement Segment, the proposed Revision and its Result.
It verifies parent lineage, target membership, source provenance, ordered references and
identity absence before using existing non-committing writers. Collision, linkage, late
write and commit failures roll back the complete record set; successful records reconstruct
exactly after restart. No schema, migration, Review or concrete-provider behavior changed.
The one bounded 6-turn required review ended without a verdict and identified no
concrete critical issue; it is recorded as
`Inconclusive — no critical findings identified` under the global review policy.

## Transcript Review Preparation

- Goal: `docs/goals/LectureOS_Codex_Goal_Transcript_Review_Preparation.md`
- Status: **COMPLETE**
- Selected persistence: additive SQLite schema v6
- Completed slices: Goal Baseline and Assessment; Review Preparation Records;
  Deterministic Review Preparation Service; Atomic SQLite Persistence and Restart;
  Fake-Provider / Fake-Review Acceptance
- Immediate next slice: Goal Complete

This milestone prepares canonical proposed Transcript corrections for Human Review without
introducing Review decisions or changing Transcript state. It is purely preparatory:
`Product → Application → Capability Contract → Provider` and the lifecycle position
`Transcript → Proposed Revision → Review Preparation` are preserved, while Human Review
Decision, applicability and current selection remain out of scope.

The bounded architectural assessment found no substantive blocker. The existing in-memory
`review/` domain types (`CandidateReference`, `ReviewContext`, `ReviewItem`) are reused as
the canonical review-preparation vocabulary; a single Application-owned aggregate
`TranscriptReviewPreparation` is added to carry review ordering, candidate grouping, review
metadata, provenance, DomainResult linkage and structural integrity. A new
`TranscriptReviewPreparationService` mirrors the correction-generation `prepare`/persist split
with an Application-owned identity plan, and an additive SQLite schema v6 adds atomic
persistence and restart reconstruction for the preparation subset only. Providers remain
unchanged and never own Review identity or Review lifecycle. The AGENTS.md Architect Checklist
is entirely `No`: no existing Domain contract change, no released-schema meaning change, no
lifecycle authority change, no responsibility shift, no new identity semantics, one additive
migration, and no Blueprint contradiction.

The Transcript Review Preparation Goal is complete. `TranscriptReviewPreparationService`
deterministically maps a canonical proposed `CorrectedTranscriptRevision` and its
`CorrectionCandidate` set into canonical Review Items, a Review Context and Candidate
References, preserving the established cross-domain contract that a Candidate Reference
identity equals its Correction Candidate identity. It computes review ordering, target-Segment
grouping, review metadata and structural integrity, and validates candidate lineage, parent
Revision linkage, execution provenance and DomainResult provenance before any write.
`SQLiteReviewPreparationCommandPersistence` persists the aggregate, the reused review records
and the preparation's DomainResultReference in one atomic v6 transaction with restart-safe
reconstruction. An in-process fake-provider / fake-review acceptance drives the full pipeline
with no network or credential and confirms deterministic generation, immutable lineage, parent
Revision linkage, Candidate linkage, execution provenance, atomic persistence, restart
reconstruction and structural integrity. The complete 701-test suite passes. No Human Review
Decision, applicability, current selection or downstream product behavior was introduced.

## Transcript Human Review Decision

- Goal: `docs/goals/LectureOS_Codex_Goal_Transcript_Human_Review_Decision.md`
- Status: **COMPLETE**
- Selected persistence: additive SQLite schema v7
- Completed slices: Goal Baseline and Assessment; Review Decision Records; Deterministic
  Review Decision Service; Atomic SQLite Persistence, Restart and Replay; Fake-Review
  Acceptance
- Immediate next slice: Goal Complete

This milestone durably records canonical Human Review Decisions (Accept, Reject, Modify) on
prepared Review Items without triggering any downstream automation. It is purely a recording
of Human judgement: `Product → Application → Capability → Provider` and the lifecycle position
`Transcript → Proposed Revision → Review Preparation → Human Review Decision` are preserved,
while Applicability, Current Selection, Transcript Ready and Subtitle generation remain out of
scope. Human Decision never automatically changes selection, approves or rejects revisions,
updates applicability, produces Transcript Ready, or generates subtitles.

The bounded architectural assessment found no substantive blocker. The existing in-memory
review vocabulary (`DecisionKind`, `HumanActorReference`) is reused unchanged; a single
Application-owned aggregate `TranscriptReviewDecision` is added to carry decision identity,
kind, reviewer identity, a caller-supplied decision timestamp, rationale, Review Item /
Candidate / Revision linkage, append-only sequence lineage and DomainResult linkage. A new
`TranscriptReviewDecisionService` mirrors the established `prepare`/persist split with an
Application-owned identity-and-timestamp plan, and an additive SQLite schema v7 adds atomic
persistence, restart reconstruction and deterministic replay for the decision record only.
The decision timestamp is a command input, never generated from wall-clock, guaranteeing
deterministic replay. Providers are unchanged and never own Decision identity or lifecycle.
The AGENTS.md Architect Checklist is entirely `No`: no existing Domain contract change (the
released `ReviewDecision`/`ReviewService` are untouched), no released-schema meaning change,
no lifecycle authority change, no responsibility shift, no new identity semantics, one additive
migration, and no Blueprint contradiction with `043_REVIEW_PIPELINE.md`.

The Transcript Human Review Decision Goal is complete. `TranscriptReviewDecisionService`
records a reviewer's Accept, Reject or Modify judgement as an immutable
`TranscriptReviewDecision` aggregate, validating that the referenced Review Item belongs to a
durable Review Preparation, that the candidate and revision provenance match, that the reviewer
is a Human actor, that the execution is running, and that Modify carries text while Accept and
Reject do not. The decision timestamp is a caller-supplied command input, so
`SQLiteReviewDecisionCommandPersistence` — which writes the decision and its co-persisted
DomainResultReference in one atomic v7 transaction — reconstructs each decision exactly after
restart and reproduces identical decisions on deterministic replay into a fresh database. An
in-process fake-review acceptance records Accept, an append-only Modify on the same item, and
Reject, confirming immutable Decision records, Review Item / Candidate / Revision linkage,
reviewer and execution provenance, append-only lineage, atomic persistence, restart
reconstruction, structural integrity and deterministic replay. The complete 733-test suite
passes. Recording a decision triggers no downstream automation: no applicability, current
selection, Transcript Ready, subtitle or artifact behavior was introduced.

## Transcript Applicability

- Goal: `docs/goals/LectureOS_Codex_Goal_Transcript_Applicability.md`
- Status: **COMPLETE**
- Selected persistence: additive SQLite schema v8
- Completed slices: Goal Baseline and Assessment; Applicability Records; Deterministic
  Applicability Evaluation Service; Atomic SQLite Persistence, Restart and Replay;
  Fake-Review Acceptance
- Immediate next slice: Goal Complete

This milestone deterministically derives and durably records the applicability of a proposed
Transcript Revision from a canonical Human Review Decision, without selecting a current revision
or producing a Transcript Ready state. `Product → Application → Capability → Provider` and the
lifecycle position `Transcript → Proposed Revision → Review Preparation → Human Review Decision
→ Applicability` are preserved, while Current Selection, Transcript Ready and Subtitle
generation remain out of scope. Applicability is derived only from canonical Human Review
Decisions; providers have no responsibility.

The bounded architectural assessment found no substantive blocker. The pre-existing in-memory
`transcript/applicability.py` service — a broader manual applicability plus Current Selection
concern bound to the old review vocabulary — is left unchanged; a single Application-owned
aggregate `TranscriptApplicabilityEvaluation` is added, together with a focused
`ApplicabilityOutcome` enum (`APPLICABLE` from Accept, `NOT_APPLICABLE` from Reject,
`SUPERSEDED_BY_MODIFICATION` from Modify) that is a pure deterministic function of the decision
kind. A new `TranscriptApplicabilityEvaluationService` mirrors the established `prepare`/persist
split with an Application-owned identity plan, and an additive SQLite schema v8 adds atomic
persistence, restart reconstruction and deterministic replay for the evaluation record only. No
wall-clock is read, so replay is deterministic. The AGENTS.md Architect Checklist is entirely
`No`: no existing Domain contract change, no released-schema meaning change, no lifecycle
authority change (applicability is derived, not decided), no responsibility shift, no new
identity semantics, one additive migration, and no Blueprint contradiction.

The Transcript Applicability Goal is complete. `TranscriptApplicabilityEvaluationService`
loads a canonical Human Review Decision and deterministically derives the applicability of the
proposed Revision — `APPLICABLE` from Accept, `NOT_APPLICABLE` from Reject,
`SUPERSEDED_BY_MODIFICATION` from Modify — carrying the decision / review item / candidate /
revision linkage and execution provenance into an immutable `TranscriptApplicabilityEvaluation`
aggregate. `SQLiteApplicabilityEvaluationCommandPersistence` writes the evaluation and its
co-persisted DomainResultReference in one atomic v8 transaction, reconstructs each evaluation
exactly after restart, and reproduces identical evaluations on deterministic replay into a
fresh database (no wall-clock is read). An in-process fake-review acceptance records Accept,
Reject and Modify decisions and derives the three corresponding outcomes, confirming immutable
Applicability records, Review Decision / Review Item / Candidate / Revision linkage, execution
provenance, deterministic evaluation, atomic persistence, restart reconstruction, structural
integrity and deterministic replay. The complete 760-test suite passes. A Blueprint Drift Check
confirmed no drift relative to any prior completed milestone: the authority chain is preserved,
the schema change is strictly additive, applicability derives only from canonical Human Review
Decisions, and no Current Selection, Transcript Ready, subtitle, artifact or other
forbidden-scope behavior was introduced. The pre-existing in-memory `transcript/applicability.py`
service remains unchanged.

## Transcript Current Selection

- Goal: `docs/goals/LectureOS_Codex_Goal_Transcript_Current_Selection.md`
- Status: **COMPLETE**
- Selected persistence: additive SQLite schema v9
- Completed slices: Goal Baseline and Assessment; Current Selection Records; Deterministic
  Current Selection Service; Atomic SQLite Persistence, Restart, Replay and Migration
  Compatibility; Fake-Review Acceptance
- Immediate next slice: Goal Complete

This milestone deterministically derives and durably records which proposed Transcript Revision
is currently selected, from a canonical Applicability evaluation, without implying a Transcript
Ready state. `Product → Application → Capability → Provider` and the lifecycle position
`Transcript → Proposed Revision → Review Preparation → Human Review Decision → Applicability →
Current Selection` are preserved, while Transcript Ready, Subtitle generation and downstream
execution remain out of scope. Current Selection is derived only from canonical Applicability
evaluations; providers have no responsibility, and selecting a revision never implies the
Transcript is Ready.

The bounded architectural assessment found no substantive blocker. The pre-existing in-memory
`CurrentTranscriptSelection` (working-context, old review vocabulary, not derived from canonical
applicability) is left unchanged; a single Application-owned aggregate `TranscriptCurrentSelection`
is added, together with a focused `CurrentSelectionOutcome` enum (`SELECTED` from APPLICABLE,
`NOT_SELECTED` from NOT_APPLICABLE or SUPERSEDED_BY_MODIFICATION) that is a pure deterministic
function of the applicability outcome. A new `TranscriptCurrentSelectionService` mirrors the
established `evaluate`/persist split with an Application-owned identity plan, and an additive
SQLite schema v9 adds atomic persistence, restart reconstruction and deterministic replay for
the selection record only. No wall-clock is read, so replay is deterministic. The AGENTS.md
Architect Checklist is entirely `No`: no existing Domain contract change, no released-schema
meaning change, no lifecycle authority change (selection is derived, not decided, and never
produces Transcript Ready), no responsibility shift, no new identity semantics, one additive
migration, and no Blueprint contradiction. Migration compatibility from every released version
(v1..v8) to v9 will be verified in Slice 4.

The Transcript Current Selection Goal is complete. `TranscriptCurrentSelectionService` loads a
canonical Applicability evaluation and deterministically derives which proposed Revision is
currently selected — `SELECTED` from an APPLICABLE evaluation, `NOT_SELECTED` from
NOT_APPLICABLE or SUPERSEDED_BY_MODIFICATION — carrying the applicability / decision / review
item / candidate / revision linkage and execution provenance into an immutable
`TranscriptCurrentSelection` aggregate. `SQLiteCurrentSelectionCommandPersistence` writes the
selection and its co-persisted DomainResultReference in one atomic v9 transaction, reconstructs
each selection exactly after restart, and reproduces identical selections on deterministic
replay into a fresh database (no wall-clock is read). An in-process fake-review acceptance
records Accept, Reject and Modify decisions, derives applicability, and derives the three
corresponding current-selection outcomes (selected, not_selected, not_selected), confirming
immutable Current Selection records, Applicability / Review Item / Candidate / Revision linkage,
execution provenance, deterministic selection, atomic persistence, restart reconstruction,
structural integrity and deterministic replay. The complete 788-test suite passes. A Blueprint
Drift Check confirmed no drift relative to any prior completed milestone, and migration
compatibility from every released version (v1..v8) to v9 is verified by an explicit
single-step-chain test that preserves existing data. Current Selection determines only which
Revision is currently selected; it never implies the Transcript is Ready, and no Transcript
Ready, subtitle, artifact, export or downstream-execution behavior was introduced. The
pre-existing in-memory `CurrentTranscriptSelection` model and service remain unchanged.

## Transcript Ready State

- Goal: `docs/goals/LectureOS_Codex_Goal_Transcript_Ready_State.md`
- Status: **COMPLETE**
- Selected persistence: additive SQLite schema v10
- Completed slices: Goal Baseline and Assessment; Readiness Records; Deterministic Readiness
  Evaluation Service; Atomic SQLite Persistence, Restart, Replay and Migration Compatibility;
  Fake-Review / Fake-Transcript Acceptance
- Immediate next slice: Goal Complete

This milestone deterministically evaluates and durably records whether the currently selected
Transcript Revision is ready for downstream use, from canonical upstream records only.
`Product → Application → Capability Contract → Provider` and the lifecycle position
`Transcript Revision → Review Preparation → Human Review Decision → Applicability → Current
Selection → Transcript Ready` are preserved, while Subtitle, Artifact, export and downstream
execution remain out of scope. Transcript Ready is derived only from canonical records;
providers have no responsibility. Recording READY starts no downstream capability, recording
NOT_READY mutates no upstream record, and Current Selection remains a distinct concern from
Transcript Ready (SELECTED does not itself imply READY).

The bounded architectural assessment found no substantive blocker and no undefined readiness
policy: the READY conditions are fully enumerated and all derivable from canonical durable
records (Current Selection v9, Applicability v8, Human Review Decision v7, CorrectedTranscript
Revision v5) plus a deterministic recomputation of the Revision's structural Validation via the
existing `TranscriptStructuralValidationBoundary`. Because `TranscriptValidation` is a
deterministic function of the durable Revision and is not itself a durably persisted aggregate,
the readiness evaluation recomputes it at evaluation time and links the readiness record to the
resulting canonical Validation; this preserves derivation-from-canonical and deterministic
replay while mutating no upstream record. A single Application-owned aggregate
`TranscriptReadinessEvaluation` is added, with focused `ReadinessOutcome` (READY / NOT_READY)
and `ReadinessReasonCode` (ALL_CONDITIONS_MET, NOT_SELECTED, NOT_APPLICABLE,
SUPERSEDED_BY_MODIFICATION, STRUCTURAL_VALIDATION_FAILED) enums. READY requires, at the
aggregate level, selection SELECTED and applicability APPLICABLE and structural_valid True, so
READY cannot be produced for NOT_SELECTED, NOT_APPLICABLE, SUPERSEDED_BY_MODIFICATION, or
structurally invalid lineage. A new `TranscriptReadinessEvaluationService` mirrors the
established evaluate/persist split with an Application-owned identity plan, and an additive
SQLite schema v10 adds atomic persistence, restart reconstruction and deterministic replay for
the readiness record only. No wall-clock is read. The AGENTS.md Architect Checklist is entirely
`No`: no existing Domain contract change, no released-schema meaning change, no lifecycle
authority change, no responsibility shift, no new identity semantics, one additive migration,
and no Blueprint contradiction. Migration compatibility from every released version (v1..v9) to
v10 will be verified in Slice 4.

The Transcript Ready State Goal is complete. `TranscriptReadinessEvaluationService` loads a
canonical Current Selection, cross-checks its Applicability, Review Decision and Revision lineage
against durable records, recomputes the selected Revision's structural Validation via the
existing `TranscriptStructuralValidationBoundary`, and deterministically evaluates READY only
when the selection is SELECTED, applicability is APPLICABLE, and structural Validation succeeds —
otherwise NOT_READY with a deterministic reason code (NOT_SELECTED, NOT_APPLICABLE,
SUPERSEDED_BY_MODIFICATION, or STRUCTURAL_VALIDATION_FAILED). The immutable
`TranscriptReadinessEvaluation` aggregate carries Current Selection / Applicability / Review
Decision / Review Item / Candidate / Revision / structural Validation linkage and execution
provenance, and enforces the READY conditions at the record level (a second defense alongside
the deterministic service derivation and the SQLite CHECK). `SQLiteReadinessEvaluationCommand
Persistence` writes the readiness record and its co-persisted DomainResultReference in one atomic
v10 transaction, reconstructs it exactly after restart, and reproduces byte-identical records on
deterministic replay into a fresh database. An in-process fake-review / fake-transcript acceptance
records Accept, Reject and Modify decisions and confirms only the accepted-selected-applicable-
valid Revision is READY, while rejected and modified lineages are NOT_READY; it further confirms
restart reconstruction, deterministic replay, idempotency (upstream Current Selection rows are
byte-identical before and after evaluation), and that no Subtitle/Artifact table or downstream
operation is produced. The complete 822-test suite passes. A Blueprint Drift Check confirmed no
drift relative to any prior completed milestone, and migration compatibility from every released
version (v1..v9) to v10 is verified by an explicit single-step-chain test that preserves existing
data and meaning. Recording readiness starts no downstream capability and mutates no upstream
record; Current Selection and Transcript Ready remain distinct canonical concerns; and the
existing structural Validation contract and in-memory selection/applicability services remain
unchanged. This completes the canonical Transcript pipeline through the Transcript Ready lifecycle
stage; Subtitle and Artifact stages remain out of scope and unstarted.

## Subtitle Transcript Intake

- Goal: `docs/goals/LectureOS_Codex_Goal_Subtitle_Transcript_Intake.md`
- Status: **COMPLETE**
- Selected persistence: additive SQLite schema v11
- Completed slices: Goal Baseline and Assessment; Intake Records; Deterministic Intake
  Service; Atomic SQLite Persistence, Restart, Replay and Migration Compatibility; Fake-Review
  / Fake-Transcript Acceptance
- Immediate next slice: Goal Complete

This milestone begins the Subtitle Pipeline (`docs/041_SUBTITLE_PIPELINE.md §4.1 Transcript
Intake`): it deterministically derives and durably records, from a canonical Transcript
Readiness Evaluation whose outcome is READY, whether the selected Corrected Transcript revision
is ELIGIBLE to begin subtitle work. `Product → Application → Capability Contract → Provider` and
the lifecycle position `… → Current Selection → Transcript Ready → Subtitle Transcript Intake →
Subtitle Candidate Generation → …` are preserved, while Subtitle Candidate Generation,
Reading/Time Representation, Subtitle Review, Final Subtitle, Artifact and export remain out of
scope. Intake is derived only from canonical records; providers have no responsibility; recording
intake mutates no upstream record and starts no downstream capability.

The bounded architectural assessment found no substantive blocker. The `TranscriptReadinessEvaluation`
(v10) is the canonical certificate consumed; source media/timeline are resolved from the durable
Corrected Transcript revision → Raw Transcript (v5); structural validity is inherited from the
readiness record (nothing recomputed — its `validation_id` is carried for provenance). A single
Application-owned aggregate `SubtitleTranscriptIntake` is added, with a focused
`SubtitleIntakeOutcome` enum (`ELIGIBLE` iff readiness `READY`, else `NOT_ELIGIBLE`) enforced at
the aggregate and SQLite-CHECK levels. A new `SubtitleTranscriptIntakeService` mirrors the
established evaluate/persist split with an Application-owned identity plan, and an additive SQLite
schema v11 adds atomic persistence, restart reconstruction and deterministic replay for the intake
record only. The AGENTS.md Architect Checklist is entirely `No`: no existing Domain contract
change, no released-schema meaning change, no lifecycle authority change, no responsibility shift,
no new identity semantics, one additive migration, and no Blueprint contradiction. The existing
in-memory `subtitle/` domain remains unchanged. Migration compatibility from every released
version (v1..v10) to v11 will be verified in Slice 4.

The Subtitle Transcript Intake Goal is complete. `SubtitleTranscriptIntakeService` loads a
canonical Transcript Readiness Evaluation, resolves the source Corrected Transcript revision →
Raw Transcript for source media/timeline, and deterministically derives whether the revision is
ELIGIBLE to begin subtitle work — ELIGIBLE only when the readiness outcome is READY, otherwise
NOT_ELIGIBLE — carrying the readiness lineage (selection/applicability/decision/item/candidate/
revision) and the structural `validation_id` into an immutable `SubtitleTranscriptIntake`
aggregate. `SQLiteSubtitleIntakeCommandPersistence` writes the intake and its co-persisted
DomainResultReference in one atomic v11 transaction, reconstructs it exactly after restart, and
reproduces byte-identical records on deterministic replay into a fresh database (no wall-clock is
read). An in-process fake-review / fake-transcript acceptance records Accept and Reject decisions
and confirms only the READY transcript is ELIGIBLE while the NOT_READY transcript is NOT_ELIGIBLE;
it further confirms restart reconstruction, deterministic replay, idempotency (upstream Readiness
rows byte-identical before and after evaluation), and that no subtitle candidate/revision/cue or
artifact table is produced. The complete 851-test suite passes. A Blueprint Drift Check confirmed
no drift relative to any prior completed milestone, and migration compatibility from every
released version (v1..v10) to v11 is verified by an explicit single-step-chain test that preserves
existing data and meaning. Recording intake starts no downstream capability and mutates no
upstream record; the existing in-memory `subtitle/` domain remains unchanged. This begins the
Subtitle Pipeline at stage 4.1 (Transcript Intake); Subtitle Candidate Generation and later
subtitle/artifact stages remain out of scope and unstarted.

## Subtitle Candidate Generation

- Goal: `docs/goals/LectureOS_Codex_Goal_Subtitle_Candidate_Generation.md`
- Status: **COMPLETE**
- Selected persistence: additive SQLite schema v12
- Completed slices: Goal Baseline and Assessment; Candidate Records; Deterministic Candidate
  Generation Service; Atomic SQLite Persistence, Restart, Replay and Migration Compatibility;
  Fake-Review / Fake-Transcript Acceptance
- Immediate next slice: Goal Complete

This milestone advances the Subtitle Pipeline to stage 4.2 (`docs/041_SUBTITLE_PIPELINE.md §4.2
Subtitle Candidate Generation`): from a canonical **ELIGIBLE** `SubtitleTranscriptIntake` (v11) it
deterministically proposes one durable `SubtitleCandidate` plus an ordered collection of candidate
`SubtitleCandidateCue` records (Subtitle Units) derived from the source Corrected Transcript
revision's ordered segments. `Product → Application → Capability Contract → Provider` and the
lifecycle position `… → Transcript Ready → Subtitle Transcript Intake → Subtitle Candidate
Generation → Reading Representation → Time Representation → …` are preserved, while Reading/Time
Representation, Subtitle structural Validation, Subtitle Review Preparation/Decision, Final
Subtitle, Artifact and export remain out of scope. Candidate generation is admitted only by an
ELIGIBLE intake (the sole admission authority), consumes no provider (a provider-independent
capability contract and a concrete AI provider are deferred to later, separate Goals), mutates no
upstream record and starts no downstream capability.

The bounded architectural assessment found no substantive blocker. The `SubtitleTranscriptIntake`
(v11) is the canonical certificate consumed; the source revision and its ordered segments are read
from the durable v5 records; source media/timeline and structural `validation_id` are carried from
the intake for provenance (nothing recomputed). New Application-owned durable types
`SubtitleCandidate` (identity `SubtitleCandidateId`) and ordered child `SubtitleCandidateCue`
(identity `SubtitleCandidateCueId`) are added; the pre-existing in-memory `subtitle/` domain
(including its same-named identities) is left unchanged and unimported by the durable contract.
**Segment↔cue cardinality is not a domain invariant:** the durable model permanently supports
one-to-many and many-to-one relationships (a cue references an ordered tuple of ≥1 source segments;
distinct cues may reference the same segment), so later Reading/Time Representation may merge or
split cues without any schema or model change. The initial deterministic, provider-free
implementation emits one cue per ordered source segment purely as an implementation strategy for
this milestone's baseline. A new `SubtitleCandidateGenerationService` mirrors the established
generate/persist split with an Application-owned identity plan; additive SQLite schema v12 adds a
`subtitle_candidates` parent table, an ordered `subtitle_candidate_cues` child and a
`subtitle_candidate_cue_segments` ordinal child, with atomic persistence, restart reconstruction
and deterministic replay. No wall-clock is read. The AGENTS.md Architect Checklist is entirely
`No`: no existing Domain contract change, no released-schema meaning change, no lifecycle authority
change, no responsibility shift, no new identity semantics, one additive migration, and no
Blueprint contradiction. Migration compatibility from every released version (v1..v11) to v12 is
verified.

The Subtitle Candidate Generation Goal is complete. `SubtitleCandidateGenerationService.generate_
candidate(...)` loads a canonical ELIGIBLE `SubtitleTranscriptIntake`, requires a running
execution, refuses a NOT_ELIGIBLE intake, loads the source Corrected Transcript revision's ordered
segments and deterministically derives one `SubtitleCandidate` plus an ordered collection of
`SubtitleCandidateCue` records — each traceable to its ordered source segment(s), the source
timeline range and the source revision — carrying the full intake/readiness/selection/
applicability/decision/item/candidate lineage and the structural `validation_id`.
`SQLiteSubtitleCandidateCommandPersistence` writes the candidate, its ordered cues (with their
ordered cue-segment provenance) and the co-persisted `DomainResultReference` (kind
`subtitle_candidate`, upstream = the intake DomainResult) in one atomic v12 transaction,
reconstructs the candidate and ordered cues exactly after restart, and reproduces byte-identical
records on deterministic replay into a fresh database. An in-process fake-review / fake-transcript
acceptance drives the full pipeline (fake correction provider and fake reviewer, no network, no
credential) and confirms only the ELIGIBLE intake yields a candidate while the NOT_ELIGIBLE intake
is refused; cue→segment/revision/transcript lineage; candidate intake lineage and source
media/timeline; execution provenance; atomic persistence; restart reconstruction; deterministic
replay; idempotency (upstream intake rows byte-identical before and after generation); and that no
later subtitle-revision / subtitle-cue / artifact table is produced. The complete 894-test suite
passes. A Blueprint Drift Check confirmed no drift relative to any prior completed milestone, and
migration compatibility from every released version (v1..v11) to v12 is verified by an explicit
single-step-chain test that preserves existing data and meaning. The durable cue model supports
one-to-many and many-to-one segment↔cue relationships so downstream stages may merge or split cues;
the in-memory `subtitle/` domain remains unchanged. This advances the Subtitle Pipeline to stage
4.2 (Subtitle Candidate Generation); Reading/Time Representation and later subtitle/artifact stages
remain out of scope and unstarted.

## Subtitle Reading Representation

- Goal: `docs/goals/LectureOS_Codex_Goal_Subtitle_Reading_Representation.md`
- Status: **COMPLETE**
- Selected persistence: additive SQLite schema v13
- Completed slices: Goal Baseline and Assessment; Reading Records; Deterministic Reading
  Representation Service; Atomic SQLite Persistence, Restart, Replay and Migration Compatibility;
  Fake-Review / Fake-Transcript Acceptance
- Immediate next slice: Goal Complete

This milestone advances the Subtitle Pipeline to stage 4.3 (`docs/041_SUBTITLE_PIPELINE.md §4.3
Reading Representation`, §6): from a canonical `SubtitleCandidate` (v12) and its ordered cues it
deterministically composes one **new immutable** subtitle reading revision (`SubtitleReadingRevision`)
plus an ordered collection of reading units (`SubtitleReadingUnit`) that carry an explicit,
reading-oriented text form (line composition). `Product → Application → Capability Contract →
Provider` and the lifecycle position `… → Subtitle Candidate Generation → Reading Representation →
Time Representation → Subtitle Structural Validation → …` are preserved, while Time Representation,
Subtitle structural Validation, Subtitle Review Preparation/Decision, Final Subtitle, Artifact and
export remain out of scope. Reading composition is admitted only by a durable `SubtitleCandidate`
(the sole admission authority), consumes no provider, produces a new immutable representation
(never overwriting the candidate), owns no time semantics, mutates no upstream record and starts no
downstream capability.

The bounded architectural assessment found no substantive blocker. The `SubtitleCandidate` and its
immutable cues are the canonical input (via `SQLiteSubtitleCandidateRepository.get` / `get_cue`); no
transcript access is needed. New Application-owned durable types `SubtitleReadingRevision` (identity
`SubtitleReadingRevisionId`) and ordered child `SubtitleReadingUnit` (identity
`SubtitleReadingUnitId`) are added; the pre-existing in-memory `subtitle/` domain is left unchanged
and unimported. **The baseline performs a deterministic reading transformation, not a pure
structural copy:** `compose_reading_lines` applies threshold-independent, meaning-preserving
normalization — whitespace normalization and line composition that preserves the source text's
existing hard-line structure — to produce each unit's ordered `lines`. **Merge/split cardinality is
not a domain invariant:** the durable model permanently supports cue merge (a unit references an
ordered tuple of ≥1 source cues) and split (distinct units reference the same cue) with complete
deterministic provenance; only policy-based merge/split is deferred, and the baseline emits one unit
per cue. **Timing is inherited metadata, not time authority:** each unit inherits its source cue's
timeline and time range unchanged; no timestamp is computed, inferred, or reordered (§4.4 Time
Representation owns time). A new `SubtitleReadingRepresentationService` mirrors the established
compose/persist split with an Application-owned identity plan; additive SQLite schema v13 adds a
`subtitle_reading_revisions` parent table, an ordered `subtitle_reading_units` child and two ordinal
grandchildren (`subtitle_reading_unit_source_cues`, `subtitle_reading_unit_lines`), with atomic
persistence, restart reconstruction and deterministic replay. No wall-clock is read. The AGENTS.md
Architect Checklist is entirely `No`: no existing Domain contract change, no released-schema meaning
change, no lifecycle authority change, no responsibility shift, no new identity semantics, one
additive migration, and no Blueprint contradiction. Migration compatibility from every released
version (v1..v12) to v13 is verified.

The Subtitle Reading Representation Goal is complete. `SubtitleReadingRepresentationService.compose_
reading(...)` loads a canonical `SubtitleCandidate`, requires a running execution, loads its ordered
cues and deterministically composes one new immutable `SubtitleReadingRevision` plus an ordered
collection of `SubtitleReadingUnit` records — each carrying a whitespace-normalized,
hard-line-preserving line composition of its source cue's text and traceable to its ordered source
cue(s) (and, via the immutable cues, the transcript segments) — carrying the full candidate lineage
and the structural `validation_id`, and inheriting each cue's timing metadata unchanged.
`SQLiteSubtitleReadingCommandPersistence` writes the revision, its ordered units (with their ordered
source-cue and line children) and the co-persisted `DomainResultReference` (kind
`subtitle_reading_revision`, upstream = the candidate DomainResult) in one atomic v13 transaction,
reconstructs the revision and ordered units exactly after restart, and reproduces byte-identical
records on deterministic replay into a fresh database. An in-process fake-review / fake-transcript
acceptance drives the full pipeline and confirms the candidate yields one reading revision whose
units carry the deterministic normalization of each cue's text; unit→source-cue lineage; inherited
timing (nothing computed); revision candidate lineage and source media/timeline; execution
provenance; atomic persistence; restart reconstruction; deterministic replay; idempotency (upstream
candidate byte-identical before and after composition); and that no downstream time-representation /
validation / review / final / artifact table is produced. The complete 942-test suite passes. A
Blueprint Drift Check confirmed no drift relative to any prior completed milestone, and migration
compatibility from every released version (v1..v12) to v13 is verified by an explicit
single-step-chain test that preserves existing data and meaning. Reading Representation owns no time
semantics; the durable unit model supports cue merge and split so downstream stages may merge or
split units; the in-memory `subtitle/` domain remains unchanged. This advances the Subtitle Pipeline
to stage 4.3 (Reading Representation); Time Representation and later subtitle/artifact stages remain
out of scope and unstarted.

## Subtitle Time Representation

- Goal: `docs/goals/LectureOS_Codex_Goal_Subtitle_Time_Representation.md`
- Status: **COMPLETE**
- Selected persistence: additive SQLite schema v14
- Completed slices: Goal Baseline and Assessment; Time Records; Deterministic Time Representation
  Service; Atomic SQLite Persistence, Restart, Replay and Migration Compatibility; Fake-Review /
  Fake-Transcript Acceptance
- Immediate next slice: Goal Complete

This milestone advances the Subtitle Pipeline to stage 4.4 (`docs/041_SUBTITLE_PIPELINE.md §4.4 Time
Representation`, §7): from a canonical `SubtitleReadingRevision` (v13) and its ordered reading units
it deterministically composes one **new immutable** subtitle time revision (`SubtitleTimeRevision`)
whose timed units (`SubtitleTimedUnit`) carry an **authoritative, Source-Timeline-anchored display
Time Range derived** from each unit's ordered source cues — the minimal enclosing source-timeline
extent for merged units, the cue range for one-to-one units, and an explicit `UNRESOLVED` state where
the basis is untimed or spans different timelines. `Product → Application → Capability Contract →
Provider` and the lifecycle position `… → Subtitle Reading Representation → Time Representation →
Subtitle Structural Validation → …` are preserved, while structural Validation, Review, Decision,
Final Subtitle, Artifact and export remain out of scope. The reading revision is the sole admission
authority; the source cues are read read-only as the Source-Timeline basis; timing composition
consumes no provider, produces a new immutable representation (never overwriting the reading
revision), preserves text/line composition and display order exactly, mutates no upstream record and
starts no downstream capability.

The bounded architectural assessment found no substantive blocker. A key architectural clarification
was recorded: §4.4 performs genuine deterministic representation work that §4.3 could not — merge and
split broke the naïve 1:1 correspondence with timed segments, so Time Representation re-establishes a
coherent per-unit Time Range by anchoring to the Source-Timeline basis (span aggregation for merged
units). **Source-Timeline anchoring is a canonical representation of provenance, not a timing
optimization strategy:** the baseline records the minimal enclosing extent of a unit's source cues;
later timing policies (padding, snapping, overlap resolution, gap insertion, duration adjustment,
redistribution) may **refine** the interval but never **redefine** this provenance-derived baseline,
and Structural Validation (§4.5) **evaluates** the represented timing rather than constructing it.
New Application-owned durable types `SubtitleTimeRevision` (identity `SubtitleTimeRevisionId`), ordered
child `SubtitleTimedUnit` (identity `SubtitleTimedUnitId`), and enum `SubtitleTimingStatus`
(`ANCHORED` | `UNRESOLVED`) are added; the in-memory `subtitle/` domain is untouched. A new
`SubtitleTimeRepresentationService` mirrors the established compose/persist split with an
Application-owned identity plan; additive SQLite schema v14 adds a `subtitle_time_revisions` parent
and an ordered `subtitle_timed_units` child (with a CHECK binding `timing_status` to range presence),
with atomic persistence, restart reconstruction and deterministic replay. No wall-clock is read. The
AGENTS.md Architect Checklist is entirely `No`: no existing Domain contract change, no released-schema
meaning change, no lifecycle authority change, no responsibility shift, no new identity semantics, one
additive migration, and no Blueprint contradiction. Migration compatibility from every released
version (v1..v13) to v14 is verified.

The Subtitle Time Representation Goal is complete. `SubtitleTimeRepresentationService.compose_
timing(...)` loads a canonical `SubtitleReadingRevision`, resolves each reading unit's source cues
read-only as the Source-Timeline basis, requires a running execution, and deterministically derives
one `SubtitleTimedUnit` per reading unit — ANCHORED to the minimal enclosing source-timeline extent
`[min(start), max(end)]` when every source cue is timed and shares one timeline (the cue range for
one-to-one units, the genuine span for merged units), otherwise UNRESOLVED with no range — preserving
display order and referencing exactly one reading unit, and carrying the full candidate lineage and
structural `validation_id`. `SQLiteSubtitleTimeCommandPersistence` writes the revision, its ordered
timed units and the co-persisted `DomainResultReference` (kind `subtitle_time_revision`, upstream =
the reading revision DomainResult) in one atomic v14 transaction, reconstructs the revision and
ordered timed units exactly after restart, and reproduces byte-identical records on deterministic
replay into a fresh database. An in-process fake-review / fake-transcript acceptance drives the full
pipeline and confirms the durable one-to-one anchoring (each timed unit ANCHORED to its cue range), a
durable merged-unit span (one reading unit over two source cues anchors the minimal enclosing span),
and the UNRESOLVED derivation for an untimed basis; timed-unit ordering and display order preserved;
each timed unit references its reading unit; revision candidate lineage and source media/timeline;
execution provenance; atomic persistence; restart reconstruction; deterministic replay; idempotency
(upstream reading row byte-identical before and after composition); and that no downstream validation
/ review / final / artifact table is produced. The complete 984-test suite passes. A Blueprint Drift
Check confirmed no drift relative to any prior completed milestone, and migration compatibility from
every released version (v1..v13) to v14 is verified by an explicit single-step-chain test that
preserves existing data and meaning. Time Representation owns timing representation only (anchoring =
provenance, optimization deferred, validation is §4.5); the in-memory `subtitle/` domain remains
unchanged. This advances the Subtitle Pipeline to stage 4.4 (Time Representation); Subtitle Structural
Validation and later subtitle/artifact stages remain out of scope and unstarted.

## Subtitle Structural Validation

- Goal: `docs/goals/LectureOS_Codex_Goal_Subtitle_Structural_Validation.md`
- Status: **COMPLETE**
- Selected persistence: additive SQLite schema v15
- Completed slices: Goal Baseline and Assessment; Validation Records; Deterministic Structural
  Validation Service; Atomic SQLite Persistence, Restart, Replay and Migration Compatibility;
  Fake-Review / Fake-Transcript Acceptance
- Immediate next slice: Goal Complete

This milestone advances the Subtitle Pipeline to stage 4.5 (`docs/041_SUBTITLE_PIPELINE.md §4.5
Structural Validation`, §9): from a canonical `SubtitleTimeRevision` (v14) and its ordered timed units
it deterministically **diagnoses** the subtitle revision's structural correctness and produces one
**immutable Validation Result** (`SubtitleValidation`) plus a collection of **immutable Findings**
(`SubtitleValidationFinding`) traceable to affected timed units. `Product → Application → Capability
Contract → Provider` and the lifecycle position `… → Subtitle Time Representation → Structural
Validation → Subtitle Review Preparation → Decision Application → Final Subtitle` are preserved, while
Review Preparation, Decision Application, Final Subtitle, Artifact and export remain out of scope. The
time revision is the sole admission authority; the reading revision is read read-only for provenance;
validation consumes no provider, produces a new immutable diagnosis (never modifying the time/reading/
candidate records), creates no Review Item, mutates no upstream record and starts no downstream
capability.

The bounded architectural assessment found no substantive blocker. Validation's canonical artifact is
an immutable Validation Result plus immutable, individually-addressable, traceable,
blocking-classified Findings with an independent append-only revisioned lifecycle (one-to-many
Validations per Time Revision) — not mere booleans, not repair, not review. It **diagnoses only**: it
records findings and a derived `structural_valid` verdict (= no blocking finding); it does not repair
data, create Review Items, adjudicate uncertainty, score/rank, approve, or gate. New Application-owned
durable types `SubtitleValidation` (identity `SubtitleValidationId`), ordered child
`SubtitleValidationFinding` (identity `SubtitleValidationFindingId`), and enum
`SubtitleValidationCategory` (PROVENANCE_INTEGRITY | TIMELINE_TRACEABILITY | UNRESOLVED_TIMING |
ORDERING | OVERLAP) are added; the in-memory `subtitle/` validation vocabulary is left unchanged and
informs but is not reused. Two additional Architect Decisions were recorded: finding identities are
deterministically derived from the caller-owned validation identity plus their ordinal (the finding
count is defect-dependent), preserving replay; and **each finding carries a stable `rule` identifier
independent of its human-readable `description`** — the rule identity that Review Preparation, Decision
Application, UI, analytics, filtering and future policy layers consume, stable across wording changes.
A new `SubtitleStructuralValidationService` mirrors the established validate/persist split with an
Application-owned identity plan; additive SQLite schema v15 adds a `subtitle_validations` parent and an
ordered `subtitle_validation_findings` child, with atomic persistence (including a
`structural_valid ⇔ no blocking finding` cross-check), restart reconstruction and deterministic replay.
No wall-clock is read. The AGENTS.md Architect Checklist is entirely `No`: no existing Domain contract
change, no released-schema meaning change, no lifecycle authority change (validation diagnoses; it does
not approve, gate, review, or decide), no responsibility shift, no new lifecycle-identity semantics,
one additive migration, and no Blueprint contradiction. Migration compatibility from every released
version (v1..v14) to v15 is verified.

The Subtitle Structural Validation Goal is complete. `SubtitleStructuralValidationService.validate_
timing(...)` loads a canonical `SubtitleTimeRevision`, resolves the reading revision read-only, requires
a running execution, and runs five deterministic threshold-free structural checks — provenance
integrity, timeline traceability, unresolved timing, ordering, and overlap — recording each detected
defect as an immutable finding carrying a stable rule identifier, coarse category, blocking severity,
explanatory description, and the affected timed unit, and deriving the summary booleans plus overall
`structural_valid` (= no blocking finding). `SQLiteSubtitleValidationCommandPersistence` writes the
validation, its ordered findings and the co-persisted `DomainResultReference` (kind
`subtitle_validation`, upstream = the time-revision DomainResult) in one atomic v15 transaction with a
structural_valid cross-check, reconstructs the validation and ordered findings exactly after restart,
and reproduces byte-identical records on deterministic replay into a fresh database. An in-process
fake-review / fake-transcript acceptance drives the full pipeline and confirms a clean time revision is
structurally valid with no findings, while durably persisted defective time revisions produce ORDERING,
OVERLAP and UNRESOLVED findings with `structural_valid=False` and stable rule identifiers independent of
their descriptions; validation mutates no upstream record and creates no Review Item; restart
reconstruction; deterministic replay; and no downstream review / final / artifact table is produced. The
complete 1023-test suite passes. A Blueprint Drift Check confirmed no drift relative to any prior
completed milestone, and migration compatibility from every released version (v1..v14) to v15 is
verified by an explicit single-step-chain test that preserves existing data and meaning. Validation
diagnoses only; all numeric quality thresholds, review handoff (§4.6), decisions (§4.7), and final
gating (§4.8) remain deferred. This advances the Subtitle Pipeline to stage 4.5 (Structural Validation);
Subtitle Review Preparation and later subtitle/artifact stages remain out of scope and unstarted.

## Subtitle Review Preparation

- Goal: `docs/goals/LectureOS_Codex_Goal_Subtitle_Review_Preparation.md`
- Status: **COMPLETE**
- Selected persistence: additive SQLite schema v16 (reusing the common Review tables)
- Completed slices: Goal Baseline and Assessment; Review Preparation Records; Deterministic Review
  Preparation Service; Atomic SQLite Persistence, Restart, Replay and Migration Compatibility;
  Fake-Review / Fake-Transcript Acceptance
- Immediate next slice: Goal Complete

This milestone advances the Subtitle Pipeline to stage 4.6 (`docs/041_SUBTITLE_PIPELINE.md §4.6 Subtitle
Review Preparation`, §10): from the supplied canonical `SubtitleValidation` revision (v15) and its
ordered findings, it deterministically **materializes canonical human-review work** — one **common
`ReviewItem`** (with its `CandidateReference` and a shared `ReviewContext`) per validation finding —
wrapped by a new immutable `SubtitleReviewPreparation` aggregate that traces each item to its source
finding and stable `rule`. `Product → Application → Capability Contract → Provider` and the lifecycle
position `… → Subtitle Structural Validation → Subtitle Review Preparation → Decision Application →
Final Subtitle` are preserved, while Decision Application, Final Subtitle, Artifact and export remain out
of scope. Review Preparation records **no** Review Decision, changes no upstream record, creates review
work in the **open** common lifecycle, and starts nothing downstream.

Admission boundary: Review Preparation **consumes the supplied validation revision**; whether it is the
latest, currently selected, superseded, or otherwise eligible is **outside this stage** — it neither
determines nor enforces currency, selection, or supersession, which belong to an upstream lifecycle
authority. The bounded architectural assessment found no substantive blocker. The repository already
owns a **durable common Review lifecycle** (`review/` — `ReviewItem`/`CandidateReference`/`ReviewContext`/
`ReviewDecision`/`DecisionKind`, persisted in the shared `review_items`/`review_candidate_references`/
`review_contexts` tables) and a direct precedent (`TranscriptReviewPreparation`, v6). §4.6 explicitly
delivers subtitle targets to the common Review activity, so Review Preparation **reuses the common
Review model** (creates common Review Items), plus a subtitle-specific `SubtitleReviewPreparation`
aggregate and child table linking each Review Item to its source finding + rule. There is **no new
status enum**: items are created OPEN (empty `decision_references`) in the existing common lifecycle;
allowed actions are the common `DecisionKind`. Finding→Review-Item cardinality is **1:1** (each finding
→ one item, finding order, no grouping); review necessity is a fixed deterministic baseline (every
finding is review work); a clean validation (0 findings) yields a **valid empty preparation** (so a
subtitle-specific aggregate is used, since `TranscriptReviewPreparation` requires ≥1 item, while the
common Review records are reused). Additive schema v16 adds a `subtitle_review_preparations` parent and
an ordered `subtitle_review_preparation_items` child, with atomic persistence (reusing the common review
insert helpers), restart reconstruction and deterministic replay. No wall-clock is read. The AGENTS.md
Architect Checklist is entirely `No`: no existing Domain contract change (the common `review/` contracts
and the in-memory subtitle domain are untouched — rows added, meaning unchanged), no released-schema
meaning change, no lifecycle authority change (Preparation creates open work and decides nothing), no
responsibility shift, no new identity semantics, one additive migration, and no Blueprint contradiction.
Migration compatibility from every released version (v1..v15) to v16 is verified.

The Subtitle Review Preparation Goal is complete. `SubtitleReviewPreparationService.prepare_review(...)`
consumes the supplied canonical `SubtitleValidation`, requires a running execution, and for each of its
ordered findings creates one common `CandidateReference` (kind `subtitle_validation_finding`) and one
OPEN common `ReviewItem` referencing a shared `ReviewContext`, recording a `SubtitleReviewItemLink` that
traces the item to its source finding identity + stable `rule` + target timed unit; a clean validation
yields a valid empty preparation. `SQLiteSubtitleReviewPreparationCommandPersistence` writes the common
candidate references + context + open review items (via the common insert helpers) together with the
preparation parent, its ordered item-link child, and the co-persisted `DomainResultReference` (kind
`subtitle_review_preparation`, upstream = the validation DomainResult) in one atomic v16 transaction,
reconstructs the preparation and ordered item links exactly after restart, and reproduces byte-identical
records on deterministic replay into a fresh database. An in-process fake-review / fake-transcript
acceptance drives the full pipeline and confirms a clean validation yields an empty preparation and a
defective validation yields exactly one OPEN Review Item per finding — each traced to its source finding
and rule — with the review items remaining OPEN after restart (no decision recorded); idempotency
(upstream validation byte-identical before and after preparation); restart reconstruction (preparation +
common review items); deterministic replay; and no downstream final / artifact table produced. The
complete 1061-test suite passes. A Blueprint Drift Check confirmed no drift relative to any prior
completed milestone, and migration compatibility from every released version (v1..v15) to v16 is verified
by an explicit single-step-chain test that preserves existing data and meaning. Review Preparation
creates open review work and decides nothing; the common `review/` contracts are unchanged; all grouping/
prioritization/eligibility/UI policy and all decision/final authority remain deferred (§4.7/§4.8). This
advances the Subtitle Pipeline to stage 4.6 (Review Preparation); Decision Application and later stages
remain out of scope and unstarted.

## Subtitle Human Review Decision

- Goal: `docs/goals/LectureOS_Codex_Goal_Subtitle_Human_Review_Decision.md`
- Status: **COMPLETE**
- Selected persistence: additive SQLite schema v17
- Completed slices: Goal Baseline and Assessment; Subtitle Human Review Decision Records; Deterministic
  Human Review Decision Service; Atomic SQLite Persistence, Restart, Replay and Migration Compatibility;
  Fake-Review / Fake-Transcript Acceptance
- Immediate next slice: Goal Complete

This milestone adds the durable **Subtitle Human Review Decision** stage — the prerequisite to
`docs/041_SUBTITLE_PIPELINE.md §4.7 Decision Application`. An architecture-first investigation confirmed
the repository had no durable, subtitle-consumable Review Decision: the common `ReviewDecision` is
recorded only in-memory, and the sole durable recorder (`TranscriptReviewDecision` / the
`transcript_review_decisions` table) is transcript-coupled and rejects `subtitle_validation_finding`
candidate references. `SubtitleReviewDecisionService.prepare_decision(...)` records a Human reviewer's
Accept/Reject/Modify against **exactly one** common `ReviewItem` produced by Subtitle Review Preparation,
as an immutable durable `SubtitleReviewDecision` aggregate. The lifecycle is the four-stage form `…
Structural Validation → Review Preparation → **Human Review Decision (recording)** → Decision Application
(§4.7) → Final Subtitle`; this stage exercises Human Authority only — it never applies the decision,
produces no Subtitle revision, no Final Subtitle, no applicability/selection, and no automatic approval.

Admission boundary: the canonical admission authority is the **supplied common `ReviewItem`**. Human
Authority is exercised against exactly one Review Item; the `SubtitleReviewPreparation` is only the
immutable container/ordering/provenance boundary — loaded to validate that the Review Item belongs to
it and to carry subtitle provenance (source validation / time revision / finding / stable rule), never
operated on as the target and never mutated. The bounded architectural assessment found no substantive
blocker. The milestone **mirrors the transcript v7 precedent** (`TranscriptReviewDecision`) but is
**subtitle-scoped** — it admits Review Items whose candidate reference kind is `subtitle_validation_finding`
and validates a `subtitle_time_revision:` provenance string; it reuses the common Review vocabulary
(`ReviewItem`, `CandidateReference`, `DecisionKind`, `HumanActorReference`) but does **not** reuse the
transcript-coupled aggregate. The decision timestamp is a caller-supplied, timezone-aware command input,
so reconstruction and replay are deterministic (no wall-clock is read). Additive schema v17 adds one flat
`subtitle_review_decisions` table (with the Modify⇔modified_text and sequence/previous CHECKs mirroring
the transcript decision table), with atomic persistence, restart reconstruction and deterministic replay.
The AGENTS.md Architect Checklist is entirely `No`: no existing Domain contract change (the common
`review/` contracts, the transcript-coupled `TranscriptReviewDecision`, and the in-memory subtitle domain
are untouched), no released-schema meaning change, no lifecycle authority change (Human Authority records
the decision; nothing is applied), no responsibility shift, no new identity semantics, one additive
migration, and no Blueprint contradiction. Migration compatibility from every released version (v1..v16)
to v17 is verified.

The Subtitle Human Review Decision Goal is complete. `SubtitleReviewDecisionService.prepare_decision(...)`
admits a supplied common `ReviewItem`, loads its `SubtitleReviewPreparation` container to validate
membership and resolve the candidate reference (kind `subtitle_validation_finding`) plus its
`subtitle_time_revision:` provenance, requires a Human actor and a running execution, and records the
Accept/Reject/Modify as an immutable `SubtitleReviewDecision` carrying the review item + candidate
reference linkage, subtitle provenance (preparation / validation / time revision / source finding + stable
rule), a caller-supplied timezone-aware timestamp, append-only sequence/previous lineage, and (for Modify)
the required modified text. `SQLiteSubtitleReviewDecisionCommandPersistence` writes the decision and its
co-persisted `DomainResultReference` (kind `subtitle_review_decision`, upstream = the preparation
DomainResult) in one atomic v17 transaction, reconstructs the decision exactly after restart, and
reproduces byte-identical records on deterministic replay into a fresh database (the timestamp stored
verbatim via isoformat/fromisoformat). An in-process fake-review / fake-transcript acceptance drives the
full pipeline and confirms Accept, an append-only Modify (referencing the Accept), and Reject are recorded
with subtitle provenance and DomainResult chaining, each traced to its review item's source finding + rule;
recording mutates no upstream preparation or review item and applies nothing — the review items remain OPEN
(no automatic approval); restart reconstruction; deterministic replay; and no downstream final / artifact
table is produced. The complete 1104-test suite passes. A Blueprint Drift Check confirmed no drift relative
to any prior completed milestone, and migration compatibility from every released version (v1..v16) to v17
is verified by an explicit single-step-chain test that preserves existing data and meaning. This stage
records Human judgement only; Decision Application (§4.7) — applying the decision, producing a Modify-
reflecting Subtitle revision — and Final Subtitle (§4.8) remain out of scope and unstarted, and are the
next dependency-ordered milestones.

## Subtitle Decision Application

- Goal: `docs/goals/LectureOS_Codex_Goal_Subtitle_Decision_Application.md`
- Status: **COMPLETE**
- Selected persistence: additive SQLite schema v18
- Completed slices: Goal Baseline and Assessment; Subtitle Decision Application Records; Deterministic
  Decision Application Service; Atomic SQLite Persistence, Restart, Replay and Migration Compatibility;
  Fake-Review / Fake-Transcript Acceptance
- Immediate next slice: Goal Complete

This milestone advances the Subtitle Pipeline to stage 4.7 (`docs/041_SUBTITLE_PIPELINE.md §4.7 Decision
Application`): from exactly one canonical `SubtitleReviewDecision` (v17), it deterministically **applies**
the recorded Human Accept/Reject/Modify and produces the **next Subtitle revision** — a new immutable
`SubtitleDecisionRevision` reflecting the applied outcome (and, for Modify, the user's modified text) —
together with its provenance. `Product → Application → Capability Contract → Provider` and the lifecycle
position `… → Subtitle Review Preparation → Subtitle Human Review Decision → Subtitle Decision Application
→ Final Subtitle` are preserved, while Final Subtitle (§4.8), current selection, readiness, and
applicability remain out of scope. Application is a **pure deterministic transformation**: the consumed
decision remains immutable, and **no existing canonical artifact is modified** — the `SubtitleReviewDecision`,
its `ReviewItem`, its `SubtitleReviewPreparation`, and the `SubtitleValidation` are never mutated. The only
newly created canonical artifact is the `SubtitleDecisionRevision` and its `DomainResultReference`.

The bounded architectural assessment found no substantive blocker. The `SubtitleReviewDecision` (v17) is
the sole admission authority; the `SubtitleValidation` (v15) and its finding are read **read-only** to
resolve the full source lineage and the target timed unit. A new Application-owned aggregate
`SubtitleDecisionRevision` (identity `SubtitleDecisionRevisionId`) and enum `SubtitleAppliedOutcome`
(`ACCEPTED` | `REJECTED` | `MODIFIED`, a pure deterministic function of `DecisionKind`) are added, with
names distinct from the **legacy in-memory** `application/subtitle_decision.py`, which is untouched. It
reuses the common Review vocabulary (`DecisionKind`, `ReviewItemId`, `CandidateReferenceId`). No wall-clock
is read, so reconstruction and replay are deterministic. Additive SQLite schema v18 adds one flat
`subtitle_decision_revisions` table (with the kind⇔outcome and MODIFIED⇔applied_text and sequence/previous
CHECKs), with atomic persistence, restart reconstruction and deterministic replay. The AGENTS.md Architect
Checklist is entirely `No`: no existing Domain contract change, no released-schema meaning change, no
lifecycle authority change (only recorded decisions are applied), no responsibility shift, no new identity
semantics, one additive migration, and no Blueprint contradiction. Migration compatibility from every
released version (v1..v17) to v18 is verified.

The Subtitle Decision Application Goal is complete. `SubtitleDecisionRevisionService.apply_decision(...)`
admits one canonical `SubtitleReviewDecision`, requires a running execution, reads the validation and its
finding read-only for lineage and the target timed unit, derives the applied outcome (Accept→ACCEPTED,
Reject→REJECTED, Modify→MODIFIED), carries the modified text for Modify, and builds the next
`SubtitleDecisionRevision` carrying the review item / candidate reference / preparation / validation / time
& reading revision / candidate / finding + stable rule / target timed unit / transcript & revision / media
& timeline lineage and append-only sequence/previous linkage.
`SQLiteSubtitleDecisionRevisionCommandPersistence` writes the revision and its co-persisted
`DomainResultReference` (kind `subtitle_decision_revision`, upstream = the review decision DomainResult) in
one atomic v18 transaction, reconstructs the revision exactly after restart, and reproduces byte-identical
records on deterministic replay into a fresh database. An in-process fake-review / fake-transcript
acceptance drives the full pipeline and applies the recorded Accept, Modify and Reject decisions,
confirming each next revision's outcome (ACCEPTED/REJECTED/MODIFIED), the Modify applied text, subtitle
provenance and DomainResult chaining, and finding/rule traceability; that application mutates no existing
canonical artifact (decision / review item / preparation / validation byte-identical before and after);
restart reconstruction; deterministic replay; and no downstream final / artifact table is produced. The
complete 1140-test suite passes. A Blueprint Drift Check confirmed no drift relative to any prior completed
milestone, and migration compatibility from every released version (v1..v17) to v18 is verified by an
explicit single-step-chain test that preserves existing data and meaning. This stage applies one recorded
decision into the next revision only; Final Subtitle selection (§4.8), current selection, readiness, and
applicability derivation remain out of scope and unstarted — §4.8 Final Subtitle is the next
dependency-ordered milestone.

## Subtitle Final Subtitle

- Goal: `docs/goals/LectureOS_Codex_Goal_Subtitle_Final_Subtitle.md`
- Status: **COMPLETE**
- Selected persistence: additive SQLite schema v19
- Completed slices: Goal Baseline and Assessment; Final Subtitle Records; Deterministic Final Subtitle
  Service; Atomic SQLite Persistence, Restart, Replay and Migration Compatibility; Fake-Review /
  Fake-Transcript Acceptance
- Immediate next slice: Goal Complete

This milestone advances the Subtitle Pipeline to its final stage 4.8 (`docs/041_SUBTITLE_PIPELINE.md §4.8
Final Subtitle`): from exactly one canonical `SubtitleDecisionRevision` (v18), it deterministically
**selects** the authoritative, approved-state Subtitle representation — the Final Subtitle — reflecting the
applicable Review Decision, and preserves provenance to the Corrected Transcript, Source Timeline, subtitle
revision and user decision. `Product → Application → Capability Contract → Provider` and the lifecycle
position `… → Subtitle Human Review Decision → Subtitle Decision Application → Subtitle Final Subtitle` are
preserved. Final Subtitle is a **deterministic selection** stage, not a transformation: the consumed
decision revision remains immutable and **no existing canonical artifact is modified** — the
`SubtitleDecisionRevision`, `SubtitleReviewDecision`, `ReviewItem`, `SubtitleReviewPreparation` and
`SubtitleValidation` are never mutated. The only newly created canonical artifact is the
`SubtitleFinalSubtitle` and its `DomainResultReference`; per §4.8 it is a finalization/selection record and
**not a separate approved-Subtitle content entity**. The FINAL outcome is the logical "Artifact Generation
Ready State" — a status, not an artifact.

The bounded architectural assessment found no substantive blocker. The `SubtitleDecisionRevision` (v18) is
the sole admission authority; because it already carries the full lineage Final needs, Final admits only the
decision revision and reads nothing else. A new Application-owned aggregate `SubtitleFinalSubtitle` (identity
`SubtitleFinalSubtitleId`) and enum `SubtitleFinalOutcome` (`FINAL` | `NOT_FINAL`, a pure deterministic
function of the applied outcome: `ACCEPTED → FINAL`, `MODIFIED → FINAL`, `REJECTED → NOT_FINAL`) are added,
with names distinct from the **legacy in-memory** `subtitle/` domain (`FinalSubtitleSelectionId`,
`final_selection.py`), which is untouched. No wall-clock is read, so reconstruction and replay are
deterministic. Additive SQLite schema v19 adds one flat `subtitle_final_subtitles` table (with the
decision_kind⇔applied_outcome, applied_outcome⇔final_outcome, MODIFIED⇔applied_text and sequence/previous
CHECKs), with atomic persistence, restart reconstruction and deterministic replay. The AGENTS.md Architect
Checklist is entirely `No`: no existing Domain contract change, no released-schema meaning change, no
lifecycle authority change (an approved representation is only selected, never constructed), no
responsibility shift, no new identity semantics, one additive migration, and no Blueprint contradiction.
Migration compatibility from every released version (v1..v18) to v19 is verified.

The Subtitle Final Subtitle Goal is complete. `SubtitleFinalSubtitleService.select_final(...)` admits one
canonical `SubtitleDecisionRevision`, requires a running execution, derives the Final outcome
(Accept/Modify → FINAL, Reject → NOT_FINAL), carries the modified text for Modify, and builds the
`SubtitleFinalSubtitle` carrying the decision revision / review decision / review item / candidate reference
/ preparation / validation / time & reading revision / candidate / finding + stable rule / target timed unit
/ transcript & revision / media & timeline lineage and append-only sequence/previous linkage.
`SQLiteSubtitleFinalSubtitleCommandPersistence` writes the Final Subtitle and its co-persisted
`DomainResultReference` (kind `subtitle_final_subtitle`, upstream = the decision revision DomainResult) in
one atomic v19 transaction, reconstructs it exactly after restart, and reproduces byte-identical records on
deterministic replay into a fresh database. An in-process fake-review / fake-transcript acceptance drives
the full pipeline and selects the Final Subtitle from the applied Accept, Modify and Reject revisions,
confirming each Final outcome (FINAL/FINAL/NOT_FINAL), the Modify applied text, subtitle provenance and
DomainResult chaining, and finding/rule/decision traceability; that selection mutates no existing canonical
artifact (decision revision / review decision / validation / preparation / review item byte-identical before
and after); restart reconstruction; deterministic replay; and no downstream export / artifact table is
produced. One independent bounded review of the atomic-persistence slice returned PASS with no critical
findings. The complete 1176-test suite passes. A Blueprint Drift Check confirmed no drift relative to any
prior completed milestone, and migration compatibility from every released version (v1..v18) to v19 is
verified by an explicit single-step-chain test that preserves existing data and meaning. With this stage the
**041 Subtitle Pipeline (§4.2–§4.8) is fully implemented**; downstream Artifact Generation / Export
(`044` Export Pipeline) — external subtitle files, export, playback rendering — is a separate pipeline and
remains out of scope.

## Approved Subtitle Assembly (044 Export Pipeline — stage 1)

- Goal: `docs/goals/LectureOS_Codex_Goal_Approved_Subtitle_Assembly.md`
- Blueprint: approved `patches/PATCH-0006` (Approved Subtitle Assembly — Export Pipeline Input Contract)
- Status: **COMPLETE**
- Selected persistence: additive SQLite schema v20 (three tables)
- Completed slices: Goal Baseline and Assessment; Approved Subtitle Assembly Records; Deterministic
  Assembly Service; Atomic SQLite Persistence, Restart, Replay and Migration Compatibility; End-to-End
  Acceptance (co-committed with the persistence slice)
- Immediate next slice: Goal Complete

This milestone opens the **044 Export Pipeline** with its first stage, **Approved Subtitle Assembly**,
implementing approved PATCH-0006. From exactly one canonical subtitle document (its `SubtitleTimeRevision`
(v14) + `SubtitleReadingRevision` (v13)), it deterministically **reconstructs the complete, ordered,
approved subtitle representation** — the `SubtitleApprovedDocument` — by reconciling the base
timed/reading representation with the applicable finalized decisions (`SubtitleFinalSubtitle` (v19),
reaching `SubtitleDecisionRevision` (v18) through provenance), and it establishes export eligibility. This
is the canonical **Export Input**. `Product → Application → Capability Contract → Provider` and the
lifecycle position `… → Subtitle Final Subtitle → Approved Subtitle Assembly → Artifact Generation` are
preserved; **041 remains immutable**. This stage generates **no artifact**, writes **no file**, serializes
**no format** (no SRT/WebVTT/bytes), and performs no Review, Validation, Human Decision, AI, or provider
work — every upstream record is read read-only. The only newly created canonical artifact is the
`SubtitleApprovedDocument` (with its ordered approved units and approved lines) and its
`DomainResultReference`; per PATCH-0006 it is a finalization/selection reconstruction, not a separate
approved-Subtitle content entity beyond the document representation.

The canonical reconciliation (approved PATCH-0006 §4, ruled for this milestone) applies each unit's current
finalization: **Modify (FINAL) → included with the approved `applied_text`; Accept (FINAL) → included with
the original reading text; Reject (NOT_FINAL) → omitted while the document stays eligible; Untouched →
included with the original reading text.** Unit order comes solely from the timed units' `display_order`.
Export **eligibility** is document completeness: a document is `ELIGIBLE` unless it cannot be completely
reconstructed (an included unit lacks `ANCHORED` timing or resolvable reading text, or a collected
finalization's provenance does not resolve to the document), in which case it is `INELIGIBLE` with a reason
and carries **no** units — never a silent partial document. Zero-finding documents are eligible directly
(all units Untouched). The reconciliation/eligibility fork on Reject vs NOT_FINAL was raised as a
contradiction between the milestone prompt and PATCH-0006 §4 and resolved by explicit ruling (a finalized
Reject omits its unit and the document stays eligible) before implementation.

A new Application-owned aggregate pair `SubtitleApprovedDocument` (identity `SubtitleApprovedDocumentId`) +
`SubtitleApprovedUnit` (identity `SubtitleApprovedUnitId`), with enums `SubtitleExportEligibility`
(`ELIGIBLE`/`INELIGIBLE`) and `SubtitleApprovedUnitOrigin` (`ACCEPTED`/`MODIFIED`/`UNTOUCHED`), is added. No
wall-clock is read, so reconstruction and replay are deterministic. Additive SQLite schema v20 adds three
tables (`subtitle_approved_documents` parent, `subtitle_approved_units` ordered children with FK ON DELETE
CASCADE, `subtitle_approved_unit_lines` grandchildren) with atomic persistence, restart reconstruction and
deterministic replay; a read-only `list_for_time_revision` query is added to the v19 final-subtitle
repository (no v19 schema change). The AGENTS.md Architect Checklist is entirely `No`: no existing Domain
contract change, no released-schema meaning change, no lifecycle authority change (established authority is
only consumed), no responsibility shift, no new identity semantics beyond the additive aggregate, one
additive migration, and no Blueprint contradiction. Migration compatibility from every released version
(v1..v19) to v20 is verified.

`SubtitleApprovedSubtitleAssemblyService.assemble(...)` admits one time revision + reading revision,
requires a running execution, collects the document's finalized decisions, keeps the current finalization
per unit, reconciles per the table above, resolves eligibility, and builds the ordered
`SubtitleApprovedDocument`. `SQLiteSubtitleApprovedDocumentCommandPersistence` writes the document, its
ordered units and their lines together with the co-persisted `DomainResultReference` (kind
`subtitle_approved_document`, upstream = the time-revision DomainResult) in one atomic v20 transaction,
reconstructs them exactly after restart, and reproduces byte-identical records on deterministic replay. An
in-process fake-review / fake-transcript acceptance drives the durable pipeline and assembles three
documents — a modify+reject document (one modified unit included, one omitted), an accept+untouched document
(both units included with original text), and an unresolved-timing document (INELIGIBLE, no units) —
confirming reconciliation, ordering, provenance and DomainResult chaining, that assembly mutates no existing
canonical artifact (time revision / reading revision / finals / decision revisions byte-identical before and
after), restart reconstruction, deterministic replay, and that no downstream artifact/export table is
produced. One independent bounded review of the atomic-persistence slice returned PASS with no critical
findings. The complete 1224-test suite passes. A Blueprint Drift Check confirmed no drift relative to any
prior completed milestone, and migration compatibility from every released version (v1..v19) to v20 is
verified by an explicit single-step-chain test that preserves existing data and meaning. Downstream
**Artifact Generation** (SRT/WebVTT serialization, export payloads), **Physical Materialization** (files,
storage), and **Delivery** remain later, separately-gated `044` milestones and are out of scope.

## SRT Artifact Generation (044 Export Pipeline — stage 2)

- Goal: `docs/goals/LectureOS_Codex_Goal_Srt_Artifact_Generation.md`
- Status: **COMPLETE**
- Selected persistence: additive SQLite schema v21 (one table, inline payload)
- Completed slices: Goal Baseline and Assessment; Durable Artifact and SRT Payload Records; Deterministic
  SRT Artifact Generation Service; Atomic SQLite Persistence, Restart, Replay and Migration Compatibility;
  End-to-End Acceptance (co-committed with the persistence slice)
- Immediate next slice: Goal Complete

This milestone adds the **second stage of the 044 Export Pipeline**, **SRT Artifact Generation**. From
exactly one eligible `SubtitleApprovedDocument` (v20), it deterministically serializes the ordered approved
units into a canonical **SRT payload** and creates one canonical, regenerable **Artifact Record**
(`SubtitleSrtArtifact`, identity = the common `ArtifactId`) with complete provenance. `Product →
Application → Capability Contract → Provider` and the lifecycle position `… → Approved Subtitle Assembly →
SubtitleApprovedDocument → SRT Artifact Generation → Physical Materialization → Delivery` are preserved;
**041 and v20 remain immutable**. The stage **writes no file** and touches no filesystem/path/URL/storage/
delivery; it performs no Review/Validation/assembly/AI/provider work and reads all approved meaning,
ordering, timing, omission and modified text from the Approved Subtitle Document **as-is** (read-only).

Generation admits one document, **rejects `INELIGIBLE` input** with a deterministic
`SubtitleArtifactGenerationError` and no record/payload (never a partial artifact), and serializes only the
document's included units. The canonical SRT rules: cue order = the document unit order; contiguous 1-based
numbering; timestamps derived solely from approved unit timing with the released `Decimal`/`ROUND_HALF_UP`
rounding and `HH:MM:SS,mmm` syntax; cue text = the approved lines verbatim, joined by LF; one blank line
between blocks; UTF-8; a non-empty payload ends with a single trailing LF; an **eligible zero-unit document**
(permitted by the v20 contract when all units were rejected) serializes to the **empty payload** (`""`,
byte length 0, cue count 0); a unit whose duration collapses at millisecond precision is an explicit
representation failure, never silently emitted. The deterministic timestamp primitives were **extracted**
into a pure `application/srt_payload.py` module (single-sourcing the algorithm) and the legacy in-memory SRT
formatter now delegates to it with byte-identical behavior.

A new Application-owned aggregate `SubtitleSrtArtifact` + enum `SubtitleArtifactFormat` (`SRT`, the canonical
format identifier — never a filename/extension/path/URL) is added; the record stores its deterministic SRT
payload **inline** so it is durably recoverable after restart, with byte length, cue count, encoding
(`utf-8`), source document, source media/timeline, execution provenance, and append-only
`sequence`/`previous_artifact_id`. It carries **no** materialization or delivery status and no path/URL/
storage field. No wall-clock/locale/randomness is used, so reconstruction and replay are deterministic.
Additive SQLite schema v21 adds one table `subtitle_srt_artifacts` with atomic persistence, restart
reconstruction and deterministic replay. The AGENTS.md Architect Checklist is entirely `No`: no existing
Domain contract change, no released-schema meaning change, no lifecycle authority change (assembly authority
is only consumed), no responsibility shift, no new identity semantics (the common `ArtifactId` is reused),
one additive migration, and no Blueprint contradiction. Migration compatibility from every released version
(v1..v20) to v21 is verified.

`SubtitleSrtArtifactGenerationService.generate_artifact(...)` admits one approved document, requires a
running execution, rejects ineligible input, serializes the included units and builds the
`SubtitleSrtArtifact`. `SQLiteSubtitleSrtArtifactCommandPersistence` writes the artifact (with its inline
payload) and its co-persisted `DomainResultReference` (kind `subtitle_srt_artifact`, upstream = the approved
document DomainResult) in one atomic v21 transaction, reconstructs it exactly after restart with a
byte-identical payload, and reproduces byte-identical records on deterministic replay. An in-process
fake-review / fake-transcript acceptance drives the durable pipeline through Approved Subtitle Assembly and
generates an SRT Artifact from an eligible document, confirming the **exact serialized SRT payload** and its
metadata, that an ineligible document produces no artifact, provenance and DomainResult chaining, that
generation mutates no existing canonical artifact, restart reconstruction (payload byte-equal), deterministic
replay, and that no physical-file / materialization / delivery table is produced. One independent bounded
review of the atomic-persistence slice returned PASS with no critical findings. The complete 1260-test suite
passes. A Blueprint Drift Check confirmed no drift relative to any prior completed milestone, and migration
compatibility from every released version (v1..v20) to v21 is verified by an explicit single-step-chain test
that preserves existing data and meaning. Downstream **Physical Materialization** (writing bytes to a file/
storage, paths/filenames, atomic rename, directory policy) and **Delivery** (download/upload/transfer, URLs,
UI) remain later, separately-gated `044` milestones and are out of scope; the legacy atomic local file
writer is deferred to Physical Materialization.

## SRT Physical Materialization (044 Export Pipeline — stage 3)

- Goal: `docs/goals/LectureOS_Codex_Goal_Srt_Physical_Materialization.md`
- Blueprint: approved `docs/044_EXPORT_PIPELINE.md §17` / `patches/PATCH-0007`
- Status: **COMPLETE**
- Selected persistence: additive SQLite schema v22 (two insert-only tables)
- Completed slices: Goal Baseline and Assessment; Materialization Records; Storage Location Policy and
  Infrastructure Local-File Writer; Atomic SQLite Persistence (v22) and Migration Compatibility;
  Record-First Materialization Service, Reconciliation and Composition; End-to-End Acceptance, Recovery
  and Replay
- Immediate next slice: Goal Complete

This milestone adds the **third stage of the 044 Export Pipeline**, **SRT Physical Materialization**,
implementing the approved Blueprint contract §17 (`PATCH-0007`). From exactly one canonical
`SubtitleSrtArtifact` (v21) and one Materialization Request, it durably realizes the artifact's inline SRT
payload as a **physical file** under an approved Storage Root, following the **record-first, crash-consistent,
reconcilable** model: the act is established **PENDING** durably (intent + `DomainResultReference`) before any
file is written, the file is written atomically (temp file → fsync → atomic link), and the terminal
`MATERIALIZED | FAILED` outcome is recorded afterwards. `Product → Application → Capability Contract →
Provider` and the lifecycle position `… → SRT Artifact Generation → SubtitleSrtArtifact → SRT Physical
Materialization → Materialization Record + Physical File → Delivery` are preserved; **041, v20 and v21 remain
immutable**. The stage never regenerates SRT, never re-evaluates eligibility, and keeps **Artifact identity
permanently independent of any physical file**; the Storage Location is operational provenance, never
identity. **Delivery remains out of scope.**

The materialization act is modelled as two **immutable, insert-only** records (§17.3 leaves record structure
to implementation): a `SubtitleSrtMaterialization` (intent, committed first) and a
`SubtitleSrtMaterializationOutcome` (terminal); Materialization State is **derived** (no outcome ⇒ PENDING).
The **Storage Authority** is one approved Storage Root supplied by the Composition Root; **Application** owns
the deterministic relative-location and filename policy (`.srt`), and an **Infrastructure**
`LocalSrtFileWriter` (a new `infrastructure/` package) owns byte-writing behind an Application
`MaterializedFileWriter` port, reusing the hardened writer's mechanics (approved-root containment,
path-traversal and symlink-escape rejection, exact byte preservation, no-overwrite-of-different-bytes,
identical-bytes idempotency, orphan-tempfile cleanup) — not weakened. **Collision**: identical bytes →
idempotent MATERIALIZED; different bytes or a foreign object → FAILED, never overwritten; write/containment
failure → FAILED (explicit, never a silent success). **Idempotency**: a duplicate Materialization Identity
returns the existing record; a dangling PENDING is completed, not duplicated. **Rematerialization** is a new
record with a new identity, prior records preserved. **Reconciliation** of a dangling PENDING is
deterministic (matching file → MATERIALIZED, different → FAILED, absent → write then MATERIALIZED) and does
not require the original execution to be running. A missing file loses only availability — the Materialization
and Artifact records and their provenance remain canonical. **No cross-resource atomicity is claimed.**

Additive SQLite schema v22 adds `subtitle_srt_materializations` and `subtitle_srt_materialization_outcomes`
(insert-only, FK CASCADE), with the intent co-persisted with its `DomainResultReference` (kind
`subtitle_srt_materialization`, upstream = the artifact's DomainResult) in one atomic transaction and the
outcome in a separate atomic transaction after the file write. The AGENTS.md Architect Checklist is entirely
`No`: no existing Domain contract change, no released-schema meaning change, no lifecycle authority change
(established artifact authority is only consumed), no responsibility shift, no new identity semantics beyond
the additive materialization identity (distinct from `ArtifactId`), one additive migration, and no Blueprint
contradiction. Migration compatibility from every released version (v1..v21) to v22 is verified. No
path/URL/absolute-path or materialization/delivery status column is added to any existing table, and
`SubtitleSrtArtifact` is unchanged.

`SubtitleSrtMaterializationService.record_materialization(...)` admits one artifact, requires a running
execution for a new act, persists the PENDING intent record-first, writes the file, and records the terminal
outcome; `reconcile_materialization(...)` completes a dangling PENDING deterministically. The Infrastructure
`LocalSrtFileWriter` writes beneath the composed approved root only. Three independent bounded reviews (the
filesystem/security writer slice, the schema/migration/transaction persistence slice, and the
service/consistency/recovery slice) each returned PASS with no critical findings. An in-process fake-review /
fake-transcript acceptance drives the durable pipeline through Artifact Generation and materializes the
artifact to a **real file** under a temporary approved root, confirming the exact realized bytes, the
PENDING→MATERIALIZED records, provenance and DomainResult chaining, that no existing canonical artifact is
mutated (and the Artifact carries no materialization status), rematerialization with a new identity,
idempotency, different-bytes → FAILED with no overwrite, crash reconciliation of a durable PENDING with no
file, restart reconstruction, deterministic replay, and that no Delivery/URL table is produced. The complete
1319-test suite passes. A Blueprint Drift Check confirmed no drift relative to any prior completed milestone.
**Delivery** (download/upload/transfer, URLs/signed URLs, presentation filenames, UI), **cloud/object
storage**, deletion/retention/GC, and additional export formats remain later, separately-gated milestones and
are out of scope.

## Lecture Analysis Input Eligibility (042 Lecture Intelligence Pipeline — Milestone 1)

- Blueprint: approved `docs/042_LECTURE_INTELLIGENCE_PIPELINE.md §5.1` / `patches/PATCH-0009`
- Status: **COMPLETE**
- Selected persistence: additive SQLite schema v23 (one insert-only table)
- Commit: `feat: admit lecture analysis input eligibility`
- Immediate next milestone: Lecture Analysis / Analysis Finding (042 Milestone 2) — product-gated, deferred

This milestone opens the **042 Lecture Intelligence Pipeline** (the Edit Pipeline's analysis layer) with its
first stage, **Lecture Analysis Input Eligibility (Intake)**, implementing approved `042 §5.1` (PATCH-0009).
From the validated Corrected Transcript selected by the Transcript Pipeline — admitted **read-only** through
its canonical `TranscriptReadinessEvaluation` — it deterministically records one immutable, provenance-bearing
`EligibleAnalysisInput` (`ELIGIBLE` iff the readiness outcome is `READY`, else `NOT_ELIGIBLE`). Its sole
responsibility is establishing a validated, durable analysis basis; it performs **no analysis** and creates
**no** Analysis Finding, Lecture Segment, Segment Label, Edit Candidate, or Review Item, and performs **no AI
reasoning**. It reuses the established intake pattern (the Subtitle Transcript Intake stage): a deterministic
`ReadinessOutcome → LectureAnalysisEligibility` mapping, an immutable aggregate carrying full readiness /
selection / applicability / decision / review-item / candidate / transcript-revision lineage and source
media/timeline, execution-provenance and a `DomainResultReference` (kind `eligible_analysis_input`, upstream =
the readiness DomainResult), a `prepare/record` service split, and atomic v23 persistence. The AGENTS.md
Architect Checklist is entirely `No`: no existing Domain contract change, no released-schema meaning change,
no lifecycle authority change (established transcript authority is only consumed), no responsibility shift, a
new additive identity (`EligibleAnalysisInputId`), one additive migration, and no Blueprint contradiction;
041/v20/v21/v22 and the Transcript Pipeline records are unchanged. Migration compatibility from every released
version (v1..v22) to v23 is verified. An in-process fake-review / fake-transcript acceptance reuses the durable
Transcript Pipeline chain and records the analysis input for the ready and not-ready readiness evaluations,
confirming ELIGIBLE/NOT_ELIGIBLE, provenance and DomainResult chaining, that no upstream record is mutated,
restart reconstruction, deterministic replay, and that no analysis / Finding / Segment / Candidate table is
produced. The complete 1347-test suite passes. Later 042 milestones (Analysis Finding, Segmentation, Edit
Candidate, Review handoff) remain **product-gated** by the `042 §18` Requires-Validation items and are out of
scope.

## Analysis Finding Application Foundation (042 Lecture Intelligence Pipeline — Milestone 2)

- Blueprint: approved `docs/042_LECTURE_INTELLIGENCE_PIPELINE.md §8.1` / `patches/PATCH-0010`
- Status: **COMPLETE**
- Selected persistence: additive SQLite schema v24 (one insert-only table)
- Commit: `feat: establish analysis finding application foundation`
- Immediate next milestone: concrete Analysis Provider (042) — product-gated, deferred

This milestone establishes the **provider-independent Application foundation** for durable canonical
**Analysis Findings**, implementing approved `042 §8.1` (PATCH-0010). From an already-normalized,
provider-independent analysis result — admitted **read-only** against exactly one `ELIGIBLE`
`EligibleAnalysisInput` (`042 §5.1`, Milestone 1) — the `AnalysisFindingApplicationService` deterministically
records one or more immutable, provenance-bearing `AnalysisFinding` records. Each Finding is anchored to
exactly one `EligibleAnalysisInput`, carries a required, stable, Application-owned canonical **Finding Type**
(a canonical `^[a-z][a-z0-9_]*$` token — no fixed taxonomy and no closed enum, so a raw provider
classification can never be preserved as a canonical type), a required recorded **evidence** rationale with
provenance, an **optional** recorded confidence and/or uncertainty in `[0, 1]` (never computed, calibrated,
prioritized, or ranked here), and an **optional single** Source Timeline time range (no Lecture Segment
relationship; multi-range deferred). It performs **no analysis** and does **not** invoke AI, implement a
provider, define prompts or models, or create a Lecture Segment, Segment Label, Edit Candidate, or Review
Item. The admitted `NormalizedAnalysisResult` is an internal Application contract, never a provider API: it
carries no provider identifier, model, prompt, token usage, transport metadata, raw provider JSON, or internal
reasoning, so the canonical domain stays entirely provider-agnostic. Admission requires exactly one `ELIGIBLE`
`EligibleAnalysisInput`, a running unit execution, matching Source Timeline lineage, and an identity plan per
finding; all upstream objects are consumed read-only. It reuses the established durable-stage pattern:
caller-owned identities, a `prepare/record` service split, immutable frozen aggregates with `__post_init__`
invariants, per-finding `DomainResultReference` chaining (kind `analysis_finding`, upstream = the
`EligibleAnalysisInput` DomainResult), and one atomic v24 transaction persisting all Findings of an admission
and their Domain Results together (identity-absence checks, complete rollback on any collision, no partial
writes). No wall-clock is read, so reconstruction and replay are deterministic. The AGENTS.md Architect
Checklist is entirely `No`: no existing Domain contract change, no released-schema meaning change, no lifecycle
authority change (Milestone 1 eligibility is only consumed), no responsibility shift, a new additive identity
(`AnalysisFindingId`), one additive migration, and no Blueprint contradiction; 040/041/044 and the v1..v23
records are unchanged. Migration compatibility from every released version (v1..v23) to v24 is verified, and
unsupported downgrade/direct-skip migrations remain rejected. An in-process acceptance reuses the durable
Transcript Pipeline chain, records the `ELIGIBLE` analysis input, then admits a normalized analysis result and
records canonical Findings — confirming anchoring, provenance and DomainResult chaining, ordered sequences,
that no upstream record is mutated, restart reconstruction, deterministic replay, and that no Lecture Segment,
Segment Label, Edit Candidate, or Review table is produced. The complete 1397-test suite passes. The **concrete
AI Analysis Provider** (prompt design, model selection, provider retries, network calls), together with
Finding taxonomy, confidence calculation, uncertainty calibration, prioritization, revision, supersession,
multi-range Findings, Lecture Segmentation, Segment relationships, Edit Candidates, Review handoff, and
optional Subtitle/Speaker/Project Context admission, remain later, separately-gated milestones and are out of
scope.

## Lecture Segmentation Application Foundation (042 Lecture Intelligence Pipeline — Milestone 3)

- Blueprint: approved `docs/042_LECTURE_INTELLIGENCE_PIPELINE.md §7.1` / `patches/PATCH-0011`
- Status: **COMPLETE**
- Selected persistence: additive SQLite schema v25 (one insert-only table)
- Commit: `feat: establish lecture segmentation application foundation`
- Immediate next milestone: concrete segmentation provider / Segment Labels (042) — product-gated, deferred

This milestone establishes the **provider-independent Application foundation** for durable canonical
**Lecture Segments**, implementing approved `042 §7.1` (PATCH-0011). From an already-normalized,
provider-independent segmentation result — admitted **read-only** against exactly one `ELIGIBLE`
`EligibleAnalysisInput` (`042 §5.1`, Milestone 1) — the `LectureSegmentationApplicationService`
deterministically records one or more immutable, provenance-bearing `LectureSegment` records. Each Segment is
anchored to exactly one `EligibleAnalysisInput` (never a Finding; no Finding required), carries **exactly one
required, single** Source Timeline Time Range (`range_start`, `range_end`; finite, non-negative,
`start <= end`; whole-recording allowed), and inherits Source Media / Source Timeline provenance through the
anchoring input. It performs **no segmentation** and does **not** invoke AI, implement a provider, define
prompts or models, or create a Segment Label, Analysis Finding, Edit Candidate, or Review Item; it establishes
**no** Segment Label, confidence, uncertainty, or rationale semantics. The admitted `NormalizedSegmentationResult`
is an internal Application contract, never a provider API: it carries no provider identifier, model, prompt,
transport metadata, raw provider JSON, classification, or internal reasoning. Admission requires exactly one
`ELIGIBLE` `EligibleAnalysisInput`, a running unit execution, matching Source Timeline lineage, and an identity
plan per segment; all upstream objects are consumed read-only. It reuses the established durable-stage pattern:
caller-owned identities, a `prepare/record` service split, immutable frozen aggregates with `__post_init__`
invariants, per-segment `DomainResultReference` chaining (kind `lecture_segment`, upstream = the
`EligibleAnalysisInput` DomainResult), and one atomic v25 transaction persisting all Segments of an admission
and their Domain Results together (identity-absence checks, complete rollback on any collision, no partial
writes). No wall-clock is read, so reconstruction and replay are deterministic. The AGENTS.md Architect
Checklist is entirely `No`: no existing Domain contract change, no released-schema meaning change, no lifecycle
authority change (Milestone 1 eligibility is only consumed), no responsibility shift, a new additive identity
(`LectureSegmentId`), one additive migration, and no Blueprint contradiction; 040/041/044 and the v1..v24
records are unchanged. The §7.1 reprocessing contract is satisfied at the minimum by immutability plus
provenance (Segments are never mutated or deleted; supersession/revision/reconciliation remain deferred).
Migration compatibility from every released version (v1..v24) to v25 is verified, and unsupported
downgrade/direct-skip migrations remain rejected. An in-process acceptance reuses the durable Transcript
Pipeline chain, records the `ELIGIBLE` analysis input, then admits a normalized segmentation result and records
canonical Segments — confirming anchoring, provenance and DomainResult chaining, required single ranges, ordered
sequences, that no upstream record is mutated, restart reconstruction, deterministic replay, and that no Segment
Label, Analysis Finding row, Edit Candidate, or Review table is produced. The complete 1437-test suite passes.
Segment Labels and label taxonomy, multiple segmentation views / perspective groups / grouping aggregates,
confidence / uncertainty / rationale semantics (and their ownership), overlap / nesting / hierarchy / multi-range
and boundary-uncertainty representation, revision / supersession / reconciliation, and the concrete segmentation
provider remain later, separately-gated milestones and are out of scope.

## Edit Candidate Application Foundation (042 Lecture Intelligence Pipeline — Milestone 4)

- Blueprint: approved `docs/042_LECTURE_INTELLIGENCE_PIPELINE.md §9.1` / `patches/PATCH-0012`
- Status: **COMPLETE**
- Selected persistence: additive SQLite schema v26 (one insert-only table)
- Commit: `feat: establish edit candidate application foundation`
- Immediate next milestone: concrete Candidate Generation Provider / Review handoff (042/043) — product-gated, deferred

This milestone establishes the **provider-independent Application foundation** for durable canonical **Edit
Candidates**, implementing approved `042 §9.1` (PATCH-0012). From an already-normalized, provider-independent
Edit Candidate result — admitted **read-only** against exactly one canonical `AnalysisFinding` (`042 §8.1`,
Milestone 2) — the `EditCandidateApplicationService` deterministically records one or more immutable,
provenance-bearing `EditCandidate` records: optional, evaluative, advisory edit proposals derived from
analysis, prepared for later Review handoff. Each Candidate is anchored to **exactly one Analysis Finding**
(mandatory; **no Lecture Segment anchor or reference**, no second `EligibleAnalysisInput` anchor), carries
**exactly one required** Source Timeline Time Range (`range_start`, `range_end`; finite, non-negative,
`start <= end`; required even when the anchoring Finding has no range, and need not equal it), a required
**open Application-owned Candidate Type** key (`^[a-z][a-z0-9_]*$`, following the §8.1 Finding-Type canonical
key precedent — not a closed enum or taxonomy), and a required **rationale** (recorded, provider-independent,
human-reviewable, non-empty). Source Media and Source Timeline are inherited from the Finding. It performs
**no candidate generation** and does **not** invoke AI, implement a provider, define prompts/models, create a
Segment Label, Review CandidateReference, Review Item, or Approved Edit Decision, assign Review status, or
support Accept/Reject/Modify. The admitted `NormalizedCandidateResult` is an internal Application contract,
never a provider API: it carries no provider identifier, model, prompt, token usage, transport metadata, raw
provider JSON, classification, confidence, uncertainty, Review state, Segment reference, or executable
operation. Admission requires exactly one canonical Analysis Finding, a running unit execution, matching
Source Timeline lineage, and an identity plan per candidate; all upstream objects are consumed read-only.
Because a persisted Analysis Finding is the durable output of an ELIGIBLE Eligible Analysis Input (§8.1),
anchoring to a canonical Finding transitively guarantees ELIGIBLE provenance and no separate eligibility
check is re-run. It reuses the established durable-stage pattern: caller-owned identities, a `prepare/record`
service split, immutable frozen aggregates with `__post_init__` invariants, per-candidate
`DomainResultReference` chaining (kind `edit_candidate`, sole direct upstream = the `AnalysisFinding`
DomainResult), and one atomic v26 transaction persisting all Candidates of an admission and their Domain
Results together (identity-absence checks, complete rollback on any collision, no partial writes). No
wall-clock is read, so reconstruction and replay are deterministic. The AGENTS.md Architect Checklist is
entirely `No`: no existing Domain contract change, no released-schema meaning change, no lifecycle authority
change (Milestone 2 findings are only consumed), no responsibility shift, a new additive identity
(`EditCandidateId`), one additive migration, and no Blueprint contradiction; 040/041/044 and the v1..v25
records are unchanged. The §9.1 reprocessing contract is satisfied at the minimum by immutability plus
provenance (Candidates are never mutated or deleted; revision/supersession/stale-detection/reconciliation
remain deferred). Migration compatibility from every released version (v1..v25) to v26 is verified, and
unsupported downgrade/direct-skip migrations remain rejected. An in-process acceptance reuses the durable
Transcript Pipeline chain, records the ELIGIBLE analysis input and a canonical Analysis Finding (without its
own range), then admits a normalized Candidate result and records canonical Candidates — confirming anchoring,
provenance and DomainResult chaining directly to the Finding, required Type/rationale/range payload (including
a Candidate with a required range from a non-located Finding), ordered sequences, that no upstream record is
mutated, restart reconstruction, deterministic replay, and that no Segment Label / Review / Approved-Edit-
Decision table and no Lecture Segment row is produced. The complete 1483-test suite passes. Segment Label
linkage, multi-Finding / multi-Segment / many-to-many provenance, multi-range / discontinuous / non-timeline
Candidates, confidence / uncertainty / priority / severity / expected time savings / structured evidence /
source-replacement text / proposed treatment operations, Candidate revision / supersession / stale detection /
Review reconciliation / current-candidate selection, Review CandidateReferences / Review Items / Review status /
Accept-Reject-Modify / Approved Edit Decisions (043), and the concrete Candidate Generation Provider remain
later, separately-gated milestones and are out of scope.

## Concrete Edit Candidate Generation Provider — First Slice (042 Lecture Intelligence Pipeline)

- Blueprint: approved `docs/042_LECTURE_INTELLIGENCE_PIPELINE.md §9.2` / `patches/PATCH-0013`
- Status: **COMPLETE** (provider-integration complete; product-quality approval deferred)
- Selected persistence: none new — reuses the v26 Edit Candidate Application Foundation
- Commit: `feat: add concrete edit candidate generation provider first slice`
- Immediate next milestone: Review handoff (043) / provider enrichment — product-gated, deferred

This slice implements the **provider-generation layer** above the completed Edit Candidate Application
Foundation (§9.1), realizing approved `042 §9.2` (PATCH-0013). It adds a **provider-neutral
`EditCandidateGenerationPort`**, provider-neutral request/proposal/outcome models, an **Application/
generation-owned closed first-slice Candidate Type registry** (`non_lecture_region`,
`redundant_restatement`, `delivery_concern`), a **generation/orchestration service** that processes exactly
one canonical Analysis Finding per invocation and calls the existing admission service, one **concrete OpenAI
adapter** (`OpenAIEditCandidateGenerationAdapter`, injectable `transport`, strict Structured Outputs,
versioned adapter-owned prompt), and a **deterministic fake Port** for acceptance. Per invocation it loads
the Finding read-only, reconstructs bounded located corrected-transcript context (segments overlapping the
Finding range ± a fixed configuration window, no Lecture Segments, no identities transmitted), invokes the
provider once, and classifies the result into explicit outcomes: **ALL_VALID, NO_CANDIDATE, PARTIAL_SUCCESS,
PROVIDER_FAILURE, MALFORMED_OUTPUT, NORMALIZATION_FAILURE, ADMISSION_FAILURE**. A zero-proposal (or
no-usable-context) result invokes no admission and creates nothing, preserving §9.1's empty-batch rejection;
partial success admits valid proposals and surfaces rejected-proposal diagnostics (never silently dropped,
never persisted). Registry membership, non-empty rationale, and range containment within the supplied window
are enforced in the generation service (the adapter enforces only strict schema, so an unknown Type or
out-of-context range becomes a normalization diagnostic, not an adapter failure); the canonical Candidate
Type field remains an **open key** — the registry is a generation/admission constraint only. Caller-owned
identities are planned by an injected planner invoked **only when at least one valid Candidate will be
admitted**. Provider/model/prompt/config provenance stays outside the Candidate record; **no raw provider
response is persisted; no new schema, table, or persistence foundation is added** (`SQLITE_SCHEMA_VERSION`
stays 26). External egress is bounded to transcript excerpts + Finding Type/evidence + window timing (no
media bytes, file paths, or identities); provider training/data-use disabling and secret handling are the
adapter's responsibility and full redaction/retention/compliance policy remains deferred. Replay means
deterministic fake-Port pipeline replay + durable-record reconstruction; live invocation is not replay-safe.
The AGENTS.md Architect Checklist is entirely `No`: no Domain contract change, no released-schema meaning
change, no lifecycle authority change (Findings/transcripts consumed read-only), no responsibility shift, no
new identity or migration, and no Blueprint contradiction; §9.1 and the v1..v26 records are unchanged. An
in-process acceptance drives the full slice end to end against the fake Port (bounded context, partial
success, provenance to the Finding, no Review artifact, no provider metadata persisted, restart
reconstruction, deterministic replay). The complete 1522-test suite passes. Review handoff (043), Review
status/decisions, a second provider, provider fallback/selection, provider-result/raw-response persistence,
automatic repair, rich confidence/priority/enrichment, product-quality thresholds, and full privacy/retention/
compliance policy remain later, separately-gated milestones and are out of scope.

## Edit-Pipeline Review Application Foundation — First Slice (043 Review Pipeline)

- Blueprint: approved `docs/043_REVIEW_PIPELINE.md §7.4` / `patches/PATCH-0014`
- Status: **COMPLETE**
- Selected persistence: additive SQLite schema v27 (two insert-only tables)
- Commit: `feat: establish edit-pipeline review application foundation`
- Immediate next milestone: 044 Export of Approved Edit Decisions / later Review capabilities — product-gated, deferred

This milestone establishes the first **Edit-Pipeline Review Application Foundation**, implementing approved
`043 §7.4` (PATCH-0014). From one human judgment about exactly one existing durable `EditCandidate`
(`042 §9.1`), admitted **read-only**, the `EditReviewApplicationService` deterministically records one
immutable `EditReviewDecision` and — when the decision is `accept` or `modify` — exactly one immutable
`ApprovedEditDecision`; `reject` records only the durable decision. Decision kind is a **closed** vocabulary
`{accept, reject, modify}` (unknown values rejected, never coerced/aliased/lowercased/mapped), distinct from
and not altering the open Candidate Type contract of §9.1. **Accept** snapshots the Candidate's review-relevant
values; **Modify** carries a complete human-approved replacement (approved range, approved Candidate Type/label,
approved rationale) supplied as a normalized modification, while the Candidate stays immutable. The
`ApprovedEditDecision` is a self-contained approved snapshot suitable as future 044 input; it **owns** the
approved range/type/rationale + approving kind + denormalized media/timeline + execution provenance, and
**references** the source `EditReviewDecision` and `EditCandidate`. There is **no status field and no state
machine** (Alternative A): meaning is carried by decision kind + Approved-record existence. Provenance chains
`ApprovedEditDecision → EditReviewDecision → EditCandidate → AnalysisFinding → …` with single-direct-upstream
DomainResult chaining (`EditReviewDecision` upstream = the Candidate's DomainResult; `ApprovedEditDecision`
upstream = the ReviewDecision's DomainResult). Admission is **Application-owned**, running-execution-gated,
read-only toward upstream, caller-owned-identity, and **atomic**: Accept/Modify insert the decision + its
DomainResult + the approved record + its DomainResult in one transaction; Reject inserts the decision + its
DomainResult; any collision or error rolls back the whole admission (no orphan decision, approval, or
DomainResult). No wall-clock is read, so reconstruction and replay are deterministic. The AGENTS.md Architect
Checklist is entirely `No`: no existing Domain contract change, no released-schema meaning change, no lifecycle
authority change (Edit Candidates/lineage consumed read-only), no responsibility shift, two new additive
identities (`EditReviewDecisionId`, `ApprovedEditDecisionId`), one additive migration, and no Blueprint
contradiction; §9.1/§9.2, the Text-Pipeline Review, and the v1..v26 records are unchanged. Additive schema **v27**
adds two insert-only tables (`edit_review_decisions`, `approved_edit_decisions`) enforcing identity uniqueness,
the closed decision-kind CHECK, an approved-kind CHECK restricted to accept/modify, at-most-one Approved per
ReviewDecision (UNIQUE + FK), and range validity; migration compatibility from every released version (v1..v26)
to v27 is verified, and unsupported downgrade/direct-skip migrations remain rejected. An in-process acceptance
drives the full chain (Candidate → accept/modify/reject) and confirms Accept snapshot equality, Modify
replacement with an unchanged Candidate, Reject without an Approved record, provenance chaining, no status
column / no deferred Review-Session/History table, restart reconstruction, and deterministic replay. The
complete 1562-test suite passes. Review UI/API, Review Session/History persistence, multi-candidate Review
Items, multi-user conflict/authority policy, Candidate reconciliation, revision/supersession/withdrawal/stale/
current-selection, export formats, NLE integration, automatic edit application/rendering, provider-assisted
Review, and confidence/priority/severity/quality scores remain later, separately-gated milestones and are out
of scope.

## Edit-Pipeline Export Application Foundation — First Slice (044 §19 Export Pipeline)

- Blueprint: approved `docs/044_EXPORT_PIPELINE.md §19` / `patches/PATCH-0015`
- Status: **COMPLETE**
- Selected persistence: additive SQLite schema v28 (one insert-only table)
- Commit: `feat: establish edit-pipeline export application foundation`
- Immediate next milestone: 044 serializers / external formats / Artifacts / Export Profiles — product-gated, deferred

This milestone establishes the first **Edit-Pipeline Export Application Foundation**, implementing approved
`044 §19` (PATCH-0015). From exactly one existing durable `ApprovedEditDecision` (`043 §7.4`), admitted
**read-only** under a running unit execution, the `ApprovedEditExportService` deterministically records one
immutable `ApprovedEditExportRepresentation`. The representation **owns a complete exported-meaning snapshot**
— approved Source Timeline range, approved Candidate Type/label, approved rationale, approving decision kind
(`accept`|`modify`), and the human actor reference — copied faithfully **from the `ApprovedEditDecision`**
(range/type/rationale/kind) and, for the actor, from the source `EditReviewDecision`; nothing is re-derived
from the original Candidate. It **references** the source `ApprovedEditDecision`, `EditReviewDecision`, and
`EditCandidate`, and **denormalizes** Source Media/Timeline plus execution provenance. Approved Candidate Type
uses the **open** `§9.1` contract (validated as a canonical token, not the three-key generation registry).
There is **no status field and no state machine**: the record is a pure durable snapshot. `Reject` produces no
representation (only accept/modify approvals are exportable, enforced at construction). **Multiple distinct
representations MAY reference the same `ApprovedEditDecision`** (no uniqueness on `source_approved_decision_id`).
Before construction the service validates lineage consistency across the approved decision, its review
decision, and the candidate (matching candidate identity, matching decision kind, and consistent
media/timeline). Provenance chains `ApprovedEditExportRepresentation → ApprovedEditDecision → …` with
**single-direct-upstream** DomainResult chaining (the representation's DomainResult upstream = exactly the
`ApprovedEditDecision`'s DomainResult). Admission is **Application-owned**, running-execution-gated, read-only
toward upstream, caller-owned-identity, and **atomic**: the representation and its DomainResult are inserted in
one `BEGIN IMMEDIATE` transaction with identity-absence checks and a linkage validator; any collision or error
rolls back the whole admission (no orphan representation or DomainResult). No wall-clock or randomness is read,
so reconstruction and replay are deterministic. The AGENTS.md Architect Checklist is entirely `No`: no existing
Domain contract change, no released-schema meaning change, no lifecycle authority change (Approved Edit
Decisions/lineage consumed read-only), no responsibility shift, one new additive identity
(`ApprovedEditExportRepresentationId`), one additive migration, and no Blueprint contradiction; §9.1, 043's
Review foundation, and the v1..v27 records are unchanged. Additive schema **v28** adds one insert-only table
(`approved_edit_export_representations`) enforcing identity uniqueness, the approving decision-kind CHECK
(accept/modify), non-empty type/rationale/actor, range validity, and a FK to `approved_edit_decisions`;
migration compatibility from every released version (v1..v27) to v28 is verified, and unsupported downgrade/
direct-skip migrations remain rejected. An in-process acceptance drives the full chain (Candidate →
accept/modify review → export) and confirms Accept/Modify snapshot fidelity from the approved decision,
provenance chaining, multiple representations per approved decision, an unmutated upstream, absence of any
deferred Artifact/profile/scope table or status/format/path column, restart reconstruction, and deterministic
replay. The complete 1592-test suite passes. Serializers, external/interchange formats, physical files,
Artifacts, Export Profiles, current-selection, multi-decision export scope, and executable edit semantics
remain later, separately-gated milestones and are out of scope.

## Edit-Pipeline Export Assembly Application Foundation — First Slice (044 §20 Export Scope)

- Blueprint: approved `docs/044_EXPORT_PIPELINE.md §20` / `patches/PATCH-0016`
- Status: **COMPLETE**
- Selected persistence: additive SQLite schema v29 (one aggregate table + one ordered-membership table)
- Commit: `feat: establish edit export assembly foundation`
- Immediate next milestone: 044 serializer / external format / Artifact for the edit pipeline — product-gated, deferred

This milestone establishes the first **Edit-Pipeline Export Assembly Application Foundation**, implementing
approved `044 §20` (PATCH-0016). From an **explicitly supplied, non-empty set** of existing durable
`ApprovedEditExportRepresentation` records (044 §19), admitted **read-only** under a running unit execution,
the `EditExportAssemblyService` deterministically records one immutable `EditExportAssembly`: a durable,
canonical, **format-neutral** aggregate that establishes the existence of a **coherent Export Scope anchored to
exactly one Source Timeline**. Aggregation precedes serialization; the Assembly is upstream of every future
serializer/Artifact stage. The Assembly **owns** its identity, its Source Timeline anchor, a denormalized
Source Media identity, an **immutable ordered membership snapshot** of one or more member representation
identities, execution provenance, and multi-upstream DomainResult lineage; it **references** its members and
**copies no approved edit meaning** (each `ApprovedEditExportRepresentation` remains authoritative for its own
exported edit meaning). There is **no status field, no lifecycle, no Export Profile/Configuration, no
serializer, no Artifact, no file**.

The **membership-selection policy is intentionally not implemented** (§20 A-3): the caller explicitly supplies
the intended member representation identities; the service validates and admits that explicit set (non-empty,
unique, every member exists and is a canonical representation, every member belongs to the anchor Source
Timeline, all members share one Source Media, no cross-timeline/cross-media admission) but never discovers,
selects, filters, or decides which representations ought to belong. Membership is normalized to the repository's
**stable canonical identity ordering** and persisted with that order — strictly a deterministic
storage/replay normalization, **not** an edit-execution, overlap-resolution, or timeline-transformation order.

Admission is **Application-owned**, running-execution-gated, read-only toward upstream, caller-owned-identity,
deterministic (no wall-clock/randomness) → replay-safe, and **atomic**: the Assembly, its ordered membership
rows, and its DomainResult (with one direct upstream per member, in canonical order — the repository's first
**multi-upstream** aggregate lineage) are inserted in one `BEGIN IMMEDIATE` transaction with identity-absence
checks and a linkage validator; any collision or error rolls back the whole admission (no orphan Assembly,
membership, or DomainResult). Reordered equivalent caller input normalizes to the same canonical Assembly, and
replaying the same identities + payload into a fresh database reconstructs an equal Assembly. The AGENTS.md
Architect Checklist is entirely `No`: no existing Domain contract change, no released-schema meaning change, no
lifecycle authority change (representations consumed read-only), no responsibility shift, one new additive
identity (`EditExportAssemblyId`), one additive migration, and no Blueprint contradiction; §19 and the v1..v28
records are unchanged. Additive schema **v29** adds one insert-only aggregate table (`edit_export_assemblies`)
and one ordered-membership table (`edit_export_assembly_members`) enforcing per-parent ordinal uniqueness,
per-parent member uniqueness, and FK integrity to both the parent Assembly and the source representation;
migration compatibility from every released version (v1..v28) to v29 is verified, and unsupported downgrade/
direct-skip migrations remain rejected. Focused domain, service, atomic/replay, migration, and in-process
acceptance tests confirm canonical ordering, the running-execution gate, missing/duplicate/cross-timeline/
cross-media/mismatched-anchor rejection, deterministic construction and replay, multi-upstream lineage,
atomic rollback, membership FK enforcement, restart reconstruction, an unmutated member set, and the absence of
any serializer/Artifact/materialization table or status/format/scope-selection column. The complete 1629-test
suite passes. Serializer, external/interchange format, Artifact creation, physical materialization, delivery,
Export Package, Export Profile/Configuration, membership/scope-selection policy, subset selection,
current-selection, supersession, reconciliation, and executable edit semantics remain later, separately-gated
milestones and are out of scope.

## Edit-Pipeline Export Artifact Foundation — First Slice (044 §21 Canonical Representation)

- Blueprint: approved `docs/044_EXPORT_PIPELINE.md §21` / `patches/PATCH-0017`
- Status: **COMPLETE**
- Selected persistence: **none** — the Artifact is a derived, regenerable, non-authoritative representation;
  `SQLITE_SCHEMA_VERSION` stays 29 (no schema, table, or migration added)
- Commit: `feat: establish edit export artifact foundation`
- Immediate next milestone: 044 concrete serializer / external format projection — product-gated, deferred

This milestone establishes the first **Edit-Pipeline Export Artifact Foundation**, implementing approved
`044 §21` (PATCH-0017). From exactly one durable `EditExportAssembly` (044 §20), consumed **read-only**, the
`EditExportArtifactService` deterministically **derives** one `EditExportArtifact`: the canonical,
**format-neutral external representation** of the Assembly's complete approved edit meaning. Where the Assembly
only **references** its member representations, the Artifact **presents** their approved meaning — one
`EditExportArtifactEntry` per member, in the Assembly's canonical member order, each carrying the member's
approved Source Timeline range, approved Candidate Type/label, approved rationale, approving decision kind, and
human actor, copied faithfully (never re-derived or reinterpreted) from the `ApprovedEditExportRepresentation`.
The Artifact denormalizes the Assembly's Source Timeline and Source Media and references the source Assembly and
each member representation for provenance/traceability.

The Artifact is **derived, regenerable, and non-authoritative** (§3.3/§13, §21 B-5/B-6): it is **not persisted**
(no new table, schema, or migration — the Goal excludes persistence unless the contract unambiguously requires
it, and §21 does not) and is reconstructed on demand from the preserved approved sources; its loss damages no
`ApprovedEditDecision`, `ApprovedEditExportRepresentation`, or `EditExportAssembly`. It owns **no execution
provenance, no DomainResult, no status/lifecycle, no Export Profile/Configuration, no serializer/format, and no
file**. It is **descriptive, never executable** — no cut/keep/delete/transform command, output-timeline
coordinate, or NLE/rendering instruction. Derivation is deterministic (no wall-clock/randomness), so
regeneration from the same upstream preserves the same Product meaning, while a new caller-owned identity yields
another derived Artifact of the same Assembly (§21 B-13). **Representation Failure is explicit** (§21 B-11): if
a member representation is missing or its lineage is inconsistent with the Assembly, an
`EditExportArtifactError` is raised naming the failure — approved meaning is never silently omitted. The
`external representation` (what is communicated) is fixed; the `concrete serialization syntax` (how it is
written) is deferred entirely to future serializer projections. Derivation reads upstream only via `.get` and
never mutates the Assembly or its members. The AGENTS.md Architect Checklist is entirely `No`: no existing
Domain contract change, no released-schema meaning change, no lifecycle authority change (Assembly and members
consumed read-only), no responsibility shift, one new additive identity (`EditExportArtifactId`), **no
migration**, and no Blueprint contradiction; §19, §20, and the v1..v29 records are unchanged. Focused domain,
service, and in-process acceptance tests confirm faithful complete-meaning presentation in canonical order,
deterministic regeneration, multiple derived Artifacts per Assembly, unknown-assembly and missing-member
(explicit representation failure) and cross-lineage rejection, an unmutated upstream, the derived/non-persisted
nature (no Artifact table), and the absence of any status/format/serializer/path field. The complete 1646-test
suite passes. Concrete serializers, external representation syntax, export schema, external file formats,
human-readable/machine-readable/NLE projections, cross-representation equivalence, format-specific
representability, Export Profile/Configuration, provider/NLE adapters, physical materialization, delivery,
Export Package, executable edit semantics, output-timeline transformation, and Artifact replacement/revision
remain later, separately-gated milestones and are out of scope.

## Edit-Pipeline Export — First Runnable Slice: JSON Serialization + Local Materialization (044 §22)

- Blueprint: approved `docs/044_EXPORT_PIPELINE.md §22` / `patches/PATCH-0018`
- Status: **COMPLETE**
- Selected persistence: **none** — serializer and materializer are non-authoritative projections;
  `SQLITE_SCHEMA_VERSION` stays 29 (no schema, table, or migration; filesystem side effect only)
- Commit: `feat: first runnable edit export — json serialization + local materialization + CLI`
- Immediate next milestone: additional concrete formats / delivery — product-gated, deferred

This milestone delivers the **first runnable Edit Export**: a user can now invoke LectureOS and obtain a real
local edit-export file. Implementing approved `044 §22` (PATCH-0018), it adds the first concrete serializer and
safe local physical materialization over the §21 canonical `EditExportArtifact`, plus a runnable entry point.

**Selected first format (delegated Product decision):** **LectureOS-native JSON** —
`lectureos-edit-export-json`, version `v1`, identifier `application/vnd.lectureos.edit-export+json`. JSON was
chosen as the smallest fully-faithful, deterministic, inspectable, non-executable projection of the descriptive
approved edit meaning the Artifact carries. NLE interchange formats (EDL/FCPXML/AAF/OTIO) were rejected for the
first slice because they require executable / output-timeline semantics and cannot carry the approved
rationale, decision kind, actor, or Candidate Type/label without inventing missing timeline semantics or
silently dropping meaning — i.e. they cannot represent the current Artifact meaning completely and faithfully.

`serialize_edit_export_json(artifact)` (pure) projects the Artifact into a `SerializedEditExport` value: it
reads the Artifact without mutation, preserves every entry in canonical member order, and carries the complete
approved meaning — top-level format/version, artifact/assembly/media/timeline identities, and per edit the
source representation identity, decision kind, approved range start/end, approved Candidate Type/label,
approved rationale, and human actor — with a fixed field order, UTF-8, LF newlines, a single trailing newline,
and non-ASCII (e.g. Korean) preserved unescaped (`ensure_ascii=False`). It is **deterministic** (byte-identical
for the same Product meaning) and enforces **format-specific Representation Failure** explicitly: a non-finite
number (`allow_nan=False`) raises `EditExportSerializationError` rather than emitting invalid or lossy JSON.

`EditExportMaterializationService.materialize_artifact` serializes then writes via an injected
`EditExportFileWriter` port; `LocalEditExportFileWriter` (infrastructure) writes to a caller-selected absolute
destination using a temporary file + flush + fsync + atomic placement (`os.link` to create, or `os.replace`
only on explicit overwrite). **Collision is explicit**: identical existing bytes are an idempotent success,
different existing bytes fail by default (no overwrite), overwrite happens only on explicit request, and a
symlink or non-regular existing object is never overwritten; necessary parent directories are created. On any
serialization or write failure no partial final file is left and approved upstream data is preserved. Success
returns a structured `EditExportMaterializationResult` (final path, format, version, encoding, byte length),
reported only after durable placement.

The runnable entry point `lectureos.edit_export_cli` (invoked
`PYTHONPATH=src python3 -m lectureos.edit_export_cli <assembly-id> --database <db> --output <path> [--overwrite]`)
opens the database read-only, derives the Artifact with a deterministic caller-owned identity
(`edit-export:<assembly-id>`), serializes, materializes, prints the final path + format/version + byte length,
returns `0` on success, and on error prints `error: <message>` to stderr and returns `1` without leaving a
final file. Nothing is persisted to the database; the derived Artifact and serialized output remain regenerable
(re-running from the same upstream is byte-identical). The AGENTS.md Architect Checklist is entirely `No`: no
existing Domain contract change, no released-schema meaning change, no lifecycle authority change (Assembly and
representations consumed read-only), no responsibility shift, no new identity, **no migration**, and no
Blueprint contradiction; §19/§20/§21 and the v1..v29 records are unchanged. Focused serializer, file-writer,
materialization-service, and CLI tests plus an in-process end-to-end acceptance confirm faithful complete-
meaning serialization in canonical order, deterministic bytes, format/version identity, UTF-8/non-ASCII
preservation, explicit unrepresentable-value rejection, exact on-disk file contents, atomic write with no
partial file, explicit collision and no-default-overwrite with the existing file preserved, explicit-overwrite,
failure-leaves-no-file, an unmutated upstream, and a real runnable success/failure path. The complete 1676-test
suite passes. Additional concrete formats (EDL/FCPXML/AAF/OTIO/CSV/…), multiple formats, serializer registry,
cross-format equivalence, Export Profile/Configuration, provider/NLE adapters, remote delivery/upload/URLs,
executable edit semantics, output-timeline transformation, DB persistence of the derived Artifact or serialized
output, and package/bundle export remain later, separately-gated milestones and are out of scope.
