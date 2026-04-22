"""
Read-only DB access for the MCP server.

Design:
- suri_readonly account ONLY (never admin)
- SET TRANSACTION READ ONLY for session-level enforcement
- Row-to-dict conversion + JSON serialization for MCP response

This module is the *only* place where the MCP server touches the DB.
All SQL flows through execute_readonly() → suri_readonly → Layer 2/3 defense.
"""
from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterator

import psycopg
from dotenv import load_dotenv


load_dotenv()


# =============================================================
# 설정
# =============================================================

# Readonly 계정 DSN (Layer 2 방어의 핵심)
READONLY_DSN = (
    f"host={os.getenv('POSTGRES_HOST', 'localhost')} "
    f"port={os.getenv('POSTGRES_PORT', '5432')} "
    f"dbname={os.getenv('POSTGRES_DB', 'suri')} "
    f"user={os.getenv('POSTGRES_READONLY_USER', 'suri_readonly')} "
    f"password={os.getenv('POSTGRES_READONLY_PASSWORD', 'readonly_pass')}"
)

# 결과 반환 최대 행 수 (Agent context window 보호)
MAX_RESULT_ROWS = 100


# =============================================================
# 예외
# =============================================================

class DBExecutionError(RuntimeError):
    """Raised when SQL execution fails (parse-level OK, runtime-level fail)."""
    pass


# =============================================================
# JSON 직렬화 헬퍼
# =============================================================

def _json_default(obj: Any) -> Any:
    """
    Convert non-JSON-native types to serializable form.
    PostgreSQL returns date/datetime/Decimal/bytes — these aren't JSON-native.
    """
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        # 금액·비율 등 정확도 중요 값은 string으로 보존
        return str(obj)
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    raise TypeError(f"Type {type(obj).__name__} not JSON serializable")


# =============================================================
# 연결 컨텍스트 매니저
# =============================================================

@contextmanager
def readonly_connection() -> Iterator[psycopg.Connection]:
    """
    Context manager for a read-only PostgreSQL connection.

    - Uses suri_readonly account (Layer 2)
    - Sets session to READ ONLY (belt-and-suspenders)
    - Always rolls back on exit (no accidental writes even if somehow attempted)
    """
    conn = psycopg.connect(READONLY_DSN)
    try:
        # Session-level enforcement — 추가 안전장치
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
        yield conn
    finally:
        # Read-only니까 commit 의미 없음 — 안전하게 rollback
        conn.rollback()
        conn.close()


# =============================================================
# 메인 실행 함수
# =============================================================

def execute_readonly(query: str, max_rows: int = MAX_RESULT_ROWS) -> dict[str, Any]:
    """
    Execute a SELECT query via suri_readonly account, return JSON-ready dict.

    Response shape:
    {
        "columns": ["col1", "col2", ...],
        "rows":    [{"col1": ..., "col2": ...}, ...],
        "row_count": <int>,
        "truncated": <bool>
    }

    Raises DBExecutionError on any DB-level error (permission, syntax, timeout).
    Guard should have pre-validated the query; this is the last enforcement point.
    """
    try:
        with readonly_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)

                # SELECT가 아니면 description이 None
                if cur.description is None:
                    raise DBExecutionError(
                        "Query returned no column metadata (not a SELECT?)"
                    )

                columns = [desc[0] for desc in cur.description]
                raw_rows = cur.fetchmany(max_rows + 1)  # +1로 truncation 감지

                truncated = len(raw_rows) > max_rows
                rows_to_return = raw_rows[:max_rows]

                # tuple → dict 변환
                rows_dict = [
                    dict(zip(columns, row)) for row in rows_to_return
                ]

                return {
                    "columns":   columns,
                    "rows":      rows_dict,
                    "row_count": len(rows_dict),
                    "truncated": truncated,
                }

    except psycopg.errors.InsufficientPrivilege as e:
        # Layer 2 방어 발동 — 이게 나오면 Guard가 뚫린 것, DB가 막은 것
        raise DBExecutionError(
            f"Permission denied (caught by DB layer 2): {e}"
        )
    except psycopg.Error as e:
        raise DBExecutionError(f"DB execution failed: {e}")


# =============================================================
# JSON 문자열 버전 (MCP tool 응답용)
# =============================================================

def execute_readonly_json(query: str, max_rows: int = MAX_RESULT_ROWS) -> str:
    """
    Same as execute_readonly(), but returns JSON string (for MCP tool response).
    """
    result = execute_readonly(query, max_rows=max_rows)
    return json.dumps(result, default=_json_default, ensure_ascii=False, indent=2)
