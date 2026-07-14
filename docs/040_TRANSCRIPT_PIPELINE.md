# 040_TRANSCRIPT_PIPELINE

- Status: Draft
- Version: Blueprint 0.1
- Last Updated: 2026-07-14
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
  - `../patches/PATCH-0001-l0-and-prd-stabilization.md`
- Referenced By:
  - `041_SUBTITLE_PIPELINE.md`
  - `042` Lecture Intelligence Pipeline
  - `043` Review Pipeline

## Purpose

이 문서는 Source Media가 External ASR Boundary를 거쳐 Raw Transcript로 보존되고, 교정·검증·Review Decision을 통해 Corrected Transcript로 발전하는 Transcript Pipeline을 정의한다.

Pipeline 단계의 책임, 단계가 만드는 결과의 의미, provenance, Validation, 재처리와 실패 처리를 설명한다. API, 저장 구조, 실행 방식, 특정 AI provider, 교정 방법 또는 사용자 인터페이스는 정의하지 않는다.

## 1. Pipeline Scope

### Included

- Source Media와 Source Timeline 연결
- External ASR Boundary
- Raw Transcript 보존
- 교정 후보와 Corrected Transcript revision
- Transcript Unit의 시간 추적
- 구조적 Validation
- Transcript 관련 Review Item 준비
- Review Decision과 사용자 Modification 연결
- provenance와 revision
- 부분 재처리와 실패 노출

### Excluded

- Subtitle 구성, 분할, 표시 시간과 가독성 규칙
- Lecture Segment와 Edit Candidate 생성
- SRT와 다른 Artifact 생성
- 외부 export
- 외부 NLE와 실제 편집
- 자동 컷 적용과 FCPXML
- 구체적인 Transcript Unit 종류
- 화자 분리 기능의 확정

Transcript Pipeline은 Text Pipeline의 일부지만 Subtitle Pipeline을 포함하지 않는다. Corrected Transcript는 downstream Subtitle과 Lecture Intelligence 처리에 제공될 수 있으나 그 결과를 직접 만들지 않는다.

## 2. Pipeline Principles

1. **Source First:** Source Media와 Source Timeline을 변경하지 않는다.
2. **Raw Before Corrected:** Raw Transcript를 먼저 보존하며 Corrected Transcript가 이를 덮어쓰지 않는다.
3. **Provenance Before Convenience:** ASR 결과, 교정 후보, 사용자 Modification과 Review Decision의 계보를 유지한다.
4. **AI Is Suggestion:** AI는 인식 또는 교정 후보를 만들지만 사용자 판단이 필요한 최종 의미를 확정하지 않는다.
5. **Validation Before Approval:** 구조적으로 유효하지 않은 결과를 승인 가능한 Corrected Transcript로 취급하지 않는다.
6. **Human Authority:** Accept, Reject, Modify는 사용자 판단이며 AI 결과보다 높은 작업 권위를 가진다.
7. **Reprocessing Safe:** ASR 또는 Correction을 다시 수행해도 기존 사용자 결정과 revision 이력을 암묵적으로 삭제하지 않는다.
8. **Provider Independent:** 특정 ASR, correction 또는 LLM provider의 구조를 Pipeline 중심 개념으로 사용하지 않는다.

## 3. Pipeline Overview

~~~text
Source Media + Source Timeline
        |
        v
Source Intake
        |
        v
External ASR Boundary
        |
        v
Raw Transcript Preservation
        |
        v
Correction Candidates
        |
        v
Corrected Transcript Revision
        |
        v
Structural Validation
        |
        v
Transcript Review Preparation
        |
        v
User Review: Accept / Reject / Modify
        |
        v
Decision Application
        |
        v
Transcript Ready State
        |
        v
Corrected Transcript available to downstream pipelines
~~~

이 그림은 논리적 책임과 결과의 발전 순서를 나타낸다. 물리적 실행 순서, 호출 방식 또는 저장 구조를 뜻하지 않는다.

`Transcript Ready State`는 새로운 독립 도메인 개념이 아니다. 구조적 Validation과 적용 가능한 Review Decision을 반영해 downstream 처리에 사용할 수 있는 Corrected Transcript의 논리 상태를 뜻한다. 구체적인 상태 모델은 이 문서에서 정의하지 않는다.

## 4. Pipeline Stages

### 4.1 Source Intake

- **Responsibility:** Source Media 참조를 확인하고 Transcript 결과가 Source Timeline으로 돌아갈 수 있는 처리 문맥을 준비한다.
- **Produces:** 원본 변경 없이 사용할 수 있는 Source Media 참조, Source Timeline 연결, 초기 Failure 또는 Diagnostic.
- **Does Not Produce:** ASR 결과, Raw Transcript, 교정 후보, 승인 상태.

Source Intake는 촬영, 외부 파일의 장기 보관 또는 원본 변환 정책을 소유하지 않는다.

### 4.2 External ASR Boundary

- **Responsibility:** 교체 가능한 External AI Provider의 ASR 역할과 Transcript Pipeline 내부 책임을 분리한다.
- **Produces:** provider 원본 결과와 출처, 제공 가능한 발화·단어 시간 정보, confidence 또는 Uncertainty, provider failure.
- **Does Not Produce:** 사용자 승인 결과, Corrected Transcript, Subtitle, provider 결과에서 분리된 내부 conceptual identity.

provider 결과는 검증되지 않은 외부 생성 결과다. provider 고유 구조와 식별자는 provenance로 보존할 수 있지만 Transcript의 유일한 identity가 될 수 없다.

### 4.3 Raw Transcript Preservation

- **Responsibility:** External ASR Boundary가 반환한 변경 전 결과를 Raw Transcript로 보존하고 Source Media, Source Timeline, Processing Run과 연결한다.
- **Produces:** 출처와 가능한 시간 정보 및 Uncertainty를 유지한 Raw Transcript revision.
- **Does Not Produce:** 교정된 텍스트, 사용자 결정, 승인된 Transcript 상태.

Raw Transcript는 후속 Correction이나 사용자 Modification으로 덮어쓰지 않는다. ASR 결과가 불완전하더라도 실패와 누락을 숨기기 위해 내용을 임의로 보완하지 않는다.

### 4.4 Correction

- **Responsibility:** Raw Transcript와 선택적 교정 컨텍스트를 바탕으로 인식 오류, 고유명사, 전문용어와 숫자에 대한 교정 후보를 준비한다.
- **Produces:** Raw Transcript와 연결된 교정 후보, 후보의 근거와 출처, Corrected Transcript revision, Uncertainty 또는 Review 필요성.
- **Does Not Produce:** Raw Transcript의 변경, 자동 사용자 승인, Subtitle, AI가 직접 정한 최종 timestamp.

Correction은 AI 또는 다른 처리 규칙의 제안일 수 있다. 자연스럽다는 이유만으로 근거 없는 변경을 확정하지 않으며, 의미 위험이 있거나 불확실한 변경은 Review 대상으로 보낸다.

### 4.5 Structural Validation

- **Responsibility:** Raw Transcript와 Corrected Transcript revision의 시간 연결, 순서, 누락과 구조적 무결성을 AI의 의미 판단과 분리해 확인한다.
- **Produces:** Validation Result, 영향받는 Transcript Unit 또는 Time Range와 연결된 Diagnostic, 필요한 Review Item.
- **Does Not Produce:** 의미 정확성에 대한 사용자 판단, 교정 후보, Review Decision, 자동 승인.

Validation Failure가 있는 결과는 정상 완료나 승인 가능한 상태로 숨기지 않는다. Validation은 AI가 제안한 표현의 자연스러움을 평가하는 활동이 아니다.

### 4.6 Transcript Review Preparation

- **Responsibility:** 교정 후보, Uncertainty, Validation Failure, 누락과 의미 위험을 Review Item으로 연결하고 관련 Source Media 구간을 확인할 수 있게 준비한다.
- **Produces:** 원래 후보, Raw Transcript, Corrected Transcript revision, Source Media 또는 Time Range까지 추적 가능한 Review Item.
- **Does Not Produce:** 사용자 대신 내린 Accept·Reject·Modify, 자동 승인, UI layout 또는 Review Engine.

모든 변경이 반드시 독립된 Review Item을 가져야 하는지는 이 문서에서 확정하지 않는다. Transcript Review Preparation은 `031_ARCHITECTURE.md`의 공통 Review 활동으로 Transcript 대상을 전달한다.

### 4.7 Decision Application

- **Responsibility:** 사용자의 Accept, Reject, Modify를 관련 교정 후보와 Corrected Transcript revision에 연결하고 결정과 Modification의 계보를 보존한다.
- **Produces:** Review Decision, 사용자 Modification과 연결된 Corrected Transcript revision, 충돌 또는 재확인이 필요한 Review Item.
- **Does Not Produce:** Source Media 변경, Raw Transcript 변경, AI의 자동 승인, Subtitle 또는 Artifact.

Reject된 교정 후보는 새 사용자 판단 없이 승인 상태가 되지 않는다. Modify는 상태 표시에 그치지 않고 원래 후보, 사용자 변경과 변경된 결과의 관계를 유지해야 한다.

### 4.8 Transcript Ready State

- **Responsibility:** downstream 처리가 사용할 Corrected Transcript가 필요한 Validation과 사용자 결정을 반영했는지 논리적으로 구분한다.
- **Produces:** provenance와 현재 적용 가능한 Review Decision을 유지한 Corrected Transcript의 논리적 사용 가능 상태.
- **Does Not Produce:** 별도의 승인 Transcript 엔티티, Final Subtitle, SRT, Edit Candidate 또는 외부 export.

Approval은 Source Media보다 높은 사실 권위를 부여하지 않는다. Corrected Transcript가 현재 작업에서 사용할 수 있음을 나타낼 뿐이며, Source Media와 Raw Transcript까지의 계보를 계속 유지한다.

## 5. Transcript Unit and Time Traceability

Transcript Unit은 Transcript의 발화 또는 텍스트를 안정적으로 참조하기 위한 최소 개념적 단위의 자리다. 이 Pipeline은 단위를 Word, Utterance, Sentence 또는 다른 표현으로 확정하지 않는다.

Transcript Unit과 관련 결과는 다음 조건을 만족해야 한다.

- 가능한 경우 Source Timeline의 Time Range로 추적할 수 있어야 한다.
- Raw Transcript와 Corrected Transcript 사이의 관계를 설명할 수 있어야 한다.
- 교정 후보, Validation Result, Review Item과 Review Decision의 대상을 연결할 수 있어야 한다.
- 재처리 전후에 사용자 결정과 새 후보의 관계를 비교할 수 있어야 한다.

`Segment`는 Lecture Segment와 혼동되므로 Transcript 단위의 대표 용어로 사용하지 않는다. 시간 단위, timestamp 표현과 정렬 계산 방법은 정의하지 않는다.

## 6. Provenance and Revision

Transcript Pipeline은 최소한 다음 출처와 관계를 설명할 수 있어야 한다.

### 6.1 Raw Provenance

- 어떤 Source Media와 Source Timeline에서 인식 결과가 생성되었는가?
- 어떤 External AI Provider 역할과 Processing Run에서 왔는가?
- provider가 제공한 시간 정보와 Uncertainty는 무엇인가?

### 6.2 Correction Provenance

- 어떤 Raw Transcript 또는 이전 Corrected Transcript revision을 근거로 했는가?
- 후보가 AI, 처리 규칙 또는 사용자 Modification 중 어디에서 왔는가?
- 어떤 근거, Validation Result와 Uncertainty가 연결되는가?

### 6.3 Decision Provenance

- 어떤 Review Item과 교정 후보에 대한 결정인가?
- 사용자가 Accept, Reject, Modify 중 어떤 판단을 했는가?
- Modify라면 원래 후보와 변경된 결과는 어떻게 연결되는가?
- 이후 Review Decision이 이전 결정을 대체했다면 그 이력은 어떻게 이어지는가?

### 6.4 Revision Continuity

새 revision은 이전 표현을 설명 없이 덮어쓰지 않는다. 현재 사용할 Corrected Transcript를 구분할 수 있어야 하지만, 이전 근거와 사용자 판단을 잃지 않아야 한다. 구체적인 revision 식별과 supersession 표현은 후속 설계에서 정한다.

## 7. Validation Strategy

Validation은 교정 결과의 구조적 안전성을 확인하며 AI의 의미 판단과 분리한다.

### 7.1 Time Alignment

- Transcript의 시간 기반 부분이 Source Timeline으로 추적 가능한지 확인한다.
- 시간 연결이 없거나 검증할 수 없는 부분을 정상으로 간주하지 않는다.
- AI가 최종 timestamp를 직접 생성하거나 변경한 결과를 승인 근거로 사용하지 않는다.

### 7.2 Ordering

- Transcript Unit과 관련 시간 범위의 순서가 원본 시간 흐름을 위반하지 않는지 확인한다.
- 순서가 불명확하거나 충돌하면 Validation Failure 또는 Review Item으로 연결한다.

### 7.3 Missing Content

- Source Media 또는 Raw Transcript에서 존재하는 내용이 교정 과정에서 설명 없이 누락되지 않았는지 확인할 수 있어야 한다.
- 누락 여부를 확정할 수 없으면 빈 정상 결과로 처리하지 않고 Uncertainty를 노출한다.

### 7.4 Structural Integrity

- Raw Transcript, Corrected Transcript, Transcript Unit과 provenance 연결이 끊기지 않았는지 확인한다.
- 교정 결과가 원래 후보와 revision 관계를 잃지 않았는지 확인한다.
- Correction revision과 사용자 Modification이 연결된 provenance 및 현재 Review Decision과 모순되지 않는지 확인한다.
- 구조적으로 유효하지 않은 결과가 Transcript Ready State로 이동하지 않게 한다.

Validation의 구체적인 규칙, 임계값과 계산 방법은 이 문서에서 정하지 않는다.

## 8. Review Connection

Transcript Pipeline은 공통 Review Architecture에 다음 대상을 제공할 수 있다.

- 낮은 confidence 또는 Uncertainty가 있는 ASR 결과
- 인식 오류와 교정 후보
- 고유명사와 전문용어 변경
- 숫자 변경과 의미 위험
- Source Timeline 연결 문제
- 누락, 순서 또는 구조적 Validation Failure
- 서로 충돌하는 교정 revision과 기존 Review Decision

각 Review Item은 가능한 경우 Raw Transcript, 교정 후보, 관련 Source Media 또는 Time Range를 함께 확인할 수 있어야 한다. Review 결과인 Accept, Reject, Modify는 Decision Application으로 돌아와 provenance와 revision에 반영된다.

Transcript Pipeline은 Review UI, 검수 우선순위 전체 또는 다른 Pipeline의 Review 대상을 정의하지 않는다.

## 9. Failure Model

### 9.1 ASR Failure

External ASR Boundary가 결과를 만들지 못하거나 사용할 수 없는 결과를 반환한 상태다. 실패 범위와 Diagnostic을 노출하며 정상 Raw Transcript가 생성된 것처럼 표시하지 않는다.

### 9.2 Correction Failure

교정 후보 또는 Corrected Transcript revision을 신뢰할 수 있게 만들지 못한 상태다. Raw Transcript는 보존하며 실패가 기존 사용자 결정이나 유효한 revision을 손상시키지 않게 한다.

### 9.3 Validation Failure

시간 연결, 순서, 누락 또는 구조적 무결성 조건을 만족하지 못한 상태다. 영향받는 결과를 Transcript Ready State로 취급하지 않고 Diagnostic 또는 Review Item으로 연결한다.

### 9.4 Incomplete Transcript

ASR이 일부 Source Media 구간을 충분히 인식하지 못했거나, Correction 결과가 누락·충돌·Uncertainty로 인해 완전하지 않은 상태다. 어느 단계에서 불완전해졌는지와 영향 범위를 구분하고, 완전한 Transcript처럼 downstream에 제공하지 않는다. Correction 결과에 사람의 판단이 필요하다면 User Review Required로 연결한다.

### 9.5 User Review Required

자동으로 해소할 근거가 부족해 사용자의 판단이 필요한 상태다. 관련 Source Media 구간, Raw Transcript, 후보, 이유와 Uncertainty를 Review Item으로 연결한다.

### 9.6 Failure Propagation

- 실패는 영향받는 Transcript revision과 Time Range에 연결되어야 한다.
- 부분 실패가 독립적으로 유효한 Raw Transcript와 사용자 결정을 삭제해서는 안 된다.
- 필요한 선행 결과가 유효하지 않으면 downstream 사용 가능 상태로 표시하지 않는다.
- 실패를 빈 텍스트, 무음 또는 정상 교정으로 해석하지 않는다.

구체적인 재시도 방식과 오류 분류 체계는 이 문서에서 정의하지 않는다.

## 10. Reprocessing Strategy

재처리는 새 Raw Transcript, 교정 후보 또는 Corrected Transcript revision을 만들 수 있다. 기존 Review Decision과 사용자 Modification은 새 결과에 자동 적용하거나 삭제하지 않는다.

### 10.1 ASR Change

- 새 ASR 결과는 새 Raw Transcript provenance와 연결한다.
- 기존 Raw Transcript를 덮어쓰지 않는다.
- 기존 Corrected Transcript와 사용자 결정을 새 결과와 비교할 수 있게 유지한다.
- 적용 가능성이 확실하지 않은 기존 결정은 자동 적용하지 않고 Review Item으로 보낸다.

### 10.2 Correction Change

- correction provider 또는 교정 방식이 바뀌면 영향받는 교정 후보와 Corrected Transcript revision을 다시 준비할 수 있다.
- 기존 사용자 Modification과 Review Decision을 새 후보로 대체하지 않는다.
- 충돌과 의미 변화는 Review Item으로 연결한다.

### 10.3 Validation Rule Change

- 새 규칙으로 영향받는 Transcript revision을 다시 검증할 수 있다.
- Validation Result 변경이 기존 사용자 결정을 자동 무효화하거나 승인하지 않는다.
- 이전에 승인 가능한 상태였던 결과에 새 문제가 생기면 숨기지 않고 재확인 대상으로 표시한다.

### 10.4 Reprocessing After Review

- 재처리 결과와 기존 Review Decision의 provenance를 각각 유지한다.
- Accept, Reject, Modify와 Modification 이력을 초기화하지 않는다.
- 기존 결정과 새 후보의 관계가 불명확하면 자동 승계하지 않는다.
- 충돌은 관련 근거와 함께 Review Item으로 보낸다.

### 10.5 Partial Reprocessing

영향받은 단계만 다시 수행할 수 있어야 한다. 이 원칙은 고정된 단계 그래프, 저장 방식 또는 재시도 방법을 뜻하지 않는다. 재처리 후에도 Source Media, Source Timeline, Raw Transcript와 사용자 결정의 계보를 유지해야 한다.

## 11. Assumptions and Open Questions

### Confirmed

- Source Media와 Source Timeline은 변경하지 않는다.
- Raw Transcript는 External ASR 결과를 변경 없이 보존한다.
- Corrected Transcript는 Raw Transcript와 별도 revision 및 계보를 가진다.
- Transcript와 Subtitle은 서로 다른 책임이다.
- AI 교정은 후보이며 사용자 결정을 대신하지 않는다.
- 구조적 Validation은 AI 의미 판단과 분리한다.
- Review는 Accept, Reject, Modify와 관련 Source Media 확인을 지원한다.
- 재처리는 사용자 결정과 Modification 이력을 삭제하거나 덮어쓰지 않는다.
- 특정 ASR, correction 또는 LLM provider에 종속되지 않는다.

### Working Assumption

- Transcript Ready State는 별도 도메인 개념이 아니라 downstream 사용 가능성을 나타내는 Corrected Transcript의 논리적 상태다.
- Transcript Unit을 시간 추적, 교정 계보와 Review 연결을 위한 최소 추상화로 사용한다.

### Requires Validation

- Transcript Unit의 최소 안정 단위와 정식 명칭은 무엇인가?
- Source Media와 Raw Transcript 사이의 missing content를 어떤 근거 범위에서 판별할 수 있는가?
- 어떤 교정은 명시적인 Review Item을 필요로 하는가?
- Corrected Transcript의 현재 사용 가능 revision을 어떻게 판별할 것인가?
- 여러 Review iteration에서 현재 적용 가능한 Review Decision을 어떻게 구분할 것인가?
- 재처리 후 기존 Review Decision을 새 후보에 연결할 수 있는 안전 조건은 무엇인가?
- Speaker Information은 Transcript Pipeline의 V1 책임에 필요한가?

### Deferred

- Transcript Unit의 구체적인 표현과 식별 방식
- 교정 규칙과 의미 위험 판단의 세부 기준
- Validation 규칙의 구체적인 계산 방법과 임계값
- revision과 승인 상태의 구현 방식
- 외부 provider별 통합 방식
- 저장, 실행과 통신 방식

## 12. Downstream Constraints

### Constraints for `041` Subtitle Pipeline

- Raw Transcript가 아니라 검증 및 적용 가능한 사용자 결정을 반영한 Corrected Transcript를 입력 근거로 사용해야 한다.
- Transcript Validation을 우회하거나 구조적으로 유효하지 않은 Corrected Transcript를 정상 입력처럼 사용하지 않아야 한다.
- Corrected Transcript를 Subtitle과 동일한 개념으로 취급하지 않아야 한다.
- Transcript Unit과 Subtitle Unit의 일대일 대응을 가정하지 않아야 한다.
- Source Timeline과 provenance 연결을 유지해야 한다.
- Subtitle 변경이 Raw Transcript 또는 Corrected Transcript를 암묵적으로 덮어쓰지 않아야 한다.

### Constraints for `042` Lecture Intelligence Pipeline

- Transcript를 사용할 경우 어느 Raw 또는 Corrected revision을 근거로 했는지 추적할 수 있어야 한다.
- Transcript의 Uncertainty와 incomplete 범위를 강의 분석에서 정상 확정 정보로 취급하지 않아야 한다.
- Transcript 교정 결과가 교육적 가치나 편집 결정을 자동 확정하는 근거가 되어서는 안 된다.
- Source Timeline 연결을 유지해야 한다.

### Constraints for `043` Review Pipeline

- Transcript 관련 Review Item을 Raw Transcript, 교정 후보, Corrected Transcript revision과 Source Media 근거에 연결해야 한다.
- Accept, Reject, Modify와 사용자 Modification의 계보를 보존해야 한다.
- Validation Failure와 Uncertainty를 정상 승인 결과처럼 숨기지 않아야 한다.
- 재처리 후 기존 결정과 새 후보의 충돌을 표시할 수 있어야 한다.
- Transcript Review를 읽기 전용 Report로 축소하지 않아야 한다.

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
- `../patches/PATCH-0001-l0-and-prd-stabilization.md`

## Change Log

### Blueprint 0.1 — 2026-07-14

- Source Media에서 Raw Transcript와 Corrected Transcript로 이어지는 논리 Pipeline을 정의했다.
- 교정 후보, 구조적 Validation, Review Decision과 사용자 Modification의 계보를 연결했다.
- 실패와 부분 재처리에서 Raw Transcript와 사용자 결정을 보존하는 제약을 정의했다.
- Subtitle, Lecture Intelligence와 Review Pipeline이 이어받아야 할 Transcript 계약을 기록했다.
