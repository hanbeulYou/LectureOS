"""Edit Export serialization — effective-transcript generation (044 §25, GOAL-032).

Implements S-2…S-5 and S-8(b) of `patches/PATCH-0037`: the one concrete format for this generation's
`§24` Artifact, and nothing downstream of it.

**One format, separately identified (S-2, S-3).** LectureOS-native JSON, and only that. The identity
is deliberately **not** the legacy `lectureos-edit-export-json` `v1`: this generation's payload shape
necessarily differs — `§23` EA-2 did not reproduce `§19`'s atom, so the per-edit member reference is
an `ApprovedEditDecision`, and `§24` AR-6 keeps Source Media out of the Artifact — and one identifier
and version must never denote two shapes. A version bump was rejected because both generations remain
valid and neither supersedes the other; the released idiom for that situation is a separately
identified representation.

**Complete relative to the Artifact (S-4).** Every canonical field of the `§24` Artifact appears; no
approved field is omitted, truncated, normalized away, reinterpreted, or invented. A top-level Source
Media identity is absent because the Artifact does not carry it, and `§22` does not require the field
in the document: C-2's completeness is Artifact-relative and its prohibition covers *approved* fields,
while Source Media identity is provenance. It stays reachable through the anchor chain from the
source assembly identity this document does carry.

**Deterministic (S-5).** Fixed field order, the Artifact's canonical entry order, UTF-8, LF, exactly
one trailing newline, non-ASCII preserved unescaped. No wall clock, randomness, UUID, filesystem
path, execution identifier, provider identifier, mutable currentness, ambient locale, or
process-dependent ordering is read.

**Non-authoritative (S-11).** Serializing approves nothing and changes nothing upstream.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from .lecture_edit_export_artifact import LectureEditExportArtifact

LECTURE_EDIT_EXPORT_JSON_FORMAT = "lectureos-lecture-edit-export-json"
LECTURE_EDIT_EXPORT_JSON_VERSION = "v1"
LECTURE_EDIT_EXPORT_JSON_MEDIA_TYPE = (
    "application/vnd.lectureos.lecture-edit-export+json"
)
LECTURE_EDIT_EXPORT_JSON_ENCODING = "utf-8"


class LectureEditExportSerializationError(ValueError):
    """S-8(b): the Artifact's canonical meaning cannot be represented in this concrete format.

    Distinct from an Artifact **derivation** failure (`§24` AR-10 — the Assembly's approved meaning
    could not be presented at all) and from a **materialization** failure (bytes were produced but no
    safe file resulted). Approved meaning is never silently dropped, and no fallback format exists.
    """


@dataclass(frozen=True, slots=True)
class SerializedLectureEditExport:
    """A deterministic, format-identified projection of one `§24` Artifact. Not persisted (S-10)."""

    format: str
    version: str
    media_type: str
    encoding: str
    payload: str
    byte_length: int

    def __post_init__(self) -> None:
        if self.format != LECTURE_EDIT_EXPORT_JSON_FORMAT:
            raise LectureEditExportSerializationError(
                "serialized lecture edit export format is invalid"
            )
        if self.version != LECTURE_EDIT_EXPORT_JSON_VERSION:
            raise LectureEditExportSerializationError(
                "serialized lecture edit export version is invalid"
            )
        if self.media_type != LECTURE_EDIT_EXPORT_JSON_MEDIA_TYPE:
            raise LectureEditExportSerializationError(
                "serialized lecture edit export media type is invalid"
            )
        if self.encoding != LECTURE_EDIT_EXPORT_JSON_ENCODING:
            raise LectureEditExportSerializationError(
                "serialized lecture edit export encoding must be utf-8"
            )
        if self.byte_length != len(
            self.payload.encode(LECTURE_EDIT_EXPORT_JSON_ENCODING)
        ):
            raise LectureEditExportSerializationError(
                "serialized lecture edit export byte length is inconsistent"
            )

    @property
    def content(self) -> bytes:
        return self.payload.encode(LECTURE_EDIT_EXPORT_JSON_ENCODING)


def _document(artifact: LectureEditExportArtifact) -> dict:
    """S-4's field mapping. Field order is fixed; Python preserves dict insertion order.

    No top-level `source_media_id`: this generation's Artifact does not carry it (`§24` AR-6), and
    resolving it here would push a repository query into a layer `§22` C-10 defines as a
    non-authoritative projection. Per edit, `source_approved_edit_decision_id` occupies the position
    the legacy document gave to `source_representation_id`, because that atom does not exist here.
    """

    return {
        "format": LECTURE_EDIT_EXPORT_JSON_FORMAT,
        "version": LECTURE_EDIT_EXPORT_JSON_VERSION,
        "artifact_id": artifact.identity.value,
        "source_assembly_id": artifact.source_assembly_id.value,
        "source_timeline_id": artifact.source_timeline_id.value,
        "edits": [
            {
                "source_approved_edit_decision_id": (
                    entry.source_approved_edit_decision_id.value
                ),
                "decision_kind": entry.decision_kind.value,
                "approved_range_start": entry.approved_range_start,
                "approved_range_end": entry.approved_range_end,
                "approved_label": entry.approved_label,
                "approved_rationale": entry.approved_rationale,
                "actor": entry.actor.value,
            }
            # The Artifact's canonical entry order, preserved. It is presentation only — never an
            # execution, edit-application, output-timeline, overlap, or authority order (S-5).
            for entry in artifact.entries
        ],
    }


def serialize_lecture_edit_export_json(
    artifact: LectureEditExportArtifact,
) -> SerializedLectureEditExport:
    """Project one `§24` Artifact into LectureOS Lecture Edit Export JSON v1 (S-2…S-5)."""

    try:
        payload = (
            json.dumps(
                _document(artifact),
                # ensure_ascii=False preserves non-ASCII (e.g. Korean) faithfully (S-5);
                # allow_nan=False turns a non-finite number — which JSON cannot express — into an
                # explicit serialization failure rather than invalid output (S-8(b)).
                ensure_ascii=False,
                allow_nan=False,
                indent=2,
                separators=(",", ": "),
            )
            + "\n"
        )
    except ValueError as error:
        raise LectureEditExportSerializationError(
            "approved edit meaning cannot be represented as "
            f"{LECTURE_EDIT_EXPORT_JSON_FORMAT}: {error}; the approved sources are unchanged"
        ) from error
    return SerializedLectureEditExport(
        format=LECTURE_EDIT_EXPORT_JSON_FORMAT,
        version=LECTURE_EDIT_EXPORT_JSON_VERSION,
        media_type=LECTURE_EDIT_EXPORT_JSON_MEDIA_TYPE,
        encoding=LECTURE_EDIT_EXPORT_JSON_ENCODING,
        payload=payload,
        byte_length=len(payload.encode(LECTURE_EDIT_EXPORT_JSON_ENCODING)),
    )


__all__ = [
    "LECTURE_EDIT_EXPORT_JSON_ENCODING",
    "LECTURE_EDIT_EXPORT_JSON_FORMAT",
    "LECTURE_EDIT_EXPORT_JSON_MEDIA_TYPE",
    "LECTURE_EDIT_EXPORT_JSON_VERSION",
    "LectureEditExportSerializationError",
    "SerializedLectureEditExport",
    "serialize_lecture_edit_export_json",
]
