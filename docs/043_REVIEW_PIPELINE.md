# 043_REVIEW_PIPELINE

- Status: Draft
- Version: Blueprint 0.2
- Last Updated: 2026-07-23
- Amended By: `patches/PATCH-0014-edit-pipeline-review-application-foundation.md`
- Depends On: `000_MANIFESTO.md`, `001_PRODUCT.md`, `002_FAQ.md`, `003_VISION.md`, `004_PRINCIPLES.md`, `020_PRODUCT_REQUIREMENTS.md`, `021_SYSTEM_CONTEXT.md`, `030_DATA_MODEL.md`, `031_ARCHITECTURE.md`, `040_TRANSCRIPT_PIPELINE.md`, `041_SUBTITLE_PIPELINE.md`, `042_LECTURE_INTELLIGENCE_PIPELINE.md`
- Referenced By: `044_EXPORT_PIPELINE.md`

## Purpose

이 문서는 LectureOS의 Review Pipeline을 정의한다.

Review Pipeline은 Transcript, Subtitle, Lecture Intelligence Pipeline이 필요에 따라 생성한 Review Item을 Human Review 대상으로 연결하고, 그 판단의 계보와 이력을 보존한다. 특히 Analysis Finding과 Edit Candidate에 관한 Human Decision과 Approved Edit Decision의 관계를 정의한다.

Review Pipeline은 LectureOS에서 Human Authority가 실제로 행사되는 유일한 Pipeline이다. 이 문서는 Review 활동의 개념, 책임, 경계와 보장 사항을 정의하며 UI, 상태 머신, 저장 구조 또는 실행 방식을 정의하지 않는다.

## 1. Pipeline Scope

### 1.1 포함 범위

- Review Item
- Review Context
- Review Session
- Review Decision
- Decision Status
- Decision Modification
- Decision Provenance
- Approved Edit Decision
- Review History
- Review Explainability
- Decision Traceability
- Review Conflict
- Stale Candidate
- Candidate Reconciliation
- Accept, Reject, Modify를 통한 Human Authority 행사

### 1.2 제외 범위

- Source Media 수용 또는 변경
- Transcript 생성 또는 수정 적용
- Subtitle 생성 또는 수정 적용
- Lecture Analysis 또는 Edit Candidate 생성
- 실제 미디어 편집
- Artifact 생성과 export packaging
- Rendering과 외부 NLE 제어

Review Pipeline은 여러 Pipeline이 생성한 Review Item을 연결하는 공통 Review Concept과 Human Decision을 정의한다. upstream 결과를 다시 만들거나 해당 Pipeline의 책임을 흡수하지 않으며, downstream Artifact를 생성하지 않는다. 사람의 판단을 기록하고 그 결과를 책임 있는 Pipeline으로 전달한다.

## 2. Pipeline Principles

### 2.1 Review Is Not Analysis

Review는 Analysis Finding이나 Edit Candidate를 생성하거나 다시 분석하지 않는다. Review는 제공된 근거를 사람이 평가하고 판단하는 활동이다.

### 2.2 Candidate Is Not Decision

Edit Candidate는 검토 가능한 제안이다. Review Decision만이 사용자의 판단을 나타내며, 후보 자체는 승인된 편집 의도가 아니다.

### 2.3 Decision Is Not Artifact

Review Decision과 Approved Edit Decision은 외부 전달용 Artifact가 아니다. Artifact 생성은 Export Pipeline의 책임이다.

### 2.4 Approval Is Not Rendering

승인은 사용자의 편집 의도를 확정하지만 미디어에 컷을 적용하거나 결과물을 렌더링하지 않는다.

### 2.5 Validation Is Not Approval

구조적으로 유효하고 추적 가능한 Review 기록이라도 사용자의 승인으로 간주할 수 없다. Validation은 Human Authority를 대신하지 않는다.

### 2.6 Human Authority

Review Decision은 AI 또는 외부 provider의 추천보다 높은 작업 권위를 가진다. confidence가 높더라도 후보를 자동 승인할 수 없다.

### 2.7 Provider Independence

Review Decision은 LectureOS의 개념이다. 특정 provider의 분류, 식별자 또는 상태 표현이 Review의 중심 개념이 되어서는 안 된다.

### 2.8 Decision Persistence

재처리나 재분석은 기존 Human Decision을 자동으로 삭제하거나 변경하지 않는다. 현재 적용 가능성이 달라져도 그 결정이 존재했던 사실과 근거는 보존된다.

### 2.9 Source Timeline Traceability

시간 기반 Review Item, Edit Candidate와 Approved Edit Decision은 Source Timeline으로 추적 가능해야 한다.

## 3. Core Concepts

### 3.1 Review Item

Review Item은 사람의 판단이 필요한 대상을 Review Pipeline에 제시하는 개념이다.

대상은 다음을 포함할 수 있다.

- Transcript 교정 후보 또는 구조적 문제
- Subtitle 변경 후보 또는 구조적 문제
- Analysis Finding
- Edit Candidate
- Failure, Uncertainty 또는 Validation 문제

Review Item은 대상 자체를 복제하거나 대체하지 않는다. 어떤 대상을 왜 확인해야 하는지 연결하며, 대상의 원래 계보를 유지한다. 모든 분석 결과가 반드시 Review Item이 되는 것은 아니다.

### 3.2 Review Context

Review Context는 사용자가 판단하는 데 필요한 관련 근거와 주변 맥락이다. 적용 가능한 경우 다음을 연결한다.

- 원본 미디어의 관련 구간 또는 source scope
- 관련 Transcript 또는 Subtitle 표현
- Analysis Finding과 Lecture Segment
- Edit Candidate의 추천, 이유와 불확실성
- 관련 Validation 결과와 이전 Review History

Review Context는 새로운 분석 결과가 아니며, 원본 또는 upstream 기록을 변경하지 않는다.

### 3.3 Review Session

Review Session은 서로 관련된 Review 활동을 이해하기 위한 개념적 문맥이다. 하나 이상의 Review Item과 그에 대한 사용자 활동을 연결할 수 있다.

Review Session은 UI 화면, 로그인 세션 또는 실행 단위가 아니다. 하나의 Review Item이 반드시 한 번의 Review Session에서만 다뤄져야 한다는 뜻도 아니다.

### 3.4 Review Decision

Review Decision은 Review 대상에 대한 사용자의 판단이다. 최소한 다음 의미를 지원한다.

- Accept: 제안된 내용 또는 의도를 수용한다.
- Reject: 제안을 수용하지 않는다.
- Modify: 제안을 그대로 수용하지 않고 사용자가 변경한 결과 또는 의도를 선택한다.

Review Decision은 Analysis Finding을 다시 쓰지 않으며, Candidate의 역사적 내용을 변경하지 않는다.

### 3.5 Decision Status

Decision Status는 Review Decision의 현재 작업상 의미와 적용 가능성을 설명한다. 결정이 현재 유효한지, 이후 판단으로 대체되었는지, 재처리로 인해 재확인이 필요한지를 구분할 수 있어야 한다.

이 문서는 고정된 상태 목록이나 상태 전이 방식을 정의하지 않는다. 어떤 상태 표현도 결정 이력이나 과거 근거를 삭제하는 수단이 되어서는 안 된다.

### 3.6 Decision Modification

Decision Modification은 Modify 판단이 원래 제안과 어떻게 다른 결과 또는 의도를 만들었는지 연결한다.

최소한 다음 관계가 설명 가능해야 한다.

- 원래 Review 대상과 Candidate
- 사용자가 변경한 내용 또는 최종 의도
- 변경을 반영한 결과와 담당 Pipeline
- 해당 변경을 선택한 Review Decision

Review Pipeline은 Transcript나 Subtitle 내용을 직접 수정하지 않는다. 해당 대상에 대한 Modify 결정과 변경 의도를 기록하고, 실제 도메인 결과 반영은 그 결과를 책임지는 Pipeline에 맡긴다.

### 3.7 Decision Provenance

Decision Provenance는 결정이 어떤 Review Item, Candidate, Finding, 원본 근거와 Review Context를 바탕으로 내려졌는지 설명한다. 재처리 전후에도 결정 당시의 분석 문맥을 식별할 수 있어야 한다.

### 3.8 Approved Edit Decision

Approved Edit Decision은 Accept 또는 Modify를 통해 사용자가 확정한 편집 판단이다.

다음 의미를 보존한다.

- Source Timeline의 관련 Time Range 또는 source reference
- 관련 구간 라벨
- 결정 상태와 최종 편집 의도
- 사용자 Modification이 있는 경우 그 내용
- 원래 Edit Candidate와 Review Decision의 계보

Approved Edit Decision은 실제 컷, 편집된 미디어, NLE 명령 또는 export Artifact가 아니다.

### 3.9 Review History

Review History는 동일하거나 관련된 대상에 대해 발생한 Review 활동과 판단의 연속성을 보존한다. 최신 결정만 남기고 이전 Accept, Reject 또는 Modify의 존재와 근거를 지워서는 안 된다.

### 3.10 Review Explainability

Review Explainability는 사용자가 판단에 필요한 근거를 확인할 수 있고, 이후에도 그 판단의 배경을 이해할 수 있음을 뜻한다. 이는 숨겨진 provider 내부 추론의 공개를 의미하지 않는다.

### 3.11 Decision Traceability

Decision Traceability는 Review Decision과 Approved Edit Decision을 Source Media, Source Timeline, upstream 대상, Review Item과 Review History로 역추적할 수 있는 성질이다.

### 3.12 Review Conflict

Review Conflict는 기존 결정과 새 Candidate, 여러 사용자 판단 또는 변경된 upstream 문맥 사이의 관계를 안전하게 확정할 수 없는 상태다.

Conflict는 자동으로 해소되거나 기존 결정을 폐기하지 않는다. 사용자가 차이를 이해하고 다시 판단할 수 있도록 표시되어야 한다.

### 3.13 Stale Candidate

Stale Candidate는 upstream 변경이나 재분석으로 인해 현재 문맥에 그대로 적용할 수 있다고 보장할 수 없는 Candidate다.

Stale 상태는 Candidate가 과거에 존재하지 않았다는 뜻이 아니며, 그 Candidate를 근거로 한 Review History를 삭제하지 않는다.

### 3.14 Candidate Reconciliation

Candidate Reconciliation은 재분석으로 생성된 Candidate와 기존 Candidate 및 Human Decision의 관계를 설명 가능하게 연결하는 활동이다.

Reconciliation은 기존 결정을 새 Candidate에 자동 적용하거나, Candidate를 자동 승인하거나, 이전 기록을 병합해 없애는 활동이 아니다.

## 4. Conceptual Relationships

```text
Analysis Finding
        |
        v
Edit Candidate
        |
        v
Review Item + Review Context
        |
        v
Human Review
        |
        v
Review Decision
        |
        v
Approved Edit Decision
        |
        v
Export Pipeline
```

이 흐름은 Edit Candidate에 대한 주요 Review 관계를 보여주는 개념도다. 모든 Analysis Finding이 Edit Candidate나 Review Item을 만드는 것은 아니다.

Transcript와 Subtitle Pipeline은 필요한 Review Item을 생성해 Review Pipeline으로 전달할 수 있다. Review Pipeline은 이를 Human Review 대상으로 연결하지만 해당 결과를 직접 수정하지 않고, Review Decision을 결과 반영을 책임지는 Pipeline으로 전달한다.

## 5. Review Inputs and Context

Review Pipeline은 다음 upstream 개념을 필요에 따라 참조할 수 있다.

- Source Media identity와 Source Timeline
- Raw Transcript 또는 Corrected Transcript의 관련 표현
- Subtitle과 Subtitle Unit의 관련 표현
- Lecture Segment와 Analysis Finding
- Edit Candidate
- Failure, Diagnostic, Validation Result와 Uncertainty
- 이전 Review Decision과 Review History

모든 Review Item이 모든 입력을 필요로 하지는 않는다. 사용할 수 없는 맥락은 숨기지 않으며, 그 부재가 판단에 영향을 주는 경우 불확실성으로 드러나야 한다.

## 6. Review Activity

Review Pipeline은 다음 책임을 수행한다.

1. Review Item을 Review Context와 연결한다.
2. 사용자가 관련 원본 구간과 근거를 확인할 수 있게 한다.
3. Accept, Reject 또는 Modify 판단을 기록한다.
4. Review Decision, Decision Provenance와 Review History를 연결한다.
5. Edit Candidate에 대한 승인 판단을 Approved Edit Decision으로 발전시킨다.
6. 재처리 후 Stale Candidate, Review Conflict와 Candidate Reconciliation 필요성을 드러낸다.

이 목록은 구현 단계나 순차 실행을 정의하지 않는다. Review는 반복될 수 있으며 이전 판단을 바탕으로 다시 수행될 수 있다.

## 7. Human Decision Application

### 7.1 Accept

Accept는 사용자가 제안된 내용이나 편집 의도를 수용했음을 기록한다. Edit Candidate의 Accept는 Approved Edit Decision을 만들 수 있지만 실제 편집이나 Artifact를 만들지는 않는다.

### 7.2 Reject

Reject는 사용자가 제안을 수용하지 않았음을 기록한다. Reject된 Candidate는 자동으로 다시 승인 상태가 될 수 없으며, 재분석으로 유사한 Candidate가 생기더라도 기존 Reject 이력과 관계가 설명 가능해야 한다.

### 7.3 Modify

Modify는 사용자가 원래 제안과 다른 결과 또는 의도를 확정했음을 기록한다. Modify는 원래 Candidate를 덮어쓰지 않으며 Decision Modification과 계보를 보존한다.

Transcript 또는 Subtitle에 대한 Modify는 해당 Pipeline이 반영할 변경 의도를 제공한다. Edit Candidate에 대한 Modify는 변경된 최종 편집 의도를 가진 Approved Edit Decision으로 발전할 수 있다.

### 7.4 First Edit-Pipeline Review Milestone — Edit-Pipeline Review Application Foundation (First Slice)

이 소절은 `PATCH-0014`로 승인된 Product Owner 결정을 기록한다. Review Pipeline의 **첫 dependency-ordered milestone**은 **Edit-Pipeline Review Application Foundation**이며, 완성된 Edit Candidate Application Foundation(`042_LECTURE_INTELLIGENCE_PIPELINE.md §9.1`)에서 admit된 durable `EditCandidate`로부터 사람의 `ReviewDecision`과, 해당되는 경우 durable `ApprovedEditDecision`으로 이어지는 canonical 경로를 확정한다. **§9.1/§9.2와 완료된 042 계약은 이 소절에 의해 변경되지 않는다.** 이 소절은 §3.4·§3.8·§7이 정의한 개념 위에서 최소 durable-record 계약만 확정하며, UI, 상태 머신, export format, 저장·실행 구현은 정의하지 않는다.

**ReviewDecision Record (Confirmed):** `ReviewDecision`은 **durable canonical domain record**이며 **immutable**, **insert-only**, **identity-owning**(Application 소유 identity), **provenance-bearing**, **replay-safe**한 독립 식별 기록이다. 모든 `ReviewDecision`은 **정확히 하나의 durable `EditCandidate`**(§9.1)에 anchor되며, 참조된 `EditCandidate`와 모든 upstream 기록은 **immutable·read-only**로 소비된다(변경하지 않는다). 최소 canonical 정보: 자신의 identity, 자신의 Domain Result identity, 정확히 하나의 참조 `EditCandidate` identity, **decision kind**(§7.4 Decision Kind), **human actor reference**(Human Authority; AI Candidate는 참조될 뿐 결정으로 승격되지 않는다), 상속된 Source Media·Source Timeline provenance, execution provenance, 그리고 per-admission `sequence`(결정적 순서). 직접 Domain Result upstream은 anchor한 `EditCandidate`의 Domain Result다. 이 기록은 free-text decision note, modify payload, status 필드, Review Session identity, full Review History identity를 가지지 않는다. 이 milestone은 **별도의 durable Review Item 기록을 요구하지 않는다**; 향후 grouping 개념은 single-Candidate `ReviewDecision` 계약을 바꾸지 않고 별도로 추가될 수 있다.

**Decision Kind (Confirmed):** first-slice decision kind는 **닫힌 집합** `accept`·`reject`·`modify`다. unknown 값은 거부되며 alias·coerce·유효값으로의 lowercasing·provider/interface-native 용어 매핑을 하지 않는다. semantics — **accept:** 사용자가 Candidate 제안을 승인된 편집 의도로 수용한다. **reject:** 사용자가 Candidate 제안을 수용하지 않는다. **modify:** 사용자가 변경된 편집 의도를 확정한다. 세 결정 중 어느 것도 편집을 **자동 실행하지 않는다**. 이 닫힌 human-action vocabulary는 042 §9.1의 **open canonical Candidate Type** 계약을 바꾸지 않는다(Candidate Type은 여전히 open Application-owned key다).

**ApprovedEditDecision Creation (Confirmed):** **accept는 정확히 하나의 `ApprovedEditDecision`을 만들고, modify는 정확히 하나를 만들며, reject는 만들지 않는다.** 하나의 `ReviewDecision`은 이 slice에서 **최대 하나의** `ApprovedEditDecision`을 만든다. Reject는 승인 출력이 없어도 durable하고 감사 가능한 사람의 결정으로 남는다. split·merge·multi-output 승인 동작은 승인하지 않는다.

**ApprovedEditDecision Record (Confirmed):** `ApprovedEditDecision`은 **durable·immutable·insert-only·identity-owning·provenance-bearing·canonical** 기록이며 이후 `044` Export의 입력으로 적합한 **self-contained 승인 스냅샷**이다. 다음을 **소유**한다: 자신의 identity, 자신의 Domain Result identity, 승인 decision kind(`accept` 또는 `modify`), 승인된 Source Timeline Time Range, 승인된 Candidate Type 또는 승인된 편집 label, 사람이 검토 가능한 승인된 rationale, 결정적 per-admission `sequence`, 상속된 Source Media identity, 상속된 Source Timeline identity, execution provenance. 다음을 **참조**한다: 원본 `ReviewDecision`, 원본 `EditCandidate`. 직접 Domain Result upstream은 `ReviewDecision`의 Domain Result이며, Candidate와 그 이전 lineage는 transitively 도달 가능하다. 실행 가능한 편집 semantics를 추가하지 않으며 특히 cut/delete 명령, NLE operation, rendering 동작, export serialization, 자동 편집 실행을 **금지**한다.

**Modify Ownership (Confirmed):** 원본 `EditCandidate`는 결코 변경되지 않는다. Modify는 Candidate의 review-relevant 값(승인된 range, 승인된 Candidate Type 또는 label, 승인된 rationale)의 **완전한 승인 대체**로 표현되며, 그 승인된 값은 **오직 `ApprovedEditDecision`이 소유**한다. `ReviewDecision`은 사람의 판단과 Candidate anchor만 기록한다. Modify는 loose patch, delta, Candidate의 mutation, 또는 두 기록에 중복된 canonical 값으로 표현되지 않는다. `ApprovedEditDecision`이 최종 human-approved 값의 **유일한 canonical authority**다.

**Status Representation (Confirmed):** 이 slice는 별도의 durable status 필드, Review state machine, transition 모델을 도입하지 않는다(Alternative A). first-slice 의미는 **decision kind**와 **`ApprovedEditDecision`의 존재/부재**로 표현된다. revision, supersession, withdrawal, revocation, stale status, current-selection은 deferred다. placeholder status 필드를 추가하지 않는다.

**Admission Boundary (Confirmed):** admission은 **running unit execution**을 요구한다. upstream Candidate와 lineage는 read-only이며, canonical admission은 **Application 계층이 소유**한다(interface/UI/API 계층은 canonical 기록을 직접 persist하지 않는다). accept와 modify는 하나의 `ReviewDecision`과 하나의 `ApprovedEditDecision`을 **atomic**하게 admit하고, reject는 하나의 `ReviewDecision`만 admit한다. atomic admission은 all-or-nothing이며 identity collision은 admission을 거부한다. identity는 caller-owned이고, 정규화된 admission은 deterministic·replay-safe이며, 동일 identity로의 replay는 중복을 만들지 않고, 새로운 사람의 판단은 새 identity를 가진 새 insert-only 처리다. 이 first slice는 provenance로서 **human actor reference만 요구**하며 UI 인증이나 완전한 authority-policy 시스템을 정의하지 않는다.

**Lineage (Confirmed):** provenance chain은 `ApprovedEditDecision → ReviewDecision → EditCandidate → AnalysisFinding → EligibleAnalysisInput → corrected transcript/source lineage → SourceTimeline → SourceMedia`다. 직접 Domain Result chaining: `ReviewDecision` upstream = `EditCandidate`의 Domain Result, `ApprovedEditDecision` upstream = `ReviewDecision`의 Domain Result. ownership split: `ApprovedEditDecision`은 승인된 range·승인된 Candidate Type/label·승인된 rationale을 소유하고, Analysis Finding·Eligible Analysis Input·corrected transcript 기록·source 기록은 복제하지 않고 참조한다. Source Media·Source Timeline identity는 기존 durable-stage 관례에 맞춰 denormalize될 수 있으며 upstream 전체 내용을 복제하지 않는다.

**Deferred (이후 milestone):** Review Session persistence, 별도의 full Review History 모델(이력은 insert-only immutability로 보존됨), 다중 Candidate Review Item, multi-user conflict resolution, 포괄적 human authority policy, Candidate reconciliation, revision·supersession, withdrawal·revocation, stale 탐지, current-selection semantics, sufficient Review Context 품질 기준, Review UI, 외부 Review API, export format, NLE 연동, 자동 편집 적용, edit rendering, provider-assisted Review, confidence·priority·severity·quality score(§15.4). 이들 deferred 개념을 위한 placeholder abstraction·field·table·enum·interface는 도입하지 않는다.

## 8. Review Explainability

Reviewer는 판단에 필요한 다음 근거를 확인할 수 있어야 한다.

- 적용 가능한 원본 구간 또는 source scope
- 관련 Analysis Finding
- 관련 Edit Candidate
- Candidate가 생성된 이유와 지원 근거
- confidence, uncertainty 또는 알려진 한계
- 관련 Transcript, Subtitle 또는 Lecture Segment가 있는 경우 그 표현
- 이전 Review Decision과 Review History

Review Explainability는 사용자가 무엇을 검토하고 있으며 왜 판단이 필요한지를 이해할 수 있을 만큼 충분해야 한다. 특정 provider의 비공개 내부 추론을 요구하지 않는다.

Decision Provenance는 이후에도 무엇을, 왜, 어떤 Candidate와 근거를 바탕으로 Accept, Reject 또는 Modify했는지 설명할 수 있어야 한다.

## 9. Safe Reprocessing and Candidate Reconciliation

재분석은 변경된 provider, 분석 기준, Transcript 또는 timing 문맥으로 새로운 Finding과 Candidate를 만들 수 있다.

Review Pipeline은 다음을 보장해야 한다.

- 기존 Review Decision과 Review History를 자동 삭제하거나 변경하지 않는다.
- 새 Candidate가 기존 Candidate 또는 Decision과 어떤 관계인지 설명할 수 있어야 한다.
- 변경된 source reference나 upstream 문맥으로 더 이상 안전하게 적용할 수 없는 Candidate를 Stale Candidate로 식별할 수 있어야 한다.
- 기존 Decision을 새 Candidate에 자동 적용하지 않는다.
- Candidate Reconciliation이 필요한 경우 Review Conflict 또는 재검토 필요성을 드러낸다.
- 사용자가 어떤 분석 문맥을 근거로 과거 결정을 내렸는지 확인할 수 있어야 한다.

새 결과가 현재 사용을 위해 이전 결과를 대체할 수는 있지만, 과거 분석과 Human Decision의 존재를 소급해 없애서는 안 된다.

## 10. Validation

Review Pipeline의 Validation은 다음 개념적 책임을 가진다.

- Review Item과 대상의 연결이 구조적으로 일관적인지 확인한다.
- 시간 기반 대상과 결정이 Source Timeline으로 추적 가능한지 확인한다.
- Review Decision과 Decision Modification의 계보가 설명 가능한지 확인한다.
- Approved Edit Decision이 필요한 원본 범위, 라벨, 결정 상태와 provenance를 유지하는지 확인한다.
- 재처리 후 Candidate와 Decision 관계가 모호한 경우 정상 승인 결과로 숨기지 않는다.

Validation은 Candidate의 교육적 가치나 편집 적합성을 결정하지 않는다. 구조적으로 유효한 Candidate도 Human Review 없이 승인될 수 없다.

## 11. Failure, Conflict, and Uncertainty Handling

다음 상황은 정상 승인 결과로 숨기지 않는다.

- Review Context가 판단에 충분하지 않은 경우
- Source Timeline 또는 원본 근거로 추적할 수 없는 경우
- Decision Provenance가 불완전한 경우
- upstream 변경으로 Candidate가 stale한 경우
- 기존 Decision과 새 Candidate 사이에 Review Conflict가 있는 경우
- Modify 결과를 책임 있는 downstream 또는 upstream 결과와 연결할 수 없는 경우

해결되지 않은 Failure, Conflict 또는 Uncertainty는 사용자 판단이 필요함을 명확히 드러내야 한다. Review Pipeline은 근거가 부족한 상태를 자동 승인으로 전환하지 않는다.

## 12. Pipeline Boundaries

### 12.1 `040_TRANSCRIPT_PIPELINE.md`와의 경계

Transcript Pipeline은 Raw Transcript와 Corrected Transcript를 생성·관리하고, 필요한 경우 Transcript 관련 Review Item을 Review Pipeline으로 전달한다. Review Pipeline은 Human Decision을 기록하지만 Transcript 내용을 직접 수정하거나 Transcript의 유효 상태를 결정하지 않는다.

### 12.2 `041_SUBTITLE_PIPELINE.md`와의 경계

Subtitle Pipeline은 Subtitle Candidate, Revision과 Final Subtitle을 생성·관리하고, 필요한 경우 Subtitle 관련 Review Item을 Review Pipeline으로 전달한다. Review Pipeline은 Accept, Reject, Modify를 기록하지만 Subtitle을 구성하거나 Artifact-ready 상태로 만들지 않는다.

### 12.3 `042_LECTURE_INTELLIGENCE_PIPELINE.md`와의 경계

Lecture Intelligence Pipeline은 Lecture Segment, Analysis Finding과 Edit Candidate를 생성하고, 필요한 경우 관련 Review Item을 Review Pipeline으로 전달한다. Review Pipeline은 이를 분석하거나 다시 생성하지 않고, Candidate에 대한 Human Decision과 Approved Edit Decision을 책임진다.

### 12.4 `044_EXPORT_PIPELINE.md`와의 경계

Export Pipeline은 Final Subtitle과 Approved Edit Decision 같은 승인 결과에서 Artifact를 생성한다. Review Pipeline은 export packaging, Rendering, 외부 형식 변환 또는 외부 시스템 전달을 수행하지 않는다.

## 13. Invariants

- Review Pipeline만 Human Authority를 행사하는 Review Decision을 기록한다.
- AI 또는 provider 결과는 Human Decision을 자동으로 대체할 수 없다.
- Review Item은 원래 대상이나 그 provenance를 대체하지 않는다.
- Edit Candidate는 Approved Edit Decision이 아니다.
- Reject된 Candidate는 자동으로 승인 상태가 될 수 없다.
- Modify는 원래 Candidate와 변경된 의도의 계보를 잃지 않는다.
- Review Decision은 Analysis Finding의 역사적 내용을 다시 쓰지 않는다.
- Approved Edit Decision은 Artifact나 실제 편집 결과가 아니다.
- 구조적 Validation은 Approval이 아니다.
- 시간 기반 Decision은 Source Timeline 추적성을 잃으면 안 된다.
- 재처리는 기존 Human Decision을 자동 삭제하거나 자동 변경하지 않는다.
- Stale Candidate 식별은 관련 Review History를 삭제하지 않는다.
- Candidate Reconciliation은 기존 결정을 새 Candidate에 자동 적용하지 않는다.
- provider 고유 표현은 Review Decision의 정체성을 독점할 수 없다.

## 14. Acceptance Criteria

- Analysis Finding, Edit Candidate, Review Item, Review Decision, Approved Edit Decision과 Artifact가 구분된다.
- Review Pipeline이 LectureOS의 Human Authority 행사 지점으로 정의된다.
- Accept, Reject, Modify의 의미와 경계가 정의된다.
- Review Context와 Review Explainability가 사람의 판단에 필요한 근거를 제공한다.
- Decision Provenance, Decision Traceability와 Review History가 보존된다.
- 재처리 후 Stale Candidate와 Review Conflict를 식별하고 Candidate Reconciliation을 지원한다.
- 기존 Human Decision은 재분석으로 자동 삭제되거나 변경되지 않는다.
- Approved Edit Decision이 Source Timeline, 라벨, 상태, 최종 의도와 계보를 유지한다.
- Review Pipeline이 Transcript, Subtitle, Analysis, Export 또는 실제 편집 책임을 흡수하지 않는다.
- 특정 provider나 구현 방식에 종속되지 않는다.

## 15. Assumptions and Open Questions

### 15.1 Confirmed

- Review Pipeline은 여러 Pipeline이 생성한 Review Item을 Human Review 대상으로 연결하는 공통 Review Concept과 Human Decision을 정의한다.
- 사용자는 Accept, Reject, Modify할 수 있다.
- 사용자는 판단에 필요한 관련 원본 오디오 또는 영상 구간을 확인할 수 있어야 한다.
- Human Decision은 AI Candidate보다 높은 작업 권위를 가진다.
- Approved Edit Decision은 Source Timeline의 범위, 라벨, 결정 상태와 provenance를 보존한다.
- Approval은 실제 편집, Rendering 또는 Artifact 생성을 의미하지 않는다.
- 첫 Edit-Pipeline Review milestone(Edit-Pipeline Review Application Foundation)의 durable `ReviewDecision`·`ApprovedEditDecision` canonical 기록(durable·immutable·insert-only·identity-owning·provenance-bearing), single-`EditCandidate` anchor, 닫힌 `{accept, reject, modify}` decision kind, accept/modify→하나·reject→0의 Approved 생성 규칙, `ApprovedEditDecision`이 소유하는 승인 스냅샷과 Modify ownership, status 필드 없음(Alternative A), running-execution·Application-owned·atomic·replay-safe admission, 그리고 lineage/ownership split은 `§7.4`(`patches/PATCH-0014`)에서 확정되었다. Review Session/History persistence, 다중 Candidate·multi-user·reconciliation·revision·supersession·status 전이·Review UI/API·export format 등은 여전히 deferred다(§15.4). §9.1/§9.2와 완료된 042 계약은 변경되지 않는다.

### 15.2 Working Assumption

- Review Session은 여러 Review Item과 반복 판단을 연결하는 개념적 문맥으로 유용하다.
- Review Context는 대상 유형에 따라 서로 다른 근거를 포함할 수 있다.

### 15.3 Requires Validation

- 하나의 Review Item이 여러 Candidate 또는 서로 다른 Pipeline의 대상을 묶어야 하는 경우가 있는가?
- 여러 사용자가 같은 Review 대상에 판단할 경우 권위와 Conflict를 어떻게 해석해야 하는가?
- 재처리 후 Candidate Reconciliation에서 자동으로 제시할 수 있는 관계의 범위는 어디까지인가?
- Review Context가 충분하다고 판단하는 제품 수준 기준은 무엇인가?

### 15.4 Deferred

- Review 상태와 전이의 구체적인 표현
- Review Session과 Review History의 저장 및 실행 방식
- Candidate reconciliation의 구현 방법
- Review Interface의 구체적인 상호작용과 화면 구성
- export 형식과 외부 NLE 연동 방식

## 16. Non-Goals

이 문서는 다음을 정의하지 않는다.

- Review Interface 구현
- 상태 머신 또는 저장 구조
- 실행과 배포 방식
- provider 연동 방식
- 자동 승인 또는 자동 편집
- Artifact 형식과 export packaging
- 외부 NLE 제어와 Rendering
- Transcript, Subtitle 또는 Lecture Analysis의 내부 처리

## 17. Downstream Constraints

`044_EXPORT_PIPELINE.md`는 다음을 이어받아야 한다.

- Artifact는 Final Subtitle 또는 Approved Edit Decision 같은 승인된 결과에서 생성되어야 한다.
- Analysis Finding, Edit Candidate 또는 Review Item을 Approved Edit Decision처럼 취급해서는 안 된다.
- export는 Review Decision과 Decision Provenance를 변경하지 않는다.
- Artifact 손실이 Approved Edit Decision이나 Review History의 손실을 의미해서는 안 된다.

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
- `044_EXPORT_PIPELINE.md` (planned)
