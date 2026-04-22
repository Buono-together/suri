# SURI — Statistical Understanding & Reasoning Interface

> 보험 상품 기획·분석 담당자를 위한 Data Agent PoC
> Submission: 2026-04-29 14:59 KST

## Positioning

보험 상품 분석 Agent의 전 기능 완성품이 아니라, 데이터 플랫폼 실무 경험을 기반으로
**읽기 전용 데이터 접근, Multi-Agent 오케스트레이션, 자가 교정, PII 거버넌스 3층 방어,
품질 평가**까지 연결한 **작동 가능한 PoC**.

## 차별화 축

| Layer | 차별점 |
|---|---|
| Governance | SQL Guard(AST) + DB ROLE + Schema VIEW — **3층 방어 구조** |
| Architecture | 공식 MCP SDK + Anthropic SDK 직접 구성 — **의존성 2개만** (ADR-003) |
| Behavior | Tool-first 스키마 탐색 — DB가 **single source of truth** |
| Resilience | `is_error=True` 피드백 루프 — Executor **자가 교정** |

## Sprint Rules (hard — 변경 금지)

- D-6 이후: 신규 기술 스택 추가 금지
- D-5 이후: 신규 시나리오 추가 금지
- D-4 이후: UI 개선 금지
- D-3 이후: 문서 구조 변경 금지
- **D-2 시작 = 이력서 풀데이 무조건 진입 (SURI 80%여도 중단)**

## Stack (see ADR-001 / ADR-002 / ADR-003)

- **LLM**: Claude Sonnet 4.6 (Executor) · Haiku 4.5 (Planner/Critic, 이관 예정)
- **Orchestration**: 공식 `mcp` SDK Client + Anthropic SDK 직접 구성 (ADR-003 Option C)
- **MCP 서버**: `mcp.server.fastmcp.FastMCP` (ADR-002)
- **MCP tools**: `execute_readonly_sql`, `list_tables`, `describe_table`
- **Data**: PostgreSQL 15 (Docker Compose), 9 오브젝트, 61만 행 합성 데이터
- **PII**: `customers_safe` VIEW only · raw `customers` table blocked at 3 layers
- **Caching**: 파일시스템 응답 캐시 (`.cache/agent_responses/`) — 반복 실행 비용 0원
- **UI**: Streamlit (시연용, 구현 중)

## 3-Agent 아키텍처
사용자 질문
|
Planner         (자연어 -> 분석 플랜 JSON, Haiku 예정)
|
Executor        (Plan -> 스키마 탐색 -> SQL -> MCP tool, Sonnet 4.6)
|            is_error=True 시 최대 2회 재시도 (자가 교정)
|  MCP stdio transport
v
MCP Server      (SQL Guard sqlglot AST -> suri_readonly -> VIEW)
|            3층 PII 방어
|
Critic          (결과 -> 도메인 해석 + 이상 탐지 + 한계 인정)
|
최종 답변 (자연어)

## 시연 시나리오 3개 (docs/golden-set.md)

1. **Scene 1 — Layer 3 투명성**: 전화번호 요청 → 3층 방어 작동
2. **Scene 2 — 자가 교정**: `customers` 직접 요청 → GuardViolation → `customers_safe` 전환
3. **Scene 3 — 멀티턴 드릴다운**: 채널 유지율 → GA 특정 상품 → 절판 시즌 발견

## 의도 주입 이상 패턴 3개 (합성 데이터)

- GA 채널 25회차 유지율 낙차 (KIRI 보고서 기반)
- 3월 신계약 스파이크 (절판 시즌)
- 특정 product_id 이상치

## Repository Layout
suri/
├── app/
│   ├── agents/           # Planner / Executor / Critic / Orchestrator / Cache
│   ├── mcp_server/       # FastMCP server + Guard + DB connector
│   └── streamlit_app.py  # UI (구현 중)
├── data/seed/            # 합성 데이터 생성 로직
├── docs/
│   ├── adr/              # ADR-001/002/003
│   ├── golden-set.md     # Core 8 + Scene 3 + Advanced 3
│   └── interview-prep/   # design-decisions, interview-answers
├── scripts/              # E2E 테스트, 골든셋 러너
├── docker-compose.yml    # PostgreSQL 15
└── pyproject.toml        # uv 기반

## Run (로컬)

```bash
# 1. 의존성 설치
uv sync

# 2. DB 기동
docker compose up -d

# 3. 합성 데이터 로드
uv run python -m data.seed.load

# 4. 대화 실행 (단일 질문)
uv run python -m scripts.e2e_test

# 5. 골든셋 회귀 테스트
uv run python -m scripts.run_golden_set --only C1
uv run python -m scripts.run_golden_set            # 전체 8개
```

## 주요 의사결정

- [ADR-001: 기술 스택](./docs/adr/ADR-001-tech-stack.md) — 합성 데이터, PostgreSQL, Streamlit
- [ADR-002: MCP 라이브러리](./docs/adr/ADR-002-mcp-library.md) — 공식 SDK의 FastMCP 채택
- [ADR-003: Agent Framework](./docs/adr/ADR-003-agent-framework.md) — LangChain 대신 Option C (직접 구성)

## License

Private — portfolio use only.
