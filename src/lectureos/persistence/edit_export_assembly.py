"""Insert-only SQLite persistence for the Edit-Pipeline Export Assembly Application Foundation (044 §20).

Serializes one immutable Edit Export Assembly, its ordered membership snapshot, and its multi-upstream
DomainResultReference in a single atomic transaction. The Assembly is a deterministic aggregate of an
explicitly supplied set of canonical Approved Edit Export Representations; persisting it records only the
coherent grouping and starts no downstream capability. Membership is stored in canonical identity order and
reconstructed by that order.
"""

from __future__ import annotations

import sqlite3

from lectureos.application.edit_export_assembly import (
    EDIT_EXPORT_ASSEMBLY_RESULT_KIND,
    EditExportAssembly,
    PreparedEditExportAssembly,
)
from lectureos.application.identities import (
    ApprovedEditExportRepresentationId,
    EditExportAssemblyId,
)
from lectureos.execution.identities import (
    DomainResultId,
    ProcessingRunId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
)

from .domain_results import _insert_domain_result_reference_record
from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection

_REQUIRED_VERSION = 29


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(
            "Edit Export Assembly persistence requires SQLite schema version 29"
        )
    return version


class SQLiteEditExportAssemblyRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(self, identity: EditExportAssemblyId) -> EditExportAssembly | None:
        try:
            row = self._connection.execute(
                """
                SELECT identity, domain_result_id, source_media_id, source_timeline_id,
                       processing_run_id, unit_execution_id
                FROM edit_export_assemblies
                WHERE identity = ?
                """,
                (identity.value,),
            ).fetchone()
            if row is None:
                return None
            member_ids = self._member_ids(identity)
            return _restore(row, member_ids)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Edit Export Assembly: {error}"
            ) from error

    def _member_ids(
        self, identity: EditExportAssemblyId
    ) -> tuple[ApprovedEditExportRepresentationId, ...]:
        rows = self._connection.execute(
            """
            SELECT ordinal, source_representation_id
            FROM edit_export_assembly_members
            WHERE edit_export_assembly_id = ?
            ORDER BY ordinal
            """,
            (identity.value,),
        ).fetchall()
        if tuple(row[0] for row in rows) != tuple(range(len(rows))):
            raise PersistenceError("Edit Export Assembly membership ordering is corrupt")
        return tuple(ApprovedEditExportRepresentationId(row[1]) for row in rows)


class SQLiteEditExportAssemblyCommandPersistence:
    """Owns one atomic v29 transaction persisting an Assembly, its membership, and its Result reference."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_edit_export_assembly(
        self, *, prepared: PreparedEditExportAssembly
    ) -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(
                "Edit Export Assembly persistence requires SQLite schema version 29"
            )
        _validate_assembly_linkage(prepared)
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            if self._exists(
                "edit_export_assemblies", prepared.assembly.identity.value
            ):
                raise PersistenceIdentityCollisionError(
                    "Edit Export Assembly identity already exists"
                )
            if self._exists(
                "domain_result_references", prepared.assembly_result.identity.value
            ):
                raise PersistenceIdentityCollisionError(
                    "Edit Export Assembly Domain Result identity already exists"
                )
            _insert_assembly(self._connection, prepared.assembly)
            for ordinal, member_id in enumerate(
                prepared.assembly.member_representation_ids
            ):
                _insert_member(self._connection, prepared.assembly, ordinal, member_id)
            _insert_domain_result_reference_record(
                self._connection, prepared.assembly_result
            )
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Edit Export Assembly: {error}"
            ) from error
        except Exception:
            self._rollback(transaction_started)
            raise

    def _exists(self, table: str, identity_value: str) -> bool:
        return (
            self._connection.execute(
                f"SELECT 1 FROM {table} WHERE identity = ?",
                (identity_value,),
            ).fetchone()
            is not None
        )

    def _rollback(self, transaction_started: bool) -> None:
        if transaction_started and self._connection.in_transaction:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass


def _validate_assembly_linkage(prepared: PreparedEditExportAssembly) -> None:
    assembly = prepared.assembly
    result = prepared.assembly_result
    if assembly.domain_result_id != result.identity:
        raise PersistenceError("Edit Export Assembly Domain Result identity mismatch")
    if result.kind != EDIT_EXPORT_ASSEMBLY_RESULT_KIND:
        raise PersistenceError("Edit Export Assembly Domain Result kind is invalid")
    members = assembly.member_representation_ids
    if not members:
        raise PersistenceError("Edit Export Assembly must have at least one member")
    # Multi-upstream lineage: exactly one direct upstream per member representation (set by the service).
    if len(result.upstream_results) != len(members):
        raise PersistenceError("Edit Export Assembly Domain Result upstream is invalid")
    if len(set(result.upstream_results)) != len(result.upstream_results):
        raise PersistenceError("Edit Export Assembly Domain Result upstream is not unique")


def _restore(
    row: tuple[object, ...],
    member_ids: tuple[ApprovedEditExportRepresentationId, ...],
) -> EditExportAssembly:
    return EditExportAssembly(
        identity=EditExportAssemblyId(row[0]),
        domain_result_id=DomainResultId(row[1]),
        source_media_id=SourceMediaId(row[2]),
        source_timeline_id=SourceTimelineId(row[3]),
        member_representation_ids=member_ids,
        run_id=ProcessingRunId(row[4]),
        unit_execution_id=UnitExecutionId(row[5]),
    )


def _insert_assembly(
    connection: sqlite3.Connection, record: EditExportAssembly
) -> None:
    connection.execute(
        """
        INSERT INTO edit_export_assemblies(
            identity, domain_result_id, source_media_id, source_timeline_id,
            processing_run_id, unit_execution_id
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            record.identity.value,
            record.domain_result_id.value,
            record.source_media_id.value,
            record.source_timeline_id.value,
            record.run_id.value,
            record.unit_execution_id.value,
        ),
    )


def _insert_member(
    connection: sqlite3.Connection,
    assembly: EditExportAssembly,
    ordinal: int,
    member_id: ApprovedEditExportRepresentationId,
) -> None:
    connection.execute(
        """
        INSERT INTO edit_export_assembly_members(
            edit_export_assembly_id, ordinal, source_representation_id
        ) VALUES (?, ?, ?)
        """,
        (assembly.identity.value, ordinal, member_id.value),
    )


__all__ = [
    "SQLiteEditExportAssemblyCommandPersistence",
    "SQLiteEditExportAssemblyRepository",
]
