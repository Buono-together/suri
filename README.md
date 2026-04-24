# SURI — Statistical Understanding & Reasoning Interface

> 보험 상품 기획·분석 담당자를 위한 Data Agent PoC
> Submission: 2026-04-29 14:59 KST

## 🌐 Live Demo

**URL**: [https://suri-production-89db.up.railway.app](https://suri-production-89db.up.railway.app)

- **Core 8**: 채널 유지율, 월별 신계약, APE, 거버넌스 시연 등 8개 프리셋
- **Scene 3 멀티턴**: 3턴 드릴다운 (판매채널 → 상품 → 계절성)
- **거버넌스 실증**: C5 "고객 전화번호 뽑아줘" → Layer 3 하드 블록 작동
- **Admin**: 캐시 제어

> **⚠️ 참고**:
> - Anthropic API 호출 때문에 응답당 60~100초 소요
> - 합성 데이터 기반 (실데이터 아님) — 생성 근거는 `data/seed/` 참조
> - 3층 PII 방어 실증: 악의적 질의 시 Layer 3 차단 체험 가능
> - 컨테이너 재시작 시 세션 초기화 (정상 동작)

## Positioning

보험 상품 분석 Agent의 전 기능 완성품이 아니라, 데이터 플랫폼 실무 경험을 기반으로
**읽기 전용 데이터 접근, Multi-Agent 오케스트레이션, 자가 교정, PII 거버넌스 3층 방어,
도메인 용어 결정적 주입, 멀티턴 드릴다운, 품질 평가**까지 연결한 **작동 가능한 PoC**.

## 차별화 축

| Layer | 차별점 |
|---|---|
| Governance | SQL Guard(AST) + DB ROLE + Schema VIEW — **3층 방어 구조** |
| Architecture | 공식 MCP SDK + Anthropic SDK 직접 구성 — **의존성 2개만** (ADR-003) |
| Behavior | Tool-first 스키마 탐색 — DB가 **single source of truth** |
| Resilience | `is_error=True` 피드백 루프 — Executor **자가 교정** |
| Domain Grounding | Glossary MCP tool + 법령·기준서 기반 20용어 — **용어 해석 결정성** (ADR-004) |

## Sprint Rules (hard — 변경 금지)

- D-6 이후: 신규 기술 스택 추가 금지
- D-5 이후: 신규 시나리오 추가 금지
- D-4 이후: UI 개선 금지
- D-3 이후: 문서 구조 변경 금지
- **D-2 시작 = 이력서 풀데이 무조건 진입 (SURI 80%여도 중단)**

## Stack (see ADR-001 / ADR-002 / ADR-003 / ADR-004 / ADR-005)

- **LLM**: Claude Sonnet 4.6 (전 Agent) — Haiku 4.5 이관 시도 후 보류 (ADR-003 Amendment, 측정 리포트: `docs/research/haiku-migration-test.md`)
- **Orchestration**: 공식 `mcp` SDK Client + Anthropic SDK 직접 구성 (ADR-003 Option C)
- **MCP 서버**: `mcp.server.fastmcp.FastMCP` (ADR-002)
- **MCP tools (4개)**: `execute_readonly_sql`, `list_tables`, `describe_table`, `get_domain_term`
- **Data**: PostgreSQL 15, 9 오브젝트, 61만 행 합성 데이터 (로컬: Docker Compose / 배포: Railway 애드온)
- **PII**: `customers_safe` VIEW only · raw `customers` table blocked at 3 layers
- **Domain Glossary**: YAML 기반 20용어 (KIRI·금감원·IFRS17 출처) — Vector DB 미도입 (ADR-004)
- **Multi-turn**: 최대 3턴 (Scene 3 시연 스코프), Planner history 주입 방식
- **Caching**: 파일시스템 응답 캐시 (`.cache/agent_responses/`) — history-aware 키
- **UI**: Streamlit 멀티페이지 (Agent 대화 / Glossary / Schema / Data Sample / Admin)
- **Deployment**: Railway 단일 프로젝트 + bootstrap idempotent 3-phase (ADR-005)

## 3-Agent 아키텍처
사용자 질문
│
▼
Planner         (자연어 → 분석 플랜 JSON)
│           멀티턴 시 이전 turn history 주입
│
▼
Executor        (Plan → 스키마 탐색 → 도메인 용어 조회 → SQL → MCP tool)
│           is_error=True 시 최대 2회 재시도 (자가 교정)
│   MCP stdio transport
▼
MCP Server      (4 tools: list_tables / describe_table / execute_readonly_sql / get_domain_term)
│           SQL Guard sqlglot AST → suri_readonly → VIEW (3층 PII 방어)
│
▼
Critic          (결과 → 도메인 해석 + 이상 탐지 + 한계 인정)
│
▼
최종 답변 (자연어)

## 시연 시나리오 3개 (docs/golden-set.md)

1. **Scene 1 — Layer 3 투명성**: 전화번호 요청 → 3층 방어 작동
2. **Scene 2 — 자가 교정**: `customers` 직접 요청 → GuardViolation → `customers_safe` 전환
3. **Scene 3 — 멀티턴 드릴다운**: 채널 유지율 → GA 특정 상품(P004 행복연금Plus) → 절판 시즌 발견

## 의도 주입 이상 패턴 3개 (합성 데이터)

- GA 채널 25회차 유지율 낙차 (KIRI 보고서 기반)
- 3월 신계약 스파이크 (절판 시즌)
- 특정 product_id 이상치 (P004 행복연금Plus)

## Repository Layout
suri/
├── app/
│   ├── agents/           # Planner / Executor / Critic / Orchestrator / Cache
│   ├── mcp_server/       # FastMCP server + Guard + DB connector + Glossary
│   │   ├── server.py     (4 MCP tools)
│   │   └── domain_glossary.yaml  (20 terms)
│   ├── pages_impl/       # Streamlit 멀티페이지 (agent / glossary / schema / data_sample / admin)
│   ├── ui/               # Rendering helpers + tab components
│   └── streamlit_app.py  # 엔트리 (st.navigation)
├── data/
│   ├── schema/           # 001_init.sql + 002_pii.sql
│   └── seed/             # 합성 데이터 생성 로직
├── docs/
│   ├── adr/              # ADR-001~005
│   ├── golden-set.md     # Core 8 + Scene 3 + Advanced 3
│   ├── glossary-draft.yaml       # 도메인 용어 사전 v1.1
│   ├── known-limitations.md       # 한계 정직 기록
│   ├── research/         # 4-AI 교차검증 원문 + Haiku 실측 리포트
│   └── interview-prep/   # design-decisions, interview-answers, qa-extended
├── scripts/
│   ├── e2e_test.py              # 단일 질문 E2E
│   ├── run_golden_set.py        # Core 8 회귀
│   ├── test_multiturn.py        # Scene 3 스모크
│   └── railway_bootstrap.py     # 3-phase idempotent 마이그레이션
├── railway.toml          # Railway 배포 설정
├── docker-compose.yml    # 로컬 PostgreSQL 15
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

# 6. 멀티턴 스모크
uv run python -m scripts.test_multiturn

# 7. Streamlit UI
PYTHONPATH=. uv run streamlit run app/streamlit_app.py
```

## 주요 의사결정

- [ADR-001: 기술 스택](./docs/adr/ADR-001-tech-stack.md) — 합성 데이터, PostgreSQL, Streamlit
- [ADR-002: MCP 라이브러리](./docs/adr/ADR-002-mcp-library.md) — 공식 SDK의 FastMCP 채택
- [ADR-003: Agent Framework](./docs/adr/ADR-003-agent-framework.md) — LangChain 대신 Option C (직접 구성) · Haiku 이관 보류 Amendment 포함
- [ADR-004: Domain Glossary](./docs/adr/ADR-004-domain-glossary.md) — Vector DB 없이 MCP tool 기반 deterministic glossary
- [ADR-005: Railway 배포](./docs/adr/ADR-005-railway-deployment.md) — 단일 프로젝트 + bootstrap idempotent 3-phase

## 한계 및 확장 경로

[Known Limitations](./docs/known-limitations.md) — 합성 데이터 절대값 괴리, C1 비결정성 측정 결과,
IFRS17 산출 불가 지표 목록, 3턴 멀티턴 상한, Production 이관 시 필요 작업.

## License

Private — portfolio use only.