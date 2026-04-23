"""
SURI MCP Server — The only entry point for Agents to access the DB.

Architecture (Layer 1 of 3-layer defense):
  Agent → MCP tool → [Guard validation] → [DB execution via suri_readonly] → response

Tools exposed:
- execute_readonly_sql(query): Validated SELECT execution
- list_tables: Schema discovery
- describe_table(name): Column inspection
- get_domain_term(term): Deterministic Korean insurance glossary lookup

Design notes:
- Uses mcp.server.fastmcp.FastMCP (official SDK's FastMCP 1.0)
- Transport: stdio (standard for MCP servers)
- Guard violations and DB errors are returned as structured error messages
  so the Agent can self-correct
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import yaml
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
# Tool: list_tables
# =============================================================

@mcp.tool()
def list_tables() -> str:
    """
    List all accessible tables and views in the SURI database.

    Returns a JSON array of objects with fields:
      - name: table or view name
      - type: 'BASE TABLE' | 'VIEW'
      - row_estimate: approximate row count (NULL for views)

    Only tables/views accessible by suri_readonly are returned.
    Due to the GRANT-based permission model (ADR: 3-layer defense),
    'customers' is intentionally absent from this list — use
    'customers_safe' view for PII-masked access.
    """
    import json

    logger.info("list_tables called")

    query = """
        SELECT 
            t.table_name AS name,
            t.table_type AS type,
            c.reltuples::BIGINT AS row_estimate
        FROM information_schema.tables t
        LEFT JOIN pg_class c ON c.relname = t.table_name
        WHERE t.table_schema = 'public'
        ORDER BY t.table_name
    """

    try:
        result = execute_readonly_json(query)
        logger.info("list_tables succeeded")
        return result
    except DBExecutionError as e:
        logger.error("list_tables failed: %s", e)
        return json.dumps(
            {"error": str(e), "type": "DBExecutionError"},
            ensure_ascii=False,
            indent=2,
        )


# =============================================================
# Tool: describe_table
# =============================================================

# 허용 테이블 이름 패턴 (SQL injection 방어)
import re
_VALID_TABLE_NAME = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


@mcp.tool()
def describe_table(table_name: str) -> str:
    """
    Describe columns of a specific table or view.

    Args:
        table_name: Name of the table or view (e.g., 'policies', 'customers_safe').
                    Must be alphanumeric + underscore only.

    Returns JSON with fields:
      - columns: list of {name, data_type, is_nullable, column_default}

    If the table is not accessible (permission denied) or does not exist,
    returns an error object.
    """
    import json

    logger.info("describe_table called with: %s", table_name)

    # 이름 검증 (SQL injection 차단)
    if not _VALID_TABLE_NAME.match(table_name):
        logger.warning("describe_table rejected invalid name: %s", table_name)
        return json.dumps(
            {"error": f"Invalid table name format: {table_name!r}",
             "type": "GuardViolation"},
            ensure_ascii=False,
            indent=2,
        )

    # Parameterized query가 아닌 이유: psycopg의 식별자는 파라미터로 못 넣음
    # 대신 정규식 화이트리스트 + information_schema가 접근 제어를 이중으로 담당
    query = f"""
        SELECT 
            column_name AS name,
            data_type,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = '{table_name}'
        ORDER BY ordinal_position
    """

    try:
        result = execute_readonly_json(query)
        logger.info("describe_table succeeded for %s", table_name)
        return result
    except DBExecutionError as e:
        logger.error("describe_table failed: %s", e)
        return json.dumps(
            {"error": str(e), "type": "DBExecutionError"},
            ensure_ascii=False,
            indent=2,
        )

# =============================================================
# Tool: get_domain_term
# =============================================================
#
# Deterministic domain glossary retrieval. Replaces RAG/vector-DB with
# a single-file YAML lookup (4-AI cross-review consensus, 2026-04-23).
# Rationale: domain terms in Korean life insurance are closed-vocabulary
# and benefit more from author-curated definitions than from semantic
# similarity search. See ADR-004.

_GLOSSARY_PATH = Path(__file__).parent / "domain_glossary.yaml"
_glossary_cache: dict[str, Any] | None = None


def _load_glossary() -> dict[str, Any]:
    """Lazy-load the glossary YAML into a dict on first access."""
    global _glossary_cache
    if _glossary_cache is None:
        with _GLOSSARY_PATH.open(encoding="utf-8") as f:
            _glossary_cache = yaml.safe_load(f)
        logger.info(
            "Glossary loaded: %d top-level keys", len(_glossary_cache)
        )
    return _glossary_cache


@mcp.tool()
def get_domain_term(term: str) -> str:
    """
    Retrieve the standard definition, formula, and SQL hint for a Korean
    life-insurance domain term.

    Use this BEFORE generating SQL whenever the user's question mentions
    a domain term like 유지율, APE, CSM, 손해율, 지급률, 코호트, 해지율,
    판매채널, 측정모형 등. The retrieved entry contains:
      - standard_definition / definition: authoritative definition
      - calculation_basis / formula / proxy_formula: computation rules
      - suri_schema_hint: which tables/columns to use in SURI DB
      - suri_산출_가능_여부: whether this metric can be computed from PoC data
      - 불가_사유 (if applicable): data limitations
      - critical_note / common_mistake: pitfalls to avoid
      - industry_benchmark: expected value range for sanity check
      - sources: primary/secondary citations

    This tool is deterministic (single-file YAML lookup, no semantic search).

    Args:
        term: Exact term key. Available keys include:
              유지율, 조기_해지율, 해지_및_실효, 해약환급금, 승환계약,
              APE, 월초보험료, 수입보험료, 코호트,
              CSM, BEL, RA, IFRS17_측정모형, 지급률_proxy,
              판매채널, 상품유형, 절판, 불완전판매

    Returns:
        JSON string of the full term entry (dict) on hit.
        On miss: {"error": "...", "suggested_terms": [all registered keys]}
    """
    import json

    logger.info("get_domain_term called: %s", term)

    glossary = _load_glossary()

    # meta 블록은 사전 조회 대상에서 제외
    registered_terms = [k for k in glossary.keys() if k != "meta"]

    if term in glossary and term != "meta":
        entry = glossary[term]
        return json.dumps(
            {"term": term, "entry": entry},
            ensure_ascii=False,
            indent=2,
        )

    logger.info("Term not registered: %s", term)
    return json.dumps(
        {
            "error": f"미등록 용어: {term!r}",
            "type": "TermNotFound",
            "suggested_terms": registered_terms,
        },
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
