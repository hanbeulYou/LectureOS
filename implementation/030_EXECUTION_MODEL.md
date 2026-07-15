# Execution Model

- Status: Approved
- Baseline: LectureOS Blueprint v1
- Baseline Commit: `b0251cf56628f012891e39eebe7f57c2be63c684`
- Implementation Baseline Commit: `f27f678445f1e82811cea5fb6bca647455c59679`
- Last Updated: 2026-07-16
- Depends On: `000_IMPLEMENTATION_DESIGN_GUIDE.md`, `010_PROJECT_LIFECYCLE.md`, `020_STORAGE_MODEL.md`, `../docs/020_PRODUCT_REQUIREMENTS.md`, `../docs/021_SYSTEM_CONTEXT.md`, `../docs/030_DATA_MODEL.md`, `../docs/031_ARCHITECTURE.md`, `../docs/040_TRANSCRIPT_PIPELINE.md`, `../docs/041_SUBTITLE_PIPELINE.md`, `../docs/042_LECTURE_INTELLIGENCE_PIPELINE.md`, `../docs/043_REVIEW_PIPELINE.md`, `../docs/044_EXPORT_PIPELINE.md`, `../docs/050_PLUGIN_SYSTEM.md`
- Referenced By:
- Requires Blueprint Clarification: Project와 Lecture의 Conceptual Identity 및 cardinality

## Purpose

이 문서는 LectureOS가 Processing Run을 시작하고 하나 이상의 처리 책임을 수행하며 부분 성공, 실패, retry, reprocessing과 recovery를 관리하는 실행 모델을 정의한다.

다음 질문에 답한다.

- 무엇이 하나의 실행 단위인가?
- Processing Run은 언제 생성되며 어떤 실행 문맥을 보존하는가?
- Pipeline 실행 책임과 Domain Result identity는 어떻게 분리되는가?
- Processing State와 Execution Outcome은 무엇을 설명하는가?
- 부분 성공과 실패의 영향 범위를 어떻게 드러내는가?
- retry와 reprocessing은 언제 구분되는가?
- 실행 실패 중 기존 Domain Result와 Human Decision을 어떻게 보호하는가?
- Plugin Capability와 provider 호출은 어떤 실행 경계에서 사용되는가?
- 실행 후 어떤 정보를 Storage Model에 지속해야 하는가?

이 문서는 특정 queue, worker, scheduler, runtime framework, cloud service 또는 orchestration engine을 선택하지 않는다.

## 1. Blueprint and Implementation Basis

### 1.1 Confirmed by Blueprint

- Pipeline은 제품 결과가 발전하는 논리적 책임이며 runtime 실행 단위가 아니다.
- Processing Run은 결과 생성 문맥과 provenance를 설명하지만 Domain Result identity를 소유하지 않는다.
- Text Pipeline과 Edit Pipeline은 독립적으로 진행하고 부분적으로 성공할 수 있다.
- Validation은 의미 판단이나 Human Approval이 아니다.
- Candidate, Review Decision, Approved Result와 Artifact는 서로 다른 책임을 가진다.
- Human Decision은 AI 또는 provider 결과보다 높은 작업 권위를 가진다.
- 실패와 uncertainty를 정상 완료로 숨기지 않는다.
- provider 또는 Plugin 교체와 재처리가 기존 provenance와 Human Decision을 지우지 않는다.

### 1.2 Confirmed by Implementation Baseline

- Project Lifecycle State와 Processing State를 분리한다.
- Lifecycle은 장기 작업의 발전을 설명하며 실행 순서나 orchestration과 같지 않다.
- Processing Run은 지속되는 Execution Record다.
- Domain Result는 Run과 별도 identity를 가진다.
- retry와 reprocessing은 서로 다른 실행 관계다.
- current, stale, superseded와 historical applicability를 구분한다.
- partial success는 하나의 성공·실패 값으로 축소하지 않는다.
- Artifact Record, Human Authority Record와 Execution Record를 분리한다.

### 1.3 Authority Boundary

Execution Model은 Blueprint와 승인된 Implementation Design의 책임을 실행 가능하게 연결한다. Pipeline 의미, Domain Concept, Human Decision 또는 Artifact의 권위를 다시 정의하지 않는다.

실행 편의를 위해 상위 계약을 변경해야 한다면 이 문서에서 우회하지 않고 `Requires Blueprint Clarification` 또는 Blueprint PATCH 필요성으로 보고한다.

## 2. Scope

### 2.1 Included

- Processing Run 생성과 실행 문맥
- Execution Intent
- Processing Unit, Unit Execution과 Execution Dependency
- Run 및 Unit Execution의 Processing State와 Execution Outcome
- 실행 전제와 Capability 사용 경계
- 부분 성공과 실패 영향 범위
- retry, reprocessing, cancellation과 recovery 관계
- 결과와 Run provenance 연결
- Storage Model로 이어지는 지속 책임
- 동시 실행과 중복 결과에 대한 최소 일관성 책임

### 2.2 Excluded

- Project Lifecycle 전체 상태 머신
- Pipeline 내부 의미와 제품 책임 재정의
- Human Review Decision 생성
- Artifact 의미와 export 규칙 재정의
- queue, worker, scheduler와 workflow engine 구현
- API, event 또는 message 형식
- 배포 topology, process와 thread model
- 특정 database transaction이나 lock 방식

## 3. Execution Principles

### 3.1 Execution Is Not Domain Meaning

실행 성공이나 실패는 Domain Result의 의미, validity, review readiness 또는 approval을 자동으로 결정하지 않는다.

### 3.2 Processing Run Is Not Pipeline

Processing Run은 하나 이상의 Pipeline 책임을 수행한 실행 문맥이다. Pipeline 자체나 Pipeline이 정의하는 제품 책임과 동일하지 않다.

### 3.3 Processing Run Is Not Domain Result

Run은 결과를 만들 수 있지만 Transcript, Subtitle, Analysis Finding, Edit Candidate, Review Decision, Approved Result 또는 Artifact를 소유하거나 대체하지 않는다.

### 3.4 Processing State Is Not Result Validity

Run이나 Unit Execution이 완료됐다는 사실은 생성 결과가 structurally valid하거나 review-ready 또는 approved라는 뜻이 아니다. 논리적 책임인 Processing Unit 자체는 실행 State를 갖지 않는다.

### 3.5 Completion Is Not Approval

처리 완료와 validation 성공은 Human Approval을 만들지 않는다. Approval은 Review Pipeline의 Human Decision을 통해서만 발생한다.

### 3.6 Failure Is Not Project Failure

하나의 Run 또는 Unit Execution 실패가 Working Model의 전체 작업 문맥이나 독립적인 다른 결과를 자동으로 무효화하지 않는다.

### 3.7 Retry Is Not Reprocessing

Retry는 같은 실행 의도와 입력 문맥에서 실패한 실행을 다시 시도한다. Reprocessing은 변경된 입력이나 조건에 따라 새 결과 계보를 만든다.

### 3.8 Orchestration Is Not Lifecycle

Execution Model은 처리 책임의 실행과 dependency를 설명한다. 사용자의 장기 작업 발전과 archive를 정의하는 Project Lifecycle을 대신하지 않는다.

## 4. Processing Run

Processing Run은 특정 입력, Configuration, Capability Context와 Execution Intent에서 하나 이상의 처리 책임을 수행하는 지속되는 Execution Record다.

Run은 실행을 시작하기로 한 시점에 생성한다. 실행 준비가 완료됐다는 사실이나 결과 성공을 전제하지 않으며, 시작 전제 부족으로 실제 처리를 수행하지 못한 경우도 명시적인 실행 문맥이 필요하면 기록할 수 있다.

Processing Run은 적용 가능한 범위에서 다음을 연결한다.

- Execution Intent
- 입력과 upstream result 참조
- Configuration 참조
- 필요한 Capability Contract
- 사용한 Plugin과 provider provenance
- 수행할 Processing Unit과 그 Unit Execution, dependency
- 생성된 Domain Result 참조
- Run 및 Unit Execution Processing State
- Validation Result
- Failure와 Diagnostic
- retry 또는 reprocessing 관계
- cancellation과 recovery 관계

Run의 종료는 생성 결과, Human Decision, Approved Result 또는 Artifact의 lifecycle 종료를 의미하지 않는다.

### 4.1 Execution Intent

Execution Intent는 Run이 시작된 이유와 달성하려는 처리 책임을 설명한다.

예시는 다음과 같다.

- 최초 처리
- 실패한 책임의 retry
- upstream 변경에 따른 reprocessing
- 변경된 Capability 또는 provider 사용
- 특정 결과만 다시 생성
- 승인 결과에서 Artifact 재생성

이 예시는 고정된 taxonomy가 아니다. Intent는 실행 관계를 설명하며 Domain Result의 의미를 결정하지 않는다.

## 5. Processing Unit and Unit Execution

Processing Unit은 독립적인 실행, 실패와 retry 경계를 갖도록 구분한 논리적 처리 책임이다. 특정 Run에서 그 책임이 실제로 수행된 사실은 Unit Execution이다.

Processing Unit은 다음과 동일하지 않다.

- Pipeline 전체의 제품 책임
- runtime worker 또는 process
- queue message
- Domain Result
- Plugin이나 provider 호출 하나

Processing Unit은 책임의 목적, 필요한 입력, Execution Dependency, Capability, 만들 수 있는 Domain Result 종류와 독립 실패 경계를 설명한다. 특정 Run의 Processing State, Execution Outcome, Failure 또는 Diagnostic을 갖지 않는다.

Processing Unit은 Pipeline 전체일 수도 있고 Pipeline 안에서 독립 실패와 재실행 경계가 필요한 더 작은 처리 책임일 수도 있다. 최소 단위와 분해 기준은 Requires Validation이다.

### 5.1 Unit Execution

Unit Execution은 특정 Processing Run 안에서 Processing Unit을 수행한 구분 가능한 실행 인스턴스다.

Unit Execution은 다음을 설명한다.

- 어떤 Processing Run에 속하는가?
- 어떤 Processing Unit을 수행했는가?
- 어떤 입력, upstream result와 Configuration을 사용했는가?
- 어떤 Capability, Plugin과 provider provenance가 적용됐는가?
- 어떤 Processing State와 Execution Outcome을 가졌는가?
- 어떤 Domain Result, Failure와 Diagnostic을 만들었는가?
- 어떤 retry, cancellation 또는 recovery 관계를 가지는가?

하나의 Run은 하나 이상의 Unit Execution을 포함할 수 있다. 같은 Processing Unit을 한 Run에서 두 번 수행하면 각 실행은 구분되는 Unit Execution이다. Unit Execution은 runtime worker, process 또는 queue message와 동일하지 않으며 Domain Result identity를 소유하지 않는다.

Processing Unit 분해는 다음 기준을 고려한다.

- 필요한 입력과 upstream result를 구분할 수 있는가?
- 독립적인 State와 Outcome을 설명할 수 있는가?
- 실패 영향 범위를 다른 책임과 분리할 수 있는가?
- 결과와 provenance를 별도로 연결할 수 있는가?
- 별도 retry가 Human Decision이나 다른 결과를 손상시키지 않는가?

Processing Unit을 작게 나누는 것 자체가 목적은 아니다. 구현 편의를 위한 임의의 Unit이 Pipeline 의미를 분할하거나 새로운 Domain Concept를 만들면 안 된다.

## 6. Execution Dependency

Execution Dependency는 Processing Unit을 수행하기 위해 필요한 입력, upstream result, Capability 또는 validation 전제를 설명하는 논리적 관계다. Unit Execution은 해당 실행에서 실제로 적용된 dependency 문맥을 참조한다.

Dependency는 고정된 전체 Pipeline 순서를 만들지 않는다.

- Text와 Edit 책임은 가능한 범위에서 독립적으로 진행할 수 있다.
- 같은 Run 안의 Unit Execution은 Processing Unit의 dependency에 따라 순차 또는 독립 관계를 가질 수 있다.
- 이전 Run에서 생성된 적용 가능한 결과를 입력으로 사용할 수 있다.
- optional input 부재는 분석 범위나 uncertainty에 영향을 줄 수 있지만 항상 전체 실행 실패는 아니다.
- dependency 변경은 대기 중 Unit의 실행 가능성이나 이미 생성된 결과의 applicability에 영향을 줄 수 있다.

Dependency 충족 여부는 실행 가능성을 설명한다. 결과 validity나 approval을 보장하지 않는다.

## 7. State and Outcome Model

### 7.1 Processing State

Processing State는 Run 또는 Unit Execution의 실행 진행과 복구 가능성을 설명한다.

최소한 다음 의미를 표현할 수 있어야 한다.

- 아직 시작되지 않음
- 실행 전제가 충족됨
- 실행 중
- 일부 책임이 완료됨
- 예정된 실행 책임이 종료됨
- 실패함
- 복구 또는 재시도가 가능함
- 취소되거나 중단됨

이는 필수 enum 이름이나 단일 상태 머신이 아니다. Processing State의 대상은 Run 또는 특정 Unit Execution이다. 논리적 Processing Unit에는 실행 State를 부여하지 않는다. Run State를 Unit Execution State에서 요약하는 규칙은 Requires Validation이며 단순 합계로 간주하지 않는다.

### 7.2 Execution Outcome

Execution Outcome은 Run 또는 특정 Unit Execution이 실행 관점에서 무엇을 만들거나 만들지 못했는지 설명한다. 논리적 Processing Unit 자체는 Outcome을 갖지 않는다.

- Domain Result 생성
- Partial Result
- Validation Failure
- No Result
- Recoverable Failure
- Non-recoverable Condition
- Export Failure
- External Consumer Failure

Outcome은 Human Approval이나 Domain Result validity와 같지 않다. 하나의 Unit Execution은 결과와 함께 warning, Diagnostic 또는 제한된 uncertainty를 가질 수 있다.

### 7.3 State and Outcome Separation

State는 실행 진행을, Outcome은 실행 결과의 범위를 설명한다. 완료된 Unit Execution을 후속 retry 결과로 다시 쓰지 않는다. 완료 State에서도 Validation Failure가 있을 수 있고, 실패한 Run 안에도 다른 Unit Execution이 만든 유효한 Domain Result가 있을 수 있다.

## 8. Partial Success

Partial Success는 Run 안의 일부 Unit Execution이 결과를 만들었지만 다른 Unit Execution이 완료되지 않았거나 실패한 실행 상황이다.

예시는 다음과 같다.

- Raw Transcript Unit Execution은 결과를 만들었지만 correction Unit Execution은 실패했다.
- Corrected Transcript는 존재하지만 Subtitle 생성은 완료되지 않았다.
- Subtitle은 Review에 제시할 수 있지만 Lecture Intelligence는 실패했다.
- 일부 Analysis Finding과 Edit Candidate만 생성됐다.
- 승인 결과는 존재하지만 Artifact 생성은 실패했다.
- 한 Export Profile은 성공하고 다른 Profile은 실패했다.

Partial Success는 다음을 보장해야 한다.

- 성공한 Unit Execution과 실패한 Unit Execution을 구분한다.
- 생성된 각 Domain Result를 해당 Run과 Unit Execution에 연결한다.
- 실패하지 않은 결과를 근거 없이 무효화하지 않는다.
- 누락되거나 불완전한 범위를 정상 완료로 숨기지 않는다.
- Review Readiness와 Export Readiness를 실행 완료와 별도로 판단할 수 있게 한다.

Run 전체 완료 여부를 별도 개념으로 둘지와 부분 성공의 최소 보존 단위는 Requires Validation이다.

## 9. Retry

Retry는 같은 Execution Intent와 입력 문맥에서 실패하거나 중단된 실행 책임을 다시 시도하는 관계다.

Retry는 다음을 유지한다.

- 이전 Run 또는 Unit Execution의 Failure와 새 Unit Execution 사이의 관계
- 동일하다고 판단한 입력, Configuration과 Capability Context
- 이전 시도의 Failure와 Diagnostic
- 각 시도에서 생성된 결과와 부작용의 구분
- 기존 Domain Result와 Human Decision 보호

Retry는 같은 Processing Unit을 수행하는 새로운 Unit Execution이다. 필요하면 새 Processing Run에 속할 수 있다. 각 시도는 구분 가능해야 하며, 새 시도의 성공으로 이전 Unit Execution의 State, Outcome, Failure 또는 Diagnostic을 다시 쓰지 않는다.

Retry만으로 새 Domain revision이 반드시 생기지는 않는다. 이전 시도가 이미 결과를 만들었거나 늦은 결과가 도착하면 중복 및 applicability를 명시적으로 판단해야 한다.

입력이나 처리 의미가 달라졌다면 retry로 숨기지 않고 reprocessing으로 다룬다. 동일 실행 문맥의 정확한 판단 기준은 Requires Validation이다.

## 10. Reprocessing

Reprocessing은 다음과 같은 변경으로 새 결과 계보가 필요한 실행이다.

- Source 또는 upstream result 변경
- Transcript나 Subtitle revision 변경
- Capability Contract 변경
- Plugin 또는 provider 변경
- Configuration 변경
- validation 기준 변경
- Human Review 이후 새 Candidate 생성 필요
- Export Profile 또는 Scope 변경

Reprocessing은 다음을 보장한다.

- 새 Processing Run 또는 구분 가능한 실행 문맥을 만든다.
- 이전 Run과 Domain Result를 유지한다.
- 새 결과 identity와 provenance를 이전 결과와 구분한다.
- 기존 Human Decision을 새 Candidate에 자동 적용하지 않는다.
- stale 또는 reconciliation 관계를 기록할 수 있게 한다.
- 영향받지 않은 적용 가능한 결과를 재사용할 수 있게 한다.
- 기존 Artifact와 새 Approved Result의 관계를 구분한다.

변경 영향 분석과 자동 재실행 정책은 후속 Reprocessing and Reconciliation Design의 책임이다.

## 11. Cancellation and Interruption

실행은 사용자 요청, 시스템 중단, provider failure 또는 dependency 변화로 완료 전에 멈출 수 있다.

다음 상황을 구분할 수 있어야 한다.

- 시작 전 취소
- 실행 중 중단
- 일부 Unit Execution 완료 후 중단
- 외부 provider 응답 대기 중 중단
- 결과 지속 전 또는 지속 중 중단

Cancellation과 Interruption은 다음을 보장한다.

- 완료된 Domain Result를 삭제하지 않는다.
- Human Decision과 기존 Artifact를 손상시키지 않는다.
- 완료, 진행 중, 중단된 Unit Execution을 구분한다.
- 결과가 지속됐는지 불명확한 상태를 성공으로 추정하지 않는다.
- resume, retry 또는 reprocessing 가능성을 설명할 수 있게 한다.
- 취소를 Failure, validity 또는 approval로 자동 변환하지 않는다.

Resume 지원 여부와 중단 시점별 자동 처리 정책은 Requires Validation이다.

## 12. Failure Model

### 12.1 Preparation Failure

입력, Context, Capability 또는 Configuration이 부족해 실행 책임을 시작할 수 없는 상태다.

### 12.2 Capability Failure

필요한 Capability Contract를 현재 Context에서 제공할 compatible Plugin을 찾지 못한 상태다.

### 12.3 Provider or Plugin Failure

외부 provider 또는 Plugin이 Capability Contract에 맞는 결과를 제공하지 못했거나 호출 결과를 신뢰할 수 있게 연결하지 못한 상태다.

### 12.4 Processing Failure

Unit Execution이 Processing Unit에서 기대한 Domain Result를 만들지 못한 상태다.

### 12.5 Validation Failure

생성 결과가 구조, traceability 또는 provenance 요구를 충족하지 못한 상태다. Validation Failure는 의미 판단이나 Reject Decision이 아니다.

### 12.6 Persistence Failure

Run, Result, Human Decision 또는 provenance를 Storage Model의 책임에 맞게 지속하지 못한 상태다. Human Decision persistence 실패를 승인 성공으로 간주하지 않는다.

### 12.7 Review Blocking Condition

Human Review에 필요한 Source Context, evidence, traceability 또는 conflict 정보가 부족한 상태다. Execution Model은 Review Decision을 대신 만들지 않는다.

### 12.8 Export Failure

승인된 Export Input을 추적 가능한 Artifact로 표현하지 못한 상태다. 기존 Approved Result를 무효화하지 않는다.

### 12.9 External Consumer Failure

생성된 Artifact를 외부 시스템이 받거나 처리하지 못한 상태다. LectureOS 내부 export 성공 및 Artifact validity와 구분한다.

각 Failure는 적용 가능한 범위에서 다음을 설명한다.

- 영향받은 Run과 Unit Execution
- 관련 입력과 결과
- 다른 성공 결과에 미치는 영향
- retry 가능성
- reprocessing 필요성
- Human Action 필요 여부

## 13. Recovery Responsibility

Recovery는 실패나 중단 이후 안전하게 실행 가능성을 회복하는 책임이다.

다음 활동을 포함할 수 있다.

- 실패한 Processing Unit을 새 Unit Execution으로 다시 수행
- 호환 가능한 다른 Plugin Capability를 사용한 reprocessing
- 누락된 Context를 보완한 뒤 재실행
- persistence failure 이후 기록 일관성 복구
- stale 결과의 reprocessing
- Review Conflict 해결 이후 후속 실행
- 보존된 승인 입력을 이용한 Artifact 재생성

Recovery는 다음을 하지 않는다.

- Failure와 Diagnostic 삭제
- 이전 Domain Result 덮어쓰기
- Human Decision 자동 변경
- Candidate 자동 승인
- 외부 consumer 성공 추정

자동 recovery, fallback Plugin 선택과 failure별 recovery 정책은 Requires Validation이다.

## 14. Plugin and Provider Execution Boundary

Execution Model은 Capability Negotiation 결과를 사용하지만 Plugin System을 다시 정의하지 않는다.

- Capability Contract가 provider보다 먼저 존재한다.
- Processing Unit은 필요한 Capability를 설명하고 Unit Execution은 compatible Plugin을 사용할 수 있다.
- Plugin은 Unit Execution을 지원하지만 Pipeline 책임이나 Domain Result identity를 소유하지 않는다.
- provider-specific result는 validation과 Concept 변환 전 canonical Domain Result가 아니다.
- Plugin Configuration과 Plugin Context를 Run provenance에 연결한다.
- Plugin Failure와 Domain Result의 structural validity를 구분한다.
- provider 교체가 기존 provenance와 Human Decision을 덮어쓰지 않는다.

Capability Negotiation은 Plugin 설치, 자동 실행 또는 Human Approval이 아니다. 선택 정책과 fallback 방식은 후속 설계로 남긴다.

## 15. Persistence Responsibility

Execution Model은 Storage Model에 따라 다음 정보를 지속할 수 있어야 한다.

- Processing Run identity
- Execution Intent
- Processing Unit definition references
- Unit Execution records
- 입력과 upstream result references
- Configuration과 Capability references
- Plugin 및 provider provenance
- Run State와 Unit Execution State
- Execution Outcome과 Validation Result
- Failure와 Diagnostic
- retry 및 reprocessing relationships
- 생성된 Domain Result references
- cancellation과 recovery relationships

실행 중 임시 진행 신호와 장기 Execution Record를 구분한다. failure, recovery 또는 provenance 설명에 필요한 임시 정보는 지속 책임으로 승격될 수 있다.

Processing Unit definition reference는 어떤 책임과 Capability 및 dependency가 실행됐는지 설명한다. 지속되는 Unit Execution record는 특정 Run에서 사용한 입력과 Configuration, State, Outcome, Result reference, Failure, Diagnostic과 retry·cancellation·recovery 관계를 보존한다.

Execution Record는 Domain Result, Review Decision 또는 Artifact Record를 대신하지 않는다. 구체적인 storage schema, cardinality 또는 ID 형식은 정의하지 않는다.

## 16. Concurrency and Idempotency

이 문서는 특정 동시성이나 idempotency 구현을 선택하지 않는다. 다만 다음 상황에서 기존 기록과 Human Authority를 보호할 책임을 둔다.

- 같은 Execution Intent에 대한 중복 Run
- 동일 입력을 사용하는 병렬 처리
- 동일 목적의 경쟁 revision
- Human Review와 동시에 진행되는 reprocessing
- 중복 Artifact 생성
- retry 이후 이전 시도의 지연 결과 도착

다음은 Implementation Decision이다.

- 중복 Run이 같은 Domain Result identity를 공유한다고 가정하지 않는다.
- 늦게 도착한 결과가 자동으로 current가 되지 않는다.
- Human Decision과 충돌하는 결과는 reconciliation 없이 적용하지 않는다.
- 같은 실행 요청이 반복돼도 기존 Human Decision을 덮어쓰지 않는다.
- Artifact 중복 생성이 Approved Result identity를 바꾸지 않는다.

구체적인 lock, transaction, idempotency key 또는 message delivery semantics는 정의하지 않는다.

## 17. Security and Trust Boundary

이 문서는 실행과 데이터 이동에 필요한 최소 신뢰 경계만 정의한다.

- Source Media와 Context가 외부 Plugin 또는 provider로 전달될 수 있는 경계를 드러낸다.
- 외부 결과는 검증되지 않은 provider-specific result로 돌아온다.
- 민감한 Configuration 정보와 Domain Context를 구분한다.
- provider 결과를 LectureOS Domain Result로 사용하기 전에 Capability Contract와 구조적 요구를 검증한다.
- 외부 실행이 Human Decision과 Approved Result를 변경하지 못하게 한다.
- cancellation이나 provider failure가 외부로 전달된 데이터의 삭제를 보장한다고 가정하지 않는다.

구체적인 permission, credential, secret, encryption과 provider data policy는 후속 Security Design에서 정의한다.

## 18. Blueprint Boundary Check

| Source Document | Preserved Responsibility |
| --- | --- |
| `031_ARCHITECTURE.md` | 논리적 Pipeline과 component 책임 |
| `040_TRANSCRIPT_PIPELINE.md` | Raw Transcript와 Corrected Transcript 처리 의미 |
| `041_SUBTITLE_PIPELINE.md` | Subtitle 표현과 Final Subtitle |
| `042_LECTURE_INTELLIGENCE_PIPELINE.md` | Analysis Finding과 Edit Candidate |
| `043_REVIEW_PIPELINE.md` | Human Review, Review Decision과 Approved Edit Decision |
| `044_EXPORT_PIPELINE.md` | Export Activity와 Artifact 표현 |
| `050_PLUGIN_SYSTEM.md` | Capability Contract, Plugin과 provider 경계 |
| `010_PROJECT_LIFECYCLE.md` | 장기 lifecycle, partial progress와 archive |
| `020_STORAGE_MODEL.md` | identity, revision, provenance와 persistence 책임 |

Execution Model은 위 책임을 실행 가능하게 연결하지만 다시 소유하지 않는다.

### Requires Blueprint Clarification

다음 기존 상태를 유지한다.

- Project와 Lecture의 Conceptual Identity
- Project Context와 lifecycle identity의 관계
- Project, Lecture와 Source Media cardinality

Processing Run, Processing Unit과 Unit Execution은 이 질문을 해결하거나 Project와 Lecture를 canonical Domain Concept로 승격하지 않는다.

## 19. Assumptions and Open Questions

### 19.1 Implementation Decisions

- Processing Run은 지속되는 Execution Record다.
- Processing Unit은 독립 실행과 실패 경계를 설명하는 논리적 책임이며 State나 Outcome을 갖지 않는다.
- 하나의 Run은 하나 이상의 Unit Execution을 포함할 수 있다.
- Unit Execution은 수행한 Processing Unit을 참조하고 독립적인 Processing State와 Execution Outcome을 가진다.
- 하나의 Unit Execution failure가 전체 Run이나 Working Model의 작업 문맥을 자동 실패로 만들지 않는다.
- Domain Result는 Run 및 Unit Execution과 별도 identity를 가진다.
- Run과 Unit Execution은 생성한 Domain Result reference를 가질 수 있다.
- Retry는 이전 Failure와 관계를 가진 새로운 Unit Execution이다.
- Reprocessing은 변경된 문맥에서 새 결과 계보를 만든다.
- Cancellation은 완료된 결과와 Human Decision을 삭제하지 않는다.
- 늦게 도착한 결과는 자동으로 current가 되지 않는다.
- provider-specific result는 validation 전 canonical Domain Result가 아니다.

### 19.2 Working Assumptions

- 독립적인 실패와 retry 경계를 설명하기 위해 Pipeline보다 작은 Processing Unit이 필요할 수 있다.
- Run과 Unit Execution State를 별도로 추적해야 partial success를 설명할 수 있다.
- 하나의 Run에서 여러 Capability를 사용할 수 있지만 구체적인 조합 책임은 확정하지 않는다.
- Project와 Lecture는 실행 기록을 묶는 canonical identity가 아닌 기존 Working Model reference다.

### 19.3 Requires Validation

- Processing Unit의 최소 단위는 무엇인가?
- 하나의 Run이 여러 Pipeline 책임을 포함할 수 있는가?
- 하나의 Unit Execution이 여러 Domain Result를 만들 수 있는가?
- Run 전체 완료를 별도로 정의할 필요가 있는가?
- Run State를 Unit Execution State에서 어떻게 요약하는가?
- partial success의 최소 보존 단위는 무엇인가?
- 동일 실행 문맥을 판단하는 기준은 무엇인가?
- 어떤 Failure는 retry할 수 있고 어떤 Failure는 reprocessing이 필요한가?
- 자동 retry나 fallback Plugin 선택을 허용하는가?
- cancellation 이후 resume을 지원하는가?
- 동시 reprocessing과 Human Review conflict를 어떻게 식별하는가?
- 지연 결과가 stale인지 superseded인지 누가 결정하는가?
- 하나의 Processing Run이 여러 Capability와 Plugin을 사용할 수 있는가?
- Execution Record의 최소 장기 보존 범위는 무엇인가?

### 19.4 Requires Blueprint Clarification

- Project와 Lecture의 Conceptual Identity
- Project Context와 lifecycle identity의 관계
- Project, Lecture와 Source Media cardinality

### 19.5 Deferred

- Processing Unit 분해와 orchestration algorithm
- Run과 Unit Execution의 구체적인 state machine
- retry 횟수와 backoff 정책
- automatic recovery와 fallback 정책
- concurrency control과 idempotency 구현
- queue, worker, scheduler와 runtime topology
- API, event와 message contract
- credential와 permission 구현

## 20. Validation Criteria

- Processing Run, Pipeline과 Domain Result를 서로 구분한다.
- Processing Unit은 논리적 책임이며 Unit Execution과 구분된다.
- Unit Execution은 runtime worker나 message로 고정되지 않는다.
- Processing State, Execution Outcome, result validity와 Human Approval을 구분한다.
- Processing State와 Execution Outcome은 Run 또는 Unit Execution에만 속한다.
- Retry는 이전 Unit Execution 기록을 덮어쓰지 않는 새로운 Unit Execution이다.
- Unit Execution failure가 독립적인 성공 결과를 자동 무효화하지 않는다.
- retry와 reprocessing이 서로 다른 관계와 계보를 가진다.
- cancellation과 recovery가 기존 Human Decision과 결과를 삭제하지 않는다.
- provider-specific result를 validation 전 canonical Domain Result로 취급하지 않는다.
- 결과와 Run, Unit Execution, Processing Unit, Capability, Plugin 및 Configuration provenance를 연결할 수 있다.
- 늦거나 중복된 결과를 자동으로 current로 승격하지 않는다.
- Project와 Lecture를 canonical Domain Concept로 승격하지 않는다.
- 특정 queue, worker, scheduler, runtime framework 또는 cloud service를 선택하지 않는다.
- Blueprint와 승인된 Implementation Design의 책임을 다시 정의하지 않는다.

## Non-Goals

이 문서는 다음을 정의하지 않는다.

- queue 기술
- worker, scheduler, orchestration 또는 workflow framework
- API, event schema와 message format
- database transaction
- lock과 idempotency key 형식
- cloud service와 배포 topology
- process와 thread model
- programming language
- 코드와 package 구조
- retry 횟수와 backoff algorithm
- 성능 목표와 자원 사양
- Pipeline별 상세 실행 algorithm

## Related Documents

- [Implementation Design Guide](./000_IMPLEMENTATION_DESIGN_GUIDE.md)
- [Project Lifecycle](./010_PROJECT_LIFECYCLE.md)
- [Storage Model](./020_STORAGE_MODEL.md)
- [Blueprint v1 Release](../docs/090_BLUEPRINT_RELEASE.md)
- [Product Requirements](../docs/020_PRODUCT_REQUIREMENTS.md)
- [System Context](../docs/021_SYSTEM_CONTEXT.md)
- [Conceptual Data Model](../docs/030_DATA_MODEL.md)
- [Logical Architecture](../docs/031_ARCHITECTURE.md)
- [Transcript Pipeline](../docs/040_TRANSCRIPT_PIPELINE.md)
- [Subtitle Pipeline](../docs/041_SUBTITLE_PIPELINE.md)
- [Lecture Intelligence Pipeline](../docs/042_LECTURE_INTELLIGENCE_PIPELINE.md)
- [Review Pipeline](../docs/043_REVIEW_PIPELINE.md)
- [Export Pipeline](../docs/044_EXPORT_PIPELINE.md)
- [Plugin System](../docs/050_PLUGIN_SYSTEM.md)
