# LectureOS Codex Goal — SRT Artifact Generation

> **Inheritance notice.** Governed by `AGENTS.md` (auto-loaded via `CLAUDE.md`).
> Do **not** restate durable operating policy here. The autonomous slice loop,
> Stop Conditions, additive-migration compatibility, Blueprint Drift Check, review
> policy, validation checklist, Goal Self-Maintenance mechanics, and the base
> Consolidated Completion Report skeleton are **inherited** from
> `AGENTS.md → "Milestone Execution Protocol"`. This Goal specifies only what is
> unique to this milestone.
>
> Authored from `docs/goals/_TEMPLATE.md`. Second stage of the 044 Export Pipeline,
> downstream of Approved Subtitle Assembly (PATCH-0006).

## 1. Mission & Lifecycle Position

Implement **SRT Artifact Generation**, the second stage of the **044 Export Pipeline**. From exactly one
canonical `SubtitleApprovedDocument` (v20), it deterministically serializes the eligible approved units
into a canonical **SRT payload** and creates a canonical, regenerable **Artifact Record** with complete
provenance. Lifecycle:
`… → Approved Subtitle Assembly → SubtitleApprovedDocument → **SRT Artifact Generation** (this milestone)
→ Physical Materialization → Delivery`.

Artifact Generation owns serialization and artifact metadata only. It **writes no file**, touches no
filesystem/path/URL/storage/delivery, performs no Review/Validation/assembly/AI/provider work, and is a
pure deterministic Application behavior. **041 and v20 remain immutable.**

## 2. Baseline

Start `HEAD 12aff1a`, branch `main`, `SQLITE_SCHEMA_VERSION 20`. Authority order inherited from `AGENTS.md`;
Export product meaning from `docs/044_EXPORT_PIPELINE.md` and PATCH-0006.

## 3. Bounded Assessment & Architect Decisions

**Admission boundary.** Admits **exactly one** `SubtitleApprovedDocument`, read via the v20 repository
(document + its ordered `SubtitleApprovedUnit`s). All approved meaning, ordering, timing, omission and
modified text are already resolved by Approved Subtitle Assembly and are consumed **as-is** — the stage
does not read or reinterpret the time/reading/final/decision/review/validation records, does not re-run
assembly, re-evaluate eligibility, reapply decisions, restore omitted units, modify text, reorder units,
change timing, or repair content.

**Assessment of existing components.** The repository already contains a deterministic SRT formatter
(`export/service.py`: `_milliseconds` via `Decimal`/`ROUND_HALF_UP`, `_format_timestamp` → `HH:MM:SS,mmm`,
block assembly `f"{i}\\n{start} --> {end}\\n{text}"` joined by `"\\n\\n"` + trailing `"\\n"`), bound to the
**legacy in-memory** subtitle domain. The only common Artifact primitive is the opaque `ArtifactId`
(`execution/identities.py`); there is **no durable Artifact record/table**. Decision: **extract** the
deterministic SRT primitives into a pure, aggregate-free module reused by this stage (and delegated to by
the legacy formatter so the algorithm is single-sourced, not duplicated); **reuse `ArtifactId`** as the
canonical artifact identity; introduce the **smallest** durable Artifact Record.

**Architect Decision — eligibility & empty document.** Only `SubtitleExportEligibility.ELIGIBLE` documents
generate an artifact; `INELIGIBLE` input raises a deterministic `SubtitleArtifactGenerationError` and
produces **no** record/payload (never a partial artifact). An **eligible zero-unit document is permitted by
the current v20 contract** (every unit rejected → omitted, document eligible), so its canonical
representation is the **empty SRT payload** (`""`, `byte_length 0`, `cue_count 0`), defined and tested. A
unit whose duration collapses at millisecond precision (`end_ms ≤ start_ms`) is an explicit representation
failure (`SubtitleArtifactGenerationError`), consistent with 044 §11.4 — never silently emitted.

**Architect Decision — canonical Artifact Record (durable, payload-owning, provider-free).** One additive
table `subtitle_srt_artifacts` storing the Artifact Record **with its SRT payload inline** (durably
recoverable after restart), plus its `DomainResultReference` (kind `subtitle_srt_artifact`, upstream = the
approved document's DomainResult). Canonical identity is `ArtifactId` — **never** a filename/extension/path/
URL/storage key/download token, and the record carries **no** materialization or delivery status. Additive
schema **v21**. No wall-clock/locale/randomness; append-only `sequence`/`previous_artifact_id`; identical
canonical input + identity plan → byte-identical payload and record. **Architect Checklist: all No —
additive; 041 and v20 unchanged.**

## 4. Scope

- **Included:**
  - pure deterministic SRT serialization primitives (extracted; `Decimal`/`ROUND_HALF_UP`, `HH:MM:SS,mmm`,
    contiguous 1-based numbering, `"\\n\\n"` block separator, trailing `"\\n"`, empty document → `""`)
  - `SubtitleSrtArtifact` record + `SubtitleArtifactFormat` (SRT) + identity plan + `Prepared…`
  - deterministic generation service admitting one `SubtitleApprovedDocument`, rejecting `INELIGIBLE`
  - canonical Artifact Record: identity (`ArtifactId`), DomainResult, source document, format, inline
    payload, byte length, cue count, encoding (`utf-8`), execution provenance, source media/timeline,
    append-only `sequence`/`previous_artifact_id`
  - atomic SQLite **v21** persistence (record + inline payload + DomainResult); restart reconstruction;
    deterministic replay; idempotency; migration compatibility (v1..v20 → v21)
  - end-to-end acceptance from a durable Approved Subtitle Document
- **Excluded (later 044 milestones / other authority):**
  - physical files, filesystem, temp files, atomic rename, directory/filename/path policy, path traversal,
    object storage, URLs/signed URLs, download/upload, delivery, playback, rendering, muxing, burn-in, UI
  - WebVTT/TXT/JSON/FCPXML, multiple-format negotiation, format plugins, batch export
  - content digest/MIME (not required by any existing Artifact contract)
  - any change to v1..v20 records/meanings, the common `review/` domain, or (beyond a pure-primitive
    delegation) the legacy in-memory subtitle/export domains
  - AI inference; any provider, network, or storage abstraction

## 5. Canonical Model

- **Identity:** reuse `ArtifactId` (`execution/identities.py`). Result kind
  `SUBTITLE_SRT_ARTIFACT_RESULT_KIND = "subtitle_srt_artifact"`.
- **Enum `SubtitleArtifactFormat`:** `SRT = "srt"` (canonical format identifier; not a filename/extension).
- **Aggregate `SubtitleSrtArtifact`:** `identity` (`ArtifactId`); `domain_result_id`;
  `source_approved_document_id`; `format`; `payload` (SRT text; may be empty for an empty document);
  `byte_length`; `cue_count`; `encoding`; `source_media_id`; `source_timeline_id`; `run_id`;
  `unit_execution_id`; `sequence`; `reason`; `previous_artifact_id`. Invariants: `format is SRT`;
  `encoding == "utf-8"`; `byte_length == len(payload.encode("utf-8"))`; `cue_count >= 0`; non-blank reason;
  non-negative sequence; first has no previous; `cue_count == 0 ⇒ payload == ""` and `payload == "" ⇒
  cue_count == 0`.
- **Identity plan:** `SubtitleSrtArtifactIdentityPlan(artifact_id, artifact_result_id)`.

## 6. Persistence

Additive SQLite **v21**: one table `subtitle_srt_artifacts` (identity, DomainResult, source document,
format CHECK IN ('srt'), inline `payload TEXT NOT NULL`, `byte_length`/`cue_count` CHECK ≥ 0, encoding
CHECK = 'utf-8', media/timeline, run/unit, sequence/previous CHECK). Co-persist a `DomainResultReference`
(kind `subtitle_srt_artifact`, upstream = (approved document DomainResult,), media/timeline from the
document) in one `BEGIN IMMEDIATE` transaction with identity-absence + linkage checks and complete
rollback. `_migrate_v20_to_v21` additive; downgrades and direct skips rejected; every released version
v1..v20 chains to v21 preserving existing data and meaning. No path/URL/storage/materialization/delivery
columns.

## 7. Slice Sequence

### Slice 1 — Goal Baseline and Assessment
Review: Optional — Skipped. Commit: `docs: add srt artifact generation goal`

### Slice 2 — Durable Artifact and SRT Payload Records
`ArtifactId` reuse, `SubtitleArtifactFormat`, `SubtitleSrtArtifact`, identity plan, `Prepared…`, result
kind, exports, focused record tests. Review: Required — Executed. Commit:
`feat: add srt artifact records`

### Slice 3 — Deterministic SRT Artifact Generation Service
Extract pure SRT primitives (delegate legacy formatter to them); `SubtitleSrtArtifactGenerationService`
admits one document, rejects INELIGIBLE, serializes eligible units, builds `PreparedSubtitleSrtArtifact`
(no write). Review: Required — Executed. Commit: `feat: generate srt artifact from approved document`

### Slice 4 — Atomic SQLite Persistence, Restart, Replay and Migration Compatibility
Additive schema v21, repository, atomic command, composition, `record_generation`, restart/replay, v1..v20
→ v21 compatibility, idempotency. Review: Required — Executed. Commit:
`feat: persist srt artifact atomically`

### Slice 5 — End-to-End Acceptance
Durable Approved Subtitle Document → generate SRT Artifact → verify exact payload, provenance, no upstream
mutation, restart reconstruction, deterministic replay, no physical-file/materialization/delivery table.
Review: Optional — Skipped (harness/test only). Commit: `test: verify srt artifact generation acceptance`

## 8. Milestone-Specific Verify

The SRT payload is produced only from one eligible `SubtitleApprovedDocument`'s ordered units; INELIGIBLE
input yields no record/payload (explicit failure); cue order == document unit order; numbering is
contiguous from 1; timestamps derive only from approved unit timing with the preserved
`Decimal`/`ROUND_HALF_UP` rounding and `HH:MM:SS,mmm` syntax; text is the approved lines verbatim (LF
separators, one blank line between blocks, UTF-8, defined trailing-newline; empty document → `""`); omitted
units stay absent; **no existing canonical artifact is modified**; the Artifact Record carries complete
provenance and DomainResult chaining (upstream = document DomainResult) and is durably reconstructable after
restart with a byte-identical payload; identical input + identity plan → byte-identical payload and record;
**no physical file, path, URL, materialization, or delivery is produced**; immutable append-only records;
duplicate-identity / DomainResult collisions roll back atomically. (Generic validation inherited.)

## 9. Status (living)

### Completed Capabilities
```text
Slice 1 — Goal Baseline and Assessment (commit docs: add srt artifact generation goal)
Slice 2 — Durable Artifact and SRT Payload Records (commit feat: add srt artifact records)
Slice 3 — Deterministic SRT Artifact Generation Service (commit feat: generate srt artifact from approved document)
Slice 4 — Atomic SQLite Persistence, Restart, Replay and Migration Compatibility (commit feat: persist srt artifact atomically)
Slice 5 — End-to-End Acceptance (co-committed with Slice 4; the atomic test consumes the acceptance fixture)
```
### Remaining Milestones
```text
None — milestone complete (SQLITE_SCHEMA_VERSION 21). Next Export milestone: Physical Materialization
(separately gated).
```
### Immediate Next Slice
```text
None — milestone complete.
```

## 10. Completion Report — Milestone Additions

Beyond the inherited skeleton, add: Artifact Contract; SRT Determinism Rules; Admission & Eligibility
Handling (incl. empty-document); Payload Ownership (inline, restart-recoverable); Provenance & DomainResult
Chaining; No-File / No-Materialization / No-Delivery Guarantee; Persistence Model; Restart and Replay
Acceptance; Migration Compatibility; Idempotency Verification; Formatter-Reuse Note; Next Recommended
Milestone.

## 11. Milestone Overrides (optional)

None — inherited critical-only review policy and default execution behavior.

---

### Deliberately deferred capabilities (recorded for the completion report)
**Physical Materialization** (writing bytes to a file/storage, paths/filenames, atomic rename, directory
policy, path-traversal, object storage) and **Delivery** (download/upload/transfer, URLs/signed URLs, UI).
The existing atomic local file writer remains a legacy implementation component for the Physical
Materialization milestone. Additional export formats (WebVTT/TXT/JSON/FCPXML), batch export, and content
digest/MIME remain deferred.
