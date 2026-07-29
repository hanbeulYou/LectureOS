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

## Developer Preview — Mock Workflow, Golden Example, and Docs (tooling only)

- Status: **COMPLETE**
- Product/Blueprint impact: **none** — developer experience only; no new capability, no schema change
  (`SQLITE_SCHEMA_VERSION` stays 29), no product semantics changed.

Adds a runnable mock end-to-end demo (`lectureos.edit_export_demo`) that drives the full pipeline — fake
transcript → analysis + human review → approved decisions → representations → Assembly → Artifact → LectureOS
Edit Export JSON → local file — with no real media, model, or network, producing a byte-deterministic export.
Adds a worked example under `examples/edit-export/` with a golden output (`expected/edit-export.json`) and a
regression test (`tests/test_edit_export_demo.py`) that reproduces it byte-for-byte. Improves the edit-export
CLI help/usage/error guidance (usability only; arguments unchanged). Refreshes `README.md` (Korean) to the
current MVP with an Implemented / In Progress / Planned breakdown, an implemented-pipeline architecture
overview, quick start, CLI usage, example export, limitations, and roadmap; adds an MIT `LICENSE`; and ignores
generated demo output. The complete 1682-test suite passes.

## Repository Integrity Validation — Read-only Validator + CLI (tooling only)

- Status: **COMPLETE**
- Product/Blueprint impact: **none** — a read-only diagnostic subsystem asserting existing invariants; no new
  product concept or contract, no schema change (`SQLITE_SCHEMA_VERSION` stays 29), no product semantics
  changed.

Adds a repository-wide, **read-only** integrity validation subsystem (`src/lectureos/validation/`) that verifies
persisted repository state is internally consistent before higher-level workflows run. It opens the database
with `PRAGMA query_only = ON`, issues only SELECT/PRAGMA, and never mutates state; it is independent of the
application/business services (it consumes the persisted store) and is not coupled into export. It checks:
schema version compatibility; foreign-key integrity (`PRAGMA foreign_key_check`); **dangling non-foreign-key
references** (the many plain-TEXT references the schema does not enforce — review/candidate/DomainResult ids);
DomainResult upstream lineage contiguity; the Edit Export Assembly invariants (non-empty, contiguous/unique
membership, single-Source-Timeline/Media coherence, canonical member order); the edit-export provenance
invariants (representation ↔ approved decision ↔ review decision kind and lineage consistency); and malformed
identities. Diagnostics are structured (`code`, `severity`, `location`, `message`) and deterministic (sorted by
`(code, location, message)`); a `ValidationReport` derives overall health (healthy/warnings/errors). A runnable
CLI (`lectureos.validate_cli --database <path> [--format text|json]`) prints a summary and each diagnostic and
returns machine-readable exit codes (`0` healthy, `1` errors, `2` warnings-only). Comprehensive tests cover a
healthy repository, each corruption class (dangling reference, foreign-key orphan, empty assembly,
non-contiguous ordinals, cross-timeline/cross-media member, kind mismatch, malformed identity, duplicate member
on a tampered schema), multiple simultaneous failures, determinism, read-only behavior, non-repository and
missing-database handling, CLI success/error/warning exit codes, and byte-for-byte golden reports
(`examples/repository-validation/`). Documented in `implementation/070_REPOSITORY_VALIDATION.md` and the README.
The complete 1713-test suite passes. No Blueprint PATCH is required (no product meaning changes).

## Media Import Application Foundation — First Slice (045 §1 Local Source Media Registration)

- Blueprint: approved `docs/045_MEDIA_IMPORT_PIPELINE.md §1` / `patches/PATCH-0019`
- Status: **COMPLETE**
- Selected persistence: additive SQLite schema **v30** (one insert-only table `source_media`)
- Commit: `feat: establish media import application foundation`
- Immediate next milestone: audio extraction / ffprobe for the imported Source Media — product-gated, deferred

This milestone establishes the first **Media Import Application Foundation** (045 §1 / PATCH-0019) — the pipeline
origin and the first owner of `SourceMediaId`, which every downstream stage had only referenced. From one
caller-selected local file, inspected read-only, `MediaImportService` registers a canonical
`SourceMediaRecord`. **Media identity is content-addressed**: it is derived from a streaming SHA-256 fingerprint
of the file bytes (`sha256:<hexdigest>`), so it is independent of path/filename/extension and idempotent for
identical content by construction; the domain enforces the derivation (`identity == "<algorithm>:<digest>"`).
The `LocalSourceMediaInspector` streams the file in fixed 1 MiB chunks (never loading it whole into memory),
rejects missing/directory/non-regular/unreadable/empty(0-byte) sources with an explicit `MediaImportError`,
accepts a symlink only when it resolves to a readable regular file, and records the resolved absolute observed
path. The original file is **referenced in place** (no copy/move/delete); the record stores the fingerprint,
byte length (> 0), and observed path as immutable provenance, and carries **no execution provenance, status,
duration, or codec**.

Import is idempotent: re-importing identical content resolves and returns the existing record (`created=False`);
the same content under a different path converges on the same identity (the recorded path stays the first
import's); changed content at the same path is a different identity and a new record (insert-only coexistence);
a near-concurrent duplicate converges to the existing record on a persistence collision. Persistence is durable,
immutable, insert-only, and atomic (`BEGIN IMMEDIATE` with identity + `UNIQUE(fingerprint_algorithm,
fingerprint_digest)` uniqueness and rollback leaving no partial row). LectureOS is **not authoritative for the
file's continued physical availability** (settling `030 §5.1`'s Requires-Validation boundary); a moved/deleted
original does not change the record and validation never checks physical existence. The AGENTS.md Architect
Checklist is entirely `No`: no existing contract change, no responsibility shift, `SourceMediaId` reused (no new
identity type), one additive migration, and no Blueprint contradiction; 040–044 and the v1..v29 records are
unchanged. Additive schema **v30** adds the insert-only `source_media` table; every released version (v1..v29)
chains single-step to v30 preserving rows, and downgrade/direct-skip/unsupported-target migrations are rejected.
Read-only repository validation gains `source_media` checks (malformed fingerprint, identity/fingerprint
disagreement, duplicate fingerprint) without checking physical existence. A runnable CLI
(`lectureos.media_import_cli <source-path> --database <db>`, bootstrapping the DB if new) reports the canonical
identity, fingerprint, byte length, and created/reused status, exits 0/1, and leaves the DB and source unchanged
on failure. A deterministic no-real-video demo (`lectureos.media_import_demo`) with committed binary fixtures
and a golden summary, plus focused domain, inspector (filesystem safety, streaming determinism, non-ASCII,
symlink/empty/missing/directory/unreadable), atomic persistence, CLI, migration, and validation tests, cover the
slice. The complete 1766-test suite passes. Audio extraction, ffprobe/duration/codec, transcoding, remote/
managed storage, and transcription remain later, separately-gated milestones and are out of scope.

## Source Intake Application Foundation — Source Media Transcription Intake Eligibility (First Slice, 040 §13)

- Blueprint: approved `docs/040_TRANSCRIPT_PIPELINE.md §13` / `patches/PATCH-0020`
- Status: **COMPLETE**
- Selected persistence: additive SQLite schema **v31** (one insert-only table `transcript_source_intakes`)
- Commit: `feat: establish source media transcription intake eligibility`
- Immediate next milestone: External ASR Boundary provider result (040 §4.2) — introduces the first real media
  inspection/execution, product-gated, deferred

This milestone establishes the first application slice of **040 §4.1 Source Intake** (040 §13 / PATCH-0020) —
the smallest connection between the persisted `source_media` record (Media Import, 045 §1) and the Transcript
Pipeline. It answers only "**can this already-imported Source Media record be admitted as a Transcript Pipeline
input?**" — not any codec/audio/decode/transcription question. `TranscriptSourceIntakeService.admit` accepts a
canonical `SourceMediaId` (never a path), rejects a malformed identity before touching the repository, resolves
the persisted `source_media` record read-only, and — when the reference resolves — records a durable,
content-derived `TranscriptSourceIntake`. Eligibility is a repository/application decision from **persisted facts
only** (eligible iff the id resolves to a persisted record); an unknown Source Media is rejected explicitly. The
intake identity is derived (`transcript-source-intake:<source_media_id>`, enforced in the domain), giving exactly
one canonical intake per Source Media and idempotency by construction; a near-concurrent duplicate converges on
a persistence collision. The slice performs **no** decoding, probing, hashing, file access, or transcription;
carries **no** execution provenance/DomainResult (an eligibility question, not an execution step); produces
**no** transcript content or execution result; and never mutates the Source Media record. It **does not check
physical file existence** — a moved/deleted reference-in-place original is not an eligibility failure (045 §1
M-11), keeping operational availability and persisted-domain integrity distinct.

The AGENTS.md Architect Checklist is entirely `No`: no existing contract change (§4.1 is implemented, not
rewritten), no responsibility shift, `SourceMediaId` reused, one additive identity
(`TranscriptSourceIntakeId`), one additive migration, and no Blueprint contradiction; 041–045 and the v1..v30
records are unchanged. Additive schema **v31** adds the insert-only `transcript_source_intakes` table (identity
PK, `UNIQUE(source_media_id)`, FK → `source_media`); every released version (v1..v30) chains single-step to v31
preserving rows, and downgrade/direct-skip/unsupported-target migrations are rejected. Read-only repository
validation gains `transcript_source_intakes` checks (dangling source_media reference, identity/reference
derivation disagreement, duplicate intake per Source Media) without checking physical existence. A runnable CLI
(`lectureos.transcript_intake_cli --media <source-media-id> --database <db>`, existing repository required)
reports created/reused, the intake and Source Media identities, and "no transcription was executed"; it exits
0/1 and leaves the repository unchanged on a malformed/unknown media or any failure. A deterministic no-decoding
demo (`lectureos.transcript_intake_demo`, reusing the media-import fixtures) with a golden summary, plus focused
domain, service, atomic persistence, CLI, migration, and validation tests, cover the slice. The complete
1809-test suite passes. ffmpeg/ffprobe, media probing, duration/codec/audio-stream verification, audio
extraction, transcoding, transcription providers, model/language, transcript generation, background jobs,
multiple transcript-intakes per Source Media, and the actual transcript execution linked to an intake remain
later, separately-gated milestones and are out of scope.

## External ASR Boundary — Provider Transcript Result Admission (First Slice, 040 §14)

- Blueprint: approved `docs/040_TRANSCRIPT_PIPELINE.md §14` / `patches/PATCH-0021`
- Status: **COMPLETE**
- Selected persistence: additive SQLite schema **v32** (one insert-only table `provider_transcript_admissions`;
  the existing v5 provider result / segment / raw transcript / domain result tables are reused unchanged)
- Commit: `feat: establish external ASR boundary provider transcript result admission`
- Immediate next milestone: a real single-provider ASR execution adapter (e.g. a local Whisper adapter) behind
  this provider-neutral boundary — introduces actual audio extraction/decoding, product-gated, deferred

This milestone establishes the first application realization of **040 §4.2 External ASR Boundary** and
**§4.3 Raw Transcript Preservation** (040 §14 / PATCH-0021) — the smallest boundary through which an
**externally produced** ASR result is admitted for an admitted `TranscriptSourceIntake` (040 §13) to produce the
first canonical `RawTranscript`. It answers only "**how does LectureOS admit an externally produced ASR result
for an already-admitted Source Media intake?**" — not how media is decoded, how audio is extracted, or which
provider runs. `ProviderTranscriptAdmissionService.admit` accepts a canonical `TranscriptSourceIntakeId` and a
provider-neutral (LectureOS-native) result document (provider, optional model/language, external result
reference, ordered `start`/`end`/`text` segments) — **not** a media path — and **executes no ASR engine**, reads
no media file, and makes no network request (the result is supplied). The existing canonical
`ProviderTranscriptResult`, `TranscriptSegment`, and `RawTranscript` records are reused unchanged: the provider
evidence is preserved un-normalized and kept distinct from the canonical Raw Transcript (its `TranscriptId` is
never the provider payload). All identities are derived deterministically from the anchor
`(intake_id, provider, model, provider_result_ref)` (SHA-256); admission carries **external** execution
provenance (no internal `ProcessingRun`/RUNNING unit execution is invented). Admission is idempotent by a
`content_fingerprint` over the full payload; re-admitting the same anchor with a different payload is a conflict
and is rejected without mutation. Segment timing is in seconds (`end > start`, non-overlapping, non-decreasing),
text is preserved exactly (Korean included), and an empty result is rejected.

The AGENTS.md Architect Checklist is entirely `No`: no existing contract change (§4.2/§4.3 realized, not
rewritten), no responsibility shift, the transcript records/identities reused, one additive identity
(`ProviderTranscriptAdmissionId`), one additive migration, and no Blueprint contradiction. Additive schema
**v32** adds the insert-only `provider_transcript_admissions` table (identity PK, `UNIQUE(provider result)`,
`UNIQUE(raw transcript)`, FKs → `transcript_source_intakes`, `source_media`); every released version (v1..v31)
chains single-step to v32 preserving rows, and downgrade/direct-skip/unsupported-target migrations are rejected.
Read-only repository validation gains `provider_transcript_admissions` checks (dangling intake/source-media/
provider-result/raw-transcript, intake↔media provenance disagreement, raw↔provider disagreement, segment-count
disagreement, duplicate provider result / raw transcript) plus a raw-transcript segment ordinal-contiguity
check, none checking provider availability or physical media. A runnable CLI
(`lectureos.transcript_result_admit_cli --intake <id> --input <provider-result.json> --database <db>`, existing
repository required) reports the admission/provider-result/raw-transcript identities, segment count, created/
reused, and "LectureOS did not execute an ASR engine"; it exits 0/1 and leaves the repository unchanged on
malformed/unknown/conflicting/invalid input. A deterministic no-ASR demo
(`lectureos.transcript_result_admission_demo`, reusing the media-import fixtures and a committed Korean
provider-result fixture) with a golden summary, plus focused domain, service, atomic persistence, CLI, migration,
and validation tests, cover the slice. The complete 1875-test suite passes. ffmpeg/ffprobe, media decoding,
audio extraction, Whisper and all ASR engines, model download/selection, provider/plugin registries, background
jobs/queues/retries/progress, streaming, diarization, word/token timestamps, language detection, correction,
review, and subtitle/export changes remain later, separately-gated milestones and are out of scope.

## First Concrete Local ASR Execution Adapter — faster-whisper (First Slice, 040 §15)

- Blueprint: approved `docs/040_TRANSCRIPT_PIPELINE.md §15` / `patches/PATCH-0022`
- Status: **COMPLETE**
- Selected persistence: **no schema change** (reuses the v32 Provider Transcript Admission structures);
  `SQLITE_SCHEMA_VERSION` stays 32
- Repository hygiene: accidentally-tracked compiled bytecode (359 `__pycache__/*.pyc`) removed from version
  control and ignored; the working tree is now genuinely clean per `git status --porcelain`
- Commit: `feat: add first concrete local ASR execution adapter (faster-whisper)`
- Immediate next milestone: the smallest transcript-workflow capability after one working local adapter —
  e.g. current-Raw-Transcript selection / readiness surfacing per intake — product-gated, deferred

This milestone establishes the first **concrete local ASR execution adapter** (040 §15 / PATCH-0022) behind the
unchanged provider-neutral admission boundary (040 §14). `LocalAsrTranscriptionService.transcribe` accepts an
admitted `TranscriptSourceIntakeId` (not a media path), resolves its `SourceMedia`, verifies the reference-in-
place source file is operationally available and still matches the stored content fingerprint (streaming,
bounded memory, reusing the Media Import inspector's symlink/read policy; changed bytes are a distinct explicit
failure directing re-import, never transcribed under the old `SourceMediaId`), runs **one** concrete local engine
(`faster-whisper`, CPU by default) behind the `LocalAsrEngineRunner` port, converts the output into the existing
`ProviderTranscriptDocument`, and hands it to the existing admission service — the **sole** write boundary. The
adapter writes no Raw Transcript / Provider Transcript Result rows directly and never mutates the Source Media or
intake. The engine dependency is optional and lazily imported (the core package and the whole suite run without
`faster-whisper`); its absence, a missing/unusable model, an engine failure, and inadmissible output surface as
typed `LocalAsr*` errors. The provider-result reference is deterministic (`local-asr:model=..:lang=..:media=
<source_media_id>`; device/compute excluded), so the adapter reuses an already-admitted result **without
re-running the engine** (avoiding spurious non-determinism conflicts); no wall-clock/randomness defines identity.
No repository write occurs before a valid result is admitted; admission atomicity remains owned by the existing
service.

The AGENTS.md Architect Checklist is entirely `No`: no existing contract change (§14 boundary reused unchanged),
no responsibility shift (admission remains the write boundary), no new identity semantics, no migration, and no
Blueprint contradiction. Adapter contract tests drive the real faster-whisper invocation shape (model/device/
compute-type propagation, `transcribe(path, language)`, segment/text/timestamp extraction, error translation,
dependency detection) via an injected fake model factory with no real library/model; orchestration, source-
verification, CLI, and deterministic-demo tests cover the rest offline. A runnable CLI
(`lectureos.local_asr_cli --intake <id> --database <db> --model <model>`) performs real local ASR and reports
identities, provider/model, segment count, created/reused, and whether real ASR ran. The deterministic demo
(`lectureos.local_asr_demo`, fake engine) with a golden proves lineage use, source verification, reuse-without-
rerun replay, failure-before-admission-writes-nothing, and healthy validation. The complete 1919-test suite
passes. **Real ASR smoke test: PASS** — a self-authored `say`-generated speech fixture was imported, admitted,
and transcribed by real faster-whisper `tiny` (3 real timestamped segments) end-to-end through the CLI with a
healthy repository; nothing was committed (transient temp dir). Other engines/providers, registries, cloud ASR,
model management, queues, retries, progress, diarization, word timestamps, translation, and a generalized ffmpeg
framework remain later, separately-gated milestones and are out of scope. Repository hygiene was corrected first:
tracked `.pyc` bytecode was untracked and ignored so the tree is genuinely clean.

## Current Raw Transcript Selection and Downstream Readiness (First Slice, 040 §16)

- Blueprint: approved `docs/040_TRANSCRIPT_PIPELINE.md §16` / `patches/PATCH-0023`
- Status: **COMPLETE**
- Selected persistence: additive SQLite schema **v33** (one append-only table `current_raw_transcript_selections`)
- Commit: `feat: add current raw transcript selection and downstream readiness`
- Immediate next milestone: the smallest Transcript Correction capability — admit one AI/rule correction
  candidate against the current Raw Transcript (040 §4.4), product-gated, deferred

This milestone decides **which admitted `RawTranscript` is the current authoritative downstream input for a
`TranscriptSourceIntake`** and whether the intake is **ready** for Correction (040 §16 / PATCH-0023). After
External Provider Transcript Admission (§14) and the local ASR adapter (§15), one intake may hold several admitted
Raw Transcripts; downstream Correction (§4.4) needs exactly one. `CurrentRawTranscriptSelectionService` enumerates
candidates (the intake's admitted Raw Transcripts from `provider_transcript_admissions`, ordered by identity —
**never ranked** by provider/model/time/length/confidence), resolves and switches the current selection, and
derives readiness. Selection is an **explicit** repository-authority decision: admitting a result does not
auto-select it (admission unchanged), so readiness stays `not_ready` until an explicit selection; history is
**append-only** (each change is a new record with a per-intake `sequence` superseding the prior via
`previous_selection_id`; the current selection is the highest sequence), so switching preserves all prior
records and no transcript content is deleted or mutated. Selecting the already-current Raw Transcript is
idempotent; a near-concurrent duplicate converges. Identity is deterministic
(`raw-transcript-selection:<sha256(intake, raw_transcript, sequence)>`; no wall-clock/randomness). A malformed
intake or Raw Transcript identity, an unknown intake or Raw Transcript, and a Raw Transcript belonging to a
different intake are rejected explicitly; the append is atomic and any failure leaves no partial state and mutates
neither the transcript, provider result, Source Media, nor intake. Readiness (`not_ready`/`ready`/`error`) is
derived from current persisted facts only — never from source-file existence, ASR/provider availability, model
accuracy, confidence, or review — and later admissions never silently replace the current selection.

The AGENTS.md Architect Checklist is entirely `No`: no existing contract change (Admission/Raw Transcript identity
and the §4.8 corrected current selection are unchanged), no responsibility shift, one additive identity
(`CurrentRawTranscriptSelectionId`), one additive migration, and no Blueprint contradiction. Additive schema
**v33** adds the append-only `current_raw_transcript_selections` table (identity PK, `UNIQUE(intake, sequence)`,
sequence/previous CHECK, FKs → `transcript_source_intakes`, `raw_transcripts`); every released version v1..v32
chains single-step to v33 preserving rows, and downgrade/direct-skip/unsupported-target migrations are rejected.
Read-only repository validation gains `current_raw_transcript_selections` checks (dangling intake/raw-transcript,
lineage mismatch, non-contiguous sequence, broken supersession), none checking ASR/model availability or
source-file existence. A single runnable CLI (`lectureos.raw_transcript_selection_cli` with `candidates`,
`select`, `readiness` subcommands) accepts intake/raw-transcript identities (never paths), lists candidates
without ranking, reports created/reused/switched and readiness, and exits 0/1 leaving the repository unchanged on
failure. A deterministic demo (`lectureos.raw_transcript_selection_demo`, fake provider results) with a golden
proves multiple distinct candidates, identity-ordered (not ranked) enumeration, idempotent re-selection,
history-preserving switching, unrelated-selection rejection, readiness, and healthy validation. The complete
1973-test suite passes. Transcript correction, candidates, structural validation, review, scoring/ranking,
merging/ensemble, subtitle/export changes, queues, and additional adapters remain later, separately-gated
milestones and are out of scope.

## First Transcript Correction Candidate Admission (First Slice, 040 §17)

- Blueprint: approved `docs/040_TRANSCRIPT_PIPELINE.md §17` / `patches/PATCH-0024`
- Status: **COMPLETE**
- Selected persistence: additive SQLite schema **v34** (one new table `correction_candidate_admissions`; the v5
  `correction_candidates` records are reused unchanged)
- Commit: `feat: add first transcript correction candidate admission`
- Immediate next milestone: the first Human Authority decision on a Correction Candidate — accept/reject one
  admitted candidate and prepare (not auto-create) the first corrected transcript revision (040 §4.7), deferred

This milestone records a **proposed** correction for one segment of the intake's **currently selected** Raw
Transcript (040 §17 / PATCH-0024) **without applying it** — the first application slice of §4.4 Correction. A
Correction Candidate is a suggestion, not canonical transcript content. `CorrectionCandidateAdmissionService.admit`
resolves the intake, requires **readiness** (a valid current Raw Transcript selection, §16) and that the target
Raw Transcript is that current selection, resolves the target segment and verifies it belongs to the Raw
Transcript, and verifies the supplied **source-text snapshot** equals the persisted segment text (stale
detection); it rejects empty and **no-op** proposed text. It **reuses the canonical `CorrectionCandidate`** (v5 —
no second correction hierarchy) with external/manual provenance (deterministic markers, no internal RUNNING
execution) and binds it via the additive v34 `correction_candidate_admissions` record (intake, segment, immutable
snapshot, source metadata). Identity is deterministic from the anchor `(intake, raw_transcript, segment,
source_type, source_reference, candidate_ref)`; admission is idempotent by a content fingerprint and a conflicting
reuse of the same anchor is rejected without overwrite. Multiple distinct suggestions per segment coexist (distinct
`candidate_ref`). Admission **never** mutates Raw Transcript text, the current selection, the Source Media, or the
intake, and creates no corrected revision, decision, acceptance, ranking, or review. After a later selection
switch, existing candidates remain immutable historical evidence, surfaced as no longer applicable — not
corruption.

The AGENTS.md Architect Checklist is entirely `No`: no existing contract change (CorrectionCandidate/Raw
Transcript/§16 selection unchanged), no responsibility shift, one additive identity
(`CorrectionCandidateAdmissionId`), one additive migration, and no Blueprint contradiction. Additive schema
**v34** adds the `correction_candidate_admissions` table (identity PK, `UNIQUE(correction_candidate_id)`, FKs →
`correction_candidates`, `transcript_source_intakes`, `raw_transcripts`, `transcript_segments`); every released
version v1..v33 chains single-step to v34 preserving rows, and downgrade/direct-skip/unsupported-target migrations
are rejected. Read-only repository validation gains `correction_candidate_admissions` checks (dangling candidate/
intake/raw-transcript/segment, raw-transcript-not-in-intake, segment-not-in-raw-transcript, source-text
disagreement, admission lineage disagreement, empty proposed text) — and deliberately does not diagnose a
historical candidate as corruption merely because a different Raw Transcript is currently selected. One CLI
(`lectureos.correction_candidate_cli` with `admit`/`list`, no `--apply`) accepts identities (never paths), states
the candidate was not applied, lists candidates with current-selection applicability (not ranked), and exits 0/1
leaving the repository unchanged on failure. A deterministic demo (`lectureos.correction_candidate_demo`, fake
provider results + manual candidates) with a golden proves readiness gating, immutable-segment targeting,
unchanged Raw Transcript text, idempotent replay, coexisting candidates, no ranking/application, history-preserving
selection switch, and stale/not-current rejection. The complete 2026-test suite passes. Candidate acceptance/
rejection/modification, ranking, automatic correction, LLM/rule engines, corrected transcript revision, review,
and subtitle/export changes remain later, separately-gated milestones and are out of scope.

## First Human Authority Decision on a Correction Candidate (First Slice, 040 §18 / GOAL-009)

- Blueprint: approved `docs/040_TRANSCRIPT_PIPELINE.md §18` / `patches/PATCH-0025`
- Status: **COMPLETE**
- Selected persistence: additive SQLite schema **v35** (one append-only table `correction_candidate_decisions`;
  the v5 `correction_candidates` records are reused unchanged)
- Commit: `feat: add first human authority decision on a correction candidate`
- Immediate next milestone (GOAL-010): consume Accepted decisions to prepare the first corrected transcript
  revision input — no transcript mutation, product-gated, deferred

This milestone establishes the first explicit **Human Authority** for Transcript Correction (040 §18 / PATCH-0025,
GOAL-009): whether a human explicitly **accepts** or **rejects** an admitted `CorrectionCandidate` (§17). A
suggestion is only evidence; authority exists only when a human decides. `CorrectionCandidateDecisionService.decide`
records an append-only, immutable, deterministic decision referencing exactly one admitted candidate. Three states
exist — **Undecided** (no record; derived by absence), **Accepted**, **Rejected** — with **no Modify** (deferred).
History is append-only (INSERT-only; per-candidate `sequence` + `previous_decision_id`); the current authority is
the highest-sequence record, always **derived**, never stored. Identity is deterministic from
`(correction_candidate_id, kind, sequence)` (no wall-clock/randomness); the decision matrix (None→Insert;
same-kind→Reuse; different-kind→Append) is enforced, replay is idempotent, and a same-anchor/different-provenance
re-submission is a conflict rejected without overwrite. Only Accepted candidates are eligible for future
corrected-revision generation (established, not implemented). The decision **never** mutates the candidate, the Raw
Transcript, any segment, or the current selection, and creates no corrected revision, decision, or application.

**Reuse investigation (GOAL-009 requirement):** the existing `TranscriptReviewDecision` (§4.6/§4.7) requires a
revision context + review preparation + RUNNING execution + Modify — all forbidden here; the generic
`review.models.ReviewDecision` references a review-domain `CandidateReference`/`ReviewItem`, not a
`CorrectionCandidateId` (wrapping would be a second candidate hierarchy). Neither is reusable as the aggregate.
The smallest additive aggregate was introduced, **reusing** the Review `DecisionKind` (accept/reject) and
`HumanActorReference` value types and the 040 §16 append-only supersession pattern — no second candidate or review
hierarchy. **Architect Decision was judged not required:** 040 §4.6 explicitly leaves candidate-review-item
coupling unconfirmed (§11 "Requires Validation"), so a direct binary candidate decision contradicts no confirmed
contract; §4.6/§4.7 remain intact for the revision-scoped review path. The AGENTS.md Architect Checklist is
entirely `No`: no existing contract change, no responsibility shift, one additive identity
(`CorrectionCandidateDecisionId`), one additive migration, and no Blueprint contradiction. Additive schema **v35**
adds the `correction_candidate_decisions` table (identity PK, `UNIQUE(candidate, sequence)`, sequence/previous
CHECK, kind CHECK accept/reject, FK → `correction_candidates`); every released version v1..v34 chains single-step
to v35 preserving rows, and downgrade/direct-skip/unsupported-target migrations are rejected. Read-only repository
validation gains `correction_candidate_decisions` checks (dangling candidate, non-contiguous sequence, broken
supersession) — integrity only, never flagging a historical decision as corruption. One CLI
(`lectureos.correction_candidate_decision_cli` with `decide`/`status`/`history`, no `--apply`) records/inspects
authority and derives current status/eligibility, exiting 0/1 leaving the repository unchanged on failure. A
deterministic demo (`lectureos.correction_candidate_decision_demo`) with a golden exercises the §51 A/B/C/D
authority evolution and proves candidate/Raw-Transcript immutability and healthy validation. The complete
2079-test suite passes. Applying accepted decisions, corrected-revision generation, current corrected-revision
selection, Modify, ranking, automatic correction, and review UI remain later, separately-gated milestones and are
out of scope.

## First Corrected Transcript Revision — One-Candidate Explicit Application (First Slice, 040 §19 / GOAL-010)

- Blueprint: approved `docs/040_TRANSCRIPT_PIPELINE.md §19` / `patches/PATCH-0026`
- Status: **COMPLETE**
- Selected persistence: additive SQLite schema **v36** (one new table `corrected_revision_generations`; the v5
  `corrected_transcript_revisions` / segment / domain-result records are reused unchanged)
- Commit: `feat: add first corrected transcript revision generation`
- Immediate next milestone (GOAL-011): Current Corrected Revision Selection — a separate authority deciding
  which corrected revision is the current downstream input, deferred

This milestone establishes the first **immutable Corrected Transcript Revision** (040 §19 / PATCH-0026,
GOAL-010): explicitly applying exactly **one currently Accepted** Correction Candidate (§17/§18) to its
authoritative source Raw Transcript. Acceptance authorizes; generation applies — separate boundaries: accepting
never creates a revision, and `CorrectedRevisionGenerationService.generate` is an explicit request naming one
candidate. Generation requires the candidate's **current** §18 authority to be Accepted (Undecided/Rejected
ineligible; historical acceptance insufficient after a later Reject) and structural applicability against the
candidate's own §17 lineage (its Raw Transcript is the intake's current selection; the target segment belongs to
it; the persisted segment text equals the source-text snapshot — staleness is ineligibility, never corruption,
never fuzzy-matched). Application is a pure deterministic transformation reusing the **canonical v5
`CorrectedTranscriptRevision`** (complete snapshot via ordered segment references — no second transcript
representation): one new replacement segment with the candidate's exact proposed text and `replaces_segment_id`,
timing/order/timeline/speaker preserved, every unaffected segment referenced unchanged, human/provider provenance
kept distinct. All identities derive from the anchor `(candidate, authorizing_accepted_decision)` — the revision
references the **specific authorizing Accepted Decision**, distinct re-acceptances yield distinct revisions
(immutable records acquire no new provenance; a separate content fingerprint keeps entity vs content identity
distinct), identical replay reuses (also after restart and under near-concurrent duplicates), and same-anchor
content divergence is an explicit conflict. `Accept → Generate → Reject` leaves the revision persisted and
queryable; the Reject only blocks new generation. Revisions coexist; **none is selected as current** (no
current/active flags — GOAL-011). Nothing mutates the Raw Transcript, candidate, decision history, or current
selection; the revision is a domain record, not a file.

**Reuse investigation (GOAL-010 §7):** the v5 `CorrectedTranscriptRevision` + segment/domain-result records and
their transaction-free insert helpers are reused (the PATCH-0021/24 pattern); the execution-coupled
`TranscriptService.create_corrected_revision` (RUNNING execution) is not used — no fake executions. What is new
is only the additive v36 `corrected_revision_generations` binding (identity PK, `UNIQUE(corrected_revision_id)`,
`UNIQUE(candidate, authorizing_decision)` replay anchor, FKs → revision/candidate/decision/raw-transcript/
segments, content fingerprint). **Architect Decision judged not required:** the existing confirmed v5 revision
contract answers owner/representation/parent/segment-identity (GOAL-010 §14/§24/§28/§29); §36 is resolved
conservatively by immutability (distinct authorizing decisions → distinct revisions); nothing is weakened and
GOAL-011 selection remains fully open. Every released version v1..v35 chains single-step to v36 preserving rows;
downgrade/direct-skip/unsupported-target rejected. Read-only validation gains generation checks (dangling
revision/candidate/decision/parent, authorizing-decision-not-Accept — inspecting the **specific** authorizing
decision, never current authority, decision-candidate mismatch, parent mismatch, membership disagreement). One
CLI (`lectureos.corrected_revision_cli` with `generate`/`show`/`list`, no `--force`/`--apply-all`) reports
created/reused and that the revision was not selected as current. A deterministic demo
(`lectureos.corrected_revision_demo`) with a golden proves the §70–§73 scenarios (undecided/rejected blocked,
acceptance-alone creates nothing, exact application with preservation, replay reuse, authority-change survival,
healthy validation). The complete 2133-test suite passes. Current corrected revision selection,
multiple-candidate merge, overlap resolution, revision chaining, ranking, automatic/LLM correction, linguistic
validation, mutable editing, segment structure changes, timing correction, and subtitle/export changes remain
later, separately-gated milestones and are out of scope.

## Current Corrected Revision Selection and Effective Transcript Resolution (First Slice, 040 §20 / GOAL-011)

- Blueprint: approved `docs/040_TRANSCRIPT_PIPELINE.md §20` / `patches/PATCH-0027`
- Status: **COMPLETE**
- Selected persistence: additive SQLite schema **v37** (one append-only table `corrected_revision_selections`)
- Commit: `feat: add current corrected revision selection and effective transcript resolution`
- Immediate next milestone: integrate the effective-transcript resolver into one specific downstream consumer
  (e.g. subtitle transcript intake) as its explicit input authority — product-gated, deferred

This milestone establishes the first explicit, append-only **Current Corrected Revision Selection** authority
(040 §20 / PATCH-0027, GOAL-011): which immutable `CorrectedTranscriptRevision` (§19), if any, is currently
selected for an intake's transcript context — with an explicit **Raw Transcript fallback** (a real authority
fact, never a fake revision, historically distinguishable from never-having-selected) and the deterministic
**effective-transcript resolver**. Four distinctions are preserved: revision existence ≠ selection ≠
applicability ≠ effective resolution. Currentness is explicit — never inferred from recency/uniqueness/
acceptance/generation — and `CorrectedRevisionSelectionService` mutates nothing upstream: revisions, candidates,
decisions, Raw Transcripts, and the current Raw selection are untouched, and unselected revisions are never
marked superseded. History is append-only (per-intake `sequence` + `previous_selection_id`; current = highest
sequence, derived — no `is_current`, no timestamps); identity derives from SHA-256 of `(intake, kind,
revision-or-none, sequence)`; the normative replay matrix holds (same target → reused, changed target → append
with the superseded state reported; near-concurrent identical converge, divergent conflict explicitly). **New**
selection requires write-time eligibility (revision + §19 generation binding; parent = the intake's current Raw
selection; candidate's current §18 authority = Accepted; no `--force`); **existing** selection is never
retro-judged — a later Reject or Raw switch makes it *inapplicable* (`candidate_not_accepted` /
`parent_raw_transcript_not_current`) without any history mutation, auto-fallback, or corruption finding. The
resolver returns raw (no history) / raw (explicit fallback) / corrected (applicable) / selected-but-inapplicable
with a reason — never a silent fallback; no existing downstream consumer is switched in this slice.

**Reuse investigation (GOAL-011 §13):** the legacy v9 `TranscriptCurrentSelection` (§4.8) requires an
applicability evaluation + old-review-path decision/item/reference + RUNNING execution and cannot represent Raw
fallback — not reusable for the §13–§19 chain (it remains untouched for its own path). The §16/§18 append-only
idiom, `HumanActorReference`, the intake context, and the §19 generation lineage are reused; only the additive
v37 table and the resolver are new. **Architect Decision judged not required:** the owner (intake context) is
conservatively determined by the §16 precedent; fallback is representable without a fake revision; selected-vs-
applicable resolves the later-Reject/Raw-switch tensions per the goal's own normative defaults; nothing is
weakened and future downstream integration remains fully open. Every released version v1..v36 chains single-step
to v37 preserving all rows; downgrade/direct-skip/unsupported-target rejected. Read-only validation gains
`corrected_revision_selections` checks (dangling intake/revision, kind/revision disagreement, context mismatch
via generation lineage, non-contiguous sequence, broken supersession) — integrity only, never flagging a
later-Rejected selected revision (tested healthy). One CLI (`lectureos.corrected_selection_cli` with
`select`/`fallback`/`status`/`history`/`resolve`, no `--force`) derives context from the revision, distinguishes
all states, and exits 0/1 leaving the repository unchanged on failure. A deterministic demo
(`lectureos.corrected_selection_demo`) with a golden proves the §63–§67 scenarios. The complete 2188-test suite
passes. Downstream resolver integration, ranking/recommendation, automatic selection, multi-candidate revisions,
revision chaining, and review UI remain later, separately-gated milestones and are out of scope.

## Effective Transcript Consumption Boundary (First Slice, 040 §21 / GOAL-012)

- Blueprint: approved `docs/040_TRANSCRIPT_PIPELINE.md §21` / `patches/PATCH-0028`
- Status: **COMPLETE**
- Selected persistence: additive SQLite schema **v38** (one insert-only table `effective_transcript_consumptions`)
- Commit: `feat: add effective transcript consumption boundary with manifest consumer`
- Immediate next milestone: switch one real downstream operation (transcript validation, subtitle preparation,
  review preparation, or export) to consume this boundary — product-gated, deferred

This milestone establishes the first **Effective Transcript Consumption Boundary** (040 §21 / PATCH-0028,
GOAL-012): the shared application boundary through which downstream transcript-derived operations acquire one
immutable transcript source. Five distinctions are preserved: current authority ≠ consumed source ≠ historical
binding lineage ≠ binding currentness ≠ repository integrity. All effective-source determination flows through
the **sole §20 resolver** (extended additively to expose the authority record identities it observed — no new
resolution meaning); no consumer duplicates selection/acceptance/parent/fallback logic. Acquisition validates
consumability (no current Raw selection → explicit failure; selected-but-inapplicable corrected revision →
explicit refusal with the resolver's reason — **never a silent Raw fallback**) and loads the ordered canonical
`TranscriptSegment` snapshot **by immutable resolved source identity**, never back through current authority, so
mixed-source snapshots are impossible; text, timing, speaker, `replaces_segment_id` replacement lineage, and
provider/human provenance pass through untouched, and the §19 `content_fingerprint_for` is reused verbatim.

The persisted **consumption binding** pins one consumer to one exact source: deterministic identity
`transcript-consumption:<sha256(consumer kind, intake, source kind, exact source identity)>`; the row records
the exact source and Raw parent, the observed raw/corrected selection authority (no-history and explicit
fallback remain distinguishable), and the deterministic manifest (segment count + fingerprint). Replay: same
consumer + same source → reused (UNIQUE replay anchor, converge-on-collision); different source → distinct
binding; same content under different source entities stays distinct; fingerprint disagreement is an explicit
conflict. Later authority changes (Reject, Raw switch, selection change, fallback) never rewrite, delete, or
reinterpret a binding — currentness is **derived** (`current` / `stale_due_to_raw_selection_change` /
`stale_due_to_corrected_selection_change` / `stale_due_to_selected_revision_inapplicability` / `unresolvable`),
never a stored flag, and no automatic reprocessing/deletion/switching exists.

**First-consumer decision (GOAL-012 §7):** the preferred existing candidates — the transcript
validation/readiness boundary and the subtitle transcript intake — live on the legacy §4.6–§4.8 path (legacy
`TranscriptCurrentSelection`, ApplicabilityEvaluation, ReviewItem/CandidateReference, RUNNING unit executions)
and cannot join the §13–§20 chain without fabricated execution machinery; both remain untouched. The bounded
first consumer is therefore the neutral deterministic **consumption manifest**
(`transcript_consumption_manifest`, the only member of `SUPPORTED_CONSUMER_KINDS`), whose persisted output is
the binding itself; no ProcessingRun/DomainResult/Artifact/physical file is fabricated. **Architect Decision
judged not required:** the binding owner (consumer kind + intake context) follows the §16/§20 precedent,
persistence is justified by the goal's own criteria (replay, audit, non-reinterpretation, validation), result
identity depends on immutable source identity (not current selection), and both sources already share the
canonical segment snapshot. Every released version v1..v37 chains single-step to v38 preserving all rows;
downgrade/direct-skip/unsupported-target rejected. Read-only validation gains eight integrity-only
`CONSUMPTION_*` checks (dangling refs, kind/state disagreement, parent mismatch, observed-authority mismatch,
manifest recomputation) — staleness is deliberately never flagged (tested healthy after Reject + Raw switch).
One CLI (`lectureos.transcript_consumption_cli` with `resolve-input`/`consume`/`status`, no `--force`) and a
deterministic demo (`lectureos.transcript_consumption_demo`) with a byte-stable golden prove the §62–§65
scenarios. The complete 2250-test suite passes. Switching real downstream consumers, automatic staleness
reactions, additional consumer kinds, and merged/multi-source consumption remain later, separately-gated
milestones and are out of scope.

## Effective-Transcript Subtitle Candidate Generation (First Slice, 041 §15 / GOAL-013)

- Blueprint: approved `docs/041_SUBTITLE_PIPELINE.md §15` (E1…E14) / `patches/PATCH-0029`, cross-referenced by
  `docs/040_TRANSCRIPT_PIPELINE.md §21 S3-15`
- Status: **COMPLETE**
- Selected persistence: additive SQLite schema **v39** (three insert-only tables
  `subtitle_effective_candidates` / `subtitle_effective_candidate_cues` /
  `subtitle_effective_candidate_cue_segments`)
- Commit: `feat: add effective transcript subtitle candidate generation`
- Immediate next milestone: bridge effective-source candidates into one downstream stage (review preparation
  with source currentness, or final-selection eligibility) — product-gated, deferred

This milestone implements the first canonical subtitle generation path of the effective-transcript contract
generation (041 §15 / PATCH-0029, GOAL-013). An **explicit** request acquires its transcript source **only**
through the GOAL-012 consumption boundary — `SUPPORTED_CONSUMER_KINDS` gains exactly one production kind,
`subtitle_candidate_generation`, and the persisted binding exists **before** generation, pinning the exact
immutable source (Raw or Corrected), Raw parent, authority provenance, ordered snapshot, and §19 fingerprint.
No current Raw selection or a selected-but-inapplicable corrected revision fails before any row is persisted —
never a silent Raw fallback; nothing generates automatically on authority changes.

The deterministic local generator (`deterministic_segment_passthrough` v1, parameters v1 — no
ProcessingRun/UnitExecution, per E6) emits one ordered cue per consumed segment with exact text, timing, and
single-segment lineage; corrected replacement cues reach the underlying Raw segment through the consumed
segment's immutable `replaces_segment_id`, human-correction provenance stays distinct from generator
provenance, and confidence is never fabricated. Candidate identity is deterministic and exact-source-sensitive
(consumer kind, intake, binding, source kind, exact source, generator kind/version/parameters); cue identity
is (candidate, ordinal, segment). Replay reuses (same binding + semantics), the Raw → Corrected → Raw round
trip reuses the original Raw candidate, byte-identical content under different source entities stays distinct,
near-concurrent identical requests converge on the UNIQUE replay anchor, and payload disagreement for one
identity is an explicit conflict. The whole graph — candidate, cues, lineage — commits in one atomic
transaction with full rollback (no partial candidate can exist). Currentness is derived through the GOAL-012
vocabulary and stale candidates remain immutable, historically valid records.

**Contract-generation isolation:** the legacy `subtitle_candidates` family (v12) and every legacy stage
(review, decisions, final selection, SRT export) are untouched — no reads, writes, migration, backfill, or
dual-write; the demo and tests assert zero rows appear in legacy/review/final/execution tables. Every released
version v1..v38 chains single-step to v39 preserving all rows. Read-only validation gains thirteen
integrity-only `EFFECTIVE_SUBTITLE_*` checks (dangling refs, binding mismatch, cue membership/ordinals/
lineage, snapshot membership, v1 passthrough content recomputation) — staleness is never corruption (tested
healthy after a later Reject). One CLI (`lectureos.effective_subtitle_cli` with
`generate`/`show`/`list`/`status`, no `--force`) and a deterministic demo
(`lectureos.effective_subtitle_demo`) with a byte-stable golden prove the Raw / replay / corrected-lineage /
round-trip / same-content-different-source / inapplicable scenarios. The complete 2298-test suite passes.
Downstream bridging (review, selection eligibility, export enforcement), additional generators or
configurations, automatic staleness reactions, and legacy candidate migration remain later, separately-gated
milestones and are out of scope.

## Effective-Source Subtitle Review Preparation (First Slice, 041 §15 downstream / GOAL-014)

- Blueprint: `docs/041_SUBTITLE_PIPELINE.md §15` E11–E14 downstream separation / `patches/PATCH-0029`
- Status: **COMPLETE**
- Selected persistence: additive SQLite schema **v40** (one insert-only table
  `subtitle_effective_review_subjects`)
- Commit: `feat: add effective subtitle review preparation`
- Immediate next milestone: Human Decisions over effective-source review subjects (reusing the §18 Human
  Authority idiom) — product-gated, deferred

This milestone implements the first downstream stage of the effective-transcript subtitle contract
generation (GOAL-014): an **explicit** request prepares one exact immutable `EffectiveSubtitleCandidate`
graph as an immutable **Review Subject** — the historical fact that this exact graph was presented for
review. Preparation is preparation only: it grants no authority (no Human Decision, reviewer,
approval/rejection/completion state, decision applicability, final-selection eligibility, or export
eligibility), touches no legacy review table (ReviewItem/CandidateReference/subtitle review — zero-row
asserted), and never prepares automatically on generation or authority changes.

The subject binds the exact graph twice: a truthful FK to the effective-source candidate representation
(never a generic candidate id) and a deterministic **candidate graph fingerprint** over the candidate's
immutable provenance and complete ordered cue set (identity, ordinal, text, timing, ordered source-segment
lineage) — an integrity anchor, never authority. Structural integrity (cue count, contiguous ordinals,
non-empty lineage) is verified before preparation; a broken graph refuses with nothing persisted.
**Recorded stale-candidate policy:** a structurally valid but source-stale candidate may be explicitly
prepared, returning derived stale currentness — historical inspectability ≠ current decision applicability.

Identity is deterministic (`subtitle-effective-review-subject:<sha256(kind, version, candidate, graph
fingerprint)>`); the replay anchor (`preparation_key` UNIQUE + UNIQUE(candidate, kind, version)) yields one
canonical subject per candidate and preparation contract; identical replay reuses, byte-identical content
under different candidates stays distinct, near-concurrent identical requests converge on the collision, and
a divergent payload for one anchor is an explicit conflict. Persistence is one atomic single-row insert with
full rollback. Currentness is derived only: the full GOAL-012/013 `ConsumptionCurrentness` vocabulary for
the candidate source plus `current`/`stale_due_to_candidate_source`/`unresolvable` for the subject; no
mutable flag exists and stale subjects remain valid history. Every released version v1..v39 chains
single-step to v40 preserving all rows (GOAL-013 and legacy rows unchanged). Read-only validation gains six
integrity-only `EFFECTIVE_REVIEW_SUBJECT_*` checks (dangling candidate, unsupported contract, duplicate
preparation, key/identity re-derivation, graph-fingerprint recomputation) — absence of a Human Decision and
candidate staleness are deliberately never flagged (tested healthy). One CLI
(`lectureos.effective_review_cli` with `prepare`/`show`/`list`/`status`, no `--force`, no fabricated review
status) and a deterministic demo (`lectureos.effective_review_demo`) with a byte-stable golden prove the
prepare/replay/corrected/round-trip/same-content/stale-history/invalid-graph scenarios. The complete
2341-test suite passes. Human Decisions, reviewer assignment, decision applicability, final-selection
eligibility, export enforcement, and additional preparation contract versions remain later,
separately-gated milestones and are out of scope.

## Effective-Source Subtitle Human Decisions (First Slice, GOAL-015)

- Blueprint: GOAL-009 Human Authority idiom over `docs/041_SUBTITLE_PIPELINE.md §15` review subjects; no new
  Blueprint PATCH required
- Status: **COMPLETE**
- Selected persistence: additive SQLite schema **v41** (one append-only table
  `subtitle_effective_review_decisions`)
- Commit: `feat: add effective subtitle human decisions`
- Immediate next milestone: final subtitle selection eligibility over accepted effective-source subjects, or
  the modified-subtitle authoring path implied by Modify — product-gated, deferred

This milestone introduces Human Authority for the effective-transcript subtitle contract generation
(GOAL-015), reusing the released GOAL-009 idiom exactly: an explicit command by a truthful
`HumanActorReference` records one immutable Accept/Reject/Modify judgment (the closed canonical
`DecisionKind` vocabulary) about one exact `EffectiveSubtitleReviewSubject`. Identity is
`(subject, kind, sequence)`; reviewer and rationale are provenance verified through the content
fingerprint. A request whose kind matches the current authority is **reused** idempotently (GOAL-009's
released repeated-intent rule — authority is a state, not a ledger; the (subject, kind, sequence) slot plus
fingerprint verification is the command identity, so no separate command-id exists); a changed judgment
**appends** with `previous_decision_id` supersession. The current decision is derived as the highest
sequence — never a latest-row heuristic, never a mutable flag. Near-concurrent identical commands converge
on the collision with payload verification; divergent payloads are explicit conflicts.

A decision records authority only: Accept creates no final selection or export eligibility, Reject deletes
and mutates nothing, Modify edits nothing (the modified-subtitle authoring path is a later goal). The
subject's candidate graph is re-verified against its immutable fingerprint anchor before any new authority; a
broken graph refuses with nothing persisted. **Recorded stale-subject policy:** explicit historical decisions
over structurally valid but source-stale subjects are allowed with derived staleness. Applicability is
derived, never stored, and separate from kind and integrity: `applicable` / `superseded` /
`stale_due_to_candidate_source` / `unresolvable` — reject and modify can be current and applicable. Every
released version v1..v40 chains single-step to v41 preserving all rows (GOAL-013/014 and legacy rows
unchanged; zero-row asserted). Read-only validation gains six integrity-only `EFFECTIVE_REVIEW_DECISION_*`
checks (dangling subject, unsupported kind, identity/fingerprint re-derivation, sequence contiguity, broken
supersession) — reject/modify/superseded/stale are deliberately never corruption (tested healthy). One CLI
(`lectureos.effective_decision_cli` with `decide`/`show`/`history`/`current`/`status`, no `--force`, no
fabricated workflow states) and a deterministic demo (`lectureos.effective_decision_demo`) with a byte-stable
golden prove the accept/replay/repeated-intent/reject/modify/supersession/stale-history/same-content/
invalid-graph scenarios. The complete 2385-test suite passes. Final-selection eligibility, export
enforcement, modified-subtitle authoring, annotations, reviewer assignment/authorization, and additional
decision contract versions remain later, separately-gated milestones and are out of scope.

## Effective Subtitle Final Selection Authority (First Slice, GOAL-016)

- Blueprint: GOAL-011 selection idiom + GOAL-015 Human Authority lineage over `docs/041_SUBTITLE_PIPELINE.md
  §15` subjects; no new Blueprint PATCH required
- Status: **COMPLETE**
- Selected persistence: additive SQLite schema **v42** (one append-only table
  `subtitle_effective_final_selections`)
- Commit: `feat: add effective subtitle final selection`
- Immediate next milestone: SRT export over the current applicable final selection (export eligibility
  enforcement + artifact generation for the effective-source generation) — product-gated, deferred

This milestone implements the explicit Final Selection boundary of the effective-transcript subtitle
contract generation (GOAL-016). **Accept ≠ Final Selection ≠ export.** Eligibility is derived and never
persisted: a NEW selection requires the subject's current decision to exist, be `accept`, and be applicable
(the conservative stale policy — reject/modify/superseded-accept/stale subjects are never eligible, while
existing selections remain immutable history). The explicit command binds, by truthful FKs, the exact
candidate, review subject, **supporting Accept decision observed at command time** (persisted, never
inferred later), and the explicit selector `HumanActorReference` (provenance, never authorization, never
inferred from the reviewer).

The selection scope is the intake (`TranscriptSourceIntakeId`); identity is
`(contract, intake, candidate, subject, supporting decision, sequence)` with selector/rationale as
fingerprint-verified provenance; current = highest per-intake sequence over `UNIQUE(intake, sequence)` with
validated supersession — the GOAL-011 rule. Replay follows the target-match idiom: the current selection
already binding the exact (candidate, subject, supporting decision) triple is reused idempotently; a
different candidate OR a new supporting Accept for the same subject appends new lineage (older selections
are never silently reused). Identical near-concurrent commands converge on fingerprint-verified collisions;
competing different selections raise an explicit conflict — an explicit Human command is never silently
discarded. Applicability is derived (`applicable`/`superseded`/`supporting_decision_superseded`/
`stale_due_to_candidate_source`/`unresolvable`) and separate from integrity.

Every released version v1..v41 chains single-step to v42 preserving all rows (GOAL-013/014/015 and legacy
rows unchanged; zero-row asserted for export/legacy tables). Read-only validation gains ten integrity-only
`EFFECTIVE_FINAL_SELECTION_*` checks (dangling refs, lineage mismatch, non-Accept support,
identity/fingerprint re-derivation, sequence contiguity, broken supersession) — superseded/stale
selections and later-superseded supporting decisions are deliberately never corruption (tested healthy).
One CLI (`lectureos.effective_selection_cli` with
`eligibility`/`select`/`show`/`history`/`current`/`status`, no `--force`, explicit "export state: not part
of this contract") and a deterministic demo (`lectureos.effective_selection_demo`) with a byte-stable
golden prove the eligibility/replay/blocking/new-lineage/supersession/stale-history/same-content/
invalid-graph/downstream-isolation scenarios. The complete 2428-test suite passes. SRT export and
enforcement, physical materialization, the modified-subtitle authoring path, and additional selection
contract versions remain later, separately-gated milestones and are out of scope.

## Effective Subtitle SRT Artifact Generation (First Slice, GOAL-017)

- Blueprint: released canonical SRT serialization (`application/srt_payload`, reused verbatim) + GOAL-016
  selection authority; no new Blueprint PATCH required
- Status: **COMPLETE**
- Selected persistence: additive SQLite schema **v43** (one insert-only table
  `subtitle_effective_srt_artifacts`)
- Commit: `feat: add effective subtitle SRT artifact generation`
- Immediate next milestone: physical SRT materialization for effective artifacts (paths, files, overwrite
  policy — reusing the legacy materialization precedent) — product-gated, deferred

This milestone implements the logical export boundary of the effective-transcript subtitle contract
generation (GOAL-017), completing the chain **consumption → generation → review → decision → selection →
logical export**. **Final Selection ≠ Artifact ≠ physical file.** Export eligibility is derived and never
persisted: only the current, applicable Final Selection of a scope may generate a new artifact
(`selection_not_found`/`selection_not_current`/`selection_not_applicable` blocking reasons); superseded or
stale selections are refused with nothing persisted, while existing artifacts remain immutable history whose
currentness is derived through the GOAL-016 applicability chain (`current`/`superseded_by_final_selection`/
`supporting_decision_superseded`/`stale_due_to_candidate_source`/`unresolvable`).

Serialization reuses the released pure primitives byte-for-byte (`canonical_srt` v1: numbering from 1 in
ordinal order, `HH:MM:SS,mmm` with ROUND_HALF_UP, LF endings, one blank line between blocks, single trailing
LF, exact text preservation, collapsed-duration and negative-time rejection, untimed cues refused). The
artifact binds, by truthful FKs, the exact final selection, candidate, and intake scope, stores the exact
canonical payload (TEXT — never a path, filename, URL, or materialized flag), and is identified
deterministically by (contract, exact selection, candidate, serializer contract, content fingerprint) —
content fingerprint alone is never identity, so byte-identical payloads under different selections stay
distinct. The replay anchor `UNIQUE(final_selection_id, serializer contract)` yields one canonical artifact
per selection; identical replay reuses; collisions converge only on complete payload equality, else an
explicit conflict; persistence is one atomic insert with full rollback.

Every released version v1..v42 chains single-step to v43 preserving all rows (GOAL-013…016 and legacy rows
unchanged; zero-row asserted for legacy export/materialization tables; no .srt file is ever written).
Read-only validation gains nine integrity-only `EFFECTIVE_SRT_ARTIFACT_*` checks (danglings, lineage
mismatch, unsupported serializer, identity/fingerprint re-derivation, cue-count mismatch, and byte-identical
reserialization from the bound cue graph via the shared pure serializer) — superseded/stale artifacts and
missing materialization are deliberately never corruption (tested healthy). One CLI
(`lectureos.effective_srt_cli` with `eligibility`/`generate`/`show`/`content`/`list`/`status`, no
`--force`, explicit materialization/path "not part of this contract") and a deterministic demo
(`lectureos.effective_srt_demo`) with a byte-stable golden (including the exact SRT payload) prove the
export/replay/superseded-block/distinct-artifact/same-content/invalid-graph/physical-isolation scenarios.
The complete 2468-test suite passes. Physical materialization, delivery, export-enforcement workflows,
and additional serializer versions remain later, separately-gated milestones and are out of scope.

## Effective SRT Physical Materialization (First Slice, GOAL-018)

- Blueprint: the released record-first materialization discipline (044 §17 / PATCH-0007) and the hardened
  released local writer, applied to GOAL-017 logical artifacts; no new Blueprint PATCH required
- Status: **COMPLETE**
- Selected persistence: additive SQLite schema **v44** (two insert-only tables
  `subtitle_effective_srt_materializations` / `subtitle_effective_srt_materialization_outcomes`)
- Commit: `feat: add effective subtitle physical materialization`
- Immediate next milestone: the effective-source pipeline is complete through a user-visible `.srt` file —
  subsequent goals should move beyond subtitle generation itself (delivery/publication workflows or broader
  system capabilities)

This milestone implements the physical materialization boundary of the effective-transcript subtitle
contract generation (GOAL-018), completing the pipeline end-to-end: **effective transcript → candidate →
review subject → Human Decision → final selection → logical SRT artifact → physical `.srt` file**.
**Artifact ≠ Materialization ≠ delivery.** The released record-first discipline is reused truthfully: the
immutable intent (PENDING) is durable before any file write, the immutable terminal outcome
(MATERIALIZED | FAILED) after; state is always derived; a dangling PENDING (crash residue) is completed —
never duplicated — by the next explicit request; collisions, containment escapes, and I/O failures are
honest FAILED outcomes. The hardened released writer is reused unchanged (approved absolute root, symlink
rejection, containment, atomic temp-file discipline, identical-bytes idempotence, different-bytes refusal),
extended additively with one explicit ``replace`` used solely for an explicit ``overwrite=True`` request.

Identity is deterministic — `(artifact, relative location, per-pair sequence)`; the relative location is
write provenance, never artifact identity; the recorded payload fingerprint always equals the immutable
artifact's fingerprint (validated). Replay reuses without rewriting when the latest act is MATERIALIZED and
the file still holds the exact canonical bytes (UTF-8, LF, no BOM); an existing different file refuses by
default; explicit overwrite and post-deletion re-realization append new sequence events; deleted or
diverged physical files never mutate any record and are never corruption (tested healthy). Every released
version v1..v43 chains single-step to v44 preserving all rows; legacy materialization is untouched
(zero-row asserted). Read-only validation gains six integrity-only `EFFECTIVE_SRT_MATERIALIZATION_*`
checks (dangling artifact, payload-fingerprint disagreement, identity re-derivation, per-pair sequence
contiguity, broken supersession, orphan outcome). One CLI (`lectureos.effective_materialize_cli` with
`materialize`/`show`/`status`/`list`; FAILED outcomes exit 1 as honest records) and a deterministic demo
(`lectureos.effective_materialize_demo`) with a byte-stable golden prove the ten GOAL-018 scenarios. The
complete 2506-test suite passes. Delivery, publication, URL generation, and archive management remain
later, separately-gated milestones and are out of scope.

## Explicit Effective SRT Delivery (First Slice, GOAL-019)

- Blueprint: the released record-first side-effect discipline (044 §17 / PATCH-0007) and the hardened
  released local writer, applied as an outbound delivery boundary over GOAL-018 materializations; no new
  Blueprint PATCH required
- Status: **COMPLETE**
- Selected persistence: additive SQLite schema **v45** (two insert-only tables
  `subtitle_effective_srt_delivery_intents` / `subtitle_effective_srt_delivery_outcomes`)
- Commit: `feat: add effective subtitle delivery`
- Immediate next milestone: outbound movement of the finished `.srt` is now explicit and auditable —
  subsequent goals may add publication/acknowledgement semantics as separately-gated contracts, or return
  to broader system capabilities (e.g. the Lecture Intelligence pipeline)

This milestone implements the explicit delivery boundary of the effective-transcript subtitle contract
generation (GOAL-019): one explicit request records that one exact successful physical Materialization's
bytes were copied to one exact destination beneath an explicitly supplied approved Delivery Root, through
one delivery mechanism (`local_copy`, contract `subtitle_effective_srt_delivery` v1), with one honest
terminal outcome. **Artifact ≠ Materialization ≠ Delivery ≠ Publication.** Delivery never regenerates SRT
content and never mutates Artifact or Materialization records; success never implies publication, a URL,
public availability, or recipient acknowledgement — none exist in this contract.

Eligibility is derived, never persisted: MATERIALIZED state, structurally valid artifact lineage, and a
source file whose bytes verify against the artifact's content fingerprint; superseded/stale artifacts
remain deliverable (historical operability). Source-side defects block **before** any intent is persisted;
the immutable intent is durable before the destination write; DELIVERED is recorded only after
re-verifying the destination bytes; destination-side failures are honest FAILED outcomes with stable
categories; a crash residue is an honest dangling PENDING closed only by explicit reconciliation
(observation only — matching → DELIVERED, missing/different → honest FAILED; never a write, never during
repository validation). Identity is deterministic over (contract, materialization, artifact, delivery
kind, destination location, expected fingerprint, per-pair sequence, overwrite policy); append-only
contiguous sequences with validated supersession; near-concurrent identical requests converge through the
durable intent slot and divergent collisions raise an explicit conflict. Exact replay reuses without
rewriting; default no-overwrite preserves different destination bytes as FAILED history; explicit
overwrite appends a NEW attempt; deleted destinations never mutate history and re-deliver as the next
attempt. The GOAL-018 hardened writer is reused with one additive observational `path_of` (aliasing
rejection, distinct path reporting) — no safety property weakened. Every released version v1..v44 chains
single-step to v45 preserving all rows; legacy tables are untouched. Read-only validation gains ten
integrity-only `EFFECTIVE_SRT_DELIVERY_*` checks; PENDING/FAILED/missing-file states are never corruption.
One CLI (`lectureos.effective_deliver_cli` with `eligibility`/`deliver`/`show`/`status`/`list`/
`reconcile`; FAILED outcomes exit 1 as honest records) and a deterministic demo
(`lectureos.effective_deliver_demo`) with a byte-stable golden prove the fourteen GOAL-019 scenarios
(56 focused new tests). The complete 2562-test suite passes. Publication, URLs, network transfer, and
recipient acknowledgement remain later, separately-gated milestones and are out of scope.

## Effective SRT Publication Authority (First Slice, GOAL-020)

- Blueprint: the released Human Authority pattern (GOAL-009/GOAL-015) and the released append-only
  per-scope authority idiom (GOAL-011/GOAL-016), applied over GOAL-019 deliveries; no new Blueprint
  PATCH required
- Status: **COMPLETE**
- Selected persistence: additive SQLite schema **v46** (one append-only table
  `subtitle_effective_srt_publications`)
- Commit: `feat: add effective subtitle publication authority`
- Immediate next milestone: the effective-source subtitle pipeline now ends in explicit, auditable
  publication authority with derived availability — subsequent goals may serve availability
  externally (a deliberately separate, network-facing contract) or return to broader system
  capabilities (e.g. the Lecture Intelligence pipeline)

This milestone implements explicit Publication and Availability Authority over successfully
delivered effective-source subtitles (GOAL-020). One explicit Human command (`publish` targeting
one exact DELIVERED delivery, or `withdraw` for an intake scope with publication history) appends
one immutable authority record (contract `effective_srt_publication` v1); Current Publication is
derived per intake as the highest valid sequence over the validated supersession chain, and
Availability is derived separately (`not_published` / `available` / `withdrawn` / `not_observed` /
`destination_missing` / `destination_mismatch` / `unresolvable`). **Delivery ≠ Publication ≠
Availability ≠ network access**: no URL, no network operation, no file write, no recipient
acknowledgement, no mutable `is_published` flag.

Eligibility is derived, never persisted: a repository-proven DELIVERED record with coherent
lineage; when a Delivery Root is supplied the destination must currently match (missing/diverged
bytes block a NEW publish), while historical publications stay immutable when files later change —
availability alone derives the loss. Stale/superseded artifacts' deliveries remain publishable
(historical operability). Identity is deterministic over (contract, intake scope, kind, exact
target | null, sequence); publisher and rationale are fingerprint-verified provenance, never
identity. Repeated intent follows GOAL-009: the same target — even by another actor — converges on
the established authority state preserving first-establishing provenance; different targets,
withdrawals, and re-publications append; withdraw deletes nothing anywhere. Near-concurrent
identical commands converge through the durable slot; divergent commands (publish-vs-withdraw,
competing targets) raise an explicit conflict — never silent loss. Every released version v1..v45
chains single-step to v46 preserving all rows; artifact/materialization/delivery/legacy rows are
untouched. Read-only validation gains nine integrity-only `EFFECTIVE_SRT_PUBLICATION_*` checks;
withdrawals, superseded history, and missing destinations are never corruption and validation never
reads the filesystem. One CLI (`lectureos.effective_publish_cli` with `eligibility`/`publish`/
`withdraw`/`show`/`history`/`current`/`availability`/`status`) and a deterministic demo
(`lectureos.effective_publish_demo`) with a byte-stable golden prove the fourteen GOAL-020
scenarios (44 focused new tests). The complete 2606-test suite passes. Public URLs, download
endpoints, network transfer, recipient models, scheduling, and automatic publication remain later,
separately-gated milestones and are out of scope.

## Effective Subtitle Pipeline v1 Release Closure (GOAL-021)

- Blueprint: release closure over the released GOAL-013…GOAL-020 contracts; no new Blueprint PATCH
  required and no new product capability added
- Status: **COMPLETE — Effective Subtitle Pipeline v1 Complete**
- Schema: unchanged (**v46**; no release persistence added)
- Commits: `test: add effective subtitle v1 release acceptance`,
  `docs: close effective subtitle pipeline v1`
- Immediate next epic: **Lecture Intelligence** (docs/042 / PATCH-0009 analysis-input eligibility) —
  the effective subtitle pipeline is complete and network-facing serving remains a deliberately
  deferred boundary

This milestone closes GOAL-013…GOAL-020 as one coherent released system rather than a sequence of
individually passing features. It adds: one connected production-service release acceptance suite
(`tests/test_effective_subtitle_pipeline_release.py`, 12 tests — typed lineage across all eight
stages, exact-byte SRT verification end to end, full-pipeline exact replay with zero new rows,
reject/modify blocking downstream authority, new-Accept lineage, candidate replacement with
immutable superseded history, physical/destination deletion preserving history, withdraw/republish
append-only, restart reconstruction of every derived state, healthy full-pipeline validation, and
cross-stage corruption detection); one deterministic release demo
(`lectureos.effective_subtitle_release_demo`) with a byte-stable machine-path-free golden; a
deterministic release manifest (`examples/effective-subtitle-v1/release-manifest.json`: goals,
schema range v39→v46, stages/tables/services/CLIs, contract kinds/versions, authority and derived
state vocabularies, deferred boundaries); and the canonical release document
(`implementation/111_EFFECTIVE_SUBTITLE_PIPELINE_V1_RELEASE.md`) with the stage/contract/identity/
authority maps, validator inventory, concurrency and side-effect audits, legacy isolation, and
explicit v1 boundary (no HTTP/URL/access control/acknowledgement/frontend/orchestration/Lecture
Intelligence). One documentation drift was corrected (README no longer describes materialization as
a future goal). No release tag was created — the repository has no tag policy. The complete
2622-test suite passes (16 new release tests).

## Derived Lecture Analysis Input Eligibility (First Slice, GOAL-022)

- Blueprint: `docs/042` §5/§5.1 + `PATCH-0009` (042 Milestone 1, Confirmed), over the released
  040 §20 effective-transcript authority; no new Blueprint PATCH required
- Status: **COMPLETE**
- Selected persistence: **none** — eligibility is derived only; schema unchanged (**v46**)
- Commit: `feat: add lecture analysis input eligibility`
- Immediate next milestone: Explicit Lecture Analysis Input Admission — revalidate eligibility and
  persist one immutable, provenance-bearing Eligible Analysis Input record for the effective
  generation, separate from Analysis Execution

This milestone resumes the Lecture Intelligence pipeline with its first executable contract for the
effective-transcript generation: `LectureAnalysisInputEligibilityService.evaluate(intake_id)`
derives whether one intake's current effective transcript authority is admissible as an analysis
input. Per the confirmed 042 §5.1 admission authority (the validated selected Corrected
Transcript + Source Timeline + Source Media reference), eligibility requires the §20 resolver to
return a current **applicable corrected revision** with a complete non-empty snapshot; raw-only
authority and explicit raw-fallback selections are honest ineligible states, inapplicable
selections surface the canonical resolver's reason (never a silent fallback), and only current
authority is admissible (no historical admission). The closed blocking vocabulary is
`intake_not_found` / `no_current_raw_transcript` / `corrected_transcript_not_selected` /
`corrected_selection_not_applicable` / `transcript_content_empty` (conservative non-empty-content
rule only — no invented token/duration/timing minimums). The result exposes the exact lineage a
later admission would bind (intake, source media, corrected revision, parent raw transcript,
observed selections, released §19 content fingerprint reused verbatim); one evaluation resolves
authority exactly once and loads snapshots by immutable identity (snapshot-coherent), and the
result is advisory — admission must revalidate (documented TOCTOU boundary). Normal ineligibility
never throws; integrity failures raise and are never concealed. Nothing is persisted anywhere
(restart-identical results; legacy `eligible_analysis_inputs` — the released execution-coupled
042 §5.1 implementation for the legacy generation — stays untouched at zero rows, classified and
documented). One CLI (`lectureos.analysis_input_eligibility_cli evaluate`; eligible exit 0,
ineligible exit 1) and a deterministic demo (`lectureos.analysis_input_eligibility_demo`) with a
byte-stable golden prove the ten GOAL-022 scenarios (20 focused new tests). The complete
2642-test suite passes; Effective Subtitle Pipeline v1 and all transcript contracts are
unchanged.

## Explicit Lecture Analysis Input Admission (First Slice, GOAL-023)

- Blueprint: `docs/042` §5.1 + `PATCH-0009` (042 Milestone 1, Confirmed) — the durable half for
  the effective-transcript generation; no new Blueprint PATCH required
- Status: **COMPLETE**
- Selected persistence: additive SQLite schema **v47** (one append-only table
  `lecture_analysis_input_admissions`)
- Commit: `feat: add explicit lecture analysis input admission`
- Immediate next milestone: the first analysis capability over admitted inputs — 042's later
  milestones (segmentation/finding foundations, §7.1/§8.1) remain product-gated and need gate
  evaluation before implementation

This milestone completes 042 Milestone 1 for the effective-transcript generation:
`LectureAnalysisInputAdmissionService.admit(intake_id)` revalidates the GOAL-022 derived
eligibility at command time (closing its advisory/TOCTOU boundary — a prior result is never
trusted; ineligible intakes refuse before persistence) and appends one immutable, identity-owning,
provenance-bearing analysis input record binding the exact authority snapshot: intake, source
media, current applicable corrected revision, parent raw transcript, both observed selection
records, the released §19 content fingerprint, and the segment count. Identity follows the
released GOAL-012 binding rule — derived from the exact immutable source only (contract, intake,
corrected revision); same-authority re-admission converges idempotently (near-concurrent commands
and returning authority included), a changed authority appends a NEW record, prior records remain
valid immutable history (append-only, no update/delete), and fingerprint divergence is an explicit
integrity conflict. `authority_match` derives (never stores) current/superseded/ineligible
standing. No wall-clock, path, or rowid participates; no Analysis Run, ProcessingRun, Finding, or
AI exists. Every released version v1..v46 chains single-step to v47 preserving all rows; the
legacy execution-coupled `eligible_analysis_inputs` contract stays untouched at zero rows.
Read-only validation gains six integrity-only `LECTURE_ANALYSIS_ADMISSION_*` checks (superseded
admissions are never corruption). One CLI (`lectureos.analysis_input_admission_cli` with
`admit`/`show`/`status`/`list`) and a deterministic demo (`lectureos.analysis_input_admission_demo`)
with a byte-stable golden prove the eight GOAL-023 scenarios (38 focused new tests). The complete
2680-test suite passes; the subtitle pipeline and all transcript contracts are unchanged.

## Analysis Finding Application Foundation — Effective-Transcript Generation (First Slice, GOAL-025)

- Blueprint: `docs/042` §8.2 + `PATCH-0030` (D-1…D-12, Confirmed), over the released GOAL-023
  durable analysis input; the canonical Finding record contract is inherited unchanged from
  `docs/042` §8.1 / `PATCH-0010`
- Status: **COMPLETE**
- Selected persistence: additive SQLite schema **v48** (one append-only table
  `lecture_analysis_findings`)
- Commit: `feat: add effective analysis finding foundation`
- Immediate next milestone: `042 §7.1` Lecture Segmentation and `042 §9.1` Edit Candidate still
  carry their legacy-generation admission boundaries and were deliberately not re-scoped by
  PATCH-0030 (D-12); each needs its own targeted generation-scope PATCH before implementation

This milestone opens Analysis itself for the effective-transcript generation:
`LectureAnalysisFindingService.admit(...)` admits one provider-independent finding payload
against **exactly one** immutable `LectureAnalysisInputAdmission` and appends one immutable,
identity-owning, provenance-bearing canonical Finding. Per PATCH-0030 D-3 the anchor's authority
standing is **re-derived at command time** through the released GOAL-023 `authority_match` (no
authority resolver is reimplemented) and only `current` admits;
`superseded_by_authority_change` and `current_authority_ineligible` are explicit refusals, and a
missing or malformed reference is refused before standing is evaluated — never a fourth standing
value. Upstream provenance is obtained *through* the anchor and deliberately not duplicated: the
row carries no intake, source media, corrected revision, or fingerprint column. Finding Type
reuses the released `^[a-z][a-z0-9_]*$` open Application-owned token rule (no closed enum, no
LI-001…LI-012 taxonomy, no alias mapping or case folding); evidence is required, stored verbatim,
and participates in identity; confidence and uncertainty are optional `[0, 1]` **recorded facts,
not identity**; the source range is optional, single, both-or-neither, finite, non-negative, and
`start <= end` (no media-duration or transcript-boundary validation is introduced — `042 §9.2`
forbids adding it at a Foundation). Identity is Application-owned and deterministic
(`lecture-analysis-finding:<sha256(contract kind/version, admission, type, evidence, range)>`);
no wall-clock, randomness, rowid, path, or provider identifier participates. Generation provenance
is execution-free and marker-free per D-6: **no ProcessingRun, ProcessingUnit, UnitExecution,
RUNNING state, or DomainResult is created** (test-asserted, including an unchanged upstream
DomainResult count). Exact replay converges (`reused`, no new row, near-concurrent inserts
included); a divergent recorded payload on an existing identity is an explicit conflict, never an
overwrite; a different anchor, type, evidence, or range is a distinct Finding. Existing Findings
are never mutated when authority changes, and returning authority restores admissibility on the
same canonical admission identity. Per D-11 the legacy `analysis_findings` relation is **not
reused** — its mandatory `source_input_id`/`run_id`/`unit_execution_id` could only be satisfied by
fabricating what D-6 prohibits — so persistence is a new additive v48 table; every released
version v1..v47 chains single-step to v48 preserving all rows, and the legacy execution-coupled
`analysis_findings` / `eligible_analysis_inputs` contracts stay untouched at zero rows.
Read-only validation gains seven integrity-only `LECTURE_ANALYSIS_FINDING_*` checks (a superseded
anchor is never corruption). One CLI (`lectureos.analysis_finding_cli` with
`admit`/`show`/`status`/`list`) and a deterministic demo (`lectureos.analysis_finding_demo`) with
a byte-stable golden prove the twelve GOAL-025 scenarios (79 focused new tests). The complete
2759-test suite passes; the subtitle pipeline, transcript contracts, and both legacy analysis
generations are unchanged.
