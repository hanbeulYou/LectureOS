import os
import tempfile
import unittest
from unittest.mock import patch
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from lectureos.execution.identities import ArtifactId, WorkingContextReference
from lectureos.export.identities import (
    ExportRequestId,
    MaterializationRequestId,
    MaterializationResultId,
    SystemRequesterReference,
)
from lectureos.export.materialization import (
    LocalArtifactMaterializationService,
    _AtomicLocalFileWriter,
)
from lectureos.export.models import (
    ExportArtifact,
    ExportFormat,
    ExportRequesterKind,
    ExportRequesterReference,
    ExportTargetMode,
    LocalBomPolicy,
    LocalEncodingPolicy,
    LocalNewlinePolicy,
    LocalOverwritePolicy,
)
from lectureos.subtitle.identities import (
    FinalSubtitleSelectionId,
    SubtitleCueId,
    SubtitleRevisionId,
    SubtitleValidationId,
)


class _ExportQuery:
    def __init__(self, artifact):
        self.artifact = artifact

    def get_export_artifact(self, identity):
        return (
            self.artifact
            if self.artifact is not None and self.artifact.identity == identity
            else None
        )


class _FailingWriter(_AtomicLocalFileWriter):
    def write(self, final_path, content, overwrite_policy):
        raise OSError("injected writer failure")


class LocalArtifactMaterializationTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir="/private/tmp")
        self.directory = Path(self.temporary.name)
        self.artifact = ExportArtifact(
            identity=ArtifactId("artifact-1"),
            request_id=ExportRequestId("export-request-1"),
            format=ExportFormat.SRT,
            target_mode=ExportTargetMode.ACTIVE_FINAL,
            working_context=WorkingContextReference("context-1"),
            final_selection_id=FinalSubtitleSelectionId("final-1"),
            revision_id=SubtitleRevisionId("revision-1"),
            final_validation_id=SubtitleValidationId("validation-1"),
            latest_validation_id=SubtitleValidationId("validation-1"),
            requester=self._requester("exporter"),
            cue_ids=(SubtitleCueId("cue-1"),),
            content="1\n00:00:00,000 --> 00:00:01,000\n한글 English 123!\n둘째 줄\n",
            serializer_version="srt-v1",
            created_at=datetime.now(timezone.utc),
        )
        self.service = LocalArtifactMaterializationService(
            _ExportQuery(self.artifact)
        )

    def tearDown(self):
        self.temporary.cleanup()

    def test_materializes_utf8_srt_and_records_result(self):
        before = self.artifact
        result = self._materialize(filename="lecture-ko")
        path = self.directory / "lecture-ko.srt"
        content = path.read_bytes()
        self.assertEqual(self.artifact.content.encode("utf-8"), content)
        self.assertFalse(content.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn(b"\r\n", content)
        self.assertEqual(len(content), result.byte_size)
        self.assertEqual(str(path), result.final_path)
        self.assertEqual(LocalEncodingPolicy.UTF8, result.encoding_policy)
        self.assertEqual(LocalBomPolicy.NONE, result.bom_policy)
        self.assertEqual(LocalNewlinePolicy.LF, result.newline_policy)
        self.assertIs(before, self.artifact)
        self.assertEqual(1, len(self.service.requests.all()))
        self.assertEqual(1, len(self.service.results.all()))

    def test_filename_contract(self):
        allowed = {
            "lecture-no-extension": "lecture-no-extension.srt",
            "lecture-lower.srt": "lecture-lower.srt",
            "lecture-upper.SRT": "lecture-upper.SRT",
            "lecture-mixed.SrT": "lecture-mixed.SrT",
            "lecture.ko.srt": "lecture.ko.srt",
        }
        for index, (requested, expected) in enumerate(allowed.items()):
            with self.subTest(requested=requested):
                result = self._materialize(
                    request=f"allowed-request-{index}",
                    result=f"allowed-result-{index}",
                    filename=requested,
                )
                self.assertEqual(str(self.directory / expected), result.final_path)
        rejected = (
            "",
            "   ",
            ".",
            "..",
            ".hidden.srt",
            "lecture.txt",
            "lecture.srt.txt",
            "nested/lecture.srt",
            "nested\\lecture.srt",
            "/absolute.srt",
            " lecture.srt",
            "lecture.srt ",
            "bad\x00name.srt",
        )
        for index, requested in enumerate(rejected):
            with self.subTest(requested=requested):
                with self.assertRaises((TypeError, ValueError)):
                    self._materialize(
                        request=f"rejected-request-{index}",
                        result=f"rejected-result-{index}",
                        filename=requested,
                    )

    def test_directory_must_be_absolute_existing_real_directory(self):
        invalid = (
            Path("relative"),
            self.directory / "missing",
        )
        file_path = self.directory / "not-directory"
        file_path.write_text("x")
        invalid += (file_path,)
        symlink_path = self.directory.parent / f"{self.directory.name}-link"
        symlink_path.symlink_to(self.directory, target_is_directory=True)
        self.addCleanup(symlink_path.unlink)
        invalid += (symlink_path,)
        for index, directory in enumerate(invalid):
            with self.subTest(directory=directory):
                with self.assertRaises((ValueError, PermissionError)):
                    self._materialize(
                        request=f"directory-request-{index}",
                        result=f"directory-result-{index}",
                        directory=directory,
                    )
        self.assertFalse((self.directory / "missing").exists())
        self.assertFalse(self.service.requests.all())
        self.assertFalse(self.service.results.all())

    def test_existing_regular_file_obeys_overwrite_policy(self):
        path = self.directory / "lecture.srt"
        path.write_bytes(b"original")
        with self.assertRaises(FileExistsError):
            self._materialize()
        self.assertEqual(b"original", path.read_bytes())
        result = self._materialize(
            request="replace-request",
            result="replace-result",
            policy=LocalOverwritePolicy.REPLACE_EXISTING,
        )
        self.assertEqual(self.artifact.content.encode(), path.read_bytes())
        self.assertEqual(LocalOverwritePolicy.REPLACE_EXISTING, result.overwrite_policy)

    def test_symlink_and_non_regular_targets_are_rejected(self):
        source = self.directory / "source"
        source.write_bytes(b"original")
        target = self.directory / "lecture.srt"
        target.symlink_to(source)
        for policy in LocalOverwritePolicy:
            with self.subTest(policy=policy):
                with self.assertRaisesRegex(ValueError, "regular file"):
                    self._materialize(
                        request=f"symlink-request-{policy.value}",
                        result=f"symlink-result-{policy.value}",
                        policy=policy,
                    )
        self.assertEqual(b"original", source.read_bytes())
        target.unlink()
        target.mkdir()
        with self.assertRaisesRegex(ValueError, "regular file"):
            self._materialize(request="directory-target", result="directory-result")

    def test_same_request_is_idempotent_without_filesystem_revalidation(self):
        first = self._materialize()
        path = Path(first.final_path)
        path.unlink()
        second = self._materialize()
        self.assertIs(first, second)
        self.assertFalse(path.exists())
        self.assertEqual(1, len(self.service.requests.all()))
        self.assertEqual(1, len(self.service.results.all()))
        path.write_bytes(b"external content")
        third = self._materialize()
        self.assertIs(first, third)
        self.assertEqual(b"external content", path.read_bytes())

        path.unlink()
        self.directory.rmdir()
        fourth = self._materialize()
        self.assertIs(first, fourth)

    def test_same_request_with_different_inputs_is_collision(self):
        self._materialize()
        changes = (
            {"artifact": ArtifactId("different")},
            {"filename": "different.srt"},
            {"policy": LocalOverwritePolicy.REPLACE_EXISTING},
            {"requester": self._requester("different")},
        )
        for change in changes:
            with self.subTest(change=change):
                with self.assertRaisesRegex(ValueError, "identity collision"):
                    self._materialize(**change)

    def test_new_request_rematerializes_same_artifact(self):
        first = self._materialize(filename="first")
        second = self._materialize(
            request="second-request", result="second-result", filename="second"
        )
        self.assertNotEqual(first.identity, second.identity)
        self.assertEqual(first.artifact_id, second.artifact_id)
        self.assertEqual(
            Path(first.final_path).read_bytes(), Path(second.final_path).read_bytes()
        )
        self.assertEqual(2, len(self.service.list_materializations_for_artifact(
            self.artifact.identity
        )))
        self.assertEqual(
            (first,), self.service.list_materializations_for_path(first.final_path)
        )

    def test_unsupported_artifacts_fail_before_side_effects(self):
        variants = (
            replace(self.artifact, serializer_version="srt-v2"),
            replace(self.artifact, content=""),
        )
        bytes_artifact = replace(self.artifact)
        object.__setattr__(bytes_artifact, "content", b"bytes")
        variants += (bytes_artifact,)
        for index, artifact in enumerate(variants):
            with self.subTest(index=index):
                service = LocalArtifactMaterializationService(_ExportQuery(artifact))
                with self.assertRaises((TypeError, ValueError)):
                    self._materialize(
                        request=f"invalid-request-{index}",
                        result=f"invalid-result-{index}",
                        service=service,
                    )
                self.assertFalse(service.requests.all())
                self.assertFalse(service.results.all())
        missing = LocalArtifactMaterializationService(_ExportQuery(None))
        with self.assertRaises(KeyError):
            self._materialize(artifact=ArtifactId("missing"), service=missing)

    def test_writer_failure_has_no_file_or_records(self):
        service = LocalArtifactMaterializationService(
            _ExportQuery(self.artifact), writer=_FailingWriter()
        )
        with self.assertRaisesRegex(OSError, "injected"):
            self._materialize(service=service)
        self.assertFalse((self.directory / "lecture.srt").exists())
        self.assertFalse(service.requests.all())
        self.assertFalse(service.results.all())

    def test_atomic_commit_failures_clean_temporary_files_and_preserve_target(self):
        target = self.directory / "lecture.srt"
        with patch("lectureos.export.materialization.os.link", side_effect=OSError("link")):
            with self.assertRaisesRegex(OSError, "link"):
                self._materialize()
        self.assertFalse(target.exists())
        self.assertFalse(tuple(self.directory.glob(".*.tmp")))

        target.write_bytes(b"original")
        with patch(
            "lectureos.export.materialization.os.replace",
            side_effect=OSError("replace"),
        ):
            with self.assertRaisesRegex(OSError, "replace"):
                self._materialize(
                    request="replace-failure-request",
                    result="replace-failure-result",
                    policy=LocalOverwritePolicy.REPLACE_EXISTING,
                )
        self.assertEqual(b"original", target.read_bytes())
        self.assertFalse(tuple(self.directory.glob(".*.tmp")))
        self.assertFalse(self.service.requests.all())
        self.assertFalse(self.service.results.all())

    def test_unexpected_request_persistence_failure_removes_new_file(self):
        def fail(_record):
            raise RuntimeError("request persistence failed")

        self.service.requests.save = fail
        with self.assertRaisesRegex(RuntimeError, "persistence"):
            self._materialize()
        self.assertFalse((self.directory / "lecture.srt").exists())
        self.assertFalse(self.service.results.all())

    def test_unexpected_result_failure_preserves_request_and_replacement(self):
        path = self.directory / "lecture.srt"
        path.write_bytes(b"original")

        def fail(_record):
            raise RuntimeError("result persistence failed")

        self.service.results.save = fail
        with self.assertRaisesRegex(RuntimeError, "persistence"):
            self._materialize(policy=LocalOverwritePolicy.REPLACE_EXISTING)
        self.assertEqual(self.artifact.content.encode(), path.read_bytes())
        self.assertEqual(1, len(self.service.requests.all()))
        self.assertFalse(self.service.results.all())

    def test_unexpected_result_failure_removes_new_file_but_keeps_request(self):
        def fail(_record):
            raise RuntimeError("result persistence failed")

        self.service.results.save = fail
        with self.assertRaisesRegex(RuntimeError, "persistence"):
            self._materialize()
        self.assertFalse((self.directory / "lecture.srt").exists())
        self.assertEqual(1, len(self.service.requests.all()))
        self.assertFalse(self.service.results.all())

    def test_result_identity_collision_precedes_file_write(self):
        first = self._materialize(filename="first")
        with self.assertRaisesRegex(ValueError, "identity already exists"):
            self._materialize(
                request="second-request", result=first.identity.value, filename="second"
            )
        self.assertFalse((self.directory / "second.srt").exists())

    def _materialize(
        self,
        *,
        request="materialization-request",
        result="materialization-result",
        artifact=None,
        requester=None,
        directory=None,
        filename="lecture.srt",
        policy=LocalOverwritePolicy.FAIL_IF_EXISTS,
        service=None,
    ):
        return (service or self.service).materialize_export_artifact_to_local_file(
            request_id=MaterializationRequestId(request),
            result_id=MaterializationResultId(result),
            artifact_id=artifact or self.artifact.identity,
            requester=requester or self._requester("materializer"),
            target_directory=directory or self.directory,
            requested_filename=filename,
            overwrite_policy=policy,
        )

    @staticmethod
    def _requester(value):
        return ExportRequesterReference(
            kind=ExportRequesterKind.SYSTEM,
            system_reference=SystemRequesterReference(value),
        )


if __name__ == "__main__":
    unittest.main()
