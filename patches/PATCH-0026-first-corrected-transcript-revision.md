# PATCH-0026

- Title: First Corrected Transcript Revision — One-Candidate Explicit Application (First Slice) (040)
- Status: Accepted
- Priority: Medium
- Trigger: Architect / Product Owner Decision (GOAL-010 — first corrected-transcript revision boundary)
- Created: 2026-07-26
- Target Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` (§4.4 Correction / §6.2 Correction Provenance — first
  application of an accepted candidate)

---

## Status

Accepted. Establishes the first **immutable Corrected Transcript Revision** derived by explicitly applying
exactly **one currently Accepted** Correction Candidate (040 §17/§18) to its authoritative source Raw
Transcript. It **reuses the canonical `CorrectedTranscriptRevision`** (transcript domain, schema v5 — complete
snapshot via ordered segment references, replacement segments carrying `replaces_segment_id`,
`parent_raw_transcript_id`, `correction_candidate_ids`) and binds it to its generation context with one additive
record — the **Corrected Revision Generation** — at schema **v36**. The revision is **not** selected as current
(Current Corrected Revision Selection is GOAL-011); nothing mutates the Raw Transcript, the candidate, the
decision history, or the current Raw Transcript selection.

## Trigger

GOAL-009 (PATCH-0025) established Human Authority: only a currently Accepted candidate is eligible for revision
generation. The eligibility existed but no application boundary did — LectureOS could not yet produce the
corrected transcript state that §4.4 promises downstream. GOAL-010 requires the smallest one-candidate
application slice, consuming the §18 authority contract without reinterpreting it. A bounded Product decision
settled it and this PATCH promotes it.

## Reuse investigation (required by GOAL-010 §7)

- **`CorrectedTranscriptRevision` (v5)** — the repository's confirmed corrected-transcript representation:
  complete snapshot via ordered segment references (unchanged source segments **retain** their identities; the
  corrected segment is a **new** revision-scoped `TranscriptSegment` with `replaces_segment_id`), a
  `parent_raw_transcript_id` (with `parent_revision_id` already modeled for future chaining, not used here), and
  `correction_candidate_ids`. **Reused unchanged** — no second transcript representation, no new revision model.
  This settles GOAL-010 §14/§24/§28 (complete snapshot via references — not a patch/delta) and §29 (parent =
  Raw Transcript) from existing confirmed contracts.
- **`TranscriptService.create_corrected_revision`** — requires a RUNNING internal unit execution; **not
  reusable** as the service for a deterministic local application (no fake executions). Its transaction-free
  insert helpers (`_insert_corrected_transcript_revision`, `_insert_transcript_segment`,
  `_insert_domain_result_reference_record`) **are reused** — the PATCH-0021/24 pattern — so a generated revision
  is structurally identical to an internally produced one.
- **What is new**: only the additive generation binding (`corrected_revision_generations`, v36) recording the
  candidate, the **specific authorizing Accepted Decision**, the parent, the replaced/replacement segments, the
  content fingerprint, and the deterministic replay anchor.

## First-Slice Product Decision

### Explicit, separate authority boundaries

Acceptance authorizes; generation applies. Accepting a candidate **never** creates a revision
(`Accepted ≠ Applied ≠ Current`). Generation is an explicit request naming exactly **one** candidate — no
apply-all/best/latest, no implicit discovery, no multiple-candidate merge, no ranking, no overlap resolution.
Competing revisions from independently applied candidates may coexist; no one-revision-per-transcript/segment
constraint exists; current selection is a later, separate authority (GOAL-011).

### Eligibility and applicability

Generation requires the candidate's **current** Human Authority (§18 derived) to be Accepted — Undecided and
Rejected are ineligible, and historical acceptance is insufficient after a later Reject. The candidate must also
remain structurally applicable to its own lineage (§17): its Raw Transcript must be the intake's current
selection, its target segment must belong to that transcript, and the persisted segment text must still equal
the candidate's source-text snapshot. Staleness/non-applicability is application-level ineligibility, never
repository corruption, and never triggers fuzzy matching, rebasing, or automatic retargeting.

### Deterministic application

Application is a pure deterministic transformation: replace exactly the candidate-owned segment's text with the
candidate's proposed text (exact — no normalization/trimming/punctuation rewriting), preserving the segment's
timing, ordering, timeline linkage, and speaker metadata, and referencing every unaffected segment unchanged.
Corrected text provenance stays human (via the candidate/decision lineage); provider provenance stays on the
source segments; the replacement segment carries no fabricated provider confidence. Text correction only —
no timing correction, segment deletion, splitting, or merging (all admitted candidate kinds are single-segment
text replacements; anything else would fail before persistence). Empty replacement remains impossible (§17
rejects empty proposed text).

### Identity, authorizing decision, replay, and conflict

All identities derive deterministically from the anchor `(candidate, authorizing_accepted_decision)` (SHA-256):
the revision (`corrected-revision:<digest>`), the generation record, the domain result, the derived
external-application execution markers (no internal RUNNING execution, no fake Processing Run), and the
replacement segment. Because Human Authority is append-only, **distinct** authorizing Accepted Decisions
(Accept#1 vs Accept#2 after a Reject) are distinct authority facts and yield **distinct** revisions — immutable
records cannot acquire new provenance; entity identity and content identity remain distinct (a separate
content fingerprint over order/text/timing records that such revisions may carry identical content). Identical
replay (same anchor) reuses the existing revision — after restart, from the CLI, and under near-concurrent
duplicates (converging on the persistence collision). A same-anchor replay whose resulting content differs is an
explicit immutable-identity conflict — never an overwrite.

### Historical validity after authority change

`Accept → Generate → Reject` is legal: the revision remains persisted, immutable, and queryable, referencing its
authorizing Accepted Decision; the new Reject only blocks *new* generation. Repository validation inspects the
**specific authorizing decision** (must be an Accept belonging to the candidate), never the candidate's current
authority — a historical revision is never corruption.

### Atomicity and boundaries

Generation is one atomic transaction (replacement segment + revision + membership + candidate reference + domain
result + generation binding — all or nothing). The revision is a domain record, not a physical file (no
materialization, no path identity). The canonical `DomainResultReference` (kind `corrected_transcript_revision`,
upstream = the Raw Transcript's domain result) preserves §6.2 correction provenance.

## Explicit Deferred Scope

Current Corrected Revision Selection (GOAL-011), multiple-candidate application/merge/composition, overlap
resolution, revision-on-revision chaining (modeled by the existing `parent_revision_id`, not implemented),
candidate ranking/recommendation, automatic correction, LLM/grammar/punctuation engines, linguistic validation,
mutable editing, segment deletion/splitting/merging, timing correction, subtitle regeneration, and export
changes — all deferred. No placeholders are introduced.

## Consequences

- 040 gains the first confirmed corrected-revision application contract (`040 §19`) consuming §17/§18 unchanged.
- Schema advances additively to **v36** (one new table `corrected_revision_generations`); the v5 corrected-
  revision/segment/domain-result tables are reused unchanged; every released version v1..v35 reaches v36 through
  the supported single-step chain with no data loss.
- Human Decision (§18), Candidate Admission (§17), Current Raw Transcript Selection (§16), Raw Transcript
  identity, and the §4.6/§4.7 review path are unchanged. GOAL-011 can select among existing revisions without
  redesigning these identities.
