# 예제 — Explicit Lecture Analysis Input Admission (GOAL-023)

이 예제는 042 Milestone 1의 **durable half**를 보여줍니다: 명시적 명령이 intake의 현재 effective
transcript authority(042 §5.1의 validated selected Corrected Transcript + Source Timeline + Source
Media reference)를 **불변·identity 소유·provenance 보존** analysis input 기록으로 admit합니다.

> **중요:** Admission ≠ Analysis Execution. Analysis Run·ProcessingRun·Finding·AI reasoning은 이
> 계약에 없습니다. 모든 admission은 GOAL-022 파생 eligibility를 **명령 시점에 재검증**하며(이전 결과를
> 신뢰하지 않음 — advisory/TOCTOU 경계 폐쇄), ineligible이면 아무것도 persist하지 않습니다. identity는
> released GOAL-012 binding 규칙을 따라 정확한 불변 source(계약, intake, corrected revision)에서만
> 파생됩니다 — 같은 authority의 재admission은(동시 요청·authority가 갔다가 돌아온 경우 포함) 기존 기록으로
> 멱등 수렴하고, 바뀐 authority는 **새** 기록을 append하며 이전 기록은 불변 history로 남습니다
> (append-only; 수정·삭제 없음). fingerprint 불일치는 명시적 integrity conflict입니다. wall-clock·경로·
> rowid는 어디에도 참여하지 않습니다. legacy `eligible_analysis_inputs`(실행 결합형 042 구현)는 결코 읽거나
> 쓰지 않습니다.

## 결정적 데모 (LLM/ASR/네트워크 없음; 쓰기는 admission 테이블뿐)

```bash
PYTHONPATH=src python3 -m lectureos.analysis_input_admission_demo
```

- ineligible 거부(무기록) → eligible admit(정확한 snapshot) → replay(reused·행 불변) → authority 변경(새
  기록·이전 기록 불변·superseded 파생) → authority 복귀(기존 기록 수렴) → 재시작 동일 재구성 → legacy·실행
  격리 → Validation healthy(superseded admission은 손상이 아님).
- content에서 파생된 golden(`expected/admission-summary.json`)이 바이트 단위로 재현됩니다.

## CLI

```bash
PYTHONPATH=src python3 -m lectureos.analysis_input_admission_cli admit  --intake transcript-source-intake:sha256:<digest> --database /path/to/lectureos.sqlite3
PYTHONPATH=src python3 -m lectureos.analysis_input_admission_cli show   --admission lecture-analysis-input:<digest> --database /path/to/lectureos.sqlite3
PYTHONPATH=src python3 -m lectureos.analysis_input_admission_cli status --admission lecture-analysis-input:<digest> --database /path/to/lectureos.sqlite3
PYTHONPATH=src python3 -m lectureos.analysis_input_admission_cli list   --intake transcript-source-intake:sha256:<digest> --database /path/to/lectureos.sqlite3
```

## 예제 구조

```text
examples/analysis-input-admission/
├── README.md
└── expected/
    └── admission-summary.json   # 데모가 재현하는 결정적 golden
```

자세한 계약은 `implementation/113_LECTURE_ANALYSIS_INPUT_ADMISSION.md`를 참고하세요.
