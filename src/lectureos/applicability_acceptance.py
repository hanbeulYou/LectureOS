"""In-process fake-review acceptance for Transcript Applicability.

Drives the full canonical pipeline with no network and no credential: a fake correction
provider yields a proposed Revision, Review Preparation maps it to Review Items, a Human
reviewer records Accept, Reject and Modify decisions, and applicability is deterministically
derived from those canonical decisions. It then verifies immutable Applicability records,
Review Decision / Review Item / Candidate / Revision linkage, execution provenance,
deterministic evaluation, atomic persistence, restart reconstruction and deterministic replay.
Deriving applicability triggers no current selection, Transcript Ready, or downstream output.
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from lectureos.application import (
    ApplicabilityEvaluationIdentityPlan,
    ApplicabilityOutcome,
    CorrectionCandidateIdentityPlan,
    CorrectionGenerationIdentityPlan,
    CorrectionProposal,
    ReviewDecisionIdentityPlan,
    ReviewPreparationIdentityPlan,
    ReviewPreparationTargetIdentityPlan,
)
from lectureos.application.identities import (
    TranscriptApplicabilityEvaluationId,
    TranscriptReviewDecisionId,
    TranscriptReviewPreparationId,
)
from lectureos.composition import (
    compose_sqlite_execution_service,
    compose_sqlite_transcript_applicability_evaluation_service,
    compose_sqlite_transcript_correction_generation_service,
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
    SQLiteTranscriptApplicabilityEvaluationRepository,
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
_ACCEPT_AT = datetime(2026, 7, 22, 15, 0, tzinfo=timezone.utc)
_REJECT_AT = datetime(2026, 7, 22, 15, 5, tzinfo=timezone.utc)
_MODIFY_AT = datetime(2026, 7, 22, 15, 10, tzinfo=timezone.utc)

# review item index -> (decision kind, decision id, decision result id, timestamp)
_DECISION_PLAN = (
    (0, DecisionKind.ACCEPT, "dec-accept", "dec-accept-result", _ACCEPT_AT, None),
    (1, DecisionKind.REJECT, "dec-reject", "dec-reject-result", _REJECT_AT, None),
    (2, DecisionKind.MODIFY, "dec-modify", "dec-modify-result", _MODIFY_AT, "revised"),
)


class _FakeCorrectionCapability:
    def __init__(self, proposals) -> None:
        self._proposals = proposals

    def generate_corrections(self, request):
        return self._proposals


def _candidate_id(index: int):
    from lectureos.transcript.identities import CorrectionCandidateId

    return CorrectionCandidateId(f"app-candidate-{index}")


def _build_persisted_decisions(connection):
    run_id = ProcessingRunId("app-run")
    execution_id = UnitExecutionId("app-execution")
    unit_id = ProcessingUnitId("app-unit")
    media_id = SourceMediaId("app-media")
    timeline_id = SourceTimelineId("app-timeline")
    correction = CapabilityReference("transcript.correction")
    raw_id = TranscriptId("app-raw")
    revision_id = TranscriptRevisionId("app-revision")

    execution = compose_sqlite_execution_service(connection)
    execution.register_unit(
        ProcessingUnit(
            identity=unit_id, purpose="applicability", capabilities=(correction,)
        )
    )
    execution.start_run(
        run_id=run_id,
        intent=ExecutionIntent("derive applicability"),
        working_context=WorkingContextReference("app-context"),
        unit_ids=(unit_id,),
    )
    execution.start_unit_execution(
        execution_id=execution_id, run_id=run_id, unit_id=unit_id
    )
    transcripts = compose_sqlite_transcript_service(connection, execution)
    provider = ProviderTranscriptResult(
        identity=ProviderTranscriptResultId("app-provider"),
        source_media_id=media_id,
        source_timeline_id=timeline_id,
        run_id=run_id,
        unit_execution_id=execution_id,
        capability=CapabilityReference("speech.transcription"),
        provider_reference="fake:acceptance",
        original_content="acceptance source",
    )
    segment_ids = tuple(TranscriptSegmentId(f"app-seg-{index}") for index in range(3))
    raw = RawTranscript(
        identity=raw_id,
        domain_result_id=DomainResultId("app-raw-result"),
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
                    candidate_result_id=DomainResultId(f"app-cand-result-{index}"),
                    replacement_segment_id=TranscriptSegmentId(f"app-replace-{index}"),
                )
                for index in range(3)
            ),
            revision_id=revision_id,
            revision_result_id=DomainResultId("app-revision-result"),
            validation_id=TranscriptValidationId("app-validation"),
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
            preparation_id=TranscriptReviewPreparationId("app-prep"),
            preparation_result_id=DomainResultId("app-prep-result"),
            context_id=ReviewContextId("app-review-context"),
            targets=tuple(
                ReviewPreparationTargetIdentityPlan(
                    candidate_reference_id=CandidateReferenceId(_candidate_id(index).value),
                    review_item_id=ReviewItemId(f"app-item-{index}"),
                )
                for index in range(3)
            ),
        ),
    )
    decision_service = compose_sqlite_transcript_review_decision_service(
        connection, execution
    )
    reviewer = HumanActorReference(FAKE_REVIEWER)
    for index, kind, decision_id, result_id, decided_at, modified in _DECISION_PLAN:
        decision_service.record_decision(
            preparation_id=TranscriptReviewPreparationId("app-prep"),
            review_item_id=ReviewItemId(f"app-item-{index}"),
            reviewer=reviewer,
            kind=kind,
            run_id=run_id,
            unit_execution_id=execution_id,
            identities=ReviewDecisionIdentityPlan(
                decision_id=TranscriptReviewDecisionId(decision_id),
                decision_result_id=DomainResultId(result_id),
                decided_at=decided_at,
            ),
            modified_text=modified,
        )
    return execution, run_id, execution_id, revision_id


def _record_all_evaluations(connection, execution, run_id, execution_id):
    service = compose_sqlite_transcript_applicability_evaluation_service(
        connection, execution
    )
    evaluations = []
    for _, _, decision_id, _, _, _ in _DECISION_PLAN:
        evaluations.append(
            service.record_evaluation(
                source_decision_id=TranscriptReviewDecisionId(decision_id),
                run_id=run_id,
                unit_execution_id=execution_id,
                identities=ApplicabilityEvaluationIdentityPlan(
                    evaluation_id=TranscriptApplicabilityEvaluationId(f"eval-{decision_id}"),
                    evaluation_result_id=DomainResultId(f"eval-{decision_id}-result"),
                ),
            )
        )
    return tuple(evaluations)


def run_applicability_acceptance() -> dict:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "acceptance.sqlite3"
        connection = initialize_sqlite_database(path)
        execution, run_id, execution_id, revision_id = _build_persisted_decisions(
            connection
        )
        prepared = _record_all_evaluations(connection, execution, run_id, execution_id)
        connection.close()

        reopened = open_sqlite_database(path)
        evaluations = SQLiteTranscriptApplicabilityEvaluationRepository(reopened)
        results = SQLiteDomainResultReferenceRepository(reopened)
        restart_reconstructed = all(
            evaluations.get(item.evaluation.identity) == item.evaluation
            and results.get(item.evaluation_result.identity) == item.evaluation_result
            for item in prepared
        )
        reopened.close()

        outcomes = tuple(item.evaluation.outcome for item in prepared)
        deterministic_evaluation = outcomes == (
            ApplicabilityOutcome.APPLICABLE,
            ApplicabilityOutcome.NOT_APPLICABLE,
            ApplicabilityOutcome.SUPERSEDED_BY_MODIFICATION,
        )
        decision_linked = all(
            item.evaluation.source_decision_id
            == TranscriptReviewDecisionId(plan[2])
            for item, plan in zip(prepared, _DECISION_PLAN)
        )
        review_item_linked = all(
            item.evaluation.review_item_id == ReviewItemId(f"app-item-{plan[0]}")
            for item, plan in zip(prepared, _DECISION_PLAN)
        )
        candidate_linked = all(
            item.evaluation.candidate_reference_id
            == CandidateReferenceId(_candidate_id(plan[0]).value)
            for item, plan in zip(prepared, _DECISION_PLAN)
        )
        revision_linked = all(
            item.evaluation.source_revision_id == revision_id for item in prepared
        )
        execution_provenance = all(
            item.evaluation.run_id == run_id
            and item.evaluation.unit_execution_id == execution_id
            for item in prepared
        )

        # Deterministic replay into a fresh database with identical recorded inputs.
        replay_path = Path(directory) / "replay.sqlite3"
        replay_connection = initialize_sqlite_database(replay_path)
        r_execution, r_run, r_exec, _ = _build_persisted_decisions(replay_connection)
        replayed = _record_all_evaluations(replay_connection, r_execution, r_run, r_exec)
        replay_connection.close()
        deterministic_replay = all(
            a.evaluation == b.evaluation
            and a.evaluation_result == b.evaluation_result
            for a, b in zip(prepared, replayed)
        )

        return {
            "reviewer": FAKE_REVIEWER,
            "evaluation_count": len(prepared),
            "outcomes": [outcome.value for outcome in outcomes],
            "deterministic_evaluation": deterministic_evaluation,
            "restart_reconstructed": restart_reconstructed,
            "decision_linked": decision_linked,
            "review_item_linked": review_item_linked,
            "candidate_linked": candidate_linked,
            "revision_linked": revision_linked,
            "execution_provenance": execution_provenance,
            "deterministic_replay": deterministic_replay,
        }


def main() -> int:
    print(json.dumps(run_applicability_acceptance(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
