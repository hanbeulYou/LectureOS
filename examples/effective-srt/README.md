# 예제 — Effective Subtitle SRT Artifact (GOAL-017)

이 예제는 effective transcript 계약 세대의 **논리적 SRT export**를 보여줍니다: 파생 export eligibility(현재
적용 가능한 Final Selection 필수) → 명시적 generate → released canonical SRT serializer(바이트 결정적) →
immutable 논리 artifact(정확한 selection/candidate lineage + content fingerprint).

> **중요:** Final Selection ≠ Artifact ≠ 물리 파일. artifact 존재는 파일·경로·URL·materialization·전달을
> 의미하지 않습니다(물리 materialization은 이후 Goal). superseded/stale/inapplicable selection은 새 artifact를
> 생성할 수 없고, 기존 artifact는 불변 history로 남으며 currentness(current/superseded_by_final_selection/
> supporting_decision_superseded/stale_due_to_candidate_source/unresolvable)가 파생됩니다. content
> fingerprint는 identity가 아닙니다 — 내용이 같아도 selection이 다르면 별개 artifact입니다. 자동 재생성·자동
> export는 없으며 legacy export는 읽지도 쓰지도 않습니다. **identity를 받습니다(경로 아님). `--force`는
> 없습니다.**

## SRT 직렬화 계약 (`canonical_srt` v1)

번호는 1부터 canonical ordinal 순서; `HH:MM:SS,mmm`(ROUND_HALF_UP ms); LF 줄바꿈; 블록 사이 빈 줄 1개; 비어
있지 않은 payload는 단일 trailing LF; 텍스트는 정확히 보존(재작성·줄바꿈·병합·분할·타이밍 수정 없음); ms
정밀도에서 붕괴하는 duration과 음수 시간은 거부.

## 결정적 데모 (LLM/ASR 아님)

```bash
PYTHONPATH=src python3 -m lectureos.effective_srt_demo
```

- eligibility → generate(정확한 payload) → replay(reused) → superseded selection 차단(기존 artifact 불변·
  superseded 파생) → 현재 selection의 별개 artifact → 동일 내용·다른 selection = 같은 fingerprint·다른
  identity → 손상 graph 거부 → 물리 격리(.srt 파일 0개·경로 컬럼 없음·legacy/materialization row 0개) →
  Validation healthy.
- content에서 파생된 golden(`expected/srt-summary.json`, 정확한 SRT payload 포함)이 바이트 단위로 재현됩니다.

## CLI

```bash
PYTHONPATH=src python3 -m lectureos.effective_srt_cli eligibility --selection subtitle-effective-final-selection:<digest> --database "$(pwd)/out/lectureos.sqlite3"
PYTHONPATH=src python3 -m lectureos.effective_srt_cli generate    --selection subtitle-effective-final-selection:<digest> --database "$(pwd)/out/lectureos.sqlite3"
PYTHONPATH=src python3 -m lectureos.effective_srt_cli show        --artifact subtitle-effective-srt-artifact:<digest> --database "$(pwd)/out/lectureos.sqlite3"
PYTHONPATH=src python3 -m lectureos.effective_srt_cli content     --artifact subtitle-effective-srt-artifact:<digest> --database "$(pwd)/out/lectureos.sqlite3"
PYTHONPATH=src python3 -m lectureos.effective_srt_cli list        --intake transcript-source-intake:sha256:<digest> --database "$(pwd)/out/lectureos.sqlite3"
PYTHONPATH=src python3 -m lectureos.effective_srt_cli status      --artifact subtitle-effective-srt-artifact:<digest> --database "$(pwd)/out/lectureos.sqlite3"
```

## 예제 구조

```text
examples/effective-srt/
├── README.md
└── expected/
    └── srt-summary.json   # 데모가 재현하는 결정적 golden (정확한 SRT payload 포함)
```

자세한 계약은 `implementation/107_EFFECTIVE_SUBTITLE_SRT_ARTIFACT.md`를 참고하세요.
