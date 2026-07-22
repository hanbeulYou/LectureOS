import tempfile
import unittest
from pathlib import Path

from lectureos.application import SubtitleTimeIdentityPlan, SubtitleTimingStatus
from lectureos.application.identities import (
    SubtitleReadingRevisionId,
    SubtitleTimedUnitId,
    SubtitleTimeRevisionId,
)
from lectureos.composition import (
    compose_sqlite_subtitle_time_representation_service,
)
from lectureos.execution.identities import DomainResultId
from lectureos.persistence import (
    PersistenceIdentityCollisionError,
    SQLiteDomainResultReferenceRepository,
    SQLiteSubtitleReadingRevisionRepository,
    SQLiteSubtitleTimeCommandPersistence,
    SQLiteSubtitleTimeRevisionRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)

try:  # importable both under discovery and as tests.<module>
    from tests.test_sqlite_atomic_subtitle_reading import (
        _build_persisted_candidate,
        _record_reading,
    )
except ImportError:  # pragma: no cover - invocation-style fallback
    from test_sqlite_atomic_subtitle_reading import (
        _build_persisted_candidate,
        _record_reading,
    )

_READING_ID = SubtitleReadingRevisionId("reading-0")


def _time_plan(name="time-0") -> SubtitleTimeIdentityPlan:
    return SubtitleTimeIdentityPlan(
        time_revision_id=SubtitleTimeRevisionId(name),
        time_result_id=DomainResultId(f"{name}-result"),
        timed_unit_ids=(
            SubtitleTimedUnitId(f"{name}-unit-0"),
            SubtitleTimedUnitId(f"{name}-unit-1"),
        ),
    )


def _record_timing(connection, execution, run_id, execution_id, name="time-0"):
    service = compose_sqlite_subtitle_time_representation_service(connection, execution)
    return service.record_timing(
        source_reading_revision_id=_READING_ID,
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=_time_plan(name),
    )


def _build_persisted_reading(connection):
    execution, run_id, execution_id = _build_persisted_candidate(connection)
    _record_reading(connection, execution, run_id, execution_id)
    return execution, run_id, execution_id


class SQLiteAtomicSubtitleTimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database_path)
        self.execution, self.run_id, self.execution_id = _build_persisted_reading(
            self.connection
        )

    def tearDown(self) -> None:
        try:
            self.connection.close()
        except Exception:
            pass
        self.temporary_directory.cleanup()

    def test_persists_and_reconstructs_revision_and_ordered_units(self) -> None:
        prepared = _record_timing(
            self.connection, self.execution, self.run_id, self.execution_id
        )
        self.assertEqual(len(prepared.units), 2)
        # the pipeline cues are timed, so the baseline anchors them
        self.assertTrue(
            all(u.timing_status is SubtitleTimingStatus.ANCHORED for u in prepared.units)
        )
        self.connection.close()

        reopened = open_sqlite_database(self.database_path)
        try:
            repo = SQLiteSubtitleTimeRevisionRepository(reopened)
            revision = repo.get(prepared.revision.identity)
            self.assertEqual(revision, prepared.revision)
            self.assertEqual(revision.timed_unit_ids, prepared.revision.timed_unit_ids)
            for unit in prepared.units:
                self.assertEqual(repo.get_unit(unit.identity), unit)
            result = SQLiteDomainResultReferenceRepository(reopened).get(
                prepared.revision_result.identity
            )
            self.assertEqual(result, prepared.revision_result)
        finally:
            reopened.close()

    def test_deterministic_replay_into_fresh_database(self) -> None:
        first = _record_timing(
            self.connection, self.execution, self.run_id, self.execution_id
        )
        self.connection.close()

        replay_path = Path(self.temporary_directory.name) / "replay.sqlite3"
        replay_connection = initialize_sqlite_database(replay_path)
        try:
            execution, run_id, execution_id = _build_persisted_reading(replay_connection)
            second = _record_timing(replay_connection, execution, run_id, execution_id)
            self.assertEqual(first.revision, second.revision)
            self.assertEqual(first.units, second.units)
            self.assertEqual(first.revision_result, second.revision_result)
            replayed = SQLiteSubtitleTimeRevisionRepository(replay_connection).get(
                first.revision.identity
            )
            self.assertEqual(replayed, first.revision)
        finally:
            replay_connection.close()

    def test_repeated_composition_does_not_mutate_upstream_reading(self) -> None:
        reading_repo = SQLiteSubtitleReadingRevisionRepository(self.connection)
        before = reading_repo.get(_READING_ID)
        _record_timing(self.connection, self.execution, self.run_id, self.execution_id, "t-a")
        _record_timing(self.connection, self.execution, self.run_id, self.execution_id, "t-b")
        after = reading_repo.get(_READING_ID)
        self.assertEqual(before, after)
        count = self.connection.execute(
            "SELECT COUNT(*) FROM subtitle_time_revisions"
        ).fetchone()[0]
        self.assertEqual(count, 2)

    def test_repeated_persist_is_rejected_and_atomic(self) -> None:
        prepared = _record_timing(
            self.connection, self.execution, self.run_id, self.execution_id
        )
        persistence = SQLiteSubtitleTimeCommandPersistence(self.connection)
        with self.assertRaises(PersistenceIdentityCollisionError):
            persistence.persist_subtitle_timing(
                revision=prepared.revision,
                units=prepared.units,
                revision_result=prepared.revision_result,
            )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM subtitle_time_revisions"
            ).fetchone()[0],
            1,
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM subtitle_timed_units"
            ).fetchone()[0],
            2,
        )

    def test_result_collision_rolls_back_revision_and_units(self) -> None:
        service = compose_sqlite_subtitle_time_representation_service(
            self.connection, self.execution
        )
        prepared = service.compose_timing(
            source_reading_revision_id=_READING_ID,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=SubtitleTimeIdentityPlan(
                time_revision_id=SubtitleTimeRevisionId("time-x"),
                # Reuse an existing DomainResult identity to force a collision.
                time_result_id=DomainResultId("reading-0-result"),
                timed_unit_ids=(
                    SubtitleTimedUnitId("time-x-unit-0"),
                    SubtitleTimedUnitId("time-x-unit-1"),
                ),
            ),
        )
        persistence = SQLiteSubtitleTimeCommandPersistence(self.connection)
        with self.assertRaises(PersistenceIdentityCollisionError):
            persistence.persist_subtitle_timing(
                revision=prepared.revision,
                units=prepared.units,
                revision_result=prepared.revision_result,
            )
        for table in ("subtitle_time_revisions", "subtitle_timed_units"):
            self.assertEqual(
                self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0],
                0,
                table,
            )


if __name__ == "__main__":
    unittest.main()
