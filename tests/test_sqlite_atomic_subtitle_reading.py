import tempfile
import unittest
from pathlib import Path

from lectureos.application import SubtitleReadingIdentityPlan
from lectureos.application.identities import (
    SubtitleCandidateId,
    SubtitleReadingRevisionId,
    SubtitleReadingUnitId,
)
from lectureos.composition import (
    compose_sqlite_subtitle_reading_representation_service,
)
from lectureos.execution.identities import DomainResultId
from lectureos.persistence import (
    PersistenceIdentityCollisionError,
    SQLiteDomainResultReferenceRepository,
    SQLiteSubtitleCandidateRepository,
    SQLiteSubtitleReadingCommandPersistence,
    SQLiteSubtitleReadingRevisionRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)

try:  # importable both under discovery and as tests.<module>
    from tests.test_sqlite_atomic_subtitle_candidate import (
        _build_persisted_intake,
        _record_candidate,
    )
except ImportError:  # pragma: no cover - invocation-style fallback
    from test_sqlite_atomic_subtitle_candidate import (
        _build_persisted_intake,
        _record_candidate,
    )

_CANDIDATE_ID = SubtitleCandidateId("cand-0")


def _reading_plan(name="reading-0") -> SubtitleReadingIdentityPlan:
    return SubtitleReadingIdentityPlan(
        reading_revision_id=SubtitleReadingRevisionId(name),
        reading_result_id=DomainResultId(f"{name}-result"),
        unit_ids=(
            SubtitleReadingUnitId(f"{name}-unit-0"),
            SubtitleReadingUnitId(f"{name}-unit-1"),
        ),
    )


def _record_reading(connection, execution, run_id, execution_id, name="reading-0"):
    service = compose_sqlite_subtitle_reading_representation_service(connection, execution)
    return service.record_reading(
        source_candidate_id=_CANDIDATE_ID,
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=_reading_plan(name),
    )


def _build_persisted_candidate(connection):
    execution, run_id, execution_id = _build_persisted_intake(connection)
    _record_candidate(connection, execution, run_id, execution_id)
    return execution, run_id, execution_id


class SQLiteAtomicSubtitleReadingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "lectureos.sqlite3"
        self.connection = initialize_sqlite_database(self.database_path)
        self.execution, self.run_id, self.execution_id = _build_persisted_candidate(
            self.connection
        )

    def tearDown(self) -> None:
        try:
            self.connection.close()
        except Exception:
            pass
        self.temporary_directory.cleanup()

    def test_persists_and_reconstructs_revision_and_ordered_units(self) -> None:
        prepared = _record_reading(
            self.connection, self.execution, self.run_id, self.execution_id
        )
        self.assertEqual(len(prepared.units), 2)
        self.connection.close()

        reopened = open_sqlite_database(self.database_path)
        try:
            repo = SQLiteSubtitleReadingRevisionRepository(reopened)
            revision = repo.get(prepared.revision.identity)
            self.assertEqual(revision, prepared.revision)
            self.assertEqual(revision.unit_ids, prepared.revision.unit_ids)
            for unit in prepared.units:
                self.assertEqual(repo.get_unit(unit.identity), unit)
            result = SQLiteDomainResultReferenceRepository(reopened).get(
                prepared.revision_result.identity
            )
            self.assertEqual(result, prepared.revision_result)
        finally:
            reopened.close()

    def test_deterministic_replay_into_fresh_database(self) -> None:
        first = _record_reading(
            self.connection, self.execution, self.run_id, self.execution_id
        )
        self.connection.close()

        replay_path = Path(self.temporary_directory.name) / "replay.sqlite3"
        replay_connection = initialize_sqlite_database(replay_path)
        try:
            execution, run_id, execution_id = _build_persisted_candidate(replay_connection)
            second = _record_reading(replay_connection, execution, run_id, execution_id)
            self.assertEqual(first.revision, second.revision)
            self.assertEqual(first.units, second.units)
            self.assertEqual(first.revision_result, second.revision_result)
            replayed = SQLiteSubtitleReadingRevisionRepository(replay_connection).get(
                first.revision.identity
            )
            self.assertEqual(replayed, first.revision)
        finally:
            replay_connection.close()

    def test_repeated_composition_does_not_mutate_upstream_candidate(self) -> None:
        candidate_repo = SQLiteSubtitleCandidateRepository(self.connection)
        before = candidate_repo.get(_CANDIDATE_ID)
        _record_reading(self.connection, self.execution, self.run_id, self.execution_id, "r-a")
        _record_reading(self.connection, self.execution, self.run_id, self.execution_id, "r-b")
        after = candidate_repo.get(_CANDIDATE_ID)
        self.assertEqual(before, after)
        count = self.connection.execute(
            "SELECT COUNT(*) FROM subtitle_reading_revisions"
        ).fetchone()[0]
        self.assertEqual(count, 2)

    def test_repeated_persist_is_rejected_and_atomic(self) -> None:
        prepared = _record_reading(
            self.connection, self.execution, self.run_id, self.execution_id
        )
        persistence = SQLiteSubtitleReadingCommandPersistence(self.connection)
        with self.assertRaises(PersistenceIdentityCollisionError):
            persistence.persist_subtitle_reading(
                revision=prepared.revision,
                units=prepared.units,
                revision_result=prepared.revision_result,
            )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM subtitle_reading_revisions"
            ).fetchone()[0],
            1,
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM subtitle_reading_units"
            ).fetchone()[0],
            2,
        )

    def test_result_collision_rolls_back_revision_units_and_children(self) -> None:
        service = compose_sqlite_subtitle_reading_representation_service(
            self.connection, self.execution
        )
        prepared = service.compose_reading(
            source_candidate_id=_CANDIDATE_ID,
            run_id=self.run_id,
            unit_execution_id=self.execution_id,
            identities=SubtitleReadingIdentityPlan(
                reading_revision_id=SubtitleReadingRevisionId("reading-x"),
                # Reuse an existing DomainResult identity to force a collision.
                reading_result_id=DomainResultId("cand-0-result"),
                unit_ids=(
                    SubtitleReadingUnitId("reading-x-unit-0"),
                    SubtitleReadingUnitId("reading-x-unit-1"),
                ),
            ),
        )
        persistence = SQLiteSubtitleReadingCommandPersistence(self.connection)
        with self.assertRaises(PersistenceIdentityCollisionError):
            persistence.persist_subtitle_reading(
                revision=prepared.revision,
                units=prepared.units,
                revision_result=prepared.revision_result,
            )
        for table in (
            "subtitle_reading_revisions",
            "subtitle_reading_units",
            "subtitle_reading_unit_source_cues",
            "subtitle_reading_unit_lines",
        ):
            self.assertEqual(
                self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0],
                0,
                table,
            )


if __name__ == "__main__":
    unittest.main()
