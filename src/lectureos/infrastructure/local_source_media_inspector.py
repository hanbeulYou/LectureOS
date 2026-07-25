"""Local filesystem inspector for Media Import (045 §1).

Inspects one local source file read-only and returns its :class:`SourceMediaFingerprint`. It rejects missing
paths, directories, non-regular files, unreadable files, and empty (0-byte) files with an explicit
:class:`MediaImportError`; a symlink is accepted only when it resolves to a readable regular file, and the
resolved absolute path is recorded as the observed source path. The file is hashed by streaming fixed-size
chunks (never loaded whole into memory), producing a lowercase SHA-256 hex digest. The source bytes are never
modified.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from lectureos.application.media_import import (
    SHA256_ALGORITHM,
    MediaImportError,
    SourceMediaFingerprint,
)

_CHUNK_SIZE = 1024 * 1024  # 1 MiB


class LocalSourceMediaInspector:
    """Reads a local source file read-only and fingerprints it with streaming SHA-256."""

    def inspect(self, source_path: str) -> SourceMediaFingerprint:
        path = Path(source_path)
        if not path.exists():
            raise MediaImportError("source file does not exist")
        # Resolve symlinks to the real target; the observed path is the resolved absolute path.
        resolved = path.resolve()
        if resolved.is_dir():
            raise MediaImportError("source path is a directory, not a file")
        if not resolved.is_file():
            raise MediaImportError("source path is not a readable regular file")

        digest = hashlib.sha256()
        byte_length = 0
        try:
            with resolved.open("rb") as stream:
                while True:
                    chunk = stream.read(_CHUNK_SIZE)
                    if not chunk:
                        break
                    digest.update(chunk)
                    byte_length += len(chunk)
        except OSError as error:
            raise MediaImportError(f"source file could not be read: {error}") from error

        if byte_length == 0:
            raise MediaImportError("source file is empty")

        return SourceMediaFingerprint(
            algorithm=SHA256_ALGORITHM,
            digest=digest.hexdigest(),
            byte_length=byte_length,
            observed_source_path=str(resolved),
        )


__all__ = ["LocalSourceMediaInspector"]
