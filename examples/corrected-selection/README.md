# 예제 — Current Corrected Revision Selection (GOAL-011)

이 예제는 §19의 immutable **Corrected Revision** 중 **어느 것이 현재 선택되었는지**를 명시적·append-only로
결정하고, 명시적 **Raw Transcript fallback**과 결정적 **effective transcript resolver**를 제공하는 첫 슬라이스
(`040 §20`)를 보여줍니다.

> **중요:** Revision 존재 ≠ 선택 ≠ 적용 가능성 ≠ effective 해석. revision은 생성만으로 current가 되지 않으며
> (자동 promotion 금지), 선택은 revision·후보·결정·Raw Transcript·Raw 선택을 **변경하지 않습니다.** history는
> append-only이고 current는 최고 sequence로 파생됩니다. 이후 후보 Reject나 Raw 선택 전환은 선택된 revision을
> **inapplicable**하게 만들 뿐 history를 바꾸지 않으며, resolver는 이를 **명시적으로** 보고합니다(조용한 fallback
> 없음). **identity를 받습니다(경로 아님). `--force`는 없습니다.**

## 결정적 데모 (LLM/ASR 아님)

```text
Raw Transcript → Candidate A/B → Accept → Revision A/B 생성(자동 선택 없음)
             → Select A → resolve(corrected) → replay(reused)
             → Select B(changed) → Raw Fallback(changed) → resolve(raw) → re-Select A(changed)
             → Candidate A Reject → history 불변·resolver INAPPLICABLE·재선택 차단 → Repository Validation
```

```bash
PYTHONPATH=src python3 -m lectureos.corrected_selection_demo
```

- 선택 전 상태는 no-history이며 resolver는 Raw를 반환합니다. 명시적 fallback은 history 부재와 구분되는 authority
  사실입니다.
- 동일 대상 재선택은 `reused`, 전환은 append(전체 history 보존, 4개 transition), 어떤 revision도 삭제·변경되지
  않습니다.
- 이후 Reject: 선택 history는 불변, resolver는 `candidate_not_accepted` 이유와 함께 INAPPLICABLE을 보고하고, 그
  revision의 **새** 선택은 차단됩니다. 저장소는 무결성 검증을 통과합니다.
- content에서 파생된 golden(`expected/selection-summary.json`)이 바이트 단위로 재현됩니다.

## CLI

```bash
# 현재 corrected revision 선택 (문맥은 revision lineage에서 파생)
PYTHONPATH=src python3 -m lectureos.corrected_selection_cli select \
  --revision corrected-revision:<digest> --reviewer selector:kim --database "$(pwd)/out/lectureos.sqlite3"

# 명시적 Raw Transcript fallback
PYTHONPATH=src python3 -m lectureos.corrected_selection_cli fallback \
  --intake transcript-source-intake:sha256:<digest> --reviewer selector:kim --database "$(pwd)/out/lectureos.sqlite3"

# 상태 / append-only history / effective transcript 해석
PYTHONPATH=src python3 -m lectureos.corrected_selection_cli status  --intake transcript-source-intake:sha256:<digest> --database "$(pwd)/out/lectureos.sqlite3"
PYTHONPATH=src python3 -m lectureos.corrected_selection_cli history --intake transcript-source-intake:sha256:<digest> --database "$(pwd)/out/lectureos.sqlite3"
PYTHONPATH=src python3 -m lectureos.corrected_selection_cli resolve --intake transcript-source-intake:sha256:<digest> --database "$(pwd)/out/lectureos.sqlite3"
```

## 예제 구조

```text
examples/corrected-selection/
├── README.md
└── expected/
    └── selection-summary.json   # 데모가 재현하는 결정적 golden (content-derived id)
```

자세한 계약은 `docs/040_TRANSCRIPT_PIPELINE.md §20`과 `implementation/101_CORRECTED_REVISION_SELECTION.md`를
참고하세요.
