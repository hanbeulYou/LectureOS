"""Append-only SQLite persistence for Lecture Analysis Input Admissions (GOAL-023).

Serializes one immutable admitted analysis input per exact source in a single atomic
transaction. Rows are never updated or deleted; a changed authority admits a NEW record for the
new source. Collisions map to the released identity-collision error so the application layer
converges idempotently. No legacy analysis table (`eligible_analysis_inputs`) is ever touched.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from lectureos.application.identities import (
    LectureAnalysisInputAdmissionId,
    TranscriptSourceIntakeId,
)
from lectureos.execution.identities import SourceMediaId
from lectureos.transcript.identities import TranscriptId, TranscriptRevisionId

from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection

if TYPE_CHECKING:
    from lectureos.application.lecture_analysis_input_admission import (
        LectureAnalysisInputAdmission,
    )

_REQUIRED_VERSION = 47


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(
            "Lecture Analysis Input Admission persistence requires SQLite schema version 47"
        )
    return version


class SQLiteLectureAnalysisInputAdmissionRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(
        self, identity: LectureAnalysisInputAdmissionId
    ) -> "LectureAnalysisInputAdmission | None":
        try:
            row = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE identity = ?", (identity.value,)
            ).fetchone()
            return None if row is None else _restore(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Lecture Analysis Input Admission: {error}"
            ) from error

    def list_for_intake(
        self, intake_id: TranscriptSourceIntakeId
    ) -> "tuple[LectureAnalysisInputAdmission, ...]":
        try:
            rows = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE transcript_source_intake_id = ? "
                "ORDER BY identity",
                (intake_id.value,),
            ).fetchall()
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not list Lecture Analysis Input Admissions: {error}"
            ) from error
        return tuple(_restore(row) for row in rows)


class SQLiteLectureAnalysisInputAdmissionCommandPersistence:
    """Owns one atomic v47 transaction appending an immutable admitted analysis input."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_admission(self, *, admission: "LectureAnalysisInputAdmission") -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(
                "Lecture Analysis Input Admission persistence requires SQLite schema "
                "version 47"
            )
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            exists = self._connection.execute(
                "SELECT 1 FROM lecture_analysis_input_admissions WHERE identity = ?",
                (admission.identity.value,),
            ).fetchone()
            if exists is not None:
                raise PersistenceIdentityCollisionError(
                    "Lecture Analysis Input Admission identity already exists"
                )
            self._connection.execute(
                """
                INSERT INTO lecture_analysis_input_admissions(
                    identity, transcript_source_intake_id, source_media_id,
                    corrected_revision_id, parent_raw_transcript_id, raw_selection_id,
                    corrected_selection_id, content_fingerprint, segment_count,
                    admission_contract_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    admission.identity.value,
                    admission.transcript_source_intake_id.value,
                    admission.source_media_id.value,
                    admission.corrected_revision_id.value,
                    admission.parent_raw_transcript_id.value,
                    admission.raw_selection_id.value,
                    admission.corrected_selection_id.value,
                    admission.content_fingerprint,
                    admission.segment_count,
                    admission.admission_contract_version,
                ),
            )
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.IntegrityError as error:
            self._rollback(transaction_started)
            raise PersistenceIdentityCollisionError(
                f"Lecture Analysis Input Admission already exists: {error}"
            ) from error
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Lecture Analysis Input Admission: {error}"
            ) from error
        except Exception:
            self._rollback(transaction_started)
            raise

    def _rollback(self, transaction_started: bool) -> None:
        if transaction_started and self._connection.in_transaction:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass


_SELECT_COLUMNS = (
    "SELECT identity, transcript_source_intake_id, source_media_id, "
    "corrected_revision_id, parent_raw_transcript_id, raw_selection_id, "
    "corrected_selection_id, content_fingerprint, segment_count, "
    "admission_contract_version "
    "FROM lecture_analysis_input_admissions"
)


def _restore(row: tuple[object, ...]) -> "LectureAnalysisInputAdmission":
    from lectureos.application.identities import (
        CorrectedRevisionSelectionId,
        CurrentRawTranscriptSelectionId,
    )
    from lectureos.application.lecture_analysis_input_admission import (
        LectureAnalysisInputAdmission,
    )

    return LectureAnalysisInputAdmission(
        identity=LectureAnalysisInputAdmissionId(row[0]),
        transcript_source_intake_id=TranscriptSourceIntakeId(row[1]),
        source_media_id=SourceMediaId(row[2]),
        corrected_revision_id=TranscriptRevisionId(row[3]),
        parent_raw_transcript_id=TranscriptId(row[4]),
        raw_selection_id=CurrentRawTranscriptSelectionId(row[5]),
        corrected_selection_id=CorrectedRevisionSelectionId(row[6]),
        content_fingerprint=row[7],
        segment_count=row[8],
        admission_contract_version=row[9],
    )


__all__ = [
    "SQLiteLectureAnalysisInputAdmissionCommandPersistence",
    "SQLiteLectureAnalysisInputAdmissionRepository",
]
