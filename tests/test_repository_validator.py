import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from lectureos.application.edit_export_assembly import EditExportAssemblyIdentityPlan
from lectureos.application.identities import EditExportAssemblyId
from lectureos.composition import compose_sqlite_edit_export_assembly_service
from lectureos.edit_export_assembly_acceptance import _seed_representations
from lectureos.execution.identities import DomainResultId, SourceTimelineId
from lectureos.persistence import initialize_sqlite_database
from lectureos.subtitle_intake_acceptance import TIMELINE_ID, _build_persisted_readiness
from lectureos.validation import (
    RepositoryHealth,
    Severity,
    validate_database,
    validate_repository,
)

_ASSEMBLY = "val-assembly"


def _seed_healthy(database: Path) -> str:
    connection = initialize_sqlite_database(database)
    execution, run_id, execution_id, _revision, _raw = _build_persisted_readiness(connection)
    accepted, modified, again = _seed_representations(connection, execution, run_id, execution_id)
    compose_sqlite_edit_export_assembly_service(connection, execution).record_assembly(
        source_timeline_id=SourceTimelineId(TIMELINE_ID),
        member_representation_ids=(
            accepted.representation.identity,
            modified.representation.identity,
            again.representation.identity,
        ),
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=EditExportAssemblyIdentityPlan(
            assembly_id=EditExportAssemblyId(_ASSEMBLY),
            assembly_result_id=DomainResultId(f"{_ASSEMBLY}-result"),
        ),
    )
    connection.close()
    return accepted.representation.identity.value


class RepositoryValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.healthy = self.base / "healthy.db"
        self.member = _seed_healthy(self.healthy)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _corrupt(self, name: str, mutate) -> Path:
        target = self.base / name
        shutil.copyfile(self.healthy, target)
        connection = sqlite3.connect(target)
        try:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute("BEGIN")
            mutate(connection)
            connection.execute("COMMIT")
        finally:
            connection.close()
        return target

    def _codes(self, database: Path) -> set[str]:
        return {d.code for d in validate_database(str(database)).diagnostics}

    def test_healthy_repository_is_clean(self) -> None:
        report = validate_database(str(self.healthy))
        self.assertEqual(report.health, RepositoryHealth.HEALTHY)
        self.assertTrue(report.ok)
        self.assertEqual(report.error_count, 0)
        self.assertEqual(report.warning_count, 0)
        self.assertEqual(report.schema_version, 45)
        self.assertGreater(report.objects_checked, 0)

    def test_validator_does_not_mutate_the_database(self) -> None:
        before = self.healthy.read_bytes()
        validate_database(str(self.healthy))
        self.assertEqual(self.healthy.read_bytes(), before)

    def test_dangling_non_fk_reference_detected(self) -> None:
        broken = self._corrupt(
            "dangling.db",
            lambda c: c.execute(
                "UPDATE approved_edit_export_representations "
                "SET source_review_decision_id = 'ghost' WHERE identity = ?",
                (self.member,),
            ),
        )
        self.assertIn("DANGLING_REFERENCE", self._codes(broken))

    def test_foreign_key_violation_detected(self) -> None:
        def _delete(c: sqlite3.Connection) -> None:
            decision = c.execute(
                "SELECT source_approved_decision_id FROM approved_edit_export_representations "
                "WHERE identity = ?",
                (self.member,),
            ).fetchone()[0]
            c.execute("DELETE FROM approved_edit_decisions WHERE identity = ?", (decision,))

        broken = self._corrupt("orphan.db", _delete)
        self.assertIn("FOREIGN_KEY_VIOLATION", self._codes(broken))

    def test_empty_assembly_detected(self) -> None:
        broken = self._corrupt(
            "empty.db", lambda c: c.execute("DELETE FROM edit_export_assembly_members")
        )
        self.assertIn("ASSEMBLY_EMPTY", self._codes(broken))

    def test_noncontiguous_ordinals_detected(self) -> None:
        broken = self._corrupt(
            "gap.db",
            lambda c: c.execute(
                "UPDATE edit_export_assembly_members SET ordinal = 9 WHERE ordinal = 1"
            ),
        )
        self.assertIn("ASSEMBLY_MEMBER_ORDINAL_NONCONTIGUOUS", self._codes(broken))

    def test_cross_timeline_member_detected(self) -> None:
        broken = self._corrupt(
            "timeline.db",
            lambda c: c.execute(
                "UPDATE approved_edit_export_representations SET source_timeline_id = 'elsewhere' "
                "WHERE identity = ?",
                (self.member,),
            ),
        )
        self.assertIn("ASSEMBLY_MEMBER_TIMELINE_MISMATCH", self._codes(broken))

    def test_cross_media_member_detected(self) -> None:
        broken = self._corrupt(
            "media.db",
            lambda c: c.execute(
                "UPDATE approved_edit_export_representations SET source_media_id = 'elsewhere' "
                "WHERE identity = ?",
                (self.member,),
            ),
        )
        self.assertIn("ASSEMBLY_MEMBER_MEDIA_MISMATCH", self._codes(broken))

    def test_representation_kind_mismatch_detected(self) -> None:
        broken = self._corrupt(
            "kind.db",
            lambda c: c.execute(
                "UPDATE approved_edit_export_representations SET decision_kind = "
                "CASE decision_kind WHEN 'accept' THEN 'modify' ELSE 'accept' END WHERE identity = ?",
                (self.member,),
            ),
        )
        self.assertIn("REPRESENTATION_KIND_MISMATCH", self._codes(broken))

    def test_malformed_identity_detected(self) -> None:
        broken = self._corrupt(
            "malformed.db",
            lambda c: c.execute("UPDATE edit_export_assemblies SET identity = '  '"),
        )
        self.assertIn("MALFORMED_IDENTITY", self._codes(broken))

    def test_noncanonical_member_order_is_a_warning(self) -> None:
        def _swap(c: sqlite3.Connection) -> None:
            # Swap ordinals 0 and 2 via a temporary slot so membership stays contiguous but out of order.
            c.execute("UPDATE edit_export_assembly_members SET ordinal = 100 WHERE ordinal = 0")
            c.execute("UPDATE edit_export_assembly_members SET ordinal = 0 WHERE ordinal = 2")
            c.execute("UPDATE edit_export_assembly_members SET ordinal = 2 WHERE ordinal = 100")

        broken = self._corrupt("reorder.db", _swap)
        report = validate_database(str(broken))
        codes = {d.code for d in report.diagnostics}
        self.assertIn("ASSEMBLY_MEMBER_ORDER_NONCANONICAL", codes)
        self.assertEqual(report.error_count, 0)
        self.assertEqual(report.health, RepositoryHealth.WARNINGS)
        self.assertTrue(report.ok)  # warnings do not make the repository invalid

    def test_multiple_simultaneous_failures_all_reported(self) -> None:
        def _multi(c: sqlite3.Connection) -> None:
            c.execute(
                "UPDATE approved_edit_export_representations SET source_candidate_id = 'ghost' "
                "WHERE identity = ?",
                (self.member,),
            )
            c.execute("DELETE FROM edit_export_assembly_members")

        broken = self._corrupt("multi.db", _multi)
        codes = self._codes(broken)
        self.assertIn("DANGLING_REFERENCE", codes)
        self.assertIn("ASSEMBLY_EMPTY", codes)

    def test_diagnostics_are_deterministic(self) -> None:
        broken = self._corrupt(
            "det.db",
            lambda c: c.execute(
                "UPDATE approved_edit_export_representations SET source_candidate_id = 'ghost' "
                "WHERE identity = ?",
                (self.member,),
            ),
        )
        self.assertEqual(
            validate_database(str(broken)).as_dict(),
            validate_database(str(broken)).as_dict(),
        )

    def test_missing_database_reported(self) -> None:
        report = validate_database(str(self.base / "no-such.db"))
        self.assertEqual({d.code for d in report.diagnostics}, {"DATABASE_NOT_FOUND"})
        self.assertFalse(report.ok)

    def test_non_repository_database_reported(self) -> None:
        empty = self.base / "empty.sqlite3"
        sqlite3.connect(empty).close()
        self.assertIn("SCHEMA_METADATA_MISSING", self._codes(empty))

    def test_duplicate_member_detected_on_tampered_schema(self) -> None:
        # The real schema forbids duplicate members via a UNIQUE constraint; this exercises the check on a
        # minimal tampered schema where that constraint is absent.
        path = self.base / "dupe.db"
        connection = sqlite3.connect(path)
        try:
            connection.executescript(
                """
                CREATE TABLE schema_metadata (singleton INTEGER PRIMARY KEY, version INTEGER NOT NULL);
                INSERT INTO schema_metadata VALUES (1, 29);
                CREATE TABLE edit_export_assemblies (
                    identity TEXT PRIMARY KEY, domain_result_id TEXT, source_media_id TEXT,
                    source_timeline_id TEXT, processing_run_id TEXT, unit_execution_id TEXT);
                CREATE TABLE edit_export_assembly_members (
                    edit_export_assembly_id TEXT, ordinal INTEGER, source_representation_id TEXT);
                INSERT INTO edit_export_assemblies VALUES ('a', 'r', 'm', 't', 'run', 'exec');
                INSERT INTO edit_export_assembly_members VALUES ('a', 0, 'rep-1');
                INSERT INTO edit_export_assembly_members VALUES ('a', 1, 'rep-1');
                """
            )
            connection.commit()
        finally:
            connection.close()
        report = validate_database(str(path))
        self.assertIn(
            "ASSEMBLY_MEMBER_DUPLICATE", {d.code for d in report.diagnostics}
        )

    def test_representation_provenance_mismatch_detected(self) -> None:
        # Point a representation at a different existing review decision than its approved decision's.
        broken = self._corrupt(
            "prov.db",
            lambda c: c.execute(
                "UPDATE approved_edit_export_representations "
                "SET source_review_decision_id = 'decision-modify' WHERE identity = ?",
                (self.member,),
            ),
        )
        self.assertIn("REPRESENTATION_PROVENANCE_MISMATCH", self._codes(broken))

    def test_approved_decision_kind_invalid_detected(self) -> None:
        def _flip(c: sqlite3.Connection) -> None:
            decision = c.execute(
                "SELECT source_approved_decision_id FROM approved_edit_export_representations "
                "WHERE identity = ?",
                (self.member,),
            ).fetchone()[0]
            c.execute(
                "UPDATE approved_edit_decisions SET decision_kind = "
                "CASE decision_kind WHEN 'accept' THEN 'modify' ELSE 'accept' END WHERE identity = ?",
                (decision,),
            )

        broken = self._corrupt("dkind.db", _flip)
        self.assertIn("APPROVED_DECISION_KIND_INVALID", self._codes(broken))

    def test_approved_decision_provenance_mismatch_detected(self) -> None:
        def _swap_candidate(c: sqlite3.Connection) -> None:
            decision = c.execute(
                "SELECT source_approved_decision_id FROM approved_edit_export_representations "
                "WHERE identity = ?",
                (self.member,),
            ).fetchone()[0]
            c.execute(
                "UPDATE approved_edit_decisions SET source_candidate_id = 'candidate-modify' "
                "WHERE identity = ?",
                (decision,),
            )

        broken = self._corrupt("dprov.db", _swap_candidate)
        self.assertIn("APPROVED_DECISION_PROVENANCE_MISMATCH", self._codes(broken))

    def test_domain_result_upstream_noncontiguous_detected(self) -> None:
        broken = self._corrupt(
            "lineage.db",
            lambda c: c.execute(
                "UPDATE domain_result_upstream_results SET ordinal = 9 "
                "WHERE domain_result_id = ? AND ordinal = 1",
                (f"{_ASSEMBLY}-result",),
            ),
        )
        self.assertIn("DOMAIN_RESULT_UPSTREAM_NONCONTIGUOUS", self._codes(broken))

    def test_unsupported_schema_version_detected(self) -> None:
        broken = self._corrupt(
            "version.db",
            lambda c: c.execute("UPDATE schema_metadata SET version = 999 WHERE singleton = 1"),
        )
        self.assertIn("SCHEMA_VERSION_UNSUPPORTED", self._codes(broken))

    def test_unreadable_database_reported(self) -> None:
        junk = self.base / "junk.db"
        junk.write_bytes(b"this is not a sqlite database" * 8)
        self.assertIn("DATABASE_UNREADABLE", self._codes(junk))

    def test_every_diagnostic_has_required_fields(self) -> None:
        broken = self._corrupt(
            "fields.db", lambda c: c.execute("DELETE FROM edit_export_assembly_members")
        )
        report = validate_database(str(broken))
        self.assertTrue(report.diagnostics)
        for diagnostic in report.diagnostics:
            self.assertTrue(diagnostic.code)
            self.assertIsInstance(diagnostic.severity, Severity)
            self.assertTrue(diagnostic.location)
            self.assertTrue(diagnostic.message)


class SourceMediaValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        from lectureos.composition import compose_sqlite_media_import_service

        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.healthy = self.base / "media.db"
        connection = initialize_sqlite_database(self.healthy)
        source = self.base / "sample.bin"
        source.write_bytes(b"media-validation-sample \x00\x01")
        compose_sqlite_media_import_service(connection).import_media(str(source))
        connection.close()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _corrupt(self, name: str, mutate) -> Path:
        target = self.base / name
        shutil.copyfile(self.healthy, target)
        connection = sqlite3.connect(target)
        try:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute("BEGIN")
            mutate(connection)
            connection.execute("COMMIT")
        finally:
            connection.close()
        return target

    def _codes(self, database: Path) -> set[str]:
        return {d.code for d in validate_database(str(database)).diagnostics}

    def test_healthy_media_repository_is_clean(self) -> None:
        report = validate_database(str(self.healthy))
        self.assertTrue(report.ok)
        self.assertEqual(report.health, RepositoryHealth.HEALTHY)

    def test_malformed_fingerprint_detected(self) -> None:
        # 64 characters (satisfies the length CHECK) but not lowercase hex.
        broken = self._corrupt(
            "malformed.db",
            lambda c: c.execute(
                "UPDATE source_media SET fingerprint_digest = ?", ("A" * 64,)
            ),
        )
        self.assertIn("MEDIA_FINGERPRINT_MALFORMED", self._codes(broken))

    def test_identity_fingerprint_disagreement_detected(self) -> None:
        broken = self._corrupt(
            "disagree.db",
            lambda c: c.execute("UPDATE source_media SET identity = 'sha256:mismatch'"),
        )
        self.assertIn("MEDIA_IDENTITY_FINGERPRINT_DISAGREEMENT", self._codes(broken))

    def test_duplicate_fingerprint_detected_on_tampered_schema(self) -> None:
        # The real schema forbids duplicate fingerprints via UNIQUE; exercise the check on a minimal
        # tampered schema where that constraint is absent.
        path = self.base / "dup.db"
        connection = sqlite3.connect(path)
        try:
            connection.executescript(
                """
                CREATE TABLE schema_metadata (singleton INTEGER PRIMARY KEY, version INTEGER NOT NULL);
                INSERT INTO schema_metadata VALUES (1, 30);
                CREATE TABLE source_media (
                    identity TEXT PRIMARY KEY, fingerprint_algorithm TEXT, fingerprint_digest TEXT,
                    byte_length INTEGER, observed_source_path TEXT);
                INSERT INTO source_media VALUES ('sha256:aaa', 'sha256', 'a', 1, '/x');
                INSERT INTO source_media VALUES ('sha256:bbb', 'sha256', 'a', 1, '/y');
                """
            )
            connection.commit()
        finally:
            connection.close()
        self.assertIn("MEDIA_FINGERPRINT_DUPLICATE", self._codes(path))

    def test_blank_media_identity_detected(self) -> None:
        broken = self._corrupt(
            "blank.db",
            lambda c: c.execute("UPDATE source_media SET identity = '  '"),
        )
        self.assertIn("MALFORMED_IDENTITY", self._codes(broken))


class TranscriptSourceIntakeValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        from lectureos.composition import (
            compose_sqlite_media_import_service,
            compose_sqlite_transcript_source_intake_service,
        )

        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.healthy = self.base / "intake.db"
        connection = initialize_sqlite_database(self.healthy)
        source = self.base / "sample.bin"
        source.write_bytes(b"intake-validation-sample \x00\x01")
        media = compose_sqlite_media_import_service(connection).import_media(str(source))
        self.media_id = media.record.identity.value
        compose_sqlite_transcript_source_intake_service(connection).admit(self.media_id)
        connection.close()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _corrupt(self, name: str, mutate) -> Path:
        target = self.base / name
        shutil.copyfile(self.healthy, target)
        connection = sqlite3.connect(target)
        try:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute("BEGIN")
            mutate(connection)
            connection.execute("COMMIT")
        finally:
            connection.close()
        return target

    def _codes(self, database: Path) -> set[str]:
        return {d.code for d in validate_database(str(database)).diagnostics}

    def test_healthy_intake_repository_is_clean(self) -> None:
        report = validate_database(str(self.healthy))
        self.assertTrue(report.ok)
        self.assertEqual(report.health, RepositoryHealth.HEALTHY)

    def test_identity_disagreement_detected(self) -> None:
        broken = self._corrupt(
            "disagree.db",
            lambda c: c.execute(
                "UPDATE transcript_source_intakes SET identity = 'transcript-source-intake:wrong'"
            ),
        )
        self.assertIn("TRANSCRIPT_INTAKE_IDENTITY_DISAGREEMENT", self._codes(broken))

    def test_dangling_source_media_detected(self) -> None:
        broken = self._corrupt(
            "dangling.db",
            lambda c: c.execute(
                "UPDATE transcript_source_intakes SET source_media_id = 'sha256:' || ("
                "SELECT substr(hex(randomblob(32)), 1, 64))"
            ),
        )
        # The FK check and the intake dangling check both surface a broken reference.
        codes = self._codes(broken)
        self.assertTrue(
            "TRANSCRIPT_INTAKE_DANGLING_SOURCE_MEDIA" in codes
            or "FOREIGN_KEY_VIOLATION" in codes
        )

    def test_blank_intake_identity_detected(self) -> None:
        broken = self._corrupt(
            "blank.db",
            lambda c: c.execute("UPDATE transcript_source_intakes SET identity = '  '"),
        )
        self.assertIn("MALFORMED_IDENTITY", self._codes(broken))

    def test_duplicate_intake_detected_on_tampered_schema(self) -> None:
        # The real schema forbids two intakes per media via UNIQUE(source_media_id); exercise the check on a
        # minimal tampered schema where that constraint is absent.
        path = self.base / "dup.db"
        connection = sqlite3.connect(path)
        try:
            connection.executescript(
                """
                CREATE TABLE schema_metadata (singleton INTEGER PRIMARY KEY, version INTEGER NOT NULL);
                INSERT INTO schema_metadata VALUES (1, 31);
                CREATE TABLE transcript_source_intakes (identity TEXT PRIMARY KEY, source_media_id TEXT);
                INSERT INTO transcript_source_intakes
                    VALUES ('transcript-source-intake:sha256:m', 'sha256:m');
                INSERT INTO transcript_source_intakes
                    VALUES ('transcript-source-intake:sha256:m2', 'sha256:m');
                """
            )
            connection.commit()
        finally:
            connection.close()
        self.assertIn("TRANSCRIPT_INTAKE_DUPLICATE", self._codes(path))


class ProviderTranscriptAdmissionValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        from lectureos.application.provider_transcript_admission import (
            build_provider_transcript_document,
        )
        from lectureos.composition import (
            compose_sqlite_media_import_service,
            compose_sqlite_provider_transcript_admission_service,
            compose_sqlite_transcript_source_intake_service,
        )

        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.healthy = self.base / "admission.db"
        connection = initialize_sqlite_database(self.healthy)
        source = self.base / "sample.bin"
        source.write_bytes(b"admission-validation-sample \x00\x01\x02")
        media_id = (
            compose_sqlite_media_import_service(connection)
            .import_media(str(source))
            .record.identity.value
        )
        intake_id = (
            compose_sqlite_transcript_source_intake_service(connection)
            .admit(media_id)
            .intake.identity.value
        )
        document = build_provider_transcript_document(
            {
                "provider": "fake-deterministic-asr",
                "provider_result_ref": "ref-0001",
                "segments": [
                    {"start": 0.0, "end": 2.0, "text": "가"},
                    {"start": 2.0, "end": 4.0, "text": "나"},
                ],
            }
        )
        compose_sqlite_provider_transcript_admission_service(connection).admit(
            intake_id=intake_id, document=document
        )
        connection.close()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _corrupt(self, name: str, mutate) -> Path:
        target = self.base / name
        shutil.copyfile(self.healthy, target)
        connection = sqlite3.connect(target)
        try:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute("BEGIN")
            mutate(connection)
            connection.execute("COMMIT")
        finally:
            connection.close()
        return target

    def _codes(self, database: Path) -> set[str]:
        return {d.code for d in validate_database(str(database)).diagnostics}

    def test_healthy_admission_repository_is_clean(self) -> None:
        report = validate_database(str(self.healthy))
        self.assertTrue(report.ok)
        self.assertEqual(report.health, RepositoryHealth.HEALTHY)

    def test_intake_provenance_disagreement_detected(self) -> None:
        broken = self._corrupt(
            "prov.db",
            lambda c: c.execute(
                "UPDATE provider_transcript_admissions "
                "SET transcript_source_intake_id = 'transcript-source-intake:sha256:other'"
            ),
        )
        self.assertIn(
            "PROVIDER_TRANSCRIPT_ADMISSION_PROVENANCE_DISAGREEMENT", self._codes(broken)
        )

    def test_raw_provider_disagreement_detected(self) -> None:
        broken = self._corrupt(
            "rawprov.db",
            lambda c: c.execute(
                "UPDATE provider_transcript_admissions "
                "SET provider_transcript_result_id = 'provider-transcript-result:mismatch'"
            ),
        )
        codes = self._codes(broken)
        self.assertTrue(
            "PROVIDER_TRANSCRIPT_ADMISSION_RAW_PROVIDER_DISAGREEMENT" in codes
            or "PROVIDER_TRANSCRIPT_ADMISSION_DANGLING_PROVIDER_RESULT" in codes
        )

    def test_segment_count_disagreement_detected(self) -> None:
        broken = self._corrupt(
            "segcount.db",
            lambda c: c.execute(
                "UPDATE provider_transcript_admissions SET segment_count = 5"
            ),
        )
        self.assertIn(
            "PROVIDER_TRANSCRIPT_ADMISSION_SEGMENT_COUNT_DISAGREEMENT", self._codes(broken)
        )

    def test_dangling_raw_transcript_detected(self) -> None:
        broken = self._corrupt(
            "dangraw.db",
            lambda c: c.execute("DELETE FROM raw_transcripts"),
        )
        self.assertIn(
            "PROVIDER_TRANSCRIPT_ADMISSION_DANGLING_RAW_TRANSCRIPT", self._codes(broken)
        )

    def test_noncontiguous_raw_transcript_segments_detected(self) -> None:
        broken = self._corrupt(
            "seggap.db",
            lambda c: c.execute(
                "DELETE FROM raw_transcript_segments WHERE ordinal = 0"
            ),
        )
        self.assertIn(
            "RAW_TRANSCRIPT_SEGMENT_ORDINAL_NONCONTIGUOUS", self._codes(broken)
        )

    def test_blank_admission_identity_detected(self) -> None:
        broken = self._corrupt(
            "blank.db",
            lambda c: c.execute(
                "UPDATE provider_transcript_admissions SET identity = '  '"
            ),
        )
        self.assertIn("MALFORMED_IDENTITY", self._codes(broken))

    def test_duplicate_provider_result_detected_on_tampered_schema(self) -> None:
        path = self.base / "dup.db"
        connection = sqlite3.connect(path)
        try:
            connection.executescript(
                """
                CREATE TABLE schema_metadata (singleton INTEGER PRIMARY KEY, version INTEGER NOT NULL);
                INSERT INTO schema_metadata VALUES (1, 32);
                CREATE TABLE provider_transcript_admissions (
                    identity TEXT PRIMARY KEY,
                    transcript_source_intake_id TEXT,
                    source_media_id TEXT,
                    provider_transcript_result_id TEXT,
                    raw_transcript_id TEXT,
                    provider_reference TEXT,
                    provider_model TEXT,
                    declared_language TEXT,
                    provider_result_ref TEXT,
                    segment_count INTEGER,
                    content_fingerprint TEXT
                );
                INSERT INTO provider_transcript_admissions VALUES
                    ('provider-transcript-admission:a', 'transcript-source-intake:sha256:m', 'sha256:m',
                     'provider-transcript-result:x', 'raw-transcript:a', 'p', NULL, NULL, 'r', 1, 'f');
                INSERT INTO provider_transcript_admissions VALUES
                    ('provider-transcript-admission:b', 'transcript-source-intake:sha256:m', 'sha256:m',
                     'provider-transcript-result:x', 'raw-transcript:b', 'p', NULL, NULL, 'r2', 1, 'f');
                """
            )
            connection.commit()
        finally:
            connection.close()
        self.assertIn(
            "PROVIDER_TRANSCRIPT_ADMISSION_DUPLICATE_PROVIDER_RESULT", self._codes(path)
        )


class CurrentRawTranscriptSelectionValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        from lectureos.application.provider_transcript_admission import (
            build_provider_transcript_document,
        )
        from lectureos.composition import (
            compose_sqlite_current_raw_transcript_selection_service,
            compose_sqlite_media_import_service,
            compose_sqlite_provider_transcript_admission_service,
            compose_sqlite_transcript_source_intake_service,
        )

        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.healthy = self.base / "selection.db"
        connection = initialize_sqlite_database(self.healthy)
        source = self.base / "s.bin"
        source.write_bytes(b"selection-validation \x00\x01")
        media_id = (
            compose_sqlite_media_import_service(connection).import_media(str(source)).record.identity.value
        )
        self.intake = (
            compose_sqlite_transcript_source_intake_service(connection).admit(media_id).intake.identity.value
        )

        def _doc(ref):
            return build_provider_transcript_document(
                {"provider": "fake", "model": "tiny", "language": "ko",
                 "provider_result_ref": ref, "segments": [{"start": 0.0, "end": 1.0, "text": "가"}]}
            )

        admit = compose_sqlite_provider_transcript_admission_service(connection)
        self.raw_a = admit.admit(intake_id=self.intake, document=_doc("A")).admission.raw_transcript_id.value
        self.raw_b = admit.admit(intake_id=self.intake, document=_doc("B")).admission.raw_transcript_id.value
        selection = compose_sqlite_current_raw_transcript_selection_service(connection)
        selection.select(self.intake, self.raw_a)
        selection.select(self.intake, self.raw_b)  # switch -> two rows (sequence 0, 1)
        connection.close()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _corrupt(self, name: str, mutate) -> Path:
        target = self.base / name
        shutil.copyfile(self.healthy, target)
        connection = sqlite3.connect(target)
        try:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute("BEGIN")
            mutate(connection)
            connection.execute("COMMIT")
        finally:
            connection.close()
        return target

    def _codes(self, database: Path) -> set[str]:
        return {d.code for d in validate_database(str(database)).diagnostics}

    def test_healthy_selection_repository_is_clean(self) -> None:
        report = validate_database(str(self.healthy))
        self.assertTrue(report.ok)
        self.assertEqual(report.health, RepositoryHealth.HEALTHY)

    def test_lineage_mismatch_detected(self) -> None:
        broken = self._corrupt(
            "lineage.db",
            lambda c: c.execute(
                "UPDATE current_raw_transcript_selections "
                "SET transcript_source_intake_id = 'transcript-source-intake:sha256:other' "
                "WHERE sequence = 0"
            ),
        )
        # An intake-side change makes both the intake FK and the admission lineage dangle.
        codes = self._codes(broken)
        self.assertTrue(
            "RAW_TRANSCRIPT_SELECTION_LINEAGE_MISMATCH" in codes
            or "RAW_TRANSCRIPT_SELECTION_DANGLING_INTAKE" in codes
        )

    def test_sequence_gap_detected(self) -> None:
        broken = self._corrupt(
            "gap.db",
            lambda c: c.execute(
                "UPDATE current_raw_transcript_selections SET sequence = 5 WHERE sequence = 1"
            ),
        )
        self.assertIn(
            "RAW_TRANSCRIPT_SELECTION_SEQUENCE_NONCONTIGUOUS", self._codes(broken)
        )

    def test_broken_supersession_detected(self) -> None:
        broken = self._corrupt(
            "supersession.db",
            lambda c: c.execute(
                "UPDATE current_raw_transcript_selections "
                "SET previous_selection_id = 'raw-transcript-selection:ghost' WHERE sequence = 1"
            ),
        )
        self.assertIn(
            "RAW_TRANSCRIPT_SELECTION_BROKEN_SUPERSESSION", self._codes(broken)
        )

    def test_dangling_raw_transcript_detected(self) -> None:
        broken = self._corrupt(
            "dangraw.db",
            lambda c: c.execute(
                "UPDATE current_raw_transcript_selections "
                "SET raw_transcript_id = 'raw-transcript:" + "0" * 64 + "' WHERE sequence = 1"
            ),
        )
        codes = self._codes(broken)
        self.assertTrue(
            "RAW_TRANSCRIPT_SELECTION_DANGLING_RAW_TRANSCRIPT" in codes
            or "RAW_TRANSCRIPT_SELECTION_LINEAGE_MISMATCH" in codes
        )

    def test_blank_selection_identity_detected(self) -> None:
        broken = self._corrupt(
            "blank.db",
            lambda c: c.execute(
                "UPDATE current_raw_transcript_selections SET identity = '  ' WHERE sequence = 1"
            ),
        )
        self.assertIn("MALFORMED_IDENTITY", self._codes(broken))


class CorrectionCandidateAdmissionValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        from lectureos.application.correction_candidate_admission import (
            build_correction_candidate_input,
        )
        from lectureos.application.provider_transcript_admission import (
            build_provider_transcript_document,
        )
        from lectureos.composition import (
            compose_sqlite_correction_candidate_admission_service,
            compose_sqlite_current_raw_transcript_selection_service,
            compose_sqlite_media_import_service,
            compose_sqlite_provider_transcript_admission_service,
            compose_sqlite_transcript_source_intake_service,
        )
        from lectureos.persistence import (
            SQLiteRawTranscriptRepository,
            SQLiteTranscriptSegmentRepository,
        )
        from lectureos.transcript.identities import TranscriptId

        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.healthy = self.base / "correction.db"
        connection = initialize_sqlite_database(self.healthy)
        source = self.base / "s.bin"
        source.write_bytes(b"correction-validation \x00\x01")
        media_id = (
            compose_sqlite_media_import_service(connection).import_media(str(source)).record.identity.value
        )
        intake = (
            compose_sqlite_transcript_source_intake_service(connection).admit(media_id).intake.identity.value
        )
        raw = compose_sqlite_provider_transcript_admission_service(connection).admit(
            intake_id=intake,
            document=build_provider_transcript_document(
                {"provider": "fake", "model": "tiny", "language": "ko", "provider_result_ref": "A",
                 "segments": [{"start": 0.0, "end": 2.0, "text": "원본"}]}
            ),
        ).admission.raw_transcript_id.value
        compose_sqlite_current_raw_transcript_selection_service(connection).select(intake, raw)
        segment = SQLiteRawTranscriptRepository(connection).get(TranscriptId(raw)).segment_ids[0].value
        text = SQLiteTranscriptSegmentRepository(connection).get(
            SQLiteRawTranscriptRepository(connection).get(TranscriptId(raw)).segment_ids[0]
        ).text
        compose_sqlite_correction_candidate_admission_service(connection).admit(
            intake_id=intake,
            candidate=build_correction_candidate_input(
                {"raw_transcript_id": raw, "segment_id": segment, "candidate_ref": "c1",
                 "source_type": "manual", "source_reference": "human", "proposed_text": "교정",
                 "source_text_snapshot": text, "rationale": "fix"}
            ),
        )
        connection.close()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _corrupt(self, name: str, mutate) -> Path:
        target = self.base / name
        shutil.copyfile(self.healthy, target)
        connection = sqlite3.connect(target)
        try:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute("BEGIN")
            mutate(connection)
            connection.execute("COMMIT")
        finally:
            connection.close()
        return target

    def _codes(self, database: Path) -> set[str]:
        return {d.code for d in validate_database(str(database)).diagnostics}

    def test_healthy_correction_repository_is_clean(self) -> None:
        report = validate_database(str(self.healthy))
        self.assertTrue(report.ok)
        self.assertEqual(report.health, RepositoryHealth.HEALTHY)

    def test_source_text_disagreement_detected(self) -> None:
        broken = self._corrupt(
            "snapshot.db",
            lambda c: c.execute(
                "UPDATE correction_candidate_admissions SET source_text_snapshot = 'DRIFTED'"
            ),
        )
        self.assertIn("CORRECTION_CANDIDATE_SOURCE_TEXT_DISAGREEMENT", self._codes(broken))

    def test_segment_not_in_raw_transcript_detected(self) -> None:
        broken = self._corrupt(
            "seg.db",
            lambda c: c.execute(
                "UPDATE correction_candidate_admissions "
                "SET raw_transcript_id = 'raw-transcript:" + "9" * 64 + "'"
            ),
        )
        codes = self._codes(broken)
        self.assertTrue(
            "CORRECTION_CANDIDATE_SEGMENT_NOT_IN_RAW_TRANSCRIPT" in codes
            or "CORRECTION_CANDIDATE_DANGLING_RAW_TRANSCRIPT" in codes
            or "CORRECTION_CANDIDATE_RAW_TRANSCRIPT_NOT_IN_INTAKE" in codes
        )

    def test_lineage_disagreement_detected(self) -> None:
        broken = self._corrupt(
            "lineage.db",
            lambda c: c.execute(
                "UPDATE correction_candidates SET segment_id = 'transcript-segment:" + "9" * 64 + ":0'"
            ),
        )
        self.assertIn(
            "CORRECTION_CANDIDATE_ADMISSION_LINEAGE_DISAGREEMENT", self._codes(broken)
        )

    def test_empty_proposed_text_detected(self) -> None:
        broken = self._corrupt(
            "empty.db",
            lambda c: c.execute("UPDATE correction_candidates SET proposed_text = '   '"),
        )
        self.assertIn("CORRECTION_CANDIDATE_EMPTY_PROPOSED_TEXT", self._codes(broken))

    def test_blank_admission_identity_detected(self) -> None:
        broken = self._corrupt(
            "blank.db",
            lambda c: c.execute("UPDATE correction_candidate_admissions SET identity = '  '"),
        )
        self.assertIn("MALFORMED_IDENTITY", self._codes(broken))


class CorrectionCandidateDecisionValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        from lectureos.application.correction_candidate_admission import (
            build_correction_candidate_input,
        )
        from lectureos.application.provider_transcript_admission import (
            build_provider_transcript_document,
        )
        from lectureos.composition import (
            compose_sqlite_correction_candidate_admission_service,
            compose_sqlite_correction_candidate_decision_service,
            compose_sqlite_current_raw_transcript_selection_service,
            compose_sqlite_media_import_service,
            compose_sqlite_provider_transcript_admission_service,
            compose_sqlite_transcript_source_intake_service,
        )
        from lectureos.persistence import (
            SQLiteRawTranscriptRepository,
            SQLiteTranscriptSegmentRepository,
        )
        from lectureos.transcript.identities import TranscriptId

        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.healthy = self.base / "decision.db"
        connection = initialize_sqlite_database(self.healthy)
        source = self.base / "s.bin"
        source.write_bytes(b"decision-validation \x00\x01")
        media_id = compose_sqlite_media_import_service(connection).import_media(str(source)).record.identity.value
        intake = compose_sqlite_transcript_source_intake_service(connection).admit(media_id).intake.identity.value
        raw = compose_sqlite_provider_transcript_admission_service(connection).admit(
            intake_id=intake,
            document=build_provider_transcript_document(
                {"provider": "fake", "model": "tiny", "language": "ko", "provider_result_ref": "A",
                 "segments": [{"start": 0.0, "end": 2.0, "text": "원본"}]}
            ),
        ).admission.raw_transcript_id.value
        compose_sqlite_current_raw_transcript_selection_service(connection).select(intake, raw)
        segment = SQLiteRawTranscriptRepository(connection).get(TranscriptId(raw)).segment_ids[0]
        text = SQLiteTranscriptSegmentRepository(connection).get(segment).text
        candidate = compose_sqlite_correction_candidate_admission_service(connection).admit(
            intake_id=intake,
            candidate=build_correction_candidate_input(
                {"raw_transcript_id": raw, "segment_id": segment.value, "candidate_ref": "c1",
                 "source_type": "manual", "source_reference": "human", "proposed_text": "교정",
                 "source_text_snapshot": text, "rationale": "fix"}
            ),
        ).candidate.identity.value
        service = compose_sqlite_correction_candidate_decision_service(connection)
        service.decide(candidate_id=candidate, kind="accept", reviewer="r:kim")
        service.decide(candidate_id=candidate, kind="reject", reviewer="r:kim")  # append -> two rows
        connection.close()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _corrupt(self, name: str, mutate) -> Path:
        target = self.base / name
        shutil.copyfile(self.healthy, target)
        connection = sqlite3.connect(target)
        try:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute("BEGIN")
            mutate(connection)
            connection.execute("COMMIT")
        finally:
            connection.close()
        return target

    def _codes(self, database: Path) -> set[str]:
        return {d.code for d in validate_database(str(database)).diagnostics}

    def test_healthy_decision_repository_is_clean(self) -> None:
        report = validate_database(str(self.healthy))
        self.assertTrue(report.ok)
        self.assertEqual(report.health, RepositoryHealth.HEALTHY)

    def test_dangling_candidate_detected(self) -> None:
        broken = self._corrupt(
            "dangcand.db",
            lambda c: c.execute(
                "UPDATE correction_candidate_decisions "
                "SET correction_candidate_id = 'correction-candidate:" + "0" * 64 + "' WHERE sequence = 1"
            ),
        )
        codes = self._codes(broken)
        self.assertTrue(
            "CORRECTION_DECISION_DANGLING_CANDIDATE" in codes
            or "CORRECTION_DECISION_SEQUENCE_NONCONTIGUOUS" in codes
        )

    def test_sequence_gap_detected(self) -> None:
        broken = self._corrupt(
            "gap.db",
            lambda c: c.execute(
                "UPDATE correction_candidate_decisions SET sequence = 5 WHERE sequence = 1"
            ),
        )
        self.assertIn("CORRECTION_DECISION_SEQUENCE_NONCONTIGUOUS", self._codes(broken))

    def test_broken_supersession_detected(self) -> None:
        broken = self._corrupt(
            "supersession.db",
            lambda c: c.execute(
                "UPDATE correction_candidate_decisions "
                "SET previous_decision_id = 'correction-candidate-decision:ghost' WHERE sequence = 1"
            ),
        )
        self.assertIn("CORRECTION_DECISION_BROKEN_SUPERSESSION", self._codes(broken))

    def test_blank_decision_identity_detected(self) -> None:
        broken = self._corrupt(
            "blank.db",
            lambda c: c.execute(
                "UPDATE correction_candidate_decisions SET identity = '  ' WHERE sequence = 1"
            ),
        )
        self.assertIn("MALFORMED_IDENTITY", self._codes(broken))


class CorrectedRevisionGenerationValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        from lectureos.application.correction_candidate_admission import (
            build_correction_candidate_input,
        )
        from lectureos.application.provider_transcript_admission import (
            build_provider_transcript_document,
        )
        from lectureos.composition import (
            compose_sqlite_corrected_revision_generation_service,
            compose_sqlite_correction_candidate_admission_service,
            compose_sqlite_correction_candidate_decision_service,
            compose_sqlite_current_raw_transcript_selection_service,
            compose_sqlite_media_import_service,
            compose_sqlite_provider_transcript_admission_service,
            compose_sqlite_transcript_source_intake_service,
        )
        from lectureos.persistence import (
            SQLiteRawTranscriptRepository,
            SQLiteTranscriptSegmentRepository,
        )
        from lectureos.transcript.identities import TranscriptId

        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.healthy = self.base / "generation.db"
        connection = initialize_sqlite_database(self.healthy)
        source = self.base / "s.bin"
        source.write_bytes(b"generation-validation \x00\x01")
        media_id = compose_sqlite_media_import_service(connection).import_media(str(source)).record.identity.value
        intake = compose_sqlite_transcript_source_intake_service(connection).admit(media_id).intake.identity.value
        raw = compose_sqlite_provider_transcript_admission_service(connection).admit(
            intake_id=intake,
            document=build_provider_transcript_document(
                {"provider": "fake", "model": "tiny", "language": "ko", "provider_result_ref": "A",
                 "segments": [{"start": 0.0, "end": 2.0, "text": "원본"}]}
            ),
        ).admission.raw_transcript_id.value
        compose_sqlite_current_raw_transcript_selection_service(connection).select(intake, raw)
        segment = SQLiteRawTranscriptRepository(connection).get(TranscriptId(raw)).segment_ids[0]
        text = SQLiteTranscriptSegmentRepository(connection).get(segment).text
        candidate = compose_sqlite_correction_candidate_admission_service(connection).admit(
            intake_id=intake,
            candidate=build_correction_candidate_input(
                {"raw_transcript_id": raw, "segment_id": segment.value, "candidate_ref": "c1",
                 "source_type": "manual", "source_reference": "human", "proposed_text": "교정",
                 "source_text_snapshot": text, "rationale": "fix"}
            ),
        ).candidate.identity.value
        compose_sqlite_correction_candidate_decision_service(connection).decide(
            candidate_id=candidate, kind="accept", reviewer="r:kim"
        )
        compose_sqlite_corrected_revision_generation_service(connection).generate(candidate_id=candidate)
        # A later Reject: the historical revision must NOT be flagged as corruption (§65).
        compose_sqlite_correction_candidate_decision_service(connection).decide(
            candidate_id=candidate, kind="reject", reviewer="r:kim"
        )
        connection.close()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _corrupt(self, name: str, mutate) -> Path:
        target = self.base / name
        shutil.copyfile(self.healthy, target)
        connection = sqlite3.connect(target)
        try:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute("BEGIN")
            mutate(connection)
            connection.execute("COMMIT")
        finally:
            connection.close()
        return target

    def _codes(self, database: Path) -> set[str]:
        return {d.code for d in validate_database(str(database)).diagnostics}

    def test_healthy_generation_repository_is_clean_even_after_later_reject(self) -> None:
        report = validate_database(str(self.healthy))
        self.assertTrue(report.ok)
        self.assertEqual(report.health, RepositoryHealth.HEALTHY)

    def test_authorizing_decision_not_accept_detected(self) -> None:
        # Point the generation at the (existing) Reject decision: historical authority becomes untrue.
        broken = self._corrupt(
            "notaccept.db",
            lambda c: c.execute(
                "UPDATE corrected_revision_generations SET authorizing_decision_id = ("
                "SELECT identity FROM correction_candidate_decisions WHERE kind = 'reject')"
            ),
        )
        self.assertIn("CORRECTED_REVISION_AUTHORIZING_DECISION_NOT_ACCEPT", self._codes(broken))

    def test_dangling_decision_detected(self) -> None:
        broken = self._corrupt(
            "dangdec.db",
            lambda c: c.execute(
                "UPDATE corrected_revision_generations "
                "SET authorizing_decision_id = 'correction-candidate-decision:ghost'"
            ),
        )
        self.assertIn("CORRECTED_REVISION_DANGLING_DECISION", self._codes(broken))

    def test_parent_mismatch_detected(self) -> None:
        broken = self._corrupt(
            "parent.db",
            lambda c: c.execute(
                "UPDATE corrected_transcript_revisions "
                "SET parent_raw_transcript_id = 'raw-transcript:" + "9" * 64 + "'"
            ),
        )
        self.assertIn("CORRECTED_REVISION_PARENT_MISMATCH", self._codes(broken))

    def test_membership_disagreement_detected(self) -> None:
        broken = self._corrupt(
            "membership.db",
            lambda c: c.execute(
                "DELETE FROM corrected_transcript_revision_segments "
                "WHERE transcript_segment_id = ("
                "SELECT replacement_segment_id FROM corrected_revision_generations)"
            ),
        )
        self.assertIn("CORRECTED_REVISION_MEMBERSHIP_DISAGREEMENT", self._codes(broken))

    def test_blank_generation_identity_detected(self) -> None:
        broken = self._corrupt(
            "blank.db",
            lambda c: c.execute("UPDATE corrected_revision_generations SET identity = '  '"),
        )
        self.assertIn("MALFORMED_IDENTITY", self._codes(broken))


class CorrectedRevisionSelectionValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        from lectureos.application.correction_candidate_admission import (
            build_correction_candidate_input,
        )
        from lectureos.application.provider_transcript_admission import (
            build_provider_transcript_document,
        )
        from lectureos.composition import (
            compose_sqlite_corrected_revision_generation_service,
            compose_sqlite_corrected_revision_selection_service,
            compose_sqlite_correction_candidate_admission_service,
            compose_sqlite_correction_candidate_decision_service,
            compose_sqlite_current_raw_transcript_selection_service,
            compose_sqlite_media_import_service,
            compose_sqlite_provider_transcript_admission_service,
            compose_sqlite_transcript_source_intake_service,
        )
        from lectureos.persistence import (
            SQLiteRawTranscriptRepository,
            SQLiteTranscriptSegmentRepository,
        )

        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.healthy = self.base / "selection.db"
        connection = initialize_sqlite_database(self.healthy)
        source = self.base / "s.bin"
        source.write_bytes(b"selection-validation \x00\x01")
        media_id = compose_sqlite_media_import_service(connection).import_media(str(source)).record.identity.value
        intake = compose_sqlite_transcript_source_intake_service(connection).admit(media_id).intake.identity.value
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
        raw_record = SQLiteRawTranscriptRepository(connection).get(raw.raw_transcript_id)
        segment = raw_record.segment_ids[0]
        text = SQLiteTranscriptSegmentRepository(connection).get(segment).text
        candidate = compose_sqlite_correction_candidate_admission_service(connection).admit(
            intake_id=intake,
            candidate=build_correction_candidate_input(
                {"raw_transcript_id": raw.raw_transcript_id.value, "segment_id": segment.value,
                 "candidate_ref": "c1", "source_type": "manual", "source_reference": "human",
                 "proposed_text": "교정", "source_text_snapshot": text, "rationale": "fix"}
            ),
        ).candidate.identity.value
        decisions = compose_sqlite_correction_candidate_decision_service(connection)
        decisions.decide(candidate_id=candidate, kind="accept", reviewer="r:kim")
        revision = compose_sqlite_corrected_revision_generation_service(connection).generate(
            candidate_id=candidate
        ).revision.identity.value
        selection = compose_sqlite_corrected_revision_selection_service(connection)
        selection.select_revision(revision_id=revision, reviewer="s:kim")
        selection.select_raw_fallback(intake_id=intake, reviewer="s:kim")  # two rows
        # Later Reject: the historically selected revision must NOT be flagged as corruption (§44/§52).
        decisions.decide(candidate_id=candidate, kind="reject", reviewer="r:kim")
        connection.close()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _corrupt(self, name: str, mutate) -> Path:
        target = self.base / name
        shutil.copyfile(self.healthy, target)
        connection = sqlite3.connect(target)
        try:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute("BEGIN")
            mutate(connection)
            connection.execute("COMMIT")
        finally:
            connection.close()
        return target

    def _codes(self, database: Path) -> set[str]:
        return {d.code for d in validate_database(str(database)).diagnostics}

    def test_healthy_selection_repository_is_clean_even_after_later_reject(self) -> None:
        report = validate_database(str(self.healthy))
        self.assertTrue(report.ok)
        self.assertEqual(report.health, RepositoryHealth.HEALTHY)

    def test_dangling_revision_detected(self) -> None:
        broken = self._corrupt(
            "dangrev.db",
            lambda c: c.execute(
                "UPDATE corrected_revision_selections "
                "SET corrected_revision_id = 'corrected-revision:" + "0" * 64 + "' "
                "WHERE kind = 'corrected_revision'"
            ),
        )
        codes = self._codes(broken)
        self.assertTrue(
            "CORRECTED_SELECTION_DANGLING_REVISION" in codes
            or "CORRECTED_SELECTION_CONTEXT_MISMATCH" in codes
        )

    def test_context_mismatch_detected(self) -> None:
        broken = self._corrupt(
            "context.db",
            lambda c: c.execute(
                "UPDATE corrected_revision_selections "
                "SET transcript_source_intake_id = 'transcript-source-intake:sha256:other'"
            ),
        )
        codes = self._codes(broken)
        self.assertTrue(
            "CORRECTED_SELECTION_CONTEXT_MISMATCH" in codes
            or "CORRECTED_SELECTION_DANGLING_INTAKE" in codes
        )

    def test_kind_revision_disagreement_detected_on_tampered_schema(self) -> None:
        # The real schema CHECK-enforces kind/revision consistency; exercise the read-only check on a
        # minimal tampered schema where that constraint is absent (the established duplicate-test pattern).
        path = self.base / "kind.db"
        connection = sqlite3.connect(path)
        try:
            connection.executescript(
                """
                CREATE TABLE schema_metadata (singleton INTEGER PRIMARY KEY, version INTEGER NOT NULL);
                INSERT INTO schema_metadata VALUES (1, 37);
                CREATE TABLE corrected_revision_selections (
                    identity TEXT PRIMARY KEY,
                    transcript_source_intake_id TEXT,
                    kind TEXT,
                    corrected_revision_id TEXT,
                    reviewer TEXT,
                    sequence INTEGER,
                    previous_selection_id TEXT,
                    rationale TEXT
                );
                INSERT INTO corrected_revision_selections VALUES
                    ('corrected-revision-selection:x', 'transcript-source-intake:sha256:m',
                     'corrected_revision', NULL, 's', 0, NULL, NULL);
                """
            )
            connection.commit()
        finally:
            connection.close()
        self.assertIn("CORRECTED_SELECTION_KIND_REVISION_DISAGREEMENT", self._codes(path))

    def test_sequence_gap_detected(self) -> None:
        broken = self._corrupt(
            "gap.db",
            lambda c: c.execute(
                "UPDATE corrected_revision_selections SET sequence = 5 WHERE sequence = 1"
            ),
        )
        self.assertIn("CORRECTED_SELECTION_SEQUENCE_NONCONTIGUOUS", self._codes(broken))

    def test_broken_supersession_detected(self) -> None:
        broken = self._corrupt(
            "supersession.db",
            lambda c: c.execute(
                "UPDATE corrected_revision_selections "
                "SET previous_selection_id = 'corrected-revision-selection:ghost' WHERE sequence = 1"
            ),
        )
        self.assertIn("CORRECTED_SELECTION_BROKEN_SUPERSESSION", self._codes(broken))

    def test_blank_selection_identity_detected(self) -> None:
        broken = self._corrupt(
            "blank.db",
            lambda c: c.execute(
                "UPDATE corrected_revision_selections SET identity = '  ' WHERE sequence = 1"
            ),
        )
        self.assertIn("MALFORMED_IDENTITY", self._codes(broken))


class EffectiveTranscriptConsumptionValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        from lectureos.application.correction_candidate_admission import (
            build_correction_candidate_input,
        )
        from lectureos.application.provider_transcript_admission import (
            build_provider_transcript_document,
        )
        from lectureos.composition import (
            compose_sqlite_corrected_revision_generation_service,
            compose_sqlite_corrected_revision_selection_service,
            compose_sqlite_correction_candidate_admission_service,
            compose_sqlite_correction_candidate_decision_service,
            compose_sqlite_current_raw_transcript_selection_service,
            compose_sqlite_effective_transcript_consumption_service,
            compose_sqlite_media_import_service,
            compose_sqlite_provider_transcript_admission_service,
            compose_sqlite_transcript_source_intake_service,
        )
        from lectureos.persistence import (
            SQLiteRawTranscriptRepository,
            SQLiteTranscriptSegmentRepository,
        )

        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.healthy = self.base / "consumption.db"
        connection = initialize_sqlite_database(self.healthy)
        source = self.base / "s.bin"
        source.write_bytes(b"consumption-validation \x00\x01")
        media_id = compose_sqlite_media_import_service(connection).import_media(str(source)).record.identity.value
        intake = compose_sqlite_transcript_source_intake_service(connection).admit(media_id).intake.identity.value
        provider = compose_sqlite_provider_transcript_admission_service(connection)
        raw = provider.admit(
            intake_id=intake,
            document=build_provider_transcript_document(
                {"provider": "fake", "model": "tiny", "language": "ko", "provider_result_ref": "A",
                 "segments": [{"start": 0.0, "end": 2.0, "text": "원본"}]}
            ),
        ).admission
        self.raw_1 = raw.raw_transcript_id.value
        raw_selection = compose_sqlite_current_raw_transcript_selection_service(connection)
        raw_selection.select(intake, self.raw_1)
        consumption = compose_sqlite_effective_transcript_consumption_service(connection)
        consumption.consume(intake_id=intake)  # raw binding
        raw_record = SQLiteRawTranscriptRepository(connection).get(raw.raw_transcript_id)
        segment = raw_record.segment_ids[0]
        text = SQLiteTranscriptSegmentRepository(connection).get(segment).text
        candidate = compose_sqlite_correction_candidate_admission_service(connection).admit(
            intake_id=intake,
            candidate=build_correction_candidate_input(
                {"raw_transcript_id": self.raw_1, "segment_id": segment.value,
                 "candidate_ref": "c1", "source_type": "manual", "source_reference": "human",
                 "proposed_text": "교정", "source_text_snapshot": text, "rationale": "fix"}
            ),
        ).candidate.identity.value
        decisions = compose_sqlite_correction_candidate_decision_service(connection)
        decisions.decide(candidate_id=candidate, kind="accept", reviewer="r:kim")
        revision = compose_sqlite_corrected_revision_generation_service(connection).generate(
            candidate_id=candidate
        ).revision.identity.value
        compose_sqlite_corrected_revision_selection_service(connection).select_revision(
            revision_id=revision, reviewer="s:kim"
        )
        consumption.consume(intake_id=intake)  # corrected binding
        # Later authority changes: staleness must NEVER be corruption (040 §21 S3-11).
        decisions.decide(candidate_id=candidate, kind="reject", reviewer="r:kim")
        raw_2 = provider.admit(
            intake_id=intake,
            document=build_provider_transcript_document(
                {"provider": "fake", "model": "tiny", "language": "ko", "provider_result_ref": "B",
                 "segments": [{"start": 0.0, "end": 2.0, "text": "다른 원본"}]}
            ),
        ).admission.raw_transcript_id.value
        self.second_raw_selection = raw_selection.select(intake, raw_2).selection.identity.value
        connection.close()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _corrupt(self, name: str, mutate) -> Path:
        target = self.base / name
        shutil.copyfile(self.healthy, target)
        connection = sqlite3.connect(target)
        try:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute("BEGIN")
            mutate(connection)
            connection.execute("COMMIT")
        finally:
            connection.close()
        return target

    def _codes(self, database: Path) -> set[str]:
        return {d.code for d in validate_database(str(database)).diagnostics}

    def test_healthy_bindings_stay_clean_after_reject_and_raw_switch(self) -> None:
        report = validate_database(str(self.healthy))
        self.assertTrue(report.ok)
        self.assertEqual(report.health, RepositoryHealth.HEALTHY)

    def test_dangling_intake_detected(self) -> None:
        broken = self._corrupt(
            "intake.db",
            lambda c: c.execute(
                "UPDATE effective_transcript_consumptions "
                "SET transcript_source_intake_id = 'transcript-source-intake:sha256:ghost'"
            ),
        )
        self.assertIn("CONSUMPTION_DANGLING_INTAKE", self._codes(broken))

    def test_dangling_raw_source_detected(self) -> None:
        ghost = "raw-transcript:" + "0" * 64
        broken = self._corrupt(
            "rawsource.db",
            lambda c: c.execute(
                "UPDATE effective_transcript_consumptions "
                f"SET parent_raw_transcript_id = '{ghost}', source_transcript_identity = '{ghost}' "
                "WHERE source_kind = 'raw_transcript'"
            ),
        )
        self.assertIn("CONSUMPTION_DANGLING_RAW_SOURCE", self._codes(broken))

    def test_dangling_revision_source_detected(self) -> None:
        ghost = "corrected-revision:" + "0" * 64
        broken = self._corrupt(
            "revsource.db",
            lambda c: c.execute(
                "UPDATE effective_transcript_consumptions "
                f"SET corrected_revision_id = '{ghost}', source_transcript_identity = '{ghost}' "
                "WHERE source_kind = 'corrected_transcript_revision'"
            ),
        )
        self.assertIn("CONSUMPTION_DANGLING_REVISION_SOURCE", self._codes(broken))

    def test_dangling_selection_authority_detected(self) -> None:
        broken = self._corrupt(
            "authority.db",
            lambda c: c.execute(
                "UPDATE effective_transcript_consumptions "
                "SET raw_selection_id = 'raw-transcript-selection:ghost'"
            ),
        )
        self.assertIn("CONSUMPTION_DANGLING_SELECTION", self._codes(broken))

    def test_authority_mismatch_detected(self) -> None:
        # Point a binding's observed raw-selection provenance at the (real) later selection whose
        # raw transcript differs from the binding's recorded parent.
        broken = self._corrupt(
            "mismatch.db",
            lambda c: c.execute(
                "UPDATE effective_transcript_consumptions "
                f"SET raw_selection_id = '{self.second_raw_selection}'"
            ),
        )
        self.assertIn("CONSUMPTION_AUTHORITY_MISMATCH", self._codes(broken))

    def test_parent_mismatch_detected(self) -> None:
        broken = self._corrupt(
            "parent.db",
            lambda c: c.execute(
                "UPDATE effective_transcript_consumptions "
                "SET parent_raw_transcript_id = ("
                "  SELECT identity FROM raw_transcripts WHERE identity <> ("
                "    SELECT parent_raw_transcript_id FROM corrected_transcript_revisions LIMIT 1"
                "  ) LIMIT 1"
                ") WHERE source_kind = 'corrected_transcript_revision'"
            ),
        )
        self.assertIn("CONSUMPTION_PARENT_MISMATCH", self._codes(broken))

    def test_fingerprint_mismatch_detected(self) -> None:
        broken = self._corrupt(
            "fingerprint.db",
            lambda c: c.execute(
                "UPDATE effective_transcript_consumptions SET content_fingerprint = ?",
                ("f" * 64,),
            ),
        )
        self.assertIn("CONSUMPTION_FINGERPRINT_MISMATCH", self._codes(broken))

    def test_segment_count_mismatch_detected(self) -> None:
        broken = self._corrupt(
            "count.db",
            lambda c: c.execute(
                "UPDATE effective_transcript_consumptions SET segment_count = 42"
            ),
        )
        self.assertIn("CONSUMPTION_FINGERPRINT_MISMATCH", self._codes(broken))

    def test_source_kind_disagreement_detected_on_tampered_schema(self) -> None:
        # The real schema CHECK-enforces kind/state consistency; exercise the read-only check on a
        # minimal tampered schema where that constraint is absent (the established pattern).
        path = self.base / "kind.db"
        connection = sqlite3.connect(path)
        try:
            connection.executescript(
                """
                CREATE TABLE schema_metadata (singleton INTEGER PRIMARY KEY, version INTEGER NOT NULL);
                INSERT INTO schema_metadata VALUES (1, 38);
                CREATE TABLE effective_transcript_consumptions (
                    identity TEXT PRIMARY KEY,
                    consumer_kind TEXT,
                    transcript_source_intake_id TEXT,
                    resolution_state TEXT,
                    source_kind TEXT,
                    source_transcript_identity TEXT,
                    parent_raw_transcript_id TEXT,
                    corrected_revision_id TEXT,
                    raw_selection_id TEXT,
                    corrected_selection_id TEXT,
                    content_fingerprint TEXT,
                    segment_count INTEGER
                );
                INSERT INTO effective_transcript_consumptions VALUES
                    ('transcript-consumption:x', 'transcript_consumption_manifest',
                     'transcript-source-intake:sha256:m', 'no_history', 'raw_transcript',
                     'raw-transcript:a', 'raw-transcript:a', 'corrected-revision:b',
                     'raw-transcript-selection:s', NULL, 'f', 1);
                """
            )
            connection.commit()
        finally:
            connection.close()
        self.assertIn("CONSUMPTION_SOURCE_KIND_DISAGREEMENT", self._codes(path))


class EffectiveSubtitleCandidateValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        from lectureos.application.correction_candidate_admission import (
            build_correction_candidate_input,
        )
        from lectureos.application.provider_transcript_admission import (
            build_provider_transcript_document,
        )
        from lectureos.composition import (
            compose_sqlite_corrected_revision_generation_service,
            compose_sqlite_corrected_revision_selection_service,
            compose_sqlite_correction_candidate_admission_service,
            compose_sqlite_correction_candidate_decision_service,
            compose_sqlite_current_raw_transcript_selection_service,
            compose_sqlite_effective_subtitle_generation_service,
            compose_sqlite_media_import_service,
            compose_sqlite_provider_transcript_admission_service,
            compose_sqlite_transcript_source_intake_service,
        )
        from lectureos.persistence import (
            SQLiteRawTranscriptRepository,
            SQLiteTranscriptSegmentRepository,
        )

        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.healthy = self.base / "effective-subtitle.db"
        connection = initialize_sqlite_database(self.healthy)
        source = self.base / "s.bin"
        source.write_bytes(b"effective-subtitle-validation \x00\x01")
        media_id = compose_sqlite_media_import_service(connection).import_media(str(source)).record.identity.value
        intake = compose_sqlite_transcript_source_intake_service(connection).admit(media_id).intake.identity.value
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
        generation = compose_sqlite_effective_subtitle_generation_service(connection)
        generation.generate(intake_id=intake)  # raw candidate
        segment = SQLiteRawTranscriptRepository(connection).get(raw.raw_transcript_id).segment_ids[0]
        text = SQLiteTranscriptSegmentRepository(connection).get(segment).text
        candidate = compose_sqlite_correction_candidate_admission_service(connection).admit(
            intake_id=intake,
            candidate=build_correction_candidate_input(
                {"raw_transcript_id": raw.raw_transcript_id.value, "segment_id": segment.value,
                 "candidate_ref": "c1", "source_type": "manual", "source_reference": "human",
                 "proposed_text": "교정", "source_text_snapshot": text, "rationale": "fix"}
            ),
        ).candidate.identity.value
        decisions = compose_sqlite_correction_candidate_decision_service(connection)
        decisions.decide(candidate_id=candidate, kind="accept", reviewer="r:kim")
        revision = compose_sqlite_corrected_revision_generation_service(connection).generate(
            candidate_id=candidate
        ).revision.identity.value
        compose_sqlite_corrected_revision_selection_service(connection).select_revision(
            revision_id=revision, reviewer="s:kim"
        )
        generation.generate(intake_id=intake)  # corrected candidate
        # Later Reject: both candidates become stale/derived facts — NEVER corruption.
        decisions.decide(candidate_id=candidate, kind="reject", reviewer="r:kim")
        connection.close()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _corrupt(self, name: str, mutate) -> Path:
        target = self.base / name
        shutil.copyfile(self.healthy, target)
        connection = sqlite3.connect(target)
        try:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute("BEGIN")
            mutate(connection)
            connection.execute("COMMIT")
        finally:
            connection.close()
        return target

    def _codes(self, database: Path) -> set[str]:
        return {d.code for d in validate_database(str(database)).diagnostics}

    def test_healthy_candidates_stay_clean_after_later_reject(self) -> None:
        report = validate_database(str(self.healthy))
        self.assertTrue(report.ok)
        self.assertEqual(report.health, RepositoryHealth.HEALTHY)

    def test_dangling_binding_detected(self) -> None:
        broken = self._corrupt(
            "binding.db",
            lambda c: c.execute(
                "UPDATE subtitle_effective_candidates "
                "SET consumption_binding_id = 'transcript-consumption:" + "0" * 64 + "' "
                "WHERE source_kind = 'raw_transcript'"
            ),
        )
        self.assertIn("EFFECTIVE_SUBTITLE_DANGLING_BINDING", self._codes(broken))

    def test_binding_mismatch_detected(self) -> None:
        # A candidate whose recorded snapshot fingerprint disagrees with its immutable binding.
        broken = self._corrupt(
            "mismatch.db",
            lambda c: c.execute(
                "UPDATE subtitle_effective_candidates SET source_snapshot_fingerprint = ? "
                "WHERE source_kind = 'raw_transcript'",
                ("f" * 64,),
            ),
        )
        self.assertIn("EFFECTIVE_SUBTITLE_BINDING_MISMATCH", self._codes(broken))

    def test_cue_count_mismatch_detected(self) -> None:
        broken = self._corrupt(
            "count.db",
            lambda c: c.execute("UPDATE subtitle_effective_candidates SET cue_count = 5"),
        )
        self.assertIn("EFFECTIVE_SUBTITLE_CUE_COUNT_MISMATCH", self._codes(broken))

    def test_orphan_cue_and_lineage_detected(self) -> None:
        broken = self._corrupt(
            "orphan.db",
            lambda c: c.execute(
                "UPDATE subtitle_effective_candidate_cues "
                "SET candidate_id = 'subtitle-effective-candidate:" + "0" * 64 + "' "
                "WHERE rowid = (SELECT MIN(rowid) FROM subtitle_effective_candidate_cues)"
            ),
        )
        codes = self._codes(broken)
        self.assertIn("EFFECTIVE_SUBTITLE_ORPHAN_CUE", codes)

    def test_lineage_without_cue_detected(self) -> None:
        broken = self._corrupt(
            "lineage.db",
            lambda c: c.execute(
                "UPDATE subtitle_effective_candidate_cue_segments "
                "SET cue_id = 'subtitle-effective-cue:" + "0" * 64 + "' "
                "WHERE rowid = (SELECT MIN(rowid) FROM subtitle_effective_candidate_cue_segments)"
            ),
        )
        codes = self._codes(broken)
        self.assertIn("EFFECTIVE_SUBTITLE_ORPHAN_CUE_SEGMENT", codes)
        self.assertIn("EFFECTIVE_SUBTITLE_CUE_WITHOUT_SOURCE_SEGMENT", codes)

    def test_cue_segment_outside_snapshot_detected(self) -> None:
        # Point the corrected candidate's replaced-segment cue lineage at the ORIGINAL raw
        # segment: that segment is not part of the corrected revision's snapshot membership.
        broken = self._corrupt(
            "outside.db",
            lambda c: c.execute(
                """
                UPDATE subtitle_effective_candidate_cue_segments
                SET transcript_segment_id = (
                    SELECT g.replaced_segment_id FROM corrected_revision_generations g LIMIT 1
                )
                WHERE cue_id IN (
                    SELECT q.identity FROM subtitle_effective_candidate_cues q
                    JOIN subtitle_effective_candidates cc ON cc.identity = q.candidate_id
                    WHERE cc.source_kind = 'corrected_transcript_revision' AND q.ordinal = 0
                )
                """
            ),
        )
        self.assertIn("EFFECTIVE_SUBTITLE_CUE_SEGMENT_OUTSIDE_SNAPSHOT", self._codes(broken))

    def test_passthrough_content_mismatch_detected(self) -> None:
        broken = self._corrupt(
            "content.db",
            lambda c: c.execute(
                "UPDATE subtitle_effective_candidate_cues SET text = '조작된 텍스트'"
            ),
        )
        self.assertIn("EFFECTIVE_SUBTITLE_CUE_CONTENT_MISMATCH", self._codes(broken))


class EffectiveSubtitleReviewSubjectValidationTests(unittest.TestCase):
    def setUp(self) -> None:
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

        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.healthy = self.base / "review-subject.db"
        connection = initialize_sqlite_database(self.healthy)
        source = self.base / "s.bin"
        source.write_bytes(b"review-subject-validation \x00\x01")
        media_id = compose_sqlite_media_import_service(connection).import_media(str(source)).record.identity.value
        intake = compose_sqlite_transcript_source_intake_service(connection).admit(media_id).intake.identity.value
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
        ).candidate.identity.value
        compose_sqlite_effective_subtitle_review_preparation_service(connection).prepare_review(
            candidate_id=candidate
        )
        connection.close()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _corrupt(self, name: str, mutate) -> Path:
        target = self.base / name
        shutil.copyfile(self.healthy, target)
        connection = sqlite3.connect(target)
        try:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute("BEGIN")
            mutate(connection)
            connection.execute("COMMIT")
        finally:
            connection.close()
        return target

    def _codes(self, database: Path) -> set[str]:
        return {d.code for d in validate_database(str(database)).diagnostics}

    def test_healthy_subject_without_decision_is_clean(self) -> None:
        # No Human Decision, no reviewer, no selection, no export — none of that is corruption.
        report = validate_database(str(self.healthy))
        self.assertTrue(report.ok)
        self.assertEqual(report.health, RepositoryHealth.HEALTHY)

    def test_dangling_candidate_detected(self) -> None:
        broken = self._corrupt(
            "dangling.db",
            lambda c: c.execute(
                "UPDATE subtitle_effective_review_subjects "
                "SET candidate_id = 'subtitle-effective-candidate:" + "0" * 64 + "'"
            ),
        )
        self.assertIn("EFFECTIVE_REVIEW_SUBJECT_DANGLING_CANDIDATE", self._codes(broken))

    def test_unsupported_preparation_detected(self) -> None:
        broken = self._corrupt(
            "version.db",
            lambda c: c.execute(
                "UPDATE subtitle_effective_review_subjects SET preparation_version = 9"
            ),
        )
        self.assertIn("EFFECTIVE_REVIEW_SUBJECT_UNSUPPORTED_PREPARATION", self._codes(broken))

    def test_key_and_identity_mismatch_detected(self) -> None:
        broken = self._corrupt(
            "key.db",
            lambda c: c.execute(
                "UPDATE subtitle_effective_review_subjects SET preparation_key = 'tampered:key'"
            ),
        )
        self.assertIn("EFFECTIVE_REVIEW_SUBJECT_KEY_MISMATCH", self._codes(broken))
        broken = self._corrupt(
            "identity.db",
            lambda c: c.execute(
                "UPDATE subtitle_effective_review_subjects "
                "SET identity = 'subtitle-effective-review-subject:" + "0" * 64 + "'"
            ),
        )
        self.assertIn("EFFECTIVE_REVIEW_SUBJECT_IDENTITY_MISMATCH", self._codes(broken))

    def test_graph_fingerprint_mismatch_detected(self) -> None:
        # Tamper the underlying cue text: the stored subject fingerprint no longer matches the
        # actual candidate graph.
        broken = self._corrupt(
            "graph.db",
            lambda c: c.execute(
                "UPDATE subtitle_effective_candidate_cues SET text = '조작된 텍스트'"
            ),
        )
        self.assertIn(
            "EFFECTIVE_REVIEW_SUBJECT_GRAPH_FINGERPRINT_MISMATCH", self._codes(broken)
        )


class EffectiveSubtitleReviewDecisionValidationTests(unittest.TestCase):
    def setUp(self) -> None:
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

        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.healthy = self.base / "review-decision.db"
        connection = initialize_sqlite_database(self.healthy)
        source = self.base / "s.bin"
        source.write_bytes(b"review-decision-validation \x00\x01")
        media_id = compose_sqlite_media_import_service(connection).import_media(str(source)).record.identity.value
        intake = compose_sqlite_transcript_source_intake_service(connection).admit(media_id).intake.identity.value
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
        ).candidate.identity.value
        subject = compose_sqlite_effective_subtitle_review_preparation_service(connection).prepare_review(
            candidate_id=candidate
        ).subject.identity.value
        decisions = compose_sqlite_effective_subtitle_review_decision_service(connection)
        # Healthy history: reject superseded by accept — reject/modify/superseded are never corruption.
        decisions.decide(review_subject_id=subject, kind="reject", reviewer="reviewer:kim")
        decisions.decide(review_subject_id=subject, kind="accept", reviewer="reviewer:kim")
        connection.close()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _corrupt(self, name: str, mutate) -> Path:
        target = self.base / name
        shutil.copyfile(self.healthy, target)
        connection = sqlite3.connect(target)
        try:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute("BEGIN")
            mutate(connection)
            connection.execute("COMMIT")
        finally:
            connection.close()
        return target

    def _codes(self, database: Path) -> set[str]:
        return {d.code for d in validate_database(str(database)).diagnostics}

    def test_healthy_superseded_history_is_clean(self) -> None:
        report = validate_database(str(self.healthy))
        self.assertTrue(report.ok)
        self.assertEqual(report.health, RepositoryHealth.HEALTHY)

    def test_dangling_subject_detected(self) -> None:
        broken = self._corrupt(
            "dangling.db",
            lambda c: c.execute(
                "UPDATE subtitle_effective_review_decisions "
                "SET review_subject_id = 'subtitle-effective-review-subject:" + "0" * 64 + "'"
            ),
        )
        self.assertIn("EFFECTIVE_REVIEW_DECISION_DANGLING_SUBJECT", self._codes(broken))

    def test_identity_and_fingerprint_mismatch_detected(self) -> None:
        broken = self._corrupt(
            "identity.db",
            lambda c: c.execute(
                "UPDATE subtitle_effective_review_decisions "
                "SET identity = 'subtitle-effective-review-decision:" + "0" * 64 + "' "
                "WHERE sequence = 1"
            ),
        )
        self.assertIn("EFFECTIVE_REVIEW_DECISION_IDENTITY_MISMATCH", self._codes(broken))
        broken = self._corrupt(
            "reviewer.db",
            lambda c: c.execute(
                "UPDATE subtitle_effective_review_decisions SET reviewer = 'reviewer:evil' "
                "WHERE sequence = 0"
            ),
        )
        self.assertIn("EFFECTIVE_REVIEW_DECISION_FINGERPRINT_MISMATCH", self._codes(broken))

    def test_sequence_gap_detected(self) -> None:
        broken = self._corrupt(
            "gap.db",
            lambda c: c.execute(
                "UPDATE subtitle_effective_review_decisions SET sequence = 5 WHERE sequence = 1"
            ),
        )
        self.assertIn("EFFECTIVE_REVIEW_DECISION_SEQUENCE_NONCONTIGUOUS", self._codes(broken))

    def test_broken_supersession_detected(self) -> None:
        broken = self._corrupt(
            "supersession.db",
            lambda c: c.execute(
                "UPDATE subtitle_effective_review_decisions "
                "SET previous_decision_id = 'subtitle-effective-review-decision:ghost' "
                "WHERE sequence = 1"
            ),
        )
        self.assertIn("EFFECTIVE_REVIEW_DECISION_BROKEN_SUPERSESSION", self._codes(broken))

    def test_unsupported_kind_detected_on_tampered_schema(self) -> None:
        path = self.base / "kind.db"
        connection = sqlite3.connect(path)
        try:
            connection.executescript(
                """
                CREATE TABLE schema_metadata (singleton INTEGER PRIMARY KEY, version INTEGER NOT NULL);
                INSERT INTO schema_metadata VALUES (1, 41);
                CREATE TABLE subtitle_effective_review_decisions (
                    identity TEXT PRIMARY KEY,
                    review_subject_id TEXT,
                    kind TEXT,
                    reviewer TEXT,
                    sequence INTEGER,
                    content_fingerprint TEXT,
                    previous_decision_id TEXT,
                    rationale TEXT
                );
                INSERT INTO subtitle_effective_review_decisions VALUES
                    ('subtitle-effective-review-decision:x',
                     'subtitle-effective-review-subject:s', 'approve', 'reviewer:kim', 0,
                     'f', NULL, NULL);
                """
            )
            connection.commit()
        finally:
            connection.close()
        self.assertIn("EFFECTIVE_REVIEW_DECISION_UNSUPPORTED_KIND", self._codes(path))


class EffectiveSubtitleFinalSelectionValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        from lectureos.application.provider_transcript_admission import (
            build_provider_transcript_document,
        )
        from lectureos.composition import (
            compose_sqlite_current_raw_transcript_selection_service,
            compose_sqlite_effective_subtitle_final_selection_service,
            compose_sqlite_effective_subtitle_generation_service,
            compose_sqlite_effective_subtitle_review_decision_service,
            compose_sqlite_effective_subtitle_review_preparation_service,
            compose_sqlite_media_import_service,
            compose_sqlite_provider_transcript_admission_service,
            compose_sqlite_transcript_source_intake_service,
        )

        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.healthy = self.base / "final-selection.db"
        connection = initialize_sqlite_database(self.healthy)
        source = self.base / "s.bin"
        source.write_bytes(b"final-selection-validation \x00\x01")
        media_id = compose_sqlite_media_import_service(connection).import_media(str(source)).record.identity.value
        intake = compose_sqlite_transcript_source_intake_service(connection).admit(media_id).intake.identity.value
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
        ).candidate.identity.value
        subject = compose_sqlite_effective_subtitle_review_preparation_service(connection).prepare_review(
            candidate_id=candidate
        ).subject.identity.value
        decisions = compose_sqlite_effective_subtitle_review_decision_service(connection)
        decisions.decide(review_subject_id=subject, kind="accept", reviewer="reviewer:kim")
        selection = compose_sqlite_effective_subtitle_final_selection_service(connection)
        selection.select_final(review_subject_id=subject, selector="selector:park")
        # Healthy staleness: the supporting Accept is later superseded — never corruption.
        decisions.decide(review_subject_id=subject, kind="reject", reviewer="reviewer:kim")
        connection.close()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _corrupt(self, name: str, mutate) -> Path:
        target = self.base / name
        shutil.copyfile(self.healthy, target)
        connection = sqlite3.connect(target)
        try:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute("BEGIN")
            mutate(connection)
            connection.execute("COMMIT")
        finally:
            connection.close()
        return target

    def _codes(self, database: Path) -> set[str]:
        return {d.code for d in validate_database(str(database)).diagnostics}

    def test_healthy_selection_with_superseded_support_is_clean(self) -> None:
        report = validate_database(str(self.healthy))
        self.assertTrue(report.ok)
        self.assertEqual(report.health, RepositoryHealth.HEALTHY)

    def test_dangling_references_detected(self) -> None:
        broken = self._corrupt(
            "subject.db",
            lambda c: c.execute(
                "UPDATE subtitle_effective_final_selections "
                "SET review_subject_id = 'subtitle-effective-review-subject:" + "0" * 64 + "'"
            ),
        )
        self.assertIn("EFFECTIVE_FINAL_SELECTION_DANGLING_SUBJECT", self._codes(broken))
        broken = self._corrupt(
            "decision.db",
            lambda c: c.execute(
                "UPDATE subtitle_effective_final_selections "
                "SET supporting_decision_id = 'subtitle-effective-review-decision:" + "0" * 64 + "'"
            ),
        )
        self.assertIn("EFFECTIVE_FINAL_SELECTION_DANGLING_DECISION", self._codes(broken))

    def test_non_accept_supporting_decision_detected(self) -> None:
        # Point the selection at the (real) later reject decision — lineage joins the same
        # subject, but the supporting kind is not accept.
        broken = self._corrupt(
            "kind.db",
            lambda c: c.execute(
                "UPDATE subtitle_effective_final_selections "
                "SET supporting_decision_id = ("
                "  SELECT identity FROM subtitle_effective_review_decisions "
                "  WHERE kind = 'reject' LIMIT 1)"
            ),
        )
        self.assertIn("EFFECTIVE_FINAL_SELECTION_DECISION_NOT_ACCEPT", self._codes(broken))

    def test_identity_and_fingerprint_mismatch_detected(self) -> None:
        broken = self._corrupt(
            "identity.db",
            lambda c: c.execute(
                "UPDATE subtitle_effective_final_selections "
                "SET identity = 'subtitle-effective-final-selection:" + "0" * 64 + "'"
            ),
        )
        self.assertIn("EFFECTIVE_FINAL_SELECTION_IDENTITY_MISMATCH", self._codes(broken))
        broken = self._corrupt(
            "selector.db",
            lambda c: c.execute(
                "UPDATE subtitle_effective_final_selections SET selector = 'selector:evil'"
            ),
        )
        self.assertIn("EFFECTIVE_FINAL_SELECTION_FINGERPRINT_MISMATCH", self._codes(broken))

    def test_sequence_and_supersession_detected(self) -> None:
        broken = self._corrupt(
            "gap.db",
            lambda c: c.execute(
                "UPDATE subtitle_effective_final_selections SET sequence = 5, "
                "previous_selection_id = 'subtitle-effective-final-selection:ghost'"
            ),
        )
        self.assertIn("EFFECTIVE_FINAL_SELECTION_SEQUENCE_NONCONTIGUOUS", self._codes(broken))


class EffectiveSubtitleSrtArtifactValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        from lectureos.application.provider_transcript_admission import (
            build_provider_transcript_document,
        )
        from lectureos.composition import (
            compose_sqlite_current_raw_transcript_selection_service,
            compose_sqlite_effective_subtitle_final_selection_service,
            compose_sqlite_effective_subtitle_generation_service,
            compose_sqlite_effective_subtitle_review_decision_service,
            compose_sqlite_effective_subtitle_review_preparation_service,
            compose_sqlite_effective_subtitle_srt_artifact_service,
            compose_sqlite_media_import_service,
            compose_sqlite_provider_transcript_admission_service,
            compose_sqlite_transcript_source_intake_service,
        )

        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.healthy = self.base / "srt-artifact.db"
        connection = initialize_sqlite_database(self.healthy)
        source = self.base / "s.bin"
        source.write_bytes(b"srt-artifact-validation \x00\x01")
        media_id = compose_sqlite_media_import_service(connection).import_media(str(source)).record.identity.value
        intake = compose_sqlite_transcript_source_intake_service(connection).admit(media_id).intake.identity.value
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
        ).candidate.identity.value
        subject = compose_sqlite_effective_subtitle_review_preparation_service(connection).prepare_review(
            candidate_id=candidate
        ).subject.identity.value
        decisions = compose_sqlite_effective_subtitle_review_decision_service(connection)
        decisions.decide(review_subject_id=subject, kind="accept", reviewer="reviewer:kim")
        selection = compose_sqlite_effective_subtitle_final_selection_service(connection).select_final(
            review_subject_id=subject, selector="selector:park"
        ).selection.identity.value
        compose_sqlite_effective_subtitle_srt_artifact_service(connection).generate_srt_artifact(
            final_selection_id=selection
        )
        # Healthy staleness: the supporting Accept is later superseded — never corruption.
        decisions.decide(review_subject_id=subject, kind="reject", reviewer="reviewer:kim")
        connection.close()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _corrupt(self, name: str, mutate) -> Path:
        target = self.base / name
        shutil.copyfile(self.healthy, target)
        connection = sqlite3.connect(target)
        try:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute("BEGIN")
            mutate(connection)
            connection.execute("COMMIT")
        finally:
            connection.close()
        return target

    def _codes(self, database: Path) -> set[str]:
        return {d.code for d in validate_database(str(database)).diagnostics}

    def test_healthy_artifact_after_authority_change_is_clean(self) -> None:
        report = validate_database(str(self.healthy))
        self.assertTrue(report.ok)
        self.assertEqual(report.health, RepositoryHealth.HEALTHY)

    def test_dangling_selection_detected(self) -> None:
        broken = self._corrupt(
            "selection.db",
            lambda c: c.execute(
                "UPDATE subtitle_effective_srt_artifacts "
                "SET final_selection_id = 'subtitle-effective-final-selection:" + "0" * 64 + "'"
            ),
        )
        self.assertIn("EFFECTIVE_SRT_ARTIFACT_DANGLING_SELECTION", self._codes(broken))

    def test_unsupported_serializer_detected(self) -> None:
        broken = self._corrupt(
            "serializer.db",
            lambda c: c.execute(
                "UPDATE subtitle_effective_srt_artifacts SET serializer_version = 9"
            ),
        )
        self.assertIn("EFFECTIVE_SRT_ARTIFACT_UNSUPPORTED_SERIALIZER", self._codes(broken))

    def test_fingerprint_and_identity_mismatch_detected(self) -> None:
        broken = self._corrupt(
            "payload.db",
            lambda c: c.execute(
                "UPDATE subtitle_effective_srt_artifacts "
                "SET srt_content = '1' || char(10) || '00:00:00,000 --> 00:00:01,000' "
                "|| char(10) || 'tampered' || char(10)"
            ),
        )
        codes = self._codes(broken)
        self.assertIn("EFFECTIVE_SRT_ARTIFACT_FINGERPRINT_MISMATCH", codes)
        self.assertIn("EFFECTIVE_SRT_ARTIFACT_RESERIALIZATION_MISMATCH", codes)
        broken = self._corrupt(
            "identity.db",
            lambda c: c.execute(
                "UPDATE subtitle_effective_srt_artifacts "
                "SET identity = 'subtitle-effective-srt-artifact:" + "0" * 64 + "'"
            ),
        )
        self.assertIn("EFFECTIVE_SRT_ARTIFACT_IDENTITY_MISMATCH", self._codes(broken))

    def test_cue_count_mismatch_detected(self) -> None:
        broken = self._corrupt(
            "count.db",
            lambda c: c.execute(
                "UPDATE subtitle_effective_srt_artifacts SET cue_count = 5"
            ),
        )
        self.assertIn("EFFECTIVE_SRT_ARTIFACT_CUE_COUNT_MISMATCH", self._codes(broken))


class EffectiveSrtMaterializationValidationTests(unittest.TestCase):
    def setUp(self) -> None:
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

        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.healthy = self.base / "materialize.db"
        storage_root = self.base / "out"
        storage_root.mkdir()
        connection = initialize_sqlite_database(self.healthy)
        source = self.base / "s.bin"
        source.write_bytes(b"materialize-validation \x00\x01")
        media_id = compose_sqlite_media_import_service(connection).import_media(str(source)).record.identity.value
        intake = compose_sqlite_transcript_source_intake_service(connection).admit(media_id).intake.identity.value
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
        ).candidate.identity.value
        subject = compose_sqlite_effective_subtitle_review_preparation_service(connection).prepare_review(
            candidate_id=candidate
        ).subject.identity.value
        compose_sqlite_effective_subtitle_review_decision_service(connection).decide(
            review_subject_id=subject, kind="accept", reviewer="reviewer:kim"
        )
        selection = compose_sqlite_effective_subtitle_final_selection_service(connection).select_final(
            review_subject_id=subject, selector="selector:park"
        ).selection.identity.value
        artifact = compose_sqlite_effective_subtitle_srt_artifact_service(connection).generate_srt_artifact(
            final_selection_id=selection
        ).artifact.identity.value
        materializer = compose_sqlite_effective_srt_materialization_service(
            connection, str(storage_root)
        )
        record = materializer.materialize(artifact_id=artifact)
        connection.close()
        # A later-deleted physical file must never be corruption.
        (storage_root / record.materialization.relative_location).unlink()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _corrupt(self, name: str, mutate) -> Path:
        target = self.base / name
        shutil.copyfile(self.healthy, target)
        connection = sqlite3.connect(target)
        try:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute("BEGIN")
            mutate(connection)
            connection.execute("COMMIT")
        finally:
            connection.close()
        return target

    def _codes(self, database: Path) -> set[str]:
        return {d.code for d in validate_database(str(database)).diagnostics}

    def test_healthy_even_after_physical_file_deleted(self) -> None:
        report = validate_database(str(self.healthy))
        self.assertTrue(report.ok)
        self.assertEqual(report.health, RepositoryHealth.HEALTHY)

    def test_dangling_artifact_detected(self) -> None:
        broken = self._corrupt(
            "dangling.db",
            lambda c: c.execute(
                "UPDATE subtitle_effective_srt_materializations "
                "SET artifact_id = 'subtitle-effective-srt-artifact:" + "0" * 64 + "'"
            ),
        )
        self.assertIn(
            "EFFECTIVE_SRT_MATERIALIZATION_DANGLING_ARTIFACT", self._codes(broken)
        )

    def test_fingerprint_and_identity_mismatch_detected(self) -> None:
        broken = self._corrupt(
            "fingerprint.db",
            lambda c: c.execute(
                "UPDATE subtitle_effective_srt_materializations "
                "SET payload_fingerprint = ?",
                ("f" * 64,),
            ),
        )
        self.assertIn(
            "EFFECTIVE_SRT_MATERIALIZATION_FINGERPRINT_MISMATCH", self._codes(broken)
        )
        broken = self._corrupt(
            "identity.db",
            lambda c: c.execute(
                "UPDATE subtitle_effective_srt_materializations "
                "SET identity = 'subtitle-effective-srt-materialization:" + "0" * 64 + "'"
            ),
        )
        codes = self._codes(broken)
        self.assertIn("EFFECTIVE_SRT_MATERIALIZATION_IDENTITY_MISMATCH", codes)
        self.assertIn("EFFECTIVE_SRT_MATERIALIZATION_ORPHAN_OUTCOME", codes)

    def test_sequence_gap_detected(self) -> None:
        broken = self._corrupt(
            "gap.db",
            lambda c: c.execute(
                "UPDATE subtitle_effective_srt_materializations SET sequence = 5, "
                "previous_materialization_id = 'subtitle-effective-srt-materialization:ghost'"
            ),
        )
        codes = self._codes(broken)
        self.assertIn("EFFECTIVE_SRT_MATERIALIZATION_SEQUENCE_NONCONTIGUOUS", codes)
        self.assertIn("EFFECTIVE_SRT_MATERIALIZATION_BROKEN_SUPERSESSION", codes)


class EffectiveSrtDeliveryValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        from lectureos.application.provider_transcript_admission import (
            build_provider_transcript_document,
        )
        from lectureos.application.effective_srt_delivery import (
            EffectiveSrtDelivery,
            derive_delivery_identity,
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
        from lectureos.persistence import (
            SQLiteEffectiveSrtDeliveryCommandPersistence,
        )

        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.healthy = self.base / "deliver.db"
        storage_root = self.base / "storage"
        delivery_root = self.base / "delivered"
        storage_root.mkdir()
        delivery_root.mkdir()
        connection = initialize_sqlite_database(self.healthy)
        source = self.base / "s.bin"
        source.write_bytes(b"deliver-validation \x00\x01")
        media_id = compose_sqlite_media_import_service(connection).import_media(str(source)).record.identity.value
        intake = compose_sqlite_transcript_source_intake_service(connection).admit(media_id).intake.identity.value
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
        ).candidate.identity.value
        subject = compose_sqlite_effective_subtitle_review_preparation_service(connection).prepare_review(
            candidate_id=candidate
        ).subject.identity.value
        compose_sqlite_effective_subtitle_review_decision_service(connection).decide(
            review_subject_id=subject, kind="accept", reviewer="reviewer:kim"
        )
        selection = compose_sqlite_effective_subtitle_final_selection_service(connection).select_final(
            review_subject_id=subject, selector="selector:park"
        ).selection.identity.value
        artifact = compose_sqlite_effective_subtitle_srt_artifact_service(connection).generate_srt_artifact(
            final_selection_id=selection
        ).artifact
        materialization = compose_sqlite_effective_srt_materialization_service(
            connection, str(storage_root)
        ).materialize(artifact_id=artifact.identity.value).materialization
        deliverer = compose_sqlite_effective_srt_delivery_service(
            connection, str(storage_root), str(delivery_root)
        )
        delivered = deliverer.deliver(materialization_id=materialization.identity.value)
        # Honest FAILED history: an existing different destination without overwrite.
        (delivery_root / "other.srt").write_bytes(b"foreign\n")
        deliverer.deliver(
            materialization_id=materialization.identity.value,
            relative_location="other.srt",
        )
        # An honest dangling PENDING intent (as after a crash between intent and write).
        pending = EffectiveSrtDelivery(
            identity=derive_delivery_identity(
                materialization.identity, artifact.identity, "pending.srt",
                artifact.content_fingerprint, 0, False,
            ),
            materialization_id=materialization.identity,
            artifact_id=artifact.identity,
            delivery_kind="local_copy",
            delivery_contract_version=1,
            relative_location="pending.srt",
            expected_payload_fingerprint=artifact.content_fingerprint,
            sequence=0,
            overwrite=False,
        )
        SQLiteEffectiveSrtDeliveryCommandPersistence(connection).persist_delivery_intent(
            delivery=pending
        )
        connection.close()
        # A later-deleted destination file must never be corruption.
        (delivery_root / delivered.delivery.relative_location).unlink()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _corrupt(self, name: str, mutate) -> Path:
        target = self.base / name
        shutil.copyfile(self.healthy, target)
        connection = sqlite3.connect(target)
        try:
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute("BEGIN")
            mutate(connection)
            connection.execute("COMMIT")
        finally:
            connection.close()
        return target

    def _codes(self, database: Path) -> set[str]:
        return {d.code for d in validate_database(str(database)).diagnostics}

    def test_healthy_with_pending_failed_and_deleted_destination(self) -> None:
        report = validate_database(str(self.healthy))
        self.assertTrue(report.ok)
        self.assertEqual(report.health, RepositoryHealth.HEALTHY)

    def test_dangling_materialization_detected(self) -> None:
        broken = self._corrupt(
            "dangling.db",
            lambda c: c.execute(
                "UPDATE subtitle_effective_srt_delivery_intents "
                "SET materialization_id = "
                "'subtitle-effective-srt-materialization:" + "0" * 64 + "'"
            ),
        )
        self.assertIn(
            "EFFECTIVE_SRT_DELIVERY_DANGLING_MATERIALIZATION", self._codes(broken)
        )

    def test_artifact_lineage_mismatch_detected(self) -> None:
        broken = self._corrupt(
            "lineage.db",
            lambda c: c.execute(
                "UPDATE subtitle_effective_srt_delivery_intents "
                "SET artifact_id = 'subtitle-effective-srt-artifact:" + "0" * 64 + "'"
            ),
        )
        self.assertIn(
            "EFFECTIVE_SRT_DELIVERY_ARTIFACT_LINEAGE_MISMATCH", self._codes(broken)
        )

    def test_fingerprint_and_identity_mismatch_detected(self) -> None:
        broken = self._corrupt(
            "fingerprint.db",
            lambda c: c.execute(
                "UPDATE subtitle_effective_srt_delivery_intents "
                "SET expected_payload_fingerprint = ?",
                ("f" * 64,),
            ),
        )
        codes = self._codes(broken)
        self.assertIn("EFFECTIVE_SRT_DELIVERY_FINGERPRINT_MISMATCH", codes)
        self.assertIn("EFFECTIVE_SRT_DELIVERY_IDENTITY_MISMATCH", codes)
        broken = self._corrupt(
            "identity.db",
            lambda c: c.execute(
                "UPDATE subtitle_effective_srt_delivery_intents "
                "SET identity = 'subtitle-effective-srt-delivery:" + "0" * 64 + "' "
                "WHERE sequence = 0 AND relative_location <> 'pending.srt' "
                "AND relative_location <> 'other.srt'"
            ),
        )
        codes = self._codes(broken)
        self.assertIn("EFFECTIVE_SRT_DELIVERY_IDENTITY_MISMATCH", codes)
        self.assertIn("EFFECTIVE_SRT_DELIVERY_ORPHAN_OUTCOME", codes)

    def test_unsafe_location_detected(self) -> None:
        broken = self._corrupt(
            "unsafe.db",
            lambda c: c.execute(
                "UPDATE subtitle_effective_srt_delivery_intents "
                "SET relative_location = '../escape.srt' "
                "WHERE relative_location = 'pending.srt'"
            ),
        )
        self.assertIn("EFFECTIVE_SRT_DELIVERY_UNSAFE_LOCATION", self._codes(broken))

    def test_sequence_gap_and_broken_supersession_detected(self) -> None:
        broken = self._corrupt(
            "gap.db",
            lambda c: c.execute(
                "UPDATE subtitle_effective_srt_delivery_intents SET sequence = 5, "
                "previous_delivery_id = 'subtitle-effective-srt-delivery:ghost' "
                "WHERE relative_location = 'pending.srt'"
            ),
        )
        codes = self._codes(broken)
        self.assertIn("EFFECTIVE_SRT_DELIVERY_SEQUENCE_NONCONTIGUOUS", codes)
        self.assertIn("EFFECTIVE_SRT_DELIVERY_BROKEN_SUPERSESSION", codes)

    def test_outcome_integrity_detected(self) -> None:
        broken = self._corrupt(
            "category.db",
            lambda c: c.execute(
                "UPDATE subtitle_effective_srt_delivery_outcomes "
                "SET failure_category = 'exotic_failure' WHERE state = 'failed'"
            ),
        )
        self.assertIn(
            "EFFECTIVE_SRT_DELIVERY_UNSUPPORTED_FAILURE_CATEGORY", self._codes(broken)
        )
        broken = self._corrupt(
            "delivered-fp.db",
            lambda c: c.execute(
                "UPDATE subtitle_effective_srt_delivery_outcomes "
                "SET delivered_payload_fingerprint = ? WHERE state = 'delivered'",
                ("e" * 64,),
            ),
        )
        self.assertIn(
            "EFFECTIVE_SRT_DELIVERY_DELIVERED_FINGERPRINT_MISMATCH",
            self._codes(broken),
        )


if __name__ == "__main__":
    unittest.main()
