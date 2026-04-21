# ADR-001: SURI 기술 스택 (v3.2)

- **Date**: 2026-04-21
- **Status**: Accepted
- **Author**: 동훈
- **Supersedes**: — (initial)

## Context

한화생명 데이터전략부문 Data Agent Developer 포지션 지원용 9일 스프린트 PoC.

- 제출 마감: 2026-04-29 14:59 KST
- 실질 개발 가능: 7~8일
- 재사용 전제: 포지션 1건이 아닌 향후 6~12개월 Data Agent 포지션 공통 포트폴리오

### JD 핵심 요건 매칭 (11/12)

- ✅ Agent 프레임워크 E2E 개발 → LangChain 채택
- ✅ LLM Orchestration / Agentic workflow → 3-Agent 구조
- ✅ MCP 연동 (**JD 직접 명시**) → 커스텀 read-only MCP 서버
- ✅ Reasoning/Planning 파이프라인 → Planner Agent
- ✅ Multi-Agent 협업 구조 (JD 2회 등장) → Planner/Executor/Critic 3-Agent
- ✅ Tool Usage → `execute_readonly_sql`
- ✅ 실행 로그 기반 성능 최적화 → JSONL 감사 로그
- ✅ 운영 안정화 → Circuit Breaker + Critic 재계획
- ✅ Python + SQL → 전체 Python, SQL 핵심
- ✅ 금융권 도메인 → 보험 상품 분석
- ✅ PoC 검증 → 작동 가능한 PoC 포지셔닝
- ⚠️ RAG → 조건부 추가 (Phase 4, D-5 체크포인트 이후 여유 판단)

### 개인 제약

- LangChain / PostgreSQL 미경험 → 학습 리스크 존재
- SQL 기본 숙련 (SELECT / JOIN / GROUP BY)
- MCP, Airflow, Streamlit, Docker Compose 조금 써봄

## Decision — v3.2 Stack

| Layer | Choice |
|---|---|
| LLM | Claude Sonnet 4.6 단일 (단계적 최적화 로드맵) |
| Agent Framework | LangChain 1.x `create_agent` (D-5 막힐 시 Anthropic SDK 전환 옵션) |
| Tool 계층 | 커스텀 Read-only MCP 서버, single tool `execute_readonly_sql` |
| Database | PostgreSQL 15 (Docker Compose), ~9 테이블, ~50k 행 합성 데이터 |
| PII 처리 | `customers_safe` view + GRANT/REVOKE 권한 분리 |
| UI | Streamlit 단독 |
| 관측 | JSONL 감사 로그 + Streamlit 로그 탭 |
| 스케줄러 | Airflow DAG 1개 (`daily_product_kpi_dag`), 별도 compose 파일 |
| 배포 | Railway Singapore, Hobby $5 |

### Multi-Agent 용어 통일

내부 문서·코드·면접 설명 모두 **"3-Agent"**로 표기 (JD의 Multi-Agent 키워드 매칭).

### 단계적 최적화 로드맵

본 프로젝트의 엔지니어링 원칙: **"먼저 작동시키고, 실측한 뒤 최적화한다."**

1. **Phase 1 (D-6 마감, 필수)**: Sonnet 단일 모델로 3-Agent E2E baseline 구축
2. **Phase 2 (조건부, D-5 이후 여유 시)**: Haiku 분리 실험 — 비용·지연 실측 후 Planner/Critic에 적용
3. **Phase 3 (조건부, D-4 이후 여유 시)**: OpenAI/Gemini로 골든셋 돌려 모델 간 EA 비교
4. **Phase 4 (조건부, D-5 이후)**: 스키마 RAG 추가 — JD의 RAG 키워드 커버

## Alternatives Considered

### LLM: Sonnet 단일 vs Sonnet+Haiku 분리 vs Opus+Sonnet vs Haiku 단일

- **Sonnet+Haiku 역할 분리**: 디자인 임팩트 있으나, **baseline 확보 전 조기 최적화 우려**. Phase 1에서 실측한 뒤 Phase 2에서 근거 있는 분리로 보류.
- **Opus+Sonnet**: 비용·지연 부담이 크고 PoC 단계에 과도.
- **Haiku 단일**: SQL 품질 보장 어려움.

### Agent Framework: LangChain vs SDK 직접 vs LangGraph 저수준 vs Pydantic AI

- **Anthropic SDK 직접**: 학습 리스크 최소화 가능. 다만 JD "Agent 프레임워크 E2E" 요건 정면 매칭 약함. **D-5 막힐 경우 전환 옵션으로 유지**.
- **LangGraph 저수준**: 9일 내 학습 리스크 과도.
- **Pydantic AI**: 업계 인지도·자료량 부족.

### Database: PostgreSQL vs SQLite vs DuckDB vs MySQL

- **SQLite**: 설정 최소이나 GRANT/REVOKE·view 기반 PII 거버넌스 서사가 약함 → SURI 핵심 차별화 훼손.
- **DuckDB**: 분석 성능 우수하나 금융권 운영 맥락 인지도 낮음.
- **MySQL**: PostgreSQL 대비 view·ROLE 유연성에서 열세.

### Observability: JSONL vs Phoenix vs LangSmith

- **Phoenix / LangSmith**: 관측 품질 강력하나 9일 내 설정·학습 비용 대비 이득 작음. JSONL + Streamlit 탭으로 JD "실행 로그 기반 최적화" 충분 커버.

### Tool 계층: 커스텀 MCP vs LangChain 내장 SQL toolkit vs 함수호출 직접

- LangChain 내장은 개발 속도 유리하나 **JD가 MCP를 직접 명시** → 커스텀 MCP가 키워드 매칭·재사용 가치 모두 우위.

### Deployment: Railway vs Fly.io vs Render vs Streamlit Cloud

- **Streamlit Cloud**: DB·cron 운영 불가.
- **Fly.io / Render**: 기능 유사하나 Railway의 Singapore 리전 + Postgres 애드온 + cron 통합이 매끄러움.

## Consequences

### Positive

- **JD 키워드 11/12 매칭**, MCP는 JD 직접 명시 단어를 그대로 커버
- 3-Agent 구조 + Circuit Breaker로 **자가수정·운영 안정화** 시연 가능
- `customers_safe` view + GRANT로 **PII 거버넌스 서사** 일관
- 단계적 최적화 로드맵 자체가 **실측 기반 엔지니어링 사고** 증빙
- Streamlit 단독 → UI 공수 최소, Agent 로직에 집중

### Negative / Risks

- LangChain 미경험 → D-6~D-7 학습 곡선 리스크
- PostgreSQL 미경험 → Docker Compose 설정·초기화 타이밍 삽질 가능
- Sonnet 단일 → 모델 최적화 서사 부재 (Phase 2로 보완)
- RAG 부재 → JD 키워드 1개 미매칭 (Phase 4로 조건부 보완)

### Mitigations

- **D-5 체크포인트**: MCP + PostgreSQL + 3-Agent E2E 한 번이라도 성공 필수
  - 미달 시: Airflow DAG 포기, ADR 문서 4→2개 축소
  - LangChain 막힐 시: Anthropic SDK로 전환 (코드 구조를 framework-neutral하게 유지)
- **D-3 체크포인트**: 골든셋 1차 측정 완료, 미달 시 UI 완성도 포기
- **D-2 이력서 전용 진입**: SURI 80%여도 중단 — 제출 리스크보다 포트폴리오·이력서 완성 우선
- **코드 구조 원칙**: 프롬프트·상태·Agent 로직을 framework-neutral Python 함수로 작성 → 프레임워크 교체 비용 최소화

## Sprint Rules Lock

- D-6 이후 스택 변경 금지 (README 최상단 고정)
- D-5 이후 신규 시나리오 추가 금지
- D-4 이후 UI 개선 금지
- D-3 이후 문서 구조 변경 금지
- **D-2 이후 이력서 전용, SURI 중단**

변경 발생 시 별도 ADR(ADR-005 이후)로 기록, 본 ADR은 Status를 `Superseded by ADR-XXX`로 갱신.

## Related

- ADR-002: Read-only MCP Tool 설계 (D-7 예정)
- ADR-003: Self-correction & Circuit Breaker 전략 (D-5 예정)
- ADR-004: Evaluation — 골든셋 & Wilson CI (D-4 예정)
