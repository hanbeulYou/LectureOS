# Document Commit Policy

- Status: Active
- Version: 0.1
- Last Updated: 2026-07-13

## 1. 목적

LectureOS의 설계 결정 이력을 명확히 남기기 위해 문서 변경의 커밋 단위와 메시지 규칙을 정의한다.

## 2. 기본 원칙

### 하나의 커밋은 하나의 설계 의도

좋은 예:
- 제품 비전 정의
- 설계 원칙 확정
- v1 요구사항 확정
- 시스템 경계 정의
- 특정 ADR 승인

나쁜 예:
- 여러 제품 문서와 코드 구현을 한꺼번에 포함
- 문서 작성, 포맷 변경, 파일 이동을 혼합
- 무관한 설계 변경을 하나로 묶음

### 문서별 커밋이 기본

```text
00_PRODUCT.md
01_VISION.md
02_PRINCIPLES.md
03_PRODUCT_REQUIREMENTS.md
04_SYSTEM_CONTEXT.md
```

여러 문서가 동시에 생성돼도 검토·승인·커밋은 분리한다.

### Codex는 자동 커밋하지 않음

Codex는 파일 수정, diff 요약, 권장 순서와 메시지 제안까지만 수행한다.

## 3. 초기 Blueprint 권장 커밋 순서

```bash
git add 00_PRODUCT.md
git commit -m "docs: define LectureOS product"

git add 01_VISION.md
git commit -m "docs: define LectureOS product vision"

git add 02_PRINCIPLES.md
git commit -m "docs: establish product and design principles"

git add 03_PRODUCT_REQUIREMENTS.md
git commit -m "docs: define product requirements and delivery phases"

git add 04_SYSTEM_CONTEXT.md
git commit -m "docs: define system context and workflow boundaries"
```

## 4. 여러 문서를 함께 커밋할 수 있는 경우

다음 조건을 모두 충족할 때만 허용:
- 하나의 동일 결정이 여러 문서에 반영됨
- 분리 커밋 시 중간 상태가 모순됨
- 커밋 메시지에서 결정 내용이 분명함
- 관련 ADR이 존재함

## 5. 브랜치 전략

```bash
git switch -c docs/blueprint-foundation
```

Blueprint 검토가 끝나면 main에 병합한다.

## 6. 커밋 전 확인

```bash
git status
git diff -- 01_VISION.md
git diff --cached
```

문서 하나만 stage:

```bash
git add 01_VISION.md
git diff --cached
git commit -m "docs: define LectureOS product vision"
```

여러 파일이 수정된 경우:

```bash
git reset
git add <승인한 문서 하나>
git diff --cached
git commit -m "<해당 문서 메시지>"
```

## 7. 피해야 할 작업

- `git add .` 후 검토 없이 커밋
- Codex에게 모든 변경 자동 커밋 요청
- 문서와 실험 코드를 같은 커밋에 포함
- Open Question을 확정 결정처럼 커밋
- 변경 이유 없이 기존 결정을 교체

## 8. Open Questions

- 문서별 PR을 사용할지 Blueprint 전체를 하나의 PR로 묶을지
- conventional commits 규칙을 전체 프로젝트에 강제할지
- 문서 버전을 수동으로 갱신할지

## 9. Related Documents

- `AI_COLLABORATION_WORKFLOW.md`
- `DOCUMENT_REVIEW_CHECKLIST.md`
- `CODEX_BLUEPRINT_REVIEW_PROMPT.md`

## 10. Change Log

- 2026-07-13: 최초 작성
