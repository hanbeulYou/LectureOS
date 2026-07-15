# Implementation Workflow

- Status: Approved
- Baseline: LectureOS Blueprint v1
- Baseline Commit: `b0251cf56628f012891e39eebe7f57c2be63c684`
- Last Updated: 2026-07-16
- Depends On: `000_IMPLEMENTATION_DESIGN_GUIDE.md`, `010_PROJECT_LIFECYCLE.md`, `020_STORAGE_MODEL.md`, `030_EXECUTION_MODEL.md`, `040_INTERFACE_CONTRACTS.md`, `../docs/090_BLUEPRINT_RELEASE.md`
- Referenced By: Future implementation work

## Purpose

이 문서는 LectureOS Implementation Phase의 코드 작업, 검증, 독립 리뷰와 커밋 절차를 정의한다.

새 Product Contract나 구현 기능을 정의하지 않는다. 승인된 계약을 코드로 옮길 때 Codex와 Claude가 같은 기준과 범위를 사용하도록 작업 절차를 고정한다.

## 1. Authority and Roles

권위는 다음 순서를 따른다.

```text
Core Blueprint
        |
        v
Approved Implementation Design
        |
        v
Implementation
        |
        v
Code Review
```

- Core Blueprint는 Product Contract와 시스템 책임의 상위 기준선이다.
- Approved Implementation Design은 Blueprint를 구현 가능한 책임과 경계로 구체화한다.
- Implementation은 두 기준선을 코드와 테스트로 반영한다.
- Code Review는 구현이 상위 계약과 invariant를 지키는지 검증한다.
- Claude는 독립 Code Reviewer지만 Product Contract를 새로 결정하지 않는다.
- Codex는 Claude의 리뷰를 기계적으로 전부 반영하지 않고 근거에 따라 판정한다.
- 상위 계약이 불충분하면 `Requires Blueprint Clarification`으로, 구현 선택에 지속적인 판단이 필요하면 `Requires Architect Decision`으로 보고한다.

## 2. Official Workflow

### Step 1 — Define Scope

사용자 요청과 현재 repository 상태를 확인하고 이번 변경의 목표, 포함 파일과 제외 범위를 정한다.

- 기존 working tree 변경을 사용자 작업으로 취급하고 보존한다.
- 새로운 Product Contract가 필요한지 구현 전에 확인한다.
- 문서 변경과 코드 변경은 가능한 경우 별도 commit으로 계획한다.

### Step 2 — Read Governing Documents

항상 다음 기준선을 먼저 읽는다.

- `../docs/090_BLUEPRINT_RELEASE.md`
- `000_IMPLEMENTATION_DESIGN_GUIDE.md`

그다음 변경 책임과 직접 관련된 Blueprint, Approved Implementation Design, 기존 코드와 테스트를 읽는다. 승인되지 않은 Draft를 확정 계약처럼 사용하지 않는다.

### Step 3 — Implement

승인된 범위만 구현한다.

새 Product Contract가 필요하면 구현을 중단하고 `Requires Blueprint Clarification` 또는 필요한 Blueprint PATCH를 보고한다. 장기적인 구현 기준 선택이 필요하지만 승인된 설계로 결정할 수 없다면 `Requires Architect Decision`으로 보고한다.

### Step 4 — Test and Self Review

stage 전에 적용 가능한 다음 검증을 수행한다.

- build 또는 compile
- 관련 test
- 전체 regression test
- lint
- type check
- format
- `git diff --check`

구성되지 않은 도구는 임의로 추가하지 않고 미실행 사유를 보고한다. Codex는 staged review 전에 상위 계약, 변경 범위와 테스트 누락을 self-review한다.

### Step 5 — Stage Review Scope

현재 작업 파일만 명시적으로 stage한다.

```bash
git add <current-work-files>
git status --short
git diff --cached --name-status
git diff --cached --check
```

의도하지 않은 파일이 staged되면 Claude 리뷰 전에 staged 범위에서 제거한다. 전체 repository를 편의상 stage하지 않는다.

### Step 6 — Claude Review

다음 명령으로 독립 리뷰를 실행한다.

```bash
claude -p \
  --allowedTools "Read" "Glob" "Grep" "Bash(git diff:*)" "Bash(git status:*)" \
  --disallowedTools "Edit" "Write" \
  --max-turns 12 \
  "먼저 .claude/review-code.md를 읽고, 그 지침에 따라 현재 staged diff를 리뷰하라."
```

Claude를 실행할 수 없는 환경이면 다음 절차를 따른다.

1. Codex self-review를 수행한다.
2. 독립 리뷰를 실행하지 못한 사실과 원인을 보고한다.
3. 사용자가 독립 리뷰 없이 커밋하도록 명시적으로 승인한 경우에만 진행한다.

Claude 리뷰를 실행하지 않고 완료한 것으로 보고하지 않는다.

### Step 7 — Resolve Review

`.claude/review-fix.md`를 읽고 각 리뷰 항목을 다음 중 하나로 분류한다.

- Accepted
- Rejected with Evidence
- Requires Architect Decision
- Requires Blueprint Clarification

`Accepted` Blocking Issue와 필수 테스트 누락만 최소 수정한다. 수정 후 현재 작업 파일만 다시 stage한다.

### Step 8 — Revalidate

수정된 코드에 대해 Step 4의 적용 가능한 validation을 모두 다시 실행한다.

`.claude/review-fix.md`의 재리뷰 조건에 해당하면 Claude 리뷰를 다시 수행한다. 재리뷰에서도 Blocking Issue가 남으면 commit하지 않는다.

### Step 9 — Commit

다음 조건을 모두 만족할 때만 commit한다.

- 테스트와 적용 가능한 validation 통과
- 해결되지 않은 Blocking Issue 없음
- staged 범위가 작업 목표와 일치
- Blueprint 및 Approved Implementation Design 위반 없음
- working tree에 남은 변경 확인

하나의 commit은 하나의 의미를 가진다.

### Step 10 — Report

다음을 보고한다.

- 구현 요약
- 적용한 문서 기준
- 테스트와 validation 결과
- Claude Verdict
- 리뷰 항목의 분류와 처리 결과
- commit hash와 포함 파일
- 실행하지 못했거나 남은 validation
- 다음 제안 작업

## 3. Review Command

공식 로컬 리뷰 명령은 다음과 같다.

```bash
claude -p \
  --allowedTools "Read" "Glob" "Grep" "Bash(git diff:*)" "Bash(git status:*)" \
  --disallowedTools "Edit" "Write" \
  --max-turns 12 \
  "먼저 .claude/review-code.md를 읽고, 그 지침에 따라 현재 staged diff를 리뷰하라."
```

Claude 결과를 Codex가 처리할 때 다음 지침을 사용한다.

```text
먼저 .claude/review-fix.md를 읽어라.

방금 받은 Claude Code Review의 각 항목을
Accepted,
Rejected with Evidence,
Requires Architect Decision,
Requires Blueprint Clarification
중 하나로 분류하라.

Accepted Blocking Issue만 최소 수정하고
전체 테스트를 다시 실행하라.
```

## 4. Review Failure Policy

Claude가 `CHANGES REQUIRED`를 반환하면 인정된 Blocking Issue를 해결하기 전 commit하지 않는다.

Claude 지적이 잘못됐다고 판단하면 `Rejected with Evidence`로 기록하고 다음 중 적절한 절차를 따른다.

- 근거를 제공해 Claude 재리뷰 수행
- Requires Architect Decision 요청
- Requires Blueprint Clarification 요청

Claude 실행 자체가 실패하면 실패 원인을 기록하고 임의로 `PASS`로 간주하지 않는다.

## 5. Scope Safety

- Claude 리뷰를 위해 전체 repository를 무조건 stage하지 않는다.
- 현재 작업 파일만 stage한다.
- staged되지 않은 사용자 변경을 수정하거나 리뷰 범위에 포함하지 않는다.
- untracked 파일은 현재 작업 범위인지 확인한 뒤 명시적으로 stage한다.
- 문서와 코드 변경은 가능한 경우 별도 commit으로 분리한다.
- 리뷰 대응 수정이 작업 범위를 넓히면 중단하고 새 범위를 보고한다.

## 6. Emergency Exception

다음 상황에서만 독립 Claude 리뷰 없이 commit할 수 있다.

- 사용자가 명시적으로 생략을 승인했다.
- 사소한 문서 오탈자다.
- 빌드나 테스트에 영향을 주지 않는 링크 수정이다.
- 리뷰 도구 장애 중 긴급 수정이 필요하다.

이 경우 commit 보고에 리뷰 생략 사유와 수행한 대체 검증을 기록한다.

## 7. Validation Criteria

- Core Blueprint와 Approved Implementation Design의 권위가 리뷰보다 우선하는가?
- Claude가 staged diff만 현재 변경 범위로 검토하는가?
- unstaged와 untracked 변경을 별도로 보고하는가?
- Claude에게 Edit 또는 Write 권한을 허용하지 않는가?
- Verdict가 Blocking Issue 존재 여부에 따라 결정되는가?
- Codex가 Claude 지적을 근거에 따라 분류하는가?
- 실질적인 리뷰 수정 뒤 재검증과 재리뷰가 수행되는가?
- 테스트와 self-review가 stage 및 독립 리뷰보다 먼저 수행되는가?
- commit 전에 staged 범위와 남은 working tree 변경을 확인하는가?

## 8. Non-Goals

이 Workflow는 다음을 정의하지 않는다.

- CI provider
- GitHub branch protection
- Pull Request platform
- Claude model version
- programming language
- package manager
- release automation
- deployment workflow

## Related Documents

- [LectureOS Blueprint v1 Release](../docs/090_BLUEPRINT_RELEASE.md)
- [Implementation Design Guide](000_IMPLEMENTATION_DESIGN_GUIDE.md)
- [Project Lifecycle](010_PROJECT_LIFECYCLE.md)
- [Storage Model](020_STORAGE_MODEL.md)
- [Execution Model](030_EXECUTION_MODEL.md)
- [Interface Contracts](040_INTERFACE_CONTRACTS.md)
- [Claude Code Review Instructions](../.claude/review-code.md)
- [Claude Code Review Resolution Instructions](../.claude/review-fix.md)
