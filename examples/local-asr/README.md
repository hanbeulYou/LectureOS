# 예제 — First Local ASR Execution Adapter (faster-whisper)

이 예제는 이미 admit된 **Transcript Source Intake**에 대해 하나의 **로컬 ASR 엔진(faster-whisper)**을 실행하여,
그 출력을 기존 provider-neutral admission 경계(`040 §14`)를 통해 canonical **Raw Transcript**로 만드는 첫
concrete adapter(`040 §15`)를 보여줍니다.

> **중요:** adapter는 **intake identity를 받습니다(미디어 경로가 아님)**. 실행 시 `SourceMedia`의 reference-in-place
> 원본 파일을 resolve하여 존재·읽기 가능·regular file인지 확인하고, 저장된 content fingerprint와 **재검증**합니다.
> 바이트가 바뀌었으면 옛 `SourceMediaId`로 전사하지 않고 새 import를 요구합니다. adapter는 Raw Transcript를 직접
> 쓰지 않고 기존 admission service만 사용합니다. `faster-whisper`는 **선택적 의존성**이며, 없어도 패키지·테스트·아래
> 결정적 데모는 동작합니다(데모는 fake 엔진 사용).

## 결정적 데모 (실제 ASR 아님)

fake 결정적 엔진으로 orchestration을 재현합니다(실제 전사 품질 데모가 아님):

```text
Fixture bytes → Media Import → Transcript Intake → Local ASR Adapter orchestration
             → Fake engine output → Provider Transcript Admission → Raw Transcript → Repository Validation
```

```bash
PYTHONPATH=src python3 -m lectureos.local_asr_demo
```

- adapter가 Source Media lineage를 사용하고 원본 검증(존재+fingerprint)이 수행됨을 증명합니다.
- provider-neutral admission이 유일한 쓰기 경계이며, 재실행 없이 재사용(replay)됩니다.
- admit 이전 실패(바뀐 바이트)는 아무것도 쓰지 않으며 저장소는 무결성 검증을 통과합니다.
- content에서 파생된 golden(`expected/local-asr-summary.json`)이 바이트 단위로 재현됩니다
  (`tests/test_local_asr_demo.py`).

## 실제 로컬 ASR 실행 (선택)

`faster-whisper`와 로컬 모델(및 디코딩 백엔드)이 설치되어 있으면 실제 전사를 실행할 수 있습니다:

```bash
# 1) 미디어 임포트 → SourceMediaId
PYTHONPATH=src python3 -m lectureos.media_import_cli /path/to/lecture.mp4 \
  --database "$(pwd)/out/lectureos.sqlite3"

# 2) intake admit
PYTHONPATH=src python3 -m lectureos.transcript_intake_cli \
  --media sha256:<digest> --database "$(pwd)/out/lectureos.sqlite3"

# 3) 실제 로컬 ASR 실행 (CPU 기본)
PYTHONPATH=src python3 -m lectureos.local_asr_cli \
  --intake transcript-source-intake:sha256:<digest> \
  --database "$(pwd)/out/lectureos.sqlite3" --model tiny --language ko
```

전사 정확도는 보장되지 않으며, 모든 미디어 포맷·운영체제·GPU 가용성도 보장되지 않습니다.

## 예제 구조

```text
examples/local-asr/
├── README.md
└── expected/
    └── local-asr-summary.json   # 데모가 재현하는 결정적 golden (content-derived id)
```

fixture는 `examples/media-import/fixtures/`의 바이너리를 재사용합니다(재생 가능한 오디오가 아니라 임의의 결정적
바이트 — fake 엔진이 전사를 대신하므로 실제 오디오가 필요 없음).

자세한 계약은 `docs/040_TRANSCRIPT_PIPELINE.md §15`와 `implementation/096_LOCAL_ASR_ADAPTER.md`를 참고하세요.
