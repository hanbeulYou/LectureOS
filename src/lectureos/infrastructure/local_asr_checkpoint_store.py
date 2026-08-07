"""Filesystem execution checkpoint store for the local ASR adapter (040 §15 CP-9…CP-21).

Infrastructure half of `PATCH-0044`'s CP-4 split: storage, atomic metadata replacement, complete-
record append and recovery, advisory locking, corruption detection, deletion and age-based
collection. It never reconstructs the product meaning of the binding — it stores what Application
gives it and reports compatibility field by field.

Layout beneath the approved scratch root:

```text
<scratch-root>/local-asr/<checkpoint-id>/
    metadata.json     replaced atomically
    segments.jsonl    appended; only complete lines are ever reused
    lock              flock target; ownership released by the OS when the process dies
```

Durability is best-effort by contract (CP-10), so this store does **not** fsync per record: a
2,500-segment run would pay a synchronous disk round-trip per segment for a guarantee the contract
declines to make. An OS crash that loses unflushed records yields an incomplete tail, which
`load` discards — that is the designed outcome, not corruption.
"""

from __future__ import annotations

import fcntl
import json
import os
import shutil
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

from lectureos.application.local_asr_checkpoint import (
    CHECKPOINT_FORMAT_VERSION,
    CheckpointBinding,
    CheckpointDiscardReason,
    CheckpointOwnershipError,
    CheckpointSegment,
    LoadedCheckpoint,
    segments_are_increasing,
)

_METADATA = "metadata.json"
_SEGMENTS = "segments.jsonl"
_LOCK = "lock"
_SUBDIRECTORY = "local-asr"


def default_checkpoint_root() -> Path:
    """A scratch root outside the repository and outside any canonical storage directory.

    The OS temporary directory is used deliberately: it is absolute, platform-appropriate, never
    inside the source tree or the SQLite database's directory, and carries no Product Domain
    meaning. An operator may override it; nothing about it participates in any identity.
    """

    return Path(tempfile.gettempdir()) / "lectureos" / _SUBDIRECTORY


class LocalAsrCheckpointFileStore:
    """The concrete checkpoint store. Reports absence rather than raising on ordinary I/O trouble."""

    def __init__(self, root: str | Path) -> None:
        resolved = Path(root).expanduser()
        if not resolved.is_absolute():
            raise ValueError("checkpoint root must be an absolute path")
        self._root = resolved

    @property
    def root(self) -> Path:
        return self._root

    # -- paths -----------------------------------------------------------------------------------

    def _directory(self, binding: CheckpointBinding) -> Path:
        # The id is a SHA-256 hex digest, so it cannot escape the root or inject a path component.
        return self._root / binding.checkpoint_id

    # -- ownership (CP-20) -----------------------------------------------------------------------

    @contextmanager
    def owned(self, binding: CheckpointBinding):
        """Exclusive, non-blocking ownership of one checkpoint key.

        `flock` is chosen because the kernel releases it when the owning process dies, so no
        heartbeat, lease, or stale-owner sweep is needed — which is what lets CP-20 forbid inventing
        one. A second execution is refused outright; it never queues, appends alongside, or steals.
        """

        directory = self._directory(binding)
        directory.mkdir(parents=True, exist_ok=True)
        handle = open(directory / _LOCK, "a+")
        try:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as error:
                raise CheckpointOwnershipError(
                    "another execution already owns this local ASR checkpoint "
                    f"({binding.identity}); it is not queued, shared, or taken over"
                ) from error
            yield
        finally:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
            handle.close()

    # -- read (CP-11, CP-19) ---------------------------------------------------------------------

    def load(self, binding: CheckpointBinding) -> LoadedCheckpoint:
        directory = self._directory(binding)
        metadata_path = directory / _METADATA
        if not metadata_path.is_file():
            return LoadedCheckpoint(discard_reason=CheckpointDiscardReason.ABSENT)
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeDecodeError):
            return LoadedCheckpoint(discard_reason=CheckpointDiscardReason.UNREADABLE_METADATA)
        if not isinstance(metadata, dict):
            return LoadedCheckpoint(discard_reason=CheckpointDiscardReason.UNREADABLE_METADATA)
        if metadata.get("checkpoint_format_version") != CHECKPOINT_FORMAT_VERSION:
            return LoadedCheckpoint(discard_reason=CheckpointDiscardReason.UNKNOWN_FORMAT_VERSION)
        if metadata.get("binding") != binding.as_payload():
            # Field-by-field equality: a device, compute-type or engine-version change is an
            # incompatibility, not an upgrade path (CP-7).
            return LoadedCheckpoint(discard_reason=CheckpointDiscardReason.BINDING_MISMATCH)

        segments_path = directory / _SEGMENTS
        if not segments_path.is_file():
            return LoadedCheckpoint(discard_reason=CheckpointDiscardReason.NO_COMPLETE_SEGMENT)
        try:
            raw = segments_path.read_bytes()
        except OSError:
            return LoadedCheckpoint(discard_reason=CheckpointDiscardReason.NO_COMPLETE_SEGMENT)

        # Only complete records count. Anything after the final newline is an incomplete tail from
        # an interrupted write and is discarded rather than repaired (CP-11).
        cut = raw.rfind(b"\n")
        if cut < 0:
            return LoadedCheckpoint(discard_reason=CheckpointDiscardReason.NO_COMPLETE_SEGMENT)
        try:
            body = raw[: cut + 1].decode("utf-8")
        except UnicodeDecodeError:
            return LoadedCheckpoint(discard_reason=CheckpointDiscardReason.MALFORMED_SEGMENT)

        segments: list[CheckpointSegment] = []
        for line in body.splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                segment = CheckpointSegment(
                    ordinal=int(record["ordinal"]),
                    start=float(record["start"]),
                    end=float(record["end"]),
                    text=record["text"],
                )
            except (ValueError, TypeError, KeyError):
                return LoadedCheckpoint(discard_reason=CheckpointDiscardReason.MALFORMED_SEGMENT)
            segments.append(segment)

        if not segments:
            return LoadedCheckpoint(discard_reason=CheckpointDiscardReason.NO_COMPLETE_SEGMENT)
        if not segments_are_increasing(segments):
            return LoadedCheckpoint(discard_reason=CheckpointDiscardReason.NON_INCREASING_SEGMENTS)
        return LoadedCheckpoint(segments=tuple(segments))

    # -- write (CP-11) ---------------------------------------------------------------------------

    def begin(self, binding: CheckpointBinding) -> None:
        """Start a fresh checkpoint for this binding, discarding any prior content for the key."""

        directory = self._directory(binding)
        directory.mkdir(parents=True, exist_ok=True)
        try:
            (directory / _SEGMENTS).unlink(missing_ok=True)
            self._atomic_write(
                directory / _METADATA,
                json.dumps(
                    {
                        "checkpoint_format_version": CHECKPOINT_FORMAT_VERSION,
                        "binding": binding.as_payload(),
                        # Operational only; participates in no identity (CP-2).
                        "created_at": time.time(),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ).encode("utf-8"),
            )
        except OSError:
            # Best-effort: an unwritable checkpoint costs the resume opportunity, never the run.
            return

    def append(self, binding: CheckpointBinding, segment: CheckpointSegment) -> None:
        line = json.dumps(segment.as_payload(), ensure_ascii=False, sort_keys=True) + "\n"
        try:
            with open(self._directory(binding) / _SEGMENTS, "a", encoding="utf-8") as handle:
                handle.write(line)
        except OSError:
            # CP-10: losing a checkpoint is never an error condition. The execution continues and
            # only the resume opportunity is lost — the canonical result is unaffected.
            return

    def delete(self, binding: CheckpointBinding) -> None:
        shutil.rmtree(self._directory(binding), ignore_errors=True)

    # -- collection (CP-21) ----------------------------------------------------------------------

    def collect_older_than(self, cutoff_epoch_seconds: float) -> int:
        """Remove checkpoints last modified before the cutoff. Returns how many were removed.

        The cutoff is supplied by the caller: CP-21 leaves the retention duration to operational
        configuration, so this primitive deliberately holds no default TTL and schedules nothing.
        """

        if not self._root.is_dir():
            return 0
        removed = 0
        for entry in self._root.iterdir():
            if not entry.is_dir():
                continue
            try:
                modified = max(
                    (child.stat().st_mtime for child in entry.iterdir()),
                    default=entry.stat().st_mtime,
                )
            except OSError:
                continue
            if modified < cutoff_epoch_seconds:
                shutil.rmtree(entry, ignore_errors=True)
                removed += 1
        return removed

    # -- helpers ---------------------------------------------------------------------------------

    @staticmethod
    def _atomic_write(path: Path, content: bytes) -> None:
        """Temporary file plus rename, following the released `LocalSrtFileWriter` idiom."""

        handle = tempfile.NamedTemporaryFile(
            mode="wb", dir=str(path.parent), delete=False, prefix=".tmp-"
        )
        try:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
            handle.close()
            os.replace(handle.name, path)
        except OSError:
            try:
                handle.close()
            except OSError:
                pass
            Path(handle.name).unlink(missing_ok=True)
            raise


__all__ = ["LocalAsrCheckpointFileStore", "default_checkpoint_root"]
