# Repository Validation

- Status: Implementation Reference
- Scope: read-only repository integrity validation subsystem
- Blueprint impact: none (asserts existing invariants; introduces no product concept or contract)

## Philosophy

Repository validation verifies that persisted repository state is internally consistent **before** higher-level
workflows run. It is:

- **Read-only.** The validator opens the database with `PRAGMA query_only = ON` and issues only SELECT/PRAGMA
  statements. It never mutates repository state.
- **Independent of business logic.** It consumes the persisted store; it does not re-run the domain/application
  services that produced it, and it is not coupled into export or any other workflow. Future workflows simply
  invoke validation before execution.
- **Deterministic.** The same repository always yields the same diagnostics in the same order (diagnostics are
  sorted by `(code, location, message)`).
- **Additive.** The current checks are edit-export focused (the implemented MVP) plus a global foreign-key
  sweep; new checks for other pipelines can be added without changing the framework.

## Architecture

- `src/lectureos/validation/diagnostics.py` — `Severity`, `RepositoryHealth`, `Diagnostic`, `ValidationReport`.
- `src/lectureos/validation/repository_validator.py` — `validate_repository(connection)` and
  `validate_database(path)` (opens read-only, maps open failures to diagnostics), plus the individual checks.
- `src/lectureos/validate_cli.py` — the `lectureos.validate_cli` entry point.

The validator lives outside `application/` deliberately (validation is independent of business logic). It reads
the persisted store via SQL and never constructs or persists domain aggregates.

## Diagnostic format

Each diagnostic carries:

- `code` — a stable machine-readable identifier.
- `severity` — `info` | `warning` | `error`.
- `location` — typically `table:identity` or `table.column`.
- `message` — a human-readable explanation.

A `ValidationReport` carries the schema version, the number of objects checked, and the ordered diagnostics,
and derives `health` (`healthy` / `warnings` / `errors`) and `ok` (no errors).

## Exit codes (`lectureos.validate_cli`)

| Code | Health | Meaning |
| --- | --- | --- |
| `0` | healthy | no errors and no warnings |
| `1` | errors | one or more error diagnostics (repository is inconsistent) |
| `2` | warnings | warnings only, no errors |

## Diagnostic codes

| Code | Severity | Meaning |
| --- | --- | --- |
| `DATABASE_NOT_FOUND` | error | the database file does not exist |
| `DATABASE_UNREADABLE` | error | the file could not be read as a database |
| `SCHEMA_METADATA_MISSING` | error | no `schema_metadata`; not a LectureOS repository |
| `SCHEMA_VERSION_UNSUPPORTED` | error | schema version is outside the supported range |
| `FOREIGN_KEY_VIOLATION` | error | a foreign-key-constrained reference points at a missing row |
| `DANGLING_REFERENCE` | error | a non-foreign-key TEXT reference points at a missing target |
| `DOMAIN_RESULT_UPSTREAM_NONCONTIGUOUS` | error | DomainResult upstream ordinals are not a contiguous `0..n-1` sequence |
| `ASSEMBLY_EMPTY` | error | an Edit Export Assembly has no member representations |
| `ASSEMBLY_MEMBER_ORDINAL_NONCONTIGUOUS` | error | assembly member ordinals are not a contiguous `0..n-1` sequence |
| `ASSEMBLY_MEMBER_DUPLICATE` | error | a representation appears more than once in an assembly |
| `ASSEMBLY_MEMBER_TIMELINE_MISMATCH` | error | a member representation belongs to a different Source Timeline than the assembly |
| `ASSEMBLY_MEMBER_MEDIA_MISMATCH` | error | a member representation belongs to a different Source Media than the assembly |
| `ASSEMBLY_MEMBER_ORDER_NONCANONICAL` | warning | assembly member order is not the canonical ascending-identity order |
| `REPRESENTATION_KIND_MISMATCH` | error | a representation's decision kind disagrees with its approved decision |
| `REPRESENTATION_PROVENANCE_MISMATCH` | error | a representation's review/candidate/media/timeline lineage disagrees with its approved decision |
| `APPROVED_DECISION_KIND_INVALID` | error | an approved decision's kind is not a valid approving accept/modify aligned with its review |
| `APPROVED_DECISION_PROVENANCE_MISMATCH` | error | an approved decision's candidate disagrees with its review decision |
| `PROVIDER_TRANSCRIPT_ADMISSION_DANGLING_INTAKE` | error | an admission references a missing transcript source intake |
| `PROVIDER_TRANSCRIPT_ADMISSION_DANGLING_SOURCE_MEDIA` | error | an admission references a missing `source_media` record |
| `PROVIDER_TRANSCRIPT_ADMISSION_DANGLING_PROVIDER_RESULT` | error | an admission references a missing provider transcript result |
| `PROVIDER_TRANSCRIPT_ADMISSION_DANGLING_RAW_TRANSCRIPT` | error | an admission references a missing raw transcript |
| `PROVIDER_TRANSCRIPT_ADMISSION_PROVENANCE_DISAGREEMENT` | error | an admission's intake is not derived from its Source Media reference |
| `PROVIDER_TRANSCRIPT_ADMISSION_RAW_PROVIDER_DISAGREEMENT` | error | an admitted raw transcript and provider result provenance disagree |
| `PROVIDER_TRANSCRIPT_ADMISSION_SEGMENT_COUNT_DISAGREEMENT` | error | an admission's segment count disagrees with the raw transcript membership |
| `PROVIDER_TRANSCRIPT_ADMISSION_DUPLICATE_PROVIDER_RESULT` | error | a provider transcript result is admitted by more than one admission |
| `PROVIDER_TRANSCRIPT_ADMISSION_DUPLICATE_RAW_TRANSCRIPT` | error | a raw transcript is admitted by more than one admission |
| `RAW_TRANSCRIPT_SEGMENT_ORDINAL_NONCONTIGUOUS` | error | raw transcript segment ordinals are not a contiguous `0..n-1` sequence |
| `RAW_TRANSCRIPT_SELECTION_DANGLING_INTAKE` | error | a current-selection references a missing transcript source intake |
| `RAW_TRANSCRIPT_SELECTION_DANGLING_RAW_TRANSCRIPT` | error | a current-selection references a missing raw transcript |
| `RAW_TRANSCRIPT_SELECTION_LINEAGE_MISMATCH` | error | a selected raw transcript is not an admitted candidate of the selection's intake |
| `RAW_TRANSCRIPT_SELECTION_SEQUENCE_NONCONTIGUOUS` | error | an intake's selection sequences are not a contiguous `0..n-1` sequence |
| `RAW_TRANSCRIPT_SELECTION_BROKEN_SUPERSESSION` | error | a non-initial selection does not supersede its intake's immediately prior sequence |
| `CORRECTION_CANDIDATE_DANGLING_CANDIDATE` | error | a correction-candidate admission references a missing correction candidate |
| `CORRECTION_CANDIDATE_DANGLING_INTAKE` | error | a correction-candidate admission references a missing transcript source intake |
| `CORRECTION_CANDIDATE_DANGLING_RAW_TRANSCRIPT` | error | a correction-candidate admission references a missing raw transcript |
| `CORRECTION_CANDIDATE_DANGLING_SEGMENT` | error | a correction-candidate admission references a missing transcript segment |
| `CORRECTION_CANDIDATE_RAW_TRANSCRIPT_NOT_IN_INTAKE` | error | the target raw transcript is not an admitted Raw Transcript of the admission's intake |
| `CORRECTION_CANDIDATE_SEGMENT_NOT_IN_RAW_TRANSCRIPT` | error | the target segment does not belong to the target raw transcript |
| `CORRECTION_CANDIDATE_SOURCE_TEXT_DISAGREEMENT` | error | a candidate's source-text snapshot no longer matches the segment text |
| `CORRECTION_CANDIDATE_ADMISSION_LINEAGE_DISAGREEMENT` | error | an admitted candidate's transcript/segment disagree with its admission |
| `CORRECTION_CANDIDATE_EMPTY_PROPOSED_TEXT` | error | an admitted correction candidate has empty proposed text |
| `CORRECTION_DECISION_DANGLING_CANDIDATE` | error | a human decision references a missing correction candidate |
| `CORRECTION_DECISION_SEQUENCE_NONCONTIGUOUS` | error | a candidate's decision sequences are not a contiguous `0..n-1` sequence |
| `CORRECTION_DECISION_BROKEN_SUPERSESSION` | error | a non-initial decision does not supersede its candidate's immediately prior sequence |
| `CORRECTED_REVISION_DANGLING_REVISION` | error | a generation references a missing corrected transcript revision |
| `CORRECTED_REVISION_DANGLING_CANDIDATE` | error | a generation references a missing correction candidate |
| `CORRECTED_REVISION_DANGLING_DECISION` | error | a generation references a missing authorizing decision |
| `CORRECTED_REVISION_DANGLING_PARENT` | error | a generation references a missing parent raw transcript |
| `CORRECTED_REVISION_AUTHORIZING_DECISION_NOT_ACCEPT` | error | a generation's specific authorizing decision is not an Accept (the candidate's later/current authority is deliberately not checked) |
| `CORRECTED_REVISION_DECISION_CANDIDATE_MISMATCH` | error | a generation's authorizing decision does not belong to its candidate |
| `CORRECTED_REVISION_PARENT_MISMATCH` | error | a generated revision's parent disagrees with its generation record |
| `CORRECTED_REVISION_MEMBERSHIP_DISAGREEMENT` | error | a revision's membership disagrees with the generation's replaced/replacement segments |
| `CORRECTED_SELECTION_DANGLING_INTAKE` | error | a corrected-revision selection references a missing transcript source intake |
| `CORRECTED_SELECTION_DANGLING_REVISION` | error | a corrected-revision selection references a missing corrected revision |
| `CORRECTED_SELECTION_KIND_REVISION_DISAGREEMENT` | error | a selection's kind disagrees with the presence of a selected revision |
| `CORRECTED_SELECTION_CONTEXT_MISMATCH` | error | a selected revision's lineage does not belong to the selection's intake context |
| `CORRECTED_SELECTION_SEQUENCE_NONCONTIGUOUS` | error | an intake's selection sequences are not a contiguous `0..n-1` sequence |
| `CORRECTED_SELECTION_BROKEN_SUPERSESSION` | error | a non-initial selection does not supersede its intake's immediately prior selection |
| `CONSUMPTION_DANGLING_INTAKE` | error | a consumption binding references a missing transcript source intake |
| `CONSUMPTION_DANGLING_RAW_SOURCE` | error | a consumption binding references a missing parent raw transcript |
| `CONSUMPTION_DANGLING_REVISION_SOURCE` | error | a consumption binding references a missing corrected transcript revision |
| `CONSUMPTION_DANGLING_SELECTION` | error | a consumption binding references a missing raw/corrected selection authority record |
| `CONSUMPTION_SOURCE_KIND_DISAGREEMENT` | error | a binding's source kind, exact source identity, and resolution state disagree |
| `CONSUMPTION_PARENT_MISMATCH` | error | a corrected consumption's recorded Raw parent disagrees with the revision's immutable parent |
| `CONSUMPTION_AUTHORITY_MISMATCH` | error | a binding's observed selection provenance disagrees with its context or consumed source (staleness against *current* authority is deliberately never checked) |
| `CONSUMPTION_FINGERPRINT_MISMATCH` | error | a binding's persisted content manifest (fingerprint/segment count) does not match its bound immutable snapshot |
| `EFFECTIVE_SUBTITLE_DANGLING_INTAKE` | error | an effective subtitle candidate references a missing transcript source intake |
| `EFFECTIVE_SUBTITLE_DANGLING_BINDING` | error | an effective subtitle candidate references a missing consumption binding |
| `EFFECTIVE_SUBTITLE_DANGLING_RAW_PARENT` | error | an effective subtitle candidate references a missing parent raw transcript |
| `EFFECTIVE_SUBTITLE_DANGLING_REVISION` | error | an effective subtitle candidate references a missing corrected revision |
| `EFFECTIVE_SUBTITLE_SOURCE_KIND_DISAGREEMENT` | error | a candidate's source kind disagrees with its exact-source columns |
| `EFFECTIVE_SUBTITLE_BINDING_MISMATCH` | error | a candidate's context/source/snapshot facts disagree with its immutable consumption binding |
| `EFFECTIVE_SUBTITLE_CUE_COUNT_MISMATCH` | error | a candidate's cue set does not match its declared cue count |
| `EFFECTIVE_SUBTITLE_CUE_ORDINAL_NONCONTIGUOUS` | error | a candidate's cue ordinals are not a contiguous unique `0..n-1` sequence |
| `EFFECTIVE_SUBTITLE_ORPHAN_CUE` | error | a cue references a missing effective subtitle candidate |
| `EFFECTIVE_SUBTITLE_ORPHAN_CUE_SEGMENT` | error | cue source-segment lineage references a missing cue |
| `EFFECTIVE_SUBTITLE_CUE_WITHOUT_SOURCE_SEGMENT` | error | a cue has no source-segment lineage |
| `EFFECTIVE_SUBTITLE_CUE_SEGMENT_OUTSIDE_SNAPSHOT` | error | a cue's source segment does not belong to the candidate's bound source snapshot |
| `EFFECTIVE_SUBTITLE_CUE_CONTENT_MISMATCH` | error | a v1 passthrough cue's text or timing disagrees with its consumed source segment (staleness against current authority is deliberately never checked) |
| `EFFECTIVE_REVIEW_SUBJECT_DANGLING_CANDIDATE` | error | a review subject references a missing effective subtitle candidate |
| `EFFECTIVE_REVIEW_SUBJECT_UNSUPPORTED_PREPARATION` | error | a review subject records an unsupported preparation contract kind/version |
| `EFFECTIVE_REVIEW_SUBJECT_DUPLICATE_PREPARATION` | error | more than one review subject exists for one candidate and preparation contract |
| `EFFECTIVE_REVIEW_SUBJECT_KEY_MISMATCH` | error | a review subject's preparation key does not re-derive from its contract and candidate |
| `EFFECTIVE_REVIEW_SUBJECT_IDENTITY_MISMATCH` | error | a review subject's identity does not re-derive from its stored payload |
| `EFFECTIVE_REVIEW_SUBJECT_GRAPH_FINGERPRINT_MISMATCH` | error | a review subject's graph fingerprint does not match the bound candidate graph (absence of a Human Decision, reviewer, selection, or export is deliberately never flagged) |
| `EFFECTIVE_REVIEW_DECISION_DANGLING_SUBJECT` | error | a review decision references a missing effective review subject |
| `EFFECTIVE_REVIEW_DECISION_UNSUPPORTED_KIND` | error | a review decision records a kind outside accept/reject/modify |
| `EFFECTIVE_REVIEW_DECISION_IDENTITY_MISMATCH` | error | a review decision's identity does not re-derive from its subject, kind, and sequence |
| `EFFECTIVE_REVIEW_DECISION_FINGERPRINT_MISMATCH` | error | a review decision's content fingerprint does not match its stored payload |
| `EFFECTIVE_REVIEW_DECISION_SEQUENCE_NONCONTIGUOUS` | error | a subject's decision sequences are not a contiguous unique `0..n-1` sequence |
| `EFFECTIVE_REVIEW_DECISION_BROKEN_SUPERSESSION` | error | a non-initial decision does not supersede its subject's immediately prior decision (reject/modify kinds, superseded decisions, and stale subjects are deliberately never flagged) |
| `EFFECTIVE_FINAL_SELECTION_DANGLING_INTAKE` | error | a final selection references a missing transcript source intake |
| `EFFECTIVE_FINAL_SELECTION_DANGLING_CANDIDATE` | error | a final selection references a missing effective subtitle candidate |
| `EFFECTIVE_FINAL_SELECTION_DANGLING_SUBJECT` | error | a final selection references a missing effective review subject |
| `EFFECTIVE_FINAL_SELECTION_DANGLING_DECISION` | error | a final selection references a missing supporting decision |
| `EFFECTIVE_FINAL_SELECTION_LINEAGE_MISMATCH` | error | a final selection's candidate/subject/decision/scope lineage disagrees |
| `EFFECTIVE_FINAL_SELECTION_DECISION_NOT_ACCEPT` | error | a final selection's supporting decision is not an accept |
| `EFFECTIVE_FINAL_SELECTION_IDENTITY_MISMATCH` | error | a final selection's identity does not re-derive from its stored payload |
| `EFFECTIVE_FINAL_SELECTION_FINGERPRINT_MISMATCH` | error | a final selection's content fingerprint does not match its stored payload |
| `EFFECTIVE_FINAL_SELECTION_SEQUENCE_NONCONTIGUOUS` | error | an intake's final-selection sequences are not a contiguous unique `0..n-1` sequence |
| `EFFECTIVE_FINAL_SELECTION_BROKEN_SUPERSESSION` | error | a non-initial selection does not supersede its scope's immediately prior selection (superseded selections, stale sources, later-superseded supporting decisions, and the absence of any export are deliberately never flagged) |
| `EFFECTIVE_SRT_ARTIFACT_DANGLING_INTAKE` | error | an SRT artifact references a missing transcript source intake |
| `EFFECTIVE_SRT_ARTIFACT_DANGLING_SELECTION` | error | an SRT artifact references a missing final selection |
| `EFFECTIVE_SRT_ARTIFACT_DANGLING_CANDIDATE` | error | an SRT artifact references a missing effective subtitle candidate |
| `EFFECTIVE_SRT_ARTIFACT_LINEAGE_MISMATCH` | error | an SRT artifact's selection/candidate/intake lineage disagrees |
| `EFFECTIVE_SRT_ARTIFACT_UNSUPPORTED_SERIALIZER` | error | an SRT artifact records an unsupported serializer contract |
| `EFFECTIVE_SRT_ARTIFACT_IDENTITY_MISMATCH` | error | an SRT artifact's identity does not re-derive from its stored payload |
| `EFFECTIVE_SRT_ARTIFACT_FINGERPRINT_MISMATCH` | error | an SRT artifact's content fingerprint does not match its stored payload |
| `EFFECTIVE_SRT_ARTIFACT_CUE_COUNT_MISMATCH` | error | an SRT artifact's cue count does not match the bound candidate graph |
| `EFFECTIVE_SRT_ARTIFACT_RESERIALIZATION_MISMATCH` | error | a stored SRT payload does not reserialize byte-identically from the bound candidate graph (superseded/stale artifacts and missing physical materialization are deliberately never flagged) |
| `EFFECTIVE_SRT_MATERIALIZATION_DANGLING_ARTIFACT` | error | a materialization references a missing effective SRT artifact |
| `EFFECTIVE_SRT_MATERIALIZATION_FINGERPRINT_MISMATCH` | error | a materialization's payload fingerprint disagrees with its artifact |
| `EFFECTIVE_SRT_MATERIALIZATION_IDENTITY_MISMATCH` | error | a materialization's identity does not re-derive from its stored payload |
| `EFFECTIVE_SRT_MATERIALIZATION_SEQUENCE_NONCONTIGUOUS` | error | a (artifact, location) pair's materialization sequences are not contiguous |
| `EFFECTIVE_SRT_MATERIALIZATION_BROKEN_SUPERSESSION` | error | a non-initial materialization does not supersede its pair's immediately prior act |
| `EFFECTIVE_SRT_MATERIALIZATION_ORPHAN_OUTCOME` | error | a materialization outcome references a missing intent (PENDING intents, FAILED outcomes, and missing or diverged physical files are deliberately never flagged) |
| `EFFECTIVE_SRT_DELIVERY_DANGLING_MATERIALIZATION` | error | a delivery references a missing effective SRT materialization |
| `EFFECTIVE_SRT_DELIVERY_ARTIFACT_LINEAGE_MISMATCH` | error | a delivery's artifact lineage disagrees with its source materialization |
| `EFFECTIVE_SRT_DELIVERY_FINGERPRINT_MISMATCH` | error | a delivery's expected payload fingerprint disagrees with its artifact |
| `EFFECTIVE_SRT_DELIVERY_UNSAFE_LOCATION` | error | a delivery destination location is not a contained relative path |
| `EFFECTIVE_SRT_DELIVERY_IDENTITY_MISMATCH` | error | a delivery's identity does not re-derive from its stored payload |
| `EFFECTIVE_SRT_DELIVERY_SEQUENCE_NONCONTIGUOUS` | error | a (materialization, destination) pair's delivery sequences are not contiguous |
| `EFFECTIVE_SRT_DELIVERY_BROKEN_SUPERSESSION` | error | a non-initial delivery does not supersede its pair's immediately prior attempt |
| `EFFECTIVE_SRT_DELIVERY_ORPHAN_OUTCOME` | error | a delivery outcome references a missing intent |
| `EFFECTIVE_SRT_DELIVERY_UNSUPPORTED_FAILURE_CATEGORY` | error | a failed delivery outcome uses an unsupported failure category |
| `EFFECTIVE_SRT_DELIVERY_DELIVERED_FINGERPRINT_MISMATCH` | error | a delivered outcome's fingerprint disagrees with the intent's expected payload (PENDING intents, FAILED outcomes, and missing or diverged source/destination files are deliberately never flagged) |
| `MALFORMED_IDENTITY` | error | one or more rows have an empty or blank identity |

## Scope

Validation focuses on the edit-export pipeline (the implemented MVP) plus a global foreign-key sweep that
covers foreign-key-constrained references across all tables. It intentionally does not re-implement the
transcript/subtitle domain state machines; deeper per-pipeline semantic checks can be added additively as those
capabilities mature. The framework, diagnostic model, CLI, and exit-code contract are stable.

## Golden fixtures & tests

- `examples/repository-validation/expected/*.json` — deterministic golden reports, reproduced byte-for-byte by
  `tests/test_repository_validation_golden.py`.
- `tests/test_repository_validator.py`, `tests/test_validate_cli.py`,
  `tests/test_repository_validation_acceptance.py` — unit, CLI, and end-to-end coverage.
