# PATCH-0049

- Title: Multi-Candidate Timing Correction Revision Generation (040 §19/§20)
- Status: Accepted
- Priority: Medium
- Trigger: `implementation/144`'s real-media E2E produced three accepted timing corrections on one
  lecture and measured that the released model can deliver one; the follow-up Architect Decision,
  Closure (CC-1…CC-6) and Generation Replay Boundary Verification closed the contract questions
- Created: 2026-09-23
- Target Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` (§19 V-1/V-2/V-7/V-8/V-9/V-10/V-11/V-13/V-14
  notes and a new subsection; §20 S2-8/S2-9/S2-14 notes; §17 TC-7 clarification note; header
  amended) **and** `docs/030_DATA_MODEL.md` §6.2 (one conceptual clause naming the
  generation-to-member relationship, deferring its operational contract to `040` §19).
  `docs/041_SUBTITLE_PIPELINE.md` is **not** amended.

---

## Status

**Accepted.** Applied to `docs/040_TRANSCRIPT_PIPELINE.md` (Blueprint 0.7, 2026-09-24) as additive
notes on `§17` TC-7, `§19` V-1/V-2/V-7/V-8/V-9/V-10/V-11/V-13/V-14 and `§20` S2-8/S2-9/S2-14, plus the
new `§19` subsection *Multi-Candidate Timing Correction Revision Generation* carrying MG-1…MG-38 and
its Canonical Invariants; and to `docs/030_DATA_MODEL.md` `§6.2` as one conceptual clause naming the
generation-to-member relationship and deferring its operational contract to `040 §19`.
`docs/041_SUBTITLE_PIPELINE.md` and `§21`'s consumption boundary are unamended.

**What acceptance means here, precisely:**

- **Product contract approved and reflected in the Blueprint.** The 24 Acceptance Criteria above are
  document-completeness checks and were each verified against the amended Blueprint text.
- **Implementation pending.** No production code or test was written. The released runtime still
  applies exactly one candidate per generation and still treats an existing replacement segment as a
  collision rather than performing verified reuse.
- **Schema and migration pending.** `SQLITE_SCHEMA_VERSION` remains **54**. The additive persistence
  extension this contract requires has not been designed or applied.
- **Runtime and E2E verification not performed.** The 24 Implementation Requirements below remain
  outstanding; none was executed, and none is marked complete by this acceptance.

It introduces **no automatic candidate discovery, no ranking, no latest-wins, no conflict
resolution, no revision chaining, no selection-layer merge, no new Human Authority entity, no
historical exact-replay operation, and no new threshold or tolerance.** It requires a **strictly
additive** persistence extension, designed at implementation time.

## Context

`PATCH-0047` released Human Timing Correction. `implementation/144` drove it end to end on real
media: a person listened to eight diagnostic findings from MVI_0147, judged four mis-timed, and three
became canonical corrections with recorded Accept decisions. The delivered SRT moved by 22.11 seconds
on one cue with its text byte-identical.

The same record measured the ceiling. Three accepted corrections produced three sibling revisions,
and selecting the second dropped the first out of the effective transcript. At `implementation/137`'s
~8 material cases per lecture-hour, a lecture needing several corrections can ship one.

This PATCH proposes the narrowest extension that lifts that ceiling.

## Current released contract

`§19` V-2 states that generation is *"정확히 **하나의** 후보를 지명하는 명시적 요청"* and excludes
*"apply-all/best/latest·암묵적 후보 발견·multiple-candidate merge·ranking·overlap 해소"*. `§19` V-14
defers *"multiple-candidate 적용/merge/구성"*; `§20` S2-14 defers *"multi-candidate revision"*. The
same deferral appears in the PATCHes that introduced these sections — `PATCH-0026` ("no
multiple-candidate merge", "multiple-candidate application/merge/composition" deferred) and
`PATCH-0027` ("multi-candidate" deferred).

**The released implementation follows the contract exactly.** This is not an implementation defect.
It is a deliberate first-slice limit that a new product requirement now asks to extend.

`§20` selects one revision (S2-3, and a single nullable revision under a `CHECK`). That boundary is
sound and is preserved here; what needs extending is the cardinality of `§19` generation and, as a
consequence, the cardinality assumed by `§20`'s applicability derivation.

## Evidence and Architect Decision basis

**Repository evidence.** `docs/040` §17 K-1…K-14 and TC-1…TC-21; §18 H-1…H-14; §19 V-1…V-14; §20
S2-1…S2-14; §21 S3-1. `PATCH-0026`, `PATCH-0027`, `PATCH-0047`, `PATCH-0048`. Production:
`application/timing_correction_revision_generation.py`,
`application/corrected_revision_generation.py`, `application/corrected_revision_selection.py`,
`persistence/timing_correction_revision_generation.py`,
`persistence/corrected_revision_generation.py`, `persistence/sqlite.py`. Reports
`implementation/144` and `implementation/145`.

**Architect basis.** The decisions below come from three reviews supplied by the Product Owner in
session — the Multi-Candidate Architect Decision, its Closure (CC-1…CC-6), and the Generation Replay
Boundary Verification. Of these, only `implementation/145` exists as a repository file; **the Closure
and the Replay Verification are user-supplied Architect reports and are cited as such**, not as
repository paths.

**Authority.** An Architect report being committed does not approve a normative Product Contract.
Released Blueprint text and Accepted PATCHes are the baseline; this document is the proposal.

**Corrections carried forward.** `implementation/145` contains statements this PATCH does **not**
adopt: that no schema change is needed, that `§20` is entirely unchanged, that replacement identity
is already revision-independent and reuse already supported, and that the scope covers text
aggregation. The Closure corrected the first three; the scope is narrowed here. That report is not
modified by this PATCH.

**Product evidence.** MVI_0147's three corrections were recorded in an **evaluation measurement
database copy**, not in a canonical production repository. They establish the requirement; they are
not production records.

## Decision

### Scope and base

**MG-1 (Proposed) — Model B, timing-only.** The released `§19` generation contract is extended to
accept an **explicit set** of accepted Timing Correction Candidates, applied into **one** immutable
`CorrectedTranscriptRevision`. A separate parallel generation contract is not introduced: two
cardinality rules for sibling paths in one section is the asymmetry that produced the defect
`implementation/141` fixed.

**MG-2 (Proposed) — Base.** All members share one Raw Transcript with consistent source timeline and
lineage, and that Raw Transcript must be the intake's current Raw selection under the released
applicability rules (V-4). A set spanning different Raw Transcripts or timelines is refused.

**MG-3 (Proposed) — One candidate per source segment.** An aggregate contains at most one timing
candidate per source segment. Members target **different** source segments.

**MG-4 (Proposed) — Complete snapshot, not a delta.** The result is a complete
`CorrectedTranscriptRevision` in V-1's released form: ordered segment references, unchanged source
segments keeping their identity, and each corrected segment a revision-scoped `TranscriptSegment`
carrying `replaces_segment_id`. Text and every untouched segment are preserved exactly. V-1's
prohibition on patch/delta representation stands.

**MG-5 (Proposed) — No revision base.** An existing Corrected Revision is never the base. A currently
selected text-corrected revision's changes are **not** inherited. Doing either would be
revision-on-revision chaining, which stays deferred.

**MG-6 (Proposed) — The released text single-candidate path is unchanged.** Nothing in this PATCH
alters, deprecates, or re-scopes it.

### Explicit candidate set

**MG-7 (Proposed) — The caller enumerates the members.** Every candidate identity is named. The
following are refused: an empty input; a repeated candidate identity (no silent deduplication).
A singleton is permitted. An explicit subset is permitted — candidates not named simply do not
participate, and their Decisions are untouched.

**MG-8 (Proposed) — Membership is fixed at request intake** and never silently changed. Canonical
ordering (MG-12) is normalisation, not a membership change.

**MG-9 (Proposed) — No implicit selection.** Forbidden: collecting all currently accepted candidates,
choosing by recency, quality, confidence or correction size, inheriting a previous generation's
membership, and resolving competition automatically. **This does not forbid deriving each named
candidate's current authority through the released `§18` path — that derivation is required.**

**MG-10 (Proposed) — No partial application.** A request that names members and succeeds with a
subset is forbidden; see MG-19.

### Human Authority and staleness

**MG-11 (Proposed) — Four facts stay separate.** A person verified timing against media; a valid
Accepted authority exists in the system; the candidate is in this explicit set; the resulting revision
was selected downstream. None implies another.

**MG-12 (Proposed) — Authority snapshot.** Generation verifies every member's current Human Authority
and applicability. Each member's authorizing decision is **derived from the released current-authority
path** — no input lets a caller name a past Accepted Decision to bypass a current Reject. The members'
authorizing decisions are fixed as **one consistent authority snapshot**, and the result preserves
those specific Decision identities as provenance.

**MG-13 (Proposed) — Staleness.** If any of the following changes between verification and persist,
the whole generation fails: a member's current authorizing Decision identity; whether a member is
Accepted; the relevant current Raw Transcript selection; the integrity of a source snapshot the
application depends on. No silent re-binding to a different Decision, no automatic rebase, no
retarget. **No corrected-revision selection agreement is added as a condition** — V-4 does not require
it.

> The released guard already precedes identity derivation and existing-result lookup, but that
> ordering alone does not implement the snapshot consistency MG-12 and MG-13 require. It is stated
> here as an implementation requirement to be verified, not as an existing guarantee.

### Same-source competition

**MG-14 (Proposed) — Competing candidates in one set are refused** by name. Two candidates targeting
one source segment are never both applied, and are never merged even when their proposed intervals
coincide — they are distinct authority facts.

**MG-15 (Proposed) — A stored competitor does not block an explicit choice.** That other accepted
candidates exist for the same segment does not prevent generating from the one the caller named, and
naming one candidate does **not** reject the other. No latest-wins, first-wins, or confidence-wins.

### Ordering and combined validation

**MG-16 (Proposed) — Four orderings are distinguished**: the caller's input order; the canonical
membership serialization order; the base transcript's source segment order; the resulting revision's
segment order. **Canonical membership order is the base Raw Transcript's source segment ordinal**,
chosen for consistency with the source ordering and the resulting snapshot order rather than because
other stable orderings would be non-deterministic.

**MG-17 (Proposed) — Order independence.** One base and one member authority set converge on the same
applied content and the same identity regardless of input order. Identity never depends on corrected
timestamp values, wall clock, database return order, or execution completion order.

**MG-18 (Proposed) — Combined structural validation.** Individual admission validity does **not**
imply aggregate validity: `§17` TC-7 checks a proposal against the **original** Raw Transcript
neighbours, so two individually admissible corrections can conflict once applied together. The
complete resulting snapshot is therefore revalidated against the released structural constraints —
ordering, positive duration, and non-overlap — reusing `§14` A-10's vocabulary and the released
`PATCH-0039` ε. **No new tolerance or threshold is introduced, and touching boundaries the released
contract allows are not newly forbidden.** A combined-validity failure refuses the whole request;
timing is never clamped, trimmed, averaged, or re-estimated, because that would change
Human-approved values.

### Atomicity

**MG-19 (Proposed) — All or nothing.** One success unit covers: fixing membership and the authority
snapshot; per-member applicability verification; complete aggregate validation; any new replacement
segments; the Corrected Revision; the generation record with **complete** member provenance; and the
revision's membership. Partial success is refused, with an explicit error naming what failed.

**MG-20 (Proposed) — All-or-nothing applies to what this request newly creates.** On failure, records
that already existed are preserved untouched: legacy generations and revisions, shared replacement
segments, other revisions' memberships, existing Human Decisions and selections. An audit record of a
failed execution under existing contracts is distinct from a partially successful domain result; this
PATCH creates no new audit persistence contract.

### Identity

**MG-21 (Proposed) — Singleton compatibility.** For a timing set of one member with the same candidate
and the same authorizing Decision as the released single-candidate path, the **released identity is
used**. If a generation and revision already exist for that anchor, they are reused after the same
guard and integrity verification. If none exists, the result is created with the identity the legacy
path would have produced. Past identities, records, and replay meaning are never recalculated.

**MG-22 (Proposed) — Aggregate identity.** For two or more members, identity is determined by the base
Raw Transcript and the canonical member authority set, where each member contributes both its
candidate identity and its specific authorizing Decision identity. The same membership with a
different authorizing Decision is a different anchor. Adding or removing a member is a different
anchor.

**MG-23 (Proposed) — Four identities stay distinct**: entity identity, content fingerprint,
authorization provenance, and execution attempt identity. Identical resulting content never merges
distinct Human Authority histories (V-8).

### Replacement identity and verified reuse

**MG-24 (Proposed) — Replacement identity is per-member**, derived from that member's `(candidate,
authorizing decision)` anchor. Consequently the same member contributes the **same replacement** in
`{A, B}` and in `{A, C}`, and shares it with the legacy singleton generation of A. A different
authorizing Decision yields a different replacement identity.

**MG-25 (Proposed) — Verified reuse.** When a replacement with that identity already exists, its
complete canonical payload and source lineage are verified against what this generation expects —
the same standard MG-29 condition 3 states for a member's replacement. Matching: the existing entity
is reused unchanged. Not matching: **integrity failure**, refusing the whole generation — never
overwrite, never delete, never silently reuse.

> That the schema permits a segment to be referenced by several revisions is a structural
> observation. The released writer treats an existing replacement segment as a collision and refuses
> it. **Moving from collision-only to verified reuse is an explicit change this PATCH requires**, not
> a capability that already exists.

### Replay and concurrency

**MG-26 (Proposed) — Exactly three operations exist.** (A) reading a past immutable generation or
revision by identity; (B) requesting generation against current authority; (C) duplicate or
concurrent execution of a valid request on the same anchor. **No separate historical exact-replay
operation is introduced**, and no idempotency token, replay API, or input that pins a past Decision is
added.

**MG-27 (Proposed) — Historical lookup.** Reading a past result is possible even while the candidate's
current authority is Reject. It grants no generation or selection authority.

**MG-28 (Proposed) — Generation under Reject.** The current-authority and applicability guard runs
first. If any member is Rejected or Undecided, the whole request is refused. **The existence of a past
generation never skips the guard.**

> This corrects an earlier Architect statement that a past exact replay would succeed as REUSED while
> the current authority is Reject. It conflated reading a past result with re-issuing a generation
> command. **"Queryable while Rejected" and "the generation command succeeds while Rejected" are
> different claims**, and only the first holds.

**MG-29 (Proposed) — Same-anchor requests that pass the guard.** If none exists, it is a normal new
generation. If a stored result exists under that identity, it is returned as REUSED **only when it
satisfies complete-result integrity**; otherwise it is an integrity failure.

**Complete-result integrity** is defined here and is the single standard referenced wherever this
PATCH permits reuse. A stored result matches only when **all** of the following hold:

1. **Generation anchor** — the stored anchor equals the anchor derived from this request, and its base
   Raw Transcript relationship is consistent. A singleton keeps the released single-candidate identity
   encoding; two or more members match the canonical member authority set.
2. **Complete member authority provenance** — every expected candidate is present with the specific
   authorizing Decision this request fixed, with nothing missing, nothing extra, nothing duplicated,
   no member bound to a different candidate or Decision, and the canonical membership order equal. A
   legacy singleton satisfies this by derivation from its existing singular relationship.
3. **Source-to-replacement mapping** — each member's source segment and replacement identity equal the
   expected pair, and each replacement's canonical payload and source lineage are consistent. A
   replacement that is individually correct but attached to a different member does not match.
4. **Complete revision ordered membership** — the stored revision expresses the expected complete
   snapshot: unchanged source segments referenced in the released order, and each corrected position
   carrying the expected replacement in the expected place. Equal content under different segment
   identities, or the expected replacements arranged in a different membership or order, does **not**
   match.
5. **Canonical content and lineage** — the released content verification still applies.

**A matching content fingerprint does not substitute for conditions 1 through 4.** The released
fingerprint deliberately carries content identity and excludes segment entity identities, so it can be
equal while the member authority set, the source-to-replacement mapping, or the revision's ordered
membership differ. Content equality and provenance integrity are **separate checks**; this PATCH does
not change the released fingerprint recipe and does not fold provenance into it.

A mismatch refuses the whole generation. A stored result is never overwritten, never deleted, never
repaired by rewriting its relationships, and missing provenance is never synthesised or back-filled to
make a reuse succeed.

**MG-30 (Proposed) — Re-Accept.** After Reject then re-Accept, generation uses the anchor derived from
the new current Decision. This is **not** a replay of the past anchor. If a result already exists for
the new anchor, MG-29's reuse rules apply to it.

**MG-31 (Proposed) — Concurrency.** Concurrent identical valid requests converge on one result. When
a persistence collision occurs and the stored result is re-read, it is returned as REUSED **only when
it satisfies the same complete-result integrity standard defined in MG-29** — the collision path
applies no weaker test than the pre-persist lookup does. A mismatch is an integrity failure, not a
convergence. **Collision handling and existing-result reuse must not become a path that bypasses the
authority, applicability or staleness guard**; they apply only to a request that already passed it.

### Selection and lifecycle

**MG-32 (Proposed) — `§20` still selects exactly one revision.** It is not made a merge or derivation
layer.

**MG-33 (Proposed) — Applicability extends to all members.** An aggregate revision is applicable when
(1) its parent Raw Transcript is the relevant intake's current Raw selection, and (2) **every** member
candidate's current Human Authority is Accepted.

**MG-34 (Proposed) — Agreement between a current Accepted Decision identity and the authorizing
Decision identity is *not* added as a selection condition.** The released single-candidate contract
requires only current Accepted authority; requiring identity agreement would be a stronger new policy
and would retroactively change released behaviour. Historical provenance validation and current
applicability stay separate, as V-11 already separates them: repository integrity verifies the
recorded authorizing Accepted Decision and member provenance, and a candidate being currently
Rejected never makes a past revision a damaged record.

**MG-35 (Proposed) — Member Reject after selection.** The revision and its authorizing provenance are
preserved; the persisted selection record is not automatically deleted or changed; the released
effective-resolution and consumption boundaries handle inapplicability; there is no silent raw
fallback and no automatic reselection.

**MG-36 (Proposed) — Member re-Accept.** If the other applicability conditions hold, a past aggregate
may become applicable again. Its authorizing Decision references are **never** rewritten to the new
Decision. A new generation request uses the new current Decision's anchor.

**MG-37 (Proposed) — Generation, selection and effective consumption remain three acts**, never
collapsed into one.

### Downstream

**MG-38 (Proposed) — Downstream is unchanged.** Generation performs no selection. The subtitle
pipeline never re-queries candidates to add corrections. No revisions are merged at `§20` or in the
subtitle stage. Existing subtitle and SRT artifacts are never automatically rewritten, and editing an
SRT file directly is not a path. After an explicit selection of the new aggregate, the released
downstream path consumes that complete revision. Existing subtitle merge/split, time representation
and serialization contracts are preserved. Success is **not** expressed as a one-to-one
segment-to-cue correspondence or a cue count.

## Canonical Invariants

(1) Aggregation is timing-only, over one Raw Transcript, across different source segments, with at
most one candidate per segment. (2) The member set is explicitly enumerated; empty and duplicated
inputs are refused; no discovery, ranking, latest-wins, or inherited membership. (3) Every member's
current Human Authority is verified, and the authorizing Decisions are fixed as one snapshot and
preserved as provenance. (4) Competing candidates for one segment are refused in a set and never
merged; a stored competitor blocks nothing and a named choice rejects nothing. (5) Canonical order is
the base transcript's source segment ordinal, and identity is input-order independent. (6) The
complete resulting snapshot is revalidated against released structural constraints; no new tolerance;
failure refuses the whole request and never adjusts Human-approved timing. (7) Generation is
all-or-nothing over what it newly creates, and preserves everything that already existed. (8) A
singleton uses the released identity and reuses the released result; two or more members derive
identity from the base and the canonical member authority set. (9) Replacement identity is per-member
and shared across aggregates and with the legacy singleton, with reuse only after full verification
and integrity failure otherwise. (9a) Every reuse — a replacement, a stored generation found before
persist, or a stored generation re-read after a collision — is permitted only under the one
complete-result integrity standard, and a matching content fingerprint never substitutes for anchor,
member provenance, source-to-replacement mapping, or ordered revision membership. (10) Only
historical lookup, guarded generation, and same-anchor duplicate execution exist; no historical
exact-replay operation. (11) Reading a past result while
Rejected grants no authority, and the generation guard is never skipped. (12) `§20` selects one
revision, its applicability requires every member currently Accepted, and no Decision-identity
agreement condition is added. (13) A member's later Reject preserves the revision, its provenance and
the selection record, and a later re-Accept never rewrites authorizing references. (14) The released
text single-candidate path, `docs/041`, and `§21` consumption are unchanged.

## Scope and Non-goals

Out of scope, each requiring its own gate: text-only multi-candidate aggregation; mixed text and
timing candidate sets; text + timing same-segment composition; revision-on-revision chaining; revision
merge at `§20` or in the subtitle stage; a batch approval entity; automatic timing correction; any
drift, anchor-gap or readability threshold; provider timing refinement.

**`PATCH-0048`'s text + timing same-segment composition gate remains `MORE_EVIDENCE_REQUIRED` and is
not moved by this PATCH.**

## Required Blueprint Changes

Applied to `docs/040_TRANSCRIPT_PIPELINE.md` and, for item 12 only, `docs/030_DATA_MODEL.md`.
Released sentences are preserved verbatim; every change is an additive note, an additive clause, or a
new subsection.

1. **Header** — Blueprint version and Last Updated advanced; this PATCH added to `Amended By`.
2. **§19 V-2** — additive note: cardinality extends to an explicit timing-only candidate set
   (**normative extension**). V-2's principles — explicit naming, no apply-all/best/latest, no
   implicit discovery, no ranking, no automatic overlap resolution — are preserved verbatim and
   restated as binding at the new cardinality.
3. **§19 V-1** — note: the complete snapshot form is unchanged; only the number of replaced positions
   differs (**clarification**).
4. **§19 V-7/V-8** — note: set anchor, per-member replacement anchor, and complete member provenance;
   the entity/content identity separation is unchanged (**normative extension**).
5. **§19 V-9/V-10/V-11** — note: the guard precedes identity derivation and existing-result lookup;
   reuse and conflict are judged by the **complete-result integrity standard defined in the new
   subsection (MG-29)** — anchor, complete member authority provenance, source-to-replacement
   mapping, ordered revision membership and canonical content — and a matching content fingerprint
   does not substitute for the provenance and membership conditions; the same standard governs the
   post-collision path; V-11's queryable guarantee does not exempt the generation command from the
   guard (**clarification**).
6. **§19 V-13** — note: atomicity covers the newly created result and preserves pre-existing shared
   records (**clarification**).
7. **§19 V-14** — note: **only** timing-only, distinct-source multiple-candidate application is
   un-deferred. Merge, composition, overlap resolution, ranking and chaining stay deferred
   (**normative extension**, narrow).
8. **§19** — new subsection carrying MG-1…MG-38 and the Canonical Invariants above.
9. **§17 TC-7** — note: individual admission is unchanged and remains an original-neighbour check;
   combined validation of the resulting snapshot belongs to `§19` (**clarification**).
10. **§20 S2-8/S2-9** — note: the selection act is unchanged; eligibility and applicability extend to
    every member, with no Decision-identity agreement condition, and the Reject / re-Accept lifecycle
    is recorded (**normative extension** of cardinality only).
11. **§20 S2-14** — note: only this timing aggregate is un-deferred (**normative extension**, narrow).
12. **`docs/030_DATA_MODEL.md` §6.2 Corrected Transcript** — one additive conceptual clause naming
    the **generation-to-member relationship**: a corrected revision's generation is the single owner
    of which corrections it applied, one generation relates to one or more members, and each member
    relates one accepted correction proposal, the human decision that authorized it, the source
    segment it replaces, and the replacement that results. The clause also records that a revision's
    ordered segment membership and a generation's member provenance are **different relationships**,
    and that a legacy single-correction record is read as a one-member generation without being
    rewritten (**normative extension**).

    `docs/030`'s Purpose covers *"개념 사이의 관계"* while excluding tables, fields and storage
    structure, so the relationship belongs there and its shape does not. **The operational contract —
    admission, authority, identity, integrity, replay and validation — stays in `docs/040` §19, and
    the `§6.2` clause defers to it**, following the reference direction `PATCH-0047` already
    established in that same subsection (*"이 문서는 그 저장 구조를 정의하지 않는다"*). The two
    documents must not become independent authorities over the same contract.

`docs/041_SUBTITLE_PIPELINE.md` and `§21`'s consumption boundary are **not** amended beyond any
cross-reference already implied; no new consumption or publication policy is added.

**The released Blueprint is not rewritten to read as though it always supported multiple candidates**,
and no deferral of "multiple candidates" is removed wholesale.

## Schema and persistence impact

**An additive persistence extension is required.** This PATCH does not change schema, and specifies
meaning rather than design.

Requirements: one generation is the **canonical owner** of member provenance; a generation-to-member
relationship of one to many is required; each member must carry its candidate, authorizing Decision,
source segment, replacement segment and canonical ordinal; per-source uniqueness within a generation
and completeness of the membership must be verifiable; one revision must never acquire two canonical
generation owners.

Explicitly not acceptable: filling an existing singular field with one representative member in place
of the whole provenance; placing timing identities into the text-only `correction_candidate_ids`;
distorting released semantics by reusing generic JSON or an empty column; conflating the generation's
membership with the revision's resulting segment membership; letting member authority provenance be
owned independently in two places.

Legacy compatibility: existing single-candidate records are preserved as they are and **interpreted as
a singleton derived from the existing singular relationship** — no member rows are back-filled, no
identity or authorizing reference is recalculated, and legacy and new lineage must be readable
consistently by one reader.

**"Additive change is required" is not the same claim as "adding a member table while leaving the
existing mandatory singular columns in place is sufficient."** The latter is an expressiveness
question the implementing design must resolve; the released generation relations currently constrain
one generation per revision with singular candidate, decision, replaced and replacement fields.

Concrete relation names, DDL, migration recipe and schema version are left to implementation design.

## Legacy compatibility and replay

Released behaviour preserved without change: the guard-first ordering of generation; anchors derived
from current authority; historical lookup unguarded by authority; reuse of a matching result on the
same anchor; conflict on differing content; a new anchor after re-Accept; a past revision remaining
immutable and queryable while its candidate is Rejected.

Changed behaviour proposed: generation cardinality; `§20` applicability cardinality; the writer's
handling of an existing replacement segment, from collision-only to verified reuse.

## Human Authority and selection lifecycle

With an aggregate of members whose authorizing decisions were fixed at generation:

- **All members Accepted** — generation permitted; the revision is not selected by generation.
- **A member Rejected before generation** — the whole request is refused, naming that member.
- **A member Rejected after generation, before selection** — the revision exists and is immutable;
  new generation on that anchor is blocked; the aggregate cannot be newly selected.
- **A member Rejected after the aggregate was selected** — the revision, its provenance and the
  selection record are preserved; effective resolution reports the selection as inapplicable under the
  released boundary and new consumption is refused there; existing artifacts are untouched.
- **That member re-Accepted** — the past aggregate may become applicable again; its authorizing
  references are unchanged; a new generation request uses the new current Decision's anchor and is a
  different generation.

## Acceptance Criteria

Verified against the Blueprint amendment, before this PATCH may be marked `Accepted`.

- [x] The extension is stated **timing-only**, over one Raw Transcript, across different source
      segments, with at most one candidate per segment, and the released text single-candidate path is
      stated unchanged.
- [x] The member set is stated **explicitly enumerated**, with empty and duplicated inputs refused,
      singletons and explicit subsets permitted, and membership fixed at intake.
- [x] Automatic discovery, ranking, latest/best/confidence selection, inherited membership and
      automatic competition resolution are each stated forbidden — while the released per-candidate
      current-authority derivation is stated required.
- [x] Per-member current Human Authority verification, a single consistent authority snapshot, and
      preservation of the specific authorizing Decision identities as provenance are stated.
- [x] Staleness is stated to fail the whole request, with no silent re-binding, rebase or retarget, and
      **no corrected-revision selection agreement condition added**.
- [x] Same-source competing candidates in one set are stated refused; a stored competitor is stated not
      to block an explicit choice; naming one candidate is stated not to reject another.
- [x] Canonical ordering is stated as the base transcript's source segment ordinal, with identity
      stated independent of input order, corrected timestamps and database return order.
- [x] Combined structural revalidation of the complete snapshot is stated required, reusing released
      constraints with **no new tolerance or threshold**, and failure is stated to refuse the whole
      request without adjusting Human-approved timing.
- [x] All-or-nothing is stated, scoped to what the request newly creates, with pre-existing records
      stated preserved on failure.
- [x] Singleton identity is stated to use and reuse the **released** single-candidate identity, with no
      recalculation of past identities or replay meaning.
- [x] Aggregate identity is stated to derive from the base and the canonical member authority set,
      including each member's authorizing Decision, with membership or Decision changes stated to give
      a different anchor.
- [x] Replacement identity is stated per-member and shared across aggregates and with the legacy
      singleton, with **verified reuse** on match and **integrity failure** on mismatch, and the move
      from the released collision-only writer behaviour is stated an explicit change.
- [x] **Complete-result integrity is defined once and enumerated** — anchor, complete member authority
      provenance, source-to-replacement mapping, ordered revision membership, and canonical content —
      and is stated to govern **all three** reuse paths: an existing replacement, a stored generation
      found before persist, and a stored generation re-read after a collision.
- [x] It is stated that a **matching content fingerprint does not substitute** for the provenance and
      membership conditions, that content equality and provenance integrity are separate checks, and
      that the released fingerprint recipe is **not** changed and provenance is **not** folded into it.
- [x] Exactly three operations are stated, and **no historical exact-replay operation, idempotency
      token, replay API, or past-Decision input is introduced**.
- [x] Historical lookup under Reject is stated possible and stated to grant no authority; the
      generation command under Reject is stated refused; the two are **not** stated in the same terms.
- [x] Re-Accept is stated to produce a new anchor rather than a replay of the past anchor.
- [x] Concurrency is stated to converge on one matching result, with collision handling stated **not**
      to bypass the authority or staleness guard.
- [x] `§20` is stated to still select exactly one revision; applicability is stated to require every
      member currently Accepted; **Decision-identity agreement is stated not added**.
- [x] The Reject and re-Accept selection lifecycle is stated, including preserved selection records and
      unrewritten authorizing references.
- [x] Downstream is stated unchanged, with no automatic selection, no candidate re-query, no merge, no
      artifact rewrite, and success **not** expressed as cue counts or one-to-one correspondence.
- [x] The additive persistence requirement is stated with generation-owned member provenance,
      one-to-many cardinality, verifiable uniqueness and completeness, and legacy singleton
      interpretation **without backfill**.
- [x] `docs/041`, `§21` consumption and `docs/030` are confirmed unamended, and `PATCH-0048`'s
      composition gate is confirmed unmoved.
- [x] No released sentence in `docs/040` is deleted or rewritten — prior PATCH notes included —
      verified line by line; §17, §19 and §20 gain **additive notes and one subsection only**.

## Implementation Requirements

Required validation for the implementing milestone. **Not satisfied by this PATCH.** These are
expectations to be verified, not results already obtained.

1. A strictly additive migration introduces generation-owned member provenance; every previously
   released schema version reaches the new one through the supported single-step chain with no row
   rewritten and no data or meaning lost; legacy single-candidate records are interpreted as
   singletons without backfill.
2. Three accepted timing corrections on different source segments of one Raw Transcript are applied
   into one revision, with each source-to-replacement correspondence traceable.
3. The same member set in a different input order converges on one identity and one complete result.
4. A singleton converges on the released single-candidate generation, revision and replacement
   identity, and reuses an existing legacy result.
5. Empty input and a repeated candidate identity are refused; an explicit subset succeeds.
6. Two candidates targeting one source segment in a set are refused; a competitor stored but not named
   does not block generation, and its Decision is unchanged.
7. A wrong candidate type, a different Raw Transcript or timeline, a stale source snapshot, and a
   member that is not currently Accepted each refuse the whole request.
8. A combination whose members are individually admissible but whose aggregate breaks structural
   validity is refused, with no timing value adjusted.
9. The same member contributes one shared replacement across `{A, B}`, `{A, C}` and the legacy
   singleton, reused only after full payload and lineage verification.
10. An existing replacement with the same identity but different payload or provenance causes whole
    integrity failure with no overwrite.
11. A stored revision whose replacement entities are each individually correct but whose ordered
    segment membership differs from the expected complete snapshot — a replacement referenced in
    the wrong position, attached to a different member, or arranged in a different order — is an
    integrity failure and is **not** reused, with existing records unchanged and no partial new
    result.
12. Authority or current Raw selection changing between verification and persist causes stale failure
    with no automatic re-binding.
13. Historical lookup succeeds while a member is Rejected; the generation command is refused; the
    lookup grants no generation or selection authority.
14. After re-Accept, generation uses the new Decision's anchor and past provenance is unchanged.
15. Replay of a valid same-anchor request, including after restart, reuses the existing result
    **only when complete-result integrity holds**. A stored result whose content fingerprint matches
    the expectation but whose canonical source lineage or member source-to-replacement mapping
    differs is an integrity failure, not a reuse — asserted, with existing records unchanged and no
    partial new result.
16. Concurrent identical valid requests converge on one result, and the post-collision re-read applies
    **the same complete-result integrity standard** as the pre-persist lookup — asserted, including
    that the collision path cannot accept a stored result the pre-persist path would have refused.
17. Persist failure rolls back everything newly created and preserves pre-existing shared records.
18. Generation alone leaves existing selections and artifacts unchanged.
19. A member Rejected after selection preserves the selection record while new effective consumption
    is refused under the released boundary.
20. After re-Accept and with other conditions met, the past aggregate is applicable again with
    authorizing references unchanged.
21. Explicitly selecting the aggregate delivers all three corrections through the released effective
    transcript, subtitle and SRT path, preserving merge/split, time representation and serialization.
22. Legacy single-candidate data and past artifacts are unchanged, with no backfill and no identity
    recalculation.
23. Text + timing composition, mixed sets, text-only aggregation and revision chaining remain closed on
    this path — asserted, not assumed.
24. Repository validation reports healthy; the schema version advances by exactly one step; the
    complete test suite passes.

## Consequences and deferred work

- `§19` gains a subsection and additive notes; `§20` gains applicability notes; `§17` gains one
  clarification; released text is untouched throughout.
- A lecture needing several timing corrections can, for the first time, deliver them together through
  one explicitly selected revision.
- Identity, provenance and authority semantics of every existing record are unchanged, and no existing
  artifact is rewritten or invalidated.
- The writer's handling of an existing replacement segment changes from refusal to verified reuse —
  the one released behaviour this PATCH deliberately alters.
- A persistence extension becomes necessary; its design, naming and migration are deferred to the
  implementing milestone.
- Text-only aggregation, mixed sets, same-segment composition and revision chaining remain deferred;
  `PATCH-0048`'s gate is unmoved.
