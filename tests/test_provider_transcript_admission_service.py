"""Domain and application tests for the External ASR Boundary admission (040 §14)."""

import unittest

from lectureos.application.identities import (
    ProviderTranscriptAdmissionId,
    TranscriptSourceIntakeId,
)
from lectureos.application.provider_transcript_admission import (
    ProviderTranscriptAdmission,
    ProviderTranscriptAdmissionConflictError,
    ProviderTranscriptAdmissionError,
    ProviderTranscriptAdmissionService,
    ProviderTranscriptDocument,
    build_provider_transcript_document,
    derive_source_timeline_id,
    require_canonical_intake_id,
)
from lectureos.application.transcript_source_intake import TranscriptSourceIntake
from lectureos.execution.identities import SourceMediaId
from lectureos.persistence.errors import PersistenceIdentityCollisionError
from lectureos.transcript.identities import ProviderTranscriptResultId, TranscriptId

_MEDIA = "sha256:" + "a" * 64
_INTAKE = "transcript-source-intake:" + _MEDIA


def _document(**overrides):
    payload = {
        "provider": "fake-deterministic-asr",
        "model": "fake-model-v1",
        "language": "ko",
        "provider_result_ref": "ref-0001",
        "segments": [
            {"start": 0.0, "end": 2.5, "text": "안녕하세요"},
            {"start": 2.5, "end": 5.0, "text": "강의를 시작합니다"},
        ],
    }
    payload.update(overrides)
    return build_provider_transcript_document(payload)


class _FakeQuery:
    def __init__(self, records=None):
        self._records = dict(records or {})

    def get(self, identity):
        return self._records.get(identity.value)

    def put(self, identity, record):
        self._records[identity.value] = record


class _FakePersistence:
    def __init__(self, admissions: _FakeQuery):
        self._admissions = admissions
        self.calls = 0

    def persist_provider_transcript_admission(
        self, *, admission, provider_result, segments, raw_transcript, result
    ):
        self.calls += 1
        if self._admissions.get(admission.identity) is not None:
            raise PersistenceIdentityCollisionError("admission exists")
        self._admissions.put(admission.identity, admission)


def _service(intake=True, media=True, admissions=None, persistence=None):
    intake_records = (
        {_INTAKE: TranscriptSourceIntake(TranscriptSourceIntakeId(_INTAKE), SourceMediaId(_MEDIA))}
        if intake
        else {}
    )
    media_records = {_MEDIA: object()} if media else {}
    admissions = admissions if admissions is not None else _FakeQuery()
    persistence = persistence if persistence is not None else _FakePersistence(admissions)
    service = ProviderTranscriptAdmissionService(
        _FakeQuery(intake_records), _FakeQuery(media_records), admissions, persistence
    )
    return service, admissions, persistence


class DocumentValidationTests(unittest.TestCase):
    def test_valid_document_parses(self):
        document = _document()
        self.assertEqual(document.provider, "fake-deterministic-asr")
        self.assertEqual(len(document.segments), 2)

    def test_empty_segments_rejected(self):
        with self.assertRaises(ProviderTranscriptAdmissionError):
            _document(segments=[])

    def test_empty_text_rejected(self):
        with self.assertRaises(ProviderTranscriptAdmissionError):
            _document(segments=[{"start": 0.0, "end": 1.0, "text": "  "}])

    def test_negative_start_rejected(self):
        with self.assertRaises(ProviderTranscriptAdmissionError):
            _document(segments=[{"start": -1.0, "end": 1.0, "text": "x"}])

    def test_end_before_start_rejected(self):
        with self.assertRaises(ProviderTranscriptAdmissionError):
            _document(segments=[{"start": 2.0, "end": 1.0, "text": "x"}])

    def test_zero_length_rejected(self):
        with self.assertRaises(ProviderTranscriptAdmissionError):
            _document(segments=[{"start": 2.0, "end": 2.0, "text": "x"}])

    def test_unordered_segments_rejected(self):
        with self.assertRaises(ProviderTranscriptAdmissionError):
            _document(
                segments=[
                    {"start": 3.0, "end": 4.0, "text": "b"},
                    {"start": 0.0, "end": 1.0, "text": "a"},
                ]
            )

    def test_overlapping_segments_rejected(self):
        with self.assertRaises(ProviderTranscriptAdmissionError):
            _document(
                segments=[
                    {"start": 0.0, "end": 3.0, "text": "a"},
                    {"start": 2.0, "end": 4.0, "text": "b"},
                ]
            )

    def test_touching_segments_allowed(self):
        document = _document(
            segments=[
                {"start": 0.0, "end": 2.0, "text": "a"},
                {"start": 2.0, "end": 4.0, "text": "b"},
            ]
        )
        self.assertEqual(len(document.segments), 2)

    def test_blank_provider_rejected(self):
        with self.assertRaises(ProviderTranscriptAdmissionError):
            _document(provider="  ")

    def test_blank_provider_result_ref_rejected(self):
        with self.assertRaises(ProviderTranscriptAdmissionError):
            _document(provider_result_ref="")

    def test_unknown_field_rejected(self):
        with self.assertRaises(ProviderTranscriptAdmissionError):
            build_provider_transcript_document(
                {"provider": "p", "provider_result_ref": "r", "segments": [], "extra": 1}
            )

    def test_segment_unknown_field_rejected(self):
        with self.assertRaises(ProviderTranscriptAdmissionError):
            _document(segments=[{"start": 0.0, "end": 1.0, "text": "x", "speaker": "s"}])

    def test_non_numeric_timing_rejected(self):
        with self.assertRaises(ProviderTranscriptAdmissionError):
            _document(segments=[{"start": "0", "end": 1.0, "text": "x"}])

    def test_boolean_timing_rejected(self):
        with self.assertRaises(ProviderTranscriptAdmissionError):
            _document(segments=[{"start": False, "end": 1.0, "text": "x"}])

    def test_optional_model_and_language_may_be_absent(self):
        document = build_provider_transcript_document(
            {
                "provider": "p",
                "provider_result_ref": "r",
                "segments": [{"start": 0.0, "end": 1.0, "text": "x"}],
            }
        )
        self.assertIsNone(document.model)
        self.assertIsNone(document.language)


class IntakeIdentityTests(unittest.TestCase):
    def test_malformed_intake_identity_rejected(self):
        with self.assertRaises(ProviderTranscriptAdmissionError):
            require_canonical_intake_id("not-an-intake")

    def test_canonical_intake_identity_accepted(self):
        self.assertEqual(require_canonical_intake_id(_INTAKE).value, _INTAKE)

    def test_source_timeline_is_derived_from_media(self):
        self.assertEqual(
            derive_source_timeline_id(SourceMediaId(_MEDIA)).value,
            "source-timeline:" + _MEDIA,
        )


class AdmissionServiceTests(unittest.TestCase):
    def test_admits_and_creates_canonical_records(self):
        service, admissions, persistence = _service()
        result = service.admit(intake_id=_INTAKE, document=_document())
        self.assertTrue(result.created)
        self.assertEqual(persistence.calls, 1)
        admission = result.admission
        self.assertTrue(admission.identity.value.startswith("provider-transcript-admission:"))
        self.assertTrue(
            admission.provider_transcript_result_id.value.startswith("provider-transcript-result:")
        )
        self.assertTrue(admission.raw_transcript_id.value.startswith("raw-transcript:"))
        self.assertEqual(admission.segment_count, 2)
        self.assertEqual(admission.source_media_id, SourceMediaId(_MEDIA))
        self.assertEqual(admission.provider_reference, "fake-deterministic-asr")

    def test_identities_are_deterministic(self):
        first, _, _ = _service()
        second, _, _ = _service()
        r1 = first.admit(intake_id=_INTAKE, document=_document())
        r2 = second.admit(intake_id=_INTAKE, document=_document())
        self.assertEqual(r1.admission.identity, r2.admission.identity)
        self.assertEqual(
            r1.admission.provider_transcript_result_id,
            r2.admission.provider_transcript_result_id,
        )
        self.assertEqual(r1.admission.content_fingerprint, r2.admission.content_fingerprint)

    def test_repeated_admission_is_idempotent(self):
        service, _, persistence = _service()
        first = service.admit(intake_id=_INTAKE, document=_document())
        repeated = service.admit(intake_id=_INTAKE, document=_document())
        self.assertFalse(repeated.created)
        self.assertEqual(repeated.admission.identity, first.admission.identity)
        self.assertEqual(persistence.calls, 1)

    def test_conflicting_replay_rejected(self):
        service, _, _ = _service()
        service.admit(intake_id=_INTAKE, document=_document())
        conflicting = _document(segments=[{"start": 0.0, "end": 1.0, "text": "다른 내용"}])
        with self.assertRaises(ProviderTranscriptAdmissionConflictError):
            service.admit(intake_id=_INTAKE, document=conflicting)

    def test_distinct_provider_results_allowed_for_one_intake(self):
        service, _, _ = _service()
        a = service.admit(intake_id=_INTAKE, document=_document(provider_result_ref="ref-a"))
        b = service.admit(intake_id=_INTAKE, document=_document(provider_result_ref="ref-b"))
        self.assertTrue(a.created and b.created)
        self.assertNotEqual(a.admission.identity, b.admission.identity)
        self.assertNotEqual(a.admission.raw_transcript_id, b.admission.raw_transcript_id)

    def test_unknown_intake_rejected(self):
        service, _, persistence = _service(intake=False)
        with self.assertRaises(ProviderTranscriptAdmissionError):
            service.admit(intake_id=_INTAKE, document=_document())
        self.assertEqual(persistence.calls, 0)

    def test_malformed_intake_identity_rejected(self):
        service, _, _ = _service()
        with self.assertRaises(ProviderTranscriptAdmissionError):
            service.admit(intake_id="bad", document=_document())

    def test_missing_source_media_rejected(self):
        service, _, persistence = _service(media=False)
        with self.assertRaises(ProviderTranscriptAdmissionError):
            service.admit(intake_id=_INTAKE, document=_document())
        self.assertEqual(persistence.calls, 0)

    def test_near_concurrent_collision_converges(self):
        admissions = _FakeQuery()

        class _RacingPersistence:
            calls = 0

            def persist_provider_transcript_admission(self, *, admission, **_):
                type(self).calls += 1
                # Simulate another writer winning the race just before this insert.
                admissions.put(admission.identity, admission)
                raise PersistenceIdentityCollisionError("won by another writer")

        service, _, _ = _service(admissions=admissions, persistence=_RacingPersistence())
        result = service.admit(intake_id=_INTAKE, document=_document())
        self.assertFalse(result.created)

    def test_persistence_required(self):
        intake_records = {
            _INTAKE: TranscriptSourceIntake(TranscriptSourceIntakeId(_INTAKE), SourceMediaId(_MEDIA))
        }
        service = ProviderTranscriptAdmissionService(
            _FakeQuery(intake_records), _FakeQuery({_MEDIA: object()}), _FakeQuery(), None
        )
        with self.assertRaises(RuntimeError):
            service.admit(intake_id=_INTAKE, document=_document())


class AdmissionRecordTests(unittest.TestCase):
    def _valid_kwargs(self):
        return dict(
            identity=ProviderTranscriptAdmissionId("provider-transcript-admission:x"),
            transcript_source_intake_id=TranscriptSourceIntakeId(_INTAKE),
            source_media_id=SourceMediaId(_MEDIA),
            provider_transcript_result_id=ProviderTranscriptResultId("provider-transcript-result:x"),
            raw_transcript_id=TranscriptId("raw-transcript:x"),
            provider_reference="p",
            provider_result_ref="r",
            segment_count=1,
            content_fingerprint="0" * 64,
        )

    def test_rejects_non_positive_segment_count(self):
        kwargs = self._valid_kwargs()
        kwargs["segment_count"] = 0
        with self.assertRaises(ValueError):
            ProviderTranscriptAdmission(**kwargs)

    def test_rejects_bad_fingerprint_length(self):
        kwargs = self._valid_kwargs()
        kwargs["content_fingerprint"] = "short"
        with self.assertRaises(ValueError):
            ProviderTranscriptAdmission(**kwargs)


if __name__ == "__main__":
    unittest.main()
