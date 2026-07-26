"""Atomic SQLite persistence for Correction Candidate Admission (040 §17, PATCH-0024).

Serializes one admitted correction suggestion in a single transaction: the canonical `CorrectionCandidate`
(reusing the v5 correction records), its `DomainResultReference` provenance, and the additive
`correction_candidate_admissions` binding row (intake, target segment, immutable source-text snapshot, source
metadata, content fingerprint). It reuses the existing transaction-free insert helpers so an admitted candidate is
structurally identical to a generated one. Any collision or error rolls back with no partial state; an admitted
candidate is never silently overwritten, and no Raw Transcript / segment / selection row is mutated.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from lectureos.application.identities import (
    CorrectionCandidateAdmissionId,
    TranscriptSourceIntakeId,
)
from lectureos.execution.models import DomainResultReference
from lectureos.transcript.identities import (
    CorrectionCandidateId,
    TranscriptId,
    TranscriptSegmentId,
)
from lectureos.transcript.models import CorrectionCandidate

from .correction_candidates import (
    SQLiteCorrectionCandidateRepository,
    _insert_correction_candidate,
)
from .domain_results import _insert_domain_result_reference_record
from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection

if TYPE_CHECKING:
    from lectureos.application.correction_candidate_admission import (
        CorrectionCandidateAdmission,
        CorrectionCandidateView,
    )

_REQUIRED_VERSION = 34


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(
            "Correction Candidate Admission persistence requires SQLite schema version 34"
        )
    return version


class SQLiteCorrectionCandidateAdmissionRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(
        self, identity: CorrectionCandidateAdmissionId
    ) -> "CorrectionCandidateAdmission | None":
        try:
            row = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE identity = ?", (identity.value,)
            ).fetchone()
            return None if row is None else _restore(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Correction Candidate Admission: {error}"
            ) from error

    def candidate(self, candidate_id: CorrectionCandidateId) -> CorrectionCandidate | None:
        return SQLiteCorrectionCandidateRepository(self._connection).get(candidate_id)

    def get_by_candidate(
        self, candidate_id: CorrectionCandidateId
    ) -> "CorrectionCandidateAdmission | None":
        # Well-defined: the schema enforces UNIQUE(correction_candidate_id).
        try:
            row = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE correction_candidate_id = ?",
                (candidate_id.value,),
            ).fetchone()
            return None if row is None else _restore(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Correction Candidate Admission: {error}"
            ) from error

    def candidates_for_intake(
        self,
        intake_id: TranscriptSourceIntakeId,
        current_raw_transcript_id: TranscriptId | None,
    ) -> "tuple[CorrectionCandidateView, ...]":
        from lectureos.application.correction_candidate_admission import (
            CorrectionCandidateSourceType,
            CorrectionCandidateView,
        )

        try:
            rows = self._connection.execute(
                """
                SELECT a.correction_candidate_id, a.raw_transcript_id, a.segment_id,
                       a.source_type, a.source_reference, a.candidate_ref,
                       a.source_text_snapshot, c.proposed_text
                FROM correction_candidate_admissions a
                JOIN correction_candidates c ON c.identity = a.correction_candidate_id
                WHERE a.transcript_source_intake_id = ?
                ORDER BY a.segment_id, a.candidate_ref, a.correction_candidate_id
                """,
                (intake_id.value,),
            ).fetchall()
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read correction candidates: {error}"
            ) from error
        current = current_raw_transcript_id.value if current_raw_transcript_id else None
        return tuple(
            CorrectionCandidateView(
                correction_candidate_id=CorrectionCandidateId(row[0]),
                raw_transcript_id=TranscriptId(row[1]),
                segment_id=TranscriptSegmentId(row[2]),
                source_type=CorrectionCandidateSourceType(row[3]),
                source_reference=row[4],
                candidate_ref=row[5],
                source_text=row[6],
                proposed_text=row[7],
                applicable_to_current_selection=row[1] == current,
            )
            for row in rows
        )


class SQLiteCorrectionCandidateAdmissionCommandPersistence:
    """Owns one atomic v34 transaction persisting an admitted correction candidate."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_correction_candidate_admission(
        self,
        *,
        admission: "CorrectionCandidateAdmission",
        candidate: CorrectionCandidate,
        result: DomainResultReference,
    ) -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(
                "Correction Candidate Admission persistence requires SQLite schema version 34"
            )
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            _validate_linkage(admission, candidate, result)
            if (
                self._exists("identity", admission.identity.value)
                or self._exists(
                    "correction_candidate_id", admission.correction_candidate_id.value
                )
                or self._candidate_exists(candidate.identity)
            ):
                raise PersistenceIdentityCollisionError(
                    "Correction Candidate Admission records already exist"
                )
            _insert_correction_candidate(self._connection, candidate)
            _insert_domain_result_reference_record(self._connection, result)
            self._connection.execute(
                """
                INSERT INTO correction_candidate_admissions(
                    identity, correction_candidate_id, transcript_source_intake_id,
                    raw_transcript_id, segment_id, source_type, source_reference,
                    candidate_ref, model_reference, source_text_snapshot,
                    content_fingerprint
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    admission.identity.value,
                    admission.correction_candidate_id.value,
                    admission.transcript_source_intake_id.value,
                    admission.raw_transcript_id.value,
                    admission.segment_id.value,
                    admission.source_type.value,
                    admission.source_reference,
                    admission.candidate_ref,
                    admission.model_reference,
                    admission.source_text_snapshot,
                    admission.content_fingerprint,
                ),
            )
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.IntegrityError as error:
            self._rollback(transaction_started)
            raise PersistenceIdentityCollisionError(
                f"Correction Candidate Admission already exists: {error}"
            ) from error
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Correction Candidate Admission: {error}"
            ) from error
        except Exception:
            self._rollback(transaction_started)
            raise

    def _exists(self, column: str, value: str) -> bool:
        return (
            self._connection.execute(
                f"SELECT 1 FROM correction_candidate_admissions WHERE {column} = ?",
                (value,),
            ).fetchone()
            is not None
        )

    def _candidate_exists(self, identity: CorrectionCandidateId) -> bool:
        return (
            self._connection.execute(
                "SELECT 1 FROM correction_candidates WHERE identity = ?", (identity.value,)
            ).fetchone()
            is not None
        )

    def _rollback(self, transaction_started: bool) -> None:
        if transaction_started and self._connection.in_transaction:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass


def _validate_linkage(
    admission: "CorrectionCandidateAdmission",
    candidate: CorrectionCandidate,
    result: DomainResultReference,
) -> None:
    if admission.correction_candidate_id != candidate.identity:
        raise PersistenceError("admission candidate identity must match the candidate")
    if candidate.transcript_id != admission.raw_transcript_id:
        raise PersistenceError("candidate transcript must match the admission raw transcript")
    if candidate.segment_id != admission.segment_id:
        raise PersistenceError("candidate segment must match the admission segment")
    if result.identity != candidate.domain_result_id:
        raise PersistenceError("domain result identity must match the candidate")
    if result.kind != "transcript_correction_candidate":
        raise PersistenceError("domain result kind must be transcript_correction_candidate")
    if len(result.upstream_results) != 1:
        raise PersistenceError("candidate domain result requires exactly one upstream result")


_SELECT_COLUMNS = (
    "SELECT identity, correction_candidate_id, transcript_source_intake_id, "
    "raw_transcript_id, segment_id, source_type, source_reference, candidate_ref, "
    "model_reference, source_text_snapshot, content_fingerprint "
    "FROM correction_candidate_admissions"
)


def _restore(row: tuple[object, ...]) -> "CorrectionCandidateAdmission":
    from lectureos.application.correction_candidate_admission import (
        CorrectionCandidateAdmission,
        CorrectionCandidateSourceType,
    )

    return CorrectionCandidateAdmission(
        identity=CorrectionCandidateAdmissionId(row[0]),
        correction_candidate_id=CorrectionCandidateId(row[1]),
        transcript_source_intake_id=TranscriptSourceIntakeId(row[2]),
        raw_transcript_id=TranscriptId(row[3]),
        segment_id=TranscriptSegmentId(row[4]),
        source_type=CorrectionCandidateSourceType(row[5]),
        source_reference=row[6],
        candidate_ref=row[7],
        model_reference=row[8],
        source_text_snapshot=row[9],
        content_fingerprint=row[10],
    )


__all__ = [
    "SQLiteCorrectionCandidateAdmissionCommandPersistence",
    "SQLiteCorrectionCandidateAdmissionRepository",
]
