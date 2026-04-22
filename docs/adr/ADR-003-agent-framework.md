# ADR-003: Agent Orchestration Framework 선택

**상태**: Accepted  
**작성일**: 2026-04-22 (D-7)  
**컨텍스트**: SURI 3-Agent (Planner / Executor / Critic) 구현 시 프레임워크 선택

---

## 공통 서문 (ADR-001~003 관통 원칙)

SURI는 모든 레이어에서 **의존성 최소화**와 **동작 명시성**을 우선한다.
이는 PoC → Production 이관 시 변경 surface를 최소화하고, 각 계층의
책임 경계를 감사 문서에서 단선적으로 기술할 수 있게 하기 위함이다.

- ADR-001: 데이터 레이어 — 합성 데이터 (통제·재현성 우선)
- ADR-002: 프로토콜 레이어 — 공식 MCP SDK (의존성 최소·공식성)
- ADR-003: 오케스트레이션 레이어 — 본 문서

---

## Context

SURI의 3-Agent 구조(Planner / Executor / Critic)를 구현하는 방법을 결정해야 한다.

### 제약 조건

- **9일 타임박스**: D-6까지 3-Agent E2E 1회 성공 (D-5 체크포인트)
- **ADR-002 철학 연속성**: 의존성 최소화, 공식성, 통제력
- **JD 정합**: "Agent 프레임워크를 활용한 Agent E2E 개발 역량", 
  "Multi-Agent 구조 설계", "상용모델 API/MCP 연동"
- **부서 문화**: 3개 JD 공통 언어 — 표준화, 규제, 점진 배포, 롤백, 모니터링

### 이미 결정된 사항

- MCP 서버: `mcp.server.fastmcp.FastMCP`로 구현 완료 (ADR-002)
- MCP Inspector로 프로토콜 레벨 검증 완료
- Tool 1개 (`execute_readonly_sql`)는 is_error 피드백 패턴 지원

---

## Decision

**공식 `mcp` SDK Client + Anthropic SDK 직접 구성** (Option C)

- Agent 간 상태 전이: 명령형 Python 함수 호출 체인
- MCP tool 호출: `mcp.client.stdio.stdio_client` + `ClientSession`
- 자가교정 루프: Executor 내부 `while` 루프 (최대 2회 재시도)
- GuardViolation 피드백: `is_error=True` 플래그로 Agent에게 전달

---

## Considered Options

### Option A: Anthropic SDK 직접 + MCP tool Python 함수 직접 import

- 구성: `anthropic` 1개 패키지 + `from app.mcp_server.server import execute_readonly_sql`
- 장점: 구현 가장 단순 (1~1.5시간)
- 단점:
  - **MCP 프로토콜을 실제로 거치지 않음** — 서버가 "장식용"이 됨
  - 면접 방어 취약: "MCP Inspector로 검증까지 했는데 왜 Agent는 함수 import?"
  - ADR-002에서 공식 MCP SDK 채택한 의미가 퇴색

### Option B: LangChain + LangGraph + langchain-mcp-adapters

- 구성: 4개 패키지 (`langgraph`, `langchain-anthropic`, `langchain-mcp-adapters`, `langchain-core`)
- 장점:
  - `StateGraph`의 `conditional_edges`로 자가교정 선언적 표현
  - `MemorySaver`, `LangSmith` 등 운영 기능 풍부
  - 업계 표준 프레임워크
- 단점:
  - **의존성 4개 추가** — ADR-001·002의 "의존성 최소화" 철학 단절
  - `langchain-mcp-adapters`는 공식 `mcp` SDK를 내부에서 wrap하는 추가 레이어 — MCP 경계가 프레임워크 뒤로 숨음
  - 우리 3-node 선형 flow에선 LangGraph 장점 대부분 미사용 (checkpointing, durable execution, human-in-the-loop 등)
  - 금융권 망분리 환경에서 LangChain 생태계 OSS 심사 surface 증가
  - LangSmith는 외부 SaaS → 망분리 시 대체재 결정 필요

### Option C: 공식 `mcp` SDK Client + Anthropic SDK 직접 구성 ✅

- 구성: 2개 패키지 (`mcp`, `anthropic`)
- 장점:
  - **ADR-002 철학 직접 연속** — 공식 SDK, 의존성 최소
  - **MCP 프로토콜 E2E 실제 사용** — stdio transport 경유
  - 3층 PII 방어 구조가 코드 레벨에서 투명 (MCP 호출 → Guard → DB)
  - 자가교정 로직이 `is_error=True` 플래그로 명시적
  - 오케스트레이션 레이어 직접 구성 → "Multi-Agent 구조 설계" 증거
- 단점:
  - `conditional_edges` 대비 자가교정 코드 5~10줄 더 필요
  - LangGraph 특유의 운영 기능(checkpointing 등)은 직접 구현 필요 시 추가 작업

---

## Rationale

### 1. ADR-001·002와의 서사 관통

세 ADR이 하나의 문장으로 관통해야 면접 서사가 일관됨:

> "데이터는 합성으로 통제하고, 프로토콜은 공식 SDK를 직접 쓰며, 
> 오케스트레이션은 순수 Python으로 구성한다. 모든 레이어에서 
> 의존성 최소화와 동작 명시성을 우선함으로써 PoC → Production 
> 이관 시 변경 surface를 최소화한다."

Option B는 이 문장을 깨뜨린다. Option C는 그대로 유지한다.

### 2. 부서 3개 JD 공통 언어와의 정합

Data Agent Developer, Product Manager, Technical Program Manager 세 JD의
공통 어휘: 표준화 · 운영 체계 · 규제 · 점진 배포 · 체크포인트 · 롤백 · 모니터링.

이 어휘는 "프레임워크 사용자"보다 **"사내 통제 가능한 구조 설계자"**를 
선호한다는 시그널. Option C는 이 시그널과 정합한다.

### 3. 신기술 PoC 검증 능력 증명

MCP는 2026년 현재 adoption 초기 단계 (OpenAI/Google 2025년 채택).
부서 JD가 명시한 "신기술, 핵심 유스케이스 기반 PoC 추진"의 본질은
**프로토콜을 직접 다뤄본 경험**. `langchain-mcp-adapters` 뒤에 숨으면
"검증했다"가 아니라 "통합했다"가 된다.

### 4. 면접 시연 임팩트

15분 시연에서 면접관이 "SQL Guard 차단 시 Agent는?"이라고 물을 때,
Option C는 `if is_error:` 구문과 프롬프트 히스토리 재주입 5줄을
**1 hop으로** 보여줄 수 있다. Option B는 LangGraph 노드·엣지·state
통과 경로를 **2+ hop으로** 설명해야 한다.

### 5. 10년+ 멀티커리어 지원자의 차별화 축

전통적 SWE 이력이 없는 상황에서 "LangGraph 튜토리얼 따라했다"는
경쟁 지원자(신입~3년차 SWE) 대비 차별화가 약함. 반면
"프로토콜을 직접 다루고 Multi-Agent 오케스트레이션을 순수 Python으로
설계했다"는 **경험의 깊이**를 증명.

---

## Consequences

### 긍정적 결과

- ADR 3개가 하나의 철학으로 관통 — 면접 서사 일관성
- MCP 프로토콜 E2E 검증 이력 확보
- 의존성 2개 유지 — 금융권 OSS 심사 surface 최소
- 3층 PII 방어의 각 레이어가 코드에서 직접 관찰 가능

### 트레이드오프

- **포기한 것**: LangGraph의 prebuilt 패턴 (ReAct, plan-and-execute),
  MemorySaver 기반 checkpointing, LangSmith tracing
- **직접 구현 필요**: 자가교정 루프 (최대 2회 재시도), 상태 전달
  (dict 기반), 로깅 (JSONL)
- **3-Agent 초과 확장 시**: 복잡한 상태 머신이 필요해지면 자체
  state machine 또는 LangGraph 도입 재검토 필요

### 운영 고려사항

- stdin/stdout 기반 MCP 통신 — 프로덕션에서는 컨테이너화 필요
- 재시도 제한 (2회) 초과 시 Executor가 에러 상태 반환 → Critic이
  "접근 제한으로 답변 불가" 형태로 종료
- MCP Client 연결을 매 호출마다 새로 생성 (D-6 PoC 수준). 프로덕션
  이관 시 연결 풀링 또는 session 재사용 검토

---

## Migration Path

규모 확장 시 LangGraph 도입 경로:

1. **MCP Client 레이어는 그대로 유지** — 공식 `mcp.client.stdio`
2. **Orchestration 레이어만 교체** — Python 함수 체인 → LangGraph StateGraph
3. **Migration cost 최소**: MCP tool 스키마는 프로토콜 표준이라
   `langchain-mcp-adapters`가 자동 변환

즉 Option C 선택은 **미래의 Option B 전환을 차단하지 않는다**. 반대로
Option B에서 시작하면 LangChain 추상화 해제가 훨씬 어려움.

---

## 면접 방어 답변

### Q: Agent 프레임워크 경험이 없는 것 아닌가요?

"LangGraph, CrewAI, LlamaIndex 같은 주요 프레임워크의 구조와 장점은
학습했고 이번 PoC에서 Option B로 검토도 했습니다. 다만 3-Agent 선형
파이프라인이라는 복잡도에서 프레임워크 이점보다 의존성 추가 비용이
더 컸고, ADR-002에서 확립한 '의존성 최소화' 철학을 Agent 레이어에서도
일관되게 적용했습니다. 프레임워크 **사용자**가 아닌 **설계자** 시그널을
우선한 선택이었습니다."

### Q: LangChain 왜 안 썼나요?

"LangChain은 상태 지속성·장기 실행·human-in-the-loop가 필요한 복잡한
운영형 Agent에 적합하다고 판단했습니다. 본 PoC의 3-Agent 흐름은
선형·단기 실행이며 핵심 검증 포인트가 MCP 거버넌스이므로 공식 MCP
Client + 명시적 오케스트레이션을 선택했습니다. 다만 규모가 커지면
MCP Client 레이어는 유지한 채 오케스트레이션만 LangGraph로 교체하는
마이그레이션 경로를 열어두었습니다."

### Q: 프로덕션 이관 시 가장 큰 갭은?

"세 가지입니다. (1) stdin/stdout 기반 프로세스 통신을 망분리 환경의
컨테이너로 이관, (2) `suri_readonly` ROLE의 실제 운영 DB 매핑 및
secret manager 연동, (3) OpenTelemetry 기반 tracing 추가. Option B로
갔다면 여기에 'LangChain 사내 OSS 심사 + LangSmith 대체재 결정'이
추가되었을 겁니다."

---

## References

- 4-AI cross-validation research: `docs/research/agent-framework/01~04.md`
- ADR-001: 합성 데이터 채택
- ADR-002: MCP 라이브러리 선택 (`mcp.server.fastmcp.FastMCP`)
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk
- Anthropic Messages API + Tool Use: https://docs.anthropic.com/en/docs/agents-and-tools/tool-use
