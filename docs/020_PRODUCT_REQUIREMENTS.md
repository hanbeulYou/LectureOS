# LectureOS Product Requirements

- Status: Draft
- Version: Blueprint 0.1
- Last Updated: 2026-07-13
- Layer: L1 — Product
- Depends On:
  - `000_MANIFESTO.md`
  - `001_PRODUCT.md`
  - `002_FAQ.md`
  - `003_VISION.md`
  - `004_PRINCIPLES.md`
- Referenced By:
  - `021_SYSTEM_CONTEXT.md`
  - `022_WORKFLOW.md`
  - `030_DATA_MODEL.md`

## Purpose

이 문서는 LectureOS가 사용자에게 제공해야 하는 기능과 책임을 정의한다. 구현 방법, 데이터 구조, 모델 선정, UI 기술을 정의하지 않는다.

## 1. Product Goal

### Primary Goal

강의 한 편의 전체 후반작업 시간을 현재 방식 대비 절반 이하로 줄이는 것을 **Working Target**으로 둔다.

이 수치는 승인된 고정 성능 약속이 아니라 **Requires Validation** 상태다. 현재 방식의 기준선, 측정 시작·종료점, 대표 강의 자료를 확정한 뒤 검증한다.

### Equal Core Outcomes

LectureOS는 다음 두 결과를 동등한 핵심으로 다룬다.

1. **Text Pipeline**: 인식 오류를 교정하고 학생이 읽기 좋은 Subtitle을 준비해 Final Cut에서의 자막 수정을 최소화한다.
2. **Edit Pipeline**: 강의 구간을 분석하고 컷편집용 라벨과 Edit Candidate를 준비해 편집 후보 검토 시간을 줄인다.

한 파이프라인을 다른 파이프라인의 부가기능이나 장기 확장으로 축소하지 않는다.

### Success Criteria

- Final Cut에서 수정하는 자막량 감소
- 긴 자막의 수동 분할 감소
- 자막 타이밍 수정 감소
- 잘못된 인식과 불확실한 변경의 검수 시간 감소
- 컷편집 후보를 찾고 검토하는 시간 감소
- 전체 영상을 처음부터 균일한 집중도로 재생해야 하는 필요 감소
- 승인된 자막과 편집 결정의 재사용 및 재실행 후 보존

## 2. Current Workflow

현재 사용자는 다음 흐름에서 자막 수정과 컷편집을 동시에 수행한다.

~~~text
원본 영상
→ 초안 SRT
→ Final Cut
→ 컷편집과 자막 수정 동시 수행
~~~

현재 문제:

- 자막 인식 오류가 많다.
- 타이밍 수정이 많다.
- 긴 자막과 잘못된 줄바꿈을 Final Cut에서 직접 고친다.
- 삭제하거나 검토할 구간을 사람이 끝까지 보며 찾는다.
- 자막과 편집 결정이 분리되어 같은 구간을 반복 확인한다.

## 3. Target Workflow

목표 흐름에서는 자막과 편집 후보를 LectureOS 안에서 먼저 검수한다.

~~~text
원본 영상
→ LectureOS 분석·교정·라벨링·검수
→ 승인된 자막과 편집 결정
→ Final Cut에서 화면 편집과 최종 확인
~~~

LectureOS는 텍스트와 편집 후보의 준비·검수·결정 보존을 담당한다. Final Cut은 화면 편집과 최종 확인, 렌더링을 담당한다.

## 4. Core Pipelines

### 4.1 Text Pipeline

~~~text
Media
→ ASR
→ Correction
→ Subtitle Generation
→ Integrated Review
→ Final Subtitle/SRT
~~~

목표:

- 인식 오류 감소
- 자막 정확성과 가독성 향상
- 위험한 텍스트 변경의 우선 검수
- Final Cut에서의 대량 자막 수정 방지

### 4.2 Edit Pipeline

~~~text
Media
→ Lecture Intelligence
→ Segment Labeling
→ Edit Candidate
→ Integrated Review
→ Approved Edit Decisions
~~~

목표:

- 컷편집용 구간 라벨 생성
- 유지·삭제·검토 후보 제안
- 교육적 판단이 필요한 후보의 우선 검수
- 승인된 편집 결정 보존

자동 삭제가 아니라 설명 가능한 후보 생성과 사람의 결정을 기본으로 한다. Lecture Intelligence의 분석 계층과 Analysis Finding 계약은 `042_LECTURE_INTELLIGENCE_PIPELINE.md`가 정의한다.

## 5. Functional Requirements

모든 Must 요구사항은 V1 핵심 범위다.

### 5.1 Media Ingestion Requirements

- **MIR-001 — Must:** 영상 또는 오디오 입력을 받아야 한다.
- **MIR-002 — Must:** 2시간 이상의 장시간·대용량 입력을 처리할 수 있어야 한다.
- **MIR-003 — Must:** 원본 미디어를 변경하거나 덮어쓰지 않아야 한다.
- **MIR-004 — Must:** 후속 처리를 위한 오디오를 추출할 수 있어야 한다.
- **MIR-005 — Must:** 비용이 큰 중간 산출물을 단계별로 재사용할 수 있어야 한다.
- **MIR-006 — Must:** 실패한 단계부터 안전하게 다시 실행할 수 있어야 한다.

### 5.2 ASR Requirements

- **ASR-001 — Must:** 한국어 장시간 교육 강의를 우선 지원해야 한다.
- **ASR-002 — Must:** 특정 모델에 종속되지 않도록 ASR backend를 교체할 수 있어야 한다.
- **ASR-003 — Must:** 원본 시간축과 연결된 발화 또는 단어 수준 시간 정보를 제공해야 한다.
- **ASR-004 — Must:** ASR이 생성한 raw 결과와 출처를 보존해야 한다.
- **ASR-005 — Must:** 제공 가능한 confidence 또는 불확실성 정보를 보존하고 노출해야 한다.
- **ASR-006 — Must:** 장시간 처리 실패 후 완료된 작업을 잃지 않고 재개할 수 있어야 한다.

원본 시간축 기반 데이터의 정확한 명칭과 최소 단위는 Glossary와 Data Model에서 확정한다.

### 5.3 Correction Requirements

- **COR-001 — Must:** ASR 인식 오류의 교정 후보를 생성할 수 있어야 한다.
- **COR-002 — Must:** 고유명사와 전문용어의 교정 후보를 다룰 수 있어야 한다.
- **COR-003 — Must:** 숫자 변경을 별도의 위험한 변경으로 검수할 수 있어야 한다.
- **COR-004 — Must:** raw 인식문과 corrected Transcript를 분리해 보존해야 한다.
- **COR-005 — Must:** LLM이 제안한 결과의 형식과 구조적 유효성을 코드로 검증해야 한다.
- **COR-006 — Must:** LLM이 최종 타임스탬프를 직접 생성하거나 변경하지 않아야 한다.
- **COR-007 — Must:** 근거가 부족하거나 불확실한 수정을 자동 확정하지 않고 Review Item으로 보내야 한다.
- **COR-008 — Must:** 사용자가 승인·거절·수정한 교정 결정을 재실행 후에도 보존해야 한다.

### 5.4 Subtitle Requirements

- **SUB-001 — Must:** ASR이 제공한 구간을 최종 Subtitle cue로 그대로 사용하지 않아야 한다.
- **SUB-002 — Must:** 지나치게 긴 자막을 다시 분할할 수 있어야 한다.
- **SUB-003 — Must:** Subtitle은 최대 2줄 제약을 지원해야 한다.
- **SUB-004 — Must:** 읽기 속도 제약을 적용하고 위반을 Review Item으로 제시해야 한다.
- **SUB-005 — Must:** 최대 표시 시간 제약을 적용하고 위반을 Review Item으로 제시해야 한다.
- **SUB-006 — Must:** 발화 호흡과 의미 단위를 고려해 분할 후보를 만들어야 한다.
- **SUB-007 — Must:** 줄바꿈과 분할 오류를 검수 대상으로 제시해야 한다.
- **SUB-008 — Must:** 시작·종료 역전, 음수 시간, 0 duration, 순서 오류, 겹침 등 타임스탬프 구조를 코드로 검증해야 한다.
- **SUB-009 — Must:** 원본 시간축 연결을 바탕으로 Final Cut에서 사용할 최종 SRT를 출력해야 한다.

읽기 속도, 최대 표시 시간, 글자 수 등 구체적인 임계값은 **Requires Validation**이며 후속 명세에서 확정한다.

### 5.5 Lecture Intelligence Requirements

Lecture Intelligence는 최소한 다음 구간을 분석하고 컷편집용 라벨 후보를 생성해야 한다.

- **LI-001 — Must:** 수업 시작 전
- **LI-002 — Must:** 수업 종료 후
- **LI-003 — Must:** 쉬는 시간
- **LI-004 — Must:** 긴 무음
- **LI-005 — Must:** 학생 잡담
- **LI-006 — Must:** 선생님 잡담
- **LI-007 — Must:** 장비 문제
- **LI-008 — Must:** 교재 찾는 시간
- **LI-009 — Must:** 판서 대기
- **LI-010 — Must:** 반복 설명 후보
- **LI-011 — Must:** 말실수 또는 다시 말한 구간
- **LI-012 — Must:** 교육적 가치가 낮을 가능성이 있는 구간

분류 결과는 자동 삭제 명령이 아니다. 반복 설명, 선생님의 개성, 교육적 예시와 교육적 가치가 불명확한 구간은 보수적으로 처리하고 Review Item으로 제시해야 한다.

### 5.6 Edit Candidate Requirements

각 Edit Candidate는 최소한 다음 정보를 제공해야 한다.

- **EC-001 — Must:** 원본 시간 구간
- **EC-002 — Must:** 구간 라벨
- **EC-003 — Must:** 유지·삭제·검토 추천
- **EC-004 — Must:** confidence 또는 불확실성
- **EC-005 — Must:** 추천 이유
- **EC-006 — Must:** 예상 절감 시간
- **EC-007 — Must:** Review 상태

추가 요구사항:

- **EC-008 — Must:** Edit Candidate는 원본 시간축과 추적 가능해야 한다.
- **EC-009 — Must:** 교육적 가치가 불명확하면 자동 삭제하지 않고 검토를 추천해야 한다.
- **EC-010 — Must:** 사용자의 승인 없이 고위험 편집 후보를 자동 적용하지 않아야 한다.

### 5.7 Integrated Review Requirements

Review는 자막 오류와 Edit Candidate를 한 흐름에서 다뤄야 한다.

V1은 다음 사용자 동작과 원본 구간 확인을 실제로 수행할 수 있는 최소 Review Interface를 제공해야 한다. 구체적인 UI 기술이나 프레임워크는 이 요구사항에서 정의하지 않는다.

Review 대상:

- ASR 인식 오류
- 고유명사·전문용어 변경
- 숫자 변경
- 낮은 confidence 또는 불확실성
- 타이밍 이상
- 지나치게 긴 자막
- 줄바꿈·분할 오류
- 삭제 후보
- 편집 구간 라벨
- 애매한 잡담과 교육적 판단이 필요한 구간

사용자 동작:

- **REV-001 — Must:** 자막 변경과 Edit Candidate를 Accept할 수 있어야 한다.
- **REV-002 — Must:** 자막 변경과 Edit Candidate를 Reject할 수 있어야 한다.
- **REV-003 — Must:** 자막 변경과 Edit Candidate를 Modify할 수 있어야 한다.
- **REV-004 — Must:** 관련 원본 오디오 또는 영상 구간을 확인할 수 있어야 한다.
- **REV-005 — Must:** 위험도와 우선순위에 따라 Review Item을 확인할 수 있어야 한다.
- **REV-006 — Must:** 수정 이력과 현재 결정 상태를 확인할 수 있어야 한다.
- **REV-007 — Must:** 사용자 결정과 승인된 편집 결정을 재실행 후에도 보존해야 한다.
- **REV-008 — Must:** Accept, Reject, Modify와 관련 원본 미디어 확인을 수행할 수 있는 최소 Review Interface를 제공해야 한다.

Review의 목표는 원본 확인을 금지하는 것이 아니다. 위험 구간을 우선 제시해 전체 영상을 처음부터 재생해야 하는 필요를 줄이는 것이다.

### 5.8 Required Outputs

LectureOS는 최소한 다음 결과를 제공해야 한다.

- **OUT-001 — Must:** raw transcript
- **OUT-002 — Must:** corrected transcript
- **OUT-003 — Must:** final subtitle/SRT
- **OUT-004 — Must:** edit candidates
- **OUT-005 — Must:** review items
- **OUT-006 — Must:** approved edit decisions
- **OUT-007 — Must:** processing log
- **OUT-008 — Must:** 향후 Timeline 연결에 필요한 안정적 식별자
- **OUT-009 — Must:** approved edit decisions를 원본 시간 구간, 구간 라벨, 결정 상태와 함께 사람이 읽을 수 있거나 기계가 읽을 수 있는 형태로 내보낼 수 있어야 한다.

모든 필수 출력은 가능한 범위에서 원본 시간축, 생성 근거, 사용자 결정과 추적 가능해야 한다.
OUT-009의 구체적인 스키마와 외부 편집 도구 포맷은 이 문서에서 정의하지 않는다.

## 6. Product Boundary

### LectureOS Responsibilities

- 음성 인식
- 텍스트 교정
- 자막 생성·분할·타이밍
- 강의 구간 분석
- 컷편집용 라벨링
- Edit Candidate 생성
- 자막·편집 통합 Review
- 승인된 편집 결정 저장
- 최종 자막 산출

### Final Cut Responsibilities

- 크롭
- 확대·축소
- 회전
- 위치 조정
- 색보정
- 복잡한 시각 편집
- 최종 컷 확인
- 렌더링

현재 핵심 사용 환경에서 Final Cut은 화면 편집과 최종 확인에 사용한다. 특정 편집 도구는 LectureOS의 영구 제품 정체성이 아니다.

## 7. Non-functional Requirements

- **NFR-001 — Must:** 원본 미디어와 원본 시간축 연결을 보존해야 한다.
- **NFR-002 — Must:** 필요한 단계만 다시 실행할 수 있어야 한다.
- **NFR-003 — Must:** 중간 산출물을 캐시하고 입력이나 조건 변경 시 필요한 결과를 다시 만들 수 있어야 한다.
- **NFR-004 — Must:** 실패 후 완료된 단계를 잃지 않고 재개할 수 있어야 한다.
- **NFR-005 — Must:** 특정 ASR, LLM, alignment 모델에 종속되지 않아야 한다.
- **NFR-006 — Must:** 실패, 오류, 누락, 불확실성을 정상 결과처럼 숨기지 않아야 한다.
- **NFR-007 — Must:** 사용자의 교정과 편집 결정을 보존해야 한다.
- **NFR-008 — Must:** 2시간 이상의 대용량 강의 영상을 지원해야 한다.

### Local-first Decision Status

local-first는 현재 핵심 사용 사례를 위한 **Working Assumption**이자 전략적 기본값이다. 영구 제품 원칙이나 local-only 요구사항으로 확정하지 않으며, 선택적 클라우드 기능을 막지 않는다.

## 8. V1 Scope

### Included

- Media Ingestion
- Text Pipeline 전체
- Edit Pipeline 전체
- 컷편집용 필수 구간 라벨
- Edit Candidate
- 자막·편집 통합 Review
- Accept·Reject·Modify와 관련 원본 미디어 확인을 위한 최소 Review Interface
- 사용자 Accept·Reject·Modify
- 승인된 편집 결정 보존
- 필수 출력 전체

Text Pipeline과 Edit Pipeline은 모두 V1 핵심 범위다.

### Deferred

- 자동 컷편집
- FCPXML 생성
- 완성형 GUI 자막·타임라인 편집기
- OCR
- PPT 분석
- Preference Learning

Deferred 항목은 Edit Candidate, 사용자 결정 흐름, 최소 Review Interface를 V1에서 제외하는 근거가 아니다.

## 9. Acceptance Criteria

- [ ] 기존 방식보다 Final Cut 내 자막 수정량이 감소한다.
- [ ] 긴 자막의 수동 분할 수가 감소한다.
- [ ] 자막 타이밍 수정 수가 감소한다.
- [ ] 컷편집 후보를 찾고 검토하는 시간이 감소한다.
- [ ] 사용자가 자막 변경과 Edit Candidate를 LectureOS 안에서 Accept·Reject·Modify할 수 있다.
- [ ] 최소 Review Interface에서 관련 원본 오디오 또는 영상 구간을 확인할 수 있다.
- [ ] 승인된 자막과 편집 결정이 재실행 후에도 보존된다.
- [ ] 승인된 편집 결정을 원본 시간 구간, 구간 라벨, 결정 상태와 함께 사람이 읽을 수 있거나 기계가 읽을 수 있는 형태로 내보낼 수 있다.
- [ ] Final Cut에서 대량 자막 수정이 필요하지 않다.
- [ ] 모든 필수 출력이 원본 시간축과 추적 가능하다.
- [ ] Text Pipeline과 Edit Pipeline이 모두 V1 핵심 범위에 존재한다.
- [ ] 자동 삭제보다 설명 가능한 추천과 사람의 확인이 우선된다.
- [ ] 교육적 가치가 불명확한 구간이 자동 삭제되지 않는다.

50% 시간 절감 Working Target은 기준선과 측정 범위가 승인된 뒤 별도로 검증한다.

## Open Questions

- 50% 시간 절감 Working Target의 기준 작업, 측정 범위, 대표 자료는 무엇인가?
- 읽기 속도, 최대 표시 시간, 자막 길이의 기본 임계값은 무엇인가?
- 원본 시간축 기반 발화·단어 데이터의 최종 명칭과 최소 단위는 무엇인가?
- stable identifier의 정확한 책임과 범위는 무엇인가?
- Review, Review Item, Review 상태의 최종 용어와 관계는 무엇인가?
- local-first는 검증 후에도 장기 제품 원칙으로 유지할 것인가?

## Related Documents

- `000_MANIFESTO.md`
- `001_PRODUCT.md`
- `002_FAQ.md`
- `003_VISION.md`
- `004_PRINCIPLES.md`
- `../patches/PATCH-0001-l0-and-prd-stabilization.md`

## Change Log

### Blueprint 0.1 — 2026-07-13

- Text Pipeline과 Edit Pipeline을 동등한 V1 핵심으로 명시했다.
- Media, ASR, Correction, Subtitle, Lecture Intelligence, Edit Candidate, Review, Output 요구사항을 보완했다.
- LectureOS와 Final Cut의 책임 경계, local-first 상태, 50% Working Target 상태를 명확히 했다.
