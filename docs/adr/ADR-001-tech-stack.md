# ADR-001: SURI 기술 스택 (v3.2 → 프레임워크 부분 ADR-003으로 대체)

> SURI는 모든 레이어에서 의존성 최소화와 동작 명시성을 우선한다. 
> 이는 PoC → Production 이관 시 변경 surface를 최소화하고, 
> 각 계층의 책임 경계를 감사 문서에서 단선적으로 기술할 수 있게 
> 하기 위함이다.

- **Date**: 2026-04-21 (Initial) / 2026-04-22 (Amended — Agent Framework는 ADR-003으로 대체)
- **Status**: Accepted (with Agent Framework row superseded by ADR-003)
- **Author**: 동훈

## Supersedence Note (2026-04-22)

본 ADR v3.2 원안은 Agent Framework로 LangChain 1.x `create_agent`를
채택했다. 단 **"D-5 막힐 시 Anthropic SDK 전환 옵션 유지"**라는 완화
경로를 함께 적어두었다.

D-7 구현 단계에서 ADR-003 (2026-04-22)의 4-AI 교차검증(4:0 만장일치)
결과로 **Option C (공식 `mcp` SDK Client + Anthropic SDK 직접 구성)**
을 채택했다. 본 ADR의 "Agent Framework" 행과 관련 JD 매칭 근거는
ADR-003에 의해 대체된다. 나머지 행(LLM, Database, PII 처리, UI, 관측,
스케줄러, 배포)은 여전히 유효하다.

따라서 본 문서는 **히스토리 유지 + 교체 지점 명시** 형태로 갱신했다.
v3.2 원안 의사결정 기록은 섹션 하단에 그대로 보존한다.

## Context

한화생명 데이터전략부문 Data Agent Developer 포지션 지원용 9일 스프린트 PoC.

- 제출 마감: 2026-04-29 14:59 KST
- 실질 개발 가능: 7~8일
- 재사용 전제: 포지션 1건이 아닌 향후 6~12개월 Data Agent 포지션 공통 포트폴리오

### JD 핵심 요건 매칭 (11/12) — 갱신본

- ✅ Agent 프레임워크 E2E 개발 → **공식 `mcp` SDK + Anthropic SDK 직접 구성 (ADR-003)**
- ✅ LLM Orchestration / Agentic workflow → 3-Agent 구조
- ✅ MCP 연동 (**JD 직접 명시**) → 공식 MCP SDK의 FastMCP (ADR-002)
- ✅ Reasoning/Planning 파이프라인 → Planner Agent
- ✅ Multi-Agent 협업 구조 (JD 2회 등장) → Planner/Executor/Critic 3-Agent
- ✅ Tool Usage → `execute_readonly_sql`, `list_tables`, `describe_table` (3개)
- ✅ 실행 로그 기반 성능 최적화 → JSONL 감사 로그 (예정) + MCP Inspector 검증 이력
- ✅ 운영 안정화 → `is_error=True` 피드백 루프 + 자가 교정 (최대 2회 재시도)
- ✅ Python + SQL → 전체 Python, SQL 핵심
- ✅ 금융권 도메인 → 보험 상품 분석
- ✅ PoC 검증 → 작동 가능한 PoC 포지셔닝 (D-7 E2E 성공)
- ⚠️ RAG → Future Work (`docs/future-work.md`)

### 개인 제약

- LangChain / PostgreSQL 미경험 → 학습 리스크 존재
  (LangChain은 ADR-003에서 기각되어 이 리스크는 해소됨)
- SQL 기본 숙련 (SELECT / JOIN / GROUP BY)
- MCP, Airflow, Streamlit, Docker Compose 조금 써봄

## Decision — 갱신판 Stack

| Layer | Choice | 갱신 여부 |
|---|---|---|
| LLM | Claude Sonnet 4.6 (Executor) + Haiku 4.5 분리 예정 (Planner/Critic) | 동일 |
| Agent Framework | **공식 `mcp` SDK Client + Anthropic SDK 직접 (Option C)** | **ADR-003으로 대체** |
| Tool 계층 | 공식 `mcp.server.fastmcp.FastMCP` (Option A2) | ADR-002에서 확정 |
| MCP Tools | `execute_readonly_sql`, `list_tables`, `describe_table` | 3개로 확장 |
| Database | PostgreSQL 15 (Docker Compose), 9 오브젝트, **61만 행** 합성 데이터 | 스케일 갱신 |
| PII 처리 | `customers_safe` view + GRANT/REVOKE + SQL Guard (sqlglot AST) | 3층으로 명시 |
| UI | Streamlit 단독 | 동일 (구현 중) |
| 관측 | JSONL 감사 로그 + Streamlit 로그 탭 | 동일 (예정) |
| 스케줄러 | Airflow DAG — Future Work로 이관 | 스코프 조정 |
| 배포 | Railway Singapore, Hobby $5 | 동일 (예정) |
| 캐시 | **파일시스템 응답 캐시 (`.cache/agent_responses/`)** | 신규 (D-7 추가) |

### Multi-Agent 용어 통일

내부 문서·코드·면접 설명 모두 **"3-Agent"**로 표기 (JD의 Multi-Agent 키워드 매칭).

### 단계적 최적화 로드맵 — 갱신판

본 프로젝트의 엔지니어링 원칙: **"먼저 작동시키고, 실측한 뒤 최적화한다."**

1. **Phase 1 (D-6 마감, 필수)**: Sonnet 단일 모델로 3-Agent E2E baseline 구축 — ✅ **D-7 조기 달성**
2. **Phase 2 (조건부, D-5 이후 여유 시)**: Haiku 분리 실험 — 비용·지연 실측 후 Planner/Critic에 적용 — ⏳ **보류 (품질 테스트 후)**
3. **Phase 3 (조건부, D-4 이후 여유 시)**: OpenAI/Gemini로 골든셋 돌려 모델 간 EA 비교 — ⏳ Future Work
4. **Phase 4 (조건부, D-5 이후)**: 스키마 RAG 추가 — ⏳ Future Work

## Alternatives Considered

### LLM: Sonnet 단일 vs Sonnet+Haiku 분리 vs Opus+Sonnet vs Haiku 단일

- **Sonnet+Haiku 역할 분리**: 디자인 임팩트 있으나, baseline 확보 전 조기 최적화 우려. Phase 1에서 실측한 뒤 Phase 2에서 근거 있는 분리로 보류.
- **Opus+Sonnet**: 비용·지연 부담이 크고 PoC 단계에 과도.
- **Haiku 단일**: SQL 품질 보장 어려움.

### Agent Framework — ADR-003으로 이관

원안(LangChain 1.x `create_agent`) 및 대안(Anthropic SDK 직접, LangGraph
저수준, Pydantic AI) 4개를 재평가한 결과, **공식 `mcp` SDK Client +
Anthropic SDK 직접 (Option C)**으로 확정했다. 상세 근거는 ADR-003 참조.

Option C 채택의 핵심 이유:

1. ADR-002 (공식 MCP SDK) 철학 직접 연속 — 의존성 최소화
2. MCP 프로토콜 E2E 실제 사용 (stdio transport) — 3층 PII 방어 투명성
3. 부서 JD 3개 공통 언어(표준화·운영 체계·롤백) 정합 — "사내 통제 가능한 구조 설계자" 시그널
4. `langchain-mcp-adapters` 뒤에 MCP 경계가 숨지 않음 — 금융권 감사 문서 기술 용이

### Database: PostgreSQL vs SQLite vs DuckDB vs MySQL

- **SQLite**: 설정 최소이나 GRANT/REVOKE·view 기반 PII 거버넌스 서사가 약함 → SURI 핵심 차별화 훼손.
- **DuckDB**: 분석 성능 우수하나 금융권 운영 맥락 인지도 낮음.
- **MySQL**: PostgreSQL 대비 view·ROLE 유연성에서 열세.

### Observability: JSONL vs Phoenix vs LangSmith

- **Phoenix / LangSmith**: 관측 품질 강력하나 9일 내 설정·학습 비용 대비 이득 작음. JSONL + Streamlit 탭으로 JD "실행 로그 기반 최적화" 충분 커버.
- **추가 참고**: LangSmith는 LangChain 생태계 전제라 Option C 채택 이후 선택지에서 제외.

### Tool 계층: 공식 FastMCP vs 독립 fastmcp 2.x vs 저수준 Server

ADR-002에서 상세 분석. 공식 SDK의 FastMCP 1.0 (`mcp.server.fastmcp`)
채택 — 단일 의존성 + 생산성 + 공식성 확보.

### Deployment: Railway vs Fly.io vs Render vs Streamlit Cloud

- **Streamlit Cloud**: DB·cron 운영 불가.
- **Fly.io / Render**: 기능 유사하나 Railway의 Singapore 리전 + Postgres 애드온 + cron 통합이 매끄러움.

## Consequences

### Positive

- **JD 키워드 11/12 매칭**, MCP는 JD 직접 명시 단어를 그대로 커버
- 3-Agent 구조 + `is_error` 피드백 루프로 **자가수정·운영 안정화** 시연 가능
- `customers_safe` view + GRANT + Guard AST로 **PII 거버넌스 3층 서사** 일관
- 단계적 최적화 로드맵 자체가 **실측 기반 엔지니어링 사고** 증빙
- ADR-002/003과 함께 **"의존성 최소화 + 동작 명시성"** 3층 서사 완성
- Streamlit 단독 → UI 공수 최소, Agent 로직에 집중

### Negative / Risks

- LangChain 미경험 → **ADR-003으로 LangChain 기각되면서 리스크 해소**
- PostgreSQL 미경험 → Docker Compose 설정·초기화 타이밍 삽질 발생 (`.env` 동기화, INTEGER→BIGINT 전환 등) — **D-7 오전에 해결 완료**
- Sonnet 단일 → 모델 최적화 서사 부재 (Phase 2로 보완 예정)
- RAG 부재 → Future Work로 이관

### Mitigations

- **D-5 체크포인트**: MCP + PostgreSQL + 3-Agent E2E 한 번이라도 성공 필수 — ✅ **D-7에 조기 달성**
  - **LangChain 막힐 시 Anthropic SDK로 전환**이라는 원안 mitigation은 ADR-003에서 **처음부터 Option C 선택**으로 대체됨
- **D-3 체크포인트**: 골든셋 1차 측정 완료 — ⏳ 진행 중 (v3 Core 8 중 C1 PASS)
- **D-2 이력서 전용 진입**: SURI 80%여도 중단 — 제출 리스크보다 포트폴리오·이력서 완성 우선
- **코드 구조 원칙**: 프롬프트·상태·Agent 로직을 framework-neutral Python 함수로 작성 → 프레임워크 교체 비용 최소화 (이 원칙 덕분에 원안→Option C 전환도 부드러웠음)

## Sprint Rules Lock

- D-6 이후 스택 변경 금지 (README 최상단 고정)
- D-5 이후 신규 시나리오 추가 금지
- D-4 이후 UI 개선 금지
- D-3 이후 문서 구조 변경 금지
- **D-2 이후 이력서 전용, SURI 중단**

변경 발생 시 별도 ADR로 기록. 본 ADR의 "Agent Framework" 행은 ADR-003에 의해 대체되었으며, Status를 `Amended by ADR-003 (Agent Framework row only)`로 표기.

## Related

- [ADR-002: MCP 라이브러리 선택](./ADR-002-mcp-library.md) — 공식 SDK의 FastMCP 채택
- [ADR-003: Agent Orchestration Framework 선택](./ADR-003-agent-framework.md) — Option C (직접 구성) 확정, 본 ADR의 Agent Framework 행 대체
- ADR-004 (예정): Evaluation — 골든셋 v3 + 평가 지표

---

## 부록: v3.2 원안 의사결정 기록 (히스토리 보존)

아래는 2026-04-21 작성된 v3.2 원안의 Agent Framework 선택 기록.
**ADR-003에 의해 최종 대체되었으나 의사결정 투명성을 위해 보존**한다.

### 원안 — Agent Framework

> **LangChain 1.x `create_agent` (D-5 막힐 시 Anthropic SDK 전환 옵션)**

원안 근거:
- JD "Agent 프레임워크 E2E 개발" 키워드 매칭 우선 고려
- LangChain의 `create_agent` prebuilt 패턴으로 학습 곡선 단축 기대
- `langchain-mcp-adapters`로 공식 MCP SDK 통합 가능

원안의 Alternatives Considered:
- **Anthropic SDK 직접**: 학습 리스크 최소화 가능. 다만 JD "Agent 프레임워크 E2E" 요건 정면 매칭 약함. **D-5 막힐 경우 전환 옵션으로 유지**.
- **LangGraph 저수준**: 9일 내 학습 리스크 과도.
- **Pydantic AI**: 업계 인지도·자료량 부족.

### 원안이 대체된 이유 (요약)

1. ADR-002 (공식 FastMCP, 단일 의존성) 작성 후 **의존성 최소화가 문서화된 원칙**이 됨. 의존성 4개 추가(LangChain 1.x 생태계)가 이 원칙과 정면 충돌.
2. 4-AI 교차검증 (ADR-003 Round 1 + Round 2) 결과 4:0 만장일치로 Option C 지지.
3. 부서 3개 JD 공통 언어(표준화·운영·롤백)가 **프레임워크 사용자**보다 **사내 통제 가능한 구조 설계자** 선호를 시사.
4. 실제 구현 착수 시 `langchain-mcp-adapters` 중간 레이어가 MCP 경계를 감추는 문제가 발견됨 — 3층 PII 방어 시연 서사 훼손.

전체 근거는 ADR-003 참조.
