"""End-to-end CLI tests for provider evidence inspection and the quality diagnostic (040 §15).

These run the real SQLite path — composition root, repositories, schema — so they also prove the
wiring, which is where three checkpoint defects hid during `PATCH-0044`: a service-level test passes
happily while the composition root drops a dependency.

The strongest assertion here is negative: the output must never let an empty finding list read as a
clean verdict (QD-9).
"""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from lectureos.application.local_asr_transcription import (
    LocalAsrDecodeEvidence,
    LocalAsrResult,
    LocalAsrSegment,
)
from lectureos.composition import (
    compose_sqlite_local_asr_transcription_service,
    compose_sqlite_media_import_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.persistence import initialize_sqlite_database
from lectureos.validation import validate_database
import lectureos.transcript_quality_cli as cli


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(argv)
    return code, out.getvalue(), err.getvalue()


class _Engine:
    """Fake engine whose segments carry (or omit) decode evidence, at window granularity."""

    def __init__(self, with_evidence=True):
        self._with_evidence = with_evidence

    def transcribe(self, *, media_path, model, language, device, compute_type,
                   condition_on_previous_text, start_offset=None, on_segment=None):
        def evidence(ref, logprob, nsp, cr, temperature):
            if not self._with_evidence:
                return None
            return LocalAsrDecodeEvidence(
                window_ref=ref,
                values=(
                    ("avg_logprob", logprob),
                    ("compression_ratio", cr),
                    ("no_speech_prob", nsp),
                    ("temperature", temperature),
                ),
            )

        shared = evidence("seek=0", -0.281, 0.033, 1.46, 0.0)
        segments = (
            LocalAsrSegment(0.0, 2.0, "첫 번째 문장", decode_evidence=shared),
            LocalAsrSegment(2.0, 4.0, "두 번째 문장", decode_evidence=shared),
            LocalAsrSegment(
                4.0, 6.0, "세 번째 문장",
                decode_evidence=evidence("seek=400", -0.967, 0.813, 2.37, 0.4),
            ),
        )
        for segment in segments:
            if on_segment is not None:
                on_segment(segment)
        return LocalAsrResult(
            provider="faster-whisper", model=model, language=language or "ko", segments=segments
        )


@contextlib.contextmanager
def _repository(with_evidence=True):
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        database = base / "lectureos.sqlite3"
        source = base / "lecture-source.bin"
        source.write_bytes(b"deterministic-lecture-bytes")

        connection = initialize_sqlite_database(database)
        media = compose_sqlite_media_import_service(connection).import_media(str(source)).record
        intake = compose_sqlite_transcript_source_intake_service(connection).admit(
            media.identity.value
        ).intake
        service = compose_sqlite_local_asr_transcription_service(
            connection, engine_runner=_Engine(with_evidence)
        )
        result = service.transcribe(intake_id=intake.identity.value, model="tiny", language="ko")
        connection.close()
        yield str(database), result.admission.identity.value


class InspectionTests(unittest.TestCase):
    def test_preserved_evidence_is_reported_with_its_granularity(self):
        with _repository() as (database, admission):
            code, out, _ = _run(["inspect", "--admission", admission, "--database", database])
        self.assertEqual(code, 0)
        self.assertIn("provider evidence: available", out)
        self.assertIn("decode evidence windows: 2", out)
        self.assertIn("segments covered by evidence: 3", out)
        # QD-7: the sharing must be visible, not implied.
        self.assertIn("share one window", out)
        self.assertIn("not that segment's own confidence", out)

    def test_absent_evidence_is_never_reported_as_clean(self):
        with _repository(with_evidence=False) as (database, admission):
            code, out, _ = _run(["inspect", "--admission", admission, "--database", database])
        self.assertEqual(code, 0)
        self.assertIn("provider evidence: unavailable", out)
        self.assertIn("NOT the same as quality clean", out)
        self.assertNotIn("clean\n", out.replace("NOT the same as quality clean", ""))

    def test_unknown_admission_fails_cleanly(self):
        with _repository() as (database, _):
            code, _, err = _run(
                ["inspect", "--admission", "provider-transcript-admission:" + "0" * 64,
                 "--database", database]
            )
        self.assertEqual(code, 1)
        self.assertIn("error:", err)


class DiagnosticOutputTests(unittest.TestCase):
    def test_algorithm_anchor_and_deferred_threshold_are_disclosed(self):
        with _repository() as (database, admission):
            code, out, _ = _run(["diagnose", "--admission", admission, "--database", database])
        self.assertEqual(code, 0)
        self.assertIn("algorithm: local-asr-transcript-quality v1", out)
        self.assertIn("provider parameter version: unavailable (threshold policy deferred)", out)

    def test_zero_findings_are_never_printed_as_clean(self):
        with _repository() as (database, admission):
            code, out, _ = _run(["diagnose", "--admission", admission, "--database", database])
        self.assertEqual(code, 0)
        self.assertIn("findings: 0", out)
        self.assertIn("does NOT assert the transcript is clean", out)
        self.assertIn("undetermined reasons: 5", out)

    def test_every_reason_states_why_it_could_not_be_decided(self):
        with _repository() as (database, admission):
            _, out, _ = _run(["diagnose", "--admission", admission, "--database", database])
        for reason in (
            "PROVIDER_LOW_CONFIDENCE",
            "PROVIDER_HIGH_NO_SPEECH",
            "PROVIDER_HIGH_COMPRESSION",
            "PROVIDER_DECODE_FALLBACK",
            "REPEATED_TEXT",
        ):
            self.assertIn(reason, out)
        self.assertIn("threshold policy deferred", out)
        self.assertIn("repetition rule not contracted", out)

    def test_legacy_result_reports_evidence_unavailable_as_the_cause(self):
        with _repository(with_evidence=False) as (database, admission):
            _, out, _ = _run(["diagnose", "--admission", admission, "--database", database])
        self.assertIn("provider evidence: unavailable", out)
        self.assertIn("provider evidence unavailable", out)
        self.assertIn("does NOT assert the transcript is clean", out)

    def test_the_cli_offers_no_correcting_or_deleting_command(self):
        # QD-16: there must be no path from an observation to a mutation.
        with self.assertRaises(SystemExit):
            _run(["correct", "--admission", "x", "--database", "y"])

    def test_repository_stays_healthy_and_unchanged(self):
        with _repository() as (database, admission):
            before = Path(database).read_bytes()
            _run(["diagnose", "--admission", admission, "--database", database])
            _run(["inspect", "--admission", admission, "--database", database])
            after = Path(database).read_bytes()
            validation = validate_database(database)
        self.assertEqual(before, after)
        self.assertTrue(validation.ok)
        self.assertEqual(validation.health.value, "healthy")


if __name__ == "__main__":
    unittest.main()
