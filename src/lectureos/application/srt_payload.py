"""Pure, aggregate-free deterministic SRT serialization primitives.

Extracted so both the legacy in-memory export service and the durable SRT Artifact Generation stage share
one timestamp algorithm. No wall-clock, locale, randomness, filesystem, or domain aggregate is involved;
identical inputs always produce byte-identical output.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from math import isfinite
from typing import Iterable


def srt_milliseconds(seconds: float) -> int:
    """Deterministic seconds→milliseconds with ROUND_HALF_UP (matches the released formatter)."""

    if not isfinite(seconds) or seconds < 0:
        raise ValueError("SRT timestamp must be finite and non-negative")
    return int(
        (Decimal(str(seconds)) * Decimal(1000)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )


def format_srt_timestamp(milliseconds: int) -> str:
    """Render milliseconds as the canonical SRT ``HH:MM:SS,mmm`` timestamp."""

    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def serialize_srt_cues(cues: Iterable[tuple[float, float, str]]) -> str:
    """Serialize ``(start_seconds, end_seconds, text)`` cues into a canonical SRT payload.

    Cues are numbered contiguously from 1 in the given order; blocks are separated by one blank line and a
    non-empty payload ends with a single trailing LF. An empty cue sequence yields the empty payload.
    """

    blocks = []
    for index, (start, end, text) in enumerate(cues, start=1):
        start_ms = srt_milliseconds(start)
        end_ms = srt_milliseconds(end)
        if end_ms <= start_ms:
            raise ValueError("SRT Cue duration collapses at millisecond precision")
        blocks.append(
            f"{index}\n"
            f"{format_srt_timestamp(start_ms)} --> {format_srt_timestamp(end_ms)}\n"
            f"{text}"
        )
    if not blocks:
        return ""
    return "\n\n".join(blocks) + "\n"


__all__ = [
    "format_srt_timestamp",
    "serialize_srt_cues",
    "srt_milliseconds",
]
