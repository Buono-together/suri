실제 현황 확인부터 하겠습니다 — fastmcp가 공식 SDK에 통합됐다는 소식이 있었는데 2026년 4월 기준 관계가 어떻게 정리됐는지가 이 결정의 핵심입니다.중요한 발견이 있습니다. 유저의 옵션 A/B 프레이밍 자체가 현재 상황과 맞지 않습니다. 추가 확인하겠습니다.# MCP 서버 구현 선택 — SURI PoC 관점

## ⚠️ 먼저 프레이밍 교정이 필요합니다

리서치 결과, 유저의 옵션 A/B 프레이밍이 **현재 MCP 생태계 구조와 맞지 않습니다**. 이 부분을 바로잡지 않으면 최종 결정이 틀린 전제 위에 올라갑니다.

**핵심 사실:**
- FastMCP 1.0은 2024년에 공식 MCP Python SDK로 편입되었고, FastMCP의 독립 프로젝트(현재 2.x/3.x)는 하루 100만 다운로드로 전체 MCP 서버의 70%를 차지한다
- 공식 `mcp` SDK 안에 **`mcp.server.fastmcp.FastMCP` 클래스가 이미 존재**하며, `@mcp.tool()`, `@mcp.resource()`, `@mcp.prompt()` 데코레이터 문법을 그대로 지원
- 독립 `fastmcp` 2.x는 이후 분기된 프로젝트로, GitHub 이슈에서도 "둘이 sync로 갈 건지 fork된 상태인지" 공식 질의가 오픈되어 있으며 효과적으로 fork된 상태
- jlowin의 fastmcp는 현재 **PrefectHQ로 이관**되어 더 이상 "1인 프로젝트"가 아님 (`github.com/PrefectHQ/fastmcp`)

즉, 선택지는 2개가 아니라 **3개**입니다:

| 옵션 | import 경로 | 정체 | 유저 프레이밍의 위치 |
|---|---|---|---|
| **A1** | `from mcp.server.lowlevel import Server` | 저수준 raw 프로토콜 API | 유저의 "옵션 A" 예시 코드 |
| **A2** | `from mcp.server.fastmcp import FastMCP` | **공식 SDK에 편입된 FastMCP 1.0** | 유저의 프레이밍에 누락됨 |
| **B** | `from fastmcp import FastMCP` | PrefectHQ의 독립 fastmcp 2.x/3.x | 유저의 "옵션 B" |

**A2의 발견이 게임 체인저입니다.** 유저의 Option B 예시 코드는 단 한 줄(`from fastmcp import FastMCP` → `from mcp.server.fastmcp import FastMCP`)만 바꾸면 **공식 SDK 안에서 그대로 작동**합니다. 공식성과 생산성을 모두 얻을 수 있다는 뜻입니다.

---

## 6개 축 비교 (3-way)

| 축 | A1: lowlevel Server | **A2: mcp.server.fastmcp** | B: PrefectHQ fastmcp |
|---|---|---|---|
| **1. 금융권 면접 시그널** | ○ "공식" | **◎ "공식 + 실용"** | △ "왜 서드파티?" 질문 발생 |
| **2. 프로덕션 이관 OSS 심사** | ◎ 의존성 최소 | **◎ 의존성 최소 (동일 패키지)** | △ 추가 심사 대상 1건 |
| **3. 유지보수 리스크** | ◎ Anthropic 전담 | **◎ Anthropic 전담** | ○ PrefectHQ 전담 (1인 아님) |
| **4. 스펙 변경 대응** | ◎ 즉시 | **○ 동일 릴리스 사이클** | △ 한 층 lag 가능 |
| **5. 디버깅 투명성** | ◎ 직접 | **○ 얇은 래퍼** | △ 두 층 래핑 |
| **6. 7일 PoC ROI** | ✗ boilerplate ~30줄/tool | **◎ ~5줄/tool** | ◎ ~5줄/tool (동일) |

**A2가 A1·B 양쪽의 장점을 대부분 흡수하는 구조**입니다. B가 A2 대비 갖는 유일한 추가 가치는 최신 2.x/3.x 기능(Proxy, Composition, Auth integrations)인데, SURI의 MVP 범위(tool 1~3개)에서는 **사용할 일이 없는 기능들**입니다.

---

## 금융권 특화 관점 (한화생명 컨텍스트)

### 망분리·OSS 반입 심사
대기업 금융사의 사내 개발망 OSS 반입 심사는 통상 **"직접 의존성(top-level)"을 개별 심사**합니다. `fastmcp` (B)를 쓰면 심사 대상이 `mcp` + `fastmcp` 두 건이 되고, `fastmcp`는 다시 `mcp`를 내부 의존합니다. A2는 **`mcp` 하나**로 끝납니다. 실무 관점에서 심사 리드타임 차이는 작지 않습니다.

### 개인정보보호법·DLP와의 관계
MCP 라이브러리 선택 자체가 개보법이나 DLP와 직접 충돌하지는 않습니다. 다만 **"3층 방어의 Layer 1 구현이 공식 SDK 위에 있다"**는 서사가 감사·심사 문서에서 간결합니다. B를 쓰면 *"Layer 1은 Apache 2.0 커뮤니티 래퍼(PrefectHQ 관리) 기반, 이는 내부 MIT 라이선스 공식 SDK를 wrap한 구조로..."* 같은 추가 설명이 감사 문서에 들어갑니다. 작은 차이지만 누적됩니다.

### 면접 질문 프레임
한화생명 Data Agent Developer 면접관이 물을 가능성 높은 순서:
1. *"MCP를 왜 썼나요?"* — 누구나 같은 답
2. *"어느 라이브러리로 구현했나요?"* — **여기서 A2가 가장 깔끔한 답을 만든다**
3. *"Layer 1에서 실제로 무엇을 차단하나요?"* — 핵심 시연

(2) 답이 *"공식 SDK의 FastMCP 클래스"*이면 *"왜 공식을 택했나?"* 와 *"왜 생산성을 포기했나?"* 두 질문이 동시에 방어됩니다. B는 앞의 질문을, A1은 뒤의 질문을 각각 추가로 받게 됩니다.

---

## 최종 권장: **옵션 A2** (`mcp.server.fastmcp.FastMCP`)

**근거 3줄:**
1. **공식성과 생산성의 False Dilemma를 없앤다** — A2는 Anthropic 공식 SDK 패키지(`mcp`) 안에 포함된 FastMCP 1.0이므로, 유저의 옵션 B 예시 코드를 거의 그대로 쓰면서도 "공식 SDK 직접 사용" 타이틀을 유지한다.
2. **금융권 OSS 심사·감사 문서에서 의존성·라이선스 서사가 단일 라인으로 끝난다** — `mcp` (MIT, Anthropic) 하나. B는 `mcp` + `fastmcp` (Apache 2.0, PrefectHQ) 두 건의 심사 대상을 만든다.
3. **SURI의 실제 차별화 포인트는 MCP 프레임워크가 아니라 3층 방어**다. Layer 1 구현체 선택에서 절약한 시간과 인지 대역폭을 SQL AST 파서와 거버넌스 시연 리허설에 투자하는 것이 면접 ROI 최대.

---

## 코드 스켈레톤 (A2 기준)

```python
# suri_mcp/server.py
from mcp.server.fastmcp import FastMCP
from .guards import SqlGuard  # Layer 1: AST 기반 SELECT-only, 원본 customers 차단
from .db import ReadOnlyConnection  # suri_readonly ROLE로만 연결

mcp = FastMCP("suri-mcp")
guard = SqlGuard(blocked_tables={"customers"}, allowed_verbs={"SELECT"})

@mcp.tool()
def execute_readonly_sql(query: str) -> str:
    """Execute read-only SQL against SURI insurance DB.
    
    Blocks direct access to customers table (PII).
    Use customers_safe view for masked customer data.
    """
    guard.check(query)  # raises GuardViolation → returned to Agent as error
    with ReadOnlyConnection() as conn:
        return conn.execute_to_json(query)

@mcp.tool()
def describe_schema(table: str) -> str:
    """Return column names/types for an allowed table or view."""
    ...

if __name__ == "__main__":
    mcp.run()  # stdio transport
```

**타입 힌트 → JSON 스키마 자동 생성, docstring → tool description**. 이게 3-Agent의 Planner가 tool을 올바르게 호출하는 맥락이 됩니다. boilerplate가 없어서 Guard 로직 자체에 시선이 집중되는 점이 중요합니다.

---

## 면접 방어 답변 템플릿

### Q: "왜 공식 SDK를 선택했나요?"
> "SURI는 대기업 금융권 프로덕션 이관을 전제로 한 PoC였습니다. Anthropic이 직접 유지하는 `mcp` 패키지는 MCP 스펙 변경 대응 lag이 없고, 사내 OSS 심사에서 직접 의존성이 하나로 끝난다는 이점이 있어 선택했습니다. 다만 저수준 Server API는 tool 하나당 30줄 boilerplate가 나와서, **공식 SDK 안에 편입된 FastMCP 1.0**(`mcp.server.fastmcp.FastMCP`)을 썼습니다. 데코레이터와 타입 힌트 기반 스키마 자동 생성을 활용해 핵심 로직인 SQL Guard에 집중할 수 있었습니다."

### Q: "PrefectHQ의 standalone fastmcp 2.x는 왜 안 썼나요?"
> "2.x/3.x의 추가 기능(Proxy, Composition, OAuth integration)은 유용하지만 SURI MVP 범위에서는 쓰지 않는 기능입니다. 반면 Apache 2.0 서드파티 의존성은 사내 OSS 심사 건을 하나 추가하고, 감사 문서에 '커뮤니티 래퍼를 통한 간접 사용' 서사를 만듭니다. 3층 방어 거버넌스를 핵심으로 하는 이 PoC의 톤과 맞지 않다고 판단했습니다. 만약 Proxy나 Composition이 필요한 규모로 커지면 그 시점에 `fastmcp` 2.x로 이관하는 것도 경로상 어렵지 않습니다 — 데코레이터 API가 거의 동일하기 때문입니다."

### Q: "MCP 대신 그냥 function calling 썼으면 되지 않나?"
> "가능하지만 SURI의 핵심은 'Application layer에서 PII를 차단하는 거버넌스'입니다. MCP로 tool 경계를 명시적 프로토콜로 분리하면 Guard 로직이 Agent 구현체로부터 독립되어, 나중에 Claude 외 다른 LLM으로 교체해도 거버넌스 층이 그대로 유지됩니다. 이게 면접 기획서의 '3층 방어'에서 Layer 1의 구조적 의미입니다."

---

## 현재 계획(fastmcp 선호) 평가: **Modify**

유저의 *"생산성을 위해 fastmcp를 쓰고 싶다"*는 직관은 정확합니다. 문제는 그 직관을 만족시키는 선택지가 옵션 B만 있다고 오해한 점입니다.

- **Rewrite 아님**: 이미 작성된 유저의 Option B 예시 코드는 import 한 줄만 바꾸면 A2로 완전 이전됩니다. 1분 작업.
- **Go 아님**: 지금 그대로 B로 가면 면접에서 *"왜 공식 SDK를 직접 안 썼나"* 질문에 *"생산성 때문"* 이라는 답을 해야 하는데, 그 답은 A2가 이미 존재한다는 사실 앞에서 약해집니다.
- **Modify**: `from fastmcp import FastMCP` → `from mcp.server.fastmcp import FastMCP` + `pyproject.toml`에서 `fastmcp` 제거 + `mcp>=1.18.0` 추가. 이것으로 *"공식을 썼는데 생산성도 잡았다"*라는 강한 메시지가 동시에 성립합니다.

---

## 부가 권장 사항

- **Pin 버전**: `mcp>=1.18.0,<2.0.0`. `mcp>=1.18.0`이 현재 MCP 스펙 2025-06-18을 지원하는 최소 버전. 2.0이 나올 때 breaking change 가능성이 있으므로 상한 고정.
- **SKILL.md에 명시**: `/docs/architecture/mcp-layer.md`에 *"공식 mcp SDK 내부의 FastMCP 클래스 사용. 서드파티 fastmcp 2.x는 사용하지 않음. 이유: OSS 심사 단일화 + 스펙 대응 즉시성"* 1문단 고정. 면접 시 화면 공유로 바로 보여주기 좋습니다.
- **대안 경로 기록**: 향후 Layer 1이 더 복잡해지면(예: multi-server composition, OAuth) PrefectHQ fastmcp 2.x로 migrate하는 경로가 열려있다는 점을 `docs/decisions/001-mcp-library.md` ADR로 남기면, 면접에서 "장기 로드맵 사고"까지 증명할 수 있습니다.