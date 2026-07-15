# PATCH-0001

Patch ID: PATCH-0001
Title: L0 and PRD Stabilization
Status: Completed
Priority: High
Owner: Product Owner
Trigger: Blueprint Review
Created: 2026-07-13

Depends On:

- docs/000_MANIFESTO.md
- docs/001_PRODUCT.md
- docs/002_FAQ.md
- docs/003_VISION.md
- docs/004_PRINCIPLES.md
- docs/020_PRODUCT_REQUIREMENTS.md

---

# Title

L0 and PRD Stabilization

---

# Background

L0 Blueprint는 원본 보존, 인간 판단, 모델 독립성, 재생성, 검수 시간 감소에 대해 대체로 일관되어 있다.

그러나 docs/020_PRODUCT_REQUIREMENTS.md는 Text Pipeline에 비해 Edit Pipeline 요구사항이 약하다. 컷편집용 라벨링과 삭제·검토 후보 생성이 제품의 동등한 핵심 기능으로 충분히 보장되지 않으며, Review가 읽기 전용 Report로 축소될 위험이 있다.

특히 사용자의 승인·거절·수정, 결정 상태, 승인된 편집 결정의 보존 요구가 빠져 있다. 이 상태로 docs/021_SYSTEM_CONTEXT.md를 작성하면 Text Pipeline 중심의 잘못된 시스템 경계가 굳어질 수 있다.

---

# Trigger

Trigger Type: Blueprint Review
Review Result: Needs Major Revision

직전 Blueprint Review는 현재 워크플로와 목표 워크플로의 구분, 원본 보존, 재생성, 모델 독립성은 대체로 일관된다고 평가했다. 반면 Text Pipeline과 Edit Pipeline의 동등성, 통합 Review의 사용자 결정 흐름, Edit Candidate의 필수 정보, 필수 출력과 수용 기준은 후속 시스템 경계를 정의하기 전에 보완해야 한다고 결론 내렸다.

---

# Findings

## F-01 — Text Pipeline과 Edit Pipeline의 동등성 부족

Severity: Critical

- docs/001_PRODUCT.md와 docs/020_PRODUCT_REQUIREMENTS.md에서 자막이 중심이고 편집 라벨링은 보조 기능처럼 해석될 수 있다.
- 컷편집용 라벨링, Edit Candidate, 편집 Review가 제품 계약 수준에서 약하다.
- docs/020_PRODUCT_REQUIREMENTS.md의 Secondary Goal, “텍스트 중심”, “Lecture Intelligence 기초” 표현은 두 파이프라인의 동등성을 약화할 수 있다.
- 후속 System Context가 Text Pipeline을 본체로, Edit Pipeline을 부가기능으로 고정하지 않도록 보완해야 한다.

## F-02 — Review의 사용자 결정 흐름 누락

Severity: Critical

다음 요구사항이 빠져 있다.

- 편집 후보 승인
- 편집 후보 거절
- 편집 후보 수정
- 결정 상태
- 재실행 후 결정 보존
- 원본 시간축 연결

Edit Pipeline은 Approved Edit Decisions로 끝나지만, 현재 기능 요구사항은 Review 데이터와 Report 생성까지만 정의한다.

## F-03 — Edit Pipeline 탐지 범주 부족

Severity: Major

다음 범주가 기능 요구사항 수준에서 완결되어 있지 않다.

- 수업 시작 전
- 수업 종료 후
- 쉬는 시간
- 긴 무음
- 학생 잡담
- 선생님 잡담
- 장비 문제
- 교재 찾는 시간
- 판서 대기
- 반복 설명 후보
- 말실수 또는 다시 말한 구간
- 교육적 가치가 낮을 가능성이 있는 구간

각 후보에 필요한 다음 공통 정보도 요구사항으로 명시되지 않았다.

- 구간 라벨
- 추천 상태
- confidence 또는 불확실성
- 이유
- 예상 절감 시간

## F-04 — ASR과 Correction 요구사항 부족

Severity: Major

다음 요구사항이 부족하거나 누락되어 있다.

- 한국어 우선
- 교체 가능한 ASR backend
- 발화 또는 단어 수준 시간 정보
- raw 결과 보존
- confidence 또는 불확실성
- 실패 후 재개
- 고유명사·전문용어 교정
- 숫자 변경 검수
- 원문·교정문 분리
- LLM 결과의 구조적 검증
- 불확실한 수정의 Review 전환

## F-05 — Subtitle 요구사항 부족

Severity: Major

다음 자막 품질 요구사항이 부족하거나 누락되어 있다.

- ASR 구간을 그대로 최종 cue로 사용하지 않음
- 긴 자막 재분할
- 최대 2줄
- 읽기 속도
- 최대 표시 시간
- 발화 호흡과 의미 단위
- 줄바꿈·분할 오류 검수
- 타임스탬프 구조 검증

구체적인 임계값은 아직 확정하지 않고 Requires Validation 또는 후속 명세로 남겨야 한다.

## F-06 — 통합 Review 요구사항 부족

Severity: Major

Review가 다음 책임을 모두 포함하도록 보완해야 한다.

- 자막과 편집 후보를 한 흐름에서 검수
- 위험도와 우선순위
- 관련 오디오 또는 영상 구간 재생
- 승인·거절·수정
- 수정 이력
- 사용자 결정 보존
- Accept·Reject·Modify와 원본 구간 확인을 수행할 수 있는 최소 Review Interface
- 전체 영상을 처음부터 보는 시간을 줄이는 목적

원본 확인을 금지하는 것이 아니라 위험 구간을 우선 제시해 전체 재생 필요성을 줄여야 한다.

## F-07 — LectureOS와 Final Cut의 책임 경계 불명확

Severity: Major

LectureOS가 담당해야 할 책임:

- 강의 구간 분석
- 컷편집용 라벨링
- Edit Candidate
- 자막·편집 통합 Review
- 승인된 편집 결정 저장
- 최종 자막 산출

Final Cut이 담당해야 할 책임:

- 크롭
- 확대·축소
- 회전
- 위치 조정
- 색보정
- 복잡한 시각 편집
- 최종 컷 확인
- 렌더링

Final Cut에서 다시 대량의 자막 수정과 전체 컷 판단을 수행하는 흐름이 목표 워크플로로 남지 않도록 경계를 명확히 해야 한다.

## F-08 — 필수 출력 부족

Severity: Major

다음 최소 출력이 요구사항으로 충분히 정의되지 않았다.

- raw transcript
- corrected transcript
- final subtitle/SRT
- edit candidates
- review items
- approved edit decisions
- 원본 시간 구간, 구간 라벨, 결정 상태를 포함한 approved edit decisions의 사람이 읽을 수 있거나 기계가 읽을 수 있는 export
- processing log
- 원본 시간축과 연결되는 안정적 식별자

## F-09 — local-first 상태 불명확

Severity: Major

- L0에서는 local-first를 Working Assumption 또는 Working Principle로 정의한다.
- docs/020_PRODUCT_REQUIREMENTS.md에서는 확정된 Non-functional Requirement처럼 보인다.
- 현재 전략적 기본값과 영구 제품 원칙을 구분해야 한다.
- local-first를 local-only로 확대 해석해서는 안 된다.

## F-10 — 50% 시간 절감 목표 검증 상태 불명확

Severity: Major

- 후반작업 시간 50% 절감이 승인된 목표인지 Working Target인지 표시해야 한다.
- 비교 기준선과 측정 범위를 정의해야 한다.
- Acceptance Criteria가 해당 목표의 검증 방식과 연결되어야 한다.
- 측정 구현이나 benchmark 설계는 이번 Patch에서 확정하지 않는다.

## F-11 — 문서 품질과 메타데이터 부족

Severity: Minor

docs/020_PRODUCT_REQUIREMENTS.md에 다음 보완이 필요하다.

- Depends On
- Referenced By
- Open Questions
- Change Log
- Review, Review Item, Review Report의 관계를 오해하지 않게 하는 표현
- confidence 표기 일관성
- Current Workflow와 Target Workflow의 명시적 구분 유지
- local-first의 상태 명시
- 50% 목표의 상태 명시

현재 docs/020_PRODUCT_REQUIREMENTS.md는 Git에서 아직 추적되지 않은 상태이므로, Patch 적용과 검토가 끝난 뒤 별도 승인된 커밋으로 기록해야 한다.

---

# Goal

이번 Patch의 목표는 다음과 같다.

1. Text Pipeline과 Edit Pipeline을 동등한 제품 핵심으로 명시한다.
2. 컷편집용 라벨링과 Edit Candidate를 L0 제품 경계와 PRD에 안정적으로 연결한다.
3. 자막과 편집 후보를 함께 다루는 통합 Review와 사용자 결정 흐름을 정의한다.
4. LectureOS와 Final Cut의 책임 경계를 목표 워크플로에 맞게 정렬한다.
5. ASR, Correction, Subtitle, Lecture Intelligence, Edit Candidate, Review, Output 요구사항의 누락을 보완한다.
6. local-first와 50% 시간 절감 목표의 결정 상태를 명확히 한다.
7. docs/021_SYSTEM_CONTEXT.md 작성 전에 제품 요구사항을 안정화한다.

---

# Scope

이번 Patch 적용 시 수정할 수 있는 파일:

- docs/001_PRODUCT.md
- docs/002_FAQ.md
- docs/020_PRODUCT_REQUIREMENTS.md
- patches/PATCH-0001-l0-and-prd-stabilization.md

docs/000_MANIFESTO.md, docs/003_VISION.md, docs/004_PRINCIPLES.md는 변경 기준으로 참조하되 수정하지 않는다.

---

# Out of Scope

- docs/000_MANIFESTO.md 수정
- docs/003_VISION.md 수정
- docs/004_PRINCIPLES.md 수정
- docs/021_SYSTEM_CONTEXT.md 작성
- docs/022_WORKFLOW.md 작성
- Architecture 설계
- Data Model 설계
- TimedUnit 또는 WordUnit 최종 선택
- Event Sourcing
- CQRS
- Domain Model
- Storage Model
- API 설계
- 클래스 구조
- 파일 포맷 세부 스키마
- ASR 모델 최종 선정
- LLM 모델 최종 선정
- FCPXML 구현 방식
- GUI 프레임워크
- SaaS 인프라
- 오픈소스 라이선스
- 구현 코드 작성
- 패키지 설치

---

# Constraints

- L0 철학과 승인된 제품 방향을 변경하지 않는다.
- 제품 범위를 새로운 시장이나 범용 플랫폼으로 확대하지 않는다.
- Text Pipeline과 Edit Pipeline을 동등한 V1 핵심으로 유지한다.
- 자동 삭제보다 설명 가능한 후보와 사람의 판단을 우선한다.
- 교육적 가치가 불명확하면 보수적으로 처리한다.
- 반복 설명, 교사의 개성, 교육적 예시를 단순 중복이나 잡담으로 자동 삭제하지 않는다.
- 원본 미디어와 원본 시간축 연결을 보존한다.
- raw 인식문, corrected Transcript, Subtitle을 분리한다.
- 사용자의 수정과 편집 결정을 보존한다.
- LLM은 후보를 제안하고 구조적 유효성은 코드가 검증한다.
- LLM이 최종 타임스탬프를 직접 통제하지 않는다.
- 특정 ASR, LLM, alignment 모델을 확정하지 않는다.
- 구체적인 자막 임계값은 확정하지 않고 Requires Validation 또는 후속 명세로 남긴다.
- 새로운 아키텍처 패러다임을 추가하지 않는다.
- Product Owner의 명시적 승인 없이 새 제품 결정을 만들지 않는다.

---

# Expected Changes

## docs/001_PRODUCT.md

- Product Definition과 In Scope에서 자막 품질 개선과 컷편집용 라벨링을 동등한 핵심 책임으로 명시한다.
- 강의 구간 분석, Edit Candidate, 자막·편집 통합 Review, 사용자 결정 보존을 제품 계약 수준에서 연결한다.
- Final Cut 이전에 자막과 편집 후보를 검수하고 승인된 결과를 준비한다는 경계를 명확히 한다.
- Final Cut은 현재 핵심 사용 환경이지만 LectureOS의 영구 정체성은 아니라는 기존 방향을 유지한다.
- 세부 탐지 범주, 구현 방식, 데이터 구조는 이 문서에 넣지 않는다.

## docs/002_FAQ.md

- 자동 컷편집과 Edit Candidate를 구분한다.
- 컷편집용 라벨링과 Edit Candidate는 현재 핵심 제품 범위임을 설명한다.
- 자동 컷편집과 FCPXML 구현은 Deferred Scope임을 유지한다.
- 현재 워크플로와 목표 워크플로의 차이를 직접 설명한다.
- Review가 읽기 전용 Report가 아니라 자막과 편집 후보에 대한 사용자 결정을 포함한다는 점을 명확히 한다.
- Final Cut은 현재 작업 환경이지만 영구 제품 종속은 아니라는 기존 구분을 유지한다.

## docs/020_PRODUCT_REQUIREMENTS.md

### Product Goal

- Text Pipeline과 Edit Pipeline을 동등한 핵심으로 명시한다.
- 자막 품질 개선과 컷편집 후보 검토 시간 감소를 함께 제품 목표에 둔다.
- 50% 시간 절감 목표가 Approved Goal인지 Working Target인지 명시한다.
- 총 검수 시간 감소와 Final Cut 내 반복 수정 감소를 성공 기준에 연결한다.

### Current Workflow

~~~text
원본 영상
→ 초안 SRT
→ Final Cut
→ 컷편집과 자막 수정 동시 수행
~~~

### Target Workflow

~~~text
원본 영상
→ LectureOS 분석·교정·라벨링·검수
→ 승인된 자막과 편집 결정
→ Final Cut에서 화면 편집과 최종 확인
~~~

### Media Ingestion Requirements

- 원본 보존
- 장시간·대용량 입력
- 오디오 추출
- 중간 산출물 캐시
- 실패 후 단계 재실행

### ASR Requirements

- 한국어 우선
- backend 교체 가능
- 발화 또는 단어 수준 시간 정보
- raw 결과 보존
- confidence 또는 불확실성
- 실패 후 재개

### Correction Requirements

- 인식 오류 교정
- 고유명사·전문용어 교정
- 숫자 변경 검수
- 원문·교정문 분리
- LLM 결과의 구조적 검증
- 불확실한 수정의 Review 처리

### Subtitle Requirements

- ASR 구간을 그대로 최종 cue로 사용하지 않음
- 긴 자막 재분할
- 최대 2줄
- 읽기 속도
- 최대 표시 시간
- 발화 호흡과 의미 단위
- 줄바꿈·분할 오류 검수
- 타임스탬프 구조 검증
- Final Cut용 SRT 출력

구체적인 임계값은 확정하지 않고 Requires Validation 또는 후속 명세로 둔다.

### Lecture Intelligence Requirements

최소 라벨링 대상:

- 수업 시작 전
- 수업 종료 후
- 쉬는 시간
- 긴 무음
- 학생 잡담
- 선생님 잡담
- 장비 문제
- 교재 찾는 시간
- 판서 대기
- 반복 설명 후보
- 말실수 또는 다시 말한 구간
- 교육적 가치가 낮을 가능성이 있는 구간

교육적 판단은 확정 삭제가 아니라 분석·추천의 근거로 사용한다.

### Edit Candidate Requirements

각 후보는 최소한 다음을 제공해야 한다.

- 원본 시간 구간
- 구간 라벨
- 유지·삭제·검토 추천
- confidence 또는 불확실성
- 이유
- 예상 절감 시간
- Review 상태

### Review Requirements

Review는 자막과 편집 후보를 함께 다룬다.

V1은 다음 동작과 원본 미디어 확인을 실제로 수행할 수 있는 최소 Review Interface를 포함한다. 구체적인 UI 기술이나 프레임워크는 정의하지 않는다.

사용자는 다음을 수행할 수 있어야 한다.

- Accept
- Reject
- Modify
- 관련 원본 오디오·영상 구간 확인
- 수정 이력 확인
- 결정 상태 보존

Review의 목표는 원본 확인을 금지하는 것이 아니라, 위험 구간을 우선 제시하여 전체 재생 필요성을 줄이는 것이다.

### Product Boundary

LectureOS 책임:

- 음성 인식
- 텍스트 교정
- 자막 생성·분할·타이밍
- 강의 구간 분석
- 컷편집용 라벨링
- Edit Candidate
- 통합 Review
- 승인된 편집 결정 저장
- 최종 자막 산출

Final Cut 책임:

- 크롭
- 확대·축소
- 회전
- 위치 조정
- 색보정
- 복잡한 시각 편집
- 최종 컷 확인
- 렌더링

### Required Outputs

- raw transcript
- corrected transcript
- final subtitle/SRT
- edit candidates
- review items
- approved edit decisions
- source time ranges, labels, decision status를 포함한 approved edit decisions의 human-readable 또는 machine-readable export
- processing log
- 향후 Timeline 연결에 필요한 안정적 식별자

구체적인 export 스키마는 정의하지 않으며 FCPXML을 추가하지 않는다.

### Non-functional Requirements

- 원본 보존
- 단계별 재실행
- 캐시
- 실패 후 재개
- 모델 교체 가능성
- 오류와 불확실성 노출
- 사용자 결정 보존
- 2시간 이상 대용량 영상 지원
- local-first의 현재 결정 상태 명시

### V1 Scope

- Accept, Reject, Modify와 관련 원본 미디어 확인을 수행할 수 있는 최소 Review Interface를 Included에 둔다.
- Deferred GUI 범위는 완성형 자막·Timeline 편집기로 한정한다.
- 최소 Review Interface의 UI 기술이나 프레임워크는 확정하지 않는다.
- FCPXML은 계속 Deferred로 유지한다.

### Acceptance Criteria

최소한 다음을 포함한다.

- 기존 방식보다 Final Cut 내 자막 수정량 감소
- 긴 자막 수동 분할 감소
- 타이밍 수정 감소
- 컷편집 후보 검토 시간 감소
- 사용자가 자막과 Edit Candidate의 결정을 LectureOS 안에서 완료 가능
- 승인된 편집 결정이 재실행 후에도 보존
- Final Cut에서 대량 자막 수정이 필요하지 않음
- 모든 필수 출력이 원본 시간축과 추적 가능
- Text Pipeline과 Edit Pipeline이 모두 V1 핵심 범위에 존재

### Document Quality

- Depends On과 Referenced By를 추가한다.
- Open Questions와 Change Log를 추가한다.
- confidence, Review, Review Item, Edit Candidate의 임시 표현을 문서 안에서 일관되게 사용한다.
- 아직 확정되지 않은 용어와 수치는 명시적으로 Deferred 또는 Requires Validation로 표시한다.

---

# Acceptance Criteria

- [x] docs/001_PRODUCT.md에서 Text Pipeline과 Edit Pipeline의 동등한 지위가 명시됨
- [x] docs/001_PRODUCT.md에서 컷편집용 라벨링이 핵심 제품 책임으로 명시됨
- [x] docs/002_FAQ.md에서 자동 컷편집과 Edit Candidate가 구분됨
- [x] docs/002_FAQ.md에서 현재와 목표 워크플로가 구분됨
- [x] docs/020_PRODUCT_REQUIREMENTS.md가 자막과 편집 분석 요구사항을 동등하게 다룸
- [x] Edit Pipeline의 필수 구간 라벨이 정의됨
- [x] Edit Candidate의 필수 정보가 요구사항에 포함됨
- [x] Review의 Accept·Reject·Modify가 포함됨
- [x] V1 Included에 Accept·Reject·Modify와 원본 미디어 확인을 위한 최소 Review Interface가 포함됨
- [x] Deferred GUI 범위가 완성형 자막·타임라인 편집기로 한정됨
- [x] 사용자 결정 보존이 Must 요구사항으로 포함됨
- [x] LectureOS와 Final Cut의 책임 경계가 명확함
- [x] 필수 출력이 모두 정의됨
- [x] approved edit decisions의 source time ranges·labels·decision status export가 Must로 정의됨
- [x] local-first와 50% 목표의 상태가 명확함
- [x] L0 철학과 제품 범위를 변경하지 않음
- [x] 새 아키텍처 개념을 추가하지 않음
- [x] git diff --check를 통과함

---

# Completion Checklist

- [x] Blueprint review completed
- [x] Review findings captured
- [x] Blueprint changes completed
- [x] Self-review completed
- [x] Merge approved
- [x] Related Blueprint documents committed
- [x] PATCH-0001 final review completed
- [x] PATCH-0001 marked Completed

---

# Result

- Status: Completed
- Changed Blueprint Files: `docs/001_PRODUCT.md`, `docs/002_FAQ.md`, `docs/020_PRODUCT_REQUIREMENTS.md`
- Notes: L0 Product·FAQ와 Product Requirements의 책임 경계, Text Pipeline과 Edit Pipeline의 동등성, 통합 Review와 사용자 결정 흐름이 안정화되어 PATCH-0001이 완료되었다.

---

# Suggested Commit

Patch 등록 커밋:

~~~bash
git add patches/PATCH-0001-l0-and-prd-stabilization.md
git commit -m "docs: add PATCH-0001 blueprint stabilization"
~~~

Patch 적용 완료 후 예상 커밋:

~~~bash
git add docs/001_PRODUCT.md docs/002_FAQ.md docs/020_PRODUCT_REQUIREMENTS.md patches/PATCH-0001-l0-and-prd-stabilization.md
git commit -m "docs: stabilize product blueprint and requirements"
~~~

이번 Patch 등록 작업에서는 커밋하지 않는다.
