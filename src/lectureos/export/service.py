"""Minimal SRT Export orchestration and canonical serialization."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from math import isfinite
from typing import Generic, TypeVar

from lectureos.execution.identities import ArtifactId, WorkingContextReference
from lectureos.subtitle.boundaries import (
    FinalSubtitleSelectionQueryBoundary,
    SubtitleApplicabilityQueryBoundary,
    SubtitleQueryBoundary,
    SubtitleRevisionValidationBoundary,
)
from lectureos.subtitle.identities import (
    FinalSubtitleSelectionId,
    SubtitleRevisionId,
)

from .identities import ExportRequestId
from .models import (
    ExportArtifact,
    ExportFormat,
    ExportRequest,
    ExportRequesterReference,
    ExportTargetMode,
)

SRT_SERIALIZER_VERSION = "srt-v1"

IdentityT = TypeVar("IdentityT")
RecordT = TypeVar("RecordT")


class _AppendOnlyRepository(Generic[IdentityT, RecordT]):
    def __init__(self) -> None:
        self._records: dict[IdentityT, RecordT] = {}

    def get(self, identity: IdentityT) -> RecordT | None:
        return self._records.get(identity)

    def save(self, record: RecordT) -> None:
        identity = getattr(record, "identity")
        if identity in self._records:
            raise ValueError("Export identity already exists")
        self._records[identity] = record

    def all(self) -> tuple[RecordT, ...]:
        return tuple(self._records.values())


class MinimalSrtExportService:
    """Creates append-only requests and immutable in-memory SRT Artifacts."""

    def __init__(
        self,
        final_selection_query: FinalSubtitleSelectionQueryBoundary,
        subtitle_query: SubtitleQueryBoundary,
        validation_query: SubtitleRevisionValidationBoundary,
        applicability_query: SubtitleApplicabilityQueryBoundary,
    ) -> None:
        self._final_selection_query = final_selection_query
        self._subtitle_query = subtitle_query
        self._validation_query = validation_query
        self._applicability_query = applicability_query
        self.requests: _AppendOnlyRepository[
            ExportRequestId, ExportRequest
        ] = _AppendOnlyRepository()
        self.artifacts: _AppendOnlyRepository[
            ArtifactId, ExportArtifact
        ] = _AppendOnlyRepository()

    def export_final_subtitle_to_srt(
        self,
        *,
        request_id: ExportRequestId,
        artifact_id: ArtifactId,
        working_context: WorkingContextReference,
        final_selection_id: FinalSubtitleSelectionId,
        target_mode: ExportTargetMode,
        requester: ExportRequesterReference,
        format: ExportFormat = ExportFormat.SRT,
        stale_condition_acknowledged: bool = False,
        historical_risk_acknowledged: bool = False,
    ) -> ExportArtifact:
        requested_at = datetime.now(timezone.utc)
        proposed_request = ExportRequest(
            identity=request_id,
            working_context=working_context,
            final_selection_id=final_selection_id,
            format=format,
            target_mode=target_mode,
            requester=requester,
            requested_at=requested_at,
            stale_condition_acknowledged=stale_condition_acknowledged,
            historical_risk_acknowledged=historical_risk_acknowledged,
        )
        existing_request = self.requests.get(request_id)
        if existing_request is not None:
            self._require_same_request(existing_request, proposed_request)
            artifact = self.get_artifact_for_request(request_id)
            if artifact is None:
                raise RuntimeError("successful Export Request has no Artifact")
            return artifact

        if format is not ExportFormat.SRT:
            raise ValueError("unsupported Export format")
        if not isinstance(target_mode, ExportTargetMode):
            raise ValueError("unsupported Export target mode")
        if not isinstance(requester, ExportRequesterReference):
            raise TypeError("Export Request requires a typed requester")
        if self.artifacts.get(artifact_id) is not None:
            raise ValueError("Export Artifact identity already exists")

        selection = self._final_selection_query.get_final_selection(
            final_selection_id
        )
        if selection is None:
            raise KeyError("unknown Final Subtitle Selection")
        if selection.working_context != working_context:
            raise ValueError("Export and Final Selection Working Context differ")
        self._validate_target_mode(selection, target_mode)

        revision = self._subtitle_query.get_revision(selection.revision_id)
        if revision is None:
            raise KeyError("Final Subtitle Revision does not exist")
        if revision.subtitle_id != selection.subtitle_id:
            raise ValueError("Final Selection and Revision lineage differ")

        final_validation = self._require_final_validation(
            selection, revision, working_context
        )
        latest_validation, latest_valid = self._latest_validation_state(
            revision, working_context
        )
        if target_mode is ExportTargetMode.ACTIVE_FINAL and not latest_valid:
            raise ValueError("active Final Export requires latest valid Validation")
        if (
            target_mode is ExportTargetMode.HISTORICAL_REPRODUCTION
            and not latest_valid
            and not historical_risk_acknowledged
        ):
            raise ValueError(
                "historical reproduction requires risk acknowledgment"
            )
        if (
            target_mode is ExportTargetMode.ACTIVE_FINAL
            and historical_risk_acknowledged
        ):
            raise ValueError(
                "historical risk acknowledgment requires historical reproduction"
            )

        is_stale = self._applicability_query.is_revision_stale(
            working_context, revision.identity
        )
        if is_stale and not stale_condition_acknowledged:
            raise ValueError("stale Final Export requires acknowledgment")
        if not is_stale and stale_condition_acknowledged:
            raise ValueError("stale acknowledgment requires a stale Revision")

        cues = self._resolve_cues(revision)
        content = self._serialize_srt(cues)
        artifact = ExportArtifact(
            identity=artifact_id,
            request_id=request_id,
            format=format,
            target_mode=target_mode,
            working_context=working_context,
            final_selection_id=selection.identity,
            revision_id=revision.identity,
            final_validation_id=final_validation.identity,
            latest_validation_id=latest_validation.identity,
            requester=requester,
            cue_ids=revision.cue_ids,
            content=content,
            serializer_version=SRT_SERIALIZER_VERSION,
            created_at=datetime.now(timezone.utc),
            stale_condition_acknowledged=stale_condition_acknowledged,
            historical_risk_acknowledged=historical_risk_acknowledged,
        )
        self.requests.save(proposed_request)
        self.artifacts.save(artifact)
        return artifact

    def get_export_request(self, identity: ExportRequestId) -> ExportRequest | None:
        return self.requests.get(identity)

    def get_export_artifact(self, identity: ArtifactId) -> ExportArtifact | None:
        return self.artifacts.get(identity)

    def get_artifact_for_request(
        self, request_id: ExportRequestId
    ) -> ExportArtifact | None:
        matches = tuple(
            artifact
            for artifact in self.artifacts.all()
            if artifact.request_id == request_id
        )
        if len(matches) > 1:
            raise RuntimeError("multiple Artifacts exist for one Export Request")
        return matches[0] if matches else None

    def list_artifacts_for_final_selection(
        self, final_selection_id: FinalSubtitleSelectionId
    ) -> tuple[ExportArtifact, ...]:
        return tuple(
            artifact
            for artifact in self.artifacts.all()
            if artifact.final_selection_id == final_selection_id
        )

    def list_artifacts_for_revision(
        self, revision_id: SubtitleRevisionId
    ) -> tuple[ExportArtifact, ...]:
        return tuple(
            artifact
            for artifact in self.artifacts.all()
            if artifact.revision_id == revision_id
        )

    def _validate_target_mode(self, selection, target_mode) -> None:
        latest = self._final_selection_query.get_latest_final_selection(
            selection.working_context, selection.subtitle_id
        )
        if latest is None:
            raise ValueError("Final Selection history is incomplete")
        is_active = latest.identity == selection.identity
        if target_mode is ExportTargetMode.ACTIVE_FINAL and not is_active:
            raise ValueError("active Final Export requires the latest Final Selection")
        if target_mode is ExportTargetMode.HISTORICAL_REPRODUCTION and is_active:
            raise ValueError(
                "historical reproduction requires a historical Final Selection"
            )

    def _require_final_validation(self, selection, revision, working_context):
        validation = self._subtitle_query.get_validation(selection.validation_id)
        if validation is None:
            raise KeyError("Final Selection Validation evidence does not exist")
        if (
            validation.target_revision_id != revision.identity
            or validation.target_candidate_id is not None
            or validation.working_context != working_context
            or validation.target_cue_ids != revision.cue_ids
        ):
            raise ValueError("Final Selection Validation evidence differs")
        findings = self._validation_query.get_validation_findings(
            validation.identity
        )
        if tuple(item.identity for item in findings) != validation.finding_ids:
            raise RuntimeError("Final Selection Validation findings are incomplete")
        if not validation.structural_valid or any(item.blocking for item in findings):
            raise ValueError("Final Selection Validation evidence is invalid")
        return validation

    def _latest_validation_state(self, revision, working_context):
        history = self._validation_query.get_revision_validation_history(
            revision.identity
        )
        if not history:
            raise ValueError("Export requires current Revision Validation")
        for index, validation in enumerate(history):
            expected_previous = history[index - 1].identity if index else None
            if (
                validation.target_revision_id != revision.identity
                or validation.sequence != index
                or validation.previous_validation_id != expected_previous
            ):
                raise RuntimeError("Revision Validation history is corrupt")
        latest = history[-1]
        if (
            latest.target_candidate_id is not None
            or latest.working_context != working_context
            or latest.target_cue_ids != revision.cue_ids
        ):
            raise ValueError("latest Revision Validation evidence differs")
        findings = self._validation_query.get_validation_findings(latest.identity)
        if tuple(item.identity for item in findings) != latest.finding_ids:
            raise RuntimeError("latest Revision Validation findings are incomplete")
        return latest, (
            latest.structural_valid
            and not any(item.blocking for item in findings)
        )

    def _resolve_cues(self, revision):
        if not revision.cue_ids:
            raise ValueError("SRT Export requires at least one Cue")
        if len(set(revision.cue_ids)) != len(revision.cue_ids):
            raise ValueError("SRT Export requires unique Cue references")
        domain_result = self._subtitle_query.get_domain_result_reference(
            revision.domain_result_id
        )
        if domain_result is None or domain_result.kind != "subtitle_revision":
            raise ValueError("Subtitle Revision provenance is incomplete")
        cues = []
        for cue_id in revision.cue_ids:
            cue = self._subtitle_query.get_cue(cue_id)
            if cue is None:
                raise KeyError("SRT Export references an unknown Cue")
            if (
                cue.subtitle_id != revision.subtitle_id
                or cue.source_timeline_id != domain_result.source_timeline
            ):
                raise ValueError("SRT Cue lineage differs")
            if cue.replaces_cue_id is not None:
                original = self._subtitle_query.get_cue(cue.replaces_cue_id)
                if original is None:
                    raise KeyError("SRT replacement Cue original does not exist")
                if (
                    original.identity == cue.identity
                    or original.subtitle_id != cue.subtitle_id
                    or original.source_timeline_id != cue.source_timeline_id
                    or original.source_transcript_id != cue.source_transcript_id
                    or original.source_revision_id != cue.source_revision_id
                    or original.start != cue.start
                    or original.end != cue.end
                    or original.display_order != cue.display_order
                    or original.source_segment_ids != cue.source_segment_ids
                ):
                    raise ValueError("SRT replacement Cue lineage differs")
            cues.append(cue)
        orders = tuple(cue.display_order for cue in cues)
        if len(set(orders)) != len(orders) or orders != tuple(sorted(orders)):
            raise ValueError("SRT Cue ordering is invalid")
        return tuple(cues)

    @classmethod
    def _serialize_srt(cls, cues) -> str:
        blocks = []
        for index, cue in enumerate(cues, start=1):
            start_ms = cls._milliseconds(cue.start)
            end_ms = cls._milliseconds(cue.end)
            if end_ms <= start_ms:
                raise ValueError("SRT Cue duration collapses at millisecond precision")
            text = cue.text.replace("\r\n", "\n").replace("\r", "\n")
            if not text or not text.strip():
                raise ValueError("SRT Cue text must not be empty")
            if any(not line.strip() for line in text.split("\n")):
                raise ValueError("SRT Cue text must not contain blank lines")
            blocks.append(
                f"{index}\n"
                f"{cls._format_timestamp(start_ms)} --> "
                f"{cls._format_timestamp(end_ms)}\n"
                f"{text}"
            )
        return "\n\n".join(blocks) + "\n"

    @staticmethod
    def _milliseconds(seconds: float) -> int:
        if not isfinite(seconds) or seconds < 0:
            raise ValueError("SRT timestamp must be finite and non-negative")
        return int(
            (Decimal(str(seconds)) * Decimal(1000)).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )

    @staticmethod
    def _format_timestamp(milliseconds: int) -> str:
        hours, remainder = divmod(milliseconds, 3_600_000)
        minutes, remainder = divmod(remainder, 60_000)
        seconds, millis = divmod(remainder, 1_000)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"

    @staticmethod
    def _require_same_request(existing, proposed) -> None:
        comparable = (
            "working_context",
            "final_selection_id",
            "format",
            "target_mode",
            "requester",
            "stale_condition_acknowledged",
            "historical_risk_acknowledged",
        )
        if any(
            getattr(existing, field) != getattr(proposed, field)
            for field in comparable
        ):
            raise ValueError("Export Request identity collision")
