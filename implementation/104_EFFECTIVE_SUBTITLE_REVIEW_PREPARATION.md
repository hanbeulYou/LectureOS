# Effective-Source Subtitle Review Preparation

- Status: Implementation Reference
- Blueprint: `docs/041_SUBTITLE_PIPELINE.md` §15 (E11–E14 downstream separation) / `patches/PATCH-0029`
  (GOAL-014)
- Schema: v40 (one additive insert-only table `subtitle_effective_review_subjects`)

## Purpose

The first downstream stage of the effective-transcript subtitle contract generation: an explicit request
prepares one exact immutable candidate graph as an immutable **Review Subject** — the historical fact "this
exact candidate graph was presented for review".

```text
Immutable EffectiveSubtitleCandidate → explicit prepare_review(candidate_id)
                                     → immutable Review Subject (exact graph binding)
                                     → derived candidate-source + review-subject currentness
```

Preparation is preparation only. A Review Subject's existence implies **no** Human Decision, review
completion, reviewer, approval/rejection, decision applicability, final-selection eligibility, or export
eligibility. The legacy review pipeline (ReviewItem, CandidateReference, subtitle review records) is a
separate contract generation: never read, never written, never bridged.

## Exact graph binding

The subject binds the exact candidate graph two ways: a truthful FK to `subtitle_effective_candidates`
(never a generic/ambiguous candidate id) plus a deterministic **candidate graph fingerprint** —
`derive_candidate_graph_fingerprint` over the candidate's immutable provenance (identity, intake, binding,
source kind/identity, Raw parent, snapshot fingerprint, generator kind/version/params, cue count) and the
complete ordered cue set (identity, ordinal, text, timing, ordered source-segment lineage). The fingerprint
is an integrity anchor, never authority, and never replaces the candidate identity. Structural integrity
(cue count, contiguous ordinals, non-empty lineage) is verified at preparation time; a broken graph refuses
preparation with nothing persisted.

## Stale-candidate policy (recorded decision)

A structurally valid but source-stale candidate **may** be explicitly prepared; the result carries its
derived stale currentness. This preserves *historical inspectability ≠ current decision applicability* —
preparation never implies review or decision applicability. (The Blueprint does not decide this; the goal's
preferred default was adopted and is recorded here.)

## Identity and replay

- Identity: `subtitle-effective-review-subject:<sha256>` over (preparation kind
  `effective_subtitle_review_preparation`, preparation version 1, exact candidate identity, candidate graph
  fingerprint). No timestamps, reviewer, latest-candidate, currentness, or row-order derivation.
- Replay anchor: `preparation_key` = `<kind>:v<version>:<candidate-id>` (UNIQUE), plus
  `UNIQUE(candidate_id, preparation_kind, preparation_version)` — one canonical subject per candidate and
  contract. Same candidate → reused; different candidate (even with byte-identical cue content) → distinct;
  a future materially different preparation version yields a distinct subject (never silent cross-version
  reuse).
- Concurrency: near-concurrent identical requests converge on the identity/anchor collision → re-read; a
  payload disagreement for one anchor is an explicit `ReviewSubjectConflictError`, never an overwrite.

## Currentness (derived, never stored)

`status(subject)` returns `candidate_source_currentness` (the full GOAL-012/013 `ConsumptionCurrentness`
vocabulary, unchanged) plus `review_subject_currentness`: `current` / `stale_due_to_candidate_source` /
`unresolvable`. No `is_current` column exists; stale subjects are immutable historical evidence; authority
changes never mutate or auto-re-prepare a subject.

## Architecture

- `application/effective_subtitle_review_preparation.py` — model, deterministic identities/fingerprint/key,
  `EffectiveSubtitleReviewPreparationService`
  (prepare_review / get / subject_for_candidate / status / candidate_of), typed errors.
- `persistence/effective_subtitle_review_subject.py` — repository (get / get_for_candidate) + one atomic
  single-row insert.
- `composition.py::compose_sqlite_effective_subtitle_review_preparation_service`.
- `effective_review_cli.py` — the `lectureos.effective_review_cli` entry point.

## CLI

```bash
PYTHONPATH=src python3 -m lectureos.effective_review_cli prepare --candidate <id> --database <db>
PYTHONPATH=src python3 -m lectureos.effective_review_cli show --review-subject <id> --database <db>
PYTHONPATH=src python3 -m lectureos.effective_review_cli list --candidate <id> --database <db>
PYTHONPATH=src python3 -m lectureos.effective_review_cli status --review-subject <id> --database <db>
```

Output always states `human decision state: not part of this contract` and never displays a fabricated
review status (pending/approved/rejected/completed). No `--force`. Exit `0`/`1`; failures leave the
repository unchanged.

## Persistence (schema v40)

One additive table `subtitle_effective_review_subjects` (identity PK; candidate FK; 64-hex graph
fingerprint; preparation kind/version; UNIQUE preparation key; UNIQUE(candidate, kind, version)).
Insert-only; no mutable status columns; no cascade deletion. Every released version v1..v39 chains
single-step to v40 preserving all rows (GOAL-013 candidate rows and all legacy rows unchanged); the new
table starts empty; downgrade/direct-skip/unsupported-target rejected.

## Validation (integrity only)

Six `EFFECTIVE_REVIEW_SUBJECT_*` codes: dangling candidate, unsupported preparation contract, duplicate
preparation, key mismatch, identity mismatch, graph-fingerprint mismatch (deterministic recomputation
against the actual candidate graph). Deliberately never flagged: stale candidate source, absent Human
Decision/reviewer/selection/export — a healthy repository with an undecided, stale subject validates clean
(tested). See `implementation/070_REPOSITORY_VALIDATION.md`.

## Deferred (later goals)

Human Decisions over review subjects, reviewer assignment, annotations, decision applicability, final
subtitle selection eligibility, export enforcement, additional preparation contract versions, automatic
staleness reactions. No placeholders are introduced.
