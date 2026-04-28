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
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from .base import (
    get_anthropic_client,
    list_mcp_tools,
    call_mcp_tool,
    MODEL_NAME,
    MAX_TOKENS_EXECUTOR,
    MAX_GUARD_RETRIES,
    cached_system,
)
from .prompts import EXECUTOR_SYSTEM
from .planner import Plan


logger = logging.getLogger("suri.executor")


@dataclass
class ToolCall:
    """Single MCP tool invocation with its outcome — for UI display."""
    name: str
    input: dict
    output_raw: str
    is_error: bool
    error_type: str | None
    elapsed_ms: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "input": self.input,
            "output_raw": self.output_raw,
            "is_error": self.is_error,
            "error_type": self.error_type,
            "elapsed_ms": self.elapsed_ms,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ToolCall":
        return cls(
            name=d["name"],
            input=d["input"],
            output_raw=d["output_raw"],
            is_error=d["is_error"],
            error_type=d.get("error_type"),
            elapsed_ms=d["elapsed_ms"],
        )


class ExecutorError(RuntimeError):
    """Raised when executor fails after retries."""
    def __init__(self, msg: str, tool_calls: list[ToolCall] | None = None):
        super().__init__(msg)
        self.tool_calls = tool_calls or []


async def execute(
    plan: Plan,
    on_event: Callable[[dict], None] | None = None,
) -> tuple[dict, list[ToolCall]]:
    """
    Execute the plan by generating SQL and calling MCP tool.

    Returns (result_dict, tool_calls):
      - result_dict: the MCP tool's final result (columns/rows/row_count/truncated)
                     or error dict ({error, type}) if retries exhausted
      - tool_calls: full list of MCP tool invocations with timings, for UI.

    Raises ExecutorError only on fundamental failures (LLM errors, etc.).
    The exception carries .tool_calls so partial trace is preserved.

    on_event: optional progress callback. Invoked synchronously from this
    coroutine's thread with dict payloads of shape
      {"stage": "executor", "type": "tool_start"|"tool_done"|"retry", "data": {...}}.
    Exceptions inside the callback are swallowed with a warning so a broken UI
    listener never corrupts the pipeline.
    """
    client = get_anthropic_client()
    tool_calls_trace: list[ToolCall] = []

    def _emit(type_: str, **data: Any) -> None:
        if on_event is None:
            return
        try:
            on_event({"stage": "executor", "type": type_, "data": data})
        except Exception as cb_err:  # noqa: BLE001
            logger.warning("on_event callback raised: %s", cb_err)

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
            system=cached_system(EXECUTOR_SYSTEM),
            tools=tools,
            messages=messages,
        )

        stop_reason = response.stop_reason
        logger.info("LLM stop_reason: %s", stop_reason)

        # Case A: end_turn
        if stop_reason == "end_turn":
            if last_tool_result_text:
                logger.info("Executor completed normally after tool call")
                break
            text_blocks = [b.text for b in response.content if b.type == "text"]
            text = "\n".join(text_blocks)
            logger.error("Executor ended without calling any tool")
            raise ExecutorError(
                f"Executor did not call the tool. Response: {text[:300]}",
                tool_calls=tool_calls_trace,
            )

        # Case A-2: max_tokens — tool 결과가 있으면 정상 종료로 간주
        if stop_reason == "max_tokens":
            if last_tool_result_text:
                logger.warning(
                    "Executor hit max_tokens after tool call — "
                    "treating last tool result as final"
                )
                break
            raise ExecutorError("max_tokens hit before any tool call", tool_calls=tool_calls_trace)

        # Case B: tool_use 요청
        if stop_reason != "tool_use":
            raise ExecutorError(f"Unexpected stop_reason: {stop_reason}", tool_calls=tool_calls_trace)

        # tool_use block 추출
        assistant_content = response.content
        messages.append({"role": "assistant", "content": assistant_content})

        tool_uses = [b for b in assistant_content if b.type == "tool_use"]
        if not tool_uses:
            raise ExecutorError("stop_reason=tool_use but no tool_use block", tool_calls=tool_calls_trace)

        # 각 tool_use 실행 (일반적으로 1개)
        tool_results = []
        for tu in tool_uses:
            tool_name = tu.name
            tool_input = tu.input
            logger.info("Calling MCP tool '%s' with input: %s",
                        tool_name, json.dumps(tool_input, ensure_ascii=False)[:200])

            _emit(
                "tool_start",
                name=tool_name,
                input=dict(tool_input) if tool_input else {},
                call_index=len(tool_calls_trace) + 1,
            )

            t0 = time.monotonic()
            raw_result = await call_mcp_tool(tool_name, tool_input)
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            last_tool_result_text = raw_result

            # Parse to check for errors
            try:
                parsed = json.loads(raw_result)
            except json.JSONDecodeError:
                parsed = {"error": "Tool returned non-JSON", "type": "ParseError"}

            is_error = "error" in parsed and "type" in parsed
            error_type = parsed.get("type") if is_error else None
            if is_error:
                logger.warning("Tool error: %s (%s)", parsed.get("error"), parsed.get("type"))
                if parsed.get("type") == "GuardViolation":
                    guard_retries += 1
                    _emit(
                        "retry",
                        attempt=guard_retries,
                        reason="GuardViolation",
                        error=str(parsed.get("error", ""))[:200],
                    )

            # UI trace 수집
            tool_calls_trace.append(ToolCall(
                name=tool_name,
                input=dict(tool_input) if tool_input else {},
                output_raw=raw_result,
                is_error=is_error,
                error_type=error_type,
                elapsed_ms=elapsed_ms,
            ))

            _emit(
                "tool_done",
                name=tool_name,
                duration_ms=elapsed_ms,
                is_error=is_error,
                error_type=error_type,
                call_index=len(tool_calls_trace),
            )

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": raw_result,
                "is_error": is_error,
            })

        # Guard 재시도 한계 체크
        if guard_retries > MAX_GUARD_RETRIES:
            logger.error("Max guard retries (%d) exceeded", MAX_GUARD_RETRIES)
            return json.loads(last_tool_result_text), tool_calls_trace

        # Tool result를 user message로 추가하고 다음 iteration
        messages.append({"role": "user", "content": tool_results})

    # 루프 종료 — 마지막 tool 결과 반환
    if not last_tool_result_text:
        raise ExecutorError("Loop ended without any tool call", tool_calls=tool_calls_trace)

    return json.loads(last_tool_result_text), tool_calls_trace
