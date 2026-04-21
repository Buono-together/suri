# SURI — Statistical Understanding & Reasoning Interface

> 보험 상품 기획·분석 담당자를 위한 Data Agent PoC
> Submission: 2026-04-29 14:59 KST

## Positioning

보험 상품 분석 Agent의 전 기능 완성품이 아니라, 데이터 플랫폼 실무 경험을 기반으로
**읽기 전용 데이터 접근, 오케스트레이션, 실패 복구, 거버넌스 로그, 품질 평가**까지
연결한 **작동 가능한 PoC**.

## Sprint Rules (hard — 변경 금지)

- D-6 이후: 신규 기술 스택 추가 금지
- D-5 이후: 신규 시나리오 추가 금지
- D-4 이후: UI 개선 금지
- D-3 이후: 문서 구조 변경 금지
- **D-2 시작 = 이력서 풀데이 무조건 진입 (SURI 80%여도 중단)**

## Stack (v3.2 FINAL — see ADR-001)

- **LLM**: Claude Sonnet 4.6 (SQL Executor) + Haiku 4.5 (Planner/Critic)
- **Framework**: LangChain 1.x `create_agent` · TypedDict state · InMemorySaver
- **Tool layer**: 커스텀 read-only MCP 서버, single tool `execute_readonly_sql`
- **Data**: PostgreSQL 15 (Docker Compose), ~9 tables, ~50k rows 합성 데이터
- **PII**: `customers_safe` view only · raw table MCP-blocked
- **UI**: Streamlit (JSONL + log tab)
- **Scheduler**: Airflow `daily_product_kpi_dag`
- **Deploy**: Railway Singapore Hobby $5

## 3-Node Architecture
Planner (Haiku) → Executor (Sonnet SQL) → Critic (Haiku)
↓
실패 시 Planner 재계획
(Circuit Breaker 3회)

## Run

(D-7 이후 작성)

## License

Private — portfolio use only.
