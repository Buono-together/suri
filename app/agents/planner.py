"""
Planner Agent — 자연어 질문 → 분석 계획.

No tool use. Single LLM call.
Output: structured dict (JSON parsed).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from .base import get_anthropic_client, PLANNER_MODEL, MAX_TOKENS_PLANNER, cached_system
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

# 이전 턴 답변 문맥은 요약된 형태로만 전달한다. Planner가 필요한 건
# 엔티티(채널·상품 등)와 대체적 결론뿐이고, 전문을 넣으면 prompt가
# 늘어나 드물게 token 초과를 유발한다.
_HISTORY_ANSWER_CHAR_BUDGET = 600


def _build_messages(question: str, history: list[dict] | None) -> list[dict]:
    messages: list[dict] = []
    if history:
        for turn in history:
            q = turn.get("question", "").strip()
            a = turn.get("answer", "").strip()
            if len(a) > _HISTORY_ANSWER_CHAR_BUDGET:
                a = a[:_HISTORY_ANSWER_CHAR_BUDGET] + " …(이하 생략)"
            if q:
                messages.append({"role": "user", "content": q})
            if a:
                messages.append({"role": "assistant", "content": a})
    messages.append({"role": "user", "content": question})
    return messages


def plan(question: str, history: list[dict] | None = None) -> Plan:
    """
    Produce an analysis plan from a Korean natural-language question.

    Args:
        question: Current user question.
        history: Optional prior turns as [{"question": str, "answer": str}, ...]
                 in chronological order. When present, the Planner resolves
                 deictic references (e.g., "그 상품") using prior context.
                 history=None or [] → identical behavior to single-turn plan().

    Raises PlannerError if:
    - LLM response is not valid JSON
    - Required fields are missing
    """
    client = get_anthropic_client()

    if history:
        logger.info(
            "plan() called with question: %s (history turns=%d)",
            question[:200], len(history),
        )
    else:
        logger.info("plan() called with question: %s", question[:200])

    response = client.messages.create(
        model=PLANNER_MODEL,
        max_tokens=MAX_TOKENS_PLANNER,
        system=cached_system(PLANNER_SYSTEM),
        messages=_build_messages(question, history),
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
    # JSON 파싱 (max_tokens 부족으로 잘렸을 가능성 대비)
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as e:
        logger.warning("JSON parse failed (likely truncated). Retrying with explicit 'shorter plan' instruction. Raw tail: ...%s", raw_text[-200:])
        
        # 재시도: 더 짧게 응답하도록 명시
        retry_question = question + "\n\n(Keep each field concise - aim for a shorter plan. Maximum 3 items per list.)"
        retry_response = client.messages.create(
            model=PLANNER_MODEL,
            max_tokens=MAX_TOKENS_PLANNER,
            system=cached_system(PLANNER_SYSTEM),
            messages=_build_messages(retry_question, history),
        )
        
        if not retry_response.content:
            raise PlannerError("Empty response on retry")
        
        raw_text = retry_response.content[0].text.strip()
        if raw_text.startswith("```"):
            lines = raw_text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            raw_text = "\n".join(lines).strip()
        
        try:
            parsed = json.loads(raw_text)
            logger.info("Planner retry succeeded with shorter instruction")
        except json.JSONDecodeError as e2:
            logger.error("Planner retry also failed. Raw: %s", raw_text[:500])
            raise PlannerError(f"Planner returned invalid JSON (after retry): {e2}")

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
