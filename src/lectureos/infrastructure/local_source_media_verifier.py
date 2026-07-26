"""Operational source-file verification for the local ASR adapter (040 §15).

Given a persisted `SourceMediaRecord`, resolve its reference-in-place source path and confirm it is still
operationally usable *and* unchanged: it must exist as a readable regular file (the confirmed Media Import
symlink policy applies) and its current bytes must still hash to the stored content fingerprint. It reuses the
Media Import streaming, bounded-memory SHA-256 inspector, so the symlink and read policy are identical. It never
mutates the record or the file, never re-imports, and never changes `SourceMediaId`. A missing/unreadable file is
an execution failure (`LocalAsrSourceUnavailableError`); changed bytes are a distinct failure
(`LocalAsrSourceChangedError`) directing the operator to import the changed file as a new Source Media record.
"""

from __future__ import annotations

from lectureos.application.local_asr_transcription import (
    LocalAsrSourceChangedError,
    LocalAsrSourceUnavailableError,
)
from lectureos.application.media_import import MediaImportError, SourceMediaRecord
from lectureos.infrastructure.local_source_media_inspector import (
    LocalSourceMediaInspector,
)


class LocalSourceMediaVerifier:
    """Verifies operational availability and content-fingerprint stability of a Source Media source file."""

    def __init__(self, inspector: LocalSourceMediaInspector | None = None) -> None:
        self._inspector = inspector if inspector is not None else LocalSourceMediaInspector()

    def verify(self, record: SourceMediaRecord) -> str:
        try:
            fingerprint = self._inspector.inspect(record.observed_source_path)
        except MediaImportError as error:
            raise LocalAsrSourceUnavailableError(
                f"source media file is unavailable: {error}"
            ) from error
        if (
            fingerprint.algorithm != record.fingerprint_algorithm
            or fingerprint.digest != record.fingerprint_digest
        ):
            raise LocalAsrSourceChangedError(
                "source file bytes no longer match the stored Source Media fingerprint; "
                "import the changed file as a new Source Media record before transcribing"
            )
        return fingerprint.observed_source_path


__all__ = ["LocalSourceMediaVerifier"]
