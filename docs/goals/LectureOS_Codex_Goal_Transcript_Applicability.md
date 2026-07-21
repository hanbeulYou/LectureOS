# LectureOS Codex Goal — Transcript Applicability

## 1. Mission

이 Goal은 완료된 Transcript Human Review Decision 위에서 canonical Human Review
Decision으로부터 Transcript Revision의 applicability를 **결정론적으로 도출(derive)** 하고
durable하게 기록하는 provider-independent Application capability를 구축한다.

이 Goal의 목적은 새로운 판단을 만드는 것이 아니라, 이미 기록된 canonical Human Review
Decision(Accept/Reject/Modify)으로부터 proposed Revision의 applicability를 immutable하게
평가·기록하고, 그 evaluation provenance·decision lineage·revision linkage·DomainResult
linkage를 보존하며, 이를 atomic SQLite persistence와 restart reconstruction, deterministic
replay로 보장하는 계약을 완성하는 것이다.

Applicability는 오직 canonical Human Review Decision으로부터만 도출된다. Provider는 아무런
책임이 없다. 이 Goal은 Current Selection, Transcript Ready, Subtitle 생성으로 진행하지 않는다.

보존해야 하는 architecture:

```text
Product
→ Application
→ Capability
→ Provider
```

그리고 lifecycle 위치:

```text
Transcript
→ Proposed Revision
→ Review Preparation
→ Human Review Decision
→ Applicability              ← 이 Goal
→ Current Selection          (범위 밖)
→ Transcript Ready           (범위 밖)
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
`implementation/060_IMPLEMENTATION_STATUS.md`, 완료된 Human Review Decision Goal과 현재
`TranscriptReviewDecision` aggregate 및 기존 in-memory `transcript/applicability.py`를 확인한다.

Goal 시작 baseline:

```text
HEAD 202c7b8
Branch main
Working Tree Clean
SQLITE_SCHEMA_VERSION 7
```

## 3. Bounded Architectural Assessment

### 3.1 관찰된 현재 상태

- Canonical `TranscriptReviewDecision` aggregate(v7)는 applicability 도출에 필요한 모든
  linkage를 이미 보유한다: `domain_result_id`, `review_item_id`, `candidate_reference_id`,
  `source_revision_id`, `kind`(ACCEPT/REJECT/MODIFY). `SQLiteTranscriptReviewDecisionRepository`
  `.get()`으로 조회 가능하다.
- 기존 in-memory `transcript/applicability.py`의 `TranscriptApplicabilityService`는 더 넓은
  별개의 관심사다: 수동 applicability 명령(mark_stale/supersede/mark_historical)과 **Current
  Selection**(`select_current_revision`)을 포함하고, 구 review vocab(`ReviewDecisionId`,
  `ApprovedDecisionId`)에 연결되며 durable하지 않다. canonical Human Review Decision으로부터
  도출되지 않는다.
- `TranscriptApplicability` enum과 위 in-memory service는 이 Goal의 범위와 다르며, 수정하지
  않는다.

### 3.2 Architect Decision

Transcript Applicability는 다음으로 구현한다.

- 기존 `TranscriptApplicabilityService`(in-memory), `TranscriptApplicability` enum,
  `TranscriptReviewDecision`, review 모델을 **수정하지 않는다**(직전 두 milestone이 in-memory
  `ReviewService`를 수정하지 않은 것과 동일한 규율).
- Application-owned 신규 aggregate `TranscriptApplicabilityEvaluation` 하나를 **추가**한다.
  이 aggregate가 evaluation identity, 도출된 `ApplicabilityOutcome`, source Human Review
  Decision linkage(decision id + kind), Review Item / Candidate / Revision linkage,
  execution provenance, append-only sequence/previous linkage, deterministic reason,
  DomainResult linkage를 담는다.
- 신규 focused enum `ApplicabilityOutcome`을 추가한다(값 분류이며 identity 아님):
  `APPLICABLE`(Accept), `NOT_APPLICABLE`(Reject), `SUPERSEDED_BY_MODIFICATION`(Modify).
  이는 decision kind의 순수 결정론적 함수이며 current-selection/ready를 의미하지 않는다.
- Correction/Preparation/Decision service를 mirror하는 신규 Application service
  `TranscriptApplicabilityEvaluationService`를 추가한다(`prepare_evaluation` 순수 계산 /
  `record_evaluation` persist 경로, Application-owned identity plan).
- Evaluation 하위 집합만을 위한 additive SQLite schema **v8**, atomic command, repository,
  composition wiring, restart reconstruction, deterministic replay를 추가한다.

**Deterministic evaluation/replay 보장**: applicability는 loaded canonical decision의 kind에
대한 순수 함수이며 wall-clock을 사용하지 않는다. 동일 decision과 identity plan을 재입력하면
byte-identical evaluation 기록이 재구성된다.

Provider는 applicability에 아무 책임이 없다. Applicability identity와 lifecycle은 Application이
소유한다.

### 3.3 Architect Checklist 결과

AGENTS.md checklist 전 항목 **No**:

- 기존 Domain contract 변경 없음(`TranscriptApplicability` enum, in-memory applicability
  service, review 모델, decision aggregate 불변; 신규 aggregate는 additive).
- released schema 의미 변경 없음(additive v8).
- lifecycle authority 변경 없음(applicability는 도출이며 Human Authority를 행사하지 않음;
  자동 current-selection/ready 없음).
- Domain/Application/Persistence 책임 이동 없음(Application이 applicability identity/lifecycle/
  persistence/provenance/reconstruction 소유; provider 무책임).
- 신규 identity 의미 없음(`OpaqueIdentity` 파생 신규 id 하나; `ApplicabilityOutcome`은 값
  분류).
- 하나의 additive migration 외 새로운 migration 요구 없음.
- Blueprint 모순 없음(lifecycle과 일치; Current Selection/Ready 제외).

**결론: 실질적 architectural blocker 없음. Goal을 실행한다.**

## 4. Scope

Included:

- canonical Applicability model (신규 aggregate `TranscriptApplicabilityEvaluation`)
- deterministic applicability evaluation (decision kind → `ApplicabilityOutcome`)
- immutable applicability records
- evaluation provenance (run/unit execution)
- decision lineage (source `TranscriptReviewDecision` linkage + append-only sequence)
- revision linkage (source Revision)
- DomainResult linkage (신규 kind "transcript_applicability_evaluation")
- atomic SQLite persistence (additive schema v8)
- restart reconstruction
- deterministic replay
- fake-review acceptance

Excluded (구현하지 않는다):

- Current Selection, Transcript Ready
- Subtitle generation, Artifact generation
- automatic publication, automatic export
- Review redesign, Human Decision redesign
- applicability evaluation을 넘어서는 policy engine
- provider changes, plugin runtime, registry, UI, long-media execution

Applicability는 오직 canonical Human Review Decision으로부터만 도출된다.

## 5. Responsibility Boundary

Application이 소유한다: Applicability identity, lifecycle, persistence, provenance,
reconstruction, evaluation 결정성. Persistence는 승인된 상태를 serialize/deserialize하고
atomic transaction·rollback·schema gate를 담당한다. Provider는 applicability에 관여하지 않는다.
Applicability 도출은 어떤 current selection·ready·downstream 자동화도 트리거하지 않는다.

## 6. Canonical Applicability Model

### 6.1 신규 identity

- `TranscriptApplicabilityEvaluationId`(`OpaqueIdentity` 파생, `application/identities.py`)

### 6.2 신규 outcome enum `ApplicabilityOutcome`

- `APPLICABLE` (Accept decision)
- `NOT_APPLICABLE` (Reject decision)
- `SUPERSEDED_BY_MODIFICATION` (Modify decision)

### 6.3 신규 aggregate `TranscriptApplicabilityEvaluation`

최소 필드:

- `identity: TranscriptApplicabilityEvaluationId`
- `domain_result_id: DomainResultId` (DomainResult linkage)
- `source_decision_id: TranscriptReviewDecisionId` (Review Decision linkage)
- `decision_kind: DecisionKind` (도출 근거)
- `outcome: ApplicabilityOutcome` (도출 결과)
- `review_item_id: ReviewItemId` (Review Item linkage)
- `candidate_reference_id: CandidateReferenceId` (Candidate linkage)
- `source_revision_id: TranscriptRevisionId` (Revision linkage)
- `run_id`, `unit_execution_id` (execution provenance)
- `sequence: int`, `previous_evaluation_id: TranscriptApplicabilityEvaluationId | None`
  (append-only lineage)
- `reason: str` (deterministic, non-empty)

불변식: sequence ≥ 0; outcome은 decision_kind의 결정론적 매핑과 일치; reason 비어있지 않음;
first evaluation(sequence 0)은 previous 참조 없음.

### 6.4 Identity plan

`ApplicabilityEvaluationIdentityPlan`:

- `evaluation_id: TranscriptApplicabilityEvaluationId`
- `evaluation_result_id: DomainResultId`

plan은 command 입력이며 결정론적이다.

## 7. Persistence Model

- additive SQLite schema **v8**(현재 7). 기존 table 의미 변경 없음.
- 신규 table: applicability evaluation aggregate root(scalar 필드) 하나. child 없음.
- evaluation의 `DomainResultReference`는 기존 domain result table에 co-persist(신규 kind
  "transcript_applicability_evaluation", upstream = source decision domain result).
- 하나의 atomic command `SQLiteApplicabilityEvaluationCommandPersistence`가 evaluation
  record와 DomainResultReference를 단일 `BEGIN IMMEDIATE` transaction으로 쓰고 실패 시
  rollback한다. 기존 command pattern(identity absence 확인, linkage 검증, 공유 insert helper,
  exception ladder)을 mirror한다.
- restart reconstruction: 재오픈한 DB에서 evaluation aggregate가 동일하게 복원된다.
- deterministic replay: 동일 decision·identity plan을 새 DB에 재평가하면 동일 record가
  재구성된다.

## 8. Slice Sequence

### Slice 1 — Goal Baseline and Assessment

이 Goal 문서와 implementation status assessment 기록. Review: Optional — Skipped. Commit:

```text
docs: add transcript applicability goal
```

### Slice 2 — Applicability Records

`TranscriptApplicabilityEvaluationId`, `ApplicabilityOutcome`, `TranscriptApplicabilityEvaluation`
aggregate, `ApplicabilityEvaluationIdentityPlan`, prepared-result dataclass와 invariant,
exports, focused unit tests. Review: Required — Executed. Commit:

```text
feat: add transcript applicability records
```

### Slice 3 — Deterministic Applicability Evaluation Service

`TranscriptApplicabilityEvaluationService.evaluate_applicability(...)`가 durable Human Review
Decision을 로드해 kind로부터 outcome을 결정론적으로 도출하고 canonical evaluation aggregate를
구성한다(순수, persistence 없음). identity plan·decision/revision/item/candidate linkage·
execution provenance 검증. no-network in-memory acceptance. Review: Required — Executed. Commit:

```text
feat: evaluate transcript applicability from decisions
```

### Slice 4 — Atomic SQLite Persistence, Restart and Replay

additive schema v8 migration·table·repository·atomic command·composition wiring,
`record_evaluation` persist 경로, restart reconstruction, deterministic replay,
migration/persistence tests. Review: Required — Executed. Commit:

```text
feat: persist transcript applicability atomically
```

### Slice 5 — Fake-Review Acceptance

fake review decisions(Accept/Reject/Modify) → applicability 도출 → atomic persist → 재오픈 →
동일 복원 → 동일 replay end-to-end acceptance. immutable Applicability records, Review Decision
linkage, Review Item linkage, Candidate linkage, Revision linkage, execution provenance,
deterministic evaluation, restart reconstruction, structural integrity를 검증한다.
Review: Required only if production boundary changes; otherwise Optional — Skipped. Commit:

```text
test: verify transcript applicability acceptance
```

## 9. Validation

모든 slice는 focused tests, 전체 unittest suite, `compileall`, `tabnanny`,
`git diff --check`, staged diff 확인을 실행한다. Required review는 AGENTS.md critical-only
정책을 따른다: staged diff 대상 bounded 6-turn 리뷰 하나, 검증된 미해결 critical defect만
차단. 명시적 PASS를 얻기 위한 재실행 금지.

이 Goal은 다음을 명시적으로 검증한다.

- immutable Applicability records
- Review Decision linkage
- Review Item linkage
- Candidate linkage
- Revision linkage
- execution provenance
- deterministic evaluation
- restart reconstruction
- structural integrity

## 10. Blueprint Drift Check

완료 전에 Blueprint Drift Check를 수행한다. 이 milestone이 이전 완료 milestone(Execution
Durability, Canonical Transcript Foundation, Correction Application Foundation, Concrete
Correction Provider, Review Preparation, Human Review Decision) 대비 architectural drift를
도입하지 않음을 검증한다: authority chain(Product→Application→Capability→Provider) 보존,
additive schema만 사용, 기존 aggregate/enum/service 불변, applicability는 canonical decision
으로부터만 도출, Current Selection/Ready 미구현.

## 11. Stop Conditions

다음 경우에만 중단한다.

- 검증된 Blueprint 또는 책임 계약 모순
- canonical decision이 Domain/Application 변경 없이 applicability를 표현할 수 없음
- 미해결 critical privacy/security/public-contract/identity/provenance defect
- additive migration이 기존 schema 의미를 바꿔야만 함
- 범위 밖 변경 없이는 test를 교정할 수 없음
- 관련 없는 repository 변경과 충돌
- 필요한 Architect Decision, Blueprint Clarification 또는 PATCH

Reviewer verdict 부재만으로는 Stop Condition이 아니다.

중단 시: 정확한 blocker, 현재 repository 상태, 정확한 resume 지점, 추측성 재설계 금지.

## 12. Goal Self-Maintenance

각 slice 후 이 Goal과 `implementation/060_IMPLEMENTATION_STATUS.md`를 갱신하고
commit/review/validation 근거를 기록하며, 완료 slice를 Remaining에서 제거하고 다음 slice를
지정한다. slice당 하나의 commit과 clean Working Tree를 요구한다.

### Completed Capabilities

```text
Slice 1 — Goal Baseline and Assessment
- commit `3ee4ac3` — `docs: add transcript applicability goal`
- bounded architectural assessment: no substantive blocker
- reuse canonical decision aggregate; add one Application-owned evaluation aggregate
- deterministic outcome mapping; additive schema v8 planned; existing applicability
  service and enum left unchanged
- Review: Optional — Skipped (documentation only)

Slice 2 — Applicability Records
- `TranscriptApplicabilityEvaluationId` added to application identities
- `ApplicabilityOutcome` enum (APPLICABLE / NOT_APPLICABLE / SUPERSEDED_BY_MODIFICATION)
  with `outcome_for_decision_kind` deterministic mapping from decision kind
- `TranscriptApplicabilityEvaluation` aggregate: identity, DomainResult linkage, source
  decision id + kind, derived outcome, review item / candidate / revision linkage, execution
  provenance, append-only sequence / previous linkage, deterministic reason
- `ApplicabilityEvaluationIdentityPlan` (evaluation id, result id)
- invariants: non-negative sequence, non-blank reason, outcome must match decision-kind
  mapping, first evaluation has no previous reference
- 9 focused record tests passed; complete suite 742 passed
- Required Claude Review: Inconclusive — no critical findings identified
  (additive immutable records; deterministic mapping; no Blueprint/lifecycle/contract defect)

Slice 3 — Deterministic Applicability Evaluation Service
- `TranscriptApplicabilityEvaluationService.evaluate_applicability(...)` deterministic pure
  derivation
- loads the durable canonical Human Review Decision, requires a running execution, derives
  the outcome from the decision kind via the single deterministic mapping, and carries the
  decision / review item / candidate / revision linkage into the evaluation
- evaluation DomainResult links upstream to the source decision DomainResult; no wall-clock
  is read; performs no canonical write
- `PreparedApplicabilityEvaluation` return; `AtomicApplicabilityEvaluationPersistence` port;
  `TranscriptApplicabilityEvaluationError` for unsafe input
- 7 focused service tests passed; complete suite 749 passed
- Required Claude Review: Inconclusive — no critical findings identified
  (pure deterministic derivation; linkage/execution provenance validated; no persistence,
  no selection, no automation)
```

### Remaining Milestones

```text
Slice 4 — Atomic SQLite Persistence, Restart and Replay
Slice 5 — Fake-Review Acceptance
```

### Immediate Next Slice

```text
Slice 4 — Atomic SQLite Persistence, Restart and Replay
```

## 13. Consolidated Completion Report

완료 시 다음을 반환한다.

```text
## Summary
## Repository Status
## Completed Commits
## Architecture Decisions
## Canonical Applicability Model
## Persistence Model
## Provenance
## Restart and Replay Acceptance
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
