# LectureOS — Post-Silence Transcript Timestamp Drift: Architect Decision Prompt

당신은 LectureOS 프로젝트의 **Architect**다.

이번 세션의 목표는 실제 강의 3편에서 관측된 **무발화 직후 transcript timestamp 밀림**에 대해
LectureOS가 입장을 가질 것인지, 가진다면 **어느 계층에서 어떤 계약으로** 다룰 것인지 결정하는 것이다.

이번 세션에서는 **구현하지 않는다.**
threshold를 정하지 않는다.
PATCH를 바로 쓰지 않는다. (결정이 서면 후속 세션에서 PATCH를 쓴다.)

---

# 1. 반드시 먼저 읽을 것

프롬프트 요약보다 **released Blueprint 문언과 implementation report 원문을 우선**한다.

## Blueprint

* `docs/040_TRANSCRIPT_PIPELINE.md`
  * §4.2 External ASR Boundary / §4.3 Raw Transcript Preservation
  * §14 A-10 (Timing Semantics), A-11 (Text Semantics), A-14 (Authority)
  * §15 L-6 (Execution Metadata), **L-16 (VAD Non-adoption)**
* `docs/041_SUBTITLE_PIPELINE.md`
  * §7 Time Representation
  * §16 R-계열 readability contract

## PATCH

* PATCH-0039 (timing representation tolerance)
* PATCH-0040 (previous-text conditioning, P-8/P-9)
* PATCH-0041 / PATCH-0043 (readability parameter v1/v2)
* PATCH-0045 (transcript quality diagnostic boundary)

## Implementation report

* `implementation/122_FULL_LENGTH_REAL_MEDIA_E2E_VALIDATION.md`
* `implementation/124_READABLE_SUBTITLE_CUE_COMPOSITION.md`
* `implementation/131_STRUCTURAL_POPULATION_LABEL_ANALYSIS.md` ← **이번 결정의 직접 근거**

---

# 2. 관측된 현상

실제 강의 3편(5.86시간, 강사 2명)에서 다음이 확인됐다.

## 2.1 사람이 청취해 확인한 사례

구조 기반 전수 라벨링(221건) 중 라벨러가 **요청받지 않았는데도** 다음을 반복 기록했다.

```text
전사가 주장하는 시작 시각보다 실제 발화가 7~27초 늦게 시작함
```

5건 모두 **긴 무발화 구간 직후 첫 segment**였다.
라벨러는 일반 발화 구간에서는 이 현상이 없다고 확인했다.

## 2.2 released SRT에서의 독립 측정

라벨 없이, 이미 생성된 SRT 2편으로 측정한 결과:

| 위치 | cue 수 | 평균 길이 | 7초 초과 비율 |
|---|---|---|---|
| 무발화(≥10s) 직후 첫 cue | 19 | **5.3초** | **21%** |
| 그 외 전체 | 4,265 | 2.8초 | 0.3% |

무발화 직후에만 duration이 **1.9배**, readability 경고율이 **70배**다.

## 2.3 추정되는 기제

Whisper 계열이 decode window가 무음에서 열릴 때, segment의 start를 **실제 발화 시작이 아니라
decode window 시작점**에 앵커링하는 것으로 보인다.

**이 기제는 아직 검증되지 않았다.** 결정 과정에서 확인이 필요하면 명시하라.

---

# 3. 현재 계약상 위치

## 3.1 계약 위반이 아니다

* `§14` A-10은 ordering, positivity, non-overlap만 구속한다.
  **segment start가 발화 시작을 의미한다고 주장하는 문언은 없다.**
* `§14` A-11은 text를 정확히 보존하라고 요구한다.
* `§14` A-14는 admission이 **"media 파일을 읽지 않는다"**고 명시한다.
  따라서 admission 경계에는 이 현상을 검출할 수단이 원리적으로 없다.

## 3.2 그러나 제품 결과에 영향이 있다

* 자막이 최대 **27초 일찍** 표시된다.
* `124`가 기록한 `READABILITY_DURATION_ABOVE_MAXIMUM` 경고 상당수가
  편집상 사유가 아니라 이 artefact일 가능성이 있다.
* 이미 materialize된 SRT 2편이 이 오차를 담고 있다.

## 3.3 L-16이 직접 맞물린다

`§15` L-16은 VAD를 채택하지 않기로 하면서 사유를 명시했다.

> `vad_filter`는 실제 강사 발화를 **삭제**하고 downstream에서 사용할 수 없는 duration의 segment를
> 만든다. 2초 발화에 212초 segment는 자막 단위로 성립하지 않는다.
>
> **이는 사유가 기록된 deferral이지 영구 금지가 아니다: 발화 손실과 segment duration을 함께
> 해결하는 이후 계약은 VAD를 채택할 수 있다.**

즉 L-16이 거부한 두 사유 중 **하나(segment duration)가 바로 이번 현상**이다.
L-16은 이 문제를 해결하는 계약이라면 VAD 채택 가능성을 명시적으로 열어두었다.

**단, 나머지 사유(실제 발화 삭제)는 여전히 해결되지 않았다.**

---

# 4. 결정해야 할 것

## Q1. LectureOS는 이 현상에 입장을 가지는가?

* 가진다 → Q2로
* 가지지 않는다 → 그 근거를 기록하고 종료 (이것도 유효한 결정이다)

## Q2. 어느 계층의 문제인가?

최소 다음 넷을 비교하라. 하나를 고르라는 뜻이 아니라, **책임이 어디에 있는지** 판단하라는 뜻이다.

### 계층 A — Provider 실행 (`§15`)

VAD 또는 등가의 발화 시작 검출을 도입해 provider가 정확한 timestamp를 내게 한다.

* L-16이 조건부로 열어둔 경로
* 미해결 사유: 실제 발화 삭제 위험이 그대로 남는다
* Raw Transcript 내용 자체가 달라진다 → 새 admission anchor, 기존 record와 병존

### 계층 B — Admission 경계 (`§14`)

admission이 timestamp를 검증하거나 보정한다.

* **A-14와 정면 충돌**한다. admission은 media를 읽지 않는다.
* A-11의 "제출된 값 그대로 보존"과도 충돌 가능
* 채택하려면 released 계약을 바꿔야 한다 → 그 비용이 정당한가?

### 계층 C — Subtitle 시간 표현 (`041`)

Raw Transcript는 그대로 두고, **cue 시간을 만들 때** 보정한다.

* `041` §7 Time Representation과 readable cue composition이 이미 시간을 다룬다
* Raw 보존 원칙(`§2` Raw Before Corrected)을 건드리지 않는다
* 다만 무엇을 근거로 보정할 것인가? 오디오를 읽지 않으면 추정일 뿐이다

### 계층 D — 진단만 (`PATCH-0045` 계열)

보정하지 않고 **경고로 노출**한다.

* PATCH-0045가 이미 만든 Quality Warning 경계를 재사용
* 사람이 판단하고 `§17`~`§19`로 교정
* 자동 보정 없음 → 가장 보수적
* 그러나 자막은 여전히 일찍 뜬다

## Q3. 오디오를 읽을 것인가?

이 질문이 실질적으로 Q2를 결정한다.

* **읽지 않는다** → C의 추정 보정 또는 D의 진단만 가능
* **읽는다** → 어느 계층에서 읽는가? 그 계층이 media를 읽어도 되는가?
  `§4.1` Source Intake와 `§15` L-5(격리된 임시 workspace)가 관련 문언이다.

## Q4. 이미 released된 SRT 2편을 어떻게 하는가?

* 그대로 둔다 / 재생성한다 / 경고만 붙인다
* 재생성한다면 identity와 provenance는 어떻게 되는가?
  (`041` Final Selection, SRT Artifact, Materialization은 모두 identity를 가진다)

---

# 5. 반드시 지킬 제약

* **Raw Transcript는 provider가 출력한 결과 그대로 보존한다.** (`§2`, `§4.3`, `§14` A-11)
* Human Authority를 우회하는 자동 보정을 만들지 않는다.
* released 계약 문장을 삭제하거나 재작성하지 않는다. 필요하면 additive forward note.
* 근거 없는 숫자(보정량, 임계값, tolerance)를 발명하지 않는다.
* `§14` A-10의 released tolerance(ε = 1e-6, `PATCH-0039`)와 혼동하지 않는다.
  그것은 **표현 오차**에 대한 것이고, 이번 건은 **수십 초 규모의 의미 오차**다.
* schema 변경은 필요성이 입증된 경우에만.

---

# 6. 근거가 부족하면 확인을 요구하라

다음은 아직 확인되지 않았다. 결정에 필요하면 **추가 측정을 요구하는 것이 정답이다.**

* 2.3의 기제 추정이 맞는가? (decode window 앵커링)
* 밀림 크기가 무발화 길이와 비례하는가?
* 무발화 직후가 아닌 곳에서도 발생하는가? (라벨러는 아니라고 했으나 표본이 작다)
* 다른 model / 다른 configuration에서도 재현되는가?
* 3편 외 강의에서도 재현되는가?

**추측으로 결정을 채우지 마라.** 측정이 필요하면 무엇을 어떻게 측정할지 명시하라.

---

# 7. 하지 않을 것

* 구현
* PATCH 작성
* threshold / 보정량 확정
* Blueprint 수정
* schema 변경
* 기존 SRT 재생성
* 환각 탐지 규칙과 이번 건을 섞기 (별개 사안이다)

---

# 8. 출력 형식

## 1. Contract Investigation
읽은 문언과 그 문언이 이번 현상에 대해 실제로 말하는 것 / 말하지 않는 것.

## 2. Evidence Assessment
`131`의 근거가 결정을 내리기에 충분한지. 부족하면 무엇이 부족한지.

## 3. Problem Classification
Provider behaviour / Implementation defect / Blueprint gap / Product decision 중 무엇인지와 근거.

## 4. Layer Analysis
계층 A~D 각각에 대해: 무엇을 해결하는가 / 무엇을 깨뜨리는가 / 어떤 released 계약과 충돌하는가.

## 5. Audio Access Decision
Q3에 대한 답과 근거.

## 6. Decision
입장을 가지는가. 가진다면 어느 계층에서 어떤 성격의 계약인가.
**결정하지 않기로 하는 것도 유효한 결정이며, 그 경우 재개 조건을 명시한다.**

## 7. Released Artifact Impact
Q4에 대한 답.

## 8. Required Evidence Before PATCH
PATCH를 쓰기 전에 확보해야 할 측정.

## 9. Scope Boundary
이 결정이 **다루지 않는 것**을 명시. 특히 환각 탐지와의 경계.

## 10. Result

```text
Requires Architect Decision:
Requires Blueprint Clarification:
Requires Blueprint PATCH:
Requires additional measurement:
```

---

# 9. 성공 조건

이번 세션의 성공은 **문제를 해결하는 것이 아니다.**

성공 조건은:

> 이 현상이 LectureOS의 어느 책임 계층에 속하는지, 그리고 released 계약 중 무엇을
> 건드려야 하는지를 근거와 함께 확정하는 것.

"고칠 수 있다"가 아니라 **"어디서 고쳐야 하고, 그 대가가 무엇인가"**에 답하라.

근거가 부족하다는 결론도 유효하다. 그 경우 무엇을 더 측정해야 하는지 명시하라.
