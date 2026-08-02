"""Local filesystem writer for effective-generation Edit Export (044 §25, GOAL-032).

Writes serialized bytes to a **caller-supplied absolute destination** as one complete physical file.
The safety mechanics deliberately mirror the hardened legacy writer, because `§25` S-7 inherits
C-6/C-7/C-8 unchanged and an implementation that weakened them would be changing a product contract:
a temporary file in the destination's parent is written, flushed, and fsynced, then placed atomically
— created via `os.link` (which fails if the target appears concurrently) or, **only** when overwrite
is explicitly requested, replaced via `os.replace`. On any failure no partial file is left at the
final path and the temporary file is removed. Identical existing bytes are an idempotent success;
different existing bytes are an explicit collision unless overwrite was requested; a symlink or
non-regular existing object is never overwritten. Necessary parent directories are created.

The mechanics are duplicated rather than inherited from `LocalEditExportFileWriter` so that this
generation raises **its own** error family and carries no source-level dependency on the legacy
Export boundary — the separation idiom GOAL-028 established. Destination validation beyond the rules
S-7 names is an implementation choice, as it was in the legacy realization.
"""

from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path

from lectureos.application.lecture_edit_export_materialization import (
    LectureEditExportCollisionError,
    LectureEditExportContainmentError,
    LectureEditExportWriteError,
)


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


class LocalLectureEditExportFileWriter:
    """Places serialized Edit Export bytes at an absolute local destination, safely and atomically."""

    def write(self, *, destination: Path, content: bytes, overwrite: bool) -> int:
        final_path = self._resolve(destination)
        current = _entry_kind(final_path)
        if current == "symlink":
            raise LectureEditExportContainmentError(
                "destination must not be a symlink"
            )
        if current == "regular":
            try:
                existing = final_path.read_bytes()
            except OSError as error:
                raise LectureEditExportWriteError(
                    f"could not read existing export file: {error}"
                ) from error
            if existing == content:
                return len(content)  # identical bytes -> idempotent success (S-7)
            if not overwrite:
                raise LectureEditExportCollisionError(
                    "destination holds different bytes; refusing to overwrite"
                )
            self._atomic_write(final_path, content, overwrite=True)
            return len(content)
        if current is not None:
            raise LectureEditExportCollisionError(
                "destination holds a foreign non-regular object; refusing to overwrite"
            )
        self._atomic_write(final_path, content, overwrite=False)
        return len(content)

    def _resolve(self, destination: Path) -> Path:
        final_path = Path(destination)
        if not final_path.is_absolute():
            raise LectureEditExportContainmentError(
                "destination must be an absolute path"
            )
        parent = final_path.parent
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise LectureEditExportWriteError(
                f"could not create export directory: {error}"
            ) from error
        try:
            resolved_parent = parent.resolve(strict=True)
        except OSError as error:
            raise LectureEditExportContainmentError(
                f"could not resolve export directory: {error}"
            ) from error
        if not resolved_parent.is_dir():
            raise LectureEditExportContainmentError(
                "export destination parent is not a directory"
            )
        return final_path

    def _atomic_write(
        self, final_path: Path, content: bytes, *, overwrite: bool
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
                raise OSError("temporary export file size differs")
            if overwrite:
                os.replace(temporary_path, final_path)
                temporary_path = None
            else:
                os.link(temporary_path, final_path)
                temporary_path.unlink()
                temporary_path = None
            if not final_path.is_file() or final_path.stat().st_size != len(content):
                raise OSError("final export file validation failed")
        except FileExistsError as error:
            raise LectureEditExportCollisionError(
                "destination appeared concurrently; refusing to overwrite"
            ) from error
        except OSError as error:
            raise LectureEditExportWriteError(
                f"could not write export file: {error}"
            ) from error
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except OSError:  # pragma: no cover - best-effort cleanup
                    pass


__all__ = ["LocalLectureEditExportFileWriter"]
