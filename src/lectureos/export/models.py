"""Immutable Minimal SRT Export request and artifact records."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from lectureos.execution.identities import (
    ArtifactId,
    WorkingContextReference,
)
from lectureos.review.identities import HumanActorReference
from lectureos.subtitle.identities import (
    FinalSubtitleSelectionId,
    SubtitleCueId,
    SubtitleRevisionId,
    SubtitleValidationId,
)

from .identities import (
    ExportRequestId,
    MaterializationRequestId,
    MaterializationResultId,
    SystemRequesterReference,
)


class ExportFormat(str, Enum):
    SRT = "srt"


class ExportTargetMode(str, Enum):
    ACTIVE_FINAL = "active_final"
    HISTORICAL_REPRODUCTION = "historical_reproduction"


class ExportRequesterKind(str, Enum):
    HUMAN = "human"
    SYSTEM = "system"


@dataclass(frozen=True, slots=True)
class ExportRequesterReference:
    kind: ExportRequesterKind
    human_actor: HumanActorReference | None = None
    system_reference: SystemRequesterReference | None = None

    def __post_init__(self) -> None:
        if self.kind is ExportRequesterKind.HUMAN:
            if not isinstance(self.human_actor, HumanActorReference):
                raise TypeError("human Export requester requires a Human Actor")
            if self.system_reference is not None:
                raise ValueError("human and system Export requesters are distinct")
        elif self.kind is ExportRequesterKind.SYSTEM:
            if not isinstance(self.system_reference, SystemRequesterReference):
                raise TypeError("system Export requester requires a System reference")
            if self.human_actor is not None:
                raise ValueError("human and system Export requesters are distinct")
        else:
            raise ValueError("Export requester kind is not supported")


@dataclass(frozen=True, slots=True)
class ExportRequest:
    identity: ExportRequestId
    working_context: WorkingContextReference
    final_selection_id: FinalSubtitleSelectionId
    format: ExportFormat
    target_mode: ExportTargetMode
    requester: ExportRequesterReference
    requested_at: datetime
    stale_condition_acknowledged: bool = False
    historical_risk_acknowledged: bool = False


@dataclass(frozen=True, slots=True)
class ExportArtifact:
    identity: ArtifactId
    request_id: ExportRequestId
    format: ExportFormat
    target_mode: ExportTargetMode
    working_context: WorkingContextReference
    final_selection_id: FinalSubtitleSelectionId
    revision_id: SubtitleRevisionId
    final_validation_id: SubtitleValidationId
    latest_validation_id: SubtitleValidationId
    requester: ExportRequesterReference
    cue_ids: tuple[SubtitleCueId, ...]
    content: str
    serializer_version: str
    created_at: datetime
    stale_condition_acknowledged: bool = False
    historical_risk_acknowledged: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.content, str):
            raise TypeError("SRT Artifact content must be a Unicode string")
        if not self.serializer_version.strip():
            raise ValueError("Export Artifact requires a serializer version")


class LocalOverwritePolicy(str, Enum):
    FAIL_IF_EXISTS = "fail_if_exists"
    REPLACE_EXISTING = "replace_existing"


class LocalEncodingPolicy(str, Enum):
    UTF8 = "utf-8"


class LocalBomPolicy(str, Enum):
    NONE = "none"


class LocalNewlinePolicy(str, Enum):
    LF = "lf"


@dataclass(frozen=True, slots=True)
class LocalArtifactMaterializationRequest:
    identity: MaterializationRequestId
    artifact_id: ArtifactId
    requester: ExportRequesterReference
    target_directory: str
    requested_filename: str
    final_path: str
    overwrite_policy: LocalOverwritePolicy
    requested_at: datetime
    encoding_policy: LocalEncodingPolicy = LocalEncodingPolicy.UTF8
    bom_policy: LocalBomPolicy = LocalBomPolicy.NONE
    newline_policy: LocalNewlinePolicy = LocalNewlinePolicy.LF


@dataclass(frozen=True, slots=True)
class MaterializedFileResult:
    identity: MaterializationResultId
    request_id: MaterializationRequestId
    artifact_id: ArtifactId
    requester: ExportRequesterReference
    final_path: str
    byte_size: int
    overwrite_policy: LocalOverwritePolicy
    materialized_at: datetime
    encoding_policy: LocalEncodingPolicy = LocalEncodingPolicy.UTF8
    bom_policy: LocalBomPolicy = LocalBomPolicy.NONE
    newline_policy: LocalNewlinePolicy = LocalNewlinePolicy.LF
