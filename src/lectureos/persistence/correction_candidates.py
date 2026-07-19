"""Insert-only SQLite repository for canonical CorrectionCandidate records."""

from __future__ import annotations

import sqlite3

from lectureos.execution.identities import (
    CapabilityReference,
    DomainResultId,
    PluginReference,
    ProcessingRunId,
    UnitExecutionId,
)
from lectureos.transcript.identities import (
    CorrectionCandidateId,
    TranscriptId,
    TranscriptRevisionId,
    TranscriptSegmentId,
)
from lectureos.transcript.models import CorrectionCandidate

from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection


class SQLiteCorrectionCandidateRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        if validate_sqlite_connection(connection) < 5:
            raise SchemaFeatureUnavailableError(
                "CorrectionCandidate persistence requires SQLite schema version 5"
            )
        self._connection = connection

    def get(self, identity: CorrectionCandidateId) -> CorrectionCandidate | None:
        try:
            row = self._connection.execute(
                """
                SELECT identity, domain_result_id, transcript_id, segment_id,
                       proposed_text, rationale, processing_run_id,
                       unit_execution_id, target_revision_id, confidence,
                       uncertainty, capability, plugin_reference,
                       provider_reference
                FROM correction_candidates
                WHERE identity = ?
                """,
                (identity.value,),
            ).fetchone()
            if row is None:
                return None
            return self._restore(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read CorrectionCandidate: {error}"
            ) from error

    def save(self, record: CorrectionCandidate) -> None:
        if self.get(record.identity) is not None:
            raise PersistenceIdentityCollisionError(
                "CorrectionCandidate identity already exists"
            )
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            _insert_correction_candidate(self._connection, record)
            self._connection.execute("COMMIT")
        except sqlite3.IntegrityError as error:
            self._rollback()
            if self.get(record.identity) is not None:
                raise PersistenceIdentityCollisionError(
                    "CorrectionCandidate identity already exists"
                ) from error
            raise PersistenceError(
                f"could not persist CorrectionCandidate: {error}"
            ) from error
        except sqlite3.Error as error:
            self._rollback()
            raise PersistenceError(
                f"could not persist CorrectionCandidate: {error}"
            ) from error
        except Exception:
            self._rollback()
            raise

    def _restore(self, row: tuple[object, ...]) -> CorrectionCandidate:
        identity = CorrectionCandidateId(row[0])
        return CorrectionCandidate(
            identity=identity,
            domain_result_id=DomainResultId(row[1]),
            transcript_id=TranscriptId(row[2]),
            segment_id=TranscriptSegmentId(row[3]),
            proposed_text=row[4],
            rationale=row[5],
            run_id=ProcessingRunId(row[6]),
            unit_execution_id=UnitExecutionId(row[7]),
            target_revision_id=(
                TranscriptRevisionId(row[8]) if row[8] is not None else None
            ),
            evidence=self._evidence_values(identity),
            confidence=row[9],
            uncertainty=row[10],
            capability=(CapabilityReference(row[11]) if row[11] is not None else None),
            plugin_reference=(PluginReference(row[12]) if row[12] is not None else None),
            provider_reference=row[13],
        )

    def _evidence_values(self, identity: CorrectionCandidateId) -> tuple[str, ...]:
        rows = self._connection.execute(
            """
            SELECT ordinal, evidence
            FROM correction_candidate_evidence
            WHERE correction_candidate_id = ?
            ORDER BY ordinal
            """,
            (identity.value,),
        ).fetchall()
        if tuple(row[0] for row in rows) != tuple(range(len(rows))):
            raise PersistenceError("CorrectionCandidate evidence ordering is corrupt")
        return tuple(row[1] for row in rows)

    def _rollback(self) -> None:
        if self._connection.in_transaction:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass


def _insert_correction_candidate(
    connection: sqlite3.Connection, record: CorrectionCandidate
) -> None:
    """Insert one complete Candidate without owning a transaction."""

    connection.execute(
        """
        INSERT INTO correction_candidates(
            identity, domain_result_id, transcript_id, segment_id,
            proposed_text, rationale, processing_run_id, unit_execution_id,
            target_revision_id, confidence, uncertainty, capability,
            plugin_reference, provider_reference
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.identity.value,
            record.domain_result_id.value,
            record.transcript_id.value,
            record.segment_id.value,
            record.proposed_text,
            record.rationale,
            record.run_id.value,
            record.unit_execution_id.value,
            record.target_revision_id.value if record.target_revision_id else None,
            record.confidence,
            record.uncertainty,
            record.capability.value if record.capability else None,
            record.plugin_reference.value if record.plugin_reference else None,
            record.provider_reference,
        ),
    )
    connection.executemany(
        """
        INSERT INTO correction_candidate_evidence(
            correction_candidate_id, ordinal, evidence
        ) VALUES (?, ?, ?)
        """,
        (
            (record.identity.value, ordinal, evidence)
            for ordinal, evidence in enumerate(record.evidence)
        ),
    )
