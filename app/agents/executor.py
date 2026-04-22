"""
Executor Agent — Plan → SQL → MCP tool call, with self-correction.

Uses Anthropic tool_use protocol.
Calls MCP server via stdio (see base.call_mcp_tool).

Self-correction: GuardViolation / DBExecutionError is passed back to
the LLM with is_error=True, allowing the LLM to retry (up to MAX_GUARD_RETRIES).
"""
from __future__ import annotations

import json
import logging

from .base import (
    get_anthropic_client,
    list_mcp_tools,
    call_mcp_tool,
    MODEL_NAME,
    MAX_TOKENS_EXECUTOR,
    MAX_GUARD_RETRIES,
)
from .prompts import EXECUTOR_SYSTEM
from .planner import Plan


logger = logging.getLogger("suri.executor")


class ExecutorError(RuntimeError):
    """Raised when executor fails after retries."""
    pass


async def execute(plan: Plan) -> dict:
    """
    Execute the plan by generating SQL and calling MCP tool.

    Returns the MCP tool's final result dict, e.g.:
        {"columns": [...], "rows": [...], "row_count": N, "truncated": False}

    Or if Guard/DB errors persist beyond retries:
        {"error": "...", "type": "GuardViolation" | "DBExecutionError"}

    Raises ExecutorError only on fundamental failures (LLM errors, etc.).
    """
    client = get_anthropic_client()

    # MCP 서버에서 tool 스키마 조회 (매번 하는 이유: PoC 단순성)
    tools = await list_mcp_tools()
    logger.info("Loaded %d MCP tool(s)", len(tools))

    # 초기 메시지: Plan을 user content로 전달
    messages = [
        {
            "role": "user",
            "content": (
                "Execute this analysis plan by generating a SQL query "
                "and calling the execute_readonly_sql tool.\n\n"
                f"Plan:\n{json.dumps(plan.to_dict(), ensure_ascii=False, indent=2)}"
            ),
        }
    ]

    # tool_use 루프
    guard_retries = 0
    last_tool_result_text: str | None = None

    for iteration in range(MAX_GUARD_RETRIES + 2):  # 여유 iteration
        logger.info("Executor iteration %d (guard_retries=%d)",
                    iteration + 1, guard_retries)

        response = client.messages.create(
            model=MODEL_NAME,
            max_tokens=MAX_TOKENS_EXECUTOR,
            system=EXECUTOR_SYSTEM,
            tools=tools,
            messages=messages,
        )

        stop_reason = response.stop_reason
        logger.info("LLM stop_reason: %s", stop_reason)

        # Case A: LLM이 tool 안 쓰고 바로 응답 — 이건 프롬프트 실패 (Executor는 반드시 tool 써야 함)
        if stop_reason == "end_turn":
            text_blocks = [b.text for b in response.content if b.type == "text"]
            text = "\n".join(text_blocks)
            logger.warning("Executor ended without tool_use. Text: %s", text[:500])
            if last_tool_result_text:
                # tool은 썼지만 이후에 end_turn으로 마무리 — 정상
                break
            raise ExecutorError(
                f"Executor did not call the tool. Response: {text[:300]}"
            )

        # Case B: tool_use 요청
        if stop_reason != "tool_use":
            raise ExecutorError(f"Unexpected stop_reason: {stop_reason}")

        # tool_use block 추출
        assistant_content = response.content
        messages.append({"role": "assistant", "content": assistant_content})

        tool_uses = [b for b in assistant_content if b.type == "tool_use"]
        if not tool_uses:
            raise ExecutorError("stop_reason=tool_use but no tool_use block")

        # 각 tool_use 실행 (일반적으로 1개)
        tool_results = []
        for tu in tool_uses:
            tool_name = tu.name
            tool_input = tu.input
            logger.info("Calling MCP tool '%s' with input: %s",
                        tool_name, json.dumps(tool_input, ensure_ascii=False)[:200])

            raw_result = await call_mcp_tool(tool_name, tool_input)
            last_tool_result_text = raw_result

            # Parse to check for errors
            try:
                parsed = json.loads(raw_result)
            except json.JSONDecodeError:
                parsed = {"error": "Tool returned non-JSON", "type": "ParseError"}

            is_error = "error" in parsed and "type" in parsed
            if is_error:
                logger.warning("Tool error: %s (%s)", parsed.get("error"), parsed.get("type"))
                if parsed.get("type") == "GuardViolation":
                    guard_retries += 1

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": raw_result,
                "is_error": is_error,
            })

        # Guard 재시도 한계 체크
        if guard_retries > MAX_GUARD_RETRIES:
            logger.error("Max guard retries (%d) exceeded", MAX_GUARD_RETRIES)
            # 마지막 에러를 결과로 반환 (raise 대신)
            return json.loads(last_tool_result_text)

        # Tool result를 user message로 추가하고 다음 iteration
        messages.append({"role": "user", "content": tool_results})

    # 루프 종료 — 마지막 tool 결과 반환
    if not last_tool_result_text:
        raise ExecutorError("Loop ended without any tool call")

    return json.loads(last_tool_result_text)
