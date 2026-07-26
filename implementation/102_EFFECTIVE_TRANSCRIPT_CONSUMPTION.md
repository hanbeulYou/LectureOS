# Effective Transcript Consumption Boundary

- Status: Implementation Reference
- Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` §21 (GOAL-012) / `patches/PATCH-0028`
- Schema: v38 (one additive insert-only table `effective_transcript_consumptions`)

## Purpose

The shared application boundary through which downstream transcript-derived operations acquire **one
immutable transcript source**: resolution through the sole §20 resolver, consumability validation, snapshot
loading by exact immutable source identity, and a stable deterministic **consumption binding**. Five
distinctions are preserved throughout:

```text
Current authority ≠ Consumed source ≠ Historical binding lineage ≠ Binding currentness ≠ Repository integrity
```

A downstream operation consumes one immutable source — never a moving selection pointer. Authority changes
after acquisition never rewrite, delete, or reinterpret a binding.

## Acquisition model

- **Sole resolution authority**: `CorrectedRevisionSelectionService.resolve_effective_transcript` (§20). No
  consumer re-derives selection/acceptance/parent/fallback logic. The resolver result additively exposes the
  authority records it observed (`raw_selection_id`, `corrected_selection_id`) — provenance only, no new
  resolution meaning.
- **Consumability**: no current Raw selection → explicit failure; selected-but-inapplicable corrected revision
  → `InapplicableSelectedRevisionError` with the resolver's reason — **never a silent Raw fallback**.
- **Immutable loading**: segments load by the resolved source identity (Raw Transcript or Corrected Revision
  `segment_ids`) — never back through current authority, so a mixed-source snapshot is impossible. A revision
  whose immutable parent disagrees with the observed authority state fails truthfully (retryable race).
- **Canonical input**: `EffectiveTranscriptInput` — intake context, observed resolver state
  (`no_history`/`raw_fallback`/`corrected_revision_selected`), source kind (`raw_transcript` |
  `corrected_transcript_revision`), exact source identity, exact Raw parent, authority provenance, the ordered
  canonical `TranscriptSegment` snapshot (text/timing/speaker/`replaces_segment_id` lineage and provider/human
  provenance pass through untouched), and the §19 `content_fingerprint_for` fingerprint reused verbatim.

## Consumption binding

`EffectiveTranscriptConsumption` (persisted, insert-only): identity
`transcript-consumption:<sha256>` derived from `(consumer kind, intake, source kind, exact source identity)` —
authority provenance and fingerprint are recorded facts, not identity. The row records the exact source, the
Raw parent, the observed raw/corrected selection authority, and the deterministic manifest (segment count +
content fingerprint). Replay: same consumer + same source → **reused** (no duplicate row; recorded provenance
remains the first observation); different source → distinct binding; near-concurrent identical requests
converge on the persistence collision; fingerprint disagreement for one identity is an explicit
`ConsumptionConflictError`.

## Bounded first consumer

`transcript_consumption_manifest` — a neutral deterministic manifest whose persisted output is the binding
itself. The legacy validation/readiness and subtitle-intake boundaries were investigated and rejected as first
consumers: they live on the §4.6–§4.8 path (legacy `TranscriptCurrentSelection`, ApplicabilityEvaluation,
ReviewItem/CandidateReference, RUNNING executions) and cannot join the §13–§20 chain without fabricated
execution machinery. `SUPPORTED_CONSUMER_KINDS` admits only the manifest kind; further consumers are separate
milestones. No ProcessingRun, DomainResult, Artifact, or physical file is created (truthful provenance of a
deterministic local transformation).

## Derived currentness (never stored)

`currentness(binding)` compares the binding with the current resolver result: `current`,
`stale_due_to_raw_selection_change`, `stale_due_to_corrected_selection_change`,
`stale_due_to_selected_revision_inapplicability`, `unresolvable`. There is no `is_current`/`is_stale` flag,
no automatic reprocessing, regeneration, or deletion. Stale bindings are historically valid — never
corruption.

## Architecture

- `application/effective_transcript_consumption.py` — canonical input, binding model, deterministic identity,
  `EffectiveTranscriptInputService` (acquisition), `EffectiveTranscriptConsumptionService`
  (consume / bindings / currentness), typed errors.
- `persistence/effective_transcript_consumption.py` — repository (get / list_for_intake) and one atomic
  `BEGIN IMMEDIATE` insert.
- `composition.py::compose_sqlite_effective_transcript_consumption_service`.
- `transcript_consumption_cli.py` — the `lectureos.transcript_consumption_cli` entry point.

## CLI

```bash
PYTHONPATH=src python3 -m lectureos.transcript_consumption_cli resolve-input --intake <id> --database <db>
PYTHONPATH=src python3 -m lectureos.transcript_consumption_cli consume       --intake <id> --database <db>
PYTHONPATH=src python3 -m lectureos.transcript_consumption_cli status       --intake <id> --database <db>
```

`resolve-input` reports resolver state, authority provenance, source kind/identity, Raw parent, segment count
and consumability; `consume` reports created/reused, the binding, and that nothing was mutated; `status` lists
bindings with derived currentness. No `--force`/`--latest`/`--best`/`--auto`/`--repair`/`--clear-history`.
Exit `0`/`1`; failures leave the repository unchanged.

## Persistence (schema v38)

One additive table `effective_transcript_consumptions`: PK identity; UNIQUE replay anchor
`(consumer_kind, transcript_source_intake_id, source_transcript_identity)`; CHECK-enforced source-kind /
source-identity / resolution-state consistency (Raw fallback and no-history are never fake revisions; a
corrected consumption always records its observed corrected-selection authority); FKs to intakes, raw
transcripts, corrected revisions, raw selections, and corrected selections; fingerprint and non-negative
segment count. Insert-only; strictly additive; every released version v1..v37 chains single-step to v38
preserving all rows; downgrade / direct-skip / unsupported-target rejected; no cascade deletion.

## Validation (integrity only)

`CONSUMPTION_DANGLING_INTAKE` / `_DANGLING_RAW_SOURCE` / `_DANGLING_REVISION_SOURCE` / `_DANGLING_SELECTION`
(broken references), `_SOURCE_KIND_DISAGREEMENT`, `_PARENT_MISMATCH`, `_AUTHORITY_MISMATCH` (immutable
observed-provenance consistency), `_FINGERPRINT_MISMATCH` (deterministic manifest recomputation against the
bound snapshot). Deliberately **not** flagged (§21 S3-11): a binding whose source is no longer effective —
later Reject, Raw switch, changed corrected selection, later fallback. A healthy repository containing stale
bindings validates clean (tested). See `implementation/070_REPOSITORY_VALIDATION.md`.

## Deferred (later goals)

Switching transcript validation / subtitle generation / review preparation / export / analysis to this
boundary; automatic staleness reactions (reprocessing, regeneration, invalidation, deletion); additional
consumer kinds; multi-source or merged consumption; content-based cross-source deduplication; physical
materialization. No placeholders are introduced.
