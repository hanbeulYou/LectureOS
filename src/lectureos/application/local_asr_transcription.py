"""First concrete local ASR execution adapter — orchestration (040 §15, PATCH-0022).

The smallest real local ASR adapter. It resolves an admitted `TranscriptSourceIntake` to its `SourceMedia`,
verifies the reference-in-place source file is operationally available *and* still matches the stored content
fingerprint, executes **one** concrete local ASR engine (behind a port), converts the engine output into the
existing provider-neutral `ProviderTranscriptDocument`, and hands it to the **existing** Provider Transcript
Result Admission service (040 §14) — which remains the sole write boundary. The adapter never writes Provider
Transcript Result / Raw Transcript rows directly and never mutates the Source Media or intake records.

This module is engine-agnostic: it depends only on the `LocalAsrEngineRunner` and `SourceMediaLocationVerifier`
ports (concrete implementations live under ``infrastructure/``), so the engine is replaceable without touching
the admission contract. The optional engine dependency is isolated in the concrete runner, so importing this
module never requires the ASR library to be installed.

Replay is safe: the admission identity is deterministic from the anchor
``(intake_id, provider, model, provider_result_ref)``, so the service **checks for an already-admitted result
before running the engine** and reuses it without re-executing (avoiding a spurious conflict from ordinary ASR
non-determinism). A conflicting result for the same anchor is never overwritten. No wall-clock/randomness defines
identity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from lectureos.execution.identities import SourceMediaId

from .provider_transcript_admission import (
    ProviderTranscriptAdmission,
    ProviderTranscriptAdmissionError,
    ProviderTranscriptAdmissionService,
    ProviderTranscriptDocument,
    build_provider_transcript_document,
    derive_provider_transcript_admission_identity,
    require_canonical_intake_id,
)

# The one concrete engine this first slice integrates. Truthful provider metadata (not a registry key).
FASTER_WHISPER_PROVIDER = "faster-whisper"
DEFAULT_DEVICE = "cpu"
DEFAULT_COMPUTE_TYPE = "int8"
_PROVIDER_RESULT_REF_PREFIX = "local-asr"

# 040 §15 L-7 / PATCH-0040 P-4: the reference grammar is versioned. v1
# (`local-asr:model=…:lang=…:media=…`) is released, stays valid and readable, and is never generated
# again; v2 additionally carries the approved provider configuration.
PROVIDER_RESULT_REF_VERSION = "v2"


class LocalAsrError(Exception):
    """Base class for local ASR execution failures (operational, not repository corruption)."""


class LocalAsrIntakeError(LocalAsrError):
    """The transcript source intake is malformed or unknown."""


class LocalAsrSourceUnavailableError(LocalAsrError):
    """The reference-in-place source file is missing, unreadable, a directory, or empty."""


class LocalAsrSourceChangedError(LocalAsrError):
    """The source file's current bytes no longer match the stored Source Media fingerprint."""


class LocalAsrDependencyError(LocalAsrError):
    """The selected local ASR engine dependency is not installed."""


class LocalAsrModelError(LocalAsrError):
    """The requested ASR model could not be loaded (missing or unusable)."""


class LocalAsrEngineError(LocalAsrError):
    """The local ASR engine failed while transcribing."""


class LocalAsrOutputError(LocalAsrError):
    """The engine produced output that is not admissible as a provider-neutral document."""


@dataclass(frozen=True, slots=True)
class LocalAsrProviderConfiguration:
    """The engine decoding parameters LectureOS declares rather than inherits (040 §15 L-15).

    Application owns these because they change the emitted text and therefore the canonical Raw Transcript
    (PATCH-0040 P-1). Only the parameters this contract actually decides are represented — this is deliberately
    not a general settings framework, and a parameter absent here is one LectureOS has taken no position on and
    leaves to the engine.

    ``condition_on_previous_text=False`` is the approved production value (P-2). It configures the provider
    **before** it decodes; it is never a filter over what the provider returned (P-7).
    """

    condition_on_previous_text: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.condition_on_previous_text, bool):
            raise LocalAsrError("condition_on_previous_text must be a boolean")

    @property
    def reference_fragment(self) -> str:
        """This configuration's contribution to the versioned provider-result reference (L-7)."""

        return f"cond_prev_text={'true' if self.condition_on_previous_text else 'false'}"


# 040 §15 L-15 / PATCH-0040 P-2: the sole approved production configuration. There is deliberately no
# CLI flag, environment variable, or configuration file that selects a different value — an override is
# the bypass P-1 exists to prevent. Diagnostic exploration happens outside this path and admits nothing.
APPROVED_LOCAL_ASR_CONFIGURATION = LocalAsrProviderConfiguration(condition_on_previous_text=False)


@dataclass(frozen=True, slots=True)
class LocalAsrSegment:
    """One timestamped segment returned by the local engine (seconds)."""

    start: float
    end: float
    text: str


@dataclass(frozen=True, slots=True)
class LocalAsrResult:
    """The engine's raw result: truthful provider/model/language metadata and ordered segments."""

    provider: str
    model: str
    language: str | None
    segments: tuple[LocalAsrSegment, ...]


@dataclass(frozen=True, slots=True)
class LocalAsrTranscriptionResult:
    """The outcome: the admitted record, whether it was newly created, and whether the engine actually ran."""

    admission: ProviderTranscriptAdmission
    created: bool
    executed: bool


class TranscriptSourceIntakeQuery(Protocol):
    def get(self, identity): ...


class SourceMediaQuery(Protocol):
    def get(self, identity): ...


class ProviderTranscriptAdmissionQuery(Protocol):
    def get(self, identity): ...


class SourceMediaLocationVerifier(Protocol):
    """Resolves and verifies the operational source file for a persisted Source Media record.

    Returns the verified resolved absolute path. Raises `LocalAsrSourceUnavailableError` if the file is missing/
    unreadable/a directory/empty, or `LocalAsrSourceChangedError` if its current bytes no longer match the stored
    fingerprint. It must never mutate the record or the file.
    """

    def verify(self, record) -> str: ...


class LocalAsrEngineRunner(Protocol):
    """Executes one concrete local ASR engine over a local media path and returns a `LocalAsrResult`.

    Raises `LocalAsrDependencyError` / `LocalAsrModelError` / `LocalAsrEngineError` for the respective operational
    failures. Must not read the repository or admit results.
    """

    def transcribe(
        self,
        *,
        media_path: str,
        model: str,
        language: str | None,
        device: str,
        compute_type: str,
        condition_on_previous_text: bool,
    ) -> LocalAsrResult: ...


def derive_provider_result_ref(
    source_media_id: SourceMediaId,
    model: str,
    language: str | None,
    configuration: LocalAsrProviderConfiguration = APPROVED_LOCAL_ASR_CONFIGURATION,
) -> str:
    """Deterministic, versioned provider-result reference for a local ASR execution (040 §15 L-7).

    Encodes the semantic execution request — model, requested language, the approved provider configuration, and
    source content identity — so a distinct model, language, configuration, or source produces a distinct
    admission anchor. Device/compute-type stay excluded: they serve the same request faster without changing the
    emitted text, whereas the configuration changes the text and therefore the canonical Raw Transcript
    (PATCH-0040 P-3).

    This emits **v2** only. Released v1 references stay valid and readable, are never rewritten or re-derived,
    and are never re-interpreted as carrying a configuration they do not state (P-4). An intake holding a v1
    admission therefore will not match a v2 anchor, so L-8 reuse does not fire and a second Raw Transcript is
    admitted — permitted by §14 A-7, with §16 Selection deciding which is authoritative (P-5).
    """

    return (
        f"{_PROVIDER_RESULT_REF_PREFIX}:{PROVIDER_RESULT_REF_VERSION}:model={model}:"
        f"lang={language or 'auto'}:{configuration.reference_fragment}:"
        f"media={source_media_id.value}"
    )


class LocalAsrTranscriptionService:
    """Runs one local ASR engine for an intake and admits the result through the existing boundary."""

    def __init__(
        self,
        intake_query: TranscriptSourceIntakeQuery,
        source_media_query: SourceMediaQuery,
        admission_query: ProviderTranscriptAdmissionQuery,
        admission_service: ProviderTranscriptAdmissionService,
        source_verifier: SourceMediaLocationVerifier,
        engine_runner: LocalAsrEngineRunner,
        *,
        provider: str = FASTER_WHISPER_PROVIDER,
        configuration: LocalAsrProviderConfiguration = APPROVED_LOCAL_ASR_CONFIGURATION,
    ) -> None:
        self._intakes = intake_query
        self._source_media = source_media_query
        self._admissions = admission_query
        self._admission_service = admission_service
        self._source_verifier = source_verifier
        self._engine = engine_runner
        self._provider = provider
        self._configuration = configuration

    @property
    def configuration(self) -> LocalAsrProviderConfiguration:
        """The provider configuration every execution through this service uses (040 §15 L-15).

        It is fixed at construction, not per call, so no caller can select a different value on the production
        path. Tests that must exercise identity separation build a second service explicitly.
        """

        return self._configuration

    def transcribe(
        self,
        *,
        intake_id: str,
        model: str,
        language: str | None = None,
        device: str = DEFAULT_DEVICE,
        compute_type: str = DEFAULT_COMPUTE_TYPE,
    ) -> LocalAsrTranscriptionResult:
        if not isinstance(model, str) or not model.strip():
            raise LocalAsrError("model identifier must be a non-empty string")

        # Resolve the intake (persisted facts only); a malformed identity is rejected before any lookup.
        try:
            intake_identity = require_canonical_intake_id(intake_id)
        except ProviderTranscriptAdmissionError as error:
            raise LocalAsrIntakeError(str(error)) from error
        intake = self._intakes.get(intake_identity)
        if intake is None:
            raise LocalAsrIntakeError(
                "unknown transcript source intake: admit the Source Media as an intake first"
            )
        source_media_id = SourceMediaId(intake_identity.value.split(":", 1)[1])
        record = self._source_media.get(source_media_id)
        if record is None:
            raise LocalAsrIntakeError(
                "unknown source media: the intake references a missing Source Media record"
            )

        provider_result_ref = derive_provider_result_ref(
            source_media_id, model, language, self._configuration
        )

        # Reuse-before-rerun: if an equivalent result was already admitted, return it WITHOUT running the engine
        # (ordinary ASR non-determinism would otherwise conflict on replay).
        admission_identity = derive_provider_transcript_admission_identity(
            intake_identity, self._provider, model, provider_result_ref
        )
        existing = self._admissions.get(admission_identity)
        if existing is not None:
            return LocalAsrTranscriptionResult(
                admission=existing, created=False, executed=False
            )

        # Operational availability + fingerprint verification (does not change Media identity).
        media_path = self._source_verifier.verify(record)

        # Execute the concrete local engine (the only place external ASR work happens).
        result = self._engine.transcribe(
            media_path=media_path,
            model=model,
            language=language,
            device=device,
            compute_type=compute_type,
            condition_on_previous_text=self._configuration.condition_on_previous_text,
        )

        document = self._to_document(result, model, provider_result_ref)
        admission_result = self._admission_service.admit(
            intake_id=intake_identity.value, document=document
        )
        return LocalAsrTranscriptionResult(
            admission=admission_result.admission,
            created=admission_result.created,
            executed=True,
        )

    def _to_document(
        self, result: LocalAsrResult, model: str, provider_result_ref: str
    ) -> ProviderTranscriptDocument:
        try:
            return build_provider_transcript_document(
                {
                    "provider": self._provider,
                    "model": model,
                    "language": result.language,
                    "provider_result_ref": provider_result_ref,
                    "segments": [
                        {"start": float(segment.start), "end": float(segment.end), "text": segment.text}
                        for segment in result.segments
                    ],
                }
            )
        except ProviderTranscriptAdmissionError as error:
            raise LocalAsrOutputError(
                f"local ASR engine produced inadmissible output: {error}"
            ) from error


__all__ = [
    "APPROVED_LOCAL_ASR_CONFIGURATION",
    "DEFAULT_COMPUTE_TYPE",
    "DEFAULT_DEVICE",
    "FASTER_WHISPER_PROVIDER",
    "PROVIDER_RESULT_REF_VERSION",
    "LocalAsrDependencyError",
    "LocalAsrEngineError",
    "LocalAsrEngineRunner",
    "LocalAsrError",
    "LocalAsrIntakeError",
    "LocalAsrModelError",
    "LocalAsrOutputError",
    "LocalAsrProviderConfiguration",
    "LocalAsrResult",
    "LocalAsrSegment",
    "LocalAsrSourceChangedError",
    "LocalAsrSourceUnavailableError",
    "LocalAsrTranscriptionResult",
    "LocalAsrTranscriptionService",
    "ProviderTranscriptAdmissionQuery",
    "SourceMediaLocationVerifier",
    "SourceMediaQuery",
    "TranscriptSourceIntakeQuery",
    "derive_provider_result_ref",
]
