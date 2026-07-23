"""In-process acceptance for the Concrete Edit Candidate Generation Provider — First Slice (042 §9.2).

Reuses the durable Transcript Pipeline chain, records the ELIGIBLE Eligible Analysis Input and a located
canonical Analysis Finding, then runs the provider-neutral generation orchestration against a **deterministic
fake provider Port** (no network, no credential) and verifies the full first slice end to end:

    Analysis Finding + bounded corrected-transcript context -> fake provider -> validated proposals
        -> existing Edit Candidate admission -> durable canonical Edit Candidates.

It confirms bounded-context construction (only overlapping segments, no canonical identities transmitted),
a partial-success outcome (valid admitted, invalid surfaced as diagnostics), Candidate Type registry
enforcement, provenance to the Finding, that no Review artifact or provider-native metadata reaches
persistence, and deterministic replay into a fresh equivalent database.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lectureos.application import (
    AnalysisFindingIdentityPlan,
    EditCandidateIdentityPlan,
    GeneratedProposal,
    GenerationOutcomeKind,
    LectureAnalysisInputIdentityPlan,
    NormalizedAnalysisFinding,
    NormalizedAnalysisResult,
)
from lectureos.application.edit_candidate import EDIT_CANDIDATE_RESULT_KIND
from lectureos.application.identities import (
    AnalysisFindingId,
    EditCandidateId,
    EligibleAnalysisInputId,
    TranscriptReadinessEvaluationId,
)
from lectureos.composition import (
    compose_sqlite_analysis_finding_service,
    compose_sqlite_edit_candidate_generation_service,
    compose_sqlite_lecture_analysis_input_service,
)
from lectureos.execution.identities import DomainResultId, SourceTimelineId
from lectureos.persistence import (
    SQLiteAnalysisFindingRepository,
    SQLiteEditCandidateRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.subtitle_intake_acceptance import TIMELINE_ID, _build_persisted_readiness

_READY = TranscriptReadinessEvaluationId("rdy-int-accept")
_INPUT = EligibleAnalysisInputId("generation-input")
_FINDING = AnalysisFindingId("generation-finding")


class FakeEditCandidateGenerationPort:
    """A deterministic in-process generation provider; no network, no credential, no clock."""

    def __init__(self, proposals=(), *, error=None) -> None:
        self._proposals = tuple(proposals)
        self._error = error
        self.captured_requests = []

    def generate_candidates(self, request):
        self.captured_requests.append(request)
        if self._error is not None:
            raise self._error
        return self._proposals


def _planner(count):
    return tuple(
        EditCandidateIdentityPlan(
            candidate_id=EditCandidateId(f"gen-candidate-{index}"),
            candidate_result_id=DomainResultId(f"gen-candidate-{index}-result"),
        )
        for index in range(count)
    )


def _seed_located_finding(connection, execution, run_id, execution_id):
    input_service = compose_sqlite_lecture_analysis_input_service(connection, execution)
    input_service.record_input(
        source_readiness_id=_READY,
        run_id=run_id,
        unit_execution_id=execution_id,
        identities=LectureAnalysisInputIdentityPlan(
            input_id=_INPUT,
            input_result_id=DomainResultId("generation-input-result"),
        ),
    )
    finding_service = compose_sqlite_analysis_finding_service(connection, execution)
    finding_service.record_findings(
        source_input_id=_INPUT,
        run_id=run_id,
        unit_execution_id=execution_id,
        result=NormalizedAnalysisResult(
            source_timeline_id=SourceTimelineId(TIMELINE_ID),
            findings=(
                NormalizedAnalysisFinding(
                    finding_type="low_educational_value",
                    evidence="an off-topic aside appears mid-lecture",
                    range_start=0.5,
                    range_end=1.5,
                ),
            ),
        ),
        identities=(
            AnalysisFindingIdentityPlan(
                finding_id=_FINDING,
                finding_result_id=DomainResultId("generation-finding-result"),
            ),
        ),
    )


def _partial_success_proposals():
    # Two valid proposals (within the bounded context window) and one invalid (unknown Type) -> partial.
    return (
        GeneratedProposal(
            candidate_type="non_lecture_region",
            rationale="the speaker digresses into off-topic chatter",
            range_start=0.5,
            range_end=1.2,
        ),
        GeneratedProposal(
            candidate_type="redundant_restatement",
            rationale="the same point is restated immediately after",
            range_start=1.0,
            range_end=1.5,
        ),
        GeneratedProposal(
            candidate_type="Remove This Clip",  # not a registry key -> rejected
            rationale="delete it",
            range_start=0.5,
            range_end=1.0,
        ),
    )


def _run_generation(connection, execution, run_id, execution_id):
    _seed_located_finding(connection, execution, run_id, execution_id)
    port = FakeEditCandidateGenerationPort(_partial_success_proposals())
    service = compose_sqlite_edit_candidate_generation_service(
        connection, execution, port, context_window_seconds=15.0
    )
    outcome = service.generate(
        source_finding_id=_FINDING,
        run_id=run_id,
        unit_execution_id=execution_id,
        identity_planner=_planner,
    )
    return outcome, port


def run_edit_candidate_generation_acceptance() -> dict:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "acceptance.sqlite3"
        connection = initialize_sqlite_database(path)
        execution, run_id, execution_id, _revision, _raw = _build_persisted_readiness(
            connection
        )
        finding_repo = SQLiteAnalysisFindingRepository(connection)

        outcome, port = _run_generation(connection, execution, run_id, execution_id)
        finding = finding_repo.get(_FINDING)

        partial_success = outcome.kind is GenerationOutcomeKind.PARTIAL_SUCCESS
        admitted = outcome.admitted
        admitted_count = 0 if admitted is None else len(admitted.candidates)
        rejected_surfaced = (
            len(outcome.rejected) == 1
            and outcome.rejected[0].failure_category == "unknown_candidate_type"
        )

        # Bounded context: the fake provider received only overlapping segments and no canonical identity.
        request = port.captured_requests[0]
        bounded_context = (
            len(port.captured_requests) == 1
            and all(
                seg.start is not None and seg.end is not None
                for seg in request.context_segments
            )
            and not hasattr(request, "finding_id")
            and not hasattr(request, "source_media_id")
        )
        registry_offered = set(request.allowed_candidate_types) == {
            "non_lecture_region",
            "redundant_restatement",
            "delivery_concern",
        }

        anchored = admitted is not None and all(
            item.candidate.source_finding_id == _FINDING for item in admitted.candidates
        )
        provenance_linked = admitted is not None and all(
            item.candidate_result.kind == EDIT_CANDIDATE_RESULT_KIND
            and item.candidate_result.upstream_results == (finding.domain_result_id,)
            and item.candidate.source_media_id == finding.source_media_id
            and item.candidate.source_timeline_id == finding.source_timeline_id
            for item in admitted.candidates
        )
        ranges_within_context = admitted is not None and all(
            request.context_window_start
            <= item.candidate.range_start
            <= item.candidate.range_end
            <= request.context_window_end
            for item in admitted.candidates
        )
        types_from_registry = admitted is not None and all(
            item.candidate.candidate_type
            in {"non_lecture_region", "redundant_restatement"}
            for item in admitted.candidates
        )
        upstream_unmutated = finding_repo.get(_FINDING) == finding

        existing_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        # No analysis Review-item table exists; the Edit-Pipeline Review (v27) tables exist but must stay
        # empty — generation creates no Review record.
        review_rows = tuple(
            connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("edit_review_decisions", "approved_edit_decisions")
        )
        no_review_tables = (
            not {"review_items_analysis", "candidate_references_analysis"} & existing_tables
            and all(count == 0 for count in review_rows)
        )
        # The persisted canonical row carries no provider metadata columns (only the §9.1 minimum).
        candidate_columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(edit_candidates)").fetchall()
        }
        no_provider_columns = not {
            "model",
            "prompt",
            "provider",
            "raw_response",
            "tokens",
            "confidence",
            "priority",
        } & candidate_columns
        connection.close()

        reopened = open_sqlite_database(path)
        candidate_repo = SQLiteEditCandidateRepository(reopened)
        restart_reconstructed = admitted is not None and all(
            candidate_repo.get(item.candidate.identity) == item.candidate
            for item in admitted.candidates
        )
        reopened.close()

        # Deterministic replay into a fresh equivalent database with the same fake proposals.
        replay_path = Path(directory) / "replay.sqlite3"
        replay_connection = initialize_sqlite_database(replay_path)
        r_execution, r_run, r_exec, _, _ = _build_persisted_readiness(replay_connection)
        r_outcome, _ = _run_generation(replay_connection, r_execution, r_run, r_exec)
        replay_connection.close()
        deterministic_replay = (
            r_outcome.kind is GenerationOutcomeKind.PARTIAL_SUCCESS
            and r_outcome.admitted is not None
            and admitted is not None
            and tuple(item.candidate for item in r_outcome.admitted.candidates)
            == tuple(item.candidate for item in admitted.candidates)
        )

        return {
            "partial_success": partial_success,
            "admitted_count": admitted_count,
            "rejected_surfaced": rejected_surfaced,
            "bounded_context": bounded_context,
            "registry_offered": registry_offered,
            "anchored_to_finding": anchored,
            "provenance_linked": provenance_linked,
            "ranges_within_context": ranges_within_context,
            "types_from_registry": types_from_registry,
            "upstream_unmutated": upstream_unmutated,
            "no_review_tables": no_review_tables,
            "no_provider_columns": no_provider_columns,
            "restart_reconstructed": restart_reconstructed,
            "deterministic_replay": deterministic_replay,
        }


def main() -> int:
    print(json.dumps(run_edit_candidate_generation_acceptance(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
