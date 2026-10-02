# Same-Source Text + Timing Composition — PATCH-0050 Implementation

- Status: Implementation Record (runtime implementation of an Accepted PATCH; uncommitted working tree at the time of writing)
- Starting point: `PATCH-0050` **Accepted** and applied to `docs/040` (Blueprint 0.8, 2026-10-01) and
  `docs/030 §6.2`; HEAD `9d03eab` with those document changes and the PATCH still uncommitted
- Governing contract: Accepted `PATCH-0050` TX-1…TX-39 — **unchanged**. No Blueprint, PATCH, identity
  recipe, content fingerprint recipe, selection or consumption semantics were altered.
- Schema: **v55 → v56**, one additive relation, single-step migration, no back-fill
- Scope: same-source **text 1 + timing 1** explicit pair only. Mixed sets across sources, batches,
  chaining, same-role automatic resolution, `§20`/subtitle merge and automatic correction stay Deferred.
- Review type: same-session author self-review — not an independent model or human review
- Written: 2026-10-01

## Summary

An explicit pair request now applies one currently Accepted text candidate and one currently Accepted
timing candidate on the same original source segment into one composed replacement inside one
complete immutable Corrected Revision. The composition generation is the single canonical owner of
the two-role provenance; `§20` resolves its lineage role by role; both candidate kinds' histories
list it; the repository validator checks it and single ownership across all four generation kinds.
Verified over the C014-03 human-verified evidence (copy): the delivered SRT changed exactly one cue,
carrying the corrected text **and** the corrected interval together.

## 1. TX / IR coverage

| contract | implementation | verification |
|---|---|---|
| TX-1…TX-4 scope, explicit roles | `SameSourceCompositionGenerationService.generate(text_candidate_id=, timing_candidate_id=)`; `_require_roles` | `ExplicitPairAndScopeTests` |
| TX-5…TX-9 model B authority | `_snapshot` reads each role's current Decision from its own store; no requester, no pair record | `AuthorityAndStalenessTests`, `test_same_reviewer_or_session_is_not_a_guard` |
| TX-10…TX-13 applicability, field ownership | `_snapshot` (own snapshot per role, no subset rule), replacement built from the Raw source | `test_the_pair_composes_both_accepted_values_into_one_replacement`, `test_the_corrected_interval_need_not_be_a_subset_of_the_original` |
| TX-14…TX-17 identity | `derive_composition_digest` (role-keyed JSON), new replacement entity, `UNIQUE` over the full anchor | `IdentityAndIntegrityTests`, `test_a_different_accept_after_re_accept_is_a_different_anchor` |
| TX-18…TX-22 provenance, ownership | `same_source_composition_generations`; `_revision_owned_elsewhere` in **all** writers; validator | `test_validator_flags_…`, `test_existing_writers_refuse_a_revision_owned_by_a_composition` |
| TX-23…TX-26 validation, atomicity | `_require_composed_validity`, reused `_require_combined_validity`, in-transaction `revalidate` | `test_authority_moving_between_verification_and_persist_is_a_stale_failure`, `test_a_persist_failure_leaves_no_partial_result_and_preserves_siblings` |
| TX-27…TX-30 replay, integrity | `_resolve_existing` + `_require_complete_result_integrity` on lookup and collision | `IdentityAndIntegrityTests` (swapped role, payload, membership, fingerprint), concurrency test |
| TX-31…TX-35 `§20` lifecycle | `_RevisionLineage.members` (candidate, decision store) pairs; `_composition_lineage` | `SelectionLifecycleAndHistoryTests` |
| TX-36…TX-37 history | both `generations_for_candidate` readers include compositions | `test_both_candidate_histories_list_the_composition_once_with_both_roles` |
| TX-38 downstream | generation performs no selection; `§21`/`041` untouched | `test_generation_alone_changes_no_selection_or_artifact`, `test_explicit_selection_delivers_both_corrections_in_one_cue` |
| IR 17 migration | `_migrate_v55_to_v56`, `_V56_EXPECTED_COLUMNS` | `tests/test_sqlite_schema_v56_migration.py` (incl. migrated/fresh equivalence + negative control) |
| IR 1, 2, 18, 19 real evidence | C014-03 copy E2E (§8) | durable run directory |

## 2. Persistence design

One additive relation, `same_source_composition_generations`: identity (PK), `corrected_revision_id`
(UNIQUE), `parent_raw_transcript_id`, `replaced_segment_id`, `text_correction_candidate_id`,
`text_authorizing_decision_id`, `timing_correction_candidate_id`, `timing_authorizing_decision_id`,
`replacement_segment_id` (UNIQUE — the composed replacement is pair-dependent and belongs to one
anchor), `content_fingerprint`; `UNIQUE` over the four authority columns (the complete anchor, so a
re-Accept of either candidate is a new anchor); `CHECK (replaced <> replacement)`; typed foreign keys
to both candidate kinds and both decision kinds. The released timing member relation is untouched and
never holds a text identity. Each role's candidate snapshot stays on its candidate record.

Migration `_migrate_v55_to_v56` is strictly additive. Verified: fresh v56, 55→56 row preservation,
every released version 1…55 chaining to 56, downgrade and direct-skip refused, rollback on failure,
migrated/fresh schema equivalence with a negative control, feature gating below v56
(`SchemaFeatureUnavailableError`; the reader degrades to "no composition"), and **zero** composition
back-fill for existing text-only / timing-only siblings.

## 3. Identity encoding

`same-source-composition-generation:<digest>`, `corrected-revision:<digest>` and
`transcript-segment:<digest>:0` where `<digest>` is the SHA-256 of the canonical JSON
`{"base", "source", "text": {"candidate", "authorizing_decision"}, "timing": {...}}`. Roles are JSON
keys, so neither option order nor keyword order can change the digest, and swapping the roles is a
different (and invalid) anchor. The released `content_fingerprint_for` and single-kind recipes are
unchanged.

## 4. Authority snapshot and commit boundary

`_snapshot` fixes, in one pass on the caller's connection, both candidates, both current Accepted
Decisions (each from its own store), the current Raw selection and the source segment, and checks
each role with the snapshot it actually carries. The persistence `revalidate` callback re-derives all
of that **inside** `BEGIN IMMEDIATE` and compares Decision identities against the fixed ones, so an
Accept → different Accept is refused as stale, never adopted. The release-grade test for this drives a
Reject on a separate connection between snapshot and persist and asserts nothing was written.

Three outcomes are distinguished: created; reused from the pre-persist lookup; reused after a
persistence collision. Both reuse paths call the same `_resolve_existing`, which applies the five
TX-28 conditions; a matching fingerprint never substitutes (TX-29). The concurrency test uses two real
connections on one file with a barrier placed after both have found no stored result, so the loser
converges only through the collision path.

## 5. Four-kind ownership

`SQLiteSameSourceCompositionCommandPersistence._revision_owned_elsewhere` consults the text, timing
singleton and timing aggregate relations. In the reverse direction the released text writer gained a
schema-gated `_revision_owned_elsewhere` over the timing and composition relations, and the timing
writer's existing check now also consults the composition relation. The validator adds
`SAME_SOURCE_COMPOSITION_*` checks (dangling references, role authorization by the right kind's
Accept, same-source/base mismatch, broken replacement, broken membership, candidate reference,
ownership collision) and extends the aggregate ownership and singleton kind-collision checks to the
fourth relation.

## 6. `§20` mixed-kind lineage and history

`_RevisionLineage` now carries `members: ((candidate_id, decision query), ...)`; single-kind lineages
pass one store for every member, the composition passes the text store for the text role and the
timing store for the timing role. Applicability is unchanged in meaning: parent Raw current and every
member currently Accepted, no Decision-identity agreement. `_revision_context` / `_lineage_for` try
text → timing → composition.

`generations_for_candidate` on both kinds returns a mixed tuple sorted by identity: the kind's own
records plus `SameSourceCompositionGeneration` entries, which carry both roles. The text CLI `list`
prints composition entries with both roles. No new UI or search surface was added.

## 7. CLI

```text
PYTHONPATH=src python3 -m lectureos.same_source_composition_cli generate \
    --text-candidate correction-candidate:<digest> \
    --timing-candidate timing-correction-candidate:<digest> --database <db>
PYTHONPATH=src python3 -m lectureos.same_source_composition_cli show --generation <id> --database <db>
```

Subprocess tests cover: generate then show; swapped option order reuses; a text identity in the timing
role fails with exit 1; a missing role fails at argparse; a rejected role fails with exit 1 and
writes nothing; the released `corrected_selection_cli select/resolve` accept the composed revision;
`corrected_revision_cli` and `timing_correction_cli generate` are unchanged and the timing set still
refuses a text identity.

## 8. C014-03 evidence E2E (persisted human-verified evidence, copy only)

Durable location: `/Users/hanbyeol/Desktop/LectureOS-review-evidence/C014-03/composition-e2e/run-2026-10-01-a/`
(`manifest.json`, `commands.txt`, `checksums.sha256`, step outputs, `storage/*.srt`, the migrated
working copy). Original repository `C014-03.sqlite3` sha256 `123c9fdc…6749` before and after; the
review packet's checksums unchanged. The copy was made with the SQLite backup API and migrated 55→56
on the copy only; rows and identities preserved; compositions after migration: 0.

Explicit pair (recorded 2026-09-30 Accepts, consumed as-is): text
`correction-candidate:3f872ddf…c8c5` / `correction-candidate-decision:ad814afa…8503`, timing
`timing-correction-candidate:87717f68…f65a` / `timing-correction-candidate-decision:5883610d…81eb`,
source `…485d:2224`. Result: `same-source-composition-generation:f9f6d0cd…a529`, revision
`corrected-revision:f9f6d0cd…a529`, replacement `transcript-segment:f9f6d0cd…a529:0` with text
`"아, 께랑 께서는 달라요. 그래서 일단 께서만 생각하세요."` and interval `[6745.638, 6750.881]`; 2,370
segments, 2,369 unchanged source identities in released order; both authorizing Decisions recorded;
generation alone changed no Decision, selection or artifact; validator healthy at v56; both histories
list the composition once; after process exit the same pair with swapped option order was `reused`.

Delivery: a baseline SRT was produced while the effective transcript was still the Raw Transcript,
then the composed revision was explicitly selected (`corrected_selection_cli select`), then the same
released chain ran again (`effective_subtitle_cli` → `effective_review_cli` → `effective_decision_cli`
→ `effective_selection_cli` → `effective_srt_cli` → `effective_materialize_cli`). Like-for-like
(deterministic passthrough, 2,370 cues each): **one** cue changed — #2225 from
`01:52:01,200 --> 01:52:30,300 / ' 아 깨랑 깨서는 …'` to
`01:52:25,638 --> 01:52:30,881 / '아, 께랑 께서는 …'` — and 2,369 cues byte-identical. Cue count is
context, not the criterion. No new listening, ASR, alignment or Human Acceptance was performed.

## 9. Tests executed

- Focused: `tests.test_same_source_composition_generation` (35), `tests.test_same_source_composition_cli`
  (4, subprocess), `tests.test_sqlite_schema_v56_migration` (12): OK.
- Migration regression: `tests.test_sqlite_schema_v55_migration` re-scoped to the superseded idiom
  (v55 remains supported; chain and equivalence tests now target the current version through v55;
  the v54→v55 step tests still target 55 explicitly); v2/v4/v5/processing-units latest-version pins
  bumped to 56; validator/CLI/E2E reports compare against `SQLITE_SCHEMA_VERSION`.
- Goldens: ten `examples/*/expected/*.json` files changed **only** in `"schema_version": 55 → 56`;
  `repository_validation_acceptance.py`'s hard-coded 55 now reads `SQLITE_SCHEMA_VERSION`.
- Existing composition-boundary tests kept: text-only/timing-only never compose on their own,
  replacement segments are never valid targets, the timing set refuses text identities; the one
  docstring claiming "nothing merges them" was scoped to those paths.
- Full suite on the final state: `PYTHONPATH=src python3 -m unittest discover -s tests` → **Ran 3827
  tests, OK, skipped 0** (previous baseline 3,776; +51 new tests). The first full run had surfaced the ten
  golden version pins and the acceptance-script pin, which were fixed before this final run.
- `python3 -m compileall -q src tests` and `git diff --check` clean. lint/typecheck/format are not
  configured in this repository and were not added.

## 10. Self-review notes

- A text Decision is read only through `SQLiteCorrectionCandidateDecisionRepository`, a timing Decision
  only through `SQLiteTimingCorrectionDecisionRepository`; `_composition_lineage` pairs each role with
  its own store.
- The composition is its own relation and generation kind; the timing set and member relation are not
  reused or widened.
- Every success return passes `_resolve_existing` (reused) or a fresh persist (created); the
  post-collision path re-reads and re-runs the same integrity check.
- `_require_snapshot_unchanged` compares against the Decision identities fixed at request time.
- Ownership is checked by the new writer, by both released writers (reverse direction) and by the
  validator.
- A current Reject blocks new generation and selection but hides nothing from history or lookup.
- The original evidence repository, the review packet and the uncommitted Blueprint/PATCH changes were
  preserved; nothing was staged or committed in this session.

## 11. Known limits and remaining work

- Evaluation-copy E2E only; no operational repository was migrated or written.
- The composition relation has no CLI listing by candidate beyond the released `corrected_revision_cli
  list` (text side) and the application history query (timing side); a timing-side CLI listing was
  not added (no released timing history command exists).
- Commit of this working tree, and any operational rollout, require separate authorization.
