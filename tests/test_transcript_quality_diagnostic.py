"""Provider quality evidence preservation and the derived quality diagnostic (040 §15 QD-1…QD-20).

The gate these tests exist for is QD-8: `original_content` and `content_fingerprint` were one helper
before `PATCH-0045`, so enriching the preserved evidence could silently move every released identity.
`FingerprintIdentityTests` asserts byte-identity directly, and the released demo goldens
(`examples/local-asr`, `examples/transcript-result-admission`) pin the same values independently.
"""

import json
import unittest

from lectureos.application.identities import TranscriptSourceIntakeId
from lectureos.application.local_asr_checkpoint import (
    CHECKPOINT_FORMAT_VERSION,
    CheckpointSegment,
)
from lectureos.application.local_asr_transcription import (
    FASTER_WHISPER_DECODE_EVIDENCE_KIND,
    LocalAsrDecodeEvidence,
    LocalAsrResult,
    LocalAsrSegment,
    LocalAsrTranscriptionService,
    derive_provider_result_ref,
)
from lectureos.application.media_import import SourceMediaRecord
from lectureos.application.provider_transcript_admission import (
    ProviderDecodeEvidence,
    ProviderDecodeWindow,
    ProviderTranscriptAdmissionError,
    ProviderTranscriptAdmissionService,
    ProviderTranscriptDocument,
    ProviderTranscriptSegmentInput,
    build_provider_transcript_document,
    parse_preserved_provider_evidence,
)
from lectureos.application.transcript_quality_diagnostic import (
    DIAGNOSTIC_ALGORITHM_KIND,
    DIAGNOSTIC_ALGORITHM_VERSION,
    PROVIDER_PARAMETER_VERSION,
    DiagnosticCompleteness,
    EvidenceScope,
    QualityFinding,
    QualityReason,
    TranscriptQualityDiagnosticError,
    TranscriptQualityDiagnosticService,
)
from lectureos.application.transcript_source_intake import (
    TranscriptSourceIntake,
    derive_intake_identity,
)
from lectureos.execution.identities import SourceMediaId
from lectureos.infrastructure.faster_whisper_engine import FasterWhisperEngineRunner
from lectureos.persistence.errors import PersistenceIdentityCollisionError

_DIGEST = "abcd" * 16
_MEDIA_ID = SourceMediaId(f"sha256:{_DIGEST}")
_INTAKE_ID = derive_intake_identity(_MEDIA_ID).value

# One decode window covering two segments plus a second window covering one — the measured shape,
# where several segments share a single window's values.
_EVIDENCE = ProviderDecodeEvidence(
    kind=FASTER_WHISPER_DECODE_EVIDENCE_KIND,
    windows=(
        ProviderDecodeWindow(
            window_ref="seek=0",
            segment_ordinals=(0, 1),
            values=(
                ("avg_logprob", -0.281),
                ("compression_ratio", 1.46),
                ("no_speech_prob", 0.033),
                ("temperature", 0.0),
            ),
            start=0.0,
            end=4.0,
        ),
        ProviderDecodeWindow(
            window_ref="seek=400",
            segment_ordinals=(2,),
            values=(
                ("avg_logprob", -0.967),
                ("compression_ratio", 2.37),
                ("no_speech_prob", 0.813),
                ("temperature", 0.4),
            ),
            start=4.0,
            end=6.0,
        ),
    ),
)


def _record():
    return SourceMediaRecord(
        identity=_MEDIA_ID,
        fingerprint_algorithm="sha256",
        fingerprint_digest=_DIGEST,
        byte_length=10,
        observed_source_path="/abs/lecture.bin",
    )


def _segments():
    return (
        ProviderTranscriptSegmentInput(0.0, 2.0, "첫 번째 문장"),
        ProviderTranscriptSegmentInput(2.0, 4.0, "두 번째 문장"),
        ProviderTranscriptSegmentInput(4.0, 6.0, "세 번째 문장"),
    )


def _document(*, evidence=None, ref="fake-result-0001"):
    return ProviderTranscriptDocument(
        provider="faster-whisper",
        provider_result_ref=ref,
        segments=_segments(),
        model="tiny",
        language="ko",
        provider_evidence=evidence,
    )


class _FakeQuery:
    def __init__(self, records=None):
        self._records = dict(records or {})

    def get(self, identity):
        return self._records.get(identity.value)


class _Store:
    """In-memory admission store that also keeps the provider result and raw transcript."""

    def __init__(self):
        self.records = {}
        self.provider_results = {}
        self.raw_transcripts = {}
        self.segments = {}
        self.writes = 0

    def get(self, identity):
        return self.records.get(identity.value)

    def persist_provider_transcript_admission(
        self, *, admission, provider_result, segments, raw_transcript, result
    ):
        if admission.identity.value in self.records:
            raise PersistenceIdentityCollisionError("admission exists")
        self.writes += 1
        self.records[admission.identity.value] = admission
        self.provider_results[provider_result.identity.value] = provider_result
        self.raw_transcripts[raw_transcript.identity.value] = raw_transcript
        for segment in segments:
            self.segments[segment.identity.value] = segment

    # query views used by the diagnostic service
    @property
    def provider_result_query(self):
        return _FakeQuery(self.provider_results)

    @property
    def raw_transcript_query(self):
        return _FakeQuery(self.raw_transcripts)


def _admit(document, store=None):
    store = store if store is not None else _Store()
    intakes = _FakeQuery(
        {_INTAKE_ID: TranscriptSourceIntake(TranscriptSourceIntakeId(_INTAKE_ID), _MEDIA_ID)}
    )
    source_media = _FakeQuery({_MEDIA_ID.value: _record()})
    service = ProviderTranscriptAdmissionService(intakes, source_media, store, store)
    return service.admit(intake_id=_INTAKE_ID, document=document), store


def _diagnostic_service(store):
    return TranscriptQualityDiagnosticService(
        store, store.provider_result_query, store.raw_transcript_query
    )


class FingerprintIdentityTests(unittest.TestCase):
    """QD-8/QD-9: evidence enrichment must move no identity and rewrite no released record."""

    def test_content_fingerprint_is_byte_identical_with_and_without_evidence(self):
        without, _ = _admit(_document())
        with_evidence, _ = _admit(_document(evidence=_EVIDENCE))
        self.assertEqual(
            without.admission.content_fingerprint,
            with_evidence.admission.content_fingerprint,
        )

    def test_provider_result_reference_is_unchanged(self):
        without, _ = _admit(_document())
        with_evidence, _ = _admit(_document(evidence=_EVIDENCE))
        self.assertEqual(
            without.admission.provider_result_ref, with_evidence.admission.provider_result_ref
        )
        # The derived local-ASR reference grammar is untouched: still v2, never v3 (QD-9).
        reference = derive_provider_result_ref(_MEDIA_ID, "tiny", "ko")
        self.assertIn(":v2:", reference)
        self.assertNotIn("v3", reference)

    def test_raw_transcript_and_provider_result_identities_are_unchanged(self):
        without, _ = _admit(_document())
        with_evidence, _ = _admit(_document(evidence=_EVIDENCE))
        self.assertEqual(
            without.admission.raw_transcript_id, with_evidence.admission.raw_transcript_id
        )
        self.assertEqual(
            without.admission.provider_transcript_result_id,
            with_evidence.admission.provider_transcript_result_id,
        )

    def test_evidence_only_difference_is_not_an_identity_conflict(self):
        first, store = _admit(_document())
        # Same anchor, same text and timing, richer evidence: the same logical result (A-8), so it
        # resolves to the existing record instead of raising a conflict.
        second, _ = _admit(_document(evidence=_EVIDENCE), store=store)
        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(first.admission.identity, second.admission.identity)

    def test_legacy_evidence_free_result_stays_readable(self):
        result, store = _admit(_document())
        diagnostic = _diagnostic_service(store).diagnose(
            admission_id=result.admission.identity.value
        )
        self.assertFalse(diagnostic.evidence_available)
        self.assertEqual(diagnostic.decode_window_count, 0)
        self.assertEqual(diagnostic.segment_count, 3)

    def test_re_admission_does_not_backfill_the_released_record(self):
        first, store = _admit(_document())
        preserved = store.provider_results[
            first.admission.provider_transcript_result_id.value
        ].original_content
        _admit(_document(evidence=_EVIDENCE), store=store)
        after = store.provider_results[
            first.admission.provider_transcript_result_id.value
        ].original_content
        self.assertEqual(preserved, after)
        self.assertIsNone(parse_preserved_provider_evidence(after))
        self.assertEqual(store.writes, 1)


class ProviderEvidenceCaptureTests(unittest.TestCase):
    """QD-5/QD-7: the engine's decode evidence reaches the boundary, at window granularity."""

    class _Segment:
        def __init__(self, start, end, text, seek, logprob, nsp, cr, temperature):
            self.start = start
            self.end = end
            self.text = text
            self.seek = seek
            self.avg_logprob = logprob
            self.compression_ratio = cr
            self.no_speech_prob = nsp
            self.temperature = temperature

    class _Info:
        language = "ko"

    def _runner(self, segments):
        def build(model, device, compute_type):
            outer = self

            class _Model:
                def transcribe(self, media_path, **kwargs):
                    return (iter(segments), outer._Info())

            return _Model()

        return FasterWhisperEngineRunner(model_factory=build)

    def _run(self):
        segments = [
            self._Segment(0.0, 2.0, "가", 0, -0.281, 0.033, 1.46, 0.0),
            self._Segment(2.0, 4.0, "나", 0, -0.281, 0.033, 1.46, 0.0),
            self._Segment(4.0, 6.0, "다", 400, -0.967, 0.813, 2.37, 0.4),
        ]
        return self._runner(segments).transcribe(
            media_path="/abs/lecture.bin",
            model="tiny",
            language="ko",
            device="cpu",
            compute_type="int8",
            condition_on_previous_text=False,
        )

    def test_engine_captures_decode_evidence(self):
        result = self._run()
        self.assertTrue(all(s.decode_evidence is not None for s in result.segments))

    def test_each_provider_field_is_preserved_verbatim(self):
        values = dict(self._run().segments[2].decode_evidence.values)
        self.assertAlmostEqual(values["avg_logprob"], -0.967)
        self.assertAlmostEqual(values["no_speech_prob"], 0.813)
        self.assertAlmostEqual(values["compression_ratio"], 2.37)
        self.assertAlmostEqual(values["temperature"], 0.4)

    def test_window_anchor_is_preserved(self):
        result = self._run()
        self.assertEqual(result.segments[0].decode_evidence.window_ref, "seek=0")
        self.assertEqual(result.segments[2].decode_evidence.window_ref, "seek=400")

    def test_no_field_is_renamed_to_a_segment_level_semantic(self):
        evidence = self._run().segments[0].decode_evidence
        names = {name for name, _ in evidence.values}
        # QD-7: the provider's own names survive; nothing is presented as this segment's confidence.
        self.assertEqual(
            names, {"avg_logprob", "compression_ratio", "no_speech_prob", "temperature"}
        )
        self.assertNotIn("confidence", names)
        self.assertNotIn("uncertainty", names)
        self.assertFalse(hasattr(evidence, "confidence"))

    def test_engine_reporting_no_evidence_yields_none(self):
        class _Bare:
            def __init__(self):
                self.start, self.end, self.text = 0.0, 1.0, "가"

        result = self._runner([_Bare()]).transcribe(
            media_path="/abs/lecture.bin",
            model="tiny",
            language=None,
            device="cpu",
            compute_type="int8",
            condition_on_previous_text=False,
        )
        self.assertIsNone(result.segments[0].decode_evidence)


class EvidenceGranularityTests(unittest.TestCase):
    """QD-7: shared window values stay shared, and never become per-segment confidence."""

    def test_segments_sharing_a_window_produce_one_window_entry(self):
        evidence = parse_preserved_provider_evidence(
            _original_content_of(_document(evidence=_EVIDENCE))
        )
        self.assertEqual(len(evidence.windows), 2)
        self.assertEqual(evidence.windows[0].segment_ordinals, (0, 1))
        self.assertEqual(evidence.windows[1].segment_ordinals, (2,))

    def test_generic_transcript_segment_columns_are_untouched(self):
        result, store = _admit(_document(evidence=_EVIDENCE))
        self.assertEqual(len(store.segments), 3)
        for segment in store.segments.values():
            # QD-6: a window value must never be projected onto these released columns.
            self.assertIsNone(segment.confidence)
            self.assertIsNone(segment.uncertainty)

    def test_evidence_may_not_reference_a_missing_segment(self):
        with self.assertRaises(ProviderTranscriptAdmissionError):
            ProviderTranscriptDocument(
                provider="faster-whisper",
                provider_result_ref="r",
                segments=_segments()[:1],
                provider_evidence=_EVIDENCE,
            )

    def test_windows_may_not_share_segment_ordinals(self):
        window = ProviderDecodeWindow(
            window_ref="seek=0", segment_ordinals=(0,), values=(("avg_logprob", -0.1),)
        )
        with self.assertRaises(ProviderTranscriptAdmissionError):
            ProviderDecodeEvidence(kind="k", windows=(window, window))


def _original_content_of(document):
    _, store = _admit(document)
    return next(iter(store.provider_results.values())).original_content


class OriginalContentTests(unittest.TestCase):
    """QD-6: evidence is preserved in `original_content` without disturbing the logical content."""

    def test_evidence_is_preserved(self):
        payload = json.loads(_original_content_of(_document(evidence=_EVIDENCE)))
        self.assertIn("provider_evidence", payload)
        self.assertEqual(
            payload["provider_evidence"]["kind"], FASTER_WHISPER_DECODE_EVIDENCE_KIND
        )

    def test_logical_content_is_unchanged_alongside_evidence(self):
        bare = json.loads(_original_content_of(_document()))
        rich = json.loads(_original_content_of(_document(evidence=_EVIDENCE)))
        rich.pop("provider_evidence")
        self.assertEqual(bare, rich)

    def test_without_evidence_the_representation_is_exactly_as_before(self):
        content = _original_content_of(_document())
        self.assertNotIn("provider_evidence", content)
        self.assertIsNone(parse_preserved_provider_evidence(content))

    def test_representation_is_deterministic(self):
        self.assertEqual(
            _original_content_of(_document(evidence=_EVIDENCE)),
            _original_content_of(_document(evidence=_EVIDENCE)),
        )

    def test_unreadable_content_reports_unavailable_rather_than_raising(self):
        self.assertIsNone(parse_preserved_provider_evidence("not json"))
        self.assertIsNone(parse_preserved_provider_evidence('{"provider_evidence": 5}'))

    def test_document_builder_accepts_submitted_evidence(self):
        document = build_provider_transcript_document(
            {
                "provider": "faster-whisper",
                "model": "tiny",
                "language": "ko",
                "provider_result_ref": "r",
                "segments": [{"start": 0.0, "end": 1.0, "text": "가"}],
                "provider_evidence": {
                    "kind": "faster-whisper/decode-window",
                    "windows": [
                        {
                            "window_ref": "seek=0",
                            "segment_ordinals": [0],
                            "values": {"avg_logprob": -0.2},
                        }
                    ],
                },
            }
        )
        self.assertIsNotNone(document.provider_evidence)


class CheckpointEvidenceTests(unittest.TestCase):
    """QD-9 across `PATCH-0044`: a resumed execution preserves the evidence a fresh one would."""

    def test_checkpoint_format_version_was_bumped(self):
        # A v1 checkpoint holds no evidence; resuming from one would admit a half-evidenced result.
        self.assertEqual(CHECKPOINT_FORMAT_VERSION, 2)

    def test_checkpoint_segment_round_trips_evidence(self):
        segment = CheckpointSegment(
            0, 0.0, 2.0, "가", window_ref="seek=0", values=(("avg_logprob", -0.281),)
        )
        payload = segment.as_payload()
        self.assertEqual(payload["window_ref"], "seek=0")
        self.assertEqual(payload["values"], {"avg_logprob": -0.281})

    def test_checkpoint_segment_without_evidence_omits_the_keys(self):
        self.assertNotIn("window_ref", CheckpointSegment(0, 0.0, 2.0, "가").as_payload())

    def test_resumed_execution_preserves_evidence_for_the_whole_result(self):
        store = _Store()
        intakes = _FakeQuery(
            {_INTAKE_ID: TranscriptSourceIntake(TranscriptSourceIntakeId(_INTAKE_ID), _MEDIA_ID)}
        )
        source_media = _FakeQuery({_MEDIA_ID.value: _record()})
        admission_service = ProviderTranscriptAdmissionService(
            intakes, source_media, store, store
        )

        class _Verifier:
            def verify(self, record):
                return "/abs/lecture.bin"

        class _Engine:
            def transcribe(self, *, media_path, model, language, device, compute_type,
                           condition_on_previous_text, start_offset=None, on_segment=None):
                # The post-resume half, decoded from an offset: its anchor restarts at zero, which
                # must not merge with the pre-resume window that also used `seek=0`.
                return LocalAsrResult(
                    provider="faster-whisper",
                    model=model,
                    language="ko",
                    segments=(
                        LocalAsrSegment(
                            4.0, 6.0, "세 번째 문장",
                            decode_evidence=LocalAsrDecodeEvidence(
                                "seek=0", (("avg_logprob", -0.9),)
                            ),
                        ),
                    ),
                )

        class _Checkpoints:
            """Resumable checkpoint holding two evidence-carrying segments."""

            def owned(self, binding):
                from contextlib import nullcontext

                return nullcontext()

            def load(self, binding):
                from lectureos.application.local_asr_checkpoint import LoadedCheckpoint

                return LoadedCheckpoint(
                    segments=(
                        CheckpointSegment(0, 0.0, 2.0, "첫 번째 문장",
                                          window_ref="seek=0", values=(("avg_logprob", -0.2),)),
                        CheckpointSegment(1, 2.0, 4.0, "두 번째 문장",
                                          window_ref="seek=0", values=(("avg_logprob", -0.2),)),
                    )
                )

            def begin(self, binding):
                pass

            def append(self, binding, segment):
                pass

            def delete(self, binding):
                pass

        service = LocalAsrTranscriptionService(
            intakes, source_media, store, admission_service, _Verifier(), _Engine(),
            checkpoint_store=_Checkpoints(),
        )
        result = service.transcribe(intake_id=_INTAKE_ID, model="tiny", language="ko")
        evidence = parse_preserved_provider_evidence(
            store.provider_results[
                result.admission.provider_transcript_result_id.value
            ].original_content
        )
        self.assertIsNotNone(evidence)
        # Every segment carries evidence, and the repeated `seek=0` anchor stayed two windows.
        self.assertEqual(evidence.covered_ordinals, frozenset({0, 1, 2}))
        self.assertEqual(len(evidence.windows), 2)
        self.assertEqual(evidence.windows[0].segment_ordinals, (0, 1))
        self.assertEqual(evidence.windows[1].segment_ordinals, (2,))


class DiagnosticFoundationTests(unittest.TestCase):
    """QD-10…QD-16: derived, versioned, never persisted, and never silently clean."""

    def _diagnose(self, evidence=None):
        result, store = _admit(_document(evidence=evidence))
        return _diagnostic_service(store).diagnose(
            admission_id=result.admission.identity.value
        ), store

    def test_no_persistence_occurs(self):
        _, store = _admit(_document(evidence=_EVIDENCE))
        before = store.writes
        service = _diagnostic_service(store)
        admission_id = next(iter(store.records))
        service.diagnose(admission_id=admission_id)
        service.diagnose(admission_id=admission_id)
        self.assertEqual(store.writes, before)
        # There is no port through which a diagnostic could be written.
        self.assertFalse(hasattr(service, "_persistence"))

    def test_reason_vocabulary_is_fixed(self):
        self.assertEqual(
            {reason.value for reason in QualityReason},
            {
                "PROVIDER_LOW_CONFIDENCE",
                "PROVIDER_HIGH_NO_SPEECH",
                "PROVIDER_HIGH_COMPRESSION",
                "PROVIDER_DECODE_FALLBACK",
                "REPEATED_TEXT",
            },
        )

    def test_algorithm_anchor_is_declared(self):
        diagnostic, _ = self._diagnose(_EVIDENCE)
        self.assertEqual(diagnostic.algorithm_kind, DIAGNOSTIC_ALGORITHM_KIND)
        self.assertEqual(diagnostic.algorithm_version, DIAGNOSTIC_ALGORITHM_VERSION)
        # QD-14: no threshold parameter set exists, and the result says so rather than implying one.
        self.assertIsNone(diagnostic.provider_parameter_version)
        self.assertIsNone(PROVIDER_PARAMETER_VERSION)

    def test_same_inputs_produce_the_same_result(self):
        result, store = _admit(_document(evidence=_EVIDENCE))
        service = _diagnostic_service(store)
        first = service.diagnose(admission_id=result.admission.identity.value)
        second = service.diagnose(admission_id=result.admission.identity.value)
        self.assertEqual(first, second)

    def test_no_provider_reason_fires_without_a_threshold(self):
        diagnostic, _ = self._diagnose(_EVIDENCE)
        self.assertEqual(diagnostic.findings, ())
        undecided = {entry.reason for entry in diagnostic.undetermined}
        self.assertEqual(undecided, set(QualityReason))
        for entry in diagnostic.undetermined:
            if entry.reason is not QualityReason.REPEATED_TEXT:
                self.assertIn("threshold policy deferred", entry.cause)

    def test_repeated_text_does_not_fire_without_a_contracted_rule(self):
        diagnostic, _ = self._diagnose(_EVIDENCE)
        cause = next(
            entry.cause
            for entry in diagnostic.undetermined
            if entry.reason is QualityReason.REPEATED_TEXT
        )
        self.assertIn("repetition rule not contracted", cause)

    def test_evidence_present_is_observable(self):
        diagnostic, _ = self._diagnose(_EVIDENCE)
        self.assertTrue(diagnostic.evidence_available)
        self.assertEqual(diagnostic.decode_window_count, 2)
        self.assertEqual(diagnostic.evidence_covered_segment_count, 3)

    def test_empty_findings_are_never_reported_as_clean(self):
        for evidence in (None, _EVIDENCE):
            with self.subTest(evidence=evidence is not None):
                diagnostic, _ = self._diagnose(evidence)
                self.assertEqual(diagnostic.findings, ())
                self.assertFalse(diagnostic.reports_clean)
                self.assertIs(diagnostic.completeness, DiagnosticCompleteness.UNAVAILABLE)

    def test_evidence_unavailable_states_its_own_cause(self):
        diagnostic, _ = self._diagnose(None)
        causes = {entry.cause for entry in diagnostic.undetermined}
        self.assertTrue(any("provider evidence unavailable" in cause for cause in causes))

    def test_finding_shape_carries_scope_and_version(self):
        finding = QualityFinding(
            segment_ordinal=2,
            reason=QualityReason.PROVIDER_HIGH_NO_SPEECH,
            evidence_source="no_speech_prob",
            evidence_scope=EvidenceScope.DECODE_WINDOW,
            detail="window value shared by the segments it covers",
        )
        self.assertIs(finding.evidence_scope, EvidenceScope.DECODE_WINDOW)
        self.assertEqual(finding.algorithm_version, DIAGNOSTIC_ALGORITHM_VERSION)

    def test_unknown_admission_is_rejected(self):
        _, store = _admit(_document())
        with self.assertRaises(TranscriptQualityDiagnosticError):
            _diagnostic_service(store).diagnose(
                admission_id="provider-transcript-admission:" + "0" * 64
            )
        with self.assertRaises(TranscriptQualityDiagnosticError):
            _diagnostic_service(store).diagnose(admission_id="nonsense")


class HumanCorrectionBoundaryTests(unittest.TestCase):
    """QD-16/QD-17: the diagnostic hands over an identity and nothing more."""

    def test_the_service_exposes_only_read_only_operations(self):
        _, store = _admit(_document(evidence=_EVIDENCE))
        service = _diagnostic_service(store)
        public = {name for name in dir(service) if not name.startswith("_")}
        # `correction_target_for` resolves an ordinal to an existing identity and is the whole of
        # QD-17's connection; anything that could create, apply, or delete would violate QD-16.
        self.assertEqual(public, {"diagnose", "correction_target_for"})

    def test_no_proposed_replacement_text_is_ever_produced(self):
        result, store = _admit(_document(evidence=_EVIDENCE))
        diagnostic = _diagnostic_service(store).diagnose(
            admission_id=result.admission.identity.value
        )
        for finding in diagnostic.findings:
            self.assertFalse(hasattr(finding, "proposed_text"))
        self.assertFalse(hasattr(diagnostic, "candidates"))

    def test_correction_target_resolves_to_the_existing_segment_identity(self):
        result, store = _admit(_document(evidence=_EVIDENCE))
        segment_id = _diagnostic_service(store).correction_target_for(
            admission_id=result.admission.identity.value, segment_ordinal=2
        )
        # This is exactly what §17 Correction Candidate admission already accepts.
        self.assertIn(segment_id.value, store.segments)

    def test_correction_target_rejects_an_out_of_range_ordinal(self):
        result, store = _admit(_document(evidence=_EVIDENCE))
        with self.assertRaises(TranscriptQualityDiagnosticError):
            _diagnostic_service(store).correction_target_for(
                admission_id=result.admission.identity.value, segment_ordinal=99
            )

    def test_transcript_text_is_never_altered(self):
        result, store = _admit(_document(evidence=_EVIDENCE))
        before = {k: v.text for k, v in store.segments.items()}
        service = _diagnostic_service(store)
        service.diagnose(admission_id=result.admission.identity.value)
        service.correction_target_for(
            admission_id=result.admission.identity.value, segment_ordinal=0
        )
        self.assertEqual({k: v.text for k, v in store.segments.items()}, before)


class DownstreamNonBlockingTests(unittest.TestCase):
    """QD-3/QD-18: no boundary consults the diagnostic, and none is blocked by it."""

    def test_admission_succeeds_with_hallucination_shaped_evidence(self):
        result, _ = _admit(_document(evidence=_EVIDENCE))
        self.assertTrue(result.created)
        self.assertEqual(result.admission.segment_count, 3)

    def test_admission_service_never_computes_a_diagnostic(self):
        import lectureos.application.provider_transcript_admission as admission_module

        source = admission_module.__file__
        with open(source, encoding="utf-8") as handle:
            body = handle.read()
        # The admission boundary must not import or consult the diagnostic (QD-3, QD-4).
        self.assertNotIn("transcript_quality_diagnostic", body)

    def test_selection_and_downstream_modules_do_not_consult_the_diagnostic(self):
        import lectureos.application.current_raw_transcript_selection as selection
        import lectureos.application.effective_subtitle_final_selection as final_selection

        for module in (selection, final_selection):
            with open(module.__file__, encoding="utf-8") as handle:
                self.assertNotIn("transcript_quality_diagnostic", handle.read())


if __name__ == "__main__":
    unittest.main()
