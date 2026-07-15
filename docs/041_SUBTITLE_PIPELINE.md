# 041_SUBTITLE_PIPELINE

- Status: Draft
- Version: Blueprint 0.1
- Last Updated: 2026-07-15
- Layer: L1 — Pipeline
- Depends On:
  - `000_MANIFESTO.md`
  - `001_PRODUCT.md`
  - `002_FAQ.md`
  - `003_VISION.md`
  - `004_PRINCIPLES.md`
  - `020_PRODUCT_REQUIREMENTS.md`
  - `021_SYSTEM_CONTEXT.md`
  - `030_DATA_MODEL.md`
  - `031_ARCHITECTURE.md`
  - `040_TRANSCRIPT_PIPELINE.md`
  - `../patches/PATCH-0001-l0-and-prd-stabilization.md`
- Referenced By:
  - `043` Review Pipeline
  - `044` Export Pipeline

## Purpose

이 문서는 검증되어 downstream 처리에 사용할 수 있는 Corrected Transcript가 시청 가능한 Subtitle과 Final Subtitle로 발전하는 Subtitle Pipeline을 정의한다.

Pipeline 단계의 책임, Subtitle Unit의 의미, 읽기 표현과 시간 표현, provenance, Validation, Review 연결, 재처리와 실패 처리를 설명한다. Subtitle은 Transcript의 저장 형식이 아니라 시청을 위한 파생 표현이다. 이 문서는 외부 자막 파일 형식, Artifact 생성, export, 사용자 인터페이스, 저장 구조, 실행 방식 또는 특정 AI provider를 정의하지 않는다.

## 1. Pipeline Scope

### Included

- 검증되고 현재 적용 가능한 사용자 결정을 반영한 Corrected Transcript
- Subtitle Candidate와 Subtitle revision
- Subtitle Unit
- Reading Representation과 Time Representation 책임
- Subtitle의 구조적 Validation
- Subtitle 관련 Review Item 준비
- Review Decision과 사용자 Modification 연결
- Final Subtitle
- provenance와 revision
- 부분 재처리와 실패 노출

### Excluded

- Source Media 인식과 Raw Transcript 생성
- Transcript 의미 교정
- Lecture Segment와 Edit Candidate 생성
- Artifact 생성과 외부 export
- 외부 자막 파일 형식과 생성 규칙
- 외부 NLE와 실제 영상 편집
- 자동 컷 적용과 FCPXML
- 자막 표시와 영상 재생 구현
- 구체적인 가독성 또는 타이밍 임계값

Subtitle Pipeline은 Text Pipeline의 일부지만 Transcript Pipeline이나 Artifact Generation을 포함하지 않는다. `040_TRANSCRIPT_PIPELINE.md`가 제공하는 유효한 Corrected Transcript를 입력 근거로 사용하며, Final Subtitle이 Artifact Generation에 사용될 수 있는 논리적 준비 상태까지 다룬다.

## 2. Pipeline Principles

1. **Transcript Is Not Subtitle:** Corrected Transcript는 발화 의미의 언어 계층이고 Subtitle은 시청을 위한 표현 계층이다. 어느 쪽도 다른 쪽을 덮어쓰지 않는다.
2. **Readability Before Storage:** Subtitle은 저장 편의보다 시청 가독성을 위해 구성한다.
3. **Representation Before Artifact:** Subtitle과 Final Subtitle이 외부 전달용 Artifact보다 먼저 존재하며, Artifact가 중심 표현을 대신하지 않는다.
4. **Source Traceability:** 모든 Subtitle Unit은 가능한 경우 Source Timeline의 근거로 추적할 수 있어야 한다.
5. **Human Authority:** AI 또는 처리 규칙은 Subtitle 후보를 만들 수 있지만 사용자의 Accept, Reject, Modify를 대신하지 않는다.
6. **Validation Before Review:** 구조적으로 유효하지 않은 Subtitle Candidate를 정상 Review 대상으로 전달하지 않고 Validation Failure를 함께 드러낸다.
7. **Meaning Boundary:** Subtitle Pipeline은 가독성과 표시 구조를 다루며 Corrected Transcript의 발화 의미를 임의로 다시 교정하지 않는다.
8. **Reprocessing Safe:** Subtitle 구성 기준이 바뀌거나 Transcript가 갱신되어도 사용자 Modification과 Review Decision을 암묵적으로 삭제하거나 새 후보에 자동 적용하지 않는다.
9. **Provider Independent:** 특정 AI provider나 외부 자막 형식의 구조를 Subtitle의 중심 개념으로 사용하지 않는다.

## 3. Pipeline Overview

~~~text
Validated Corrected Transcript
        |
        v
Transcript Intake
        |
        v
Subtitle Candidate Generation
        |
        +----> Reading Representation
        |
        +----> Time Representation
        |
        v
Subtitle Revision
        |
        v
Structural Validation
        |
        v
Subtitle Review Preparation
        |
        v
User Review: Accept / Reject / Modify
        |
        v
Decision Application
        |
        v
Final Subtitle
        |
        v
Artifact Generation Ready State
~~~

이 그림은 논리적 책임과 Subtitle 표현의 발전 순서를 나타낸다. 물리적 실행 순서, 내부 컴포넌트 호출 또는 저장 구조를 뜻하지 않는다. Reading Representation과 Time Representation은 별도 도메인 엔티티가 아니라 Subtitle Candidate를 구성하는 두 책임 관점이다.

`Artifact Generation Ready State`는 Pipeline 단계, 새로운 도메인 개념 또는 Artifact가 아니다. Final Subtitle이 필요한 Validation과 적용 가능한 Review Decision을 반영해 downstream Artifact Generation에 사용될 수 있음을 나타내는 논리적 상태일 뿐이다.

## 4. Pipeline Stages

### 4.1 Transcript Intake

- **Responsibility:** `040_TRANSCRIPT_PIPELINE.md`의 Validation을 통과하고 현재 적용 가능한 사용자 결정을 반영한 Corrected Transcript를 확인하며 Source Timeline과 provenance 연결을 이어받는다.
- **Produces:** Subtitle 구성을 시작할 수 있는 Corrected Transcript 참조와 그 revision, Source Timeline 연결, 입력의 Failure 또는 Diagnostic.
- **Does Not Produce:** Raw Transcript, Transcript 교정, Subtitle Candidate, 사용자 승인.

Transcript Validation을 우회하거나 구조적으로 유효하지 않은 Corrected Transcript를 정상 입력처럼 사용하지 않는다. 입력이 불완전하면 그 범위와 불확실성을 Subtitle Pipeline에서 숨기지 않는다.

### 4.2 Subtitle Candidate Generation

- **Responsibility:** Corrected Transcript의 내용과 시간 근거를 바탕으로 시청용 Subtitle Candidate와 Subtitle Unit 구성을 제안한다.
- **Produces:** Corrected Transcript와 연결된 Subtitle Candidate revision, 후보 Subtitle Unit, 생성 근거와 Uncertainty.
- **Does Not Produce:** Corrected Transcript 변경, Final Subtitle, 사용자 Review Decision, 외부 자막 Artifact.

Candidate 생성은 AI 또는 처리 규칙의 도움을 받을 수 있다. Candidate는 Review와 Validation 이전의 제안이며, Corrected Transcript Unit과 Subtitle Unit의 일대일 대응을 가정하지 않는다.

### 4.3 Reading Representation

- **Responsibility:** 발화 의미를 유지하면서 시청자가 읽기 좋은 표시 단위, 분할, 줄 구성과 필요한 표현 정리를 Subtitle Candidate에 반영한다.
- **Produces:** 읽기 구조가 설명 가능한 Subtitle Unit과 관련 revision, 가독성 문제 또는 Uncertainty.
- **Does Not Produce:** Transcript 의미 교정, 구체적인 가독성 정책의 임계값, 사용자 승인, 화면 렌더링.

표시 표현을 구성하거나 분할할 때 Corrected Transcript와의 계보를 유지해야 한다. 읽기 편의를 이유로 발화 의미를 설명 없이 삭제하거나 바꾸지 않는다.

### 4.4 Time Representation

- **Responsibility:** Subtitle Unit의 표시 범위와 순서를 Source Timeline의 근거에 연결하고 읽기 표현과 시간 표현이 함께 검증될 수 있게 한다.
- **Produces:** Source Timeline으로 추적 가능한 Subtitle Unit의 Time Range와 표시 순서, 시간 관련 Uncertainty 또는 Diagnostic.
- **Does Not Produce:** AI가 직접 확정한 최종 timestamp, 편집 후 Timeline, 실제 영상 컷, 구체적인 타이밍 계산 방법.

Subtitle은 Corrected Transcript의 시간 구조를 설명 없이 잃거나 원본 시간축과 분리되어서는 안 된다. 의미 경계는 시간 표현의 후보 근거가 될 수 있지만 Time Range의 구조적 유효성은 다음 Validation 단계가 확인한다.

### 4.5 Structural Validation

- **Responsibility:** Subtitle revision의 읽기 구조, Source Timeline 연결, Time Range 일관성, 표시 순서와 provenance 무결성을 확인한다.
- **Produces:** Validation Result, 영향받는 Subtitle Unit 또는 Time Range에 연결된 Diagnostic, 필요한 Review Item.
- **Does Not Produce:** Transcript 의미 판단, 사용자 Review Decision, 자동 승인, Artifact.

Validation Failure가 있는 Subtitle revision을 Final Subtitle로 취급하지 않는다. Validation은 구체적인 표현이 교육적으로 올바른지 대신 판단하지 않으며, Transcript Pipeline의 의미 검증을 다시 수행하지 않는다.

### 4.6 Subtitle Review Preparation

- **Responsibility:** 분할, 표현, 타이밍, 읽기 문제, Uncertainty와 Validation Failure를 Subtitle 관련 Review Item으로 연결하고 관련 Source Media 구간을 확인할 수 있게 준비한다.
- **Produces:** Subtitle Candidate, Corrected Transcript, Subtitle revision, Source Media 또는 Time Range까지 추적 가능한 Review Item.
- **Does Not Produce:** 사용자 대신 내린 Accept·Reject·Modify, 자동 승인, Review UI 또는 다른 Pipeline의 Review 정책.

모든 Subtitle Unit이 반드시 독립된 Review Item을 가져야 하는지는 이 문서에서 확정하지 않는다. Subtitle Review Preparation은 `031_ARCHITECTURE.md`의 공통 Review 활동으로 Subtitle 대상을 전달한다.

### 4.7 Decision Application

- **Responsibility:** 사용자의 Accept, Reject, Modify를 관련 Subtitle Candidate와 revision에 연결하고 Review Decision과 Modification의 계보를 보존한다.
- **Produces:** Review Decision, 사용자 Modification을 반영한 Subtitle revision, 충돌하거나 재확인이 필요한 Review Item.
- **Does Not Produce:** Corrected Transcript 변경, 자동 승인, 외부 자막 Artifact 또는 실제 영상 편집.

Reject된 후보는 새 사용자 판단 없이 다시 승인 상태가 되지 않는다. Modify는 상태 표시에 그치지 않고 원래 후보, 사용자 변경, 변경된 결과와 결정 사이의 관계를 유지해야 한다.

### 4.8 Final Subtitle

- **Responsibility:** 구조적 Validation과 적용 가능한 Review Decision을 반영해 외부 전달용 Artifact를 만들 수 있는 승인 상태의 Subtitle 표현을 구분한다.
- **Produces:** Corrected Transcript, Source Timeline, Subtitle revision과 사용자 결정까지의 provenance를 유지한 Final Subtitle.
- **Does Not Produce:** 별도의 승인 Subtitle 엔티티, 외부 자막 파일, export, 실제 화면 렌더링.

Final Subtitle은 SRT와 동일하지 않으며 외부 파일이 Final Subtitle을 덮어쓰지 않는다. 승인 상태는 Source Media보다 높은 사실 권위를 부여하지 않고 현재 작업에서 사용할 Subtitle 표현을 확정한다.

## 5. Subtitle Unit

Subtitle Unit은 Source Timeline의 특정 Time Range와 연결되는 하나의 자막 단위다. Transcript Unit이 발화 또는 텍스트를 안정적으로 참조하기 위한 자리인 것과 달리, Subtitle Unit은 시청 가독성과 표시를 위한 책임을 가진다.

Subtitle Unit은 다음 조건을 만족해야 한다.

- 가능한 경우 Source Timeline의 Time Range로 추적할 수 있어야 한다.
- 근거가 된 Corrected Transcript revision과의 관계를 설명할 수 있어야 한다.
- 읽기 표현과 시간 표현을 함께 검증할 수 있어야 한다.
- Subtitle Candidate, Validation Result, Review Item과 Review Decision을 연결할 수 있어야 한다.
- 사용자 Modification과 이후 revision의 계보를 유지할 수 있어야 한다.

하나의 Transcript 부분은 읽기 표현에 따라 여러 Subtitle Unit으로 나뉠 수 있다. 여러 Transcript Unit도 의미와 시간 근거를 잃지 않는 범위에서 하나의 Subtitle Unit에 기여할 수 있다. 구체적인 결합과 분할 방법은 이 문서에서 정하지 않는다.

## 6. Reading Representation

Reading Representation은 Corrected Transcript의 의미를 시청자가 읽기 쉬운 Subtitle로 표현하는 책임 관점이다. 별도의 저장 개념이나 화면 표현 구현을 뜻하지 않는다.

다음 사항을 다룬다.

- 발화 호흡과 의미 경계를 고려한 표시 단위 구성
- 지나치게 많은 내용을 한 표시 단위에 두지 않기 위한 분할
- 읽는 흐름을 방해하지 않는 줄 구성
- 발화 의미를 유지하는 범위의 표현 정리
- 분할과 결합 이후 Corrected Transcript와의 추적 관계

가독성 정책의 구체적인 수치, 언어별 기준과 판단 방법은 이 문서에서 확정하지 않는다. 정책이 달라져도 Corrected Transcript와 사용자 Modification을 덮어쓰지 않고 Subtitle만 다시 구성할 수 있어야 한다.

## 7. Time Representation

Time Representation은 Subtitle Unit이 Source Timeline 위에서 언제 표시되고 어떤 순서를 갖는지 표현하는 책임 관점이다. 편집 도구의 UI Timeline이나 편집 후 시간축을 뜻하지 않는다.

다음 원칙을 따른다.

- Subtitle Unit의 Time Range는 가능한 경우 Source Timeline의 근거로 돌아갈 수 있어야 한다.
- 표시 순서는 원본 시간 흐름과의 관계를 잃지 않아야 한다.
- 읽기 표현을 위해 Time Range가 조정되더라도 근거가 된 Transcript 시간 구조를 설명할 수 있어야 한다.
- 검증할 수 없는 시간 연결, 충돌과 Uncertainty를 정상 결과처럼 숨기지 않는다.

시간 단위, timestamp 표현, 경계 계산과 조정 방법은 정의하지 않는다.

## 8. Provenance and Revision

Subtitle Pipeline은 최소한 다음 관계를 설명할 수 있어야 한다.

### 8.1 Transcript Provenance

- 어떤 Corrected Transcript revision에서 Subtitle Candidate가 생성되었는가?
- 어떤 Transcript Unit 또는 Time Range가 각 Subtitle Unit의 근거인가?
- 입력 Transcript의 Failure나 Uncertainty가 어느 Subtitle 범위에 영향을 주는가?

### 8.2 Subtitle Provenance

- 어떤 처리 기준 또는 후보 생성 문맥에서 Subtitle revision이 만들어졌는가?
- 분할, 결합, 표현 변경과 시간 조정은 이전 revision과 어떻게 연결되는가?
- Reading Representation과 Time Representation의 결과가 어떤 근거를 유지하는가?

### 8.3 Decision Provenance

- 어떤 Review Item과 Subtitle Candidate에 대한 결정인가?
- 사용자가 Accept, Reject, Modify 중 어떤 판단을 했는가?
- Modify라면 원래 후보와 사용자 변경 결과는 어떻게 연결되는가?
- 이후 결정이 이전 결정을 대체했다면 그 이력은 어떻게 이어지는가?

### 8.4 Revision Continuity

새 Subtitle revision은 이전 표현을 설명 없이 덮어쓰지 않는다. 현재 Final Subtitle을 구분할 수 있어야 하지만 이전 후보, 사용자 Modification과 Review Decision을 잃지 않아야 한다. 구체적인 revision 식별과 supersession 표현은 후속 설계에서 정한다.

## 9. Validation Strategy

Validation은 Subtitle의 가독성과 시간 구조를 확인하며 Transcript 의미 판단과 분리한다.

### 9.1 Reading Structure

- Subtitle Unit의 분할과 줄 구성이 적용 가능한 가독성 정책을 위반하지 않는지 확인한다.
- 지나치게 길거나 불완전한 표시 단위를 정상 결과처럼 통과시키지 않는다.
- 구체적인 정책 수치와 판정 방법은 후속 검증에서 정한다.

### 9.2 Time Consistency

- Subtitle Unit의 Time Range가 Source Timeline으로 추적 가능한지 확인한다.
- 시간 범위가 유효하고 읽기 표현과 모순되지 않는지 확인한다.
- 검증할 수 없는 시간 연결은 Validation Failure 또는 Review Item으로 연결한다.

### 9.3 Ordering

- Subtitle Unit의 표시 순서가 Source Timeline의 흐름과 모순되지 않는지 확인한다.
- 순서가 불명확하거나 충돌하면 정상 Final Subtitle로 취급하지 않는다.

### 9.4 Structural Integrity

- Corrected Transcript, Subtitle Candidate, Subtitle Unit과 provenance 연결이 끊기지 않았는지 확인한다.
- 분할 또는 결합 과정에서 Transcript 내용이 설명 없이 누락되거나 중복되지 않았는지 확인할 수 있어야 한다.
- 사용자 Modification, 현재 적용 가능한 Review Decision과 Subtitle revision이 모순되지 않는지 확인한다.
- 구조적으로 유효하지 않은 결과가 Final Subtitle로 이동하지 않게 한다.

Validation의 구체적인 규칙, 임계값과 계산 방법은 이 문서에서 정하지 않는다. 의미 오류가 발견되면 Subtitle에서 임의로 교정하지 않고 Transcript 관련 Review 흐름으로 연결해야 한다.

## 10. Review Connection

Subtitle Pipeline은 공통 Review Architecture에 다음 대상을 제공할 수 있다.

- Subtitle Unit 분할 또는 결합 후보
- 줄 구성과 표시 표현 변경
- Time Range와 표시 순서 문제
- 읽기 어려운 표현 또는 불완전한 Subtitle
- Corrected Transcript와 Subtitle 사이의 누락 또는 중복
- Reading Structure, Time Consistency, Ordering 또는 Structural Integrity의 Validation Failure
- 서로 충돌하는 Subtitle revision과 기존 Review Decision

각 Review Item은 가능한 경우 Subtitle Candidate, Corrected Transcript, 관련 Source Media 또는 Time Range를 함께 확인할 수 있어야 한다. Review 결과인 Accept, Reject, Modify는 Decision Application으로 돌아와 provenance와 revision에 반영된다.

Subtitle Pipeline은 Review UI, 검수 우선순위 전체 또는 Transcript와 Edit Pipeline의 Review 대상을 정의하지 않는다. Review를 읽기 전용 Report로 축소하거나 AI가 Review Decision을 자동 확정하게 하지 않는다.

## 11. Failure Model

### 11.1 Subtitle Generation Failure

Corrected Transcript에서 사용할 수 있는 Subtitle Candidate 또는 Subtitle Unit 구성을 만들지 못한 상태다. 영향 범위와 Diagnostic을 노출하며 빈 Subtitle을 정상 결과처럼 표시하지 않는다.

### 11.2 Validation Failure

읽기 구조, 시간 일관성, 순서 또는 구조적 무결성 조건을 만족하지 못한 상태다. 영향받는 Subtitle revision을 Final Subtitle로 취급하지 않고 Diagnostic 또는 Review Item으로 연결한다.

### 11.3 Incomplete Subtitle

입력 Corrected Transcript의 불완전한 범위가 이어졌거나 Subtitle 생성·분할·결합 과정에서 일부 내용을 신뢰할 수 있게 표현하지 못한 상태다. 어느 단계에서 불완전해졌는지와 영향받는 Time Range를 구분하며, 완전한 Subtitle처럼 downstream에 제공하지 않는다.

### 11.4 User Review Required

가독성, 시간 구조 또는 기존 결정과의 충돌을 자동으로 해소할 근거가 부족해 사용자의 판단이 필요한 상태다. 관련 Source Media 구간, Corrected Transcript, Subtitle Candidate, 이유와 Uncertainty를 Review Item으로 연결한다.

### 11.5 Failure Propagation

- 입력 Corrected Transcript가 유효하지 않으면 해당 범위를 정상 Subtitle Candidate로 진행하지 않는다.
- 실패는 영향받는 Subtitle revision, Subtitle Unit과 Time Range에 연결되어야 한다.
- 부분 실패가 독립적으로 유효한 Subtitle revision과 사용자 결정을 삭제해서는 안 된다.
- 필요한 선행 결과가 유효하지 않으면 Final Subtitle 또는 Artifact Generation 준비 상태로 표시하지 않는다.
- 실패를 빈 표시 단위, 정상 타이밍 또는 사용자 승인으로 해석하지 않는다.

구체적인 재시도 방식과 오류 분류 체계는 이 문서에서 정의하지 않는다.

## 12. Reprocessing Strategy

재처리는 새 Subtitle Candidate 또는 Subtitle revision을 만들 수 있다. 기존 Review Decision과 사용자 Modification은 새 결과에 자동 적용하거나 삭제하지 않는다.

### 12.1 Corrected Transcript Change

- 새 Corrected Transcript revision을 근거로 영향받는 Subtitle Candidate를 다시 준비할 수 있다.
- 기존 Final Subtitle과 사용자 결정을 새 후보로 덮어쓰지 않는다.
- Transcript 의미 또는 시간 근거가 달라져 기존 결정의 적용 가능성이 불명확하면 Review Item으로 보낸다.

### 12.2 Subtitle Rule Change

- 가독성 또는 시간 구조 기준이 바뀌면 영향받는 Subtitle Candidate와 revision을 다시 구성하고 검증할 수 있다.
- 기존 사용자 Modification과 Review Decision을 새 후보에 자동 적용하지 않는다.
- 새 결과와 기존 결정의 충돌은 근거와 함께 Review Item으로 연결한다.

### 12.3 Reprocessing After Review

- 재처리 결과와 기존 Review Decision의 provenance를 각각 유지한다.
- Accept, Reject, Modify와 사용자 Modification 이력을 초기화하지 않는다.
- 기존 결정이 새 후보에도 안전하게 적용되는지 불명확하면 자동 승계하지 않는다.
- 충돌은 관련 Corrected Transcript, Subtitle revision과 Source Media 근거를 포함한 Review Item으로 보낸다.

### 12.4 Partial Reprocessing

영향받은 Subtitle 단계만 다시 수행할 수 있어야 한다. 이 원칙은 고정된 실행 그래프, 저장 방식 또는 재시도 방법을 뜻하지 않는다. 재처리 후에도 Corrected Transcript, Source Timeline, Subtitle revision과 사용자 결정의 계보를 유지해야 한다.

## 13. Assumptions and Open Questions

### Confirmed

- Corrected Transcript와 Subtitle은 서로 다른 책임이다.
- Subtitle Unit은 Transcript Unit과 반드시 일대일로 대응하지 않는다.
- Subtitle과 Final Subtitle은 SRT Artifact보다 상위의 중심 표현이다.
- Final Subtitle은 Review와 사용자 결정을 반영한 승인 상태의 Subtitle 표현이다.
- 모든 Subtitle Unit은 가능한 경우 Source Timeline으로 추적할 수 있어야 한다.
- AI 또는 처리 규칙은 Subtitle 후보를 만들지만 사용자의 결정을 대신하지 않는다.
- Review는 Accept, Reject, Modify와 관련 Source Media 확인을 지원한다.
- 재처리는 사용자 결정과 Modification 이력을 삭제하거나 덮어쓰지 않는다.

### Working Assumption

- Subtitle Candidate와 Subtitle revision은 새 중심 엔티티가 아니라 Subtitle이 Review 전까지 발전하는 후보 및 revision 표현이다.
- Reading Representation과 Time Representation은 별도 엔티티가 아니라 Subtitle 구성의 책임 관점이다.
- `Artifact Generation Ready State`는 별도 도메인 개념이 아니라 Final Subtitle의 논리적 사용 가능 상태다.

### Requires Validation

- 어떤 Subtitle 변경이 명시적인 Review Item을 필요로 하는가?
- 적용 가능한 가독성 정책과 그 임계값은 무엇인가?
- 발화 호흡과 의미 경계를 Subtitle 분할에 어떤 우선순위로 반영할 것인가?
- 여러 Transcript Unit을 하나의 Subtitle Unit에 결합할 수 있는 안전 조건은 무엇인가?
- 시간 조정이 허용되는 범위와 원본 근거를 확인하는 기준은 무엇인가?
- 여러 Review iteration에서 현재 적용 가능한 Subtitle Review Decision을 어떻게 구분할 것인가?
- 재처리 후 기존 Subtitle Decision을 새 후보에 연결할 수 있는 안전 조건은 무엇인가?

### Deferred

- 구체적인 가독성 및 시간 정책과 계산 방법
- Subtitle revision과 승인 상태의 구현 방식
- 외부 자막 파일 형식과 생성 규칙
- Artifact 생성과 export 방식
- 저장, 실행과 통신 방식
- 외부 편집 결과의 round trip

## 14. Downstream Constraints

### Constraints for `043` Review Pipeline

- Subtitle 관련 Review Item을 Subtitle Candidate, Subtitle revision, Corrected Transcript와 Source Media 근거에 연결해야 한다.
- 줄 분할, 표현, 타이밍, 가독성 문제와 Validation Failure를 함께 다룰 수 있어야 한다.
- Accept, Reject, Modify와 사용자 Modification의 계보를 보존해야 한다.
- Review를 읽기 전용 Report나 자동 승인 활동으로 축소하지 않아야 한다.
- 재처리 후 기존 결정과 새 후보의 충돌을 표시할 수 있어야 한다.

### Constraints for `044` Export Pipeline

- Final Subtitle을 외부 자막 Artifact의 입력 근거로 사용해야 한다.
- 외부 자막 Artifact를 Final Subtitle이나 중심 도메인 데이터로 취급하지 않아야 한다.
- Artifact가 어떤 Final Subtitle revision과 사용자 결정에서 생성되었는지 추적할 수 있어야 한다.
- Artifact 손실이 Final Subtitle, 사용자 결정 또는 provenance 손실을 의미하지 않아야 한다.
- 외부 파일 형식이 Subtitle Unit과 Final Subtitle의 개념 책임을 재정의하지 않아야 한다.
- Subtitle Pipeline의 Validation을 우회하거나 구조적으로 유효하지 않은 Subtitle revision을 정상 Artifact로 취급하지 않아야 한다.

## Related Documents

- `000_MANIFESTO.md`
- `001_PRODUCT.md`
- `002_FAQ.md`
- `003_VISION.md`
- `004_PRINCIPLES.md`
- `020_PRODUCT_REQUIREMENTS.md`
- `021_SYSTEM_CONTEXT.md`
- `030_DATA_MODEL.md`
- `031_ARCHITECTURE.md`
- `040_TRANSCRIPT_PIPELINE.md`
- `../patches/PATCH-0001-l0-and-prd-stabilization.md`

## Change Log

### Blueprint 0.1 — 2026-07-15

- Corrected Transcript에서 Subtitle Candidate와 Final Subtitle로 이어지는 논리 Pipeline을 정의했다.
- Subtitle Unit, Reading Representation과 Time Representation의 책임을 구분했다.
- Subtitle의 구조적 Validation, Review Decision, 사용자 Modification과 provenance를 연결했다.
- 실패와 부분 재처리에서 Final Subtitle과 사용자 결정을 보존하는 제약을 정의했다.
- Review와 Export Pipeline이 이어받아야 할 Subtitle 계약을 기록했다.
