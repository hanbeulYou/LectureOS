# Explicit Effective SRT Delivery

- Status: Implementation Reference
- Blueprint: the released record-first side-effect discipline (044 §17 / PATCH-0007) and the
  hardened released local writer, applied as an outbound boundary over GOAL-018 materializations
  (GOAL-019); no new Blueprint PATCH required
- Schema: v45 (two additive insert-only tables `subtitle_effective_srt_delivery_intents` /
  `subtitle_effective_srt_delivery_outcomes`)

## Purpose

The explicit delivery boundary of the effective-transcript subtitle contract generation: an
explicit request records that one exact successful physical Materialization's bytes were copied
to one exact destination beneath an approved Delivery Root, through one delivery mechanism, with
one honest terminal outcome.

```text
successful materialization → explicit deliver(materialization, location?, overwrite?)
                           → source bytes verified against the artifact fingerprint (pre-intent)
                           → immutable intent (PENDING, durable BEFORE the destination write)
                           → contained atomic local copy of the exact bytes
                           → destination bytes re-verified
                           → immutable terminal outcome (DELIVERED | FAILED)
```

**Artifact ≠ Materialization ≠ Delivery ≠ Publication.** Delivery never regenerates SRT content
and never mutates Artifact or Materialization records. Delivery success never implies
publication, a URL, public availability, download access, notification, or recipient
acknowledgement — none exist in this contract. Destination paths never affect Artifact identity;
a later deleted destination file never mutates any record.

## Delivery contract

- Contract kind/version: `subtitle_effective_srt_delivery` v1.
- Delivery kind: `local_copy` (the only implemented mechanism; anything else is
  `unsupported_delivery_kind`).
- Default destination location: `<artifact-id>.srt` (repository precedent; convenience
  provenance only, validated identically to explicit locations; contains `:`, which some
  filesystems do not support — pass an explicit `--location` there).

## Eligibility (derived, never persisted)

A materialization is deliverable only when it exists, its derived state is MATERIALIZED, its
artifact lineage is structurally valid (artifact exists and fingerprints agree), and its source
file exists beneath the Storage Root with bytes matching the artifact's content fingerprint.
Blocking reasons: `materialization_not_found`, `materialization_not_materialized`,
`source_file_missing`, `source_file_mismatch`, `source_path_unsafe`, `artifact_lineage_invalid`,
`unsupported_delivery_kind`. **Historical policy:** a structurally valid successful
materialization with a matching source file remains deliverable even when its artifact is
superseded or stale — delivery operates over one exact immutable physical realization
(the GOAL-018 historical-operability rule).

## Record-first lifecycle (released discipline, reused)

Source-side defects block **before** any intent is persisted (nothing recorded, nothing
written). The immutable intent is durable before the destination write; the immutable terminal
outcome is appended after post-write byte verification; state (PENDING | DELIVERED | FAILED) is
always derived, never stored. Destination-side failures are honest FAILED outcomes with stable
categories: `destination_exists_different`, `destination_unsafe`, `destination_missing`,
`write_failed`, `verification_failed`. DELIVERED records the verified delivered fingerprint and
byte count. One terminal outcome maximum per intent; outcomes are never overwritten; a retry is
a new intent. No atomicity across SQLite and the filesystem is claimed — a crash between intent
and outcome leaves an honest dangling PENDING.

## Identity, sequence, and concurrency

`subtitle-effective-srt-delivery:<sha256(contract kind/version, materialization, artifact,
delivery kind, destination location, expected fingerprint, per-pair sequence, overwrite
policy)>` — no absolute root, timestamp, rowid, or mutable state participates. Append-only
attempt history per (materialization, destination location): contiguous sequence from 0,
validated `previous_delivery_id` linkage, `UNIQUE(materialization, location, sequence)` as the
replay/concurrency anchor. Near-concurrent identical requests coordinate through the durable
intent: the loser's insert collides, re-reads the canonical record, and converges (reusing a
terminal DELIVERED, or reporting the honest PENDING) — a divergent payload occupying the slot
raises an explicit conflict, never silent loss.

## Replay, overwrite, reconciliation

- Exact replay: latest attempt DELIVERED + destination bytes still match → **reused**, no
  rewrite, no new intent.
- DELIVERED but destination deleted → a new explicit request appends the next attempt and
  re-delivers; history is immutable.
- Existing different destination, `overwrite=false` (default) → FAILED
  (`destination_exists_different`), destination untouched.
- Explicit overwrite → a NEW append-only attempt atomically replaces the file (never a mutation,
  never reinterpreted as replay).
- Existing identical destination → truthful successful delivery (idempotent physical agreement).
- `reconcile(delivery)` explicitly closes one dangling PENDING intent from destination
  observation only (never writes): matching bytes → DELIVERED; missing → FAILED
  (`destination_missing`); different → FAILED (`verification_failed`); a terminal delivery
  reconciles idempotently to its existing outcome. Reconciliation never runs during repository
  validation.

## Architecture

- `application/effective_srt_delivery.py` — models, deterministic identity, eligibility,
  `EffectiveSrtDeliveryService` (delivery_eligibility / deliver / reconcile / get / state /
  outcome / status / source_path / destination_path / list_for_materialization), typed errors.
- `infrastructure/local_effective_srt_delivery_writer.py` — the GOAL-018 hardened writer plus
  contained `path_of` resolution (for aliasing rejection and distinct path reporting); no safety
  property weakened.
- `persistence/effective_srt_delivery.py` — repository + the two atomic transactions of the
  record-first lifecycle with supersession validation.
- `composition.compose_sqlite_effective_srt_delivery_service(connection, storage_root,
  delivery_root)` — both approved roots are explicit; neither is persisted.
- `effective_deliver_cli.py` — eligibility / deliver / show / status / list / reconcile;
  honest FAILED outcomes exit 1; pre-intent validation failures exit 1 persisting nothing;
  output distinguishes artifact/materialization/delivery identities and source/destination
  physical paths, and states that publication and recipient acknowledgement are not part of
  this contract.
- `effective_deliver_demo.py` + `examples/effective-deliver/` — deterministic demo with a
  byte-stable golden covering the fourteen GOAL-019 scenarios.

## Destination safety

Explicit absolute Delivery Root; destination-relative locations only; empty, absolute, and
parent-traversal locations rejected; symlink targets and escaping resolution rejected by the
released containment rules; source/destination aliasing (the destination resolving to the
materialized source file) rejected pre-intent; partial destination visibility avoided via the
released atomic temp-file discipline.

## Validation

Read-only, logical integrity only (never reads the filesystem): dangling materialization,
artifact-lineage disagreement, expected-fingerprint disagreement, unsafe stored location,
identity re-derivation, per-pair sequence contiguity, broken supersession, orphan outcome,
unsupported failure category, delivered-fingerprint disagreement
(`EFFECTIVE_SRT_DELIVERY_*`). PENDING intents, FAILED outcomes, missing/diverged
source or destination files, and stale/superseded artifacts are deliberately never corruption.

## Status

Complete: schema v45 chains from every released version single-step; 56 focused new tests; the
complete 2562-test suite passes. Publication, URLs, network transfer, recipient
acknowledgement, and additional delivery mechanisms remain later, separately-gated milestones.
