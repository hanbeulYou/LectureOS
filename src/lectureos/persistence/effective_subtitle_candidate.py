"""Insert-only SQLite persistence for Effective-Source Subtitle Candidates (041 §15, PATCH-0029).

Serializes one immutable candidate graph — the candidate row, its complete ordered cue set, and the
exact cue-to-source-segment lineage — in a single atomic transaction. Candidates, cues, and lineage
rows are never updated or deleted: later transcript-authority changes derive staleness at query
time and leave every row untouched. Any collision or error rolls back the whole graph; no partial
candidate, missing cue, or orphan lineage row can become visible. Legacy `subtitle_candidates`
tables belong to the prior contract generation and are never read or written here.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from lectureos.application.identities import (
    EffectiveSubtitleCandidateId,
    EffectiveSubtitleCueId,
    EffectiveTranscriptConsumptionId,
    TranscriptSourceIntakeId,
)
from lectureos.transcript.identities import (
    TranscriptId,
    TranscriptRevisionId,
    TranscriptSegmentId,
)

from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .sqlite import validate_sqlite_connection

if TYPE_CHECKING:
    from lectureos.application.effective_subtitle_generation import (
        EffectiveSubtitleCandidate,
        EffectiveSubtitleCue,
    )

_REQUIRED_VERSION = 39


def _require_version(connection: sqlite3.Connection) -> int:
    version = validate_sqlite_connection(connection)
    if version < _REQUIRED_VERSION:
        raise SchemaFeatureUnavailableError(
            "Effective Subtitle Candidate persistence requires SQLite schema version 39"
        )
    return version


class SQLiteEffectiveSubtitleCandidateRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        _require_version(connection)
        self._connection = connection

    def get(
        self, identity: EffectiveSubtitleCandidateId
    ) -> "EffectiveSubtitleCandidate | None":
        try:
            row = self._connection.execute(
                f"{_CANDIDATE_COLUMNS} WHERE identity = ?", (identity.value,)
            ).fetchone()
            return None if row is None else _restore_candidate(row)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Effective Subtitle Candidate: {error}"
            ) from error

    def list_for_intake(
        self, intake_id: TranscriptSourceIntakeId
    ) -> "tuple[EffectiveSubtitleCandidate, ...]":
        try:
            rows = self._connection.execute(
                f"{_CANDIDATE_COLUMNS} WHERE transcript_source_intake_id = ? "
                "ORDER BY consumption_binding_id, generator_kind, generator_version, "
                "generation_parameters_version",
                (intake_id.value,),
            ).fetchall()
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not list Effective Subtitle Candidates: {error}"
            ) from error
        return tuple(_restore_candidate(row) for row in rows)

    def cues(
        self, candidate_id: EffectiveSubtitleCandidateId
    ) -> "tuple[EffectiveSubtitleCue, ...]":
        try:
            rows = self._connection.execute(
                """
                SELECT c.identity, c.candidate_id, c.ordinal, c.text, c.start, c.end
                FROM subtitle_effective_candidate_cues c
                WHERE c.candidate_id = ?
                ORDER BY c.ordinal
                """,
                (candidate_id.value,),
            ).fetchall()
            cues = []
            for row in rows:
                segments = self._connection.execute(
                    """
                    SELECT transcript_segment_id
                    FROM subtitle_effective_candidate_cue_segments
                    WHERE cue_id = ?
                    ORDER BY ordinal
                    """,
                    (row[0],),
                ).fetchall()
                cues.append(_restore_cue(row, tuple(s[0] for s in segments)))
            return tuple(cues)
        except sqlite3.Error as error:
            raise PersistenceError(
                f"could not read Effective Subtitle Candidate cues: {error}"
            ) from error


class SQLiteEffectiveSubtitleCandidateCommandPersistence:
    """Owns one atomic v39 transaction inserting a complete candidate graph."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._schema_version = validate_sqlite_connection(connection)

    def persist_candidate(
        self,
        *,
        candidate: "EffectiveSubtitleCandidate",
        cues: "tuple[EffectiveSubtitleCue, ...]",
    ) -> None:
        if self._schema_version < _REQUIRED_VERSION:
            raise SchemaFeatureUnavailableError(
                "Effective Subtitle Candidate persistence requires SQLite schema version 39"
            )
        if len(cues) != candidate.cue_count:
            raise PersistenceError(
                "effective subtitle candidate cue set does not match its declared cue count"
            )
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            if self._exists(candidate.identity.value):
                raise PersistenceIdentityCollisionError(
                    "Effective Subtitle Candidate identity already exists"
                )
            self._connection.execute(
                """
                INSERT INTO subtitle_effective_candidates(
                    identity, transcript_source_intake_id, consumption_binding_id,
                    source_kind, corrected_revision_id, parent_raw_transcript_id,
                    source_snapshot_fingerprint, generator_kind, generator_version,
                    generation_parameters_version, cue_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate.identity.value,
                    candidate.transcript_source_intake_id.value,
                    candidate.consumption_binding_id.value,
                    candidate.source_kind.value,
                    candidate.corrected_revision_id.value
                    if candidate.corrected_revision_id
                    else None,
                    candidate.parent_raw_transcript_id.value,
                    candidate.source_snapshot_fingerprint,
                    candidate.generator_kind,
                    candidate.generator_version,
                    candidate.generation_parameters_version,
                    candidate.cue_count,
                ),
            )
            for cue in cues:
                self._connection.execute(
                    """
                    INSERT INTO subtitle_effective_candidate_cues(
                        identity, candidate_id, ordinal, text, start, end
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        cue.identity.value,
                        cue.candidate_id.value,
                        cue.ordinal,
                        cue.text,
                        cue.start,
                        cue.end,
                    ),
                )
                for segment_ordinal, segment_id in enumerate(cue.source_segment_ids):
                    self._connection.execute(
                        """
                        INSERT INTO subtitle_effective_candidate_cue_segments(
                            cue_id, ordinal, transcript_segment_id
                        ) VALUES (?, ?, ?)
                        """,
                        (cue.identity.value, segment_ordinal, segment_id.value),
                    )
            self._connection.execute("COMMIT")
        except PersistenceError:
            self._rollback(transaction_started)
            raise
        except sqlite3.IntegrityError as error:
            self._rollback(transaction_started)
            raise PersistenceIdentityCollisionError(
                f"Effective Subtitle Candidate already exists: {error}"
            ) from error
        except sqlite3.Error as error:
            self._rollback(transaction_started)
            raise PersistenceError(
                f"could not persist Effective Subtitle Candidate: {error}"
            ) from error
        except Exception:
            self._rollback(transaction_started)
            raise

    def _exists(self, identity: str) -> bool:
        return (
            self._connection.execute(
                "SELECT 1 FROM subtitle_effective_candidates WHERE identity = ?",
                (identity,),
            ).fetchone()
            is not None
        )

    def _rollback(self, transaction_started: bool) -> None:
        if transaction_started and self._connection.in_transaction:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass


_CANDIDATE_COLUMNS = (
    "SELECT identity, transcript_source_intake_id, consumption_binding_id, source_kind, "
    "corrected_revision_id, parent_raw_transcript_id, source_snapshot_fingerprint, "
    "generator_kind, generator_version, generation_parameters_version, cue_count "
    "FROM subtitle_effective_candidates"
)


def _restore_candidate(row: tuple[object, ...]) -> "EffectiveSubtitleCandidate":
    from lectureos.application.effective_subtitle_generation import (
        EffectiveSubtitleCandidate,
    )
    from lectureos.application.effective_transcript_consumption import ConsumedSourceKind

    return EffectiveSubtitleCandidate(
        identity=EffectiveSubtitleCandidateId(row[0]),
        transcript_source_intake_id=TranscriptSourceIntakeId(row[1]),
        consumption_binding_id=EffectiveTranscriptConsumptionId(row[2]),
        source_kind=ConsumedSourceKind(row[3]),
        corrected_revision_id=(
            TranscriptRevisionId(row[4]) if row[4] is not None else None
        ),
        parent_raw_transcript_id=TranscriptId(row[5]),
        source_snapshot_fingerprint=row[6],
        generator_kind=row[7],
        generator_version=row[8],
        generation_parameters_version=row[9],
        cue_count=row[10],
    )


def _restore_cue(
    row: tuple[object, ...], segment_values: tuple[str, ...]
) -> "EffectiveSubtitleCue":
    from lectureos.application.effective_subtitle_generation import EffectiveSubtitleCue

    return EffectiveSubtitleCue(
        identity=EffectiveSubtitleCueId(row[0]),
        candidate_id=EffectiveSubtitleCandidateId(row[1]),
        ordinal=row[2],
        text=row[3],
        source_segment_ids=tuple(TranscriptSegmentId(value) for value in segment_values),
        start=row[4],
        end=row[5],
    )


__all__ = [
    "SQLiteEffectiveSubtitleCandidateCommandPersistence",
    "SQLiteEffectiveSubtitleCandidateRepository",
]
