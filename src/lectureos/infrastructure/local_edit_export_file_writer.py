"""Local filesystem writer for the first runnable Edit Export slice (044 §22).

Writes serialized Edit Export bytes to a caller-selected absolute destination path as one complete physical
file. Safety mirrors the hardened `LocalSrtFileWriter`: a temporary file in the destination's parent directory
is written, flushed, and fsynced, then placed atomically — created via `os.link` (fails if the target appears)
or, only when overwrite is explicitly requested, replaced via `os.replace`. On any failure no partial file is
left at the final path and the temporary file is removed. Identical existing bytes are an idempotent success;
different existing bytes fail with a collision unless overwrite is requested; a symlink or non-regular existing
object is never overwritten. Necessary parent directories are created.
"""

from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path

from lectureos.application.edit_export_materialization import (
    EditExportCollisionError,
    EditExportContainmentError,
    EditExportWriteError,
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


class LocalEditExportFileWriter:
    """Writes serialized Edit Export bytes to an absolute local destination path, safely and atomically."""

    def write(self, *, destination: Path, content: bytes, overwrite: bool) -> int:
        final_path = self._resolve(destination)
        current = _entry_kind(final_path)
        if current == "symlink":
            raise EditExportContainmentError("destination must not be a symlink")
        if current == "regular":
            try:
                existing = final_path.read_bytes()
            except OSError as error:
                raise EditExportWriteError(
                    f"could not read existing export file: {error}"
                ) from error
            if existing == content:
                return len(content)  # identical bytes -> idempotent success
            if not overwrite:
                raise EditExportCollisionError(
                    "destination holds different bytes; refusing to overwrite"
                )
            self._atomic_write(final_path, content, overwrite=True)
            return len(content)
        if current is not None:
            raise EditExportCollisionError(
                "destination holds a foreign non-regular object; refusing to overwrite"
            )
        self._atomic_write(final_path, content, overwrite=False)
        return len(content)

    def _resolve(self, destination: Path) -> Path:
        final_path = Path(destination)
        if not final_path.is_absolute():
            raise EditExportContainmentError("destination must be an absolute path")
        parent = final_path.parent
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise EditExportWriteError(
                f"could not create export directory: {error}"
            ) from error
        try:
            resolved_parent = parent.resolve(strict=True)
        except OSError as error:
            raise EditExportContainmentError(
                f"could not resolve export directory: {error}"
            ) from error
        if not resolved_parent.is_dir():
            raise EditExportContainmentError("export destination parent is not a directory")
        return final_path

    def _atomic_write(self, final_path: Path, content: bytes, *, overwrite: bool) -> None:
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
            raise EditExportCollisionError(
                "destination appeared concurrently; refusing to overwrite"
            ) from error
        except OSError as error:
            raise EditExportWriteError(
                f"could not write export file: {error}"
            ) from error
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass


__all__ = ["LocalEditExportFileWriter"]
