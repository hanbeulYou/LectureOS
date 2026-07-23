# PATCH-0011

- Title: Lecture Segmentation Application Foundation (042 Milestone 3)
- Status: Completed
- Priority: Medium
- Trigger: Architect / Product Owner Decision (042 Milestone 3 architecture-first investigation)
- Created: 2026-07-23
- Target Blueprint: `docs/042_LECTURE_INTELLIGENCE_PIPELINE.md`

---

## Summary

An architecture-first investigation of the third dependency-ordered 042 milestone — **Lecture Segmentation
Application Foundation** — found that `042 §7` and `030 §8.1` fix what a Lecture Segment *means* but that its
durable-record contract was undefined: durability/immutability were unconfirmed; the mandatory canonical
anchor was unassigned; the minimum boundary/multiplicity rules (overlap, nesting, hierarchy, multi-range)
were `§18` Requires-Validation / `030 §16` open; the reprocessing/supersession mechanism was deferred; and
Segment Labels, multiple segmentation views, and confidence/uncertainty/rationale semantics were undecided.
The Product Owner approved the minimal decision resolving exactly the contracts the first Segmentation
milestone needs, reusing the durable-stage precedent established by Eligible Analysis Input (`§5.1`,
PATCH-0009) and Analysis Finding (`§8.1`, PATCH-0010).

This PATCH records that decision by promoting the first Segmentation milestone into a **Confirmed** normative
contract (new `§7.1`). It defines **no** implementation, SQL, repository, execution, or provider API, and
resolves nothing belonging to later milestones. `042` remains the single source of truth.

## Problem Statement

**F-01 — The Lecture Segment's durable-record contract was undefined.** `§7`/`§3.3` fix the Segment's meaning
(an interpreted semantic/functional region of the Source Timeline, provider-independent, not an Edit
Candidate), but the **record's durability/immutability/identity**, the **mandatory anchor**, the **minimum
boundary contract**, and the **reprocessing stance** were `§18` Requires-Validation / Deferred (and
`030 §8.1`/`§16` left nesting/overlap and the record contract open). Absent a decision, engineering would
invent durable product meaning.

**F-02 — Segmentation is provider-driven; the provider boundary and milestone scope needed fixing.** A
provider's segment output is never canonical (`§7`, `§2.10`); the first milestone had to be scoped as an
Application Foundation with a provider-independent boundary (the `040`/`§8.1` precedent), and it had to be
bounded so that undecided concepts — Labels, multiple views, confidence/uncertainty/rationale semantics —
were not silently introduced.

## Architect / Product Owner Decision (Confirmed)

For **042 Milestone 3 — Lecture Segmentation Application Foundation** (recorded as `042 §7.1`):

- **D-1 — Lecture Segment Record:** a durable canonical domain record — **immutable**, **identity-owning**
  (Application identity), **provenance-bearing**, **replay-safe**, **provider-independent**, **insert-only**.
  No lifecycle states. Follows the Eligible Analysis Input / Analysis Finding durable-stage precedent.
- **D-2 — Canonical Anchor:** every Segment is anchored to **exactly one `EligibleAnalysisInput`** whose
  eligibility is **ELIGIBLE** (`§5.1`). It is **not** anchored to any Analysis Finding and requires no
  Finding. Source Timeline and Source Media are provenance **inherited through** the anchoring input, not the
  direct anchor. One `EligibleAnalysisInput` may anchor many distinct Segments. Provenance chain:
  `Lecture Segment → EligibleAnalysisInput → Transcript Readiness → selected Corrected Transcript lineage →
  Source Timeline → Source Media`.
- **D-3 — Minimum Boundary:** every Segment carries **exactly one required Source Timeline Time Range** on the
  anchoring input's Source Timeline (finite, non-negative, `start <= end`); the Range is **mandatory and
  single**. No inter-segment relationship is modeled: **overlap, nesting, hierarchy, containment, adjacency,
  and multi-range are deferred**, as is boundary-uncertainty representation. A whole-recording Range is
  permitted; a per-admission `sequence` is an ordinal only and guarantees no semantic ordering/adjacency.
- **D-4 — Reprocessing:** the milestone establishes **immutable, insert-only** Segments; **revision,
  supersession, and reconciliation are deferred**. The `§7` requirement that reprocessing not obscure prior
  provenance/Review is met at the minimum by immutability plus provenance (prior Segments are never mutated
  or deleted; reprocessing inserts new records). No supersession link or reconciliation mechanism is added.
- **D-5 — Milestone Scope:** the milestone establishes **only the canonical Lecture Segment record** and its
  provider-independent Application boundary admitting a **normalized, provider-independent segmentation
  result**. It does not invoke AI, implement a provider, define prompts/models, or create a Segment Label,
  Analysis Finding, Edit Candidate, or Review Item; raw provider output/classifications/identifiers/internal
  reasoning never enter the canonical domain; the concrete segmentation provider is deferred. The milestone
  establishes **no confidence, uncertainty, or rationale semantics** and takes **no position on where such
  properties would attach** if introduced later. It imposes no canonical-set/uniqueness constraint and models
  no named view, so "no single canonical segmentation is forced" (`§7`, `§19`) is preserved.
- **Admission Boundary:** a Segment may be admitted only from **exactly one ELIGIBLE `EligibleAnalysisInput`**,
  a **running unit execution**, complete upstream provenance, and a Time Range matching the input's Source
  Timeline lineage; all upstream objects are consumed **read-only**.

## Scope

- Records the approved Lecture Segmentation Application Foundation contract as normative `042 §7.1` and a
  confirming note in `§18`.
- Adds a minimal cross-reference in `030_DATA_MODEL.md §8.1` promoting the now-confirmed Lecture Segment
  record contract while leaving nesting/label taxonomy/revision explicitly deferred.

## Out of Scope (Deferred to later 042 / other milestones)

Segment Label and label taxonomy; multiple segmentation views, perspective groups, grouping aggregates, view
identities; confidence, uncertainty, and rationale semantics (including where they attach); overlap, nesting,
hierarchy, containment, adjacency, multi-range Segments, boundary-uncertainty representation; revision,
supersession, reconciliation; segmentation quality; concrete segmentation providers, prompt design, model
selection; Edit Candidates; Review (`§18`). Also out of scope: any implementation, SQL, schema, migration,
repository, execution code, provider API, lifecycle state, or Goal.

## Compatibility Notes

- **No canonical concept added; no released meaning changed.** `§7.1` confirms a durable-record contract for
  the Segment already described by `§7`/`§3.3`; it does not re-define `§7`, and the illustrative "may have"
  properties in `§7` (Labels, confidence/uncertainty, revision relationships) remain deferred, not removed.
- **No change** to `040`, `041`, `043`, `044`, or to the completed v1..v24 records/meanings. The Segment
  admits the canonical `EligibleAnalysisInput` read-only.
- **Additive only:** the subsequent implementation milestone is expected to add strictly additive persistence
  (a new schema version) for the Lecture Segment record, preserving every released v1–v24 meaning.
- `042` remains the single source of truth; `030` carries a cross-reference only.

## Acceptance Criteria

- [x] The first Segmentation milestone (Lecture Segmentation Application Foundation) is promoted to a
  confirmed normative contract (`§7.1`).
- [x] Lecture Segment is a durable, immutable, identity-owning, provenance-bearing, replay-safe,
  provider-independent, insert-only canonical record; revision/supersession deferred.
- [x] Every Segment is anchored to exactly one ELIGIBLE `EligibleAnalysisInput`; Source Timeline/Media are
  inherited provenance; no mandatory Analysis Finding relationship; deterministic provenance chain.
- [x] Exactly one required, single Source Timeline Time Range (finite, `start <= end`); overlap, nesting,
  hierarchy, containment, adjacency, multi-range, and boundary uncertainty deferred.
- [x] Reprocessing contract is immutable insert-only; revision, supersession, and reconciliation deferred; no
  downstream Review reconciliation invented.
- [x] Milestone scope is the Segment record only; Segment Labels, views, grouping, and confidence/uncertainty/
  rationale semantics (and their ownership) are deferred; no position taken on where those attach.
- [x] Provider-independent Application boundary confirmed; no AI/provider/prompt/model/Label/Finding/
  Candidate/Review Item; concrete provider deferred.
- [x] Existing deferrals preserved (`§7.1`, `§18`); `030 §8.1` cross-reference added.
- [x] No implementation, schema, repository, provider, lifecycle state, or Goal is introduced.

## Result

- Status: **Completed**
- Changed Blueprint Files: `docs/042_LECTURE_INTELLIGENCE_PIPELINE.md` (new §7.1; §18 confirming note; header
  amended). Cross-reference: `docs/030_DATA_MODEL.md §8.1`.
- Notes: Records the Product Owner's approved decision for 042 Milestone 3. Product policy/clarification only;
  no schema, code, or Goal. The next step is implementation of the Lecture Segmentation Application Foundation
  milestone; all later 042 concerns remain deferred.

## Related Documents

- `PATCH-0008-delivery-deferral.md`
- `PATCH-0009-lecture-analysis-input-eligibility.md`
- `PATCH-0010-analysis-finding-application-foundation.md`
- `../docs/042_LECTURE_INTELLIGENCE_PIPELINE.md`
- `../docs/030_DATA_MODEL.md`
