# SURI — Statistical Understanding & Reasoning Interface

> 합성 보험 상품 데이터 기반 자연어→SQL→해석 흐름 PoC
> 자연어 질의 → SQL 생성 → 실행 → 해석 흐름을 역할 분리형 3-Agent Pipeline으로 확인한 개인 포트폴리오

## 🌐 Live Demo & Repository

- **Live Demo**: [https://suri-production-89db.up.railway.app](https://suri-production-89db.up.railway.app)
- **GitHub**: [https://github.com/Buono-together/suri](https://github.com/Buono-together/suri)

## 프로젝트 성격

- **개인 포트폴리오 PoC**입니다. 상용 운영 시스템이 아닙니다.
- 데이터는 **100% 합성 데이터**입니다. 실데이터가 아니며 생성 근거는 `data/seed/`에 있습니다.
- 확인 범위는 Core 8 + 멀티턴 3 + 확장 3, 총 14개 질문 단위 동작 확인에 한정됩니다.
- Anthropic API 호출로 응답당 60~100초 소요 (시연용 수치).
- 컨테이너 재시작 시 세션 초기화 (정상 동작).

## Positioning

회사 실무에서는 데이터 플랫폼 운영, 접근 제어, 스케줄러, 로그·모니터링 기반 운영을 담당했고,
이 PoC는 그 경험을 바탕으로 **Data Agent 직무의 핵심 메커니즘 — Tool 호출, 조회 통제, 도메인 grounding,
검증 범위와 한계 기록**을 PoC 수준에서 확인한 개인 프로젝트입니다.

다루는 범위:

- **MCP Tool 기반 흐름** — DB 스키마 탐색, 읽기 전용 SQL 실행, 도메인 용어(Glossary) 조회
- **PoC 수준의 읽기 전용 조회 통제 흐름** — SQL Guard(AST) + DB Role + Schema View 조합
- **도메인 grounding** — KIRI·금감원·IFRS17 자료를 참고한 보험/회계 용어 Glossary 기반 (Vector DB 미도입)
- **실패 피드백 기반 SQL 수정 흐름** — `is_error=True` 피드백을 다음 호출에 재주입 (재시도 상한 2회)
- **검증 범위와 한계 기록** — Core 8 시나리오에서 Critic 답변의 핵심 키워드 포함 여부 확인(Core regression tests = answer keyword check), ADR 5건, known-limitations를 통해 검증 범위와 한계를 기록

다루지 않는 범위:

- 상용 운영, 실데이터 PII 처리, CI/CD 자동화, 대화 영속화, 4턴 이상 멀티턴.
  운영 적용 검토 시 필요한 보완 과제는 [Known Limitations §8](./docs/known-limitations.md)에 정리되어 있습니다.

## 구성 요소

| 영역 | 구성 |
|---|---|
| Orchestration | 공식 MCP SDK + Anthropic SDK 직접 구성 (LangChain 등 미도입, ADR-003) |
| Tool 호출 | `list_tables`, `describe_table`, `execute_readonly_sql`, `get_domain_term` (4개) |
| 조회 통제 (PoC 수준) | SQL Guard(sqlglot AST) → `suri_readonly` DB Role → `customers_safe` Schema View |
| 도메인 Grounding | YAML 기반 18개 도메인 용어 Glossary (KIRI·금감원·IFRS17 출처) — Vector DB 미도입 (ADR-004) |
| 재시도 | `is_error=True` 피드백 기반 SQL 수정 (상한 2회) |
| 문서화 | ADR 5건, Known Limitations, Core 8 시나리오 keyword 회귀 |

## Stack (see ADR-001 / ADR-002 / ADR-003 / ADR-004 / ADR-005)

- **LLM**: Claude Sonnet 4.6 (전 Agent) — Haiku 4.5 이관 시도 후 보류 (ADR-003 Amendment, 측정 리포트: `docs/research/haiku-migration-test.md`)
- **Orchestration**: 공식 `mcp` SDK Client + Anthropic SDK 직접 구성 (ADR-003 Option C)
- **MCP 서버**: `mcp.server.fastmcp.FastMCP` (ADR-002)
- **MCP tools (4개)**: `execute_readonly_sql`, `list_tables`, `describe_table`, `get_domain_term`
- **Data**: PostgreSQL 15, 9 오브젝트, SEED=20260421 기준 약 61만 행 합성 데이터 (로컬: Docker Compose / 배포: Railway 애드온)
- **조회 통제 (PoC 수준)**: `customers_safe` VIEW만 노출, raw `customers` 테이블은 Guard + Role + View 조합으로 차단
- **Domain Glossary**: YAML 기반 18개 도메인 용어 (KIRI·금감원·IFRS17 출처) — Vector DB 미도입 (ADR-004)
- **Multi-turn**: 최대 3턴 (멀티턴 시연 스코프), Planner history 주입 방식
- **Caching**: 파일시스템 응답 캐시 (`.cache/agent_responses/`) — history-aware 키
- **UI**: Streamlit 멀티페이지 (Agent 대화 / Glossary / Schema / Data Sample / Admin)
- **Deployment**: Railway 단일 프로젝트 + bootstrap idempotent 3-phase (ADR-005)

## 역할 분리형 3-Agent Pipeline

복잡한 협업형 Multi-Agent 시스템이 아니라, **SQL 생성·실행·해석을 역할별로 분리한 3-Agent Pipeline**입니다.

```
사용자 질문
    │
    ▼
Planner       (자연어 → 분석 플랜 JSON)
    │         멀티턴 시 이전 turn history 주입
    │
    ▼
Executor      (Plan → 스키마 탐색 → 도메인 용어 조회 → SQL → MCP tool)
    │         is_error=True 피드백 기반 SQL 수정 (상한 2회)
    │  MCP stdio transport
    ▼
MCP Server    (4 tools: list_tables / describe_table / execute_readonly_sql / get_domain_term)
    │         SQL Guard(sqlglot AST) → suri_readonly Role → customers_safe View
    │
    ▼
Critic        (결과 → 도메인 해석 + 이상 탐지 + 한계 인정)
    │
    ▼
최종 답변 (자연어)
```

## 시연 시나리오 3개 (docs/golden-set.md)

1. **Scene 1 — 조회 통제 흐름 확인**: 전화번호 요청 → Guard/Role/View 조합으로 raw `customers` 접근 차단
2. **Scene 2 — 실패 피드백 기반 SQL 수정**: `customers` 직접 요청 → GuardViolation → `customers_safe`로 재작성
3. **Scene 3 — 멀티턴 드릴다운 (3턴)**: 채널 유지율 → GA 특정 합성 상품(P004) → 절판 시즌 식별

## 의도 주입 이상 패턴 3개 (합성 데이터)

합성 데이터에 의도적으로 주입한 패턴이며, 절대값은 업계 실측과 차이가 있습니다 (Known Limitations §1 참조).

- GA 채널 25회차 유지율 낙차 (KIRI 보고서 기반)
- 3월 신계약 스파이크 (절판 시즌)
- 특정 합성 product_id 이상치 (P004)

## Repository Layout

```
suri/
├── app/
│   ├── agents/           # Planner / Executor / Critic / Orchestrator / Cache
│   ├── mcp_server/       # FastMCP server + Guard + DB connector + Glossary
│   │   ├── server.py     (4 MCP tools)
│   │   └── domain_glossary.yaml  (18 terms)
│   ├── pages_impl/       # Streamlit 멀티페이지 (agent / glossary / schema / data_sample / admin)
│   ├── ui/               # Rendering helpers + tab components
│   └── streamlit_app.py  # 엔트리 (st.navigation)
├── data/
│   ├── schema/           # 001_init.sql + 002_pii.sql
│   └── seed/             # 합성 데이터 생성 로직
├── docs/
│   ├── adr/              # ADR-001~005
│   ├── golden-set.md     # Core 8 + 멀티턴 3 + 확장 3
│   ├── glossary-draft.yaml       # 도메인 용어 사전 v1.1
│   ├── known-limitations.md      # 한계 정직 기록
│   ├── research/         # 4-AI 교차검증 원문 + Haiku 실측 리포트
│   └── interview-prep/   # design-decisions, interview-answers, qa-extended
├── scripts/
│   ├── e2e_test.py              # 단일 질문 E2E
│   ├── run_golden_set.py        # Core 8 시나리오 답변 키워드 확인
│   ├── test_multiturn.py        # 멀티턴 스모크
│   └── railway_bootstrap.py     # 3-phase idempotent 마이그레이션
├── railway.toml          # Railway 배포 설정
├── docker-compose.yml    # 로컬 PostgreSQL 15
└── pyproject.toml        # uv 기반
```

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

# 5. Core 8 시나리오 keyword 회귀 (답변 텍스트의 기대 키워드 포함 확인)
uv run python -m scripts.run_golden_set --only C1
uv run python -m scripts.run_golden_set            # 전체 8개

# 6. 멀티턴 스모크
uv run python -m scripts.test_multiturn

# 7. Streamlit UI
PYTHONPATH=. uv run streamlit run app/streamlit_app.py
```

## 주요 의사결정 (ADR)

- [ADR-001: 기술 스택](./docs/adr/ADR-001-tech-stack.md) — 합성 데이터, PostgreSQL, Streamlit
- [ADR-002: MCP 라이브러리](./docs/adr/ADR-002-mcp-library.md) — 공식 SDK의 FastMCP 채택
- [ADR-003: Agent Framework](./docs/adr/ADR-003-agent-framework.md) — LangChain 대신 Option C (직접 구성) · Haiku 이관 보류 Amendment 포함
- [ADR-004: Domain Glossary](./docs/adr/ADR-004-domain-glossary.md) — Vector DB 없이 MCP tool 기반 YAML 기반 Glossary 조회 방식
- [ADR-005: Railway 배포](./docs/adr/ADR-005-railway-deployment.md) — 단일 프로젝트 + bootstrap idempotent 3-phase

## 한계 및 확장 경로

[Known Limitations](./docs/known-limitations.md) — 합성 데이터 절대값 괴리, Agent 실행 비결정성 측정 결과,
IFRS17 산출 불가 지표 목록, 3턴 멀티턴 상한, 운영 적용 검토 시 추가로 필요한 보완 과제.

## License

Private — portfolio use only.
