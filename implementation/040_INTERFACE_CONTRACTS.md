# Interface Contracts

- Status: Approved
- Baseline: LectureOS Blueprint v1
- Baseline Commit: `b0251cf56628f012891e39eebe7f57c2be63c684`
- Implementation Baseline Commit: `7a774082a264c3123987573db67eafc0f8654fa0`
- Last Updated: 2026-07-16
- Depends On: `000_IMPLEMENTATION_DESIGN_GUIDE.md`, `010_PROJECT_LIFECYCLE.md`, `020_STORAGE_MODEL.md`, `030_EXECUTION_MODEL.md`, `../docs/020_PRODUCT_REQUIREMENTS.md`, `../docs/021_SYSTEM_CONTEXT.md`, `../docs/030_DATA_MODEL.md`, `../docs/031_ARCHITECTURE.md`, `../docs/040_TRANSCRIPT_PIPELINE.md`, `../docs/041_SUBTITLE_PIPELINE.md`, `../docs/042_LECTURE_INTELLIGENCE_PIPELINE.md`, `../docs/043_REVIEW_PIPELINE.md`, `../docs/044_EXPORT_PIPELINE.md`, `../docs/050_PLUGIN_SYSTEM.md`
- Referenced By:
- Requires Blueprint Clarification: Project와 Lecture의 Conceptual Identity 및 cardinality

## Purpose

이 문서는 LectureOS의 구현 책임 사이에서 요청, 입력, 결과, 실패와 provenance가 어떤 의미로 전달되어야 하는지 정의한다.

다음 질문에 답한다.

- 어떤 책임이 다른 책임에 무엇을 요청할 수 있는가?
- 요청을 수락하거나 실행하기 위한 전제는 무엇인가?
- 요청 수락, 실행 시작, 결과 생성과 완료는 어떻게 구분되는가?
- 실패, 부분 성공과 uncertainty를 어떻게 전달하는가?
- Domain Result와 Execution Record는 어떻게 연결되는가?
- Plugin 또는 provider 결과는 어느 경계에서 LectureOS Concept로 변환되는가?
- Human Decision을 실행 책임이나 외부 자동화가 덮어쓰지 못하게 하는 계약은 무엇인가?
- runtime이나 transport가 달라져도 어떤 의미를 유지해야 하는가?

Interface Contract는 책임 사이의 의미 계약이다. 구체적인 protocol, payload, endpoint, event 또는 파일 교환 형식을 정의하지 않는다.

## 1. Blueprint and Implementation Basis

### 1.1 Confirmed by Blueprint

- Pipeline과 Domain Concept의 책임은 전달 방식보다 먼저 존재한다.
- Candidate, Review Decision, Approved Result와 Artifact를 분리한다.
- Validation은 Meaning이나 Human Approval이 아니다.
- Human Decision은 AI, Plugin 또는 provider 결과보다 높은 작업 권위를 가진다.
- provider-specific result는 검증과 정규화 전 canonical LectureOS Domain Result가 아니다.
- Failure와 uncertainty를 정상적인 빈 결과로 숨기지 않는다.
- 모든 주요 시간 기반 결과는 Source Timeline으로 추적 가능해야 한다.
- Plugin과 외부 consumer가 Pipeline 책임이나 Domain identity를 소유하지 않는다.

### 1.2 Confirmed by Implementation Baseline

- Processing Run, Processing Unit, Unit Execution과 Domain Result를 구분한다.
- Processing Unit은 논리적 책임이고 Unit Execution은 Run 안의 실행 인스턴스다.
- Processing State와 Execution Outcome은 Run 또는 Unit Execution에 속한다.
- 요청 수락이나 실행 완료가 validation 또는 approval을 뜻하지 않는다.
- Processing Run과 Domain Result는 별도 identity를 가진다.
- Human Authority Record와 Execution Record를 분리한다.
- retry와 reprocessing은 다른 실행 의도와 관계를 가진다.
- partial success와 persistence failure를 전체 성공으로 숨기지 않는다.

### 1.3 Authority Boundary

Interface Contracts는 승인된 책임 사이에서 전달해야 할 의미를 구체화한다. Domain Concept, Pipeline 책임, 실행 모델 또는 저장 책임을 다시 정의하지 않는다.

Interface 편의를 위해 Project나 Lecture를 확정된 resource로 만들거나 Human Decision을 일반 처리 명령으로 바꾸지 않는다.

## 2. Scope

### 2.1 Included

- Interface Contract의 공통 구성
- Working Model의 상위 작업 문맥 인터페이스
- Processing 요청과 실행 reference
- Domain Result 조회 및 연결
- Human Review와 Decision 경계
- Approved Result와 Artifact 생성 요청 경계
- Plugin Capability와 provider 결과 경계
- Failure, partial success와 provenance 전달
- 중복 요청에 대한 최소 의미 보장
- 동기·비동기 방식에 독립적인 전달 단계
- persistence, security와 trust boundary

### 2.2 Excluded

- transport protocol과 endpoint
- request 또는 response payload schema
- event와 message 형식
- error code와 exception type
- API resource taxonomy
- authentication protocol과 permission 구현
- serialization과 version 표기 형식
- client, server 또는 SDK 구조

## 3. Interface Principles

### 3.1 Interface Contract Is Not Transport

Interface Contract는 책임 사이에 전달되는 의미를 정의한다. function call, network request, message, event 또는 file exchange와 동일하지 않다.

### 3.2 Request Is Not Execution

요청이 수락돼도 Processing Run이나 Unit Execution이 시작 또는 성공했다고 볼 수 없다.

### 3.3 Command Is Not Decision

시스템의 처리 요청과 Human Review Decision은 다른 권위와 persistence 책임을 가진다. 일반 Command가 Accept, Reject 또는 Modify를 대신하지 않는다.

### 3.4 Domain Result Reference Is Not Domain Result Payload

Interface는 Domain Result 자체 또는 identity reference를 전달할 수 있다. 어느 방식을 사용할지는 후속 구현에서 정하며 계약의 의미는 같아야 한다.

### 3.5 Acceptance Is Not Completion

요청을 실행 대상으로 받아들였다는 사실은 실행 완료나 결과 생성을 뜻하지 않는다.

### 3.6 Completion Is Not Validation

Run 또는 Unit Execution 완료와 생성 결과의 structural validation을 분리한다.

### 3.7 Validation Is Not Approval

구조적으로 유효한 결과라도 Human Approval이 필요한 경우 자동 승인하지 않는다.

### 3.8 Failure Is Not Empty Success

Failure, partial success와 unavailable result를 정상적인 빈 결과로 표현하지 않는다.

### 3.9 External Result Is Not Canonical Domain Result

Plugin 또는 provider 결과는 Capability Contract에 따라 정규화되고 검증되기 전 LectureOS Domain Result가 아니다.

## 4. Interface Contract Structure

각 Interface Contract는 적용 가능한 범위에서 다음 책임을 설명해야 한다.

### 4.1 Responsibility Owner

계약을 제공하고 그 결과 의미를 보장하는 논리적 책임이다. 구현 process나 배포 단위를 뜻하지 않는다.

### 4.2 Caller Responsibility

요청자가 제공해야 하는 identity reference, Context, 권한 전제와 요청 의도의 정확성을 설명한다.

### 4.3 Request Intent

요청이 의도하는 처리, 조회, 판단 또는 전달 책임을 설명한다. Intent가 결과 identity나 성공을 미리 확정하지 않는다.

### 4.4 Preconditions

요청을 수락하거나 실행할 수 있기 위해 필요한 Source availability, upstream result, Configuration, Capability, validation 또는 approval 조건이다.

### 4.5 Inputs

필요한 Domain reference, Execution reference, Configuration, Capability와 Context를 설명한다. 모든 입력을 값 자체로 전달해야 한다는 뜻은 아니다.

### 4.6 Accepted Response

요청이 처리 대상으로 받아들여졌다는 의미다. Run 생성, Unit Execution 시작, 결과 생성 또는 완료를 뜻하지 않는다.

### 4.7 Execution Reference

요청으로 생성되거나 연결된 Processing Run과 Unit Execution을 추적할 수 있는 reference다.

### 4.8 Domain Result References

생성, 조회 또는 연결된 Domain Result identity와 revision 관계를 설명한다. Execution reference와 Result reference를 혼합하지 않는다.

### 4.9 Failure Contract

Request Rejection, 실행 단계별 Failure, partial success와 Human Action 필요성을 구분한다.

### 4.10 Provenance Contract

입력, upstream result, Configuration, Capability, Plugin, provider, Run, Unit Execution과 결과 사이에서 유지해야 할 provenance를 설명한다.

### 4.11 Idempotency Expectation

같은 의도의 요청이 반복될 때 보존할 기록과 자동 재사용하지 않을 identity를 설명한다. 구체적인 key나 protocol은 정의하지 않는다.

## 5. Interface Categories

### 5.1 Project Context Interfaces

Working Model의 상위 작업 문맥을 시작하거나 참조하고 Source와 관련 결과를 연결하는 책임이다.

다음 의도를 지원할 수 있어야 한다.

- 상위 작업 문맥 시작
- Source Media 등록과 reference 연결
- Source availability 확인
- 기존 작업 문맥 조회
- archive 요청

Project와 Lecture는 Working Model reference다. 이 계약은 이를 canonical Domain Entity나 CRUD resource로 확정하지 않는다.

상위 작업 문맥 시작은 Processing Run 생성을 뜻하지 않는다. Source 등록 성공과 Source Media 물리 파일 availability도 구분한다. Archive 요청은 Physical Deletion 요청이 아니다.

### 5.2 Processing Request Interfaces

Processing Run 또는 Unit Execution을 시작하거나 기존 실행 관계에 후속 행동을 요청하는 계약이다.

다음 Request Intent를 구분한다.

- 최초 처리
- 특정 Processing Unit 수행
- retry
- reprocessing
- cancellation
- recovery

Processing Request는 다음 단계를 서로 다른 의미로 전달할 수 있어야 한다.

- Request Accepted
- Processing Run Created
- Unit Execution Started
- Partial Result Available
- Unit Execution Finished
- Domain Result Generated
- Validation Finished
- Review Ready

요청 수락 응답은 최소한 후속 실행을 추적할 수 있는 reference를 제공하거나, reference가 아직 만들어지지 않았다면 그 상태를 명확히 해야 한다.

Processing Request Interface는 실행 이후 다음 기록을 조회하거나 전달하는 책임도 연결한다.

- Processing Run과 Unit Execution
- Processing State와 Execution Outcome
- Validation Result
- Failure와 Diagnostic
- retry와 reprocessing relationship
- cancellation과 recovery relationship

이 실행·검증·실패 정보는 Domain Result와 별도 책임이다. Processing Request Interface는 이를 조회하거나 전달할 수 있지만 Domain Result로 소유하거나 수정하지 않는다.

### 5.3 Domain Result Interfaces

Pipeline Result를 조회하고 다음 책임의 입력으로 연결하는 계약이다.

적용 대상은 다음을 포함할 수 있다.

- Raw Transcript
- Corrected Transcript revision
- Subtitle Candidate와 Final Subtitle
- Lecture Segment와 Analysis Finding
- Edit Candidate
- Approved Edit Decision

Domain Result 조회와 수정 의도를 같은 계약으로 혼합하지 않는다. correction, revision, Review Decision 또는 reprocessing 요청은 각각 책임이 다른 명시적 Intent를 사용한다.

Domain Result를 전달할 때 current, stale, superseded 또는 historical applicability를 숨기지 않는다. 조회 결과가 current라는 사실이 approved라는 뜻은 아니다.

Domain Result는 관련 Validation Result, Failure, Diagnostic과 Execution provenance를 참조할 수 있다. 이 참조는 Validation Result, Failure 또는 Diagnostic을 Domain Result로 만들지 않는다.

### 5.4 Review Interfaces

여러 Pipeline이 만든 Review Item을 사람에게 연결하고 Human Decision을 지속하는 계약이다.

다음 의도를 구분한다.

- Review Item 조회
- Review Context와 Source evidence 조회
- Accept
- Reject
- Modify
- Review History 조회
- stale Candidate와 Review Conflict 확인

Accept, Reject와 Modify는 Human Decision이다. 일반 Processing Command, Plugin 호출 또는 자동 retry로 대체하지 않는다.

Modify는 original Candidate를 덮어쓰지 않고 변경 결과와 Decision Provenance를 연결한다. Human Decision persistence가 실패하면 승인 성공으로 응답하지 않는다.

Review Interface는 Transcript, Subtitle 또는 Analysis를 직접 다시 수행하지 않는다. 필요한 후속 처리는 별도의 Processing Request나 reconciliation 관계로 연결한다.

### 5.5 Export Interfaces

Final Subtitle 또는 Approved Edit Decision을 Export Input으로 사용해 Artifact 생성을 요청하고 결과를 추적하는 계약이다.

다음 의도를 지원할 수 있어야 한다.

- Export Readiness 확인
- Artifact 생성 요청
- Artifact reference 조회
- Artifact availability 확인
- 보존된 승인 입력에서 Artifact 재생성 요청
- External Consumer Result 기록

Export 요청은 Approval을 생성하지 않는다. Artifact 생성 성공과 external consumer 성공을 분리한다. Artifact 물리 파일과 Artifact Record를 구분한다.

동일한 승인 입력과 Export Configuration을 사용하는 재생성은 Approved Result나 Human Decision을 변경하지 않는다.

### 5.6 Plugin Capability Interfaces

Capability Contract를 실행에 사용할 수 있는지 확인하고 외부 Plugin 또는 provider 결과를 LectureOS 경계로 가져오는 계약이다.

다음 의미를 구분한다.

- Capability availability
- Plugin compatibility와 선택 결과
- Plugin Context와 Configuration 준비
- provider-specific result 수신
- Plugin 또는 provider Failure
- normalization 및 validation 결과
- 해당 Pipeline Domain Result reference

Plugin Interface는 Pipeline Interface나 Domain Contract를 대신하지 않는다. Plugin이 compatible하다는 사실은 실행 성공, 결과 validity 또는 Human Approval을 뜻하지 않는다.

## 6. Request Lifecycle

```text
Request Intent
      |
      v
Precondition Evaluation
      |
      +----> Rejected / Not Ready
      |
      v
Request Accepted
      |
      v
Processing Run
      |
      v
Unit Execution
      |
      +----> Failure / Partial Success
      |
      v
Domain Result
      |
      v
Validation
      |
      +----> Review Readiness
      |
      v
Human Review / Export Readiness
```

이 흐름은 동기 호출 순서, event 흐름, API chain 또는 고정 orchestration이 아니다. 책임 사이에서 구분해야 할 의미를 보여준다.

Review가 필요하지 않은 결과나 실행 전에 거부되는 요청처럼 모든 요청이 전체 흐름을 거치지는 않는다.

Failure는 Domain Result의 한 종류가 아니다. Unit Execution이 실패하면 Domain Result 없이 Failure와 Diagnostic만 존재할 수 있다. Partial Success에서는 생성된 Domain Result와 Failure가 함께 존재할 수 있으며, Validation Result는 Domain Result 생성 이후 별도 관계로 연결된다.

## 7. Processing Request Contract

Processing Request는 적용 가능한 범위에서 다음을 설명할 수 있어야 한다.

- Execution Intent
- Working Model의 상위 작업 문맥 reference
- Source 또는 upstream result reference
- 요청하는 Processing Unit
- Configuration
- 필요한 Capability Contract
- retry 또는 reprocessing 여부
- 이전 Run, Unit Execution 또는 Failure와의 관계
- 요청 주체
- Human Decision이 필요한 경우 그 전제

Processing Request는 Domain Result identity를 미리 확정하지 않는다. 요청이 특정 Unit Execution 생성을 의도하더라도 실제 실행 reference와 수락 여부는 별도로 전달한다.

### 7.1 Request Acceptance

요청 수락은 precondition을 평가한 결과 해당 요청을 실행 대상으로 다룰 수 있다는 뜻이다.

수락 결과는 적용 가능한 Processing Run 또는 Unit Execution reference를 제공할 수 있어야 한다. reference가 아직 생성되지 않았다면 실행이 시작된 것처럼 응답하지 않는다.

### 7.2 Request Rejection

필수 Context, Source availability, Capability, Configuration, approval 또는 권한 전제가 충족되지 않으면 Request Rejection이나 Not Ready 상태로 드러낸다.

요청 거부는 Processing Failure가 아니다. Processing Run이 만들어지기 전 거부와 실행 준비 이후 Failure를 구분한다.

### 7.3 Retry and Reprocessing Requests

Retry 요청은 이전 실패한 Unit Execution과 같은 Processing Unit 및 실행 문맥에서 새 Unit Execution을 의도한다. Reprocessing 요청은 변경된 입력이나 조건에서 새 결과 계보를 의도한다.

두 요청 모두 기존 실행 기록, Domain Result 또는 Human Decision을 다시 쓰지 않는다.

## 8. Domain Result Contract

Domain Result 전달은 적용 가능한 범위에서 다음 관계를 설명한다.

- Domain Result identity와 종류
- Source 또는 upstream result references
- Processing Run과 Unit Execution
- Configuration
- Capability, Plugin과 provider provenance
- revision relationship
- 관련 Validation Result reference
- 관련 Failure와 Diagnostic reference 및 uncertainty
- current, stale, superseded 또는 historical applicability
- 관련 Review Item과 Human Decision

모든 Domain Result가 모든 관계를 갖는 것은 아니다. 적용되지 않는 정보를 성공처럼 채우거나 누락을 정상으로 숨기지 않는다. Validation Result, Failure와 Diagnostic은 참조되는 별도 기록이며 Domain Result의 revision이나 종류가 아니다.

### 8.1 Domain Result Identity

Domain Result identity는 Processing Run, Unit Execution, provider result 또는 전달 payload identity와 다르다. 같은 실행 요청이 반복됐다는 이유만으로 Result identity를 재사용하지 않는다.

### 8.2 Domain Result Availability

Domain Result reference가 존재한다는 사실과 결과 내용이 현재 접근 가능한지는 구분할 수 있어야 한다. 물리 정보의 일시적 부재가 provenance 또는 Human Decision을 삭제하지 않는다.

### 8.3 Partial Domain Results

부분 결과는 생성된 Domain Result reference와 별도의 Failure reference를 함께 설명한다. caller가 partial result를 사용할 수 있는지, Review에 제시할 수 있는지는 별도 Validation Result와 readiness 책임에 따른다.

## 9. Failure Contract

Failure Contract는 다음 범주를 구분한다.

- Request Rejection
- Preparation Failure
- Capability Failure
- Provider or Plugin Failure
- Processing Failure
- Validation Failure
- Persistence Failure
- Review Blocking Condition
- Export Failure
- External Consumer Failure

Failure와 Diagnostic은 Execution 및 Interface 실패 문맥이며 Domain Result가 아니다. Domain Result 없이 존재할 수 있고, Failure가 발생해도 이미 생성된 독립적인 Domain Result는 유지될 수 있다. Validation Result는 구조적 요구, Source Timeline traceability, provenance와 downstream 전달 가능성을 설명하지만 Domain Result identity나 Human Approval을 대신하지 않는다.

각 Failure는 적용 가능한 범위에서 다음 질문에 답할 수 있어야 한다.

- 어떤 요청, Run 또는 Unit Execution에서 발생했는가?
- 어떤 입력과 Domain Result가 영향을 받았는가?
- partial success와 사용 가능한 Domain Result가 있는가?
- retry할 수 있는가?
- reprocessing이 필요한가?
- Human Action이 필요한가?
- 어떤 Diagnostic과 provenance가 있는가?

Failure의 분류는 구체적인 error code나 exception class가 아니다. Failure reference와 영향 범위를 전달할 수 있어야 하며, 빈 Domain Result나 일반 완료 응답으로 바꾸지 않는다. Failure와 Diagnostic은 Domain Result 조회 계약을 통해 수정하지 않는다.

## 10. Idempotency and Duplicate Requests

이 문서는 idempotency 구현을 정하지 않지만 다음 의미를 보장한다.

- 같은 요청이 반복돼도 기존 Human Decision을 덮어쓰지 않는다.
- 반복 요청만으로 같은 Domain Result identity를 사용하지 않는다.
- 중복 요청은 새 Run, 새 Unit Execution 또는 기존 실행과의 명시적 관계로 해석할 수 있다.
- 늦게 도착한 결과를 자동으로 current로 만들지 않는다.
- retry와 reprocessing을 서로 다른 Request Intent로 전달한다.
- Artifact 재생성은 Approved Result를 변경하지 않는다.
- Human Decision 요청은 일반 자동 retry 대상이 아니다.

중복 여부 판정, 실행 재사용 정책과 구체적인 idempotency key는 Requires Validation 또는 후속 설계의 책임이다.

## 11. Synchrony and Delivery Semantics

Interface Contract는 동기 또는 비동기 전달을 고정하지 않는다.

다음 의미는 서로 다른 시점에 제공될 수 있다.

- Request Accepted
- Processing Run Created
- Unit Execution Started
- Progress Available
- Partial Result Available
- Unit Execution Finished
- Validation Finished
- Review Ready
- Artifact Available
- External Consumer Completed

하나의 응답이 모든 단계를 포함한다고 가정하지 않는다. 진행 정보가 available하다는 사실이 장기 Execution Record나 Domain Result를 뜻하지 않을 수 있다.

구체적인 polling, subscription, callback 또는 event delivery 방식은 정의하지 않는다.

## 12. Authorization and Human Authority Boundary

이 문서는 상세 permission model을 정의하지 않는다. 다만 다음 권한과 책임을 혼합하지 않는다.

- 처리 실행 요청과 Human Review Decision
- Plugin 또는 provider 실행과 Accept, Reject, Modify
- Export 실행과 Approved Result 생성
- cancellation과 기존 Domain Result 또는 Human Decision 삭제
- archive와 Physical Deletion
- External Consumer 처리와 LectureOS Decision 변경

Human Decision Interface는 외부 provider가 호출하는 자동 승인 계약으로 노출하지 않는다. 누가 Decision 권한을 갖는지와 인증 방식은 후속 Security Design에서 정한다.

## 13. Interface Version and Evolution

구체적인 version 형식은 정하지 않고 다음 원칙을 유지한다.

- Interface 변화가 Domain Concept의 의미를 조용히 변경하지 않는다.
- 새로운 전달 정보가 기존 Human Decision 의미를 소급해 바꾸지 않는다.
- Capability Contract 변화와 Interface Contract 변화를 구분한다.
- 과거 Processing Run, Unit Execution과 Domain Result provenance를 계속 해석할 수 있어야 한다.
- 호환되지 않는 변화는 Implementation Decision과 Blueprint 영향 여부를 검토한다.
- transport 교체가 Domain Result identity나 Human Authority를 변경하지 않는다.

## 14. Persistence Boundary

Interface는 Storage Model의 기록 책임을 우회하지 않는다.

- Human Decision persistence 실패를 승인 성공으로 응답하지 않는다.
- Result identity와 provenance가 안전하게 지속되지 않으면 완전한 성공으로 응답하지 않는다.
- Artifact 물리 파일만 생성되고 Artifact Record가 없으면 완전한 성공으로 취급하지 않는다.
- partial persistence를 전체 성공으로 숨기지 않는다.
- Execution Record와 Domain Result Record를 구분한다.
- 요청 응답의 일시적 전달 성공을 장기 기록 성공으로 간주하지 않는다.

구체적인 transaction, commit 또는 rollback 구현은 정의하지 않는다.

## 15. Security and Trust Boundary

이 문서는 Interface에 필요한 최소 신뢰 경계를 정의한다.

- Source Media나 Context가 외부 provider로 나가는 요청 경계를 드러낸다.
- provider-specific result는 비신뢰 외부 결과로 수신한다.
- credential 또는 secret과 Domain Context를 구분한다.
- 외부 결과의 normalization과 validation 책임을 LectureOS 경계에 둔다.
- Human Decision 요청을 외부 자동화가 대신 수행하지 못하게 한다.
- 외부 Artifact 전달과 내부 Artifact Record를 구분한다.
- 외부 전달 실패가 내부 Approved Result를 무효화하지 않게 한다.

구체적인 authentication, authorization, encryption과 secret storage는 후속 Security Design으로 넘긴다.

## 16. Blueprint and Implementation Boundary Check

| Source Document | Preserved Responsibility |
| --- | --- |
| `031_ARCHITECTURE.md` | 논리적 component와 Pipeline 책임 |
| `040_TRANSCRIPT_PIPELINE.md` | Transcript 처리 의미 |
| `041_SUBTITLE_PIPELINE.md` | Subtitle 표현과 Final Subtitle |
| `042_LECTURE_INTELLIGENCE_PIPELINE.md` | Analysis Finding과 Edit Candidate |
| `043_REVIEW_PIPELINE.md` | Human Review와 Decision |
| `044_EXPORT_PIPELINE.md` | Approved Result의 Artifact 표현 |
| `050_PLUGIN_SYSTEM.md` | Capability Contract와 Plugin 경계 |
| `010_PROJECT_LIFECYCLE.md` | 장기 작업 문맥과 readiness |
| `020_STORAGE_MODEL.md` | identity, revision, persistence와 provenance |
| `030_EXECUTION_MODEL.md` | Processing Run, Processing Unit, Unit Execution과 Failure |

Interface Contracts는 위 책임 사이의 전달 의미를 정의하지만 책임 자체를 소유하거나 재정의하지 않는다.

### Requires Blueprint Clarification

다음 기존 상태를 유지한다.

- Project와 Lecture의 Conceptual Identity
- Project Context와 lifecycle identity의 관계
- Project, Lecture와 Source Media cardinality

Interface Contract는 이 Working Model reference를 확정된 API resource나 canonical Domain Concept로 만들지 않는다.

## 17. Assumptions and Open Questions

### 17.1 Implementation Decisions

- Request Accepted와 실행 성공을 분리한다.
- Processing Request는 Run 또는 Unit Execution reference를 제공하거나 아직 생성되지 않았음을 명확히 한다.
- Domain Result는 Run 및 Unit Execution과 별도 identity를 가진다.
- Domain Result, Validation Result, Failure, Diagnostic과 Execution Record를 구분한다.
- Failure를 빈 성공 응답으로 표현하지 않는다.
- partial success를 Domain Result와 Failure reference로 구분할 수 있어야 한다.
- Human Decision Interface와 일반 Processing Interface를 분리한다.
- Plugin result는 normalization과 validation 경계를 거친다.
- Artifact 생성 결과와 External Consumer Result를 분리한다.
- Retry와 Reprocessing은 서로 다른 Request Intent다.
- 동기 또는 비동기 transport를 계약에서 고정하지 않는다.

### 17.2 Working Assumptions

- 책임 간 구현은 값 전체나 identity reference 중 적절한 전달 방식을 선택할 수 있다.
- 하나의 사용자 의도가 여러 Interface Contract를 거칠 수 있지만 각 책임의 상태는 구분해야 한다.
- 상위 작업 문맥 reference는 Interface를 연결하는 데 필요할 수 있지만 canonical identity는 아니다.
- 실행 진행 정보 중 일부는 장기 기록이 아닌 일시적 전달 정보일 수 있다.

### 17.3 Requires Validation

- Interface Category별 최소 계약 집합은 무엇인가?
- 어떤 Interface에서 Working Model의 상위 작업 문맥 reference가 필수인가?
- 하나의 요청이 여러 Processing Unit을 시작할 수 있는가?
- Run 생성과 Request Accepted는 항상 같은 시점인가?
- Unit Execution reference는 언제 caller에게 제공할 수 있는가?
- partial result를 언제 caller에게 공개할 수 있는가?
- Review Interface에 Review Session이 항상 필요한가?
- Modify 요청이 변경 결과 생성까지 포함하는가?
- Artifact 재생성이 새 Artifact identity를 만드는가?
- External Consumer Result를 어느 범위까지 추적하는가?
- Capability Negotiation 실패를 Request Rejection과 Execution Failure 중 어디에 분류하는가?
- Interface 호환성의 최소 보장 범위는 무엇인가?
- 중복 요청이 기존 실행을 참조할 수 있는 조건은 무엇인가?

### 17.4 Requires Blueprint Clarification

- Project와 Lecture의 Conceptual Identity
- Project Context와 lifecycle identity의 관계
- Project, Lecture와 Source Media cardinality

### 17.5 Deferred

- transport와 protocol 선택
- payload와 serialization schema
- endpoint와 resource 설계
- error code와 exception mapping
- event 및 message delivery 구현
- authentication과 authorization 구현
- Interface version 표기와 compatibility mechanism
- client, server와 SDK 구조

## 18. Validation Criteria

- Interface Contract와 transport를 구분한다.
- Request Accepted, Run 생성, Unit Execution 시작, 결과 생성과 완료를 구분한다.
- Processing Request와 Human Decision을 분리한다.
- Domain Result identity와 Execution reference를 분리한다.
- Validation Result, Failure와 Diagnostic을 Domain Result로 분류하지 않는다.
- Domain Result가 없는 Failure와 Domain Result 및 Failure가 함께 존재하는 partial success를 표현할 수 있다.
- Completion, Validation, Review Readiness와 Approval을 구분한다.
- Failure, partial success와 unavailable result를 빈 성공으로 숨기지 않는다.
- Retry와 Reprocessing을 별도 Request Intent로 유지한다.
- provider-specific result가 normalization과 validation 전 canonical Domain Result가 되지 않는다.
- Artifact 생성 결과와 External Consumer Result를 분리한다.
- Human Decision persistence 실패를 승인 성공으로 응답하지 않는다.
- Project와 Lecture를 canonical API resource로 확정하지 않는다.
- 특정 protocol, payload, framework 또는 runtime 기술을 선택하지 않는다.
- Blueprint와 승인된 Implementation Design의 책임을 다시 정의하지 않는다.

## Non-Goals

이 문서는 다음을 정의하지 않는다.

- REST, GraphQL 또는 RPC
- HTTP method, URL과 endpoint
- WebSocket, event bus와 message broker
- JSON 또는 request/response schema
- event schema와 message format
- error code와 exception class
- authentication protocol
- SDK와 client library
- code와 programming language
- framework와 runtime topology
- concrete versioning format
- transaction과 delivery guarantee 구현

## Related Documents

- [Implementation Design Guide](./000_IMPLEMENTATION_DESIGN_GUIDE.md)
- [Project Lifecycle](./010_PROJECT_LIFECYCLE.md)
- [Storage Model](./020_STORAGE_MODEL.md)
- [Execution Model](./030_EXECUTION_MODEL.md)
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
