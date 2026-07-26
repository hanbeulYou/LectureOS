# 예제 — First Corrected Transcript Revision (GOAL-010)

이 예제는 **현재 Accepted**(§18)인 하나의 교정 후보(§17)를 source Raw Transcript에 **명시적으로 적용**하여 하나의
**immutable Corrected Transcript Revision**을 만드는 첫 슬라이스(`040 §19`)를 보여줍니다.

> **중요:** 수락은 권한 부여이고 생성은 적용입니다 — **Accept만으로 revision이 생기지 않습니다.** 생성은 정확히
> 하나의 후보를 지명하는 명시적 명령이며, 결과 revision은 **current로 선택되지 않습니다**(Current Corrected Revision
> Selection은 GOAL-011). Raw Transcript·후보·결정 history·current 선택은 변경되지 않고, revision은 immutable하며
> 이후 Reject가 와도 historical revision은 보존됩니다. **candidate identity를 받습니다(경로 아님).**
> `--force`/`--apply-all` 같은 옵션은 없습니다.

## 결정적 데모 (LLM/ASR 아님)

```text
Fixture Source Media → Transcript Intake → Provider Result → Raw Transcript
                    → Current Raw Transcript Selection → Correction Candidate
                    → generate(Undecided: 차단) → Accept → 명시적 Generate → Corrected Revision
                    → replay Generate(reused) → Reject → generate(차단) → revision 보존
                    → Repository Validation
```

```bash
PYTHONPATH=src python3 -m lectureos.corrected_revision_demo
```

- 생성은 현재 Accepted authority를 요구하고(Undecided/Rejected 차단), 수락만으로는 아무것도 생성되지 않습니다.
- revision은 의도한 교정만 담습니다: 교정 segment는 `replaces_segment_id`를 가진 새 segment(timing 보존), 비변경
  segment는 그대로 참조되고 Raw Transcript는 byte 단위로 불변입니다.
- 동일 요청 재실행은 `reused`(하나의 revision만 존재), 이후 Reject는 새 생성만 차단하며 기존 revision은 보존됩니다.
- revision은 current가 아니며 저장소는 무결성 검증을 통과합니다. content에서 파생된
  golden(`expected/revision-summary.json`)이 바이트 단위로 재현됩니다(`tests/test_corrected_revision_demo.py`).

## CLI

```bash
# 현재 Accepted 후보를 명시적으로 적용 (revision은 current로 선택되지 않음)
PYTHONPATH=src python3 -m lectureos.corrected_revision_cli generate \
  --candidate correction-candidate:<digest> --database "$(pwd)/out/lectureos.sqlite3"

# revision 내용/lineage 조회
PYTHONPATH=src python3 -m lectureos.corrected_revision_cli show \
  --revision corrected-revision:<digest> --database "$(pwd)/out/lectureos.sqlite3"

# 후보의 generation 목록
PYTHONPATH=src python3 -m lectureos.corrected_revision_cli list \
  --candidate correction-candidate:<digest> --database "$(pwd)/out/lectureos.sqlite3"
```

## 예제 구조

```text
examples/corrected-revision/
├── README.md
└── expected/
    └── revision-summary.json   # 데모가 재현하는 결정적 golden (content-derived id)
```

자세한 계약은 `docs/040_TRANSCRIPT_PIPELINE.md §19`와 `implementation/100_CORRECTED_REVISION_GENERATION.md`를
참고하세요.
