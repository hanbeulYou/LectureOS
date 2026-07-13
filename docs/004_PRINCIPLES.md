# LectureOS Principles

- Status: Draft
- Version: Blueprint 0.1
- Last Updated: 2026-07-13
- Layer: L0
- Depends On:
  - `000_MANIFESTO.md`
  - `001_PRODUCT.md`
  - `003_VISION.md`
- Referenced By:
  - `002_FAQ.md`

## Purpose

이 문서는 LectureOS의 제품과 시스템을 설계할 때 선택지 사이에서 판단하는 규칙을 정의한다. 기능 명세, 데이터 모델, 기술 선택을 대신하지 않는다.

원칙이 충돌하면 먼저 Manifesto와 Product의 의도를 확인한다. 그래도 하나의 선택으로 좁혀지지 않으면 되돌릴 수 있고 근거를 더 모을 수 있는 쪽을 선택하며, 제품 철학을 바꾸는 결정은 제품 책임자에게 요청한다.

## Principle 1. Preserve Original Media and Its Timebase

### Intent

원본 미디어와 원본 시간축을 변경하지 않고 모든 작업의 최상위 물리적 근거로 보존한다.

### Rationale

원본과의 연결이 사라지면 인식, 교정, 자막, 편집 결과를 검증하거나 다시 만들 수 없다.

### Consequence

- 파생 작업은 원본을 덮어쓰지 않는다.
- 발화·단어 위치는 원본 시간축과의 연결을 유지한다.
- 편집 후 시간은 원본 시간과 구분한다.

### Good Example

삭제 구간을 원본 파일에 즉시 반영하지 않고, 원본 구간과 편집 후 구간의 관계를 별도 결정으로 기록한다.

### Anti-pattern

처리 편의를 위해 원본 파일을 잘라 저장하고 원본 시간 위치를 잃는다.

## Principle 2. Prefer Evidence to Inference

### Intent

자연스럽거나 편리한 추측보다 원본 미디어, 시간 정보, 사용자 확인과 같은 근거를 우선한다.

### Rationale

ASR과 LLM은 그럴듯하지만 실제 발화와 다른 결과를 만들 수 있다. 교육 콘텐츠에서는 발견하기 어려운 의미 오류가 단순 오탈자보다 위험하다.

### Consequence

- 제안은 가능한 근거와 연결한다.
- 근거가 부족하면 확정하지 않고 불확실성을 표시한다.
- confidence는 근거를 대신하지 않고 검토 우선순위를 돕는다.

### Good Example

전문용어 교정 후보를 해당 오디오 구간, raw 인식문, 변경 이유와 함께 Review Item으로 제시한다.

### Anti-pattern

문맥상 자연스럽다는 이유만으로 원본에서 확인할 수 없는 이름이나 숫자를 자동 확정한다.

## Principle 3. Separate Raw Recognition, Corrected Transcript, and Subtitle

### Intent

raw 인식문, 사람이 교정할 수 있는 Transcript, 학생용 Subtitle을 서로 다른 표현 계층으로 관리한다.

### Rationale

세 계층은 각각 모델 결과 보존, 발화 의미 확인, 학생 가독성이라는 다른 목적을 가진다.

### Consequence

- 교정으로 raw 인식문을 덮어쓰지 않는다.
- Subtitle을 다듬어도 Transcript의 의미 기록을 잃지 않는다.
- 계층 사이의 변경과 연결을 추적할 수 있어야 한다.

### Good Example

반복 발화를 Transcript에는 보존하고, 학생용 Subtitle에서는 가독성 정책에 따라 정리한 뒤 두 표현의 관계를 남긴다.

### Anti-pattern

최종 SRT 문구 하나를 raw 인식 결과이자 Transcript이자 Subtitle로 사용한다.

## Principle 4. Make Derived Results Regenerable

### Intent

Subtitle, Timeline, Review Item과 기타 파생 결과를 보존된 근거와 결정으로 다시 생성할 수 있게 한다.

### Rationale

규칙, 모델, 사용자 결정, 출력 형식은 바뀐다. 파생 파일만 남으면 변경할 때 전체 작업을 처음부터 반복해야 한다.

### Consequence

- 파생 출력은 유일한 기준 데이터가 아니다.
- 결과를 만든 입력, 설정, 결정의 연결을 보존한다.
- 재생성 시 사용자의 승인된 수정을 잃지 않는다.

### Good Example

자막 가독성 규칙이 바뀌면 원본 시간축 연결과 교정된 Transcript를 이용해 Subtitle만 다시 만든다.

### Anti-pattern

SRT만 보관하고 어떤 발화, 교정, 설정에서 생성됐는지 알 수 없게 한다.

## Principle 5. Let LLMs Propose and Code Validate Structure

### Intent

LLM은 의미 기반 후보를 제안하고, 코드가 형식과 구조적 유효성을 검증한다.

### Rationale

LLM은 맥락 해석에 유용하지만 누락, 순서 변경, 형식 오류, 비결정적 결과를 만들 수 있다.

### Consequence

- LLM 출력은 검증 가능한 구조로 받는다.
- 순서, 필수 필드, 범위, 참조 무결성 같은 조건은 코드가 확인한다.
- 검증 실패를 자동으로 정상 결과처럼 통과시키지 않는다.

### Good Example

LLM이 자막 분할 후보를 제안하고, 코드가 누락, 길이, 순서, 시간 제약을 검사한 뒤 유효한 결과만 파생 출력에 사용한다.

### Anti-pattern

LLM이 만든 전체 출력 문자열을 검증 없이 최종 파일로 저장한다.

## Principle 6. Keep Timestamps Out of LLM Control

### Intent

LLM이 최종 타임스탬프를 직접 생성하거나 변경하지 않게 한다.

### Rationale

시간 값은 원본 미디어의 물리적 위치와 연결된 구조 데이터다. 언어 모델의 추정은 그 연결과 단조성, 겹침 제약을 보장하지 못한다.

### Consequence

- LLM은 의미 경계나 분할 후보를 제안할 수 있다.
- 최종 시작·종료 시간은 원본 시간축 기반 데이터와 검증 규칙으로 계산한다.
- 시간 매핑의 실패는 Review Item 또는 명시적 오류로 남긴다.

### Good Example

LLM이 두 발화 사이를 의미 경계로 추천하면 코드가 연결된 발화·단어 위치에서 유효한 Subtitle 시작·종료 시간을 계산한다.

### Anti-pattern

LLM에게 SRT 타임스탬프를 작성하게 하고 원본 발화와의 일치를 확인하지 않는다.

## Principle 7. Prefer Explainable Recommendations to Automatic Deletion

### Intent

삭제나 큰 변경은 자동 실행보다 이유를 설명할 수 있는 추천을 우선한다.

### Rationale

잘못된 삭제는 원래 의미를 복구하기 어렵고 교육 콘텐츠의 신뢰를 훼손한다.

### Consequence

- 추천에는 대상 구간, 이유, 근거, 불확실성을 포함한다.
- 자동화 수준은 되돌릴 수 있는 범위와 검증된 오탐 비용에 맞춘다.
- 사용자 승인 없이 고위험 추천을 확정하지 않는다.

### Good Example

긴 비수업 구간을 삭제 후보로 표시하고 구간 유형과 판단 근거를 함께 보여준다.

### Anti-pattern

“잡담”으로 분류됐다는 이유만으로 원본과 결정 기록 없이 구간을 자동 제거한다.

## Principle 8. Be Conservative When Educational Value Is Unclear

### Intent

교육적 가치가 불명확하면 제거보다 유지와 검토를 우선한다.

### Rationale

반복, 침묵, 질문, 일화는 표면적으로 불필요해 보여도 이해, 복습, 사고 시간에 기여할 수 있다.

### Consequence

- 분류와 교육적 판단을 구분한다.
- 낮은 확신의 편집 후보는 Review Item으로 보낸다.
- 자동화 효율보다 중요한 설명을 잃지 않는 것을 우선한다.

### Good Example

반복 설명을 바로 삭제하지 않고 복습인지 단순 중복인지 사람이 확인하도록 표시한다.

### Anti-pattern

텍스트 유사도가 높다는 이유만으로 두 번째 설명을 교육적 중복으로 확정한다.

## Principle 9. Preserve User Corrections and Editing Decisions

### Intent

사용자가 확인한 수정과 편집 결정을 다시 실행과 후속 작업에서도 보존한다.

### Rationale

사용자의 판단은 비용을 들여 만든 중요한 제품 데이터다. 이를 잃으면 신뢰가 깨지고 같은 검수를 반복하게 된다.

### Consequence

- 사용자 수정은 원본 데이터를 덮어쓰는 방식으로 저장하지 않는다.
- 자동 재처리는 승인된 결정을 임의로 되돌리지 않는다.
- 충돌이 생기면 숨기지 않고 비교와 재확인을 제공한다.

### Good Example

모델을 바꿔 재인식해도 사용자가 확정한 전문용어 교정을 보존하고 충돌만 Review Item으로 제시한다.

### Anti-pattern

파이프라인을 다시 실행할 때 사용자의 교정과 제외 결정을 초기화한다.

## Principle 10. Stay Independent of Specific ASR, LLM, and Alignment Models

### Intent

제품 개념과 핵심 데이터 관계를 특정 ASR, LLM, alignment 모델에 종속시키지 않는다.

### Rationale

모델의 품질, 비용, 라이선스, 실행 환경은 바뀐다. 제품의 사용자 가치와 축적된 결정은 모델보다 오래가야 한다.

### Consequence

- 공급자 고유 출력은 제품 개념과 분리한다.
- 모델 교체가 원본 연결과 사용자 결정을 무효화하지 않게 한다.
- L0 문서에서 특정 모델을 영구 기본값으로 확정하지 않는다.

### Good Example

서로 다른 인식 결과를 공통 제품 의미로 변환하되 공급자별 원본 출력과 출처를 보존한다.

### Anti-pattern

특정 모델이 출력하는 고유한 구간 묶음을 LectureOS의 영구 데이터 모델로 그대로 채택한다.

## Principle 11. Cache by Stage and Support Reruns

### Intent

비용이 큰 작업을 단계별로 구분하고 필요한 단계만 안전하게 다시 실행할 수 있게 한다.

### Rationale

장시간 미디어 처리와 모델 실행은 비싸다. 작은 규칙 변경 때문에 전체 작업을 반복하면 검증과 개선이 느려진다.

### Consequence

- 단계의 입력과 결과를 식별할 수 있어야 한다.
- 변경 영향 범위를 판단해 필요한 결과만 무효화한다.
- 캐시는 재현성과 사용자 결정 보존을 해치지 않아야 한다.

### Good Example

Subtitle 분할 규칙만 바뀌면 인식과 Transcript 교정을 재사용하고 Subtitle과 관련 Review Item만 다시 만든다.

### Anti-pattern

어떤 설정이 바뀌어도 전체 미디어 인식부터 다시 실행하거나, 반대로 오래된 캐시를 조건 확인 없이 재사용한다.

## Principle 12. Optimize Total Review Time, Not Accuracy in Isolation

### Intent

개별 모델 정확도 숫자보다 강의 한 편을 완성하는 총 검수 시간을 우선한다.

### Rationale

높은 평균 정확도도 중요한 오류를 숨기거나 확인 절차를 늘리면 사용자 가치를 만들지 못한다.

### Consequence

- 정확도, 처리 속도, Review Item 수를 총 검수 시간과 함께 평가한다.
- 위험한 오류의 발견 비용을 평균 수치와 분리해 본다.
- 새 기능은 실제 작업 완료 시간을 줄이는지 검증한다.

### Good Example

평균 정확도가 비슷한 두 방법 중 중요한 오류를 더 잘 표시해 검수 시간을 줄이는 방법을 선택한다.

### Anti-pattern

사용자가 결과 전체를 다시 확인해야 하는데도 단일 정확도 지표가 높다는 이유로 성공이라 판단한다.

## Principle 13. Expose Failure and Uncertainty

### Intent

실패, 누락, 낮은 확신, 검증 불가 상태를 정상 결과처럼 숨기지 않는다.

### Rationale

사용자는 시스템의 한계를 알아야 주의를 어디에 쓸지 판단할 수 있다. 조용한 실패는 잘못된 신뢰를 만든다.

### Consequence

- 처리 실패와 부분 결과를 구분한다.
- 불확실성은 원인과 영향을 가능한 범위에서 설명한다.
- 누락된 결과를 빈 정상 결과로 표현하지 않는다.

### Good Example

정렬에 실패한 구간을 시간 정확도가 확인되지 않은 Review Item으로 표시하고 원본 구간으로 이동할 수 있게 한다.

### Anti-pattern

인식되지 않은 구간을 침묵으로 간주하거나 오류를 로그에만 남기고 최종 결과에서는 숨긴다.

## Principle 14. Optimize the Current Core Use Case First

### Intent

한국어 장시간 교육 강의 후반작업에서 실제 가치를 먼저 만든다.

### Rationale

초기부터 모든 언어, 영상 장르, 편집 환경을 만족시키려 하면 핵심 사용자의 검수 문제를 충분히 해결하지 못한다.

### Consequence

- 현재 Primary User의 자료와 작업 흐름을 우선 검증한다.
- 미래 확장 가능성은 열어두되 현재 복잡성을 정당화하는 근거로 쓰지 않는다.
- 범위 확대는 핵심 가치가 확인된 뒤 별도 승인한다.

### Good Example

한국어 전문용어와 긴 강의 검수 흐름을 먼저 개선하고 다른 언어 일반화는 검증 후 결정한다.

### Anti-pattern

실사용 검증 전에 모든 언어와 모든 편집 도구를 위한 추상화를 제품 목표로 삼는다.

## Principle 15. Avoid Irreversible Operations

### Intent

되돌리거나 비교할 수 없는 작업을 피하고, 가능한 변경을 비파괴 결정으로 표현한다.

### Rationale

자동화와 사용자는 실수할 수 있다. 원본과 이전 결정을 복구할 수 있어야 안전하게 더 많은 자동화를 시도할 수 있다.

### Consequence

- 삭제보다 제외 표시, 덮어쓰기보다 revision을 우선한다.
- 위험한 작업에는 명시적 승인과 복구 경로가 필요하다.
- 결과 변경 전후를 비교할 수 있게 한다.

### Good Example

자막 교정을 새 revision으로 기록하고 사용자가 이전 표현과 근거를 확인해 되돌릴 수 있게 한다.

### Anti-pattern

승인 즉시 이전 데이터와 변경 이유를 삭제해 복구할 수 없게 한다.

## Working Principle: Local-First by Default, Not Local-Only

### Intent

현재 핵심 사용 사례에서는 로컬 처리를 전략적 기본값으로 검토하되 영구 제품 원칙으로 확정하지 않는다.

### Rationale

장시간 미디어의 크기, 개인정보, 반복 비용, 현재 사용자 환경은 로컬 처리에 유리하다. 반면 협업, 운영, 고급 처리 요구는 선택적 클라우드 가치를 만들 수 있다.

### Consequence

- 현재 설계는 원본을 로컬에 둘 수 있는 경로를 중요하게 평가한다.
- 클라우드 사용 가능성을 원칙적으로 금지하지 않는다.
- local-first의 장기 지위는 제품 요구와 실제 검증을 통해 결정한다.

### Good Example

로컬에서 핵심 흐름을 수행할 수 있게 하면서, 사용자가 명시적으로 선택할 수 있는 외부 처리 가능성을 닫지 않는다.

### Anti-pattern

현재 장비 환경만을 근거로 모든 미래 기능의 로컬 실행을 영구 의무로 만들거나, 반대로 원본 업로드를 당연한 전제로 둔다.

## Decision Checklist

새 기능, 구조, 자동화 수준을 검토할 때 다음을 확인한다.

- 원본 미디어와 원본 시간축 연결을 보존하는가?
- 추측보다 확인 가능한 근거를 우선하는가?
- raw 인식문, Transcript, Subtitle의 책임을 섞지 않는가?
- 파생 결과를 다시 만들 수 있는가?
- LLM 제안의 구조적 유효성을 코드가 검증하는가?
- LLM이 최종 타임스탬프를 직접 통제하지 않는가?
- 삭제나 의미 변경에 설명과 확인 경로가 있는가?
- 교육적 가치가 불명확할 때 보수적으로 처리하는가?
- 사용자의 수정과 편집 결정을 보존하는가?
- 특정 ASR, LLM, alignment 모델에 불필요하게 종속되는가?
- 필요한 단계만 재실행할 수 있고 캐시 조건을 확인하는가?
- 정확도 지표가 아니라 총 검수 시간을 실제로 줄이는가?
- 실패와 불확실성을 사용자가 알 수 있는가?
- 현재 핵심 사용 사례를 먼저 개선하는가?
- 비가역적 작업을 피하고 복구·비교할 수 있는가?
- 제품 경계나 철학을 바꾸는 새 결정을 암묵적으로 만들고 있지 않은가?

## Open Questions

- 원본 시간축 기반 발화·단어 데이터의 정식 명칭과 최소 단위는 무엇인가?
- 사용자 수정과 자동 생성 결과가 충돌할 때 우선순위와 상태를 어떻게 표현할 것인가?
- 단계별 캐시의 식별과 무효화 기준은 무엇인가?
- 총 검수 시간을 어떤 대표 자료와 절차로 측정할 것인가?
- local-first는 검증 후에도 장기 제품 원칙으로 유지할 것인가?
- 어떤 위험 수준부터 자동 적용이 아니라 명시적 사용자 승인이 필요한가?

## Related Documents

- `000_MANIFESTO.md`
- `001_PRODUCT.md`
- `002_FAQ.md`
- `003_VISION.md`

## Change Log

### Blueprint 0.1 — 2026-07-13

- 기존 10개 원칙을 제품·시스템 의사결정에 필요한 15개 원칙으로 재구성했다.
- 각 원칙에 Intent, Rationale, Consequence, Good Example, Anti-pattern을 적용했다.
- 원본·시간축, 텍스트 계층, 사용자 결정, 재실행, 실패 노출, 현재 핵심 사용자 우선 원칙을 명확히 했다.
- local-first를 영구 원칙이 아닌 검증이 필요한 Working Principle로 분리했다.
