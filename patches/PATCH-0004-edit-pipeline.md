# PATCH-0004

- Title: Edit Pipeline
- Status: In Progress
- Trigger: Completion of Lecture Intelligence Pipeline
- Created: 2026-07-15

## Background

PATCH-0001은 Text Pipeline과 Edit Pipeline을 동등한 제품 핵심으로 확정했고, PATCH-0002와 PATCH-0003은 System Model과 Text Pipeline을 구체화했다. 그러나 Edit Pipeline에는 강의 분석, Human Review와 승인된 편집 결정의 외부 전달을 서로 다른 책임으로 정의하는 Blueprint가 아직 완성되지 않았다.

이 Change Set은 Lecture Intelligence, Review와 Export의 경계를 순서대로 정의해 Analysis Finding과 Edit Candidate가 인간의 결정과 외부 Artifact로 발전하는 동안 각 개념의 권위와 provenance를 보존하기 위해 시작되었다.

현재 완료된 범위는 `042_LECTURE_INTELLIGENCE_PIPELINE.md`뿐이다. `043_REVIEW_PIPELINE.md`와 `044_EXPORT_PIPELINE.md`는 아직 작성되지 않았으며, 완료될 때 이 Patch를 계속 갱신한다.

## Trigger

- Trigger Type: Completion of Lecture Intelligence Pipeline
- Source: PATCH-0003 이후 Edit Pipeline의 분석·결정·전달 책임 분리 필요

## Findings

### F-01 — Analysis와 Editing의 분리 필요

강의 구조와 전달 신호를 분석하는 책임이 실제 편집이나 자동 삭제로 해석되지 않도록 Analysis Finding과 Edit Candidate의 경계를 명확히 해야 했다.

### F-02 — Candidate와 Human Decision의 분리 필요

Edit Candidate는 분석이 제안한 Review 대상이며, 사용자의 Accept, Reject, Modify를 거친 Approved Edit Decision과 동일하지 않다.

### F-03 — Decision과 Artifact의 분리 필요

Approved Edit Decision은 외부 편집에 사용할 사용자 결정이지만 그 자체로 export Artifact나 실제 컷은 아니다. Review와 Export의 후속 책임을 별도 Blueprint로 정의해야 한다.

### F-04 — 재분석 이후 결정 계보 보존 필요

새 Analysis Finding과 Edit Candidate가 생성되어도 이전 Review 이력과 사용자 결정이 삭제되거나 모호해지지 않는 Edit Pipeline 계약이 필요하다.

## Goals

- Source Timeline 기반 Lecture Intelligence의 분석 책임을 정의한다.
- Lecture Segment, Analysis Finding과 Edit Candidate를 구분한다.
- Human Review가 Candidate를 Decision으로 발전시키는 책임을 정의한다.
- Approved Edit Decision과 export Artifact를 구분한다.
- Analysis, Candidate, Decision과 Artifact의 provenance를 유지한다.
- 재분석과 재처리에서 사용자 결정의 권위를 보존한다.
- provider와 외부 NLE에 독립적인 Edit Pipeline 계약을 완성한다.

## Non-Goals

- Source Media 변경과 실제 영상 편집
- 자동 컷 적용과 자동 삭제
- Transcript 또는 Subtitle 생성과 수정
- 데이터베이스, API와 저장 구조
- runtime, deployment와 기술 스택
- 특정 AI provider 또는 NLE 선정
- FCPXML과 외부 편집 round trip

## Files

- `docs/042_LECTURE_INTELLIGENCE_PIPELINE.md`

`docs/043_REVIEW_PIPELINE.md`와 `docs/044_EXPORT_PIPELINE.md`는 아직 이 Patch의 완료된 Files에 포함되지 않는다.

## Key Decisions

1. **Analysis Is Not Editing:** Lecture Intelligence는 강의를 이해하고 설명하지만 Source Media나 승인된 기록을 변경하지 않는다.
2. **Analysis Is the Parent Concept:** Lecture Segment는 Analysis 결과를 표현하는 하나의 선택적 개념이며 모든 Finding의 필수 전제가 아니다.
3. **Finding Is Not Candidate:** Analysis Finding은 설명적 또는 해석적 결과이며 Edit Candidate 없이 존재할 수 있다.
4. **Candidate Is Not Decision:** Edit Candidate는 사람이 검토할 제안이고 Approved Edit Decision이나 실제 컷이 아니다.
5. **Human Authority:** 분석 결과와 confidence는 사용자 판단을 대신하지 않는다.
6. **Explainability:** Finding과 Candidate는 적용 가능한 근거, rationale과 Uncertainty를 검토할 수 있어야 한다.
7. **Provider Independence:** provider 고유 결과를 canonical LectureOS concept로 사용하지 않는다.
8. **Source Timeline Traceability:** 시간 기반 분석 결과와 Candidate는 Source Timeline으로 추적 가능해야 한다.
9. **Safe Reprocessing:** 재분석은 새 결과를 만들 수 있지만 기존 Review 이력과 사용자 결정을 삭제하거나 자동 변경하지 않는다.
10. **Decision Is Not Artifact:** Review Decision과 Approved Edit Decision은 외부 Artifact와 실제 편집 결과가 아니다.

## Scope

현재 Patch 범위는 Merge 가능한 상태로 승인된 `042_LECTURE_INTELLIGENCE_PIPELINE.md`의 변경 이유와 확정 결정을 기록한다.

향후 `043_REVIEW_PIPELINE.md`와 `044_EXPORT_PIPELINE.md`가 완료되면 Human Review, Approved Edit Decision과 Artifact 전달에 관한 Change Set을 이 Patch에 추가한다.

## Out of Scope

- 아직 작성되지 않은 `043_REVIEW_PIPELINE.md`의 결정을 완료된 것으로 기록하는 것
- 아직 작성되지 않은 `044_EXPORT_PIPELINE.md`의 결정을 완료된 것으로 기록하는 것
- PATCH-0001~0003 또는 기존 Blueprint의 계약 변경
- 구현 코드와 기술 선정
- 실제 NLE 편집과 rendering

## Constraints

- Text Pipeline과 Edit Pipeline을 동등한 핵심 범위로 유지한다.
- Analysis Finding, Edit Candidate, Review Decision, Approved Edit Decision과 Artifact를 혼합하지 않는다.
- Source Media와 Source Timeline을 변경하지 않는다.
- Human Review Authority를 provider 결과보다 우선한다.
- 재분석과 재처리가 기존 사용자 결정을 손상시키지 않게 한다.
- 자동 컷 적용, FCPXML과 외부 편집 round trip을 범위에 추가하지 않는다.
- Blueprint와 PATCH의 책임을 구분한다.

## Acceptance Criteria

- [x] Lecture Intelligence Pipeline이 정의되었다.
- [x] Analysis와 Editing이 구분되었다.
- [x] Lecture Segment, Analysis Finding과 Edit Candidate가 구분되었다.
- [x] Explainability와 provider independence가 정의되었다.
- [x] Source Timeline traceability와 safe reprocessing이 정의되었다.
- [ ] Review Pipeline이 정의되었다.
- [ ] Human Review Decision과 Approved Edit Decision의 관계가 정의되었다.
- [ ] Export Pipeline이 정의되었다.
- [ ] Approved Edit Decision과 Artifact의 전달 경계가 정의되었다.
- [ ] Edit Pipeline 전체가 상위 Blueprint와 일관되는지 최종 검토되었다.

## Completion Checklist

- [x] `042_LECTURE_INTELLIGENCE_PIPELINE.md` completed
- [x] 042 final review completed
- [x] 042 Product Owner approval completed
- [x] 042 committed
- [ ] `043_REVIEW_PIPELINE.md` completed
- [ ] 043 final review completed
- [ ] `044_EXPORT_PIPELINE.md` completed
- [ ] 044 final review completed
- [ ] PATCH-0004 final review completed
- [ ] PATCH-0004 marked Completed
- [ ] Edit Pipeline changes committed

## Result

- Status: In Progress
- Changed Blueprint Files: `docs/042_LECTURE_INTELLIGENCE_PIPELINE.md`
- Notes: Lecture Intelligence Pipeline이 완료되었다. Review Pipeline과 Export Pipeline은 아직 작성되지 않았으며, 완료 시 PATCH-0004를 갱신한다.

## Related Documents

이 Patch는 PATCH-0002의 System Model과 PATCH-0003의 Pipeline 책임 분리를 기반으로 한다.

- `PATCH-0001-l0-and-prd-stabilization.md`
- `PATCH-0002-system-model.md`
- `PATCH-0003-text-pipeline.md`
- `../docs/020_PRODUCT_REQUIREMENTS.md`
- `../docs/030_DATA_MODEL.md`
- `../docs/031_ARCHITECTURE.md`
- `../docs/042_LECTURE_INTELLIGENCE_PIPELINE.md`
