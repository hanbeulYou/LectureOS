import dataclasses
import unittest

from lectureos.application.media_import import (
    MediaImportError,
    MediaImportService,
    SourceMediaFingerprint,
    SourceMediaRecord,
    derive_media_identity,
)
from lectureos.execution.identities import SourceMediaId
from lectureos.persistence.errors import PersistenceIdentityCollisionError

_DIGEST_A = "a" * 64
_DIGEST_B = "b" * 64


def _fingerprint(digest=_DIGEST_A, byte_length=42, path="/abs/source.bin"):
    return SourceMediaFingerprint(
        algorithm="sha256", digest=digest, byte_length=byte_length, observed_source_path=path
    )


class _Inspector:
    def __init__(self, fingerprint=None, error=None):
        self._fingerprint = fingerprint if fingerprint is not None else _fingerprint()
        self._error = error

    def inspect(self, source_path):
        if self._error is not None:
            raise self._error
        return self._fingerprint


class _Repository:
    def __init__(self):
        self.records = {}

    def get(self, identity):
        return self.records.get(identity)


class _Persistence:
    def __init__(self, repository, *, fail_with=None):
        self._repository = repository
        self._fail_with = fail_with
        self.calls = 0

    def persist_source_media(self, *, record):
        self.calls += 1
        if self._fail_with is not None:
            raise self._fail_with
        if record.identity in self._repository.records:
            raise PersistenceIdentityCollisionError("exists")
        self._repository.records[record.identity] = record


class SourceMediaRecordDomainTests(unittest.TestCase):
    def _record(self, **overrides):
        base = dict(
            identity=derive_media_identity("sha256", _DIGEST_A),
            fingerprint_algorithm="sha256",
            fingerprint_digest=_DIGEST_A,
            byte_length=42,
            observed_source_path="/abs/source.bin",
        )
        base.update(overrides)
        return SourceMediaRecord(**base)

    def test_valid_record_is_immutable(self) -> None:
        record = self._record()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            record.byte_length = 1  # type: ignore[misc]

    def test_identity_must_be_derived_from_fingerprint(self) -> None:
        with self.assertRaises(ValueError):
            self._record(identity=SourceMediaId("sha256:" + "c" * 64))

    def test_digest_must_be_64_lowercase_hex(self) -> None:
        with self.assertRaises(ValueError):
            SourceMediaFingerprint(
                algorithm="sha256", digest="ABC", byte_length=1, observed_source_path="/x"
            )

    def test_byte_length_must_be_positive(self) -> None:
        with self.assertRaises(ValueError):
            _fingerprint(byte_length=0)

    def test_no_path_or_execution_or_status_fields(self) -> None:
        fields = set(SourceMediaRecord.__dataclass_fields__)
        for forbidden in ("run_id", "unit_execution_id", "status", "duration", "codec", "path"):
            self.assertNotIn(forbidden, fields)


class MediaImportServiceTests(unittest.TestCase):
    def _service(self, inspector=None, repository=None, persistence=None):
        repository = repository if repository is not None else _Repository()
        inspector = inspector if inspector is not None else _Inspector()
        persistence = (
            persistence if persistence is not None else _Persistence(repository)
        )
        return MediaImportService(inspector, repository, persistence), repository

    def test_first_import_creates_content_addressed_record(self) -> None:
        service, _repo = self._service()
        result = service.import_media("/abs/source.bin")
        self.assertTrue(result.created)
        self.assertEqual(result.record.identity.value, f"sha256:{_DIGEST_A}")
        self.assertEqual(result.record.byte_length, 42)
        self.assertEqual(result.record.observed_source_path, "/abs/source.bin")

    def test_repeated_import_is_idempotent(self) -> None:
        service, _repo = self._service()
        first = service.import_media("/abs/source.bin")
        second = service.import_media("/abs/source.bin")
        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(second.record.identity, first.record.identity)

    def test_same_content_different_path_resolves_same_identity(self) -> None:
        repo = _Repository()
        service, _ = self._service(
            inspector=_Inspector(_fingerprint(path="/abs/first.bin")), repository=repo
        )
        first = service.import_media("/abs/first.bin")
        # Same digest, a different observed path.
        service2 = MediaImportService(
            _Inspector(_fingerprint(path="/abs/second.bin")), repo, _Persistence(repo)
        )
        second = service2.import_media("/abs/second.bin")
        self.assertFalse(second.created)
        self.assertEqual(second.record.identity, first.record.identity)
        # The recorded path stays the first import's (immutable record).
        self.assertEqual(second.record.observed_source_path, "/abs/first.bin")

    def test_different_content_creates_new_record(self) -> None:
        repo = _Repository()
        MediaImportService(
            _Inspector(_fingerprint(digest=_DIGEST_A)), repo, _Persistence(repo)
        ).import_media("/a")
        result = MediaImportService(
            _Inspector(_fingerprint(digest=_DIGEST_B)), repo, _Persistence(repo)
        ).import_media("/b")
        self.assertTrue(result.created)
        self.assertEqual(len(repo.records), 2)

    def test_ineligible_source_raises(self) -> None:
        service, repo = self._service(
            inspector=_Inspector(error=MediaImportError("source file is empty"))
        )
        with self.assertRaises(MediaImportError):
            service.import_media("/empty")
        self.assertEqual(len(repo.records), 0)

    def test_near_concurrent_duplicate_converges_idempotently(self) -> None:
        # The repository reports "absent" but the persistence raises a collision (another writer won the race).
        repo = _Repository()
        existing = SourceMediaRecord(
            identity=derive_media_identity("sha256", _DIGEST_A),
            fingerprint_algorithm="sha256",
            fingerprint_digest=_DIGEST_A,
            byte_length=42,
            observed_source_path="/abs/winner.bin",
        )

        class _RacingRepository(_Repository):
            def __init__(self):
                super().__init__()
                self._served_absent = False

            def get(self, identity):
                if not self._served_absent:
                    self._served_absent = True
                    return None  # first check: appears absent
                return existing  # after the collision: the winner's record

        racing = _RacingRepository()
        persistence = _Persistence(
            racing, fail_with=PersistenceIdentityCollisionError("race")
        )
        service = MediaImportService(_Inspector(), racing, persistence)
        result = service.import_media("/abs/source.bin")
        self.assertFalse(result.created)
        self.assertEqual(result.record, existing)

    def test_record_without_persistence_raises(self) -> None:
        repo = _Repository()
        service = MediaImportService(_Inspector(), repo)
        with self.assertRaises(RuntimeError):
            service.import_media("/abs/source.bin")


if __name__ == "__main__":
    unittest.main()
