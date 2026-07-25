# 예제 — Transcript Source Intake (전사 소스 인테이크 적격성)

이 예제는 이미 임포트된 canonical **Source Media** 기록을 **Transcript Pipeline의 입력으로 admit할 수 있는지**를
확인하는 첫 슬라이스(`040_TRANSCRIPT_PIPELINE.md §13`)를 보여줍니다. 실제 transcription을 수행하지 않습니다.

> **중요:** Media Import와 Transcript Intake는 **분리된 단계**입니다. Intake는 `SourceMediaId`를 받습니다(파일
> 경로가 아님). Intake는 **media를 디코딩·probe·재생·transcription하지 않고**, audio stream 존재도 주장하지
> 않습니다. 적격성은 오직 **persist된 사실**로만 판정됩니다: `SourceMediaId`가 persist된 `source_media` 기록으로
> resolve되면 적격입니다. import 이후 원본 파일이 이동·삭제되어도 intake 적격성에는 영향이 없습니다(이후 실행
> 단계의 관심사).

## 무엇을 보여주나

```text
Fixture bytes
  → Media Import       (로컬 파일 → content-addressed SourceMedia)
  → Persisted SourceMedia
  → Transcript Intake Eligibility  (SourceMediaId를 admit)
  → Intake result      (created / reused)
  → Repository Validation (healthy)
```

- intake identity는 Source Media에서 **결정적으로 파생**됩니다:
  `transcript-source-intake:<source_media_id>`. 하나의 Source Media에는 하나의 canonical intake가 대응합니다.
- 동일 Source Media의 반복 admission은 idempotent(`reused`)이며 서로 다른 Source Media는 서로 다른 intake를
  가집니다.
- 존재하지 않는(unknown) Source Media와 형식이 잘못된(malformed) identity는 명시적으로 거부됩니다.
- transcript 내용·실행 결과는 만들어지지 않으며 Source Media 기록은 변경되지 않습니다. 저장소는 무결성 검증을
  통과합니다.

## 실행 방법

먼저 미디어를 임포트한 뒤(SourceMediaId 획득), 그 id로 intake를 admit합니다:

```bash
# 1) 로컬 파일을 임포트하고 SourceMediaId를 얻는다
PYTHONPATH=src python3 -m lectureos.media_import_cli examples/media-import/fixtures/sample-a.bin \
  --database "$(pwd)/out/lectureos.sqlite3"

# 2) 그 SourceMediaId를 transcript 입력으로 admit한다 (transcription은 실행되지 않음)
PYTHONPATH=src python3 -m lectureos.transcript_intake_cli \
  --media sha256:<digest> --database "$(pwd)/out/lectureos.sqlite3"
```

예상 출력:

```text
created transcript intake transcript-source-intake:sha256:<digest> for source media sha256:<digest>
no transcription was executed
```

전체 흐름을 결정적으로 재현하는 데모:

```bash
PYTHONPATH=src python3 -m lectureos.transcript_intake_demo
```

## 예제 구조

```text
examples/transcript-intake/
├── README.md
└── expected/
    └── intake-summary.json   # 데모가 재현하는 결정적 golden(media id·intake id)
```

데모는 `examples/media-import/fixtures/`의 바이너리 fixture를 재사용합니다(재생 가능한 비디오가 아니라 임의의
결정적 바이트). intake identity가 content에서 파생되므로 `intake-summary.json`의 값은 바이트 단위로 결정적이며
`tests/test_transcript_intake_demo.py`가 이를 재현합니다.

자세한 계약은 `docs/040_TRANSCRIPT_PIPELINE.md §13`과 `implementation/090_TRANSCRIPT_SOURCE_INTAKE.md`를 참고하세요.
