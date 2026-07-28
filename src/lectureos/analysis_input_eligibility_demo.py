"""Deterministic demonstration of Derived Lecture Analysis Input Eligibility (GOAL-022).

Drives the first Lecture Intelligence contract with fake provider results and explicit human
actors — no LLM, ASR, network, model, or filesystem write beyond the repository itself:

    A. Intake without a current raw transcript → ineligible (no_current_raw_transcript)
    B. Raw authority only (no corrected selection history) → ineligible
       (corrected_transcript_not_selected) — 042 §5.1 admits only the validated selected
       Corrected Transcript
    C. Explicit raw-fallback selection → still ineligible (same confirmed policy)
    D. Current applicable corrected revision → ELIGIBLE with exact lineage
       (intake, source media, revision, parent raw, selections, §19 content fingerprint)
    E. Superseded historical revision → eligibility resolves only the current authority
    F. Inapplicable selection (upstream authority change) → ineligible with the canonical
       resolver's reason, never a silent raw fallback
    G. Unknown intake → ineligible (intake_not_found)
    H. Restart determinism → byte-identical result after reopening the repository
    I. Derived-only → zero rows written anywhere by any evaluation; schema unchanged (v46)
    J. Repository validation stays healthy; ineligibility is never corruption

The committed golden reproduces byte-for-byte; no machine paths or timestamps appear.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lectureos.application.correction_candidate_admission import (
    build_correction_candidate_input,
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
    compose_sqlite_lecture_analysis_input_eligibility_service,
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


def _result_dict(result) -> dict:
    return {
        "intake": result.transcript_source_intake_id,
        "eligible": result.eligible,
        "blocking_reasons": [reason.value for reason in result.blocking_reasons],
        "source_media": (
            result.source_media_id.value if result.source_media_id else None
        ),
        "selection_state": (
            result.selection_state.value if result.selection_state else None
        ),
        "effective_kind": (
            result.effective_kind.value if result.effective_kind else None
        ),
        "corrected_revision": (
            result.corrected_revision_id.value if result.corrected_revision_id else None
        ),
        "parent_raw_transcript": (
            result.parent_raw_transcript_id.value
            if result.parent_raw_transcript_id
            else None
        ),
        "inapplicability_reason": result.inapplicability_reason,
        "segment_count": result.segment_count,
        "content_fingerprint": result.content_fingerprint,
    }


def run_analysis_input_eligibility_demo(media_fixtures_directory: str | None = None) -> dict:
    fixtures = Path(media_fixtures_directory) if media_fixtures_directory else _MEDIA_FIXTURES
    sample = fixtures / "sample-a.bin"

    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "lectureos.sqlite3"
        connection = initialize_sqlite_database(database)

        media = compose_sqlite_media_import_service(connection).import_media(str(sample)).record
        intake_id = compose_sqlite_transcript_source_intake_service(connection).admit(
            media.identity.value
        ).intake.identity.value
        eligibility = compose_sqlite_lecture_analysis_input_eligibility_service(connection)

        def _rows() -> dict:
            return {
                table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for (table,) in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
                ).fetchall()
            }

        # A: no current raw transcript yet.
        no_raw = eligibility.evaluate(intake_id)

        provider = compose_sqlite_provider_transcript_admission_service(connection)
        raw = provider.admit(
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

        # B: raw authority only — 042 §5.1 admits only the validated Corrected Transcript.
        raw_only = eligibility.evaluate(intake_id)

        # C: an explicit raw-fallback selection is still not the confirmed admission authority.
        selection = compose_sqlite_corrected_revision_selection_service(connection)
        selection.select_raw_fallback(intake_id=intake_id, reviewer="selector:kim")
        raw_fallback = eligibility.evaluate(intake_id)

        # D: current applicable corrected revision → eligible with exact lineage.
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

        revision_1 = _revise("c1", "안녕하세요 여러분")
        eligible_first = eligibility.evaluate(intake_id)

        # E: a replacement corrected revision supersedes; eligibility resolves only the
        # current authority (the historical revision remains a valid immutable record).
        revision_2 = _revise("c2", "안녕하세요 여러분, 반갑습니다")
        eligible_second = eligibility.evaluate(intake_id)

        # F: an upstream change makes the selected revision inapplicable — the canonical
        # resolver reports it explicitly; eligibility never falls back silently.
        raw_b = provider.admit(
            intake_id=intake_id,
            document=build_provider_transcript_document(
                {"provider": "fake-asr", "model": "tiny", "language": "ko",
                 "provider_result_ref": "B",
                 "segments": [{"start": 0.0, "end": 1.0, "text": "안녕하세요 여러부"},
                              {"start": 1.0, "end": 2.0, "text": "오늘의 강의입니다"}]}
            ),
        ).admission
        compose_sqlite_current_raw_transcript_selection_service(connection).select(
            intake_id, raw_b.raw_transcript_id.value
        )
        inapplicable = eligibility.evaluate(intake_id)

        # G: unknown intake → stable ineligible result, nothing raised, nothing persisted.
        unknown = eligibility.evaluate(
            "transcript-source-intake:sha256:" + "0" * 64
        )

        # I: derived-only — every evaluation above wrote nothing anywhere.
        rows_before = _rows()
        eligibility.evaluate(intake_id)
        eligibility.evaluate(intake_id)
        derived_only = _rows() == rows_before
        no_analysis_rows = all(
            count == 0
            for name, count in rows_before.items()
            if "analysis" in name or name == "processing_runs"
        )

        # H: restart determinism — byte-identical result from the same stored graph.
        connection.close()
        reopened = open_sqlite_database(database)
        try:
            restarted = compose_sqlite_lecture_analysis_input_eligibility_service(
                reopened
            ).evaluate(intake_id)
        finally:
            reopened.close()

        validation = validate_database(str(database))

        return {
            # Deterministic, content-derived facts (golden).
            "schema_version": SQLITE_SCHEMA_VERSION,
            "intake_id": intake_id,
            "revision_1_id": revision_1,
            "revision_2_id": revision_2,
            "no_raw": _result_dict(no_raw),
            "raw_only": _result_dict(raw_only),
            "raw_fallback": _result_dict(raw_fallback),
            "eligible_first": _result_dict(eligible_first),
            "eligible_second": _result_dict(eligible_second),
            "inapplicable": _result_dict(inapplicable),
            "unknown": _result_dict(unknown),
            "repository_validation": validation.health.value,
            # Behavioral checks.
            "corrected_authority_required": not no_raw.eligible
            and not raw_only.eligible and not raw_fallback.eligible
            and [b.value for b in raw_only.blocking_reasons]
            == ["corrected_transcript_not_selected"]
            and [b.value for b in raw_fallback.blocking_reasons]
            == ["corrected_transcript_not_selected"],
            "eligible_exposes_exact_lineage": eligible_first.eligible
            and eligible_first.corrected_revision_id.value == revision_1
            and eligible_first.parent_raw_transcript_id == raw.raw_transcript_id
            and eligible_first.source_media_id == media.identity
            and eligible_first.segment_count == 2
            and eligible_first.content_fingerprint is not None,
            "eligibility_resolves_only_current_authority": eligible_second.eligible
            and eligible_second.corrected_revision_id.value == revision_2
            and eligible_second.content_fingerprint
            != eligible_first.content_fingerprint,
            "inapplicable_selection_never_falls_back": not inapplicable.eligible
            and [b.value for b in inapplicable.blocking_reasons]
            == ["corrected_selection_not_applicable"]
            and inapplicable.inapplicability_reason == "parent_raw_transcript_not_current",
            "unknown_intake_is_stable_ineligibility": not unknown.eligible
            and [b.value for b in unknown.blocking_reasons] == ["intake_not_found"],
            "derived_only_nothing_persisted": derived_only and no_analysis_rows,
            "restart_produces_identical_result": _result_dict(restarted)
            == _result_dict(inapplicable),
            "repository_validates_healthy": validation.health.value == "healthy"
            and validation.ok,
        }


def _golden(summary: dict) -> dict:
    keys = (
        "schema_version",
        "intake_id",
        "revision_1_id",
        "revision_2_id",
        "no_raw",
        "raw_only",
        "raw_fallback",
        "eligible_first",
        "eligible_second",
        "inapplicable",
        "unknown",
        "repository_validation",
    )
    return {key: summary[key] for key in keys}


def main() -> int:
    print(json.dumps(run_analysis_input_eligibility_demo(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
