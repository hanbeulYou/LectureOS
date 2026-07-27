import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from lectureos.application.provider_transcript_admission import (
    build_provider_transcript_document,
)
from lectureos.composition import (
    compose_sqlite_corrected_revision_selection_service,
    compose_sqlite_correction_candidate_admission_service,
    compose_sqlite_corrected_revision_generation_service,
    compose_sqlite_correction_candidate_decision_service,
    compose_sqlite_current_raw_transcript_selection_service,
    compose_sqlite_effective_subtitle_generation_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.effective_review_cli import main
from lectureos.persistence import initialize_sqlite_database, open_sqlite_database
from lectureos.validation import validate_database


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class EffectiveReviewCliTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        connection = initialize_sqlite_database(self.database)
        source = self.base / "a.bin"
        source.write_bytes(b"review-cli \x00\x01")
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
        self.raw_id = raw.raw_transcript_id.value
        compose_sqlite_current_raw_transcript_selection_service(connection).select(
            self.intake, self.raw_id
        )
        self.candidate = compose_sqlite_effective_subtitle_generation_service(
            connection
        ).generate(intake_id=self.intake).candidate.identity.value
        connection.close()

    def tearDown(self):
        self.tempdir.cleanup()

    def _db(self):
        return ["--database", str(self.database)]

    def _subject_id(self, out: str) -> str:
        for line in out.splitlines():
            if line.startswith("review subject: "):
                return line.split(": ", 1)[1]
        raise AssertionError(out)

    def test_prepare_reports_full_provenance(self):
        code, out, _err = _run(["prepare", "--candidate", self.candidate, *self._db()])
        self.assertEqual(code, 0)
        self.assertIn("created effective subtitle review subject", out)
        self.assertIn("review subject: subtitle-effective-review-subject:", out)
        self.assertIn(f"candidate: {self.candidate}", out)
        self.assertIn("candidate graph fingerprint: ", out)
        self.assertIn("source kind: raw_transcript", out)
        self.assertIn(f"source identity: {self.raw_id}", out)
        self.assertIn("consumption binding: transcript-consumption:", out)
        self.assertIn("generator: deterministic_segment_passthrough v1", out)
        self.assertIn("preparation contract: effective_subtitle_review_preparation v1", out)
        self.assertIn("candidate source currentness: current", out)
        self.assertIn("review subject currentness: current", out)
        self.assertIn("human decision state: not part of this contract", out)
        self.assertIn("preparation is preparation only", out)
        for fabricated in ("pending", "approved", "rejected", "completed"):
            self.assertNotIn(fabricated, out)

    def test_prepare_replay_reports_reused(self):
        _run(["prepare", "--candidate", self.candidate, *self._db()])
        code, out, _err = _run(["prepare", "--candidate", self.candidate, *self._db()])
        self.assertEqual(code, 0)
        self.assertIn("reused effective subtitle review subject", out)

    def test_show_and_status_derive_currentness(self):
        _code, out, _err = _run(["prepare", "--candidate", self.candidate, *self._db()])
        subject = self._subject_id(out)
        code, out, _err = _run(["show", "--review-subject", subject, *self._db()])
        self.assertEqual(code, 0)
        self.assertIn(f"candidate: {self.candidate}", out)
        # Make the candidate source stale through a real authority transition.
        connection = open_sqlite_database(str(self.database))
        try:
            from lectureos.application.correction_candidate_admission import (
                build_correction_candidate_input,
            )
            from lectureos.persistence import (
                SQLiteRawTranscriptRepository,
                SQLiteTranscriptSegmentRepository,
            )
            from lectureos.transcript.identities import TranscriptId

            segment = SQLiteRawTranscriptRepository(connection).get(
                TranscriptId(self.raw_id)
            ).segment_ids[0]
            text = SQLiteTranscriptSegmentRepository(connection).get(segment).text
            correction = compose_sqlite_correction_candidate_admission_service(connection).admit(
                intake_id=self.intake,
                candidate=build_correction_candidate_input(
                    {"raw_transcript_id": self.raw_id, "segment_id": segment.value,
                     "candidate_ref": "c1", "source_type": "manual", "source_reference": "human",
                     "proposed_text": "교정", "source_text_snapshot": text, "rationale": "fix"}
                ),
            ).candidate.identity.value
            compose_sqlite_correction_candidate_decision_service(connection).decide(
                candidate_id=correction, kind="accept", reviewer="r:kim"
            )
            revision = compose_sqlite_corrected_revision_generation_service(connection).generate(
                candidate_id=correction
            ).revision.identity.value
            compose_sqlite_corrected_revision_selection_service(connection).select_revision(
                revision_id=revision, reviewer="s:kim"
            )
        finally:
            connection.close()
        code, out, _err = _run(["status", "--review-subject", subject, *self._db()])
        self.assertEqual(code, 0)
        self.assertIn("review subject currentness: stale_due_to_candidate_source", out)
        self.assertIn("valid historical evidence", out)

    def test_list_reports_unprepared_and_prepared(self):
        code, out, _err = _run(["list", "--candidate", self.candidate, *self._db()])
        self.assertEqual(code, 0)
        self.assertIn(": 0", out)
        _run(["prepare", "--candidate", self.candidate, *self._db()])
        code, out, _err = _run(["list", "--candidate", self.candidate, *self._db()])
        self.assertIn(": 1", out)

    def test_unknown_candidate_exits_one_and_persists_nothing(self):
        before = self.database.read_bytes()
        code, _out, err = _run(["prepare", "--candidate",
                                "subtitle-effective-candidate:" + "0" * 64, *self._db()])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)
        self.assertEqual(self.database.read_bytes(), before)

    def test_unknown_subject_exits_one(self):
        code, _out, err = _run(["status", "--review-subject",
                                "subtitle-effective-review-subject:" + "0" * 64, *self._db()])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_missing_database_exits_one(self):
        code, _out, err = _run(["list", "--candidate", self.candidate,
                                "--database", str(self.base / "nope.db")])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_repository_validates_healthy_after_preparation(self):
        _run(["prepare", "--candidate", self.candidate, *self._db()])
        report = validate_database(str(self.database))
        self.assertTrue(report.ok)
        self.assertEqual(report.health.value, "healthy")


if __name__ == "__main__":
    unittest.main()
