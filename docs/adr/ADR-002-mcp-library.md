# ADR-002: MCP 서버 라이브러리 선택

**Status**: Accepted
**Date**: 2026-04-22
**Context**: SURI PoC, D-7

## Context

SURI의 Layer 1(Application)은 MCP 서버로 구현한다. `execute_readonly_sql`
tool 1개를 중심으로 3-Agent가 PostgreSQL에 접근하는 유일한 경로가 된다.

MCP Python 구현체 선택 시 초기 프레이밍은 2개 옵션이었다:
- 공식 `mcp` SDK (저수준 `Server` 클래스)
- 독립 `fastmcp` 2.x (PrefectHQ 유지, Apache 2.0)

그러나 4개 AI 교차검증 + 웹 검색 교차검증 결과 **프레이밍 자체가
사실과 달랐다**. 실제 선택지는 3개:

| 옵션 | import | 정체 |
|---|---|---|
| A1 | `from mcp.server.lowlevel import Server` | 저수준 raw API |
| **A2** | `from mcp.server.fastmcp import FastMCP` | **공식 SDK 내부의 FastMCP 1.0** |
| B  | `from fastmcp import FastMCP` | 독립 fastmcp 2.x/3.x (PrefectHQ) |

**핵심 사실** (pypi.org/project/mcp, modelcontextprotocol.github.io/python-sdk,
PrefectHQ/fastmcp README 교차 확인):
- FastMCP 1.0이 2024년에 공식 MCP Python SDK로 편입됨
- 현재 `mcp` 패키지 안에 `mcp.server.fastmcp.FastMCP` 클래스가 존재
- `@mcp.tool()` 데코레이터 + 타입 힌트 기반 스키마 자동 생성 지원
- 독립 fastmcp 2.x/3.x는 이후 분기된 별도 프로젝트

즉 A2는 공식성(A1의 장점)과 생산성(B의 장점)을 모두 갖는다.

## Decision

**A2 채택**: `from mcp.server.fastmcp import FastMCP`

## Rationale

### 1. 금융권 OSS 심사 단일화
사내 망분리 환경에서 오픈소스 반입 심사는 직접 의존성을 개별 검토한다.
- A1: `mcp` (MIT, Anthropic) 1건
- **A2: `mcp` (MIT, Anthropic) 1건**
- B:  `mcp` + `fastmcp` (Apache 2.0, PrefectHQ) 2건

A2는 공식 SDK 1건으로 심사 대상이 단일화되며, 감사 문서에서
"Apache 2.0 커뮤니티 래퍼를 통한 간접 사용" 같은 추가 서사가 불필요하다.

### 2. 생산성
Tool 1~3개 규모에서 A1의 boilerplate(~30줄/tool)는 핵심 로직(SQL Guard)을
가린다. A2는 데코레이터 + 타입 힌트로 ~5줄/tool, 코드 읽기 시 거버넌스
로직에 즉시 집중 가능.

### 3. 장기 유지보수
A2는 Anthropic이 전담 유지한다. MCP 스펙 변경 시 즉시 반영되며, 6~12개월
포트폴리오 재사용 시 버전 lag 리스크 없음.

### 4. 디버깅 투명성
A2는 `mcp` 패키지 내부에 있어 콜스택이 공식 구현 내에서 끝난다.
"Layer 1에서 장애 발생 시 책임 추적 가능"이라는 금융권 요구에 부합.

### 5. 면접 방어력
"공식 SDK의 FastMCP 클래스 사용. 1.0이 2024년 공식 편입되어 래퍼
의존성 없이 동일한 생산성 얻음" → "왜 공식을 선택했나?"와 "왜 생산성을
포기했나?" 두 질문 동시 방어.

## Consequences

### Positive
- 단일 의존성 (`mcp[cli]`) → 사내 이관 심사 간소화
- 데코레이터 + 타입 힌트로 `execute_readonly_sql` Guard 로직에 집중
- MCP 스펙 업데이트 즉시 대응
- Tool 수가 늘어도 동일 패턴 확장 가능

### Negative
- 독립 fastmcp 2.x의 고급 기능(Proxy, Composition, OAuth) 비사용
  → SURI MVP 범위에 불필요하므로 실질 손실 없음
- 향후 이 기능이 필요해지면 fastmcp 2.x로 마이그레이션 경로 존재
  (import 한 줄만 변경, 데코레이터 API 거의 동일)

## Alternatives Considered

### A1: 저수준 `Server` 클래스
- **Pros**: 프로토콜 내부 노출, 최대 제어권
- **Cons**: Tool당 30줄 boilerplate, 핵심 로직 가림, PoC 타임박스 부적합

### B: 독립 fastmcp 2.x
- **Pros**: Proxy/Composition/OAuth 등 고급 기능
- **Cons**: 의존성 2건, 금융권 심사 추가 건, 스펙 대응 lag 가능
- 기각 이유: MVP 범위에서 고급 기능 불필요. A2가 동일 생산성 제공.

## References

- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk
- MCP Python SDK PyPI: https://pypi.org/project/mcp/
- FastMCP (PrefectHQ): https://github.com/PrefectHQ/fastmcp
- MCP Spec: https://modelcontextprotocol.io/specification
- 금융보안원 오픈소스 활용 안내서:
  https://www.fsec.or.kr/bbs/detail?bbsNo=11166&menuNo=222

## Cross-validation

4개 AI 리서치 + 웹 검색 교차검증 (2026-04-22):
- ChatGPT: A1 추천 (A2 존재 인지 못함)
- Gemini: B 유지 (A2 존재 인지 못함)
- Claude: **A2 추천** (정확한 프레이밍)
- Web search: A2 존재 및 권장성 확인
  - pypi.org/project/mcp 공식 예시 코드가 `mcp.server.fastmcp.FastMCP` 사용
  - PrefectHQ/fastmcp README "FastMCP 1.0 was incorporated into the
    official MCP Python SDK in 2024" 명시

`docs/research/mcp-library/` 폴더에 4개 AI 답변 원문 보관.
