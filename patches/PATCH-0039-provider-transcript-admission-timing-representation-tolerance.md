# PATCH-0039

- Title: Provider Transcript Admission Timing Boundary Representation Tolerance (040 §14)
- Status: Accepted
- Priority: High
- Trigger: Verified defect — end-to-end validation against real 2h02m / 30.2GB classroom media
  rejected the complete transcription at the §14 admission boundary
- Created: 2026-08-03
- Target Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` (§14 A-10 amended; §14 Canonical Invariants
  item (10) amended)

---

## Status

Accepted. This PATCH amends one Confirmed Product decision (`040 §14` A-10) and **requires a
corresponding implementation slice** at the §14 admission boundary. It introduces no schema change,
no migration, no new record, no new identity, no repository, and no CLI. The SQLite schema remains
**v53**. It changes no other section, and `040 §15` L-6 is explicitly left untouched.

## Context

`PATCH-0021` fixed the provider-neutral admission boundary and stated A-10 as an exact inequality
over the submitted values:

> segment는 `start` 비내림차순으로 제출되어야 하고 겹치지 않아야 한다
> (`segment[i].end <= segment[i+1].start`; 경계가 맞닿는 것은 허용).

`PATCH-0022` then added the first concrete local ASR adapter (`040 §15`) and bound it by L-6:

> 반환된 segment는 순서·**시간**·text를 그대로 보존하고

Together these two Confirmed decisions leave no implementation-level resolution for the defect
below: §14 requires an exact inequality over submitted values, and §15 forbids the adapter from
adjusting the values it submits. The contradiction is a Blueprint-level question, which is why it is
resolved here rather than in code.

## Trigger — verified defect

Validation ran the released pipeline against real classroom media: `7355.85 s` (2h02m36s),
`32,391,572,455` bytes, `faster-whisper` `large-v3`, `language=ko`, CPU `int8`. The engine produced
**2564 segments** in 85.5 minutes. `lectureos.local_asr_cli` then exited `1` with:

```text
local ASR engine produced inadmissible output: segments must be ordered by start and must not overlap
```

Three adjacent boundaries were responsible. All three have the identical shape:

```text
segment[1082].end   = 3129.1000000000004      segment[1083].start = 3129.1
segment[1221].end   = 3390.6400000000003      segment[1222].start = 3390.64
segment[1384].end   = 4021.9600000000005      segment[1385].start = 4021.96
delta = -4.547473508864641e-13 (identical at all three)
```

Each pair denotes **one instant**. The engine derives a segment's `end` and the next segment's
`start` through different floating-point paths (`chunk_offset + tick × 0.02`), and the results
differ in the last representable bits. No segment overlaps in the sense A-10 exists to prevent.

The defect is **scale-dependent, not incidental**. Of this result's 2563 adjacent boundaries,
**2257 (88%)** are within `1e-6 s` of touching; three of them landed on the rejecting side of an
exact comparison. The released M1 validation passed only because a 96-second result has 37
boundaries. As media length grows, rejection approaches certainty, and the failure consumes the full
transcription cost before it is detected.

## Decision

**T-1 (Confirmed) — A-10 compares instants, not representations.** The non-overlap rule expresses a
statement about time: a segment must not begin before the previous segment ended. Two boundary
values that differ only by floating-point representation noise denote the same instant and are
therefore **touching**, which A-10 already admits. The prior wording expressed this as an exact
inequality over submitted values; that wording did not contemplate binary floating-point
representation and is amended here.

**T-2 (Confirmed) — Representation tolerance.** Adjacency is admitted when
`segment[i+1].start >= segment[i].end - ε`, with `ε = 1e-6` seconds (one microsecond), declared as a
single named constant at the §14 boundary. A gap larger than `ε` on the rejecting side remains a
real overlap and is rejected unchanged.

**T-3 (Confirmed) — ε is confined to the adjacency comparison.** A-10's per-segment rules are
unchanged and remain exact: `start >= 0`, and `end > start` with zero-length spans rejected. A
segment must still have strictly positive length; `ε` never admits a degenerate segment, and it
never applies within a segment.

**T-4 (Confirmed) — Tolerance governs admission, never mutation.** No submitted timestamp is
snapped, rounded, quantized, or rewritten at any boundary. The values are persisted exactly as
submitted. A-4 (provider evidence preserved un-normalized), A-11 (text preserved exactly), and
`§15` L-6 (the adapter preserves the engine's order, timing, and text verbatim) are unchanged and
are **not** re-scoped by this PATCH.

**T-5 (Confirmed) — Identity and idempotency are unchanged.** `content_fingerprint` is computed over
the submitted values, so two documents differing only by representation noise remain **distinct**
payloads. A-6 (deterministic identity), A-8 (content idempotency), and A-9 (same anchor, different
payload is a conflict) hold exactly as before. `ε` participates in no identity, fingerprint, or
anchor.

**T-6 (Confirmed) — Magnitude rationale.** `ε` must sit far above float64 representation noise at
realistic media durations and far below any meaningful timing distinction:

| quantity | magnitude |
|---|---|
| observed discrepancy | `4.5e-13 s` |
| float64 ULP at `t ≈ 7355 s` | `~1.8e-12 s` |
| float64 ULP at `t ≈ 36000 s` (10h) | `~7.3e-12 s` |
| **ε** | **`1e-6 s`** |
| SRT serialization grid (`041` canonical serializer) | `1e-3 s` |
| Whisper timestamp grid | `2e-2 s` |

`ε` is ~5 orders of magnitude above representation noise even for ten-hour media, and ~3 orders
below the millisecond grid that the released SRT serializer rounds to. A real overlap large enough
to change any downstream artifact is therefore never admitted by `ε`.

**T-7 (Confirmed) — Scope.** This decision governs `040 §14` only. The legacy execution-coupled
subtitle structural validation (`041 §9.2`, `RULE_OVERLAP_ADJACENT`) belongs to a different contract
generation, is not on the effective-transcript path, and is **not** re-scoped, amended, or denied
here. Whether it needs the same treatment is left to its own gate evaluation.

## Non-goals

This PATCH does not address, and must not be read as approving:

- **Incremental persistence of engine output.** `§15` L-10 keeps the adapter from writing anything
  before a valid result is admitted, so a rejection still discards the full transcription. That cost
  is real and was observed (85.5 minutes lost), but changing it touches L-10's failure-atomicity
  guarantee and requires its own gate evaluation.
- **ASR engine parameters.** The observed hallucination and repetition on silent regions
  (`vad_filter` unset, `condition_on_previous_text` at library default) is an `§15` engine-invocation
  question, not an admission-boundary question.
- **Provider output hygiene.** Replacement characters (`U+FFFD`) present in engine output are
  preserved verbatim under A-11 and reach downstream artifacts. Introducing any sanitization point
  would contradict A-11 and is not proposed.
- Any schema change, migration, new record, new identity, or new validation code.

## Consequences

- `040 §14` A-10 and Canonical Invariant (10) are amended to state the tolerance.
- One implementation slice at the §14 admission boundary realizes T-2 and T-3.
- The released `local_asr_cli` path becomes usable for full-length lecture media without changing
  `§15`, any adapter, any engine, or any downstream contract.
- Previously admitted results are unaffected: the change only widens what is admissible, so every
  document admissible before remains admissible, with identical identities and fingerprints.
