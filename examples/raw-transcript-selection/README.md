# 예제 — Current Raw Transcript Selection & Readiness

이 예제는 하나의 **Transcript Source Intake**가 여러 admitted **Raw Transcript**를 가질 때, 그중 **어느 것이
downstream의 현재 authoritative 입력인지**를 명시적으로 선택·전환하고 intake의 **readiness**를 노출하는 슬라이스
(`040 §16`)를 보여줍니다.

> **중요:** selection은 명시적 repository authority 결정입니다. provider 이름·model 크기·wall-clock·길이·confidence로
> **추론하지 않으며** 어떤 후보도 "best"로 표시하지 않습니다. selection은 ASR 품질을 비교하거나 transcript 내용을
> 바꾸거나 Correction을 실행하지 않습니다. 전환(switch)은 append-only이며 이전 record·비선택 transcript를 삭제하지
> 않습니다. intake·raw transcript **identity를 받습니다(파일 경로가 아님)**.

## 무엇을 보여주나

```text
Fixture Source Media → Transcript Intake
  → Provider Result A → Raw Transcript A
  → Provider Result B → Raw Transcript B
  → candidate 목록 (identity 순, ranking 없음)
  → select A → ready → switch to B → ready
  → Repository Validation (healthy)
```

- 하나의 intake가 서로 다른 여러 Raw Transcript 후보를 가지며, 후보는 identity로 정렬됩니다(provider/model 크기가
  아님 — 예제에서 A의 model이 `large`, B가 `tiny`지만 정렬은 identity 기준).
- 선택 전 readiness는 `not_ready`, 선택 후 `ready`입니다. 동일 선택 반복은 idempotent(`reused`)입니다.
- 전환은 current authority를 바꾸되 이전 record를 보존합니다(append-only, sequence 증가).
- 다른 intake의 Raw Transcript 선택은 명시적으로 거부됩니다. 저장소는 무결성 검증을 통과합니다.

## 실행 방법

CLI(세 서브커맨드):

```bash
PYTHONPATH=src python3 -m lectureos.raw_transcript_selection_cli candidates \
  --intake transcript-source-intake:sha256:<digest> --database "$(pwd)/out/lectureos.sqlite3"

PYTHONPATH=src python3 -m lectureos.raw_transcript_selection_cli select \
  --intake transcript-source-intake:sha256:<digest> \
  --transcript raw-transcript:<digest> --database "$(pwd)/out/lectureos.sqlite3"

PYTHONPATH=src python3 -m lectureos.raw_transcript_selection_cli readiness \
  --intake transcript-source-intake:sha256:<digest> --database "$(pwd)/out/lectureos.sqlite3"
```

결정적 데모(fake provider 결과, 실제 ASR 아님):

```bash
PYTHONPATH=src python3 -m lectureos.raw_transcript_selection_demo
```

## 예제 구조

```text
examples/raw-transcript-selection/
├── README.md
└── expected/
    └── selection-summary.json   # 데모가 재현하는 결정적 golden (content-derived id)
```

fixture는 `examples/media-import/fixtures/`의 바이너리를 재사용합니다. identity가 content에서 파생되므로
`selection-summary.json`은 바이트 단위로 결정적이며 `tests/test_raw_transcript_selection_demo.py`가 이를 재현합니다.

자세한 계약은 `docs/040_TRANSCRIPT_PIPELINE.md §16`과 `implementation/097_RAW_TRANSCRIPT_SELECTION.md`를 참고하세요.
