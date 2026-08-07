"""Contract tests for readable subtitle cue composition (041 §16, PATCH-0041)."""

import json
import unittest
from dataclasses import dataclass
from pathlib import Path

from lectureos.application.effective_subtitle_generation import (
    GENERATION_PARAMETERS_VERSION,
    GENERATOR_KIND,
    GENERATOR_VERSION,
    PASSTHROUGH_GENERATOR,
    build_passthrough_cues,
    derive_effective_candidate_identity,
)
from lectureos.application.effective_transcript_consumption import ConsumedSourceKind
from lectureos.application.identities import (
    EffectiveSubtitleCandidateId,
    EffectiveTranscriptConsumptionId,
    TranscriptSourceIntakeId,
)
from lectureos.application.readable_cue_composition import (
    READABILITY_PARAMETERS,
    READABILITY_PARAMETERS_VERSION,
    READABLE_GENERATOR_KIND,
    READABLE_GENERATOR_VERSION,
    ReadabilityParameters,
    build_readable_cues,
    compose_lines,
    compose_readable_cues,
    cue_display_length,
    display_length,
    merge_normalized_source_text,
    readable_generator_spec,
    split_positions,
)
from lectureos.application.readable_subtitle_validation import (
    READABILITY_CONSECUTIVE_LINE_BREAKS,
    READABILITY_CUES_OVERLAP,
    READABILITY_CUE_TEXT_TOO_LONG,
    READABILITY_DURATION_ABOVE_MAXIMUM,
    READABILITY_DURATION_BELOW_HARD_MINIMUM,
    READABILITY_DURATION_BELOW_TARGET,
    READABILITY_LEADING_LINE_BREAK,
    READABILITY_LINE_COUNT_EXCEEDED,
    READABILITY_LINE_TOO_LONG,
    READABILITY_READING_RATE_HIGH,
    READABILITY_SOURCE_LINEAGE_MISMATCH,
    READABILITY_TEXT_NOT_RECOVERABLE,
    READABILITY_TRAILING_LINE_BREAK,
    ReadabilitySeverity,
    evaluate_readable_cues,
    verify_serialized_lines,
)
from lectureos.application.srt_payload import serialize_srt_cues
from lectureos.transcript.identities import TranscriptId, TranscriptSegmentId

LF = "\n"
_FIXTURE = Path(__file__).resolve().parents[1] / "e2e-results" / "segments.jsonl"


@dataclass(frozen=True)
class _Segment:
    identity: TranscriptSegmentId
    text: str
    start: float | None
    end: float | None


@dataclass(frozen=True)
class _Cue:
    ordinal: int
    text: str
    start: float | None
    end: float | None
    source_segment_ids: tuple


def _segments(*rows):
    return tuple(
        _Segment(TranscriptSegmentId(f"transcript-segment:t:{index}"), text, start, end)
        for index, (text, start, end) in enumerate(rows)
    )


def _as_cues(composed):
    return [
        _Cue(index, cue.text, cue.start, cue.end, cue.source_segment_ids)
        for index, cue in enumerate(composed)
    ]


class ParameterSetTests(unittest.TestCase):
    def test_readability_parameter_set_is_pinned_to_its_version(self):
        """R-10/R-13: a silent value change would let two policies share one identity."""

        self.assertEqual(READABILITY_PARAMETERS.version, READABILITY_PARAMETERS_VERSION)
        self.assertEqual(
            READABILITY_PARAMETERS.fingerprint(),
            "b487fcec7aaae4fa72cf7dcdeee97b9ec5fecea4869c230445f27edef60eb742",
        )

    def test_declared_values_match_the_contract(self):
        p = READABILITY_PARAMETERS
        self.assertEqual(p.hard_minimum_duration, 0.100)
        self.assertEqual(p.target_minimum_duration, 1.000)
        self.assertEqual(p.maximum_duration, 7.000)
        self.assertEqual(p.maximum_line_characters, 22)
        self.assertEqual(p.maximum_lines, 2)
        self.assertEqual(p.maximum_cue_characters, 44)
        self.assertEqual(p.cps_warning_threshold, 12)

    def test_incoherent_parameters_are_rejected(self):
        with self.assertRaises(ValueError):
            ReadabilityParameters(hard_minimum_duration=2.0, target_minimum_duration=1.0)
        with self.assertRaises(ValueError):
            ReadabilityParameters(maximum_cue_characters=10, maximum_line_characters=22)


class GeneratorIdentityTests(unittest.TestCase):
    def _identity(self, kind, version, parameters_version):
        return derive_effective_candidate_identity(
            TranscriptSourceIntakeId("transcript-source-intake:sha256:" + "a" * 64),
            EffectiveTranscriptConsumptionId("transcript-consumption:" + "b" * 64),
            ConsumedSourceKind.RAW_TRANSCRIPT,
            "raw-transcript:" + "c" * 64,
            kind,
            version,
            parameters_version,
        )

    def test_readable_and_passthrough_identities_differ(self):
        """R-3/R-13: two generators, two Candidates for one binding."""

        passthrough = self._identity(GENERATOR_KIND, GENERATOR_VERSION, GENERATION_PARAMETERS_VERSION)
        readable = self._identity(
            READABLE_GENERATOR_KIND, READABLE_GENERATOR_VERSION, READABILITY_PARAMETERS_VERSION
        )
        self.assertNotEqual(passthrough, readable)

    def test_parameter_version_change_changes_identity(self):
        """R-13: a different policy is a different Candidate."""

        first = self._identity(READABLE_GENERATOR_KIND, READABLE_GENERATOR_VERSION, 1)
        second = self._identity(READABLE_GENERATOR_KIND, READABLE_GENERATOR_VERSION, 2)
        self.assertNotEqual(first, second)

    def test_passthrough_generator_spec_is_unchanged(self):
        """R-1/R-2: naming the passthrough generator did not change what it is."""

        self.assertEqual(PASSTHROUGH_GENERATOR.kind, GENERATOR_KIND)
        self.assertEqual(PASSTHROUGH_GENERATOR.version, GENERATOR_VERSION)
        self.assertEqual(PASSTHROUGH_GENERATOR.parameters_version, GENERATION_PARAMETERS_VERSION)
        self.assertIs(PASSTHROUGH_GENERATOR.build_cues, build_passthrough_cues)

    def test_readable_generator_spec_declares_the_parameter_version(self):
        spec = readable_generator_spec()
        self.assertEqual(spec.kind, READABLE_GENERATOR_KIND)
        self.assertEqual(spec.parameters_version, READABILITY_PARAMETERS.version)


class SplitTests(unittest.TestCase):
    def test_over_long_duration_is_split(self):
        segments = _segments(("첫 문장이다. 두 번째 문장이다.", 0.0, 12.0))
        composed = compose_readable_cues(segments)
        self.assertGreaterEqual(len(composed), 2)
        self.assertEqual(composed[0].start, 0.0)
        self.assertEqual(composed[-1].end, 12.0)
        for cue in composed:
            self.assertLessEqual(cue.end - cue.start, 7.0 + 1e-6)

    def test_over_long_text_is_split(self):
        text = "가나다라마바사아자차카타파하가나다라마바사. 아자차카타파하가나다라마바사아자차카타파하."
        segments = _segments((text, 0.0, 6.0))
        composed = compose_readable_cues(segments)
        self.assertGreater(len(composed), 1)
        for cue in composed:
            self.assertLessEqual(cue_display_length(cue.text), 44)

    def test_terminator_beats_comma_and_space(self):
        positions = split_positions("가나, 다라. 마바 사아")
        best = min(tier for tier, _ in positions)
        self.assertEqual(best, 1)

    def test_comma_is_used_when_no_terminator_exists(self):
        positions = split_positions("가나다라마바사, 아자차카타파하")
        self.assertEqual(min(tier for tier, _ in positions), 2)

    def test_whitespace_is_the_last_resort(self):
        positions = split_positions("가나다라마바사 아자차카타파하")
        self.assertEqual(min(tier for tier, _ in positions), 3)

    def test_never_splits_inside_a_word(self):
        text = "가나다라마바사아자차카타파하가나다라마바사아자차카타파하가나다라마바사아자차"
        self.assertEqual(split_positions(text), ())
        composed = compose_readable_cues(_segments((text, 0.0, 20.0)))
        self.assertEqual(len(composed), 1)

    def test_unsplittable_over_long_cue_is_kept_and_diagnosed(self):
        """R-5/R-11: forcing a split is prohibited; the goal becomes a warning."""

        composed = compose_readable_cues(_segments(("애들을", 0.0, 13.4)))
        self.assertEqual(len(composed), 1)
        validation = evaluate_readable_cues(_as_cues(composed))
        self.assertTrue(validation.deliverable)
        self.assertIn(
            READABILITY_DURATION_ABOVE_MAXIMUM, [f.code for f in validation.warnings]
        )

    def test_split_is_refused_when_a_child_would_fall_below_the_hard_minimum(self):
        composed = compose_readable_cues(_segments(("가. 나.", 0.0, 0.15)))
        self.assertEqual(len(composed), 1)


class SplitTimingTests(unittest.TestCase):
    def test_timing_is_proportional_to_display_characters(self):
        segments = _segments(("가나다. 라마바사아자차카.", 0.0, 10.0))
        composed = compose_readable_cues(segments)
        self.assertEqual(len(composed), 2)
        left = cue_display_length(composed[0].text)
        right = cue_display_length(composed[1].text)
        expected = 10.0 * left / (left + right)
        self.assertAlmostEqual(composed[0].end, expected, places=9)

    def test_outer_bounds_are_preserved_exactly(self):
        segments = _segments(("가나다. 라마바. 사아자. 차카타.", 3.25, 19.75))
        composed = compose_readable_cues(segments)
        self.assertGreater(len(composed), 1)
        self.assertEqual(composed[0].start, 3.25)
        self.assertEqual(composed[-1].end, 19.75)

    def test_children_are_ordered_and_do_not_overlap(self):
        segments = _segments(("가나다. 라마바. 사아자. 차카타. 파하가.", 0.0, 25.0))
        composed = compose_readable_cues(segments)
        for earlier, later in zip(composed, composed[1:]):
            self.assertLessEqual(earlier.end, later.start)
            self.assertGreater(earlier.end, earlier.start)

    def test_repeated_composition_is_deterministic(self):
        segments = _segments(("가나다. 라마바. 사아자.", 0.0, 15.0))
        first = compose_readable_cues(segments)
        second = compose_readable_cues(segments)
        self.assertEqual(
            [(c.text, c.start, c.end) for c in first],
            [(c.text, c.start, c.end) for c in second],
        )

    def test_untimed_input_is_never_split(self):
        composed = compose_readable_cues(
            _segments(("가나다. " * 20, None, None))
        )
        self.assertEqual(len(composed), 1)


class MergeTests(unittest.TestCase):
    def test_identical_adjacent_cues_merge(self):
        segments = _segments(("같은 문장", 0.0, 5.72), ("같은 문장", 5.72, 5.74))
        composed = compose_readable_cues(segments)
        self.assertEqual(len(composed), 1)
        self.assertEqual(composed[0].start, 0.0)
        self.assertEqual(composed[0].end, 5.74)

    def test_merge_preserves_both_lineages(self):
        segments = _segments(("같은 문장", 0.0, 2.0), ("같은 문장", 2.0, 2.02))
        composed = compose_readable_cues(segments)
        self.assertEqual(
            composed[0].source_segment_ids,
            (segments[0].identity, segments[1].identity),
        )

    def test_similar_text_is_not_merged(self):
        segments = _segments(("같은 문장", 0.0, 2.0), ("같은 문장!", 2.0, 4.0))
        self.assertEqual(len(compose_readable_cues(segments)), 2)

    def test_whitespace_difference_is_not_merged(self):
        segments = _segments(("같은 문장", 0.0, 2.0), (" 같은 문장", 2.0, 4.0))
        self.assertEqual(len(compose_readable_cues(segments)), 2)

    def test_non_adjacent_identical_cues_are_not_merged(self):
        segments = _segments(("가", 0.0, 2.0), ("나", 2.0, 4.0), ("가", 4.0, 6.0))
        self.assertEqual(len(compose_readable_cues(segments)), 3)

    def test_merge_is_refused_when_it_would_break_a_blocking_rule(self):
        long_text = "가" * 50  # already over the cue character limit, so merging cannot help
        segments = _segments((long_text, 0.0, 2.0), (long_text, 2.0, 4.0))
        composed = compose_readable_cues(segments)
        self.assertEqual(len(composed), 2)


class TimingExtensionTests(unittest.TestCase):
    def test_short_cue_extends_into_a_real_gap(self):
        segments = _segments(("네", 0.0, 0.5), ("다음", 3.0, 5.0))
        composed = compose_readable_cues(segments)
        self.assertAlmostEqual(composed[0].end, 1.0, places=9)

    def test_extension_never_encroaches_on_the_next_cue(self):
        segments = _segments(("네", 0.0, 0.5), ("다음", 0.7, 2.0))
        composed = compose_readable_cues(segments)
        self.assertLessEqual(composed[0].end, 0.7)
        self.assertGreaterEqual(composed[1].start, composed[0].end)

    def test_no_gap_keeps_the_short_cue_and_warns(self):
        segments = _segments(("네", 0.0, 0.5), ("다음", 0.5, 2.0))
        composed = compose_readable_cues(segments)
        self.assertEqual(composed[0].end, 0.5)
        validation = evaluate_readable_cues(_as_cues(composed))
        self.assertTrue(validation.deliverable)
        self.assertIn(READABILITY_DURATION_BELOW_TARGET, [f.code for f in validation.warnings])

    def test_the_next_cue_is_never_moved(self):
        segments = _segments(("네", 0.0, 0.5), ("다음", 3.0, 5.0))
        composed = compose_readable_cues(segments)
        self.assertEqual(composed[1].start, 3.0)
        self.assertEqual(composed[1].end, 5.0)


class LineCompositionTests(unittest.TestCase):
    def test_two_lines_from_one_break(self):
        text = "가나다라마바사아자차. 카타파하가나다라마바사"
        composed = compose_lines(text, READABILITY_PARAMETERS)
        self.assertEqual(composed.count(LF), 1)
        self.assertEqual(len(composed.split(LF)), 2)

    def test_removing_the_break_recovers_the_text(self):
        text = "가나다라마바사아자차. 카타파하가나다라마바사"
        self.assertEqual(compose_lines(text, READABILITY_PARAMETERS).replace(LF, ""), text)

    def test_short_text_gets_no_break(self):
        self.assertNotIn(LF, compose_lines("짧은 문장", READABILITY_PARAMETERS))

    def test_each_line_stays_within_the_limit(self):
        text = "가나다라마바사아자차. 카타파하가나다라마바사"
        for line in compose_lines(text, READABILITY_PARAMETERS).split(LF):
            self.assertLessEqual(display_length(line), 22)

    def test_unbreakable_long_text_stays_flat(self):
        text = "가" * 30
        self.assertEqual(compose_lines(text, READABILITY_PARAMETERS), text)

    def test_composition_refuses_pre_existing_line_breaks(self):
        with self.assertRaises(ValueError):
            compose_lines("가나" + LF + "다라", READABILITY_PARAMETERS)


class ValidationTests(unittest.TestCase):
    def _cue(self, text, start=0.0, end=3.0, ordinal=0):
        return _Cue(ordinal, text, start, end, (TranscriptSegmentId("transcript-segment:t:0"),))

    def test_blocking_and_warning_are_separated(self):
        validation = evaluate_readable_cues([self._cue("짧다", 0.0, 0.05)])
        self.assertFalse(validation.deliverable)
        self.assertEqual(
            [f.code for f in validation.blocking], [READABILITY_DURATION_BELOW_HARD_MINIMUM]
        )

    def test_duration_over_maximum_is_only_a_warning(self):
        validation = evaluate_readable_cues([self._cue("짧은 말", 0.0, 20.0)])
        self.assertTrue(validation.deliverable)
        self.assertIn(READABILITY_DURATION_ABOVE_MAXIMUM, [f.code for f in validation.warnings])

    def test_high_reading_rate_is_a_warning(self):
        validation = evaluate_readable_cues([self._cue("가나다라마바사아자차카타파하", 0.0, 1.0)])
        self.assertTrue(validation.deliverable)
        self.assertIn(READABILITY_READING_RATE_HIGH, [f.code for f in validation.warnings])

    def test_line_grammar_violations_block(self):
        for text, code in (
            (LF + "가나", READABILITY_LEADING_LINE_BREAK),
            ("가나" + LF, READABILITY_TRAILING_LINE_BREAK),
            ("가나" + LF * 2 + "다라", READABILITY_CONSECUTIVE_LINE_BREAKS),
            ("가" + LF + "나" + LF + "다", READABILITY_LINE_COUNT_EXCEEDED),
        ):
            validation = evaluate_readable_cues([self._cue(text)])
            self.assertIn(code, [f.code for f in validation.blocking], code)

    def test_long_line_and_long_cue_block(self):
        long_line = "가" * 30
        self.assertIn(
            READABILITY_LINE_TOO_LONG,
            [f.code for f in evaluate_readable_cues([self._cue(long_line)]).blocking],
        )
        oversize = "가" * 23 + LF + "나" * 23
        self.assertIn(
            READABILITY_CUE_TEXT_TOO_LONG,
            [f.code for f in evaluate_readable_cues([self._cue(oversize)]).blocking],
        )

    def test_overlap_blocks(self):
        cues = [self._cue("가", 0.0, 3.0, 0), self._cue("나", 2.0, 5.0, 1)]
        self.assertIn(
            READABILITY_CUES_OVERLAP, [f.code for f in evaluate_readable_cues(cues).blocking]
        )

    def test_representation_noise_is_not_an_overlap(self):
        """The PATCH-0039 boundary shape must not be reported as a readability defect."""

        cues = [
            self._cue("가", 3127.34, 3129.1000000000004, 0),
            self._cue("나", 3129.1, 3133.42, 1),
        ]
        self.assertNotIn(
            READABILITY_CUES_OVERLAP, [f.code for f in evaluate_readable_cues(cues).blocking]
        )

    def test_text_recovery_failure_blocks(self):
        segments = _segments(("원본 문장", 0.0, 3.0))
        cues = [self._cue("다른 문장")]
        validation = evaluate_readable_cues(cues, source_segments=segments)
        self.assertIn(READABILITY_TEXT_NOT_RECOVERABLE, [f.code for f in validation.blocking])

    def test_lineage_loss_blocks(self):
        segments = _segments(("가", 0.0, 2.0), ("나", 2.0, 4.0))
        cues = [_Cue(0, "가나", 0.0, 4.0, (segments[0].identity,))]
        validation = evaluate_readable_cues(cues, source_segments=segments)
        self.assertIn(READABILITY_SOURCE_LINEAGE_MISMATCH, [f.code for f in validation.blocking])

    def test_severity_is_fixed_per_code(self):
        from lectureos.application.readable_subtitle_validation import ReadabilityFinding

        with self.assertRaises(ValueError):
            ReadabilityFinding(
                READABILITY_CUES_OVERLAP, ReadabilitySeverity.WARNING, "wrong severity"
            )


class SerializerTests(unittest.TestCase):
    def test_serializer_preserves_the_line_break_verbatim(self):
        """L-3: the released serializer emits approved text verbatim; no wrapping is added."""

        payload = serialize_srt_cues([(0.0, 2.0, "첫 줄" + LF + "둘째 줄")])
        self.assertIn("첫 줄" + LF + "둘째 줄", payload)
        block = payload.rstrip(LF).split(LF * 2)[0]
        self.assertEqual(block.split(LF)[2:], ["첫 줄", "둘째 줄"])

    def test_serializer_does_not_wrap_a_long_single_line(self):
        long_text = "가" * 60
        payload = serialize_srt_cues([(0.0, 2.0, long_text)])
        self.assertEqual(payload.rstrip(LF).split(LF * 2)[0].split(LF)[2:], [long_text])

    def test_serialized_line_structure_agrees_with_the_approved_cues(self):
        cues = [
            _Cue(0, "첫 줄" + LF + "둘째 줄", 0.0, 2.0, ()),
            _Cue(1, "한 줄", 2.0, 4.0, ()),
        ]
        payload = serialize_srt_cues([(c.start, c.end, c.text) for c in cues])
        self.assertIsNone(verify_serialized_lines(cues, payload))

    def test_disagreeing_line_structure_is_detected(self):
        cues = [_Cue(0, "첫 줄" + LF + "둘째 줄", 0.0, 2.0, ())]
        payload = serialize_srt_cues([(0.0, 2.0, "첫 줄 둘째 줄")])
        finding = verify_serialized_lines(cues, payload)
        self.assertIsNotNone(finding)
        self.assertIs(finding.severity, ReadabilitySeverity.BLOCKING)


@unittest.skipUnless(_FIXTURE.is_file(), "real E2E fixture is not present in this checkout")
class RealFixtureTests(unittest.TestCase):
    """Regression over the preserved 2,564-cue corpus from the full-length validation."""

    @classmethod
    def setUpClass(cls):
        rows = [json.loads(line) for line in _FIXTURE.read_text(encoding="utf-8").splitlines()]
        cls.segments = tuple(
            _Segment(
                TranscriptSegmentId(f"transcript-segment:fixture:{index}"),
                row["text"],
                row["start"],
                row["end"],
            )
            for index, row in enumerate(rows)
        )
        cls.composed = compose_readable_cues(cls.segments)
        cls.cues = _as_cues(cls.composed)
        cls.validation = evaluate_readable_cues(cls.cues, source_segments=cls.segments)

    def test_text_is_recovered_exactly(self):
        recovered = "".join(cue.text.replace(LF, "") for cue in self.composed)
        self.assertEqual(recovered, merge_normalized_source_text(self.segments))

    def test_source_lineage_covers_every_segment_once_in_order(self):
        seen = []
        for cue in self.composed:
            for segment_id in cue.source_segment_ids:
                if segment_id.value not in seen:
                    seen.append(segment_id.value)
        self.assertEqual(seen, [segment.identity.value for segment in self.segments])

    def test_no_overlap_and_strict_order(self):
        for earlier, later in zip(self.composed, self.composed[1:]):
            self.assertGreaterEqual(later.start, earlier.end - 1e-6)
            self.assertGreaterEqual(later.start, earlier.start)

    def test_the_duplicate_cues_that_broke_import_are_merged(self):
        """The 0.020s duplicates are resolved, so no cue falls below the hard minimum."""

        below = [
            cue
            for cue in self.composed
            if cue.end - cue.start < READABILITY_PARAMETERS.hard_minimum_duration - 1e-6
        ]
        self.assertEqual(below, [])
        merged = [cue for cue in self.composed if len(cue.source_segment_ids) > 1]
        self.assertGreaterEqual(len(merged), 3)

    def test_short_conversational_cues_stay_separate(self):
        """R-6: `저요?`/`응` are distinct turns and must not be merged into one another."""

        texts = [cue.text.strip() for cue in self.composed]
        self.assertIn("저요?", texts)
        self.assertIn("응", texts)

    def test_no_cue_exceeds_the_character_limit(self):
        worst = max(cue_display_length(cue.text) for cue in self.composed)
        self.assertLessEqual(worst, READABILITY_PARAMETERS.maximum_cue_characters)

    def test_no_cue_exceeds_two_lines(self):
        self.assertEqual(max(cue.text.count(LF) for cue in self.composed), 1)

    def test_the_longest_source_cue_is_split(self):
        """The 145-character / 23-second cue is detected by the length and duration rules."""

        for cue in self.composed:
            if "중실이가 사냥을" in cue.text:
                self.assertLessEqual(cue_display_length(cue.text), 44)
                self.assertLessEqual(cue.end - cue.start, 7.0 + 1e-6)
                break
        else:  # pragma: no cover - the fixture must contain this utterance
            self.fail("the long explanation cue is missing from the fixture")

    def test_remaining_blocking_findings_are_only_unbreakable_lines(self):
        """Blocking findings must be enumerable and explained, not incidental."""

        codes = {finding.code for finding in self.validation.blocking}
        self.assertLessEqual(codes, {READABILITY_LINE_TOO_LONG})

    def test_serialized_payload_carries_the_approved_lines(self):
        payload = serialize_srt_cues(
            (cue.start, cue.end, cue.text) for cue in self.cues
        )
        self.assertIsNone(verify_serialized_lines(self.cues, payload))


class BuildReadableCuesTests(unittest.TestCase):
    def test_cue_identities_are_deterministic_within_the_candidate(self):
        @dataclass(frozen=True)
        class _Acquired:
            segments: tuple

        candidate_id = EffectiveSubtitleCandidateId("subtitle-effective-candidate:" + "d" * 64)
        acquired = _Acquired(_segments(("가나다. 라마바.", 0.0, 12.0)))
        first = build_readable_cues(candidate_id, acquired)
        second = build_readable_cues(candidate_id, acquired)
        self.assertEqual([c.identity for c in first], [c.identity for c in second])
        self.assertEqual([c.ordinal for c in first], list(range(len(first))))


if __name__ == "__main__":
    unittest.main()


class EnforcementBoundaryTests(unittest.TestCase):
    """Pins where readability validation is — and is not — consulted (041 §16 EN-4/EN-7).

    `PATCH-0042` resolved the question this class was written to anchor: Final Selection admission
    is the one enforcing boundary, and every other boundary is explicitly out of scope. Review
    Preparation and Human Decision must admit (EN-2/EN-3), and downstream must not re-evaluate
    (EN-7), so those modules must not consult the validator at all.
    """

    _MUST_NOT_CONSULT = (
        "lectureos.application.effective_subtitle_review_preparation",
        "lectureos.application.effective_subtitle_review_decision",
        "lectureos.application.effective_subtitle_srt_artifact",
        "lectureos.application.effective_srt_materialization",
    )
    _ENFORCING = "lectureos.application.effective_subtitle_final_selection"

    @staticmethod
    def _imports(module_name):
        import ast
        import importlib

        module = importlib.import_module(module_name)
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
            elif isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
        return imported

    def test_final_selection_is_the_enforcing_boundary(self):
        """EN-4: the one boundary that must consult the validator."""

        self.assertIn("readable_subtitle_validation", self._imports(self._ENFORCING))

    def test_no_other_boundary_consults_readability(self):
        import ast
        import importlib

        for module_name in self._MUST_NOT_CONSULT:
            module = importlib.import_module(module_name)
            tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module)
                elif isinstance(node, ast.Import):
                    imported.update(alias.name for alias in node.names)
            self.assertNotIn("readable_subtitle_validation", imported, module_name)
            self.assertNotIn(
                "lectureos.application.readable_subtitle_validation", imported, module_name
            )

    def test_validation_stores_nothing_and_decides_nothing(self):
        cue = _Cue(0, "가" * 30, 0.0, 3.0, (TranscriptSegmentId("transcript-segment:t:0"),))
        validation = evaluate_readable_cues([cue])
        self.assertTrue(validation.blocking)
        # The outcome is a value, not a command: it exposes findings and a derived boolean only.
        self.assertEqual(
            sorted(field for field in validation.__dataclass_fields__),
            ["findings", "parameters_version"],
        )
