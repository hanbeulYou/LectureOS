# Edit Export Assembly — Effective-Transcript Generation

- Status: Implementation Reference
- Blueprint: `docs/044` §23 + `PATCH-0035` (EA-1…EA-11, Confirmed) — the effective-transcript
  generation's Edit Export **admission boundary** over the GOAL-028/029 Review records (GOAL-030);
  `§19`–`§22`'s legacy contracts and `043 §7.5` R-1…R-12 / `§7.6` AH-1…AH-12 are inherited unchanged
- Schema: v53 (two additive tables `lecture_edit_export_assemblies`,
  `lecture_edit_export_assembly_members`)

## Purpose

`043 §7.6` AH-10 stated that being the current judgment is **not** Export eligibility and left the
actual condition to a separate decision. `044 §23` made that decision; this milestone implements it.

```text
observe_scope(source_timeline)
    → every §9.3 Edit Candidate on that timeline, via the released anchor chain
    → per candidate: observe_candidate_authority (043 §7.6) → anchor_status (§7.5 R-3)
    → CandidateExportStanding: eligible | why not
    → ExportScopeObservation — derived, stores nothing, never stops

admit_assembly(source_timeline)
    → the observation
    → STOP if undecided (cross-actor conflict, or no eligible member)
    → members = every eligible approved edit, ordered by identity
    → one immutable assembly + its membership, in ONE transaction, or none
```

**Nothing is approved, executed, serialized, or selected here.** Review remains the only place Human
Authority is exercised (EA-6); no Artifact, serializer, export file, output timeline, package,
download, URL, provider, NLE, Export Profile, or Export Configuration exists; and no Final Selection
concept exists in this pipeline at all (EA-11).

## Members are `ApprovedEditDecision` records directly (EA-2)

`044 §19`'s `ApprovedEditExportRepresentation` atom stage is **not reproduced**. Its D-2 minimum — an
owned Domain Result identity, execution provenance, and a per-admission ordinal — is precisely what
`043 §7.5` R-6 declared unsatisfiable in this generation (the §9.3 Candidate produces no Domain
Result, so there is nothing to own or reference) and R-9 declared meaningless (the ordinal is
structurally single-valued). Reproducing it would require fabricating the execution records and
synthetic Domain Results that `040 §18` H-10 and `041 §15` E6 prohibit. Its D-3 purpose is already
discharged: R-8 confirms the `ApprovedEditDecision` **already owns** the complete approved snapshot.

`§20` A-1's cardinality and direction are unchanged — one Assembly, one Source Timeline, upstream
consumed read-only. Only the generation of the record in the member position changes, exactly as
`§7.5` R-2 changed only the Candidate's generation.

## Export eligibility (EA-4) — three conditions, in the order that makes each reason reachable

| Observation | `ExportEligibility` | Contributes a member |
| --- | --- | --- |
| no authority history for the candidate | `no_recorded_authority` | no |
| two or more actors hold history | `cross_actor_conflict` | no |
| current operative judgment is a `reject` | `current_judgment_approves_nothing` | no |
| chain standing is not `current` | `superseded_by_authority_change` / `current_authority_ineligible` | no |
| otherwise | `eligible` | **yes** |

The released three-value **standing** vocabulary (`§7.5` R-3) is read and never extended; two rows
above carry a standing value as a *reason*, which reports what caused ineligibility and adds no
fourth standing. `reject` owns no approval, so `§19` D-7's rule holds without being restated as a
filter. No authority or standing resolver is reimplemented: `observe_candidate_authority` and
`anchor_status` are the released ones.

Ineligibility is never corruption. A superseded judgment's approval, and an approval whose chain
lost current standing, both remain valid immutable history (`§7.5` R-5) — tests assert they are
still readable after they stop contributing.

## Membership is total and derived, never chosen (EA-3, EA-7)

One Assembly denotes **every** export-eligible approved edit of its Source Timeline. There is no API
to ask for fewer: no subset, filter, ranking, selection record, or selection flag exists anywhere,
and no mutable current, stale, or selection column exists on either relation. The scope query walks
`Candidate → Finding → Admission → parent Raw Transcript → Source Timeline` — `§7.5` R-7's anchor
chain read in reverse, which is why no record in this generation carries a Source Timeline column —
and **stops there**: eligibility is computed in the Application, never in SQL.

## Identity binds the anchor *and* the membership (EA-10)

`lecture-edit-export-assembly:<sha256(contract kind/version, source timeline, ordered member ids)>`,
Application-owned. No provider identifier, execution identifier, `DomainResult`, UUID, timestamp,
wall clock, rowid, path, or mutable currentness participates.

Binding the membership is **required, not incidental**. Membership is derived and total, so an
upstream authority change legitimately makes a *new* Assembly gather a different set. Had the
identity bound only the timeline, that second Assembly would collide with the first and could never
be recorded. With membership bound: an identical re-admission converges (`reused`, nothing written),
and a genuinely different scope becomes a new immutable record. Successive Assemblies are a
difference between records, never a mutation of one — no recorded Assembly is ever rewritten, and
this contract defines **no currentness among them**.

**Reachability: Option B.** Every persisted canonical field participates, so a divergent stored
payload for an existing identity is structurally unreachable short of a hash collision. The
semantic-equality check is kept anyway, as `§7.5` R-10 requires under (B); reaching it in a test
needs an injected query stub.

Member order is by approved-decision identity — a pure function of the member set, so it adds no
information to the identity. It is **presentation only**: never an execution, timeline, or overlap
order (`§22` C-3 idiom), as `044 §23`'s Deferred section requires it to be recorded.

## The two undecided policies stop admission without choosing (EA-5, Deferred)

`044 §23` deliberately leaves undecided (a) the product behaviour when a Source Timeline holds a
cross-actor Conflict — whether an Assembly is admitted at all, admitted without those candidates, or
refused outright, and whether the Conflict must be surfaced at export time — and (b) the treatment of
a scope with no eligible member.

`admit_assembly` therefore raises `EditExportUndecidedPolicyError` in both situations. **This is not
a product refusal.** It does not mean "this timeline cannot be exported"; it means the Blueprint does
not yet say, and `§23`'s Deferred section prohibits an implementation from settling the question by
picking a behaviour and shipping it — the chosen behaviour would be read back as the contract. It is
the runtime form of the AGENTS.md Stop Condition "product policy materially undefined by current
contracts", and the message says so in words.

`observe_scope` is the counterpart and **never stops**: a person must be able to see a Conflict in
order to resolve it in Review, which is where `§3.12` puts the resolution. Cross-actor arbitration —
priority, recency, role ranking, merge, automatic selection — exists nowhere in the implementation,
and `043 §15.3` stays declined rather than answered by implication.

**No overlap rule exists either.** EA-4's predicate does not consider overlap, so two eligible
approved edits with overlapping ranges are both members; a test asserts it. An implementation may not
invent an overlap filter under this contract.

## Execution-free provenance (EA-8)

No `ProcessingRun`, `ProcessingUnit`, `UnitExecution`, RUNNING state, or `DomainResult` is required,
referenced, or fabricated — tests assert the run and result relation counts are unchanged across an
admission. Construction is deterministic and replay-safe: no wall clock, no randomness, same
persisted state → same Assembly. Source Media and Source Timeline provenance is secured through the
anchor chain rather than denormalized, keeping the released "inherit, never duplicate" idiom
(`042 §8.2` D-2, `§9.3` C-8, `§7.5` R-7); only the Source Timeline anchor itself is stored, because
`§20` A-1 makes it the Assembly's anchor.

## Architecture

- `application/lecture_edit_export_assembly.py` — `LectureEditExportAssembly`,
  `LectureEditExportAssemblyMember`, `ExportEligibility`, `CandidateExportStanding`,
  `ExportScopeObservation`, the deterministic identity, `canonical_member_order`,
  `LectureEditExportAssemblyService` (observe_scope / admit_assembly / get / members / history), and
  the three error types.
- `persistence/lecture_edit_export_assembly.py` — the scope repository (lineage walk only), the
  assembly repository, and one atomic `BEGIN IMMEDIATE` insert-only command persistence. No update or
  delete method exists.
- `composition.compose_sqlite_lecture_edit_export_assembly_service(connection)` — wires the released
  GOAL-028/029 Review service (the sole authority and standing path) over the v53 store.
- `lecture_edit_export_cli.py` — `scope`, `assemble`, `show`, `history`.

## Persistence and migration (EA-10)

v52 → v53, strictly additive: `lecture_edit_export_assemblies` (identity PK; non-blank
`source_timeline_id`; contract-version CHECK) and `lecture_edit_export_assembly_members`
(`PRIMARY KEY (assembly_id, ordinal)`; `UNIQUE (assembly_id, approved_edit_decision_id)`;
non-negative ordinal CHECK; FKs to the parent Assembly and to
`lecture_approved_edit_decisions`). **No `domain_result_id`, `processing_run_id`,
`unit_execution_id`, per-admission `sequence`, wall-clock, status, currentness, or selection column
exists**, and no approved payload is copied — the approved kind, range, label, and rationale stay
owned by the `ApprovedEditDecision` and are reached through the reference.

The uniqueness is deliberately **per assembly**: one approved edit may belong to several assemblies
over time, because membership is derived and total. A global uniqueness on
`approved_edit_decision_id` would make the second, legitimately different assembly unrepresentable.

Every released version v1..v52 chains single-step to v53 preserving all rows; a migration test
captures the `CREATE TABLE` statements of this generation's three Review relations **and the legacy
`approved_edit_export_representations` / `edit_export_assemblies` / `edit_export_assembly_members`
family** before and after the step and asserts they are byte-identical, with the new tables empty.
Downgrade, direct-skip, and unsupported targets stay rejected. The legacy Export family is never read
or written — a test asserts all three relations stay empty after an admission — because its mandatory
legacy anchors and execution provenance could only be satisfied by fabricating what EA-8 prohibits.

## Validation (integrity only)

Five `LECTURE_EDIT_EXPORT_ASSEMBLY_*` codes. **Four are reached by a corruption test**: an emptied
assembly, a tampered membership that breaks identity re-derivation, a member reference that does not
resolve, and a non-contiguous ordinal. **One is schema-guarded, therefore defence-in-depth**: the
contract version, whose CHECK refuses the write first even with `PRAGMA foreign_keys = OFF`.

Deliberately **never** flagged: several assemblies on one Source Timeline with different membership;
an assembly whose member's judgment was later superseded or whose chain later lost current standing
(the assembly records what was eligible when it was admitted and is never rewritten); one approved
edit appearing in several assemblies; a Source Timeline with no assembly at all. Validation reads no
filesystem, media, or provider.

## Status

Complete: 75 focused new tests (records, service, persistence, migration, CLI, validator
diagnostics); the complete 3267-test suite passes; schema v53.

Not re-scoped by `PATCH-0035` and therefore still needing their own approved decision: `044 §21`
Artifact and `§22` concrete serialization for this generation (so this milestone ends at a durable
Assembly and produces **no file** — that absence is the contract, not a defect); the product
behaviour on a timeline holding a cross-actor Conflict; overlap adjudication and inter-decision
ordering semantics; the treatment of a scope with no eligible member; explicit subset selection,
Export Profile and Export Configuration; and every `043 §15.4` deferred item.
