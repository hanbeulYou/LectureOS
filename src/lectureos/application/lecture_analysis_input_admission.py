"""Explicit Lecture Analysis Input Admission (042 §5.1 / PATCH-0009 Milestone 1, GOAL-023).

The durable half of 042 Milestone 1 for the effective-transcript generation: one explicit
command admits the current effective transcript authority — the validated selected Corrected
Transcript with its Source Timeline and Source Media reference — as one **immutable,
identity-owning, provenance-bearing** analysis input record. Analysis itself does not start:
no Analysis Run, ProcessingRun, Finding, Artifact, or AI reasoning exists in this contract.

**Eligibility is revalidated, never trusted.** Every admission command re-evaluates the derived
GOAL-022 eligibility at command time (closing its documented advisory/TOCTOU boundary); an
ineligible intake admits nothing and persists nothing. The eligible result's single-snapshot
lineage is what the admission binds — intake, source media, exact corrected revision, parent raw
transcript, the observed selection records, and the released §19 content fingerprint — so the
record is an immutable snapshot of the authority *as admitted*; later authority changes never
mutate it.

**Identity and replay (the released GOAL-012 binding rule, reused).** Admission identity derives
from the exact immutable source only — (contract, intake scope, corrected revision); observed
authority provenance and the content fingerprint are recorded facts, not identity. Re-admitting
the same current authority converges idempotently on the one existing record (REUSED, no new
row) — including under near-concurrent identical commands (insert collision → converge) and
after the authority changed away and back. A changed authority (a new current corrected
revision) admits a NEW record; prior admissions remain valid immutable history (append-only —
nothing is updated or deleted). A fingerprint disagreement on an existing record is an explicit
integrity conflict, never an overwrite. No wall-clock, randomness, path, or rowid participates
anywhere (the repository's released no-wall-clock rule).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from lectureos.execution.identities import SourceMediaId
from lectureos.persistence.errors import PersistenceIdentityCollisionError
from lectureos.transcript.identities import TranscriptId, TranscriptRevisionId

from .identities import LectureAnalysisInputAdmissionId, TranscriptSourceIntakeId
from .lecture_analysis_input_eligibility import (
    LectureAnalysisInputEligibility,
    LectureAnalysisInputEligibilityService,
)
from .provider_transcript_admission import (
    ProviderTranscriptAdmissionError,
    require_canonical_intake_id,
)

LECTURE_ANALYSIS_INPUT_ADMISSION_IDENTITY_PREFIX = "lecture-analysis-input"

ADMISSION_CONTRACT_KIND = "lecture_analysis_input_admission"
ADMISSION_CONTRACT_VERSION = 1


class LectureAnalysisInputAdmissionError(ValueError):
    """An admission request that cannot proceed (malformed, unknown, or unsupported input)."""


class AnalysisInputNotAdmissibleError(LectureAnalysisInputAdmissionError):
    """The intake's current authority is not eligible for admission right now."""


class AnalysisInputAdmissionConflictError(LectureAnalysisInputAdmissionError):
    """An existing admission for this exact source records a divergent payload."""


class AdmissionOutcome(str, Enum):
    ADMITTED = "admitted"   # a new immutable analysis input record was created
    REUSED = "reused"       # the identical source is already admitted; no new row


class AdmissionAuthorityMatch(str, Enum):
    """Derived, never stored: does an admission still bind the CURRENT authority?"""

    CURRENT = "current"
    SUPERSEDED_BY_AUTHORITY_CHANGE = "superseded_by_authority_change"
    CURRENT_AUTHORITY_INELIGIBLE = "current_authority_ineligible"


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def derive_admission_identity(
    intake_id: TranscriptSourceIntakeId,
    corrected_revision_id: TranscriptRevisionId,
) -> LectureAnalysisInputAdmissionId:
    """Deterministic admission identity — the exact immutable admitted source only.

    The released GOAL-012 rule: authority provenance and content fingerprint are recorded
    facts, not identity; re-admitting the same revision under changed-but-equivalent authority
    converges on one record. No timestamp, path, or rowid participates.
    """

    digest = hashlib.sha256(
        _canonical_json(
            {
                "contract": ADMISSION_CONTRACT_KIND,
                "contract_version": ADMISSION_CONTRACT_VERSION,
                "intake": intake_id.value,
                "corrected_revision": corrected_revision_id.value,
            }
        ).encode("utf-8")
    ).hexdigest()
    return LectureAnalysisInputAdmissionId(
        f"{LECTURE_ANALYSIS_INPUT_ADMISSION_IDENTITY_PREFIX}:{digest}"
    )


@dataclass(frozen=True, slots=True)
class LectureAnalysisInputAdmission:
    """Immutable durable analysis input: one exact effective authority explicitly admitted."""

    identity: LectureAnalysisInputAdmissionId
    transcript_source_intake_id: TranscriptSourceIntakeId
    source_media_id: SourceMediaId
    corrected_revision_id: TranscriptRevisionId
    parent_raw_transcript_id: TranscriptId
    raw_selection_id: object       # CurrentRawTranscriptSelectionId (observed provenance)
    corrected_selection_id: object  # CorrectedRevisionSelectionId (observed provenance)
    content_fingerprint: str
    segment_count: int
    admission_contract_version: int = ADMISSION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.admission_contract_version != ADMISSION_CONTRACT_VERSION:
            raise ValueError("unsupported analysis input admission contract version")
        if len(self.content_fingerprint) != 64:
            raise ValueError(
                "analysis input content fingerprint must be a 64-hex SHA-256 digest"
            )
        if self.segment_count <= 0:
            raise ValueError(
                "an admitted analysis input requires non-empty transcript content"
            )
        if self.raw_selection_id is None or self.corrected_selection_id is None:
            raise ValueError(
                "an admission must record the observed selection authority provenance"
            )
        if self.identity != derive_admission_identity(
            self.transcript_source_intake_id, self.corrected_revision_id
        ):
            raise ValueError(
                "analysis input admission identity must derive from its intake scope and "
                "exact corrected revision"
            )


@dataclass(frozen=True, slots=True)
class AdmissionResult:
    """One admission command outcome: the immutable record, the outcome, and the revalidated
    eligibility snapshot the command observed."""

    admission: LectureAnalysisInputAdmission
    outcome: AdmissionOutcome
    eligibility: LectureAnalysisInputEligibility


class AdmissionQuery(Protocol):
    def get(self, identity): ...

    def list_for_intake(self, intake_id) -> tuple: ...


class AtomicAdmissionPersistence(Protocol):
    def persist_admission(self, *, admission: LectureAnalysisInputAdmission) -> None: ...


class LectureAnalysisInputAdmissionService:
    """The single canonical explicit-admission path of the effective generation (GOAL-023)."""

    def __init__(
        self,
        eligibility_service: LectureAnalysisInputEligibilityService,
        admission_query: AdmissionQuery,
        persistence: AtomicAdmissionPersistence,
    ) -> None:
        self._eligibility = eligibility_service
        self._admissions = admission_query
        self._persistence = persistence

    # -- explicit admission command -------------------------------------------------------------------

    def admit(self, *, intake_id: str) -> AdmissionResult:
        # Revalidation at command time — a prior eligibility result is advisory only.
        report = self._eligibility.evaluate(intake_id)
        if not report.eligible:
            raise AnalysisInputNotAdmissibleError(
                "intake's current effective authority is not admissible: "
                + ", ".join(reason.value for reason in report.blocking_reasons)
            )
        admission = LectureAnalysisInputAdmission(
            identity=derive_admission_identity(
                TranscriptSourceIntakeId(report.transcript_source_intake_id),
                report.corrected_revision_id,
            ),
            transcript_source_intake_id=TranscriptSourceIntakeId(
                report.transcript_source_intake_id
            ),
            source_media_id=report.source_media_id,
            corrected_revision_id=report.corrected_revision_id,
            parent_raw_transcript_id=report.parent_raw_transcript_id,
            raw_selection_id=report.raw_selection_id,
            corrected_selection_id=report.corrected_selection_id,
            content_fingerprint=report.content_fingerprint,
            segment_count=report.segment_count,
        )
        existing = self._admissions.get(admission.identity)
        if existing is not None:
            return self._reuse(existing, admission, report)
        try:
            self._persistence.persist_admission(admission=admission)
        except PersistenceIdentityCollisionError:
            # A near-concurrent identical admission won the insert; converge on its record.
            resolved = self._admissions.get(admission.identity)
            if resolved is not None:
                return self._reuse(resolved, admission, report)
            raise
        return AdmissionResult(
            admission=admission, outcome=AdmissionOutcome.ADMITTED, eligibility=report
        )

    @staticmethod
    def _reuse(
        existing: LectureAnalysisInputAdmission,
        expected: LectureAnalysisInputAdmission,
        report: LectureAnalysisInputEligibility,
    ) -> AdmissionResult:
        # The admitted source is immutable, so its recorded snapshot can never legitimately
        # diverge; a disagreement is an explicit conflict, never an overwrite.
        if (
            existing.content_fingerprint != expected.content_fingerprint
            or existing.parent_raw_transcript_id != expected.parent_raw_transcript_id
            or existing.source_media_id != expected.source_media_id
            or existing.segment_count != expected.segment_count
        ):
            raise AnalysisInputAdmissionConflictError(
                "existing analysis input admission for this source records a different "
                "snapshot (repository integrity failure)"
            )
        return AdmissionResult(
            admission=existing, outcome=AdmissionOutcome.REUSED, eligibility=report
        )

    # -- queries (derived; never mutate history) ------------------------------------------------------

    def get(self, admission_id: str) -> LectureAnalysisInputAdmission | None:
        return self._admissions.get(require_canonical_admission_id(admission_id))

    def list_for_intake(
        self, intake_id: str
    ) -> tuple[LectureAnalysisInputAdmission, ...]:
        try:
            identity = require_canonical_intake_id(intake_id)
        except ProviderTranscriptAdmissionError as error:
            raise LectureAnalysisInputAdmissionError(str(error)) from error
        return self._admissions.list_for_intake(identity)

    def authority_match(
        self, admission: LectureAnalysisInputAdmission
    ) -> AdmissionAuthorityMatch:
        """Derived only: does this immutable admission still bind the CURRENT authority?

        A superseded admission remains valid immutable history — this observation never
        mutates anything.
        """

        report = self._eligibility.evaluate(
            admission.transcript_source_intake_id.value
        )
        if not report.eligible:
            return AdmissionAuthorityMatch.CURRENT_AUTHORITY_INELIGIBLE
        if report.corrected_revision_id == admission.corrected_revision_id:
            return AdmissionAuthorityMatch.CURRENT
        return AdmissionAuthorityMatch.SUPERSEDED_BY_AUTHORITY_CHANGE


def require_canonical_admission_id(value: str) -> LectureAnalysisInputAdmissionId:
    prefix = LECTURE_ANALYSIS_INPUT_ADMISSION_IDENTITY_PREFIX + ":"
    if (
        not isinstance(value, str)
        or not value.startswith(prefix)
        or len(value) != len(prefix) + 64
    ):
        raise LectureAnalysisInputAdmissionError(
            "lecture analysis input admission identity is malformed "
            "(expected 'lecture-analysis-input:<64 hex digest>')"
        )
    return LectureAnalysisInputAdmissionId(value)


__all__ = [
    "ADMISSION_CONTRACT_KIND",
    "ADMISSION_CONTRACT_VERSION",
    "LECTURE_ANALYSIS_INPUT_ADMISSION_IDENTITY_PREFIX",
    "AdmissionAuthorityMatch",
    "AdmissionOutcome",
    "AdmissionQuery",
    "AdmissionResult",
    "AnalysisInputAdmissionConflictError",
    "AnalysisInputNotAdmissibleError",
    "AtomicAdmissionPersistence",
    "LectureAnalysisInputAdmission",
    "LectureAnalysisInputAdmissionError",
    "LectureAnalysisInputAdmissionService",
    "derive_admission_identity",
    "require_canonical_admission_id",
]
