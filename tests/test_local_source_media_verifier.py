"""Tests for operational source verification used by the local ASR adapter (040 §15)."""

import os
import tempfile
import unittest
from pathlib import Path

from lectureos.application.local_asr_transcription import (
    LocalAsrSourceChangedError,
    LocalAsrSourceUnavailableError,
)
from lectureos.application.media_import import SourceMediaRecord, derive_media_identity
from lectureos.infrastructure.local_source_media_inspector import (
    LocalSourceMediaInspector,
)
from lectureos.infrastructure.local_source_media_verifier import (
    LocalSourceMediaVerifier,
)


def _record_for(path: Path, *, observed: str | None = None) -> SourceMediaRecord:
    fp = LocalSourceMediaInspector().inspect(str(path))
    return SourceMediaRecord(
        identity=derive_media_identity(fp.algorithm, fp.digest),
        fingerprint_algorithm=fp.algorithm,
        fingerprint_digest=fp.digest,
        byte_length=fp.byte_length,
        observed_source_path=observed if observed is not None else fp.observed_source_path,
    )


class LocalSourceMediaVerifierTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.source = self.base / "lecture.bin"
        self.source.write_bytes(b"speech-media-bytes \x00\x01\x02\x03")
        self.verifier = LocalSourceMediaVerifier()

    def tearDown(self):
        self.tempdir.cleanup()

    def test_verifies_unchanged_source_and_returns_resolved_path(self):
        record = _record_for(self.source)
        path = self.verifier.verify(record)
        self.assertEqual(path, str(self.source.resolve()))

    def test_missing_source_is_unavailable(self):
        record = _record_for(self.source, observed=str(self.base / "gone.bin"))
        with self.assertRaises(LocalAsrSourceUnavailableError):
            self.verifier.verify(record)

    def test_directory_source_is_unavailable(self):
        record = _record_for(self.source, observed=str(self.base))
        with self.assertRaises(LocalAsrSourceUnavailableError):
            self.verifier.verify(record)

    def test_changed_bytes_are_rejected(self):
        record = _record_for(self.source)
        self.source.write_bytes(b"completely different bytes now")
        with self.assertRaises(LocalAsrSourceChangedError):
            self.verifier.verify(record)

    def test_symlink_to_regular_file_is_accepted(self):
        link = self.base / "link.bin"
        try:
            os.symlink(self.source, link)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks not supported on this platform")
        record = _record_for(self.source, observed=str(link))
        path = self.verifier.verify(record)
        self.assertEqual(path, str(self.source.resolve()))

    def test_does_not_mutate_source_bytes(self):
        record = _record_for(self.source)
        before = self.source.read_bytes()
        self.verifier.verify(record)
        self.assertEqual(self.source.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
