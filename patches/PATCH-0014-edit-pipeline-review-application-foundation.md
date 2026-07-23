# PATCH-0014

- Title: Edit-Pipeline Review Application Foundation — First Slice (043)
- Status: Completed
- Priority: Medium
- Trigger: Architect / Product Owner Decision (First Edit-Pipeline Review Foundation investigation + Architect Decision)
- Created: 2026-07-23
- Target Blueprint: `docs/043_REVIEW_PIPELINE.md`

---

## Status

Completed. Product policy/clarification only; no schema, code, tests, migration, Review UI, or Goal. Implementation
becomes authorized only after this PATCH is reviewed and accepted.

## Trigger

A Blueprint-first investigation identified the next dependency-ordered milestone as the **first Edit-Pipeline
Review** capability: the missing canonical path `EditCandidate → durable ReviewDecision → durable
ApprovedEditDecision (where applicable)`. Text-Pipeline Review is already implemented; Edit-Pipeline Review is
absent (no durable Edit-Candidate Review Decision, no Approved Edit Decision persistence). `043` was Draft
(Blueprint 0.1) with the durable-record contract, decision-kind vocabulary, Approved-record shape, status
representation, and admission boundary left Requires-Validation / Deferred (§15.3, §15.4; §3.5 defines no
status list). The Architect Decision resolved the minimum durable product contract; this PATCH promotes it.

## Contract Basis

The approved Architect Decision (D-1…D-10) for the first Edit-Pipeline Review slice, built on the completed
Edit Candidate Application Foundation (`042 §9.1`, PATCH-0012) and the Concrete Edit Candidate Generation
Provider first slice (`042 §9.2`, PATCH-0013), both of which remain unchanged.

## Findings

- **F-01 — The Edit-Pipeline Review durable-record contract was undefined.** `043` fixed Review *meaning*
  (Accept/Reject/Modify; Approved Edit Decision preserves range/label/intent/provenance; §15.1) but the durable
  `ReviewDecision` / `ApprovedEditDecision` records, the decision-kind vocabulary, the Approved payload, the
  status representation, and the admission boundary were unconfirmed (§3.5, §15.3, §15.4). Absent a decision,
  engineering would invent durable product meaning.
- **F-02 — Text-Pipeline Review is only a structural precedent.** The existing transcript/subtitle Review
  records may inform structure but do not define the Edit-Pipeline Review / Approved Edit Decision contract,
  which had to be decided explicitly.

## Decision Basis (Confirmed D-1…D-10)

Recorded as `043 §7.4`:

- **D-1 Anchor:** every `ReviewDecision` anchors to **exactly one** durable `EditCandidate`; no multi-candidate
  Review Item, reconciliation, or aggregation; the Candidate and all upstream records stay immutable/read-only;
  no separate durable Review Item record; future grouping is additive and does not change this contract.
- **D-2 ReviewDecision record:** durable, immutable, insert-only, identity-owning, provenance-bearing,
  replay-safe; minimum fields = identity, own Domain Result identity, one referenced `EditCandidate`, decision
  kind, human actor reference, inherited Source Media/Timeline, execution provenance, per-admission sequence;
  direct Domain Result upstream = the Candidate's Domain Result; no note/modify-payload/status/session/history
  fields.
- **D-3 Decision kinds:** closed `{accept, reject, modify}`; unknown values rejected, never aliased/coerced/
  lowercased/mapped; semantics per §7.4; none auto-executes an edit; the closed human-action vocabulary does
  **not** change the open Candidate Type contract of 042 §9.1.
- **D-4 Approved creation:** accept → one `ApprovedEditDecision`, modify → one, reject → none; one
  `ReviewDecision` → at most one `ApprovedEditDecision`; Reject remains durable and auditable; no split/merge/
  multi-output.
- **D-5 ApprovedEditDecision record:** durable, immutable, insert-only, identity-owning, provenance-bearing;
  owns a complete approved snapshot (approving kind accept|modify, approved Time Range, approved Candidate
  Type/label, approved rationale, sequence, denormalized Source Media/Timeline, execution provenance);
  references the source `ReviewDecision` and `EditCandidate`; direct Domain Result upstream = the
  `ReviewDecision`'s Domain Result; suitable as future 044 input; no executable/cut/delete/NLE/rendering/
  export-serialization/auto-execution semantics.
- **D-6 Modify ownership:** the Candidate is never mutated; Modify is a complete approved replacement owned
  solely by the `ApprovedEditDecision` (approved range/type/rationale); the `ReviewDecision` records only the
  judgment + anchor; not a patch/delta/mutation/duplicate; the Approved record is the single canonical
  authority for approved values.
- **D-7 Status:** Alternative A — no durable status field, no state machine, no transitions; meaning carried by
  decision kind + Approved-record existence; revision/supersession/withdrawal/revocation/stale/current-selection
  deferred.
- **D-8 Admission:** running unit execution required; upstream read-only; Application-owned admission (interface/
  UI/API must not persist canonical records); accept/modify atomically admit one `ReviewDecision` + one
  `ApprovedEditDecision`, reject admits one `ReviewDecision`; all-or-nothing; identity collision rejects;
  caller-owned identities; deterministic replay-safe normalized admission; same-identity replay makes no
  duplicates; a new judgment is new insert-only processing; only a human actor reference is required (no UI
  auth / authority-policy framework).
- **D-9 Lineage:** `ApprovedEditDecision → ReviewDecision → EditCandidate → AnalysisFinding →
  EligibleAnalysisInput → corrected transcript/source lineage → SourceTimeline → SourceMedia`; single-direct-
  upstream Domain Result chaining; the Approved record owns approved range/type/rationale and references (does
  not duplicate) Finding/Input/transcript/source; Source Media/Timeline denormalized per existing convention.
- **D-10 Deferrals:** Review Session persistence; separate full Review History model (history preserved by
  immutability); multi-candidate Review Items; multi-user conflict resolution; comprehensive authority policy;
  Candidate reconciliation; revision/supersession; withdrawal/revocation; stale detection; current-selection;
  sufficient-context quality criteria; Review UI; external Review API; export formats; NLE integration;
  automatic edit application; edit rendering; provider-assisted Review; confidence/priority/severity/quality —
  with no placeholder abstraction/field/table/enum/interface.

## Expected Blueprint Changes

- New normative `043 §7.4` recording D-1…D-10; a `§15.1` confirming note; the header amended to Blueprint 0.2 /
  PATCH-0014.
- One minimal cross-reference in `030_DATA_MODEL.md §11.1` (Approved Edit Decision), keeping `043 §7.4` as the
  sole normative owner of the first-slice Review contract.

## Explicit Non-Goals

Any implementation, SQL, schema, migration, repository, execution/admission code, interface/UI/API, or Goal;
export formats and serialization; executable edit operations, cut/delete commands, NLE integration, edit
rendering, automatic edit application; a Review state machine / status transitions; Review Session/History
persistence; multi-candidate Review Items; multi-user conflict resolution or authority policy; Candidate
reconciliation; revision/supersession/withdrawal/stale/current-selection; sufficient-context quality policy;
provider-assisted Review; confidence/priority/severity/quality scores. No 042 §9.1/§9.2 modification.

## Affected Blueprint Files

- `docs/043_REVIEW_PIPELINE.md` — new §7.4 (normative); §15.1 confirming note; header amended.
- `docs/030_DATA_MODEL.md` — §11.1 minimal cross-reference.

## Acceptance Criteria

- [x] A confirmed normative Application Foundation subsection exists in 043 (`§7.4`).
- [x] `ReviewDecision` is durable, immutable, insert-only, single-`EditCandidate` anchored, human-authority
  bearing (actor reference), and provenance-bearing.
- [x] `{accept, reject, modify}` is confirmed as the closed decision-kind vocabulary (unknown rejected, no
  alias/coerce/mapping).
- [x] Accept/Modify → one and Reject → zero `ApprovedEditDecision` is explicit.
- [x] `ApprovedEditDecision` owns the complete approved snapshot and references the ReviewDecision/Candidate.
- [x] Modify leaves the Candidate unchanged and places approved values only on the Approved record (single
  authority).
- [x] No status field or state machine is introduced (Alternative A).
- [x] Admission is running-execution-gated, Application-owned, deterministic, replay-safe, and atomic; the
  interface layer never persists canonical records.
- [x] Domain Result single-direct-upstream chaining and the owned-vs-referenced lineage split are explicit.
- [x] All first-slice deferrals are listed; no placeholder abstraction is introduced.
- [x] No executable editing/export/UI/reconciliation/revision/multi-user policy is introduced.
- [x] No completed 042 contract (§9.1/§9.2) is changed; cross-references are minimal and non-duplicative.
- [x] No code, tests, schema, or migrations changed; `SQLITE_SCHEMA_VERSION` remains 26.

## Result

- Status: **Completed**
- Changed Blueprint Files: `docs/043_REVIEW_PIPELINE.md` (new §7.4; §15.1 note; header). Cross-reference:
  `docs/030_DATA_MODEL.md §11.1`.
- Notes: Records the Product Owner's approved D-1…D-10 decision for the first Edit-Pipeline Review slice.
  Product policy/clarification only; no schema, code, or Goal; no implementation commit (implementation has not
  begun). The next step is implementation of the Edit-Pipeline Review Application Foundation, which becomes
  authorized only after this PATCH is reviewed and accepted. `043 §7.4` is the sole normative owner of the
  first-slice Review contract; `030 §11.1` carries a cross-reference only.

## Related Documents

- `PATCH-0012-edit-candidate-application-foundation.md`
- `PATCH-0013-concrete-edit-candidate-generation-provider.md`
- `../docs/043_REVIEW_PIPELINE.md`
- `../docs/030_DATA_MODEL.md`
- `../docs/044_EXPORT_PIPELINE.md`
