# 031_ARCHITECTURE

- Status: Draft
- Version: Blueprint 0.1
- Last Updated: 2026-07-14
- Layer: L1 — Logical System Architecture
- Depends On:
  - `000_MANIFESTO.md`
  - `001_PRODUCT.md`
  - `002_FAQ.md`
  - `003_VISION.md`
  - `004_PRINCIPLES.md`
  - `020_PRODUCT_REQUIREMENTS.md`
  - `021_SYSTEM_CONTEXT.md`
  - `030_DATA_MODEL.md`
  - `../patches/PATCH-0001-l0-and-prd-stabilization.md`
- Referenced By:
  - `040~044` Pipeline Documents

## Purpose

이 문서는 LectureOS의 Logical System Architecture를 정의한다. `030_DATA_MODEL.md`의 Conceptual Model을 처리하기 위한 책임 단위, 처리 흐름, orchestration, 외부 경계, 재처리와 실패 대응을 설명한다.

이 문서는 기술 스택이나 물리적 실행 구조를 정하지 않는다. 프레임워크, 프로그래밍 언어, 데이터베이스, API 형식, 메시징 방식, thread 또는 process model, 배포 topology, 디렉터리 구조는 의도적으로 정의하지 않는다.

## 1. Architecture Goals

LectureOS Architecture는 다음 목표를 따른다.

1. **Boundary First:** `021_SYSTEM_CONTEXT.md`가 정한 LectureOS와 외부 시스템의 경계를 유지한다.
2. **Concept Before Component:** `030_DATA_MODEL.md`의 개념과 책임이 컴포넌트보다 먼저 존재한다. 컴포넌트는 개념을 처리할 뿐 개념의 identity를 독점하지 않는다.
3. **Equal Core Pipelines:** Text Pipeline과 Edit Pipeline을 동등한 핵심 흐름으로 지원한다.
4. **Replaceable AI:** ASR, correction, LLM, 강의 분석 역할을 특정 External AI Provider에 종속시키지 않는다.
5. **Original Never Changes:** Source Media와 Source Timeline을 변경하지 않고 모든 시간 기반 결과의 추적성을 유지한다.
6. **Human Authority:** AI 결과는 후보로 다루며 Review Decision 없이 사용자 판단이 필요한 결과를 자동 승인하지 않는다.
7. **Safe Reprocessing:** 필요한 처리 범위만 다시 실행할 수 있고 사용자 결정과 Review 이력을 잃지 않는다.
8. **Regenerable Artifacts:** SRT와 approved edit decisions export를 승인 결과에서 다시 만들 수 있게 한다.
9. **Visible Failure:** 실패, 누락, Validation Failure와 Uncertainty를 정상 결과처럼 숨기지 않는다.
10. **Logical, Not Physical:** 책임의 분리를 설명하되 런타임, 저장소, 통신 또는 배포 방식을 미리 고정하지 않는다.
11. **Responsibility Ownership Is Not Data Ownership:** 컴포넌트는 처리 책임만 가지며 Conceptual Model과 그 identity를 소유하지 않는다.

## 2. High-Level Architecture

~~~text
외부 파일 시스템 / Source Media
                |
                v
          Media Intake
                |
                v
      Processing Coordinator
        |                 |
        |                 +----------------------+
        v                                        v
 Text Processing                         Edit Processing
 Transcript Processor                   Lecture Intelligence Processor
        |                                        |
 Subtitle Processor                         Edit Candidate
        |                                        |
        +------------------+---------------------+
                           |
                           v
                  Review Coordinator
                           |
                 사용자 Accept / Reject / Modify
                           |
                           v
                    Decision Manager
                           |
             Final Subtitle / Approved Edit Decision
                           |
                           v
                   Artifact Generator
                           |
                           v
                   Export Coordinator
                           |
                           v
              외부 NLE / Export Consumer

External AI Provider
        ^
        | 교체 가능한 요청·응답 경계
        v
Transcript / Subtitle / Lecture Intelligence processing

Processing State Manager와 Diagnostic Manager는 전체 흐름의
상태, provenance, Validation Result, Failure, Uncertainty를 연결한다.
~~~

이 그림은 논리적 책임과 데이터 이동을 나타낸다. 컴포넌트의 물리적 배치, 호출 방식, 실행 순서 또는 동시성 모델을 뜻하지 않는다. Text Processing과 Edit Processing은 공통 입력에서 독립적으로 진행될 수 있으나 공통 Review와 사용자 결정에서 다시 연결된다.

## 3. Architectural Layers

이 계층은 기술 스택 계층이 아니라 책임을 구분하기 위한 논리적 관점이다.

### 3.1 External Systems

Source Media와 외부 파일 시스템, External AI Provider, 외부 NLE, export consumer가 위치한다. 이들은 LectureOS 내부 컴포넌트가 아니며 각자의 운영과 데이터 형식을 소유한다.

### 3.2 Application Coordination

사용자의 처리 요청, Review 활동, export 요청을 LectureOS의 처리 흐름으로 연결한다. Processing Coordinator, Review Coordinator, Export Coordinator가 이 책임을 수행한다.

### 3.3 Processing Responsibilities

미디어 준비, Transcript 처리, Subtitle 구성, 강의 구조 분석과 Edit Candidate 생성을 수행한다. 각 책임은 Conceptual Model의 입력을 받아 후보와 Validation Result를 만들며 사용자 결정을 대신하지 않는다.

### 3.4 Domain Policy and Decisions

원본 보존, 시간축 추적, 후보와 결정의 분리, 구조 검증, 사용자 권위, 계보와 승인 결과에 관한 규칙을 적용한다. 이 관점은 하나의 컴포넌트나 저장 위치를 뜻하지 않는다.

### 3.5 Artifact and Export

Final Subtitle과 Approved Edit Decision에서 전달 가능한 Artifact를 만들고 외부 시스템 경계를 넘겨준다. Artifact는 도메인 개념이나 사용자 결정의 대체물이 아니다.

### 3.6 External Integration Boundary

외부 파일 시스템, External AI Provider와 실행 환경의 차이를 내부 논리 책임에서 분리한다. 구체적인 통합 구현은 이 문서에서 선택하지 않는다.

개념은 특정 계층이나 컴포넌트의 독점 소유물이 아니다. 계층은 같은 개념을 서로 다른 책임으로 처리하며 conceptual identity와 provenance를 유지해야 한다.

## 4. Major Components

아래 `Owns`는 개념 데이터의 독점 소유가 아니라 해당 컴포넌트가 맡는 **논리적 처리 책임**을 뜻한다.

### 4.1 Media Intake

- **Responsibility:** Source Media를 받아 처리 가능한 입력으로 준비하고 원본 참조와 Source Timeline 연결을 시작한다.
- **Owns:** 입력 수용, 원본 변경 방지, 처리 전 기본 검증의 책임.
- **Does Not Own:** 외부 파일의 장기 보관 정책, Source Media의 물리적 내용, Transcript 생성, 실제 편집.

### 4.2 Processing Coordinator

- **Responsibility:** Text Pipeline과 Edit Pipeline을 포함한 처리 흐름을 조정한다.
- **Owns:** 처리 책임 사이의 orchestration.
- **Does Not Own:** Source Media, Transcript, Subtitle, Edit Candidate, Review Decision의 conceptual identity 또는 각 Processor의 도메인 규칙.

### 4.3 External AI Provider Boundary

- **Responsibility:** ASR, correction, LLM, 강의 분석 역할의 외부 요청과 반환 결과를 LectureOS 내부 처리 책임에서 분리한다.
- **Owns:** provider 교체 경계와 외부 결과의 출처 보존 책임.
- **Does Not Own:** 도메인 truth, 최종 timestamp, 사용자 결정, provider 내부 운영과 품질 보장.

External AI Provider Boundary는 특정 provider의 응답 구조를 Conceptual Model로 직접 노출하지 않는다. 로컬 또는 원격 실행 여부는 이 논리 경계를 바꾸지 않는다.

### 4.4 Transcript Processor

- **Responsibility:** ASR 결과를 Raw Transcript로 보존하고 교정 후보와 Corrected Transcript를 준비하며 구조적 유효성을 확인한다.
- **Owns:** raw와 corrected 표현의 분리, 교정 계보, 텍스트 구조 검증의 책임.
- **Does Not Own:** Subtitle 표시 규칙, Edit Candidate, 사용자 승인, 최종 timestamp에 대한 LLM 판단.

### 4.5 Subtitle Processor

- **Responsibility:** Corrected Transcript와 Source Timeline 연결을 바탕으로 가독성 있는 Subtitle 후보를 구성하고 시간 구조를 검증한다.
- **Owns:** Transcript와 Subtitle 책임 분리, 자막 구성, 분할과 시간 구조 검증의 책임.
- **Does Not Own:** Raw Transcript, 사용자 Review Decision, SRT 파일을 중심 데이터로 삼는 책임, LLM의 최종 timestamp 생성.

### 4.6 Lecture Intelligence Processor

- **Responsibility:** Source Media와 관련 Transcript 맥락을 분석해 Lecture Segment, 컷편집용 label 후보와 Edit Candidate를 준비한다.
- **Owns:** 강의 구조 분석, 설명 가능한 편집 후보 생성, 원본 Time Range 연결의 책임.
- **Does Not Own:** 교육적 가치의 최종 판단, 사용자 승인, 자동 삭제, 실제 NLE operation 또는 컷 적용.

### 4.7 Review Coordinator

- **Responsibility:** Text, Subtitle, Edit Candidate, Failure, Diagnostic과 Uncertainty를 공통 Review 활동으로 연결하고 관련 Source Media 구간 확인을 지원한다.
- **Owns:** 통합 Review 흐름, 대상과 근거 연결, 검수 우선순위 조정의 책임.
- **Does Not Own:** UI layout 또는 framework, 사용자 대신 내리는 결정, AI 후보의 자동 승인, Review Decision의 지속성.

Review Coordinator는 UI나 독립적인 판단 엔진이 아니다. 최소 Review Interface를 포함한 여러 상호작용 방식이 공통 Review 활동을 수행할 수 있도록 책임을 연결한다.

### 4.8 Decision Manager

- **Responsibility:** 사용자의 Accept, Reject, Modify를 Review Decision으로 반영하고 결정 이력, Modification 계보, 현재 승인 결과를 보존한다.
- **Owns:** 사용자 결정 적용, 결정 이력과 supersession, 승인 결과 연결의 책임.
- **Does Not Own:** Source Media 변경, AI 후보 생성, 실제 컷 적용, 구체적인 상태 저장 방식.

### 4.9 Artifact Generator

- **Responsibility:** Final Subtitle과 Approved Edit Decision에서 재생성 가능한 Artifact를 만든다.
- **Owns:** Artifact 생성 규칙 적용과 생성 근거 연결의 책임.
- **Does Not Own:** 승인 결정, 중심 도메인 데이터, 외부 NLE format의 영구 종속, 실제 편집 결과.

### 4.10 Export Coordinator

- **Responsibility:** 생성된 Artifact를 외부 NLE 또는 export consumer에 전달하는 시스템 경계를 조정한다.
- **Owns:** 외부 전달 경계와 전달 결과 노출의 책임.
- **Does Not Own:** Artifact의 도메인 의미, 외부 시스템의 처리 결과, FCPXML round trip, 외부 편집 완료본 재수입. **v1에서는** transport, download, upload, transfer, URL/signed URL 생성, content distribution, recipient 관리, presentation filename 정책, delivery identity, delivery 지속성 또는 delivery lifecycle을 소유하지 않는다. 이 경계는 개념적 조정일 뿐 durable Delivery 도메인을 함의하지 않으며, v1에서 LectureOS 소유 Export Pipeline은 Physical Materialization에서 끝난다(`044_EXPORT_PIPELINE.md §17`, §18; `patches/PATCH-0008`).

### 4.11 Processing State Manager

- **Responsibility:** Processing Run과 관련된 진행, 완료, 부분 성공과 재실행 상태를 연결한다.
- **Owns:** 처리 상태와 진행 상황을 연결하는 책임.
- **Does Not Own:** Processing Run의 conceptual identity, 중심 도메인 identity, 사용자 결정, 승인 결과, 구체적인 상태 머신 구현. Processing Run의 개념 책임은 `030_DATA_MODEL.md`를 따른다.

### 4.12 Diagnostic Manager

- **Responsibility:** Failure, Validation Result와 Uncertainty를 Diagnostic으로 설명하고 필요한 Review Item과 연결하는 논리적 진단 책임을 조정한다.
- **Owns:** Diagnostic coordination과 처리 영향 노출의 책임.
- **Does Not Own:** 실패의 자동 은폐, 사용자 결정, provider 품질 보장, 오류를 정상 결과로 변환하는 책임.

Diagnostic Manager는 독립 배포 단위를 뜻하지 않으며 여러 처리 책임에 걸친 Diagnostic responsibility를 나타낸다.

## 5. Processing Pipeline

Pipeline은 논리적 의존 관계를 설명한다. 모든 단계를 하나의 순차 실행으로 강제하지 않으며 물리적 병렬 처리 방식도 정하지 않는다.

### 5.1 Shared Intake and Coordination

~~~text
Source Media + Project Context
→ Media Intake
→ Source Media 참조와 Source Timeline 연결
→ Processing Coordinator
→ 필요한 Text / Edit 처리 책임 조정
~~~

두 파이프라인은 Source Media, Processing Run, provenance와 Diagnostic 책임을 공유할 수 있지만 서로의 부가기능이 아니다.

### 5.2 Text Pipeline

~~~text
Source Media
→ External AI Provider Boundary: ASR 역할
→ Transcript Processor: Raw Transcript 보존과 Correction
→ Subtitle Processor: Subtitle 구성과 구조 검증
→ Review Coordinator
→ Decision Manager
→ Final Subtitle
~~~

Raw Transcript, Corrected Transcript, Subtitle은 서로 다른 책임으로 유지한다. LLM은 교정이나 분할 후보를 제안할 수 있지만 최종 timestamp를 직접 통제하지 않는다.

### 5.3 Edit Pipeline

~~~text
Source Media + Source Timeline + 선택적 Transcript 맥락
→ External AI Provider Boundary: Lecture Analysis 역할
→ Lecture Intelligence Processor
→ Lecture Segment와 Edit Candidate
→ Review Coordinator
→ Decision Manager
→ Approved Edit Decision
~~~

Edit Candidate는 추천과 근거를 제공하며 실제 편집 명령이 아니다. 교육적 가치가 불명확하면 사용자 Review를 거치며 자동 삭제로 이어지지 않는다.

### 5.4 Common Review and Decisions

~~~text
Transcript / Subtitle / Edit Candidate / Failure / Diagnostic / Uncertainty
→ Review Item과 Source Media 근거 연결
→ 사용자 Accept / Reject / Modify
→ Review Decision과 Modification 계보 보존
→ Final Subtitle / Approved Edit Decision
~~~

Text와 Edit 결과는 같은 Review 활동에서 다룰 수 있다. Review 순서와 우선순위는 위험도와 사용자 필요에 따라 조정할 수 있으며, 이 문서는 화면 구성이나 상호작용 기술을 정하지 않는다.

### 5.5 Artifact Generation and Export

~~~text
Final Subtitle / Approved Edit Decision
→ Artifact Generator
→ SRT / approved edit decisions export / 선택적 Review·Diagnostic 표현
→ Export Coordinator
→ 외부 NLE 또는 export consumer
~~~

외부 편집 과정은 LectureOS 밖에 있다. Artifact 생성은 자동 컷 적용이나 FCPXML round trip을 의미하지 않는다.

### 5.6 Execution Independence

Text와 Edit 처리의 준비 가능 시점은 서로 다를 수 있다. Processing Coordinator는 두 흐름을 독립적으로 조정할 수 있어야 하며, 한 흐름의 부분 실패가 근거 없이 다른 흐름의 유효 결과를 모두 실패로 만들지 않아야 한다.

이는 구체적인 병렬·동시 실행 방식을 선택한다는 뜻이 아니다. 실행 전략은 후속 설계 책임이다.

## 6. Reprocessing Model

재처리는 새 후보와 파생 결과를 만들 수 있지만 Source Media, 사용자 결정과 승인 결과를 암묵적으로 초기화하지 않는다.

### 6.1 Reprocessing Rules

- 재처리 범위는 변경된 입력, provider, 규칙 또는 설정의 영향을 구분할 수 있어야 한다.
- 영향받지 않은 처리 결과는 재사용할 수 있어야 한다.
- 새 Processing Run과 결과는 이전 결과까지의 provenance를 유지해야 한다.
- 기존 Review Decision과 Modification 이력은 새 후보와 분리해 보존해야 한다.
- 기존 결정이 새 결과에 그대로 적용 가능한지 확실하지 않으면 자동 적용하지 않고 충돌 또는 Review Item으로 노출해야 한다.
- Artifact는 현재 승인 결과에서 다시 생성해야 하며 오래된 Artifact가 중심 상태를 결정해서는 안 된다.

### 6.2 Reprocessing Scenarios

| Change | Reprocessing Boundary | Preserved Authority |
| --- | --- | --- |
| ASR provider 교체 | Raw Transcript와 그 downstream 후보를 다시 평가한다. | Source Media, 기존 사용자 결정과 Review 이력은 보존한다. |
| LLM 또는 correction provider 교체 | 영향받는 교정·분할·분류 후보를 다시 만든다. | 승인된 사용자 Modification과 결정은 자동으로 덮어쓰지 않는다. |
| Correction rule 변경 | Corrected Transcript 관련 결과와 downstream Subtitle 영향을 다시 평가한다. | Raw Transcript, Source Timeline, 관련 사용자 결정의 계보를 유지한다. |
| Subtitle rule 변경 | Subtitle 후보와 관련 Review Item, Artifact를 다시 만든다. | Transcript 계층과 기존 Subtitle 사용자 결정을 보존하고 충돌을 드러낸다. |
| Lecture analysis 변경 | Lecture Segment와 Edit Candidate를 다시 평가한다. | Approved Edit Decision은 새 후보와 구분해 보존한다. |
| Review 이후 재실행 | 새 후보와 기존 결정을 비교한다. | Accept, Reject, Modify와 Modification 이력을 임의로 초기화하지 않는다. |
| Artifact format 변경 | Artifact 생성만 다시 수행한다. | Final Subtitle과 Approved Edit Decision은 변경하지 않는다. |

표는 영향 경계의 원칙을 설명하며 고정된 단계 그래프나 cache 무효화 알고리즘을 정의하지 않는다.

## 7. Failure Model

Failure는 정상 결과와 구분되고 Processing Status, Diagnostic, Review 필요성에 반영되어야 한다. 실패를 빈 결과나 성공으로 변환하지 않는다.

### 7.1 Failure Categories

| Failure Category | Architectural Meaning | Required Response |
| --- | --- | --- |
| Partial Failure | 일부 책임은 결과를 만들었지만 다른 책임은 완료되지 않았다. | 유효한 결과와 실패 범위를 구분하고 영향받는 downstream 사용을 제한한다. |
| Recoverable Failure | 같은 처리 책임을 다시 수행하면 회복할 수 있는 실패다. | 완료된 결과와 사용자 결정을 유지하고 안전한 재실행 가능성을 노출한다. |
| Validation Failure | 결과가 시간, 순서, 누락 또는 다른 구조 규칙을 충족하지 못한다. | 정상 결과로 승인하지 않고 Diagnostic 또는 Review Item으로 연결한다. |
| External Provider Failure | External AI Provider가 실패, 불완전 결과 또는 사용할 수 없는 응답을 반환한다. | provider 결과와 내부 도메인 결과를 구분하고 실패 범위와 대안을 노출한다. |
| User Action Required | 자동으로 해소할 근거가 부족하고 사람의 판단이 필요하다. | 관련 Source Media와 근거를 포함한 Review Item을 제공한다. |

### 7.2 Failure Propagation

- 실패는 영향받는 결과와 연결되어야 한다.
- 한 처리 책임의 실패가 독립적으로 유효한 결과를 자동으로 폐기해서는 안 된다.
- downstream 처리가 필요한 선행 결과를 신뢰할 수 없으면 진행을 정상 완료로 표시해서는 안 된다.
- 외부 provider의 실패나 Uncertainty는 내부 사용자 결정과 승인 결과를 손상시키면 안 된다.
- 실패 후 재실행은 기존 provenance와 Processing Run 관계를 잃지 않아야 한다.

### 7.3 Partial Success

부분 성공은 일부 결과가 존재한다는 이유만으로 전체 성공이 되는 상태가 아니다. 각 결과가 어떤 입력과 검증 상태에 기반하는지 드러내고, 사용할 수 없는 결과와 Review가 필요한 결과를 구분해야 한다.

부분 성공의 구체적인 상태 전이와 사용자에게 허용할 동작은 후속 Pipeline 문서에서 정한다.

## 8. AI Boundary

External AI Provider는 LectureOS 밖에 있는 기술 의존성이다. 내부 Architecture는 provider의 출력과 Conceptual Model 사이에 명시적인 검증 경계를 둔다.

### Boundary Rules

- ASR, correction, LLM, Lecture Analysis 역할은 교체 가능해야 한다.
- provider 고유 결과와 ID는 provenance로 보존할 수 있지만 내부 conceptual identity가 될 수 없다.
- provider 출력은 Raw Transcript, 교정 후보, Subtitle 후보, Lecture Segment 후보 또는 Edit Candidate를 준비하는 입력이다.
- provider 결과가 바로 Corrected Transcript, Final Subtitle, Review Decision 또는 Approved Edit Decision이 되어서는 안 된다.
- 구조적 Validation Result가 실패한 결과를 정상 후보나 승인 결과로 통과시키지 않는다.
- LLM은 의미 경계나 변경 후보를 제안할 수 있지만 최종 timestamp를 직접 생성하거나 변경하지 않는다.
- provider를 교체해도 Source Timeline 연결, 사용자 결정, Review 이력과 승인 결과가 유지되어야 한다.
- 원격 provider 사용 시 데이터가 시스템 신뢰 경계를 넘는 사실을 숨기지 않아야 한다.

provider 역할을 하나의 제품이나 하나의 호출 방식으로 묶을지는 이 문서에서 결정하지 않는다.

## 9. Review Architecture

Review Architecture는 사용자가 Text, Subtitle, Edit Candidate와 처리 문제를 함께 검수하고 결정할 수 있게 하는 논리 책임의 협력이다.

### Review Subjects

- Transcript 교정 후보와 의미 위험
- Subtitle 분할, 줄바꿈, 타이밍과 구조 문제
- Lecture Segment label과 Edit Candidate
- Failure, 누락, Validation Result, Diagnostic과 Uncertainty

### Review Responsibilities

- Review Item과 원래 대상, Source Media 또는 Time Range를 연결한다.
- 위험도와 우선순위에 따라 검수 대상을 준비할 수 있게 한다.
- 관련 원본 오디오 또는 영상 구간을 확인할 수 있게 한다.
- Accept, Reject, Modify를 Review Decision으로 전달한다.
- Modification과 이전 결정의 계보를 보존한다.
- 여러 Review iteration에서 이전 결정을 잃지 않는다.
- 재처리로 새 후보가 생기면 기존 결정과의 관계 또는 충돌을 드러낸다.

Review Architecture는 특정 UI, Review Engine 또는 자동 판단 시스템이 아니다. Review Coordinator는 활동을 연결하고 Decision Manager는 사용자의 판단을 반영한다. AI가 Review Item을 생성할 수는 있지만 사용자 결정을 대신하지 않는다.

## 10. Artifact Architecture

Artifact Generator는 승인 결과를 외부 전달 표현으로 변환하고 Export Coordinator는 외부 시스템 경계를 조정한다.

### Artifact Rules

- SRT Artifact는 Final Subtitle에서 생성한다.
- approved edit decisions export는 Approved Edit Decision의 Source Time Range, label, 결정 상태를 잃지 않아야 한다.
- Artifact는 생성 근거와 승인 결과까지 추적 가능해야 한다.
- Artifact 손실이 Source Media, Review Decision 또는 승인 결과의 손실을 의미해서는 안 된다.
- 출력 규칙이나 형식이 바뀌면 승인 결과를 변경하지 않고 Artifact만 다시 만들 수 있어야 한다.
- 외부 export schema와 NLE별 형식은 이 문서에서 정하지 않는다.
- FCPXML과 자동 컷 적용은 V1 Artifact Architecture에 포함하지 않는다.
- 외부 편집 완료본의 round trip은 V1에서 다루지 않는다.

## 11. Cross-Cutting Constraints

### 11.1 Identity and Provenance

모든 Processor와 Coordinator는 결과가 어떤 Source Media, Source Timeline, Processing Run, AI 결과와 사용자 결정에서 왔는지 설명할 수 있게 해야 한다. 컴포넌트 교체가 conceptual identity를 무효화해서는 안 된다.

### 11.2 Validation

시간, 순서, 누락과 구조적 유효성은 AI의 자연어 판단과 분리해 검증한다. Validation Failure는 정상 결과로 숨기지 않고 Diagnostic 또는 Review Item으로 연결한다.

### 11.3 Decision Preservation

사용자 결정과 Modification 이력은 처리 결과보다 오래 지속될 수 있다. 재처리, provider 교체 또는 Artifact 재생성이 이를 삭제하거나 덮어쓰지 않아야 한다.

### 11.4 Provider and NLE Independence

내부 책임과 개념은 특정 AI provider 또는 NLE의 고유 구조를 중심으로 설계하지 않는다. Final Cut은 외부 현재 사용자 환경이며 LectureOS 내부 구성요소가 아니다.

### 11.5 Local-First Without Local-Only

local-first는 현재 Working Assumption이다. 논리 아키텍처는 로컬 처리를 지원해야 하지만 모든 책임을 영구적으로 한 실행 환경에 고정하거나 원격 처리를 필수로 가정하지 않는다.

## 12. Assumptions and Open Questions

### Confirmed

- Text Pipeline과 Edit Pipeline은 동등한 핵심 흐름이다.
- Source Media와 Source Timeline은 변경하지 않는다.
- External AI Provider는 교체 가능한 외부 의존성이다.
- AI 결과는 후보이며 사용자 결정이 아니다.
- Review는 Text, Subtitle, Edit Candidate, Failure와 Uncertainty를 함께 다룬다.
- Accept, Reject, Modify와 관련 Source Media 확인을 지원해야 한다.
- 사용자 결정과 Approved Edit Decision은 재처리 후에도 보존되어야 한다.
- Artifact는 승인 결과에서 생성되며 도메인 데이터를 대체하지 않는다.
- 자동 컷 적용, FCPXML과 외부 편집 round trip은 V1 Deferred다.

### Working Assumption

- 현재 논리 컴포넌트 분리는 책임을 설명하기 위한 기준이며 물리적 배포 단위를 의미하지 않는다.
- Text와 Edit 처리는 명시된 입력 의존성 안에서 독립적으로 조정될 수 있다.
- local-first를 전략적 기본값으로 지원하되 local-only Architecture로 제한하지 않는다.

### Requires Validation

- Pipeline stage의 최소 재실행 경계는 어디인가?
- 변경 영향 범위를 어떤 규칙으로 판단할 것인가?
- 기존 Review Decision을 재처리 결과에 자동으로 재적용할 수 있는 안전 조건은 무엇인가?
- 부분 성공 상태에서 어떤 downstream 처리를 허용할 것인가?
- Review Item의 위험도와 우선순위를 어느 책임에서 계산하고 조정할 것인가?
- 여러 Review iteration의 현재 유효 결정을 어떻게 판별할 것인가?
- Review에서 Source Media 구간에 접근하는 논리 경계는 무엇인가?
- 원격 External AI Provider에 전달할 수 있는 데이터 범위는 무엇인가?

### Deferred

- 물리적 component 배치와 deployment topology
- process, thread와 concurrency model
- 저장 기술, cache 구현과 무효화 알고리즘
- 컴포넌트 간 protocol과 API schema
- 외부 export schema와 NLE별 통합 방식
- FCPXML 생성과 round trip
- 외부 편집 완료본 재수입

## 13. Downstream Constraints

### Constraints for `040~044` Pipeline Documents

- 각 Pipeline은 이 문서의 컴포넌트 책임과 `030_DATA_MODEL.md`의 개념 책임을 구분해야 한다.
- Text Pipeline과 Edit Pipeline 중 하나를 다른 하나의 부가기능으로 축소하지 않아야 한다.
- 각 단계는 입력, 출력, provenance, Validation Result와 실패 영향을 설명해야 한다.
- Raw Transcript, Corrected Transcript, Subtitle의 책임을 혼합하지 않아야 한다.
- Edit Candidate, Review Decision, Approved Edit Decision, 실제 편집 적용을 구분해야 한다.
- Review는 Text, Subtitle, Edit, Failure, Diagnostic을 함께 처리할 수 있어야 한다.
- Accept, Reject, Modify와 Modification 이력을 보존해야 한다.
- 단계 재실행이 사용자 결정과 승인 결과를 손상시키지 않아야 한다.
- External AI Provider 고유 구조가 Pipeline의 중심 개념이 되어서는 안 된다.
- LLM이 최종 timestamp를 직접 통제하게 해서는 안 된다.
- Failure와 Uncertainty를 정상 결과처럼 숨기지 않아야 한다.
- Artifact 생성과 도메인 결과 생성을 같은 책임으로 합치지 않아야 한다.
- 자동 컷 적용, FCPXML 또는 외부 편집 round trip을 V1 흐름으로 추가하지 않아야 한다.

## Related Documents

- `000_MANIFESTO.md`
- `001_PRODUCT.md`
- `002_FAQ.md`
- `003_VISION.md`
- `004_PRINCIPLES.md`
- `020_PRODUCT_REQUIREMENTS.md`
- `021_SYSTEM_CONTEXT.md`
- `030_DATA_MODEL.md`
- `../patches/PATCH-0001-l0-and-prd-stabilization.md`

## Change Log

### Blueprint 0.1 — 2026-07-14

- Conceptual Model을 처리하는 논리 책임과 시스템 경계를 정의했다.
- Text Pipeline과 Edit Pipeline, 공통 Review, Decision, Artifact 흐름을 연결했다.
- 교체 가능한 External AI Provider 경계와 원본·사용자 결정 보존 규칙을 반영했다.
- 부분 재처리, 실패 노출과 downstream Pipeline 제약을 정의했다.
