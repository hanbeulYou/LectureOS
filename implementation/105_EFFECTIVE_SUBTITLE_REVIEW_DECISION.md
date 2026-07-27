# Effective-Source Subtitle Review Decisions

- Status: Implementation Reference
- Blueprint: GOAL-009 Human Authority idiom over `docs/041_SUBTITLE_PIPELINE.md` §15 review
  subjects (GOAL-015); no new Blueprint PATCH required
- Schema: v41 (one additive append-only table `subtitle_effective_review_decisions`)

## Purpose

Human Authority for the effective-transcript subtitle contract generation: an explicit command by a
truthful `HumanActorReference` records one immutable Accept/Reject/Modify judgment about one exact
`EffectiveSubtitleReviewSubject`.

```text
EffectiveSubtitleReviewSubject → decide(subject, kind, reviewer)
                               → immutable append-only decision
                               → derived current decision → derived applicability
```

A decision records authority and nothing else: Accept creates no final selection or export
eligibility; Reject deletes nothing; Modify edits nothing (authoring a modified subtitle artifact is
a later, separately scoped goal). `HumanActorReference` is provenance, never authorization; the actor
is always explicit, never inferred.

## GOAL-009 idiom, reused exactly

- **Identity**: `subtitle-effective-review-decision:<sha256(subject, kind, sequence)>` — reviewer and
  rationale are provenance, verified through the content fingerprint
  (`sha256(subject, kind, sequence, reviewer, rationale)`), never identity.
- **Repeated intent**: a request whose kind already matches the current authority is **reused**
  idempotently (authority is a state, not a ledger of identical utterances — the released GOAL-009
  rule; there is consequently no separate command-id: the replay identity is the
  (subject, kind, sequence) slot plus payload-fingerprint verification).
- **Changed judgment**: appends sequence+1 with `previous_decision_id` supersession; the current
  decision is the highest sequence — derived, never a latest-row heuristic or mutable flag.
- **Concurrency**: near-concurrent identical commands converge on the identity collision with
  fingerprint verification; a divergent payload for one slot is an explicit conflict, never an
  overwrite.

## Subject binding and integrity

Every decision binds one exact review subject (FK to `subtitle_effective_review_subjects` only). At
decision time the subject's candidate graph is re-verified against its immutable graph-fingerprint
anchor; a broken graph refuses new authority with nothing persisted. **Recorded stale-subject
policy** (mirrors GOAL-014): an explicit decision over a structurally valid but source-stale subject
is allowed — human historical judgment ≠ current downstream applicability.

## Applicability (derived, never stored)

`applicability(decision)`: `superseded` (not the current decision) / `applicable` (current decision +
current subject) / `stale_due_to_candidate_source` / `unresolvable` (from the GOAL-014 subject
currentness). Kind is never applicability — reject and modify decisions can be current and
applicable. Integrity is reported separately by the validator.

## Architecture

- `application/effective_subtitle_review_decision.py` — model, closed vocabulary
  (accept/reject/modify via canonical `DecisionKind`), deterministic identities,
  `EffectiveSubtitleReviewDecisionService`
  (decide / get / current / history / applicability / subject_status), typed errors.
- `persistence/effective_subtitle_review_decision.py` — repository (get / get_current / history) +
  one atomic append with supersession validation.
- `composition.py::compose_sqlite_effective_subtitle_review_decision_service`.
- `effective_decision_cli.py` — the `lectureos.effective_decision_cli` entry point.

## CLI

```bash
PYTHONPATH=src python3 -m lectureos.effective_decision_cli decide --review-subject <id> --decision accept --reviewer reviewer:kim --database <db>
PYTHONPATH=src python3 -m lectureos.effective_decision_cli show --decision <id> --database <db>
PYTHONPATH=src python3 -m lectureos.effective_decision_cli history --review-subject <id> --database <db>
PYTHONPATH=src python3 -m lectureos.effective_decision_cli current --review-subject <id> --database <db>
PYTHONPATH=src python3 -m lectureos.effective_decision_cli status --decision <id> --database <db>
```

Output always states `final selection state: not part of this contract` and
`export state: not part of this contract`; no fabricated workflow states. No `--force`. Exit `0`/`1`;
failures leave the repository unchanged.

## Persistence (schema v41)

One additive append-only table (identity PK; subject FK; kind CHECK IN accept/reject/modify;
non-empty reviewer; `UNIQUE(review_subject_id, sequence)`; sequence/previous pairing CHECK; no
self-supersession; 64-hex content fingerprint). Never updated or deleted; supersession is validated
in the command transaction (previous exists, same subject, sequence−1). Every released version
v1..v40 chains single-step to v41 preserving all rows; the new table starts empty;
downgrade/direct-skip/unsupported-target rejected.

## Validation (integrity only)

Six `EFFECTIVE_REVIEW_DECISION_*` codes: dangling subject, unsupported kind, identity re-derivation,
fingerprint re-derivation, non-contiguous sequence, broken supersession. Deliberately never flagged:
reject/modify kinds, superseded decisions, stale subjects/candidate sources, and the absence of a
final selection or export — a healthy repository with a superseded reject history validates clean
(tested). See `implementation/070_REPOSITORY_VALIDATION.md`.

## Deferred (later goals)

Final subtitle selection eligibility over accepted subjects, export enforcement, the modified-
subtitle authoring path implied by Modify, review annotations/comments, reviewer assignment and
authorization, and additional decision contract versions. No placeholders are introduced.
