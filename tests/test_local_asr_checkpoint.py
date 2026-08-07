"""Local ASR execution checkpoint and resume tests (040 §15 CP-1…CP-21, PATCH-0044)."""

import json
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

from lectureos.application.identities import TranscriptSourceIntakeId
from lectureos.application.local_asr_checkpoint import (
    CHECKPOINT_FORMAT_VERSION,
    CheckpointBinding,
    CheckpointDiscardReason,
    CheckpointOwnershipError,
    CheckpointSegment,
    ExecutionMode,
)
from lectureos.application.local_asr_transcription import (
    LocalAsrResult,
    LocalAsrSegment,
    LocalAsrTranscriptionService,
)
from lectureos.application.media_import import SourceMediaRecord
from lectureos.application.provider_transcript_admission import (
    ProviderTranscriptAdmissionService,
)
from lectureos.application.transcript_source_intake import (
    TranscriptSourceIntake,
    derive_intake_identity,
)
from lectureos.execution.identities import SourceMediaId
from lectureos.infrastructure.local_asr_checkpoint_store import (
    LocalAsrCheckpointFileStore,
    default_checkpoint_root,
)
from lectureos.persistence.errors import PersistenceIdentityCollisionError

_DIGEST = "abcd" * 16
_MEDIA_ID = SourceMediaId(f"sha256:{_DIGEST}")
_INTAKE_ID = derive_intake_identity(_MEDIA_ID).value


def _binding(**overrides):
    values = dict(
        provider_result_ref="local-asr:v2:model=tiny:lang=ko:cond_prev_text=false:media=sha256:x",
        device="cpu",
        compute_type="int8",
        engine_library="faster-whisper",
        engine_version="1.2.0",
    )
    values.update(overrides)
    return CheckpointBinding(**values)


class BindingTests(unittest.TestCase):
    def test_checkpoint_id_is_deterministic(self):
        self.assertEqual(_binding().checkpoint_id, _binding().checkpoint_id)
        self.assertEqual(len(_binding().checkpoint_id), 64)

    def test_device_change_yields_a_different_key(self):
        self.assertNotEqual(_binding().checkpoint_id, _binding(device="cuda").checkpoint_id)

    def test_compute_type_change_yields_a_different_key(self):
        self.assertNotEqual(
            _binding().checkpoint_id, _binding(compute_type="float32").checkpoint_id
        )

    def test_engine_version_change_yields_a_different_key(self):
        self.assertNotEqual(
            _binding().checkpoint_id, _binding(engine_version="1.3.0").checkpoint_id
        )

    def test_provider_configuration_change_yields_a_different_key(self):
        other = _binding(
            provider_result_ref=(
                "local-asr:v2:model=tiny:lang=ko:cond_prev_text=true:media=sha256:x"
            )
        )
        self.assertNotEqual(_binding().checkpoint_id, other.checkpoint_id)

    def test_canonical_identity_ignores_device_and_compute_type(self):
        """CP-6: the asymmetry — admission identity must NOT move with operational settings."""

        from lectureos.application.local_asr_transcription import derive_provider_result_ref

        media = SourceMediaId("sha256:" + "a" * 64)
        reference = derive_provider_result_ref(media, "tiny", "ko")
        self.assertNotIn("int8", reference)
        self.assertNotIn("cpu", reference)
        # The two bindings differ, yet they share one provider-result reference.
        self.assertEqual(
            _binding(provider_result_ref=reference).provider_result_ref,
            _binding(provider_result_ref=reference, device="cuda").provider_result_ref,
        )

    def test_id_is_filesystem_safe(self):
        self.assertTrue(all(c in "0123456789abcdef" for c in _binding().checkpoint_id))

    def test_blank_binding_field_is_rejected(self):
        with self.assertRaises(ValueError):
            _binding(device="  ")


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.store = LocalAsrCheckpointFileStore(self.tempdir.name)
        self.binding = _binding()

    def tearDown(self):
        self.tempdir.cleanup()

    def _directory(self):
        return Path(self.tempdir.name) / self.binding.checkpoint_id

    def test_relative_root_is_rejected(self):
        with self.assertRaises(ValueError):
            LocalAsrCheckpointFileStore("relative/path")

    def test_default_root_is_absolute_and_outside_the_repository(self):
        root = default_checkpoint_root()
        self.assertTrue(root.is_absolute())
        self.assertNotIn("LectureOS/src", str(root))

    def test_absent_checkpoint_reports_absent(self):
        loaded = self.store.load(self.binding)
        self.assertFalse(loaded.resumable)
        self.assertIs(loaded.discard_reason, CheckpointDiscardReason.ABSENT)

    def test_round_trip_of_complete_records(self):
        self.store.begin(self.binding)
        for index in range(3):
            self.store.append(
                self.binding, CheckpointSegment(index, index * 2.0, index * 2.0 + 2.0, f"t{index}")
            )
        loaded = self.store.load(self.binding)
        self.assertTrue(loaded.resumable)
        self.assertEqual(len(loaded.segments), 3)
        self.assertEqual(loaded.resume_from, 6.0)

    def test_incomplete_tail_is_discarded(self):
        """CP-11: anything after the last newline is an interrupted write."""

        self.store.begin(self.binding)
        self.store.append(self.binding, CheckpointSegment(0, 0.0, 2.0, "complete"))
        with open(self._directory() / "segments.jsonl", "a", encoding="utf-8") as handle:
            handle.write('{"ordinal": 1, "start": 2.0, "end": 4.0, "te')  # truncated, no newline
        loaded = self.store.load(self.binding)
        self.assertTrue(loaded.resumable)
        self.assertEqual(len(loaded.segments), 1)
        self.assertEqual(loaded.resume_from, 2.0)

    def test_metadata_is_written_atomically(self):
        self.store.begin(self.binding)
        metadata = json.loads((self._directory() / "metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(metadata["checkpoint_format_version"], CHECKPOINT_FORMAT_VERSION)
        self.assertEqual(metadata["binding"], self.binding.as_payload())
        leftovers = [p for p in self._directory().iterdir() if p.name.startswith(".tmp-")]
        self.assertEqual(leftovers, [])

    def test_unreadable_metadata_is_discarded(self):
        self.store.begin(self.binding)
        self.store.append(self.binding, CheckpointSegment(0, 0.0, 2.0, "x"))
        (self._directory() / "metadata.json").write_text("{ not json", encoding="utf-8")
        self.assertIs(
            self.store.load(self.binding).discard_reason,
            CheckpointDiscardReason.UNREADABLE_METADATA,
        )

    def test_unknown_format_version_is_discarded(self):
        self.store.begin(self.binding)
        self.store.append(self.binding, CheckpointSegment(0, 0.0, 2.0, "x"))
        path = self._directory() / "metadata.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["checkpoint_format_version"] = 999
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertIs(
            self.store.load(self.binding).discard_reason,
            CheckpointDiscardReason.UNKNOWN_FORMAT_VERSION,
        )

    def test_binding_mismatch_is_discarded(self):
        self.store.begin(self.binding)
        self.store.append(self.binding, CheckpointSegment(0, 0.0, 2.0, "x"))
        path = self._directory() / "metadata.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["binding"]["compute_type"] = "float32"
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertIs(
            self.store.load(self.binding).discard_reason,
            CheckpointDiscardReason.BINDING_MISMATCH,
        )

    def test_malformed_segment_is_discarded(self):
        self.store.begin(self.binding)
        self.store.append(self.binding, CheckpointSegment(0, 0.0, 2.0, "x"))
        with open(self._directory() / "segments.jsonl", "a", encoding="utf-8") as handle:
            handle.write("this is not json\n")
        self.assertIs(
            self.store.load(self.binding).discard_reason,
            CheckpointDiscardReason.MALFORMED_SEGMENT,
        )

    def test_non_increasing_segments_are_discarded(self):
        self.store.begin(self.binding)
        self.store.append(self.binding, CheckpointSegment(0, 5.0, 9.0, "a"))
        self.store.append(self.binding, CheckpointSegment(1, 1.0, 2.0, "b"))
        self.assertIs(
            self.store.load(self.binding).discard_reason,
            CheckpointDiscardReason.NON_INCREASING_SEGMENTS,
        )

    def test_delete_removes_the_checkpoint(self):
        self.store.begin(self.binding)
        self.store.append(self.binding, CheckpointSegment(0, 0.0, 2.0, "x"))
        self.store.delete(self.binding)
        self.assertIs(self.store.load(self.binding).discard_reason, CheckpointDiscardReason.ABSENT)

    def test_age_based_collection_takes_a_caller_supplied_cutoff(self):
        """CP-21: no default TTL is invented here."""

        self.store.begin(self.binding)
        self.assertEqual(self.store.collect_older_than(time.time() - 3600), 0)
        self.assertEqual(self.store.collect_older_than(time.time() + 3600), 1)


class LockTests(unittest.TestCase):
    """CP-20 verified with real processes, because the guarantee is the OS's, not Python's."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.store = LocalAsrCheckpointFileStore(self.tempdir.name)
        self.binding = _binding()

    def tearDown(self):
        self.tempdir.cleanup()

    def test_second_owner_in_the_same_process_is_refused(self):
        with self.store.owned(self.binding):
            other = LocalAsrCheckpointFileStore(self.tempdir.name)
            with self.assertRaises(CheckpointOwnershipError):
                with other.owned(self.binding):
                    pass

    def test_ownership_is_released_on_normal_exit(self):
        with self.store.owned(self.binding):
            pass
        with self.store.owned(self.binding):
            pass  # reacquired without any stale-lock handling

    def test_ownership_is_released_when_the_owning_process_is_killed(self):
        """CP-20's whole basis: the OS releases the lock, so no heartbeat or sweep is needed."""

        script = textwrap.dedent(
            f"""
            import sys, time
            sys.path.insert(0, {str(Path(__file__).resolve().parents[1] / "src")!r})
            from lectureos.application.local_asr_checkpoint import CheckpointBinding
            from lectureos.infrastructure.local_asr_checkpoint_store import (
                LocalAsrCheckpointFileStore,
            )
            store = LocalAsrCheckpointFileStore({self.tempdir.name!r})
            binding = CheckpointBinding(**{_binding().as_payload()!r})
            with store.owned(binding):
                print("ACQUIRED", flush=True)
                time.sleep(60)
            """
        )
        child = subprocess.Popen(
            [sys.executable, "-c", script], stdout=subprocess.PIPE, text=True
        )
        try:
            self.assertEqual(child.stdout.readline().strip(), "ACQUIRED")
            with self.assertRaises(CheckpointOwnershipError):
                with self.store.owned(self.binding):
                    pass
            child.kill()
            child.wait(timeout=10)
            deadline = time.time() + 10
            while True:
                try:
                    with self.store.owned(self.binding):
                        break
                except CheckpointOwnershipError:
                    if time.time() > deadline:
                        self.fail("advisory lock was not released when the owner was killed")
                    time.sleep(0.05)
        finally:
            if child.poll() is None:
                child.kill()


# -- orchestration ---------------------------------------------------------------------------------


class _FakeQuery:
    def __init__(self, records=None):
        self._records = dict(records or {})

    def get(self, identity):
        return self._records.get(identity.value)


class _AdmissionStore:
    def __init__(self, fail=False):
        self.records = {}
        self.fail = fail

    def get(self, identity):
        return self.records.get(identity.value)

    def persist_provider_transcript_admission(
        self, *, admission, provider_result, segments, raw_transcript, result
    ):
        if self.fail:
            raise PersistenceIdentityCollisionError("injected admission failure")
        if admission.identity.value in self.records:
            raise PersistenceIdentityCollisionError("admission exists")
        self.records[admission.identity.value] = admission


class _FakeVerifier:
    def verify(self, record):
        return "/abs/lecture.bin"


class _FakeEngine:
    def __init__(self, batches=None, error=None):
        # Each call returns the next batch, so a resumed run can produce different segments.
        self.batches = list(batches or [[LocalAsrSegment(0.0, 2.0, "a"), LocalAsrSegment(2.0, 4.0, "b")]])
        self.error = error
        self.calls = []

    def transcribe(self, *, media_path, model, language, device, compute_type,
                   condition_on_previous_text, start_offset=None, on_segment=None):
        self.calls.append({"start_offset": start_offset})
        if self.error is not None:
            raise self.error
        batch = self.batches[min(len(self.calls) - 1, len(self.batches) - 1)]
        # Mirrors the real runner: each segment is surfaced as it is produced (CP-11).
        for segment in batch:
            if on_segment is not None:
                on_segment(segment)
        return LocalAsrResult("faster-whisper", model, language or "ko", tuple(batch))


def _service(store, engine, *, admissions=None, checkpoints=None):
    intakes = _FakeQuery(
        {_INTAKE_ID: TranscriptSourceIntake(TranscriptSourceIntakeId(_INTAKE_ID), _MEDIA_ID)}
    )
    media = _FakeQuery(
        {
            _MEDIA_ID.value: SourceMediaRecord(
                identity=_MEDIA_ID,
                fingerprint_algorithm="sha256",
                fingerprint_digest=_DIGEST,
                byte_length=10,
                observed_source_path="/abs/lecture.bin",
            )
        }
    )
    admissions = admissions if admissions is not None else store
    admission_service = ProviderTranscriptAdmissionService(
        intakes, media, admissions, admissions
    )
    return LocalAsrTranscriptionService(
        intakes, media, admissions, admission_service, _FakeVerifier(), engine,
        checkpoint_store=checkpoints, engine_version="1.2.0",
    )


class OrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.checkpoints = LocalAsrCheckpointFileStore(self.tempdir.name)

    def tearDown(self):
        self.tempdir.cleanup()

    def _bindings(self):
        return [
            CheckpointBinding(**json.loads((p / "metadata.json").read_text())["binding"])
            for p in Path(self.tempdir.name).iterdir()
            if (p / "metadata.json").is_file()
        ]

    def test_fresh_run_writes_a_checkpoint_and_deletes_it_on_success(self):
        store = _AdmissionStore()
        engine = _FakeEngine()
        service = _service(store, engine, checkpoints=self.checkpoints)
        result = service.transcribe(intake_id=_INTAKE_ID, model="tiny", language="ko")
        self.assertIs(result.mode, ExecutionMode.FRESH)
        self.assertIsNotNone(result.checkpoint_identity)
        # CP-17: the canonical result exists, so the checkpoint is gone.
        self.assertEqual(self._bindings(), [])

    def test_canonical_reuse_never_consults_the_checkpoint(self):
        """CP-8 step 1 without exception."""

        store = _AdmissionStore()
        engine = _FakeEngine()
        service = _service(store, engine, checkpoints=self.checkpoints)
        service.transcribe(intake_id=_INTAKE_ID, model="tiny", language="ko")
        again = service.transcribe(intake_id=_INTAKE_ID, model="tiny", language="ko")
        self.assertIs(again.mode, ExecutionMode.REUSED)
        self.assertFalse(again.executed)
        self.assertIsNone(again.checkpoint_identity)
        self.assertEqual(len(engine.calls), 1)

    def test_admission_failure_keeps_the_checkpoint_and_writes_no_repository_row(self):
        store = _AdmissionStore(fail=True)
        engine = _FakeEngine()
        service = _service(store, engine, checkpoints=self.checkpoints)
        with self.assertRaises(Exception):
            service.transcribe(intake_id=_INTAKE_ID, model="tiny", language="ko")
        self.assertEqual(store.records, {})            # CP-14: no repository write
        self.assertEqual(len(self._bindings()), 1)     # CP-18: checkpoint retained

    def test_engine_failure_keeps_the_checkpoint(self):
        from lectureos.application.local_asr_transcription import LocalAsrEngineError

        store = _AdmissionStore()
        service = _service(
            store, _FakeEngine(error=LocalAsrEngineError("boom")), checkpoints=self.checkpoints
        )
        with self.assertRaises(LocalAsrEngineError):
            service.transcribe(intake_id=_INTAKE_ID, model="tiny", language="ko")
        self.assertEqual(store.records, {})
        self.assertEqual(len(self._bindings()), 1)

    def test_resume_adopts_prior_segments_and_offsets_the_engine(self):
        """CP-12/CP-13: continue from the last complete segment; never regenerate it."""

        store = _AdmissionStore(fail=True)
        engine = _FakeEngine(batches=[[LocalAsrSegment(0.0, 2.0, "a"), LocalAsrSegment(2.0, 4.0, "b")]])
        service = _service(store, engine, checkpoints=self.checkpoints)
        with self.assertRaises(Exception):
            service.transcribe(intake_id=_INTAKE_ID, model="tiny", language="ko")

        store2 = _AdmissionStore()
        engine2 = _FakeEngine(batches=[[LocalAsrSegment(4.0, 6.0, "c")]])
        service2 = _service(store2, engine2, checkpoints=self.checkpoints)
        result = service2.transcribe(intake_id=_INTAKE_ID, model="tiny", language="ko")
        self.assertIs(result.mode, ExecutionMode.RESUMED)
        self.assertEqual(result.resumed_from, 4.0)
        self.assertEqual(engine2.calls[0]["start_offset"], 4.0)
        # Two adopted plus one new, assembled and admitted as one whole.
        self.assertEqual(result.admission.segment_count, 3)

    def test_force_fresh_discards_the_checkpoint(self):
        store = _AdmissionStore(fail=True)
        service = _service(store, _FakeEngine(), checkpoints=self.checkpoints)
        with self.assertRaises(Exception):
            service.transcribe(intake_id=_INTAKE_ID, model="tiny", language="ko")
        store2 = _AdmissionStore()
        engine2 = _FakeEngine()
        service2 = _service(store2, engine2, checkpoints=self.checkpoints)
        result = service2.transcribe(
            intake_id=_INTAKE_ID, model="tiny", language="ko", force_fresh=True
        )
        self.assertIs(result.mode, ExecutionMode.FRESH)
        self.assertIsNone(engine2.calls[0]["start_offset"])

    def test_corrupt_checkpoint_falls_back_to_fresh_with_a_disclosed_reason(self):
        store = _AdmissionStore(fail=True)
        service = _service(store, _FakeEngine(), checkpoints=self.checkpoints)
        with self.assertRaises(Exception):
            service.transcribe(intake_id=_INTAKE_ID, model="tiny", language="ko")
        directory = Path(self.tempdir.name) / self._bindings()[0].checkpoint_id
        (directory / "segments.jsonl").write_text("garbage\n", encoding="utf-8")

        store2 = _AdmissionStore()
        engine2 = _FakeEngine()
        service2 = _service(store2, engine2, checkpoints=self.checkpoints)
        result = service2.transcribe(intake_id=_INTAKE_ID, model="tiny", language="ko")
        self.assertIs(result.mode, ExecutionMode.FRESH)
        self.assertIs(
            result.checkpoint_discard_reason, CheckpointDiscardReason.MALFORMED_SEGMENT
        )
        self.assertIsNone(engine2.calls[0]["start_offset"])

    def test_no_checkpoint_store_keeps_the_released_behaviour(self):
        """Without a store the adapter behaves exactly as before, and always fresh."""

        store = _AdmissionStore()
        engine = _FakeEngine()
        service = _service(store, engine, checkpoints=None)
        result = service.transcribe(intake_id=_INTAKE_ID, model="tiny", language="ko")
        self.assertIs(result.mode, ExecutionMode.FRESH)
        self.assertIsNone(result.checkpoint_identity)
        self.assertIsNone(engine.calls[0]["start_offset"])

    def test_checkpoint_never_creates_canonical_rows_before_admission(self):
        """CP-2/CP-14 and L-10: repository state is untouched while a checkpoint exists."""

        store = _AdmissionStore(fail=True)
        service = _service(store, _FakeEngine(), checkpoints=self.checkpoints)
        with self.assertRaises(Exception):
            service.transcribe(intake_id=_INTAKE_ID, model="tiny", language="ko")
        self.assertEqual(store.records, {})
        self.assertEqual(len(self._bindings()), 1)


if __name__ == "__main__":
    unittest.main()


class StreamingTests(unittest.TestCase):
    """CP-11: the checkpoint is written during the run, not after it."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.checkpoints = LocalAsrCheckpointFileStore(self.tempdir.name)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_segments_are_recorded_before_the_engine_returns(self):
        observed = []

        class _StreamingEngine:
            def transcribe(self, *, media_path, model, language, device, compute_type,
                           condition_on_previous_text, start_offset=None, on_segment=None):
                produced = []
                for index in range(3):
                    segment = LocalAsrSegment(index * 2.0, index * 2.0 + 2.0, f"s{index}")
                    if on_segment is not None:
                        on_segment(segment)
                    # How many complete records exist on disk at this instant?
                    directories = [
                        p for p in Path(self.root).iterdir() if (p / "segments.jsonl").is_file()
                    ]
                    written = sum(
                        len((p / "segments.jsonl").read_text(encoding="utf-8").splitlines())
                        for p in directories
                    )
                    observed.append(written)
                    produced.append(segment)
                return LocalAsrResult("faster-whisper", model, language or "ko", tuple(produced))

        engine = _StreamingEngine()
        engine.root = self.tempdir.name
        store = _AdmissionStore()
        service = _service(store, engine, checkpoints=self.checkpoints)
        service.transcribe(intake_id=_INTAKE_ID, model="tiny", language="ko")
        # A durable record exists after each segment — not only once the engine finished.
        self.assertEqual(observed, [1, 2, 3])


class CompositionWiringTests(unittest.TestCase):
    """The composition root must actually attach the store — a unit-tested service does not prove it.

    The first cut of this milestone wired every layer except this one, and every service-level test
    passed against it: the defect only surfaced when a real run left an empty checkpoint directory.
    """

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tempdir.cleanup()

    def _service(self, **kwargs):
        from lectureos.composition import compose_sqlite_local_asr_transcription_service
        from lectureos.persistence import initialize_sqlite_database

        connection = initialize_sqlite_database(Path(self.tempdir.name) / "t.sqlite3")
        self.addCleanup(connection.close)
        return compose_sqlite_local_asr_transcription_service(
            connection, engine_runner=object(), **kwargs
        )

    def test_checkpoint_root_attaches_a_store(self):
        service = self._service(checkpoint_root=str(Path(self.tempdir.name) / "scratch"))
        self.assertIsNotNone(service._checkpoints)

    def test_omitting_the_root_disables_checkpointing(self):
        """CP-10: without a root every run is fresh, which is always a correct outcome."""

        self.assertIsNone(self._service()._checkpoints)

    def test_engine_version_reaches_the_binding(self):
        """CP-5: an 'unknown' version would silently merge checkpoints across engine upgrades."""

        service = self._service(checkpoint_root=str(Path(self.tempdir.name) / "scratch"))
        try:
            import faster_whisper  # noqa: F401
        except ImportError:
            self.skipTest("faster-whisper is not installed in this environment")
        self.assertNotEqual(service._engine_version, "unknown")


class CliWiringTests(unittest.TestCase):
    """The CLI must forward the operational options; an unforwarded flag is silently inert."""

    def test_cli_forwards_checkpoint_options(self):
        import inspect

        import lectureos.local_asr_cli as cli

        source = inspect.getsource(cli.main)
        self.assertIn("checkpoint_root=args.checkpoint_root", source)
        self.assertIn("force_fresh=args.force_fresh", source)

    def test_cli_declares_no_retention_default(self):
        """CP-21: the retention duration is operational configuration, not a product number."""

        import lectureos.local_asr_cli as cli

        help_text = cli._parser().format_help()
        for forbidden in ("--ttl", "--retention", "--max-age"):
            self.assertNotIn(forbidden, help_text)


class RepresentationToleranceTests(unittest.TestCase):
    """The PATCH-0039 boundary shape must not silently turn every long resume into a fresh run."""

    def test_representation_noise_is_not_a_non_increasing_checkpoint(self):
        from lectureos.application.local_asr_checkpoint import segments_are_increasing

        segments = [
            CheckpointSegment(0, 3127.34, 3129.1000000000004, "a"),
            CheckpointSegment(1, 3129.1, 3133.42, "b"),
        ]
        self.assertTrue(segments_are_increasing(segments))

    def test_a_real_overlap_is_still_rejected(self):
        from lectureos.application.local_asr_checkpoint import segments_are_increasing

        segments = [
            CheckpointSegment(0, 0.0, 2.0, "a"),
            CheckpointSegment(1, 0.5, 3.0, "b"),
        ]
        self.assertFalse(segments_are_increasing(segments))

    def test_out_of_order_ordinals_are_still_rejected(self):
        from lectureos.application.local_asr_checkpoint import segments_are_increasing

        self.assertFalse(
            segments_are_increasing(
                [CheckpointSegment(1, 0.0, 2.0, "a"), CheckpointSegment(0, 2.0, 4.0, "b")]
            )
        )

    def test_noise_bearing_checkpoint_resumes_rather_than_restarting(self):
        """End to end: a store round-trip over the real boundary shape stays resumable."""

        with tempfile.TemporaryDirectory() as directory:
            store = LocalAsrCheckpointFileStore(directory)
            binding = _binding()
            store.begin(binding)
            store.append(binding, CheckpointSegment(0, 3127.34, 3129.1000000000004, "a"))
            store.append(binding, CheckpointSegment(1, 3129.1, 3133.42, "b"))
            loaded = store.load(binding)
            self.assertTrue(loaded.resumable)
            self.assertEqual(loaded.resume_from, 3133.42)
