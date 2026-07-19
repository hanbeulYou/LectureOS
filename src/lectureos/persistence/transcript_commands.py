"""SQLite transaction owner for canonical Transcript commands."""

from __future__ import annotations

import sqlite3

from lectureos.execution.models import DomainResultReference
from lectureos.transcript.models import (
    CorrectionCandidate,
    RawTranscript,
    TranscriptSegment,
)

from .correction_candidates import _insert_correction_candidate
from .domain_results import _insert_domain_result_reference_record
from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .raw_transcripts import _insert_raw_transcript
from .sqlite import validate_sqlite_connection
from .transcript_segments import _insert_transcript_segment


class SQLiteTranscriptCommandPersistence:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._schema_version = validate_sqlite_connection(connection)
        self._connection = connection

    def persist_raw_transcript(
        self,
        *,
        transcript: RawTranscript,
        segments: tuple[TranscriptSegment, ...],
        result: DomainResultReference,
    ) -> None:
        if self._schema_version < 5:
            raise SchemaFeatureUnavailableError(
                "atomic RawTranscript persistence requires SQLite schema version 5"
            )
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            self._validate_raw_linkage(transcript, segments, result)
            if self._raw_identity_exists(transcript) or self._result_identity_exists(result):
                raise PersistenceIdentityCollisionError(
                    "RawTranscript or DomainResultReference identity already exists"
                )
            for segment in segments:
                if self._segment_identity_exists(segment):
                    raise PersistenceIdentityCollisionError(
                        "TranscriptSegment identity already exists"
                    )
            for segment in segments:
                _insert_transcript_segment(self._connection, segment)
            _insert_raw_transcript(self._connection, transcript)
            _insert_domain_result_reference_record(self._connection, result)
            self._commit()
        except PersistenceError:
            self._rollback_if_owned(transaction_started)
            raise
        except sqlite3.Error as error:
            self._rollback_if_owned(transaction_started)
            raise PersistenceError(
                f"could not persist atomic RawTranscript records: {error}"
            ) from error
        except Exception:
            self._rollback_if_owned(transaction_started)
            raise

    def persist_correction_candidate(
        self,
        *,
        candidate: CorrectionCandidate,
        result: DomainResultReference,
    ) -> None:
        if self._schema_version < 5:
            raise SchemaFeatureUnavailableError(
                "atomic CorrectionCandidate persistence requires SQLite schema version 5"
            )
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            self._validate_candidate_linkage(candidate, result)
            if self._candidate_identity_exists(candidate) or self._result_identity_exists(result):
                raise PersistenceIdentityCollisionError(
                    "CorrectionCandidate or DomainResultReference identity already exists"
                )
            _insert_correction_candidate(self._connection, candidate)
            _insert_domain_result_reference_record(self._connection, result)
            self._commit()
        except PersistenceError:
            self._rollback_if_owned(transaction_started)
            raise
        except sqlite3.Error as error:
            self._rollback_if_owned(transaction_started)
            raise PersistenceError(
                f"could not persist atomic CorrectionCandidate records: {error}"
            ) from error
        except Exception:
            self._rollback_if_owned(transaction_started)
            raise

    @staticmethod
    def _validate_raw_linkage(
        transcript: RawTranscript,
        segments: tuple[TranscriptSegment, ...],
        result: DomainResultReference,
    ) -> None:
        if transcript.segment_ids != tuple(segment.identity for segment in segments):
            raise PersistenceError(
                "RawTranscript segment references must match supplied Segments"
            )
        if any(segment.transcript_id != transcript.identity for segment in segments):
            raise PersistenceError("TranscriptSegment must belong to RawTranscript")
        if result.identity != transcript.domain_result_id:
            raise PersistenceError("RawTranscript Result identity must match")
        if result.kind != "raw_transcript":
            raise PersistenceError("RawTranscript Result kind must match")
        if result.source_media != transcript.source_media_id:
            raise PersistenceError("RawTranscript Result source media must match")
        if result.source_timeline != transcript.source_timeline_id:
            raise PersistenceError("RawTranscript Result source timeline must match")

    def _raw_identity_exists(self, transcript: RawTranscript) -> bool:
        return self._connection.execute(
            "SELECT 1 FROM raw_transcripts WHERE identity = ?",
            (transcript.identity.value,),
        ).fetchone() is not None

    @staticmethod
    def _validate_candidate_linkage(
        candidate: CorrectionCandidate,
        result: DomainResultReference,
    ) -> None:
        if result.identity != candidate.domain_result_id:
            raise PersistenceError("CorrectionCandidate Result identity must match")
        if result.kind != "transcript_correction_candidate":
            raise PersistenceError("CorrectionCandidate Result kind must match")
        if len(result.upstream_results) != 1:
            raise PersistenceError(
                "CorrectionCandidate Result requires one upstream Result"
            )

    def _candidate_identity_exists(self, candidate: CorrectionCandidate) -> bool:
        return self._connection.execute(
            "SELECT 1 FROM correction_candidates WHERE identity = ?",
            (candidate.identity.value,),
        ).fetchone() is not None

    def _segment_identity_exists(self, segment: TranscriptSegment) -> bool:
        return self._connection.execute(
            "SELECT 1 FROM transcript_segments WHERE identity = ?",
            (segment.identity.value,),
        ).fetchone() is not None

    def _result_identity_exists(self, result: DomainResultReference) -> bool:
        return self._connection.execute(
            "SELECT 1 FROM domain_result_references WHERE identity = ?",
            (result.identity.value,),
        ).fetchone() is not None

    def _rollback_if_owned(self, transaction_started: bool) -> None:
        if transaction_started and self._connection.in_transaction:
            try:
                self._connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass

    def _commit(self) -> None:
        self._connection.execute("COMMIT")
