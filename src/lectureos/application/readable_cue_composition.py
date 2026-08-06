"""Readable subtitle cue composition for the effective-transcript generation (041 §16, PATCH-0041).

The second generator of the effective-transcript subtitle contract generation. It consumes the same
`EffectiveTranscriptInput` as `deterministic_segment_passthrough` and produces a **separate**
Candidate whose cues are display units rather than transcript units: over-long cues are split,
character-identical adjacent duplicates are merged, sub-second cues are extended into real gaps, and
cues wider than one line are composed into two lines with a single canonical `LF`.

It is a **proposal**. It creates no review record, no decision, no selection, and no export
eligibility, and it never supersedes or modifies the passthrough Candidate (R-3, R-12).

What it never does (R-4): add, delete, rewrite, normalize, trim, re-order, translate, punctuate or
case-fold a character. The one permitted insertion is the `LF` that carries the approved line
structure (L-1), and removing every inserted `LF` recovers the composed text exactly.

Two invariants are worth stating together because they interact. R-4 requires the source text to be
recoverable; R-6 authorizes merging adjacent cues whose text is character-identical and carrying that
text **once**. Recovery is therefore exact against the *merge-normalized* source — the source
sequence with authorized identical-adjacent duplicates collapsed — not against the raw sequence.
`merge_normalized_source_text` computes that reference so the invariant is testable rather than
rhetorical.

Character counts are measured on `str.strip()`-ed text. Leading and trailing whitespace carries no
display width, and the corpus this policy was measured against prefixes almost every segment with a
space, so counting stored whitespace would inflate every measurement against the thresholds it is
compared to.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from typing import Sequence

from lectureos.transcript.identities import TranscriptSegmentId

from .provider_transcript_admission import TIMING_BOUNDARY_TOLERANCE_SECONDS

READABLE_GENERATOR_KIND = "readable_cue_composition"
READABLE_GENERATOR_VERSION = 1

# 041 §16 R-10 / R-13. Bumping any value below REQUIRES bumping this version: the parameter version
# participates in Candidate identity, so a silent value change would let two different policies share
# one identity. `test_readability_parameter_set_is_pinned_to_its_version` fails if they drift apart.
READABILITY_PARAMETERS_VERSION = 1

# Tier 1: sentence terminators. Tier 2: comma / conjunctive punctuation. Tier 3 is whitespace and is
# handled positionally. Deliberately punctuation-only: no morphological analyzer, no NLP dependency
# (R-5), so "conjunctive boundary" is realized as the comma family rather than as parsed grammar.
_TERMINATORS = ".?!。？！"
_SECONDARY = ",;:，、；："

_LF = "\n"


@dataclass(frozen=True, slots=True)
class ReadabilityParameters:
    """The versioned readability parameter set (041 §16 R-10) — immutable, not user-configurable."""

    hard_minimum_duration: float = 0.100
    target_minimum_duration: float = 1.000
    maximum_duration: float = 7.000
    maximum_line_characters: int = 22
    maximum_lines: int = 2
    maximum_cue_characters: int = 44
    cps_warning_threshold: float = 12.0
    version: int = READABILITY_PARAMETERS_VERSION

    def __post_init__(self) -> None:
        if not (0 < self.hard_minimum_duration <= self.target_minimum_duration):
            raise ValueError("hard minimum must be positive and not exceed the target minimum")
        if self.target_minimum_duration >= self.maximum_duration:
            raise ValueError("target minimum must be below the maximum duration")
        if self.maximum_lines < 1 or self.maximum_line_characters < 1:
            raise ValueError("line limits must be positive")
        if self.maximum_cue_characters < self.maximum_line_characters:
            raise ValueError("cue character limit must not be below the line limit")
        if self.version < 1:
            raise ValueError("readability parameter version must be >= 1")

    def fingerprint(self) -> str:
        """Digest of the parameter values, so a test can pin them to `version` (R-13)."""

        payload = {
            "hard_minimum_duration": self.hard_minimum_duration,
            "target_minimum_duration": self.target_minimum_duration,
            "maximum_duration": self.maximum_duration,
            "maximum_line_characters": self.maximum_line_characters,
            "maximum_lines": self.maximum_lines,
            "maximum_cue_characters": self.maximum_cue_characters,
            "cps_warning_threshold": self.cps_warning_threshold,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


READABILITY_PARAMETERS = ReadabilityParameters()


def display_length(text: str) -> int:
    """Display character count: stored whitespace at the ends carries no width."""

    return len(text.strip())


def cue_display_length(text: str) -> int:
    """Display character count of a composed cue, excluding the canonical line breaks."""

    return sum(display_length(line) for line in text.split(_LF))


@dataclass(frozen=True, slots=True)
class ComposedCue:
    """One composed display cue before it is given a canonical identity."""

    text: str
    start: float | None
    end: float | None
    source_segment_ids: tuple[TranscriptSegmentId, ...]

    @property
    def duration(self) -> float | None:
        if self.start is None or self.end is None:
            return None
        return self.end - self.start


def merge_normalized_source_text(segments: Sequence) -> str:
    """The text R-4 recovery is checked against: source order with R-6 merges collapsed."""

    parts: list[str] = []
    previous: str | None = None
    for segment in segments:
        if previous is not None and segment.text == previous:
            continue
        parts.append(segment.text)
        previous = segment.text
    return "".join(parts)


# -- stage 1: identical adjacent merge (R-6) -------------------------------------------------------


def _merge_identical_adjacent(
    segments: Sequence, parameters: ReadabilityParameters
) -> list[ComposedCue]:
    merged: list[ComposedCue] = []
    for segment in segments:
        cue = ComposedCue(
            text=segment.text,
            start=segment.start,
            end=segment.end,
            source_segment_ids=(segment.identity,),
        )
        if not merged:
            merged.append(cue)
            continue
        previous = merged[-1]
        # Exactly identical canonical text only. Not similar, not whitespace-insensitive, not
        # semantically close — no evidence distinguishes one speaker continuing from two turns.
        if previous.text != cue.text:
            merged.append(cue)
            continue
        if segment.identity in previous.source_segment_ids:
            merged.append(cue)
            continue
        union_start = previous.start if previous.start is not None else cue.start
        union_end = cue.end if cue.end is not None else previous.end
        candidate = ComposedCue(
            text=previous.text,
            start=union_start,
            end=union_end,
            source_segment_ids=previous.source_segment_ids + (segment.identity,),
        )
        # A merge that would break a blocking rule is refused; the duplicate stays its own cue.
        if cue_display_length(candidate.text) > parameters.maximum_cue_characters:
            merged.append(cue)
            continue
        if candidate.start is not None and candidate.end is not None:
            if candidate.end < candidate.start:
                merged.append(cue)
                continue
        merged[-1] = candidate
    return merged


# -- stage 2: split (R-5) + derived timing (R-8) ---------------------------------------------------


def split_positions(text: str) -> tuple[tuple[int, int], ...]:
    """Every admissible cut position as ``(tier, index)``, best tier first.

    A cut at ``index`` yields ``text[:index]`` and ``text[index:]``; both sides must carry display
    text. Cuts never fall inside a word: tier 1 and 2 cut after punctuation, tier 3 cuts after a
    whitespace run so the following line starts on a word and no character is consumed.
    """

    positions: list[tuple[int, int]] = []
    length = len(text)
    for index, character in enumerate(text):
        cut: int | None = None
        tier: int | None = None
        if character in _TERMINATORS:
            cut, tier = index + 1, 1
        elif character in _SECONDARY:
            cut, tier = index + 1, 2
        elif character.isspace() and (index + 1 >= length or not text[index + 1].isspace()):
            cut, tier = index + 1, 3
        if cut is None or tier is None or cut >= length:
            continue
        if not text[:cut].strip() or not text[cut:].strip():
            continue
        positions.append((tier, cut))
    return tuple(positions)


def _best_cut(text: str) -> int | None:
    """The admissible cut closest to the middle within the best available tier."""

    positions = split_positions(text)
    if not positions:
        return None
    best_tier = min(tier for tier, _ in positions)
    midpoint = len(text) / 2
    return min(
        (cut for tier, cut in positions if tier == best_tier),
        key=lambda cut: (abs(cut - midpoint), cut),
    )


def _interpolate(cue: ComposedCue, left_text: str, right_text: str) -> tuple[float, float, float]:
    """Character-proportional derived boundary inside the parent range (R-8).

    Proportion uses display characters excluding line breaks. The parent's own start and end are
    reused verbatim, so no float accumulation can push a child outside the source range.
    """

    assert cue.start is not None and cue.end is not None
    left = cue_display_length(left_text)
    right = cue_display_length(right_text)
    total = left + right
    span = cue.end - cue.start
    if total <= 0 or span <= 0:
        return cue.start, cue.start, cue.end
    boundary = cue.start + span * (left / total)
    if boundary <= cue.start or boundary >= cue.end:
        return cue.start, cue.start, cue.end
    return cue.start, boundary, cue.end


def _needs_split(cue: ComposedCue, parameters: ReadabilityParameters) -> bool:
    if cue_display_length(cue.text) > parameters.maximum_cue_characters:
        return True
    duration = cue.duration
    return duration is not None and duration > parameters.maximum_duration


def _split_cue(cue: ComposedCue, parameters: ReadabilityParameters) -> list[ComposedCue]:
    """Recursively split while a safe point exists; otherwise return the cue unchanged (R-5)."""

    if not _needs_split(cue, parameters):
        return [cue]
    cut = _best_cut(cue.text)
    if cut is None:
        return [cue]
    left_text, right_text = cue.text[:cut], cue.text[cut:]
    if cue.start is None or cue.end is None:
        # Untimed input: splitting would require inventing a boundary, so it is refused.
        return [cue]
    start, boundary, end = _interpolate(cue, left_text, right_text)
    if boundary <= start or boundary >= end:
        return [cue]
    # A split that would produce a child below the product hard minimum is not performed (R-5/R-10).
    floor = parameters.hard_minimum_duration - TIMING_BOUNDARY_TOLERANCE_SECONDS
    if (boundary - start) < floor or (end - boundary) < floor:
        return [cue]
    left = ComposedCue(left_text, start, boundary, cue.source_segment_ids)
    right = ComposedCue(right_text, boundary, end, cue.source_segment_ids)
    return _split_cue(left, parameters) + _split_cue(right, parameters)


# -- stage 3: gap extension (R-7) ------------------------------------------------------------------


def _extend_into_gaps(
    cues: list[ComposedCue], parameters: ReadabilityParameters
) -> list[ComposedCue]:
    extended: list[ComposedCue] = list(cues)
    for index, cue in enumerate(extended):
        duration = cue.duration
        if duration is None or duration >= parameters.target_minimum_duration:
            continue
        if index + 1 >= len(extended):
            # No following cue means no observed gap; the timeline end is not known here, so the
            # short cue is kept rather than extended on an assumption.
            continue
        following = extended[index + 1]
        if following.start is None or cue.end is None:
            continue
        ceiling = following.start
        target = cue.start + parameters.target_minimum_duration
        new_end = min(target, ceiling)
        if new_end > cue.end:
            extended[index] = replace(cue, end=new_end)
    return extended


# -- stage 4: line composition (L-1, L-2) ----------------------------------------------------------


def compose_lines(text: str, parameters: ReadabilityParameters) -> str:
    """Insert at most ``maximum_lines - 1`` canonical `LF`s; never delete or move a character."""

    if _LF in text:
        raise ValueError("source cue text must not already contain a canonical line break")
    if display_length(text) <= parameters.maximum_line_characters:
        return text
    if parameters.maximum_lines < 2:
        return text
    positions = split_positions(text)
    if not positions:
        return text
    best_tier = min(tier for tier, _ in positions)
    balanced = [
        cut
        for tier, cut in positions
        if tier == best_tier
        and display_length(text[:cut]) <= parameters.maximum_line_characters
        and display_length(text[cut:]) <= parameters.maximum_line_characters
    ]
    if not balanced:
        # Any tier is acceptable if the best one cannot produce two conforming lines.
        balanced = [
            cut
            for _, cut in positions
            if display_length(text[:cut]) <= parameters.maximum_line_characters
            and display_length(text[cut:]) <= parameters.maximum_line_characters
        ]
    if not balanced:
        # No safe break exists; the flat text is kept and blocking validation reports it (§7).
        return text
    cut = min(
        balanced,
        key=lambda index: (
            abs(display_length(text[:index]) - display_length(text[index:])),
            index,
        ),
    )
    composed = text[:cut] + _LF + text[cut:]
    if composed.replace(_LF, "") != text:
        raise ValueError("line composition must insert only, never alter the text")
    return composed


# -- entry point -----------------------------------------------------------------------------------


def compose_readable_cues(
    segments: Sequence, parameters: ReadabilityParameters = READABILITY_PARAMETERS
) -> tuple[ComposedCue, ...]:
    """Compose the ordered display cues for one acquired effective transcript snapshot."""

    merged = _merge_identical_adjacent(segments, parameters)
    split: list[ComposedCue] = []
    for cue in merged:
        split.extend(_split_cue(cue, parameters))
    extended = _extend_into_gaps(split, parameters)
    return tuple(
        replace(cue, text=compose_lines(cue.text, parameters)) for cue in extended
    )


__all__ = [
    "READABILITY_PARAMETERS",
    "READABILITY_PARAMETERS_VERSION",
    "READABLE_GENERATOR_KIND",
    "READABLE_GENERATOR_VERSION",
    "ComposedCue",
    "ReadabilityParameters",
    "compose_lines",
    "compose_readable_cues",
    "cue_display_length",
    "display_length",
    "merge_normalized_source_text",
    "split_positions",
]


def build_readable_cues(candidate_id, acquired):
    """`SubtitleGeneratorSpec.build_cues` for `readable_cue_composition` (041 §16).

    Imported lazily inside the function so this module stays free of a cycle with the generation
    module that owns the cue aggregate and its identity derivation.
    """

    from .effective_subtitle_generation import (
        EffectiveSubtitleCue,
        derive_effective_cue_identity,
    )

    composed = compose_readable_cues(acquired.segments, READABILITY_PARAMETERS)
    return tuple(
        EffectiveSubtitleCue(
            identity=derive_effective_cue_identity(
                candidate_id, ordinal, cue.source_segment_ids[0]
            ),
            candidate_id=candidate_id,
            ordinal=ordinal,
            text=cue.text,
            source_segment_ids=cue.source_segment_ids,
            start=cue.start,
            end=cue.end,
        )
        for ordinal, cue in enumerate(composed)
    )


def readable_generator_spec():
    """The `readable_cue_composition` generator descriptor (R-2/R-13)."""

    from .effective_subtitle_generation import SubtitleGeneratorSpec

    return SubtitleGeneratorSpec(
        kind=READABLE_GENERATOR_KIND,
        version=READABLE_GENERATOR_VERSION,
        parameters_version=READABILITY_PARAMETERS.version,
        build_cues=build_readable_cues,
    )


__all__ += ["build_readable_cues", "readable_generator_spec"]
