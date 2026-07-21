# LectureOS Codex Goal — Concrete Transcript Correction Provider

## 1. Mission

이 Goal은 완료된 Transcript Correction Application Foundation 위에 첫 production
acceptance용 concrete provider adapter 하나를 구현한다. 선택 provider는 OpenAI Responses
API의 `gpt-5.6-terra`이며, adapter는 기존 Application-owned
`CorrectionGenerationPort`만 구현한다.

완료 흐름:

```text
canonical Korean Transcript context
→ OpenAI Responses request translation
→ strict JSON Schema response
→ provider-neutral CorrectionProposal tuple
→ existing Application validation/construction
→ existing atomic canonical persistence
→ existing structural Validation
→ restart reconstruction
```

## 2. Authority and Baseline

Authority order는 Released Blueprint, active PATCH, approved Goals, Domain/Application
contracts, implementation 순이다. 실행 시 `AGENTS.md`, `docs/031_ARCHITECTURE.md`,
`docs/040_TRANSCRIPT_PIPELINE.md`, `docs/050_PLUGIN_SYSTEM.md`, PATCH-0005,
`implementation/050_IMPLEMENTATION_WORKFLOW.md`, `implementation/060_IMPLEMENTATION_STATUS.md`,
완료된 Correction Application Goal과 현재 `CorrectionGenerationPort`를 확인한다.

Goal 시작 baseline:

```text
HEAD e514c30e191cf500b58b44a17a41d044782988bf
Branch main
Working Tree Clean
```

## 3. Bounded Provider Decision

### 3.1 Compared providers

- OpenAI Responses API: strict JSON Schema structured outputs, multilingual current models,
  existing repository `OPENAI_API_KEY` convention과 credentialed Whisper acceptance 경험,
  dependency-free REST implementation 가능.
- Anthropic Messages API: Korean correction에 적합한 general model과 API가 있으나 새
  credential convention과 provider dependency를 추가하고 기존 repository acceptance
  자산을 재사용하지 못한다.
- Gemini API: JSON Schema structured output과 낮은 비용 선택지가 있으나 새 credential,
  endpoint/SDK convention과 별도 privacy configuration을 도입한다.

### 3.2 Selected provider and model

OpenAI Responses API와 `gpt-5.6-terra`를 선택한다. 이는 provider superiority에 대한
product contract가 아니라 첫 adapter를 위한 bounded implementation Architect Decision이다.
Terra는 current OpenAI model catalog에서 intelligence/cost balance 모델이며 Responses와
Structured Outputs를 지원한다. Korean suitability는 credentialed acceptance에서 검증하며
production quality 승인을 의미하지 않는다.

공식 근거:

- `https://developers.openai.com/api/docs/guides/structured-outputs`
- `https://developers.openai.com/api/docs/models/compare`
- `https://developers.openai.com/api/docs/guides/your-data`

Privacy boundary는 API 입력/출력이 기본적으로 training에 사용되지 않지만 abuse-monitoring
logs가 최대 30일 보존될 수 있음을 전제로 한다. adapter는 `store: false`를 전송하고,
credentialed acceptance에는 비민감 synthetic Korean text만 사용한다.

## 4. Scope

Included:

- `OpenAITranscriptCorrectionAdapter` 하나
- existing `CorrectionGenerationPort` 구현
- `CorrectionGenerationRequest` → Responses API request translation
- strict JSON Schema response format
- deterministic response extraction와 strict neutral proposal parsing
- API key environment configuration without logging/persistence
- bounded timeout
- HTTP, timeout, malformed/refusal/incomplete response → `CorrectionGenerationFailure`
- injected transport를 사용한 no-network unit tests
- one explicit synthetic Korean credentialed acceptance command
- existing canonical persistence/Validation/restart flow acceptance

Excluded:

- `CorrectionGenerationPort` 또는 canonical Domain meaning 변경
- provider-controlled canonical identities
- multiple providers, registry, plugin runtime, selection/fallback/retry
- prompt-management framework 또는 prompt optimization milestone
- Review, Human Decision, applicability/current selection
- Subtitle, Artifact, Diagnostic, Lecture Intelligence, long-media
- credential, raw provider payload, sensitive transcript commit

## 5. Responsibility Boundary

Adapter owns request/response translation only. Application continues to own proposal
semantic validation, canonical identities, Candidate/Revision construction, provenance,
Validation invocation, persistence, lifecycle와 failure boundary. Provider output remains
non-canonical.

## 6. Request Contract

The adapter sends:

- endpoint `https://api.openai.com/v1/responses`
- model `gpt-5.6-terra`
- `store: false`
- one bounded system instruction and one deterministic JSON user context
- strict `text.format` JSON Schema
- timeout supplied at construction
- bearer credential from explicit argument or `OPENAI_API_KEY`

No repository, canonical identity, Review authority or hidden context is sent. Segment
identity is serialized only as the opaque target reference needed to map proposals.

## 7. Response Contract

Schema root is an object containing ordered `proposals`. Each item contains exactly:

- `target_segment_id`
- `proposed_text`
- `rationale`
- `evidence` string array
- nullable `confidence`
- nullable `uncertainty`

Unknown keys, wrong types, missing output text, refusal, incomplete response, invalid JSON,
non-finite numbers or unknown target identities fail explicitly. The adapter never repairs,
deduplicates or silently drops malformed proposals.

## 8. Credential and Privacy Policy

- never print or persist `OPENAI_API_KEY`
- never include credential in exception text
- no `.env` creation or credential fixture
- acceptance checks presence only
- no raw response logging or persistence
- synthetic non-sensitive Korean acceptance text only
- `store: false`
- one paid call unless inconclusive

## 9. Slice Sequence

### Slice 1 — Provider Decision and Goal Baseline

Record this bounded decision and status. Review: Optional — Skipped. Commit:

```text
docs: add concrete transcript correction provider goal
```

### Slice 2 — OpenAI Correction Adapter

Implement dependency-free transport, strict schema, parsing, credential/timeout/error mapping,
exports and focused no-network tests. Review: Required — Executed. Commit:

```text
feat: add openai transcript correction adapter
```

### Slice 3 — Credentialed Korean Acceptance

Add the narrow acceptance CLI/module, synthetic Korean test path, full SQLite composition and
restart verification. Run one real request when credential exists. No product feature beyond
acceptance harness. Review: Required only if production boundary changes; otherwise Optional —
Skipped. Commit:

```text
test: verify openai transcript correction acceptance
```

## 10. Validation

Every slice runs focused tests, complete unittest suite, compileall, tabnanny,
`git diff --check`, and staged diff check. Required review follows AGENTS.md critical-only
policy: one bounded 6-turn staged-diff review; only unresolved verified critical defects block.

Acceptance must prove:

- actual network request and actual provider response
- selected model and strict structured output
- recognizably Korean correction proposal or explicit zero proposal
- existing Application canonical construction
- atomic persistence and structural Validation
- restart reconstruction
- no credential/payload/sensitive content committed

## 11. Stop Conditions

Stop only for:

- verified Blueprint or responsibility contradiction
- existing port cannot represent the response without Domain/Application change
- unresolved critical privacy/security/public-contract/identity/provenance defect
- credential absent at credentialed acceptance
- provider access/model/endpoint failure that is not an implementation defect
- required Architect Decision, Blueprint Clarification or PATCH
- tests cannot be corrected within scope
- unrelated repository changes overlap

Missing reviewer verdict alone is not a Stop Condition.

## 12. Goal Self-Maintenance

After each slice update this Goal and `implementation/060_IMPLEMENTATION_STATUS.md`, record
commit/review/validation evidence, remove completed slices from Remaining, identify the exact
next slice, commit once and require a clean Working Tree.

### Completed Capabilities

```text
Slice 1 — Provider Decision and Goal Baseline
- commit `c00dc3f` — `docs: add concrete transcript correction provider goal`
- OpenAI Responses API selected
- model gpt-5.6-terra selected
- dependency-free REST and OPENAI_API_KEY convention approved
- privacy boundary and strict-output contract recorded

Slice 2 — OpenAI Correction Adapter
- commit `d18b168` — `feat: add openai transcript correction adapter`
- dependency-free `OpenAITranscriptCorrectionAdapter`
- Responses API `gpt-5.6-terra`, `store:false`, strict JSON Schema request
- deterministic ordered neutral proposal parsing
- credential, timeout, refusal, incomplete, malformed and transport failure mapping
- no-network injected-transport tests
- Required Claude Review: Inconclusive — no critical findings identified
  (one bounded 6-turn review; no concrete critical issue reported)

Slice 3 — Credentialed Korean Acceptance
- dependency-free synthetic Korean acceptance module implemented
- fake transport exercises canonical Candidate/Revision/Result persistence and restart
- focused acceptance test passed; complete suite 670 passed
- credentialed OpenAI request succeeded outside Codex with one proposal
- provider `openai:gpt-5.6-terra`; structural Validation and canonical restart verified
- no credential, raw provider payload or sensitive Transcript committed
- no additional paid request made during resume
- Claude Review: Optional — Skipped (acceptance harness/test only; no production contract change)
```

### Remaining Milestones

```text
None — Goal complete
```

### Immediate Next Slice

```text
Goal Complete
```

## 13. Consolidated Completion Report

Return:

```text
## Summary
## Repository Status
## Provider Decision
## Files Changed
## Adapter Contract
## Request Translation
## Response Parsing
## Credential and Privacy
## Failure Mapping
## Canonical Pipeline Acceptance
## Credentialed Korean Acceptance
## Tests and Validation
## Claude Reviews
## Completed Commits
## Scope Confirmation
## Product Milestone Impact
## Deferred Capabilities
## Open Questions
## Final Verdict
```

End with:

```text
Requires Architect Decision: Yes/No
Requires Blueprint Clarification: Yes/No
Requires Blueprint PATCH: Yes/No
```
