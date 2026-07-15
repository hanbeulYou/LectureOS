# 044_EXPORT_PIPELINE

- Status: Draft
- Version: Blueprint 0.1
- Last Updated: 2026-07-15
- Depends On: `000_MANIFESTO.md`, `001_PRODUCT.md`, `002_FAQ.md`, `003_VISION.md`, `004_PRINCIPLES.md`, `020_PRODUCT_REQUIREMENTS.md`, `021_SYSTEM_CONTEXT.md`, `030_DATA_MODEL.md`, `031_ARCHITECTURE.md`, `040_TRANSCRIPT_PIPELINE.md`, `041_SUBTITLE_PIPELINE.md`, `042_LECTURE_INTELLIGENCE_PIPELINE.md`, `043_REVIEW_PIPELINE.md`
- Referenced By:

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
- Artifact 저장과 전달 방식
- 실행, 재시도 또는 배포 방식
- Rendering 구현
- 자동 승인 또는 자동 편집
- 외부 시스템의 정책과 호환성 보장
- Source Media, Transcript, Subtitle, Analysis 또는 Review 내부 처리

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
