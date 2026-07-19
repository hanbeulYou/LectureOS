"""SQLite transaction owner for canonical Transcript commands."""

from __future__ import annotations

import sqlite3

from lectureos.execution.models import DomainResultReference
from lectureos.transcript.models import (
    CorrectionCandidate,
    CorrectedTranscriptRevision,
    RawTranscript,
    TranscriptSegment,
)

from .correction_candidates import _insert_correction_candidate
from .corrected_transcript_revisions import _insert_corrected_transcript_revision
from .domain_results import _insert_domain_result_reference_record
from .errors import (
    PersistenceError,
    PersistenceIdentityCollisionError,
    SchemaFeatureUnavailableError,
)
from .raw_transcripts import _insert_raw_transcript
from .sqlite import validate_sqlite_connection
from .transcript_segments import _insert_transcript_segment
from .transcript_segments import _restore_transcript_segment


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

    def persist_corrected_revision(
        self,
        *,
        revision: CorrectedTranscriptRevision,
        segments: tuple[TranscriptSegment, ...],
        result: DomainResultReference,
    ) -> None:
        if self._schema_version < 5:
            raise SchemaFeatureUnavailableError(
                "atomic CorrectedTranscriptRevision persistence requires SQLite schema version 5"
            )
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            self._validate_revision_linkage(revision, segments, result)
            if self._revision_identity_exists(revision) or self._result_identity_exists(result):
                raise PersistenceIdentityCollisionError(
                    "CorrectedTranscriptRevision or DomainResultReference identity already exists"
                )
            new_segments = []
            for segment in segments:
                existing = self._read_segment(segment)
                if existing is None:
                    new_segments.append(segment)
                elif existing != segment:
                    raise PersistenceIdentityCollisionError(
                        "TranscriptSegment identity has conflicting content"
                    )
            for segment in new_segments:
                _insert_transcript_segment(self._connection, segment)
            _insert_corrected_transcript_revision(self._connection, revision)
            _insert_domain_result_reference_record(self._connection, result)
            self._commit()
        except PersistenceError:
            self._rollback_if_owned(transaction_started)
            raise
        except sqlite3.Error as error:
            self._rollback_if_owned(transaction_started)
            raise PersistenceError(
                f"could not persist atomic CorrectedTranscriptRevision records: {error}"
            ) from error
        except Exception:
            self._rollback_if_owned(transaction_started)
            raise

    def persist_generated_correction(
        self,
        *,
        candidates: tuple[CorrectionCandidate, ...],
        candidate_results: tuple[DomainResultReference, ...],
        replacement_segments: tuple[TranscriptSegment, ...],
        revision: CorrectedTranscriptRevision,
        revision_result: DomainResultReference,
    ) -> None:
        if self._schema_version < 5:
            raise SchemaFeatureUnavailableError(
                "atomic generated correction persistence requires SQLite schema version 5"
            )
        transaction_started = False
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            transaction_started = True
            self._validate_generated_correction_linkage(
                candidates,
                candidate_results,
                replacement_segments,
                revision,
                revision_result,
            )
            self._require_generated_identities_absent(
                candidates,
                candidate_results,
                replacement_segments,
                revision,
                revision_result,
            )
            self._require_generated_parent_linkage(
                candidates, revision, revision_result
            )
            self._require_revision_segments_resolvable(
                revision, replacement_segments
            )
            for candidate, result in zip(candidates, candidate_results):
                _insert_correction_candidate(self._connection, candidate)
                _insert_domain_result_reference_record(self._connection, result)
            for segment in replacement_segments:
                _insert_transcript_segment(self._connection, segment)
            _insert_corrected_transcript_revision(self._connection, revision)
            _insert_domain_result_reference_record(self._connection, revision_result)
            self._commit()
        except PersistenceError:
            self._rollback_if_owned(transaction_started)
            raise
        except sqlite3.Error as error:
            self._rollback_if_owned(transaction_started)
            raise PersistenceError(
                f"could not persist atomic generated correction records: {error}"
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

    @staticmethod
    def _validate_revision_linkage(
        revision: CorrectedTranscriptRevision,
        segments: tuple[TranscriptSegment, ...],
        result: DomainResultReference,
    ) -> None:
        identities = tuple(segment.identity for segment in segments)
        if revision.segment_ids != identities:
            raise PersistenceError(
                "CorrectedTranscriptRevision segment references must match supplied Segments"
            )
        if len(set(identities)) != len(identities):
            raise PersistenceError("CorrectedTranscriptRevision Segments must be unique")
        if any(segment.transcript_id != revision.transcript_id for segment in segments):
            raise PersistenceError("TranscriptSegment must belong to Revision lineage")
        if result.identity != revision.domain_result_id:
            raise PersistenceError("CorrectedTranscriptRevision Result identity must match")
        if result.kind != "corrected_transcript_revision":
            raise PersistenceError("CorrectedTranscriptRevision Result kind must match")
        if len(result.upstream_results) != 1:
            raise PersistenceError(
                "CorrectedTranscriptRevision Result requires one upstream Result"
            )

    def _revision_identity_exists(
        self, revision: CorrectedTranscriptRevision
    ) -> bool:
        return self._connection.execute(
            "SELECT 1 FROM corrected_transcript_revisions WHERE identity = ?",
            (revision.identity.value,),
        ).fetchone() is not None

    @staticmethod
    def _validate_generated_correction_linkage(
        candidates,
        candidate_results,
        replacement_segments,
        revision,
        revision_result,
    ) -> None:
        if not candidates:
            raise PersistenceError("generated correction requires at least one Candidate")
        if not (
            len(candidates) == len(candidate_results) == len(replacement_segments)
        ):
            raise PersistenceError(
                "generated correction Candidate, Result and Segment counts must match"
            )
        if revision.correction_candidate_ids != tuple(
            candidate.identity for candidate in candidates
        ):
            raise PersistenceError(
                "generated correction Candidate order must match Revision references"
            )
        if len(set(revision.segment_ids)) != len(revision.segment_ids):
            raise PersistenceError("generated Revision Segment references must be unique")
        if revision_result.identity != revision.domain_result_id:
            raise PersistenceError("generated Revision Result identity must match")
        if revision_result.kind != "corrected_transcript_revision":
            raise PersistenceError("generated Revision Result kind must match")
        if len(revision_result.upstream_results) != 1:
            raise PersistenceError("generated Revision Result requires one upstream Result")

        expected_parent = revision.parent_revision_id
        seen_targets = set()
        seen_replacements = set()
        seen_candidate_ids = set()
        seen_result_ids = {revision_result.identity}
        for candidate, result, replacement in zip(
            candidates, candidate_results, replacement_segments
        ):
            if candidate.transcript_id != revision.transcript_id:
                raise PersistenceError("generated Candidate lineage must match Revision")
            if candidate.run_id != revision.run_id or (
                candidate.unit_execution_id != revision.unit_execution_id
            ):
                raise PersistenceError("generated Candidate execution must match Revision")
            if candidate.target_revision_id != expected_parent:
                raise PersistenceError("generated Candidate parent must match Revision")
            if replacement.transcript_id != revision.transcript_id:
                raise PersistenceError("replacement Segment lineage must match Revision")
            if replacement.replaces_segment_id != candidate.segment_id:
                raise PersistenceError("replacement Segment target must match Candidate")
            if replacement.identity not in revision.segment_ids:
                raise PersistenceError("Revision must reference replacement Segment")
            if replacement.identity in seen_replacements:
                raise PersistenceError("replacement Segment identities must be unique")
            seen_replacements.add(replacement.identity)
            if candidate.identity in seen_candidate_ids:
                raise PersistenceError("generated Candidate identities must be unique")
            seen_candidate_ids.add(candidate.identity)
            if candidate.segment_id in seen_targets:
                raise PersistenceError("generated Candidates must target distinct Segments")
            seen_targets.add(candidate.segment_id)
            if result.identity != candidate.domain_result_id:
                raise PersistenceError("generated Candidate Result identity must match")
            if result.kind != "transcript_correction_candidate":
                raise PersistenceError("generated Candidate Result kind must match")
            if result.identity in seen_result_ids:
                raise PersistenceError("generated Result identities must be unique")
            seen_result_ids.add(result.identity)
            if result.upstream_results != revision_result.upstream_results:
                raise PersistenceError(
                    "generated Candidate and Revision upstream Results must match"
                )
            if result.source_media != revision_result.source_media or (
                result.source_timeline != revision_result.source_timeline
            ):
                raise PersistenceError(
                    "generated Candidate and Revision Result provenance must match"
                )

    def _require_generated_identities_absent(
        self,
        candidates,
        candidate_results,
        replacement_segments,
        revision,
        revision_result,
    ) -> None:
        if self._revision_identity_exists(revision):
            raise PersistenceIdentityCollisionError(
                "CorrectedTranscriptRevision identity already exists"
            )
        if self._result_identity_exists(revision_result):
            raise PersistenceIdentityCollisionError(
                "Revision DomainResultReference identity already exists"
            )
        for candidate, result, segment in zip(
            candidates, candidate_results, replacement_segments
        ):
            if self._candidate_identity_exists(candidate):
                raise PersistenceIdentityCollisionError(
                    "CorrectionCandidate identity already exists"
                )
            if self._result_identity_exists(result):
                raise PersistenceIdentityCollisionError(
                    "Candidate DomainResultReference identity already exists"
                )
            if self._segment_identity_exists(segment):
                raise PersistenceIdentityCollisionError(
                    "replacement TranscriptSegment identity already exists"
                )

    def _require_revision_segments_resolvable(
        self,
        revision: CorrectedTranscriptRevision,
        replacements: tuple[TranscriptSegment, ...],
    ) -> None:
        new_ids = {segment.identity for segment in replacements}
        if len(new_ids) != len(replacements):
            raise PersistenceError("replacement Segment identities must be unique")
        for identity in revision.segment_ids:
            if identity in new_ids:
                continue
            row = self._connection.execute(
                "SELECT transcript_id FROM transcript_segments WHERE identity = ?",
                (identity.value,),
            ).fetchone()
            if row is None:
                raise PersistenceError("Revision references an unknown existing Segment")
            if row[0] != revision.transcript_id.value:
                raise PersistenceError("Revision Segment lineage must match")

    def _require_generated_parent_linkage(
        self,
        candidates: tuple[CorrectionCandidate, ...],
        revision: CorrectedTranscriptRevision,
        revision_result: DomainResultReference,
    ) -> None:
        if revision.parent_raw_transcript_id is not None:
            parent = self._connection.execute(
                """
                SELECT domain_result_id, source_media_id, source_timeline_id
                FROM raw_transcripts WHERE identity = ?
                """,
                (revision.parent_raw_transcript_id.value,),
            ).fetchone()
            segment_rows = self._connection.execute(
                """
                SELECT transcript_segment_id FROM raw_transcript_segments
                WHERE raw_transcript_id = ? ORDER BY ordinal
                """,
                (revision.parent_raw_transcript_id.value,),
            ).fetchall()
        else:
            parent = self._connection.execute(
                """
                SELECT revision.domain_result_id, raw.source_media_id,
                       raw.source_timeline_id
                FROM corrected_transcript_revisions AS revision
                JOIN raw_transcripts AS raw
                  ON raw.identity = revision.transcript_id
                WHERE revision.identity = ? AND revision.transcript_id = ?
                """,
                (revision.parent_revision_id.value, revision.transcript_id.value),
            ).fetchone()
            segment_rows = self._connection.execute(
                """
                SELECT transcript_segment_id
                FROM corrected_transcript_revision_segments
                WHERE transcript_revision_id = ? ORDER BY ordinal
                """,
                (revision.parent_revision_id.value,),
            ).fetchall()
        if parent is None:
            raise PersistenceError("generated Revision parent must exist")
        if revision_result.upstream_results[0].value != parent[0]:
            raise PersistenceError("generated Result upstream must match parent")
        if (
            revision_result.source_media is None
            or revision_result.source_media.value != parent[1]
            or revision_result.source_timeline is None
            or revision_result.source_timeline.value != parent[2]
        ):
            raise PersistenceError("generated Result source provenance must match parent")
        parent_segment_ids = {row[0] for row in segment_rows}
        if any(candidate.segment_id.value not in parent_segment_ids for candidate in candidates):
            raise PersistenceError("generated Candidate target must belong to parent")

    def _read_segment(self, segment: TranscriptSegment) -> TranscriptSegment | None:
        row = self._connection.execute(
            """
            SELECT identity, transcript_id, source_timeline_id, text,
                   source_order, start, end, speaker_label, confidence,
                   uncertainty, replaces_segment_id
            FROM transcript_segments WHERE identity = ?
            """,
            (segment.identity.value,),
        ).fetchone()
        return _restore_transcript_segment(row) if row is not None else None

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
