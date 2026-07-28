# Derived Lecture Analysis Input Eligibility

- Status: Implementation Reference
- Blueprint: `docs/042_LECTURE_INTELLIGENCE_PIPELINE.md` §5/§5.1 with `PATCH-0009` (042
  Milestone 1, Confirmed), over the released 040 §20 effective-transcript authority (GOAL-022);
  no new Blueprint PATCH required
- Schema: unchanged (**v46**) — eligibility is derived only; no table, no migration

## Purpose

The first executable Lecture Intelligence contract for the effective-transcript generation:
for one exact `TranscriptSourceIntakeId`, derive whether the current effective transcript
authority is admissible as a lecture-analysis input, and expose the exact lineage a later
explicit admission command would bind.

```text
Transcript Source Intake → 040 §20 resolver (called exactly once)
                         → derived eligibility (eligible | stable blocking reasons)
                         → exact lineage: intake, source media, corrected revision,
                           parent raw transcript, observed selections, §19 fingerprint
```

**Eligibility ≠ Analysis Input ≠ Analysis Run.** Nothing is persisted, no identity is
allocated, no transcript record is touched, no ProcessingRun exists, and no AI runs.

## Admission authority and eligibility policy (042 §5.1, Confirmed)

The confirmed admission authority is the **validated Corrected Transcript selected by the
Transcript Pipeline** with its Source Timeline (ordered canonical segments) and Source Media
reference, in the current-selected applicable state. Therefore:

- eligible ⇔ the §20 resolver returns `effective_kind = corrected_revision` (current
  corrected selection, applicable) **and** the immutable revision snapshot is complete with
  non-empty content;
- raw-only authority (`no_history`) and an explicit `raw_fallback` selection are honest
  ineligible states — raw transcripts are first-class upstream records but not the confirmed
  analysis admission authority;
- an inapplicable selection is reported with the canonical resolver's reason
  (`parent_raw_transcript_not_current` | `candidate_not_accepted`) — never a silent fallback;
- **historical policy:** only current applicable authority is eligible; historical
  raw transcripts and superseded revisions remain valid immutable records but are never
  admitted as new analysis inputs (042 defines no historical analysis);
- **empty-content policy:** a conservative structural rule only — at least one segment with
  non-whitespace text; no token-count, duration, or timing minimum is invented (042 defines
  none; timing is not required for eligibility).

## Result and blocking vocabulary

`LectureAnalysisInputEligibility` (frozen, derived): intake, `eligible`, deterministically
ordered `blocking_reasons`, source media, selection state, effective kind, corrected revision,
parent raw transcript, observed raw/corrected selection identities, inapplicability reason,
segment count, and the released **§19 content fingerprint** (`content_fingerprint_for`,
reused verbatim — no second normalization). Closed blocking vocabulary, ordered by
definition: `intake_not_found`, `no_current_raw_transcript`,
`corrected_transcript_not_selected`, `corrected_selection_not_applicable`,
`transcript_content_empty`. Normal ineligibility never throws;
`LectureAnalysisInputEligibilityError` is reserved for malformed input and repository
integrity failures (missing resolved snapshots), which are never concealed as ineligibility.

## Snapshot coherence and the advisory (TOCTOU) boundary

One evaluation resolves authority **exactly once** through the sole released resolver
(`CorrectedRevisionSelectionService.resolve_effective_transcript`) and then loads the revision
snapshot by immutable identities only — a single result never mixes two authority snapshots.
The result is **advisory**: it reserves and freezes nothing; near-concurrent authority changes
may make two evaluations observe different valid snapshots, each internally coherent. A later
explicit admission command must revalidate current authority before persisting anything.

## Relation to the legacy 042 §5.1 implementation

The released `application/lecture_analysis_input.py` (durable `eligible_analysis_inputs`
records, v23 era) realizes PATCH-0009 over the **legacy** execution-coupled transcript
pipeline (Transcript Readiness Evaluation, ProcessingRun/UnitExecution provenance). This
module is the **effective-transcript contract generation's** counterpart — exactly as the
effective subtitle pipeline coexists with the legacy subtitle path. Neither reads or writes
the other; the legacy tables stay zero-row under this contract (test-asserted). The durable
Eligible Analysis Input record for the effective generation belongs to the next Goal
(explicit admission).

## Architecture

- `application/lecture_analysis_input_eligibility.py` — result model, closed blocking enum,
  `LectureAnalysisInputEligibilityService.evaluate(intake_id)`.
- `composition.compose_sqlite_lecture_analysis_input_eligibility_service(connection)` —
  wires the intake repository, raw-selection repository, the released §20 resolver service,
  and the immutable revision/segment snapshot repositories. Read-only.
- `analysis_input_eligibility_cli.py` — `evaluate --intake --database`; exit 0 eligible,
  1 ineligible (stable reasons printed) or error; output separates lineage from the explicit
  "analysis input state: not created" and "analysis execution state: not part of this
  contract" boundaries.
- `analysis_input_eligibility_demo.py` + `examples/analysis-input-eligibility/` —
  deterministic demo with a byte-stable, machine-path-free golden covering the ten GOAL-022
  scenarios (raw-only/raw-fallback ineligibility, eligible corrected lineage, supersession,
  inapplicability, unknown intake, restart determinism, derived-only, healthy validation).

## Validation

No validator changes: eligibility has no rows to validate, and every structural invariant it
relies on (intake linkage, revision-generation binding, segment lineage, selection
supersession) is already covered by the released transcript validators. Ineligibility —
including no effective transcript, stale/superseded authority, and empty content — is never
corruption.

## Status

Complete: 20 focused new tests; the complete 2642-test suite passes; schema v46 unchanged.
Next Goal: **Explicit Lecture Analysis Input Admission** — revalidate eligibility and persist
one immutable, provenance-bearing Eligible Analysis Input record for the effective generation
(042 §5.1's durable record), separate from Analysis Execution.
