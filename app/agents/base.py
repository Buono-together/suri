"""
Agent Base — Shared resources for Planner / Executor / Critic.

Responsibilities:
- Anthropic client singleton
- MCP server connection params
- MCP tool discovery + invocation helpers

MCP connection pattern:
- Each tool call opens a new stdio session (PoC simplicity).
- In production, session pooling would be introduced here.
"""
from __future__ import annotations

import os
import sys
from dotenv import load_dotenv

from anthropic import Anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


# =============================================================
# 환경 로드
# =============================================================

load_dotenv(".env")


# =============================================================
# 상수 / 모델 선택
# =============================================================
#
# ADR-003 원칙: Executor 는 SQL 생성의 핵심이므로 반드시 Sonnet 유지.
# Planner / Critic 은 비용 효율을 위해 Haiku 이관 가능성이 있으므로
# 각 에이전트별로 환경변수로 교체 가능하게 둔다.
#
# 환경변수 미설정 시 기본값은 Sonnet 4.6 (backward compatible).

_DEFAULT_MODEL = "claude-sonnet-4-6"

# 공통 레거시 상수 — 외부 모듈 import 호환용 (Executor 가 참조).
MODEL_NAME = os.environ.get("SURI_MODEL", _DEFAULT_MODEL)

# Agent 별 모델 — 이관 실측 테스트 또는 비용 최적화 시 env 로 교체.
PLANNER_MODEL = os.environ.get("SURI_PLANNER_MODEL", _DEFAULT_MODEL)
EXECUTOR_MODEL = os.environ.get("SURI_EXECUTOR_MODEL", _DEFAULT_MODEL)
CRITIC_MODEL = os.environ.get("SURI_CRITIC_MODEL", _DEFAULT_MODEL)

# 공통 LLM 설정
MAX_TOKENS_PLANNER = 1500   # v3 복잡 질문 대응 (800은 부족)
MAX_TOKENS_EXECUTOR = 4000  # tool_use block + CTE SQL + 다회 describe_table 누적 대응
MAX_TOKENS_CRITIC = 800     # 도메인 해석 포함 시 여유

# 자가교정 재시도 한계 (ADR-003)
MAX_GUARD_RETRIES = 2

# MCP 서버 실행 방식 — stdio_client 가 subprocess 로 띄워 파이프 통신.
# - command: sys.executable 로 현재 프로세스의 Python 바이너리 직접 호출
#   (로컬 venv · Railway nixpacks 양쪽 모두 동일하게 해결).
# - env: os.environ 명시 전달. StdioServerParameters 는 env 를 지정하지
#   않으면 subprocess 에 부모 환경을 상속하지 않을 수 있어 Railway 에서
#   POSTGRES_HOST 등이 유실돼 localhost fallback 이 발생하는 것을 차단.
SERVER_PARAMS = StdioServerParameters(
    command=sys.executable,
    args=["-m", "app.mcp_server.server"],
    env=dict(os.environ),
)


# =============================================================
# Anthropic Client (singleton)
# =============================================================

_anthropic_client: Anthropic | None = None


def get_anthropic_client() -> Anthropic:
    """Anthropic 클라이언트 싱글톤."""
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = Anthropic()
    return _anthropic_client


# =============================================================
# MCP Helpers
# =============================================================

async def list_mcp_tools() -> list[dict]:
    """
    MCP 서버의 tool 스키마를 Anthropic tools 포맷으로 변환.

    Returns:
        [{"name": ..., "description": ..., "input_schema": ...}, ...]
    """
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_response = await session.list_tools()
            return [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.inputSchema,
                }
                for t in tools_response.tools
            ]


async def call_mcp_tool(tool_name: str, tool_input: dict) -> str:
    """
    MCP tool 1회 호출. 새 stdio session을 연다.

    Returns:
        Tool이 반환한 text content (JSON 문자열 예상)
    """
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, tool_input)
            # content는 TextContent 객체의 리스트 — 우리는 첫 번째 text만 사용
            if not result.content:
                return "{}"
            first = result.content[0]
            return getattr(first, "text", str(first))

# =============================================================
# Prompt caching helper
# =============================================================

def cached_system(system_text: str) -> list[dict]:
    """
    Wrap system prompt with ephemeral cache_control.
    
    Anthropic prompt caching: 5-min TTL.
    - Cache write: 1.25x normal input cost
    - Cache read: 0.1x normal input cost (90% discount)
    
    For our use case (3 agents sharing similar system prompts,
    many repeated calls during testing), this saves ~70-90% on input cost.
    """
    return [
        {
            "type": "text",
            "text": system_text,
            "cache_control": {"type": "ephemeral"},
        }
    ]