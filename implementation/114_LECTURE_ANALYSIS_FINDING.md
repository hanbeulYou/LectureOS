# Analysis Finding Application Foundation — Effective-Transcript Generation

- Status: Implementation Reference
- Blueprint: `docs/042` §8.2 + `PATCH-0030` (D-1…D-12, Confirmed) — the effective-transcript
  generation's Analysis Finding admission boundary, over the GOAL-023 durable analysis input
  (GOAL-025); the canonical Finding record contract is inherited unchanged from `docs/042` §8.1
- Schema: v48 (one additive append-only table `lecture_analysis_findings`)

## Purpose

One explicit command admits one provider-independent finding payload against a **current**
Lecture Analysis Input Admission and appends one **immutable, identity-owning,
provenance-bearing** canonical Analysis Finding.

```text
admit(admission, type, evidence, [confidence] [uncertainty] [range])
    → payload validated
    → anchor resolved; its authority standing RE-DERIVED at command time (current only)
    → deterministic Application-owned identity
    → immutable LectureAnalysisFinding appended
    → idempotent replay (same canonical content ⇒ reused, no new row)
```

**Analysis Finding admission ≠ Analysis Execution.** No analysis is performed and no provider,
prompt, model, AI call, ProcessingRun, ProcessingUnit, UnitExecution, RUNNING state, Lecture
Segment, or Edit Candidate exists in this contract. The caller supplies an already-normalized
payload; this boundary records it as canonical Application-owned meaning.

## Anchor (D-2)

Every Finding anchors to **exactly one** `LectureAnalysisInputAdmission`, never to the legacy
`EligibleAnalysisInput`. Upstream provenance — intake, source media, corrected revision, parent
raw transcript, both observed selections, the released `040 §19` content fingerprint — is
obtained **through** that anchor and deliberately **not duplicated** onto the Finding row (the
table has no `source_media_id`, `corrected_revision_id`, `content_fingerprint`, or intake
column; this is test-asserted). One admission may anchor many distinct Findings.

Deterministic chain: `Analysis Finding → Lecture Analysis Input Admission → current applicable
Corrected Revision → parent Raw Transcript → Source Timeline → Source Media`.

## Admission standing (D-3, D-4)

A stored admission's mere existence never suffices. Every command re-derives the anchor's
standing through the released GOAL-023 `authority_match` — **no authority resolver is
reimplemented here** — and admits only at `current`. `superseded_by_authority_change` and
`current_authority_ineligible` are explicit refusals; the released three-value vocabulary is not
extended. A missing or malformed admission reference is refused **before** standing is
evaluated (a refusal of the reference itself, never a fourth standing value) and is reported in
this boundary's own error type so callers handle one error family.

Standing is never stored: no mutable status is added to the admission, and the finding table has
no `current`/`stale`/`active`/`ready`/`superseded` column.

## Historical semantics (D-5, D-10)

Existing Findings are never mutated, deleted, or rewritten when upstream authority changes; a
Finding legitimately anchored to a then-`current` admission stays a valid immutable record.
Only *new* Findings anchored to a superseded admission are refused. When authority returns to a
previously admitted revision the same canonical admission identity becomes `current` again and
admissibility is restored by the derived rule — GOAL-023's returning-authority convergence.
`anchor_status(finding)` derives present applicability on demand; it is never persisted.

## Finding Type

The released `042 §8.1` canonical token rule (`^[a-z][a-z0-9_]*$`) — an **open** Application-owned
vocabulary, never a closed enum, never a fixed taxonomy, and never derived from `020 §5.5`
LI-001…LI-012. No alias mapping, case folding, or whitespace normalization: the token is admitted
exactly as given or refused. The rule is restated locally rather than imported from the legacy
module so this generation declares no source-level dependency on the execution-coupled one (D-1).
That is a source boundary only — it does not shrink the import graph, since `persistence.errors`
already loads the legacy modules transitively. The three copies (legacy application, this module,
the validator) are pinned equal by `test_canonical_finding_type_rule_agrees_across_layers`.

## Evidence, confidence, range

- **Evidence** — required, non-empty after strip, stored **verbatim** and unnormalized, and it
  participates in identity, so differing evidence can never converge on one Finding (D-9).
- **Confidence / uncertainty** — optional, real, within `[0, 1]` (the released §8.1 bounds,
  reused). Nothing is computed, calibrated, or prioritized. They are **recorded facts, not
  identity** (the released GOAL-023 rule that observed provenance is recorded, never identity),
  so a divergence on an existing identity is an explicit conflict rather than a second row.
- **Source range** — optional, **at most one**, both-or-neither, finite, non-negative,
  `start <= end`; a zero-duration range is structurally valid. Multi-range is not implemented.
  **No media-duration or transcript-boundary validation is added**: `042 §9.2` explicitly forbids
  introducing such checks at an Application Foundation, and the anchor records no timeline extent
  to check against.

## Identity, provenance, replay (D-6, D-8, D-9)

`lecture-analysis-finding:<sha256(contract kind/version, admission, finding_type, evidence,
range_start, range_end)>` over canonical JSON. Application-owned; no provider identifier, UUID4,
timestamp, rowid, path, or mutable currentness participates.

Generation provenance is **execution-free and marker-free**, following the GOAL-023 precedent:
the contract kind (cryptographically bound into the identity), the recorded
`finding_contract_version`, and the immutable admitted source (the anchor FK). No `ProcessingRun`,
`UnitExecution`, RUNNING state, or DomainResult is created — test-asserted, including that the
upstream chain's DomainResult count is unchanged by a finding admission.

Replay: same admission + same canonical content + same contract version → the same identity,
**reused**, no new row (near-concurrent inserts converge through the released identity-collision
error). A divergent recorded payload on an existing identity is an explicit conflict, never an
overwrite. A different admission, type, evidence, or range is a distinct Finding.

## Architecture

- `application/lecture_analysis_finding.py` — model, canonical token rule, deterministic identity,
  `LectureAnalysisFindingService` (admit / get / list_for_admission / anchor_status).
- `persistence/lecture_analysis_finding.py` — repository + one atomic `BEGIN IMMEDIATE`
  insert-only transaction; no update or delete method exists.
- `composition.compose_sqlite_lecture_analysis_finding_service(connection)` — wires the released
  GOAL-023 admission service (the sole standing path) + the v48 store.
- `analysis_finding_cli.py` — admit / show / status / list; replay exits 0 reporting `reused`;
  superseded-anchor, malformed, unknown, and invalid-payload commands exit 1 persisting nothing.
- `analysis_finding_demo.py` + `examples/analysis-finding/` — deterministic demo with a
  byte-stable, machine-path-free golden covering the twelve GOAL-025 scenarios.

## Persistence and migration

v47 → v48, strictly additive: one insert-only table `lecture_analysis_findings` (identity PK; FK
to `lecture_analysis_input_admissions`; non-empty type and evidence CHECKs; `[0, 1]` confidence
and uncertainty CHECKs; both-or-neither, non-negative, non-inverted range CHECKs;
contract-version CHECK). The legacy `analysis_findings` relation is **not reused** (D-11): its
mandatory `source_input_id`, `run_id`, and `unit_execution_id` columns could only be satisfied by
fabricating exactly what D-6 prohibits. Legacy tables are unmodified. Chain v1..v47 → v48
preserves all rows; downgrade, direct-skip, and unsupported targets stay rejected. No wall-clock
column exists, per the released no-wall-clock rule.

## Validation

Seven integrity-only codes (`LECTURE_ANALYSIS_FINDING_*`): anchor missing, contract-version
mismatch, malformed type, empty evidence, invalid range, confidence out of range, and identity
re-derivation — the last proving the whole canonical binding (contract kind and version, anchor,
and every identity-participating field) in one check. Deliberately **never** flagged: a finding
whose anchor later became superseded or whose intake's current authority became ineligible. Those
are valid immutable history, never corruption. Validation reads no filesystem and no provider.

## Relation to the legacy 042 §8.1 implementation

The released execution-coupled `analysis_finding` module (durable `analysis_findings`, anchored to
`eligible_analysis_inputs` and requiring a RUNNING unit execution) remains the **legacy**
generation's realization of PATCH-0010; this contract never reads or writes it (test-asserted zero
rows). The two generations coexist exactly as PATCH-0030 D-1 records and as the legacy and
effective subtitle pipelines already do.

## Status

Complete: 79 focused new tests; the complete 2759-test suite passes; schema v48. `042 §7.1`
(Lecture Segmentation) and `042 §9.1` (Edit Candidate) still carry their legacy-generation
admission boundaries and were deliberately **not** re-scoped by PATCH-0030 (D-12); each needs its
own approved generation-scope decision before it can be implemented in this generation.
