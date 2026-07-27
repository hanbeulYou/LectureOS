"""Application tests for Effective-Source Subtitle Review Preparation (GOAL-014)."""

import tempfile
import unittest
from pathlib import Path

from lectureos.application.correction_candidate_admission import (
    build_correction_candidate_input,
)
from lectureos.application.effective_subtitle_review_preparation import (
    CandidateGraphIntegrityError,
    EffectiveSubtitleReviewPreparationError,
    EffectiveSubtitleReviewPreparationService,
    EffectiveSubtitleReviewSubject,
    PREPARATION_KIND,
    PREPARATION_VERSION,
    ReviewSubjectConflictError,
    ReviewSubjectCurrentness,
    derive_candidate_graph_fingerprint,
    derive_preparation_key,
    derive_review_subject_identity,
)
from lectureos.application.effective_transcript_consumption import ConsumptionCurrentness
from lectureos.application.identities import EffectiveSubtitleCandidateId
from lectureos.application.provider_transcript_admission import (
    build_provider_transcript_document,
)
from lectureos.composition import (
    compose_sqlite_corrected_revision_generation_service,
    compose_sqlite_corrected_revision_selection_service,
    compose_sqlite_correction_candidate_admission_service,
    compose_sqlite_correction_candidate_decision_service,
    compose_sqlite_current_raw_transcript_selection_service,
    compose_sqlite_effective_subtitle_generation_service,
    compose_sqlite_effective_subtitle_review_preparation_service,
    compose_sqlite_media_import_service,
    compose_sqlite_provider_transcript_admission_service,
    compose_sqlite_transcript_source_intake_service,
)
from lectureos.persistence import (
    SQLiteEffectiveSubtitleReviewSubjectCommandPersistence,
    SQLiteEffectiveSubtitleReviewSubjectRepository,
    SQLiteRawTranscriptRepository,
    SQLiteTranscriptSegmentRepository,
    initialize_sqlite_database,
)
from lectureos.transcript.identities import TranscriptId

_CAND = EffectiveSubtitleCandidateId("subtitle-effective-candidate:" + "a" * 64)
_CAND2 = EffectiveSubtitleCandidateId("subtitle-effective-candidate:" + "b" * 64)


class IdentityTests(unittest.TestCase):
    def test_identity_deterministic_and_input_sensitive(self):
        a = derive_review_subject_identity(_CAND, "0" * 64)
        self.assertEqual(a, derive_review_subject_identity(_CAND, "0" * 64))
        self.assertTrue(a.value.startswith("subtitle-effective-review-subject:"))
        self.assertNotEqual(a, derive_review_subject_identity(_CAND2, "0" * 64))
        self.assertNotEqual(a, derive_review_subject_identity(_CAND, "1" * 64))

    def test_preparation_key_deterministic(self):
        self.assertEqual(
            derive_preparation_key(_CAND),
            f"{PREPARATION_KIND}:v{PREPARATION_VERSION}:{_CAND.value}",
        )

    def test_model_enforces_contract_and_derivations(self):
        fingerprint = "0" * 64
        subject = EffectiveSubtitleReviewSubject(
            identity=derive_review_subject_identity(_CAND, fingerprint),
            candidate_id=_CAND,
            candidate_graph_fingerprint=fingerprint,
            preparation_kind=PREPARATION_KIND,
            preparation_version=PREPARATION_VERSION,
            preparation_key=derive_preparation_key(_CAND),
        )
        self.assertEqual(subject.candidate_id, _CAND)
        with self.assertRaises(ValueError):  # wrong identity
            EffectiveSubtitleReviewSubject(
                identity=derive_review_subject_identity(_CAND2, fingerprint),
                candidate_id=_CAND,
                candidate_graph_fingerprint=fingerprint,
                preparation_kind=PREPARATION_KIND,
                preparation_version=PREPARATION_VERSION,
                preparation_key=derive_preparation_key(_CAND),
            )
        with self.assertRaises(ValueError):  # unsupported version
            EffectiveSubtitleReviewSubject(
                identity=derive_review_subject_identity(_CAND, fingerprint),
                candidate_id=_CAND,
                candidate_graph_fingerprint=fingerprint,
                preparation_kind=PREPARATION_KIND,
                preparation_version=2,
                preparation_key=derive_preparation_key(_CAND),
            )
        with self.assertRaises(ValueError):  # wrong key
            EffectiveSubtitleReviewSubject(
                identity=derive_review_subject_identity(_CAND, fingerprint),
                candidate_id=_CAND,
                candidate_graph_fingerprint=fingerprint,
                preparation_kind=PREPARATION_KIND,
                preparation_version=PREPARATION_VERSION,
                preparation_key=derive_preparation_key(_CAND2),
            )


class EffectiveSubtitleReviewPreparationServiceTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.base = Path(self.tempdir.name)
        self.connection = initialize_sqlite_database(self.base / "lectureos.sqlite3")
        source = self.base / "a.bin"
        source.write_bytes(b"review-prep \x00\x01")
        media = compose_sqlite_media_import_service(self.connection).import_media(str(source)).record
        self.intake = compose_sqlite_transcript_source_intake_service(self.connection).admit(
            media.identity.value
        ).intake.identity.value
        self.provider = compose_sqlite_provider_transcript_admission_service(self.connection)
        self.raw_selection = compose_sqlite_current_raw_transcript_selection_service(self.connection)
        self.decisions = compose_sqlite_correction_candidate_decision_service(self.connection)
        self.selection = compose_sqlite_corrected_revision_selection_service(self.connection)
        self.generation = compose_sqlite_effective_subtitle_generation_service(self.connection)
        self.preparation = compose_sqlite_effective_subtitle_review_preparation_service(
            self.connection
        )

    def tearDown(self):
        try:
            self.connection.close()
        except Exception:
            pass
        self.tempdir.cleanup()

    def _admit_raw(self, ref: str, texts=("원본 하나", "원본 둘")) -> str:
        return self.provider.admit(
            intake_id=self.intake,
            document=build_provider_transcript_document(
                {"provider": "fake", "model": "tiny", "language": "ko",
                 "provider_result_ref": ref,
                 "segments": [
                     {"start": float(i), "end": float(i) + 1.0, "text": text}
                     for i, text in enumerate(texts)
                 ]}
            ),
        ).admission.raw_transcript_id.value

    def _raw_candidate(self):
        raw = self._admit_raw("A")
        self.raw_selection.select(self.intake, raw)
        return raw, self.generation.generate(intake_id=self.intake).candidate

    def _corrected_candidate(self, raw):
        segment = SQLiteRawTranscriptRepository(self.connection).get(
            TranscriptId(raw)
        ).segment_ids[0]
        text = SQLiteTranscriptSegmentRepository(self.connection).get(segment).text
        candidate = compose_sqlite_correction_candidate_admission_service(self.connection).admit(
            intake_id=self.intake,
            candidate=build_correction_candidate_input(
                {"raw_transcript_id": raw, "segment_id": segment.value,
                 "candidate_ref": "c1", "source_type": "manual", "source_reference": "human",
                 "proposed_text": "교정", "source_text_snapshot": text, "rationale": "fix"}
            ),
        ).candidate.identity.value
        self.decisions.decide(candidate_id=candidate, kind="accept", reviewer="r:kim")
        revision = compose_sqlite_corrected_revision_generation_service(self.connection).generate(
            candidate_id=candidate
        ).revision.identity.value
        self.selection.select_revision(revision_id=revision, reviewer="s:kim")
        return candidate, self.generation.generate(intake_id=self.intake).candidate

    def test_prepare_raw_candidate_binds_exact_graph(self):
        _, candidate = self._raw_candidate()
        result = self.preparation.prepare_review(candidate_id=candidate.identity.value)
        self.assertEqual(result.outcome.value, "created")
        self.assertEqual(result.subject.candidate_id, candidate.identity)
        cues = self.generation.cues(candidate.identity.value)
        self.assertEqual(
            result.subject.candidate_graph_fingerprint,
            derive_candidate_graph_fingerprint(candidate, cues),
        )
        self.assertIs(
            result.status.review_subject_currentness, ReviewSubjectCurrentness.CURRENT
        )
        self.assertIs(
            result.status.candidate_source_currentness, ConsumptionCurrentness.CURRENT
        )

    def test_prepare_corrected_candidate_distinct_subject(self):
        raw, raw_candidate = self._raw_candidate()
        r1 = self.preparation.prepare_review(candidate_id=raw_candidate.identity.value)
        _, corrected_candidate = self._corrected_candidate(raw)
        r2 = self.preparation.prepare_review(candidate_id=corrected_candidate.identity.value)
        self.assertNotEqual(r1.subject.identity, r2.subject.identity)
        self.assertEqual(r2.subject.candidate_id, corrected_candidate.identity)
        self.assertEqual(
            r2.candidate.parent_raw_transcript_id.value, raw
        )  # Raw parent lineage reachable through the bound candidate

    def test_unknown_candidate_rejected(self):
        with self.assertRaises(EffectiveSubtitleReviewPreparationError):
            self.preparation.prepare_review(
                candidate_id="subtitle-effective-candidate:" + "0" * 64
            )
        with self.assertRaises(EffectiveSubtitleReviewPreparationError):
            self.preparation.prepare_review(candidate_id="not-a-candidate")

    def test_identical_replay_reuses_without_duplicates(self):
        _, candidate = self._raw_candidate()
        first = self.preparation.prepare_review(candidate_id=candidate.identity.value)
        second = self.preparation.prepare_review(candidate_id=candidate.identity.value)
        self.assertEqual(second.outcome.value, "reused")
        self.assertEqual(first.subject, second.subject)
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM subtitle_effective_review_subjects"
            ).fetchone()[0],
            1,
        )

    def test_raw_round_trip_reuses_original_subject(self):
        raw, raw_candidate = self._raw_candidate()
        r1 = self.preparation.prepare_review(candidate_id=raw_candidate.identity.value)
        self._corrected_candidate(raw)
        self.selection.select_raw_fallback(intake_id=self.intake, reviewer="s:kim")
        regenerated = self.generation.generate(intake_id=self.intake).candidate
        self.assertEqual(regenerated.identity, raw_candidate.identity)
        again = self.preparation.prepare_review(candidate_id=regenerated.identity.value)
        self.assertEqual(again.outcome.value, "reused")
        self.assertEqual(again.subject.identity, r1.subject.identity)

    def test_same_content_different_candidate_distinct_subjects(self):
        _, c1 = self._raw_candidate()
        r1 = self.preparation.prepare_review(candidate_id=c1.identity.value)
        raw2 = self._admit_raw("B")  # byte-identical content, distinct entity
        self.raw_selection.select(self.intake, raw2)
        c2 = self.generation.generate(intake_id=self.intake).candidate
        r2 = self.preparation.prepare_review(candidate_id=c2.identity.value)
        self.assertNotEqual(c1.identity, c2.identity)
        self.assertNotEqual(r1.subject.identity, r2.subject.identity)

    def test_near_concurrent_identical_preparation_converges(self):
        _, candidate = self._raw_candidate()
        self.preparation.prepare_review(candidate_id=candidate.identity.value)

        class _RacingView:
            def __init__(self, inner):
                self._inner = inner
                self._missed = False

            def get(self, identity):
                if not self._missed:
                    self._missed = True
                    return None
                return self._inner.get(identity)

            def get_for_candidate(self, candidate_id):
                return self._inner.get_for_candidate(candidate_id)

        racing = EffectiveSubtitleReviewPreparationService(
            self.generation,
            _RacingView(SQLiteEffectiveSubtitleReviewSubjectRepository(self.connection)),
            SQLiteEffectiveSubtitleReviewSubjectCommandPersistence(self.connection),
        )
        result = racing.prepare_review(candidate_id=candidate.identity.value)
        self.assertEqual(result.outcome.value, "reused")
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM subtitle_effective_review_subjects"
            ).fetchone()[0],
            1,
        )

    def test_divergent_payload_for_same_anchor_is_explicit_conflict(self):
        _, candidate = self._raw_candidate()
        self.preparation.prepare_review(candidate_id=candidate.identity.value)
        # A self-consistent but divergent stored subject occupying the same replay anchor: the
        # new preparation misses by identity, collides on the anchor, and must refuse to
        # converge because the structural payload disagrees.
        tampered = derive_review_subject_identity(candidate.identity, "f" * 64)
        self.connection.execute("PRAGMA foreign_keys = OFF")
        try:
            self.connection.execute(
                "UPDATE subtitle_effective_review_subjects "
                "SET identity = ?, candidate_graph_fingerprint = ?",
                (tampered.value, "f" * 64),
            )
        finally:
            self.connection.execute("PRAGMA foreign_keys = ON")
        with self.assertRaises(ReviewSubjectConflictError):
            self.preparation.prepare_review(candidate_id=candidate.identity.value)
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM subtitle_effective_review_subjects"
            ).fetchone()[0],
            1,
        )

    def test_broken_candidate_graph_blocks_preparation(self):
        _, candidate = self._raw_candidate()
        self.connection.execute("PRAGMA foreign_keys = OFF")
        try:
            self.connection.execute(
                "DELETE FROM subtitle_effective_candidate_cue_segments WHERE cue_id = "
                "(SELECT identity FROM subtitle_effective_candidate_cues "
                " WHERE candidate_id = ? AND ordinal = 0)",
                (candidate.identity.value,),
            )
            self.connection.execute(
                "DELETE FROM subtitle_effective_candidate_cues "
                "WHERE candidate_id = ? AND ordinal = 0",
                (candidate.identity.value,),
            )
        finally:
            self.connection.execute("PRAGMA foreign_keys = ON")
        with self.assertRaises(CandidateGraphIntegrityError):
            self.preparation.prepare_review(candidate_id=candidate.identity.value)
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM subtitle_effective_review_subjects"
            ).fetchone()[0],
            0,
        )

    def test_stale_candidate_prepares_with_derived_staleness(self):
        raw, raw_candidate = self._raw_candidate()
        self._corrected_candidate(raw)  # authority moves on; raw candidate now stale
        result = self.preparation.prepare_review(candidate_id=raw_candidate.identity.value)
        self.assertEqual(result.outcome.value, "created")
        self.assertIs(
            result.status.review_subject_currentness,
            ReviewSubjectCurrentness.STALE_DUE_TO_CANDIDATE_SOURCE,
        )

    def test_authority_changes_never_mutate_subjects_or_create_authority(self):
        raw, raw_candidate = self._raw_candidate()
        r1 = self.preparation.prepare_review(candidate_id=raw_candidate.identity.value)
        correction_candidate, corrected = self._corrected_candidate(raw)
        r2 = self.preparation.prepare_review(candidate_id=corrected.identity.value)
        self.decisions.decide(candidate_id=correction_candidate, kind="reject", reviewer="r:kim")
        self.assertEqual(self.preparation.get(r1.subject.identity.value), r1.subject)
        self.assertEqual(self.preparation.get(r2.subject.identity.value), r2.subject)
        status = self.preparation.status(r2.subject)
        self.assertIs(
            status.review_subject_currentness,
            ReviewSubjectCurrentness.STALE_DUE_TO_CANDIDATE_SOURCE,
        )
        for table in ("subtitle_review_preparations", "subtitle_review_decisions",
                      "subtitle_final_subtitles", "review_items", "subtitle_candidates"):
            self.assertEqual(
                self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0],
                0,
                table,
            )


if __name__ == "__main__":
    unittest.main()
