"""Atomic SQLite persistence for Same-Source Text + Timing Composition (040 §19 `PATCH-0050`).

Serializes one explicit pair composition in a single transaction: the new composed replacement
`TranscriptSegment` (text from the text candidate, interval from the timing candidate,
``replaces_segment_id`` to the original source), the canonical `CorrectedTranscriptRevision` (the
released v5 revision tables, reused unchanged), its `DomainResultReference`, and the additive
``same_source_composition_generations`` row that is the **single canonical owner** of the two-role
provenance (TX-18/TX-21). It reuses the released transaction-free insert helpers so a composed
revision is structurally identical to any other and `§20` stays correction-kind-agnostic.

Revision ownership is single across all **four** generation kinds: the write refuses a revision
already owned by the text, timing singleton, or timing aggregate relation, and those relations'
writers refuse a revision owned here (TX-21). Any collision or error rolls back with no partial
state; no candidate, Decision, Raw selection, sibling revision, or shared replacement is touched.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from lectureos.application.identities import (
    CorrectionCandidateDecisionId,
    SameSourceCompositionGenerationId,
    TimingCorrectionCandidateDecisionId,
    TimingCorrectionCandidateId,
)
from lectureos.execution.models import DomainResultReference
from lectureos.transcript.identities import (
    CorrectionCandidateId,
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
    from lectureos.application.same_source_composition_generation import (
        SameSourceCompositionGeneration,
    )

REQUIRED_VERSION = 56
_UNAVAILABLE = (
    "Same-Source Text + Timing Composition persistence requires SQLite schema version 56"
)

TABLE = "same_source_composition_generations"

_SELECT_COLUMNS = (
    "SELECT identity, corrected_revision_id, parent_raw_transcript_id, replaced_segment_id, "
    "text_correction_candidate_id, text_authorizing_decision_id, "
    "timing_correction_candidate_id, timing_authorizing_decision_id, "
    f"replacement_segment_id, content_fingerprint FROM {TABLE}"
)

_REPLACEMENT_SELECT = (
    "SELECT transcript_id, source_timeline_id, text, source_order, start, end, "
    "speaker_label, confidence, uncertainty, replaces_segment_id "
    "FROM transcript_segments WHERE identity = ?"
)

# Every other relation that may own a revision (TX-21). Each is consulted only when present.
OTHER_OWNER_RELATIONS = (
    "corrected_revision_generations",
    "timing_correction_revision_generations",
    "timing_correction_revision_aggregate_generations",
)


def composition_available(connection: sqlite3.Connection, schema_version: int) -> bool:
    return schema_version >= REQUIRED_VERSION


def revision_owned_by_composition(
    connection: sqlite3.Connection, revision_id: TranscriptRevisionId
) -> bool:
    """Whether the composition relation owns this revision — safe to call on any schema version."""

    if (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (TABLE,)
        ).fetchone()
        is None
    ):
        return False
    return (
        connection.execute(
            f"SELECT 1 FROM {TABLE} WHERE corrected_revision_id = ?", (revision_id.value,)
        ).fetchone()
        is not None
    )


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(_UNAVAILABLE)
    return version


class SQLiteSameSourceCompositionRepository:
    """Read side of the composition relation, plus the revision reader `§20` and history need."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._schema_version = validate_sqlite_connection(connection)
        self._connection = connection

    def _available(self) -> bool:
        return self._schema_version >= REQUIRED_VERSION

    def get(
        self, identity: SameSourceCompositionGenerationId
    ) -> "SameSourceCompositionGeneration | None":
        return self._one("identity", identity.value)

    def get_by_revision(
        self, revision_id: TranscriptRevisionId
    ) -> "SameSourceCompositionGeneration | None":
        # Well-defined: the schema enforces UNIQUE(corrected_revision_id).
        return self._one("corrected_revision_id", revision_id.value)

    def revision(self, revision_id: TranscriptRevisionId) -> CorrectedTranscriptRevision | None:
        return SQLiteCorrectedTranscriptRevisionRepository(self._connection).get(revision_id)

    def generations_for_text_candidate(
        self, candidate_id: CorrectionCandidateId
    ) -> "tuple[SameSourceCompositionGeneration, ...]":
        return self._many("text_correction_candidate_id", candidate_id.value)

    def generations_for_timing_candidate(
        self, candidate_id: TimingCorrectionCandidateId
    ) -> "tuple[SameSourceCompositionGeneration, ...]":
        return self._many("timing_correction_candidate_id", candidate_id.value)

    def _one(self, column: str, value: str):
        if not self._available():
            return None
        try:
            row = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE {column} = ?", (value,)
            ).fetchone()
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Same-Source Composition Generation: {error}"
            ) from error
        return None if row is None else _restore(row)

    def _many(self, column: str, value: str) -> tuple:
        if not self._available():
            return ()
        try:
            rows = self._connection.execute(
                f"{_SELECT_COLUMNS} WHERE {column} = ? ORDER BY identity", (value,)
            ).fetchall()
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not list Same-Source Composition Generations: {error}"
            ) from error
        return tuple(_restore(row) for row in rows)


class SQLiteSameSourceCompositionCommandPersistence:
    """Owns one atomic v56 transaction persisting a complete same-source composition."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_same_source_composition(
        self,
        *,
        generation: "SameSourceCompositionGeneration",
        revision: CorrectedTranscriptRevision,
        replacement_segment: TranscriptSegment,
        result: DomainResultReference,
        revalidate=None,
    ) -> None:
        if self._schema_version < REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(_UNAVAILABLE)
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            if revalidate is not None:
                # The caller's authority snapshot is re-derived INSIDE the write transaction, so the
                # guard cannot be overtaken between verification and persist (TX-24).
                revalidate()
            _validate_linkage(generation, revision, replacement_segment, result)
            if (
                self._exists("identity", generation.identity.value)
                or self._exists("corrected_revision_id", generation.corrected_revision_id.value)
                or self._exists("replacement_segment_id", generation.replacement_segment_id.value)
                or self._anchor_exists(generation)
                or self._revision_exists(revision.identity)
                or self._revision_owned_elsewhere(revision.identity)
            ):
                raise PersistenceIdentityCollisionError(
                    "Same-Source Composition Generation records already exist"
                )
            self._write_replacement(replacement_segment)
            _insert_corrected_transcript_revision(self._connection, revision)
            _insert_domain_result_reference_record(self._connection, result)
            self._connection.execute(
                f"""
                INSERT INTO {TABLE}(
                    identity, corrected_revision_id, parent_raw_transcript_id, replaced_segment_id,
                    text_correction_candidate_id, text_authorizing_decision_id,
                    timing_correction_candidate_id, timing_authorizing_decision_id,
                    replacement_segment_id, content_fingerprint
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    generation.identity.value,
                    generation.corrected_revision_id.value,
                    generation.parent_raw_transcript_id.value,
                    generation.replaced_segment_id.value,
                    generation.text_correction_candidate_id.value,
                    generation.text_authorizing_decision_id.value,
                    generation.timing_correction_candidate_id.value,
                    generation.timing_authorizing_decision_id.value,
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
                f"Same-Source Composition Generation already exists: {error}"
            ) from error
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Same-Source Composition Generation: {error}"
            ) from error
        except Exception:
            self._rollback(transaction_started)
            raise

    def _write_replacement(self, segment: TranscriptSegment) -> None:
        """Insert the composed replacement, or reuse an identical one only after verification.

        The composed replacement is pair-dependent and its identity is unique to this anchor
        (TX-16), so an existing row can only be the same anchor's earlier write. It is reused only
        when its complete canonical payload and lineage match; a mismatch refuses the generation.
        """

        stored = self._connection.execute(
            _REPLACEMENT_SELECT, (segment.identity.value,)
        ).fetchone()
        if stored is None:
            _insert_transcript_segment(self._connection, segment)
            return
        if tuple(stored) != _expected_replacement_row(segment):
            raise PersistenceError(
                "an existing composed replacement segment does not match this composition's expected "
                f"canonical payload or source lineage ({segment.identity.value}): the whole "
                "generation is refused"
            )

    def _exists(self, column: str, value: str) -> bool:
        return (
            self._connection.execute(
                f"SELECT 1 FROM {TABLE} WHERE {column} = ?", (value,)
            ).fetchone()
            is not None
        )

    def _anchor_exists(self, generation) -> bool:
        return (
            self._connection.execute(
                f"SELECT 1 FROM {TABLE} WHERE text_correction_candidate_id = ? "
                "AND text_authorizing_decision_id = ? AND timing_correction_candidate_id = ? "
                "AND timing_authorizing_decision_id = ?",
                (
                    generation.text_correction_candidate_id.value,
                    generation.text_authorizing_decision_id.value,
                    generation.timing_correction_candidate_id.value,
                    generation.timing_authorizing_decision_id.value,
                ),
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

    def _revision_owned_elsewhere(self, identity: TranscriptRevisionId) -> bool:
        """A revision has exactly one canonical generation owner across every generation kind."""

        for relation in OTHER_OWNER_RELATIONS:
            if (
                self._connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (relation,)
                ).fetchone()
                is None
            ):
                continue
            if (
                self._connection.execute(
                    f"SELECT 1 FROM {relation} WHERE corrected_revision_id = ?",
                    (identity.value,),
                ).fetchone()
                is not None
            ):
                return True
        return False

    def _rollback(self, transaction_started: bool) -> None:
        if transaction_started and self._connection.in_transaction:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass


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


def _validate_linkage(
    generation: "SameSourceCompositionGeneration",
    revision: CorrectedTranscriptRevision,
    replacement_segment: TranscriptSegment,
    result: DomainResultReference,
) -> None:
    if generation.corrected_revision_id != revision.identity:
        raise PersistenceError("generation revision identity must match the revision")
    if revision.parent_raw_transcript_id != generation.parent_raw_transcript_id:
        raise PersistenceError("revision parent must match the generation parent")
    if revision.correction_candidate_ids != (generation.text_correction_candidate_id,):
        # The released text-only field carries exactly the applied text candidate (TX-19).
        raise PersistenceError(
            "a composed revision must reference exactly the applied text correction candidate"
        )
    if replacement_segment.identity != generation.replacement_segment_id:
        raise PersistenceError("replacement segment identity must match the generation")
    if replacement_segment.replaces_segment_id != generation.replaced_segment_id:
        raise PersistenceError("replacement segment must replace the generation's replaced segment")
    if replacement_segment.identity not in revision.segment_ids:
        raise PersistenceError("revision must reference the composed replacement segment")
    if generation.replaced_segment_id in revision.segment_ids:
        raise PersistenceError("revision must not still reference the replaced segment")
    if result.identity != revision.domain_result_id:
        raise PersistenceError("domain result identity must match the revision")
    if result.kind != "corrected_transcript_revision":
        raise PersistenceError("domain result kind must be corrected_transcript_revision")
    if len(result.upstream_results) != 1:
        raise PersistenceError("revision domain result requires exactly one upstream result")


def _restore(row: tuple[object, ...]) -> "SameSourceCompositionGeneration":
    from lectureos.application.same_source_composition_generation import (
        SameSourceCompositionGeneration,
    )

    return SameSourceCompositionGeneration(
        identity=SameSourceCompositionGenerationId(row[0]),
        corrected_revision_id=TranscriptRevisionId(row[1]),
        parent_raw_transcript_id=TranscriptId(row[2]),
        replaced_segment_id=TranscriptSegmentId(row[3]),
        text_correction_candidate_id=CorrectionCandidateId(row[4]),
        text_authorizing_decision_id=CorrectionCandidateDecisionId(row[5]),
        timing_correction_candidate_id=TimingCorrectionCandidateId(row[6]),
        timing_authorizing_decision_id=TimingCorrectionCandidateDecisionId(row[7]),
        replacement_segment_id=TranscriptSegmentId(row[8]),
        content_fingerprint=row[9],
    )


__all__ = [
    "OTHER_OWNER_RELATIONS",
    "REQUIRED_VERSION",
    "SQLiteSameSourceCompositionCommandPersistence",
    "SQLiteSameSourceCompositionRepository",
    "TABLE",
    "revision_owned_by_composition",
]
