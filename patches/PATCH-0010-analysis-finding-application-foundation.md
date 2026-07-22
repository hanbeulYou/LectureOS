# PATCH-0010

- Title: Analysis Finding Application Foundation (042 Milestone 2)
- Status: Completed
- Priority: Medium
- Trigger: Architect / Product Owner Decision (042 Milestone 2 architecture-first investigation)
- Created: 2026-07-23
- Target Blueprint: `docs/042_LECTURE_INTELLIGENCE_PIPELINE.md`

---

## Summary

An architecture-first investigation of the second dependency-ordered 042 milestone — **Analysis Finding
Application Foundation** — found that `042 §8` fixes what an Analysis Finding must *mean* but that its
durable-record contract was undefined: the canonical reference unit was a `§18` Requires-Validation item
(deferred by `030 §168` to the pipeline doc); the finding-type taxonomy is `§18` Deferred; the confidence
calculation is `§18` Deferred; and, because analysis is AI-driven and a provider's classification is never
canonical (`§8`, `§2.10`), the analysis-provider boundary was unspecified. The Product Owner approved the
minimal decision resolving exactly the contracts the first Finding milestone needs.

This PATCH records that decision by promoting the first Analysis milestone into a **Confirmed** normative
contract (new `§8.1`). It defines **no** implementation, SQL, repository, execution, or provider API, and
resolves nothing belonging to later milestones. `042` remains the single source of truth.

## Problem Statement

**F-01 — The Analysis Finding's durable-record contract was undefined.** `§8` fixed the Finding's required
meanings (finding type; optional Source region; evidence; confidence/uncertainty; analysis provenance;
optional segment relationship), but the **canonical reference unit / anchor**, **finding-type
representation**, **confidence/evidence field shape**, **analysis-provider boundary**, and **durability**
were `§18` Requires-Validation / Deferred (and `030 §168` deferred the minimal unit to the pipeline doc).
Absent a decision, engineering would invent durable product meaning.

**F-02 — Analysis is AI-driven; the provider boundary needed to be fixed.** A provider result is never
canonical (`§8`, `§2.10`); the first milestone had to be scoped as an Application Foundation with a
provider-independent boundary, mirroring the transcript "Application Foundation → Concrete Provider"
precedent, rather than coupling the record to an AI provider.

## Architect / Product Owner Decision (Confirmed)

For **042 Milestone 2 — Analysis Finding Application Foundation** (recorded as `042 §8.1`):

- **Analysis Finding:** a durable canonical domain record — **immutable**, **identity-owning**,
  **provenance-bearing**, **insert-only**. Revision and supersession remain deferred.
- **Canonical anchor:** every Finding is anchored to **exactly one `EligibleAnalysisInput`** (§5.1); a
  Source Timeline Time Range is **optional** (at most one); Lecture Segment is not part of this milestone;
  multi-range references remain deferred. One `EligibleAnalysisInput` may anchor many distinct Findings.
- **Finding Type:** every Finding carries a required, **provider-independent, stable, Application-owned**
  canonical Finding Type (never a provider classification). No taxonomy or category values are defined.
- **Evidence:** every Finding carries **recorded** supporting evidence with provenance (a human-reviewable
  rationale plus provenance to the `EligibleAnalysisInput` and any Source Timeline range). Structured
  evidence models and textual-representation constraints remain deferred.
- **Confidence:** a Finding **may** carry recorded confidence or uncertainty; its calculation, calibration,
  prioritization, and interpretation remain deferred.
- **Application Foundation:** this milestone establishes canonical Finding records and a
  **provider-independent Application boundary** that admits a **normalized, provider-independent analysis
  result**. It does **not** invoke AI, implement a provider, define prompts or models, or create Lecture
  Segments, Edit Candidates, or Review Items; raw provider output, provider-specific classifications, and
  provider internal reasoning never enter the canonical domain. The concrete AI provider is deferred to a
  separate later milestone.
- **Admission boundary:** a Finding may be admitted only from **exactly one ELIGIBLE
  `EligibleAnalysisInput`**, a **running unit execution**, and complete upstream provenance; all upstream
  objects are consumed **read-only**.

## Scope

- Records the approved Analysis Finding Application Foundation contract as normative `042 §8.1` and a
  confirming note in `§18`.
- Adds a minimal cross-reference in `030_DATA_MODEL.md §168` (the Finding minimum reference unit, previously
  deferred there, is now resolved by `042 §8.1`) and a minimal consistency reference in
  `020_PRODUCT_REQUIREMENTS.md §4.2` pointing to `042` for the analysis layer.

## Out of Scope (Deferred to later 042 / other milestones)

Taxonomy; confidence calculation; uncertainty calibration; prioritization; revision; supersession; Lecture
Segmentation; Segment relationships; multi-range / overlapping-range Findings; Edit Candidates; Review;
concrete AI providers, prompt design, model selection; Source-Media-only analysis; optional Subtitle/
Speaker/Project Context admission (`§18`). Also out of scope: any implementation, SQL, schema, migration,
repository, execution code, provider API, or Goal.

## Compatibility Notes

- **No canonical concept added; no released meaning changed.** `§8.1` confirms an already-anchored record
  contract for the Finding described by `§8`; it does not re-define `§8`.
- **No change** to `040`, `041`, `043`, `044`, or to the completed v1..v23 records/meanings. The Finding
  admits the v23 `EligibleAnalysisInput` read-only.
- **Additive only:** the subsequent implementation milestone is expected to add strictly additive
  persistence (a new schema version) for the Analysis Finding record, preserving every released v1–v23
  meaning.
- `042` remains the single source of truth; `030`/`020` carry cross-references only.

## Acceptance Criteria

- [x] The first Analysis milestone (Analysis Finding Application Foundation) is promoted to a confirmed
  normative contract (`§8.1`).
- [x] Analysis Finding is a durable, immutable, identity-owning, provenance-bearing, insert-only canonical
  record; revision/supersession deferred.
- [x] Every Finding is anchored to exactly one `EligibleAnalysisInput`; optional single Source Timeline
  range; no Segment; multi-range deferred.
- [x] Required provider-independent, stable, Application-owned Finding Type (no taxonomy defined).
- [x] Recorded evidence with provenance; optional recorded confidence/uncertainty (calculation deferred).
- [x] Application Foundation boundary confirmed (normalized provider-independent result admitted; no AI /
  provider / prompt / model / Segment / Candidate / Review Item).
- [x] Admission = one ELIGIBLE `EligibleAnalysisInput` + running execution + complete provenance, read-only.
- [x] Existing deferrals preserved (`§8.1`, `§18`); `030 §168` / `020 §4.2` cross-references added.
- [x] No implementation, schema, repository, provider, or Goal is introduced.

## Result

- Status: **Completed**
- Changed Blueprint Files: `docs/042_LECTURE_INTELLIGENCE_PIPELINE.md` (new §8.1; §18 confirming note;
  header amended). Cross-references: `docs/030_DATA_MODEL.md §168`, `docs/020_PRODUCT_REQUIREMENTS.md §4.2`.
- Notes: Records the Product Owner's approved decision for 042 Milestone 2. Product policy/clarification
  only; no schema, code, or Goal. The next step is implementation of the Analysis Finding Application
  Foundation milestone; all later 042 concerns remain deferred.

## Related Documents

- `PATCH-0007-physical-materialization.md`
- `PATCH-0008-delivery-deferral.md`
- `PATCH-0009-lecture-analysis-input-eligibility.md`
- `../docs/042_LECTURE_INTELLIGENCE_PIPELINE.md`
- `../docs/030_DATA_MODEL.md`
- `../docs/020_PRODUCT_REQUIREMENTS.md`
