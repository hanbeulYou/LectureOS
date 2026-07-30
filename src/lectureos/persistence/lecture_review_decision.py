"""Append-only SQLite persistence for effective-generation Review records (043 §7.5, GOAL-028).

Serializes one immutable `ReviewDecision` and — for `accept` and `modify` — exactly one immutable
`ApprovedEditDecision` in a **single atomic transaction**. `§7.4`'s all-or-nothing requirement,
inherited by R-11, means a partially recorded Review admission must never be visible as valid: both
inserts share one `BEGIN IMMEDIATE`, and any failure rolls the pair back together.

Rows are never updated or deleted (R-5). A different canonical judgment records new rows; collisions
map to the released identity-collision error so the application layer converges idempotently (R-11).

No ordinal column exists (R-9), no status, current, stale, or selection column exists (R-4), and no
execution, `DomainResult`, Source Media, or Source Timeline column exists — R-6 removes the first two
from this generation and R-7 secures the inherited provenance through the anchor chain instead.

The legacy execution-coupled Review family (`edit_review_decisions`, `approved_edit_decisions`) is
never read or written here: PATCH-0033 R-12 keeps the two contract generations separate, and those
relations could not hold this generation's rows without fabricating the legacy Edit Candidate anchor,
`domain_result_id`, `processing_run_id`, `unit_execution_id`, and `sequence` that R-6 and R-9
prohibit.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from lectureos.application.identities import (
    LectureAnalysisEditCandidateId,
    LectureApprovedEditDecisionId,
    LectureReviewDecisionId,
)
from lectureos.review.identities import HumanActorReference

from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection

if TYPE_CHECKING:
    from lectureos.application.lecture_review_decision import (
        LectureApprovedEditDecision,
        LectureReviewDecision,
    )

_REQUIRED_VERSION = 51

_UNAVAILABLE = "Lecture Review persistence requires SQLite schema version 51"


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(_UNAVAILABLE)
    return version


class SQLiteLectureReviewRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get_decision(
        self, identity: LectureReviewDecisionId
    ) -> "LectureReviewDecision | None":
        try:
            row = self._connection.execute(
                f"{_SELECT_DECISION_COLUMNS} WHERE identity = ?", (identity.value,)
            ).fetchone()
            return None if row is None else _restore_decision(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Lecture Review Decision: {error}"
            ) from error

    def get_approved_for_decision(
        self, identity: LectureReviewDecisionId
    ) -> "LectureApprovedEditDecision | None":
        """The at-most-one approved snapshot owned by this decision (`§7.4`, enforced by UNIQUE)."""

        try:
            row = self._connection.execute(
                f"{_SELECT_APPROVED_COLUMNS} WHERE review_decision_id = ?",
                (identity.value,),
            ).fetchone()
            return None if row is None else _restore_approved(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Lecture Approved Edit Decision: {error}"
            ) from error

    def get_approved(
        self, identity: LectureApprovedEditDecisionId
    ) -> "LectureApprovedEditDecision | None":
        try:
            row = self._connection.execute(
                f"{_SELECT_APPROVED_COLUMNS} WHERE identity = ?", (identity.value,)
            ).fetchone()
            return None if row is None else _restore_approved(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Lecture Approved Edit Decision: {error}"
            ) from error

    def list_decisions_for_candidate(
        self, candidate_id: LectureAnalysisEditCandidateId
    ) -> "tuple[LectureReviewDecision, ...]":
        """Deterministic presentation order by identity.

        This is a listing order, not a canonical ordinal: R-9 stores none, and the order says
        nothing about which coexisting judgment is currently operative.
        """

        try:
            rows = self._connection.execute(
                f"{_SELECT_DECISION_COLUMNS} WHERE candidate_id = ? ORDER BY identity",
                (candidate_id.value,),
            ).fetchall()
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not list Lecture Review Decisions: {error}"
            ) from error
        return tuple(_restore_decision(row) for row in rows)


class SQLiteLectureReviewCommandPersistence:
    """Owns one atomic v51 transaction appending an immutable Review admission."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_review(
        self,
        *,
        decision: "LectureReviewDecision",
        approved: "LectureApprovedEditDecision | None",
    ) -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(_UNAVAILABLE)
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            exists = self._connection.execute(
                "SELECT 1 FROM lecture_review_decisions WHERE identity = ?",
                (decision.identity.value,),
            ).fetchone()
            if exists is not None:
                raise PersistenceIdentityCollisionError(
                    "Lecture Review Decision identity already exists"
                )
            self._connection.execute(
                """
                INSERT INTO lecture_review_decisions(
                    identity, candidate_id, decision_kind, actor, review_contract_version
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    decision.identity.value,
                    decision.candidate_id.value,
                    decision.decision_kind.value,
                    decision.actor.value,
                    decision.review_contract_version,
                ),
            )
            if approved is not None:
                # Same transaction: accept and modify admit both records together or neither.
                self._connection.execute(
                    """
                    INSERT INTO lecture_approved_edit_decisions(
                        identity, review_decision_id, candidate_id, approved_decision_kind,
                        approved_range_start, approved_range_end, approved_label,
                        approved_rationale, approved_contract_version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        approved.identity.value,
                        approved.review_decision_id.value,
                        approved.candidate_id.value,
                        approved.approved_decision_kind.value,
                        approved.approved_range_start,
                        approved.approved_range_end,
                        approved.approved_label,
                        approved.approved_rationale,
                        approved.approved_contract_version,
                    ),
                )
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.IntegrityError as error:
            self._rollback(transaction_started)
            raise PersistenceIdentityCollisionError(
                f"Lecture Review record already exists: {error}"
            ) from error
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Lecture Review admission: {error}"
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


_SELECT_DECISION_COLUMNS = (
    "SELECT identity, candidate_id, decision_kind, actor, review_contract_version "
    "FROM lecture_review_decisions"
)

_SELECT_APPROVED_COLUMNS = (
    "SELECT identity, review_decision_id, candidate_id, approved_decision_kind, "
    "approved_range_start, approved_range_end, approved_label, approved_rationale, "
    "approved_contract_version "
    "FROM lecture_approved_edit_decisions"
)


def _restore_decision(row: tuple[object, ...]) -> "LectureReviewDecision":
    from lectureos.application.lecture_review_decision import (
        LectureReviewDecision,
        require_decision_kind,
    )

    return LectureReviewDecision(
        identity=LectureReviewDecisionId(row[0]),
        candidate_id=LectureAnalysisEditCandidateId(row[1]),
        decision_kind=require_decision_kind(row[2]),
        actor=HumanActorReference(row[3]),
        review_contract_version=row[4],
    )


def _restore_approved(row: tuple[object, ...]) -> "LectureApprovedEditDecision":
    from lectureos.application.lecture_review_decision import (
        LectureApprovedEditDecision,
        require_decision_kind,
    )

    return LectureApprovedEditDecision(
        identity=LectureApprovedEditDecisionId(row[0]),
        review_decision_id=LectureReviewDecisionId(row[1]),
        candidate_id=LectureAnalysisEditCandidateId(row[2]),
        approved_decision_kind=require_decision_kind(row[3]),
        approved_range_start=row[4],
        approved_range_end=row[5],
        approved_label=row[6],
        approved_rationale=row[7],
        approved_contract_version=row[8],
    )


__all__ = [
    "SQLiteLectureReviewCommandPersistence",
    "SQLiteLectureReviewRepository",
]
