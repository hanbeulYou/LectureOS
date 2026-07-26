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
- Amended By:
  - `../patches/PATCH-0020-source-media-transcription-intake-eligibility.md`
  - `../patches/PATCH-0021-external-asr-boundary-provider-transcript-admission.md`
  - `../patches/PATCH-0022-first-local-asr-execution-adapter.md`
  - `../patches/PATCH-0023-current-raw-transcript-selection-and-readiness.md`

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

## 13. Source Intake Application Foundation — Source Media Transcription Intake Eligibility (First Slice)

이 절은 `PATCH-0020`으로 승인된 Architect/Product 결정(S-1…S-14)을 기록한다. **첫 Source Intake milestone**은
§4.1 Source Intake의 첫 application 실현이다. 이 slice는 이미 임포트된 canonical `SourceMedia` 기록
(`045_MEDIA_IMPORT_PIPELINE.md §1`)을 하나 받아, 그것이 **Transcript Pipeline의 입력으로 admit될 자격이 있는지**를
판정하고, 그 확인을 나타내는 durable한 intake 기록을 만든다. 이 slice는 오직 한 가지 질문에 답한다: "이미 임포트된
이 Source Media 기록을 Transcript Pipeline의 입력으로 admit할 수 있는가?" — codec·재생 가능성·길이·audio 존재·언어·
provider·audio 추출·transcription 성공 여부에는 답하지 않는다. **실제 transcription을 수행하지 않는다.**

**Scope (Confirmed, S-1):** Media Import와 Source Intake는 **분리된 단계**다. Media Import는 로컬 파일을 canonical
`SourceMedia`로 등록하고(045 §1), Source Intake는 그 **이미 존재하는 `SourceMediaId`**를 받아 transcript 입력으로의
적격성만 확인한다. 이 slice는 ffmpeg·ffprobe·probe·duration·codec·resolution·stream·audio 검증·audio 추출·
transcode·transcription·provider·language 감지·background job·queue를 도입하지 않는다.

**Input (Confirmed, S-2):** 입력은 **canonical `SourceMediaId`**(예: `sha256:<digest>`)이며 파일 경로가 아니다.
경로는 Media Import의 것이다. Source Intake는 raw 경로를 받지 않는다.

**Eligibility (Confirmed, S-3):** 적격성은 **persist된 사실만으로** 판정되는 repository·application-contract 결정이며
codec·media-content 주장이 아니다. persist된 `source_media` 기록이 그 `SourceMediaId`로 resolve되면 적격이다. 존재
하지 않는(resolve 불가) Source Media는 명시적으로 부적격(거부)이다. 형식이 잘못된(malformed) Source Media identity는
resolve를 시도하기 전에 명시적으로 거부된다.

**No Decoding Claim (Confirmed, S-4):** admit된 입력을 디코딩 의미의 "transcription-ready media"라고 부르지 않는다.
admission은 audio stream 존재·재생 가능성·transcription 성공을 주장하지 않는다. 표현은 "admitted transcription input",
"transcript intake eligibility", "Source Media reference confirmed", "eligible repository input"으로 한정한다.

**Physical File Availability (Confirmed, S-5):** intake는 원본 파일의 **물리적 존재를 확인하지 않는다**. 적격성은
persist된 `source_media` 기록에서만 도출된다. import 이후 reference-in-place 원본이 이동·삭제되어도 그것은 이 slice의
적격성 실패가 아니라 이후 실행 단계의 관심사다(045 §1 M-11과 일관). 저장소 무결성 검증은 원본 파일의 물리적 존재를
확인하지 않는다. 운영상 파일 가용성과 persist된 도메인 무결성은 분리된 채로 유지된다.

**Intake Identity (Confirmed, S-6):** intake 기록은 자신의 identity를 가지며, 그 identity는 Source Media로부터
**결정적으로 파생**된다: `transcript-source-intake:<source_media_id>`. 따라서 하나의 Source Media에는 정확히 하나의
canonical intake 기록이 대응한다.

**Persistence (Confirmed, S-7):** admission은 **persist**된다(계산만 하지 않는다). intake 기록은 durable·immutable·
insert-only이며 하나의 atomic transaction으로 저장된다. 최소한 intake identity와 그것이 확인하는 `SourceMediaId`
참조를 담는다. codec·duration·audio-stream·provider·model·language·path 설정을 담지 않는다.

**Idempotency (Confirmed, S-8):** 동일한 Source Media의 반복 admission은 **기존 canonical intake 기록을 resolve하여
반환**하며(재사용) 중복·충돌 기록을 만들지 않는다. 근접 동시 admission에서도 uniqueness가 유지되고 결과는 idempotent
하게 기존 기록으로 수렴한다.

**Single Canonical Intake (Confirmed, S-9):** 하나의 Source Media는 이 slice에서 **하나의** canonical transcript-intake
기록만 가진다(파생 identity + uniqueness로 강제). 서로 다른 Source Media는 서로 다른 intake 기록을 가진다.

**Provenance (Confirmed, S-10):** intake 기록은 자신이 확인하는 `SourceMediaId` 참조를 담아 Source Media와 이후
transcript 실행 사이의 provenance를 보존한다. `SourceMediaId`는 canonical media identity로 남고 경로는 provenance일 뿐
identity가 아니다.

**Relationship to Transcript Execution (Confirmed, S-11):** intake는 §4.1 Source Intake의 적격성 확인만 수행한다.
ASR 결과·Raw Transcript·Corrected Transcript·Subtitle·승인 상태 등 어떤 transcript 내용이나 실행 결과도 만들지 않는다
(§4.1 "Does Not Produce"와 일관). 이미 어떤 transcript가 그 Source Media에 연관되어 있어도 intake의 적격성·idempotency에
영향을 주지 않는다.

**Failure Atomicity (Confirmed, S-12):** malformed identity·missing Source Media·persistence 실패 등 어떤 실패에서도
부분 기록이나 오해를 주는 상태를 남기지 않으며 기존 기록과 Source Media 기록은 보존된다. Source Media 기록은 파일이
이동·삭제되어도 변경되지 않는다.

**Authority (Confirmed, S-13):** intake 기록은 오직 "이 persist된 Source Media가 transcript 입력으로 admit되었다"는
repository·application 사실에만 authoritative하다. media의 디코딩 가능성·audio 존재·transcription 가능성·형식 유효성을
주장하지 않으며, Source Media 기록이나 원본 바이트를 변경하지 않는다. 기존 Transcript identity·execution 계약이
우선한다.

**Deferred (이후 milestone, S-14):** ffmpeg·ffprobe·media probe·duration/codec/resolution/stream 추출·audio-stream
검증·audio 추출·transcode·정규화·waveform/thumbnail·playback·Whisper 등 transcription provider·model 선택·language
감지·transcript 생성·transcript segmentation·background job·queue·retry·progress·원격 media·upload·object storage·
managed media copy·provider/plugin registry·workflow engine·이 Source Media에 대한 다중 transcript-intake·intake에
연결된 실제 transcript 실행. 이들 deferred 개념을 위한 placeholder는 도입하지 않는다.

**Canonical Invariants (Confirmed):** (1) Media Import와 Source Intake는 분리된 단계다. (2) 입력은 canonical
`SourceMediaId`이며 경로가 아니다. (3) 적격성은 persist된 사실만으로 판정되는 repository·application 결정이며 codec·
content 주장이 아니다. (4) admission은 audio·재생·transcription 가능성을 주장하지 않는다. (5) intake는 물리적 파일
존재를 확인하지 않으며 이동·삭제된 원본은 적격성 실패가 아니다. (6) intake identity는 Source Media에서 결정적으로
파생된다(`transcript-source-intake:<source_media_id>`). (7) admission은 durable·immutable·insert-only이며 atomic하게
persist된다. (8) 동일 Source Media 반복 admission은 idempotent(기존 기록 resolve). (9) 하나의 Source Media는 하나의
canonical intake 기록을 가진다. (10) intake는 `SourceMediaId` provenance를 보존한다. (11) intake는 transcript 내용·
실행 결과를 만들지 않는다. (12) 실패는 부분 상태를 남기지 않고 Source Media 기록을 변경하지 않는다. (13) 기존
Transcript·execution 계약이 우선한다. (14) deferred 개념은 placeholder를 도입하지 않는다.

## 14. External ASR Boundary Application Foundation — Provider Transcript Result Admission (First Slice)

이 절은 `PATCH-0021`로 승인된 Architect/Product 결정(A-1…A-15)을 기록한다. **첫 External ASR Boundary
milestone**은 §4.2 External ASR Boundary와 §4.3 Raw Transcript Preservation의 첫 application 실현이다. 이 slice는
이미 admit된 하나의 `TranscriptSourceIntake`(§13, PATCH-0020)와 외부에서 생성된 결정적 provider ASR 결과
문서를 받아, provider 증거를 보존하는 `ProviderTranscriptResult`와 그로부터 파생되는 정확히 하나의 canonical
`RawTranscript`(및 `TranscriptSegment`들)를 만든다. 이 slice는 오직 한 가지 질문에 답한다: "이미 admit된 이 Source
Media intake에 대해 외부에서 생성된 ASR 결과를 어떻게 admit하는가?" — 어떻게 media를 디코딩·audio 추출·provider
선택·설치·모델 다운로드·job 스케줄하는지에는 답하지 않는다. **실제 ASR 엔진을 실행하지 않는다.**

**Scope (Confirmed, A-1):** provider 결과는 외부 실행 boundary가 만든 **검증되지 않은 외부 증거**다(§4.2와 일관).
이 slice는 ffmpeg·ffprobe·media 디코딩·audio 추출·codec/duration/stream 검사·Whisper 등 ASR 엔진·network·model
다운로드·provider 설치·registry를 도입하지 않으며, 이들 deferred 개념의 placeholder도 만들지 않는다. 입력은 provider가
공급한 결과 문서이지 media 파일이 아니다.

**Input (Confirmed, A-2):** 입력은 (1) canonical `TranscriptSourceIntakeId`와 (2) provider-neutral(LectureOS-native)
ASR 결과 문서다. 문서는 provider 참조, 선택적 model, 선택적 declared language, 외부 provider-result 참조,
그리고 순서가 있는 segment 배열(각 segment는 `start`, `end`, `text`)을 담는다. media 경로는 받지 않는다.

**External Execution Provenance (Confirmed, A-3):** External ASR Boundary는 **외부** 실행의 결과를 admit한다. 이
slice는 내부 `ProcessingRun`/`UnitExecution`을 만들지 않고 RUNNING unit execution을 요구하지도 않는다(외부 boundary에
내부 실행 의미를 강요하지 않는다). 대신 admission은 **외부 실행 provenance**를 담는다: 호출자가 안정적인 외부
provider-result 참조를 공급하고, LectureOS는 그로부터 결정적으로 `ProcessingRunId`/`UnitExecutionId`/`DomainResultId`
provenance 마커를 파생한다. 이들은 기존 record의 provenance TEXT 참조이며(내부 실행 row를 강제하는 cross-table
foreign key가 없다), raw transcript의 canonical `DomainResultReference`는 평소와 같이 생성·persist된다.

**Provider Evidence Preservation (Confirmed, A-4):** `ProviderTranscriptResult`는 제출된 provider 증거(provider 참조,
model, declared language, 외부 result 참조, 전체 순서 segment payload)를 canonical하게 직렬화한 `original_content`로
보존하며 **정규화 이전 상태**로 저장한다(`normalized = 0`, 기존 model/schema가 강제). 제출된 provider 증거를 조용히
버리지 않는다.

**Distinct Canonical Transcript (Confirmed, A-5):** canonical `RawTranscript`는 자신의 `TranscriptId`를 가진 **별도**
record다. provider 결과는 `provider_transcript_result_id` provenance로 참조되며 Transcript의 identity가 되지 않는다
(§4.2 "provider 결과에서 분리된 내부 conceptual identity"). provider payload를 canonical transcript identity와
동일시하지 않는다.

**Deterministic Identity (Confirmed, A-6):** 모든 LectureOS identity는 안정적 anchor
`(intake_id, provider, model, provider_result_ref)`를 SHA-256으로 해시하여 결정적으로 파생된다:
`ProviderTranscriptResult` 하나, 그로부터 정확히 하나의 canonical `RawTranscript`(1:1 projection), 제출 segment마다
하나의 `TranscriptSegment`(ordinal = 제출 순서), 그리고 intake→provider 결과→raw transcript를 잇는 하나의
**Provider Transcript Admission** record. 어떤 semantic identity에도 wall-clock 시간이나 randomness가 관여하지 않는다.

**Multiple Provider Results per Intake (Confirmed, A-7):** 하나의 intake는 여러 provider 결과를 받을 수 있다(서로
다른 provider/model/execution은 서로 다른 anchor를 만든다). 이는 reprocessing(§10.1 "새 ASR 결과는 새 Raw Transcript
provenance와 연결")과 일관된다. 다만 하나의 provider 결과는 정확히 하나의 canonical Raw Transcript만 만든다.

**Idempotency (Confirmed, A-8):** admission은 **내용 기준으로 idempotent**하다. Provider Transcript Admission은 전체
canonical admission payload(모든 segment의 timing과 정확한 text 포함)에 대한 SHA-256 `content_fingerprint`를 저장한다.
동일한 논리적 결과(같은 anchor, 동일 payload)의 재admission은 기존 record를 resolve하여 반환한다(`created = false`).

**Conflict (Confirmed, A-9):** **같은 anchor에 다른 payload**를 admit하면 **conflict**이며 변경 없이 거부된다.
LectureOS는 admit된 provider 결과나 raw transcript를 조용히 덮어쓰지 않는다(§2 Raw Before Corrected; §10.1 "기존 Raw
Transcript를 덮어쓰지 않는다").

**Timing Semantics (Confirmed, A-10):** segment는 `start`·`end`를 **초(seconds)** 단위 finite 값으로 가지며
`start >= 0`, `end > start`(zero-length span 거부)이고 Source Media에서 파생된 결정적 source timeline
(`source-timeline:<source_media_id>`)에 정렬된다. segment는 `start` 비내림차순으로 제출되어야 하고 겹치지 않아야 한다
(`segment[i].end <= segment[i+1].start`; 경계가 맞닿는 것은 허용).

**Text Semantics (Confirmed, A-11):** segment text는 필수이며 공백만으로 이루어질 수 없고 제출된 그대로 **정확히
보존**된다(trim·정규화·재배치 없음). 비ASCII/한국어 text는 그대로 보존된다.

**Empty Result Policy (Confirmed, A-12):** segment가 0개인 **빈** provider 결과는 거부된다 — 빈 raw transcript는 ASR
실패를 숨긴다(§9.6 "실패를 빈 텍스트… 정상 교정으로 해석하지 않는다").

**Failure Atomicity (Confirmed, A-13):** 어떤 실패(malformed intake identity·unknown intake·malformed/empty/
unordered/overlapping/zero-length segment·blank provider metadata·conflict·persistence 실패)에서도 provider 결과·
segment·raw transcript·admission의 **부분 상태**를 남기지 않으며 Source Media·intake record를 변경하지 않는다.

**Authority (Confirmed, A-14):** admission record는 오직 "이 외부 provider 결과가 이 intake에 대해 admit되어 이 raw
transcript를 만들었다"는 repository·application 사실에만 authoritative하다. ASR 정확성·완전성·audio 내용·media
디코딩 가능성을 주장하지 않으며 media 파일을 읽지 않는다. 기존 Transcript identity·execution 계약이 우선한다.

**Deferred (이후 milestone, A-15):** ffmpeg·ffprobe·media 디코딩·audio 추출·codec/duration/stream 검사·Whisper/
faster-whisper/whisper.cpp/cloud ASR·model 다운로드/선택·GPU/device 선택·credentials·provider 설치·provider/plugin
registry·background job·queue·retry·progress·cancellation·streaming·diarization·speaker 식별·word/token 단위
timestamp·confidence 기반 교정·language **감지**(declared passthrough language만 허용)·correction 후보·corrected
revision·raw transcript의 structural validation·review·subtitle/export 변경. 이들 deferred 개념의 placeholder는
도입하지 않는다.

**Canonical Invariants (Confirmed):** (1) provider 결과는 검증되지 않은 외부 증거이며 media 파일을 읽지 않는다.
(2) 입력은 `TranscriptSourceIntakeId` + provider-neutral 결과 문서이며 media 경로가 아니다. (3) admission은 외부 실행
provenance를 담으며 내부 RUNNING execution을 요구하지 않는다. (4) provider 증거는 정규화 이전 상태로 보존된다.
(5) canonical Raw Transcript는 provider 결과와 별개의 identity를 가진다. (6) 모든 identity는 anchor에서 결정적으로
파생된다. (7) 하나의 intake는 여러 provider 결과를, 하나의 provider 결과는 하나의 canonical Raw Transcript를 가진다.
(8) admission은 content_fingerprint로 idempotent하다. (9) 같은 anchor·다른 payload는 conflict로 거부된다. (10) timing은
초 단위이며 `end > start`, 비겹침, 비내림차순이다. (11) text는 정확히 보존되고 빈 결과는 거부된다. (12) 실패는 부분
상태를 남기지 않고 Source Media·intake를 변경하지 않는다. (13) 기존 Transcript·execution 계약이 우선한다. (14) deferred
개념의 placeholder는 도입하지 않는다.

## 15. First Concrete Local ASR Execution Adapter — faster-whisper (First Slice)

이 절은 `PATCH-0022`로 승인된 Architect/Product 결정(L-1…L-14)을 기록한다. **첫 concrete local ASR execution
adapter**는 §4.2 External ASR Boundary의 첫 구체 provider 실현이며, §14의 provider-neutral admission 경계(PATCH-0021)를
**변경 없이** 그대로 사용한다. 이 slice는 하나의 로컬 엔진(`faster-whisper`)을 실행하여 그 출력을 기존
`ProviderTranscriptDocument`로 변환하고 기존 admission service에 넘겨 canonical Raw Transcript를 만든다. 이 slice는
하나의 concrete adapter를 도입할 뿐 provider framework를 만들지 않는다. **스키마를 바꾸지 않는다(v32 유지).**

**Authoritative Boundary (Confirmed, L-1):** §14 admission service가 Provider Transcript Result·Raw Transcript
상태의 **유일한 쓰기 경로**다. adapter는 상류 실행자일 뿐이며 Raw Transcript row를 직접 쓰지 않고, 엔진에 맞추려
provider-result·Raw Transcript 의미를 바꾸지 않으며, admission service를 우회하지 않는다.

**Selected Engine (Confirmed, L-2):** `faster-whisper`(CTranslate2 Whisper 구현). 로컬 실행, cloud credential 불필요,
안정적 timestamp segment, CPU 실행 가능(GPU 선택), 제한된 pip 의존성, 실제 model 없이 injected factory로 테스트 가능,
media를 내부에서 디코딩(별도 ffmpeg 단계 불필요). 라이브러리는 **지연 import**되어 core 패키지·테스트는 미설치
상태에서도 동작하며 부재는 명시적 operational error다.

**Operational Source Resolution (Confirmed, L-3):** 실행 시 persist된 `SourceMedia.observed_source_path`(reference in
place)를 resolve한다. 경로는 읽을 수 있는 regular file로 존재해야 하며(확정된 Media Import symlink 정책 적용: symlink는
regular-file 대상으로 resolve), 현재 바이트를 저장된 content fingerprint와 **재검증**한다(streaming, bounded memory).
re-import·re-hash-into-new-identity를 하지 않고 record를 변경하지 않으며 `SourceMediaId`를 바꾸지 않는다.

**Changed Bytes (Confirmed, L-4):** 없거나 읽을 수 없거나 디렉터리이거나 비어 있는 source는
`LocalAsrSourceUnavailableError`다. 바이트가 바뀐 경우는 별개의 `LocalAsrSourceChangedError`이며 operator에게 바뀐
파일을 **새 Source Media 기록으로 import**하도록 안내한다. LectureOS는 옛 identity로 바뀐 바이트를 조용히 전사하지
않는다. 물리적 파일 부재는 실행 실패이지 저장소 손상이 아니다(045 §1 M-11, 040 §13 S-5와 일관).

**Media Preparation (Confirmed, L-5):** 이 slice에서는 **없음**. faster-whisper가 source를 내부에서 디코딩하므로
대칭성만을 위해 ffmpeg 단계를 추가하지 않는다. 이후 엔진이 준비를 요구하면 shell 없는(argument-array) bounded runner로
격리된 임시 workspace에만 쓰고 성공·실패 모두 정리하며 원본을 덮어쓰지 않고, 확정 계약이 없는 한 추출 audio를
Artifact로 persist하지 않는다.

**Execution Metadata (Confirmed, L-6):** provider/model 메타데이터는 사실대로다: `provider = "faster-whisper"`,
`model`은 operator가 지정한 식별자. 반환된 segment는 순서·시간·text를 그대로 보존하고, 사용/감지 언어는 사실대로
기록한다.

**Provider-Result Reference (Confirmed, L-7):** provider-result reference는 **결정적**이다 —
`local-asr:model=<model>:lang=<language-or-auto>:media=<source_media_id>` — 즉 semantic request(model, 요청 language,
source content identity)를 인코딩한다. device·compute-type은 operational 성능 설정이며 semantic identity가 아니므로
reference에서 제외한다. 어떤 semantic identity에도 wall-clock·randomness가 관여하지 않는다.

**Replay (Confirmed, L-8):** admission identity가 anchor에서 결정적이므로 adapter는 **엔진을 실행하기 전에** 이미
admit된 동등 결과가 있는지 확인하고 있으면 **재실행 없이 재사용**한다(일반적 ASR 비결정성으로 인한 conflict를 회피).
서로 다른 model/language/source는 서로 다른 admission을 만든다.

**Conflict (Confirmed, L-9):** 같은 anchor에 대한 상충 결과는 결코 덮어쓰지 않는다(§14 A-9와 일관). reuse-before-rerun
때문에 이 adapter를 통해서는 자연히 conflict가 발생하지 않는다.

**Failure Atomicity (Confirmed, L-10):** 외부 ASR 작업은 롤백할 수 없으나 adapter는 **유효한 엔진 결과가 admit되기
전에는 저장소에 아무것도 쓰지 않는다**. 어떤 실패(malformed/unknown intake·source unavailable/changed·dependency/model
부재·engine 실패·inadmissible output)에서도 Provider Transcript Result·segment·Raw Transcript·admission 상태를 남기지
않으며 Source Media·intake 기록을 바꾸지 않는다. admission 원자성은 기존 admission service가 소유한다.

**Replaceability (Confirmed, L-11):** adapter는 변경되지 않은 provider-neutral 경계(§14)에서 종료하므로 엔진은
admission 계약을 바꾸지 않고 교체 가능하다. 이 slice는 provider registry·plugin discovery·generic provider SDK를
만들지 않는다.

**Dependency Isolation (Confirmed, L-12):** 선택 엔진 의존성은 optional이며 지연 import로 격리된다. core 패키지와
테스트는 의존성 미설치 상태에서도 import·실행된다.

**No Schema Change (Confirmed, L-13):** 이 slice는 durable 실행 사실을 위한 새 table을 만들지 않는다. v32 admission
구조를 그대로 재사용하며 `SQLITE_SCHEMA_VERSION`은 32로 유지된다.

**Deferred (이후 milestone, L-14):** 다른 엔진/provider·provider registry·plugin discovery·cloud ASR·credential
관리·model downloader/catalog·GPU 강제·background job·durable queue·retry scheduler·progress·cancellation·streaming/
microphone·diarization·speaker 식별·word/token timestamp·confidence rewriting·자동 correction·translation·subtitle/
NLE/rendering 변경·managed media storage·영구 추출-audio 저장·일반화된 ffmpeg framework. 이들 deferred 개념의
placeholder는 도입하지 않는다.

**Canonical Invariants (Confirmed):** (1) §14 admission service가 유일한 쓰기 경로다. (2) 하나의 concrete 엔진
(faster-whisper)만 통합하며 framework를 만들지 않는다. (3) source는 실행 시 존재·regular-file·fingerprint 재검증된다.
(4) 바뀐 바이트는 옛 identity로 전사되지 않고 새 import를 요구한다. (5) `SourceMediaId`·record는 변경되지 않는다.
(6) provider-result reference와 identity는 결정적이며 device/compute·wall-clock을 제외한다. (7) 엔진 실행 전에
재사용을 확인한다. (8) admit 전에는 저장소에 아무것도 쓰지 않는다. (9) 엔진 의존성은 optional·격리된다. (10) 스키마
변경 없음. (11) 엔진은 admission 계약을 바꾸지 않고 교체 가능하다. (12) deferred 개념의 placeholder는 없다.

## 16. Current Raw Transcript Selection and Downstream Readiness (First Slice)

이 절은 `PATCH-0023`으로 승인된 Architect/Product 결정(R-1…R-13)을 기록한다. External Provider Transcript
Admission(§14)과 첫 local ASR adapter(§15) 이후 하나의 `TranscriptSourceIntake`는 여러 admitted `RawTranscript`를
가질 수 있다. 이 slice는 두 질문에 답한다: "이 intake의 여러 Raw Transcript 중 **어느 것이 downstream 작업의 현재
authoritative 입력인가?**" 그리고 "이 intake는 downstream **Correction을 시작할 준비가 되었는가?**" — 어느 transcript가
가장 정확한지·어느 model이 나은지·text가 언어적으로 맞는지·timing 품질·review 완료·subtitle/export 여부에는 답하지
않는다. **Correction·Validation·Review·Subtitle·Export를 구현하지 않는다.**

**Selection Authority (Confirmed, R-1):** selection은 명시적 Product·repository authority 결정이다. provider 이름·
model 크기·최근 wall-clock·transcript 길이·confidence로 **추론하지 않으며** 어떤 후보도 "best"로 표시하지 않는다.
후보 열거는 결정적이다(Raw Transcript identity 오름차순) — provider/model provenance 메타데이터만 담고 ranking은
담지 않는다. intake의 후보는 정확히 그 admitted Raw Transcript들(`provider_transcript_admissions`)이다.

**Explicit Initial Selection (Confirmed, R-2):** selection은 **항상 명시적**이다(후보가 하나여도). Provider
Transcript Admission은 변경되지 않으며(admit이 자동 선택하지 않는다) authority는 단순 존재로 암시되지 않는다.
readiness는 명시적 선택 전까지 `not_ready`다: 0개 → not_ready; 1개 → 선택 전 not_ready, 선택 후 ready; 2개+ → 정확히
하나의 명시적 current 선택 필요.

**Append-only Supersession (Confirmed, R-3):** history는 **append-only**다(저장소의 확립된 authority-change idiom).
각 selection은 intake별 `sequence`(0-based)를 가진 immutable record이며 `previous_selection_id`로 이전 current를
supersede한다. **current**는 그 intake의 최고 `sequence` record다(ordering은 sequence이며 wall-clock이 아니다).

**Switching (Confirmed, R-4):** 전환은 새 record(`sequence`+1)를 만들고 **모든 이전 record를 보존**한다 — 전환은
어떤 transcript나 이전 selection도 삭제·변경하지 않는다.

**Idempotency (Confirmed, R-5):** 이미 current인 Raw Transcript를 선택하면 **idempotent**(새 record 없음)다. 근접
동시 중복은 기존 current로 수렴한다.

**Deterministic Identity (Confirmed, R-6):** selection identity는 intake·선택 Raw Transcript·sequence에서 결정적으로
파생된다(`raw-transcript-selection:<sha256(intake, raw_transcript, sequence)>`). 어떤 identity에도 wall-clock·
randomness가 관여하지 않는다.

**Readiness (Confirmed, R-7):** readiness는 현재 persist된 사실에서 **파생**되며(자체 persist하지 않음) `not_ready`
(current 없음)·`ready`(정확히 하나의 유효한 current Raw Transcript 선택)·`error`(persist된 current 선택이 비일관 —
예: 그 Raw Transcript가 더 이상 intake의 admitted 후보가 아님) 중 하나다. readiness는 원본 파일 물리 존재·ASR/provider
가용성·model 정확도·confidence·human review에 **의존하지 않는다**.

**No Automatic Staleness (Confirmed, R-8):** 이후 admission은 current 선택을 조용히 무효화·대체하지 않는다. 따라서 새
admission이 current 선택을 stale로 만들지 않으며, 오직 비일관 persist된 선택만 `error`가 된다.

**Explicit Rejection (Confirmed, R-9):** malformed intake·Raw Transcript identity, unknown intake·Raw Transcript,
**다른** intake에 속한 Raw Transcript는 모두 명시적으로 거부된다.

**Failure Atomicity (Confirmed, R-10):** append는 하나의 atomic transaction이다. 어떤 실패에서도 부분 선택 상태를
남기지 않으며 transcript·provider result·Source Media·intake를 변경하지 않는다. human `reason`은 선택적이다.

**Downstream Authority (Confirmed, R-11):** downstream Correction은 intake당 정확히 하나의 current Raw Transcript를
본다. selection은 ASR 품질을 비교하거나 Raw Transcript 내용을 바꾸거나 Correction을 실행하지 않는다.

**No Content Mutation (Confirmed, R-12):** selection은 Raw Transcript 내용을 결코 바꾸지 않는다. 비선택 transcript도
삭제·변경되지 않는다. 기존 Provider Transcript Admission·Raw Transcript identity·§4.8 corrected 현재 선택은 변경되지
않는다.

**Deferred (이후 milestone, R-13):** transcript correction·correction 후보·문법/구두점 교정·structural transcript
validation·human review·자동 transcript scoring·ASR confidence ranking·model/provider ranking·자동 best-transcript
선택·transcript merging/ensemble·word-level alignment·diarization·subtitle/export/rendering 변경·queue·retry·
progress·cloud ASR·추가 local ASR adapter·provider registry·일반 workflow status engine. placeholder는 도입하지 않는다.

**Canonical Invariants (Confirmed):** (1) 후보는 intake의 admitted Raw Transcript이며 결코 자동 ranking되지 않는다.
(2) selection은 항상 명시적이고 admission은 변경되지 않는다. (3) history는 append-only이며 current는 최고 sequence다.
(4) 전환은 이전 record를 보존한다. (5) 동일 선택 반복은 idempotent다. (6) identity는 결정적(intake·transcript·
sequence)이다. (7) intake당 current는 최대 하나다. (8) readiness는 유효한 current 선택에서만 파생된다. (9) 이후
admission은 current를 조용히 대체하지 않는다. (10) malformed·unknown·unrelated·dangling은 명시적으로 거부된다.
(11) 실패는 부분 상태를 남기지 않고 상위 record를 변경하지 않는다. (12) transcript 내용은 변경되지 않는다.
(13) deferred 개념의 placeholder는 없다.

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
