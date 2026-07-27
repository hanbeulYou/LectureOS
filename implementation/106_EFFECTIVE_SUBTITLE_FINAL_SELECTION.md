# Effective Subtitle Final Selection Authority

- Status: Implementation Reference
- Blueprint: GOAL-011 selection idiom + GOAL-015 Human Authority lineage over `docs/041_SUBTITLE_PIPELINE.md`
  §15 subjects (GOAL-016); no new Blueprint PATCH required
- Schema: v42 (one additive append-only table `subtitle_effective_final_selections`)

## Purpose

The explicit Final Selection boundary of the effective-transcript subtitle contract generation: which exact
reviewed candidate is currently the final subtitle for one **intake scope** (`TranscriptSourceIntakeId` — the
same stable scope as every effective-generation authority).

```text
eligibility (derived: current applicable Accept required)
→ explicit select_final(review_subject, selector)
→ immutable append-only selection (candidate + subject + supporting Accept + selector)
→ derived current selection → derived applicability
```

**Accept ≠ Final Selection ≠ export.** An Accept decision never selects; a selection never exports (export is
a later goal); reject/modify are never eligible; the legacy final-selection pipeline is a separate contract
generation, never read or written.

## Eligibility (derived, never persisted)

`eligibility(review_subject_id)` → `SelectionEligibility`: eligible ⇔ the subject's current decision exists,
is `accept`, and is `applicable` (which, per GOAL-015, requires the subject and candidate source to be
current — the conservative stale policy: stale subjects are never eligible for a NEW selection, while existing
selections remain immutable history). Blocking reasons: `no_decision` / `decision_not_accept` /
`decision_not_applicable`; the result also carries the decision, its applicability, and both currentness
values for inspection. No `is_eligible` column exists anywhere.

## Selection record and lineage

`EffectiveSubtitleFinalSelection` binds, immutably and by truthful FKs: the exact candidate, the exact review
subject, the exact **supporting Accept decision observed at command time** (persisted, never inferred later),
and the explicit selector `HumanActorReference` (provenance, never authorization; may differ from the
reviewer and is never inferred from one).

## Identity, replay, current derivation

- Identity: `subtitle-effective-final-selection:<sha256(contract kind/version, intake, candidate, subject,
  supporting decision, sequence)>` — candidate-, subject-, decision-, and sequence-sensitive; selector and
  rationale are fingerprint-verified provenance (`sha256(intake, candidate, subject, decision, sequence,
  selector, rationale)`).
- Replay (GOAL-011 target-match rule): the current selection already binding the exact
  (candidate, subject, supporting decision) triple → **reused** idempotently; a different candidate OR a
  **new supporting Accept for the same subject** → **append** (`recorded` at 0 / `changed`) — changed
  authority lineage never silently reuses an older selection.
- Current: highest per-intake sequence over `UNIQUE(intake, sequence)` with validated
  `previous_selection_id` supersession — derived, never a flag or latest-row heuristic.
- Concurrency: identical near-concurrent commands converge on the collision only when the resolved current
  binds the exact target with an equal fingerprint; a competing different selection surfaces an explicit
  `FinalSelectionConflictError` — an explicit Human command is never silently discarded (the caller
  re-evaluates eligibility and reissues).

## Applicability (derived, never stored)

`applicability(selection)`: `superseded` (not current — checked first) → `supporting_decision_superseded`
(the persisted Accept is no longer the subject's current decision) → `stale_due_to_candidate_source` /
`unresolvable` (from the supporting decision's derived applicability) → `applicable`. Kind, staleness, and
supersession are never corruption; historical selections are immutable.

## Architecture

- `application/effective_subtitle_final_selection.py` — model, eligibility, deterministic identities,
  `EffectiveSubtitleFinalSelectionService` (eligibility / select_final / get / current / history /
  applicability / supporting_decision), typed errors.
- `persistence/effective_subtitle_final_selection.py` — repository (get / get_current / history) + one
  atomic append with supersession validation.
- `composition.py::compose_sqlite_effective_subtitle_final_selection_service`.
- `effective_selection_cli.py` — the `lectureos.effective_selection_cli` entry point.

## CLI

```bash
PYTHONPATH=src python3 -m lectureos.effective_selection_cli eligibility --review-subject <id> --database <db>
PYTHONPATH=src python3 -m lectureos.effective_selection_cli select --review-subject <id> --selector selector:kim --database <db>
PYTHONPATH=src python3 -m lectureos.effective_selection_cli show --selection <id> --database <db>
PYTHONPATH=src python3 -m lectureos.effective_selection_cli history --intake <id> --database <db>
PYTHONPATH=src python3 -m lectureos.effective_selection_cli current --intake <id> --database <db>
PYTHONPATH=src python3 -m lectureos.effective_selection_cli status --selection <id> --database <db>
```

Output always states `export state: not part of this contract`. No `--force`. Exit `0`/`1`; failures leave
the repository unchanged.

## Persistence (schema v42)

One additive append-only table (identity PK; intake/candidate/subject/decision FKs; non-empty selector;
`UNIQUE(transcript_source_intake_id, sequence)`; sequence/previous pairing CHECK; no self-supersession;
64-hex fingerprint). Never updated or deleted; supersession validated in the command transaction. Every
released version v1..v41 chains single-step to v42 preserving all rows; the new table starts empty;
downgrade/direct-skip/unsupported-target rejected.

## Validation (integrity only)

Ten `EFFECTIVE_FINAL_SELECTION_*` codes: four dangling references, lineage mismatch
(candidate/subject/decision/scope), non-Accept supporting decision, identity/fingerprint re-derivation,
sequence contiguity, broken supersession. Deliberately never flagged: superseded selections, stale sources,
later-superseded supporting decisions, absent export/artifact — a selection whose supporting Accept was later
rejected validates healthy (tested). See `implementation/070_REPOSITORY_VALIDATION.md`.

## Deferred (later goals)

SRT export/enforcement over the current applicable selection, physical materialization, the
modified-subtitle authoring path, automatic staleness reactions, and additional selection contract versions.
No placeholders are introduced.
