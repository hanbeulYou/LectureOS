# Multi-Candidate Timing Correction Revision Generation — Implementation

- Status: Implementation Record
- Governing contract: **Accepted `PATCH-0049`** (`patches/PATCH-0049-multi-candidate-timing-correction-revision-generation.md`), reflected in `docs/040_TRANSCRIPT_PIPELINE.md` §17/§19/§20 and `docs/030_DATA_MODEL.md` §6.2
- Schema: **v54 → v55**, strictly additive, two new relations
- Related: `139`, `140`, `141`, `142`, `143`, `144`, `145`; `PATCH-0045`…`PATCH-0048`
- `PATCH-0048` text+timing same-segment composition gate: **`MORE_EVIDENCE_REQUIRED` — unchanged**

`implementation/145` is the Architect Decision record and is **not** rewritten here. Where 145 and
this record differ, the Accepted `PATCH-0049` is the governing contract — 145's three superseded
claims (no schema change needed, §20 unchanged, replacement reuse already supported) were already
corrected in its Closure report.

## Summary

A person can now name several accepted timing corrections and have them applied into **one**
immutable Corrected Revision, which flows through the released `§20` selection and subtitle path
unchanged. On the real MVI_0147 evidence this closed the operational ceiling `144` measured: three
human-verified corrections that previously produced three sibling revisions — of which selection
could deliver exactly **one** — now reach the SRT together, each cue moved to the value the listener
measured, text byte-identical, and every other cue unchanged.

## 1. Limited Blueprint/metadata consistency check

Performed before implementation, bounded to the two questions the handoff raised.

**V-2 scope (§3.2).** The `PATCH-0049` note at `docs/040` §19 already scoped the extension
explicitly ("바뀌는 것은 '정확히 하나'라는 개수뿐이다", timing-only, text path unchanged). Two places
still stated an **unconditional** singular rule with no scope marker, ~65 lines from that note:

- V-2's own sentence — "생성은 정확히 **하나의** 후보를 지명하는 명시적 요청이다"
- §19 Canonical Invariant (3) — "revision당 정확히 하나의 후보가 적용된다"

Both were minimally rewritten to carry the scope the Accepted PATCH defines: generation applies only
explicitly named candidates; text keeps exactly one; timing takes a non-empty explicit set; N=1 is a
singleton preserving the released identity. No released prohibition was loosened — apply-all, best,
latest, implicit discovery, merge, ranking and automatic overlap resolution remain forbidden at every
cardinality.

One consequential clause was also scoped: `PATCH-0048`'s gate rationale derived its conclusion from
"정확히 하나". The **conclusion** is unchanged and the gate is unchanged; the rationale now says the
nameable set is restricted to **one kind**, which is why a text and a timing correction on one
segment still produce two sibling revisions that no code path merges.

V-14, S2-14 and the reuse forward notes were re-read and needed no change — the `PATCH-0049` note
already states which single deferral is lifted and how narrowly.

**Metadata (§3.3).** The handoff's `Last Updated: 2026-09-24` was one day ahead of the actual
Asia/Seoul date. Verified `2026-09-23 KST` in the execution environment and corrected the header to
`2026-09-23`. Blueprint version stays **0.7** — it was raised for this PATCH's application and is not
raised again.

**Schema version.** Not pre-reserved. Read the actual migration chain (`_migrate_v53_to_v54` was the
latest step, `SQLITE_SCHEMA_VERSION = 54`), so the next version is **55**.

## 2. Implementation design

Model B — one generation contract whose cardinality is extended — is implemented as one service
method. `generate_set(candidate_ids=…)` is the whole contract; the released
`generate(candidate_id=…)` is a one-element call into it and returns the released result shape
unchanged. There is no parallel generation contract and no second cardinality rule.

| Decision | Choice | Why |
|---|---|---|
| Physical representation | N=1 → released `timing_correction_revision_generations`; N≥2 → two additive relations | A legacy singleton keeps its exact released row and identity (MG-21); `member_count >= 2` makes the two representations structurally disjoint |
| Member provenance | `timing_correction_revision_generation_members`, one row per member | The generation is the single owner of *which* corrections were applied |
| Legacy reading | Derived projection, no back-fill | `SQLiteTimingCorrectionGenerationRepository.view()` returns a released singleton as a one-member `TimingCorrectionGenerationView` |
| Canonical order | Base transcript's source segment ordinal | Input order, timestamps and DB return order never reach identity (MG-16/MG-17) |
| Identity | N=1 released digest; N≥2 digest over base + ordered `(candidate, authorizing Decision)` pairs | MG-21/MG-22 |
| Replacement identity | Per-`(candidate, authorizing Decision)` — already the released recipe | The same member contributes the same entity to `{A,B}`, `{A,C}` and A's singleton (MG-24) |
| Staleness boundary | Application closure re-derived **inside** the write transaction | Guard ordering alone is not TOCTOU protection (MG-13's own warning) |

## 3. Schema and migration (v55)

```sql
timing_correction_revision_aggregate_generations(
  identity PK, corrected_revision_id UNIQUE, parent_raw_transcript_id,
  member_count CHECK (>= 2), content_fingerprint)

timing_correction_revision_generation_members(
  aggregate_generation_id, member_ordinal, timing_correction_candidate_id,
  authorizing_decision_id, replaced_segment_id, replacement_segment_id,
  PRIMARY KEY (aggregate_generation_id, member_ordinal),
  UNIQUE (aggregate_generation_id, timing_correction_candidate_id),
  UNIQUE (aggregate_generation_id, replaced_segment_id),
  UNIQUE (aggregate_generation_id, replacement_segment_id))
```

Deliberately **absent**: any global uniqueness on `(candidate, authorizing_decision)` or on
`replacement_segment_id`. One candidate may participate in several aggregates and one replacement may
be shared across revisions — a global constraint would forbid the contract.

No released column became nullable, polymorphic, or reused. No timing identity was written into the
text-only `correction_candidate_ids`. No canonical relationship is hidden in JSON.

Revision ownership is single across **all three** generation relations. Table-level `UNIQUE` cannot
express that, so it is enforced twice: inside the write transaction
(`_revision_owned_elsewhere` plus the aggregate/singleton existence checks) and in the repository
validator (`TIMING_CORRECTION_AGGREGATE_OWNERSHIP_COLLISION`).

Migration verified in `tests/test_sqlite_schema_v55_migration.py`: fresh v55 initialization; v54→v55
preserving rows and every released table's exact DDL; **every** released version 1…54 reaching v55
through the single-step chain; downgrade and direct-skip refused; a failed step rolling back to v54
with no partial addition; and the decisive property — a released singleton generation surviving with
**zero** member rows written.

## 4. Generation, identity, legacy compatibility

`src/lectureos/application/timing_correction_revision_generation.py`

- `_require_explicit_set` — refuses an empty input, a repeated identity (never silent
  deduplication), and a bare string mistaken for a set.
- `_snapshot` — resolves every named candidate, derives each one's current authority through the
  released `§18` path, refuses a set spanning different intakes/raw transcripts, refuses two
  candidates on one source segment, and verifies each source snapshot. One consistent state.
- Canonical ordering by source ordinal, then per-member replacement construction: source text
  exactly, the accepted interval, everything else preserved.
- `_require_combined_validity` — revalidates the **complete** resulting snapshot for ordering,
  positive duration and non-overlap, reusing `§14` A-10's vocabulary and the released `PATCH-0039` ε.
  No new tolerance. A failure refuses the whole request; nothing is clamped or re-estimated.
- Identity derivation, then existing-result lookup, then persist.

`derive_timing_generation_digest` is untouched; `derive_timing_aggregate_generation_digest` is new and
used only for N≥2. The released content fingerprint recipe is unchanged and stays a separate fact
from entity identity.

## 5. Verified reuse and complete-result integrity

**Replacement reuse (path A)** moved from collision to verification. `_write_replacement` reads the
existing row inside the transaction and compares the **complete** canonical payload and source
lineage — transcript, timeline, text, order, both boundaries, speaker, `replaces_segment_id`,
confidence and uncertainty. Equal: reused unchanged. Different: integrity failure refusing the whole
generation. Never an overwrite, never a repair.

**Existing generation (path B)** and **collision re-read (path C)** run the *same*
`_require_complete_result_integrity`, in this order:

1. content fingerprint differs → the released V-10 conflict error, verbatim;
2. anchor identity, base raw transcript, revision ownership;
3. member count, canonical order, and per-member candidate **and** authorizing Decision;
4. per-member source→replacement pair, plus the stored replacement's canonical payload;
5. the revision's complete ordered segment membership.

A matching fingerprint never substitutes for 2–5. Tests prove each separately: a rebound member
candidate, a swapped replacement, and a genuine membership **reorder** (dense ordinals, same segment
set) are each refused while the content is byte-identical. Non-dense ordinals are repository
corruption and are refused by the released reader first — that guard was not weakened to let the new
check report it.

## 6. Authority, atomicity, concurrency

Authority is verified before identity derivation *and* re-derived inside the write transaction via a
closure the Application owns and Persistence invokes after `BEGIN IMMEDIATE`. Persistence never
decides policy; it owns the transaction boundary.

Atomicity covers replacements, revision, ordered membership, domain result, aggregate header and
complete member provenance. A blocked aggregate insert leaves a byte-identical repository, with the
pre-existing aggregate and its shared replacement untouched.

Concurrency is tested against real separate connections on one database file, not mock call counts:

- **Same anchor** — two services, opposite input orders: one `created`, one `reused`, exactly one
  aggregate row, and the collision path applies the same integrity standard.
- **Shared member** — `G1 = {A, B}` and `G2 = {A, C}`: two distinct valid results, A's replacement
  verified-reused as one entity, and the shared entity never misread as a duplicate request.

## 7. Selection and downstream

`_RevisionLineage.candidate_id` became `candidate_ids`, and applicability requires **every** member's
current authority to be Accepted. A text generation and a legacy timing singleton carry one member,
so their behaviour is identical to before. No agreement between a current Accepted Decision identity
and the historical authorizing Decision is added as a condition.

`§20` still selects exactly one revision. Verified: one member's Reject makes the aggregate
inapplicable while **preserving** the selection record; re-Accept makes it applicable again; a
revision with a rejected member cannot be newly selected; generation alone selects nothing and
creates no artifact.

`timing_correction_cli generate` now accepts a repeated `--candidate`. Nothing else in the CLI
changed and no new UI or bulk-authoring path was added.

## 8. Tests and validation

Commands actually run (the repository has no configured lint, type-check or format tool; none was
added):

```text
PYTHONPATH=src:tests python3 -m unittest discover -s tests -t tests
  baseline (before changes)  : 3700 tests, OK (skipped=1)
  after  (implementation)    : 3754 tests, 11 failures — all schema-version fixtures
  after  (fixtures updated)  : 3754 tests, OK (skipped=1)
python3 -m compileall  (changed modules)  : OK
git diff --check                          : clean
```

New: `tests/test_multi_candidate_timing_correction_generation.py` (44 tests) and
`tests/test_sqlite_schema_v55_migration.py` (10 tests).

A schema bump has a known maintenance surface in this repository, and all of it surfaced as honest
test failures rather than being anticipated:

- **Version pins** — seven released modules assert the current version; advanced 54 → 55.
- **Superseded-latest assertions** — the v54 migration module's three "v54 is the latest" assertions
  became the repository's superseded idiom (`assertLessEqual(54, SQLITE_SCHEMA_VERSION)`), matching
  how v52 and v53 were handled, plus an explicit new downgrade-to-54 rejection.
- **`unsupported target` tests** — 48 modules hardcoded the then-next version (55) as the
  unsupported target, which silently became a *supported* target. All now use
  `SQLITE_SCHEMA_VERSION + 1`, so the assertion stays true across future releases.
- **Chain-test addition blocks** — each module's `_ADDITION_BLOCKS` must cover every version its
  chain test builds a legacy database at. Thirteen modules stopped at 53 and only passed because
  `range(1, SQLITE_SCHEMA_VERSION)` never reached 54. All 47 full-chain modules now derive the list
  from `SQLITE_SCHEMA_VERSION`, so this cannot silently rot again. (v2–v8 build their low-version
  fixtures locally and run no full-chain test; they were left alone.)
- **Golden fixtures** — ten `examples/**/expected/*.json` summaries and the repository-validation
  acceptance script record `schema_version`; all updated 54 → 55. Only that field changed;
  `objects_checked` and every diagnostic stayed identical.

None of these was a defect in the new capability, and none was worked around by weakening an
assertion.

### The PATCH's 24 Implementation Requirements, against real tests

`M` = `tests/test_multi_candidate_timing_correction_generation.py`,
`V55` = `tests/test_sqlite_schema_v55_migration.py`, `E2E` = §9 below.

| IR | Where it is verified |
|---|---|
| 1 | `V55.test_every_released_version_chains_to_v55_preserving_data`, `…_released_relations_keep_their_exact_definition`, `…_singleton_generation_survives_without_member_backfill` |
| 2 | `M.test_the_result_is_a_complete_snapshot_with_every_correction_applied`; `E2E` on the three real corrections |
| 3 | `M.test_input_order_does_not_change_identity_or_content`, `…_members_are_ordered_by_source_segment_ordinal` |
| 4 | `M.test_a_one_member_set_uses_the_released_singleton_identity_and_relation`, `…_the_released_single_candidate_call_is_unchanged` |
| 5 | `M.test_an_empty_set_is_refused`, `…_a_repeated_identity_is_refused_rather_than_deduplicated`, `…_an_explicit_subset_is_permitted`, `…_a_bare_string_is_not_silently_treated_as_a_set` |
| 6 | `M.test_two_candidates_on_one_source_segment_are_refused_by_name`, `…_a_stored_competitor_does_not_block_the_named_choice` |
| 7 | `M.test_an_unknown_identity_refuses_the_whole_set`, `…_a_set_spanning_two_raw_transcripts_is_refused`, `…_a_stale_source_snapshot_refuses_the_whole_set`, `…_one_undecided_member_…`, `…_one_rejected_member_…` |
| 8 | `M.test_individually_admissible_corrections_that_overlap_together_are_refused`, `…_a_combined_validity_failure_clamps_nothing`, `…_touching_boundaries_stay_allowed` |
| 9 | `M.test_a_member_replacement_is_shared_across_aggregates_and_the_singleton` |
| 10 | `M.test_a_corrupted_existing_replacement_refuses_the_whole_generation` |
| 11 | `M.test_reuse_is_refused_when_the_revision_membership_order_differs`, `…_when_a_member_replacement_is_swapped`, `…_corrupt_revision_ordering_is_refused_by_the_repository_reader_first` |
| 12 | `M.test_authority_moving_inside_the_write_transaction_fails_the_request` |
| 13 | `M.test_a_past_acceptance_never_authorizes_under_a_current_reject` |
| 14 | `M.test_re_accept_is_a_new_anchor_not_a_replay` |
| 15 | `M.test_an_identical_request_is_reused`, `…_an_aggregate_survives_restart_and_replays_as_reuse`, `…_reuse_is_refused_when_member_provenance_differs`, `…_when_a_member_is_missing` |
| 16 | `M.ConcurrentAggregateGenerationTests.test_concurrent_identical_requests_converge_on_one_result` (real separate connections; the collision path calls the same `_resolve_existing`) |
| 17 | `M.test_a_persistence_failure_leaves_no_partial_result` |
| 18 | `M.test_generation_alone_selects_nothing`; `E2E` step 5 |
| 19 | `M.test_one_member_reject_makes_the_whole_aggregate_inapplicable`, `…_a_revision_with_a_rejected_member_cannot_be_newly_selected` |
| 20 | `M.test_member_re_accept_makes_the_past_aggregate_applicable_again` (also asserts the authorizing references were not rewritten) |
| 21 | `E2E` — like-for-like SRT, three cues moved, 2,367 unchanged |
| 22 | `V55.test_a_released_singleton_generation_survives_without_member_backfill`; `E2E` preservation checks |
| 23 | `M.test_a_replacement_segment_is_never_a_valid_generation_target`; mixed/text-only sets have no entry point — `generate_set` resolves only timing candidates |
| 24 | `M.test_repository_validation_is_healthy_with_aggregates_present`, `V55.test_schema_version_is_fifty_five`, full suite below |

IR 16's stronger clause — "the collision path cannot accept a stored result the pre-persist path
would have refused" — is satisfied structurally rather than by a separate fault-injection test: both
paths call the same `_resolve_existing`, and there is no second, weaker validator to diverge from.
The concurrency test proves convergence on a real race; the integrity tests prove what
`_resolve_existing` refuses.

## 9. MVI_0147 evaluation E2E

Run on a **copy**; the original evidence database was made read-only first and verified
byte-identical afterwards (`sha256 4d79ad0f…`). No ASR ran, no media was re-listened to, and no Human
Acceptance record was altered. The three corrections are the ones a person actually measured in
`144` — identities read from the evidence, not reconstructed.

```text
copy migrated v54 -> v55, released rows preserved, zero member back-fill

R03 seg …1134  3365.78 -> 3387.89  (+22.11s)  authority=accept
R05 seg …1350  4254.86 -> 4274.02  (+19.16s)  authority=accept
R06 seg …1355  4343.16 -> 4349.16  (+6.00s)   authority=accept

generate_set -> created, one revision, 3 members, each text byte-identical
generation changed no selection, decision, artifact, or legacy generation
explicit selection -> effective corrected_revision
repository validation: v55, 0 diagnostics
restart + reversed input order -> reused, same revision
```

Like-for-like SRT comparison (both `deterministic_segment_passthrough`, 2,370 cues each):

```text
cues changed: 3       all 2,367 others byte-identical

  #1135  00:56:05,780 -> 00:56:27,890   너무 쉽지?
  #1351  01:10:54,860 -> 01:11:14,020   얘들아 사전 잘 볼 줄 알죠?
  #1356  01:12:23,160 -> 01:12:29,160   다 했나요?
```

Each delivered start equals the human-measured value; each text is byte-identical. Cue count is
reported as context, not as the success criterion — the criterion is lineage and value.

Pre-existing artifacts, selections, Human Decisions and the legacy singleton generation rows in the
copy are byte-for-byte unchanged; the new records are purely additive.

**What this E2E is:** verification over persisted evidence derived from real media.
**What it is not:** a fresh listening pass. No new human judgement was produced or implied.

## 10. Remaining scope

Still Deferred and untouched: text-only aggregation, mixed text/timing sets, text+timing same-segment
composition, revision-on-revision chaining, automatic resolution of same-source competition, merge at
`§20` or in the subtitle stage, a batch approval entity, and automatic timing correction.

`144`'s R08 remains uncorrectable: its blocking neighbour is a 0.12 s segment the listener does not
hear, and `PATCH-0049` does not change TC-7's individual admission rule. That is a content question
for the hallucination diagnostic, not a generation question.
