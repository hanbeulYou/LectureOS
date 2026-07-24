import os
import tempfile
import unittest
from pathlib import Path

from lectureos.application.edit_export_materialization import (
    EditExportCollisionError,
    EditExportContainmentError,
    EditExportWriteError,
)
from lectureos.infrastructure.local_edit_export_file_writer import (
    LocalEditExportFileWriter,
)

_CONTENT = '{"format": "lectureos-edit-export-json"}\n'.encode("utf-8")
_OTHER = '{"format": "other"}\n'.encode("utf-8")


class LocalEditExportFileWriterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.writer = LocalEditExportFileWriter()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _dest(self, name="edits.json"):
        return self.root / name

    def test_writes_exact_bytes(self) -> None:
        n = self.writer.write(destination=self._dest(), content=_CONTENT, overwrite=False)
        self.assertEqual(n, len(_CONTENT))
        self.assertEqual(self._dest().read_bytes(), _CONTENT)

    def test_creates_nested_directories(self) -> None:
        dest = self.root / "nested" / "dir" / "edits.json"
        self.writer.write(destination=dest, content=_CONTENT, overwrite=False)
        self.assertEqual(dest.read_bytes(), _CONTENT)

    def test_identical_bytes_is_idempotent(self) -> None:
        self.writer.write(destination=self._dest(), content=_CONTENT, overwrite=False)
        n = self.writer.write(destination=self._dest(), content=_CONTENT, overwrite=False)
        self.assertEqual(n, len(_CONTENT))
        self.assertEqual(self._dest().read_bytes(), _CONTENT)

    def test_different_bytes_rejected_without_overwrite(self) -> None:
        self.writer.write(destination=self._dest(), content=_CONTENT, overwrite=False)
        with self.assertRaises(EditExportCollisionError):
            self.writer.write(destination=self._dest(), content=_OTHER, overwrite=False)
        self.assertEqual(self._dest().read_bytes(), _CONTENT)

    def test_explicit_overwrite_replaces_atomically(self) -> None:
        self.writer.write(destination=self._dest(), content=_CONTENT, overwrite=False)
        n = self.writer.write(destination=self._dest(), content=_OTHER, overwrite=True)
        self.assertEqual(n, len(_OTHER))
        self.assertEqual(self._dest().read_bytes(), _OTHER)

    def test_foreign_directory_rejected(self) -> None:
        (self.root / "edits.json").mkdir()
        with self.assertRaises(EditExportCollisionError):
            self.writer.write(destination=self._dest(), content=_CONTENT, overwrite=True)

    def test_absolute_path_required(self) -> None:
        with self.assertRaises(EditExportContainmentError):
            self.writer.write(
                destination=Path("relative/edits.json"), content=_CONTENT, overwrite=False
            )

    def test_symlink_destination_rejected(self) -> None:
        target = self.root / "real.json"
        target.write_bytes(_OTHER)
        link = self.root / "link.json"
        os.symlink(target, link)
        with self.assertRaises(EditExportContainmentError):
            self.writer.write(destination=link, content=_CONTENT, overwrite=True)
        # The real target must be untouched.
        self.assertEqual(target.read_bytes(), _OTHER)

    def test_no_orphan_tempfiles_after_success(self) -> None:
        self.writer.write(destination=self._dest(), content=_CONTENT, overwrite=False)
        leftovers = [p for p in self.root.iterdir() if p.name.endswith(".tmp")]
        self.assertEqual(leftovers, [])

    def test_write_failure_leaves_no_final_file_or_tempfile(self) -> None:
        # A directory that cannot be written to (read-only) surfaces an explicit write error with no partial
        # final file. Skip where the process can bypass permissions (e.g. running as root).
        readonly = self.root / "readonly"
        readonly.mkdir()
        os.chmod(readonly, 0o500)
        dest = readonly / "edits.json"
        try:
            probe = readonly / ".probe"
            try:
                probe.write_bytes(b"x")
                probe.unlink()
                self.skipTest("directory is writable in this environment")
            except OSError:
                pass
            with self.assertRaises(EditExportWriteError):
                self.writer.write(destination=dest, content=_CONTENT, overwrite=False)
            self.assertFalse(dest.exists())
            self.assertEqual(
                [p for p in readonly.iterdir() if p.name.endswith(".tmp")], []
            )
        finally:
            os.chmod(readonly, 0o700)


if __name__ == "__main__":
    unittest.main()
