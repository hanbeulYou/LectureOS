# PATCH-0009

- Title: Lecture Analysis Input Eligibility (042 Milestone 1)
- Status: Completed
- Priority: Medium
- Trigger: Architect / Product Owner Decision (042 Milestone 1 architecture-first investigation)
- Created: 2026-07-23
- Target Blueprint: `docs/042_LECTURE_INTELLIGENCE_PIPELINE.md`

---

## Summary

An architecture-first investigation of the first dependency-ordered milestone of the 042 Lecture
Intelligence Pipeline found that the earliest stage — **Lecture Analysis Input Eligibility (Intake)** — is
buildable once two narrow product decisions are fixed: the intake's **admission authority** and whether
**Eligible Analysis Input** is a durable canonical record. `042 §5` already settles the eligible-input set
and guarantees; `§3`/`§4`/`§20` settle concept meanings and the downstream handoff. The Product Owner
approved the minimal decision.

This PATCH records that decision by promoting `§5` + the `§18 Working Assumption` into a **Confirmed**
first-milestone contract (new `§5.1`). It defines **no** implementation, schema, repository, provider API,
or execution logic, and resolves nothing belonging to later milestones.

## Problem Statement

**F-01 — The first 042 milestone's admission authority was undefined.**
`042 §18 Requires-Validation` left open "which analysis views require which inputs," which encompasses what
the first intake must admit. Absent a decision, engineering would invent a durable product contract
(admission authority, required readiness).

**F-02 — The durability of Eligible Analysis Input was unconfirmed.**
`§3.1` defines the concept but `§18 Deferred` left storage open; whether the intake is a durable canonical
record or transient state was unsettled.

## Architect / Product Owner Decision (Confirmed)

For **042 Milestone 1 — Lecture Analysis Input Eligibility (Intake)**:

- **Admission authority:** the milestone admits the **validated Corrected Transcript selected by the
  Transcript Pipeline** together with its **Source Timeline** and **Source Media reference**, in the usable
  (ready/current-selected) state that does not bypass `040` validation (`§5`). All upstream is consumed
  **read-only**; no upstream record is modified.
- **Eligible Analysis Input:** a **durable canonical record** — **immutable**, **identity-owning**, and
  **provenance-bearing** (to the admitted Corrected Transcript, Source Timeline, and Source Media), per
  `§2.7` and `§12`. It is not transient implementation state.
- **Milestone responsibility (sole):** establish a validated, durable analysis input. The milestone
  performs **no Analysis**, and creates **no** Analysis Finding, Lecture Segment, Segment Label, Edit
  Candidate, or Review Item, and performs **no AI reasoning**; it only surfaces input Failure/missing/
  Uncertainty scope for later analysis (`§5`).

## Scope

- Records the approved first-milestone contract as normative `042 §5.1` and a confirming note in `§18`.

## Out of Scope (Deferred to later 042 milestones)

The following remain **deferred** and are **not** resolved by this PATCH: the canonical analysis unit; the
Analysis Finding minimal reference unit; segmentation hierarchy and overlapping segmentation; multi-range
(multi-segment / multi-time-range) Edit Candidate references; Review Item generation conditions;
Source-Media-only analysis; and optional Subtitle/Speaker/Project Context admission (`§18`).

Also out of scope: any implementation, schema, migration, repository, provider API, execution logic, or
Goal.

## Compatibility Notes

- **No canonical concept added; no released meaning changed.** `§5.1` confirms an admission/record contract
  already anchored by `§5` and the `§18 Working Assumption`.
- **No change** to `020`, `030`, `031`, `040`, `041`, `043`, or `044` meanings. The intake consumes the
  `040` validated Corrected Transcript read-only and does not re-define `041` Subtitle provenance.
- **Additive only:** the subsequent implementation milestone is expected to add strictly additive
  persistence (a new schema version) for the Eligible Analysis Input record, preserving every released
  v1–v22 meaning.

## Acceptance Criteria

- [x] The first 042 milestone (Lecture Analysis Input Eligibility) is promoted to an approved product
  contract (`§5.1`).
- [x] Admission authority = validated selected Corrected Transcript + Source Timeline + Source Media,
  read-only, non-bypassing of `040` validation.
- [x] Eligible Analysis Input is stated as a durable, immutable, identity-owning, provenance-bearing
  canonical record.
- [x] The milestone is stated to perform no analysis and to create no Finding/Segment/Candidate/Review
  Item and no AI reasoning.
- [x] Later-milestone items remain explicitly deferred (`§5.1`, `§18`).
- [x] No implementation, schema, repository, provider, or Goal is introduced.

## Result

- Status: **Completed**
- Changed Blueprint Files: `docs/042_LECTURE_INTELLIGENCE_PIPELINE.md` (new §5.1 first-milestone contract;
  §18 confirming note; header amended).
- Notes: Records the Product Owner's approved decision for 042 Milestone 1. Product policy/clarification
  only; no schema, code, or Goal. This unlocks a single additive implementation milestone (a durable
  Eligible Analysis Input intake reading the validated Corrected Transcript + Source Timeline) with no
  further product decisions for that milestone; all later 042 milestones remain product-gated.

## Related Documents

- `PATCH-0007-physical-materialization.md`
- `PATCH-0008-delivery-deferral.md`
- `../docs/042_LECTURE_INTELLIGENCE_PIPELINE.md`
- `../docs/040_TRANSCRIPT_PIPELINE.md`
- `../docs/043_REVIEW_PIPELINE.md`
- `../docs/020_PRODUCT_REQUIREMENTS.md`
