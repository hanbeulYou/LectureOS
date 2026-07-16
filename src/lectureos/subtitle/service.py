"""Subtitle application service preserving Transcript and execution provenance."""

from lectureos.execution.boundaries import ExecutionQueryBoundary
from lectureos.execution.identities import DomainResultId, ProcessingRunId, UnitExecutionId
from lectureos.execution.models import DomainResultReference, ProcessingState
from lectureos.execution.repositories import InMemoryRepository
from lectureos.transcript.boundaries import TranscriptQueryBoundary

from .identities import (
    SubtitleCandidateId,
    SubtitleCueId,
    SubtitleRevisionId,
    SubtitleValidationFindingId,
    SubtitleValidationId,
)
from .models import (
    SubtitleCandidate,
    SubtitleCue,
    SubtitleRevision,
    SubtitleValidation,
    SubtitleValidationFinding,
)


class SubtitleService:
    def __init__(
        self,
        transcript_query: TranscriptQueryBoundary,
        execution_query: ExecutionQueryBoundary,
    ) -> None:
        self._transcript_query = transcript_query
        self._execution_query = execution_query
        self.cues: InMemoryRepository[SubtitleCueId, SubtitleCue] = InMemoryRepository()
        self.candidates: InMemoryRepository[
            SubtitleCandidateId, SubtitleCandidate
        ] = InMemoryRepository()
        self.revisions: InMemoryRepository[
            SubtitleRevisionId, SubtitleRevision
        ] = InMemoryRepository()
        self.validations: InMemoryRepository[
            SubtitleValidationId, SubtitleValidation
        ] = InMemoryRepository()
        self.findings: InMemoryRepository[
            SubtitleValidationFindingId, SubtitleValidationFinding
        ] = InMemoryRepository()
        self.domain_results: InMemoryRepository[
            DomainResultId, DomainResultReference
        ] = InMemoryRepository()

    def create_candidate(
        self, candidate: SubtitleCandidate, cues: tuple[SubtitleCue, ...]
    ) -> None:
        self._require_new(self.candidates, candidate.identity, "subtitle candidate")
        self._require_new(self.domain_results, candidate.domain_result_id, "domain result")
        raw, source_result = self._resolve_transcript_source(
            candidate.source_transcript_id, candidate.source_revision_id
        )
        if candidate.source_media_id != raw.source_media_id:
            raise ValueError("subtitle source media must match Transcript lineage")
        if candidate.source_timeline_id != raw.source_timeline_id:
            raise ValueError("subtitle Source Timeline must match Transcript lineage")
        self._require_execution(candidate.run_id, candidate.unit_execution_id)
        self._validate_cues(
            candidate.subtitle_id,
            candidate.source_transcript_id,
            candidate.source_revision_id,
            candidate.source_timeline_id,
            candidate.cue_ids,
            cues,
            allow_existing=False,
        )
        for cue in cues:
            self.cues.save(cue)
        self.candidates.save(candidate)
        self.domain_results.save(
            DomainResultReference(
                identity=candidate.domain_result_id,
                kind="subtitle_candidate",
                source_media=candidate.source_media_id,
                source_timeline=candidate.source_timeline_id,
                upstream_results=(source_result,),
            )
        )

    def create_revision(
        self, revision: SubtitleRevision, cues: tuple[SubtitleCue, ...]
    ) -> None:
        self._require_new(self.revisions, revision.identity, "subtitle revision")
        self._require_new(self.domain_results, revision.domain_result_id, "domain result")
        self._validate_revision_cycle(revision)
        parent, upstream = self._resolve_subtitle_parent(revision)
        self._require_execution(revision.run_id, revision.unit_execution_id)
        source_transcript_id, source_revision_id, timeline = self._parent_source(parent)
        self._validate_cues(
            revision.subtitle_id,
            source_transcript_id,
            source_revision_id,
            timeline,
            revision.cue_ids,
            cues,
            allow_existing=True,
        )
        for cue in cues:
            if self.cues.get(cue.identity) is None:
                self.cues.save(cue)
        self.revisions.save(revision)
        self.domain_results.save(
            DomainResultReference(
                identity=revision.domain_result_id,
                kind="subtitle_revision",
                source_media=self._require_raw(source_transcript_id).source_media_id,
                source_timeline=timeline,
                upstream_results=(upstream,),
            )
        )

    def record_validation(
        self,
        validation: SubtitleValidation,
        findings: tuple[SubtitleValidationFinding, ...],
    ) -> None:
        self._require_new(self.validations, validation.identity, "subtitle validation")
        self._require_execution(validation.run_id, validation.unit_execution_id)
        if validation.target_candidate_id is not None:
            if self.candidates.get(validation.target_candidate_id) is None:
                raise KeyError("unknown subtitle candidate")
        if validation.target_revision_id is not None:
            if self.revisions.get(validation.target_revision_id) is None:
                raise KeyError("unknown subtitle revision")
        if tuple(item.identity for item in findings) != validation.finding_ids:
            raise ValueError("subtitle validation finding references must match")
        for finding in findings:
            self._require_new(self.findings, finding.identity, "subtitle validation finding")
            if finding.validation_id != validation.identity:
                raise ValueError("subtitle finding must belong to validation")
        for finding in findings:
            self.findings.save(finding)
        self.validations.save(validation)

    def get_candidate(self, identity):
        return self.candidates.get(identity)

    def get_revision(self, identity):
        return self.revisions.get(identity)

    def get_cue(self, identity):
        return self.cues.get(identity)

    def get_validation(self, identity):
        return self.validations.get(identity)

    def get_validation_finding(self, identity):
        return self.findings.get(identity)

    def get_domain_result_reference(self, identity):
        return self.domain_results.get(identity)

    def get_lineage(self, subtitle_id):
        candidates = tuple(x for x in self.candidates.all() if x.subtitle_id == subtitle_id)
        revisions = tuple(x for x in self.revisions.all() if x.subtitle_id == subtitle_id)
        return candidates, revisions

    def _validate_cues(
        self,
        subtitle_id,
        transcript_id,
        revision_id,
        timeline_id,
        expected_ids,
        cues,
        *,
        allow_existing,
    ):
        actual_ids = tuple(cue.identity for cue in cues)
        if actual_ids != expected_ids:
            raise ValueError("subtitle Cue references must match provided order")
        if len(set(actual_ids)) != len(actual_ids):
            raise ValueError("subtitle Cue identities must be unique")
        for cue in cues:
            existing = self.cues.get(cue.identity)
            if existing is not None and (not allow_existing or existing != cue):
                raise ValueError("subtitle Cue identity already exists")
            if cue.subtitle_id != subtitle_id:
                raise ValueError("subtitle Cue must belong to Subtitle lineage")
            if cue.source_transcript_id != transcript_id:
                raise ValueError("subtitle Cue belongs to another Transcript lineage")
            if cue.source_revision_id != revision_id:
                raise ValueError("subtitle Cue source revision does not match input")
            if cue.source_timeline_id != timeline_id:
                raise ValueError("subtitle Cue Source Timeline does not match input")
            for segment_id in cue.source_segment_ids:
                segment = self._transcript_query.get_segment(segment_id)
                if segment is None:
                    raise KeyError("unknown source Transcript Segment")
                if segment.transcript_id != transcript_id:
                    raise ValueError("source Segment belongs to another Transcript lineage")
                if segment.source_timeline_id not in (None, timeline_id):
                    raise ValueError("source Segment Timeline does not match Subtitle")

    def _resolve_transcript_source(self, transcript_id, revision_id):
        raw = self._require_raw(transcript_id)
        if revision_id is None:
            return raw, raw.domain_result_id
        revision = self._transcript_query.get_corrected_revision(revision_id)
        if revision is None:
            raise KeyError("unknown source Transcript revision")
        if revision.transcript_id != transcript_id:
            raise ValueError("source revision belongs to another Transcript lineage")
        return raw, revision.domain_result_id

    def _resolve_subtitle_parent(self, revision):
        if revision.parent_candidate_id is not None:
            parent = self.candidates.get(revision.parent_candidate_id)
            if parent is None:
                raise KeyError("unknown parent Subtitle Candidate")
            upstream = parent.domain_result_id
        else:
            parent = self.revisions.get(revision.parent_revision_id)
            if parent is None:
                raise KeyError("unknown parent Subtitle Revision")
            upstream = parent.domain_result_id
        if parent.subtitle_id != revision.subtitle_id:
            raise ValueError("Subtitle parent belongs to another lineage")
        return parent, upstream

    def _parent_source(self, parent):
        if isinstance(parent, SubtitleCandidate):
            return (
                parent.source_transcript_id,
                parent.source_revision_id,
                parent.source_timeline_id,
            )
        ancestor = self._root_candidate(parent)
        return (
            ancestor.source_transcript_id,
            ancestor.source_revision_id,
            ancestor.source_timeline_id,
        )

    def _root_candidate(self, revision):
        seen = set()
        current = revision
        while current.parent_revision_id is not None:
            if current.identity in seen:
                raise ValueError("subtitle revision cycle detected")
            seen.add(current.identity)
            current = self.revisions.get(current.parent_revision_id)
            if current is None:
                raise KeyError("unknown parent Subtitle Revision")
        candidate = self.candidates.get(current.parent_candidate_id)
        if candidate is None:
            raise KeyError("unknown parent Subtitle Candidate")
        return candidate

    def _validate_revision_cycle(self, revision):
        if revision.parent_revision_id == revision.identity:
            raise ValueError("subtitle revision cannot be its own parent")
        seen = {revision.identity}
        current_id = revision.parent_revision_id
        while current_id is not None:
            if current_id in seen:
                raise ValueError("subtitle revision cycle detected")
            seen.add(current_id)
            current = self.revisions.get(current_id)
            if current is None:
                raise KeyError("unknown parent Subtitle Revision")
            current_id = current.parent_revision_id

    def _require_raw(self, identity):
        raw = self._transcript_query.get_raw_transcript(identity)
        if raw is None:
            raise KeyError("unknown source Transcript")
        return raw

    def _require_execution(self, run_id: ProcessingRunId, execution_id: UnitExecutionId):
        run = self._execution_query.get_run(run_id)
        execution = self._execution_query.get_unit_execution(execution_id)
        if run is None or execution is None:
            raise KeyError("unknown Subtitle execution provenance")
        if execution.run_id != run_id:
            raise ValueError("Subtitle Unit Execution must belong to Processing Run")
        if execution.state is not ProcessingState.RUNNING:
            raise ValueError("Subtitle output requires a running Unit Execution")

    @staticmethod
    def _require_new(repository, identity, label):
        if repository.get(identity) is not None:
            raise ValueError(f"{label} identity already exists")
