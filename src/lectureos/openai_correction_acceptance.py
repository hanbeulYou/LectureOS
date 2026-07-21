"""Credentialed synthetic Korean acceptance for the OpenAI correction adapter."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lectureos.application import (
    CorrectionCandidateIdentityPlan,
    CorrectionGenerationIdentityPlan,
)
from lectureos.composition import (
    compose_sqlite_execution_service,
    compose_sqlite_transcript_correction_generation_service,
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
    SQLiteCorrectionCandidateRepository,
    SQLiteCorrectedTranscriptRevisionRepository,
    SQLiteDomainResultReferenceRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.providers import OpenAITranscriptCorrectionAdapter
from lectureos.transcript.identities import (
    CorrectionCandidateId,
    ProviderTranscriptResultId,
    TranscriptId,
    TranscriptRevisionId,
    TranscriptSegmentId,
    TranscriptValidationId,
)
from lectureos.transcript.models import ProviderTranscriptResult, RawTranscript, TranscriptSegment


def run_credentialed_acceptance() -> dict:
    capability = CapabilityReference("transcript.correction")
    run_id = ProcessingRunId("acceptance-run")
    execution_id = UnitExecutionId("acceptance-execution")
    raw_id = TranscriptId("acceptance-raw")
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "acceptance.sqlite3"
        connection = initialize_sqlite_database(path)
        execution = compose_sqlite_execution_service(connection)
        unit_id = ProcessingUnitId("acceptance-unit")
        execution.register_unit(
            ProcessingUnit(
                identity=unit_id,
                purpose="correct Korean transcript",
                capabilities=(capability,),
            )
        )
        execution.start_run(
            run_id=run_id,
            intent=ExecutionIntent("credentialed correction acceptance"),
            working_context=WorkingContextReference("synthetic-context"),
            unit_ids=(unit_id,),
        )
        execution.start_unit_execution(
            execution_id=execution_id, run_id=run_id, unit_id=unit_id
        )
        transcripts = compose_sqlite_transcript_service(connection, execution)
        media_id = SourceMediaId("synthetic-media")
        timeline_id = SourceTimelineId("synthetic-timeline")
        provider = ProviderTranscriptResult(
            identity=ProviderTranscriptResultId("synthetic-provider-result"),
            source_media_id=media_id,
            source_timeline_id=timeline_id,
            run_id=run_id,
            unit_execution_id=execution_id,
            capability=CapabilityReference("speech.transcription"),
            provider_reference="synthetic:acceptance",
            original_content="synthetic Korean classroom sentence",
        )
        segment_id = TranscriptSegmentId("synthetic-segment")
        raw = RawTranscript(
            identity=raw_id,
            domain_result_id=DomainResultId("synthetic-raw-result"),
            source_media_id=media_id,
            source_timeline_id=timeline_id,
            provider_result_id=provider.identity,
            run_id=run_id,
            unit_execution_id=execution_id,
            segment_ids=(segment_id,),
        )
        transcripts.register_provider_result(provider)
        transcripts.create_raw_transcript(
            raw,
            (
                TranscriptSegment(
                    identity=segment_id,
                    transcript_id=raw_id,
                    source_timeline_id=timeline_id,
                    text="윤동주에 서시를 읽겠습니다.",
                    source_order=0,
                    start=0.0,
                    end=2.0,
                ),
            ),
        )
        service = compose_sqlite_transcript_correction_generation_service(
            connection, execution, OpenAITranscriptCorrectionAdapter()
        )
        result = service.generate_correction(
            transcript_id=raw_id,
            parent_revision_id=None,
            run_id=run_id,
            unit_execution_id=execution_id,
            capability=capability,
            identities=CorrectionGenerationIdentityPlan(
                candidates=(
                    CorrectionCandidateIdentityPlan(
                        CorrectionCandidateId("acceptance-candidate"),
                        DomainResultId("acceptance-candidate-result"),
                        TranscriptSegmentId("acceptance-replacement"),
                    ),
                ),
                revision_id=TranscriptRevisionId("acceptance-revision"),
                revision_result_id=DomainResultId("acceptance-revision-result"),
                validation_id=TranscriptValidationId("acceptance-validation"),
            ),
        )
        if result.revision is None:
            connection.close()
            return {
                "provider": "openai:gpt-5.6-terra",
                "proposal_count": 0,
                "canonical_restart_verified": False,
                "structural_valid": None,
            }
        connection.close()
        reopened = open_sqlite_database(path)
        candidate_ok = (
            SQLiteCorrectionCandidateRepository(reopened).get(result.candidates[0].identity)
            == result.candidates[0]
        )
        revision_ok = (
            SQLiteCorrectedTranscriptRevisionRepository(reopened).get(result.revision.identity)
            == result.revision
        )
        results = SQLiteDomainResultReferenceRepository(reopened)
        result_ok = (
            results.get(result.candidate_results[0].identity) == result.candidate_results[0]
            and results.get(result.revision_result.identity) == result.revision_result
        )
        reopened.close()
        return {
            "provider": "openai:gpt-5.6-terra",
            "proposal_count": len(result.proposals),
            "canonical_restart_verified": candidate_ok and revision_ok and result_ok,
            "structural_valid": result.validation.structural_valid,
        }


def main() -> int:
    print(json.dumps(run_credentialed_acceptance(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
