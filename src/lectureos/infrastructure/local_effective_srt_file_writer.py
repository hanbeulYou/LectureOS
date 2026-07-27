"""Infrastructure local-file writer for Effective SRT Materialization (GOAL-018).

Extends the hardened released writer with one capability required by the effective materialization
contract: an **explicit** ``replace`` used only for an explicit overwrite request. Every safety
property of the released writer is preserved — approved-root containment, symlink rejection,
atomic temporary-file discipline, exact byte preservation — and ``replace`` still refuses foreign
non-regular objects; the only relaxation is that an existing regular file with different bytes may
be atomically replaced. The default ``write`` path keeps the released no-overwrite behavior.
"""

from __future__ import annotations

from lectureos.application.subtitle_srt_materialization import (
    MaterializationCollisionError,
    MaterializationWriteError,
)

from .local_srt_file_writer import LocalSrtFileWriter, _entry_kind


class LocalEffectiveSrtFileWriter(LocalSrtFileWriter):
    """The released writer plus explicit-overwrite ``replace`` (GOAL-018)."""

    def replace(self, *, relative_location: str, content: bytes) -> int:
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
                return len(content)  # identical bytes -> idempotent success, no rewrite
            try:
                final_path.unlink()
            except OSError as error:
                raise MaterializationWriteError(
                    f"could not replace existing materialized file: {error}"
                ) from error
        elif current is not None:
            raise MaterializationCollisionError(
                "target location holds a foreign non-regular object; refusing to replace"
            )
        self._atomic_write(final_path, content)
        return len(content)


__all__ = ["LocalEffectiveSrtFileWriter"]
