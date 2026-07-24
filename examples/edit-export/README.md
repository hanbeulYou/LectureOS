# 예제 — Edit Export (Developer Preview)

이 예제는 LectureOS의 **Edit Export** 파이프라인을 end-to-end로 보여줍니다. **실제 미디어 파일, Whisper 모델,
네트워크 없이** 단일 프로세스에서 실행되어, 실제이고 결정적인 로컬 JSON export 파일 하나를 만듭니다.

## 무엇을 보여주나

```text
Fake Transcript (가짜 인식문)
    -> 강의 분석 + 사람의 검수 (accept / modify 결정)
    -> Approved Edit Decision (승인된 편집 결정)
    -> Approved Edit Export Representation
    -> Edit Export Assembly        (승인 편집들을 하나의 coherent Export Scope로 모음)
    -> Edit Export Artifact        (승인 의미의 canonical external representation)
    -> LectureOS Edit Export JSON  (직렬화 — lectureos-edit-export-json v1)
    -> Local File                  (materialization)
```

이 파이프라인은 시계(wall-clock)를 읽지 않고 고정된 identity를 사용하므로 export 파일은 **바이트 단위로 결정적**입니다.
같은 실행은 항상 같은 바이트를 만듭니다. 그래서 `expected/edit-export.json`을 회귀 테스트용 golden 픽스처로 쓸 수
있습니다(`tests/test_edit_export_demo.py` 참고).

## 실행 방법

클린 체크아웃에서(src 레이아웃 — 설치 단계 없음):

```bash
PYTHONPATH=src python3 -m lectureos.edit_export_demo --output-directory "$(pwd)/examples/edit-export/out"
```

임시 디렉터리에 일회용 SQLite 데이터베이스를 만들고 전체 파이프라인을 실행한 뒤, export를
`examples/edit-export/out/edit-export.json`에 씁니다. 출력 디렉터리에는 JSON 파일만 만들어집니다.

예상 콘솔 출력(경로는 다를 수 있음):

```text
LectureOS Edit Export — mock end-to-end demo

  fake transcript segments : 2
  analysis findings        : 1
  edit candidates          : 2
  human review decisions   : 2
  approved edit decisions  : 2
  export representations   : 3
  assembly                 : edit-export-demo-assembly (3 members)
  artifact                 : edit-export-demo (3 edits)

  exported lectureos-edit-export-json v1 (1221 bytes)
  -> .../examples/edit-export/out/edit-export.json
```

## 예제 구조

```text
examples/edit-export/
├── README.md                     # 이 문서
└── expected/
    └── edit-export.json          # 데모가 바이트 단위로 재현하는 golden 출력
```

별도의 입력 파일은 없습니다. 여기서 "입력"은 데모(`src/lectureos/edit_export_demo.py`)가 만드는 결정적 가짜 인식문과
seeding된 사람의 검수 결정입니다. 생성된 출력은 `expected/edit-export.json`과 비교됩니다.

## 출력이 나타내는 것

`edit-export.json`은 LectureOS 고유 형식(`lectureos-edit-export-json` v1)입니다. 하나의 Source Timeline에 대한 승인
편집 결정을 **서술적으로** 표현합니다 — 각 승인 편집마다 승인된 Source Timeline range, 승인된 candidate type/label,
승인된 rationale, 승인 decision kind(`accept` 또는 `modify`), 사람 actor를 담습니다. 실행 가능한 편집이나 NLE
교환 형식이 **아닙니다**: LectureOS는 소스 미디어를 자르지 않습니다. `docs/044_EXPORT_PIPELINE.md` §19–§22 참고.

## golden 파일 재생성

golden 픽스처는 같은 데모로 만들어집니다. 의도적이고 리뷰된 변경 이후에 재생성하려면:

```bash
PYTHONPATH=src python3 -m lectureos.edit_export_demo \
  --output-directory examples/edit-export/expected --overwrite
```
