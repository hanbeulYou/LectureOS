# 예제 — Effective Transcript Consumption Boundary (GOAL-012)

이 예제는 downstream transcript 파생 작업이 **하나의 immutable transcript source**를 획득하는 첫 공유 소비 경계
(`040 §21`)를 보여줍니다: §20 resolver를 통한 유일한 해석, 소비 가능성 검증, immutable source identity에 의한
snapshot 로딩, 그리고 결정적 **consumption binding**.

> **중요:** 현재 authority ≠ 소비된 source ≠ historical lineage ≠ currentness ≠ 무결성. 작업은 움직이는 선택
> pointer가 아니라 정확한 immutable source에 고정됩니다. 이후 Reject·Raw 전환·선택 변경은 기존 binding을
> **변경·삭제·재해석하지 않으며**, currentness는 저장되지 않고 항상 **파생**됩니다. selected-but-inapplicable
> revision은 새 소비를 **명시적으로** 차단합니다(조용한 Raw fallback 없음). 이 슬라이스의 유일한 소비자는 중립
> manifest(`transcript_consumption_manifest`)이며 기존 subtitle/review/export 소비자는 전환되지 않습니다.
> **identity를 받습니다(경로 아님). `--force`는 없습니다.**

## 결정적 데모 (LLM/ASR 아님)

```text
Raw R1 선택 → consume(no-history raw) → replay(reused)
          → Candidate → Accept → Revision C1 → Select C1 → consume C1(created) → replay(reused)
          → Raw fallback → consume(같은 R1 source로 수렴; 중복 binding 없음)
          → re-Select C1 → Candidate Reject → 새 소비 차단(INAPPLICABLE), 기존 binding 불변·파생 stale
          → Raw R2 선택 → corrected 소비 차단(parent mismatch) → fallback → consume R2(created)
          → Repository Validation(healthy — staleness는 손상이 아님)
```

```bash
PYTHONPATH=src python3 -m lectureos.transcript_consumption_demo
```

- 세 개의 서로 다른 source(R1·C1·R2)가 각각 정확한 binding을 갖고, 같은 source 재소비는 `reused`로 수렴합니다.
- no-history와 명시적 fallback은 같은 Raw source를 낳지만 구분 가능한 provenance로 보존됩니다.
- 이후 Reject·Raw 전환은 어떤 binding도 바꾸지 않으며 currentness가
  `stale_due_to_selected_revision_inapplicability` / `stale_due_to_raw_selection_change`로 **파생**됩니다.
- content에서 파생된 golden(`expected/consumption-summary.json`)이 바이트 단위로 재현됩니다.

## CLI

```bash
# effective transcript input 해석(읽기 전용): resolver 상태·provenance·source·segment manifest
PYTHONPATH=src python3 -m lectureos.transcript_consumption_cli resolve-input \
  --intake transcript-source-intake:sha256:<digest> --database "$(pwd)/out/lectureos.sqlite3"

# manifest consumption binding 기록(또는 동일 source 재사용 수렴)
PYTHONPATH=src python3 -m lectureos.transcript_consumption_cli consume \
  --intake transcript-source-intake:sha256:<digest> --database "$(pwd)/out/lectureos.sqlite3"

# 저장된 binding과 파생 currentness 조회
PYTHONPATH=src python3 -m lectureos.transcript_consumption_cli status \
  --intake transcript-source-intake:sha256:<digest> --database "$(pwd)/out/lectureos.sqlite3"
```

## 예제 구조

```text
examples/transcript-consumption/
├── README.md
└── expected/
    └── consumption-summary.json   # 데모가 재현하는 결정적 golden (content-derived id)
```

자세한 계약은 `docs/040_TRANSCRIPT_PIPELINE.md §21`과 `implementation/102_EFFECTIVE_TRANSCRIPT_CONSUMPTION.md`를
참고하세요.
