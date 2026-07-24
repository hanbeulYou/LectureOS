"""First concrete Edit Export serializer — LectureOS Edit Export JSON v1 (044 §22).

A pure, deterministic projection of one :class:`EditExportArtifact` (044 §21) into the first concrete external
format: LectureOS-native JSON (`lectureos-edit-export-json`, version `v1`). It reads the Artifact without
mutation, preserves every entry in canonical member order, and represents the complete approved edit meaning —
per member the approved Source Timeline range, approved Candidate Type/label, approved rationale, approving
decision kind, and human actor — with no silent omission, truncation, normalization, reinterpretation, or
invention.

Determinism: identical Product meaning always yields byte-identical text — a fixed field order, no
wall-clock/locale/randomness, UTF-8 encoding, LF newlines, a single trailing newline, and non-ASCII characters
(e.g. Korean) preserved unescaped. Format-specific Representation Failure is explicit: a value the format cannot
carry faithfully (a non-finite number) raises :class:`EditExportSerializationError` rather than emitting an
invalid or lossy document. The serializer is a non-authoritative projection; it is not persisted and creates no
approved meaning. This is the concrete syntax deferred by §21 D-14/B-4, added additively without changing the
Artifact's meaning.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from .edit_export_artifact import EditExportArtifact

EDIT_EXPORT_JSON_FORMAT = "lectureos-edit-export-json"
EDIT_EXPORT_JSON_VERSION = "v1"
EDIT_EXPORT_JSON_MEDIA_TYPE = "application/vnd.lectureos.edit-export+json"
EDIT_EXPORT_JSON_ENCODING = "utf-8"


class EditExportSerializationError(ValueError):
    """Approved meaning that cannot be represented faithfully in the selected concrete format."""


@dataclass(frozen=True, slots=True)
class SerializedEditExport:
    """A deterministic, format-identified serialized projection of one Edit Export Artifact (not persisted)."""

    format: str
    version: str
    media_type: str
    encoding: str
    payload: str
    byte_length: int

    def __post_init__(self) -> None:
        if self.format != EDIT_EXPORT_JSON_FORMAT:
            raise ValueError("serialized edit export format is invalid")
        if self.version != EDIT_EXPORT_JSON_VERSION:
            raise ValueError("serialized edit export version is invalid")
        if self.encoding != EDIT_EXPORT_JSON_ENCODING:
            raise ValueError("serialized edit export encoding must be utf-8")
        if self.byte_length != len(self.payload.encode(EDIT_EXPORT_JSON_ENCODING)):
            raise ValueError("serialized edit export byte length is inconsistent")


def _document(artifact: EditExportArtifact) -> dict:
    # Fixed field order — Python preserves dict insertion order, so this is deterministic.
    return {
        "format": EDIT_EXPORT_JSON_FORMAT,
        "version": EDIT_EXPORT_JSON_VERSION,
        "artifact_id": artifact.identity.value,
        "source_assembly_id": artifact.source_assembly_id.value,
        "source_media_id": artifact.source_media_id.value,
        "source_timeline_id": artifact.source_timeline_id.value,
        "edits": [
            {
                "source_representation_id": entry.source_representation_id.value,
                "decision_kind": entry.decision_kind.value,
                "approved_range_start": entry.approved_range_start,
                "approved_range_end": entry.approved_range_end,
                "approved_candidate_type": entry.approved_candidate_type,
                "approved_rationale": entry.approved_rationale,
                "actor": entry.actor.value,
            }
            for entry in artifact.entries
        ],
    }


def serialize_edit_export_json(artifact: EditExportArtifact) -> SerializedEditExport:
    """Deterministically project one Edit Export Artifact into LectureOS Edit Export JSON v1."""

    try:
        # allow_nan=False rejects non-finite numbers (invalid JSON) as an explicit representation failure;
        # ensure_ascii=False preserves non-ASCII (e.g. Korean) faithfully.
        payload = (
            json.dumps(
                _document(artifact),
                ensure_ascii=False,
                allow_nan=False,
                indent=2,
                separators=(",", ": "),
            )
            + "\n"
        )
    except ValueError as error:
        raise EditExportSerializationError(
            f"approved edit meaning cannot be represented as {EDIT_EXPORT_JSON_FORMAT}: {error}"
        ) from error
    return SerializedEditExport(
        format=EDIT_EXPORT_JSON_FORMAT,
        version=EDIT_EXPORT_JSON_VERSION,
        media_type=EDIT_EXPORT_JSON_MEDIA_TYPE,
        encoding=EDIT_EXPORT_JSON_ENCODING,
        payload=payload,
        byte_length=len(payload.encode(EDIT_EXPORT_JSON_ENCODING)),
    )


__all__ = [
    "EDIT_EXPORT_JSON_ENCODING",
    "EDIT_EXPORT_JSON_FORMAT",
    "EDIT_EXPORT_JSON_MEDIA_TYPE",
    "EDIT_EXPORT_JSON_VERSION",
    "EditExportSerializationError",
    "SerializedEditExport",
    "serialize_edit_export_json",
]
