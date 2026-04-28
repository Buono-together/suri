"""
Orchestrator — 3-Agent pipeline entry point.

Flow: question → Planner → Executor → Critic → answer

Provides both async and sync interfaces.
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Callable

from .planner import plan, Plan, PlannerError
from .executor import execute, ExecutorError, ToolCall
from .critic import critique, CriticError


logger = logging.getLogger("suri.orchestrator")


@dataclass
class PipelineResult:
    """Full trace of a pipeline run — useful for debugging & UI display."""
    question: str
    plan: Plan | None
    tool_calls: list[ToolCall]
    execution_result: dict | None
    answer: str
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "plan": self.plan.to_dict() if self.plan else None,
            "tool_calls": [tc.to_dict() for tc in self.tool_calls],
            "execution_result": self.execution_result,
            "answer": self.answer,
            "error": self.error,
        }


def _safe_emit(
    on_event: Callable[[dict], None] | None,
    stage: str,
    type_: str,
    **data: Any,
) -> None:
    """Callback invocation that never raises into the pipeline."""
    if on_event is None:
        return
    try:
        on_event({"stage": stage, "type": type_, "data": data})
    except Exception as e:  # noqa: BLE001
        logger.warning("on_event callback raised in stage=%s type=%s: %s",
                       stage, type_, e)


async def run_async(
    question: str,
    history: list[dict] | None = None,
    on_event: Callable[[dict], None] | None = None,
) -> PipelineResult:
    """
    Run the full 3-Agent pipeline.

    Args:
        question: Current user question.
        history: Optional prior conversation turns [{"question", "answer"}, ...].
                 Passed to the Planner only; Executor/Critic operate on the
                 resolved single-turn plan.
        on_event: Optional progress callback. Payload shape:
                  {"stage": "planner"|"executor"|"critic",
                   "type":  "start"|"done"|"error"
                            |"tool_start"|"tool_done"|"retry",
                   "data":  {...}}
                  start/done are emitted at every stage boundary. Executor
                  additionally emits tool_start/tool_done/retry from inside
                  the tool-use loop.

    Errors at any stage are caught and surfaced in `error` field.
    `answer` always contains a user-facing string.
    """
    logger.info("=" * 60)
    if history:
        logger.info("Pipeline START (multi-turn, history=%d): %s",
                    len(history), question)
    else:
        logger.info("Pipeline START: %s", question)
    logger.info("=" * 60)

    # Step 1: Planner
    _safe_emit(on_event, "planner", "start")
    try:
        plan_obj = plan(question, history=history)
    except PlannerError as e:
        logger.error("Planner failed: %s", e)
        _safe_emit(on_event, "planner", "error", error=str(e))
        return PipelineResult(
            question=question,
            plan=None,
            tool_calls=[],
            execution_result=None,
            answer="질문 이해에 실패했습니다. 좀 더 구체적으로 말씀해 주세요.",
            error=f"PlannerError: {e}",
        )
    _safe_emit(
        on_event,
        "planner",
        "done",
        intent=plan_obj.intent,
        tables_needed=list(plan_obj.tables_needed),
    )

    # Step 2: Executor
    _safe_emit(on_event, "executor", "start")
    try:
        exec_result, tool_calls = await execute(plan_obj, on_event=on_event)
    except ExecutorError as e:
        logger.error("Executor failed: %s", e)
        # Executor 실패 시에도 지금까지 수집된 tool_calls가 있을 수 있음
        collected = getattr(e, "tool_calls", [])
        _safe_emit(
            on_event,
            "executor",
            "error",
            error=str(e),
            tool_count=len(collected),
        )
        return PipelineResult(
            question=question,
            plan=plan_obj,
            tool_calls=collected,
            execution_result=None,
            answer="데이터 조회 중 오류가 발생했습니다.",
            error=f"ExecutorError: {e}",
        )
    _safe_emit(
        on_event,
        "executor",
        "done",
        tool_count=len(tool_calls),
        error_count=sum(1 for tc in tool_calls if tc.is_error),
    )

    # Step 3: Critic
    _safe_emit(on_event, "critic", "start")
    try:
        answer = critique(question, plan_obj, exec_result)
    except CriticError as e:
        logger.error("Critic failed: %s", e)
        _safe_emit(on_event, "critic", "error", error=str(e))
        return PipelineResult(
            question=question,
            plan=plan_obj,
            tool_calls=tool_calls,
            execution_result=exec_result,
            answer="결과 해석 중 오류가 발생했습니다.",
            error=f"CriticError: {e}",
        )
    _safe_emit(on_event, "critic", "done", answer_chars=len(answer))

    logger.info("Pipeline END — success")
    return PipelineResult(
        question=question,
        plan=plan_obj,
        tool_calls=tool_calls,
        execution_result=exec_result,
        answer=answer,
    )


def run(
    question: str,
    use_cache: bool = True,
    history: list[dict] | None = None,
    on_event: Callable[[dict], None] | None = None,
) -> PipelineResult:
    """
    Sync wrapper for Streamlit / CLI use.

    Args:
        question: User question (Korean NL).
        use_cache: If True, check filesystem cache first (dev convenience).
                   Set False to force fresh API call.
        history: Optional prior conversation turns (multi-turn context).
                 Passed through to the Planner; also folded into the cache key
                 so different conversation paths don't collide.
        on_event: Optional progress callback — see run_async.
    """
    if use_cache:
        from .cache import load_cached, save_cached
        cached = load_cached(question, history=history)
        if cached is not None:
            # 캐시 HIT — UI가 3단계 UI를 그려뒀다면 비어있게 보일 수 있으니
            # 합성 start/done 이벤트를 빠르게 흘려준다. 각 stage duration은 0s.
            if on_event is not None:
                plan_obj = cached.plan
                _safe_emit(on_event, "planner", "start", cached=True)
                _safe_emit(
                    on_event, "planner", "done", cached=True,
                    intent=plan_obj.intent if plan_obj else "",
                    tables_needed=list(plan_obj.tables_needed) if plan_obj else [],
                )
                _safe_emit(on_event, "executor", "start", cached=True)
                # 캐시된 tool_calls을 순차 이벤트로 치환 (진행 모양만 재현)
                for i, tc in enumerate(cached.tool_calls, 1):
                    _safe_emit(
                        on_event, "executor", "tool_start",
                        name=tc.name, input=tc.input, call_index=i, cached=True,
                    )
                    _safe_emit(
                        on_event, "executor", "tool_done",
                        name=tc.name, duration_ms=tc.elapsed_ms,
                        is_error=tc.is_error, error_type=tc.error_type,
                        call_index=i, cached=True,
                    )
                _safe_emit(
                    on_event, "executor", "done", cached=True,
                    tool_count=len(cached.tool_calls),
                    error_count=sum(1 for tc in cached.tool_calls if tc.is_error),
                )
                _safe_emit(on_event, "critic", "start", cached=True)
                _safe_emit(on_event, "critic", "done", cached=True,
                           answer_chars=len(cached.answer))
            return cached

        result = asyncio.run(
            run_async(question, history=history, on_event=on_event)
        )
        if not result.error:  # 에러 응답은 캐시 안 함 (다음 시도 허용)
            save_cached(result, history=history)
        return result

    return asyncio.run(
        run_async(question, history=history, on_event=on_event)
    )