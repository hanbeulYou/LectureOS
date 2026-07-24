# 예제 — Repository Validation (저장소 무결성 검증)

LectureOS는 상위 워크플로가 실행되기 **전에** 저장소 상태가 내부적으로 일관적인지 확인하는 **읽기 전용** 검증
서브시스템을 제공합니다. 미디어 임포트, Whisper, 리뷰 엔진, 추가 export 형식, delivery 등 앞으로의 기능이 검증된
저장소 상태 위에서 안전하게 동작할 수 있게 하는 것이 목적입니다.

## 검증 철학

- **읽기 전용** — 검증기는 데이터베이스를 `PRAGMA query_only = ON`으로 열고 SELECT/PRAGMA만 실행합니다. 저장소를
  **절대 수정하지 않습니다**.
- **비즈니스 로직과 독립** — 검증기는 저장된 상태(persisted store)를 소비할 뿐, 그 상태를 만든 도메인 서비스를
  다시 실행하지 않습니다. export 등 어떤 워크플로에도 결합되지 않습니다.
- **결정적** — 같은 저장소에 대해 항상 같은 진단(diagnostics)을 같은 순서로 냅니다.
- **호출 우선** — 앞으로의 워크플로는 실행 전에 그냥 이 검증을 호출하면 됩니다.

## 무엇을 검증하나

- **스키마** — 지원되는 스키마 버전인지, LectureOS 저장소가 맞는지.
- **참조 무결성** — FK로 강제되는 참조(`PRAGMA foreign_key_check`)와, 스키마가 FK로 강제하지 **않는** 다수의
  plain-TEXT 참조(review/candidate/DomainResult id 등)의 dangling 참조·orphan.
- **DomainResult lineage** — upstream ordinal이 0..n-1로 연속인지.
- **Edit Export Assembly** — 빈 assembly, member ordinal 연속성/중복, 단일 Source Timeline·Media 일관성,
  canonical member 순서(어긋나면 warning).
- **Edit Export provenance** — representation ↔ approved decision ↔ review decision의 kind·lineage 일관성,
  malformed identity.

## CLI 사용법

```bash
PYTHONPATH=src python3 -m lectureos.validate_cli --database lecture.db
PYTHONPATH=src python3 -m lectureos.validate_cli --database lecture.db --format json
```

요약(스키마 버전, 검사한 객체 수, warning/error 수, 전체 health)과 각 진단을 출력합니다.

종료 코드(machine-readable):

| 코드 | 의미 |
| --- | --- |
| `0` | healthy — error·warning 없음 |
| `1` | errors — error 진단 하나 이상(저장소 불일치) |
| `2` | warnings — error는 없고 warning만 |

## 진단 형식

각 진단은 다음을 담습니다:

- `code` — 안정적인 기계 판독용 식별자(예: `DANGLING_REFERENCE`, `ASSEMBLY_EMPTY`)
- `severity` — `info` | `warning` | `error`
- `location` — 위치(보통 `table:identity` 또는 `table.column`)
- `message` — 사람이 읽는 설명

## golden 예제

`expected/`에는 결정적 golden 리포트가 들어 있습니다:

```text
examples/repository-validation/
├── README.md
└── expected/
    ├── healthy-report.json           # 정상 저장소 리포트
    └── empty-assembly-report.json    # 멤버가 비어 있는 assembly를 검출한 리포트
```

이 리포트들은 `tests/test_repository_validation_golden.py`가 바이트 단위로 재현합니다. 진단 형식이나 코드를 의도적으로
바꾼 경우에만, 리뷰를 거쳐 golden을 재생성하세요.
