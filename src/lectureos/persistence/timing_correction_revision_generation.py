"""Atomic SQLite persistence for Timing Correction revision generation (040 §19, PATCH-0047 TC-12).

Serializes one explicit timing-correction generation in a single transaction: the new replacement
`TranscriptSegment` (source text preserved exactly, accepted interval, ``replaces_segment_id``), the
canonical `CorrectedTranscriptRevision` (the released v5 revision tables, reused unchanged), its
`DomainResultReference`, and the additive `timing_correction_revision_generations` binding row. It
reuses the released transaction-free insert helpers so a timing-generated revision is structurally
identical to a text-generated one — which is what makes `§20` selection and every downstream boundary
correction-kind-agnostic. Any collision or error rolls back with no partial state; no candidate,
decision, raw transcript, segment, released generation row, or selection is ever touched.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from lectureos.application.identities import (
    TimingCorrectionCandidateDecisionId,
    TimingCorrectionCandidateId,
    TimingCorrectionRevisionGenerationId,
)
from lectureos.execution.models import DomainResultReference
from lectureos.transcript.identities import (
    TranscriptId,
    TranscriptRevisionId,
    TranscriptSegmentId,
)
from lectureos.transcript.models import CorrectedTranscriptRevision, TranscriptSegment

from .corrected_transcript_revisions import (
    SQLiteCorrectedTranscriptRevisionRepository,
    _insert_corrected_transcript_revision,
)
from .domain_results import _insert_domain_result_reference_record
from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection
from .transcript_segments import _insert_transcript_segment

if TYPE_CHECKING:
    from lectureos.application.timing_correction_revision_generation import (
        TimingCorrectionRevisionGeneration,
    )

_REQUIRED_VERSION = 54
_UNAVAILABLE = (
    "Timing Correction Revision Generation persistence requires SQLite schema version 54"
)
_AGGREGATE_REQUIRED_VERSION = 55
_AGGREGATE_UNAVAILABLE = (
    "Multi-candidate Timing Correction Revision Generation persistence requires SQLite schema "
    "version 55"
)

_AGGREGATE_SELECT = (
    "SELECT identity, corrected_revision_id, parent_raw_transcript_id, member_count, "
    "content_fingerprint FROM timing_correction_revision_aggregate_generations"
)
_MEMBER_SELECT = (
    "SELECT member_ordinal, timing_correction_candidate_id, authorizing_decision_id, "
    "replaced_segment_id, replacement_segment_id "
    "FROM timing_correction_revision_generation_members "
    "WHERE aggregate_generation_id = ? ORDER BY member_ordinal"
)

_REPLACEMENT_SELECT = (
    "SELECT transcript_id, source_timeline_id, text, source_order, start, end, "
    "speaker_label, confidence, uncertainty, replaces_segment_id "
    "FROM transcript_segments WHERE identity = ?"
)


def _expected_replacement_row(segment: TranscriptSegment) -> tuple[object, ...]:
    return (
        segment.transcript_id.value,
        segment.source_timeline_id.value if segment.source_timeline_id else None,
        segment.text,
        segment.source_order,
        segment.start,
        segment.end,
        segment.speaker_label,
        segment.confidence,
        segment.uncertainty,
        segment.replaces_segment_id.value if segment.replaces_segment_id else None,
    )

_SELECT_COLUMNS = (
    "SELECT identity, corrected_revision_id, timing_correction_candidate_id, "
    "authorizing_decision_id, parent_raw_transcript_id, replaced_segment_id, "
    "replacement_segment_id, content_fingerprint FROM timing_correction_revision_generations"
)


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(_UNAVAILABLE)
    return version


class SQLiteTimingCorrectionGenerationRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._schema_version = _require_version(connection)
        self._connection = connection

    def get(
        self, identity: TimingCorrectionRevisionGenerationId
    ) -> "TimingCorrectionRevisionGeneration | None":
        return self._one("identity", identity.value)

    def get_by_revision(
        self, revision_id: TranscriptRevisionId
    ) -> "TimingCorrectionRevisionGeneration | None":
        # Well-defined: the schema enforces UNIQUE(corrected_revision_id).
        return self._one("corrected_revision_id", revision_id.value)

    # -- normalised projection (legacy singleton rows are derived, never back-filled) ----------------

    def view(self, identity: TimingCorrectionRevisionGenerationId):
        """One generation read uniformly, whichever relation physically owns it (MG-21)."""

        from lectureos.application.timing_correction_revision_generation import (
            view_of_singleton,
        )

        singleton = self.get(identity)
        if singleton is not None:
            return view_of_singleton(singleton)
        return self._aggregate_view("identity", identity.value)

    def view_by_revision(self, revision_id: TranscriptRevisionId):
        from lectureos.application.timing_correction_revision_generation import (
            view_of_singleton,
        )

        singleton = self.get_by_revision(revision_id)
        if singleton is not None:
            return view_of_singleton(singleton)
        return self._aggregate_view("corrected_revision_id", revision_id.value)

    def _aggregate_view(self, column: str, value: str):
        if not self._aggregate_available():
            return None
        from lectureos.application.timing_correction_revision_generation import (
            TimingCorrectionRevisionAggregateGeneration,
            view_of_aggregate,
        )

        try:
            row = self._connection.execute(
                f"{_AGGREGATE_SELECT} WHERE {column} = ?", (value,)
            ).fetchone()
            if row is None:
                return None
            members = self._connection.execute(_MEMBER_SELECT, (row[0],)).fetchall()
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Timing Correction Revision Generation: {error}"
            ) from error
        if len(members) != row[3]:
            raise PersistenceError(
                "aggregate timing generation member count does not match its stored members"
            )
        return view_of_aggregate(
            TimingCorrectionRevisionAggregateGeneration(
                identity=TimingCorrectionRevisionGenerationId(row[0]),
                corrected_revision_id=TranscriptRevisionId(row[1]),
                parent_raw_transcript_id=TranscriptId(row[2]),
                members=tuple(_restore_member(member) for member in members),
                content_fingerprint=row[4],
            )
        )

    def _aggregate_available(self) -> bool:
        return self._schema_version >= _AGGREGATE_REQUIRED_VERSION

    def revision(
        self, revision_id: TranscriptRevisionId
    ) -> CorrectedTranscriptRevision | None:
        return SQLiteCorrectedTranscriptRevisionRepository(self._connection).get(revision_id)

    def candidate(self, candidate_id: TimingCorrectionCandidateId):
        """The timing candidate behind a generation — the lineage `§20` needs to find its intake."""

        from .timing_correction_candidate import SQLiteTimingCorrectionCandidateRepository

        return SQLiteTimingCorrectionCandidateRepository(self._connection).get(candidate_id)

    def generations_for_candidate(
        self, candidate_id: TimingCorrectionCandidateId
    ) -> tuple:
        """Every generation this candidate was actually applied by, at either cardinality.

        Participation is decided by persisted candidate identity and stored generation membership —
        never by a shared source segment, equal timing, equal replacement content, being part of the
        currently selected revision, or the candidate's current authority. A historical generation
        stays in this list after a later Reject or a current-Raw switch; those change applicability,
        not what was generated.

        Returns normalised `TimingCorrectionGenerationView`s: a released singleton row is derived as
        a one-member view (never back-filled) and an aggregate carries its **complete** membership.
        The queried candidate filters *which* generations appear; it never trims the other members
        out of one. Each generation appears exactly once, ordered by generation identity — the
        released singleton ordering, extended over both relations. That is a stable order, not a
        chronology.
        """

        from lectureos.application.timing_correction_revision_generation import (
            view_of_singleton,
        )

        try:
            rows = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE timing_correction_candidate_id = ? ORDER BY identity",
                (candidate_id.value,),
            ).fetchall()
            aggregate_ids = (
                [
                    row[0]
                    for row in self._connection.execute(
                        "SELECT DISTINCT aggregate_generation_id "
                        "FROM timing_correction_revision_generation_members "
                        "WHERE timing_correction_candidate_id = ? "
                        "ORDER BY aggregate_generation_id",
                        (candidate_id.value,),
                    ).fetchall()
                ]
                if self._aggregate_available()
                else []
            )
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not list Timing Correction Revision Generations: {error}"
            ) from error

        views = [view_of_singleton(_restore(row)) for row in rows]
        for identity in aggregate_ids:
            view = self._aggregate_view("identity", identity)
            if view is None:
                # The member row references a header that does not exist. That is repository
                # corruption, not an absent history entry; it is surfaced rather than skipped.
                raise PersistenceError(
                    "generation member references a missing aggregate generation: "
                    f"{identity}"
                )
            views.append(view)
        return tuple(sorted(views, key=lambda view: view.identity.value))

    def _one(
        self, column: str, value: str
    ) -> "TimingCorrectionRevisionGeneration | None":
        try:
            row = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE {column} = ?", (value,)
            ).fetchone()
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Timing Correction Revision Generation: {error}"
            ) from error
        return None if row is None else _restore(row)


class SQLiteTimingCorrectionGenerationCommandPersistence:
    """Owns one atomic v54 transaction persisting a complete timing-correction generation."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_timing_correction_generation(
        self,
        *,
        generation: "TimingCorrectionRevisionGeneration",
        revision: CorrectedTranscriptRevision,
        replacement_segment: TranscriptSegment,
        result: DomainResultReference,
        revalidate=None,
    ) -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(_UNAVAILABLE)
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            if revalidate is not None:
                # The caller's authority snapshot is re-derived INSIDE the write transaction, so the
                # guard cannot be overtaken between verification and persist (MG-13).
                revalidate()
            _validate_linkage(generation, revision, replacement_segment, result)
            if (
                self._exists("identity", generation.identity.value)
                or self._exists(
                    "corrected_revision_id", generation.corrected_revision_id.value
                )
                or self._revision_exists(revision.identity)
                or self._revision_owned_elsewhere(revision.identity)
            ):
                raise PersistenceIdentityCollisionError(
                    "Timing Correction Revision Generation records already exist"
                )
            self._write_replacement(replacement_segment)
            _insert_corrected_transcript_revision(self._connection, revision)
            _insert_domain_result_reference_record(self._connection, result)
            self._connection.execute(
                """
                INSERT INTO timing_correction_revision_generations(
                    identity, corrected_revision_id, timing_correction_candidate_id,
                    authorizing_decision_id, parent_raw_transcript_id,
                    replaced_segment_id, replacement_segment_id, content_fingerprint
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    generation.identity.value,
                    generation.corrected_revision_id.value,
                    generation.timing_correction_candidate_id.value,
                    generation.authorizing_decision_id.value,
                    generation.parent_raw_transcript_id.value,
                    generation.replaced_segment_id.value,
                    generation.replacement_segment_id.value,
                    generation.content_fingerprint,
                ),
            )
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.IntegrityError as error:
            self._rollback(transaction_started)
            raise PersistenceIdentityCollisionError(
                f"Timing Correction Revision Generation already exists: {error}"
            ) from error
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Timing Correction Revision Generation: {error}"
            ) from error
        except Exception:
            self._rollback(transaction_started)
            raise

    def persist_timing_correction_aggregate_generation(
        self,
        *,
        generation,
        revision: CorrectedTranscriptRevision,
        replacement_segments: tuple[TranscriptSegment, ...],
        result: DomainResultReference,
        revalidate=None,
    ) -> None:
        """One atomic v55 transaction for a two-or-more-member generation.

        Every new record — each new replacement segment, the revision and its ordered membership, the
        domain result, the aggregate header and its **complete** member provenance — commits together
        or not at all. Replacement segments that already exist are reused only after verification
        (MG-25); nothing existing is ever updated, deleted, or repaired.
        """

        if self._schema_version < _AGGREGATE_REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(_AGGREGATE_UNAVAILABLE)
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            if revalidate is not None:
                revalidate()
            _validate_aggregate_linkage(
                generation, revision, replacement_segments, result
            )
            if (
                self._aggregate_exists("identity", generation.identity.value)
                or self._aggregate_exists(
                    "corrected_revision_id", generation.corrected_revision_id.value
                )
                or self._exists("identity", generation.identity.value)
                or self._exists(
                    "corrected_revision_id", generation.corrected_revision_id.value
                )
                or self._revision_exists(revision.identity)
                or self._revision_owned_elsewhere(revision.identity)
            ):
                raise PersistenceIdentityCollisionError(
                    "Timing Correction Revision Generation records already exist"
                )
            for segment in replacement_segments:
                self._write_replacement(segment)
            _insert_corrected_transcript_revision(self._connection, revision)
            _insert_domain_result_reference_record(self._connection, result)
            self._connection.execute(
                """
                INSERT INTO timing_correction_revision_aggregate_generations(
                    identity, corrected_revision_id, parent_raw_transcript_id,
                    member_count, content_fingerprint
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    generation.identity.value,
                    generation.corrected_revision_id.value,
                    generation.parent_raw_transcript_id.value,
                    len(generation.members),
                    generation.content_fingerprint,
                ),
            )
            self._connection.executemany(
                """
                INSERT INTO timing_correction_revision_generation_members(
                    aggregate_generation_id, member_ordinal, timing_correction_candidate_id,
                    authorizing_decision_id, replaced_segment_id, replacement_segment_id
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        generation.identity.value,
                        member.member_ordinal,
                        member.timing_correction_candidate_id.value,
                        member.authorizing_decision_id.value,
                        member.replaced_segment_id.value,
                        member.replacement_segment_id.value,
                    )
                    for member in generation.members
                ],
            )
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.IntegrityError as error:
            self._rollback(transaction_started)
            raise PersistenceIdentityCollisionError(
                f"Timing Correction Revision Generation already exists: {error}"
            ) from error
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Timing Correction Revision Generation: {error}"
            ) from error
        except Exception:
            self._rollback(transaction_started)
            raise

    def _write_replacement(self, segment: TranscriptSegment) -> None:
        """Insert a new replacement, or reuse an existing one only after verifying it (MG-25).

        A replacement's identity is per-``(candidate, authorizing Decision)``, so the same member
        contributes the same entity to ``{A, B}``, to ``{A, C}``, and to A's legacy singleton. An
        existing entity whose canonical payload or source lineage differs is an integrity failure that
        refuses the whole generation — never an overwrite and never a silent reuse.
        """

        stored = self._connection.execute(
            _REPLACEMENT_SELECT, (segment.identity.value,)
        ).fetchone()
        if stored is None:
            _insert_transcript_segment(self._connection, segment)
            return
        if tuple(stored) != _expected_replacement_row(segment):
            raise PersistenceError(
                "an existing replacement segment does not match this generation's expected canonical "
                f"payload or source lineage ({segment.identity.value}): the whole generation is refused"
            )

    def _exists(self, column: str, value: str) -> bool:
        return (
            self._connection.execute(
                f"SELECT 1 FROM timing_correction_revision_generations WHERE {column} = ?",
                (value,),
            ).fetchone()
            is not None
        )

    def _aggregate_exists(self, column: str, value: str) -> bool:
        if self._schema_version < _AGGREGATE_REQUIRED_VERSION:
            return False
        return (
            self._connection.execute(
                "SELECT 1 FROM timing_correction_revision_aggregate_generations "
                f"WHERE {column} = ?",
                (value,),
            ).fetchone()
            is not None
        )

    def _revision_owned_elsewhere(self, identity: TranscriptRevisionId) -> bool:
        """A revision has exactly one canonical generation owner across every generation relation."""

        return (
            self._connection.execute(
                "SELECT 1 FROM corrected_revision_generations WHERE corrected_revision_id = ?",
                (identity.value,),
            ).fetchone()
            is not None
        )

    def _revision_exists(self, identity: TranscriptRevisionId) -> bool:
        return (
            self._connection.execute(
                "SELECT 1 FROM corrected_transcript_revisions WHERE identity = ?",
                (identity.value,),
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
    generation: "TimingCorrectionRevisionGeneration",
    revision: CorrectedTranscriptRevision,
    replacement_segment: TranscriptSegment,
    result: DomainResultReference,
) -> None:
    if generation.corrected_revision_id != revision.identity:
        raise PersistenceError("generation revision identity must match the revision")
    if revision.parent_raw_transcript_id != generation.parent_raw_transcript_id:
        raise PersistenceError("revision parent must match the generation parent")
    if revision.correction_candidate_ids != ():
        # A timing correction applies no text CorrectionCandidate; the released field stays empty
        # rather than being repurposed to carry a timing identity (TC-2).
        raise PersistenceError(
            "a timing-corrected revision must reference no text correction candidate"
        )
    if replacement_segment.identity != generation.replacement_segment_id:
        raise PersistenceError("replacement segment identity must match the generation")
    if replacement_segment.replaces_segment_id != generation.replaced_segment_id:
        raise PersistenceError(
            "replacement segment must replace the generation's replaced segment"
        )
    if replacement_segment.identity not in revision.segment_ids:
        raise PersistenceError("revision must reference the replacement segment")
    if generation.replaced_segment_id in revision.segment_ids:
        raise PersistenceError("revision must not still reference the replaced segment")
    if result.identity != revision.domain_result_id:
        raise PersistenceError("domain result identity must match the revision")
    if result.kind != "corrected_transcript_revision":
        raise PersistenceError("domain result kind must be corrected_transcript_revision")
    if len(result.upstream_results) != 1:
        raise PersistenceError("revision domain result requires exactly one upstream result")


def _validate_aggregate_linkage(
    generation,
    revision: CorrectedTranscriptRevision,
    replacement_segments: tuple[TranscriptSegment, ...],
    result: DomainResultReference,
) -> None:
    if generation.corrected_revision_id != revision.identity:
        raise PersistenceError("generation revision identity must match the revision")
    if revision.parent_raw_transcript_id != generation.parent_raw_transcript_id:
        raise PersistenceError("revision parent must match the generation parent")
    if revision.correction_candidate_ids != ():
        raise PersistenceError(
            "a timing-corrected revision must reference no text correction candidate"
        )
    if len(replacement_segments) != len(generation.members):
        raise PersistenceError(
            "an aggregate generation must carry one replacement segment per member"
        )
    supplied = {segment.identity: segment for segment in replacement_segments}
    for member in generation.members:
        segment = supplied.get(member.replacement_segment_id)
        if segment is None:
            raise PersistenceError(
                "a member's replacement segment was not supplied to the transaction"
            )
        if segment.replaces_segment_id != member.replaced_segment_id:
            raise PersistenceError(
                "replacement segment must replace the member's replaced segment"
            )
        if segment.identity not in revision.segment_ids:
            raise PersistenceError("revision must reference every replacement segment")
        if member.replaced_segment_id in revision.segment_ids:
            raise PersistenceError("revision must not still reference a replaced segment")
    if result.identity != revision.domain_result_id:
        raise PersistenceError("domain result identity must match the revision")
    if result.kind != "corrected_transcript_revision":
        raise PersistenceError("domain result kind must be corrected_transcript_revision")
    if len(result.upstream_results) != 1:
        raise PersistenceError("revision domain result requires exactly one upstream result")


def _restore_member(row: tuple[object, ...]):
    from lectureos.application.timing_correction_revision_generation import (
        TimingCorrectionGenerationMember,
    )

    return TimingCorrectionGenerationMember(
        member_ordinal=row[0],
        timing_correction_candidate_id=TimingCorrectionCandidateId(row[1]),
        authorizing_decision_id=TimingCorrectionCandidateDecisionId(row[2]),
        replaced_segment_id=TranscriptSegmentId(row[3]),
        replacement_segment_id=TranscriptSegmentId(row[4]),
    )


def _restore(row: tuple[object, ...]) -> "TimingCorrectionRevisionGeneration":
    from lectureos.application.timing_correction_revision_generation import (
        TimingCorrectionRevisionGeneration,
    )

    return TimingCorrectionRevisionGeneration(
        identity=TimingCorrectionRevisionGenerationId(row[0]),
        corrected_revision_id=TranscriptRevisionId(row[1]),
        timing_correction_candidate_id=TimingCorrectionCandidateId(row[2]),
        authorizing_decision_id=TimingCorrectionCandidateDecisionId(row[3]),
        parent_raw_transcript_id=TranscriptId(row[4]),
        replaced_segment_id=TranscriptSegmentId(row[5]),
        replacement_segment_id=TranscriptSegmentId(row[6]),
        content_fingerprint=row[7],
    )


__all__ = [
    "SQLiteTimingCorrectionGenerationCommandPersistence",
    "SQLiteTimingCorrectionGenerationRepository",
]
