"""Append-only SQLite persistence for Effective SRT Publications (GOAL-020).

Serializes one immutable publication-authority record per authority change in a single atomic
transaction — the released idiom: per-intake ``sequence`` + ``previous_publication_id``
supersession, current publication derived as the highest sequence (no mutable flag, no
latest-row heuristic). Publications are never updated or deleted; a later command appends. Any
collision or error rolls back with no partial state; no delivery, materialization, artifact, or
legacy row is ever touched, and no filesystem access occurs here.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from lectureos.application.identities import (
    EffectiveSrtDeliveryId,
    EffectiveSrtPublicationId,
    EffectiveSubtitleSrtArtifactId,
    TranscriptSourceIntakeId,
)
from lectureos.review.identities import HumanActorReference

from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection

if TYPE_CHECKING:
    from lectureos.application.effective_srt_publication import EffectiveSrtPublication

_REQUIRED_VERSION = 46


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(
            "Effective SRT Publication persistence requires SQLite schema version 46"
        )
    return version


class SQLiteEffectiveSrtPublicationRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(
        self, identity: EffectiveSrtPublicationId
    ) -> "EffectiveSrtPublication | None":
        try:
            row = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE identity = ?", (identity.value,)
            ).fetchone()
            return None if row is None else _restore(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Effective SRT Publication: {error}"
            ) from error

    def get_current(
        self, intake_id: TranscriptSourceIntakeId
    ) -> "EffectiveSrtPublication | None":
        try:
            row = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE transcript_source_intake_id = ? "
                "ORDER BY sequence DESC LIMIT 1",
                (intake_id.value,),
            ).fetchone()
            return None if row is None else _restore(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read current Effective SRT Publication: {error}"
            ) from error

    def history(
        self, intake_id: TranscriptSourceIntakeId
    ) -> "tuple[EffectiveSrtPublication, ...]":
        try:
            rows = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE transcript_source_intake_id = ? ORDER BY sequence",
                (intake_id.value,),
            ).fetchall()
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Effective SRT Publication history: {error}"
            ) from error
        return tuple(_restore(row) for row in rows)


class SQLiteEffectiveSrtPublicationCommandPersistence:
    """Owns one atomic v46 transaction appending a publication-authority record."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_publication(self, *, publication: "EffectiveSrtPublication") -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(
                "Effective SRT Publication persistence requires SQLite schema version 46"
            )
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            if self._exists(publication.identity.value):
                raise PersistenceIdentityCollisionError(
                    "Effective SRT Publication identity already exists"
                )
            self._require_valid_supersession(publication)
            self._connection.execute(
                """
                INSERT INTO subtitle_effective_srt_publications(
                    identity, transcript_source_intake_id, kind, target_delivery_id,
                    target_artifact_id, publisher, sequence, content_fingerprint,
                    previous_publication_id, rationale
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    publication.identity.value,
                    publication.transcript_source_intake_id.value,
                    publication.kind.value,
                    publication.target_delivery_id.value
                    if publication.target_delivery_id
                    else None,
                    publication.target_artifact_id.value
                    if publication.target_artifact_id
                    else None,
                    publication.publisher.value,
                    publication.sequence,
                    publication.content_fingerprint,
                    publication.previous_publication_id.value
                    if publication.previous_publication_id
                    else None,
                    publication.rationale,
                ),
            )
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.IntegrityError as error:
            self._rollback(transaction_started)
            raise PersistenceIdentityCollisionError(
                f"Effective SRT Publication already exists: {error}"
            ) from error
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Effective SRT Publication: {error}"
            ) from error
        except Exception:
            self._rollback(transaction_started)
            raise

    def _require_valid_supersession(self, publication: "EffectiveSrtPublication") -> None:
        if publication.previous_publication_id is None:
            return
        row = self._connection.execute(
            """
            SELECT transcript_source_intake_id, sequence
            FROM subtitle_effective_srt_publications
            WHERE identity = ?
            """,
            (publication.previous_publication_id.value,),
        ).fetchone()
        if row is None:
            raise PersistenceError("publication supersedes an unknown previous publication")
        if row[0] != publication.transcript_source_intake_id.value:
            raise PersistenceError(
                "publication supersession must stay within one intake scope"
            )
        if row[1] != publication.sequence - 1:
            raise PersistenceError(
                "publication supersession must increment the sequence by one"
            )

    def _exists(self, identity: str) -> bool:
        return (
            self._connection.execute(
                "SELECT 1 FROM subtitle_effective_srt_publications WHERE identity = ?",
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
    "SELECT identity, transcript_source_intake_id, kind, target_delivery_id, "
    "target_artifact_id, publisher, sequence, content_fingerprint, "
    "previous_publication_id, rationale "
    "FROM subtitle_effective_srt_publications"
)


def _restore(row: tuple[object, ...]) -> "EffectiveSrtPublication":
    from lectureos.application.effective_srt_publication import (
        EffectiveSrtPublication,
        PublicationKind,
    )

    return EffectiveSrtPublication(
        identity=EffectiveSrtPublicationId(row[0]),
        transcript_source_intake_id=TranscriptSourceIntakeId(row[1]),
        kind=PublicationKind(row[2]),
        target_delivery_id=(
            EffectiveSrtDeliveryId(row[3]) if row[3] is not None else None
        ),
        target_artifact_id=(
            EffectiveSubtitleSrtArtifactId(row[4]) if row[4] is not None else None
        ),
        publisher=HumanActorReference(row[5]),
        sequence=row[6],
        content_fingerprint=row[7],
        previous_publication_id=(
            EffectiveSrtPublicationId(row[8]) if row[8] is not None else None
        ),
        rationale=row[9],
    )


__all__ = [
    "SQLiteEffectiveSrtPublicationCommandPersistence",
    "SQLiteEffectiveSrtPublicationRepository",
]
