# First Concrete Local ASR Execution Adapter — faster-whisper

- Status: Implementation Reference
- Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` §15 (realizes §4.2 behind the §14 admission boundary) /
  `patches/PATCH-0022`
- Schema: unchanged (v32; reuses the Provider Transcript Admission structures)

## What it is (and is not)

The first **concrete local ASR execution adapter**. It runs one local engine (`faster-whisper`) over the source
file of an admitted `TranscriptSourceIntake`, converts the output into the existing provider-neutral
`ProviderTranscriptDocument`, and hands it to the **existing** Provider Transcript Result Admission service
(040 §14) — the sole write boundary. It produces (or reuses) exactly one canonical `RawTranscript`.

- It is **one concrete adapter**, not a provider framework: no registry, plugin discovery, or generic SDK.
- The engine dependency is **optional and lazily imported**, so the core package and the whole test suite run
  without `faster-whisper` installed; its absence is an explicit `LocalAsrDependencyError`.
- It **never writes Raw Transcript / Provider Transcript Result rows directly** and never alters their semantics.
- Transcription **accuracy is not guaranteed**; supported formats, operating systems, and GPU availability are
  not guaranteed.

## Orchestration

```text
TranscriptSourceIntake → SourceMedia → verified operational source path
  → (no media preparation; faster-whisper decodes internally)
  → local ASR engine (faster-whisper) → LocalAsrResult
  → ProviderTranscriptDocument → existing admission service
  → ProviderTranscriptResult + RawTranscript
```

`LocalAsrTranscriptionService.transcribe(intake_id, model, language=None, device="cpu", compute_type="int8")`:

1. resolve the intake (malformed/unknown → `LocalAsrIntakeError`) and its Source Media record;
2. compute the deterministic provider-result reference and admission identity, and **reuse an already-admitted
   result without re-running the engine** if present (`executed=False`);
3. verify operational source availability + fingerprint (below);
4. run the engine (dependency/model/engine failures → typed errors);
5. convert to a `ProviderTranscriptDocument` (inadmissible output → `LocalAsrOutputError`);
6. admit via the existing service; return the admission, `created`, and `executed` flags.

## Source availability and fingerprint verification

`infrastructure/local_source_media_verifier.py::LocalSourceMediaVerifier` reuses the Media Import streaming,
bounded-memory SHA-256 inspector, so the symlink and read policy are identical. It requires a readable regular
file at `SourceMedia.observed_source_path` and re-hashes the current bytes:

- missing / unreadable / directory / empty → `LocalAsrSourceUnavailableError`;
- current bytes ≠ stored fingerprint → `LocalAsrSourceChangedError` (import the changed file as a **new** Source
  Media record; LectureOS never transcribes changed bytes under the old `SourceMediaId`).

It never re-imports, re-hashes into a new identity, mutates the record, or changes `SourceMediaId`. Missing files
are execution failures, not repository corruption.

## Media preparation

None. faster-whisper decodes the source internally, so no separate ffmpeg step is added.

## Engine integration

`infrastructure/faster_whisper_engine.py::FasterWhisperEngineRunner` runs `faster_whisper.WhisperModel` on CPU by
default (`device="cpu"`, `compute_type="int8"`; GPU optional). It is a **pure library call** (no subprocess, no
shell — no injection surface). The injectable `model_factory` seam lets contract tests drive the exact invocation
shape (model/device/compute-type propagation, `transcribe(path, language=...)`, segment/text/timestamp
extraction, and error translation) with a fake model, without the real library or a downloaded model. Errors map
to `LocalAsrDependencyError` / `LocalAsrModelError` / `LocalAsrEngineError`.

## Identity and replay

The provider-result reference is deterministic — `local-asr:model=<model>:lang=<language-or-auto>:media=
<source_media_id>` — so distinct model / language / source produce distinct admissions. Device and compute-type
are operational performance settings and are **excluded** from identity. Because the admission identity is
deterministic, the adapter checks for an already-admitted result **before** running the engine and reuses it
without re-executing — avoiding a spurious conflict from ordinary ASR non-determinism. No wall-clock/randomness
defines identity.

## Failure and atomicity

No repository write occurs before a valid engine result is admitted; any failure leaves no partial state and
mutates neither the Source Media nor the intake. Admission atomicity is owned by the existing admission service.

## CLI

```bash
PYTHONPATH=src python3 -m lectureos.local_asr_cli \
    --intake <transcript-source-intake-id> --database <db-path> --model <model> \
    [--language <lang>] [--device cpu] [--compute-type int8]
```

Requires an existing repository with the intake admitted. Runs real local ASR (CPU default). Prints the Source
Media, intake, provider-result, and Raw Transcript identities, provider/model, segment count, created/reused, and
whether real ASR execution occurred. Exit `0` on success; `1` on unavailable/changed source, missing dependency
or model, engine failure, malformed output, admission conflict, or any error — leaving the repository unchanged
before admission.

## Optional dependency

`faster-whisper` is an optional runtime dependency (install `faster-whisper`). It is not required to import the
package, run the test suite, or run the deterministic demo (which uses a fake engine). Real execution also needs
a local model (faster-whisper fetches it on first use) and can decode common media via its bundled backend.

## Deterministic demo & real smoke

`lectureos.local_asr_demo` drives the whole orchestration with a **fake** deterministic engine (no real ASR),
proving lineage use, source verification, reuse-without-rerun replay, failure-before-admission writes nothing,
healthy validation, and a byte-for-byte golden (`examples/local-asr/`). The real smoke test (a genuine
faster-whisper run) is documented in the example README and the milestone report.

## Deferred

Other engines/providers, provider registry / plugin discovery, cloud ASR, credentials, model downloader/catalog,
GPU-required execution, background jobs, queues, retries, progress, cancellation, streaming/microphone,
diarization, speaker labels, word/token timestamps, translation, automatic correction, subtitle/NLE/rendering,
managed media storage, permanent extracted-audio storage, and a generalized ffmpeg framework — all deferred
(040 §15 L-14). No placeholders are introduced.
