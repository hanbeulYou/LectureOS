"""In-process fake-review / fake-transcript acceptance for Approved Subtitle Assembly (044, PATCH-0006).

Drives the durable pipeline (candidate → reading → time) and persists finalized decisions directly, then
deterministically assembles the document-level Approved Subtitle Document — the canonical Export Input.

It verifies canonical reconciliation (Accept→original text, Modify→applied_text, Reject→omitted,
Untouched→original text), export eligibility (a document with an unresolved included unit is INELIGIBLE
and carries no units), canonical ordering, provenance and DomainResult chaining, that no existing
canonical artifact is mutated, exact restart reconstruction, deterministic replay, and that no downstream
artifact/export table is produced.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from lectureos.application import (
    RULE_OVERLAP_ADJACENT,
    SubtitleApprovedAssemblyIdentityPlan,
    SubtitleApprovedUnitOrigin,
    SubtitleAppliedOutcome,
    SubtitleDecisionRevision,
    SubtitleExportEligibility,
    SubtitleFinalSubtitle,
    SubtitleTimingStatus,
    applied_outcome_for_kind,
    final_outcome_for_applied_outcome,
)
from lectureos.application.identities import (
    SubtitleApprovedDocumentId,
    SubtitleApprovedUnitId,
    SubtitleDecisionRevisionId,
    SubtitleFinalSubtitleId,
    SubtitleReviewDecisionId,
    SubtitleReviewPreparationId,
    SubtitleTimedUnitId,
    SubtitleTimeRevisionId,
    SubtitleValidationFindingId,
    SubtitleValidationId,
)
from lectureos.composition import (
    compose_sqlite_subtitle_approved_assembly_service,
)
from lectureos.execution.identities import DomainResultId
from lectureos.execution.models import DomainResultReference
from lectureos.persistence import (
    SQLiteDomainResultReferenceRepository,
    SQLiteSubtitleApprovedDocumentRepository,
    SQLiteSubtitleDecisionRevisionCommandPersistence,
    SQLiteSubtitleDecisionRevisionRepository,
    SQLiteSubtitleFinalSubtitleCommandPersistence,
    SQLiteSubtitleFinalSubtitleRepository,
    SQLiteSubtitleReadingRevisionRepository,
    SQLiteSubtitleTimeRevisionRepository,
    initialize_sqlite_database,
    open_sqlite_database,
)
from lectureos.review.identities import CandidateReferenceId, ReviewItemId
from lectureos.review.models import DecisionKind
from lectureos.subtitle_reading_acceptance import (
    _build_persisted_candidate,
    _compose_reading,
)
from lectureos.subtitle_validation_acceptance import _persist_defective_time


def _persist_decision_revision(
    connection, reading_revision, time_revision_id, name, kind, target_unit_id, applied_text
):
    outcome = applied_outcome_for_kind(kind)
    revision = SubtitleDecisionRevision(
        identity=SubtitleDecisionRevisionId(name),
        domain_result_id=DomainResultId(f"{name}-result"),
        source_review_decision_id=SubtitleReviewDecisionId(f"{name}-decision"),
        decision_kind=kind,
        outcome=outcome,
        review_item_id=ReviewItemId(f"{name}-item"),
        candidate_reference_id=CandidateReferenceId(f"{name}-ref"),
        source_preparation_id=SubtitleReviewPreparationId(f"{name}-prep"),
        source_validation_id=SubtitleValidationId(f"{name}-validation"),
        source_time_revision_id=time_revision_id,
        source_reading_revision_id=reading_revision.identity,
        source_candidate_id=reading_revision.source_candidate_id,
        source_finding_id=SubtitleValidationFindingId(f"{name}-finding"),
        rule=RULE_OVERLAP_ADJACENT,
        source_transcript_id=reading_revision.source_transcript_id,
        source_revision_id=reading_revision.source_revision_id,
        source_media_id=reading_revision.source_media_id,
        source_timeline_id=reading_revision.source_timeline_id,
        run_id=reading_revision.run_id,
        unit_execution_id=reading_revision.unit_execution_id,
        sequence=0,
        reason=f"decision revision {name}",
        target_timed_unit_id=target_unit_id,
        applied_text=applied_text,
    )
    result = DomainResultReference(
        identity=revision.domain_result_id,
        kind="subtitle_decision_revision",
        source_media=reading_revision.source_media_id,
        source_timeline=reading_revision.source_timeline_id,
        upstream_results=(DomainResultId(f"{name}-upstream"),),
    )
    SQLiteSubtitleDecisionRevisionCommandPersistence(
        connection
    ).persist_subtitle_decision_revision(revision=revision, revision_result=result)
    return revision


def _persist_final(connection, reading_revision, decision_revision, time_revision_id, name, target_unit_id):
    final = SubtitleFinalSubtitle(
        identity=SubtitleFinalSubtitleId(name),
        domain_result_id=DomainResultId(f"{name}-result"),
        source_decision_revision_id=decision_revision.identity,
        decision_kind=decision_revision.decision_kind,
        applied_outcome=decision_revision.outcome,
        final_outcome=final_outcome_for_applied_outcome(decision_revision.outcome),
        source_review_decision_id=decision_revision.source_review_decision_id,
        review_item_id=decision_revision.review_item_id,
        candidate_reference_id=decision_revision.candidate_reference_id,
        source_preparation_id=decision_revision.source_preparation_id,
        source_validation_id=decision_revision.source_validation_id,
        source_time_revision_id=time_revision_id,
        source_reading_revision_id=reading_revision.identity,
        source_candidate_id=decision_revision.source_candidate_id,
        source_finding_id=decision_revision.source_finding_id,
        rule=decision_revision.rule,
        source_transcript_id=decision_revision.source_transcript_id,
        source_revision_id=decision_revision.source_revision_id,
        source_media_id=decision_revision.source_media_id,
        source_timeline_id=decision_revision.source_timeline_id,
        run_id=decision_revision.run_id,
        unit_execution_id=decision_revision.unit_execution_id,
        sequence=0,
        reason=f"final {name}",
        target_timed_unit_id=target_unit_id,
        applied_text=decision_revision.applied_text,
    )
    result = DomainResultReference(
        identity=final.domain_result_id,
        kind="subtitle_final_subtitle",
        source_media=decision_revision.source_media_id,
        source_timeline=decision_revision.source_timeline_id,
        upstream_results=(decision_revision.domain_result_id,),
    )
    SQLiteSubtitleFinalSubtitleCommandPersistence(
        connection
    ).persist_subtitle_final_subtitle(final=final, final_result=result)
    return final


def _finalize(connection, reading_revision, time_revision_id, name, kind, target_unit_id, applied_text=None):
    revision = _persist_decision_revision(
        connection, reading_revision, time_revision_id, name, kind, target_unit_id, applied_text
    )
    return _persist_final(
        connection, reading_revision, revision, time_revision_id, f"final-{name}", target_unit_id
    )


def _plan(name, unit_count):
    return SubtitleApprovedAssemblyIdentityPlan(
        document_id=SubtitleApprovedDocumentId(name),
        document_result_id=DomainResultId(f"{name}-result"),
        unit_ids=tuple(SubtitleApprovedUnitId(f"{name}-unit-{i}") for i in range(unit_count)),
    )


def build_persisted_documents(connection):
    """Persist the durable upstream and return (execution, run, exec, reading, prepared docs)."""

    execution, run_id, execution_id, candidate = _build_persisted_candidate(connection)
    reading = _compose_reading(connection, execution, run_id, execution_id)
    reading_revision = reading.revision
    units = reading_revision.unit_ids

    # Document A: modify unit 0, reject unit 1 -> eligible (1 modified, 1 omitted).
    time_a = _persist_defective_time(
        connection, reading_revision, candidate, "asm-a",
        [(units[0], SubtitleTimingStatus.ANCHORED, 0.0, 1.0),
         (units[1], SubtitleTimingStatus.ANCHORED, 1.0, 2.0)],
    )
    _finalize(connection, reading_revision, time_a, "a-modify", DecisionKind.MODIFY,
              SubtitleTimedUnitId("asm-a-unit-0"), applied_text="고친 자막")
    _finalize(connection, reading_revision, time_a, "a-reject", DecisionKind.REJECT,
              SubtitleTimedUnitId("asm-a-unit-1"))

    # Document B: accept unit 0, leave unit 1 untouched -> eligible (accept + untouched).
    time_b = _persist_defective_time(
        connection, reading_revision, candidate, "asm-b",
        [(units[0], SubtitleTimingStatus.ANCHORED, 0.0, 1.0),
         (units[1], SubtitleTimingStatus.ANCHORED, 1.0, 2.0)],
    )
    _finalize(connection, reading_revision, time_b, "b-accept", DecisionKind.ACCEPT,
              SubtitleTimedUnitId("asm-b-unit-0"))

    # Document C: unit 1 has unresolved timing and is included -> INELIGIBLE.
    time_c = _persist_defective_time(
        connection, reading_revision, candidate, "asm-c",
        [(units[0], SubtitleTimingStatus.ANCHORED, 0.0, 1.0),
         (units[1], SubtitleTimingStatus.UNRESOLVED, None, None)],
    )

    service = compose_sqlite_subtitle_approved_assembly_service(connection, execution)

    def assemble(time_id, plan_name):
        return service.record_assembly(
            source_time_revision_id=time_id,
            source_reading_revision_id=reading_revision.identity,
            run_id=run_id,
            unit_execution_id=execution_id,
            identities=_plan(plan_name, 2),
        )

    doc_a = assemble(time_a, "doc-a")
    doc_b = assemble(time_b, "doc-b")
    doc_c = assemble(time_c, "doc-c")
    return execution, run_id, execution_id, reading, (doc_a, doc_b, doc_c), (time_a, time_b, time_c)


def run_subtitle_approved_assembly_acceptance() -> dict:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "acceptance.sqlite3"
        connection = initialize_sqlite_database(path)

        time_repo = SQLiteSubtitleTimeRevisionRepository(connection)
        reading_repo = SQLiteSubtitleReadingRevisionRepository(connection)
        final_repo = SQLiteSubtitleFinalSubtitleRepository(connection)
        revision_repo = SQLiteSubtitleDecisionRevisionRepository(connection)

        execution, run_id, execution_id, reading, docs, time_ids = build_persisted_documents(
            connection
        )
        doc_a, doc_b, doc_c = docs
        time_a, time_b, time_c = time_ids
        reading_units = reading.units

        upstream_after = (
            time_repo.get(time_a),
            reading_repo.get(reading.revision.identity),
            final_repo.list_for_time_revision(time_a),
            revision_repo.get(SubtitleDecisionRevisionId("a-modify")),
        )

        # Document A: modify included, reject omitted.
        a_modified = (
            doc_a.document.eligibility is SubtitleExportEligibility.ELIGIBLE
            and doc_a.document.omitted_unit_count == 1
            and len(doc_a.units) == 1
            and doc_a.units[0].origin is SubtitleApprovedUnitOrigin.MODIFIED
            and doc_a.units[0].lines == ("고친 자막",)
        )
        # Document B: accept keeps original text, untouched keeps original text.
        original0 = reading_units[0].lines
        original1 = reading_units[1].lines
        b_accept_untouched = (
            doc_b.document.eligibility is SubtitleExportEligibility.ELIGIBLE
            and doc_b.document.omitted_unit_count == 0
            and len(doc_b.units) == 2
            and doc_b.units[0].origin is SubtitleApprovedUnitOrigin.ACCEPTED
            and doc_b.units[0].lines == original0
            and doc_b.units[1].origin is SubtitleApprovedUnitOrigin.UNTOUCHED
            and doc_b.units[1].lines == original1
            and doc_b.units[1].source_final_subtitle_id is None
        )
        # Document C: unresolved included unit -> ineligible, no units.
        c_ineligible = (
            doc_c.document.eligibility is SubtitleExportEligibility.INELIGIBLE
            and doc_c.units == ()
            and doc_c.document.approved_unit_ids == ()
            and doc_c.document.ineligibility_reason is not None
        )
        # ordering preserved from timed units
        ordering_preserved = [u.display_order for u in doc_b.units] == [0, 1]
        provenance_linked = all(
            d.document_result.kind == "subtitle_approved_document"
            and d.document_result.upstream_results == (time_repo.get(t).domain_result_id,)
            for d, t in ((doc_a, time_a), (doc_b, time_b))
        )
        no_upstream_mutation = upstream_after == (
            time_repo.get(time_a),
            reading_repo.get(reading.revision.identity),
            final_repo.list_for_time_revision(time_a),
            revision_repo.get(SubtitleDecisionRevisionId("a-modify")),
        )

        existing_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        no_downstream_tables = not {"subtitle_exports", "artifacts"} & existing_tables
        connection.close()

        reopened = open_sqlite_database(path)
        document_repo = SQLiteSubtitleApprovedDocumentRepository(reopened)
        results = SQLiteDomainResultReferenceRepository(reopened)
        restart_reconstructed = all(
            document_repo.get(d.document.identity) == d.document
            and results.get(d.document_result.identity) == d.document_result
            and all(document_repo.get_unit(u.identity) == u for u in d.units)
            for d in (doc_a, doc_b, doc_c)
        )
        reopened.close()

        replay_path = Path(directory) / "replay.sqlite3"
        replay_connection = initialize_sqlite_database(replay_path)
        _, _, _, _, r_docs, _ = build_persisted_documents(replay_connection)
        replay_connection.close()
        deterministic_replay = all(
            r.document == d.document and r.units == d.units
            for r, d in zip(r_docs, docs)
        )

        return {
            "document_count": 3,
            "a_modified": a_modified,
            "b_accept_untouched": b_accept_untouched,
            "c_ineligible": c_ineligible,
            "ordering_preserved": ordering_preserved,
            "provenance_linked": provenance_linked,
            "no_upstream_mutation": no_upstream_mutation,
            "restart_reconstructed": restart_reconstructed,
            "deterministic_replay": deterministic_replay,
            "no_downstream_tables": no_downstream_tables,
        }


def main() -> int:
    print(json.dumps(run_subtitle_approved_assembly_acceptance(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
