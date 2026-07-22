import os
import tempfile
import unittest
from pathlib import Path

from lectureos.application.subtitle_srt_materialization import (
    MaterializationCollisionError,
    MaterializationContainmentError,
)
from lectureos.infrastructure.local_srt_file_writer import LocalSrtFileWriter

CONTENT = "1\n00:00:00,000 --> 00:00:01,000\n첫 자막\n".encode("utf-8")


class LocalSrtFileWriterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.writer = LocalSrtFileWriter(self.root)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_writes_exact_bytes(self) -> None:
        n = self.writer.write(relative_location="a.srt", content=CONTENT)
        self.assertEqual(n, len(CONTENT))
        self.assertEqual((self.root / "a.srt").read_bytes(), CONTENT)

    def test_creates_nested_directories(self) -> None:
        self.writer.write(relative_location="nested/dir/a.srt", content=CONTENT)
        self.assertEqual((self.root / "nested/dir/a.srt").read_bytes(), CONTENT)

    def test_identical_bytes_is_idempotent(self) -> None:
        self.writer.write(relative_location="a.srt", content=CONTENT)
        # second write with identical content succeeds without error
        n = self.writer.write(relative_location="a.srt", content=CONTENT)
        self.assertEqual(n, len(CONTENT))

    def test_different_bytes_is_rejected_without_overwrite(self) -> None:
        self.writer.write(relative_location="a.srt", content=CONTENT)
        with self.assertRaises(MaterializationCollisionError):
            self.writer.write(relative_location="a.srt", content=b"different")
        # original preserved
        self.assertEqual((self.root / "a.srt").read_bytes(), CONTENT)

    def test_foreign_directory_is_rejected(self) -> None:
        (self.root / "a.srt").mkdir()
        with self.assertRaises(MaterializationCollisionError):
            self.writer.write(relative_location="a.srt", content=CONTENT)

    def test_absolute_location_is_rejected(self) -> None:
        with self.assertRaises(MaterializationContainmentError):
            self.writer.write(relative_location="/etc/passwd", content=CONTENT)

    def test_traversal_location_is_rejected(self) -> None:
        with self.assertRaises(MaterializationContainmentError):
            self.writer.write(relative_location="../escape.srt", content=CONTENT)
        with self.assertRaises(MaterializationContainmentError):
            self.writer.write(relative_location="a/../../escape.srt", content=CONTENT)

    def test_symlink_escape_is_rejected(self) -> None:
        outside = Path(tempfile.mkdtemp())
        try:
            (self.root / "link").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(MaterializationContainmentError):
                self.writer.write(relative_location="link/a.srt", content=CONTENT)
            self.assertFalse((outside / "a.srt").exists())
        finally:
            import shutil

            shutil.rmtree(outside, ignore_errors=True)

    def test_symlink_target_is_rejected(self) -> None:
        (self.root / "a.srt").symlink_to(self.root / "real.srt")
        with self.assertRaises(MaterializationContainmentError):
            self.writer.write(relative_location="a.srt", content=CONTENT)

    def test_read_returns_bytes_or_none(self) -> None:
        self.assertIsNone(self.writer.read(relative_location="a.srt"))
        self.writer.write(relative_location="a.srt", content=CONTENT)
        self.assertEqual(self.writer.read(relative_location="a.srt"), CONTENT)

    def test_no_orphan_tempfiles_after_success(self) -> None:
        self.writer.write(relative_location="a.srt", content=CONTENT)
        leftovers = [p for p in self.root.iterdir() if p.name.endswith(".tmp")]
        self.assertEqual(leftovers, [])

    def test_root_must_be_absolute_existing_dir(self) -> None:
        with self.assertRaises(ValueError):
            LocalSrtFileWriter("relative/root")
        with self.assertRaises(ValueError):
            LocalSrtFileWriter(self.root / "does-not-exist")


if __name__ == "__main__":
    unittest.main()
