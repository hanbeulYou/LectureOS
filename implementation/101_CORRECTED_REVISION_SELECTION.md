# Current Corrected Revision Selection and Effective Transcript Resolution

- Status: Implementation Reference
- Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` §20 (GOAL-011) / `patches/PATCH-0027`
- Schema: v37 (one additive append-only table `corrected_revision_selections`)

## Purpose

The first explicit, append-only authority deciding **which immutable Corrected Revision (§19), if any, is
currently selected for an intake's transcript context** — including an explicit **Raw Transcript fallback** —
plus the deterministic **effective-transcript resolver**. Four distinctions are preserved throughout:

```text
Revision existence ≠ Revision selection ≠ Revision applicability ≠ Effective resolution
```

A revision never becomes current implicitly (not by recency, uniqueness, acceptance, generation success, or
validation). Selection mutates nothing upstream and never auto-promotes, auto-clears, or silently falls back.

## Authority model

- **Owner/context**: the intake (`TranscriptSourceIntakeId`) — the same stable context as §16 Raw selection. A
  revision's context derives from its own lineage (generation → candidate admission → intake), so unrelated
  contexts cannot compete and the CLI derives context from the revision.
- **Two actions**: `corrected_revision` (revision required) and `raw_fallback` (revision absent; CHECK-enforced —
  never a fake revision). **No-history** and **explicit fallback** derive the same effective state but are
  historically distinguishable.
- **Append-only** (§16/§18 idiom): per-intake `sequence` + `previous_selection_id`; current = highest sequence,
  always derived — no `is_current`, no mutable pointer, no timestamp ordering.
- **Identity**: SHA-256 of `(intake, kind, revision-or-none, sequence)`; reviewer (`HumanActorReference`) and
  rationale are provenance, not identity.
- **Replay matrix**: same semantic target → `reused` (no row; a different rationale alone never appends);
  different target → append (`recorded` at sequence 0, else `changed` with the superseded state). Near-concurrent
  identical requests converge; divergent concurrent requests surface an explicit collision for retry.

## Eligibility vs applicability

- **Write-time eligibility** (new selection; no `--force`): the revision must exist with its §19 generation
  binding; its parent Raw Transcript must be the intake's **current** Raw selection; its candidate's current §18
  authority must be **Accepted**. A currently-Rejected candidate's revision is historically valid but not newly
  selectable (`RevisionNotEligibleError`).
- **Query-time applicability** (existing selection; never mutates history): `parent_raw_transcript_not_current`
  (Raw selection switched) or `candidate_not_accepted` (later Reject). An inapplicable selected revision is an
  explicit state — never corruption, never auto-fallback/reselection, never hidden as "no selection".

## Effective transcript resolver

`resolve_effective_transcript(intake)` returns an explicit `EffectiveTranscript`:

| selection_state | effective_kind | meaning |
|---|---|---|
| `no_history` | `raw_transcript` | nothing ever selected → authoritative Raw Transcript |
| `raw_fallback` | `raw_transcript` | explicit fallback → authoritative Raw Transcript |
| `corrected_revision_selected` | `corrected_revision` | selected and applicable |
| `corrected_revision_selected` | `inapplicable_selection` | selected but inapplicable, with reason — **no silent fallback** |

This is the stable query contract for future downstream consumers (validation/subtitle/review/export); **no
existing consumer is switched** in this slice.

## Architecture

- `application/corrected_revision_selection.py` — `CorrectedRevisionSelection`, `SelectionKind`,
  `SelectionState`, `SelectionApplicability`, `EffectiveTranscript`/`EffectiveKind`,
  `CorrectedRevisionSelectionService` (select_revision / select_raw_fallback / current / history /
  selection_state / applicability / resolve_effective_transcript), typed errors, deterministic identity.
- `persistence/corrected_revision_selection.py` — repository (get / get_current / history) and one atomic
  `BEGIN IMMEDIATE` append with supersession validation.
- `composition.py::compose_sqlite_corrected_revision_selection_service`.
- `corrected_selection_cli.py` — the `lectureos.corrected_selection_cli` entry point.

## CLI

```bash
PYTHONPATH=src python3 -m lectureos.corrected_selection_cli select --revision <id> --reviewer <actor> --database <db>
PYTHONPATH=src python3 -m lectureos.corrected_selection_cli fallback --intake <id> --reviewer <actor> --database <db>
PYTHONPATH=src python3 -m lectureos.corrected_selection_cli status  --intake <id> --database <db>
PYTHONPATH=src python3 -m lectureos.corrected_selection_cli history --intake <id> --database <db>
PYTHONPATH=src python3 -m lectureos.corrected_selection_cli resolve --intake <id> --database <db>
```

`select` derives the context from the revision, reports recorded/reused/changed, the previous state, the derived
current selection and applicability, and that no revision content was mutated. `status` distinguishes
no-history / explicit fallback / selected(+applicability); `resolve` never silently falls back for an
inapplicable selection. No `--force`/`--latest`/`--best`/`--auto`/`--repair`/`--clear-history`. Exit `0`/`1`;
failures leave the repository unchanged.

## Persistence (schema v37)

```sql
CREATE TABLE corrected_revision_selections (
    identity TEXT PRIMARY KEY,
    transcript_source_intake_id TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('corrected_revision', 'raw_fallback')),
    corrected_revision_id TEXT,
    reviewer TEXT NOT NULL CHECK (length(trim(reviewer)) > 0),
    sequence INTEGER NOT NULL CHECK (sequence >= 0),
    previous_selection_id TEXT,
    rationale TEXT CHECK (rationale IS NULL OR length(trim(rationale)) > 0),
    UNIQUE (transcript_source_intake_id, sequence),
    CHECK ((kind = 'corrected_revision' AND corrected_revision_id IS NOT NULL) OR
           (kind = 'raw_fallback' AND corrected_revision_id IS NULL)),
    CHECK ((sequence = 0 AND previous_selection_id IS NULL) OR
           (sequence > 0 AND previous_selection_id IS NOT NULL)),
    CHECK (previous_selection_id IS NULL OR previous_selection_id <> identity),
    FOREIGN KEY (transcript_source_intake_id) REFERENCES transcript_source_intakes(identity),
    FOREIGN KEY (corrected_revision_id) REFERENCES corrected_transcript_revisions(identity)
)
```

Append-only; strictly additive; every released version v1..v36 chains single-step to v37 preserving all rows;
downgrade / direct-skip / unsupported-target migrations rejected; no cascade deletion.

## Validation (integrity only)

`CORRECTED_SELECTION_DANGLING_INTAKE` / `_DANGLING_REVISION` (broken references),
`_KIND_REVISION_DISAGREEMENT` (kind vs revision presence), `_CONTEXT_MISMATCH` (selected revision's lineage does
not belong to the selection's intake), `_SEQUENCE_NONCONTIGUOUS`, `_BROKEN_SUPERSESSION`. Deliberately **not**
flagged (§52 applicability, not integrity): a selected revision whose candidate is now Rejected, whose Raw
parent is no longer current, a superseded selection, Raw fallback, or absent history — a healthy repository with
a later-Rejected selected revision validates clean (tested). See `implementation/070_REPOSITORY_VALIDATION.md`.

## Deferred (later goals)

Downstream integration of the resolver (transcript validation, subtitle generation, review preparation, export),
revision ranking/recommendation, automatic selection or fallback, multi-candidate revisions, revision chaining,
mutable annotations, workflow/publication statuses, and review UI. No placeholders are introduced.
