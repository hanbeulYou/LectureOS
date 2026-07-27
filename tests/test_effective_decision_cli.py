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
    compose_sqlite_effective_subtitle_review_preparation_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.effective_decision_cli import main
from lectureos.persistence import initialize_sqlite_database
from lectureos.validation import validate_database


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class EffectiveDecisionCliTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        connection = initialize_sqlite_database(self.database)
        source = self.base / "a.bin"
        source.write_bytes(b"decision-cli \x00\x01")
        media = compose_sqlite_media_import_service(connection).import_media(str(source)).record
        intake = compose_sqlite_transcript_source_intake_service(connection).admit(
            media.identity.value
        ).intake.identity.value
        raw = compose_sqlite_provider_transcript_admission_service(connection).admit(
            intake_id=intake,
            document=build_provider_transcript_document(
                {"provider": "fake", "model": "tiny", "language": "ko", "provider_result_ref": "A",
                 "segments": [{"start": 0.0, "end": 2.0, "text": "원본"}]}
            ),
        ).admission
        compose_sqlite_current_raw_transcript_selection_service(connection).select(
            intake, raw.raw_transcript_id.value
        )
        candidate = compose_sqlite_effective_subtitle_generation_service(connection).generate(
            intake_id=intake
        ).candidate
        self.subject = compose_sqlite_effective_subtitle_review_preparation_service(
            connection
        ).prepare_review(candidate_id=candidate.identity.value).subject.identity.value
        connection.close()

    def tearDown(self):
        self.tempdir.cleanup()

    def _db(self):
        return ["--database", str(self.database)]

    def _decision_id(self, out: str) -> str:
        for line in out.splitlines():
            if line.startswith("decision: "):
                return line.split(": ", 1)[1].split(" ")[0]
        raise AssertionError(out)

    def test_accept_reports_authority_only(self):
        code, out, _err = _run(["decide", "--review-subject", self.subject,
                                "--decision", "accept", "--reviewer", "reviewer:kim", *self._db()])
        self.assertEqual(code, 0)
        self.assertIn("recorded effective subtitle review decision", out)
        self.assertIn("decision: subtitle-effective-review-decision:", out)
        self.assertIn("decision kind: accept", out)
        self.assertIn("reviewer: reviewer:kim", out)
        self.assertIn("this decision is current: yes", out)
        self.assertIn("decision applicability: applicable", out)
        self.assertIn("final selection state: not part of this contract", out)
        self.assertIn("export state: not part of this contract", out)
        self.assertIn("a decision records authority only", out)
        for fabricated in ("pending review", "review completed", "export approved"):
            self.assertNotIn(fabricated, out)

    def test_reject_and_modify_supported_and_replay_reused(self):
        code, out, _err = _run(["decide", "--review-subject", self.subject,
                                "--decision", "reject", "--reviewer", "reviewer:kim", *self._db()])
        self.assertEqual(code, 0)
        code, out, _err = _run(["decide", "--review-subject", self.subject,
                                "--decision", "reject", "--reviewer", "reviewer:kim", *self._db()])
        self.assertIn("reused effective subtitle review decision", out)
        code, out, _err = _run(["decide", "--review-subject", self.subject,
                                "--decision", "modify", "--reviewer", "reviewer:kim", *self._db()])
        self.assertEqual(code, 0)
        self.assertIn("changed effective subtitle review decision", out)
        self.assertIn("superseded decision: subtitle-effective-review-decision:", out)

    def test_history_and_current(self):
        _run(["decide", "--review-subject", self.subject,
              "--decision", "reject", "--reviewer", "reviewer:kim", *self._db()])
        _run(["decide", "--review-subject", self.subject,
              "--decision", "accept", "--reviewer", "reviewer:lee", *self._db()])
        code, out, _err = _run(["history", "--review-subject", self.subject, *self._db()])
        self.assertEqual(code, 0)
        self.assertIn("#0 reject by reviewer:kim", out)
        self.assertIn("#1 accept by reviewer:lee", out)
        self.assertIn("*current", out)
        self.assertIn("append-only", out)
        code, out, _err = _run(["current", "--review-subject", self.subject, *self._db()])
        self.assertIn("decision kind: accept", out)
        self.assertIn("derived from the highest immutable sequence", out)

    def test_status_reports_superseded(self):
        _code, out, _err = _run(["decide", "--review-subject", self.subject,
                                 "--decision", "reject", "--reviewer", "reviewer:kim", *self._db()])
        first = self._decision_id(out)
        _run(["decide", "--review-subject", self.subject,
              "--decision", "accept", "--reviewer", "reviewer:kim", *self._db()])
        code, out, _err = _run(["status", "--decision", first, *self._db()])
        self.assertEqual(code, 0)
        self.assertIn("decision applicability: superseded", out)
        self.assertIn("immutable historical record", out)

    def test_unknown_kind_exits_one(self):
        before = self.database.read_bytes()
        code, _out, err = _run(["decide", "--review-subject", self.subject,
                                "--decision", "approve", "--reviewer", "r", *self._db()])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)
        self.assertEqual(self.database.read_bytes(), before)

    def test_unknown_subject_exits_one(self):
        code, _out, err = _run(["decide", "--review-subject",
                                "subtitle-effective-review-subject:" + "0" * 64,
                                "--decision", "accept", "--reviewer", "r", *self._db()])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_missing_database_exits_one(self):
        code, _out, err = _run(["current", "--review-subject", self.subject,
                                "--database", str(self.base / "nope.db")])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_repository_validates_healthy_after_decisions(self):
        _run(["decide", "--review-subject", self.subject,
              "--decision", "reject", "--reviewer", "reviewer:kim", *self._db()])
        _run(["decide", "--review-subject", self.subject,
              "--decision", "accept", "--reviewer", "reviewer:kim", *self._db()])
        report = validate_database(str(self.database))
        self.assertTrue(report.ok)
        self.assertEqual(report.health.value, "healthy")


if __name__ == "__main__":
    unittest.main()
