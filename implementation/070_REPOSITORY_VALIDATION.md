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
