"""First Transcript Correction Candidate Admission (040 §17, PATCH-0024).

Records a **proposed** correction for one segment of the **currently selected** Raw Transcript, **without applying
it**. It answers only: *how can LectureOS record a proposed correction for one segment of the current Raw
Transcript?* — not whether the correction is right, who approves it, or how a corrected revision is built.

A Correction Candidate is a suggestion, not canonical transcript content. Admission:

* requires the intake to be **ready** (a valid current Raw Transcript selection, 040 §16) and the target Raw
  Transcript to be that current selection;
* targets one **immutable** Raw Transcript segment and stores a **source-text snapshot** that must match the
  persisted segment exactly (stale detection);
* **never** mutates Raw Transcript text, changes the current selection, creates a corrected revision or a
  candidate decision, ranks candidates, applies anything, runs ASR, or reads media.

It reuses the existing canonical `CorrectionCandidate` (transcript domain, schema v5) as the suggestion record and
binds it to its admission context (intake, snapshot, source metadata) with an additive admission record (v34).
Provenance is external/manual — deterministic execution markers derived from the anchor, with no internal RUNNING
execution. Identities are deterministic from the anchor `(intake, raw_transcript, segment, source_type,
source_reference, candidate_ref)`; admission is idempotent by a content fingerprint, and a conflicting reuse of the
same anchor is rejected without overwrite. Multiple distinct suggestions per segment coexist (distinct
`candidate_ref`). Historical candidates remain immutable after a later selection switch — surfaced as no longer
applicable, never deleted, retargeted, or treated as corruption. No wall-clock/randomness defines identity.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Protocol

from lectureos.execution.identities import (
    CapabilityReference,
    DomainResultId,
    ProcessingRunId,
    UnitExecutionId,
)
from lectureos.execution.models import DomainResultReference
from lectureos.persistence.errors import PersistenceIdentityCollisionError
from lectureos.transcript.identities import (
    CorrectionCandidateId,
    TranscriptId,
    TranscriptSegmentId,
)
from lectureos.transcript.models import CorrectionCandidate

from .identities import CorrectionCandidateAdmissionId, TranscriptSourceIntakeId
from .provider_transcript_admission import (
    ProviderTranscriptAdmissionError,
    require_canonical_intake_id,
)
from .current_raw_transcript_selection import require_canonical_raw_transcript_id

# A fixed provider-neutral capability role for the correction stage (not a provider/model/plugin identifier).
TRANSCRIPT_CORRECTION_CAPABILITY = "capability:transcript-correction"
CORRECTION_CANDIDATE_ADMISSION_IDENTITY_PREFIX = "correction-candidate-admission"
CORRECTION_CANDIDATE_IDENTITY_PREFIX = "correction-candidate"
CORRECTION_CANDIDATE_DOMAIN_RESULT_KIND = "transcript_correction_candidate"
_DOMAIN_RESULT_PREFIX = "domain-result:transcript-correction-candidate"
_EXTERNAL_RUN_PREFIX = "external-correction-run"
_EXTERNAL_EXECUTION_PREFIX = "external-correction-execution"
_SEGMENT_IDENTITY_PREFIX = "transcript-segment:"


class CorrectionCandidateSourceType(str, Enum):
    MANUAL = "manual"
    EXTERNAL = "external"
    RULE = "rule"


class CorrectionCandidateAdmissionError(ValueError):
    """A correction candidate that cannot be admitted (malformed, not ready, unrelated, stale, or no-op)."""


class IntakeNotReadyError(CorrectionCandidateAdmissionError):
    """The intake has no valid current Raw Transcript selection, so no candidate may be admitted."""


class RawTranscriptNotCurrentError(CorrectionCandidateAdmissionError):
    """The target Raw Transcript is not the intake's current selection."""


class SegmentLineageError(CorrectionCandidateAdmissionError):
    """The target segment is unknown or does not belong to the target Raw Transcript."""


class SourceTextMismatchError(CorrectionCandidateAdmissionError):
    """The supplied source-text snapshot does not match the persisted segment text (stale target)."""


class CorrectionCandidateConflictError(CorrectionCandidateAdmissionError):
    """The same candidate anchor was re-admitted with a different payload (no silent overwrite)."""


def require_canonical_segment_id(value: str) -> TranscriptSegmentId:
    """Return a `TranscriptSegmentId` if the value is a well-formed transcript segment identity, else reject."""

    if not isinstance(value, str) or not value.startswith(_SEGMENT_IDENTITY_PREFIX):
        raise CorrectionCandidateAdmissionError(
            "segment identity is malformed (expected 'transcript-segment:<...>')"
        )
    remainder = value[len(_SEGMENT_IDENTITY_PREFIX):]
    if not re.fullmatch(r"[0-9a-f]{64}:\d+", remainder):
        raise CorrectionCandidateAdmissionError(
            "segment identity is malformed (expected 'transcript-segment:<64 hex>:<ordinal>')"
        )
    return TranscriptSegmentId(value)


@dataclass(frozen=True, slots=True)
class CorrectionCandidateInput:
    """A validated first-slice correction candidate suggestion (no ranking/quality/approval fields)."""

    raw_transcript_id: str
    segment_id: str
    candidate_ref: str
    source_type: CorrectionCandidateSourceType
    source_reference: str
    proposed_text: str
    source_text_snapshot: str
    rationale: str
    model_reference: str | None = None

    def __post_init__(self) -> None:
        for label, value in (
            ("candidate_ref", self.candidate_ref),
            ("source_reference", self.source_reference),
            ("rationale", self.rationale),
        ):
            if not isinstance(value, str) or not value.strip():
                raise CorrectionCandidateAdmissionError(f"{label} must be a non-empty string")
        if not isinstance(self.proposed_text, str) or not self.proposed_text.strip():
            raise CorrectionCandidateAdmissionError("proposed text must not be empty")
        if not isinstance(self.source_text_snapshot, str):
            raise CorrectionCandidateAdmissionError("source text snapshot must be a string")
        if self.model_reference is not None and (
            not isinstance(self.model_reference, str) or not self.model_reference.strip()
        ):
            raise CorrectionCandidateAdmissionError("model reference, when present, must not be empty")
        if self.proposed_text == self.source_text_snapshot:
            raise CorrectionCandidateAdmissionError(
                "proposed text equals the source text (a no-op candidate is not admissible)"
            )


def build_correction_candidate_input(payload: Mapping[str, object]) -> CorrectionCandidateInput:
    """Build a validated :class:`CorrectionCandidateInput` from a decoded JSON mapping (strict fields)."""

    if not isinstance(payload, Mapping):
        raise CorrectionCandidateAdmissionError("correction candidate must be a JSON object")
    allowed = {
        "raw_transcript_id", "segment_id", "candidate_ref", "source_type",
        "source_reference", "proposed_text", "source_text_snapshot", "rationale",
        "model_reference",
    }
    unknown = set(payload) - allowed
    if unknown:
        raise CorrectionCandidateAdmissionError(
            f"correction candidate has unknown field(s): {', '.join(sorted(unknown))}"
        )
    source_type_value = payload.get("source_type")
    try:
        source_type = CorrectionCandidateSourceType(source_type_value)
    except ValueError:
        raise CorrectionCandidateAdmissionError(
            "source_type must be one of: manual, external, rule"
        ) from None
    required = ("raw_transcript_id", "segment_id", "candidate_ref", "source_reference",
                "proposed_text", "source_text_snapshot", "rationale")
    for field in required:
        if field not in payload:
            raise CorrectionCandidateAdmissionError(f"correction candidate requires '{field}'")
    return CorrectionCandidateInput(
        raw_transcript_id=_require_str(payload["raw_transcript_id"], "raw_transcript_id"),
        segment_id=_require_str(payload["segment_id"], "segment_id"),
        candidate_ref=_require_str(payload["candidate_ref"], "candidate_ref"),
        source_type=source_type,
        source_reference=_require_str(payload["source_reference"], "source_reference"),
        proposed_text=_require_str(payload["proposed_text"], "proposed_text"),
        source_text_snapshot=payload["source_text_snapshot"]
        if isinstance(payload["source_text_snapshot"], str)
        else _reject("source_text_snapshot"),
        rationale=_require_str(payload["rationale"], "rationale"),
        model_reference=(
            _require_str(payload["model_reference"], "model_reference")
            if payload.get("model_reference") is not None
            else None
        ),
    )


def _require_str(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise CorrectionCandidateAdmissionError(f"{label} must be a string")
    return value


def _reject(label: str):
    raise CorrectionCandidateAdmissionError(f"{label} must be a string")


@dataclass(frozen=True, slots=True)
class CorrectionCandidateAdmission:
    """Durable, immutable record binding an admitted CorrectionCandidate to its admission context (040 §17)."""

    identity: CorrectionCandidateAdmissionId
    correction_candidate_id: CorrectionCandidateId
    transcript_source_intake_id: TranscriptSourceIntakeId
    raw_transcript_id: TranscriptId
    segment_id: TranscriptSegmentId
    source_type: CorrectionCandidateSourceType
    source_reference: str
    candidate_ref: str
    source_text_snapshot: str
    content_fingerprint: str
    model_reference: str | None = None

    def __post_init__(self) -> None:
        if not self.source_reference.strip() or not self.candidate_ref.strip():
            raise ValueError("admission source and candidate references must not be empty")
        if len(self.content_fingerprint) != 64:
            raise ValueError("admission content fingerprint must be a 64-hex SHA-256 digest")


@dataclass(frozen=True, slots=True)
class CorrectionCandidateAdmissionResult:
    """The outcome of one admission: the admission record, the candidate, and whether it was newly created."""

    admission: CorrectionCandidateAdmission
    candidate: CorrectionCandidate
    created: bool


@dataclass(frozen=True, slots=True)
class CorrectionCandidateView:
    """A read-only view of an admitted candidate, with applicability to the intake's current selection."""

    correction_candidate_id: CorrectionCandidateId
    raw_transcript_id: TranscriptId
    segment_id: TranscriptSegmentId
    source_type: CorrectionCandidateSourceType
    source_reference: str
    candidate_ref: str
    source_text: str
    proposed_text: str
    applicable_to_current_selection: bool


class TranscriptSourceIntakeQuery(Protocol):
    def get(self, identity): ...


class RawTranscriptSelectionQuery(Protocol):
    def get_current(self, intake_id): ...


class TranscriptSegmentQuery(Protocol):
    def get(self, identity): ...


class RawTranscriptQuery(Protocol):
    def get(self, identity): ...


class CorrectionCandidateAdmissionQuery(Protocol):
    def get(self, identity): ...

    def candidate(self, candidate_id): ...

    def candidates_for_intake(self, intake_id, current_raw_transcript_id) -> tuple: ...


class AtomicCorrectionCandidateAdmissionPersistence(Protocol):
    def persist_correction_candidate_admission(
        self,
        *,
        admission: CorrectionCandidateAdmission,
        candidate: CorrectionCandidate,
        result: DomainResultReference,
    ) -> None: ...


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _anchor_digest(
    intake_id: TranscriptSourceIntakeId,
    raw_transcript_id: TranscriptId,
    segment_id: TranscriptSegmentId,
    source_type: CorrectionCandidateSourceType,
    source_reference: str,
    candidate_ref: str,
) -> str:
    return _sha256(
        _canonical_json(
            {
                "intake": intake_id.value,
                "raw_transcript": raw_transcript_id.value,
                "segment": segment_id.value,
                "source_type": source_type.value,
                "source_reference": source_reference,
                "candidate_ref": candidate_ref,
            }
        )
    )


class CorrectionCandidateAdmissionService:
    """Admits a proposed correction against the current Raw Transcript segment — never applying it."""

    def __init__(
        self,
        intake_query: TranscriptSourceIntakeQuery,
        selection_query: RawTranscriptSelectionQuery,
        segment_query: TranscriptSegmentQuery,
        raw_transcript_query: RawTranscriptQuery,
        admission_query: CorrectionCandidateAdmissionQuery,
        persistence: AtomicCorrectionCandidateAdmissionPersistence | None = None,
    ) -> None:
        self._intakes = intake_query
        self._selections = selection_query
        self._segments = segment_query
        self._raw_transcripts = raw_transcript_query
        self._admissions = admission_query
        self._persistence = persistence

    def _resolve_intake(self, intake_id: str) -> TranscriptSourceIntakeId:
        try:
            identity = require_canonical_intake_id(intake_id)
        except ProviderTranscriptAdmissionError as error:
            raise CorrectionCandidateAdmissionError(str(error)) from error
        if self._intakes.get(identity) is None:
            raise CorrectionCandidateAdmissionError(
                "unknown transcript source intake: admit the Source Media as an intake first"
            )
        return identity

    def admit(
        self, *, intake_id: str, candidate: CorrectionCandidateInput
    ) -> CorrectionCandidateAdmissionResult:
        intake_identity = self._resolve_intake(intake_id)

        # Readiness: a valid current Raw Transcript selection must exist.
        current = self._selections.get_current(intake_identity)
        if current is None:
            raise IntakeNotReadyError(
                "intake is not ready: select a current Raw Transcript before admitting candidates"
            )

        transcript_identity = require_canonical_raw_transcript_id(candidate.raw_transcript_id)
        if transcript_identity != current.raw_transcript_id:
            raise RawTranscriptNotCurrentError(
                "target raw transcript is not the intake's current selection"
            )

        segment_identity = require_canonical_segment_id(candidate.segment_id)
        segment = self._segments.get(segment_identity)
        if segment is None:
            raise SegmentLineageError("unknown transcript segment")
        if segment.transcript_id != transcript_identity:
            raise SegmentLineageError(
                "segment does not belong to the target raw transcript"
            )
        if candidate.source_text_snapshot != segment.text:
            raise SourceTextMismatchError(
                "source text snapshot does not match the current segment text (stale target)"
            )

        raw_transcript = self._raw_transcripts.get(transcript_identity)
        if raw_transcript is None:  # defensive: the current selection guarantees this exists
            raise RawTranscriptNotCurrentError("current raw transcript could not be resolved")

        digest = _anchor_digest(
            intake_identity,
            transcript_identity,
            segment_identity,
            candidate.source_type,
            candidate.source_reference,
            candidate.candidate_ref,
        )
        content_fingerprint = _sha256(
            _canonical_json(
                {
                    "anchor": digest,
                    "proposed_text": candidate.proposed_text,
                    "source_text_snapshot": candidate.source_text_snapshot,
                    "rationale": candidate.rationale,
                    "model_reference": candidate.model_reference,
                }
            )
        )
        admission_identity = CorrectionCandidateAdmissionId(
            f"{CORRECTION_CANDIDATE_ADMISSION_IDENTITY_PREFIX}:{digest}"
        )
        existing = self._admissions.get(admission_identity)
        if existing is not None:
            if existing.content_fingerprint != content_fingerprint:
                raise CorrectionCandidateConflictError(
                    "a different correction candidate was already admitted for this candidate reference "
                    "(LectureOS does not overwrite an admitted candidate)"
                )
            return self._reused(existing)

        candidate_identity = CorrectionCandidateId(
            f"{CORRECTION_CANDIDATE_IDENTITY_PREFIX}:{digest}"
        )
        domain_result_id = DomainResultId(f"{_DOMAIN_RESULT_PREFIX}:{digest}")
        record = CorrectionCandidate(
            identity=candidate_identity,
            domain_result_id=domain_result_id,
            transcript_id=transcript_identity,
            segment_id=segment_identity,
            proposed_text=candidate.proposed_text,
            rationale=candidate.rationale,
            run_id=ProcessingRunId(f"{_EXTERNAL_RUN_PREFIX}:{digest}"),
            unit_execution_id=UnitExecutionId(f"{_EXTERNAL_EXECUTION_PREFIX}:{digest}"),
            capability=CapabilityReference(TRANSCRIPT_CORRECTION_CAPABILITY),
            provider_reference=candidate.source_reference,
        )
        result = DomainResultReference(
            identity=domain_result_id,
            kind=CORRECTION_CANDIDATE_DOMAIN_RESULT_KIND,
            source_media=raw_transcript.source_media_id,
            source_timeline=raw_transcript.source_timeline_id,
            upstream_results=(raw_transcript.domain_result_id,),
        )
        admission = CorrectionCandidateAdmission(
            identity=admission_identity,
            correction_candidate_id=candidate_identity,
            transcript_source_intake_id=intake_identity,
            raw_transcript_id=transcript_identity,
            segment_id=segment_identity,
            source_type=candidate.source_type,
            source_reference=candidate.source_reference,
            candidate_ref=candidate.candidate_ref,
            source_text_snapshot=candidate.source_text_snapshot,
            content_fingerprint=content_fingerprint,
            model_reference=candidate.model_reference,
        )

        if self._persistence is None:
            raise RuntimeError("correction candidate admission persistence is not configured")
        try:
            self._persistence.persist_correction_candidate_admission(
                admission=admission, candidate=record, result=result
            )
        except PersistenceIdentityCollisionError:
            resolved = self._admissions.get(admission_identity)
            if resolved is not None and resolved.content_fingerprint == content_fingerprint:
                return self._reused(resolved)
            raise
        return CorrectionCandidateAdmissionResult(
            admission=admission, candidate=record, created=True
        )

    def _reused(
        self, admission: CorrectionCandidateAdmission
    ) -> CorrectionCandidateAdmissionResult:
        candidate = self._admissions.candidate(admission.correction_candidate_id)
        return CorrectionCandidateAdmissionResult(
            admission=admission, candidate=candidate, created=False
        )

    def candidates(self, intake_id: str) -> tuple[CorrectionCandidateView, ...]:
        intake_identity = self._resolve_intake(intake_id)
        current = self._selections.get_current(intake_identity)
        current_raw = current.raw_transcript_id if current is not None else None
        return self._admissions.candidates_for_intake(intake_identity, current_raw)


__all__ = [
    "CORRECTION_CANDIDATE_ADMISSION_IDENTITY_PREFIX",
    "CORRECTION_CANDIDATE_DOMAIN_RESULT_KIND",
    "CORRECTION_CANDIDATE_IDENTITY_PREFIX",
    "TRANSCRIPT_CORRECTION_CAPABILITY",
    "AtomicCorrectionCandidateAdmissionPersistence",
    "CorrectionCandidateAdmission",
    "CorrectionCandidateAdmissionError",
    "CorrectionCandidateAdmissionQuery",
    "CorrectionCandidateAdmissionResult",
    "CorrectionCandidateAdmissionService",
    "CorrectionCandidateConflictError",
    "CorrectionCandidateInput",
    "CorrectionCandidateSourceType",
    "CorrectionCandidateView",
    "IntakeNotReadyError",
    "RawTranscriptNotCurrentError",
    "SegmentLineageError",
    "SourceTextMismatchError",
    "build_correction_candidate_input",
    "require_canonical_segment_id",
]
