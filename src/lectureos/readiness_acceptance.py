"""In-process fake-review / fake-transcript acceptance for Transcript Ready State.

Drives the full canonical pipeline with no network and no credential: a fake correction
provider yields a proposed Revision, Review Preparation maps it to Review Items, a Human
reviewer records Accept, Reject and Modify decisions, applicability is derived, current
selection is derived, and Transcript readiness is deterministically evaluated from those
canonical records. It verifies that only the accepted-selected-applicable-valid Revision is
READY, that rejected and modified lineages are NOT_READY, immutable readiness records, full
linkage and provenance, atomic persistence, restart reconstruction, deterministic replay,
idempotency with respect to upstream state, and that no downstream Subtitle or Artifact record
is produced.
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from lectureos.application import (
    ApplicabilityEvaluationIdentityPlan,
    CorrectionCandidateIdentityPlan,
    CorrectionGenerationIdentityPlan,
    CorrectionProposal,
    CurrentSelectionIdentityPlan,
    ReadinessEvaluationIdentityPlan,
    ReadinessOutcome,
    ReadinessReasonCode,
    ReviewDecisionIdentityPlan,
    ReviewPreparationIdentityPlan,
    ReviewPreparationTargetIdentityPlan,
)
from lectureos.application.identities import (
    TranscriptApplicabilityEvaluationId,
    TranscriptCurrentSelectionId,
    TranscriptReadinessEvaluationId,
    TranscriptReviewDecisionId,
    TranscriptReviewPreparationId,
)
from lectureos.composition import (
    compose_sqlite_execution_service,
    compose_sqlite_transcript_applicability_evaluation_service,
    compose_sqlite_transcript_correction_generation_service,
    compose_sqlite_transcript_current_selection_service,
    compose_sqlite_transcript_readiness_evaluation_service,
    compose_sqlite_transcript_review_decision_service,
    compose_sqlite_transcript_review_preparation_service,
    compose_sqlite_transcript_service,
)
from lectureos.execution.identities import (
    CapabilityReference,
    DomainResultId,
    ProcessingRunId,
    ProcessingUnitId,
    SourceMediaId,
    SourceTimelineId,
    UnitExecutionId,
    WorkingContextReference,
)
from lectureos.execution.models import ExecutionIntent, ProcessingUnit
from lectureos.persistence import (
    SQLiteDomainResultReferenceRepository,
    SQLiteTranscriptCurrentSelectionRepository,
    SQLiteTranscriptReadinessEvaluationRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.review.identities import (
    CandidateReferenceId,
    HumanActorReference,
    ReviewContextId,
    ReviewItemId,
)
from lectureos.review.models import DecisionKind
from lectureos.transcript.identities import (
    ProviderTranscriptResultId,
    TranscriptId,
    TranscriptRevisionId,
    TranscriptSegmentId,
    TranscriptValidationId,
)
from lectureos.transcript.models import (
    ProviderTranscriptResult,
    RawTranscript,
    TranscriptSegment,
)

FAKE_REVIEWER = "fake:reviewer"
_ACCEPT_AT = datetime(2026, 7, 22, 20, 0, tzinfo=timezone.utc)
_REJECT_AT = datetime(2026, 7, 22, 20, 5, tzinfo=timezone.utc)
_MODIFY_AT = datetime(2026, 7, 22, 20, 10, tzinfo=timezone.utc)

# review item index -> (decision kind, decision id, timestamp, modified text)
_DECISION_PLAN = (
    (0, DecisionKind.ACCEPT, "rdy-accept", _ACCEPT_AT, None),
    (1, DecisionKind.REJECT, "rdy-reject", _REJECT_AT, None),
    (2, DecisionKind.MODIFY, "rdy-modify", _MODIFY_AT, "revised"),
)


class _FakeCorrectionCapability:
    def __init__(self, proposals) -> None:
        self._proposals = proposals

    def generate_corrections(self, request):
        return self._proposals


def _candidate_id(index: int):
    from lectureos.transcript.identities import CorrectionCandidateId

    return CorrectionCandidateId(f"rdy-candidate-{index}")


def _build_persisted_selections(connection):
    run_id = ProcessingRunId("rdy-run")
    execution_id = UnitExecutionId("rdy-execution")
    unit_id = ProcessingUnitId("rdy-unit")
    media_id = SourceMediaId("rdy-media")
    timeline_id = SourceTimelineId("rdy-timeline")
    correction = CapabilityReference("transcript.correction")
    raw_id = TranscriptId("rdy-raw")
    revision_id = TranscriptRevisionId("rdy-revision")

    execution = compose_sqlite_execution_service(connection)
    execution.register_unit(
        ProcessingUnit(identity=unit_id, purpose="readiness", capabilities=(correction,))
    )
    execution.start_run(
        run_id=run_id,
        intent=ExecutionIntent("evaluate transcript readiness"),
        working_context=WorkingContextReference("rdy-context"),
        unit_ids=(unit_id,),
    )
    execution.start_unit_execution(
        execution_id=execution_id, run_id=run_id, unit_id=unit_id
    )
    transcripts = compose_sqlite_transcript_service(connection, execution)
    provider = ProviderTranscriptResult(
        identity=ProviderTranscriptResultId("rdy-provider"),
        source_media_id=media_id,
        source_timeline_id=timeline_id,
        run_id=run_id,
        unit_execution_id=execution_id,
        capability=CapabilityReference("speech.transcription"),
        provider_reference="fake:acceptance",
        original_content="acceptance source",
    )
    segment_ids = tuple(TranscriptSegmentId(f"rdy-seg-{index}") for index in range(3))
    raw = RawTranscript(
        identity=raw_id,
        domain_result_id=DomainResultId("rdy-raw-result"),
        source_media_id=media_id,
        source_timeline_id=timeline_id,
        provider_result_id=provider.identity,
        run_id=run_id,
        unit_execution_id=execution_id,
        segment_ids=segment_ids,
    )
    segments = tuple(
        TranscriptSegment(
            identity=segment_ids[index],
            transcript_id=raw_id,
            source_timeline_id=timeline_id,
            text=f"line {index}",
            source_order=index,
            start=float(index),
            end=float(index) + 1.0,
        )
        for index in range(3)
    )
    transcripts.register_provider_result(provider)
    transcripts.create_raw_transcript(raw, segments)

    proposals = tuple(
        CorrectionProposal(
            target_segment_id=segment_ids[index],
            proposed_text=f"corrected line {index}",
            rationale="acceptance correction",
        )
        for index in range(3)
    )
    generation = compose_sqlite_transcript_correction_generation_service(
        connection, execution, _FakeCorrectionCapability(proposals)
    )
    generation.generate_correction(
        transcript_id=raw_id,
        parent_revision_id=None,
        run_id=run_id,
        unit_execution_id=execution_id,
        capability=correction,
        identities=CorrectionGenerationIdentityPlan(
            candidates=tuple(
                CorrectionCandidateIdentityPlan(
                    candidate_id=_candidate_id(index),
                    candidate_result_id=DomainResultId(f"rdy-cand-result-{index}"),
                    replacement_segment_id=TranscriptSegmentId(f"rdy-replace-{index}"),
                )
                for index in range(3)
            ),
            revision_id=revision_id,
            revision_result_id=DomainResultId("rdy-revision-result"),
            validation_id=TranscriptValidationId("rdy-gen-validation"),
        ),
    )
    preparation_service = compose_sqlite_transcript_review_preparation_service(
        connection, execution
    )
    preparation_service.generate_review(
        revision_id=revision_id,
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=ReviewPreparationIdentityPlan(
            preparation_id=TranscriptReviewPreparationId("rdy-prep"),
            preparation_result_id=DomainResultId("rdy-prep-result"),
            context_id=ReviewContextId("rdy-review-context"),
            targets=tuple(
                ReviewPreparationTargetIdentityPlan(
                    candidate_reference_id=CandidateReferenceId(_candidate_id(index).value),
                    review_item_id=ReviewItemId(f"rdy-item-{index}"),
                )
                for index in range(3)
            ),
        ),
    )
    decision_service = compose_sqlite_transcript_review_decision_service(
        connection, execution
    )
    applicability_service = compose_sqlite_transcript_applicability_evaluation_service(
        connection, execution
    )
    selection_service = compose_sqlite_transcript_current_selection_service(
        connection, execution
    )
    reviewer = HumanActorReference(FAKE_REVIEWER)
    for index, kind, decision_id, decided_at, modified in _DECISION_PLAN:
        decision_service.record_decision(
            preparation_id=TranscriptReviewPreparationId("rdy-prep"),
            review_item_id=ReviewItemId(f"rdy-item-{index}"),
            reviewer=reviewer,
            kind=kind,
            run_id=run_id,
            unit_execution_id=execution_id,
            identities=ReviewDecisionIdentityPlan(
                decision_id=TranscriptReviewDecisionId(decision_id),
                decision_result_id=DomainResultId(f"{decision_id}-result"),
                decided_at=decided_at,
            ),
            modified_text=modified,
        )
        applicability_service.record_evaluation(
            source_decision_id=TranscriptReviewDecisionId(decision_id),
            run_id=run_id,
            unit_execution_id=execution_id,
            identities=ApplicabilityEvaluationIdentityPlan(
                evaluation_id=TranscriptApplicabilityEvaluationId(f"eval-{decision_id}"),
                evaluation_result_id=DomainResultId(f"eval-{decision_id}-result"),
            ),
        )
        selection_service.record_selection(
            source_applicability_id=TranscriptApplicabilityEvaluationId(f"eval-{decision_id}"),
            run_id=run_id,
            unit_execution_id=execution_id,
            identities=CurrentSelectionIdentityPlan(
                selection_id=TranscriptCurrentSelectionId(f"selection-{decision_id}"),
                selection_result_id=DomainResultId(f"selection-{decision_id}-result"),
            ),
        )
    return execution, run_id, execution_id, revision_id


def _record_all_readiness(connection, execution, run_id, execution_id):
    service = compose_sqlite_transcript_readiness_evaluation_service(connection, execution)
    readiness = []
    for _, _, decision_id, _, _ in _DECISION_PLAN:
        readiness.append(
            service.record_readiness(
                source_selection_id=TranscriptCurrentSelectionId(f"selection-{decision_id}"),
                run_id=run_id,
                unit_execution_id=execution_id,
                identities=ReadinessEvaluationIdentityPlan(
                    readiness_id=TranscriptReadinessEvaluationId(f"readiness-{decision_id}"),
                    readiness_result_id=DomainResultId(f"readiness-{decision_id}-result"),
                    validation_id=TranscriptValidationId(f"readiness-{decision_id}-validation"),
                ),
            )
        )
    return tuple(readiness)


def run_readiness_acceptance() -> dict:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "acceptance.sqlite3"
        connection = initialize_sqlite_database(path)
        execution, run_id, execution_id, revision_id = _build_persisted_selections(
            connection
        )
        selection_repo = SQLiteTranscriptCurrentSelectionRepository(connection)
        upstream_before = tuple(
            selection_repo.get(TranscriptCurrentSelectionId(f"selection-{plan[2]}"))
            for plan in _DECISION_PLAN
        )
        prepared = _record_all_readiness(connection, execution, run_id, execution_id)
        upstream_after = tuple(
            selection_repo.get(TranscriptCurrentSelectionId(f"selection-{plan[2]}"))
            for plan in _DECISION_PLAN
        )
        no_downstream_tables = not {
            "subtitles",
            "subtitle_candidates",
            "artifacts",
        } & {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        connection.close()

        reopened = open_sqlite_database(path)
        readiness_repo = SQLiteTranscriptReadinessEvaluationRepository(reopened)
        results = SQLiteDomainResultReferenceRepository(reopened)
        restart_reconstructed = all(
            readiness_repo.get(item.readiness.identity) == item.readiness
            and results.get(item.readiness_result.identity) == item.readiness_result
            for item in prepared
        )
        reopened.close()

        outcomes = tuple(item.readiness.outcome for item in prepared)
        reason_codes = tuple(item.readiness.reason_code for item in prepared)
        deterministic_readiness = outcomes == (
            ReadinessOutcome.READY,
            ReadinessOutcome.NOT_READY,
            ReadinessOutcome.NOT_READY,
        ) and reason_codes == (
            ReadinessReasonCode.ALL_CONDITIONS_MET,
            ReadinessReasonCode.NOT_APPLICABLE,
            ReadinessReasonCode.SUPERSEDED_BY_MODIFICATION,
        )
        ready_item = prepared[0].readiness
        selection_linked = ready_item.source_selection_id == TranscriptCurrentSelectionId(
            "selection-rdy-accept"
        )
        applicability_linked = all(
            item.readiness.source_applicability_id
            == TranscriptApplicabilityEvaluationId(f"eval-{plan[2]}")
            for item, plan in zip(prepared, _DECISION_PLAN)
        )
        decision_linked = all(
            item.readiness.source_decision_id == TranscriptReviewDecisionId(plan[2])
            for item, plan in zip(prepared, _DECISION_PLAN)
        )
        review_item_linked = all(
            item.readiness.review_item_id == ReviewItemId(f"rdy-item-{plan[0]}")
            for item, plan in zip(prepared, _DECISION_PLAN)
        )
        candidate_linked = all(
            item.readiness.candidate_reference_id
            == CandidateReferenceId(_candidate_id(plan[0]).value)
            for item, plan in zip(prepared, _DECISION_PLAN)
        )
        revision_linked = all(
            item.readiness.source_revision_id == revision_id for item in prepared
        )
        validation_linked = all(
            item.readiness.validation_id
            == TranscriptValidationId(f"readiness-{plan[2]}-validation")
            for item, plan in zip(prepared, _DECISION_PLAN)
        )
        ready_structurally_valid = ready_item.structural_valid is True
        execution_provenance = all(
            item.readiness.run_id == run_id
            and item.readiness.unit_execution_id == execution_id
            for item in prepared
        )
        idempotent_upstream = upstream_before == upstream_after

        # Deterministic replay into a fresh database with identical recorded inputs.
        replay_path = Path(directory) / "replay.sqlite3"
        replay_connection = initialize_sqlite_database(replay_path)
        r_execution, r_run, r_exec, _ = _build_persisted_selections(replay_connection)
        replayed = _record_all_readiness(replay_connection, r_execution, r_run, r_exec)
        replay_connection.close()
        deterministic_replay = all(
            a.readiness == b.readiness and a.readiness_result == b.readiness_result
            for a, b in zip(prepared, replayed)
        )

        return {
            "reviewer": FAKE_REVIEWER,
            "readiness_count": len(prepared),
            "outcomes": [outcome.value for outcome in outcomes],
            "reason_codes": [code.value for code in reason_codes],
            "deterministic_readiness": deterministic_readiness,
            "ready_structurally_valid": ready_structurally_valid,
            "restart_reconstructed": restart_reconstructed,
            "selection_linked": selection_linked,
            "applicability_linked": applicability_linked,
            "decision_linked": decision_linked,
            "review_item_linked": review_item_linked,
            "candidate_linked": candidate_linked,
            "revision_linked": revision_linked,
            "validation_linked": validation_linked,
            "execution_provenance": execution_provenance,
            "idempotent_upstream": idempotent_upstream,
            "no_downstream_tables": no_downstream_tables,
            "deterministic_replay": deterministic_replay,
        }


def main() -> int:
    print(json.dumps(run_readiness_acceptance(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
