"""Insert-only SQLite persistence for Effective-Source Subtitle Review Subjects (GOAL-014).

Serializes one immutable review-preparation record per (candidate, preparation contract) in a
single atomic transaction. Subjects are never updated or deleted: currentness is derived at query
time, staleness is history, and no reviewer, decision, status, or workflow column exists. Any
collision or error rolls back with no partial state; the bound candidate graph and every legacy
review table are never touched.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from lectureos.application.identities import (
    EffectiveSubtitleCandidateId,
    EffectiveSubtitleReviewSubjectId,
)

from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection

if TYPE_CHECKING:
    from lectureos.application.effective_subtitle_review_preparation import (
        EffectiveSubtitleReviewSubject,
    )

_REQUIRED_VERSION = 40


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(
            "Effective Subtitle Review Subject persistence requires SQLite schema version 40"
        )
    return version


class SQLiteEffectiveSubtitleReviewSubjectRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(
        self, identity: EffectiveSubtitleReviewSubjectId
    ) -> "EffectiveSubtitleReviewSubject | None":
        try:
            row = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE identity = ?", (identity.value,)
            ).fetchone()
            return None if row is None else _restore(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Effective Subtitle Review Subject: {error}"
            ) from error

    def get_for_candidate(
        self, candidate_id: EffectiveSubtitleCandidateId
    ) -> "EffectiveSubtitleReviewSubject | None":
        try:
            row = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE candidate_id = ? "
                "ORDER BY preparation_kind, preparation_version LIMIT 1",
                (candidate_id.value,),
            ).fetchone()
            return None if row is None else _restore(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Effective Subtitle Review Subject: {error}"
            ) from error


class SQLiteEffectiveSubtitleReviewSubjectCommandPersistence:
    """Owns one atomic v40 transaction inserting a review subject."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_review_subject(
        self, *, subject: "EffectiveSubtitleReviewSubject"
    ) -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(
                "Effective Subtitle Review Subject persistence requires SQLite schema version 40"
            )
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            if self._exists(subject.identity.value):
                raise PersistenceIdentityCollisionError(
                    "Effective Subtitle Review Subject identity already exists"
                )
            self._connection.execute(
                """
                INSERT INTO subtitle_effective_review_subjects(
                    identity, candidate_id, candidate_graph_fingerprint,
                    preparation_kind, preparation_version, preparation_key
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    subject.identity.value,
                    subject.candidate_id.value,
                    subject.candidate_graph_fingerprint,
                    subject.preparation_kind,
                    subject.preparation_version,
                    subject.preparation_key,
                ),
            )
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.IntegrityError as error:
            self._rollback(transaction_started)
            raise PersistenceIdentityCollisionError(
                f"Effective Subtitle Review Subject already exists: {error}"
            ) from error
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Effective Subtitle Review Subject: {error}"
            ) from error
        except Exception:
            self._rollback(transaction_started)
            raise

    def _exists(self, identity: str) -> bool:
        return (
            self._connection.execute(
                "SELECT 1 FROM subtitle_effective_review_subjects WHERE identity = ?",
                (identity,),
            ).fetchone()
            is not None
        )

    def _rollback(self, transaction_started: bool) -> None:
        if transaction_started and self._connection.in_transaction:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass


_SELECT_COLUMNS = (
    "SELECT identity, candidate_id, candidate_graph_fingerprint, "
    "preparation_kind, preparation_version, preparation_key "
    "FROM subtitle_effective_review_subjects"
)


def _restore(row: tuple[object, ...]) -> "EffectiveSubtitleReviewSubject":
    from lectureos.application.effective_subtitle_review_preparation import (
        EffectiveSubtitleReviewSubject,
    )

    return EffectiveSubtitleReviewSubject(
        identity=EffectiveSubtitleReviewSubjectId(row[0]),
        candidate_id=EffectiveSubtitleCandidateId(row[1]),
        candidate_graph_fingerprint=row[2],
        preparation_kind=row[3],
        preparation_version=row[4],
        preparation_key=row[5],
    )


__all__ = [
    "SQLiteEffectiveSubtitleReviewSubjectCommandPersistence",
    "SQLiteEffectiveSubtitleReviewSubjectRepository",
]
