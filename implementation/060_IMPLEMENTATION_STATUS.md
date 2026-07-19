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
- Status: **IN PROGRESS**
- Completed slices: Correction Application Composition Assessment; Correction
  Capability Contract; Correction Proposal Validation and Canonical Construction
- Immediate next slice: Atomic Correction Generation Persistence

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
