# Lecture Segmentation Foundation — Effective-Transcript Generation

- Status: Implementation Reference
- Blueprint: `docs/042` §7.2 + `PATCH-0031` (S-1…S-13, Confirmed) — the effective-transcript
  generation's Lecture Segmentation admission boundary, over the GOAL-023 durable analysis input
  (GOAL-026); the canonical Segment record contract is inherited unchanged from `docs/042` §7.1
- Schema: v49 (one additive append-only table `lecture_analysis_segments`)

## Purpose

One explicit command admits an **ordered batch** of provider-independent range payloads against a
**current** Lecture Analysis Input Admission and appends one immutable canonical Lecture Segment per
batch member, atomically.

```text
admit_segmentation(admission, [(start, end), …])
    → batch canonicalized and validated
    → anchor resolved; its authority standing RE-DERIVED at command time (current only)
    → deterministic Application-owned identity per member (batch position = sequence)
    → every pre-existing member verified for semantic equality BEFORE any write
    → missing members appended in one atomic transaction
    → idempotent replay (same ordered batch ⇒ reused, no new row)
```

**Lecture Segmentation ≠ Analysis Execution, ≠ Analysis Finding.** No segmentation is performed and
no provider, prompt, model, AI call, ProcessingRun, ProcessingUnit, UnitExecution, RUNNING state, or
DomainResult exists in this contract.

## Anchor and Finding independence (S-2, S-3)

Every Segment anchors to **exactly one** `LectureAnalysisInputAdmission`, never to the legacy
`EligibleAnalysisInput` and — as `§7.1` states outright — **never to an Analysis Finding**.
Segmentation and Analysis Finding are siblings over the same *kind* of admission: neither requires
the other, and the demo admits a full segmentation with **zero Findings anywhere** to prove it.
Upstream provenance is obtained through the anchor and not duplicated: the row has no intake, source
media, corrected revision, source timeline, or fingerprint column (test-asserted).

## Admission standing (S-4, S-5)

Every command re-derives the anchor's standing through the released GOAL-023 `authority_match` — no
authority resolver is reimplemented — and admits only at `current`.
`superseded_by_authority_change` and `current_authority_ineligible` are explicit refusals; the
released three-value vocabulary is not extended. A missing or malformed reference is refused before
standing is evaluated and reported in this boundary's own error type. Standing is never stored: the
table has no `current`/`stale`/`active`/`ready`/`superseded` column.

## Historical semantics (S-6)

Existing Segments are never mutated, deleted, or rewritten when upstream authority changes. Only
*new* segmentation against a superseded anchor is refused. When authority returns to a previously
admitted revision, the same canonical admission identity becomes `current` again and the same batch
converges on its original identities.

## Ordered batch semantics (S-9)

One command admits **one or more** Segments; an empty batch is refused. **The batch position *is*
the sequence**, so sequences are contiguous from 0 by construction and can never collide within one
command — the caller does not supply them. Input order is the recorded order; a reordered batch is a
different canonical set. Identical ranges at different positions are distinct Segments.

**No uniqueness constraint over (admission, sequence) exists, deliberately.** `§7.1` forbids
canonical-set/uniqueness constraints and does not force one canonical segmentation, so an Admission
may carry several independent batches whose positions legitimately overlap. A
`UNIQUE(admission_id, sequence)` index would violate the contract; a test asserts no index mentions
`sequence`.

## Range semantics (S-8)

`§7.1`'s Minimum Boundary verbatim: exactly one **required single** range per Segment, finite,
non-negative, `start <= end`. Zero-duration ranges are structurally valid and a whole-recording
range is merely a valid range. **No media-duration, transcript-boundary, coverage, gap, or overlap
validation is applied** — S-8 forbids adding any of them here, and the anchor records no timeline
extent to check against. A test admits ranges far beyond the transcript, with gaps and overlaps, and
expects success.

## Numeric canonicalization

Every boundary — identity derivation, batch canonicalization, domain construction, and
reconstruction — coerces bounds to `float` **and collapses negative zero**. This is load-bearing: `json.dumps(1)` is `1` while
`json.dumps(1.0)` is `1.0`, and the column has REAL affinity, so a non-normalized integral bound
would mint an identity the stored row could never re-derive — permanently unreadable and permanently
flagged in an insert-only table. Negative zero is the same trap wearing a different hat: `-0.0 < 0` is False so it passes the
non-negative check, `json.dumps(-0.0)` is `-0.0`, and SQLite stores plain `0.0`. This is the defect
class GOAL-025 discovered in the sibling Finding contract; here both spellings are prevented and
covered by identity, service, persistence, and round-trip tests.

**The same latent negative-zero defect was found in the released GOAL-025 Finding contract while
implementing this milestone.** It was fixed as a *separate* slice with its own commit and its own
entries in `114_LECTURE_ANALYSIS_FINDING.md` and `060_IMPLEMENTATION_STATUS.md`, rather than folded
into this one — a released-contract fix is its own logical change. No stored row was affected.

## Segment Type or Label

**None.** `§7.1` defers Segment Label and label taxonomy, so no label, type, or title field exists.
Nothing was added for implementation convenience.

## Identity (S-10)

`lecture-analysis-segment:<sha256(contract kind/version, admission, sequence, canonical start,
canonical end)>` over canonical JSON. Application-owned; no provider identifier, execution-framework
identifier, UUID4, timestamp, rowid, path, or mutable currentness participates.

## Identity conflict reachability — **Option B**

**Every persisted canonical semantic field participates in identity** (admission, sequence,
range_start, range_end, and the contract version, which is pinned to 1 by the model and by a schema
CHECK). A divergent payload for an existing identity is therefore **structurally unreachable through
this command**, short of a SHA-256 collision.

The semantic-equality guard in the collision branch is retained regardless. It is the only thing
standing between a corrupted or hand-edited row and silent acceptance, and removing it because the
happy path cannot reach it would trade an integrity guarantee for nothing. It is exercised directly
by a tampering-stub test rather than left uncovered.

## Replay and partial pre-existence (S-11)

Same admission + same contract version + same ordered batch → the same identities, **reused**, no new
row. Because identity is per-Segment and no canonical-set constraint exists, a batch may legitimately
overlap another: every pre-existing member is verified for semantic equality **before any write**,
then only the genuinely missing members are inserted. The result reports `recorded_count` and
`reused_count` so a mixed outcome is explicit rather than hidden. Near-concurrent identical batches
converge through the released identity-collision error.

## Deterministic provenance (S-7)

Execution-free and marker-free, following the GOAL-023/GOAL-025 precedent: the contract kind
(cryptographically bound into the identity), the recorded `segment_contract_version`, and the
immutable admitted source (the anchor FK). No `ProcessingRun`, `UnitExecution`, RUNNING state, or
`DomainResult` is created — asserted by a delta test showing the upstream DomainResult count is
unchanged by segmentation.

## Architecture

- `application/lecture_analysis_segment.py` — model, canonicalization, deterministic identity,
  `LectureAnalysisSegmentationService` (admit_segmentation / get / list_for_admission /
  anchor_status).
- `persistence/lecture_analysis_segment.py` — repository + one atomic `BEGIN IMMEDIATE` insert-only
  batch transaction; no update or delete method exists. `list_for_admission` orders by sequence then
  identity — the tie-break is required, since several batches may share a sequence.
- `composition.compose_sqlite_lecture_analysis_segmentation_service(connection)` — wires the released
  GOAL-023 admission service (the sole standing path) + the v49 store.
- `analysis_segment_cli.py` — admit / show / status / list; `--segment START:END` is repeatable and
  the order given is the recorded sequence. Replay exits 0 reporting `reused`; superseded-anchor,
  malformed, unknown, and invalid-payload commands exit 1 persisting nothing.
- `analysis_segment_demo.py` + `examples/analysis-segment/` — deterministic demo with a byte-stable,
  machine-path-free golden covering the fourteen GOAL-026 scenarios.

## Persistence and migration

v48 → v49, strictly additive: one insert-only table `lecture_analysis_segments` (identity PK; FK to
`lecture_analysis_input_admissions`; non-negative sequence CHECK; non-negative bound CHECKs;
`range_start <= range_end` CHECK; contract-version CHECK; **no uniqueness constraint beyond the
identity PK**). The legacy `lecture_segments` relation is **not reused** (S-12): its mandatory
`source_input_id`, `processing_run_id`, `unit_execution_id`, and `domain_result_id` could only be
satisfied by fabricating exactly what S-7 prohibits. Legacy tables are unmodified. Chain v1..v48 →
v49 preserves all rows; downgrade, direct-skip, and unsupported targets stay rejected. No wall-clock
column exists.

## Validation

Six integrity-only codes (`LECTURE_ANALYSIS_SEGMENT_*`): anchor missing, contract-version mismatch,
invalid sequence, non-canonical range (non-float, NaN, or infinity), invalid range (negative or
inverted), and identity re-derivation — the last proving the whole canonical binding, including that
the stored bound is the exact float that was hashed. Deliberately **never** flagged: a superseded or
ineligible anchor, a historical segment no longer in use, several batches sharing a sequence
(contract-correct), or a range exceeding an externally estimated media duration. Validation reads no
filesystem, media, or provider.

## Relation to the legacy 042 §7.1 implementation

The released execution-coupled `lecture_segment` module (durable `lecture_segments`, anchored to
`eligible_analysis_inputs` and requiring a RUNNING unit execution) remains the **legacy**
generation's realization of PATCH-0011; this contract never reads or writes it (test-asserted zero
rows). The two generations coexist exactly as PATCH-0031 S-1 records.

## Status

Complete: 82 focused new tests; the complete 2843-test suite passes; schema v49. `042 §9.1` (Edit
Candidate) still carries its legacy-generation admission boundary and was deliberately **not**
re-scoped by PATCH-0031 (S-13); it needs its own approved generation-scope decision before it can be
implemented in this generation.
