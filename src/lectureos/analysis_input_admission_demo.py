"""Deterministic demonstration of Explicit Lecture Analysis Input Admission (GOAL-023).

Drives the durable half of 042 Milestone 1 with fake provider results and explicit human
actors — no LLM, ASR, network, or model; the only write is the append-only admission table:

    A. Ineligible intake → admission refused, nothing persisted
    B. Eligible corrected authority → explicit admit → immutable record with the exact
       authority snapshot (intake, source media, revision, parent raw, selections, §19
       fingerprint)
    C. Exact replay → reused, no new row (idempotent convergence)
    D. Authority change (new corrected revision) → NEW admission; the old record remains
       byte-identical immutable history (append-only) and derives
       superseded_by_authority_change
    E. Authority returns to a previously admitted revision → converges on the existing record
    F. Restart → identical reconstruction from the same stored graph
    G. Isolation: legacy `eligible_analysis_inputs` untouched (zero rows); no ProcessingRun,
       no analysis rows, no subtitle rows
    H. Repository validation stays healthy (superseded admissions are never corruption)

The committed golden reproduces byte-for-byte; no machine paths or timestamps appear.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lectureos.application.correction_candidate_admission import (
    build_correction_candidate_input,
)
from lectureos.application.lecture_analysis_input_admission import (
    AdmissionAuthorityMatch,
    AnalysisInputNotAdmissibleError,
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


def run_analysis_input_admission_demo(media_fixtures_directory: str | None = None) -> dict:
    fixtures = Path(media_fixtures_directory) if media_fixtures_directory else _MEDIA_FIXTURES
    sample = fixtures / "sample-a.bin"

    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "lectureos.sqlite3"
        connection = initialize_sqlite_database(database)

        media = compose_sqlite_media_import_service(connection).import_media(str(sample)).record
        intake_id = compose_sqlite_transcript_source_intake_service(connection).admit(
            media.identity.value
        ).intake.identity.value
        admissions = compose_sqlite_lecture_analysis_input_admission_service(connection)

        def _rows(table: str) -> int:
            return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

        # A: ineligible intake — refused before persistence, nothing recorded.
        refused = False
        try:
            admissions.admit(intake_id=intake_id)
        except AnalysisInputNotAdmissibleError:
            refused = True
        refused_nothing = _rows("lecture_analysis_input_admissions") == 0

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

        # B: eligible corrected authority → explicit admission with the exact snapshot.
        revision_1 = _revise("c1", "안녕하세요 여러분")
        first = admissions.admit(intake_id=intake_id)

        # C: exact replay — reused, no new row.
        replay = admissions.admit(intake_id=intake_id)
        rows_after_replay = _rows("lecture_analysis_input_admissions")

        # D: authority change → NEW admission; old record immutable, derives superseded.
        revision_2 = _revise("c2", "안녕하세요 여러분, 반갑습니다")
        second = admissions.admit(intake_id=intake_id)
        first_after_change = admissions.get(first.admission.identity.value)
        first_match = admissions.authority_match(first.admission)
        second_match = admissions.authority_match(second.admission)

        # E: authority returns to the previously admitted revision → converge.
        selection.select_revision(revision_id=revision_1, reviewer="selector:kim")
        converged = admissions.admit(intake_id=intake_id)

        history = admissions.list_for_intake(intake_id)
        legacy_rows = _rows("eligible_analysis_inputs")
        processing_rows = _rows("processing_runs")
        subtitle_rows = _rows("subtitle_effective_candidates")

        # F: restart — identical reconstruction from the same stored graph.
        connection.close()
        reopened = open_sqlite_database(database)
        try:
            restarted_service = compose_sqlite_lecture_analysis_input_admission_service(
                reopened
            )
            restarted = restarted_service.get(first.admission.identity.value)
            restarted_match = restarted_service.authority_match(restarted)
        finally:
            reopened.close()

        validation = validate_database(str(database))

        return {
            # Deterministic, content-derived facts (golden).
            "schema_version": SQLITE_SCHEMA_VERSION,
            "intake_id": intake_id,
            "revision_1_id": revision_1,
            "revision_2_id": revision_2,
            "admission_1_id": first.admission.identity.value,
            "admission_2_id": second.admission.identity.value,
            "admission_1_fingerprint": first.admission.content_fingerprint,
            "admission_2_fingerprint": second.admission.content_fingerprint,
            "admission_count": len(history),
            "repository_validation": validation.health.value,
            # Behavioral checks.
            "ineligible_admission_refused_nothing_persisted": refused and refused_nothing,
            "admission_binds_exact_authority_snapshot": first.outcome.value == "admitted"
            and first.admission.corrected_revision_id.value == revision_1
            and first.admission.parent_raw_transcript_id == raw.raw_transcript_id
            and first.admission.source_media_id == media.identity
            and first.admission.segment_count == 2
            and first.eligibility.eligible,
            "exact_replay_reused_no_new_row": replay.outcome.value == "reused"
            and replay.admission.identity == first.admission.identity
            and rows_after_replay == 1,
            "authority_change_appends_immutable_history": second.outcome.value == "admitted"
            and second.admission.corrected_revision_id.value == revision_2
            and second.admission.identity != first.admission.identity
            and first_after_change == first.admission
            and first_match is AdmissionAuthorityMatch.SUPERSEDED_BY_AUTHORITY_CHANGE
            and second_match is AdmissionAuthorityMatch.CURRENT
            and first.admission.content_fingerprint
            != second.admission.content_fingerprint,
            "returning_authority_converges": converged.outcome.value == "reused"
            and converged.admission.identity == first.admission.identity
            and len(history) == 2,
            "restart_reconstructs_identically": restarted == first.admission
            and restarted_match is AdmissionAuthorityMatch.CURRENT,
            "legacy_and_execution_isolation": legacy_rows == 0
            and processing_rows == 0 and subtitle_rows == 0,
            "repository_validates_healthy": validation.health.value == "healthy"
            and validation.ok,
        }


def _golden(summary: dict) -> dict:
    keys = (
        "schema_version",
        "intake_id",
        "revision_1_id",
        "revision_2_id",
        "admission_1_id",
        "admission_2_id",
        "admission_1_fingerprint",
        "admission_2_fingerprint",
        "admission_count",
        "repository_validation",
    )
    return {key: summary[key] for key in keys}


def main() -> int:
    print(json.dumps(run_analysis_input_admission_demo(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
