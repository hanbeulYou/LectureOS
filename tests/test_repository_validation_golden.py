import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from lectureos.repository_validation_acceptance import _corrupt, _seed_healthy
from lectureos.validation import validate_database

_EXPECTED = (
    Path(__file__).resolve().parent.parent / "examples" / "repository-validation" / "expected"
)


def _report_text(database: Path) -> str:
    return json.dumps(validate_database(str(database)).as_dict(), indent=2) + "\n"


class RepositoryValidationGoldenTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.healthy = self.base / "lecture.db"
        _seed_healthy(self.healthy)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_healthy_report_matches_golden(self) -> None:
        self.assertEqual(
            _report_text(self.healthy),
            (_EXPECTED / "healthy-report.json").read_text(encoding="utf-8"),
            "healthy validation report drifted from the golden fixture",
        )

    def test_empty_assembly_report_matches_golden(self) -> None:
        broken = self.base / "broken.db"
        _corrupt(
            self.healthy, broken, lambda c: c.execute("DELETE FROM edit_export_assembly_members")
        )
        self.assertEqual(
            _report_text(broken),
            (_EXPECTED / "empty-assembly-report.json").read_text(encoding="utf-8"),
            "empty-assembly validation report drifted from the golden fixture",
        )


if __name__ == "__main__":
    unittest.main()
