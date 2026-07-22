# LectureOS Codex Goal — Approved Subtitle Assembly

> **Inheritance notice.** Governed by `AGENTS.md` (auto-loaded via `CLAUDE.md`).
> Do **not** restate durable operating policy here. The autonomous slice loop,
> Stop Conditions, additive-migration compatibility, Blueprint Drift Check, review
> policy, validation checklist, Goal Self-Maintenance mechanics, and the base
> Consolidated Completion Report skeleton are **inherited** from
> `AGENTS.md → "Milestone Execution Protocol"`. This Goal specifies only what is
> unique to this milestone.
>
> Authored from `docs/goals/_TEMPLATE.md`. Implements approved **PATCH-0006 —
> Approved Subtitle Assembly (Export Pipeline Input Contract)**.

## 1. Mission & Lifecycle Position

Implement **Approved Subtitle Assembly**, the first stage of the **044 Export Pipeline** and the
canonical contract established by approved PATCH-0006. From exactly one canonical subtitle document
(its `SubtitleTimeRevision`), it deterministically **reconstructs the complete, ordered, approved
subtitle representation** — the **Approved Subtitle Document** — by reconciling the base timed/reading
representation with the applicable finalized decisions (`SubtitleFinalSubtitle`), and it establishes
export eligibility. This is the canonical **Export Input**. Lifecycle:
`… → Subtitle Decision Application → Subtitle Final Subtitle → **Approved Subtitle Assembly** (this
milestone) → Artifact Generation → Physical Materialization → Delivery`.

This stage generates **no artifact**, writes **no file**, serializes **no format** (no SRT/WebVTT/bytes),
performs no Review, no Validation, no Human Decision, no AI, and uses no provider. **041 remains
immutable.**

## 2. Baseline

Start `HEAD cd8d0a3`, branch `main`, `SQLITE_SCHEMA_VERSION 19`. Authority order inherited from
`AGENTS.md`; product meaning from PATCH-0006 and `docs/044_EXPORT_PIPELINE.md`.

## 3. Bounded Assessment & Architect Decisions

**Admission boundary.** Assembly admits **one canonical subtitle document**, identified by its
`SubtitleTimeRevision` (the complete ordered timed-unit set) together with its `SubtitleReadingRevision`
(the approved display text). It collects the **applicable finalized decisions** for that document from
`SubtitleFinalSubtitle` (grouped by `source_time_revision_id`), reaching `SubtitleDecisionRevision`
through provenance. All upstream records are read **read-only** and never mutated. No Review, Validation,
Human Decision, AI, or provider is involved.

**Architect Decision — canonical reconciliation (approved, PATCH-0006 §4; ruling confirmed for this
milestone).** For each timed unit, the **current** finalization (highest `sequence` among finalizations
targeting that unit) is applied:

| Effective outcome | Result |
|---|---|
| Modify (FINAL) | unit included, text = approved `applied_text` |
| Accept (FINAL) | unit included, text = original reading text |
| Reject (NOT_FINAL) | unit **omitted**; document remains eligible |
| Untouched (no finalization) | unit included, text = original reading text |

A finalized Reject (NOT_FINAL) omits its unit and does **not** block the document. Assembly invents no
further reconciliation policy.

**Architect Decision — eligibility (document completeness).** The Approved Subtitle Document is
`ELIGIBLE` unless it cannot be completely reconstructed, in which case it is `INELIGIBLE` with a reason
and **carries no unit sequence** (never a silent partial document). Ineligibility causes (each read-only):
an included unit lacks resolved (`ANCHORED`) timing; an included unit's reading text is unresolvable; a
collected finalized decision's provenance does not resolve to this document (wrong time/reading revision
or a target unit outside the document). **Zero-finding documents are eligible directly** — with no
finalizations, every unit is Untouched (original text) in canonical order. Unknown admitted records
(time/reading revision absent) are admission errors, not ineligibility.

**Architect Decision — ordering.** Unit order comes solely from the canonical timed units
(`display_order`). Omitted units are removed without disturbing the relative order of the rest.

**Architect Decision — output & persistence.** The Approved Subtitle Document is a canonical, immutable,
deterministic, provider-free, document-level record (parent document + ordered approved units + approved
lines). It is **not** an SRT/WebVTT/file/bytes/artifact/download. Additive schema **v20**. No wall-clock;
append-only `sequence`/`previous_document_id`; identical canonical input + identity plan → byte-identical
document. **Architect Checklist result: all No — additive; 041 unchanged.**

## 4. Scope

- **Included:**
  - `SubtitleApprovedDocument` (parent) + `SubtitleApprovedUnit` (ordered children, each with approved
    `lines`) + `SubtitleExportEligibility` (ELIGIBLE/INELIGIBLE) + `SubtitleApprovedUnitOrigin`
    (ACCEPTED/MODIFIED/UNTOUCHED)
  - deterministic reconstruction from one time revision + one reading revision + collected finalized
    decisions (decision revision reached through provenance), read-only
  - canonical reconciliation (table above) and eligibility (document completeness)
  - canonical ordering from timed units; omitted (Rejected) units disappear
  - carried document lineage (candidate / transcript & revision / media & timeline) + DomainResult
    chaining (`upstream = time revision DomainResult`)
  - append-only `sequence`/`previous_document_id`
  - atomic SQLite **v20** persistence (three additive tables); restart reconstruction; deterministic
    replay; idempotency; migration compatibility (v1..v19 → v20)
  - a read-only `list_for_time_revision` query over the existing v19 final-subtitle table (no schema
    change to v19)
  - fake-review / fake-transcript acceptance chaining decisions → finals → assembly (eligible, modify,
    reject-omission, and a zero-finding document)
- **Excluded (later Export milestones / other authority):**
  - Artifact Generation; SRT/WebVTT serialization; export payloads/bytes; MIME/checksums/format identifiers
  - Physical Materialization; files; filesystem; paths/URIs; atomic file writes
  - Delivery; download; upload; transfer
  - any change to 041 records, the common `review/` domain, or the legacy in-memory subtitle/export domains
  - AI inference; any provider or capability port

## 5. Canonical Model

- **Identities:** `SubtitleApprovedDocumentId`, `SubtitleApprovedUnitId` (`OpaqueIdentity`,
  `application/identities.py`).
- **Enums:** `SubtitleExportEligibility` = `ELIGIBLE | INELIGIBLE`; `SubtitleApprovedUnitOrigin` =
  `ACCEPTED | MODIFIED | UNTOUCHED`.
- **`SubtitleApprovedUnit`:** `identity`; `document_id`; `source_timed_unit_id`;
  `source_reading_unit_id`; `origin`; `display_order`; `start`; `end`; `lines` (≥1, non-blank);
  `source_final_subtitle_id` (None iff `UNTOUCHED`). Invariants: resolved timing (`end ≥ start ≥ 0`);
  non-empty lines; origin⇔final-subtitle presence.
- **`SubtitleApprovedDocument`:** `identity`; `domain_result_id`; `source_time_revision_id`;
  `source_reading_revision_id`; `eligibility`; `ineligibility_reason` (None iff ELIGIBLE);
  `source_candidate_id`; `source_transcript_id`; `source_revision_id`; `source_media_id`;
  `source_timeline_id`; `approved_unit_ids` (ordered; `()` iff INELIGIBLE); `omitted_unit_count` (≥0);
  `run_id`; `unit_execution_id`; `sequence`; `reason`; `previous_document_id`. Invariants:
  ELIGIBLE⇔reason None; INELIGIBLE⇒reason set **and** `approved_unit_ids == ()`; non-blank reason;
  non-negative sequence/omitted count; first has no previous.
- **Identity plan:** `SubtitleApprovedAssemblyIdentityPlan(document_id, document_result_id, unit_ids)`
  where `unit_ids` positionally matches the admitted time revision's `timed_unit_ids`; each **included**
  unit takes its positional id.

## 6. Persistence

Additive SQLite **v20**: three tables — `subtitle_approved_documents` (parent, with eligibility⇔reason and
sequence/previous CHECKs), `subtitle_approved_units` (ordered children, origin⇔final CHECK, resolved-timing
CHECK, `UNIQUE(document, ordinal)`, FK ON DELETE CASCADE), `subtitle_approved_unit_lines`
(`PRIMARY KEY(unit, ordinal)`, FK ON DELETE CASCADE). Co-persist a `DomainResultReference` (kind
`subtitle_approved_document`, `upstream = (time revision DomainResult,)`, media/timeline from the time
revision) in one `BEGIN IMMEDIATE` transaction with identity-absence + linkage checks and complete
rollback. `_migrate_v19_to_v20` additive; downgrades and direct skips rejected; every released version
v1..v19 chains to v20 preserving existing data and meaning.

## 7. Slice Sequence

### Slice 1 — Goal Baseline and Assessment
Review: Optional — Skipped. Commit: `docs: add approved subtitle assembly goal`

### Slice 2 — Approved Subtitle Assembly Records
Identities, enums, `SubtitleApprovedUnit`, `SubtitleApprovedDocument`, identity plan, `Prepared…`,
`SUBTITLE_APPROVED_DOCUMENT_RESULT_KIND`, exports, focused record tests. Review: Required — Executed.
Commit: `feat: add approved subtitle assembly records`

### Slice 3 — Deterministic Assembly Service
`SubtitleApprovedSubtitleAssemblyService.assemble(...)` admits one document, collects finalized decisions,
reconciles per the table, resolves eligibility, and builds `PreparedSubtitleApprovedDocument` (no write).
Review: Required — Executed. Commit: `feat: assemble approved subtitle document from finals`

### Slice 4 — Atomic SQLite Persistence, Restart, Replay and Migration Compatibility
Additive schema v20 (three tables), repository, atomic command, `list_for_time_revision` query,
composition, `record_assembly`, restart/replay, v1..v19 → v20 compatibility, idempotency. Review:
Required — Executed. Commit: `feat: persist approved subtitle document atomically`

### Slice 5 — End-to-End Acceptance
Chain decisions → finals → assembly: eligible document (accept + modify), reject-omission, and a
zero-finding document; persist → reopen → identical reconstruction → identical replay → no upstream
mutation → no downstream artifact/export table. Review: Optional — Skipped (harness/test only). Commit:
`test: verify approved subtitle assembly acceptance`

## 8. Milestone-Specific Verify

The Approved Subtitle Document is produced only from one time revision + one reading revision + collected
finalized decisions (read-only); reconciliation matches the canonical table (Modify→applied_text,
Accept→original, Reject→omitted, Untouched→original); ordering is exactly the timed-unit `display_order`
with omissions removed; eligibility is ELIGIBLE unless completeness fails, and INELIGIBLE documents carry
no units; zero-finding documents assemble directly; full document lineage and DomainResult chaining
(`upstream = time revision DomainResult`) preserved; **no existing canonical artifact is modified** — time
revision, reading revision, final subtitles, decision revisions byte-identical before/after; **no artifact,
file, byte payload, or export format is produced**; immutable records; append-only sequence/previous;
duplicate-identity / DomainResult collisions roll back atomically; identical canonical input + identity
plan → byte-identical document; replay after restart → byte-equivalent. (Generic validation inherited.)

## 9. Status (living)

### Completed Capabilities
```text
Slice 1 — Goal Baseline and Assessment (commit docs: add approved subtitle assembly goal)
Slice 2 — Approved Subtitle Assembly Records (commit feat: add approved subtitle assembly records)
Slice 3 — Deterministic Assembly Service (commit feat: assemble approved subtitle document from finals)
Slice 4 — Atomic SQLite Persistence, Restart, Replay and Migration Compatibility (commit feat: persist approved subtitle document atomically)
Slice 5 — End-to-End Acceptance (co-committed with Slice 4; the atomic test consumes the acceptance fixture)
```
### Remaining Milestones
```text
None — milestone complete (SQLITE_SCHEMA_VERSION 20). Approved Subtitle Assembly is the canonical
Export Input. Next Export milestone: Artifact Generation (separately gated).
```
### Immediate Next Slice
```text
None — milestone complete.
```

## 10. Completion Report — Milestone Additions

Beyond the inherited skeleton, add: Canonical Assembly Model; Admission Boundary (one subtitle document);
Reconciliation & Eligibility Outcomes; Ordering Guarantee; No-Mutation & No-Artifact Guarantee; Provenance
& DomainResult Chaining; Persistence Model (three additive tables); Restart and Replay Acceptance;
Migration Compatibility; Idempotency Verification; Export-Boundary Deferral Note (Artifact Generation /
Materialization / Delivery); Next Recommended Milestone.

## 11. Milestone Overrides (optional)

None — inherited critical-only review policy and default execution behavior.

---

### Deliberately deferred capabilities (recorded for the completion report)
**Artifact Generation** (SRT/WebVTT serialization, export payloads, MIME/checksums/format identifiers),
**Physical Materialization** (files, filesystem, paths/URIs, atomic writes), and **Delivery** (download,
upload, transfer). The existing deterministic SRT formatter and atomic file writer remain legacy
implementation components to be adapted by those later, separately-gated milestones.
