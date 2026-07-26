# 예제 — Transcript Correction Candidate Admission

이 예제는 현재 선택된 **Raw Transcript**의 한 segment에 대한 **제안된 교정을 적용하지 않고 기록**하는 첫 슬라이스
(`040 §17`)를 보여줍니다. Correction Candidate는 **제안**이며 canonical transcript 내용이 아닙니다.

> **중요:** admission은 intake가 **ready**(유효한 current Raw Transcript 선택, §16)일 것을 요구하고, 후보는 그 current
> Raw Transcript의 한 **immutable segment**를 target합니다. **source-text snapshot**은 persist된 segment text와 정확히
> 일치해야 합니다(stale 감지). admission은 Raw Transcript text를 **결코 바꾸지 않고**, current 선택을 바꾸지 않으며,
> corrected revision·decision을 만들지 않고, 후보를 **적용·수락·ranking하지 않습니다.** intake·raw transcript·segment
> **identity를 받습니다(파일 경로가 아님)**. `--apply` 옵션은 없습니다.

## 결정적 데모 (LLM/규칙 엔진 아님)

fake provider 결과와 수동(manual) 후보로 전체 흐름을 재현합니다:

```text
Fixture Source Media → Transcript Intake → Provider Result → Raw Transcript
                    → Current Raw Transcript Selection
                    → Candidate A for Segment 1 → replay A → Candidate B for Segment 1
                    → candidate listing → switch current Raw Transcript
                    → historical 후보는 보존되나 새 current에 not-applicable → Repository Validation
```

```bash
PYTHONPATH=src python3 -m lectureos.correction_candidate_demo
```

- readiness가 필요하고, 후보는 특정 immutable segment를 target하며 source text는 변경되지 않습니다.
- 동일 후보 재admission은 idempotent(`reused`), 같은 참조에 다른 내용은 conflict로 거부됩니다.
- 하나의 segment에 여러 distinct 후보가 공존하고, 어떤 후보도 ranking·적용되지 않습니다.
- current Raw Transcript 전환 후에도 historical 후보는 보존되며 새 current에 not-applicable로 표시됩니다.
- stale(snapshot 불일치)·not-current admission은 거부됩니다. 저장소는 무결성 검증을 통과합니다.
- content에서 파생된 golden(`expected/candidate-summary.json`)이 바이트 단위로 재현됩니다
  (`tests/test_correction_candidate_demo.py`).

## CLI

```bash
# 제안 교정 admit (적용되지 않음)
PYTHONPATH=src python3 -m lectureos.correction_candidate_cli admit \
  --intake transcript-source-intake:sha256:<digest> \
  --input candidate.json --database "$(pwd)/out/lectureos.sqlite3"

# admit된 후보 목록 (current 선택에 대한 applicability 포함, ranking 없음)
PYTHONPATH=src python3 -m lectureos.correction_candidate_cli list \
  --intake transcript-source-intake:sha256:<digest> --database "$(pwd)/out/lectureos.sqlite3"
```

`candidate.json`의 형태:

```json
{
  "raw_transcript_id": "raw-transcript:<digest>",
  "segment_id": "transcript-segment:<digest>:0",
  "candidate_ref": "c1",
  "source_type": "manual",
  "source_reference": "human:editor-1",
  "proposed_text": "안녕하세요 여러분",
  "source_text_snapshot": "안녕하세요 여러부",
  "rationale": "맞춤법 교정"
}
```

## 예제 구조

```text
examples/correction-candidate/
├── README.md
└── expected/
    └── candidate-summary.json   # 데모가 재현하는 결정적 golden (content-derived id)
```

자세한 계약은 `docs/040_TRANSCRIPT_PIPELINE.md §17`과 `implementation/098_CORRECTION_CANDIDATE_ADMISSION.md`를
참고하세요.
