# 예제 — Explicit Effective SRT Delivery (GOAL-019)

이 예제는 effective transcript 계약 세대의 **명시적 delivery 경계**를 보여줍니다: 명시적 요청이 정확히
하나의 성공한 물리 Materialization의 bytes를 승인된 Delivery Root 아래 정확한 목적지로 복사하고, released
record-first 규율(immutable intent가 목적지 쓰기 **전에** durable, 종결 outcome이 검증 후에 기록, 상태는
파생)을 그대로 따릅니다.

> **중요:** Artifact ≠ Materialization ≠ Delivery ≠ Publication. delivery는 SRT 내용을 재생성하지 않고
> source 파일의 정확한 bytes를 Artifact fingerprint로 intent **이전에** 검증하며, 목적지 bytes를 재검증한
> 뒤에만 DELIVERED를 기록합니다. source 결함(없음·변조·이탈)은 intent 이전에 차단되어 아무것도 persist되지
> 않고, 목적지 결함은 안정된 category를 가진 정직한 FAILED outcome입니다. 같은 요청의 replay는 파일을 다시
> 쓰지 않고 **reused**되며, 기존의 다른 목적지 파일은 기본적으로 거부되고(파일 불변), 오직 명시적
> `--overwrite`만 새 append-only attempt로 교체합니다. 배달된 파일 삭제는 어떤 record도 변경하지 않으며,
> dangling PENDING intent는 오직 명시적 `reconcile`(관찰만, 쓰기 없음)로 닫힙니다. publication·URL·수신
> 확인은 이 계약에 없습니다. delivery 성공 ≠ 공개·수신 확인. **`--force`는 없습니다.**

## 결정적 데모 (LLM/ASR/네트워크 아님; 쓰기는 격리된 승인 root 아래에만)

```bash
PYTHONPATH=src python3 -m lectureos.effective_deliver_demo
```

- 첫 delivery(정확한 검증 bytes) → replay(reused) → 동일 bytes 기존 목적지(정직한 성공) → 다른 bytes 거부
  (FAILED 기록·파일 불변) → 명시적 overwrite(새 attempt) → 배달 파일 삭제 후에도 history 불변·새 명시적
  재배달 → source 없음/변조 시 intent 이전 차단 → superseded 역사적 artifact도 배달 가능 → 이탈 목적지 거부
  → dangling intent 명시적 reconcile(DELIVERED/FAILED, 쓰기 없음) → 동시 동일 요청의 durable-intent 수렴 →
  legacy·publication 격리 → Validation healthy(없어진 파일·PENDING·FAILED는 손상이 아님).
- content에서 파생된 golden(`expected/deliver-summary.json`)이 바이트 단위로 재현됩니다.

## CLI

```bash
PYTHONPATH=src python3 -m lectureos.effective_deliver_cli eligibility --materialization subtitle-effective-srt-materialization:<digest> --storage-root "$(pwd)/out" --database "$(pwd)/out/lectureos.sqlite3"
PYTHONPATH=src python3 -m lectureos.effective_deliver_cli deliver --materialization subtitle-effective-srt-materialization:<digest> --storage-root "$(pwd)/out" --delivery-root "$(pwd)/deliver" --database "$(pwd)/out/lectureos.sqlite3"
PYTHONPATH=src python3 -m lectureos.effective_deliver_cli show   --delivery subtitle-effective-srt-delivery:<digest> --storage-root "$(pwd)/out" --delivery-root "$(pwd)/deliver" --database "$(pwd)/out/lectureos.sqlite3"
PYTHONPATH=src python3 -m lectureos.effective_deliver_cli status --delivery subtitle-effective-srt-delivery:<digest> --storage-root "$(pwd)/out" --delivery-root "$(pwd)/deliver" --database "$(pwd)/out/lectureos.sqlite3"
PYTHONPATH=src python3 -m lectureos.effective_deliver_cli list   --materialization subtitle-effective-srt-materialization:<digest> --storage-root "$(pwd)/out" --delivery-root "$(pwd)/deliver" --database "$(pwd)/out/lectureos.sqlite3"
PYTHONPATH=src python3 -m lectureos.effective_deliver_cli reconcile --delivery subtitle-effective-srt-delivery:<digest> --storage-root "$(pwd)/out" --delivery-root "$(pwd)/deliver" --database "$(pwd)/out/lectureos.sqlite3"
```

## 예제 구조

```text
examples/effective-deliver/
├── README.md
└── expected/
    └── deliver-summary.json   # 데모가 재현하는 결정적 golden
```

자세한 계약은 `implementation/109_EFFECTIVE_SRT_DELIVERY.md`를 참고하세요.
