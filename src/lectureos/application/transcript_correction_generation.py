"""Provider-independent Application contract for Transcript correction proposals."""

from dataclasses import dataclass, replace
from math import isfinite
from typing import Protocol

from lectureos.execution.identities import (
    CapabilityReference,
    DomainResultId,
    PluginReference,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)
from lectureos.execution.models import DomainResultReference, ProcessingState
from lectureos.execution.boundaries import ExecutionQueryBoundary
from lectureos.transcript.boundaries import (
    TranscriptQueryBoundary,
    TranscriptStructuralValidationBoundary,
)
from lectureos.transcript.identities import (
    CorrectionCandidateId,
    TranscriptId,
    TranscriptRevisionId,
    TranscriptSegmentId,
    TranscriptValidationId,
)
from lectureos.transcript.models import (
    CorrectionCandidate,
    CorrectedTranscriptRevision,
    TranscriptSegment,
    TranscriptValidation,
)


@dataclass(frozen=True, slots=True)
class CorrectionSegmentContext:
    """One canonical source Segment exposed to a correction capability."""

    identity: TranscriptSegmentId
    text: str
    source_order: int
    source_timeline_id: SourceTimelineId | None
    start: float | None = None
    end: float | None = None
    speaker_label: str | None = None
    confidence: float | None = None
    uncertainty: float | None = None


@dataclass(frozen=True, slots=True)
class CorrectionGenerationRequest:
    """Immutable Application context; never a provider-specific payload."""

    transcript_id: TranscriptId
    parent_revision_id: TranscriptRevisionId | None
    source_media_id: SourceMediaId
    source_timeline_id: SourceTimelineId
    run_id: ProcessingRunId
    unit_execution_id: UnitExecutionId
    capability: CapabilityReference
    segments: tuple[CorrectionSegmentContext, ...]


@dataclass(frozen=True, slots=True)
class CorrectionProposal:
    """Provider-neutral suggestion that has not become canonical Domain state."""

    target_segment_id: TranscriptSegmentId
    proposed_text: str
    rationale: str
    evidence: tuple[str, ...] = ()
    confidence: float | None = None
    uncertainty: float | None = None
    capability: CapabilityReference | None = None
    plugin_reference: PluginReference | None = None
    provider_reference: str | None = None


class CorrectionGenerationFailure(RuntimeError):
    """The correction capability could not produce a usable response."""


class CorrectionGenerationPort(Protocol):
    def generate_corrections(
        self, request: CorrectionGenerationRequest
    ) -> tuple[CorrectionProposal, ...]: ...


class AtomicGeneratedCorrectionPersistence(Protocol):
    def persist_generated_correction(
        self,
        *,
        candidates: tuple[CorrectionCandidate, ...],
        candidate_results: tuple[DomainResultReference, ...],
        replacement_segments: tuple[TranscriptSegment, ...],
        revision: CorrectedTranscriptRevision,
        revision_result: DomainResultReference,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class CorrectionCandidateIdentityPlan:
    candidate_id: CorrectionCandidateId
    candidate_result_id: DomainResultId
    replacement_segment_id: TranscriptSegmentId


@dataclass(frozen=True, slots=True)
class CorrectionGenerationIdentityPlan:
    candidates: tuple[CorrectionCandidateIdentityPlan, ...]
    revision_id: TranscriptRevisionId
    revision_result_id: DomainResultId
    validation_id: TranscriptValidationId


@dataclass(frozen=True, slots=True)
class PreparedCorrectionGeneration:
    request: CorrectionGenerationRequest
    proposals: tuple[CorrectionProposal, ...]
    candidates: tuple[CorrectionCandidate, ...]
    replacement_segments: tuple[TranscriptSegment, ...]
    revision: CorrectedTranscriptRevision | None
    candidate_results: tuple[DomainResultReference, ...]
    revision_result: DomainResultReference | None
    validation_id: TranscriptValidationId | None
    validation: TranscriptValidation | None = None


class TranscriptCorrectionGenerationError(ValueError):
    """A capability response cannot safely become canonical correction state."""


class TranscriptCorrectionGenerationService:
    def __init__(
        self,
        transcript_query: TranscriptQueryBoundary,
        execution_query: ExecutionQueryBoundary,
        generation: CorrectionGenerationPort,
        persistence: AtomicGeneratedCorrectionPersistence | None = None,
        validation: TranscriptStructuralValidationBoundary | None = None,
    ) -> None:
        self._transcripts = transcript_query
        self._executions = execution_query
        self._generation = generation
        self._persistence = persistence
        self._validation = validation

    def generate_correction(self, **kwargs) -> PreparedCorrectionGeneration:
        prepared = self.prepare_correction(**kwargs)
        if prepared.revision is None:
            return prepared
        if self._persistence is None:
            raise RuntimeError("generated correction persistence is not configured")
        if self._validation is None:
            raise RuntimeError("transcript structural validation is not configured")
        self._persistence.persist_generated_correction(
            candidates=prepared.candidates,
            candidate_results=prepared.candidate_results,
            replacement_segments=prepared.replacement_segments,
            revision=prepared.revision,
            revision_result=prepared.revision_result,
        )
        validation = self._validation.validate_corrected_revision(
            validation_id=prepared.validation_id,
            revision_id=prepared.revision.identity,
            run_id=prepared.request.run_id,
            unit_execution_id=prepared.request.unit_execution_id,
        )
        return replace(prepared, validation=validation)

    def prepare_correction(
        self,
        *,
        transcript_id: TranscriptId,
        parent_revision_id: TranscriptRevisionId | None,
        run_id: ProcessingRunId,
        unit_execution_id: UnitExecutionId,
        capability: CapabilityReference,
        identities: CorrectionGenerationIdentityPlan,
    ) -> PreparedCorrectionGeneration:
        raw = self._transcripts.get_raw_transcript(transcript_id)
        if raw is None:
            raise KeyError("unknown raw transcript")
        self._require_running_execution(run_id, unit_execution_id)
        parent_revision, parent_segment_ids, parent_result_id = self._resolve_parent(
            raw, parent_revision_id
        )
        source_segments = tuple(
            self._require_segment(identity) for identity in parent_segment_ids
        )
        request = CorrectionGenerationRequest(
            transcript_id=raw.identity,
            parent_revision_id=parent_revision.identity if parent_revision else None,
            source_media_id=raw.source_media_id,
            source_timeline_id=raw.source_timeline_id,
            run_id=run_id,
            unit_execution_id=unit_execution_id,
            capability=capability,
            segments=tuple(self._context(segment) for segment in source_segments),
        )
        proposals = self._generation.generate_corrections(request)
        if not isinstance(proposals, tuple):
            raise TranscriptCorrectionGenerationError(
                "correction capability must return an immutable proposal tuple"
            )
        if not proposals:
            if identities.candidates:
                raise TranscriptCorrectionGenerationError(
                    "zero proposals require an empty candidate identity plan"
                )
            return PreparedCorrectionGeneration(
                request, (), (), (), None, (), None, None
            )
        if len(proposals) != len(identities.candidates):
            raise TranscriptCorrectionGenerationError(
                "proposal and candidate identity counts must match"
            )

        self._validate_identity_plan(identities)
        self._validate_new_revision_identities(identities)
        source_by_id = {segment.identity: segment for segment in source_segments}
        seen_targets = set()
        candidates = []
        replacements = []
        candidate_results = []
        for proposal, identity_plan in zip(proposals, identities.candidates):
            source = source_by_id.get(proposal.target_segment_id)
            self._validate_proposal(proposal, source, capability, seen_targets)
            self._validate_new_candidate_identities(identity_plan)
            candidate = CorrectionCandidate(
                identity=identity_plan.candidate_id,
                domain_result_id=identity_plan.candidate_result_id,
                transcript_id=raw.identity,
                segment_id=source.identity,
                proposed_text=proposal.proposed_text,
                rationale=proposal.rationale,
                run_id=run_id,
                unit_execution_id=unit_execution_id,
                target_revision_id=parent_revision.identity if parent_revision else None,
                evidence=proposal.evidence,
                confidence=proposal.confidence,
                uncertainty=proposal.uncertainty,
                capability=proposal.capability or capability,
                plugin_reference=proposal.plugin_reference,
                provider_reference=proposal.provider_reference,
            )
            replacement = TranscriptSegment(
                identity=identity_plan.replacement_segment_id,
                transcript_id=raw.identity,
                source_timeline_id=source.source_timeline_id,
                text=proposal.proposed_text,
                source_order=source.source_order,
                start=source.start,
                end=source.end,
                speaker_label=source.speaker_label,
                confidence=proposal.confidence,
                uncertainty=proposal.uncertainty,
                replaces_segment_id=source.identity,
            )
            candidates.append(candidate)
            replacements.append(replacement)
            candidate_results.append(
                DomainResultReference(
                    identity=candidate.domain_result_id,
                    kind="transcript_correction_candidate",
                    source_media=raw.source_media_id,
                    source_timeline=raw.source_timeline_id,
                    upstream_results=(parent_result_id,),
                )
            )

        replacement_by_source = {
            segment.replaces_segment_id: segment for segment in replacements
        }
        final_segments = tuple(
            replacement_by_source.get(segment.identity, segment)
            for segment in source_segments
        )
        revision = CorrectedTranscriptRevision(
            identity=identities.revision_id,
            transcript_id=raw.identity,
            domain_result_id=identities.revision_result_id,
            run_id=run_id,
            unit_execution_id=unit_execution_id,
            segment_ids=tuple(segment.identity for segment in final_segments),
            parent_raw_transcript_id=raw.identity if parent_revision is None else None,
            parent_revision_id=parent_revision.identity if parent_revision else None,
            correction_candidate_ids=tuple(
                candidate.identity for candidate in candidates
            ),
        )
        revision_result = DomainResultReference(
            identity=revision.domain_result_id,
            kind="corrected_transcript_revision",
            source_media=raw.source_media_id,
            source_timeline=raw.source_timeline_id,
            upstream_results=(parent_result_id,),
        )
        return PreparedCorrectionGeneration(
            request=request,
            proposals=proposals,
            candidates=tuple(candidates),
            replacement_segments=tuple(replacements),
            revision=revision,
            candidate_results=tuple(candidate_results),
            revision_result=revision_result,
            validation_id=identities.validation_id,
        )

    def _resolve_parent(self, raw, parent_revision_id):
        if parent_revision_id is None:
            return None, raw.segment_ids, raw.domain_result_id
        revision = self._transcripts.get_corrected_revision(parent_revision_id)
        if revision is None:
            raise KeyError("unknown parent corrected transcript revision")
        if revision.transcript_id != raw.identity:
            raise TranscriptCorrectionGenerationError(
                "parent revision belongs to another transcript lineage"
            )
        return revision, revision.segment_ids, revision.domain_result_id

    def _require_segment(self, identity):
        segment = self._transcripts.get_segment(identity)
        if segment is None:
            raise KeyError("unknown parent transcript segment")
        return segment

    def _require_running_execution(self, run_id, unit_execution_id) -> None:
        run = self._executions.get_run(run_id)
        if run is None:
            raise KeyError("unknown processing run")
        execution = self._executions.get_unit_execution(unit_execution_id)
        if execution is None:
            raise KeyError("unknown unit execution")
        if execution.run_id != run.identity:
            raise TranscriptCorrectionGenerationError(
                "unit execution must belong to processing run"
            )
        if execution.state is not ProcessingState.RUNNING:
            raise TranscriptCorrectionGenerationError(
                "correction generation requires a running unit execution"
            )

    @staticmethod
    def _context(segment: TranscriptSegment) -> CorrectionSegmentContext:
        return CorrectionSegmentContext(
            identity=segment.identity,
            text=segment.text,
            source_order=segment.source_order,
            source_timeline_id=segment.source_timeline_id,
            start=segment.start,
            end=segment.end,
            speaker_label=segment.speaker_label,
            confidence=segment.confidence,
            uncertainty=segment.uncertainty,
        )

    @staticmethod
    def _validate_proposal(proposal, source, capability, seen_targets) -> None:
        if not isinstance(proposal, CorrectionProposal):
            raise TranscriptCorrectionGenerationError(
                "correction capability returned an unsupported proposal"
            )
        if source is None:
            raise TranscriptCorrectionGenerationError(
                "correction proposal targets a Segment outside the parent"
            )
        if source.identity in seen_targets:
            raise TranscriptCorrectionGenerationError(
                "correction proposals must target distinct Segments"
            )
        seen_targets.add(source.identity)
        if not proposal.proposed_text.strip():
            raise TranscriptCorrectionGenerationError(
                "correction proposal text must not be blank"
            )
        if not proposal.rationale.strip():
            raise TranscriptCorrectionGenerationError(
                "correction proposal rationale must not be blank"
            )
        if proposal.provider_reference is not None and not proposal.provider_reference.strip():
            raise TranscriptCorrectionGenerationError(
                "provider reference must not be blank"
            )
        if proposal.capability is not None and proposal.capability != capability:
            raise TranscriptCorrectionGenerationError(
                "proposal capability must match requested capability"
            )
        for value in (proposal.confidence, proposal.uncertainty):
            if value is not None and not isfinite(value):
                raise TranscriptCorrectionGenerationError(
                    "proposal confidence and uncertainty must be finite"
                )

    def _validate_new_revision_identities(
        self, identities: CorrectionGenerationIdentityPlan
    ) -> None:
        if self._transcripts.get_corrected_revision(identities.revision_id) is not None:
            raise TranscriptCorrectionGenerationError("revision identity already exists")
        if self._transcripts.get_domain_result_reference(
            identities.revision_result_id
        ) is not None:
            raise TranscriptCorrectionGenerationError(
                "revision result identity already exists"
            )

    @staticmethod
    def _validate_identity_plan(identities: CorrectionGenerationIdentityPlan) -> None:
        candidate_ids = tuple(item.candidate_id for item in identities.candidates)
        result_ids = (
            *(item.candidate_result_id for item in identities.candidates),
            identities.revision_result_id,
        )
        segment_ids = tuple(
            item.replacement_segment_id for item in identities.candidates
        )
        if len(set(candidate_ids)) != len(candidate_ids):
            raise TranscriptCorrectionGenerationError(
                "candidate identity plan must be unique"
            )
        if len(set(result_ids)) != len(result_ids):
            raise TranscriptCorrectionGenerationError(
                "Domain Result identity plan must be unique"
            )
        if len(set(segment_ids)) != len(segment_ids):
            raise TranscriptCorrectionGenerationError(
                "replacement Segment identity plan must be unique"
            )

    def _validate_new_candidate_identities(
        self, identities: CorrectionCandidateIdentityPlan
    ) -> None:
        if self._transcripts.get_candidate(identities.candidate_id) is not None:
            raise TranscriptCorrectionGenerationError("candidate identity already exists")
        if self._transcripts.get_domain_result_reference(
            identities.candidate_result_id
        ) is not None:
            raise TranscriptCorrectionGenerationError(
                "candidate result identity already exists"
            )
        if self._transcripts.get_segment(identities.replacement_segment_id) is not None:
            raise TranscriptCorrectionGenerationError(
                "replacement Segment identity already exists"
            )


__all__ = [
    "AtomicGeneratedCorrectionPersistence",
    "CorrectionCandidateIdentityPlan",
    "CorrectionGenerationFailure",
    "CorrectionGenerationIdentityPlan",
    "CorrectionGenerationPort",
    "CorrectionGenerationRequest",
    "CorrectionProposal",
    "CorrectionSegmentContext",
    "PreparedCorrectionGeneration",
    "TranscriptCorrectionGenerationError",
    "TranscriptCorrectionGenerationService",
]
