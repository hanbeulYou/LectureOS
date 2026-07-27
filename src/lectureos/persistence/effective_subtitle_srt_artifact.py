"""Insert-only SQLite persistence for Effective Subtitle SRT Artifacts (GOAL-017).

Serializes one immutable logical SRT artifact per (final selection, serializer contract) in a
single atomic transaction. Artifacts are never updated or deleted: later authority changes derive
staleness at query time and leave every row untouched. The row stores the exact canonical SRT
payload (never a path, filename, URL, or materialization state). Any collision or error rolls back
with no partial state; no selection, candidate, decision, or legacy export row is ever touched.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from lectureos.application.identities import (
    EffectiveSubtitleCandidateId,
    EffectiveSubtitleFinalSelectionId,
    EffectiveSubtitleSrtArtifactId,
    TranscriptSourceIntakeId,
)

from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection

if TYPE_CHECKING:
    from lectureos.application.effective_subtitle_srt_artifact import (
        EffectiveSubtitleSrtArtifact,
    )

_REQUIRED_VERSION = 43


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(
            "Effective Subtitle SRT Artifact persistence requires SQLite schema version 43"
        )
    return version


class SQLiteEffectiveSubtitleSrtArtifactRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(
        self, identity: EffectiveSubtitleSrtArtifactId
    ) -> "EffectiveSubtitleSrtArtifact | None":
        try:
            row = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE identity = ?", (identity.value,)
            ).fetchone()
            return None if row is None else _restore(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Effective Subtitle SRT Artifact: {error}"
            ) from error

    def get_for_selection(
        self, final_selection_id: EffectiveSubtitleFinalSelectionId
    ) -> "EffectiveSubtitleSrtArtifact | None":
        try:
            row = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE final_selection_id = ? "
                "ORDER BY serializer_kind, serializer_version, "
                "serialization_parameters_version LIMIT 1",
                (final_selection_id.value,),
            ).fetchone()
            return None if row is None else _restore(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Effective Subtitle SRT Artifact: {error}"
            ) from error

    def list_for_intake(
        self, intake_id: TranscriptSourceIntakeId
    ) -> "tuple[EffectiveSubtitleSrtArtifact, ...]":
        try:
            rows = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE transcript_source_intake_id = ? "
                "ORDER BY final_selection_id, serializer_kind, serializer_version",
                (intake_id.value,),
            ).fetchall()
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not list Effective Subtitle SRT Artifacts: {error}"
            ) from error
        return tuple(_restore(row) for row in rows)


class SQLiteEffectiveSubtitleSrtArtifactCommandPersistence:
    """Owns one atomic v43 transaction inserting a logical SRT artifact."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_artifact(self, *, artifact: "EffectiveSubtitleSrtArtifact") -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(
                "Effective Subtitle SRT Artifact persistence requires SQLite schema version 43"
            )
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            if self._exists(artifact.identity.value):
                raise PersistenceIdentityCollisionError(
                    "Effective Subtitle SRT Artifact identity already exists"
                )
            self._connection.execute(
                """
                INSERT INTO subtitle_effective_srt_artifacts(
                    identity, transcript_source_intake_id, final_selection_id,
                    candidate_id, serializer_kind, serializer_version,
                    serialization_parameters_version, cue_count, content_fingerprint,
                    srt_content
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact.identity.value,
                    artifact.transcript_source_intake_id.value,
                    artifact.final_selection_id.value,
                    artifact.candidate_id.value,
                    artifact.serializer_kind,
                    artifact.serializer_version,
                    artifact.serialization_parameters_version,
                    artifact.cue_count,
                    artifact.content_fingerprint,
                    artifact.srt_content,
                ),
            )
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.IntegrityError as error:
            self._rollback(transaction_started)
            raise PersistenceIdentityCollisionError(
                f"Effective Subtitle SRT Artifact already exists: {error}"
            ) from error
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Effective Subtitle SRT Artifact: {error}"
            ) from error
        except Exception:
            self._rollback(transaction_started)
            raise

    def _exists(self, identity: str) -> bool:
        return (
            self._connection.execute(
                "SELECT 1 FROM subtitle_effective_srt_artifacts WHERE identity = ?",
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
    "SELECT identity, transcript_source_intake_id, final_selection_id, candidate_id, "
    "serializer_kind, serializer_version, serialization_parameters_version, cue_count, "
    "content_fingerprint, srt_content "
    "FROM subtitle_effective_srt_artifacts"
)


def _restore(row: tuple[object, ...]) -> "EffectiveSubtitleSrtArtifact":
    from lectureos.application.effective_subtitle_srt_artifact import (
        EffectiveSubtitleSrtArtifact,
    )

    return EffectiveSubtitleSrtArtifact(
        identity=EffectiveSubtitleSrtArtifactId(row[0]),
        transcript_source_intake_id=TranscriptSourceIntakeId(row[1]),
        final_selection_id=EffectiveSubtitleFinalSelectionId(row[2]),
        candidate_id=EffectiveSubtitleCandidateId(row[3]),
        serializer_kind=row[4],
        serializer_version=row[5],
        serialization_parameters_version=row[6],
        cue_count=row[7],
        content_fingerprint=row[8],
        srt_content=row[9],
    )


__all__ = [
    "SQLiteEffectiveSubtitleSrtArtifactCommandPersistence",
    "SQLiteEffectiveSubtitleSrtArtifactRepository",
]
