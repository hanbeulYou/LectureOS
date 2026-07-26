# PATCH-0023

- Title: Current Raw Transcript Selection and Downstream Readiness (First Slice) (040)
- Status: Accepted
- Priority: Medium
- Trigger: Architect / Product Owner Decision (per-intake current Raw Transcript authority and readiness)
- Created: 2026-07-26
- Target Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` (§4.3 → §4.4 handoff; realizes the current-input authority)

---

## Status

Accepted. Establishes the first application contract for **which admitted `RawTranscript` is the current
authoritative downstream input for a `TranscriptSourceIntake`**, and whether the intake is **ready** to begin
downstream Correction. Introduces one additive persisted record — the append-only **Current Raw Transcript
Selection** — at schema **v33**. No transcript content, provider result, Source Media, or intake row is ever
mutated; no Correction, Validation, Review, Subtitle, or Export behavior is implemented.

## Trigger

After External Provider Transcript Admission (040 §14, PATCH-0021) and the first local ASR adapter (040 §15,
PATCH-0022), a single intake may hold **several** admitted Raw Transcripts (different providers/models/languages).
Downstream Correction (040 §4.4) expects **one** Raw Transcript as its input, but no authority decided which. A
bounded Product decision settled that authority — an explicit, deterministic, append-only per-intake selection —
and this PATCH promotes it.

## Context

A Provider Transcript Result is evidence; a Raw Transcript is the first canonical transcript projection. The
**current Raw Transcript selection** decides which Raw Transcript is authoritative as the downstream input for one
intake. It is distinct from the corrected-transcript current selection (040 §4.8, the `transcript_current_selections`
applicability record) and from final downstream selection. It sits between §4.3 (Raw Transcript preservation) and
§4.4 (Correction) and never rewrites or deletes a non-selected transcript.

## First-Slice Product Decision

### Explicit authority, never ranked

Selection is an explicit Product and repository authority decision. It is **never** inferred from provider name,
model size, latest wall-clock time, transcript length, or confidence, and no candidate is labelled "best".
Candidate enumeration is deterministic — ordered by Raw Transcript identity — and carries only provider/model
provenance metadata, never a ranking. The candidates of an intake are exactly its admitted Raw Transcripts (read
from `provider_transcript_admissions`).

### Explicit initial selection (admission unchanged)

Selection is **always explicit**, even when only one Raw Transcript exists. Provider Transcript Admission is left
unchanged — admitting a result does not auto-select it — so authority is never implied by mere existence, and
readiness stays `not_ready` until an explicit selection is made:

```text
0 Raw Transcripts → not_ready
1 Raw Transcript  → not_ready until explicitly selected → ready
2+ Raw Transcripts → exactly one explicit current selection required
```

### Append-only supersession, one current per intake

History is **append-only** (the repository's established authority-change idiom): each selection is an immutable
record with a per-intake ``sequence`` (0-based) whose ``previous_selection_id`` supersedes the prior current
record. The **current** selection is the highest-``sequence`` record for the intake; ordering is by ``sequence``,
never by wall-clock. Switching creates a new record (``sequence`` + 1) and **preserves** all prior records —
switching never deletes or mutates any transcript or prior selection. Selecting the already-current Raw Transcript
is **idempotent** (no new record). A near-concurrent duplicate converges on the existing current selection.

### Deterministic identity

The selection identity is derived deterministically from the intake, chosen Raw Transcript, and sequence
(`raw-transcript-selection:<sha256(intake, raw_transcript, sequence)>`). No wall-clock/randomness defines identity.

### Readiness derived from repository state

Readiness is derived from current persisted facts, not persisted itself, and is one of: `not_ready` (no current
selection), `ready` (exactly one valid current Raw Transcript is selected), `error` (the persisted current
selection is inconsistent — e.g. its Raw Transcript is no longer an admitted candidate of the intake). Readiness
**never** depends on source-file physical existence, ASR/provider availability, model accuracy, transcript
confidence, or human review. Later admissions never silently invalidate or replace the current selection, so a
newer admission does not make the current selection stale; only an inconsistent persisted selection yields
`error`.

### Explicit rejection and failure atomicity

A malformed intake or Raw Transcript identity, an unknown intake or Raw Transcript, and a Raw Transcript that
belongs to a **different** intake are all rejected explicitly. The append is a single atomic transaction; any
failure leaves no partial selection state and mutates neither the transcript, provider result, Source Media, nor
intake. A human `reason` may accompany a selection but is optional.

### Downstream authority

Downstream Correction sees exactly one current Raw Transcript per intake. Selection does not compare ASR quality,
alter Raw Transcript content, or execute Correction — Correction itself is out of scope here.

## Explicit Deferred Scope

Transcript correction and correction candidates, grammar/punctuation correction, structural transcript validation,
human review, automatic transcript scoring, ASR confidence ranking, model/provider ranking, automatic
best-transcript selection, transcript merging/ensemble, word-level alignment, diarization, subtitle/export/rendering
changes, queues, retries, progress, cloud ASR, additional local ASR adapters, provider registries, and generic
workflow status engines — all deferred. No placeholders are introduced.

## Consequences

- 040 gains a confirmed current-Raw-Transcript authority + readiness contract (`040 §16`) between §4.3 and §4.4.
- Schema advances additively to **v33** (one new append-only table `current_raw_transcript_selections`); every
  released version v1..v32 reaches v33 through the supported single-step chain with no data loss.
- Provider Transcript Admission, Raw Transcript identity, and the corrected-transcript current selection (§4.8)
  are unchanged; no second transcript hierarchy or generic workflow engine is introduced.
