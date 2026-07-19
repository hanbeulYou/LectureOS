# LectureOS Codex Goal — Transcript Correction Application Foundation

## 1. Mission

이 문서는 완료된 Durability Goal과 Canonical Transcript Foundation 이후,
Blueprint dependency order에 따라 provider-independent Transcript Correction
Application foundation을 구축하기 위한 장기 실행 Goal이다.

이 Goal의 목적은 특정 AI provider를 연결하거나 correction 품질을 시연하는 것이 아니다.
LectureOS가 canonical Raw Transcript와 선택적 correction context를 입력으로 받아 외부
Capability의 제안을 검증하고, canonical `CorrectionCandidate`와 proposed
`CorrectedTranscriptRevision`을 구성하며, structural Validation과 persistence를
Application 책임 아래 조율하는 계약을 완성하는 것이다.

Codex는 사용자가 각 slice마다 별도 prompt를 전달하지 않아도 다음 루프를 반복한다.

```text
현재 repository baseline 확인
→ 첫 번째 미완료 slice 선정
→ Blueprint와 active PATCH 확인
→ Architect Decision 필요 여부 판정
→ 한 개의 bounded slice 구현
→ focused tests와 전체 regression 실행
→ Risk-Based Claude Review 적용
→ 한 개의 logical commit 생성
→ Goal과 implementation status 동기화
→ Working Tree Clean 확인
→ 다음 slice로 계속
```

단, 이 문서의 Stop Conditions에 해당하면 즉시 중단하고 그 원인을 보고한다.

---

## 2. Blueprint and Contract Authority

구현 권위는 다음 순서를 따른다.

```text
Released Blueprint
→ Active approved PATCH documents
→ Approved Implementation Design
→ Architect Decisions recorded by this Goal
→ Domain/Application contracts
→ Persistence and adapter implementations
```

실행 전에 최소한 다음 문서를 읽는다.

```text
AGENTS.md

docs/000_MANIFESTO.md
docs/001_PRODUCT.md
docs/002_FAQ.md
docs/003_VISION.md
docs/004_PRINCIPLES.md
docs/020_PRODUCT_REQUIREMENTS.md
docs/021_SYSTEM_CONTEXT.md
docs/030_DATA_MODEL.md
docs/031_ARCHITECTURE.md
docs/040_TRANSCRIPT_PIPELINE.md
docs/043_REVIEW_PIPELINE.md
docs/050_PLUGIN_SYSTEM.md
docs/090_BLUEPRINT_RELEASE.md

patches/PATCH-0001-l0-and-prd-stabilization.md
patches/PATCH-0002-system-model.md
patches/PATCH-0003-text-pipeline.md
patches/PATCH-0004-edit-pipeline.md
patches/PATCH-0005-plugin-system.md

implementation/000_IMPLEMENTATION_DESIGN_GUIDE.md
implementation/020_STORAGE_MODEL.md
implementation/030_EXECUTION_MODEL.md
implementation/040_INTERFACE_CONTRACTS.md
implementation/050_IMPLEMENTATION_WORKFLOW.md
implementation/060_IMPLEMENTATION_STATUS.md
implementation/070_DIAGNOSTIC_PERSISTENCE_ASSESSMENT.md

docs/goals/LectureOS_Codex_Goal_Durability.md
docs/goals/LectureOS_Codex_Goal_Canonical_Transcript_Foundation.md
```

Blueprint의 Product meaning을 provider payload나 구현 편의를 위해 변경하지 않는다.
Blueprint가 호출 interface, DTO 또는 transaction shape를 정하지 않은 부분은 Slice 1의
Architect Decision으로 최소 정책을 정한다. 두 개 이상의 plausible interpretation이
CorrectionCandidate, revision, Validation 또는 Human Authority의 Domain meaning을
바꾸는 경우에는 Blueprint Clarification 또는 PATCH 없이는 구현하지 않는다.

---

## 3. Current Repository Baseline

이 Goal 작성 시점의 기준은 다음과 같다.

```text
Branch:
main

HEAD:
920edd28cd3b5e6560a53c33d9d91427544a1dc5

Commit:
test: verify canonical transcript persistence across restart

Working Tree:
Clean
```

Goal 실행을 시작하거나 재개할 때 반드시 다음을 확인한다.

```bash
git rev-parse HEAD
git branch --show-current
git status --short
```

실제 baseline이 다르면:

1. 현재 commit history와 working tree를 조사한다.
2. 이 Goal의 일부 slice가 이미 완료되었는지 확인한다.
3. 완료된 slice를 다시 구현하지 않는다.
4. Goal과 `implementation/060_IMPLEMENTATION_STATUS.md`를 실제 상태에 맞춘다.
5. 불일치가 안전하게 해석되지 않거나 unrelated changes가 겹치면 중단한다.

---

## 4. Blueprint Consistency and Milestone Boundary

### 4.1 Blueprint dependency position

`040_TRANSCRIPT_PIPELINE.md`는 다음 책임 순서를 정의한다.

```text
Raw Transcript Preservation
→ Correction Candidates
→ Corrected Transcript Revision
→ Structural Validation
→ Transcript Review Preparation
→ Human Decision Application
→ Transcript Ready State
```

Canonical Transcript Foundation은 Raw Transcript, Segment, Candidate, Revision과
lineage의 durable storage를 완료했다. 다음 미완료 제품 책임은 Correction Application
orchestration이다. 따라서 Review, Subtitle 또는 Artifact보다 먼저 이 foundation을
완료한다.

### 4.2 Contract-before-provider rule

`050_PLUGIN_SYSTEM.md`와 PATCH-0005는 다음 순서를 요구한다.

```text
Product
→ Application
→ Capability Contract
→ Provider
```

Capability는 Provider가 아니며 Plugin은 Pipeline이 아니다. provider-specific output은
LectureOS가 해석하고 검증하기 전 canonical Domain record가 아니다. 따라서 이 Goal은
Application-owned `CorrectionGenerationPort`를 먼저 정의하며 구체 provider adapter를
도입하지 않는다.

### 4.3 Milestone result

이 Goal이 완료되면 다음 흐름을 fake/in-memory provider로 검증할 수 있어야 한다.

```text
canonical Raw Transcript + optional correction context
→ Application correction request construction
→ CorrectionGenerationPort
→ provider-neutral proposals
→ proposal validation
→ canonical CorrectionCandidates
→ proposed CorrectedTranscriptRevision
→ structural Validation invocation
→ existing canonical Transcript persistence
→ process restart
→ exact candidate, revision and provenance reconstruction
```

이 흐름은 Human Approval이나 Transcript Ready State를 만들지 않는다.

---

## 5. Scope

### 5.1 Included capabilities

이 Goal은 다음만 포함한다.

- provider-independent Correction capability contract
- Application-owned `CorrectionGenerationPort`
- correction request와 허용된 context construction
- provider-neutral correction proposal DTO
- proposal representation 및 consistency validation
- canonical `CorrectionCandidate` construction
- proposed `CorrectedTranscriptRevision` construction
- existing structural Transcript Validation invocation
- uncertainty propagation
- capability, plugin-like opaque reference, execution과 source provenance propagation
- provider and persistence failure propagation
- existing canonical Transcript persistence와 atomic coordination
- process restart 이후 canonical correction record reconstruction
- in-memory 또는 fake provider acceptance
- top-level Application composition that remains provider-independent
- focused tests, regression validation and milestone acceptance
- implementation ordering, review policy, completion report와 Goal self-maintenance

### 5.2 Explicitly excluded capabilities

다음은 이 Goal에서 구현하지 않는다.

```text
OpenAI
Claude
Gemini
any concrete correction provider
prompt engineering
provider credentials
HTTP clients
network calls
provider registry
plugin runtime
multiple providers
automatic provider selection

Review Item creation
Review Decision persistence
Human Decision application
Transcript applicability or current selection
Transcript Ready State policy

Subtitle generation
Subtitle persistence
Artifact persistence
Diagnostic persistence
Lecture Intelligence
long-media runtime
unrelated Execution work
```

Structural Validation은 existing Application capability를 호출하는 경계까지만 포함한다.
새 canonical Validation schema/repository 또는 durable Review handoff가 필요하다고
판명되면 이 Goal에 임의로 추가하지 않고 Stop Condition으로 보고한다.

### 5.3 No provider framework

이 Goal은 provider를 선택, 발견, 설치 또는 실행하는 framework를 만들지 않는다.
fake provider는 port의 Application acceptance를 검증하기 위한 test double일 뿐 Plugin
runtime이나 provider registry의 시작점이 아니다.

---

## 6. Responsibility Boundary

### 6.1 Application owns

Application은 다음을 소유한다.

- correction orchestration
- canonical Raw Transcript와 revision input 선택
- correction request/context construction
- provider-neutral proposal validation
- canonical CorrectionCandidate construction
- proposed CorrectedTranscriptRevision construction
- structural Validation invocation
- persistence coordination
- command lifecycle와 exactly-once invocation
- identity source coordination
- provenance와 uncertainty propagation
- failure semantics와 false-success 방지

### 6.2 Capability contract owns

`CorrectionGenerationPort`는 다음만 표현한다.

- LectureOS Application이 correction proposal을 요청하는 provider-independent boundary
- 허용된 canonical input/context
- canonical record가 아닌 provider-neutral proposal result
- uncertainty와 provenance hints
- explicit failure propagation

Port는 SQLite, HTTP, provider SDK, credential, prompt 또는 concrete model을 알지 않는다.

### 6.3 Providers own

후속 concrete provider adapter가 소유할 수 있는 책임은 다음뿐이다.

- external request translation
- external response translation

이 Goal은 해당 adapter를 구현하지 않는다.

### 6.4 Providers never own

Provider 또는 fake provider는 다음을 소유하지 않는다.

- canonical Domain decisions
- CorrectionCandidate identity 또는 canonical construction
- structural Validation
- correction authority
- revision authority
- Human Approval
- persistence semantics
- transaction ownership
- current revision selection
- downstream readiness

Provider output shape에 맞추기 위해 Domain을 변경하지 않는다.

---

## 7. Slice 1 Architect Assessment

첫 implementation slice 전에 read-only assessment를 수행하고 decision을 이 Goal의
`Architecture Decision History`와 `implementation/060_IMPLEMENTATION_STATUS.md`에
기록한다. 별도 assessment 문서는 여기와 status에 합리적으로 기록할 수 없을 때만 만든다.

최소 결정 그룹:

### 7.1 Correction request boundary

결정할 항목:

- request가 참조하는 canonical Raw Transcript 또는 parent Revision
- Segment body와 identity를 전달하는 최소 representation
- Source Media/Timeline identity의 포함 범위
- execution, capability와 optional context provenance
- context가 canonical input을 복제하거나 변경하지 않는 규칙

### 7.2 Provider-neutral proposal shape

결정할 항목:

- proposal의 target Segment reference
- proposed text와 rationale
- evidence, confidence와 uncertainty
- replacement/split/merge 표현 중 현재 Domain이 실제 지원하는 최소 범위
- rejected or malformed proposal의 Application behavior

현재 Domain이 안전하게 표현하지 못하는 proposal 형태를 새 개념으로 임의 추가하지 않는다.

### 7.3 Identity ownership

결정할 항목:

- CorrectionCandidate identity source
- proposed Revision identity source
- new TranscriptSegment identity source
- DomainResult identity source
- provider가 canonical identity를 제공하거나 재사용하지 못하게 하는 경계

### 7.4 Generation cardinality and revision construction

결정할 항목:

- 한 request가 0, 1 또는 여러 proposals를 반환할 수 있는가
- valid proposal가 없을 때 Revision을 생성하는가
- 여러 proposals가 하나의 proposed Revision을 구성하는 최소 규칙
- conflicting proposals를 reject할지 command failure로 볼지
- provider ordering을 canonical ordering으로 그대로 신뢰하지 않는 규칙

### 7.5 Atomic persistence boundary

결정할 항목:

- 여러 new CorrectionCandidates
- genuinely new TranscriptSegments
- one proposed CorrectedTranscriptRevision
- 각 concrete record의 DomainResultReference

중 어떤 최소 record set이 한 Application command의 logical success인지 결정한다.
기존 단일 Candidate와 Revision persistence command를 순차 호출해 partial canonical state가
생길 수 있다면 새로운 command-specific Application port와 SQLite transaction boundary를
정의한다. Generic Unit of Work는 만들지 않는다.

### 7.6 Structural Validation boundary

결정할 항목:

- persistence 전 proposal representation validation
- canonical persistence 전후 existing structural Validation invocation ordering
- Validation failure가 command rejection인지 persisted proposed revision plus explicit
  validation outcome인지
- 이 Goal에서 Validation result durability 없이 restart-safe correction foundation을
  어떻게 정확히 표현할지

Validation은 의미 정확성, 자연스러움 또는 Human Approval을 판단하지 않는다.

### 7.7 Failure semantics

결정할 항목:

- provider failure와 malformed proposal의 Application error boundary
- zero-proposal success와 correction failure의 구분
- persistence collision/write/commit failure propagation
- existing Execution Failure command와의 관계
- 자동 retry 또는 fallback provider를 도입하지 않는 정책

### 7.8 Composition and testing boundary

결정할 항목:

- default in-memory/fake provider construction
- production composition이 concrete provider 없이 어떻게 explicit dependency를 요구하는가
- unit, Application integration, SQLite restart acceptance test ownership
- fake provider가 product behavior를 우회하지 않는 검증 방식

---

## 8. Application Contract Requirements

### 8.1 CorrectionGenerationPort

Port는 Application-owned protocol이어야 한다. 정확한 method와 DTO shape는 Slice 1이
결정하지만 다음 원칙을 만족한다.

```text
canonical Application request
→ CorrectionGenerationPort
→ provider-neutral proposal tuple or explicit failure
```

Port module은 다음을 import하지 않는다.

```text
sqlite3
SQLite concrete classes
HTTP client
provider SDK
OpenAI/Claude/Gemini types
credential configuration
```

### 8.2 Request and context

Application은 필요한 canonical records를 먼저 load하고 모든 context를 명시적으로
구성한다. Provider가 repository를 직접 조회하거나 hidden global context를 사용하지 않는다.

Context는 최소 권한 원칙을 따른다. Blueprint가 허용하지 않은 Source Media body,
credentials, private project context 또는 unrelated Transcript lineage를 전달하지 않는다.

### 8.3 Provider-neutral proposals

Proposal DTO는 external response나 canonical Domain model이 아니다.

```text
External provider response
≠ provider-neutral proposal
≠ CorrectionCandidate
≠ CorrectedTranscriptRevision
```

Proposal은 canonical construction에 필요한 최소 정보만 표현한다. Provider-specific
metadata blob, arbitrary JSON extension 또는 provider identity를 canonical authority로
사용하지 않는다.

### 8.4 Proposal validation

Application은 canonical construction 전에 최소한 다음을 검증한다.

- target identity가 requested Transcript lineage에 속하는가
- referenced Segment가 존재하는가
- proposed text와 rationale이 Domain requirements를 만족하는가
- evidence와 uncertainty representation이 유효한가
- duplicate/conflicting proposals가 approved command policy와 일치하는가
- provider가 Source Timeline structure를 임의 변경하지 않는가
- unsupported proposal shape가 명시적으로 거부되는가

Validation 실패를 provider output에 맞춰 조용히 보정하지 않는다.

### 8.5 Canonical construction

Application만 다음을 구성한다.

- `CorrectionCandidate`
- new or reused `TranscriptSegment` selection
- proposed `CorrectedTranscriptRevision`
- related `DomainResultReference`

기존 Domain constructors와 invariants를 사용한다. Provider proposal을 Domain object로
cast하거나 저장하지 않는다.

### 8.6 Structural Validation

Proposed Revision은 existing `TranscriptValidationService`의 구조 검사를 거친다.
검사 범위는 timeline traceability, ordering, missing references와 structural integrity다.

다음은 Validation 책임이 아니다.

- 의미 교정의 정답 판정
- 문장 자연스러움 승인
- Human Accept/Reject/Modify
- current revision 선택
- Subtitle readiness

### 8.7 Return and failure contract

Public Application result는 canonical records와 explicit validation/failure outcome을
provider-independent하게 표현해야 한다. Concrete provider payload, HTTP response 또는
SQLite DTO를 반환하지 않는다.

Provider, proposal validation 또는 persistence failure에서 false success를 반환하지 않는다.
자동 provider fallback, automatic retry 또는 replacement identity generation을 하지 않는다.

---

## 9. Provenance and Uncertainty

### 9.1 Required provenance continuity

모든 generated Candidate와 proposed Revision은 최소한 다음 계보를 설명할 수 있어야 한다.

```text
Source Media / Source Timeline
→ ProviderTranscriptResult / RawTranscript
→ optional parent CorrectedTranscriptRevision
→ CorrectionGenerationPort capability invocation
→ provider-neutral proposal
→ CorrectionCandidate
→ proposed CorrectedTranscriptRevision
→ DomainResultReference lineage
```

### 9.2 Provider provenance

이 Goal은 concrete provider identity를 정의하지 않는다. Existing `CapabilityReference`,
optional `PluginReference`, provider-reference string과 execution provenance 중 실제 현재
Domain이 지원하는 필드만 사용한다. 중복 canonical provider record나 generic metadata
storage를 만들지 않는다.

### 9.3 Uncertainty

Provider가 제공한 confidence 또는 uncertainty는 Application에서 validate하고 현재
Domain field가 허용하는 범위로 명시적으로 전달한다. 누락을 `0`, `False` 또는 확신으로
해석하지 않는다. Uncertainty는 자동 Reject, Approval 또는 Review Decision이 아니다.

### 9.4 Safe reprocessing

Correction generation을 다시 실행해도 기존 Candidate, Revision, Result reference 또는
future Human Decision을 overwrite하지 않는다. 새 identity와 lineage를 사용하며 기존
record는 immutable history로 보존한다.

이 Goal은 old/new candidate reconciliation 또는 current selection을 구현하지 않는다.

---

## 10. Atomic Coordination and Persistence

### 10.1 Existing foundation reuse

다음을 그대로 재사용한다.

- `SQLiteCorrectionCandidateRepository`
- `SQLiteCorrectedTranscriptRevisionRepository`
- `SQLiteTranscriptSegmentRepository`
- `SQLiteDomainResultReferenceRepository`
- existing non-committing canonical writers
- existing SQLite transaction/error conventions

Released schema v5를 변경하지 않는 방향을 우선한다.

### 10.2 Command-specific atomicity

Slice 1이 한 correction generation call을 하나의 logical command로 결정하면 그 command의
모든 new canonical records는 한 transaction으로 저장한다.

```text
Application computes final records
→ command persistence port
→ BEGIN IMMEDIATE
→ internal non-committing writes
→ representation linkage checks
→ COMMIT
```

어느 write나 commit이 실패해도 complete rollback한다. Public repository `save()`를 outer
transaction 안에서 호출하지 않는다.

### 10.3 Collision semantics

Candidate, Revision, Segment와 DomainResultReference의 immutable identity reuse는 existing
contract에 따라 collision이다. Identical duplicate를 idempotent success로 바꾸거나
provider가 새 identity를 재생성하게 하지 않는다.

### 10.4 Restart safety

성공 후 connection close/reopen 시 generated Candidate, proposed Revision, new Segment,
Result lineage와 ordering이 exact reconstruction되어야 한다. Structural Validation result가
durable하지 않은 현재 scope는 정확히 보고하며 승인 상태로 과장하지 않는다.

### 10.5 No schema expansion by default

현재 v5 shape가 approved command set을 정확히 저장할 수 있으면 schema/migration을
변경하지 않는다. 새 canonical request, proposal 또는 orchestration record가 필요하다는
결론이 나오면 구현을 중단하고 Architect/Blueprint 필요성을 판정한다.

---

## 11. Testing Strategy

### 11.1 Contract tests

- Application port has no provider or persistence dependency
- request/context contains only approved canonical inputs
- provider-neutral proposals cannot masquerade as Domain records
- fake provider receives exactly one request
- proposal ordering and duplicates follow approved policy
- malformed and unsupported proposals fail explicitly

### 11.2 Application orchestration tests

- canonical inputs are loaded before provider invocation
- lifecycle/provenance validation precedes first write
- canonical identities are Application-controlled
- exact Candidate fields are constructed
- exact proposed Revision and parent lineage are constructed
- uncertainty and provenance fields are preserved
- structural Validation is invoked at the approved point
- persistence port is invoked exactly once
- no legacy independent multi-record writes remain
- provider/persistence failures propagate without fallback

### 11.3 Atomic persistence tests

- complete approved record set commits together
- Candidate, Segment, Revision and Result collision paths roll back
- writer-stage and commit failures preserve previous state
- caller-owned connection remains open and reusable
- no nested public repository transaction occurs
- no partial correction generation is visible after failure

### 11.4 Structural Validation tests

- valid proposed Revision produces the current structural result
- broken Segment membership/order/timeline fails through existing rules
- semantic correctness is not inferred
- Validation does not create Review Items or Human Decisions
- validation failure behavior matches Slice 1 decision

### 11.5 Restart acceptance

한 temporary v5 database와 fake provider에서 다음을 검증한다.

```text
durable execution provenance and canonical Raw Transcript 준비
→ provider-independent correction request
→ fake proposals
→ canonical Candidates and proposed Revision construction
→ structural Validation invocation
→ atomic persistence
→ connection close
→ new connection open
→ exact Candidate/Revision/Segment/Result lineage reconstruction
```

하나의 deterministic failure path에서 complete rollback과 restart 후 original lineage
preservation을 검증한다.

### 11.6 Regression ownership

다음 기존 capability가 변하지 않았음을 검증한다.

- Execution durability
- schema v1-v5 validation and migration
- provider provenance and Raw Transcript persistence
- standalone Candidate/Revision repositories
- existing manual Candidate/Revision service APIs
- Transcript structural validation
- Subtitle and SRT demo regressions
- no Review or applicability behavior activation

---

## 12. Implementation Sequence

각 slice는 하나의 bounded responsibility와 하나의 logical commit으로 완료한다.

### Slice 1 — Correction Application Composition Assessment

목표:

- current correction, validation and canonical persistence inventory
- request/context ownership decision
- provider-neutral proposal shape decision
- identity and cardinality decision
- revision construction decision
- atomic record set and transaction ownership decision
- Validation ordering and failure decision
- exact Application public capability boundary
- Architecture Decision History와 implementation status 동기화

이 slice는 read-only assessment이며 production interface를 만들지 않는다.

권장 commit:

```text
docs: assess transcript correction application composition
```

### Slice 2 — Correction Capability Contract

목표:

- Application-owned `CorrectionGenerationPort`
- provider-independent request/context types
- provider-neutral proposal DTO
- explicit capability failure boundary
- fake provider contract tests
- no concrete provider imports or runtime selection

권장 commit:

```text
feat: establish transcript correction capability contract
```

### Slice 3 — Correction Proposal Validation and Canonical Construction

목표:

- Application correction orchestration service
- canonical input loading and validation
- proposal validation
- canonical Candidate construction
- proposed Segment and Revision construction
- identity, ordering, provenance and uncertainty handling
- fake provider Application tests

이 slice는 아직 persistence transaction을 분할 호출하지 않는다. Approved command port가
필요하면 final records를 계산해 한 번 전달한다.

권장 commit:

```text
feat: orchestrate transcript correction proposals
```

### Slice 4 — Atomic Correction Generation Persistence

목표:

- Slice 1이 승인한 exact correction-generation record set
- Application-owned command persistence port
- SQLite command-specific transaction composition
- existing internal writer reuse
- collision, rollback, commit and restart tests
- Application exactly-once persistence wiring

Schema v5 변경이 필요하다는 결론이면 구현하지 않고 Stop Condition으로 보고한다.

권장 commit:

```text
feat: persist generated transcript corrections atomically
```

### Slice 5 — Structural Validation Integration

목표:

- generated proposed Revision에 existing structural Validation invocation
- Slice 1이 승인한 validation ordering
- validation and correction failure propagation
- no Human Decision or Review Item creation
- valid/invalid proposal integration tests

권장 commit:

```text
feat: validate generated transcript corrections
```

### Slice 6 — In-Memory Acceptance and Restart Verification

목표:

- fake provider end-to-end Application composition
- deterministic proposals and failures
- canonical restart reconstruction
- previous lineage preservation after failure
- concrete provider absence proof
- Goal/status completion synchronization

이 slice는 빠진 production behavior를 새로 추가하는 catch-all이 아니다.

권장 commit:

```text
test: verify transcript correction application foundation
```

### Sequence changes

Slice 1의 approved assessment가 더 작은 safe ordering을 요구하면 Goal을 먼저 수정하고
근거를 Architecture Decision History에 남길 수 있다. 다음은 허용하지 않는다.

- concrete provider를 capability contract보다 먼저 구현
- fake provider shape로 Domain model을 변경
- proposal validation을 provider adapter로 이동
- structural Validation 이전에 Human Approval을 암시
- Review, applicability, Subtitle 또는 Artifact를 이 Goal에 포함
- 여러 logical slices를 검증 없이 한 commit으로 합치기

---

## 13. Acceptance Criteria

### 13.1 Capability contract

- Correction port is Application-owned and provider-independent
- request/context shape is explicit and minimal
- proposal DTO is not a canonical Domain model
- port exposes no SQLite, network, SDK or credential type
- fake provider satisfies the same contract without special service branches

### 13.2 Application behavior

- Application loads canonical inputs and verifies lineage
- provider is invoked exactly once after preconditions pass
- malformed proposals cannot become canonical records
- canonical Candidate and Revision fields are Application-computed
- provider cannot supply canonical identities or approval
- provenance and uncertainty are exact
- no Review Item, Decision or applicability record is created

### 13.3 Validation

- generated Revision passes existing structural Validation before the approved success boundary
- invalid timeline/order/reference structure is exposed
- Validation does not judge semantic correctness
- Validation does not approve a correction
- result is not described as Transcript Ready State

### 13.4 Persistence and restart

- approved logical record set is atomic
- every practical failure stage rolls back the complete set
- identity collision preserves original records
- generated canonical lineage survives restart exactly
- no provider DTO or raw response is stored as canonical Domain data
- schema remains v5 unless a separately approved decision changes scope

### 13.5 Scope integrity

- no concrete provider dependency exists
- no network or credential usage exists
- no provider registry/plugin runtime exists
- no Review, Human Decision or current-selection behavior exists
- no Subtitle, Artifact, Diagnostic, Lecture Intelligence or long-media work exists

---

## 14. Validation

각 implementation slice에서 최소한 다음을 실행한다.

```bash
PYTHONPATH=src python3 -m compileall -q src tests
PYTHONPATH=src python3 -m unittest discover -s tests -q
python3 -m tabnanny src tests
git diff --check
git diff --cached --check
```

Repository에 configured lint 또는 type check가 있으면 함께 실행한다. Focused tests,
relevant Transcript/Execution/Subtitle regressions와 complete suite 결과를 모두 기록한다.

Network, credential, paid provider, real classroom media 또는 sensitive transcript content를
사용하지 않는다.

---

## 15. Review Requirements

`implementation/050_IMPLEMENTATION_WORKFLOW.md`의 Risk-Based Workflow를 따른다.
독립 Claude review는 critical architecture/correctness defect 탐지만을 목적으로 한다.
General code/style review, refactoring suggestion 또는 architecture brainstorming을 수행하는
gate가 아니다.

기본 분류:

| Slice | Expected Classification | Reason |
| --- | --- | --- |
| 1. Assessment | Optional — Skipped | read-only architecture decision record |
| 2. Capability Contract | Required — Executed | first correction provider boundary and Application contract |
| 3. Orchestration | Required — Executed | canonical construction, provenance and lifecycle behavior |
| 4. Atomic Persistence | Required — Executed | multi-record transaction, rollback and restart semantics |
| 5. Validation Integration | Required — Executed | validation ordering and externally observable success/failure |
| 6. Acceptance | Optional — Skipped | test/composition-only일 때; production boundary 변경 시 Required |

실제 diff가 예상보다 높은 위험 경계를 바꾸면 `Required — Executed`로 상향한다.
Skipped review를 `PASS`로 표현하지 않는다.

Required review는 정확히 한 번, actual staged diff와 직접 관련된
Blueprint/Application/Persistence contracts만 읽으며 다음 구조를 요구한다.

```text
Verdict:
PASS | CRITICAL_CHANGES_REQUIRED | BLOCKED

Critical Issues:
- ...

Critical Missing Tests:
- ...

Blueprint Conflict:
Yes/No

Review Basis:
- ...
```

기본 review budget은 6 turns다. Formatting 불일치나 verdict omission만으로 재실행하지
않는다. 명시적 verdict가 없으면 concrete critical issue가 실제로 식별되었는지 확인한다.
없으면 `Inconclusive — no critical findings identified`로 기록하고 진행한다. Reviewer silence,
verbosity 또는 verdict line omission 자체는 Stop Condition이 아니다.

Critical finding은 다음으로 제한한다.

- released Blueprint violation
- architectural responsibility inversion
- transaction atomicity, migration correctness 또는 rollback defect
- data corruption/loss, identity 또는 provenance corruption
- lifecycle 또는 Human Authority violation
- public contract violation
- security/privacy defect
- realistic critical failure path의 missing test

Naming, formatting, documentation wording, optional abstraction/refactoring, speculative
improvement, future extensibility, correctness impact 없는 performance suggestion과 optional
additional test는 non-blocking이다. Verified critical issue만 최소 수정하고 focused/full
validation을 다시 실행한다. Non-critical observation은 slice를 차단하지 않는다.

---

## 16. Commit Policy

각 slice는 정확히 하나의 logical commit으로 완료한다.

Commit 전에 반드시:

```text
focused tests pass
relevant regressions pass
complete suite pass
compile/static checks pass
diff checks pass
required review identified no unresolved critical defect
no unrelated staged change
Goal/status synchronized
```

Commit 후:

```bash
git rev-parse HEAD
git status --short
```

Working Tree가 clean인지 확인한다. 다음 slice를 같은 commit에 포함하지 않는다.

---

## 17. Goal Self-Maintenance

이 Goal은 실행 중 repository의 active status record 역할을 한다.

각 successful slice 후 반드시:

1. 해당 slice를 `Completed Capabilities`에 기록한다.
2. `Remaining Milestones`에서 제거한다.
3. immediate next slice를 갱신한다.
4. 실제 Application port, orchestration, transaction과 validation capability를 요약한다.
5. `implementation/060_IMPLEMENTATION_STATUS.md`를 동기화한다.
6. Architect Decision 또는 approved sequence deviation의 근거를 history에 남긴다.
7. excluded scope가 우연히 완료된 것처럼 표현되지 않았는지 확인한다.

Goal 문서 변경은 해당 implementation slice의 상태 동기화로서 같은 logical commit에
포함할 수 있다. 완료 evidence를 덮어쓰거나 삭제하지 않는다.

### 17.1 Completed Capabilities

```text
Slice 1 — Correction Application Composition Assessment
- commit `4c63d18` — `docs: assess transcript correction application composition`
- provider-independent request/context ownership approved
- provider-neutral single-Segment replacement proposal approved
- caller-supplied deterministic canonical identity plan approved
- zero-or-many proposal cardinality and zero-proposal no-op approved
- one atomic Candidate/Segment/Revision/Result record set approved
- persist-proposed-records then structural-validate ordering approved
- explicit provider/proposal/persistence/validation failure propagation approved
- Claude Review: Optional — Skipped (read-only assessment)

Slice 2 — Correction Capability Contract
- commit `cc93c4a` — `feat: establish transcript correction capability contract`
- Application-owned `CorrectionGenerationPort`
- immutable provider-independent request and Segment context
- provider-neutral ordered `CorrectionProposal` tuple
- explicit `CorrectionGenerationFailure` boundary
- caller-owned deterministic Candidate/Result/Segment/Revision/Validation identity plan
- no SQLite, HTTP, concrete provider, credential or provider-runtime dependency
- Required Claude Review: Inconclusive — no critical findings identified
  (one bounded 6-turn review; no concrete critical issue reported)

Slice 3 — Correction Proposal Validation and Canonical Construction
- commit `7620f32` — `feat: orchestrate transcript correction proposals`
- `TranscriptCorrectionGenerationService.prepare_correction(...)`
- canonical Raw/parent Revision and running-execution precondition loading
- exactly-once provider-independent capability invocation
- immutable request and ordered Segment context construction
- proposal type, target, uniqueness, content, capability and finite-number validation
- caller identity-plan cardinality, uniqueness and existing-identity validation
- exact Candidate, replacement Segment, proposed Revision and Result construction
- zero-proposal no-op and provider/proposal error propagation
- no canonical write before the Slice 4 command boundary
- Required Claude Review: Inconclusive — no critical findings identified
  (one bounded 6-turn review; no concrete critical issue reported)

Slice 4 — Atomic Correction Generation Persistence
- commit `20cb710` — `feat: persist generated transcript corrections atomically`
- Application-owned `AtomicGeneratedCorrectionPersistence`
- one v5 transaction for all Candidates, Candidate Results, replacement Segments,
  proposed Revision and Revision Result
- parent lineage, source provenance, ordered reference and target membership checks
- immutable identity collision handling and complete rollback
- restart reconstruction and lower-schema feature-gate coverage
- no public repository transaction nesting
- Required Claude Review: Inconclusive — no critical findings identified
  (one bounded 6-turn review; no concrete critical issue reported)

Slice 5 — Structural Validation Integration
- generated Revision commit precedes existing structural Validation invocation
- returned `PreparedCorrectionGeneration` includes the exact Validation result
- structurally invalid results remain unapproved proposed Revisions
- validation operation failure propagates after canonical proposal commit
- zero-proposal no-op invokes neither persistence nor Validation
- Required Claude Review: Inconclusive — no critical findings identified
  (one bounded 6-turn review; no concrete critical issue reported)
```

### 17.2 Remaining Milestones

```text
6. In-Memory Acceptance and Restart Verification
```

### 17.3 Immediate Next Slice

```text
In-Memory Acceptance and Restart Verification
```

### 17.4 Architecture Decision History

Slice 1부터 다음 decision을 이 표에 누적 기록하고
`implementation/060_IMPLEMENTATION_STATUS.md`와 동기화한다. `Pending`은 이 Goal이 outcome을
선결정하지 않았다는 뜻이다.

| Decision Group | Status | Approved Decision | Evidence / Commit |
| --- | --- | --- | --- |
| correction request/context | Approved | Request identifies Raw Transcript lineage, optional parent Revision, running execution and correction Capability. Application resolves the exact parent Segment sequence and constructs immutable provider-neutral context containing existing Segment identity, text, source order and optional timeline/speaker/confidence/uncertainty values. Source Media body, repositories and hidden global context are not exposed. | Slice 1 |
| provider-neutral proposal DTO | Approved | One proposal targets exactly one existing Segment and supplies proposed text, rationale, ordered evidence and optional confidence/uncertainty/provider provenance hints. Split, merge, deletion, timestamp replacement and arbitrary provider metadata are unsupported and rejected. | Slice 1 |
| canonical identity ownership | Approved | Provider supplies no canonical identity. Caller supplies one deterministic identity plan containing Candidate, Candidate Result and replacement Segment identities per expected proposal plus proposed Revision, Revision Result and Validation identities. Application validates cardinality and absence before persistence. | Slice 1 |
| generation cardinality | Approved | Port returns an ordered tuple of zero or more proposals. Duplicate targets and conflicting proposals are rejected. Zero proposals is an explicit successful no-op with no Candidate, Revision, Result or Validation write. | Slice 1 |
| proposed revision construction | Approved | One or more valid proposals produce one proposed Revision. Each target Segment is replaced in the parent sequence by one new Segment preserving timeline, order, speaker and timing; untouched Segments are reused. Candidate order follows validated proposal order. Revision parent is the requested Raw Transcript or existing Revision, has no decision reference, no validation id and `UNDETERMINED` applicability. | Slice 1 |
| atomic persistence boundary | Approved | One generation command atomically first-inserts all Candidates and their DomainResultReferences, all replacement Segments, the proposed Revision and its DomainResultReference. Public repository saves are not nested. Existing schema v5 and internal writers are reused; no request/proposal record is persisted. Parent lineage, target membership and source provenance are checked before writes. | Slice 1; Slice 4 |
| structural Validation ordering | Approved | Proposal and canonical linkage validation occur before the atomic write. After the proposed records commit, existing `TranscriptValidationService.validate_corrected_revision(...)` runs against canonical storage. A structurally invalid result remains an explicit unapproved proposed Revision; it is not rolled back or treated as ready. Validation records remain in-memory in this Goal and are not claimed restart-durable. | Slice 1; Slice 5 |
| failure propagation | Approved | Port failure propagates without fallback or write. Malformed/unsupported proposal or identity-plan mismatch raises an Application correction error before persistence. Persistence errors propagate with atomic rollback. Validation operation errors propagate after the already committed proposal records; structurally invalid Validation is returned normally and grants no approval. No automatic retry, alternate provider or Execution Failure recording is added. | Slice 1 |
| approved sequence changes | None | 현재 Section 12 순서 유지 | Goal baseline |

별도 assessment document는 decision과 evidence를 이 section 및 implementation status에
합리적으로 기록할 수 없을 때만 만든다.

#### Slice 1 contract evidence

- Current `CorrectionCandidate` targets one `TranscriptSegmentId`; current Domain has no
  provider-neutral split/merge/delete proposal concept. The minimum supported proposal is
  therefore one text replacement for one existing Segment.
- Current `TranscriptSegment` preserves source order, optional time range, speaker,
  confidence, uncertainty and `replaces_segment_id`; replacement construction can retain
  source traceability without provider-controlled timestamps.
- Current `CorrectedTranscriptRevision` requires exactly one Raw or Revision parent and
  already represents ordered Segment and Candidate references, optional decision/validation
  references and undetermined applicability.
- Existing `TranscriptService` validates execution provenance, parent lineage, Segment order
  and immutable identity absence before Candidate or Revision persistence.
- Existing `TranscriptValidationService` loads a persisted Revision through query boundaries
  and records structural findings separately. It does not judge semantic correctness or
  approval, so persistence precedes its current invocation without moving authority.
- Existing separate Candidate and Revision atomic commands cannot make a multi-proposal
  generation call indivisible. A command-specific atomic persistence port is required in
  Slice 4, using the released v5 structures without schema change.
- Current Application services receive deterministic identities from their callers. A
  caller-supplied identity plan preserves that convention and keeps provider output from
  owning canonical identity.

---

## 18. Stop Conditions

다음 중 하나라도 발생하면 자동 진행을 중단한다.

### 18.1 Blueprint or Domain ambiguity

- provider-neutral proposal를 표현하려면 새 canonical Product Concept가 필요하다.
- current CorrectionCandidate 또는 CorrectedTranscriptRevision meaning을 변경해야 한다.
- correction 결과와 Human Modification을 구분할 수 없다.
- structural Validation과 semantic correction authority가 분리되지 않는다.
- 현재 TranscriptSegment model로 supported correction을 안전하게 표현할 수 없다.

### 18.2 Authority boundary ambiguity

- provider가 canonical identity, revision 또는 approval을 소유해야만 구현할 수 있다.
- Application과 provider 사이에서 Validation 또는 failure authority가 이동한다.
- concrete provider contract 없이는 Application capability를 정의할 수 없다는 결론이 난다.
- Review Item 또는 Human Decision을 구현해야만 correction success를 표현할 수 있다.

### 18.3 Persistence blocker

- complete atomic command를 위해 released schema v5 meaning을 변경해야 한다.
- existing canonical writers로 exact records를 저장할 수 없다.
- rollback 또는 restart reconstruction을 보장할 수 없다.
- partial Candidate/Revision persistence를 피할 approved transaction boundary를 정할 수 없다.

### 18.4 Validation blocker

- existing structural Validation contract가 generated revision을 검증할 수 없다.
- validation failure durability가 이 Goal의 success semantics에 필수지만 current contract가 없다.
- Validation이 Human Approval이나 Review policy를 결정해야만 진행할 수 있다.

### 18.5 Review or operational blocker

- verified released Blueprint contradiction이 남는다.
- verified architectural correctness issue가 남는다.
- unresolved critical migration, rollback 또는 atomicity defect가 남는다.
- unresolved public contract violation이 남는다.
- unresolved security/privacy defect가 남는다.
- required Architect Decision 없이는 책임 경계를 확정할 수 없다.
- required Blueprint Clarification 또는 Blueprint PATCH 없이는 구현할 수 없다.
- focused 또는 full test failure를 current slice 안에서 안전하게 해결할 수 없다.
- configured validation을 실행할 수 없고 사용자 승인 없이 우회해야 한다.

### 18.6 Repository state blocker

- unrelated user changes가 current slice와 겹친다.
- working tree 또는 HEAD 불일치를 안전하게 해석할 수 없다.
- commit history를 파괴하거나 approved work를 discard해야만 진행할 수 있다.

중단 보고는 다음을 정확히 구분한다.

```text
Requires Architect Decision
Requires Blueprint Clarification
Requires Blueprint PATCH
Operational Blocker
```

DTO naming, method signature, serialization reuse 또는 command-specific internal writer shape만의
문제는 Blueprint ambiguity가 아니다.

---

## 19. Explicitly Deferred Scope

이 Goal 완료 후에도 다음은 별도 milestone과 Goal이 필요하다.

```text
Concrete Correction Provider Adapter and credentialed acceptance
prompt and provider quality evaluation
Transcript Review Preparation
Review Item and Review Decision durability
Human Decision Application
Transcript applicability and current selection
Transcript Ready State
Subtitle canonical persistence and generation quality
Final Subtitle durability
Artifact persistence
Diagnostic canonical persistence when required by a resolving consumer
Lecture Intelligence and Edit Candidate pipeline
Plugin runtime and registry
long-media runtime and chunking
```

Correction Application Foundation 완료를 concrete provider success나 production correction
quality로 표현하지 않는다.

---

## 20. Consolidated Completion Report

Goal의 모든 slice가 완료되면 다음 구조로 하나의 consolidated report를 작성한다.

```text
## Summary

## Repository Status

## Blueprint and Contract Basis

## Completed Slice Commits

## Architecture Decisions

## Correction Capability Contract

## Request and Context Construction

## Provider-Neutral Proposal Model

## Application Orchestration

## Canonical Candidate Construction

## Proposed Revision Construction

## Structural Validation

## Atomic Persistence Coordination

## Provenance and Uncertainty

## Failure Semantics

## Restart Acceptance

## Tests and Validation

## Claude Reviews

## Scope Confirmation

## Product Milestone Impact

## Deferred Capabilities

## Open Questions

## Next Product Milestone Candidate

## Final Verdict
```

보고에는 최소한 다음을 포함한다.

- starting and final HEAD
- every logical commit hash and message
- final branch and clean Working Tree
- exact port, request, context and proposal inventory
- identity, cardinality and revision construction decisions
- transaction record set and ownership
- structural Validation invocation and non-authority boundaries
- restart acceptance evidence
- focused and full test counts/results
- every Claude Review classification, budget, verdict and findings
- corrections made after review
- no network, credential, concrete provider or sensitive artifact가 commit되었다는 확인
- excluded scope가 구현되지 않았다는 확인

Final Verdict는 다음으로 끝낸다.

```text
Transcript Correction Application foundation: VERIFIED | BLOCKED

Requires Architect Decision: Yes/No
Requires Blueprint Clarification: Yes/No
Requires Blueprint PATCH: Yes/No
```

---

## 21. Goal Completion Condition

다음 조건을 모두 만족할 때만 이 Goal을 complete로 표시한다.

```text
provider-independent correction capability contract complete
request/context ownership approved
provider-neutral proposal validation complete
canonical Candidate and proposed Revision construction complete
structural Validation invoked at the approved boundary
approved atomic persistence command complete
restart-safe canonical correction lineage verified
fake provider acceptance complete
no concrete provider or network dependency introduced
all focused and regression tests pass
all required reviews identify no unresolved critical defect
all slice commits created
Goal and implementation status synchronized
Working Tree clean
```

그때 `Remaining Milestones`는 다음으로 바꾼다.

```text
None — all Goal slices complete
```

그리고 immediate next slice는 다음으로 바꾼다.

```text
Goal Complete — Concrete Correction Provider Adapter requires a fresh Goal
```
