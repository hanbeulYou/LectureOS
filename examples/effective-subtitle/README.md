# 예제 — Effective-Transcript Subtitle Candidate 생성 (GOAL-013)

이 예제는 effective transcript 계약 세대(`041 §15`, PATCH-0029)의 첫 canonical subtitle 생성 경로를
보여줍니다: 명시적 요청 → GOAL-012 소비 binding(생성 전에 존재) → 결정적 passthrough generator → immutable
Candidate + 순서 있는 Cue 집합 + 정확한 source-segment lineage (하나의 atomic commit).

> **중요:** transcript authority ≠ 소비 ≠ subtitle 생성 ≠ review ≠ decision ≠ final selection ≠ export.
> 생성은 authority를 독자 해석하지 않으며(조용한 Raw fallback 없음), selected-but-inapplicable revision은
> 생성을 **명시적으로** 차단합니다. Candidate identity는 정확한 source에 민감하고(내용이 같아도 source가
> 다르면 별개), 이후 authority 변경은 Candidate를 변경하지 않고 currentness만 파생됩니다. legacy
> `subtitle_candidates` 계열(별도 계약 세대)은 읽지도 쓰지도 않으며, review record·Human Decision·final
> selection·SRT export·물리 파일은 만들지 않습니다. **identity를 받습니다(경로 아님). `--force`는 없습니다.**

## 결정적 데모 (LLM/ASR 아님)

```text
Raw R1 선택 → S1 생성(segment당 cue 1개, 정확한 lineage) → 재생성(reused)
          → Accept → Corrected C1 → 선택 → S2 생성(교정 텍스트·교체 lineage·Raw parent)
          → Raw fallback → 재생성 → 원래 S1 재사용(authority 왕복)
          → 동일 내용의 Raw R2 → S3 생성(같은 내용 ≠ 같은 source)
          → C1 재선택 → 후보 Reject → 생성 명시적 실패(부분 Candidate 없음)
          → S1/S2 불변·stale 파생 → Repository Validation healthy
```

```bash
PYTHONPATH=src python3 -m lectureos.effective_subtitle_demo
```

- generator는 `deterministic_segment_passthrough` v1: cue 텍스트·타이밍·순서·segment lineage가 소비된
  immutable snapshot의 정확한 pass-through입니다(병합·분할·정규화·번역 없음).
- 교정된 cue의 segment는 `replaces_segment_id`로 원본 Raw segment lineage에 도달하며, 사람 교정 텍스트에
  confidence를 조작하지 않습니다.
- legacy subtitle 테이블·review·final selection·export에 어떤 row도 생기지 않음을 데모가 검증합니다.
- content에서 파생된 golden(`expected/subtitle-summary.json`)이 바이트 단위로 재현됩니다.

## CLI

```bash
# 명시적 생성(또는 동일 semantic 재사용 수렴)
PYTHONPATH=src python3 -m lectureos.effective_subtitle_cli generate \
  --intake transcript-source-intake:sha256:<digest> --database "$(pwd)/out/lectureos.sqlite3"

# Candidate 상세(lineage + 순서 있는 cue) / intake의 Candidate 목록 / 파생 currentness
PYTHONPATH=src python3 -m lectureos.effective_subtitle_cli show   --candidate subtitle-effective-candidate:<digest> --database "$(pwd)/out/lectureos.sqlite3"
PYTHONPATH=src python3 -m lectureos.effective_subtitle_cli list   --intake transcript-source-intake:sha256:<digest> --database "$(pwd)/out/lectureos.sqlite3"
PYTHONPATH=src python3 -m lectureos.effective_subtitle_cli status --candidate subtitle-effective-candidate:<digest> --database "$(pwd)/out/lectureos.sqlite3"
```

## 예제 구조

```text
examples/effective-subtitle/
├── README.md
└── expected/
    └── subtitle-summary.json   # 데모가 재현하는 결정적 golden (content-derived id)
```

자세한 계약은 `docs/041_SUBTITLE_PIPELINE.md §15`와 `implementation/103_EFFECTIVE_SUBTITLE_GENERATION.md`를
참고하세요.
