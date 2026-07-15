# Project Lifecycle

- Status: Approved
- Baseline: LectureOS Blueprint v1
- Baseline Commit: `b0251cf56628f012891e39eebe7f57c2be63c684`
- Last Updated: 2026-07-15
- Depends On: `000_IMPLEMENTATION_DESIGN_GUIDE.md`, `../docs/020_PRODUCT_REQUIREMENTS.md`, `../docs/021_SYSTEM_CONTEXT.md`, `../docs/030_DATA_MODEL.md`, `../docs/031_ARCHITECTURE.md`, `../docs/040_TRANSCRIPT_PIPELINE.md`, `../docs/041_SUBTITLE_PIPELINE.md`, `../docs/042_LECTURE_INTELLIGENCE_PIPELINE.md`, `../docs/043_REVIEW_PIPELINE.md`, `../docs/044_EXPORT_PIPELINE.md`, `../docs/050_PLUGIN_SYSTEM.md`
- Referenced By:
- Requires Blueprint Clarification: Project와 Lecture의 Conceptual Identity 및 cardinality

## Purpose

이 문서는 LectureOS에서 하나의 후반작업이 시작되고, 처리·검수·승인·export·재처리를 거쳐 장기간 보존되거나 archive되는 lifecycle을 구현 책임 수준에서 정의한다. Project와 Lecture는 이 흐름을 설명하기 위한 Working Model이며 아직 확정된 canonical Domain Concept가 아니다.

Project Lifecycle은 Blueprint의 Pipeline을 다시 정의하지 않는다. 여러 Pipeline의 결과, Processing Run, Human Decision과 Artifact가 하나의 지속적인 작업 문맥에서 어떻게 공존하는지 설명한다.

## 1. Blueprint Basis

### 1.1 Confirmed by Blueprint

- Project Context는 Source Media, 선택적 강의 맥락, 처리 설정과 사용자 결정을 하나의 작업 목적으로 연결하는 최소 상위 문맥이다.
- Source Media와 Source Timeline은 파생 처리로 변경되지 않는다.
- Processing Run은 결과가 생성된 실행 문맥과 provenance를 설명하지만 지속되는 Domain Concept의 identity를 소유하지 않는다.
- Text Pipeline과 Edit Pipeline은 동등한 핵심이며 독립적으로 진행될 수 있다.
- Processing State는 Domain Result나 Human Decision을 대신하지 않는다.
- 부분 성공은 전체 성공으로 단순화되지 않는다.
- Review Decision과 Approved Edit Decision은 재처리 후에도 보존된다.
- Artifact는 승인 결과에서 파생되며 Project 완료나 Domain Result를 대신하지 않는다.
- Plugin 또는 provider 교체가 기존 provenance와 Human Decision을 지우지 않는다.

### 1.2 Blueprint Gap

`030_DATA_MODEL.md`는 `Project`와 `Lecture`를 별도 Concept로 확정할 근거가 부족하다고 명시하고 `Project Context`를 최소 상위 문맥으로 사용한다.

이 문서는 lifecycle 책임을 설명하기 위해 Project와 Lecture를 서로 다른 **Working Model 역할**로 임시 사용한다. 현재 구현 기준선으로 확정하거나 새로운 canonical Domain Entity로 승격하는 것이 아니며, 다른 구현 모델로 대체될 가능성도 열어둔다. Conceptual Identity와 cardinality의 정식 분리는 Blueprint clarification 또는 PATCH가 필요하다.

## 2. Scope

### 2.1 Included

- Project와 Lecture Working Model의 임시 역할
- Source Registration
- Processing Run과 Processing State
- Project Lifecycle State
- Text and Edit Processing의 부분 진행
- Review Readiness와 Human Review
- Approved Result와 Export Readiness
- Export Activity와 Artifact Availability
- reprocessing, stale result와 reconciliation
- archive와 장기 보존 책임
- failure, recovery와 persistence responsibility

### 2.2 Excluded

- Transcript, Subtitle, Analysis, Review와 Export의 내부 처리 규칙
- 고정된 전역 상태 머신
- orchestration algorithm과 scheduler
- 저장 구조와 database schema
- API와 UI navigation
- 실행 방식과 기술 스택
- Plugin Runtime과 provider adapter
- 실제 편집, Rendering과 외부 NLE round trip

## 3. Core Distinctions

### 3.1 Project Is Not Lecture

이 문서의 Working Model에서 Project 역할은 사용자가 하나 이상의 LectureOS 작업과 관련 입력, 결과, Review, Decision과 Artifact를 관리하는 지속적인 작업 문맥을 나타낸다.

Lecture 역할은 Transcript, Subtitle, Analysis, Review와 Export가 같은 교육 내용으로 이해되는 강의 단위를 나타낸다.

두 역할은 lifecycle을 설명하기 위해 구분할 뿐 구현 기준선이나 canonical identity로 확정하지 않는다. 다음 관계도 결정하지 않는다.

- Project 하나에 Lecture가 몇 개 포함되는가?
- Lecture 하나가 여러 Project에서 재사용되는가?
- 하나의 Lecture가 몇 개의 Source Media로 구성되는가?

### 3.2 Project State Is Not Pipeline State

Project Lifecycle은 작업 문맥이 생성, 처리, 검수, 재처리와 archive를 거치며 시간에 따라 어떻게 발전하는지를 설명하는 모델이다. Project Lifecycle State는 그 모델 안에서 Project 역할이 현재 어떤 작업 문맥에 있는지를 나타내는 한 시점의 상태다.

Processing State는 특정 Processing Run 또는 처리 책임의 진행과 결과 상태를 설명한다.

하나의 Pipeline이 실패하거나 대기 중이어도 Project와 다른 유효한 결과는 유지된다. Project 상태를 모든 Pipeline 상태의 단순 합계나 단일 성공·실패 값으로 계산하지 않는다.

### 3.3 Lifecycle Is Not Processing Order

Lifecycle은 사용자의 작업, 결과와 결정이 시간에 따라 어떻게 지속되는지 설명한다. Pipeline의 고정 실행 순서나 orchestration algorithm이 아니다.

Text Pipeline과 Edit Pipeline은 각자의 전제 안에서 독립적으로 진행될 수 있다. 같은 Project 안에서도 일부 결과는 다른 결과보다 먼저 Review 가능할 수 있다.

### 3.4 Processing Run Is Not Domain Result

Processing Run은 특정 입력, Configuration과 Capability Context에서 하나 이상의 처리 책임을 수행한 실행 문맥이다.

Processing Run은 어떤 실행 책임이 어떤 조건에서 수행되었는지를 설명한다. Pipeline Result, Review Decision, Approved Result와 Artifact를 소유하지 않는다.

따라서 Processing Run이 끝나거나 실패해도 Source Media와 해당 Domain Result의 lifecycle이 끝나는 것이 아니며, 그 identity가 Run에 흡수되거나 함께 사라지지 않는다.

### 3.5 Artifact Is Not Project Completion

Artifact 하나가 생성되었다고 Working Model의 상위 작업 문맥에 속한 모든 작업이 끝난 것은 아니다. 다른 Pipeline의 Review, 다른 Export Profile, 재처리 또는 추가 Lecture 역할의 작업이 남아 있을 수 있다.

### 3.6 Validation Is Not Review or Approval

Validation은 결과가 구조적으로 추적 가능하고 처리 가능한지 판단한다. Review Readiness는 사람이 검토할 수 있는지를 설명하며, Approval은 Human Decision을 통해서만 발생한다.

## 4. Core Concepts

### 4.1 Project Role — Working Model

Project 역할은 현재 lifecycle 설계를 진행하기 위한 Working Model이다. 사용자가 하나 이상의 LectureOS 작업을 수행하고 관련 입력, Pipeline Result, Review, Decision과 Artifact를 연결하는 지속적인 작업 문맥을 가정한다.

이 역할은 다음과 동일하지 않다.

- 한 번의 실행 요청
- Processing Run
- 파일 시스템의 폴더
- Source Media 하나
- Export Artifact 하나

현재 설계에서는 작업이 중단되거나 archive되어도 provenance와 Human Decision을 연결하는 문맥이 필요하다고 본다. 그 문맥의 canonical 이름과 identity는 확정하지 않는다.

### 4.2 Lecture Role — Working Model

Lecture 역할도 현재 lifecycle 설계를 위한 Working Model이다. 분석, Transcript, Subtitle, Review와 Export가 같은 강의 내용으로 이해되는 작업 단위를 가정한다.

이 역할을 Source Media 하나와 동일하다고 단정하지 않는다. 여러 Source Media의 결합, 하나의 Source Media 재사용과 Lecture 역할 사이의 cardinality는 Requires Validation이다.

### 4.3 Processing Run

Processing Run은 특정 입력, Configuration과 Capability Context에서 하나 이상의 처리 책임을 수행한 실행 문맥이다.

Processing Run은 다음을 설명해야 한다.

- 어떤 입력과 조건에서 처리가 수행되었는가?
- 어떤 Pipeline 책임과 Capability가 참여했는가?
- 어떤 결과, Failure와 Diagnostic이 생성되었는가?
- 이전 Run 또는 결과와 어떤 재처리 관계가 있는가?

Processing Run은 실행 책임과 그 문맥을 설명할 뿐 Pipeline Result, Review Decision, Approved Result와 Artifact를 소유하거나 대체하지 않는다. Run의 종료는 이 결과들의 lifecycle 종료를 의미하지 않는다.

### 4.4 Project Lifecycle State

Project Lifecycle State는 Reference Lifecycle 안에서 Project 역할이 현재 어떤 작업을 허용하고 어떤 장기 문맥에 있는지 설명하는 상태다. Lifecycle 자체나 진행 이력을 대신하지 않는다.

Project Lifecycle State는 다음과 같은 질문에 답할 수 있어야 한다.

- 새 Source나 Lecture 작업을 연결할 수 있는가?
- 처리, Review, Export 또는 재처리를 계속할 수 있는가?
- 활성 작업에서 제외되어 archive되었는가?
- 사용자의 추가 조치가 필요한가?

이 문서는 고정된 상태 목록과 전이표를 확정하지 않는다.

### 4.5 Processing State

Processing State는 개별 Processing Run 또는 처리 책임의 현재 진행, 완료, 부분 성공, 실패와 복구 가능성을 설명한다.

Processing State는 Project Lifecycle State, Pipeline Result의 유효성 또는 Human Approval을 대신하지 않는다.

### 4.6 Review Readiness

Review Readiness는 Pipeline Result, Candidate, Failure 또는 Uncertainty가 충분한 Review Context와 traceability를 갖추어 Human Review에 제시될 수 있는지를 설명하는 조건이다.

Review Ready라는 사실은 다음을 뜻하지 않는다.

- Validation이 모든 의미 정확성을 보장함
- Candidate가 승인됨
- Review Decision이 이미 존재함
- 관련 Pipeline 전체가 완료됨

### 4.7 Export Readiness

Export Readiness는 Final Subtitle 또는 Approved Edit Decision이 필요한 provenance와 validation을 유지하며 Export Input으로 사용 가능한지를 설명하는 조건이다.

Export Ready라는 사실은 Artifact가 이미 생성되었거나 외부 consumer가 처리에 성공했음을 뜻하지 않는다.

### 4.8 Archive

Archive는 Working Model의 상위 작업 문맥을 활성 작업 대상에서 제외하되 Project Context, Source identity, provenance, Human Decision, Approved Result와 Artifact 관계를 보존하는 lifecycle 상태다.

Archive는 Delete가 아니다. Archive된 Project를 다시 활성 작업으로 전환할 수 있어야 하는지는 Requires Validation이다.

### 4.9 Approved Result

Approved Result는 Human Review를 거쳐 외부 작업이나 Artifact 생성에 사용할 수 있는 승인 결과다. Final Subtitle과 Approved Edit Decision의 의미는 각 Blueprint 문서를 따른다.

Project Lifecycle은 Approved Result를 만들거나 승인하지 않고 Project 안에서 그 지속성과 사용 가능성을 연결한다.

### 4.10 Export Activity

Export Activity는 승인된 Export Input, Export Configuration, Profile과 Scope를 사용해 Artifact를 만드는 작업 문맥이다.

Project Lifecycle은 Export Activity와 Project의 관계를 연결하지만 Export 규칙이나 Artifact 의미를 다시 정의하지 않는다.

### 4.11 Artifact

Artifact는 승인 결과를 외부에서 사용할 수 있게 표현한 파생 결과다. Project Lifecycle에서는 Artifact의 availability, provenance와 관련 Approved Result를 연결한다.

Artifact 손실은 Project, Human Decision 또는 Approved Result의 손실을 의미하지 않는다.

## 5. Reference Lifecycle

```text
Project Creation
        |
        v
Lecture and Source Registration
        |
        v
Processing Preparation
        |
        v
Text and/or Edit Processing
        |
        v
Validation and Review Readiness
        |
        v
Human Review
        |
        v
Approved Results
        |
        v
Export Activity
        |
        v
Artifact Availability
        |
        v
Reprocessing / Continued Review / Archive
```

이 흐름은 사용자의 장기 작업을 설명하기 위한 **Reference Lifecycle**이다. 실행 순서, orchestration 또는 상태 머신을 정의하지 않는다. 각 phase는 반복되거나 생략될 수 있고, 서로 다른 Lecture 역할과 Pipeline에서 동시에 다른 지점에 있을 수 있다.

## 6. Reference Lifecycle Phases

이 절의 phase 이름은 구현 component나 고정 state가 아니다. 장기 작업에서 나타나는 책임과 전환 지점을 설명하기 위한 권장 흐름이다.

### 6.1 Project Creation

Working Model의 지속적인 작업 문맥을 시작한다. `Project Creation`은 이 책임을 설명하기 위한 임시 이름이며 Source Media 처리나 Processing Run 시작과 동일하지 않다.

이 상위 작업 문맥을 시작할 때 최소한 어떤 정보가 필요한지는 Requires Validation이며, Course, Student 또는 Classroom 같은 교육 관리 개념을 추가하지 않는다.

### 6.2 Lecture and Source Registration

Lecture 역할과 Source Media identity를 상위 작업 문맥에 연결하고 Source Timeline을 추적할 준비를 한다. Project와 Lecture의 canonical identity를 확정하는 phase가 아니다.

Registration은 다음을 보장해야 한다.

- Source Media를 변경하지 않는다.
- 외부 파일의 위치와 LectureOS의 identity 책임을 구분한다.
- 같은 Source를 중복 등록하거나 재사용하는 경우를 식별할 수 있어야 한다.
- 등록 실패가 기존 Project와 다른 Source의 유효성을 손상시키지 않는다.

### 6.3 Processing Preparation

처리에 필요한 Source, Context, Configuration, Capability와 validation 전제를 확인한다.

Preparation은 Processing Run의 실행 성공이나 결과 승인을 보장하지 않는다. 필요한 Context가 없거나 Plugin Capability가 compatible하지 않으면 명시적인 Failure로 남긴다.

### 6.4 Text and/or Edit Processing

Text Pipeline과 Edit Pipeline은 상위 Blueprint가 정의한 책임에 따라 결과를 만든다.

- Text 처리는 Raw Transcript, Corrected Transcript와 Subtitle 결과를 발전시킨다.
- Edit 처리는 Analysis Finding, Lecture Segment와 Edit Candidate를 준비한다.
- 두 흐름은 동등하며 한쪽을 다른 쪽의 필수 부가 단계로 만들지 않는다.
- 각 결과는 해당 Processing Run과 provenance를 유지한다.

### 6.5 Validation and Review Readiness

각 Pipeline은 자신의 구조적 validation을 수행하고 필요한 Review Item을 Review Pipeline에 전달한다.

Project Lifecycle은 어떤 결과가 Review Ready인지 연결하지만 Validation 기준이나 Review Item을 생성하는 책임을 흡수하지 않는다.

### 6.6 Human Review

Review Pipeline은 여러 Pipeline이 보낸 Review Item을 Human Review 대상으로 연결하고 Accept, Reject, Modify를 Review Decision으로 기록한다.

Project Lifecycle은 Review Session, History, Decision과 관련 결과를 Project 문맥에 연결하되 Human Decision을 만들거나 변경하지 않는다.

### 6.7 Approved Results

적용 가능한 Review Decision을 반영한 Final Subtitle과 Approved Edit Decision이 존재할 수 있다.

한 종류의 Approved Result가 있다고 다른 결과까지 승인되거나 Project 전체가 완료된 것으로 간주하지 않는다.

### 6.8 Export Activity and Artifact Availability

Export Ready인 Approved Result를 사용해 Export Activity를 수행할 수 있다. 성공한 Artifact와 Export Failure는 같은 Project에서 별도로 존재할 수 있다.

Artifact Availability는 다음을 설명할 수 있어야 한다.

- 어떤 Approved Result와 Export Configuration에서 생성되었는가?
- 현재 사용할 수 있는가?
- 이후 승인 결과 변경으로 stale해졌는가?
- 외부 consumer 처리 여부와 LectureOS 생성 성공을 구분할 수 있는가?

### 6.9 Reprocessing, Continued Review, and Archive

현재 Working Model의 상위 작업 문맥에서는 Artifact 생성 이후에도 재처리, 추가 Review, 다른 Export Profile 또는 새 Lecture 역할의 작업을 계속할 수 있다.

활성 작업이 끝나면 archive할 수 있지만, archive는 Source identity, provenance와 Human Decision을 삭제하지 않는다.

## 7. State Model

Reference Lifecycle은 하나의 전역 상태 대신 서로 다른 상태 관점을 함께 구분한다. Lifecycle은 시간에 따른 발전 모델이고, 아래 상태들은 각 대상의 현재 조건을 설명하는 관점이다.

| State View | Subject | Meaning |
| --- | --- | --- |
| Project Lifecycle State | Project 역할 | 작업을 계속할 수 있는지, archive되었는지와 같은 상위 문맥 |
| Processing State | Processing Run 또는 처리 책임 | 진행, 완료, 부분 성공, 실패와 복구 가능성 |
| Validation Result | Pipeline Result | 구조적 요구와 traceability 충족 여부 |
| Review Readiness | Review 대상 | 사람이 판단할 수 있는 Context 준비 여부 |
| Review Decision Status | Review Decision | 사용자의 판단과 현재 적용 가능성 |
| Export Readiness | Approved Result | Export Input으로 사용할 수 있는지 여부 |
| Artifact Availability | Artifact | 생성 여부, 사용 가능성, provenance와 stale 여부 |

각 상태 관점은 서로 관련될 수 있지만 자동으로 같은 값이 되지 않는다.

## 8. Partial Progress

Reference Lifecycle은 상위 작업 문맥에 속한 여러 결과의 진행 상태를 하나의 성공·실패 값으로 축소하지 않는다.

다음은 모두 유효한 부분 진행 상태다.

- Transcript는 완료됐지만 Subtitle은 미완료다.
- Subtitle은 Review 가능하지만 Lecture Intelligence는 실패했다.
- 일부 Edit Candidate만 Review가 완료되었다.
- Approved Edit Decision은 존재하지만 Artifact는 아직 없다.
- 하나의 Export Profile은 성공했지만 다른 Profile은 실패했다.
- 재처리 결과와 기존 승인 결과가 동시에 존재한다.

부분 진행은 다음을 보장해야 한다.

- 유효한 결과와 실패한 범위를 구분한다.
- 결과마다 provenance, validation과 Review 상태를 확인할 수 있다.
- 독립적으로 유효한 결과를 근거 없이 무효화하지 않는다.
- 사용자가 다음에 필요한 작업을 판단할 수 있어야 한다.

부분 결과를 사용자에게 노출하는 구체적인 기준은 Requires Validation이다.

## 9. Reprocessing and Reconciliation

### 9.1 Reprocessing Triggers

다음 변화는 reprocessing을 유발할 수 있다.

- 등록된 Source 선택 또는 관련 Context 변경
- ASR, correction, analysis 또는 export Capability 변경
- Plugin 또는 provider 교체
- 처리 Configuration이나 validation 기준 변경
- Transcript 또는 Subtitle revision 변경
- Human Review 이후 새 Candidate 생성
- Export Profile 또는 Configuration 변경

이 목록은 고정된 재실행 규칙이 아니다. 어떤 변화가 어떤 결과에 영향을 주는지는 후속 Reprocessing Design에서 구체화한다.

### 9.2 New Processing Run

재처리는 새 Processing Run을 만들 수 있다. 새 Run은 기존 결과를 덮어쓰지 않고 어떤 입력과 조건이 달라졌는지 provenance로 설명해야 한다.

새 Run의 생성이 기존 Domain Result를 자동 폐기하거나 새 결과를 현재 결과로 자동 승격하지 않는다.

### 9.3 Result Continuity

- 영향받지 않은 결과는 재사용할 수 있어야 한다.
- 이전 결과와 새 결과는 각각의 provenance를 유지한다.
- 기존 Human Decision을 새 Candidate에 자동 적용하지 않는다.
- 적용 가능성이 불명확한 결과나 Candidate는 stale 또는 reconciliation 필요 상태로 구분한다.
- 기존 Artifact와 새 Approved Result의 관계를 설명할 수 있어야 한다.
- 새 export가 실패해도 기존 Approved Result와 독립적으로 유효한 Artifact를 손상시키지 않는다.

### 9.4 Reconciliation Responsibility

Project Lifecycle은 reconciliation이 필요한 대상을 연결하고 작업 가능성을 드러낸다. Candidate와 Review Decision의 구체적인 reconciliation 의미는 Review Pipeline 계약을 따르며, 자동 병합 algorithm은 정의하지 않는다.

## 10. Failure and Recovery

### 10.1 Source Registration Failure

Source Media identity, 접근 가능성 또는 Source Timeline 연결을 안전하게 준비하지 못한 상태다. 등록되지 않은 Source를 정상 입력으로 처리하지 않는다.

### 10.2 Processing Preparation Failure

필수 Context, Configuration, Capability 또는 실행 전제를 충족하지 못한 상태다. Processing Run이 정상 시작되었다고 표시하지 않는다.

### 10.3 Pipeline Failure

Transcript, Subtitle 또는 Lecture Intelligence 책임이 필요한 결과를 만들지 못한 상태다. 실패한 Pipeline과 독립적인 다른 결과는 유지한다.

### 10.4 Provider or Plugin Failure

외부 provider 또는 Plugin이 Capability Contract에 맞는 결과를 제공하지 못한 상태다. provider failure를 빈 Domain Result나 전체 Project 실패로 바꾸지 않는다.

### 10.5 Validation Failure

Pipeline Result가 구조, provenance 또는 traceability 요구를 충족하지 못한 상태다. Human Approval이나 정상 downstream 입력으로 자동 승격하지 않는다.

### 10.6 Review Blocking Condition

Review Context 부족, Source 접근 실패, stale Candidate 또는 unresolved conflict 때문에 사람이 안전하게 판단할 수 없는 상태다. Review Decision을 추측하거나 자동 생성하지 않는다.

### 10.7 Export Failure

Approved Result를 선택한 Export Profile과 Configuration에 맞는 Artifact로 표현하지 못한 상태다. Approved Result와 Review History는 유지한다.

### 10.8 External Consumer Failure

외부 consumer가 Artifact를 받거나 처리하지 못한 상태다. LectureOS의 Export 성공, Artifact availability와 외부 처리 결과를 구분한다.

### 10.9 Recovery Rules

- recovery는 기존 provenance와 Human Decision을 삭제하거나 덮어쓰지 않는다.
- 실패 범위와 영향받은 결과를 식별한다.
- 완료된 독립 결과를 재사용할 수 있어야 한다.
- 새 시도는 이전 실패와의 관계를 설명할 수 있어야 한다.
- 복구 불가능하거나 사용자 판단이 필요한 상태를 정상 완료로 숨기지 않는다.

## 11. Persistence Responsibility

구현은 실행이 끝난 뒤에도 필요한 작업 문맥, provenance와 Human Decision을 유지해야 한다. 다음 목록은 그 책임을 검토하기 위한 **persistent record responsibility 후보**이며, 확정된 저장 모델, entity 목록 또는 schema가 아니다.

| Record Candidate | Persistence Responsibility |
| --- | --- |
| Project 역할 참조 | Working Model의 작업 목적, lifecycle 문맥과 관련 LectureOS 결과를 연결할 필요성을 나타낸다. |
| Lecture 역할 참조 | 같은 강의 내용으로 이해되는 작업과 결과를 연결할 필요성을 나타낸다. Conceptual status는 clarification이 필요하다. |
| Source Media identity | 외부 원본을 변경하지 않고 참조하며 수명주기 관계를 설명한다. |
| Source Timeline | 모든 시간 기반 결과가 돌아갈 공통 기준을 보존한다. |
| Pipeline Result | 각 Pipeline의 결과, revision, validation과 provenance를 보존한다. |
| Processing Run provenance | 입력, 조건, Capability, 결과와 실패의 생성 문맥을 보존한다. |
| Review Decision | Accept, Reject, Modify와 Decision Provenance를 보존한다. |
| Approved Edit Decision | 승인된 편집 의도와 Source Timeline 연결을 보존한다. |
| Export Artifact provenance | Artifact와 Approved Result, Profile, Configuration과 Scope의 관계를 보존한다. |
| Failure and reconciliation relationship | 실패, stale result, conflict와 후속 결과의 관계를 보존한다. |

### 11.1 Long-Lived Records

Source identity, provenance, Human Decision, Approved Result와 그 관계는 개별 Processing Run보다 오래 지속될 수 있다. 이를 어떤 record로 나눌지는 후속 Storage Design에서 결정한다.

### 11.2 Ephemeral Execution Information

실행 중에만 필요한 진행 신호, 임시 자원 정보와 provider 호출 세부사항은 장기 Domain Record와 구분한다. 어떤 실행 정보가 recovery와 provenance에 필요한지는 후속 Execution Model에서 정한다.

### 11.3 Persistence Invariants

- Processing Run 종료가 Domain Record 삭제를 의미하지 않는다.
- Artifact 손실이 Approved Result 손실을 의미하지 않는다.
- archive가 provenance와 Human Decision 삭제를 의미하지 않는다.
- 재처리가 이전 결과와 결정 이력을 덮어쓰지 않는다.
- 저장 기술이 Conceptual Identity를 정의하지 않는다.

구체적인 database, schema, key, transaction과 retention 기간은 이 문서에서 정하지 않는다.

## 12. Security and Trust Boundary

이 문서는 lifecycle이 만나는 최소 신뢰 경계만 표시한다.

- Source Media와 개인정보가 외부 provider 또는 Plugin Context로 전달되는지 식별할 수 있어야 한다.
- 외부 consumer의 결과를 LectureOS Domain State로 자동 신뢰하지 않는다.
- archive가 접근 권한, 보존 또는 삭제 정책을 자동으로 결정하지 않는다.

접근 정책, permission model, 개인정보 처리 규칙과 보안 통제는 이 문서에서 정의하지 않으며 후속 Security Design으로 넘긴다.

## 13. Blueprint Boundary Check

Project Lifecycle은 다음 문서의 책임을 조정하고 연결할 뿐 다시 소유하지 않는다.

| Blueprint | Preserved Responsibility |
| --- | --- |
| `030_DATA_MODEL.md` | Domain Concept, identity, lineage와 provenance |
| `031_ARCHITECTURE.md` | 논리적 처리 책임과 component 경계 |
| `040_TRANSCRIPT_PIPELINE.md` | Raw Transcript와 Corrected Transcript |
| `041_SUBTITLE_PIPELINE.md` | Subtitle와 Final Subtitle |
| `042_LECTURE_INTELLIGENCE_PIPELINE.md` | Analysis Finding, Lecture Segment와 Edit Candidate |
| `043_REVIEW_PIPELINE.md` | Human Review와 Review Decision |
| `044_EXPORT_PIPELINE.md` | Export Input, Activity와 Artifact 표현 |
| `050_PLUGIN_SYSTEM.md` | Capability Contract, Plugin Context와 provider 경계 |

### Requires Blueprint Clarification

Project와 Lecture를 별도 canonical Concept로 확정하는 것은 `030_DATA_MODEL.md`의 현재 미결정 사항을 하위 설계에서 해결하는 일이 된다. 이 문서는 구현 설계 역할만 구분하며, Conceptual Identity와 cardinality는 Blueprint clarification 또는 PATCH 전까지 Working Assumption으로 유지한다.

## 14. Assumptions and Open Questions

### 14.1 Implementation Decisions

- Project Lifecycle State와 Processing State를 분리한다.
- lifecycle을 고정 Processing Order로 사용하지 않는다.
- Review Readiness, Export Readiness, Approval과 Artifact Availability를 서로 다른 상태 관점으로 다룬다.
- 부분 진행과 부분 실패를 Project의 단일 성공·실패 값으로 축소하지 않는다.
- Processing Run과 장기 Domain Record의 persistence 책임을 분리한다.
- Archive를 Delete와 구분한다.

### 14.2 Working Assumptions

- Working Model에서 Project 역할은 지속적인 작업 문맥으로, Lecture 역할은 그 안에서 강의 의미를 연결하는 작업 단위로 유용하다.
- Text와 Edit 처리는 각자의 전제가 충족되면 독립적으로 진행될 수 있다.
- 하나의 Project에서 여러 Export Activity와 Artifact가 존재할 수 있다.

### 14.3 Requires Validation

- Project와 Lecture의 cardinality는 무엇인가?
- Lecture와 Source Media의 cardinality는 무엇인가?
- 여러 Source Media가 하나의 Source Timeline을 공유할 수 있는가?
- Text Pipeline과 Edit Pipeline의 최소 실행 의존성은 무엇인가?
- Project 완료를 별도 lifecycle 의미로 정의할 필요가 있는가?
- Archive된 Project를 다시 활성화할 수 있어야 하는가?
- Archive와 Delete의 정확한 경계와 retention 책임은 무엇인가?
- 부분 결과를 사용자에게 노출하는 기준은 무엇인가?
- Processing Run이 장기 provenance로 남겨야 할 최소 범위는 무엇인가?
- 동일 Project 안에서 여러 export 목적과 Profile을 어떻게 관리할 것인가?

### 14.4 Requires Blueprint Clarification

- Project와 Lecture는 별도 canonical Domain Concept인가?
- Project Context와 이 문서의 Project lifecycle identity는 같은 Concept인가?

### 14.5 Deferred

- 고정 Project state 목록과 transition table
- Processing Job과 orchestration 책임
- 구체적인 reconciliation algorithm
- persistent storage model
- interface contract와 payload
- permission과 retention 구현
- UI navigation과 사용자 작업 화면

## 15. Validation Criteria

- Project와 Lecture의 구현 역할을 구분하되 canonical identity를 확정하지 않는다.
- Project Lifecycle State와 Processing State를 혼합하지 않는다.
- lifecycle을 Pipeline 실행 순서로 사용하지 않는다.
- Processing Run을 Domain Result의 identity나 저장 단위로 사용하지 않는다.
- 부분 성공과 독립적인 Pipeline 진행을 표현할 수 있다.
- Review Readiness, Approval, Export Readiness와 Artifact Availability를 구분한다.
- reprocessing에서 기존 Human Decision과 provenance를 보존한다.
- failure와 recovery가 독립적인 유효 결과를 손상시키지 않는다.
- archive를 delete로 취급하지 않는다.
- 특정 저장, 실행, provider 또는 기술 스택을 선택하지 않는다.
- 기존 Blueprint Pipeline 책임을 재정의하지 않는다.

## Non-Goals

이 문서는 다음을 정의하지 않는다.

- database schema와 storage vendor
- API와 구체적인 interface
- queue, worker와 orchestration engine
- scheduler와 실행 algorithm
- 특정 상태 머신 구현
- UI navigation
- cloud architecture
- programming language와 framework
- 실제 구현 코드
- Plugin Runtime과 provider adapter
- 실제 영상 편집과 Rendering

## Related Documents

- [Implementation Design Guide](./000_IMPLEMENTATION_DESIGN_GUIDE.md)
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
