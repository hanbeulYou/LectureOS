# PATCH-0028

- Title: Effective Transcript Consumption Boundary (First Slice) (040)
- Status: Accepted
- Priority: Medium
- Trigger: Architect / Product Owner Decision (GOAL-012 — first downstream consumption boundary)
- Created: 2026-07-26
- Target Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` (first consumption realization over the §13–§20 slice
  chain and its §20 effective-transcript resolver)

---

## Status

Accepted. Establishes the first **Effective Transcript Consumption Boundary**: the shared application boundary
through which a downstream transcript-derived operation acquires **one immutable transcript source** — resolved
solely by the §20 effective-transcript resolver, validated for consumability, loaded by exact immutable source
identity, and recorded as a stable, deterministic **consumption binding** at schema **v38**. Five distinctions
are preserved: current authority ≠ consumed source ≠ historical Result lineage ≠ Result currentness ≠
repository integrity. Exactly one bounded first consumer (a neutral deterministic consumption manifest) proves
the boundary; no existing downstream subsystem switches its source.

## Trigger

GOAL-011 (PATCH-0027) established which transcript is effective *now*. Downstream operations (validation,
subtitle, review preparation, analysis, export, future processing) must not each answer independently which
transcript to consume — nor consume a moving selection pointer. Without one shared boundary, subsystems could
use the latest Raw, the latest Revision, an inapplicable selected Revision, silently fall back to Raw, or
re-resolve authority mid-operation. GOAL-012 requires the explicit consumption contract; a bounded Product
decision settled it and this PATCH promotes it.

## Reuse investigation (required by GOAL-012 §9)

- **§20 effective-transcript resolver** — **reused as the sole resolution authority.** Extended additively
  only: the resolver result now also carries the exact authority record identities it already observed
  (current Raw selection identity; current corrected selection identity where history exists), so acquisition
  needs no second read of authority state and no consumer duplicates resolution logic.
- **Legacy readiness / subtitle-intake path (`TranscriptReadinessEvaluation`, `SubtitleTranscriptIntake`,
  §4.6–§4.8 machinery)** — **not reusable as the first consumer**: it requires the legacy
  `TranscriptCurrentSelection` + ApplicabilityEvaluation + ReviewItem + CandidateReference lineage and a
  RUNNING unit execution; integrating it with the §13–§20 chain would require fabricating review/execution
  machinery (forbidden). It remains untouched on its own recorded lineage.
- **Canonical `RawTranscript` / `CorrectedTranscriptRevision` / `TranscriptSegment` (v5)** — **reused** as the
  only transcript snapshot representation: both sources expose ordered `segment_ids` over the same canonical
  segment record (identity, order, text, timing, speaker, provenance, `replaces_segment_id` lineage). No
  second transcript hierarchy, no flattened copy.
- **§19 `content_fingerprint_for` (order/text/timing canonical content identity)** — **reused verbatim** as the
  snapshot content fingerprint; no new fingerprint format.
- **§16/§18/§20 deterministic-identity and admission-binding conventions** — **reused** (SHA-256 canonical
  JSON identity, replay-anchor UNIQUE, atomic `BEGIN IMMEDIATE` persistence, converge-on-collision).
- **DomainResult / ProcessingRun / Artifact machinery** — **not used**: the first consumer is a deterministic
  local transformation; truthful provenance requires no execution records, no fake `RUNNING` executions, no
  Artifact, no physical file.
- **What is new**: only the canonical `EffectiveTranscriptInput` application representation, the acquisition
  service, the additive `effective_transcript_consumptions` table (v38), and the derived currentness query.

## First-Slice Product Decision

### Resolution ≠ consumption binding

Effective resolution answers "what is effective **now**"; a consumption binding answers "what exact transcript
did this operation **consume**". A downstream operation consumes one immutable transcript source — never a
moving selection pointer. Once acquired, the operation stays pinned to that source; authority is never
re-resolved midway, and segments are loaded by the immutable resolved source identity — never back through
current authority (no mixed-source snapshot).

### Canonical input and source kinds

`EffectiveTranscriptInput` normalizes both sources without erasing their kind: intake context, resolver state
observed (`no_history` / `raw_fallback` / `corrected_revision_selected`), source kind (`raw_transcript` |
`corrected_transcript_revision` — never an ambiguous generic id), exact immutable source identity, exact Raw
parent identity, authority provenance (the observed Raw selection record, and corrected selection record where
history exists), the ordered canonical segment snapshot, and the §19 content fingerprint. No-history Raw and
explicit Raw fallback yield the same Raw source with distinguishable provenance. Corrected replacement lineage
(`replaces_segment_id`) and provider/human provenance pass through faithfully; nothing is fabricated.

### Consumability

New consumption requires a consumable source **now**: no current Raw selection → explicit failure; selected but
inapplicable corrected Revision → explicit refusal with the resolver's reason — never a silent Raw fallback.
Query-time currentness of an existing binding is a separate, derived comparison (`current` /
`stale_due_to_raw_selection_change` / `stale_due_to_corrected_selection_change` /
`stale_due_to_selected_revision_inapplicability` / `unresolvable`) — never a stored flag, never a mutation,
never a validation finding.

### Stable binding, deterministic identity, replay

The persisted binding is owned by (consumer kind, intake context) and records the exact source consumed with
its authority provenance and content fingerprint. Persistence is justified by the goal's own criteria: replay
depends on source identity, audit must show what was consumed, later authority changes must not reinterpret
records, and repository validation must verify lineage. Identity derives from SHA-256 of
`(consumer kind, intake, source kind, exact source identity)` — no wall-clock/UUID/randomness; authority
provenance and fingerprint are recorded facts, not identity. Same consumer + same source → **reused** (a later
identical consumption converges on the existing binding; recorded provenance remains the first observation);
different source → a distinct binding; identical near-concurrent requests converge on the persistence
collision; a fingerprint disagreement for the same identity is an explicit conflict. Bindings are never
mutated, deleted, or auto-regenerated when authority changes; stale bindings are historically valid and are
not corruption.

### Bounded first consumer

The first consumer is a **neutral deterministic consumption manifest** (`transcript_consumption_manifest`): its
persisted output is the binding itself carrying a harmless deterministic summary (segment count + §19 content
fingerprint). Chosen because the preferred candidates are unavailable without scope violation: the existing
validation/readiness and subtitle-intake boundaries live on the legacy §4.6–§4.8 path (RUNNING executions,
legacy selection machinery), and adapting them would force review/subtitle architecture decisions. The manifest
consumer proves acquisition, pinning, replay, authority-change stability, and validation without deciding any
subtitle/review/export design. No other consumer is integrated; no automatic reprocessing, deletion, or source
switching exists anywhere.

### Atomicity and boundaries

Binding persistence is one atomic transaction; failures leave the repository unchanged. The boundary mutates
nothing upstream: revisions, candidates, decisions, Raw Transcripts, Raw selections, and corrected selections
are read-only inputs. No cascade deletion can destroy consumption history.

## Explicit Deferred Scope

Switching transcript validation / subtitle generation / review preparation / export / analysis to this
boundary; automatic staleness reactions (reprocessing, regeneration, invalidation, deletion); additional
consumer kinds; multi-source or merged consumption; content-based deduplication across sources; physical
materialization — all deferred to separately gated milestones. No placeholders are introduced.

## Consequences

- 040 gains the first confirmed consumption-boundary contract (`040 §21`): downstream operations acquire
  immutable transcript sources through one shared boundary instead of interpreting selection authority
  themselves.
- Schema advances additively to **v38** (one new table `effective_transcript_consumptions`); every released
  version v1..v37 reaches v38 through the supported single-step chain with no data loss.
- The §20 resolver result additively exposes observed authority identities; its meaning, states, and no-silent-
  fallback behavior are unchanged. All §13–§20 contracts and the legacy §4.6–§4.8 machinery are unchanged.
