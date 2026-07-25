import dataclasses
import unittest

from lectureos.application.media_import import SourceMediaRecord, derive_media_identity
from lectureos.application.transcript_source_intake import (
    TranscriptSourceIntake,
    TranscriptSourceIntakeError,
    TranscriptSourceIntakeService,
    derive_intake_identity,
    require_canonical_source_media_id,
)
from lectureos.application.identities import TranscriptSourceIntakeId
from lectureos.execution.identities import SourceMediaId
from lectureos.persistence.errors import PersistenceIdentityCollisionError

_DIGEST_A = "a" * 64
_DIGEST_B = "b" * 64


def _media(digest=_DIGEST_A, path="/abs/source.bin"):
    return SourceMediaRecord(
        identity=derive_media_identity("sha256", digest),
        fingerprint_algorithm="sha256",
        fingerprint_digest=digest,
        byte_length=42,
        observed_source_path=path,
    )


class _Repo:
    def __init__(self, records=()):
        self.records = {r.identity: r for r in records}

    def get(self, identity):
        return self.records.get(identity)


class _Persistence:
    def __init__(self, intake_repo, *, fail_with=None):
        self._repo = intake_repo
        self._fail_with = fail_with

    def persist_transcript_source_intake(self, *, intake):
        if self._fail_with is not None:
            raise self._fail_with
        if intake.identity in self._repo.records:
            raise PersistenceIdentityCollisionError("exists")
        self._repo.records[intake.identity] = intake


class TranscriptSourceIntakeDomainTests(unittest.TestCase):
    def test_valid_intake_is_immutable(self) -> None:
        media = SourceMediaId(f"sha256:{_DIGEST_A}")
        intake = TranscriptSourceIntake(
            identity=derive_intake_identity(media), source_media_id=media
        )
        with self.assertRaises(dataclasses.FrozenInstanceError):
            intake.source_media_id = media  # type: ignore[misc]

    def test_identity_must_be_derived(self) -> None:
        media = SourceMediaId(f"sha256:{_DIGEST_A}")
        with self.assertRaises(ValueError):
            TranscriptSourceIntake(
                identity=TranscriptSourceIntakeId("transcript-source-intake:wrong"),
                source_media_id=media,
            )

    def test_derive_identity_format(self) -> None:
        media = SourceMediaId(f"sha256:{_DIGEST_A}")
        self.assertEqual(
            derive_intake_identity(media).value,
            f"transcript-source-intake:sha256:{_DIGEST_A}",
        )

    def test_require_canonical_rejects_malformed(self) -> None:
        for bad in ("", "not-a-hash", "sha256:short", "sha256:" + "Z" * 64, "sha256:" + "a" * 63):
            with self.subTest(value=bad):
                with self.assertRaises(TranscriptSourceIntakeError):
                    require_canonical_source_media_id(bad)

    def test_require_canonical_accepts_valid(self) -> None:
        value = f"sha256:{_DIGEST_A}"
        self.assertEqual(require_canonical_source_media_id(value), SourceMediaId(value))

    def test_no_codec_audio_or_path_fields(self) -> None:
        fields = set(TranscriptSourceIntake.__dataclass_fields__)
        for forbidden in (
            "codec", "duration", "audio", "language", "provider", "path", "status",
            "observed_source_path", "run_id", "unit_execution_id",
        ):
            self.assertNotIn(forbidden, fields)


class TranscriptSourceIntakeServiceTests(unittest.TestCase):
    def _service(self, media=None, intakes=None, persistence=None):
        media_repo = media if media is not None else _Repo((_media(),))
        intake_repo = intakes if intakes is not None else _Repo()
        persistence = persistence if persistence is not None else _Persistence(intake_repo)
        return TranscriptSourceIntakeService(media_repo, intake_repo, persistence), intake_repo

    def test_admits_eligible_source_media(self) -> None:
        service, _repo = self._service()
        result = service.admit(f"sha256:{_DIGEST_A}")
        self.assertTrue(result.created)
        self.assertEqual(
            result.intake.identity.value, f"transcript-source-intake:sha256:{_DIGEST_A}"
        )
        self.assertEqual(result.intake.source_media_id.value, f"sha256:{_DIGEST_A}")

    def test_repeated_admission_is_idempotent(self) -> None:
        service, _repo = self._service()
        first = service.admit(f"sha256:{_DIGEST_A}")
        second = service.admit(f"sha256:{_DIGEST_A}")
        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(second.intake.identity, first.intake.identity)

    def test_distinct_media_get_distinct_intakes(self) -> None:
        repo = _Repo((_media(_DIGEST_A), _media(_DIGEST_B)))
        intakes = _Repo()
        service = TranscriptSourceIntakeService(repo, intakes, _Persistence(intakes))
        a = service.admit(f"sha256:{_DIGEST_A}")
        b = service.admit(f"sha256:{_DIGEST_B}")
        self.assertNotEqual(a.intake.identity, b.intake.identity)
        self.assertEqual(len(intakes.records), 2)

    def test_unknown_source_media_rejected(self) -> None:
        service, repo = self._service(media=_Repo())  # empty media repo
        with self.assertRaises(TranscriptSourceIntakeError):
            service.admit(f"sha256:{_DIGEST_A}")
        self.assertEqual(len(repo.records), 0)

    def test_malformed_identity_rejected_before_repository(self) -> None:
        service, repo = self._service()
        with self.assertRaises(TranscriptSourceIntakeError):
            service.admit("not-a-media-id")
        self.assertEqual(len(repo.records), 0)

    def test_near_concurrent_duplicate_converges(self) -> None:
        media_repo = _Repo((_media(),))
        media = SourceMediaId(f"sha256:{_DIGEST_A}")
        existing = TranscriptSourceIntake(
            identity=derive_intake_identity(media), source_media_id=media
        )

        class _RacingIntakes(_Repo):
            def __init__(self):
                super().__init__()
                self._served = False

            def get(self, identity):
                if not self._served:
                    self._served = True
                    return None
                return existing

        racing = _RacingIntakes()
        service = TranscriptSourceIntakeService(
            media_repo, racing, _Persistence(racing, fail_with=PersistenceIdentityCollisionError("race"))
        )
        result = service.admit(f"sha256:{_DIGEST_A}")
        self.assertFalse(result.created)
        self.assertEqual(result.intake, existing)

    def test_admission_does_not_mutate_source_media(self) -> None:
        media = _media()
        media_repo = _Repo((media,))
        service, _repo = self._service(media=media_repo)
        service.admit(f"sha256:{_DIGEST_A}")
        self.assertEqual(media_repo.get(media.identity), media)

    def test_record_without_persistence_raises(self) -> None:
        service = TranscriptSourceIntakeService(_Repo((_media(),)), _Repo())
        with self.assertRaises(RuntimeError):
            service.admit(f"sha256:{_DIGEST_A}")


if __name__ == "__main__":
    unittest.main()
