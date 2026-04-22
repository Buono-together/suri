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
from typing import Any

from .planner import plan, Plan, PlannerError
from .executor import execute, ExecutorError
from .critic import critique, CriticError


logger = logging.getLogger("suri.orchestrator")


@dataclass
class PipelineResult:
    """Full trace of a pipeline run — useful for debugging & UI display."""
    question: str
    plan: Plan | None
    execution_result: dict | None
    answer: str
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "plan": self.plan.to_dict() if self.plan else None,
            "execution_result": self.execution_result,
            "answer": self.answer,
            "error": self.error,
        }


async def run_async(question: str) -> PipelineResult:
    """
    Run the full 3-Agent pipeline.

    Errors at any stage are caught and surfaced in `error` field.
    `answer` always contains a user-facing string.
    """
    logger.info("=" * 60)
    logger.info("Pipeline START: %s", question)
    logger.info("=" * 60)

    # Step 1: Planner
    try:
        plan_obj = plan(question)
    except PlannerError as e:
        logger.error("Planner failed: %s", e)
        return PipelineResult(
            question=question,
            plan=None,
            execution_result=None,
            answer="질문 이해에 실패했습니다. 좀 더 구체적으로 말씀해 주세요.",
            error=f"PlannerError: {e}",
        )

    # Step 2: Executor
    try:
        exec_result = await execute(plan_obj)
    except ExecutorError as e:
        logger.error("Executor failed: %s", e)
        return PipelineResult(
            question=question,
            plan=plan_obj,
            execution_result=None,
            answer="데이터 조회 중 오류가 발생했습니다.",
            error=f"ExecutorError: {e}",
        )

    # Step 3: Critic
    try:
        answer = critique(question, plan_obj, exec_result)
    except CriticError as e:
        logger.error("Critic failed: %s", e)
        return PipelineResult(
            question=question,
            plan=plan_obj,
            execution_result=exec_result,
            answer="결과 해석 중 오류가 발생했습니다.",
            error=f"CriticError: {e}",
        )

    logger.info("Pipeline END — success")
    return PipelineResult(
        question=question,
        plan=plan_obj,
        execution_result=exec_result,
        answer=answer,
    )


def run(question: str) -> PipelineResult:
    """
    Sync wrapper for Streamlit / CLI use.
    """
    return asyncio.run(run_async(question))
