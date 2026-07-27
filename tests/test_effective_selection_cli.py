import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from lectureos.application.provider_transcript_admission import (
    build_provider_transcript_document,
)
from lectureos.composition import (
    compose_sqlite_current_raw_transcript_selection_service,
    compose_sqlite_effective_subtitle_generation_service,
    compose_sqlite_effective_subtitle_review_decision_service,
    compose_sqlite_effective_subtitle_review_preparation_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.effective_selection_cli import main
from lectureos.persistence import initialize_sqlite_database, open_sqlite_database
from lectureos.validation import validate_database


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class EffectiveSelectionCliTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        connection = initialize_sqlite_database(self.database)
        source = self.base / "a.bin"
        source.write_bytes(b"selection-cli \x00\x01")
        media = compose_sqlite_media_import_service(connection).import_media(str(source)).record
        self.intake = compose_sqlite_transcript_source_intake_service(connection).admit(
            media.identity.value
        ).intake.identity.value
        raw = compose_sqlite_provider_transcript_admission_service(connection).admit(
            intake_id=self.intake,
            document=build_provider_transcript_document(
                {"provider": "fake", "model": "tiny", "language": "ko", "provider_result_ref": "A",
                 "segments": [{"start": 0.0, "end": 2.0, "text": "원본"}]}
            ),
        ).admission
        compose_sqlite_current_raw_transcript_selection_service(connection).select(
            self.intake, raw.raw_transcript_id.value
        )
        candidate = compose_sqlite_effective_subtitle_generation_service(connection).generate(
            intake_id=self.intake
        ).candidate
        self.subject = compose_sqlite_effective_subtitle_review_preparation_service(
            connection
        ).prepare_review(candidate_id=candidate.identity.value).subject.identity.value
        connection.close()

    def tearDown(self):
        self.tempdir.cleanup()

    def _db(self):
        return ["--database", str(self.database)]

    def _accept(self):
        connection = open_sqlite_database(str(self.database))
        try:
            compose_sqlite_effective_subtitle_review_decision_service(connection).decide(
                review_subject_id=self.subject, kind="accept", reviewer="reviewer:kim"
            )
        finally:
            connection.close()

    def _selection_id(self, out: str) -> str:
        for line in out.splitlines():
            if line.startswith("selection: "):
                return line.split(": ", 1)[1]
        raise AssertionError(out)

    def test_eligibility_reports_blocking_reason_then_eligible(self):
        code, out, _err = _run(["eligibility", "--review-subject", self.subject, *self._db()])
        self.assertEqual(code, 0)
        self.assertIn("eligible for a new final selection: no", out)
        self.assertIn("blocking reason: no_decision", out)
        self.assertIn("never persisted", out)
        self._accept()
        code, out, _err = _run(["eligibility", "--review-subject", self.subject, *self._db()])
        self.assertIn("eligible for a new final selection: yes", out)
        self.assertIn("current decision kind: accept", out)

    def test_select_reports_lineage_and_no_export(self):
        self._accept()
        code, out, _err = _run(["select", "--review-subject", self.subject,
                                "--selector", "selector:park", *self._db()])
        self.assertEqual(code, 0)
        self.assertIn("recorded effective subtitle final selection", out)
        self.assertIn("selection: subtitle-effective-final-selection:", out)
        self.assertIn("candidate: subtitle-effective-candidate:", out)
        self.assertIn(f"review subject: {self.subject}", out)
        self.assertIn("supporting accept decision: subtitle-effective-review-decision:", out)
        self.assertIn("selector: selector:park", out)
        self.assertIn("this selection is current: yes", out)
        self.assertIn("selection applicability: applicable", out)
        self.assertIn("export state: not part of this contract", out)
        self.assertIn("records authority only", out)

    def test_replay_reports_reused(self):
        self._accept()
        _run(["select", "--review-subject", self.subject,
              "--selector", "selector:park", *self._db()])
        code, out, _err = _run(["select", "--review-subject", self.subject,
                                "--selector", "selector:park", *self._db()])
        self.assertEqual(code, 0)
        self.assertIn("reused effective subtitle final selection", out)

    def test_ineligible_exits_one_and_persists_nothing(self):
        before = self.database.read_bytes()
        code, _out, err = _run(["select", "--review-subject", self.subject,
                                "--selector", "selector:park", *self._db()])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)
        self.assertIn("no_decision", err)
        self.assertEqual(self.database.read_bytes(), before)

    def test_history_current_and_status(self):
        self._accept()
        _code, out, _err = _run(["select", "--review-subject", self.subject,
                                 "--selector", "selector:park", *self._db()])
        selection = self._selection_id(out)
        code, out, _err = _run(["history", "--intake", self.intake, *self._db()])
        self.assertEqual(code, 0)
        self.assertIn("#0 candidate subtitle-effective-candidate:", out)
        self.assertIn("*current", out)
        self.assertIn("append-only", out)
        code, out, _err = _run(["current", "--intake", self.intake, *self._db()])
        self.assertIn("current final selection (derived from the highest immutable sequence):", out)
        code, out, _err = _run(["status", "--selection", selection, *self._db()])
        self.assertIn("selection applicability: applicable", out)
        self.assertIn("supporting decision: subtitle-effective-review-decision:", out)

    def test_unknown_selection_exits_one(self):
        code, _out, err = _run(["status", "--selection",
                                "subtitle-effective-final-selection:" + "0" * 64, *self._db()])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_missing_database_exits_one(self):
        code, _out, err = _run(["current", "--intake", self.intake,
                                "--database", str(self.base / "nope.db")])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_repository_validates_healthy_after_selection(self):
        self._accept()
        _run(["select", "--review-subject", self.subject,
              "--selector", "selector:park", *self._db()])
        report = validate_database(str(self.database))
        self.assertTrue(report.ok)
        self.assertEqual(report.health.value, "healthy")


if __name__ == "__main__":
    unittest.main()
