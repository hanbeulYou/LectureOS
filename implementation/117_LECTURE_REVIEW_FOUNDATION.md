# Review Foundation — Effective-Transcript Generation

- Status: Implementation Reference
- Blueprint: `docs/043` §7.5 + `PATCH-0033` (R-1…R-12, Confirmed) — the effective-transcript
  generation's Review admission boundary, over the GOAL-027 Edit Candidate (GOAL-028); the canonical
  record contract of `ReviewDecision` and `ApprovedEditDecision` is inherited unchanged from
  `docs/043` §7.4 (R-8)
- Schema: v51 (two additive append-only tables `lecture_review_decisions`,
  `lecture_approved_edit_decisions`)

## Purpose

One explicit command records one **human** judgment against a current-generation Edit Candidate and
appends one immutable `ReviewDecision` plus, for `accept` and `modify`, exactly one immutable
`ApprovedEditDecision` — atomically.

```text
admit_review_decision(candidate, kind, actor[, approved replacement])
    → judgment validated (closed kind, human actor, per-kind approved arguments)
    → anchor Candidate resolved; the standing of the admission at the chain root RE-DERIVED (current only)
    → approved snapshot built (accept inherits the candidate's proposal; modify replaces it)
    → deterministic Application-owned identities
    → both records appended in ONE transaction, or neither
    → idempotent replay (same canonical judgment ⇒ reused, no new row)
```

**Nothing is executed here.** None of the three decisions applies an edit (`§7.4` Decision Kind,
inherited by R-8): no cut or delete command, NLE operation, rendering, export serialization, or
automatic edit application exists. No Review Session, Review Item, Review History model, revision,
withdrawal, revocation, current-selection, Final Selection, Export, or Review UI exists either.

## Candidate anchor chain (R-2, R-7)

Every `ReviewDecision` anchors to **exactly one** `LectureAnalysisEditCandidate` (`042 §9.3`) — never
the legacy `EditCandidate` (`042 §9.1`), and never directly to an Analysis Finding, a
`LectureAnalysisInputAdmission`, or a Lecture Segment. A test admits the Finding and Admission
identities as anchors and asserts both are refused. `§7.4`'s cardinality and direction are unchanged;
only the Candidate's generation changes.

`§7.4`'s inherited Source Media and Source Timeline provenance still applies; only its form changes
(R-7). It is secured through `Review Decision → Edit Candidate → Analysis Finding → Lecture Analysis
Input Admission → corrected revision → parent raw transcript → Source Timeline → Source Media`, so
neither row duplicates it — no admission, media, timeline, revision, DomainResult, run, or execution
column exists (test-asserted).

## Admission standing (R-3, R-5)

Standing lives at the **root** of the chain. Every command resolves the Candidate, then re-derives
the standing of its Finding's admission through the released GOAL-027 → GOAL-025 → GOAL-023
`anchor_status` path — no authority resolver is reimplemented — and admits only at `current`.
`superseded_by_authority_change` and `current_authority_ineligible` are explicit refusals; the
released three-value vocabulary is not extended. A missing or malformed Candidate reference is
refused **before** standing is evaluated and reported in this boundary's own error type.

Existing Review records are never mutated, deleted, or rewritten when upstream authority changes —
a reject stays a durable, auditable human decision. Only *new* admission against a non-current chain
is refused, and when authority returns the same canonical judgment converges on its original
identity.

## Decision Kind (R-8)

`§7.4`'s closed set `{accept, reject, modify}`, re-declared locally rather than imported from the
legacy `application.edit_review` module so this generation carries **no source-level dependency** on
that module's execution boundary. An `ast`-based test asserts the module's import graph names none of
`edit_review`, `ExecutionQueryBoundary`, `ProcessingRunId`, `UnitExecutionId`, or `ProcessingState`,
and a second test asserts the two vocabularies are value-for-value identical so they can never
drift. Matching is exact: `Accept`, `ACCEPT`, `" accept"`, and `approve` are refused, never coerced.
This closed human-action vocabulary leaves `042 §9.1`/`§9.3`'s **open** Candidate Type contract
unchanged.

## Per-kind arguments and Modify Ownership (R-8)

| kind | approved arguments | records written |
| --- | --- | --- |
| `accept` | **none** — the snapshot is the Candidate's proposal, inherited verbatim | decision + approval |
| `reject` | **none** | decision only |
| `modify` | **all four** — range start, range end, label, rationale | decision + approval |

`modify` requires the *complete* approved replacement because `§7.4` Modify Ownership forbids
expressing it as a loose patch or delta; a partial argument set is refused. Supplying approved values
to `accept` or `reject` is also refused — accept means accepting the proposal as it stands. The
original Candidate is never mutated either way (test-asserted byte-identical), and the approved
values are owned **solely** by the `ApprovedEditDecision`.

## Approved Candidate Type or label

`§7.4` names "the approved Candidate Type **or** the approved edit label" as alternatives for one
owned value, not as two fields, so one column `approved_label` carries either. Its grammar is the
released open Application-owned key rule (`^[a-z][a-z0-9_]*$`) that `042 §9.3` uses for Candidate
Type, so an approved label is expressible without inventing a vocabulary no Blueprint has defined.
It stays an open vocabulary — never a closed enum — and a test admits a token no registry knows.

## Approved range

`§9.1`/`§9.3`'s range contract verbatim: finite, non-negative, `start <= end`, zero duration
structurally valid. **No media-duration validation, transcript-boundary alignment, containment check
against the Candidate's range, or range reconciliation is applied** — R-8 forbids adding any of them,
and a test approves a range far beyond both the transcript and the Candidate's own range to assert
it. Every boundary routes through the shared `application/canonical_timeline_value.py` primitive, so
integral (`1`) and negative-zero (`-0.0`) spellings can never produce a row whose identity fails to
re-derive.

## Ordinal (R-9)

Neither record stores a per-admission `sequence`; a test asserts no such column exists on either
table. `040 §18`'s per-anchor authority-history ordinal is a **different concept** and is neither
introduced nor denied — it stays `§15.4`-deferred.

**Recorded consequence.** When a person reverses a judgment (`accept` → `reject` → `accept`), the
third submission converges on the first identity and the repository holds two contradicting records
with no ordinal, no `previous` link, and no timestamp. This contract does not adjudicate them:
`list_for_candidate` exposes only that they coexist, and the repository validator deliberately does
**not** flag the coexistence. Closing that gap requires a separate approved PATCH establishing an
authority-history contract analogous to `040 §18` H-5/H-6; the released legacy path has the identical
gap because its `sequence` is a constant.

**Closed for kind reversal (PATCH-0034, GOAL-029).** That separate PATCH now exists: `043 §7.6` adds
an append-only authority history in a **separate** record, so the reversal above is three history
positions over two converged decisions and the current judgment is derived per (Candidate, actor).
Nothing on this page changes — neither record gained a column, the per-admission ordinal still does
not exist, and `list_for_candidate` still adjudicates nothing. A same-kind resubmission with
different approved values stays R-11's explicit conflict. See
`implementation/118_LECTURE_REVIEW_AUTHORITY_HISTORY.md`.

## Identity (R-10)

- `lecture-review-decision:<sha256(contract kind/version, candidate, decision kind, actor)>`
- `lecture-approved-edit-decision:<sha256(contract kind/version, review decision, candidate,
  approved kind, canonical approved range, approved label, approved rationale)>`

Both over canonical JSON, Application-owned. `§7.4`'s **caller-owned identity is legacy-only**; no
provider identifier, execution identifier, `DomainResult`, UUID, timestamp, rowid, path, or mutable
currentness participates, and no ordinal exists to participate.

The **human actor participates** in the decision identity, as R-10 requires: without it two
different people's identical-kind judgments would collide, and Human Authority would lose the meaning
`§7.4` gives it. The actor is validated non-empty and stored verbatim, reusing the released
`HumanActorReference` precedent (`040 §18`'s decision reviewer).

The approved snapshot deliberately does **not** participate in the decision identity: Modify
Ownership makes the `ApprovedEditDecision` the sole canonical authority for those values, and hashing
them into the decision as well would represent the same canonical values in both records. This choice
has a consequence, recorded next, and it keeps each record's identity re-derivable from **its own**
stored columns — which is what the `__post_init__` guard and the validator both rely on.

## Identity conflict reachability — **Option B per row, Option A per admission**

- **Per row: Option B.** Every persisted canonical field of each record participates in that
  record's identity, so a divergent stored payload for an existing identity is structurally
  unreachable short of a hash collision. The semantic-equality guard is kept anyway, as R-10 requires
  under Option B; reaching it in a test needs an injected query stub.
- **Per admission: Option A, and it is genuinely reachable.** The approved snapshot is canonical
  content of the *admission* that does not participate in the decision identity. So the same actor
  submitting `modify` twice on one Candidate with **different** approved values lands on the existing
  decision, and R-11 requires exactly what happens: `ReviewApprovalConflictError`, no overwrite,
  nothing written. Recording two differing approvals for one `ReviewDecision` is impossible by
  contract (`§7.4` allows at most one) and revising a human judgment is `§15.4`-deferred, so refusal
  is the only faithful outcome. A different actor, kind, or Candidate remains a distinct record, so
  R-11's "may be distinct records" list stays realizable.

## Atomicity and replay (R-11)

Both records of an approving admission share one `BEGIN IMMEDIATE`: all-or-nothing. A test injects a
failure while writing the approval and asserts no decision row survives and no transaction is left
open. On replay, the service also verifies the approval side — an approving decision found without
its approval, or a reject found owning one, is refused as a conflict rather than treated as valid.
Near-concurrent identical commands converge through the released identity-collision error.

## Architecture

- `application/lecture_review_decision.py` — both models, the closed kind, the actor and label rules,
  both deterministic identities, `LectureReviewApplicationService` (admit_review_decision / get /
  get_approved / list_for_candidate / anchor_status).
- `persistence/lecture_review_decision.py` — repository + one atomic `BEGIN IMMEDIATE` insert-only
  transaction writing one or two rows; no update or delete method exists.
- `composition.compose_sqlite_lecture_review_service(connection)` — wires the released GOAL-027
  Candidate service (the sole standing path) + the v51 store.
- `lecture_review_cli.py` — accept / reject / modify / show / status / list.
- `lecture_review_demo.py` + `examples/lecture-review/` — deterministic demo with a byte-stable,
  machine-path-free golden covering sixteen scenarios.

## Persistence and migration (R-12)

v50 → v51, strictly additive: two insert-only tables. `lecture_review_decisions` (identity PK; FK to
`lecture_analysis_edit_candidates`; closed `decision_kind` CHECK; non-blank actor CHECK;
contract-version CHECK) and `lecture_approved_edit_decisions` (identity PK; **`review_decision_id`
UNIQUE**; FKs to both parents; `accept|modify` CHECK; non-negative bound CHECKs;
`approved_range_start <= approved_range_end` CHECK; non-empty label and rationale CHECKs;
contract-version CHECK). **No ordinal, status, currentness, execution, DomainResult, Source Media, or
Source Timeline column exists.**

The `UNIQUE` is deliberate and contract-backed: `§7.4` requires at most one `ApprovedEditDecision`
per `ReviewDecision`, so R-12 permits expressing it as a constraint. That is the **opposite in
character** to `042 §7.1`, which declines canonical-set uniqueness so as not to force one canonical
segmentation — and the two uniqueness notions differ in kind (set canonicalization versus 1:1
parent-child cardinality), so neither is authority for the other.

Per R-12 the legacy `edit_review_decisions` and `approved_edit_decisions` relations are **not
reused** — their mandatory legacy Candidate anchor, `domain_result_id`, `processing_run_id`,
`unit_execution_id`, and `sequence` could only be satisfied by fabricating what R-6 and R-9 prohibit.
A migration test captures both legacy `CREATE TABLE` statements before and after the v50 → v51 step
and asserts they are byte-identical. Chain v1..v50 → v51 preserves all rows; downgrade, direct-skip,
and unsupported targets stay rejected. No wall-clock column exists.

## Validation

Fourteen integrity-only codes across the two tables. **Seven are reached by a corruption test**:
decision identity mismatch, decision anchor missing, approval cardinality invalid (both directions —
an approving decision missing its approval, and a reject owning one), approved identity mismatch,
approved label malformed, approved range not canonical, and the cross-generation anchor leak. The
last of those is deliberately **not** classified as defence-in-depth: legacy `edit_candidates`
declares no foreign key and its identity is caller-owned free text, so one identity string can name a
row in both generations while the v51 foreign key is still satisfied — what normally keeps them apart
is the hash-derived prefix, an Application invariant rather than a schema constraint, so a corruption
test drives it.

**Seven are schema-guarded, therefore defence-in-depth**: unknown decision kind, missing actor, both
contract versions, approved kind outside `accept|modify`, empty approved rationale, and invalid
approved range — a CHECK refuses the write first, even with `PRAGMA foreign_keys = OFF`, so those
branches can only fire for an out-of-band write. That split is pinned by
`tests/test_lecture_analysis_validator_diagnostics.py`, which fails if a new code is added without
being either exercised or accounted for.

Deliberately **never** flagged: a superseded or ineligible chain; a reject that approved nothing;
several coexisting judgments on one Candidate, **including contradictory ones** (adjudicating them is
`§15.4`-deferred, not this validator's question); the absence of an export. Validation reads no
filesystem, media, or provider.

## Relation to the legacy 043 §7.4 implementation

The released execution-coupled `edit_review` module (durable `edit_review_decisions` /
`approved_edit_decisions`, anchored to a legacy `EditCandidate`, requiring a RUNNING unit execution,
owning its own Domain Result identity, chaining Domain Results directly, and taking a caller-owned
identity with a constant `sequence`) remains the **legacy** generation's realization of PATCH-0014.
This contract never reads or writes either relation (test-asserted zero rows).

## Status

Complete: 129 focused new tests; the complete 3068-test suite passes; schema v51. `044` Export, the
downstream consumption of this generation's `ApprovedEditDecision`, and every `§15.4` deferred item
(Review Session, Review Item grouping, Review History model, multi-user conflict resolution,
comprehensive authority policy, reconciliation, revision, supersession, withdrawal, revocation, stale
detection, current-selection, Review UI and external API, provider-assisted Review,
confidence/priority/severity/quality score) were **not** re-scoped by PATCH-0033; each needs its own
approved generation-scope decision.
