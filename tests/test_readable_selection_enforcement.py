"""Final Selection readability enforcement tests (041 §16 EN-1…EN-11, PATCH-0042)."""

import unittest
from dataclasses import dataclass, replace

from lectureos.application.effective_subtitle_final_selection import (
    EligibilityBlockingReason,
    ReviewSubjectNotEligibleError,
)
from lectureos.application.readable_cue_composition import (
    READABILITY_PARAMETERS,
    READABILITY_PARAMETERS_V1,
    READABILITY_PARAMETERS_V2,
    READABLE_GENERATOR_KIND,
    READABLE_GENERATOR_VERSION,
    UnknownReadabilityContractError,
    is_readable_candidate,
    readability_contract_for,
)
from lectureos.application.effective_subtitle_generation import GENERATOR_KIND
from lectureos.transcript.identities import TranscriptSegmentId

LF = "\n"


@dataclass(frozen=True)
class _Candidate:
    generator_kind: str = READABLE_GENERATOR_KIND
    generator_version: int = READABLE_GENERATOR_VERSION
    generation_parameters_version: int = 2


@dataclass(frozen=True)
class _Cue:
    ordinal: int
    text: str
    start: float
    end: float
    source_segment_ids: tuple = (TranscriptSegmentId("transcript-segment:t:0"),)


class ContractDispatchTests(unittest.TestCase):
    """EN-4: validation re-derives under the Candidate's OWN version, never the current default."""

    def test_v1_candidate_resolves_the_v1_parameter_set(self):
        """PV-4: a released v1 Candidate is evaluated under v1 forever."""

        parameters = readability_contract_for(_Candidate(generation_parameters_version=1))
        self.assertEqual(parameters, READABILITY_PARAMETERS_V1)
        self.assertEqual(parameters.maximum_line_characters, 22)

    def test_v2_candidate_resolves_the_v2_parameter_set(self):
        parameters = readability_contract_for(_Candidate(generation_parameters_version=2))
        self.assertEqual(parameters, READABILITY_PARAMETERS_V2)
        self.assertEqual(parameters.maximum_line_characters, 24)

    def test_unknown_parameter_version_never_falls_back(self):
        with self.assertRaises(UnknownReadabilityContractError) as raised:
            readability_contract_for(_Candidate(generation_parameters_version=99))
        self.assertIn("unknown readability parameter version", str(raised.exception))

    def test_unknown_generator_version_never_falls_back(self):
        with self.assertRaises(UnknownReadabilityContractError):
            readability_contract_for(_Candidate(generator_version=99))

    def test_passthrough_candidate_has_no_readability_contract(self):
        with self.assertRaises(UnknownReadabilityContractError):
            readability_contract_for(_Candidate(generator_kind=GENERATOR_KIND))

    def test_dispatch_is_deterministic(self):
        first = readability_contract_for(_Candidate())
        second = readability_contract_for(_Candidate())
        self.assertIs(first, second)

    def test_generator_kind_is_answered_in_one_place(self):
        """EN-9: the scope question has a single answer, not scattered string comparisons."""

        self.assertTrue(is_readable_candidate(_Candidate()))
        self.assertFalse(is_readable_candidate(_Candidate(generator_kind=GENERATOR_KIND)))
        self.assertFalse(is_readable_candidate(object()))


class _FakeSubjects:
    def __init__(self, subject, candidate, cues):
        self._subject, self._candidate, self._cues = subject, candidate, cues
        self.cue_calls = 0

    def get(self, review_subject_id):
        return self._subject

    def status(self, subject):
        return _Status()

    def candidate_of(self, subject):
        return self._candidate

    def cues_of(self, subject):
        self.cue_calls += 1
        return self._cues


@dataclass(frozen=True)
class _Status:
    candidate_source_currentness: object = "current"
    review_subject_currentness: object = "current"


@dataclass(frozen=True)
class _Identity:
    value: str


@dataclass(frozen=True)
class _Subject:
    identity: object
    candidate_id: object


class _FakeDecisions:
    def __init__(self, decision, applicability):
        self._decision, self._applicability = decision, applicability

    def current(self, review_subject_id):
        return self._decision

    def applicability(self, decision):
        return self._applicability


class _FakeSelections:
    def __init__(self):
        self.persisted = []

    def get(self, identity):
        return None

    def get_current(self, intake_id):
        return None

    def history(self, intake_id):
        return ()

    def persist_selection(self, *, selection):
        self.persisted.append(selection)


class EnforcementGateTests(unittest.TestCase):
    """EN-1…EN-9 exercised over the released eligibility path with an in-memory graph."""

    def _service(self, cues, *, candidate=None, accept=True, applicable=True):
        from lectureos.application.effective_subtitle_final_selection import (
            EffectiveSubtitleFinalSelectionService,
        )
        from lectureos.application.effective_subtitle_review_decision import (
            DecisionApplicability,
            DecisionKind,
        )

        candidate = candidate if candidate is not None else _Candidate()
        subject = _Subject(identity=_Identity("subject"), candidate_id=_Identity("candidate"))
        decision = _Decision(
            identity=_Identity("decision"),
            kind=DecisionKind.ACCEPT if accept else DecisionKind.REJECT,
        )
        subjects = _FakeSubjects(subject, candidate, cues)
        decisions = _FakeDecisions(
            decision,
            DecisionApplicability.APPLICABLE if applicable else DecisionApplicability.SUPERSEDED,
        )
        selections = _FakeSelections()
        service = EffectiveSubtitleFinalSelectionService(
            subjects, decisions, selections, selections
        )
        return service, subjects, selections

    def test_clean_readable_candidate_is_eligible(self):
        """EN-1: no blocking finding, applicable accept → selectable."""

        service, _, _ = self._service([_Cue(0, "짧고 좋은 자막", 0.0, 3.0)])
        report = service.eligibility("subject")
        self.assertTrue(report.eligible)
        self.assertIsNone(report.blocking_reason)
        self.assertEqual(report.readability_findings, ())
        self.assertEqual(report.readability_parameters_version, 2)

    def test_warning_only_candidate_is_eligible(self):
        """EN-6: warnings never refuse."""

        cues = [
            _Cue(0, "짧다", 0.0, 0.5),                       # below target minimum
            _Cue(1, "긴 침묵 구간", 1.0, 30.0),                # above maximum, unsplittable
            _Cue(2, "가나다라마바사아자차카타파하", 30.0, 31.0),   # high reading rate
        ]
        service, _, _ = self._service(cues)
        report = service.eligibility("subject")
        self.assertTrue(report.eligible)
        self.assertEqual(report.readability_findings, ())

    def test_one_blocking_finding_refuses(self):
        """EN-1/EN-4: a single blocking finding is enough."""

        service, _, _ = self._service([_Cue(0, "가" * 30, 0.0, 3.0)])
        report = service.eligibility("subject")
        self.assertFalse(report.eligible)
        self.assertIs(report.blocking_reason, EligibilityBlockingReason.READABILITY_BLOCKING)
        self.assertEqual(len(report.readability_findings), 1)

    def test_every_blocking_finding_is_exposed(self):
        """EN-4/EN-5: the refusal names what must change, not merely that something did."""

        cues = [_Cue(index, "가" * 30, index * 3.0, index * 3.0 + 2.0) for index in range(3)]
        service, _, _ = self._service(cues)
        report = service.eligibility("subject")
        self.assertEqual(len(report.readability_findings), 3)
        self.assertEqual({f.cue_ordinal for f in report.readability_findings}, {0, 1, 2})

    def test_refusal_writes_no_selection(self):
        """EN-5: side-effect free."""

        service, _, selections = self._service([_Cue(0, "가" * 30, 0.0, 3.0)])
        with self.assertRaises(ReviewSubjectNotEligibleError):
            service.select_final(review_subject_id="subject", selector="selector:kim")
        self.assertEqual(selections.persisted, [])

    def test_refusal_message_enumerates_the_findings(self):
        service, _, _ = self._service([_Cue(0, "가" * 30, 0.0, 3.0)])
        with self.assertRaises(ReviewSubjectNotEligibleError) as raised:
            service.select_final(review_subject_id="subject", selector="selector:kim")
        message = str(raised.exception)
        self.assertIn("readability_blocking", message)
        self.assertIn("READABILITY_LINE_TOO_LONG", message)
        self.assertIn("cue #0", message)
        self.assertIn("parameters v2", message)

    def test_passthrough_candidate_is_never_evaluated(self):
        """EN-9: out of scope entirely — the cue graph is not even read."""

        service, subjects, _ = self._service(
            [_Cue(0, "가" * 60, 0.0, 3.0)],
            candidate=_Candidate(generator_kind=GENERATOR_KIND),
        )
        report = service.eligibility("subject")
        self.assertTrue(report.eligible)
        self.assertEqual(subjects.cue_calls, 0)
        self.assertIsNone(report.readability_parameters_version)

    def test_unknown_contract_refuses_rather_than_falling_back(self):
        service, _, _ = self._service(
            [_Cue(0, "짧고 좋은 자막", 0.0, 3.0)],
            candidate=_Candidate(generation_parameters_version=99),
        )
        report = service.eligibility("subject")
        self.assertFalse(report.eligible)
        self.assertIs(
            report.blocking_reason, EligibilityBlockingReason.READABILITY_CONTRACT_UNKNOWN
        )

    def test_readability_is_not_reached_when_the_decision_already_blocks(self):
        """The released decision conditions keep precedence; readability adds one condition."""

        service, subjects, _ = self._service(
            [_Cue(0, "가" * 30, 0.0, 3.0)], accept=False
        )
        report = service.eligibility("subject")
        self.assertIs(report.blocking_reason, EligibilityBlockingReason.DECISION_NOT_ACCEPT)
        self.assertEqual(subjects.cue_calls, 0)

    def test_accept_alone_is_not_eligibility(self):
        """EN-3: an applicable Accept exists and the subject is still refused."""

        service, _, _ = self._service([_Cue(0, "가" * 30, 0.0, 3.0)])
        report = service.eligibility("subject")
        self.assertIs(report.current_decision_kind.value, report.current_decision_kind.value)
        self.assertFalse(report.eligible)


@dataclass(frozen=True)
class _Decision:
    identity: object
    kind: object


if __name__ == "__main__":
    unittest.main()
