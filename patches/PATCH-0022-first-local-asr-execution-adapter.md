# PATCH-0022

- Title: First Concrete Local ASR Execution Adapter — faster-whisper (First Slice) (040)
- Status: Accepted
- Priority: Medium
- Trigger: Architect / Product Owner Decision (first concrete local ASR adapter behind the provider-neutral boundary)
- Created: 2026-07-26
- Target Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` (§4.2 External ASR Boundary; realizes a concrete provider behind §14)

---

## Status

Accepted. Establishes the first **concrete local ASR execution adapter** — a single engine (`faster-whisper`)
that runs locally, converts its output into the existing provider-neutral `ProviderTranscriptDocument`
(040 §14, PATCH-0021), and admits it through the **existing** Provider Transcript Result Admission service. No
schema change: the adapter reuses the v32 admission structures unchanged. It introduces one concrete adapter, not
a provider framework.

## Trigger

`040 §14` (PATCH-0021) established the provider-neutral admission boundary but supplied results by hand; no real
ASR engine existed. `040 §4.2` requires that a replaceable external provider's ASR role be integrated behind that
boundary. The first concrete adapter is the smallest capability that makes LectureOS actually transcribe a
`SourceMedia` locally. A bounded, delegated Product decision settled the concrete engine and its execution
contract, and this PATCH promotes it.

## Context

The admission boundary (040 §14) is authoritative and is the **sole write path** for Provider Transcript Result
and Raw Transcript state. This adapter is an *upstream executor*: it resolves an admitted intake to its Source
Media, verifies the reference-in-place source file, runs one local engine, and terminates by producing the
already-confirmed provider-neutral document and calling the existing admission service. It never writes Raw
Transcript rows directly and never alters provider-result or Raw Transcript semantics to accommodate the engine.

## First-Slice Product Decision

### Selected engine

**faster-whisper** (a CTranslate2 Whisper implementation): local execution, no cloud credentials, stable
timestamped segment output, CPU-capable (GPU optional), a bounded pip dependency, testable behind an injected
factory without loading a real model, and decodes media internally (no separate ffmpeg step for common inputs).
It is imported **lazily** so the core package and tests remain usable without it installed; its absence is an
explicit operational error. This is the smallest faithful first implementation; the engine remains replaceable
because it terminates at the unchanged provider-neutral boundary.

### Operational source resolution and fingerprint verification

At execution time the adapter resolves the persisted `SourceMedia.observed_source_path` (reference in place). It
requires the path to exist as a readable regular file (the confirmed Media Import symlink policy applies:
symlinks are resolved to a regular-file target) and **re-verifies the current bytes against the stored content
fingerprint** by streaming (bounded memory). It never re-imports, never re-hashes into a new identity, never
mutates the record, and never changes `SourceMediaId`. A missing/unreadable/directory/empty source is a
`LocalAsrSourceUnavailableError`; changed bytes are a distinct `LocalAsrSourceChangedError` directing the
operator to import the changed file as a **new** Source Media record — LectureOS never silently transcribes
changed bytes under the old identity. Missing physical files are execution failures, **not** repository
corruption (consistent with 045 §1 M-11 and 040 §13 S-5).

### Media preparation

**None** in this slice: faster-whisper decodes the source internally, so no ffmpeg step is added merely for
symmetry. If a future engine requires preparation, it must use a bounded, shell-free (argument-array) runner
writing only to an isolated temporary workspace cleaned on success and failure, never overwriting the original,
and must not persist extracted audio as an Artifact unless a confirmed contract requires it.

### Execution metadata, identity, and replay

Provider/model metadata is truthful: `provider = "faster-whisper"`, `model` is the operator-supplied identifier.
The **provider-result reference is deterministic** — `local-asr:model=<model>:lang=<language-or-auto>:media=
<source_media_id>` — encoding the semantic request (model, requested language, source content identity). Because
the admission identity is deterministic from the anchor `(intake, provider, model, provider_result_ref)`, the
adapter **checks for an already-admitted result before running the engine and reuses it without re-executing**,
avoiding a spurious conflict from ordinary ASR non-determinism. Device and compute-type are operational
performance settings, **not** semantic identity, and are excluded from the reference. No wall-clock timestamp or
randomness defines identity. Distinct model / language / source produce distinct admissions; a conflicting result
for the same anchor is never overwritten.

### Failure and atomicity

External ASR work cannot be rolled back, but the adapter performs **no repository write before a valid engine
result is admitted**. Any failure — malformed/unknown intake, source unavailable/changed, missing dependency or
model, engine failure, or inadmissible output — leaves no Provider Transcript Result, segment, Raw Transcript, or
admission state, and mutates neither the Source Media nor the intake record. Admission atomicity remains owned by
the existing admission service (all-or-nothing).

## Explicit Deferred Scope

Other engines/providers, a provider registry or plugin discovery, cloud ASR, credential management, a model
downloader/catalog UI, GPU-required execution, background jobs, durable queues, retry schedulers, progress
persistence, cancellation, streaming/microphone input, diarization, speaker identification, word/token-level
timestamps, confidence rewriting, automatic correction, translation, subtitle/NLE/rendering changes, managed
media storage, permanent extracted-audio storage, and a generalized ffmpeg framework — all deferred. No
placeholders are introduced.

## Consequences

- `040 §4.2` gains its first confirmed concrete provider (§15) behind the unchanged §14 boundary.
- **No schema change**: the v32 admission structures are reused; `SQLITE_SCHEMA_VERSION` stays 32.
- The engine dependency is optional and isolated; the core package imports without it.
- The provider-neutral admission contract, provider-result evidence, and Raw Transcript semantics are unchanged.
- Repository hygiene: accidentally-tracked compiled bytecode (`__pycache__/*.pyc`) is removed from version
  control and ignored, so the working tree is genuinely clean.
