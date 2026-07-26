"""Orchestration tests for the local ASR execution adapter (040 §15)."""

import unittest

from lectureos.application.identities import TranscriptSourceIntakeId
from lectureos.application.local_asr_transcription import (
    LocalAsrDependencyError,
    LocalAsrEngineError,
    LocalAsrError,
    LocalAsrIntakeError,
    LocalAsrModelError,
    LocalAsrOutputError,
    LocalAsrResult,
    LocalAsrSegment,
    LocalAsrSourceChangedError,
    LocalAsrSourceUnavailableError,
    LocalAsrTranscriptionService,
    derive_provider_result_ref,
)
from lectureos.application.media_import import SourceMediaRecord, derive_media_identity
from lectureos.application.provider_transcript_admission import (
    ProviderTranscriptAdmissionService,
)
from lectureos.application.transcript_source_intake import (
    TranscriptSourceIntake,
    derive_intake_identity,
)
from lectureos.execution.identities import SourceMediaId
from lectureos.persistence.errors import PersistenceIdentityCollisionError

_DIGEST = "abcd" * 16
_MEDIA_ID = SourceMediaId(f"sha256:{_DIGEST}")
_INTAKE_ID = derive_intake_identity(_MEDIA_ID).value


def _record():
    return SourceMediaRecord(
        identity=_MEDIA_ID,
        fingerprint_algorithm="sha256",
        fingerprint_digest=_DIGEST,
        byte_length=10,
        observed_source_path="/abs/lecture.bin",
    )


class _FakeQuery:
    def __init__(self, records=None):
        self._records = dict(records or {})

    def get(self, identity):
        return self._records.get(identity.value)


class _AdmissionStore:
    """In-memory store acting as both the admission query (pre-check) and the atomic persistence."""

    def __init__(self):
        self.records = {}

    def get(self, identity):
        return self.records.get(identity.value)

    def persist_provider_transcript_admission(
        self, *, admission, provider_result, segments, raw_transcript, result
    ):
        if admission.identity.value in self.records:
            raise PersistenceIdentityCollisionError("admission exists")
        self.records[admission.identity.value] = admission


class _FakeVerifier:
    def __init__(self, path="/abs/lecture.bin", error=None):
        self.path = path
        self.error = error
        self.calls = 0

    def verify(self, record):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.path


class _FakeEngine:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.invocations = []

    def transcribe(self, *, media_path, model, language, device, compute_type):
        self.invocations.append(
            dict(media_path=media_path, model=model, language=language, device=device, compute_type=compute_type)
        )
        if self.error is not None:
            raise self.error
        if self.result is not None:
            return self.result
        return LocalAsrResult(
            provider="faster-whisper",
            model=model,
            language=language or "ko",
            segments=(LocalAsrSegment(0.0, 2.0, "안녕하세요"), LocalAsrSegment(2.0, 4.0, "반갑습니다")),
        )


def _service(*, intake=True, media=True, verifier=None, engine=None, store=None):
    intakes = _FakeQuery(
        {_INTAKE_ID: TranscriptSourceIntake(TranscriptSourceIntakeId(_INTAKE_ID), _MEDIA_ID)}
        if intake
        else {}
    )
    source_media = _FakeQuery({_MEDIA_ID.value: _record()} if media else {})
    store = store if store is not None else _AdmissionStore()
    admission_service = ProviderTranscriptAdmissionService(intakes, source_media, store, store)
    verifier = verifier if verifier is not None else _FakeVerifier()
    engine = engine if engine is not None else _FakeEngine()
    service = LocalAsrTranscriptionService(
        intakes, source_media, store, admission_service, verifier, engine
    )
    return service, verifier, engine, store


class LocalAsrOrchestrationTests(unittest.TestCase):
    def test_successful_transcription_admits_and_runs(self):
        service, verifier, engine, store = _service()
        result = service.transcribe(intake_id=_INTAKE_ID, model="tiny", language="ko")
        self.assertTrue(result.created)
        self.assertTrue(result.executed)
        self.assertEqual(result.admission.segment_count, 2)
        self.assertEqual(result.admission.provider_reference, "faster-whisper")
        self.assertEqual(result.admission.provider_model, "tiny")
        self.assertEqual(verifier.calls, 1)
        self.assertEqual(len(engine.invocations), 1)

    def test_engine_receives_verified_source_path_and_cpu_defaults(self):
        verifier = _FakeVerifier(path="/resolved/lecture.bin")
        service, _, engine, _ = _service(verifier=verifier)
        service.transcribe(intake_id=_INTAKE_ID, model="tiny")
        call = engine.invocations[0]
        self.assertEqual(call["media_path"], "/resolved/lecture.bin")
        self.assertEqual(call["device"], "cpu")
        self.assertEqual(call["compute_type"], "int8")

    def test_language_passthrough(self):
        service, _, engine, _ = _service()
        service.transcribe(intake_id=_INTAKE_ID, model="tiny", language="en")
        self.assertEqual(engine.invocations[0]["language"], "en")

    def test_replay_reuses_without_rerunning_engine(self):
        service, verifier, engine, _ = _service()
        first = service.transcribe(intake_id=_INTAKE_ID, model="tiny", language="ko")
        second = service.transcribe(intake_id=_INTAKE_ID, model="tiny", language="ko")
        self.assertTrue(first.executed)
        self.assertFalse(second.executed)
        self.assertFalse(second.created)
        self.assertEqual(second.admission.identity, first.admission.identity)
        self.assertEqual(len(engine.invocations), 1)  # engine ran only once
        self.assertEqual(verifier.calls, 1)  # no re-verify on reuse

    def test_distinct_model_produces_distinct_admission(self):
        service, _, engine, _ = _service()
        a = service.transcribe(intake_id=_INTAKE_ID, model="tiny", language="ko")
        b = service.transcribe(intake_id=_INTAKE_ID, model="base", language="ko")
        self.assertNotEqual(a.admission.identity, b.admission.identity)
        self.assertEqual(len(engine.invocations), 2)

    def test_distinct_language_produces_distinct_admission(self):
        service, _, engine, _ = _service()
        a = service.transcribe(intake_id=_INTAKE_ID, model="tiny", language="ko")
        b = service.transcribe(intake_id=_INTAKE_ID, model="tiny", language="en")
        self.assertNotEqual(a.admission.identity, b.admission.identity)

    def test_malformed_intake_rejected(self):
        service, _, engine, _ = _service()
        with self.assertRaises(LocalAsrIntakeError):
            service.transcribe(intake_id="not-an-intake", model="tiny")
        self.assertEqual(len(engine.invocations), 0)

    def test_unknown_intake_rejected(self):
        service, _, engine, _ = _service(intake=False)
        with self.assertRaises(LocalAsrIntakeError):
            service.transcribe(intake_id=_INTAKE_ID, model="tiny")
        self.assertEqual(len(engine.invocations), 0)

    def test_missing_source_media_record_rejected(self):
        service, _, engine, _ = _service(media=False)
        with self.assertRaises(LocalAsrIntakeError):
            service.transcribe(intake_id=_INTAKE_ID, model="tiny")
        self.assertEqual(len(engine.invocations), 0)

    def test_empty_model_rejected(self):
        service, _, engine, _ = _service()
        with self.assertRaises(LocalAsrError):
            service.transcribe(intake_id=_INTAKE_ID, model="   ")
        self.assertEqual(len(engine.invocations), 0)

    def test_source_unavailable_rejected_without_running_engine(self):
        verifier = _FakeVerifier(error=LocalAsrSourceUnavailableError("missing"))
        service, _, engine, store = _service(verifier=verifier)
        with self.assertRaises(LocalAsrSourceUnavailableError):
            service.transcribe(intake_id=_INTAKE_ID, model="tiny")
        self.assertEqual(len(engine.invocations), 0)
        self.assertEqual(len(store.records), 0)

    def test_source_changed_rejected_without_writing(self):
        verifier = _FakeVerifier(error=LocalAsrSourceChangedError("changed"))
        service, _, engine, store = _service(verifier=verifier)
        with self.assertRaises(LocalAsrSourceChangedError):
            service.transcribe(intake_id=_INTAKE_ID, model="tiny")
        self.assertEqual(len(engine.invocations), 0)
        self.assertEqual(len(store.records), 0)

    def test_dependency_missing_surfaced_without_writing(self):
        engine = _FakeEngine(error=LocalAsrDependencyError("no faster-whisper"))
        service, _, _, store = _service(engine=engine)
        with self.assertRaises(LocalAsrDependencyError):
            service.transcribe(intake_id=_INTAKE_ID, model="tiny")
        self.assertEqual(len(store.records), 0)

    def test_model_missing_surfaced_without_writing(self):
        engine = _FakeEngine(error=LocalAsrModelError("no model"))
        service, _, _, store = _service(engine=engine)
        with self.assertRaises(LocalAsrModelError):
            service.transcribe(intake_id=_INTAKE_ID, model="ghost")
        self.assertEqual(len(store.records), 0)

    def test_engine_failure_surfaced_without_writing(self):
        engine = _FakeEngine(error=LocalAsrEngineError("boom"))
        service, _, _, store = _service(engine=engine)
        with self.assertRaises(LocalAsrEngineError):
            service.transcribe(intake_id=_INTAKE_ID, model="tiny")
        self.assertEqual(len(store.records), 0)

    def test_malformed_engine_output_rejected_as_output_error(self):
        # end <= start is inadmissible; the adapter must translate to LocalAsrOutputError, writing nothing.
        engine = _FakeEngine(
            result=LocalAsrResult(
                provider="faster-whisper",
                model="tiny",
                language="ko",
                segments=(LocalAsrSegment(3.0, 3.0, "zero length"),),
            )
        )
        service, _, _, store = _service(engine=engine)
        with self.assertRaises(LocalAsrOutputError):
            service.transcribe(intake_id=_INTAKE_ID, model="tiny")
        self.assertEqual(len(store.records), 0)

    def test_empty_engine_output_rejected(self):
        engine = _FakeEngine(
            result=LocalAsrResult(provider="faster-whisper", model="tiny", language="ko", segments=())
        )
        service, _, _, store = _service(engine=engine)
        with self.assertRaises(LocalAsrOutputError):
            service.transcribe(intake_id=_INTAKE_ID, model="tiny")
        self.assertEqual(len(store.records), 0)

    def test_korean_text_preserved_through_admission(self):
        service, _, _, store = _service()
        result = service.transcribe(intake_id=_INTAKE_ID, model="tiny", language="ko")
        self.assertEqual(result.admission.segment_count, 2)
        self.assertEqual(len(store.records), 1)

    def test_provider_result_ref_is_deterministic(self):
        ref1 = derive_provider_result_ref(_MEDIA_ID, "tiny", "ko")
        ref2 = derive_provider_result_ref(_MEDIA_ID, "tiny", "ko")
        self.assertEqual(ref1, ref2)
        self.assertNotEqual(ref1, derive_provider_result_ref(_MEDIA_ID, "tiny", "en"))
        self.assertNotEqual(ref1, derive_provider_result_ref(_MEDIA_ID, "base", "ko"))


if __name__ == "__main__":
    unittest.main()
