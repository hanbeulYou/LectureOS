# Explicit Lecture Analysis Input Admission

- Status: Implementation Reference
- Blueprint: `docs/042` §5.1 + `PATCH-0009` (042 Milestone 1, Confirmed) — the **durable half**
  for the effective-transcript generation, over the GOAL-022 derived eligibility (GOAL-023);
  no new Blueprint PATCH required
- Schema: v47 (one additive append-only table `lecture_analysis_input_admissions`)

## Purpose

One explicit command admits the intake's current effective transcript authority — the
validated selected Corrected Transcript with its Source Timeline and Source Media reference —
as one **immutable, identity-owning, provenance-bearing** analysis input record.

```text
explicit admit(intake) → GOAL-022 eligibility REVALIDATED at command time
                       → immutable LectureAnalysisInputAdmission
                         (intake, source media, corrected revision, parent raw transcript,
                          observed raw/corrected selections, §19 fingerprint, segment count)
                       → idempotent replay (same authority ⇒ reused, no new row)
```

**Admission ≠ Analysis Execution.** No Analysis Run, ProcessingRun, Finding, Artifact, or AI
reasoning exists here; the record is the durable analysis basis only.

## Admission semantics

- **Revalidation:** every command re-evaluates the derived eligibility (closing GOAL-022's
  documented advisory/TOCTOU boundary); an ineligible intake — including raw-only authority,
  raw-fallback selections, and inapplicable selections — refuses before persistence with the
  eligibility blocking reasons. A prior eligibility result is never trusted.
- **Snapshot:** the record binds the eligible result's single-snapshot lineage exactly as
  admitted; later authority changes (new revisions, new selections) never mutate it.
- **Contract:** `lecture_analysis_input_admission` v1; no wall-clock, path, or rowid
  participates anywhere (the repository's released no-wall-clock rule — deliberately no
  admission timestamp).

## Identity and replay (the released GOAL-012 binding rule, reused)

`lecture-analysis-input:<sha256(contract kind/version, intake scope, corrected revision)>` —
identity derives from the exact immutable admitted source only; observed authority provenance
and the content fingerprint are recorded facts, not identity.

- Same current authority re-admitted → **reused** (idempotent, no new row) — including under
  near-concurrent identical commands (insert collision → converge) and after the authority
  changed away and back to a previously admitted revision.
- Changed authority (a new current corrected revision) → a **new** admission record; prior
  admissions remain valid immutable history (**append-only** — never updated or deleted).
- A fingerprint/lineage disagreement on an existing record is an explicit
  `AnalysisInputAdmissionConflictError` (integrity), never an overwrite.
- `authority_match(admission)` derives (never stores) whether a record still binds the
  current authority: `current` | `superseded_by_authority_change` |
  `current_authority_ineligible`. Historical admissions are never corruption.

## Architecture

- `application/lecture_analysis_input_admission.py` — model, deterministic identity,
  `LectureAnalysisInputAdmissionService` (admit / get / list_for_intake / authority_match).
- `persistence/lecture_analysis_input_admission.py` — repository + one atomic BEGIN IMMEDIATE
  insert-only transaction; collisions map to the released identity-collision error.
- `composition.compose_sqlite_lecture_analysis_input_admission_service(connection)` — wires
  the GOAL-022 eligibility service (the sole §20/§19 authority path) + the v47 store.
- `analysis_input_admission_cli.py` — admit / show / status / list; replay exits 0 reporting
  `reused`; ineligible admits exit 1 persisting nothing.
- `analysis_input_admission_demo.py` + `examples/analysis-input-admission/` — deterministic
  demo with a byte-stable, machine-path-free golden covering the eight GOAL-023 scenarios.

## Migration

v46 → v47, strictly additive: the one insert-only table (identity PK; FKs to intake, source
media, corrected revision, raw transcript, and both selection tables; 64-hex fingerprint;
`segment_count > 0`; contract-version CHECK; `UNIQUE(intake, corrected_revision)`). Chain
v1..v46 → v47 preserves all rows; downgrade/direct-skip/unsupported targets rejected; the
full superseded-version ritual applied.

## Validation

Six integrity-only codes (`LECTURE_ANALYSIS_ADMISSION_*`): source-media mismatch, raw-lineage
mismatch (raw selection must belong to the intake and select the recorded parent raw),
selection-lineage mismatch (corrected selection must have selected the exact admitted
revision), fingerprint re-derivation (the §19 fingerprint recomputed from the immutable
revision segments), segment-count mismatch, identity re-derivation. Superseded admissions,
ineligible current authority, and the untouched legacy `eligible_analysis_inputs` contract
are deliberately never flagged. Validation never reads the filesystem.

## Relation to the legacy 042 implementation

The released execution-coupled `lecture_analysis_input` module (durable
`eligible_analysis_inputs`) remains the legacy generation's realization of PATCH-0009; this
contract never reads or writes it (test-asserted zero rows). The two generations coexist
exactly as the legacy and effective subtitle pipelines do.

## Status

Complete: 38 focused new tests; the complete 2680-test suite passes; schema v47. Next Goal:
the first analysis capability over admitted inputs — per 042's dependency order, the
**Lecture Segmentation / Analysis Finding application foundations** (042 §7.1/§8.1) remain
product-gated; the next implementation-ready step should be selected against those gates.
