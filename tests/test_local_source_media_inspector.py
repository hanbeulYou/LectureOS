import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from lectureos.application.media_import import MediaImportError
from lectureos.infrastructure.local_source_media_inspector import (
    LocalSourceMediaInspector,
)


class LocalSourceMediaInspectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.inspector = LocalSourceMediaInspector()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _file(self, name, content: bytes):
        path = self.base / name
        path.write_bytes(content)
        return path

    def test_fingerprints_a_regular_file(self) -> None:
        content = b"arbitrary media bytes \x00\x01\x02"
        path = self._file("a.bin", content)
        fingerprint = self.inspector.inspect(str(path))
        self.assertEqual(fingerprint.algorithm, "sha256")
        self.assertEqual(fingerprint.digest, hashlib.sha256(content).hexdigest())
        self.assertEqual(fingerprint.byte_length, len(content))
        self.assertEqual(fingerprint.observed_source_path, str(path.resolve()))

    def test_streaming_hash_is_deterministic_and_correct_for_large_input(self) -> None:
        content = bytes(range(256)) * 20000  # ~5 MiB, spans multiple 1 MiB chunks
        path = self._file("big.bin", content)
        a = self.inspector.inspect(str(path))
        b = self.inspector.inspect(str(path))
        self.assertEqual(a.digest, hashlib.sha256(content).hexdigest())
        self.assertEqual(a.digest, b.digest)
        self.assertEqual(a.byte_length, len(content))

    def test_does_not_mutate_source_bytes(self) -> None:
        content = b"unchanged-bytes"
        path = self._file("keep.bin", content)
        self.inspector.inspect(str(path))
        self.assertEqual(path.read_bytes(), content)

    def test_non_ascii_filename_is_supported(self) -> None:
        content = b"korean-filename-content"
        path = self._file("강의-샘플.bin", content)
        fingerprint = self.inspector.inspect(str(path))
        self.assertEqual(fingerprint.digest, hashlib.sha256(content).hexdigest())

    def test_empty_file_is_rejected(self) -> None:
        path = self._file("empty.bin", b"")
        with self.assertRaises(MediaImportError):
            self.inspector.inspect(str(path))

    def test_missing_file_is_rejected(self) -> None:
        with self.assertRaises(MediaImportError):
            self.inspector.inspect(str(self.base / "nope.bin"))

    def test_directory_is_rejected(self) -> None:
        directory = self.base / "adir"
        directory.mkdir()
        with self.assertRaises(MediaImportError):
            self.inspector.inspect(str(directory))

    def test_symlink_to_regular_file_is_resolved(self) -> None:
        content = b"symlinked-content"
        target = self._file("real.bin", content)
        link = self.base / "link.bin"
        os.symlink(target, link)
        fingerprint = self.inspector.inspect(str(link))
        self.assertEqual(fingerprint.digest, hashlib.sha256(content).hexdigest())
        # The observed path is the resolved real target, not the symlink.
        self.assertEqual(fingerprint.observed_source_path, str(target.resolve()))

    def test_broken_symlink_is_rejected(self) -> None:
        link = self.base / "broken.bin"
        os.symlink(self.base / "missing-target.bin", link)
        with self.assertRaises(MediaImportError):
            self.inspector.inspect(str(link))

    def test_symlink_to_directory_is_rejected(self) -> None:
        directory = self.base / "target-dir"
        directory.mkdir()
        link = self.base / "dirlink.bin"
        os.symlink(directory, link)
        with self.assertRaises(MediaImportError):
            self.inspector.inspect(str(link))

    def test_unreadable_file_is_rejected_where_testable(self) -> None:
        content = b"secret bytes"
        path = self._file("locked.bin", content)
        os.chmod(path, 0o000)
        try:
            # Skip where the process can bypass permissions (e.g. running as root).
            try:
                with path.open("rb"):
                    self.skipTest("file is readable in this environment")
            except OSError:
                pass
            with self.assertRaises(MediaImportError):
                self.inspector.inspect(str(path))
        finally:
            os.chmod(path, 0o600)


if __name__ == "__main__":
    unittest.main()
