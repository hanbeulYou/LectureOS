# 예제 — Derived Lecture Analysis Input Eligibility (GOAL-022)

이 예제는 **Lecture Intelligence Pipeline의 첫 실행 계약**(042 §5.1 / PATCH-0009 Milestone 1)을
보여줍니다: 정확히 하나의 intake에 대해 현재 effective transcript authority가 강의 분석 입력으로
admissible한지 **파생**으로 판정하고, 이후 명시적 admission이 바인딩할 정확한 lineage를 노출합니다.

> **중요:** Eligibility ≠ Analysis Input ≠ Analysis Run. 아무것도 persist되지 않고(mutable ready 플래그
> 없음), 어떤 transcript 기록도 변경되지 않으며, 분석·AI 호출은 없습니다. 042 §5.1의 확정된 admission
> authority는 **Transcript Pipeline이 선택한 validated Corrected Transcript**(+ Source Timeline·Source
> Media reference)입니다 — 따라서 raw 전용 authority나 명시적 raw-fallback 선택은 정직한 ineligible
> 상태(`corrected_transcript_not_selected`)이고, inapplicable한 선택은 canonical resolver의 이유와 함께
> 차단되며 조용한 raw fallback은 없습니다. 결과는 **advisory**입니다: transcript를 예약하지 않으며, 이후
> 명시적 admission 명령이 current authority를 재검증해야 합니다(TOCTOU 경계). 하나의 평가는 §20 resolver를
> 정확히 한 번 호출하고 snapshot은 불변 identity로만 로드하므로 서로 다른 authority snapshot을 섞지
> 않습니다. content fingerprint는 released §19 계약을 그대로 재사용합니다.

## 결정적 데모 (LLM/ASR/네트워크/쓰기 없음)

```bash
PYTHONPATH=src python3 -m lectureos.analysis_input_eligibility_demo
```

- raw 없음 → raw 전용 → raw-fallback(모두 ineligible) → 적용 가능한 corrected revision(eligible + 정확한
  lineage·fingerprint) → 교체 revision(current authority만 해석) → upstream 변경으로 inapplicable(명시적
  이유) → unknown intake(안정적 ineligible) → 재시작 후 동일 결과 → 아무 행도 쓰이지 않음(스키마 v46 불변)
  → Validation healthy(ineligibility는 손상이 아님).
- content에서 파생된 golden(`expected/eligibility-summary.json`)이 바이트 단위로 재현됩니다.

## CLI

```bash
PYTHONPATH=src python3 -m lectureos.analysis_input_eligibility_cli evaluate --intake transcript-source-intake:sha256:<digest> --database /path/to/lectureos.sqlite3
```

exit code: eligible → 0, ineligible → 1(차단 이유 출력), 오류 → 1(`error:` stderr).

## 예제 구조

```text
examples/analysis-input-eligibility/
├── README.md
└── expected/
    └── eligibility-summary.json   # 데모가 재현하는 결정적 golden
```

자세한 계약은 `implementation/112_LECTURE_ANALYSIS_INPUT_ELIGIBILITY.md`를 참고하세요.
