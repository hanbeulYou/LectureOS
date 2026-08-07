# Local ASR Execution Checkpoint and Resume

- Status: Implementation Reference
- Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` §15 CP-1…CP-21 / `PATCH-0044`
- Schema: unchanged (**v53**; no migration, no table, no column, no identity kind)
- Related: `122_FULL_LENGTH_REAL_MEDIA_E2E_VALIDATION.md`, `123_LOCAL_ASR_PROVIDER_CONFIGURATION.md`

## What it is

Durable, execution-local evidence of an in-progress ASR run, kept so a 90-minute transcription can be
continued instead of repeated. It is not a `ProviderTranscriptResult`, not a `RawTranscript`, not a
canonical segment, not a Product Domain record, and it starts no downstream stage (CP-2, CP-3).

Full-length validation lost a complete transcription twice — 95 and 85.5 minutes — because the
adapter writes nothing before admission. That cost is now recoverable without weakening the rule
that produced it.

## Why no schema change was needed

`§15` L-10 prohibits writing to the **repository** before admission and enumerates only repository
records. Execution-local filesystem state was never inside that prohibition, which is what makes a
checkpoint possible without touching admission atomicity, `§14` A-13, or the schema.

## Platform capability gate

CP-20 assumes the OS releases ownership when the owner dies, and the milestone verified that before
any code was written, with real subprocesses on Darwin 25.5.0:

| test | result |
|---|---|
| second acquirer while held | refused, `EAGAIN` (35) |
| after normal exit | acquired immediately |
| after `SIGKILL` | **acquired immediately, no stale-lock handling** |

`fcntl.flock(LOCK_EX \| LOCK_NB)` satisfies all three, so automatic resume is offered. Had it not,
CP-20 requires declining resume rather than inventing a stale-owner policy.

## Engine capability

`faster-whisper 1.2.0` exposes `clip_timestamps`, seeks to the requested frame, and restores emitted
timestamps onto the original media timeline (Capability A, verified in `PATCH-0044`). The adapter
therefore never re-bases a timestamp, which is what keeps L-6's verbatim-timing requirement intact.

## Structure

| file | role |
|---|---|
| `application/local_asr_checkpoint.py` | binding key, compatibility, discard reasons, execution mode, port |
| `infrastructure/local_asr_checkpoint_store.py` | directory, atomic metadata, append/recovery, `flock`, collection |
| `application/local_asr_transcription.py` | reuse → resume → fresh ordering, streaming record, assembly |
| `infrastructure/faster_whisper_engine.py` | `start_offset` → `clip_timestamps`; per-segment callback |
| `composition.py`, `local_asr_cli.py` | wiring, `--checkpoint-root`, `--force-fresh`, disclosure |

### Binding and the CP-6 asymmetry

```text
checkpoint_key = provider_result_ref + device + compute_type + engine_library_version
```

`§15` L-7 excludes device and compute type from the **admission** anchor because they serve the same
request faster. A checkpoint resumes **one physical execution**, so splicing `int8` output onto
`float32` output — or across engine library versions — would join segments produced under different
arithmetic. The key is deliberately narrower than the anchor, and tests assert both halves: the key
moves with those fields and the provider-result reference does not.

The key is hashed before it becomes a path. A `provider_result_ref` contains `:` and `=` and is
caller-influenced, so a SHA-256 id removes every traversal and injection surface while the original
values stay recoverable from the stored metadata.

## Three defects the tests did not catch

Each passed the full unit suite and was found only by running the real experiment. They are recorded
because the pattern matters more than the fixes: every one lived in a layer the tests did not reach.

**1 — Recording was not streaming.** The engine runner materialized the whole generator before
returning, so the checkpoint was written only after the engine finished. A 90-minute run would have
been unprotected for its entire duration, making the contract decorative. Found when a live run left
an empty checkpoint directory after 90 seconds. Both the port and the runner now take a per-segment
callback, and a test counts durable records from inside the engine as it yields.

**2 — The composition root built the store and dropped it.** `checkpoint_root` was accepted, the
store constructed, and the service returned without it. Every service-level test passed because they
construct the service directly. Found the same way. Tests now assert the composed service holds a
store, that omitting the root disables checkpointing, and that the CLI forwards both options.

**3 — Boundary comparison rejected valid checkpoints.** `segments_are_increasing` compared exactly,
so the `PATCH-0039` shape — `3129.1000000000004` against `3129.1`, a delta of `4.5e-13` — made a
checkpoint look non-increasing. On the real corpus 88 % of boundaries touch, so a long checkpoint was
near-certain to hit one: resume was unreachable in exactly the situation it exists for. Found when
the restart wrote three fresh segments instead of resuming from 441.58 s. The released
`TIMING_BOUNDARY_TOLERANCE_SECONDS` is now reused for both comparisons; the full 2,564-segment corpus
is accepted while a real 0.5-second overlap and an out-of-order ordinal are still rejected.

## Real interruption and resume

Executed on the 2-hour, 30.2 GB lecture with `large-v3`, `language=ko`, CPU `int8`.

| stage | observation |
|---|---|
| run 1, before kill | 90 segments recorded, last end `441.58 s` |
| repository at that moment | admissions 0, raw transcripts 0, segments 0 |
| after `SIGKILL` | process dead, **90 segments survived** |
| run 2, +90 s | 106 segments; the first 90 unchanged |
| resume boundary | `#89` ends `441.58`, `#90` starts `441.58` — absolute, contiguous, ordinals unbroken |
| run 2, completion | `execution mode: resumed`, `resumed from: 441.58s`, 1,731 segments admitted |
| checkpoint afterwards | **deleted** (CP-17); directory empty |
| repository | `healthy`, schema v53, 0 errors, 0 warnings |
| run 3 | `execution mode: reused` — canonical reuse, engine not run, checkpoint not consulted |

The evidence that 85 minutes were not repeated is the checkpoint content itself: after resume the
first 90 records are byte-identical and `#89` still ends at `441.58`, where a fresh run would have
restarted from zero.

All three CP-8 paths are therefore demonstrated on real media: **reused**, **resumed**, **fresh**.

## What is not implemented

Per CP-21 and the milestone scope: no background collection scheduler (the primitive takes a
caller-supplied cutoff so no TTL is invented), no progress percentage, no background job, durable
queue, retry scheduler, cancellation, chunked or parallel ASR, remote or shared checkpoints, and no
checkpoint migration across providers.
