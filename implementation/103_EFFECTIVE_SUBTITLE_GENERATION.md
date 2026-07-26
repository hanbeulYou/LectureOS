# Effective-Transcript Subtitle Candidate Generation

- Status: Implementation Reference
- Blueprint: `docs/041_SUBTITLE_PIPELINE.md` §15 (E1…E14, GOAL-013) / `patches/PATCH-0029`;
  `docs/040_TRANSCRIPT_PIPELINE.md` §21 S3-15
- Schema: v39 (three additive insert-only tables: `subtitle_effective_candidates`,
  `subtitle_effective_candidate_cues`, `subtitle_effective_candidate_cue_segments`)

## Purpose

The first canonical subtitle generation path of the **effective-transcript contract generation**: an explicit
request acquires one immutable transcript source solely through the GOAL-012 consumption boundary and persists
one immutable Effective-Source Subtitle Candidate with its ordered cue set and exact source-segment lineage.

```text
Explicit request → GOAL-012 consumption binding (exists before generation)
                → deterministic_segment_passthrough v1
                → immutable candidate + ordered cues + exact lineage (one atomic commit)
```

The legacy `subtitle_candidates` family (v12, readiness/review lineage) is a separate contract generation:
never read, never written, never migrated, never dual-written (E1/E2). Candidate existence ≠ review
preparation ≠ review authority ≠ Human Decision ≠ final selection ≠ export eligibility (E13) — no downstream
stage is integrated in this slice.

## Consumer integration (E5)

`SUPPORTED_CONSUMER_KINDS` gains exactly one production kind: `subtitle_candidate_generation`. The generation
service calls `EffectiveTranscriptConsumptionService.consume(...)` — the binding is created (or converged on)
**before** generation and pins the exact source, Raw parent, authority provenance, ordered snapshot, and §19
fingerprint. Generation never resolves authority itself, never re-resolves midway, and never reconstructs
content from current state. No current Raw selection or a selected-but-inapplicable corrected revision fails
**before** any row (binding or candidate) is persisted — never a silent Raw fallback.

## Generator (E6)

`deterministic_segment_passthrough` v1 (parameters v1): one ordered cue per ordered consumed segment; cue
text/timing/ordinal and single-segment lineage are exact pass-throughs of the immutable snapshot. No merging,
splitting, rewriting, normalization, translation, or timing change; no configuration surface. Provenance is
execution-free (no ProcessingRun/UnitExecution — E6); human-correction provenance stays in the transcript
segment lineage (`replaces_segment_id`), never misrepresented as generator provenance; confidence is never
fabricated for corrected text.

## Identity and replay (E7/E8)

- Candidate: `subtitle-effective-candidate:<sha256>` over (consumer kind, intake, binding identity, source
  kind, exact source identity, generator kind, generator version, parameters version). No timestamp, current
  pointer, content-fingerprint-alone, path, or row-order derivation.
- Cue: `subtitle-effective-cue:<sha256>` over (candidate, ordinal, source segment) — insertion timing never
  participates.
- Replay: same binding + same generator semantics → **reused** (no duplicate rows); Raw → Corrected → Raw
  round trip reuses the original Raw candidate (the GOAL-012 binding for the same source is itself reused);
  a different exact source — even with a byte-identical content fingerprint — is a distinct candidate.
- Near-concurrent identical requests converge on the PK/replay-anchor collision
  (`UNIQUE(consumption_binding_id, generator_kind, generator_version, generation_parameters_version)`);
  a structural payload disagreement for one identity is an explicit
  `EffectiveSubtitleGenerationConflictError`, never an overwrite.

## Persistence (schema v39)

One atomic `BEGIN IMMEDIATE` commits the whole graph — candidate row, all cue rows, all cue-segment lineage
rows — or nothing. CHECKs enforce source-kind/exact-source agreement, fingerprint shape, versions >= 1, cue
timing sanity, and `UNIQUE(candidate_id, ordinal)`. FKs bind intake, consumption binding, corrected revision,
parent raw transcript, cue→candidate, and lineage→cue/segment. Insert-only; no cascade deletion; no mutable
`is_current`; no wall-clock column (repository convention: no wall-clock participates anywhere — observability
timestamps were deliberately omitted). Every released version v1..v38 chains single-step to v39 preserving all
rows; legacy tables and rows are untouched.

## Derived currentness (E11)

`currentness(candidate)` loads the candidate's binding and delegates to the GOAL-012
`ConsumptionCurrentness` vocabulary (`current` / `stale_due_to_raw_selection_change` /
`stale_due_to_corrected_selection_change` / `stale_due_to_selected_revision_inapplicability` /
`unresolvable`). Stale candidates are immutable, historically valid records — never corruption, never
auto-regenerated or deleted.

## Architecture

- `application/effective_subtitle_generation.py` — models, deterministic identities,
  `build_passthrough_cues`, `EffectiveSubtitleGenerationService`
  (generate / get / cues / list_for_intake / currentness), typed errors.
- `persistence/effective_subtitle_candidate.py` — repository (get / cues / list_for_intake) + one atomic
  graph insert.
- `composition.py::compose_sqlite_effective_subtitle_generation_service`.
- `effective_subtitle_cli.py` — the `lectureos.effective_subtitle_cli` entry point.

## CLI

```bash
PYTHONPATH=src python3 -m lectureos.effective_subtitle_cli generate --intake <id> --database <db>
PYTHONPATH=src python3 -m lectureos.effective_subtitle_cli show --candidate <id> --database <db>
PYTHONPATH=src python3 -m lectureos.effective_subtitle_cli list --intake <id> --database <db>
PYTHONPATH=src python3 -m lectureos.effective_subtitle_cli status --candidate <id> --database <db>
```

`generate` reports created/reused, binding, source kind/identity, Raw parent, generator kind/version, cue
count, derived currentness, and that no review/decision/selection/export changed. No `--force`. Exit `0`/`1`;
failures leave the repository unchanged.

## Validation (integrity only)

Thirteen `EFFECTIVE_SUBTITLE_*` codes: dangling intake/binding/raw-parent/revision, source-kind disagreement,
binding mismatch (context/source/fingerprint vs the immutable binding), cue-count mismatch, non-contiguous
ordinals, orphan cues/lineage, cue without lineage, cue segment outside the bound snapshot, and v1 passthrough
content mismatch (deterministically recomputable for generator v1 only). Staleness against current authority
is deliberately never flagged — a repository whose candidates are stale from a later Reject validates clean
(tested). See `implementation/070_REPOSITORY_VALIDATION.md`.

## Deferred (later goals)

Bridging effective-source candidates into subtitle review preparation, Human Decisions, final selection, SRT
export, or materialization; additional generators or generator configurations; automatic staleness reactions;
legacy candidate migration or backfill. No placeholders are introduced.
