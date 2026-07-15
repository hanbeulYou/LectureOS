# LectureOS Code Review Resolution Instructions

## Purpose

Claude의 리뷰 결과를 기계적으로 적용하지 않고 Core Blueprint, Approved Implementation Design과 실제 코드 근거에 따라 판정한다.

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

Codex와 Claude는 상위 계약을 변경할 권한이 없다. 수정이 상위 계약과 충돌하거나 계약만으로 판단할 수 없다면 임의로 우회하지 않는다.

## Classification

Claude의 각 지적을 다음 중 하나로 분류한다.

### Accepted

실제 계약 위반, correctness 문제 또는 현재 변경에 필요한 테스트 누락이다.

- Blocking으로 인정한다.
- 문제를 해결하는 최소 범위만 수정한다.
- 회귀를 막는 테스트를 추가하거나 보강한다.

### Rejected with Evidence

지적이 실제 코드나 상위 계약과 맞지 않는다.

다음 근거를 구체적으로 제시한다.

- 관련 Blueprint 또는 Approved Implementation Design 조항
- 관련 코드 위치와 실제 동작
- 재현 결과 또는 기존 테스트
- 지적한 실패 시나리오가 성립하지 않는 이유

근거 없이 선호나 직관만으로 거부하지 않는다.

### Requires Architect Decision

Blueprint 의미를 바꾸지는 않지만 둘 이상의 구현 방식이 가능하고, 선택이 이후 구조나 운영 책임에 지속적인 영향을 준다.

- 현재 변경에서 임의로 확정하지 않는다.
- 선택지, trade-off와 영향 범위를 보고한다.
- Architect Decision 전까지 안전하게 보류할 수 있는 범위를 명시한다.

### Requires Blueprint Clarification

Core Blueprint가 불충분하거나 문서 간 의미가 충돌해 구현에서 확정할 수 없다.

- 코드 편의를 위해 Product Contract를 만들지 않는다.
- 관련 문서와 충돌 지점을 기록한다.
- 필요한 경우 Blueprint PATCH가 필요함을 보고한다.

## Resolution Procedure

1. Claude가 실제로 검토한 staged diff와 문서 범위를 확인한다.
2. 각 Blocking Issue, Missing Test와 기타 판단 항목을 독립적으로 검증한다.
3. 각 항목을 네 가지 분류 중 하나로 기록한다.
4. `Accepted`로 판정한 Blocking Issue와 필수 테스트 누락만 최소 수정한다.
5. 수정 후 관련 테스트와 전체 regression validation을 다시 실행한다.
6. staged 범위를 현재 작업 파일로 다시 구성하고 `git diff --cached --check`를 수행한다.
7. 수정이 실질적이거나 기존 Verdict의 근거를 바꿨다면 Claude 재리뷰를 수행한다.

## Re-Review Rules

다음 중 하나에 해당하면 Claude 재리뷰가 필요하다.

- `Accepted` Blocking Issue를 수정했다.
- public boundary, Domain identity 또는 lifecycle rule이 변경됐다.
- 리뷰 대응 중 원래 staged 범위를 넘어선 코드가 변경됐다.
- 기존 테스트만으로 수정된 invariant를 검증할 수 없어 새 테스트를 추가했다.
- `Rejected with Evidence` 판단에 대해 독립 검증이 필요하다.

오탈자나 설명 주석처럼 실행 의미를 바꾸지 않는 수정만 있었다면 재리뷰를 생략할 수 있으며 그 이유를 보고한다.

## Resolution Output

리뷰 처리 결과는 다음을 포함한다.

```text
## Review Verdict Received

PASS 또는 CHANGES REQUIRED

## Resolution

각 항목:

- Review Item
- Classification
- Evidence
- Action Taken
- Validation

## Re-Review

- Required: Yes 또는 No
- Reason
- Result 또는 Pending

## Remaining Decisions

Requires Architect Decision 또는 Requires Blueprint Clarification 항목을 기록한다.

없으면:

None.
```

## Guardrails

- Claude가 제안했다는 이유만으로 상위 계약을 변경하지 않는다.
- 리뷰 수정 과정에서 새로운 기능이나 무관한 리팩터링을 추가하지 않는다.
- `Rejected with Evidence`를 리뷰 회피 수단으로 사용하지 않는다.
- `Requires Architect Decision`을 사소한 구현 판단에 남용하지 않는다.
- `Requires Blueprint Clarification`을 하위 구현에서 확정 사항으로 바꾸지 않는다.
- Human Decision과 과거 provenance를 리뷰 수정 과정에서 덮어쓰지 않는다.
