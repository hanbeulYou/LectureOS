# LectureOS Codex Goal — Transcript Human Review Decision

## 1. Mission

이 Goal은 완료된 Transcript Review Preparation 위에서 준비된 Review Item에 대한
canonical Human Review Decision을 durable하게 기록하는 provider-independent Application
capability를 구축한다.

이 Goal의 목적은 Human의 Accept/Reject/Modify 판단을 canonical Decision 기록으로
남기고, 그 provenance(reviewer identity, decision timestamp, rationale, Review Item /
Candidate / Revision linkage, execution provenance, DomainResult linkage)를 보존하며,
이를 atomic SQLite persistence와 restart reconstruction, deterministic replay로 보장하는
계약을 완성하는 것이다.

Human Decision은 판단을 **기록**할 뿐이며 어떤 자동화도 트리거하지 않는다. 이 Goal은
Applicability, Current Selection, Transcript Ready, Subtitle 생성으로 진행하지 않는다.

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
→ Human Review Decision      ← 이 Goal
→ Applicability              (범위 밖)
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
`docs/043_REVIEW_PIPELINE.md`, `docs/040_TRANSCRIPT_PIPELINE.md`, `patches/PATCH-0004-edit-pipeline.md`,
`implementation/040_INTERFACE_CONTRACTS.md`, `implementation/050_IMPLEMENTATION_WORKFLOW.md`,
`implementation/060_IMPLEMENTATION_STATUS.md`, 완료된 Review Preparation Goal과 현재
`review/` 도메인(특히 `ReviewDecision`, `DecisionKind`, `HumanActorReference`)을 확인한다.

Goal 시작 baseline:

```text
HEAD 89c3d93
Branch main
Working Tree Clean
SQLITE_SCHEMA_VERSION 6
```

## 3. Bounded Architectural Assessment

### 3.1 관찰된 현재 상태

- `review/` 모듈은 canonical decision 어휘를 이미 in-memory로 정의한다: `ReviewDecision`
  (reviewer `actor`, `kind`, `rationale`, review item/candidate linkage, `sequence`,
  `previous_decision_id`), `DecisionKind`(ACCEPT/REJECT/MODIFY), `HumanActorReference`,
  `DecisionModification`.
- 이 decision 기록들은 durable하게 persist되지 않는다(SQLite table 없음).
- `043_REVIEW_PIPELINE.md`는 Review Decision, Accept/Reject/Modify, Human Authority,
  Decision Provenance, Decision Persistence를 명시하며 자동 승인/자동 적용을 금지한다.
- 완료된 Review Preparation은 durable(v6) Review Item, Review Context, Candidate
  Reference, Preparation aggregate(`source_revision_id` 포함)를 제공하고 `.get()`으로
  조회 가능하다. Decision service가 이를 근거로 linkage를 검증할 수 있다.
- 기존 decision 모델에는 **decision timestamp가 없다**.

### 3.2 Architect Decision

Transcript Human Review Decision은 다음으로 구현한다.

- 기존 review vocab(`DecisionKind`, `HumanActorReference`)을 **재사용**한다. 기존
  `ReviewDecision`, `ReviewService`, review 모델은 수정하지 않는다.
- Application-owned 신규 durable aggregate `TranscriptReviewDecision` 하나를 **추가**한다.
  이 aggregate가 decision identity, kind, reviewer identity, **caller-supplied decision
  timestamp**, rationale, review item/candidate/revision linkage, modified text(Modify),
  sequence/previous linkage, DomainResult linkage를 담는다.
- Correction/Preparation service를 mirror하는 신규 Application service
  `TranscriptReviewDecisionService`를 추가한다(`prepare_decision` 순수 계산 /
  `record_decision` persist 경로, Application-owned identity plan).
- Decision 하위 집합만을 위한 additive SQLite schema **v7**, atomic command, repository,
  composition wiring, restart reconstruction, deterministic replay를 추가한다.

**Deterministic replay 보장**: decision timestamp는 Application이 생성하지 않고 command
입력으로 받는다(wall-clock 미사용). 동일한 recorded input과 identity plan을 재입력하면
byte-identical decision 기록이 재구성된다.

Provider는 변경하지 않는다. Decision identity와 Decision lifecycle은 Application이
소유하며 provider가 소유하지 않는다.

### 3.3 Architect Checklist 결과

AGENTS.md checklist 전 항목 **No**:

- 기존 Domain contract 변경 없음(`ReviewDecision`/`ReviewService`/review 모델 불변; 신규
  aggregate는 additive).
- released schema 의미 변경 없음(additive v7).
- lifecycle authority 변경 없음(Human Authority 보존; 어떤 자동 적용/승인/거부/선택도 없음).
- Domain/Application/Persistence 책임 이동 없음(Application이 decision identity/lifecycle/
  persistence/provenance/reconstruction 소유; provider 불변).
- 신규 identity 의미 없음(`OpaqueIdentity` 파생 신규 id 하나).
- 하나의 additive migration 외 새로운 migration 요구 없음.
- Blueprint 모순 없음(`043_REVIEW_PIPELINE.md`와 일치; 자동화 금지 준수).

**결론: 실질적 architectural blocker 없음. Goal을 실행한다.**

## 4. Scope

Included:

- canonical Review Decision model (신규 durable aggregate `TranscriptReviewDecision`)
- Human Accept, Human Reject, Human Modify
- multiple (n) immutable decision records per review item (sequence/previous linkage)
- Decision provenance (review item / candidate / revision linkage)
- reviewer identity (`HumanActorReference`)
- decision timestamp (caller-supplied, replay-deterministic)
- decision rationale
- DomainResult linkage (신규 kind "transcript_review_decision")
- atomic SQLite persistence (additive schema v7)
- restart reconstruction
- deterministic replay
- fake-review acceptance

Excluded (구현하지 않는다):

- Applicability, Current Selection, Transcript Ready
- Subtitle generation, Artifact generation
- Policy engine, Confidence threshold automation, AI self-approval
- Provider changes, Review Preparation redesign
- UI, Plugin runtime, Registry, long-media execution
- 기존 review decision/service 모델 변경

Human Decision은 절대로 다음을 하지 않는다:

- transcript selection 자동 변경
- revision 자동 승인
- revision 자동 거부
- applicability 자동 갱신
- Transcript Ready 자동 생성
- subtitle 자동 생성

Persist는 오직 Human Decision만 한다.

## 5. Responsibility Boundary

Application이 소유한다: Decision identity, lifecycle, persistence, provenance,
reconstruction, replay 결정성. Persistence는 승인된 상태를 serialize/deserialize하고
atomic transaction·rollback·schema gate를 담당한다. Provider는 decision에 관여하지 않는다.
Decision은 어떤 downstream 자동화도 트리거하지 않는다.

## 6. Canonical Review Decision Model

### 6.1 신규 identity

- `TranscriptReviewDecisionId`(`OpaqueIdentity` 파생, `application/identities.py`)

### 6.2 신규 aggregate `TranscriptReviewDecision`

최소 필드:

- `identity: TranscriptReviewDecisionId`
- `domain_result_id: DomainResultId` (DomainResult linkage)
- `review_item_id: ReviewItemId` (Review Item linkage)
- `candidate_reference_id: CandidateReferenceId` (Candidate linkage)
- `source_revision_id: TranscriptRevisionId` (Revision linkage)
- `reviewer: HumanActorReference` (reviewer provenance)
- `kind: DecisionKind` (accept / reject / modify)
- `decided_at: datetime` (caller-supplied decision timestamp)
- `run_id`, `unit_execution_id` (execution provenance)
- `sequence: int`, `previous_decision_id: TranscriptReviewDecisionId | None`
  (append-only lineage)
- `rationale: str | None`
- `modified_text: str | None` (Modify에서만 존재)

불변식: sequence ≥ 0; MODIFY는 modified_text 필수·비어있지 않음; ACCEPT/REJECT는
modified_text 금지; reviewer는 `HumanActorReference`; decided_at은 timezone-aware.

### 6.3 재사용 review vocab

- `DecisionKind`(ACCEPT/REJECT/MODIFY), `HumanActorReference`를 그대로 재사용한다.

### 6.4 Identity/timestamp plan

`ReviewDecisionIdentityPlan`:

- `decision_id: TranscriptReviewDecisionId`
- `decision_result_id: DomainResultId`
- `decided_at: datetime`

plan은 command 입력이며, Application은 timestamp를 생성하지 않는다(replay 결정성).

## 7. Persistence Model

- additive SQLite schema **v7**(현재 6). 기존 table 의미 변경 없음.
- 신규 table: decision aggregate root(scalar 필드) 하나. optional child 없음(단일 record).
- decision의 `DomainResultReference`는 기존 domain result table에 co-persist(신규 kind
  "transcript_review_decision", upstream = source revision domain result).
- 하나의 atomic command `SQLiteReviewDecisionCommandPersistence`가 decision record와
  DomainResultReference를 단일 `BEGIN IMMEDIATE` transaction으로 쓰고 실패 시 rollback한다.
  기존 command pattern(identity absence 확인, linkage 검증, 공유 insert helper, exception
  ladder)을 mirror한다.
- restart reconstruction: 재오픈한 DB에서 decision aggregate가 동일하게 복원된다.
- deterministic replay: 동일 recorded input을 새 DB에 재기록하면 동일 record가 재구성된다.

## 8. Slice Sequence

### Slice 1 — Goal Baseline and Assessment

이 Goal 문서와 implementation status assessment 기록. Review: Optional — Skipped. Commit:

```text
docs: add transcript human review decision goal
```

### Slice 2 — Review Decision Records

`TranscriptReviewDecisionId`, `TranscriptReviewDecision` aggregate, `ReviewDecisionIdentityPlan`,
prepared-result dataclass와 invariant, exports, focused unit tests. Review: Required — Executed.
Commit:

```text
feat: add transcript review decision records
```

### Slice 3 — Deterministic Review Decision Service

`TranscriptReviewDecisionService.record_decision(...)`가 durable Review Item / Candidate /
Revision을 로드해 reviewer·timestamp·kind·rationale를 검증하고 canonical decision aggregate를
구성한다(순수 prepare, persistence 없음). identity plan·linkage·reviewer/execution provenance·
Modify/Accept/Reject 규칙 검증. no-network in-memory acceptance. Review: Required — Executed.
Commit:

```text
feat: record transcript human review decisions
```

### Slice 4 — Atomic SQLite Persistence, Restart and Replay

additive schema v7 migration·table·repository·atomic command·composition wiring,
`persist_decision` 경로, restart reconstruction, deterministic replay, migration/persistence
tests. Review: Required — Executed. Commit:

```text
feat: persist transcript review decisions atomically
```

### Slice 5 — Fake-Review Acceptance

fake review preparation → Accept/Reject/Modify 결정 기록 → atomic persist → 재오픈 → 동일
복원 → 동일 replay end-to-end acceptance. immutable Decision records, Review Item linkage,
Candidate linkage, Revision linkage, reviewer provenance, execution provenance, restart
reconstruction, atomic persistence, structural integrity를 검증한다. Review: Required only if
production boundary changes; otherwise Optional — Skipped. Commit:

```text
test: verify transcript human review decision acceptance
```

## 9. Validation

모든 slice는 focused tests, 전체 unittest suite, `compileall`, `tabnanny`,
`git diff --check`, staged diff 확인을 실행한다. Required review는 AGENTS.md critical-only
정책을 따른다: staged diff 대상 bounded 6-turn 리뷰 하나, 검증된 미해결 critical defect만
차단. 명시적 PASS를 얻기 위한 재실행 금지.

이 Goal은 다음을 명시적으로 검증한다.

- immutable Decision records
- Review Item linkage
- Candidate linkage
- Revision linkage
- reviewer provenance
- execution provenance
- restart reconstruction
- atomic persistence
- structural integrity
- deterministic replay

## 10. Stop Conditions

다음 경우에만 중단한다.

- 검증된 Blueprint 또는 책임 계약 모순
- 기존 review vocab이 Domain/Application 변경 없이 durable decision을 표현할 수 없음
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
Slice 2 — Review Decision Records
Slice 3 — Deterministic Review Decision Service
Slice 4 — Atomic SQLite Persistence, Restart and Replay
Slice 5 — Fake-Review Acceptance
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
## Canonical Review Decision Model
## Persistence Model
## Provenance
## Restart and Replay Acceptance
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
