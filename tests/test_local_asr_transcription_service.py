"""Orchestration tests for the local ASR execution adapter (040 §15)."""

import unittest

from lectureos.application.identities import TranscriptSourceIntakeId
from lectureos.application.local_asr_transcription import (
    APPROVED_LOCAL_ASR_CONFIGURATION,
    LocalAsrDependencyError,
    LocalAsrEngineError,
    LocalAsrError,
    LocalAsrIntakeError,
    LocalAsrModelError,
    LocalAsrOutputError,
    LocalAsrProviderConfiguration,
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
    derive_provider_transcript_admission_identity,
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

    def transcribe(
        self, *, media_path, model, language, device, compute_type, condition_on_previous_text
    ):
        self.invocations.append(
            dict(
                media_path=media_path,
                model=model,
                language=language,
                device=device,
                compute_type=compute_type,
                condition_on_previous_text=condition_on_previous_text,
            )
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


def _service(
    *, intake=True, media=True, verifier=None, engine=None, store=None, configuration=None
):
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
    kwargs = {} if configuration is None else {"configuration": configuration}
    service = LocalAsrTranscriptionService(
        intakes, source_media, store, admission_service, verifier, engine, **kwargs
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


class LocalAsrProviderConfigurationTests(unittest.TestCase):
    """040 §15 L-15/L-16 (PATCH-0040): the declared provider configuration and its identity role."""

    def test_approved_configuration_disables_previous_text_conditioning(self):
        """P-2: the sole approved production value."""

        self.assertFalse(APPROVED_LOCAL_ASR_CONFIGURATION.condition_on_previous_text)

    def test_engine_receives_the_setting_explicitly(self):
        """P-1: passed explicitly, never inherited from the installed library's default."""

        service, _, engine, _ = _service()
        service.transcribe(intake_id=_INTAKE_ID, model="tiny", language="ko")
        self.assertIn("condition_on_previous_text", engine.invocations[0])
        self.assertIs(engine.invocations[0]["condition_on_previous_text"], False)

    def test_setting_is_fixed_regardless_of_library_default(self):
        """P-1: the value is pinned to the contract, not to whatever the library currently defaults to."""

        service, _, engine, _ = _service()
        service.transcribe(intake_id=_INTAKE_ID, model="tiny", language="ko")
        self.assertEqual(
            engine.invocations[0]["condition_on_previous_text"],
            APPROVED_LOCAL_ASR_CONFIGURATION.condition_on_previous_text,
        )

    def test_vad_is_never_passed_on_the_production_path(self):
        """L-16/P-8: no VAD parameter is introduced by this contract."""

        service, _, engine, _ = _service()
        service.transcribe(intake_id=_INTAKE_ID, model="tiny", language="ko")
        for forbidden in ("vad_filter", "vad_parameters", "speech_pad_ms", "min_silence_duration_ms"):
            self.assertNotIn(forbidden, engine.invocations[0])

    def test_service_configuration_is_fixed_at_construction(self):
        """P-2: there is no per-call override, so no caller can select a different value."""

        service, _, _, _ = _service()
        self.assertEqual(service.configuration, APPROVED_LOCAL_ASR_CONFIGURATION)

    def test_reference_records_the_configuration_as_provenance(self):
        """P-6: the setting is legible from the persisted record alone, with no new column."""

        service, _, _, _ = _service()
        result = service.transcribe(intake_id=_INTAKE_ID, model="tiny", language="ko")
        self.assertIn("cond_prev_text=false", result.admission.provider_result_ref)
        self.assertIn("local-asr:v2:", result.admission.provider_result_ref)

    def test_differing_configuration_is_not_the_same_execution(self):
        """P-3: a different setting is a different semantic request — distinct reference and identity."""

        off = derive_provider_result_ref(
            _MEDIA_ID, "tiny", "ko", LocalAsrProviderConfiguration(condition_on_previous_text=False)
        )
        on = derive_provider_result_ref(
            _MEDIA_ID, "tiny", "ko", LocalAsrProviderConfiguration(condition_on_previous_text=True)
        )
        self.assertNotEqual(off, on)
        intake = TranscriptSourceIntakeId(_INTAKE_ID)
        self.assertNotEqual(
            derive_provider_transcript_admission_identity(intake, "faster-whisper", "tiny", off),
            derive_provider_transcript_admission_identity(intake, "faster-whisper", "tiny", on),
        )

    def test_admissions_under_different_configurations_do_not_collide(self):
        """P-3/P-5 end to end: two services, two admitted results, both engine runs actually happen."""

        store = _AdmissionStore()
        approved, _, engine_off, _ = _service(store=store)
        other, _, engine_on, _ = _service(
            store=store, configuration=LocalAsrProviderConfiguration(condition_on_previous_text=True)
        )
        first = approved.transcribe(intake_id=_INTAKE_ID, model="tiny", language="ko")
        second = other.transcribe(intake_id=_INTAKE_ID, model="tiny", language="ko")
        self.assertTrue(first.executed and second.executed)
        self.assertNotEqual(first.admission.identity, second.admission.identity)
        self.assertNotEqual(first.admission.raw_transcript_id, second.admission.raw_transcript_id)
        self.assertEqual(len(store.records), 2)
        self.assertIs(engine_off.invocations[0]["condition_on_previous_text"], False)
        self.assertIs(engine_on.invocations[0]["condition_on_previous_text"], True)

    def test_released_v1_reference_is_not_regenerated(self):
        """P-4: v1 stays released; nothing re-derives it and nothing re-interprets it."""

        ref = derive_provider_result_ref(_MEDIA_ID, "tiny", "ko")
        legacy = f"local-asr:model=tiny:lang=ko:media={_MEDIA_ID.value}"
        self.assertNotEqual(ref, legacy)
        self.assertTrue(ref.startswith("local-asr:v2:"))
        self.assertNotIn("cond_prev_text", legacy)

    def test_v1_admission_does_not_satisfy_a_v2_anchor(self):
        """P-5: reuse does not fire across the grammar change, and the prior record is left untouched."""

        intake = TranscriptSourceIntakeId(_INTAKE_ID)
        legacy_ref = f"local-asr:model=tiny:lang=ko:media={_MEDIA_ID.value}"
        self.assertNotEqual(
            derive_provider_transcript_admission_identity(
                intake, "faster-whisper", "tiny", legacy_ref
            ),
            derive_provider_transcript_admission_identity(
                intake, "faster-whisper", "tiny", derive_provider_result_ref(_MEDIA_ID, "tiny", "ko")
            ),
        )

    def test_configuration_rejects_a_non_boolean(self):
        with self.assertRaises(LocalAsrError):
            LocalAsrProviderConfiguration(condition_on_previous_text="false")

    def test_raw_output_is_preserved_verbatim_under_the_configuration(self):
        """P-7: the setting configures the provider; it never filters or edits what came back."""

        engine = _FakeEngine(
            result=LocalAsrResult(
                provider="faster-whisper",
                model="tiny",
                language="ko",
                segments=(
                    LocalAsrSegment(0.0, 2.0, " 화장실 좀 갔다 올게"),
                    LocalAsrSegment(2.0, 4.0, " o"),
                ),
            )
        )
        service, _, _, store = _service(engine=engine)
        result = service.transcribe(intake_id=_INTAKE_ID, model="tiny", language="ko")
        self.assertEqual(result.admission.segment_count, 2)
        admitted = store.records[result.admission.identity.value]
        self.assertEqual(admitted.segment_count, 2)


if __name__ == "__main__":
    unittest.main()
