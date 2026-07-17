"""Local filesystem materialization for immutable SRT Export Artifacts."""

from __future__ import annotations

import os
import stat
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Generic, TypeVar

from lectureos.execution.identities import ArtifactId

from .boundaries import ExportQueryBoundary
from .identities import MaterializationRequestId, MaterializationResultId
from .models import (
    ExportFormat,
    ExportRequesterReference,
    LocalArtifactMaterializationRequest,
    LocalOverwritePolicy,
    MaterializedFileResult,
)
from .service import SRT_SERIALIZER_VERSION

IdentityT = TypeVar("IdentityT")
RecordT = TypeVar("RecordT")


class _AppendOnlyRepository(Generic[IdentityT, RecordT]):
    def __init__(self) -> None:
        self._records: dict[IdentityT, RecordT] = {}

    def get(self, identity: IdentityT) -> RecordT | None:
        return self._records.get(identity)

    def contains(self, identity: IdentityT) -> bool:
        return identity in self._records

    def save(self, record: RecordT) -> None:
        identity = getattr(record, "identity")
        if identity in self._records:
            raise ValueError("Materialization identity already exists")
        self._records[identity] = record

    def all(self) -> tuple[RecordT, ...]:
        return tuple(self._records.values())


class _AtomicLocalFileWriter:
    """Writes validated bytes without owning Artifact or repository policy."""

    def write(
        self,
        final_path: Path,
        content: bytes,
        overwrite_policy: LocalOverwritePolicy,
    ) -> None:
        temporary_path: Path | None = None
        try:
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{final_path.name}.", suffix=".tmp", dir=final_path.parent
            )
            temporary_path = Path(temporary_name)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            if temporary_path.stat().st_size != len(content):
                raise OSError("temporary materialized file size differs")
            self._commit(temporary_path, final_path, overwrite_policy)
            temporary_path = None
            if not final_path.is_file() or final_path.stat().st_size != len(content):
                raise OSError("final materialized file validation failed")
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass

    def _commit(
        self,
        temporary_path: Path,
        final_path: Path,
        overwrite_policy: LocalOverwritePolicy,
    ) -> None:
        current = _entry_kind(final_path)
        if overwrite_policy is LocalOverwritePolicy.FAIL_IF_EXISTS:
            if current is not None:
                raise FileExistsError("target path already exists")
            os.link(temporary_path, final_path)
            temporary_path.unlink()
            return
        if current not in (None, "regular"):
            raise ValueError("replace target must be a regular file")
        os.replace(temporary_path, final_path)


class LocalArtifactMaterializationService:
    """Materializes an existing SRT Artifact and records the successful fact."""

    def __init__(
        self,
        export_query: ExportQueryBoundary,
        *,
        writer: _AtomicLocalFileWriter | None = None,
    ) -> None:
        self._export_query = export_query
        self._writer = writer or _AtomicLocalFileWriter()
        self.requests: _AppendOnlyRepository[
            MaterializationRequestId, LocalArtifactMaterializationRequest
        ] = _AppendOnlyRepository()
        self.results: _AppendOnlyRepository[
            MaterializationResultId, MaterializedFileResult
        ] = _AppendOnlyRepository()

    def materialize_export_artifact_to_local_file(
        self,
        *,
        request_id: MaterializationRequestId,
        result_id: MaterializationResultId,
        artifact_id: ArtifactId,
        requester: ExportRequesterReference,
        target_directory: str | Path,
        requested_filename: str,
        overwrite_policy: LocalOverwritePolicy,
    ) -> MaterializedFileResult:
        directory_input = Path(target_directory)
        if not directory_input.is_absolute():
            raise ValueError("target directory must be absolute")
        filename = self._validate_filename(requested_filename)
        final_path_input = directory_input / filename
        proposed = LocalArtifactMaterializationRequest(
            identity=request_id,
            artifact_id=artifact_id,
            requester=requester,
            target_directory=str(directory_input),
            requested_filename=requested_filename,
            final_path=str(final_path_input),
            overwrite_policy=overwrite_policy,
            requested_at=datetime.now(timezone.utc),
        )
        existing = self.requests.get(request_id)
        if existing is not None:
            self._require_same_request(existing, proposed)
            result = self.get_result_for_request(request_id)
            if result is None:
                raise RuntimeError("successful Materialization Request has no Result")
            return result

        directory = self._validate_directory(directory_input)
        final_path = directory / filename
        self._validate_final_path(directory, final_path)

        if not isinstance(requester, ExportRequesterReference):
            raise TypeError("Materialization Request requires a typed requester")
        if not isinstance(overwrite_policy, LocalOverwritePolicy):
            raise ValueError("unsupported overwrite policy")
        if self.results.contains(result_id):
            raise ValueError("Materialization Result identity already exists")

        artifact = self._export_query.get_export_artifact(artifact_id)
        if artifact is None:
            raise KeyError("unknown Export Artifact")
        if artifact.format is not ExportFormat.SRT:
            raise ValueError("only SRT Artifacts can be materialized")
        if artifact.serializer_version != SRT_SERIALIZER_VERSION:
            raise ValueError("unsupported SRT serializer version")
        if not isinstance(artifact.content, str):
            raise TypeError("SRT Artifact content must be Unicode text")
        if not artifact.content:
            raise ValueError("SRT Artifact content must not be empty")

        entry_before = _entry_kind(final_path)
        self._validate_existing_entry(entry_before, overwrite_policy)
        content = artifact.content.encode("utf-8")
        created_new_file = entry_before is None
        try:
            self._writer.write(final_path, content, overwrite_policy)
        except Exception:
            if created_new_file:
                try:
                    final_path.unlink(missing_ok=True)
                except OSError:
                    pass
            raise
        result = MaterializedFileResult(
            identity=result_id,
            request_id=request_id,
            artifact_id=artifact_id,
            requester=requester,
            final_path=str(final_path),
            byte_size=len(content),
            overwrite_policy=overwrite_policy,
            materialized_at=datetime.now(timezone.utc),
        )
        try:
            self.requests.save(proposed)
            self.results.save(result)
        except Exception:
            if created_new_file:
                try:
                    final_path.unlink(missing_ok=True)
                except OSError:
                    pass
            raise
        return result

    def get_materialization_request(self, identity: MaterializationRequestId):
        return self.requests.get(identity)

    def get_materialization_result(self, identity: MaterializationResultId):
        return self.results.get(identity)

    def get_result_for_request(self, request_id: MaterializationRequestId):
        matches = tuple(
            result for result in self.results.all() if result.request_id == request_id
        )
        if len(matches) > 1:
            raise RuntimeError("multiple Results exist for one Materialization Request")
        return matches[0] if matches else None

    def list_materializations_for_artifact(self, artifact_id: ArtifactId):
        return tuple(
            result for result in self.results.all() if result.artifact_id == artifact_id
        )

    def list_materializations_for_path(self, final_path: str | Path):
        path = str(Path(final_path))
        return tuple(
            result for result in self.results.all() if result.final_path == path
        )

    @staticmethod
    def _validate_directory(target_directory: str | Path) -> Path:
        directory = Path(target_directory)
        if not directory.is_absolute():
            raise ValueError("target directory must be absolute")
        if not directory.exists():
            raise ValueError("target directory must exist")
        if directory.is_symlink() or directory.resolve(strict=True) != directory:
            raise ValueError("target directory must not contain symlinks")
        if not directory.is_dir():
            raise ValueError("target path must be a directory")
        if not os.access(directory, os.W_OK | os.X_OK):
            raise PermissionError("target directory is not writable")
        return directory

    @staticmethod
    def _validate_filename(requested_filename: str) -> str:
        if not isinstance(requested_filename, str):
            raise TypeError("requested filename must be text")
        if not requested_filename or requested_filename.isspace():
            raise ValueError("requested filename must not be empty")
        if requested_filename != requested_filename.strip():
            raise ValueError("requested filename must not have boundary whitespace")
        if requested_filename in (".", "..") or requested_filename.startswith("."):
            raise ValueError("hidden or traversal filenames are not supported")
        if "\x00" in requested_filename or "/" in requested_filename or "\\" in requested_filename:
            raise ValueError("requested filename must be a basename")
        candidate = Path(requested_filename)
        if candidate.is_absolute() or candidate.name != requested_filename:
            raise ValueError("requested filename must be a basename")
        suffix = candidate.suffix
        if not suffix:
            return requested_filename + ".srt"
        if suffix.lower() != ".srt":
            raise ValueError("requested filename must use the .srt extension")
        return requested_filename

    @staticmethod
    def _validate_final_path(directory: Path, final_path: Path) -> None:
        if final_path.parent != directory or final_path.is_absolute() is False:
            raise ValueError("materialized file must be a direct child")
        if final_path.parent.resolve(strict=True) != directory:
            raise ValueError("materialized path escapes target directory")

    @staticmethod
    def _validate_existing_entry(
        entry_kind: str | None, overwrite_policy: LocalOverwritePolicy
    ) -> None:
        if entry_kind is None:
            return
        if entry_kind != "regular":
            raise ValueError("target must be absent or a regular file")
        if overwrite_policy is LocalOverwritePolicy.FAIL_IF_EXISTS:
            raise FileExistsError("target path already exists")

    @staticmethod
    def _require_same_request(existing, proposed) -> None:
        fields = (
            "artifact_id",
            "requester",
            "target_directory",
            "requested_filename",
            "final_path",
            "overwrite_policy",
            "encoding_policy",
            "bom_policy",
            "newline_policy",
        )
        if any(getattr(existing, name) != getattr(proposed, name) for name in fields):
            raise ValueError("Materialization Request identity collision")


def _entry_kind(path: Path) -> str | None:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return None
    if stat.S_ISLNK(mode):
        return "symlink"
    if stat.S_ISREG(mode):
        return "regular"
    if stat.S_ISDIR(mode):
        return "directory"
    return "non-regular"
