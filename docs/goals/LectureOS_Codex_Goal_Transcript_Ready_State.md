# LectureOS Codex Goal — Transcript Ready State

## 1. Mission

이 Goal은 완료된 Transcript Current Selection 위에서, 현재 선택된 Transcript Revision이
downstream 사용을 위해 준비(ready)되었는지를 canonical records로부터 **결정론적으로 평가**하고
durable하게 기록하는 provider-independent Application capability를 구축한다.

이 Goal의 목적은 새로운 판단을 만드는 것이 아니라, 이미 기록된 canonical upstream records
(Current Selection, Applicability, Human Review Decision, Review Preparation lineage,
CorrectedTranscriptRevision, 그리고 그 Revision의 structural Validation)로부터 READY/NOT_READY를
immutable하게 평가·기록하고, 그 readiness provenance와 모든 linkage를 보존하며, 이를 atomic
SQLite persistence와 restart reconstruction, deterministic replay, idempotency로 보장하는 계약을
완성하는 것이다.

Transcript Ready는 오직 canonical records로부터만 도출된다. Provider는 readiness에 아무런
책임이 없다. READY 기록은 어떤 downstream capability도 자동으로 시작하지 않는다. NOT_READY 기록은
어떤 upstream record도 변경/삭제/거부/supersede하지 않는다. Current Selection과 Transcript Ready는
서로 별개의 canonical 관심사로 남는다; SELECTED 자체가 READY를 의미하지 않는다.

보존해야 하는 architecture:

```text
Product
→ Application
→ Capability Contract
→ Provider
```

그리고 lifecycle 위치:

```text
Transcript Revision
→ Review Preparation
→ Human Review Decision
→ Applicability
→ Current Selection
→ Transcript Ready          ← 이 Goal
→ Subtitle                  (범위 밖)
→ Artifact                  (범위 밖)
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
`docs/040_TRANSCRIPT_PIPELINE.md`, `docs/043_REVIEW_PIPELINE.md`, `patches/PATCH-0004-edit-pipeline.md`,
`implementation/040_INTERFACE_CONTRACTS.md`, `implementation/050_IMPLEMENTATION_WORKFLOW.md`,
`implementation/060_IMPLEMENTATION_STATUS.md`, 완료된 Current Selection Goal, 현재
`TranscriptCurrentSelection`/`TranscriptApplicabilityEvaluation`/`TranscriptReviewDecision`
aggregate와 `TranscriptStructuralValidationBoundary`/`TranscriptValidation` contract를 확인한다.

Goal 시작 baseline:

```text
HEAD d02ab80
Branch main
Working Tree Clean
SQLITE_SCHEMA_VERSION 9
```

## 3. Bounded Architectural Assessment

### 3.1 관찰된 현재 상태

- Canonical `TranscriptCurrentSelection` aggregate(v9)는 readiness 평가에 필요한 upstream
  linkage를 이미 보유한다: `source_applicability_id`, `applicability_outcome`, `outcome`
  (SELECTED/NOT_SELECTED), `source_decision_id`, `review_item_id`, `candidate_reference_id`,
  `source_revision_id`, execution provenance, `domain_result_id`. v9/v8/v7 repository로 durable
  하게 조회 가능하다.
- `CorrectedTranscriptRevision`은 durable(v5)하다. 그 structural Validation은
  `TranscriptStructuralValidationBoundary.validate_corrected_revision(...)`가 durable Revision과
  그 segments/provenance로부터 **결정론적으로 계산**하는 canonical `TranscriptValidation`이다.
  `TranscriptValidation`은 canonical Domain record지만 SQLite에 durable하게 저장되지 않는다.
- readiness 조건(SELECTED, exact Revision linkage, 성공적 structural Validation, 완전한 Review
  Preparation/Decision lineage, APPLICABLE, 모순 없는 review state, 완전한 execution/DomainResult
  provenance)은 모두 위 canonical durable records + 결정론적 structural Validation 재계산으로
  판정 가능하다. 추가 product policy가 필요하지 않다.

### 3.2 Architect Decision

Transcript Ready는 다음으로 구현한다.

- 기존 selection/applicability/decision/validation contract와 review 모델을 **수정하지 않는다**
  (직전 milestone들과 동일한 규율).
- Application-owned 신규 aggregate `TranscriptReadinessEvaluation` 하나를 **추가**한다. 이
  aggregate가 readiness identity, `ReadinessOutcome`(READY/NOT_READY), 결정론적
  `ReadinessReasonCode`, Current Selection linkage(+ selection outcome), Applicability linkage
  (+ applicability outcome), Review Decision linkage, Review Item linkage, Candidate linkage,
  Revision linkage, structural Validation linkage(+ structural_valid), execution provenance,
  append-only sequence/previous linkage, deterministic reason, DomainResult linkage를 담는다.
- 신규 focused enum 두 개를 추가한다(값 분류이며 identity 아님):
  - `ReadinessOutcome`: `READY`, `NOT_READY`.
  - `ReadinessReasonCode`: `ALL_CONDITIONS_MET`(READY), `NOT_SELECTED`, `NOT_APPLICABLE`,
    `SUPERSEDED_BY_MODIFICATION`, `STRUCTURAL_VALIDATION_FAILED`(모두 NOT_READY).
- 신규 Application service `TranscriptReadinessEvaluationService`를 추가한다
  (`evaluate_readiness` 계산 / `record_readiness` persist 경로, Application-owned identity plan).
  이 서비스는 durable Current Selection을 로드하고, 그 Applicability/Decision/Revision lineage를
  durable records로 교차 검증하며, 선택된 Revision에 대해 기존 structural Validation boundary를
  호출해 canonical `TranscriptValidation`을 결정론적으로 재계산하고, 아래 규칙으로 READY/NOT_READY를
  도출한다.
- Readiness 하위 집합만을 위한 additive SQLite schema **v10**, atomic command, repository,
  composition wiring, restart reconstruction, deterministic replay를 추가한다.

**Structural Validation 재계산 근거**: `TranscriptValidation`은 durable Revision의 순수 결정론적
함수이며 자체 durable aggregate가 아니다. 따라서 readiness 평가 시점에 기존 boundary로 재계산하고
그 결과 canonical Validation에 readiness record를 linkage한다. 이는 readiness를 canonical durable
records(Revision)와 결정론적 재계산으로부터만 도출하게 하여 restart 후 deterministic replay를
보존한다. 이 재계산은 어떤 durable upstream canonical record(v5..v9)도 변경하지 않는다.

**Deterministic evaluation/replay/idempotency 보장**: readiness outcome은 loaded canonical
records(selection outcome, applicability outcome)와 결정론적 structural Validation의 순수 함수이며
wall-clock을 사용하지 않는다. 동일 canonical input과 identity plan을 재입력하면 byte-identical
readiness 기록이 재구성된다. 재평가는 durable upstream state를 변경하지 않는다.

Provider는 readiness에 아무 책임이 없다. Readiness identity와 lifecycle은 Application이 소유한다.

### 3.3 Architect Checklist 결과

AGENTS.md checklist 전 항목 **No**:

- 기존 Domain contract 변경 없음(selection/applicability/decision/validation/review 모델 불변;
  신규 aggregate는 additive).
- released schema 의미 변경 없음(additive v10).
- lifecycle authority 변경 없음(readiness는 도출이며 Human Authority를 행사하지 않음; downstream을
  자동 시작하지 않음; upstream을 변경하지 않음).
- Domain/Application/Persistence 책임 이동 없음(Application이 readiness identity/lifecycle/
  persistence/provenance/reconstruction 소유; provider 무책임; Subtitle/Artifact/export 책임을
  Transcript 도메인으로 끌어들이지 않음).
- 신규 identity 의미 없음(`OpaqueIdentity` 파생 신규 id 하나; 두 enum은 값 분류).
- 하나의 additive migration 외 새로운 migration 요구 없음.
- Blueprint 모순 없음(lifecycle과 일치; Current Selection과 Transcript Ready 분리 유지).

**결론: 실질적 architectural blocker 없음. Goal을 실행한다.**

## 4. Scope

Included:

- canonical Transcript Ready evaluation model (신규 aggregate `TranscriptReadinessEvaluation`)
- deterministic readiness evaluation (canonical records → `ReadinessOutcome` + `ReadinessReasonCode`)
- immutable readiness records; explicit READY / NOT_READY outcomes; deterministic reason codes
- Current Selection / Applicability / Review Decision / Review Item / Candidate / Revision /
  structural Validation linkage
- execution provenance; DomainResult linkage(신규 kind "transcript_readiness_evaluation")
- atomic SQLite persistence(additive schema v10); restart reconstruction; deterministic replay;
  idempotency verification
- fake-review / fake-transcript acceptance

Excluded (구현하지 않는다):

- Subtitle generation, Subtitle Candidate creation, Artifact generation, automatic export,
  downstream execution, publication, delivery
- provider changes, correction-provider calls
- Review Preparation / Human Review Decision / Applicability / Current Selection redesign
- automatic selection changes, readiness와 무관한 policy engine
- UI, provider registry, plugin runtime, long-media execution

READY 기록은 어떤 downstream capability도 자동 시작하지 않는다. NOT_READY 기록은 어떤 upstream
record도 변경/삭제/거부/supersede하지 않는다.

## 5. Responsibility Boundary

Application이 소유한다: Readiness identity, readiness evaluation, lifecycle, persistence,
provenance, reconstruction, 결정성. Persistence는 승인된 상태를 serialize/deserialize하고 atomic
transaction·rollback·schema gate를 담당한다. Provider는 readiness에 관여하지 않는다. Readiness
도출은 어떤 downstream 자동화도 트리거하지 않으며 upstream을 변경하지 않는다.

## 6. Canonical Transcript Ready Model

### 6.1 신규 identity

- `TranscriptReadinessEvaluationId`(`OpaqueIdentity` 파생, `application/identities.py`)

### 6.2 신규 enum

- `ReadinessOutcome`: `READY`, `NOT_READY`.
- `ReadinessReasonCode`: `ALL_CONDITIONS_MET`, `NOT_SELECTED`, `NOT_APPLICABLE`,
  `SUPERSEDED_BY_MODIFICATION`, `STRUCTURAL_VALIDATION_FAILED`.

### 6.3 신규 aggregate `TranscriptReadinessEvaluation`

최소 필드: `identity`, `domain_result_id`, `source_selection_id`, `selection_outcome`,
`source_applicability_id`, `applicability_outcome`, `source_decision_id`, `review_item_id`,
`candidate_reference_id`, `source_revision_id`, `validation_id`, `structural_valid`, `outcome`,
`reason_code`, `run_id`, `unit_execution_id`, `sequence`, `reason`, `previous_readiness_id`.

불변식(defense in depth): sequence ≥ 0; reason 비어있지 않음; first(sequence 0)은 previous 없음;
`outcome == READY` ⇔ `reason_code == ALL_CONDITIONS_MET`; READY는 반드시
`selection_outcome == SELECTED` AND `applicability_outcome == APPLICABLE` AND
`structural_valid == True`; NOT_READY의 reason_code는 그 위반을 결정론적으로 반영한다. 이로써
NOT_SELECTED, NOT_APPLICABLE, SUPERSEDED_BY_MODIFICATION, structurally invalid lineage에서
READY가 생성될 수 없다.

### 6.4 Readiness 결정 규칙(결정론적)

```text
if selection_outcome == NOT_SELECTED:
    if applicability_outcome == NOT_APPLICABLE            -> NOT_READY, NOT_APPLICABLE
    elif applicability_outcome == SUPERSEDED_BY_MODIFICATION -> NOT_READY, SUPERSEDED_BY_MODIFICATION
    else                                                 -> NOT_READY, NOT_SELECTED
elif selection_outcome == SELECTED:      # applicability_outcome == APPLICABLE 보장
    if not structural_valid              -> NOT_READY, STRUCTURAL_VALIDATION_FAILED
    else                                 -> READY, ALL_CONDITIONS_MET
```

Missing/모순 lineage(존재하지 않는 selection/applicability/decision/revision, 또는 durable
records 간 불일치)는 정상 NOT_READY가 아니라 명시적 error로 처리한다(canonical corruption).

### 6.5 Identity plan

`ReadinessEvaluationIdentityPlan`: `readiness_id`, `readiness_result_id`, `validation_id`.
plan은 command 입력이며 결정론적이다.

## 7. Persistence Model

- additive SQLite schema **v10**(현재 9). 기존 table 의미 변경 없음.
- 신규 table: readiness evaluation aggregate root(scalar 필드) 하나. child 없음.
- readiness의 `DomainResultReference`는 기존 domain result table에 co-persist(신규 kind
  "transcript_readiness_evaluation", upstream = source current selection domain result).
- 하나의 atomic command `SQLiteReadinessEvaluationCommandPersistence`가 readiness record와
  DomainResultReference를 단일 `BEGIN IMMEDIATE` transaction으로 쓰고 실패 시 rollback한다. 기존
  command pattern(identity absence 확인, linkage 검증, 공유 insert helper, exception ladder)을
  mirror한다.
- restart reconstruction: 재오픈한 DB에서 readiness aggregate가 동일하게 복원된다.
- deterministic replay: 동일 canonical input·identity plan을 새 DB에 재평가하면 동일 record가
  재구성된다.
- migration compatibility: 모든 이전 released schema version(v1..v9)에서 단일 step chain을 통해
  v10까지 도달하며 데이터 손실/의미 변경 없이 보존됨을 검증한다.

## 8. Slice Sequence

### Slice 1 — Goal Baseline and Assessment

이 Goal 문서와 implementation status assessment 기록. Review: Optional — Skipped. Commit:

```text
docs: add transcript ready state goal
```

### Slice 2 — Readiness Records

`TranscriptReadinessEvaluationId`, `ReadinessOutcome`, `ReadinessReasonCode`,
`TranscriptReadinessEvaluation` aggregate, `ReadinessEvaluationIdentityPlan`, prepared-result
dataclass와 invariant, exports, focused unit tests. Review: Required — Executed. Commit:

```text
feat: add transcript ready state records
```

### Slice 3 — Deterministic Readiness Evaluation Service

`TranscriptReadinessEvaluationService.evaluate_readiness(...)`가 durable Current Selection을
로드해 Applicability/Decision/Revision lineage를 교차 검증하고, 기존 structural Validation
boundary로 선택 Revision을 재검증하며, 결정론적으로 READY/NOT_READY와 reason code를 도출해
canonical readiness aggregate를 구성한다. no-network in-memory acceptance. Review: Required —
Executed. Commit:

```text
feat: evaluate transcript ready state from canonical records
```

### Slice 4 — Atomic SQLite Persistence, Restart, Replay and Migration Compatibility

additive schema v10 migration·table·repository·atomic command·composition wiring,
`record_readiness` persist 경로, restart reconstruction, deterministic replay, 모든 이전 released
version(v1..v9)에서 v10까지의 migration compatibility test, migration/persistence tests.
Review: Required — Executed. Commit:

```text
feat: persist transcript ready state atomically
```

### Slice 5 — Fake-Review / Fake-Transcript Acceptance

fake pipeline(Accept/Reject/Modify decisions → applicability → current selection → readiness)
end-to-end acceptance: accepted-selected-valid Revision → READY, rejected/modified lineage →
NOT_READY, atomic persist → 재오픈 → 동일 복원 → 동일 replay → 재평가 idempotency(upstream 불변),
downstream(Subtitle/Artifact) 미트리거를 검증한다. Review: Required only if production boundary
changes; otherwise Optional — Skipped. Commit:

```text
test: verify transcript ready state acceptance
```

## 9. Validation

모든 slice는 focused tests, 전체 unittest suite, `compileall`, `tabnanny`,
`git diff --check`, staged diff 확인을 실행한다. Required review는 AGENTS.md critical-only
정책을 따른다: staged diff 대상 bounded 6-turn 리뷰 하나, 검증된 미해결 critical defect만 차단.
명시적 PASS를 얻기 위한 재실행 금지.

이 Goal은 다음을 명시적으로 검증한다.

- readiness는 canonical upstream records로부터만 도출된다
- READY는 NOT_SELECTED Revision에 대해 생성될 수 없다
- READY는 NOT_APPLICABLE/SUPERSEDED_BY_MODIFICATION lineage에 대해 생성될 수 없다
- READY는 structurally invalid/missing Validation에 대해 생성될 수 없다
- readiness는 exact Revision/Current Selection lineage를 보존한다
- readiness records는 immutable하다
- duplicate identity/persistence collision은 atomic rollback된다
- 동일 canonical input·identity plan은 deterministic output을 생성한다
- SQLite restart 후 replay는 byte-equivalent canonical record를 생성한다
- 반복 평가는 upstream state를 변경하지 않는다(idempotency)
- 어떤 downstream Subtitle/Artifact operation도 트리거되지 않는다

## 10. Blueprint Drift Check and Migration Compatibility

완료 전에 Blueprint Drift Check를 수행한다. 이 milestone이 이전 완료 milestone 대비
architectural drift를 도입하지 않음을 명시적으로 검증한다: Product → Application → Capability
Contract → Provider 의존 방향 불변; provider가 readiness identity/policy/lifecycle를 소유하지
않음; 기존 canonical enum/aggregate/service 의미 불변; schema migration이 strictly additive;
downstream Subtitle/Artifact/export 책임이 Transcript 도메인으로 들어오지 않음; Human Authority
유지; Current Selection과 Transcript Ready의 분리 유지.

또한 모든 이전 released schema version(v1..v9)에서 신규 v10 schema까지 단일 step chain migration이
성공하고 기존 데이터와 의미를 보존함을 검증한다.

## 11. Stop Conditions

다음 substantive Stop Condition에만 중단한다.

- 해결되지 않은 Blueprint 모순
- 현재 contracts로 readiness policy가 실질적으로 미정의
- implementation level에서 안전하게 bound할 수 없는 Architect Decision
- atomicity/identity/provenance/Human Authority를 보존할 수 없음
- acceptance에 필요한 외부 dependency 부재

Reviewer 침묵, PASS 문구 부재, optional 개선, 명명 선호, 추측성 미래 우려, 비-critical
refactoring은 Stop Condition이 아니다.

중단 시: 정확한 blocker, 관련 contract 충돌 또는 미정의 policy, repository 상태, 완료 commits,
staged/unstaged 상태, 정확한 resume 지점, 필요한 Architect Decision 또는 Blueprint Clarification.

## 12. Goal Self-Maintenance

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
Slice 2 — Readiness Records
Slice 3 — Deterministic Readiness Evaluation Service
Slice 4 — Atomic SQLite Persistence, Restart, Replay and Migration Compatibility
Slice 5 — Fake-Review / Fake-Transcript Acceptance
```

### Immediate Next Slice

```text
Slice 1 — Goal Baseline and Assessment
```

## 13. Consolidated Completion Report

완료 시 다음을 반환한다.

```text
## Summary
## Repository Status
## Blueprint and Contract Basis
## Completed Commits
## Architecture Decisions
## Canonical Transcript Ready Model
## Readiness Rules
## Validation Linkage
## Persistence Model
## Provenance
## Restart and Replay Acceptance
## Migration Compatibility
## Idempotency Verification
## Tests and Validation
## Claude Reviews
## Blueprint Drift Check
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
