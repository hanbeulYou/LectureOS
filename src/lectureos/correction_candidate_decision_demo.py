"""Deterministic demonstration of the first Human Authority Decision (040 §18).

Drives the whole authority slice with fake provider results and manual candidates — no LLM, ASR, network, or
model — proving that Human Accept/Reject decisions are recorded as append-only, immutable, replay-safe authority
that never mutates the candidate or the Raw Transcript and applies nothing:

    Fixture Source Media → Transcript Intake → Provider Result → Raw Transcript
                        → Current Raw Transcript Selection → Correction Candidate Admission
                        → Undecided → Accept → replay Accept → Reject → re-Accept
                        → decision history → current authority → Repository Validation

It exercises the authority evolution examples (§51 A/B/C/D): Accept, Reject, Accept→Reject, Reject→Accept. It
proves: Undecided is derived from absence; Accept/Reject recorded deterministically; replay is idempotent;
switching authority appends history without deleting prior records; only Accepted candidates are eligible for
future revision; the Candidate and Raw Transcript remain immutable; validation stays healthy; and the committed
golden reproduces byte-for-byte.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lectureos.application.correction_candidate_admission import (
    build_correction_candidate_input,
)
from lectureos.application.correction_candidate_decision import (
    CorrectionCandidateDecisionError,
    HumanDecisionStatus,
)
from lectureos.application.provider_transcript_admission import (
    build_provider_transcript_document,
)
from lectureos.composition import (
    compose_sqlite_correction_candidate_admission_service,
    compose_sqlite_correction_candidate_decision_service,
    compose_sqlite_current_raw_transcript_selection_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.persistence import (
    SQLiteCorrectionCandidateAdmissionRepository,
    SQLiteRawTranscriptRepository,
    SQLiteTranscriptSegmentRepository,
    initialize_sqlite_database,
)
from lectureos.validation import validate_database

_MEDIA_FIXTURES = Path(__file__).resolve().parents[2] / "examples" / "media-import" / "fixtures"
_SEGMENT_TEXT = "안녕하세요 여러부"


def run_correction_candidate_decision_demo(media_fixtures_directory: str | None = None) -> dict:
    fixtures = Path(media_fixtures_directory) if media_fixtures_directory else _MEDIA_FIXTURES
    sample = fixtures / "sample-a.bin"

    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "lectureos.sqlite3"
        connection = initialize_sqlite_database(database)

        media = compose_sqlite_media_import_service(connection).import_media(str(sample)).record
        intake = compose_sqlite_transcript_source_intake_service(connection).admit(
            media.identity.value
        ).intake
        raw = compose_sqlite_provider_transcript_admission_service(connection).admit(
            intake_id=intake.identity.value,
            document=build_provider_transcript_document(
                {"provider": "fake-asr", "model": "tiny", "language": "ko", "provider_result_ref": "A",
                 "segments": [{"start": 0.0, "end": 2.5, "text": _SEGMENT_TEXT},
                              {"start": 2.5, "end": 5.0, "text": "오늘 강의를 시작합니다"}]}
            ),
        ).admission
        raw_transcript = SQLiteRawTranscriptRepository(connection).get(raw.raw_transcript_id)
        segment_id = raw_transcript.segment_ids[0]
        segment_text_before = SQLiteTranscriptSegmentRepository(connection).get(segment_id).text
        compose_sqlite_current_raw_transcript_selection_service(connection).select(
            intake.identity.value, raw.raw_transcript_id.value
        )
        candidate = compose_sqlite_correction_candidate_admission_service(connection).admit(
            intake_id=intake.identity.value,
            candidate=build_correction_candidate_input(
                {"raw_transcript_id": raw.raw_transcript_id.value, "segment_id": segment_id.value,
                 "candidate_ref": "c1", "source_type": "manual", "source_reference": "human:editor-1",
                 "proposed_text": "안녕하세요 여러분", "source_text_snapshot": segment_text_before,
                 "rationale": "맞춤법 교정"}
            ),
        ).candidate
        candidate_id = candidate.identity.value

        decisions = compose_sqlite_correction_candidate_decision_service(connection)

        undecided = decisions.authority(candidate_id)
        accept = decisions.decide(candidate_id=candidate_id, kind="accept", reviewer="reviewer:kim")
        accept_authority = decisions.authority(candidate_id)
        replay = decisions.decide(candidate_id=candidate_id, kind="accept", reviewer="reviewer:lee")
        reject = decisions.decide(candidate_id=candidate_id, kind="reject", reviewer="reviewer:kim", rationale="다시 검토")
        reject_authority = decisions.authority(candidate_id)
        re_accept = decisions.decide(candidate_id=candidate_id, kind="accept", reviewer="reviewer:park")
        final_authority = decisions.authority(candidate_id)
        history = decisions.history(candidate_id)

        # Modify and unknown candidate are rejected.
        modify_rejected = False
        try:
            decisions.decide(candidate_id=candidate_id, kind="modify", reviewer="x")
        except CorrectionCandidateDecisionError:
            modify_rejected = True
        unknown_rejected = False
        try:
            decisions.decide(candidate_id="correction-candidate:" + "0" * 64, kind="accept", reviewer="x")
        except CorrectionCandidateDecisionError:
            unknown_rejected = True

        candidate_after = SQLiteCorrectionCandidateAdmissionRepository(connection).candidate(candidate.identity)
        segment_text_after = SQLiteTranscriptSegmentRepository(connection).get(segment_id).text
        connection.close()
        validation = validate_database(str(database))

        return {
            # Deterministic, content-derived facts (golden).
            "candidate_id": candidate_id,
            "accept_decision_id": accept.decision.identity.value,
            "reject_decision_id": reject.decision.identity.value,
            "re_accept_decision_id": re_accept.decision.identity.value,
            "decision_count": len(history),
            # Behavioral checks.
            "undecided_before_any_decision": undecided.status == HumanDecisionStatus.UNDECIDED
            and undecided.decision_count == 0,
            "accept_recorded": accept.outcome.value == "recorded" and accept.decision.sequence == 0,
            "accepted_eligible_for_revision": accept_authority.status == HumanDecisionStatus.ACCEPTED
            and accept_authority.eligible_for_revision,
            "replay_reused": replay.outcome.value == "reused",
            "reject_changed_authority": reject.outcome.value == "changed"
            and reject.decision.sequence == 1
            and reject_authority.status == HumanDecisionStatus.REJECTED
            and not reject_authority.eligible_for_revision,
            "re_accept_appends_history": re_accept.outcome.value == "changed"
            and re_accept.decision.sequence == 2,
            "history_is_append_only": [d.kind.value for d in history] == ["accept", "reject", "accept"],
            "current_authority_accepted": final_authority.status == HumanDecisionStatus.ACCEPTED,
            "modify_rejected": modify_rejected,
            "unknown_candidate_rejected": unknown_rejected,
            "candidate_immutable": candidate_after.proposed_text == "안녕하세요 여러분",
            "raw_transcript_immutable": segment_text_before == segment_text_after == _SEGMENT_TEXT,
            "repository_validates_healthy": validation.health.value == "healthy" and validation.ok,
        }


def _golden(summary: dict) -> dict:
    keys = (
        "candidate_id",
        "accept_decision_id",
        "reject_decision_id",
        "re_accept_decision_id",
        "decision_count",
    )
    return {key: summary[key] for key in keys}


def main() -> int:
    print(json.dumps(run_correction_candidate_decision_demo(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
