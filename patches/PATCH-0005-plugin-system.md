# PATCH-0005

- Title: Plugin System
- Status: Completed
- Trigger: Completion of Edit Pipeline and the need to formalize Provider Independence
- Created: 2026-07-15

## Background

기존 Blueprint는 모든 Pipeline에서 Provider Independence를 핵심 원칙으로 유지했다. 그러나 Provider Independence가 원칙으로만 존재하고, 외부 provider와 LectureOS의 Product Concept 및 Pipeline 책임 사이의 구조적 경계는 별도 문서로 정의되지 않았다.

이 Change Set은 provider 교체 가능성을 단순 구현 선택이 아니라 Capability Contract와 Plugin Concept의 관계로 설명하고, 외부 결과가 LectureOS의 개념과 권위를 대신하지 않게 하기 위해 시작되었다.

## Trigger

- Trigger Type: Completion of Edit Pipeline and the need to formalize Provider Independence
- Source: 전체 Pipeline에서 반복된 provider 교체 가능성에 대한 공통 Blueprint 경계 필요

## Findings

### F-01 — Capability와 provider의 혼동 위험

LectureOS가 필요로 하는 역할과 그 역할을 제공하는 외부 주체를 구분하지 않으면 provider 고유 구조가 제품 계약을 대신할 수 있었다.

### F-02 — Plugin과 Pipeline의 혼동 위험

Plugin이 Pipeline 자체로 해석되면 Pipeline이 소유하는 provenance, validation, Human Review와 결과 책임이 외부 제공 수단으로 이동할 수 있었다.

### F-03 — 외부 결과의 Domain Concept 직접 승격 위험

provider-specific result가 검증 없이 canonical LectureOS Concept로 취급되면 Concept Before Component와 Source Timeline traceability가 약화될 수 있었다.

### F-04 — Plugin 교체 이후 계보 손상 위험

provider 교체나 retirement가 이전 결과, Plugin Provenance와 Human Decision의 관계를 지우지 않도록 공통 계약이 필요했다.

### F-05 — Plugin에 의한 Product Scope 확대 위험

사용 가능한 Plugin이나 Capability가 있다는 사실만으로 새로운 Product Feature가 승인된 것으로 해석될 수 있었다.

### F-06 — Blueprint Concept와 Runtime의 혼동 위험

Plugin을 곧바로 설치·로딩·실행 단위로 해석하면 아직 결정하지 않은 Architecture와 기술 선택이 Blueprint에 고정될 수 있었다.

## Goals

- Provider Independence를 Capability Contract와 Plugin Concept로 구조화한다.
- Capability, provider, Plugin, Pipeline과 Product Feature를 구분한다.
- provider-specific result와 LectureOS Concept 사이에 validation 경계를 둔다.
- Plugin 교체와 lifecycle 변화에서도 provenance와 Human Decision을 보존한다.
- Plugin Configuration, Context, Compatibility와 Capability Negotiation의 개념적 책임을 정의한다.
- 후속 Plugin 설계가 Core Product Contract와 Pipeline 책임을 침범하지 않게 한다.

## Non-Goals

- Plugin Runtime 또는 Plugin SDK
- Plugin 설치와 로딩
- package와 dependency 관리
- registry 구현과 manifest schema
- API와 통신 방식
- 실행 격리와 permission 구현
- provider adapter
- version resolution
- 새로운 Product Feature 추가

## Files

- `docs/050_PLUGIN_SYSTEM.md`

## Key Decisions

1. **Capability Is Not Provider:** Capability는 LectureOS가 필요로 하는 역할이고 provider는 그 역할을 제공할 수 있는 외부 주체다.
2. **Plugin Is Not Pipeline:** Plugin은 Capability를 제공할 수 있지만 Pipeline의 전체 책임을 소유하지 않는다.
3. **Plugin Is Not Product Feature:** Plugin의 존재나 Capability 선언은 Product Scope를 확대하지 않는다.
4. **Plugin Is Not Runtime Module:** Plugin Concept는 process, service, library 또는 배포 단위를 확정하지 않는다.
5. **Contract Before Provider:** Capability Contract가 provider와 Plugin 선택보다 먼저 존재한다.
6. **Validation Before Canonical Concept:** provider-specific result는 검증 전 canonical LectureOS Concept가 아니다.
7. **Human Authority:** Plugin은 Human Decision이나 사용자 승인의 권위를 소유하지 않는다.
8. **Configuration Preserves Meaning:** Plugin Configuration은 Capability Contract의 의미를 변경하지 않는다.
9. **Compatibility Is Not Quality or Approval:** Plugin Compatibility는 결과 품질이나 Human Approval의 보장이 아니다.
10. **Lifecycle Provenance:** Plugin 교체와 retirement 이후에도 과거 결과의 Plugin Identity와 provenance를 보존한다.
11. **Negotiation Is Not Execution:** Capability Negotiation은 설치, 실행 또는 자동 선택이 아니다.
12. **Product Before Plugin:** Product Requirements가 Capability의 필요성을 정의하고 Plugin은 이를 제공할 수 있는 선택적 수단이다.

## Scope

이 Patch는 `050_PLUGIN_SYSTEM.md`가 Provider Independence를 Plugin Concept와 Capability Contract로 구체화한 변경 이유와 결정 경계를 기록한다.

## Out of Scope

- 기존 Product Requirements와 Pipeline 범위 변경
- Plugin Runtime과 Plugin SDK
- 설치, 로딩, package와 dependency 처리
- registry와 manifest 구현
- API, protocol과 통신 방식
- 실행 격리와 permission model
- provider adapter와 특정 provider 선정
- compatibility 및 version resolution 구현
- 새로운 Product Feature 또는 Pipeline

## Constraints

- Capability와 provider를 혼합하지 않는다.
- Plugin이 Pipeline 책임이나 Domain Concept identity를 소유하지 않게 한다.
- Product Requirements보다 먼저 Plugin이 기능 범위를 확정하지 않게 한다.
- provider-specific result를 검증 없이 canonical Concept로 취급하지 않는다.
- Human Authority, Source Timeline traceability와 provenance를 유지한다.
- Plugin 교체와 lifecycle 변화가 기존 Human Decision을 손상시키지 않게 한다.
- 구현 Architecture와 Runtime을 Blueprint Concept로 확정하지 않는다.

## Acceptance Criteria

- [x] Capability와 provider가 구분되었다.
- [x] Plugin, Pipeline, Product Feature와 Runtime Module이 구분되었다.
- [x] Capability Contract가 provider보다 먼저 존재하는 계약이 정의되었다.
- [x] provider-specific result와 canonical LectureOS Concept가 구분되었다.
- [x] Plugin이 Human Authority를 소유하지 않음이 정의되었다.
- [x] Plugin Configuration이 Contract의 의미를 변경하지 않음이 정의되었다.
- [x] Plugin Compatibility와 품질·승인이 구분되었다.
- [x] 교체와 retirement 이후 provenance 보존이 정의되었다.
- [x] Capability Negotiation과 설치·실행·자동 선택이 구분되었다.
- [x] Product Requirements와 Plugin Capability의 우선 관계가 정의되었다.
- [x] Plugin Runtime과 구현 세부사항이 추가되지 않았다.
- [x] 기존 Blueprint 계약과 충돌하지 않는다.

## Completion Checklist

- [x] `050_PLUGIN_SYSTEM.md` completed
- [x] Blueprint review completed
- [x] Merge approved
- [x] Blueprint document committed
- [x] PATCH-0005 documented
- [x] PATCH-0005 self-review completed

## Result

- Status: Completed
- Changed Blueprint Files: `docs/050_PLUGIN_SYSTEM.md`
- Notes: Provider Independence가 Capability Contract와 Plugin Concept를 통해 구조화되었다.

## Related Documents

이 Patch는 PATCH-0004까지 확정된 Product, System Model과 Pipeline 책임을 기반으로 한다.

- `PATCH-0001-l0-and-prd-stabilization.md`
- `PATCH-0002-system-model.md`
- `PATCH-0003-text-pipeline.md`
- `PATCH-0004-edit-pipeline.md`
- `../docs/004_PRINCIPLES.md`
- `../docs/020_PRODUCT_REQUIREMENTS.md`
- `../docs/021_SYSTEM_CONTEXT.md`
- `../docs/030_DATA_MODEL.md`
- `../docs/031_ARCHITECTURE.md`
- `../docs/050_PLUGIN_SYSTEM.md`
