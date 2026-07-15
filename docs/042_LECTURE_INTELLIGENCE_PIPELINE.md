# 042_LECTURE_INTELLIGENCE_PIPELINE

- Status: Draft
- Version: Blueprint 0.1
- Last Updated: 2026-07-15
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
  - `041_SUBTITLE_PIPELINE.md`
- Referenced By:
  - `043_REVIEW_PIPELINE.md`
  - `044_EXPORT_PIPELINE.md`

## Purpose

이 문서는 Source Timeline에 맞춰진 강의 기록에서 설명 가능한 강의 이해를 도출하는 Lecture Intelligence Pipeline을 정의한다. LectureOS에서 lecture intelligence는 강의의 구조, 전달, 시간적 흐름과 교육적 맥락에 관한 분석을 준비하고, 사람이 검토할 수 있는 Lecture Segment, Analysis Finding과 Edit Candidate로 표현하는 책임이다.

이 Pipeline은 강의를 분석하지만 편집하지 않는다. Source Media, Transcript, Subtitle 또는 Artifact를 변경하지 않으며, Edit Candidate를 사용자 결정이나 실제 컷으로 취급하지 않는다. 분석 방법, provider, 기술 스택과 실행 구조는 정의하지 않는다.

## 1. Pipeline Scope

### Included

- 분석에 사용할 수 있는 upstream 기록의 적격성 확인
- Source Media와 Source Timeline에 대한 추적
- 선택적 Transcript, Subtitle, 화자 정보와 강의 맥락의 활용
- 강의 구조와 의미 있는 신호의 분석
- Lecture Segment와 Segment Label 후보
- Analysis Finding
- Edit Candidate
- 분석 결과와 후보의 explainability
- 구조적 Validation
- provenance와 analysis revision
- Review Pipeline으로의 후보와 근거 전달
- 재처리와 실패·Uncertainty 노출

### Excluded

- Source Media ingestion과 원본 변경
- Raw Transcript와 Corrected Transcript 생성 또는 교정 결정
- Subtitle 작성과 Final Subtitle 확정
- Edit Candidate의 Accept, Reject, Modify 결정
- Approved Edit Decision 생성과 관리
- 실제 영상 편집, 컷 적용과 렌더링
- Artifact 생성과 export packaging
- 외부 시스템으로의 전달
- FCPXML과 외부 편집 round trip
- 고정된 분석 taxonomy와 provider 선정

Lecture Intelligence Pipeline은 Edit Pipeline의 분석 계층이다. upstream 결과를 참조하고 downstream Review를 위한 분석과 후보를 만들 수 있지만 `040`, `041`, `043`, `044`의 책임을 흡수하지 않는다.

## 2. Pipeline Principles

1. **Concept Before Component:** Source Media, Lecture Segment, Analysis Finding, Edit Candidate와 Review Decision의 의미를 처리 단계나 구현 구성보다 먼저 정의한다.
2. **Analysis Is Not Editing:** 분석은 강의에서 관찰되거나 해석된 내용을 설명하고 제안할 수 있지만 미디어나 승인된 기록을 변경하지 않는다.
3. **Lecture Segment Is Not Edit Candidate:** Lecture Segment는 강의의 의미 있는 영역이고 Edit Candidate는 가능한 편집 처리를 제안하는 별도 개념이다.
4. **Candidate Is Not Decision:** Edit Candidate는 Review 가능한 제안이며 Approved Edit Decision이나 자동 실행 명령이 아니다.
5. **Validation Is Not Meaning:** Validation은 완전성, 추적성, 일관성과 처리 가능성을 확인하지만 교육적 정확성이나 편집 적절성을 확정하지 않는다.
6. **Decision Is Not Artifact:** 사용자 결정과 그 결정에서 만들어질 외부 Artifact는 서로 다른 책임이다.
7. **Source Timeline Traceability:** 모든 시간 기반 분석 결과는 Source Timeline으로 돌아갈 수 있어야 한다.
8. **Human Authority:** 시스템은 탐지, 분류, 설명, 우선순위화와 추천을 할 수 있지만 최종 교육적·편집적 판단은 사용자에게 있다.
9. **Explainable Results:** 의미 있는 분석 결과와 후보는 검토 가능한 근거, 이유와 Uncertainty를 제공해야 한다.
10. **Provider Independence:** provider 고유 분류나 식별자를 LectureOS의 canonical concept로 사용하지 않는다.
11. **Safe Reprocessing:** 재분석은 새 결과와 후보를 만들 수 있지만 기존 Review 이력과 사용자 결정을 암묵적으로 변경하지 않는다.
12. **Conservative Educational Judgment:** 교육적 가치가 불명확한 구간은 확정적 제거보다 유지 또는 Review를 우선한다.

## 3. Core Concepts

### 3.1 Eligible Analysis Input

Eligible Analysis Input은 Lecture Intelligence가 사용할 수 있는 Source Media 기반 기록과 명시적으로 허용된 맥락이다. 모든 입력이 필수이거나 항상 존재한다고 가정하지 않는다.

입력의 출처, 적용 범위, Validation 상태와 Uncertainty가 분석 결과에 이어져야 한다. 사용할 수 없거나 불완전한 입력은 분석 범위와 confidence를 제한할 수 있으며, 없는 정보를 확정된 사실로 보완하지 않는다.

### 3.2 Analysis

Analysis는 적격한 입력에서 강의의 구조, 조건, 패턴과 관계를 해석하는 최상위 활동이다. 시간 범위에 정렬된 결과뿐 아니라 강의 전반이나 기록 사이의 관계에 관한 결과도 만들 수 있다.

Analysis는 Lecture Segment, Analysis Finding 또는 Edit Candidate를 필요에 따라 준비할 수 있다. 모든 Analysis가 Lecture Segment를 만들거나 Segment를 거쳐야 하는 것은 아니다.

### 3.3 Lecture Segment

Lecture Segment는 Source Timeline의 Time Range와 연결된 강의의 의미적 또는 기능적 영역이다. 주제, 설명, 예시, 전환, 질문, 멈춤, 반복 또는 다른 분석 관점을 표현할 수 있지만 그 자체로 문제나 편집 추천은 아니다.

Lecture Segment는 `030_DATA_MODEL.md`의 대표 용어를 따른다. Transcript Unit, Subtitle Unit, 외부 편집 도구의 구간 또는 실제 컷과 동일하지 않다.

Lecture Segment는 Analysis 결과를 시간축상의 의미 있는 영역으로 구조화하는 하나의 표현이다. Lecture Intelligence 전체의 중심 객체나 모든 Finding의 필수 전제가 아니다.

### 3.4 Segment Label

Segment Label은 Lecture Segment의 분석적 성격을 설명하는 분류 후보다. label은 분석 관점을 전달할 수 있지만 삭제 명령, 교육적 가치의 확정, Review Decision 또는 편집 동작이 아니다.

현재 분석 범주는 `020_PRODUCT_REQUIREMENTS.md`가 소유한다. 그 범주는 Current Product Requirements의 최소 기반이지 영구적으로 닫힌 taxonomy가 아니다.

### 3.5 Analysis Finding

Analysis Finding은 적격한 입력에서 도출된 설명적 또는 해석적 분석 결과다. 무엇이 식별되었는지, 적용 가능한 경우 어디에서 식별되었는지, 어떤 근거가 이를 뒷받침하는지, 어떤 제한과 Uncertainty가 있는지를 Review 가능한 형태로 연결한다.

Finding은 관찰, 패턴, 관계 또는 해석을 표현할 수 있다. Audio Quality, Background Noise, Speaker Overlap 또는 Confidence Degradation처럼 Lecture Segment 없이도 설명 가능한 Finding이 있을 수 있다. 모든 Finding이 문제이거나 Edit Candidate를 만들어야 하는 것은 아니다.

### 3.6 Edit Candidate

Edit Candidate는 Analysis Finding을 근거로 제안할 수 있는 선택적 편집 후보다. 영향을 받는 Source Timeline 영역, 편집상 우려나 기회, 추천 이유, Uncertainty와 제안된 처리 의도를 사람이 검토할 수 있게 한다.

Edit Candidate는 Approved Edit Decision, 외부 편집 명령 또는 실제 컷이 아니다. Candidate가 actionable한 사용자 결정으로 발전하는 책임은 Review Pipeline에 있다.

### 3.7 Review Decision and Artifact

Review Decision은 Edit Candidate에 대한 사용자의 Accept, Reject 또는 Modify 판단이다. Lecture Intelligence Pipeline은 Review Decision을 만들거나 적용하지 않으며, 기존 결정과 새 분석 결과의 관계를 모호하게 만들지 않을 책임만 가진다.

Artifact는 승인된 결과를 외부에서 사용할 수 있게 만든 파생 표현이다. Analysis Finding, Edit Candidate와 Review Decision 중 어느 것도 그 자체로 Artifact가 아니다.

## 4. Conceptual Relationships

~~~text
Source Media + Source Timeline
        |
        +----> eligible Transcript / Subtitle / context references
        |
        v
Lecture Analysis
        |
        +----> Lecture Segment ----> Segment Label candidate
        |
        +----> Analysis Finding
        |             |
        |             +----> optional Lecture Segment relationship
        |             |
        |             +----> no Edit Candidate
        |             |
        |             +----> one or more Edit Candidates
        |
        +----> other analysis representations

Lecture Segment / Analysis Finding / Edit Candidate
        |
        v
Review Pipeline handoff
        |
        v
Human Review Decision
        |
        v
Approved Edit Decision
        |
        v
Export Pipeline / Artifact
~~~

이 그림은 개념 관계를 보여주며 구현 단계, 호출 순서 또는 데이터 소유권을 뜻하지 않는다. Lecture Intelligence Pipeline의 책임은 Review Pipeline handoff에서 끝난다.

관계는 다음 원칙을 따른다.

- 하나의 Lecture Segment는 Edit Candidate를 만들지 않거나, 하나 또는 여러 Candidate의 근거가 될 수 있다.
- 하나의 Edit Candidate는 Segment 일부, 여러 Segment 또는 Segment 사이의 관계를 참조할 수 있다. Current Product Requirements에서 지원할 정확한 관계 범위는 Requires Validation이다.
- 하나의 Analysis Finding은 Lecture Segment 없이 존재할 수 있고, Candidate 없이 강의 이해만 제공할 수도 있다.
- 여러 Finding이 하나의 Candidate를 뒷받침할 수 있고 하나의 Finding이 여러 Candidate와 관련될 수 있다.
- Review Decision은 Candidate를 판단하지만 과거 Analysis Finding을 다시 쓰지 않는다.
- Artifact는 Approved Edit Decision에서 파생되며 Analysis Finding이나 Candidate에서 직접 생성되는 승인 결과가 아니다.

Responsibility ownership과 data ownership은 동일하지 않다. Lecture Intelligence Pipeline은 분석 결과를 준비하는 논리 책임을 가지지만 Source Media, upstream Transcript·Subtitle, 사용자 결정 또는 Artifact의 Conceptual Identity를 소유하지 않는다.

## 5. Input Eligibility

Lecture Intelligence는 다음 upstream 기록을 필요한 범위에서 사용할 수 있다.

- **Source Media identity and Source Timeline:** 모든 시간 기반 분석의 최상위 물리적 근거다.
- **Corrected Transcript:** 발화 의미와 Transcript Unit의 시간 연결을 분석 맥락으로 사용할 수 있다.
- **Transcript timing and Uncertainty:** 분석 범위와 근거의 신뢰 한계를 설명하는 데 사용할 수 있다.
- **Speaker Information:** upstream에서 제공되고 검증된 경우 선택적 신호로 사용할 수 있다.
- **Subtitle records:** 표시 표현이나 시청 흐름과 관련된 분석에 필요한 경우 선택적으로 참조할 수 있다.
- **Project Context and lecture metadata:** 명시적으로 제공된 강의 맥락, 용어와 처리 조건을 분석 보조 근거로 사용할 수 있다.
- **Explicitly permitted contextual information:** 제품 경계와 개인정보 정책 안에서 허용된 추가 맥락을 사용할 수 있다.

입력 적격성은 다음을 보장해야 한다.

- Corrected Transcript를 사용하는 경우 `040_TRANSCRIPT_PIPELINE.md`의 Validation을 우회하지 않는다.
- Subtitle을 사용하는 경우 `041_SUBTITLE_PIPELINE.md`의 책임과 provenance를 다시 정의하지 않는다.
- Speaker Information이나 Subtitle이 항상 존재한다고 가정하지 않는다.
- 입력의 Failure, 누락과 Uncertainty가 영향을 주는 분석 범위를 식별할 수 있어야 한다.
- provider가 반환한 원본 결과를 검증 없이 LectureOS Analysis Finding으로 취급하지 않는다.
- 허용되지 않은 외부 맥락을 분석 편의를 이유로 암묵적으로 사용하지 않는다.

## 6. Lecture Understanding

Lecture understanding은 강의의 내용과 전달 흐름에서 Review에 유용한 구조, 조건, 패턴과 관계를 식별하는 분석 책임이다.

분석은 다음과 같은 관점을 포함할 수 있다.

- 주제 진행과 전환
- 설명, 예시, 질문과 요약
- 교육적 강조와 중요한 반복
- 멈춤, 침묵, 망설임과 다시 말하기
- 수업 전후, 쉬는 시간과 비수업 구간
- 잡담, 장비 문제와 진행 대기
- 가능한 말실수, 연속성 문제와 전달상 문제
- 교육적 가치가 불명확하거나 Review가 필요한 영역

이 목록은 lecture intelligence의 확장 가능한 개념 경계를 설명하는 예시다. 모든 구현이 모든 관점을 지원해야 한다는 뜻이 아니며, 영구 taxonomy를 확정하지 않는다.

다만 `020_PRODUCT_REQUIREMENTS.md`의 현재 Must 범주는 Current Product Requirements의 최소 요구사항으로 유지한다. 강의 구조 분석은 그 범주를 자동 삭제 규칙으로 바꾸거나, 반복 설명·교사의 개성·교육적 예시를 낮은 가치로 확정하지 않는다.

## 7. Lecture Segmentation

Lecture Segmentation은 Analysis 결과를 Source Timeline의 의미 있는 영역으로 구조화할 필요가 있을 때 사용하는 책임이다. 의미, 시간, 화자, 전달 방식, 구조와 허용된 맥락 신호를 조합할 수 있지만 특정 신호나 provider의 구간 결과를 유일한 기준으로 삼지 않는다.

Lecture Segment는 다음 특성을 가질 수 있다.

- Source Timeline의 Time Range와 추적 가능한 경계
- 의미적 또는 기능적 목적
- 경계를 뒷받침하는 신호와 provenance
- Segment Label 후보
- confidence 또는 Uncertainty
- 관련 Analysis Finding과 Edit Candidate
- 재처리 전후의 revision 관계

하나의 canonical segmentation만 존재한다고 강제하지 않는다. 서로 다른 분석 관점이 별도의 Segment 집합을 제안한다면 각 관점, 근거와 Source Timeline 관계를 구분할 수 있어야 한다.

Segment는 분석 관점에 따라 중첩되거나 계층적일 수 있고 경계가 불확실할 수 있다. 그러나 중첩과 계층을 Current Product Requirements의 확정 기능으로 추가하지 않으며, 구체적인 지원 범위와 Review 표현은 Requires Validation이다.

재처리로 Segment 경계나 label이 바뀔 수 있다. 새 Segment가 이전 Segment를 현재 분석에서 대체하더라도 이전 Segment를 근거로 이루어진 Review Decision과 provenance를 모호하게 만들어서는 안 된다.

## 8. Analysis Findings

Analysis Finding은 다음 의미를 보존해야 한다.

- **Purpose or finding type:** 어떤 분석 관점에서 무엇을 식별했는가?
- **Source reference:** 적용 가능한 경우 어느 Source Media와 Source Timeline 영역에 관한 결과인가?
- **Supporting evidence:** 어떤 허용된 기록, 신호 또는 관계가 해석을 뒷받침하는가?
- **Confidence or Uncertainty:** 결과를 어느 범위까지 신뢰하거나 제한해서 해석해야 하는가?
- **Analysis provenance:** 어떤 입력과 분석 문맥에서 결과가 생성되었는가?
- **Segment relationship:** Lecture Segment와 관련된다면 어떤 Segment 또는 Segment 사이의 관계인가?

Finding은 사실처럼 보이는 문장을 제공하더라도 provider의 분류를 canonical truth로 승격하지 않는다. 해석이 교육적·맥락적으로 불확실하면 그 제한을 명시한다.

Finding은 Lecture Segment나 Edit Candidate 없이도 유효한 강의 이해가 될 수 있다. 예를 들어 주제 전환이나 교육적 강조를 식별한 결과는 Segment와 연결될 수 있지만, 전체 녹음의 Audio Quality나 Background Noise에 관한 Finding은 Segment 없이 존재할 수 있다.

## 9. Edit Candidates

Edit Candidate는 Analysis Finding에서 선택적으로 도출되는 평가적 제안이다. Candidate는 다음 질문에 답할 수 있어야 한다.

- 영향을 받는 Source Timeline 영역은 어디인가?
- 어떤 Analysis Finding이 근거이며, Lecture Segment와 관련된다면 어떤 관계인가?
- 어떤 편집상 우려 또는 기회가 제안되는가?
- 추천 이유와 검토 가능한 증거는 무엇인가?
- confidence 또는 Uncertainty와 제한은 무엇인가?
- 제안된 처리 의도가 있다면 무엇인가?
- 현재 후보가 어떤 분석 문맥에서 생성되었는가?

Current Product Requirements에 따라 Edit Candidate는 원본 Time Range, Segment Label, 유지·삭제·검토 추천, confidence 또는 Uncertainty, 추천 이유, 예상 절감 시간과 Review 상태를 연결할 수 있어야 한다.

향후 Candidate 목적은 shortening, emphasis, clarification need, correction need, reordering proposal, transcript·subtitle review request 또는 media review request와 같은 편집상 관심을 표현할 수 있다. 이는 개념 확장 가능성의 예시이며 Current Product Requirements를 추가하거나 자동 처리 동작을 승인하지 않는다.

Suggested treatment는 비권위적이다. 높은 confidence, 강한 label 또는 예상 절감 시간이 사용자의 Review를 대신하거나 자동 편집을 정당화하지 않는다.

## 10. Explainability Requirements

Explainability는 reviewer가 opaque provider output에만 의존하지 않고 Analysis Finding과 Edit Candidate의 근거를 검토할 수 있게 하는 책임이다. 설명의 구성은 Analysis의 성격과 사용 가능한 evidence에 따라 달라질 수 있다.

의미 있는 Finding과 Candidate의 설명은 적용 가능하고 사용할 수 있는 경우 다음을 포함할 수 있다.

- **Source region:** 관련 Source Media와 Source Timeline의 위치
- **Textual evidence:** 관련성이 있고 사용 가능한 경우 Transcript 또는 Subtitle 기록과 그 Validation 상태
- **Lecture context:** Segment가 있는 경우 관련 Lecture Segment, Segment Label과 주변 구조
- **Detected condition or pattern:** 무엇이 관찰되거나 해석되었는가?
- **Rationale:** 그 관찰이 Finding 또는 Candidate로 이어진 이유는 무엇인가?
- **Uncertainty and limitation:** 어떤 입력 부족, 모호성 또는 분석 한계가 있는가?
- **Analysis origin:** 어떤 분석 문맥과 provider-independent 역할에서 결과가 생성되었는가?
- **Finding-to-candidate relationship:** Candidate가 있는 경우 어떤 Finding이 어떤 제안을 뒷받침하는가?
- **Proposed downstream use:** Review에서 무엇을 확인하거나 판단하도록 제안하는가?

Explainability는 provider 내부의 비공개 추론이나 원문 reasoning을 노출하라는 요구가 아니다. reviewer가 원본 구간, 근거, rationale과 제한을 확인할 수 있는 제품 수준의 설명 가능성을 뜻한다.

설명이 존재한다는 사실은 분석이 정확하거나 편집 제안이 적절하다는 보장이 아니다. confidence는 근거를 대신하지 않으며 설명과 함께 Review 우선순위를 돕는 정보다.

## 11. Human Authority and Review Connection

Lecture Intelligence Pipeline은 Review Pipeline에 Lecture Segment, Analysis Finding, Edit Candidate, Validation Result, Failure와 Uncertainty를 전달할 수 있다.

Review handoff는 다음 조건을 만족해야 한다.

- Review Item이 원래 Finding 또는 Candidate와 Source Media 근거로 돌아갈 수 있어야 한다.
- reviewer가 관련 원본 오디오 또는 영상 구간을 확인할 수 있어야 한다.
- Candidate의 추천, 이유, evidence와 Uncertainty를 함께 검토할 수 있어야 한다.
- 새 분석 결과와 기존 Review Decision 또는 Approved Edit Decision의 관계와 충돌을 드러낼 수 있어야 한다.
- 교육적 가치가 불명확한 후보를 확정 사실이나 자동 삭제 대상으로 표시하지 않아야 한다.

사용자는 Review Pipeline에서 Candidate를 Accept, Reject 또는 Modify한다. Lecture Intelligence Pipeline은 이 동작을 정의하거나 수행하지 않으며 Review UI, 결정 상태 전이, 우선순위 정책 전체와 Approved Edit Decision 생성을 소유하지 않는다.

Accept는 과거 Analysis Finding을 수정하지 않는다. Reject는 Finding이 존재했다는 provenance를 삭제하지 않는다. Modify는 원래 Candidate와 사용자가 승인한 변경 의도 사이의 관계를 보존해야 한다. 구체적인 결정 모델은 `043_REVIEW_PIPELINE.md`의 책임이다.

## 12. Safe Reprocessing

다음 변화는 재분석을 유발할 수 있다.

- Source Media 참조 또는 사용 가능한 시간 근거의 변경
- Corrected Transcript revision 또는 timing의 변경
- 선택적 Subtitle, Speaker Information 또는 Project Context의 변경
- 분석 기준이나 허용된 맥락의 변경
- External AI Provider 역할의 교체
- Validation 기준의 변경
- 이전 Failure의 해소

재분석은 새 Lecture Segment, Analysis Finding 또는 Edit Candidate revision을 만들 수 있다. 새 결과가 현재 사용을 위해 이전 결과를 대체할 수는 있지만 이전 결과의 provenance와 그 결과를 근거로 한 Review 이력은 역사적으로 구분 가능해야 한다.

재처리는 다음 규칙을 따른다.

- 이전 Review Decision과 Approved Edit Decision을 새 Candidate에 자동 적용하지 않는다.
- 기존 결정을 삭제하거나 처음부터 존재하지 않았던 것처럼 만들지 않는다.
- 변경된 Transcript 또는 timing이 Candidate의 근거에 영향을 주면 reconciliation 필요성을 드러낸다.
- 더 이상 현재 입력에 적용되지 않는 Candidate를 stale 또는 재검토 대상으로 식별할 수 있어야 한다.
- reviewer가 어떤 분석 문맥과 Candidate를 근거로 결정을 내렸는지 확인할 수 있어야 한다.
- 새 Finding과 Candidate가 이전 결과를 대체하는 관계를 설명할 수 있어야 한다.
- 영향받지 않은 분석 결과를 유지할 수 있지만 안전한 재사용 조건은 후속 설계에서 검증한다.

재처리 관계는 version 번호, 저장 전략 또는 history 구현을 이 문서에서 확정하지 않는다. 핵심 계약은 분석 provenance와 인간 결정의 권위가 재처리 뒤에도 모호해지지 않는 것이다.

## 13. Validation Strategy

Validation은 Analysis 결과가 downstream에서 해석되고 Review될 수 있는 개념적 조건을 확인한다. 구체적인 검사 절차나 구현 규칙을 정의하지 않는다.

- **Structural Consistency:** Analysis, Lecture Segment, Finding과 Candidate가 서로의 책임을 혼합하지 않고 내부적으로 모순되지 않아야 한다.
- **Traceability:** 시간 기반 결과는 Source Timeline과 연결되고, 그 밖의 결과도 적용 대상과 근거를 설명할 수 있어야 한다.
- **Provenance Integrity:** 입력, 분석 문맥, 결과와 reprocessing 전후의 관계를 구분할 수 있어야 한다.
- **Uncertainty Preservation:** 입력이나 해석의 제한을 확정 사실로 조용히 승격하지 않아야 한다.
- **Provider Normalization:** provider-specific output이 검증 없이 canonical LectureOS concept가 되어서는 안 된다.

구조적으로 유효한 Analysis Finding이나 Edit Candidate도 교육적·편집적으로 틀릴 수 있다. Validation은 의미의 정확성이나 편집 적절성을 인증하지 않으며, 그 판단은 사람의 Review 책임이다.

## 14. Pipeline Boundaries

Lecture Intelligence Pipeline은 다음 책임을 소유하지 않는다.

| Responsibility | Owning Blueprint Area | Boundary Rule |
| --- | --- | --- |
| Source Media ingestion | System intake responsibility | 042는 이미 수용된 Source Media identity와 Source Timeline을 참조한다. |
| Transcript 생성과 correction decision | `040_TRANSCRIPT_PIPELINE.md` | 042는 적격한 Transcript를 분석 맥락으로만 사용하며 수정하지 않는다. |
| Subtitle authoring과 Final Subtitle | `041_SUBTITLE_PIPELINE.md` | 042는 관련 evidence로 참조할 수 있지만 Subtitle revision을 만들거나 승인하지 않는다. |
| Candidate Accept, Reject, Modify | `043_REVIEW_PIPELINE.md` | 042는 근거와 Candidate를 전달하고 사용자 결정을 만들지 않는다. |
| Approved Edit Decision | `043_REVIEW_PIPELINE.md` | 042는 이전 결정을 재처리 관계로 참조할 수 있지만 소유하거나 변경하지 않는다. |
| Artifact rendering과 export packaging | `044_EXPORT_PIPELINE.md` | 042 결과를 직접 승인 Artifact로 만들지 않는다. |
| 외부 시스템 전달 | `044_EXPORT_PIPELINE.md`와 System Context | 042는 전달 형식과 외부 통합을 정의하지 않는다. |
| 실제 미디어 편집과 렌더링 | 외부 NLE | LectureOS의 분석은 실제 컷 적용이 아니다. |

이 책임 분리는 Component ownership이나 물리적 배치를 뜻하지 않는다. 각 Blueprint 영역의 논리적 책임과 Conceptual Identity를 구분한다.

## 15. Invariants

- Analysis Finding과 Edit Candidate는 Source Media를 직접 변경하지 않는다.
- 분석 결과는 Corrected Transcript 또는 Final Subtitle을 직접 변경하지 않는다.
- Lecture Segment는 본질적으로 Edit Candidate가 아니다.
- 모든 Lecture Segment가 Candidate를 만들 필요는 없다.
- Edit Candidate는 Approved Edit Decision이 아니다.
- Human Review Decision은 provider가 생성한 분석보다 높은 작업 권위를 가진다.
- 재처리는 기존 인간 결정과 Review 이력을 조용히 삭제하거나 새 Candidate에 자동 적용하지 않는다.
- 모든 시간 기반 Finding과 Candidate는 Source Timeline으로 추적 가능해야 한다.
- provider-specific output은 canonical LectureOS concept가 아니다.
- Uncertainty가 있는 분석은 확정 사실로 조용히 승격되지 않는다.
- 구조적 Validation은 분석의 교육적 정확성이나 편집 적절성을 인증하지 않는다.
- downstream Review는 과거 Analysis Finding을 다시 쓰지 않고 Candidate를 Accept, Reject 또는 Modify할 수 있어야 한다.
- 분석 provenance는 reprocessing 전후에 구분 가능해야 한다.
- Approved Edit Decision은 Artifact나 실제 컷과 동일하지 않다.
- 높은 confidence가 사람의 편집 권위를 대체하지 않는다.

## 16. Failure and Uncertainty Handling

### 16.1 Ineligible or Incomplete Input

필요한 upstream 기록이 없거나 Validation 상태를 신뢰할 수 없는 경우다. 영향을 받는 분석 범위를 제한하고, 지원되지 않는 해석을 정상 결과처럼 만들지 않는다.

### 16.2 Analysis Failure

적격한 입력에서 사용할 수 있는 Analysis Finding을 만들지 못한 경우다. 영향 범위와 Diagnostic을 노출하고 분석되지 않은 영역을 정상 또는 가치 없는 구간으로 해석하지 않는다.

### 16.3 Invalid Segment or Finding

Lecture Segment 또는 Analysis Finding이 Source Timeline, evidence, provenance나 내부 일관성을 유지하지 못한 경우다. 정상 Candidate의 근거로 사용하지 않고 Failure 또는 Review 필요성을 드러낸다.

### 16.4 Invalid or Ambiguous Candidate

Edit Candidate의 affected region, rationale, supporting Finding 또는 suggested treatment가 불완전하거나 모순되는 경우다. 승인 가능한 결정처럼 전달하지 않고 Uncertainty와 함께 Review 대상으로 구분한다.

### 16.5 Provider Failure

External AI Provider가 실패하거나 불완전하고 사용할 수 없는 결과를 반환한 경우다. provider failure와 LectureOS Analysis Finding을 구분하고, 기존 사용자 결정과 유효한 분석 결과를 손상시키지 않는다.

### 16.6 Failure Propagation

- Failure는 영향을 받는 입력, Lecture Segment, Finding, Candidate와 Source Timeline 영역에 연결되어야 한다.
- 한 분석 관점의 Failure가 독립적으로 유효한 다른 관점의 결과를 근거 없이 폐기해서는 안 된다.
- downstream Review가 필요한 선행 근거를 신뢰할 수 없으면 정상 Candidate로 표시하지 않는다.
- 누락된 분석을 정상 구간, 침묵, 낮은 교육적 가치 또는 삭제 추천으로 해석하지 않는다.
- 부분 성공은 어떤 결과가 유효하고 어떤 결과가 실패했는지 구분해야 한다.

구체적인 오류 분류 체계, 복구 방식과 재시도 정책은 이 문서에서 정의하지 않는다.

## 17. Acceptance Criteria

- [ ] Lecture intelligence가 Source Timeline 기반 강의 이해의 분석 책임으로 정의되어 있다.
- [ ] Lecture Segment, Analysis Finding, Edit Candidate, Review Decision과 Artifact가 구분되어 있다.
- [ ] Lecture Segment가 Edit Candidate 없이 존재하거나 여러 Candidate의 근거가 될 수 있다.
- [ ] Analysis Finding이 모든 경우에 문제나 Candidate로 취급되지 않는다.
- [ ] Edit Candidate가 실제 컷이나 Approved Edit Decision으로 표현되지 않는다.
- [ ] 의미 있는 Finding과 Candidate에 explainability와 provenance 요구가 적용된다.
- [ ] 사람의 Accept, Reject, Modify 권위가 분석 confidence보다 우선한다.
- [ ] provider 고유 분류가 canonical concept가 되지 않는다.
- [ ] 재처리에서 기존 Review 이력과 사용자 결정을 보존한다.
- [ ] stale 또는 reconciliation이 필요한 Candidate를 식별할 수 있어야 한다.
- [ ] 모든 시간 기반 결과가 Source Timeline으로 추적 가능하다.
- [ ] Validation과 교육적·편집적 의미 판단이 분리되어 있다.
- [ ] Transcript, Subtitle, Review와 Export Pipeline의 책임을 침범하지 않는다.
- [ ] 실제 편집, 자동 컷, FCPXML과 외부 편집 round trip을 포함하지 않는다.
- [ ] Failure와 Uncertainty를 정상 결과처럼 숨기지 않는다.

## 18. Assumptions and Open Questions

### Confirmed

- Lecture Intelligence Pipeline은 강의를 분석하지만 Source Media나 승인된 기록을 편집하지 않는다.
- Lecture Segment는 Source Timeline의 의미적 또는 기능적 영역이며 Edit Candidate와 다르다.
- Analysis Finding은 설명적 또는 해석적 결과이고 모든 Finding이 편집 문제는 아니다.
- Edit Candidate는 Review 가능한 제안이며 사용자 결정이나 실제 컷이 아니다.
- 사용자는 Review Pipeline에서 Candidate를 Accept, Reject 또는 Modify한다.
- 시간 기반 분석 결과는 Source Timeline으로 추적 가능해야 한다.
- provider 결과는 LectureOS concept로 정규화되고 검증되기 전에는 canonical truth가 아니다.
- 재처리는 기존 사용자 결정과 Review 이력을 삭제하거나 덮어쓰지 않는다.

### Working Assumption

- 검증된 Corrected Transcript는 강의 분석의 주요 선택적 맥락으로 사용할 수 있다.
- Subtitle, Speaker Information과 추가 Project Context는 특정 분석 목적에 필요한 경우에만 선택적으로 사용한다.
- Analysis Finding을 Lecture Segment 존재 여부와 무관하게 설명적 분석 결과를 표현하는 Pipeline 개념으로 사용한다.

### Requires Validation

- 어떤 분석 관점이 Source Media만으로 가능하고 어떤 관점이 Transcript 또는 Subtitle 맥락을 요구하는가?
- 여러 분석 segmentation view를 Current Product Requirements에서 어느 범위까지 지원할 것인가?
- Lecture Segment의 overlap과 hierarchy를 Review에서 어떻게 구분할 것인가?
- 하나의 Edit Candidate가 여러 Segment 또는 여러 Time Range를 참조할 수 있는 안전 범위는 무엇인가?
- Analysis Finding의 최소 안정적 참조 단위는 무엇인가?
- 어떤 Finding과 Candidate가 반드시 Review Item을 필요로 하는가?
- 기존 Review Decision과 새 Candidate를 reconciliation할 수 있는 안전 조건은 무엇인가?
- stale Candidate의 현재 적용 가능성을 어떤 제품 기준으로 판별할 것인가?
- expected time savings를 어떤 기준과 범위로 추정하고 검증할 것인가?
- 외부 맥락과 개인정보를 Lecture Analysis에 사용할 수 있는 허용 범위는 무엇인가?

### Deferred

- 고정된 Segment Label과 Analysis Finding taxonomy
- segmentation, 분류와 추천 방법
- confidence와 우선순위 계산 기준
- analysis revision과 supersession의 구현 방식
- Review 상태 전이와 Approved Edit Decision 생성 방식
- Artifact, export schema와 외부 NLE 형식
- 자동 컷 적용, FCPXML과 외부 편집 round trip
- 저장, 실행과 통신 방식

## 19. Non-Goals

- 모든 강의 이해 범주를 영구적으로 확정하는 것
- 하나의 canonical Lecture Segmentation을 강제하는 것
- provider 내부 reasoning을 제품 출력으로 요구하는 것
- 교육적 가치와 편집 적절성을 AI가 최종 판정하는 것
- 자동 삭제, 자동 컷 또는 실제 편집을 수행하는 것
- Transcript나 Subtitle의 내용을 교정하거나 승인하는 것
- Review Decision과 Approved Edit Decision을 생성하는 것
- Artifact 또는 외부 편집 형식을 정의하는 것
- 구현 컴포넌트, 저장 구조, API, runtime 또는 기술 스택을 선택하는 것

## 20. Downstream Constraints

### Constraints for `043_REVIEW_PIPELINE.md`

- `043`은 Lecture Segment, Analysis Finding, Edit Candidate와 관련 Failure·Uncertainty를 Review 입력으로 받을 수 있어야 한다.
- `043`은 Analysis 결과와 Candidate를 변경하지 않고 사용자 Review Decision과 Modification을 연결해야 한다.
- Review의 구체적인 상태, 우선순위와 reconciliation 계약은 `043`이 정의한다.

### Constraints for `044_EXPORT_PIPELINE.md`

- `044`는 Review Pipeline이 제공하는 Approved Edit Decision을 승인된 편집 결정 Artifact의 입력으로 사용한다.
- Analysis Finding이나 Edit Candidate는 그 자체로 승인된 export 입력이 아니다.
- Artifact와 외부 전달의 상세 계약은 `044`가 정의한다.

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
- `041_SUBTITLE_PIPELINE.md`
