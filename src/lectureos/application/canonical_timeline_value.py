"""Canonical numeric representation for Source Timeline values (042 effective generation).

One shared primitive for every effective-generation contract that puts a timeline bound into a
canonical identity hash **and** into a SQLite `REAL` column. Both GOAL-025 (Analysis Finding) and
GOAL-026 (Lecture Segmentation) grew their own copy of this logic, and the second copy was written
only after the first had already shipped a defect; a third copy would be how the next one ships.

Two distinct spellings of one bound must never mint two identities:

* ``json.dumps(1)`` is ``1`` while ``json.dumps(1.0)`` is ``1.0`` — different digests.
* ``-0.0 < 0`` is False, so negative zero passes a non-negative check, and ``json.dumps(-0.0)`` is
  ``-0.0`` while ``json.dumps(0.0)`` is ``0.0`` — different digests again.

SQLite's REAL affinity stores ``1.0`` and ``0.0`` in both cases. An uncollapsed bound therefore
leaves a row whose identity can never re-derive from its own stored payload: permanently unreadable
and permanently flagged by repository validation, in an insert-only table with no delete path.

The helper raises a caller-supplied error type so each boundary keeps a single coherent error
family — an `OverflowError` from an int too large for a double must not escape as a bare
`ArithmeticError`.
"""

from __future__ import annotations

from math import isfinite
from typing import Callable


def canonical_timeline_value(
    value: float, *, error: Callable[[str], Exception], subject: str
) -> float:
    """Validate one timeline value and return its single canonical ``float`` form.

    Rejects non-numbers, booleans, non-finite values, negatives, and magnitudes beyond a double.
    Collapses negative zero. ``subject`` names the value in the raised message (for example
    ``"lecture segment range start"``); ``error`` builds the boundary's own exception.
    """

    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise error(f"{subject} must be a real number")
    try:
        canonical = float(value)
    except OverflowError as overflow:
        raise error(f"{subject} is out of representable range") from overflow
    if not isfinite(canonical):
        raise error(f"{subject} must be finite")
    if canonical < 0:
        raise error(f"{subject} must not be negative")
    return 0.0 if canonical == 0.0 else canonical


__all__ = ["canonical_timeline_value"]
