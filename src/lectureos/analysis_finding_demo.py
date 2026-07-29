"""Deterministic demonstration of effective-generation Analysis Findings (042 §8.2, GOAL-025).

Drives the Analysis Finding Application Foundation with caller-supplied provider-independent
payloads — no LLM, ASR, network, model, prompt, or execution record; the only write of this
contract is the append-only `lecture_analysis_findings` table:

    A. Current analysis input admission prepared (GOAL-023 chain)
    B. Finding admitted → immutable canonical record anchored to that admission
    C. Exact replay → reused, no new row (idempotent convergence)
    D. Divergent recorded payload on the same identity → explicit conflict, nothing written
    E. Different canonical content (type / evidence / range) → distinct findings
    F. Authority change → the anchor derives superseded_by_authority_change
    G. Admitting against the superseded anchor → explicit refusal, no row
    H. Existing findings stay byte-identical immutable history
    I. Authority returns to the previously admitted revision → the anchor is current again and
       the same canonical finding converges on its original identity
    J. Restart → identical reconstruction from the same stored graph
    K. Isolation: no legacy `analysis_findings` / `eligible_analysis_inputs` row, no
       ProcessingRun, no UnitExecution, no Lecture Segment, no Edit Candidate
    L. Repository validation stays healthy (a superseded anchor is never corruption)

The committed golden reproduces byte-for-byte; no machine paths, timestamps, or randomness appear.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lectureos.application.correction_candidate_admission import (
    build_correction_candidate_input,
)
from lectureos.application.lecture_analysis_finding import (
    AnalysisFindingAnchorNotAdmissibleError,
    AnalysisFindingConflictError,
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


def run_analysis_finding_demo(media_fixtures_directory: str | None = None) -> dict:
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

        # A: a current analysis input admission (the released GOAL-023 anchor).
        revision_1 = _revise("c1", "안녕하세요 여러분")
        admissions = compose_sqlite_lecture_analysis_input_admission_service(connection)
        admission = admissions.admit(intake_id=intake_id).admission
        findings = compose_sqlite_lecture_analysis_finding_service(connection)

        # B: one immutable canonical finding anchored to that admission.
        first = findings.admit(
            admission_id=admission.identity.value,
            finding_type="background_noise",
            evidence="0.0~1.0s 구간에 지속적인 배경 잡음이 관찰된다",
            confidence=0.5,
        )

        # C: exact replay — reused, no new row.
        replay = findings.admit(
            admission_id=admission.identity.value,
            finding_type="background_noise",
            evidence="0.0~1.0s 구간에 지속적인 배경 잡음이 관찰된다",
            confidence=0.5,
        )
        rows_after_replay = _rows("lecture_analysis_findings")

        # D: same identity, divergent recorded confidence → explicit conflict, nothing written.
        conflicted = False
        try:
            findings.admit(
                admission_id=admission.identity.value,
                finding_type="background_noise",
                evidence="0.0~1.0s 구간에 지속적인 배경 잡음이 관찰된다",
                confidence=0.9,
            )
        except AnalysisFindingConflictError:
            conflicted = True
        rows_after_conflict = _rows("lecture_analysis_findings")

        # E: different canonical content → distinct findings (evidence, then a located range).
        other_evidence = findings.admit(
            admission_id=admission.identity.value,
            finding_type="background_noise",
            evidence="1.0~2.0s 구간에도 같은 잡음이 이어진다",
            confidence=0.5,
        )
        located = findings.admit(
            admission_id=admission.identity.value,
            finding_type="speaker_overlap",
            evidence="두 화자의 발화가 겹친다",
            range_start=0.5,
            range_end=1.5,
        )
        unlocated_count = sum(
            0 if f.has_source_range else 1
            for f in findings.list_for_admission(admission.identity.value)
        )

        # F/G: authority change → the anchor derives superseded; new findings are refused.
        revision_2 = _revise("c2", "안녕하세요 여러분, 반갑습니다")
        anchor_after_change = findings.anchor_status(first.finding)
        refused = False
        try:
            findings.admit(
                admission_id=admission.identity.value,
                finding_type="delivery_pause",
                evidence="이 시점에는 admit되지 않아야 한다",
            )
        except AnalysisFindingAnchorNotAdmissibleError:
            refused = True
        rows_after_refusal = _rows("lecture_analysis_findings")

        # H: existing findings are untouched immutable history.
        first_after_change = findings.get(first.finding.identity.value)
        located_after_change = findings.get(located.finding.identity.value)

        # I: authority returns → anchor current again; the same canonical finding converges.
        selection.select_revision(revision_id=revision_1, reviewer="selector:kim")
        anchor_after_return = findings.anchor_status(first.finding)
        converged = findings.admit(
            admission_id=admission.identity.value,
            finding_type="background_noise",
            evidence="0.0~1.0s 구간에 지속적인 배경 잡음이 관찰된다",
            confidence=0.5,
        )

        recorded = findings.list_for_admission(admission.identity.value)
        legacy_finding_rows = _rows("analysis_findings")
        legacy_input_rows = _rows("eligible_analysis_inputs")
        processing_rows = _rows("processing_runs")
        unit_execution_rows = _rows("unit_executions")
        segment_rows = _rows("lecture_segments")
        candidate_rows = _rows("edit_candidates")

        # J: restart — identical reconstruction from the same stored graph.
        connection.close()
        reopened = open_sqlite_database(database)
        try:
            restarted_service = compose_sqlite_lecture_analysis_finding_service(reopened)
            restarted = restarted_service.get(first.finding.identity.value)
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
            "finding_1_id": first.finding.identity.value,
            "finding_2_id": other_evidence.finding.identity.value,
            "finding_3_id": located.finding.identity.value,
            "finding_count": len(recorded),
            "repository_validation": validation.health.value,
            # Behavioral checks.
            "finding_anchors_admission_without_duplicating_provenance":
                first.outcome.value == "recorded"
                and first.finding.admission_id == admission.identity
                and first.finding.finding_type == "background_noise"
                and first.finding.confidence == 0.5
                and not first.finding.has_source_range
                and first.finding.finding_contract_version == 1,
            "exact_replay_reused_no_new_row": replay.outcome.value == "reused"
            and replay.finding.identity == first.finding.identity
            and rows_after_replay == 1,
            "divergent_payload_conflicts_nothing_written": conflicted
            and rows_after_conflict == 1,
            "distinct_content_creates_distinct_findings":
                other_evidence.finding.identity != first.finding.identity
                and located.finding.identity != first.finding.identity
                and located.finding.has_source_range
                and located.finding.range_start == 0.5
                and located.finding.range_end == 1.5
                and unlocated_count == 2,
            "superseded_anchor_refused_no_row": refused
            and anchor_after_change
            is AdmissionAuthorityMatch.SUPERSEDED_BY_AUTHORITY_CHANGE
            and rows_after_refusal == 3,
            "existing_findings_are_immutable_history":
                first_after_change == first.finding
                and located_after_change == located.finding,
            "returning_authority_restores_admissibility":
                anchor_after_return is AdmissionAuthorityMatch.CURRENT
                and converged.outcome.value == "reused"
                and converged.finding.identity == first.finding.identity
                and len(recorded) == 3,
            "restart_reconstructs_identically": restarted == first.finding
            and len(restarted_list) == 3
            and restarted_anchor is AdmissionAuthorityMatch.CURRENT,
            "legacy_execution_and_downstream_isolation": legacy_finding_rows == 0
            and legacy_input_rows == 0
            and processing_rows == 0
            and unit_execution_rows == 0
            and segment_rows == 0
            and candidate_rows == 0,
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
        "finding_1_id",
        "finding_2_id",
        "finding_3_id",
        "finding_count",
        "repository_validation",
    )
    return {key: summary[key] for key in keys}


def main() -> int:
    print(json.dumps(run_analysis_finding_demo(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
