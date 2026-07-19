# LectureOS Codex Goal — Durability Milestone Completion

## 1. Mission

이 문서는 Codex가 LectureOS 저장소에서 승인된 durability 구현 순서를 스스로 이어서 수행하기 위한 장기 실행 Goal이다.

Codex는 사용자가 각 단계마다 별도 프롬프트를 전달하지 않아도 다음 루프를 반복한다.

```text
현재 repository baseline 확인
→ 다음 미완료 slice 선정
→ 계약과 범위 검토
→ 구현
→ 집중 테스트
→ 전체 회귀 검증
→ Risk-Based Claude Review 적용
→ commit
→ Working Tree Clean 확인
→ 진행 상태 문서 갱신
→ 다음 slice로 계속
```
단, 이 문서의 Stop Conditions에 해당하면 즉시 중단하고 Architect 검토를 요청한다.

---

## 2. Current Repository Baseline

이 문서를 처음 실행할 때 기대하는 기준:

```text
Branch:
main

HEAD:
f5b9e1453dd5b6f93434e3b188d6cf83c489ef9c

Commit:
feat: wire atomic retry persistence

Working Tree:
Clean
```

시작 전에 반드시 다음을 확인한다.

```bash
git rev-parse HEAD
git branch --show-current
git status --short
```

실제 상태가 위 기준과 다르면:

1. 현재 diff와 commit history를 조사한다.
2. 이미 후속 작업이 정상적으로 완료된 상태인지 확인한다.
3. 완료된 slice를 다시 구현하지 않는다.
4. baseline 불일치가 안전하게 해석되지 않으면 중단한다.

---

## 3. Product Context

LectureOS의 처리 흐름:

```text
Media
→ Provider Adapter
→ Transcript Domain
→ Subtitle Domain
→ Review
→ Validation
→ Final Selection
→ Export
```

현재 durability 흐름은 실행 상태와 결과 관계를 SQLite에 보존하여 다음을 가능하게 하는 작업이다.

```text
프로세스 재시작
→ ProcessingRun 복원
→ UnitExecution 복원
→ canonical Failure 복원
→ canonical Result reference 복원
→ 실패 또는 Retry 상태 판단
→ 이후 처리 계속
```

물리 파일과 Domain record는 별도 책임이다.

```text
Artifact/Result record
≠ physical file
```

파일이 유실되어도 Domain record는 존재할 수 있으며, 물리 파일 경로나 URL은 identity가 아니다.

---

## 4. Verified Product Milestone

Credentialed Real Media M1은 이미 검증되었다.

```text
실제 .mov 수업 영상
→ ffmpeg 오디오 추출
→ 실제 OpenAI whisper-1 API
→ timed transcript segments
→ Subtitle pipeline
→ Validation
→ Final Selection
→ SRT Export
→ Local Materialization
```

검증 상태:

```text
Credentialed real video → SRT: VERIFIED
```

이 문서의 durability 작업 중 실제 credential, 비디오, 전사 내용, 학생 정보, 생성 SRT 또는 로컬 절대 경로를 commit하지 않는다.

---

## 5. Completed Durability Baseline

다음 단계는 완료된 것으로 간주한다. 실제 repository가 이를 증명하는지 반드시 확인한다.

```text
Schema v1 — ProcessingUnit
Schema v2 — ProcessingRun
Schema v3 — UnitExecution
Schema v4 — canonical DomainResultReference + canonical Failure structures

SQLiteProcessingUnitRepository
SQLiteProcessingRunRepository
SQLiteUnitExecutionRepository
Atomic Start Persistence
ExecutionService Atomic Start Wiring
SQLiteFailureRepository
Atomic Failure Persistence
ExecutionService Failure Wiring
Atomic Retry Persistence
ExecutionService Retry Wiring
SQLiteDomainResultReferenceRepository
Atomic Result Persistence
```

완료된 주요 commits:

```text
7b6f3f4c  feat: support sqlite schema version 4 migration
2e061aaf  feat: persist failures in sqlite
395c527c  feat: persist terminal failures atomically
61e11262  feat: wire atomic failure persistence
cf91fec4  feat: persist retries atomically
f5b9e145  feat: wire atomic retry persistence
```

---

## 6. Authoritative Remaining Sequence

다음 미완료 slice부터 아래 순서대로 계속 진행한다.

```text
1. ExecutionService Result Wiring
2. Diagnostic Persistence Assessment
```

각 slice는 별도 commit으로 완료한다.

현재 immediate next slice는 다음과 같다.

```text
ExecutionService Result Wiring
```

순서를 바꾸거나 두 slice를 하나의 commit으로 합치지 않는다.

다음 slice로 넘어가기 전에 현재 slice가 반드시 다음 조건을 충족해야 한다.

```text
implementation complete
focused tests pass
full regression passes
required review gate satisfied
commit created
Working Tree clean
```

---

## 7. Global Architecture Contracts

### 7.1 Responsibility separation

```text
Domain
→ product meaning and invariants

Application
→ lifecycle legality and final record computation

Persistence
→ representation, transaction, rollback, error mapping

Composition Root
→ concrete dependency construction
```

Application service는 SQLite 또는 `sqlite3`를 import하지 않는다.

Persistence는 lifecycle legality, Retry authority, Failure category, retryability 또는 Result selection을 결정하지 않는다.

### 7.2 Record semantics

```text
ProcessingUnit
→ immutable insert-only

ProcessingRun
→ mutable current snapshot

UnitExecution
→ mutable current snapshot

DomainResultReference
→ immutable insert-only canonical record

Failure
→ immutable insert-only canonical record
```

Repositories는 current record 또는 current snapshot만 노출한다.

숨겨진 history를 repository 내부에 저장하지 않는다.

### 7.3 Snapshot references versus canonical records

반드시 구분한다.

```text
UnitExecution.result_references
≠ DomainResultReference canonical records

UnitExecution.failure_references
≠ Failure canonical records
```

Snapshot table의 identity reference를 canonical record로 자동 합성하지 않는다.

### 7.4 Transaction ownership

Command transaction 구조:

```text
SQLiteExecutionCommandPersistence
→ BEGIN IMMEDIATE
→ internal non-committing writers
→ representation-level checks
→ COMMIT / ROLLBACK
```

Public repository는 독립적으로 self-transactional하다.

Internal writer는 절대 다음을 실행하지 않는다.

```text
BEGIN
COMMIT
ROLLBACK
```

Outer command transaction 안에서 public repository save를 호출하지 않는다.

---

## 8. Migration Policy

승인된 정책:

```text
explicit migrations only
ordinary database opening does not migrate
no automatic chained migration
no downgrade
released schema meanings remain frozen
```

지원:

```text
v1→v2
v2→v3
v3→v4
v2→v2 validated no-op
v3→v3 validated no-op
v4→v4 validated no-op
```

거부:

```text
direct v1→v4
direct v2→v4
v4→v3
automatic v1→v2→v3→v4 chain
unknown-version migration
```

남은 durability slice에서 schema 또는 migration을 수정하지 않는다.

새 schema가 필요하다고 판단되면 Stop Condition이다.

---

## 9. Current Retry Contract

현재 Retry authority는 Application이 가진다.

```text
FAILED UnitExecution
+ at least one failure reference
+ at least one resolved retryable Failure
→ Retry allowed
```

현재 규칙은 다음을 요구하지 않는다.

```text
모든 Failure reference가 resolve될 것
모든 resolved Failure가 retryable일 것
```

현재 Retry 판단에 사용하지 않는 항목:

```text
Diagnostic records
DomainResultReference records
reprocessing_required
human_action_required
ProcessingUnit.independently_retryable
```

이 규칙을 남은 구현 중 강화하거나 약화하지 않는다.

---

## 9.1 Completed Retry Wiring Contract

`ExecutionService Retry Wiring`은 commit `f5b9e145`에서 완료되었다. 다시 구현하지 않는다.

확정된 동작:

```text
ExecutionService.retry_unit_execution
→ source FAILED 확인
→ ordered Failure references resolve
→ at least one resolved retryable Failure 확인
→ caller-supplied target identity absence 확인
→ new Retry UnitExecution 계산
→ final ProcessingRun 계산
→ AtomicRetryExecutionPersistence exactly once
→ durable success 후 RequestAccepted 반환
```

보존된 Retry authority:

```text
unresolved Failure reference
→ 허용

resolved non-retryable Failure
→ 단독 승인하지 않지만 veto하지 않음

at least one resolved retryable Failure
→ Retry 승인
```

확정된 composition:

```text
compose_sqlite_execution_service(connection)
→ ProcessingUnit repository
→ ProcessingRun repository
→ UnitExecution repository
→ Failure repository
→ one SQLiteExecutionCommandPersistence
→ Atomic Start + Failure + Retry ports
→ ExecutionService
```

기존 `compose_sqlite_atomic_failure_execution_service(...)`는 backward-compatible alias다.

Capability distinction:

```text
Atomic Retry command
→ Schema v3+

canonical Failure resolution을 포함한 full durable Retry service
→ Schema v4
```

Retry wiring 이후 baseline 검증:

```text
focused: 21 tests PASS
relevant regression: 179 tests PASS
complete suite: 573 tests PASS
Claude Review: Required — Executed, PASS
Working Tree: Clean
```

---

# Slice 1 — SQLiteDomainResultReferenceRepository (Completed)

Completion status:

```text
implementation: complete
focused tests: 10 PASS
review classification: Optional — Skipped
commit: feat: persist domain result references in sqlite
next slice: Atomic Result Persistence
```

## Goal

Schema v4의 canonical Result 구조를 사용하는 insert-only SQLite repository를 구현한다.

Authoritative model:

```python
@dataclass(frozen=True, slots=True)
class DomainResultReference:
    identity: DomainResultId
    kind: str
    source_media: SourceMediaId | None = None
    source_timeline: SourceTimelineId | None = None
    upstream_results: tuple[DomainResultId, ...] = ()
    revision_of: DomainResultId | None = None
    applicability: str | None = None
```

Storage:

```text
domain_result_references
domain_result_upstream_results
```

## Repository semantics

```text
immutable insert-only canonical record
```

최소 public interface는 기존 repository protocol을 따른다.

예상 기능:

```text
save(record)
get(identity)
```

기존 interface를 조사한 뒤 정확한 method 이름을 사용한다.

Speculative query API를 추가하지 않는다.

## Serialization requirements

- `identity` typed wrapper의 `.value`
- `kind` exact string
- nullable source IDs 유지
- nullable `revision_of` 유지
- nullable `applicability` 유지
- `upstream_results`는 ordinal child rows
- 0부터 시작하는 ordinal
- exact tuple order
- duplicate upstream identity 보존
- empty tuple은 child row 0개
- JSON storage 금지
- external FK 금지

## Deserialization requirements

- explicit `ORDER BY ordinal`
- ordinal이 정확한 `0..n-1`이 아니면 persistence corruption error
- typed wrappers 복원
- exact immutable tuple 복원
- unknown identity는 기존 repository convention에 따라 `None` 또는 approved error

## Collision semantics

기존 immutable repository convention을 따른다.

현재 예상:

```text
same identity, identical content
→ collision

same identity, different content
→ collision
```

Overwrite, update, replace, delete-and-reinsert 금지.

## Feature gate

```text
Schema v1–v3
→ SchemaFeatureUnavailableError

Schema v4
→ available
```

자동 migration 금지.

## Transaction

Public `save()` 하나가 다음 전체 canonical record를 하나의 transaction으로 저장한다.

```text
parent
+ all upstream child rows
```

## Required tests

- v1/v2/v3 feature gate
- v4 full round-trip
- all optional fields
- empty upstream tuple
- ordered upstream tuple
- duplicate upstream identities
- blank kind는 schema constraint로 거부됨
- identical collision
- conflicting collision
- parent insert 후 child failure rollback
- restart durability
- malformed ordinal gap 거부
- caller-owned connection 유지
- speculative API 부재

## Expected commit

```text
feat: persist domain result references in sqlite
```

## Review classification

기본 예상:

```text
Optional — Skipped
```

하지만 schema, transaction architecture, lifecycle 또는 recovery boundary를 변경하면 Required로 재분류한다.

Skipped review를 PASS로 표현하지 않는다.

---

# Slice 2 — Atomic Result Persistence (Completed)

Completion status:

```text
implementation: complete
focused tests: 10 PASS
review classification: Required — Executed
commit: feat: persist terminal results atomically
next slice: ExecutionService Result Wiring
```

## Goal

다음 logical record set을 하나의 SQLite transaction으로 저장하는 Application port와 concrete adapter를 구현한다.

```text
all new canonical DomainResultReference records
+ final completed UnitExecution snapshot
+ final ProcessingRun snapshot
```

후보 port:

```python
persist_recorded_results(
    *,
    results: tuple[DomainResultReference, ...],
    execution: UnitExecution,
    run: ProcessingRun,
) -> None
```

정확한 naming은 기존 port convention을 따른다.

`ExecutionService` wiring은 이 slice에서 하지 않는다.

## Responsibility boundary

Application:

- lifecycle legality
- 결과 record 구성
- final completed execution 계산
- final run 계산
- ordered result references 계산

Persistence:

- one SQLite transaction
- canonical Result insertions
- final execution snapshot write
- final run snapshot write
- representation-level linkage checks
- rollback
- error mapping

Persistence는 Result kind, applicability, completion legality 또는 result selection을 결정하지 않는다.

## Atomic set

```text
0개가 아닌 모든 supplied new Result records
+ 1 final UnitExecution
+ 1 final ProcessingRun
```

현재 Application contract가 empty result tuple을 허용하는지 조사한다.

명확하지 않고 command correctness에 영향을 주면 중단한다.

## Collision

어느 Result identity 하나라도 기존에 존재하면 전체 command rollback.

기존 execution/run snapshot도 변경되지 않아야 한다.

## Linkage checks

실제 Domain 모델을 조사해 이미 표현된 관계만 검사한다.

가능한 검사:

- execution.run_id == run.identity
- final execution이 supplied Result identities를 계약상 참조
- final run이 supplied Result identities를 계약상 참조
- ordered result references 일치

새 semantics를 만들지 않는다.

## Internal writers

재사용:

```text
_insert_domain_result_reference_record
_write_unit_execution_snapshot
_write_processing_run_snapshot
```

모두 non-committing.

## Feature gate

Canonical Result structures가 Schema v4이므로 atomic Result command는 Schema v4에서만 가능하다.

## Required tests

- multiple Results atomic success
- result order and upstream lineage preservation
- restart reconstruction
- v1–v3 feature gate
- first/middle/last Result collision rollback
- Result child insertion failure rollback
- execution write failure rollback
- run write failure rollback
- linkage mismatch rollback
- commit failure rollback
- caller connection reuse
- no nested transaction
- Application port SQLite isolation
- `ExecutionService` 미연결 확인

## Expected commit

```text
feat: persist terminal results atomically
```

## Review classification

```text
Required — Executed
```

---

# Slice 3 — ExecutionService Result Wiring

## Goal

기존 결과 기록 또는 execution completion Application flow를 Atomic Result persistence port에 연결한다.

실제 method 이름과 return contract는 repository를 조사해 확인한다.

성공 흐름의 개념:

```text
load current execution/run
→ existing lifecycle validation
→ build canonical DomainResultReference records
→ compute final completed UnitExecution
→ compute final ProcessingRun
→ atomic result persistence exactly once
→ return after durable success
```

## Preserve existing semantics

반드시 기존 구현과 테스트를 source of truth로 삼아 보존한다.

- legal source state
- completed state
- outcome
- result identities
- ordered result references
- failure references
- run snapshot behavior
- return value
- illegal-state error

## Exactly-once write path

독립적인 다음 save를 terminal result transition에서 호출하지 않는다.

```text
DomainResultReferenceRepository.save
UnitExecutionRepository.save
ProcessingRunRepository.save
```

Read operations은 허용한다.

## Persistence failure

- error propagate
- no success return
- no fallback writes
- no regenerated Result identity
- durable snapshots unchanged through rollback

## Required tests

- atomic port exactly once
- exact supplied Result tuple
- exact final execution/run
- independent saves absent
- lifecycle-invalid call에서 persistence 0회
- ordered result references 보존
- multiple Results 처리
- generic persistence error
- Result collision
- schema unavailable
- SQLite end-to-end success and restart
- concrete write/commit failure through service
- existing Failure and Retry regressions

## Expected commit

```text
feat: wire atomic result persistence
```

## Review classification

```text
Required — Executed
```

---

# Slice 4 — Diagnostic Persistence Assessment

## Goal

Diagnostic canonical persistence가 다음 milestone에 실제로 필요한지 평가한다.

이 slice는 기본적으로 assessment이며, 자동 구현 slice가 아니다.

현재 계약:

```text
Failure.diagnostics
→ ordered opaque DiagnosticId references

Diagnostic canonical persistence
→ deferred
```

## Required investigation

검토할 항목:

- 현재 Diagnostic Domain model 존재 여부
- authoritative fields 존재 여부
- identity semantics
- immutable/mutable 여부
- producer와 consumer
- Failure diagnostics를 resolve해야 하는 실제 Application use case
- Retry authority에서 Diagnostic 필요 여부
- review/export/UI 필요 여부
- physical logs와 Domain Diagnostic의 구분
- schema에 canonical Diagnostic table이 없는 이유
- 다음 product milestone이 Diagnostic persistence에 의존하는지

## Allowed outcomes

### Outcome A — Continue deferral

구체적인 소비자와 authoritative model이 없으면:

```text
Diagnostic Persistence: DEFERRED
```

assessment 문서만 commit한다.

### Outcome B — Blueprint Clarification required

Domain model은 있으나 persistence semantics가 불명확하면 구현하지 않고 중단한다.

### Outcome C — Blueprint PATCH required

새 schema/table/identity/lifecycle 의미가 필요하면 구현하지 않고 중단한다.

### Outcome D — Implementation ready

이미 승인된 충분한 계약이 존재하는 경우에만 별도 후속 plan을 작성한다.

이 Goal 실행 중 즉시 Diagnostic persistence까지 구현하지 않는다.

## Deliverable

예상 문서:

```text
implementation/070_DIAGNOSTIC_PERSISTENCE_ASSESSMENT.md
```

포함 내용:

- current state
- contract evidence
- actual consumers
- persistence necessity
- recommended decision
- dependencies
- risks
- next implementation candidate

## Expected commit

Deferral assessment라면:

```text
docs: assess diagnostic persistence
```

## Review classification

Assessment only이면:

```text
Optional — Skipped
```

Blueprint 또는 schema 의미를 결정·변경하면 중단하고 Architect에게 넘긴다.

---

## 10. Risk-Based Claude Review Workflow

Authoritative source:

```text
implementation/050_IMPLEMENTATION_WORKFLOW.md
```

각 slice마다 정확히 하나를 보고한다.

```text
Required — Executed
Required — Blocked
Optional — Executed
Optional — Skipped
```

### Required review categories

다음을 변경하면 Required:

- schema
- migration
- lifecycle
- transaction boundary
- filesystem boundary
- idempotency
- recovery
- security

Default budget:

```text
--max-turns 6
```

Verdict 없이 종료되면 제한적으로 증액할 수 있다.

모든 budget과 증액 이유를 completion report에 기록한다.

Reviewer에게 다음 형식을 요구한다.

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

명시적 Verdict가 없으면 PASS가 아니다.

```text
Required — Blocked
```

Blocking issue가 있으면:

```text
contract 검증
→ 최소 수정
→ focused test 갱신
→ full validation
→ review 재실행
→ explicit PASS 확보
```

---

## 11. Global Validation Requirements

각 implementation slice마다 최소 실행:

```bash
PYTHONPATH=src python3 -m unittest <focused modules> -q
PYTHONPATH=src python3 -m unittest discover -s tests -q
PYTHONPATH=src python3 -m compileall -q src tests
python3 -m tabnanny src tests
git diff --check
git diff --cached --check
```

Configured lint/type checker가 있으면 실행한다.

관련 regression에는 최소 다음 영역을 포함한다.

```text
Execution foundation
Atomic Start persistence and wiring
Failure repository
Atomic Failure persistence
Failure service wiring
Atomic Retry persistence
Retry service tests
Schema v3/v4 migrations
ProcessingUnit repository
ProcessingRun repository
UnitExecution repository
Real Media demo
```

Result slice가 추가되면 Result 관련 테스트도 이후 regression set에 계속 포함한다.

---

## 12. Commit and Working Tree Policy

각 slice는 별도 commit.

Commit 전:

- focused tests PASS
- relevant regression PASS
- complete suite PASS
- compile/static PASS
- diff checks PASS
- required reviewer explicit PASS
- unrelated changes 없음

Commit 후:

```bash
git rev-parse HEAD
git status --short
```

반드시 Working Tree가 Clean이어야 다음 slice로 진행한다.

Commit amend, squash 또는 이전 slice와 결합은 별도 요구가 없으면 하지 않는다.

---

## 13. Status Documentation

각 slice 완료 후 다음 중 기존 관례에 맞는 상태 문서를 갱신한다.

```text
implementation/060_IMPLEMENTATION_STATUS.md
```

필요하면 durability 진행 문서를 추가할 수 있다.

상태 문서는 사실만 기록한다.

- commit hash
- capability
- test result
- review classification
- remaining limitations

credential, 학생 정보, 실제 전사 내용, 로컬 절대 경로는 기록하지 않는다.

---

## 14. Stop Conditions

다음 중 하나라도 발생하면 다음 slice로 넘어가지 말고 즉시 중단한다.

### Architecture

- 승인되지 않은 Domain field 필요
- 새로운 identity semantics 필요
- lifecycle rule 변경 필요
- Retry authority 변경 필요
- canonical record와 snapshot reference 관계가 불명확
- Artifact identity 또는 physical-file 의미 변경 필요
- persistence responsibility가 Application과 충돌

### Blueprint

- 기존 문서 사이에 실질적 모순 발견
- authoritative model이 없음
- schema 변경 없이는 구현 불가능
- 새로운 migration이 필요
- released schema meaning 변경 필요

### Review

- Required review가 반복적으로 verdict 없이 종료
- reviewer가 blocking issue 제시
- reviewer가 Blueprint Clarification을 요구

### Repository

- baseline을 안전하게 해석할 수 없음
- unrelated modifications를 분리할 수 없음
- tests가 승인 범위 밖 문제로 실패
- Working Tree를 clean하게 만들 수 없음

### Security/Data

- real credential 또는 민감 데이터 commit 위험
- 실제 강의/학생 데이터가 fixture에 포함될 위험

중단 보고서는 다음을 포함한다.

```text
blocking fact
reviewed contracts
why current scope cannot safely continue
smallest required Architect decision
repository state
uncommitted changes
```

---

## 15. Prohibited Scope

이 Goal 전체에서 별도 승인 없이 구현하지 않는다.

```text
schema v5
migration changes
Project domain
Lecture domain
Diagnostic canonical schema
transcript terminology correction
subtitle candidate segmentation
short-cue merge
long-cue split
reading-rate optimization
line wrapping
GUI timeline editor
new cloud database
PostgreSQL migration
multi-user concurrency architecture
background distributed workers
new API server
unrelated Demo/CLI redesign
unrelated refactoring
```

---

## 16. Per-Slice Completion Report

각 slice 완료 후 내부 기록 및 최종 milestone report에 다음 구조를 사용한다.

```text
## Summary

## Repository Status
- Starting HEAD
- Final HEAD
- Branch
- Working Tree
- Commit

## Contract Basis

## Files Changed

## Implementation

## Responsibility Boundaries

## Transaction / Repository Semantics

## Tests Added

## Validation Performed

## Claude Review
- Classification
- budgets
- explicit verdict
- Blocking Issues
- Non-Blocking Issues
- Missing Tests
- Blueprint Clarification

## Scope Confirmation

## Product Milestone Impact

## Open Questions
- Architect Decision
- Blueprint Clarification
- Blueprint PATCH
- Operational blockers

## Next Slice

Requires Architect Decision: Yes/No
Requires Blueprint Clarification: Yes/No
Requires Blueprint PATCH: Yes/No
```

---

## 17. Final Goal Completion Criteria

이 Goal은 다음 조건을 모두 만족하면 완료된다.

```text
SQLiteDomainResultReferenceRepository complete
Atomic Result Persistence complete
ExecutionService Result Wiring complete
Diagnostic Persistence Assessment complete
all commits created
all required reviews PASS
complete suite PASS
Working Tree clean
no unresolved blocker
```

완료 시 하나의 최종 milestone report를 작성한다.

최종 report에는 다음을 명확히 구분한다.

### Newly durable

```text
terminal Failure through ExecutionService
Retry through ExecutionService
canonical DomainResultReference save/load
terminal Result recording through ExecutionService
```

### Still deferred

```text
Diagnostic canonical persistence, unless assessment says otherwise
quality pipeline improvements
Project/Lecture domains
```

### Final repository state

```text
final HEAD
commit list
complete test count
review results
Working Tree clean
```

---

## 18. Immediate Instruction to Codex

이 문서를 읽은 뒤 다음과 같이 행동한다.

```text
1. repository와 authoritative contracts를 조사한다.
2. 이미 완료된 slice를 식별한다.
3. 첫 미완료 slice부터 시작한다.
4. 각 slice를 독립적으로 구현·검증·review·commit한다.
5. Stop Condition이 없으면 다음 slice로 자동 진행한다.
6. 사용자에게 중간 승인이나 다음 프롬프트를 요구하지 않는다.
7. Architect Decision, Blueprint Clarification, Blueprint PATCH 또는 operational blocker가 있을 때만 중단한다.
8. 모든 remaining slice가 끝나면 최종 milestone report를 반환한다.
```
