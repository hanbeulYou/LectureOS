# Edit Export Artifact — Effective-Transcript Generation

- Status: Implementation Reference
- Blueprint: `docs/044` §24 + `PATCH-0036` (AR-1…AR-11, Confirmed) — the effective-transcript
  generation's Edit Export **Artifact** boundary over the GOAL-030 Assembly (GOAL-031); `§21`'s
  legacy contract and `§23` EA-1…EA-11 are inherited unchanged
- Schema: **v53, unchanged** — no table, no migration, no validator code (AR-11)

## Purpose

`044 §23` ended at a durable Assembly with no consumer. `§24` decides how that Assembly becomes the
canonical **external representation** of its approved edit meaning — *what* is communicated, never
*how it is written*.

```text
derive_artifact(assembly_id)
    → one §23 Assembly, read-only            (AR-2: exactly one, complete, no partial artifact)
    → the timeline's candidates, for the lineage check §21 B-11 requires
    → per member, in the Assembly's canonical order:
        ApprovedEditDecision  → approved kind, range, label, rationale   (owns them, R-8)
        ReviewDecision        → human actor
    → LectureEditExportArtifact — derived, returned, never stored
```

**Nothing is written, approved, executed, serialized, or re-decided.** No serializer, concrete
syntax, file, output timeline, package, download, URL, provider, NLE adapter, Export Profile, or
Export Configuration exists; `§22` remains deferred for this generation.

## Not persisted — the decision AR-11 left open (AR-11, AR-9)

AR-11 makes a durable representation neither required nor prohibited, and none is added. The reason
is that **the Artifact carries no fact the repository does not already hold**: it is a pure function
of the Assembly, whose identity binds its Source Timeline and exact membership (`§23` EA-10), and of
member records that are immutable. Storing it would duplicate a derivation rather than record
anything, and a stored row invites exactly the authority AR-9 denies the Artifact. The legacy `§21`
realization made the same choice for the same reason and left `SQLITE_SCHEMA_VERSION` untouched.

Consequences, recorded so they are not mistaken for omissions: **no new table or migration**, so the
schema stays at **v53**; **no validator codes**, because there are no rows to check for integrity;
and **regeneration is the read path** — `derive_artifact` is called again rather than a row being
fetched. Should a later milestone need a durable form (most plausibly once `§22` exists), AR-11's
conditions apply: strictly additive, never authoritative, and the legacy `edit_export_*` family not
reused.

## Identity converges — a consequence, not a cardinality rule (AR-7)

`lecture-edit-export-artifact:<sha256(contract kind, contract version, source assembly identity)>`,
Application-owned. No provider identifier, execution identifier, `DomainResult`, UUID, timestamp,
wall clock, rowid, path, or mutable currentness participates. **`§21`'s caller-owned identity stays
with the legacy generation** (`043 §7.5` R-10).

Binding the Assembly identity alone is sufficient rather than minimal: that identity already binds
the Source Timeline and the exact membership, and every member is immutable, so it determines the
presented content completely. Re-deriving therefore yields the same identity and the same content —
**canonical derivation converges**. That is the consequence of the identity contract, not a product
rule that only one Artifact may exist; `§21` B-13's permitted plurality is untouched, and **no
discriminator parameter exists** (a test pins the signature). A future need for several
representations of one Assembly belongs to the serializer projecting this Artifact (`§21` B-4,
`§22` C-10).

**Reachability accounting (`§7.5` R-10 (A)/(B)).** The (A)/(B) accounting is about a *stored* payload
diverging from an existing identity. Nothing is stored here, so that branch does not exist: two
derivations from one Assembly are equal because every input is immutable. There is accordingly no
semantic-equality check to keep and no conflict error to raise — which is why the module defines
none. Should persistence ever be added, the accounting must be redone at that point.

## Two layers, and where each value comes from (AR-3, AR-4)

| Presented value | Owner it is copied from |
| --- | --- |
| approved decision kind, range start/end, label, rationale | `ApprovedEditDecision` (`043 §7.5` R-8) |
| human actor | the `ReviewDecision` that owns the approval |
| entry order | the Assembly's canonical member order (`§23`) |

`§19`'s atom layer is absent (`§23` EA-2), so the layering is **owns → references → presents**. The
Artifact holds a **copy**; AR-4 records why that is not a breach of this generation's "inherit
through the anchor, never duplicate" idiom — that idiom governs canonical records, and presenting a
self-contained external product is the Artifact stage's whole purpose. Values are copied verbatim,
never re-derived or reinterpreted, and the range stays a **Source Timeline** range, never an
output-timeline coordinate.

## Nothing is re-decided (AR-8) — the decision `§21` could not have made

Export eligibility, admission standing, authority history, and cross-actor Conflict are **not
consulted**. Membership was fixed when the Assembly was admitted. Three consequences are driven by
tests:

- a member whose judgment is later **superseded** still yields a byte-equal Artifact;
- a member whose chain later **loses `current` standing** still yields a byte-equal Artifact, while
  the scope observation correctly reports `superseded_by_authority_change`;
- a Candidate that later enters a **cross-actor Conflict** does not stop derivation — `§23`'s
  undecided conflict policy stays at admission and is **not reopened** here.

The Artifact also never changes the Assembly's membership or a member's approved meaning: it does not
filter, merge, split, or omit. **Presentation order is not what that protects** — order was already
fixed as presentation by `§23`, and how a future `§22` serializer expresses it is unconstrained.

## Representation Failure is explicit (AR-10 / `§21` B-11)

Three structural failures raise `ArtifactRepresentationFailureError` naming what could not be
presented, and never produce a shortened Artifact:

1. a member `ApprovedEditDecision` that cannot be resolved;
2. a member whose Candidate does not belong to the Assembly's Source Timeline — B-11's "lineage
   inconsistent with the Assembly" case;
3. a member whose owning `ReviewDecision` cannot be resolved, so the human actor cannot be presented.

All three are **structural**, never a judgement about eligibility, standing, authority, or Conflict —
re-evaluating those is what AR-8 prohibits. A test asserts the approved sources are byte-identical
after a failure. Format-specific representability stays with `§22`.

## Architecture

- `application/lecture_edit_export_artifact.py` — `LectureEditExportArtifact`,
  `LectureEditExportArtifactEntry`, the deterministic identity, `LectureEditExportArtifactService`
  (`derive_artifact`), and the two error types. Read-only throughout; no persistence module exists.
- `composition.compose_sqlite_lecture_edit_export_artifact_service(connection)` — wires the released
  GOAL-030 assembly and scope repositories and the released GOAL-028 Review repository. Every
  dependency is a **query**; there is no command persistence to wire.
- `lecture_edit_export_cli.py` — gains `artifact`; its `_NOT_PART` banner drops "artifact" (now part
  of the contract) and keeps serializer, file, Profile, Configuration, selection, and overlap.

## Status

Complete: 27 focused new tests (identity and record invariants, derivation, the three AR-8
consequences, the three Representation Failures, and the CLI); the complete **3294**-test suite
passes; schema **v53 unchanged**; no `src/` persistence, migration, or validator code added.

Not re-scoped by `PATCH-0036` and therefore still needing their own approved decision: **`044 §22`
concrete serialization and local materialization for this generation** — so this milestone, like
GOAL-030, produces **no file**, and that absence is the contract rather than a defect. Also
unchanged: `§23`'s three undecided policies (the product behaviour on a timeline holding a
cross-actor Conflict, overlap adjudication, and the treatment of a scope with no eligible member),
Export Profile and Export Configuration, provider and NLE adapters, delivery, and every `043 §15.4`
deferred item.
