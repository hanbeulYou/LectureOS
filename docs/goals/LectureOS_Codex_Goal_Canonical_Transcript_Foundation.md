# LectureOS Codex Goal — Canonical Transcript Foundation

## 1. Mission

이 문서는 완료된 Durability Goal 이후, Blueprint dependency order에 따라
LectureOS의 canonical Transcript foundation을 구축하기 위한 장기 실행 Goal이다.

이 Goal의 목적은 production correction generation 또는 Review 기능을 먼저
보여 주는 것이 아니다. Source Media와 provider provenance에서 시작한 Transcript
record가 process restart 이후에도 동일한 identity, ordering, provenance와 revision
lineage를 보존하도록 durable canonical foundation을 완성하는 것이다.

Codex는 사용자가 각 slice마다 별도 prompt를 전달하지 않아도 다음 루프를 반복한다.

```text
현재 repository baseline 확인
→ 첫 번째 미완료 milestone 선정
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
→ Persistence implementation
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
docs/090_BLUEPRINT_RELEASE.md

patches/PATCH-0001-l0-and-prd-stabilization.md
patches/PATCH-0002-system-model.md
patches/PATCH-0003-text-pipeline.md
patches/PATCH-0004-edit-pipeline.md
patches/PATCH-0005-plugin-system.md

implementation/000_IMPLEMENTATION_DESIGN_GUIDE.md
implementation/010_PROJECT_LIFECYCLE.md
implementation/020_STORAGE_MODEL.md
implementation/030_EXECUTION_MODEL.md
implementation/040_INTERFACE_CONTRACTS.md
implementation/050_IMPLEMENTATION_WORKFLOW.md
implementation/060_IMPLEMENTATION_STATUS.md
implementation/070_DIAGNOSTIC_PERSISTENCE_ASSESSMENT.md

docs/goals/LectureOS_Codex_Goal_Durability.md
```

Blueprint의 Product meaning을 SQLite 편의를 위해 변경하지 않는다. Blueprint가
구체적인 storage shape을 정하지 않은 경우에는 Architect Decision으로 최소 구현
정책을 정한다. 두 개 이상의 plausible interpretation이 Domain meaning을 바꾸는
경우에는 Blueprint Clarification 또는 Blueprint PATCH 없이는 구현하지 않는다.

---

## 3. Current Repository Baseline

이 Goal 작성 시점의 기준은 다음과 같다.

```text
Branch:
main

HEAD:
6be8d627cc8f4aed5e174e563d621a01f346b70e

Commit:
docs: assess diagnostic persistence

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

## 4. Scope Validation

### 4.1 Included canonical records

이 Goal은 현재 승인된 Transcript Domain record 중 다음 foundation만 다룬다.

```text
ProviderTranscriptResult provenance ownership/resolution
RawTranscript
TranscriptSegment
CorrectionCandidate
CorrectedTranscriptRevision
Transcript lineage relationships
```

`ProviderTranscriptResult`는 Raw Transcript의 필수 provenance input이지만, 이 Goal은
이를 독립 canonical aggregate로 선결정하지 않는다. Slice 1은 기존 Execution/Result
durability가 canonical provider provenance를 이미 소유하는지, Transcript foundation이
별도 canonical storage를 소유해야 하는지, 또는 durable resolution만 필요한지
결정한다. 이미 승인된 canonical owner가 존재하면 duplicate storage를 만들지 않는다.

`TranscriptSegment`는 Blueprint의 미확정 conceptual `Transcript Unit` 명칭을
재정의하지 않는다. 이 Goal은 현재 승인된 implementation Domain model인
`TranscriptSegment`를 그대로 저장하며, 새로운 product terminology를 만들지 않는다.

### 4.2 Included capabilities

포함 범위는 다음과 같다.

- exact current Domain model inventory와 storage semantics assessment
- canonical Transcript schema와 명시적 migration
- direct initialization of the complete new schema version
- `ProviderTranscriptResult` provenance ownership decision and durable resolution
- `RawTranscript`와 owned ordered segment-reference persistence
- canonical `TranscriptSegment` persistence
- `CorrectionCandidate` persistence
- `CorrectedTranscriptRevision`과 ordered lineage-reference persistence
- immutable record collision semantics
- exact serialization and deserialization
- schema feature gates
- restart reconstruction and lineage queries
- Application-owned persistence ports where a multi-record logical command is required
- command-specific SQLite transaction composition
- `TranscriptService` dependency injection and durable wiring
- top-level Composition Root construction
- focused repository, transaction, service and restart tests
- implementation status and Goal self-maintenance

### 4.3 Explicitly excluded capabilities

다음은 이 Goal에서 구현하지 않는다.

```text
Review Item persistence
Review Decision persistence
Human Decision Application persistence
Subtitle persistence
Final Subtitle persistence
Artifact persistence
TranscriptValidation persistence
TranscriptValidationFinding persistence
RevisionApplicabilityRecord persistence
CurrentTranscriptSelection persistence
Correction provider integration
external AI correction provider
provider registry
generic provider framework
plugin runtime or plugin loading
long-media chunking
Lecture Intelligence
Diagnostic canonical persistence
DomainResultReference schema redesign
unrelated Execution durability
schema downgrade
automatic migration chaining
generic Unit of Work
generic migration framework
generic DI container
quality optimization
Demo or CLI feature expansion
Project or Lecture work
```

Review persistence는 correction candidate와 corrected revision을 검토하고 승인하는
후속 milestone에 속한다. 이 Goal은 Review handoff가 사용할 canonical target을
준비하지만 Review Item이나 Review Decision을 저장하지 않는다.

Transcript validation record persistence와 revision applicability/current-selection
history도 이 foundation의 선행조건이 아니다. 현재 raw, segment, candidate, revision
lineage를 restart-safe하게 만드는 데 필요한 canonical record set만 구현한다.

---

## 5. Dependency Validation

Blueprint의 Transcript 순서는 다음과 같다.

```text
External ASR Boundary
→ provider result provenance
→ Raw Transcript preservation
→ Transcript units/time traceability
→ Correction Candidate
→ Corrected Transcript Revision
→ structural Validation
→ Review preparation and Decision Application
→ Transcript Ready State
→ Subtitle
→ Artifact
```

따라서 production correction candidate generation이나 Review handoff보다 먼저
durable canonical Transcript foundation이 필요하다.

그 근거는 다음과 같다.

1. Blueprint는 Raw Transcript를 correction보다 먼저 보존하도록 요구한다.
2. Correction은 Raw Transcript 또는 이전 corrected revision을 근거로 해야 한다.
3. Corrected Transcript는 Raw Transcript를 덮어쓰지 않고 revision lineage를 보존한다.
4. Review Item은 원래 candidate, revision, Source Media 또는 Time Range로 돌아갈 수
   있어야 한다.
5. Reprocessing은 기존 Raw Transcript, revision과 사용자 결정을 잃지 않아야 한다.
6. Subtitle은 적용 가능한 Corrected Transcript를 downstream input으로 사용하며
   Transcript와 독립된 책임이다.
7. Artifact는 승인된 canonical state에서 재생성되는 파생물이며 foundation의
   유일한 storage가 될 수 없다.

M1 demo의 in-memory Transcript와 generated SRT는 execution viability를 증명했지만,
process restart 후 production correction 또는 Review provenance를 복원하는 canonical
foundation은 증명하지 않았다.

---

## 6. Proposed Milestone Boundary

이 Goal이 완료되면 다음 path가 durable해야 한다.

```text
approved provider provenance source or ProviderTranscriptResult storage
→ RawTranscript + ordered TranscriptSegment records
→ CorrectionCandidate
→ CorrectedTranscriptRevision + ordered TranscriptSegment references
→ restart
→ exact Domain reconstruction
→ exact raw-to-revision lineage query
```

이 Goal이 완료되어도 다음 path는 production-ready가 아니다.

```text
external correction provider
→ generated correction candidates
→ durable Review Item
→ Human Review Decision
→ Transcript Ready selection
→ durable Subtitle
→ durable Artifact
```

Milestone acceptance statement:

```text
Canonical Transcript foundation across restart: VERIFIED
```

이 statement는 durable record와 lineage foundation만 의미한다. Transcript correction
quality, Human Review, Subtitle quality 또는 Artifact delivery를 승인하지 않는다.

---

## 7. Domain Record Semantics

첫 architecture assessment는 정확한 current fields와 invariants를 다시 기록하고,
아래 의미를 code와 contract evidence로 확정해야 한다.

### 7.1 ProviderTranscriptResult

Slice 1에서 확정할 의미:

```text
Option A — Transcript-owned immutable insert-only canonical provenance record
Option B — existing Execution/Result-owned canonical provenance with durable resolution
```

이 Goal은 Option A를 선결정하지 않는다. 기존 durability가 canonical provenance를
이미 소유한다면 별도 `ProviderTranscriptResult` table과 repository를 추가하지 않고,
Raw Transcript reconstruction에 필요한 durable resolution boundary만 구현한다.

Option A가 승인되는 경우 보존 대상은 현재 Domain model의 exact fields뿐이다.

```text
identity
source_media_id
source_timeline_id
run_id
unit_execution_id
capability
provider_reference
original_content
plugin_reference
diagnostic_references (ordered)
uncertainty
normalized
```

Provider response JSON을 Domain storage shape으로 사용하지 않는다. API credential,
temporary audio 또는 provider-specific arbitrary payload를 저장하지 않는다.

### 7.2 RawTranscript

예상 의미:

```text
immutable insert-only canonical raw transcript record
```

보존 대상:

```text
identity
domain_result_id
source_media_id
source_timeline_id
provider_result_id
run_id
unit_execution_id
segment_ids (ordered)
validation_id (optional opaque reference)
```

Raw Transcript는 correction이나 revision에 의해 수정되거나 덮어써지지 않는다.

### 7.3 TranscriptSegment

예상 의미:

```text
immutable insert-only canonical implementation record
```

보존 대상:

```text
identity
transcript_id
source_timeline_id
text
source_order
start
end
speaker_label
confidence
uncertainty
replaces_segment_id
```

`None`과 empty string의 current Domain distinction을 보존한다. 시간값은 SQLite
representation으로 저장하되 Domain validation을 SQL lifecycle policy로 복제하지
않는다.

### 7.4 CorrectionCandidate

예상 의미:

```text
immutable insert-only canonical candidate record
```

보존 대상:

```text
identity
domain_result_id
transcript_id
segment_id
proposed_text
rationale
run_id
unit_execution_id
target_revision_id
evidence (ordered)
confidence
uncertainty
capability
plugin_reference
provider_reference
```

Candidate는 Review Decision이나 승인 결과가 아니다. 저장 시 자동 승인하지 않는다.

### 7.5 CorrectedTranscriptRevision

예상 의미:

```text
immutable append-only revision record
```

보존 대상:

```text
identity
transcript_id
domain_result_id
run_id
unit_execution_id
segment_ids (ordered)
parent_raw_transcript_id
parent_revision_id
correction_candidate_ids (ordered)
decision_reference
validation_id
applicability
```

현재 Domain constructor가 요구하는 exactly-one-parent invariant를 보존한다.
Revision identity collision은 overwrite, update 또는 idempotent success가 아니다.

### 7.6 Canonical records versus references

다음을 혼동하지 않는다.

```text
RawTranscript.segment_ids
≠ embedded TranscriptSegment records

CorrectedTranscriptRevision.segment_ids
≠ hidden segment snapshots

CorrectionCandidate.domain_result_id
≠ DomainResultReference canonical record body

CorrectedTranscriptRevision.domain_result_id
≠ DomainResultReference canonical record body

validation_id / decision_reference / diagnostic_references
≠ ownership of Validation, Review Decision or Diagnostic records
```

Owned ordered child rows는 tuple ordering을 보존하기 위한 representation이다. Opaque
external references에는 승인되지 않은 aggregate foreign key를 추가하지 않는다.

---

## 8. Mandatory Architecture Assessment Gate

첫 구현 commit 전에 read-only assessment를 완료하고 Architect Decision을 기록한다.

가장 중요한 기존 경계는 다음과 같다.

```text
TranscriptService.create_raw_transcript(...)
TranscriptService.create_correction_candidate(...)
TranscriptService.create_corrected_revision(...)
```

현재 서비스는 Transcript record와 함께 `DomainResultReference`를 생성한다. 완료된
Execution durability에서는 `ExecutionService.record_results(...)`도 canonical
DomainResultReference와 final execution/run snapshots를 하나의 atomic command로
저장한다. 어느 command가 canonical insertion을 소유하는지는 아직 이 Goal에서
결정하지 않았으며 Slice 1의 Architect Decision 대상이다.

따라서 구현 전에 다음 충돌을 해결해야 한다.

```text
Transcript command currently constructs DomainResultReference
vs.
Execution terminal Result command currently persists supplied canonical DomainResultReference
```

assessment는 최소한 다음을 답해야 한다.

1. 각 Transcript public command의 exact read/write inventory는 무엇인가?
2. TranscriptService가 생성하는 DomainResultReference는 언제 canonical하게
   저장되어야 하는가?
3. 동일 DomainResultId가 Transcript persistence와 Execution result persistence에서
   두 번 insert되는 것을 어떻게 방지하는가?
4. Transcript record와 해당 DomainResultReference는 같은 transaction이어야 하는가?
5. Execution terminal Result snapshots와 Transcript canonical record까지 하나의
   transaction이어야 하는가, 또는 approved command ordering으로 분리 가능한가?
6. provider result registration은 독립 command인가?
7. raw transcript와 new segments의 minimum atomic record set은 무엇인가?
8. corrected revision에서 existing segment reuse와 new segment insertion을 어떻게
   구분하는가?
9. CorrectionCandidate와 revision은 각각 별도 command boundary인가?
10. public repository protocols를 변경해야 하는가?
11. SQLite-only non-committing writers는 Application protocols 밖에 유지할 수 있는가?
12. in-memory default behavior와 durable composition이 같은 Application contract를
    어떻게 만족하는가?

권장 최소 방향은 다음과 같지만 assessment evidence 없이 자동 승인하지 않는다.

```text
Application computes complete immutable records
→ Application-owned command port
→ SQLite command adapter owns BEGIN/COMMIT/ROLLBACK
→ internal non-committing canonical writers
→ no lifecycle computation in persistence
```

이 gate에서 genuinely new Domain meaning이 필요하면 구현을 중단한다. SQLite table,
serialization, migration, transaction ownership과 sequencing 선택만 필요하면 Architect
Decision으로 문서화하고 계속할 수 있다.

---

## 9. Schema and Migration Strategy

### 9.1 Expected schema direction

현재 complete durable baseline은 schema v4다. Transcript canonical structures가 v4에
없다면 frozen v4를 수정하지 않고 다음 schema version을 추가한다.

예상 방향:

```text
next released schema version
= complete v4
+ provider provenance structures only if Slice 1 assigns ownership here
+ RawTranscript structures
+ TranscriptSegment structures
+ CorrectionCandidate structures
+ CorrectedTranscriptRevision structures
```

실제 version number와 grouping은 Slice 1 assessment에서 schema inventory를 확인한 뒤
Architect Decision으로 확정한다. 하나의 released version에 incomplete Transcript
foundation을 넣지 않는다.

### 9.2 Migration policy

기본 migration 방향:

```text
v4 → selected target schema explicit transactional migration
selected target schema → same version validated no-op
```

지원하지 않는 기본 방향:

```text
direct v1 → selected target schema
direct v2 → selected target schema
direct v3 → selected target schema
automatic chained migration
downgrade
ordinary open-time migration
```

기존 migration API가 다른 approved policy를 명시하면 그 계약을 따른다. 새 database는
complete selected target schema로 직접 initialize되어야 하며, 해당 version marker를
가진 incomplete database는 validation에 실패해야 한다.

### 9.3 Storage constraints

- typed identities는 established stable `TEXT` representation을 사용한다.
- enums는 exact `.value`를 constrained `TEXT`로 저장한다.
- booleans는 constrained integer representation을 사용한다.
- ordered tuples는 parent identity와 ordinal을 가진 child rows로 저장한다.
- ordinal은 non-negative이고 parent/ordinal은 unique해야 한다.
- owned child rows만 parent FK와 `ON DELETE CASCADE`를 사용한다.
- duplicate referenced values at distinct ordinals를 Domain이 금지하지 않으면 보존한다.
- optional references는 nullable typed columns로 저장한다.
- generic JSON, pickle, delimiter text 또는 arbitrary metadata column을 사용하지 않는다.
- SourceMedia, SourceTimeline, Run, UnitExecution, Result, Review, Validation, Diagnostic,
  Plugin aggregate에 승인되지 않은 external FK를 추가하지 않는다.
- schema constraint는 representation validity만 보장하며 lifecycle, correction authority,
  Review approval 또는 applicability selection을 결정하지 않는다.

### 9.4 Migration safety

Migration은 다음 순서를 보장한다.

```text
validate complete source schema
→ BEGIN IMMEDIATE
→ create all complete Transcript structures
→ update schema marker
→ validate complete target schema
→ COMMIT
```

어떤 DDL, marker update, validation 또는 commit failure에서도 rollback 후:

```text
source marker unchanged
no partial Transcript tables
all pre-existing records unchanged
connection state recoverable according to established convention
```

기존 in-memory Transcript data나 Execution result references를 migration 중 canonical
Transcript record로 합성하거나 backfill하지 않는다.

---

## 10. Repository Contracts

각 repository는 기존 public `Repository[Identity, Record]` contract를 우선한다.
assessment에서 current mechanical behavior와 approved immutable semantics를 구분한다.

필요한 repository 후보:

```text
SQLiteProviderTranscriptResultRepository (conditional on Slice 1 ownership decision)
SQLiteTranscriptSegmentRepository
SQLiteRawTranscriptRepository
SQLiteCorrectionCandidateRepository
SQLiteCorrectedTranscriptRevisionRepository
```

Slice 1이 existing Execution/Result durability를 provider provenance의 canonical owner로
확정하면 `SQLiteProviderTranscriptResultRepository`를 구현하지 않는다. 그 경우 기존
owner에서 Raw Transcript provenance를 restart 후 resolve하는 최소 durable boundary만
구현한다.

각 repository는 최소한 current protocol이 요구하는 exact methods만 구현한다.
speculative query, update, delete, upsert, pagination 또는 history API를 추가하지 않는다.

공통 요구사항:

- public save는 independently self-transactional이다.
- immutable identity collision은 `PersistenceIdentityCollisionError`다.
- identical duplicate save도 collision이며 idempotent success가 아니다.
- `INSERT OR REPLACE`, update, delete-and-reinsert를 사용하지 않는다.
- parent와 모든 owned ordered child rows는 한 transaction에 저장한다.
- `get`은 exact Domain wrapper와 tuple ordering을 재구성한다.
- `all` ordering은 current repository contract를 따른다.
- unknown identity behavior는 existing repository convention을 따른다.
- raw SQLite exceptions는 established persistence error mapping을 따른다.
- caller-owned connection을 닫지 않는다.
- lower schema에서는 `SchemaFeatureUnavailableError`를 사용하고 migration하지 않는다.
- malformed stored data를 default, coercion, skipping 또는 silent repair로 숨기지 않는다.

Command composition이 필요한 record에는 public repository와 command adapter가 공유할
SQLite-package-internal non-committing writer를 사용할 수 있다. Internal writer는
`BEGIN`, `COMMIT`, `ROLLBACK`을 실행하지 않으며 Domain repository protocol에 노출하지
않는다.

---

## 11. Application Wiring Contracts

`TranscriptService`는 현재 in-memory repository를 내부에서 직접 생성한다. Durable
wiring은 Application이 SQLite를 알지 않도록 constructor injection 또는 approved
Application-owned ports로 바꾼다.

필수 방향:

```text
TranscriptService
→ Transcript repository/query protocols

TranscriptService
→ command-specific Application persistence ports where atomic composition is required

Composition Root
→ concrete SQLite repositories and command adapters
```

금지 방향:

```text
Application → sqlite3
Application → SQLite concrete class
Persistence → Application service
Domain → Persistence
```

Application은 다음을 계속 소유한다.

- record identity selection
- execution provenance validation
- source/provider/transcript/revision relationship validation
- segment membership and ordering validation
- parent lineage validation
- candidate relationship validation
- final immutable record computation
- DomainResultReference construction or resolution only as decided by Slice 1

Persistence는 다음만 소유한다.

- exact supplied record serialization
- representation-level linkage validation
- transaction ownership
- collision detection
- rollback
- schema feature gate
- persistence error mapping

Application public APIs, lifecycle legality, returned Domain values와 exception semantics는
승인된 변경 없이는 바꾸지 않는다.

---

## 12. Authoritative Implementation Sequence

이 Goal은 다음 순서로 진행한다. 각 번호는 별도 validated and reviewed commit이다.

### Slice 1 — Transcript Persistence Composition Assessment

```text
Type: read-only architecture assessment and Architect Decision record
```

목표:

- exact model/repository/service write inventory 작성
- schema grouping과 migration boundary 확정
- immutable/append-only semantics 확정
- DomainResultReference ownership conflict 해결
- raw/candidate/revision minimum atomic record sets 확정
- Application port와 composition architecture 확정
- validation read transaction boundary 확정
- error propagation과 implementation sequence 확정

Architect Decisions는 이 Goal의 `Architecture Decision History`와
`implementation/060_IMPLEMENTATION_STATUS.md`에 기록한다. 결정과 evidence가 두 문서에
합리적으로 담기지 않는 경우에만 별도 focused assessment document를 만든다.

권장 commit:

```text
docs: assess canonical transcript persistence
```

### Slice 2 — Complete Transcript Schema and Migration

목표:

- complete new schema version direct initialization
- complete normalized Transcript table set
- explicit v4-to-new-version migration
- strict schema validation
- feature availability constants
- rollback injection tests
- old data preservation and empty canonical Transcript tables after migration

이 slice는 repository나 Application wiring을 구현하지 않는다.

권장 commit:

```text
feat: add canonical transcript sqlite schema
```

### Slice 3 — Provider Provenance Resolution and Segment Repository

목표:

- Slice 1이 Transcript ownership을 승인한 경우에만
  `SQLiteProviderTranscriptResultRepository`
- 기존 owner가 승인된 경우 duplicate repository 대신 durable provenance resolution
- `SQLiteTranscriptSegmentRepository`
- approved owner를 통한 exact provider provenance resolution 또는 round-trip
- ordered diagnostics and segment fields round-trip where Transcript owns the record
- insert-only collision behavior
- restart durability and lower-schema feature gating

Provider provenance resolution과 Segment는 Raw Transcript의 선행조건이므로 먼저
구현한다. Slice 1이 기존 canonical owner를 확인하면 duplicate storage를 만들지 않는다.

권장 commit:

```text
feat: persist transcript source records in sqlite
```

### Slice 4 — Raw Transcript Atomic Persistence

목표:

- `SQLiteRawTranscriptRepository`
- raw transcript plus new segment record atomic composition as approved by Slice 1
- DomainResultReference ownership/composition as approved by Slice 1
- Application-owned raw transcript persistence port where required
- rollback, collision, ordering and restart tests
- `TranscriptService.create_raw_transcript(...)` durable wiring

Provider result registration wiring이 별도 command slice여야 한다고 Slice 1이 결론 내리면,
이 slice 전에 가장 작은 별도 commit으로 추가하고 Goal sequence를 동기화한다.

권장 commit:

```text
feat: persist raw transcripts atomically
```

### Slice 5 — Correction Candidate Persistence

목표:

- `SQLiteCorrectionCandidateRepository`
- ordered evidence persistence
- exact optional capability/plugin/provider provenance
- DomainResultReference composition as approved by Slice 1
- `TranscriptService.create_correction_candidate(...)` durable wiring
- collision, rollback, ordering and restart tests

이 slice는 correction candidate를 생성하는 external provider를 구현하지 않는다.

권장 commit:

```text
feat: persist transcript correction candidates
```

### Slice 6 — Corrected Transcript Revision Persistence

목표:

- `SQLiteCorrectedTranscriptRevisionRepository`
- exactly-one-parent reconstruction
- ordered segment and candidate references
- reuse of existing segments and atomic insertion of genuinely new segments
- DomainResultReference composition as approved by Slice 1
- `TranscriptService.create_corrected_revision(...)` durable wiring
- multi-revision lineage, collision, rollback and restart tests

이 slice는 Review Decision record를 생성하거나 persistence하지 않는다.
`decision_reference`는 nullable opaque identity reference로만 보존한다.

권장 commit:

```text
feat: persist corrected transcript revisions
```

### Slice 7 — Canonical Transcript Composition and Restart Acceptance

목표:

- top-level SQLite Transcript composition helper 완성
- all construction sites and default in-memory composition regression
- raw-to-candidate-to-multiple-revision durable lineage query
- process restart reconstruction
- no Review/Subtitle/Artifact persistence dependency 증명
- implementation status와 Goal completion 상태 최종 동기화

이 slice는 빠진 production behavior를 새로 추가하는 catch-all이 아니다. 앞선 slice를
통합 검증하고 milestone acceptance를 기록하는 bounded slice다.

권장 commit:

```text
test: verify canonical transcript persistence across restart
```

### Sequence changes

Slice 1의 approved assessment가 더 작은 safe ordering을 요구하면 Goal을 먼저 수정하고
그 근거를 history에 남길 수 있다. 다음은 허용하지 않는다.

- incomplete released schema를 만들기 위한 임의 분할
- Review, Subtitle 또는 Artifact를 Transcript foundation보다 먼저 구현
- external correction provider를 canonical storage보다 먼저 구현
- architecture decision 없이 DomainResultReference ownership을 중복 구현
- 여러 logical slices를 검증 없이 하나의 commit으로 합치기

---

## 13. Tests and Acceptance Criteria

### 13.1 Schema and migration

- new database initializes directly as complete target schema
- explicit v4 migration succeeds transactionally
- same-version open/migration is a validated no-op according to migration API
- unsupported direct paths and downgrade are rejected
- ordinary open does not auto-migrate
- incomplete target schema marker is rejected
- each required parent and child shape is validated
- DDL, marker, final validation and reliable commit failures roll back
- existing v1-v4 records remain unchanged
- no canonical Transcript rows are synthesized

### 13.2 Repository round-trip

- every exact Domain field round-trips
- every optional field preserves `None`
- enums use exact `.value`
- booleans reconstruct as exact Python `bool`
- float values preserve finite Domain values
- empty ordered tuples produce no child rows
- non-sorted order is preserved
- duplicates at distinct ordinals remain where Domain permits them
- all immutable identity collisions preserve original data
- unknown identity and `all()` behavior match current repository protocols
- restart reconstructs exact Domain equality

### 13.3 Atomic command behavior

- every approved command persists its minimum logical record set in one transaction
- failure at every practical writer stage rolls back the complete command
- collision of any new immutable identity rolls back all supplied new records
- pre-existing records remain unchanged after failure
- commit failure rolls back where reliably injectable
- caller-owned connection remains open and reusable
- no nested public repository transaction occurs
- internal writers never own transactions
- no lifecycle or correction authority is duplicated in persistence

### 13.4 Application wiring

- service lifecycle and validation behavior remains unchanged
- service computes final records before persistence call
- each command port is invoked exactly once
- legacy independent writes are absent for composed commands
- persistence errors propagate without false success or fallback saves
- Application modules do not import SQLite
- Composition Root owns concrete construction
- in-memory unit tests remain possible without SQLite

### 13.5 Milestone restart acceptance

한 temporary v5 database에서 다음을 검증한다.

```text
existing durable execution provenance 준비
→ approved owner를 통해 provider provenance 저장 또는 resolve
→ RawTranscript와 ordered segments 저장
→ CorrectionCandidate 저장
→ first CorrectedTranscriptRevision 저장
→ second CorrectedTranscriptRevision 저장
→ connection close
→ new connection open
→ all canonical records exact reconstruction
→ raw-to-revision lineage exact reconstruction
→ ordering, duplicates, optional references and provenance 확인
```

추가로 하나의 deterministic failure path에서 complete rollback과 restart 후 original
state preservation을 검증한다.

### 13.6 Global validation

각 implementation slice에서 최소한 다음을 실행한다.

```bash
PYTHONPATH=src python3 -m compileall -q src tests
PYTHONPATH=src python3 -m unittest discover -s tests -q
python3 -m tabnanny src tests
git diff --check
git diff --cached --check
```

Repository에 configured lint 또는 type check가 있으면 함께 실행한다. Network, paid
provider call, real credential 또는 real classroom media를 사용하지 않는다.

---

## 14. Review Requirements

`implementation/050_IMPLEMENTATION_WORKFLOW.md`의 Risk-Based Workflow를 따른다.

기본 분류:

| Slice | Expected Classification | Reason |
| --- | --- | --- |
| 1. Assessment | Optional — Skipped | read-only architecture/design record |
| 2. Schema and Migration | Required — Executed | schema, migration, rollback, compatibility |
| 3. Provider/Segment Repositories | Optional — Skipped | approved schema 위 isolated repositories, boundary 변경 없을 때 |
| 4. Raw Transcript Atomic Persistence | Required — Executed | multi-record transaction and Application wiring |
| 5. Correction Candidate Persistence | Required — Executed | provenance command boundary and DomainResult composition |
| 6. Corrected Revision Persistence | Required — Executed | revision lineage and multi-record transaction |
| 7. Restart Acceptance | Optional — Skipped | test/composition-only일 때; production boundary 변경 시 Required |

실제 diff가 예상보다 높은 위험 경계를 바꾸면 `Required — Executed`로 상향한다.
Skipped review를 `PASS`로 표현하지 않는다.

Required review command:

```bash
claude -p \
  --allowedTools "Read" "Glob" "Grep" "Bash(git diff:*)" "Bash(git status:*)" \
  --disallowedTools "Edit" "Write" \
  --max-turns 6 \
  "먼저 .claude/review-code.md를 읽고, 그 지침에 따라 현재 staged diff를 리뷰하라."
```

리뷰는 actual staged diff와 relevant contracts를 읽어야 하며 다음 명시적 구조를
요구한다.

```text
Verdict: PASS | CHANGES_REQUIRED | BLOCKED

Blocking Issues:
- ...

Non-Blocking Issues:
- ...

Missing Tests:
- ...

Blueprint Clarification:
- Yes/No
- explanation

Review Basis:
- ...
```

명시적 verdict가 없으면 approval이 아니다. Blocking finding은 contract와 대조하고
최소 수정, focused/full validation, restage, required re-review를 거친다.

---

## 15. Commit Policy

각 slice는 정확히 하나의 logical commit으로 완료한다.

Commit 전에 반드시:

```text
focused tests pass
relevant regressions pass
complete suite pass
compile/static checks pass
diff checks pass
required review has explicit PASS
no Blocking Issue remains
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

## 16. Goal Self-Maintenance

이 Goal은 실행 중 repository의 active status record 역할을 한다.

각 successful slice 후 반드시:

1. 해당 slice를 `Completed Capabilities`에 commit hash와 함께 기록한다.
2. `Remaining Milestones`에서 제거한다.
3. immediate next slice를 갱신한다.
4. 실제 schema/repository/port/composition capability를 요약한다.
5. `implementation/060_IMPLEMENTATION_STATUS.md`를 동기화한다.
6. Architect Decision 또는 approved deviation의 근거를 history에 남긴다.
7. deferred scope가 우연히 완료된 것처럼 표현되지 않았는지 확인한다.

Goal 문서 변경은 해당 implementation slice의 상태 동기화로서 같은 logical commit에
포함할 수 있다. Goal history를 삭제하거나 완료된 evidence를 덮어쓰지 않는다.

### 16.1 Completed Capabilities

```text
Slice 1 — Transcript Persistence Composition Assessment
- commit `bb01ab4` — `docs: assess canonical transcript persistence`
- Architect Decisions recorded in this Goal and implementation status
- selected target schema: v5
- provider provenance: Transcript-owned immutable provenance record, not a
  separate product aggregate
- DomainResultReference: existing v4 canonical storage reused; producing
  Transcript command owns first insertion for its result identity
- command-specific atomic record sets approved

Slice 2 — Complete Transcript Schema and Migration
- commit `f7d9766` — `feat: add canonical transcript sqlite schema`
- complete SQLite schema v5 direct initialization
- explicit transactional v4-to-v5 migration and validated v5 no-op
- strict v5 table, column, owned-child foreign-key and representation constraints
- frozen v1-v4 compatibility and no canonical Transcript backfill
- Required Claude Review: PASS (20-turn final focused review; prior 6/10-turn
  runs ended without verdict)

Slice 3 — Provider Provenance Resolution and Segment Repository
- commit `4fc8028` — `feat: persist transcript source records in sqlite`
- `SQLiteProviderTranscriptResultRepository`
- `SQLiteTranscriptSegmentRepository`
- exact immutable round-trip, ordered duplicate diagnostic preservation,
  collision rejection, atomic standalone save, restart durability and v5 gate
- Claude Review: Optional — Skipped (approved isolated repository pattern)

Slice 4 — Raw Transcript Atomic Persistence
- commit `2e8abdd` — `feat: persist raw transcripts atomically`
- `AtomicRawTranscriptPersistence` Application port and in-memory adapter
- `SQLiteRawTranscriptRepository` and reusable non-committing writer
- `SQLiteTranscriptCommandPersistence.persist_raw_transcript(...)`
- atomic RawTranscript + all supplied new Segments + DomainResultReference
- `TranscriptService.create_raw_transcript(...)` exactly-once port wiring
- collision, linkage, write/commit rollback and restart integration coverage
- Required Claude Review: PASS (20-turn focused rerun after 6-turn run ended
  without verdict; no Blocking Issues or Missing Tests)

Slice 5 — Correction Candidate Persistence
- `SQLiteCorrectionCandidateRepository`
- `AtomicCorrectionCandidatePersistence` Application port and in-memory adapter
- atomic CorrectionCandidate + generated DomainResultReference command
- exact ordered evidence and optional provider/plugin/capability provenance
- `TranscriptService.create_correction_candidate(...)` exactly-once wiring
- collision, linkage, write/commit rollback and restart integration coverage
- Required Claude Review: PASS (20-turn focused rerun after 6-turn run ended
  without verdict; no Blocking Issues)
- reviewer-suggested non-null target revision round-trip test added
```

### 16.2 Remaining Milestones

```text
6. Corrected Transcript Revision Persistence
7. Canonical Transcript Composition and Restart Acceptance
```

### 16.3 Immediate Next Slice

```text
Corrected Transcript Revision Persistence
```

### 16.4 Architecture Decision History

Slice 1부터 다음 decision을 이 표에 누적 기록하고
`implementation/060_IMPLEMENTATION_STATUS.md`와 동기화한다. `Pending`은 Goal이 outcome을
선결정하지 않았다는 뜻이다.

| Decision Group | Status | Approved Decision | Evidence / Commit |
| --- | --- | --- | --- |
| selected target schema version | Approved | v5. Frozen v4에는 Transcript structures가 없고 다음 연속 version이므로 complete Transcript foundation을 v5 한 version으로 release한다. | Slice 1, `bb01ab4` |
| provider provenance ownership | Approved | `ProviderTranscriptResult`는 독립 product aggregate가 아니라 Transcript-owned immutable provenance record다. Existing `DomainResultReference`는 original provider content, capability, run/execution provenance를 복원할 수 없으므로 duplicate canonical owner가 아니다. v5에 normalized storage와 repository를 둔다. | Slice 1, `bb01ab4` |
| DomainResultReference ownership | Approved | v4의 canonical table/repository가 record storage를 계속 소유한다. Raw, Candidate, Revision을 생산하는 Transcript command가 해당 identity의 first insertion을 같은 transaction에서 수행한다. Transcript body를 `ExecutionService.record_results()`에 다시 신규 Result로 제출하지 않는다. Existing Execution terminal Result API의 다른 result semantics는 변경하지 않으며, 두 Application services를 결합하는 terminal orchestration은 이 foundation 밖의 후속 assessment 대상이다. | Slice 1, `bb01ab4` |
| transaction boundaries | Approved | provider registration = ProviderTranscriptResult 1개. raw creation = RawTranscript + supplied new TranscriptSegments + generated DomainResultReference. candidate creation = CorrectionCandidate + generated DomainResultReference. revision creation = CorrectedTranscriptRevision + only genuinely new supplied TranscriptSegments + generated DomainResultReference. Reads와 lifecycle/lineage validation은 Application에서 first write 전에 끝내고 SQLite adapter는 representation linkage와 identity absence만 확인한다. | Slice 1, `bb01ab4` |
| approved sequence changes | None | 현재 Section 12 순서 유지 | Goal baseline |

결정이 바뀌거나 sequence가 조정되면 기존 row를 삭제하지 않고 dated history row를
추가한다. 별도 assessment document는 decision과 evidence를 이 section 및 implementation
status에 합리적으로 기록할 수 없을 때만 만든다.

#### Slice 1 command and ownership evidence

- `ProviderTranscriptResult`는 `RawTranscript.provider_result_id`가 가리키는 exact
  provenance body이며 provider 원문, capability, plugin, diagnostics와 uncertainty를
  보존한다. `DomainResultReference`만으로 이 body를 reconstruct할 수 없다.
- `TranscriptService`는 provider registration, raw creation, candidate creation와
  revision creation을 별도 public commands로 제공한다. 각 command는 모든 Domain 및
  execution/lineage validation을 first write 전에 수행한다.
- Raw와 Revision은 ordered segment identity tuples를 소유하지만 Segment body를
  embedded snapshot으로 소유하지 않는다. Raw command의 supplied segments는 모두 new다.
  Revision command는 identical existing segments를 reuse하고 absent supplied segments만
  insert한다.
- Candidate와 Revision의 `domain_result_id`는 해당 concrete Transcript record의
  canonical cross-pipeline identity reference다. Generated `DomainResultReference`는
  concrete body가 아니라 lineage/reference boundary이므로 둘은 같은 command에서
  atomic하게 first-insert되어야 한다.
- Existing `ExecutionService.record_results()`는 supplied Results가 new라는 terminal
  command contract를 가진다. 이 Goal은 그 contract를 바꾸거나 이미 inserted Transcript
  Result를 재삽입하지 않는다. Durable execution terminal orchestration과 Transcript
  production을 하나의 public command로 결합하는 것은 canonical foundation 완료 후
  별도 milestone에서 평가한다.
- Public Transcript repository protocols는 변경하지 않는다. Multi-record commands는
  Application-owned ports를 사용하고 SQLite-only non-committing writers는 persistence
  package 내부에 유지한다.
- Schema validation, collision, representation linkage, SQLite write와 commit failure는
  existing persistence taxonomy로 전달한다. Domain/lifecycle errors는 first write 전에
  발생하며 persistence error로 포장하지 않는다.

---

## 17. Stop Conditions

다음 중 하나라도 발생하면 자동 진행을 중단한다.

### 17.1 Blueprint or Domain ambiguity

- current Transcript model과 released Blueprint가 모순된다.
- TranscriptSegment implementation을 canonical Transcript Unit product term으로
  승격해야만 구현할 수 있다.
- CorrectionCandidate, revision 또는 Review Decision의 Domain meaning을 바꿔야 한다.
- 현재 revision parent/applicability 의미로 restart-safe lineage를 표현할 수 없다.
- 새 canonical concept 또는 product contract가 필요하다.

### 17.2 Ownership ambiguity

- Transcript command와 Execution terminal Result command 사이의
  DomainResultReference ownership을 하나의 approved boundary로 확정할 수 없다.
- atomicity를 보장하려면 기존 approved Execution transaction contract를 깨야 한다.
- Application과 Persistence 사이에서 lifecycle 또는 provenance authority가 이동한다.

### 17.3 Schema or migration blocker

- released schema v4의 의미를 변경해야 한다.
- explicit migration policy로 complete target schema를 만들 수 없다.
- migration rollback 또는 old-data preservation을 보장할 수 없다.
- requested record shape가 current Domain model을 exact reconstruction할 수 없다.

### 17.4 Review or validation blocker

- Required Claude Review가 explicit verdict 없이 종료된다.
- Required review가 `BLOCKED`이거나 unresolved Blocking Issue가 남는다.
- focused 또는 full test failure를 current slice 안에서 안전하게 해결할 수 없다.
- configured validation을 실행할 수 없고 사용자 승인 없이 우회해야 한다.

### 17.5 Repository state blocker

- unrelated user changes가 current slice와 겹친다.
- working tree 또는 HEAD 불일치를 안전하게 해석할 수 없다.
- commit history를 파괴하거나 approved work를 discard해야만 진행할 수 있다.

중단 보고는 정확히 다음을 구분한다.

```text
Requires Architect Decision
Requires Blueprint Clarification
Requires Blueprint PATCH
Operational Blocker
```

SQLite table naming, serialization, migration sequencing 또는 internal writer shape만의
문제는 Blueprint ambiguity가 아니다.

---

## 18. Explicitly Deferred Scope

이 Goal 완료 후에도 다음은 별도 assessment와 Goal이 필요하다.

```text
Real Transcript Correction Candidate generation
Correction provider boundary
Transcript Review Handoff
Review Item and Review Decision durability
Transcript Validation record durability
Transcript applicability/current-selection durability
Subtitle canonical persistence
Subtitle Review and Final Selection durability
Artifact canonical persistence and materialization policy
Diagnostic canonical persistence, when a resolving production consumer exists
long-media/chunking
Lecture Intelligence
plugin runtime
quality optimization
```

권장 후속 milestone은 이 Goal의 acceptance evidence를 바탕으로 다시 assessment한다.
Review persistence가 없는데 production Human Review completion을 주장하지 않는다.

---

## 19. Consolidated Completion Report

Goal의 모든 slice가 완료되면 다음 구조로 하나의 consolidated report를 작성한다.

```text
## Summary

## Repository Status

## Blueprint and Contract Basis

## Completed Slice Commits

## Architecture Decisions

## Schema and Migration

## Canonical Transcript Repositories

## Atomic Persistence Boundaries

## Application Wiring

## Transcript Lineage

## Feature Gating

## Error and Rollback Semantics

## Tests and Validation

## Claude Reviews

## Manual Restart Acceptance

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
- schema version and supported/rejected migration paths
- exact repository and Application port inventory
- transaction record sets and ownership
- restart acceptance evidence
- focused and full test counts/results
- every Claude Review classification, budget, explicit verdict and findings
- corrections made after review
- sensitive/provider artifacts가 commit되지 않았다는 확인
- excluded scope가 구현되지 않았다는 확인

Final Verdict는 다음으로 끝낸다.

```text
Canonical Transcript foundation across restart: VERIFIED | BLOCKED

Requires Architect Decision: Yes/No
Requires Blueprint Clarification: Yes/No
Requires Blueprint PATCH: Yes/No
```

---

## 20. Goal Completion Condition

다음 조건을 모두 만족할 때만 이 Goal을 complete로 표시한다.

```text
complete canonical Transcript schema released at the selected target version
explicit migration validated
all included repositories implemented
all approved atomic command boundaries implemented
TranscriptService durable wiring complete
exact lineage survives restart
DomainResultReference ownership resolved without collision
all focused and regression tests pass
all required reviews return explicit PASS
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
Goal Complete — next product milestone requires a fresh Blueprint-order assessment
```
