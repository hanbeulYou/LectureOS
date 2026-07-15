# Implementation Design Guide

- Status: Draft
- Baseline: LectureOS Blueprint v1
- Baseline Commit: `b0251cf56628f012891e39eebe7f57c2be63c684`
- Last Updated: 2026-07-15
- Depends On: `../docs/090_BLUEPRINT_RELEASE.md`
- Referenced By: `010_PROJECT_LIFECYCLE.md`

## Purpose

이 문서는 LectureOS Implementation Design 문서의 역할, 권위, 범위와 작성 규칙을 정의한다.

Implementation Design은 Core Blueprint v1을 실제로 구현할 수 있는 책임, 상태, 경계와 복구 규칙으로 구체화한다. 새로운 Product Contract를 만들거나 Blueprint의 Conceptual Identity와 책임 경계를 바꾸지 않는다.

## 1. Relationship to Blueprint

### 1.1 Authority

문서의 권위는 다음 순서를 따른다.

```text
Core Blueprint v1
        |
        v
Implementation Design
        |
        v
Implementation
```

- Core Blueprint는 LectureOS가 무엇을 보장하고 왜 그 책임을 갖는지 정의하는 상위 기준선이다.
- Implementation Design은 해당 계약을 어떻게 실현할지 구체화한다.
- Implementation은 승인된 Implementation Design을 코드와 운영 환경에 반영한다.
- 하위 문서는 상위 문서의 의미를 변경하거나 우회할 수 없다.

### 1.2 Conflict Rule

Implementation Design과 Blueprint가 충돌하면 Blueprint가 우선한다.

충돌이 발견되면 다음 순서를 따른다.

1. 구현 편의를 위해 Blueprint 의미를 재해석하지 않는다.
2. 충돌한 문서와 책임 경계를 기록한다.
3. 기존 Blueprint 안에서 해결 가능한지 검토한다.
4. Blueprint 변경이 필요하면 별도 PATCH를 제안한다.
5. PATCH가 승인되기 전에는 변경된 의미를 Implementation Design의 확정 사항으로 사용하지 않는다.

### 1.3 No Silent Product Decisions

Implementation Design에서 편리한 상태, 데이터 또는 component가 필요하다는 이유만으로 Product Requirement, Domain Concept, Pipeline 또는 사용자 권한을 추가하지 않는다.

새 개념이 구현 전용 보조 개념인지 Core Product Contract에 영향을 주는 개념인지 구분할 수 없다면 `Requires Blueprint Clarification`으로 남긴다.

## 2. Document Responsibilities

Implementation Design은 승인된 Blueprint 범위 안에서 다음을 정의할 수 있다.

- 실행 가능한 책임 분해
- lifecycle과 지속되는 작업 문맥
- processing boundary와 processing unit
- state와 transition의 의미
- persistent record responsibility
- interface responsibility와 신뢰 경계
- execution dependency
- failure handling과 recovery responsibility
- reprocessing과 reconciliation
- security boundary와 접근 책임
- operational constraint

각 문서는 하나의 구현 설계 질문에 집중한다. 다른 문서의 책임을 흡수하지 않고 필요한 계약을 참조한다.

## 3. Allowed Detail

Implementation Design은 필요한 경우 다음 수준까지 구체화할 수 있다.

### 3.1 Logical Responsibility

- Blueprint의 논리 component를 더 작은 실행 책임으로 나누기
- 책임 사이의 입력 전제와 결과 책임 설명
- 장기 Domain Record와 임시 실행 정보 구분

### 3.2 State and Transition

- 상태가 설명하는 대상과 의미
- 상태 전이가 가능한 조건
- 상태 전이의 주체와 권위
- 부분 성공, 실패, 복구와 재검토 조건

상태 목록은 필요한 문서에서만 정의하며, 서로 다른 대상의 상태를 하나의 전역 상태로 합치지 않는다.

### 3.3 Processing and Persistence

- 처리 단위와 재실행 경계
- 결과가 지속되어야 하는 책임
- provenance와 사용자 결정을 보존하는 책임
- 재처리 결과와 기존 결과의 reconciliation 책임

### 3.4 Interface and Security Boundary

- 어떤 책임이 어떤 정보에 접근해야 하는가?
- 시스템 또는 신뢰 경계를 넘는 데이터는 무엇인가?
- 호출 성공, 실패와 불확실성을 누가 해석하는가?
- 외부 결과를 LectureOS Concept로 받아들이기 전에 무엇을 검증해야 하는가?

구체적인 payload와 protocol은 별도 승인 전에는 정의하지 않는다.

## 4. Still Prohibited

별도 승인 전까지 Implementation Design에서 다음을 확정하지 않는다.

- 특정 database 또는 storage vendor
- 특정 cloud와 managed service
- 특정 queue, scheduler 또는 worker 기술
- 특정 framework 또는 programming language
- 특정 provider SDK
- 구체적인 API payload
- 구체적인 database 또는 message schema
- 배포 topology와 process 배치
- 구체적인 성능 수치와 자원 사양
- 기술 스택 선정
- 구현 코드와 package 구조

이 제한은 책임과 경계를 설계하지 말라는 뜻이 아니다. 기술 선택을 책임 설계보다 먼저 고정하지 말라는 뜻이다.

## 5. Document System

### 5.1 Location

Implementation Design 문서는 `implementation/`에 둔다. Core Blueprint가 있는 `docs/`와 변경 이유를 기록하는 `patches/`에 섞지 않는다.

### 5.2 Numbering

- `000`: Implementation Design 작성 기준
- `010~099`: lifecycle, execution, storage, interface와 같은 핵심 구현 설계
- 이후 번호는 승인된 설계 순서와 의존성에 따라 배정한다.

번호가 Product Scope나 Architecture layer를 뜻하지는 않는다.

### 5.3 Metadata

각 문서는 최소한 다음을 표시한다.

- Status
- Baseline
- Last Updated
- Depends On
- Referenced By

필요하면 `Supersedes` 또는 `Requires Blueprint Clarification`을 추가할 수 있다. 메타데이터는 구현 schema가 아니라 문서 관계를 설명한다.

### 5.4 Status

- **Draft:** 작성 중이며 구현 기준선으로 승인되지 않은 상태
- **In Review:** 책임, 경계와 Blueprint 일관성을 검토하는 상태
- **Approved:** 현재 구현 설계 기준선으로 사용할 수 있는 상태
- **Superseded:** 더 최신의 승인 문서가 책임을 대신하는 상태

문서 Status는 Project State나 Processing State가 아니다.

## 6. Required Sections

각 Implementation Design 문서는 필요한 범위에서 다음을 포함한다.

1. Purpose
2. Blueprint Basis
3. Scope and Non-Goals
4. Responsibilities
5. State or Lifecycle Model
6. Failure and Recovery
7. Persistence or Interface Responsibility
8. Security and Trust Boundary
9. Assumptions and Open Questions
10. Blueprint Boundary Check
11. Validation Criteria
12. Related Documents

문서 성격에 맞지 않는 절은 생략할 수 있지만, Blueprint 경계와 미결정 사항은 반드시 드러낸다.

## 7. Decision Classification

Implementation Design의 판단은 다음과 같이 구분한다.

- **Confirmed by Blueprint:** 상위 Blueprint가 이미 확정한 계약
- **Implementation Decision:** Blueprint 의미를 바꾸지 않는 구현 책임 결정
- **Working Assumption:** 설계를 진행하기 위해 임시로 사용하는 가정
- **Requires Validation:** 구현이나 실제 사용 전에 검증해야 하는 판단
- **Requires Blueprint Clarification:** 상위 계약의 의미가 불충분하거나 충돌해 하위 문서에서 확정할 수 없는 사항
- **Deferred:** 현재 문서에서 의도적으로 다루지 않는 사항

`Requires Blueprint Clarification`을 Implementation Decision으로 바꾸려면 관련 Blueprint 근거 또는 승인된 PATCH가 필요하다.

## 8. Naming and Concept Reuse

- Blueprint에 정의된 Concept 이름을 우선 사용한다.
- 구현 보조 개념은 Blueprint Concept와 구분해 설명한다.
- 같은 이름으로 다른 책임을 만들지 않는다.
- Project State, Processing State, Review Decision과 Export Readiness처럼 대상이 다른 상태를 혼합하지 않는다.
- component 이름이 Domain Concept의 identity나 data ownership을 암시하지 않게 한다.
- `owns`를 사용할 때는 논리적 처리 책임인지 지속 기록 책임인지 명시한다.

## 9. State Design Rules

- 상태는 어떤 대상의 상태인지 이름에 드러내야 한다.
- lifecycle state와 processing state를 구분한다.
- validation, review readiness, approval과 artifact availability를 하나의 상태로 합치지 않는다.
- 부분 성공을 하나의 성공·실패 값으로 축소하지 않는다.
- 실패가 다른 유효한 결과를 근거 없이 무효화하지 않게 한다.
- 전이는 provenance와 이전 Human Decision을 조용히 삭제하지 않는다.
- 고정 상태 목록이 필요한지는 해당 문서에서 근거와 함께 결정한다.

## 10. Persistence Design Rules

Implementation Design은 저장 기술보다 먼저 다음을 설명해야 한다.

- 실행이 끝난 뒤에도 남아야 하는 기록은 무엇인가?
- 어떤 기록이 원본, 사용자 결정과 승인 결과를 보호하는가?
- 어떤 정보가 임시 실행 정보인가?
- 재처리 전후의 결과와 provenance를 어떻게 구분해야 하는가?
- Artifact 손실이 Domain Record 손실로 이어지지 않게 하는 책임은 무엇인가?

이 문서는 구체적인 저장 형태, key, index 또는 transaction 방식을 정하지 않는다.

## 11. Review Checklist

Implementation Design을 승인하기 전에 다음을 확인한다.

- Core Blueprint v1과 충돌하지 않는가?
- 기존 Conceptual Identity와 책임 경계를 바꾸지 않는가?
- 새로운 Product Requirement나 Pipeline을 암묵적으로 추가하지 않는가?
- 구현 보조 개념과 Blueprint Concept를 구분했는가?
- Human Authority와 Source Timeline traceability를 유지하는가?
- provenance, safe reprocessing과 부분 실패를 다루는가?
- 기술 선택이 책임 설계보다 먼저 확정되지 않았는가?
- 미결정 사항을 임의로 확정하지 않았는가?
- Blueprint 변경이 필요하면 별도 PATCH 필요성을 표시했는가?

## 12. Change Policy

- 의미를 바꾸지 않는 명확화는 해당 Implementation Design 문서에서 Review한다.
- 승인된 Implementation Decision을 바꾸면 영향받는 문서와 구현 책임을 함께 검토한다.
- Core Blueprint 의미나 책임 경계에 영향이 있으면 Blueprint PATCH를 먼저 제안한다.
- Implementation Design은 PATCH를 대신하거나 Core Blueprint Release 기준선을 수정하지 않는다.

## Non-Goals

이 Guide는 다음을 정의하지 않는다.

- 개별 Project의 lifecycle
- Pipeline 실행 순서
- 저장 모델과 interface 계약
- 기술 스택과 구현 구조
- 구현 일정과 roadmap
- 새로운 Product Feature

## Related Documents

- [Blueprint v1 Release](../docs/090_BLUEPRINT_RELEASE.md)
- [Product Requirements](../docs/020_PRODUCT_REQUIREMENTS.md)
- [Conceptual Data Model](../docs/030_DATA_MODEL.md)
- [Logical Architecture](../docs/031_ARCHITECTURE.md)
- [Project Lifecycle](./010_PROJECT_LIFECYCLE.md)
