"""Deterministic demonstration of effective-generation Edit Candidates (042 §9.3, GOAL-027).

Drives the Edit Candidate Foundation with caller-supplied provider-independent payloads — no LLM,
ASR, network, model, prompt, review, or execution record; the only write of this contract is the
append-only `lecture_analysis_edit_candidates` table:

    A. Current analysis input admission and Analysis Finding prepared, with NO Lecture Segment
       anywhere — Segmentation is a sibling branch the Candidate never touches
    B. Edit Candidate admitted → immutable canonical record anchored to the Finding
    C. Exact replay → reused, no new row
    D. Integral (1 vs 1.0) and negative-zero (-0.0 vs 0.0) spellings → same canonical identity
    E. A different rationale, candidate type, or range → distinct canonical records
    F. Invalid payloads (inverted, negative, non-finite range; empty rationale; bad type)
       → refused, nothing written
    G. Authority change → the anchor chain derives superseded_by_authority_change
    H. Admitting against the superseded chain → explicit refusal, no row
    I. Existing candidates stay byte-identical immutable history
    J. Authority returns → the chain is current again and the same candidate converges
    K. Restart → identical reconstruction from the same stored graph
    L. Isolation: no legacy `edit_candidates` row, no ProcessingRun, no UnitExecution, no
       DomainResult of this contract, no Lecture Segment, no review or selection state
    M. Repository validation stays healthy (a superseded chain is never corruption)

The committed golden reproduces byte-for-byte; no machine paths, timestamps, or randomness appear.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lectureos.application.correction_candidate_admission import (
    build_correction_candidate_input,
)
from lectureos.application.lecture_analysis_edit_candidate import (
    EditCandidateAnchorNotAdmissibleError,
    LectureAnalysisEditCandidateError,
)
from lectureos.application.lecture_analysis_input_admission import AdmissionAuthorityMatch
from lectureos.application.provider_transcript_admission import (
    build_provider_transcript_document,
)
from lectureos.composition import (
    compose_sqlite_corrected_revision_generation_service,
    compose_sqlite_corrected_revision_selection_service,
    compose_sqlite_correction_candidate_admission_service,
    compose_sqlite_correction_candidate_decision_service,
    compose_sqlite_current_raw_transcript_selection_service,
    compose_sqlite_lecture_analysis_edit_candidate_service,
    compose_sqlite_lecture_analysis_finding_service,
    compose_sqlite_lecture_analysis_input_admission_service,
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

_RATIONALE = "0.0~1.0s 구간은 수업 시작 전 잡담으로 보이므로 사람이 검토할 만하다"


def run_analysis_edit_candidate_demo(media_fixtures_directory: str | None = None) -> dict:
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

        # A: a current admission and one Analysis Finding, with no Lecture Segment anywhere.
        revision_1 = _revise("c1", "안녕하세요 여러분")
        admission = compose_sqlite_lecture_analysis_input_admission_service(
            connection
        ).admit(intake_id=intake_id).admission
        finding = compose_sqlite_lecture_analysis_finding_service(connection).admit(
            admission_id=admission.identity.value,
            finding_type="non_lecture_speech",
            evidence="시작 직후 수업과 무관한 발화가 관찰된다",
        ).finding
        candidates = compose_sqlite_lecture_analysis_edit_candidate_service(connection)
        segments_before = _rows("lecture_analysis_segments")
        domain_results_before = _rows("domain_result_references")

        def _admit(**overrides):
            payload = {
                "finding_id": finding.identity.value,
                "candidate_type": "non_lecture_region",
                "range_start": 0.0,
                "range_end": 1.0,
                "rationale": _RATIONALE,
            }
            payload.update(overrides)
            return candidates.admit_edit_candidate(**payload)

        # B: one immutable canonical candidate anchored to the Finding.
        first = _admit()

        # C: exact replay — reused, no new row.
        replay = _admit()
        rows_after_replay = _rows("lecture_analysis_edit_candidates")

        # D: integral and negative-zero spellings converge on the same identity.
        integral = _admit(range_start=0, range_end=1)
        negative_zero = _admit(range_start=-0.0)

        # E: a different rationale, type, or range is a distinct canonical candidate.
        other_rationale = _admit(rationale="같은 구간이지만 다른 이유로 검토가 필요하다")
        other_type = _admit(candidate_type="delivery_concern")
        other_range = _admit(range_end=2.0)

        # F: invalid payloads refused before any write.
        rows_before_invalid = _rows("lecture_analysis_edit_candidates")
        refused_invalid = 0
        for bad in ({"range_start": 1.0, "range_end": 0.0}, {"range_start": -1.0},
                    {"range_end": float("nan")}, {"range_end": float("inf")},
                    {"rationale": "   "}, {"candidate_type": "Bad Type"}):
            try:
                _admit(**bad)
            except LectureAnalysisEditCandidateError:
                refused_invalid += 1
        rows_after_invalid = _rows("lecture_analysis_edit_candidates")
        domain_results_after_candidates = _rows("domain_result_references")

        # G/H: authority change → chain superseded; new candidates refused.
        revision_2 = _revise("c2", "안녕하세요 여러분, 반갑습니다")
        chain_after_change = candidates.anchor_status(first.candidate)
        refused_superseded = False
        try:
            _admit(candidate_type="redundant_restatement", range_start=1.0, range_end=2.0,
                   rationale="이 시점에는 admit되지 않아야 한다")
        except EditCandidateAnchorNotAdmissibleError:
            refused_superseded = True
        rows_after_refusal = _rows("lecture_analysis_edit_candidates")

        # I: existing candidates are untouched immutable history.
        first_after_change = candidates.get(first.candidate.identity.value)

        # J: authority returns → chain current again; the same candidate converges.
        selection.select_revision(revision_id=revision_1, reviewer="selector:kim")
        chain_after_return = candidates.anchor_status(first.candidate)
        converged = _admit()

        recorded = candidates.list_for_finding(finding.identity.value)
        legacy_candidate_rows = _rows("edit_candidates")
        processing_rows = _rows("processing_runs")
        unit_execution_rows = _rows("unit_executions")
        segment_rows = _rows("lecture_analysis_segments")
        legacy_segment_rows = _rows("lecture_segments")

        # K: restart — identical reconstruction from the same stored graph.
        connection.close()
        reopened = open_sqlite_database(database)
        try:
            restarted_service = compose_sqlite_lecture_analysis_edit_candidate_service(reopened)
            restarted = restarted_service.get(first.candidate.identity.value)
            restarted_list = restarted_service.list_for_finding(finding.identity.value)
            restarted_chain = restarted_service.anchor_status(restarted)
        finally:
            reopened.close()

        validation = validate_database(str(database))

        return {
            # Deterministic, content-derived facts (golden).
            "schema_version": SQLITE_SCHEMA_VERSION,
            "intake_id": intake_id,
            "admission_id": admission.identity.value,
            "finding_id": finding.identity.value,
            "revision_1_id": revision_1,
            "revision_2_id": revision_2,
            "candidate_1_id": first.candidate.identity.value,
            "candidate_count": len(recorded),
            "repository_validation": validation.health.value,
            # Behavioral checks.
            "candidate_anchors_finding_without_segment_or_execution":
                first.outcome.value == "recorded"
                and first.candidate.finding_id == finding.identity
                and first.candidate.candidate_type == "non_lecture_region"
                and first.candidate.rationale == _RATIONALE
                and first.candidate.candidate_contract_version == 1
                and segments_before == 0,
            "exact_replay_reused_no_new_row": replay.outcome.value == "reused"
            and replay.candidate.identity == first.candidate.identity
            and rows_after_replay == 1,
            "integral_and_negative_zero_converge":
                integral.outcome.value == "reused"
                and negative_zero.outcome.value == "reused"
                and integral.candidate.identity == first.candidate.identity
                and negative_zero.candidate.identity == first.candidate.identity,
            "distinct_content_creates_distinct_candidates":
                other_rationale.candidate.identity != first.candidate.identity
                and other_type.candidate.identity != first.candidate.identity
                and other_range.candidate.identity != first.candidate.identity,
            "invalid_payloads_refused_nothing_written": refused_invalid == 6
            and rows_after_invalid == rows_before_invalid,
            "superseded_chain_refused_no_row": refused_superseded
            and chain_after_change
            is AdmissionAuthorityMatch.SUPERSEDED_BY_AUTHORITY_CHANGE
            and rows_after_refusal == rows_before_invalid,
            "existing_candidates_are_immutable_history":
                first_after_change == first.candidate,
            "returning_authority_restores_admissibility":
                chain_after_return is AdmissionAuthorityMatch.CURRENT
                and converged.outcome.value == "reused"
                and converged.candidate.identity == first.candidate.identity,
            "restart_reconstructs_identically": restarted == first.candidate
            and len(restarted_list) == len(recorded)
            and restarted_chain is AdmissionAuthorityMatch.CURRENT,
            "segmentation_independence_and_legacy_isolation": segment_rows == 0
            and legacy_segment_rows == 0
            and legacy_candidate_rows == 0
            and processing_rows == 0
            and unit_execution_rows == 0
            and domain_results_after_candidates == domain_results_before,
            "repository_validates_healthy": validation.health.value == "healthy"
            and validation.ok,
        }


def _golden(summary: dict) -> dict:
    keys = (
        "schema_version",
        "intake_id",
        "admission_id",
        "finding_id",
        "revision_1_id",
        "revision_2_id",
        "candidate_1_id",
        "candidate_count",
        "repository_validation",
    )
    return {key: summary[key] for key in keys}


def main() -> int:
    print(json.dumps(run_analysis_edit_candidate_demo(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
