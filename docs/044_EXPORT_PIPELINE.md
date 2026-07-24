# 044_EXPORT_PIPELINE

- Status: Draft
- Version: Blueprint 0.6
- Last Updated: 2026-07-24
- Depends On: `000_MANIFESTO.md`, `001_PRODUCT.md`, `002_FAQ.md`, `003_VISION.md`, `004_PRINCIPLES.md`, `020_PRODUCT_REQUIREMENTS.md`, `021_SYSTEM_CONTEXT.md`, `030_DATA_MODEL.md`, `031_ARCHITECTURE.md`, `040_TRANSCRIPT_PIPELINE.md`, `041_SUBTITLE_PIPELINE.md`, `042_LECTURE_INTELLIGENCE_PIPELINE.md`, `043_REVIEW_PIPELINE.md`
- Referenced By:
- Amended By: `patches/PATCH-0007-physical-materialization.md`, `patches/PATCH-0008-delivery-deferral.md`, `patches/PATCH-0015-edit-pipeline-export-application-foundation.md`, `patches/PATCH-0016-edit-export-assembly-scope.md`, `patches/PATCH-0017-edit-export-artifact-representation.md`

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

### 15.2 Working Assumption

- Export Profile은 외부 사용 목적별 표현 책임을 구분하는 개념적 문맥으로 유용하다.
- Export Scope는 전체 승인 결과와 명시적으로 선택된 일부 결과를 구분할 수 있다.
- 동일한 의미의 재생성은 byte-level 동일성보다 승인 의미와 traceability의 동등성을 우선한다.

### 15.3 Requires Validation

- Export Profile과 Export Configuration의 제품 수준 경계는 어디까지인가?
- 일부 승인 결과만 export할 때 Scope의 완전성을 사용자가 어떻게 확인해야 하는가?
- 서로 다른 Representation 사이에서 동일한 승인 의미를 검증하는 기준은 무엇인가?
- 외부 consumer가 표현할 수 없는 승인 의미를 발견했을 때 허용 가능한 처리 범위는 무엇인가?

### 15.4 Deferred

- 구체적인 export schema와 파일 형식
- subtitle Artifact의 구체적인 형식과 문법
- 외부 NLE별 통합 방식
- 자동 컷 적용과 편집 명령 생성
- 외부 편집 완료본의 round trip
- Rendering과 전달 구현

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
