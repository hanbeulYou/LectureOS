# 예제 — Effective Subtitle Pipeline v1 Release (GOAL-021)

이 예제는 완성된 **Effective Subtitle Pipeline v1**의 릴리스 검증 자산입니다: 하나의 연결된 시나리오가
production 서비스와 실제 persistence로 전체 파이프라인을 구동하고, 모든 단계 간 typed lineage와 정확한
canonical SRT bytes(논리 artifact == 물리 파일 == 배달 파일)를 검증합니다.

> **중요:** 모든 전이는 명시적 명령입니다 — 어떤 단계도 다음 단계를 자동으로 만들지 않습니다. 모든 current
> 상태는 불변 append-only history에서 파생되며, side effect는 record-first로 정직하게 기록되고, 파일시스템
> 관찰은 어떤 record도 변경하지 않습니다. legacy 파이프라인 테이블에는 단 한 행도 쓰이지 않습니다.

## 결정적 릴리스 데모

```bash
PYTHONPATH=src python3 -m lectureos.effective_subtitle_release_demo
```

- intake → candidate → review subject → Human Accept → final selection → 논리 SRT artifact → 물리
  materialization → 검증된 delivery → publication → 파생 availability.
- content에서 파생된 golden(`expected/release-summary.json`)이 바이트 단위로 재현되며, 절대 경로·타임스탬프·
  머신 의존 데이터는 포함되지 않습니다.

## 릴리스 자산

```text
examples/effective-subtitle-v1/
├── README.md
├── release-manifest.json            # 결정적 릴리스 manifest (Goals·스키마 범위·단계·계약·어휘·유예 경계)
└── expected/
    └── release-summary.json         # 릴리스 데모가 재현하는 결정적 golden
```

- 릴리스 문서: `implementation/111_EFFECTIVE_SUBTITLE_PIPELINE_V1_RELEASE.md`
- 릴리스 수용 스위트: `tests/test_effective_subtitle_pipeline_release.py`
- 단계별 완결 문서: `implementation/103` ~ `110`
- 단계별 CLI/데모: `examples/effective-subtitle/` ~ `examples/effective-publish/` 및 각 README 참고
