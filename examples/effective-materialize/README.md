# 예제 — Effective SRT Physical Materialization (GOAL-018)

이 예제는 effective transcript 계약 세대의 **물리 materialization 경계**를 보여줍니다: 명시적 요청이 승인된
Storage Root 아래에 논리 artifact의 정확한 canonical bytes(UTF-8·LF·BOM 없음)를 실현하고, released
record-first 규율(intent가 쓰기 **전에** durable, 종결 outcome이 쓰기 후에 기록, 상태는 파생)을 그대로
따릅니다.

> **중요:** Artifact ≠ Materialization ≠ delivery. artifact identity는 경로에 의존하지 않으며 relative
> location은 한 write event의 provenance입니다. 같은 artifact/location/payload 재요청은 파일을 다시 쓰지 않고
> **reused**되고, 기존의 다른 파일은 기본적으로 거부되어 정직한 FAILED outcome으로 기록되며(파일 불변), 오직
> 명시적 `--overwrite`만 새 append-only write event로 교체합니다. 물리 파일 삭제는 어떤 record도 변경하지
> 않고(파일 상태 ≠ 논리 history), superseded된 역사적 artifact도 여전히 materialize할 수 있습니다.
> delivery·publication·URL은 이 계약에 없습니다. **`--force`는 없습니다.**

## 결정적 데모 (LLM/ASR 아님; 쓰기는 격리된 Storage Root 아래에만)

```bash
PYTHONPATH=src python3 -m lectureos.effective_materialize_demo
```

- 첫 실현(정확한 bytes) → replay(reused) → 다른 파일 거부(FAILED 기록·파일 불변) → 명시적 overwrite(새
  event) → 파일 삭제 후에도 record 불변·새 명시적 실현 → superseded artifact 실현 가능 → 이탈 경로 거부 →
  legacy materialization 격리 → Validation healthy(없어진 파일은 손상이 아님).
- content에서 파생된 golden(`expected/materialize-summary.json`)이 바이트 단위로 재현됩니다.

## CLI

```bash
PYTHONPATH=src python3 -m lectureos.effective_materialize_cli materialize --artifact subtitle-effective-srt-artifact:<digest> --storage-root "$(pwd)/out" --database "$(pwd)/out/lectureos.sqlite3"
PYTHONPATH=src python3 -m lectureos.effective_materialize_cli show   --materialization subtitle-effective-srt-materialization:<digest> --storage-root "$(pwd)/out" --database "$(pwd)/out/lectureos.sqlite3"
PYTHONPATH=src python3 -m lectureos.effective_materialize_cli status --materialization subtitle-effective-srt-materialization:<digest> --storage-root "$(pwd)/out" --database "$(pwd)/out/lectureos.sqlite3"
PYTHONPATH=src python3 -m lectureos.effective_materialize_cli list   --artifact subtitle-effective-srt-artifact:<digest> --storage-root "$(pwd)/out" --database "$(pwd)/out/lectureos.sqlite3"
```

## 예제 구조

```text
examples/effective-materialize/
├── README.md
└── expected/
    └── materialize-summary.json   # 데모가 재현하는 결정적 golden
```

자세한 계약은 `implementation/108_EFFECTIVE_SRT_MATERIALIZATION.md`를 참고하세요.
