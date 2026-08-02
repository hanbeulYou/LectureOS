# 044_EXPORT_PIPELINE

- Status: Draft
- Version: Blueprint 1.1
- Last Updated: 2026-08-02
- Depends On: `000_MANIFESTO.md`, `001_PRODUCT.md`, `002_FAQ.md`, `003_VISION.md`, `004_PRINCIPLES.md`, `020_PRODUCT_REQUIREMENTS.md`, `021_SYSTEM_CONTEXT.md`, `030_DATA_MODEL.md`, `031_ARCHITECTURE.md`, `040_TRANSCRIPT_PIPELINE.md`, `041_SUBTITLE_PIPELINE.md`, `042_LECTURE_INTELLIGENCE_PIPELINE.md`, `043_REVIEW_PIPELINE.md`
- Referenced By:
- Amended By: `patches/PATCH-0007-physical-materialization.md`, `patches/PATCH-0008-delivery-deferral.md`, `patches/PATCH-0015-edit-pipeline-export-application-foundation.md`, `patches/PATCH-0016-edit-export-assembly-scope.md`, `patches/PATCH-0017-edit-export-artifact-representation.md`, `patches/PATCH-0018-edit-export-json-serialization-and-local-materialization.md`, `patches/PATCH-0035-effective-transcript-edit-export-admission-boundary.md`, `patches/PATCH-0036-effective-transcript-edit-export-artifact-boundary.md`, `patches/PATCH-0037-effective-transcript-edit-export-serialization-boundary.md`, `patches/PATCH-0038-effective-transcript-edit-export-cross-actor-conflict-disclosure-boundary.md`

## Purpose

이 문서는 LectureOS 내부의 승인된 결과를 외부에서 사용할 수 있는 Artifact로 표현하는 Export Pipeline을 정의한다.

Export Pipeline은 LectureOS의 마지막 Pipeline이다. Final Subtitle과 Approved Edit Decision을 외부 표현으로 변환하지만 새로운 분석, 판단, 승인 또는 편집을 만들지 않는다.

이 문서는 Export의 개념, 책임, 경계와 보장 사항을 정의한다. 구체적인 파일 형식, schema, 외부 시스템 연동, Rendering 또는 실행 방법은 정의하지 않는다.

## 1. Pipeline Scope

### 1.1 포함 범위

- Export Input
- Export Configuration
- Export Artifact
- Artifact Provenance
- Export Profile
- Export Representation
- Export Scope
- Export Validation
- Export Traceability
- Export Failure
- Export Reproducibility
- Final Subtitle과 Approved Edit Decision의 외부 표현

### 1.2 제외 범위

- Source Media 변경
- Transcript 또는 Subtitle 내용 변경
- Lecture Analysis와 Edit Candidate 생성
- Review와 Human Decision 생성
- 자동 승인 또는 자동 편집
- 미디어 Rendering
- 외부 시스템의 처리와 정책
- 특정 export 형식 또는 NLE 통합

Export Pipeline은 승인 결과를 표현할 뿐 그 의미를 다시 결정하지 않는다. Artifact를 생성해도 upstream Concept와 Human Decision의 권위는 그대로 유지된다.

## 2. Pipeline Principles

### 2.1 Export Is Not Review

Export는 승인 여부를 판단하지 않는다. 각 결과를 책임지는 Pipeline이 적용 가능한 Human Decision을 반영해 준비한 승인 결과만 Export Input으로 사용할 수 있다.

### 2.2 Export Is Not Editing

Export는 Source Media에 컷을 적용하거나 편집 결과를 만들지 않는다. Approved Edit Decision을 외부에서 사용할 수 있는 표현으로 변환한다.

### 2.3 Artifact Is Not Decision

Export Artifact는 Approved Edit Decision을 표현한 파생 결과다. Artifact 자체가 Human Decision이나 승인 결과의 중심 기록이 되어서는 안 된다.

### 2.4 Artifact Is Not Source

Artifact는 Source Media, Source Timeline 또는 upstream Concept를 대체하지 않는다. 외부 표현을 다시 가져와 원본 사실로 취급하지 않는다.

### 2.5 Rendering Is Not Approval

외부 시스템이 Artifact를 처리하거나 결과를 Rendering하더라도 LectureOS의 Approval 의미가 새로 생성되거나 변경되지 않는다.

### 2.6 Representation Is Not Meaning

동일한 승인 결과는 서로 다른 Export Representation으로 표현될 수 있다. 표현 방식의 차이가 승인된 의미의 차이를 자동으로 뜻하지 않는다.

### 2.7 Provider Independence

Export Concept는 특정 NLE, subtitle format, vendor 또는 export format에 종속되지 않는다. 외부 형식은 교체 가능한 표현 경계다.

### 2.8 Human Authority

Export Configuration이나 외부 consumer는 Human Decision을 변경하거나 새로 승인할 권위를 갖지 않는다.

### 2.9 Source Timeline Traceability

시간 기반 Export Artifact는 Final Subtitle 또는 Approved Edit Decision을 거쳐 Source Timeline으로 추적 가능해야 한다.

### 2.10 Deterministic Export

동일한 승인 입력과 동일한 Export Configuration은 동일한 의미의 Export Artifact를 재생성할 수 있어야 한다. 이는 특정 serialization의 byte-level 동일성을 확정하는 규칙이 아니다.

## 3. Core Concepts

### 3.1 Export Input

Export Input은 외부 표현을 만들기 위해 사용할 수 있는 승인된 LectureOS 결과다.

현재 Export Input은 다음을 포함한다.

- Final Subtitle
- Approved Edit Decision

Analysis Finding, Edit Candidate, Review Item 또는 미완료 Review Decision은 그 자체로 승인된 Export Input이 아니다. Export Input은 원래 결과의 provenance와 현재 적용 가능한 승인 상태를 유지해야 한다.

### 3.2 Export Configuration

Export Configuration은 특정 export에서 어떤 승인 결과를 어떤 Export Profile과 Export Scope로 표현할지 설명하는 적용 문맥이다.

Export Configuration은 승인 결과의 의미를 변경하지 않는다. 구체적인 필드, 저장 방식 또는 외부 형식별 옵션은 이 문서에서 정의하지 않는다.

### 3.3 Export Artifact

Export Artifact는 승인된 LectureOS Concept를 외부 consumer가 사용할 수 있도록 표현한 파생 결과다.

Export Artifact는 다음 특성을 가진다.

- Final Subtitle 또는 Approved Edit Decision에서 파생된다.
- 사용한 Export Configuration, Export Profile과 Export Scope를 설명할 수 있다.
- 가능한 경우 Source Timeline과 승인 결과로 추적할 수 있다.
- 삭제되거나 손상되어도 원본, Review History 또는 승인 결과를 손상시키지 않는다.
- 보존된 입력과 설정에서 다시 생성할 수 있다.

### 3.4 Artifact Provenance

Artifact Provenance는 Export Artifact가 어떤 Export Input, Export Configuration, Export Profile과 Export Scope에서 생성되었는지 설명한다.

Artifact Provenance는 Artifact가 승인 결과를 대신하게 하지 않는다. 외부 provider나 consumer의 식별자가 LectureOS Artifact의 유일한 정체성이 되어서는 안 된다.

### 3.5 Export Profile

Export Profile은 특정 외부 사용 목적에 맞는 표현 규칙과 기대를 개념적으로 묶는다.

Profile은 다음을 설명할 수 있다.

- 어떤 종류의 Export Input을 표현하는가?
- 어떤 외부 사용 목적을 위한 표현인가?
- 어떤 의미와 traceability를 유지해야 하는가?

Export Profile은 특정 vendor를 Blueprint의 영구 전제로 만들지 않으며 구체적인 형식 명세가 아니다.

### 3.6 Export Representation

Export Representation은 승인된 의미를 외부에서 소비할 수 있게 나타내는 방식이다. 사람이 읽을 수 있는 표현 또는 기계가 읽을 수 있는 표현을 지원할 수 있다.

Final Subtitle의 외부 표현과 Approved Edit Decision의 외부 표현은 서로 다른 목적을 가질 수 있다. 이 문서는 구체적인 문법이나 format을 정의하지 않는다.

### 3.7 Export Scope

Export Scope는 하나의 export가 포함하는 승인 결과의 범위를 설명한다. 전체 승인 결과 또는 명시적으로 선택된 일부 결과를 대상으로 할 수 있다.

Scope가 제한되었음을 숨기거나 제외된 결과를 승인되지 않은 것으로 해석해서는 안 된다. Export Scope는 Review Decision을 변경하지 않는다.

### 3.8 Export Validation

Export Validation은 Export Input, Configuration, Profile, Scope, Artifact와 provenance의 구조적 일관성을 확인하는 책임이다.

Validation을 통과했다는 사실은 외부 시스템의 동작, 편집 결과의 품질 또는 Rendering 성공을 보장하지 않는다.

### 3.9 Export Traceability

Export Traceability는 Artifact에서 사용한 승인 결과, Review Decision, Source Timeline과 Source Media까지의 관계를 설명할 수 있는 성질이다.

모든 외부 표현이 내부 계보 전체를 직접 포함해야 한다는 뜻은 아니다. LectureOS는 Artifact와 관련 내부 Concept 사이의 연결을 잃지 않아야 한다.

### 3.10 Export Failure

Export Failure는 승인 결과를 요구된 외부 표현으로 완전하고 추적 가능하게 만들지 못한 상태다. 실패는 빈 Artifact나 정상 완료로 숨기지 않는다.

### 3.11 Export Reproducibility

Export Reproducibility는 보존된 Export Input과 Export Configuration을 사용해 동일한 승인 의미를 가진 Artifact를 다시 생성할 수 있음을 뜻한다.

재생성은 이전 Artifact를 중심 데이터로 사용하지 않으며 Review Decision이나 Approved Edit Decision을 변경하지 않는다.

## 4. Conceptual Relationships

```text
Final Subtitle --------------------+
                                   |
Approved Edit Decision ------------+--> Export Input
                                             |
                                             v
                            Export Configuration
                            + Export Profile
                            + Export Scope
                                             |
                                             v
                                    Export Validation
                                             |
                                             v
                                      Export Artifact
                                             |
                                             v
                              External Export Consumer
```

이 그림은 승인된 내부 결과가 외부 표현으로 발전하는 개념적 관계를 보여준다. Export Pipeline은 Final Subtitle 또는 Approved Edit Decision을 생성하지 않으며 외부 consumer의 후속 처리를 소유하지 않는다.

## 5. Export Inputs

### 5.1 Final Subtitle

Final Subtitle은 Subtitle Pipeline에서 Review와 사용자 결정을 반영해 Artifact Generation에 사용할 수 있는 승인된 Subtitle 표현이다.

Export Pipeline은 Final Subtitle의 텍스트, 분할, 순서 또는 Time Range를 수정하지 않는다. 필요한 정보가 불완전하거나 구조적으로 유효하지 않다면 임의로 보완하지 않고 Export Failure로 드러낸다.

### 5.2 Approved Edit Decision

Approved Edit Decision은 Review Pipeline에서 사용자가 확정한 편집 판단이다. 외부 표현은 최소한 적용 가능한 다음 의미를 잃지 않아야 한다.

- Source Timeline의 관련 Time Range 또는 source reference
- 관련 구간 라벨
- 결정 상태와 최종 편집 의도
- Decision Modification이 있는 경우 승인된 변경 의미

Export Pipeline은 Approved Edit Decision을 실제 컷 명령이나 편집된 미디어로 바꾸지 않는다.

### 5.3 Ineligible Inputs

다음 결과는 승인 결과를 대신해 정상 Export Input으로 사용하지 않는다.

- 미승인 Subtitle Candidate 또는 revision
- Analysis Finding
- Edit Candidate
- Review Item
- unresolved Review Conflict 또는 Stale Candidate

이 결과들은 provenance나 진단 문맥으로 참조될 수 있지만 Export Pipeline이 새 승인 판단을 내려 사용할 수 있는 입력으로 승격하지 않는다.

## 6. Export Activity

Export Pipeline은 다음 책임을 수행한다.

1. 승인된 Export Input을 식별한다.
2. 적용할 Export Configuration, Export Profile과 Export Scope를 연결한다.
3. 승인된 의미를 Export Representation으로 표현한다.
4. Export Validation을 수행한다.
5. Artifact Provenance와 Export Traceability를 연결한다.
6. 성공한 Export Artifact 또는 명시적인 Export Failure를 제공한다.

이 목록은 구현 단계, 호출 방식 또는 실행 순서를 정의하지 않는다. 하나의 승인 결과에서 목적이 다른 Artifact를 만들 수 있으며, 각 Artifact의 provenance는 구분되어야 한다.

## 7. Export Representation

### 7.1 Final Subtitle Representation

Final Subtitle의 Export Representation은 외부 자막 사용을 위한 파생 Artifact다. Subtitle의 승인된 내용과 Source Timeline 연결을 유지하며 Final Subtitle 자체를 대체하지 않는다.

### 7.2 Approved Edit Decision Representation

Approved Edit Decision의 Export Representation은 외부 편집 과정에서 사람이 읽거나 외부 시스템이 처리할 수 있는 파생 Artifact다.

이 표현은 원본 시간 범위, 관련 라벨과 결정 상태를 유지해야 한다. 외부 NLE가 실제 편집을 어떻게 적용할지는 Export Pipeline이 결정하지 않는다.

### 7.3 Multiple Representations

하나의 승인 결과는 서로 다른 외부 목적을 위해 여러 Representation으로 표현될 수 있다. 각 Representation은 같은 Decision을 복제해 새 Decision으로 만들지 않으며 자신이 사용한 Profile과 Scope를 구분해야 한다.

## 8. Export Provenance and Traceability

Export Pipeline은 다음 관계를 설명할 수 있어야 한다.

```text
Final Subtitle or Approved Edit Decision
                    |
                    v
        Export Configuration
        + Export Profile
        + Export Scope
                    |
                    v
            Export Artifact
```

Artifact Provenance는 최소한 다음 질문에 답할 수 있어야 한다.

- 어떤 승인 결과를 표현했는가?
- 어떤 Export Configuration, Profile과 Scope를 사용했는가?
- 어떤 Source Media와 Source Timeline까지 추적되는가?
- 재생성된 Artifact라면 어떤 승인 문맥을 유지했는가?

Export는 Review Decision, Decision Provenance 또는 Review History를 변경하지 않는다.

## 9. Export Validation

Export Validation은 다음 개념적 책임을 가진다.

- Export Input이 승인된 현재 결과이며 필요한 의미를 갖추었는지 확인한다.
- 시간 기반 결과가 Source Timeline으로 추적 가능한지 확인한다.
- Artifact Provenance가 Export Input, Configuration, Profile과 Scope를 설명할 수 있는지 확인한다.
- Export Representation이 Profile과 Scope에 일관되는지 확인한다.
- 누락, 충돌 또는 표현 불가 상태를 정상 Artifact로 숨기지 않는다.

Validation은 다음을 보장하지 않는다.

- Subtitle이나 편집 판단의 교육적·편집적 품질
- 외부 consumer의 호환성 또는 정책 준수
- 외부 NLE에서의 실제 컷 결과
- Rendering 성공 또는 최종 미디어 품질

Validation Failure는 승인 결과를 변경하거나 Review를 다시 수행하는 근거가 아니다. 필요한 경우 Export Failure와 영향 범위를 보고한다.

## 10. Deterministic Export and Safe Reprocessing

동일한 Approved Edit Decision 또는 Final Subtitle과 동일한 Export Configuration을 사용하면 동일한 승인 의미의 Export Artifact를 재생성할 수 있어야 한다.

Export Profile이나 Export Scope가 달라지면 Artifact 표현은 달라질 수 있다. 이 경우에도 어떤 입력과 설정 차이가 결과를 만들었는지 provenance로 설명할 수 있어야 한다.

재생성은 다음을 보장해야 한다.

- Review Decision, Decision Provenance와 Review History를 수정하거나 삭제하지 않는다.
- Final Subtitle과 Approved Edit Decision을 Artifact 내용으로 역대체하지 않는다.
- 이전 Artifact를 덮어써도 승인 결과의 계보를 잃지 않는다.
- 실패한 재생성이 기존의 유효한 승인 결과를 손상시키지 않는다.
- 변경된 승인 입력으로 만든 Artifact를 이전 승인 문맥의 재현 결과처럼 표시하지 않는다.

byte-level 동일성, serialization 순서 또는 외부 format별 결정성은 이 문서에서 확정하지 않는다.

## 11. Failure Handling

### 11.1 Incomplete Export Input

Final Subtitle 또는 Approved Edit Decision이 필요한 승인 상태, traceability 또는 의미를 갖추지 못한 경우다. Export Pipeline은 누락을 임의로 채우거나 입력을 자동 승인하지 않는다.

### 11.2 Configuration or Profile Conflict

Export Configuration, Profile 또는 Scope가 Export Input의 종류나 유지해야 할 의미와 일관되지 않은 경우다. 충돌을 숨기고 그럴듯한 Artifact를 만들지 않는다.

### 11.3 Traceability Failure

시간 기반 결과가 Source Timeline으로 추적되지 않거나 Artifact Provenance를 설명할 수 없는 경우다. 영향받는 결과를 정상 Export Artifact로 취급하지 않는다.

### 11.4 Representation Failure

승인된 의미를 선택된 Export Representation으로 완전하게 표현할 수 없는 경우다. 표현 과정에서 의미를 조용히 버리거나 다른 의미로 바꾸지 않는다.

### 11.5 External Consumer Failure

외부 consumer가 Artifact를 받지 못하거나 처리하지 못한 상태는 LectureOS의 승인 결과와 구분한다. 외부 실패가 Human Decision을 무효화하거나 Artifact의 생성을 소급해 승인되지 않은 것으로 만들지 않는다.

### 11.6 Failure Reporting

Export Failure는 다음을 구분할 수 있어야 한다.

- 어떤 Export Input과 Export Scope가 영향을 받았는가?
- Artifact가 생성되지 않았는가, 불완전한가, 사용할 수 없는가?
- 어떤 provenance 또는 traceability가 유지되지 않았는가?
- 외부 consumer 경계 이전과 이후 중 어디에서 문제가 드러났는가?

구체적인 오류 분류, 복구 절차 또는 재시도 방식은 정의하지 않는다.

## 12. Pipeline Boundaries

### 12.1 `040_TRANSCRIPT_PIPELINE.md`와의 경계

Transcript Pipeline은 Raw Transcript와 Corrected Transcript를 생성·관리한다. Export Pipeline은 Transcript를 수정하거나 Transcript revision을 승인하지 않으며, Transcript 자체를 현재 승인 Artifact 입력으로 정의하지 않는다.

### 12.2 `041_SUBTITLE_PIPELINE.md`와의 경계

Subtitle Pipeline은 Subtitle Candidate, revision과 Final Subtitle을 생성·관리한다. Export Pipeline은 Final Subtitle만 승인 입력으로 받아 외부 표현을 만들며 Subtitle의 내용, 분할 또는 timing을 변경하지 않는다.

### 12.3 `042_LECTURE_INTELLIGENCE_PIPELINE.md`와의 경계

Lecture Intelligence Pipeline은 Analysis Finding과 Edit Candidate를 생성한다. Export Pipeline은 이를 승인 입력으로 승격하거나 분석하지 않으며 직접 Artifact로 변환하지 않는다.

### 12.4 `043_REVIEW_PIPELINE.md`와의 경계

Review Pipeline은 Human Decision과 Approved Edit Decision을 책임진다. Export Pipeline은 Approved Edit Decision을 외부 표현으로 변환하지만 Decision, provenance 또는 Review History를 변경하지 않는다.

### 12.5 External Consumer와의 경계

외부 consumer는 Artifact를 사용해 후속 편집, 확인 또는 전달을 수행할 수 있다. Export Pipeline은 외부 시스템의 정책, 실제 편집, Rendering 또는 결과 해석을 소유하지 않는다.

## 13. Invariants

- Export Pipeline은 Review Decision이나 Approved Edit Decision을 생성하지 않는다.
- Export Artifact는 Final Subtitle 또는 Approved Edit Decision을 대체하지 않는다.
- Artifact는 Source Media 또는 Source Timeline의 권위를 가질 수 없다.
- Analysis Finding, Edit Candidate와 Review Item은 승인 결과처럼 export할 수 없다.
- Export Configuration은 승인된 의미를 변경할 수 없다.
- 시간 기반 Artifact는 Source Timeline traceability를 잃으면 안 된다.
- Artifact Provenance는 Export Input, Configuration, Profile과 Scope까지 설명할 수 있어야 한다.
- Export Validation은 Human Approval이나 편집 품질 판단이 아니다.
- 외부 consumer의 결과는 LectureOS의 새 Approval로 간주되지 않는다.
- Artifact 손실은 원본, Review History 또는 승인 결과의 손실을 의미하지 않는다.
- 재생성은 Review Decision과 Decision Provenance를 수정하거나 삭제하지 않는다.
- provider 또는 외부 format 고유 표현이 Export Concept의 정체성을 독점할 수 없다.
- Export Failure는 정상 Artifact로 숨기지 않는다.

## 14. Acceptance Criteria

- Final Subtitle과 Approved Edit Decision이 Export Input으로 명확히 정의된다.
- Export Input, Configuration, Profile, Representation, Scope와 Artifact가 구분된다.
- Artifact와 Decision, Source의 책임이 구분된다.
- Export가 Review, Editing, Approval 또는 Rendering을 수행하지 않는다.
- Final Subtitle과 Approved Edit Decision의 의미가 외부 표현에서 유지된다.
- 시간 기반 Artifact가 Source Timeline으로 추적 가능하다.
- Artifact Provenance와 Export Traceability가 보존된다.
- Export Validation과 외부 품질·동작 보장이 구분된다.
- 동일한 승인 입력과 Export Configuration에서 동일한 의미의 Artifact를 재생성할 수 있다.
- Export Failure가 승인 결과와 구분되어 보고된다.
- Artifact 손실이나 재생성이 Human Decision과 Review History를 손상시키지 않는다.
- 특정 NLE, subtitle format, vendor 또는 export format에 종속되지 않는다.

## 15. Assumptions and Open Questions

### 15.1 Confirmed

- Final Subtitle과 Approved Edit Decision은 외부 Artifact를 만들 수 있는 승인 결과다.
- Approved Edit Decision export는 원본 시간 범위, 구간 라벨과 결정 상태를 유지해야 한다.
- Artifact는 중심 Domain Concept가 아니라 승인 결과에서 만든 파생 표현이다.
- Export는 Review Decision이나 승인 결과를 변경하지 않는다.
- Source Timeline traceability와 provenance를 유지해야 한다.
- 자동 컷 적용, 특정 NLE round trip과 실제 Rendering은 Export Pipeline 범위가 아니다.
- effective-transcript generation의 Edit Export **admission 경계**는 `§23`(`patches/PATCH-0035`)에서 확정되었다: Edit Export 경계도 legacy execution-coupled generation과 effective-transcript generation의 **두 contract generation**으로 존재하며 `§19`~`§22`는 legacy 세대의 계약으로 변경 없이 유지된다(EA-1). 현행 세대에서 Assembly는 이 세대의 **`ApprovedEditDecision`(`043 §7.5`)을 직접** 모으고 `§19`의 표현 atom 단계는 재현되지 않는다 — `§19` D-2가 요구하는 Domain Result identity·execution provenance·per-admission ordinal이 `043 §7.5` R-6·R-9에 의해 이 세대에서 충족 불가능하고, 그 atom의 목적인 승인 snapshot 소유는 R-8이 확정한 대로 `ApprovedEditDecision`이 이미 수행하기 때문이다. `§20` A-1의 anchor cardinality와 방향은 그대로이며 바뀌는 것은 member 기록의 세대뿐이다(EA-2). **`§20` A-3이 유보한 membership 정책이 이 세대에 한해 해소되었다**: 하나의 Assembly는 그 Source Timeline의 **모든 export 적격 승인 편집**을 뜻하며 subset·filter·사용자 선택·ranking은 참여하지 않는다(EA-3). Export 적격성은 **현재 유효한 판단의 승인 + 단일 actor + 연쇄 뿌리 standing `current`**의 세 조건으로 정의되어 `043 §7.6` AH-10이 열어 둔 조건을 닫는다(EA-4). 다중 actor Conflict에 대해 Export는 **어떤 중재도 하지 않으며** AH-9가 파생하지 않는 곳에서 operative judgment를 파생하지 않는다(EA-5). Assembly 구성은 승인 행위가 아니고 Review가 Human Authority의 유일한 행사 지점으로 남는다(EA-6). membership은 **파생 관측**이며 Final Selection 기록·aggregate·flag는 존재하지 않는다(EA-7). 이 세대는 `ProcessingRun`·`UnitExecution`·RUNNING state·Domain Result 소유와 chaining을 요구하지 않고 provenance는 anchor 연쇄로 확보되며 `§20` A-8의 결정성과 replay-safety는 유지된다(EA-8). `PATCH-0034` 이전에 admit되어 이력 위치가 없는 판단은 적격하지 않으나 손상이 아니며 소급 backfill은 계속 금지된다(EA-9). 저장 형태는 strictly additive하고 legacy 관계는 재사용하지 않으며 identity·atomicity의 구체 구성은 구현에 위임된다(EA-10). **Edit Pipeline에 Final Selection이라는 제품 개념은 존재하지 않는다**(EA-11). `§21`·`§22`의 이 세대 연결, Conflict가 있는 timeline의 제품 동작, overlap 판정, 빈 scope 정책은 **재범위화되지 않았고 각각 별도의 승인된 PATCH를 요구한다**.
- effective-transcript generation의 Edit Export **Artifact 경계**는 `§24`(`patches/PATCH-0036`)에서 확정되었다: `§21`의 B-1…B-15는 legacy 세대의 계약으로 유지되고, 이 세대에 대해서는 네 지점만 범위화된다(AR-1). Artifact는 **정확히 하나의 `§23` Assembly**에서 파생되어 그 Assembly의 **완전한** 승인 편집 의미를 나타내며 B-1의 cardinality와 방향은 그대로다(AR-2). 계층은 `ApprovedEditDecision`(소유) → Assembly(참조) → Artifact(제시)의 2층이고 제시되는 값은 달라지지 않는다(AR-3). Artifact가 제시 값을 복사하는 것은 이 세대의 "anchor를 통해 상속하고 복제하지 않는다" 관용구 위반이 **아니다** — 그 관용구는 canonical 기록을 규율하고 Artifact는 명시적으로 derived·non-authoritative이기 때문이다(AR-4). **execution provenance와 `DomainResult` 부재는 이 세대에서 새로 금지되는 것이 아니라 `§21`에서 상속된다**(AR-5). Source Timeline은 Assembly anchor에서, Source Media는 anchor 연쇄로 확보된다(AR-6). identity는 **Application 소유·결정적**이며 caller-owned identity는 legacy 전용이고, 그 결과 canonical 파생이 **수렴한다** — 이는 identity 계약의 귀결이지 "Artifact는 하나만 존재한다"는 제품 규칙이 아니며 B-13의 허용을 부정하지 않는다(AR-7). Artifact는 **적격성·standing·authority·Conflict를 재평가하지 않는다** — membership은 Assembly admission 시점에 확정되었고, 이후 member의 판단이 supersede되거나 chain이 standing을 잃어도 그 Assembly에서 파생된 Artifact는 **정상이며 손상이 아니다**. Assembly가 확정한 membership과 member의 승인 의미를 변경하지 않으며, `§23`이 미결로 둔 세 정책은 **여기서 되열리지 않는다**(AR-8). Artifact는 immutable·insert-only·derived·regenerable·non-authoritative이고 status·lifecycle·Profile·Configuration을 갖지 않으며 그 파생은 **승인 행위가 아니다**(AR-9). 범위는 **canonical external representation까지**이고 serializer·구체 문법·파일·output timeline·package·URL·provider·NLE는 도입되지 않으며 B-11 Representation Failure는 그대로 유지된다(AR-10). derived·regenerable하므로 durable 표현을 **요구하지 않으며**, 기록한다면 strictly additive해야 하고 authority를 얻지 않으며 legacy `edit_export_*` 관계를 재사용하지 않는다(AR-11). **`§22` 구체 serialization과 materialization의 이 세대 연결은 재범위화되지 않았고 별도의 승인된 PATCH를 요구한다.**
- effective-transcript generation의 Edit Export **serialization과 local materialization 경계**는 `§25`(`patches/PATCH-0037`)에서 확정되었다: `§22`의 C-1…C-14는 legacy 세대의 계약으로 유지되고, 이 세대에 대해서는 format identity·per-edit member 참조·anchor의 세 지점만 범위화된다(S-1). `§22`가 serialization과 local materialization을 하나의 계약으로 확정했고 C-6·C-7·C-8이 destination·collision·atomicity·result를 제품 결정으로 고정했으므로 **두 범위를 함께** 확정한다(S-1). concrete format은 **LectureOS-native JSON 하나뿐**이며 C-1의 근거가 그대로 적용되고 다중 format을 선제 계약하지 않는다(S-2). format identity는 legacy와 **구별된다** — `lectureos-lecture-edit-export-json` `v1`, `application/vnd.lectureos.lecture-edit-export+json` — payload shape가 필연적으로 다르고 두 표현은 대체 관계가 아니기 때문이다(S-3). 문서는 자기 Artifact에 대해 **완전**하며 per-edit member 참조는 `ApprovedEditDecision` identity이고, 최상위 Source Media identity는 담지 않는다 — `§24` AR-6이 그것을 anchor 연쇄로 확보했고 C-2의 완전성은 Artifact 상대적이며 그 금지는 승인 필드에 대한 것이기 때문이다(S-4). 직렬화는 **결정적**이다(고정 field 순서, canonical member 순서, UTF-8, LF, trailing newline 하나, 비-ASCII 보존, wall-clock·randomness·UUID·경로·execution/provider 식별자·mutable currentness·locale·process 의존 순서 금지)(S-5). logical payload와 physical file은 분리되고 **경로·파일명·URL·시각·filesystem metadata는 어떤 identity에도 참여하지 않는다**(S-6). materialization은 C-6·C-7·C-8을 **의미 그대로 상속**한다 — caller가 destination을 제공하고, 원자적으로 배치하며, 부분 파일을 남기지 않고, 동일 bytes는 idempotent 성공, 다른 bytes는 명시적 collision, 덮어쓰기는 명시 요청 시에만, symlink·비정규 객체는 덮어쓰지 않으며, 성공은 완전 배치 후에만 구조화된 결과로 보고된다(S-7). 실패는 **derivation·serialization·materialization의 세 계층**으로 구분되고 빈 파일·빈 문서·부분 파일·성공 상태·조용한 member 누락·fallback format으로 숨기지 않는다(S-8). execution provenance 부재는 이 세대에서 새로 금지되는 것이 아니라 `§22`에서 **상속**된다(S-9). payload와 파일은 저장되지 않으며 이 절은 `§24` Artifact의 persistence를 **우회적으로도 요구하지 않는다**(S-10). serialization과 materialization은 **승인 행위가 아니고** member 제외·추가·승인값 수정·re-approval·Final Selection·Export Approval을 하지 않으며 `§23`이 미결로 둔 세 정책을 **되열지 않는다**(S-11).
- effective-transcript generation의 Edit Export **cross-actor Conflict disclosure 경계**는 `§26`(`patches/PATCH-0038`)에서 확정되었다: `§23`이 유보한 세 제품 정책 중 **첫째만** 결정한다(CD-1). Source Timeline에 cross-actor Conflict가 있어도 export 적격 member가 하나 이상 남아 있으면 **Assembly Admission은 진행하며 Conflict는 timeline 전체의 veto가 아니다**(CD-2). Conflict Candidate가 membership에 기여하지 않는 것은 **`EA-4` (i)·(ii)의 직접적 귀결**이고 새 filter나 Export 판단이 아니며, Export는 그것을 reject·supersede·resolve·withdraw·미승인 중 어느 것으로도 해석하지 않는다(CD-3). 나머지 export 적격 `ApprovedEditDecision`은 `EA-3`대로 전부 membership을 구성하며 **EA-3의 총체성은 변하지 않는다**(CD-4). Conflict의 존재는 admission result에서 **반드시 공개된다** — 선택적 warning이 아니라 **결과 계약의 필수 구성요소**이고 생략은 계약 위반이며, membership·approved meaning·payload·persistence와 분리된다(CD-5). 최소 공개 정보는 conflicted Candidate identity, authority 이력을 가진 actor 전체, **현재 유효한 판단이 파생되지 않았다는 사실**, 그리고 **그 Candidate가 이 Assembly의 membership에 포함되지 않았다는 사실**이며, severity 척도·Conflict 분류·actor 간 순서·개수 의존 동작은 발명하지 않는다(CD-6). 결과 모델은 **disclosure-bearing success**이며 failure·partial failure·silent success·optional warning·best-effort export·degraded success 중 어느 것도 아니고 새 lifecycle state와 status 필드를 도입하지 않는다(CD-7). Export는 actor priority·recency·role/permission ranking·자동 merge·자동 selection·Conflict resolution·re-approval·rejection을 하지 않으며 **Review가 Human Authority의 유일한 행사 지점**으로 남고 `043 §15.3`은 계속 미답이며 `§7.6` AH-9는 변경되지 않는다(CD-8). `§24` Artifact·`§25` serializer·materializer는 Conflict를 재평가하지 않고 disclosure를 Artifact·문서·파일에 삽입하지 않으며, 비-억제 의무는 **admission result의 직접 consumer에만** 적용되고 전이되지 않는다(CD-9). 새 aggregate·Conflict Artifact·Conflict Report·`DomainResult`·persistent diagnostic 기록·Assembly 컬럼·Artifact field·serializer field·JSON format version·lifecycle·status 필드를 **전혀 도입하지 않고** 이미 존재하는 admission observation과 result 경계를 사용한다(CD-10). **Conflict Candidate를 제외한 뒤 적격 member가 하나도 없는 경우는 이 절이 결정하지 않으며** 다섯 후보 동작이 모두 유보되고 기존 stop이 유지된다(CD-11).

### 15.2 Working Assumption

- Export Profile은 외부 사용 목적별 표현 책임을 구분하는 개념적 문맥으로 유용하다.
- Export Scope는 전체 승인 결과와 명시적으로 선택된 일부 결과를 구분할 수 있다.
- 동일한 의미의 재생성은 byte-level 동일성보다 승인 의미와 traceability의 동등성을 우선한다.

### 15.3 Requires Validation

- Export Profile과 Export Configuration의 제품 수준 경계는 어디까지인가?
- 일부 승인 결과만 export할 때 Scope의 완전성을 사용자가 어떻게 확인해야 하는가?
- 서로 다른 Representation 사이에서 동일한 승인 의미를 검증하는 기준은 무엇인가?
- 외부 consumer가 표현할 수 없는 승인 의미를 발견했을 때 허용 가능한 처리 범위는 무엇인가?

두 번째 질문("일부 승인 결과만 export할 때 Scope의 완전성…")에 대해: `§23` EA-3은 effective-transcript generation의 membership을 **총체(all current)**로 확정했으므로 그 세대에서는 부분 Scope 자체가 발생하지 않으며 이 질문이 제기되지 않는다. 질문은 **여전히 열린 상태**이고, 이후 어떤 세대에서든 subset 계약이 도입될 때 그때의 승인된 PATCH가 답한다. 나머지 세 질문은 그대로 열려 있다.

*(후속 기록, `PATCH-0038`: 위 note는 **그대로 보존되나 그 전제가 좁아졌다.** `§26` CD-2·CD-3에 따라 cross-actor Conflict Candidate는 승인을 소유한 채 membership 밖에 남고 나머지 적격 scope는 export되므로, 그 세대에서도 **부분 scope가 도달 가능해졌다.** 다만 그 사실은 숨겨지지 않는다 — **확정된 것:** admission result에서 Conflict와 membership 제외 사실은 **항상 공개된다**(CD-5·CD-6). **여전히 Deferred:** JSON 문서 자체가 Conflict나 제한된 scope를 표시해야 하는지, 파일만 전달받은 외부 consumer가 제한을 어떻게 인지하는지, delivery나 Export Package가 disclosure를 보존해야 하는지, 그리고 UI가 어떤 문구·severity로 표시하는지. 이 질문 자체는 계속 열려 있다.)*

### 15.4 Deferred

- 구체적인 export schema와 파일 형식
- subtitle Artifact의 구체적인 형식과 문법
- 외부 NLE별 통합 방식
- 자동 컷 적용과 편집 명령 생성
- 외부 편집 완료본의 round trip
- Rendering과 전달 구현

이 목록은 그대로 유지된다. effective-transcript generation에 한해 `§23`(`patches/PATCH-0035`)이 확정한 것은 **Edit Export의 admission 경계**뿐이며, 구체적인 export schema·파일 형식·NLE 통합·자동 컷 적용·round trip·Rendering은 이 세대에서도 계속 deferred다. 여기에 더해 다음이 명시적으로 유보된다: `§21` Artifact와 `§22` 구체 serialization의 이 세대 연결, Conflict가 존재하는 Source Timeline에서 Export Admission의 제품 동작, overlap 판정과 결정 간 ordering semantics, 그리고 적격 member가 없는 scope의 처리 정책.

*(후속 기록, `PATCH-0036`: 위 유보 항목 중 **`§21` Artifact의 이 세대 연결**은 `§24`(AR-1…AR-11)가 확정했다. **`§22` 구체 serialization과 local materialization의 이 세대 연결은 그대로 deferred**이며, 그와 함께 구체 external representation 문법·export schema·외부 파일 형식·NLE projection·cross-representation equivalence·format-specific representability·Export Profile·Export Configuration·provider/NLE adapter·physical materialization과 그 path/filename/checksum 정책·delivery·download·upload·외부 URL·Export Package·retry와 failure lifecycle·Artifact의 replacement와 revision도 유지된다(`§21` B-15). Conflict가 존재하는 timeline의 제품 동작, overlap 판정, 적격 member 없는 scope의 처리도 그대로 유보되며 `§24` AR-8이 이를 되열지 않는다.)*

*(후속 기록, `PATCH-0038`: 위 세 항목 중 **Conflict가 존재하는 timeline의 Export Admission 동작**은 `§26`이 확정했다. **overlap 판정**과 **적격 member 없는 scope의 처리**는 그대로 유보된다. 여기에 더해 `043 §15.3`의 다중 actor 권위 해석, `§15.4`의 withdrawal·revocation, 그리고 **cross-actor Conflict 자체의 해소**는 이 절도 `§26`도 확정하지 않으며 각각 별도의 승인된 결정을 요구한다.)*

*(후속 기록, `PATCH-0037`: 남아 있던 **`§22` 구체 serialization과 local materialization의 이 세대 연결**은 `§25`(S-1…S-11)가 확정했다. 이로써 이 세대의 Edit Export 분기는 Review에서 로컬 파일까지 계약 수준에서 완결된다. `§21` B-15와 `§22` C-14의 나머지 항목은 그대로 유지된다: 다른 concrete format, 다중 format, serializer registry, **두 세대 문서 간 cross-format equivalence**, Export Profile·Export Configuration, provider·NLE adapter, 실행 가능한 편집 명령, output-timeline transformation, rendering, remote upload·download·외부 URL·object storage·delivery lifecycle, Export Package, retry·failure lifecycle, publication authority, payload나 파일의 replacement·revision, 파생 결과의 DB 저장, checksum 정책. `§23`이 미결로 둔 세 정책도 그대로이며, **직렬화 문서가 Source Media identity를 담아야 하는지**가 여기에 더해진다.)*

## 16. Non-Goals

이 문서는 다음을 정의하지 않는다.

- 특정 export format과 파일 문법
- 외부 NLE 명령 또는 프로젝트 구조
- Artifact 전달(Delivery)과 외부 배포 방식 (Final Subtitle SRT Artifact의 Physical Materialization은 §17에서 정의한다)
- 실행, 재시도 또는 배포 방식
- Rendering 구현
- 자동 승인 또는 자동 편집
- 외부 시스템의 정책과 호환성 보장
- Source Media, Transcript, Subtitle, Analysis 또는 Review 내부 처리

## 17. Physical Materialization

이 절은 `PATCH-0007`로 승인된 Physical Materialization의 규범적 제품 계약이다. §15.4와 §16이 이전에 유보했던 Artifact 저장(storage) 경계 중 **Final Subtitle SRT Artifact**의 물리 실현(materialization)을 여기서 확정한다. 이 절은 제품 정책만 정의하며 schema, API, record 구조 또는 구현을 정의하지 않는다.

### 17.1 책임과 경계

Physical Materialization은 하나의 canonical SRT Artifact를 물리 파일로 실현하는 단계다. lifecycle 위치는 다음과 같다.

```text
SubtitleSrtArtifact
    → Physical Materialization
    → Materialization Record
    → Physical File
    → Delivery
```

Physical Materialization은 admission, Storage Location 정책, filename 정책, collision 정책, Materialization State, provenance와 recovery를 소유한다. 다음은 소유하지 않는다: Subtitle Assembly, Artifact Generation, Delivery, download, upload, signed URL, cloud/object storage, HTTP, UI. Artifact를 재직렬화하거나 재순서화하거나 timing을 바꾸지 않으며 eligibility를 다시 판단하지 않는다.

### 17.2 Artifact / Materialization Record / Physical File 분리

세 계층은 서로 다른 권위를 가진다.

- **SubtitleSrtArtifact** — 승인된 SRT의 canonical source of truth. identity와 payload는 파일의 존재·위치·실현 횟수에 의존하지 않는다.
- **Materialization Record** — 하나의 실현 행위와 그 결과를 설명하는 canonical record. 고유한 Materialization Identity를 가지며 물리 파일 존재와 독립적으로 지속된다.
- **Physical File** — 파생된 외부 상태. 유실·이동·부재할 수 있으며 결코 identity가 아니다.

Artifact identity는 어떤 물리 표현과도 독립적이다. 파일이 존재한다는 사실이 canonical 완료를 뜻하지 않고, 파일이 사라졌다는 사실이 Artifact 손실을 뜻하지 않는다.

### 17.3 Canonical Concepts

- **Materialization Request** — 하나의 SubtitleSrtArtifact를 Storage Location에 실현하라는 승인된 지시. Materialization Identity를 가진다. admission일 뿐이며 Artifact를 재생성·변경하지 않는다.
- **Materialization Identity** — 하나의 실현 행위의 canonical identity로 Artifact Identity와 구분된다. path, filename, byte 내용, digest에서 파생하지 않는다.
- **Materialization Record** — 실현 행위의 lifecycle 상태·결과·provenance를 담는 canonical record. 단일 record인지 복수 record인지는 이 계약이 정하지 않는 구현 문제다.
- **Storage Authority** — 실현이 허용되는 위치 경계를 정하는 권위. Composition Root가 공급하는 하나의 approved Storage Root(운영 구성)이며 Domain 사실이 아니고 canonical identity로 저장하지 않는다.
- **Storage Location** — approved Storage Root 하위의 Application 소유 상대 위치(파일명 포함)이며 Application 정책이 결정한다. 어디에 파일을 두었는지 설명하는 operational provenance일 뿐 identity가 아니다.
- **Materialization Provenance** — Materialization Record → SubtitleSrtArtifact → SubtitleApprovedDocument → … → Source Timeline로 이어지는 추적 관계와 실행 문맥.
- **Materialization State** — 실현 행위의 canonical lifecycle: **PENDING**(admit되어 실현 중, 아직 확정되지 않음), **MATERIALIZED**(실현이 durable하게 확정됨), **FAILED**(실현을 완료할 수 없음). PENDING은 recovery 시 결정적으로 reconcile된다.
- **Materialization Failure** — 실현을 완료할 수 없을 때의 명시적 canonical 결과(FAILED). 정상으로 숨기지 않으며 Artifact나 provenance를 변경하지 않는다.
- **Materialized File** — 파생된 외부 물리 객체. 부재·접근불가일 수 있으며 identity가 아니다.

### 17.4 Lifecycle

```text
PENDING → MATERIALIZED
        ↘ FAILED
```

Blueprint은 lifecycle 상태, 상태 의미, 관찰 가능한 동작과 recovery 기대를 정의한다. record가 하나의 진화하는 record로 실현되는지 복수 record로 실현되는지는 정의하지 않는다.

### 17.5 Admission

Physical Materialization은 **정확히 하나의 canonical SubtitleSrtArtifact**와 그것을 참조하는 **하나의 Materialization Request**만 admit한다. payload는 durable Artifact Record에서 읽으며 SRT를 재생성하지 않고 eligibility를 다시 판단하지 않는다. 존재하지 않는 Artifact나 canonical Artifact를 참조하지 않는 Request는 부작용 없이 거부한다.

### 17.6 Storage Authority

approved Storage Root는 **Composition Root가 운영 구성으로 공급**하며 Application이 materialization 정책과 lifecycle을 소유한다. caller는 임의 위치나 절대 경로를 선택할 수 없고 current working directory를 암묵적으로 사용하지 않는다. approved root 하위의 상대 위치는 operational provenance로 저장할 수 있으나 **절대 경로는 canonical이 아니다**. root 변경이나 파일 이동은 어떤 identity도 바꾸지 않는다.

### 17.7 Materialization Identity

**Artifact Identity ≠ Materialization Identity.** 실현 행위는 caller가 공급한 고유 Materialization Identity를 가지며 path·filename·byte·digest에서 파생하지 않는다. 하나의 Artifact는 여러 번(서로 다른 run·위치, 또는 파일 유실 이후) 실현될 수 있고, 각 실현은 고유 identity를 가진 별개의 Materialization Record이며 이전 record는 history로 보존된다. 재실현은 이전 materialization을 참조할 수 있다. record가 단일인지 복수인지는 구현이 정한다. replay는 Materialization Record와 상태를 결정적으로 재구성하며 물리 파일은 그에 맞춰 reconcile된다.

### 17.8 Storage Location과 Filename 정책

Storage Location은 approved Storage Root 하위의 Application 소유 상대 위치로 Application 정책이 결정하며 주어진 정책에서 결정적이다. operational provenance로 기록되며 **identity가 아니다**: 경로를 identity로 파싱하지 않고 경로 변경이 identity를 바꾸지 않는다. **path-as-identity는 금지된다.** Blueprint은 위치를 Artifact나 Materialization identity에서 파생하도록 요구하지 않으며, 구현은 모든 위치가 결정적이고 approved root 하위에 포함되며 identity로 취급되지 않는 한 저장 계층 구조를 자유롭게 조직할 수 있다. filename 생성은 Application 정책이 소유하고 결정적이며 사용자 제어 대상이 아니다. canonical format 확장자는 SRT format 계약이 소유하는 `.srt`다. 사람이 읽기 위한 presentation filename은 별도의 non-canonical Delivery 관심사이며 이 절의 범위 밖이다.

### 17.9 Collision 정책

| 상황 | canonical 동작 |
| --- | --- |
| 파일 없음 | 기록 후 **MATERIALIZED** |
| 동일 byte 파일 존재 | 재기록 없이 **MATERIALIZED**(idempotent 성공) |
| 다른 byte 파일 존재 | **Materialization Failure**, 절대 덮어쓰지 않음 |
| 동일 request identity의 terminal record 존재 | 재실행하지 않고 기존 record 반환 |
| 동일 Materialization Identity의 중복 Request | identity collision, idempotent, 두 번째 행위 생성 안 함 |
| 다른 Artifact의 파일 또는 foreign 파일 | foreign으로 간주, 절대 덮어쓰지 않음 |

admit한 Artifact와 byte가 일치하지 않는 내용을 조용히 대체하지 않는다.

### 17.10 Missing-File 의미

Artifact가 있고 Materialization Record가 있으며 이후 파일이 사라지면 **Artifact Record와 Materialization Record는 canonical하게 유효한 채로 남는다**. 파일 availability만 잃으며 이는 record 삭제나 provenance 손실이 아니다. Artifact는 무효화되지 않고 rematerialization이 허용된다. missing file은 Artifact나 Decision·provenance history의 삭제·변경을 유발하지 않는다.

### 17.11 Rematerialization

payload가 고정·결정적이므로 rematerialization은 byte-repeatable하다. 각 실현은 새 Materialization Identity를 가진 **새 Materialization Record**이며 이전 materialization을 선택적으로 참조하고 이전 record는 history로 보존된다. 이전 record의 identity를 재사용·덮어쓰지 않는다. 동일 Artifact + 동일 Materialization Identity + 동일 위치는 기존 record를 반환하는 반복 가능한 no-op다.

### 17.12 Database ↔ Filesystem Consistency

SQLite와 filesystem 사이의 cross-resource atomicity는 달성할 수 없으므로 이 계약은 atomic이 아니라 **record-first, crash-consistent, reconcilable** 모델을 정의한다.

고려한 대안: (a) file-first — crash 시 record 없는 orphan 파일을 남겨 거부한다. (b) 단일 atomic DB+FS — 물리적으로 불가능하여 거부한다. (c) **record-first** — 파일 기록 전에 canonical materialization을 PENDING 상태로 확정하고 파일을 canonical record에 맞춰 reconcile한다. **채택.**

채택 모델(lifecycle 기반):

1. 파일 기록 **이전에** 실현 행위를 (이 Artifact·Materialization Identity·선언된 Storage Location으로) **PENDING** 상태로 durable하게 확정한다.
2. approved root 내 임시 파일에 기록 후 flush·fsync하고 atomic move/link로 선언된 위치에 배치한다.
3. terminal 상태 **MATERIALIZED**(실현 byte 길이 포함) 또는 **FAILED**(명시적 사유)를 durable하게 기록한다.

Blueprint은 lifecycle과 그 의미를 확정한다. 그 lifecycle을 단일 record로 실현할지 복수 record로 실현할지는 구현 문제다.

실패 순서별 결정적 의미:

- PENDING 확정, FS 기록 실패 → atomic replacement로 부분 파일이 노출되지 않음(임시 파일 폐기); 행위는 FAILED로 resolve되거나 reconcile 가능한 PENDING으로 남는다. Artifact 불변.
- FS 기록 성공, terminal 상태 durable 이전 → PENDING 행위와 결정적 위치로 recovery 시 reconcile: 파일 byte가 Artifact payload와 일치하면 MATERIALIZED로 완료(idempotent), 다르면 FAILED로 하고 덮어쓰지 않는다.
- 기록 도중 crash → approved root 임시 영역의 orphan 임시 파일을 결정적으로 정리; PENDING 행위가 reconcile을 유도; 거짓 성공을 기록하지 않는다.
- orphan 파일(파일 있으나 행위 없음) → tracked 실현에서는 PENDING을 기록 이전에 확정하므로 발생하지 않는다; PENDING/terminal 행위가 없는 위치의 파일은 foreign으로 간주하여 덮어쓰지 않는다.
- 행위 없음 → reconcile 대상 없음; Artifact는 새 행위로 실현 가능.
- missing file(MATERIALIZED, 파일 사라짐) → availability 손실; 새 행위로 rematerialize.

payload는 Artifact가 고정하고 위치는 Application 정책으로 결정적이며 lifecycle(PENDING → MATERIALIZED | FAILED)이 결정적이다. 유일한 비결정 요소인 물리 파일 존재 여부는 availability로 명시 모델링되어 reconcile되며 canonical 진실로 취급하지 않는다. **cross-resource atomicity는 주장하지 않는다.**

### 17.13 Provider Boundary

Application은 materialization 정책·lifecycle(admission, Storage Location 정책, filename 정책, collision 정책, Materialization State, provenance, recovery)을 소유한다. Infrastructure는 byte 기록 메커니즘(임시 파일, fsync, atomic move/link, path 안전성)을 Application이 정의한 경계 뒤에서 소유한다. approved Storage Root는 Composition Root 운영 구성이다. 어떤 provider·infrastructure도 Artifact identity, Materialization identity, lifecycle authority, filename 정책, eligibility를 소유하지 않는다. cloud/object storage는 도입하지 않으며 `020_STORAGE_MODEL.md §16.4`의 External Object Storage Boundary는 별도 계약으로 유보한다.

### 17.14 Security

approved-root containment(모든 실현은 approved Storage Root 하위로 resolve, 이탈 거부), path-traversal 방지, symlink-escape 방지, approved root 내 안전한 임시 파일, 우발적 덮어쓰기 금지(다른 byte → 실패), exact byte 보존(실현 파일 byte == Artifact payload의 UTF-8 byte), atomic replacement, payload의 실행 해석 금지, locale 의존 경로 동작 금지를 요구하고 보존한다. 기존 hardened writer의 보장은 재사용하며 약화하지 않는다.

### 17.15 Recovery

재시작 시 모든 materialization 행위와 lifecycle 상태를 재구성한다. PENDING 행위는 결정적으로 reconcile한다(선언 위치의 byte를 Artifact payload와 대조하여 일치 시 MATERIALIZED, 다르거나 기록 불가 시 FAILED). approved root 내 orphan 임시 파일을 정리한다. 실패 후 retry는 새 materialization 행위를 기록한다. deterministic replay는 Materialization Record와 상태를 재구성하며 물리 파일은 reconcile되는 부작용일 뿐 canonical 진실로 replay되지 않는다. recovery는 다른 byte 파일을 덮어쓰지 않고 Artifact나 provenance를 삭제하지 않는다.

### 17.16 Export Boundary와 Invariants

- Artifact Generation은 durable SubtitleSrtArtifact에서 끝난다. Physical Materialization은 payload를 그대로 소비한다.
- Physical Materialization은 하나의 Artifact를 admit하여 Materialization Record와 (성공 시) Storage Location의 실현 파일에서 끝난다.
- Delivery(download, upload, transfer, signed URL, HTTP, content-disposition, presentation filename, UI)는 이 절의 범위 밖이며, **v1에서는 LectureOS 소유 능력으로 구현하지 않는다**(§18, `patches/PATCH-0008`).
- Artifact identity는 어떤 물리 파일과도 영구히 독립적이다.
- 파일 경로·URL·object key는 Artifact 또는 Materialization identity가 될 수 없다.
- Materialization Failure는 정상 결과로 숨기지 않는다.
- 물리 파일 손실이 Human Decision, provenance 또는 Source Timeline traceability의 손실을 뜻하지 않는다.

## 18. Delivery — Deferred for v1

이 절은 `PATCH-0008`로 승인된 Product Owner 결정을 기록한다. **v1에서 Physical Materialization(§17)이 LectureOS가 소유하는 Export Pipeline의 마지막 단계다.** MATERIALIZED Materialization Record와 그 물리 파일이 최종 내부 export 결과이며, 그 이후의 "Delivery"는 **외부 consumer의 사용** 또는 **향후 별도로 승인되는 능력**만을 뜻한다(`044 §12.5`).

v1에서 LectureOS는 다음을 소유하지 않는다: transport, download, upload, transfer, URL 또는 signed URL 생성, content distribution, recipient 관리, presentation filename 정책, delivery identity, delivery 지속성(persistence), delivery lifecycle. `031_ARCHITECTURE.md §4.10`의 Export Coordinator는 외부 전달 경계의 개념적 조정만을 뜻하며, 위 항목을 소유하는 durable Delivery 도메인·Record·lifecycle·transport provider·network endpoint를 함의하지 않는다.

확정 사항:

- 외부 consumer는 canonical Artifact와 Materialization 결과를 **read-only**로 사용할 수 있으나, 그 처리 결과는 LectureOS canonical authority가 되지 않는다(`044 §11.5`, `§12.5`; `020_STORAGE_MODEL.md §11.2`).
- Presentation filename은 non-canonical이며 계속 deferred다(`§17.8`). URL은 canonical이 아니며 정의하지 않는다. delivery identity와 delivery lifecycle은 존재하지 않는다.
- Artifact 또는 Materialization Record에 delivery 상태를 추가하지 않는다.
- missing-file reconciliation과 rematerialization은 Physical Materialization(§17.10/§17.15)의 배타적 책임으로 남는다.
- Delivery는 구현 세부로 몰래 도입되지 않는다.

향후 LectureOS 소유의 Delivery 능력은 새로운 architecture-first 조사, 명시적 Product Owner 승인, 별도 Blueprint PATCH, 새로 경계 지어진 구현 milestone을 통해서만 도입된다.

## 19. Edit-Pipeline Export Application Foundation — Approved Edit Decision Export Representation (First Slice)

이 절은 `PATCH-0015`로 승인된 Product Owner 결정(D-1…D-15)을 기록한다. **첫 Edit-Pipeline Export milestone**은 `043_REVIEW_PIPELINE.md §7.4`에서 확정된 durable `ApprovedEditDecision`을 소비하여 **하나의 durable canonical Edit-Pipeline Export Representation 기록**을 만드는 것이다. §17(Physical Materialization)은 **Final Subtitle SRT Artifact 전용**으로 유지되며 이 절에 의해 넓혀지거나 재해석되지 않는다. 완료된 042 §9.1/§9.2와 043 §7.4 계약은 변경되지 않는다. 이 절은 제품·Application 계약만 정의하며 schema, API, record 컬럼, serialization 문법, 파일 형식, Artifact 저장, materialization 또는 구현을 정의하지 않는다.

**Anchor and Cardinality (Confirmed, D-1):** 모든 `ApprovedEditExportRepresentation`은 **정확히 하나의 durable `ApprovedEditDecision`**에 anchor된다. caller는 admission마다 하나의 명시적 Approved Edit Decision identity를 제출한다. 이 first slice는 Export Scope aggregate, 다중 결정 request, 결정 간 ordering, all-current selection, current-selection query, grouped export plan을 도입하지 않는다. 향후 grouping은 이 single-decision 계약을 바꾸지 않고 additively 추가될 수 있다.

**Canonical Record (Confirmed, D-2):** `ApprovedEditExportRepresentation`은 **durable canonical domain record**이며 **immutable**, **insert-only**, **identity-owning**(Application 소유 identity), **provenance-bearing**, **replay-safe**한 독립 식별 기록이다. 최소 개념 범주: 자신의 identity, 자신의 Domain Result identity, 정확히 하나의 원본 `ApprovedEditDecision` 참조, 직접 `EditReviewDecision` 참조, 직접 `EditCandidate` 참조, Source Media identity, Source Timeline identity, execution provenance, 결정적 per-admission sequence(ordinal), 그리고 소유한 exported-meaning snapshot. 구현 필드·컬럼 이름은 규정하지 않는다.

**Owned Exported-Meaning Snapshot (Confirmed, D-3):** 이 표현은 승인된 의미의 완전한 snapshot을 **소유**한다: 승인된 Source Timeline Time Range, 승인된 Candidate Type 또는 label, 승인된 rationale, 승인 decision kind(`accept` 또는 `modify`), human actor reference. lineage를 위해 `ApprovedEditDecision`·`EditReviewDecision`·`EditCandidate`를 **참조**한다. Analysis Finding·Eligible Analysis Input·transcript·Source Media·Source Timeline의 전체 내용을 복제하지 않으며, 이전 lineage는 참조로 도달 가능하다.

**Authority Boundary (Confirmed, D-4):** `ApprovedEditDecision`은 human-approved 편집 의도의 **유일한 canonical authority**로 남는다. `ApprovedEditExportRepresentation`은 이미 승인된 그 의미의 **export 표현에 대해서만** authoritative하다. 이 표현은 승인 값을 충실히 복사하고, 새 사람의 결정을 만들지 않으며, Approved Edit Decision을 변경·대체하지 않고, Candidate 의도를 재해석하지 않는다. 승인 편집 의도에 대한 경쟁 authority는 존재하지 않는다.

**Representation Semantics (Confirmed, D-5):** first-slice 표현은 **structured·canonical·format-neutral·provider-independent·NLE-independent·non-executable**이다. delete/cut/keep 명령, edit operation, timeline transformation 명령, output-timeline 좌표, NLE instruction, rendering instruction, serialized 파일 payload를 포함하지 않는다. Candidate Type 또는 label은 descriptive로 유지되며 용어를 이유로 실행 가능한 operation으로 취급되지 않는다.

**Accept and Modify Preservation (Confirmed, D-6):** 이 표현은 원본 Candidate 제안이 아니라 최종 승인 snapshot을 export한다. Accept일 때 export snapshot은 수용된 승인 값과 같다. Modify일 때 export snapshot은 오직 `ApprovedEditDecision`에서 오며, 원본 Candidate 값은 lineage로만 남고, patch·delta 재구성이나 원본 Candidate와의 비교가 필요하지 않다. 승인 decision kind는 `accept` 또는 `modify`로 계속 추적 가능해야 한다.

**Reject Exclusion (Confirmed, D-7):** 오직 `ApprovedEditDecision` 기록만 유효한 입력이다. Reject는 `ApprovedEditDecision`을 만들지 않으므로 `ApprovedEditExportRepresentation`을 만들지 않는다. rejection export 기록, rejected-Candidate export 표현, negative edit instruction을 도입하지 않는다.

**Admission Boundary (Confirmed, D-8/D-9/D-10):** admission은 **Application이 소유**하고 **running unit execution**을 요구하며 deterministic·replay-safe·caller-identity-owned·interface-independent·provider-independent·atomic이다. 경계는 (1) 하나의 durable Approved Edit Decision을 read-only로 로드하고, (2) canonical lineage를 검증하고, (3) running execution을 확인하고, (4) Approved Edit Decision에서 export snapshot을 도출하고, (5) 표현을 구성하고, (6) Domain Result lineage를 구성하고, (7) 전체 admission을 atomic하게 persist한다. interface나 provider 계층은 canonical 기록을 직접 persist하지 않으며, 이 first slice에는 외부 provider가 참여하지 않는다. identity는 caller-owned이고, 동일 입력+동일 identity는 결정적이며, 이미 저장된 identity의 재사용은 canonical collision 동작으로 실패하고 중복·부분 기록을 만들지 않으며, 같은 Approved Edit Decision의 새 표현은 새 identity로 또 하나의 immutable 기록이 된다. 표현과 그 Domain Result는 하나의 transaction으로 admit되고, 어떤 collision·persistence 실패도 전체 admission을 rollback하며, orphan 표현이나 Domain Result가 남지 않는다. content 기반 dedup·update·overwrite·compensating write·mutation을 도입하지 않는다.

**DomainResult Lineage (Confirmed, D-11):** 표현의 Domain Result는 **정확히 하나의 직접 upstream**을 가진다: 원본 `ApprovedEditDecision`의 Domain Result. canonical lineage는 `ApprovedEditExportRepresentation → ApprovedEditDecision → EditReviewDecision → EditCandidate → AnalysisFinding → EligibleAnalysisInput → corrected transcript/source lineage → SourceTimeline → SourceMedia`다. 표현은 추적성을 위해 Approved Edit Decision·Edit Review Decision·Edit Candidate identity를 직접 저장하고, 기존 durable-stage 관례에 따라 Source Media identity·Source Timeline identity·execution provenance를 denormalize하며, 이전 단계 기록 전체를 복제하지 않는다.

**Status and Lifecycle (Confirmed, D-12):** 이 기록은 status 필드를 가지지 않는다. pending·generated·exported·materialized·delivered·failed·stale·current·superseded·revoked·withdrawn 등을 도입하지 않는다. 표현은 하나의 immutable 사실이며, materialization·delivery·failure·retry와 downstream lifecycle은 이후 단계에 속한다. 이 first slice에 lifecycle state machine은 없다.

**Artifact and Format Boundary (Confirmed, D-13/D-14):** `ApprovedEditExportRepresentation`은 canonical domain export-representation 기록이며 Artifact, Artifact Record, 물리 파일, materialization outcome, path, URL이 아니다. first slice는 durable structured 표현에서 끝나고 JSON·CSV·XML·EDL·FCPXML·NLE 형식·textual serialization·byte payload·MIME type·파일 확장자·checksum·filename·물리 경로·외부 URL을 만들지 않는다. Artifact 생성과 physical materialization은 별도의 이후 milestone이다. 이 first slice는 Export Profile 또는 Configuration 기록을 가지지 않으며 profile identity·persistence·representation variant·destination/serializer/NLE 설정·user-selectable configuration·implicit format marker·deferred format variant를 위한 version marker를 도입하지 않는다. canonical 표현은 하나의 고정된 format-neutral 제품 의미를 가지며, 향후 serializer는 자신의 format/version 계약을 additively 도입할 수 있다.

**Deferred (이후 milestone, D-15):** 다중 결정 Export Scope, export request aggregate, current approved-decision selection, all-current export, supersession, stale 탐지, reconciliation, overlap 처리, 결정 간 ordering, partial-scope completeness UX, cross-representation equivalence, Export Profile persistence, user-selectable/destination configuration, 구체적 export schema, 외부 파일 형식, serializer, provider adapter, NLE 연동, 실행 가능한 cut/delete/keep/edit 명령, output-timeline transformation, 외부 편집 round trip, rendering, Artifact 생성, physical file materialization, materialization path·filename·checksum 정책, delivery·download·upload·외부 URL, retry·failure lifecycle, 표현의 replacement·revision. 이들 deferred 개념을 위한 placeholder field·record·table·enum·protocol·interface·abstraction은 도입하지 않는다.

**Canonical Invariants (Confirmed):** (1) 하나의 표현은 정확히 하나의 Approved Edit Decision에 anchor된다. (2) Approved Edit Decision만 유효한 입력이다. (3) Reject는 표현을 만들지 않는다. (4) upstream 기록은 read-only다. (5) 표현은 durable·immutable·insert-only·identity-owning·provenance-bearing·replay-safe다. (6) 표현은 완전한 exported-meaning snapshot을 소유한다. (7) Approved Edit Decision이 승인 의도에 대해 authoritative로 남는다. (8) 표현은 export 의미에 대해서만 authoritative다. (9) 실행 가능한 편집 semantics가 없다. (10) serialized format이 없다. (11) Artifact나 물리 파일이 없다. (12) Export Profile이 없다. (13) status나 lifecycle이 없다. (14) admission은 running-execution-gated이며 Application이 소유한다. (15) identity는 caller-owned다. (16) 구성은 결정적이다. (17) persistence는 atomic·all-or-nothing이다. (18) 직접 Domain Result upstream은 Approved Edit Decision Domain Result다. (19) Source Media·Source Timeline·execution provenance는 추적 가능하게 유지된다. (20) deferred 개념은 placeholder를 도입하지 않는다.

## 20. Edit-Pipeline Export Assembly — Approved Edit Export Scope (First Slice)

이 절은 `PATCH-0016`으로 승인된 Architect Decision(A-1…A-13)을 기록한다. **첫 Edit Export Assembly milestone**은 §19에서 확정된 durable `ApprovedEditExportRepresentation`(하나의 `ApprovedEditDecision`에 대한 export 의미의 atom)을 소비하여, 하나의 Source Timeline에 속한 승인 편집 표현들을 **하나의 coherent한 canonical Export Scope**로 모으는 것이다. 이 절은 §3.7 Export Scope를 Edit Pipeline에서 canonical 단계로 승격하며, aggregation은 serialization보다 앞선다(§8: 승인 결과 → Scope → Artifact). 구조적 선례는 subtitle의 `ApprovedDocument`(승인 subtitle 단위를 하나의 format-neutral 문서로 모으는 단계)이다. 이 절은 제품·Application 계약(개념적 의미)만 정의하며 schema, storage, repository, serializer, 파일 형식, Artifact, materialization, API를 정의하지 않는다. 완료된 §19, 042 §9.1/§9.2, 043 §7.4 계약과 subtitle §17은 변경되지 않는다.

**Existence and Anchor (Confirmed, A-1):** Edit Export Assembly는 정확히 하나의 Source Timeline에 anchor된 coherent Export Scope의 **존재**를 canonical하게 확립한다. Assembly는 그 Source Timeline에 속한 `ApprovedEditExportRepresentation` 기록들을 하나의 coherent한 export 단위로 모은다. cross-timeline·cross-media 집계는 존재하지 않는다.

**Purpose (Confirmed, A-2):** 외부 편집 결과물은 본질적으로 timeline 범위의 여러 승인 편집으로 구성된다. 하나의 `ApprovedEditExportRepresentation`은 building block이며 그 자체로 외부 deliverable이 아니다. Assembly는 어떤 형식 결정보다 먼저 "함께 속한 승인 편집 집합의 coherence와 존재"를 first-class·provenance-bearing 제품 사실로 만든다. §8의 provenance 모델은 Scope를 승인 결과와 Artifact 사이에 둔다.

**Ownership Boundary (Confirmed, A-3):** Assembly는 **coherent Export Scope의 존재만** 소유한다. Assembly는 scope-selection(membership) 정책을 소유하지 않는다. 즉 하나의 Assembly가 그 timeline의 모든 현재 승인 편집을 나타내는지, 명시적으로 선택된 일부를 나타내는지는 이 절이 고정하지 않는다(§3.7의 all-or-subset 이중성; §15.3의 완전성 질문). membership 정책은 독립적이고 여전히 열린 제품 결정으로 유보된다.

**`§23`과의 관계 (Confirmed, PATCH-0035):** 위 유보는 **legacy execution-coupled generation에 대해 그대로 유효하다.** effective-transcript generation에 한해 `§23` EA-3이 그 유보를 해소한다 — 하나의 Assembly는 그 Source Timeline의 **모든 export 적격 승인 편집**을 뜻하며, `PATCH-0016`이 미결로 열거한 두 선택지("all current approved edits" 또는 "an explicit subset") 중 전자가 선택되고 후자는 채택되지 않는다. 그 세대에서 membership은 누군가가 **고르는** 것이 아니라 `§23` EA-4의 적격성 판정으로 **결정된다**. A-13이 "canonical 정책이 아니라 Goal 수준의 scope 경계"라고 한 caveat도 그 세대에 한해 해소되며, 그 밖의 A-13 deferred 항목과 A-1의 cross-timeline·cross-media 금지는 두 세대 모두에서 그대로다.

**Upstream Relationship (Confirmed, A-4):** Assembly는 `ApprovedEditExportRepresentation` 기록을 **read-only**로 소비한다. 이를 변경·대체·재해석·재도출하지 않으며 새 승인 편집 의도를 만들지 않는다. `ApprovedEditDecision`은 승인 편집 의도에 대해, `ApprovedEditExportRepresentation`은 그 export 의미에 대해 authoritative로 남는다. Assembly는 오직 coherent grouping에 대해서만 authoritative하다.

**Downstream Relationship (Confirmed, A-5):** serializer·Artifact·physical materialization·delivery·Export Package는 엄격히 downstream이며 이 절에서 정의하지 않는다. Assembly는 format-neutral하며 serialized·외부 표현을 만들지 않는다. 향후 serializer는 Assembly를 입력으로 소비하고 자신의 format/version 계약을 additively 도입하되 Assembly의 의미를 바꾸지 않는다.

**Semantics (Confirmed, A-6):** Assembly는 structured·canonical·format-neutral·provider/NLE-independent·non-executable이다. serialization·파일 형식·byte payload·delete/cut/keep/edit/transformation 명령·output-timeline 좌표·NLE/rendering 명령을 포함하지 않는다.

**Coherence (Confirmed, A-7):** coherence의 기준은 하나의 Source Timeline이다. Assembly는 그 timeline의 승인 편집 표현들로 구성되며 서로 다른 timeline이나 media를 섞지 않는다.

**Determinism and Replay (Confirmed, A-8):** Assembly의 구성은 deterministic·replay-safe이다. 동일한 입력은 동일한 Assembly를 만든다. wall-clock·random을 읽지 않으며, 보존된 입력으로부터 동일한 의미의 Assembly를 재구성할 수 있다.

**Lineage and Provenance (Confirmed, A-9):** Assembly는 provenance-bearing이다. 그 Domain Result는 구성한 `ApprovedEditExportRepresentation`들의 Domain Result를 upstream으로 가진다(multi-upstream). canonical lineage는 `Edit Export Assembly → ApprovedEditExportRepresentation(집합) → ApprovedEditDecision → EditReviewDecision → EditCandidate → AnalysisFinding → EligibleAnalysisInput → corrected transcript/source lineage → SourceTimeline → SourceMedia`다. Assembly는 기존 durable-stage 관례대로 Source Timeline·execution provenance를 denormalize하고 이전 단계 기록 전체를 복제하지 않는다.

**Relationship to ApprovedEditExportRepresentation (Confirmed, A-10):** 표현은 export 의미의 atom(하나의 `ApprovedEditDecision`당 하나)이고 Assembly는 하나의 timeline에 대한 그 atom들의 coherent 집합이다. Assembly는 표현을 **참조**하며 그들의 owned snapshot을 새 authority로 복사·재기술하지 않는다.

**Relationship to Future Artifact (Confirmed, A-11):** Assembly는 향후 serializer/Artifact가 소비할 입력이다. aggregation은 serialization보다 앞선다. Artifact·materialization은 별도의 이후 milestone이며 이 절은 그 형식·존재를 정의하지 않는다.

**Status and Lifecycle (Confirmed, A-12):** Assembly는 status 필드·lifecycle·state machine을 가지지 않는다. Export Profile 또는 Configuration 기록을 가지지 않는다.

**Deferred (이후 milestone, A-13):** membership 정책(all/selected/filtered), subset selection, partial-scope completeness UX, current approved-decision selection, supersession, stale 탐지, reconciliation, overlap 처리, 결정 간 ordering, cross-representation equivalence, Export Profile·Export Configuration, serializer, 구체적 export schema, 외부 파일 형식, provider adapter, NLE 연동, Artifact 생성, physical materialization, materialization path·filename·checksum 정책, delivery·download·upload·외부 URL, Export Package, retry·failure lifecycle, 실행 가능한 cut/delete/keep/edit 명령, output-timeline transformation, 표현이나 Assembly의 replacement·revision. 이들 deferred 개념을 위한 placeholder field·record·table·enum·protocol·interface·abstraction은 도입하지 않는다. 첫 구현 slice는 canonical 정책이 아니라 Goal 수준의 scope 경계로서 "그 timeline의 모든 현재 승인 편집" 경우만 실현할 수 있으며 user-selectable subsetting은 이후 additive 결정에 남긴다.

**Canonical Invariants (Confirmed):** (1) Assembly는 정확히 하나의 Source Timeline에 anchor된다. (2) Assembly는 `ApprovedEditExportRepresentation`을 모으며 그 기록은 read-only다. (3) Assembly는 coherent Export Scope의 존재만 소유하고 scope-selection(membership) 정책은 소유하지 않는다. (4) aggregation은 serialization보다 앞서고 Assembly는 어떤 Artifact보다 upstream이다. (5) Assembly는 format-neutral이다: serializer·파일 형식·byte·외부 표현이 없다. (6) Assembly는 non-executable이다: 편집 명령·output-timeline transformation·NLE/rendering 명령이 없다. (7) Assembly는 새 승인 편집 의도를 만들지 않고 upstream을 변경·대체·재해석하지 않는다. (8) `ApprovedEditDecision`과 `ApprovedEditExportRepresentation`은 자기 의미에 대해 authoritative로 남고 Assembly는 coherent grouping에 대해서만 authoritative하다. (9) Assembly는 durable·immutable·insert-only·identity-owning·provenance-bearing·replay-safe다. (10) 구성은 deterministic하며 동일 입력은 동일 Assembly를 만든다. (11) Assembly Domain Result의 upstream은 구성한 표현들의 Domain Result이며(multi-upstream) SourceTimeline·SourceMedia까지 lineage를 보존한다. (12) cross-timeline·cross-media 집계는 없다. (13) status·lifecycle·state machine이 없다. (14) Export Profile·Configuration이 없다. (15) membership 정책(all/selected/filtered/current-selection/supersession)은 독립적으로 유보된다. (16) Artifact·serializer·materialization·delivery·Export Package는 downstream이며 여기서 정의하지 않는다. (17) deferred 개념은 placeholder를 도입하지 않는다.

## 21. Edit-Pipeline Export Artifact — Canonical Approved Edit Decision Representation (First Slice)

이 절은 `PATCH-0017`으로 승인된 Architect Decision(B-1…B-15)을 기록한다. **첫 Edit Export Artifact milestone**은 §20에서 확정된 durable `EditExportAssembly`(하나의 Source Timeline에 대한 승인 편집 표현들의 coherent Export Scope)를 소비하여, 그 Assembly의 **완전한 승인 편집 의미를 나타내는 하나의 canonical external Representation**을 만드는 것이다. 이 절은 §3.3·§7.2의 Artifact 개념을 canonical 수준에서 실현하며, aggregation은 serialization보다 앞선다(§8). 이 Artifact는 **external representation(외부 표현) 그 자체**이고, **concrete serialization syntax(구체적 직렬화 문법)는 전적으로 유보**된다 — 이 둘의 구분이 이 절의 핵심이다. 이 절은 제품·개념적 의미만 정의하며 serializer, 구체적 format/syntax, schema, storage, persistence, API, materialization을 정의하지 않는다. 완료된 §19, §20, 042 §9.1/§9.2, 043 §7.4 계약과 subtitle §17은 변경되지 않는다.

**Existence and Anchor (Confirmed, B-1):** 하나의 Edit Export Artifact는 정확히 하나의 `EditExportAssembly`에서 파생되며 그 Assembly의 **완전한 승인 편집 의미**를 나타낸다. cross-Assembly Artifact는 존재하지 않는다.

**`§24`와의 관계 (Confirmed, PATCH-0036):** 이 절의 B-1…B-15는 **legacy execution-coupled generation의 계약으로 그대로 유효하다.** effective-transcript generation에 대해서는 `§24`(AR-1…AR-11)가 네 지점만 세대 범위로 명시한다. **(1)** B-1의 source Assembly는 그 세대에서 `§23` Assembly다 — anchor의 **cardinality와 방향은 그대로**이고 바뀌는 것은 Assembly의 세대뿐이다(AR-2). **(2)** B-12의 3층 관계(atom → grouping → presentation)는 그 세대에서 2층이다 — `§23` EA-2가 `§19` atom 단계를 재현하지 않으므로 member는 `ApprovedEditDecision`이며, **제시되는 값과 그 소유자는 달라지지 않는다**(AR-3). **(3)** B-10의 traceability 요구는 유지되고 담는 형태만 달라진다 — Source Timeline은 Assembly anchor에서 상속하고 Source Media는 anchor 연쇄로 확보한다(AR-6). **(4)** B-13의 복수 derived Artifact는 **계속 허용되나**, 그 세대의 identity는 `043 §7.5` R-10에 따라 Application 소유·결정적이므로 파생이 **수렴한다**(AR-7) — caller-owned identity는 legacy 세대에 남는다. 나머지 B-2·B-3·B-4·B-5·B-6·B-7·B-8·B-9·B-11·B-14·B-15는 두 세대에 **변경 없이 상속된다.** 특히 이 절이 execution provenance와 `DomainResult`를 요구하지 않는다는 사실은 legacy 세대에서도 그러했으므로 `§24` AR-5는 새 금지가 아니라 상속의 확인이다.

**Purpose — the External Representation Transition (Confirmed, B-2):** Artifact는 **internal canonical 기록에서 external derived representation으로의 제품 전환**을 도입하는 첫 단계다. `EditExportAssembly`는 member 표현들을 **참조**하는 internal canonical grouping 기록이다. Artifact는 그 grouping의 승인 의미를 하나의 self-contained external product로 **제시(present)**한다. 즉 Assembly는 "어떤 승인 편집들이 함께 속하는가"를 소유하고, Artifact는 "그 승인 편집 의미를 외부 consumer가 사용할 수 있는 하나의 표현으로 제시"한다. 이 제시(external representation) 자체가 Artifact 단계에서 처음 나타나는 새 제품 의미다.

**Canonical External Representation (Confirmed, B-3):** Artifact는 승인 편집 의미의 **canonical external representation**이다. Assembly의 canonical 순서로 각 member에 대해 승인 Source Timeline range, 승인 label/type, 승인 rationale, 승인 decision kind, human actor를 **제시**하며 provenance·traceability를 유지한다. 이것은 **external representation(무엇을 전달하는가)**이며, 이를 구체 문자열/바이트로 만드는 **serialization syntax(어떻게 표기하는가)**와 구별된다. LectureOS는 정확히 하나의 canonical Product representation을 소유한다.

**External Representation vs Concrete Syntax (Confirmed, B-4):** Artifact는 **무엇을 전달하는지(승인 편집 결정 의미)**를 확정하고 **어떤 구체 문법으로 표기하는지**는 확정하지 않는다. 구체적 human-readable/machine-readable 형식은 이후 serializer가 이 canonical representation을 **project**하여 additively 도입하며(§7.3, §19 D-14), canonical Artifact의 의미를 바꾸지 않는다. Artifact는 특정 format의 이름(EDL·FCPXML 등)이 아니라 승인 편집 결정의 canonical 표현이다.

**Derived and Regenerable (Confirmed, B-5):** Artifact는 승인 원본에서 파생된 **derived·regenerable** 결과다(§3.3, §13). 보존된 승인 입력으로부터 재생성될 수 있고, 그 손실은 `ApprovedEditDecision`·`ApprovedEditExportRepresentation`·`EditExportAssembly` 또는 어떤 승인 기록도 손상시키지 않는다.

**Non-authoritative (Confirmed, B-6):** Artifact는 어떤 canonical 사실에 대해서도 authoritative하지 않다. `ApprovedEditDecision`은 승인 편집 의도에, `ApprovedEditExportRepresentation`은 그 export 의미에, `EditExportAssembly`는 coherent grouping에 대해 authoritative로 남는다. Artifact는 새 승인 결정을 만들지 않고 승인 의미를 변경·재해석하지 않으며 upstream을 대체하지 않는다.

**Descriptive, Non-executable (Confirmed, B-7):** Artifact는 승인된 편집 **결정**을 서술적으로 제시하며 실행 가능한 cut/keep/delete/transform 명령, output-timeline 좌표, NLE/rendering instruction을 포함하지 않는다. 외부 NLE가 편집을 실제로 어떻게 적용할지는 Export Pipeline이 결정하지 않는다(§7.2).

**Upstream Relationship (Confirmed, B-8):** Artifact는 하나의 `EditExportAssembly`를 **read-only**로 소비하며 그것이나 그 member 표현들을 변경·재해석·재도출하지 않는다. aggregation은 serialization보다 앞서고 Artifact는 Assembly의 downstream이다.

**Downstream Relationship (Confirmed, B-9):** serializer, 구체적 external format/syntax, Export Profile, Export Configuration, physical materialization, delivery, Export Package는 엄격히 downstream이며 이 절에서 정의하지 않는다. 향후 serializer는 이 canonical Artifact를 입력으로 삼아 구체 format으로 project하되 그 canonical 의미를 바꾸지 않는다.

**Provenance and Traceability (Confirmed, B-10):** Artifact는 provenance-bearing이다. 자신을 파생시킨 `EditExportAssembly`, 그 member 표현들, 그리고 이를 통해 Source Timeline·Source Media까지 추적 가능해야 한다(§8). Artifact는 이전 단계 기록 전체를 복제하지 않으며 그 provenance를 유지한다.

**Representation Failure (Confirmed, B-11):** Representation Failure는 승인 편집 의미를 canonical Artifact representation으로 **완전하고 충실하게** 나타낼 수 없는 상태다(§11.4). 표현 과정에서 승인 의미를 조용히 버리거나 다른 의미로 바꾸지 않으며, 완전·충실한 표현이 불가능하면 무엇을 표현할 수 없었는지 밝히는 **명시적 Export Failure**로 처리하고 승인 원본은 그대로 보존한다(§9, §3.10). 구체 syntax가 특정 의미를 표기할 수 있는지의 format-specific representability는 이후 serializer 단계의 문제로 유보되며, 거기서 §11.4가 "the selected representation"에 대해 적용된다.

**Relationship to Assembly and Representation (Confirmed, B-12):** `ApprovedEditExportRepresentation`은 하나의 승인 편집의 export 의미 atom이고, `EditExportAssembly`는 하나의 timeline에 대한 그 atom들의 coherent grouping(참조)이며, `EditExportArtifact`는 그 grouping된 승인 의미의 derived external presentation이다. Artifact는 external representation 자체를 도입하며 Assembly의 재기술이 아니다. Assembly는 참조하고, Artifact는 제시한다.

**Cardinality (Confirmed, B-13):** 하나의 Artifact는 정확히 하나의 Assembly의 완전한 승인 의미를 나타낸다. 같은 Assembly에 대해 여러 derived Artifact가 존재할 수 있으나(regenerable·non-authoritative, §7.3) 각 Artifact는 그 Assembly의 완전한 의미를 담는다.

**Status and Lifecycle (Confirmed, B-14):** Artifact는 status 필드·lifecycle·state machine을 가지지 않는다. Export Profile 또는 Configuration을 가지지 않는다.

**Deferred (이후 milestone, B-15):** serializer, 구체적 external representation syntax, export schema, 외부 파일 형식, human-readable/machine-readable/NLE 구체 projection, cross-representation equivalence(둘 이상의 구체 format이 생길 때만 필요), format-specific representability, Export Profile·Export Configuration, provider·NLE adapter, physical materialization, materialization path·filename·checksum 정책, delivery·download·upload·외부 URL, Export Package, 실행 가능한 cut/delete/keep/edit 명령, output-timeline transformation, rendering, retry·failure lifecycle, Artifact의 replacement·revision. 이들 deferred 개념을 위한 placeholder는 도입하지 않는다.

**Canonical Invariants (Confirmed):** (1) 하나의 Artifact는 정확히 하나의 `EditExportAssembly`에서 파생된다. (2) upstream Assembly와 그 member 표현은 read-only다. (3) Artifact는 승인 편집 의미의 canonical external representation을 도입한다(제시). (4) external representation(무엇을)과 concrete serialization syntax(어떻게)는 구별되며 syntax는 유보된다. (5) LectureOS는 정확히 하나의 canonical Product representation을 소유하고 구체 format은 이후 serializer의 additive projection이다. (6) Artifact는 derived·regenerable이며 그 손실은 승인 원본을 손상시키지 않는다. (7) Artifact는 non-authoritative이며 승인 의미를 만들거나 변경·재해석하지 않는다. (8) Artifact는 descriptive이며 실행 가능한 편집·timeline transformation·NLE/rendering 의미가 없다. (9) Artifact는 provenance·traceability를 Assembly·member·SourceTimeline·SourceMedia까지 유지한다. (10) aggregation은 serialization보다 앞서고 Artifact는 Assembly의 downstream, 모든 serializer/format의 upstream이다. (11) Representation Failure는 완전·충실한 표현 불가를 뜻하며 조용한 손실 없이 명시적 실패로 드러난다. (12) status·lifecycle·Export Profile·Configuration이 없다. (13) 구체 format·serializer·materialization·delivery·Export Package는 downstream이며 여기서 정의하지 않는다. (14) deferred 개념은 placeholder를 도입하지 않는다.

## 22. Edit-Pipeline Export — First Concrete Serialization and Local Materialization (LectureOS Edit Export JSON v1)

이 절은 `PATCH-0018`으로 승인된 Architect/Product 결정(C-1…C-14)을 기록한다. **첫 runnable Edit Export slice**는 §21의 canonical `EditExportArtifact`를 하나의 **구체 format**으로 serialize하고, 그 결과를 하나의 **로컬 물리 파일**로 materialize하여, 사용자가 실제로 실행해 외부에서 열어볼 수 있는 첫 export 파일을 만드는 것이다. 이 절은 §19 D-14가 예고한 "future serializer가 자신의 format/version 계약을 additively 도입한다"의 첫 실현이며, §21의 Artifact 의미를 바꾸지 않고 그 위에 **projection**으로만 추가된다. serializer·materializer는 §21 Artifact의 non-authoritative projection이고 승인 원본을 변경하지 않는다. 이 절은 하나의 구체 format만 정의하며 다중 format, serializer registry, cross-format equivalence, Export Profile/Configuration, provider/NLE adapter, delivery/upload/URL, executable 편집 의미를 정의하지 않는다.

**Selected First Format (Confirmed, C-1):** 첫 구체 format은 **LectureOS-native JSON**이다. format identifier는 `lectureos-edit-export-json`, format version은 `v1`, format 식별자(media type 상당)는 `application/vnd.lectureos.edit-export+json`이다. 이는 NLE interchange format(EDL·FCPXML·AAF·OTIO 등)이 **아니다**. 근거: 현재 `EditExportArtifact`가 담는 의미는 서술적 승인 편집 결정(승인 range·label/type·rationale·decision kind·actor)이며 실행 가능한 timeline operation이 아니다. NLE format으로 project하려면 없는 timeline/executable semantics(record timecode, reel, track, frame rate 등)를 발명하거나 rationale·decision kind·actor·label 같은 비-timeline 의미를 조용히 버려야 하므로 완전·충실 표현이 불가능하다. LectureOS-native JSON은 Artifact의 모든 필드를 손실 없이·결정적으로·검사 가능하게 표현하는 최소 충실 format이다.

**Complete Faithful Field Mapping (Confirmed, C-2):** serialize된 문서는 §21 Artifact의 완전한 의미를 담는다. 최상위: format identifier, format version, artifact identity, source assembly identity, source media identity, source timeline identity, 그리고 canonical member 순서의 edit 목록. 각 edit entry: source representation identity, decision kind(`accept`|`modify`), 승인 range start, 승인 range end, 승인 Candidate Type/label, 승인 rationale, human actor. 어떤 승인 필드도 생략·절단·정규화 제거·재해석·발명하지 않는다.

**`§25`와의 관계 (Confirmed, PATCH-0037):** 이 절의 C-1…C-14는 **legacy execution-coupled generation의 계약으로 그대로 유효하며**, legacy serializer는 계속 `lectureos-edit-export-json` `v1`을 그 field 집합 그대로 만든다. effective-transcript generation에 대해서는 `§25`(S-1…S-11)가 **세 지점만** 세대 범위로 명시한다. **(1)** C-1의 format identity는 그 세대에서 재사용되지 않는다 — payload shape가 필연적으로 다르므로 하나의 identifier·version이 두 shape를 지칭할 수 없고, 두 표현은 대체 관계가 아니므로 version bump가 아니라 **별도 identifier**를 쓴다(S-3). **(2)** C-2의 field 목록 중 per-edit `source representation identity`의 자리는 그 세대에서 **`ApprovedEditDecision` identity**가 차지한다 — `§23` EA-2가 `§19` atom을 재현하지 않기 때문이다(S-4). **(3)** C-6의 anchor는 그 세대의 `§24` Artifact다. **C-2의 지배 규칙 자체는 달라지지 않는다** — "§21 Artifact의 완전한 의미를 담는다"는 **Artifact 상대적** 완전성이고 "어떤 **승인 필드**도 생략하지 않는다"는 승인 의미에 대한 것이며, 그 세대의 문서도 **자기 Artifact에 대해 완전**하다. 최상위 `source media identity`가 그 세대 문서에 없는 것은 그 세대의 Artifact가 그것을 담지 않기 때문이고(`§24` AR-6), C-2·C-3·C-4와 Canonical Invariant 어느 것도 JSON 자체에 그 field를 **필수로 요구하지 않는다**(Invariant (2)도 "완전한 **승인** 의미"라고 말한다). 나머지 C-3·C-4·C-5·C-7·C-8·C-9·C-10·C-11·C-12·C-13·C-14는 두 세대에 **변경 없이 상속된다** — 특히 C-6·C-7·C-8의 destination·collision·overwrite·atomic placement·structured result와 C-12의 무저장이 그렇다.

**Ordering (Confirmed, C-3):** edit entry의 순서는 §20/§21에서 확정된 canonical member 순서(stable identity 순서)를 그대로 보존한다. serializer는 순서를 재정렬하지 않으며 이는 저장/재현 순서이지 편집 실행·timeline·overlap 순서가 아니다.

**Deterministic Serialization (Confirmed, C-4):** 동일한 Product 의미의 Artifact는 항상 byte-동일한 직렬화를 만든다. 필드 순서는 고정되고, wall-clock·locale·randomness를 읽지 않으며, 숫자·문자열은 결정적으로 표기된다. encoding은 UTF-8, 개행은 LF(`\n`), 문서 끝에 정확히 하나의 개행을 둔다. 비-ASCII(예: 한국어) 문자는 escape 없이 그대로 보존한다.

**Format-specific Representation Failure (Confirmed, C-5):** 승인 의미를 선택된 format으로 완전·충실하게 표현할 수 없으면(예: JSON이 표현할 수 없는 non-finite 수치) serializer는 조용히 버리거나 유효하지 않은 문서를 만들지 않고 **명시적 실패**를 낸다(§11.4를 "the selected representation"에 대해 적용). 승인 원본은 그대로 보존된다.

**Local Physical Materialization (Confirmed, C-6):** materializer는 직렬화된 bytes를 caller가 지정한 로컬 destination 경로에 하나의 완전한 물리 파일로 쓴다. destination 선택 책임은 caller에게 있다. 쓰기는 temporary 파일에 완전히 기록·flush·fsync한 뒤 원자적으로 최종 경로에 배치하는 방식으로 수행하여, 실패 시 최종 경로에 부분 파일이 남지 않게 한다.

**Collision and Overwrite (Confirmed, C-7):** 최종 경로에 이미 동일 bytes의 정규 파일이 있으면 idempotent 성공으로 처리한다. 다른 bytes의 정규 파일이 있으면 기본적으로 **명시적 collision 실패**로 처리하고 덮어쓰지 않는다. 덮어쓰기는 입력 계약이 명시적으로 허용할 때만(overwrite 요청) 원자적으로 수행한다. symlink나 정규 파일이 아닌 기존 객체는 덮어쓰지 않고 실패로 처리한다. 필요한 상위 디렉터리는 계약이 허용하는 범위에서 생성할 수 있다.

**Successful Result Contract (Confirmed, C-8):** 성공 시 구조화된 결과로 최종 파일 경로, format identifier, format version, 실현된 byte 길이, encoding을 반환한다. 성공은 완전한 파일이 최종 경로에 durably 배치된 뒤에만 보고된다.

**Non-executable and Descriptive (Confirmed, C-9):** 직렬화 문서는 서술적이며 실행 가능한 cut/keep/delete/transform 명령, output-timeline 좌표, NLE/rendering instruction을 포함하지 않는다. range는 승인된 Source Timeline range이며 output-timeline 좌표가 아니다.

**Authority and Provenance (Confirmed, C-10):** serializer와 materializer는 §21 Artifact의 non-authoritative projection이다. 어떤 승인 결정도 만들거나 변경·재해석하지 않고, `ApprovedEditDecision`·`ApprovedEditExportRepresentation`·`EditExportAssembly`를 authoritative로 남긴다. 직렬화 문서는 자신이 표현한 Artifact·Assembly와 그 provenance(Source Timeline·Source Media)를 담아 추적 가능하게 한다. 어떤 실패에서도 승인 upstream 데이터는 보존된다.

**Regenerability (Confirmed, C-11):** 직렬화 결과는 파생·재생성 가능하다. 동일한 valid upstream 상태에서 다시 만들면 동일한 Product 의미와 byte-동일한 문서를 만든다. 직렬화 결과나 materialize된 파일은 authoritative canonical 기록이 아니며 그 손실은 승인 원본을 손상시키지 않는다.

**Persistence Boundary (Confirmed, C-12):** 이 slice는 파생 Artifact나 직렬화 결과를 데이터베이스에 durably 저장하지 않는다. 새 table·schema·migration을 도입하지 않으며 `SQLITE_SCHEMA_VERSION`을 바꾸지 않는다. 직렬화·materialization은 필요 시 로컬 파일시스템에만 side-effect를 가진다.

**Runnable Entry Point (Confirmed, C-13):** 이 slice는 기존 저장소 관례(application entry point)를 통해 실제 실행 가능해야 한다: 하나의 유효한 `EditExportAssembly`를 식별하고, 그 Artifact를 파생하고, 선택된 format으로 serialize하고, 로컬 파일로 materialize하고, 최종 경로와 format/version을 보고하며, 실패 시 오탐 성공이나 최종 파일을 남기지 않고 명시적 실패를 반환한다.

**Deferred (이후 milestone, C-14):** 다른 구체 format(EDL·FCPXML·AAF·OTIO·CSV 등), 다중 format, serializer registry·plugin discovery, cross-format equivalence, Export Profile·Export Configuration, provider·NLE adapter, executable cut/delete/keep/edit 명령, source media에의 편집 적용, output-timeline transformation, rendering, 원격 upload·download·URL·object storage·delivery lifecycle, retry lifecycle, 직렬화 결과나 파일의 replacement·revision·history, 파생 Artifact/직렬화 결과의 DB 저장, 일반화된 package/bundle export, checksum 정책(안전 materialization에 불필요). 이들 deferred 개념을 위한 placeholder는 도입하지 않는다.

**Canonical Invariants (Confirmed):** (1) 첫 구체 format은 `lectureos-edit-export-json` `v1`이며 NLE interchange format이 아니다. (2) 직렬화는 §21 Artifact의 완전한 승인 의미를 손실 없이 담는다. (3) edit 순서는 canonical member 순서를 보존하며 실행/timeline 순서가 아니다. (4) 직렬화는 결정적이다(UTF-8·LF·고정 필드 순서·비-ASCII 보존). (5) 표현 불가 값은 조용한 손실 없이 명시적 실패로 처리한다. (6) materialization은 원자적이며 실패 시 최종 부분 파일을 남기지 않는다. (7) 기본은 덮어쓰기 금지이고 collision은 명시적 실패이며 덮어쓰기는 명시 요청 시에만 수행한다. (8) 성공은 완전 파일이 durably 배치된 뒤에만 보고되고 최종 경로·format·version·byte 길이·encoding을 담는다. (9) 직렬화 문서는 서술적이며 실행 가능한 편집·timeline·NLE 의미가 없다. (10) serializer·materializer는 non-authoritative projection이며 승인 원본을 보존한다. (11) 결과는 파생·재생성 가능하며 동일 upstream에서 byte-동일하다. (12) 이 slice는 DB 저장·schema·migration을 도입하지 않고 `SQLITE_SCHEMA_VERSION`을 바꾸지 않는다. (13) 실제 실행 가능한 entry point가 존재하고 실패 시 명시적으로 실패한다. (14) deferred 개념은 placeholder를 도입하지 않는다.

## 23. Effective-Transcript Generation — Edit Export Admission Boundary

이 절은 `PATCH-0035`로 승인된 Architect Decision(EA-1…EA-11)을 기록한다. `043 §7.5`의 **Sections Not Re-scoped**와 `§7.6` AH-10이 "별도 결정"으로 남긴 것 — **이 세대의 `ApprovedEditDecision`을 `044` Export에 연결하는 계약** — 을 effective-transcript generation에 한해 확정한다. `§3`의 Export 개념과 `§19`·`§20`·`§21`·`§22`의 legacy 계약은 삭제·재작성·소급 해석되지 않는다. 이 절이 확정하는 것은 **Export admission 경계, 곧 무엇이 Assembly의 member가 되는가**이며 그 member로 Export가 어떤 제품 동작을 보이는가는 확정하지 않는다. 결정 번호에 `EA-` 접두사를 쓰는 것은 Export Admission을 다루기 때문이며 계약상 의미는 없다.

**Scope and Instrument (Confirmed, EA-1):** 이 절은 **effective-transcript generation에만** 적용된다. `§19`·`§20`·`§21`·`§22`는 legacy execution-coupled generation의 계약으로 자기 세대에서 그대로 유효하며 그 기록은 유효한 역사로 보존된다. 두 세대는 영구히 구분 가능하고, 한 세대의 기록을 다른 세대의 Export 입력으로 교차 사용하지 않는다. **하나의 contract generation 안에는 정확히 하나의 canonical Edit Export admission 경계가 존재한다.**

**Export Admission Anchor (Confirmed, EA-2):** 이 세대에서 Edit Export Assembly는 이 세대의 **`ApprovedEditDecision`(`043 §7.5`)을 직접** 모은다. `§19`의 `ApprovedEditExportRepresentation` 단계는 이 세대에서 **재현되지 않는다.** 이유는 두 가지다. 첫째, `§19` D-2의 최소 요구(자신의 Domain Result identity 소유, execution provenance, per-admission ordinal)와 D-8/D-9/D-10의 running unit execution·caller-owned identity는 `043 §7.5` R-6이 이 세대에서 **충족 불가능**하다고(이 세대의 Candidate는 Domain Result를 만들지 않으므로 소유할 것도 참조할 것도 없다), R-9가 **제품 의미가 없다**고 확정한 바로 그 항목들이다. 이를 문자 그대로 적용하면 `040 §18` H-10과 `041 §15` E6이 금지한 가짜 실행 기록과 합성 Domain Result를 만들어야 한다. 둘째, 그 atom의 목적인 승인 snapshot 소유(D-3)는 R-8이 확정한 대로 `ApprovedEditDecision`이 **이미** 수행하며, 이 세대는 `042 §8.2` D-2·`§9.3` C-8·`§7.5` R-7이 확립한 "anchor를 통해 상속하고 복제하지 않는다" 관용구를 따른다. `§20` A-1의 **cardinality와 방향은 그대로다** — Assembly는 정확히 하나의 Source Timeline에 anchor하고 그 timeline에 속한 승인 편집을 모으며 upstream은 **immutable·read-only**로 소비된다. 바뀌는 것은 member 자리를 차지하는 기록이 **어느 세대의 것인가**뿐이며, 이는 `§7.5` R-2가 anchor의 세대만 바꾼 것과 같은 관용구다. 이 절은 **새 aggregate를 만들지 않는다**: Assembly는 `§3.7`·`§20`이 이미 확립한 개념이며 여기서는 그 세대 범위만 정한다.

**Membership Is All Current Approved Edits of One Source Timeline (Confirmed, EA-3):** `§20` A-3의 유보가 이 세대에 대해 **해소된다.** 하나의 Assembly는 그 하나의 Source Timeline에 속한 **모든 export 적격 승인 편집(EA-4)**을 뜻하며 그 밖의 것을 뜻하지 않는다. `PATCH-0016`이 미결로 열거한 두 선택지 중 **"all current approved edits"가 선택되고 "an explicit subset"은 채택되지 않는다.** 따라서 membership은 누군가가 **고르는** 것이 아니라 적격성 판정으로 **결정된다**. subset·filter·사용자 선택·ranking·priority는 참여하지 않는다. `§20` A-1의 cross-timeline·cross-media 집계 금지는 그대로다.

**Export Eligibility (Confirmed, EA-4):** `043 §7.6` AH-10이 열어 둔 조건을 닫는다. 이 세대의 하나의 `ApprovedEditDecision`은 다음 **세 조건을 모두** 만족할 때 export 적격이다.

- **(i) 현재 유효한 판단.** 그 Candidate의 **현재 유효한 판단**(`§7.6` AH-8에 따라 persist된 위치에서만 파생되며 저장되지 않고 latest-row heuristic이 아니다)이 소유한 승인이다. supersede된 판단의 승인은 **적격하지 않으며**, 그것은 유효한 immutable history로 남는다(`§7.5` R-5, `§7.6` AH-8).
- **(ii) 단일 actor.** 그 Candidate에 대해 이력을 가진 actor가 **정확히 하나**여서 현재 유효한 판단이 파생된다(`§7.6` AH-9). EA-5를 함께 본다.
- **(iii) current standing.** anchor 연쇄 뿌리의 파생 admission standing(`§7.5` R-3)이 **`current`**다. `superseded_by_authority_change`와 `current_authority_ineligible`은 export 부적격 사유다. released 3값 vocabulary를 **확장하지 않으며** 네 번째 값을 도입하지 않는다. 없거나 canonical 형식에 맞지 않는 참조는 standing 평가 이전에 거부된다. 부적격 연쇄의 **관측은 계속 허용되고 어떤 기록도 변경하지 않으며**(`§7.6` AH-10), superseded 연쇄는 결코 저장소 손상이 아니다(`040 §18` H-12 관용구).

`reject`는 `ApprovedEditDecision`을 만들지 않으므로 구조적으로 이 판정의 대상이 아니다 — `§19` D-7의 규칙이 별도 filter 없이 그대로 보존된다.

**Multi-actor Conflict Is Never Arbitrated (Confirmed, EA-5):** 하나의 Candidate가 둘 이상 actor의 authority 이력을 가지면 `§7.6` AH-9는 현재 유효한 판단을 **파생하지 않는다.** Export는 그것을 **해소하지 않는다**: actor 사이의 우선순위, 최신성(recency), 역할·권한 서열, 자동 merge, 자동 selection은 **금지되며**, AH-9가 파생하지 않는 곳에서 Export가 operative judgment를 파생할 수 없다. membership에는 추가 규칙이 필요하지 않다 — 그런 Candidate는 EA-4 (i)·(ii)를 만족하지 못해 member를 기여하지 않는다. `§15.3`(`043`)의 다중 사용자 질문에는 **답하지 않으며** 그 deferred 상태는 유지된다. 해소는 사람이 다시 판단하는 Review에 속한다. **이 절이 결정하지 않는 것:** Conflict가 존재하는 Source Timeline에서 Export Admission의 제품 동작 — Assembly를 admit하는지, 나머지 적격 편집만 admit하는지, 그 timeline의 admission을 거부하는지, 그리고 Conflict를 export 시점에 어떻게 드러내는지. `§3.12`(`043`)는 Review 안에서 Conflict 자체를 규율하며, export 시점의 처리는 아래 Deferred에 속한다. *(후속 기록, `PATCH-0038`: 위에 열거된 것 중 **Conflict가 존재하는 Source Timeline에서 Export Admission의 제품 동작과 그 공개 방식**은 `§26`(CD-1…CD-11)이 확정했다 — admission은 진행하고, Conflict Candidate는 EA-4의 귀결로 membership에 기여하지 않으며, 나머지 적격 편집은 EA-3대로 전부 포함되고, Conflict는 admission result의 **필수 disclosure**로 공개된다. **overlap 판정과 적격 member 없는 scope의 처리는 그대로 미결이다.** EA-5가 확정한 비중재 원칙은 변경되지 않으며 `§26`은 그것을 소비할 뿐이다.)*

**No New Authority (Confirmed, EA-6):** Assembly를 구성하는 것은 **승인 행위가 아니다.** 사람의 결정을 만들지 않고, 재승인하지 않으며, 어떤 Review 기록도 변경·거부·filter·재해석·supersede하지 않는다(`§2.8`, `§13`; `043 §13`). **Review는 Human Authority가 행사되는 유일한 단계로 남는다.** 사람이 export를 촉발할 수 있으나 촉발은 권위를 행사하지 않는다 — admit되는 의미는 전적으로 Review에 이미 기록된 결정으로 결정된다. `ApprovedEditDecision`은 승인 편집 의도에 대한 **유일한 canonical authority**로 남는다(`043 §7.4` Modify Ownership, `§7.5` R-8, `§19` D-4).

**Membership Is Derived, Never Selected or Stored as Selection (Confirmed, EA-7):** 이 세대에는 **Final Selection 기록·aggregate·단계·권위가 존재하지 않는다.** 적격성은 persist된 행에 대한 **파생 관측**이며 `§7.5` R-4와 `§7.6` AH-8의 관용구를 따른다: mutable current flag·stale flag·selection flag·lifecycle state·status 필드를 어디에도 도입하지 않으며 도입하는 방향을 금지한다. Assembly가 자신이 모은 승인 편집을 durable하게 기록하는 것은 **그 Assembly의 membership provenance**이며, 저장된 selection도 아니고 무엇이 승인되었는지에 대한 authority도 아니다.

**Execution-Free Deterministic Provenance (Confirmed, EA-8):** 이 세대의 Edit Export admission은 `ProcessingRun`, `ProcessingUnit`, `UnitExecution`, RUNNING state, execution lifecycle, Domain Result identity 소유, Domain Result chaining을 **요구하지 않는다.** `§19` D-2·D-8·D-11과 `§20` A-9의 multi-upstream Domain Result lineage는 **legacy 세대의 요구**이며 그 세대 범위로 명시된다 — `§7.5` R-6이 기록한 대로 이 세대에는 소유하거나 참조할 Domain Result가 존재하지 않기 때문이다. 가짜 실행 기록·synthetic Processing Run·합성 RUNNING state·합성 Domain Result를 provenance로 사용하는 것은 **금지된다**(`040 §18` H-10, `041 §15` E6). `§20` A-8의 **결정성과 replay-safety는 그대로 유지된다**: 동일한 persist된 상태는 동일한 Assembly를 만들며 wall-clock과 무작위를 읽지 않는다. Source Media·Source Timeline provenance는 **사라지지 않고** anchor 연쇄 `ApprovedEditDecision → ReviewDecision → Edit Candidate(042 §9.3) → Analysis Finding(042 §8.2) → Lecture Analysis Input Admission → current applicable Corrected Revision → parent Raw Transcript → Source Timeline → Source Media`를 통해 확보된다(`§7.5` R-7). 조회 편의를 위해 일부를 denormalize할지는 구현 선택이며, 어떤 형태를 택하든 `§2.9` Source Timeline traceability는 유지되어야 한다.

**Judgments Without a History Position (Confirmed, EA-9):** `PATCH-0034` 이전에 admit된 `ReviewDecision`은 authority 위치를 갖지 않을 수 있으며 그것은 **손상이 아니다**(`§7.6` AH-12). 그 경우 현재 유효한 판단이 파생되지 않으므로 그 승인은 EA-4 (i)에 의해 **export 적격이 아니다.** 이는 "기록된 authority 이력 없음"으로 보고되어야 하며 오류로도, "판단이 존재하지 않음"으로도 보고되어서는 안 된다. **이력 위치의 소급 backfill은 계속 금지되며**, export가 위치를 합성하는 계기가 되어서는 안 된다.

**Persisted Representation (Confirmed, EA-10):** 이 절은 **의미**만 확정하고 물리적 저장 형태를 확정하지 않는다. 필요한 형태는 `041 §15` E1, `042 §8.2` D-11·`§7.2` S-12·`§9.3` C-12, `043 §7.5` R-12·`§7.6` AH-12의 선례를 따라 **strictly additive한 새 versioned representation**으로 도입한다. `§19`~`§22`의 legacy `edit_export_*` 관계는 **재사용하지 않으며** — 그 필수 legacy anchor와 실행 provenance는 EA-8이 금지한 값을 날조해야만 충족되므로 — 재해석·backfill·dual-write 없이 그대로 남고 released 행은 자신의 identity와 컬럼을 정확히 유지한다. identity 방향은 새로 만들지 않고 상속한다: **Application 소유**이며 immutable anchor에서 결정적으로 파생되고, provider 식별자·execution 식별자·`DomainResult`·UUID·timestamp·wall-clock·rowid·물리 경로·mutable currentness는 참여하지 않는다(`§7.5` R-10, `§7.6` AH-11). **정확한 hash 구성, conflict 분기 도달 가능성 회계, atomicity 경계는 구현 milestone에 위임한다**; 이 절은 자신의 identity·history·replay 계약을 저술하지 않는다.

**Final Selection Does Not Exist (Confirmed, EA-11):** Edit Pipeline에 **Final Selection은 제품 개념으로 존재하지 않는다** — legacy 세대에도, 이 세대에도, 미래 기능으로도 아니다. `042 §9.3` C-13, `042`의 Deferred 목록, `042 §18`이 Export와 나란히 그 이름을 열거한 곳에서 그 라벨은 **만들어질 무엇도 지시하지 않으며**, 같은 절의 Export 부분만 실재하고 그것은 이 절이 범위화한다. 그 released 문장들은 **삭제되지 않고**, 개념이 조사된 뒤 존재하지 않는 것으로 판정되었다는 note가 기록된다. `041`의 Final Subtitle과 그 선택은 **다른 Pipeline의 계약**이며 전혀 영향받지 않는다 — 거기서는 상호배타적인 전체 문서 후보 중 정확히 하나가 승인 자막이 되지만, 승인 편집은 집합의 상호보완적 원소이고 그 operative judgment는 `§7.6`이 이미 Candidate 단위로 파생한다.

**Sections Not Re-scoped (Confirmed):** 이 절은 `§19`·`§21`·`§22`, `§1`~`§18`, `043 §7.4`의 legacy 계약, `042`의 어떤 소절, `041`의 Final Subtitle 계약을 재범위화하지 않는다. 특히 `§21` Artifact와 `§22` 구체 serialization의 **이 세대 연결은 확정되지 않았다** — 그 released 문언은 legacy Assembly에 anchor하며, legacy 분기가 `§19`→`§20`→`§21`→`§22`를 각각 별도 PATCH로 확정한 것과 같이 각자 자기 세대 범위 결정을 요구한다. Export Profile·Export Configuration, 구체 export schema, 외부 파일 형식, serializer, provider·NLE adapter, 실행 가능한 편집 명령, output-timeline transformation, rendering, Artifact 생성, physical materialization, delivery, Export Package도 마찬가지로 재범위화되지 않는다.

**Deferred (이후 milestone):** `§15.4`의 목록 전체가 그대로 유지되며, 여기에 다음이 **명시적으로** 더해진다. **(1) Conflict가 존재하는 Source Timeline에서 Export Admission의 제품 동작** — Assembly를 admit하는지, 나머지 적격 편집만 admit하는지, timeline의 admission을 거부하는지, Conflict를 export 시점에 드러내야 하는지. EA-5는 Export가 중재하지 않는다는 것과 conflicted Candidate가 member를 기여하지 않는다는 것만 확정하며, 그 결과 나타날 제품 동작은 확정하지 않는다. **(2) overlap 판정** — 승인 range가 겹치는 두 적격 승인 편집에 대해 merge·split·우선순위·거부 중 무엇이 필요한지는 `§19` D-15·`§20` A-13이 남긴 그대로다. 이 절은 **어떤 overlap 규칙도 도입하지 않는다**: EA-4의 적격성 판정은 overlap을 고려하지 않으므로 이 계약 아래에서 overlap 승인 편집을 배제하는 filter를 구현이 발명할 수 없다. 결정 간 ordering semantics도 함께 deferred이며, `§20` A-8이 이미 요구하는 결정적 구성은 EA-8이 유지하고 그 canonical member 순서는 EA-10이 **presentation 문제로 위임**한다 — 실행·timeline·overlap 순서가 아니다(`§22` C-3 관용구). **(3) 적격 member가 없는 scope의 처리** — 그 경우 zero-member Assembly인지 명시적 거부인지 그 밖인지. Conflict만 있는 timeline도 적격 member가 없는 상태에 이르므로 이 정책이 두 경우를 함께 규율하게 된다. 이 세 항목은 admission 경계 이후의 제품 정책이며 각각 별도의 승인된 PATCH를 요구한다. 구현은 이들 중 어느 하나를 임의로 선택해 확정할 수 없다 — 선택된 동작이 계약으로 역독되기 때문이다. *(후속 기록, `PATCH-0038`: 세 항목 중 **(1) Conflict가 존재하는 Source Timeline의 제품 동작**은 `§26`이 확정했다. **(2) overlap 판정**과 **(3) 적격 member 없는 scope의 처리**는 그대로 미결이며, 후자에 대해서는 `§26` CD-11이 다섯 후보 동작(빈 Assembly·전체 거부·disclosure-only 결과·no-op 성공·별도 diagnostic 결과)을 모두 유보 상태로 명시하고 기존 stop을 유지한다.)* 이들 deferred 개념을 위한 placeholder field·record·table·enum·interface는 도입하지 않는다.

**Canonical Invariants (Confirmed):** (1) 이 절은 effective-transcript generation에만 적용되고 `§19`~`§22`의 legacy 계약과 기록은 불변이다. (2) 이 세대의 Assembly는 이 세대의 `ApprovedEditDecision`을 직접 모으고 `§19` atom 단계는 재현되지 않는다. (3) `§20` A-1의 anchor cardinality와 방향, cross-timeline·cross-media 금지는 그대로다. (4) membership은 그 Source Timeline의 모든 export 적격 승인 편집이며 subset·filter·사용자 선택·ranking은 없다. (5) export 적격성은 현재 유효한 판단의 승인·단일 actor·standing `current`의 세 조건이다. (6) supersede된 판단의 승인과 이력 위치 없는 판단은 적격하지 않으나 유효한 역사이며 손상이 아니다. (7) Export는 actor 사이를 중재하지 않으며 AH-9가 파생하지 않는 곳에서 operative judgment를 파생하지 않는다. (8) Assembly 구성은 승인 행위가 아니고 Review가 Human Authority의 유일한 행사 지점이다. (9) `ApprovedEditDecision`이 승인 편집 의도의 유일한 canonical authority로 남는다. (10) membership은 파생 관측이며 Final Selection 기록·aggregate·flag는 존재하지 않는다. (11) mutable current·stale·selection flag와 lifecycle state를 도입하지 않는다. (12) 실행 provenance와 Domain Result는 요구되지 않고 그 날조는 금지되며 결정성과 replay-safety는 유지된다. (13) Source Media·Source Timeline provenance는 anchor 연쇄로 확보되고 traceability는 유지된다. (14) 이력 위치의 소급 backfill은 금지된다. (15) 저장 형태는 strictly additive하고 legacy 관계는 재사용하지 않으며 released 행은 불변이다. (16) identity는 Application 소유·결정적이고 그 구성·atomicity는 구현에 위임된다. (17) Edit Pipeline에 Final Selection은 존재하지 않는다. (18) Conflict 상황의 제품 동작·overlap 판정·적격 member 없는 scope의 처리는 확정되지 않으며 구현이 임의로 선택할 수 없다. (19) `§21`·`§22`의 이 세대 연결은 별도 결정을 요구한다. (20) deferred 개념은 placeholder를 도입하지 않는다.

## 24. Effective-Transcript Generation — Edit Export Artifact Boundary

이 절은 `PATCH-0036`으로 승인된 Architect Decision(AR-1…AR-11)을 기록한다. `§23`의 **Sections Not Re-scoped**가 "별도 결정을 요구한다"고 남겨 둔 둘 중 **`§21` Artifact**를 effective-transcript generation에 한해 확정한다. `§21`의 B-1…B-15, `§19`·`§20`·`§22`·`§23`, `§1`~`§18`은 삭제·재작성·소급 해석되지 않는다. 이 절이 확정하는 것은 **하나의 Assembly가 어떻게 하나의 canonical external representation이 되는가**이며 그것이 어떤 구체 문법으로 표기되는가는 확정하지 않는다. 결정 번호에 `AR-` 접두사를 쓰는 것은 Artifact를 다루기 때문이며 계약상 의미는 없다.

**Scope and Instrument (Confirmed, AR-1):** 이 절은 **effective-transcript generation에만**, 그리고 **`§21`에만** 적용된다. `§19`·`§20`·`§21`·`§22`는 legacy execution-coupled generation의 계약으로 자기 세대에서 그대로 유효하며 그 기록과 파생은 유효하게 남는다. 두 세대는 영구히 구분 가능하고, 한 세대의 Assembly가 다른 세대 Artifact의 source가 되지 않는다. **`§22`는 이 절이 재범위화하지 않으며 이 세대에 대해 계속 deferred다.**

**Artifact Admission Anchor (Confirmed, AR-2):** 이 세대에서 하나의 Edit Export Artifact는 **정확히 하나의 `§23` Edit Export Assembly**에서 파생되며, 그 Assembly는 **immutable·read-only**로 소비되고, Artifact는 그 Assembly의 **완전한** 승인 편집 의미를 나타낸다. `§21` B-1의 **cardinality와 방향은 그대로다** — 하나의 Artifact, 하나의 Assembly, cross-Assembly Artifact 없음, 부분 Artifact 없음. 바뀌는 것은 source 자리를 차지하는 Assembly가 **어느 세대의 것인가**뿐이며, 이는 `043 §7.5` R-2가 Candidate의 세대만, `§23` EA-2가 member의 세대만 바꾼 것과 같은 관용구다.

**Two Layers, Not Three (Confirmed, AR-3):** `§21` B-12의 계층은 이 세대에서 다음이 된다: `ApprovedEditDecision`이 승인 의미를 **소유**하고, Assembly가 그것을 **참조**하는 coherent grouping이며, Artifact가 그것을 **제시**하는 파생 external representation이다. `§19` atom 계층은 `§23` EA-2가 재현하지 않았으므로 존재하지 않는다. **제시되는 값은 달라지지 않는다** — 승인 Source Timeline range, 승인 Candidate Type 또는 label, 승인 rationale, 승인 decision kind, human actor를 Assembly의 canonical member 순서로 제시하며, `§7.5` R-8이 `ApprovedEditDecision`을 그 값들의 소유자로 확정했기 때문이다(legacy atom도 `§19` D-3에 따라 거기서 복사했다). B-2의 전환(내부 canonical 기록 → 외부 파생 표현)과 B-3의 canonical external representation은 그 밖에 변경되지 않는다.

**The Presentation Copy Is Not a Duplication Violation (Confirmed, AR-4):** Artifact는 자신이 제시하는 승인 값의 복사본을 담는다. 이는 이 세대의 **"anchor를 통해 상속하고 복제하지 않는다"** 관용구(`042 §8.2` D-2·`§9.3` C-8, `§7.5` R-7, `§23` EA-2)를 위반하지 않는다 — 그 관용구는 **canonical 기록**을 규율하고, Artifact는 명시적으로 **derived·non-authoritative**이기 때문이다(B-5, B-6). self-contained external product를 제시하는 것이 Artifact 단계의 존재 이유 그 자체다(B-2). `ApprovedEditDecision`은 승인 편집 의도의, Assembly는 coherent grouping의 유일한 canonical authority로 남고 Artifact는 어떤 것에 대해서도 authoritative하지 않다.

**Execution-Free Provenance Is Inherited, Not Established (Confirmed, AR-5):** 이 세대의 Artifact는 `ProcessingRun`·`ProcessingUnit`·`UnitExecution`·RUNNING state·execution lifecycle·Domain Result identity 소유·Domain Result chaining을 **요구하지 않으며**, `§21`도 자기 세대에서 그것을 요구하지 않았다. 이 점이 `§19` D-2·`§20` A-9와 다르다 — 그 둘은 요구했고 `§7.5` R-6과 `§23` EA-8이 그 요구를 세대 범위로 명시해야 했으나, `§21`에 대해서는 **상속의 확인**이다. 가짜 실행 기록·synthetic Processing Run·합성 RUNNING state·**합성 Domain Result**를 provenance로 쓰는 것은 계속 **금지된다**(`040 §18` H-10, `041 §15` E6, `§23` EA-8). 파생은 **deterministic·replay-safe**하다: wall-clock과 무작위를 읽지 않으며 동일한 Assembly는 동일한 Artifact를 만든다.

**Provenance Through the Anchor (Confirmed, AR-6):** B-10의 traceability 요구는 **유지된다** — Artifact는 자신이 제시하는 Assembly, 그 Assembly의 member들, 그리고 이를 통해 Source Timeline과 Source Media까지 추적 가능해야 한다. 달라지는 것은 **담는 형태**이며 `§23` EA-8을 따른다: Source Timeline은 Assembly anchor에서 상속하고, Source Media는 anchor 연쇄 `Assembly → ApprovedEditDecision → ReviewDecision → Edit Candidate(042 §9.3) → Analysis Finding(042 §8.2) → Lecture Analysis Input Admission → current applicable Corrected Revision → parent Raw Transcript → Source Timeline → Source Media`로 확보한다. 일부를 denormalize할지는 이전 단계들과 마찬가지로 구현 선택이며, 어떤 형태를 택하든 `§2.9` Source Timeline traceability는 유지되어야 한다.

**Identity Direction (Confirmed, AR-7):** Artifact identity는 **Application이 소유**하며 immutable source Assembly에서 결정적으로 파생된다. provider 식별자·execution 식별자·`DomainResult`·UUID·timestamp·wall-clock·rowid·물리 경로·mutable currentness는 참여하지 않는다(`§7.5` R-10, `§7.6` AH-11, `§23` EA-10). **`§21`의 caller-owned identity는 legacy 전용**이며, 이는 R-10이 이 세대 전반에 대해 확정한 바다.

이 소절이 확정하는 것은 **identity 계약이지 cardinality 규칙이 아니다.** 그 귀결을 여기 기록하는 것은 나중에 발견되지 않게 하기 위함이다: identity가 결정적이고 Assembly의 의미가 고정되어 있으므로 **canonical 파생이 수렴한다** — 같은 Assembly에서 다시 파생하면 같은 identity가 나오고 같은 canonical Artifact가 된다. 이 소절은 하나의 Assembly에 대해 **Artifact가 하나만 존재해야 한다는 제품 규칙을 세우지 않으며**, 복수의 derived Artifact를 요구하지 않되 허용한 B-13을 부정하지도 않는다. 기록하는 것은 그 복수에 이르는 legacy의 경로 — 새 caller-owned identity — 가 legacy 세대에 남는다는 사실과, **복수를 만들어 내기 위한 목적만으로 discriminator를 발명해서는 안 된다**는 것뿐이다. 하나의 Assembly에 대한 복수 표현이 필요해지면 `§21` B-4와 `§22` C-10이 이미 그 자리를 serializer의 canonical Artifact projection으로 지정하고 있다.

정확한 hash 구성은 구현 milestone에 위임한다(`041 §15` E7, `042 §8.2` D-8·`§7.2` S-10·`§9.3` C-10, `§7.5` R-10, `§23` EA-10 선례). 구현은 identity에 참여하는 필드와 참여하지 않는 필드를 명시하고 그 선택이 R-10의 (A)/(B) 회계로 conflict 분기를 도달 가능하게 하는지를 기록해야 하며, **(B)를 택하더라도 semantic equality 검사를 제거하지 않는다.**

**The Artifact Re-decides Nothing (Confirmed, AR-8):** Artifact 파생은 export 적격성·admission standing·authority history·다중 actor Conflict를 **재평가하지 않는다.** membership은 Assembly가 admit될 때 `§23` EA-3·EA-4로 확정되었고, Artifact는 그 Assembly의 의미를 기록된 그대로 제시한다. 세 가지 귀결을 확정한다. **(a)** member의 판단이 이후 supersede되었거나 그 chain이 이후 `current` standing을 잃은 Assembly에서도 Artifact는 파생될 수 있으며, 그것은 **정상이고 손상이 아니다** — Assembly는 admit 당시 적격이었던 것을 기록하며 결코 재작성되지 않는다(`§23` EA-4, `§7.5` R-5). 이 세대의 released validation도 그것을 결함으로 표시하지 않는다. **(b)** Artifact는 **Assembly가 확정한 membership을 변경하지 않고 member의 승인 의미를 변경하지 않는다**: member를 filter·merge·split·생략하지 않으며 승인 값을 재작성·재도출·재해석하지 않는다. 생략은 승인 범위를 잘못 표현하는 일이며 `§23`이 유보한 membership 결정을 조용히 내리는 일이다. **presentation order는 이 항이 보호하는 대상이 아니다** — `§21` B-3이 이미 Assembly의 canonical member 순서로 제시하도록 하고 `§23`의 Deferred가 그 순서를 실행·timeline·overlap 순서가 아닌 **presentation**으로 확정했으며(`§22` C-3 관용구), 향후 `§22` serializer가 순서를 어떻게 표기할지는 그 계층에 속하고 **여기서 제약하지 않는다.** **(c)** `§23`이 **미결**로 둔 정책 — Conflict가 존재하는 timeline에서 Export Admission의 제품 동작, overlap 판정, 적격 member 없는 scope의 처리 — 은 **여기서 되열리지 않으며 계속 미결이다**. 그것을 Artifact 단계에서 다시 파생하는 구현은 `§23`이 승인된 PATCH에 유보한 것을 구현으로 확정하는 셈이 된다.

**Immutability and Non-authority (Confirmed, AR-9):** Artifact는 Assembly와 같은 의미에서 **immutable**하고 **insert-only**다: 기록된 Artifact는 갱신·재작성·재키잉·재번호되지 않으며, status 필드·lifecycle·state machine·Export Profile·Export Configuration이 존재하지 않는다(B-14, `§20` A-12, `§23` EA-7). **derived·regenerable**하다(B-5): 보존된 Assembly와 승인 원본에서 재구성할 수 있고, 그 손실은 어떤 `ApprovedEditDecision`·authority 위치·Assembly도 손상시키지 않는다. **non-authoritative**하다(B-6): 승인 결정을 만들지 않고 승인 의미를 변경·재해석하지 않으며 upstream을 대체하지 않는다. Artifact를 파생하는 것은 **Human Authority를 행사하지 않는다** — Review가 그 유일한 행사 지점으로 남는다(`§23` EA-6, `043 §13`, `§2.8`).

**Representation Scope and Failure (Confirmed, AR-10):** 이 절은 **canonical external representation만** 확정한다 — *무엇을* 전달하는가다. serializer, 구체 문법, export schema, 외부 파일 형식, byte payload, MIME type, filename, 물리 경로, 외부 URL, package, download, delivery, provider·NLE adapter, Export Profile, Export Configuration을 도입하지 않으며, 실행 가능한 편집 semantics도 도입하지 않는다: cut/keep/delete/transform 명령 없음, output-timeline 좌표와 transformation 없음, rendering instruction 없음(B-4, B-7, B-9). 승인 range는 계속 **Source Timeline** range이며 output-timeline 좌표가 아니다. B-11의 Representation Failure는 **변경 없이 유지된다**: Assembly의 승인 의미를 완전·충실하게 제시할 수 없으면 — 해석되지 않는 member, 또는 Assembly와 lineage가 일치하지 않는 member — 무엇을 제시할 수 없었는지 밝히는 **명시적 실패**가 되고 조용히 짧아진 Artifact가 되지 않으며 승인 원본은 보존된다. 새 실패 분류를 도입하지 않으며 **format-specific representability는 `§22`에 남는다.**

**Persisted Representation (Confirmed, AR-11):** 이 절은 **의미**만 확정한다. Artifact가 derived·regenerable·non-authoritative이므로(AR-9) `§21`은 durable 표현을 요구하지 않았고 **이 절도 요구하지 않는다** — legacy 실현도 어떤 저장 형태나 schema를 도입하지 않았다. 구현 milestone이 기록할지는 그 milestone의 선택이며, 기록한다면 그 형태는 **strictly additive한 새 versioned representation**이어야 하고(`041 §15` E1, `042 §8.2` D-11·`§7.2` S-12·`§9.3` C-12, `§7.5` R-12·`§7.6` AH-12, `§23` EA-10), Artifact에 authority를 부여해서는 안 되며, legacy `edit_export_*` 관계를 재사용해서는 안 된다 — 그 관계는 자기 세대에 속하고 backfill·dual-write·재해석 없이 그대로 남는다.

**Sections Not Re-scoped (Confirmed):** 이 절은 `§19`·`§20`·`§22`·`§23`, `§1`~`§18`, `043`의 어떤 소절, `042`의 어떤 소절, `041`의 계약을 재범위화하지 않는다. 특히 **`§22` 구체 serialization과 local materialization의 이 세대 연결은 확정되지 않았고** 별도의 승인된 PATCH를 요구한다 — 그 released 문언은 legacy Artifact에 anchor한다. `§23`이 미결로 둔 세 정책(Conflict 있는 timeline의 제품 동작, overlap 판정, 적격 member 없는 scope의 처리)도 이 절이 확정하지 않는다.

**Deferred (이후 milestone):** `§21` B-15의 목록 전체가 그대로 유지된다: serializer, 구체 external representation 문법, export schema, 외부 파일 형식, human-readable/machine-readable/NLE 구체 projection, cross-representation equivalence, format-specific representability, Export Profile·Export Configuration, provider·NLE adapter, physical materialization과 그 path·filename·checksum 정책, delivery·download·upload·외부 URL, Export Package, 실행 가능한 편집 명령, output-timeline transformation, rendering, retry·failure lifecycle, Artifact의 replacement·revision. 여기에 **`§22`의 이 세대 연결**과 `§23`의 세 미결 정책이 더해진다. 이들 deferred 개념을 위한 placeholder field·record·table·enum·interface는 도입하지 않는다.

**Canonical Invariants (Confirmed):** (1) 이 절은 effective-transcript generation의 `§21`에만 적용되고 legacy 계약과 기록은 불변이며 `§22`는 재범위화되지 않는다. (2) 하나의 Artifact는 정확히 하나의 `§23` Assembly에서 파생되고 그 Assembly의 완전한 의미를 나타내며 cross-Assembly Artifact는 없다. (3) upstream Assembly와 그 member는 read-only다. (4) 계층은 소유(ApprovedEditDecision) → 참조(Assembly) → 제시(Artifact)의 2층이고 제시 값은 달라지지 않는다. (5) 제시 복사본은 canonical 기록의 중복이 아니며 Artifact는 어떤 것에도 authoritative하지 않다. (6) 실행 provenance와 Domain Result는 요구되지 않고 그 날조는 금지되며 이는 `§21`에서 상속된다. (7) 파생은 deterministic·replay-safe다. (8) Source Timeline은 Assembly anchor에서, Source Media는 anchor 연쇄로 확보되고 traceability는 유지된다. (9) identity는 Application 소유·결정적이며 caller-owned identity는 legacy 전용이고 파생은 수렴한다 — 이는 identity 계약의 귀결이지 cardinality 규칙이 아니다. (10) 복수를 만들기 위한 discriminator를 발명하지 않는다. (11) Artifact는 적격성·standing·authority·Conflict를 재평가하지 않는다. (12) supersede된 member를 가진 Assembly의 Artifact는 정상이며 손상이 아니다. (13) Artifact는 Assembly의 membership과 member의 승인 의미를 변경하지 않으며 presentation order는 이 금지의 대상이 아니다. (14) `§23`의 세 미결 정책은 되열리지 않는다. (15) Artifact는 immutable·insert-only·derived·regenerable·non-authoritative이고 status·lifecycle·Profile·Configuration이 없다. (16) Artifact 파생은 Human Authority를 행사하지 않는다. (17) 범위는 canonical external representation까지이며 serializer·문법·파일·output timeline·package·URL은 없다. (18) B-11 Representation Failure는 유지되고 새 실패 분류는 없다. (19) durable 표현은 요구되지 않으며 기록한다면 strictly additive하고 authority를 얻지 않으며 legacy 관계를 재사용하지 않는다. (20) deferred 개념은 placeholder를 도입하지 않는다.

## 25. Effective-Transcript Generation — Edit Export Serialization and Local Materialization Boundary

이 절은 `PATCH-0037`로 승인된 Architect Decision(S-1…S-11)을 기록한다. `§24`의 **Sections Not Re-scoped**가 "별도의 승인된 PATCH를 요구한다"고 남겨 둔 **`§22`**를 effective-transcript generation에 한해 확정한다. `§22`의 C-1…C-14, `§19`·`§20`·`§21`·`§23`·`§24`, `§1`~`§18`은 삭제·재작성·소급 해석되지 않는다. 이 절이 확정하는 것은 **하나의 `§24` Artifact가 어떤 구체 문법으로 표기되고 어떻게 하나의 로컬 파일이 되는가**이다. 결정 번호에 `S-` 접두사를 쓰는 것은 serialization을 다루기 때문이며 계약상 의미는 없다.

**Scope and Instrument (Confirmed, S-1):** 이 절은 **effective-transcript generation에만**, 그리고 **`§22`에만** 적용된다. `§19`~`§22`는 legacy execution-coupled generation의 계약으로 자기 세대에서 그대로 유효하고, legacy serializer와 materializer는 legacy 문서를 변경 없이 계속 만들고 배치한다. 두 세대는 영구히 구분 가능하며 한 세대의 Artifact가 다른 세대 직렬화의 입력이 되지 않는다. 이 절은 `§22` 자신의 형태를 따라 **serialization과 local materialization을 함께** 다룬다 — C-6·C-7·C-8이 destination·collision·atomicity·result를 이미 제품 결정으로 고정했고 C-13이 실제 실행 가능한 결과를 요구하므로, 둘을 쪼개는 것은 Blueprint가 이미 하나로 만든 경계를 나누는 일이 된다.

**One Concrete Format (Confirmed, S-2):** 이 세대의 concrete format은 **LectureOS-native JSON**이며 그것 하나뿐이다. C-1의 근거가 그대로 적용된다: 이 세대의 Artifact가 담는 의미는 서술적 승인 편집 결정(승인 range·label·rationale·decision kind·actor)이며 실행 가능한 timeline operation이 아니므로, NLE interchange format(EDL·FCPXML·AAF·OTIO)으로 project하려면 존재하지 않는 timeline semantics를 발명하거나 비-timeline 의미를 조용히 버려야 한다. **두 번째 format을 계약하지 않으며**, 미래에 필요할 수 있다는 이유로 선제 계약하지도 않는다(`§21` B-15, `§22` C-14가 계속 deferred로 둔다).

**A Distinct Format Identity (Confirmed, S-3):** 이 세대의 문서는 `lectureos-edit-export-json` `v1`으로 **표시되지 않는다**. format identifier는 **`lectureos-lecture-edit-export-json`**, format version은 **`v1`**, media type 상당 식별자는 **`application/vnd.lectureos.lecture-edit-export+json`**이다. 이유는 두 가지다. 첫째, payload shape가 필연적으로 다르므로(아래 S-4) **하나의 identifier·version이 두 shape를 지칭해서는 안 된다** — 그러면 모든 consumer의 parse가 모호해진다. 둘째, 두 세대는 영구히 유효하고 어느 쪽도 다른 쪽을 대체하지 않으므로(`§23` EA-1, `§24` AR-1) **version bump는 관계를 잘못 기술한다** — legacy serializer는 legacy Artifact에 대해 계속 `v1`을 만든다. 이 상황에 대한 released 관용구는 **별도로 식별되는 새 표현**이며(`041 §15` E1, `042 §9.3` C-12, `043 §7.5` R-12, `§23` EA-10), 기존 것의 새 version이 아니다. `lecture-` 요소는 이 세대가 자기 기록에 이미 쓰는 명명과 일치한다. **두 문서 사이의 cross-format equivalence는 계약하지 않으며** deferred로 남는다(`§21` B-15) — 그것은 consumer가 둘을 호환 가능하게 다뤄야 할 때 비로소 필요해지고, 어떤 계약도 그것을 요구하지 않는다.

**Complete Faithful Field Mapping (Confirmed, S-4):** 직렬화된 문서는 `§24` Artifact의 **완전한** 의미를 담고 그 밖의 것을 담지 않는다. 최상위: format identifier, format version, artifact identity, source assembly identity, source timeline identity, 그리고 canonical 순서의 edit 목록. 각 edit: **source `ApprovedEditDecision` identity**(이 세대의 member 참조이며 legacy의 `source representation identity`를 대신한다), 승인 decision kind, 승인 range start, 승인 range end, 승인 Candidate Type 또는 label, 승인 rationale, human actor. 어떤 승인 필드도 생략·절단·정규화 제거·재해석·발명하지 않는다(C-2의 규칙 그대로).

**최상위 Source Media identity는 이 문서의 field가 아니며, `§22`도 그것을 요구하지 않는다.** 이는 가정이 아니라 released 문언에 대해 확인된 바다: C-2의 지배 절은 **Artifact 상대적**이고("serialize된 문서는 §21 Artifact의 완전한 의미를 담는다"), 뒤따르는 field 목록은 그 완전성이 **legacy Artifact에 대해** 무엇인지를 열거한 것이며(그 Artifact는 자신의 Source Media identity를 담는다), C-2의 마무리 금지는 "어떤 **승인 필드**"에 대한 것인데 Source Media identity는 **승인 의미가 아니라 provenance**다. `§22`의 Canonical Invariant (2)도 같은 방향으로 "완전한 **승인** 의미"라고 말한다. C-3는 순서만, C-4는 결정성만 규율하며, **그 어느 것도, 어떤 Canonical Invariant도 문서 자체에 Source Media field를 필수로 두지 않는다.** 따라서 `§22`가 부과하는 요구는 충족된다 — 이 세대의 문서는 **자기 Artifact에 대해 완전**하고 어떤 승인 필드도 빠뜨리지 않는다. 그 field를 넣으려면 serializer가 Source Media를 anchor 연쇄로 해석해야 하는데, 이는 C-10이 **non-authoritative projection**으로 정의한 계층에 저장소 조회를 밀어 넣고 `§24` AR-6이 Artifact 단계에서 정리한 것을 직렬화에서 다시 여는 일이 된다. Source Media는 문서가 담는 source assembly identity로부터 anchor 연쇄를 통해 계속 도달 가능하고, `§2.9` Source Timeline traceability는 문서가 함께 담는 source timeline identity로 직접 충족된다. payload만 가진 consumer에 대한 귀결은 Deferred에 기록되며, 이를 바꾸는 것은 별도의 승인된 PATCH를 요구하는 제품 결정이지 구현 선택이 아니다. field **이름**은 이 semantics 안에서 구현 milestone이 정한다.

**Deterministic Serialization (Confirmed, S-5):** 하나의 Artifact는 항상 하나의 logical payload와 하나의 byte 열을 만든다. field 순서는 고정되고, edit은 Artifact의 canonical entry 순서(곧 Assembly의 canonical member 순서)로 나타난다. encoding은 **UTF-8**, 개행은 **LF(`\n`)**, 문서 끝에는 **정확히 하나의** 개행을 둔다. 비-ASCII 문자(예: 한국어)는 escape 없이 보존한다. **직렬화 입력으로 금지되는 것:** wall clock, randomness, UUID, filesystem 경로, execution 식별자, provider 식별자, mutable currentness, ambient locale, process 의존 순서. 문서에 실린 member 순서는 **presentation**이며 실행 순서·편집 적용 순서·output timeline 순서·overlap 우선순위·authority 순위가 **아니다**(`§22` C-3, `§23`, `§24` AR-8(b)).

**Logical Payload and Physical File Are Separate (Confirmed, S-6):** 직렬화된 payload는 logical projection이고 파일은 그것의 하나의 물리적 배치다. **파일은 Artifact의 identity가 아니다.** 파일명, 디렉터리, 절대 경로, 상대 경로, URL, 수정 시각, inode, filesystem metadata는 **어떤 identity에도 참여하지 않으며** 직렬화의 입력도 아니다. 동일한 logical payload가 여러 destination에 materialize되어도 새 Artifact도, 새 승인 의미도, 새 export authority도 생기지 않는다.

**Local Materialization (Confirmed, S-7):** C-6·C-7·C-8이 **변경 없이 상속된다**: **caller가 destination을 제공**하고 Application은 경로를 정하지 않는다. 쓰기는 원자적이다 — temporary 파일에 완전히 기록·flush·fsync한 뒤 원자적으로 배치하므로 **최종 경로에 부분 파일이 결코 남지 않고** 실패 시 temporary 파일은 제거된다. 필요한 상위 디렉터리는 입력 계약이 허용하는 범위에서 생성할 수 있다. 최종 경로에 **동일 bytes**의 정규 파일이 있으면 **idempotent 성공**이고, **다른 bytes**의 정규 파일이 있으면 **명시적 collision 실패**이며 덮어쓰지 않는다. **덮어쓰기는 명시적으로 요청된 경우에만** 수행되고 그때도 원자적이다. 기존 **symlink나 정규 파일이 아닌 객체는 결코 덮어쓰지 않는다.** 성공은 완전한 파일이 durably 배치된 **뒤에만** 보고되며, 최종 경로·format identifier·format version·실현된 byte 길이·encoding을 담은 구조화된 결과로 반환된다. 동일 payload를 같은 destination에 반복 materialize하는 것은 idempotent 성공 경우이고, 다른 destination에 하는 것은 같은 logical payload의 또 하나의 배치일 뿐 그 밖의 무엇도 바꾸지 않는다. 여기 열거된 규칙을 넘는 destination 검증은 legacy 실현이 그러했듯 **구현 선택**이다.

**Three Failure Layers, Kept Distinct (Confirmed, S-8):** **(a) Artifact derivation failure** — Assembly의 승인 의미를 아예 제시할 수 없다(`§24` AR-10, `§21` B-11). **(b) Serialization failure** — Artifact의 canonical 의미를 선택된 구체 format으로 충실하게 표현할 수 없다(예: JSON이 표현할 수 없는 값); serializer는 무엇을 표현할 수 없었는지 밝히며 명시적으로 실패한다(C-5). **(c) Materialization failure** — bytes는 만들어졌으나 물리 파일을 안전하게 완성·배치하지 못했다. 셋 중 어느 것도 **빈 파일·빈 문서·부분 파일·성공 상태·조용한 member 누락·fallback format**으로 숨기지 않는다. 어떤 경우에도 upstream `LectureEditExportArtifact`·`LectureEditExportAssembly`·`ApprovedEditDecision`·Review 기록·authority 이력은 **그대로 보존된다**.

**Execution-Free Provenance Is Inherited, Not Established (Confirmed, S-9):** serialization과 local materialization은 `ProcessingRun`·`ProcessingUnit`·`UnitExecution`·RUNNING lifecycle·`DomainResult`·Domain Result chaining을 요구하지 않으며, `§22`도 자기 세대에서 그것을 요구하지 않았다 — `§24` AR-5가 `§21`에 대해 기록한 것과 같다. 이는 **확인이지 새 금지가 아니다.** 합성 실행 기록을 provenance로 쓰는 것은 계속 금지된다(`040 §18` H-10, `041 §15` E6, `§23` EA-8).

**No Persistence, and No Back-Door Requirement to Persist the Artifact (Confirmed, S-10):** C-12가 상속된다: 직렬화된 payload도 물리 파일 결과도 데이터베이스에 저장하지 않고, table·schema·migration을 도입하지 않으며 `SQLITE_SCHEMA_VERSION`을 바꾸지 않는다. materialization이 요청된 경우 로컬 파일시스템에만 side-effect가 있다. **이 절은 `§24` Artifact의 persistence를 직접적으로도 우회적으로도 요구하지 않는다**: 정상 경로는 `persist된 Assembly → 파생된 Artifact → 직렬화된 payload → 선택적 로컬 파일`이며 Artifact는 조회되는 것이 아니라 재파생된다. serializer identity, serialized-result identity, materialization 기록을 도입하지 않는다.

**Authority Separation (Confirmed, S-11):** 직렬화와 materialization은 **승인 행위가 아니다.** member를 제외·추가하거나 승인 값·label·rationale·actor·decision kind·range를 수정할 수 없고, re-approval·Final Selection·Export Approval·publication authority를 만들지 않는다. `ApprovedEditDecision`은 승인 편집 의도의, Assembly는 coherent grouping의, Artifact는 canonical external representation의 authority로 남고 serializer와 materializer는 **non-authoritative projection**이다(C-10, `§24` AR-9). Review는 Human Authority가 행사되는 유일한 단계로 남는다(`043 §13`, `§2.8`, `§23` EA-6). 여기서 적격성·standing·authority·Conflict를 재평가하지 않으며(`§24` AR-8), `§23`이 미결로 둔 세 정책은 **되열리지 않는다**.

**Sections Not Re-scoped (Confirmed):** 이 절은 `§19`·`§20`·`§21`·`§23`·`§24`, `§1`~`§18`, `043`의 어떤 소절, `042`의 어떤 소절, `041`의 계약을 재범위화하지 않는다. `§23`이 미결로 둔 세 정책(Conflict가 있는 timeline의 제품 동작, overlap 판정, 적격 member 없는 scope의 처리)도 확정하지 않는다.

**Deferred (이후 milestone):** `§21` B-15와 `§22` C-14의 목록 전체가 그대로 유지된다: 다른 concrete format(EDL·FCPXML·AAF·OTIO·CSV·SRT·DOCX), 다중 format, serializer registry와 plugin discovery, **두 세대 문서 사이의 cross-format equivalence**, format-specific representability의 확장, Export Profile·Export Configuration, provider·NLE adapter, 실행 가능한 cut/delete/keep/edit 명령, source media에의 편집 적용, output-timeline transformation, rendering, 원격 upload·download·외부 URL·object storage·delivery lifecycle, Export Package, retry·failure lifecycle, publication authority, payload나 파일의 replacement·revision·history, 파생 결과의 DB 저장, checksum 정책. 여기에 더해 **직렬화 문서가 최상위 Source Media identity를 담아야 하는지**가 명시적으로 유보된다(S-4). `§23`의 세 미결 정책도 그대로다. 이들 deferred 개념을 위한 placeholder는 도입하지 않는다.

**Canonical Invariants (Confirmed):** (1) 이 절은 effective-transcript generation의 `§22`에만 적용되고 legacy 계약·문서·golden은 불변이다. (2) serialization과 local materialization은 하나의 경계이며 그 근거는 `§22` 자신의 형태와 C-6·C-7·C-8이 제품 결정이라는 사실이다. (3) concrete format은 하나뿐이고 다중 format을 선제 계약하지 않는다. (4) format identity는 legacy와 구별되며 version bump가 아니다. (5) 문서는 자기 Artifact에 대해 완전하고 어떤 승인 필드도 생략·발명하지 않는다. (6) per-edit member 참조는 `ApprovedEditDecision` identity다. (7) 최상위 Source Media identity는 담지 않으며 `§22`도 그것을 요구하지 않는다. (8) 직렬화는 결정적이고 금지된 입력을 읽지 않는다. (9) member 순서는 presentation이며 실행·timeline·overlap·authority 순서가 아니다. (10) 파일은 identity가 아니며 경로·이름·URL·시각·metadata는 어떤 identity에도 참여하지 않는다. (11) destination은 caller가 제공하고 Application은 경로를 정하지 않는다. (12) 쓰기는 원자적이며 부분 파일을 남기지 않는다. (13) 동일 bytes는 idempotent 성공, 다른 bytes는 명시적 collision, 덮어쓰기는 명시 요청 시에만, symlink·비정규 객체는 덮어쓰지 않는다. (14) 성공은 완전 배치 후에만 구조화된 결과로 보고된다. (15) 실패는 세 계층으로 구분되고 어떤 위장으로도 숨기지 않으며 승인 upstream은 보존된다. (16) execution provenance 부재는 `§22`에서 상속되며 새 금지가 아니다. (17) payload와 파일은 저장되지 않고 `§24` Artifact의 persistence도 요구되지 않는다. (18) 직렬화와 materialization은 승인 행위가 아니며 Review가 Human Authority의 유일한 행사 지점이다. (19) `§23`의 세 미결 정책은 되열리지 않는다. (20) deferred 개념은 placeholder를 도입하지 않는다.

## 26. Effective-Transcript Generation — Edit Export Cross-Actor Conflict Disclosure Boundary

이 절은 `PATCH-0038`로 승인된 Architect Decision(CD-1…CD-11)을 기록한다. `§23` EA-5가 유보한 **세 제품 정책 중 첫째** — Conflict가 존재하는 Source Timeline에서 Export Admission의 제품 동작과 그 공개 방식 — 만 확정한다. `§19`~`§25`, `043`의 어떤 소절, `042`의 어떤 소절은 삭제·재작성·소급 해석되지 않는다. **이 절은 cross-actor Conflict를 해소하는 절이 아니다.** Conflict가 존재할 때 Export가 어떻게 동작하고 그 사실이 어떻게 반드시 공개되는지만 정하며, 해소는 Review에 남는다. 결정 번호에 `CD-` 접두사를 쓰는 것은 Conflict Disclosure를 다루기 때문이며 계약상 의미는 없다.

**Scope and Instrument (Confirmed, CD-1):** 이 절은 **effective-transcript generation에만** 적용되고 `§23` EA-5가 유보한 셋 중 **하나만** 결정한다. **overlap 판정**, **적격 member 없는 scope의 처리**, 그리고 **Conflict가 어떻게 해소되는가**에 대해서는 아무것도 결정하지 않는다. legacy 세대는 영향받지 않는다 — `§7.4`의 Alternative A는 authority 위치를 저장하지 않으므로 그 세대에는 cross-actor authority 이력 자체가 존재하지 않는다.

**Admission Proceeds (Confirmed, CD-2):** Source Timeline에 cross-actor Conflict가 있다는 사실은 **Assembly admission을 막지 않는다.** 그 timeline에 export 적격 `ApprovedEditDecision`이 하나 이상 남아 있으면 Assembly는 admit된다. **Conflict는 timeline 전체의 veto가 아니며**, 한 Candidate에 미해결 판단이 있다는 사실이 다른 Candidate의 export에 대한 권한을 만들지 않는다.

**Membership Is Unchanged, and the Exclusion Means Nothing More (Confirmed, CD-3):** conflicted Candidate는 member를 기여하지 않는다. 이는 **`EA-4` (i)·(ii)의 직접적 귀결**이며 — `043 §7.6` AH-9가 현재 유효한 판단을 파생하지 않으므로 그것이 소유한 승인이 존재하지 않는다 — **새 filter도, 새 배제 규칙도, Export의 판단도 아니다.** Export는 배제된 Candidate를 **reject된 것으로도, supersede된 것으로도, 해소된 것으로도, 철회된 것으로도, 승인되지 않은 것으로도 해석하지 않는다.** 그 Candidate의 Review 기록·authority 이력·그것이 소유한 `ApprovedEditDecision`은 있는 그대로 남고 유효하다(`§7.5` R-5, `§23` EA-4).

**Remaining Eligible Members Are Unaffected (Confirmed, CD-4):** 그 Source Timeline의 다른 모든 export 적격 `ApprovedEditDecision`은 `§23` EA-3이 요구하는 그대로 membership을 구성한다. **EA-3의 총체성은 변하지 않는다** — Assembly는 여전히 그 timeline의 **모든** export 적격 승인 편집을 뜻한다. timeline 어딘가의 cross-actor Conflict가 적격 member를 붙잡아 두는 일은 없다.

**Disclosure Is Mandatory (Confirmed, CD-5):** 그 timeline의 어떤 Candidate가 `§3.12` cross-actor Review Conflict 상태이면 admission result는 **그 사실을 반드시 공개한다.** 이 공개는 **선택적 warning이 아니며**, **결과 계약의 필수 구성요소**이므로 생략은 문체 선택이 아니라 **계약 위반**이다. 공개는 **Assembly membership과 분리**되고, **Artifact의 승인 의미와 분리**되며, **직렬화된 payload와 분리**되고, **persistence를 요구하지 않는다.** `§3.7`의 "Scope가 제한되었음을 숨기거나 …해서는 안 된다"와 `§3.12`의 "표시되어야 한다"는 여기서, 그리고 오직 여기서 충족된다.

**Minimum Disclosure Content (Confirmed, CD-6):** 공개는 그 Source Timeline의 conflicted Candidate 각각에 대해 최소한 다음을 담는다. **(a)** Candidate identity, **(b)** 그것에 authority 이력을 가진 **모든** actor identity, **(c)** **현재 유효한 판단이 파생되지 않았다**는 사실, **(d)** 그 Candidate가 **이 Assembly의 membership에 포함되지 않았다**는 사실. (c)와 (d)를 명시하는 이유는 그 부재야말로 오독되는 지점이기 때문이다. 더 풍부한 관측이 이미 가능하다면 그것을 함께 제시하는 것은 허용되나, 이 절은 **새 제품 의미를 발명하지 않는다** — severity 척도, Conflict 분류, actor 간 순서, Conflict 개수에 따라 달라지는 동작을 정의하지 않는다.

**Result Model — Disclosure-Bearing Success (Confirmed, CD-7):** 결과는 **공개를 수반한 성공**이다. **failure가 아니고**, partial failure도, silent success도, optional warning도, best-effort export도, degraded success도, **새 lifecycle state도 아니며**, **status 필드와 state machine을 도입하지 않는다.** Assembly는 정상적으로 admit되고 모든 면에서 통상의 Assembly이며, 공개는 그것을 만든 admission의 결과에 동반된다.

**Authority Separation Is Unchanged (Confirmed, CD-8):** Export는 actor를 priority·recency·role·permission으로 **서열화하지 않고**, 자동으로 merge하거나 selection하지 **않으며**, 무엇도 해소·재개·재승인·거부하지 **않는다**. **Review는 Human Authority가 행사되는 유일한 단계로 남는다**(`043 §13`, `§2.8`, `§23` EA-6, `§24` AR-9, `§25` S-11). `043 §15.3`의 다중 사용자 권위 질문은 **답해지지 않고 유보된 상태 그대로**이며, `§7.6` AH-9도 변경되지 않는다 — 이 절은 AH-9의 결과를 **소비할 뿐** 거기에 아무것도 더하지 않는다.

**Downstream Boundary, and the Exact Reach of the Non-Suppression Obligation (Confirmed, CD-9):** `§24` Artifact, `§25` serializer, `§25` materializer는 Conflict·적격성·standing·authority를 **재평가하지 않으며**(`§24` AR-8), 공개는 Artifact·직렬화된 문서·파일에 **삽입되지 않는다.**

이 절이 부과하는 의무는 **admission result의 직접 consumer에게만, 그리고 그에게만** 적용된다: admission result를 받는 Application 또는 Interface 계층은 그것이 담은 Conflict 공개를 **버려서는 안 되고**, 결과를 Conflict 없는 통상의 성공으로 **축약해서는 안 되며**, 공개가 없는 Assembly-only 결과로 **대체해서는 안 된다.** 표현 — 문구, 순서, severity, 배치 — 은 그 계층의 몫이지만 **억제는 아니다.** 이 의무는 **전이되지 않는다**: 결과를 받은 계층에서 이행되며, 이 절은 그보다 하류의 어떤 것에도 요구를 두지 않는다.

**따라서 이 절은 다음을 결정하지 않는다:** `§24` Artifact가 Conflict 공개를 담아야 하는지, `§25` serializer가 Conflict나 부분 scope 표시를 JSON payload에 넣어야 하는지, `§25` materializer가 export와 함께 별도 Conflict 파일을 만들어야 하는지, 향후 delivery나 Export Package 계층이 공개를 보존해야 하는지, 로컬 JSON 파일만 가진 외부 consumer가 scope가 제한되었음을 알 수 있어야 하는지. 다섯 항목 모두 `§15.3`의 scope-completeness 질문 및 이후 delivery·packaging 계약과 함께 **deferred로 남는다.**

**No New Structure (Confirmed, CD-10):** 새 aggregate, Conflict Artifact, Conflict Report Artifact, `DomainResult`, persistent diagnostic 기록, Assembly 컬럼, Artifact field, serializer field, JSON format version, lifecycle, status 필드를 **도입하지 않는다.** 공개는 **이미 존재하는 admission observation과 result 경계**를 사용한다. 아무것도 저장되지 않는다 — Conflict는 append-only 행들에 대한 파생 관측이며 admission마다 다시 파생된다(`§7.5` R-4, `§7.6` AH-8, `§23` EA-7).

**Zero Eligible Member Is Not Decided Here (Confirmed, CD-11):** conflicted Candidate를 제외한 결과 그 timeline에 export 적격 member가 **하나도 없으면** 이 절은 **무슨 일이 일어나는지 말하지 않는다.** 그것은 `§23`이 유보한 둘째 정책이며 그대로 유보된다: **빈 Assembly, 전체 거부, disclosure-only 결과, no-op 성공, 별도 diagnostic 결과 — 다섯 모두 여전히 미결이고** 구현이 그중 어느 것도 확정할 수 없다. 그 상태에 도달하면 기존의 미결-정책 stop을 유지한다. 두 상황은 분리 가능하다 — 이 절은 "Conflict가 막는가"를 묻고 그 정책은 "적격 member 없는 scope가 admit 가능한가"를 묻는다 — 그리고 **모든 Candidate가 conflicted인 경우**에만 교차하는데, 그때는 **미결 정책이 지배한다.**

**Sections Not Re-scoped (Confirmed):** 이 절은 `§19`~`§25`, `§1`~`§18`, `043 §3.12`·`§7.5`·`§7.6`·`§11`·`§15.3`·`§15.4`, `042`의 어떤 소절, `041`의 계약을 재범위화하지 않는다. 특히 **`§7.6` AH-9의 authority 파생은 변경되지 않으며**, `§23` EA-5가 확정한 비중재 원칙과 `§23`의 나머지 두 미결 정책도 그대로다.

**Deferred (이후 milestone):** `§23`이 유보한 것 중 **overlap 판정과 결정 간 ordering semantics**, 그리고 **적격 member 없는 scope의 처리**(CD-11)가 전부 그대로 남는다. `§15.3`·`§15.4`에서: 직렬화 문서가 Conflict나 제한된 scope를 표시해야 하는지, 파일만 가진 consumer가 제한을 인지하는 방법, interface의 문구와 severity, 그리고 향후 delivery·packaging 계층에서의 공개 보존. `043 §15.3`·`§15.4`에서: **다중 actor 사이의 authority 해석**, 같은 kind·다른 승인 내용의 이력 표현, **withdrawal**, **revocation**. `§21` B-15와 `§22` C-14의 목록도 변함없다. 이들 deferred 개념을 위한 placeholder는 도입하지 않는다.

**Canonical Invariants (Confirmed):** (1) 이 절은 `§23`의 세 미결 중 첫째만 결정하고 나머지 둘은 그대로 미결이다. (2) cross-actor Conflict는 Source Timeline 전체의 veto가 아니다. (3) 적격 member가 하나 이상 남아 있으면 admission은 진행한다. (4) conflicted Candidate의 배제는 `EA-4`의 귀결이며 새 규칙이 아니다. (5) 배제는 reject·supersede·resolve·withdraw·미승인 중 어느 것도 뜻하지 않는다. (6) 배제된 Candidate의 기록과 이력은 유효하게 남는다. (7) 나머지 적격 member는 `EA-3`대로 전부 포함되고 총체성은 변하지 않는다. (8) Conflict 공개는 admission result의 필수 구성요소이며 생략은 계약 위반이다. (9) 공개는 membership·승인 의미·payload·persistence와 분리된다. (10) 최소 공개는 Candidate identity·모든 actor·현재 판단 미파생·membership 미포함의 네 항목이다. (11) severity·분류·순서·개수 의존 동작을 발명하지 않는다. (12) 결과는 disclosure-bearing success이며 failure도 partial failure도 아니다. (13) status 필드와 lifecycle을 도입하지 않는다. (14) Export는 actor를 서열화하지도 자동 merge·selection하지도 않는다. (15) Review가 Human Authority의 유일한 행사 지점이다. (16) `043 §15.3`은 답해지지 않고 `§7.6` AH-9는 변경되지 않는다. (17) downstream은 Conflict를 재평가하지 않고 공개는 Artifact·문서·파일에 삽입되지 않는다. (18) 비-억제 의무는 admission result의 직접 consumer에만 적용되고 전이되지 않는다. (19) 새 구조를 전혀 도입하지 않고 기존 경계를 사용하며 아무것도 저장하지 않는다. (20) 적격 member 없는 scope의 처리는 이 절이 결정하지 않는다.

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
