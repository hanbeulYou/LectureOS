# PATCH-0043

- Title: Effective Subtitle Readability Parameter Set v2 (041 §16 R-10)
- Status: Proposed
- Priority: Medium
- Trigger: Product Owner decision on the v1 blocking cases recorded in
  `implementation/124_READABLE_SUBTITLE_CUE_COMPOSITION.md`, verified by scratch diagnostic over the
  preserved 2,564-segment fixture
- Created: 2026-08-07
- Target Blueprint: `docs/041_SUBTITLE_PIPELINE.md` (§16 R-10 gains a v2 table and a default-version
  statement; header amended)

---

## Status

**Proposed.** This document exists; `docs/041_SUBTITLE_PIPELINE.md` has not yet been amended.

Scope is **one parameter version addition**. It designs no readability policy, changes no rule, and
touches no other decision: R-1…R-9, R-11…R-14, L-1…L-5 and EN-1…EN-11 are unchanged, as are the
generator algorithm, the split trigger and priority, the serializer, the schema, and every released
record.

## Context

`PATCH-0041` R-10 fixed the readability parameter set at version 1 and stated that changing any value
produces a new parameter version rather than mutating an existing Candidate. `PATCH-0042` made Final
Selection admission enforce blocking findings under **the Candidate's own** parameter version. The
mechanism for a second version therefore already exists; what does not exist is a second version.

Full-length validation left three cues blocking out of 2,574 (0.12 %), all
`READABILITY_LINE_TOO_LONG`. The cause is arithmetic, not algorithmic: with
`maximum_cue_characters = 44` and `maximum_line_characters = 22`, a 42–43 character cue must break
within a two-character window for both lines to conform, and natural Korean word boundaries rarely
fall there.

The diagnostic makes this concrete. For cue `#95` (42 characters) eleven admissible break points
exist and the closest are `18/23`, `24/17` and `24/17` — every one has a side above 22. Cue `#1272`
(42 characters, fourteen break points) and `#1747` (43 characters, ten break points) fail the same
way at `17/24`, `24/17` and `19/23`, `23/19`.

## Product Owner decision

One value changes:

```text
maximum_line_characters:  22 → 24
```

Everything else is held: hard minimum `0.100 s`, target minimum `1.000 s`, maximum `7.000 s`,
maximum lines `2`, **maximum cue characters `44`**, CPS warning `> 12`.

The intent is explicitly **not** to admit denser cues. The per-cue product ceiling of 44 characters
is unchanged, so no cue may carry more text than v1 allows. What is added is **line-layout slack**:
room to place an already-admissible 44-character cue across two lines at a natural Korean word
boundary instead of refusing it because no boundary lands in a two-character window.

## Diagnostic evidence

Composed from the preserved 2,564-segment fixture with the identical generator algorithm, varying
only the parameter set:

| measurement | v1 | v2 |
|---|---|---|
| output cues | 2,574 | 2,574 |
| **blocking findings** | **3** | **0** |
| warnings | 91 | 88 |
| one-line cues | 2,106 | 2,217 |
| two-line cues | 468 | 357 |
| three or more lines | 0 | 0 |
| cues over 44 characters | 0 | 0 |
| lines over the version's line maximum | 0 | 0 |
| cues under 100 ms | 0 | 0 |
| cues over 7 s | 3 | 3 |
| overlapping cues | 0 | 0 |
| text recovery | exact | exact |
| lineage preserved | yes | yes |

All three previously blocking cues compose into two conforming lines — `24/17`, `24/17`, `19/23` —
with text recovered exactly and timing unchanged. The three lost warnings are the
`READABILITY_LINE_COMPOSITION_UNAVAILABLE` diagnostics for those same cues.

**Timing, lineage and cue count are bit-identical between the two versions**; only line composition
differs, on 132 cues (5.1 %). This is expected and bounded: the parameter governs line placement
only, and no split trigger, merge rule, or timing rule reads it.

The rise in one-line cues from 2,106 to 2,217 is the direct consequence of the same change — a 23–24
character cue now fits one conforming line instead of being composed as two. It admits no additional
text.

## Decision

**PV-1 (Confirmed) — v1 is preserved permanently.** Parameter set version 1 remains a released,
supported version. Its values are not edited, reinterpreted, deprecated, or removed. Every existing
v1 Candidate keeps its identity, its cues, its line composition, and its validation outcome.

**PV-2 (Confirmed) — Parameter set version 2.**

| parameter | v1 | **v2** |
|---|---|---|
| hard minimum display duration | `0.100초` | `0.100초` |
| target minimum display duration | `1.000초` | `1.000초` |
| maximum display duration | `7.000초` | `7.000초` |
| **maximum characters per line** | `22` | **`24`** |
| maximum lines per cue | `2` | `2` |
| **maximum characters per cue** | `44` | **`44`** |
| CPS warning threshold | `> 12` | `> 12` |

Exactly one value differs. The per-cue ceiling is deliberately **not** raised in step with the line
ceiling: `2 × 24 = 48` is not the new cue maximum, and a cue over 44 characters remains blocking
under both versions.

**PV-3 (Confirmed) — Identity uses the released mechanism.** The parameter version already
participates in Candidate identity through `§15` E7 and `§16` R-13. A v2 Candidate therefore derives
a **different identity** from the v1 Candidate for the same binding, and the two coexist as competing
Candidates exactly as R-3 already permits. No new identity mechanism, aggregate, authority, or
lifecycle is introduced.

**PV-4 (Confirmed) — v1 Candidates are never re-validated under v2.** `§16` EN-4 already requires
validation to be re-derived under the Candidate's own parameter version, and that requirement is
what makes this addition safe. A released v1 Candidate is evaluated under v1 forever; introducing v2
does not re-open, re-judge, or re-classify it. An unknown parameter version still refuses rather than
falling back.

**PV-5 (Confirmed) — New readable generation produces v2.** From this contract onward, the readable
generator's default parameter set is **v2**. This is stated here because `§16` R-10 fixed the values
of version 1 without stating which version new generation uses, so the switch is a product statement
rather than an implementation choice. Generating a v1 Candidate remains possible in principle — v1 is
a supported version — but is not the default and requires no new interface.

**PV-6 (Confirmed) — Released records are untouched.** No existing Candidate, Review Subject, Review
Decision, Final Selection, SRT Artifact, materialization, delivery, or publication is rewritten,
invalidated, re-derived, superseded, or regenerated. Adding a version creates the possibility of new
Candidates; it changes nothing that exists. Nothing is auto-regenerated at v2.

**PV-7 (Confirmed) — Nothing else changes.** The generator algorithm, split trigger and priority,
merge rule, timing extension, timing interpolation, line-break grammar, validation codes and their
severities, the enforcement boundary, the canonical SRT serializer, and the schema are all unchanged.
The three cues that remain over seven seconds stay warnings under both versions.

## Non-goals

Not decided and each requiring its own gate evaluation: any change to `maximum_cue_characters`, the
duration thresholds, the CPS threshold, the split trigger or priority, the merge rule, or the
line-break grammar; a parameter version v3; semantic merge; a Review comparison interface;
format-specific line wrapping; and every item already deferred by `§16`.

## Required Blueprint Changes

Applied to `docs/041_SUBTITLE_PIPELINE.md` only.

1. **Header** — Blueprint version and Last Updated advanced; `PATCH-0043` added to `Amended By`.
2. **§16 R-10** — the released v1 table and its surrounding text are **kept verbatim**; a follow-up
   note adds the v2 table, states that exactly one value differs, states that `44` is deliberately
   not raised to `48`, records the diagnostic result, and declares v2 the default for new generation
   (PV-1…PV-7).

No other section changes. R-13 and EN-4 already carry the identity and re-validation rules this
addition relies on, and neither needs amending.

## PATCH Acceptance Criteria

Verified against the Blueprint amendment, before this PATCH may be marked `Accepted`.

- [ ] §16 R-10 carries the v2 table with `maximum_line_characters = 24` and every other value equal
      to v1.
- [ ] The released v1 table and R-10's surrounding text are present verbatim.
- [ ] `maximum_cue_characters = 44` is stated unchanged for both versions.
- [ ] v1 is stated permanently preserved and v1 Candidates stated never re-validated under v2.
- [ ] The default for new readable generation is stated as v2.
- [ ] Released records are stated untouched and nothing is auto-regenerated.
- [ ] No other §16 decision, and no other section, is modified.
- [ ] The change set contains no implementation, schema, migration, or test change.

## Implementation Requirements

Required validation for the implementing milestone. **Not satisfied by this PATCH.**

1. v2 exists as an additive parameter set; the v1 constant and its fingerprint are unchanged.
2. Version dispatch resolves v1 → v1 values and v2 → v2 values, with no fallback for either.
3. A v1 Candidate's identity is unchanged by v2's existence.
4. A v2 Candidate derives a different identity from the v1 Candidate for the same binding.
5. New readable generation defaults to v2.
6. Over the real fixture, a v2 Candidate has zero blocking findings and the three v1 blockers are
   resolved; no new blocking finding appears.
7. Final Selection admits the v2 Candidate and still refuses the v1 Candidate.
8. A warning-only v2 Candidate is selectable (EN-6).
9. SRT generated from the v2 Final Selection carries at most two lines, no line over 24 characters,
   no cue over 44, no sub-100 ms cue, no overlap, and recovers its text.
10. The serializer, the schema, and every released record are unchanged.
11. The complete test suite passes.

## Consequences

- `§16` R-10 gains a v2 table and a default-version statement; nothing else in the Blueprint moves.
- One implementation slice adds the parameter set and switches the generation default. No schema
  change is expected.
- The readable Candidate produced during validation stays un-selectable at v1 forever, which is
  correct: it was composed under v1 and EN-4 judges it under v1. A **new** v2 Candidate for the same
  binding is selectable, and both coexist under R-3.
