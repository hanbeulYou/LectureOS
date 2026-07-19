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

The next and final durability Goal slice is the read-only Diagnostic Persistence
Assessment. Diagnostic canonical persistence remains deferred pending that
evidence review.
