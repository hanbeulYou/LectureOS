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

from .local_asr_checkpoint import (
    CheckpointBinding,
    CheckpointDiscardReason,
    CheckpointSegment,
    ExecutionMode,
    LocalAsrCheckpointStore,
)
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


# The provider-native evidence family this engine reports (040 §15 QD-5). The name says both who
# produced the values and at what granularity, so a reader never has to guess whether a value is
# segment-scoped. The core models the *shape*; these field names stay faster-whisper's own.
FASTER_WHISPER_DECODE_EVIDENCE_KIND = "faster-whisper/decode-window"


@dataclass(frozen=True, slots=True)
class LocalAsrDecodeEvidence:
    """Provider-native decode evidence carried alongside a segment, recorded verbatim (QD-5, QD-7).

    Deliberately **not** named or typed as a segment confidence. faster-whisper reports these per
    *decode window*, and several segments in one window carry the identical values — measured on the
    preserved fixtures, 32 segments shared just 6 value sets. Renaming them to a segment-level
    semantic would state something the provider never said, which QD-7 forbids.

    ``window_ref`` is the provider's own window anchor (faster-whisper's ``seek``) stringified as-is.
    It is evidence for grouping, never an identity.
    """

    window_ref: str
    values: tuple[tuple[str, float], ...]


@dataclass(frozen=True, slots=True)
class LocalAsrSegment:
    """One timestamped segment returned by the local engine (seconds).

    ``decode_evidence`` is optional: an engine that reports none, or a checkpoint written before
    `PATCH-0045`, simply yields ``None`` — evidence unavailable, which is never quality-clean (QD-9).
    """

    start: float
    end: float
    text: str
    decode_evidence: LocalAsrDecodeEvidence | None = None


@dataclass(frozen=True, slots=True)
class LocalAsrResult:
    """The engine's raw result: truthful provider/model/language metadata and ordered segments."""

    provider: str
    model: str
    language: str | None
    segments: tuple[LocalAsrSegment, ...]


@dataclass(frozen=True, slots=True)
class LocalAsrTranscriptionResult:
    """The outcome: the admitted record, whether it was newly created, and whether the engine actually ran.

    `PATCH-0044` CP-21 adds the execution-mode disclosure: an operator must be able to tell which of
    CP-8's three paths a command took, and why a checkpoint was not used when one existed. These are
    statements about this command's outcome — never a progress API (L-14).
    """

    admission: ProviderTranscriptAdmission
    created: bool
    executed: bool
    mode: ExecutionMode = ExecutionMode.FRESH
    checkpoint_identity: str | None = None
    resumed_from: float | None = None
    checkpoint_discard_reason: CheckpointDiscardReason | None = None


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
        start_offset: float | None = None,
        on_segment=None,
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


def _decode_windows_of(segments) -> dict | None:
    """Group consecutive segments sharing identical decode evidence into windows (QD-7).

    Grouping is by **run of adjacent segments**, not by ``window_ref`` value, and that is deliberate.
    A resumed execution decodes from an explicit offset, so its provider-native anchors restart from
    zero and can repeat an anchor the pre-resume part already used; keying on the value would then
    merge two genuinely different decode windows into one. Runs cannot: the measured engine emits each
    window's segments contiguously and never revisits one, so a run is exactly a window, and a repeated
    anchor after a resume simply becomes a second window entry.

    Returns ``None`` when no segment carried evidence — evidence unavailable, not clean (QD-9).
    """

    windows: list[dict] = []
    current: dict | None = None
    current_key = None
    for ordinal, segment in enumerate(segments):
        evidence = getattr(segment, "decode_evidence", None)
        if evidence is None:
            # A gap is preserved as a gap: the window simply does not cover this ordinal.
            current = None
            current_key = None
            continue
        key = (evidence.window_ref, evidence.values)
        if current is None or key != current_key:
            current = {
                "window_ref": evidence.window_ref,
                "segment_ordinals": [ordinal],
                "values": {name: float(value) for name, value in evidence.values},
                "start": float(segment.start),
                "end": float(segment.end),
            }
            current_key = key
            windows.append(current)
        else:
            current["segment_ordinals"].append(ordinal)
            current["end"] = float(segment.end)
    if not windows:
        return None
    return {"kind": FASTER_WHISPER_DECODE_EVIDENCE_KIND, "windows": windows}


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
        checkpoint_store: LocalAsrCheckpointStore | None = None,
        engine_library: str = FASTER_WHISPER_PROVIDER,
        engine_version: str = "unknown",
    ) -> None:
        self._intakes = intake_query
        self._source_media = source_media_query
        self._admissions = admission_query
        self._admission_service = admission_service
        self._source_verifier = source_verifier
        self._engine = engine_runner
        self._provider = provider
        self._configuration = configuration
        # None means checkpointing is unavailable; CP-10 makes fresh execution always correct.
        self._checkpoints = checkpoint_store
        self._engine_library = engine_library
        self._engine_version = engine_version

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
        force_fresh: bool = False,
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
        # CP-8 step 1: canonical reuse wins without exception. The checkpoint is not consulted,
        # not read, and not resumed — a checkpoint alongside a canonical result is stale.
        existing = self._admissions.get(admission_identity)
        if existing is not None:
            return LocalAsrTranscriptionResult(
                admission=existing,
                created=False,
                executed=False,
                mode=ExecutionMode.REUSED,
            )

        # Operational availability + fingerprint verification (does not change Media identity).
        media_path = self._source_verifier.verify(record)

        binding = CheckpointBinding(
            provider_result_ref=provider_result_ref,
            device=device,
            compute_type=compute_type,
            engine_library=self._engine_library,
            engine_version=self._engine_version,
        )
        if self._checkpoints is None:
            return self._execute(
                intake_identity, provider_result_ref, model, language, device, compute_type,
                media_path, binding, prior=(), resume_from=None, mode=ExecutionMode.FRESH,
                discard_reason=None,
            )
        # CP-20: one owner per key for the whole inspect → decide → execute → append → admit → clean
        # span. Ownership is released by the OS if this process dies.
        with self._checkpoints.owned(binding):
            loaded = self._checkpoints.load(binding)
            if force_fresh or not loaded.resumable:
                # CP-19: an incompatible or corrupt checkpoint is discarded whole and the reason is
                # disclosed; it is never partially trusted or blended with a fresh run.
                self._checkpoints.begin(binding)
                return self._execute(
                    intake_identity, provider_result_ref, model, language, device, compute_type,
                    media_path, binding, prior=(), resume_from=None, mode=ExecutionMode.FRESH,
                    discard_reason=None if force_fresh else loaded.discard_reason,
                )
            prior = tuple(
                LocalAsrSegment(
                    start=s.start,
                    end=s.end,
                    text=s.text,
                    decode_evidence=(
                        None
                        if s.window_ref is None
                        else LocalAsrDecodeEvidence(window_ref=s.window_ref, values=s.values)
                    ),
                )
                for s in loaded.segments
            )
            return self._execute(
                intake_identity, provider_result_ref, model, language, device, compute_type,
                media_path, binding, prior=prior, resume_from=loaded.resume_from,
                mode=ExecutionMode.RESUMED, discard_reason=None,
            )

    def _execute(
        self, intake_identity, provider_result_ref, model, language, device, compute_type,
        media_path, binding, *, prior, resume_from, mode, discard_reason,
    ) -> LocalAsrTranscriptionResult:
        # CP-13: checkpointed segments are adopted as they are. They are never regenerated and never
        # compared for equality — ASR is non-deterministic, so an equality contract would be
        # unsatisfiable and would make resume permanently impossible.
        # CP-11: the checkpoint is appended **as each segment is produced**, not after the engine
        # finishes. Recording only at the end would leave a 90-minute run unprotected for its whole
        # duration, which is the exact failure this contract exists to prevent.
        next_ordinal = len(prior)

        def _record(segment) -> None:
            nonlocal next_ordinal
            if self._checkpoints is None:
                return
            evidence = getattr(segment, "decode_evidence", None)
            self._checkpoints.append(
                binding,
                CheckpointSegment(
                    next_ordinal,
                    segment.start,
                    segment.end,
                    segment.text,
                    window_ref=None if evidence is None else evidence.window_ref,
                    values=() if evidence is None else evidence.values,
                ),
            )
            next_ordinal += 1

        result = self._engine.transcribe(
            media_path=media_path,
            model=model,
            language=language,
            device=device,
            compute_type=compute_type,
            condition_on_previous_text=self._configuration.condition_on_previous_text,
            start_offset=resume_from,
            on_segment=_record if self._checkpoints is not None else None,
        )
        produced = list(result.segments)
        assembled = LocalAsrResult(
            provider=result.provider,
            model=result.model,
            language=result.language,
            segments=prior + tuple(produced),
        )
        # CP-14: the assembled whole goes through the unchanged §14 admission. No partial credit,
        # no per-segment admission, and no repository write before it. The resume join is validated
        # there like any other boundary.
        document = self._to_document(assembled, model, provider_result_ref)
        admission_result = self._admission_service.admit(
            intake_id=intake_identity.value, document=document
        )
        if self._checkpoints is not None:
            # CP-17: the canonical result now exists, so keeping the checkpoint would leave a copy
            # of canonical content outside the repository.
            self._checkpoints.delete(binding)
        return LocalAsrTranscriptionResult(
            admission=admission_result.admission,
            created=admission_result.created,
            executed=True,
            mode=mode,
            checkpoint_identity=binding.identity if self._checkpoints is not None else None,
            resumed_from=resume_from,
            checkpoint_discard_reason=discard_reason,
        )

    def _to_document(
        self, result: LocalAsrResult, model: str, provider_result_ref: str
    ) -> ProviderTranscriptDocument:
        payload = {
            "provider": self._provider,
            "model": model,
            "language": result.language,
            "provider_result_ref": provider_result_ref,
            "segments": [
                {"start": float(segment.start), "end": float(segment.end), "text": segment.text}
                for segment in result.segments
            ],
        }
        evidence = _decode_windows_of(result.segments)
        if evidence is not None:
            payload["provider_evidence"] = evidence
        try:
            return build_provider_transcript_document(payload)
        except ProviderTranscriptAdmissionError as error:
            raise LocalAsrOutputError(
                f"local ASR engine produced inadmissible output: {error}"
            ) from error


__all__ = [
    "APPROVED_LOCAL_ASR_CONFIGURATION",
    "DEFAULT_COMPUTE_TYPE",
    "DEFAULT_DEVICE",
    "FASTER_WHISPER_DECODE_EVIDENCE_KIND",
    "FASTER_WHISPER_PROVIDER",
    "PROVIDER_RESULT_REF_VERSION",
    "LocalAsrDecodeEvidence",
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
