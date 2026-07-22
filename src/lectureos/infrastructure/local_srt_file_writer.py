"""Infrastructure local-file writer for SRT Physical Materialization (044 §17.13/§17.14).

Realizes bytes beneath a single approved Storage Root using an atomic replacement discipline (temporary
file → fsync → atomic rename), with approved-root containment, symlink-escape rejection, exact byte
preservation, no-overwrite-of-different-bytes, and orphan-temporary-file cleanup. It owns byte-writing
mechanics only — no Artifact/Materialization identity, lifecycle, or filename policy. The safety
mechanics mirror the hardened legacy writer and are not weakened.
"""

from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path

from lectureos.application.subtitle_srt_materialization import (
    MaterializationCollisionError,
    MaterializationContainmentError,
    MaterializationWriteError,
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


class LocalSrtFileWriter:
    """Writes SRT payloads to relative locations beneath one approved Storage Root."""

    def __init__(self, storage_root: str | Path) -> None:
        root = Path(storage_root)
        if not root.is_absolute():
            raise ValueError("approved storage root must be absolute")
        if root.is_symlink():
            raise ValueError("approved storage root must not be a symlink")
        if not root.is_dir():
            raise ValueError("approved storage root must be an existing directory")
        # Canonicalize once so containment checks are stable even when an ancestor is a symlink
        # (e.g. macOS /var -> /private/var); the root leaf itself was rejected above if a symlink.
        self._root = root.resolve(strict=True)

    def write(self, *, relative_location: str, content: bytes) -> int:
        final_path = self._resolve(relative_location)
        current = _entry_kind(final_path)
        if current == "regular":
            try:
                existing = final_path.read_bytes()
            except OSError as error:
                raise MaterializationWriteError(
                    f"could not read existing materialized file: {error}"
                ) from error
            if existing == content:
                return len(content)  # identical bytes -> idempotent success
            raise MaterializationCollisionError(
                "target location holds different bytes; refusing to overwrite"
            )
        if current is not None:
            raise MaterializationCollisionError(
                "target location holds a foreign non-regular object; refusing to overwrite"
            )
        self._atomic_write(final_path, content)
        return len(content)

    def read(self, *, relative_location: str) -> bytes | None:
        final_path = self._resolve(relative_location)
        if _entry_kind(final_path) != "regular":
            return None
        try:
            return final_path.read_bytes()
        except OSError as error:
            raise MaterializationWriteError(
                f"could not read materialized file: {error}"
            ) from error

    def _resolve(self, relative_location: str) -> Path:
        if not relative_location.strip():
            raise MaterializationContainmentError("relative location must not be empty")
        candidate = Path(relative_location)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise MaterializationContainmentError(
                "relative location must be a contained relative path"
            )
        final_path = self._root / candidate
        parent = final_path.parent
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise MaterializationWriteError(
                f"could not create materialized directory: {error}"
            ) from error
        # Containment: the resolved parent must remain beneath the approved root and be symlink-free.
        try:
            resolved_parent = parent.resolve(strict=True)
        except OSError as error:
            raise MaterializationContainmentError(
                f"could not resolve materialized directory: {error}"
            ) from error
        if resolved_parent != self._root and self._root not in resolved_parent.parents:
            raise MaterializationContainmentError(
                "relative location escapes the approved storage root"
            )
        if _entry_kind(final_path) == "symlink":
            raise MaterializationContainmentError("target location must not be a symlink")
        return final_path

    def _atomic_write(self, final_path: Path, content: bytes) -> None:
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
            os.link(temporary_path, final_path)
            temporary_path.unlink()
            temporary_path = None
            if not final_path.is_file() or final_path.stat().st_size != len(content):
                raise OSError("final materialized file validation failed")
        except FileExistsError as error:
            raise MaterializationCollisionError(
                "target location appeared concurrently; refusing to overwrite"
            ) from error
        except OSError as error:
            raise MaterializationWriteError(
                f"could not write materialized file: {error}"
            ) from error
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass


__all__ = ["LocalSrtFileWriter"]
