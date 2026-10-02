# PATCH-0050

- Title: Same-Source Text + Timing Composition — Explicit Pair Generation (040 §19/§20)
- Status: Accepted
- Priority: Medium
- Trigger: the C014-03 evidence packet produced the first same-source text + timing pair that a
  person authored **and** accepted through the released admission and decision paths, which is the
  exact resume condition `PATCH-0048` RC-5 and `implementation/140` §11 set for the composition gate;
  the follow-up Architect Decision Closure (SC-1…SC-12, user-provided, 2026-09-30) closed the
  contract questions RC-4 listed as uncontracted
- Created: 2026-09-30
- Target Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` (§19: one new subsection carrying TX-1…TX-39
  and its Canonical Invariants; scoping notes on V-2, V-5, V-14 and on the `PATCH-0047` TC-12 note;
  §20: one note on S2-8/S2-9 lineage applicability and lifecycle and one on S2-14; §17: one note
  after the `PATCH-0048` follow-up note updating the composition gate for this scope only; header
  amended) **and** `docs/030_DATA_MODEL.md` §6.2 (one additive conceptual clause naming the
  two-role composition relationship, deferring its operational contract to `040` §19).
  `docs/041_SUBTITLE_PIPELINE.md` and `§21` are **not** amended.

---

## Status

**Accepted.** Applied to `docs/040_TRANSCRIPT_PIPELINE.md` (Blueprint 0.8, 2026-10-01) as the new
`§19` subsection *Same-Source Text + Timing Composition* carrying TX-1…TX-39 and its Canonical
Invariants, scoping of `§19` V-2/V-5/V-14, the `§19` Canonical Invariants (3)/(7), the `PATCH-0049`
note and MG Deferred list, and the `PATCH-0047` note (TC-12), one `§17` `PATCH-0050` note after the
`PATCH-0048` note with scoping of the `§17` Deferred list and Canonical Invariants (8)/(13), and one
`§20` `PATCH-0050` note with scoping of S2-14; and to `docs/030_DATA_MODEL.md` `§6.2` as one
additive conceptual clause naming the two-role composition relationship and deferring its operational
contract to `040 §19`. `docs/041_SUBTITLE_PIPELINE.md` and `§21`'s consumption boundary are
unamended. Acceptance was recorded by the Blueprint Maintainer session on 2026-10-01 after the 19
document Acceptance Criteria below were verified against the amended text; no commit was made in that
session.

**What acceptance means here, precisely:**

- **Product contract accepted and reflected in the Blueprint** for exactly one capability: an
  explicit request naming one currently-Accepted text candidate and one currently-Accepted timing
  candidate that target the **same** source segment of the **same** Raw Transcript, producing one
  composed replacement segment inside one complete immutable Corrected Revision.
- **The composition gate is released for this scope only.** The `docs/040` §17 `PATCH-0050` note
  records that the `PATCH-0048` `MORE_EVIDENCE_REQUIRED` gate is resolved for same-source text 1 +
  timing 1 and that every other item `PATCH-0048` and `PATCH-0049` left Deferred stays Deferred (see
  Scope and Non-goals).
- **Runtime implementation pending.** No production code or test was written. The released runtime
  still refuses a text identity in the timing set and has no composition path.
- **Additive persistence, schema and migration pending.** `SQLITE_SCHEMA_VERSION` remains **55**.
  Acceptance approves meaning; it designs no DDL, reserves no schema version and performs no
  migration.
- **Runtime and E2E verification not performed in this session.** The 20 Implementation
  Requirements below are outstanding work for a later milestone; none was executed, and none is marked
  complete by this acceptance.

It introduces **no new Human Decision kind, no composition approval entity, no requester provenance,
no automatic pair discovery, no pairing rule, no latest-wins, no conflict resolution, no revision
chaining, no selection-layer merge, no historical exact-replay operation, and no new threshold or
tolerance.** It requires a **strictly additive** persistence extension, designed at implementation
time.

## Context

`PATCH-0047` released Human Timing Correction beside the released text correction path. Each
generation applies exactly one candidate to the Raw Transcript (`§19` V-2), so a text correction and
a timing correction on one source segment yield two sibling revisions, and `§20` selects one.
`PATCH-0048` corrected the reasoning behind that boundary: the prohibition on composition rests on
the **absence of a canonical composition rule** (RC-4), not on staleness, and its gate was set to
`MORE_EVIDENCE_REQUIRED` with the resume condition *"A single genuine case reopens it"* (RC-5).
`implementation/140` §11 stated the same condition operationally: *"N segments where a person
authored AND accepted BOTH a text correction and a timing correction against the same source
segment … a single genuine case is enough."*

That case now exists. A structural quality label (`C014-03`) had marked one MVI_0147 segment as
both mis-transcribed and late-starting. A review packet was prepared from the canonical Raw
Transcript and the actual media, a person listened, and the resulting text correction and timing
correction were admitted and accepted through the released CLIs into an evaluation copy of the
evidence repository. The Architect Decision Closure that followed answered RC-4's open questions.

This PATCH proposes the narrowest contract that lets those two accepted corrections reach one
revision together.

## Current released contract

- `§19` V-2: generation is an explicit request naming candidates; text generation names *"정확히
  **하나의** 후보"* (released, unchanged by `PATCH-0049`); timing generation names an explicit
  timing-only set (`PATCH-0049`). No apply-all/best/latest, no implicit discovery, no merge, no
  ranking, no overlap resolution.
- `§19` V-5: text application preserves *"timing·순서·timeline 연결·speaker 메타데이터"* and states
  *"text 교정만 지원한다"*. `§19` `PATCH-0047` note TC-12: a timing replacement carries the source
  text *exactly*. Neither sentence contemplates a replacement carrying both an accepted text and an
  accepted interval.
- `§19` V-14 and the `PATCH-0049` MG Deferred list: *"같은 source segment의 text+timing
  composition(`PATCH-0048` gate 유지)"* is Deferred. `§20` S2-14 defers multi-candidate revision and
  chaining; the `PATCH-0049` §20 note un-defers only the timing aggregate.
- `§17` TC-18 and the `PATCH-0048` follow-up note: no automatic composition, no implementation-chosen
  order, no latest-wins, no retarget, no merge at `§20`; the gate is `MORE_EVIDENCE_REQUIRED`.
- `§17` K-1/K-2/K-3 (text candidate: current Raw Transcript segment, non-empty differing text,
  exact source-text snapshot); TC-6/TC-7/TC-8/TC-9 (timing candidate: finite interval, no overlap
  with original neighbours under the released ε, no no-op, exact source-interval snapshot). A text
  candidate carries **no** interval snapshot; a timing candidate carries **no** text snapshot.
- `§18` H-3/H-6/H-8: one Decision references exactly one candidate; current authority is derived per
  candidate from the highest sequence; Reject → Accept appends a new Decision identity.
- `§19` V-4/V-7/V-8/V-9/V-10/V-11/V-13: applicability, deterministic identity from
  `(candidate, authorizing Decision)`, entity identity distinct from content identity, replay reuse,
  same-anchor conflict, historical validity, atomicity.
- `§19` MG-11…MG-13 (authority snapshot and staleness), MG-16…MG-20 (ordering, combined validation,
  atomicity), MG-21…MG-25 (identity, replacement identity, verified reuse), MG-26…MG-31 (replay and
  concurrency), MG-29 (complete-result integrity), MG-32…MG-38 (selection lifecycle, downstream).
- `docs/030` §6.2 (`PATCH-0049` clause): a generation is the single owner of which corrections it
  applied; each member relates one proposal, one decision, one source unit and one replacement unit.
- Released runtime, read for compatibility evidence: both generation paths derive every identity
  from one `(candidate, authorizing_decision)` digest; the text path copies the source interval and
  the timing path copies the source text into the replacement; neither carries `confidence` or
  `uncertainty` into a replacement; the timing member relation is typed to timing candidates and
  unique per replaced and per replacement segment within a generation; revision ownership is
  enforced per relation and across relations by the repository validator; `§20` resolves lineage
  through the text relation and then the timing relations, requiring every member's current
  authority to be Accepted (MG-33) without Decision-identity agreement (MG-34).

## Evidence and Architect Decision basis

### The accepted pair (evaluation copy, read-only)

Evidence repository: `/Users/hanbyeol/Desktop/LectureOS-review-evidence/C014-03/repository/C014-03.sqlite3`
— a copy of `evaluation/timing-diagnostic-full-corpus/measurement.sqlite3` migrated through the
released single-step chain to schema 55. It is an **evaluation copy**, not an operational repository,
and it does not contain the earlier R03/R05/R06 timing records. Review packet:
`/Users/hanbyeol/Desktop/LectureOS-review-evidence/C014-03/run-2026-09-26-a/` (`manifest.json`,
`existing_notes.md`, `human_response_2026-09-30.json`, `human_response_2026-09-30_v2.json`,
`proposal_text_candidate.json`, `proposal_timing_candidate.json`, `RECORD_2026-09-30.md`,
`checksums.sha256`). All recorded identities below were read from that database and matched to the
packet files.

- Media `sha256:19aa01b5…74723` (MVI_0147; full-file digest recomputed at packet preparation and
  equal to the recorded `source_media` digest).
- Raw Transcript `raw-transcript:aea1b22db360d8a5fc2837f2c38a83a9182ca3e2481053cdfff4094bdcbb485d`,
  2,370 segments; current Raw selection
  `raw-transcript-selection:dd9d9ad3c4f924d86d03c8982f7ca98f36bb9e128c0cd154a73ede013d1e6eca`
  (sequence 0), recorded in the copy because admission requires it.
- Source segment `transcript-segment:aea1b22db360d8a5fc2837f2c38a83a9182ca3e2481053cdfff4094bdcbb485d:2224`,
  ordinal 2224, stored text `" 아 깨랑 깨서는 달라요 그래서 일단 깨서만 생각하세요"` (the leading
  space is part of the stored value), interval `[6721.2, 6750.3]`; previous segment 2223 ends at
  6721.2, next segment 2225 starts at 6751.2.
- Text candidate `correction-candidate:3f872ddf4a1004bafecf301cda85c11ee917d1064e19c773be0a902eff55c8c5`
  (manual, `human:유한별`, ref `C014-03-text-2026-09-30`); `proposed_text`
  `"아, 께랑 께서는 달라요. 그래서 일단 께서만 생각하세요."`; `source_text_snapshot` equal to the
  stored text. Accept
  `correction-candidate-decision:ad814afae530ef6e2ea5633ec96c14156cc006d8c67baaeaac8aa1ea6548e503`
  (sequence 0, `reviewer:유한별`). Current authority: accepted.
- Timing candidate `timing-correction-candidate:87717f6891307d0883d9d1892eb7354040802bc508a7da975520499cf042f65a`
  (`human:유한별`, ref `C014-03-timing-2026-09-30`); source snapshot `[6721.2, 6750.3]`; proposed
  `[6745.638, 6750.881]`. Accept
  `timing-correction-candidate-decision:5883610d85a703d73a67db7e6e864774ab9e337f3f04a4cfb5d5d32f6a8281eb`
  (sequence 0, `reviewer:유한별`). Current authority: accepted; the released `list` command reports
  the candidate `[applicable]`.
- No revision, corrected selection, final subtitle selection or SRT exists for this pair.

### Human Review attribution

The final human response (`human_response_2026-09-30_v2.json`, reviewer 유한별) records
`same_utterance: confirmed`, `text_within_corrected_interval: confirmed`,
`verified_text_content: confirmed`, `verified_timing_boundaries: confirmed`,
`verified_text_interval_correspondence: confirmed`, `remaining_uncertainty: "없음"`. The v1 response
left the reviewer field, `why_both_together` and `remaining_uncertainty` empty and
`text_within_corrected_interval` unreviewed; v2 records (`v2_note`) that the reviewer completed
those fields and clarified the text rationale in conversation, and preserves v1 otherwise unchanged.
The candidate payloads and Accepts recorded in the evaluation copy were built from this local v2
file and match it; any copy of the response circulating outside the packet with different rationale
wording is not the file the records were made from, and the contract relies on the recorded
`proposed_text`, interval and Accepts, not on rationale prose.

Direct quotations from the packet, verbatim:

- `text_correction_rationale` (v1 and v2): *"기존에 적혀있던 텍스트가 크게 틀리진 않았으나, 과거
  관찰의 경우 내 사견을 적었음."*
- `text_correction_rationale_clarified` (v2): *"이번에 적힌 corrected text가 실제로 들은 말이 맞음
  (2026-09-30 검토자 확인)"*.
- `timing_correction_rationale`: *"실제 발화 기준."*
- `why_both_together` (v2): *"이 문장은 께(높임 조사) 설명이라 글자가 틀리면 뜻이 달라지고, 29초
  동안 자막이 떠 있으면 학생이 엉뚱한 구간에서 읽게 되므로 둘 다 고쳐야 한다"*. **Attribution:**
  the packet itself records only that the reviewer completed this field in conversation
  (`v2_note`). According to the preparing agent's account of that conversation — which is not a
  packet artifact and is not independently recorded — the sentence was first offered by the agent
  as an example of what the field asks for and the reviewer returned it verbatim as their answer.
  This PATCH therefore treats it as reviewer-adopted wording of agent-offered origin, not as an
  independently phrased reviewer statement, and does not rest any contract decision on it: the
  necessity case rests on the recorded pair, the confirmed correspondence fields and the Architect's
  own analysis below.
- The past listening note preserved in `existing_notes.md` (*"시작 타이밍이 더 뒤임. 께랑 꼐서는
  달라요. 그래서 일단 께서만 생각하세요"*, label `ASR_ERROR`) is a prior observation; it was shown
  for reference and was **not** used as the corrected text.

No other reviewer statements exist in the packet. The `proposed_text` payload contains the corrected
sentence only; rationale, past notes and opinions are kept in rationale fields.

### Expected results under the released contract (analysis, not executed)

Derived from `§19` V-5 and TC-12 and the released generation code; no sibling revision or SRT was
generated for this pair.

- **Text-only revision:** `"아, 께랑 께서는 달라요. 그래서 일단 께서만 생각하세요."` displayed over
  `[6721.2, 6750.3]` — 29.1 seconds, while the utterance the reviewer located occupies the last
  5.243 seconds of that span.
- **Timing-only revision:** `" 아 깨랑 깨서는 달라요 그래서 일단 깨서만 생각하세요"` displayed over
  `[6745.638, 6750.881]` — the interval is right and the honorific particle stays mis-transcribed.
- **Desired composed revision:** the corrected text over the corrected interval, in one replacement
  that replaces source segment 2224, with the other 2,369 source segments referenced unchanged.

Under the released `§20` contract only one of the first two can be selected and delivered. **This is
the Architect's analysis of the contract**; it is not a reviewer statement and not a measured run.

### Architect Decision Closure (user-provided, 2026-09-30) — traceability

The Closure is not a repository file; it is cited here as the user-provided Architect Decision
Closure. Its decisions and where this PATCH carries them:

- SC-1 (necessity — decided by the C014-03 pair): Context, Evidence; TX-1.
- SC-2 (minimum scope and field ownership): TX-1…TX-4, TX-12…TX-13.
- SC-3 (authority — model B: two individual current Accepts plus an explicit pair request; no
  separate confirmation record; the earlier "same listening session" criterion is withdrawn): TX-5…TX-9,
  TX-39.
- SC-4 (applicability; no subset-of-original constraint): TX-10…TX-11.
- SC-5 (role-tagged identity; new composed entity; uniqueness over the full authority anchor):
  TX-14…TX-17.
- SC-6 (complete role-aware provenance; `correction_candidate_ids` keeps its text-only meaning):
  TX-18…TX-20.
- SC-7 (three operations; complete-result integrity): TX-27…TX-30.
- SC-8 (five validation responsibilities; single authority snapshot; all-or-nothing): TX-23…TX-26.
- SC-9 (`§20` applicability and Reject / re-Accept / Raw-change lifecycle): TX-31…TX-35.
- SC-10 (canonical ownership and cardinality; additive persistence required): TX-21…TX-22, Schema
  and persistence impact.
- SC-11 (compatibility): Legacy compatibility; Canonical Invariants.
- SC-12 (Blueprint positions): Required Blueprint Changes.

## Decision

### Scope (TX-1…TX-4)

**TX-1 (Proposed) — A same-source composition generation exists.** An explicit request names exactly
one text correction candidate and exactly one timing correction candidate that target the same
source segment of the same Raw Transcript, and applies both accepted values into **one** composed
replacement segment inside **one** complete immutable Corrected Revision. This is a third generation
kind beside the released text single-candidate path and the `PATCH-0047`/`PATCH-0049` timing paths;
it changes neither.

**TX-2 (Proposed) — Cardinality is fixed.** One Raw Transcript, one original source segment, one text
candidate, one timing candidate, one composed replacement, one revision. A request with a missing
role, two candidates of one role, a candidate whose kind does not match its role, or candidates on
different source segments is refused. Roles are given explicitly by the caller; the implementation
never infers a role from identity prefixes, string order or content.

**TX-3 (Proposed) — Un-named candidates do not participate.** Competing candidates of either kind on
the same source are neither auto-included nor auto-selected; the existence of a stored competitor
does not block the explicitly named pair; naming one candidate does not change any other candidate's
Decision (MG-14/MG-15 carried over).

**TX-4 (Proposed) — Nothing else is composed.** Segment deletion, split, merge, revision chaining,
mixed sets across different sources, batches of several pairs, and text-only aggregation remain
Deferred. A non-empty text replacement that changes spelling or particles is a text correction; the
removal of a segment is not, and this PATCH does not open it.

### Explicit pair request and Human Authority (TX-5…TX-9)

**TX-5 (Proposed) — Authorization is the two individual current Accepts plus the explicit request.**
The text candidate's current `§18` authority and the timing candidate's current authority must both
be Accepted. No new Decision kind, no composition approval record, no pair-level confirmation entity
and no requester provenance is introduced. This is the released V-2 idiom — *"수락은 권한 부여이고
생성은 적용이다"* — at pair cardinality, exactly as `PATCH-0049` MG-11 applied it to a set.

**TX-6 (Proposed) — What the explicit pair request means.** It is the human act of saying *"apply
these two corrections together to their common original source."* Its role is to name the exact text
candidate and the exact timing candidate by identity. It does not assert anything the two Accepts did
not already assert, it does not select a pair on the caller's behalf, and it is not recorded as a
`§18` Human Decision.

**TX-7 (Proposed) — Authorizing Decisions are derived, never supplied.** Each role's authorizing
Decision is the candidate's current Accepted Decision at request time (MG-11). There is no input by
which a caller names a past Decision to bypass a current Reject.

**TX-8 (Proposed) — Why two Accepts suffice in this scope.** Each candidate is anchored to the same
canonical segment (K-1, TC-6), and the segment is the unit of meaning: a text Accept authorizes
*"this segment's text is X"*, a timing Accept authorizes *"this segment's utterance occupies
[s, e]"*. The composed content is fully determined by those two payloads; composition invents no
value and makes no third assertion. A text candidate that described speech outside the segment's
utterance would already be a defective candidate under the text-only path, and accepting it would be
an individual-authority error, not a composition-specific one. Re-deciding the pair would re-decide
what `§18` already decided — the reason `implementation/140` §5 rejected a combined candidate.

**TX-9 (Proposed) — Context is not a guard.** Whether the two corrections were judged by the same
reviewer, in the same listening session, or at the same time is evidence context and is **not** a
contract condition. No same-reviewer, same-session or same-time check is added. The earlier proposal
to branch on "same listening session" is withdrawn.

### Applicability and field ownership (TX-10…TX-13)

**TX-10 (Proposed) — Applicability.** Both candidates must belong to the same intake and target the
same Raw Transcript and the same canonical source segment; that Raw Transcript must be the intake's
current Raw selection (V-4, MG-1); the text candidate's source-text snapshot must equal the stored
segment text exactly (K-3, V-4); the timing candidate's source-interval snapshot must equal the
stored segment interval under the released ε (TC-9); both current authorities must be Accepted. Each
candidate is checked with the snapshot it actually carries — no cross-kind snapshot is required,
invented or back-filled.

**TX-11 (Proposed) — No subset rule.** The corrected interval is **not** required to lie inside the
original interval. The released TC-6 (finite, `start >= 0`, `end > start`) and TC-7 (no overlap with
the **original** Raw neighbours, touching permitted within the released ε) govern, unchanged. That
the C014-03 corrected end (6750.881) lies 0.581 s after the original end (6750.3) and 0.319 s before
the next segment's start is admissible under those rules and creates no new policy.

**TX-12 (Proposed) — Field ownership of the composed replacement.** `text` is the text candidate's
accepted `proposed_text`, exactly. `start`/`end` are the timing candidate's accepted proposed interval,
exactly. `transcript_id`, `source_timeline_id`, `source_order` and `speaker_label` are carried from
the original source segment, as both released paths do. `replaces_segment_id` is the original source
segment. `confidence` and `uncertainty` are **not** carried and not fabricated, as in both released
paths (V-6). No value is inherited from a text-only or timing-only replacement, and no execution
order between the two roles exists.

**TX-13 (Proposed) — Snapshots and targets are immutable.** Neither candidate's source snapshot is
rewritten toward the other's corrected value; no candidate is retargeted to a replacement; the
original Raw Transcript, both candidates and both Decisions are unchanged by generation.

### Identity (TX-14…TX-17)

**TX-14 (Proposed) — Role-tagged anchor.** The composition anchor is the base Raw Transcript, the
original source segment, the text role's `(candidate, authorizing Decision)` and the timing role's
`(candidate, authorizing Decision)`, with roles named explicitly. It does not depend on the order in
which the caller listed the two candidates, on wall-clock, on corrected values or on database return
order.

**TX-15 (Proposed) — Deterministic derivation.** The composition generation identity, the revision
identity and the composed replacement identity derive deterministically from that anchor, following
the released V-7 recipe family. Existing text-only and timing-only replacement identities are
**not** reused; the composed replacement is a **new entity**, and no existing replacement's payload
is changed. The released content fingerprint recipe and every legacy identity recipe are unchanged.

**TX-16 (Proposed) — Authority combination distinguishes entities.** Two compositions with identical
text and interval but different authorizing Decision combinations are different entities (V-8,
MG-23). They are never merged on content. Two different pairs that share one candidate but differ in
the other role, or in either authorizing Decision, produce different composed replacements; a
composed replacement is not shared across pairs the way a timing member's replacement is shared
across aggregates (MG-24), because its payload depends on both roles.

**TX-17 (Proposed) — Uniqueness meaning.** Uniqueness holds over the **complete anchor** (both
candidates and both authorizing Decisions), not over the candidate pair alone, so a Reject followed by
a re-Accept of either candidate yields a new anchor that may produce a new result (MG-30). One
revision has exactly one composition generation.

### Provenance and canonical ownership (TX-18…TX-22)

**TX-18 (Proposed) — The composition generation owns both roles' application provenance.** It
records the base Raw Transcript, the original source segment, the text candidate with its historical
authorizing Decision, the timing candidate with its historical authorizing Decision, the composed
replacement and the canonical content fingerprint. The candidates' source snapshots are traced
through the candidate records; they are not duplicated into a second canonical owner.

**TX-19 (Proposed) — `correction_candidate_ids` keeps its released text-only meaning.** The revision's
`correction_candidate_ids` carries the one applied text candidate, as the released text path does.
It is not the authority provenance of the composition, it never carries a timing identity, and the
timing role's provenance lives only in the composition generation.

**TX-20 (Proposed) — Revision membership and correction provenance are different relationships.**
The revision's ordered segment membership (every unchanged source segment by identity, the composed
replacement at the source's position) and the generation's two-role provenance are recorded and
verified separately (`docs/030` §6.2 direction).

**TX-21 (Proposed) — Cardinality and single ownership.** One revision has exactly one canonical
generation owner across **all four** generation kinds — text single-candidate, timing single-candidate,
timing aggregate and same-source composition. One composition has exactly one text role and exactly
one timing role, both bound to the same original source and the same composed replacement. Ownership
collision is an integrity defect wherever it appears.

**TX-22 (Proposed) — No polymorphic reuse of the timing member relation.** The released timing member
relation is not widened to hold a text identity, and a composition is not disguised as two timing
members on one source. An additive persistence extension carries the composition provenance (see
Schema and persistence impact).

### Validation and atomicity (TX-23…TX-26)

**TX-23 (Proposed) — Five responsibilities, kept distinct.** (1) individual admission, already
complete when a candidate exists; (2) current applicability (TX-10); (3) authorization (TX-5…TX-7);
(4) structural validity of the composed segment — finite values, positive duration, no overlap with
the original neighbours under the released ε; (5) structural validity of the complete resulting
snapshot — ordering, positive duration, non-overlap over every segment (MG-18 vocabulary). No new
tolerance or threshold is created, and an accepted value is never clamped, trimmed, averaged or
re-transcribed to pass.

**TX-24 (Proposed) — One consistent authority and source snapshot.** The request fixes both
authorizing Decision identities, both Accepted states, the current Raw selection and both source
snapshots as one snapshot (MG-12). Before persisting, the write transaction re-verifies all of them
(MG-13). Any change is a whole-request stale failure; the request is never silently re-bound to a
different Decision, rebased or retargeted.

**TX-25 (Proposed) — All-or-nothing over what the request creates.** One success unit contains the
anchor, the composed replacement, the revision, its ordered membership, its candidate reference, its
domain result and the composition generation record. A partial result applying only the text or only
the timing correction is never returned as success. On failure, pre-existing candidates, Decisions,
sibling revisions, shared replacement segments, other generations and selections are preserved
(MG-19/MG-20).

**TX-26 (Proposed) — Failure names its cause.** A refusal states which of the five responsibilities
failed and for which role, so that a person can tell an inapplicable candidate from a structural
conflict from a stale authority.

### Replay and complete-result integrity (TX-27…TX-30)

**TX-27 (Proposed) — Exactly three operations.** (A) historical lookup of a past immutable
composition by identity, which grants no current generation or selection authority; (B) a generation
request under current authority, which must pass the applicability and authorization guard first and
is refused when either candidate is currently Rejected or Undecided **regardless of any past result**;
(C) duplicate or concurrent requests of one valid anchor, which converge on one result. No historical
exact-replay operation, idempotency token or past-Decision input is introduced (MG-26…MG-31).

**TX-28 (Proposed) — Reuse standard.** A stored result is returned as REUSED only when **all** of the
following hold, on the pre-persist lookup and on the post-collision re-read alike: (1) the stored
anchor and base equal the anchor derived from this request; (2) the complete two-role authority
provenance matches — the expected text candidate with the expected authorizing Decision, the expected
timing candidate with the expected authorizing Decision, nothing missing, added, swapped between
roles or bound to another candidate; (3) the source-to-composed-replacement mapping matches and the
replacement's complete canonical payload (text, interval, carried fields, lineage) matches
expectation; (4) the revision's ordered membership matches — every unchanged source in released order
and the composed replacement at the source's position; (5) the released canonical content and lineage
checks pass. (Carries MG-29 to two roles.)

**TX-29 (Proposed) — Fingerprint does not substitute.** A matching content fingerprint never waives
conditions (1)–(4); the released fingerprint excludes entity identity by design and cannot see a
swapped role, a wrong Decision or a mis-positioned replacement. Any mismatch is an integrity failure:
the stored result is not overwritten, repaired, re-linked or back-filled to make reuse succeed, and
the collision path never uses a weaker check than the pre-persist path.

**TX-30 (Proposed) — Re-Accept is a new anchor.** After a Reject and a later Accept of either
candidate, a new generation request uses the anchor derived from the new current Decisions. It is not
a replay of the past anchor; if a result for the new anchor already exists, TX-28 applies.

### `§20` selection and lifecycle (TX-31…TX-35)

**TX-31 (Proposed) — `§20` still selects exactly one revision.** A composed revision is one more
selectable revision; selection never merges a text-only and a timing-only sibling, and never derives
content (MG-32, RC-6).

**TX-32 (Proposed) — Applicability of a composed revision.** It is applicable when (1) its parent
Raw Transcript is the intake's current Raw selection and (2) the text candidate's **and** the timing
candidate's current `§18` authority are both Accepted (MG-33 over two roles). Agreement between a
current Accepted Decision identity and the authorizing Decision identity recorded at generation is
**not** a condition (MG-34), so no stronger condition is applied retroactively to any released path.

**TX-33 (Proposed) — Reject of either role.** The past composed revision and its authorizing
references are immutable and remain queryable; a new generation under the same candidates is refused;
a new selection is refused; an existing persisted selection record is not deleted or changed; the
released effective-resolution and consumption boundaries report inapplicability; there is no silent
raw fallback, no automatic reselection and no silent application of the remaining role alone.
Existing subtitle and SRT artifacts are untouched.

**TX-34 (Proposed) — Re-Accept.** When the other applicability conditions hold, a past composed
revision may become applicable again; its authorizing references are never rewritten to the new
Decision. A new generation request uses the new anchor (TX-30).

**TX-35 (Proposed) — Current Raw change.** The released parent-not-current meaning applies unchanged:
the revision remains history, and it is inapplicable for new selection and effective consumption
while its parent is not current.

### History (TX-36…TX-37)

**TX-36 (Proposed) — Both candidate histories expose composition participation.** The text
candidate's history and the timing candidate's history each include the composition generations the
candidate participated in, alongside their existing singleton and aggregate entries. A generation is
returned once per candidate; querying from one role never truncates the other role's provenance.

**TX-37 (Proposed) — History is read-only and complete.** A current Reject, a current Raw change or
an inapplicable state never hides a historical composition. History performs no repair and no
back-fill. No new user interface or general search capability is implied.

### Downstream (TX-38) and quality limits (TX-39)

**TX-38 (Proposed) — Generation stops at the revision.** Generation performs no selection, runs no
subtitle or SRT stage and rewrites no artifact. After an explicit `§20` selection the released
downstream consumes the complete revision as it consumes any other; the subtitle pipeline does not
re-collect candidates or perform composition itself. `§21` and `docs/041` are unchanged (MG-38).

**TX-39 (Proposed) — Stated quality limit.** Runtime verifies identity, authority, snapshots and
structural validity. It does **not** and cannot verify that the accepted text is what was spoken or
that the accepted interval is where it was spoken; that correspondence is exactly as good as the two
individual Accepts and the review behind them. This PATCH selects model B because the composition
adds no assertion beyond those Accepts (TX-8), not because the semantic risk is absent. Additional
human review — for example showing a segment's timing candidates when a text candidate is authored,
and the reverse — retains its ordinary value and may be added to review tooling; it is not made a
canonical authority record here.

## Canonical Invariants

Under this PATCH:

1. A same-source composition applies exactly one Accepted text candidate and exactly one Accepted
   timing candidate to exactly one original source segment of the intake's current Raw Transcript.
2. Authorization is the two candidates' current Accepted authority plus the explicit pair request;
   no composition approval entity, Decision kind or requester provenance exists.
3. Roles are explicit; nothing is inferred from order, prefix or content; missing, duplicated or
   mismatched roles are refused.
4. The composed replacement is a new entity whose text is the text candidate's accepted payload and
   whose interval is the timing candidate's accepted payload; carried fields follow the released
   source-preservation rules; no confidence or uncertainty is fabricated.
5. Identity derives from the role-tagged anchor (base, source, text candidate + Decision, timing
   candidate + Decision); uniqueness holds over that complete anchor; different authority combinations
   are different entities even with identical content.
6. The composition generation is the single canonical owner of both roles' application provenance;
   one revision has one generation owner across all four generation kinds.
7. The revision's `correction_candidate_ids` keeps its released text-only meaning and never carries a
   timing identity.
8. Applicability uses each candidate's own snapshot; no cross-kind snapshot is required or
   back-filled; the corrected interval need not be a subset of the original; released TC-6/TC-7/ε
   govern.
9. Generation is all-or-nothing over what it creates; no partial single-role success; pre-existing
   records survive failure.
10. Reuse and post-collision reads apply the same complete-result integrity standard; fingerprint
    match never waives provenance, mapping or membership checks; mismatch is an integrity failure,
    never repaired.
11. Three operations only — lookup, generation under current authority, convergence of duplicate
    valid requests; no historical exact-replay.
12. `§20` selects one revision; a composed revision is applicable when its parent Raw is current and
    both roles' current authority is Accepted; Decision-identity agreement is not a condition.
13. Reject preserves history and existing selections, refuses new generation and selection, and never
    triggers silent fallback, reselection or single-role application; re-Accept never rewrites
    authorizing references.
14. Both candidate kinds' histories expose composition participation completely and read-only.
15. Generation performs no selection and no subtitle or SRT work; `§21` and `docs/041` are unchanged.
16. Text single-candidate, timing single-candidate and timing aggregate paths, their identities,
    verified reuse, records and histories are unchanged; no existing sibling pair is auto-composed or
    back-filled.

## Scope and Non-goals

In scope: exactly the capability of TX-1/TX-2.

Out of scope, each keeping its own gate: text-only multi-candidate aggregation; mixed text and timing
sets across **different** source segments; batches of several composition pairs; segment deletion,
split or merge; revision-on-revision chaining; automatic candidate discovery, pair selection or
conflict resolution; merge at `§20` or in the subtitle stage; automatic text or timing correction;
any new threshold or tolerance; provider timing refinement. The released timing `generate_set`
remains timing-only and is **not** reinterpreted as accepting text identities.

`PATCH-0048` and `PATCH-0049` remain Accepted history; their text and status are not changed. This
PATCH narrows one Deferred item they both name — same-source text + timing composition — to the
scope above and leaves every other deferral in place.

## Required Blueprint Changes

Applied on 2026-10-01. Changes are additive notes, additive clauses and one new subsection; where a
released sentence was unconditional (`§19` V-5 and V-14, the `§19` Canonical Invariants (3)/(7), the
`§17` Deferred list and Canonical Invariants (8)/(13), the MG Deferred list, S2-14) it was **scoped in
place** so that the current rules read without contradiction. Past Accepted PATCH texts
(`PATCH-0047`, `PATCH-0048`, `PATCH-0049`) are unchanged; the `PATCH-0048` and `PATCH-0049` notes in
`docs/040` carry only a parenthetical pointer to this PATCH.

1. **Header** — Blueprint version and Last Updated advanced (0.7 → 0.8, 2026-10-01); this PATCH added
   to `Amended By`. (`docs/040`'s `Depends On` lists only the foundational `PATCH-0001`, as for every
   prior amendment, so this PATCH is not added there; `docs/030`'s header carries no amendment list and
   was left unchanged, following `PATCH-0047`/`PATCH-0049`.)
2. **§19 V-2** — additive scoping note: the text single-candidate sentence and the `PATCH-0049`
   timing-set sentence each govern their own generation kind; a third kind, the same-source
   composition, names exactly one text candidate and one timing candidate by role. V-2's principles —
   explicit naming, no apply-all/best/latest, no implicit discovery, no ranking, no automatic overlap
   resolution — are restated as binding for the pair (**normative extension**, narrow).
3. **§19 V-5** — additive scoping note: V-5's timing-preservation rule and its sentence *"text 교정만
   지원한다"* describe the **text single-candidate** application; in a same-source composition the
   interval comes from the accepted timing candidate, and every other preservation rule of V-5
   (order, timeline linkage, speaker metadata, unchanged segments by reference) applies unchanged
   (**clarification of scope**).
4. **§19 `PATCH-0047` note, TC-12** — additive scoping note: TC-12's *"source text exactly"* rule
   describes the **timing-only** replacement; in a same-source composition the text comes from the
   accepted text candidate, and TC-12's remaining rules (accepted interval as `start`/`end`,
   `replaces_segment_id` to the source) apply unchanged (**clarification of scope**).
5. **§19 V-7/V-8** — note: the role-tagged composition anchor, the composed replacement as a new
   entity, and uniqueness over the complete anchor; the entity/content identity separation is
   unchanged (**normative extension**).
6. **§19 V-9/V-10/V-11/V-13** — note: the guard precedes lookup; reuse and conflict are judged by
   TX-28/TX-29; atomicity covers what the request creates (**clarification**).
7. **§19 V-14** — note: **only** same-source text + timing composition at the cardinality of TX-2 is
   un-deferred; every other item in V-14 stays deferred (**normative extension**, narrow).
8. **§19 `PATCH-0049` subsection, Deferred list** — note: the item *"같은 source segment의 text+timing
   composition(`PATCH-0048` gate 유지)"* is released for the scope of this PATCH only; the MG rules
   themselves are unchanged and the timing set stays timing-only (**normative extension**, narrow).
9. **§19** — new subsection *Same-Source Text + Timing Composition* carrying TX-1…TX-39 and the
   Canonical Invariants above.
10. **§17 `PATCH-0048` follow-up note** — one additive note after it: the composition Product
    Decision's gate for **same-source text 1 + timing 1** is closed by this PATCH on the C014-03
    evidence, the canonical rule RC-4 found missing is now `§19` TX-1…TX-39, and RC-1/RC-6's
    prohibitions on automatic composition, implementation-chosen order, latest-wins, retarget and
    selection-layer merge remain in force; chaining stays Deferred (**gate update**, scoped).
11. **§20 S2-8/S2-9** — note: the selection act is unchanged; a composed revision's lineage is
    resolved through the composition generation and is applicable when its parent Raw is current and
    both roles' current authority is Accepted, with no Decision-identity agreement condition; the
    Reject / re-Accept / Raw-change lifecycle of TX-33…TX-35 is recorded (**normative extension** of
    lineage only).
12. **§20 S2-14** — note: only the same-source composition revision is un-deferred; chaining, merge at
    `§20` or in the subtitle stage, and simultaneous selection of several revisions stay Deferred
    (**normative extension**, narrow).
13. **`docs/030_DATA_MODEL.md` §6.2** — one additive conceptual clause after the `PATCH-0049` clause:
    a single correction lineage may bind **two corrections of different roles — one to the spoken
    text, one to the occupied interval — of the same source unit to one replacement unit**; the
    generation remains the single owner of that two-role provenance; the revision's ordered unit
    composition and the generation's correction lineage remain different relationships; the
    operational contract (admission, authority, identity, integrity, replay, validation) is defined by
    `040 §19` and is not duplicated here (**normative extension**).

`docs/041_SUBTITLE_PIPELINE.md` and `§21`'s consumption boundary are **not** amended. No new
consumption, publication or serialization policy is added.

The released Blueprint is not rewritten to read as though composition always existed, and no
deferral is removed wholesale.

## Schema and persistence impact

**An additive persistence extension is required; the existing v55 relations are insufficient and are
not altered.** This PATCH specifies meaning, not design: no table name, DDL, migration code or schema
version is written or reserved here.

Requirements the extension must satisfy:

- one composition generation is the **canonical owner** of the two-role provenance of one revision;
- it binds one text candidate with its authorizing Decision and one timing candidate with its
  authorizing Decision to one original source segment and one composed replacement, and records the
  canonical content fingerprint;
- uniqueness is expressible over the complete anchor (both candidates and both Decisions) and over the
  revision, so that a re-Accept can yield a new anchor while one revision keeps one owner;
- ownership collision across the text single-candidate, timing single-candidate, timing aggregate
  and composition relations is detectable by the repository validator;
- the released timing member relation keeps its typed foreign keys and per-source uniqueness and is
  not made polymorphic;
- every existing row and meaning of schema 1…55 is preserved; the migration is strictly additive with
  no back-fill; a released single-kind generation is never reinterpreted as a composition;
- `§20` lineage resolution and both candidate history readers can reach the composition relation.

Physical shape, transaction and locking design, and helper structure are implementation decisions
under `implementation/020_STORAGE_MODEL.md` and the existing migration contracts.

## Legacy compatibility and replay

The released text single-candidate path, the `PATCH-0047` timing singleton and the `PATCH-0049`
timing aggregate are unchanged: their identity recipes, verified-reuse rules, generation records,
histories and selection behaviour are untouched. Existing sibling text-only and timing-only
revisions for one segment remain correct immutable history (RC-7) and are never auto-composed,
reinterpreted as awaiting composition, or back-filled into a composition record. A composed
replacement never reuses a sibling's replacement identity. `OI-1`…`OI-3` outcomes are preserved.

## Human Authority and selection lifecycle

Summarized from TX-5…TX-9 and TX-31…TX-35: two current Accepts and an explicit pair request
authorize generation; no pair-level authority is stored, so there is no pair-level authority to
expire, and Reject / re-Accept semantics follow the two candidates exactly as MG-33…MG-36 already
define them for aggregate members. The four facts `PATCH-0049` MG-11 keeps separate — a person
verified against media, a valid Accepted authority exists, a candidate is named in this request, the
result is selected downstream — stay separate here, with two roles named instead of a set.

## Acceptance Criteria

Document-completeness checks, each verified against the amended Blueprint text on 2026-10-01 before
this PATCH was marked `Accepted`. The `docs/040` location of each is the `§19` subsection *Same-Source
Text + Timing Composition* unless stated otherwise.

- [x] Every SC decision of the user-provided Architect Decision Closure is traceable to at least one
      TX rule or Required Blueprint Change, and the mapping in *Evidence and Architect Decision basis*
      is complete and accurate.
- [x] Model B is stated as the authority model: two individual current Accepts plus an explicit pair
      request; no composition approval entity, Decision kind, confirmation record or requester
      provenance is introduced; and the reason it suffices (TX-8) is stated together with its quality
      limit (TX-39) without claiming semantic risk is absent.
- [x] The withdrawn "same listening session / same reviewer / same time" criterion is stated as
      **not** a contract condition (TX-9).
- [x] The C014-03 evidence is cited with full identities read from the evaluation copy, the copy is
      stated to be non-operational, and every reviewer quotation is verbatim from the packet with the
      `why_both_together` provenance stated; the text-only/timing-only comparison is labelled analysis,
      not execution.
- [x] Scope is stated as exactly one Raw Transcript, one source segment, one text candidate, one
      timing candidate, one composed replacement, one revision, with explicit roles and refusal of
      missing, duplicated or mismatched roles.
- [x] Un-named competitors are stated neither auto-included nor blocking (TX-3).
- [x] Applicability is stated per candidate with the snapshot it carries, with no cross-kind snapshot
      required or back-filled, and with no subset-of-original rule (TX-10, TX-11).
- [x] Field ownership of the composed replacement is stated for text, interval, carried fields,
      `replaces_segment_id`, and the non-fabrication of confidence/uncertainty (TX-12).
- [x] The role-tagged anchor, the new-entity rule for the composed replacement, non-merging of
      identical content under different authority, and uniqueness over the **complete** anchor (not the
      candidate pair) are stated (TX-14…TX-17).
- [x] Two-role provenance ownership, the unchanged text-only meaning of `correction_candidate_ids`,
      the separation of revision membership from correction provenance, and single ownership across all
      four generation kinds are stated (TX-18…TX-22).
- [x] The five validation responsibilities, the single authority/source snapshot with in-transaction
      re-verification, whole-request staleness, and all-or-nothing with no single-role success are
      stated (TX-23…TX-26).
- [x] The three operations and the complete-result integrity standard — anchor, two-role provenance,
      source-to-replacement mapping and payload, ordered membership, canonical content — are stated,
      with fingerprint match explicitly not substituting and the post-collision path held to the same
      standard (TX-27…TX-30).
- [x] `§20` is stated to select one revision; composed-revision applicability is stated as parent
      current plus both roles Accepted, with no Decision-identity agreement; the Reject, re-Accept and
      Raw-change outcomes are each stated (TX-31…TX-35).
- [x] Both candidate kinds' histories are stated to expose composition participation completely and
      read-only (TX-36, TX-37).
- [x] Generation is stated to perform no selection and no subtitle/SRT work; `§21` and `docs/041`
      are stated unamended (TX-38).
- [x] The Required Blueprint Changes name exactly `docs/040` §19 (V-2, V-5, TC-12 note, V-7/V-8,
      V-9…V-13, V-14, MG Deferred list, new subsection), §17 (`PATCH-0048` note gate update), §20
      (S2-8/S2-9, S2-14) and `docs/030` §6.2, each with scoping language; unconditional released
      sentences are scoped in place rather than contradicted by a note, and no past Accepted PATCH text
      is altered.
- [x] The gate release is stated as limited to same-source text 1 + timing 1, with every other
      `PATCH-0048`/`PATCH-0049` deferral listed as remaining Deferred, and the timing `generate_set`
      stated to remain timing-only.
- [x] Compatibility of the text singleton, timing singleton and timing aggregate — identities,
      verified reuse, records, histories — and the no-auto-compose / no-back-fill rule for existing
      sibling pairs are stated.
- [x] The additive persistence requirement is stated as meaning only, with the timing member relation
      stated not to become polymorphic and no version, name or DDL reserved.

## Implementation Requirements

Outstanding work for a later, separately authorized milestone. None is executed or satisfied by
this PATCH; real-media steps are targets to run on an evaluation copy, not results.

1. The C014-03 pair — text `"아, 께랑 께서는 달라요. 그래서 일단 께서만 생각하세요."`, interval
   `[6745.638, 6750.881]` — is applied by one explicit pair request into one composed replacement that
   replaces source segment 2224, and the other 2,369 source segments of that Raw Transcript (2,370 in
   total, read from the evidence copy) are referenced by their identities in released order.
2. Every unchanged source segment's identity, text, timing and ordered membership is preserved
   byte-for-byte in the resulting revision.
3. The same pair with the two candidates listed in the other order, requested again, and requested
   after process restart converges on the same generation, revision and replacement identities and is
   reported REUSED, not created.
4. A pair on different source segments, different Raw Transcripts or different intakes; a candidate
   of the wrong kind in a role; two candidates of one role; and a missing role are each refused with a
   cause naming the role, and nothing is written.
5. A pair in which either candidate is Undecided, Rejected or stale (snapshot mismatch, parent Raw not
   current) is refused as a whole; no text-only or timing-only result is produced.
6. Un-named competing candidates of either kind on the same source do not block the named pair and
   are not changed by it.
7. Two compositions with identical content under different authorizing Decision combinations have
   different identities and both persist.
8. Two pairs sharing one candidate but differing in the other role, or in either authorizing
   Decision, produce different composed replacements and different revisions.
9. A stored composition whose source mapping, replacement payload, role provenance or ordered
   membership differs from expectation is refused as an integrity failure, never repaired.
10. A stored composition with a matching content fingerprint but wrong lineage or membership is an
    integrity failure.
11. The post-collision re-read applies the same complete-result integrity standard as the
    pre-persist lookup, verified against real concurrent connections on one database file.
12. Concurrent valid requests of one anchor converge on one result; newly created results are
    all-or-nothing.
13. A persist failure leaves every pre-existing candidate, Decision, sibling revision, shared
    replacement, generation and selection unchanged.
14. After a Reject of either role: lookup still returns the past composition; a generation request is
    refused regardless of the past result; a new selection is refused; an existing selection record
    persists and resolves inapplicable. After re-Accept: the past composition becomes applicable again
    without rewritten references, and a new generation request uses the new anchor. After a current Raw
    change: parent-not-current applies.
15. The text candidate's history and the timing candidate's history each list the composition once,
    with both roles' provenance intact, alongside any singleton or aggregate entries, and regardless of
    current authority.
16. Existing text single-candidate, timing singleton and timing aggregate generations keep their
    identities, verified reuse, records and histories; existing sibling pairs are not composed or
    back-filled.
17. The additive migration preserves every row and meaning of schema 1…55 through the single-step
    chain, refuses downgrade and direct-skip consistently, rolls back on failure, writes no back-fill,
    and yields a schema equal to fresh initialization under the existing migrated/fresh equivalence
    test approach.
18. Generation alone changes no selection, effective transcript, subtitle candidate or SRT artifact.
19. After an explicit `§20` selection of the composed revision, the released subtitle path delivers a
    cue carrying the corrected text over `[6745.638, 6750.881]`, with the released merge/split, time
    representation and serialization contracts unchanged; success is judged by lineage and value, not
    by a fixed cue count or a source-to-cue 1:1 assumption, and a controlled passthrough expectation is
    distinguished from the general consumption contract.
20. Mixed sets across different sources, batches of pairs, chaining and text-only aggregation remain
    refused, and the timing `generate_set` still refuses text identities.

## Consequences, quality limitations and deferred work

**Consequences.** A person who has accepted both a text and a timing correction on one segment can,
by one explicit request, obtain one revision carrying both, and select it. Nothing changes for
anyone who does not make that request: sibling revisions remain valid, existing selections and
artifacts remain untouched, and every released generation kind behaves as before.

**Quality limitations, stated plainly.** Composition is exactly as correct as its two Accepts. A text
candidate accepted against a wide original interval and a timing candidate that narrows that interval
can, if the text was transcribed from audio outside the narrowed span, compose a caption that is
wrong — and it would have produced a wrong text-only revision too. Runtime cannot detect this;
review practice can, and review tooling that shows a segment's other-kind candidates when a candidate
is authored is a reasonable, separately scoped improvement. One real case establishes need and shape;
it does not establish the composability of every kind of text correction, and this PATCH generalizes
no further than TX-2.

**Deferred work.** Everything listed under Scope and Non-goals. In addition: the physical persistence
design, the migration and its equivalence test, the `§20` lineage reader extension, both history
reader extensions, the repository validator's four-kind ownership check, and the real-media E2E on an
evaluation copy — all belong to the implementing milestone.

**Gate status.** With this PATCH accepted and applied, the `docs/040` §17 `PATCH-0050` note records
that the `PATCH-0048` `MORE_EVIDENCE_REQUIRED` gate is resolved for same-source text 1 + timing 1
only; the historical `PATCH-0048` note sentence that set the gate is preserved with a pointer to this
resolution, and every other composition and chaining item remains Deferred. Acceptance of the document
is distinct from runtime availability, which requires the implementing milestone to complete.
