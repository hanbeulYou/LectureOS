# Effective Subtitle SRT Artifact Generation

- Status: Implementation Reference
- Blueprint: released canonical SRT serialization (`application/srt_payload`) + GOAL-016 selection
  authority over `docs/041_SUBTITLE_PIPELINE.md` §15 (GOAL-017); no new Blueprint PATCH required
- Schema: v43 (one additive insert-only table `subtitle_effective_srt_artifacts`)

## Purpose

The logical export boundary of the effective-transcript subtitle contract generation: an explicit
request over one exact, **current, applicable** `EffectiveSubtitleFinalSelection` serializes the
selected candidate's immutable cue graph into a canonical SRT payload and records it as an
immutable **logical** artifact.

```text
export eligibility (derived: current + applicable selection)
→ explicit generate_srt_artifact(final_selection_id)
→ canonical SRT payload (released serializer, byte-deterministic)
→ immutable artifact (exact selection/candidate lineage + content fingerprint)
```

**Final Selection ≠ Artifact ≠ physical file.** Artifact existence never implies a file, path,
URL, materialization, or delivery — physical materialization is a later, separately scoped goal;
the legacy export pipeline is a separate contract generation, never read or written.

## SRT serialization contract (`canonical_srt` v1, parameters v1)

Reuses the released pure primitives (`serialize_srt_cues` / `format_srt_timestamp` /
`srt_milliseconds`) verbatim:

- index base **1**, blocks in canonical cue-ordinal order;
- timestamps `HH:MM:SS,mmm`, seconds→milliseconds with **ROUND_HALF_UP**; hours widen beyond two
  digits naturally (no cap); negative or non-finite times rejected;
- durations that collapse at millisecond precision (`end_ms <= start_ms`) rejected;
- LF line endings; one blank line between blocks; a single trailing LF on non-empty payloads; the
  empty cue sequence yields the empty payload (unreachable here: artifacts require >= 1 cue);
- text preserved exactly (multiline text flows as-is; no rewriting, wrapping, merging, splitting,
  or timing correction); canonical UTF-8 encoding;
- untimed cues refuse serialization explicitly (`ArtifactCandidateGraphError`).

## Export eligibility (derived, never persisted)

`export_eligibility(final_selection_id)`: eligible ⇔ the selection exists, is the **current**
selection of its scope, and its GOAL-016 applicability is `applicable`. Blocking reasons:
`selection_not_found` / `selection_not_current` / `selection_not_applicable`. Superseded, stale,
or inapplicable selections never generate a new artifact; existing artifacts remain immutable
history. No `is_exportable` column exists anywhere.

## Identity, fingerprint, replay

- Content fingerprint: SHA-256 of the canonical UTF-8 payload — an integrity witness, **never**
  identity (byte-identical SRT under different selections stays distinct).
- Identity: `subtitle-effective-srt-artifact:<sha256(contract kind/version, exact final selection,
  candidate, serializer kind/version/params, content fingerprint)>` — selection-, candidate-,
  serializer-version-, and content-sensitive; no path/filename/URL/timestamp/rowid inputs.
- Replay anchor: `UNIQUE(final_selection_id, serializer_kind, serializer_version,
  serialization_parameters_version)` — one canonical artifact per selection and serializer
  contract; identical replay reuses; a future incompatible serializer version yields a distinct
  artifact; collision converges only on complete payload equality, else explicit
  `SrtArtifactConflictError`.

## Currentness (derived, never stored)

`currentness(artifact)` maps the bound selection's GOAL-016 applicability: `current` /
`superseded_by_final_selection` / `supporting_decision_superseded` /
`stale_due_to_candidate_source` / `unresolvable`. Stale/superseded artifacts are immutable valid
history; no automatic regeneration exists.

## Architecture

- `application/effective_subtitle_srt_artifact.py` — model, eligibility, serializer bridge
  (`serialize_effective_cues`), deterministic identities,
  `EffectiveSubtitleSrtArtifactService`
  (export_eligibility / generate_srt_artifact / get / list_for_intake / currentness), typed errors.
- `persistence/effective_subtitle_srt_artifact.py` — repository
  (get / get_for_selection / list_for_intake) + one atomic single-row insert.
- `composition.py::compose_sqlite_effective_subtitle_srt_artifact_service`.
- `effective_srt_cli.py` — the `lectureos.effective_srt_cli` entry point.

## CLI

```bash
PYTHONPATH=src python3 -m lectureos.effective_srt_cli eligibility --selection <id> --database <db>
PYTHONPATH=src python3 -m lectureos.effective_srt_cli generate --selection <id> --database <db>
PYTHONPATH=src python3 -m lectureos.effective_srt_cli show --artifact <id> --database <db>
PYTHONPATH=src python3 -m lectureos.effective_srt_cli content --artifact <id> --database <db>
PYTHONPATH=src python3 -m lectureos.effective_srt_cli list --intake <id> --database <db>
PYTHONPATH=src python3 -m lectureos.effective_srt_cli status --artifact <id> --database <db>
```

`content` emits the exact canonical payload to stdout. Output always states
`materialization state: not part of this contract` and `physical path: not part of this
contract`. No `--force`. Exit `0`/`1`; failures leave the repository unchanged.

## Persistence (schema v43)

One additive insert-only table (identity PK; intake/selection/candidate FKs; serializer contract
CHECKs; cue_count >= 1; non-empty TEXT payload; 64-hex fingerprint; the replay-anchor UNIQUE).
No path/filename/URL/materialized column exists. Every released version v1..v42 chains
single-step to v43 preserving all rows; the new table starts empty;
downgrade/direct-skip/unsupported-target rejected.

## Validation (integrity only)

Nine `EFFECTIVE_SRT_ARTIFACT_*` codes: three dangling references, lineage mismatch, unsupported
serializer, identity/fingerprint re-derivation, cue-count mismatch, and byte-identical
**reserialization** of the stored payload from the bound immutable cue graph (via the shared pure
`srt_payload` primitives — deliberately one algorithm, no drift). Deliberately never flagged:
superseded/stale artifacts, later-superseded supporting decisions, and missing physical
materialization (tested healthy). See `implementation/070_REPOSITORY_VALIDATION.md`.

## Deferred (later goals)

Physical SRT materialization (paths, files, overwrite policy, delivery), export enforcement
workflows, additional serializer versions, and automatic staleness reactions. No placeholders are
introduced.
