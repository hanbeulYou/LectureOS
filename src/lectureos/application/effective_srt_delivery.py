"""Explicit Delivery of Effective Subtitle Materializations (GOAL-019).

The outbound boundary of the effective-transcript subtitle contract generation: an explicit
request records that one exact successful physical Materialization's bytes were copied to one
exact destination beneath an approved Delivery Root, through one delivery mechanism
(``local_copy``), with one honest terminal outcome. The released record-first discipline
(044 §17 / PATCH-0007, reused by GOAL-018) applies truthfully: the immutable **intent** is
durable before any destination write; the immutable terminal **outcome** (DELIVERED | FAILED)
is appended after; state is always derived, never stored.

**Artifact ≠ Materialization ≠ Delivery ≠ Publication.** Delivery never regenerates SRT content —
the delivered bytes are always the source Materialization's exact physical bytes, verified against
the Artifact's content fingerprint before the intent and re-verified at the destination before
DELIVERED is recorded. Delivery success never implies publication, a URL, public availability, or
recipient acknowledgement — none of those exist in this contract. Destination paths never affect
Artifact or Materialization identity; a later deleted destination file never mutates any record.
Source-side defects (missing, tampered, unsafe) block **before** any intent is persisted;
destination-side defects after the durable intent are honest FAILED outcomes with stable
categories. A dangling PENDING intent is closed only by explicit reconciliation, which inspects
the destination and appends exactly one truthful terminal outcome — it never writes.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from .identities import (
    EffectiveSrtDeliveryId,
    EffectiveSrtMaterializationId,
    EffectiveSubtitleSrtArtifactId,
)
from .effective_srt_materialization import (
    EffectiveSrtMaterialization,
    MaterializationState,
    require_canonical_materialization_id,
)
from .effective_subtitle_srt_artifact import ArtifactCurrentness
from .subtitle_srt_materialization import (
    MaterializationCollisionError,
    MaterializationContainmentError,
    MaterializationWriteError,
)
from lectureos.persistence.errors import PersistenceIdentityCollisionError

EFFECTIVE_SRT_DELIVERY_IDENTITY_PREFIX = "subtitle-effective-srt-delivery"

DELIVERY_CONTRACT_KIND = "subtitle_effective_srt_delivery"
DELIVERY_CONTRACT_VERSION = 1
DELIVERY_KIND = "local_copy"


class EffectiveSrtDeliveryError(ValueError):
    """A delivery request that cannot proceed (malformed, unknown, ineligible, or unsafe input)."""


class EffectiveSrtDeliveryConflictError(EffectiveSrtDeliveryError):
    """A competing divergent delivery request occupies this attempt slot; re-evaluate explicitly."""


class DeliveryState(str, Enum):
    PENDING = "pending"        # intent recorded, no terminal outcome (derived)
    DELIVERED = "delivered"
    FAILED = "failed"


class DeliveryRequestKind(str, Enum):
    CREATED = "created"        # a new delivery attempt was recorded
    REUSED = "reused"          # an existing attempt already answers this exact request


class DeliveryBlockingReason(str, Enum):
    MATERIALIZATION_NOT_FOUND = "materialization_not_found"
    MATERIALIZATION_NOT_MATERIALIZED = "materialization_not_materialized"
    SOURCE_FILE_MISSING = "source_file_missing"
    SOURCE_FILE_MISMATCH = "source_file_mismatch"
    SOURCE_PATH_UNSAFE = "source_path_unsafe"
    ARTIFACT_LINEAGE_INVALID = "artifact_lineage_invalid"
    UNSUPPORTED_DELIVERY_KIND = "unsupported_delivery_kind"


class DeliveryFailureCategory(str, Enum):
    DESTINATION_EXISTS_DIFFERENT = "destination_exists_different"
    DESTINATION_UNSAFE = "destination_unsafe"
    DESTINATION_MISSING = "destination_missing"
    WRITE_FAILED = "write_failed"
    VERIFICATION_FAILED = "verification_failed"


def _is_safe_relative_location(location: str) -> bool:
    if not location.strip():
        return False
    if location.startswith("/"):
        return False
    return ".." not in location.split("/")


def default_delivery_location(artifact_id: EffectiveSubtitleSrtArtifactId) -> str:
    """Deterministic default destination policy — convenience provenance, never identity.

    The identifier contains ``:`` (legal on POSIX filesystems); callers targeting filesystems
    without it must pass an explicit destination location.
    """

    return f"{artifact_id.value}.srt"


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def derive_delivery_identity(
    materialization_id: EffectiveSrtMaterializationId,
    artifact_id: EffectiveSubtitleSrtArtifactId,
    relative_location: str,
    expected_payload_fingerprint: str,
    sequence: int,
    overwrite: bool,
) -> EffectiveSrtDeliveryId:
    """Deterministic identity of one delivery attempt.

    Never a destination path alone, never the materialization alone, never a timestamp, never an
    absolute Delivery Root — one immutable record per explicit attempt against one target.
    """

    digest = hashlib.sha256(
        _canonical_json(
            {
                "contract": DELIVERY_CONTRACT_KIND,
                "contract_version": DELIVERY_CONTRACT_VERSION,
                "materialization": materialization_id.value,
                "artifact": artifact_id.value,
                "delivery_kind": DELIVERY_KIND,
                "relative_location": relative_location,
                "expected_payload_fingerprint": expected_payload_fingerprint,
                "sequence": sequence,
                "overwrite": overwrite,
            }
        ).encode("utf-8")
    ).hexdigest()
    return EffectiveSrtDeliveryId(f"{EFFECTIVE_SRT_DELIVERY_IDENTITY_PREFIX}:{digest}")


@dataclass(frozen=True, slots=True)
class EffectiveSrtDelivery:
    """Immutable delivery intent: the committed act of copying one materialized file out."""

    identity: EffectiveSrtDeliveryId
    materialization_id: EffectiveSrtMaterializationId
    artifact_id: EffectiveSubtitleSrtArtifactId
    delivery_kind: str
    delivery_contract_version: int
    relative_location: str
    expected_payload_fingerprint: str
    sequence: int
    overwrite: bool
    previous_delivery_id: EffectiveSrtDeliveryId | None = None

    def __post_init__(self) -> None:
        if self.delivery_kind != DELIVERY_KIND:
            raise ValueError("unsupported delivery kind")
        if self.delivery_contract_version != DELIVERY_CONTRACT_VERSION:
            raise ValueError("unsupported delivery contract version")
        if not _is_safe_relative_location(self.relative_location):
            raise ValueError(
                "delivery relative location must be a non-empty, contained relative path"
            )
        if len(self.expected_payload_fingerprint) != 64:
            raise ValueError(
                "delivery expected payload fingerprint must be a 64-hex SHA-256 digest"
            )
        if self.sequence < 0:
            raise ValueError("delivery sequence must not be negative")
        if (self.sequence == 0) != (self.previous_delivery_id is None):
            raise ValueError(
                "the first delivery attempt (sequence 0) has no previous; later ones require one"
            )
        if self.previous_delivery_id == self.identity:
            raise ValueError("a delivery attempt cannot supersede itself")
        if self.identity != derive_delivery_identity(
            self.materialization_id,
            self.artifact_id,
            self.relative_location,
            self.expected_payload_fingerprint,
            self.sequence,
            self.overwrite,
        ):
            raise ValueError(
                "delivery identity must derive from its materialization, artifact, destination, "
                "fingerprint, sequence, and overwrite policy"
            )


@dataclass(frozen=True, slots=True)
class EffectiveSrtDeliveryOutcome:
    """Immutable terminal outcome of one delivery attempt (DELIVERED or FAILED)."""

    delivery_id: EffectiveSrtDeliveryId
    state: DeliveryState
    delivered_payload_fingerprint: str | None = None
    byte_length: int | None = None
    failure_category: DeliveryFailureCategory | None = None
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        if self.state is DeliveryState.DELIVERED:
            if (
                self.delivered_payload_fingerprint is None
                or len(self.delivered_payload_fingerprint) != 64
            ):
                raise ValueError(
                    "delivered outcome requires a 64-hex delivered payload fingerprint"
                )
            if self.byte_length is None or self.byte_length < 0:
                raise ValueError("delivered outcome requires a non-negative byte length")
            if self.failure_category is not None or self.failure_reason is not None:
                raise ValueError("delivered outcome must not carry failure data")
        elif self.state is DeliveryState.FAILED:
            if self.failure_category is None:
                raise ValueError("failed outcome requires a stable failure category")
            if self.failure_reason is None or not self.failure_reason.strip():
                raise ValueError("failed outcome requires a non-empty failure reason")
            if self.delivered_payload_fingerprint is not None or self.byte_length is not None:
                raise ValueError("failed outcome must not carry delivered payload data")
        else:
            raise ValueError("delivery outcome state must be terminal")


@dataclass(frozen=True, slots=True)
class DeliveryRecord:
    """One delivery attempt with its derived state: intent + optional terminal outcome."""

    delivery: EffectiveSrtDelivery
    outcome: EffectiveSrtDeliveryOutcome | None
    kind: DeliveryRequestKind

    @property
    def state(self) -> DeliveryState:
        if self.outcome is None:
            return DeliveryState.PENDING
        return self.outcome.state


@dataclass(frozen=True, slots=True)
class DeliveryEligibility:
    """Derived, never persisted: may this exact materialization be delivered right now?"""

    materialization_id: str
    eligible: bool
    materialization_state: MaterializationState | None
    blocking_reason: DeliveryBlockingReason | None
    delivery_kind: str = DELIVERY_KIND
    delivery_contract_version: int = DELIVERY_CONTRACT_VERSION


@dataclass(frozen=True, slots=True)
class DeliveryStatus:
    """Derived delivery state and separate, purely observational filesystem agreement."""

    delivery_state: DeliveryState
    source_file_agreement: str        # matches | differs | missing | unsafe
    destination_file_agreement: str   # matches | differs | missing | unsafe
    artifact_currentness: ArtifactCurrentness
    materialization_state: MaterializationState


class DeliveryFileReader(Protocol):
    """A contained reader over one approved root (the GOAL-018 hardened writer's read side)."""

    def read(self, *, relative_location: str) -> bytes | None: ...

    def path_of(self, *, relative_location: str) -> str: ...


class DeliveryFileWriter(Protocol):
    """The hardened destination writer port: contained, atomic, no-overwrite-of-different-bytes;
    ``replace`` only for an explicit overwrite request."""

    def write(self, *, relative_location: str, content: bytes) -> int: ...

    def replace(self, *, relative_location: str, content: bytes) -> int: ...

    def read(self, *, relative_location: str) -> bytes | None: ...

    def path_of(self, *, relative_location: str) -> str: ...


class DeliveryArtifactLookup(Protocol):
    def get(self, artifact_id: str): ...

    def currentness(self, artifact) -> ArtifactCurrentness: ...


class DeliveryMaterializationQuery(Protocol):
    def get(self, identity): ...

    def get_outcome(self, identity): ...


class DeliveryQuery(Protocol):
    def get(self, identity): ...

    def get_outcome(self, identity): ...

    def get_latest(self, materialization_id, relative_location): ...

    def list_for_materialization(self, materialization_id) -> tuple: ...


class AtomicDeliveryPersistence(Protocol):
    def persist_delivery_intent(self, *, delivery: EffectiveSrtDelivery) -> None: ...

    def persist_delivery_outcome(self, *, outcome: EffectiveSrtDeliveryOutcome) -> None: ...


class EffectiveSrtDeliveryService:
    """The single canonical delivery path of the effective generation (GOAL-019)."""

    def __init__(
        self,
        artifact_lookup: DeliveryArtifactLookup,
        materialization_query: DeliveryMaterializationQuery,
        delivery_query: DeliveryQuery,
        persistence: AtomicDeliveryPersistence,
        source_reader: DeliveryFileReader,
        destination_writer: DeliveryFileWriter,
    ) -> None:
        self._artifacts = artifact_lookup
        self._materializations = materialization_query
        self._deliveries = delivery_query
        self._persistence = persistence
        self._source = source_reader
        self._destination = destination_writer

    # -- derived eligibility (never persisted) --------------------------------------------------------

    def delivery_eligibility(
        self, materialization_id: str, *, delivery_kind: str = DELIVERY_KIND
    ) -> DeliveryEligibility:
        def _blocked(
            reason: DeliveryBlockingReason,
            state: MaterializationState | None = None,
        ) -> DeliveryEligibility:
            return DeliveryEligibility(
                materialization_id=materialization_id,
                eligible=False,
                materialization_state=state,
                blocking_reason=reason,
            )

        if delivery_kind != DELIVERY_KIND:
            return _blocked(DeliveryBlockingReason.UNSUPPORTED_DELIVERY_KIND)
        try:
            identity = require_canonical_materialization_id(materialization_id)
        except ValueError as error:
            raise EffectiveSrtDeliveryError(str(error)) from error
        materialization = self._materializations.get(identity)
        if materialization is None:
            return _blocked(DeliveryBlockingReason.MATERIALIZATION_NOT_FOUND)
        state = self._materialization_state(materialization)
        if state is not MaterializationState.MATERIALIZED:
            return _blocked(
                DeliveryBlockingReason.MATERIALIZATION_NOT_MATERIALIZED, state
            )
        artifact = self._artifacts.get(materialization.artifact_id.value)
        if (
            artifact is None
            or materialization.payload_fingerprint != artifact.content_fingerprint
        ):
            return _blocked(DeliveryBlockingReason.ARTIFACT_LINEAGE_INVALID, state)
        try:
            source_bytes = self._source.read(
                relative_location=materialization.relative_location
            )
        except MaterializationContainmentError:
            return _blocked(DeliveryBlockingReason.SOURCE_PATH_UNSAFE, state)
        if source_bytes is None:
            return _blocked(DeliveryBlockingReason.SOURCE_FILE_MISSING, state)
        if hashlib.sha256(source_bytes).hexdigest() != artifact.content_fingerprint:
            return _blocked(DeliveryBlockingReason.SOURCE_FILE_MISMATCH, state)
        return DeliveryEligibility(
            materialization_id=materialization_id,
            eligible=True,
            materialization_state=state,
            blocking_reason=None,
        )

    # -- explicit delivery command --------------------------------------------------------------------

    def deliver(
        self,
        *,
        materialization_id: str,
        relative_location: str | None = None,
        overwrite: bool = False,
        delivery_kind: str = DELIVERY_KIND,
    ) -> DeliveryRecord:
        eligibility = self.delivery_eligibility(
            materialization_id, delivery_kind=delivery_kind
        )
        if not eligibility.eligible:
            raise EffectiveSrtDeliveryError(
                "materialization is not deliverable: "
                f"{eligibility.blocking_reason.value}"
            )
        materialization = self._materializations.get(
            require_canonical_materialization_id(materialization_id)
        )
        artifact = self._artifacts.get(materialization.artifact_id.value)
        content = self._source.read(
            relative_location=materialization.relative_location
        )
        # The bytes actually copied are re-verified here, not only during eligibility, so a
        # source file swapped between the two reads can never be recorded or delivered under
        # the artifact's fingerprint (pre-intent: nothing is persisted).
        if (
            content is None
            or hashlib.sha256(content).hexdigest() != artifact.content_fingerprint
        ):
            raise EffectiveSrtDeliveryError(
                "materialization is not deliverable: the source file changed during the "
                "request and no longer matches the artifact fingerprint"
            )
        location = (
            relative_location
            if relative_location is not None
            else default_delivery_location(artifact.identity)
        )
        if not _is_safe_relative_location(location):
            raise EffectiveSrtDeliveryError(
                "delivery relative location must be a non-empty, contained relative path"
            )
        try:
            destination_path = self._destination.path_of(relative_location=location)
        except MaterializationContainmentError as error:
            raise EffectiveSrtDeliveryError(
                f"delivery destination is not contained: {error}"
            ) from error
        if destination_path == self._source.path_of(
            relative_location=materialization.relative_location
        ):
            raise EffectiveSrtDeliveryError(
                "delivery destination aliases the materialized source file; refusing"
            )

        latest = self._deliveries.get_latest(materialization.identity, location)
        if latest is not None:
            latest_outcome = self._deliveries.get_outcome(latest.identity)
            if latest_outcome is None:
                # A dangling PENDING intent stays open for explicit reconciliation or an
                # explicit completion; this identical explicit request completes it rather
                # than duplicating the attempt (the released record-first rule). The stored
                # intent's overwrite policy governs the completion — the caller's flag applies
                # only to a new attempt it creates itself.
                return DeliveryRecord(
                    latest,
                    self._finalize(latest, content),
                    DeliveryRequestKind.CREATED,
                )
            if (
                latest_outcome.state is DeliveryState.DELIVERED
                and latest.expected_payload_fingerprint == artifact.content_fingerprint
                and self._destination.read(relative_location=location) == content
            ):
                # Exact replay: the destination already holds the exact bytes — reuse,
                # never rewrite, never append.
                return DeliveryRecord(latest, latest_outcome, DeliveryRequestKind.REUSED)

        sequence = 0 if latest is None else latest.sequence + 1
        delivery = EffectiveSrtDelivery(
            identity=derive_delivery_identity(
                materialization.identity,
                artifact.identity,
                location,
                artifact.content_fingerprint,
                sequence,
                overwrite,
            ),
            materialization_id=materialization.identity,
            artifact_id=artifact.identity,
            delivery_kind=DELIVERY_KIND,
            delivery_contract_version=DELIVERY_CONTRACT_VERSION,
            relative_location=location,
            expected_payload_fingerprint=artifact.content_fingerprint,
            sequence=sequence,
            overwrite=overwrite,
            previous_delivery_id=latest.identity if latest is not None else None,
        )
        # Record-first: the PENDING attempt is durable before any destination write.
        try:
            self._persistence.persist_delivery_intent(delivery=delivery)
        except PersistenceIdentityCollisionError as error:
            return self._converge_after_collision(delivery, error)
        return DeliveryRecord(
            delivery, self._finalize(delivery, content), DeliveryRequestKind.CREATED
        )

    def _converge_after_collision(
        self, delivery: EffectiveSrtDelivery, error: Exception
    ) -> DeliveryRecord:
        """A near-concurrent request won the durable intent slot first.

        Identical payload (same identity) → converge on the canonical record without a second
        destination write: report its terminal outcome, or its honest PENDING state while the
        winner is still mid-flight. A divergent payload occupying the same sequence slot is an
        explicit conflict — never silent loss, never last-write-wins.
        """

        canonical = self._deliveries.get(delivery.identity)
        if canonical is None or canonical != delivery:
            raise EffectiveSrtDeliveryConflictError(
                "a competing divergent delivery request occupies this attempt slot; "
                "re-evaluate and retry explicitly"
            ) from error
        return DeliveryRecord(
            canonical,
            self._deliveries.get_outcome(canonical.identity),
            DeliveryRequestKind.REUSED,
        )

    def _finalize(
        self, delivery: EffectiveSrtDelivery, content: bytes
    ) -> EffectiveSrtDeliveryOutcome:
        try:
            if delivery.overwrite:
                self._destination.replace(
                    relative_location=delivery.relative_location, content=content
                )
            else:
                self._destination.write(
                    relative_location=delivery.relative_location, content=content
                )
        except MaterializationCollisionError as error:
            return self._persist_failure(
                delivery, DeliveryFailureCategory.DESTINATION_EXISTS_DIFFERENT, error
            )
        except MaterializationContainmentError as error:
            return self._persist_failure(
                delivery, DeliveryFailureCategory.DESTINATION_UNSAFE, error
            )
        except MaterializationWriteError as error:
            return self._persist_failure(
                delivery, DeliveryFailureCategory.WRITE_FAILED, error
            )
        # Post-write verification: DELIVERED is recorded only for verified destination bytes.
        try:
            observed = self._destination.read(
                relative_location=delivery.relative_location
            )
        except (MaterializationContainmentError, MaterializationWriteError) as error:
            return self._persist_failure(
                delivery, DeliveryFailureCategory.VERIFICATION_FAILED, error
            )
        if observed != content:
            return self._persist_failure(
                delivery,
                DeliveryFailureCategory.VERIFICATION_FAILED,
                "destination bytes do not verify against the expected payload",
            )
        outcome = EffectiveSrtDeliveryOutcome(
            delivery_id=delivery.identity,
            state=DeliveryState.DELIVERED,
            delivered_payload_fingerprint=hashlib.sha256(observed).hexdigest(),
            byte_length=len(observed),
        )
        self._persistence.persist_delivery_outcome(outcome=outcome)
        return outcome

    def _persist_failure(
        self,
        delivery: EffectiveSrtDelivery,
        category: DeliveryFailureCategory,
        detail: object,
    ) -> EffectiveSrtDeliveryOutcome:
        outcome = EffectiveSrtDeliveryOutcome(
            delivery_id=delivery.identity,
            state=DeliveryState.FAILED,
            failure_category=category,
            failure_reason=str(detail),
        )
        self._persistence.persist_delivery_outcome(outcome=outcome)
        return outcome

    # -- explicit reconciliation of a dangling PENDING intent -----------------------------------------

    def reconcile(self, delivery_id: str) -> DeliveryRecord:
        """Close one dangling PENDING intent from destination observation — never write.

        Matching destination bytes → DELIVERED; missing → FAILED (destination_missing); different
        bytes → FAILED (verification_failed). A terminal delivery reconciles idempotently to its
        existing outcome; it can never receive another one.
        """

        delivery = self._require_delivery(delivery_id)
        existing = self._deliveries.get_outcome(delivery.identity)
        if existing is not None:
            return DeliveryRecord(delivery, existing, DeliveryRequestKind.REUSED)
        try:
            observed = self._destination.read(
                relative_location=delivery.relative_location
            )
        except (MaterializationContainmentError, MaterializationWriteError) as error:
            return DeliveryRecord(
                delivery,
                self._persist_failure(
                    delivery, DeliveryFailureCategory.DESTINATION_UNSAFE, error
                ),
                DeliveryRequestKind.CREATED,
            )
        if observed is None:
            outcome = self._persist_failure(
                delivery,
                DeliveryFailureCategory.DESTINATION_MISSING,
                "no destination file exists for this dangling delivery intent",
            )
        elif (
            hashlib.sha256(observed).hexdigest()
            == delivery.expected_payload_fingerprint
        ):
            outcome = EffectiveSrtDeliveryOutcome(
                delivery_id=delivery.identity,
                state=DeliveryState.DELIVERED,
                delivered_payload_fingerprint=delivery.expected_payload_fingerprint,
                byte_length=len(observed),
            )
            self._persistence.persist_delivery_outcome(outcome=outcome)
        else:
            outcome = self._persist_failure(
                delivery,
                DeliveryFailureCategory.VERIFICATION_FAILED,
                "destination bytes do not verify against the expected payload",
            )
        return DeliveryRecord(delivery, outcome, DeliveryRequestKind.CREATED)

    # -- queries (derived; never mutate history) ------------------------------------------------------

    def get(self, delivery_id: str) -> EffectiveSrtDelivery | None:
        return self._deliveries.get(require_canonical_delivery_id(delivery_id))

    def state(self, delivery: EffectiveSrtDelivery) -> DeliveryState:
        outcome = self._deliveries.get_outcome(delivery.identity)
        if outcome is None:
            return DeliveryState.PENDING
        return outcome.state

    def outcome(
        self, delivery: EffectiveSrtDelivery
    ) -> EffectiveSrtDeliveryOutcome | None:
        return self._deliveries.get_outcome(delivery.identity)

    def status(self, delivery: EffectiveSrtDelivery) -> DeliveryStatus:
        """Derived state plus purely observational filesystem agreement — kept separate.

        A DELIVERED record whose destination file was later deleted remains a truthful
        historical delivery; observation never rewrites history.
        """

        materialization = self._materializations.get(delivery.materialization_id)
        if materialization is None:
            raise EffectiveSrtDeliveryError(
                "delivery references an unknown materialization (repository integrity failure)"
            )
        artifact = self._artifacts.get(delivery.artifact_id.value)
        if artifact is None:
            raise EffectiveSrtDeliveryError(
                "delivery references an unknown artifact (repository integrity failure)"
            )
        expected = artifact.srt_content.encode("utf-8")
        return DeliveryStatus(
            delivery_state=self.state(delivery),
            source_file_agreement=self._agreement(
                self._source, materialization.relative_location, expected
            ),
            destination_file_agreement=self._agreement(
                self._destination, delivery.relative_location, expected
            ),
            artifact_currentness=self._artifacts.currentness(artifact),
            materialization_state=self._materialization_state(materialization),
        )

    def source_path(self, delivery: EffectiveSrtDelivery) -> str:
        materialization = self._materializations.get(delivery.materialization_id)
        if materialization is None:
            raise EffectiveSrtDeliveryError(
                "delivery references an unknown materialization (repository integrity failure)"
            )
        return self._source.path_of(
            relative_location=materialization.relative_location
        )

    def destination_path(self, delivery: EffectiveSrtDelivery) -> str:
        return self._destination.path_of(relative_location=delivery.relative_location)

    def list_for_materialization(
        self, materialization_id: str
    ) -> tuple[EffectiveSrtDelivery, ...]:
        try:
            identity = require_canonical_materialization_id(materialization_id)
        except ValueError as error:
            raise EffectiveSrtDeliveryError(str(error)) from error
        return self._deliveries.list_for_materialization(identity)

    # -- internals ------------------------------------------------------------------------------------

    def _materialization_state(
        self, materialization: EffectiveSrtMaterialization
    ) -> MaterializationState:
        outcome = self._materializations.get_outcome(materialization.identity)
        if outcome is None:
            return MaterializationState.PENDING
        return outcome.state

    def _agreement(
        self, reader: DeliveryFileReader, relative_location: str, expected: bytes
    ) -> str:
        try:
            observed = reader.read(relative_location=relative_location)
        except (MaterializationContainmentError, MaterializationWriteError):
            return "unsafe"
        if observed is None:
            return "missing"
        return "matches" if observed == expected else "differs"

    def _require_delivery(self, delivery_id: str) -> EffectiveSrtDelivery:
        delivery = self.get(delivery_id)
        if delivery is None:
            raise EffectiveSrtDeliveryError(
                "unknown effective SRT delivery: reconciliation and queries require one "
                "exact existing delivery intent"
            )
        return delivery


def require_canonical_delivery_id(value: str) -> EffectiveSrtDeliveryId:
    prefix = EFFECTIVE_SRT_DELIVERY_IDENTITY_PREFIX + ":"
    if (
        not isinstance(value, str)
        or not value.startswith(prefix)
        or len(value) != len(prefix) + 64
    ):
        raise EffectiveSrtDeliveryError(
            "effective SRT delivery identity is malformed "
            "(expected 'subtitle-effective-srt-delivery:<64 hex digest>')"
        )
    return EffectiveSrtDeliveryId(value)


__all__ = [
    "DELIVERY_CONTRACT_KIND",
    "DELIVERY_CONTRACT_VERSION",
    "DELIVERY_KIND",
    "EFFECTIVE_SRT_DELIVERY_IDENTITY_PREFIX",
    "AtomicDeliveryPersistence",
    "DeliveryBlockingReason",
    "DeliveryEligibility",
    "DeliveryFailureCategory",
    "DeliveryFileReader",
    "DeliveryFileWriter",
    "DeliveryRecord",
    "DeliveryRequestKind",
    "DeliveryState",
    "DeliveryStatus",
    "EffectiveSrtDelivery",
    "EffectiveSrtDeliveryConflictError",
    "EffectiveSrtDeliveryError",
    "EffectiveSrtDeliveryOutcome",
    "EffectiveSrtDeliveryService",
    "default_delivery_location",
    "derive_delivery_identity",
    "require_canonical_delivery_id",
]
