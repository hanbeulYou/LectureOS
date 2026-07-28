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
    compose_sqlite_effective_srt_delivery_service,
    compose_sqlite_effective_srt_materialization_service,
    compose_sqlite_effective_subtitle_final_selection_service,
    compose_sqlite_effective_subtitle_generation_service,
    compose_sqlite_effective_subtitle_review_decision_service,
    compose_sqlite_effective_subtitle_review_preparation_service,
    compose_sqlite_effective_subtitle_srt_artifact_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.effective_publish_cli import main
from lectureos.persistence import initialize_sqlite_database, open_sqlite_database
from lectureos.validation import validate_database


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class EffectivePublishCliTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.database = self.base / "lectureos.sqlite3"
        self.storage_root = self.base / "storage"
        self.delivery_root = self.base / "delivered"
        self.storage_root.mkdir()
        self.delivery_root.mkdir()
        connection = initialize_sqlite_database(self.database)
        source = self.base / "a.bin"
        source.write_bytes(b"publish-cli \x00\x01")
        media = compose_sqlite_media_import_service(connection).import_media(str(source)).record
        self.intake = compose_sqlite_transcript_source_intake_service(connection).admit(
            media.identity.value
        ).intake.identity.value
        raw = compose_sqlite_provider_transcript_admission_service(connection).admit(
            intake_id=self.intake,
            document=build_provider_transcript_document(
                {"provider": "fake", "model": "tiny", "language": "ko", "provider_result_ref": "A",
                 "segments": [{"start": 0.0, "end": 1.0, "text": "하나"}]}
            ),
        ).admission
        compose_sqlite_current_raw_transcript_selection_service(connection).select(
            self.intake, raw.raw_transcript_id.value
        )
        candidate = compose_sqlite_effective_subtitle_generation_service(connection).generate(
            intake_id=self.intake
        ).candidate
        subject = compose_sqlite_effective_subtitle_review_preparation_service(
            connection
        ).prepare_review(candidate_id=candidate.identity.value).subject
        compose_sqlite_effective_subtitle_review_decision_service(connection).decide(
            review_subject_id=subject.identity.value, kind="accept", reviewer="reviewer:kim"
        )
        selection = compose_sqlite_effective_subtitle_final_selection_service(
            connection
        ).select_final(
            review_subject_id=subject.identity.value, selector="selector:park"
        ).selection
        artifact = compose_sqlite_effective_subtitle_srt_artifact_service(
            connection
        ).generate_srt_artifact(final_selection_id=selection.identity.value).artifact
        materialization = compose_sqlite_effective_srt_materialization_service(
            connection, str(self.storage_root)
        ).materialize(artifact_id=artifact.identity.value).materialization
        self.delivery = compose_sqlite_effective_srt_delivery_service(
            connection, str(self.storage_root), str(self.delivery_root)
        ).deliver(materialization_id=materialization.identity.value).delivery
        connection.close()

    def tearDown(self):
        self.tempdir.cleanup()

    def _db(self):
        return ["--database", str(self.database)]

    def _publish(self, *extra):
        return _run([
            "publish", "--delivery", self.delivery.identity.value,
            "--publisher", "publisher:kim",
            "--delivery-root", str(self.delivery_root), *extra, *self._db(),
        ])

    def _publication_id(self, output):
        for line in output.splitlines():
            if line.startswith("publication: "):
                return line.split(" ", 1)[1]
        raise AssertionError(f"no publication line in: {output}")

    def test_eligibility_reports_derived_result(self):
        code, out, err = _run([
            "eligibility", "--delivery", self.delivery.identity.value,
            "--delivery-root", str(self.delivery_root), *self._db(),
        ])
        self.assertEqual(code, 0, err)
        self.assertIn("eligible for a new publish command: yes", out)
        self.assertIn("destination observation: matches", out)
        self.assertIn("never persisted", out)

    def test_publish_replay_and_show(self):
        code, out, err = self._publish("--rationale", "1차 공개")
        self.assertEqual(code, 0, err)
        self.assertIn("recorded effective SRT publication", out)
        self.assertIn("kind: publish", out)
        self.assertIn(f"target delivery: {self.delivery.identity.value}", out)
        self.assertIn("public URL: not part of this contract", out)
        self.assertIn("recipient acknowledgement: not part of this contract", out)
        publication_id = self._publication_id(out)
        code, out, err = self._publish("--rationale", "1차 공개")
        self.assertEqual(code, 0, err)
        self.assertIn("reused effective SRT publication", out)
        code, out, err = _run(["show", "--publication", publication_id, *self._db()])
        self.assertEqual(code, 0, err)
        self.assertIn("current publication authority: yes", out)
        self.assertIn("publisher: publisher:kim", out)

    def test_withdraw_current_history_and_availability(self):
        self._publish()
        code, out, err = _run([
            "withdraw", "--intake", self.intake, "--publisher", "publisher:choi",
            "--rationale", "검수 이슈", *self._db(),
        ])
        self.assertEqual(code, 0, err)
        self.assertIn("changed effective SRT publication withdrawal", out)
        self.assertIn("kind: withdraw", out)
        self.assertIn("target delivery: none", out)
        code, out, err = _run(["current", "--intake", self.intake, *self._db()])
        self.assertEqual(code, 0, err)
        self.assertIn("kind: withdraw", out)
        code, out, err = _run(["history", "--intake", self.intake, *self._db()])
        self.assertEqual(code, 0, err)
        self.assertIn(": 2", out)
        self.assertIn("#0 publish", out)
        self.assertIn("#1 withdraw", out)
        self.assertIn("[current]", out)
        code, out, err = _run([
            "availability", "--intake", self.intake,
            "--delivery-root", str(self.delivery_root), *self._db(),
        ])
        self.assertEqual(code, 0, err)
        self.assertIn("derived availability: withdrawn", out)

    def test_availability_separates_authority_from_filesystem(self):
        _, out, _ = self._publish()
        publication_id = self._publication_id(out)
        (self.delivery_root / self.delivery.relative_location).unlink()
        code, out, err = _run([
            "availability", "--intake", self.intake,
            "--delivery-root", str(self.delivery_root), *self._db(),
        ])
        self.assertEqual(code, 0, err)
        self.assertIn("publication authority: publish", out)
        self.assertIn("derived availability: destination_missing", out)
        code, out, err = _run([
            "status", "--publication", publication_id,
            "--delivery-root", str(self.delivery_root), *self._db(),
        ])
        self.assertEqual(code, 0, err)
        self.assertIn("current publication authority: yes", out)
        self.assertIn("destination observation: missing", out)
        self.assertIn("scope availability: destination_missing", out)
        # Without a root, availability is honestly not observed.
        code, out, err = _run(["availability", "--intake", self.intake, *self._db()])
        self.assertEqual(code, 0, err)
        self.assertIn("derived availability: not_observed", out)

    def test_ineligible_or_unknown_input_exits_nonzero_and_persists_nothing(self):
        code, _, err = _run([
            "publish", "--delivery",
            "subtitle-effective-srt-delivery:" + "0" * 64,
            "--publisher", "publisher:kim", *self._db(),
        ])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)
        code, _, err = _run([
            "withdraw", "--intake", self.intake, "--publisher", "publisher:kim",
            *self._db(),
        ])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)
        connection = open_sqlite_database(self.database)
        try:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM subtitle_effective_srt_publications"
                ).fetchone()[0],
                0,
            )
        finally:
            connection.close()

    def test_repository_validates_healthy_after_cli_use(self):
        self._publish()
        _run(["withdraw", "--intake", self.intake, "--publisher", "publisher:kim",
              *self._db()])
        self._publish()
        report = validate_database(str(self.database))
        self.assertTrue(report.ok)
        self.assertEqual(report.health.value, "healthy")


if __name__ == "__main__":
    unittest.main()
