# LectureOS Codex Goal — Transcript Current Selection

## 1. Mission

이 Goal은 완료된 Transcript Applicability 위에서 canonical Applicability evaluation으로부터
어떤 Transcript Revision이 현재 선택(current)인지를 **결정론적으로 도출(derive)** 하고 durable
하게 기록하는 provider-independent Application capability를 구축한다.

이 Goal의 목적은 새로운 판단을 만드는 것이 아니라, 이미 기록된 canonical Applicability
evaluation으로부터 Revision의 current selection 여부를 immutable하게 도출·기록하고, 그 selection
provenance·applicability linkage·revision linkage·DomainResult linkage를 보존하며, 이를 atomic
SQLite persistence와 restart reconstruction, deterministic replay로 보장하는 계약을 완성하는
것이다.

Current Selection은 오직 canonical Applicability evaluation으로부터만 도출된다. Provider는 아무런
책임이 없다. Current Selection은 어떤 Revision이 현재 선택되었는지만 결정하며, **Transcript가
Ready임을 의미하지 않는다**. 이 Goal은 Transcript Ready, Subtitle 생성으로 진행하지 않는다.

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
→ Applicability
→ Current Selection          ← 이 Goal
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
`implementation/060_IMPLEMENTATION_STATUS.md`, 완료된 Applicability Goal과 현재
`TranscriptApplicabilityEvaluation` aggregate 및 기존 in-memory `transcript/applicability.py`를
확인한다.

Goal 시작 baseline:

```text
HEAD 63af2d9
Branch main
Working Tree Clean
SQLITE_SCHEMA_VERSION 8
```

## 3. Bounded Architectural Assessment

### 3.1 관찰된 현재 상태

- Canonical `TranscriptApplicabilityEvaluation` aggregate(v8)는 current selection 도출에 필요한
  모든 linkage를 이미 보유한다: `source_decision_id`, `outcome`(APPLICABLE/NOT_APPLICABLE/
  SUPERSEDED_BY_MODIFICATION), `review_item_id`, `candidate_reference_id`, `source_revision_id`,
  execution provenance, `domain_result_id`. `SQLiteTranscriptApplicabilityEvaluationRepository`
  `.get()`으로 조회 가능하다.
- 기존 in-memory `transcript/applicability.py`의 `CurrentTranscriptSelection`은 더 넓은 별개의
  관심사다: working-context 기반 수동 선택과 구 review vocab에 연결되며 durable하지 않고
  canonical Applicability evaluation으로부터 도출되지 않는다.
- 위 in-memory 모델과 서비스는 이 Goal의 범위와 다르며 수정하지 않는다.

### 3.2 Architect Decision

Transcript Current Selection은 다음으로 구현한다.

- 기존 `CurrentTranscriptSelection`(in-memory), `TranscriptApplicabilityService`,
  applicability/review 모델을 **수정하지 않는다**(직전 milestone들과 동일한 규율).
- Application-owned 신규 aggregate `TranscriptCurrentSelection` 하나를 **추가**한다. 이
  aggregate가 selection identity, 도출된 `CurrentSelectionOutcome`, source Applicability
  evaluation linkage(evaluation id + applicability outcome), decision / review item / candidate
  / revision linkage, execution provenance, append-only sequence/previous linkage,
  deterministic reason, DomainResult linkage를 담는다.
- 신규 focused enum `CurrentSelectionOutcome`을 추가한다(값 분류이며 identity 아님):
  `SELECTED`, `NOT_SELECTED`. 이는 applicability outcome의 순수 결정론적 함수다:
  APPLICABLE → SELECTED, NOT_APPLICABLE → NOT_SELECTED, SUPERSEDED_BY_MODIFICATION →
  NOT_SELECTED. Transcript Ready를 의미하지 않는다.
- Applicability service를 mirror하는 신규 Application service
  `TranscriptCurrentSelectionService`를 추가한다(`evaluate_selection` 순수 계산 /
  `record_selection` persist 경로, Application-owned identity plan).
- Selection 하위 집합만을 위한 additive SQLite schema **v9**, atomic command, repository,
  composition wiring, restart reconstruction, deterministic replay를 추가한다.

**Deterministic selection/replay 보장**: current selection은 loaded canonical applicability
evaluation의 outcome에 대한 순수 함수이며 wall-clock을 사용하지 않는다. 동일 evaluation과
identity plan을 재입력하면 byte-identical selection 기록이 재구성된다.

Provider는 current selection에 아무 책임이 없다. Selection identity와 lifecycle은 Application이
소유한다.

### 3.3 Architect Checklist 결과

AGENTS.md checklist 전 항목 **No**:

- 기존 Domain contract 변경 없음(`CurrentTranscriptSelection`, applicability/review 모델,
  evaluation aggregate 불변; 신규 aggregate는 additive).
- released schema 의미 변경 없음(additive v9).
- lifecycle authority 변경 없음(selection은 도출이며 Human Authority를 행사하지 않음; Transcript
  Ready를 생성하지 않음).
- Domain/Application/Persistence 책임 이동 없음(Application이 selection identity/lifecycle/
  persistence/provenance/reconstruction 소유; provider 무책임).
- 신규 identity 의미 없음(`OpaqueIdentity` 파생 신규 id 하나; `CurrentSelectionOutcome`은 값
  분류).
- 하나의 additive migration 외 새로운 migration 요구 없음.
- Blueprint 모순 없음(lifecycle과 일치; Transcript Ready 제외).

**결론: 실질적 architectural blocker 없음. Goal을 실행한다.**

## 4. Scope

Included:

- canonical Current Selection model (신규 aggregate `TranscriptCurrentSelection`)
- deterministic current-selection evaluation (applicability outcome → `CurrentSelectionOutcome`)
- immutable selection records
- selection provenance (execution + source applicability lineage)
- applicability linkage (source `TranscriptApplicabilityEvaluation`)
- revision linkage (source Revision)
- DomainResult linkage (신규 kind "transcript_current_selection")
- atomic SQLite persistence (additive schema v9)
- restart reconstruction
- deterministic replay
- fake-review acceptance

Excluded (구현하지 않는다):

- Transcript Ready
- Subtitle generation, Artifact generation, automatic export, downstream execution
- provider changes, Review redesign, Human Decision redesign, Applicability redesign
- plugin runtime, registry, UI, long-media execution

Current Selection은 어떤 Revision이 현재 선택되었는지만 결정하며 Transcript가 Ready임을 의미하지
않는다. Current Selection은 오직 canonical Applicability evaluation으로부터만 도출된다.

## 5. Responsibility Boundary

Application이 소유한다: Current Selection identity, lifecycle, persistence, provenance,
reconstruction, selection 결정성. Persistence는 승인된 상태를 serialize/deserialize하고 atomic
transaction·rollback·schema gate를 담당한다. Provider는 selection에 관여하지 않는다. Current
Selection 도출은 어떤 Transcript Ready·downstream 자동화도 트리거하지 않는다.

## 6. Canonical Current Selection Model

### 6.1 신규 identity

- `TranscriptCurrentSelectionId`(`OpaqueIdentity` 파생, `application/identities.py`)

### 6.2 신규 outcome enum `CurrentSelectionOutcome`

- `SELECTED` (applicability APPLICABLE)
- `NOT_SELECTED` (applicability NOT_APPLICABLE 또는 SUPERSEDED_BY_MODIFICATION)

### 6.3 신규 aggregate `TranscriptCurrentSelection`

최소 필드:

- `identity: TranscriptCurrentSelectionId`
- `domain_result_id: DomainResultId` (DomainResult linkage)
- `source_applicability_id: TranscriptApplicabilityEvaluationId` (Applicability linkage)
- `applicability_outcome: ApplicabilityOutcome` (도출 근거)
- `outcome: CurrentSelectionOutcome` (도출 결과)
- `source_decision_id: TranscriptReviewDecisionId` (decision lineage)
- `review_item_id: ReviewItemId` (Review Item linkage)
- `candidate_reference_id: CandidateReferenceId` (Candidate linkage)
- `source_revision_id: TranscriptRevisionId` (Revision linkage)
- `run_id`, `unit_execution_id` (execution provenance)
- `sequence: int`, `previous_selection_id: TranscriptCurrentSelectionId | None`
  (append-only lineage)
- `reason: str` (deterministic, non-empty)

불변식: sequence ≥ 0; outcome은 applicability_outcome의 결정론적 매핑과 일치; reason 비어있지
않음; first selection(sequence 0)은 previous 참조 없음.

### 6.4 Identity plan

`CurrentSelectionIdentityPlan`:

- `selection_id: TranscriptCurrentSelectionId`
- `selection_result_id: DomainResultId`

plan은 command 입력이며 결정론적이다.

## 7. Persistence Model

- additive SQLite schema **v9**(현재 8). 기존 table 의미 변경 없음.
- 신규 table: current selection aggregate root(scalar 필드) 하나. child 없음.
- selection의 `DomainResultReference`는 기존 domain result table에 co-persist(신규 kind
  "transcript_current_selection", upstream = source applicability evaluation domain result).
- 하나의 atomic command `SQLiteCurrentSelectionCommandPersistence`가 selection record와
  DomainResultReference를 단일 `BEGIN IMMEDIATE` transaction으로 쓰고 실패 시 rollback한다. 기존
  command pattern(identity absence 확인, linkage 검증, 공유 insert helper, exception ladder)을
  mirror한다.
- restart reconstruction: 재오픈한 DB에서 selection aggregate가 동일하게 복원된다.
- deterministic replay: 동일 evaluation·identity plan을 새 DB에 재평가하면 동일 record가
  재구성된다.
- migration compatibility: 모든 이전 released schema version(v1..v8)에서 단일 step chain을 통해
  v9까지 도달 가능함을 검증한다.

## 8. Slice Sequence

### Slice 1 — Goal Baseline and Assessment

이 Goal 문서와 implementation status assessment 기록. Review: Optional — Skipped. Commit:

```text
docs: add transcript current selection goal
```

### Slice 2 — Current Selection Records

`TranscriptCurrentSelectionId`, `CurrentSelectionOutcome`, `TranscriptCurrentSelection` aggregate,
`CurrentSelectionIdentityPlan`, prepared-result dataclass와 invariant, exports, focused unit
tests. Review: Required — Executed. Commit:

```text
feat: add transcript current selection records
```

### Slice 3 — Deterministic Current Selection Service

`TranscriptCurrentSelectionService.evaluate_selection(...)`가 durable Applicability evaluation을
로드해 outcome으로부터 selection을 결정론적으로 도출하고 canonical selection aggregate를
구성한다(순수, persistence 없음). identity plan·applicability/decision/item/candidate/revision
linkage·execution provenance 검증. no-network in-memory acceptance. Review: Required — Executed.
Commit:

```text
feat: select current transcript revision from applicability
```

### Slice 4 — Atomic SQLite Persistence, Restart, Replay and Migration Compatibility

additive schema v9 migration·table·repository·atomic command·composition wiring,
`record_selection` persist 경로, restart reconstruction, deterministic replay, 모든 이전 released
version(v1..v8)에서 v9까지의 migration compatibility test, migration/persistence tests.
Review: Required — Executed. Commit:

```text
feat: persist transcript current selection atomically
```

### Slice 5 — Fake-Review Acceptance

fake review decisions(Accept/Reject/Modify) → applicability 도출 → current selection 도출 →
atomic persist → 재오픈 → 동일 복원 → 동일 replay end-to-end acceptance. immutable Current
Selection records, Applicability linkage, Review Item linkage, Candidate linkage, Revision
linkage, execution provenance, deterministic selection, restart reconstruction, structural
integrity를 검증한다. Review: Required only if production boundary changes; otherwise Optional —
Skipped. Commit:

```text
test: verify transcript current selection acceptance
```

## 9. Validation

모든 slice는 focused tests, 전체 unittest suite, `compileall`, `tabnanny`,
`git diff --check`, staged diff 확인을 실행한다. Required review는 AGENTS.md critical-only
정책을 따른다: staged diff 대상 bounded 6-turn 리뷰 하나, 검증된 미해결 critical defect만 차단.
명시적 PASS를 얻기 위한 재실행 금지.

이 Goal은 다음을 명시적으로 검증한다.

- immutable Current Selection records
- Applicability linkage
- Review Item linkage
- Candidate linkage
- Revision linkage
- execution provenance
- deterministic selection
- restart reconstruction
- atomic persistence
- structural integrity

## 10. Blueprint Drift Check and Migration Compatibility

완료 전에 Blueprint Drift Check를 수행한다. 이 milestone이 이전 완료 milestone 대비
architectural drift를 도입하지 않음을 검증한다: authority chain 보존, additive schema만 사용,
기존 aggregate/enum/service 불변, current selection은 canonical applicability로부터만 도출,
Transcript Ready 미구현.

또한 모든 이전 released schema version(v1, v2, v3, v4, v5, v6, v7, v8)에서 신규 v9 schema까지
단일 step chain migration이 성공하고 기존 데이터를 보존함을 검증한다.

## 11. Stop Conditions

다음 경우에만 중단한다.

- 검증된 Blueprint 또는 책임 계약 모순
- canonical applicability가 Domain/Application 변경 없이 current selection을 표현할 수 없음
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
- commit `7333658` — `docs: add transcript current selection goal`
- bounded architectural assessment: no substantive blocker
- reuse canonical applicability aggregate; add one Application-owned selection aggregate
- deterministic outcome mapping; additive schema v9 planned; existing selection service
  and enum left unchanged
- Review: Optional — Skipped (documentation only)

Slice 2 — Current Selection Records
- `TranscriptCurrentSelectionId` added to application identities
- `CurrentSelectionOutcome` enum (SELECTED / NOT_SELECTED) with
  `selection_for_applicability_outcome` deterministic mapping (APPLICABLE→SELECTED,
  NOT_APPLICABLE/SUPERSEDED_BY_MODIFICATION→NOT_SELECTED)
- `TranscriptCurrentSelection` aggregate: identity, DomainResult linkage, source
  applicability id + outcome, derived selection outcome, decision / review item / candidate
  / revision linkage, execution provenance, append-only sequence / previous linkage,
  deterministic reason
- `CurrentSelectionIdentityPlan` (selection id, result id)
- invariants: non-negative sequence, non-blank reason, outcome must match applicability-outcome
  mapping, first selection has no previous reference
- 9 focused record tests passed; complete suite 769 passed
- Required Claude Review: Inconclusive — no critical findings identified
  (additive immutable records; deterministic mapping; no Blueprint/lifecycle/contract defect)

Slice 3 — Deterministic Current Selection Service
- `TranscriptCurrentSelectionService.evaluate_selection(...)` deterministic pure derivation
- loads the durable canonical Applicability evaluation, requires a running execution, derives
  the selection outcome from the applicability outcome via the single deterministic mapping,
  and carries the applicability / decision / review item / candidate / revision linkage into
  the selection
- selection DomainResult links upstream to the source applicability DomainResult; no wall-clock
  is read; performs no canonical write; never produces a Transcript Ready state
- `PreparedCurrentSelection` return; `AtomicCurrentSelectionPersistence` port;
  `TranscriptCurrentSelectionError` for unsafe input
- 7 focused service tests passed; complete suite 776 passed
- Required Claude Review: Inconclusive — no critical findings identified
  (pure deterministic derivation; linkage/execution provenance validated; no persistence,
  no Transcript Ready, no automation)
```

### Remaining Milestones

```text
Slice 4 — Atomic SQLite Persistence, Restart, Replay and Migration Compatibility
Slice 5 — Fake-Review Acceptance
```

### Immediate Next Slice

```text
Slice 4 — Atomic SQLite Persistence, Restart, Replay and Migration Compatibility
```

## 13. Consolidated Completion Report

완료 시 다음을 반환한다.

```text
## Summary
## Repository Status
## Completed Commits
## Architecture Decisions
## Canonical Current Selection Model
## Persistence Model
## Provenance
## Restart and Replay Acceptance
## Tests and Validation
## Claude Reviews
## Blueprint Drift Check
## Migration Compatibility
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
