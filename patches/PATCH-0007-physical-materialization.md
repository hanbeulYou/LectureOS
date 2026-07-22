# PATCH-0007

- Title: Physical Materialization
- Status: Completed
- Priority: High
- Trigger: Blueprint Review (Physical Materialization architecture-first investigation)
- Created: 2026-07-22
- Target Blueprint: `docs/044_EXPORT_PIPELINE.md` (resolves items deferred by `implementation/020_STORAGE_MODEL.md` §11.1, §15.2, §16.4, §19.3, §19.5)

---

## Summary

The 044 Export Pipeline is durable through **SRT Artifact Generation**: an eligible `SubtitleApprovedDocument` yields a canonical, regenerable `SubtitleSrtArtifact` whose deterministic SRT payload is stored inline. The next stage — **Physical Materialization** — was blocked not by engineering but by **missing product policy**: the authoritative storage contract deliberately deferred the storage authority, path/filename policy, collision/overwrite rules, materialization identity, missing-file recovery, and the database↔filesystem consistency model.

PATCH-0007 makes those policies **normative Blueprint contracts** so that Physical Materialization can be implemented without inventing product meaning. It introduces the canonical concept of a **Materialization Record** (the durable record of one act of realizing an Artifact as a physical file), an approved **Storage Authority**, and a **record-first, crash-consistent, reconcilable consistency model** expressed as a **PENDING → MATERIALIZED | FAILED** lifecycle. It defines product policy only — no schema, no API, no implementation, and no record-structure. Artifact identity remains permanently independent of any physical representation.

## Problem Statement

**F-01 — The Artifact is durable; its physical realization has no contract.**
`SubtitleSrtArtifact` (durable, inline payload, stable `ArtifactId`) is complete. But `020_STORAGE_MODEL.md` §11.1 kept the physical file explicitly separate from the record and left as *Requires Validation* whether a rematerialized file keeps the same identity; §16.3–16.4 preserved the record/file split but "특정 filesystem 또는 object storage를 선택하지 않는다"; §19.3 left missing-file persistence and rematerialization identity open; §19.5 deferred "물리 storage model과 schema" and "transaction과 consistency 구현."

**F-02 — There was no approved storage authority or path/filename policy.**
`044 §16` listed "Artifact 저장과 전달 방식" as a Non-Goal; `030 §24` and `031 §1` define no directory/location. The only physical-write component (`LocalArtifactMaterializationService` / `_AtomicLocalFileWriter`) takes a **caller-supplied** directory and filename and records results **only in memory** — it is a legacy demo component, not an approved contract.

**F-03 — Cross-resource atomicity between SQLite and the filesystem is impossible, and no consistency model was approved.**
`020 §15.2` gives consistency *constraints* but explicitly "구체적인 transaction, atomicity와 recovery 구현은 정의하지 않는다." Implementation must not silently pick file-first vs record-first, must not claim atomicity it cannot guarantee, and must not overwrite on recovery (§15.2). This is the primary decision this PATCH resolves.

**F-04 — Implementation cannot invent storage policy.**
Storage authority, path/filename policy, collision behavior, missing-file recovery, and the consistency model are all product decisions with lasting durability and security consequences. Choosing them in code — without a Blueprint contract — would create unapproved, hard-to-reverse product meaning. They must be decided here.

## Architectural Rationale

Three layers with three distinct authorities, each independently valid:

```text
SubtitleSrtArtifact        (canonical: stable ArtifactId, inline payload, provenance — the source of truth)
        │
        ▼
Materialization Record     (canonical: one act of realizing that artifact — its lifecycle state and where)
        │
        ▼
Physical File              (derived external state: may be lost, moved, or unavailable — never identity)
```

- The **Artifact** owns *what the approved SRT is*. Its identity and payload never depend on whether, where, or how many times it is written to disk. A file that is lost, moved, or renamed changes nothing about the Artifact (`020 §11.1`, §6.1).
- The **Materialization Record** owns *the fact that a realization was attempted and its outcome*. It has its **own** identity, distinct from the Artifact's, because one Artifact may be realized many times (different runs, different locations, after loss) and each realization is a separate historical fact.
- The **Physical File** is a derived, potentially-transient consequence. Its existence is an *availability* property, never a truth about approval or provenance (`020 §11.2`, §15.2). Because a database transaction and a filesystem write cannot be made a single atomic operation, the contract is deliberately **crash-consistent and reconcilable**, not atomic: the canonical record is authoritative and the file is reconciled to it.

This separation is why Artifact identity is independent from any physical representation, and why "the file exists" is never equated with "the export is canonically complete," nor "the file is gone" with "the Artifact is lost."

## New Canonical Concepts

Defined by meaning only (no schema, no fields, no record-structure):

- **Materialization Request** — the admitted instruction to realize exactly one `SubtitleSrtArtifact` as a physical file at a Storage Location, carrying a Materialization Identity. Admission only; it never regenerates or alters the Artifact.
- **Materialization Identity** — the canonical identity of one materialization act, **distinct** from Artifact Identity. Never derived from a path, filename, byte content, or digest. Caller-supplied and deterministic, consistent with the pipeline's identity discipline.
- **Materialization Record** — the durable canonical record of one materialization act: its lifecycle state, its outcome, and its provenance to the Artifact. It persists independently of the physical file's existence. Whether it is realized as a single evolving record or as several is an implementation concern outside this contract.
- **Storage Authority** — the approved authority that bounds *where* realizations may occur: a single approved **Storage Root** supplied by the Composition Root as operational configuration. It is not a Domain fact and is never stored as canonical identity.
- **Storage Location** — the Application-owned **relative** location (beneath the approved Storage Root, including the filename) of a realization, determined by Application policy. Recorded as *operational provenance* describing where a file was placed; it is **not** identity.
- **Materialization Provenance** — the traceable chain Materialization Record → `SubtitleSrtArtifact` → `SubtitleApprovedDocument` → … → Source Timeline, plus the producing execution context.
- **Materialization State** — the canonical lifecycle of a materialization act: **PENDING** (admitted and being realized, not yet confirmed), **MATERIALIZED** (realization confirmed durable), or **FAILED** (realization could not be completed). Reconciliation resolves a PENDING act deterministically on recovery.
- **Materialization Failure** — the explicit canonical outcome (the **FAILED** state) when a realization cannot be completed (byte-collision, write failure, containment violation). Never hidden as success; never mutates the Artifact or its provenance.
- **Materialized File** — the derived external physical object. May be absent or unavailable; never defines identity.

## Lifecycle

```text
SubtitleSrtArtifact           (044 Artifact Generation — COMPLETE, unchanged)
        │
        ▼
Physical Materialization      (this PATCH: admit one artifact → PENDING → write → MATERIALIZED | FAILED)
        │
        ▼
Materialization Record        (canonical: PENDING → MATERIALIZED | FAILED)
        │
        ▼
Physical File                 (derived; availability, not identity)
        │
        ▼
Delivery                      (later, separate contract — out of scope)
```

Ownership: Artifact Generation owns serialization and the Artifact; **Physical Materialization owns admission, storage-location policy, filename policy, collision policy, materialization state, provenance, and recovery**; Delivery owns download/upload/transfer. No stage re-enters an upstream authority.

## Product Decisions

### 1. Admission Authority
Physical Materialization admits **exactly one canonical `SubtitleSrtArtifact`** and **exactly one Materialization Request** referencing it. Nothing else is admissible — not the Approved Document, not the payload out of band. The payload is **read from the durable Artifact Record**; materialization never regenerates SRT and never re-evaluates eligibility (eligibility was settled at Artifact Generation). An artifact that does not exist, or a request that does not reference a canonical artifact, is rejected without side effect.

### 2. Storage Authority
The **Composition Root supplies a single approved Storage Root** as operational configuration; the **Application owns materialization policy and lifecycle**. Callers may **not** choose arbitrary locations, may **not** supply absolute paths, and the current working directory is **never** used implicitly. **Relative locations beneath the approved root may be stored** as operational provenance. **Absolute paths are never canonical** — the absolute root is a deployment concern that must not appear in the canonical record as identity or as a portable fact. Changing the root or moving a file never changes any identity (`020 §11.1`, §16.4).

### 3. Materialization Identity
**Artifact Identity ≠ Materialization Identity.** A materialization act carries its own caller-supplied Materialization Identity, never derived from a path, filename, byte content, or digest. One Artifact may be realized **many** times — different runs, different locations, or after a file is lost — and each realization is a **distinct Materialization Record with its own identity**, with prior records **preserved as history**. Repeated realizations may reference a previous materialization. The Blueprint fixes these identity semantics; **whether the durable record is realized as one evolving record or several is left to implementation.** **Replay reconstructs the materialization records and their lifecycle states deterministically**; the physical file is reconciled to them (§9), never replayed as canonical truth.

### 4. Relative Path Policy
A **Storage Location is an Application-owned relative location** beneath the approved Storage Root, **determined by Application policy** and **deterministic** for a given policy. It is stored as **operational provenance** on the Materialization Record. It is emphatically **not identity**: a path is never parsed into identity, and a path change never changes any identity (`020 §11.1`). **Path-as-identity is forbidden.** The Blueprint does **not** require the location to be derived from Artifact or Materialization identity; implementations remain free to organize storage hierarchies as their policy dictates, provided every location is deterministic, contained beneath the approved root, and never treated as identity.

### 5. Filename Policy
**Filename generation is owned by materialization policy (Application), is deterministic according to Application policy, and is not user-controlled.** The **canonical format extension** for this contract is `.srt`, owned by the SRT format contract, not by the filesystem. A filename is part of the (operational, non-identity) Storage Location and is never identity. **Presentation filenames** (human-facing, download-friendly names) are a separate, non-canonical **Delivery** concern and are out of scope here.

### 6. Collision Policy
Unambiguous rules for a realization at a declared Storage Location:

| Situation | Canonical behavior |
|---|---|
| No file present | Write; record **MATERIALIZED**. |
| File present, **identical bytes** to the Artifact payload | **Idempotent success**; record **MATERIALIZED** without rewriting. |
| File present, **different bytes** | **Materialization Failure**; **never overwrite** (`020 §15.2`). |
| A terminal Materialization Record already exists for the **same request identity** | Not re-executed; the existing record is returned. |
| A **duplicate Materialization Request** (same Materialization Identity) | Identity collision — idempotent; no second act is created. |
| A file belonging to a **different artifact / foreign file** at the location | Treated as foreign; **never overwritten**. |

No realization silently replaces content that does not byte-match the admitted Artifact.

### 7. Missing-File Semantics
If the Artifact exists, a Materialization Record exists, and the file later disappears: **the Artifact Record and the Materialization Record remain canonical and valid.** Only the file **availability** is lost — this is an availability fact, not a deletion of any record and not a loss of provenance (`020 §15.2`, §11.2). Nothing about the Artifact becomes invalid. **Rematerialization is permitted** (§8). A missing file never triggers deletion of, or mutation to, the Artifact or its Decision/provenance history.

### 8. Rematerialization
Because the Artifact payload is fixed and deterministic, rematerialization is **byte-repeatable** — the same Artifact always yields the same file bytes. Each materialization act is a **new Materialization Record with a new Materialization Identity**, optionally referencing the prior materialization; the earlier record is **preserved as history**. A rematerialization does **not** reuse or overwrite a prior record's identity. The idempotent case — same Artifact + same Materialization Identity + same location — is a repeatable no-op that returns the existing record. This resolves `020 §11.1`/§19.3: a rematerialized realization is a **new record**, and the Artifact keeps its identity.

### 9. Database ↔ Filesystem Consistency (primary decision)
Cross-resource atomicity across SQLite and the filesystem **cannot be achieved**; this contract therefore defines a **crash-consistent, reconcilable model**, not an atomic one.

**Alternatives considered:**
- **(a) File-first, then record.** A crash between the write and the record leaves an **orphan file with no canonical record** (`020 §15.1` "External object availability mismatch") — untracked, unreconcilable, and a silent-overwrite risk. **Rejected.**
- **(b) Single atomic DB+FS operation.** Physically impossible without a distributed transaction manager, which is out of scope and unavailable. **Rejected.**
- **(c) Record-first.** The canonical materialization is established in the database in a **PENDING** state before the file is written; the file is then reconciled to the canonical record. **Chosen.**

**Chosen model (record-first, lifecycle-based):**
1. The materialization act is established durably in a **PENDING** state (this Artifact, this Materialization Identity, this declared Storage Location) **before** any file is written.
2. The file is written to the declared location using an **atomic replacement discipline** (write to a temporary file within the approved root, flush and fsync, then atomically move/link into place).
3. The act's **terminal lifecycle state** is durably recorded — **MATERIALIZED** (with the realized byte length) or **FAILED** (with an explicit reason).

The Blueprint fixes the **lifecycle and its semantics**; whether that lifecycle is realized as one evolving record or several distinct records is an implementation concern outside this contract.

**Failure semantics (deterministic), expressed via states:**
- **PENDING established, FS write fails** → an atomic-replacement discipline means **no partial file becomes visible** (the temporary file is discarded); the act resolves to **FAILED** or remains a reconcilable **PENDING** act. The Artifact is untouched.
- **FS write succeeds, terminal state not yet durable** → a **PENDING** act plus the deterministic location permit **reconciliation on recovery**: if the file's bytes **match** the Artifact payload, complete to **MATERIALIZED** (idempotent — identical bytes); if they **differ**, resolve to **FAILED** and **do not overwrite**.
- **Crash mid-write** → the temporary file is an **orphan within the approved root's temporary area** and is cleaned deterministically on recovery; the **PENDING** act drives reconciliation; **no false success** is ever recorded.
- **Orphan file (file present, no materialization act)** → impossible for tracked realizations, because the **PENDING** act is established **before** any write; any file at a declared location lacking a PENDING or terminal act is **foreign** and never overwritten.
- **Missing act** → nothing to reconcile; the Artifact remains materializable via a new act.
- **Missing file (act MATERIALIZED, file gone)** → availability lost; rematerialize as a new act (§7, §8).

The model is **deterministic** in every canonical dimension: the payload bytes are fixed by the Artifact, the Storage Location is deterministic according to Application policy, and the lifecycle (PENDING → MATERIALIZED | FAILED) is deterministic. The only non-deterministic element — whether the physical file currently exists — is modeled explicitly as **availability** and reconciled, never treated as canonical truth. **No cross-resource atomicity is claimed.**

### 10. Provider Boundary
- **Application** owns materialization **policy and lifecycle**: admission, Storage-Location policy, filename policy, collision policy, materialization state, provenance, and recovery.
- **Infrastructure** owns the **byte-writing mechanics**: temporary files, fsync, atomic move/link, and path-safety enforcement — behind an Application-defined boundary.
- **Storage Authority (the approved Storage Root)** is Composition-Root operational configuration.
- **No provider or infrastructure component owns** Artifact identity, Materialization identity, lifecycle authority, filename policy, or eligibility.
- **No cloud or object storage** is introduced; `020 §16.4`'s External Object Storage Boundary remains reserved for a separate future contract.

### 11. Security
The contract requires and preserves: **approved-root containment** (every realization must resolve to a location beneath the approved Storage Root; escapes are rejected), **path-traversal prevention**, **symlink-escape prevention**, **safe temporary files** created within the approved root, **no accidental overwrite** (different bytes → failure, never overwrite), **exact byte preservation** (the realized file's bytes equal the Artifact payload's UTF-8 bytes), **atomic replacement** (temporary file → atomic move), **no executable interpretation** of the payload, and **no locale-dependent path behavior**. The existing hardened writer's guarantees are to be **reused and must not be weakened**.

### 12. Recovery
On restart, all materialization acts and their lifecycle states are reconstructed. A **PENDING** act is **reconciled deterministically**: verify the declared location's bytes against the Artifact payload — complete as **MATERIALIZED** if identical, resolve to **FAILED** if different or unwritable. **Orphan temporary files** within the approved root are cleaned. **Retry** after failure records a **new** materialization act. **Deterministic replay** reconstructs the materialization records and states; the physical file is a reconciled side effect, never replayed as canonical truth. Recovery never overwrites a differing file and never deletes the Artifact or its provenance.

## Export Boundary

- **Artifact Generation ends** at the durable `SubtitleSrtArtifact` (payload + record). Physical Materialization does not serialize, reformat, re-number, or re-time; it consumes the payload verbatim.
- **Physical Materialization** begins by admitting one Artifact and ends at a Materialization Record plus (on success) a realized file at a Storage Location.
- **Delivery begins after** Physical Materialization: download, upload, transfer, signed URLs, HTTP, content-disposition, presentation filenames, and UI are all **out of scope** for this contract.

## Acceptance Criteria

- [x] Physical Materialization admits exactly one canonical `SubtitleSrtArtifact` (+ one Materialization Request) and never regenerates the payload or re-evaluates eligibility.
- [x] Storage Authority is defined: an approved Storage Root supplied by the Composition Root; callers cannot choose arbitrary or absolute locations; the CWD is never used; absolute paths are never canonical.
- [x] Materialization Identity is defined as distinct from Artifact Identity, caller-supplied, never derived from path/filename/bytes; one Artifact may have many Materialization Records, with prior records preserved as history.
- [x] Storage Location is defined as an Application-owned relative location that is deterministic according to Application policy (operational provenance, never identity, not required to be derived from identity); path-as-identity is forbidden.
- [x] Filename policy is defined: Application-owned, deterministic according to policy, not user-controlled, `.srt` extension owned by the format contract; presentation filenames are a separate Delivery concern.
- [x] Collision policy is defined unambiguously for no-file / identical-bytes / different-bytes / existing-record / duplicate-request / foreign-file, with no silent overwrite.
- [x] Missing-file semantics are defined: Artifact and Materialization Records remain canonical; only availability is lost; rematerialization is permitted; nothing is invalidated or deleted.
- [x] Rematerialization is defined: byte-repeatable; a new Materialization Record with a new identity; idempotent no-op for the same identity + location.
- [x] The materialization **lifecycle (PENDING → MATERIALIZED | FAILED)** — its states, semantics, observable behavior, and recovery expectations — is defined **without prescribing record structure or persistence strategy**.
- [x] A **single** DB↔FS consistency model (record-first, crash-consistent and reconcilable, expressed as the PENDING → MATERIALIZED | FAILED lifecycle) is chosen, with alternatives discussed and failure semantics defined for every ordering (DB-ok/FS-fail, FS-ok/DB-fail, crash, partial write, orphan file, missing record, missing file, recovery, replay); no atomicity is claimed.
- [x] Provider boundary is defined: Application owns policy/lifecycle; Infrastructure owns byte-writing; Storage Root is operational config; no component owns identity/lifecycle/filename/eligibility; no cloud/object storage.
- [x] Security requirements are defined and the existing hardened writer's guarantees are preserved, not weakened.
- [x] Recovery is defined: restart reconstruction, deterministic reconciliation of PENDING acts, orphan-tempfile cleanup, retry as a new act, deterministic record/state replay.
- [x] The Export Boundary places Artifact Generation before and Delivery after Physical Materialization.
- [x] Every policy above is stated so it can be made testable by the implementation milestone.

## Compatibility Notes

- **041 Subtitle Pipeline — unchanged.**
- **Approved Subtitle Assembly (v20) — unchanged.**
- **SRT Artifact Generation (v21) / `SubtitleSrtArtifact` — unchanged.** The Artifact remains the source of truth; its identity and payload gain no dependency on any physical file.
- **Only 044 expands** — Physical Materialization is added downstream of Artifact Generation and upstream of Delivery. No prior lifecycle meaning changes.
- This PATCH **resolves** the deferred items in `020_STORAGE_MODEL.md` §11.1 (rematerialization identity → new record), §15.2 (a chosen consistency model), §16.4 (a local approved Storage Root; object storage still reserved), §19.3 (missing-file → record persists; rematerialization → new identity), and §19.5 ("물리 storage model과 schema", "transaction과 consistency 구현" → policy now fixed; concrete schema and persistence realization follow in the implementation milestone).
- **Additive only:** the subsequent implementation milestone is expected to add strictly additive persistence for materialization records, preserving every released v1–v21 meaning, with no downgrade and no direct-skip migration.
- **Blueprint change surface (applied):** `docs/044_EXPORT_PIPELINE.md` §17 (normative additions); §16 Non-Goal scoped from storage to Delivery; header version 0.2 / Amended By. Non-normative cross-reference notes added to `implementation/020_STORAGE_MODEL.md` §11.1, §15.2, §16.4, §19.3, §19.5.

## Completion Checklist

- [x] Physical Materialization product contract authorized by Architect
- [x] Two required Architect refinements applied (lifecycle-only states; Storage Location not identity-derived)
- [x] Contract integrated into `docs/044_EXPORT_PIPELINE.md`
- [x] Resolved Storage Model deferrals converted to cross-references
- [x] Patch documentation recorded

## Result

- Status: **Completed**
- Changed Blueprint Files: `docs/044_EXPORT_PIPELINE.md` (new §17 Physical Materialization; §16 Non-Goal scoped to Delivery; header amended). Cross-reference updates: `implementation/020_STORAGE_MODEL.md` §11.1, §15.2, §16.4, §19.3, §19.5.
- Notes: Establishes the canonical Physical Materialization contract — Materialization Record, Storage Authority, and a record-first, crash-consistent, reconcilable DB↔filesystem model expressed as a PENDING → MATERIALIZED | FAILED lifecycle — that unblocks implementation while keeping the completed 041/v20/v21 pipeline immutable and Artifact identity permanently independent of any physical file. Product policy only; no schema, API, record structure, or implementation is defined here. Concrete schema (prospective v22) and persistence realization belong to the implementation milestone.

## Related Documents

- `PATCH-0003-text-pipeline.md`
- `../docs/030_DATA_MODEL.md`
- `../docs/031_ARCHITECTURE.md`
- `../docs/044_EXPORT_PIPELINE.md`
- `../implementation/020_STORAGE_MODEL.md`
