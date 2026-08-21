"""Transcript Timing Quality Diagnostic (040 §15 TD-1…TD-20, `PATCH-0046`).

The contract this file exists to hold is a pair of boundaries, and both are asserted directly:

    P1 alone  = a window's first segment starting at its provider anchor
              = normal faster-whisper decode semantics
              = NEVER a warning                                     (TD-4)

    P1 + a positive gap from the previous admitted coverage
              = a structure worth reviewing
              = a non-blocking Quality Warning                      (TD-2, TD-5)

An earlier round of this investigation contracted a rule from a signal-selected sample and had to
withdraw it. The predicate tests below therefore pin the exact boundary conditions — equality,
one tolerance unit either side, and non-first segments — rather than only the happy path.
"""

import ast
import sqlite3
import unittest

from lectureos.application.provider_transcript_admission import (
    TIMING_BOUNDARY_TOLERANCE_SECONDS as EPS,
    ProviderDecodeEvidence,
    ProviderDecodeWindow,
    parse_preserved_segment_timings,
)
from lectureos.application.transcript_quality_diagnostic import (
    DiagnosticCompleteness,
    EvidenceScope,
    QualityReason,
    TIMING_ALGORITHM_KIND,
    TIMING_ALGORITHM_VERSION,
    TIMING_PROVIDER_PARAMETER_VERSION,
    TimingQualityReason,
    TranscriptQualityDiagnosticError,
    TranscriptTimingDiagnosticService,
    evaluate_timing_predicate,
    provider_anchor_seconds,
)


def _window(anchor_centiseconds, ordinals):
    return ProviderDecodeWindow(
        window_ref=f"seek={anchor_centiseconds}",
        segment_ordinals=tuple(ordinals),
        values=(("avg_logprob", -0.3),),
    )


def _evidence(*windows):
    return ProviderDecodeEvidence(kind="faster-whisper/decode-window", windows=tuple(windows))


class PredicateTests(unittest.TestCase):
    """TD-4, TD-5, TD-6 — exactly when P fires, and the boundaries where it must not."""

    def test_p1_without_p2_produces_no_finding(self):
        # A window opening exactly where the previous segment ended: continuous speech, which is how
        # faster-whisper advances `seek`. This is the case TD-4 forbids warning about.
        timings = ((0.0, 10.0), (10.0, 14.0))
        self.assertEqual(evaluate_timing_predicate(_evidence(_window(1000, [1])), timings), ())

    def test_p1_with_p2_produces_one_finding(self):
        timings = ((0.0, 10.0), (30.0, 34.0))
        found = evaluate_timing_predicate(_evidence(_window(3000, [1])), timings)
        self.assertEqual(len(found), 1)
        ordinal, anchor, gap = found[0]
        self.assertEqual(ordinal, 1)
        self.assertAlmostEqual(anchor, 30.0)
        self.assertAlmostEqual(gap, 20.0)

    def test_non_window_first_segment_never_fires(self):
        # Segment 2 sits inside the window but is not its first segment.
        timings = ((0.0, 10.0), (30.0, 34.0), (34.0, 38.0))
        found = evaluate_timing_predicate(_evidence(_window(3000, [1, 2])), timings)
        self.assertEqual([o for o, _, _ in found], [1])

    def test_segment_not_at_the_anchor_never_fires(self):
        # If the provider had placed the segment at speech onset rather than the window boundary,
        # P1 would be false and there would be nothing to review.
        timings = ((0.0, 10.0), (35.0, 39.0))
        self.assertEqual(evaluate_timing_predicate(_evidence(_window(3000, [1])), timings), ())

    def test_anchor_exactly_equal_to_previous_end_does_not_fire(self):
        timings = ((0.0, 30.0), (30.0, 34.0))
        self.assertEqual(evaluate_timing_predicate(_evidence(_window(3000, [1])), timings), ())

    def test_representation_noise_counts_as_the_same_instant(self):
        # PATCH-0039 T-2: a difference this small denotes one instant, not a gap.
        timings = ((0.0, 30.0 - EPS / 2), (30.0, 34.0))
        self.assertEqual(evaluate_timing_predicate(_evidence(_window(3000, [1])), timings), ())

    def test_smallest_representable_gap_fires_like_the_largest(self):
        # TD-6: no duration threshold. One provider timestamp tick qualifies exactly as 85 s does.
        small = ((0.0, 29.98), (30.0, 34.0))
        large = ((0.0, 0.5), (30.0, 34.0))
        self.assertEqual(len(evaluate_timing_predicate(_evidence(_window(3000, [1])), small)), 1)
        self.assertEqual(len(evaluate_timing_predicate(_evidence(_window(3000, [1])), large)), 1)

    def test_first_segment_of_the_transcript_never_fires(self):
        # There is no previous admitted coverage to compare against.
        self.assertEqual(
            evaluate_timing_predicate(_evidence(_window(0, [0])), ((0.0, 4.0),)), ()
        )

    def test_no_numeric_gap_threshold_exists_in_the_detector(self):
        """TD-6 asserted structurally: the predicate's source contains no duration constant."""
        import lectureos.application.transcript_quality_diagnostic as module
        import inspect as _inspect

        tree = ast.parse(_inspect.getsource(module.evaluate_timing_predicate))
        numbers = {
            n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, (int, float))
            and not isinstance(n.value, bool)
        }
        # Only ordinal indexing constants may appear; no seconds-scale cut.
        self.assertTrue(numbers <= {0, 1}, f"unexpected numeric constants: {numbers}")


class ProviderBoundaryTests(unittest.TestCase):
    """TD-8 — the detector is provider-specific and refuses to guess."""

    def test_faster_whisper_anchor_is_centiseconds(self):
        self.assertAlmostEqual(provider_anchor_seconds("seek=2880"), 28.80)
        self.assertAlmostEqual(provider_anchor_seconds("seek=0"), 0.0)

    def test_unknown_anchor_grammar_yields_none(self):
        for ref in ("seek=unknown", "offset=100", "", "seek=", "seek=-5", "seek=1.5"):
            self.assertIsNone(provider_anchor_seconds(ref), ref)

    def test_windows_without_a_usable_anchor_are_skipped(self):
        evidence = ProviderDecodeEvidence(
            kind="other-provider",
            windows=(ProviderDecodeWindow(
                window_ref="seek=unknown", segment_ordinals=(1,), values=(("x", 1.0),)),),
        )
        self.assertEqual(evaluate_timing_predicate(evidence, ((0.0, 1.0), (30.0, 34.0))), ())


class _Q:
    def __init__(self, records): self._r = records
    def get(self, identity): return self._r.get(identity.value)


class _Result:
    def __init__(self, content): self.original_content = content


class _Raw:
    def __init__(self, ids): self.segment_ids = ids


class _Admission:
    def __init__(self, pr, raw):
        from lectureos.transcript.identities import ProviderTranscriptResultId, TranscriptId
        self.provider_transcript_result_id = ProviderTranscriptResultId(pr)
        self.raw_transcript_id = TranscriptId(raw)


_AID = "provider-transcript-admission:" + "a" * 64
_PRID = "provider-transcript-result:" + "a" * 64
_RID = "raw-transcript:" + "a" * 64


def _service(content, segment_ids=()):
    from lectureos.application.identities import ProviderTranscriptAdmissionId  # noqa: F401
    return TranscriptTimingDiagnosticService(
        _Q({_AID: _Admission(_PRID, _RID)}),
        _Q({_PRID: _Result(content)}),
        _Q({_RID: _Raw(segment_ids)}),
    )


_WITH_ANCHORS = (
    '{"intake":"i","provider":"faster-whisper","model":"m","language":"ko",'
    '"provider_result_ref":"r",'
    '"provider_evidence":{"kind":"faster-whisper/decode-window","windows":['
    '{"window_ref":"seek=0","segment_ordinals":[0],"values":{"avg_logprob":-0.3},'
    '"start":0.0,"end":10.0},'
    '{"window_ref":"seek=3000","segment_ordinals":[1],"values":{"avg_logprob":-0.4},'
    '"start":30.0,"end":34.0}]},'
    '"segments":[{"start":0.0,"end":10.0,"text":"a"},{"start":30.0,"end":34.0,"text":"b"}]}'
)
_LEGACY = (
    '{"intake":"i","provider":"faster-whisper","model":"m","language":"ko",'
    '"provider_result_ref":"r",'
    '"segments":[{"start":0.0,"end":10.0,"text":"a"},{"start":30.0,"end":34.0,"text":"b"}]}'
)


class ServiceTests(unittest.TestCase):
    """TD-2, TD-7, TD-9, TD-11, TD-12 — the shape of the result."""

    def test_algorithm_anchor_is_declared_and_carries_no_threshold(self):
        r = _service(_WITH_ANCHORS).diagnose(admission_id=_AID)
        self.assertEqual(r.algorithm_kind, TIMING_ALGORITHM_KIND)
        self.assertEqual(r.algorithm_version, TIMING_ALGORITHM_VERSION)
        self.assertIsNone(r.provider_parameter_version)
        self.assertIsNone(TIMING_PROVIDER_PARAMETER_VERSION)

    def test_reason_vocabulary_is_one_segment_scoped_reason(self):
        r = _service(_WITH_ANCHORS).diagnose(admission_id=_AID)
        self.assertEqual(len(r.findings), 1)
        self.assertIs(r.findings[0].reason, TimingQualityReason.TIMING_ALIGNMENT_REVIEW_REQUIRED)
        self.assertIs(r.findings[0].evidence_scope, EvidenceScope.SEGMENT)
        self.assertEqual({x.value for x in TimingQualityReason},
                         {"TIMING_ALIGNMENT_REVIEW_REQUIRED"})

    def test_finding_states_no_drift_magnitude(self):
        """TD-2/TD-7: the anchor gap must not leak into the message as if it were drift."""
        finding = _service(_WITH_ANCHORS).diagnose(admission_id=_AID).findings[0]
        detail = finding.detail
        # The fixture's anchor gap is 20 s. The anchor itself (30 s) may be cited as a position;
        # the gap must not appear anywhere, because it is not how late the speech is.
        self.assertNotIn("20.0", detail)
        self.assertNotIn("20s", detail)
        for verdict in ("drift", "early by", "late by", "is wrong", "should be corrected"):
            self.assertNotIn(verdict, detail.lower())
        self.assertIn("worth human review", detail)
        # No structured magnitude is exposed either.
        self.assertFalse(hasattr(finding, "anchor_gap"))

    def test_legacy_record_without_anchors_is_unavailable_not_clean(self):
        r = _service(_LEGACY).diagnose(admission_id=_AID)
        self.assertFalse(r.evidence_available)
        self.assertIs(r.completeness, DiagnosticCompleteness.UNAVAILABLE)
        self.assertEqual(r.findings, ())
        self.assertFalse(r.reports_clean)          # the distinction TD-12 insists on

    def test_same_inputs_produce_the_same_result(self):
        s = _service(_WITH_ANCHORS)
        self.assertEqual(s.diagnose(admission_id=_AID), s.diagnose(admission_id=_AID))

    def test_unknown_or_malformed_admission_is_rejected(self):
        for bad in ("nonsense", "provider-transcript-admission:" + "0" * 64):
            with self.assertRaises(TranscriptQualityDiagnosticError):
                _service(_WITH_ANCHORS).diagnose(admission_id=bad)

    def test_service_exposes_only_a_read_only_operation(self):
        public = {n for n in dir(_service(_WITH_ANCHORS)) if not n.startswith("_")}
        self.assertEqual(public, {"diagnose"})


class SeparationTests(unittest.TestCase):
    """TD-16 — timing and hallucination reasons never mix."""

    def test_reason_vocabularies_are_disjoint_types(self):
        self.assertFalse({r.value for r in QualityReason} & {r.value for r in TimingQualityReason})
        self.assertNotIsInstance(
            TimingQualityReason.TIMING_ALIGNMENT_REVIEW_REQUIRED, QualityReason)

    def test_timing_detector_reads_no_provider_confidence_signal(self):
        import lectureos.application.transcript_quality_diagnostic as module
        import inspect as _inspect

        source = _inspect.getsource(module.evaluate_timing_predicate) + _inspect.getsource(
            module.TranscriptTimingDiagnosticService)
        for signal in ("avg_logprob", "no_speech_prob", "compression_ratio", "temperature"):
            self.assertNotIn(signal, source, f"timing detector must not consult {signal}")

    def test_no_combined_score_exists(self):
        r = _service(_WITH_ANCHORS).diagnose(admission_id=_AID)
        for attr in ("score", "severity", "confidence", "drift_seconds"):
            self.assertFalse(hasattr(r, attr))
            self.assertFalse(hasattr(r.findings[0], attr))


class DownstreamBoundaryTests(unittest.TestCase):
    """TD-13, TD-14, TD-17, TD-18 — nothing consults it, nothing is mutated."""

    def _source(self, module):
        with open(module.__file__, encoding="utf-8") as handle:
            return handle.read()

    def test_no_downstream_boundary_imports_the_timing_diagnostic(self):
        import lectureos.application.provider_transcript_admission as admission
        import lectureos.application.current_raw_transcript_selection as raw_selection
        import lectureos.application.effective_subtitle_final_selection as final_selection
        import lectureos.application.effective_subtitle_srt_artifact as artifact
        import lectureos.application.effective_srt_materialization as materialization
        import lectureos.application.effective_srt_publication as publication
        import lectureos.application.readable_subtitle_validation as readability
        import lectureos.validation as validation

        for module in (admission, raw_selection, final_selection, artifact,
                       materialization, publication, readability, validation):
            source = self._source(module)
            self.assertNotIn("TranscriptTimingDiagnostic", source, module.__name__)
            self.assertNotIn("TIMING_ALIGNMENT_REVIEW_REQUIRED", source, module.__name__)

    def test_timing_module_never_mutates_timing_or_creates_candidates(self):
        """TD-13/TD-17 asserted on executable code, with docstrings stripped so prose cannot pass
        or fail the check."""
        import lectureos.application.transcript_quality_diagnostic as module
        import inspect as _inspect

        tree = ast.parse(_inspect.getsource(module.TranscriptTimingDiagnosticService))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if (node.body and isinstance(node.body[0], ast.Expr)
                        and isinstance(node.body[0].value, ast.Constant)
                        and isinstance(node.body[0].value.value, str)):
                    node.body.pop(0)
        code = ast.unparse(tree)
        for forbidden in ("persist", "insert", "update", "commit", "CorrectionCandidate",
                          "proposed_text", "delete"):
            self.assertNotIn(forbidden, code, forbidden)
        # Nothing is assigned to a timing attribute anywhere in the service.
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Attribute):
                        self.assertNotIn(target.attr, {"start", "end", "segments"})


class RealFixtureTests(unittest.TestCase):
    """The released measurement (`implementation/134`) must reproduce from persisted evidence."""

    DB = "evaluation/timing-diagnostic-full-corpus/measurement.sqlite3"

    def test_predicate_reproduces_the_recorded_measurement(self):
        import json
        import os

        if not os.path.exists(self.DB):
            self.skipTest("evaluation fixture not present (git-excluded)")
        from lectureos.application.provider_transcript_admission import (
            parse_preserved_provider_evidence)

        connection = sqlite3.connect(f"file:{self.DB}?mode=ro", uri=True)
        content = connection.execute(
            "SELECT original_content FROM provider_transcript_results").fetchone()[0]
        connection.close()
        found = {
            ordinal for ordinal, _, _ in evaluate_timing_predicate(
                parse_preserved_provider_evidence(content),
                parse_preserved_segment_timings(content))
        }
        with open("evaluation/timing-diagnostic-full-corpus/segments.jsonl",
                  encoding="utf-8") as handle:
            rows = json.load(handle)
        recorded = {row["ordinal"] for row in rows if row["P"]}
        self.assertEqual(found, recorded)


if __name__ == "__main__":
    unittest.main()
