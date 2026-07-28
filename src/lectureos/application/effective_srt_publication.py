"""Publication and Availability Authority for delivered effective subtitles (GOAL-020).

The explicit publication boundary of the effective-transcript subtitle contract generation:
whether one exact successfully delivered subtitle should be considered published — or withdrawn —
within LectureOS. It combines the released idioms truthfully: the GOAL-009/GOAL-015 Human
Authority pattern (explicit `HumanActorReference`, closed decision vocabulary,
fingerprint-verified provenance, same-state repeated intent reused, converge-on-collision) and
the GOAL-011/GOAL-016 append-only per-scope authority (per-intake ``sequence`` +
``previous_publication_id``; current = highest sequence, derived — never a flag, never a
latest-row heuristic).

**Delivery ≠ Publication ≠ Availability ≠ network access.** A successful Delivery proves that the
expected bytes existed at one verified destination; publication is a separate, explicit Human
Authority declaring that this exact delivered subtitle is the selected published output for its
intake scope. Publication creates no URL, performs no network operation, writes no file, and
implies no recipient acknowledgement. Withdrawal records authority only — it never deletes the
destination file, the Delivery, the Materialization, or the Artifact. Availability is always
derived (never persisted): from the current publication authority, the immutable Delivery record,
and — only when a Delivery Root observer is supplied — the destination file's observed agreement;
a published subtitle whose destination file later disappears keeps its authority history intact
and simply derives an unavailable operational state.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from lectureos.persistence.errors import PersistenceIdentityCollisionError
from lectureos.review.identities import HumanActorReference

from .effective_srt_delivery import (
    DeliveryState,
    EffectiveSrtDelivery,
    require_canonical_delivery_id,
)
from .effective_subtitle_srt_artifact import ArtifactCurrentness
from .identities import (
    EffectiveSrtDeliveryId,
    EffectiveSrtPublicationId,
    EffectiveSubtitleSrtArtifactId,
    TranscriptSourceIntakeId,
)
from .provider_transcript_admission import (
    ProviderTranscriptAdmissionError,
    require_canonical_intake_id,
)
from .subtitle_srt_materialization import (
    MaterializationContainmentError,
    MaterializationWriteError,
)

EFFECTIVE_SRT_PUBLICATION_IDENTITY_PREFIX = "subtitle-effective-srt-publication"

PUBLICATION_CONTRACT_KIND = "effective_srt_publication"
PUBLICATION_CONTRACT_VERSION = 1


class EffectiveSrtPublicationError(ValueError):
    """A publication request that cannot proceed (malformed, unknown, or ineligible input)."""


class DeliveryNotPublishableError(EffectiveSrtPublicationError):
    """The target delivery is not eligible for a new publish command under current evidence."""


class PublicationConflictError(EffectiveSrtPublicationError):
    """The deterministic publication slot maps to a structurally different persisted payload."""


class PublicationKind(str, Enum):
    PUBLISH = "publish"
    WITHDRAW = "withdraw"


class PublicationOutcome(str, Enum):
    RECORDED = "recorded"   # first publication authority for the scope (sequence 0)
    REUSED = "reused"       # the current authority already holds this exact state
    CHANGED = "changed"     # a new authority record superseding the prior state


class PublicationBlockingReason(str, Enum):
    DELIVERY_NOT_FOUND = "delivery_not_found"
    DELIVERY_NOT_DELIVERED = "delivery_not_delivered"
    LINEAGE_INVALID = "lineage_invalid"
    DESTINATION_MISSING = "destination_missing"
    DESTINATION_MISMATCH = "destination_mismatch"


class PublicationAvailability(str, Enum):
    """Derived, never stored. Operational availability is separate from publication authority."""

    NOT_PUBLISHED = "not_published"
    AVAILABLE = "available"
    WITHDRAWN = "withdrawn"
    NOT_OBSERVED = "not_observed"                 # published; no Delivery Root supplied
    DESTINATION_MISSING = "destination_missing"   # published; destination file absent
    DESTINATION_MISMATCH = "destination_mismatch" # published; destination bytes diverged
    UNRESOLVABLE = "unresolvable"                 # published; supporting lineage cannot resolve


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def derive_publication_identity(
    intake_id: TranscriptSourceIntakeId,
    kind: PublicationKind,
    target_delivery_id: EffectiveSrtDeliveryId | None,
    sequence: int,
) -> EffectiveSrtPublicationId:
    """Deterministic publication identity — the released authority idiom over the exact target.

    Scope-, kind-, target-, and sequence-sensitive; the publisher and rationale are provenance,
    verified through the content fingerprint, never identity. No timestamp, filesystem state,
    destination root, or URL participates.
    """

    digest = _sha256(
        _canonical_json(
            {
                "contract_kind": PUBLICATION_CONTRACT_KIND,
                "contract_version": PUBLICATION_CONTRACT_VERSION,
                "intake": intake_id.value,
                "kind": kind.value,
                "target_delivery": (
                    target_delivery_id.value if target_delivery_id is not None else None
                ),
                "sequence": sequence,
            }
        )
    )
    return EffectiveSrtPublicationId(
        f"{EFFECTIVE_SRT_PUBLICATION_IDENTITY_PREFIX}:{digest}"
    )


def _content_fingerprint(
    intake_id: TranscriptSourceIntakeId,
    kind: PublicationKind,
    target_delivery_id: EffectiveSrtDeliveryId | None,
    target_artifact_id: EffectiveSubtitleSrtArtifactId | None,
    sequence: int,
    publisher: HumanActorReference,
    rationale: str | None,
) -> str:
    return _sha256(
        _canonical_json(
            {
                "intake": intake_id.value,
                "kind": kind.value,
                "target_delivery": (
                    target_delivery_id.value if target_delivery_id is not None else None
                ),
                "target_artifact": (
                    target_artifact_id.value if target_artifact_id is not None else None
                ),
                "sequence": sequence,
                "publisher": publisher.value,
                "rationale": rationale,
            }
        )
    )


@dataclass(frozen=True, slots=True)
class EffectiveSrtPublication:
    """Immutable Human Authority fact: publish or withdraw for one intake's delivered subtitle."""

    identity: EffectiveSrtPublicationId
    transcript_source_intake_id: TranscriptSourceIntakeId
    kind: PublicationKind
    publisher: HumanActorReference
    sequence: int
    content_fingerprint: str
    target_delivery_id: EffectiveSrtDeliveryId | None = None
    target_artifact_id: EffectiveSubtitleSrtArtifactId | None = None
    previous_publication_id: EffectiveSrtPublicationId | None = None
    rationale: str | None = None

    def __post_init__(self) -> None:
        if not self.publisher.value.strip():
            raise ValueError("publication publisher must be a non-empty Human actor reference")
        if self.kind is PublicationKind.PUBLISH:
            if self.target_delivery_id is None or self.target_artifact_id is None:
                raise ValueError(
                    "a publish record requires one exact target delivery and artifact lineage"
                )
        elif self.kind is PublicationKind.WITHDRAW:
            if self.target_delivery_id is not None or self.target_artifact_id is not None:
                raise ValueError("a withdraw record must not carry a target")
        else:
            raise ValueError("unsupported publication kind")
        if self.sequence < 0:
            raise ValueError("publication sequence must not be negative")
        if (self.sequence == 0) != (self.previous_publication_id is None):
            raise ValueError(
                "the first publication (sequence 0) has no previous; later ones require one"
            )
        if self.previous_publication_id == self.identity:
            raise ValueError("a publication cannot supersede itself")
        if self.rationale is not None and not self.rationale.strip():
            raise ValueError("publication rationale, when present, must not be blank")
        if self.identity != derive_publication_identity(
            self.transcript_source_intake_id, self.kind, self.target_delivery_id,
            self.sequence,
        ):
            raise ValueError(
                "publication identity must derive from its scope, kind, target, and sequence"
            )
        if self.content_fingerprint != _content_fingerprint(
            self.transcript_source_intake_id, self.kind, self.target_delivery_id,
            self.target_artifact_id, self.sequence, self.publisher, self.rationale,
        ):
            raise ValueError(
                "publication content fingerprint must match its immutable payload"
            )


@dataclass(frozen=True, slots=True)
class PublicationEligibility:
    """Derived, never persisted: may this exact delivery receive a NEW publish command now?"""

    delivery_id: str
    eligible: bool
    delivery_state: DeliveryState | None
    destination_observation: str   # matches | differs | missing | unsafe | not_observed
    transcript_source_intake_id: TranscriptSourceIntakeId | None
    target_artifact_id: EffectiveSubtitleSrtArtifactId | None
    blocking_reason: PublicationBlockingReason | None


@dataclass(frozen=True, slots=True)
class PublicationResult:
    """One publication command outcome: the authority record, the outcome, the superseded record."""

    publication: EffectiveSrtPublication
    outcome: PublicationOutcome
    previous: EffectiveSrtPublication | None


@dataclass(frozen=True, slots=True)
class PublicationStatus:
    """One publication record's derived standing plus separate observational facts."""

    publication: EffectiveSrtPublication
    current: bool
    delivery_state: DeliveryState | None            # None for withdraw records
    destination_observation: str                    # matches|differs|missing|unsafe|not_observed
    artifact_currentness: ArtifactCurrentness | None  # None for withdraw records
    scope_availability: PublicationAvailability


class PublicationDeliveryQuery(Protocol):
    def get(self, identity): ...

    def get_outcome(self, identity): ...


class PublicationMaterializationQuery(Protocol):
    def get(self, identity): ...


class PublicationArtifactLookup(Protocol):
    def get(self, artifact_id: str): ...

    def currentness(self, artifact) -> ArtifactCurrentness: ...


class PublicationQuery(Protocol):
    def get(self, identity): ...

    def get_current(self, intake_id): ...

    def history(self, intake_id) -> tuple: ...


class AtomicPublicationPersistence(Protocol):
    def persist_publication(self, *, publication: EffectiveSrtPublication) -> None: ...


class PublicationDestinationReader(Protocol):
    """Optional, purely observational reader over one approved Delivery Root."""

    def read(self, *, relative_location: str) -> bytes | None: ...


class EffectiveSrtPublicationService:
    """The single canonical publication-authority path of the effective generation (GOAL-020)."""

    def __init__(
        self,
        delivery_query: PublicationDeliveryQuery,
        materialization_query: PublicationMaterializationQuery,
        artifact_lookup: PublicationArtifactLookup,
        publication_query: PublicationQuery,
        persistence: AtomicPublicationPersistence,
        destination_reader: PublicationDestinationReader | None = None,
    ) -> None:
        self._deliveries = delivery_query
        self._materializations = materialization_query
        self._artifacts = artifact_lookup
        self._publications = publication_query
        self._persistence = persistence
        self._destination = destination_reader

    # -- derived eligibility (never persisted) --------------------------------------------------------

    def publication_eligibility(self, delivery_id: str) -> PublicationEligibility:
        def _blocked(
            reason: PublicationBlockingReason,
            state: DeliveryState | None = None,
            observation: str = "not_observed",
        ) -> PublicationEligibility:
            return PublicationEligibility(
                delivery_id=delivery_id,
                eligible=False,
                delivery_state=state,
                destination_observation=observation,
                transcript_source_intake_id=None,
                target_artifact_id=None,
                blocking_reason=reason,
            )

        try:
            identity = require_canonical_delivery_id(delivery_id)
        except ValueError as error:
            raise EffectiveSrtPublicationError(str(error)) from error
        delivery = self._deliveries.get(identity)
        if delivery is None:
            return _blocked(PublicationBlockingReason.DELIVERY_NOT_FOUND)
        outcome = self._deliveries.get_outcome(delivery.identity)
        state = DeliveryState.PENDING if outcome is None else outcome.state
        if state is not DeliveryState.DELIVERED:
            return _blocked(PublicationBlockingReason.DELIVERY_NOT_DELIVERED, state)
        artifact = self._resolve_lineage(delivery, outcome)
        if artifact is None:
            return _blocked(PublicationBlockingReason.LINEAGE_INVALID, state)
        observation = self._observe_destination(delivery, artifact)
        if observation == "missing":
            # Conservative NEW-publish policy: when a Delivery Root is supplied, the
            # destination must currently hold the exact bytes. Historical publications are
            # unaffected — a later-deleted file only changes derived availability.
            return _blocked(
                PublicationBlockingReason.DESTINATION_MISSING, state, observation
            )
        if observation in ("differs", "unsafe"):
            return _blocked(
                PublicationBlockingReason.DESTINATION_MISMATCH, state, observation
            )
        return PublicationEligibility(
            delivery_id=delivery_id,
            eligible=True,
            delivery_state=state,
            destination_observation=observation,
            transcript_source_intake_id=artifact.transcript_source_intake_id,
            target_artifact_id=artifact.identity,
            blocking_reason=None,
        )

    # -- authority commands ---------------------------------------------------------------------------

    def publish(
        self,
        *,
        delivery_id: str,
        publisher: str,
        rationale: str | None = None,
    ) -> PublicationResult:
        actor = self._require_actor(publisher)
        report = self.publication_eligibility(delivery_id)
        if not report.eligible:
            raise DeliveryNotPublishableError(
                "delivery is not eligible for a new publish command: "
                f"{report.blocking_reason.value}"
            )
        delivery = self._deliveries.get(require_canonical_delivery_id(delivery_id))
        intake = report.transcript_source_intake_id
        target_artifact = report.target_artifact_id

        current = self._publications.get_current(intake)
        if (
            current is not None
            and current.kind is PublicationKind.PUBLISH
            and current.target_delivery_id == delivery.identity
        ):
            # The current authority already publishes this exact delivery — repeated intent
            # (even by another actor) converges on the established state; authority is a
            # state, not a command ledger (the GOAL-009/GOAL-015 rule). First-establishing
            # provenance is preserved.
            return PublicationResult(
                publication=current, outcome=PublicationOutcome.REUSED, previous=None
            )
        return self._append(
            intake=intake,
            kind=PublicationKind.PUBLISH,
            target_delivery_id=delivery.identity,
            target_artifact_id=target_artifact,
            actor=actor,
            rationale=rationale,
            current=current,
        )

    def withdraw(
        self,
        *,
        intake_id: str,
        publisher: str,
        rationale: str | None = None,
    ) -> PublicationResult:
        actor = self._require_actor(publisher)
        intake = self._resolve_intake(intake_id)
        current = self._publications.get_current(intake)
        if current is None:
            raise EffectiveSrtPublicationError(
                "nothing to withdraw: this intake scope has no publication history"
            )
        if current.kind is PublicationKind.WITHDRAW:
            # Already withdrawn — repeated intent converges on the established state.
            return PublicationResult(
                publication=current, outcome=PublicationOutcome.REUSED, previous=None
            )
        return self._append(
            intake=intake,
            kind=PublicationKind.WITHDRAW,
            target_delivery_id=None,
            target_artifact_id=None,
            actor=actor,
            rationale=rationale,
            current=current,
        )

    def _append(
        self,
        *,
        intake: TranscriptSourceIntakeId,
        kind: PublicationKind,
        target_delivery_id: EffectiveSrtDeliveryId | None,
        target_artifact_id: EffectiveSubtitleSrtArtifactId | None,
        actor: HumanActorReference,
        rationale: str | None,
        current: EffectiveSrtPublication | None,
    ) -> PublicationResult:
        sequence = 0 if current is None else current.sequence + 1
        publication = EffectiveSrtPublication(
            identity=derive_publication_identity(
                intake, kind, target_delivery_id, sequence
            ),
            transcript_source_intake_id=intake,
            kind=kind,
            publisher=actor,
            sequence=sequence,
            content_fingerprint=_content_fingerprint(
                intake, kind, target_delivery_id, target_artifact_id, sequence,
                actor, rationale,
            ),
            target_delivery_id=target_delivery_id,
            target_artifact_id=target_artifact_id,
            previous_publication_id=current.identity if current is not None else None,
            rationale=rationale,
        )
        try:
            self._persistence.persist_publication(publication=publication)
        except PersistenceIdentityCollisionError:
            # A near-concurrent command advanced the history. Converge only when the resolved
            # current holds our exact kind/target with an equal payload fingerprint; a
            # competing DIFFERENT command surfaces the conflict explicitly — an explicit
            # Human command is never silently discarded.
            resolved = self._publications.get_current(intake)
            if (
                resolved is not None
                and resolved.kind is kind
                and resolved.target_delivery_id == target_delivery_id
                and resolved.content_fingerprint
                == _content_fingerprint(
                    intake, kind, target_delivery_id, target_artifact_id,
                    resolved.sequence, actor, rationale,
                )
            ):
                return PublicationResult(
                    publication=resolved, outcome=PublicationOutcome.REUSED, previous=None
                )
            raise PublicationConflictError(
                "a competing publication command was recorded concurrently; re-evaluate "
                "the current authority and reissue the explicit command"
            ) from None
        outcome = (
            PublicationOutcome.RECORDED if current is None else PublicationOutcome.CHANGED
        )
        return PublicationResult(
            publication=publication, outcome=outcome, previous=current
        )

    # -- queries (derived; never mutate history) ------------------------------------------------------

    def get(self, publication_id: str) -> EffectiveSrtPublication | None:
        return self._publications.get(require_canonical_publication_id(publication_id))

    def current(self, intake_id: str) -> EffectiveSrtPublication | None:
        return self._publications.get_current(self._resolve_intake(intake_id))

    def history(self, intake_id: str) -> tuple[EffectiveSrtPublication, ...]:
        return self._publications.history(self._resolve_intake(intake_id))

    def availability(self, intake_id: str) -> PublicationAvailability:
        """Derived operational availability for one intake scope — never persisted.

        Authority first (not_published / withdrawn), then supporting Delivery resolvability,
        then — only when a Delivery Root observer is supplied — destination agreement.
        Missing or diverged files never mutate publication history.
        """

        current = self._publications.get_current(self._resolve_intake(intake_id))
        return self._availability_of(current)

    def status(self, publication_id: str) -> PublicationStatus:
        publication = self.get(publication_id)
        if publication is None:
            raise EffectiveSrtPublicationError("unknown effective SRT publication")
        current = self._publications.get_current(
            publication.transcript_source_intake_id
        )
        delivery_state: DeliveryState | None = None
        observation = "not_observed"
        currentness: ArtifactCurrentness | None = None
        if publication.kind is PublicationKind.PUBLISH:
            delivery = self._deliveries.get(publication.target_delivery_id)
            if delivery is not None:
                outcome = self._deliveries.get_outcome(delivery.identity)
                delivery_state = (
                    DeliveryState.PENDING if outcome is None else outcome.state
                )
                artifact = self._artifacts.get(publication.target_artifact_id.value)
                if artifact is not None:
                    observation = self._observe_destination(delivery, artifact)
                    currentness = self._artifacts.currentness(artifact)
        return PublicationStatus(
            publication=publication,
            current=current is not None and current.identity == publication.identity,
            delivery_state=delivery_state,
            destination_observation=observation,
            artifact_currentness=currentness,
            scope_availability=self._availability_of(current),
        )

    # -- internals ------------------------------------------------------------------------------------

    def _availability_of(
        self, current: EffectiveSrtPublication | None
    ) -> PublicationAvailability:
        if current is None:
            return PublicationAvailability.NOT_PUBLISHED
        if current.kind is PublicationKind.WITHDRAW:
            return PublicationAvailability.WITHDRAWN
        delivery = self._deliveries.get(current.target_delivery_id)
        if delivery is None:
            return PublicationAvailability.UNRESOLVABLE
        outcome = self._deliveries.get_outcome(delivery.identity)
        if outcome is None or outcome.state is not DeliveryState.DELIVERED:
            return PublicationAvailability.UNRESOLVABLE
        artifact = self._resolve_lineage(delivery, outcome)
        if artifact is None:
            return PublicationAvailability.UNRESOLVABLE
        observation = self._observe_destination(delivery, artifact)
        if observation == "not_observed":
            return PublicationAvailability.NOT_OBSERVED
        if observation == "missing":
            return PublicationAvailability.DESTINATION_MISSING
        if observation in ("differs", "unsafe"):
            return PublicationAvailability.DESTINATION_MISMATCH
        return PublicationAvailability.AVAILABLE

    def _resolve_lineage(self, delivery: EffectiveSrtDelivery, outcome):
        """The delivery's full lineage must be structurally coherent; returns the artifact."""

        if (
            outcome is not None
            and outcome.delivered_payload_fingerprint is not None
            and outcome.delivered_payload_fingerprint
            != delivery.expected_payload_fingerprint
        ):
            return None
        materialization = self._materializations.get(delivery.materialization_id)
        if materialization is None or materialization.artifact_id != delivery.artifact_id:
            return None
        artifact = self._artifacts.get(delivery.artifact_id.value)
        if artifact is None or artifact.content_fingerprint != delivery.expected_payload_fingerprint:
            return None
        return artifact

    def _observe_destination(self, delivery: EffectiveSrtDelivery, artifact) -> str:
        if self._destination is None:
            return "not_observed"
        try:
            observed = self._destination.read(
                relative_location=delivery.relative_location
            )
        except (MaterializationContainmentError, MaterializationWriteError):
            return "unsafe"
        if observed is None:
            return "missing"
        expected = artifact.srt_content.encode("utf-8")
        return "matches" if observed == expected else "differs"

    def _require_actor(self, publisher: str) -> HumanActorReference:
        if not isinstance(publisher, str) or not publisher.strip():
            raise EffectiveSrtPublicationError(
                "publisher must be a non-empty Human actor reference"
            )
        return HumanActorReference(publisher)

    def _resolve_intake(self, intake_id: str) -> TranscriptSourceIntakeId:
        try:
            return require_canonical_intake_id(intake_id)
        except ProviderTranscriptAdmissionError as error:
            raise EffectiveSrtPublicationError(str(error)) from error


def require_canonical_publication_id(value: str) -> EffectiveSrtPublicationId:
    prefix = EFFECTIVE_SRT_PUBLICATION_IDENTITY_PREFIX + ":"
    if (
        not isinstance(value, str)
        or not value.startswith(prefix)
        or len(value) != len(prefix) + 64
    ):
        raise EffectiveSrtPublicationError(
            "effective SRT publication identity is malformed "
            "(expected 'subtitle-effective-srt-publication:<64 hex digest>')"
        )
    return EffectiveSrtPublicationId(value)


__all__ = [
    "EFFECTIVE_SRT_PUBLICATION_IDENTITY_PREFIX",
    "PUBLICATION_CONTRACT_KIND",
    "PUBLICATION_CONTRACT_VERSION",
    "AtomicPublicationPersistence",
    "DeliveryNotPublishableError",
    "EffectiveSrtPublication",
    "EffectiveSrtPublicationError",
    "EffectiveSrtPublicationService",
    "PublicationAvailability",
    "PublicationBlockingReason",
    "PublicationConflictError",
    "PublicationEligibility",
    "PublicationKind",
    "PublicationOutcome",
    "PublicationResult",
    "PublicationStatus",
    "derive_publication_identity",
    "require_canonical_publication_id",
]
