# PATCH-0027

- Title: Current Corrected Transcript Revision Selection and Effective Transcript Resolution (First Slice) (040)
- Status: Accepted
- Priority: Medium
- Trigger: Architect / Product Owner Decision (GOAL-011 — first corrected-revision selection authority)
- Created: 2026-07-26
- Target Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` (§4.8 Transcript Ready State — first current-corrected
  selection realization for the §13–§19 slice chain)

---

## Status

Accepted. Establishes the first **explicit, append-only Current Corrected Revision Selection** authority: which
immutable `CorrectedTranscriptRevision` (040 §19), if any, is currently selected for an intake's transcript
context — including an explicit **Raw Transcript fallback** — plus the deterministic **effective-transcript
resolver**. Introduces one additive append-only record at schema **v37**. Revision existence ≠ revision
selection ≠ revision applicability ≠ effective resolution: all four distinctions are preserved. No revision,
candidate, decision, raw transcript, or current Raw Transcript selection is mutated; nothing is auto-promoted.

## Trigger

GOAL-010 (PATCH-0026) established immutable corrected revisions that may coexist without any current authority.
Downstream consumers need exactly one deterministic answer to "which corrected transcript, if any, is current?"
— without reinterpreting Human Decision acceptance or the Raw selection. GOAL-011 requires the explicit selection
authority and resolver. A bounded Product decision settled it and this PATCH promotes it.

## Reuse investigation (required by GOAL-011 §13)

- **Legacy `TranscriptCurrentSelection` (v9, §4.8 machinery)** — selects a corrected revision, but **requires**
  an `ApplicabilityEvaluation` + `TranscriptReviewDecision` + `ReviewItem` + `CandidateReference` + a RUNNING
  unit execution (the old §4.6/§4.7 review path), and cannot represent an explicit Raw fallback (its outcome is
  selected/not_selected per applicability evaluation, not a selection-kind authority). **Not reusable** for the
  §13–§19 slice chain without fabricating review/execution machinery (forbidden). It remains untouched for its
  own revision-review path.
- **Reused patterns**: the §16/§18 append-only authority idiom (per-context `sequence` + `previous_selection_id`,
  current = highest sequence, deterministic SHA-256 identity, reuse/changed/conflict semantics, converge-on-
  collision); `HumanActorReference` for the selecting actor; the intake (`TranscriptSourceIntakeId`) as the
  stable selection context (the same context §16 anchors Raw selection to); the §19 generation binding + §17
  admission as the revision→context lineage; existing validation/migration/CLI/golden conventions.
- **What is new**: only the additive `corrected_revision_selections` table (v37) and the effective resolver.

## First-Slice Product Decision

### Owner and context

The selection is owned by the **intake context** (`TranscriptSourceIntakeId`) — the stable transcript context
that also anchors Current Raw Transcript Selection. A revision's context is derived from its own immutable
lineage (generation → candidate admission → intake), so revisions from unrelated contexts cannot compete in one
history and the CLI derives context from the revision (no contradictory duplicate inputs). Selection identity is
anchored to this stable context, never to a mutable pointer, label, or path; history reconstructs after upstream
Raw-selection changes.

### Explicit authority, two actions, three derivable states

Currentness is explicit — never inferred from recency, uniqueness, acceptance, generation success, or validation.
Two append-only actions exist: **Select Corrected Revision** and **Select Raw Transcript Fallback** (an explicit
authority fact — never a fake revision; kind/revision consistency is CHECK-enforced). Three derivable states:
**no selection history** (nothing ever recorded), **explicit Raw fallback**, and **corrected revision selected**
— initial absence and explicit fallback derive the same effective state but remain historically distinguishable.

### Append-only history, derived current, deterministic identity

History is INSERT-only (per-intake `sequence` + `previous_selection_id`); the current selection is the
highest-`sequence` record — derived, never a stored `is_current` flag or mutable pointer, never timestamp-
ordered. Identity derives from SHA-256 of `(intake, kind, revision-or-none, sequence)` — no wall-clock/UUID/
randomness; reviewer and rationale are provenance, not identity. The normative replay matrix holds: identical
semantic target → **reused** (no new row, a differing rationale alone does not append); different target →
**append** (`recorded` at sequence 0, else `changed`, reporting the superseded state). Near-concurrent identical
requests converge on the persistence collision; divergent concurrent requests surface an explicit conflict for
retry — never resolved nondeterministically.

### Write-time eligibility vs query-time applicability

**New** selection requires eligibility now (no `--force`): the revision must exist with its §19 generation
binding and intake lineage, its parent Raw Transcript must be the intake's current Raw selection, and its
candidate's current §18 authority must be **Accepted** (a revision under a currently-Rejected candidate is
historically valid but not newly selectable). **Existing** selection is never retro-judged: a later Candidate
Reject or Raw-selection switch makes the selected revision *inapplicable* (`candidate_not_accepted` /
`parent_raw_transcript_not_current`) — selection history is never mutated, cleared, auto-fallen-back, or flagged
as corruption. Selection answers "what did the authority choose?"; applicability answers "can it currently be
used?".

### Effective transcript resolution

The deterministic resolver returns an explicit structured result: raw (no history), raw (explicit fallback),
corrected (selected + applicable), or **selected-but-inapplicable with a reason** — never a silent fallback that
hides an authority conflict, never a nullable that conflates states. It is the stable query contract for future
downstream consumers (validation, subtitle, review, export); **no existing consumer is switched** to it in this
slice.

### Atomicity and boundaries

Each selection append is one atomic transaction with supersession validation; failures leave the repository
unchanged. Unselected revisions are never marked rejected/superseded/inactive; selecting Revision B supersedes
only the prior selection *authority*, not Revision A as an entity. No cascade deletion can destroy selection
history.

## Explicit Deferred Scope

Downstream integration (switching transcript validation / subtitle / review preparation / export to the
resolver), revision generation/ranking/recommendation, automatic selection or fallback, multi-candidate
revisions, revision chaining, mutable annotations, workflow/publication/approval statuses, and review UI — all
deferred. No placeholders are introduced.

## Consequences

- 040 gains the first confirmed corrected-selection + effective-resolution contract (`040 §20`) completing the
  §13–§19 slice chain's authority story; the legacy §4.8 machinery is untouched.
- Schema advances additively to **v37** (one new append-only table `corrected_revision_selections`); every
  released version v1..v36 reaches v37 through the supported single-step chain with no data loss.
- Corrected Revision Generation (§19), Human Decision (§18), Candidate Admission (§17), Current Raw Transcript
  Selection (§16), and all downstream subtitle/export contracts are unchanged.
