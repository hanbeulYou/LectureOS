# 050_PLUGIN_SYSTEM

- Status: Draft
- Version: Blueprint 0.1
- Last Updated: 2026-07-15
- Depends On: `000_MANIFESTO.md`, `001_PRODUCT.md`, `002_FAQ.md`, `003_VISION.md`, `004_PRINCIPLES.md`, `020_PRODUCT_REQUIREMENTS.md`, `021_SYSTEM_CONTEXT.md`, `030_DATA_MODEL.md`, `031_ARCHITECTURE.md`, `040_TRANSCRIPT_PIPELINE.md`, `041_SUBTITLE_PIPELINE.md`, `042_LECTURE_INTELLIGENCE_PIPELINE.md`, `043_REVIEW_PIPELINE.md`, `044_EXPORT_PIPELINE.md`
- Referenced By:

## Purpose

이 문서는 LectureOS가 외부 AI, STT, Subtitle 처리, Export, NLE 연계와 기타 확장 기능을 Plugin으로 다루기 위한 개념적 계약을 정의한다.

Plugin System은 특정 provider나 도구의 구조를 LectureOS의 중심 개념으로 만들지 않으면서, 필요한 Capability를 교체하거나 확장할 수 있게 하는 Provider Independence의 Blueprint 표현이다.

이 문서는 Plugin의 의미, Capability 계약, identity, lifecycle, configuration, context, validation, failure, compatibility와 provenance를 정의한다. Plugin Architecture, Runtime, 배포, 로딩, package 또는 integration interface는 정의하지 않는다.

## 1. Conceptual Scope

### 1.1 포함 범위

- Plugin
- Plugin Capability
- Capability Contract
- Plugin Identity
- Plugin Lifecycle
- Plugin Configuration
- Plugin Context
- Plugin Validation
- Plugin Failure
- Plugin Compatibility
- Plugin Provenance
- Capability Negotiation
- Plugin과 LectureOS Concept 및 Pipeline 사이의 책임 경계

### 1.2 제외 범위

- Plugin의 발견, 설치, 로딩과 실행 방법
- 배포 단위와 package 관리
- 통신 interface와 호출 방식
- manifest의 구조와 serialization
- registry의 구현
- Plugin 간 의존성 해석
- 보안 격리와 실행 환경 설계
- provider별 adapter 구현

Plugin Concept는 이러한 구현 문제를 나중에 일관되게 결정하기 위한 상위 계약이며 그 구현 자체가 아니다.

## 2. Principles

### 2.1 Provider Independence

LectureOS의 제품 의미, Domain Concept와 Pipeline 책임은 특정 provider나 Plugin에 종속되지 않는다. Plugin을 교체해도 Source Timeline, provenance, Human Decision과 승인 결과의 의미가 유지되어야 한다.

### 2.2 Capability Is Not Provider

Capability는 LectureOS가 필요로 하는 역할이고 provider는 그 역할을 제공할 수 있는 외부 주체다. 하나의 Capability를 여러 Plugin이 제공할 수 있으며, 하나의 Plugin이 여러 Capability를 제공할 수 있다.

Provider의 브랜드, 모델 또는 고유 분류는 Capability의 정의가 아니다.

### 2.3 Plugin Is Not Pipeline

Pipeline은 LectureOS 결과가 발전하는 책임과 계약을 정의한다. Plugin은 Pipeline이 필요로 하는 일부 Capability를 제공할 수 있지만 Pipeline 전체의 책임, provenance, validation 또는 Human Authority를 소유하지 않는다.

### 2.4 Plugin Is Not Product Feature

Plugin이 존재한다는 사실만으로 새로운 제품 기능이나 범위가 승인되지 않는다. 제품 기능은 Product Requirements가 정의하며 Plugin은 승인된 기능을 수행할 수 있는 선택적 제공 수단이다.

### 2.5 Plugin Is Not Runtime Module

Plugin은 Blueprint의 개념적 확장 단위다. 하나의 process, library, service, executable 또는 배포 단위와 동일하다고 가정하지 않는다.

### 2.6 Human Authority

Plugin은 인식, 분석, 변환, 후보 생성 또는 표현을 지원할 수 있지만 Human Decision을 만들거나 사용자 승인을 대신하지 않는다. 높은 confidence나 compatibility가 자동 승인 권한을 부여하지 않는다.

### 2.7 Concept Before Component

Source Media, Transcript, Subtitle, Analysis Finding, Edit Candidate, Review Decision, Approved Edit Decision과 Artifact의 의미가 Plugin보다 먼저 존재한다. Plugin 출력은 LectureOS Concept로 해석되고 검증되기 전까지 중심 Domain 결과가 아니다.

## 3. Core Concepts

### 3.1 Plugin

Plugin은 하나 이상의 Plugin Capability를 LectureOS에 제공할 수 있는 개념적 확장 단위다.

Plugin은 다음을 보장해야 한다.

- 자신이 제공한다고 주장하는 Capability를 식별할 수 있다.
- Capability Contract가 요구하는 의미와 경계를 존중한다.
- 자신의 identity, configuration, provenance와 failure를 LectureOS Concept와 구분한다.
- provider 고유 결과를 LectureOS의 canonical truth로 승격하지 않는다.
- Pipeline이나 Human Review의 권위를 흡수하지 않는다.

Plugin의 물리적 형태, 실행 위치와 공급 방식은 이 정의에 포함되지 않는다.

### 3.2 Plugin Capability

Plugin Capability는 Plugin이 제공할 수 있다고 선언하는 하나의 의미 있는 역할이다.

현재 Blueprint에서 Capability가 기여할 수 있는 영역의 예는 다음과 같다.

- 음성 인식과 source-aligned timing 제공
- Transcript correction 후보 생성
- Subtitle 후보 또는 표현 변환 지원
- Lecture Analysis와 Edit Candidate 준비
- Export Representation 생성
- 외부 NLE 또는 export consumer를 위한 표현 지원

이 목록은 예시이며 영구적이거나 완전한 capability taxonomy가 아니다. Capability의 존재는 해당 제품 기능의 승인이나 V1 포함을 뜻하지 않는다.

### 3.3 Capability Contract

Capability Contract는 특정 Capability가 LectureOS 안에서 의미 있게 사용되기 위해 지켜야 하는 개념적 약속이다.

Contract는 최소한 다음을 설명할 수 있어야 한다.

- Capability의 목적과 책임 경계
- 사용할 수 있는 LectureOS Concept와 필요한 전제
- 만들어낼 수 있는 결과의 의미
- Source Timeline과 provenance 유지 의무
- validation과 uncertainty의 기대
- failure를 숨기지 않는 의무
- Human Authority와 downstream 책임의 경계

Capability Contract는 호출 interface나 payload 구조가 아니다. 특정 provider의 응답 형식을 LectureOS 계약으로 복제하지 않는다.

### 3.4 Plugin Identity

Plugin Identity는 LectureOS가 Plugin과 그 결과의 출처를 안정적으로 구분하기 위한 개념이다.

Plugin Identity는 다음과 구분된다.

- provider의 계정 또는 외부 식별자
- 특정 모델의 identity
- Plugin이 만든 Domain 결과의 identity
- 설치된 실행물이나 package의 위치

Plugin Identity는 provenance와 compatibility 판단을 지원하지만 LectureOS Domain Concept의 identity를 독점하지 않는다. 구체적인 식별 형식은 정의하지 않는다.

### 3.5 Plugin Lifecycle

Plugin Lifecycle은 Plugin이 LectureOS에서 Capability 제공 대상으로 고려되고, 검증되고, 사용 가능성이 달라지며, 더 이상 선택되지 않을 수 있는 개념적 변화다.

Lifecycle은 다음 사실을 설명할 수 있어야 한다.

- Plugin이 어떤 Capability를 제공한다고 알려졌는가?
- 현재 Context와 Contract에 대해 사용 가능한가?
- validation 또는 compatibility 상태가 바뀌었는가?
- 더 이상 현재 사용 대상으로 선택되지 않는가?
- 과거 결과의 provenance를 위해 identity를 계속 설명할 수 있는가?

Plugin을 더 이상 사용하지 않더라도 그 Plugin이 만든 과거 결과와 사용자 결정의 provenance를 삭제해서는 안 된다. 이 문서는 lifecycle 상태 목록이나 전이 방식을 정의하지 않는다.

### 3.6 Plugin Configuration

Plugin Configuration은 특정 Plugin Capability를 사용할 때 적용한 선택과 조건의 개념적 문맥이다.

Configuration은 다음 원칙을 따른다.

- Capability Contract의 의미를 임의로 변경하지 않는다.
- Human Authority나 Pipeline validation을 비활성화하는 승인 수단이 아니다.
- 결과 provenance와 재처리 관계를 설명할 수 있어야 한다.
- 비밀 정보, 저장 위치 또는 표현 형식을 이 Blueprint에서 확정하지 않는다.

동일한 Plugin이 다른 Configuration에서 다른 결과를 만들 수 있으므로, 결과는 적용된 Configuration과의 관계를 설명할 수 있어야 한다.

### 3.7 Plugin Context

Plugin Context는 Capability 수행에 허용되고 필요한 LectureOS 문맥이다.

적용 가능한 Context는 다음을 포함할 수 있다.

- Source Media identity와 허용된 media access
- Source Timeline과 Time Range
- Raw Transcript, Corrected Transcript 또는 Subtitle의 관련 표현
- Lecture Segment, Analysis Finding 또는 Edit Candidate의 관련 근거
- Project 또는 Lecture Context
- 승인된 사용자 결정과 export 목적
- 처리 제약, 불확실성 또는 validation 요구

모든 Plugin이 모든 Context에 접근할 수 있다고 가정하지 않는다. Plugin Context는 필요한 범위와 허용된 데이터 이동을 설명해야 하며, 누락된 Context가 결과에 미치는 영향을 숨기지 않아야 한다.

### 3.8 Plugin Validation

Plugin Validation은 Plugin과 그 Capability 제공 주장이 LectureOS 계약 안에서 사용 가능한지 개념적으로 확인하는 책임이다.

Validation은 다음을 구분한다.

- Plugin Identity와 provenance를 설명할 수 있는가?
- 제공 Capability가 Capability Contract와 일치하는가?
- 현재 Plugin Context와 Configuration에서 사용할 수 있는가?
- 결과가 필수 traceability와 구조적 요구를 유지하는가?
- failure와 uncertainty를 정상 결과처럼 숨기지 않는가?

Plugin Validation은 provider 출력의 의미적 정확성, 교육적 가치 또는 사용자 승인을 보장하지 않는다.

### 3.9 Plugin Failure

Plugin Failure는 Plugin이 선언한 Capability를 현재 Contract와 Context에 따라 신뢰할 수 있게 제공하지 못한 상태다.

Failure는 다음과 구분되어야 한다.

- Capability가 제공되지 않음
- 현재 Context와 호환되지 않음
- 필요한 입력이나 권한이 부족함
- 결과가 validation 또는 traceability 요구를 충족하지 못함
- provider 또는 외부 시스템이 사용할 수 없는 결과를 반환함

Plugin Failure는 빈 정상 결과나 성공으로 표현하지 않는다. 하나의 Plugin Failure가 Source Media, Human Decision 또는 독립적으로 유효한 다른 결과를 손상시키면 안 된다.

### 3.10 Plugin Compatibility

Plugin Compatibility는 Plugin이 선언한 Capability를 특정 Capability Contract, Plugin Context와 LectureOS의 현재 요구 안에서 제공할 수 있는지를 나타낸다.

Compatibility는 다음과 동일하지 않다.

- 결과 품질의 보장
- Human Approval
- 모든 Pipeline에서의 사용 가능성
- 미래 Blueprint와의 영구 호환
- 특정 실행 환경에서의 설치 성공

Compatibility는 Plugin 전체에 대한 단일 영구 속성이라기보다 Capability와 Context에 따라 달라질 수 있는 관계다.

### 3.11 Plugin Provenance

Plugin Provenance는 결과가 어떤 Plugin Identity, Plugin Capability, Capability Contract, Configuration과 Context를 통해 생성되었는지 설명한다.

Plugin Provenance는 LectureOS의 기존 provenance를 대체하지 않는다. Plugin 결과에서 Source Media, Source Timeline, upstream Concept, Review Decision과 Artifact까지 이어지는 계보의 한 부분을 제공한다.

Plugin을 교체하거나 더 이상 사용하지 않아도 과거 결과의 Plugin Provenance는 유지되어야 한다.

### 3.12 Capability Negotiation

Capability Negotiation은 현재 목적과 Context에 필요한 Capability Contract를 만족할 수 있는 Plugin 선택지를 식별하고, 사용 가능 범위를 결정하는 개념적 활동이다.

Negotiation은 다음을 고려할 수 있다.

- 필요한 Capability와 책임 경계
- Plugin이 선언한 Capability
- Plugin Compatibility와 Validation 결과
- 현재 Plugin Context와 Configuration
- 허용된 데이터 이동과 신뢰 경계
- 알려진 uncertainty, limitation과 failure 상태

Capability Negotiation은 자동 실행, provider 구매, Plugin 설치 또는 최종 사용자 승인을 의미하지 않는다. 선택 방식과 우선순위 정책은 이 문서에서 정의하지 않는다.

## 4. Conceptual Relationships

```text
LectureOS Product Requirement
              |
              v
      Required Capability
              |
              v
      Capability Contract
              |
              v
   Capability Negotiation
              |
              v
Plugin Identity + Plugin Capability
              |
              v
Configuration + Plugin Context
              |
              v
       Plugin Validation
              |
              v
Provider-specific Result
              |
              v
LectureOS Concept Boundary
```

이 그림은 제품 요구가 Capability Contract를 통해 Plugin 제공 역할과 연결되는 개념적 관계를 보여준다. 실행 순서나 Plugin Architecture를 나타내지 않는다.

Provider-specific Result는 LectureOS Concept Boundary에서 provenance, validation과 uncertainty를 유지한 채 해당 Pipeline의 Concept로 해석되어야 한다. Plugin 자체가 Pipeline 결과의 승인이나 identity를 소유하지 않는다.

## 5. Capability Contract

### 5.1 Contract Responsibility

Capability Contract는 Plugin 구현의 세부 동작보다 LectureOS가 기대하는 의미와 보장 사항을 우선한다.

각 Contract는 다음 질문에 답할 수 있어야 한다.

- LectureOS가 필요로 하는 역할은 무엇인가?
- 이 역할은 어느 Pipeline 책임에 기여하는가?
- 어떤 upstream Concept를 사용할 수 있는가?
- 어떤 결과를 제안하거나 표현할 수 있는가?
- 어떤 traceability, provenance와 validation을 유지해야 하는가?
- 어떤 failure와 uncertainty를 드러내야 하는가?
- 결과를 누가 검토하거나 승인하는가?

### 5.2 Contract Boundaries

Capability Contract는 다음 권위를 Plugin에 위임하지 않는다.

- Product Requirement 변경
- Pipeline 책임 재정의
- Domain Concept의 canonical identity 결정
- Human Review Decision 생성
- Source Media 변경
- validation을 우회한 승인
- 외부 Artifact를 내부 Source로 승격

### 5.3 Contract Evolution

Capability Contract가 변경되면 기존 Plugin의 compatibility와 기존 결과의 현재 사용 가능성을 다시 판단해야 할 수 있다.

Contract 변경은 과거 Plugin Provenance, Human Decision 또는 승인 결과를 소급해 삭제하지 않는다. 새 Contract에서 기존 결과를 안전하게 사용할 수 없는 경우 그 차이와 재검토 필요성을 드러내야 한다.

Contract version 표현과 compatibility 판별 방법은 이 문서에서 정의하지 않는다.

## 6. Capability Areas

다음 영역은 현재 Blueprint에서 Plugin Capability가 기여할 수 있는 개념적 예다. 고정된 Plugin 종류나 필수 구현 목록이 아니다.

### 6.1 Speech and Transcript Capabilities

- source-aligned speech recognition 결과 준비
- confidence와 uncertainty 제공
- Transcript correction 후보 준비

이 Capability는 Raw Transcript, Corrected Transcript와 Human Decision의 책임을 대체하지 않는다.

### 6.2 Subtitle Capabilities

- Subtitle 후보 또는 reading representation 준비
- time representation을 위한 근거 제공

이 Capability는 Final Subtitle을 자동 승인하거나 Source Timeline을 임의로 변경하지 않는다.

### 6.3 Lecture Intelligence Capabilities

- lecture understanding 지원
- Lecture Segment 또는 Analysis Finding 후보 준비
- explainable Edit Candidate 준비

이 Capability는 실제 편집, Edit Decision 또는 교육적 가치의 최종 판단을 수행하지 않는다.

### 6.4 Export and NLE Capabilities

- Final Subtitle의 외부 표현 지원
- Approved Edit Decision의 외부 표현 지원
- 특정 외부 consumer가 사용할 수 있는 표현 준비

이 Capability는 Artifact를 Human Decision으로 만들거나 외부 NLE의 실제 편집과 Rendering을 LectureOS 책임으로 가져오지 않는다.

### 6.5 Future Capability Areas

새 Capability 영역은 기존 Plugin System만으로 자동 승인되지 않는다. Product Requirements와 System Boundary가 먼저 해당 기능을 승인하고 책임을 정의해야 한다.

## 7. Plugin Context and Trust Boundary

Plugin은 LectureOS 내부 Concept와 외부 provider 사이의 신뢰 경계를 넘을 수 있다.

다음 원칙을 유지한다.

- Plugin에 전달되는 데이터 범위는 Capability 수행에 필요한 Context로 제한되어야 한다.
- Source Media, 음성, Transcript 또는 개인정보가 외부 경계를 넘는지 숨기지 않는다.
- 외부 결과는 검증되지 않은 결과로 LectureOS에 돌아온다.
- Plugin Configuration은 데이터 사용 동의나 정책을 암묵적으로 대신하지 않는다.
- Human Decision과 승인 결과는 Plugin이 임의로 변경할 수 없다.
- Plugin Failure나 외부 provider 변경이 원본과 사용자 결정을 손상시키면 안 된다.

구체적인 보안 정책, 개인정보 처리 기준, 실행 격리와 권한 방식은 후속 책임이다.

## 8. Plugin Validation and Compatibility

Plugin은 Capability Negotiation에서 선택 가능한 대상으로 사용되기 전에 현재 Contract와 Context에 대한 compatibility를 설명할 수 있어야 한다.

개념적 검토 범위는 다음과 같다.

- 선언한 Capability와 Contract의 의미가 일치하는가?
- 필요한 Context가 제공되며 허용된 범위를 넘지 않는가?
- 결과의 provenance와 Source Timeline traceability를 유지할 수 있는가?
- expected failure와 uncertainty를 표현할 수 있는가?
- Pipeline과 Human Authority의 경계를 존중하는가?
- Plugin 교체 후에도 LectureOS Concept의 identity가 유지되는가?

Validation과 compatibility는 결과의 정확도나 품질을 영구 보장하지 않는다. 실제 결과는 각 Pipeline의 validation과 필요한 Human Review를 계속 따라야 한다.

## 9. Lifecycle and Change

### 9.1 Availability Change

Plugin은 현재 Context에서 사용할 수 있게 되거나 더 이상 사용할 수 없게 될 수 있다. availability 변화는 기존 결과의 provenance를 삭제하지 않는다.

### 9.2 Capability Change

Plugin이 제공하는 Capability 또는 그 의미가 달라지면 compatibility를 다시 판단해야 한다. 새로운 Capability 선언만으로 Product Scope가 확대되지 않는다.

### 9.3 Configuration Change

Plugin Configuration 변경은 새 결과나 다른 uncertainty를 만들 수 있다. 이전 결과를 같은 문맥에서 생성된 것으로 표시하지 않으며 필요한 Pipeline 재처리 관계를 설명해야 한다.

### 9.4 Replacement

다른 Plugin이 같은 Capability Contract를 제공할 수 있다. 교체는 이전 Plugin 결과를 덮어쓰거나 기존 Human Decision을 새 결과에 자동 적용하는 행위가 아니다.

### 9.5 Retirement

Plugin이 더 이상 선택되지 않아도 그 Plugin을 통해 생성된 결과의 Plugin Identity와 provenance는 설명 가능해야 한다. retirement는 과거 Domain 결과나 Review History의 삭제를 의미하지 않는다.

## 10. Failure and Uncertainty

### 10.1 Capability Unavailable

필요한 Capability를 제공할 수 있는 compatible Plugin이 없거나 현재 Context에서 사용할 수 없는 상태다. 이를 정상 빈 결과로 표현하지 않는다.

### 10.2 Contract Mismatch

Plugin의 Capability 의미 또는 보장 사항이 현재 Capability Contract와 일치하지 않는 상태다. 유사한 provider 기능이 있다는 이유만으로 compatible하다고 간주하지 않는다.

### 10.3 Context Failure

Plugin Context가 부족하거나 허용 범위를 충족하지 못해 Capability를 안전하게 수행할 수 없는 상태다. Plugin이 누락된 정보를 근거 없이 추측하게 하지 않는다.

### 10.4 Validation Failure

Plugin 결과가 provenance, traceability 또는 구조적 요구를 만족하지 못한 상태다. 결과를 정상 Pipeline output이나 승인 결과로 승격하지 않는다.

### 10.5 Provider Failure

외부 provider가 실패하거나 불완전하고 사용할 수 없는 결과를 반환한 상태다. provider failure와 LectureOS Domain 결과를 구분한다.

### 10.6 Failure Propagation

- Plugin Failure는 영향받는 Capability와 결과 범위를 설명할 수 있어야 한다.
- 독립적으로 유효한 Pipeline 결과를 근거 없이 무효화하지 않는다.
- Source Media, Review Decision과 승인 결과를 손상시키지 않는다.
- 대체 Plugin의 존재가 자동 선택이나 자동 재처리를 의미하지 않는다.
- recovery 또는 재처리가 필요한 경우 기존 provenance와 사용자 결정을 유지한다.

## 11. Provenance and Reprocessing

Plugin을 사용한 결과는 최소한 다음 관계를 설명할 수 있어야 한다.

```text
Source or Upstream Concept
             |
             v
      Plugin Context
             |
             v
Plugin Identity + Capability
      + Configuration
             |
             v
 Provider-specific Result
             |
             v
Validation + LectureOS Concept
```

Plugin을 교체하거나 Configuration, Capability Contract 또는 upstream 입력이 바뀌면 재처리가 필요할 수 있다.

재처리는 다음을 보장해야 한다.

- 이전 Plugin 결과와 새 결과의 provenance를 구분한다.
- 기존 Review Decision과 Human Modification을 자동 삭제하거나 변경하지 않는다.
- 새 결과에 기존 결정을 자동 적용할 수 없는 경우 충돌 또는 Review 필요성을 드러낸다.
- Plugin 교체가 Source Timeline 연결과 Domain identity를 끊지 않는다.
- 과거 Plugin을 더 이상 실행할 수 없어도 그 결과가 어디에서 왔는지 설명할 수 있어야 한다.

구체적인 재실행 경계와 결과 reconciliation 방식은 각 Pipeline 및 후속 설계 책임이다.

## 12. Pipeline Boundaries

### 12.1 Transcript Pipeline

Plugin은 ASR 또는 correction Capability를 제공할 수 있다. Transcript Pipeline은 Raw Transcript 보존, Corrected Transcript 계보, validation과 Review 연결 책임을 계속 가진다.

### 12.2 Subtitle Pipeline

Plugin은 Subtitle 후보 또는 representation 관련 Capability를 제공할 수 있다. Subtitle Pipeline은 Subtitle Unit, reading and time representation, Final Subtitle과 사용자 Modification의 책임을 계속 가진다.

### 12.3 Lecture Intelligence Pipeline

Plugin은 lecture analysis Capability를 제공할 수 있다. Lecture Intelligence Pipeline은 Analysis Finding, Lecture Segment, Edit Candidate, explainability와 Source Timeline traceability의 책임을 계속 가진다.

### 12.4 Review Pipeline

Plugin은 Review Context 준비를 지원할 수 있지만 Human Decision을 생성할 수 없다. Review Pipeline만 Accept, Reject, Modify와 Approved Edit Decision의 관계를 정의한다.

### 12.5 Export Pipeline

Plugin은 Export Representation 또는 외부 consumer 관련 Capability를 제공할 수 있다. Export Pipeline은 Export Input, Configuration, Profile, Scope, Artifact Provenance, validation과 reproducibility의 책임을 계속 가진다.

## 13. Invariants

- Capability는 provider와 동일하지 않다.
- Plugin은 Pipeline, Product Feature 또는 Runtime Module과 동일하지 않다.
- Plugin의 존재나 Capability 선언은 Product Scope를 확대하지 않는다.
- Plugin은 LectureOS Domain Concept의 identity를 독점하지 않는다.
- Plugin 결과는 validation 없이 canonical LectureOS result가 될 수 없다.
- Plugin은 Human Decision을 생성하거나 자동 승인할 수 없다.
- Plugin Configuration은 Capability Contract의 의미와 Human Authority를 변경할 수 없다.
- Plugin Failure는 정상 결과로 숨기지 않는다.
- compatibility는 결과 품질이나 Human Approval의 보장이 아니다.
- Plugin 교체는 기존 결과와 provenance를 설명 없이 덮어쓰지 않는다.
- Plugin Lifecycle 변화는 과거 결과와 Review History를 삭제하지 않는다.
- Plugin Provenance는 Source Timeline과 upstream provenance를 대체하지 않는다.
- 특정 provider, model, vendor 또는 외부 format이 Plugin Concept의 중심 identity가 될 수 없다.

## 14. Acceptance Criteria

- Plugin과 Plugin Capability가 구분된다.
- Capability와 provider가 구분된다.
- Plugin, Pipeline, Product Feature와 Runtime Module의 경계가 명확하다.
- Capability Contract가 의미, provenance, validation, failure와 Human Authority의 경계를 정의한다.
- Plugin Identity가 provider 및 Domain Concept identity와 구분된다.
- Plugin Lifecycle이 과거 provenance와 사용자 결정을 보존한다.
- Plugin Configuration과 Plugin Context의 책임이 구분된다.
- Plugin Validation과 Plugin Compatibility가 품질 보장이나 Approval로 오해되지 않는다.
- Capability Negotiation이 설치, 실행 또는 자동 선택을 의미하지 않는다.
- Plugin Failure와 uncertainty가 정상 결과로 숨겨지지 않는다.
- Plugin Provenance가 교체와 재처리 후에도 유지된다.
- 특정 provider, format 또는 구현 방식에 종속되지 않는다.

## 15. Assumptions and Open Questions

### 15.1 Confirmed

- Plugin은 Provider Independence를 지원하는 Blueprint Concept다.
- Capability는 provider나 Product Feature와 동일하지 않다.
- Plugin은 Pipeline 책임과 Human Authority를 소유하지 않는다.
- provider-specific result는 검증 전 LectureOS의 canonical result가 아니다.
- Plugin 교체와 재처리는 Source Timeline, provenance와 사용자 결정을 보존해야 한다.

### 15.2 Working Assumption

- 하나의 Plugin은 하나 이상의 Capability를 제공할 수 있다.
- 하나의 Capability Contract를 여러 Plugin이 만족할 수 있다.
- compatibility는 Plugin 전체보다 Capability와 Context의 관계로 판단하는 편이 적절하다.

### 15.3 Requires Validation

- 초기 Product Requirements에서 독립적으로 구분해야 할 최소 Capability 집합은 무엇인가?
- Capability Contract의 변화와 compatibility를 제품 수준에서 어떻게 판별할 것인가?
- Plugin Context에 포함할 수 있는 데이터 범위와 사용자 통제는 무엇인가?
- 여러 compatible Plugin이 있을 때 선택 권한과 기본 정책은 누구에게 있는가?
- 과거 Plugin을 사용할 수 없을 때 재현성과 provenance의 최소 보장 범위는 무엇인가?
- Plugin이 여러 Capability를 함께 제공할 때 각각의 failure와 provenance를 어떻게 구분할 것인가?

### 15.4 Deferred

- Plugin Architecture와 Runtime
- Plugin 발견, 설치, 로딩과 제거
- package와 dependency 관리
- registry와 manifest의 구체적인 표현
- 호출 interface와 통신 방식
- execution isolation과 permission model
- compatibility 및 version resolution 구현
- Plugin 개발 도구와 배포 정책

## 16. Non-Goals

이 문서는 다음을 정의하지 않는다.

- Plugin의 물리적 구성과 실행 방식
- 설치, 로딩, package 또는 dependency 처리
- 호출 interface와 payload
- registry 또는 manifest 구현
- 실행 격리와 권한 구현
- provider별 integration
- 기술 stack과 framework
- 새로운 Product Feature 또는 Pipeline

## Related Documents

- [000_MANIFESTO.md](./000_MANIFESTO.md)
- [001_PRODUCT.md](./001_PRODUCT.md)
- [002_FAQ.md](./002_FAQ.md)
- [003_VISION.md](./003_VISION.md)
- [004_PRINCIPLES.md](./004_PRINCIPLES.md)
- [020_PRODUCT_REQUIREMENTS.md](./020_PRODUCT_REQUIREMENTS.md)
- [021_SYSTEM_CONTEXT.md](./021_SYSTEM_CONTEXT.md)
- [030_DATA_MODEL.md](./030_DATA_MODEL.md)
- [031_ARCHITECTURE.md](./031_ARCHITECTURE.md)
- [040_TRANSCRIPT_PIPELINE.md](./040_TRANSCRIPT_PIPELINE.md)
- [041_SUBTITLE_PIPELINE.md](./041_SUBTITLE_PIPELINE.md)
- [042_LECTURE_INTELLIGENCE_PIPELINE.md](./042_LECTURE_INTELLIGENCE_PIPELINE.md)
- [043_REVIEW_PIPELINE.md](./043_REVIEW_PIPELINE.md)
- [044_EXPORT_PIPELINE.md](./044_EXPORT_PIPELINE.md)
