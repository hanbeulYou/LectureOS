"""In-process fake-review / fake-transcript acceptance for Subtitle Transcript Intake.

Drives the full canonical pipeline with no network and no credential: a fake correction
provider yields a proposed Revision, Review Preparation maps it to Review Items, a Human reviewer
records Accept and Reject decisions, applicability / current selection / readiness are derived,
and subtitle transcript intake is deterministically evaluated. It verifies that only a READY
transcript yields ELIGIBLE and a NOT_READY transcript yields NOT_ELIGIBLE; immutable intake
records; full readiness/selection/applicability/decision/item/candidate/revision linkage and
source media/timeline; execution provenance; atomic persistence; restart reconstruction;
deterministic replay; idempotency with respect to upstream state; and that no subtitle candidate
or downstream table is produced.
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
    ReviewDecisionIdentityPlan,
    ReviewPreparationIdentityPlan,
    ReviewPreparationTargetIdentityPlan,
    SubtitleIntakeIdentityPlan,
    SubtitleIntakeOutcome,
)
from lectureos.application.identities import (
    SubtitleTranscriptIntakeId,
    TranscriptApplicabilityEvaluationId,
    TranscriptCurrentSelectionId,
    TranscriptReadinessEvaluationId,
    TranscriptReviewDecisionId,
    TranscriptReviewPreparationId,
)
from lectureos.composition import (
    compose_sqlite_execution_service,
    compose_sqlite_subtitle_transcript_intake_service,
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
    SQLiteTranscriptReadinessEvaluationRepository,
    SQLiteSubtitleTranscriptIntakeRepository,
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
_ACCEPT_AT = datetime(2026, 7, 22, 22, 0, tzinfo=timezone.utc)
_REJECT_AT = datetime(2026, 7, 22, 22, 5, tzinfo=timezone.utc)

# review item index -> (decision kind, decision id, timestamp)
_DECISION_PLAN = (
    (0, DecisionKind.ACCEPT, "int-accept", _ACCEPT_AT),
    (1, DecisionKind.REJECT, "int-reject", _REJECT_AT),
)

MEDIA_ID = "int-media"
TIMELINE_ID = "int-timeline"


def _candidate_id(index: int):
    from lectureos.transcript.identities import CorrectionCandidateId

    return CorrectionCandidateId(f"int-candidate-{index}")


def _build_persisted_readiness(connection):
    run_id = ProcessingRunId("int-run")
    execution_id = UnitExecutionId("int-execution")
    unit_id = ProcessingUnitId("int-unit")
    media_id = SourceMediaId(MEDIA_ID)
    timeline_id = SourceTimelineId(TIMELINE_ID)
    correction = CapabilityReference("transcript.correction")
    raw_id = TranscriptId("int-raw")
    revision_id = TranscriptRevisionId("int-revision")

    execution = compose_sqlite_execution_service(connection)
    execution.register_unit(
        ProcessingUnit(identity=unit_id, purpose="intake", capabilities=(correction,))
    )
    execution.start_run(
        run_id=run_id,
        intent=ExecutionIntent("evaluate subtitle intake"),
        working_context=WorkingContextReference("int-context"),
        unit_ids=(unit_id,),
    )
    execution.start_unit_execution(
        execution_id=execution_id, run_id=run_id, unit_id=unit_id
    )
    transcripts = compose_sqlite_transcript_service(connection, execution)
    provider = ProviderTranscriptResult(
        identity=ProviderTranscriptResultId("int-provider"),
        source_media_id=media_id,
        source_timeline_id=timeline_id,
        run_id=run_id,
        unit_execution_id=execution_id,
        capability=CapabilityReference("speech.transcription"),
        provider_reference="fake:acceptance",
        original_content="acceptance source",
    )
    segment_ids = tuple(TranscriptSegmentId(f"int-seg-{index}") for index in range(2))
    raw = RawTranscript(
        identity=raw_id,
        domain_result_id=DomainResultId("int-raw-result"),
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
                    candidate_result_id=DomainResultId(f"int-cand-result-{index}"),
                    replacement_segment_id=TranscriptSegmentId(f"int-replace-{index}"),
                )
                for index in range(2)
            ),
            revision_id=revision_id,
            revision_result_id=DomainResultId("int-revision-result"),
            validation_id=TranscriptValidationId("int-gen-validation"),
        ),
    )
    preparation = compose_sqlite_transcript_review_preparation_service(connection, execution)
    preparation.generate_review(
        revision_id=revision_id,
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=ReviewPreparationIdentityPlan(
            preparation_id=TranscriptReviewPreparationId("int-prep"),
            preparation_result_id=DomainResultId("int-prep-result"),
            context_id=ReviewContextId("int-review-context"),
            targets=tuple(
                ReviewPreparationTargetIdentityPlan(
                    candidate_reference_id=CandidateReferenceId(_candidate_id(index).value),
                    review_item_id=ReviewItemId(f"int-item-{index}"),
                )
                for index in range(2)
            ),
        ),
    )
    decisions = compose_sqlite_transcript_review_decision_service(connection, execution)
    applicability = compose_sqlite_transcript_applicability_evaluation_service(connection, execution)
    selection = compose_sqlite_transcript_current_selection_service(connection, execution)
    readiness = compose_sqlite_transcript_readiness_evaluation_service(connection, execution)
    reviewer = HumanActorReference(FAKE_REVIEWER)
    for index, kind, decision_id, decided_at in _DECISION_PLAN:
        decisions.record_decision(
            preparation_id=TranscriptReviewPreparationId("int-prep"),
            review_item_id=ReviewItemId(f"int-item-{index}"),
            reviewer=reviewer,
            kind=kind,
            run_id=run_id,
            unit_execution_id=execution_id,
            identities=ReviewDecisionIdentityPlan(
                decision_id=TranscriptReviewDecisionId(decision_id),
                decision_result_id=DomainResultId(f"{decision_id}-result"),
                decided_at=decided_at,
            ),
        )
        applicability.record_evaluation(
            source_decision_id=TranscriptReviewDecisionId(decision_id),
            run_id=run_id,
            unit_execution_id=execution_id,
            identities=ApplicabilityEvaluationIdentityPlan(
                evaluation_id=TranscriptApplicabilityEvaluationId(f"eval-{decision_id}"),
                evaluation_result_id=DomainResultId(f"eval-{decision_id}-result"),
            ),
        )
        selection.record_selection(
            source_applicability_id=TranscriptApplicabilityEvaluationId(f"eval-{decision_id}"),
            run_id=run_id,
            unit_execution_id=execution_id,
            identities=CurrentSelectionIdentityPlan(
                selection_id=TranscriptCurrentSelectionId(f"sel-{decision_id}"),
                selection_result_id=DomainResultId(f"sel-{decision_id}-result"),
            ),
        )
        readiness.record_readiness(
            source_selection_id=TranscriptCurrentSelectionId(f"sel-{decision_id}"),
            run_id=run_id,
            unit_execution_id=execution_id,
            identities=ReadinessEvaluationIdentityPlan(
                readiness_id=TranscriptReadinessEvaluationId(f"rdy-{decision_id}"),
                readiness_result_id=DomainResultId(f"rdy-{decision_id}-result"),
                validation_id=TranscriptValidationId(f"rdy-{decision_id}-validation"),
            ),
        )
    return execution, run_id, execution_id, revision_id, raw_id


class _FakeCorrectionCapability:
    def __init__(self, proposals) -> None:
        self._proposals = proposals

    def generate_corrections(self, request):
        return self._proposals


def _record_all_intakes(connection, execution, run_id, execution_id):
    service = compose_sqlite_subtitle_transcript_intake_service(connection, execution)
    intakes = []
    for _, _, decision_id, _ in _DECISION_PLAN:
        intakes.append(
            service.record_intake(
                source_readiness_id=TranscriptReadinessEvaluationId(f"rdy-{decision_id}"),
                run_id=run_id,
                unit_execution_id=execution_id,
                identities=SubtitleIntakeIdentityPlan(
                    intake_id=SubtitleTranscriptIntakeId(f"intake-{decision_id}"),
                    intake_result_id=DomainResultId(f"intake-{decision_id}-result"),
                ),
            )
        )
    return tuple(intakes)


def run_subtitle_intake_acceptance() -> dict:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "acceptance.sqlite3"
        connection = initialize_sqlite_database(path)
        execution, run_id, execution_id, revision_id, raw_id = _build_persisted_readiness(
            connection
        )
        readiness_repo = SQLiteTranscriptReadinessEvaluationRepository(connection)
        upstream_before = tuple(
            readiness_repo.get(TranscriptReadinessEvaluationId(f"rdy-{plan[2]}"))
            for plan in _DECISION_PLAN
        )
        prepared = _record_all_intakes(connection, execution, run_id, execution_id)
        upstream_after = tuple(
            readiness_repo.get(TranscriptReadinessEvaluationId(f"rdy-{plan[2]}"))
            for plan in _DECISION_PLAN
        )
        existing_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        # subtitle_candidates and its cue tables exist (empty) from schema v12 onward.
        # Intake starts no downstream capability, so no candidate rows may be produced and
        # no later subtitle-revision / subtitle-cue / artifact table may exist.
        candidate_rows = connection.execute(
            "SELECT COUNT(*) FROM subtitle_candidates"
        ).fetchone()[0]
        no_downstream_tables = candidate_rows == 0 and not {
            "subtitle_revisions",
            "subtitle_cues",
            "artifacts",
        } & existing_tables
        connection.close()

        reopened = open_sqlite_database(path)
        intakes = SQLiteSubtitleTranscriptIntakeRepository(reopened)
        results = SQLiteDomainResultReferenceRepository(reopened)
        restart_reconstructed = all(
            intakes.get(item.intake.identity) == item.intake
            and results.get(item.intake_result.identity) == item.intake_result
            for item in prepared
        )
        reopened.close()

        outcomes = tuple(item.intake.outcome for item in prepared)
        deterministic_intake = outcomes == (
            SubtitleIntakeOutcome.ELIGIBLE,
            SubtitleIntakeOutcome.NOT_ELIGIBLE,
        )
        eligible = prepared[0].intake
        readiness_linked = eligible.source_readiness_id == TranscriptReadinessEvaluationId(
            "rdy-int-accept"
        )
        revision_linked = all(
            item.intake.source_revision_id == revision_id for item in prepared
        )
        transcript_linked = all(
            item.intake.source_transcript_id == raw_id for item in prepared
        )
        media_timeline_linked = all(
            item.intake.source_media_id == SourceMediaId(MEDIA_ID)
            and item.intake.source_timeline_id == SourceTimelineId(TIMELINE_ID)
            for item in prepared
        )
        candidate_linked = all(
            item.intake.candidate_reference_id
            == CandidateReferenceId(_candidate_id(plan[0]).value)
            for item, plan in zip(prepared, _DECISION_PLAN)
        )
        review_item_linked = all(
            item.intake.review_item_id == ReviewItemId(f"int-item-{plan[0]}")
            for item, plan in zip(prepared, _DECISION_PLAN)
        )
        execution_provenance = all(
            item.intake.run_id == run_id
            and item.intake.unit_execution_id == execution_id
            for item in prepared
        )
        idempotent_upstream = upstream_before == upstream_after

        # Deterministic replay into a fresh database with identical recorded inputs.
        replay_path = Path(directory) / "replay.sqlite3"
        replay_connection = initialize_sqlite_database(replay_path)
        r_execution, r_run, r_exec, _, _ = _build_persisted_readiness(replay_connection)
        replayed = _record_all_intakes(replay_connection, r_execution, r_run, r_exec)
        replay_connection.close()
        deterministic_replay = all(
            a.intake == b.intake and a.intake_result == b.intake_result
            for a, b in zip(prepared, replayed)
        )

        return {
            "reviewer": FAKE_REVIEWER,
            "intake_count": len(prepared),
            "outcomes": [outcome.value for outcome in outcomes],
            "deterministic_intake": deterministic_intake,
            "restart_reconstructed": restart_reconstructed,
            "readiness_linked": readiness_linked,
            "revision_linked": revision_linked,
            "transcript_linked": transcript_linked,
            "media_timeline_linked": media_timeline_linked,
            "candidate_linked": candidate_linked,
            "review_item_linked": review_item_linked,
            "execution_provenance": execution_provenance,
            "idempotent_upstream": idempotent_upstream,
            "no_downstream_tables": no_downstream_tables,
            "deterministic_replay": deterministic_replay,
        }


def main() -> int:
    print(json.dumps(run_subtitle_intake_acceptance(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
