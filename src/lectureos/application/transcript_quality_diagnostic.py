"""Transcript Quality Diagnostic foundation (040 §15 QD-10…QD-15, `PATCH-0045`).

A **derived** observation over an admitted Raw Transcript and the provider evidence preserved with it.
It is a Quality Warning, never a Validation Failure (QD-2): a hallucinated segment is structurally
valid — ordered, non-overlapping, in range, with intact lineage — so repository validation neither
knows nor reports any of this.

Three properties define the boundary:

* **Nothing is persisted (QD-10).** A result is computed on demand from immutable inputs and a
  versioned algorithm. Storing it would duplicate recomputable content and allow a stale diagnostic to
  disagree with its own inputs. There is no table, no row, no identity, and no lifecycle here.
* **Nothing fires without a contracted rule (QD-14).** The reason vocabulary is fixed by `PATCH-0045`;
  the firing rules are not. Every reason is therefore reported as *undetermined with a stated cause*
  rather than guessed at — see `_undetermined_reasons`. Emitting a finding from an invented threshold
  would be a product policy decision made in code.
* **An empty result is never "clean" (QD-9).** Zero findings here means nothing could be decided, and
  the result says so explicitly through `completeness` and `undetermined`.

The result also carries no combined score. QD-12 forbids one: on the preserved fixtures two real
utterances and one fabrication shared identical decode-window values, so a single number would assert
a confidence the evidence cannot support and could not be decomposed by the person acting on it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from lectureos.transcript.identities import TranscriptSegmentId

from .provider_transcript_admission import (
    ProviderDecodeEvidence,
    ProviderTranscriptAdmissionError,
    TIMING_BOUNDARY_TOLERANCE_SECONDS,
    parse_preserved_provider_evidence,
    parse_preserved_segment_timings,
)

# The versioned algorithm anchor (QD-11). Kind and version identify the computation; the provider
# parameter version identifies the threshold parameter set — which does not exist yet, so it is
# `None`. That is the honest value: a diagnostic computed today is reproducible precisely *because*
# it declares that no threshold policy participated.
DIAGNOSTIC_ALGORITHM_KIND = "local-asr-transcript-quality"
DIAGNOSTIC_ALGORITHM_VERSION = 1
PROVIDER_PARAMETER_VERSION: str | None = None

_CANONICAL_ADMISSION_ID = re.compile(r"^provider-transcript-admission:[0-9a-f]{64}$")


class TranscriptQualityDiagnosticError(ValueError):
    """The diagnostic could not be computed (malformed identity or unresolvable record)."""


class QualityReason(str, Enum):
    """The reason vocabulary fixed by `PATCH-0045` QD-12. Each reason states its own ground.

    Vocabulary and firing rule are different questions. These names are contracted; the thresholds
    that would make the four provider reasons fire are not, and `REPEATED_TEXT`'s repetition rule is
    not either (QD-14). Membership here is therefore not permission to emit.
    """

    PROVIDER_LOW_CONFIDENCE = "PROVIDER_LOW_CONFIDENCE"
    PROVIDER_HIGH_NO_SPEECH = "PROVIDER_HIGH_NO_SPEECH"
    PROVIDER_HIGH_COMPRESSION = "PROVIDER_HIGH_COMPRESSION"
    PROVIDER_DECODE_FALLBACK = "PROVIDER_DECODE_FALLBACK"
    REPEATED_TEXT = "REPEATED_TEXT"


class EvidenceScope(str, Enum):
    """What a reason's evidence actually describes (QD-7, QD-15).

    `DECODE_WINDOW` values are shared by every segment the window covers, so a finding carrying one
    must never be read as a claim about its segment alone.
    """

    DECODE_WINDOW = "decode_window"
    TRANSCRIPT = "transcript"
    # `PATCH-0046` TD-9: the timing reason describes one segment's position relative to its decode
    # anchor, not a value shared across a window, so it carries its own scope.
    SEGMENT = "segment"


class DiagnosticCompleteness(str, Enum):
    """How much of the reason vocabulary this computation was able to decide.

    A completeness value for one derived result — deliberately not a lifecycle, not a state machine,
    and not attached to any record (QD-10). `COMPLETE` and `PARTIAL` are unreachable in this
    generation because every reason is deferred; they exist so a later threshold PATCH has an
    accurate value to return rather than having to redefine the vocabulary.
    """

    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


# Which evidence family each provider reason would read, and at what scope (QD-12).
_PROVIDER_REASON_EVIDENCE: dict[QualityReason, tuple[str, EvidenceScope]] = {
    QualityReason.PROVIDER_LOW_CONFIDENCE: ("avg_logprob", EvidenceScope.DECODE_WINDOW),
    QualityReason.PROVIDER_HIGH_NO_SPEECH: ("no_speech_prob", EvidenceScope.DECODE_WINDOW),
    QualityReason.PROVIDER_HIGH_COMPRESSION: ("compression_ratio", EvidenceScope.DECODE_WINDOW),
    QualityReason.PROVIDER_DECODE_FALLBACK: ("temperature", EvidenceScope.DECODE_WINDOW),
}


@dataclass(frozen=True, slots=True)
class QualityFinding:
    """One derived observation about one segment (QD-15).

    Carries the evidence scope explicitly so a window-scoped reason cannot be mistaken for a
    per-segment claim, and the algorithm version so a finding is always attributable to the
    computation that produced it.
    """

    segment_ordinal: int
    reason: QualityReason
    evidence_source: str
    evidence_scope: EvidenceScope
    detail: str
    algorithm_version: int = DIAGNOSTIC_ALGORITHM_VERSION
    segment_id: TranscriptSegmentId | None = None

    def __post_init__(self) -> None:
        if self.segment_ordinal < 0:
            raise TranscriptQualityDiagnosticError("finding segment ordinal must not be negative")
        if not isinstance(self.evidence_source, str) or not self.evidence_source.strip():
            raise TranscriptQualityDiagnosticError("finding evidence source must not be empty")
        if not isinstance(self.detail, str) or not self.detail.strip():
            raise TranscriptQualityDiagnosticError("finding detail must not be empty")


@dataclass(frozen=True, slots=True)
class UndeterminedReason:
    """A reason that could not be decided, and why (QD-9, QD-14).

    This is the field that keeps an empty result from reading as "clean". Every reason in the
    vocabulary appears either as a finding or here — never silently absent.
    """

    reason: QualityReason
    cause: str

    def __post_init__(self) -> None:
        if not isinstance(self.cause, str) or not self.cause.strip():
            raise TranscriptQualityDiagnosticError("undetermined reason cause must not be empty")


@dataclass(frozen=True, slots=True)
class TranscriptQualityDiagnosticResult:
    """One derived diagnostic computation. Never persisted, never a canonical record (QD-10)."""

    algorithm_kind: str
    algorithm_version: int
    provider_parameter_version: str | None
    provider_transcript_result_id: str
    raw_transcript_id: str
    segment_count: int
    evidence_available: bool
    decode_window_count: int
    evidence_covered_segment_count: int
    completeness: DiagnosticCompleteness
    findings: tuple[QualityFinding, ...] = ()
    undetermined: tuple[UndeterminedReason, ...] = ()

    @property
    def reports_clean(self) -> bool:
        """Whether this result actually asserts the transcript is clean.

        Always ``False`` while any reason is undetermined. Callers must use this instead of
        ``not findings``: zero findings with a deferred threshold policy means *nothing was decided*,
        which QD-9 forbids presenting as a clean result.
        """

        return not self.findings and not self.undetermined


class ProviderTranscriptAdmissionQuery:
    def get(self, identity): ...


class ProviderTranscriptResultQuery:
    def get(self, identity): ...


class RawTranscriptQuery:
    def get(self, identity): ...


# ---------------------------------------------------------------------------------------------
# Timing Quality Diagnostic — `PATCH-0046` TD-1…TD-20
#
# A sibling reason family inside this same framework (TD-3), deliberately kept in separate types so
# a timing reason can never be mixed into a hallucination finding or scored with one (TD-16).
# ---------------------------------------------------------------------------------------------

TIMING_ALGORITHM_KIND = "local-asr-transcript-timing-quality"
TIMING_ALGORITHM_VERSION = 1
# TD-11: versioned even though no threshold participates. `None` is the honest value — a timing
# result is reproducible precisely because it declares that no threshold policy took part.
TIMING_PROVIDER_PARAMETER_VERSION: str | None = None

# TD-8: the anchor grammar is provider-specific. faster-whisper records its decode position as
# ``seek`` in centiseconds and the released evidence preserves it verbatim in ``window_ref``
# (QD-6). No other provider is assumed to expose it or to share these semantics.
_FASTER_WHISPER_ANCHOR = re.compile(r"^seek=(\d+)$")


class TimingQualityReason(str, Enum):
    """The timing reason vocabulary fixed by `PATCH-0046` TD-9.

    Deliberately a separate enum from :class:`QualityReason`. TD-16 requires timing and hallucination
    reasons to stay apart, and separate types make an accidental merge impossible rather than merely
    discouraged.
    """

    TIMING_ALIGNMENT_REVIEW_REQUIRED = "TIMING_ALIGNMENT_REVIEW_REQUIRED"


@dataclass(frozen=True, slots=True)
class TimingQualityFinding:
    """One derived timing observation about one segment (TD-2, TD-7).

    ``detail`` states the structure that was observed and nothing more. It never carries a drift
    magnitude: the anchor gap is how far the decode window opened past the previous coverage, which
    is **not** how late the speech is, and reporting it as one would be the claim TD-2 forbids.
    """

    segment_ordinal: int
    reason: TimingQualityReason
    evidence_source: str
    evidence_scope: EvidenceScope
    detail: str
    algorithm_version: int = TIMING_ALGORITHM_VERSION
    segment_id: TranscriptSegmentId | None = None

    def __post_init__(self) -> None:
        if self.segment_ordinal < 0:
            raise TranscriptQualityDiagnosticError("finding segment ordinal must not be negative")
        if not isinstance(self.detail, str) or not self.detail.strip():
            raise TranscriptQualityDiagnosticError("finding detail must not be empty")


@dataclass(frozen=True, slots=True)
class TranscriptTimingDiagnosticResult:
    """One derived timing computation. Never persisted, never a canonical record (TD-10)."""

    algorithm_kind: str
    algorithm_version: int
    provider_parameter_version: str | None
    provider_transcript_result_id: str
    raw_transcript_id: str
    segment_count: int
    evidence_available: bool
    decode_window_count: int
    window_first_segment_count: int
    completeness: DiagnosticCompleteness
    findings: tuple[TimingQualityFinding, ...] = ()

    @property
    def reports_clean(self) -> bool:
        """Whether this result actually asserts the timing is sound.

        ``False`` whenever the required evidence was unavailable. TD-12: a record admitted before
        decode anchors were preserved yields *unavailable*, and callers must not read that as clean.
        """

        return self.evidence_available and not self.findings


def provider_anchor_seconds(window_ref: str) -> float | None:
    """The provider's decode anchor in seconds, or ``None`` when this provider has none.

    Provider-specific by contract (TD-8). Returning ``None`` is how an unrecognised grammar reaches
    *unavailable* rather than being guessed at.
    """

    match = _FASTER_WHISPER_ANCHOR.fullmatch(window_ref.strip())
    if match is None:
        return None
    return int(match.group(1)) / 100.0


def evaluate_timing_predicate(
    evidence: ProviderDecodeEvidence, timings: tuple[tuple[float, float], ...]
) -> tuple[tuple[int, float, float], ...]:
    """Segments satisfying `PATCH-0046`'s predicate P, as ``(ordinal, anchor, anchor_gap)``.

    ```text
    P1  the segment is the first of its provider decode window
        AND segment.start == provider anchor                      (within ε)
    P2  provider anchor > previous admitted segment end            (within ε)
    P   P1 AND P2
    ```

    ``ε`` is the released `PATCH-0039` tolerance, used **only** to decide whether two values denote
    the same instant (T-2). No new tolerance exists here, and **no duration threshold does either**
    (TD-6): P2 is a strict inequality, so an anchor 0.02 s past the previous coverage qualifies
    exactly as one 85 s past does.

    P1 on its own is normal provider decode semantics and is never a finding (TD-4) — every decode
    window's first segment begins at its anchor, so P1 alone would fire on roughly one segment in
    ten.
    """

    eps = TIMING_BOUNDARY_TOLERANCE_SECONDS
    out: list[tuple[int, float, float]] = []
    for window in evidence.windows:
        first = window.segment_ordinals[0]
        if first >= len(timings):
            continue
        anchor = provider_anchor_seconds(window.window_ref)
        if anchor is None:
            continue
        start, _ = timings[first]
        if abs(start - anchor) > eps:          # P1: not anchored — nothing to say
            continue
        if first == 0:                          # no previous coverage to compare against
            continue
        previous_end = timings[first - 1][1]
        if anchor > previous_end + eps:         # P2
            out.append((first, anchor, anchor - previous_end))
    return tuple(out)


class TranscriptTimingDiagnosticService:
    """Computes the derived timing-quality diagnostic for one admitted provider transcript result.

    Read-only by construction, like its sibling: queries only, no persistence port, so there is no
    code path through which a timing result could be stored or a timestamp altered (TD-10, TD-13).
    """

    def __init__(
        self,
        admission_query: ProviderTranscriptAdmissionQuery,
        provider_result_query: ProviderTranscriptResultQuery,
        raw_transcript_query: RawTranscriptQuery,
    ) -> None:
        self._admissions = admission_query
        self._provider_results = provider_result_query
        self._raw_transcripts = raw_transcript_query

    def diagnose(self, *, admission_id: str) -> TranscriptTimingDiagnosticResult:
        from .identities import ProviderTranscriptAdmissionId

        if not isinstance(admission_id, str) or not _CANONICAL_ADMISSION_ID.fullmatch(admission_id):
            raise TranscriptQualityDiagnosticError(
                "provider transcript admission identity is malformed "
                "(expected 'provider-transcript-admission:<64 hex digest>')"
            )
        admission = self._admissions.get(ProviderTranscriptAdmissionId(admission_id))
        if admission is None:
            raise TranscriptQualityDiagnosticError(
                "unknown provider transcript admission: admit a provider result first"
            )
        provider_result = self._provider_results.get(admission.provider_transcript_result_id)
        if provider_result is None:
            raise TranscriptQualityDiagnosticError(
                "the admission references a missing provider transcript result"
            )
        raw_transcript = self._raw_transcripts.get(admission.raw_transcript_id)
        if raw_transcript is None:
            raise TranscriptQualityDiagnosticError(
                "the admission references a missing raw transcript"
            )

        content = provider_result.original_content
        evidence = parse_preserved_provider_evidence(content)
        timings = parse_preserved_segment_timings(content)
        segment_ids = raw_transcript.segment_ids

        anchored_windows = (
            ()
            if evidence is None
            else tuple(
                w for w in evidence.windows if provider_anchor_seconds(w.window_ref) is not None
            )
        )
        # TD-12: no preserved anchor means the question cannot be asked, not that the answer is clean.
        available = bool(anchored_windows) and bool(timings)

        findings: tuple[TimingQualityFinding, ...] = ()
        if available:
            findings = tuple(
                TimingQualityFinding(
                    segment_ordinal=ordinal,
                    reason=TimingQualityReason.TIMING_ALIGNMENT_REVIEW_REQUIRED,
                    evidence_source="provider decode window anchor",
                    evidence_scope=EvidenceScope.SEGMENT,
                    detail=(
                        "segment begins at its provider decode-window anchor "
                        f"({anchor:.3f}s), which opened after the previous admitted coverage ended; "
                        "whether the provider timestamp aligns with acoustic speech onset is worth "
                        "human review"
                    ),
                    segment_id=segment_ids[ordinal] if ordinal < len(segment_ids) else None,
                )
                for ordinal, anchor, _gap in evaluate_timing_predicate(evidence, timings)
            )

        return TranscriptTimingDiagnosticResult(
            algorithm_kind=TIMING_ALGORITHM_KIND,
            algorithm_version=TIMING_ALGORITHM_VERSION,
            provider_parameter_version=TIMING_PROVIDER_PARAMETER_VERSION,
            provider_transcript_result_id=admission.provider_transcript_result_id.value,
            raw_transcript_id=admission.raw_transcript_id.value,
            segment_count=len(segment_ids),
            evidence_available=available,
            decode_window_count=len(anchored_windows),
            window_first_segment_count=len(anchored_windows),
            completeness=(
                DiagnosticCompleteness.COMPLETE if available else DiagnosticCompleteness.UNAVAILABLE
            ),
            findings=findings,
        )


def _undetermined_reasons(evidence: ProviderDecodeEvidence | None) -> tuple[UndeterminedReason, ...]:
    """Why each reason in the vocabulary cannot be decided in this generation.

    Two distinct causes, and the difference matters to whoever reads the result:

    * **evidence unavailable** — a result admitted before evidence was preserved, or a provider that
      reported none. Nothing can be read at all.
    * **threshold policy deferred** — the evidence is right there, but `PATCH-0045` QD-14 deliberately
      did not fix where to cut. One lecture and one hallucination cluster showed the signals separate;
      they did not show the boundary. Inventing one here would make a product policy decision in code.

    `REPEATED_TEXT` is deferred for a third reason: its *rule* is uncontracted. How many repeats
    count, whether the match must be exact, whether occurrences must be consecutive, and how
    whitespace and punctuation are treated are all undecided, and each answer changes which segments
    are flagged. A vocabulary entry is not a rule.
    """

    threshold_cause = (
        "threshold policy deferred (040 §15 QD-14): the provider-specific parameter set is a later "
        "empirical PATCH, so no numeric cut is applied"
    )
    evidence_cause = (
        "provider evidence unavailable for this result: it was admitted without preserved decode "
        "evidence, which is not the same as being clean (040 §15 QD-9)"
    )
    reasons = [
        UndeterminedReason(
            reason=reason,
            cause=evidence_cause if evidence is None else threshold_cause,
        )
        for reason in _PROVIDER_REASON_EVIDENCE
    ]
    reasons.append(
        UndeterminedReason(
            reason=QualityReason.REPEATED_TEXT,
            cause=(
                "repetition rule not contracted (040 §15 QD-14): repeat count, exact-match, "
                "adjacency, and whitespace/punctuation handling are undecided"
            ),
        )
    )
    return tuple(reasons)


class TranscriptQualityDiagnosticService:
    """Computes a derived quality diagnostic for one admitted provider transcript result.

    Read-only by construction: it holds queries, never a persistence port, so there is no code path
    through which a diagnostic could be stored, a transcript altered, or a correction created
    (QD-10, QD-16).
    """

    def __init__(
        self,
        admission_query: ProviderTranscriptAdmissionQuery,
        provider_result_query: ProviderTranscriptResultQuery,
        raw_transcript_query: RawTranscriptQuery,
    ) -> None:
        self._admissions = admission_query
        self._provider_results = provider_result_query
        self._raw_transcripts = raw_transcript_query

    def diagnose(self, *, admission_id: str) -> TranscriptQualityDiagnosticResult:
        """Derive the diagnostic for an admission. Computes nothing until after admission (QD-4)."""

        if not isinstance(admission_id, str) or not _CANONICAL_ADMISSION_ID.fullmatch(admission_id):
            raise TranscriptQualityDiagnosticError(
                "provider transcript admission identity is malformed "
                "(expected 'provider-transcript-admission:<64 hex digest>')"
            )
        from .identities import ProviderTranscriptAdmissionId

        admission = self._admissions.get(ProviderTranscriptAdmissionId(admission_id))
        if admission is None:
            raise TranscriptQualityDiagnosticError(
                "unknown provider transcript admission: admit a provider result first"
            )
        provider_result = self._provider_results.get(admission.provider_transcript_result_id)
        if provider_result is None:
            raise TranscriptQualityDiagnosticError(
                "the admission references a missing provider transcript result"
            )
        raw_transcript = self._raw_transcripts.get(admission.raw_transcript_id)
        if raw_transcript is None:
            raise TranscriptQualityDiagnosticError(
                "the admission references a missing raw transcript"
            )

        evidence = parse_preserved_provider_evidence(provider_result.original_content)
        covered = 0 if evidence is None else len(evidence.covered_ordinals)
        undetermined = _undetermined_reasons(evidence)
        # Every reason is currently undetermined, so nothing was decided. `UNAVAILABLE` is the
        # truthful completeness even when the evidence itself is present: the cause distinguishes
        # the two situations, and neither of them is a clean verdict.
        findings: tuple[QualityFinding, ...] = ()
        if not undetermined:
            completeness = DiagnosticCompleteness.COMPLETE
        elif findings:
            completeness = DiagnosticCompleteness.PARTIAL
        else:
            completeness = DiagnosticCompleteness.UNAVAILABLE

        return TranscriptQualityDiagnosticResult(
            algorithm_kind=DIAGNOSTIC_ALGORITHM_KIND,
            algorithm_version=DIAGNOSTIC_ALGORITHM_VERSION,
            provider_parameter_version=PROVIDER_PARAMETER_VERSION,
            provider_transcript_result_id=admission.provider_transcript_result_id.value,
            raw_transcript_id=admission.raw_transcript_id.value,
            segment_count=len(raw_transcript.segment_ids),
            evidence_available=evidence is not None,
            decode_window_count=0 if evidence is None else len(evidence.windows),
            evidence_covered_segment_count=covered,
            completeness=completeness,
            findings=findings,
            undetermined=undetermined,
        )

    def correction_target_for(
        self, *, admission_id: str, segment_ordinal: int
    ) -> TranscriptSegmentId:
        """Resolve a finding's segment ordinal to the canonical segment identity (QD-17).

        The whole of this milestone's correction connection: it hands a person the identity that the
        **existing** §17 Correction Candidate admission already accepts. It proposes no replacement
        text, creates no candidate, stores nothing, and makes no decision — QD-16 forbids all three,
        and it is that prohibition that makes a false positive harmless.
        """

        from .identities import ProviderTranscriptAdmissionId

        if not isinstance(admission_id, str) or not _CANONICAL_ADMISSION_ID.fullmatch(admission_id):
            raise TranscriptQualityDiagnosticError(
                "provider transcript admission identity is malformed"
            )
        admission = self._admissions.get(ProviderTranscriptAdmissionId(admission_id))
        if admission is None:
            raise TranscriptQualityDiagnosticError("unknown provider transcript admission")
        raw_transcript = self._raw_transcripts.get(admission.raw_transcript_id)
        if raw_transcript is None:
            raise TranscriptQualityDiagnosticError(
                "the admission references a missing raw transcript"
            )
        if segment_ordinal < 0 or segment_ordinal >= len(raw_transcript.segment_ids):
            raise TranscriptQualityDiagnosticError(
                f"segment ordinal {segment_ordinal} is outside this transcript"
            )
        return raw_transcript.segment_ids[segment_ordinal]


__all__ = [
    "DIAGNOSTIC_ALGORITHM_KIND",
    "DIAGNOSTIC_ALGORITHM_VERSION",
    "DiagnosticCompleteness",
    "EvidenceScope",
    "PROVIDER_PARAMETER_VERSION",
    "ProviderTranscriptAdmissionError",
    "QualityFinding",
    "QualityReason",
    "TranscriptQualityDiagnosticError",
    "TranscriptQualityDiagnosticResult",
    "TranscriptQualityDiagnosticService",
    "TranscriptTimingDiagnosticResult",
    "TranscriptTimingDiagnosticService",
    "TIMING_ALGORITHM_KIND",
    "TIMING_ALGORITHM_VERSION",
    "TIMING_PROVIDER_PARAMETER_VERSION",
    "TimingQualityFinding",
    "TimingQualityReason",
    "evaluate_timing_predicate",
    "provider_anchor_seconds",
    "UndeterminedReason",
]
