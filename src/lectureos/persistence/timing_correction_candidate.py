"""Atomic SQLite persistence for Human Timing Correction Candidates (040 §17 sibling, PATCH-0047).

Serializes one admitted human-authored timing proposal into the additive `timing_correction_candidates`
relation in a single transaction. It is a **sibling** of the released text-correction persistence, never
a reuse of it: nothing here reads, writes, widens, or reinterprets `correction_candidates`,
`correction_candidate_admissions`, or any other released relation (TC-2, TC-19, TC-20). An admitted
candidate is never updated, deleted, or overwritten, and no Raw Transcript, segment, revision, or
selection row is ever touched.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from lectureos.application.identities import (
    TimingCorrectionCandidateId,
    TranscriptSourceIntakeId,
)
from lectureos.review.identities import HumanActorReference
from lectureos.transcript.identities import TranscriptId, TranscriptSegmentId

from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection

if TYPE_CHECKING:
    from lectureos.application.timing_correction_candidate_admission import (
        TimingCorrectionCandidate,
        TimingCorrectionCandidateView,
    )

_REQUIRED_VERSION = 54
_UNAVAILABLE = (
    "Timing Correction Candidate persistence requires SQLite schema version 54"
)

_SELECT_COLUMNS = (
    "SELECT identity, transcript_source_intake_id, raw_transcript_id, segment_id, author, "
    "candidate_ref, source_start_snapshot, source_end_snapshot, proposed_start, proposed_end, "
    "rationale, content_fingerprint FROM timing_correction_candidates"
)


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(_UNAVAILABLE)
    return version


class SQLiteTimingCorrectionCandidateRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(
        self, identity: TimingCorrectionCandidateId
    ) -> "TimingCorrectionCandidate | None":
        try:
            row = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE identity = ?", (identity.value,)
            ).fetchone()
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Timing Correction Candidate: {error}"
            ) from error
        return None if row is None else _restore(row)

    def candidates_for_intake(
        self,
        intake_id: TranscriptSourceIntakeId,
        current_raw_transcript_id: TranscriptId | None,
    ) -> "tuple[TimingCorrectionCandidateView, ...]":
        from lectureos.application.timing_correction_candidate_admission import (
            TimingCorrectionCandidateView,
        )

        try:
            rows = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE transcript_source_intake_id = ? ORDER BY identity",
                (intake_id.value,),
            ).fetchall()
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not list Timing Correction Candidates: {error}"
            ) from error
        current = None if current_raw_transcript_id is None else current_raw_transcript_id.value
        return tuple(
            TimingCorrectionCandidateView(
                candidate=_restore(row),
                applicable_to_current_selection=current is not None and row[2] == current,
            )
            for row in rows
        )

    def candidates_for_segment(
        self, segment_id: TranscriptSegmentId
    ) -> "tuple[TimingCorrectionCandidate, ...]":
        try:
            rows = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE segment_id = ? ORDER BY identity",
                (segment_id.value,),
            ).fetchall()
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not list Timing Correction Candidates: {error}"
            ) from error
        return tuple(_restore(row) for row in rows)


class SQLiteTimingCorrectionCandidateCommandPersistence:
    """Owns one atomic v54 transaction persisting a complete timing correction candidate."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_timing_correction_candidate(
        self, *, candidate: "TimingCorrectionCandidate"
    ) -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(_UNAVAILABLE)
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            if self._exists(candidate.identity.value):
                raise PersistenceIdentityCollisionError(
                    "Timing Correction Candidate already exists"
                )
            self._connection.execute(
                """
                INSERT INTO timing_correction_candidates(
                    identity, transcript_source_intake_id, raw_transcript_id, segment_id,
                    author, candidate_ref, source_start_snapshot, source_end_snapshot,
                    proposed_start, proposed_end, rationale, content_fingerprint
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate.identity.value,
                    candidate.transcript_source_intake_id.value,
                    candidate.raw_transcript_id.value,
                    candidate.segment_id.value,
                    candidate.author.value,
                    candidate.candidate_ref,
                    float(candidate.source_start_snapshot),
                    float(candidate.source_end_snapshot),
                    float(candidate.proposed_start),
                    float(candidate.proposed_end),
                    candidate.rationale,
                    candidate.content_fingerprint,
                ),
            )
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.IntegrityError as error:
            self._rollback(transaction_started)
            raise PersistenceIdentityCollisionError(
                f"Timing Correction Candidate already exists: {error}"
            ) from error
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Timing Correction Candidate: {error}"
            ) from error
        except Exception:
            self._rollback(transaction_started)
            raise

    def _exists(self, identity: str) -> bool:
        return (
            self._connection.execute(
                "SELECT 1 FROM timing_correction_candidates WHERE identity = ?", (identity,)
            ).fetchone()
            is not None
        )

    def _rollback(self, transaction_started: bool) -> None:
        if transaction_started and self._connection.in_transaction:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass


def _restore(row: tuple[object, ...]) -> "TimingCorrectionCandidate":
    from lectureos.application.timing_correction_candidate_admission import (
        TimingCorrectionCandidate,
    )

    return TimingCorrectionCandidate(
        identity=TimingCorrectionCandidateId(row[0]),
        transcript_source_intake_id=TranscriptSourceIntakeId(row[1]),
        raw_transcript_id=TranscriptId(row[2]),
        segment_id=TranscriptSegmentId(row[3]),
        author=HumanActorReference(row[4]),
        candidate_ref=row[5],
        source_start_snapshot=row[6],
        source_end_snapshot=row[7],
        proposed_start=row[8],
        proposed_end=row[9],
        rationale=row[10],
        content_fingerprint=row[11],
    )


__all__ = [
    "SQLiteTimingCorrectionCandidateCommandPersistence",
    "SQLiteTimingCorrectionCandidateRepository",
]
