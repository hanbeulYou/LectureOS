import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from lectureos.application.provider_transcript_admission import (
    build_provider_transcript_document,
)
from lectureos.composition import (
    compose_sqlite_current_raw_transcript_selection_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.correction_candidate_cli import main
from lectureos.persistence import (
    SQLiteRawTranscriptRepository,
    SQLiteTranscriptSegmentRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.transcript.identities import TranscriptId
from lectureos.validation import validate_database


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class CorrectionCandidateCliTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        connection = initialize_sqlite_database(self.database)
        source = self.base / "a.bin"
        source.write_bytes(b"corr-cli \x00\x01")
        media = compose_sqlite_media_import_service(connection).import_media(str(source)).record
        self.intake = compose_sqlite_transcript_source_intake_service(connection).admit(
            media.identity.value
        ).intake.identity.value
        doc = build_provider_transcript_document(
            {"provider": "fake", "model": "tiny", "language": "ko", "provider_result_ref": "A",
             "segments": [{"start": 0.0, "end": 2.0, "text": "원본 텍스트"}]}
        )
        self.raw = compose_sqlite_provider_transcript_admission_service(connection).admit(
            intake_id=self.intake, document=doc
        ).admission.raw_transcript_id.value
        raw_record = SQLiteRawTranscriptRepository(connection).get(TranscriptId(self.raw))
        self.segment = raw_record.segment_ids[0].value
        self.segment_text = SQLiteTranscriptSegmentRepository(connection).get(raw_record.segment_ids[0]).text
        # A second intake with no selection (for the not-ready case) is not needed; we test not-ready before select.
        connection.close()
        self._selected = False

    def tearDown(self):
        self.tempdir.cleanup()

    def _select(self):
        connection = open_sqlite_database(str(self.database))
        try:
            compose_sqlite_current_raw_transcript_selection_service(connection).select(self.intake, self.raw)
        finally:
            connection.close()
        self._selected = True

    def _candidate_file(self, name, ref="c1", proposed="교정된 텍스트", snapshot=None, source_type="manual"):
        path = self.base / name
        payload = {
            "raw_transcript_id": self.raw, "segment_id": self.segment, "candidate_ref": ref,
            "source_type": source_type, "source_reference": "human:editor",
            "proposed_text": proposed,
            "source_text_snapshot": self.segment_text if snapshot is None else snapshot,
            "rationale": "fix",
        }
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    def _db(self):
        return ["--database", str(self.database)]

    def test_admit_success_states_not_applied(self):
        self._select()
        path = self._candidate_file("c.json")
        code, out, _err = _run(["admit", "--intake", self.intake, "--input", str(path), *self._db()])
        self.assertEqual(code, 0)
        self.assertIn("created correction candidate correction-candidate:", out)
        self.assertIn("the correction candidate was NOT applied", out)
        self.assertIn("proposed text: 교정된 텍스트", out)

    def test_admit_replay_reused(self):
        self._select()
        path = self._candidate_file("c.json")
        _run(["admit", "--intake", self.intake, "--input", str(path), *self._db()])
        code, out, _err = _run(["admit", "--intake", self.intake, "--input", str(path), *self._db()])
        self.assertEqual(code, 0)
        self.assertIn("reused correction candidate", out)

    def test_not_ready_exits_one_and_leaves_db_unchanged(self):
        path = self._candidate_file("c.json")
        before = self.database.read_bytes()
        code, _out, err = _run(["admit", "--intake", self.intake, "--input", str(path), *self._db()])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)
        self.assertEqual(self.database.read_bytes(), before)

    def test_stale_target_exits_one(self):
        self._select()
        path = self._candidate_file("c.json", snapshot="WRONG TEXT")
        code, _out, err = _run(["admit", "--intake", self.intake, "--input", str(path), *self._db()])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_malformed_json_exits_one(self):
        self._select()
        bad = self.base / "bad.json"
        bad.write_text("{ not json", encoding="utf-8")
        code, _out, err = _run(["admit", "--intake", self.intake, "--input", str(bad), *self._db()])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_conflict_exits_one(self):
        self._select()
        _run(["admit", "--intake", self.intake, "--input", str(self._candidate_file("a.json", ref="c1", proposed="제안1")), *self._db()])
        code, _out, err = _run(["admit", "--intake", self.intake, "--input", str(self._candidate_file("b.json", ref="c1", proposed="제안2")), *self._db()])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_list_output(self):
        self._select()
        _run(["admit", "--intake", self.intake, "--input", str(self._candidate_file("a.json", ref="c1", proposed="제안1")), *self._db()])
        _run(["admit", "--intake", self.intake, "--input", str(self._candidate_file("b.json", ref="c2", proposed="제안2")), *self._db()])
        code, out, _err = _run(["list", "--intake", self.intake, *self._db()])
        self.assertEqual(code, 0)
        self.assertIn("2 (not ranked)", out)
        self.assertIn("[applicable]", out)
        self.assertIn("proposed: 제안1", out)

    def test_missing_database_exits_one(self):
        code, _out, err = _run(["list", "--intake", self.intake, "--database", str(self.base / "nope.db")])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_repository_validates_healthy_after_admission(self):
        self._select()
        _run(["admit", "--intake", self.intake, "--input", str(self._candidate_file("c.json")), *self._db()])
        report = validate_database(str(self.database))
        self.assertTrue(report.ok)
        self.assertEqual(report.health.value, "healthy")


if __name__ == "__main__":
    unittest.main()
