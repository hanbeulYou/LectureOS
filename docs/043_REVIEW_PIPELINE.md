# 043_REVIEW_PIPELINE

- Status: Draft
- Version: Blueprint 0.2
- Last Updated: 2026-07-23
- Amended By: `patches/PATCH-0014-edit-pipeline-review-application-foundation.md`, `patches/PATCH-0033-effective-transcript-review-admission-boundary.md`, `patches/PATCH-0034-effective-transcript-review-authority-history-boundary.md`
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

effective-transcript generation에서 이 구분을 어떤 형태로 제공하는지는 `§7.6`(`patches/PATCH-0034`)이 확정한다 — 저장된 status 필드가 아니라 append-only authority history에서 **파생**되는 관측이다. 고정 상태 목록과 상태 전이 모델을 정의하지 않는다는 위 규정은 그대로 유지된다.

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

**Generation Scope of this Milestone's Anchor, Payload, and Admission Boundary (Confirmed, PATCH-0033):** 위 `ReviewDecision` Record·`ApprovedEditDecision` Record·Admission Boundary·Lineage 문단의 **문언은 삭제·재작성되지 않으며 legacy execution-coupled generation의 계약으로 그대로 유효하다.** 다만 이 소절이 원래 가졌던 **보편 한정(모든 Review 기록에 대한 진술)은 그 세대로 범위가 좁혀진다** — `042 §8.1`이 `PATCH-0030`으로, `§7.1`이 `PATCH-0031`으로, `§9.1`이 `PATCH-0032`로 받은 것과 동일한 versioned architecture 관용구이며, 계약의 소급 변경이 아니라 세대 범위의 명시다.

구체적으로 다음 **여덟 요소가 legacy 세대 전용**이다. `042 §9.1`이 네 요소였던 것보다 많다는 점에 유의한다. (1) anchor 대상 `EditCandidate`가 **`042 §9.1` legacy 세대의 Candidate**라는 점, (2) **running unit execution 요구**, (3) 두 기록이 **자신의 Domain Result identity를 소유**한다는 요구, (4) **직접 Domain Result chaining**(`ReviewDecision` upstream = Candidate의 Domain Result, `ApprovedEditDecision` upstream = `ReviewDecision`의 Domain Result), (5) 두 기록이 **execution provenance를 소유**한다는 요구, (6) **caller-owned identity**, (7) 두 기록이 **per-admission `sequence`를 최소 canonical 정보로 요구**한다는 점, 그리고 (8) 상속된 **Source Media·Source Timeline provenance를 기록에 직접 담는 형태**(`ReviewDecision`의 최소 canonical 정보 및 `ApprovedEditDecision`의 소유 값으로 열거된 형태) — `042 §9.1` 블록이 그 요소 (4)로 처리한 것과 같은 경우이며, 현행 세대에서 그 provenance는 `§7.5` R-7이 정하는 대로 anchor 연쇄를 통해 확보된다(provenance 요구 자체는 사라지지 않는다).

항목 (3)·(4)는 `042 §9.1`보다 강하다. `§9.1`은 `DomainResultReference`를 payload 항목으로 열거했을 뿐이지만 이 소절은 두 기록이 **자신의 Domain Result identity를 소유하고 서로를 직접 chaining**하도록 요구한다. effective-transcript generation의 Edit Candidate(`042 §9.3`)는 **Domain Result를 만들지 않으므로** 소유할 것도 참조할 것도 존재하지 않으며, 이 요구는 그 세대에서 **충족 불가능하다**. 항목 (7)의 `sequence` 역시 그 세대에는 결정적·Application 소유의 파생 원천이 없다. 이 요구들을 문자 그대로 적용하면 `040 §18` H-10과 `041 §15` E6이 **금지한** 가짜 실행 기록과 합성 Domain Result를 만들어야 한다. effective-transcript generation의 Review admission 경계는 `§7.5`가 정의한다.

**두 세대에 공통으로 유지되는 것**은 다음이다: 두 기록의 성질(durable·immutable·insert-only·identity-owning·provenance-bearing·replay-safe, 독립 식별), Canonical Anchor의 **cardinality와 방향**(정확히 하나의 durable `EditCandidate`, upstream은 immutable·read-only 소비), **닫힌 decision kind `{accept, reject, modify}`**와 그 semantics 및 alias·coerce·lowercasing 금지, **`ApprovedEditDecision` 생성 규칙**(accept 하나·modify 하나·reject 없음, `ReviewDecision`당 최대 하나, split·merge·multi-output 미승인), `ApprovedEditDecision`이 **소유**하는 승인 스냅샷(승인 kind, 승인된 Time Range, 승인된 Candidate Type 또는 label, 승인된 rationale)과 **참조**하는 대상, **Modify Ownership**(원본 Candidate 불변, 완전 승인 대체, `ApprovedEditDecision`이 유일한 canonical authority, 두 기록에 중복 금지), **Status Representation(Alternative A)**(별도 status 필드·state machine·transition 없음, placeholder 금지), **human actor reference 요구**와 Human Authority(AI Candidate는 참조될 뿐 결정으로 승격되지 않는다), atomic all-or-nothing admission과 Application 계층 소유(interface/UI/API가 canonical 기록을 직접 persist하지 않는다), `ReviewDecision`이 **가지지 않는** 것의 목록(free-text note, modify payload, status, Review Session identity, full Review History identity), 별도 durable Review Item 기록 미요구, 그리고 실행 가능한 편집 semantics 금지(cut/delete 명령, NLE operation, rendering, export serialization, 자동 편집 실행). 공통으로 유지되는 것은 이들 계약의 **의미**이며, 그 안에서 지목된 **세대별 record 이름과 provenance·identity·ordinal 표현 형태**가 아니다.

**Deferred (이후 milestone):** Review Session persistence, 별도의 full Review History 모델(이력은 insert-only immutability로 보존됨), 다중 Candidate Review Item, multi-user conflict resolution, 포괄적 human authority policy, Candidate reconciliation, revision·supersession, withdrawal·revocation, stale 탐지, current-selection semantics, sufficient Review Context 품질 기준, Review UI, 외부 Review API, export format, NLE 연동, 자동 편집 적용, edit rendering, provider-assisted Review, confidence·priority·severity·quality score(§15.4). 이들 deferred 개념을 위한 placeholder abstraction·field·table·enum·interface는 도입하지 않는다.

### 7.5 Effective-Transcript Generation — Review Admission Boundary

이 소절은 `PATCH-0033`으로 승인된 Architect Decision(R-1…R-12)을 기록한다. 이 소절은 **`§3`·`§7`의 Review 개념과 `§7.4`의 canonical 기록 계약을 전혀 변경하지 않는다.** 이 소절이 확정하는 것은 오직 **effective-transcript generation에서 Review 기록이 무엇에 anchor하고 어떤 전제 아래 admit되는가**이며, 그 세대가 사용하는 provenance·identity·ordinal 표현이다. 결정 번호에 `R-` 접두사를 쓰는 것은 이 문서가 Review를 다루기 때문이며 계약상 의미는 없다.

**Contract Generation (Confirmed, R-1):** Review admission 경계는 **두 개의 contract generation**으로 존재한다. `§7.4`의 Record·Admission Boundary·Lineage 문단은 **legacy execution-coupled generation**의 계약이고, 이 소절은 **effective-transcript generation**의 계약이다. legacy 계약과 그 기록은 유효한 역사로 보존되며 삭제·backfill·재해석·소급 변경되지 않는다. 두 세대는 영구히 구분 가능하고, **하나의 contract generation 안에는 정확히 하나의 canonical Review admission 경계가 존재한다.** 한 세대의 anchor를 다른 세대의 admission 근거로 교차 사용하지 않는다.

**Canonical Anchor (Confirmed, R-2):** effective-transcript generation에서 모든 `ReviewDecision`은 **정확히 하나의 canonical Edit Candidate(`042 §9.3`)**에 anchor한다. `§7.4`가 확정한 anchor의 **cardinality와 방향은 그대로다** — Candidate는 필수이고 `ReviewDecision`은 Candidate 없이 존재할 수 없으며, 참조된 Candidate와 모든 upstream 기록은 **immutable·read-only**로 소비된다. 바뀌는 것은 그 Candidate가 **어느 세대의 Candidate인가**뿐이다: legacy `042 §9.1` Candidate가 아니라 `§9.3` Candidate다. `ReviewDecision`은 Analysis Finding·Lecture Analysis Input Admission·Lecture Segment에 **직접 anchor하지 않으며**, 필요한 상류 의미는 anchor한 Candidate를 통해 확보한다.

**Current-Only Admission Standing (Confirmed, R-3):** Review admission은 **저장된 Candidate가 존재한다는 사실만으로 허용되지 않는다.** anchor한 Candidate가 매달린 연쇄의 뿌리 — 그 Candidate의 Analysis Finding이 anchor한 `Lecture Analysis Input Admission` — 의 **현재 authority standing을 prepare 또는 admission 시점에 재평가**해야 하며, 그 파생 standing이 **`current`일 때만** admit된다. `superseded_by_authority_change`와 `current_authority_ineligible`은 명시적 거부 사유다. 이 파생 vocabulary는 released GOAL-023 계약이 정의한 **정확히 세 값**이며 이 소절은 어떤 값도 추가하지 않는다. Candidate identity가 존재하지 않거나 canonical 형식에 맞지 않는 경우는 **네 번째 standing 값이 아니라** 참조 자체의 거부로 다루며, standing 평가 이전에 실패한다. 연쇄는 다음과 같다: `ReviewDecision → Edit Candidate → Analysis Finding → Lecture Analysis Input Admission`.

**No Stored Currentness (Confirmed, R-4):** `§7.4`의 **Status Representation(Alternative A)이 이 세대에서도 그대로 유지된다** — 별도의 durable status 필드, Review state machine, transition 모델을 도입하지 않으며 placeholder status 필드도 추가하지 않는다. 여기에 더해 이 소절은 mutable current flag·stale flag·selection flag·lifecycle state를 **추가하지 않으며, 추가하는 방향을 금지한다.** 연쇄의 현재 standing은 저장되지 않는 파생 관측이며, standing 관측은 어떤 기록도 변경하지 않는다. Review는 anchor한 Candidate에 상태를 쓰지 않는다(`042 §9.3` C-5와 정합).

**`§7.6`과의 관계 (Confirmed, PATCH-0034):** 위 금지는 **두 canonical 기록(`ReviewDecision`·`ApprovedEditDecision`)에 mutable 상태를 얹는 방향**에 대한 것이며 그대로 유효하다. `§7.6`이 도입하는 authority history는 그 두 기록에 어떤 컬럼도 추가하지 않는 **별개의 append-only 기록**이고, 현재 유효한 판단은 여전히 **저장되지 않고 파생**된다(`040 §18` H-6 관용구). mutable current·stale·selection flag와 lifecycle state는 이 세대에서 계속 금지된다.

**Historical Semantics (Confirmed, R-5):** superseded 연쇄의 Admission·Finding·Candidate·`ReviewDecision`·`ApprovedEditDecision`은 모두 **유효한 immutable history**로 남으며 삭제·무효화·재작성되지 않는다. **기존 Review 기록은 upstream authority가 변경되었다는 이유로 수정·삭제·재작성되지 않는다** — 이는 `§7.4`가 "Reject는 승인 출력이 없어도 durable하고 감사 가능한 사람의 결정으로 남는다"와 insert-only immutability로 이력을 보존한다고 확정한 바를 그대로 충족한다. 금지되는 것은 **standing이 `current`가 아닌 연쇄에 대한 새로운 Review admission**뿐이다. authority가 이전에 admit된 revision으로 되돌아오면 동일한 canonical Admission identity가 다시 `current`가 되고 admission 가능성은 파생 규칙에 의해 복원된다(GOAL-023의 returning-authority convergence). 사람의 판단을 되돌리는 revision·withdrawal·revocation은 `§15.4`의 deferred 상태 그대로다.

**Execution-Free Deterministic Provenance (Confirmed, R-6):** effective-transcript generation의 Review Foundation은 `ProcessingRun`, `ProcessingUnit`, `UnitExecution`, RUNNING state, execution lifecycle, **두 기록의 Domain Result identity 소유**, 그리고 **직접 Domain Result chaining**을 **요구하지 않는다.** 마지막 두 항목이 `042 §9.3` C-7보다 한 걸음 더 나아간 지점이다: `§7.4`는 두 기록이 각자 Domain Result identity를 소유하고 서로를 직접 chaining하도록 요구했으나, `§9.3` Edit Candidate는 Domain Result를 만들지 않으므로 이 세대에는 **소유할 것도 참조할 것도 존재하지 않는다.** 가짜 실행 기록·synthetic Processing Run·합성 RUNNING state·**합성 Domain Result**를 provenance로 사용하는 것은 **금지된다**(`040 §18` H-10, `041 §15` E6의 명시적 금지). 대신 Review 기록의 생성 provenance는 다음 성질을 가져야 한다: **deterministic**, **local**, **replay-safe**, **identity-owning**, canonical 기록 경계에서 **provider-independent**, wall-clock 비의존, 무작위 실행 identity 없음. 결정적으로 파생된 실행 마커를 기록할지(`040 §14` A-3 / `040 §17` K-4 관용구) 실행 마커 없는 provenance를 사용할지(`041 §15` E6, `042 §8.2` D-6, `§7.2` S-7, `§9.3` C-7 관용구)는 **구현 선택**이며 이 소절은 어느 한쪽을 강제하지 않는다.

**Upstream Provenance Through the Anchor Chain (Confirmed, R-7):** `§7.4`가 요구한 **상속된 Source Media·Source Timeline provenance는 이 세대에서도 요구된다** — 사라지지 않는다. 달라지는 것은 그것을 **담는 형태**다: 이 세대에서 그 provenance는 anchor 연쇄 `ReviewDecision → Edit Candidate(§9.3) → Analysis Finding(§8.2) → Lecture Analysis Input Admission → current applicable Corrected Revision → parent Raw Transcript → Source Timeline → Source Media`를 통해 확보되며, Review 기록이 그 값을 **직접 컬럼으로 중복 복제해야 한다는 뜻은 아니다**(`§7.4`가 이미 "Source Media·Source Timeline identity는 기존 durable-stage 관례에 맞춰 denormalize**될 수 있으며** upstream 전체 내용을 복제하지 않는다"고 선택으로 둔 바와 정합하고, `042 §8.2` D-2·`§7.2` S-2·`§9.3` C-8이 확립한 "anchor를 통해 상속하고 복제하지 않는다" 선례를 따른다). 구현이 조회 편의를 위해 일부를 denormalize할지는 구현 선택이다. 다만 어떤 형태를 택하든 **Source Timeline traceability(`§2.9`)는 유지되어야 하고**, `§7.4`의 lineage에서 legacy 기록 이름으로 지목된 `EligibleAnalysisInput`의 자리는 이 세대에서 `Lecture Analysis Input Admission`이 차지한다(`042 §5.1.1`의 세대 대응).

**Record Contract Preserved (Confirmed, R-8):** `§7.4`가 확정한 두 canonical 기록의 의미는 이 세대에서도 **그대로 상속된다**: 둘 다 durable canonical domain record이며 **immutable**, **insert-only**, **identity-owning**, **provenance-bearing**, **replay-safe**한 독립 식별 기록이다. **닫힌 decision kind `{accept, reject, modify}`**와 그 semantics, unknown 값 거부와 alias·coerce·lowercasing·interface-native 용어 매핑 금지, 세 결정 모두 편집을 자동 실행하지 않는다는 규정, 그리고 이 닫힌 human-action vocabulary가 `042 §9.1`·`§9.3`의 **open canonical Candidate Type 계약을 바꾸지 않는다**는 규정이 그대로다. **`ApprovedEditDecision` 생성 규칙**(accept 정확히 하나, modify 정확히 하나, reject 없음, 하나의 `ReviewDecision`당 **최대 하나**, split·merge·multi-output 미승인)과 그 기록이 **소유**하는 승인 스냅샷(승인 decision kind, 승인된 Source Timeline Time Range, 승인된 Candidate Type 또는 label, 사람이 검토 가능한 승인된 rationale) 및 **참조**하는 대상(원본 `ReviewDecision`, 원본 `EditCandidate`)도 그대로다. **Modify Ownership**(원본 Candidate 불변, 완전 승인 대체, `ApprovedEditDecision`이 유일한 canonical authority, loose patch·delta·중복 표현 금지), **human actor reference 요구**와 Human Authority, `ReviewDecision`이 가지지 않는 것의 목록, 별도 durable Review Item 기록 미요구, 그리고 실행 가능한 편집 semantics 금지도 유지된다. 이 소절은 승인된 Time Range에 media-duration validation·transcript-boundary 정렬·Candidate range와의 containment 검사·range reconciliation을 **추가하지 않는다**(`042 §9.3` C-9와 정합). 이 소절이 재범위화하는 것은 **anchor의 세대, admission 전제, 그리고 provenance·identity·ordinal 표현 형태뿐**이다.

**No Canonical Ordinal (Confirmed, R-9):** 이 세대의 Review 기록은 **per-admission `sequence`를 저장하지 않는다.** `§7.4`가 이를 최소 canonical 정보로 열거했으나, 하나의 Review admission은 하나의 `ReviewDecision`과 **최대 하나**의 `ApprovedEditDecision`만 만들므로(`§7.4` ApprovedEditDecision Creation) per-admission ordinal은 구조적으로 단일값이며 **제품 의미를 갖지 않는다** — 이는 released legacy 구현이 두 기록 모두에 상수를 부여한다는 사실로 확인된 바이며, 추론이 아니다. 따라서 이 세대는 `042 §9.3`이 Edit Candidate에 적용한 것과 같은 무-ordinal 관용구를 사용한다: ordinal을 persistence에도 identity에도 두지 않는다. **금지:** DB row count로 ordinal 부여, `MAX(sequence) + 1`, wall-clock order, insertion order, race-dependent order. 조회 정렬은 결정적 presentation order일 수 있으나 canonical ordinal로 오인하지 않는다.

**`040 §18`과의 구분 (Confirmed):** `040 §18`(Correction Candidate에 대한 첫 Human Authority Decision)은 human decision에 대해 **반대 방향**을 확정한 released 계약이므로 반드시 구분해야 한다. 거기서는 per-candidate `sequence`가 제품 의미를 갖는다 — H-5는 각 authority 변경이 `previous_decision_id`로 이전 current를 supersede하는 새 immutable record라고 하고, H-6은 **current authority를 최고 `sequence` record로 파생**하며, H-7은 identity를 `(correction_candidate_id, kind, sequence)`에서 파생하고, H-8은 Accept→Reject를 `sequence+1` Append로 규정한다. **두 ordinal은 서로 다른 개념이다:** `040 §18`의 것은 **한 anchor에 대한 authority 이력 위치**이고(그래서 supersession과 current 파생을 지탱한다), `§7.4`의 것은 **한 admission 안의 위치**다(그래서 최대 두 기록만 만드는 admission에서 단일값이다). 이 소절이 저장하지 않는 것은 후자뿐이며, 전자에 해당하는 authority-history ordinal·`previous` link·supersession·current 파생은 이 소절이 **도입하지도 부정하지도 않는다** — 그것들은 `§15.4`의 deferred(revision·supersession·current-selection·reconciliation) 그대로다.

**후속 확정 (Confirmed, PATCH-0034):** 이 문단이 "도입하지도 부정하지도 않는다"고 남겨 둔 **authority-history ordinal·`previous` link·supersession·current 파생**은 `§7.6`이 승인된 PATCH로 도입한다. 이 문단이 요구한 절차가 그것이었다. R-9가 금지한 **per-admission ordinal**은 계속 존재하지 않으며, 두 ordinal이 서로 다른 개념이라는 위 구분도 그대로 유지된다.

**기록된 결과 (Confirmed):** 두 가지를 명시한다. **(1)** 동일한 canonical Review 판단의 재제출은 두 번 보존되지 않고 하나로 수렴한다. 서로 다른 사람의 판단, 다른 decision kind, 다른 승인 값은 여전히 별개 기록이다(R-11). **(2)** 더 강한 결과: 한 Candidate에 대해 사람이 판단을 번복하면(예: `accept` → `reject` → 다시 `accept`) 세 번째 제출은 첫 identity로 수렴하므로 저장소에는 서로 모순되는 두 기록이 **ordinal도 `previous` link도 timestamp도 없이 공존**한다. **이 소절은 그중 무엇이 현재 유효한지 답하지 않으며**, R-4가 그것을 표현할 수 있는 어떤 필드도 금지한다. `§7.4`의 Alternative A는 Candidate당 판단이 하나일 때만 충분하고 R-11은 복수를 허용하므로, 이 공백은 실재한다. 이는 **`§15.4`가 deferred로 둔 current-selection·revision·supersession·reconciliation의 영역이며 이 소절이 새로 만든 결함이 아니다** — released legacy 경로도 `sequence`가 상수여서 동일한 공백을 갖는다. 이 세대에서 그 공백을 닫으려면 `040 §18` H-5·H-6에 해당하는 authority-history 계약을 별도의 승인된 PATCH로 확정해야 하며, 그때까지 구현은 **여러 판단이 이력으로 공존한다는 사실만** 노출하고 어느 것이 현재 유효한지 판정하지 않는다.

**공백의 해소 범위 (Confirmed, PATCH-0034):** 위 (2)가 지목한 공백은 `§7.6`이 **decision kind가 달라지는 번복에 대해** 해소한다: 같은 사람의 `accept` → `reject` → 다시 `accept`는 authority history의 세 위치로 표현되고 현재 유효한 판단이 파생된다(canonical `ReviewDecision` 기록 자체는 여전히 수렴하므로 두 개만 존재한다). **같은 kind에 승인 내용만 다른 재제출**(예: 승인 range가 다른 두 번째 `modify`)은 `§7.6`이 해소하지 않으며 R-11의 명시적 conflict로 남는다 — 그 경우를 이력으로 표현하려면 `§7.4`의 "`ReviewDecision`당 최대 하나의 `ApprovedEditDecision`" 또는 R-10의 released identity 구성을 다시 범위화해야 하고, 둘 다 이 소절과 `§7.6`의 범위 밖이다.

**Identity Direction (Confirmed, R-10):** Review 기록의 identity는 **Application이 소유**한다. provider가 반환한 식별자, execution framework의 식별자, `DomainResult` identity, UUID, timestamp, rowid, 물리 경로, mutable currentness state는 canonical identity에 참여하지 않는다. `§7.4`가 legacy 세대에 대해 확정한 **caller-owned identity는 이 세대에 적용되지 않으며**, identity는 **immutable anchor와 안정적인 Review 의미**에서 결정적으로 파생된다. **`human actor reference`는 identity에 참여해야 한다.** 참여하지 않으면 서로 다른 두 사람의 동일 kind 결정이 하나로 수렴하거나 identity 충돌로 거부되는데, `§7.4`는 `ReviewDecision`의 최소 canonical 정보에 human actor reference를 포함시키고 Human Authority를 그 기록의 의미로 확정하므로, 서로 다른 사람의 판단이 구별되지 않는 것은 그 의미를 잃는 것이다. **`040 §18` H-7과의 구분:** 그 계약은 identity를 `(correction_candidate_id, kind, sequence)`에서 파생하며 actor를 포함하지 않는다. 이는 그 세대가 per-candidate authority 이력을 `sequence`로 표현하고 actor를 provenance로만 기록하기 때문이며, R-9가 그 ordinal을 도입하지 않는 이 세대에서는 actor가 판단을 구별하는 유일한 canonical 축이 된다. 다중 사용자 충돌 처리 자체는 `§15.4`의 deferred 그대로다. **정확한 hash 구성은 이 소절에서 확정하지 않고 구현 milestone에 위임한다**(`041 §15` E7, `042 §8.2` D-8·`§7.2` S-10·`§9.3` C-10의 선례). 다만 구현은 identity에 참여하는 semantic 필드와 참여하지 않는 필드를 명시하고, 그 선택이 R-11의 conflict 분기를 도달 가능하게 하는지를 기록해야 한다. 두 경우는 다음과 같다: **(A)** 저장되는 canonical semantic 필드 중 일부가 identity에 참여하지 않으면 동일 identity에 대한 semantic 불일치가 정상 입력으로 도달 가능하며 그때는 반드시 명시적 conflict여야 한다. **(B)** 저장되는 모든 canonical semantic 필드가 identity에 참여하면 그 불일치는 hash collision을 제외하고 구조적으로 도달 불가능하다. **(B)를 택하더라도 semantic equality 검사를 제거하지 않는다.** `ApprovedEditDecision`은 `ReviewDecision`에서 결정적으로 파생될 수 있으나 그 구성 역시 구현이 명시한다.

**Replay and Conflict (Confirmed, R-11):** **동일 Edit Candidate + 동일 contract version + 동일 human actor + 동일 decision kind + 동일한 승인 내용(해당되는 경우) → 동일한 canonical identity로 수렴**하며 중복 기록을 만들지 않는다. 다음은 별개의 기록이 될 수 있다: 다른 Candidate, 다른 human actor, 다른 decision kind, 다른 승인 range·Candidate Type/label·rationale, 그 밖에 계약상 identity에 포함되는 의미적 내용의 변경. 동일 identity에 대해 **의미가 다른 payload**가 제출되면 덮어쓰지 않고 **명시적 conflict**로 거부한다(released collision-convergence 관용구, `040 §18` H-9). 근접 동시 동일 admission은 중복 canonical 기록 없이 수렴한다. **accept·modify의 두 기록은 원자적으로 함께 admit되고 reject는 하나만 admit한다**는 `§7.4`의 all-or-nothing 요구는 그대로 유지되며, 부분 기록된 Review admission은 유효한 것으로 보일 수 없다.

**Persisted Representation (Confirmed, R-12):** 이 소절은 canonical Review 기록의 **의미**만 확정하며 물리적 저장 형태를 확정하지 않는다. 다만 legacy `edit_review_decisions`·`approved_edit_decisions` 관계는 legacy 세대의 anchor와 실행 provenance(legacy Edit Candidate, `domain_result_id`, `processing_run_id`, `unit_execution_id`, `sequence`)를 **필수 컬럼으로 요구**하므로, effective-transcript generation의 Review 기록을 그 관계에 기록하려면 R-6·R-9가 금지한 값을 날조해야 한다. 따라서 이 세대의 Review 기록은 **legacy 관계를 재사용하지 않으며**, 필요한 저장 형태는 `041 §15` E1, `042 §8.2` D-11·`§7.2` S-12·`§9.3` C-12의 선례를 따라 **strictly additive한 새 versioned representation**으로 도입한다. `ReviewDecision`당 `ApprovedEditDecision`이 최대 하나라는 `§7.4` 규정은 **계약이 뒷받침하는 uniqueness**이므로 이 세대의 저장 형태는 그것을 제약으로 표현할 수 있다 — `042 §7.1`이 **하나의 canonical segmentation을 강제하지 않기 위해** canonical-set/uniqueness 제약을 두지 않는다고 확정해 Lecture Segmentation에서 그런 제약을 추가할 수 없었던 것과 **성질이 반대**다. 두 uniqueness는 종류도 다르다 — 그쪽은 segmentation 집합의 canonical화이고 이쪽은 부모-자식 1:1 cardinality다. 두 상황을 혼동하지 않으며, R-12를 `042` 전반의 일반 금지 근거로 인용하지 않는다. legacy 관계와 그 행은 backfill·dual-write·재해석 없이 자기 세대의 canonical 표현으로 남는다. 정확한 이름과 컬럼 구성은 구현 milestone이 선택하며, R-11의 수렴 키가 요구하는 **contract version을 어떤 persisted 필드로 기록할지도 구현 milestone이 확정한다**(`042 §8.2` D-11·`§7.2` S-12·`§9.3` C-12 구현 선례는 이를 저장 컬럼으로 보유한다).

**Sections Not Re-scoped (Confirmed):** 이 소절은 **`044_EXPORT_PIPELINE.md`의 Export 계약(§19·§20·§21과 그에 의존하는 §22를 포함해 전체)을 재범위화하지 않는다.** Export는 `ApprovedEditDecision`을 입력으로 소비하며 그 released 표현은 legacy 세대의 실행 provenance를 필수로 요구하므로, 이 세대의 승인 기록을 Export에 연결하려면 별도의 generation 범위 결정이 필요하다. Review Session persistence, 별도 Review History 모델, 다중 Candidate Review Item과 grouping, multi-user conflict resolution, 포괄적 human authority policy, Candidate reconciliation, revision·supersession, withdrawal·revocation, stale 탐지, current-selection semantics, Review Context 품질 기준, Review UI와 외부 Review API, provider-assisted Review, confidence·priority·severity·quality score도 마찬가지로 재범위화되지 않는다(`§15.4`). 그 결정들은 이 소절이 아니라 그때의 승인된 PATCH가 내린다.

**`044 §23`과의 관계 (Confirmed, PATCH-0035):** 위 문단이 "별도의 generation 범위 결정이 필요하다"고 남겨 둔 결정 중 **이 세대의 `ApprovedEditDecision`을 `044` Export에 연결하는 계약**은 `044 §23`(EA-1…EA-11)이 승인된 PATCH로 확정한다. 그 절이 확정하는 것은 **Export admission 경계뿐**이다: 이 세대의 Assembly가 `ApprovedEditDecision`을 직접 모으고 `§19` atom 단계를 재현하지 않는다는 것(EA-2), membership이 그 Source Timeline의 모든 export 적격 승인 편집이라는 것(EA-3), 그리고 적격성이 현재 유효한 판단의 승인·단일 actor·standing `current`라는 것(EA-4)이다. **`044 §21`·`§22`는 여전히 재범위화되지 않았고** 각각 별도 결정을 요구한다. 이 소절의 R-1…R-12는 그대로 유지되며 `044 §23`은 그중 어느 것도 변경하지 않는다.

**Deferred (이후 milestone):** `§15.4`의 deferred 목록 전체가 그대로 유지되며, 여기에 이 세대의 Export 연결과 `ApprovedEditDecision`의 downstream 소비가 더해진다. 이들 중 어느 것도 이 소절이 확정한 admission 경계의 전제가 아니므로 effective-transcript Review Foundation 구현을 막지 않는다. *(후속 기록: 여기 더해진 "이 세대의 Export 연결" 중 **admission 경계**는 `044 §23`(`patches/PATCH-0035`)이 확정했다. `044 §21` Artifact와 `§22` serialization의 이 세대 연결은 그대로 deferred다.)*

### 7.6 Effective-Transcript Generation — Review Authority History and Current Selection

이 소절은 `PATCH-0034`로 승인된 Architect Decision(AH-1…AH-12)을 기록한다. `§7.5`의 **Sections Not Re-scoped**가 "그때의 승인된 PATCH가 내린다"고 남겨 둔 결정 중 **revision·supersession과 current-selection semantics**를 effective-transcript generation에 한해 확정한다. `§3`·`§7`의 Review 개념, `§7.4`의 legacy 계약, `§7.5` R-1…R-12는 삭제·재작성·소급 해석되지 않는다. 결정 번호에 `AH-` 접두사를 쓰는 것은 authority history를 다루기 때문이며 계약상 의미는 없다.

**Scope and Instrument (Confirmed, AH-1):** 이 소절은 **effective-transcript generation에만** 적용된다. `§7.4`의 legacy execution-coupled generation은 이 소절로부터 authority history를 얻지 않으며, 그 세대의 caller-owned identity와 상수 `sequence`는 자기 세대의 계약으로 그대로 남는다. 두 세대는 계속 영구히 구분 가능하고, 한 세대의 이력을 다른 세대의 판단 근거로 교차 사용하지 않는다.

**Requirement Basis (Confirmed, AH-2):** 이 소절은 새 제품 요구를 만들지 않는다. `§3.5`는 이미 "결정이 현재 유효한지, 이후 판단으로 대체되었는지"를 **구분할 수 있어야 한다**고 요구했고, `§15.4`가 deferred로 둔 것은 그 **구체적인 표현**이었다. 이 소절은 그 표현을 이 세대에 대해 제공한다. `§3.5`가 금지한 **고정 상태 목록과 상태 전이 모델은 도입하지 않으며**, `§7.5` R-4의 Alternative A(별도 durable status 필드·state machine·transition 모델 없음)도 유지된다.

**Released Idiom Reused (Confirmed, AH-3):** 메커니즘은 새로 발명되지 않는다. `040 §18` H-5(**append-only** history; 각 authority 변경은 `previous_decision_id`로 이전 current를 supersede하는 새 immutable record)와 H-6(**current**는 최고 `sequence` record이며 persist된 상태에서 **파생**되고 중복 저장되지 않는다)의 **도메인 의미**를 재사용하며, 그 세대의 released persistence 컬럼 구성이나 legacy provenance 요구는 상속하지 않는다(`041 §15` E3의 semantic-reuse 관용구와 정합). latest-row heuristic, auto-increment 단독, mutable flag는 어느 경우에도 current의 근거가 될 수 없다 — 그 금지의 근거는 H-6(current는 최고 `sequence`에서 파생된다)과 `§7.5` R-4이며, `041 §15` E7은 같은 항목들을 **identity 입력**으로 금지한 인접 선례다(currentness 근거에 대한 authority가 아니다).

**Separate History Record, Canonical Records Unchanged (Confirmed, AH-4):** authority history는 **별개의 canonical 기록**이 담으며, `ReviewDecision`·`ApprovedEditDecision`에 ordinal·`previous` link·status 컬럼을 **추가하지 않는다.** 이유는 released 계약의 보존이다: `§7.5` R-10이 확정한 identity 구성(anchor Candidate + decision kind + human actor)과 R-11의 수렴 규칙은 이미 released이므로, 그 identity에 ordinal을 넣으면 **이미 존재하는 모든 기록의 identity 값이 바뀌어** released 의미가 변형된다. 이는 additive-evolution 계약이 금지한다. 따라서 두 canonical 기록은 `§7.5`가 확정한 그대로 유지된다 — 같은 identity 구성, 같은 수렴 동작, ordinal·status·`previous` link 없음.

**Authority History Entry (Confirmed, AH-5):** history의 각 위치는 하나의 **durable·immutable·insert-only·identity-owning·provenance-bearing·replay-safe** 기록이다. 최소 canonical 정보: 자신의 identity, 정확히 하나의 anchor Edit Candidate(`042 §9.3`), 하나의 **human actor reference**, 그 (Candidate, actor) 이력 안에서의 위치 `sequence`, 그 위치의 판단인 **정확히 하나의 `ReviewDecision` 참조**, 그리고 `sequence > 0`인 경우 자신이 supersede하는 **이전 위치 참조**. 이 기록은 참조한 판단의 payload를 **복제하지 않는다** — decision kind·승인 range·승인 Candidate Type/label·승인 rationale은 `ReviewDecision`과 `ApprovedEditDecision`이 소유하며 anchor를 통해 도달한다(`042 §8.2` D-2·`§7.2` S-2·`§9.3` C-8·`§7.5` R-7이 확립한 "anchor를 통해 상속하고 복제하지 않는다" 선례). status 필드, currentness, wall-clock, execution provenance, Domain Result는 갖지 않는다.

**History Scope Is Per Candidate and Actor (Confirmed, AH-6):** `§7.5` R-10이 human actor를 identity에 참여시키므로, 한 Candidate에 대한 이력은 **(Candidate, actor) 단위**로 존재한다. `sequence`는 각 (Candidate, actor) 안에서 0부터 **연속**이고, `sequence = 0`은 이전 위치를 갖지 않으며 `sequence > 0`은 반드시 이전 위치를 참조한다. 어떤 기록도 자신을 이전 위치로 참조하지 않으며, 하나의 (Candidate, actor, sequence)에는 **최대 하나**의 기록만 존재한다.

**하나의 `ReviewDecision`은 여러 위치에서 참조될 수 있다.** 이는 이 소절이 닫으려는 사례 그 자체다: `accept` → `reject` → 다시 `accept`에서 canonical 기록은 R-11에 따라 두 개로 수렴하지만 이력은 세 위치를 가지며, 위치 0과 위치 2가 **같은** `accept` 기록을 참조한다. 따라서 이력 관계에 `ReviewDecision`당 유일성 제약(`§7.4`의 `ApprovedEditDecision` 1:1 제약과 같은 형태)을 두는 것은 **금지된다** — 그 제약은 번복 이력을 표현 불가능하게 만든다. 유일성은 (Candidate, actor, sequence)에만 적용된다.

**Append Rule (Confirmed, AH-7):** 하나의 (Candidate, actor)에 대해 현재 head를 기준으로 판정한다. 이력이 없으면 첫 판단이 **`sequence` 0으로 insert**된다. 제출된 판단이 참조할 canonical `ReviewDecision`이 현재 head가 참조하는 것과 **동일**하면 **reuse**이며 새 위치를 만들지 않는다(idempotent replay). **다르면** `sequence + 1`에 **append**하고 이전 head를 supersede한다. 이 `sequence + 1` 파생은 이 소절이 **명시적으로 허용**하며, `§7.5` R-9가 금지한 것과 다른 것이다: R-9의 금지는 **per-admission ordinal**에 대한 것이고 그 ordinal은 여전히 존재하지 않는다. 이 이력 ordinal에서도 다음은 계속 금지된다 — wall-clock order, insertion order, rowid, DB row count, race-dependent order, 그리고 **그 정확한 (Candidate, actor) 이력의 persist된 head가 아닌 것에서 파생하는 모든 ordinal**.

**Derived Current, Never Stored (Confirmed, AH-8):** 하나의 (Candidate, actor)에 대한 **현재 유효한 판단**은 최고 `sequence` 기록이며, persist된 행에서만 **파생**된다. 저장된 flag가 아니고, latest-row heuristic이 아니며, 관측이 어떤 기록도 변경하지 않는다. supersede된 위치는 **유효한 immutable history**로 남으며 삭제·무효화·재작성·재번호되지 않는다(`§2.8`, `§3.9`, `§13`, `§7.5` R-5).

**Current Selection per Candidate and the Multi-actor Boundary (Confirmed, AH-9):** 하나의 Candidate에 대해서는 다음과 같다. 이력을 가진 actor가 **정확히 하나**이면 그 actor의 현재 판단이 그 Candidate의 **현재 유효한 판단**이다. 이력을 가진 actor가 **둘 이상**이면 **현재 유효한 판단을 파생하지 않는다.** 그 상황은 `§3.12` Review Conflict이며, 사용자가 차이를 이해하고 다시 판단할 수 있도록 **표시**되어야 하고 자동으로 해소되지 않는다 — actor 사이의 우선순위, 최신성(recency), 역할·권한 서열, 그 밖의 어떤 자동 authority 순위도 이 소절은 정의하지 않으며 도입을 금지한다. 이 소절은 `§15.3`의 열린 질문("여러 사용자가 같은 Review 대상에 판단할 경우 권위와 Conflict를 어떻게 해석해야 하는가")에 **답하지 않고 명시적으로 유보한다.** `§15.4`의 multi-user conflict resolution은 그대로 deferred다.

**Standing Orthogonality (Confirmed, AH-10):** authority history는 GOAL-023 파생 admission standing과 **직교**한다. 새 위치의 append는 `§7.5` R-3의 standing이 **`current`일 때만** 허용된다. upstream authority가 변경되어도 기존 위치는 수정·삭제·재번호되지 않고(`§7.5` R-5), superseded 연쇄는 결코 저장소 손상이 아니다(`040 §18` H-12 관용구). 현재 유효한 판단의 관측은 standing과 무관하게 허용되며 어떤 기록도 변경하지 않는다. 현재 유효한 판단이라는 사실은 그 자체로 Export 적격성이 아니다 — 이 세대의 승인 기록을 `044`에 연결하는 결정은 `§7.5`가 명시한 대로 여전히 별도 결정이다.

**Export 적격성의 확정 (Confirmed, PATCH-0035):** 위 문장이 "그 자체로는 아니다"라고만 하고 남겨 둔 실제 조건은 `044 §23` EA-4가 확정한다: 이 세대의 하나의 `ApprovedEditDecision`은 **(i)** 그것이 AH-8에 따라 파생된 **현재 유효한 판단**이 소유한 승인이고, **(ii)** 그 Candidate에 이력을 가진 actor가 AH-9의 의미로 **정확히 하나**이며, **(iii)** `§7.5` R-3의 연쇄 뿌리 standing이 **`current`**일 때 export 적격이다. 세 조건이 함께여야 하며 currentness 하나로는 여전히 충분하지 않다는 위 규정은 그대로 유지된다. 관측이 standing에 무관하다는 위 규정도 그대로다 — 적격성 판정만 standing을 요구한다. actor가 둘 이상인 Candidate에 대해 `044 §23` EA-5는 **어떤 중재도 하지 않으며** AH-9가 파생하지 않는 곳에서 operative judgment를 파생하지 않는다. `§15.3`의 다중 사용자 질문은 그 절에서도 **답해지지 않는다.**

**Identity Direction and Reachability (Confirmed, AH-11):** history 기록의 identity는 **Application이 소유**하며 immutable anchor와 안정적인 이력 위치에서 결정적으로 파생된다. provider 식별자, execution framework 식별자, `DomainResult` identity, UUID, timestamp, wall-clock, rowid, 물리 경로, mutable currentness는 참여하지 않는다. **정확한 hash 구성은 이 소절에서 확정하지 않고 구현 milestone에 위임한다**(`041 §15` E7, `042 §8.2` D-8·`§7.2` S-10·`§9.3` C-10, `§7.5` R-10의 선례). 다만 구현은 identity에 참여하는 persisted 필드와 참여하지 않는 필드를 명시하고, 그 선택이 conflict 분기를 도달 가능하게 하는지를 `§7.5` R-10의 (A)/(B) 회계로 기록해야 하며, **(B)를 택하더라도 semantic equality 검사를 제거하지 않는다.** 동일 identity에 대해 의미가 다른 기록이 제출되면 덮어쓰지 않고 **명시적 conflict**로 거부한다(`040 §18` H-9). 근접 동시 동일 제출은 중복 위치 없이 수렴한다.

**Persisted Representation and Atomicity (Confirmed, AH-12):** 이 소절은 **의미**만 확정하고 물리적 저장 형태를 확정하지 않는다. 필요한 형태는 `041 §15` E1, `042 §8.2` D-11·`§7.2` S-12·`§9.3` C-12, `§7.5` R-12의 선례를 따라 **strictly additive한 새 versioned representation**으로 도입하며, legacy `edit_review_decisions`·`approved_edit_decisions` 관계와 이 세대의 released Review 관계는 **재해석·backfill·dual-write 없이 그대로 남는다 — released 행은 자신의 identity와 컬럼을 정확히 유지한다.** 하나의 판단을 기록하는 admission은 그 `ReviewDecision`, 해당되는 경우의 `ApprovedEditDecision`, 그리고 이력 위치를 **하나의 atomic all-or-nothing 단위**로 기록한다(`§7.5` R-11 확장); 판단만 있고 위치가 없거나 위치만 있고 판단이 없는 부분 기록은 유효한 것으로 보일 수 없다. **이 계약 이전에 admit된 `ReviewDecision`은 이력 위치를 갖지 않을 수 있으며 그것은 손상이 아니다** — 위치의 부재는 그 (Candidate, actor)에 대해 기록된 authority 이력이 없다는 뜻일 뿐이고(`040 §18` H-2의 "부재로 파생" 관용구와 정합), validation은 이를 결함으로 표시하지 않는다. 이력 위치의 **소급 합성(backfill)은 금지된다**: 기존 기록들 사이의 순서를 결정할 근거가 persist되어 있지 않으므로 어떤 backfill도 날조가 된다. 그 (Candidate, actor)에 대한 이후 첫 admission이 `sequence` 0으로 이력을 시작한다.

이 두 규정은 **서로 다른 시점에 적용되므로 충돌하지 않는다**: all-or-nothing은 **기록 시점(write-time)**의 트랜잭션 의무이고, 위치 부재의 허용은 **판독 시점(read-time)**의 분류 규칙이다. 그 결과 이 계약 이후의 admission은 위치 없는 판단을 만들 수 없고, validation은 관측되는 그 행 형태에 대해 "기록된 authority 이력 없음"이라는 **하나의** 답을 갖는다. 반대 형태(판단 없는 위치)는 AH-5가 `ReviewDecision` 참조를 필수로 두므로 구조적으로 존재할 수 없다. 구현은 이 두 적용 지점을 함께 기록해야 하며, all-or-nothing 규정을 위치 없는 기존 판단을 결함으로 보는 근거로 읽어서는 안 된다.

**Sections Not Re-scoped (Confirmed):** 이 소절은 `§7.4`의 legacy 계약, `§7.5` R-1…R-12, `042`의 어떤 소절, `044`의 Export 계약을 재범위화하지 않는다. 특히 `§7.4`의 **"하나의 `ReviewDecision`은 최대 하나의 `ApprovedEditDecision`을 만든다"**와 `§7.5` R-10의 released identity 구성은 그대로이며, 그 결과 **같은 kind에 승인 내용만 다른 재제출은 이력으로 표현되지 않고 R-11의 명시적 conflict로 남는다**(위 `§7.5` "공백의 해소 범위" 참조). Review Session persistence, 별도 Review History 모델, 다중 Candidate Review Item과 grouping, multi-user conflict resolution, 포괄적 human authority policy, Candidate reconciliation, withdrawal·revocation, stale 탐지, Review Context 품질 기준, Review UI와 외부 Review API, provider-assisted Review, confidence·priority·severity·quality score도 재범위화되지 않는다(`§15.4`).

**Deferred (이후 milestone):** `§15.4`의 deferred 목록은 이 소절이 확정한 revision·supersession·current-selection 표현을 제외하고 그대로 유지된다. 여기에 더해 다음이 명시적으로 유보된다: 다중 actor 사이의 authority 해석(`§15.3`), 같은 kind·다른 승인 내용의 이력 표현, 사람의 판단 철회(withdrawal)와 취소(revocation), 그리고 이 세대 승인 기록의 `044` Export 연결. 이들 중 어느 것도 이 소절이 확정한 경계의 전제가 아니므로 구현을 막지 않는다.

*(후속 기록, `PATCH-0035`: 위 목록의 마지막 항목 "이 세대 승인 기록의 `044` Export 연결" 중 **admission 경계**는 `044 §23`(EA-1…EA-11)이 확정했다 — AH-8의 파생 current와 AH-9의 단일-actor 조건이 `§7.5` R-3의 standing과 함께 `044 §23` EA-4의 export 적격성을 이룬다. 나머지는 그대로 deferred다: `044 §21` Artifact와 `§22` serialization의 이 세대 연결, 다중 actor 사이의 authority 해석(`§15.3`), 같은 kind·다른 승인 내용의 이력 표현, withdrawal과 revocation. 여기에 더해 `044 §23`이 자기 Deferred로 남긴 것 — Conflict가 존재하는 timeline에서 Export Admission의 제품 동작, overlap 판정, 적격 member 없는 scope의 처리 — 도 이 소절이 확정하지 않는다.)*

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
- effective-transcript generation의 Review admission 경계는 `§7.5`(`patches/PATCH-0033`)에서 확정되었다: Review admission 경계도 legacy execution-coupled generation과 effective-transcript generation의 **두 contract generation**으로 존재하며(`§7.5` R-1) 두 세대는 영구히 구분 가능하다. 현행 세대에서 `ReviewDecision`은 **정확히 하나의 `042 §9.3` Edit Candidate**에 anchor하고(R-2; cardinality와 방향은 `§7.4` 그대로이며 바뀌는 것은 Candidate의 세대뿐이다), 연쇄 뿌리의 `Lecture Analysis Input Admission` 파생 standing이 **`current`일 때만** admit되며(R-3; released 3값 vocabulary를 확장하지 않고 없거나 malformed인 참조는 standing 값이 아니다), Alternative A와 무-저장 currentness가 유지된다(R-4). superseded 연쇄의 모든 기록은 **유효한 immutable history**로 보존되고 authority 복귀 시 admission 가능성이 복원된다(R-5). 현행 세대는 `ProcessingRun`·`UnitExecution`·RUNNING state에 더해 **두 기록의 Domain Result identity 소유와 직접 Domain Result chaining도 요구하지 않는다** — `§9.3` Candidate가 Domain Result를 만들지 않아 소유·참조 대상이 존재하지 않기 때문이며, 이 점이 `042 §9.3` C-7보다 한 걸음 더 나아간 지점이다(R-6). `§7.4`가 요구한 Source Media·Source Timeline provenance는 **사라지지 않고** anchor 연쇄를 통해 확보되며 표현 형태만 달라진다(R-7). **`§7.4`의 canonical 기록 계약(닫힌 decision kind, Approved 생성 규칙과 승인 스냅샷 소유, Modify ownership, Alternative A, human actor reference, atomic admission, 실행 semantics 금지를 포함)은 변경되지 않는다**(R-8). per-admission `sequence`는 저장되지 않는다 — 하나의 admission이 최대 두 기록만 만들어 ordinal이 구조적으로 단일값이고 released legacy 구현이 상수를 부여한다는 사실로 확인되었다(R-9). `040 §18` H-5…H-8의 **per-anchor authority-history ordinal**은 이와 별개의 개념으로 명시적으로 구분되며 도입되지도 부정되지도 않고 `§15.4` deferred로 남는다. 그 결과 판단 번복 시 모순되는 두 기록이 현재-유효 판정 없이 이력으로 공존하는데, 이는 legacy 상수-`sequence` 경로에서 물려받은 공백이며 그 해소는 별도의 승인된 PATCH에 속한다. identity는 Application 소유·결정적이며 **human actor reference가 참여해야** 하고(R-10; caller-owned identity는 legacy 세대 전용), replay/conflict 의미와 atomic 요구는 유지된다(R-11). legacy `edit_review_decisions`·`approved_edit_decisions` 관계는 재사용하지 않고 strictly additive한 새 versioned representation을 도입하며, `ReviewDecision`당 최대 하나의 `ApprovedEditDecision`은 **계약이 뒷받침하는 uniqueness**다(R-12; `042 §7.1`이 uniqueness를 금지한 경우와 반대). **`044` Export는 재범위화되지 않았고** 이 세대의 승인 기록을 Export에 연결하려면 별도 결정이 필요하다. Review Session·Review Item grouping·multi-user·reconciliation·revision·withdrawal·current-selection·Review UI/API 등은 **여전히 deferred**다.
- effective-transcript generation의 Review **authority history와 current selection** 경계는 `§7.6`(`patches/PATCH-0034`)에서 확정되었다: `§3.5`가 요구한 "현재 유효/대체됨" 구분의 **표현**을 이 세대에 제공하되(AH-2), 고정 상태 목록·state machine·mutable flag는 도입하지 않는다. 메커니즘은 `040 §18` H-5·H-6의 **도메인 의미 재사용**이며(AH-3), 이력은 두 canonical 기록에 컬럼을 추가하지 않는 **별개의 append-only 기록**이 담는다 — released identity 구성을 바꾸면 이미 존재하는 모든 기록의 identity 값이 변형되기 때문이다(AH-4·AH-5). 이력은 **(Candidate, actor) 단위**이고 `sequence`는 0부터 연속이며(AH-6), 참조 판단이 head와 다르면 `sequence + 1`로 append한다(AH-7; R-9가 금지한 per-admission ordinal은 계속 존재하지 않는다). 현재 유효한 판단은 최고 `sequence`에서 **파생**되고 저장되지 않는다(AH-8). 한 Candidate에 이력을 가진 actor가 둘 이상이면 **현재 유효한 판단을 파생하지 않고** `§3.12` Review Conflict로 표시하며, `§15.3`의 다중 사용자 권위 질문에는 **답하지 않고 명시적으로 유보한다**(AH-9). append는 standing이 `current`일 때만 허용되고 기존 위치는 authority 변경으로 수정되지 않는다(AH-10). identity는 Application 소유·결정적이며 hash 구성과 conflict 도달 가능성 기록은 구현 milestone에 위임된다(AH-11). 저장 형태는 strictly additive하고, 판단·승인·이력 위치는 하나의 atomic 단위로 기록되며, 이 계약 이전 기록의 위치 부재는 손상이 아니고 **소급 backfill은 금지된다**(AH-12).

### 15.2 Working Assumption

- Review Session은 여러 Review Item과 반복 판단을 연결하는 개념적 문맥으로 유용하다.
- Review Context는 대상 유형에 따라 서로 다른 근거를 포함할 수 있다.

### 15.3 Requires Validation

- 하나의 Review Item이 여러 Candidate 또는 서로 다른 Pipeline의 대상을 묶어야 하는 경우가 있는가?
- 여러 사용자가 같은 Review 대상에 판단할 경우 권위와 Conflict를 어떻게 해석해야 하는가?
- 재처리 후 Candidate Reconciliation에서 자동으로 제시할 수 있는 관계의 범위는 어디까지인가?
- Review Context가 충분하다고 판단하는 제품 수준 기준은 무엇인가?

다중 사용자 질문에 대해: `§7.6`(AH-9)은 effective-transcript generation에서 이 질문에 **답하지 않는다.** 이력을 가진 actor가 둘 이상인 Candidate에 대해 현재 유효한 판단을 파생하지 않고 `§3.12` Review Conflict로 표시하며, 자동 authority 순위의 도입을 금지한다. 따라서 위 질문은 **여전히 열린 상태**이고, 그 해석은 이후 승인된 PATCH가 내린다.

### 15.4 Deferred

- Review 상태와 전이의 구체적인 표현
- Review Session과 Review History의 저장 및 실행 방식
- Candidate reconciliation의 구현 방법
- Review Interface의 구체적인 상호작용과 화면 구성
- export 형식과 외부 NLE 연동 방식

첫 항목("Review 상태와 전이의 구체적인 표현")에 대해: effective-transcript generation에 한해 **현재 유효/대체됨 구분의 표현**은 `§7.6`(`patches/PATCH-0034`)이 확정했다 — append-only authority history와 그로부터의 파생이며, 고정 상태 목록과 상태 전이 모델은 여전히 정의되지 않는다. legacy 세대와, 같은 kind·다른 승인 내용의 이력 표현, withdrawal·revocation, 다중 actor 권위 해석은 **그대로 deferred**다.

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
