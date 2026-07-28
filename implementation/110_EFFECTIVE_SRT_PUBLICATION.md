# Effective SRT Publication Authority

- Status: Implementation Reference
- Blueprint: the released Human Authority pattern (GOAL-009/GOAL-015) and the released
  append-only per-scope authority idiom (GOAL-011/GOAL-016), applied over GOAL-019 deliveries
  (GOAL-020); no new Blueprint PATCH required
- Schema: v46 (one additive append-only table `subtitle_effective_srt_publications`)

## Purpose

The explicit publication boundary of the effective-transcript subtitle contract generation:
whether one exact successfully delivered subtitle should be considered published — or
withdrawn — within LectureOS.

```text
exact DELIVERED delivery → derived publication eligibility
                         → explicit Human publish / withdraw (HumanActorReference, rationale?)
                         → immutable append-only publication record
                         → derived Current Publication (highest valid sequence per intake)
                         → derived Availability
```

**Delivery ≠ Publication ≠ Availability ≠ network access.** Publication writes no file, creates
no URL, performs no network operation, and implies no recipient acknowledgement. Withdrawal
records authority only — it never deletes the destination file, the Delivery, the
Materialization, or the Artifact. No mutable `is_published` or availability flag exists.

## Publication contract

- Contract kind/version: `effective_srt_publication` v1.
- Closed vocabulary: `publish` (requires one exact target Delivery + persisted Artifact
  lineage) | `withdraw` (forbids a target; requires existing publication history for the scope).
- Scope: a publish command targets one exact Delivery; **Current Publication is derived per
  `TranscriptSourceIntakeId`** (the delivery's artifact scope) — the released selection-scope
  rule. Scope never derives from paths, filenames, or latest rows.

## Eligibility (derived, never persisted)

A NEW publish requires: the delivery exists; its derived state is DELIVERED; its outcome and
lineage are structurally coherent (delivered fingerprint = expected = artifact fingerprint;
materialization lineage agrees). **Destination-observation policy:** when a Delivery Root is
supplied, the destination must currently hold the exact bytes (`destination_missing` /
`destination_mismatch` block); without a root, the repository-proven DELIVERED record suffices
and observation reports `not_observed`. Blocking reasons: `delivery_not_found`,
`delivery_not_delivered`, `lineage_invalid`, `destination_missing`, `destination_mismatch`.
**Historical policy:** a stale/superseded Artifact's successful delivery remains publishable —
publication is Human Authority over one exact delivered realization; artifact currentness is
exposed observationally, never required.

## Identity, fingerprint, replay

Identity: `subtitle-effective-srt-publication:<sha256(contract kind/version, intake scope,
kind, target delivery | null, sequence)>` — scope-, kind-, target-, and sequence-sensitive;
no timestamp, root, rowid, or filesystem state. Content fingerprint (provenance verification,
GOAL-015 semantics): sha256 over intake, kind, target delivery, target artifact, sequence,
publisher, rationale.

- Exact replay (current authority already publishes the same target) → **reused**; no row.
- Same target by another actor → converges on the established state, first-establishing
  provenance preserved (authority is a state, not a command ledger — the GOAL-009 rule).
- Different target → appends; prior publication stays immutable history.
- Withdraw → appends (repeated withdraw reuses); re-publish after withdraw → appends; the same
  target after withdraw is a genuinely new authority transition and appends.

## Current Publication and Availability

Current = highest valid sequence per intake over the validated `previous_publication_id`
chain (`UNIQUE(intake, sequence)`; no `created_at`/rowid/flag). Availability is derived per
scope, in order: no history → `not_published`; current kind withdraw → `withdrawn`; target
Delivery/lineage unresolvable → `unresolvable`; no root supplied → `not_observed`; destination
absent → `destination_missing`; destination diverged → `destination_mismatch`; else
`available`. Filesystem observation never mutates history; publication integrity never depends
on filesystem access (validation reads no files).

## Concurrency and atomicity

One immutable record persists in one atomic BEGIN IMMEDIATE transaction (identity check +
supersession validation inside); on any failure nothing persists and no upstream row changes.
Near-concurrent identical commands converge: the loser's insert collides, re-reads the
canonical current, and reuses only on exact kind/target and fingerprint equality; a divergent
command occupying the slot (publish-vs-withdraw, different target, different provenance)
raises `PublicationConflictError` — never silent last-write-wins.

## Architecture

- `application/effective_srt_publication.py` — model, deterministic identity/fingerprint,
  eligibility, `EffectiveSrtPublicationService` (publication_eligibility / publish / withdraw /
  get / current / history / availability / status), typed errors.
- `persistence/effective_srt_publication.py` — repository + one atomic append transaction with
  supersession validation.
- `composition.compose_sqlite_effective_srt_publication_service(connection, delivery_root=None)`
  — the optional root enables observational availability only; never persisted.
- `effective_publish_cli.py` — eligibility / publish / withdraw / show / history / current /
  availability / status; output separates authority from filesystem observation and states
  that public URLs and recipient acknowledgement are not part of this contract.
- `effective_publish_demo.py` + `examples/effective-publish/` — deterministic demo with a
  byte-stable golden covering the fourteen GOAL-020 scenarios.

## Validation

Nine integrity-only codes (`EFFECTIVE_SRT_PUBLICATION_*`): target-rule violation, dangling
delivery, artifact-lineage mismatch, target-not-delivered, scope mismatch, identity
re-derivation, fingerprint re-derivation, sequence contiguity, broken supersession.
Withdrawals, superseded publications, missing/diverged destination or source files, and
stale/superseded artifacts are deliberately never corruption.

## Status

Complete: schema v46 chains from every released version single-step; 44 focused new tests; the
complete 2606-test suite passes. Public URLs, download endpoints, network transfer, recipient
models, scheduling, and automatic publication remain out of scope.
