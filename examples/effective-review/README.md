# 예제 — Effective-Source Subtitle Review Preparation (GOAL-014)

이 예제는 effective transcript 계약 세대의 첫 downstream 단계를 보여줍니다: 명시적 요청이 정확히 하나의
immutable `EffectiveSubtitleCandidate` graph를 immutable **Review Subject**로 준비합니다 — "정확히 이
candidate graph가 review를 위해 제시되었다"는 역사적 사실.

> **중요:** Candidate 존재 ≠ review 준비 ≠ review record ≠ Human Decision ≠ final selection ≠ export 적격성.
> Review Subject는 어떤 authority도 부여하지 않습니다 — Human Decision·reviewer·승인/거부/완료 상태·final
> selection·export·legacy review record는 만들어지지 않습니다. Subject는 정확한 candidate graph에
> binding됩니다(candidate FK + 결정적 graph fingerprint — integrity anchor이며 authority 아님). identity는
> 결정적이고(candidate + preparation 계약; timestamp·reviewer·latest 금지), 동일 candidate 재준비는
> `reused`이며, 내용이 같아도 candidate가 다르면 별개 subject입니다. source-stale candidate도 구조적으로
> 유효하면 명시적으로 준비할 수 있고(역사적 검토 가능성 ≠ 현재 결정 적용 가능성) staleness는 저장되지 않고
> 파생됩니다. **identity를 받습니다(경로 아님). `--force`는 없습니다.**

## 결정적 데모 (LLM/ASR 아님)

```text
Raw candidate S1 → prepare → R1(current) → replay(reused)
             → Accept → Corrected → S2 → prepare → 별개 R2(교정 binding·Raw parent lineage)
             → Raw fallback → S1 재사용 → prepare → 원래 R1 재사용
             → 동일 내용 Raw → S3 → prepare → 별개 R3
             → authority 변경(재선택·Reject) → R1/R2 불변·stale 파생·자동 재준비 없음
             → 손상된 candidate graph → 준비 명시적 거부(아무것도 저장 안 됨)
             → Repository Validation healthy
```

```bash
PYTHONPATH=src python3 -m lectureos.effective_review_demo
```

- content에서 파생된 golden(`expected/review-summary.json`)이 바이트 단위로 재현됩니다.
- 데모는 Human Decision·reviewer·legacy review·final selection·export record가 전혀 생기지 않음을 검증합니다.

## CLI

```bash
PYTHONPATH=src python3 -m lectureos.effective_review_cli prepare --candidate subtitle-effective-candidate:<digest> --database "$(pwd)/out/lectureos.sqlite3"
PYTHONPATH=src python3 -m lectureos.effective_review_cli show   --review-subject subtitle-effective-review-subject:<digest> --database "$(pwd)/out/lectureos.sqlite3"
PYTHONPATH=src python3 -m lectureos.effective_review_cli list   --candidate subtitle-effective-candidate:<digest> --database "$(pwd)/out/lectureos.sqlite3"
PYTHONPATH=src python3 -m lectureos.effective_review_cli status --review-subject subtitle-effective-review-subject:<digest> --database "$(pwd)/out/lectureos.sqlite3"
```

## 예제 구조

```text
examples/effective-review/
├── README.md
└── expected/
    └── review-summary.json   # 데모가 재현하는 결정적 golden (content-derived id)
```

자세한 계약은 `docs/041_SUBTITLE_PIPELINE.md §15`와
`implementation/104_EFFECTIVE_SUBTITLE_REVIEW_PREPARATION.md`를 참고하세요.
