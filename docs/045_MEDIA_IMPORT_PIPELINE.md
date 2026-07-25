# 045_MEDIA_IMPORT_PIPELINE

- Status: Draft
- Version: Blueprint 0.1
- Last Updated: 2026-07-25
- Depends On: `000_MANIFESTO.md`, `001_PRODUCT.md`, `004_PRINCIPLES.md`, `020_PRODUCT_REQUIREMENTS.md`, `021_SYSTEM_CONTEXT.md`, `030_DATA_MODEL.md`, `031_ARCHITECTURE.md`, `040_TRANSCRIPT_PIPELINE.md`
- Referenced By:
- Amended By: `patches/PATCH-0019-media-import-application-foundation.md`

## Purpose

이 문서는 외부 로컬 파일과 LectureOS 내부 **Source Media** identity 사이의 canonical 경계를 정의한다. Media Import는
파이프라인의 **origin**이며 개념적으로 `040_TRANSCRIPT_PIPELINE.md`의 upstream이다. `030_DATA_MODEL.md §5.1`은
Source Media를 "입력받는 원본 영상 또는 오디오이며 촬영된 물리적 사실의 최상위 근거"로 정의하고 파일 수명주기의 책임
분담을 **Requires Validation**으로 남겨 두었다. 이 문서는 그 경계를 첫 slice 범위에서 확정한다.

이 문서는 제품·Application 계약(개념적 의미)만 정의한다. 미디어 디코딩·probe·transcode·ffmpeg·audio 추출·
transcription·duration·해상도·thumbnail·재생·원격 전송·관리형 저장소는 정의하지 않는다.

## 1. Media Import Application Foundation — Local Source Media Registration (First Slice)

이 절은 `PATCH-0019`로 승인된 Architect/Product 결정(M-1…M-14)을 기록한다. **첫 Media Import slice**는 caller가
지정한 하나의 로컬 파일을 검사하여, 그 **내용(content)**으로부터 파생된 canonical **Source Media** 기록을 durable하게
persist하는 것이다. 이 slice는 `SourceMediaId`의 첫 소유자이며, 지금까지 downstream 기록들이 참조만 하던 identity를
처음으로 owning 기록으로 확립한다. 원본 파일은 변경하지 않으며 복사하지 않는다.

**Scope and Origin (Confirmed, M-1):** Media Import는 파이프라인의 origin이다. 입력은 하나의 로컬 파일, 출력은 하나의
canonical Source Media 기록이다. 이 slice는 codec·duration·resolution·stream·audio·transcode·transcription·
ffmpeg·ffprobe·thumbnail·waveform·playback·rendering을 수행하지 않으며, 원격 URL·업로드·object storage·관리형
content-addressable storage·background job도 도입하지 않는다.

**Source Eligibility (Confirmed, M-2):** 유효한 입력은 caller가 지정한 **읽기 가능한 로컬 정규 파일**이다. 파일
확장자나 파일명은 미디어 타입의 증거로 취급하지 않는다(확장자는 미디어 형식의 증거가 아니다). 존재하지 않는 경로,
디렉터리, 정규 파일이 아닌 대상, 읽을 수 없는 파일, 그리고 **0바이트(빈) 파일**은 부적격이며 명시적 실패로 처리한다.
symlink는 정규 파일로 resolve되어 읽을 수 있을 때만 허용하고, resolve된 실제 경로를 관찰 경로로 기록한다.

**Media Identity Boundary (Confirmed, M-3):** Source Media identity는 파일의 **내용으로부터 파생**된다
(content-addressed). **path는 identity가 아니고, filename은 identity가 아니며, 확장자는 미디어 타입의 증거가 아니다.**
identity는 `sha256:<digest>` 형태로 fingerprint에서 결정적으로 파생된다. 동일한 내용은 항상 동일한 identity를 가진다.

**Content Fingerprint (Confirmed, M-4):** fingerprint는 파일 바이트 전체에 대한 **SHA-256**이며 파일을 스트리밍으로
해시한다(임의 크기의 파일을 통째로 메모리에 적재하지 않는다). 표현은 소문자 hex 64자다. algorithm marker
`"sha256"`을 함께 기록하여 향후 다른 algorithm을 additive하게 도입할 수 있게 한다.

**Observed Source Path (Confirmed, M-5):** import 시점에 관찰된 resolve된 절대 경로를 provenance로 기록한다. 이 경로는
**identity가 아니며**, 파일의 계속적 물리 가용성에 대한 보장도 아니다.

**Reference In Place (Confirmed, M-6):** 첫 slice는 원본 파일을 **in-place로 참조**한다. 관리형 복사본을 만들지 않고,
바이트를 별도 저장소로 옮기지 않으며, 원본을 삭제·이동하지 않는다.

**Byte Length (Confirmed, M-7):** 안정적인 파일시스템 사실로 **byte length**(> 0)를 기록한다. duration 등 디코딩이
필요한 사실은 기록하지 않는다.

**Idempotency (Confirmed, M-8):** 동일한 내용의 재import는 **기존 canonical 기록을 resolve하여 반환**하며 중복 Media
기록을 만들지 않는다. 결과는 "재사용(reused)"으로 보고된다.

**Same Content, Different Path (Confirmed, M-9):** 동일한 내용은 경로나 파일명이 달라도 동일한 identity로 resolve된다
(한 개의 canonical 기록, idempotent). 기록된 관찰 경로는 최초 import의 것으로 유지되며 immutable하다.

**Same Path, Changed Content (Confirmed, M-10):** 같은 경로라도 내용이 바뀌면 다른 fingerprint → 다른 identity → **새
canonical 기록**이 만들어진다. 서로 다른 내용의 기록들은 공존한다(insert-only).

**Missing Source After Import (Confirmed, M-11):** import 이후 원본 파일이 이동·삭제·변경되어도 persist된 Source Media
기록은 바뀌지 않는다. **LectureOS는 파일의 계속적 물리 가용성에 authoritative하지 않다**(이로써 `030 §5.1`의
Requires-Validation 경계를 이 slice 범위에서 확정한다). 저장소 무결성 검증은 원본 파일의 물리적 존재를 확인하지 않으며,
이동·삭제는 (보고한다면) 도메인 손상이 아니라 운영상의 관찰로만 취급한다.

**Persistence and Atomicity (Confirmed, M-12):** Source Media 기록은 durable·immutable·insert-only이며 하나의 atomic
transaction으로 persist된다. 부적격·해시 실패·persistence 실패 등 어떤 실패에서도 부분 기록이나 오해를 주는 상태를
남기지 않으며 기존 기록은 보존된다. content fingerprint의 canonical uniqueness가 강제된다(같은 내용에 두 개의 Media
기록이 생기지 않는다). 근접 동시 import에서도 uniqueness가 유지되고 결과는 idempotent하게 기존 기록으로 수렴한다.

**Authority (Confirmed, M-13):** Source Media 기록은 승인된 원본 사실 — content identity, content fingerprint,
byte length, 최초 관찰 경로 — 에 대해서만 authoritative하다. 미디어의 디코딩 가능성·재생 가능성·transcription·
duration·형식 유효성 등 어떤 것도 주장하지 않으며 원본 바이트를 변경하지 않는다. Source Media는 `030 §5.1`대로 파생
처리로 변경·덮어써지지 않는 최상위 물리적 근거로 남는다.

**Deferred (이후 milestone, M-14):** ffmpeg·ffprobe·codec 파싱·duration/frame rate/resolution/stream 추출·audio
추출·transcode·정규화·thumbnail·waveform·playback·Whisper 등 transcription·speech-language 감지·원격 URL·업로드·
object/cloud storage·provider adapter·background 처리·job queue·retry·progress·관리형 content-addressable storage
서브시스템·자동 원본 삭제·media rendering·NLE 연동·추가 export 형식·미디어 revision history. 이들 deferred 개념을 위한
placeholder(field·record·table·enum·protocol·interface·abstraction)는 도입하지 않는다.

**Canonical Invariants (Confirmed):** (1) 입력은 읽기 가능한 로컬 정규 파일이며 0바이트·디렉터리·비정규·부재·읽기
불가는 명시적 실패다. (2) identity는 content에서 파생되며 path·filename·확장자는 identity가 아니다. (3) fingerprint는
스트리밍 SHA-256 소문자 hex 64자이고 algorithm marker와 함께 기록된다. (4) 관찰 경로와 byte length는 provenance이며
identity가 아니다. (5) 원본은 in-place로 참조되고 복사·이동·삭제·변경되지 않는다. (6) 동일 내용 재import는 idempotent
(기존 기록 resolve). (7) 동일 내용/다른 경로는 동일 identity로 수렴한다. (8) 다른 내용/같은 경로는 새 기록이다. (9)
import 이후 원본 이동·삭제는 persist된 기록을 바꾸지 않으며 LectureOS는 물리 가용성에 authoritative하지 않다. (10)
기록은 durable·immutable·insert-only이며 atomic하게 persist되고 실패는 부분 상태를 남기지 않는다. (11) content
fingerprint의 canonical uniqueness가 강제된다. (12) Source Media는 원본 사실에만 authoritative하며 디코딩·재생·
transcription을 주장하지 않는다. (13) 원본 바이트는 변경되지 않는다. (14) deferred 개념은 placeholder를 도입하지
않는다.

## Related Documents

- [000_MANIFESTO.md](./000_MANIFESTO.md)
- [020_PRODUCT_REQUIREMENTS.md](./020_PRODUCT_REQUIREMENTS.md)
- [021_SYSTEM_CONTEXT.md](./021_SYSTEM_CONTEXT.md)
- [030_DATA_MODEL.md](./030_DATA_MODEL.md)
- [031_ARCHITECTURE.md](./031_ARCHITECTURE.md)
- [040_TRANSCRIPT_PIPELINE.md](./040_TRANSCRIPT_PIPELINE.md)
