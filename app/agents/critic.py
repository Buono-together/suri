"""
Critic Agent — 결과 해석 + 자연어 답변.

No tool use. Single LLM call.
Output: Korean natural language text.
"""
from __future__ import annotations

import json
import logging

from .base import get_anthropic_client, CRITIC_MODEL, MAX_TOKENS_CRITIC, cached_system
from .prompts import CRITIC_SYSTEM
from .planner import Plan


logger = logging.getLogger("suri.critic")


class CriticError(RuntimeError):
    """Raised when critic fails to produce an answer."""
    pass


def critique(question: str, plan: Plan, execution_result: dict) -> str:
    """
    Produce a natural-language Korean answer.

    Args:
        question: Original user question.
        plan: Plan object from planner.
        execution_result: Dict with keys:
          - "columns": list[str]
          - "rows": list[dict]
          - "row_count": int
          - "truncated": bool
          OR (on failure):
          - "error": str
          - "type": str

    Returns:
        Plain Korean text answer.
    """
    client = get_anthropic_client()

    logger.info("critique() called. Result row_count: %s",
                execution_result.get("row_count", "N/A"))

    # Critic에게 줄 context 구성
    user_message = f"""User's original question (Korean):
{question}

Planner's analysis plan:
{json.dumps(plan.to_dict(), ensure_ascii=False, indent=2)}

Executor's result:
{json.dumps(execution_result, ensure_ascii=False, indent=2)}

Produce a concise Korean answer for the user."""

    response = client.messages.create(
        model=CRITIC_MODEL,
        max_tokens=MAX_TOKENS_CRITIC,
        system=cached_system(CRITIC_SYSTEM),
        messages=[
            {"role": "user", "content": user_message},
        ],
    )

    if not response.content:
        raise CriticError("Empty response from LLM")

    answer = response.content[0].text.strip()
    logger.info("Critic produced answer (%d chars)", len(answer))
    return answer
