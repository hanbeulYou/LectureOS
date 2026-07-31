"""Append-only SQLite persistence for the Edit Export Assembly (044 §23, GOAL-030).

Serializes one immutable `LectureEditExportAssembly` and its ordered membership in a **single atomic
transaction**: all rows or none. Rows are never updated or deleted — a genuinely different scope is a
new immutable Assembly, and an identical re-admission converges on the stored one at the Application
layer before reaching here (EA-10).

**No execution provenance exists to store (EA-8).** Neither relation carries a `domain_result_id`,
`processing_run_id`, `unit_execution_id`, per-admission ordinal, wall clock, status, currentness, or
selection column. `043 §7.5` R-6 removed the first three from this generation and EA-8 carries that
forward to Export; R-4/AH-8 and EA-7 keep currentness derived rather than stored.

**The legacy Export family is never read or written.** `edit_export_representations`,
`edit_export_assemblies`, and `edit_export_assembly_members` belong to the legacy
execution-coupled generation (`044 §19`–`§22`), and EA-10 keeps this generation out of them: those
relations require the legacy anchors and execution provenance that EA-8 prohibits fabricating.

The scope query is a pure lineage walk. It resolves which Edit Candidates belong to one Source
Timeline through the released anchor chain (`043 §7.5` R-7, EA-8) and stops there: **eligibility is
not evaluated in SQL.** Which of those Candidates contributes a member is an Application decision
computed from the released Review services, so that Persistence never owns the derivation.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from lectureos.application.identities import (
    LectureAnalysisEditCandidateId,
    LectureEditExportAssemblyId,
)
from lectureos.execution.identities import SourceTimelineId

from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection

if TYPE_CHECKING:
    from lectureos.application.lecture_edit_export_assembly import (
        LectureEditExportAssembly,
        LectureEditExportAssemblyMember,
    )

_REQUIRED_VERSION = 53

_UNAVAILABLE = "Lecture Edit Export Assembly persistence requires SQLite schema version 53"

_SELECT_ASSEMBLY_COLUMNS = (
    "SELECT identity, source_timeline_id, assembly_contract_version "
    "FROM lecture_edit_export_assemblies"
)

_SELECT_MEMBER_COLUMNS = (
    "SELECT assembly_id, ordinal, approved_edit_decision_id "
    "FROM lecture_edit_export_assembly_members"
)

_CANDIDATES_FOR_TIMELINE = """
SELECT DISTINCT candidate.identity
FROM lecture_analysis_edit_candidates AS candidate
JOIN lecture_analysis_findings AS finding
    ON finding.identity = candidate.finding_id
JOIN lecture_analysis_input_admissions AS admission
    ON admission.identity = finding.admission_id
JOIN raw_transcripts AS raw
    ON raw.identity = admission.parent_raw_transcript_id
WHERE raw.source_timeline_id = ?
ORDER BY candidate.identity
"""


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(_UNAVAILABLE)
    return version


class SQLiteEditExportScopeRepository:
    """Resolves which Edit Candidates belong to one Source Timeline — lineage only."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def candidate_ids_for_source_timeline(
        self, source_timeline_id: SourceTimelineId
    ) -> tuple[LectureAnalysisEditCandidateId, ...]:
        """Walk `Candidate → Finding → Admission → parent Raw Transcript → Source Timeline`.

        This is `043 §7.5` R-7's anchor chain read in the reverse direction, which is why no Source
        Timeline column exists on any of this generation's records (EA-8: provenance is inherited
        through the anchor, never duplicated). The order is by identity — deterministic presentation,
        never a ranking or an execution order.

        Returns every Candidate on the timeline regardless of eligibility: deciding which ones
        contribute a member is the Application's derivation, not this query's.
        """

        try:
            rows = self._connection.execute(
                _CANDIDATES_FOR_TIMELINE, (source_timeline_id.value,)
            ).fetchall()
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not list edit candidates for the Source Timeline: {error}"
            ) from error
        return tuple(LectureAnalysisEditCandidateId(row[0]) for row in rows)


class SQLiteEditExportAssemblyRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get_assembly(
        self, identity: LectureEditExportAssemblyId
    ) -> "LectureEditExportAssembly | None":
        try:
            row = self._connection.execute(
                f"{_SELECT_ASSEMBLY_COLUMNS} WHERE identity = ?", (identity.value,)
            ).fetchone()
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Lecture Edit Export Assembly: {error}"
            ) from error
        if row is None:
            return None
        return self._restore(row)

    def list_members(
        self, identity: LectureEditExportAssemblyId
    ) -> "tuple[LectureEditExportAssemblyMember, ...]":
        from lectureos.application.lecture_edit_export_assembly import (
            LectureEditExportAssemblyMember,
        )
        from lectureos.application.identities import LectureApprovedEditDecisionId

        try:
            rows = self._connection.execute(
                f"{_SELECT_MEMBER_COLUMNS} WHERE assembly_id = ? ORDER BY ordinal",
                (identity.value,),
            ).fetchall()
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not list Lecture Edit Export Assembly members: {error}"
            ) from error
        return tuple(
            LectureEditExportAssemblyMember(
                assembly_id=LectureEditExportAssemblyId(row[0]),
                ordinal=int(row[1]),
                approved_edit_decision_id=LectureApprovedEditDecisionId(row[2]),
            )
            for row in rows
        )

    def list_assemblies_for_timeline(
        self, source_timeline_id: SourceTimelineId
    ) -> "tuple[LectureEditExportAssembly, ...]":
        """Every Assembly recorded for one timeline, ordered by identity.

        Several may exist: membership is derived and total, so an upstream authority change
        legitimately makes a *new* Assembly gather a different set. Each is an immutable record of
        what was eligible when it was admitted; none supersedes or rewrites another, and this
        contract defines no currentness among them.
        """

        try:
            rows = self._connection.execute(
                f"{_SELECT_ASSEMBLY_COLUMNS} WHERE source_timeline_id = ? ORDER BY identity",
                (source_timeline_id.value,),
            ).fetchall()
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not list Lecture Edit Export Assemblies: {error}"
            ) from error
        return tuple(self._restore(row) for row in rows)

    def _restore(self, row: tuple[object, ...]) -> "LectureEditExportAssembly":
        from lectureos.application.lecture_edit_export_assembly import (
            LectureEditExportAssembly,
        )

        identity = LectureEditExportAssemblyId(str(row[0]))
        return LectureEditExportAssembly(
            identity=identity,
            source_timeline_id=SourceTimelineId(str(row[1])),
            members=self.list_members(identity),
            assembly_contract_version=int(row[2]),
        )


class SQLiteEditExportAssemblyCommandPersistence:
    """Owns one atomic v53 transaction appending an immutable Assembly and its membership."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(_UNAVAILABLE)

    def persist_assembly(self, assembly: "LectureEditExportAssembly") -> None:
        """All-or-nothing: the Assembly and every member row share one `BEGIN IMMEDIATE`.

        A partially recorded Assembly must never look valid — an Assembly missing members would
        misrepresent the approved scope as smaller than it was.
        """

        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            self._connection.execute(
                "INSERT INTO lecture_edit_export_assemblies("
                "identity, source_timeline_id, assembly_contract_version) "
                "VALUES (?, ?, ?)",
                (
                    assembly.identity.value,
                    assembly.source_timeline_id.value,
                    assembly.assembly_contract_version,
                ),
            )
            for member in assembly.members:
                self._connection.execute(
                    "INSERT INTO lecture_edit_export_assembly_members("
                    "assembly_id, ordinal, approved_edit_decision_id) VALUES (?, ?, ?)",
                    (
                        member.assembly_id.value,
                        member.ordinal,
                        member.approved_edit_decision_id.value,
                    ),
                )
            self._connection.commit()
        except sqlite3.IntegrityError as error:
            self._rollback(transaction_started)
            raise PersistenceIdentityCollisionError(
                f"lecture edit export assembly already exists or violates integrity: {error}"
            ) from error
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Lecture Edit Export Assembly: {error}"
            ) from error
        except Exception:
            self._rollback(transaction_started)
            raise

    def _rollback(self, transaction_started: bool) -> None:
        if not transaction_started:
            return
        try:
            self._connection.rollback()
        except sqlite3.Error:  # pragma: no cover - rollback failure surfaces the original error
            pass


__all__ = [
    "SQLiteEditExportAssemblyCommandPersistence",
    "SQLiteEditExportAssemblyRepository",
    "SQLiteEditExportScopeRepository",
]
