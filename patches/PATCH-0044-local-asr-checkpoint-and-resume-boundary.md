# PATCH-0044

- Title: Local ASR Checkpoint and Resume Boundary (040 §15)
- Status: Proposed
- Priority: High
- Trigger: Architect Decision on the transcription loss recorded in
  `implementation/122_FULL_LENGTH_REAL_MEDIA_E2E_VALIDATION.md`; the gate evaluation `PATCH-0039`
  reserved for "incremental persistence of engine output"
- Created: 2026-08-07
- Target Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` (§15 gains CP-1…CP-21; forward notes on L-5,
  L-8, L-10, L-14; header amended)

---

## Status

**Proposed.** This document exists; `docs/040_TRANSCRIPT_PIPELINE.md` has not yet been amended. The
decisions below are not in force until the changes in *Required Blueprint Changes* are applied and
the *PATCH Acceptance Criteria* are verified.

It introduces **no schema change, no migration, no new aggregate, no new Product Domain record, no
new lifecycle, no new authority, and no new database table**. It changes no released contract's
meaning and invalidates no released record.

## Context

Full-length validation lost a complete transcription twice — 95 minutes and 85.5 minutes — because
the adapter writes nothing before admission and a post-execution rejection therefore discards
everything. `PATCH-0039` named this as needing its own gate evaluation rather than resolving it, and
this PATCH is that evaluation's outcome.

The question is narrow: **can the expensive engine output be preserved for resumption without
persisting an unvalidated canonical result?**

## Blueprint evidence

Three released sentences bound the answer, and two of them permit more than they first appear to.

**`§15` L-10 constrains the repository, not the filesystem.** It reads "adapter는 유효한 엔진 결과가
admit되기 전에는 **저장소에** 아무것도 쓰지 않는다" and then enumerates exactly what must not survive:
Provider Transcript Result, segment, Raw Transcript, admission, Source Media, intake. Every item is
repository state. Execution-local filesystem state was never within its prohibition.

**`§15` L-5 already contracts an isolated temporary workspace** for this adapter: "shell 없는
(argument-array) bounded runner로 **격리된 임시 workspace에만** 쓰고 성공·실패 모두 정리하며 원본을
덮어쓰지 않고, **확정 계약이 없는 한** 추출 audio를 Artifact로 persist하지 않는다." The discipline a
checkpoint must follow already exists in released text, and the clause's own "확정 계약이 없는 한"
anticipates that a contract may authorize more.

**But L-5 requires cleanup on both success and failure**, and a resumable checkpoint must by
definition survive failure. L-5 governs the *media preparation* workspace, a different artifact from
engine output, so the two are not the same thing — and this is the one place where a new contract
sentence is genuinely required rather than derived. CP-16 supplies it and L-5 stays untouched.

Supporting: `§15` L-8 fixes reuse-before-rerun; L-7 (as amended by `PATCH-0040` P-4) already encodes
provider, model, language, configuration and media into a deterministic reference and deliberately
excludes device and compute-type as operational; L-11 keeps the engine replaceable; L-14 defers
background job, durable queue, retry scheduler, **progress**, and cancellation; `§14` A-13 states
failure atomicity in the same repository-scoped terms as L-10.

## Engine resume capability — **Capability A**

The Architect Decision made automatic resume conditional on what the installed engine can actually
do. It was determined against the installed code and by execution, not from documentation.

`faster_whisper 1.2.0`'s `WhisperModel.transcribe` exposes **`clip_timestamps`** (default `"0"`), and
`audio` additionally accepts a `numpy.ndarray`. The installed source seeks to
`int(start_timestamp * frames_per_second)` and passes the clip map through
`restore_speech_timestamps`, which maps emitted segments **back onto the original media timeline**.

Executed against the preserved 55-second terminology fixture with `large-v3`, `language=ko`,
`condition_on_previous_text=False`:

| invocation | segments | first segment start |
|---|---|---|
| full slice | 9 | `0.00` |
| `clip_timestamps="30"` | 4 | **`30.00`** |

The offset run begins at the requested instant and reports **absolute** source-timeline timestamps.
This is **Capability A**: decoding can start at an explicit timestamp on the same source media, and
no timestamp re-basing by the adapter is required — which matters because re-basing would be a
timing transformation and L-6 requires the adapter to preserve returned order, timing and text
verbatim.

Automatic resume is therefore contracted here rather than deferred. CP-10 nonetheless keeps the
contract engine-conditional, because L-11 must stay true: a replacement engine without this
capability must still be usable.

## Decision

### Nature and responsibility

**CP-1 (Confirmed) — Scope.** This contract governs the `§15` local ASR adapter's execution
checkpoint. It changes no other stage, and `§14` admission is untouched in every respect.

**CP-2 (Confirmed) — A checkpoint is not canonical, and not a Product record.** It is not a
`ProviderTranscriptResult`, not a `RawTranscript`, not a canonical segment, and not a Product Domain
record of any kind. It carries **no canonical identity**, no lifecycle, no state machine, no Human
Authority, and no provenance role. It is durable evidence of one in-progress execution and nothing
more.

**CP-3 (Confirmed) — A checkpoint starts nothing.** Its existence does not make any downstream stage
reachable: no selection, correction, subtitle generation, review, export, or validation may consume
it, query it, or be triggered by it. Nothing outside the adapter may read it as transcript content.

**CP-4 (Confirmed) — Responsibility split.** **Application** owns the checkpoint's binding key, the
reuse/resume/fresh-run ordering, and the obligation to disclose which occurred. **Infrastructure**
owns storage, atomic write, locking, corruption detection, and cleanup. Application never dictates
the storage medium; Infrastructure never invents identity semantics.

### Binding and compatibility

**CP-5 (Confirmed) — Checkpoint key.**

```text
checkpoint_key = provider_result_ref  (L-7 v2: provider, model, language, configuration, media)
               + device
               + compute_type
               + engine library version
```

**CP-6 (Confirmed) — The asymmetry is deliberate and contracted.** L-7 excludes `device` and
`compute_type` from the provider-result reference because they serve the same request faster without
changing what was requested. A checkpoint is not a request; it is **the resumption of one physical
execution**, and numeric regime is part of that execution. Splicing `int8` output onto `float32`
output, or output from two engine library versions, would join segments produced under different
arithmetic. **The checkpoint key is therefore strictly narrower than the admission anchor**, and this
narrowing changes nothing about admission identity.

**CP-7 (Confirmed) — No cross-configuration reuse.** A different provider configuration, model,
language, media, device, compute type, or engine version yields a different key and therefore a
different checkpoint. A checkpoint is never resumed across any of them.

**CP-8 (Confirmed) — Reuse order.**

```text
1. canonical admitted Provider Result   (L-8 reuse-before-rerun)
2. compatible checkpoint resume
3. fresh execution
```

L-8 is first without exception: if a canonical result already exists for the anchor, no execution
starts and the checkpoint is not consulted. A checkpoint present alongside a canonical result is
**stale** and is a cleanup target, never a competing source.

### Storage and durability

**CP-9 (Confirmed) — Storage isolation.** Checkpoints live only beneath an **approved scratch root**,
never inside the repository or its canonical storage, and never inside the Source Media's directory.
A checkpoint holds, at minimum: semantic binding metadata, execution compatibility metadata, the
ordered completed segment records, and a means of determining safely where the complete records end.
Concrete filenames and layout are implementation detail; those four meanings are contract.

**CP-10 (Confirmed) — Durability is best-effort.** A checkpoint must survive process termination and
reboot, and that is why it is filesystem state rather than memory. It is **not** a guarantee: resume
is an optimization the operator may benefit from, never a promised product capability. Losing a
checkpoint is never an error condition, and a fresh execution is always a correct outcome.

**CP-11 (Confirmed) — Complete records only; no per-record fsync.** Segment records are written
append-oriented, and only **complete** records are ever reused. A truncated trailing record is
discarded on read. Per-record `fsync` is deliberately **not** required: it would impose a synchronous
disk round-trip per segment on a 2,500-segment run, and it is unnecessary because CP-10 makes
durability best-effort. An OS crash that loses the last unflushed records therefore yields an
**incomplete tail**, not corruption — the checkpoint remains usable and resume simply restarts from
an earlier instant. Metadata is replaced atomically, following the released
`LocalSrtFileWriter._atomic_write` idiom. Checkpoint writes are never joined to a repository
transaction.

### Resume

**CP-12 (Confirmed) — Resume is engine-conditional.** Automatic resume is available only where the
engine can begin decoding at an explicit instant on the same source media **and** report timestamps
on the original timeline. The installed `faster-whisper 1.2.0` satisfies this through
`clip_timestamps` (Capability A). Where an engine does not, **resume is not offered and a fresh
execution is the correct fallback** — the adapter never approximates a resume point, never re-bases
timestamps, and never invents a capability. This keeps L-11 true.

**CP-13 (Confirmed) — Checkpointed output is adopted, never re-verified by regeneration.** Resume
keeps the complete checkpointed segments as they are and generates only what follows the last
complete segment. LectureOS does **not** re-run a checkpointed region to compare it for equality:
ASR is non-deterministic — two runs over byte-identical audio produced 23 and 60 segments in
validation — so an equality contract would be unsatisfiable by construction and would make resume
permanently impossible.

**CP-14 (Confirmed) — Full revalidation, unchanged atomicity.** The checkpointed segments and the
newly generated segments are assembled into **one** Provider Result candidate and submitted to the
unchanged `§14` admission, which validates the **whole** result. There is no partial validation
credit, no per-segment admission, and no repository write before admission. The join between the
last checkpointed segment and the first new segment is verified there like any other boundary —
ordering, non-overlap under `PATCH-0039`'s representation tolerance, and structural validity.

**CP-15 (Confirmed) — Resume does not change final meaning.** A result assembled across a resume
derives the **same** admission identity from the same anchor as a result produced in one run, because
`§14` A-6 hashes the anchor and not the execution history. Resume is invisible to identity,
provenance, and every downstream contract.

### Lifecycle

**CP-16 (Confirmed) — Checkpoints survive failure; the L-5 workspace does not.** L-5's media
preparation workspace is cleaned up on success **and** failure and that rule is unchanged. An
execution checkpoint is a different artifact with a different purpose and **persists after engine
failure, admission failure, and process death**, because surviving failure is the entire point. The
two must not share a directory lifecycle.

**CP-17 (Confirmed) — Deleted on admission success.** Once the canonical Provider Result exists, the
checkpoint is deleted. Keeping it would leave a copy of canonical content outside the repository,
which is exactly the boundary CP-2 exists to hold.

**CP-18 (Confirmed) — Retained on failure.** Admission failure, validation refusal, conflict, engine
failure, and crash all retain the checkpoint. A refusal is recoverable and the expensive output stays
available for the next attempt.

**CP-19 (Confirmed) — Corruption is discarded, never partially trusted.** A checkpoint whose
metadata will not parse, whose binding or engine compatibility does not match, that holds a malformed
record, an impossible ordering, an invalid timestamp, or an unrecognized checkpoint version is **not
used for resume**. It is discarded or quarantined, the fact is stated explicitly, and a fresh
execution proceeds. This is **not** repository corruption and **not** a Provider Transcript Validation
Failure; the repository validator neither knows nor reports it.

**CP-20 (Confirmed) — Concurrency: one owner per key.** One execution at a time may own a checkpoint
key. A second execution for the same key **refuses explicitly** and reports the existing owner; it
never interleaves, never appends alongside, and never steals the lock. Ownership must be released
automatically when the owning process dies — an OS-level advisory lock is the intended mechanism
precisely because it needs no heartbeat, and **no background heartbeat, lease renewal, or job
lifecycle is introduced** (L-14 stays intact). If a chosen platform cannot provide automatic release,
stale-owner validation must be contracted explicitly before that platform is supported; it is not
inferred.

**CP-21 (Confirmed) — Bounded retention; observation without a progress API.** Checkpoints are not
retained indefinitely: retention is bounded and age-based collection is permitted. **No specific
duration is fixed here** — no product evidence sets one, and inventing a number would be a policy
decision without grounds — so the exact duration is **operational configuration** under an approved
scratch root. An operator may inspect a checkpoint, delete it, and force a fresh run, but must not
need to manage checkpoints for normal operation. The adapter must **disclose which of the three CP-8
paths occurred**. That disclosure is a statement about one command's outcome and is **not** a
progress API: percentage progress, background jobs, durable queues, retry schedulers, cancellation
and job lifecycle all remain deferred under L-14, and none may be inferred from a checkpoint's
existence.

## Non-goals

Not decided and each requiring its own gate evaluation: independent chunk ASR, parallel ASR, and
chunk-stitching product semantics; remote, shared, or multi-machine checkpoints; checkpoint migration
across providers or engines; background job, durable queue, retry scheduler, cancellation, automatic
retry, and progress percentage; VAD; hallucination filtering; subtitle readability; and `U+FFFD`
handling.

## Required Blueprint Changes

Applied to `docs/040_TRANSCRIPT_PIPELINE.md` only. No other Blueprint file requires amendment: no
released cross-reference to local ASR execution state exists elsewhere.

1. **Header** — Blueprint version and Last Updated advanced; `PATCH-0044` added to `Amended By`.
2. **§15** — a new subsection carrying CP-1…CP-21 and its own Canonical Invariants.
3. **§15 L-5** — released sentence kept verbatim; forward note distinguishing the media preparation
   workspace (cleaned up on success and failure) from the execution checkpoint (persists after
   failure), and stating they do not share a directory lifecycle.
4. **§15 L-8** — released sentence kept verbatim; forward note recording the CP-8 ordering.
5. **§15 L-10** — released sentence kept verbatim; forward note recording that its prohibition is
   repository state and that an execution-local checkpoint creates none of the enumerated records.
6. **§15 L-14** — released list kept verbatim; forward note recording that progress, background job,
   durable queue, retry scheduler and cancellation stay deferred and that a checkpoint is none of
   them.

## PATCH Acceptance Criteria

Verified against the Blueprint amendment, before this PATCH may be marked `Accepted`.

- [ ] §15 carries CP-1…CP-21 as written here.
- [ ] No released sentence in `docs/040` is deleted or rewritten; prior PATCH notes are treated as
      released text and are likewise untouched; verified line by line.
- [ ] L-5, L-8, L-10 and L-14 gain **additive forward notes only**.
- [ ] The checkpoint is stated non-canonical, without Product Domain identity, and unable to start
      any downstream stage.
- [ ] The Application/Infrastructure split is stated.
- [ ] The checkpoint key and its deliberate asymmetry with the admission anchor are stated.
- [ ] The CP-8 reuse order places canonical reuse first.
- [ ] Full `§14` revalidation and unchanged admission atomicity are stated.
- [ ] Resume is stated engine-conditional with fresh execution as the correct fallback.
- [ ] Retention is stated bounded with the duration left to operational configuration, and no
      specific number is invented.
- [ ] The change set contains no implementation, schema, migration, or test change.

## Implementation Requirements

Required validation for the implementing milestone. **Not satisfied by this PATCH.**

1. Checkpoint records are written beneath an approved scratch root and nowhere else; no repository
   row exists before admission.
2. The checkpoint key includes device, compute type and engine library version, and a mismatch in
   any of them prevents resume.
3. Canonical reuse is checked before any checkpoint is consulted.
4. A truncated trailing record is discarded and the remaining complete records are usable.
5. Resume begins after the last complete segment and produces absolute source-timeline timestamps.
6. The assembled result passes the unchanged `§14` admission, including the join boundary.
7. A result assembled across a resume derives the same admission identity as one produced in a
   single run.
8. The checkpoint survives engine failure and admission failure, and is deleted on admission success.
9. A corrupt or incompatible checkpoint is discarded with an explicit report and a fresh run
   proceeds; repository validation is unaffected.
10. A second execution for the same key refuses and names the existing owner; ownership is released
    when the owning process dies.
11. The command discloses whether it reused a canonical result, resumed, or ran fresh.
12. The complete test suite passes and the schema version is unchanged.

## Consequences

- `§15` gains a checkpoint contract; L-5, L-8, L-10 and L-14 gain forward notes; nothing else moves.
- One implementation slice adds the checkpoint. **No schema change is expected**: nothing about a
  checkpoint is repository state.
- A failed 90-minute transcription becomes resumable rather than lost, without weakening L-10, `§14`
  A-13, or admission atomicity in any respect.
- `PATCH-0039`'s reserved gate evaluation is discharged.
