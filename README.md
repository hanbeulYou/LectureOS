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
  **v46**, 이전 모든 버전에서 additive 단일 단계 마이그레이션).
- **미디어 임포트(Media Import)** — 로컬 파일을 **content-addressed** canonical Source Media 기록으로 등록
  (스트리밍 SHA-256 → `sha256:<digest>`, 경로는 identity가 아님, 동일 내용 idempotent). 파일 identity와
  provenance만 기록하며 디코딩·transcode·probe·재생·transcription은 하지 않습니다. `lectureos.media_import_cli`.
- **전사 소스 인테이크(Transcript Source Intake)** — 이미 임포트된 `SourceMediaId`를 Transcript Pipeline의 입력으로
  admit할 적격성을 확인(040 §13). persist된 사실만으로 판정하며 디코딩·probe·audio 검증·transcription을 하지
  않습니다. content에서 파생된 intake 기록(하나의 Source Media당 하나, idempotent). `lectureos.transcript_intake_cli`.
- **External ASR Boundary(provider 결과 admission)** — 이미 admit된 intake에 대해 **외부에서 생성된 ASR 결과**를
  admit하여 첫 canonical Raw Transcript를 만듭니다(040 §14). provider 증거는 정규화 이전 상태로 보존되고 Raw
  Transcript는 별개 identity를 가집니다. identity는 결정적으로 파생되고 admission은 content로 idempotent하며 같은
  참조에 다른 내용은 conflict로 거부됩니다. **ASR 엔진을 실행하지 않으며**(Whisper·ffmpeg·network·media 접근 없음)
  결과는 로컬 JSON으로 공급됩니다. `lectureos.transcript_result_admit_cli`.
- **로컬 ASR 실행 어댑터(faster-whisper)** — 이미 admit된 intake에 대해 하나의 **로컬 ASR 엔진**을 실행하여 그
  출력을 기존 provider-neutral admission 경계로 넘겨 canonical Raw Transcript를 만듭니다(040 §15). 실행 시
  `SourceMedia` 원본 파일의 존재·fingerprint를 재검증하며, 바뀐 바이트는 새 import를 요구합니다. `faster-whisper`는
  **선택적 의존성**(지연 import; 미설치여도 core·테스트·데모 동작)이며 CPU 기본 실행입니다. admit 전에는 저장소에
  아무것도 쓰지 않고, 동등 결과는 재실행 없이 재사용됩니다. 전사 정확도는 보장되지 않습니다.
  `lectureos.local_asr_cli`.
- **Current Raw Transcript 선택 & readiness** — 한 intake의 여러 admitted Raw Transcript 중 **어느 것이 downstream의
  현재 authoritative 입력인지**를 명시적으로 선택·전환하고 readiness(not_ready/ready/error)를 노출합니다(040 §16).
  후보는 identity 순으로 열거되며(provider/model로 ranking하지 않음), 선택은 append-only(전환 시 이전 record 보존)·
  idempotent이고, 다른 intake의 transcript 선택은 거부됩니다. transcript 내용을 바꾸지 않으며 Correction을 실행하지
  않습니다. `lectureos.raw_transcript_selection_cli`.
- **Transcript 교정 후보 admission** — 현재 선택된 Raw Transcript의 한 segment에 대한 **제안된 교정을 적용하지 않고**
  기록합니다(040 §17). readiness(현재 선택)를 요구하고, immutable segment를 target하며, source-text snapshot으로 stale을
  감지하고, Raw Transcript 내용을 **결코 바꾸지 않습니다.** 후보는 결정적 identity·idempotent이며 같은 참조에 다른
  내용은 conflict로 거부됩니다. 하나의 segment에 여러 후보가 공존하고, 후보는 **ranking·적용·수락·review되지 않습니다**
  (수락·corrected revision은 이후 단계). `lectureos.correction_candidate_cli`.
- **교정 후보 Human Authority 결정** — admit된 교정 후보에 대해 사람이 **accept 또는 reject를 명시적으로 결정**합니다
  (040 §18, GOAL-009). 결정은 authority 기록일 뿐 아무것도 적용하지 않으며 후보·Raw Transcript를 변경하지 않고
  corrected revision을 만들지 않습니다. 상태는 Undecided(부재로 파생)·Accepted·Rejected뿐이고(**Modify는 이후**),
  history는 append-only이며 current authority는 최고 sequence로 파생됩니다. 동일 kind 재제출은 idempotent, Accepted
  후보만 이후 revision 대상입니다. `lectureos.correction_candidate_decision_cli`.
- **첫 Corrected Transcript Revision(교정 revision 생성)** — **현재 Accepted**인 하나의 교정 후보를 source Raw
  Transcript에 **명시적으로 적용**하여 immutable canonical corrected revision을 만듭니다(040 §19). 수락만으로는
  생성되지 않고(명시적 generate 필요), 정확히 하나의 후보만 적용되며, 교정 segment 외 모든 내용·timing은 보존됩니다.
  identity는 (candidate, authorizing decision)에서 결정적으로 파생되어 재실행은 idempotent이고, 이후 Reject는 새
  생성만 차단하며 historical revision은 보존됩니다. **revision은 current로 선택되지 않습니다**(GOAL-011).
  `lectureos.corrected_revision_cli`.
- **Current Corrected Revision 선택 & effective transcript** — §19의 immutable revision 중 **어느 것이 현재
  선택되었는지**를 명시적·append-only로 결정하고 명시적 **Raw fallback**과 결정적 **effective transcript
  resolver**를 제공합니다(040 §20). revision은 자동으로 current가 되지 않고, 선택은 아무것도 변경하지 않으며,
  이후 Reject·Raw 전환은 선택을 inapplicable하게 만들 뿐(조용한 fallback 없음) history는 불변입니다. 새 선택은
  write-time 적격성(현재 Raw parent + 현재 Accepted 후보)을 요구합니다. `lectureos.corrected_selection_cli`.
- **Effective Transcript 소비 경계** — downstream transcript 파생 작업이 **하나의 immutable transcript
  source**를 획득하는 공유 경계입니다(040 §21). 모든 해석은 §20 resolver를 통하고, snapshot은 immutable source
  identity로 로드되며, 결정적 **consumption binding**이 정확한 source·Raw parent·authority provenance·content
  fingerprint를 기록합니다. 이후 authority 변경은 binding을 바꾸지 않고 currentness가 파생되며,
  selected-but-inapplicable revision은 새 소비를 명시적으로 차단합니다(조용한 fallback 없음). 이 슬라이스의 유일한
  소비자는 중립 manifest이며 기존 소비자는 전환되지 않습니다. `lectureos.transcript_consumption_cli`.
- **Effective-Transcript Subtitle Candidate 생성** — effective transcript 계약 세대(041 §15)의 첫 canonical
  subtitle 생성 경로입니다. 명시적 요청이 GOAL-012 소비 binding(생성 전에 존재)을 통해서만 source를 획득하고,
  결정적 `deterministic_segment_passthrough` v1 generator가 immutable Candidate + 순서 있는 Cue + 정확한
  segment lineage를 atomic하게 기록합니다. identity는 정확한 source에 민감하고(같은 내용 ≠ 같은 source),
  Raw 왕복 재생성은 원래 Candidate를 재사용하며, stale은 파생될 뿐 Candidate를 바꾸지 않습니다. legacy
  subtitle pipeline·review·final selection·export는 전환되지 않습니다. `lectureos.effective_subtitle_cli`.
- **Effective-Source Subtitle Review 준비** — 정확히 하나의 immutable candidate graph를 immutable **Review
  Subject**로 명시적으로 준비합니다(GOAL-014). Subject는 candidate FK + 결정적 graph fingerprint로 정확한
  graph에 binding되고, 동일 candidate 재준비는 재사용되며, staleness는 저장되지 않고 파생됩니다. 준비는
  준비일 뿐 authority가 아닙니다 — Human Decision·reviewer·승인/거부·final selection·export·legacy review
  record는 만들어지지 않습니다. `lectureos.effective_review_cli`.
- **Effective-Source Subtitle Human Decisions** — GOAL-009 authority idiom을 재사용해 정확히 하나의 review
  subject에 대한 명시적 Accept/Reject/Modify 판단을 append-only로 기록합니다(GOAL-015). 동일 kind 반복 의도는
  idempotent reused, 판단 변경은 supersession append, current decision과 applicability는 파생됩니다. Accept는
  final selection을 만들지 않고, Reject는 삭제하지 않으며, Modify는 편집하지 않습니다.
  `lectureos.effective_decision_cli`.
- **Effective Subtitle Final Selection** — 파생 eligibility(현재 적용 가능한 Accept 필수; reject/modify/
  superseded Accept 부적격) 위에 명시적 append-only Final Selection authority를 기록합니다(GOAL-016). 선택은
  정확한 candidate·review subject·지원 Accept decision·selector lineage를 고정하고, current selection과
  applicability는 파생됩니다. Accept ≠ 선택 ≠ export — export 적격성은 부여되지 않습니다.
  `lectureos.effective_selection_cli`.
- **Effective Subtitle SRT Artifact** — 현재 적용 가능한 Final Selection에서 released canonical SRT
  serializer로 바이트 결정적 논리 artifact를 생성합니다(GOAL-017). artifact는 정확한 selection/candidate
  lineage와 content fingerprint를 고정한 불변 record이며 파일·경로·URL·materialization을 의미하지 않습니다
  (물리 materialization은 GOAL-018의 별도 명시적 단계). superseded/stale selection은 새 artifact를 만들 수 없고 currentness는
  파생됩니다. `lectureos.effective_srt_cli`.
- **Effective SRT 물리 Materialization** — 논리 artifact의 정확한 canonical bytes를 승인된 Storage Root
  아래에 실현합니다(GOAL-018, released record-first 규율·hardened writer 재사용). intent는 쓰기 전에
  durable하고 실패는 정직한 FAILED outcome으로 기록되며, 기본은 no-overwrite(명시적 `--overwrite`만 교체),
  replay는 파일을 다시 쓰지 않습니다. artifact identity는 경로에 의존하지 않고 파일 삭제는 record를 변경하지
  않습니다. `lectureos.effective_materialize_cli`.
- **Effective SRT 명시적 Delivery** — 성공한 materialization의 정확한 bytes를 승인된 Delivery Root 아래로
  명시적으로 복사합니다(GOAL-019, released record-first 규율·hardened writer 재사용). source bytes는 intent
  이전에 artifact fingerprint로 검증되고 DELIVERED는 목적지 재검증 후에만 기록되며, 실패는 안정된 category의
  정직한 FAILED outcome입니다. dangling PENDING은 명시적 `reconcile`(관찰만)로 닫힙니다. delivery ≠
  publication — URL·공개·수신 확인은 없습니다. `lectureos.effective_deliver_cli`.
- **Effective SRT Publication Authority** — 성공적으로 배달된 자막에 대한 명시적 publish/withdraw Human
  Authority입니다(GOAL-020, released Human Authority·선택 idiom 재사용). 명령은 정확히 하나의 DELIVERED
  delivery를 대상으로 하고, current publication은 intake별 최고 sequence로 파생되며, availability
  (available/withdrawn/destination_missing 등)는 authority와 분리되어 파생됩니다. withdraw는 아무것도
  삭제하지 않고 파일 삭제·변조는 history를 변경하지 않습니다. URL·네트워크·수신 확인은 없습니다.
  `lectureos.effective_publish_cli`.
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
- **저장소 검증** — **읽기 전용** 무결성 검증(identity·참조·DomainResult lineage·edit-export·media·intake 불변식)과
  `lectureos.validate_cli`. 상위 워크플로 실행 전에 저장소 일관성을 확인합니다.
- **실행 진입점** — 미디어 임포트 CLI, 전사 인테이크 CLI, edit-export CLI, 저장소 검증 CLI, mock end-to-end 데모(미디어·네트워크 불필요).

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

핵심 기능·전체 테스트·모든 데모는 **추가 의존성 없이** 표준 라이브러리만으로 동작합니다. **선택적** 의존성:

- **로컬 ASR 실행**(`lectureos.local_asr_cli`): `pip install faster-whisper` + 로컬 모델. 미설치여도 패키지
  import·전체 테스트·`local_asr_demo`(fake 엔진)는 동작합니다.

컴파일된 바이트코드(`__pycache__/`, `*.pyc`)는 버전 관리에서 제외됩니다(`.gitignore`). 테스트 실행이 만드는
바이트코드는 저장소를 dirty하게 만들지 않습니다.

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

## Media Import (미디어 임포트)

로컬 파일을 **content-addressed** canonical Source Media 기록으로 임포트합니다(데이터베이스가 없으면 생성):

```bash
PYTHONPATH=src python3 -m lectureos.media_import_cli <SOURCE_PATH> --database /path/to/lectureos.sqlite3
```

- Media identity는 파일 **내용**의 스트리밍 SHA-256에서 파생됩니다(`sha256:<digest>`). **경로·파일명·확장자는
  identity가 아닙니다.**
- 동일 내용 재import는 idempotent(`reused`), 다른 내용은 새 기록(`created`)입니다.
- 파일 identity와 provenance만 기록하며, 디코딩·transcode·probe·재생·transcription은 하지 않고 원본을 변경하지
  않습니다. 성공 시 종료 코드 `0`, 오류 시 `1`(DB·원본 불변).
- import 이후 원본이 이동·삭제되어도 기록은 유지됩니다(물리 가용성에 authoritative하지 않음).

동작 예제는 [`examples/media-import/`](examples/media-import/README.md), 계약은
`docs/045_MEDIA_IMPORT_PIPELINE.md`와 `implementation/080_MEDIA_IMPORT.md`를 참고하세요.

## Transcript Source Intake (전사 소스 인테이크)

이미 임포트된 Source Media(`SourceMediaId`)를 Transcript Pipeline의 입력으로 admit할 적격성을 확인합니다
(040 §13). Media Import와는 **분리된 단계**이며 **경로가 아니라 `SourceMediaId`를 받습니다**:

```bash
PYTHONPATH=src python3 -m lectureos.transcript_intake_cli --media sha256:<digest> --database /path/to/lectureos.sqlite3
```

- 적격성은 **persist된 사실**로만 판정됩니다(id가 persist된 `source_media`로 resolve되면 적격). media를 디코딩·
  probe·재생·transcription하지 않으며 audio stream 존재를 주장하지 않습니다. **transcription을 실행하지 않습니다.**
- intake identity는 Source Media에서 파생되어(`transcript-source-intake:<id>`) 하나의 Source Media당 하나의
  canonical intake만 있고 반복 admission은 idempotent(`reused`)입니다.
- 형식이 잘못된 identity·unknown Source Media는 명시적으로 거부(exit 1, 저장소 불변)됩니다. import 이후 원본이
  이동·삭제되어도 intake 적격성에는 영향이 없습니다.

동작 예제는 [`examples/transcript-intake/`](examples/transcript-intake/README.md), 계약은
`docs/040_TRANSCRIPT_PIPELINE.md §13`과 `implementation/090_TRANSCRIPT_SOURCE_INTAKE.md`를 참고하세요.

## External ASR Boundary — Provider Transcript Result Admission

이미 admit된 intake(`TranscriptSourceIntakeId`)에 대해 **외부에서 생성된 ASR 결과**(provider-neutral / LectureOS-
native JSON)를 admit하여 첫 canonical Raw Transcript를 만듭니다(040 §14). **입력은 intake id와 JSON 문서이며 media
경로가 아닙니다. ASR 엔진을 실행하지 않습니다**(Whisper·ffmpeg·network·media 접근 없음 — 결과는 공급됨):

```bash
PYTHONPATH=src python3 -m lectureos.transcript_result_admit_cli \
  --intake transcript-source-intake:sha256:<digest> \
  --input provider-result.json --database /path/to/lectureos.sqlite3
```

- provider 증거(`ProviderTranscriptResult`)는 정규화 이전 상태로 보존되고 canonical `RawTranscript`는 별개
  identity를 가집니다. 모든 identity는 anchor `(intake, provider, model, provider_result_ref)`에서 결정적으로
  파생됩니다.
- admission은 전체 payload의 `content_fingerprint`로 idempotent(`reused`)하며, 같은 참조에 **다른 내용**을 admit하면
  conflict로 거부(덮어쓰지 않음)됩니다. 하나의 intake는 여러 provider 결과를, 하나의 provider 결과는 하나의 Raw
  Transcript를 가집니다.
- segment timing은 초 단위(`end > start`, 비겹침·비내림차순), text는 그대로 보존(한국어 포함), 빈 결과·잘못된
  timing·unknown intake는 명시적으로 거부(exit 1, 저장소 불변)됩니다.

동작 예제는 [`examples/transcript-result-admission/`](examples/transcript-result-admission/README.md), 계약은
`docs/040_TRANSCRIPT_PIPELINE.md §14`와 `implementation/095_EXTERNAL_ASR_BOUNDARY.md`를 참고하세요.

## Local ASR Execution (faster-whisper)

이미 admit된 intake에 대해 하나의 **로컬 ASR 엔진(faster-whisper)**을 실행하여 그 출력을 위 admission 경계로 넘겨
canonical Raw Transcript를 만듭니다(040 §15). **intake identity를 받습니다(미디어 경로가 아님).** 실행 시 원본
파일의 존재·fingerprint를 재검증하며 CPU 기본으로 동작합니다:

```bash
PYTHONPATH=src python3 -m lectureos.local_asr_cli \
  --intake transcript-source-intake:sha256:<digest> \
  --database /path/to/lectureos.sqlite3 --model tiny --language ko
```

- `faster-whisper`는 **선택적 런타임 의존성**입니다(설치: `pip install faster-whisper`). **미설치여도** 패키지
  import·전체 테스트·아래 결정적 데모(fake 엔진)는 동작합니다. 실제 실행에는 로컬 모델이 추가로 필요합니다.
- 바이트가 바뀐 원본은 옛 `SourceMediaId`로 전사되지 않고 새 import를 요구합니다. adapter는 Raw Transcript를 직접
  쓰지 않고 admission service만 사용하며, 동등 결과는 **재실행 없이 재사용**됩니다.
- 실패(source 없음/변경, 의존성/모델 없음, 엔진 실패, malformed 출력, admission conflict)는 exit 1이며 admit 이전에는
  저장소를 변경하지 않습니다. **전사 정확도·모든 미디어 포맷·모든 OS·GPU 가용성은 보장되지 않습니다.**

결정적 데모(실제 ASR 아님):

```bash
PYTHONPATH=src python3 -m lectureos.local_asr_demo
```

동작 예제는 [`examples/local-asr/`](examples/local-asr/README.md), 계약은
`docs/040_TRANSCRIPT_PIPELINE.md §15`와 `implementation/096_LOCAL_ASR_ADAPTER.md`를 참고하세요.

## Current Raw Transcript Selection & Readiness

한 intake의 여러 admitted Raw Transcript 중 **현재 authoritative 입력**을 명시적으로 선택·전환하고 readiness를
노출합니다(040 §16). **intake·raw transcript identity를 받습니다(경로가 아님).** 후보는 identity 순으로 열거되며
**ranking하지 않습니다.**

```bash
# 후보 목록 (provider/model 메타데이터 포함, ranking 없음)
PYTHONPATH=src python3 -m lectureos.raw_transcript_selection_cli candidates \
  --intake transcript-source-intake:sha256:<digest> --database /path/to/lectureos.sqlite3

# 현재 Raw Transcript 선택/전환 (append-only, idempotent)
PYTHONPATH=src python3 -m lectureos.raw_transcript_selection_cli select \
  --intake transcript-source-intake:sha256:<digest> \
  --transcript raw-transcript:<digest> --database /path/to/lectureos.sqlite3

# readiness (not_ready / ready / error)
PYTHONPATH=src python3 -m lectureos.raw_transcript_selection_cli readiness \
  --intake transcript-source-intake:sha256:<digest> --database /path/to/lectureos.sqlite3
```

- selection은 명시적 authority 결정입니다(provider/model/시간/길이/confidence로 추론하지 않음). 동일 선택 반복은
  `reused`, 전환은 `switched`(이전 record 보존)이며 다른 intake의 transcript나 unknown/malformed는 exit 1로 거부됩니다.
- readiness는 유효한 current 선택에서만 파생되며 원본 파일 존재·ASR/provider 가용성·정확도·review에 의존하지 않습니다.
- selection은 transcript 내용을 바꾸지 않고 **Correction을 실행하지 않습니다**(Correction은 아직 미구현).

결정적 데모: `PYTHONPATH=src python3 -m lectureos.raw_transcript_selection_demo`. 동작 예제는
[`examples/raw-transcript-selection/`](examples/raw-transcript-selection/README.md), 계약은
`docs/040_TRANSCRIPT_PIPELINE.md §16`과 `implementation/097_RAW_TRANSCRIPT_SELECTION.md`를 참고하세요.

## Transcript Correction Candidate Admission

현재 선택된 Raw Transcript의 한 segment에 대한 **제안된 교정을 적용하지 않고** 기록합니다(040 §17). Correction
Candidate는 **제안**이며 Raw Transcript 내용을 결코 바꾸지 않습니다. **intake·raw transcript·segment identity를
받습니다(경로가 아님). `--apply` 옵션은 없습니다:**

```bash
# 제안 교정 admit (적용되지 않음)
PYTHONPATH=src python3 -m lectureos.correction_candidate_cli admit \
  --intake transcript-source-intake:sha256:<digest> \
  --input candidate.json --database /path/to/lectureos.sqlite3

# admit된 후보 목록 (current 선택에 대한 applicability 포함, ranking 없음)
PYTHONPATH=src python3 -m lectureos.correction_candidate_cli list \
  --intake transcript-source-intake:sha256:<digest> --database /path/to/lectureos.sqlite3
```

- admission은 intake의 readiness(현재 Raw Transcript 선택)와 target segment가 그 current Raw Transcript에 속함을
  요구하며, source-text snapshot이 segment text와 일치해야 합니다(stale 감지). no-op·빈 제안·unknown·unrelated·
  conflict·not-ready는 exit 1로 거부되며 저장소는 변경되지 않습니다.
- 후보는 결정적 identity로 idempotent하고, 하나의 segment에 여러 distinct 후보가 공존하며, 어떤 후보도 ranking·적용·
  수락되지 않습니다. current Raw Transcript 전환 후에도 historical 후보는 보존되며 not-applicable로 표시됩니다.

결정적 데모: `PYTHONPATH=src python3 -m lectureos.correction_candidate_demo`. 동작 예제는
[`examples/correction-candidate/`](examples/correction-candidate/README.md), 계약은
`docs/040_TRANSCRIPT_PIPELINE.md §17`과 `implementation/098_CORRECTION_CANDIDATE_ADMISSION.md`를 참고하세요.

## Correction Candidate Human Authority Decision

admit된 교정 후보에 대해 사람이 **accept/reject를 명시적으로 결정**합니다(040 §18). 결정은 **authority 기록일 뿐**이며
아무것도 적용하지 않고 후보·Raw Transcript를 변경하지 않으며 corrected revision을 만들지 않습니다. **candidate identity를
받습니다(경로가 아님). `--apply`는 없습니다:**

```bash
# 사람의 accept/reject 결정 (적용되지 않음)
PYTHONPATH=src python3 -m lectureos.correction_candidate_decision_cli decide \
  --candidate correction-candidate:<digest> --kind accept --reviewer reviewer:kim \
  --database /path/to/lectureos.sqlite3

# 현재 authority (undecided / accepted / rejected) 와 revision 대상 여부
PYTHONPATH=src python3 -m lectureos.correction_candidate_decision_cli status \
  --candidate correction-candidate:<digest> --database /path/to/lectureos.sqlite3

# append-only 결정 history
PYTHONPATH=src python3 -m lectureos.correction_candidate_decision_cli history \
  --candidate correction-candidate:<digest> --database /path/to/lectureos.sqlite3
```

- 상태는 Undecided(결정 record 없음; 부재로 파생)·Accepted·Rejected뿐입니다(**Modify는 이후 단계**). history는
  append-only(마음이 바뀌면 새 결정 append, 이전 보존)이고 current authority는 최고 sequence로 파생됩니다.
- identity는 `(candidate, kind, sequence)`에서 결정적으로 파생되어 동일 kind 재제출은 idempotent(`reused`)하며, 같은
  anchor에 다른 provenance는 conflict로 거부됩니다. **Accepted** 후보만 이후 corrected-revision 대상입니다.
- malformed·unknown·Modify·conflict는 exit 1로 거부되며 저장소는 변경되지 않습니다.

결정적 데모: `PYTHONPATH=src python3 -m lectureos.correction_candidate_decision_demo`. 동작 예제는
[`examples/correction-decision/`](examples/correction-decision/README.md), 계약은
`docs/040_TRANSCRIPT_PIPELINE.md §18`과 `implementation/099_CORRECTION_CANDIDATE_DECISION.md`를 참고하세요.

## Corrected Transcript Revision Generation

**현재 Accepted**인 하나의 교정 후보를 **명시적으로 적용**하여 immutable corrected revision을 만듭니다(040 §19).
수락만으로는 생성되지 않으며, revision은 **current로 선택되지 않습니다**(GOAL-011). **candidate identity를
받습니다(경로가 아님). `--force`/`--apply-all`은 없습니다:**

```bash
# 현재 Accepted 후보를 적용 (revision은 current로 선택되지 않음)
PYTHONPATH=src python3 -m lectureos.corrected_revision_cli generate \
  --candidate correction-candidate:<digest> --database /path/to/lectureos.sqlite3

# revision 내용/lineage 조회 · 후보의 generation 목록
PYTHONPATH=src python3 -m lectureos.corrected_revision_cli show --revision corrected-revision:<digest> --database /path/to/lectureos.sqlite3
PYTHONPATH=src python3 -m lectureos.corrected_revision_cli list --candidate correction-candidate:<digest> --database /path/to/lectureos.sqlite3
```

- 생성은 후보의 현재 §18 authority(Accepted)와 구조적 적용 가능성(현재 선택·segment lineage·snapshot 일치)을
  요구합니다. Undecided/Rejected/stale/unknown은 exit 1로 거부되며 저장소는 변경되지 않습니다.
- 정확히 하나의 후보가 적용되고, 교정 segment는 `replaces_segment_id`를 가진 새 segment(timing 보존), 비변경 내용은
  그대로 참조됩니다. Raw Transcript·후보·결정 history는 불변입니다.
- 동일 요청 재실행은 `reused`이며, 이후 Reject는 새 생성만 차단하고 historical revision은 보존됩니다. 서로 다른
  Accept(재수락)는 별개 revision을 만들며 revision들은 공존합니다.

결정적 데모: `PYTHONPATH=src python3 -m lectureos.corrected_revision_demo`. 동작 예제는
[`examples/corrected-revision/`](examples/corrected-revision/README.md), 계약은
`docs/040_TRANSCRIPT_PIPELINE.md §19`와 `implementation/100_CORRECTED_REVISION_GENERATION.md`를 참고하세요.

## Current Corrected Revision Selection & Effective Transcript

§19의 immutable revision 중 **현재 선택**을 명시적·append-only로 결정하고(명시적 Raw fallback 포함) 결정적
**effective transcript resolver**를 제공합니다(040 §20). **Revision 존재 ≠ 선택 ≠ 적용 가능성 ≠ effective 해석.**
**identity를 받습니다(경로 아님). `--force`는 없습니다:**

```bash
# corrected revision 선택 (문맥은 revision lineage에서 파생) / 명시적 Raw fallback
PYTHONPATH=src python3 -m lectureos.corrected_selection_cli select --revision corrected-revision:<digest> --reviewer selector:kim --database /path/to/lectureos.sqlite3
PYTHONPATH=src python3 -m lectureos.corrected_selection_cli fallback --intake transcript-source-intake:sha256:<digest> --reviewer selector:kim --database /path/to/lectureos.sqlite3

# 상태 / history / effective transcript 해석
PYTHONPATH=src python3 -m lectureos.corrected_selection_cli status  --intake transcript-source-intake:sha256:<digest> --database /path/to/lectureos.sqlite3
PYTHONPATH=src python3 -m lectureos.corrected_selection_cli history --intake transcript-source-intake:sha256:<digest> --database /path/to/lectureos.sqlite3
PYTHONPATH=src python3 -m lectureos.corrected_selection_cli resolve --intake transcript-source-intake:sha256:<digest> --database /path/to/lectureos.sqlite3
```

- revision은 생성만으로 current가 되지 않습니다(자동 promotion 금지). history는 append-only이고 current는 최고
  sequence로 파생되며, 동일 대상 재선택은 `reused`, 전환은 append입니다. no-history와 명시적 fallback은 역사적으로
  구분됩니다.
- 새 선택은 write-time 적격성(현재 Raw parent + 현재 Accepted 후보)을 요구하고, 이후 Reject·Raw 전환은 선택된
  revision을 **inapplicable**하게 만들 뿐 history를 바꾸지 않으며 resolver가 이유와 함께 **명시적으로** 보고합니다
  (조용한 fallback 없음). 기존 downstream 파이프라인(자막·export)은 이 slice에서 전환되지 않습니다.

결정적 데모: `PYTHONPATH=src python3 -m lectureos.corrected_selection_demo`. 동작 예제는
[`examples/corrected-selection/`](examples/corrected-selection/README.md), 계약은
`docs/040_TRANSCRIPT_PIPELINE.md §20`과 `implementation/101_CORRECTED_REVISION_SELECTION.md`를 참고하세요.

## Effective Transcript Consumption Boundary

downstream transcript 파생 작업이 **하나의 immutable transcript source**를 획득하는 공유 소비 경계입니다(040
§21). **현재 authority ≠ 소비된 source ≠ historical lineage ≠ currentness ≠ 무결성.**
**identity를 받습니다(경로 아님). `--force`는 없습니다:**

```bash
# effective transcript input 해석(읽기 전용): resolver 상태·provenance·source·segment manifest
PYTHONPATH=src python3 -m lectureos.transcript_consumption_cli resolve-input --intake transcript-source-intake:sha256:<digest> --database /path/to/lectureos.sqlite3

# manifest consumption binding 기록(또는 동일 source 재사용 수렴)
PYTHONPATH=src python3 -m lectureos.transcript_consumption_cli consume --intake transcript-source-intake:sha256:<digest> --database /path/to/lectureos.sqlite3

# 저장된 binding과 파생 currentness 조회
PYTHONPATH=src python3 -m lectureos.transcript_consumption_cli status --intake transcript-source-intake:sha256:<digest> --database /path/to/lectureos.sqlite3
```

- 모든 해석은 §20 resolver를 통하며(소비자는 resolver 논리를 복제하지 않음) segment는 immutable source identity로
  로드됩니다 — mixed-source snapshot은 불가능합니다. binding identity는 (consumer kind·intake·source kind·정확한
  source identity)에서 결정적으로 파생됩니다.
- 같은 source 재소비는 `reused`(중복 binding 없음), source 전환은 별도 binding입니다. 이후 Reject·Raw 전환은 기존
  binding을 바꾸지 않고 currentness(`current`/`stale_due_to_*`/`unresolvable`)가 파생됩니다. staleness는 손상이
  아니며 자동 재처리·삭제·전환은 없습니다.

결정적 데모: `PYTHONPATH=src python3 -m lectureos.transcript_consumption_demo`. 동작 예제는
[`examples/transcript-consumption/`](examples/transcript-consumption/README.md), 계약은
`docs/040_TRANSCRIPT_PIPELINE.md §21`과 `implementation/102_EFFECTIVE_TRANSCRIPT_CONSUMPTION.md`를 참고하세요.

## Effective-Transcript Subtitle Candidate Generation

effective transcript 계약 세대(041 §15 / PATCH-0029)의 첫 canonical subtitle 생성 경로입니다. **transcript
authority ≠ 소비 ≠ subtitle 생성 ≠ review ≠ decision ≠ final selection ≠ export.**
**identity를 받습니다(경로 아님). `--force`는 없습니다:**

```bash
# 명시적 생성(또는 동일 semantic 재사용 수렴): GOAL-012 binding이 생성 전에 존재
PYTHONPATH=src python3 -m lectureos.effective_subtitle_cli generate --intake transcript-source-intake:sha256:<digest> --database /path/to/lectureos.sqlite3

# Candidate 상세(lineage + cue) / 목록 / 파생 currentness
PYTHONPATH=src python3 -m lectureos.effective_subtitle_cli show --candidate subtitle-effective-candidate:<digest> --database /path/to/lectureos.sqlite3
PYTHONPATH=src python3 -m lectureos.effective_subtitle_cli list --intake transcript-source-intake:sha256:<digest> --database /path/to/lectureos.sqlite3
PYTHONPATH=src python3 -m lectureos.effective_subtitle_cli status --candidate subtitle-effective-candidate:<digest> --database /path/to/lectureos.sqlite3
```

- Raw와 Corrected source 모두 지원: 정확한 source identity·Raw parent·소비 binding·snapshot fingerprint가
  Candidate에 고정되고, 교정 cue는 교체 segment lineage(`replaces_segment_id`)를 보존합니다.
  selected-but-inapplicable revision은 생성을 명시적으로 차단합니다(조용한 fallback 없음).
- 동일 binding + 동일 generator semantics 재생성은 `reused`(중복 없음), Raw → Corrected → Raw 왕복은 원래
  Candidate를 재사용하며, 내용이 같아도 source entity가 다르면 별개 Candidate입니다. 이후 authority 변경은
  Candidate를 변경하지 않고 currentness(`current`/`stale_due_to_*`)가 파생됩니다.
- legacy subtitle 표현(별도 계약 세대)·review·Human Decision·final selection·SRT export는 읽지도 쓰지도
  않으며 ProcessingRun/UnitExecution을 만들지 않습니다.

결정적 데모: `PYTHONPATH=src python3 -m lectureos.effective_subtitle_demo`. 동작 예제는
[`examples/effective-subtitle/`](examples/effective-subtitle/README.md), 계약은
`docs/041_SUBTITLE_PIPELINE.md §15`와 `implementation/103_EFFECTIVE_SUBTITLE_GENERATION.md`를 참고하세요.

## Effective-Source Subtitle Review Preparation

effective transcript 계약 세대의 첫 downstream 단계입니다(GOAL-014). **Candidate 존재 ≠ review 준비 ≠
review record ≠ Human Decision ≠ final selection ≠ export 적격성.**
**identity를 받습니다(경로 아님). `--force`는 없습니다:**

```bash
# 명시적 준비(또는 동일 candidate 재사용 수렴)
PYTHONPATH=src python3 -m lectureos.effective_review_cli prepare --candidate subtitle-effective-candidate:<digest> --database /path/to/lectureos.sqlite3

# subject 상세 / candidate의 canonical subject / 파생 currentness
PYTHONPATH=src python3 -m lectureos.effective_review_cli show --review-subject subtitle-effective-review-subject:<digest> --database /path/to/lectureos.sqlite3
PYTHONPATH=src python3 -m lectureos.effective_review_cli list --candidate subtitle-effective-candidate:<digest> --database /path/to/lectureos.sqlite3
PYTHONPATH=src python3 -m lectureos.effective_review_cli status --review-subject subtitle-effective-review-subject:<digest> --database /path/to/lectureos.sqlite3
```

- Subject identity는 (preparation 계약, 정확한 candidate, graph fingerprint)에서 결정적으로 파생되며 candidate당
  preparation 계약당 정확히 하나의 canonical subject가 존재합니다(UNIQUE anchor·동시 요청 수렴·divergent payload는
  명시적 conflict).
- source-stale candidate도 구조적으로 유효하면 명시적으로 준비 가능하고(역사적 검토 가능성 ≠ 현재 결정 적용
  가능성), currentness(`current`/`stale_due_to_candidate_source`/`unresolvable`)는 항상 파생됩니다. 손상된
  candidate graph는 준비를 명시적으로 거부합니다(아무것도 저장 안 됨).
- Human Decision·reviewer·승인/거부·완료 상태·final selection·export·legacy review record는 만들어지지 않으며
  가짜 review status는 표시되지 않습니다.

결정적 데모: `PYTHONPATH=src python3 -m lectureos.effective_review_demo`. 동작 예제는
[`examples/effective-review/`](examples/effective-review/README.md), 계약은
`docs/041_SUBTITLE_PIPELINE.md §15`와 `implementation/104_EFFECTIVE_SUBTITLE_REVIEW_PREPARATION.md`를
참고하세요.

## Effective-Source Subtitle Human Decisions

effective transcript 계약 세대에 대한 Human Authority입니다(GOAL-015, GOAL-009 idiom 재사용).
**Decision 존재 ≠ current Decision ≠ applicability ≠ final selection ≠ export 적격성.**
**identity를 받습니다(경로 아님). `--force`는 없습니다:**

```bash
# 명시적 Accept/Reject/Modify (동일 kind 반복은 idempotent reused, 변경은 supersession append)
PYTHONPATH=src python3 -m lectureos.effective_decision_cli decide --review-subject subtitle-effective-review-subject:<digest> --decision accept --reviewer reviewer:kim --database /path/to/lectureos.sqlite3

# decision 상세 / append-only history / 파생 current / 파생 applicability
PYTHONPATH=src python3 -m lectureos.effective_decision_cli show --decision subtitle-effective-review-decision:<digest> --database /path/to/lectureos.sqlite3
PYTHONPATH=src python3 -m lectureos.effective_decision_cli history --review-subject subtitle-effective-review-subject:<digest> --database /path/to/lectureos.sqlite3
PYTHONPATH=src python3 -m lectureos.effective_decision_cli current --review-subject subtitle-effective-review-subject:<digest> --database /path/to/lectureos.sqlite3
PYTHONPATH=src python3 -m lectureos.effective_decision_cli status --decision subtitle-effective-review-decision:<digest> --database /path/to/lectureos.sqlite3
```

- identity는 (subject, kind, sequence)에서 결정적으로 파생되고 reviewer/rationale은 provenance입니다(fingerprint로
  검증). current는 최고 sequence로 파생되며 mutable flag·최신 row 휴리스틱이 없습니다.
- applicability(applicable/superseded/stale_due_to_candidate_source/unresolvable)는 파생이며 kind와 무관합니다 —
  reject/modify도 current+applicable일 수 있습니다. stale subject에 대한 명시적 역사적 decision은 허용됩니다.
- reviewer는 명시적 provenance(authorization 아님)이고, 손상된 candidate graph는 decision을 명시적으로 거부하며,
  legacy decision·review·final selection·export는 만들어지지 않습니다.

결정적 데모: `PYTHONPATH=src python3 -m lectureos.effective_decision_demo`. 동작 예제는
[`examples/effective-decision/`](examples/effective-decision/README.md), 계약은
`implementation/105_EFFECTIVE_SUBTITLE_REVIEW_DECISION.md`를 참고하세요.

## Effective Subtitle Final Selection

effective transcript 계약 세대의 Final Selection authority입니다(GOAL-016; GOAL-011 selection idiom +
GOAL-015 authority lineage). **Accept ≠ Final Selection ≠ export.**
**identity를 받습니다(경로 아님). `--force`는 없습니다:**

```bash
# 파생 eligibility(차단 사유 명시) / 명시적 선택(동일 authority 상태 재선택은 idempotent reused)
PYTHONPATH=src python3 -m lectureos.effective_selection_cli eligibility --review-subject subtitle-effective-review-subject:<digest> --database /path/to/lectureos.sqlite3
PYTHONPATH=src python3 -m lectureos.effective_selection_cli select --review-subject subtitle-effective-review-subject:<digest> --selector selector:kim --database /path/to/lectureos.sqlite3

# 선택 상세 / append-only history / 파생 current / 파생 applicability
PYTHONPATH=src python3 -m lectureos.effective_selection_cli show --selection subtitle-effective-final-selection:<digest> --database /path/to/lectureos.sqlite3
PYTHONPATH=src python3 -m lectureos.effective_selection_cli history --intake transcript-source-intake:sha256:<digest> --database /path/to/lectureos.sqlite3
PYTHONPATH=src python3 -m lectureos.effective_selection_cli current --intake transcript-source-intake:sha256:<digest> --database /path/to/lectureos.sqlite3
PYTHONPATH=src python3 -m lectureos.effective_selection_cli status --selection subtitle-effective-final-selection:<digest> --database /path/to/lectureos.sqlite3
```

- 선택 identity는 (계약, intake scope, candidate, subject, 지원 decision, sequence)에서 결정적으로 파생되고
  selector/rationale은 fingerprint로 검증되는 provenance입니다. current는 intake scope별 최고 sequence로
  파생됩니다(mutable flag·최신 row 휴리스틱 없음).
- 지원 Accept가 바뀌면 명시적 재선택은 새 lineage로 append되고, 다른 candidate 선택은 supersede하며, 이전
  선택들은 불변 history로 남습니다. applicability(applicable/superseded/supporting_decision_superseded/
  stale_due_to_candidate_source/unresolvable)는 항상 파생됩니다.
- reject/modify/superseded Accept/stale subject는 새 선택에 부적격(명시적 거부, 아무것도 저장 안 됨)이며,
  export·물리 파일·legacy final selection은 만들어지지 않습니다.

결정적 데모: `PYTHONPATH=src python3 -m lectureos.effective_selection_demo`. 동작 예제는
[`examples/effective-selection/`](examples/effective-selection/README.md), 계약은
`implementation/106_EFFECTIVE_SUBTITLE_FINAL_SELECTION.md`를 참고하세요.

## Effective Subtitle SRT Artifact

effective transcript 계약 세대의 논리적 SRT export입니다(GOAL-017). **Final Selection ≠ Artifact ≠ 물리
파일.** **identity를 받습니다(경로 아님). `--force`는 없습니다:**

```bash
# 파생 export eligibility / 명시적 생성(동일 selection+serializer 재요청은 idempotent reused)
PYTHONPATH=src python3 -m lectureos.effective_srt_cli eligibility --selection subtitle-effective-final-selection:<digest> --database /path/to/lectureos.sqlite3
PYTHONPATH=src python3 -m lectureos.effective_srt_cli generate --selection subtitle-effective-final-selection:<digest> --database /path/to/lectureos.sqlite3

# artifact 상세 / 정확한 SRT payload / intake 목록 / 파생 currentness
PYTHONPATH=src python3 -m lectureos.effective_srt_cli show --artifact subtitle-effective-srt-artifact:<digest> --database /path/to/lectureos.sqlite3
PYTHONPATH=src python3 -m lectureos.effective_srt_cli content --artifact subtitle-effective-srt-artifact:<digest> --database /path/to/lectureos.sqlite3
PYTHONPATH=src python3 -m lectureos.effective_srt_cli list --intake transcript-source-intake:sha256:<digest> --database /path/to/lectureos.sqlite3
PYTHONPATH=src python3 -m lectureos.effective_srt_cli status --artifact subtitle-effective-srt-artifact:<digest> --database /path/to/lectureos.sqlite3
```

- eligibility는 파생입니다: 현재 적용 가능한 Final Selection만 새 artifact를 생성할 수 있습니다
  (selection_not_found/selection_not_current/selection_not_applicable 차단 사유 명시).
- 직렬화는 released canonical serializer(`canonical_srt` v1)를 그대로 재사용합니다: 1부터 번호, ordinal 순서,
  `HH:MM:SS,mmm`(ROUND_HALF_UP), LF·블록 간 빈 줄·trailing LF, 텍스트 정확 보존.
- identity는 (계약, 정확한 selection, candidate, serializer 계약, content fingerprint)에서 파생되며 content
  fingerprint 단독은 identity가 아닙니다 — 내용이 같아도 selection이 다르면 별개 artifact입니다. 기존
  artifact는 authority 변경 후에도 불변이며 currentness만 파생됩니다.

결정적 데모: `PYTHONPATH=src python3 -m lectureos.effective_srt_demo`. 동작 예제는
[`examples/effective-srt/`](examples/effective-srt/README.md), 계약은
`implementation/107_EFFECTIVE_SUBTITLE_SRT_ARTIFACT.md`를 참고하세요.

## Effective SRT Physical Materialization

effective transcript 계약 세대의 물리 materialization 경계입니다(GOAL-018). **Artifact ≠ Materialization ≠
delivery.** **`--force`는 없습니다:**

```bash
# 명시적 실현 (기본 no-overwrite; 동일 payload 재요청은 rewrite 없이 reused)
PYTHONPATH=src python3 -m lectureos.effective_materialize_cli materialize --artifact subtitle-effective-srt-artifact:<digest> --storage-root /path/to/out --database /path/to/lectureos.sqlite3

# record 상세 / 파생 상태 + 물리 파일 일치 여부 / append-only history
PYTHONPATH=src python3 -m lectureos.effective_materialize_cli show --materialization subtitle-effective-srt-materialization:<digest> --storage-root /path/to/out --database /path/to/lectureos.sqlite3
PYTHONPATH=src python3 -m lectureos.effective_materialize_cli status --materialization subtitle-effective-srt-materialization:<digest> --storage-root /path/to/out --database /path/to/lectureos.sqlite3
PYTHONPATH=src python3 -m lectureos.effective_materialize_cli list --artifact subtitle-effective-srt-artifact:<digest> --storage-root /path/to/out --database /path/to/lectureos.sqlite3
```

- released record-first 규율: immutable intent(PENDING)가 쓰기 전에 durable, 종결 outcome
  (MATERIALIZED/FAILED)이 쓰기 후에 기록, 상태는 항상 파생. collision·containment·I/O 실패는 정직한 FAILED
  outcome입니다(숨김·자동 재시도 없음).
- hardened writer 재사용: 승인된 root 격리, symlink 거부, 원자적 쓰기, 동일-bytes idempotent, 다른-bytes
  기본 거부; 명시적 `--overwrite`만 기존 regular 파일을 원자적으로 교체합니다(새 append-only event).
- materialization identity는 (artifact, relative location, sequence)에서 파생되며 경로는 identity가 아니라
  write provenance입니다. 파일 삭제·변형은 record를 변경하지 않고 손상도 아닙니다.

결정적 데모: `PYTHONPATH=src python3 -m lectureos.effective_materialize_demo`. 동작 예제는
[`examples/effective-materialize/`](examples/effective-materialize/README.md), 계약은
`implementation/108_EFFECTIVE_SRT_MATERIALIZATION.md`를 참고하세요.

## Explicit Effective SRT Delivery

effective transcript 계약 세대의 명시적 delivery 경계입니다(GOAL-019). **Artifact ≠ Materialization ≠
Delivery ≠ Publication.** **`--force`는 없습니다:**

```bash
# 파생 적격성 (persist되지 않음)
PYTHONPATH=src python3 -m lectureos.effective_deliver_cli eligibility --materialization subtitle-effective-srt-materialization:<digest> --storage-root /path/to/out --database /path/to/lectureos.sqlite3

# 명시적 delivery (기본 no-overwrite; 동일 요청 replay는 rewrite 없이 reused)
PYTHONPATH=src python3 -m lectureos.effective_deliver_cli deliver --materialization subtitle-effective-srt-materialization:<digest> --storage-root /path/to/out --delivery-root /path/to/deliver --database /path/to/lectureos.sqlite3

# record 상세 / 파생 상태 + source·destination 파일 일치 여부 / append-only history / 명시적 reconcile
PYTHONPATH=src python3 -m lectureos.effective_deliver_cli show --delivery subtitle-effective-srt-delivery:<digest> --storage-root /path/to/out --delivery-root /path/to/deliver --database /path/to/lectureos.sqlite3
PYTHONPATH=src python3 -m lectureos.effective_deliver_cli status --delivery subtitle-effective-srt-delivery:<digest> --storage-root /path/to/out --delivery-root /path/to/deliver --database /path/to/lectureos.sqlite3
PYTHONPATH=src python3 -m lectureos.effective_deliver_cli list --materialization subtitle-effective-srt-materialization:<digest> --storage-root /path/to/out --delivery-root /path/to/deliver --database /path/to/lectureos.sqlite3
PYTHONPATH=src python3 -m lectureos.effective_deliver_cli reconcile --delivery subtitle-effective-srt-delivery:<digest> --storage-root /path/to/out --delivery-root /path/to/deliver --database /path/to/lectureos.sqlite3
```

- released record-first 규율: source bytes는 intent 이전에 artifact fingerprint로 검증(결함 시 아무것도
  persist되지 않음), immutable intent가 목적지 쓰기 전에 durable, DELIVERED는 목적지 bytes 재검증 후에만
  기록, 실패는 안정된 category(`destination_exists_different`·`destination_unsafe`·`destination_missing`·
  `write_failed`·`verification_failed`)의 정직한 FAILED outcome.
- delivery identity는 (계약, materialization, artifact, delivery kind, 목적지 location, expected
  fingerprint, sequence, overwrite 정책)에서 파생되며 절대 root·시각은 참여하지 않습니다. 동시 동일 요청은
  durable intent slot으로 수렴하고 divergent 충돌은 명시적 conflict입니다.
- superseded/stale artifact의 성공한 materialization도 배달 가능(역사적 운용성)하며, 배달 파일 삭제는 record를
  변경하지 않고 손상도 아닙니다. dangling PENDING은 명시적 `reconcile`(관찰만, 쓰기 없음)로 닫힙니다.

결정적 데모: `PYTHONPATH=src python3 -m lectureos.effective_deliver_demo`. 동작 예제는
[`examples/effective-deliver/`](examples/effective-deliver/README.md), 계약은
`implementation/109_EFFECTIVE_SRT_DELIVERY.md`를 참고하세요.

## Effective SRT Publication Authority

배달된 effective 자막에 대한 명시적 publication authority 경계입니다(GOAL-020). **Delivery ≠ Publication ≠
Availability ≠ 네트워크 접근.** **`--force`는 없습니다:**

```bash
# 파생 적격성 (persist되지 않음)
PYTHONPATH=src python3 -m lectureos.effective_publish_cli eligibility --delivery subtitle-effective-srt-delivery:<digest> --delivery-root /path/to/deliver --database /path/to/lectureos.sqlite3

# 명시적 publish / withdraw (append-only Human Authority; withdraw는 아무것도 삭제하지 않음)
PYTHONPATH=src python3 -m lectureos.effective_publish_cli publish --delivery subtitle-effective-srt-delivery:<digest> --publisher publisher:kim --delivery-root /path/to/deliver --database /path/to/lectureos.sqlite3
PYTHONPATH=src python3 -m lectureos.effective_publish_cli withdraw --intake transcript-source-intake:sha256:<digest> --publisher publisher:kim --database /path/to/lectureos.sqlite3

# 불변 record / append-only history / 파생 current / 파생 availability / 관찰 분리 status
PYTHONPATH=src python3 -m lectureos.effective_publish_cli show --publication subtitle-effective-srt-publication:<digest> --database /path/to/lectureos.sqlite3
PYTHONPATH=src python3 -m lectureos.effective_publish_cli history --intake transcript-source-intake:sha256:<digest> --database /path/to/lectureos.sqlite3
PYTHONPATH=src python3 -m lectureos.effective_publish_cli current --intake transcript-source-intake:sha256:<digest> --database /path/to/lectureos.sqlite3
PYTHONPATH=src python3 -m lectureos.effective_publish_cli availability --intake transcript-source-intake:sha256:<digest> --delivery-root /path/to/deliver --database /path/to/lectureos.sqlite3
PYTHONPATH=src python3 -m lectureos.effective_publish_cli status --publication subtitle-effective-srt-publication:<digest> --delivery-root /path/to/deliver --database /path/to/lectureos.sqlite3
```

- publish는 정확히 하나의 DELIVERED delivery를 대상으로 하며(암시적 latest 없음), 같은 target의 반복 명령은
  (다른 actor여도) 이미 성립한 authority 상태로 수렴합니다(최초 성립 provenance 보존). withdraw·교체 publish·
  재공개는 append-only로 추가되고 이전 record는 불변 history로 남습니다.
- current publication은 intake별 최고 sequence로 파생되고(mutable 플래그·created_at·latest-row 없음),
  availability는 authority와 분리되어 파생됩니다 — 배포 파일 삭제/변조는 `destination_missing`/
  `destination_mismatch`일 뿐 history를 변경하지 않으며, `--delivery-root` 없이는 정직하게
  `not_observed`입니다.
- publication identity는 (계약, intake scope, kind, 정확한 target, sequence)에서 파생되며 publisher와
  rationale은 fingerprint로 검증되는 provenance입니다. 경쟁 명령은 명시적 conflict입니다.

결정적 데모: `PYTHONPATH=src python3 -m lectureos.effective_publish_demo`. 동작 예제는
[`examples/effective-publish/`](examples/effective-publish/README.md), 계약은
`implementation/110_EFFECTIVE_SRT_PUBLICATION.md`를 참고하세요.

## Effective Subtitle Pipeline v1 Release

GOAL-013~020의 여덟 단계(candidate → review → Human decision → final selection → 논리 SRT artifact →
물리 materialization → 검증된 delivery → publication authority → 파생 availability)가 하나의 정합적인
릴리스로 닫혔습니다(GOAL-021). 모든 전이는 명시적 명령이고, current 상태는 파생되며, history는
append-only이고, legacy 파이프라인은 격리되어 있습니다.

```bash
# 전체 파이프라인 결정적 릴리스 데모 (byte-stable golden)
PYTHONPATH=src python3 -m lectureos.effective_subtitle_release_demo
```

- 릴리스 문서: `implementation/111_EFFECTIVE_SUBTITLE_PIPELINE_V1_RELEASE.md`
- 릴리스 manifest·golden: [`examples/effective-subtitle-v1/`](examples/effective-subtitle-v1/README.md)
- 릴리스 수용 스위트: `tests/test_effective_subtitle_pipeline_release.py`
- 단계별 완결 문서: `implementation/103`~`110` · 단계별 CLI는 위 각 섹션 참고
- v1에 포함되지 않는 것(유예 경계): HTTP 서빙·다운로드 endpoint·공개 URL·클라우드 업로드·접근 제어·수신
  확인·frontend·자동 오케스트레이션·Lecture Intelligence

## Repository Validation (저장소 검증)

저장소가 내부적으로 일관적인지 **읽기 전용**으로 검증합니다(저장소를 수정하지 않습니다). identity, 참조,
DomainResult lineage, edit-export 파이프라인 불변식을 확인합니다:

```bash
PYTHONPATH=src python3 -m lectureos.validate_cli --database lecture.db
PYTHONPATH=src python3 -m lectureos.validate_cli --database lecture.db --format json
```

종료 코드는 machine-readable입니다 — `0` healthy, `1` errors, `2` warnings only. 검증 철학, 진단 형식, 진단 코드
목록은 [`examples/repository-validation/`](examples/repository-validation/README.md)와
`implementation/070_REPOSITORY_VALIDATION.md`를 참고하세요.

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
│   ├── persistence/        # insert-only SQLite 저장소 + additive 스키마(v46)
│   ├── infrastructure/     # 로컬 파일시스템 writer(temp-file + 원자적 배치)
│   ├── execution/          # 처리 실행, 유닛 실행, DomainResult lineage
│   ├── providers/          # 선택적 provider 어댑터(예: OpenAI) — MVP에는 불필요
│   ├── composition.py      # composition root: 구체 어댑터를 서비스에 결선
│   ├── media_import_cli.py # 로컬 미디어 임포트 CLI
│   ├── transcript_intake_cli.py # 전사 소스 인테이크 CLI
│   ├── transcript_result_admit_cli.py # External ASR Boundary provider 결과 admission CLI
│   ├── local_asr_cli.py    # 로컬 ASR 실행 어댑터 CLI (faster-whisper)
│   ├── raw_transcript_selection_cli.py # Current Raw Transcript 선택 & readiness CLI
│   ├── correction_candidate_cli.py # Transcript 교정 후보 admission CLI
│   ├── correction_candidate_decision_cli.py # 교정 후보 Human Authority 결정 CLI
│   ├── corrected_revision_cli.py # Corrected Transcript Revision 생성 CLI
│   ├── corrected_selection_cli.py # Current Corrected Revision 선택 & resolve CLI
│   ├── transcript_consumption_cli.py # Effective Transcript 소비 경계 CLI
│   ├── effective_subtitle_cli.py # Effective-Transcript Subtitle Candidate 생성 CLI
│   ├── effective_review_cli.py # Effective-Source Subtitle Review 준비 CLI
│   ├── effective_decision_cli.py # Effective-Source Subtitle Human Decision CLI
│   ├── effective_selection_cli.py # Effective Subtitle Final Selection CLI
│   ├── effective_srt_cli.py # Effective Subtitle SRT Artifact CLI
│   ├── effective_materialize_cli.py # Effective SRT 물리 Materialization CLI
│   ├── effective_deliver_cli.py # Effective SRT 명시적 Delivery CLI
│   ├── effective_publish_cli.py # Effective SRT Publication Authority CLI
│   ├── edit_export_cli.py  # 실행 가능한 Edit Export CLI
│   ├── edit_export_demo.py # 실행 가능한 mock end-to-end 데모(미디어·네트워크 불필요)
│   └── *_acceptance.py     # 인프로세스 end-to-end 인수 실행기
├── tests/                  # unittest 스위트(1600개 이상)
├── examples/edit-export/   # 동작 예제 + golden 출력
├── docs/                   # 릴리스된 Blueprint(제품 의미) + docs/README.md
├── patches/                # Blueprint 변경 기록(PATCH-0001 … PATCH-0020)
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

- **Blueprint:** **PATCH-0020**까지 안정(`docs/`, `patches/`).
- **구현:** edit-export MVP 완료; **Effective Subtitle Pipeline v1 릴리스 완료**
  (`implementation/111_EFFECTIVE_SUBTITLE_PIPELINE_V1_RELEASE.md`); SQLite 스키마 **v46**; 전체 스위트
  green(1800개 이상).
- **거버넌스:** Blueprint 우선 — 제품 의미를 바꾸려면 PATCH를 먼저 쓰고 나서 구현합니다.
  `AGENTS.md`와 `implementation/050_IMPLEMENTATION_WORKFLOW.md` 참고.

## Documentation (문서)

- 제품 Blueprint와 권장 읽기 순서: [`docs/README.md`](docs/README.md).
- Export 파이프라인 계약(representation → assembly → artifact → JSON/materialization):
  `docs/044_EXPORT_PIPELINE.md` §19–§22.
- 구현 현황: `implementation/060_IMPLEMENTATION_STATUS.md`.

## License (라이선스)

[MIT License](LICENSE). 저작권 표기는 현재 중립적으로 `LectureOS`로 되어 있으니, 필요하면 실명/조직명으로 바꾸세요.
