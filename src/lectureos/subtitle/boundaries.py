"""Transport-independent Subtitle boundaries."""

from typing import Protocol

from lectureos.execution.identities import DomainResultId
from lectureos.execution.models import DomainResultReference

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


class SubtitleProcessingBoundary(Protocol):
    def create_candidate(
        self, candidate: SubtitleCandidate, cues: tuple[SubtitleCue, ...]
    ) -> None: ...

    def create_revision(
        self, revision: SubtitleRevision, cues: tuple[SubtitleCue, ...]
    ) -> None: ...

    def record_validation(
        self,
        validation: SubtitleValidation,
        findings: tuple[SubtitleValidationFinding, ...],
    ) -> None: ...


class SubtitleQueryBoundary(Protocol):
    def get_candidate(self, identity: SubtitleCandidateId) -> SubtitleCandidate | None: ...

    def get_revision(self, identity: SubtitleRevisionId) -> SubtitleRevision | None: ...

    def get_cue(self, identity: SubtitleCueId) -> SubtitleCue | None: ...

    def get_validation(
        self, identity: SubtitleValidationId
    ) -> SubtitleValidation | None: ...

    def get_validation_finding(
        self, identity: SubtitleValidationFindingId
    ) -> SubtitleValidationFinding | None: ...

    def get_domain_result_reference(
        self, identity: DomainResultId
    ) -> DomainResultReference | None: ...


class SubtitleValidationStoreBoundary(
    SubtitleProcessingBoundary,
    SubtitleQueryBoundary,
    Protocol,
):
    """Persistence boundary used by independent structural validation."""


class SubtitleApplicabilityCommandBoundary(Protocol):
    def select_current_revision(self, **kwargs): ...

    def mark_revision_stale(self, **kwargs): ...

    def mark_revision_historical(self, **kwargs): ...

    def mark_revision_superseded(self, **kwargs): ...


class SubtitleApplicabilityQueryBoundary(Protocol):
    def get_current_revision(self, working_context, subtitle_id): ...

    def get_latest_selection(self, working_context, revision_id): ...

    def get_latest_scope_selection(self, working_context, subtitle_id): ...

    def get_latest_scope_condition(self, working_context, subtitle_id): ...

    def is_revision_stale(self, working_context, revision_id) -> bool: ...

    def get_scope_selection_history(self, working_context, subtitle_id): ...

    def get_scope_condition_history(self, working_context, subtitle_id): ...

    def get_revision_selection_history(self, working_context, revision_id): ...

    def get_revision_condition_history(self, working_context, revision_id): ...

    def get_revision_applicability_history(self, working_context, revision_id): ...
