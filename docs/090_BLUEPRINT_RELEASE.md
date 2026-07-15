# LectureOS Blueprint v1 Release

- Status: Released
- Release Date: 2026-07-15
- Baseline: Blueprint v1

## 1. Purpose

이 문서는 LectureOS Blueprint v1의 Release 기준선과 문서 탐색 경로를 제공한다.

현재까지 정의된 Product와 System 계약, 문서별 책임, Freeze 범위, Deferred Work와 다음 단계 후보를 요약한다. 새로운 Product Requirement, Domain Concept, Pipeline 또는 구현 계약을 정의하지 않는다.

`Released`는 현재 기준선을 승인했다는 뜻이며 이후 변경을 금지한다는 뜻이 아니다. 변경은 PATCH를 통해 이유와 영향을 기록한 뒤 반영한다.

## 2. Release Scope

### 2.1 Foundation

- [000_MANIFESTO.md](./000_MANIFESTO.md)
- [001_PRODUCT.md](./001_PRODUCT.md)
- [002_FAQ.md](./002_FAQ.md)
- [003_VISION.md](./003_VISION.md)
- [004_PRINCIPLES.md](./004_PRINCIPLES.md)

Foundation은 LectureOS의 존재 이유, 제품 계약과 경계, 반복 질문, 장기 목적지와 의사결정 원칙을 정의한다.

### 2.2 Product

- [020_PRODUCT_REQUIREMENTS.md](./020_PRODUCT_REQUIREMENTS.md)

Product Requirements는 Text Pipeline과 Edit Pipeline을 동등한 핵심으로 두고 현재 제품 범위와 Must 요구사항을 정의한다.

### 2.3 System Model

- [021_SYSTEM_CONTEXT.md](./021_SYSTEM_CONTEXT.md)
- [030_DATA_MODEL.md](./030_DATA_MODEL.md)
- [031_ARCHITECTURE.md](./031_ARCHITECTURE.md)

System Model은 LectureOS의 외부 경계, Conceptual Data Model과 논리적 처리 책임을 정의한다.

### 2.4 Text Pipeline

- [040_TRANSCRIPT_PIPELINE.md](./040_TRANSCRIPT_PIPELINE.md)
- [041_SUBTITLE_PIPELINE.md](./041_SUBTITLE_PIPELINE.md)

Text Pipeline은 Source Media에서 Raw Transcript와 Corrected Transcript를 거쳐 Final Subtitle이 준비되는 책임을 정의한다.

### 2.5 Edit Pipeline

- [042_LECTURE_INTELLIGENCE_PIPELINE.md](./042_LECTURE_INTELLIGENCE_PIPELINE.md)
- [043_REVIEW_PIPELINE.md](./043_REVIEW_PIPELINE.md)
- [044_EXPORT_PIPELINE.md](./044_EXPORT_PIPELINE.md)

Edit Pipeline은 강의 분석과 Edit Candidate, Human Decision, Approved Edit Decision과 외부 Artifact 표현의 책임을 구분한다.

### 2.6 Extension Model

- [050_PLUGIN_SYSTEM.md](./050_PLUGIN_SYSTEM.md)

Extension Model은 Provider Independence를 위한 Capability Contract와 Plugin Concept의 경계를 정의한다.

### 2.7 Change Sets

- [PATCH-0001](../patches/PATCH-0001-l0-and-prd-stabilization.md)
- [PATCH-0002](../patches/PATCH-0002-system-model.md)
- [PATCH-0003](../patches/PATCH-0003-text-pipeline.md)
- [PATCH-0004](../patches/PATCH-0004-edit-pipeline.md)
- [PATCH-0005](../patches/PATCH-0005-plugin-system.md)

PATCH는 Blueprint가 현재 무엇을 정의하는지 대신 설명하지 않는다. 각 Change Set이 왜 필요했고 어떤 문제와 결정 경계를 다뤘는지 기록한다.

## 3. Recommended Reading Order

1. Foundation: `000~004`
2. Product Requirements: `020`
3. System Context: `021`
4. Data Model: `030`
5. Architecture: `031`
6. Transcript Pipeline: `040`
7. Subtitle Pipeline: `041`
8. Lecture Intelligence Pipeline: `042`
9. Review Pipeline: `043`
10. Export Pipeline: `044`
11. Plugin System: `050`
12. PATCH documents: `PATCH-0001~0005`

Blueprint를 먼저 읽어 현재 계약을 이해한 뒤, 변경 이유와 의사결정 배경이 필요할 때 PATCH를 읽는다.

## 4. Defined Product Contract

Blueprint v1은 다음 계약을 현재 기준선으로 확정한다.

- **Source Media and Source Timeline:** Source Media는 변경하지 않으며 시간 기반 결과는 Source Timeline으로 추적한다.
- **Transcript Is Not Subtitle:** Transcript는 발화의 언어적 표현이고 Subtitle은 시청 가독성을 위한 시간 기반 표현이다.
- **Raw Is Not Corrected:** Raw Transcript는 provider의 변경 전 결과이고 Corrected Transcript가 이를 덮어쓰지 않는다.
- **Candidate Is Not Decision:** AI 또는 규칙 기반 Candidate는 Human Decision이 아니다.
- **Analysis Is Not Editing:** Lecture Intelligence는 분석하고 제안하지만 실제 미디어를 편집하지 않는다.
- **Lecture Segment Is Not Edit Candidate:** Lecture Segment는 분석 표현이고 Edit Candidate는 선택적인 편집 제안이다.
- **Human Authority:** Accept, Reject, Modify와 최종 교육적·편집적 판단은 사람에게 있다.
- **Review Decision and Approved Edit Decision:** Review Decision은 사용자의 판단이며 Approved Edit Decision은 승인된 편집 의도를 보존한다.
- **Decision Is Not Artifact:** Decision은 외부 전달 표현이나 실제 편집 결과가 아니다.
- **Export Is Not Rendering:** Export는 승인 결과를 Artifact로 표현하며 실제 편집이나 Rendering을 수행하지 않는다.
- **Provider Independence:** 특정 AI, STT, NLE 또는 외부 format이 LectureOS Concept를 소유하지 않는다.
- **Capability Is Not Provider:** Capability Contract가 provider와 Plugin 선택보다 먼저 존재한다.
- **Safe Reprocessing:** 재처리는 기존 provenance와 Human Decision을 조용히 삭제하거나 변경하지 않는다.
- **Provenance and Traceability:** 원본, provider 결과, revision, Candidate, Decision과 Artifact 사이의 계보를 설명할 수 있어야 한다.

이 목록은 관련 Blueprint의 요약이며 독립적인 새 정의가 아니다.

## 5. Responsibility Map

| Document Area | Primary Responsibility |
| --- | --- |
| Product Requirements | 제품 범위, 동등한 Text/Edit 결과와 Must 요구사항 |
| System Model | System Boundary, Domain Concept와 논리적 책임 관계 |
| Transcript Pipeline | Raw Transcript와 Corrected Transcript로 이어지는 발화 기록 |
| Subtitle Pipeline | 가독성을 위한 reading 및 time representation과 Final Subtitle |
| Lecture Intelligence Pipeline | 강의 분석, Analysis Finding과 Edit Candidate |
| Review Pipeline | Human Review, Review Decision과 Approved Edit Decision |
| Export Pipeline | 승인 결과의 외부 Artifact 표현 |
| Plugin System | Capability Contract와 provider 제공 경계 |
| PATCH | 변경 필요성, 영향 범위와 결정 이유 기록 |

각 영역은 다른 문서의 책임을 흡수하지 않는다. 세부 계약은 해당 Blueprint를 따른다.

## 6. Frozen Scope

Blueprint v1의 Release 기준선으로 고정되는 범위는 다음과 같다.

- 핵심 Concept의 의미
- 문서 간 책임 경계
- Pipeline 간 입력과 결과 관계
- Human Authority
- Provider Independence
- provenance
- Safe Reprocessing
- Source Timeline traceability

Freeze는 이후 변경을 금지하지 않는다. 기준선을 변경해야 할 때 기존 Blueprint를 조용히 수정하지 않고 새로운 PATCH에 변경 이유, 영향받는 문서와 계약 영향을 기록한다.

오탈자, 링크 또는 의미를 바꾸지 않는 문서 정리도 현재 계약을 훼손하지 않아야 한다. 의미나 책임 경계에 영향을 주는 변경은 Change Policy를 따른다.

## 7. Deferred Work

Blueprint v1은 다음 영역을 의도적으로 정의하지 않는다.

- Database와 저장 구조
- API와 interface 세부 형식
- Runtime, Queue와 Worker
- Framework와 기술 스택
- Plugin Runtime과 Plugin SDK
- Plugin 설치, 로딩과 package 관리
- 특정 AI 또는 STT provider
- 특정 NLE
- 구체적인 export format
- FCPXML
- 자동 컷 적용
- Rendering
- 외부 편집 round trip
- UI 상세 설계
- 상태 머신 구현
- 구체적인 schema와 serialization

Deferred는 자동 승인된 다음 작업을 뜻하지 않는다. 필요성과 우선순위는 별도 Change Set 또는 Implementation Design 과정에서 판단한다.

## 8. Change Policy

Freeze 이후 Blueprint 계약 변경은 다음 절차를 따른다.

1. 변경 필요성을 식별한다.
2. 변경 이유를 기록할 PATCH를 생성한다.
3. 영향받는 Blueprint 문서와 책임 경계를 정의한다.
4. 승인된 범위에서 Blueprint를 수정한다.
5. 문서 간 일관성과 scope drift를 Review한다.
6. 승인된 변경을 Merge한다.
7. PATCH의 Result와 완료 상태를 갱신한다.

Blueprint는 현재 계약을 정의하고 PATCH는 변경 이유를 기록한다. PATCH가 Blueprint의 Product Contract를 대신하거나 Blueprint가 PATCH의 변경 이력을 복제하지 않는다.

## 9. Known Open Questions

다음은 기존 Blueprint의 Requires Validation 중 Implementation Design에 직접 영향을 주는 영역을 요약한 것이다.

- **Project Lifecycle:** Project와 Lecture의 관계, 여러 Source Media의 결합, 외부 파일 수명주기 책임
- **Execution and Reprocessing Boundary:** Processing Run과 지속되는 Domain Concept의 경계, 단계별 재실행 범위, 부분 성공 처리
- **Minimum Plugin Capabilities:** 초기 Product Requirements에서 독립적으로 구분할 Capability 집합과 Contract 변화의 compatibility 판단
- **Review Reconciliation:** 재처리 후 Candidate와 기존 Review Decision의 연결, stale 상태와 여러 Review iteration 처리
- **Export Profile and Configuration:** 두 개념의 제품 수준 경계, 부분 Export Scope와 Representation 간 의미 동등성
- **Privacy and Plugin Context:** 외부 provider에 전달할 수 있는 미디어·음성·텍스트·Context의 범위와 사용자 통제
- **Storage and Execution Model:** provenance, 사용자 결정, 결과 재생성과 실패를 보존할 구현 수준의 저장·실행 책임

이 문서는 질문에 답하거나 기존 Requires Validation 상태를 변경하지 않는다.

## 10. Next Phase

다음 단계는 Core Blueprint의 제품 계약을 확대하는 것이 아니라 승인된 기준선을 Implementation Design으로 구체화하는 것이다.

후보 영역은 다음과 같다.

- Project Lifecycle
- Execution Model
- Processing Job Model
- Reprocessing and Reconciliation Model
- Storage Model
- Interface Contracts
- Plugin Runtime
- Security and Permission Model

이 항목들은 이번 Release에서 정의하거나 착수하지 않는다. 후속 설계는 기존 Core Product Contract의 하위 구현 책임이어야 하며 이를 임의로 변경해서는 안 된다.

## 11. Release Invariants

- Blueprint는 구현 상세가 아니다.
- PATCH는 Blueprint를 대체하지 않는다.
- provider output은 canonical Product Concept가 아니다.
- Human Decision은 AI 결과보다 높은 작업 권위를 가진다.
- Candidate는 Decision이 아니다.
- Decision은 Artifact가 아니다.
- Transcript는 Subtitle이 아니다.
- Analysis는 Editing이 아니다.
- Validation은 Meaning이나 Approval이 아니다.
- 모든 시간 기반 결과는 Source Timeline으로 추적 가능해야 한다.
- 재처리는 과거 provenance와 Human Decision을 조용히 삭제하지 않는다.

## Related Documents

### Blueprint

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
- [044_EXPORT_PIPELINE.md](./044_EXPORT_PIPELINE.md)
- [050_PLUGIN_SYSTEM.md](./050_PLUGIN_SYSTEM.md)

### Change Sets

- [PATCH-0001](../patches/PATCH-0001-l0-and-prd-stabilization.md)
- [PATCH-0002](../patches/PATCH-0002-system-model.md)
- [PATCH-0003](../patches/PATCH-0003-text-pipeline.md)
- [PATCH-0004](../patches/PATCH-0004-edit-pipeline.md)
- [PATCH-0005](../patches/PATCH-0005-plugin-system.md)
