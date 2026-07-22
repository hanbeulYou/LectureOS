# Storage Model

- Status: Approved
- Baseline: LectureOS Blueprint v1
- Baseline Commit: `b0251cf56628f012891e39eebe7f57c2be63c684`
- Implementation Baseline Commit: `4e82881b25be67fbef99e3572f131c4233bd4cc7`
- Last Updated: 2026-07-15
- Depends On: `000_IMPLEMENTATION_DESIGN_GUIDE.md`, `010_PROJECT_LIFECYCLE.md`, `../docs/020_PRODUCT_REQUIREMENTS.md`, `../docs/021_SYSTEM_CONTEXT.md`, `../docs/030_DATA_MODEL.md`, `../docs/031_ARCHITECTURE.md`, `../docs/040_TRANSCRIPT_PIPELINE.md`, `../docs/041_SUBTITLE_PIPELINE.md`, `../docs/042_LECTURE_INTELLIGENCE_PIPELINE.md`, `../docs/043_REVIEW_PIPELINE.md`, `../docs/044_EXPORT_PIPELINE.md`, `../docs/050_PLUGIN_SYSTEM.md`
- Referenced By:
- Requires Blueprint Clarification: Project와 Lecture의 Conceptual Identity 및 cardinality

## Purpose

이 문서는 LectureOS가 Core Blueprint와 Project Lifecycle의 계약을 지키기 위해 어떤 정보를 장기 기록으로 유지해야 하는지 구현 책임 수준에서 정의한다.

다음 질문에 답한다.

- 무엇을 지속해야 하며 그 이유는 무엇인가?
- 기록은 서로 어떤 identity, reference, revision과 lineage 관계를 가져야 하는가?
- 어떤 의미를 덮어쓰면 안 되는가?
- 어떤 결과는 재생성할 수 있고 어떤 근거는 반드시 보존해야 하는가?
- Processing Run과 지속되는 Domain Record의 경계는 어디인가?
- 재처리 이후에도 Human Decision과 provenance를 어떻게 보존하는가?
- archive, logical removal, physical deletion과 retention 책임은 어떻게 다른가?

이 문서는 특정 database, schema, 파일 형식 또는 기술 스택을 선택하지 않는다.

## 1. Blueprint and Implementation Basis

### 1.1 Confirmed by Blueprint

- Source Media와 Source Timeline은 시간 기반 결과의 최상위 근거다.
- Raw Transcript, Corrected Transcript와 Subtitle은 서로 다른 identity와 책임을 가진다.
- Candidate, Review Decision, Approved Result와 Artifact는 서로 다른 기록 책임을 가진다.
- Processing Run은 결과의 생성 문맥과 provenance를 설명하지만 Domain Result identity를 소유하지 않는다.
- revision은 이전 결과를 덮어쓰지 않고 계보를 유지한다.
- Human Decision과 Review History는 재처리로 자동 삭제되거나 변경되지 않는다.
- Artifact는 승인 결과에서 재생성할 수 있으며 중심 Domain Record가 아니다.
- 외부 provider, Plugin 또는 NLE identity는 LectureOS identity를 대신하지 않는다.
- 실패, uncertainty와 validation failure를 정상 결과로 숨기지 않는다.

### 1.2 Confirmed by Implementation Baseline

- Project Lifecycle State와 Processing State를 분리한다.
- Processing Run의 실행 문맥과 장기 Domain Record를 분리한다.
- 부분 성공을 하나의 성공·실패 값으로 축소하지 않는다.
- Review Readiness, Approval, Export Readiness와 Artifact Availability를 구분한다.
- Archive는 Delete가 아니다.
- Project와 Lecture는 canonical Domain Concept가 아니라 현재 lifecycle을 설명하기 위한 Working Model 역할이다.

### 1.3 Authority Boundary

Storage Model은 기록을 보존하는 구현 책임을 정의한다. 저장 형태가 Blueprint Concept의 의미를 만들거나 Pipeline 책임을 다시 정의하지 않는다.

저장 편의를 위해 새로운 Domain Concept가 필요해 보이면 이 문서에서 확정하지 않고 `Requires Blueprint Clarification` 또는 후속 Implementation Design으로 남긴다.

## 2. Scope

### 2.1 Included

- 지속 기록과 임시 실행 정보의 구분
- identity와 reference 책임
- immutable meaning과 revision 책임
- current, superseded, stale와 historical applicability
- lineage와 provenance
- Processing Run과 execution record
- Human Authority record
- Artifact record와 외부 물리 파일의 경계
- retry, reprocessing과 reconciliation 관계
- mutation 책임
- archive, deletion과 retention 경계
- 저장 실패와 consistency 책임
- 최소 security와 privacy 경계

### 2.2 Excluded

- database 종류와 물리 schema
- table, collection, column과 key 형식
- index, transaction과 migration 구현
- ORM과 serialization
- file format과 object storage vendor
- cache와 backup 기술
- API와 payload
- retention 기간과 개인정보 삭제 정책
- 코드와 package 구조

## 3. Storage Principles

### 3.1 Storage Is Not Domain Meaning

저장 형태는 Domain Concept의 의미나 identity를 결정하지 않는다. table, collection, file, object 또는 document 같은 물리적 표현을 Concept와 동일시하지 않는다.

### 3.2 Record Is Not Runtime Object

지속되는 Record는 특정 process의 메모리 객체, 실행 instance 또는 component 내부 상태와 동일하지 않다. 실행이 끝나도 유지해야 할 의미는 runtime 수명과 분리한다.

### 3.3 Processing Run Is Not Domain Record

Processing Run은 어떤 실행 책임이 어떤 입력과 조건에서 수행되었는지 설명하는 Execution Record다. Transcript, Subtitle, Analysis Finding, Review Decision, Approved Result 또는 Artifact의 identity를 소유하지 않는다.

### 3.4 Revision Is Not Overwrite

새 revision은 이전 revision을 조용히 덮어쓰지 않는다. 이전 표현, 변경 이유와 provenance가 필요할 때 구분하고 추적할 수 있어야 한다.

### 3.5 Current Is Not Only

현재 작업에서 우선 사용하는 결과가 있어도 과거 revision, Candidate, Review History와 Artifact provenance가 자동 삭제되는 것은 아니다.

### 3.6 Candidate Is Not Decision

Candidate와 Human Decision은 별도 identity와 persistence 책임을 가진다. Accept, Reject 또는 Modify가 Candidate 기록의 의미를 바꾸지 않는다.

### 3.7 Decision Is Not Artifact

Review Decision, Approved Edit Decision과 Export Artifact는 서로 다른 지속 기록이다. Decision을 Artifact 상태로 바꾸거나 Artifact 존재를 Decision으로 해석하지 않는다.

### 3.8 Artifact Is Reproducible but Not Authoritative

Artifact는 승인 결과와 Export Configuration에서 다시 만들 수 있는 파생 결과다. Human Decision, Final Subtitle 또는 Approved Edit Decision의 중심 기록이 아니다.

### 3.9 Archive Is Not Delete

Archive는 활성 작업 대상에서 제외하는 lifecycle 책임이다. 기록의 의미나 provenance를 물리적으로 제거하는 동작과 동일하지 않다.

### 3.10 Provenance Must Survive Reprocessing

재처리, provider 또는 Plugin 교체, Configuration 변경 이후에도 이전 결과와 Human Decision이 어떤 문맥에서 생성되었는지 설명할 수 있어야 한다.

## 4. Record Classification

| Classification | Meaning | Examples |
| --- | --- | --- |
| Source Authority Record | 파생 결과가 돌아가야 하는 최상위 원본 근거를 보존한다. | Source Media reference, Source Timeline |
| Preserved Original Result | 후속 correction이나 normalization으로 덮어쓰면 안 되는 최초 결과를 보존한다. | Raw Transcript, provider-specific original result |
| Derived Domain Record | Source 또는 upstream 결과에서 파생된 지속 기록이다. | Corrected Transcript revision, Subtitle revision, Analysis Finding, Edit Candidate |
| Human Authority Record | 사람의 판단, 변경과 승인 계보를 보존한다. | Review Decision, Decision Modification, Approved Edit Decision |
| Execution Record | 처리 실행, validation, failure와 recovery 문맥을 보존한다. | Processing Run, Processing State, Validation Result, Failure, Diagnostic |
| Artifact Record | 외부 표현의 identity, availability와 provenance를 보존한다. | Export Activity, Export Artifact record, external consumer result |
| Ephemeral Execution Data | 실행 중에는 필요하지만 장기 보존이 항상 필요한 것은 아니다. | 일시적 진행 신호, 임시 자원 위치, 중간 전달 상태 |

Classification은 database table 종류가 아니다. 하나의 기록이 여러 책임 관점을 가질 수 있다.

Source Media reference와 Source Timeline만 Source Authority Record 책임을 가진다. Raw Transcript와 provider-specific original result는 변경 전 결과를 보존하지만 Source Authority는 아닌 Preserved Original Result다. Final Subtitle은 Derived Domain Record이면서 Artifact 생성에 사용하는 Approved Result다. 이 차이는 하나의 물리 저장 형태를 강제하지 않는다.

## 5. Persistent Record Responsibilities

### 5.1 Identity Records

다음 대상은 재처리와 실행 수명을 넘어 다른 기록과 구분하고 참조할 수 있는 identity가 필요하다.

| Identity Responsibility | Required Meaning |
| --- | --- |
| 상위 작업 문맥 참조 | Source, 결과, Review와 Artifact를 같은 작업 목적으로 연결한다. Project canonical identity를 확정하지 않는다. |
| Lecture 역할 참조 | 같은 강의 내용으로 이해되는 결과를 연결하는 Working Model reference다. |
| Source Media identity | 외부 파일의 위치와 분리된 원본 참조 identity를 제공한다. |
| Source Timeline identity | 시간 기반 결과가 공유하는 원본 시간 기준을 구분한다. |
| Pipeline Result identity | 각 결과와 revision을 Processing Run과 독립적으로 참조한다. |
| Review Item identity | Review 대상과 Review Context를 결정 이력에 연결한다. |
| Review Decision identity | 개별 Human Decision과 provenance를 구분한다. |
| Approved Edit Decision identity | 승인된 편집 의도와 Candidate·Decision 계보를 구분한다. |
| Export Artifact identity | Artifact record를 Approved Result와 별도로 구분한다. |
| Plugin identity reference | Plugin Provenance를 내부 Domain identity와 분리한다. |
| Capability Contract reference | 결과가 어떤 Capability 의미에 따라 생성되었는지 연결한다. |

Project와 Lecture 관련 identity는 Working Model Identity 또는 Implementation Record Responsibility로만 다룬다. canonical identity와 cardinality는 Requires Blueprint Clarification이다.

### 5.2 Preserved Original Records

`Preserved`는 물리 저장 장치에서 절대 수정할 수 없다는 뜻이 아니다. 기존 의미를 변경한 새 값으로 조용히 덮어쓰지 않는 책임을 뜻한다. Source Media reference와 Source Timeline은 최상위 원본 근거이며, Raw Transcript와 provider-specific original result는 그 원본에서 파생된 보존 대상 최초 결과다.

| Record Responsibility | Preservation Rule |
| --- | --- |
| Source Media reference | 원본 파일 참조와 identity의 역사적 의미를 보존한다. 파일 이동이나 부재는 별도 availability로 다룬다. |
| Source Timeline | 시간 기준을 파생 결과에 맞춰 변경하지 않는다. |
| Raw Transcript | Corrected Transcript나 사용자 수정으로 덮어쓰지 않는다. |
| Provider-specific original result | normalization 이후에도 가능한 범위에서 원래 provider 결과와 출처를 설명할 수 있게 한다. |
| Original Candidate | Accept, Reject, Modify 이후에도 당시 제안과 근거를 보존한다. |
| Original Review Decision | 후속 결정이 생겨도 당시 판단의 내용과 근거를 다시 쓰지 않는다. |
| Creation provenance | 생성 당시 Source, Run, Configuration, Plugin과 Capability 관계를 사후 문맥에 맞춰 바꾸지 않는다. |

오류 정정이 필요하면 기존 기록의 의미를 수정하는 대신 correction, revision, supersession 또는 diagnostic 관계를 추가한다.

### 5.3 Revisable Domain Records

Revisable Domain Record는 목적이 같은 새로운 표현이 생성될 수 있는 지속 기록이다.

| Record | New Revision Trigger | Previous Relationship | Human Decision Relationship |
| --- | --- | --- | --- |
| Corrected Transcript | correction 결과, 사용자 Modification 또는 upstream 변경 | Raw Transcript와 이전 revision 계보를 유지 | 적용된 Review Decision과 Modification을 연결 |
| Subtitle Candidate / Revision | Transcript, reading rule, time representation 또는 사용자 변경 | 이전 Candidate와 revision 관계를 유지 | Accept, Reject, Modify 대상과 결과를 분리 |
| Final Subtitle | 적용 가능한 Review Decision이나 Subtitle revision 변경 | 이전 Final Subtitle의 historical 의미를 유지 | 어떤 결정에서 승인 상태가 되었는지 연결 |
| Lecture Segment | 분석 Context, provider 또는 segmentation 관점 변경 | 이전 분석 결과와 Run provenance를 구분 | Segment 자체는 Decision이 아님 |
| Analysis Finding | Source evidence, 분석 기준 또는 Capability 변경 | 이전 Finding과 현재 applicability를 구분 | Review Decision이 Finding을 덮어쓰지 않음 |
| Edit Candidate | Finding, 추천 의도 또는 upstream 변경 | original Candidate와 stale·superseded 관계를 유지 | Candidate와 Decision identity를 분리 |
| Export Configuration | export 목적, Profile 또는 Scope 변경 | 이전 Configuration을 사용한 Artifact provenance를 유지 | Approved Result 의미를 변경하지 않음 |
| Export Artifact | Export Input이나 Configuration 변경 또는 재생성 | 이전 Artifact record와 생성 문맥을 구분 | Decision과 Approved Result를 수정하지 않음 |

새 revision이 현재 사용 가능한지는 별도 applicability 책임으로 구분한다. 새 revision 생성만으로 이전 결과가 삭제되거나 새 결과가 자동 승인되지 않는다.

### 5.4 Human Authority Records

Human Authority Record는 provider 결과보다 높은 작업 권위를 가지며 재처리로 자동 변경되지 않는다.

지속해야 할 기록은 다음과 같다.

- Review Decision
- Accept, Reject, Modify의 판단 의미
- Decision Modification과 사용자가 선택한 변경 결과 또는 의도
- Approved Edit Decision
- Decision Provenance
- Review History와 supersession 관계
- original Candidate와 Review Item 관계
- Candidate Reconciliation, Review Conflict와 stale 관계

각 Human Decision은 최소한 다음을 설명할 수 있어야 한다.

- 무엇을 판단했는가?
- 어떤 Candidate 또는 Review Item을 근거로 했는가?
- 어떤 Review Context와 Source reference를 확인할 수 있었는가?
- Accept, Reject, Modify 중 어떤 판단이었는가?
- Modify라면 원래 제안과 승인된 변경은 어떻게 다른가?
- 후속 결정이 현재 사용 책임을 대신했는가?
- 재처리 후 새 Candidate와 어떤 reconciliation 관계를 가지는가?

Human Decision 저장에 실패하면 시스템이 승인된 것으로 추정해서는 안 된다.

### 5.5 Execution Records

Execution Record는 결과가 어떻게 만들어졌고 실패 또는 복구가 어떻게 이어졌는지 설명한다.

| Execution Responsibility | Persistent Meaning |
| --- | --- |
| Processing Run | 특정 입력과 조건에서 수행된 실행 책임의 문맥 |
| Input reference | Run이 사용한 Source와 upstream result 참조 |
| Configuration reference | 실행 당시 적용한 처리 조건과 설정 참조 |
| Capability reference | 실행이 요구한 Capability Contract |
| Plugin/provider provenance | 사용한 Plugin identity와 외부 provider 출처 |
| Processing State | Run 또는 처리 책임의 진행과 결과 상태 |
| Validation Result | 구조적 조건과 traceability 검증 결과 |
| Failure | 정상 결과를 만들지 못한 범위와 영향 |
| Diagnostic | 실패, 누락과 uncertainty를 설명하는 조사 문맥 |
| Retry relationship | 같은 처리 의도의 이전 실패와 새 시도 관계 |
| Reprocessing relationship | 변경된 입력 또는 조건과 새 결과 계보의 관계 |

Processing Run은 실행 책임을 설명하지만 생성한 Domain Result를 소유하지 않는다. 하나의 Run이 끝나도 그 결과, Review Decision과 Artifact의 lifecycle은 계속될 수 있다.

모든 실행 중 정보가 장기 기록일 필요는 없다. 재현, recovery, provenance와 실패 설명에 필요한 범위를 후속 Execution Model에서 구체화한다.

### 5.6 Artifact Records

Artifact Record는 외부 표현의 생성과 추적을 담당하며 물리 파일 자체와 구분된다.

| Artifact Responsibility | Persistent Meaning |
| --- | --- |
| Export Activity | 어떤 승인 입력과 export 문맥으로 생성 작업을 수행했는지 설명 |
| Export Input reference | Final Subtitle 또는 Approved Edit Decision 참조 |
| Export Configuration | export에 적용한 선택과 조건 |
| Export Profile | 외부 사용 목적과 표현 책임 |
| Export Scope | 포함한 승인 결과의 범위 |
| Artifact provenance | Input, Configuration, Profile, Scope와 Run 관계 |
| Artifact availability | 물리 표현이 현재 존재하고 접근 가능한지 설명 |
| External consumer result | LectureOS export와 외부 consumer 처리 결과를 구분 |

Artifact identity는 Approved Result identity와 다르다. 물리 파일의 경로나 URL은 Artifact identity의 유일한 근거가 될 수 없다.

Artifact 파일이 사라져도 Artifact provenance, Approved Result와 Human Decision은 유지할 수 있어야 한다. 동일한 승인 입력과 Configuration에서 다시 생성한 Artifact는 새 생성 문맥을 설명할 수 있어야 한다.

### 5.7 Ephemeral Execution Data

다음 정보는 실행 중 필요할 수 있지만 장기 보존이 항상 필수는 아니다.

- 일시적 진행 신호
- 복구에 사용하지 않는 임시 작업 위치
- 재생성할 수 있고 provenance에 필요하지 않은 중간 전달 표현
- process 내부 coordination 정보
- 장기 Diagnostic으로 승격되지 않은 일시적 측정값

임시 정보라도 실패 복구, provenance 또는 Human Decision 설명에 필요해지면 Execution Record 책임으로 승격할 수 있어야 한다. 구체적인 승격 기준은 Requires Validation이다.

## 6. Identity and Reference Model

### 6.1 Identity Rules

- 각 지속 기록은 다른 기록과 구분 가능한 LectureOS identity를 가져야 한다.
- 외부 provider, Plugin 또는 NLE identity가 LectureOS identity를 대신하지 않는다.
- 파일 경로, URL 또는 외부 object key가 Source Media나 Artifact의 유일한 identity가 되어서는 안 된다.
- Processing Run identity가 생성된 Domain Result identity를 대신하지 않는다.
- revision은 원래 Concept와 새 revision의 관계를 설명할 수 있어야 한다.
- Artifact identity는 Approved Result와 Export Activity identity와 구분된다.
- 외부 식별자는 provenance 일부로만 사용한다.

구체적인 key 형식과 생성 방식은 정의하지 않는다.

### 6.2 Reference Rules

Reference는 다음 의미를 설명할 수 있어야 한다.

- identity가 같은 대상을 가리키는가?
- 원본, upstream, revision, decision 또는 artifact 관계 중 무엇인가?
- 참조 대상이 current, stale, superseded 또는 historical한가?
- 외부 object가 없어도 내부 기록 관계를 유지할 수 있는가?

Reference를 물리적인 foreign key, pointer 또는 URL과 동일시하지 않는다.

### 6.3 Working Model Identity

Project와 Lecture 관련 저장 책임은 다음과 같이 제한한다.

- 상위 작업 문맥을 연결할 구현 reference가 필요하다.
- 같은 강의 의미를 연결할 Working Model reference가 필요할 수 있다.
- 이 reference가 별도 canonical Domain Entity인지 확정하지 않는다.
- Project Context와 lifecycle identity가 같은 Concept인지 결정하지 않는다.
- cardinality와 재사용 관계를 storage convenience로 확정하지 않는다.

## 7. Revision and Applicability

### 7.1 Revision Relationship

Revision은 같은 목적의 표현이 변경되었을 때 이전 기록과 새 기록의 계보를 유지한다.

Revision은 최소한 다음을 설명할 수 있어야 한다.

- 어떤 기록에서 발전했는가?
- 무엇이 변경되었는가?
- 어떤 Source, Run, Configuration 또는 Human Decision이 변경을 만들었는가?
- 이전 기록을 현재 작업에서 계속 사용할 수 있는가?

고정 revision 번호 형식은 정의하지 않는다.

### 7.2 Current

Current는 현재 작업에서 우선적으로 사용하는 결과다. 유일하거나 영구적이라는 뜻이 아니며 historical record를 삭제하는 상태가 아니다.

어떤 책임이 current applicability를 결정하는지는 Record 종류에 따라 다를 수 있다. Human Approval이 필요한 결과를 자동 처리만으로 current approval 상태로 만들 수 없다.

### 7.3 Superseded

Superseded는 후속 결과가 현재 사용 책임을 대신하지만 이전 기록의 역사적 의미와 provenance는 유지되는 상태다.

후속 revision이 존재한다는 사실만으로 자동 supersession을 확정하지 않는다. 사용자 결정 또는 Pipeline 계약이 필요한 경우 그 근거를 연결한다.

### 7.4 Stale

Stale은 upstream 변경이나 재처리로 현재 문맥에 그대로 적용 가능한지 보장할 수 없는 상태다.

Stale은 invalid, rejected 또는 deleted와 동일하지 않다. Candidate, Review Decision, Approved Result와 Artifact 각각의 stale 의미를 구분해야 한다.

### 7.5 Historical

Historical은 과거 처리, Review, approval 또는 export 문맥을 설명하기 위해 유지되는 기록이다.

Current, Superseded, Stale과 Historical을 하나의 전역 상태로 구현하도록 강제하지 않는다. 하나의 기록에 여러 applicability 관점이 동시에 필요할 수 있다.

## 8. Lineage and Provenance

```text
Source Media
    |
    v
Provider-specific Result
    |
    v
Raw or Candidate Result
    |
    v
Corrected / Revised / Validated Result
    |
    v
Review Item
    |
    v
Review Decision
    |
    v
Approved Result
    |
    v
Export Artifact
```

이 흐름은 대표 lineage다. 모든 결과가 전체 단계를 거치지는 않는다. Failure, Diagnostic, Lecture Segment 또는 Analysis Finding처럼 별도 가지에서 생성되어 Review나 결과에 연결되는 기록도 있다.

각 지속 기록은 적용 가능한 범위에서 다음을 설명할 수 있어야 한다.

- 어떤 Source에서 왔는가?
- 어떤 upstream record를 사용했는가?
- 어떤 Processing Run에서 생성되었는가?
- 어떤 Plugin, provider, Capability와 Configuration이 사용되었는가?
- 어떤 revision 또는 이전 결과와 관계되는가?
- 어떤 Validation Result, Failure와 Diagnostic이 연결되는가?
- 어떤 Human Decision이 적용되었는가?
- 어떤 Approved Result와 Artifact가 파생되었는가?

Provenance는 단순한 생성 시각이나 작성자 문자열이 아니다. 결과의 생성 근거와 책임 관계를 재구성할 수 있는 연결이다.

## 9. Processing Run Records

### 9.1 Run Responsibility

Processing Run Record는 실행 책임을 설명하기 위해 지속된다.

- 실행 당시 입력과 upstream reference
- 처리 Configuration과 Capability Context
- Plugin 및 provider provenance
- 수행한 Pipeline 책임
- 생성된 Domain Result reference
- Validation Result, Failure와 Diagnostic
- retry 또는 reprocessing 관계

### 9.2 Run and Result Separation

- 하나의 Processing Run이 여러 Domain Result를 생성할 수 있는 가능성을 열어둔다.
- 하나의 Domain Result가 여러 upstream Run의 결과를 사용할 수 있는 가능성을 열어둔다.
- Run 삭제나 종료로 Domain Result를 함께 삭제하지 않는다.
- Domain Result의 current 또는 approval 상태를 Run 성공 여부만으로 결정하지 않는다.
- 같은 Run에서 생성된 결과라도 각 결과의 identity와 validation을 구분한다.

구체적인 cardinality는 Requires Validation이다.

### 9.3 Processing State

Processing State는 실행의 진행과 결과를 설명한다. 부분 성공, 실패와 recovery 가능성을 나타낼 수 있지만 Domain Result의 의미나 Human Approval을 대신하지 않는다.

진행 신호 전체를 영구 보존할 필요는 없지만 최종 상태, 실패 영향과 recovery 관계를 설명하는 데 필요한 기록은 유지해야 한다.

## 10. Human Authority Records

### 10.1 Decision Preservation

Review Decision은 original Candidate, Review Item, Review Context와 Decision Provenance를 연결한다. 후속 처리나 provider 교체가 기존 Decision 내용을 다시 쓰지 않는다.

### 10.2 Accept and Reject

- Accept는 Candidate의 제안이나 의도를 수용했다는 별도 Decision이다.
- Reject는 Candidate를 승인하지 않았다는 Decision이며 Candidate 존재를 삭제하지 않는다.
- 유사한 새 Candidate가 생겨도 이전 Accept나 Reject를 자동 적용하지 않는다.

### 10.3 Modify

Modify는 원래 Candidate를 덮어쓰지 않는다. Original Candidate, 사용자 변경, 변경된 결과 또는 최종 의도와 Review Decision의 관계를 보존한다.

### 10.4 Review History

최신 Decision만 남기지 않는다. 후속 Decision이 이전 Decision의 현재 적용 책임을 대신할 수 있지만 과거 판단과 근거는 historical record로 유지한다.

### 10.5 Reconciliation

새 Candidate와 기존 Decision의 적용 관계가 불명확하면 다음 관계를 보존할 수 있어야 한다.

- stale Candidate
- stale 또는 재검토가 필요한 Decision
- Review Conflict
- Candidate Reconciliation 필요성
- 후속 Review Decision과 이전 Decision 관계

구체적인 reconciliation algorithm과 자동 연결 기준은 정의하지 않는다.

## 11. Artifact Records

### 11.1 Artifact Record and Physical Object

Artifact Record는 Artifact의 identity, provenance, availability와 Approved Result 관계를 설명한다. 물리 파일은 그 표현이 실제로 저장된 외부 또는 내부 object다.

둘은 다음과 같이 구분한다.

- Artifact Record가 있어도 물리 파일은 손실되거나 접근 불가능할 수 있다.
- 물리 파일이 있어도 provenance가 없으면 완전한 LectureOS Artifact로 취급할 수 없다.
- 파일 경로나 URL 변경이 Artifact identity 변경을 자동으로 의미하지 않는다.
- 재생성된 물리 표현은 새 Materialization Record(새 identity)로 확정되었다 (`044_EXPORT_PIPELINE.md §17`, `patches/PATCH-0007`).

### 11.2 Artifact Availability

Artifact availability는 물리 표현의 존재, 접근 가능성, 완전성과 외부 consumer 상태를 구분해 설명해야 한다.

외부 consumer 처리 성공이나 실패를 LectureOS의 Export Validation 또는 Approval 상태와 합치지 않는다. v1에서 외부 consumer로의 delivery/transport는 LectureOS 소유 능력이 아니며, LectureOS Export Pipeline은 Physical Materialization에서 끝난다(`044_EXPORT_PIPELINE.md §18`, `patches/PATCH-0008`).

### 11.3 Reproducibility

Artifact를 재생성하려면 최소한 다음을 보존해야 한다.

- Final Subtitle 또는 Approved Edit Decision reference
- Export Configuration
- Export Profile과 Scope
- Artifact Provenance
- 재생성에 영향을 주는 Capability와 Plugin reference

Artifact 파일 자체만 보존하고 생성 근거를 잃는 저장 모델을 사용하지 않는다.

## 12. Retry and Reprocessing

### 12.1 Retry

Retry는 동일한 처리 의도와 입력 문맥에서 실패한 실행을 다시 시도한다.

- 새 Processing Run이 필요할 수 있다.
- 이전 실패와 새 Run 관계를 보존한다.
- 새로운 Domain revision이 반드시 생성되는 것은 아니다.
- 성공한 retry가 이전 Failure record를 삭제하지 않는다.

### 12.2 Reprocessing

Reprocessing은 입력, Configuration, Capability, provider, validation 기준 또는 upstream result 변화로 새 결과 계보를 만든다.

다음을 보장해야 한다.

- 이전 Processing Run 유지
- 이전 Domain Result 유지
- 새 결과 identity와 provenance 분리
- 기존 Human Decision 자동 적용 금지
- stale, Review Conflict 또는 reconciliation 관계 기록
- 영향받지 않은 결과의 재사용 가능성
- 기존 Artifact와 새 Approved Result의 관계 구분

### 12.3 Retry and Reprocessing Boundary

같은 실행 의도를 반복하는지, 변경된 문맥에서 새 결과를 만드는지 구분해야 한다. 구체적인 판별 기준은 후속 Execution and Reprocessing Design에서 정한다.

## 13. Mutation Rules

Storage responsibility에서 mutation은 다음 의미 유형으로 구분한다.

| Mutation Type | Meaning |
| --- | --- |
| Append new record | 기존 기록을 바꾸지 않고 새 결과나 사건을 추가한다. |
| Create revision | 같은 목적의 새 표현과 이전 revision 관계를 만든다. |
| Mark current applicability | 현재 작업에서 우선 사용하는 결과를 표시한다. |
| Mark stale | 현재 문맥에 그대로 적용 가능한지 불확실함을 표시한다. |
| Supersede | 후속 결과가 현재 사용 책임을 대신함을 표시한다. |
| Archive | 활성 작업 대상에서 제외하면서 계보를 유지한다. |
| Mark for deletion review | 후속 Security, Privacy and Retention Design에서 physical deletion 가능성을 검토할 대상을 표시하며 즉시 삭제하지 않는다. Candidate Domain Concept, Reject, stale, superseded 또는 archive를 뜻하지 않는다. |
| Retain for provenance | 현재 사용하지 않아도 생성 문맥 설명을 위해 보존한다. |

이 유형은 database operation이나 상태 enum이 아니다.

### 13.1 Required Mutation Constraints

- Raw Transcript를 Corrected Transcript로 덮어쓰지 않는다.
- Candidate를 Decision으로 변환해 같은 기록의 의미를 바꾸지 않는다.
- Reject가 Candidate 존재를 삭제하지 않는다.
- Modify가 original Candidate를 덮어쓰지 않는다.
- Approved Edit Decision을 Artifact 상태로 변경하지 않는다.
- Artifact 재생성이 기존 Decision을 수정하지 않는다.
- provider 또는 Plugin 교체가 과거 provenance를 덮어쓰지 않는다.
- current marker 변경이 historical record 삭제를 의미하지 않는다.

## 14. Archive, Deletion, and Retention

### 14.1 Archive

Archive는 Working Model의 상위 작업 문맥을 활성 처리, Review 또는 export 대상에서 제외하되 Domain Record와 provenance를 유지하는 lifecycle 책임이다.

Archive 복구 가능성과 archive 상태에서 허용할 작업은 Requires Validation이다.

### 14.2 Logical Removal

Logical Removal은 현재 사용 또는 노출 대상에서 기록을 제외하되 audit, recovery와 provenance를 위해 유지할 수 있는 책임이다.

Logical Removal은 Reject, Stale, Superseded 또는 Archive와 자동으로 같은 의미가 아니다.

### 14.3 Physical Deletion

Physical Deletion은 저장된 정보 자체를 제거한다. Human Decision, provenance, Source Timeline traceability와 충돌할 수 있으므로 별도 Security, Privacy and Retention Design이 필요하다.

`Mark for deletion review`는 Physical Deletion을 실행하지 않는다. 삭제 가능성에 대한 후속 검토 표시일 뿐 Candidate Domain Concept나 다른 applicability 및 lifecycle 의미를 변경하지 않는다.

### 14.4 Deferred Retention Decisions

이번 문서에서는 다음 정책과 기간을 확정하지 않는다.

- 사용자의 삭제 요청 처리
- 개인정보 삭제 의무
- 외부 Source 파일 삭제와 내부 reference 처리
- Artifact retention
- provider original result retention
- archive 복구 가능성
- Diagnostic과 Execution Record retention

## 15. Failure and Consistency

### 15.1 Persistence Failures

| Failure | Required Response |
| --- | --- |
| Identity creation failure | 구분할 수 없는 기록을 정상 Domain Record로 사용하지 않는다. |
| Provenance link failure | 생성 근거를 잃은 결과를 완전한 결과로 표시하지 않는다. |
| Partial record persistence | 저장된 범위와 누락된 범위를 구분하고 독립 결과를 근거 없이 폐기하지 않는다. |
| Revision relationship failure | 새 결과를 기존 revision의 정상 후속으로 표시하지 않는다. |
| Human Decision persistence failure | 승인되었다고 추정하거나 downstream approval로 전달하지 않는다. |
| Artifact provenance failure | 물리 파일이 있어도 완전한 Artifact 성공으로 취급하지 않는다. |
| Stale/reconciliation relationship failure | 기존 Decision을 새 Candidate에 안전하게 적용할 수 있다고 간주하지 않는다. |
| External object availability mismatch | 외부 파일 존재와 내부 record 상태 차이를 드러낸다. |

### 15.2 Consistency Rules

- 일부 저장 실패가 완료된 다른 Domain Record를 근거 없이 무효화하지 않는다.
- Human Decision이 저장되지 않았다면 승인된 것으로 추정하지 않는다.
- Artifact 파일이 존재해도 Artifact Provenance가 없으면 완전한 성공으로 취급하지 않는다.
- 외부 파일이 사라져도 내부 Decision History를 함께 삭제하지 않는다.
- 저장 복구가 이전 기록을 덮어쓰는 방식이 되어서는 안 된다.
- partial persistence를 전체 성공이나 전체 실패로 단순화하지 않는다.

구체적인 transaction, atomicity와 recovery 구현은 이 문서에서 정의하지 않는다. Final Subtitle SRT Artifact의 Physical Materialization DB↔filesystem consistency 계약은 record-first, `PENDING → MATERIALIZED | FAILED` lifecycle로 `044_EXPORT_PIPELINE.md §17`(`patches/PATCH-0007`)에서 확정되었다.

## 16. Persistence Boundaries

### 16.1 Domain Persistence

LectureOS Concept의 identity, lineage, revision, Human Decision과 Approved Result를 보존한다.

### 16.2 Execution Persistence

Processing Run, Processing State, Validation Result, Failure, Diagnostic과 recovery 문맥을 보존한다.

### 16.3 Artifact Persistence

Artifact identity, metadata, availability와 provenance를 보존한다. 물리 Artifact 표현과 record를 분리한다.

### 16.4 External Object Storage Boundary

Source Media 또는 Artifact의 물리 파일은 LectureOS가 직접 소유하지 않는 저장 경계에 존재할 수 있다.

- 외부 object 존재와 내부 Domain Record 존재를 구분한다.
- 외부 위치 변경과 Domain identity 변경을 동일시하지 않는다.
- 외부 object 손실이 Human Decision과 provenance 삭제를 유발하지 않는다.
- 접근 정보와 Domain identity를 분리한다.

특정 filesystem 또는 object storage를 이 문서에서 선택하지 않는다. Final Subtitle SRT Artifact의 approved local Storage Root와 materialization 정책은 `044_EXPORT_PIPELINE.md §17`(`patches/PATCH-0007`)에서 확정되었으며, external object storage 경계는 별도 계약으로 유보한다.

## 17. Security and Privacy Boundary

이 문서는 저장 lifecycle과 관련된 최소 경계만 정의한다.

- Source Media와 Transcript에는 개인정보가 포함될 수 있다.
- Plugin 또는 provider original result에도 민감한 데이터가 존재할 수 있다.
- Human Decision과 Review History는 권위 있는 작업 기록이다.
- 외부 파일 위치와 접근 정보는 Domain identity와 구분해야 한다.
- Archive, Logical Removal과 Physical Deletion은 서로 다른 책임이다.

구체적인 encryption, access control, retention 기간, 개인정보 삭제 정책은 후속 Security and Retention Design으로 넘긴다. 새로운 보안 정책을 이 문서에서 확정하지 않는다.

## 18. Blueprint Boundary Check

Storage Model은 다음 책임을 보존하기 위한 기록 책임을 구체화하며 원래 의미를 다시 정의하지 않는다.

| Source Document | Preserved Responsibility |
| --- | --- |
| `030_DATA_MODEL.md` | Conceptual Identity, lineage, revision과 provenance |
| `031_ARCHITECTURE.md` | 논리적 처리 책임과 persistence 이전의 component 경계 |
| `040_TRANSCRIPT_PIPELINE.md` | Raw Transcript와 Corrected Transcript |
| `041_SUBTITLE_PIPELINE.md` | Subtitle revision과 Final Subtitle |
| `042_LECTURE_INTELLIGENCE_PIPELINE.md` | Lecture Segment, Analysis Finding과 Edit Candidate |
| `043_REVIEW_PIPELINE.md` | Human Decision, Review History와 reconciliation |
| `044_EXPORT_PIPELINE.md` | Export Activity, Artifact와 Export Provenance |
| `050_PLUGIN_SYSTEM.md` | Plugin Provenance, Capability Contract와 provider boundary |
| `010_PROJECT_LIFECYCLE.md` | Working Model lifecycle, Processing Run, partial progress와 archive |

### Requires Blueprint Clarification

다음 사항은 그대로 유지한다.

- Project와 Lecture는 별도 canonical Domain Concept인가?
- Project Context와 Project lifecycle identity는 같은 Concept인가?
- Project와 Lecture의 cardinality는 무엇인가?
- Lecture와 Source Media의 cardinality는 무엇인가?

Project와 Lecture 관련 저장 책임은 Working Model reference로만 표현한다.

## 19. Assumptions and Open Questions

### 19.1 Implementation Decisions

- Processing Run은 지속되는 Execution Record다.
- Domain Result는 Processing Run과 별도 identity를 가진다.
- Raw 결과와 수정 결과는 별도 record responsibility를 가진다.
- revision은 이전 기록을 덮어쓰지 않는다.
- Human Decision은 Candidate와 별도 record다.
- Artifact Record와 Artifact 물리 파일은 별도 책임이다.
- current, superseded, stale와 historical 의미를 구분한다.
- archive와 physical deletion을 분리한다.
- provenance는 각 결과에서 upstream과 실행 문맥까지 추적 가능해야 한다.
- persistence failure는 영향 범위와 partial success를 드러내야 한다.

### 19.2 Working Assumptions

- 상위 작업 문맥과 Lecture 역할을 연결할 implementation reference가 필요하다.
- 하나의 Processing Run은 여러 Pipeline Result reference를 가질 수 있다.
- 하나의 Artifact Record는 하나 이상의 물리 표현 availability를 설명할 가능성이 있다.
- current applicability는 Record 종류에 따라 서로 다른 책임이 결정할 수 있다.

### 19.3 Requires Validation

- 하나의 Processing Run이 여러 Pipeline Result를 만들 수 있는가?
- 하나의 Domain Result가 여러 Processing Run의 입력 또는 결과 관계를 가질 수 있는가?
- 현재 사용되는 revision을 누가 결정하는가?
- Final Subtitle의 승인 상태와 current revision 관계를 어떻게 구분하는가?
- stale Candidate와 기존 Review Decision을 어떤 record relationship으로 연결해야 하는가?
- (해결됨) Artifact 물리 파일이 손실되어도 Artifact Record와 Materialization Record는 유지된다 — `044_EXPORT_PIPELINE.md §17.10`, `patches/PATCH-0007`.
- (해결됨) 재생성된 Artifact 실현은 새 Materialization Record(새 identity)이며 Artifact identity는 유지된다 — `044_EXPORT_PIPELINE.md §17.11`, `patches/PATCH-0007`.
- provider original result는 어느 범위까지 장기 보존해야 하는가?
- Diagnostic은 장기 provenance인가, 운영 정보인가?
- 임시 실행 정보를 지속 Execution Record로 승격하는 기준은 무엇인가?
- Project와 Lecture clarification 전까지 저장 책임을 어떤 상위 reference로 묶는가?
- physical deletion이 provenance invariant와 충돌할 때 우선 책임은 무엇인가?

### 19.4 Requires Blueprint Clarification

- Project와 Lecture의 Conceptual Identity
- Project Context와 lifecycle identity의 관계
- Project, Lecture와 Source Media cardinality

### 19.5 Deferred

- 물리 storage schema (Physical Materialization의 storage 정책과 consistency 모델은 `044_EXPORT_PIPELINE.md §17`/`patches/PATCH-0007`에서 확정되었으며, 구체적 schema는 구현 milestone에서 정한다)
- transaction과 consistency의 구체적 구현 (consistency 모델 자체는 `044_EXPORT_PIPELINE.md §17`에서 확정)
- concrete ID와 revision 형식
- retention 기간과 deletion workflow
- backup, restore와 disaster recovery 기술
- API와 serialization
- encryption과 access control 구현

## 20. Validation Criteria

- 저장 형태가 Domain Concept의 의미나 identity를 결정하지 않는다.
- Project와 Lecture를 canonical Domain Entity로 승격하지 않는다.
- 각 지속 기록은 Processing Run과 독립적인 identity를 가질 수 있다.
- Source Media reference와 Source Timeline만 Source Authority로 분류한다.
- Raw Transcript와 provider-specific original result를 Preserved Original Result로 구분하고 그 의미를 덮어쓰지 않는다.
- deletion review 표시를 Candidate Domain Concept 및 즉시 Physical Deletion과 구분한다.
- revision, current, superseded, stale와 historical을 구분한다.
- Candidate, Review Decision, Approved Result와 Artifact를 별도 record responsibility로 유지한다.
- Human Decision과 Decision Provenance가 재처리 후에도 보존된다.
- Artifact Record와 물리 파일을 구분한다.
- Retry와 Reprocessing을 구분한다.
- Archive, Logical Removal과 Physical Deletion을 구분한다.
- persistence failure와 partial success를 숨기지 않는다.
- 특정 database, schema, storage vendor 또는 기술 스택을 선택하지 않는다.
- Blueprint와 Project Lifecycle의 책임을 다시 정의하지 않는다.

## Non-Goals

이 문서는 다음을 정의하지 않는다.

- database 종류
- table, collection과 column
- key와 ID 형식
- index와 transaction 구현
- ORM과 migration
- file format과 serialization
- object storage vendor
- cache와 backup 기술
- API와 payload
- 코드와 package 구조
- retention 기간
- 구체적인 개인정보 삭제 정책

## Related Documents

- [Implementation Design Guide](./000_IMPLEMENTATION_DESIGN_GUIDE.md)
- [Project Lifecycle](./010_PROJECT_LIFECYCLE.md)
- [Blueprint v1 Release](../docs/090_BLUEPRINT_RELEASE.md)
- [Product Requirements](../docs/020_PRODUCT_REQUIREMENTS.md)
- [System Context](../docs/021_SYSTEM_CONTEXT.md)
- [Conceptual Data Model](../docs/030_DATA_MODEL.md)
- [Logical Architecture](../docs/031_ARCHITECTURE.md)
- [Transcript Pipeline](../docs/040_TRANSCRIPT_PIPELINE.md)
- [Subtitle Pipeline](../docs/041_SUBTITLE_PIPELINE.md)
- [Lecture Intelligence Pipeline](../docs/042_LECTURE_INTELLIGENCE_PIPELINE.md)
- [Review Pipeline](../docs/043_REVIEW_PIPELINE.md)
- [Export Pipeline](../docs/044_EXPORT_PIPELINE.md)
- [Plugin System](../docs/050_PLUGIN_SYSTEM.md)
