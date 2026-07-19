"""Transcript application service preserving source, revision, and execution lineage."""

from lectureos.execution.boundaries import ExecutionQueryBoundary
from lectureos.execution.identities import DomainResultId, ProcessingRunId, UnitExecutionId
from lectureos.execution.models import DomainResultReference, ProcessingState
from lectureos.execution.repositories import (
    DomainResultReferenceRepository,
    InMemoryRepository,
)

from .identities import (
    CorrectionCandidateId,
    ProviderTranscriptResultId,
    TranscriptId,
    TranscriptRevisionId,
    TranscriptSegmentId,
    TranscriptValidationId,
)
from .models import (
    CorrectionCandidate,
    CorrectedTranscriptRevision,
    ProviderTranscriptResult,
    RawTranscript,
    TranscriptSegment,
    TranscriptValidation,
)
from .persistence import (
    AtomicCorrectionCandidatePersistence,
    AtomicRawTranscriptPersistence,
    InMemoryAtomicCorrectionCandidatePersistence,
    InMemoryAtomicRawTranscriptPersistence,
)
from .repositories import (
    CorrectionCandidateRepository,
    ProviderTranscriptResultRepository,
    RawTranscriptRepository,
    TranscriptSegmentRepository,
)


class TranscriptService:
    def __init__(
        self,
        execution_query: ExecutionQueryBoundary,
        *,
        provider_results: ProviderTranscriptResultRepository | None = None,
        raw_transcripts: RawTranscriptRepository | None = None,
        segments: TranscriptSegmentRepository | None = None,
        candidates: CorrectionCandidateRepository | None = None,
        domain_results: DomainResultReferenceRepository | None = None,
        atomic_raw_persistence: AtomicRawTranscriptPersistence | None = None,
        atomic_candidate_persistence: AtomicCorrectionCandidatePersistence | None = None,
    ) -> None:
        self._execution_query = execution_query
        self.provider_results = (
            provider_results if provider_results is not None else InMemoryRepository()
        )
        self.raw_transcripts = (
            raw_transcripts if raw_transcripts is not None else InMemoryRepository()
        )
        self.revisions: InMemoryRepository[
            TranscriptRevisionId, CorrectedTranscriptRevision
        ] = InMemoryRepository()
        self.segments = segments if segments is not None else InMemoryRepository()
        self.candidates = candidates if candidates is not None else InMemoryRepository()
        self.validations: InMemoryRepository[
            TranscriptValidationId, TranscriptValidation
        ] = InMemoryRepository()
        self.domain_results = (
            domain_results if domain_results is not None else InMemoryRepository()
        )
        self._atomic_raw_persistence = (
            atomic_raw_persistence
            if atomic_raw_persistence is not None
            else InMemoryAtomicRawTranscriptPersistence(
                self.raw_transcripts,
                self.segments,
                self.domain_results,
            )
        )
        self._atomic_candidate_persistence = (
            atomic_candidate_persistence
            if atomic_candidate_persistence is not None
            else InMemoryAtomicCorrectionCandidatePersistence(
                self.candidates,
                self.domain_results,
            )
        )

    def register_provider_result(self, result: ProviderTranscriptResult) -> None:
        self._require_new(self.provider_results, result.identity, "provider transcript result")
        self._require_execution(result.run_id, result.unit_execution_id)
        self.provider_results.save(result)

    def create_raw_transcript(
        self, transcript: RawTranscript, segments: tuple[TranscriptSegment, ...]
    ) -> None:
        self._require_new(self.raw_transcripts, transcript.identity, "raw transcript")
        self._require_new(self.domain_results, transcript.domain_result_id, "domain result")
        provider_result = self.provider_results.get(transcript.provider_result_id)
        if provider_result is None:
            raise KeyError("unknown provider transcript result")
        self._require_execution(transcript.run_id, transcript.unit_execution_id)
        if transcript.source_media_id != provider_result.source_media_id:
            raise ValueError("raw transcript source media must match provider result")
        if transcript.source_timeline_id != provider_result.source_timeline_id:
            raise ValueError("raw transcript source timeline must match provider result")
        if transcript.run_id != provider_result.run_id:
            raise ValueError("raw transcript run must match provider result")
        if transcript.unit_execution_id != provider_result.unit_execution_id:
            raise ValueError("raw transcript unit execution must match provider result")
        self._validate_segments(
            transcript.identity,
            transcript.source_timeline_id,
            transcript.segment_ids,
            segments,
            allow_existing=False,
        )

        result = DomainResultReference(
            identity=transcript.domain_result_id,
            kind="raw_transcript",
            source_media=transcript.source_media_id,
            source_timeline=transcript.source_timeline_id,
        )
        self._atomic_raw_persistence.persist_raw_transcript(
            transcript=transcript,
            segments=segments,
            result=result,
        )

    def create_correction_candidate(self, candidate: CorrectionCandidate) -> None:
        self._require_new(self.candidates, candidate.identity, "correction candidate")
        self._require_new(self.domain_results, candidate.domain_result_id, "domain result")
        raw = self._require_raw(candidate.transcript_id)
        segment = self.segments.get(candidate.segment_id)
        if segment is None:
            raise KeyError("unknown transcript segment")
        if segment.transcript_id != candidate.transcript_id:
            raise ValueError("candidate segment must belong to target transcript")
        if candidate.target_revision_id is not None:
            revision = self._require_revision(candidate.target_revision_id)
            if revision.transcript_id != candidate.transcript_id:
                raise ValueError("candidate revision must belong to target transcript")
        self._require_execution(candidate.run_id, candidate.unit_execution_id)

        upstream = (
            self._require_revision(candidate.target_revision_id).domain_result_id
            if candidate.target_revision_id is not None
            else raw.domain_result_id
        )
        result = DomainResultReference(
            identity=candidate.domain_result_id,
            kind="transcript_correction_candidate",
            source_media=raw.source_media_id,
            source_timeline=raw.source_timeline_id,
            upstream_results=(upstream,),
        )
        self._atomic_candidate_persistence.persist_correction_candidate(
            candidate=candidate,
            result=result,
        )

    def create_corrected_revision(
        self,
        revision: CorrectedTranscriptRevision,
        segments: tuple[TranscriptSegment, ...],
    ) -> None:
        self._require_new(self.revisions, revision.identity, "corrected transcript revision")
        self._require_new(self.domain_results, revision.domain_result_id, "domain result")
        raw = self._require_raw(revision.transcript_id)
        parent_result_id = self._validate_revision_parent(revision)
        self._require_execution(revision.run_id, revision.unit_execution_id)
        for candidate_id in revision.correction_candidate_ids:
            candidate = self.candidates.get(candidate_id)
            if candidate is None:
                raise KeyError("unknown correction candidate")
            if candidate.transcript_id != revision.transcript_id:
                raise ValueError("correction candidate must belong to revision lineage")
        self._validate_segments(
            revision.transcript_id,
            raw.source_timeline_id,
            revision.segment_ids,
            segments,
            allow_existing=True,
        )

        for segment in segments:
            if self.segments.get(segment.identity) is None:
                self.segments.save(segment)
        self.revisions.save(revision)
        self.domain_results.save(
            DomainResultReference(
                identity=revision.domain_result_id,
                kind="corrected_transcript_revision",
                source_media=raw.source_media_id,
                source_timeline=raw.source_timeline_id,
                upstream_results=(parent_result_id,),
            )
        )

    def record_validation(self, validation: TranscriptValidation) -> None:
        self._require_new(self.validations, validation.identity, "transcript validation")
        if validation.target_transcript_id is not None:
            self._require_raw(validation.target_transcript_id)
        if validation.target_revision_id is not None:
            self._require_revision(validation.target_revision_id)
        self._require_execution(validation.run_id, validation.unit_execution_id)
        self.validations.save(validation)

    def get_provider_result(
        self, identity: ProviderTranscriptResultId
    ) -> ProviderTranscriptResult | None:
        return self.provider_results.get(identity)

    def get_raw_transcript(self, identity: TranscriptId) -> RawTranscript | None:
        return self.raw_transcripts.get(identity)

    def get_corrected_revision(
        self, identity: TranscriptRevisionId
    ) -> CorrectedTranscriptRevision | None:
        return self.revisions.get(identity)

    def get_segment(self, identity: TranscriptSegmentId) -> TranscriptSegment | None:
        return self.segments.get(identity)

    def get_candidate(self, identity: CorrectionCandidateId) -> CorrectionCandidate | None:
        return self.candidates.get(identity)

    def get_validation(
        self, identity: TranscriptValidationId
    ) -> TranscriptValidation | None:
        return self.validations.get(identity)

    def get_domain_result_reference(
        self, identity: DomainResultId
    ) -> DomainResultReference | None:
        return self.domain_results.get(identity)

    def get_lineage(
        self, transcript_id: TranscriptId
    ) -> tuple[RawTranscript, tuple[CorrectedTranscriptRevision, ...]] | None:
        raw = self.raw_transcripts.get(transcript_id)
        if raw is None:
            return None
        revisions = tuple(
            revision
            for revision in self.revisions.all()
            if revision.transcript_id == transcript_id
        )
        return raw, revisions

    def _validate_revision_parent(self, revision: CorrectedTranscriptRevision) -> DomainResultId:
        if revision.parent_raw_transcript_id is not None:
            parent = self._require_raw(revision.parent_raw_transcript_id)
            if parent.identity != revision.transcript_id:
                raise ValueError("raw parent must be the revision transcript lineage")
            return parent.domain_result_id
        parent_revision = self._require_revision(revision.parent_revision_id)
        if parent_revision.transcript_id != revision.transcript_id:
            raise ValueError("parent revision must belong to transcript lineage")
        return parent_revision.domain_result_id

    def _validate_segments(
        self,
        transcript_id: TranscriptId,
        source_timeline_id,
        expected_ids: tuple[TranscriptSegmentId, ...],
        segments: tuple[TranscriptSegment, ...],
        *,
        allow_existing: bool,
    ) -> None:
        actual_ids = tuple(segment.identity for segment in segments)
        if actual_ids != expected_ids:
            raise ValueError("segment references must preserve provided source order")
        if len(set(actual_ids)) != len(actual_ids):
            raise ValueError("transcript segment identities must be unique")
        if len({segment.source_order for segment in segments}) != len(segments):
            raise ValueError("transcript segment source order must be unique")
        source_orders = tuple(segment.source_order for segment in segments)
        if source_orders != tuple(sorted(source_orders)):
            raise ValueError("transcript segments must preserve source order")
        for segment in segments:
            existing = self.segments.get(segment.identity)
            if existing is not None and (not allow_existing or existing != segment):
                raise ValueError("transcript segment identity already exists")
            if segment.transcript_id != transcript_id:
                raise ValueError("segment must belong to transcript lineage")
            if segment.source_timeline_id not in (None, source_timeline_id):
                raise ValueError("segment source timeline must match transcript")

    def _require_execution(
        self, run_id: ProcessingRunId, unit_execution_id: UnitExecutionId
    ) -> None:
        run = self._execution_query.get_run(run_id)
        if run is None:
            raise KeyError("unknown processing run")
        execution = self._execution_query.get_unit_execution(unit_execution_id)
        if execution is None:
            raise KeyError("unknown unit execution")
        if execution.run_id != run_id:
            raise ValueError("unit execution must belong to processing run")
        if execution.state is not ProcessingState.RUNNING:
            raise ValueError("transcript output requires a running unit execution")

    def _require_raw(self, identity: TranscriptId) -> RawTranscript:
        transcript = self.raw_transcripts.get(identity)
        if transcript is None:
            raise KeyError("unknown raw transcript")
        return transcript

    def _require_revision(
        self, identity: TranscriptRevisionId | None
    ) -> CorrectedTranscriptRevision:
        if identity is None:
            raise KeyError("missing corrected transcript revision")
        revision = self.revisions.get(identity)
        if revision is None:
            raise KeyError("unknown corrected transcript revision")
        return revision

    @staticmethod
    def _require_new(repository, identity, label: str) -> None:
        if repository.get(identity) is not None:
            raise ValueError(f"{label} identity already exists")
