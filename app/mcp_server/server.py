"""
SURI MCP Server — The only entry point for Agents to access the DB.

Architecture (Layer 1 of 3-layer defense):
  Agent → MCP tool → [Guard validation] → [DB execution via suri_readonly] → response

Tools exposed:
- execute_readonly_sql(query): Validated SELECT execution

Design notes:
- Uses mcp.server.fastmcp.FastMCP (official SDK's FastMCP 1.0)
- Transport: stdio (standard for MCP servers)
- Guard violations and DB errors are returned as structured error messages
  so the Agent can self-correct
"""
from __future__ import annotations

import logging
import sys

from mcp.server.fastmcp import FastMCP

from .guards import check_query, GuardViolation
from .db import execute_readonly_json, DBExecutionError


# =============================================================
# 로깅 설정 (stderr로 — stdout은 MCP JSON-RPC 전용)
# =============================================================

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("suri-mcp")


# =============================================================
# MCP 서버 인스턴스
# =============================================================

mcp = FastMCP("suri-mcp")


# =============================================================
# Tool: execute_readonly_sql
# =============================================================

@mcp.tool()
def execute_readonly_sql(query: str) -> str:
    """
    Execute a read-only SELECT query against the SURI insurance database.

    This is the ONLY path for Agents to read data. All queries pass through
    a 3-layer defense:
      1. SQL Guard (this layer): AST-based validation. Blocks non-SELECT,
         blocks PII table 'customers' (use 'customers_safe' view instead).
      2. DB ROLE (suri_readonly): read-only account, no write permissions.
      3. Schema VIEW: customers_safe masks PII columns.

    Available tables:
      - products, agents, policies, claims, premium_payments
      - customers_safe (use INSTEAD of customers — PII is masked)
      - premium_payments_v (adds payment_month_seq for retention analysis)
      - monthly_ape (pre-aggregated Annual Premium Equivalent)

    Args:
        query: A single SELECT statement. Multiple statements are rejected.

    Returns:
        JSON string with shape:
        {
          "columns": ["col1", ...],
          "rows": [{"col1": ...}, ...],
          "row_count": <int>,
          "truncated": <bool>  // true if more rows available
        }

    Error responses (also JSON):
        {"error": "...", "type": "GuardViolation" | "DBExecutionError"}
    """
    import json

    logger.info("execute_readonly_sql called: %s", query[:200])

    # Layer 1 — Guard
    try:
        guard_result = check_query(query)
    except GuardViolation as e:
        logger.warning("Guard blocked query: %s", e)
        return json.dumps(
            {"error": str(e), "type": "GuardViolation"},
            ensure_ascii=False,
            indent=2,
        )

    logger.info(
        "Guard passed (tables: %s)",
        guard_result.tables_referenced,
    )

    # Layer 2 — DB execution
    try:
        result = execute_readonly_json(query)
        logger.info("Query executed successfully")
        return result
    except DBExecutionError as e:
        logger.error("DB execution failed: %s", e)
        return json.dumps(
            {"error": str(e), "type": "DBExecutionError"},
            ensure_ascii=False,
            indent=2,
        )


# =============================================================
# Entrypoint
# =============================================================

def main() -> None:
    """Run the MCP server over stdio transport."""
    logger.info("Starting SURI MCP Server")
    mcp.run()


if __name__ == "__main__":
    main()
