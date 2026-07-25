# PATCH-0021

- Title: External ASR Boundary — Provider Transcript Result Admission (First Slice) (040)
- Status: Accepted
- Priority: Medium
- Trigger: Architect / Product Owner Decision (first provider-result admission slice; delegated bounded decisions)
- Created: 2026-07-25
- Target Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` (§4.2 External ASR Boundary, §4.3 Raw Transcript Preservation)

---

## Status

Accepted. Establishes the first application realization of the **External ASR Boundary** (`040 §4.2`) and the
first **Raw Transcript Preservation** (`040 §4.3`) produced from an externally supplied ASR result. Introduces
one additive persisted record — the **Provider Transcript Admission** — at schema **v32**, binding an admitted
`TranscriptSourceIntake` (`040 §13`, PATCH-0020) to a canonical `ProviderTranscriptResult`, its
`TranscriptSegment`s, and exactly one canonical `RawTranscript`. No ffmpeg/ffprobe, no Whisper or any ASR
engine, no audio extraction, no network, and no media decoding.

## Trigger

`040 §4.2`/`§4.3` define the External ASR Boundary and Raw Transcript preservation as logical pipeline stages,
and the canonical `ProviderTranscriptResult`, `TranscriptSegment`, and `RawTranscript` records already exist in
the domain and persistence (schema v5). They were designed to be produced by an *internal* Processing Run: the
existing `TranscriptService` requires a **RUNNING** `UnitExecution` before a provider result or raw transcript
may be recorded. LectureOS had no application boundary through which an **externally produced** ASR result — the
real shape of the External ASR Boundary (`040 §4.2`: "교체 가능한 External AI Provider의 ASR 역할과 Transcript
Pipeline 내부 책임을 분리한다") — can be admitted without inventing a fake internal running execution. The first
runnable admission slice needs that boundary. A bounded, delegated Product decision settled it and this PATCH
promotes it.

## Context

The External ASR Boundary is the point where a replaceable external provider's ASR role meets internal
Transcript responsibility. Its result is **unverified external evidence** (`040 §4.2`: "provider 결과는 검증되지
않은 외부 생성 결과다"): the provider's own identifiers are preserved as provenance but can never become the
Transcript's sole identity. This slice consumes one admitted `TranscriptSourceIntake` and one deterministic
provider-neutral (LectureOS-native) ASR result document, and produces the first canonical `RawTranscript` while
preserving the provider evidence distinctly. It executes no ASR engine; the provider result is supplied, not
computed.

## First-Slice Product Decision

### External, not internal, execution provenance

The External ASR Boundary admits a result produced by an **external** execution. This slice does **not** create
an internal `ProcessingRun`/`UnitExecution` and does **not** require a RUNNING unit execution (that would be
fake execution semantics for an external boundary). Instead admission carries **external execution provenance**:
the caller supplies a stable external provider-result reference, and LectureOS derives deterministic
`ProcessingRunId` / `UnitExecutionId` / `DomainResultId` provenance markers from it. These are provenance TEXT
references on the existing records (no cross-table foreign key requires internal execution rows), consistent
with the loosely-coupled transcript schema. The canonical `DomainResultReference` for the raw transcript is
created and persisted as usual.

### Provider evidence preserved and kept distinct from canonical transcript

A `ProviderTranscriptResult` preserves the exact submitted provider evidence — provider reference, optional
model, optional declared language, external result reference, and the full ordered segment payload — serialized
canonically as `original_content` and stored **un-normalized** (`normalized = 0`, enforced by the existing
model and schema). The canonical `RawTranscript` is a **separate** record with its own `TranscriptId`; the
provider result is referenced as provenance (`provider_transcript_result_id`), never equated with the
Transcript's identity (`040 §4.2`).

### Deterministic derived identities and single canonical projection

All LectureOS identities are derived deterministically from a stable anchor —
`(intake_id, provider, model, provider_result_ref)` — hashed with SHA-256:

- one `ProviderTranscriptResult` per anchor,
- exactly **one** canonical `RawTranscript` per provider result (1:1 projection),
- one `TranscriptSegment` per submitted segment (ordinal = submission order),
- one **Provider Transcript Admission** record binding the intake → provider result → raw transcript.

No wall-clock time or randomness participates in any semantic identity. An intake **may** receive multiple
provider results (distinct providers/models/executions produce distinct anchors), consistent with reprocessing
(`040 §10.1`: "새 ASR 결과는 새 Raw Transcript provenance와 연결한다").

### Idempotency and conflict

Admission is **idempotent by content**: a Provider Transcript Admission stores a SHA-256 `content_fingerprint`
over the full canonical admission payload (including every segment's timing and exact text). Re-admitting the
same logical result (same anchor, identical payload) resolves and returns the existing records
(`created = false`). Re-admitting the **same anchor with a different payload** is a **conflict** and is rejected
without mutation — LectureOS never silently overwrites an admitted provider result or raw transcript
(`040 §2` Raw Before Corrected; `§10.1` "기존 Raw Transcript를 덮어쓰지 않는다").

### Timing and text semantics

Segments carry `start` and `end` in **seconds** (finite, `start >= 0`, `end > start` — zero-length spans are
rejected), aligned to a deterministic source timeline derived from the Source Media
(`source-timeline:<source_media_id>`). Segments must be submitted in non-decreasing `start` order and must not
overlap (`segment[i].end <= segment[i+1].start`; touching boundaries are allowed). Segment text is required,
non-blank, and **preserved exactly** as submitted (no trimming, normalization, or reflow); non-ASCII/Korean
text is preserved byte-for-byte. An **empty** provider result (zero segments) is rejected — an empty raw
transcript would hide ASR failure (`040 §9.6`: "실패를 빈 텍스트… 정상 교정으로 해석하지 않는다").

### Failure atomicity and authority

Any failure (malformed intake identity, unknown intake, malformed/empty/unordered/overlapping/zero-length
segments, blank provider metadata, conflict, persistence error) leaves **no partial** provider result, segment,
raw transcript, or admission state and mutates neither the Source Media nor the intake record. The admission
record is authoritative only for the repository/application fact that "this external provider result was
admitted for this intake, producing this raw transcript." It asserts nothing about ASR accuracy, completeness,
audio content, or the media's decodability, and it does not read the media file.

## Explicit Deferred Scope

ffmpeg/ffprobe, media decoding, audio extraction, codec/duration/stream inspection, Whisper / faster-whisper /
whisper.cpp / cloud ASR, model download/selection, GPU/device selection, credentials, provider installation, a
provider/plugin registry, background jobs, queues, retries, progress, cancellation, streaming transcription,
diarization, speaker identification, word/token-level timestamps, confidence-based correction, language
**detection** (only a declared passthrough language is accepted), correction candidates, corrected revisions,
structural validation of the raw transcript, review, and subtitle/export changes. No placeholders for these are
introduced.

## Consequences

- `040 §4.2`/`§4.3` gain a confirmed first-slice application contract (`040 §14`).
- Schema advances additively to **v32** (one new table `provider_transcript_admissions`); every released
  version v1..v31 reaches v32 through the supported single-step chain with no data loss.
- The existing canonical `ProviderTranscriptResult`, `TranscriptSegment`, and `RawTranscript` records and their
  schema are reused unchanged; no second transcript hierarchy is introduced.
- Downstream Correction, Validation, Review, and Subtitle contracts are unaffected.
