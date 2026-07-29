"""Deterministic demonstration of effective-generation Lecture Segmentation (042 §7.2, GOAL-026).

Drives the Lecture Segmentation Foundation with caller-supplied ordered range batches — no LLM,
ASR, network, model, prompt, or execution record; the only write of this contract is the
append-only `lecture_analysis_segments` table:

    A. Current analysis input admission prepared (GOAL-023 chain), with NO Analysis Finding
       anywhere — Segmentation and Finding are siblings, so neither requires the other
    B. Ordered segment batch admitted → immutable canonical records, positions 0..n-1
    C. Exact replay → reused, no new row
    D. Integral range spellings (1 vs 1.0) → same canonical identities
    E. A different ordered batch → distinct records; two batches legitimately share sequence 0,
       because §7.1 forbids canonical-set/uniqueness constraints
    F. Partial pre-existence → only the genuinely new segments are recorded
    G. Invalid ranges (inverted, negative, empty batch, non-finite) → refused, nothing written
    H. Authority change → the anchor derives superseded_by_authority_change
    I. Admitting against the superseded anchor → explicit refusal, no row
    J. Existing segments stay byte-identical immutable history
    K. Authority returns → the anchor is current again and the same batch converges
    L. Restart → identical reconstruction from the same stored graph
    M. Isolation: no legacy `lecture_segments` / `eligible_analysis_inputs` row, no ProcessingRun,
       no UnitExecution, no DomainResult of this contract, no Analysis Finding, no Edit Candidate
    N. Repository validation stays healthy (a superseded anchor and a shared sequence are never
       corruption)

The committed golden reproduces byte-for-byte; no machine paths, timestamps, or randomness appear.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lectureos.application.correction_candidate_admission import (
    build_correction_candidate_input,
)
from lectureos.application.lecture_analysis_input_admission import AdmissionAuthorityMatch
from lectureos.application.lecture_analysis_segment import (
    LectureAnalysisSegmentError,
    SegmentationAnchorNotAdmissibleError,
)
from lectureos.application.provider_transcript_admission import (
    build_provider_transcript_document,
)
from lectureos.composition import (
    compose_sqlite_corrected_revision_generation_service,
    compose_sqlite_corrected_revision_selection_service,
    compose_sqlite_correction_candidate_admission_service,
    compose_sqlite_correction_candidate_decision_service,
    compose_sqlite_current_raw_transcript_selection_service,
    compose_sqlite_lecture_analysis_input_admission_service,
    compose_sqlite_lecture_analysis_segmentation_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.persistence import (
    SQLITE_SCHEMA_VERSION,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.persistence.raw_transcripts import SQLiteRawTranscriptRepository
from lectureos.persistence.transcript_segments import SQLiteTranscriptSegmentRepository
from lectureos.validation import validate_database

_MEDIA_FIXTURES = Path(__file__).resolve().parents[2] / "examples" / "media-import" / "fixtures"


def run_analysis_segment_demo(media_fixtures_directory: str | None = None) -> dict:
    fixtures = Path(media_fixtures_directory) if media_fixtures_directory else _MEDIA_FIXTURES
    sample = fixtures / "sample-a.bin"

    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "lectureos.sqlite3"
        connection = initialize_sqlite_database(database)

        media = compose_sqlite_media_import_service(connection).import_media(str(sample)).record
        intake_id = compose_sqlite_transcript_source_intake_service(connection).admit(
            media.identity.value
        ).intake.identity.value
        raw = compose_sqlite_provider_transcript_admission_service(connection).admit(
            intake_id=intake_id,
            document=build_provider_transcript_document(
                {"provider": "fake-asr", "model": "tiny", "language": "ko",
                 "provider_result_ref": "A",
                 "segments": [{"start": 0.0, "end": 1.0, "text": "안녕하세요 여러부"},
                              {"start": 1.0, "end": 2.0, "text": "오늘의 강의입니다"}]}
            ),
        ).admission
        compose_sqlite_current_raw_transcript_selection_service(connection).select(
            intake_id, raw.raw_transcript_id.value
        )
        selection = compose_sqlite_corrected_revision_selection_service(connection)

        def _revise(candidate_ref: str, proposed_text: str) -> str:
            segment_id = SQLiteRawTranscriptRepository(connection).get(
                raw.raw_transcript_id
            ).segment_ids[0]
            source_text = SQLiteTranscriptSegmentRepository(connection).get(segment_id).text
            candidate = compose_sqlite_correction_candidate_admission_service(connection).admit(
                intake_id=intake_id,
                candidate=build_correction_candidate_input(
                    {"raw_transcript_id": raw.raw_transcript_id.value,
                     "segment_id": segment_id.value,
                     "candidate_ref": candidate_ref, "source_type": "manual",
                     "source_reference": "human", "proposed_text": proposed_text,
                     "source_text_snapshot": source_text, "rationale": "발화 교정"}
                ),
            ).candidate.identity.value
            compose_sqlite_correction_candidate_decision_service(connection).decide(
                candidate_id=candidate, kind="accept", reviewer="reviewer:kim"
            )
            revision = compose_sqlite_corrected_revision_generation_service(
                connection
            ).generate(candidate_id=candidate).revision.identity.value
            selection.select_revision(revision_id=revision, reviewer="selector:kim")
            return revision

        def _rows(table: str) -> int:
            return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

        # A: a current analysis input admission, with no Analysis Finding anywhere.
        revision_1 = _revise("c1", "안녕하세요 여러분")
        admissions = compose_sqlite_lecture_analysis_input_admission_service(connection)
        admission = admissions.admit(intake_id=intake_id).admission
        segmentation = compose_sqlite_lecture_analysis_segmentation_service(connection)
        findings_before = _rows("lecture_analysis_findings")
        domain_results_before = _rows("domain_result_references")

        # B: one ordered batch of immutable canonical segments.
        first = segmentation.admit_segmentation(
            admission_id=admission.identity.value,
            ranges=[(0.0, 1.0), (1.0, 2.0)],
        )

        # C: exact replay — reused, no new row.
        replay = segmentation.admit_segmentation(
            admission_id=admission.identity.value,
            ranges=[(0.0, 1.0), (1.0, 2.0)],
        )
        rows_after_replay = _rows("lecture_analysis_segments")

        # D: integral spellings converge on the same canonical identities.
        integral = segmentation.admit_segmentation(
            admission_id=admission.identity.value, ranges=[(0, 1), (1, 2)]
        )

        # E: a different ordered batch — distinct records sharing sequence 0 with the first.
        other = segmentation.admit_segmentation(
            admission_id=admission.identity.value,
            ranges=[(0.0, 0.5), (0.5, 2.0)],
        )
        shared_sequence_rows = connection.execute(
            "SELECT COUNT(*) FROM lecture_analysis_segments WHERE admission_id = ? "
            "AND sequence = 0",
            (admission.identity.value,),
        ).fetchone()[0]

        # F: partial pre-existence — only the genuinely new member is recorded.
        partial = segmentation.admit_segmentation(
            admission_id=admission.identity.value,
            ranges=[(0.0, 1.0), (9.0, 9.0)],
        )

        # G: invalid batches refused before any write.
        rows_before_invalid = _rows("lecture_analysis_segments")
        refused_invalid = 0
        for bad in ([(1.0, 0.0)], [(-1.0, 1.0)], [], [(0.0, float("nan"))],
                    [(0.0, float("inf"))]):
            try:
                segmentation.admit_segmentation(
                    admission_id=admission.identity.value, ranges=bad
                )
            except LectureAnalysisSegmentError:
                refused_invalid += 1
        rows_after_invalid = _rows("lecture_analysis_segments")
        domain_results_after_segmentation = _rows("domain_result_references")

        # H/I: authority change → anchor superseded; new segmentation refused.
        revision_2 = _revise("c2", "안녕하세요 여러분, 반갑습니다")
        anchor_after_change = segmentation.anchor_status(first.segments[0])
        refused_superseded = False
        try:
            segmentation.admit_segmentation(
                admission_id=admission.identity.value, ranges=[(3.0, 4.0)]
            )
        except SegmentationAnchorNotAdmissibleError:
            refused_superseded = True
        rows_after_refusal = _rows("lecture_analysis_segments")

        # J: existing segments are untouched immutable history.
        first_after_change = segmentation.get(first.segments[0].identity.value)

        # K: authority returns → anchor current again; the same batch converges.
        selection.select_revision(revision_id=revision_1, reviewer="selector:kim")
        anchor_after_return = segmentation.anchor_status(first.segments[0])
        converged = segmentation.admit_segmentation(
            admission_id=admission.identity.value,
            ranges=[(0.0, 1.0), (1.0, 2.0)],
        )

        recorded = segmentation.list_for_admission(admission.identity.value)
        legacy_segment_rows = _rows("lecture_segments")
        legacy_input_rows = _rows("eligible_analysis_inputs")
        processing_rows = _rows("processing_runs")
        unit_execution_rows = _rows("unit_executions")
        finding_rows = _rows("lecture_analysis_findings")
        candidate_rows = _rows("edit_candidates")

        # L: restart — identical reconstruction from the same stored graph.
        connection.close()
        reopened = open_sqlite_database(database)
        try:
            restarted_service = compose_sqlite_lecture_analysis_segmentation_service(reopened)
            restarted = restarted_service.get(first.segments[0].identity.value)
            restarted_list = restarted_service.list_for_admission(admission.identity.value)
            restarted_anchor = restarted_service.anchor_status(restarted)
        finally:
            reopened.close()

        validation = validate_database(str(database))

        return {
            # Deterministic, content-derived facts (golden).
            "schema_version": SQLITE_SCHEMA_VERSION,
            "intake_id": intake_id,
            "admission_id": admission.identity.value,
            "revision_1_id": revision_1,
            "revision_2_id": revision_2,
            "segment_1_id": first.segments[0].identity.value,
            "segment_2_id": first.segments[1].identity.value,
            "segment_count": len(recorded),
            "repository_validation": validation.health.value,
            # Behavioral checks.
            "batch_recorded_without_finding_or_execution":
                first.outcome.value == "recorded"
                and first.recorded_count == 2
                and [s.sequence for s in first.segments] == [0, 1]
                and all(s.admission_id == admission.identity for s in first.segments)
                and findings_before == 0
                and first.segments[0].segment_contract_version == 1,
            "exact_replay_reused_no_new_row": replay.outcome.value == "reused"
            and [s.identity for s in replay.segments]
            == [s.identity for s in first.segments]
            and rows_after_replay == 2,
            "integral_ranges_converge_on_same_identities":
                integral.outcome.value == "reused"
                and [s.identity for s in integral.segments]
                == [s.identity for s in first.segments],
            "distinct_batch_records_distinct_segments_sharing_sequence":
                other.outcome.value == "recorded"
                and other.recorded_count == 2
                and other.segments[0].identity != first.segments[0].identity
                and shared_sequence_rows == 2,
            "partial_pre_existence_records_only_new":
                partial.outcome.value == "recorded"
                and partial.recorded_count == 1
                and partial.reused_count == 1
                and partial.segments[0].identity == first.segments[0].identity,
            "invalid_batches_refused_nothing_written": refused_invalid == 5
            and rows_after_invalid == rows_before_invalid,
            "superseded_anchor_refused_no_row": refused_superseded
            and anchor_after_change
            is AdmissionAuthorityMatch.SUPERSEDED_BY_AUTHORITY_CHANGE
            and rows_after_refusal == rows_before_invalid,
            "existing_segments_are_immutable_history":
                first_after_change == first.segments[0],
            "returning_authority_restores_admissibility":
                anchor_after_return is AdmissionAuthorityMatch.CURRENT
                and converged.outcome.value == "reused"
                and [s.identity for s in converged.segments]
                == [s.identity for s in first.segments],
            "restart_reconstructs_identically": restarted == first.segments[0]
            and len(restarted_list) == len(recorded)
            and restarted_anchor is AdmissionAuthorityMatch.CURRENT,
            "finding_independence_and_legacy_isolation": finding_rows == 0
            and legacy_segment_rows == 0
            and legacy_input_rows == 0
            and processing_rows == 0
            and unit_execution_rows == 0
            and candidate_rows == 0
            and domain_results_after_segmentation == domain_results_before,
            "repository_validates_healthy": validation.health.value == "healthy"
            and validation.ok,
        }


def _golden(summary: dict) -> dict:
    keys = (
        "schema_version",
        "intake_id",
        "admission_id",
        "revision_1_id",
        "revision_2_id",
        "segment_1_id",
        "segment_2_id",
        "segment_count",
        "repository_validation",
    )
    return {key: summary[key] for key in keys}


def main() -> int:
    print(json.dumps(run_analysis_segment_demo(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
