"""Deterministic demonstration of the Effective Transcript Consumption Boundary (040 §21, GOAL-012).

Drives the whole consumption slice with fake provider results, manual candidates, and explicit human
decisions — no LLM, ASR, network, or model:

    Raw R1 selected → consume (no-history raw) → replay (reused)
                   → Candidate → Accept → Revision C1 → Select C1 → consume C1 (created)
                   → replay C1 (reused) → Raw fallback → consume (converges on the R1 binding)
                   → re-Select C1 → Candidate Rejected → new consumption blocked (INAPPLICABLE, no
                     silent fallback), historical bindings intact and derived stale
                   → Raw R2 admitted and selected → consumption blocked (parent mismatch) →
                     fallback → consume R2 (created) → Repository Validation

It proves the §62–§65 scenarios: every acquisition is explicit and resolves solely through the §20
resolver; the exact immutable source identity changes correctly (R1 → C1 → R1 → R2); same-source replay
reuses without duplicate bindings; a source change never incorrectly reuses another source's binding;
later authority changes (Reject, raw switch, fallback) never rewrite, delete, or reinterpret prior
bindings — their currentness is derived; a selected-but-inapplicable revision blocks new consumption
explicitly; and repository validation stays healthy throughout (staleness is never corruption). The
committed golden reproduces byte-for-byte.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lectureos.application.correction_candidate_admission import (
    build_correction_candidate_input,
)
from lectureos.application.effective_transcript_consumption import (
    ConsumptionCurrentness,
    InapplicableSelectedRevisionError,
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
    compose_sqlite_effective_transcript_consumption_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.persistence import (
    SQLiteRawTranscriptRepository,
    SQLiteTranscriptSegmentRepository,
    initialize_sqlite_database,
)
from lectureos.transcript.identities import TranscriptId
from lectureos.validation import validate_database

_MEDIA_FIXTURES = Path(__file__).resolve().parents[2] / "examples" / "media-import" / "fixtures"
_SOURCE_TEXT = "안녕하세요 여러부"


def run_transcript_consumption_demo(media_fixtures_directory: str | None = None) -> dict:
    fixtures = Path(media_fixtures_directory) if media_fixtures_directory else _MEDIA_FIXTURES
    sample = fixtures / "sample-a.bin"

    with tempfile.TemporaryDirectory() as directory:
        database = Path(directory) / "lectureos.sqlite3"
        connection = initialize_sqlite_database(database)

        media = compose_sqlite_media_import_service(connection).import_media(str(sample)).record
        intake_id = compose_sqlite_transcript_source_intake_service(connection).admit(
            media.identity.value
        ).intake.identity.value
        provider = compose_sqlite_provider_transcript_admission_service(connection)
        raw_selection = compose_sqlite_current_raw_transcript_selection_service(connection)

        def _admit_raw(ref: str, text: str) -> str:
            return provider.admit(
                intake_id=intake_id,
                document=build_provider_transcript_document(
                    {"provider": "fake-asr", "model": "tiny", "language": "ko",
                     "provider_result_ref": ref,
                     "segments": [{"start": 0.0, "end": 2.5, "text": text}]}
                ),
            ).admission.raw_transcript_id.value

        raw_1 = _admit_raw("A", _SOURCE_TEXT)
        raw_selection.select(intake_id, raw_1)

        consumption = compose_sqlite_effective_transcript_consumption_service(connection)

        # §62 first acquisition: no-history raw.
        consume_r1 = consumption.consume(intake_id=intake_id)
        replay_r1 = consumption.consume(intake_id=intake_id)

        # Candidate → Accept → Revision C1 → select → consume corrected.
        segment = SQLiteRawTranscriptRepository(connection).get(
            TranscriptId(raw_1)
        ).segment_ids[0]
        candidate = compose_sqlite_correction_candidate_admission_service(connection).admit(
            intake_id=intake_id,
            candidate=build_correction_candidate_input(
                {"raw_transcript_id": raw_1, "segment_id": segment.value,
                 "candidate_ref": "c1", "source_type": "manual",
                 "source_reference": "human:editor-1",
                 "proposed_text": "안녕하세요 여러분", "source_text_snapshot": _SOURCE_TEXT,
                 "rationale": "맞춤법 교정"}
            ),
        ).candidate.identity.value
        decisions = compose_sqlite_correction_candidate_decision_service(connection)
        decisions.decide(candidate_id=candidate, kind="accept", reviewer="reviewer:kim")
        revision = compose_sqlite_corrected_revision_generation_service(connection).generate(
            candidate_id=candidate
        ).revision.identity.value
        selection = compose_sqlite_corrected_revision_selection_service(connection)
        selection.select_revision(revision_id=revision, reviewer="selector:kim")

        consume_c1 = consumption.consume(intake_id=intake_id)
        replay_c1 = consumption.consume(intake_id=intake_id)

        # Explicit raw fallback: consuming again converges on the original R1 binding (same source).
        selection.select_raw_fallback(intake_id=intake_id, reviewer="selector:kim")
        consume_fallback = consumption.consume(intake_id=intake_id)

        # §63 later Reject: existing bindings intact + derived stale; new consumption blocked.
        selection.select_revision(revision_id=revision, reviewer="selector:kim")
        decisions.decide(candidate_id=candidate, kind="reject", reviewer="reviewer:kim")
        reject_blocked = False
        try:
            consumption.consume(intake_id=intake_id)
        except InapplicableSelectedRevisionError:
            reject_blocked = True
        bindings_after_reject = consumption.bindings(intake_id)
        c1_after_reject = next(
            b for b in bindings_after_reject
            if b.identity.value == consume_c1.consumption.identity.value
        )
        c1_currentness_after_reject = consumption.currentness(c1_after_reject)

        # §64 raw switch: C1 stays selected but its parent is no longer current — blocked again.
        raw_2 = _admit_raw("B", "안녕하세요 여러분 다시")
        raw_selection.select(intake_id, raw_2)
        raw_switch_blocked = False
        try:
            consumption.consume(intake_id=intake_id)
        except InapplicableSelectedRevisionError as error:
            raw_switch_blocked = "parent_raw_transcript_not_current" in str(error)
        r1_binding_now = consumption.bindings(intake_id)
        r1_after_switch = next(
            b for b in r1_binding_now
            if b.identity.value == consume_r1.consumption.identity.value
        )
        r1_currentness_after_switch = consumption.currentness(r1_after_switch)

        # Explicit fallback makes R2 consumable — a NEW binding (never reusing the R1/C1 bindings).
        selection.select_raw_fallback(intake_id=intake_id, reviewer="selector:kim")
        consume_r2 = consumption.consume(intake_id=intake_id)

        final_bindings = consumption.bindings(intake_id)
        segment_text_after = SQLiteTranscriptSegmentRepository(connection).get(segment).text
        connection.close()
        validation = validate_database(str(database))

        binding_ids = {b.identity.value for b in final_bindings}
        return {
            # Deterministic, content-derived facts (golden).
            "intake_id": intake_id,
            "raw_1_id": raw_1,
            "raw_2_id": raw_2,
            "revision_id": revision,
            "consumption_r1_id": consume_r1.consumption.identity.value,
            "consumption_c1_id": consume_c1.consumption.identity.value,
            "consumption_r2_id": consume_r2.consumption.identity.value,
            "binding_count": len(final_bindings),
            # Behavioral checks.
            "first_consumption_no_history_raw": consume_r1.outcome.value == "created"
            and consume_r1.consumption.resolution_state.value == "no_history"
            and consume_r1.consumption.source_kind.value == "raw_transcript"
            and consume_r1.consumption.source_transcript_identity == raw_1,
            "same_source_replay_reused": replay_r1.outcome.value == "reused"
            and replay_r1.consumption.identity == consume_r1.consumption.identity,
            "corrected_consumption_created": consume_c1.outcome.value == "created"
            and consume_c1.consumption.source_kind.value == "corrected_transcript_revision"
            and consume_c1.consumption.source_transcript_identity == revision
            and consume_c1.consumption.parent_raw_transcript_id.value == raw_1,
            "corrected_replay_reused": replay_c1.outcome.value == "reused",
            "distinct_sources_distinct_bindings": consume_r1.consumption.identity
            != consume_c1.consumption.identity,
            "fallback_converges_on_r1_binding": consume_fallback.outcome.value == "reused"
            and consume_fallback.consumption.identity == consume_r1.consumption.identity,
            "provenance_distinguishes_no_history_and_fallback": (
                consume_r1.consumption.resolution_state.value == "no_history"
                and consume_fallback.input.selection_state.value == "raw_fallback"
            ),
            "later_reject_blocks_new_consumption": reject_blocked,
            "later_reject_keeps_bindings": len(bindings_after_reject) == 2,
            "later_reject_derives_stale_not_mutates": c1_currentness_after_reject
            is ConsumptionCurrentness.STALE_DUE_TO_SELECTED_REVISION_INAPPLICABILITY
            and c1_after_reject.content_fingerprint == consume_c1.consumption.content_fingerprint,
            "raw_switch_blocks_corrected_consumption": raw_switch_blocked,
            "raw_switch_derives_r1_stale": r1_currentness_after_switch
            is ConsumptionCurrentness.STALE_DUE_TO_RAW_SELECTION_CHANGE,
            "new_source_gets_new_binding": consume_r2.outcome.value == "created"
            and consume_r2.consumption.source_transcript_identity == raw_2
            and consume_r2.consumption.identity.value not in
            {consume_r1.consumption.identity.value, consume_c1.consumption.identity.value},
            "all_bindings_preserved": binding_ids
            == {consume_r1.consumption.identity.value, consume_c1.consumption.identity.value,
                consume_r2.consumption.identity.value},
            "source_segments_immutable": segment_text_after == _SOURCE_TEXT,
            "repository_validates_healthy": validation.health.value == "healthy" and validation.ok,
        }


def _golden(summary: dict) -> dict:
    keys = (
        "intake_id",
        "raw_1_id",
        "raw_2_id",
        "revision_id",
        "consumption_r1_id",
        "consumption_c1_id",
        "consumption_r2_id",
        "binding_count",
    )
    return {key: summary[key] for key in keys}


def main() -> int:
    print(json.dumps(run_transcript_consumption_demo(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
