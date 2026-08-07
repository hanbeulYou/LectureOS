# 041_SUBTITLE_PIPELINE

- Status: Draft
- Version: Blueprint 0.3
- Last Updated: 2026-08-07
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
  - `../patches/PATCH-0029-effective-transcript-sourced-subtitle-candidate-contract.md`
- Amended By:
  - `../patches/PATCH-0041-effective-subtitle-readability-and-editorial-timing-policy.md`
  - `../patches/PATCH-0042-effective-subtitle-readability-enforcement-boundary.md`
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

> **계약 세대 주석 (PATCH-0029):** 이 절의 "Corrected Transcript의 내용과 시간 근거를 바탕으로"라는 입력 전제와
> 그 첫 구현(released `subtitle_candidates` 계열, readiness/legacy selection/review lineage 기반)은 **legacy
> subtitle candidate 계약 세대**에 속하며 해당 세대의 역사적 record에 대해 계속 유효하다. Effective Transcript
> (Raw 또는 Corrected)에서 생성되는 Subtitle Candidate는 §15의 **effective-transcript-sourced 계약**을 따른다.
> 이 주석은 기존 계약 문언을 삭제하지 않고 세대를 구분한다.

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

> **후속 결정 note (`PATCH-0042`):** 위 금지는 그대로 유효하며, **effective-transcript 계약 세대의 readable
> generation**에 대해 다음과 같이 구체화된다. §16 R-11의 **blocking** severity readability finding은 이 절이
> 말하는 **Validation Failure에 해당한다**. 그 금지는 §16의 enforcement 절(EN-4)에 따라 **Final Subtitle
> admission에서 집행**된다 — 생성·Review Preparation·Human Decision 단계가 아니다. **warning** severity는 이
> 금지에 포함되지 않으며 Final Subtitle 확정을 막지 않는다(EN-6). `deterministic_segment_passthrough`
> generation과 legacy 계약 세대에는 소급 적용되지 않는다(EN-9).

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

> **후속 결정 note (`PATCH-0042`):** 이 절의 "**구조적 Validation과** 적용 가능한 Review Decision을 **반영해**"는
> **effective-transcript 계약 세대의 readable Candidate**에 대해 두 조건을 함께 요구하는 것으로 확정된다.
> readable Candidate가 Final Subtitle로 선택되려면 **① 적용 가능한 Human Review Decision**과 **② readability
> blocking finding 부재**를 **모두** 만족해야 한다. 이 조건은 **Final Selection Admission이 집행**한다(§16 EN-4).
> **Review accept가 존재한다는 사실만으로 Final Subtitle 적격성이 생기지 않는다**(EN-3). warning severity는 이
> 조건에 포함되지 않는다(EN-6). §16의 이 forward note는 `PATCH-0041`이 이 절을 재범위화하지 않는다고 한 진술을
> `PATCH-0042`가 이 한 지점에서 좁힌 결과이며, 이 절의 기존 문언은 변경되지 않는다.

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

> **후속 결정 note (`PATCH-0041`):** 위 유보는 그대로 유효하다. 다만 **effective-transcript 계약 세대**에
> 한해 구체 수치와 판단 방법이 **§16**에서 versioned generation policy로 확정되었다. legacy 세대와
> `deterministic_segment_passthrough` generator에는 적용되지 않으며, "정책이 달라져도 Subtitle만 다시 구성한다"는
> 위 원칙은 §16 R-13(파라미터 변경 → 새 Candidate identity)과 R-14(released record 불변)로 실현된다.

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

> **후속 결정 note (`PATCH-0041`):** effective-transcript 계약 세대에 대한 "후속 검증"은 완료되었다. 수치와
> 판정 방법은 **§16 R-10/R-11**에 있으며, 특히 R-11은 배포 차단 위반과 비차단 진단을 구분한다 — `7초` 초과는
> 그 자체로 corruption이 아니다. legacy 세대의 판정 방법은 여전히 이 절의 유보 아래 있다.

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

> **해소 note (`PATCH-0041`):** 위 질문 목록은 문언 그대로 유효하다. 그중 **네 항목이
> effective-transcript 계약 세대에 한해 §16에서 해소되었다**:
>
> | 질문 | 해소 위치 |
> |---|---|
> | 적용 가능한 가독성 정책과 그 임계값 | §16 R-10 |
> | 발화 호흡과 의미 경계를 분할에 반영할 우선순위 | §16 R-5 |
> | 여러 Transcript Unit을 하나의 Subtitle Unit에 결합할 안전 조건 | §16 R-6 |
> | 시간 조정이 허용되는 범위와 원본 근거 확인 기준 | §16 R-7 / R-8 |
>
> 나머지 세 항목 — 어떤 변경이 명시적 Review Item을 요구하는가, 여러 iteration에서 현재 적용 가능한 Decision을
> 어떻게 구분하는가, 재처리 후 기존 Decision을 새 후보에 연결할 안전 조건은 무엇인가 — 은 **계속 미결**이며 §16이
> 답하지 않는다. legacy 세대에 대해서는 네 항목도 미결로 남는다.

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

## 15. Effective-Transcript-Sourced Subtitle Candidate (First Slice)

이 절은 `PATCH-0029`(GOAL-013 Architect Decision)로 승인된 Architect 결정(E1…E14)을 기록한다. GOAL-012의
**Effective Transcript Consumption Boundary**(040 §21)를 소비하는 subtitle candidate 생성의 규범 계약이다.
구현·스키마·마이그레이션은 이 절에 포함되지 않으며 GOAL-013 구현 milestone이 별도로 수행한다.

**Contract Generation Boundary (Confirmed, E1):** effective transcript에서 생성되는 Subtitle Candidate는
**새로운 additive versioned persisted 표현**을 사용한다(유력한 persistence 계열:
`subtitle_effective_candidates` / `subtitle_effective_candidate_cues` /
`subtitle_effective_candidate_cue_segments` — 구현 goal이 저장소 관례에 맞는 최종 이름을 선택한다). 이 표현은
effective-transcript-sourced pipeline의 **canonical** 표현이며 임시 adapter나 shadow table이 아니다. released
legacy 표현(v12 `subtitle_candidates` 계열)은 legacy pipeline에 대해서만 canonical로 남는다. **하나의 계약 세대
안에는 경쟁하는 canonical 표현이 존재하지 않는다** — 두 표현의 공존은 의도된 versioned 아키텍처 경계이며, 모든
역사적 세대를 통틀어 물리적 표현이 하나여야 한다는 이전 문언은 이 결정으로 대체된다.

**Legacy Preservation (Confirmed, E2):** 기존 legacy candidate record는 released 계약 아래 유효한 역사적
record로 남는다. 재작성·backfill·GOAL-012 source로의 재해석·조작된 binding/source-kind 부여·진실한 역사적 증거
없는 이전·삭제·조용한 supersession은 금지된다. 두 표현은 계약 세대로 영구히 구분 가능하다.

**Semantic Reuse (Confirmed, E3):** `SubtitleCandidate`/`SubtitleCue` 재사용은 **도메인 의미와 invariant의
재사용**이다: 생성된 자막 제안으로서의 Candidate identity, 순서 있는 Cue 집합, Cue timing/text invariant,
결정적 Cue 순서, source segment lineage, Candidate/Cue 불변성, 생성 provenance, Cue 구조 검증. released
persistence 컬럼 전체나 legacy provenance 요구는 상속되지 않는다: legacy readiness·legacy current-selection·
applicability evaluation·TranscriptReviewDecision·ReviewItem·CandidateReference·validation identity와 필수
ProcessingRun/UnitExecution identity는 진실하게 존재하지 않는 한 새 표현에 포함되지 않으며, 옛 스키마를 닮기
위해 조작하는 것을 금지한다.

**Supported Sources (Confirmed, E4):** 지원 source kind는 GOAL-011/012가 확립한 정확히 두 가지다:
`raw_transcript`와 `corrected_transcript_revision`. Candidate는 source kind·정확한 immutable source identity·
`TranscriptSourceIntake` identity·Raw parent identity·Effective Transcript Consumption Binding identity·소비된
순서 있는 snapshot identity 또는 fingerprint를 보존한다. Corrected source의 교체 segment lineage는 effective
input이 제공하는 범위에서 Raw segment lineage까지 추적 가능해야 한다. **같은 내용 ≠ 같은 source ≠ 같은
candidate** — 텍스트가 동일해도 source entity가 다르면 별개의 Candidate다.

**Sole Acquisition Boundary (Confirmed, E5):** 생성은 transcript 내용을 오직 GOAL-012 소비 경계로만 획득한다.
현재 Raw/corrected authority를 독자적으로 해석하거나, 조용히 Raw로 fallback하거나, 생성 중간에 재해석하거나,
snapshot을 혼합하거나, provenance를 위해 생성 후 binding을 소급 구성하는 것을 금지한다. binding은 생성 전에
존재하며 소비된 정확한 source를 고정한다. **Transcript authority ≠ effective 해석 ≠ 소비 ≠ subtitle 생성.**

**Deterministic Local Provenance (Confirmed, E6):** 이 계약의 첫 canonical generator는 결정적 로컬
generator이며 provenance는 `ProcessingRun`/`UnitExecution` 없이 표현된다: generator kind·generator version·
알고리즘/parameter version·consumption binding identity·결정적 generation key. 가짜 실행 lifecycle record는
금지된다. 실행 기반 generator는 이후 별도의 versioned 계약으로 도입될 수 있다. **생성 provenance ≠ 인간 교정
provenance ≠ review authority ≠ 실행 orchestration.**

**Deterministic Identity (Confirmed, E7):** 미래 Candidate identity는 결정적이고 **source-sensitive**해야
한다. 최소한 consumer/generator 계약·intake identity·consumption binding identity·source kind·정확한 source
identity·generator version·알고리즘/parameter version을 반영한다. timestamp·mutable current selection·content
fingerprint 단독·물리 경로·출력 파일명·latest row·auto-increment sequence 단독에 의한 identity는 금지된다.
Cue identity는 immutable Candidate 안에서 결정적이며 삽입 시점에 의존하지 않는다. 정확한 hash 구성은 GOAL-013
구현에 위임된다.

> **후속 결정 note (`PATCH-0041`):** 이 조항의 "알고리즘/parameter version"에는 **§16 R-10의 readability
> parameter set**이 포함된다. 따라서 임계값이 하나라도 바뀌면 parameter version이 바뀌고 새 Candidate identity가
> 파생된다(§16 R-13). 이는 E7의 identity 구성을 **변경하지 않고** 그 안에서 해석되는 것이며, 새 identity 메커니즘은
> 도입되지 않는다. §16 L-4에 따라 승인된 줄 구조는 cue text 안에 있으므로 identity에 자동으로 참여한다.

**Replay (Confirmed, E8):** 동일한 정확한 source binding + 동일 generator version + 동일 parameter + 동일 요청
의미 → 동일 Candidate 재사용. Raw → Corrected → 동일 Raw 복귀 → 원래 Raw-source Candidate 재사용. 내용이
동일해도 source entity가 다르면 별개 Candidate다. 이는 구현이 유예되어 있어도 계약 요구사항이다.

**Concurrency (Confirmed, E9):** 근접 동시 동일 생성 요청은 중복 canonical Candidate 없이 수렴해야 한다.
서로 다른 요청은 내용이 같다는 이유만으로 병합되지 않는다. locking/uniqueness 구체 기제는 구현 소유다.

**Atomicity (Confirmed, E10):** Candidate·순서 있는 Cue 집합·Cue-source segment lineage·생성 provenance는
atomic하게 commit된다. 부분 저장된 Candidate가 유효한 것으로 보일 수 없다.

**Currentness ≠ Integrity (Confirmed, E11):** Candidate는 authority 변경 후에도 역사적인 정확한 source
binding을 유지한다. stale해지는 것은 Candidate를 변경·삭제·손상 처리·자동 재생성하지 않으며 자동 Raw fallback을
일으키지 않고 provenance를 재작성하지 않는다. **Candidate 무결성 ≠ source currentness ≠ review 적용 가능성 ≠
final selection 적격성.**

**Human Authority Separation (Confirmed, E12):** 생성은 Human Decision·review record·수락·거부·선택을 만들지
않으며 review/authority/validation/실행 identity를 조작하지 않는다.

**Deferred Downstream Integration (Confirmed, E13):** 새 표현은 legacy 단계(subtitle review 준비·review
record·Human Decision·candidate 수락/거부·final subtitle selection·SRT export·물리 materialization)에 자동
진입하지 않는다. GOAL-013 이후 effective-source Candidate가 아직 review·선택·export 불가능한 상태로 존재하는
것은 유효하다. 각 downstream 연결은 별도로 범위가 정해진 GOAL로 도입된다. **Candidate 존재 ≠ review 준비 ≠
review authority ≠ Human Decision ≠ final selection ≠ export 적격성.**

**Additive Evolution (Confirmed, E14):** 구현은 strictly additive여야 한다(예상 스키마 v39, 전체 마이그레이션
ritual). legacy 컬럼 변경·역사적 backfill·이중 기록(dual-write)은 금지된다. 새 표현의 미래 repository
validation은 무결성 전용이며(stale은 손상이 아님) GOAL-012 §21의 검증 원칙을 따른다.

## 16. Readability and Editorial Timing Policy (Effective-Transcript Generation)

이 절은 `PATCH-0041`로 승인된 Architect 결정(R-1…R-14, L-1…L-5)을 기록한다. §4.3 Reading Representation과
§4.4 Time Representation이 이미 계약한 책임에 대해, **effective-transcript 계약 세대의 구체적 generation
policy**를 확정한다. 새 Product Domain·새 Aggregate·새 Authority·새 lifecycle을 만들지 않으며, 스키마 변경과
마이그레이션을 요구하지 않는다.

근거는 실측이다. 2시간 2분 36초 실제 강의에서 생성된 2,564 cue 중 **94.2%가 이미 1~7초**, **98.0%가 44자
이하**이며, 개입 대상은 1초 미만 60개·7초 초과 88개·44자 초과 52개·인접 완전중복 4개다. 0.020초 cue가 Final Cut
Pro import를 실제로 중단시켰고, 0.5초 교사·학생 대화는 정상 발화이며, 145자 cue는 CPS 6.3이라 CPS 규칙으로
탐지되지 않는다.

### 범위와 generator

**Scope (Confirmed, R-1):** 이 정책은 **effective-transcript 세대의 readable subtitle candidate에만** 적용된다.
legacy 계약 세대와 released `deterministic_segment_passthrough` generator는 변경·재범위화·폐기되지 않으며, 기존
어떤 record도 새 의미를 얻지 않는다.

**Generator (Confirmed, R-2):** `readable_cue_composition`은 §15 E6/E7 provenance 아래의 **새로운 additive
generator version**이다. passthrough generator를 대체·포장·supersede·재해석하지 않으며, passthrough는 이 세대에서
계속 지원되는 generator다.

**Candidate Competition (Confirmed, R-3):** 하나의 Effective Transcript Consumption Binding은 passthrough
Candidate와 readable Candidate를 동시에 가질 수 있다. 이는 §15 E9의 통상 동작이며 새 개념을 필요로 하지 않는다.
**어느 쪽도 자동으로 승격·선호·순위화·선택되지 않는다.** 채택 권위는 released Review Preparation·Human
Decision·Final Selection에 그대로 남는다.

### 변환 의미

**Text Preservation (Confirmed, R-4):** generator는 입력 transcript text의 문자 시퀀스·순서·의미를 정확히
보존한다. 문자를 추가·삭제·재작성·정규화·trim·재배열·번역·구두점화·대소문자 변경 하지 않는다. **유일하게 허용되는
삽입은 L-1의 line break**이며, 이는 §5가 Subtitle Unit을 전사 단위가 아니라 표시 단위로 정의하기 때문에 허용된다.
삽입된 모든 line break를 제거하면 원본 text가 정확히 복원되어야 한다 — 이는 검증 가능한 불변식이다.

**Split (Confirmed, R-5):** 하나의 source cue는 `duration > 7.000초` **또는** `text length > 44자`이면서 내부에
안전한 분할 지점이 있을 때 여러 표시 cue가 될 수 있다. 분할 지점은 고정 우선순위로 선택한다.

1. 문장 종결부호(`.` `?` `!`)
2. 쉼표 또는 접속 경계
3. 어절(공백) 경계

**단어 중간 분할은 금지한다.** 형태소 분석은 사용하지 않는다. pause 기반 분할은 사용할 수 없고 승인되지도 않았다 —
`040 §15` L-15의 승인된 provider configuration에서 word-level timestamp가 존재하지 않으며, 이를 켜는 것은 다른
계약의 결정이다.

우선순위를 만족하는 분할 지점이 없거나 분할 결과가 임계값을 위반하면 **generator는 분할하지 않는다.** cue를 그대로
내보내고 진단을 기록한다(R-11). 강제 분할은 금지된다.

**Merge (Confirmed, R-6):** 이 세대에서 generator는 **text가 문자 단위로 완전히 동일한 인접 cue만** 병합한다.
병합된 cue는 두 시간 범위의 합집합을 가지며 text를 한 번만 담는다. text가 다른 cue의 병합, 의미를 근거로 한 서로
다른 발화의 병합은 **금지된다** — speaker diarization이 존재하지 않으므로 한 화자의 이어지는 문장과 두 화자의 턴을
구분할 증거가 없다. 병합된 모든 cue의 source segment lineage는 보존된다.

**Timing Extension (Confirmed, R-7):** 목표 하한보다 짧은 cue는 **다음 cue 앞의 실제 gap 안에서만** `1.000초`를
향해, 그 이상은 아니게 확장할 수 있다. generator는 다음 cue를 이동시키거나 침범하거나 overlap을 만들거나 순서를
바꾸거나 Source Timeline 밖으로 확장해서는 안 된다. 무음으로의 확장은 발화를 발명하지 않지만, 이웃을 밀어내는 것은
발화를 왜곡한다. gap이 부족하면 짧은 cue를 그대로 두고 진단을 기록한다.

**Timing Interpolation (Confirmed, R-8):** word timestamp 없이 긴 cue를 분할할 때 내부 경계는 **source cue 자신의
시간 범위 안에서 문자 수에 비례하여** 계산한다. 이 값은 **derived presentation timing**이며 관측된 발화 경계가
명시적으로 아니고, 파생값임이 기록되어야 한다. 생성된 모든 cue에 대해 원본 transcript 시간 범위와
cue-to-source-segment lineage가 복원 가능해야 한다. 보간된 경계는 결코 source 범위를 벗어나지 않는다.

**Ordering and Non-overlap (Confirmed, R-9):** 표시 순서와 비겹침은 **불변식**이고 가독성 임계값은 **목표**다.
충돌하면 불변식이 이기고, 원본 cue가 그대로 남으며, 달성하지 못한 목표는 진단이 된다. 검증 코퍼스에 overlap이 0건
이므로 이 계약은 새 속성을 도입하는 것이 아니라 이미 성립하는 속성을 보존한다.

### 임계값

**Readability Parameter Set, version 1 (Confirmed, R-10):**

| parameter | value |
|---|---|
| hard minimum display duration | `0.100초` |
| target minimum display duration | `1.000초` |
| maximum display duration | `7.000초` |
| maximum characters per line | `22` |
| maximum lines per cue | `2` |
| maximum characters per cue | `44` |
| CPS warning threshold | `> 12` |

이 값들은 **하나의 versioned parameter set**을 이루며 Candidate identity에 참여한다(R-13). 값이 하나라도 바뀌면 새
parameter version이 되어 새 Candidate가 생성되며, 기존 Candidate는 결코 변형되지 않는다.

**`0.100초`가 주장하는 것과 주장하지 않는 것.** LectureOS는 `0.100초`를 **이 세대가 생성하는 readable subtitle
cue에 대한 제품 수준 hard minimum**으로 확정한다. 이는 SRT 일반·자막 포맷 일반·모든 외부 consumer에 대한 보편적
validity 규칙으로 주장되지 **않으며**, 그런 주장의 근거로 이 절을 인용해서는 안 된다. 근거는 구체적이다: `0.020초`
cue가 목표 편집 환경인 Final Cut Pro에서 실제로 import에 실패했고, `0.100초`는 24·25·30·60fps의 1프레임보다 충분히
길며, 검증 코퍼스의 정상적인 짧은 대화 cue는 약 `0.5초`이므로 보존된다. **이 값 미만인 기존 passthrough cue가
소급하여 corrupt해지지 않는다** — 그것들은 `040 §14` A-10(`PATCH-0039` 개정)에 따라 정당하게 admit되었고 provider가
산출한 바에 대한 유효한 역사적 record로 남는다.

**CPS에 관하여.** 초당 문자수는 **진단 지표로만** 채택하며 생성 규칙으로는 결코 사용하지 않는다. 실측이 그 이유를
보여준다: 145자 cue의 CPS는 6.3이라 이 코퍼스의 결함을 구조적으로 탐지하지 못한다.

### 줄 표현

**Canonical Line Structure (Confirmed, L-1):** cue의 표시 줄은 **canonical cue text 안의 `U+000A` line break**로
표현된다. line break가 없는 cue text는 한 줄 cue이며, 이는 기존의 축약 사례이므로 released cue는 재해석 없이 모두
유효하다.

판정 기준은 **사람이 무엇을 승인하는가**와 **모든 serializer가 무엇을 공통으로 투영하는가**였다. L-1에서 승인된
artifact가 곧 표시 형태다 — Human Decision과 전달 파일 사이에 어떤 변환도 서 있지 않다. 포맷 간 공통 투영 대상은
표시 줄의 순서열이고, 그것을 하나의 구분자로 정규 표현한다. 각 포맷의 serializer는 그 구분자를 자기 문법(SRT는 문자
그대로의 `LF`)으로 **매핑만** 하며 표현에 관해 아무것도 결정하지 않는다.

같은 기준으로 두 대안을 기각했다. **별도의 ordered line structure**는 cue가 내용을 두 번 소유하게 만들고, 결합
규칙이 필연적으로 serializer에 놓여 "승인 이후에 표현을 결정하는" 문제를 축소된 형태로 재발시키며, 새 필드를
받아들이기 위해 released §15 E7 identity 파생을 변경해야 한다. **serializer가 wrap하는 flat text**는 즉시
기각했다 — serializer가 아무도 승인하지 않은 표시 구조를 발명하게 되고, 하나의 승인된 Final Subtitle에 대해 포맷마다
다른 줄 구조가 배포될 수 있으며, §4.8과 모순된다.

**Line Break Grammar (Confirmed, L-2):** 하나의 cue text 안에서 line break는 최대 `maximum lines per cue − 1`
개이며, **연속 line break 금지**, **선행·후행 line break 금지**, 그 밖의 control character 금지다. 연속 line break를
금지하는 이유는 구체적이다 — released canonical SRT serializer가 블록을 빈 줄로 구분하므로 cue 안의 빈 줄은 블록
framing을 파괴한다.

**Serializer Responsibility Unchanged (Confirmed, L-3):** released `canonical_srt` v1 serializer의 "텍스트 정확
보존" 계약은 문자 그대로 만족된다: 승인된 cue text를 verbatim 내보내며, 내장된 `LF`는 이미 올바른 다중 줄 SRT를
만든다. **어떤 serializer도 text를 wrap·re-wrap·분할·결합·재배치하지 않는다.** 이 절은 어떤 serializer 변경도
승인하지 않는다.

**Identity Participation (Confirmed, L-4):** line break가 cue text 안에 있고 cue text는 이미 Candidate identity와
content fingerprint에 참여하므로, 승인된 표시 구조는 **released identity 파생을 변경하지 않고** identity에 자동으로
참여한다. 줄 구성만 다른 두 Candidate는 서로 다른 Candidate다.

**Widened Meaning of `text` (Confirmed, L-5):** 이 세대에 한해 cue의 `text`는 단순한 발화 텍스트가 아니라 **표시
텍스트**를 뜻한다. 이는 L-1의 비용이며 알면서 수용한다: §5가 이미 Subtitle Unit을 표시 책임으로 정의하고, R-4의
복원 불변식과 L-2의 문법이 확장 범위를 한정한다. legacy 세대의 의미는 변경되지 않는다.

### 권위·identity·보존

**Review Authority (Confirmed, R-12):** readable Candidate는 §4.2가 Candidate를 규정하는 그대로, 그리고 §13
Confirmed가 요구하는 그대로("AI 또는 처리 규칙은 Subtitle 후보를 만들지만 사용자의 결정을 대신하지 않는다")
**자동 제안**이다. 생성은 review record·decision·selection·export 적격성을 만들지 않는다. 채택은 Review와 Final
Selection에 남는다.

**Identity and Replay (Confirmed, R-13):** Candidate identity는 released §15 E7 구성을 사용하며, 이미 반영하는
binding·source kind·정확한 source identity에 더해 generator kind·generator version·algorithm version·readability
parameter version을 반영한다. 같은 binding·같은 immutable input·같은 parameter set은 같은 Candidate로 수렴한다
(§15 E8). 새 identity 메커니즘은 도입되지 않는다.

**Legacy and Released Preservation (Confirmed, R-14):** released record는 재작성·backfill·dual-write·재파생·
마이그레이션·재해석되지 않는다. 기존 Candidate는 identity와 내용을 유지하고, 기존 Review Decision·Final
Selection·SRT Artifact·materialization·delivery·publication은 손대지 않는다. §12.2에 따라 가독성 정책 변경은 새
Candidate를 만들 수 있으나 기존 사용자 Modification과 Review Decision을 **결코** 자동 적용하지 않으며, 승인되거나
발행된 Final Subtitle을 재작성하지 않는다.

### 검증

**Two Severities (Confirmed, R-11):** 검증은 두 단계를 의도적으로 구분한다.

배포 차단(구조 또는 계약 위반):

- 표시 시간 `< 0.100초`
- cue 겹침
- 비증가 표시 순서
- 줄 수 `> 2`
- `22`자를 넘는 줄
- cue text `> 44`자
- line break 문법 위반(L-2)
- source 대비 text 손실·text 추가·lineage 손실(R-4)
- 승인된 줄 구조와 직렬화된 줄 구조의 불일치

비차단 진단(달성하지 못한 가독성 목표, Review로 노출):

- 표시 시간 `< 1.000초`
- 안전한 분할 지점이 없는 상태의 표시 시간 `> 7.000초`
- CPS `> 12`
- 그 밖의 미달성 가독성 목표

**7초 초과는 corruption이 아니다.** 검증 코퍼스에는 정상적인 긴 설명이 존재하고, cue `#1505`(`애들을`, 3자가
13.4초)는 분할할 내용이 없는 긴 cue다. 길이만으로 결함 판정하면 진짜 강의 자료가 고장으로 표시된다.

### 집행 경계 (Enforcement Boundary)

이 소절은 `PATCH-0042`로 승인된 Architect 결정(EN-1…EN-11)을 기록한다. R-11이 정한 severity가 **어디서
집행되는지**를 확정하며, 새 Product Domain·Aggregate·Authority·lifecycle을 만들지 않고 파라미터를 바꾸지 않는다.

경계 배정은 이미 릴리스된 단계 책임에서 도출된다. §4.6은 Review Preparation의 책임을 "Validation Failure를
Review Item으로 **연결**"하는 것으로 정하므로 실패를 드러내야 할 단계가 실패를 거부하는 단계일 수 없고, §4.5는
거부를 **Final Subtitle**에 대해 진술하며, §4.8은 "**구조적 Validation과** … 반영해" 승인 상태를 구분하는 것을
Final Subtitle 자신의 책임으로 정한다.

**Blocking Is an Admission Condition (Confirmed, EN-1):** effective-transcript 세대에서 R-11의 **blocking**
severity finding을 하나라도 가진 readable Candidate는 **Final Subtitle이 될 수 없으며**, 그것을 통해
export·materialization·delivery·publication에 도달할 수 없다. `blocking`은 진단 라벨이 아니라 admission
조건이다. **warning** severity는 어느 경계에서도 admission 결과를 갖지 않는다.

**Generation and Review Preparation Admit (Confirmed, EN-2):** blocking finding은 Candidate 생성을 막지 않고
Review Preparation을 막지 않는다(§4.6). readability finding을 이유로 Candidate record·cue·lineage를 숨기거나
보류하거나 삭제하거나 무효로 표시하지 않는다. R-5와 R-9가 요구하는 "강제 변환 대신 원본 cue + 진단" 결과는 계속
도달 가능하고 관측 가능해야 하며, blocking finding은 Review Item 또는 관측 가능한 validation result로 노출된다.

**Human Decision Admits (Confirmed, EN-3):** 사람은 blocking finding을 가진 Candidate에 대해 `accept`·`reject`·
`modify`를 기록할 수 있다. Review는 관찰과 판단이며, 결함 있는 제안을 판단할 권한을 없애는 것이 그 제안을 개선하지
않는다. **Accept ≠ Final Subtitle 적격성** — 이 분리는 released effective-generation 계약이 이미 갖고 있고,
EN-4는 조건을 하나 더할 뿐 새로 만들지 않는다.

**Final Selection Is the Enforcing Boundary (Confirmed, EN-4):** 새 Final Selection admission은 명령 시점에
해당 Candidate의 readability validation을 **재파생**하고, blocking severity finding이 하나라도 있으면
**거부**한다. 거부는 명시적이고 해당 finding을 열거하며, 조용한 skip·강등·부분 선택·다른 Candidate로의 자동
대체가 아니다.

readability는 **파생이며 저장되지 않는다.** Candidate의 불변 cue 그래프를 그 Candidate 자신의 readability
parameter version(R-13이 이미 identity의 일부로 만든 값)으로 재평가하므로, 생성 시점과 선택 시점 사이에 판정이
흔들릴 수 없다.

**Refusal Preserves Everything (Confirmed, EN-5):** 거부된 선택은 아무것도 쓰지 않고 아무것도 파괴하지 않는다.
Candidate·cue·lineage·Review Subject·모든 Review Decision이 그대로 남고 상류 record는 변경되지 않는다. 부분
Final Selection을 저장하지 않고 downstream side effect를 만들지 않으며 history를 수정하지 않는다. blocking
detail은 최소한 코드와 해당 cue를 포함해 호출자에게 노출된다. 거부는 저장소 손상이 아니라 **복구 가능한 통상
admission 결과**다.

**Warnings Never Refuse (Confirmed, EN-6):** 목표 하한 미만 duration, 안전한 분할 지점이 없는 상태의 최대 초과
duration, CPS 임계 초과, 그 밖의 미달성 가독성 목표는 non-blocking이며 Final Selection을 **막지 않는다**. "7초
초과는 corruption이 아니다"라는 R-11의 진술은 그대로이며 이제 운영상 귀결을 갖는다 — 그런 Candidate는 선택
가능하다.

**Downstream Trusts Final Selection (Confirmed, EN-7):** SRT Artifact 생성·serialization·materialization·
delivery·publication은 readability를 **재평가하지 않는다.** 이들은 EN-4를 이미 만족한 Final Selection을
소비한다. 그 경계들에 readability 재검사·재파생·2차 게이트를 도입하지 않으며 이 절에서 추론될 수 없다. 하나의
결정을 한 곳에서 내리므로 향후 어떤 포맷도 정책을 지지 않는다.

**Strictly Additive; Released Records Immutable (Confirmed, EN-8):** 이미 존재하는 Final Selection·SRT
Artifact·materialization·delivery·publication은 — **Candidate가 blocking finding을 가진 상태에서 만들어진
것을 포함해** — 재작성·무효화·철회·재파생·supersede·표시되지 않는다. EN-4는 **새** admission에만 적용된다.
§12.2가 바뀐 규칙의 기존 결정 자동 적용을 금지하고 R-14가 released record 불변을 요구하는 것과 일치한다.

**Scope Is the Readable Generation (Confirmed, EN-9):** 집행은 `readable_cue_composition`이 생성한 Candidate에
적용된다. `deterministic_segment_passthrough` Candidate에는 소급으로도 장래로도 적용되지 않는다 — 그것들은
readability 정책 아래 구성되지 않았고 그 cue가 적합한 표시 단위로 제안된 적이 없다. passthrough Candidate의 선택
가능성은 모든 면에서 변경되지 않는다.

**No Parameter Change (Confirmed, EN-10):** `22`·`44`·`0.100초`·`1.000초`·`7.000초`·CPS `12`와 readability
parameter version은 변경되지 않는다. 따라서 검증 코퍼스에서 관측된 **blocking 3건은 그대로 남고**, EN-4 아래
해당 Candidate는 조용히 배포되는 대신 **선택 불가**가 된다. 이는 의도된 결과다. 그 3건을 줄이는 것은 향후
parameter version에 관한 별도 Product Decision이며 여기서 내리지 않는다.

**R-4/R-6 Recovery Reference (Confirmed, EN-11):** R-6은 문자 완전 동일 인접 cue의 병합을 승인하고 병합된 cue가
text를 **한 번만** 담는다고 정한다. 따라서 R-4의 정확 복원 요구는 **R-6이 승인한 identical-duplicate collapse
이후의 canonical source sequence**를 기준으로 평가한다. 이는 확장이 아니라 도출이다 — R-4를 원본 시퀀스 기준으로
읽으면 R-6이 자신이 규율하는 모든 경우에서 무효가 되고, 명시적 Confirmed 결정을 무효화하는 해석은 채택할 수 없다.
이 기준은 **다른 어떤 편차도 허용하지 않는다**: semantic merge·유사 병합·공백 무시 병합·그 밖의 text 손실이나
추가는 여전히 금지되며 R-11 아래 blocking으로 남는다.

#### Canonical Invariants (Enforcement)

(1) blocking finding을 가진 Candidate도 Review Preparation과 Human Decision이 가능하다.
(2) blocking finding을 가진 Candidate는 Final Subtitle로 선택될 수 없다.
(3) warning만 가진 Candidate는 Final Selection이 가능하다.
(4) Review accept는 Final Subtitle 적격성이 아니다.
(5) Final Selection 성공 이후 downstream은 readability를 재평가하지 않는다.
(6) blocking 거부는 Candidate·Decision·history를 변경하지 않으며 아무것도 저장하지 않는다.
(7) 이미 released된 Final Selection과 Artifact는 소급 무효화되지 않는다.
(8) `deterministic_segment_passthrough` generation은 이 집행의 대상이 아니다.
(9) readability parameter set과 그 version은 `PATCH-0042`에서 변경되지 않는다.
(10) readability는 파생이며 저장되지 않고, Candidate 자신의 parameter version으로 재평가된다.

### Sections Not Re-scoped

§4.2·§4.3·§4.4·§4.8·§5·§7·§12.2·§13(위 해소 note가 명시한 네 항목 제외)·§15 E1…E14는 이 절로 개정되지 않는다.
legacy 계약 세대, `deterministic_segment_passthrough` generator, released canonical SRT serializer, Review·Final
Selection·SRT Artifact·materialization·delivery·publication의 어떤 계약도 변경되지 않는다.

> **범위 축소 note (`PATCH-0042`):** 위 문언은 `PATCH-0041`이 스스로에 대해 한 진술이며 그 범위에서 그대로
> 유효하다. `PATCH-0042`가 그중 **정확히 한 지점**을 좁힌다: **Final Selection Admission**은 이제
> effective-transcript 세대의 **readable Candidate에 한해** readability 집행을 수행한다(위 EN-4). 이 축소는 그
> 한 경계, 그 한 세대에 한정되며 다음은 **여전히 재범위화되지 않는다** — legacy 계약 세대,
> `deterministic_segment_passthrough` generator, released canonical SRT serializer, Review Preparation, Human
> Review Decision, **SRT Artifact·serialization·materialization·delivery·publication**. 특히 EN-7에 따라
> downstream 경계는 readability를 재평가하지 않으므로 이 축소가 그쪽으로 번지지 않는다. §4.5와 §4.8은 원문이
> 보존된 채 후속 note만 추가되었다.

### Deferred

이 절은 다음을 확정하지 않으며 각각 별도 gate 평가가 필요하다: speaker diarization 기반 merge; 서로 다른 text의
semantic merge; pause 기반 split; word timestamp 기반 timing; 형태소 분석; 기존 Candidate의 소급 변환; 기존 Review
Decision 재적용; Review 비교 화면; cue 구조를 직접 수정하는 Modify Decision; 포맷별 line wrapping; iTT·FCPXML 등 신규
포맷; ASR 환각; 전사 checkpoint; `U+FFFD` 처리; 일괄 correction; terminology dictionary.

### Canonical Invariants

(1) 이 정책은 effective 세대의 readable candidate에만 적용되고 legacy와 passthrough를 변경하지 않는다.
(2) `readable_cue_composition`은 additive generator version이며 passthrough를 대체하지 않는다.
(3) 하나의 binding에 두 Candidate가 공존할 수 있고 자동 승격·자동 선택은 없다.
(4) L-1의 line break를 제외하면 문자는 추가·삭제·재작성되지 않으며 line break 제거로 원본이 정확히 복원된다.
(5) 분할은 조건과 우선순위를 따르고 단어 중간을 자르지 않으며 강제되지 않는다.
(6) 병합은 문자 완전 동일 인접 cue에 한하고 lineage를 보존한다.
(7) 확장은 뒤쪽 실제 gap 안에서만 일어나고 이웃을 이동·침범하지 않는다.
(8) 보간 timing은 derived presentation timing이며 관측된 발화 경계가 아니다.
(9) 순서와 비겹침은 가독성 목표보다 우선한다.
(10) 임계값은 versioned parameter set이며 identity에 참여한다.
(11) `0.100초`는 이 세대의 제품 하한이지 보편적 validity 규칙이 아니고, 기존 cue를 소급 무효화하지 않는다.
(12) CPS는 진단 지표이며 생성 규칙이 아니다.
(13) 줄 구조는 cue text 안의 단일 `LF`이고 serializer는 그대로 투영할 뿐이다.
(14) 채택 권위는 Review와 Final Selection에 남는다.
(15) released record는 재작성·재해석되지 않는다.

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
