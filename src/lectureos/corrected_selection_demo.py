"""Deterministic demonstration of Current Corrected Revision Selection (040 §20, GOAL-011).

Drives the whole authority slice with fake provider results, manual candidates, and explicit human decisions —
no LLM, ASR, network, or model:

    Raw Transcript → Candidate A/B → Accept → Generate Revision A/B (not auto-selected)
                  → Select A → resolve (corrected) → replay Select A (reused)
                  → Select B (changed) → Raw Fallback (changed) → resolve (raw) → re-Select A (changed)
                  → Candidate A Rejected → selection history unchanged, resolver reports INAPPLICABLE,
                    re-selecting A is blocked → Repository Validation

It proves the §63–§67 scenarios: selection is explicit and append-only (generation never auto-selects); replay
reuses; transitions append with full history preserved; explicit Raw fallback is a distinguishable authority fact
that deletes nothing; the effective resolver returns raw / corrected / explicit-inapplicable (never a silent
fallback); a later Candidate Reject mutates no history and blocks only new selection; revisions, candidates,
decisions, and the Raw Transcript remain immutable; validation stays healthy; and the committed golden reproduces
byte-for-byte.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lectureos.application.correction_candidate_admission import (
    build_correction_candidate_input,
)
from lectureos.application.corrected_revision_selection import (
    RevisionNotEligibleError,
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
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.persistence import (
    SQLiteCorrectedTranscriptRevisionRepository,
    SQLiteRawTranscriptRepository,
    SQLiteTranscriptSegmentRepository,
    initialize_sqlite_database,
)
from lectureos.transcript.identities import TranscriptRevisionId
from lectureos.validation import validate_database

_MEDIA_FIXTURES = Path(__file__).resolve().parents[2] / "examples" / "media-import" / "fixtures"
_SOURCE_TEXT = "안녕하세요 여러부"


def run_corrected_selection_demo(media_fixtures_directory: str | None = None) -> dict:
    fixtures = Path(media_fixtures_directory) if media_fixtures_directory else _MEDIA_FIXTURES
    sample = fixtures / "sample-a.bin"

    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "lectureos.sqlite3"
        connection = initialize_sqlite_database(database)

        media = compose_sqlite_media_import_service(connection).import_media(str(sample)).record
        intake = compose_sqlite_transcript_source_intake_service(connection).admit(
            media.identity.value
        ).intake
        intake_id = intake.identity.value
        raw = compose_sqlite_provider_transcript_admission_service(connection).admit(
            intake_id=intake_id,
            document=build_provider_transcript_document(
                {"provider": "fake-asr", "model": "tiny", "language": "ko", "provider_result_ref": "A",
                 "segments": [{"start": 0.0, "end": 2.5, "text": _SOURCE_TEXT}]}
            ),
        ).admission
        compose_sqlite_current_raw_transcript_selection_service(connection).select(
            intake_id, raw.raw_transcript_id.value
        )
        raw_transcript = SQLiteRawTranscriptRepository(connection).get(raw.raw_transcript_id)
        segment = raw_transcript.segment_ids[0]
        segment_text_before = SQLiteTranscriptSegmentRepository(connection).get(segment).text

        admissions = compose_sqlite_correction_candidate_admission_service(connection)
        decisions = compose_sqlite_correction_candidate_decision_service(connection)
        generator = compose_sqlite_corrected_revision_generation_service(connection)

        def _revision(ref: str, proposed: str) -> tuple[str, str]:
            candidate = admissions.admit(
                intake_id=intake_id,
                candidate=build_correction_candidate_input(
                    {"raw_transcript_id": raw.raw_transcript_id.value, "segment_id": segment.value,
                     "candidate_ref": ref, "source_type": "manual", "source_reference": "human:editor-1",
                     "proposed_text": proposed, "source_text_snapshot": _SOURCE_TEXT,
                     "rationale": "맞춤법 교정"}
                ),
            ).candidate
            decisions.decide(candidate_id=candidate.identity.value, kind="accept", reviewer="reviewer:kim")
            return (
                candidate.identity.value,
                generator.generate(candidate_id=candidate.identity.value).revision.identity.value,
            )

        candidate_a, revision_a = _revision("c1", "안녕하세요 여러분")
        candidate_b, revision_b = _revision("c2", "안녕하세요, 여러분!")

        selection = compose_sqlite_corrected_revision_selection_service(connection)

        no_history_state = selection.selection_state(intake_id)
        generation_did_not_auto_select = selection.current(intake_id) is None
        resolve_no_history = selection.resolve_effective_transcript(intake_id)

        select_a = selection.select_revision(revision_id=revision_a, reviewer="selector:kim")
        replay_a = selection.select_revision(revision_id=revision_a, reviewer="selector:lee")
        resolve_a = selection.resolve_effective_transcript(intake_id)
        select_b = selection.select_revision(revision_id=revision_b, reviewer="selector:kim")
        fallback = selection.select_raw_fallback(intake_id=intake_id, reviewer="selector:kim")
        fallback_replay = selection.select_raw_fallback(intake_id=intake_id, reviewer="selector:lee")
        resolve_fallback = selection.resolve_effective_transcript(intake_id)
        reselect_a = selection.select_revision(revision_id=revision_a, reviewer="selector:kim")
        history = selection.history(intake_id)

        # Later Reject: history untouched, resolver explicit-inapplicable, new selection blocked.
        decisions.decide(candidate_id=candidate_a, kind="reject", reviewer="reviewer:kim")
        current_after_reject = selection.current(intake_id)
        resolve_after_reject = selection.resolve_effective_transcript(intake_id)
        selection.select_raw_fallback(intake_id=intake_id, reviewer="selector:kim")
        reselect_rejected_blocked = False
        try:
            selection.select_revision(revision_id=revision_a, reviewer="selector:kim")
        except RevisionNotEligibleError:
            reselect_rejected_blocked = True

        revision_a_persisted = (
            SQLiteCorrectedTranscriptRevisionRepository(connection).get(
                TranscriptRevisionId(revision_a)
            )
            is not None
        )
        segment_text_after = SQLiteTranscriptSegmentRepository(connection).get(segment).text
        final_history = selection.history(intake_id)
        connection.close()
        validation = validate_database(str(database))

        return {
            # Deterministic, content-derived facts (golden).
            "intake_id": intake_id,
            "revision_a_id": revision_a,
            "revision_b_id": revision_b,
            "selection_a_id": select_a.selection.identity.value,
            "fallback_id": fallback.selection.identity.value,
            "history_length": len(final_history),
            # Behavioral checks.
            "no_history_before_selection": no_history_state.value == "no_history"
            and resolve_no_history.effective_kind.value == "raw_transcript",
            "generation_did_not_auto_select": generation_did_not_auto_select,
            "select_recorded": select_a.outcome.value == "recorded" and select_a.selection.sequence == 0,
            "replay_reused": replay_a.outcome.value == "reused",
            "resolve_returns_corrected": resolve_a.effective_kind.value == "corrected_revision"
            and resolve_a.corrected_revision_id.value == revision_a,
            "transition_appends": select_b.outcome.value == "changed"
            and fallback.outcome.value == "changed"
            and reselect_a.outcome.value == "changed",
            "fallback_replay_reused": fallback_replay.outcome.value == "reused",
            "fallback_resolves_raw": resolve_fallback.selection_state.value == "raw_fallback"
            and resolve_fallback.effective_kind.value == "raw_transcript",
            "history_preserves_all_transitions": [s.kind.value for s in history]
            == ["corrected_revision", "corrected_revision", "raw_fallback", "corrected_revision"],
            "later_reject_keeps_selection": current_after_reject is not None
            and current_after_reject.corrected_revision_id is not None
            and current_after_reject.corrected_revision_id.value == revision_a,
            "later_reject_resolves_inapplicable": resolve_after_reject.effective_kind.value
            == "inapplicable_selection"
            and resolve_after_reject.inapplicability_reason == "candidate_not_accepted",
            "reselect_rejected_blocked": reselect_rejected_blocked,
            "revision_a_persisted": revision_a_persisted,
            "raw_transcript_immutable": segment_text_before == segment_text_after == _SOURCE_TEXT,
            "repository_validates_healthy": validation.health.value == "healthy" and validation.ok,
        }


def _golden(summary: dict) -> dict:
    keys = (
        "intake_id",
        "revision_a_id",
        "revision_b_id",
        "selection_a_id",
        "fallback_id",
        "history_length",
    )
    return {key: summary[key] for key in keys}


def main() -> int:
    print(json.dumps(run_corrected_selection_demo(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
