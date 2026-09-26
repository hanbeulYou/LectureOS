# Timing Candidate Generation History Completeness — OI-1

- Status: Implementation Record (bounded read-completeness fix)
- Starting point: **PATCH-0049 milestone closed** (`implementation/146`, commits `2b2a711`, `6184e9c`,
  `e70cbb0`) with OI-1 recorded as a deferred optional improvement
- Governing contract: Accepted `PATCH-0049` — **unchanged**. No Blueprint, PATCH, schema, migration,
  identity, persistence, selection or consumption semantics were touched.
- Schema: **v55 before and after**; no migration
- `PATCH-0048` text+timing same-segment composition gate: `MORE_EVIDENCE_REQUIRED` — unchanged

## Summary

A timing candidate's generation history now reports its singleton **and** every aggregate generation
it is an explicit member of. Before this change the query answered from the released singleton
relation alone, so a candidate applied as part of a multi-candidate generation reported no history
at all.

## 1. Root cause and actual call path

`SQLiteTimingCorrectionGenerationRepository.generations_for_candidate`
(`src/lectureos/persistence/timing_correction_revision_generation.py:193`) selected only from
`timing_correction_revision_generations`. `PATCH-0049` stores a two-or-more-member generation in the
additive `timing_correction_revision_aggregate_generations` header plus
`timing_correction_revision_generation_members`, and that relation was never consulted.

`TimingCorrectionRevisionGenerationService.generations_for_candidate`
(`src/lectureos/application/timing_correction_revision_generation.py:915`) delegates straight to it,
so the application answer was incomplete in exactly the same way.

Measured before the fix: after an aggregate `{A, B}`, querying A returned **0** entries; after also
generating A's singleton it returned **1**, while A had actually participated in **2** generations.

No CLI or test called the timing variant — `corrected_revision_cli list` uses the sibling *text*
service — which is why the gap produced no failing test. It was a latent trap, not a live defect,
and that is why the review classified it Optional rather than Required.

## 2. Query and return-view changes

The fix reuses the member-aware projection that already existed for `PATCH-0049`; no new canonical
entity, table, or storage model was introduced.

- The singleton rows are read exactly as before and derived into one-member
  `TimingCorrectionGenerationView`s through the released `view_of_singleton` — **no back-fill**.
- Aggregate participation is found by `SELECT DISTINCT aggregate_generation_id … WHERE
  timing_correction_candidate_id = ?`, then each header is loaded through the existing
  `_aggregate_view`, which carries the canonical member-count integrity check.
- Results are merged and sorted by generation identity.

Return element type generalises from `TimingCorrectionRevisionGeneration` to
`TimingCorrectionGenerationView`. Nothing is lost: the singleton record's candidate, authorizing
Decision, replaced and replacement segment identities all live on `members[0]`, and
`is_legacy_singleton` still distinguishes the representation. No aggregate is disguised as a
singular record, and no first-member value is promoted into a singular field.

No released contract constrains this query's shape — `docs/` and `patches/` mention neither the
method nor a generation-history result — and the timing variant had no caller, so the generalisation
breaks nothing. The application protocol annotation was updated to match.

## 3. History semantics

**Membership, not resemblance.** Participation is decided by persisted candidate identity and stored
generation membership. A generation is never included because it shares a source segment, has equal
timing or replacement content, is part of the currently selected revision, or because the candidate
is currently Accepted. A pinned test covers the near-miss: two candidates on different segments with
the same interval shape keep separate histories.

**Exactly once per generation.** The two relations are disjoint by construction, and
`UNIQUE(aggregate_generation_id, timing_correction_candidate_id)` prevents a candidate appearing
twice in one generation; the header is loaded once per distinct id. Two aggregates sharing one
replacement entity stay two entries — sharing a replacement is not sharing a generation.

**Complete membership.** The queried candidate filters *which* generations appear; it never trims
the others out of one. Querying `{A, B}` by A and by B returns the same generation with the same
complete member provenance.

**History is not applicability.** A later Reject or a current-Raw switch changes whether a revision
can be used, not what was generated, so historical entries are retained. After Reject then
re-Accept, the two generations authorized by different Decisions are both present and each keeps the
Decision that actually authorized it — nothing is rewritten forward. A REUSED replay adds no entry.
No current-authority guard is applied to this read.

**Ordering** is by generation identity, ascending. That preserves the released singleton
`ORDER BY identity` exactly (the singleton-only result is a subset of the same sort) and extends it
deterministically across both relations. It does not depend on wall clock, database return order, or
UNION execution order, and **it is a stable order, not a chronology**.

**Corruption is surfaced, not hidden.** Deduplication removes only genuine join repetition. A member
row pointing at a missing header raises, and an aggregate whose stored members do not match its
declared `member_count` raises through the existing reader — a damaged aggregate is never returned as
a healthy partial history. No repair, recovery, or back-fill behaviour was added.

**Unknown candidate and empty history** keep the released behaviour: a malformed identity is
rejected; a well-formed identity with no history returns an empty tuple whether or not the candidate
exists.

**Read-only.** Repeated queries leave generations, aggregates, members, revisions and their ordered
membership, candidates, Human Decisions, source and replacement segments, selections, and the schema
version byte-identical.

## 4. Tests and validation

New: `tests/test_timing_candidate_generation_history.py` (19 tests) covering the released singleton
case, aggregate-only participation, singleton plus several aggregates with `G_BC` excluded, shared
replacements staying distinct, complete membership from either member, the equal-timing
different-source boundary, replay, Reject, current-Raw switch, Reject→re-Accept, ordering and
restart determinism, empty and unknown identities, malformed rejection, read-only invariance with no
member back-fill, both corruption paths, and the repository layer answering identically to the
application layer.

Executed in this session:

```text
tests.test_timing_candidate_generation_history            19 tests, OK
affected focused set (multi-candidate, timing generation,
  selection service, corrected_revision_cli, downstream
  E2E, timing validation, text generation service)       134 tests, OK
full suite: PYTHONPATH=src:tests python3 -m unittest discover -s tests -t tests
                                                       3,773 tests, OK (skipped=1)
python3 -m compileall (changed modules)                  OK
git diff --check                                         clean
```

The skip is the pre-existing `faster-whisper is not installed` environment skip. Lint, type-check
and format remain unconfigured in this repository; none was added and `compileall` is not reported as
a substitute for them.

No migration or schema bump was created, and OI-3's migrated/fresh equivalence assertion was not
added. Real-media SRT regeneration is not a completion condition for a read fix and was not
performed; completeness and invariance were verified on synthetic fixtures.

## 5. Self-review

Same-session self-review — **not** an independent model or human PASS. Re-read the diff and the call
path and confirmed: history includes singleton and aggregate; complete membership preserved; no
current-authority filtering; no canonical writes; singleton behaviour and ordering preserved;
schema, identity, fingerprint, generation and selection semantics unchanged; nothing from OI-2, OI-3
or unrelated cleanup mixed in.

## 6. Deferred

- **OI-2** — `_segment_exists` remains unused since verified reuse replaced the collision check.
- **OI-3** — the migration suite still does not assert that a migrated schema equals a freshly
  initialized one.

Neither was changed here.
