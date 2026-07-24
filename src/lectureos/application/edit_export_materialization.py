"""Local physical materialization for the first runnable Edit Export slice (044 §22).

Serializes one :class:`EditExportArtifact` into LectureOS Edit Export JSON v1 and writes the result to a
caller-selected local destination as one complete physical file. The write is atomic (temporary file + flush +
fsync + atomic placement): on serialization or write failure no partial file is left at the final path, and the
approved upstream data is preserved. Collision is explicit — identical existing bytes are an idempotent success,
different existing bytes fail by default, and overwrite happens only on explicit request; a symlink or
non-regular existing object is never overwritten. Success is reported only after the complete file is durably
placed, as a structured :class:`EditExportMaterializationResult`.

The serializer and materializer are non-authoritative projections of the §21 Artifact; nothing here is persisted
to the database, and no schema is involved. The concrete filesystem writer is injected through the
:class:`EditExportFileWriter` port.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .edit_export_artifact import EditExportArtifact
from .edit_export_serialization import (
    SerializedEditExport,
    serialize_edit_export_json,
)


class EditExportContainmentError(Exception):
    """The destination is not a safe, contained local file path."""


class EditExportCollisionError(Exception):
    """The destination already holds different bytes or a foreign object and must not be overwritten."""


class EditExportWriteError(Exception):
    """The serialized file could not be durably written."""


class EditExportMaterializationError(ValueError):
    """A serialized Edit Export could not be materialized as a local file."""


class EditExportFileWriter(Protocol):
    def write(self, *, destination: Path, content: bytes, overwrite: bool) -> int: ...


@dataclass(frozen=True, slots=True)
class EditExportMaterializationResult:
    """Structured result of a successful local materialization."""

    final_path: str
    format: str
    version: str
    encoding: str
    byte_length: int


class EditExportMaterializationService:
    """Serializes one Edit Export Artifact and materializes it as one local physical file."""

    def __init__(self, writer: EditExportFileWriter) -> None:
        self._writer = writer

    def materialize_artifact(
        self,
        *,
        artifact: EditExportArtifact,
        destination: Path,
        overwrite: bool = False,
    ) -> EditExportMaterializationResult:
        # Serialize first — a serialization (representation) failure raises before any file is touched.
        serialized = serialize_edit_export_json(artifact)
        return self.materialize(
            serialized=serialized, destination=destination, overwrite=overwrite
        )

    def materialize(
        self,
        *,
        serialized: SerializedEditExport,
        destination: Path,
        overwrite: bool = False,
    ) -> EditExportMaterializationResult:
        content = serialized.payload.encode(serialized.encoding)
        try:
            byte_length = self._writer.write(
                destination=Path(destination), content=content, overwrite=overwrite
            )
        except (
            EditExportContainmentError,
            EditExportCollisionError,
            EditExportWriteError,
        ) as error:
            # Explicit failure — no partial final file, approved sources preserved.
            raise EditExportMaterializationError(
                f"{type(error).__name__}: {error}"
            ) from error
        return EditExportMaterializationResult(
            final_path=str(Path(destination)),
            format=serialized.format,
            version=serialized.version,
            encoding=serialized.encoding,
            byte_length=byte_length,
        )


__all__ = [
    "EditExportCollisionError",
    "EditExportContainmentError",
    "EditExportFileWriter",
    "EditExportMaterializationError",
    "EditExportMaterializationResult",
    "EditExportMaterializationService",
    "EditExportWriteError",
]
