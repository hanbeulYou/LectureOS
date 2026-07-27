# 예제 — Effective-Source Subtitle Human Decisions (GOAL-015)

이 예제는 effective transcript 계약 세대에 대한 Human Authority를 보여줍니다: 명시적 명령이 정확히 하나의
immutable `EffectiveSubtitleReviewSubject`에 대해 진실한 `HumanActorReference`의 Accept/Reject/Modify 판단을
append-only로 기록합니다 — GOAL-009 authority idiom의 정확한 재사용.

> **중요:** Review Subject 존재 ≠ Decision 존재 ≠ current Decision ≠ Decision 적용 가능성 ≠ final selection ≠
> export 적격성. Decision은 authority만 기록합니다 — Accept는 final selection/export를 만들지 않고, Reject는
> 아무것도 삭제하지 않으며, Modify는 아무것도 편집하지 않습니다(수정된 자막 저작은 별도 Goal). 현재
> authority와 같은 kind의 요청은 idempotent하게 **reused**되고(GOAL-009 규칙: authority는 상태), 판단이 바뀌면
> sequence+1로 **append**되어 이전 record를 supersede합니다(변경·삭제 없음). current decision은 최고 sequence로
> **파생**되며(최신 row 휴리스틱·mutable flag 금지), applicability(applicable/superseded/
> stale_due_to_candidate_source/unresolvable)도 파생됩니다 — kind는 applicability가 아닙니다(reject/modify도
> current+applicable일 수 있음). reviewer는 명시적 provenance이며 authorization이 아닙니다.
> **identity를 받습니다(경로 아님). `--force`는 없습니다.**

## 결정적 데모 (LLM/ASR 아님)

```text
accept → replay(reused) → 타 actor 동일 intent(reused)
      → corrected subject: reject(current+applicable) → modify(authority only) → accept(supersedes)
      → history [reject, modify, accept]·current 파생·reject는 superseded
      → authority 변경 → decision들은 불변 history·stale 파생·자동 decision 없음
      → 동일 내용·다른 subject → 별개 decision identity
      → 손상된 candidate graph → decision 명시적 거부(아무것도 저장 안 됨)
      → Repository Validation healthy
```

```bash
PYTHONPATH=src python3 -m lectureos.effective_decision_demo
```

- content에서 파생된 golden(`expected/decision-summary.json`)이 바이트 단위로 재현됩니다.
- 데모는 legacy decision·review·final selection·export record가 전혀 생기지 않음을 검증합니다.

## CLI

```bash
PYTHONPATH=src python3 -m lectureos.effective_decision_cli decide --review-subject subtitle-effective-review-subject:<digest> --decision accept --reviewer reviewer:kim --database "$(pwd)/out/lectureos.sqlite3"
PYTHONPATH=src python3 -m lectureos.effective_decision_cli show    --decision subtitle-effective-review-decision:<digest> --database "$(pwd)/out/lectureos.sqlite3"
PYTHONPATH=src python3 -m lectureos.effective_decision_cli history --review-subject subtitle-effective-review-subject:<digest> --database "$(pwd)/out/lectureos.sqlite3"
PYTHONPATH=src python3 -m lectureos.effective_decision_cli current --review-subject subtitle-effective-review-subject:<digest> --database "$(pwd)/out/lectureos.sqlite3"
PYTHONPATH=src python3 -m lectureos.effective_decision_cli status  --decision subtitle-effective-review-decision:<digest> --database "$(pwd)/out/lectureos.sqlite3"
```

## 예제 구조

```text
examples/effective-decision/
├── README.md
└── expected/
    └── decision-summary.json   # 데모가 재현하는 결정적 golden (content-derived id)
```

자세한 계약은 `implementation/105_EFFECTIVE_SUBTITLE_REVIEW_DECISION.md`를 참고하세요.
