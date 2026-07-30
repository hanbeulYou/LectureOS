# Edit Candidate Foundation — Effective-Transcript Generation

- Status: Implementation Reference
- Blueprint: `docs/042` §9.3 + `PATCH-0032` (C-1…C-13, Confirmed) — the effective-transcript
  generation's Edit Candidate admission boundary, over the GOAL-025 Analysis Finding (GOAL-027);
  the canonical Candidate record contract is inherited unchanged from `docs/042` §9.1
- Schema: v50 (one additive append-only table `lecture_analysis_edit_candidates`)

## Purpose

One explicit command admits one provider-independent candidate payload against a current-generation
Analysis Finding whose chain is **current**, and appends one immutable canonical Edit Candidate.

```text
admit_edit_candidate(finding, type, start, end, rationale)
    → payload validated and canonicalized
    → anchor Finding resolved; the standing of the admission it hangs from RE-DERIVED (current only)
    → deterministic Application-owned identity
    → immutable record appended atomically
    → idempotent replay (same canonical proposal ⇒ reused, no new row)
```

**Nothing is proposed here.** No candidate is generated and no provider, prompt, model, AI call,
ProcessingRun, ProcessingUnit, UnitExecution, RUNNING state, DomainResult, Review, Final Selection,
or applied edit exists in this contract.

## Finding anchor chain (C-2, C-3, C-8)

Every Candidate anchors to **exactly one** `LectureAnalysisFinding` (`§8.2`) — never the legacy
`AnalysisFinding`, never the `LectureAnalysisInputAdmission` directly, and **never a Lecture
Segment**. `§9.1` already ruled Segment out as anchor *and* as reference; Segmentation (`§7.2`) is a
sibling branch, and the demo admits a full candidate with **zero Segments anywhere** to prove it.

`§9.1`'s mandatory Source Media and Source Timeline provenance still applies; only its form changes
(C-8). It is secured through `Edit Candidate → Analysis Finding → Lecture Analysis Input Admission →
corrected revision → parent raw transcript → Source Timeline → Source Media`, so the row duplicates
none of it — no admission, media, timeline, revision, DomainResult, run, or execution column exists
(test-asserted).

## Admission standing (C-4, C-5)

Standing lives at the **root** of the chain. Every command resolves the Finding, then re-derives the
standing of its admission through the released GOAL-025 `anchor_status` → GOAL-023 `authority_match`
path — no authority resolver is reimplemented — and admits only at `current`.
`superseded_by_authority_change` and `current_authority_ineligible` are explicit refusals; the
released three-value vocabulary is not extended. A missing or malformed Finding reference is refused
**before** standing is evaluated and reported in this boundary's own error type. Standing is never
stored: the table has no currentness, review, or selection column.

## Historical semantics (C-6)

Existing Candidates are never mutated, deleted, or rewritten when upstream authority changes. Only
*new* admission against a non-current chain is refused. When authority returns to a previously
admitted revision, the chain becomes `current` again and the same canonical proposal converges on
its original identity.

## Candidate Type

The released open Application-owned token rule (`^[a-z][a-z0-9_]*$`). `§9.1` leaves the exact key
grammar to implementation "as long as it follows the §8.1 Finding Type precedent", which is this
rule. It is **not** a closed enum and emphatically **not** `§9.2`'s three-key first-slice registry —
that is a legacy provider-slice constraint C-13 did not re-scope, so unregistered tokens are
admissible here and a test asserts it. No alias mapping, case folding, or whitespace normalization.

## Rationale

Required, non-empty after strip, stored **verbatim** and unnormalized, and it **participates in
identity**: a different reason is a different proposal and must never converge onto one record.
Rationale is the reason for the proposed *edit*; it is not the Finding's evidence.

## Time Range

`§9.1`'s contract verbatim: exactly one required range, finite, non-negative, `start <= end`. A
zero-duration range is structurally valid but carries no special canonical meaning; a
whole-recording range is merely a valid range. The range need not equal the Finding's optional range
and is required even when the Finding has none. **No media-duration validation, transcript-boundary
alignment, Candidate-to-Finding containment check, or range reconciliation is applied** — C-9
forbids adding any of them, and a test admits a range far beyond the transcript to assert it.

## Numeric canonicalization

Every boundary — identity derivation, command, domain construction, reconstruction — routes through
the shared `application/canonical_timeline_value.py` primitive extracted in this Goal's first
commit. It coerces to `float`, collapses negative zero, and refuses non-numbers, booleans,
non-finite values, negatives, and magnitudes beyond a double inside this boundary's error family.
GOAL-025 and GOAL-026 each grew their own copy of this logic and the second was written only after
the first had shipped a defect; a third copy is how the next one ships, so the copies were replaced
by one primitive rather than extended.

## Ordering and the ordinal decision — **O-1: no canonical ordinal**

`§9.2` fixes candidate order as "**deterministic transport order only**, carrying no priority or
product meaning". Its duplicate-preservation rule — exact duplicates in one provider response kept
as distinct rows at distinct sequence positions — is a **provider-slice** concern, and C-13 did not
re-scope `§9.2`. `§9.3` C-11 leaves the ordered-batch idiom optional.

This Foundation admits one candidate per command, with no provider and no proposal batch, so there
is no batch position to derive an ordinal from. Inventing one would require a row count,
`MAX(sequence) + 1`, insertion order, or wall-clock — every one of them prohibited. **No ordinal is
stored and none participates in identity**; a test asserts no such column exists.

**Recorded consequence:** two admissions of the *same* canonical proposal under one Finding converge
on one record rather than being preserved as two. That differs from the legacy provider slice, which
preserved exact duplicates — and it is the one place where this generation's behaviour intentionally
diverges. Listing order is a deterministic presentation order by identity, explicitly not an ordinal.

## Identity (C-10)

`lecture-analysis-edit-candidate:<sha256(contract kind/version, finding, candidate type, canonical
range, rationale)>` over canonical JSON. Application-owned; no provider identifier, UUID, timestamp,
rowid, path, DomainResult, execution identifier, or mutable currentness participates, and no ordinal
exists to participate.

## Identity conflict reachability — **Option B**

**Every persisted canonical semantic field participates in identity** — finding, candidate type,
range, rationale, and the contract version pinned to 1 by the model and a schema CHECK. A divergent
payload for an existing identity is therefore **structurally unreachable through this command**,
short of a SHA-256 collision.

The semantic-equality guard in the collision branch is kept regardless, because C-10 requires it
under Option B and because it is the check that would still hold if a later contract narrowed what
participates in identity. It is **not** the last line of defence: a tampered row already fails
identity re-derivation in `__post_init__` while being reconstructed, before the guard is reached —
which is precisely why reaching it in a test requires injecting a query stub.

## Replay and reprocessing (C-11)

Same Finding + same contract version + same canonical content → the same identity, **reused**, no new
row; near-concurrent identical commands converge through the released identity-collision error. A
meaningfully different proposal — different type, range, rationale, or Finding — appends a new
immutable record. Existing Candidates are never mutated. Under O-1, re-proposing the identical
canonical candidate converges rather than appending a duplicate; both behaviours are tested
explicitly so neither is assumed.

## Deterministic provenance (C-7)

Execution-free and marker-free: the contract kind (bound into the identity), the recorded
`candidate_contract_version`, and the immutable anchor. `§9.1` required a `DomainResultReference`
whose sole direct upstream is the anchoring Finding's DomainResult; the `§8.2` Finding creates none,
so that requirement is unsatisfiable in this generation and is legacy-scoped. **No ProcessingRun,
UnitExecution, RUNNING state, or DomainResult is created** — asserted by a delta test showing the
upstream DomainResult count is unchanged.

## Architecture

- `application/canonical_timeline_value.py` — the shared numeric primitive (extracted first).
- `application/lecture_analysis_edit_candidate.py` — model, type and rationale rules, deterministic
  identity, `LectureAnalysisEditCandidateService` (admit_edit_candidate / get / list_for_finding /
  anchor_status).
- `persistence/lecture_analysis_edit_candidate.py` — repository + one atomic `BEGIN IMMEDIATE`
  insert-only transaction; no update or delete method exists.
- `composition.compose_sqlite_lecture_analysis_edit_candidate_service(connection)` — wires the
  released GOAL-025 Finding service (the sole standing path) + the v50 store.
- `analysis_edit_candidate_cli.py` — admit / show / status / list.
- `analysis_edit_candidate_demo.py` + `examples/analysis-edit-candidate/` — deterministic demo with
  a byte-stable, machine-path-free golden covering the thirteen GOAL-027 scenarios.

## Persistence and migration

v49 → v50, strictly additive: one insert-only table `lecture_analysis_edit_candidates` (identity PK;
FK to `lecture_analysis_findings`; non-empty type and rationale CHECKs; non-negative bound CHECKs;
`range_start <= range_end` CHECK; contract-version CHECK; **no ordinal column**). Per C-12 the legacy
`edit_candidates` relation is **not reused** — its mandatory `source_finding_id`, `source_media_id`,
`source_timeline_id`, `processing_run_id`, `unit_execution_id`, and `domain_result_id` could only be
satisfied by fabricating what C-7 prohibits. Legacy tables are unmodified. Chain v1..v49 → v50
preserves all rows; downgrade, direct-skip, and unsupported targets stay rejected. No wall-clock
column exists.

## Validation

Eight integrity-only codes (`LECTURE_ANALYSIS_EDIT_CANDIDATE_*`): anchor missing, legacy-anchor
leak, contract-version mismatch, malformed type, empty rationale, non-canonical range, invalid
range, and identity re-derivation — the last proving the whole canonical binding including
that the stored bound is the exact float that was hashed.

**Which layer actually guards what.** Writing the validator's first tests (this Goal also closed a
repository-wide gap — the GOAL-025/026/027 diagnostics had none) showed that the table CHECKs, which
`PRAGMA foreign_keys = OFF` does not relax, already refuse most of these corruptions outright. So the
codes split in two:

- **Reached by a corruption test** — identity mismatch, anchor missing, malformed type, and
  non-canonical range. These are real guards against writes a client can perform.
- **Schema-guarded, therefore defence-in-depth** — contract version, empty rationale, invalid range,
  and the legacy-anchor-leak probe. A CHECK or the v50 foreign key refuses the write first, so these
  branches can only fire for an out-of-band write (a file produced by another tool, or a row written
  before a CHECK existed). They are **not** substantive new guarantees and are documented as such.

`tests/test_lecture_analysis_validator_diagnostics.py` pins that split for all three contracts and
fails if a new diagnostic code is added without being either exercised or accounted for.

Deliberately **never** flagged: a
superseded or ineligible chain, a historical candidate not currently selected, the absence of a
Review Decision or an export. Validation reads no filesystem, media, or provider.

## Relation to the legacy 042 §9.1 / §9.2 implementation

The released execution-coupled `edit_candidate` module (durable `edit_candidates`, anchored to a
legacy `AnalysisFinding`, requiring a RUNNING unit execution and a DomainResult) remains the
**legacy** generation's realization of PATCH-0012, and `§9.2`'s concrete provider slice stays bound
to it. This contract never reads or writes either (test-asserted zero rows).

## Status

Complete: 93 focused new tests; the complete 2939-test suite passes; schema v50. `§9.2`'s concrete
provider for this generation, and Review (`043`), Export (`044`), and Final Selection, were **not**
re-scoped by PATCH-0032 (C-13); each needs its own approved generation-scope decision.
