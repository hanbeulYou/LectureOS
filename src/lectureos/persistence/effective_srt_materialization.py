"""Insert-only SQLite persistence for Effective SRT Materializations (GOAL-018).

Serializes the record-first materialization lifecycle: the immutable intent row is durable before
any file write (one atomic transaction), and the immutable terminal outcome row is durable after
(a second atomic transaction) — a crash between them leaves an honest PENDING state, derived, not
stored. Neither row is ever updated or deleted; the physical filesystem is never touched here.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from lectureos.application.identities import (
    EffectiveSrtMaterializationId,
    EffectiveSubtitleSrtArtifactId,
)

from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection

if TYPE_CHECKING:
    from lectureos.application.effective_srt_materialization import (
        EffectiveSrtMaterialization,
        EffectiveSrtMaterializationOutcome,
    )

_REQUIRED_VERSION = 44


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(
            "Effective SRT Materialization persistence requires SQLite schema version 44"
        )
    return version


class SQLiteEffectiveSrtMaterializationRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(
        self, identity: EffectiveSrtMaterializationId
    ) -> "EffectiveSrtMaterialization | None":
        try:
            row = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE identity = ?", (identity.value,)
            ).fetchone()
            return None if row is None else _restore(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Effective SRT Materialization: {error}"
            ) from error

    def get_outcome(
        self, identity: EffectiveSrtMaterializationId
    ) -> "EffectiveSrtMaterializationOutcome | None":
        try:
            row = self._connection.execute(
                "SELECT materialization_id, state, byte_length, failure_reason "
                "FROM subtitle_effective_srt_materialization_outcomes "
                "WHERE materialization_id = ?",
                (identity.value,),
            ).fetchone()
            return None if row is None else _restore_outcome(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Effective SRT Materialization outcome: {error}"
            ) from error

    def get_latest(
        self,
        artifact_id: EffectiveSubtitleSrtArtifactId,
        relative_location: str,
    ) -> "EffectiveSrtMaterialization | None":
        try:
            row = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE artifact_id = ? AND relative_location = ? "
                "ORDER BY sequence DESC LIMIT 1",
                (artifact_id.value, relative_location),
            ).fetchone()
            return None if row is None else _restore(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read latest Effective SRT Materialization: {error}"
            ) from error

    def list_for_artifact(
        self, artifact_id: EffectiveSubtitleSrtArtifactId
    ) -> "tuple[EffectiveSrtMaterialization, ...]":
        try:
            rows = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE artifact_id = ? "
                "ORDER BY relative_location, sequence",
                (artifact_id.value,),
            ).fetchall()
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not list Effective SRT Materializations: {error}"
            ) from error
        return tuple(_restore(row) for row in rows)


class SQLiteEffectiveSrtMaterializationCommandPersistence:
    """Owns the two atomic v44 transactions of the record-first lifecycle."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_materialization_intent(
        self, *, materialization: "EffectiveSrtMaterialization"
    ) -> None:
        self._require()
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            exists = self._connection.execute(
                "SELECT 1 FROM subtitle_effective_srt_materializations WHERE identity = ?",
                (materialization.identity.value,),
            ).fetchone()
            if exists is not None:
                raise PersistenceIdentityCollisionError(
                    "Effective SRT Materialization identity already exists"
                )
            self._require_valid_supersession(materialization)
            self._connection.execute(
                """
                INSERT INTO subtitle_effective_srt_materializations(
                    identity, artifact_id, storage_kind, relative_location,
                    payload_fingerprint, sequence, previous_materialization_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    materialization.identity.value,
                    materialization.artifact_id.value,
                    materialization.storage_kind,
                    materialization.relative_location,
                    materialization.payload_fingerprint,
                    materialization.sequence,
                    materialization.previous_materialization_id.value
                    if materialization.previous_materialization_id
                    else None,
                ),
            )
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.IntegrityError as error:
            self._rollback(transaction_started)
            raise PersistenceIdentityCollisionError(
                f"Effective SRT Materialization already exists: {error}"
            ) from error
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Effective SRT Materialization: {error}"
            ) from error
        except Exception:
            self._rollback(transaction_started)
            raise

    def persist_materialization_outcome(
        self, *, outcome: "EffectiveSrtMaterializationOutcome"
    ) -> None:
        self._require()
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            self._connection.execute(
                """
                INSERT INTO subtitle_effective_srt_materialization_outcomes(
                    materialization_id, state, byte_length, failure_reason
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    outcome.materialization_id.value,
                    outcome.state.value,
                    outcome.byte_length,
                    outcome.failure_reason,
                ),
            )
            self._connection.execute("COMMIT")
        except sqlite3.IntegrityError as error:
            self._rollback(transaction_started)
            raise PersistenceIdentityCollisionError(
                f"Effective SRT Materialization outcome already exists: {error}"
            ) from error
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Effective SRT Materialization outcome: {error}"
            ) from error
        except Exception:
            self._rollback(transaction_started)
            raise

    def _require(self) -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(
                "Effective SRT Materialization persistence requires SQLite schema version 44"
            )

    def _require_valid_supersession(
        self, materialization: "EffectiveSrtMaterialization"
    ) -> None:
        if materialization.previous_materialization_id is None:
            return
        row = self._connection.execute(
            """
            SELECT artifact_id, relative_location, sequence
            FROM subtitle_effective_srt_materializations
            WHERE identity = ?
            """,
            (materialization.previous_materialization_id.value,),
        ).fetchone()
        if row is None:
            raise PersistenceError(
                "materialization supersedes an unknown previous materialization"
            )
        if (
            row[0] != materialization.artifact_id.value
            or row[1] != materialization.relative_location
        ):
            raise PersistenceError(
                "materialization supersession must stay within one (artifact, location) pair"
            )
        if row[2] != materialization.sequence - 1:
            raise PersistenceError(
                "materialization supersession must increment the sequence by one"
            )

    def _rollback(self, transaction_started: bool) -> None:
        if transaction_started and self._connection.in_transaction:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass


_SELECT_COLUMNS = (
    "SELECT identity, artifact_id, storage_kind, relative_location, payload_fingerprint, "
    "sequence, previous_materialization_id "
    "FROM subtitle_effective_srt_materializations"
)


def _restore(row: tuple[object, ...]) -> "EffectiveSrtMaterialization":
    from lectureos.application.effective_srt_materialization import (
        EffectiveSrtMaterialization,
    )

    return EffectiveSrtMaterialization(
        identity=EffectiveSrtMaterializationId(row[0]),
        artifact_id=EffectiveSubtitleSrtArtifactId(row[1]),
        storage_kind=row[2],
        relative_location=row[3],
        payload_fingerprint=row[4],
        sequence=row[5],
        previous_materialization_id=(
            EffectiveSrtMaterializationId(row[6]) if row[6] is not None else None
        ),
    )


def _restore_outcome(row: tuple[object, ...]) -> "EffectiveSrtMaterializationOutcome":
    from lectureos.application.effective_srt_materialization import (
        EffectiveSrtMaterializationOutcome,
        MaterializationState,
    )

    return EffectiveSrtMaterializationOutcome(
        materialization_id=EffectiveSrtMaterializationId(row[0]),
        state=MaterializationState(row[1]),
        byte_length=row[2],
        failure_reason=row[3],
    )


__all__ = [
    "SQLiteEffectiveSrtMaterializationCommandPersistence",
    "SQLiteEffectiveSrtMaterializationRepository",
]
