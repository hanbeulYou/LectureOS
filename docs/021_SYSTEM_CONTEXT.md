# 021_SYSTEM_CONTEXT

- Status: Draft
- Version: Blueprint 0.1
- Last Updated: 2026-07-14
- Layer: L1 — System Context
- Depends On:
  - `000_MANIFESTO.md`
  - `001_PRODUCT.md`
  - `002_FAQ.md`
  - `003_VISION.md`
  - `004_PRINCIPLES.md`
  - `020_PRODUCT_REQUIREMENTS.md`
  - `../patches/PATCH-0001-l0-and-prd-stabilization.md`
- Referenced By:
  - `022_WORKFLOW.md`
  - `030_DATA_MODEL.md`
  - `031_ARCHITECTURE.md`

## Purpose

이 문서는 LectureOS가 존재하는 시스템 환경과 LectureOS와 사용자, 외부 시스템, 외부 기술 의존성 사이의 관계를 정의한다. LectureOS의 시스템 경계, 입출력, 책임, 데이터 이동, 신뢰 경계를 설명하되 내부 Architecture, 컴포넌트, Data Model, 저장 기술, API, UI는 의도적으로 정의하지 않는다. 내부 구현은 후속 `030_DATA_MODEL.md`와 `031_ARCHITECTURE.md`가 담당한다.

## 1. System of Interest

LectureOS는 한국어 장시간 교육 강의의 반복적인 후반작업을 줄이는 AI 기반 강의 후반작업 시스템이다. 강의 미디어를 입력받아 AI-assisted post-production workflow를 조정하고, 사용자가 검수한 결과를 downstream editing 과정에 전달한다.

LectureOS의 시스템 경계는 원본 영상 또는 오디오와 선택적 처리 컨텍스트를 받아 처리 준비를 시작하는 지점에서 시작한다. 시스템은 Text Pipeline과 Edit Pipeline을 동등한 핵심으로 수행하고, 사용자가 자막 변경과 Edit Candidate를 함께 검수해 Accept, Reject, Modify할 수 있게 한다.

시스템 경계는 다음 결과를 외부로 제공하는 지점까지 이어진다.

- 최종 Subtitle과 SRT
- raw transcript 계열과 corrected transcript 계열 산출물
- Edit Candidate와 Review Item
- 승인된 편집 결정
- 처리 상태, 실패, 불확실성 정보

LectureOS는 원본 미디어를 변경하지 않고 원본 시간축과의 연결을 보존한다. SRT와 승인된 편집 결정 export는 시스템의 중심 데이터가 아니라 원본, 처리 결과, 사용자 결정에서 만들어지는 파생 출력이다.

다음은 LectureOS 시스템 경계 밖에 있다.

- 강의 촬영과 녹화
- 외부 파일 시스템과 미디어 보관 정책
- 외부 ASR·LLM backend 자체의 구현과 운영
- 외부 NLE에서 수행하는 실제 시각 편집과 렌더링
- LMS, 학생 관리, 콘텐츠 배포

## 2. Primary Actors

| Actor | Classification | Interaction with LectureOS |
| --- | --- | --- |
| 강사 또는 후반작업 담당자 | Primary human actor | 미디어와 선택적 컨텍스트를 제공하고, 자막 변경과 Edit Candidate를 검수하며 Accept, Reject, Modify 결정을 내린다. 관련 원본 오디오 또는 영상 구간을 확인하고 승인된 결과를 외부 편집 과정에 사용한다. |
| 시스템 운영자 또는 개발자 | Supporting operational actor | 실행 환경을 준비하고 처리 상태·실패 정보를 확인하며 시스템 운영과 문제 해결을 지원한다. 교육적 내용과 편집 후보의 최종 판단자는 아니다. |
| 학생 | Result consumer | LectureOS가 준비한 결과를 거쳐 완성된 교육 콘텐츠를 소비한다. V1에서 LectureOS와 직접 상호작용하는 사용자로 단정하지 않는다. |

ASR, LLM, correction provider는 사용자 행위자가 아니다. 이들은 LectureOS가 호출하거나 활용할 수 있는 외부 기술 의존성이다.

## 3. External Systems and Dependencies

| External System or Dependency | Current Status | Boundary Relationship |
| --- | --- | --- |
| 원본 미디어 파일 및 외부 파일 시스템 | Confirmed | LectureOS에 영상 또는 오디오를 제공한다. 원본의 보관 위치와 수명주기 책임은 후속 결정이 필요하다. |
| External AI Provider | Confirmed dependency | ASR, correction, LLM 역할을 통해 raw 인식 결과, 시간 정보, 가능한 불확실성 정보와 교정·분류·변경 후보를 반환할 수 있다. 특정 provider나 backend는 확정하지 않으며, 반환 결과는 검증 전에는 신뢰하지 않는다. |
| 선택된 local compute runtime | Working Assumption | 현재 local-first 전략에서 미디어와 AI 처리를 실행할 수 있는 환경이다. 특정 runtime이나 실행 기술은 확정하지 않는다. |
| Final Cut | Confirmed current user environment | LectureOS가 준비한 SRT와 승인된 결정을 받아 화면 편집, 실제 컷 작업, 최종 확인, 렌더링을 수행한다. LectureOS 내부 구성요소가 아니다. |
| Final Cut 이외 외부 NLE | Deferred integration | 장기적으로 같은 경계 역할을 할 수 있지만 V1 지원 방식은 확정하지 않는다. |
| External export consumer | Confirmed boundary role | 사람이 읽을 수 있거나 기계가 읽을 수 있는 승인된 편집 결정 export를 소비한다. 구체적인 consumer와 schema는 확정하지 않는다. |
| 향후 SaaS 또는 remote service | Deferred | 협업이나 원격 처리를 지원할 가능성은 열어두지만 완전한 SaaS 운영 모델은 V1 범위가 아니다. |

외부 AI backend가 같은 장비에서 실행되는지 원격에서 실행되는지는 제품 개념의 경계를 바꾸지 않는다. 어느 경우에도 AI가 생성한 결과는 검증되지 않은 외부 생성 결과로 취급한다.

## 4. Inputs

LectureOS는 다음 입력을 받을 수 있다.

- **원본 영상 또는 오디오:** 처리의 최상위 물리적 근거다.
- **선택적 처리 설정:** 처리 범위와 파생 결과의 생성을 조정한다. 구체적인 설정 형식은 정의하지 않는다.
- **선택적 Project Context:** 프로젝트 또는 강의에 관한 맥락 정보를 제공해 처리를 보조할 수 있다. 구체적인 metadata나 schema는 정의하지 않는다.
- **용어 또는 교정 컨텍스트:** 고유명사, 전문용어, 강의 맥락의 교정 후보 생성을 도울 수 있다.
- **사용자 Review 결정:** 자막 변경과 Edit Candidate에 대한 Accept, Reject, Modify 및 승인 상태다.
- **외부 AI 결과:** ASR raw 결과, 시간 정보, confidence 또는 불확실성, LLM·correction 후보다.

V1은 특정 입력 파일 포맷, API schema, 명령 형식을 이 문서에서 확정하지 않는다.

외부 편집이 끝난 결과를 LectureOS로 다시 가져오는 입력 흐름은 Deferred다.

## 5. Outputs

LectureOS는 최소한 다음 제품 출력을 제공한다.

- **raw transcript 계열 산출물:** 외부 ASR이 생성한 변경 전 결과와 출처를 보존한다.
- **corrected transcript 계열 산출물:** 검증 및 사용자 결정을 반영한 Transcript 표현이다.
- **Subtitle 및 최종 SRT:** 학생 가독성을 위해 구성된 Subtitle과 외부 편집 과정에서 사용할 파생 출력이다.
- **Edit Candidate:** 원본 시간 범위, 구간 라벨, 추천, 이유, confidence 또는 불확실성을 포함하는 편집 후보다.
- **Review Item:** 사람의 확인이 필요한 자막 오류, 변경, 편집 후보, 실패 또는 불확실성이다.
- **approved edit decisions:** 사용자가 승인한 편집 결정이다.
- **approved edit decisions export:** 원본 시간 범위, 라벨, 결정 상태를 포함하며 사람이 읽을 수 있거나 기계가 읽을 수 있는 형태로 외부에 제공한다.
- **운영 정보:** Processing Status와 Diagnostics를 통해 처리 기록, 부분 실패, 누락, 검증 불가 상태를 외부에 노출한다.

각 출력은 가능한 경우 원본 미디어, 원본 시간축, 생성 근거, 사용자 결정과 추적 가능해야 한다.

구체적인 저장 포맷, export schema, 외부 편집기 형식은 이 문서에서 정의하지 않는다. FCPXML은 V1 출력이 아니다.

## 6. System Responsibilities

LectureOS는 다음 제품 수준의 책임을 소유한다.

- 원본 미디어를 받아 처리할 준비를 한다.
- 원본 미디어와 원본 시간축을 변경하지 않고 연결을 보존한다.
- 교체 가능한 ASR backend 사용을 조정한다.
- ASR raw 결과와 가능한 불확실성 정보를 보존한다.
- 텍스트 교정 후보를 만들고 구조적 유효성을 검증한다.
- raw 인식문, corrected Transcript, Subtitle을 구분한다.
- 학생이 읽기 좋은 Subtitle을 구성하고 시간 구조를 검증한다.
- 강의 구간을 분석하고 컷편집용 라벨 후보를 만든다.
- 설명 가능한 Edit Candidate와 Review Item을 생성한다.
- 자막 변경과 Edit Candidate를 함께 다루는 통합 Review를 지원한다.
- 사용자가 Accept, Reject, Modify하고 관련 원본 미디어를 확인할 수 있는 최소 Review Interface를 제공한다.
- 사용자 교정, Review 결정, 승인된 편집 결정을 보존한다.
- 승인된 편집 결정을 외부에서 소비할 수 있는 형태로 내보낸다.
- 조건이나 규칙이 바뀌면 파생 출력을 다시 생성할 수 있게 한다.
- 처리 실패, 누락, 불확실성을 숨기지 않고 노출한다.
- AI-assisted processing을 조정하지만 외부 AI 결과의 정확성을 보장하지 않는다.

이 책임 목록은 내부 컴포넌트, 서비스, 프로세스 또는 배포 단위를 의미하지 않는다.

## 7. Responsibilities Outside LectureOS

다음 책임은 LectureOS 시스템 경계 밖에 있다.

- 카메라, 화면, 오디오의 촬영과 녹화
- 외부 파일 시스템의 장기 보관, 백업, 삭제 정책
- LMS, 수강생 관리, 출결, 결제, 강좌 판매
- 스트리밍과 학생 대상 콘텐츠 배포
- 크롭, 확대·축소, 회전, 위치 조정, 색보정
- 복잡한 시각 편집과 합성
- 외부 NLE에서의 실제 컷 적용과 최종 컷 확인
- 최종 렌더링
- V1에서의 자동 컷 적용
- V1에서의 FCPXML 생성과 round trip
- 범용 영상 편집기 기능
- 외부 AI provider의 내부 학습, 운영, 모델 품질 보장

LectureOS가 Edit Candidate와 승인된 편집 결정을 제공하는 것은 외부 NLE의 실제 편집 책임을 LectureOS 내부로 가져오는 것이 아니다.

## 8. Context Flows

다음 흐름은 시스템 사이의 데이터 이동을 나타낸다. LectureOS 내부 모듈이나 실행 순서를 설계하지 않는다.

### A. Primary V1 Flow

~~~text
강사 또는 후반작업 담당자
→ 원본 미디어와 선택적 컨텍스트
→ LectureOS
→ 자막 변경·Edit Candidate·Review Item
→ 통합 Review: Accept·Reject·Modify 및 원본 구간 확인
→ 승인된 Subtitle·SRT·approved edit decisions export
→ Final Cut 또는 외부 편집 과정
→ 화면 편집·실제 컷 적용·최종 확인·렌더링
→ 학생이 소비하는 최종 교육 콘텐츠
~~~

### B. Text Flow

~~~text
원본 미디어
→ LectureOS
→ External AI Provider에 ASR·correction 처리 요청
→ External AI Provider 결과를 LectureOS가 수신
→ raw transcript·corrected Transcript·Subtitle 후보
→ 통합 Review
→ 최종 Subtitle 및 SRT
→ 외부 편집 과정
~~~

### C. Edit Decision Flow

~~~text
원본 미디어
→ LectureOS
→ External AI Provider에 강의 분석 처리 요청
→ External AI Provider 결과를 LectureOS가 수신
→ 강의 구간 분석·컷편집용 라벨·Edit Candidate
→ 통합 Review
→ approved edit decisions
→ 원본 시간 범위·라벨·결정 상태를 포함한 export
→ 외부 편집 과정
~~~

외부 편집 결과를 LectureOS로 되돌리는 round trip은 V1 흐름에 포함하지 않는다.

## 9. Trust and Data Boundaries

### 9.1 Authority Order

~~~text
원본 미디어 — 촬영된 물리적 사실의 최상위 근거
↓
사용자 결정 — 자막 변경과 편집 후보의 작업 상태를 확정
↓
ASR·LLM 결과 — 외부에서 생성된 검증 전 후보
↓
파생 출력 — 원본과 보존된 사용자 결정에서 재생성 가능한 결과
~~~

사용자 결정이 작업 흐름에서 AI 후보보다 우선하더라도 원본 미디어가 물리적 사실의 최상위 근거라는 원칙은 바뀌지 않는다.

### 9.2 Boundary Crossings

- 원본 미디어, 추출된 음성, 텍스트, 용어 컨텍스트는 선택한 외부 provider에 따라 LectureOS의 로컬 실행 경계를 넘을 수 있다.
- 외부 provider가 반환한 모든 결과는 구조적 검증과 필요한 사람의 Review를 거쳐야 한다.
- 승인된 SRT와 편집 결정 export는 LectureOS에서 외부 NLE 또는 export consumer로 이동한다.
- 외부 파일 시스템에서 LectureOS로 들어오는 미디어의 보관·변경·삭제 책임은 후속 결정이 필요하다.

### 9.3 Privacy and Policy

학생과 강사의 음성, 특히 미성년자 음성은 개인정보 또는 민감한 교육 데이터가 될 수 있다. 외부 provider에 전달할 수 있는 데이터 범위, 동의, 보존 기간, 삭제 정책, 접근 통제는 아직 확정하지 않는다.

이 문서는 보안 구현이나 법률 정책을 정의하지 않는다. 해당 정책이 승인되기 전에는 외부 전송 가능성을 명시적인 신뢰 경계로 취급한다.

## 10. V1 Context Boundary

### Included

- 로컬 또는 선택된 실행 환경에서 원본 미디어를 처리한다.
- 교체 가능한 ASR, LLM, correction backend를 사용할 수 있다.
- Text Pipeline과 Edit Pipeline을 동등한 핵심 흐름으로 지원한다.
- 자막 변경과 Edit Candidate를 함께 다루는 통합 Review를 지원한다.
- 사용자가 Accept, Reject, Modify하고 관련 원본 미디어를 확인할 수 있는 최소 Review Interface를 제공한다.
- 최종 SRT를 외부 편집 과정에 제공한다.
- 승인된 편집 결정을 원본 시간 범위, 라벨, 결정 상태와 함께 사람이 읽을 수 있거나 기계가 읽을 수 있는 형태로 export한다.
- 처리 상태, 실패, 불확실성을 외부에 노출한다.
- Final Cut 또는 외부 편집 과정에 들어가기 전에 자막과 편집 후보 검수를 완료할 수 있게 한다.

### Deferred or Excluded

- 자동 컷편집
- FCPXML 생성과 round trip
- 완성형 GUI 자막·Timeline 편집기
- 외부 편집 결과의 자동 재수입
- OCR과 PPT 분석
- Preference Learning
- 완전한 SaaS 운영 모델
- LMS와 콘텐츠 배포
- 범용 영상 편집기 기능

Deferred 항목은 Edit Candidate, 통합 Review, 최소 Review Interface를 V1에서 제외하는 근거가 아니다.

## 11. Assumptions and Open Questions

### Confirmed

- LectureOS는 한국어 장시간 교육 강의의 후반작업에서 시작한다.
- Text Pipeline과 Edit Pipeline은 동등한 핵심 범위다.
- Review는 자막 변경과 Edit Candidate를 함께 다룬다.
- 사용자는 Accept, Reject, Modify하고 관련 원본 미디어를 확인할 수 있어야 한다.
- 원본 미디어와 원본 시간축을 보존한다.
- SRT와 approved edit decisions export는 파생 출력이다.
- Final Cut은 LectureOS 외부에서 화면 편집, 실제 컷 작업, 최종 확인, 렌더링을 담당한다.
- 특정 ASR, LLM, NLE, 저장 기술, 데이터베이스, UI 프레임워크를 시스템 중심에 두지 않는다.

### Working Assumption

- local-first를 현재 전략적 기본값으로 사용하되 local-only로 제한하지 않는다.
- Final Cut을 현재 핵심 사용자 환경의 외부 NLE로 다룬다.
- 선택된 실행 환경은 장시간·대용량 미디어를 처리할 수 있다.

### Requires Validation

- local engine과 remote service 사이에서 어떤 처리를 나눌 것인가?
- 외부 AI provider로 전달할 수 있는 미디어, 음성, 텍스트, 컨텍스트의 범위는 무엇인가?
- Final Cut 이외 NLE를 어떤 방식과 우선순위로 지원할 것인가?
- 최소 Review Interface가 원본 미디어에 접근하는 방식은 무엇인가?
- 개인정보와 미성년자 음성에 어떤 동의, 보존, 삭제 정책을 적용할 것인가?
- 입력 미디어와 외부 파일 시스템 사이의 수명주기 책임은 어디에 있는가?
- 여러 차례의 Review iteration을 어떻게 표현할 것인가? 이 질문은 후속 Data Model에서 다룬다.

### Deferred

- approved edit decisions의 구체적인 교환 형식과 schema
- 외부 편집 후 결과를 LectureOS로 다시 가져오는 범위
- FCPXML 생성 및 round trip
- 완전한 SaaS 운영 모델
- Preference Learning

## 12. Downstream Constraints

### Constraints for `030_DATA_MODEL.md`

- 모든 주요 산출물은 가능한 경우 원본 미디어와 원본 시간축에 추적 가능해야 한다.
- raw 인식문, corrected Transcript, Subtitle을 서로 다른 책임으로 표현해야 한다.
- Edit Candidate, Review Item, 사용자 결정, 승인된 편집 결정의 관계와 이력을 보존할 수 있어야 한다.
- 승인된 편집 결정은 원본 시간 범위, 라벨, 결정 상태를 잃지 않아야 한다.
- 파생 출력은 다시 생성할 수 있어야 하며 SRT나 외부 provider 출력이 중심 모델이 되어서는 안 된다.
- 특정 ASR이나 NLE가 제공하는 고유 구조를 제품의 중심 데이터로 고정해서는 안 된다.

### Constraints for `031_ARCHITECTURE.md`

- 교체 가능한 외부 AI backend와의 경계를 유지해야 한다.
- 원격 provider를 사용할 때 데이터가 신뢰 경계를 넘는 사실을 드러낼 수 있어야 한다.
- 내부 실패나 재실행이 원본 미디어 또는 승인된 사용자 결정을 손상시키면 안 된다.
- 필요한 단계의 재실행과 파생 결과 재생성을 지원할 수 있어야 한다.
- 외부 시스템 실패와 불확실성을 정상 결과처럼 숨기지 않아야 한다.
- 최소 Review Interface를 지원하되 특정 UI 프레임워크를 전제로 삼지 않아야 한다.
- V1에서 자동 컷편집이나 FCPXML round trip을 전제로 삼지 않아야 한다.
- 시스템 경계와 내부 구현 경계를 혼동하거나 시스템 경계를 내부 Architecture로 무너뜨리지 않아야 한다.

이 제약은 데이터 엔티티, 필드, 저장 구조, 컴포넌트, 서비스 또는 배포 토폴로지를 정의하지 않는다.

## Related Documents

- `000_MANIFESTO.md`
- `001_PRODUCT.md`
- `002_FAQ.md`
- `003_VISION.md`
- `004_PRINCIPLES.md`
- `020_PRODUCT_REQUIREMENTS.md`
- `../patches/PATCH-0001-l0-and-prd-stabilization.md`

## Change Log

### Blueprint 0.1 — 2026-07-14

- LectureOS의 시스템 경계, 외부 행위자와 의존성, 입출력, 책임, 데이터 이동, 신뢰 경계를 정의했다.
- Text Pipeline과 Edit Pipeline의 동등한 V1 컨텍스트와 통합 Review 경계를 반영했다.
- V1 상호작용과 Deferred 통합을 구분하고 후속 Data Model과 Architecture 제약을 기록했다.
- Review Round 1에서 Purpose, 외부 AI 경계, 운영 정보, 신뢰 계층과 후속 제약의 표현을 정제했다.
