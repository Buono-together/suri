# SURI — Claude Project Knowledge

> 이 문서는 Claude Project의 Knowledge에 업로드되는 정적 정보다.
> 매 세션 시작 시 자동 로드되며, 프로젝트 정체성·스택·용어·컨벤션을 담는다.
> **동적인 상태(오늘 D-몇, 무엇이 완료됐는지)는 여기 박지 않는다** —
> suri-bridge MCP로 실시간 조회한다.

---

## 1. 프로젝트 정체성

### One-liner
SURI (Statistical Understanding & Reasoning Interface). 보험 상품 기획·분석
담당자가 자연어로 데이터를 질의하면 3-Agent 파이프라인이 SQL을 생성·실행·
해석해 답변하는 Data Agent PoC.

### 목표
한화생명 데이터전략부문 Data Agent Developer 포지션 지원용 9일 스프린트 PoC.
제출 마감: **2026-04-29 14:59 KST**.

### 레포
- 로컬: `/Users/donghoon/find_job/projects/suri`
- GitHub: `https://github.com/Buono-together/suri` (private)
- 브랜치: main only

### 작업 환경
- 현 세션 도구: Claude.ai 웹 + `suri-bridge` MCP
- 실제 코드 작업은 로컬에서 `uv`로 실행
- Claude Code 경험 있음 (다른 프로젝트). 이 프로젝트는 웹 세션 중심.

---

## 2. 차별화 축 (면접 서사의 뼈대)

| Layer | 차별점 |
|---|---|
| Governance | SQL Guard(AST) + DB ROLE + Schema VIEW — **3층 방어** |
| Architecture | 공식 MCP SDK + Anthropic SDK 직접 — **의존성 2개만** (ADR-003) |
| Behavior | Tool-first 스키마 탐색 — DB가 **single source of truth** |
| Resilience | `is_error=True` 피드백 루프 — Executor **자가 교정** |

핵심 메시지: "한화생명 외부 AI 벤더(Allganize Alli) 도입에 대응하는,
**자체 개발 가능한 Data Agent 설계자**".

서사 3축:
1. "Application 레이어만 신뢰하지 않는다" — 3층 PII 방어
2. "에이전트는 실수하고, 스스로 고치고, 숨기지 않는다" — self-correction
3. "대시보드는 숫자를 보여주지만, 에이전트는 그 숫자에 이어지는 질문을 같이 던진다" — 멀티턴

---

## 3. 기술 스택

### 확정 사항 (ADR-001/002/003)

- **LLM**: Claude Sonnet 4.6 (Executor) · Haiku 4.5 분리 예정 (Planner/Critic)
  - 모델 문자열: `claude-sonnet-4-6`, `claude-haiku-4-5-20251001`
- **Agent Framework**: 공식 `mcp` SDK Client + Anthropic SDK 직접 (Option C)
  - LangChain·LangGraph **미사용** (ADR-003에서 기각)
  - 의존성 2개: `mcp`, `anthropic`
- **MCP 서버**: `from mcp.server.fastmcp import FastMCP` (공식 SDK 내부, ADR-002)
- **MCP tools (3개)**: `execute_readonly_sql`, `list_tables`, `describe_table`
- **Database**: PostgreSQL 15 (Docker Compose), 9 오브젝트, 61만 행 합성 데이터
- **PII 3층**: SQL Guard (sqlglot AST) + `suri_readonly` ROLE + `customers_safe` VIEW
- **패키지 매니저**: uv
- **Python**: 3.12.13
- **UI**: Streamlit (구현 중)
- **캐시**: 파일시스템 응답 캐시 `.cache/agent_responses/`

### 기각된 것 (질문 받을 때 답변 준비)

- LangChain 1.x `create_agent` — ADR-003에서 Option C로 대체
- `fastmcp` 독립 패키지 (PrefectHQ) — ADR-002에서 공식 SDK 내부 FastMCP로 대체
- Airflow DAG — Future Work
- RAG — Future Work
- Phoenix/LangSmith — Future Work (JSONL + Streamlit 탭으로 충분)

---

## 4. 디렉토리 구조

```
suri/
├── app/
│   ├── agents/          # Planner / Executor / Critic / Orchestrator / Cache
│   │   ├── base.py         (Anthropic client + MCP helpers + cached_system)
│   │   ├── prompts.py      (PLANNER/EXECUTOR/CRITIC SYSTEM)
│   │   ├── planner.py      (JSON 파싱 + retry 안전장치)
│   │   ├── executor.py     (tool_use loop + self-correction)
│   │   ├── critic.py       (도메인 해석)
│   │   ├── orchestrator.py (run / run_async)
│   │   └── cache.py        (filesystem cache)
│   ├── mcp_server/      # FastMCP server + Guard + DB connector
│   │   ├── server.py       (FastMCP + 3 tools)
│   │   ├── guards.py       (sqlglot AST)
│   │   └── db.py           (execute_readonly_json + DSN)
│   └── streamlit_app.py (UI, 스켈레톤만)
├── data/
│   ├── schema/          # 001_init.sql (tables), 002_pii.sql (views + ROLE)
│   └── seed/            # config / generators / anomalies / checks / load
├── docs/
│   ├── adr/             # ADR-001/002/003
│   ├── interview-prep/  # design-decisions, interview-answers
│   ├── research/        # 4-AI cross-validation 원문
│   ├── golden-set.md    (v3: Core 8 + Scene 3 + Advanced 3)
│   ├── env-setup.md
│   ├── future-work.md
│   └── seed-plan.md
├── scripts/
│   ├── e2e_test.py             (단일 질문 E2E)
│   ├── run_golden_set.py       (Core 8 회귀)
│   ├── test_agent_exploration.py
│   └── test_new_tools.py
├── airflow/dags/        # Future Work
├── .cache/              # gitignored
├── .env                 # gitignored (POSTGRES_*, ANTHROPIC_API_KEY)
├── .env.example
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

---

## 5. 합성 데이터 설계

### 규모 (61만 행)
- products: 20
- agents: 50
- customers: 15,000 (PII 포함 원본, readonly 차단)
- policies: 28,186
- premium_payments: 569,878
- claims: 4,253

### 분포
- **채널**: 방카 50 / 전속 20 / GA 20 / TM 7 / CM 3
- **상품유형**: 보장성 65 / 저축성 25 / 변액 10
- **상품군**: 건강 35 / 종신 25 / 연금 20 / 저축 10 / 정기 10
- **납입주기**: monthly 85 / annual 5 / single 10
- **연령**: 20대 7 / 30대 25 / 40대 30 / 50대 28 / 60대+ 10

### 의도 주입 이상 패턴 3개
1. **GA 채널 유지율 낙차**: 13·25회차 lapse probability 19% overlay
2. **3월 절판 스파이크**: 평월의 1.8배
3. **특정 product_id 25회차 이상치**: 교보생명 2023 사례 모델

### 합성 데이터의 알려진 한계 (면접 방어)
- 절대 수준이 업계 대비 낮음 (13회차 ~58% vs 업계 88%)
- 상대 패턴(GA 낙차 1위)은 재현됨
- 이 이슈는 CRITIC_SYSTEM의 "Data caveat" 문구로 프롬프트 레벨 완화
- 상세는 `docs/known-limitations.md` 참조

### PII 포맷 (DLP 오탐 방지)
- 주민번호: `RRN-XXXXXX` 더미 포맷
- 전화: `010-99XX-XXXX` (미할당 대역)
- 이메일: `@example.com` (IANA 예약)
- 주소: 시도 + 시군구까지만

---

## 6. 도메인 벤치마크 (업계 실측치)

### 유지율 (Korean life insurance)
- 2021 KIRI: 13회차 83.9% / 25회차 67.1%
- **2024 금감원: 13회차 88.2% / 25회차 68.9%** ← CRITIC 기준선
- 2025H1 생보협회: 13회차 88.3% / 25회차 75.8%
- 2025 종신보험(최악): 13회차 81.0% / 25회차 58.6%

### 채널 특성
- 전속·GA가 방카보다 13→25회차 낙차 큼
- 원인: 판매수당 환수시점 경과 (KIRI 확인)
- 방카는 상대적으로 안정적

### IFRS 17
- 측정모델: GMM / PAA / VFA
- GMM: 장기보장성 중심, PAA: 단기 중심, VFA: 변액
- CSM 정식 산출은 사업비·준비금·할인율 필요 → **이 PoC 데이터로 불가**

### APE 공식
- monthly × 12 + annual + lumpsum × 0.1

---

## 7. 용어 규칙

### 한국어 (일관성)
- 설계사 (O) / 보험사원 (X)
- 판매채널 (O) / 세일즈 채널 (X)
- 유지율 (O) / retention rate은 괄호 병기 OK
- 보장성/저축성/변액 (표준 분류)
- 방카 / 전속 / GA / TM / CM (채널 구분 필수)

### 스타일
- "월초보험료 (ANP)" 처럼 한국어+영문 약어 괄호 병기
- 실제 회사명·상품명 직접 사용 금지

---

## 8. 코드·문서 컨벤션

### 테스트 실행
- `uv run python -m scripts.e2e_test` (모듈 실행)
- `python scripts/xxx.py` 형태는 **금지** (상대 임포트 깨짐)

### ADR
- 파일명: `docs/adr/ADR-NNN-title.md`
- Status: Accepted / Superseded by ADR-XXX / Amended
- 포맷: Context / Decision / Rationale / Consequences / Alternatives Considered

### 커밋 메시지
- `<type>(<scope>): <summary>`
- types: feat / fix / docs / refactor / test / chore
- 한 줄 제목으로 일단 커밋 후, 필요하면 `--amend`로 상세 메시지

### 프롬프트 수정 시
- 백업 파일(`.bak`)은 작업 중간에만 만들고 정리 단계에서 삭제
- 수정 후 `rm -rf .cache/agent_responses`로 캐시 무효화

### 로깅
- 기본 INFO
- MCP stderr 로깅 (stdout은 JSON-RPC 전용)

---

## 9. 골든셋 v3 핵심

### Core 8 (회귀 테스트)
- C1: 채널별 13·25회차 유지율 낙차 → GA 1위 기대
- C2: 월별 신계약 추이 → Critic이 3월 스파이크 자발 발견
- C3: APE + 청구율 → Critic이 "proxy" 선 긋기
- **C4: customers 30대 남성** → GuardViolation → customers_safe 자가교정 ⭐
- **C5: 전화번호** → 하드 블록 + 대안 제시 ⭐
- C6: IFRS17 GMM/PAA 비교
- C7: CSM 계산 가능 여부 → "불가" 판단 + proxy 제시
- C8: 3월 절판 코호트 vs 평월 조기 해지율

### Scene 3 (시연용, ~4.5분)
1. Scene 1 (75s): Layer 3 투명성 — 전화번호 → 3층 방어
2. Scene 2 (90s): 자가 교정 — customers → customers_safe
3. Scene 3 (120s): 멀티턴 드릴다운 — 채널 유지율 → GA 특정 상품 → 절판 시즌

### Advanced 3 (Q&A 예비 탄약)
- A1: 이번 분기 가장 큰 리스크 요인은? (극도의 모호성)
- A2: 유지율 안 좋은 채널은? 기준은 네가 잡고 (기준 설정 능력)
- A3: 청구 많은 상품 수익성? (한계 인정 + proxy)

### 평가 지표
- Core 8 통과율 ≥ 7/8
- C4 self-correction 1회 이상
- C5 전화번호 반환 절대 0건
- 평균 latency < 60초 (새 질문)

---

## 10. 면접 포지셔닝

### AI 활용 솔직 인정
- 코드 70%+ AI 생성
- 본인 주도 영역 4가지:
  1. 기획·포지셔닝 (JD 분석, 차별화 축 선정)
  2. 의사결정 (4-AI 교차검증 방법론)
  3. 도메인 지식 (KIRI·IFRS17·PIPA)
  4. 검증 루프 (ADR, 골든셋, 코드 감사)

### 한 줄 프레이밍
"CTO 역할을 제가, AI가 시니어 엔지니어 역할을 했습니다."

### 주요 Q&A 대응
- "LangChain 왜 안 썼나?" → ADR-003 Option C 근거 (의존성 최소화, MCP 경계 투명성)
- "ChatGPT가 짜준 거 아닌가?" → 의사결정·도메인 판단은 본인 주도
- "9일 AI 없이 못 하는 거 아닌가?" → 맞음. 그게 요점. 2026년 시니어는 AI를 잘 쓰는 사람.
- 상세는 `docs/interview-prep/interview-answers.md`

---

## 11. 면접관이 실제로 볼 것

- GitHub 레포 (private → 면접 시점 공개 전환)
- 로컬 시연 (Streamlit + 노트북)
- `docs/adr/`, `docs/golden-set.md`, `docs/interview-prep/`
- 시연 중 실시간 로그 스트림 (Tool 호출, Guard 차단, self-correction)

### 제출 형식 (복수)
- 라이브 데모 가능성
- 로컬 데모 (백업 녹화본)
- GitHub README 중심
- ADR + 설계 문서

---

## 12. Sprint Rules (hard)

- D-6 이후: 신규 기술 스택 추가 금지
- D-5 이후: 신규 시나리오 추가 금지
- D-4 이후: UI 개선 금지
- D-3 이후: 문서 구조 변경 금지
- **D-2 시작 = 이력서 풀데이 (SURI 80%여도 중단)**

---

## 13. 중요 트러블슈팅 메모

### Claude Sonnet 4.6의 친절함 문제
Executor가 tool 결과 받고 마크다운 표로 정리하려 함. 해결:
```
CRITICAL OUTPUT RULE: After a successful tool call, output NOTHING.
```
프롬프트에 명시. 요약은 Critic 전담.

### Prompt caching
- system prompt 1024 tokens 미만이면 캐시 미적용
- SURI는 현재 ~570 tokens → 캐시 효과 없음
- 그래도 `cached_system()` 코드는 유지 (확장 대비)
- 면접에서 "측정 기반 판단" 예시로 사용 가능

### Anthropic tool_use 프로토콜
- Turn 1: LLM → tool_use block 요청
- Turn 2: Executor → MCP 호출
- Turn 3: tool_result를 user role로 messages에 추가
- Turn 4: LLM → end_turn (stop_reason)

### stop_reason
- `end_turn`: 정상 종료
- `tool_use`: tool 호출 요청
- `max_tokens`: truncation (Planner에서 retry 안전장치로 대응)

### Self-correction
- MCP tool이 `{"type": "GuardViolation"}` 반환
- Executor가 tool_result에 `is_error=True` 플래그 포함해 LLM에 전달
- LLM이 에러 메시지 읽고 쿼리 수정해 재시도 (최대 2회)

### INTEGER → BIGINT 교훈
- `monthly_premium`, `annual_premium`, `sum_insured`, `amount` 전부 BIGINT
- 원칙: "돈은 의심 없이 BIGINT"
- VIEW 의존성으로 ALTER 막힘 → DROP VIEW → ALTER → CREATE VIEW 트랜잭션 패턴

### checks.py vs Agent 유지율 정의 차이
- checks.py: `status='active' / COUNT(*)`
- Agent: `premium_payments_v`의 `payment_month_seq` 기반
- 두 방식이 다른 수치를 냄 → known-limitations.md에 문서화 대상

---

## 14. Out of Scope (명시적 제외)

- 실제 한화생명 API 연동 (면접 전 단계이므로)
- 실데이터 혼용 (합성 100%)
- OAuth·사용자 관리 (PoC 불필요)
- 멀티 LLM 제공자 (Anthropic 단일)
- Kubernetes·CI/CD (Railway로 충분)

---

## 15. 외부 이해관계자

- **4-AI 교차검증 보드**: ChatGPT / Gemini / Perplexity / Claude (별도 세션)
  - ADR-002, ADR-003, 골든셋 v3에서 활용
  - 원문: `docs/research/`
- 인간 이해관계자: 없음 (솔로 프로젝트)

---

## 16. 지금 상태 파악 방법 (매 세션 시작)

**이 문서에는 "오늘 무엇이 완료됐나"를 박지 않는다.** 매번 달라지므로
suri-bridge 도구로 실시간 조회.

### 세션 시작 프로토콜
1. `suri-bridge:session_context` 호출 — 핵심 문서 13개 일괄 로드
2. 마지막 세션 transcript 확인 (사용자가 붙여주거나 `/mnt/transcripts` 참조)
3. 필요 시 `git log --oneline -10`으로 최근 커밋 확인
4. 필요 시 `suri-bridge:file_read`로 특정 파일 점검

### 상태 변경 시 동기화
코드 수정했으면:
- `prompts.py`, `base.py` 등 코드 파일 변경은 네가 직접 실행
- `docs/*.md`는 `suri-bridge:docs_write`로 Claude가 직접 작성 가능
- 커밋은 한 줄 제목 원칙 (긴 `-m` 메시지는 zsh heredoc 에러 위험)

### 무엇을 수정 중인지 명시
세션 시작 시 사용자가 "지금 D-몇, 무엇을 하는 중" 한 줄 컨텍스트 주면
가장 빠름. 예:
> "D-6 오전. C1 재실행으로 새 CRITIC 프롬프트 검증하려고."
