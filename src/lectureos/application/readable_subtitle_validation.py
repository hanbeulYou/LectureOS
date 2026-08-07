"""Readability validation for readable effective-subtitle candidates (041 §16 R-11, PATCH-0041).

A generation-specific, read-only boundary. It evaluates a readable Candidate's cue graph against the
versioned readability parameter set and returns findings in two severities:

* **blocking** — a structural or contract violation; the Candidate must not be delivered as it is.
* **warning** — an unmet readability goal whose canonical meaning is intact; surfaced for Review.

The separation is the point. `duration > maximum` is a *warning*, not corruption: the measured corpus
contains genuine long explanations, and one 13.4-second cue holds three characters with nothing to
split. Treating length alone as a defect would mark real lecture material broken.

This module reinterprets nothing. The legacy `subtitle_structural_validation` boundary belongs to a
different contract generation, is untouched, and keeps its meaning; these codes are additive and
scoped to readable candidates.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from .provider_transcript_admission import TIMING_BOUNDARY_TOLERANCE_SECONDS
from .readable_cue_composition import (
    READABILITY_PARAMETERS,
    ReadabilityParameters,
    cue_display_length,
    display_length,
    merge_normalized_source_text,
)

_LF = "\n"

# Durations are compared against the R-10 thresholds with the released representation tolerance
# (040 §14 A-10 / PATCH-0039 T-2). The same defect appears here: a cue whose true duration is exactly
# 0.100s can be stored as 0.09999999999990905 because its bounds came from different float paths, and
# an exact comparison would report the product minimum violated by 9e-14 seconds.
_TOLERANCE = TIMING_BOUNDARY_TOLERANCE_SECONDS


class ReadabilitySeverity(str, Enum):
    BLOCKING = "blocking"
    WARNING = "warning"


# Blocking codes (R-11).
READABILITY_DURATION_BELOW_HARD_MINIMUM = "READABILITY_DURATION_BELOW_HARD_MINIMUM"
READABILITY_DURATION_NOT_POSITIVE = "READABILITY_DURATION_NOT_POSITIVE"
READABILITY_ORDER_NOT_INCREASING = "READABILITY_ORDER_NOT_INCREASING"
READABILITY_CUES_OVERLAP = "READABILITY_CUES_OVERLAP"
READABILITY_LINE_COUNT_EXCEEDED = "READABILITY_LINE_COUNT_EXCEEDED"
READABILITY_LINE_TOO_LONG = "READABILITY_LINE_TOO_LONG"
READABILITY_CUE_TEXT_TOO_LONG = "READABILITY_CUE_TEXT_TOO_LONG"
READABILITY_LEADING_LINE_BREAK = "READABILITY_LEADING_LINE_BREAK"
READABILITY_TRAILING_LINE_BREAK = "READABILITY_TRAILING_LINE_BREAK"
READABILITY_CONSECUTIVE_LINE_BREAKS = "READABILITY_CONSECUTIVE_LINE_BREAKS"
READABILITY_EMPTY_LINE = "READABILITY_EMPTY_LINE"
READABILITY_TEXT_NOT_RECOVERABLE = "READABILITY_TEXT_NOT_RECOVERABLE"
READABILITY_SOURCE_LINEAGE_MISMATCH = "READABILITY_SOURCE_LINEAGE_MISMATCH"
READABILITY_SERIALIZED_LINES_DISAGREE = "READABILITY_SERIALIZED_LINES_DISAGREE"

# Warning codes (R-11).
READABILITY_DURATION_BELOW_TARGET = "READABILITY_DURATION_BELOW_TARGET"
READABILITY_DURATION_ABOVE_MAXIMUM = "READABILITY_DURATION_ABOVE_MAXIMUM"
READABILITY_READING_RATE_HIGH = "READABILITY_READING_RATE_HIGH"
READABILITY_LINE_COMPOSITION_UNAVAILABLE = "READABILITY_LINE_COMPOSITION_UNAVAILABLE"

BLOCKING_CODES = frozenset(
    {
        READABILITY_DURATION_BELOW_HARD_MINIMUM,
        READABILITY_DURATION_NOT_POSITIVE,
        READABILITY_ORDER_NOT_INCREASING,
        READABILITY_CUES_OVERLAP,
        READABILITY_LINE_COUNT_EXCEEDED,
        READABILITY_LINE_TOO_LONG,
        READABILITY_CUE_TEXT_TOO_LONG,
        READABILITY_LEADING_LINE_BREAK,
        READABILITY_TRAILING_LINE_BREAK,
        READABILITY_CONSECUTIVE_LINE_BREAKS,
        READABILITY_EMPTY_LINE,
        READABILITY_TEXT_NOT_RECOVERABLE,
        READABILITY_SOURCE_LINEAGE_MISMATCH,
        READABILITY_SERIALIZED_LINES_DISAGREE,
    }
)

WARNING_CODES = frozenset(
    {
        READABILITY_DURATION_BELOW_TARGET,
        READABILITY_DURATION_ABOVE_MAXIMUM,
        READABILITY_READING_RATE_HIGH,
        READABILITY_LINE_COMPOSITION_UNAVAILABLE,
    }
)


@dataclass(frozen=True, slots=True)
class ReadabilityFinding:
    """One evaluated readability fact about a cue (or the graph, when `cue_ordinal` is None)."""

    code: str
    severity: ReadabilitySeverity
    detail: str
    cue_ordinal: int | None = None

    def __post_init__(self) -> None:
        expected = (
            ReadabilitySeverity.BLOCKING
            if self.code in BLOCKING_CODES
            else ReadabilitySeverity.WARNING
        )
        if self.code not in BLOCKING_CODES and self.code not in WARNING_CODES:
            raise ValueError(f"unknown readability code: {self.code}")
        if self.severity is not expected:
            raise ValueError(f"readability code {self.code} has a fixed severity")


@dataclass(frozen=True, slots=True)
class ReadabilityValidation:
    """The read-only outcome; storing nothing and deciding nothing."""

    findings: tuple[ReadabilityFinding, ...]
    parameters_version: int

    @property
    def blocking(self) -> tuple[ReadabilityFinding, ...]:
        return tuple(f for f in self.findings if f.severity is ReadabilitySeverity.BLOCKING)

    @property
    def warnings(self) -> tuple[ReadabilityFinding, ...]:
        return tuple(f for f in self.findings if f.severity is ReadabilitySeverity.WARNING)

    @property
    def deliverable(self) -> bool:
        """Whether any finding reached blocking severity — a **derived observation, not a gate**.

        041 §16 R-11 classifies these violations as delivery-blocking but names no boundary that
        must refuse them, and §16's *Sections Not Re-scoped* clause leaves the Review, Final
        Selection, SRT Artifact, materialization, delivery and publication contracts unchanged. No
        boundary consults this value today; reading it as an enforced admission decision would
        assert a contract that does not exist.
        """

        return not self.blocking


def _line_findings(
    ordinal: int, text: str, parameters: ReadabilityParameters
) -> list[ReadabilityFinding]:
    findings: list[ReadabilityFinding] = []
    if text.startswith(_LF):
        findings.append(
            ReadabilityFinding(
                READABILITY_LEADING_LINE_BREAK,
                ReadabilitySeverity.BLOCKING,
                "cue text begins with a canonical line break",
                ordinal,
            )
        )
    if text.endswith(_LF):
        findings.append(
            ReadabilityFinding(
                READABILITY_TRAILING_LINE_BREAK,
                ReadabilitySeverity.BLOCKING,
                "cue text ends with a canonical line break",
                ordinal,
            )
        )
    if _LF * 2 in text:
        findings.append(
            ReadabilityFinding(
                READABILITY_CONSECUTIVE_LINE_BREAKS,
                ReadabilitySeverity.BLOCKING,
                "cue text contains consecutive canonical line breaks; a blank line inside a cue "
                "would corrupt SRT block framing",
                ordinal,
            )
        )
    lines = text.split(_LF)
    if len(lines) > parameters.maximum_lines:
        findings.append(
            ReadabilityFinding(
                READABILITY_LINE_COUNT_EXCEEDED,
                ReadabilitySeverity.BLOCKING,
                f"cue has {len(lines)} lines (maximum {parameters.maximum_lines})",
                ordinal,
            )
        )
    for index, line in enumerate(lines):
        if not line.strip():
            findings.append(
                ReadabilityFinding(
                    READABILITY_EMPTY_LINE,
                    ReadabilitySeverity.BLOCKING,
                    f"line {index + 1} carries no display text",
                    ordinal,
                )
            )
            continue
        if display_length(line) > parameters.maximum_line_characters:
            findings.append(
                ReadabilityFinding(
                    READABILITY_LINE_TOO_LONG,
                    ReadabilitySeverity.BLOCKING,
                    f"line {index + 1} is {display_length(line)} characters "
                    f"(maximum {parameters.maximum_line_characters})",
                    ordinal,
                )
            )
    total = cue_display_length(text)
    if total > parameters.maximum_cue_characters:
        findings.append(
            ReadabilityFinding(
                READABILITY_CUE_TEXT_TOO_LONG,
                ReadabilitySeverity.BLOCKING,
                f"cue carries {total} display characters "
                f"(maximum {parameters.maximum_cue_characters})",
                ordinal,
            )
        )
    elif total > parameters.maximum_line_characters and _LF not in text:
        findings.append(
            ReadabilityFinding(
                READABILITY_LINE_COMPOSITION_UNAVAILABLE,
                ReadabilitySeverity.WARNING,
                f"cue needs two lines at {total} characters but no safe break point exists",
                ordinal,
            )
        )
    return findings


def _timing_findings(
    ordinal: int, cue, parameters: ReadabilityParameters
) -> list[ReadabilityFinding]:
    findings: list[ReadabilityFinding] = []
    if cue.start is None or cue.end is None:
        return findings
    duration = cue.end - cue.start
    if duration <= 0:
        findings.append(
            ReadabilityFinding(
                READABILITY_DURATION_NOT_POSITIVE,
                ReadabilitySeverity.BLOCKING,
                f"cue duration is {duration:.6f}s",
                ordinal,
            )
        )
        return findings
    if duration < parameters.hard_minimum_duration - _TOLERANCE:
        findings.append(
            ReadabilityFinding(
                READABILITY_DURATION_BELOW_HARD_MINIMUM,
                ReadabilitySeverity.BLOCKING,
                f"cue duration {duration:.3f}s is below the product hard minimum "
                f"{parameters.hard_minimum_duration:.3f}s",
                ordinal,
            )
        )
    elif duration < parameters.target_minimum_duration - _TOLERANCE:
        findings.append(
            ReadabilityFinding(
                READABILITY_DURATION_BELOW_TARGET,
                ReadabilitySeverity.WARNING,
                f"cue duration {duration:.3f}s is below the readability target "
                f"{parameters.target_minimum_duration:.3f}s",
                ordinal,
            )
        )
    if duration > parameters.maximum_duration + _TOLERANCE:
        findings.append(
            ReadabilityFinding(
                READABILITY_DURATION_ABOVE_MAXIMUM,
                ReadabilitySeverity.WARNING,
                f"cue duration {duration:.3f}s exceeds {parameters.maximum_duration:.3f}s and no "
                "safe split point was available",
                ordinal,
            )
        )
    rate = cue_display_length(cue.text) / duration
    if rate > parameters.cps_warning_threshold:
        findings.append(
            ReadabilityFinding(
                READABILITY_READING_RATE_HIGH,
                ReadabilitySeverity.WARNING,
                f"reading rate {rate:.1f} characters/second exceeds "
                f"{parameters.cps_warning_threshold:.0f}",
                ordinal,
            )
        )
    return findings


def evaluate_readable_cues(
    cues: Sequence,
    *,
    source_segments: Sequence | None = None,
    parameters: ReadabilityParameters = READABILITY_PARAMETERS,
) -> ReadabilityValidation:
    """Evaluate one readable candidate's ordered cue graph. Read-only; stores nothing."""

    findings: list[ReadabilityFinding] = []
    ordered = sorted(cues, key=lambda cue: cue.ordinal)

    previous_end: float | None = None
    previous_start: float | None = None
    for cue in ordered:
        findings.extend(_line_findings(cue.ordinal, cue.text, parameters))
        findings.extend(_timing_findings(cue.ordinal, cue, parameters))
        if cue.start is None or cue.end is None:
            continue
        if previous_start is not None and cue.start < previous_start - _TOLERANCE:
            findings.append(
                ReadabilityFinding(
                    READABILITY_ORDER_NOT_INCREASING,
                    ReadabilitySeverity.BLOCKING,
                    "cue starts before the preceding displayed cue",
                    cue.ordinal,
                )
            )
        if previous_end is not None and cue.start < previous_end - _TOLERANCE:
            findings.append(
                ReadabilityFinding(
                    READABILITY_CUES_OVERLAP,
                    ReadabilitySeverity.BLOCKING,
                    "cue overlaps the preceding displayed cue",
                    cue.ordinal,
                )
            )
        previous_start, previous_end = cue.start, cue.end

    if source_segments is not None:
        recovered = "".join(cue.text.replace(_LF, "") for cue in ordered)
        expected = merge_normalized_source_text(source_segments)
        if recovered != expected:
            findings.append(
                ReadabilityFinding(
                    READABILITY_TEXT_NOT_RECOVERABLE,
                    ReadabilitySeverity.BLOCKING,
                    "removing the canonical line breaks does not recover the merge-normalized "
                    "source text",
                )
            )
        covered: list[str] = []
        for cue in ordered:
            for segment_id in cue.source_segment_ids:
                if segment_id.value not in covered:
                    covered.append(segment_id.value)
        expected_ids = [segment.identity.value for segment in source_segments]
        if covered != expected_ids:
            findings.append(
                ReadabilityFinding(
                    READABILITY_SOURCE_LINEAGE_MISMATCH,
                    ReadabilitySeverity.BLOCKING,
                    "cue source lineage does not cover the consumed segments exactly once, in order",
                )
            )

    return ReadabilityValidation(tuple(findings), parameters.version)


def verify_serialized_lines(cues: Sequence, srt_content: str) -> ReadabilityFinding | None:
    """Confirm the serialized payload carries the approved line structure verbatim (R-11).

    The released `canonical_srt` v1 serializer emits cue text verbatim, so this is an assertion
    about that guarantee holding, not a re-implementation of serialization.
    """

    # The canonical payload ends with a single trailing LF; keeping it would append a phantom empty
    # line to the last block and report a disagreement that does not exist.
    payload = srt_content[:-1] if srt_content.endswith(_LF) else srt_content
    blocks = [block for block in payload.split(_LF * 2) if block.strip()]
    ordered = sorted(cues, key=lambda cue: cue.ordinal)
    if len(blocks) != len(ordered):
        return ReadabilityFinding(
            READABILITY_SERIALIZED_LINES_DISAGREE,
            ReadabilitySeverity.BLOCKING,
            f"serialized payload has {len(blocks)} blocks for {len(ordered)} approved cues",
        )
    for cue, block in zip(ordered, blocks):
        lines = block.split("\n")
        if len(lines) < 3:
            return ReadabilityFinding(
                READABILITY_SERIALIZED_LINES_DISAGREE,
                ReadabilitySeverity.BLOCKING,
                "serialized block is missing its text lines",
                cue.ordinal,
            )
        if "\n".join(lines[2:]) != cue.text:
            return ReadabilityFinding(
                READABILITY_SERIALIZED_LINES_DISAGREE,
                ReadabilitySeverity.BLOCKING,
                "serialized line structure differs from the approved cue text",
                cue.ordinal,
            )
    return None


__all__ = [
    "BLOCKING_CODES",
    "WARNING_CODES",
    "ReadabilityFinding",
    "ReadabilitySeverity",
    "ReadabilityValidation",
    "evaluate_readable_cues",
    "verify_serialized_lines",
]
