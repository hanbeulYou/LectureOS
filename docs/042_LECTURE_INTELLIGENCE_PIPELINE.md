# 042_LECTURE_INTELLIGENCE_PIPELINE

- Status: Draft
- Version: Blueprint 0.6
- Last Updated: 2026-07-23
- Amended By: `patches/PATCH-0009-lecture-analysis-input-eligibility.md`, `patches/PATCH-0010-analysis-finding-application-foundation.md`, `patches/PATCH-0011-lecture-segmentation-application-foundation.md`, `patches/PATCH-0012-edit-candidate-application-foundation.md`, `patches/PATCH-0013-concrete-edit-candidate-generation-provider.md`, `patches/PATCH-0030-effective-transcript-analysis-finding-admission-boundary.md`, `patches/PATCH-0031-effective-transcript-lecture-segmentation-admission-boundary.md`, `patches/PATCH-0032-effective-transcript-edit-candidate-admission-boundary.md`
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

### 5.1 First Milestone — Lecture Analysis Input Eligibility (Intake)

이 소절은 `PATCH-0009`로 승인된 Product Owner 결정을 기록한다. Lecture Intelligence Pipeline의 **첫 dependency-ordered milestone**은 **Lecture Analysis Input Eligibility (Intake)**이며, 이후 분석의 validated·durable 근거를 확정하는 것이 유일한 책임이다.

Admission authority (Confirmed): 이 milestone은 **Transcript Pipeline이 선택한 validated Corrected Transcript**를 그 **Source Timeline**과 **Source Media reference**와 함께 admit한다. Corrected Transcript는 `040_TRANSCRIPT_PIPELINE.md`의 Validation을 우회하지 않은 사용 가능한(ready/current-selected) 상태여야 한다(§5). 모든 upstream은 **read-only**로 소비하며 이 milestone은 어떤 upstream 기록도 변경하지 않는다.

Eligible Analysis Input (Confirmed): 이 milestone이 만드는 **Eligible Analysis Input**은 **durable canonical record**로, **immutable**하고 **고유 identity**를 가지며 admit한 Corrected Transcript·Source Timeline·Source Media까지의 **provenance**를 보존한다(`§2.7`, `§12`). 이는 transient 구현 상태가 아니다.

이 milestone의 책임 경계 — 이 milestone은 다음을 **하지 않는다**: Analysis 수행, Analysis Finding 생성, Lecture Segment 생성, Segment Label 생성, Edit Candidate 생성, Review Item 생성 또는 Review 연결, AI reasoning. `§5`에 따라 입력의 Failure·누락·Uncertainty가 영향을 주는 범위만 식별해 이후 분석에 전달한다.

다음은 이 milestone의 범위가 아니며 이후 milestone으로 **deferred**된다(§18): canonical analysis unit, Analysis Finding의 최소 참조 단위, segmentation hierarchy와 overlapping segmentation, multi-range Edit Candidate 참조, Review Item 생성 조건, Source-Media-only 분석, 그리고 optional Subtitle/Speaker/Project Context admission.

#### 5.1.1 Contract Generations of the Durable Analysis Input (Confirmed, PATCH-0030)

`§5.1`이 확정한 **Eligible Analysis Input**의 개념 의미(durable canonical record, immutable, 고유 identity, admit한 Corrected Transcript·Source Timeline·Source Media까지의 provenance 보존)는 변경되지 않는다. 이 소절은 그 durable 역할을 수행하는 canonical record가 **두 개의 contract generation**으로 존재한다는 사실만 기록한다. 이는 `041 §15`가 legacy subtitle candidate generation과 effective-transcript generation을 구분한 선례와 동일한 versioned architecture 경계다.

- **Legacy execution-coupled generation:** `EligibleAnalysisInput` — Transcript Readiness Evaluation에 anchor되고 내부 `ProcessingRun`/`UnitExecution` provenance를 요구하는 최초 구현 세대. 그 역사적 계약과 기록은 **그대로 유효한 역사**로 보존되며 삭제·소급 변경·재해석되지 않는다. 현행 세대에서는 **superseded**다.
- **Effective-transcript generation (현행):** **Lecture Analysis Input Admission** — `040 §20`의 effective transcript authority 위에서 파생 eligibility를 command 시점에 재검증하고, 그 정확한 authority snapshot(intake, Source Media, current applicable corrected revision, parent Raw Transcript, 관측된 raw·corrected selection, `040 §19` content fingerprint, segment count)을 immutable·append-only로 binding하는 canonical record다. `§5.1`이 요구한 durable·immutable·identity-owning·provenance-bearing 성질을 모두 충족한다.

**표기 규약 (Confirmed):** 이 문서에서 띄어 쓴 **Eligible Analysis Input**은 `§5.1`이 정의한 **generation-neutral 개념 역할**을 가리키고, code-font `EligibleAnalysisInput`은 **legacy 세대의 구체적 record 이름**을 가리킨다. 이 구분은 `§8.1`을 포함해 이 문서 전체에 적용된다.

두 세대는 문서상 영구히 구분 가능하며, **하나의 contract generation 안에는 정확히 하나의 canonical durable analysis input record가 존재한다.** 한 세대의 record를 다른 세대의 admission 근거로 교차 사용하지 않는다. 현행 세대의 Analysis Finding admission 경계는 `§8.2`가, Lecture Segmentation admission 경계는 `§7.2`가, Edit Candidate admission 경계는 `§9.3`이 정의한다. 현행 세대의 관계는 다음과 같다: durable analysis input record 아래에 **Analysis Finding과 Lecture Segmentation이 sibling**으로 놓이고, **Edit Candidate는 Analysis Finding에만 anchor**하며 Segmentation을 parent로 사용하지도 참조하지도 않는다(`§9.1` Canonical Anchor). 두 경계는 **같은 종류의 durable analysis input record를 각자 독립적으로 anchor하는 sibling**이며 서로를 전제하지 않는다(`§7.1` Canonical Anchor는 Segment가 Finding에 anchor하지 않음을, `§8.1` Canonical Anchor는 Finding이 Segment 관계를 갖지 않음을 각각 확정한다). 같은 종류라는 것이 **같은 개별 record 인스턴스를 공유해야 한다는 뜻은 아니다** — 어떤 Admission 위에 Segment만 존재하거나 Finding만 존재하는 것도 완전히 유효하다.

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

### 7.1 First Segmentation Milestone — Lecture Segmentation Application Foundation

이 소절은 `PATCH-0011`으로 승인된 Product Owner 결정을 기록한다. Lecture Segmentation의 **첫 dependency-ordered milestone**은 **Lecture Segmentation Application Foundation**이며, `§7`이 정의한 Lecture Segment를 canonical 기록으로 확정하는 것이 책임이다. 이 milestone은 §7의 의미를 다시 정의하지 않고 아래 계약만 확정하며, §7이 "가질 수 있다"로 열거한 그 밖의 특성(Segment Label, confidence/Uncertainty, revision 관계 등)은 확정하지 않고 deferred로 둔다.

**Lecture Segment Record (Confirmed):** Lecture Segment는 **durable canonical domain record**이며 **immutable**, **identity-owning**(Application 소유 identity), **provenance-bearing**, **replay-safe**, **provider-independent**한 **insert-only** 기록이다. lifecycle state를 도입하지 않는다. Eligible Analysis Input(§5.1)과 Analysis Finding(§8.1)의 durable-stage 선례를 그대로 따른다.

**Canonical Anchor (Confirmed):** 모든 Lecture Segment는 **eligibility가 ELIGIBLE인 정확히 하나의 `EligibleAnalysisInput`(§5.1)**에 anchor된다. Segment는 어떤 Analysis Finding에도 anchor되지 않으며 Finding의 존재를 요구하지 않는다(§3.3). Source Timeline과 Source Media는 anchor한 입력을 **통해 상속되는 provenance**이지 직접 anchor 대상이 아니다. 하나의 `EligibleAnalysisInput`은 여러 개의 서로 다른 Lecture Segment 기록의 anchor가 될 수 있다. deterministic provenance chain은 다음과 같다: `Lecture Segment → EligibleAnalysisInput → Transcript Readiness → 선택된 Corrected Transcript 계보 → Source Timeline → Source Media`.

**Minimum Boundary (Confirmed):** 모든 Lecture Segment는 anchor한 입력의 Source Timeline 위에 **정확히 하나의 필수 Source Timeline Time Range**를 가진다(`range_start`, `range_end`; finite, non-negative, `start <= end`). Time Range는 **필수이며 단일**이다(Segment는 경계를 가진 영역이므로 Analysis Finding의 선택적 range와 구별된다). 이 milestone은 Segment 사이의 어떤 관계도 모델링하지 않는다: overlap, adjacency, nesting, hierarchy, containment, multi-range를 표현하지 않는다. 전체 녹음을 덮는 Range는 허용된다(단지 유효한 Range다). per-admission `sequence`는 안정적 ordinal과 deterministic identity를 위한 것이며 Segment 사이의 의미적 순서나 인접성을 보장하지 않는다. 같은 입력 위에 여러 독립 single-range Segment가 존재할 수 있고, 시간축상 우연히 겹치더라도 그것은 모델링된 관계가 아니다.

**Reprocessing (Confirmed):** 이 milestone은 **immutable, insert-only** Segment만 확립한다. revision, supersession, downstream reconciliation은 deferred다. §7의 "재처리가 이전 provenance와 Review 이력을 모호하게 만들지 않는다"는 요구는 최소 수준에서 immutability와 provenance로 충족된다: Segment는 변경·삭제되지 않으므로 이전 Segment와 그에 근거한 provenance·Review는 그대로 보존되며, 이후 재처리는 각자의 identity와 provenance를 가진 새 Segment 기록을 삽입할 뿐이다. supersession link나 reconciliation 메커니즘을 도입하지 않는다.

**Application Foundation (Confirmed):** 이 milestone은 canonical Lecture Segment 기록과 **provider-independent Application 경계**를 확립하며, **정규화된(normalized) provider-independent segmentation 결과**를 Application 경계로 admit한다. AI를 호출하지 않고, provider를 구현하지 않으며, prompt나 model을 정의하지 않고, Segment Label·Analysis Finding·Edit Candidate·Review Item을 생성하지 않는다. **원본 provider 출력, provider 고유 분류·식별자, provider 내부 reasoning은 canonical domain으로 들어오지 않는다**(§7, §2.10). 구체적인 segmentation provider는 별도의 이후 milestone으로 deferred다(`040`의 Application Foundation → Concrete Provider 선례를 따른다).

**Admission Boundary (Confirmed):** Lecture Segment는 **eligibility가 ELIGIBLE인 정확히 하나의 `EligibleAnalysisInput`**, **running unit execution**, 그리고 완전한 upstream provenance가 있을 때만 admit된다. Time Range는 anchor한 입력의 Source Timeline 계보와 일치해야 한다. `EligibleAnalysisInput`과 모든 upstream 기록은 **read-only**로 소비하며 이 milestone은 어떤 upstream 기록도 변경하지 않는다.

**Generation Scope of this Milestone's Anchor and Admission Boundary (Confirmed, PATCH-0031):** 위 Canonical Anchor 문단과 Admission Boundary 문단의 **문언은 삭제·재작성되지 않으며 legacy execution-coupled generation(`§5.1.1`)의 계약으로 그대로 유효하다.** 다만 두 문단이 원래 가졌던 **보편 한정(모든 Lecture Segment에 대한 진술)은 그 세대로 범위가 좁혀진다** — `§8.1`이 `PATCH-0030`으로 받은 것과 동일한 versioned architecture 관용구이며, 계약의 소급 변경이 아니라 세대 범위의 명시다. 구체적으로 다음 두 요소가 **legacy 세대 전용**이다: (1) **anchor 대상 record인 `EligibleAnalysisInput`**(그리고 그 `ELIGIBLE` eligibility 상태 요구), 그리고 (2) **running unit execution 요구**. effective-transcript generation에서 그 anchor 자리는 `§5.1.1`의 세대 대응에 따라 `Lecture Analysis Input Admission`이 차지한다.

이 요구를 effective-transcript generation에 문자 그대로 적용할 수 없는 이유는 `§8.1`의 경우와 동일하다: 그 세대는 legacy `EligibleAnalysisInput`을 만들지 않고 내부 execution lifecycle을 사용하지 않으므로, 문자 그대로 적용하면 `040 §18` H-10과 `041 §15` E6이 **금지한** 가짜 실행 기록을 만들어야 한다. effective-transcript generation의 Lecture Segmentation admission 경계는 `§7.2`가 정의한다.

**두 세대에 공통으로 유지되는 것**은 다음이다: Lecture Segment 기록의 성질(immutable·identity-owning·provenance-bearing·replay-safe·provider-independent·insert-only, lifecycle state 없음), Canonical Anchor의 **cardinality 규칙**(정확히 하나의 durable analysis input; **Analysis Finding에 anchor하지 않으며 Finding의 존재를 요구하지 않음**; Source Timeline·Source Media는 anchor를 통해 상속), **Minimum Boundary 전체**(정확히 하나의 필수 단일 Time Range, finite·non-negative·`start <= end`, 전체 녹음 Range 허용, Segment 간 관계 미모델링, per-admission `sequence`의 의미), Reprocessing(insert-only), Application Foundation 경계, 그리고 Milestone Scope. 공통으로 유지되는 것은 이들 계약의 **의미**이며, 그 안에서 지목된 **세대별 record 이름**이 아니다.

**Milestone Scope (Confirmed):** 이 milestone은 **canonical Lecture Segment 기록만** 확립한다. 이 milestone은 confidence·uncertainty·rationale에 관한 어떤 semantics도 확립하지 않으며, 그러한 속성이 장차 어디에 귀속되는지(Lecture Segment, Segment Label, 또는 다른 downstream 객체)에 대해 아무 입장도 취하지 않는다. 이 milestone은 canonical-set/uniqueness 제약을 두지 않고 named view를 모델링하지 않으므로 "하나의 canonical segmentation을 강제하지 않는다"(§7, §19)가 그대로 보존된다.

**Deferred (이후 milestone):** Segment Label과 label taxonomy, 다중 segmentation view·perspective group·grouping aggregate·view identity, confidence·uncertainty·rationale semantics(및 그 귀속 대상), overlap·nesting·hierarchy·containment·adjacency·multi-range와 boundary uncertainty 표현, revision·supersession·reconciliation, segmentation quality, 구체적 segmentation provider·prompt·model, Edit Candidate와 Review(§18).

### 7.2 Effective-Transcript Generation — Lecture Segmentation Admission Boundary

이 소절은 `PATCH-0031`으로 승인된 Architect Decision(S-1…S-13)을 기록한다. 이 소절은 **`§7`의 Lecture Segment 의미와 `§7.1`의 canonical 기록 계약을 전혀 변경하지 않는다.** 이 소절이 확정하는 것은 오직 **effective-transcript generation에서 Segment가 무엇에 anchor하고 어떤 전제 아래 admit되는가**이며, 그 세대가 사용하는 생성 provenance 관용구다. 결정 번호에 `S-` 접두사를 쓰는 것은 이 문서가 이미 `§8.2`와 `§9.2`에서 서로 다른 `D-` 계열을 쓰고 있어 세 번째 `D-` 계열을 더하지 않기 위한 표기 구분일 뿐이며 계약상 의미는 없다. 이 문서의 모든 결정 인용은 소절로 한정해 읽는다.

**Contract Generation (Confirmed, S-1):** Lecture Segmentation admission 경계는 **두 개의 contract generation**으로 존재한다. `§7.1`의 Canonical Anchor·Admission Boundary 문단은 **legacy execution-coupled generation**의 계약이고, 이 소절은 **effective-transcript generation**의 계약이다. legacy 계약과 그 기록은 유효한 역사로 보존되며 삭제·backfill·재해석·소급 변경되지 않는다. 두 세대는 영구히 구분 가능하고, **하나의 contract generation 안에는 정확히 하나의 canonical Segmentation admission 경계가 존재한다.** 한 세대의 anchor를 다른 세대의 admission 근거로 교차 사용하지 않는다.

**Canonical Anchor (Confirmed, S-2):** effective-transcript generation에서 모든 Lecture Segment는 **정확히 하나의 immutable `Lecture Analysis Input Admission`**(`§5.1`의 durable 역할, `§5.1.1`)에 anchor한다. legacy `EligibleAnalysisInput`에는 anchor하지 않는다. `§7.1`이 확정한 대로 **Segment는 어떤 Analysis Finding에도 anchor하지 않으며 Finding의 존재를 요구하지 않는다** — 이 소절은 그 독립성을 그대로 보존한다. Source Timeline과 Source Media는 anchor를 **통해 상속되는 provenance**이지 직접 anchor 대상이 아니며, Finding과 마찬가지로 Segment 기록에 중복 복제하지 않는다. 하나의 Admission은 여러 개의 서로 다른 Lecture Segment 기록의 anchor가 될 수 있다. deterministic provenance chain은 다음과 같다: `Lecture Segment → Lecture Analysis Input Admission → current applicable Corrected Revision → parent Raw Transcript → Source Timeline → Source Media`.

**Sibling, Not Derived (Confirmed, S-3):** Lecture Segmentation과 Analysis Finding(`§8.2`)은 **같은 종류의 Admission을 각자 독립적으로 anchor하는 sibling application 기록**이다(`§7.1`과 `§8.1`의 Canonical Anchor가 각 방향의 무참조를 확정한다). 하나의 Admission 위에 Segment만, 또는 Finding만 존재해도 완전히 유효하다. 어느 쪽도 다른 쪽의 parent가 아니고, 어느 쪽도 다른 쪽의 존재를 전제하지 않으며, 순서 의존도 없다. Segmentation은 Finding 없이 admit될 수 있고 그 반대도 같다. Finding을 Segment의 근거(evidence)로 참조하는 관계, Segment-Finding linkage, Segment Label은 이 소절이 도입하지 않으며 `§7.1`·`§8.1`의 deferred 상태를 그대로 유지한다.

**Current-Only Admission Standing (Confirmed, S-4):** Segmentation admission은 **저장된 Admission 기록이 존재한다는 사실만으로 허용되지 않는다.** prepare 또는 admission 시점에 anchor 대상 Admission의 **현재 authority standing을 재평가**해야 하며, 그 파생 standing이 **`current`일 때만** admit된다. `superseded_by_authority_change`와 `current_authority_ineligible`은 명시적 거부 사유다. 이 파생 vocabulary는 released GOAL-023 계약이 정의한 **정확히 세 값**이며 이 소절은 여기에 어떤 값도 추가하지 않는다. Admission identity가 존재하지 않거나 canonical 형식에 맞지 않는 경우는 **네 번째 standing 값이 아니라** 참조 자체의 거부로 다루며, standing 평가 이전에 실패한다.

**No Stored Currentness (Confirmed, S-5):** Admission standing은 **파생 관측**이며 저장 상태가 아니다. 이 소절은 `Lecture Analysis Input Admission` 기록에도, Segment 기록에도 mutable status·current flag·stale flag·lifecycle state를 **추가하지 않으며, 추가하는 방향을 금지한다**(`§7.1`의 "lifecycle state를 도입하지 않는다"와 정합). standing 관측은 어떤 기록도 변경하지 않는다.

**Historical Semantics (Confirmed, S-6):** superseded Admission은 **유효한 immutable history**로 남으며 삭제·무효화·재작성되지 않는다. 마찬가지로 **기존 Lecture Segment는 upstream authority가 변경되었다는 이유로 수정·삭제·재작성되지 않는다.** 생성 당시 `current`였던 Admission에 적법하게 anchor된 Segment는 이후 authority가 바뀌어도 유효한 immutable 기록으로 남으며, 이는 `§7.1` Reprocessing이 immutability와 provenance만으로 충족한다고 확정한 바와 동일하다. 금지되는 것은 **superseded Admission을 anchor로 하는 새로운 Segmentation admission**뿐이다. authority가 이전에 admit된 revision으로 되돌아오면 동일한 canonical Admission identity가 다시 `current`가 되고 admission 가능성은 파생 규칙에 의해 복원된다(GOAL-023의 returning-authority convergence).

**Execution-Free Deterministic Provenance (Confirmed, S-7):** effective-transcript generation의 Segmentation Foundation은 `ProcessingRun`, `ProcessingUnit`, `UnitExecution`, RUNNING state, execution lifecycle, `DomainResult` chaining을 **요구하지 않는다.** 가짜 실행 기록·synthetic Processing Run·합성 RUNNING state를 provenance로 사용하는 것은 **금지된다**(`040 §18` H-10, `041 §15` E6의 명시적 금지). 대신 Segment의 생성 provenance는 다음 성질을 가져야 한다: **deterministic**, **local**, **replay-safe**, **identity-owning**, canonical 기록 경계에서 **provider-independent**, wall-clock 비의존, 무작위 실행 identity 없음. 결정적으로 파생된 실행 마커를 기록할지(`040 §14` A-3 / `040 §17` K-4 관용구) 실행 마커 없는 generator provenance를 사용할지(`041 §15` E6 관용구)는 **구현 선택**이며 이 소절은 어느 한쪽을 강제하지 않는다. 구체적인 provider invocation, model, prompt, remote request, execution lifecycle은 이 소절에서 확정하지 않는다.

**Segment Record Contract Preserved (Confirmed, S-8):** `§7.1`이 확정한 canonical Lecture Segment 기록의 의미는 이 세대에서도 **그대로 상속된다**: durable canonical domain record, **immutable**, **identity-owning**, **provenance-bearing**, **replay-safe**, **provider-independent**, **insert-only**, lifecycle state 없음. **Minimum Boundary는 문언 그대로 유지된다** — 모든 Segment는 anchor한 입력의 Source Timeline 위에 **정확히 하나의 필수 단일 Time Range**를 가지며(`range_start`, `range_end`; finite, non-negative, `start <= end`), 전체 녹음을 덮는 Range는 유효하고, Segment 사이의 overlap·adjacency·nesting·hierarchy·containment·multi-range는 **모델링하지 않는다**. 이 소절은 media-duration validation, transcript-boundary 정렬, full-coverage 요구, overlap 금지, gap 금지를 **추가하지 않는다**(`§9.2`가 Application Foundation 단계에 그러한 검증을 추가하지 않는다고 확정한 바와 정합하며, anchor는 대조할 timeline extent를 기록하지 않는다). canonical-set/uniqueness 제약과 named view도 도입하지 않으므로 "하나의 canonical segmentation을 강제하지 않는다"(§7, §19)가 그대로 보존된다. 이 소절이 재범위화하는 것은 **anchor와 admission 전제뿐**이다.

**Segment Identity and Ordered Admission (Confirmed, S-9):** identity를 소유하는 canonical 객체는 **개별 Lecture Segment**다(`§7.1` Lecture Segment Record의 identity-owning 규정). 이 소절은 segmentation aggregate·collection·perspective group·view identity를 **도입하지 않으며**, 그것들은 `§7.1`의 deferred 상태로 남는다.

`§7.1`은 per-admission `sequence`가 안정적 ordinal과 deterministic identity를 **위한 것**이며 Segment 사이의 의미적 순서나 인접성을 보장하지 않는다고 확정했다. 그 목적 규정 위에서 **이 소절이 다음을 새로 확정한다**(`§7.1`에서 상속하는 것이 아니다): 이 세대의 하나의 admission은 **순서 있는 하나 이상의 Segment**를 admit하고, batch 내 위치인 `sequence`는 **identity에 참여하는 안정적 ordinal**이며, 그 batch는 **원자적으로** 기록된다 — 부분 기록된 segmentation은 유효한 것으로 보일 수 없다. `sequence`가 identity에 참여한다는 것은 여전히 Segment 사이의 의미적 순서나 인접성을 뜻하지 않는다.

**Identity Direction (Confirmed, S-10):** Segment identity는 **Application이 소유**한다. provider가 반환한 식별자나 execution framework의 식별자를 canonical identity로 사용하지 않는다. identity는 **immutable admitted source와 안정적인 segmentation 의미**에만 기반해야 하며, timestamp·rowid·물리 경로·mutable currentness state·auto-increment sequence 단독은 identity에 참여하지 않는다. **정확한 hash 구성은 이 소절에서 확정하지 않고 구현 milestone에 위임한다**(`041 §15` E7과 `§8.2` D-8의 선례). 이 위임은 위 원칙과 S-9의 identity 소유 주체가 이미 규범으로 닫혀 있으므로 구현을 막지 않는다.

**Replay and Conflict (Confirmed, S-11):** **동일 Admission + 동일 contract version + 동일한 순서의 canonical segment 내용 → 동일한 canonical Segment identity 집합으로 수렴**하며 중복 기록을 만들지 않는다. 다음은 별개의 Segment가 될 수 있다: 다른 Admission, 다른 Time Range, 그 밖에 계약상 identity에 포함되는 의미적 내용의 변경, 그리고 batch 내 위치(`sequence`)의 변경. 동일 identity에 대해 **의미가 다른 payload**가 제출되면 덮어쓰지 않고 **명시적 conflict**로 거부한다(released collision-convergence 관용구, `040 §18` H-9). 근접 동시 동일 admission은 중복 canonical Segment 없이 수렴한다.

**Persisted Representation (Confirmed, S-12):** 이 소절은 canonical Segment 기록의 **의미**만 확정하며 물리적 저장 형태를 확정하지 않는다. 다만 legacy `lecture_segments` 관계는 legacy 세대의 anchor와 실행 provenance(legacy analysis input, `ProcessingRun`, `UnitExecution`, `DomainResult`)를 **필수 컬럼으로 요구**하므로, effective-transcript generation의 Segment를 그 관계에 기록하려면 S-7이 금지한 값을 날조해야 한다. 따라서 이 세대의 Segment는 **legacy 관계를 재사용하지 않으며**, 필요한 저장 형태는 `041 §15` E1과 `§8.2` D-11의 선례를 따라 **strictly additive한 새 versioned representation**으로 도입한다. legacy 관계와 그 행은 backfill·dual-write·재해석 없이 자기 세대의 canonical 표현으로 남는다. 정확한 이름과 컬럼 구성은 구현 milestone이 선택한다.

**Sections Not Re-scoped (Confirmed, S-13):** 이 소절은 **`§9.1`(Edit Candidate)의 admission 경계를 재범위화하지 않는다.** `§9.1`의 anchor(정확히 하나의 Analysis Finding)와 running unit execution 요구는 자기 계약으로 변경 없이 유지되며, `§7.2`가 그것에 암묵적으로 일반화되지 않는다. *(후속 기록: `§9.1`은 이후 `PATCH-0032`가 `§9.3`으로 재범위화했다. S-13이 당시 재범위화하지 않았다는 사실은 그대로 유효하나, `§9.1`이 legacy 계약을 그대로 유지한다는 서술은 이제 legacy 세대에 한정된다.)* Review(`043`), Export(`044`), Analysis Execution, Processing Model도 마찬가지다. 해당 milestone이 effective-transcript generation에서 일정에 오를 때 각자 동등한 generation 범위 결정이 필요하며, 그 결정은 이 소절이 아니라 그때의 승인된 PATCH가 내린다.

**Deferred (이후 milestone):** Segment Label과 label taxonomy, 다중 segmentation view·perspective group·grouping aggregate·view identity, confidence·uncertainty·rationale semantics, overlap·nesting·hierarchy·containment·adjacency·multi-range와 boundary uncertainty 표현, revision·supersession·reconciliation, current-segmentation selection, segmentation quality, 구체적 segmentation provider·prompt·model·remote invocation·provider response persistence, Analysis Execution lifecycle과 `ProcessingRun`과의 장기 관계, Segment-Finding linkage, Edit Candidate와 Review, user-editable segmentation, export 표현(§18). 이들 중 어느 것도 이 소절이 확정한 admission 경계의 전제가 아니므로 effective-transcript Segmentation Foundation 구현을 막지 않는다.

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

### 8.1 First Analysis Milestone — Analysis Finding Application Foundation

이 소절은 `PATCH-0010`으로 승인된 Product Owner 결정을 기록한다. Analysis의 **첫 dependency-ordered milestone**은 **Analysis Finding Application Foundation**이며, `§8`이 정의한 Analysis Finding을 canonical 기록으로 확정하는 것이 책임이다. 이 milestone은 §8의 의미를 다시 정의하지 않고 아래 계약을 확정한다.

**Analysis Finding (Confirmed):** Analysis Finding은 **durable canonical domain record**이며 **immutable**, **identity-owning**(Application 소유 identity), **provenance-bearing**한 **insert-only** 기록이다. revision과 supersession은 계속 deferred다.

**Canonical Anchor (Confirmed):** 모든 Finding은 **정확히 하나의 `EligibleAnalysisInput`(§5.1)**에 anchor된다. **Source Timeline Time Range는 선택적**이며(시간에 위치한 Finding일 때만) 최대 하나다. **Lecture Segment 관계는 이 milestone의 범위가 아니며**, multi-range·overlapping 참조는 deferred다. 하나의 `EligibleAnalysisInput`은 여러 개의 서로 다른 Finding 기록의 anchor가 될 수 있다.

**Finding Type (Confirmed):** 모든 Finding은 **필수 Finding Type**을 가진다. Finding Type은 **provider-independent**하고 **stable**하며 **Application이 소유**하는 canonical 분류값이다. provider의 분류를 canonical truth로 승격하지 않는다(§8, §2.10). 이 milestone은 고정 taxonomy나 category 값을 정의하지 않는다(§18).

**Evidence (Confirmed):** 모든 Finding은 **기록된(recorded) supporting evidence**를 provenance와 함께 가진다: 사람이 검토할 수 있는 rationale/설명과 admit한 `EligibleAnalysisInput`(및 존재하는 경우 Source Timeline range)까지의 provenance. 구조적 evidence 모델과 특정 텍스트 표현 제약은 deferred다.

**Confidence (Confirmed):** Finding은 **기록된 confidence 또는 uncertainty**를 선택적으로 가질 수 있다. confidence의 계산·calibration·prioritization·해석 기준은 deferred다.

**Application Foundation (Confirmed):** 이 milestone은 canonical Finding 기록과 **provider-independent Application 경계**를 확립하며, **정규화된(normalized) provider-independent 분석 결과**를 Application 경계로 admit한다. 이 milestone은 AI를 호출하지 않고, provider를 구현하지 않으며, prompt나 model을 정의하지 않고, Lecture Segment·Edit Candidate·Review Item을 생성하지 않는다. **원본 provider 출력, provider 고유 분류·식별자, provider 내부 reasoning은 canonical domain으로 들어오지 않는다**(§8, §2.10). 구체적인 AI Analysis Provider는 별도의 이후 milestone으로 deferred다(`040`의 Application Foundation → Concrete Provider 선례를 따른다).

**Admission Boundary (Confirmed):** Finding은 **eligibility가 ELIGIBLE인 정확히 하나의 `EligibleAnalysisInput`**, **running unit execution**, 그리고 완전한 upstream provenance가 있을 때만 admit된다. `EligibleAnalysisInput`과 모든 transcript/readiness upstream은 **read-only**로 소비하며 이 milestone은 어떤 upstream 기록도 변경하지 않는다.

**Generation Scope of this Milestone's Anchor and Admission Boundary (Confirmed, PATCH-0030):** 위 Canonical Anchor 문단과 Admission Boundary 문단의 **문언은 삭제·재작성되지 않으며 legacy execution-coupled generation(`§5.1.1`)의 계약으로 그대로 유효하다.** 다만 두 문단이 원래 가졌던 **보편 한정(모든 Finding에 대한 진술)은 그 세대로 범위가 좁혀진다** — 이는 `041 §15`가 확립한 versioned architecture 관용구이며, 계약의 소급 변경이 아니라 세대 범위의 명시다. 구체적으로 다음 두 요소가 **legacy 세대 전용**이다: (1) **anchor 대상 record인 `EligibleAnalysisInput`**, 그리고 (2) **running unit execution 요구**. Evidence 문단이 provenance 대상으로 지목한 `EligibleAnalysisInput` 역시 같은 이유로 legacy 세대의 record 이름이며, effective-transcript generation에서 그 자리는 `§5.1.1`의 세대 대응에 따라 `Lecture Analysis Input Admission`이 차지한다.

이 요구를 effective-transcript generation에 문자 그대로 적용할 수 없는 이유는 명확하다: 그 세대는 legacy `EligibleAnalysisInput`을 만들지 않고 내부 execution lifecycle을 사용하지 않으므로, 문자 그대로 적용하면 `040 §18` H-10과 `041 §15` E6이 **금지한** 가짜 실행 기록을 만들어야 한다. effective-transcript generation의 Analysis Finding admission 경계는 `§8.2`가 정의한다.

**두 세대에 공통으로 유지되는 것**은 다음이다: Finding 기록의 성질(immutable·identity-owning·provenance-bearing·insert-only), Canonical Anchor의 **cardinality 규칙**(정확히 하나의 durable analysis input, 선택적이며 최대 하나인 Source Timeline Time Range, Lecture Segment 무참조, multi-range deferred), Finding Type, **evidence를 provenance와 함께 기록해야 한다는 요구 자체**, Confidence, 그리고 Application Foundation 경계. 공통으로 유지되는 것은 이들 계약의 **의미**이며, 그 안에서 지목된 **세대별 record 이름**이 아니다.

**Deferred (이후 milestone):** taxonomy, confidence 계산, uncertainty calibration, prioritization, revision, supersession, Lecture Segmentation, Segment 관계, multi-range Finding, overlapping range, Edit Candidate, Review, 구체적 AI Provider·prompt·model, Source-Media-only 분석, optional Subtitle/Speaker/Project Context admission(§18).

### 8.2 Effective-Transcript Generation — Analysis Finding Admission Boundary

이 소절은 `PATCH-0030`으로 승인된 Architect Decision(D-1…D-12)을 기록한다. 이 소절은 **`§8`의 Analysis Finding 의미와 `§8.1`의 canonical Finding 기록 계약을 전혀 변경하지 않는다.** 이 소절이 확정하는 것은 오직 **effective-transcript generation에서 Finding이 무엇에 anchor하고 어떤 전제 아래 admit되는가**이며, 그 세대가 사용하는 생성 provenance 관용구다. 새 taxonomy, 새 confidence 계산법, 새 multi-range 모델, concrete provider 계약, Analysis Execution lifecycle은 이 소절에서 확정하지 않는다.

**Contract Generation (Confirmed, D-1):** Analysis Finding admission 경계는 **두 개의 contract generation**으로 존재한다. `§8.1`의 Admission Boundary 문단은 **legacy execution-coupled generation**의 계약이고, 이 소절은 **effective-transcript generation**의 계약이다. legacy 계약과 그 기록은 유효한 역사로 보존되며 삭제·backfill·재해석·소급 변경되지 않는다. 두 세대는 영구히 구분 가능하고, **하나의 contract generation 안에는 정확히 하나의 canonical Finding admission 경계가 존재한다.** 한 세대의 anchor를 다른 세대의 admission 근거로 교차 사용하지 않는다.

**Canonical Finding Anchor (Confirmed, D-2):** effective-transcript generation에서 모든 Analysis Finding은 **정확히 하나의 immutable `Lecture Analysis Input Admission`**(`§5.1`의 durable 역할, `§5.1.1`)에 anchor한다. legacy `EligibleAnalysisInput`에는 anchor하지 않는다. 이 anchor는 다음 의미를 **참조로** 확보한다: 정확한 effective transcript authority snapshot, 정확한 Source Media 계보, 정확한 current applicable corrected revision, 정확한 parent Raw Transcript, 정확한 selection provenance, 그리고 `040 §19` content fingerprint. **Finding이 이 provenance를 자신의 기록에 중복 복제해야 한다는 뜻은 아니다** — Finding은 canonical Admission identity를 참조하고 필요한 의미를 그 Admission을 통해 얻는다. 하나의 Admission은 서로 다른 여러 Finding의 anchor가 될 수 있다. deterministic provenance chain은 다음과 같다: `Analysis Finding → Lecture Analysis Input Admission → current applicable Corrected Revision → parent Raw Transcript → Source Timeline → Source Media`. `§8.1`이 확정한 anchor cardinality 규칙(정확히 하나의 durable analysis input, 선택적이며 최대 하나인 Source Timeline Time Range, Lecture Segment 무참조, multi-range deferred)은 그대로 유지된다.

**Current-Only Admission Standing (Confirmed, D-3):** Finding admission은 **저장된 Admission 기록이 존재한다는 사실만으로 허용되지 않는다.** prepare 또는 admission 시점에 anchor 대상 Admission의 **현재 authority standing을 재평가**해야 하며, 그 파생 standing이 **`current`일 때만** admit된다. `superseded_by_authority_change`와 `current_authority_ineligible`은 명시적 거부 사유다. 이 파생 vocabulary는 released GOAL-023 계약이 정의한 **정확히 세 값**(`current`, `superseded_by_authority_change`, `current_authority_ineligible`)이며 이 소절은 여기에 어떤 값도 추가하지 않는다. Admission identity가 존재하지 않거나 canonical 형식에 맞지 않는 경우는 **네 번째 standing 값이 아니라** 참조 자체의 거부(missing/malformed reference)로 다루며, standing 평가 이전에 실패한다.

**No Stored Currentness (Confirmed, D-4):** Admission standing은 **파생 관측**이며 저장 상태가 아니다. 이 소절은 `Lecture Analysis Input Admission` 기록에 mutable status·current flag·stale flag·lifecycle state를 **추가하지 않으며, 추가하는 방향을 금지한다.** standing 관측은 어떤 기록도 변경하지 않는다. Admission 기록은 released 계약대로 append-only이며 update·delete되지 않는다.

**Historical Admission Semantics (Confirmed, D-5):** superseded Admission은 **유효한 immutable history**로 남으며 삭제·무효화·재작성되지 않는다. 마찬가지로 **기존 Analysis Finding은 upstream authority가 변경되었다는 이유로 수정·삭제·재작성되지 않는다.** 생성 당시 `current`였던 Admission에 적법하게 anchor된 Finding은 이후 authority가 바뀌어도 손상되거나 무효가 되지 않는 유효한 immutable 기록으로 남는다. 금지되는 것은 **superseded Admission을 anchor로 하는 새로운 Finding admission**뿐이다. authority가 이전에 admit된 revision으로 되돌아오면, Admission identity가 정확한 immutable admitted source에서만 파생된다는 released 규칙에 따라 **동일한 canonical Admission identity가 다시 `current`가 되고** admission 가능성은 파생 규칙에 의해 복원된다. 이때 새로운 Admission identity는 만들어지지 않으며, 이는 GOAL-023의 returning-authority convergence 계약과 정확히 일치한다.

**Execution-Free Deterministic Provenance (Confirmed, D-6):** effective-transcript generation의 Finding Foundation은 `ProcessingRun`, `ProcessingUnit`, `UnitExecution`, RUNNING state, execution lifecycle을 **요구하지 않는다.** released precedent는 두 갈래로 구분해 인용한다. **(a) 내부 실행 row를 만들지 않고 RUNNING execution을 요구하지 않는 관용구** — `040 §14` A-3(외부 결과를 admit하며 내부 `ProcessingRun`/`UnitExecution`을 만들지 않고 RUNNING unit execution을 요구하지 않는다)과 `040 §17` K-4(실행 마커를 anchor에서 결정적으로 파생하되 내부 RUNNING execution을 만들지 않는다). **(b) 명시적 금지** — `040 §18` H-10(fake execution·synthetic Processing Run·RUNNING state는 없다)과 `041 §15` E6(가짜 실행 lifecycle record는 금지된다). 따라서 이 세대에서 **가짜 실행 기록·synthetic Processing Run·합성 RUNNING state를 provenance로 사용하는 것은 금지된다.**

구현이 (a)의 결정적으로 파생된 실행 마커를 기록할지, `041 §15` E6처럼 실행 마커 없는 generator provenance를 사용할지는 **구현 선택**이며 이 소절은 어느 한쪽을 강제하지 않는다. 다만 어느 쪽이든 다음을 반드시 만족해야 한다: 내부 execution row를 만들지 않을 것, RUNNING state를 날조하지 않을 것, 그리고 Finding의 생성 provenance가 **deterministic**, **local**, **replay-safe**, **identity-owning**, canonical 기록 경계에서 **provider-independent**, 그리고 **생성 계약(generation contract — 어떤 계약과 그 version 아래 기록되었는가)과 immutable source binding을 구분하기에 충분할 것.** 구체적인 provider invocation, model, prompt, remote request, token usage, execution lifecycle은 이 소절에서 확정하지 않으며 concrete Analysis Provider 또는 Analysis Execution milestone의 별도 계약 대상이다.

**Finding Record Contract Preserved (Confirmed, D-7):** `§8.1`이 확정한 canonical Finding 기록의 의미는 이 세대에서도 **그대로 상속된다**: durable canonical domain record, **immutable**, **identity-owning**, **provenance-bearing**, **insert-only**; 필수이며 provider-independent·stable·Application 소유인 canonical **Finding Type**(고정 taxonomy·closed enum 없음); provenance를 동반한 **기록된 evidence**; **선택적**으로 기록되는 confidence 또는 uncertainty(계산·calibration·prioritization은 deferred); **선택적이며 최대 하나**인 Source Timeline Time Range. 원본 provider 출력, provider 고유 분류·식별자, provider 내부 reasoning은 canonical domain으로 들어오지 않는다. revision과 supersession은 계속 deferred다. 이 소절이 재범위화하는 것은 **anchor와 admission 전제뿐**이다.

**Identity Direction (Confirmed, D-8):** Finding identity는 **Application이 소유**한다. provider가 반환한 식별자를 canonical identity로 사용하지 않는다. identity는 **immutable admitted source와 안정적인 canonical Finding 내용**에 기반해야 하며, timestamp·rowid·물리 경로·출력 파일명·mutable currentness state·auto-increment sequence 단독은 identity에 참여하지 않는다. 동일 canonical Finding의 replay는 동일 identity로 수렴해야 한다. **정확한 hash 구성은 이 소절에서 확정하지 않고 구현 milestone에 위임한다**(`041 §15` E7이 hash 구성을 GOAL-013 구현에 위임한 선례를 따른다). 이 위임은 위 identity 원칙이 이미 규범으로 닫혀 있으므로 구현을 막지 않는다.

**Replay and Conflict (Confirmed, D-9):** **동일 Admission + 동일 canonical Finding 내용 + 동일 Finding contract version → 동일 canonical Finding identity로 수렴**하며 중복 기록을 만들지 않는다. 다음은 별개의 Finding이 될 수 있다: 다른 Admission, 다른 Finding Type, 다른 evidence 내용, 다른 stable source range, 그 밖에 계약상 identity에 포함되는 의미적 내용의 변경. 동일 identity에 대해 **의미가 다른 payload**가 제출되면 덮어쓰지 않고 **명시적 conflict**로 거부한다(released collision-convergence 관용구, `040 §18` H-9). 근접 동시 동일 admission은 중복 canonical Finding 없이 수렴한다.

**No Finding Currentness State (Confirmed, D-10):** 이 소절은 Finding 기록에 `finding_is_current`·`finding_is_stale`·`ready`·`active`·supersession flag 같은 **저장 상태를 추가하지 않는다.** Finding의 현재 활용 가능성·staleness·current-Finding 선택 정책은 별도 계약이 없는 한 이 소절의 범위 밖이다. **Finding 무결성 ≠ Admission currentness ≠ 분석 적용 가능성 ≠ Review 적격성.** upstream authority 변경으로 Finding이 stale해지더라도 그것은 무결성 손상이 아니며 어떤 기록도 변경·재생성하지 않는다.

**Milestone Scope (Confirmed):** 이 소절은 effective-transcript generation의 **Analysis Finding admission 경계만** 확정한다. 이 소절은 분석을 수행하지 않고, AI를 호출하지 않으며, provider를 구현하지 않고, prompt나 model을 정의하지 않으며, Lecture Segment·Segment Label·Edit Candidate·Review Item을 생성하지 않는다. `§8.1`의 provider-independent Application Foundation 경계(정규화된 provider-independent 분석 결과를 admit한다)는 이 세대에서도 그대로 적용된다.

**Persisted Representation (Confirmed, D-11):** 이 소절은 canonical Finding 기록의 **의미**만 확정하며 물리적 저장 형태를 확정하지 않는다. 다만 legacy `analysis_findings` 관계는 legacy 세대의 anchor와 실행 provenance를 **필수 컬럼으로 요구**하므로, effective-transcript generation의 Finding을 그 관계에 기록하려면 D-6이 금지한 값을 날조해야 한다. 따라서 이 세대의 Finding은 **legacy 관계를 재사용하지 않으며**, 필요한 저장 형태는 `041 §15` E1의 선례를 따라 **strictly additive한 새 versioned representation**으로 도입한다. legacy 관계와 그 행은 backfill·dual-write·재해석 없이 자기 세대의 canonical 표현으로 남는다. 정확한 이름과 컬럼 구성은 구현 milestone이 선택한다.

**Sections Not Re-scoped (Confirmed, D-12):** 이 소절은 **`§7.1`(Lecture Segmentation)과 `§9.1`(Edit Candidate)의 admission 경계를 재범위화하지 않는다.** 그 두 소절의 anchor와 running unit execution 요구는 각자의 계약으로 변경 없이 유지되며, `§8.2`가 그들에게 암묵적으로 일반화되지 않는다. *(후속 기록: `§7.1`은 `PATCH-0031`이 `§7.2`로, `§9.1`은 `PATCH-0032`가 `§9.3`으로 각각 재범위화했다. D-12가 당시 두 소절 중 어느 쪽도 재범위화하지 않았다는 사실은 그대로 유효하다. 아래 문장이 두 소절을 legacy 계약 유지로 서술한 부분은 이제 **각 소절의 legacy generation에 한정해서** 읽어야 하며, 두 소절의 legacy 계약 자체는 `§7.2` S-1·`§9.3` C-1에 따라 여전히 유효하다.)* 해당 milestone이 effective-transcript generation에서 일정에 오를 때 각자 동등한 generation 범위 결정이 필요하며, 그 결정은 이 소절이 아니라 그때의 승인된 PATCH가 내린다.

**Deferred (이후 milestone):** canonical analysis unit, Analysis Execution lifecycle과 `ProcessingRun`과의 장기 관계, 구체적 Analysis Provider·prompt schema·model selection·remote invocation·provider response persistence, Finding taxonomy 폐쇄와 `020 §5.5` LI-001…LI-012와 open Finding Type의 최종 조정, confidence 계산, Finding revision·supersession·reconciliation, multi-range evidence, segmentation view, Review workflow, current-Finding selection, Analysis Result aggregate, 그리고 GOAL-023 입력 snapshot을 넘어서는 Analysis Snapshot(§18). 이들 중 어느 것도 이 소절이 확정한 admission 경계의 전제가 아니므로 effective-transcript Finding Foundation 구현을 막지 않는다.

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

### 9.1 First Candidate Milestone — Edit Candidate Application Foundation

이 소절은 `PATCH-0012`로 승인된 Product Owner 결정을 기록한다. Edit Candidate의 **첫 dependency-ordered milestone**은 **Edit Candidate Application Foundation**이며, `§9`가 정의한 Edit Candidate를 canonical 기록으로 확정하는 것이 책임이다. 이 milestone은 §9의 의미를 다시 정의하지 않고 아래 계약만 확정하며, §9가 "연결할 수 있어야 한다"로 열거한 그 밖의 속성(Segment Label, confidence/Uncertainty, 예상 절감 시간, Review 상태, 처리 의도 등)은 확정하지 않고 deferred로 둔다.

**Edit Candidate Record (Confirmed):** Edit Candidate는 optional·evaluative·advisory한 분석 파생 제안이며, 그 canonical 기록은 **durable canonical domain record**로 **immutable**, **identity-owning**(Application 소유 identity), **provenance-bearing**, **replay-safe**, **provider-independent**한 **insert-only** 기록이다. Analysis Finding, Review Decision, Approved Edit Decision, 적용된 편집, 실행 가능한 NLE operation과 구별된다. 이 기록은 lifecycle state, Review 상태, 가변 상태, 삭제 동작, revision 필드, supersession 필드, rejected-candidate 상태를 가지지 않는다. 이후 Reject된 Candidate도 durable historical record로 남으며, 거절 자체는 Review(043)의 책임이고 Candidate에 표현되지 않는다.

**Canonical Anchor (Confirmed):** 모든 Edit Candidate는 **정확히 하나의 Analysis Finding**(§8.1)에 anchor된다. Analysis Finding은 **필수**이며 Candidate는 Finding 없이 존재할 수 없다. **Lecture Segment는 이 milestone의 anchor도 reference도 아니다.** 하나의 Analysis Finding은 여러 Edit Candidate의 근거가 될 수 있고, 각 Edit Candidate는 정확히 하나의 Finding을 참조한다. 하나의 Candidate가 여러 Finding을 참조하는 것, Segment linkage, 다중 Segment 참조, many-to-many provenance는 deferred다. canonical provenance는 anchor한 Finding을 통해 상속된다: `Edit Candidate → Analysis Finding → EligibleAnalysisInput → transcript 계보 → Source Timeline → Source Media`. 해당 DomainResultReference는 Edit Candidate 결과를 식별하고 anchor한 Analysis Finding의 DomainResult를 **유일한 직접 upstream result**로 사용한다. Candidate에 두 번째 직접 `EligibleAnalysisInput` anchor를 요구하지 않으며 Lecture Segment의 존재를 요구하지 않는다.

**Source Timeline Time Range (Confirmed):** 모든 Edit Candidate는 **정확히 하나의 필수 Source Timeline Time Range**를 가진다. 이 range는 Candidate에 속하며, 사람이 Review할 수 있도록 제안된 Source Timeline 영역을 가리키고, anchor한 Analysis Finding에서 상속한 Source Timeline 위에 존재한다. Candidate range는 Analysis Finding의 **선택적** range와 같을 필요가 없고, 더 좁거나 더 넓을 수 있으며, **Finding에 range가 없어도 필수**다. 최소 구조 불변식은 정확히 하나의 range, finite, non-negative, `start <= end`이다. 전체 녹음을 덮는 range는 유효하고, zero-duration range는 구조적으로 유효하나 특별한 canonical 의미가 없다. 다중 range, discontinuous target, non-timeline Candidate, cross-Segment target, overlap·adjacency·containment semantics, range reconciliation, Segment range와의 equality는 deferred다.

**Minimum Payload (Confirmed):** 이 milestone의 canonical Edit Candidate payload는 다음을 포함한다: 필수 Edit Candidate identity, 필수 Analysis Finding anchor, 필수 Source Media provenance, 필수 Source Timeline provenance, 정확히 하나의 필수 Time Range, 필수 **Candidate Type**, 필수 **rationale**, 확립된 durable-stage admission 패턴이 요구하는 범위의 결정적(ordering) metadata, 그리고 DomainResultReference provenance. **rationale**는 canonical·provider-independent·비어 있지 않은·사람이 검토 가능한 텍스트로, 이 advisory 제안을 뒷받침하는 기록된 분석적 이유다(사람이 **작성**해야 한다는 뜻은 아니다). rationale은 provider 내부 reasoning, chain of thought, raw model explanation, 실행 가능한 편집 명령, Review modification content가 아니다. confidence, uncertainty, priority, severity, 예상 절감 시간, structured evidence, source text, replacement text, proposed replacement, proposed treatment operation, 실행 가능한 편집 명령, NLE operation, provider explanation, provider metadata, raw provider response는 deferred다.

**Candidate Type (Confirmed):** 모든 Edit Candidate는 하나의 필수 canonical **Candidate Type**을 가진다. Candidate Type은 **open key**이며 **stable**, **provider-independent**, **Application이 소유**하는 canonical 값이다. 이는 closed enum, 고정 product taxonomy, provider 분류, provider operation name, NLE command이 아니다. retain, remove, condense, review, emphasize 같은 예시는 **illustrative일 뿐**이며 이 소절은 그것을 normative 값으로 승격하지 않는다. 정확한 canonical key grammar는 기존 canonical Application-key 선례(§8.1의 Finding Type)를 따르는 한 구현 수준의 선택으로 둘 수 있다. provider 경계: provider-native label·classification은 canonical이 아니며, 구체적 provider는 admission 이전에 출력을 Application 소유 Candidate Type으로 매핑해야 하고, canonical 기록은 정규화된 Application 소유 값만 admit한다. 런타임 validation이 유효한 문자열의 과거 출처를 추론·탐지하도록 요구하지 않는다.

**Application Foundation (Confirmed):** 이 milestone은 **Edit Candidate Application Foundation**을 확립하며, provider-independent Edit Candidate 기록을 admit하고 durable하게 기록한 뒤 종료된다. 이 경계는 정규화된 provider-independent Candidate 결과를 admit하고, canonical admission 요건과 Finding·Source Timeline 계보를 검증하며, running execution을 요구하고, caller-owned identity를 사용하고, 결정적 immutable Candidate 기록을 구성하고, Candidate를 DomainResultReference와 함께 atomic하게 persist하며, 모든 upstream 기록에 대해 read-only를 유지할 수 있다. 이 milestone은 구체적 AI provider를 호출하지 않고, provider-native 출력을 저장하지 않으며, Review CandidateReference·Review Item을 생성하지 않고, Review 상태를 부여하지 않으며, Accept·Reject·Modify를 지원하지 않고, Approved Edit Decision을 만들지 않으며, 편집을 적용하지 않고, 미디어를 변경하지 않으며, NLE 명령을 생성하지 않는다. 안정적 Candidate identity·provenance·Source Timeline traceability가 이 milestone의 완전한 Review-handoff 보장이며, Review 통합은 `043`에 속한다. 구체적 Candidate Generation Provider는 별도의 이후 milestone으로 deferred다(`040`의 Application Foundation → Concrete Provider 선례를 따른다).

**Admission Boundary (Confirmed):** Edit Candidate는 **정확히 하나의 canonical Analysis Finding**, **running unit execution**, 그리고 완전한 upstream provenance가 있을 때만 admit된다. 정규화된 결과의 Source Timeline은 anchor한 Finding의 Source Timeline 계보와 일치해야 한다. Analysis Finding과 모든 upstream 기록은 **read-only**로 소비하며 이 milestone은 어떤 upstream 기록도 변경하지 않는다.

**Generation Scope of this Milestone's Anchor and Admission Boundary (Confirmed, PATCH-0032):** 위 Canonical Anchor·Minimum Payload·Application Foundation·Admission Boundary 문단의 **문언은 삭제·재작성되지 않으며 legacy execution-coupled generation(`§5.1.1`)의 계약으로 그대로 유효하다.** 다만 이 소절이 원래 가졌던 **보편 한정(모든 Edit Candidate에 대한 진술)은 그 세대로 범위가 좁혀진다** — `§8.1`이 `PATCH-0030`으로, `§7.1`이 `PATCH-0031`로 받은 것과 동일한 versioned architecture 관용구이며, 계약의 소급 변경이 아니라 세대 범위의 명시다.

구체적으로 다음 **네 요소가 legacy 세대 전용**이다. 앞의 두 소절보다 하나 더 많다는 점에 유의한다. (1) anchor 대상 Analysis Finding이 **`§8.1` legacy 세대의 Finding**이라는 점, (2) **running unit execution 요구**, (3) **`DomainResultReference` provenance** — Canonical Anchor 문단이 "anchor한 Analysis Finding의 DomainResult를 유일한 직접 upstream result로 사용한다"고 요구하고 Minimum Payload가 이를 payload 항목으로 열거하지만, effective-transcript generation의 Finding(`§8.2`)은 **DomainResult를 만들지 않으므로 참조할 upstream DomainResult 자체가 존재하지 않는다**(이 요구는 그 세대에서 충족 불가능하다), 그리고 (4) 필수 **Source Media·Source Timeline provenance를 Candidate 기록에 직접 담는 형태** — 현행 세대에서 그 provenance는 `§9.3`이 정하는 대로 anchor 연쇄를 통해 확보된다(provenance 요구 자체는 사라지지 않는다).

이 요구를 effective-transcript generation에 문자 그대로 적용할 수 없는 이유는 `§8.1`·`§7.1`의 경우와 같고, 여기서는 한 가지가 더 있다: running unit execution과 DomainResult를 문자 그대로 요구하면 `040 §18` H-10과 `041 §15` E6이 **금지한** 가짜 실행 기록을 만들어야 한다. effective-transcript generation의 Edit Candidate admission 경계는 `§9.3`이 정의한다.

**두 세대에 공통으로 유지되는 것**은 다음이다: Edit Candidate 기록의 성질(optional·evaluative·advisory, immutable·identity-owning·provenance-bearing·replay-safe·provider-independent·insert-only, lifecycle/Review 상태·revision·supersession·rejected 상태 없음), Canonical Anchor의 **cardinality와 방향**(정확히 하나의 Analysis Finding, Finding 없이 존재 불가, 하나의 Finding이 여러 Candidate의 근거가 될 수 있음, **Lecture Segment는 anchor도 reference도 아님**), **Source Timeline Time Range 전체**(정확히 하나의 필수 range, finite·non-negative·`start <= end`, Finding range와 같을 필요 없음, Finding에 range가 없어도 필수, 전체 녹음 range 유효, zero-duration 구조적 유효), 필수 **Candidate Type**(open key)과 필수 **rationale**의 의미와 경계, Reprocessing의 **insert-only·provenance-preserving 성질**(재실행이 기존 기록을 덮어쓰거나 삭제하지 않고 이전 Candidate identity에 연결된 Review provenance가 계속 주소 지정 가능해야 한다는 요구 — 다만 **의미가 동일한 재admission이 새 기록을 만드는지 기존 identity로 수렴하는지는 세대마다 다르며 이 세대에서는 C-11이 정한다**), Application Foundation이 **하지 않는** 것의 목록(Review·Approved Edit Decision·편집 적용·NLE 명령 등), 그리고 EC-001…EC-010 범위. 공통으로 유지되는 것은 이들 계약의 **의미**이며, 그 안에서 지목된 **세대별 record 이름과 provenance 표현 형태**가 아니다.

**Reprocessing (Confirmed):** Candidate 생성 재처리는 immutable·insert-only·provenance-preserving이다. 재실행은 새 Candidate identity와 기록을 만든다. 기존 Candidate 기록은 덮어쓰거나 삭제되지 않으며, 이전 Candidate identity에 연결된 기존·미래의 Review provenance는 계속 주소 지정 가능해야 한다. 이 milestone은 Candidate revision, supersession, replacement 관계, stale-candidate 탐지, Review reconciliation, current-candidate selection을 확립하지 않으며 이들을 `043` 또는 이후 승인된 milestone으로 deferred한다.

**EC-001…EC-010 Scope (Confirmed):** *Implemented now* — EC-001(필수 단일 Source Timeline Time Range), EC-005(필수 기록 rationale), EC-008(Source Timeline traceability). *Structurally guaranteed now* — EC-003(open Candidate Type이 canonical 구조 슬롯을 제공하되 구체적 recommendation 카테고리는 deferred), EC-009(Candidate는 advisory이며 자동 삭제 동작이 없다), EC-010(Candidate는 비실행이며 milestone은 자동 적용 이전에 멈춘다). *Explicitly deferred* — EC-002(Segment Label linkage; Segment Label과 함께 deferred), EC-004(confidence/uncertainty; 이후 Candidate enrichment/provider 계약으로 deferred), EC-006(예상 절감 시간; Requires Validation/이후 enrichment), EC-007(Review 상태; `043` Review 소유). deferral은 해당 eventual Must를 **순서화**할 뿐 취소하지 않는다. Candidate Type이 존재한다는 이유만으로 EC-003의 retain/delete/review 구체 값이 이미 구현된 것은 아니다.

**Deferred (이후 milestone):** Segment Label linkage와 label taxonomy, 다중 Finding·다중 Segment·many-to-many provenance, 다중 range·discontinuous·non-timeline·cross-Segment target, confidence·uncertainty·priority·severity·예상 절감 시간·structured evidence·source/replacement text·proposed treatment operation·실행 가능한 편집 명령, Candidate revision·supersession·stale 탐지·Review reconciliation·current-candidate selection, Review CandidateReference·Review Item·Review 상태·Accept/Reject/Modify·Approved Edit Decision(`043`), 구체적 Candidate Generation Provider·prompt·model(§18).

### 9.2 First Candidate Provider Milestone — Concrete Edit Candidate Generation Provider (First Slice)

이 소절은 `PATCH-0013`으로 승인된 Product Owner 결정(D-1…D-15)을 기록한다. `§9.1`이 확정한 **Edit Candidate Application Foundation은 이 소절에 의해 전혀 변경되지 않는다.** 이 소절은 §9.1의 canonical Candidate 기록 계약 위에서 동작하는 **provider-generation product semantics**만 확정하며, concrete adapter의 구현 세부는 정의하지 않는다. 이 소절은 canonical Edit Candidate domain 계약, provider-generation 제품 의미, concrete adapter 메커닉스, execution provenance, 외부 데이터 경계, deterministic integration acceptance, 그리고 deferred product-quality 승인을 명확히 구분한다.

**Provider Milestone Purpose (Confirmed):** 첫 Concrete Edit Candidate Generation milestone은 **provider-neutral generation Port**, **하나의 concrete real provider adapter**, **하나의 deterministic fake provider**, 그리고 §9.1의 완성된 Application admission을 호출하는 **generation/orchestration 계층**을 확립한다. provider는 **한 번의 invocation당 정확히 하나의 canonical Analysis Finding**을 평가하며, 그 Finding이 Candidate를 정당화하는지 판단하고, **zero 이상의 advisory Candidate 제안**을 생성하고, 승인된 first-slice registry에서 Candidate Type을 고르고, 근거 있는 단일 Candidate-owned Time Range를 고르고, 근거 있는 canonical rationale 하나를 생성한다. provider는 Candidate를 제품 중요도로 **ranking하지 않고**, priority·risk·confidence·uncertainty·예상 절감 시간을 부여하지 않으며, Review decision을 추천하지 않고, Review Item·Review 상태·Accept/Reject/Modify·Approved Edit Decision을 만들지 않으며, 편집을 적용·삭제하지 않고, auto-apply 적격성을 판정하지 않으며, admit된 Candidate를 변경하지 않는다. Candidate 순서는 **deterministic transport order일 뿐** priority나 제품 의미를 갖지 않는다. Human Authority(§2)와 Review 소유권(§20, `043`)은 그대로 유지된다.

**Invocation and No-Candidate Outcome (Confirmed):** 한 invocation은 정확히 하나의 Analysis Finding을 처리한다. generation-layer outcome은 zero/one/many Candidate 성공, provider failure, normalization failure, Application admission failure를 구분한다. **zero-Candidate 성공은 `NormalizedCandidateResult`와 구별되는 generation-outcome으로 표현되어야 한다.** zero Candidate일 때는 admission을 호출하지 않고, 빈 normalized batch를 제출하지 않으며, canonical Candidate나 DomainResult를 만들지 않는다. **§9.1 Application Foundation의 empty-batch 거부는 변경되지 않는다**(빈 batch를 받도록 바꾸지 않는다). 모든 Finding이 Candidate를 만들 필요는 없으며, multi-Finding provider invocation은 허용하지 않는다.

**First-Slice Candidate Type Registry (Confirmed):** provider-generation을 위한 **Application/product 소유의 closed first-slice registry**는 정확히 다음 세 key를 포함한다: `non_lecture_region`, `redundant_restatement`, `delivery_concern`. 이 registry는 **Application/generation 계층이 소유**하며 provider adapter나 prompt가 소유하지 않고, first-slice에서 **closed**이며, 이후 승인된 제품 결정을 통해서만 additively 확장된다. **§9.1의 canonical Edit Candidate 기록은 변경되지 않는다**: Candidate Type 필드는 여전히 **open canonical Application-owned key**이고, 이 registry는 generation/admission 단계에 추가된 제약일 뿐 canonical 필드를 global closed enum으로 재정의하지 않는다. 이 계층 구분은 반드시 보존된다. provider는 canonical registry key를 직접 emit할 수 있으나 모든 emit 값은 first-slice registry에 대해 검증되어야 한다. unknown 값은 `NormalizedCandidateResult`에도 canonical 기록에도 들어가지 않고, 조용히 강제 변환되지 않으며, 문서화되지 않은 alias로 변환되지 않는다. first-slice에서 alias는 지원하지 않는다. provider-native label은 canonical이 아니다. 승인된 registry로 명시적·결정적으로 매핑하지 않는 provider-specific mapping table은 이 slice에서 승인되지 않는다.

**Registry Key Meanings (Confirmed):**
- `non_lecture_region` — 어떤 located Source Timeline 영역이 **비수업성 자료**(우발적 잡담, 장비·셋업 문제, 대기, 수업 전후 자료, 쉬는 시간)를 포함할 수 있다는 제안. 근거: 제공된 transcript 발췌 + Analysis Finding evidence + located 원본 영역. **삭제 명령이 아니고, 교육적 가치가 없다는 판정이 아니며, Review decision이 아니고, 자동 적용 대상이 아니다.**
- `redundant_restatement` — 어떤 located 영역이 **말실수·restart·반복 어구·반복 설명·중복 재진술**을 포함할 수 있다는 제안. 근거: 반복/재시작을 보여주는 transcript 발췌 + Finding evidence. **cut/condense 명령이 아니고, 교수 스타일에 대한 부정적 판단이 아니며, Review decision이 아니다.**
- `delivery_concern` — 어떤 located 영역이 사람의 Review가 필요한 **전달·연속성·명료성 문제** 가능성을 포함할 수 있다는 제안. 근거: transcript 발췌 + Finding evidence. **내용이 틀렸다는 단정이 아니고, 최종 교육적 가치 판정이 아니며, 실행 가능한 편집 operation이 아니고, Review decision이 아니다.**
세 값 모두 advisory concern descriptor이며, 편집 명령이 아니고, 완결된 editorial taxonomy가 아니며, 항상 이후 사람의 Review 대상이다.

**Provider Input Contract (Confirmed):** 한 invocation은 다음만 읽을 수 있다 — Analysis Finding identity, Finding Type, Finding evidence, Finding Time Range, Finding range와 겹치는 corrected-transcript 텍스트, 그 range와 겹치는 located transcript segment, 그리고 작은 bounded surrounding transcript window. surrounding-window 경계는 provider/generation configuration으로 **고정**되고 한 invocation에 대해 결정적이며 provider가 동적으로 고르지 않고 canonical 기록의 일부가 아니다. provider는 승인된 window 밖의 전체 corrected transcript, Lecture Segment, 이전 Edit Candidate, Review history/Decision, Source Media bytes, raw audio·video, 물리 파일 경로, 무관한 Source Timeline 영역, 불필요한 식별자를 읽지 않는다. 모든 upstream 기록은 read-only다. **어떤 Lecture Segment identity나 참조도** provider-neutral generation 결과·`NormalizedCandidateResult`·canonical Edit Candidate 기록에 들어갈 수 없다. usable located transcript context가 없는 Finding에 대해서는 first slice가 Candidate를 생성하지 않고, generation outcome은 no-Candidate 성공을 기록하며 admission을 호출하지 않는다.

**External Data-Egress Boundary (Confirmed):** 첫 real provider adapter의 외부 egress는 승인된 corrected-transcript 발췌와 bounded context, Analysis Finding Type, Analysis Finding evidence, 근거 있는 range에 필요한 최소 타이밍 정보로 제한된다. adapter는 Source Media bytes, 물리 파일 경로, Review history, 무관한 transcript context, (기술적으로 필요하고 명시적으로 비민감한 경우가 아니면) 내부 DB 식별자, secret, provider configuration secret을 전송하지 않는다. 학생 이름·식별자 등 개인정보를 요청에 **의도적으로 추가하지 않는다.** first slice는 완전한 transcript redaction 시스템을 확립하지 않는다. 승인된 발췌 안에 개인정보가 나타날 위험은 **인지되고, 해결되었다고 주장하지 않으며, 이후 redaction/privacy 정책 milestone으로 deferred된다.** 이 PATCH는 오직 보수적인 first-slice **system boundary**만 승인하며, 완전한 법적 준거·관할 판단·retention 정책 승인·포괄적 PII 처리 기준을 구성하지 않는다. 최소 provider-operation 규칙: provider가 지원하는 경우 training/data-use는 비활성화하고, secret은 canonical 기록 밖에 두며, secret은 로깅하지 않고, raw request/response body는 durably 저장하지 않으며, request/response body 로깅은 비활성화하거나 제한한다. 이 경계는 `050_PLUGIN_SYSTEM.md §7`의 신뢰 경계 원칙과 일관된다.

**Candidate Range Generation (Confirmed):** 생성된 각 Candidate는 제공된 transcript context에 근거한 정확히 하나의 located Time Range를 가진다. first-slice provider 정책: range는 제안이 다루는 구체적 located 하위 영역을 가리키고, provider는 제공된 context 안에서 range를 좁힐 수 있으나 밖으로 넓힐 수 없으며, whole-recording range를 생성하지 않고, non-located Candidate 생성을 지원하지 않으며, 근거 있는 located range가 없는 제안은 거부·생략된다. Finding이 located일 때 그 range가 1차 근거 영역을 제공하되 생성된 range는 제공된 provider context 안에 머물러야 한다. **§9.1 Application Foundation의 range validation은 변경되지 않는다**(오직 real·finite·non-negative·`start <= end`; zero-duration은 Foundation 경계에서 구조적으로 유효). adapter는 non-degenerate range를 선호하되 이 선호는 새로운 canonical validation 규칙이 되지 않는다. 저장소의 canonical 시간 단위(현재 float seconds 또는 정확히 확립된 등가물)를 사용한다. Foundation에 media-duration validation·transcript-boundary 정렬·Candidate-to-Finding containment 검사를 추가하지 않는다.

**Canonical Rationale Mapping (Confirmed):** 모든 생성 제안은 canonical rationale을 만든다 — 사람이 검토 가능하고, editorial concern을 식별하며, 제공된 발췌/Finding evidence에 근거하고, 선택한 Candidate Type이 적용되는 이유를 간결히 설명하며, 제공된 내용의 언어를 따르고, 실행 가능한 명령을 포함하지 않는다. adapter는 raw provider explanation, provider 내부 reasoning, chain of thought, hidden reasoning, prompt trace, Review modification content, replacement text, 실행 명령을 rationale로 admit하지 않는다. 고정 template은 first slice에서 요구되지 않으며 rationale은 adapter 수준 정규화/정화 단계로 만들 수 있다. confidence·uncertainty·priority·severity·예상 절감 시간·structured evidence를 위한 canonical 필드를 추가하지 않는다.

**Provider Port and Adapter Boundary (Confirmed):** provider-neutral Port는 provider-독립적 request/result 개념을 노출한다. concrete adapter는 request 구성, 외부 provider 호출, strict structured-output 설정, provider-native 응답 파싱, provider-native 실패 변환, provider-neutral 결과로의 매핑을 소유한다. adapter는 canonical Candidate나 DomainResult를 직접 쓰지 않고, Application Service를 우회하지 않으며, raw provider JSON을 Port로 반환하지 않고, 새로운 Candidate Type 의미를 정의하지 않으며, Review artifact를 만들지 않는다. generation/orchestration service는 canonical 입력 로딩, 승인된 registry 적용, zero/one/many outcome 구분, 유효한 provider-neutral 제안의 `NormalizedCandidateResult` 매핑, caller-owned Candidate·DomainResult identity 계획, 완성된 Application admission 호출, generation-layer outcome 반환을 소유한다. 구조적 선례로 Transcript Correction concrete-provider 구조를 참고하되 그 제품 의미를 가져오지 않는다.

**Prompt Ownership and Versioning (Confirmed):** prompt는 source-controlled, inspectable, versioned이며 concrete provider adapter가 구현 콘텐츠로 소유하고 canonical Edit Candidate domain 계약의 일부가 아니다. prompt는 최소한 승인된 세 Candidate Type key만 열거하고, unknown Type을 금지하며, strict structured output·source grounding을 요구하고, 지어낸 사실·Review decision·실행 편집 명령을 금지하며, chain of thought 대신 canonical rationale을 요청하고, 생성 range를 제공된 context로 제한한다. 이 PATCH는 최종 prompt 문구를 담지 않는다. provider·model·model version·prompt version·output-schema version·secret 참조는 adapter/execution configuration과 execution provenance에 속하며 canonical Candidate 기록에 속하지 않는다. model이나 prompt 변경은 새 UnitExecution/provider attempt를 요구하며 이전 Candidate를 변경하지 않는다.

**Structured Output and Partial Normalization (Confirmed):** concrete adapter는 strict structured output을 사용하고 provider-native 응답을 adapter 내부에서 완전히 파싱한다. provider-neutral 결과는 zero 이상의 제안을 담을 수 있고, 각 제안은 승인된 Candidate Type·비어 있지 않은 근거 rationale·유효한 located range·필수 구조 필드를 검증받는다. top-level malformed 출력은 admission 없이 명시적 provider/normalization failure가 된다. 파싱 가능하나 유효·무효 제안이 섞인 응답에서는 유효 제안은 normalized admission으로 진행하고, 무효 제안은 거부되며, 각 거부는 **명시적으로 표면화**되고, 거부된 제안은 조용히 사라지거나 canonical 기록에 들어가지 않는다. 이는 미분화된 성공이나 전면 provider failure가 아니라 **partial-success generation outcome**으로 정의된다. 최소한 다음을 구분한다: 전 제안 유효 성공, no-Candidate 성공, 유효 Candidate와 거부 제안이 있는 partial success, provider failure, malformed-output failure, 유효 제안이 없는 normalization failure, Application admission failure. partial 거부 진단을 canonical Candidate 필드로 만들지 않으며, 진단을 위해 raw provider 출력을 저장하지 않는다. malformed-output 자동 repair는 first slice에 포함되지 않는다.

**Failure and Retry Contract (Confirmed):** provider transport/외부 서비스 실패(timeout, rate limit, auth 실패, provider 거부, context-length 실패, transport error)는 기존 provider/plugin execution failure category(또는 정확한 저장소 등가물)로 매핑된다. normalization 실패(unknown Candidate Type, blank rationale, invalid range, 누락 필수 필드)와 Application admission 실패는 기존 Application/persistence 경계가 소유한다. retry 정책은 orchestration/execution이 소유한다. adapter는 attempt provenance를 잃는 방식으로 retry를 내부에 숨기지 않는다. 각 retry는 새 provider attempt이며 새 UnitExecution 또는 기존 canonical execution-attempt 메커니즘과 연관되고 `retry_of`(또는 정확한 기존 retry provenance 계약)로 연결된다. malformed-output repair는 지원되지 않으며, 두 번째 호출은 이전 응답의 in-place 변경이 아니라 retry/새 attempt다.

**Execution Provenance and Replay (Confirmed):** provider·model·prompt·configuration provenance는 Edit Candidate 기록 밖에 유지된다. capability identity, provider/plugin 참여, 가능한 경우 configuration identity, execution outcome, failure category, retry 연결에 기존 execution model을 사용한다. **첫 adapter 이전에 새로운 provider-result persistence foundation은 필요하지 않다.** raw provider 응답은 저장되지 않는다. first-slice replay 계약: (1) fake provider Port를 통한 deterministic replay, (2) 주어진 provider-neutral/normalized 결과로부터의 deterministic Application admission, (3) admit된 durable Candidate의 정확한 재구성. replay는 live 외부 model 재호출을 의미하지 않는다. live model 호출은 비결정적이며 replay-safe로 기술되지 않는다. live rerun은 새 reprocessing·새 execution/provider attempt·새 caller-owned Candidate identity·새 immutable Candidate 기록이다. Edit Candidate에 provider provenance 필드를 추가하지 않는다. raw-response Artifact 캡처, normalized provider-result Artifact 캡처, provider-attempt domain 기록, content hash, 정확한 live-provider 재현성은 명시적으로 deferred다.

**Duplicate and Reprocessing (Confirmed):** 반복 provider invocation은 insert-only로 유지된다. first slice는 overwrite·update·Candidate revision·supersession·stale 탐지·current selection·Review reconciliation·cross-run semantic deduplication을 도입하지 않는다. 한 provider 응답 내 정확한 중복은 별개 제안으로 보존되고, 유효하면 별개 caller-owned identity와 결정적 sequence 위치를 가진 별개 Candidate가 된다. 조용한 dedup을 하지 않으며 Candidate 순서는 transport order일 뿐이다.

**Acceptance Boundary (Confirmed):** acceptance는 세 tier로 분리된다. **(1) Deterministic architectural acceptance**(기본 suite 필수) — fake provider Port로 한 Finding invocation, zero/one/many 성공, partial success, generation→admission 흐름, caller-owned identity 계획, persistence, provenance, Review artifact 부재, deterministic replay, provider-native 누출 부재를 검증한다. **(2) Concrete adapter tests**(기본 suite 필수) — 주입된 recorded/fake transport로 request 구성, bounded 입력 context, egress 제한, strict structured-output schema, 파싱, registry 검증, canonical 매핑, malformed-output failure, partial-success 진단, hidden retry 부재, raw-output 누출 부재를 검증한다. **(3) Live provider tests** — 선택적·수동, credentialed, 기본 suite 밖, non-replay-safe, 오직 real provider wiring 검증용. **Product-quality evaluation은 명시적으로 deferred다.** 이 milestone은 architecture/provider-integration 완료로 분류될 수 있으나 production-quality 승인·교육적 검증·편집적 검증으로 분류되지 않는다. hallucination rate·Candidate 유용성·Candidate Type 정확도·range 정확도·rationale 품질에 대한 수치 임계값을 발명하지 않는다.

**Deferred (이후 milestone):** 완결된 Candidate Type taxonomy와 alias, 다중 provider·fallback·selection marketplace/policy, rich configuration binding, prompt-as-Artifact와 prompt 문구, whole-transcript·Lecture Segment·Source Media·Review-history·prior-Candidate context, non-located Finding 생성, whole-recording Candidate, transcript-boundary 정렬, media-duration validation, rationale template·인용·현지화 정책, confidence·uncertainty·priority·severity·예상 절감 시간·structured evidence, raw-response·normalized provider-result·provider-attempt·content-hash persistence, 자동 response repair, adapter 소유 retry, duplicate reconciliation·supersession·stale 탐지·current selection·Review reconciliation, production-quality 임계값·human-evaluation 프로토콜, 완전한 redaction·retention·regional-processing·법적 준거 정책(§18).

### 9.3 Effective-Transcript Generation — Edit Candidate Admission Boundary

이 소절은 `PATCH-0032`로 승인된 Architect Decision(C-1…C-13)을 기록한다. 이 소절은 **`§9`의 Edit Candidate 의미와 `§9.1`의 canonical 기록 계약을 전혀 변경하지 않는다.** 이 소절이 확정하는 것은 오직 **effective-transcript generation에서 Edit Candidate가 무엇에 anchor하고 어떤 전제 아래 admit되는가**이며, 그 세대가 사용하는 provenance 관용구다. 번호가 `§9.2` 다음인 것은 `§9.2`(Concrete Provider, `PATCH-0013`)가 이미 존재하고 그 절 번호를 바꾸면 문서·구현·PATCH 전반의 기존 참조가 깨지기 때문이며, 순서가 의존 관계를 뜻하지 않는다. 결정 번호에 `C-` 접두사를 쓰는 것도 같은 이유다 — `§9.2`가 이미 `D-` 계열을 쓰고 있어 한 절 안에서 번호가 겹치지 않도록 한 표기 구분일 뿐이며 계약상 의미는 없다.

**Contract Generation (Confirmed, C-1):** Edit Candidate admission 경계는 **두 개의 contract generation**으로 존재한다. `§9.1`의 Canonical Anchor·Minimum Payload·Application Foundation·Admission Boundary 문단은 **legacy execution-coupled generation**의 계약이고, 이 소절은 **effective-transcript generation**의 계약이다. legacy 계약과 그 기록은 유효한 역사로 보존되며 삭제·backfill·재해석·소급 변경되지 않는다. 두 세대는 영구히 구분 가능하고, **하나의 contract generation 안에는 정확히 하나의 canonical Edit Candidate admission 경계가 존재한다.** 한 세대의 anchor를 다른 세대의 admission 근거로 교차 사용하지 않는다.

**Canonical Anchor (Confirmed, C-2):** effective-transcript generation에서 모든 Edit Candidate는 **정확히 하나의 canonical Analysis Finding(`§8.2`)**에 anchor한다. `§9.1`이 확정한 anchor의 **cardinality와 방향은 그대로다** — Finding은 필수이고 Candidate는 Finding 없이 존재할 수 없으며, 하나의 Finding이 여러 Candidate의 근거가 될 수 있고, 각 Candidate는 정확히 하나의 Finding을 참조한다. 바뀌는 것은 그 Finding이 **어느 세대의 Finding인가**뿐이다: legacy `§8.1` Finding이 아니라 `§8.2` Finding이다. Candidate는 `Lecture Analysis Input Admission`에 **직접 anchor하지 않으며**(두 번째 직접 anchor를 요구하지 않는다는 `§9.1` 규정 그대로), 필요한 상류 의미는 anchor한 Finding을 통해 확보한다.

**Segmentation Is a Sibling, Never a Parent (Confirmed, C-3):** `§9.1`이 확정한 대로 **Lecture Segment는 이 세대에서도 anchor가 아니고 reference도 아니다.** Segmentation(`§7.2`)과 Analysis Finding(`§8.2`)은 같은 durable analysis input record 종류를 각자 anchor하는 **sibling**이며, Edit Candidate는 그중 **Finding 가지에만** 매달린다. 현행 세대의 관계는 다음과 같다:

~~~text
Lecture Analysis Input Admission
        |
        +----> Analysis Finding (§8.2) ----> Edit Candidate (§9.3)
        |
        +----> Lecture Segmentation (§7.2)
~~~

Segment linkage, 다중 Segment 참조, cross-Segment target, Segment range와의 equality는 `§9.1`의 deferred 상태 그대로 유지된다. Segmentation이 존재하지 않아도 Edit Candidate는 완전히 유효하며, 그 반대도 같다.

**Current-Only Admission Standing (Confirmed, C-4):** Candidate admission은 **저장된 Finding이 존재한다는 사실만으로 허용되지 않는다.** anchor한 Finding이 매달린 `Lecture Analysis Input Admission`의 **현재 authority standing을 prepare 또는 admission 시점에 재평가**해야 하며, 그 파생 standing이 **`current`일 때만** admit된다. `superseded_by_authority_change`와 `current_authority_ineligible`은 명시적 거부 사유다. 이 파생 vocabulary는 released GOAL-023 계약이 정의한 **정확히 세 값**이며 이 소절은 어떤 값도 추가하지 않는다. Finding identity가 존재하지 않거나 canonical 형식에 맞지 않는 경우는 **네 번째 standing 값이 아니라** 참조 자체의 거부로 다루며, standing 평가 이전에 실패한다. standing은 Candidate가 아니라 **anchor 연쇄의 뿌리**에서 파생된다는 점에 유의한다: Candidate → Finding → Admission.

**No Stored Currentness (Confirmed, C-5):** standing은 **파생 관측**이며 저장 상태가 아니다. 이 소절은 Candidate 기록에도, 그 anchor에도 mutable status·current flag·stale flag·lifecycle state·Review 상태를 **추가하지 않으며, 추가하는 방향을 금지한다**(`§9.1`의 "lifecycle state, Review 상태, 가변 상태를 가지지 않는다"와 정합). standing 관측은 어떤 기록도 변경하지 않는다.

**Historical Semantics (Confirmed, C-6):** superseded Admission, 그에 매달린 Finding, 그리고 그 Finding에 매달린 Candidate는 모두 **유효한 immutable history**로 남으며 삭제·무효화·재작성되지 않는다. **기존 Edit Candidate는 upstream authority가 변경되었다는 이유로 수정·삭제·재작성되지 않는다** — 이는 `§9.1` Reprocessing이 "이전 Candidate identity에 연결된 기존·미래의 Review provenance는 계속 주소 지정 가능해야 한다"고 요구한 바를 그대로 충족한다. 금지되는 것은 **standing이 `current`가 아닌 연쇄에 대한 새로운 Candidate admission**뿐이다. authority가 이전에 admit된 revision으로 되돌아오면 동일한 canonical Admission identity가 다시 `current`가 되고 admission 가능성은 파생 규칙에 의해 복원된다(GOAL-023의 returning-authority convergence).

**Execution-Free Deterministic Provenance (Confirmed, C-7):** effective-transcript generation의 Edit Candidate Foundation은 `ProcessingRun`, `ProcessingUnit`, `UnitExecution`, RUNNING state, execution lifecycle, 그리고 **`DomainResultReference` provenance**를 **요구하지 않는다.** 마지막 항목이 `§8.2`·`§7.2`와 다른 지점이다: `§9.1`은 DomainResultReference를 payload 항목으로 열거했으나, `§8.2` Finding은 DomainResult를 만들지 않으므로 이 세대에는 참조할 upstream DomainResult가 **존재하지 않는다**. 가짜 실행 기록·synthetic Processing Run·합성 RUNNING state·합성 DomainResult를 provenance로 사용하는 것은 **금지된다**(`040 §18` H-10, `041 §15` E6의 명시적 금지). 대신 Candidate의 생성 provenance는 다음 성질을 가져야 한다: **deterministic**, **local**, **replay-safe**, **identity-owning**, canonical 기록 경계에서 **provider-independent**, wall-clock 비의존, 무작위 실행 identity 없음. 결정적으로 파생된 실행 마커를 기록할지(`040 §14` A-3 / `040 §17` K-4 관용구) 실행 마커 없는 provenance를 사용할지(`041 §15` E6, `§8.2` D-6, `§7.2` S-7 관용구)는 **구현 선택**이며 이 소절은 어느 한쪽을 강제하지 않는다.

**Upstream Provenance Through the Anchor (Confirmed, C-8):** `§9.1` Minimum Payload가 요구한 **필수 Source Media provenance와 Source Timeline provenance는 이 세대에서도 요구된다** — 사라지지 않는다. 달라지는 것은 그것을 **담는 형태**다: 이 세대에서 그 provenance는 anchor 연쇄 `Edit Candidate → Analysis Finding(§8.2) → Lecture Analysis Input Admission → current applicable Corrected Revision → parent Raw Transcript → Source Timeline → Source Media`를 통해 확보되며, Candidate 기록이 그 값을 **직접 컬럼으로 중복 복제해야 한다는 뜻은 아니다**(`§8.2` D-2와 `§7.2` S-2가 확립한 "anchor를 통해 상속하고 복제하지 않는다" 선례). 구현이 조회 편의를 위해 일부를 denormalize할지는 구현 선택이며 이 소절은 어느 쪽도 강제하지 않는다. 다만 어떤 형태를 택하든 **Source Timeline traceability(EC-008)는 유지되어야 하고**, 정규화된 결과의 Source Timeline은 anchor한 Finding의 Source Timeline 계보와 일치해야 한다는 `§9.1`의 요구도 그대로 유지된다.

**Candidate Record Contract Preserved (Confirmed, C-9):** `§9.1`이 확정한 canonical Edit Candidate 기록의 의미는 이 세대에서도 **그대로 상속된다**: optional·evaluative·advisory한 분석 파생 제안이며 durable canonical domain record로 **immutable**, **identity-owning**, **provenance-bearing**, **replay-safe**, **provider-independent**, **insert-only**이고, lifecycle state·Review 상태·가변 상태·삭제 동작·revision 필드·supersession 필드·rejected-candidate 상태를 가지지 않는다. **Source Timeline Time Range는 문언 그대로 유지된다** — 정확히 하나의 필수 range, finite, non-negative, `start <= end`, Finding의 선택적 range와 같을 필요 없고 Finding에 range가 없어도 필수이며, 전체 녹음 range는 유효하고 zero-duration range는 구조적으로 유효하나 특별한 canonical 의미가 없다. 필수 **Candidate Type**(open key, Application 소유, closed enum·고정 taxonomy 아님)과 필수 **rationale**(canonical·provider-independent·비어 있지 않은·사람이 검토 가능한 텍스트이며 provider 내부 reasoning·chain of thought·실행 명령·Review modification content가 아니다)의 의미와 경계도 그대로다. 이 소절은 media-duration validation, transcript-boundary 정렬, Candidate-to-Finding containment 검사, range reconciliation을 **추가하지 않는다**(`§9.2`가 Foundation에 그러한 검증을 추가하지 않는다고 확정한 바와 정합한다). 이 소절이 재범위화하는 것은 **anchor의 세대, admission 전제, 그리고 provenance 표현 형태뿐**이다.

**Identity Direction (Confirmed, C-10):** Candidate identity는 **Application이 소유**한다. provider가 반환한 식별자, execution framework의 식별자, UUID, timestamp, rowid, 물리 경로, mutable currentness state는 canonical identity에 참여하지 않는다. identity는 **immutable anchor(Finding)와 안정적인 Candidate 의미**에만 기반해야 한다. **정확한 hash 구성은 이 소절에서 확정하지 않고 구현 milestone에 위임한다**(`041 §15` E7, `§8.2` D-8, `§7.2` S-10의 선례). 이 위임은 위 원칙이 이미 규범으로 닫혀 있으므로 구현을 막지 않는다. 다만 구현은 identity에 참여하는 semantic 필드와 참여하지 않는 필드를 명시하고, 그 선택이 C-11의 conflict 분기를 도달 가능하게 하는지를 기록해야 한다. 두 경우는 다음과 같다: **(A)** 저장되는 canonical semantic 필드 중 일부가 identity에 참여하지 않으면, 동일 identity에 대한 semantic 불일치가 정상 입력으로 도달 가능하며 그때는 반드시 명시적 conflict여야 한다. **(B)** 저장되는 모든 canonical semantic 필드가 identity에 참여하면 그 불일치는 hash collision을 제외하고 구조적으로 도달 불가능하다. **(B)를 택하더라도 semantic equality 검사를 제거하지 않는다** — 손상되거나 손으로 편집된 행에 대한 유일한 방어이기 때문이다. 어느 쪽을 택했고 왜 계약과 일치하는지는 구현 문서에 기록한다.

**Replay and Conflict (Confirmed, C-11):** **동일 Finding + 동일 contract version + 동일한 canonical Candidate 내용 → 동일한 canonical Candidate identity로 수렴**하며 중복 기록을 만들지 않는다. 다음은 별개의 Candidate가 될 수 있다: 다른 Finding, 다른 Candidate Type, 다른 rationale, 다른 Time Range, 그 밖에 계약상 identity에 포함되는 의미적 내용의 변경. 동일 identity에 대해 **의미가 다른 payload**가 제출되면 덮어쓰지 않고 **명시적 conflict**로 거부한다(released collision-convergence 관용구, `040 §18` H-9). 근접 동시 동일 admission은 중복 canonical Candidate 없이 수렴한다. 하나의 Finding에 대해 여러 Candidate를 순서 있게 admit하는 경우 `§7.2` S-9가 확립한 ordered-batch 관용구(batch 위치가 곧 ordinal, batch는 원자적으로 기록)를 재사용할 수 있으며, 그 채택 여부와 ordinal의 identity 참여는 구현 milestone이 C-10에 따라 명시한다.

**Persisted Representation (Confirmed, C-12):** 이 소절은 canonical Candidate 기록의 **의미**만 확정하며 물리적 저장 형태를 확정하지 않는다. 다만 legacy `edit_candidates` 관계는 legacy 세대의 anchor와 실행 provenance(legacy Analysis Finding, `ProcessingRun`, `UnitExecution`, `DomainResult`)를 **필수 컬럼으로 요구**하므로, effective-transcript generation의 Candidate를 그 관계에 기록하려면 C-7이 금지한 값을 날조해야 한다. 따라서 이 세대의 Candidate는 **legacy 관계를 재사용하지 않으며**, 필요한 저장 형태는 `041 §15` E1, `§8.2` D-11, `§7.2` S-12의 선례를 따라 **strictly additive한 새 versioned representation**으로 도입한다. legacy 관계와 그 행은 backfill·dual-write·재해석 없이 자기 세대의 canonical 표현으로 남는다. 정확한 이름과 컬럼 구성은 구현 milestone이 선택한다.

**Sections Not Re-scoped (Confirmed, C-13):** 이 소절은 **`§9.2`(Concrete Edit Candidate Generation Provider)를 재범위화하지 않는다.** `§9.2`는 `§9.1` 위에서 동작하는 legacy 세대의 provider-generation 계약으로 변경 없이 유지되며, running unit execution·`retry_of`·execution provenance에 대한 그 요구도 그대로다. **`§9.3` 위에서 동작하는 구체적 Candidate Generation Provider는 이 소절이 확정하지 않았고**, 그 milestone이 일정에 오를 때 자기 generation 범위 결정이 필요하다. Review(`043`), Export(`044`), Final Selection, Approved Edit Decision, Analysis Execution, Processing Model도 마찬가지로 재범위화되지 않는다. *(후속 기록: `043 §7.4`의 Review admission 경계는 이후 `PATCH-0033`이 `043 §7.5`로 재범위화했다. C-13이 당시 재범위화하지 않았다는 사실은 그대로 유효하며, `§7.4`의 legacy 계약도 `§7.5` R-1에 따라 자기 세대에서 여전히 유효하다. Export(`044`)·Final Selection·Analysis Execution·Processing Model은 여전히 재범위화되지 않았다.)* *(후속 기록, `PATCH-0035`: Export(`044`) 중 이 세대의 **Edit Export admission 경계**는 `044 §23`(EA-1…EA-11)이 재범위화했다 — `044 §21` Artifact와 `§22` serialization의 이 세대 연결, Analysis Execution, Processing Model은 여전히 재범위화되지 않았다. **위에 열거된 `Final Selection`은 재범위화 대기 항목이 아니다**: `044 §23` EA-11이 확정한 대로 Edit Pipeline에 Final Selection이라는 제품 개념은 legacy 세대에도, 이 세대에도, 미래 기능으로도 **존재하지 않는다.** 이 목록의 그 라벨은 만들어질 무엇도 지시하지 않으며, 위 문장은 당시 기록으로 그대로 보존된다. `041`의 Final Subtitle과 그 선택은 다른 Pipeline의 계약으로 영향받지 않는다.)* 그 결정들은 이 소절이 아니라 그때의 승인된 PATCH가 내린다.

**Deferred (이후 milestone):** Segment Label linkage와 label taxonomy, 다중 Finding·다중 Segment·many-to-many provenance, 다중 range·discontinuous·non-timeline·cross-Segment target, confidence·uncertainty·priority·severity·예상 절감 시간·structured evidence·source/replacement text·proposed treatment operation·실행 가능한 편집 명령, Candidate revision·supersession·stale 탐지·Review reconciliation·current-candidate selection, Candidate ranking·conflict resolution·merge policy, Review CandidateReference·Review Item·Review 상태·Accept/Reject/Modify·Approved Edit Decision(`043`), Final Selection과 Export(`044`), GUI editing과 human editing, 이 세대의 구체적 Candidate Generation Provider·prompt·model·AI 호출, Analysis Execution lifecycle(§18). 이들 중 어느 것도 이 소절이 확정한 admission 경계의 전제가 아니므로 effective-transcript Edit Candidate Foundation 구현을 막지 않는다.

*(후속 기록, `PATCH-0035`: 위 목록의 "**Final Selection과 Export(`044`)**" 항목에 대해 두 가지를 명시한다. **Export**는 실재하는 deferred 항목이었고 그중 이 세대의 **Edit Export admission 경계**는 `044 §23`이 확정했다(`§21`·`§22` 연결은 그대로 deferred). **Final Selection**은 deferred 항목이 **아니었다** — `044 §23` EA-11이 확정한 대로 Edit Pipeline에 그런 제품 개념은 존재하지 않으며, 승인 편집은 상호배타적 대안이 아니라 집합의 상호보완적 원소이고 어느 판단이 유효한지는 `043 §7.6`이 이미 Candidate 단위로 파생한다. 위 문장은 당시 기록으로 보존되며 그 라벨은 미래 작업을 지시하지 않는다.)*

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
- 첫 milestone(Lecture Analysis Input Eligibility)의 admission authority와 Eligible Analysis Input의 durable·canonical 성격은 `§5.1`(`patches/PATCH-0009`)에서 확정되었다. 아래 Requires-Validation 항목은 이후 milestone에 대해 여전히 열려 있다.
- 첫 Analysis milestone(Analysis Finding Application Foundation)의 Analysis Finding canonical 기록·anchor·Finding Type·evidence·confidence·Application 경계·admission은 `§8.1`(`patches/PATCH-0010`)에서 확정되었다. Finding의 최소 안정적 참조 단위는 `§8.1`의 anchor(하나의 `EligibleAnalysisInput` + 선택적 Source Timeline range)로 확정되었다. taxonomy·confidence 계산·revision·supersession·segmentation·multi-range·구체적 Provider 등은 여전히 deferred다.
- 첫 Segmentation milestone(Lecture Segmentation Application Foundation)의 Lecture Segment canonical 기록(durable·immutable·identity-owning·insert-only·provenance-bearing·replay-safe·provider-independent)·anchor(ELIGIBLE `EligibleAnalysisInput` 정확히 하나 + 필수 단일 Source Timeline Time Range)·reprocessing(insert-only)·Application 경계·admission은 `§7.1`(`patches/PATCH-0011`)에서 확정되었다. Segment Label·label taxonomy·다중 segmentation view·grouping·confidence/uncertainty/rationale semantics와 그 귀속·overlap/nesting/hierarchy/multi-range·revision·supersession·구체적 Provider 등은 여전히 deferred다.
- 첫 Candidate milestone(Edit Candidate Application Foundation)의 Edit Candidate canonical 기록(durable·immutable·identity-owning·insert-only·provenance-bearing·replay-safe·provider-independent)·anchor(정확히 하나의 Analysis Finding, Segment 비참조)·필수 단일 Source Timeline Time Range·필수 open Candidate Type과 rationale·reprocessing(insert-only)·Application 경계·admission·Review-handoff 경계는 `§9.1`(`patches/PATCH-0012`)에서 확정되었다. Segment Label linkage·다중 Finding/Segment·다중 range·confidence/uncertainty/priority/severity/예상 절감 시간·proposed treatment/replacement·revision·supersession·stale 탐지·Review reconciliation·Review 상태와 Accept/Reject/Modify·구체적 Provider 등은 여전히 deferred다.
- 첫 Candidate Provider milestone(Concrete Edit Candidate Generation Provider — First Slice)의 provider-generation 계약은 `§9.2`(`patches/PATCH-0013`)에서 확정되었다: provider-neutral generation Port + 하나의 concrete adapter + deterministic fake, 한 invocation당 하나의 Analysis Finding, zero/one/many 및 partial-success outcome(빈 batch는 admission 미호출로 §9.1 empty-batch 거부 불변), Application/generation 소유 closed first-slice Candidate Type registry(`non_lecture_region`·`redundant_restatement`·`delivery_concern`; canonical 필드는 여전히 open key), bounded 발췌-only 입력과 보수적 외부 egress 경계, canonical 기록 밖의 execution provenance, fake 기반 deterministic replay(live 호출은 replay-safe 아님), raw-response 미저장, 3-tier acceptance. **§9.1 Application Foundation은 변경되지 않는다.** 완결 taxonomy·alias·다중 provider·prompt 문구·whole-transcript/Segment/Media context·non-located 생성·raw/normalized/attempt persistence·자동 repair·product-quality 임계값·완전한 privacy/retention/compliance 정책 등은 여전히 deferred다.
- effective-transcript generation의 Analysis Finding admission 경계는 `§8.2`(`patches/PATCH-0030`)에서 확정되었다: Analysis Finding admission 경계는 legacy execution-coupled generation과 effective-transcript generation의 **두 contract generation**으로 존재하며(`§5.1.1`, `§8.2` D-1) 두 세대는 영구히 구분 가능하다. 현행 세대에서 Finding은 legacy `EligibleAnalysisInput`이 아니라 **정확히 하나의 immutable `Lecture Analysis Input Admission`**에 anchor하고(D-2), 그 Admission의 파생 standing이 **`current`일 때만** admit되며(D-3; released 파생 vocabulary는 정확히 `current`·`superseded_by_authority_change`·`current_authority_ineligible` 세 값이고 이 소절은 값을 추가하지 않는다), standing은 저장되지 않는 파생 관측이고 Admission 기록에 mutable status를 추가하지 않는다(D-4). superseded Admission과 기존 Finding은 **유효한 immutable history**로 보존되며 authority 변경이 기존 Finding을 수정하지 않고, authority가 이전 revision으로 복귀하면 동일 canonical Admission identity가 다시 current가 되어 admission 가능성이 파생 규칙으로 복원된다(D-5). 현행 세대는 `ProcessingRun`·`UnitExecution`·RUNNING state를 요구하지 않고 가짜 실행 기록을 금지하며 deterministic·local·replay-safe·identity-owning provenance를 사용한다(D-6). **`§8`의 Finding 의미와 `§8.1`의 canonical Finding 기록 계약은 변경되지 않는다**(D-7). identity 원칙과 replay/conflict 의미는 확정되었고 정확한 hash 구성은 구현에 위임된다(D-8, D-9). Finding currentness는 저장 상태로 도입되지 않는다(D-10). 현행 세대의 Finding은 legacy `analysis_findings` 관계를 재사용하지 않고 strictly additive한 새 versioned representation으로 기록되며(D-11), `§8.2`는 `§7.1`·`§9.1`의 admission 경계를 재범위화하지 않는다(D-12). 위 세대 구분에 따라, 바로 앞 항목이 기록한 **Finding의 최소 안정적 참조 단위**(하나의 durable analysis input + 선택적 Source Timeline range)는 **cardinality 규칙으로서 두 세대에 공통이며, 그 자리를 차지하는 record만 세대별로 다르다**(legacy = `EligibleAnalysisInput`, effective-transcript = `Lecture Analysis Input Admission`). canonical analysis unit, Analysis Execution lifecycle, 구체적 Analysis Provider, Finding taxonomy 폐쇄와 LI-001…LI-012 조정, confidence 계산, revision·supersession·reconciliation, current-Finding selection 등은 **여전히 deferred**다.
- effective-transcript generation의 Lecture Segmentation admission 경계는 `§7.2`(`patches/PATCH-0031`)에서 확정되었다: Segmentation admission 경계도 legacy execution-coupled generation과 effective-transcript generation의 **두 contract generation**으로 존재하며(`§5.1.1`, `§7.2` S-1) 두 세대는 영구히 구분 가능하다. 현행 세대에서 Segment는 legacy `EligibleAnalysisInput`이 아니라 **정확히 하나의 immutable `Lecture Analysis Input Admission`**에 anchor하고(S-2), **`§7.1`이 확정한 Finding 무참조 독립성은 그대로 보존된다** — Segmentation과 Analysis Finding(`§8.2`)은 같은 Admission을 각자 anchor하는 **sibling**이며 어느 쪽도 다른 쪽의 parent가 아니다(S-3). anchor Admission의 파생 standing이 **`current`일 때만** admit되고(S-4; released 3값 vocabulary를 확장하지 않으며 없거나 malformed인 참조는 standing 값이 아니다), standing은 저장되지 않는 파생 관측이다(S-5). superseded Admission과 기존 Segment는 **유효한 immutable history**로 보존되고 authority 복귀 시 admission 가능성이 파생 규칙으로 복원된다(S-6). 현행 세대는 `ProcessingRun`·`UnitExecution`·RUNNING state·`DomainResult` chaining을 요구하지 않고 가짜 실행 기록을 금지한다(S-7). **`§7`의 Segment 의미와 `§7.1`의 canonical 기록 계약(Minimum Boundary의 필수 단일 Time Range, `start <= end`, Segment 간 관계 미모델링, per-admission `sequence`의 의미를 포함)은 변경되지 않으며**, media-duration·transcript-boundary·full-coverage·overlap 금지 검증을 추가하지 않는다(S-8). identity를 소유하는 canonical 객체는 개별 Segment이고 aggregate·view identity는 도입하지 않으며, 하나의 admission은 순서 있는 batch를 원자적으로 기록한다(S-9). identity 원칙과 replay/conflict 의미는 확정되었고 정확한 hash 구성은 구현에 위임된다(S-10, S-11). legacy `lecture_segments` 관계는 재사용하지 않고 strictly additive한 새 versioned representation을 도입한다(S-12). `§9.1` Edit Candidate·Review·Export·Analysis Execution은 재범위화되지 않았다. Segment Label과 taxonomy, 다중 segmentation view·grouping aggregate, overlap·계층·multi-range, revision·supersession·reconciliation, current-segmentation selection, 구체적 segmentation provider, Segment-Finding linkage 등은 **여전히 deferred**다.
- effective-transcript generation의 Edit Candidate admission 경계는 `§9.3`(`patches/PATCH-0032`)에서 확정되었다: Edit Candidate admission 경계도 legacy execution-coupled generation과 effective-transcript generation의 **두 contract generation**으로 존재하며(`§5.1.1`, `§9.3` C-1) 두 세대는 영구히 구분 가능하다. 현행 세대에서 Candidate는 **정확히 하나의 `§8.2` canonical Analysis Finding**에 anchor하고(C-2; anchor의 cardinality와 방향은 `§9.1` 그대로이며 바뀌는 것은 Finding의 세대뿐이다), **Lecture Segment는 이 세대에서도 anchor도 reference도 아니다** — Segmentation(`§7.2`)과 Finding(`§8.2`)은 sibling이고 Edit Candidate는 Finding 가지에만 매달린다(C-3). anchor 연쇄 뿌리의 `Lecture Analysis Input Admission` 파생 standing이 **`current`일 때만** admit되고(C-4; released 3값 vocabulary를 확장하지 않으며 없거나 malformed인 참조는 standing 값이 아니다), standing은 저장되지 않는다(C-5). superseded 연쇄의 Admission·Finding·Candidate는 모두 **유효한 immutable history**로 보존되며 authority 복귀 시 admission 가능성이 파생 규칙으로 복원된다(C-6). 현행 세대는 `ProcessingRun`·`UnitExecution`·RUNNING state에 더해 **`DomainResultReference` provenance도 요구하지 않는다** — `§8.2` Finding이 DomainResult를 만들지 않아 참조할 upstream result 자체가 없기 때문이며, 이 점이 `§8.2`·`§7.2`와 다른 지점이다(C-7). `§9.1`이 요구한 Source Media·Source Timeline provenance는 **사라지지 않고** anchor 연쇄를 통해 확보되며 표현 형태만 달라진다(C-8). **`§9`의 Edit Candidate 의미와 `§9.1`의 canonical 기록 계약(필수 단일 Time Range와 그 불변식, open Candidate Type, rationale, insert-only, lifecycle/Review 상태 부재를 포함)은 변경되지 않는다**(C-9). identity 원칙과 replay/conflict 의미는 확정되었고 정확한 hash 구성과 conflict 도달 가능성 판단은 구현에 위임된다(C-10, C-11). legacy `edit_candidates` 관계는 재사용하지 않고 strictly additive한 새 versioned representation을 도입한다(C-12). **`§9.2`(Concrete Provider)는 재범위화되지 않았고** 이 세대의 구체적 provider는 별도 결정을 요구하며, Review·Export·Final Selection·Approved Edit Decision도 마찬가지다(C-13). Segment Label linkage, 다중 Finding/Segment/range, confidence·priority·예상 절감 시간, revision·supersession·stale 탐지·current-candidate selection, ranking·conflict resolution·merge policy, Review와 Export, 이 세대의 AI provider 등은 **여전히 deferred**다. *(후속 기록: 이 세대의 Review는 이후 `043 §7.5`(`PATCH-0033`)와 `§7.6`(`PATCH-0034`)이, Edit Export의 **admission 경계**는 `044 §23`(`PATCH-0035`)이 확정했다. `044 §21`·`§22`의 이 세대 연결과 `§9.2` 구체 provider는 그대로 재범위화되지 않았다. C-13이 Review·Export와 나란히 열거한 **`Final Selection`은 `044 §23` EA-11에 의해 존재하지 않는 개념으로 확정되었으므로 deferred 항목이 아니다.**)* *(후속 기록, `PATCH-0036`: 위 note가 "그대로 재범위화되지 않았다"고 한 `044 §21`·`§22` 중 **`§21` Artifact의 이 세대 연결**은 이후 `044 §24`(AR-1…AR-11)가 확정했다. **`§22`의 이 세대 연결**과 `§9.2` 구체 provider는 그대로다.)*

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
