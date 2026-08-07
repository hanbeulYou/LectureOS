# PATCH-0042

- Title: Effective Subtitle Readability Validation Enforcement Boundary (041 §16)
- Status: Accepted
- Priority: High
- Trigger: Contract-consistency review of the GOAL implementing `PATCH-0041`, recorded in
  `implementation/124_READABLE_SUBTITLE_CUE_COMPOSITION.md`
- Created: 2026-08-07
- Target Blueprint: `docs/041_SUBTITLE_PIPELINE.md` (§16 gains EN-1…EN-11; §16 *Sections Not
  Re-scoped* amended; §4.5 and §4.8 forward notes; header amended)

---

## Status

**Accepted.** `docs/041_SUBTITLE_PIPELINE.md` was amended and the *PATCH Acceptance Criteria* below
were verified; the decisions are in force for the effective-transcript readable generation.

It introduces no schema change, no migration, no new aggregate, no new authority, no new lifecycle,
and no parameter change. It invalidates no released record.

## Context

`PATCH-0041` fixed the readability policy and classified its violations into two severities, calling
one **배포 차단 / delivery-blocking**. It named no boundary that must refuse such a Candidate, and its
*Sections Not Re-scoped* clause stated that the Review, Final Selection, SRT Artifact,
materialization, delivery and publication contracts were unchanged.

The implementing GOAL therefore produced a validator that no boundary consults. Full-length
validation made the consequence concrete: a readable Candidate carrying **three findings at blocking
severity** and 91 warnings passed Review Preparation, an Accept decision, Final Selection, SRT
Artifact generation, and physical materialization, and nothing refused it at any point.

That is not an implementation defect. `PATCH-0041` created a severity vocabulary without an
enforcement contract, and the implementation correctly declined to invent one. This PATCH supplies
the missing contract.

## Blueprint evidence

The released stage responsibilities already assign this work, and they assign it to different stages
than one might guess. Three sentences decide the outcome.

**`§4.6` Subtitle Review Preparation** — "분할, 표현, 타이밍, 읽기 문제, Uncertainty와 **Validation
Failure**를 Subtitle 관련 Review Item으로 **연결**하고 관련 Source Media 구간을 확인할 수 있게
준비한다." Review Preparation's released responsibility is to *surface* Validation Failure. A
boundary whose job is to connect failures to Review Items cannot also be the boundary that refuses
them; refusing there would defeat the responsibility the section assigns.

**`§4.5` Structural Validation** — "**Validation Failure가 있는 Subtitle revision을 Final Subtitle로
취급하지 않는다.**" The released refusal is stated against **Final Subtitle**, not against review,
not against export. `§4.5` is not listed in `§16`'s *Sections Not Re-scoped* clause and stands
unamended.

**`§4.8` Final Subtitle** — "**구조적 Validation과** 적용 가능한 Review Decision을 **반영해** 외부
전달용 Artifact를 만들 수 있는 승인 상태의 Subtitle 표현을 **구분한다**." Distinguishing the approved
representation *by reflecting structural validation* is Final Subtitle's own stated responsibility.
The enforcing boundary is therefore not a new invention — it is the stage the Blueprint already made
responsible.

Two further released statements bound the shape. `§9.1` requires that an over-long or incomplete
display unit not be passed off as a normal result, and `§16`'s existing forward note already connects
`§9.1` to R-10/R-11 for this generation. `§12.2` requires that a readability rule change never
auto-apply to existing user Modifications and Review Decisions.

## Alternatives

**Alternative A — refuse at Review Preparation.** Rejected on `§4.6`. It contradicts the stage's
released responsibility to connect Validation Failure to Review Items, and it is
self-defeating in practice: the person best placed to judge whether three unbreakable 42-character
lines matter is denied the chance to look at them. It also hides a Candidate that `§15` E11 makes an
immutable historical record.

**Alternative B — admit Review, refuse at Final Selection.** Matches `§4.5` (the refusal is stated
against Final Subtitle), `§4.8` (reflecting structural validation is that stage's responsibility),
and `§4.6` (review still surfaces the problem). Human Authority is untouched: a person may still
accept, reject, or modify; what they cannot do is make a structurally non-conforming Candidate the
final subtitle. Downstream stays simple because one boundary decides once.

**Alternative C — refuse at SRT Artifact generation.** Rejected on `§4.8`. Final Subtitle is defined
as the approved state *from which* an external artifact can be made; deferring the check past it
means a Final Subtitle exists that cannot produce an artifact, which contradicts what Final Subtitle
is. It also splits the decision across every future format, since each serializer would have to
re-derive it.

**Alternative D — keep it diagnostic-only.** Rejected on `§4.5` and `§9.1`. It is the current state,
and it makes "blocking" a word with no consequence: an over-long display unit passes as a normal
result and reaches publication. It also leaves `PATCH-0041` R-11 internally hollow.

| | A | B | C | D |
|---|---|---|---|---|
| Human sees the blocking detail | **no** | **yes** | yes | yes |
| Matches `§4.5`'s stated refusal point | no | **yes** | no | **no** |
| Matches `§4.8`'s stated responsibility | no | **yes** | **no** | no |
| Matches `§4.6`'s stated responsibility | **no** | **yes** | yes | yes |
| Downstream re-evaluation needed | no | **no** | per format | n/a |
| Human Authority preserved | reduced | **yes** | yes | yes |
| "blocking" has consequence | yes | **yes** | yes | **no** |

**Alternative B is confirmed**, and on released text rather than on preference.

## Decision

**EN-1 (Confirmed) — `blocking` is an admission condition, not a label.** In the
effective-transcript generation, a readable Candidate carrying one or more findings at blocking
severity under `§16` R-11 **must not become the Final Subtitle** and must not reach export,
materialization, delivery, or publication through it. `warning` severity carries no admission
consequence anywhere.

**EN-2 (Confirmed) — Review Preparation admits.** A blocking finding never prevents preparing a
Candidate for review, per `§4.6`. The Candidate record, its cues, and its lineage are never hidden,
withheld, deleted, or marked invalid because of a readability finding. Generation likewise never
refuses: `§16` R-5 and R-9 require the generator to emit the unmodified cue and diagnose rather than
force a transformation, and that outcome must remain reachable and inspectable.

**EN-3 (Confirmed) — Human Decision admits.** A person may record `accept`, `reject`, or `modify`
against a Candidate carrying blocking findings. Review is observation and judgement, and removing the
ability to judge a flawed proposal would not improve it. **Accept ≠ Final Subtitle eligibility**,
which the released effective-generation contracts already separate; EN-4 adds one further condition
to that separation rather than creating it.

**EN-4 (Confirmed) — Final Selection is the enforcing boundary.** A new Final Selection admission
re-derives the Candidate's readability validation at command time and **refuses** when any finding is
at blocking severity. The refusal is explicit and names the findings; it is not a silent skip, a
downgrade, a partial selection, or an automatic fallback to another Candidate.

Readability is **derived, never stored**. It is re-evaluated from the Candidate's immutable cue graph
under the Candidate's own readability parameter version — which `§16` R-13 already makes part of that
Candidate's identity — so the evaluation is deterministic for a given Candidate and cannot drift
between the moment of generation and the moment of selection.

**EN-5 (Confirmed) — Refusal preserves everything.** A refused selection writes nothing and destroys
nothing. The Candidate, its cues, its lineage, the Review Subject, and every Review Decision survive
unchanged, and no upstream record is mutated. The blocking findings are surfaced to the caller with
enough detail to act on — at minimum the code and the affected cue. A refusal is an ordinary,
recoverable outcome, not repository corruption.

**EN-6 (Confirmed) — Warnings never refuse.** Duration below the target minimum, duration above the
maximum with no safe split point, a reading rate over the CPS threshold, and any other unmet
readability goal are non-blocking and **must not** prevent Final Selection. `§16` R-11's statement
that a cue over seven seconds is not corruption is unchanged and now has an operational consequence:
such a Candidate is selectable.

**EN-7 (Confirmed) — Downstream trusts Final Selection.** SRT Artifact generation, serialization,
materialization, delivery, and publication **do not re-evaluate readability**. They consume a Final
Selection that has already satisfied EN-4. No readability re-check, re-derivation, or second gate is
introduced at those boundaries, and none may be inferred. This keeps one decision at one place and
keeps every future format free of policy.

**EN-8 (Confirmed) — Strictly additive; released records are immutable.** Final Selections, SRT
Artifacts, materializations, deliveries, and publications that already exist — including any made
while a Candidate carried blocking findings — are **not** rewritten, invalidated, withdrawn,
re-derived, superseded, or flagged. EN-4 governs **new** admissions only. This follows `§12.2`, which
forbids auto-applying a changed rule to existing decisions, and `§16` R-14.

**EN-9 (Confirmed) — Scope is the readable generation.** Enforcement applies to Candidates produced
by `readable_cue_composition`. It is **not** applied retroactively or prospectively to
`deterministic_segment_passthrough` Candidates, which are not composed under the readability policy
and whose cues were never proposed as conforming display units. A passthrough Candidate's
selectability is unchanged in every respect.

**EN-10 (Confirmed) — No parameter changes.** `22`, `44`, `0.100 s`, `1.000 s`, `7.000 s`, and the
CPS threshold of `12` are unchanged, and the readability parameter version is unchanged. The three
blocking findings observed in the validation corpus **remain**, and under EN-4 that Candidate becomes
un-selectable rather than silently deliverable. Reducing them is a separate Product Decision about a
future parameter version and is explicitly not made here.

**EN-11 (Confirmed) — R-4/R-6 recovery reference, recorded.** `§16` R-6 authorizes merging adjacent
cues whose text is character-identical and states that the merged cue carries the text **once**.
R-4's exact-recovery requirement is therefore evaluated against the canonical source sequence **after
R-6's authorized identical-duplicate collapse**. This is derivation, not extension: reading R-4
against the raw sequence would make R-6 inoperative in every case it governs, and a reading that
nullifies an explicit Confirmed decision is unavailable. The reference admits **no** other deviation
— semantic merge, near-identical merge, whitespace-insensitive merge, and any other text loss or
addition remain prohibited and remain blocking under R-11.

## Non-goals

Not decided and each requiring its own gate evaluation: any change to the readability parameter set
or its version; a Candidate-comparison interface; a Modify decision that edits cue structure; an
automatic re-selection or re-issue of released output; retroactive enforcement against passthrough
Candidates; enforcement in the legacy contract generation; a readability gate at any downstream
boundary; export-eligibility semantics beyond `§16`; and every item already deferred by `§16`.

## Required Blueprint Changes

Applied to `docs/041_SUBTITLE_PIPELINE.md` only. No other Blueprint file requires amendment: the
effective-generation Final Selection carries no separate Blueprint section — `implementation/106`
records that it was introduced under the released `§4.8` responsibility and the `§15` generation with
no dedicated PATCH — so the enforcing contract belongs where the policy already lives.

1. **Header** — Blueprint version and Last Updated advanced; `PATCH-0042` added to `Amended By`.
2. **§16** — a new subsection carrying EN-1…EN-11 and its own Canonical Invariants.
3. **§16 *Sections Not Re-scoped*** — amended so it no longer asserts the Final Selection contract is
   unchanged, while continuing to assert that for the SRT Artifact, materialization, delivery,
   publication, legacy generation, passthrough generator, and canonical SRT serializer.
4. **§4.5** — released sentence kept verbatim; forward note recording that for the effective
   generation the refusal it states is realized at Final Selection admission per EN-4.
5. **§4.8** — released text kept verbatim; forward note recording that the structural validation this
   stage reflects includes `§16` R-11 readability for readable Candidates.

## PATCH Acceptance Criteria

Verified against the Blueprint amendment, before this PATCH may be marked `Accepted`. These say
nothing about code.

- [x] §16 carries EN-1…EN-11 as written here.
- [x] No released sentence in `docs/041` is deleted or rewritten; prior PATCH notes are treated as
      released text and are likewise untouched; verified line by line.
- [x] §4.5 and §4.8 gain **additive forward notes only**.
- [x] The *Sections Not Re-scoped* amendment removes only the Final Selection assertion and leaves
      every other assertion in force.
- [x] The enforcing boundary is named unambiguously as Final Selection admission, and Review
      Preparation and Human Decision are stated as admitting.
- [x] Warnings are stated as carrying no admission consequence.
- [x] Existing records are stated immutable and the change is stated strictly additive.
- [x] The parameter set and its version are stated unchanged, and the three known blocking findings
      are stated as remaining.
- [x] The change set contains no implementation, schema, migration, or test change.

## Implementation Requirements

Required validation for the implementing milestone. **Not satisfied by this PATCH.**

1. Final Selection admission re-derives readability and refuses a Candidate with any blocking
   finding, naming the findings.
2. A Candidate with warnings only is selectable.
3. Review Preparation and Human Decision admit a Candidate carrying blocking findings.
4. A refused selection writes nothing; Candidate, cues, lineage, Review Subject, and Decisions are
   byte-identical afterwards.
5. Passthrough Candidates are unaffected in generation, review, selection, and export.
6. No downstream boundary gains a readability check.
7. Existing Final Selections, artifacts, materializations, deliveries, and publications are
   unchanged and are not re-derived or flagged.
8. The real-fixture readable Candidate — three blocking findings — is refused at Final Selection, and
   the refusal enumerates the three affected cues.
9. The complete test suite passes and the schema version is unchanged.

## Changed Blueprint Files

- `docs/041_SUBTITLE_PIPELINE.md` — §16 enforcement subsection (EN-1…EN-11 + Canonical Invariants);
  forward notes on §4.5 and §4.8; scope-narrowing note on §16 *Sections Not Re-scoped*; header
  (`Version`, `Last Updated`, `Amended By`). **+112 / −2 lines**; the two deletions are the two
  header metadata lines, so every substantive change is an insertion.

No other Blueprint file was amended. The effective-generation Final Selection carries no separate
Blueprint section — `implementation/106` records it as introduced under the released `§4.8`
responsibility and the `§15` generation with no dedicated PATCH — so the enforcing contract belongs
where the policy already lives.

## Result

**Applied.** §16 carries EN-1…EN-11 and ten enforcement Canonical Invariants. Preservation was
verified mechanically: `git diff --check` clean, two deleted lines both header metadata, and each
released sentence the notes attach to confirmed present verbatim afterwards — §4.5's refusal, §4.8's
Final Subtitle definition, §4.6's responsibility to connect Validation Failure to Review Items, §6's
threshold deferral, §13's open questions, and PATCH-0029's contract-generation annotation. All eight
`PATCH-0041` references survive, R-1…R-14 and L-1…L-5 are intact, and `src/` and `tests/` are
unchanged with the schema at v53.

`PATCH-0041`'s *Sections Not Re-scoped* sentence was narrowed by note rather than rewritten, so the
record of what that PATCH declined to re-scope stays legible beside what this one changed.

The implementing milestone has not started. *Implementation Requirements* is the open obligation
list: Final Selection admission does not yet consult readability, and until it does the enforcement
contracted here is not in effect in code.

## Consequences

- `§16` gains an enforcement contract; `§4.5` and `§4.8` gain forward notes; the *Sections Not
  Re-scoped* clause narrows by exactly one boundary.
- One implementation slice adds a check at Final Selection admission. No schema change is expected:
  readability is derived from the immutable cue graph and stored nowhere.
- The readable Candidate produced during validation becomes **un-selectable** until a future
  parameter version or a human-authored alternative resolves its three blocking findings. That is the
  intended consequence of EN-1, and the previously materialized output stays as immutable history
  under EN-8.
- `PATCH-0041` R-11's "blocking" acquires the consequence its name asserts.
