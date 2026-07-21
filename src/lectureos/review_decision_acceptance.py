"""In-process fake-review acceptance for Transcript Human Review Decision.

Drives the full canonical pipeline with no network and no credential: a fake correction
provider yields a proposed Revision, Review Preparation maps it to durable Review Items, and a
Human reviewer records Accept, Reject and Modify decisions (including an append-only second
decision on one item). It then verifies immutable Decision records, Review Item / Candidate /
Revision linkage, reviewer and execution provenance, atomic persistence, restart
reconstruction and deterministic replay. Decision recording triggers no downstream automation.
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from lectureos.application import (
    CorrectionCandidateIdentityPlan,
    CorrectionGenerationIdentityPlan,
    CorrectionProposal,
    ReviewDecisionIdentityPlan,
    ReviewPreparationIdentityPlan,
    ReviewPreparationTargetIdentityPlan,
)
from lectureos.application.identities import (
    TranscriptReviewDecisionId,
    TranscriptReviewPreparationId,
)
from lectureos.composition import (
    compose_sqlite_execution_service,
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
    SQLiteTranscriptReviewDecisionRepository,
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
_ACCEPT_AT = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)
_MODIFY_AT = datetime(2026, 7, 22, 12, 5, tzinfo=timezone.utc)
_REJECT_AT = datetime(2026, 7, 22, 12, 10, tzinfo=timezone.utc)


class _FakeCorrectionCapability:
    def __init__(self, proposals) -> None:
        self._proposals = proposals

    def generate_corrections(self, request):
        return self._proposals


def _build_preparation(connection):
    run_id = ProcessingRunId("dec-run")
    execution_id = UnitExecutionId("dec-execution")
    unit_id = ProcessingUnitId("dec-unit")
    media_id = SourceMediaId("dec-media")
    timeline_id = SourceTimelineId("dec-timeline")
    correction = CapabilityReference("transcript.correction")
    raw_id = TranscriptId("dec-raw")
    revision_id = TranscriptRevisionId("dec-revision")

    execution = compose_sqlite_execution_service(connection)
    execution.register_unit(
        ProcessingUnit(
            identity=unit_id, purpose="review decisions", capabilities=(correction,)
        )
    )
    execution.start_run(
        run_id=run_id,
        intent=ExecutionIntent("record human review decisions"),
        working_context=WorkingContextReference("dec-context"),
        unit_ids=(unit_id,),
    )
    execution.start_unit_execution(
        execution_id=execution_id, run_id=run_id, unit_id=unit_id
    )
    transcripts = compose_sqlite_transcript_service(connection, execution)
    provider = ProviderTranscriptResult(
        identity=ProviderTranscriptResultId("dec-provider"),
        source_media_id=media_id,
        source_timeline_id=timeline_id,
        run_id=run_id,
        unit_execution_id=execution_id,
        capability=CapabilityReference("speech.transcription"),
        provider_reference="fake:acceptance",
        original_content="acceptance source",
    )
    segment_ids = (TranscriptSegmentId("dec-seg-0"), TranscriptSegmentId("dec-seg-1"))
    raw = RawTranscript(
        identity=raw_id,
        domain_result_id=DomainResultId("dec-raw-result"),
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
        for index in range(2)
    )
    transcripts.register_provider_result(provider)
    transcripts.create_raw_transcript(raw, segments)

    proposals = tuple(
        CorrectionProposal(
            target_segment_id=segment_ids[index],
            proposed_text=f"corrected line {index}",
            rationale="acceptance correction",
        )
        for index in range(2)
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
                    candidate_result_id=DomainResultId(f"dec-cand-result-{index}"),
                    replacement_segment_id=TranscriptSegmentId(f"dec-replace-{index}"),
                )
                for index in range(2)
            ),
            revision_id=revision_id,
            revision_result_id=DomainResultId("dec-revision-result"),
            validation_id=TranscriptValidationId("dec-validation"),
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
            preparation_id=TranscriptReviewPreparationId("dec-prep"),
            preparation_result_id=DomainResultId("dec-prep-result"),
            context_id=ReviewContextId("dec-review-context"),
            targets=tuple(
                ReviewPreparationTargetIdentityPlan(
                    candidate_reference_id=CandidateReferenceId(_candidate_id(index).value),
                    review_item_id=ReviewItemId(f"dec-item-{index}"),
                )
                for index in range(2)
            ),
        ),
    )
    return execution, run_id, execution_id, revision_id


def _candidate_id(index: int):
    from lectureos.transcript.identities import CorrectionCandidateId

    return CorrectionCandidateId(f"dec-candidate-{index}")


def _record_all_decisions(connection, execution, run_id, execution_id):
    service = compose_sqlite_transcript_review_decision_service(connection, execution)
    reviewer = HumanActorReference(FAKE_REVIEWER)
    accept = service.record_decision(
        preparation_id=TranscriptReviewPreparationId("dec-prep"),
        review_item_id=ReviewItemId("dec-item-0"),
        reviewer=reviewer,
        kind=DecisionKind.ACCEPT,
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=ReviewDecisionIdentityPlan(
            decision_id=TranscriptReviewDecisionId("dec-accept"),
            decision_result_id=DomainResultId("dec-accept-result"),
            decided_at=_ACCEPT_AT,
        ),
        rationale="accept item 0",
    )
    modify = service.record_decision(
        preparation_id=TranscriptReviewPreparationId("dec-prep"),
        review_item_id=ReviewItemId("dec-item-0"),
        reviewer=reviewer,
        kind=DecisionKind.MODIFY,
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=ReviewDecisionIdentityPlan(
            decision_id=TranscriptReviewDecisionId("dec-modify"),
            decision_result_id=DomainResultId("dec-modify-result"),
            decided_at=_MODIFY_AT,
        ),
        sequence=1,
        previous_decision_id=TranscriptReviewDecisionId("dec-accept"),
        rationale="revise item 0",
        modified_text="human revised line 0",
    )
    reject = service.record_decision(
        preparation_id=TranscriptReviewPreparationId("dec-prep"),
        review_item_id=ReviewItemId("dec-item-1"),
        reviewer=reviewer,
        kind=DecisionKind.REJECT,
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=ReviewDecisionIdentityPlan(
            decision_id=TranscriptReviewDecisionId("dec-reject"),
            decision_result_id=DomainResultId("dec-reject-result"),
            decided_at=_REJECT_AT,
        ),
        rationale="reject item 1",
    )
    return (accept, modify, reject)


def run_review_decision_acceptance() -> dict:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "acceptance.sqlite3"
        connection = initialize_sqlite_database(path)
        execution, run_id, execution_id, revision_id = _build_preparation(connection)
        prepared = _record_all_decisions(connection, execution, run_id, execution_id)
        connection.close()

        reopened = open_sqlite_database(path)
        decisions = SQLiteTranscriptReviewDecisionRepository(reopened)
        results = SQLiteDomainResultReferenceRepository(reopened)
        restart_reconstructed = all(
            decisions.get(item.decision.identity) == item.decision for item in prepared
        )
        results_reconstructed = all(
            results.get(item.decision_result.identity) == item.decision_result
            for item in prepared
        )
        reopened.close()

        accept, modify, reject = prepared
        kinds = tuple(item.decision.kind for item in prepared)
        review_item_linked = (
            accept.decision.review_item_id == ReviewItemId("dec-item-0")
            and reject.decision.review_item_id == ReviewItemId("dec-item-1")
        )
        candidate_linked = accept.decision.candidate_reference_id == CandidateReferenceId(
            "dec-candidate-0"
        )
        revision_linked = all(
            item.decision.source_revision_id == revision_id for item in prepared
        )
        reviewer_provenance = all(
            item.decision.reviewer == HumanActorReference(FAKE_REVIEWER)
            for item in prepared
        )
        execution_provenance = all(
            item.decision.run_id == run_id
            and item.decision.unit_execution_id == execution_id
            for item in prepared
        )
        append_only_lineage = (
            modify.decision.sequence == 1
            and modify.decision.previous_decision_id
            == TranscriptReviewDecisionId("dec-accept")
        )

        # Deterministic replay into a fresh database with identical recorded inputs.
        replay_path = Path(directory) / "replay.sqlite3"
        replay_connection = initialize_sqlite_database(replay_path)
        r_execution, r_run, r_exec, _ = _build_preparation(replay_connection)
        replayed = _record_all_decisions(replay_connection, r_execution, r_run, r_exec)
        replay_connection.close()
        deterministic_replay = all(
            a.decision == b.decision and a.decision_result == b.decision_result
            for a, b in zip(prepared, replayed)
        )

        return {
            "reviewer": FAKE_REVIEWER,
            "decision_count": len(prepared),
            "kinds": [kind.value for kind in kinds],
            "restart_reconstructed": restart_reconstructed and results_reconstructed,
            "review_item_linked": review_item_linked,
            "candidate_linked": candidate_linked,
            "revision_linked": revision_linked,
            "reviewer_provenance": reviewer_provenance,
            "execution_provenance": execution_provenance,
            "append_only_lineage": append_only_lineage,
            "deterministic_replay": deterministic_replay,
        }


def main() -> int:
    print(json.dumps(run_review_decision_acceptance(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
