# PATCH-0008

- Title: Delivery Deferral (v1)
- Status: Completed
- Priority: Medium
- Trigger: Architect / Product Owner Decision (Delivery architecture-first investigation)
- Created: 2026-07-23
- Target Blueprint: `docs/044_EXPORT_PIPELINE.md` (with cross-references in `docs/031_ARCHITECTURE.md §4.10` and `implementation/020_STORAGE_MODEL.md §11.2`)

---

## Summary

An architecture-first investigation of the Delivery boundary (downstream of Physical Materialization) found no authoritative product contract for a LectureOS-owned Delivery capability: the Blueprint defers Delivery (`044 §15.4`, §16), assigns actual transport to the external consumer (`044 §12.5`; `031 §99`), and — at the product level — places content distribution out of v1 scope (`001`, `002`), leaving long-term delivery-tool ownership an open question (`003`). The Product Owner selected **Option D: Delivery is deferred for v1.**

This PATCH records that decision and closes the Delivery question for v1 with a minimal, non-duplicative clarification. It defines **no** Delivery contract, domain, record, identity, lifecycle, transport, URL, or presentation-filename policy, and requires **no** implementation, schema, or migration.

## Problem Statement

**F-01 — Delivery had no product contract and would otherwise be invented in code.**
There is no authoritative definition of what Delivery is for v1, its admission, identity, durability, transport, URL, presentation-filename, missing-file interaction, or security. Absent a decision, an implementer could silently introduce durable product meaning (a Delivery domain/record/transport). The Blueprint needed an explicit closure.

**F-02 — A conceptual placeholder (Export Coordinator) risked implying ownership.**
`031 §4.10` describes an Export Coordinator that "coordinates the external delivery boundary and exposes delivery results." Without clarification this could be read as implying a durable LectureOS Delivery domain, which it does not.

## Architect / Product Owner Decision

**Delivery is deferred for LectureOS v1.** Physical Materialization (`044 §17`) is the **final LectureOS-owned stage** of the current Export Pipeline. A MATERIALIZED Materialization Record and its physical file are the final internal export result. Any "Delivery" after that refers only to **external-consumer use** or a **future, separately approved capability** — not part of the canonical Export Pipeline contract.

For v1, LectureOS does **not** own: transport, download, upload, transfer, URL / signed-URL generation, content distribution, recipient management, presentation-filename policy, delivery identity, delivery persistence, or delivery lifecycle. Presentation filenames remain non-canonical and deferred; URLs are not canonical and not defined; no delivery status may be added to Artifact or Materialization records; missing-file reconciliation and rematerialization remain exclusively Physical Materialization responsibilities. Delivery must not be silently introduced as an implementation detail.

Any future LectureOS-owned Delivery capability requires a new architecture-first investigation, explicit Product Owner approval, a separate Blueprint PATCH, and a newly bounded implementation milestone.

## Scope

- Records the Delivery deferral decision for v1.
- Adds `docs/044_EXPORT_PIPELINE.md §18 "Delivery — Deferred for v1"` and scopes the §17.16 Delivery bullet accordingly.
- Cross-references the decision from `031 §4.10 Export Coordinator` and `020_STORAGE_MODEL.md §11.2 Artifact Availability`.

## Out of Scope

- Any Delivery contract, domain concept, record, identity, lifecycle, transport, URL, presentation-filename, authorization, or provider.
- Any implementation, schema, migration, or Goal.
- Broadening product scope; changing Physical Materialization (§17), 041, v20, v21, or v22 semantics.

## Compatibility Notes

- **041 Subtitle Pipeline, Approved Subtitle Assembly (v20), SRT Artifact Generation (v21), SRT Physical Materialization (v22) — unchanged.**
- **No canonical concept added; no released meaning changed.** Artifact and Materialization identity, provenance, and file-generation semantics are untouched.
- Clarification-only: it removes a potential ambiguity (Export Coordinator ownership) and records a deferral. `SQLITE_SCHEMA_VERSION` remains 22.

## Acceptance Criteria

- [x] Physical Materialization is stated as the final LectureOS-owned Export Pipeline stage for v1.
- [x] "Delivery" after Physical Materialization is scoped to external-consumer use or a future separately approved capability.
- [x] The Export Coordinator's external boundary is clarified to **not** own transport/download/upload/transfer/URL/content-distribution/recipient/presentation-filename/delivery-identity/persistence/lifecycle in v1.
- [x] External consumers may use canonical Artifact and Materialization outputs read-only without becoming LectureOS canonical authority.
- [x] Missing-file reconciliation and rematerialization remain Physical Materialization responsibilities.
- [x] Future LectureOS-owned Delivery requires a new investigation, Product Owner approval, a separate PATCH, and a bounded milestone.
- [x] No Delivery record/state/schema/provider is implied; no implementation is required.

## Result

- Status: **Completed**
- Changed Blueprint Files: `docs/044_EXPORT_PIPELINE.md` (new §18; §17.16 Delivery bullet scoped; header amended). Cross-references: `docs/031_ARCHITECTURE.md §4.10`, `implementation/020_STORAGE_MODEL.md §11.2`.
- Notes: Records the Product Owner's Option D decision — Delivery deferred for v1 — and closes the Delivery question. Product policy/clarification only; no schema, code, or Goal. The next engineering milestone should be selected from another already-authorized product capability rather than inventing Delivery.

## Related Documents

- `PATCH-0007-physical-materialization.md`
- `../docs/044_EXPORT_PIPELINE.md`
- `../docs/031_ARCHITECTURE.md`
- `../implementation/020_STORAGE_MODEL.md`
- `../docs/001_PRODUCT.md`
- `../docs/003_VISION.md`
