# LectureOS Codex Goal — Transcript Review Preparation

## 1. Mission

이 Goal은 완료된 Transcript Correction Application Foundation, Concrete OpenAI
Correction Provider Adapter, Credentialed Acceptance 위에서 canonical Transcript
correction 제안을 Human Review 대상으로 **준비(prepare)** 하는 provider-independent
Application capability를 구축한다.

이 Goal의 목적은 Human Review 결정을 도입하거나 Transcript 상태를 변경하는 것이 아니다.
목적은 canonical proposed `CorrectedTranscriptRevision`과 그 `CorrectionCandidate`
집합을 입력으로 받아, deterministic mapping으로 canonical Review Item을 생성하고,
review ordering·candidate grouping·review metadata·provenance·DomainResult linkage를
Application 책임 아래 구성하며, 이를 atomic SQLite persistence와 restart
reconstruction으로 보존하는 계약을 완성하는 것이다.

Review Preparation은 순수하게 준비적(preparatory)이다. Human Authority, Accept/Reject/
Modify, applicability, current selection, Transcript Ready 상태는 이 Goal의 범위가 아니다.

보존해야 하는 architecture:

```text
Product
→ Application
→ Capability Contract
→ Provider
```

그리고 lifecycle 위치:

```text
Transcript
→ Proposed Revision
→ Review Preparation        ← 이 Goal
→ Human Review Decision      (범위 밖)
→ Applicability              (범위 밖)
→ Current Selection          (범위 밖)
```

Codex는 사용자가 각 slice마다 별도 prompt를 전달하지 않아도 다음 루프를 반복한다.

```text
현재 repository baseline 확인
→ 첫 번째 미완료 slice 선정
→ Blueprint와 active PATCH 확인
→ Architect Decision 필요 여부 판정
→ 한 개의 bounded slice 구현
→ focused tests와 전체 regression 실행
→ critical-only Claude Review 적용
→ 한 개의 logical commit 생성
→ Goal과 implementation status 동기화
→ Working Tree Clean 확인
→ 다음 slice로 계속
```

Stop Conditions에 해당하면 즉시 중단하고 원인을 보고한다.

## 2. Authority and Baseline

Authority order는 Released Blueprint, active PATCH, approved Goals, Domain/Application
contracts, implementation 순이다. 실행 시 `AGENTS.md`, `docs/031_ARCHITECTURE.md`,
`docs/040_TRANSCRIPT_PIPELINE.md`, `docs/043_REVIEW_PIPELINE.md`, `docs/050_PLUGIN_SYSTEM.md`,
`patches/PATCH-0004-edit-pipeline.md`, `patches/PATCH-0005-plugin-system.md`,
`implementation/040_INTERFACE_CONTRACTS.md`, `implementation/050_IMPLEMENTATION_WORKFLOW.md`,
`implementation/060_IMPLEMENTATION_STATUS.md`, 완료된 Correction Application/Provider Goals,
그리고 현재 `review/` 도메인과 Transcript Correction Generation Application service를 확인한다.

Goal 시작 baseline:

```text
HEAD 2437dcd
Branch main
Working Tree Clean
SQLITE_SCHEMA_VERSION 5
```

## 3. Bounded Architectural Assessment

### 3.1 관찰된 현재 상태

- `review/` 모듈은 전체 Human Review lifecycle(`CandidateReference`, `ReviewContext`,
  `ReviewItem`, `ReviewDecision`, `ApprovedDecision`, history/stale/conflict/reconciliation)을
  이미 **in-memory** domain으로 정의한다. Review Item·Context·Candidate Reference는 여러
  Pipeline이 공유하는 canonical review-preparation 어휘다.
- `043_REVIEW_PIPELINE.md §3.1`은 "Transcript 교정 후보"를 Review Item 대상으로 명시한다.
- Transcript Correction Generation Application은 canonical proposed
  `CorrectedTranscriptRevision`과 `CorrectionCandidate`(각각 `domain_result_id`, run/unit
  provenance, distinct target segment 보유)을 이미 생성·persist한다.
- SQLite persistence는 strictly additive versioned chain이며 현재 버전은 5다. Review
  domain에는 아직 durable repository가 없다.

### 3.2 Architect Decision

Transcript Review Preparation은 다음으로 구현한다.

- 기존 review domain type(`CandidateReference`, `ReviewContext`, `ReviewItem`)을 canonical
  review-preparation 어휘로 **재사용**한다. 기존 type은 수정하지 않는다.
- Application-owned 신규 aggregate `TranscriptReviewPreparation` 하나를 **추가**한다. 이
  aggregate가 review ordering, candidate grouping, review metadata, provenance,
  DomainResult linkage, source revision/candidate linkage, structural integrity를 담는다.
- Correction Generation service를 mirror하는 신규 Application service
  `TranscriptReviewPreparationService`를 추가한다(`prepare_review` 순수 계산 /
  `generate_review` persist 경로, Application-owned identity plan).
- Preparation 하위 집합만을 위한 additive SQLite schema **v6**, atomic command,
  repositories, composition wiring, restart reconstruction을 추가한다.

Provider는 변경하지 않는다(여전히 상류에서 `CorrectionCandidate`를 생성한다). Review
identity와 Review lifecycle은 Application이 소유하며 provider가 소유하지 않는다.

### 3.3 Architect Checklist 결과

AGENTS.md checklist 전 항목 **No**:

- 기존 Domain contract 변경 없음(신규 aggregate는 additive, 기존 review/transcript model
  불변).
- released schema 의미 변경 없음(additive v6).
- lifecycle authority 변경 없음(결정 없음; Human Authority 불변).
- Domain/Application/Persistence 책임 이동 없음(Application이 identity/ordering/
  persistence 소유; provider 불변).
- 신규 identity 의미 없음(`OpaqueIdentity` 파생 신규 id 하나).
- 하나의 additive migration 외 새로운 migration 요구 없음.
- Blueprint 모순 없음(preparation ≠ decision; provider-independence 보존).

**결론: 실질적 architectural blocker 없음. Goal을 실행한다.**

## 4. Scope

Included:

- provider-independent Transcript review preparation
- canonical Review Item generation (기존 `ReviewItem` 재사용)
- proposed `CorrectedTranscriptRevision` → review target으로의 deterministic mapping
- review ordering(canonical candidate 순서 보존)
- candidate grouping(target Transcript Segment 기준 deterministic grouping)
- review metadata(item count, source media/timeline 등)
- provenance preservation(run/unit execution, source media/timeline)
- DomainResult linkage(신규 `kind` "transcript_review_preparation")
- SQLite atomic persistence(additive schema v6)
- restart reconstruction
- fake-provider / fake-review acceptance
- structural validation where applicable(structural integrity 계산·보존)

Excluded (구현하지 않는다):

- Human approval 또는 rejection, Review Decision
- transcript applicability, current selection, Transcript Ready 상태
- automatic acceptance/rejection, policy engine, confidence threshold, AI self-approval
- subtitle generation, artifact generation, diagnostics
- provider registry, plugin runtime, multiple providers, long-media execution
- UI implementation
- 기존 review decision type 또는 canonical Domain 의미 변경
- provider가 소유하는 Review identity 또는 Review lifecycle

## 5. Responsibility Boundary

Application이 소유한다: Review identity, provenance, ordering, grouping, metadata,
structural integrity 계산, persistence 조율, reconstruction. Persistence는 승인된 상태를
serialize/deserialize하고 atomic transaction·rollback·schema gate를 담당한다. Provider는
review에 관여하지 않는다. Review Preparation은 어떤 Transcript 내용도 수정하지 않고 어떤
Human Decision도 만들지 않는다.

## 6. Canonical Review Preparation Model

### 6.1 신규 identity

- `TranscriptReviewPreparationId`(`OpaqueIdentity` 파생, `application/identities.py`)

### 6.2 신규 aggregate `TranscriptReviewPreparation`

최소 필드:

- `identity: TranscriptReviewPreparationId`
- `domain_result_id: DomainResultId` (DomainResult linkage)
- `source_transcript_id: TranscriptId`
- `source_revision_id: TranscriptRevisionId` (proposed revision)
- `run_id`, `unit_execution_id` (execution provenance)
- `source_media_id`, `source_timeline_id` (review metadata / provenance)
- `context_id: ReviewContextId`
- `candidate_reference_ids: tuple[CandidateReferenceId, ...]`
- `ordered_item_ids: tuple[ReviewItemId, ...]` (review ordering)
- `groups: tuple[ReviewItemGroup, ...]` (candidate grouping; group_key + ordered members)
- `item_count: int` (review metadata)
- `structural_valid: bool`, `provenance_complete: bool`, `ordering_valid: bool`
  (structural integrity)

불변식: item count 일치, ordered/grouped member 집합 일치, 최소 하나의 review item,
source media/timeline 비어있지 않음.

### 6.3 재사용 review domain type

- 각 `CorrectionCandidate` → 하나의 `CandidateReference`
  (`kind="transcript_correction_candidate"`, `source_domain="transcript"`,
  candidate의 `domain_result_id`·source media/timeline·run/unit provenance 보존,
  `revision_reference`=source revision, `applicability="undetermined"`).
- 하나의 `ReviewContext`(source media/timeline, DomainResult references, blocking 없음).
- 각 candidate reference → 하나의 `ReviewItem`(context 참조, decision/stale/conflict
  reference 없음 — 준비 상태).

### 6.4 Deterministic mapping 규칙

- review target 순서는 source revision의 `correction_candidate_ids` canonical 순서를 따른다.
- candidate reference·review item identity는 Application-owned identity plan에서 온다.
- grouping key는 candidate의 target Transcript Segment(`segment_id`)이며 deterministic하다.
- 동일 입력 + 동일 identity plan → 동일 canonical 출력(byte-stable).

### 6.5 Identity plan

`ReviewPreparationIdentityPlan`:

- `preparation_id`, `preparation_result_id`, `context_id`
- `targets: tuple[(candidate_reference_id, review_item_id), ...]`

plan은 고유성(모든 id distinct)·source candidate 개수 일치를 요구한다.

## 7. Persistence Model

- additive SQLite schema **v6**(현재 5). 기존 table 의미 변경 없음.
- 신규 table: preparation aggregate root, ordered item child, group member child,
  candidate reference, review context(+ tuple child), review item(+ tuple child).
- preparation의 `DomainResultReference`는 기존 domain result table에 co-persist(신규 kind
  "transcript_review_preparation", upstream = source revision domain result).
- 하나의 atomic command `SQLiteReviewPreparationCommandPersistence`가 모든 record를 단일
  `BEGIN IMMEDIATE` transaction으로 쓰고 실패 시 rollback한다. 기존 command pattern(identity
  absence 확인, linkage 검증, 공유 insert helper, exception ladder)을 mirror한다.
- ordinal child table은 기존 관례(composite PK, ordinal CHECK, ON DELETE CASCADE,
  복원 시 ordering 무결성 assert)를 따른다.
- restart reconstruction: 재오픈한 DB에서 aggregate와 재사용 review record가 동일하게
  복원된다.

## 8. Slice Sequence

### Slice 1 — Goal Baseline and Assessment

이 Goal 문서와 implementation status assessment 기록. Review: Optional — Skipped. Commit:

```text
docs: add transcript review preparation goal
```

### Slice 2 — Review Preparation Records

`TranscriptReviewPreparationId`, `TranscriptReviewPreparation` aggregate, `ReviewItemGroup`,
`ReviewPreparationIdentityPlan`, prepared-result dataclass와 invariant, exports, focused unit
tests. Review: Required — Executed. Commit:

```text
feat: add transcript review preparation records
```

### Slice 3 — Deterministic Review Preparation Service

`TranscriptReviewPreparationService.prepare_review(...)`가 canonical proposed revision과
candidate를 로드해 deterministic하게 review target·context·item·aggregate를 구성한다(순수,
persistence 없음). identity plan·lineage·candidate linkage·ordering 검증. no-network in-memory
acceptance. Review: Required — Executed. Commit:

```text
feat: prepare transcript corrections for review
```

### Slice 4 — Atomic SQLite Persistence and Restart

additive schema v6 migration·table·repository·atomic command·composition wiring,
`generate_review` persist 경로, restart reconstruction, migration/persistence tests.
Review: Required — Executed. Commit:

```text
feat: persist transcript review preparation atomically
```

### Slice 5 — Fake-Provider / Fake-Review Acceptance

fake correction provider → proposed revision → prepare review → atomic persist → 재오픈 →
동일 복원 end-to-end acceptance. deterministic generation, immutable lineage, parent revision
linkage, candidate linkage, execution provenance, restart reconstruction, atomic persistence,
structural integrity를 검증한다. Review: Required only if production boundary changes;
otherwise Optional — Skipped. Commit:

```text
test: verify transcript review preparation acceptance
```

## 9. Validation

모든 slice는 focused tests, 전체 unittest suite, `compileall`, `tabnanny`,
`git diff --check`, staged diff 확인을 실행한다. Required review는 AGENTS.md critical-only
정책을 따른다: staged diff 대상 bounded 6-turn 리뷰 하나, 검증된 미해결 critical defect만
차단. 명시적 PASS를 얻기 위한 재실행 금지.

이 Goal은 다음을 명시적으로 검증한다.

- deterministic Review Item generation
- immutable lineage
- parent Revision linkage
- Candidate linkage
- execution provenance
- restart reconstruction
- atomic persistence
- structural integrity

## 10. Stop Conditions

다음 경우에만 중단한다.

- 검증된 Blueprint 또는 책임 계약 모순
- 기존 review type이 Domain/Application 변경 없이 preparation을 표현할 수 없음
- 미해결 critical privacy/security/public-contract/identity/provenance defect
- additive migration이 기존 schema 의미를 바꿔야만 함
- 범위 밖 변경 없이는 test를 교정할 수 없음
- 관련 없는 repository 변경과 충돌
- 필요한 Architect Decision, Blueprint Clarification 또는 PATCH

Reviewer verdict 부재만으로는 Stop Condition이 아니다.

중단 시: 정확한 blocker, 현재 repository 상태, 정확한 resume 지점, 추측성 재설계 금지.

## 11. Goal Self-Maintenance

각 slice 후 이 Goal과 `implementation/060_IMPLEMENTATION_STATUS.md`를 갱신하고
commit/review/validation 근거를 기록하며, 완료 slice를 Remaining에서 제거하고 다음 slice를
지정한다. slice당 하나의 commit과 clean Working Tree를 요구한다.

### Completed Capabilities

```text
None yet
```

### Remaining Milestones

```text
Slice 1 — Goal Baseline and Assessment
Slice 2 — Review Preparation Records
Slice 3 — Deterministic Review Preparation Service
Slice 4 — Atomic SQLite Persistence and Restart
Slice 5 — Fake-Provider / Fake-Review Acceptance
```

### Immediate Next Slice

```text
Slice 1 — Goal Baseline and Assessment
```

## 12. Consolidated Completion Report

완료 시 다음을 반환한다.

```text
## Summary
## Repository Status
## Completed Commits
## Architecture Decisions
## Canonical Review Preparation Model
## Persistence Model
## Provenance
## Restart Acceptance
## Tests and Validation
## Claude Reviews
## Scope Confirmation
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
