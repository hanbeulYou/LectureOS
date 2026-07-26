"""Insert-only SQLite persistence for Effective Transcript Consumption bindings (040 §21, PATCH-0028).

Serializes one immutable consumption binding per (consumer kind, intake, exact source) in a single atomic
transaction. Bindings are never updated or deleted: later authority changes, staleness, rejections, and raw
switches leave every row untouched (currentness is derived at query time, never stored). The row records the
exact immutable source consumed (source kind + identity + exact Raw parent), the authority provenance observed
at acquisition (raw selection record, corrected selection record where history existed), and the deterministic
content manifest (segment count + the §19 content fingerprint). Any collision or error rolls back with no
partial state; no transcript, selection, candidate, or decision row is ever touched.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from lectureos.application.identities import (
    CorrectedRevisionSelectionId,
    CurrentRawTranscriptSelectionId,
    EffectiveTranscriptConsumptionId,
    TranscriptSourceIntakeId,
)
from lectureos.transcript.identities import TranscriptId, TranscriptRevisionId

from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection

if TYPE_CHECKING:
    from lectureos.application.effective_transcript_consumption import (
        EffectiveTranscriptConsumption,
    )

_REQUIRED_VERSION = 38


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(
            "Effective Transcript Consumption persistence requires SQLite schema version 38"
        )
    return version


class SQLiteEffectiveTranscriptConsumptionRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(
        self, identity: EffectiveTranscriptConsumptionId
    ) -> "EffectiveTranscriptConsumption | None":
        try:
            row = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE identity = ?", (identity.value,)
            ).fetchone()
            return None if row is None else _restore(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Effective Transcript Consumption: {error}"
            ) from error

    def list_for_intake(
        self, intake_id: TranscriptSourceIntakeId
    ) -> "tuple[EffectiveTranscriptConsumption, ...]":
        try:
            rows = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE transcript_source_intake_id = ? "
                "ORDER BY consumer_kind, source_transcript_identity",
                (intake_id.value,),
            ).fetchall()
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not list Effective Transcript Consumptions: {error}"
            ) from error
        return tuple(_restore(row) for row in rows)


class SQLiteEffectiveTranscriptConsumptionCommandPersistence:
    """Owns one atomic v38 transaction inserting a consumption binding."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_consumption(
        self, *, consumption: "EffectiveTranscriptConsumption"
    ) -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(
                "Effective Transcript Consumption persistence requires SQLite schema version 38"
            )
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            if self._exists(consumption.identity.value):
                raise PersistenceIdentityCollisionError(
                    "Effective Transcript Consumption identity already exists"
                )
            self._connection.execute(
                """
                INSERT INTO effective_transcript_consumptions(
                    identity, consumer_kind, transcript_source_intake_id, resolution_state,
                    source_kind, source_transcript_identity, parent_raw_transcript_id,
                    corrected_revision_id, raw_selection_id, corrected_selection_id,
                    content_fingerprint, segment_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    consumption.identity.value,
                    consumption.consumer_kind,
                    consumption.transcript_source_intake_id.value,
                    consumption.resolution_state.value,
                    consumption.source_kind.value,
                    consumption.source_transcript_identity,
                    consumption.parent_raw_transcript_id.value,
                    consumption.corrected_revision_id.value
                    if consumption.corrected_revision_id
                    else None,
                    consumption.raw_selection_id.value,
                    consumption.corrected_selection_id.value
                    if consumption.corrected_selection_id
                    else None,
                    consumption.content_fingerprint,
                    consumption.segment_count,
                ),
            )
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.IntegrityError as error:
            self._rollback(transaction_started)
            raise PersistenceIdentityCollisionError(
                f"Effective Transcript Consumption already exists: {error}"
            ) from error
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Effective Transcript Consumption: {error}"
            ) from error
        except Exception:
            self._rollback(transaction_started)
            raise

    def _exists(self, identity: str) -> bool:
        return (
            self._connection.execute(
                "SELECT 1 FROM effective_transcript_consumptions WHERE identity = ?",
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
    "SELECT identity, consumer_kind, transcript_source_intake_id, resolution_state, "
    "source_kind, parent_raw_transcript_id, corrected_revision_id, raw_selection_id, "
    "corrected_selection_id, content_fingerprint, segment_count "
    "FROM effective_transcript_consumptions"
)


def _restore(row: tuple[object, ...]) -> "EffectiveTranscriptConsumption":
    from lectureos.application.effective_transcript_consumption import (
        ConsumedSourceKind,
        EffectiveTranscriptConsumption,
    )
    from lectureos.application.corrected_revision_selection import SelectionState

    return EffectiveTranscriptConsumption(
        identity=EffectiveTranscriptConsumptionId(row[0]),
        consumer_kind=row[1],
        transcript_source_intake_id=TranscriptSourceIntakeId(row[2]),
        resolution_state=SelectionState(row[3]),
        source_kind=ConsumedSourceKind(row[4]),
        parent_raw_transcript_id=TranscriptId(row[5]),
        corrected_revision_id=(
            TranscriptRevisionId(row[6]) if row[6] is not None else None
        ),
        raw_selection_id=CurrentRawTranscriptSelectionId(row[7]),
        corrected_selection_id=(
            CorrectedRevisionSelectionId(row[8]) if row[8] is not None else None
        ),
        content_fingerprint=row[9],
        segment_count=row[10],
    )


__all__ = [
    "SQLiteEffectiveTranscriptConsumptionCommandPersistence",
    "SQLiteEffectiveTranscriptConsumptionRepository",
]
