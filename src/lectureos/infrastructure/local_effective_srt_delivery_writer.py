"""Infrastructure local-file adapter for Effective SRT Delivery (GOAL-019).

The GOAL-018 hardened writer (approved-root containment, symlink rejection, atomic temporary-file
discipline, no-overwrite-of-different-bytes, explicit ``replace`` only) plus one observational
capability required by the delivery contract: ``path_of`` resolves a relative location to its
contained absolute path so the service can reject source/destination aliasing and report physical
paths distinctly. No safety property is weakened; resolution reuses the released containment
checks unchanged.
"""

from __future__ import annotations

from .local_effective_srt_file_writer import LocalEffectiveSrtFileWriter


class LocalEffectiveSrtDeliveryWriter(LocalEffectiveSrtFileWriter):
    """The GOAL-018 writer plus contained absolute-path resolution (GOAL-019)."""

    def path_of(self, *, relative_location: str) -> str:
        return str(self._resolve(relative_location))


__all__ = ["LocalEffectiveSrtDeliveryWriter"]
