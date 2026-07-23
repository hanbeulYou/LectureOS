# PATCH-0013

- Title: Concrete Edit Candidate Generation Provider — First Slice (042)
- Status: Completed
- Priority: Medium
- Trigger: Architect / Product Owner Decision (Concrete Edit Candidate Generation Provider investigation, D-1…D-15)
- Created: 2026-07-23
- Target Blueprint: `docs/042_LECTURE_INTELLIGENCE_PIPELINE.md`

---

## Status

Completed. Product policy/clarification only; no schema, code, Application Foundation change, Review behavior, or Goal.

## Trigger

An architecture-first investigation of the **Concrete Edit Candidate Generation Provider** — the provider
stage that produces normalized input for the already-completed Edit Candidate Application Foundation (§9.1) —
concluded that implementation is not safe without an Architect Decision (Candidate Type space, provider
input/context and privacy, zero-candidate representation, prompt/model ownership, provider-output persistence
and replay, evaluation). The Product Owner approved the minimal decision (D-1…D-15) authorizing one small,
testable first slice. This PATCH promotes that decision into the canonical Blueprint.

## Context

The Edit Candidate Application Foundation (§9.1, PATCH-0012) admits an already-normalized, provider-independent
Candidate result and persists immutable, insert-only Edit Candidate records; it performs no provider
invocation. The concrete provider that produces that normalized result was explicitly deferred there and in
§18 as "a separate later milestone" following the `040` Application-Foundation → Concrete-Provider precedent.
This PATCH authorizes only that first provider slice and **leaves the §9.1 contract entirely unchanged.**

## Findings

- **F-01 — Candidate Type was the pivot blocker.** §9.1 requires the provider to map into an Application-owned
  Candidate Type, but the key space/registry/ownership were undefined; implementing a provider first would let
  the prompt or adapter silently decide a product taxonomy (§1 Excluded, §18). Resolved by a small,
  Application/generation-owned, closed first-slice registry.
- **F-02 — A real provider crosses an undefined external-data boundary.** Sending transcript/PII to an external
  model is the §18 Requires-Validation "외부 맥락과 개인정보 허용 범위" question and the 050 §7 trust boundary.
  Resolved by a conservative, explicitly incomplete first-slice egress boundary.
- **F-03 — Replay for an AI stage needed a truthful contract.** A live model is non-deterministic; the
  admitted Candidates are the durable normalized result and reprocessing is insert-only, so no raw-response
  persistence foundation is required, but "replay" must mean fake-Port + durable-record reconstruction, not
  live re-invocation.

## Decision Basis (Confirmed D-1…D-15)

Recorded as `042 §9.2`:

- **D-1 Purpose / D-2 Invocation & No-Candidate:** provider-neutral generation Port + one concrete adapter +
  deterministic fake + a generation/orchestration layer invoking §9.1 admission; one Analysis Finding per
  invocation; advisory generation only (no ranking/priority/risk/confidence/Review judgment/apply/delete);
  transport-order only. A **generation outcome distinct from `NormalizedCandidateResult`** carries
  zero/one/many; zero ⇒ **no admission call**, preserving §9.1's empty-batch rejection unchanged; no
  multi-Finding invocation.
- **D-3/D-4 Candidate Type registry & meanings:** an Application/generation-owned **closed first-slice
  registry** of exactly `non_lecture_region`, `redundant_restatement`, `delivery_concern`, additively
  extensible only by later decision; the canonical Candidate Type field **remains an open key** and is not
  redefined as a global closed enum; provider values are validated against the registry; unknown values are
  rejected (never coerced, no aliases); each key has a fixed advisory meaning, required grounding, and
  prohibited implications (never a deletion command, value determination, executable operation, or Review
  decision).
- **D-5 Input contract:** one invocation reads only Finding fields + the corrected-transcript excerpt/segments
  overlapping the Finding range + a fixed bounded surrounding window; no whole transcript, Lecture Segments,
  prior Candidates, Review history, Source Media bytes, file paths, or unnecessary identifiers; upstream
  read-only; no Lecture Segment reference enters generation/normalized/canonical layers; a Finding without
  usable located context yields no Candidate.
- **D-6 External data-egress:** transcript excerpt + Finding Type/evidence + minimum timing only; no media
  bytes/file paths/Review history/unrelated context/identifiers/secrets; PII not deliberately added;
  redaction/retention/regional/legal policy **deferred**; provider training/data-use disabled where
  supported; secrets outside records and unlogged; raw bodies not persisted and their logging restricted; a
  conservative **system boundary only**, not a compliance policy.
- **D-7 Range generation:** one located range grounded in supplied context; may narrow, not broaden; no
  whole-recording or non-located generation; **Foundation range validation unchanged** (real/finite/
  non-negative/`start <= end`; zero-duration structurally valid); adapter prefers non-degenerate ranges as a
  non-canonical preference; canonical time unit reused; no media-duration/boundary/containment validation
  added to the Foundation.
- **D-8 Rationale mapping:** adapter-level sanitization into a human-reviewable, grounded canonical rationale;
  no raw explanation/chain-of-thought/executable command/Review content; no new canonical enrichment fields.
- **D-9/D-10 Port & prompt ownership:** provider-neutral Port; adapter owns request/invocation/strict-schema/
  parsing/failure-translation/mapping and never writes canonical records or returns raw JSON; generation
  service owns registry application, outcome classification, normalized mapping, identity planning, and
  admission; prompt is source-controlled, versioned, adapter-owned implementation content (wording not in the
  Blueprint); provider/model/prompt/schema versions and secrets live in execution/adapter configuration, not
  the record; model/prompt change ⇒ new UnitExecution/attempt.
- **D-11 Structured output & partial normalization:** strict structured output parsed inside the adapter;
  malformed top-level ⇒ no admission + explicit failure; mixed valid/invalid ⇒ **explicit partial-success
  outcome** (valid proceed, invalid rejected and surfaced, never silent loss, never canonical fields, no raw
  persistence); no automatic repair.
- **D-12 Failure/retry:** provider/transport failures use the existing provider/plugin failure category;
  normalization/admission failures owned by existing boundaries; retry owned by orchestration/execution, each
  retry a new attempt via existing `retry_of` provenance; no hidden retries; no in-place repair.
- **D-13 Execution provenance & replay:** provider/model/prompt/config provenance stays outside the record via
  the existing execution model; **no provider-result persistence foundation required first**; raw responses
  not persisted; replay = fake-Port deterministic pipeline + durable-record reconstruction; live invocation is
  not replay-safe; a live rerun is new insert-only reprocessing.
- **D-14 Duplicate/reprocessing:** insert-only; no overwrite/revision/supersession/stale/current-selection/
  reconciliation/dedup; exact intra-response duplicates preserved as distinct Candidates; transport order only.
- **D-15 Acceptance:** three tiers — deterministic fake-Port architectural acceptance (default suite),
  concrete-adapter tests via injected transport (default suite), optional/manual credentialed live tests
  (outside the suite, non-replay-safe); **product-quality evaluation deferred**; milestone is
  integration-complete, not production-quality approved; no invented numeric thresholds.

## Expected Blueprint Changes

- New normative `042 §9.2` recording the D-1…D-15 provider-generation contract; a `§18` confirming note; the
  header amended to Blueprint 0.6 / PATCH-0013.
- One minimal cross-reference in `050_PLUGIN_SYSTEM.md §7` (external-provider trust boundary) pointing to
  `042 §9.2` for the conservative first-slice egress boundary.

## Out of Scope

Any implementation, SQL, schema, migration, repository, execution code, adapter code, prompt wording, or Goal;
and every item in the §9.2 Deferred list (completed taxonomy/aliases, multiple providers/fallback/selection
policy, rich configuration binding, prompt-as-Artifact, whole-transcript/Lecture-Segment/Source-Media/
Review-history/prior-Candidate context, non-located and whole-recording generation, transcript-boundary/
media-duration validation, rationale templates/quotation/localization, confidence/uncertainty/priority/
severity/time-savings/structured evidence, raw-response/normalized-result/provider-attempt/content-hash
persistence, automatic repair, adapter-owned retries, duplicate reconciliation/supersession/stale/
current-selection/Review reconciliation, production-quality thresholds, human-evaluation protocol, and full
redaction/retention/regional/legal-compliance policy).

## Acceptance Criteria

- [x] The first provider slice is promoted to a confirmed normative contract (`§9.2`) with all D-1…D-15
  decisions represented, and §9.1 is not altered.
- [x] Provider-neutral Port + one concrete adapter + deterministic fake + generation/orchestration layer;
  one Finding per invocation; advisory-only; transport-order only.
- [x] zero/one/many + partial-success generation outcomes explicit; zero ⇒ no admission; §9.1 empty-batch
  rejection unchanged; no multi-Finding invocation.
- [x] Closed first-slice registry (`non_lecture_region`, `redundant_restatement`, `delivery_concern`),
  Application/generation-owned, additively extensible; canonical Candidate Type field remains an open key;
  unknown values rejected, no aliases; each key's advisory meaning/grounding/prohibited-implications fixed.
- [x] Input bounded to Finding fields + located excerpt + fixed window; conservative egress boundary; no
  Lecture Segment reference in any layer; PII risk acknowledged and deferred; conservative system boundary
  only (no compliance claim).
- [x] Provider-generated ranges grounded and bounded; Foundation range validation unchanged; canonical
  rationale sanitized/human-reviewable; no new canonical enrichment fields.
- [x] Adapter/Application separation fixed; prompt source-controlled/versioned/adapter-owned (wording absent);
  provider/model/prompt provenance in execution config, not the record.
- [x] Failure/retry via existing categories and `retry_of`; no hidden retries; no auto-repair.
- [x] Raw responses neither canonical nor persisted; replay = fake-Port + durable-record reconstruction; live
  invocation explicitly not replay-safe; no provider-result persistence foundation required first.
- [x] Insert-only reprocessing; intra-response duplicates preserved as distinct Candidates.
- [x] Three-tier acceptance defined; product-quality approval explicitly deferred; no invented thresholds.
- [x] No source or schema file changed; no canonical Foundation contract altered.

## Consistency Confirmation

Verified against the required checks: (1) the Candidate record stays provider-independent; (2) the canonical
Candidate Type field stays an **open key** — the three-key registry is a provider-generation constraint, not a
global closed enum; (3) the registry applies only to the first concrete generation milestone; (4) provider
ranges do not change Foundation validation; (5) a no-Candidate outcome creates no empty admission; (6)
partial success is explicit, not silent loss; (7) raw responses are neither canonical nor persisted; (8) live
invocation is not called deterministic replay; (9) execution provenance does not leak into Candidate fields;
(10) Review behavior remains absent (043 owns it); (11) the security boundary is narrow and claims no full
compliance. No contradiction with PATCH-0009/0010/0011/0012, §9.1, provider-independence, Human Authority,
no-overwrite/reprocessing, execution retry provenance, or Source Timeline traceability.

## Result

- Status: **Completed**
- Changed Blueprint Files: `docs/042_LECTURE_INTELLIGENCE_PIPELINE.md` (new §9.2; §18 confirming note; header
  amended). Cross-reference: `docs/050_PLUGIN_SYSTEM.md §7`.
- Notes: Records the Product Owner's approved D-1…D-15 decision for the first concrete provider slice; product
  policy/clarification only; no schema, code, Application Foundation change, Review behavior, or Goal. The
  next step is implementation of the first provider slice; all later provider/Review concerns remain deferred.

## Related Documents

- `PATCH-0010-analysis-finding-application-foundation.md`
- `PATCH-0011-lecture-segmentation-application-foundation.md`
- `PATCH-0012-edit-candidate-application-foundation.md`
- `../docs/042_LECTURE_INTELLIGENCE_PIPELINE.md`
- `../docs/050_PLUGIN_SYSTEM.md`
