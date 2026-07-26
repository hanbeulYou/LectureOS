# 예제 — First Human Authority Decision (Correction Candidate)

이 예제는 §17에서 admit된 **Correction Candidate**에 대해 사람이 **accept 또는 reject를 명시적으로 결정**하는 첫
Human Authority 계층(`040 §18`, GOAL-009)을 보여줍니다. 결정은 **authority 기록일 뿐**이며 아무것도 적용하지 않고
후보나 Raw Transcript를 변경하지 않으며 corrected revision을 만들지 않습니다.

> **중요:** 상태는 세 가지 — **Undecided**(결정 record 없음; 부재로 파생), **Accepted**, **Rejected** — 뿐이며
> **Modify는 이후 단계입니다.** history는 append-only(마음이 바뀌면 새 결정을 append; 이전 record는 보존)이고 current
> authority는 최고 sequence로 **파생**됩니다. identity는 `(candidate, kind, sequence)`에서 결정적으로 파생되며 동일 kind
> 재제출은 idempotent(`reused`)합니다. **candidate·raw transcript identity를 받습니다(경로가 아님). `--apply`는 없습니다.**

## 결정적 데모 (LLM/규칙 엔진 아님)

fake provider 결과·수동 후보로 authority 진화(§51 A/B/C/D: Accept, Reject, Accept→Reject, Reject→Accept)를
재현합니다:

```text
Fixture Source Media → Transcript Intake → Provider Result → Raw Transcript
                    → Current Raw Transcript Selection → Correction Candidate Admission
                    → Undecided → Accept → replay Accept → Reject → re-Accept
                    → decision history → current authority → Repository Validation
```

```bash
PYTHONPATH=src python3 -m lectureos.correction_candidate_decision_demo
```

- Undecided는 부재로 파생되고, Accept/Reject는 결정적으로 기록되며, 동일 kind 재제출은 `reused`입니다.
- authority 전환(Accept↔Reject)은 history를 append하며 이전 record를 삭제하지 않습니다.
- **Accepted** 후보만 이후 corrected-revision 대상이 됩니다(여기서는 확립만; 생성은 미구현).
- 후보와 Raw Transcript는 변경되지 않으며, Modify·unknown 후보는 거부되고, 저장소는 무결성 검증을 통과합니다.
- content에서 파생된 golden(`expected/decision-summary.json`)이 바이트 단위로 재현됩니다.

## CLI

```bash
# 사람의 accept/reject 결정 (적용되지 않음)
PYTHONPATH=src python3 -m lectureos.correction_candidate_decision_cli decide \
  --candidate correction-candidate:<digest> --kind accept --reviewer reviewer:kim \
  --database "$(pwd)/out/lectureos.sqlite3"

# 현재 authority (undecided / accepted / rejected + revision 대상 여부)
PYTHONPATH=src python3 -m lectureos.correction_candidate_decision_cli status \
  --candidate correction-candidate:<digest> --database "$(pwd)/out/lectureos.sqlite3"

# append-only 결정 history
PYTHONPATH=src python3 -m lectureos.correction_candidate_decision_cli history \
  --candidate correction-candidate:<digest> --database "$(pwd)/out/lectureos.sqlite3"
```

## 예제 구조

```text
examples/correction-decision/
├── README.md
└── expected/
    └── decision-summary.json   # 데모가 재현하는 결정적 golden (content-derived id)
```

자세한 계약은 `docs/040_TRANSCRIPT_PIPELINE.md §18`과 `implementation/099_CORRECTION_CANDIDATE_DECISION.md`를
참고하세요.
