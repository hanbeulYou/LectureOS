# 예제 — Effective SRT Publication Authority (GOAL-020)

이 예제는 effective transcript 계약 세대의 **명시적 publication authority 경계**를 보여줍니다: 정확히
하나의 성공한(DELIVERED) delivery에 대해 명시적 Human Authority가 publish/withdraw를 선언하고, current
publication과 availability는 언제나 파생됩니다.

> **중요:** Delivery ≠ Publication ≠ Availability ≠ 네트워크 접근. publication은 파일을 쓰지 않고 URL을
> 만들지 않으며 네트워크 작업·수신 확인이 없습니다. withdraw는 어떤 파일·delivery·materialization·
> artifact도 삭제하지 않는 순수 authority 기록입니다. 같은 target의 반복 publish는(다른 actor여도) 이미
> 성립한 authority 상태로 **수렴**하고(최초 성립 provenance 보존), 다른 target publish·withdraw·재공개는
> append-only로 추가됩니다. 배포 파일이 나중에 삭제·변조되어도 publication history는 불변이며 파생
> availability만 `destination_missing`/`destination_mismatch`가 됩니다. `--delivery-root` 없이 조회하면
> availability는 정직하게 `not_observed`를 보고합니다. mutable `is_published` 플래그는 존재하지 않습니다.
> **`--force`는 없습니다.**

## 결정적 데모 (LLM/ASR/네트워크 아님; publication 자체는 파일을 쓰지 않음)

```bash
PYTHONPATH=src python3 -m lectureos.effective_publish_demo
```

- publish(eligibility→기록→current→available) → 정확한 replay(reused) → 다른 actor 동일 target 수렴 →
  교체 delivery publish(이전 기록은 불변 history) → withdraw(append-only·무삭제) → 재공개 → 파일
  삭제/변조에도 authority 불변(availability만 파생) → superseded 역사적 artifact의 delivery도 공개 가능 →
  FAILED delivery 공개 불가(아무것도 persist되지 않음) → 동시 동일 publish 수렴 → publish 대 withdraw
  경쟁은 명시적 conflict → 격리(publication 테이블에 URL·수신자·플래그 없음) → Validation healthy.
- content에서 파생된 golden(`expected/publish-summary.json`)이 바이트 단위로 재현됩니다.

## CLI

```bash
PYTHONPATH=src python3 -m lectureos.effective_publish_cli eligibility --delivery subtitle-effective-srt-delivery:<digest> --delivery-root "$(pwd)/deliver" --database "$(pwd)/out/lectureos.sqlite3"
PYTHONPATH=src python3 -m lectureos.effective_publish_cli publish --delivery subtitle-effective-srt-delivery:<digest> --publisher publisher:kim --delivery-root "$(pwd)/deliver" --database "$(pwd)/out/lectureos.sqlite3"
PYTHONPATH=src python3 -m lectureos.effective_publish_cli withdraw --intake transcript-source-intake:sha256:<digest> --publisher publisher:kim --database "$(pwd)/out/lectureos.sqlite3"
PYTHONPATH=src python3 -m lectureos.effective_publish_cli show --publication subtitle-effective-srt-publication:<digest> --database "$(pwd)/out/lectureos.sqlite3"
PYTHONPATH=src python3 -m lectureos.effective_publish_cli history --intake transcript-source-intake:sha256:<digest> --database "$(pwd)/out/lectureos.sqlite3"
PYTHONPATH=src python3 -m lectureos.effective_publish_cli current --intake transcript-source-intake:sha256:<digest> --database "$(pwd)/out/lectureos.sqlite3"
PYTHONPATH=src python3 -m lectureos.effective_publish_cli availability --intake transcript-source-intake:sha256:<digest> --delivery-root "$(pwd)/deliver" --database "$(pwd)/out/lectureos.sqlite3"
PYTHONPATH=src python3 -m lectureos.effective_publish_cli status --publication subtitle-effective-srt-publication:<digest> --delivery-root "$(pwd)/deliver" --database "$(pwd)/out/lectureos.sqlite3"
```

## 예제 구조

```text
examples/effective-publish/
├── README.md
└── expected/
    └── publish-summary.json   # 데모가 재현하는 결정적 golden
```

자세한 계약은 `implementation/110_EFFECTIVE_SRT_PUBLICATION.md`를 참고하세요.
