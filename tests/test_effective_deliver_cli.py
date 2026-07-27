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
from lectureos.effective_deliver_cli import main
from lectureos.persistence import initialize_sqlite_database, open_sqlite_database
from lectureos.validation import validate_database


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


class EffectiveDeliverCliTests(unittest.TestCase):
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
        source.write_bytes(b"deliver-cli \x00\x01")
        media = compose_sqlite_media_import_service(connection).import_media(str(source)).record
        intake = compose_sqlite_transcript_source_intake_service(connection).admit(
            media.identity.value
        ).intake.identity.value
        raw = compose_sqlite_provider_transcript_admission_service(connection).admit(
            intake_id=intake,
            document=build_provider_transcript_document(
                {"provider": "fake", "model": "tiny", "language": "ko", "provider_result_ref": "A",
                 "segments": [{"start": 0.0, "end": 1.0, "text": "하나"}]}
            ),
        ).admission
        compose_sqlite_current_raw_transcript_selection_service(connection).select(
            intake, raw.raw_transcript_id.value
        )
        candidate = compose_sqlite_effective_subtitle_generation_service(connection).generate(
            intake_id=intake
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
        self.artifact = compose_sqlite_effective_subtitle_srt_artifact_service(
            connection
        ).generate_srt_artifact(final_selection_id=selection.identity.value).artifact
        self.materialization = compose_sqlite_effective_srt_materialization_service(
            connection, str(self.storage_root)
        ).materialize(artifact_id=self.artifact.identity.value).materialization
        connection.close()
        self.mat_id = self.materialization.identity.value

    def tearDown(self):
        self.tempdir.cleanup()

    def _roots(self):
        return ["--storage-root", str(self.storage_root),
                "--delivery-root", str(self.delivery_root),
                "--database", str(self.database)]

    def _deliver(self, *extra):
        return _run(["deliver", "--materialization", self.mat_id, *extra,
                     *self._roots()])

    def _delivery_id(self, output):
        for line in output.splitlines():
            if line.startswith("delivery: "):
                return line.split(" ", 1)[1]
        raise AssertionError(f"no delivery line in: {output}")

    def test_eligibility_reports_derived_result(self):
        code, out, err = _run([
            "eligibility", "--materialization", self.mat_id,
            "--storage-root", str(self.storage_root), "--database", str(self.database),
        ])
        self.assertEqual(code, 0, err)
        self.assertIn("eligible for delivery: yes", out)
        self.assertIn("never persisted", out)

    def test_deliver_and_replay(self):
        code, out, err = self._deliver()
        self.assertEqual(code, 0, err)
        self.assertIn("delivery state: delivered", out)
        self.assertIn("request result: created", out)
        self.assertIn("publication state: not part of this contract", out)
        self.assertIn("recipient acknowledgement: not part of this contract", out)
        destination = self.delivery_root / f"{self.artifact.identity.value}.srt"
        self.assertEqual(
            destination.read_bytes(), self.artifact.srt_content.encode("utf-8")
        )
        code, out, err = self._deliver()
        self.assertEqual(code, 0, err)
        self.assertIn("request result: reused", out)

    def test_refusal_records_failed_and_exits_nonzero(self):
        (self.delivery_root / "other.srt").write_bytes(b"foreign\n")
        code, out, err = self._deliver("--location", "other.srt")
        self.assertEqual(code, 1)
        self.assertIn("delivery state: failed (destination_exists_different", out)
        self.assertEqual((self.delivery_root / "other.srt").read_bytes(), b"foreign\n")
        code, out, err = self._deliver("--location", "other.srt", "--overwrite")
        self.assertEqual(code, 0, err)
        self.assertIn("delivery state: delivered", out)
        self.assertIn("overwrite policy: explicit overwrite", out)

    def test_show_status_and_list(self):
        _, out, _ = self._deliver()
        delivery_id = self._delivery_id(out)
        code, out, err = _run(["show", "--delivery", delivery_id, *self._roots()])
        self.assertEqual(code, 0, err)
        self.assertIn(f"materialization: {self.mat_id}", out)
        self.assertIn(f"artifact: {self.artifact.identity.value}", out)
        self.assertIn("delivery contract: local_copy v1", out)
        self.assertIn("source physical path: ", out)
        self.assertIn("destination physical path: ", out)
        (self.delivery_root / f"{self.artifact.identity.value}.srt").unlink()
        code, out, err = _run(["status", "--delivery", delivery_id, *self._roots()])
        self.assertEqual(code, 0, err)
        self.assertIn("delivery state: delivered", out)
        self.assertIn("destination file agreement: missing", out)
        self.assertIn("source file agreement: matches", out)
        code, out, err = _run([
            "list", "--materialization", self.mat_id, *self._roots()
        ])
        self.assertEqual(code, 0, err)
        self.assertIn(": 1", out)
        self.assertIn("#0 [delivered]", out)

    def test_reconcile_terminal_is_idempotent(self):
        _, out, _ = self._deliver()
        delivery_id = self._delivery_id(out)
        code, out, err = _run(["reconcile", "--delivery", delivery_id, *self._roots()])
        self.assertEqual(code, 0, err)
        self.assertIn("already terminal", out)

    def test_ineligible_or_unknown_input_exits_nonzero_and_persists_nothing(self):
        code, _, err = self._deliver("--location", "../escape.srt")
        self.assertEqual(code, 1)
        self.assertIn("error:", err)
        code, _, err = _run([
            "deliver", "--materialization",
            "subtitle-effective-srt-materialization:" + "0" * 64, *self._roots(),
        ])
        self.assertEqual(code, 1)
        self.assertIn("error:", err)
        connection = open_sqlite_database(self.database)
        try:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM subtitle_effective_srt_delivery_intents"
                ).fetchone()[0],
                0,
            )
        finally:
            connection.close()

    def test_repository_validates_healthy_after_cli_use(self):
        self._deliver()
        (self.delivery_root / "other.srt").write_bytes(b"foreign\n")
        self._deliver("--location", "other.srt")  # honest FAILED history
        report = validate_database(str(self.database))
        self.assertTrue(report.ok)
        self.assertEqual(report.health.value, "healthy")


if __name__ == "__main__":
    unittest.main()
