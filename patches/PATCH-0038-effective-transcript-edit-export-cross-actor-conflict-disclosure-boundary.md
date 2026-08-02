# PATCH-0038

- Title: Effective-Transcript Generation Edit Export Cross-Actor Conflict Disclosure Boundary (044)
- Status: Accepted
- Priority: High
- Trigger: Architect Decision (Edit Export Cross-Actor Conflict Policy — **Alternative C**: export the
  remaining eligible members and disclose the Conflict as a mandatory component of the admission
  result)
- Created: 2026-08-02
- Target Blueprint: `docs/044_EXPORT_PIPELINE.md` (new §26; forward notes on §23 EA-5 and its
  Deferred list; §15.1 confirming note; §15.3 correction note; §15.4 scope note; header amended),
  `docs/043_REVIEW_PIPELINE.md` (one §7.6 note)

---

## Status

Accepted. **Documentation only.** It adds no implementation, no schema change, no migration, no
application code, no serializer change, no file-writer change, no repository, no validator, no CLI
change, no test, and no Goal. The SQLite schema remains **v53**.

It introduces **no new aggregate, no new product domain, no new human authority, no Conflict
resolution policy, no actor priority, no recency rule, no role or permission ranking, no automatic
merge, no automatic selection, no Final Selection, no Artifact change, no serializer change, no JSON
format change, no persistent record, no lifecycle, and no status field.**

It is **not** a PATCH that resolves cross-actor Conflict. It fixes only how Export Admission behaves
while one exists, and how that fact is disclosed. Resolution stays with Review.

## Context

`PATCH-0035`…`PATCH-0037` and GOAL-030…GOAL-032 carried this generation's Edit Export branch from
Review to a local file at schema v53:

```text
ApprovedEditDecision → LectureEditExportAssembly (§23) → LectureEditExportArtifact (§24)
  → lectureos-lecture-edit-export-json v1 → one local file (§25)
```

`§23` deliberately left three product policies undecided. `§23` EA-5 states them in its own words:
"**이 절이 결정하지 않는 것:** Conflict가 존재하는 Source Timeline에서 Export Admission의 제품 동작 —
Assembly를 admit하는지, 나머지 적격 편집만 admit하는지, 그 timeline의 admission을 거부하는지, 그리고
Conflict를 export 시점에 어떻게 드러내는지." This PATCH decides **the first of the three** and
nothing else.

The released implementation currently stops admission when any Conflict exists, and reports that stop
as an **undecided-policy** signal rather than a product refusal — precisely so that this decision
could be made deliberately rather than inherited from an implementation. That posture is what this
PATCH now closes.

## Trigger

The Architect Decision compared four alternatives — refuse the whole timeline (A), exclude and
proceed silently (B), exclude and proceed with mandatory disclosure (C), and refuse with a structured
Conflict report (D) — and selected **C** on four verified grounds.

1. **`044 §3.7` permits a limited scope and forbids only concealment.** "Export Scope는 하나의
   export가 포함하는 승인 결과의 범위를 설명한다. 전체 승인 결과 또는 **명시적으로 선택된 일부 결과**를
   대상으로 할 수 있다. **Scope가 제한되었음을 숨기거나** 제외된 결과를 승인되지 않은 것으로 해석해서는
   안 된다." The Blueprint has never prohibited a partial scope; it prohibits hiding that it is
   partial. `043 §3.12` and `§11` impose the matching obligation from the Review side: an unresolved
   Conflict "사용자가 차이를 이해하고 다시 판단할 수 있도록 **표시되어야 한다**" and must never be
   hidden as a normal approved outcome.

2. **A Conflict is not an Export Failure.** `044 §3.10` defines failure as approved results that
   could not be made into the required external representation "완전하고 추적 가능하게". The eligible
   members are represented completely and traceably; what is unresolved is a Review state, not an
   export capability. `§11.1` Incomplete Export Input concerns an input lacking approved status or
   traceability — a Conflict Candidate is not an input at all, because `EA-4` already excludes it.

3. **Refusing the timeline privileges one of five ineligibility reasons with no contract basis.**
   `EA-4` states three conjunct conditions and ranks none of them. A Candidate can fail export
   eligibility five ways — no recorded authority history, a current judgment that approves nothing, a
   chain superseded by authority change, a chain whose current authority is ineligible, and a
   cross-actor Conflict. Four are ordinary exclusions; treating the fifth as a timeline-wide veto is
   a ranking the released text does not make.

4. **Refusing is not the neutral option.** Granting one unresolved Candidate the power to withhold
   every resolved approved edit on its timeline is itself a judgement about how much weight an
   unresolved Conflict carries — a stronger one than excluding it. Neither refusing nor excluding is
   "deciding nothing". What the Blueprint actually requires is not that Export withhold, but that
   Export **not conceal**. C implements that distinction exactly.

## Problem

**P-01 The exclusion is a consequence, but the silence would be a decision.** `043 §7.6` AH-9 derives
**no** current operative judgment when two or more actors hold authority history on one Candidate, so
that Candidate satisfies neither `EA-4` (i) nor (ii) and contributes no member. That much is
arithmetic, not judgement. But a resulting Assembly, Artifact, and file that say nothing about the
excluded Candidate would present a partial approved scope as if it were the whole one — which
`§3.7` forbids and `§3.12` independently forbids from the Review side. The exclusion therefore needs
no new rule; the **disclosure** does.

**P-02 A Conflict differs in kind from the other four exclusions, and the difference must be
expressed without becoming a veto.** A `reject` is a decision; a superseded judgment is history; an
ineligible chain is a recorded authority state. Each is *settled*. A cross-actor Conflict is
**unsettled** — a person's judgment is pending. Treating it with the same silence as the other four
would understate it; treating it as a veto would overstate it. The proportionate expression of that
difference is a **mandatory disclosure obligation**, which the other four do not carry.

**P-03 Disclosure must not contaminate approved meaning.** The Assembly is an immutable canonical
record and a Conflict is a transient observation, so a Conflict column on the Assembly would freeze a
changing fact into an unchangeable record. The Artifact and the serialized document carry **approved
meaning**, and a Conflict is not approved meaning. Any disclosure must therefore live outside all
three, without a new record, a new field, or a new format version.

**P-04 The disclosure boundary already exists and must be named, not invented.** The released
admission result already carries the derived scope observation, including the conflicted Candidates
and the actors holding history on each. What is missing is not a structure but an **obligation**:
nothing currently says that this information may not be discarded by the layer that receives it.

## Architect Decision (Confirmed)

Eleven decisions, to be encoded normatively as `044 §26`, CD-1…CD-11. Summarized here; `§26` is
authoritative once applied.

1. **CD-1 Scope and Instrument.** This subsection applies to the **effective-transcript generation**
   only and decides **one** of the three product policies `§23` EA-5 reserved: the behaviour of Export
   Admission on a Source Timeline holding a cross-actor Review Conflict, and how that fact is
   disclosed. It decides **nothing** about overlap adjudication, about a scope with no eligible
   member, or about how a Conflict is resolved. `§19`–`§25`, `043`'s subsections, and `042`'s
   subsections are not re-scoped, and the legacy generation is unaffected.

2. **CD-2 Admission Proceeds.** A cross-actor Conflict on a Source Timeline **does not prevent**
   Assembly admission. When at least one export-eligible `ApprovedEditDecision` remains on that
   timeline, the Assembly is admitted. **A Conflict is not a timeline-wide veto**, and the existence
   of an unresolved judgment on one Candidate confers no authority over the export of others.

3. **CD-3 Membership Is Unchanged, and the Exclusion Means Nothing More.** The conflicted Candidate
   contributes no member. This is **the direct consequence of `EA-4` (i) and (ii)** — AH-9 derives no
   current operative judgment, so there is no approval owned by one — and **not a new filter, a new
   exclusion rule, or an Export judgement**. Export does **not** interpret the excluded Candidate as
   rejected, as superseded, as resolved, as withdrawn, or as unapproved; its Review records,
   authority history, and any `ApprovedEditDecision` it owns remain exactly as they are and remain
   valid (`§7.5` R-5, `§23` EA-4).

4. **CD-4 Remaining Eligible Members Are Unaffected.** Every other export-eligible
   `ApprovedEditDecision` on that Source Timeline composes the membership exactly as `§23` EA-3
   requires. **EA-3's totality is unchanged**: the Assembly still denotes *every* export-eligible
   approved edit of its timeline. A cross-actor Conflict elsewhere on the timeline never withholds an
   eligible member.

5. **CD-5 Disclosure Is Mandatory.** When any Candidate on the timeline is in a `§3.12` cross-actor
   Review Conflict, the admission result **must disclose it**. The disclosure is:
   **not** an optional warning; **a required component of the result contract**, so omitting it is a
   contract violation rather than a stylistic choice; **separate from Assembly membership**;
   **separate from the Artifact's approved meaning**; **separate from the serialized payload**; and it
   **requires no persistence**. `§3.7`'s prohibition on concealing a limited scope and `§3.12`'s
   requirement that a Conflict be surfaced are satisfied here and only here.

6. **CD-6 Minimum Disclosure Content.** The disclosure carries at least, for each conflicted
   Candidate on that Source Timeline: **(a)** the Candidate identity; **(b)** every actor identity
   holding authority history on it; **(c)** the fact that **no current operative judgment is
   derived**; and **(d)** the fact that the Candidate **is not part of this Assembly's membership**.
   Items (c) and (d) are stated because their absence is exactly what would be misread. A richer
   observation may already be available, and presenting more of it is permitted — but this subsection
   **invents no new product meaning**, defines no severity scale, no Conflict classification, no
   count-dependent behaviour, and no ordering among actors.

7. **CD-7 Result Model — Disclosure-Bearing Success.** The outcome is a **success that carries a
   disclosure**. It is **not** a failure, a partial failure, a silent success, an optional warning, a
   best-effort export, a degraded success, or a new lifecycle state, and it introduces **no status
   field and no state machine**. The Assembly is admitted normally and is in every respect an ordinary
   Assembly; the disclosure accompanies the result of the admission that produced it.

8. **CD-8 Authority Separation Is Unchanged.** Export does **not** rank actors by priority, recency,
   role, or permission; does **not** merge or select automatically; and does **not** resolve, reopen,
   re-approve, or reject anything. **Review remains the only stage at which Human Authority is
   exercised** (`043 §13`, `§2.8`, `§23` EA-6, `§24` AR-9, `§25` S-11). `043 §15.3`'s multi-user
   authority question stays **declined, not answered**, and `§7.6` AH-9 is unchanged: this subsection
   consumes AH-9's outcome and adds nothing to it.

9. **CD-9 Downstream Boundary, and the Exact Reach of the Non-Suppression Obligation.** The `§24`
   Artifact, the `§25` serializer, and the `§25` materializer **do not re-evaluate** Conflict,
   eligibility, standing, or authority (`§24` AR-8), and the disclosure is **not inserted** into the
   Artifact, the serialized document, or the file.

   The obligation this subsection fixes binds **the direct consumer of the admission result, and only
   it**: an Application or Interface layer that receives an admission result must not **discard** the
   Conflict disclosure it carries, must not **reduce** the outcome to a Conflict-free ordinary
   success, and must not **substitute** an Assembly-only result that carries no disclosure.
   Presentation — wording, ordering, severity, placement — is that layer's concern; **suppression is
   not**. The obligation does not travel transitively: it is discharged by the layer that receives
   the result, and this subsection places no requirement on anything further downstream.

   **This subsection accordingly does not decide** whether the `§24` Artifact must carry a Conflict
   disclosure; whether the `§25` serializer must place a Conflict or partial-scope indication in the
   JSON payload; whether the `§25` materializer must produce a separate Conflict file alongside the
   export; whether a future delivery or Export Package layer must preserve a disclosure; or whether an
   external consumer holding only the local JSON file must be able to learn that the scope was
   limited. All five stay deferred with `§15.3`'s scope-completeness question and the later
   delivery and packaging contracts.

10. **CD-10 No New Structure.** No new aggregate, Conflict Artifact, Conflict Report Artifact,
    `DomainResult`, persistent diagnostic record, Assembly column, Artifact field, serializer field,
    JSON format version, lifecycle, or status field is introduced. The disclosure uses the **admission
    observation and result boundary that already exists**. Nothing is persisted: the Conflict is a
    derived observation of append-only rows and is re-derived on each admission (`§7.5` R-4, `§7.6`
    AH-8, `§23` EA-7).

11. **CD-11 Zero Eligible Member Is Not Decided Here.** If excluding the conflicted Candidates leaves
    **no** export-eligible member on the timeline, this subsection **does not say what happens**. That
    is the second of `§23`'s reserved policies and it stays reserved in full: an empty Assembly, an
    outright refusal, a disclosure-only result, a no-op success, and a separate diagnostic result are
    **all still undecided**, and an implementation may not settle any of them. On reaching that state
    the existing undecided-policy stop is retained. The two situations are separable — this one asks
    whether a Conflict blocks, that one asks whether a zero-member scope is admissible — and they
    intersect only when every Candidate is conflicted, where **the undecided policy governs**.

## `§15.3` Handling

`PATCH-0035` recorded on `§15.3`'s second question that, because EA-3 makes membership total, "그
세대에서는 부분 Scope 자체가 발생하지 않으며 이 질문이 제기되지 않는다". That note **cannot stand
unchanged**: under CD-2/CD-3 a Candidate holding an approval can now sit outside the membership while
the rest of the timeline is exported, so a partial scope in the ordinary sense of the question is
reachable.

The released sentence is **not deleted or rewritten**; a follow-up note records the corrected state:

- **Confirmed:** at the admission result, the Conflict and the fact of exclusion are **always
  disclosed** (CD-5, CD-6).
- **Still deferred:** whether the serialized document itself must indicate a Conflict or a limited
  scope; how a consumer holding only the file learns of the limitation; what wording or severity an
  interface uses; and how a disclosure is preserved across a future delivery or packaging layer.

## Affected Contracts

- `docs/044 §26` — new subsection, CD-1…CD-11 plus "Sections Not Re-scoped" and "Deferred".
- `docs/044 §23` EA-5 — one forward note on its "이 절이 결정하지 않는 것" clause: the first of the
  three reserved items is decided by `§26`; overlap and the zero-eligible-member case stay reserved.
- `docs/044 §23` Deferred — one note with the same correction.
- `docs/044 §15.1` — one Confirmed note recording CD-1…CD-11.
- `docs/044 §15.3` — one correction note, as set out above.
- `docs/044 §15.4` — one note: the Conflict behaviour is confirmed; overlap, the zero-eligible-member
  case, and the document-level partial-scope indication stay deferred.
- `docs/043 §7.6` — one note on AH-9: its outcome is now **consumed** by `044 §26`, which derives
  nothing further from it; AH-9 itself and `§15.3`'s declined multi-user question are unchanged.
- Unchanged in meaning: `044 §1`–`§22`, `§24`, `§25`; `043 §3.12`, `§7.5`, `§7.6` AH-1…AH-12,
  `§11`, `§15.3`, `§15.4`; all of `042`, `041`, `040`, `030`; every released record.

## Required Blueprint Changes

- `docs/044_EXPORT_PIPELINE.md` — new `§26` (CD-1…CD-11); two `§23` notes (EA-5 and Deferred); one
  `§15.1` Confirmed bullet; one `§15.3` correction note; one `§15.4` note; header amended to
  Blueprint 1.1 / Amended By PATCH-0038.
- `docs/043_REVIEW_PIPELINE.md` — one `§7.6` note on AH-9.

## Legacy Compatibility

The legacy generation is untouched: `§19`–`§22` never had cross-actor authority history at all,
because `§7.4`'s Alternative A stores no authority positions. No released record, document, golden, or
byte sequence changes, and no migration is required; the schema stays at **v53**.

## Deferred (unchanged or newly recorded by this PATCH)

Still reserved from `§23`, in full: **overlap adjudication and inter-decision ordering semantics**,
and **the treatment of a scope with no export-eligible member** (CD-11). Still deferred from
`§15.3`/`§15.4`: whether the serialized document must indicate a Conflict or a limited scope, how a
file-only consumer learns of a limitation, interface wording and severity, and disclosure across a
future delivery or packaging layer. Still deferred from `043 §15.3`/`§15.4`: the interpretation of
authority across actors, the same-kind/different-approval history representation, **withdrawal**, and
**revocation**. Unchanged from `§21` B-15 and `§22` C-14: other concrete formats, cross-format
equivalence, Export Profile and Export Configuration, provider and NLE adapters, executable edit
semantics, output-timeline transformation, rendering, delivery, packaging, publication, and retry
lifecycle.

## Explicit Non-goals

- No implementation, schema, migration, application code, serializer change, file-writer change,
  repository, validator, CLI change, test, demo, golden, or Goal; the schema stays at **v53**.
- **No Conflict resolution policy of any kind** — no withdrawal, no revocation, no authority-position
  retirement, no replacement authority, no actor priority, no recency comparison, no role or
  permission ranking, no automatic merge, no automatic selection.
- **No new aggregate, product domain, human authority, Conflict Artifact, Conflict Report,
  `DomainResult`, persistent record, lifecycle, or status field.**
- **No Artifact, serializer, JSON, or format-version change**, and no Conflict content in any exported
  document.
- No Final Selection, no Export Approval, no re-approval, no rejection.
- No overlap policy and **no general no-eligible-member policy**.
- `043 §7.6` AH-9 is not re-scoped and `043 §15.3` is not answered.

## Acceptance Criteria

- [x] The cross-actor Conflict behaviour of Export Admission is Confirmed in the Blueprint, without
  deleting or rewriting a single existing sentence of `§19`–`§25` or `043`.
- [x] Admission is stated to **proceed** when at least one eligible member remains, and a Conflict is
  stated **not** to be a timeline-wide veto (CD-2).
- [x] The exclusion is recorded as the **direct consequence of `EA-4`**, together with the explicit
  statement that it means nothing further — not rejected, superseded, resolved, withdrawn, or
  unapproved (CD-3).
- [x] `EA-3`'s totality is preserved and stated to be unaffected (CD-4).
- [x] Disclosure is fixed as **mandatory and part of the result contract**, with omission declared a
  contract violation, and its separation from membership, approved meaning, payload, and persistence
  is stated (CD-5).
- [x] The four minimum disclosure items are enumerated, including the two that exist precisely because
  their absence would be misread, and no severity scale, classification, ordering, or count-dependent
  behaviour is invented (CD-6).
- [x] The result model is named **disclosure-bearing success** and the six things it is not are
  enumerated (CD-7).
- [x] Authority separation is restated, `043 §15.3` is left declined, and AH-9 is left unchanged
  (CD-8).
- [x] The downstream boundary is fixed: no re-evaluation and no insertion into the Artifact,
  document, or file; the **non-suppression obligation** bound to the **direct** consumer of the
  admission result and stated as three prohibited behaviours (discard, reduce, substitute); declared
  non-transitive; and the five questions it does **not** decide — Artifact, serializer, materializer,
  delivery/package, and file-only consumer — enumerated as deferred (CD-9).
- [x] No new structure of any kind is introduced, and the existing admission observation and result
  boundary is named as the disclosure site (CD-10).
- [x] The zero-eligible-member case is recorded as **not decided**, with all five candidate behaviours
  listed as still undecided and the existing stop retained (CD-11).
- [x] `§15.3`'s PATCH-0035 note is corrected by a follow-up note rather than edited, separating what
  is now confirmed from what stays deferred.
- [x] The permanent-Conflict risk is recorded, with its own Architect Decision named and no remedy
  pre-selected.
- [x] Schema remains v53; no code file changes; one documentation commit with a clean working tree.

## Remaining Risk

**Permanent Conflict.** This is the most serious item this PATCH records and does not solve.
`043 §7.6` AH-9 derives a Conflict whenever two or more actors hold authority history on one
Candidate. Authority positions are **append-only**, and the released contracts define **no**
withdrawal, revocation, authority-position retirement, or replacement authority — `§15.4` keeps
withdrawal and revocation deferred. The set of actors holding history on a Candidate can therefore
only grow. A second actor judging **identically** to the first does not clear the Conflict either,
because AH-9's condition counts actors, not disagreement.

The consequence is that a cross-actor Conflict, once created, may be **permanent under current
contracts**, and the approved edit of that Candidate may never enter any Assembly.

This materially changes what the four alternatives meant. Under Alternative A it would have meant a
Source Timeline permanently unable to export anything at all, which is why A was rejected: its stated
virtue — forcing the user back to Review — is not available, because there is currently nothing in
Review that clears the state. **Alternative C bounds the damage to the single affected Candidate**
rather than the whole timeline, and CD-5's disclosure ensures the situation is visible on every
admission rather than silently persistent. It does **not** repair it.

Closing this requires its own Architect Decision, expected as **Effective Transcript Generation Review
Cross-Actor Conflict Resolution Boundary**, whose plausible subjects include actor authority
interpretation (`043 §15.3`), withdrawal, revocation, authority-position retirement, replacement
authority, and the audit history of a resolution. **This PATCH pre-selects none of them**, and an
implementation may not introduce any of them under this contract.

**A disclosure can still be dropped by a caller.** CD-9 obliges the receiving layer not to suppress
the disclosure, but this is a contract on that layer, not a mechanism. An interface that ignores it
produces exactly the concealment `§3.7` forbids. Whether the obligation should be reinforced further
downstream — in a document, a package, or a delivery record — is deferred with the `§15.3` items.

## Result

- Status: **Accepted**
- Changed Blueprint Files: `docs/044_EXPORT_PIPELINE.md` (new §26 with CD-1…CD-11, "Sections Not
  Re-scoped", "Deferred", and twenty canonical invariants; one §23 EA-5 forward note; one §23
  Deferred note; one §15.1 Confirmed bullet; one §15.3 follow-up note; one §15.4 note; header amended
  to Blueprint 1.1 / Amended By PATCH-0038) and `docs/043_REVIEW_PIPELINE.md` (one §7.6 forward note
  placed immediately after AH-9).
- CD-9 Boundary Tightened Before Application: the drafted CD-9 was directionally correct but
  imprecise on three points and was corrected rather than confirmed. It now (a) binds the obligation
  to the **direct** consumer of the admission result and declares it **non-transitive**, where the
  draft read as binding any downstream layer; (b) names **three** prohibited behaviours — discard,
  reduce to a Conflict-free ordinary success, substitute an Assembly-only result — where the draft
  named only discarding; and (c) enumerates **five** questions it does not decide (Artifact,
  serializer, materializer, delivery/package, file-only consumer), where the draft named only the
  document-level one.
- Released Text Preserved: verified mechanically. The applied diff is +47/−4 lines; of the four
  replaced lines, two are paragraphs whose original text is preserved **verbatim** inside the new
  line, one is a paragraph whose original text is preserved with an inserted parenthetical (checked
  by reconstruction), and one is the `044` header's `Version` metadata field. No released sentence
  and no prior PATCH note was deleted or reworded; every addition is an appended or inserted note.
- Notes: Decides the **first** of the three product policies `§23` reserved, and only that one. No
  schema, code, or Goal is introduced. The next step after acceptance is an implementation milestone
  — removing the Conflict stop and making the disclosure a required component of the admission result
  — with this contract as its basis. The zero-eligible-member policy, overlap adjudication, and the
  resolution of cross-actor Conflict itself all remain undecided and each needs its own approved
  decision.

## Related Documents

- `PATCH-0034-effective-transcript-review-authority-history-boundary.md`
- `PATCH-0035-effective-transcript-edit-export-admission-boundary.md`
- `PATCH-0036-effective-transcript-edit-export-artifact-boundary.md`
- `PATCH-0037-effective-transcript-edit-export-serialization-boundary.md`
- `../docs/044_EXPORT_PIPELINE.md`
- `../docs/043_REVIEW_PIPELINE.md`
- `../implementation/118_LECTURE_REVIEW_AUTHORITY_HISTORY.md`
- `../implementation/119_LECTURE_EDIT_EXPORT_ASSEMBLY.md`
- `../implementation/120_LECTURE_EDIT_EXPORT_ARTIFACT.md`
- `../implementation/121_LECTURE_EDIT_EXPORT_SERIALIZATION.md`
