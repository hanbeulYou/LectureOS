"""External ASR Boundary Application Foundation — Provider Transcript Result admission (040 §14).

The first application realization of 040 §4.2 (External ASR Boundary) and §4.3 (Raw Transcript Preservation)
(PATCH-0021). It admits an **externally produced** ASR result for an already-admitted `TranscriptSourceIntake`
(040 §13) and produces the first canonical `RawTranscript`, while preserving the provider evidence distinctly.

It answers one question: *how does LectureOS admit an externally produced ASR result for an already-admitted
Source Media intake?* — not how media is decoded, how audio is extracted, which provider is selected, or how a
model runs. **No ASR engine executes here**; the provider result is supplied, not computed. The service reads no
media file and makes no network request.

Key contract (040 §14):

* Input is a canonical `TranscriptSourceIntakeId` plus a provider-neutral (LectureOS-native) result document —
  provider reference, optional model, optional declared language, an external provider-result reference, and an
  ordered list of segments (``start``/``end`` seconds, ``text``). It is never a media path.
* Admission carries **external** execution provenance: this slice creates no internal ``ProcessingRun`` and
  requires no RUNNING unit execution. All identities are derived deterministically from the anchor
  ``(intake_id, provider, model, provider_result_ref)`` (SHA-256); no wall-clock/randomness participates.
* The provider evidence (`ProviderTranscriptResult`) is preserved un-normalized and kept distinct from the
  canonical `RawTranscript`, which is a separate record whose identity is never the provider payload.
* One provider result projects to exactly one `RawTranscript`; an intake may hold multiple provider results.
* Admission is idempotent by content (a SHA-256 fingerprint over the full payload); re-admitting the same anchor
  with a different payload is a conflict and is rejected without mutation.
* Timing is in seconds with ``end > start``, non-overlapping and non-decreasing; text is preserved exactly; an
  empty (zero-segment) result is rejected. Non-overlap is judged between **instants**, not float
  representations (PATCH-0039): adjacent boundaries within ``TIMING_BOUNDARY_TOLERANCE_SECONDS`` are the
  touching case A-10 already allows. Submitted values are never adjusted, and the tolerance participates in no
  identity or fingerprint.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from math import isfinite
from typing import Mapping, Protocol, Sequence

from lectureos.execution.identities import (
    CapabilityReference,
    DomainResultId,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)
from lectureos.execution.models import DomainResultReference
from lectureos.persistence.errors import PersistenceIdentityCollisionError
from lectureos.transcript.identities import (
    ProviderTranscriptResultId,
    TranscriptId,
    TranscriptSegmentId,
)
from lectureos.transcript.models import (
    ProviderTranscriptResult,
    RawTranscript,
    TranscriptSegment,
)

from .identities import ProviderTranscriptAdmissionId, TranscriptSourceIntakeId

# The ASR capability role at the External ASR Boundary (040 §4.2). A fixed provider-neutral capability reference;
# it is NOT a provider, model, or plugin identifier.
ASR_TRANSCRIPTION_CAPABILITY = "capability:asr-transcription"

PROVIDER_TRANSCRIPT_ADMISSION_IDENTITY_PREFIX = "provider-transcript-admission"
PROVIDER_TRANSCRIPT_RESULT_IDENTITY_PREFIX = "provider-transcript-result"
RAW_TRANSCRIPT_IDENTITY_PREFIX = "raw-transcript"
RAW_TRANSCRIPT_DOMAIN_RESULT_KIND = "raw_transcript"
_RAW_TRANSCRIPT_DOMAIN_RESULT_PREFIX = "domain-result:raw-transcript"
_EXTERNAL_ASR_RUN_PREFIX = "external-asr-run"
_EXTERNAL_ASR_EXECUTION_PREFIX = "external-asr-execution"
_TRANSCRIPT_SEGMENT_PREFIX = "transcript-segment"
_SOURCE_TIMELINE_PREFIX = "source-timeline"

# The `original_content` key under which preserved provider decode evidence lives (040 §15 QD-6).
# It is absent from the fingerprint basis by construction — see `_logical_admission_content`.
_PROVIDER_EVIDENCE_KEY = "provider_evidence"

# 040 §14 A-10 / PATCH-0039 T-2: adjacent segment boundaries are compared as instants, so a
# neighbouring start may precede the previous end by at most this much and still count as touching.
# One microsecond sits ~5 orders of magnitude above float64 representation noise even for ten-hour
# media (ULP ~7.3e-12 s at t = 36000 s) and ~3 orders below the released SRT millisecond grid, so a
# real overlap capable of changing any downstream artifact is never admitted by it (T-6). It governs
# admission only — no submitted timestamp is ever adjusted, and it participates in no identity,
# fingerprint, or anchor (T-4, T-5).
TIMING_BOUNDARY_TOLERANCE_SECONDS = 1e-6

# A canonical Source Media intake identity is 'transcript-source-intake:<algorithm>:<64 hex digest>'.
_CANONICAL_INTAKE_ID = re.compile(
    r"^transcript-source-intake:[a-z0-9]+:[0-9a-f]{64}$"
)


class ProviderTranscriptAdmissionError(ValueError):
    """A provider transcript result that cannot be admitted (malformed input or unresolvable intake)."""


class ProviderTranscriptAdmissionConflictError(ProviderTranscriptAdmissionError):
    """The same provider-result anchor was re-admitted with a different payload (no silent overwrite)."""


def require_canonical_intake_id(value: str) -> TranscriptSourceIntakeId:
    """Return a `TranscriptSourceIntakeId` if the value is a well-formed intake identity, else reject."""

    if not isinstance(value, str) or not _CANONICAL_INTAKE_ID.fullmatch(value):
        raise ProviderTranscriptAdmissionError(
            "transcript source intake identity is malformed "
            "(expected 'transcript-source-intake:<algorithm>:<64 hex digest>')"
        )
    return TranscriptSourceIntakeId(value)


def _source_media_id_of(intake_id: TranscriptSourceIntakeId) -> SourceMediaId:
    """The Source Media identity embedded in a canonical intake identity (040 §13 derivation)."""

    return SourceMediaId(intake_id.value.split(":", 1)[1])


def derive_source_timeline_id(source_media_id: SourceMediaId) -> SourceTimelineId:
    """Deterministic single source timeline for a Source Media (`source-timeline:<source_media_id>`)."""

    return SourceTimelineId(f"{_SOURCE_TIMELINE_PREFIX}:{source_media_id.value}")


@dataclass(frozen=True, slots=True)
class ProviderDecodeWindow:
    """One decode window's provider-native evidence and the segments it covers (040 §15 QD-5, QD-7).

    This is **provider evidence**, not a diagnostic: values the provider reported during one execution,
    recorded verbatim under the provider's own field names. It is deliberately *not* a per-segment
    confidence — QD-7 forbids that, because a window's value is shared by every segment it covers and
    presenting it as one segment's own confidence states something untrue. The shape keeps the sharing
    structurally visible: the value lives on the window and the covered segments are listed.

    ``window_ref`` is the provider's own window anchor recorded as-is (faster-whisper's ``seek``). It is
    evidence, never an identity: window entries are distinguished by their position and covered
    ordinals, so a resumed execution that re-bases its anchors cannot collide with an earlier window.
    """

    window_ref: str
    segment_ordinals: tuple[int, ...]
    values: tuple[tuple[str, float], ...]
    start: float | None = None
    end: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.window_ref, str) or not self.window_ref.strip():
            raise ProviderTranscriptAdmissionError("decode window reference must not be empty")
        if not self.segment_ordinals:
            raise ProviderTranscriptAdmissionError(
                "decode window must cover at least one segment ordinal"
            )
        previous: int | None = None
        for ordinal in self.segment_ordinals:
            if isinstance(ordinal, bool) or not isinstance(ordinal, int) or ordinal < 0:
                raise ProviderTranscriptAdmissionError(
                    "decode window segment ordinal must be a non-negative integer"
                )
            if previous is not None and ordinal <= previous:
                raise ProviderTranscriptAdmissionError(
                    "decode window segment ordinals must be strictly increasing"
                )
            previous = ordinal
        if not self.values:
            raise ProviderTranscriptAdmissionError("decode window must carry at least one value")
        seen: set[str] = set()
        for name, value in self.values:
            if not isinstance(name, str) or not name.strip():
                raise ProviderTranscriptAdmissionError("decode evidence name must not be empty")
            if name in seen:
                raise ProviderTranscriptAdmissionError(
                    f"decode evidence name {name!r} is repeated in one window"
                )
            seen.add(name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
                raise ProviderTranscriptAdmissionError(
                    f"decode evidence {name!r} must be a finite number"
                )
        for label, bound in (("start", self.start), ("end", self.end)):
            if bound is None:
                continue
            if isinstance(bound, bool) or not isinstance(bound, (int, float)) or not isfinite(bound):
                raise ProviderTranscriptAdmissionError(
                    f"decode window {label} must be a finite number of seconds"
                )


@dataclass(frozen=True, slots=True)
class ProviderDecodeEvidence:
    """The provider evidence submitted alongside a result: ordered, non-overlapping decode windows.

    ``kind`` names the provider-native evidence family so a reader knows what the value names mean
    without the core having to model them. A window need not exist for every segment: a provider may
    report evidence for part of a result, and the absent part is evidence-unavailable — never
    quality-clean (QD-9).
    """

    kind: str
    windows: tuple[ProviderDecodeWindow, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.kind, str) or not self.kind.strip():
            raise ProviderTranscriptAdmissionError("provider evidence kind must not be empty")
        if not self.windows:
            raise ProviderTranscriptAdmissionError(
                "provider evidence must contain at least one decode window"
            )
        highest: int | None = None
        for window in self.windows:
            lowest = window.segment_ordinals[0]
            if highest is not None and lowest <= highest:
                raise ProviderTranscriptAdmissionError(
                    "decode windows must be ordered and must not share segment ordinals"
                )
            highest = window.segment_ordinals[-1]

    @property
    def covered_ordinals(self) -> frozenset[int]:
        return frozenset(
            ordinal for window in self.windows for ordinal in window.segment_ordinals
        )


@dataclass(frozen=True, slots=True)
class ProviderTranscriptSegmentInput:
    """One submitted provider segment: a source-timeline-aligned span of text (seconds).

    Deliberately carries no confidence or uncertainty field. Provider decode evidence is window-scoped
    and reaches the boundary through :class:`ProviderDecodeEvidence` instead (QD-6, QD-7).
    """

    start: float
    end: float
    text: str

    def __post_init__(self) -> None:
        for label, value in (("start", self.start), ("end", self.end)):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ProviderTranscriptAdmissionError(
                    f"segment {label} must be a number in seconds"
                )
            if not isfinite(value):
                raise ProviderTranscriptAdmissionError(
                    f"segment {label} must be a finite number of seconds"
                )
        if self.start < 0:
            raise ProviderTranscriptAdmissionError("segment start must not be negative")
        if self.end <= self.start:
            raise ProviderTranscriptAdmissionError(
                "segment end must be strictly after start (zero-length spans are rejected)"
            )
        if not isinstance(self.text, str) or not self.text.strip():
            raise ProviderTranscriptAdmissionError("segment text must not be empty")


@dataclass(frozen=True, slots=True)
class ProviderTranscriptDocument:
    """A validated provider-neutral ASR result: provider evidence plus ordered, non-overlapping segments."""

    provider: str
    provider_result_ref: str
    segments: tuple[ProviderTranscriptSegmentInput, ...]
    model: str | None = None
    language: str | None = None
    provider_evidence: ProviderDecodeEvidence | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.provider, str) or not self.provider.strip():
            raise ProviderTranscriptAdmissionError("provider must not be empty")
        if not isinstance(self.provider_result_ref, str) or not self.provider_result_ref.strip():
            raise ProviderTranscriptAdmissionError("provider result reference must not be empty")
        if self.model is not None and (not isinstance(self.model, str) or not self.model.strip()):
            raise ProviderTranscriptAdmissionError("provider model, when present, must not be empty")
        if self.language is not None and (
            not isinstance(self.language, str) or not self.language.strip()
        ):
            raise ProviderTranscriptAdmissionError("declared language, when present, must not be empty")
        if not self.segments:
            raise ProviderTranscriptAdmissionError(
                "provider result must contain at least one segment (empty results are rejected)"
            )
        # Segments must be non-decreasing in start and non-overlapping (touching boundaries allowed).
        # A-10 compares instants, not float representations (PATCH-0039 T-1): boundaries that differ
        # only by representation noise denote one instant and are touching, so adjacency is judged
        # within TIMING_BOUNDARY_TOLERANCE_SECONDS. The submitted values are never adjusted (T-4).
        previous_end: float | None = None
        for segment in self.segments:
            if (
                previous_end is not None
                and segment.start < previous_end - TIMING_BOUNDARY_TOLERANCE_SECONDS
            ):
                raise ProviderTranscriptAdmissionError(
                    "segments must be ordered by start and must not overlap"
                )
            previous_end = segment.end
        if self.provider_evidence is not None:
            limit = len(self.segments)
            for ordinal in self.provider_evidence.covered_ordinals:
                if ordinal >= limit:
                    raise ProviderTranscriptAdmissionError(
                        "provider evidence references a segment ordinal that does not exist"
                    )


def build_provider_transcript_document(payload: Mapping[str, object]) -> ProviderTranscriptDocument:
    """Build a validated :class:`ProviderTranscriptDocument` from a decoded JSON mapping."""

    if not isinstance(payload, Mapping):
        raise ProviderTranscriptAdmissionError("provider result must be a JSON object")
    allowed = {
        "provider", "model", "language", "provider_result_ref", "segments", "provider_evidence",
    }
    unknown = set(payload) - allowed
    if unknown:
        raise ProviderTranscriptAdmissionError(
            f"provider result has unknown field(s): {', '.join(sorted(unknown))}"
        )
    raw_segments = payload.get("segments")
    if not isinstance(raw_segments, Sequence) or isinstance(raw_segments, (str, bytes)):
        raise ProviderTranscriptAdmissionError("provider result segments must be a list")
    segments = tuple(_build_segment(entry) for entry in raw_segments)
    return ProviderTranscriptDocument(
        provider=_require_str(payload.get("provider"), "provider"),
        provider_result_ref=_require_str(payload.get("provider_result_ref"), "provider result reference"),
        segments=segments,
        model=_optional_str(payload.get("model"), "provider model"),
        language=_optional_str(payload.get("language"), "declared language"),
        provider_evidence=_build_provider_evidence(payload.get("provider_evidence")),
    )


def _build_provider_evidence(entry: object) -> ProviderDecodeEvidence | None:
    """Build submitted provider evidence from a decoded JSON mapping, or ``None`` when absent."""

    if entry is None:
        return None
    if not isinstance(entry, Mapping):
        raise ProviderTranscriptAdmissionError("provider evidence must be a JSON object")
    unknown = set(entry) - {"kind", "windows"}
    if unknown:
        raise ProviderTranscriptAdmissionError(
            f"provider evidence has unknown field(s): {', '.join(sorted(unknown))}"
        )
    raw_windows = entry.get("windows")
    if not isinstance(raw_windows, Sequence) or isinstance(raw_windows, (str, bytes)):
        raise ProviderTranscriptAdmissionError("provider evidence windows must be a list")
    return ProviderDecodeEvidence(
        kind=_require_str(entry.get("kind"), "provider evidence kind"),
        windows=tuple(_build_decode_window(window) for window in raw_windows),
    )


def _build_decode_window(entry: object) -> ProviderDecodeWindow:
    if not isinstance(entry, Mapping):
        raise ProviderTranscriptAdmissionError("each decode window must be a JSON object")
    unknown = set(entry) - {"window_ref", "segment_ordinals", "values", "start", "end"}
    if unknown:
        raise ProviderTranscriptAdmissionError(
            f"decode window has unknown field(s): {', '.join(sorted(unknown))}"
        )
    ordinals = entry.get("segment_ordinals")
    values = entry.get("values")
    if not isinstance(ordinals, Sequence) or isinstance(ordinals, (str, bytes)):
        raise ProviderTranscriptAdmissionError("decode window segment ordinals must be a list")
    if not isinstance(values, Mapping):
        raise ProviderTranscriptAdmissionError("decode window values must be a JSON object")
    return ProviderDecodeWindow(
        window_ref=_require_str(entry.get("window_ref"), "decode window reference"),
        segment_ordinals=tuple(ordinals),
        values=tuple(sorted((str(name), value) for name, value in values.items())),
        start=entry.get("start"),
        end=entry.get("end"),
    )


def _build_segment(entry: object) -> ProviderTranscriptSegmentInput:
    if not isinstance(entry, Mapping):
        raise ProviderTranscriptAdmissionError("each segment must be a JSON object")
    unknown = set(entry) - {"start", "end", "text"}
    if unknown:
        raise ProviderTranscriptAdmissionError(
            f"segment has unknown field(s): {', '.join(sorted(unknown))}"
        )
    if "start" not in entry or "end" not in entry or "text" not in entry:
        raise ProviderTranscriptAdmissionError("each segment requires start, end, and text")
    return ProviderTranscriptSegmentInput(
        start=entry["start"], end=entry["end"], text=entry["text"]
    )


def _require_str(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProviderTranscriptAdmissionError(f"{label} must be a non-empty string")
    return value


def _optional_str(value: object, label: str) -> str | None:
    if value is None:
        return None
    return _require_str(value, label)


@dataclass(frozen=True, slots=True)
class ProviderTranscriptAdmission:
    """Durable, immutable record that an external provider result was admitted for an intake (040 §14)."""

    identity: ProviderTranscriptAdmissionId
    transcript_source_intake_id: TranscriptSourceIntakeId
    source_media_id: SourceMediaId
    provider_transcript_result_id: ProviderTranscriptResultId
    raw_transcript_id: TranscriptId
    provider_reference: str
    provider_result_ref: str
    segment_count: int
    content_fingerprint: str
    provider_model: str | None = None
    declared_language: str | None = None

    def __post_init__(self) -> None:
        if not self.provider_reference.strip():
            raise ValueError("admission provider reference must not be empty")
        if not self.provider_result_ref.strip():
            raise ValueError("admission provider result reference must not be empty")
        if self.segment_count <= 0:
            raise ValueError("admission segment count must be positive")
        if len(self.content_fingerprint) != 64:
            raise ValueError("admission content fingerprint must be a 64-hex SHA-256 digest")


@dataclass(frozen=True, slots=True)
class ProviderTranscriptAdmissionResult:
    """The outcome of one admission: the admission record and whether it was newly created or reused.

    The admission record carries the canonical provider-result and raw-transcript identities and the segment
    count, so callers never need to re-fetch the domain objects to report the outcome.
    """

    admission: ProviderTranscriptAdmission
    created: bool


class TranscriptSourceIntakeQuery(Protocol):
    def get(self, identity): ...


class SourceMediaQuery(Protocol):
    def get(self, identity): ...


class ProviderTranscriptAdmissionQuery(Protocol):
    def get(self, identity): ...


class AtomicProviderTranscriptAdmissionPersistence(Protocol):
    def persist_provider_transcript_admission(
        self,
        *,
        admission: ProviderTranscriptAdmission,
        provider_result: ProviderTranscriptResult,
        segments: tuple[TranscriptSegment, ...],
        raw_transcript: RawTranscript,
        result: DomainResultReference,
    ) -> None: ...


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _anchor_digest(
    intake_id_value: str, provider: str, model: str | None, provider_result_ref: str
) -> str:
    """The SHA-256 digest of the canonical admission anchor — the basis of every derived identity."""

    return _sha256(
        _canonical_json(
            {
                "intake": intake_id_value,
                "provider": provider,
                "model": model or "",
                "provider_result_ref": provider_result_ref,
            }
        )
    )


def derive_provider_transcript_admission_identity(
    intake_id: TranscriptSourceIntakeId,
    provider: str,
    model: str | None,
    provider_result_ref: str,
) -> ProviderTranscriptAdmissionId:
    """The deterministic admission identity for an anchor, computable before any provider result exists.

    Lets an upstream executor (e.g. a local ASR adapter) check whether an equivalent result was already admitted
    and skip re-running the engine, without re-deriving the anchor logic itself.
    """

    return ProviderTranscriptAdmissionId(
        f"{PROVIDER_TRANSCRIPT_ADMISSION_IDENTITY_PREFIX}:"
        f"{_anchor_digest(intake_id.value, provider, model, provider_result_ref)}"
    )


class ProviderTranscriptAdmissionService:
    """Admits an external provider ASR result for an intake, producing one canonical Raw Transcript."""

    def __init__(
        self,
        intake_query: TranscriptSourceIntakeQuery,
        source_media_query: SourceMediaQuery,
        admission_query: ProviderTranscriptAdmissionQuery,
        persistence: AtomicProviderTranscriptAdmissionPersistence | None = None,
    ) -> None:
        self._intakes = intake_query
        self._source_media = source_media_query
        self._admissions = admission_query
        self._persistence = persistence

    def admit(
        self, *, intake_id: str, document: ProviderTranscriptDocument
    ) -> ProviderTranscriptAdmissionResult:
        # Resolve the intake (persisted facts only); a malformed identity is rejected before any lookup.
        intake_identity = require_canonical_intake_id(intake_id)
        intake = self._intakes.get(intake_identity)
        if intake is None:
            raise ProviderTranscriptAdmissionError(
                "unknown transcript source intake: admit the Source Media as an intake first"
            )
        source_media_id = _source_media_id_of(intake_identity)
        if intake.source_media_id != source_media_id:
            raise ProviderTranscriptAdmissionError(
                "transcript source intake identity disagrees with its Source Media reference"
            )
        if self._source_media.get(source_media_id) is None:
            raise ProviderTranscriptAdmissionError(
                "unknown source media: the intake references a missing Source Media record"
            )

        digest = _anchor_digest(
            intake_identity.value,
            document.provider,
            document.model,
            document.provider_result_ref,
        )
        # QD-8: the fingerprint basis is the logical content only. Evidence enrichment must never
        # move a released fingerprint, so these two serializations are deliberately separate.
        content_fingerprint = _sha256(_logical_admission_content(intake_identity, document))
        admission_identity = ProviderTranscriptAdmissionId(
            f"{PROVIDER_TRANSCRIPT_ADMISSION_IDENTITY_PREFIX}:{digest}"
        )

        existing = self._admissions.get(admission_identity)
        if existing is not None:
            return self._resolve_existing(existing, content_fingerprint)

        source_timeline_id = derive_source_timeline_id(source_media_id)
        provider_result_id = ProviderTranscriptResultId(
            f"{PROVIDER_TRANSCRIPT_RESULT_IDENTITY_PREFIX}:{digest}"
        )
        transcript_id = TranscriptId(f"{RAW_TRANSCRIPT_IDENTITY_PREFIX}:{digest}")
        domain_result_id = DomainResultId(f"{_RAW_TRANSCRIPT_DOMAIN_RESULT_PREFIX}:{digest}")
        run_id = ProcessingRunId(f"{_EXTERNAL_ASR_RUN_PREFIX}:{digest}")
        unit_execution_id = UnitExecutionId(f"{_EXTERNAL_ASR_EXECUTION_PREFIX}:{digest}")

        segments = tuple(
            TranscriptSegment(
                identity=TranscriptSegmentId(f"{_TRANSCRIPT_SEGMENT_PREFIX}:{digest}:{ordinal}"),
                transcript_id=transcript_id,
                source_timeline_id=source_timeline_id,
                text=segment.text,
                source_order=ordinal,
                start=float(segment.start),
                end=float(segment.end),
            )
            for ordinal, segment in enumerate(document.segments)
        )
        provider_result = ProviderTranscriptResult(
            identity=provider_result_id,
            source_media_id=source_media_id,
            source_timeline_id=source_timeline_id,
            run_id=run_id,
            unit_execution_id=unit_execution_id,
            capability=CapabilityReference(ASR_TRANSCRIPTION_CAPABILITY),
            provider_reference=document.provider,
            original_content=_original_provider_content(intake_identity, document),
            normalized=False,
        )
        raw_transcript = RawTranscript(
            identity=transcript_id,
            domain_result_id=domain_result_id,
            source_media_id=source_media_id,
            source_timeline_id=source_timeline_id,
            provider_result_id=provider_result_id,
            run_id=run_id,
            unit_execution_id=unit_execution_id,
            segment_ids=tuple(segment.identity for segment in segments),
        )
        result = DomainResultReference(
            identity=domain_result_id,
            kind=RAW_TRANSCRIPT_DOMAIN_RESULT_KIND,
            source_media=source_media_id,
            source_timeline=source_timeline_id,
        )
        admission = ProviderTranscriptAdmission(
            identity=admission_identity,
            transcript_source_intake_id=intake_identity,
            source_media_id=source_media_id,
            provider_transcript_result_id=provider_result_id,
            raw_transcript_id=transcript_id,
            provider_reference=document.provider,
            provider_result_ref=document.provider_result_ref,
            segment_count=len(segments),
            content_fingerprint=content_fingerprint,
            provider_model=document.model,
            declared_language=document.language,
        )

        if self._persistence is None:
            raise RuntimeError("provider transcript admission persistence is not configured")
        try:
            self._persistence.persist_provider_transcript_admission(
                admission=admission,
                provider_result=provider_result,
                segments=segments,
                raw_transcript=raw_transcript,
                result=result,
            )
        except PersistenceIdentityCollisionError:
            # A near-concurrent admission of the same anchor won; converge on it (or surface a conflict).
            resolved = self._admissions.get(admission_identity)
            if resolved is None:
                raise
            return self._resolve_existing(resolved, content_fingerprint)
        return ProviderTranscriptAdmissionResult(admission=admission, created=True)

    def _resolve_existing(
        self, existing: ProviderTranscriptAdmission, content_fingerprint: str
    ) -> ProviderTranscriptAdmissionResult:
        if existing.content_fingerprint != content_fingerprint:
            raise ProviderTranscriptAdmissionConflictError(
                "a different provider transcript result was already admitted for this provider result "
                "reference (LectureOS does not overwrite an admitted result)"
            )
        return ProviderTranscriptAdmissionResult(admission=existing, created=False)


def _logical_admission_content(
    intake_id: TranscriptSourceIntakeId, document: ProviderTranscriptDocument
) -> str:
    """Canonical serialization of the **logical** admitted result — the A-8 fingerprint basis.

    Includes every segment's timing and exact text so any content difference is detectable, and
    deliberately nothing else. Provider decode evidence does not appear here (040 §14 A-8 note /
    §15 QD-8): A-8 identifies "the same logical result", and two executions whose text and timing agree
    but whose decode statistics differ **are** the same logical result — the statistics say how the
    result was produced, not what it is. Adding them would make evidence enrichment look like an A-9
    conflict and would change every released fingerprint.

    This function is therefore the fingerprint basis and nothing else. `_original_provider_content`
    is what gets preserved; the two were one helper before `PATCH-0045` and are now separate on
    purpose, so a later change to preserved evidence cannot silently move an identity.
    """

    return _canonical_json(
        {
            "intake": intake_id.value,
            "provider": document.provider,
            "model": document.model,
            "language": document.language,
            "provider_result_ref": document.provider_result_ref,
            "segments": [
                {"start": float(segment.start), "end": float(segment.end), "text": segment.text}
                for segment in document.segments
            ],
        }
    )


def _original_provider_content(
    intake_id: TranscriptSourceIntakeId, document: ProviderTranscriptDocument
) -> str:
    """Canonical serialization of the preserved provider evidence — `original_content` (A-4, QD-6).

    The logical content plus whatever decode evidence the provider actually returned. When no evidence
    was submitted this is byte-identical to the logical content, so a result admitted without evidence
    is represented exactly as it always was — its absence is what makes it *evidence unavailable*,
    which is not *quality clean* (QD-9).
    """

    logical = _logical_admission_content(intake_id, document)
    evidence = document.provider_evidence
    if evidence is None:
        return logical
    payload = json.loads(logical)
    payload[_PROVIDER_EVIDENCE_KEY] = {
        "kind": evidence.kind,
        "windows": [
            {
                "window_ref": window.window_ref,
                "segment_ordinals": list(window.segment_ordinals),
                "values": {name: float(value) for name, value in window.values},
                "start": window.start,
                "end": window.end,
            }
            for window in evidence.windows
        ],
    }
    return _canonical_json(payload)


def parse_preserved_segment_timings(original_content: str) -> tuple[tuple[float, float], ...]:
    """Read back the ordered ``(start, end)`` pairs preserved in an `original_content` string.

    The logical admission content records every segment's timing verbatim (A-4), so a derived
    read-time observation can reconstruct segment ordering and boundaries without re-reading the
    canonical segment rows. Returns an empty tuple when the content is unreadable — this is preserved
    provider evidence, and failing to interpret it must never make a released record unreadable.
    """

    try:
        payload = json.loads(original_content)
    except (TypeError, ValueError):
        return ()
    if not isinstance(payload, dict):
        return ()
    raw = payload.get("segments")
    if not isinstance(raw, list):
        return ()
    out: list[tuple[float, float]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            return ()
        try:
            out.append((float(entry["start"]), float(entry["end"])))
        except (KeyError, TypeError, ValueError):
            return ()
    return tuple(out)


def parse_preserved_provider_evidence(original_content: str) -> ProviderDecodeEvidence | None:
    """Read back the decode evidence preserved in an `original_content` string, or ``None``.

    ``None`` means **evidence unavailable** — either a result admitted before `PATCH-0045`, or a
    provider that reported none. It never means the result is clean; callers must keep that
    distinction (QD-9). Unreadable content also yields ``None`` rather than raising: `original_content`
    is preserved provider evidence, and failing to interpret it must not make a released record
    unreadable.
    """

    try:
        payload = json.loads(original_content)
    except (TypeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    raw = payload.get(_PROVIDER_EVIDENCE_KEY)
    if not isinstance(raw, dict):
        return None
    raw_windows = raw.get("windows")
    if not isinstance(raw_windows, list) or not raw_windows:
        return None
    windows: list[ProviderDecodeWindow] = []
    for entry in raw_windows:
        if not isinstance(entry, dict):
            return None
        values = entry.get("values")
        ordinals = entry.get("segment_ordinals")
        if not isinstance(values, dict) or not isinstance(ordinals, list):
            return None
        try:
            windows.append(
                ProviderDecodeWindow(
                    window_ref=entry["window_ref"],
                    segment_ordinals=tuple(int(ordinal) for ordinal in ordinals),
                    values=tuple(sorted((str(k), float(v)) for k, v in values.items())),
                    start=None if entry.get("start") is None else float(entry["start"]),
                    end=None if entry.get("end") is None else float(entry["end"]),
                )
            )
        except (KeyError, TypeError, ValueError, ProviderTranscriptAdmissionError):
            return None
    try:
        return ProviderDecodeEvidence(kind=str(raw.get("kind") or ""), windows=tuple(windows))
    except ProviderTranscriptAdmissionError:
        return None


__all__ = [
    "ASR_TRANSCRIPTION_CAPABILITY",
    "AtomicProviderTranscriptAdmissionPersistence",
    "PROVIDER_TRANSCRIPT_ADMISSION_IDENTITY_PREFIX",
    "PROVIDER_TRANSCRIPT_RESULT_IDENTITY_PREFIX",
    "ProviderTranscriptAdmission",
    "ProviderTranscriptAdmissionConflictError",
    "ProviderTranscriptAdmissionError",
    "ProviderTranscriptAdmissionQuery",
    "ProviderTranscriptAdmissionResult",
    "ProviderTranscriptAdmissionService",
    "ProviderDecodeEvidence",
    "ProviderDecodeWindow",
    "ProviderTranscriptDocument",
    "ProviderTranscriptSegmentInput",
    "RAW_TRANSCRIPT_DOMAIN_RESULT_KIND",
    "RAW_TRANSCRIPT_IDENTITY_PREFIX",
    "SourceMediaQuery",
    "TranscriptSourceIntakeQuery",
    "build_provider_transcript_document",
    "derive_provider_transcript_admission_identity",
    "derive_source_timeline_id",
    "parse_preserved_provider_evidence",
    "parse_preserved_segment_timings",
    "require_canonical_intake_id",
]
