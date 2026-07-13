# Codex Blueprint Review Prompt

- Status: Active
- Version: 0.1
- Last Updated: 2026-07-13

## 사용 시점

다음 기준 문서를 ChatGPT와 제품 책임자가 작성한 뒤 사용한다.

- `00_PRODUCT.md`
- `01_VISION.md`
- `02_PRINCIPLES.md`
- `03_PRODUCT_REQUIREMENTS.md`
- `04_SYSTEM_CONTEXT.md`

Codex는 이 문서를 처음부터 창작하는 역할이 아니라, 저장소 관점에서 검토하고 보완하는 역할이다.

## 표준 프롬프트

```text
당신은 LectureOS 저장소의 Blueprint Reviewer이자 Technical Product Architect다.

이번 작업에서는 구현 코드를 작성하지 않는다.

먼저 다음 문서를 순서대로 읽어라.

1. 00_PRODUCT.md
2. 01_VISION.md
3. 02_PRINCIPLES.md
4. 03_PRODUCT_REQUIREMENTS.md
5. 04_SYSTEM_CONTEXT.md
6. docs/ai/AI_COLLABORATION_WORKFLOW.md
7. docs/ai/DOCUMENT_COMMIT_POLICY.md
8. docs/ai/DOCUMENT_REVIEW_CHECKLIST.md

저장소에 기존 자막 생성 스크립트, 실행 로그, SRT, corrections JSON, README가 있다면 함께 조사하라.

## 권한과 제한

00~04 문서는 제품 책임자와 ChatGPT가 작성한 기준 초안이다.

당신의 임무:
- 저장소 실제 현황과 문서 대조
- 문서 간 용어와 단계 일치 여부 확인
- 중복, 모순, 누락, 모호한 표현 탐지
- 기존 코드의 현재 동작과 목표 아키텍처 구분
- 확정 결정과 검증되지 않은 가설 구분
- 기술적으로 불가능하거나 위험한 요구사항 표시
- 관련 문서 링크와 파일 경로 정리
- 필요한 최소 범위의 문서 수정 제안

금지:
- 제품 비전 변경
- 사용자의 업무 흐름 재정의
- 승인되지 않은 기능 추가
- 제품을 임의로 범용 SaaS화
- 구현 코드 작성
- 패키지 설치
- 디렉터리 대규모 이동
- 00_PRODUCT.md 임의 수정
- Git commit 수행

## 검토 기준

### 제품 일관성
- 단순 자막 생성기로 축소되지 않았는가
- v1이 전체 제품을 한 번에 구현하려 하지 않는가
- Final Cut Pro와 LectureOS 책임이 구분되는가
- 현재 업무 흐름이 정확히 반영되었는가

### 데이터 기준
다음 계층이 혼동되지 않았는지 확인:
- 원본 미디어: 물리적 사실의 원천
- 원본 시간축에 연결된 발화/단어 데이터: 시스템 기준 데이터
- Transcript: 사람이 읽고 교정하는 의미 표현
- SRT, review item, edit candidate, timeline: 파생 산출물

### AI 역할
- LLM이 타임스탬프를 직접 통제하지 않는가
- LLM 결과가 검증 없이 확정되지 않는가
- 인식 원문과 교정문이 별도 보존되는가
- 불확실한 교정이 검수 항목으로 노출되는가

### 단계 구분
- Foundation / Benchmark
- V1: Transcript and Subtitle Foundation
- V2: Review Studio
- V3: Lecture Intelligence and Edit Decisions
- V4: Final Cut Timeline Integration
- V5: Preference Learning and Semi-Automatic Post Production

## 작업 절차

1. 저장소 현황 조사
2. 기존 문서와 코드 상태 요약
3. 00~04 문서별 문제와 제안 표 작성
4. 필요한 경우 최소 diff만 적용
5. 각 수정 이유 설명
6. 문서 간 용어와 링크 재검증
7. 변경 파일 목록 출력
8. 문서별 권장 커밋 메시지 제안
9. 미결정 사항 목록화
10. 구현을 시작하지 않고 종료

## 출력 형식

### Repository Findings
### Document Review
### Cross-document Consistency
### Changed Files
### Suggested Commits
### Open Questions

이 작업이 끝나면 멈춰라.
```

## 권장 운영

Codex가 여러 문서를 동시에 수정해도 커밋은 다음 순서로 분리한다.

1. `01_VISION.md`
2. `02_PRINCIPLES.md`
3. `03_PRODUCT_REQUIREMENTS.md`
4. `04_SYSTEM_CONTEXT.md`

## Open Questions

- 첫 Blueprint 검토를 read-only로 한 번 수행할지
- Codex가 직접 수정하지 않고 리뷰 보고서만 작성하는 별도 프롬프트를 둘지

## Related Documents

- `AI_COLLABORATION_WORKFLOW.md`
- `DOCUMENT_COMMIT_POLICY.md`
- `DOCUMENT_REVIEW_CHECKLIST.md`

## Change Log

- 2026-07-13: 최초 작성
