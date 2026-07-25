"""Atomic SQLite persistence tests for the External ASR Boundary admission (040 §14)."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from lectureos.application.identities import (
    ProviderTranscriptAdmissionId,
    TranscriptSourceIntakeId,
)
from lectureos.application.media_import import SourceMediaRecord, derive_media_identity
from lectureos.application.provider_transcript_admission import (
    ProviderTranscriptAdmission,
    RAW_TRANSCRIPT_DOMAIN_RESULT_KIND,
    derive_source_timeline_id,
)
from lectureos.application.transcript_source_intake import (
    TranscriptSourceIntake,
    derive_intake_identity,
)
from lectureos.execution.identities import (
    CapabilityReference,
    DomainResultId,
    ProcessingRunId,
    SourceMediaId,
    UnitExecutionId,
)
from lectureos.execution.models import DomainResultReference
from lectureos.persistence import (
    PersistenceIdentityCollisionError,
    SQLiteProviderTranscriptAdmissionCommandPersistence,
    SQLiteProviderTranscriptAdmissionRepository,
    SQLiteRawTranscriptRepository,
    SQLiteProviderTranscriptResultRepository,
    SQLiteSourceMediaCommandPersistence,
    SQLiteTranscriptSourceIntakeCommandPersistence,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence.errors import PersistenceError, SchemaFeatureUnavailableError
from lectureos.transcript.identities import (
    ProviderTranscriptResultId,
    TranscriptId,
    TranscriptSegmentId,
)
from lectureos.transcript.models import (
    ProviderTranscriptResult,
    RawTranscript,
    TranscriptSegment,
)

_DIGEST = "abcd" * 16
_MEDIA = SourceMediaId(f"sha256:{_DIGEST}")


def _bundle(anchor="anchor-1", *, media=_MEDIA, ref="ref-0001", segment_count=2):
    intake_id = derive_intake_identity(media)
    timeline = derive_source_timeline_id(media)
    provider_result_id = ProviderTranscriptResultId(f"provider-transcript-result:{anchor}")
    transcript_id = TranscriptId(f"raw-transcript:{anchor}")
    domain_result_id = DomainResultId(f"domain-result:raw-transcript:{anchor}")
    run_id = ProcessingRunId(f"external-asr-run:{anchor}")
    unit_execution_id = UnitExecutionId(f"external-asr-execution:{anchor}")
    segments = tuple(
        TranscriptSegment(
            identity=TranscriptSegmentId(f"transcript-segment:{anchor}:{i}"),
            transcript_id=transcript_id,
            source_timeline_id=timeline,
            text=f"세그먼트 {i}",
            source_order=i,
            start=float(i),
            end=float(i) + 1.0,
        )
        for i in range(segment_count)
    )
    provider_result = ProviderTranscriptResult(
        identity=provider_result_id,
        source_media_id=media,
        source_timeline_id=timeline,
        run_id=run_id,
        unit_execution_id=unit_execution_id,
        capability=CapabilityReference("capability:asr-transcription"),
        provider_reference="fake-deterministic-asr",
        original_content='{"provider":"fake"}',
        normalized=False,
    )
    raw = RawTranscript(
        identity=transcript_id,
        domain_result_id=domain_result_id,
        source_media_id=media,
        source_timeline_id=timeline,
        provider_result_id=provider_result_id,
        run_id=run_id,
        unit_execution_id=unit_execution_id,
        segment_ids=tuple(s.identity for s in segments),
    )
    result = DomainResultReference(
        identity=domain_result_id,
        kind=RAW_TRANSCRIPT_DOMAIN_RESULT_KIND,
        source_media=media,
        source_timeline=timeline,
    )
    admission = ProviderTranscriptAdmission(
        identity=ProviderTranscriptAdmissionId(f"provider-transcript-admission:{anchor}"),
        transcript_source_intake_id=intake_id,
        source_media_id=media,
        provider_transcript_result_id=provider_result_id,
        raw_transcript_id=transcript_id,
        provider_reference="fake-deterministic-asr",
        provider_result_ref=ref,
        segment_count=segment_count,
        content_fingerprint="0" * 64,
        provider_model="m",
        declared_language="ko",
    )
    return admission, provider_result, segments, raw, result


class SQLiteAtomicProviderTranscriptAdmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.tempdir.name) / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database_path)
        SQLiteSourceMediaCommandPersistence(self.connection).persist_source_media(
            record=SourceMediaRecord(
                identity=_MEDIA,
                fingerprint_algorithm="sha256",
                fingerprint_digest=_DIGEST,
                byte_length=10,
                observed_source_path="/abs/a.bin",
            )
        )
        SQLiteTranscriptSourceIntakeCommandPersistence(
            self.connection
        ).persist_transcript_source_intake(
            intake=TranscriptSourceIntake(derive_intake_identity(_MEDIA), _MEDIA)
        )

    def tearDown(self) -> None:
        try:
            self.connection.close()
        except Exception:
            pass
        self.tempdir.cleanup()

    def _persist(self, bundle) -> None:
        admission, provider_result, segments, raw, result = bundle
        SQLiteProviderTranscriptAdmissionCommandPersistence(
            self.connection
        ).persist_provider_transcript_admission(
            admission=admission,
            provider_result=provider_result,
            segments=segments,
            raw_transcript=raw,
            result=result,
        )

    def _counts(self) -> dict:
        tables = (
            "provider_transcript_admissions",
            "provider_transcript_results",
            "transcript_segments",
            "raw_transcripts",
            "raw_transcript_segments",
            "domain_result_references",
        )
        return {
            t: self.connection.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in tables
        }

    def test_persists_all_records_atomically(self) -> None:
        bundle = _bundle()
        self._persist(bundle)
        counts = self._counts()
        self.assertEqual(counts["provider_transcript_admissions"], 1)
        self.assertEqual(counts["provider_transcript_results"], 1)
        self.assertEqual(counts["transcript_segments"], 2)
        self.assertEqual(counts["raw_transcripts"], 1)
        self.assertEqual(counts["raw_transcript_segments"], 2)
        self.assertEqual(counts["domain_result_references"], 1)

    def test_round_trips_the_admission_record(self) -> None:
        admission = _bundle()[0]
        self._persist(_bundle())
        self.connection.close()
        reopened = open_sqlite_database(self.database_path)
        try:
            restored = SQLiteProviderTranscriptAdmissionRepository(reopened).get(
                admission.identity
            )
            self.assertEqual(restored, admission)
            raw = SQLiteRawTranscriptRepository(reopened).get(admission.raw_transcript_id)
            self.assertEqual(len(raw.segment_ids), 2)
            provider = SQLiteProviderTranscriptResultRepository(reopened).get(
                admission.provider_transcript_result_id
            )
            self.assertFalse(provider.normalized)
        finally:
            reopened.close()

    def test_identity_collision_rolls_back(self) -> None:
        self._persist(_bundle())
        before = self._counts()
        with self.assertRaises(PersistenceIdentityCollisionError):
            self._persist(_bundle())
        self.assertEqual(self._counts(), before)

    def test_raw_transcript_uniqueness_collision_rolls_back(self) -> None:
        self._persist(_bundle(anchor="one"))
        before = self._counts()
        # A different admission identity but colliding on the same raw transcript / provider result.
        conflicting = _bundle(anchor="one")
        admission = conflicting[0]
        object.__setattr__(
            admission,
            "identity",
            ProviderTranscriptAdmissionId("provider-transcript-admission:two"),
        )
        with self.assertRaises(PersistenceIdentityCollisionError):
            self._persist(conflicting)
        # No partial rows from the failed second attempt.
        self.assertEqual(self._counts(), before)

    def test_dangling_intake_is_rejected_by_foreign_key(self) -> None:
        other_media = SourceMediaId("sha256:" + "f" * 64)
        bundle = _bundle(anchor="x", media=other_media)
        # The intake for other_media was never admitted -> FK violation.
        with self.assertRaises(PersistenceError):
            self._persist(bundle)
        self.assertEqual(self._counts()["provider_transcript_admissions"], 0)

    def test_distinct_admissions_coexist(self) -> None:
        self._persist(_bundle(anchor="a", ref="ref-a"))
        self._persist(_bundle(anchor="b", ref="ref-b"))
        self.assertEqual(self._counts()["provider_transcript_admissions"], 2)

    def test_repository_rejects_pre_v32_schema(self) -> None:
        legacy_path = Path(self.tempdir.name) / "legacy.sqlite3"
        from lectureos.persistence import sqlite as sqlite_lifecycle

        connection = sqlite3.connect(legacy_path, isolation_level=None)
        connection.execute("PRAGMA foreign_keys = ON")
        statements = [*sqlite_lifecycle._V1_TABLE_STATEMENTS]
        for level in range(2, 32):
            statements += getattr(sqlite_lifecycle, f"_V{level}_ADDITION_STATEMENTS")
        connection.execute("BEGIN")
        for statement in statements:
            connection.execute(statement)
        connection.execute("INSERT INTO schema_metadata VALUES (1, 31)")
        connection.execute("COMMIT")
        connection.close()
        reopened = open_sqlite_database(legacy_path)
        try:
            with self.assertRaises(SchemaFeatureUnavailableError):
                SQLiteProviderTranscriptAdmissionRepository(reopened)
        finally:
            reopened.close()


if __name__ == "__main__":
    unittest.main()
