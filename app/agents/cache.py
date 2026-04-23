"""
File-system cache for Agent pipeline results.

Purpose:
- Development/testing only. Skip API calls for previously-answered questions.
- NOT a production cache. Production would use session-scoped memory or Redis.

Cache key: MD5 hash of question string.
Cache location: .cache/agent_responses/<hash>.json
Invalidation: manual (delete .cache directory)
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .planner import Plan
from .executor import ToolCall
from .orchestrator import PipelineResult


logger = logging.getLogger("suri.cache")


CACHE_DIR = Path(".cache/agent_responses")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _cache_key(question: str) -> str:
    """Stable hash of question text."""
    return hashlib.md5(question.strip().encode("utf-8")).hexdigest()[:16]


def _cache_path(question: str) -> Path:
    return CACHE_DIR / f"{_cache_key(question)}.json"


def load_cached(question: str) -> PipelineResult | None:
    """Return cached PipelineResult if present, else None."""
    path = _cache_path(question)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        plan_data = data.get("plan")
        plan_obj = Plan(**plan_data) if plan_data else None
        
        tool_calls_data = data.get("tool_calls", [])
        tool_calls = [ToolCall.from_dict(tc) for tc in tool_calls_data]
        
        result = PipelineResult(
            question=data["question"],
            plan=plan_obj,
            tool_calls=tool_calls,
            execution_result=data.get("execution_result"),
            answer=data["answer"],
            error=data.get("error"),
        )
        logger.info("Cache HIT for question: %s", question[:60])
        return result
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.warning("Cache file corrupted, ignoring: %s", e)
        return None


def save_cached(result: PipelineResult) -> None:
    """Save PipelineResult to cache."""
    path = _cache_path(result.question)
    try:
        data: dict[str, Any] = {
            "question": result.question,
            "plan": asdict(result.plan) if result.plan else None,
            "tool_calls": [tc.to_dict() for tc in result.tool_calls],
            "execution_result": result.execution_result,
            "answer": result.answer,
            "error": result.error,
        }
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("Cache SAVED for question: %s", result.question[:60])
    except (OSError, TypeError) as e:
        logger.warning("Cache save failed: %s", e)


def clear_cache() -> int:
    """Remove all cached responses. Returns number of files deleted."""
    count = 0
    for f in CACHE_DIR.glob("*.json"):
        f.unlink()
        count += 1
    logger.info("Cache cleared: %d files removed", count)
    return count
