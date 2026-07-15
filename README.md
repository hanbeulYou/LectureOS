# LectureOS

LectureOS는 긴 한국어 강의를 편집할 때 생기는 반복 작업을 줄이기 위한 AI 기반 후반작업 시스템입니다.

강의 영상을 완성하려면 자막만 만들어서는 부족합니다. 잘못 인식된 말을 고치고, 자막을 읽기 좋게 나누고, 편집이 필요한 구간을 찾아 직접 확인해야 합니다. LectureOS는 흩어져 있던 이 작업들을 한곳에서 이어서 처리하고 수정과 결정 내역을 남깁니다.

> 현재 저장소에는 구현 코드가 아닌 **릴리스가 완료된 Blueprint v1**이 담겨 있습니다.

## Why LectureOS

긴 강의 영상의 후반작업에서는 다음 작업이 반복됩니다.

- 음성 인식 오류와 전문용어 교정
- 긴 자막의 분할과 타이밍 조정
- 쉬는 시간, 무음, 잡담과 다시 말한 구간 확인
- 삭제하거나 유지할 편집 후보 검토
- 같은 구간의 반복 재생과 결정 재입력

LectureOS에서는 AI가 판단에 필요한 근거와 후보를 준비하고, 최종 결정은 사람이 내립니다. 교육자가 단순 반복 작업보다 강의의 의미와 품질을 살피는 데 더 많은 시간을 쓰게 하는 것이 목표입니다.

## Workflow

```text
원본 미디어
    |
    +--> 텍스트 처리
    |       원본 인식문
    |       -> 교정된 인식문
    |       -> 최종 자막
    |
    +--> 편집 후보 처리
            강의 분석
            -> 분석 결과
            -> 편집 후보
            -> 사람의 검수
            -> 승인된 편집 결정

승인된 결과
    -> 외부 전달용 산출물
    -> 외부 편집 과정
```

텍스트 처리와 편집 후보 처리는 어느 한쪽이 부가 기능이 아닌 동등한 핵심 영역입니다. LectureOS는 원본 영상을 자동으로 잘라내지 않으며, 전문 영상 편집기를 대신하지도 않습니다.

## Design Principles

- **원본 우선:** 원본 미디어와 원본 시간축을 변경하지 않습니다.
- **인식문과 자막의 분리:** 발화 내용을 기록하는 인식문과 시청하기 좋게 다듬은 자막을 구분합니다.
- **후보와 결정의 분리:** AI가 만든 후보를 사람의 결정으로 간주하지 않습니다.
- **분석과 편집의 분리:** 강의를 분석하고 편집 후보를 제안할 뿐, 실제 영상을 편집하지 않습니다.
- **사람의 결정권:** 수락, 거절, 수정에 대한 최종 권한은 사람에게 있습니다.
- **결정과 산출물의 분리:** 승인된 결정과 외부로 전달하는 파일이나 표현을 구분합니다.
- **제공자 독립성:** 특정 AI, 음성 인식 서비스, 영상 편집 도구나 업체에 핵심 구조를 종속시키지 않습니다.
- **안전한 재처리:** 일부 단계를 다시 실행해도 이전 근거와 사용자 결정을 몰래 지우지 않습니다.

## Project Status

**Blueprint v1 — 릴리스 완료 (2026-07-15)**

현재 완료된 범위:

- 제품 철학과 제품 요구사항
- 시스템 경계, 개념 데이터 모델, 논리 아키텍처
- 인식문과 자막 처리 흐름
- 강의 분석, 검수, 결과 전달 흐름
- 개념 수준의 플러그인 시스템
- PATCH를 이용한 Blueprint 변경 관리

데이터베이스, API, 실행 환경, 기술 스택, 플러그인 실행 방식, 세부 화면과 실제 구현은 아직 정하지 않았습니다. 자세한 릴리스 기준은 [Blueprint v1 Release](docs/090_BLUEPRINT_RELEASE.md)에서 확인할 수 있습니다.

## Documentation

| 영역 | 문서 | 역할 |
| --- | --- | --- |
| 기초 문서 | [000~004](docs/000_MANIFESTO.md) | 존재 이유, 제품 경계, FAQ, 비전, 설계 원칙 |
| 제품 | [020](docs/020_PRODUCT_REQUIREMENTS.md) | 제품 범위와 필수 요구사항 |
| 시스템 모델 | [021](docs/021_SYSTEM_CONTEXT.md), [030](docs/030_DATA_MODEL.md), [031](docs/031_ARCHITECTURE.md) | 시스템 경계, 핵심 개념, 논리적 책임 |
| 텍스트 처리 | [040](docs/040_TRANSCRIPT_PIPELINE.md), [041](docs/041_SUBTITLE_PIPELINE.md) | 인식문과 자막이 만들어지는 과정 |
| 편집 후보 처리 | [042](docs/042_LECTURE_INTELLIGENCE_PIPELINE.md), [043](docs/043_REVIEW_PIPELINE.md), [044](docs/044_EXPORT_PIPELINE.md) | 분석, 사람의 결정, 외부 전달 표현 |
| 확장 모델 | [050](docs/050_PLUGIN_SYSTEM.md) | 기능 계약과 플러그인의 경계 |
| 릴리스 | [090](docs/090_BLUEPRINT_RELEASE.md) | Blueprint v1 기준선과 다음 단계 |
| 변경 기록 | [PATCH-0001~0005](patches/PATCH-0001-l0-and-prd-stabilization.md) | 변경 이유와 결정 기록 |

### Recommended Reading Order

1. [선언문](docs/000_MANIFESTO.md)
2. [제품 정의](docs/001_PRODUCT.md)와 [제품 요구사항](docs/020_PRODUCT_REQUIREMENTS.md)
3. [시스템 컨텍스트](docs/021_SYSTEM_CONTEXT.md)
4. [데이터 모델](docs/030_DATA_MODEL.md)과 [아키텍처](docs/031_ARCHITECTURE.md)
5. [인식문 처리](docs/040_TRANSCRIPT_PIPELINE.md)와 [자막 처리](docs/041_SUBTITLE_PIPELINE.md)
6. [강의 분석](docs/042_LECTURE_INTELLIGENCE_PIPELINE.md), [검수](docs/043_REVIEW_PIPELINE.md), [결과 전달](docs/044_EXPORT_PIPELINE.md)
7. [플러그인 시스템](docs/050_PLUGIN_SYSTEM.md)
8. [Blueprint v1 릴리스](docs/090_BLUEPRINT_RELEASE.md)
9. 변경 배경이 필요할 때 [PATCH 문서](patches/)

## Repository Structure

```text
LectureOS/
├── docs/       # 현재 적용되는 Blueprint 문서
├── docs/ai/    # AI 협업 및 문서 작업 규칙
└── patches/    # Blueprint 변경 이유와 영향 기록
```

Blueprint에는 현재 합의된 내용을 적고, PATCH에는 그 내용을 바꾼 이유를 남깁니다. 개념의 의미나 문서 사이의 책임을 바꾸려면 기존 문서를 조용히 고치는 대신 새로운 PATCH를 먼저 작성합니다.

## Contributing

현재는 구현을 서두르기보다 Blueprint의 일관성을 지키고, 여기서 실제 구현 설계로 자연스럽게 이어지는 일을 우선합니다.

변경을 제안할 때는 다음을 확인해 주세요.

- 기존 제품 계약과 시스템 경계를 유지하는가?
- 새 개념이나 기능이 필요한 이유가 분명한가?
- 영향을 받는 Blueprint 문서를 식별했는가?
- 사람의 결정권, 변경 이력, 원본 시간축과의 연결을 보존하는가?
- 특정 구현 방식을 Blueprint의 영구 계약으로 못 박고 있지 않은가?

자세한 절차는 [Blueprint v1 변경 정책](docs/090_BLUEPRINT_RELEASE.md#8-change-policy)을 따릅니다.

## License

아직 라이선스를 정하지 않았습니다. 저장소가 공개되어 있더라도 별도 라이선스가 추가되기 전에는 사용·수정·재배포 권한이 자동으로 주어지지 않습니다.
