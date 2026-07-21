"""In-process fake-provider / fake-review acceptance for Transcript Review Preparation.

Drives the full canonical pipeline with no network and no credential: a fake correction
capability produces proposals, the correction Application persists one proposed Revision,
the Review Preparation Application maps it to canonical Review Items, and the atomic v6
persistence is reconstructed after restart. It verifies deterministic generation, immutable
lineage, parent Revision linkage, Candidate linkage, execution provenance, atomic
persistence, restart reconstruction and structural integrity.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lectureos.application import (
    CorrectionCandidateIdentityPlan,
    CorrectionGenerationIdentityPlan,
    CorrectionProposal,
    ReviewPreparationIdentityPlan,
    ReviewPreparationTargetIdentityPlan,
    TranscriptReviewPreparationService,
)
from lectureos.application.identities import TranscriptReviewPreparationId
from lectureos.composition import (
    compose_sqlite_execution_service,
    compose_sqlite_transcript_correction_generation_service,
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
    SQLiteReviewCandidateReferenceRepository,
    SQLiteReviewContextRepository,
    SQLiteReviewItemRepository,
    SQLiteTranscriptReviewPreparationRepository,
    open_sqlite_database,
)
from lectureos.review.identities import (
    CandidateReferenceId,
    ReviewContextId,
    ReviewItemId,
)
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

FAKE_PROVIDER = "fake:transcript.correction"


class FakeCorrectionCapability:
    """A deterministic in-process correction provider; no network, no credential."""

    def __init__(self, proposals: tuple[CorrectionProposal, ...]) -> None:
        self._proposals = proposals

    def generate_corrections(self, request) -> tuple[CorrectionProposal, ...]:
        return self._proposals


def run_review_preparation_acceptance() -> dict:
    run_id = ProcessingRunId("prep-run")
    execution_id = UnitExecutionId("prep-execution")
    unit_id = ProcessingUnitId("prep-unit")
    media_id = SourceMediaId("acceptance-media")
    timeline_id = SourceTimelineId("acceptance-timeline")
    correction = CapabilityReference("transcript.correction")
    raw_id = TranscriptId("acceptance-raw")
    revision_id = TranscriptRevisionId("acceptance-revision")

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "acceptance.sqlite3"
        from lectureos.persistence import initialize_sqlite_database

        connection = initialize_sqlite_database(path)
        execution = compose_sqlite_execution_service(connection)
        execution.register_unit(
            ProcessingUnit(
                identity=unit_id,
                purpose="prepare transcript review",
                capabilities=(correction,),
            )
        )
        execution.start_run(
            run_id=run_id,
            intent=ExecutionIntent("prepare transcript review"),
            working_context=WorkingContextReference("acceptance-context"),
            unit_ids=(unit_id,),
        )
        execution.start_unit_execution(
            execution_id=execution_id, run_id=run_id, unit_id=unit_id
        )

        transcripts = compose_sqlite_transcript_service(connection, execution)
        provider = ProviderTranscriptResult(
            identity=ProviderTranscriptResultId("acceptance-provider"),
            source_media_id=media_id,
            source_timeline_id=timeline_id,
            run_id=run_id,
            unit_execution_id=execution_id,
            capability=CapabilityReference("speech.transcription"),
            provider_reference="fake:acceptance",
            original_content="acceptance source content",
        )
        segment_ids = (TranscriptSegmentId("seg-0"), TranscriptSegmentId("seg-1"))
        raw = RawTranscript(
            identity=raw_id,
            domain_result_id=DomainResultId("acceptance-raw-result"),
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
            connection, execution, FakeCorrectionCapability(proposals)
        )
        generated = generation.generate_correction(
            transcript_id=raw_id,
            parent_revision_id=None,
            run_id=run_id,
            unit_execution_id=execution_id,
            capability=correction,
            identities=CorrectionGenerationIdentityPlan(
                candidates=tuple(
                    CorrectionCandidateIdentityPlan(
                        candidate_id=raw_candidate_id(index),
                        candidate_result_id=DomainResultId(f"cand-result-{index}"),
                        replacement_segment_id=TranscriptSegmentId(f"replace-{index}"),
                    )
                    for index in range(2)
                ),
                revision_id=revision_id,
                revision_result_id=DomainResultId("acceptance-revision-result"),
                validation_id=TranscriptValidationId("acceptance-validation"),
            ),
        )
        if generated.revision is None:
            connection.close()
            return {"provider": FAKE_PROVIDER, "review_item_count": 0}

        preparation_plan = ReviewPreparationIdentityPlan(
            preparation_id=TranscriptReviewPreparationId("acceptance-preparation"),
            preparation_result_id=DomainResultId("acceptance-preparation-result"),
            context_id=ReviewContextId("acceptance-context"),
            targets=tuple(
                ReviewPreparationTargetIdentityPlan(
                    candidate_reference_id=CandidateReferenceId(
                        raw_candidate_id(index).value
                    ),
                    review_item_id=ReviewItemId(f"review-item-{index}"),
                )
                for index in range(2)
            ),
        )
        preparation_query = TranscriptReviewPreparationService(transcripts, execution)
        first = preparation_query.prepare_review(
            revision_id=revision_id,
            run_id=run_id,
            unit_execution_id=execution_id,
            identities=preparation_plan,
        )
        second = preparation_query.prepare_review(
            revision_id=revision_id,
            run_id=run_id,
            unit_execution_id=execution_id,
            identities=preparation_plan,
        )
        deterministic = first == second

        service = compose_sqlite_transcript_review_preparation_service(
            connection, execution
        )
        prepared = service.generate_review(
            revision_id=revision_id,
            run_id=run_id,
            unit_execution_id=execution_id,
            identities=preparation_plan,
        )
        connection.close()

        reopened = open_sqlite_database(path)
        preparation = SQLiteTranscriptReviewPreparationRepository(reopened).get(
            prepared.preparation.identity
        )
        context = SQLiteReviewContextRepository(reopened).get(prepared.context.identity)
        items = SQLiteReviewItemRepository(reopened)
        references = SQLiteReviewCandidateReferenceRepository(reopened)
        result = SQLiteDomainResultReferenceRepository(reopened).get(
            prepared.preparation_result.identity
        )
        restart_reconstructed = (
            preparation == prepared.preparation
            and context == prepared.context
            and result == prepared.preparation_result
            and all(
                items.get(item.identity) == item for item in prepared.review_items
            )
            and all(
                references.get(reference.identity) == reference
                for reference in prepared.candidate_references
            )
        )
        reopened.close()

        candidates_linked = tuple(
            reference.identity.value for reference in prepared.candidate_references
        ) == tuple(candidate.identity.value for candidate in generated.candidates)
        parent_revision_linked = (
            generated.revision.parent_raw_transcript_id == raw_id
            and preparation.source_revision_id == revision_id
        )
        lineage_immutable = (
            preparation.source_transcript_id == raw_id
            and result.upstream_results == (generated.revision.domain_result_id,)
        )
        execution_provenance = (
            preparation.run_id == run_id
            and preparation.unit_execution_id == execution_id
        )

        return {
            "provider": FAKE_PROVIDER,
            "proposal_count": len(generated.proposals),
            "review_item_count": preparation.item_count,
            "group_count": len(preparation.groups),
            "deterministic": deterministic,
            "restart_reconstructed": restart_reconstructed,
            "structural_valid": preparation.structural_valid,
            "provenance_complete": preparation.provenance_complete,
            "ordering_valid": preparation.ordering_valid,
            "lineage_immutable": lineage_immutable,
            "parent_revision_linked": parent_revision_linked,
            "candidates_linked": candidates_linked,
            "execution_provenance": execution_provenance,
        }


def raw_candidate_id(index: int):
    from lectureos.transcript.identities import CorrectionCandidateId

    return CorrectionCandidateId(f"acceptance-candidate-{index}")


def main() -> int:
    print(json.dumps(run_review_preparation_acceptance(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
