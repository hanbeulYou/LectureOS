"""Read-only repository integrity checks.

``validate_repository`` runs a deterministic set of read-only checks over an open SQLite connection and returns
a :class:`ValidationReport`. ``validate_database`` opens a database read-only (``PRAGMA query_only = ON``) and
validates it, mapping open failures to diagnostics rather than exceptions. Nothing here mutates the database.

The checks cover: schema version compatibility; foreign-key integrity (SQLite-enforced references); dangling
non-foreign-key references (the many plain-TEXT references the schema does not enforce, e.g. review/candidate/
DomainResult ids); DomainResult lineage contiguity; the Edit Export Assembly invariants (non-empty, contiguous
and unique membership, single-timeline / single-media coherence, canonical member order); and the edit-export
provenance invariants (representation ↔ approved decision ↔ review decision kind and lineage consistency), plus
malformed identities. The validator is edit-export focused (the current MVP) but the framework is additive.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from lectureos.persistence.sqlite import _SUPPORTED_SCHEMA_VERSIONS

from .diagnostics import (
    Diagnostic,
    Severity,
    ValidationReport,
    build_report,
)

# Plain-TEXT references the schema does NOT enforce with a foreign key. Each is
# (table, column, target_table, source_locator_sql) where source_locator_sql yields a stable location string.
_NON_FK_REFERENCES = (
    ("approved_edit_export_representations", "domain_result_id", "domain_result_references", "t.identity"),
    ("approved_edit_export_representations", "source_review_decision_id", "edit_review_decisions", "t.identity"),
    ("approved_edit_export_representations", "source_candidate_id", "edit_candidates", "t.identity"),
    ("edit_export_assemblies", "domain_result_id", "domain_result_references", "t.identity"),
    ("approved_edit_decisions", "domain_result_id", "domain_result_references", "t.identity"),
    ("approved_edit_decisions", "source_candidate_id", "edit_candidates", "t.identity"),
    ("edit_review_decisions", "domain_result_id", "domain_result_references", "t.identity"),
    ("edit_review_decisions", "source_candidate_id", "edit_candidates", "t.identity"),
    ("edit_candidates", "domain_result_id", "domain_result_references", "t.identity"),
    (
        "domain_result_upstream_results",
        "upstream_domain_result_id",
        "domain_result_references",
        "t.domain_result_id || ':' || t.ordinal",
    ),
)

# Tables whose row counts contribute to "objects checked", and whose identity columns are checked for blanks.
_INSPECTED_TABLES = (
    "domain_result_references",
    "domain_result_upstream_results",
    "edit_candidates",
    "edit_review_decisions",
    "approved_edit_decisions",
    "approved_edit_export_representations",
    "edit_export_assemblies",
    "edit_export_assembly_members",
    "source_media",
    "transcript_source_intakes",
)
_IDENTITY_TABLES = (
    "domain_result_references",
    "edit_candidates",
    "edit_review_decisions",
    "approved_edit_decisions",
    "approved_edit_export_representations",
    "edit_export_assemblies",
    "source_media",
    "transcript_source_intakes",
)
_APPROVING_KINDS = ("accept", "modify")


def _table_exists(connection: sqlite3.Connection, name: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
        ).fetchone()
        is not None
    )


def _schema_version(connection: sqlite3.Connection) -> int | None:
    if not _table_exists(connection, "schema_metadata"):
        return None
    row = connection.execute(
        "SELECT version FROM schema_metadata WHERE singleton = 1"
    ).fetchone()
    return None if row is None else int(row[0])


def _check_foreign_keys(connection: sqlite3.Connection) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for table, rowid, parent, _fkid in connection.execute("PRAGMA foreign_key_check").fetchall():
        diagnostics.append(
            Diagnostic(
                code="FOREIGN_KEY_VIOLATION",
                severity=Severity.ERROR,
                location=f"{table}:rowid={rowid}",
                message=f"row in '{table}' references a missing row in '{parent}'",
            )
        )
    return diagnostics


def _check_non_fk_references(connection: sqlite3.Connection) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for table, column, target, locator in _NON_FK_REFERENCES:
        if not (_table_exists(connection, table) and _table_exists(connection, target)):
            continue
        rows = connection.execute(
            f"""
            SELECT ({locator}) AS location, t.{column} AS value
            FROM {table} t
            LEFT JOIN {target} r ON t.{column} = r.identity
            WHERE r.identity IS NULL
            ORDER BY location
            """
        ).fetchall()
        for location, value in rows:
            diagnostics.append(
                Diagnostic(
                    code="DANGLING_REFERENCE",
                    severity=Severity.ERROR,
                    location=f"{table}:{location}",
                    message=(
                        f"column '{column}' references missing {target} '{value}'"
                    ),
                )
            )
    return diagnostics


def _check_domain_result_lineage(connection: sqlite3.Connection) -> list[Diagnostic]:
    if not _table_exists(connection, "domain_result_upstream_results"):
        return []
    rows = connection.execute(
        """
        SELECT domain_result_id
        FROM domain_result_upstream_results
        GROUP BY domain_result_id
        HAVING COUNT(*) <> MAX(ordinal) + 1
            OR MIN(ordinal) <> 0
            OR COUNT(DISTINCT ordinal) <> COUNT(*)
        ORDER BY domain_result_id
        """
    ).fetchall()
    return [
        Diagnostic(
            code="DOMAIN_RESULT_UPSTREAM_NONCONTIGUOUS",
            severity=Severity.ERROR,
            location=f"domain_result_upstream_results:{domain_result_id}",
            message="DomainResult upstream ordinals are not a contiguous 0..n-1 sequence",
        )
        for (domain_result_id,) in rows
    ]


def _check_assemblies(connection: sqlite3.Connection) -> list[Diagnostic]:
    if not (
        _table_exists(connection, "edit_export_assemblies")
        and _table_exists(connection, "edit_export_assembly_members")
    ):
        return []
    diagnostics: list[Diagnostic] = []

    for (identity,) in connection.execute(
        """
        SELECT a.identity
        FROM edit_export_assemblies a
        LEFT JOIN edit_export_assembly_members m
            ON a.identity = m.edit_export_assembly_id
        GROUP BY a.identity
        HAVING COUNT(m.ordinal) = 0
        ORDER BY a.identity
        """
    ).fetchall():
        diagnostics.append(
            Diagnostic(
                code="ASSEMBLY_EMPTY",
                severity=Severity.ERROR,
                location=f"edit_export_assemblies:{identity}",
                message="assembly has no member representations",
            )
        )

    for (assembly_id,) in connection.execute(
        """
        SELECT edit_export_assembly_id
        FROM edit_export_assembly_members
        GROUP BY edit_export_assembly_id
        HAVING COUNT(*) <> MAX(ordinal) + 1
            OR MIN(ordinal) <> 0
            OR COUNT(DISTINCT ordinal) <> COUNT(*)
        ORDER BY edit_export_assembly_id
        """
    ).fetchall():
        diagnostics.append(
            Diagnostic(
                code="ASSEMBLY_MEMBER_ORDINAL_NONCONTIGUOUS",
                severity=Severity.ERROR,
                location=f"edit_export_assemblies:{assembly_id}",
                message="member ordinals are not a contiguous 0..n-1 sequence",
            )
        )

    for assembly_id, representation_id, count in connection.execute(
        """
        SELECT edit_export_assembly_id, source_representation_id, COUNT(*) AS c
        FROM edit_export_assembly_members
        GROUP BY edit_export_assembly_id, source_representation_id
        HAVING c > 1
        ORDER BY edit_export_assembly_id, source_representation_id
        """
    ).fetchall():
        diagnostics.append(
            Diagnostic(
                code="ASSEMBLY_MEMBER_DUPLICATE",
                severity=Severity.ERROR,
                location=f"edit_export_assemblies:{assembly_id}",
                message=f"member representation '{representation_id}' appears {count} times",
            )
        )

    if _table_exists(connection, "approved_edit_export_representations"):
        for assembly_id, representation_id, kind in connection.execute(
            """
            SELECT m.edit_export_assembly_id, m.source_representation_id,
                   CASE WHEN r.source_timeline_id <> a.source_timeline_id THEN 'timeline'
                        WHEN r.source_media_id <> a.source_media_id THEN 'media'
                        ELSE 'ok' END AS mismatch
            FROM edit_export_assembly_members m
            JOIN edit_export_assemblies a ON a.identity = m.edit_export_assembly_id
            JOIN approved_edit_export_representations r ON r.identity = m.source_representation_id
            WHERE r.source_timeline_id <> a.source_timeline_id
               OR r.source_media_id <> a.source_media_id
            ORDER BY m.edit_export_assembly_id, m.source_representation_id
            """
        ).fetchall():
            code = (
                "ASSEMBLY_MEMBER_TIMELINE_MISMATCH"
                if kind == "timeline"
                else "ASSEMBLY_MEMBER_MEDIA_MISMATCH"
            )
            diagnostics.append(
                Diagnostic(
                    code=code,
                    severity=Severity.ERROR,
                    location=f"edit_export_assemblies:{assembly_id}",
                    message=(
                        f"member representation '{representation_id}' belongs to a different "
                        f"source {kind} than the assembly"
                    ),
                )
            )

    # Canonical member order: ordinal order must equal ascending representation-identity order.
    members: dict[str, list[tuple[int, str]]] = {}
    for assembly_id, ordinal, representation_id in connection.execute(
        """
        SELECT edit_export_assembly_id, ordinal, source_representation_id
        FROM edit_export_assembly_members
        ORDER BY edit_export_assembly_id, ordinal
        """
    ).fetchall():
        members.setdefault(assembly_id, []).append((ordinal, representation_id))
    for assembly_id, entries in members.items():
        actual = [representation_id for _ordinal, representation_id in entries]
        if actual != sorted(actual):
            diagnostics.append(
                Diagnostic(
                    code="ASSEMBLY_MEMBER_ORDER_NONCANONICAL",
                    severity=Severity.WARNING,
                    location=f"edit_export_assemblies:{assembly_id}",
                    message="member order is not the canonical ascending identity order",
                )
            )
    return diagnostics


def _check_representation_provenance(connection: sqlite3.Connection) -> list[Diagnostic]:
    if not (
        _table_exists(connection, "approved_edit_export_representations")
        and _table_exists(connection, "approved_edit_decisions")
    ):
        return []
    diagnostics: list[Diagnostic] = []
    for row in connection.execute(
        """
        SELECT r.identity, r.decision_kind, r.source_review_decision_id, r.source_candidate_id,
               r.source_media_id, r.source_timeline_id,
               d.decision_kind, d.source_decision_id, d.source_candidate_id,
               d.source_media_id, d.source_timeline_id
        FROM approved_edit_export_representations r
        JOIN approved_edit_decisions d ON d.identity = r.source_approved_decision_id
        ORDER BY r.identity
        """
    ).fetchall():
        (
            identity, r_kind, r_review, r_candidate, r_media, r_timeline,
            d_kind, d_review, d_candidate, d_media, d_timeline,
        ) = row
        location = f"approved_edit_export_representations:{identity}"
        if r_kind != d_kind:
            diagnostics.append(
                Diagnostic(
                    code="REPRESENTATION_KIND_MISMATCH",
                    severity=Severity.ERROR,
                    location=location,
                    message=(
                        f"decision kind '{r_kind}' does not match its approved decision's '{d_kind}'"
                    ),
                )
            )
        if (
            r_review != d_review
            or r_candidate != d_candidate
            or r_media != d_media
            or r_timeline != d_timeline
        ):
            diagnostics.append(
                Diagnostic(
                    code="REPRESENTATION_PROVENANCE_MISMATCH",
                    severity=Severity.ERROR,
                    location=location,
                    message=(
                        "representation lineage (review/candidate/media/timeline) is inconsistent "
                        "with its approved decision"
                    ),
                )
            )
    return diagnostics


def _check_approved_decision_provenance(connection: sqlite3.Connection) -> list[Diagnostic]:
    if not (
        _table_exists(connection, "approved_edit_decisions")
        and _table_exists(connection, "edit_review_decisions")
    ):
        return []
    diagnostics: list[Diagnostic] = []
    for identity, d_kind, d_candidate, v_kind, v_candidate in connection.execute(
        """
        SELECT d.identity, d.decision_kind, d.source_candidate_id,
               v.decision_kind, v.source_candidate_id
        FROM approved_edit_decisions d
        JOIN edit_review_decisions v ON v.identity = d.source_decision_id
        ORDER BY d.identity
        """
    ).fetchall():
        location = f"approved_edit_decisions:{identity}"
        if v_kind not in _APPROVING_KINDS or d_kind != v_kind:
            diagnostics.append(
                Diagnostic(
                    code="APPROVED_DECISION_KIND_INVALID",
                    severity=Severity.ERROR,
                    location=location,
                    message=(
                        f"approving kind '{d_kind}' is inconsistent with its review decision kind "
                        f"'{v_kind}' (must be an approving accept/modify review)"
                    ),
                )
            )
        if d_candidate != v_candidate:
            diagnostics.append(
                Diagnostic(
                    code="APPROVED_DECISION_PROVENANCE_MISMATCH",
                    severity=Severity.ERROR,
                    location=location,
                    message="approved decision candidate does not match its review decision's candidate",
                )
            )
    return diagnostics


def _check_source_media(connection: sqlite3.Connection) -> list[Diagnostic]:
    if not _table_exists(connection, "source_media"):
        return []
    diagnostics: list[Diagnostic] = []

    # Malformed fingerprints: digest must be 64 lowercase hex characters; algorithm must be non-blank.
    for identity, digest in connection.execute(
        """
        SELECT identity, fingerprint_digest
        FROM source_media
        WHERE length(trim(fingerprint_algorithm)) = 0
            OR length(fingerprint_digest) <> 64
            OR fingerprint_digest <> lower(fingerprint_digest)
            OR fingerprint_digest GLOB '*[^0-9a-f]*'
        ORDER BY identity
        """
    ).fetchall():
        diagnostics.append(
            Diagnostic(
                code="MEDIA_FINGERPRINT_MALFORMED",
                severity=Severity.ERROR,
                location=f"source_media:{identity}",
                message=f"fingerprint digest '{digest}' is not 64 lowercase hex characters",
            )
        )

    # Identity must be derived from the content fingerprint (identity = '<algorithm>:<digest>').
    for (identity,) in connection.execute(
        """
        SELECT identity
        FROM source_media
        WHERE identity <> fingerprint_algorithm || ':' || fingerprint_digest
        ORDER BY identity
        """
    ).fetchall():
        diagnostics.append(
            Diagnostic(
                code="MEDIA_IDENTITY_FINGERPRINT_DISAGREEMENT",
                severity=Severity.ERROR,
                location=f"source_media:{identity}",
                message="identity is not derived from its content fingerprint",
            )
        )

    # Canonical uniqueness: no two Media records may share a content fingerprint.
    for algorithm, digest, count in connection.execute(
        """
        SELECT fingerprint_algorithm, fingerprint_digest, COUNT(*) AS c
        FROM source_media
        GROUP BY fingerprint_algorithm, fingerprint_digest
        HAVING c > 1
        ORDER BY fingerprint_algorithm, fingerprint_digest
        """
    ).fetchall():
        diagnostics.append(
            Diagnostic(
                code="MEDIA_FINGERPRINT_DUPLICATE",
                severity=Severity.ERROR,
                location=f"source_media:{algorithm}:{digest}",
                message=f"content fingerprint is shared by {count} Media records",
            )
        )
    return diagnostics


def _check_transcript_source_intake(connection: sqlite3.Connection) -> list[Diagnostic]:
    if not _table_exists(connection, "transcript_source_intakes"):
        return []
    diagnostics: list[Diagnostic] = []

    # A dangling source_media reference (also enforced by the foreign key, checked here for defense in depth).
    if _table_exists(connection, "source_media"):
        for (identity,) in connection.execute(
            """
            SELECT t.identity
            FROM transcript_source_intakes t
            LEFT JOIN source_media m ON t.source_media_id = m.identity
            WHERE m.identity IS NULL
            ORDER BY t.identity
            """
        ).fetchall():
            diagnostics.append(
                Diagnostic(
                    code="TRANSCRIPT_INTAKE_DANGLING_SOURCE_MEDIA",
                    severity=Severity.ERROR,
                    location=f"transcript_source_intakes:{identity}",
                    message="intake references a missing source_media record",
                )
            )

    # Identity must be derived from the confirmed Source Media (identity = 'transcript-source-intake:<id>').
    for (identity,) in connection.execute(
        """
        SELECT identity
        FROM transcript_source_intakes
        WHERE identity <> 'transcript-source-intake:' || source_media_id
        ORDER BY identity
        """
    ).fetchall():
        diagnostics.append(
            Diagnostic(
                code="TRANSCRIPT_INTAKE_IDENTITY_DISAGREEMENT",
                severity=Severity.ERROR,
                location=f"transcript_source_intakes:{identity}",
                message="intake identity is not derived from its Source Media reference",
            )
        )

    # Canonical uniqueness: at most one transcript intake per Source Media.
    for source_media_id, count in connection.execute(
        """
        SELECT source_media_id, COUNT(*) AS c
        FROM transcript_source_intakes
        GROUP BY source_media_id
        HAVING c > 1
        ORDER BY source_media_id
        """
    ).fetchall():
        diagnostics.append(
            Diagnostic(
                code="TRANSCRIPT_INTAKE_DUPLICATE",
                severity=Severity.ERROR,
                location=f"transcript_source_intakes:{source_media_id}",
                message=f"source media is admitted by {count} transcript intakes",
            )
        )
    return diagnostics


def _check_malformed_identities(connection: sqlite3.Connection) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for table in _IDENTITY_TABLES:
        if not _table_exists(connection, table):
            continue
        count = connection.execute(
            f"SELECT COUNT(*) FROM {table} WHERE identity IS NULL OR length(trim(identity)) = 0"
        ).fetchone()[0]
        if count:
            diagnostics.append(
                Diagnostic(
                    code="MALFORMED_IDENTITY",
                    severity=Severity.ERROR,
                    location=f"{table}.identity",
                    message=f"{count} row(s) have an empty or blank identity",
                )
            )
    return diagnostics


def _objects_checked(connection: sqlite3.Connection) -> int:
    total = 0
    for table in _INSPECTED_TABLES:
        if _table_exists(connection, table):
            total += connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    return total


def validate_repository(connection: sqlite3.Connection) -> ValidationReport:
    """Run all read-only integrity checks against an open connection and return a report."""

    version = _schema_version(connection)
    if version is None:
        return build_report(
            schema_version=None,
            objects_checked=0,
            diagnostics=[
                Diagnostic(
                    code="SCHEMA_METADATA_MISSING",
                    severity=Severity.ERROR,
                    location="schema_metadata",
                    message="database has no schema_metadata; not a LectureOS repository",
                )
            ],
        )

    diagnostics: list[Diagnostic] = []
    if version not in _SUPPORTED_SCHEMA_VERSIONS:
        diagnostics.append(
            Diagnostic(
                code="SCHEMA_VERSION_UNSUPPORTED",
                severity=Severity.ERROR,
                location="schema_metadata",
                message=(
                    f"schema version {version} is not supported by this build "
                    f"(supported: {min(_SUPPORTED_SCHEMA_VERSIONS)}..{max(_SUPPORTED_SCHEMA_VERSIONS)})"
                ),
            )
        )

    diagnostics += _check_foreign_keys(connection)
    diagnostics += _check_non_fk_references(connection)
    diagnostics += _check_domain_result_lineage(connection)
    diagnostics += _check_assemblies(connection)
    diagnostics += _check_representation_provenance(connection)
    diagnostics += _check_approved_decision_provenance(connection)
    diagnostics += _check_source_media(connection)
    diagnostics += _check_transcript_source_intake(connection)
    diagnostics += _check_malformed_identities(connection)

    return build_report(
        schema_version=version,
        objects_checked=_objects_checked(connection),
        diagnostics=diagnostics,
    )


def validate_database(database_path: str) -> ValidationReport:
    """Open a database read-only and validate it, mapping open failures to diagnostics."""

    path = Path(database_path)
    if not path.exists() or not path.is_file():
        return build_report(
            schema_version=None,
            objects_checked=0,
            diagnostics=[
                Diagnostic(
                    code="DATABASE_NOT_FOUND",
                    severity=Severity.ERROR,
                    location=str(database_path),
                    message="database file does not exist",
                )
            ],
        )
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(str(path))
        connection.execute("PRAGMA query_only = ON")
        return validate_repository(connection)
    except sqlite3.Error as error:
        return build_report(
            schema_version=None,
            objects_checked=0,
            diagnostics=[
                Diagnostic(
                    code="DATABASE_UNREADABLE",
                    severity=Severity.ERROR,
                    location=str(database_path),
                    message=f"database could not be read: {error}",
                )
            ],
        )
    finally:
        if connection is not None:
            connection.close()


__all__ = ["validate_database", "validate_repository"]
