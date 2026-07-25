# 예제 — External ASR Boundary (Provider Transcript Result admission)

이 예제는 이미 admit된 **Transcript Source Intake**(`040_TRANSCRIPT_PIPELINE.md §13`)에 대해, **외부에서
생성된 ASR 결과**를 admit하여 첫 canonical **Raw Transcript**를 만드는 첫 슬라이스(`040 §14`)를 보여줍니다.
**LectureOS는 ASR 엔진을 실행하지 않습니다.** provider 결과는 계산되는 것이 아니라 로컬 JSON 문서로 *공급*됩니다.

> **중요:** 입력은 `TranscriptSourceIntakeId`와 provider-neutral(LectureOS-native) 결과 문서이며 **media 경로가
> 아닙니다.** admission은 media를 디코딩·probe·재생하지 않고 audio를 추출하지 않으며 network 요청도 하지 않습니다.
> provider 증거(`ProviderTranscriptResult`)는 정규화 이전 상태로 보존되고, canonical `RawTranscript`는 그와 **별개**의
> identity를 가집니다.

## 무엇을 보여주나

```text
Fixture bytes
  → Media Import                (로컬 파일 → content-addressed SourceMedia)
  → Transcript Source Intake    (SourceMediaId를 admit)
  → Fake Provider Result        (committed JSON fixture — 실제 ASR 결과가 아님)
  → Provider Result Admission   (외부 결과를 admit)
  → Raw Transcript              (canonical, provider 결과와 별개 identity)
  → Repository Validation       (healthy)
```

- 모든 LectureOS identity는 anchor `(intake_id, provider, model, provider_result_ref)`에서 결정적으로 파생됩니다
  (SHA-256). 하나의 intake는 여러 provider 결과를, 하나의 provider 결과는 하나의 canonical Raw Transcript를 가집니다.
- admission은 전체 payload에 대한 `content_fingerprint`로 idempotent합니다. 동일 결과 재admission은 `reused`이며,
  **같은 참조에 다른 내용**을 admit하면 conflict로 거부됩니다(덮어쓰지 않음).
- 잘못된 timing(`end <= start`), 빈 결과, 순서 위반·겹침, 존재하지 않는 intake는 명시적으로 거부됩니다.
- segment의 timing은 초(seconds) 단위이며 text는 그대로 보존됩니다(한국어 포함). Source Media·intake 기록은 변경되지
  않습니다. 저장소는 무결성 검증을 통과합니다.

## 실행 방법

fixture는 `examples/media-import/fixtures/`의 바이너리(재생 가능한 비디오가 아니라 임의의 결정적 바이트)와 이 예제의
`fixtures/provider-result.json`(한국어 transcript text를 담은 결정적 provider 결과)을 재사용합니다.

```bash
# 1) 로컬 파일 임포트 → SourceMediaId
PYTHONPATH=src python3 -m lectureos.media_import_cli examples/media-import/fixtures/sample-a.bin \
  --database "$(pwd)/out/lectureos.sqlite3"

# 2) 그 SourceMediaId를 transcript 입력으로 admit
PYTHONPATH=src python3 -m lectureos.transcript_intake_cli \
  --media sha256:<digest> --database "$(pwd)/out/lectureos.sqlite3"

# 3) 외부 provider ASR 결과를 admit (ASR 엔진은 실행되지 않음)
PYTHONPATH=src python3 -m lectureos.transcript_result_admit_cli \
  --intake transcript-source-intake:sha256:<digest> \
  --input examples/transcript-result-admission/fixtures/provider-result.json \
  --database "$(pwd)/out/lectureos.sqlite3"
```

예상 출력(발췌):

```text
created provider transcript admission provider-transcript-admission:<digest> for intake transcript-source-intake:sha256:<digest>
provider transcript result: provider-transcript-result:<digest>
canonical raw transcript: raw-transcript:<digest>
segments: 3
LectureOS did not execute an ASR engine
```

전체 흐름을 결정적으로 재현하는 데모:

```bash
PYTHONPATH=src python3 -m lectureos.transcript_result_admission_demo
```

## 예제 구조

```text
examples/transcript-result-admission/
├── README.md
├── fixtures/
│   └── provider-result.json     # 결정적 fake provider ASR 결과 (한국어 text)
└── expected/
    └── admission-summary.json   # 데모가 재현하는 결정적 golden (content-derived id)
```

identity가 content에서 파생되므로 `admission-summary.json`의 값은 바이트 단위로 결정적이며
`tests/test_transcript_result_admission_demo.py`가 이를 재현합니다.

자세한 계약은 `docs/040_TRANSCRIPT_PIPELINE.md §14`와 `implementation/095_EXTERNAL_ASR_BOUNDARY.md`를 참고하세요.
