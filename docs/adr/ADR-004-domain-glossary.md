# ADR-004: Domain Glossary 구현 방식 선택

**상태**: Accepted  
**작성일**: 2026-04-23 (D-6)  
**컨텍스트**: 도메인 용어 해석 비결정성 문제 해소. RAG 도입 여부 결정.

---

## 공통 서문 (ADR-001~004 관통 원칙)

SURI는 모든 레이어에서 **의존성 최소화**와 **동작 명시성**을 우선한다.
이는 PoC → Production 이관 시 변경 surface를 최소화하고, 각 계층의
책임 경계를 감사 문서에서 단선적으로 기술할 수 있게 하기 위함이다.

- ADR-001: 데이터 레이어 — 합성 데이터 (통제·재현성 우선)
- ADR-002: 프로토콜 레이어 — 공식 MCP SDK (의존성 최소·공식성)
- ADR-003: 오케스트레이션 레이어 — 공식 MCP SDK + Anthropic SDK 직접
- ADR-004: 지식 주입 레이어 — 본 문서

---

## Context

### 문제 발견

D-6 오전 Core 8 재측정 중 C1 (채널별 유지율 낙차) 수치 이상 발견:
- 전 채널 유지율 99.4~99.8%대 (업계 평균 13회차 88.2%, 25회차 68.9%와 괴리)
- 13회차와 25회차 낙차 0.00%p (설계 의도인 GA 낙차 패턴 미재현)

쿼리 분석 결과, Executor가 생성한 SQL이 분모를 "25회차 이상 납입 계약"으로
고정해 13·25회차가 동일 집합이 되는 **LLM 비결정성** 문제. 어제 C1은
같은 질문에 다른 SQL로 GA 89.23%/71.35% 산출 (PASS). 즉 Executor가
"유지율" 같은 도메인 용어를 매번 다르게 해석.

### 제약 조건

- **Sprint Rules 하드룰**: D-6 이후 신규 기술 스택 추가 금지
- **ADR-001/002/003 관통 철학**: 의존성 최소화
- **JD 매칭**: "Tool Usage 및 RAG 구현" 키워드 (현재 11/12, RAG 미구현)
- **시간**: 실질 개발일 D-6 ~ D-3 = 약 4일 (Claude Code 협업으로 속도 2~3배)
- **8/8 PASS 브랜치 보호**: 현재 Core 8 전부 PASS 상태 유지

### 이미 결정된 사항

- 3-Agent 파이프라인 E2E 작동 (ADR-003)
- PostgreSQL 15 + 3층 PII 방어 (SQL Guard / ROLE / VIEW)
- MCP server + 3 tools (list_tables, describe_table, execute_readonly_sql)

---

## Decision

**MCP tool 기반 deterministic glossary** (Option D)

- 용어 사전: YAML 파일 (20개 용어, 2023.6 공시 기준 반영)
- 인터페이스: `get_domain_term(term) -> dict` MCP tool (4번째 tool)
- 출처: 법령·기준서·KIRI 연구 기반 (자체 작성 정의 제로)
- 벡터 DB 미도입. chromadb·pgvector·faiss 모두 제외.

---

## Considered Options

### Option A: chromadb 기반 Full RAG (Schema RAG + Domain RAG)

- 구성: `chromadb` + embedding 클라이언트 + chunking 로직 추가
- 장점:
  - JD "RAG 구현" 키워드 직접 충족 (11/12 → 12/12)
  - 규모 확장 시 정공법
- 단점:
  - **ADR-001/002/003 철학 단절** — 의존성 +3개, 그 중 하나는 벡터 DB
  - **스코프 부적합** — 테이블 8개·용어 50개 규모에서 vector retrieval의
    recall 이점이 없음. 면접관이 "이 규모에 왜 RAG?" 반문 가능
  - **금융권 OSS 심사 surface 증가** — 벡터 DB는 C/C++ 바인딩 포함 심사 1~3개월
  - **8/8 PASS 브랜치 회귀 리스크** — Planner/Executor 프롬프트 재조정 범위 넓음
  - **Sprint Rules "신규 스택 금지" 하드룰 위반**

### Option B: 현상 유지 + 프롬프트 내 도메인 섹션

- 구성: `EXECUTOR_SYSTEM` 또는 `CRITIC_SYSTEM`에 용어 정의 섹션 추가
- 장점: 변경 범위 최소, 8/8 PASS 보호 확실
- 단점:
  - **근본 해결 아닌 워크어라운드** — 용어가 늘어나면 프롬프트 붕괴
  - **골든셋 overfitting 의심 여지** — "C1용 규칙"으로 보일 위험
  - **JD "Tool Usage 및 RAG 구현" 미충족**

### Option C: 반일 explore (하루 시간투자 후 A/B 재결정)

- 구성: chromadb 설치 + POC 1~2시간 후 내일 결정
- 장점: 실제 난이도 측정 후 판단
- 단점:
  - **Sunken cost 함정** — POC 돌아가면 "여기까지 왔는데" 심리로 A 기울 위험
  - **결정 미룸 비용** — 오늘 저녁은 리허설·이력서 등에 써야 할 시간
  - **정보 가치 낮음** — chromadb 설치 난이도는 이미 알려진 변수

### Option D: MCP tool 기반 deterministic glossary ✅

- 구성: YAML 용어 사전 + `get_domain_term` MCP tool (4번째)
- 장점:
  - **ADR-001/002/003 철학 직접 연속** — 의존성 0 추가, MCP tool 확장 패턴
  - **비결정성 근본 해결** — 용어 정의가 tool 호출로 결정적 retrieve
  - **JD "Tool Usage 및 RAG 구현" 충족** — retrieval-augmented의 본질
    (외부 지식을 context로 주입)을 vector 기반 아닌 exact-match로 구현
  - **Sprint Rules 준수** — MCP tool 추가는 스택 추가 아닌 ADR-002 패턴 확장
  - **8/8 PASS 보호** — 기존 플로우 유지, 새 tool은 선택적 호출
  - **금융권 OSS 심사 중립** — 의존성 추가 0
- 단점:
  - 도메인 용어 규모가 수천 개로 확장되면 exact match 한계
  - 유사어·오탈자 내성 없음 (vector retrieval 대비)

---

## Rationale

### 1. 4-AI 교차검증 만장일치

ChatGPT·Claude·Gemini·Perplexity 4개 모델에 동일 프롬프트로 질문한 결과:
- A 전면도입: 4/4 반대
- 8/8 PASS 보호: 4/4 최우선
- 거버넌스 시연 > RAG 시연: 4/4 동의
- JD 매칭률 11→12: 4/4 가치 낮음 평가
- Domain Dictionary 우선 (Schema보다): 4/4

특히 ChatGPT와 Claude는 **독립적으로** Vector DB 없이 MCP tool 기반
deterministic glossary 구현을 제안. 이 독립 수렴이 가장 강한 신호.

### 2. ADR-001~003 철학 관통성 유지

ADR-001 합성 데이터, ADR-002 공식 MCP SDK, ADR-003 프레임워크 없는 직접
구성 — 세 결정이 "의존성 최소화 + 이관 surface 최소화"로 관통.

Option A는 이 문장을 깨뜨린다. Option D는 유지한다.

> "데이터는 합성으로 통제하고, 프로토콜은 공식 SDK를 직접 쓰며,
> 오케스트레이션은 순수 Python으로 구성하고, 지식 주입은 기존
> MCP 패턴으로 확장한다."

ADR-004가 이 문장에 자연스럽게 들어간다.

### 3. JD 원문과의 정합

JD의 "실시간 데이터 접근 및 액션을 수행하는 **Tool Usage 및 RAG 구현**"은
Tool Usage와 RAG를 **같은 bullet**에 묶었다. JD 작성자의 의도는
엄격한 vector DB 기반 semantic search가 아닌 "외부 지식을 tool로
주입하는 방식" 전반을 염두에 둔 것으로 해석 가능.

Option D는 이 해석과 정합한다.

### 4. 스코프 적합성

본 PoC 도메인 범위:
- 테이블 8개
- 핵심 용어 20개 (golden-set + Scene 3 범위)

이 규모에서 vector retrieval의 recall 이점은 0에 수렴. 오히려 exact-match가
결정론적(deterministic) 보장으로 hallucination 방어에 유리. 금융권은
0.1% 오차도 허용되지 않는 decisiveness가 핵심.

### 5. 면접 서사 강화 (구현 여부 → 판단 능력)

면접관 예상 질문 *"RAG 안 쓰셨네요?"*에 대한 답변 차이:

- Option B: *"PoC 범위상 제외했습니다"* — 방어적
- Option D: *"RAG의 retrieval layer를 vector 기반이 아닌 exact-match로
  구현했습니다. 이 규모에서는 deterministic lookup이 합리적 선택이고,
  용어 수 확장 시 pgvector로 업그레이드할 경로는 설계 완료"* — **선언적**

"RAG를 모르고 안 쓴 사람"과 "알고 안 쓴 사람"을 구별하는 답변.

### 6. 금융권 프로덕션 이관 적합성

금융보안원 가이드라인: OSS 금지는 아니나 도입·활용·관리 절차 강조.
벡터 DB 추가는 프로덕션 이관 시 OSS 심사·관리 포인트 +1. Option D는
이 부담이 없고, 확장 시 **사내 Data Catalog 연동 또는 pgvector**로
직접 이관 가능 (PostgreSQL 재사용).

---

## Consequences

### 긍정적 결과

- ADR 4개가 단일 철학으로 관통 — 면접 서사 관통성 유지
- C1 비결정성 근본 해결 (용어 정의 결정적 retrieve)
- 8/8 PASS 브랜치 보호 확실
- 의존성 0 추가 — OSS 심사 surface 그대로
- MCP tool 패턴 재활용 — ADR-002 설계 일관성 증명
- 사업비 절감: glossary YAML은 계리팀·상품기획팀이 직접 수정 가능

### 트레이드오프

- **포기한 것**: JD 매칭 11/12 → 12/12 symbolic 상승, chromadb "구현 경험"
- **한계**: 수천 개 용어 규모에선 exact match 약점, 유사어·오탈자 내성 없음
- **확장 조건**: 도메인 용어가 unstructured 문서(약관·규제 해설) 검색이
  필요한 규모로 확장되면 RAG 이관 필요

### 운영 고려사항

- glossary YAML 수정은 반드시 peer review (용어 정의 오류는 SQL 오류로 직결)
- 매 수정 후 Core 8 회귀 측정 필수
- 용어 추가 시 출처 필드 필수 (법령·기준서·연구보고서)

---

## Migration Path

Production 이관 시 RAG 확장 경로:

### Phase 1 (현재): MCP tool + YAML
- 규모: ~50 용어
- 구현: 본 ADR

### Phase 2: MCP tool + PostgreSQL dictionary table
- 규모: ~500 용어
- 구현: YAML을 `domain_dictionary` 테이블로 이관. tool 시그니처 동일.
- 장점: 계리팀·상품팀이 DB UI로 직접 수정
- 의존성 추가: 0 (PostgreSQL 기존 사용)

### Phase 3: pgvector 기반 semantic retrieval
- 규모: 수천 개 이상 + 약관·규제 해설 등 unstructured docs
- 구현: `domain_dictionary` 테이블에 embedding 컬럼 추가
- 장점: 유사어·오탈자 내성, hybrid search (exact + semantic)
- 의존성 추가: pgvector 확장 1개 (PostgreSQL 네이티브라 OSS 심사 가벼움)

### Phase 4: 사내 Data Catalog 연동
- 금융사가 이미 운영하는 메타데이터 관리 시스템이 있을 경우 API MCP tool로 연결
- 의존성 추가: 0
- 장점: 사내 거버넌스 체계에 완전 통합

즉 Option D는 **미래의 Phase 2~4 전환을 모두 차단하지 않는다**. 반대로
Option A(chromadb 시작)는 pgvector 이관 시 embedding 재계산·데이터 마이그레이션
필요.

---

## 면접 방어 답변

### Q: RAG 왜 구현 안 하셨어요?

"세 가지 이유입니다. 첫째, 이 PoC 스코프에서 RAG가 기술적으로 의미 있는
가치를 내지 못합니다. 테이블 8개, 용어 50개 수준이면 vector retrieval의
recall 이점이 없고, `list_tables`+`describe_table` MCP tool이 이미
exact-match 기반 동적 스키마 조회를 수행합니다. 이 규모에서 chromadb를
얹는 것은 dependency 추가 비용 대비 기능 이득이 없다고 판단했습니다.
둘째, ADR-001/002/003에서 확립한 **의존성 최소화** 철학의 일관성입니다.
합성 데이터, 공식 MCP SDK, 프레임워크 없는 오케스트레이션 — 모두
프로덕션 이관 시 변경 surface를 최소화한다는 같은 원칙의 적용입니다.
RAG를 JD 키워드 때문에 추가하면 이 철학이 편의적이 됩니다. 셋째,
**업그레이드 경로는 설계해 두었습니다**. 도메인이 unstructured 문서로
확장되는 시점에는 pgvector로 이관합니다 — PostgreSQL을 이미 쓰고 있어
OSS 심사 surface가 가볍고, 사내 망분리 환경에서 외부 벤더 심사를
우회할 수 있기 때문입니다."

### Q: 이게 진짜 RAG인가요? 그냥 dict lookup 아닌가요?

"RAG의 본질은 Retrieval-Augmented Generation — LLM이 외부 지식을 
검색해 context에 주입하는 것입니다. 제 구현은 retrieval layer가 
vector 기반이 아닌 exact-match 기반입니다. 도메인 용어 50개 규모에서
vector retrieval은 recall 이점 없이 latency·의존성 비용만 추가합니다.
규모 확장 시 pgvector로 업그레이드하는 경로는 ADR-004에 명시되어
있습니다. **엄격한 vector DB 기반 RAG**를 JD가 특정한 것이 아니라면,
이 구현은 '**Tool Usage 및 RAG 구현**'의 본질을 만족한다고 봅니다."

### Q: 용어가 수천 개로 늘어나면 어떡하죠?

"Migration Path에 4단계로 설계했습니다. 현재는 YAML 50개. 500개까지는
PostgreSQL `domain_dictionary` 테이블로 이관, tool 시그니처 동일하게
유지. 수천 개+unstructured 문서 단계에서 pgvector 확장 추가. 마지막으로
사내 Data Catalog API 연동. 각 단계 이관 비용이 선형적이고, 현재 Phase 1
선택이 Phase 2~4를 차단하지 않도록 설계했습니다."

### Q: C1 비결정성은 정말 해결되나요?

"근본 원인은 Executor LLM이 '유지율'을 매번 다른 정의로 해석한 것입니다.
glossary가 있으면 tool 호출로 '13회차 분모는 13개월 전 신계약 코호트'
정의가 결정적으로 주입됩니다. 단 LLM이 tool을 **매번 호출하도록**
보장할 수는 없습니다. EXECUTOR 프롬프트에 '도메인 용어 발견 시
get_domain_term 호출' 원칙을 추가했고, 회귀 측정으로 C1 3회 반복 시
매번 코호트 기반 정의가 적용되는지 검증합니다. 100% deterministic을
보장하는 것은 아니지만, 기존 대비 재현성이 크게 개선됩니다."

---

## References

- 4-AI cross-validation research: `docs/research/rag-decision/`
- Glossary v1.1: `docs/glossary-draft.yaml`
- ADR-001: 합성 데이터 채택
- ADR-002: MCP 라이브러리 선택
- ADR-003: Agent Orchestration Framework 선택
- KIRI 2022-13 「보험계약 유지율에 관한 연구」(김동겸·정인영)
- 금융보안원 「금융권 오픈소스SW 활용 가이드」
- IFRS17 (K-IFRS 제1117호) 「보험계약」
- PostgreSQL pgvector: https://github.com/pgvector/pgvector
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk