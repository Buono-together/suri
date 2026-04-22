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
from dotenv import load_dotenv

from anthropic import Anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


# =============================================================
# 환경 로드
# =============================================================

load_dotenv(".env")


# =============================================================
# 상수
# =============================================================

# Anthropic 모델 (ADR-003)
MODEL_NAME = "claude-sonnet-4-6"

# 공통 LLM 설정
MAX_TOKENS_PLANNER = 800
MAX_TOKENS_EXECUTOR = 1500
MAX_TOKENS_CRITIC = 600

# 자가교정 재시도 한계 (ADR-003)
MAX_GUARD_RETRIES = 2

# MCP 서버 실행 방식
# uv run python -m app.mcp_server.server 로 서버 기동
# stdio_client가 이 명령을 subprocess로 띄우고 파이프 통신
SERVER_PARAMS = StdioServerParameters(
    command="uv",
    args=["run", "python", "-m", "app.mcp_server.server"],
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