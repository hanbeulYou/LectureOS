# LectureOS Codex Goal — SRT Physical Materialization

> **Inheritance notice.** Governed by `AGENTS.md` (auto-loaded via `CLAUDE.md`).
> Do **not** restate durable operating policy here. The autonomous slice loop,
> Stop Conditions, additive-migration compatibility, Blueprint Drift Check, review
> policy, validation checklist, Goal Self-Maintenance mechanics, and the base
> Consolidated Completion Report skeleton are **inherited** from
> `AGENTS.md → "Milestone Execution Protocol"`. This Goal specifies only what is
> unique to this milestone.
>
> Authored from `docs/goals/_TEMPLATE.md`. Implements the approved Blueprint
> contract **`docs/044_EXPORT_PIPELINE.md` §17** (`patches/PATCH-0007`). This is
> **implementation only** — no Blueprint change, no product policy, no Architect
> decision. Every decision below conforms to §17.

## 1. Mission & Lifecycle Position

Implement **SRT Physical Materialization**, the third stage of the 044 Export Pipeline, exactly as fixed
by Blueprint §17. From exactly one canonical `SubtitleSrtArtifact` (v21) and one Materialization Request,
it durably realizes the artifact's inline SRT payload as a **physical file** under an approved Storage
Root, recording the act's canonical lifecycle. Lifecycle:
`… → SRT Artifact Generation → SubtitleSrtArtifact → **SRT Physical Materialization** (this milestone) →
Materialization Record + Physical File → Delivery`.

It follows the **record-first, crash-consistent, reconcilable** model (§17.12): establish the act as
**PENDING** durably → write the file atomically → record the terminal **MATERIALIZED | FAILED** state. It
admits only the artifact, never regenerates the payload, and keeps Artifact identity permanently
independent of any physical file. **Delivery remains out of scope.** 041, v20, and v21 remain immutable.

## 2. Baseline

Start `HEAD 36bc0ac`, branch `main`, `SQLITE_SCHEMA_VERSION 21`. Authority order inherited from `AGENTS.md`;
product meaning from `044 §17` / `PATCH-0007`.

## 3. Bounded Assessment & Implementation-Level Architect Decisions

All decisions below are **implementation choices §17 explicitly leaves open** (record structure, storage
kind, relative-location scheme) — not new product policy.

**Admission (§17.5).** Admit exactly one canonical `SubtitleSrtArtifact` (read via the v21 repository, incl.
its inline payload) and one Materialization Request. Read-only over the artifact; never regenerate SRT;
never re-evaluate eligibility.

**Record model — two insert-only records (§17.3 leaves this open).** Model the act as two **immutable,
insert-only** records, consistent with the durable subtitle pipeline's append-only discipline and the
durability model's "insert-only canonical record" class:
- a **Materialization** record (the committed intent), carrying the Materialization Identity, source
  artifact, storage kind, declared relative Storage Location, and provenance — persisted **first** (the
  durable PENDING commit);
- a **Materialization Outcome** record (terminal), carrying `MATERIALIZED` (realized byte length) or
  `FAILED` (reason) — persisted **after** the file write.
**Materialization State is derived** (§17.4): a Materialization with **no Outcome** is `PENDING`; with an
Outcome it is that Outcome's terminal state. No row is ever mutated; a dangling PENDING is precisely the
reconcilable state (§17.12/§17.15).

**Storage authority & provider boundary (§17.6, §17.13).** The **Composition Root supplies one approved
Storage Root**; the Application owns policy/lifecycle; **Infrastructure** owns byte-writing behind an
Application port. Storage kind for this milestone is **local file** (extensible identifier; no cloud/object
storage). The legacy hardened writer's safety mechanics (tempfile → fsync → atomic move/link,
symlink/traversal rejection) are **reused/adapted**, not weakened.

**Storage Location policy (§17.7–17.8).** The Application owns a **deterministic** relative-location policy
beneath the approved root (filename ends `.srt`). The location is **operational provenance, never
identity**; it is not required to be derived from identity, and using identity as a convenient
deterministic basis is permitted so long as the path is never treated as identity.

**Identity (§17.7, §17.11).** `SubtitleSrtMaterializationId` is caller-supplied and **distinct** from
`ArtifactId`; never derived from path/filename/bytes. One artifact may have many Materialization records;
**rematerialization = a new record with a new identity**, prior records preserved. No wall-clock/locale/
randomness; deterministic replay of the records.

**Consistency, collision, recovery (§17.9–17.12, §17.14–17.15).** Record-first orchestration; collision
table enforced exactly (identical bytes → idempotent MATERIALIZED; different bytes / foreign file →
FAILED, never overwrite); reconciliation of a dangling PENDING by comparing the declared location's bytes
to the artifact payload; orphan-tempfile cleanup within the approved root; exact byte preservation;
approved-root containment. **No cross-resource atomicity is claimed.**

**Architect Checklist: all No — additive; 041/v20/v21 unchanged; conforms to §17.**

## 4. Scope

- **Included:**
  - additive SQLite **v22** persistence: two insert-only tables (`subtitle_srt_materializations`,
    `subtitle_srt_materialization_outcomes`, FK outcome → materialization) + co-persisted
    `DomainResultReference` (kind `subtitle_srt_materialization`, upstream = the artifact's DomainResult)
  - records: `SubtitleSrtMaterialization`, `SubtitleSrtMaterializationOutcome`, `SubtitleMaterializationState`
    (PENDING/MATERIALIZED/FAILED), `SubtitleMaterializationStorageKind` (LOCAL_FILE), identity plan, result
    kind
  - an Application filesystem port + an Infrastructure **local-file writer** (approved-root containment,
    deterministic relative location, atomic replacement, symlink/traversal rejection, exact byte
    preservation, orphan-tempfile cleanup) reusing the hardened writer's mechanics
  - a **record-first** Materialization service: persist PENDING → write file → persist terminal outcome;
    collision handling; idempotency; and a **reconciliation/recovery** operation for a dangling PENDING
  - composition wiring `(connection, execution_query, approved storage root)`
  - restart reconstruction; deterministic replay of records; migration compatibility (v1..v21 → v22)
  - end-to-end acceptance + recovery/replay tests writing real files under a temporary approved root
- **Excluded (later 044 / other authority):**
  - **Delivery** (download, upload, transfer, signed URLs, HTTP, content-disposition, presentation
    filenames, UI)
  - cloud/object storage; multiple storage providers; deletion/retention/GC workflows
  - any change to 041 / v20 / v21 records or meanings, `SubtitleSrtArtifact`, or Artifact identity
  - any materialization/delivery **status field on the Artifact record** (§17: Artifact carries no such
    state)
  - additional export formats; AI; network

## 5. Canonical Model (implementation, conforming to §17)

- **Identity:** `SubtitleSrtMaterializationId` (`application/identities.py`), distinct from `ArtifactId`.
- **Enums:** `SubtitleMaterializationState` = `PENDING | MATERIALIZED | FAILED` (PENDING derived);
  `SubtitleMaterializationStorageKind` = `LOCAL_FILE`.
- **`SubtitleSrtMaterialization` (intent, immutable):** `identity`; `domain_result_id`; `source_artifact_id`
  (`ArtifactId`); `storage_kind`; `relative_location` (operational, non-identity); `source_media_id`;
  `source_timeline_id`; `run_id`; `unit_execution_id`; `sequence`; `reason`; `previous_materialization_id`
  (optional). Invariants: non-blank relative location and reason; non-negative sequence; first has no
  previous; location is not identity.
- **`SubtitleSrtMaterializationOutcome` (terminal, immutable):** `materialization_id`; `state`
  (`MATERIALIZED | FAILED`); `byte_length` (present iff MATERIALIZED, equals the realized UTF-8 byte
  length); `failure_reason` (present iff FAILED). Invariants: state⇔byte_length/failure_reason presence;
  exactly one outcome per materialization.
- **Identity plan:** `SubtitleSrtMaterializationIdentityPlan(materialization_id, materialization_result_id)`.
- **Prepared / ports:** `PreparedSubtitleSrtMaterialization` (the intent + its DomainResult); an Application
  filesystem-writer port; an atomic persistence port (intent + outcome).

## 6. Persistence

Additive SQLite **v22**: `subtitle_srt_materializations` (intent, with storage_kind CHECK, sequence/previous
CHECK) and `subtitle_srt_materialization_outcomes` (state CHECK IN materialized/failed,
state⇔byte_length/failure_reason CHECK, PK/FK to the materialization). The intent is co-persisted with its
`DomainResultReference` in one `BEGIN IMMEDIATE` transaction (record-first commit); the outcome is persisted
in a **separate** `BEGIN IMMEDIATE` transaction after the file write. Identity-absence + linkage checks and
complete rollback per transaction. `_migrate_v21_to_v22` additive; downgrades and direct skips rejected;
every released version v1..v21 chains to v22 preserving existing data and meaning. **No path/URL/absolute-
path/materialization-status column on any existing table.**

## 7. Slice Sequence

### Slice 1 — Goal Baseline and Assessment
Review: Optional — Skipped. Commit: `docs: add srt physical materialization goal`

### Slice 2 — Materialization Records
Identities, enums, `SubtitleSrtMaterialization`, `SubtitleSrtMaterializationOutcome`, identity plan,
`Prepared…`, result kind, exports, focused record tests (state⇔fields, location-not-identity, append-only
lineage). Review: Required — Executed. Commit: `feat: add srt materialization records`

### Slice 3 — Storage Location Policy and Infrastructure Local-File Writer
Application filesystem port; Infrastructure local-file writer (approved-root containment, deterministic
relative location, atomic tempfile→fsync→move/link, symlink/traversal rejection, exact byte preservation,
different-bytes/foreign-file rejection, orphan-tempfile cleanup) reusing hardened mechanics; focused
writer/security tests (no DB). Review: Required — Executed (filesystem/security boundary). Commit:
`feat: add approved-root local file writer`

### Slice 4 — Atomic SQLite Persistence (v22) and Migration Compatibility
Additive schema v22 (two insert-only tables), repository (get intent + get outcome), atomic intent
persistence (+ DomainResult), atomic outcome persistence, migration chain, superseded-test maintenance.
Review: Required — Executed (schema/migration/transaction). Commit:
`feat: persist srt materialization records atomically`

### Slice 5 — Record-First Materialization Service, Reconciliation, and Composition
`SubtitleSrtMaterializationService.record_materialization(...)` (persist PENDING → write file → persist
terminal outcome) with collision handling and idempotency; `reconcile_materialization(...)` for a dangling
PENDING; composition `(connection, execution_query, approved storage root)`. Review: Required — Executed
(idempotency/recovery/consistency/lifecycle). Commit: `feat: materialize srt artifacts record-first`

### Slice 6 — End-to-End Acceptance, Recovery and Replay
Durable artifact → materialize → real file with **exact bytes** under a temporary approved root; restart
reconstruction of both records; simulated crash (intent without outcome) → reconcile → MATERIALIZED;
different-bytes/foreign-file → FAILED with no overwrite; containment/traversal/symlink rejection;
rematerialization → new record/new identity; idempotent repeat; deterministic replay; **no Delivery
behavior, no URL, no materialization status on the Artifact**. Review: Optional — Skipped (harness/test
only). Commit: `test: verify srt physical materialization acceptance`

## 8. Milestone-Specific Verify

Materialization admits only one `SubtitleSrtArtifact` and never regenerates the payload or re-evaluates
eligibility; the act is established **PENDING before any file write** and only then written and finalized
(record-first); the realized file's bytes **exactly equal** the artifact payload's UTF-8 bytes;
identical-bytes is idempotent MATERIALIZED, different-bytes/foreign-file is FAILED with **no overwrite**;
every realization is **contained beneath the approved root** (traversal/symlink escapes rejected); the
Storage Location is operational provenance, **never identity**, and path changes never change any identity;
a dangling PENDING **reconciles deterministically** (match → MATERIALIZED, differ/unwritable → FAILED) and
orphan tempfiles are cleaned; rematerialization is a **new record with a new identity**, prior records
preserved; a missing file loses only availability — the Materialization and Artifact records and all
provenance remain canonical; **no existing canonical artifact is modified** (the `SubtitleSrtArtifact` and
its DomainResult are byte-identical before/after) and the Artifact carries **no** materialization/delivery
status; records reconstruct after restart and replay deterministically; duplicate-identity / DomainResult
collisions roll back; and **no Delivery, URL, upload, or download behavior is produced**. (Generic
validation inherited.)

## 9. Status (living)

### Completed Capabilities
```text
None yet
```
### Remaining Milestones
```text
Slice 1 — Goal Baseline and Assessment
Slice 2 — Materialization Records
Slice 3 — Storage Location Policy and Infrastructure Local-File Writer
Slice 4 — Atomic SQLite Persistence (v22) and Migration Compatibility
Slice 5 — Record-First Materialization Service, Reconciliation, and Composition
Slice 6 — End-to-End Acceptance, Recovery and Replay
```
### Immediate Next Slice
```text
Slice 1 — Goal Baseline and Assessment
```

## 10. Completion Report — Milestone Additions

Beyond the inherited skeleton, add: Materialization Record Model (two insert-only records; derived state);
Storage Authority & Provider Boundary; Storage Location & Filename Policy; Record-First Consistency Model &
Failure Orderings; Collision Handling; Missing-File & Rematerialization Guarantees; Reconciliation/Recovery;
Security (containment/traversal/symlink/atomic replacement/byte preservation); Persistence Model (v22, two
transactions bracketing the file write); Restart, Replay and Recovery Acceptance; Migration Compatibility;
§17 Conformance Confirmation; Next Recommended Milestone (Delivery).

## 11. Milestone Overrides (optional)

None — inherited critical-only review policy and default execution behavior. (Per the Durability Goal review
categories, the filesystem-boundary, schema/migration, consistency, idempotency, recovery, and security
surfaces make Slices 3–5 **Required — Executed** reviews.)

---

### Deliberately deferred capabilities (recorded for the completion report)
**Delivery** (download, upload, transfer, signed URLs, HTTP, content-disposition, presentation filenames,
UI) and **cloud/object storage** (the `020 §16.4` External Object Storage Boundary), plus deletion/
retention/GC workflows and additional export formats. This milestone realizes one canonical SRT artifact as
a local physical file and records the act; making that file available to external consumers is the next,
separately-gated 044 milestone.
