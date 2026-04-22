"""
SQL Guard — Layer 1 of 3-layer defense

AST-based SQL validation:
- SELECT statements only (no DML/DDL)
- Block direct access to PII tables (customers)
- Redirect to VIEW equivalents (customers_safe)

Design principle: fail fast, fail loudly.
If the query is suspicious, reject it with clear reason.

This is the Application layer. Even if we miss something here,
Layer 2 (suri_readonly ROLE) and Layer 3 (schema VIEW) still catch it.
But better to reject early with a meaningful error message than let
the Agent try and get a cryptic DB error.
"""
from __future__ import annotations

from dataclasses import dataclass

import sqlglot
from sqlglot import exp


# =============================================================
# 설정
# =============================================================

# 접근 차단 테이블 (PII 원본)
BLOCKED_TABLES: frozenset[str] = frozenset({"customers"})

# 허용 SQL 동작 (읽기 전용)
ALLOWED_STATEMENTS: frozenset[type] = frozenset({exp.Select})


# =============================================================
# 예외
# =============================================================

class GuardViolation(ValueError):
    """Raised when a SQL query violates SURI access policy."""
    pass


# =============================================================
# 검증 결과 데이터 클래스
# =============================================================

@dataclass(frozen=True)
class GuardResult:
    """SQL 검증 통과 시의 요약 정보 (로그용)."""
    statement_type: str
    tables_referenced: tuple[str, ...]


# =============================================================
# 핵심 검증 함수
# =============================================================

def check_query(query: str) -> GuardResult:
    """
    Validate a SQL query against SURI access policy.

    Raises GuardViolation with descriptive message if:
    - Query fails to parse
    - Contains non-SELECT statements (INSERT/UPDATE/DELETE/DROP/...)
    - References blocked PII tables (customers)
    - Contains multiple statements (injection vector)

    Returns GuardResult on success, with tables referenced for logging.
    """
    # 0. Empty/whitespace check
    if not query or not query.strip():
        raise GuardViolation("Empty query")

    # 1. Parse with PostgreSQL dialect
    try:
        parsed = sqlglot.parse(query, dialect="postgres")
    except sqlglot.errors.ParseError as e:
        raise GuardViolation(f"SQL parse error: {e}")

    # 2. Multi-statement check (SQL injection vector)
    # parse() returns list of statements; multiple = suspicious
    non_null = [p for p in parsed if p is not None]
    if len(non_null) == 0:
        raise GuardViolation("No parseable statement found")
    if len(non_null) > 1:
        raise GuardViolation(
            f"Multiple statements detected ({len(non_null)}). "
            "Only single SELECT is allowed."
        )

    stmt = non_null[0]

    # 3. Statement type check
    if type(stmt) not in ALLOWED_STATEMENTS:
        stmt_name = type(stmt).__name__
        raise GuardViolation(
            f"Only SELECT statements allowed. Got: {stmt_name}"
        )

    # 4. Blocked table check (AST traversal)
    # exp.Table matches `customers`, `c.customers`, `public.customers` all
    blocked_found: set[str] = set()
    tables_all: set[str] = set()

    for table_node in stmt.find_all(exp.Table):
        # table_node.name == "customers" (lowercase, unqualified name)
        table_name = table_node.name.lower()
        tables_all.add(table_name)
        if table_name in BLOCKED_TABLES:
            blocked_found.add(table_name)

    if blocked_found:
        raise GuardViolation(
            f"Access denied to PII table(s): {sorted(blocked_found)}. "
            f"Use 'customers_safe' view instead."
        )

    return GuardResult(
        statement_type="SELECT",
        tables_referenced=tuple(sorted(tables_all)),
    )
