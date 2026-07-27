# 예제 — Effective Subtitle Final Selection (GOAL-016)

이 예제는 effective transcript 계약 세대의 **Final Selection authority**를 보여줍니다: 파생 eligibility(현재
적용 가능한 Accept 필수) → 명시적 select → append-only 선택(정확한 candidate·subject·지원 Accept·selector
lineage) → 파생 current selection → 파생 applicability.

> **중요:** Accept ≠ Final Selection ≠ export. Accept decision은 선택을 만들지 않고, 선택은 export 적격성을
> 부여하지 않습니다(export는 이후 Goal). reject/modify/superseded Accept/stale subject는 새 선택에 결코
> 적격하지 않으며, 기존 역사적 선택은 불변으로 보존되고 applicability만 파생됩니다
> (applicable/superseded/supporting_decision_superseded/stale_due_to_candidate_source/unresolvable). 지원
> Accept가 바뀌면 명시적 재선택은 **새 lineage로 append**됩니다(옛 선택의 조용한 재사용 금지). selector는
> 명시적 provenance이며 reviewer로부터 추론되지 않습니다. legacy final selection·export는 읽지도 쓰지도
> 않습니다. **identity를 받습니다(경로 아님). `--force`는 없습니다.**

## 결정적 데모 (LLM/ASR 아님)

```text
Accept → eligibility(yes) → select(current+applicable) → replay(reused)
      → Reject/Modify/superseded Accept → 선택 명시적 거부(아무것도 저장 안 됨)
      → 새 Accept → 재선택 → 새 lineage append
      → 다른 candidate 선택 → append·supersede·history 불변
      → authority 변경 → applicability 파생·자동 재선택 없음
      → 동일 내용·다른 candidate → 별개 선택 identity
      → 손상된 graph → 선택 거부 → export/legacy 격리 → Validation healthy
```

```bash
PYTHONPATH=src python3 -m lectureos.effective_selection_demo
```

- content에서 파생된 golden(`expected/selection-summary.json`)이 바이트 단위로 재현됩니다.

## CLI

```bash
PYTHONPATH=src python3 -m lectureos.effective_selection_cli eligibility --review-subject subtitle-effective-review-subject:<digest> --database "$(pwd)/out/lectureos.sqlite3"
PYTHONPATH=src python3 -m lectureos.effective_selection_cli select      --review-subject subtitle-effective-review-subject:<digest> --selector selector:kim --database "$(pwd)/out/lectureos.sqlite3"
PYTHONPATH=src python3 -m lectureos.effective_selection_cli show        --selection subtitle-effective-final-selection:<digest> --database "$(pwd)/out/lectureos.sqlite3"
PYTHONPATH=src python3 -m lectureos.effective_selection_cli history     --intake transcript-source-intake:sha256:<digest> --database "$(pwd)/out/lectureos.sqlite3"
PYTHONPATH=src python3 -m lectureos.effective_selection_cli current     --intake transcript-source-intake:sha256:<digest> --database "$(pwd)/out/lectureos.sqlite3"
PYTHONPATH=src python3 -m lectureos.effective_selection_cli status      --selection subtitle-effective-final-selection:<digest> --database "$(pwd)/out/lectureos.sqlite3"
```

## 예제 구조

```text
examples/effective-selection/
├── README.md
└── expected/
    └── selection-summary.json   # 데모가 재현하는 결정적 golden (content-derived id)
```

자세한 계약은 `implementation/106_EFFECTIVE_SUBTITLE_FINAL_SELECTION.md`를 참고하세요.
