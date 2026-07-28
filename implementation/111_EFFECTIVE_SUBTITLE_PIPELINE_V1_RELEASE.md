# Effective Subtitle Pipeline v1 Release

- Status: **Release Closure — Effective Subtitle Pipeline v1 Complete**
- Included Goals: GOAL-013 … GOAL-020 (completion records `implementation/103` … `110`)
- Schema: first release version v39 → latest v46 (prerequisite consumption boundary v38);
  every released version reaches v46 through the supported single-step migration chain
- Release verification: `tests/test_effective_subtitle_pipeline_release.py` (12 cross-stage
  acceptance tests), `python3 -m lectureos.effective_subtitle_release_demo` (byte-stable golden
  at `examples/effective-subtitle-v1/expected/release-summary.json`), deterministic manifest at
  `examples/effective-subtitle-v1/release-manifest.json`

## Release summary

GOAL-013 through GOAL-020 form one coherent released system: a fully explicit, append-only,
Human-authorized pipeline from an effective transcript source to a published, available `.srt`
file. Every transition is an explicit command over one exact typed identity; every current
state is derived from immutable history; every side effect is record-first and honestly
reported; filesystem observation never mutates authority; the legacy subtitle pipeline remains
byte-untouched throughout.

```text
Effective Transcript Source Intake
  → Candidate → Review Subject → Human Decision → Final Selection
  → Logical SRT Artifact → Physical Materialization → Verified Delivery
  → Publication Authority → Derived Availability
```

## Release scope

**v1 includes:** candidate generation; review preparation; Human decisions
(accept/reject/modify); final selection; logical SRT export (canonical serializer, byte-stable);
physical materialization (record-first, hardened local writer); local-copy delivery
(record-first, source- and destination-verified); publication authority (publish/withdraw);
derived availability.

**v1 does not include:** HTTP serving, download endpoints, public URLs, cloud upload, access
control/authentication/authorization, recipient acknowledgement, publication scheduling,
frontend/editor UI, automatic orchestration, Lecture Intelligence.

## Stage and contract map

| Stage | Canonical input | Canonical output | Explicit authority | Persisted representation | Derived states |
|---|---|---|---|---|---|
| Candidate (GOAL-013) | Effective Transcript Source Intake (consumption binding, v38) | immutable candidate cue graph | explicit `generate` command | `subtitle_effective_candidates` (+ cues, cue segments) | source currentness |
| Review (GOAL-014) | Candidate | Review Subject | explicit `prepare_review` command | `subtitle_effective_review_subjects` | subject currentness/applicability |
| Decision (GOAL-015) | Review Subject | accept / reject / modify history | explicit `HumanActorReference` | `subtitle_effective_review_decisions` | current decision, decision applicability |
| Selection (GOAL-016) | accepted subject (current applicable Accept) | Final Selection history | explicit selector | `subtitle_effective_final_selections` | eligibility, current selection, selection applicability |
| Artifact (GOAL-017) | current applicable selection | logical SRT artifact (payload + fingerprint) | explicit export request | `subtitle_effective_srt_artifacts` | artifact currentness |
| Materialization (GOAL-018) | logical artifact | physical file outcome | explicit materialize request | `subtitle_effective_srt_materializations` (+ outcomes) | PENDING/MATERIALIZED/FAILED, file agreement |
| Delivery (GOAL-019) | successful materialization | delivered destination outcome | explicit deliver request | `subtitle_effective_srt_delivery_intents` (+ outcomes) | PENDING/DELIVERED/FAILED, source/destination agreement |
| Publication (GOAL-020) | DELIVERED delivery | publish/withdraw authority | explicit Human publisher | `subtitle_effective_srt_publications` | current publication, availability |

Contract kinds/versions: SRT serializer `canonical_srt` v1 (parameters v1); materialization
storage kind `local_file`; delivery `subtitle_effective_srt_delivery` v1 (`local_copy`);
publication `effective_srt_publication` v1.

## Identity map

Eight distinct typed identity namespaces, each a deterministic sha256 over its contract's exact
payload: `subtitle-effective-candidate`, `subtitle-effective-review-subject`,
`subtitle-effective-review-decision`, `subtitle-effective-final-selection`,
`subtitle-effective-srt-artifact`, `subtitle-effective-srt-materialization`,
`subtitle-effective-srt-delivery`, `subtitle-effective-srt-publication`. No physical path,
filename, URL, timestamp, rowid, or mutable currentness participates in any identity;
actor/rationale provenance participates only in content fingerprints (GOAL-015 semantics).

## Authority and derived-state map

Three distinct Human authorities — review decision (accept/reject/modify), final selection
(selector), publication (publish/withdraw) — plus explicit non-Human commands for generation,
preparation, export, materialization, and delivery. **No stage creates the next stage
automatically** (release-verified: repository loading, validation, status queries, and CLI
inspection never write). Every current state is derived: current decision/selection/publication
(highest valid sequence over validated supersession), artifact currentness, materialization/
delivery states (intent + terminal outcome), availability (authority → delivery resolvability →
optional destination observation). No mutable `is_current`/`is_published` flag exists anywhere.

## End-to-end workflow, replay, and concurrency

The release acceptance suite drives one connected production-service scenario: happy path to
derived availability with exact-byte verification (artifact payload == materialized bytes ==
delivered bytes), full-pipeline exact replay (every stage reuses; zero new rows), reject/modify
blocking downstream authority, new-Accept lineage, candidate replacement with immutable
superseded history, physical/destination deletion preserving history, withdraw/republish
append-only, restart reconstruction of every derived state, healthy full-pipeline validation,
and cross-stage corruption detection.

Concurrency (audited per stage, consistent guarantees): deterministic identity + UNIQUE
sequence anchors make near-concurrent identical commands converge (fingerprint-verified after
collision), and divergent commands raise explicit conflicts (`FinalSelectionConflictError`,
`EffectiveSrtDeliveryConflictError`, `PublicationConflictError`, decision conflict) — callers
re-evaluate and reissue; no silent last-write-wins path exists. First-establishing actor
provenance is preserved on same-state repeated intent (decisions, publications).

## Side-effect boundaries

Materialization and delivery are record-first (immutable intent durable before the write,
verified terminal outcome after; crash residue is an honest PENDING; delivery re-verifies
destination bytes before DELIVERED; reconciliation is explicit and observational). Publication
performs no filesystem write. No SQLite/filesystem atomicity is claimed anywhere. Physical
agreement is always observational (`file_matches`, source/destination agreement,
`not_observed` without a root) and never mutates records or counts as corruption.

## Validator coverage (stage inventory)

All checks are read-only SQL; the validator never reads the filesystem.

- Candidate: `EFFECTIVE_SUBTITLE_*` graph/lineage/identity checks (see `implementation/103`).
- Review Subject: `EFFECTIVE_REVIEW_SUBJECT_*` identity/candidate-graph fingerprint checks.
- Decision: `EFFECTIVE_REVIEW_DECISION_*` identity/fingerprint/sequence/supersession checks.
- Selection: 10 `EFFECTIVE_FINAL_SELECTION_*` checks incl. lineage and decision-not-accept.
- Artifact: 9 `EFFECTIVE_SRT_ARTIFACT_*` checks incl. byte-exact reserialization.
- Materialization: 6 `EFFECTIVE_SRT_MATERIALIZATION_*` checks.
- Delivery: 10 `EFFECTIVE_SRT_DELIVERY_*` checks incl. cross-stage artifact-lineage and
  delivered-fingerprint agreement.
- Publication: 9 `EFFECTIVE_SRT_PUBLICATION_*` checks incl. cross-stage scope and
  target-DELIVERED agreement.

Deliberate non-errors everywhere: stale, superseded, withdrawn, PENDING, FAILED, missing
physical file, missing destination, not observed. The full 070 catalog lists every code.

## CLI and demo inventory

Per-stage CLIs (identities only, never media paths): `effective_subtitle_cli` (candidate),
`effective_review_cli` (subject), `effective_decision_cli` (decision), `effective_selection_cli`
(selection), `effective_srt_cli` (artifact), `effective_materialize_cli` (materialization),
`effective_deliver_cli` (delivery), `effective_publish_cli` (publication). Deterministic demos
with committed goldens exist per stage (`examples/effective-*`), plus the release demo
`python3 -m lectureos.effective_subtitle_release_demo`
(`examples/effective-subtitle-v1/`). No single orchestration CLI exists by design — each stage
remains an explicit command.

## Legacy isolation

The legacy subtitle/export/materialization pipeline is a separate contract generation with
disjoint tables (`subtitle_final_subtitles`, `subtitle_srt_artifacts`,
`subtitle_srt_materializations`, …) and disjoint identity namespaces. The release demo and
acceptance suite assert zero legacy rows after the full effective pipeline; no dual-writes,
shared mutable authority, or altered legacy semantics exist. The legacy path is not deprecated
by this release.

## Known limitations and deferred boundaries

- Delivery/publication observation requires explicitly supplied approved roots; without them
  availability honestly reports `not_observed`. Roots are never persisted.
- Path resolution in the observational readers can create empty contained parent directories
  (inherited from the released writer); a read-only resolve variant is a candidate follow-up.
- Default physical filenames embed identity `:` characters (POSIX-legal; explicit locations
  exist for other filesystems).
- Cross-actor convergence during the narrow collision race window is conservative (explicit
  conflict; reissue converges).
- No serving, URL, access control, acknowledgement, scheduling, frontend, or orchestration —
  all deferred beyond v1 (see manifest `deferred_boundaries`).

## Release verdict

**Effective Subtitle Pipeline v1 Complete.** All eight stages are released, cross-verified as
one coherent system (typed lineage, explicit authority, immutable history, derived state,
honest side effects, legacy isolation), reproducible via the deterministic release demo and
manifest, and protected by the release acceptance suite, per-stage suites, full migration
chain, and read-only repository validation. No release tag was created — the repository has no
tag policy.
