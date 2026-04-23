"""
Streamlit 렌더링 헬퍼.

각 뷰 섹션의 표시 로직 분리. streamlit_app.py 본문 간결 유지 목적.
"""
from __future__ import annotations

import json
from typing import Any

import streamlit as st

from app.agents.executor import ToolCall
from app.agents.orchestrator import PipelineResult


# =============================================================
# 3층 방어 뱃지
# =============================================================

def render_governance_status(result: PipelineResult) -> None:
    """
    3층 방어 중 어디까지 갔는지 상단에 보여준다.
    - Layer 3 (Schema/VIEW): customers 부재 감지, customers_safe 사용, Schema 단계 차단
    - Layer 1 (SQL Guard): GuardViolation 발생 여부
    - Layer 2 (DB ROLE): 읽기전용 (항상 적용)

    Layer 3 분기 순서 (엄격한 것부터):
    1. execute_readonly_sql 미호출 → Schema 단계에서 차단 (C5 케이스)
    2. customers_safe 사용 → VIEW 우회 (C4 케이스)
    3. 그 외 → 일반 테이블 접근
    """
    sql_executed = any(tc.name == "execute_readonly_sql" for tc in result.tool_calls)
    layer3_safe_view = False
    layer1_blocked = False

    for tc in result.tool_calls:
        if tc.name == "execute_readonly_sql":
            sql = str(tc.input.get("query", ""))
            if "customers_safe" in sql.lower():
                layer3_safe_view = True
        if tc.is_error and tc.error_type == "GuardViolation":
            layer1_blocked = True

    col1, col2, col3 = st.columns(3)
    with col1:
        if layer1_blocked:
            st.error("🔴 Layer 1 — SQL Guard 차단 발생")
        else:
            st.success("🟢 Layer 1 — SQL Guard 통과")
    with col2:
        st.success("🟢 Layer 2 — suri_readonly ROLE")
    with col3:
        if not sql_executed:
            st.info("🔵 Layer 3 — Schema 차단 (원본 테이블/PII 컬럼 부재)")
        elif layer3_safe_view:
            st.info("🔵 Layer 3 — customers_safe VIEW 사용")
        else:
            st.success("🟢 Layer 3 — 일반 테이블 접근")


# =============================================================
# Tool Call 렌더링
# =============================================================

def render_tool_call(tc: ToolCall, idx: int) -> None:
    """개별 tool call을 접을 수 있는 블록으로 표시."""
    # 상태 아이콘
    if tc.is_error:
        icon = "🔴"
        status = f"ERROR · {tc.error_type}"
    else:
        icon = "✅"
        status = "OK"

    # 요약 (header) — SQL은 미리보기
    if tc.name == "execute_readonly_sql":
        query = str(tc.input.get("query", ""))
        preview = query.strip().split("\n")[0][:80]
        header = f"{icon} [{idx}] `{tc.name}` · {status} · {tc.elapsed_ms}ms · `{preview}...`"
    else:
        header = f"{icon} [{idx}] `{tc.name}({tc.input})` · {status} · {tc.elapsed_ms}ms"

    with st.expander(header, expanded=tc.is_error):
        # Input
        if tc.name == "execute_readonly_sql":
            st.markdown("**SQL Query:**")
            st.code(tc.input.get("query", ""), language="sql")
        else:
            st.markdown("**Input:**")
            st.code(json.dumps(tc.input, ensure_ascii=False, indent=2), language="json")

        # Output
        st.markdown("**Result:**")
        try:
            parsed = json.loads(tc.output_raw)
            # 에러/성공 case 분기 렌더링
            if tc.is_error:
                st.error(f"**{parsed.get('type', 'Error')}**: {parsed.get('error', tc.output_raw)}")
                if "suggested_alternative" in parsed:
                    st.info(f"💡 Suggested: {parsed['suggested_alternative']}")
            else:
                # list_tables / describe_table / execute_readonly_sql 결과
                if "rows" in parsed and "columns" in parsed:
                    # SQL 결과 테이블
                    rows = parsed.get("rows", [])
                    if rows:
                        st.dataframe(rows, use_container_width=True)
                        st.caption(
                            f"{parsed.get('row_count', len(rows))}행"
                            + (" · 잘림(truncated)" if parsed.get("truncated") else "")
                        )
                    else:
                        st.info("결과 0행")
                elif "tables" in parsed:
                    # list_tables
                    st.json(parsed)
                elif "columns" in parsed:
                    # describe_table
                    st.json(parsed)
                else:
                    st.json(parsed)
        except json.JSONDecodeError:
            st.code(tc.output_raw[:1000])


def render_tool_timeline(tool_calls: list[ToolCall]) -> None:
    """Tool 호출 타임라인 전체."""
    if not tool_calls:
        st.caption("호출된 MCP tool 없음")
        return

    total_ms = sum(tc.elapsed_ms for tc in tool_calls)
    errors = sum(1 for tc in tool_calls if tc.is_error)

    st.caption(
        f"🔧 총 {len(tool_calls)}회 호출 · {total_ms}ms"
        + (f" · 에러 {errors}건" if errors else "")
    )

    for i, tc in enumerate(tool_calls, 1):
        render_tool_call(tc, i)


# =============================================================
# Plan 렌더링
# =============================================================

def render_plan(result: PipelineResult) -> None:
    if result.plan is None:
        st.caption("Plan 없음 (Planner 실패)")
        return

    plan = result.plan
    st.markdown(f"**Intent:** {plan.intent}")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Tables needed (business-level):**")
        for t in plan.tables_needed:
            st.markdown(f"- {t}")
        st.markdown("**Aggregations:**")
        for a in plan.aggregations:
            st.markdown(f"- {a}")
    with col2:
        st.markdown("**Filters:**")
        for f in plan.filters:
            st.markdown(f"- {f}")
        st.markdown("**Expected columns:**")
        for c in plan.expected_columns:
            st.markdown(f"- {c}")

    if plan.caveats:
        st.markdown("**Caveats:**")
        for cv in plan.caveats:
            st.markdown(f"- {cv}")


# =============================================================
# Execution Result 렌더링
# =============================================================

def render_execution_result(exec_result: dict[str, Any] | None) -> None:
    if exec_result is None:
        st.caption("실행 결과 없음")
        return

    if "error" in exec_result and "type" in exec_result:
        st.error(f"**{exec_result['type']}**: {exec_result['error']}")
        return

    rows = exec_result.get("rows", [])
    if rows:
        st.dataframe(rows, use_container_width=True)
        st.caption(
            f"총 {exec_result.get('row_count', len(rows))}행"
            + (" · 잘림(truncated)" if exec_result.get("truncated") else "")
        )
    else:
        st.info("결과 0행")
