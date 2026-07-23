# 030_DATA_MODEL

- Status: Draft
- Version: Blueprint 0.1
- Last Updated: 2026-07-14
- Layer: L1 — Conceptual Data Model
- Depends On:
  - `000_MANIFESTO.md`
  - `001_PRODUCT.md`
  - `002_FAQ.md`
  - `003_VISION.md`
  - `004_PRINCIPLES.md`
  - `020_PRODUCT_REQUIREMENTS.md`
  - `021_SYSTEM_CONTEXT.md`
  - `../patches/PATCH-0001-l0-and-prd-stabilization.md`
- Referenced By:
  - `031_ARCHITECTURE.md`
  - `040~044` Pipeline Documents

## Purpose

이 문서는 LectureOS의 Conceptual Data Model을 정의한다. 제품 세계의 핵심 개념, 각 개념의 의미와 책임, 개념 사이의 관계, 원본에서 파생 결과까지의 계보를 설명한다.

이 문서는 물리적 또는 논리적 저장 schema가 아니다. 테이블, 필드, ID 형식, 파일 포맷, API payload, 상태 enum, 저장 기술, UI state, 컴포넌트 구조는 정의하지 않는다. 이 개념 모델을 구현 경계로 옮기는 책임은 후속 Architecture와 Pipeline 문서에 있다.

## 1. Modeling Scope

### Included

- Source Media와 Source Timeline
- 시간 기반 개념이 공유하는 Time Range
- Raw Transcript와 Corrected Transcript
- Subtitle, Subtitle Unit, Final Subtitle
- Lecture Segment를 통한 강의 구조 표현
- Edit Candidate
- 통합 Review, Review Item, Review Decision, Modification
- Final Subtitle과 Approved Edit Decision
- Artifact와 외부 export
- Processing Run, 처리 상태, Failure, Diagnostic, Validation Result, Uncertainty
- identity, revision, provenance, lineage, 재처리 전후의 연속성

### Excluded

- 데이터베이스와 파일 schema
- 테이블, 컬럼, key, index, ID 형식
- API, DTO, serialization, event schema
- 컴포넌트, 서비스, 패키지, 배포 구조
- 저장 엔진과 디렉터리 구조
- UI layout과 UI state model
- 외부 NLE의 내부 데이터 모델
- FCPXML 구조와 실제 컷 적용 모델
- 구체적인 label taxonomy, confidence threshold, Subtitle 임계값

## 2. Conceptual Overview

~~~text
선택적 Project Context
        |
        v
Source Media ─────────────> Source Timeline / Time Range
        |                              |
        +----> Transcript Lineage -----+----> Subtitle Lineage
        |                                      |
        |                                      v
        |                                  Review 대상
        |
        +----> Lecture Segment --------+----> Edit Candidate
                                               |
Transcript / Subtitle / Edit Candidate / Failure / Uncertainty
        |
        v
Review Item
        |
        v
Review Decision: Accept / Reject / Modify
        |
        v
Final Subtitle / Approved Edit Decision
        |
        v
Artifact / Export

Processing Run ── 생성 근거와 처리 상태를 연결하되 위 개념의 정체성을 독점하지 않음
~~~

이 그림은 개념 사이의 관계를 보여준다. 내부 처리 순서, 컴포넌트, 서비스 또는 저장 구조를 뜻하지 않는다. Text Pipeline과 Edit Pipeline은 같은 Source Media와 Review 책임을 공유하는 동등한 제품 흐름이다.

## 3. Identity and Lineage

### 3.1 Conceptual Identity

Source Media, 시간 기반 표현, Transcript와 Subtitle의 revision, Lecture Segment, Edit Candidate, Review Item, Review Decision, 승인 결과, Artifact, Processing Run은 각자의 의미가 재처리 전후에도 구별되고 추적될 수 있어야 한다.

안정적 식별은 다음을 가능하게 해야 한다.

- 같은 원본과 그 파생 결과를 연결한다.
- AI가 생성한 결과와 사용자가 변경한 결과의 출처를 구분한다.
- 재처리로 새 결과가 생겨도 이전 결과와 사용자 결정을 찾을 수 있다.
- 현재 결과가 무엇을 대체했는지 또는 무엇에서 파생됐는지 설명한다.
- 외부 export가 원본 시간축과 승인 결정으로 되돌아갈 수 있게 한다.

구체적인 식별자 형식은 정의하지 않는다. 외부 provider 또는 NLE가 부여한 ID는 provenance의 일부가 될 수 있지만 LectureOS 개념의 유일한 identity가 될 수 없다.

### 3.2 Provenance and Revision

Provenance는 결과가 어떤 Source Media, AI 결과, 처리 조건, 사용자 수정과 결정에서 왔는지를 나타내는 개념적 연결이다. Revision은 같은 목적의 표현이 변경되었을 때 이전 상태를 덮어쓰지 않고 비교와 계보를 유지하기 위한 개념이다.

모든 중간 결과를 영구 보존하는 정책을 이 문서에서 확정하지는 않는다. 다만 승인된 결과를 설명하고 안전하게 재생성하는 데 필요한 계보와 사용자 결정은 잃지 않아야 한다.

### 3.3 Continuity Across Reprocessing

Processing Run이 바뀌면 AI 후보와 파생 결과는 달라질 수 있다. 이때 기존 사용자 결정은 자동으로 새 후보의 결정이 되지도, 암묵적으로 삭제되지도 않는다. 기존 결정과 새 후보의 적용 가능성 또는 충돌은 추적 가능해야 하며, 구체적인 reconciliation 규칙은 후속 문서에서 정한다.

## 4. Project and Processing Context

### 4.1 Project Context

Project Context는 하나의 후반작업 목적 아래 Source Media, 선택적 강의 맥락, 처리 설정, 용어·교정 컨텍스트, 사용자 결정을 이해하기 위한 상위 작업 문맥이다.

`Project`와 `Lecture`를 별도 개념으로 확정할 근거는 아직 부족하다. 따라서 이 문서에서는 **Project Context**를 최소 상위 문맥으로 사용하며, 별도 교육 관리 개념인 Course, Student, Classroom을 추가하지 않는다.

### 4.2 Optional Lecture and Correction Context

강의 주제, 프로젝트 metadata, 고유명사, 전문용어와 같은 선택적 맥락은 후보 생성과 Review를 보조할 수 있다. 이 맥락은 원본 미디어의 물리적 근거나 사용자 결정을 대체하지 않는다. 구체적인 구성은 정의하지 않는다.

### 4.3 Processing Run

Processing Run은 특정 입력과 처리 조건에서 결과가 생성된 문맥이다. 결과의 provenance와 처리 상태를 설명하지만 지속되는 도메인 개념의 identity를 소유하지 않는다.

## 5. Source Media and Timeline

### 5.1 Source Media

Source Media는 LectureOS가 입력받는 원본 영상 또는 오디오이며 촬영된 물리적 사실의 최상위 근거다. LectureOS는 이를 파생 처리로 변경하거나 덮어쓰지 않는다.

외부 파일 시스템은 실제 파일의 보관, 이동, 삭제와 수명주기를 소유할 수 있다. LectureOS는 Source Media를 안정적으로 참조하고 파생 결과와 연결할 책임을 가진다. 파일 수명주기의 구체적인 책임 분담은 Requires Validation이다.

### 5.2 Source Timeline

Source Timeline은 Source Media에 존재하는 발화와 사건의 원본 시간 기준이다. Transcript, Subtitle, Lecture Segment, Edit Candidate, Review 대상, Approved Edit Decision 같은 시간 기반 개념이 공유하는 추적 기준이다.

추출 오디오, 재인코딩 미디어 또는 다른 파생 표현이 존재하더라도 Source Timeline과의 연결을 잃지 않아야 한다. Source Timeline은 편집 도구의 UI Timeline을 뜻하지 않으며, 편집 후 시간축과 동일한 개념으로 취급하지 않는다.

### 5.3 Time Range

Time Range는 Source Timeline 위에서 시작과 끝을 갖는 개념적 범위다. 여러 시간 기반 개념이 같은 원본 구간을 가리키기 위해 사용할 수 있다.

이 문서는 시간 단위, timestamp 표현, frame rate 계산, 경계 포함 규칙을 정하지 않는다. AI가 의미 경계를 제안할 수는 있지만 최종 Time Range의 구조적 유효성은 검증되어야 한다.

## 6. Transcript Model

### 6.1 Raw Transcript

Raw Transcript는 ASR backend가 반환한 변경 전 인식 결과다. provider의 원래 결과, 출처, 가능한 시간 정보와 confidence 또는 불확실성을 보존한다. 최종 텍스트나 사용자 승인 결과가 아니다.

교정 또는 후속 처리는 Raw Transcript를 덮어쓰지 않는다. provider 고유 표현은 provenance로 보존할 수 있지만 중심 개념을 규정하지 않는다.

### 6.2 Corrected Transcript

Corrected Transcript는 원본 발화의 의미를 사람이 읽고 교정할 수 있도록 표현한 언어 계층이다. Raw Transcript에서 시작해 교정 후보, 구조 검증, 사용자 판단을 반영할 수 있으며 Raw Transcript와 Source Media까지의 계보를 유지한다.

Corrected Transcript는 Subtitle이 아니다. 발화 의미 보존과 교정이 주 책임이며, 학생에게 표시할 줄 분할, 읽기 속도, 표시 시간은 Subtitle의 책임이다.

### 6.3 Transcript Unit

Transcript Unit은 Transcript 안의 발화 또는 텍스트를 안정적으로 참조하기 위한 최소 개념적 단위의 자리다. 이 문서는 그 단위를 Word, Utterance, Sentence, Block 중 하나로 확정하지 않는다.

원본 시간축 기반 발화·단어 데이터는 Transcript Unit이 Source Timeline의 어디에 존재하는지 추적하는 시스템 기준 정보다. `Word Timeline`을 확정 용어로 사용하지 않는다. 후속 Pipeline 문서는 시간 추적, 교정 계보, Review 연결에 필요한 최소 단위와 정식 명칭을 정해야 한다. `Segment`는 Lecture Segment와 혼동되므로 Transcript 단위의 대표 용어로 사용하지 않는다. Analysis Finding의 최소 참조 단위는 `042_LECTURE_INTELLIGENCE_PIPELINE.md §8.1`(`patches/PATCH-0010`)에서 확정되었다(하나의 Eligible Analysis Input + 선택적 Source Timeline range).

### 6.4 Speaker Information

Speaker Information은 발화의 화자 맥락을 나타낼 수 있는 선택 정보다. 현재 상위 요구사항만으로는 V1 중심 개념인지 확정할 수 없다. Speaker diarization을 새 V1 기능으로 추가하지 않으며 필요성과 정확도 기대는 Requires Validation이다.

## 7. Subtitle Model

### 7.1 Subtitle

Subtitle은 학생의 시청 가독성을 위해 구성된 시간 기반 표시 결과다. Corrected Transcript를 그대로 복사한 것이 아니며, 의미 경계, 발화 호흡, 줄 분할, 읽기 속도, 표시 길이, 타이밍 규칙의 영향을 받는 파생 표현이다.

### 7.2 Subtitle Unit

Subtitle Unit은 특정 Time Range에 표시되는 하나의 자막 단위다. Transcript Unit과 목적이 다르며 반드시 일대일로 대응하지 않는다. 하나의 Transcript 부분이 여러 Subtitle Unit으로 나뉘거나 여러 부분이 하나의 표시 단위에 기여할 수 있다.

`Cue`는 외부 자막 형식의 표현과 혼동될 수 있으므로 이 개념 모델의 대표 용어로 사용하지 않는다.

### 7.3 Final Subtitle

Final Subtitle은 Review와 사용자 결정을 반영해 외부 전달용 Artifact를 만들 수 있는 승인 상태의 Subtitle 표현이다. 이는 SRT 파일과 동일하지 않다.

Final Subtitle의 승인 단위와 승인 상태를 표현하는 구체적인 방법은 후속 문서에서 정한다. SRT가 다시 들어와 Final Subtitle을 덮어쓰는 모델은 사용하지 않는다.

### 7.4 SRT Artifact

SRT Artifact는 Final Subtitle에서 생성되는 외부 전달용 파생 산출물이다. 중심 데이터 모델이나 최상위 근거가 아니며, 보존된 Final Subtitle과 관련 결정에서 재생성할 수 있어야 한다. SRT 문법과 생성 규칙은 이 문서에서 정의하지 않는다.

## 8. Lecture Structure Model

### 8.1 Lecture Segment

Lecture Segment는 Source Timeline의 Time Range와 연결된 강의의 의미적 또는 기능적 구간이다. 강의 구조를 설명하고 컷편집용 라벨 후보와 Edit Candidate, Review의 근거를 연결하는 데 사용한다.

이 문서에서는 `Lecture Segment`를 대표 용어로 선택한다. `Section`, `Semantic Region`, `Timeline Label`을 같은 개념의 대체 이름으로 혼용하지 않는다.

Lecture Segment는 다음 원칙을 따른다.

- Source Timeline과 추적 가능해야 한다.
- AI 또는 규칙 기반 분류의 출처와 불확실성을 표현할 수 있어야 한다.
- 특정 provider의 분류 체계에 종속되지 않아야 한다.
- 분류 자체가 삭제 결정이나 교육적 가치의 확정이 되어서는 안 된다.

구간 label taxonomy와 Lecture Segment의 중첩 가능성은 이 문서에서 확정하지 않는다.

Lecture Segment의 canonical 기록 계약은 `042_LECTURE_INTELLIGENCE_PIPELINE.md §7.1`(`patches/PATCH-0011`)에서 확정되었다: durable·immutable·identity-owning·insert-only·provenance-bearing 기록으로, eligibility가 ELIGIBLE인 하나의 Eligible Analysis Input에 anchor되고 정확히 하나의 필수 Source Timeline Time Range를 가진다. Segment Label과 taxonomy, 중첩·계층·multi-range, revision·supersession은 여전히 deferred다.

## 9. Edit Candidate Model

Edit Candidate는 AI 또는 규칙 기반 강의 분석이 생성한 편집 제안이다. Text Pipeline의 교정 후보와 마찬가지로 검증 전 후보이며 실제 편집 결정이나 적용된 컷이 아니다.

Edit Candidate는 개념적으로 다음과 연결될 수 있어야 한다.

- 하나 이상의 Source Timeline Time Range 또는 Lecture Segment
- 컷편집용 구간 label 또는 분류
- 유지, 삭제, 검토와 같은 추천 의도
- 사람이 이해할 수 있는 추천 이유와 근거
- confidence 또는 불확실성
- 관련 Review Item과 이후 Review Decision

교육적 가치가 불명확한 Edit Candidate는 자동 삭제 명령이 아니다. Edit Candidate를 NLE operation, FCPXML command 또는 실제 컷이 적용된 미디어로 모델링하지 않는다. 여러 Time Range를 참조할 수 있는지는 Requires Validation이다.

Edit Candidate의 canonical 기록 계약은 `042_LECTURE_INTELLIGENCE_PIPELINE.md §9.1`(`patches/PATCH-0012`)에서 확정되었다: durable·immutable·identity-owning·insert-only·provenance-bearing·provider-independent 기록으로, 정확히 하나의 Analysis Finding에 anchor되고(Lecture Segment 비참조) 정확히 하나의 필수 Source Timeline Time Range와 필수 open Candidate Type·rationale을 가진다. Segment Label linkage, 다중 Time Range/Segment, confidence·예상 절감 시간, revision·supersession, Review 상태와 Accept/Reject/Modify는 여전히 deferred이며 Review 통합은 `043`이 소유한다.

## 10. Review Model

Review는 Text Pipeline과 Edit Pipeline의 후보, 오류, 실패와 불확실성을 사람이 확인하고 결정하는 공통 활동이다. 읽기 전용 Report가 아니다.

### 10.1 Review Item

Review Item은 사람의 확인이 필요한 단위다. 다음 대상을 가리킬 수 있다.

- Transcript 교정 또는 자막 변경 후보
- Subtitle의 시간, 분할, 줄바꿈 또는 구조 문제
- Edit Candidate와 편집 구간 label
- Failure, 누락, 낮은 confidence 또는 Uncertainty
- Validation Result가 발견한 구조 문제

Review Item은 원래 대상과 Source Media 또는 관련 Time Range로 돌아갈 수 있어야 한다. Review Interface에서 해당 원본 오디오 또는 영상 구간을 확인할 수 있다는 제품 계약을 보존한다.

모든 후보가 반드시 독립된 Review Item을 가져야 하는지, 하나의 Review Item이 여러 대상을 묶을 수 있는지는 확정하지 않는다.

### 10.2 Review Decision

Review Decision은 Review Item 또는 그 대상에 대해 사용자가 내린 판단이다. 다음 의미를 지원해야 한다.

- **Accept:** 제안 또는 현재 결과를 사용자의 판단으로 받아들인다.
- **Reject:** 제안 또는 변경을 받아들이지 않는다.
- **Modify:** 제안을 그대로 채택하지 않고 사용자가 변경한 결과를 만든다.

이는 지원해야 할 제품 의미이며 구체적인 상태 enum이나 전이 규칙이 아니다. Review Decision은 AI 후보보다 높은 작업 권위를 가지지만 Source Media의 물리적 사실을 변경하지 않는다.

### 10.3 Modification

Modification은 단순히 `Modify` 상태만 남기는 것이 아니다. 원래 후보, 사용자 변경, 변경된 결과, 이를 확정한 Review Decision 사이의 계보를 보존해야 한다. 가능한 경우 변경 근거와 이전 revision도 추적할 수 있어야 한다.

사용자가 만든 변경 결과를 새 Candidate, 승인 결과 또는 별도 revision 중 무엇으로 표현할지는 Requires Validation이다.

### 10.4 Review Iteration

같은 대상에 여러 번의 Review와 Modification이 발생할 수 있다. 최신 결정만 남기고 이전 판단을 잃는 모델을 사용하지 않는다. 이전 결정이 후속 결정으로 대체되었는지, 현재 어떤 결정이 유효한지, 재처리로 생긴 새 후보와 기존 결정이 어떤 관계인지 설명할 수 있어야 한다.

구체적인 iteration 구조, supersession 표현과 충돌 해결 방식은 정의하지 않는다. 다만 후속 Architecture와 Pipeline은 결정 이력을 보존해야 한다.

## 11. Approved Results

Approved Result는 AI 후보와 Review Decision을 거쳐 외부 작업과 Artifact 생성에 사용할 수 있는 사용자 승인 결과다. Subtitle의 승인 결과는 `7.3 Final Subtitle`로 표현한다. Approved Result는 최신 파생 파일과 같은 개념이 아니다.

### 11.1 Approved Edit Decision

Approved Edit Decision은 사용자가 확정한 편집 판단이다. 다음 의미를 잃지 않아야 한다.

- Source Timeline의 Time Range
- 관련 Lecture Segment 또는 구간 label
- 결정 상태와 최종 편집 의도
- 사용자 Modification이 있다면 그 결과
- 원래 Edit Candidate와 Review Decision까지의 계보

Approved Edit Decision은 외부 편집 과정에서 사용할 수 있지만 실제 컷이 적용된 미디어나 NLE operation이 아니다. 승인된 결정은 재처리로 암묵적으로 사라지거나 새로운 AI 후보에 의해 덮어써지면 안 된다.

## 12. Artifacts and Exports

Artifact는 LectureOS의 내부 개념과 승인 결정에서 만들어지는 전달 가능한 파생 결과다. 중심 도메인 사실이나 사용자 결정 자체가 아니다.

V1의 Artifact 또는 외부 표현은 다음을 포함할 수 있다.

- Final Subtitle에서 생성한 SRT
- Approved Edit Decision을 원본 시간 범위, label, 결정 상태와 함께 제공하는 export
- 사람이 읽을 수 있는 Review 결과
- 기계가 읽을 수 있는 외부 전달 결과
- Processing Status와 Diagnostic의 외부 표현

Artifact는 가능한 경우 다시 생성할 수 있어야 하며, 그 손실이 Source Media, 사용자 결정 또는 승인 결과의 손실을 의미해서는 안 된다. 사람이 읽을 수 있는 형식과 기계가 읽을 수 있는 형식의 구체적인 schema는 정의하지 않는다.

FCPXML은 V1 Artifact가 아니다. 외부 편집 완료본과 그 round trip도 V1에서 LectureOS Artifact로 확정하지 않는다.

## 13. Processing State and Diagnostics

Processing State와 Diagnostic은 제품 결과의 정확성과 처리 가능성을 설명하는 운영 정보다. Source Media, Transcript, Subtitle, 사용자 결정 또는 Approved Result를 대체하지 않는다.

### Processing Run

Processing Run은 생성 결과와 provenance를 연결하되 지속되는 도메인 개념의 identity를 소유하지 않는다.

### Stage Status and Failure

Stage Status는 처리 진행과 완료 여부를 나타내는 개념이며, Failure는 정상 결과를 만들지 못했거나 일부 결과의 신뢰성이 훼손된 상황이다. 부분 성공의 허용 범위와 상태 전이는 후속 Architecture가 정한다.

### Diagnostic, Validation Result, and Uncertainty

- **Diagnostic:** 실패, 누락 또는 이상을 사람이 이해하고 조사할 수 있도록 설명하는 운영 정보다.
- **Validation Result:** 시간, 순서, 누락 같은 구조적 조건을 확인한 결과다.
- **Uncertainty:** AI 결과나 분석을 확정하기 어려운 정도 또는 상태이며 근거를 대신하지 않는다.

실패, 검증 불가와 Uncertainty를 정상 완료 결과처럼 숨기지 않는다. 필요한 항목은 Review Item으로 연결할 수 있어야 한다. 구체적인 상태 머신, error taxonomy, confidence 계산은 정의하지 않는다.

## 14. Concept Relationships

| Source Concept | Relationship | Related Concept |
| --- | --- | --- |
| Project Context | Source Media 처리와 선택적 맥락을 하나의 작업 목적으로 연결한다. | Source Media, Processing Run, 사용자 결정 |
| Source Media | 원본 시간 기준을 제공한다. | Source Timeline |
| Source Timeline | 시간 기반 개념의 공통 추적 기준이다. | Time Range, Transcript, Subtitle, Lecture Segment, Edit Candidate |
| Raw Transcript | Source Media와 외부 ASR 결과에서 파생되고 그 출처를 보존한다. | Source Media, External AI Provider, Processing Run |
| Corrected Transcript | Raw Transcript의 계보를 유지하며 교정과 사용자 판단을 반영할 수 있다. | Raw Transcript, Review Decision |
| Subtitle | Transcript에서 파생되지만 Transcript Unit과 일대일 대응하지 않는다. | Corrected Transcript, Subtitle Unit |
| Lecture Segment | Source Timeline의 의미적 또는 기능적 구간을 나타낸다. | Time Range, Edit Candidate |
| Edit Candidate | 하나 이상의 시간 범위 또는 Lecture Segment를 근거로 편집 제안을 표현할 수 있다. | Time Range, Lecture Segment, Review Item |
| Review Item | Transcript, Subtitle, Edit Candidate, Failure 또는 Uncertainty를 Review 대상으로 연결한다. | Review Decision, Source Media |
| Review Decision | Review Item 또는 그 대상에 대한 사용자 판단을 기록한다. | Candidate, Modification, Approved Result |
| Modification | 원래 후보와 사용자가 변경한 결과의 계보를 연결한다. | Review Decision, revision |
| Approved Edit Decision | Edit Candidate와 사용자 결정의 계보를 보존한다. | Time Range, label, Review Decision |
| Artifact | 승인된 현재 상태와 보존된 결정에서 파생된다. | Final Subtitle, Approved Edit Decision |
| Processing Run | 결과의 생성 문맥을 연결하지만 중심 개념의 identity를 독점하지 않는다. | 파생 결과, Processing State, Diagnostic |

이 표는 관계의 제품 의미를 설명한다. 데이터베이스 cardinality, foreign key 또는 ownership 구현을 정하지 않는다.

## 15. Invariants

- Source Media는 파생 처리로 변경되거나 덮어써지지 않는다.
- Source Timeline과의 추적성을 잃은 시간 기반 결과는 승인된 결과로 취급하지 않는다.
- Raw Transcript와 다른 AI 결과는 사용자 승인 결과를 덮어쓸 수 없다.
- Reject된 후보는 새 사용자 판단 없이 자동으로 승인 상태가 되어서는 안 된다.
- Modification은 원래 후보 또는 이전 상태와의 계보를 잃어서는 안 된다.
- SRT Artifact는 Final Subtitle보다 권위 있는 원본이 될 수 없다.
- 외부 provider ID는 LectureOS 개념의 유일한 identity가 될 수 없다.
- 재처리는 승인된 사용자 결정을 무조건 삭제하거나 덮어써서는 안 된다.
- Edit Candidate는 Approved Edit Decision과 동일하지 않다.
- Approved Edit Decision은 실제 컷 적용 결과와 동일하지 않다.
- 파생 Artifact의 손실이 Source Media, 사용자 결정 또는 Approved Result의 손실을 의미해서는 안 된다.
- Corrected Transcript와 Subtitle은 서로의 책임을 대신하지 않는다.
- Processing State는 도메인 결과나 사용자 결정을 대신할 수 없다.

## 16. Assumptions and Open Questions

### Confirmed

- Source Media와 Source Timeline은 변경하지 않고 보존한다.
- Raw Transcript, Corrected Transcript, Subtitle은 서로 다른 책임을 가진다.
- Text Pipeline과 Edit Pipeline은 동등한 핵심 범위다.
- AI 결과와 Edit Candidate는 검증 전 후보이며 사용자 결정이 아니다.
- Review는 자막과 Edit Candidate를 함께 다루고 Accept, Reject, Modify를 지원한다.
- Review 대상은 관련 Source Media의 오디오 또는 영상 구간으로 추적 가능해야 한다.
- 사용자 결정과 Approved Edit Decision은 재처리 후에도 보존되어야 한다.
- Approved Edit Decision은 원본 Time Range, label, 결정 상태와 연결된다.
- SRT와 approved edit decisions export는 재생성 가능한 Artifact다.
- 자동 컷 적용, FCPXML, 외부 편집 round trip은 V1 Deferred다.
- 특정 AI provider, NLE, 저장 기술 또는 UI framework를 중심 모델로 고정하지 않는다.

### Working Assumption

- Project Context를 Source Media, 처리 맥락과 사용자 결정을 묶는 최소 상위 개념으로 사용한다.
- Processing Run을 결과의 provenance와 생성 문맥을 설명하는 개념으로 사용한다.
- Lecture Segment를 강의의 의미적 또는 기능적 구간을 나타내는 대표 용어로 사용한다.
- local-first는 실행 위치가 아닌 전략적 기본값이며 Conceptual Data Model을 local-only로 제한하지 않는다.

### Requires Validation

- Project와 Lecture는 별도 개념이어야 하는가?
- 하나의 Source Media를 여러 Project Context에서 재사용할 수 있는가?
- 여러 Source Media를 하나의 강의 작업으로 묶을 수 있는가?
- 원본 시간축 기반 발화·단어 데이터의 정식 명칭과 Transcript의 최소 안정 단위는 무엇인가?
- Speaker Information은 V1 중심 모델에 필요한가?
- Lecture Segment는 중첩될 수 있는가?
- Edit Candidate는 여러 Time Range를 참조할 수 있는가?
- 하나의 Review Item은 여러 후보나 문제를 묶을 수 있는가?
- 여러 Review iteration과 superseded decision을 어떻게 표현할 것인가?
- 재처리 후 기존 Review Decision을 새 후보에 어떻게 연결할 것인가?
- 사용자 Modification 결과는 새 Candidate, Approved Result 또는 별도 revision 중 무엇인가?
- Processing Run과 지속되는 도메인 개념의 수명 경계를 어떻게 나눌 것인가?
- 외부 파일 시스템과 LectureOS 사이에서 Source Media의 수명주기 책임을 어떻게 나눌 것인가?

### Deferred

- approved edit decisions export의 구체적인 교환 모델과 schema
- 외부 편집 결과를 다시 가져올 때의 lineage
- FCPXML 구조와 NLE별 operation 모델
- 데이터베이스, 파일 포맷, ID 형식, API payload
- label taxonomy와 상태 enum의 전체 목록
- confidence threshold와 Subtitle 표시 임계값

## 17. Downstream Constraints

### Constraints for `031_ARCHITECTURE.md`

- 이 문서의 개념 책임을 컴포넌트 책임과 동일시하지 않아야 한다.
- 특정 컴포넌트가 중심 개념의 유일한 소유자가 되어 복구 불가능한 결합을 만들지 않아야 한다.
- Source Media, AI 결과, 사용자 결정, 승인 결과, Artifact의 provenance와 lineage를 유지할 수 있어야 한다.
- 단계 재실행이 승인된 사용자 결정과 Review 이력을 손상시키지 않아야 한다.
- External AI Provider를 교체해도 내부 conceptual identity가 유지되어야 한다.
- 부분 실패, Validation Result와 Uncertainty를 숨기지 않고 표현할 수 있어야 한다.
- Artifact를 중심 데이터의 유일한 저장 형태로 사용하지 않아야 한다.
- Review에서 관련 Source Media 구간에 접근할 수 있어야 한다.
- 외부 provider ID와 LectureOS conceptual identity를 분리해야 한다.
- `021_SYSTEM_CONTEXT.md`의 시스템 경계와 내부 구현 경계를 혼동하지 않아야 한다.

### Constraints for `040~044` Pipeline Documents

- 이 문서의 대표 개념명과 책임을 재정의하지 않고 사용해야 한다.
- raw, corrected, candidate, reviewed, approved 상태의 의미를 혼합하지 않아야 한다.
- Raw Transcript, Corrected Transcript, Subtitle을 동일한 객체처럼 취급하지 않아야 한다.
- Edit Candidate, Approved Edit Decision, 실제 편집 적용을 구분해야 한다.
- Review Decision 이력과 Modification 결과를 보존해야 한다.
- 각 시간 기반 결과가 어떤 Source Media와 Source Timeline을 참조하는지 설명해야 한다.
- 각 파생 결과가 어떤 입력, AI 결과와 사용자 결정에서 생성되었는지 설명할 수 있어야 한다.
- LLM이 최종 timestamp를 직접 통제하는 흐름을 도입하지 않아야 한다.

## Related Documents

- `000_MANIFESTO.md`
- `001_PRODUCT.md`
- `002_FAQ.md`
- `003_VISION.md`
- `004_PRINCIPLES.md`
- `020_PRODUCT_REQUIREMENTS.md`
- `021_SYSTEM_CONTEXT.md`
- `../patches/PATCH-0001-l0-and-prd-stabilization.md`

## Change Log

### Blueprint 0.1 — 2026-07-14

- Source Media와 Source Timeline에서 Transcript, Subtitle, Edit Candidate, Review, 승인 결과, Artifact로 이어지는 Conceptual Data Model을 정의했다.
- AI 후보와 사용자 결정, Approved Result와 파생 Artifact의 책임을 분리했다.
- identity, provenance, revision, 재처리와 Review iteration에 필요한 개념적 제약을 기록했다.
- 미확정 단위, 관계, export schema와 외부 편집 round trip을 Open Questions와 Deferred로 남겼다.
