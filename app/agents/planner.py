"""
Planner Agent — 자연어 질문 → 분석 계획.

No tool use. Single LLM call.
Output: structured dict (JSON parsed).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from .base import get_anthropic_client, MODEL_NAME, MAX_TOKENS_PLANNER, cached_system
from .prompts import PLANNER_SYSTEM


logger = logging.getLogger("suri.planner")


# =============================================================
# Result type
# =============================================================

@dataclass(frozen=True)
class Plan:
    intent: str
    tables_needed: list[str]
    aggregations: list[str]
    filters: list[str]
    expected_columns: list[str]
    caveats: list[str]

    def to_dict(self) -> dict:
        return {
            "intent": self.intent,
            "tables_needed": self.tables_needed,
            "aggregations": self.aggregations,
            "filters": self.filters,
            "expected_columns": self.expected_columns,
            "caveats": self.caveats,
        }


class PlannerError(RuntimeError):
    """Raised when planner fails to produce a valid plan."""
    pass


# =============================================================
# Main function
# =============================================================

def plan(question: str) -> Plan:
    """
    Produce an analysis plan from a Korean natural-language question.

    Raises PlannerError if:
    - LLM response is not valid JSON
    - Required fields are missing
    """
    client = get_anthropic_client()

    logger.info("plan() called with question: %s", question[:200])

    response = client.messages.create(
        model=MODEL_NAME,
        max_tokens=MAX_TOKENS_PLANNER,
        system=cached_system(PLANNER_SYSTEM),
        messages=[
            {"role": "user", "content": question},
        ],
    )

    # Claude 응답은 content blocks의 리스트. 첫 번째 text block 사용.
    if not response.content:
        raise PlannerError("Empty response from LLM")

    raw_text = response.content[0].text.strip()

    # LLM이 가끔 ```json ... ``` 로 감싸는 경우 제거
    if raw_text.startswith("```"):
        # ```json\n{...}\n``` 또는 ```\n{...}\n```
        lines = raw_text.split("\n")
        # 첫 줄과 마지막 줄(``` 있는 줄) 제거
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw_text = "\n".join(lines).strip()

    # JSON 파싱
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as e:
        logger.error("JSON parse failed. Raw: %s", raw_text[:500])
        raise PlannerError(f"Planner returned invalid JSON: {e}")

    # 필수 필드 검증
    required = ["intent", "tables_needed", "aggregations", "filters",
                "expected_columns", "caveats"]
    missing = [f for f in required if f not in parsed]
    if missing:
        raise PlannerError(f"Plan missing required fields: {missing}")

    plan_obj = Plan(
        intent=parsed["intent"],
        tables_needed=parsed["tables_needed"],
        aggregations=parsed["aggregations"],
        filters=parsed["filters"],
        expected_columns=parsed["expected_columns"],
        caveats=parsed["caveats"],
    )

    logger.info("Plan produced. Tables: %s", plan_obj.tables_needed)
    return plan_obj
