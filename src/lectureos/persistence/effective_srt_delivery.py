"""Insert-only SQLite persistence for Effective SRT Deliveries (GOAL-019).

Serializes the record-first delivery lifecycle: the immutable intent row is durable before any
destination write (one atomic transaction), and the immutable terminal outcome row is durable
after (a second atomic transaction) — a crash between them leaves an honest PENDING state,
derived, not stored. Neither row is ever updated or deleted; the physical filesystem is never
touched here, and no absolute Delivery Root is stored.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from lectureos.application.identities import (
    EffectiveSrtDeliveryId,
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
    from lectureos.application.effective_srt_delivery import (
        EffectiveSrtDelivery,
        EffectiveSrtDeliveryOutcome,
    )

_REQUIRED_VERSION = 45


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(
            "Effective SRT Delivery persistence requires SQLite schema version 45"
        )
    return version


class SQLiteEffectiveSrtDeliveryRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(self, identity: EffectiveSrtDeliveryId) -> "EffectiveSrtDelivery | None":
        try:
            row = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE identity = ?", (identity.value,)
            ).fetchone()
            return None if row is None else _restore(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Effective SRT Delivery: {error}"
            ) from error

    def get_outcome(
        self, identity: EffectiveSrtDeliveryId
    ) -> "EffectiveSrtDeliveryOutcome | None":
        try:
            row = self._connection.execute(
                "SELECT delivery_id, state, delivered_payload_fingerprint, byte_length, "
                "failure_category, failure_reason "
                "FROM subtitle_effective_srt_delivery_outcomes WHERE delivery_id = ?",
                (identity.value,),
            ).fetchone()
            return None if row is None else _restore_outcome(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Effective SRT Delivery outcome: {error}"
            ) from error

    def get_latest(
        self,
        materialization_id: EffectiveSrtMaterializationId,
        relative_location: str,
    ) -> "EffectiveSrtDelivery | None":
        try:
            row = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE materialization_id = ? AND relative_location = ? "
                "ORDER BY sequence DESC LIMIT 1",
                (materialization_id.value, relative_location),
            ).fetchone()
            return None if row is None else _restore(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read latest Effective SRT Delivery: {error}"
            ) from error

    def list_for_materialization(
        self, materialization_id: EffectiveSrtMaterializationId
    ) -> "tuple[EffectiveSrtDelivery, ...]":
        try:
            rows = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE materialization_id = ? "
                "ORDER BY relative_location, sequence",
                (materialization_id.value,),
            ).fetchall()
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not list Effective SRT Deliveries: {error}"
            ) from error
        return tuple(_restore(row) for row in rows)


class SQLiteEffectiveSrtDeliveryCommandPersistence:
    """Owns the two atomic v45 transactions of the record-first delivery lifecycle."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_delivery_intent(self, *, delivery: "EffectiveSrtDelivery") -> None:
        self._require()
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            exists = self._connection.execute(
                "SELECT 1 FROM subtitle_effective_srt_delivery_intents WHERE identity = ?",
                (delivery.identity.value,),
            ).fetchone()
            if exists is not None:
                raise PersistenceIdentityCollisionError(
                    "Effective SRT Delivery identity already exists"
                )
            self._require_valid_supersession(delivery)
            self._connection.execute(
                """
                INSERT INTO subtitle_effective_srt_delivery_intents(
                    identity, materialization_id, artifact_id, delivery_kind,
                    delivery_contract_version, relative_location,
                    expected_payload_fingerprint, sequence, overwrite,
                    previous_delivery_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    delivery.identity.value,
                    delivery.materialization_id.value,
                    delivery.artifact_id.value,
                    delivery.delivery_kind,
                    delivery.delivery_contract_version,
                    delivery.relative_location,
                    delivery.expected_payload_fingerprint,
                    delivery.sequence,
                    1 if delivery.overwrite else 0,
                    delivery.previous_delivery_id.value
                    if delivery.previous_delivery_id
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
                f"Effective SRT Delivery already exists: {error}"
            ) from error
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Effective SRT Delivery: {error}"
            ) from error
        except Exception:
            self._rollback(transaction_started)
            raise

    def persist_delivery_outcome(
        self, *, outcome: "EffectiveSrtDeliveryOutcome"
    ) -> None:
        self._require()
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            self._connection.execute(
                """
                INSERT INTO subtitle_effective_srt_delivery_outcomes(
                    delivery_id, state, delivered_payload_fingerprint, byte_length,
                    failure_category, failure_reason
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    outcome.delivery_id.value,
                    outcome.state.value,
                    outcome.delivered_payload_fingerprint,
                    outcome.byte_length,
                    outcome.failure_category.value
                    if outcome.failure_category is not None
                    else None,
                    outcome.failure_reason,
                ),
            )
            self._connection.execute("COMMIT")
        except sqlite3.IntegrityError as error:
            self._rollback(transaction_started)
            raise PersistenceIdentityCollisionError(
                f"Effective SRT Delivery outcome already exists: {error}"
            ) from error
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Effective SRT Delivery outcome: {error}"
            ) from error
        except Exception:
            self._rollback(transaction_started)
            raise

    def _require(self) -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(
                "Effective SRT Delivery persistence requires SQLite schema version 45"
            )

    def _require_valid_supersession(self, delivery: "EffectiveSrtDelivery") -> None:
        if delivery.previous_delivery_id is None:
            return
        row = self._connection.execute(
            """
            SELECT materialization_id, relative_location, sequence
            FROM subtitle_effective_srt_delivery_intents
            WHERE identity = ?
            """,
            (delivery.previous_delivery_id.value,),
        ).fetchone()
        if row is None:
            raise PersistenceError(
                "delivery supersedes an unknown previous delivery attempt"
            )
        if (
            row[0] != delivery.materialization_id.value
            or row[1] != delivery.relative_location
        ):
            raise PersistenceError(
                "delivery supersession must stay within one "
                "(materialization, destination) pair"
            )
        if row[2] != delivery.sequence - 1:
            raise PersistenceError(
                "delivery supersession must increment the sequence by one"
            )

    def _rollback(self, transaction_started: bool) -> None:
        if transaction_started and self._connection.in_transaction:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass


_SELECT_COLUMNS = (
    "SELECT identity, materialization_id, artifact_id, delivery_kind, "
    "delivery_contract_version, relative_location, expected_payload_fingerprint, "
    "sequence, overwrite, previous_delivery_id "
    "FROM subtitle_effective_srt_delivery_intents"
)


def _restore(row: tuple[object, ...]) -> "EffectiveSrtDelivery":
    from lectureos.application.effective_srt_delivery import EffectiveSrtDelivery

    return EffectiveSrtDelivery(
        identity=EffectiveSrtDeliveryId(row[0]),
        materialization_id=EffectiveSrtMaterializationId(row[1]),
        artifact_id=EffectiveSubtitleSrtArtifactId(row[2]),
        delivery_kind=row[3],
        delivery_contract_version=row[4],
        relative_location=row[5],
        expected_payload_fingerprint=row[6],
        sequence=row[7],
        overwrite=bool(row[8]),
        previous_delivery_id=(
            EffectiveSrtDeliveryId(row[9]) if row[9] is not None else None
        ),
    )


def _restore_outcome(row: tuple[object, ...]) -> "EffectiveSrtDeliveryOutcome":
    from lectureos.application.effective_srt_delivery import (
        DeliveryFailureCategory,
        DeliveryState,
        EffectiveSrtDeliveryOutcome,
    )

    return EffectiveSrtDeliveryOutcome(
        delivery_id=EffectiveSrtDeliveryId(row[0]),
        state=DeliveryState(row[1]),
        delivered_payload_fingerprint=row[2],
        byte_length=row[3],
        failure_category=(
            DeliveryFailureCategory(row[4]) if row[4] is not None else None
        ),
        failure_reason=row[5],
    )


__all__ = [
    "SQLiteEffectiveSrtDeliveryCommandPersistence",
    "SQLiteEffectiveSrtDeliveryRepository",
]
