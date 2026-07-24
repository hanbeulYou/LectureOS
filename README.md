# LectureOS

LectureOS는 긴 한국어 강의의 후반작업에서 생기는 반복 작업을 줄이기 위한 AI 기반 시스템입니다. 잘못 인식된 말을
고치고, 자막을 읽기 좋게 나누고, 편집이 필요한 구간을 찾아 사람이 검토·결정하는 과정을 한곳에서 이어서 처리하고,
모든 사람의 결정과 그 근거(provenance)를 남깁니다.

핵심 원칙은 하나입니다. **AI는 판단에 필요한 근거와 후보를 준비하고, 최종 결정은 사람이 내립니다.** LectureOS는 원본
영상을 자동으로 잘라내지 않고 전문 편집기를 대신하지도 않습니다. 대신 사람이 승인한 편집 결정을 만들고, 그것을 외부에서
쓸 수 있는 표현으로 export합니다.

> **상태: Developer Preview.** 이 저장소에는 릴리스된 **Blueprint**(`docs/`, `patches/`)와, 실행 가능한
> **Edit Export** MVP까지 구현·테스트된 코드가 함께 들어 있습니다. 지금 바로 전체 edit-export 파이프라인을 end-to-end로
> 실행할 수 있습니다 — [빠른 시작](#quick-start-빠른-시작)을 참고하세요.

## Design Philosophy (설계 철학)

- **원본 우선** — 원본 미디어와 원본 시간축(Source Timeline)은 절대 변경하지 않습니다.
- **인식문과 자막의 분리** — 발화 내용을 기록하는 인식문(transcript)과 시청용으로 다듬은 자막(subtitle)을 구분합니다.
- **후보와 결정의 분리** — AI가 만든 후보(candidate)를 사람의 결정(decision)으로 간주하지 않습니다.
- **분석과 편집의 분리** — 편집 후보를 제안할 뿐, 실제 영상을 편집하지 않습니다.
- **사람의 결정권** — 수락·거절·수정의 최종 권한은 사람에게 있습니다.
- **결정과 산출물의 분리** — 승인된 결정과 외부로 내보내는 파일/표현(artifact)을 구분합니다.
- **제공자 독립성** — 특정 AI·음성 인식·편집 도구를 핵심 구조에 종속시키지 않습니다.
- **안전한 재처리** — 일부 단계를 다시 실행해도 이전 근거와 사용자 결정을 몰래 지우지 않습니다.
- **Blueprint 우선** — 제품 의미는 `docs/`에서 정의하고, 변경은 `patches/`의 PATCH로만 합니다.

## Implemented Capabilities (구현 현황)

### ✅ Implemented (구현 완료 · 테스트됨)

- **실행 · lineage** — 처리 실행(run), 유닛 실행, `DomainResult` provenance를 SQLite에 durable하게 저장(스키마
  **v29**, 이전 모든 버전에서 additive 단일 단계 마이그레이션).
- **인식문 파이프라인** — 원본 인식문 + provider 결과, 교정 생성·적용, 검수 준비, 사람의 검수 결정, applicability,
  current selection, ready state.
- **자막 파이프라인** — 인테이크, 후보 생성, reading/time 표현, 구조 검증, 검수 준비, 사람의 검수 결정, 결정 적용,
  최종 자막.
- **자막 export** — 승인 assembly → SRT artifact(직렬화) → **SRT 물리 materialization**(로컬 파일).
- **강의 분석(Lecture Intelligence)** — eligible analysis input, analysis finding, segmentation, edit candidate
  foundation, 구체 edit-candidate 생성 provider.
- **검수(Review)** — edit review decision(accept/reject/modify)와 approved edit decision.
- **편집 export(Edit Export)** — approved edit export representation → edit export assembly → edit export
  artifact → **LectureOS Edit Export JSON v1** 직렬화 → **로컬 파일 materialization**, 그리고 실행 가능한 CLI.
- **실행 진입점** — edit-export CLI와 mock end-to-end 데모(미디어·네트워크 불필요).

### 🚧 In Progress (진행 중)

- 동일한 canonical Artifact 위에 additive하게 얹는 Edit Export 후속 단계들.

### 🗺️ Planned (계획 · Blueprint에서 유보됨)

추가 export 형식과 serializer registry, Export Profile/Configuration, provider/NLE 어댑터, 원격 delivery/업로드,
소스 미디어에 대한 실제 편집 적용, output-timeline 변환·렌더링. 이들은 의도적으로 유보되어 있습니다 —
`docs/044_EXPORT_PIPELINE.md` 참고.

## Architecture Overview (아키텍처 개요)

LectureOS는 Blueprint 기반의 계층형 아키텍처를 따릅니다. Domain/Application 로직은 순수·결정적이며, 부작용(저장,
파일시스템)은 경계의 포트(Protocol) 뒤에 둡니다.

```text
Domain / Application   순수 모델·불변식·서비스              (src/lectureos/application, execution, ...)
        │              결정적 · 시계/입출력 없음
Ports (Protocols)      persistence · file-writer 경계
        │
Persistence            insert-only SQLite, additive 스키마    (src/lectureos/persistence)
Infrastructure         로컬 파일시스템 writer(temp+atomic)     (src/lectureos/infrastructure)
Composition Root       구체 어댑터를 서비스에 결선            (src/lectureos/composition.py)
```

구현된 **edit-export 파이프라인**(MVP 경로):

```text
Approved Edit Decision            (043 — 사람의 accept/modify 결정)
    → Edit Export Representation   (044 §19 — 승인 편집 하나의 export 의미)
    → Edit Export Assembly         (044 §20 — 하나의 Source Timeline에 대한 coherent Export Scope)
    → Edit Export Artifact         (044 §21 — canonical·format-neutral external representation)
    → LectureOS Edit Export JSON   (044 §22 — 결정적 직렬화, v1)
    → Local File                   (044 §22 — 안전한 원자적 로컬 materialization)
```

제품 아키텍처는 Blueprint(`docs/030_DATA_MODEL.md`, `docs/031_ARCHITECTURE.md`, `docs/044_EXPORT_PIPELINE.md`)에
정의되어 있고, 구현 현황은 `implementation/060_IMPLEMENTATION_STATUS.md`에서 추적합니다.

## Requirements (요구 사항)

- **Python 3.10+** (`X | None` 유니온과 slotted dataclass 사용).
- MVP·데모·테스트에 **third-party 의존성이 없습니다** — 핵심은 표준 라이브러리(`sqlite3`, `json`, `argparse` 등)만
  사용합니다.
- 선택적 실제 미디어 / OpenAI 인식 경로(`providers/`, `real_media_demo`)는 `ffmpeg`와 OpenAI 자격증명이 추가로
  필요하며, edit-export MVP에는 **필요하지 않습니다**.

## Installation (설치)

빌드 단계가 없습니다. `src/` 레이아웃을 사용하며 `PYTHONPATH=src`로 실행합니다:

```bash
git clone <this-repo>
cd LectureOS
python3 --version            # 3.10 이상
```

## Quick Start (빠른 시작)

미디어 파일·네트워크 **없이** 전체 edit-export 파이프라인을 end-to-end로 실행하면, 실제이고 결정적인 JSON export
파일 하나가 만들어집니다:

```bash
PYTHONPATH=src python3 -m lectureos.edit_export_demo --output-directory "$(pwd)/out"
cat out/edit-export.json
```

전체 테스트 실행(1600개 이상):

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

## CLI Usage (CLI 사용법)

LectureOS SQLite 데이터베이스에 있는 기존 `EditExportAssembly`의 승인 편집을 로컬 파일로 export합니다:

```bash
PYTHONPATH=src python3 -m lectureos.edit_export_cli <ASSEMBLY_ID> \
    --database /path/to/lectureos.sqlite3 \
    --output   /path/to/lecture-42.json \
    [--overwrite]
```

- 성공 시 종료 코드 `0`, 최종 경로·형식·바이트 길이를 출력합니다.
- 오류(존재하지 않는 assembly, DB 없음, collision, 쓰기 실패) 시 종료 코드 `1`, stderr에 명시적 메시지를 남기고,
  **부분 파일이나 오해를 주는 파일을 절대 남기지 않습니다**.
- 기본적으로 내용이 다른 기존 파일은 그대로 두며, `--overwrite`를 주면 원자적으로 교체합니다.

전체 도움말과 예시는 `PYTHONPATH=src python3 -m lectureos.edit_export_cli --help`에서 볼 수 있습니다.

## Example Export (예제 export)

동작하는 예제가 [`examples/edit-export/`](examples/edit-export/README.md)에 있으며, 데모가 바이트 단위로 재현하는
golden 출력이 포함됩니다. export된 JSON은 서술적입니다 — 실행 가능한 컷 명령이 아니라 승인된 편집 결정을 기록합니다:

```json
{
  "format": "lectureos-edit-export-json",
  "version": "v1",
  "artifact_id": "edit-export-demo",
  "source_assembly_id": "edit-export-demo-assembly",
  "source_media_id": "int-media",
  "source_timeline_id": "int-timeline",
  "edits": [
    {
      "source_representation_id": "export-accept",
      "decision_kind": "accept",
      "approved_range_start": 0.5,
      "approved_range_end": 1.5,
      "approved_candidate_type": "non_lecture_region",
      "approved_rationale": "propose review of a non-lecture region",
      "actor": "reviewer:alice"
    }
  ]
}
```

## Repository Structure (저장소 구조)

```text
LectureOS/
├── src/lectureos/
│   ├── application/        # 순수 domain + application 서비스(모델·불변식·오케스트레이션)
│   ├── persistence/        # insert-only SQLite 저장소 + additive 스키마(v29)
│   ├── infrastructure/     # 로컬 파일시스템 writer(temp-file + 원자적 배치)
│   ├── execution/          # 처리 실행, 유닛 실행, DomainResult lineage
│   ├── providers/          # 선택적 provider 어댑터(예: OpenAI) — MVP에는 불필요
│   ├── composition.py      # composition root: 구체 어댑터를 서비스에 결선
│   ├── edit_export_cli.py  # 실행 가능한 Edit Export CLI
│   ├── edit_export_demo.py # 실행 가능한 mock end-to-end 데모(미디어·네트워크 불필요)
│   └── *_acceptance.py     # 인프로세스 end-to-end 인수 실행기
├── tests/                  # unittest 스위트(1600개 이상)
├── examples/edit-export/   # 동작 예제 + golden 출력
├── docs/                   # 릴리스된 Blueprint(제품 의미) + docs/README.md
├── patches/                # Blueprint 변경 기록(PATCH-0001 … PATCH-0018)
└── implementation/         # 구현 워크플로·저장 모델·현황
```

## Current Limitations (현재 한계)

- 구체 export 형식은 **LectureOS Edit Export JSON v1** 하나뿐이며, 다른 형식은 유보되어 있습니다.
- 로컬 파일시스템 출력만 지원 — 원격 delivery·업로드·URL 없음.
- Edit Export Artifact와 직렬화 결과는 **derived·regenerable**이며 데이터베이스에 저장하지 않습니다(설계상).
- LectureOS는 승인된 *결정*과 그 표현을 만들 뿐, 미디어에 편집을 적용하거나 타임라인을 변환·렌더링하지 않습니다.
- 실제 인식(OpenAI/ffmpeg)은 선택 사항이며 edit-export MVP 경로 밖에 있습니다.

## Roadmap (로드맵)

1. **현재(Developer Preview):** end-to-end edit-export MVP — Assembly → Artifact → JSON → 로컬 파일, CLI와
   데모로 실행 가능. ✅
2. **다음:** canonical Artifact 위에 additive하게 얹는 추가 export 형식.
3. **이후(유보):** Export Profile/Configuration, provider/NLE export 어댑터, 원격 delivery, 그리고 — 현재 제품
   경계 밖의 먼 후속 단계로 — 실제 편집 적용과 렌더링.

무엇이 범위 안/밖인지는 Blueprint가 규정하며, 각 기능은 구현 전에 PATCH로 승격됩니다.

## Development Status (개발 상태)

- **Blueprint:** **PATCH-0018**까지 안정(`docs/`, `patches/`).
- **구현:** edit-export MVP 완료; SQLite 스키마 **v29**; 전체 스위트 green(1600개 이상).
- **거버넌스:** Blueprint 우선 — 제품 의미를 바꾸려면 PATCH를 먼저 쓰고 나서 구현합니다.
  `AGENTS.md`와 `implementation/050_IMPLEMENTATION_WORKFLOW.md` 참고.

## Documentation (문서)

- 제품 Blueprint와 권장 읽기 순서: [`docs/README.md`](docs/README.md).
- Export 파이프라인 계약(representation → assembly → artifact → JSON/materialization):
  `docs/044_EXPORT_PIPELINE.md` §19–§22.
- 구현 현황: `implementation/060_IMPLEMENTATION_STATUS.md`.

## License (라이선스)

[MIT License](LICENSE). 저작권 표기는 현재 중립적으로 `LectureOS`로 되어 있으니, 필요하면 실명/조직명으로 바꾸세요.
