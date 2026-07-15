# PATCH-0003

- Title: Text Pipeline
- Status: Completed
- Trigger: Completion of System Model
- Created: 2026-07-15

## Background

PATCH-0002의 System Model은 LectureOS의 경계, 핵심 개념과 논리적 처리 책임을 정의했다. 이후 Text Pipeline의 실제 Blueprint 책임을 명확히 하기 위해 Transcript와 Subtitle 흐름을 각각 `040_TRANSCRIPT_PIPELINE.md`와 `041_SUBTITLE_PIPELINE.md`로 구체화했다.

이 Patch는 이미 Merge된 두 Pipeline 문서가 Raw Transcript에서 Corrected Transcript로, 다시 Final Subtitle로 이어지는 Text Pipeline의 Change Set을 형성하게 된 이유와 확정 사항을 기록한다.

## Trigger

- Trigger Type: Completion of System Model
- Source: System Model 이후 Merge된 Text Pipeline 문서

## Findings

### F-01 — Transcript와 Subtitle Pipeline 책임 분리 필요

Transcript의 의미 교정과 Subtitle의 시청 표현을 같은 처리로 다루면 raw 결과, corrected 의미와 자막 표현의 계보가 섞일 위험이 있었다.

### F-02 — Validation과 의미 판단의 분리 필요

시간, 순서, 누락과 구조적 유효성을 검증하는 책임이 AI의 의미 제안이나 사용자 판단을 대신하지 않도록 명확한 Pipeline 계약이 필요했다.

### F-03 — 재처리 후 사용자 결정 보존 필요

ASR, correction 또는 Subtitle 기준이 바뀔 때 기존 Review Decision과 Modification이 새 후보에 자동 적용되거나 유실되지 않도록 공통 제약이 필요했다.

## Goals

- Source Media에서 Raw Transcript와 Corrected Transcript로 이어지는 Transcript Pipeline을 정의한다.
- Corrected Transcript에서 Final Subtitle로 이어지는 Subtitle Pipeline을 정의한다.
- 단계별 구조적 Validation 책임을 정의한다.
- 공통 Review와 Accept, Reject, Modify 연결을 정의한다.
- raw, corrected, candidate, revision과 사용자 결정의 provenance를 유지한다.
- 실패와 부분 재처리의 처리 원칙을 정의한다.

## Non-Goals

- Edit Pipeline과 Lecture Intelligence
- Artifact 생성과 외부 export
- 실제 영상 편집과 렌더링
- FCPXML과 외부 편집 round trip
- 데이터베이스와 저장 schema
- API와 통신 형식
- runtime과 deployment
- 기술 스택, provider와 구체적인 처리 방법 선정

## Files

- `docs/040_TRANSCRIPT_PIPELINE.md`
- `docs/041_SUBTITLE_PIPELINE.md`

## Key Decisions

1. **Transcript Is Not Subtitle:** Transcript는 발화 의미를 보존·교정하는 계층이고 Subtitle은 시청을 위한 표현이다.
2. **Raw Is Not Corrected:** Raw Transcript는 provider의 변경 전 결과이며 Corrected Transcript가 이를 덮어쓰지 않는다.
3. **Subtitle Is Not Artifact:** Final Subtitle은 중심 Subtitle 표현이고 SRT 같은 Artifact는 그로부터 재생성되는 외부 결과다.
4. **Validation Is Not Meaning:** 구조적 Validation은 시간, 순서, 누락, 표현 무결성을 확인하지만 의미 정확성이나 사용자 판단을 대신하지 않는다.
5. **Reading Representation:** 가독성을 위한 분할과 표시 표현은 Transcript 교정과 분리된 Subtitle 책임이다.
6. **Time Representation:** Subtitle의 시간 표현은 Source Timeline으로 추적되며 AI의 의미 제안이 최종 시간 구조를 직접 확정하지 않는다.
7. **Final Subtitle:** Review와 사용자 결정을 반영해 Artifact Generation에 사용할 수 있는 승인 상태의 Subtitle 표현이다.
8. **Provenance:** Source Media, Raw Transcript, Corrected Transcript, Subtitle revision, 후보와 Review Decision의 계보를 유지한다.
9. **Safe Reprocessing:** 새 처리 결과는 기존 사용자 결정과 Modification을 삭제하거나 새 후보에 자동 적용하지 않는다.

## Scope

이 Patch는 위 두 문서가 정의한 Transcript Pipeline과 Subtitle Pipeline을 하나의 Text Pipeline Change Set으로 기록한다.

## Out of Scope

- `042` Lecture Intelligence Pipeline
- `043` Review Pipeline
- `044` Export Pipeline
- PATCH-0001 또는 PATCH-0002 계약 변경
- 구현 코드와 기술 선정

## Constraints

- Raw Transcript, Corrected Transcript와 Subtitle 책임을 혼합하지 않는다.
- Source Media와 Source Timeline의 추적성을 유지한다.
- Review를 자동 승인이나 읽기 전용 Report로 축소하지 않는다.
- 구조적 Validation을 의미 판단으로 확대하지 않는다.
- 재처리에서 사용자 Review Decision과 Modification을 보존한다.

## Acceptance Criteria

- [x] Transcript Pipeline이 정의되었다.
- [x] Subtitle Pipeline이 정의되었다.
- [x] 각 Pipeline의 구조적 Validation이 정의되었다.
- [x] 공통 Review와 Accept, Reject, Modify 연결이 정의되었다.
- [x] provenance, failure와 reprocessing 계약이 정의되었다.
- [x] Review 및 Export를 위한 downstream 계약이 정의되었다.
- [x] PATCH-0001과 System Model의 계약을 유지한다.

## Completion Checklist

- [x] Transcript Pipeline completed
- [x] Subtitle Pipeline completed
- [x] Review refinements applied
- [x] Blueprint documents committed
- [x] Patch documentation backfilled

## Result

- Status: Completed
- Changed Blueprint Files: `docs/040_TRANSCRIPT_PIPELINE.md`, `docs/041_SUBTITLE_PIPELINE.md`
- Notes: 이미 Merge된 Text Pipeline의 결정과 범위를 기록했다. 새로운 Pipeline 또는 구현 결정을 추가하지 않았다.

## Related Documents

이 Patch는 PATCH-0002의 System Model을 기반으로 한다.

- `PATCH-0001-l0-and-prd-stabilization.md`
- `PATCH-0002-system-model.md`
- `../docs/020_PRODUCT_REQUIREMENTS.md`
- `../docs/030_DATA_MODEL.md`
- `../docs/031_ARCHITECTURE.md`
- `../docs/040_TRANSCRIPT_PIPELINE.md`
- `../docs/041_SUBTITLE_PIPELINE.md`
