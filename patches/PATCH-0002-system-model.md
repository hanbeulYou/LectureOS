# PATCH-0002

- Title: System Model
- Status: Completed
- Trigger: Completion of PATCH-0001
- Created: 2026-07-15

## Background

PATCH-0001로 LectureOS의 제품 계약과 Text Pipeline·Edit Pipeline의 동등한 범위가 안정화되었지만, 제품 요구사항을 시스템 설계로 연결하는 System Layer는 아직 없었다.

`021_SYSTEM_CONTEXT.md`, `030_DATA_MODEL.md`, `031_ARCHITECTURE.md`는 각각 LectureOS의 Boundary, Concept, Logical Architecture를 정의했다. 이 Patch는 이미 Merge된 세 문서가 하나의 일관된 System Model을 형성하게 된 이유와 확정 사항을 기록한다.

## Trigger

- Trigger Type: Completion of PATCH-0001
- Source: PATCH-0001 이후 Merge된 System Layer 문서

## Findings

### F-01 — 제품 계약과 내부 설계 사이의 시스템 경계 필요

제품 요구사항만으로는 LectureOS와 외부 시스템의 책임, 신뢰 경계와 데이터 이동을 후속 설계가 일관되게 해석하기 어려웠다.

### F-02 — Concept와 Component의 책임 분리 필요

원본, Transcript, Subtitle, Candidate, Decision, Artifact의 제품 의미를 먼저 정의하지 않으면 컴포넌트나 특정 provider 구조가 중심 모델을 대신할 위험이 있었다.

### F-03 — 재처리와 인간 권위의 공통 계약 필요

AI provider나 처리 단계가 바뀌어도 원본과 사용자 결정을 보존하는 제약을 System Context, Data Model과 Architecture가 함께 유지해야 했다.

## Goals

- LectureOS의 System Boundary와 외부 책임을 정의한다.
- 핵심 Domain Concept와 관계를 Conceptual Data Model로 정의한다.
- Concept를 처리하는 논리적 Component와 Pipeline 책임을 정의한다.
- Concept와 Component의 책임을 분리한다.
- External AI Provider 독립성을 유지한다.
- 사용자 Review Decision의 권위를 보존한다.
- 부분 재처리와 provenance 유지 계약을 확정한다.

## Non-Goals

- 데이터베이스 또는 저장 schema
- API와 통신 형식
- 저장 기술과 파일 구조
- runtime, process 또는 deployment 설계
- UI 구조와 framework
- 기술 스택과 provider 선정
- Pipeline별 세부 처리 규칙

## Files

- `docs/021_SYSTEM_CONTEXT.md`
- `docs/030_DATA_MODEL.md`
- `docs/031_ARCHITECTURE.md`

## Key Decisions

1. **System Boundary:** LectureOS는 분석, 후보 생성, 통합 Review와 승인 결과 준비를 담당하고 실제 시각 편집과 렌더링은 외부 시스템이 담당한다.
2. **Transcript / Subtitle Separation:** Transcript는 발화 의미 계층이고 Subtitle은 시청 가독성을 위한 파생 표현이다.
3. **Candidate / Decision / Artifact Separation:** AI 후보, 사용자 결정, 승인 결과와 외부 Artifact는 서로 다른 권위와 책임을 가진다.
4. **Concept Before Component:** Domain Concept는 Component보다 먼저 존재하며 Component 구조로 재정의되지 않는다.
5. **Responsibility Ownership Is Not Data Ownership:** Component의 `Owns`는 논리적 처리 책임이며 Conceptual Identity의 독점 소유를 뜻하지 않는다.
6. **Provider Independence:** 특정 ASR, LLM, correction, Lecture Analysis provider 또는 NLE 구조를 중심 모델로 사용하지 않는다.
7. **Reprocessing Contract:** 재처리는 새 후보를 만들 수 있지만 원본, Review 이력과 승인된 사용자 결정을 암묵적으로 삭제하거나 덮어쓰지 않는다.
8. **Human Review Authority:** AI 결과는 검증 전 후보이며 Accept, Reject, Modify와 최종 교육적·편집적 판단은 사용자에게 있다.

## Scope

이 Patch는 위 세 문서가 정의한 System Boundary, Conceptual Data Model과 Logical Architecture를 하나의 Change Set으로 기록한다.

## Out of Scope

- `040~044` Pipeline의 세부 책임
- 구현 코드와 기술 선정
- PATCH-0001의 제품 계약 변경
- 자동 컷 적용, FCPXML과 외부 편집 round trip

## Constraints

- `020_PRODUCT_REQUIREMENTS.md` 및 PATCH-0001과 충돌하지 않는다.
- Text Pipeline과 Edit Pipeline을 동등한 핵심 범위로 유지한다.
- Source Media와 Source Timeline을 변경하지 않는다.
- AI 후보와 사용자 결정을 혼합하지 않는다.
- System Boundary와 내부 Implementation Boundary를 혼동하지 않는다.

## Acceptance Criteria

- [x] LectureOS의 System Boundary가 정의되었다.
- [x] 핵심 Concept와 관계가 정의되었다.
- [x] Logical Architecture와 책임 단위가 정의되었다.
- [x] Concept와 Component의 소유 책임이 분리되었다.
- [x] Provider Independence와 Human Review Authority가 유지되었다.
- [x] 재처리에서 사용자 결정을 보존하는 계약이 정의되었다.
- [x] `020_PRODUCT_REQUIREMENTS.md`와 충돌하지 않는다.
- [x] PATCH-0001의 제품 계약을 유지한다.

## Completion Checklist

- [x] System Context completed
- [x] Conceptual Data Model completed
- [x] Logical Architecture completed
- [x] Review refinements applied
- [x] Blueprint documents committed
- [x] Patch documentation backfilled

## Result

- Status: Completed
- Changed Blueprint Files: `docs/021_SYSTEM_CONTEXT.md`, `docs/030_DATA_MODEL.md`, `docs/031_ARCHITECTURE.md`
- Notes: 이미 Merge된 System Layer의 결정과 범위를 기록했다. 새로운 설계 결정은 추가하지 않았다.

## Related Documents

이 Patch는 PATCH-0001에서 안정화된 제품 계약을 따른다.

- `PATCH-0001-l0-and-prd-stabilization.md`
- `../docs/020_PRODUCT_REQUIREMENTS.md`
- `../docs/021_SYSTEM_CONTEXT.md`
- `../docs/030_DATA_MODEL.md`
- `../docs/031_ARCHITECTURE.md`
