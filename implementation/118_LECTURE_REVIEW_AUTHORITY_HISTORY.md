# Review Authority History and Current Selection — Effective-Transcript Generation

- Status: Implementation Reference
- Blueprint: `docs/043` §7.6 + `PATCH-0034` (AH-1…AH-12, Confirmed) — the effective-transcript
  generation's authority-history and current-selection boundary over the GOAL-028 Review records
  (GOAL-029); `§7.4`'s legacy contract and `§7.5` R-1…R-12 are inherited unchanged
- Schema: v52 (one additive append-only table `lecture_review_authority_positions`)

## Purpose

`§7.5` R-9 recorded a gap deliberately: when one person reverses a judgment on one Edit Candidate
(`accept` → `reject` → `accept`), the third submission converges on the first identity, so the
repository holds two contradicting records **with no ordinal, no `previous` link, and no timestamp**,
and nothing says which one is operative. `§7.6` closes that gap for **kind reversal** by adding an
append-only authority history in a separate record.

```text
admit_review_decision(candidate, kind, actor[, approved replacement])
    → the released GOAL-028 admission is unchanged (closed kind, standing re-derived, records built)
    → the (candidate, actor) history head is read
    → head absent → position 0 | head records this decision → REUSED | otherwise → append sequence+1
    → decision + optional approval + position written in ONE transaction, or none of them

current_review(candidate, actor)      → highest sequence, DERIVED from persisted rows, never stored
observe_candidate_authority(candidate) → one actor: that judgment | two or more: a §3.12 Conflict
```

**Nothing new is executed, arbitrated, or exported.** Cross-actor arbitration, a Candidate-level
single winner, Final Selection, Export, applied edits, withdrawal, revocation, correction, the
same-kind/different-approval history, Review UI, and an external API are all outside this milestone.

## The two canonical records are untouched (AH-4)

No ordinal, `previous` link, or status column is added to `lecture_review_decisions` or
`lecture_approved_edit_decisions` (test-asserted). The reason is preservation, not taste: `§7.5`
R-10's released identity composition is `(contract, candidate, decision kind, human actor)`, so
folding a `sequence` into it would change the identity **value** of every already-recorded row and
mutate released meaning — which the additive-evolution contract prohibits. The history therefore
lives in a third record, and both released records keep their exact convergence behaviour.

## Scope: per (Candidate, actor) (AH-6)

Because R-10 keeps the human actor in the decision identity, one Candidate carries **one history per
actor**. `sequence` is contiguous from 0 inside a scope, `sequence = 0` carries no previous,
`sequence > 0` requires exactly one, no position references itself, and `(candidate, actor,
sequence)` is unique.

**One `ReviewDecision` may occupy several positions.** In `accept` → `reject` → `accept` the canonical
records converge to **two** while the history holds **three** positions, with positions 0 and 2
referencing the same `accept` record. A per-decision uniqueness constraint on this relation is
therefore prohibited — it would make reversal history unrepresentable, which is the very case this
subsection exists to close. Both the schema (no `UNIQUE` and no index on `review_decision_id`) and
the validator (which never flags reuse) are tested against that prohibition.

## Append rule (AH-7)

`plan_authority_position(candidate, actor, decision, head)` is a **pure function of that scope's
persisted head**:

| head | submitted decision | outcome |
| --- | --- | --- |
| absent | any | `RECORDED` at `sequence` 0, no previous |
| present | identical to the head's | `REUSED` — nothing is written (idempotent replay) |
| present | different | `RECORDED` at `sequence + 1`, superseding the head |

The `sequence + 1` derivation is what `§7.6` explicitly authorizes and is **not** what R-9 prohibits:
R-9 governs the **per-admission** ordinal, which still does not exist on either canonical record. Row
counts, `MAX(sequence) + 1` over the table, wall-clock, insertion order, rowid, and any ordinal
derived from anything but this exact scope's head remain prohibited; a test appends three actors'
histories and asserts a fourth scope still starts at 0.

## Derived current and the cross-actor boundary (AH-8, AH-9)

`current_review(candidate, actor)` returns the highest-`sequence` position with the `ReviewDecision`
and `ApprovedEditDecision` it references, derived from persisted rows only. There is no stored flag,
no latest-row heuristic, and no observation mutates anything (test-asserted over repeated reads).
Superseded positions stay valid immutable history and are never deleted, rewritten, or re-numbered.

`observe_candidate_authority(candidate)` reports one of exactly three observations — `no_history`,
`single_actor`, `cross_actor_conflict` — and **arbitrates nothing**. With two or more actors it
derives **no** current judgment: that is a `§3.12` Review Conflict to be surfaced. No priority among
actors, no recency across actors, and no role ranking exists anywhere in the implementation, and
`§15.3`'s open multi-user question is declined rather than answered by implication. Per-actor currents
stay derivable during the conflict, which is what lets an interface show a person the difference.

## Standing orthogonality (AH-10)

Appending a position requires `§7.5` R-3's standing to be `current`; the released admission path is
reused unchanged, so a superseded chain refuses the whole admission and no position is written
(test-asserted byte-identical history). Observation is **not** gated on standing — a superseded chain
still has an observable current judgment, and a superseded chain is never corruption. Being the
current judgment is **not** Export eligibility: linking this generation's `ApprovedEditDecision` to
`044` remains a separate decision, and a test asserts the export relations stay empty.

## Identity (AH-11) — composition and reachability

`lecture-review-authority-position:<sha256(contract kind, contract version, candidate, actor,
sequence)>` over canonical JSON, Application-owned. No provider identifier, execution identifier,
`DomainResult`, UUID, timestamp, wall-clock, rowid, path, or mutable currentness participates. This is
the released precedent's shape — `040 §18` H-7 binds `(anchor, kind, sequence)` and keeps the
referenced payload out.

**Participating:** contract kind and version, `candidate_id`, `actor`, `sequence`.
**Persisted but not participating:** `review_decision_id`, `previous_position_id`.

**Reachability accounting: Option A, and it is genuinely reachable.** Because the referenced decision
does not participate, two near-concurrent appends that both computed `sequence + 1` derive the **same
identity** with different content. That is ordinary concurrent input, not a hash collision, and it
must be an explicit conflict:

- identical referenced decision → converge on the stored position, `REUSED`, nothing written;
- different referenced decision → `ReviewAuthorityConflictError`, nothing overwritten
  (`040 §18` H-9).

The semantic-equality check is kept regardless, as AH-11 requires. `previous_position_id` needs no
separate check because it is a deterministic function of the same scope and position.

The compare in AH-12's compare-and-append is the `UNIQUE (candidate_id, actor, sequence)` constraint
evaluated **inside** the transaction, not a read-then-write window: a loser's insert fails and is
mapped to the released identity-collision error, so the application layer converges or refuses.

## Atomicity: two enforcement points, two different times (AH-12)

AH-12 requires an implementation to record both points together, so both are stated here.

- **Write-time (transactional).** The `ReviewDecision`, its optional `ApprovedEditDecision`, and its
  history position are written in **one** `BEGIN IMMEDIATE`: all of them or none. A test injects a
  failure while writing the position and asserts no decision row survives and no transaction is left
  open. The reversal path — a converged decision that still opens a new position — writes the
  position alone in its own transaction, leaving the already-recorded decision and approval exactly
  as they are; a failure there leaves the history byte-identical. Consequently **no admission made
  under this contract can produce a positionless judgment**.
- **Read-time (classification).** A `ReviewDecision` admitted **before** this contract may carry no
  position, and that is **not corruption**. `current_review` returns `None`, the CLI prints "no
  recorded authority history" and states plainly that this does not mean no judgment exists, and the
  validator never flags it. **Retroactive backfill is prohibited** — the ordering between such
  records is persisted nowhere, so any backfill would be fabrication (`040 §18` H-10, `041 §15` E6).
  The next admission for that (Candidate, actor) simply starts the history at `sequence` 0
  (test-asserted).

The converse shape — a position with no judgment — is structurally impossible: the
`review_decision_id` is mandatory and foreign-keyed. The all-or-nothing rule must never be read as
licence to flag a pre-existing positionless judgment.

## Architecture

- `application/lecture_review_authority.py` — `LectureReviewAuthorityPosition`, the deterministic
  identity, `plan_authority_position` (the append rule as a pure function), `CurrentReviewAuthority`,
  `CandidateAuthorityObservation`, and the two error types.
- `application/lecture_review_decision.py` — the released admission extended with position planning
  and settlement, plus the derived queries `authority_history`, `current_review`, `current_approved`,
  and `observe_candidate_authority`. `ReviewAdmissionResult` now carries `position` and
  `position_outcome`; the two outcomes differ exactly in the reversal case.
- `persistence/lecture_review_decision.py` — the same repository and the same single atomic
  transaction, extended with the position insert and the read paths `head_position`,
  `list_positions`, `get_position`, `actors_with_history`. No update or delete method exists.
- `composition.compose_sqlite_lecture_review_service(connection)` — unchanged wiring over the v52
  store.
- `lecture_review_cli.py` — `history`, `current`, and `candidate-authority` added; every judgment now
  also prints its position, sequence, and what it supersedes.
- `lecture_review_authority_demo.py` + `examples/lecture-review-authority/` — deterministic demo with
  a byte-stable, machine-path-free golden covering fifteen scenarios.

## Persistence and migration (AH-12)

v51 → v52, strictly additive: one insert-only table `lecture_review_authority_positions` — identity
PK; FKs to `lecture_analysis_edit_candidates`, `lecture_review_decisions`, and itself for the
previous link; `UNIQUE (candidate_id, actor, sequence)`; non-blank actor CHECK; non-negative
`sequence` CHECK; the `sequence = 0 ⟺ previous IS NULL` CHECK; a no-self-supersession CHECK; and a
contract-version CHECK. **No status, currentness, wall-clock, execution, `DomainResult`, or copied
payload column exists**, and the decision kind, approved range, approved label, and approved
rationale stay owned by the two canonical records and are reached through the reference (AH-5).

The released v51 relations are **not** altered, re-keyed, backfilled, dual-written, or reinterpreted:
a migration test captures the `CREATE TABLE` statements of `lecture_review_decisions`,
`lecture_approved_edit_decisions`, and both legacy Review relations before and after the step and
asserts they are byte-identical, and that the new table starts empty. Every released version v1..v51
chains single-step to v52 preserving all rows; downgrade, direct-skip, and unsupported targets stay
rejected.

**Recorded consequence of the schema gate.** `persistence/lecture_review_decision.py` now requires
schema **v52**, where GOAL-028 required v51. This is contract-driven rather than incidental: AH-12's
write-time obligation makes a positionless post-contract admission inexpressible, and a v51 database
has nowhere to write the position. The released rows are untouched and lose no meaning — a v51
repository reaches v52 through the supported single-step migration, after which its existing
judgments are read normally and classified as "no recorded authority history".

## Validation

Six integrity-only `LECTURE_REVIEW_AUTHORITY_*` codes. **Five are reached by a corruption test**:
position identity mismatch (re-derivation from the stored scope and position), a referenced decision
that does not exist, a position recording **another scope's** judgment, an invalid previous link, and
a non-contiguous scope sequence. The scope probe is deliberately a real guard rather than
defence-in-depth: the foreign key only requires the referenced decision to *exist*, so a position can
point at another person's judgment while the schema stays satisfied, silently moving authority
between scopes. **One is schema-guarded, therefore defence-in-depth**: the contract version, whose
CHECK refuses the write first even with `PRAGMA foreign_keys = OFF`.

Deliberately **never** flagged: a judgment carrying no position (AH-12); several positions
referencing one decision (AH-6's reversal case); a superseded position; contradictory histories held
by different actors on one Candidate (AH-9 makes that a surfaced Conflict, not a defect); a
superseded or ineligible chain. Validation reads no filesystem, media, or provider.

## Status

Complete: 124 focused new tests across records, service, persistence, CLI, demo, migration, and
validator diagnostics; the complete 3192-test suite passes; schema v52. The GOAL-028 atomicity test
was also repaired — its persistence stub had not been updated for the new keyword argument, so it had
stopped exercising the rollback path it names.

Not re-scoped by `PATCH-0034` and therefore still needing their own approved decision: cross-actor
arbitration and the interpretation of authority across actors (`§15.3`), a Candidate-level single
winner, the history representation of a same-kind/different-approval resubmission (which stays R-11's
explicit conflict), withdrawal, revocation, correction of a human judgment, stale detection, Review
Session persistence, a separate full Review History model, multi-Candidate Review Items, Review UI
and external API, provider-assisted Review, confidence/priority/severity/quality score, Final
Selection, and linking this generation's `ApprovedEditDecision` to `044` Export.
