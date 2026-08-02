"""Local materialization — effective-transcript generation (044 §25, GOAL-032).

Implements S-6, S-7, S-8(c), S-10, and S-11 of `patches/PATCH-0037`: writing one serialized payload
to one caller-supplied local destination as one complete physical file.

**C-6/C-7/C-8 are inherited, not reinvented (S-7).** The **caller supplies the destination** and this
layer never chooses a path. The write is atomic — a temporary file is fully written, flushed, and
fsynced, then placed atomically — so no partial file is ever left at the final path. An existing
regular file with identical bytes is an idempotent success; with different bytes it is an explicit
collision and is not overwritten; overwrite happens only on explicit request; a symlink or
non-regular object is never overwritten. Success is reported only after the complete file is durably
placed, as a structured result.

**The file is not the Artifact's identity (S-6).** Filename, directory, path, URL, modification time,
inode, and filesystem metadata participate in no identity and are never serialization inputs. The
same logical payload may be placed at several destinations without creating a new Artifact, a new
approved meaning, or a new export authority.

**Nothing is persisted (S-10).** Neither the payload nor the outcome is stored in the database; no
table, schema, or migration exists for either, and the `§24` Artifact is not required to be persisted
in order to reach a file. The only side effect is on the local filesystem.

**Nothing is approved (S-11).** Materializing exercises no Human Authority and changes no upstream
record.

This module deliberately declares its own error family rather than importing the legacy
`application.edit_export_materialization` one, so this generation carries **no source-level
dependency** on the legacy Export boundary — the idiom GOAL-028 established for the Review vocabulary.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .lecture_edit_export_artifact import LectureEditExportArtifact
from .lecture_edit_export_serialization import (
    SerializedLectureEditExport,
    serialize_lecture_edit_export_json,
)


class LectureEditExportMaterializationError(ValueError):
    """S-8(c): bytes were produced but no safe physical file resulted."""


class LectureEditExportContainmentError(LectureEditExportMaterializationError):
    """The destination is not a usable local file path."""


class LectureEditExportCollisionError(LectureEditExportMaterializationError):
    """The destination holds different bytes or a foreign object and must not be overwritten."""


class LectureEditExportWriteError(LectureEditExportMaterializationError):
    """The serialized file could not be durably written."""


class LectureEditExportFileWriter(Protocol):
    def write(self, *, destination: Path, content: bytes, overwrite: bool) -> int: ...


@dataclass(frozen=True, slots=True)
class LectureEditExportMaterializationResult:
    """C-8's structured successful result, reported only after durable placement (S-7)."""

    final_path: str
    format: str
    version: str
    media_type: str
    encoding: str
    byte_length: int


class LectureEditExportMaterializationService:
    """Places one serialized payload at one caller-supplied local destination (044 §25 S-7)."""

    def __init__(self, writer: LectureEditExportFileWriter) -> None:
        self._writer = writer

    def materialize_artifact(
        self,
        *,
        artifact: LectureEditExportArtifact,
        destination: str | Path,
        overwrite: bool = False,
    ) -> LectureEditExportMaterializationResult:
        """Serialize one Artifact and place the result. Failures stay in their own layer (S-8)."""

        return self.materialize(
            serialized=serialize_lecture_edit_export_json(artifact),
            destination=destination,
            overwrite=overwrite,
        )

    def materialize(
        self,
        *,
        serialized: SerializedLectureEditExport,
        destination: str | Path,
        overwrite: bool = False,
    ) -> LectureEditExportMaterializationResult:
        content = serialized.content
        final_path = Path(destination)
        realized = self._writer.write(
            destination=final_path, content=content, overwrite=overwrite
        )
        if realized != serialized.byte_length:
            # Defence in depth: the writer reports what it placed, and a mismatch means the file on
            # disk does not carry the payload we serialized. Report a failure rather than a success.
            raise LectureEditExportWriteError(
                "materialized byte length does not match the serialized payload"
            )
        return LectureEditExportMaterializationResult(
            final_path=str(final_path),
            format=serialized.format,
            version=serialized.version,
            media_type=serialized.media_type,
            encoding=serialized.encoding,
            byte_length=serialized.byte_length,
        )


__all__ = [
    "LectureEditExportCollisionError",
    "LectureEditExportContainmentError",
    "LectureEditExportFileWriter",
    "LectureEditExportMaterializationError",
    "LectureEditExportMaterializationResult",
    "LectureEditExportMaterializationService",
    "LectureEditExportWriteError",
]
