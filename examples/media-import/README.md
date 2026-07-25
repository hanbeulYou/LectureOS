# 예제 — Media Import (미디어 임포트)

이 예제는 LectureOS의 **Media Import**를 보여줍니다. 로컬 파일을 **content-addressed** canonical Source Media
기록으로 등록하는 첫 슬라이스입니다. 실제 비디오·코덱·ffmpeg·네트워크 없이 동작합니다.

> **중요:** 이 슬라이스는 파일의 **identity와 provenance만** 기록합니다. 미디어를 디코딩·transcode·probe·재생·
> transcription하지 않습니다. **경로(path)는 Media identity가 아니며**, 파일명·확장자도 미디어 타입의 증거가
> 아닙니다. import 이후 원본 파일이 이동·삭제되어도 기록은 바뀌지 않습니다(LectureOS는 파일의 계속적 물리
> 가용성에 authoritative하지 않습니다).

## 무엇을 보여주나

```text
로컬 파일  ->  스트리밍 SHA-256 fingerprint  ->  content-addressed Source Media 기록
```

- Media identity는 내용에서 파생됩니다: `sha256:<digest>`.
- 동일 내용 재import는 idempotent(기존 기록 재사용).
- 동일 내용/다른 파일명은 같은 identity로 수렴.
- 다른 내용/같은 경로는 새 기록.
- 원본 바이트는 변경되지 않으며, 임포트된 저장소는 무결성 검증을 통과합니다.

## 실행 방법

CLI로 하나의 로컬 파일을 임포트합니다(데이터베이스가 없으면 생성됩니다):

```bash
PYTHONPATH=src python3 -m lectureos.media_import_cli examples/media-import/fixtures/sample-a.bin \
  --database "$(pwd)/out/lectureos.sqlite3"
```

예상 출력(경로는 환경마다 다름):

```text
created source media sha256:7be6a9582ff6c7bd4e66c052dc634a38b88909402f2fb330d663000d7f2079a5 \
  (fingerprint sha256:7be6a9582ff6c7bd4e66c052dc634a38b88909402f2fb330d663000d7f2079a5, 810 bytes)
```

같은 내용을 다시 임포트하면 `reused ...`로, `sample-a-copy.bin`(같은 바이트, 다른 파일명)도 `reused ...`로
같은 identity에 수렴합니다. `sample-b.bin`(다른 바이트)은 새 `created ...` 기록이 됩니다.

전체 흐름을 결정적으로 재현하는 데모:

```bash
PYTHONPATH=src python3 -m lectureos.media_import_demo
```

## 예제 구조

```text
examples/media-import/
├── README.md
├── fixtures/
│   ├── sample-a.bin        # 임의의 media-like 바이트 (재생 가능한 비디오가 아님)
│   ├── sample-a-copy.bin   # sample-a.bin 과 바이트가 동일 (파일명만 다름)
│   └── sample-b.bin        # 다른 바이트
└── expected/
    └── import-summary.json # 데모가 재현하는 결정적 golden(identity·fingerprint·byte length)
```

fixture는 **재생 가능한 비디오가 아니라** 임의의 결정적 바이트입니다. content가 identity를 결정하므로
`import-summary.json`의 identity·fingerprint 값은 바이트 단위로 결정적이며 `tests/test_media_import_demo.py`가
이를 재현합니다. 관찰 경로(observed path)만 환경마다 다릅니다.

## 검증

임포트한 저장소는 읽기 전용 무결성 검증을 통과합니다:

```bash
PYTHONPATH=src python3 -m lectureos.validate_cli --database out/lectureos.sqlite3
```

자세한 계약은 `docs/045_MEDIA_IMPORT_PIPELINE.md`와 `implementation/080_MEDIA_IMPORT.md`를 참고하세요.
