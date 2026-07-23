import sqlite3
import tempfile
import unittest
from pathlib import Path

from lectureos.application import (
    LectureAnalysisInputIdentityPlan,
    LectureSegmentIdentityPlan,
    NormalizedLectureSegment,
    NormalizedSegmentationResult,
)
from lectureos.application.identities import (
    EligibleAnalysisInputId,
    LectureSegmentId,
    TranscriptReadinessEvaluationId,
)
from lectureos.composition import (
    compose_sqlite_lecture_analysis_input_service,
    compose_sqlite_lecture_segmentation_service,
)
from lectureos.execution.identities import DomainResultId, SourceTimelineId
from lectureos.persistence import (
    PersistenceIdentityCollisionError,
    SQLiteDomainResultReferenceRepository,
    SQLiteEligibleAnalysisInputRepository,
    SQLiteLectureSegmentCommandPersistence,
    SQLiteLectureSegmentRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence.errors import SchemaFeatureUnavailableError
from lectureos.subtitle_intake_acceptance import TIMELINE_ID, _build_persisted_readiness

_READY = TranscriptReadinessEvaluationId("rdy-int-accept")
_INPUT = EligibleAnalysisInputId("segmentation-input")


def _result(*segments):
    return NormalizedSegmentationResult(
        source_timeline_id=SourceTimelineId(TIMELINE_ID), segments=segments
    )


def _segment(start=0.0, end=5.0):
    return NormalizedLectureSegment(range_start=start, range_end=end)


def _segment_plans(*names):
    return tuple(
        LectureSegmentIdentityPlan(
            segment_id=LectureSegmentId(name),
            segment_result_id=DomainResultId(f"{name}-result"),
        )
        for name in names
    )


class SQLiteAtomicLectureSegmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database_path)
        (
            self.execution,
            self.run_id,
            self.execution_id,
            _revision,
            _raw,
        ) = _build_persisted_readiness(self.connection)
        input_service = compose_sqlite_lecture_analysis_input_service(
            self.connection, self.execution
        )
        input_service.record_input(
            source_readiness_id=_READY,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=LectureAnalysisInputIdentityPlan(
                input_id=_INPUT,
                input_result_id=DomainResultId("segmentation-input-result"),
            ),
        )

    def tearDown(self) -> None:
        try:
            self.connection.close()
        except Exception:
            pass
        self.temporary_directory.cleanup()

    def _record(self, result, plans):
        service = compose_sqlite_lecture_segmentation_service(
            self.connection, self.execution
        )
        return service.record_segments(
            source_input_id=_INPUT,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            result=result,
            identities=plans,
        )

    def test_persists_and_reconstructs_segments(self) -> None:
        prepared = self._record(
            _result(_segment(0.0, 10.0), _segment(10.0, 20.0)),
            _segment_plans("segment-0", "segment-1"),
        )
        self.connection.close()
        reopened = open_sqlite_database(self.database_path)
        try:
            repo = SQLiteLectureSegmentRepository(reopened)
            results = SQLiteDomainResultReferenceRepository(reopened)
            for item in prepared.segments:
                self.assertEqual(repo.get(item.segment.identity), item.segment)
                self.assertEqual(
                    results.get(item.segment_result.identity), item.segment_result
                )
        finally:
            reopened.close()

    def test_deterministic_replay_into_fresh_database(self) -> None:
        first = self._record(_result(_segment()), _segment_plans("segment-0"))
        self.connection.close()
        replay_path = Path(self.temporary_directory.name) / "replay.sqlite3"
        replay_connection = initialize_sqlite_database(replay_path)
        try:
            execution, run_id, execution_id, _, _ = _build_persisted_readiness(
                replay_connection
            )
            input_service = compose_sqlite_lecture_analysis_input_service(
                replay_connection, execution
            )
            input_service.record_input(
                source_readiness_id=_READY,
                run_id=run_id,
                unit_execution_id=execution_id,
                identities=LectureAnalysisInputIdentityPlan(
                    input_id=_INPUT,
                    input_result_id=DomainResultId("segmentation-input-result"),
                ),
            )
            service = compose_sqlite_lecture_segmentation_service(
                replay_connection, execution
            )
            second = service.record_segments(
                source_input_id=_INPUT,
                run_id=run_id,
                unit_execution_id=execution_id,
                result=_result(_segment()),
                identities=_segment_plans("segment-0"),
            )
            self.assertEqual(first.segments[0].segment, second.segments[0].segment)
            self.assertEqual(
                first.segments[0].segment_result, second.segments[0].segment_result
            )
        finally:
            replay_connection.close()

    def test_recording_does_not_mutate_upstream_input(self) -> None:
        input_repo = SQLiteEligibleAnalysisInputRepository(self.connection)
        before = input_repo.get(_INPUT)
        self._record(_result(_segment()), _segment_plans("segment-0"))
        self.assertEqual(input_repo.get(_INPUT), before)

    def test_identity_collision_rolls_back_all_segments(self) -> None:
        self._record(_result(_segment()), _segment_plans("segment-0"))
        service = compose_sqlite_lecture_segmentation_service(
            self.connection, self.execution
        )
        # first segment fresh, second collides -> neither must persist
        prepared = service.evaluate_segments(
            source_input_id=_INPUT,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            result=_result(_segment(0.0, 1.0), _segment(1.0, 2.0)),
            identities=_segment_plans("segment-1", "segment-0"),
        )
        persistence = SQLiteLectureSegmentCommandPersistence(self.connection)
        with self.assertRaises(PersistenceIdentityCollisionError):
            persistence.persist_lecture_segments(prepared=prepared.segments)
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM lecture_segments WHERE identity = 'segment-1'"
            ).fetchone()[0],
            0,
        )

    def test_result_collision_rolls_back_segment(self) -> None:
        service = compose_sqlite_lecture_segmentation_service(
            self.connection, self.execution
        )
        prepared = service.evaluate_segments(
            source_input_id=_INPUT,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            result=_result(_segment()),
            identities=(
                LectureSegmentIdentityPlan(
                    segment_id=LectureSegmentId("segment-x"),
                    # reuse the eligible input's DomainResult id to force a collision
                    segment_result_id=DomainResultId("segmentation-input-result"),
                ),
            ),
        )
        persistence = SQLiteLectureSegmentCommandPersistence(self.connection)
        with self.assertRaises(PersistenceIdentityCollisionError):
            persistence.persist_lecture_segments(prepared=prepared.segments)
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM lecture_segments WHERE identity = 'segment-x'"
            ).fetchone()[0],
            0,
        )

    def test_repository_rejects_pre_v25_schema(self) -> None:
        legacy_path = Path(self.temporary_directory.name) / "legacy.sqlite3"
        from lectureos.persistence import sqlite as sqlite_lifecycle

        connection = sqlite3.connect(legacy_path, isolation_level=None)
        connection.execute("PRAGMA foreign_keys = ON")
        statements = [*sqlite_lifecycle._V1_TABLE_STATEMENTS]
        for level in range(2, 25):
            statements += getattr(sqlite_lifecycle, f"_V{level}_ADDITION_STATEMENTS")
        connection.execute("BEGIN")
        for statement in statements:
            connection.execute(statement)
        connection.execute("INSERT INTO schema_metadata VALUES (1, 24)")
        connection.execute("COMMIT")
        connection.close()
        reopened = open_sqlite_database(legacy_path)
        try:
            with self.assertRaises(SchemaFeatureUnavailableError):
                SQLiteLectureSegmentRepository(reopened)
        finally:
            reopened.close()


if __name__ == "__main__":
    unittest.main()
