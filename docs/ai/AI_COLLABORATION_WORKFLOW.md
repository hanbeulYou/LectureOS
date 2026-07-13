# AI Collaboration Workflow

- Status: Active
- Version: 0.1
- Last Updated: 2026-07-13

## 1. 목적

LectureOS는 제품 문서가 코드보다 먼저 존재하는 문서 주도 개발 방식을 사용한다.

이 문서는 제품 책임자, ChatGPT, Codex의 역할과 문서 작성·검토·커밋·구현 순서를 정의한다.

## 2. 역할

### 제품 책임자

최종 결정:
- 해결하려는 실제 문제
- 현재 작업 방식
- 사용자 우선순위
- 제품 범위
- 자동화 허용 수준
- 품질 기준
- 단계별 우선순위
- 문서 및 커밋 승인

### ChatGPT

제품 설계 파트너:
- 대화를 기반으로 요구사항 정리
- 제품 문서 기준 초안 작성
- 문서 간 논리 구조 설계
- 대안과 트레이드오프 정리
- Codex용 프롬프트 작성
- Codex 결과 검토
- 기존 결정과 신규 제안의 충돌 탐지

### Codex

저장소 기반 검토·구현 에이전트.

Blueprint 단계:
- 저장소 구조와 기존 코드 조사
- 기준 문서의 저장소 반영
- 문서 간 용어·범위·단계 일관성 점검
- 기술적 모순과 위험 표시
- 파일 생성 및 수정
- 변경 파일과 미결정 사항 보고

Blueprint 단계 금지:
- 제품 비전 임의 변경
- 사용자의 작업 흐름 재정의
- 승인되지 않은 기능 추가
- 제품을 근거 없이 범용화
- 구현 코드 작성
- 패키지 설치
- 대규모 디렉터리 재구성
- 자동 커밋

## 3. 문서 작성 흐름

1. 제품 책임자와 ChatGPT가 사실·목표·제약을 확정한다.
2. ChatGPT가 기준 Markdown 초안을 작성한다.
3. 제품 책임자가 1차 검토한다.
4. Codex가 저장소 맥락에서 검토·보완한다.
5. 문서별 diff를 검토한다.
6. 문서별로 커밋한다.
7. 승인된 문서에 의존하는 다음 문서를 작성한다.

권장 순서:

```text
00_PRODUCT
01_VISION
02_PRINCIPLES
03_PRODUCT_REQUIREMENTS
04_SYSTEM_CONTEXT
05_DATA_MODEL
06_ARCHITECTURE
07_PIPELINE
08_TRANSCRIPT_ENGINE
09_SUBTITLE_ENGINE
10_LECTURE_INTELLIGENCE
11_TIMELINE_ENGINE
12_REVIEW_STUDIO
13_ROADMAP
14_MILESTONES
15_BENCHMARK
```

## 4. 구현 시작 조건

- 제품 목표 문서화
- v1 범위와 제외 범위 확정
- 기준 데이터 정의
- 엔진 책임 경계 정의
- 수용 기준 존재
- benchmark 자료 지정
- 구현 마일스톤 승인
- Codex 구현 프롬프트가 해당 마일스톤만 요청

## 5. 변경 관리

의사결정 우선순위:

1. 승인된 ADR
2. 최신 승인 제품 문서
3. 기술 명세
4. 코드

새 제약 발견 시:

```text
제약 발견
→ 이슈 기록
→ 대안 작성
→ 결정
→ ADR 작성
→ 관련 문서 수정
→ 코드 수정
```

## 6. Open Questions

- 문서 승인 상태를 GitHub Issue/PR과 연동할지
- Codex 작업을 항상 별도 브랜치에서 수행할지
- 문서 리뷰용 PR 템플릿을 만들지

## 7. Related Documents

- `00_PRODUCT.md`
- `DOCUMENT_COMMIT_POLICY.md`
- `DOCUMENT_REVIEW_CHECKLIST.md`
- `CODEX_BLUEPRINT_REVIEW_PROMPT.md`

## 8. Change Log

- 2026-07-13: 최초 작성
