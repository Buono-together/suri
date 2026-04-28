"""
Streamlit 렌더링 헬퍼.

각 뷰 섹션의 표시 로직 분리. streamlit_app.py 본문 간결 유지 목적.
"""
from __future__ import annotations

import json
import re
from typing import Any

import streamlit as st

from app.agents.executor import ToolCall
from app.agents.orchestrator import PipelineResult


# LLM 답변 중 숫자 범위 표기("25~28만", "2,000~4,000억") 의 단일 틸드를
# Streamlit 프런트엔드 마크다운이 strikethrough 로 해석해 한 ~부터 다른 ~
# 까지를 통째로 취소선으로 렌더하는 현상이 관찰됨. 이를 방지하려면
# 1) ~~...~~ 페어는 내부 텍스트만 살리고 제거,
# 2) 남은 단일 ~ 는 마크다운 이스케이프(\~) 처리하여 strikethrough 해석 차단.
_STRIKETHROUGH_RE = re.compile(r"~~(.+?)~~", flags=re.DOTALL)


def _sanitize_tildes(text: str) -> str:
    text = _STRIKETHROUGH_RE.sub(r"\1", text)
    return text.replace("~", r"\~")


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

    # 3 layer 뱃지를 st.columns + st.success 로 분리 렌더하면 주변 여백이
    # 불균형해지는 문제가 있어, 단일 HTML flex 블록으로 렌더. 외부 margin 을
    # 질문/답변 박스와 동일하게 잡아 시각 균형 확보.
    _STYLE_OK = "background:#e6f4ea; color:#137333; border:1px solid #b7dfbe;"
    _STYLE_INFO = "background:#e8f0fe; color:#1967d2; border:1px solid #bcd0f7;"
    _STYLE_ERR = "background:#fce8e6; color:#c5221f; border:1px solid #f4b7b1;"

    def _badge(style: str, text: str) -> str:
        return (
            f'<div style="{style} padding:10px 14px; border-radius:6px; '
            f'flex:1; font-size:0.92rem; line-height:1.35;">{text}</div>'
        )

    layer1_html = _badge(
        _STYLE_ERR, "🔴 Layer 1 — SQL Guard 차단 발생",
    ) if layer1_blocked else _badge(
        _STYLE_OK, "🟢 Layer 1 — SQL Guard 통과",
    )
    layer2_html = _badge(_STYLE_OK, "🟢 Layer 2 — suri_readonly ROLE")
    if not sql_executed:
        layer3_html = _badge(
            _STYLE_INFO, "🔵 Layer 3 — Schema 차단 (원본 테이블/PII 컬럼 부재)",
        )
    elif layer3_safe_view:
        layer3_html = _badge(
            _STYLE_INFO, "🔵 Layer 3 — customers_safe VIEW 사용",
        )
    else:
        layer3_html = _badge(_STYLE_OK, "🟢 Layer 3 — 일반 테이블 접근")

    st.markdown(
        '<div style="display:flex; gap:12px; margin:6px 0;">'
        + layer1_html + layer2_html + layer3_html
        + '</div>',
        unsafe_allow_html=True,
    )


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
# Conversation (multi-turn) 턴 렌더링
# =============================================================

def render_conversation_turn(
    turn_idx: int,
    question: str,
    result: PipelineResult,
    elapsed: float | None = None,
    cache_hit: bool = False,
    stage_durations: dict[str, float] | None = None,
) -> None:
    """지난 턴 렌더 — 실행 중 UI와 동일하게 Planner/Executor/Critic 3단계로 그룹핑.

    stage_durations가 주어지면 각 단계 expander 라벨에 duration을 표기.
    주어지지 않아도(예: 이전 포맷 캐시) 안전하게 생략.
    """
    sd = stage_durations or {}

    meta_bits = [f"Turn {turn_idx}"]
    if elapsed is not None:
        meta_bits.append(f"{elapsed:.1f}s")
    meta_bits.append("Tool " + str(len(result.tool_calls)))
    if cache_hit:
        meta_bits.append("캐시 HIT")
    st.caption(" · ".join(meta_bits))

    # 질문 / 답변 컨테이너: inline style 로 직접 주입 (DOM 구조 변경에 영향 X).
    # padding top·bottom 을 대칭으로 잡고, 라벨/본문 사이 간격을 답변과 동일하게.
    _BOX_PADDING = "16px 20px 18px 20px"

    safe_question = _sanitize_tildes(question)
    st.markdown(
        f'''<div style="background-color:#eef0f3; border:1px solid #cfd3d9; '''
        f'''border-radius:8px; padding:{_BOX_PADDING}; margin:6px 0;">\n\n'''
        f'''**🗣️ 질문**\n\n{safe_question}\n\n</div>''',
        unsafe_allow_html=True,
    )

    render_governance_status(result)

    # 답변 — 약간 더 진한 회색 + 좌측 strip 강조.
    safe_answer = _sanitize_tildes(result.answer)
    st.markdown(
        f'''<div style="background-color:#e3e7ec; border:1px solid #c0c6ce; '''
        f'''border-left:4px solid #6b7280; border-radius:8px; '''
        f'''padding:{_BOX_PADDING}; margin:6px 0;">\n\n'''
        f'''**💬 답변**\n\n{safe_answer}\n\n</div>''',
        unsafe_allow_html=True,
    )

    st.markdown("**🤖 Agent 파이프라인**")

    # 1️⃣ Planner
    planner_label = "✅ 1️⃣ Planner"
    if "planner" in sd:
        planner_label += f" ({sd['planner']:.1f}s)"
    with st.expander(planner_label, expanded=True):
        render_plan(result)

    # 2️⃣ Executor — tool 호출만 (최종 실행 결과는 아래 분리)
    executor_label = "✅ 2️⃣ Executor"
    if "executor" in sd:
        executor_label += f" ({sd['executor']:.1f}s)"
    tool_count = len(result.tool_calls)
    err_count = sum(1 for tc in result.tool_calls if tc.is_error)
    executor_label += f" · {tool_count} tool"
    if err_count:
        executor_label += f" · 에러 {err_count}"

    with st.expander(executor_label, expanded=True):
        render_tool_timeline(result.tool_calls)

    # 3️⃣ Critic — 전용 데이터가 없어 메타정보만 노출
    critic_label = "✅ 3️⃣ Critic"
    if "critic" in sd:
        critic_label += f" ({sd['critic']:.1f}s)"
    critic_label += f" · 답변 {len(result.answer)}자"
    with st.expander(critic_label, expanded=True):
        st.caption(
            "Critic은 도메인 벤치마크·proxy 선긋기·거버넌스 경로 보고를 "
            "자연어 답변으로 합성하는 단계입니다. 출력은 위 **💬 답변** 섹션에 표시."
        )

    # 최종 실행 결과 — 파이프라인 3단계와 분리. Critic 답변의 원천 데이터.
    sql_executed = any(
        tc.name == "execute_readonly_sql" for tc in result.tool_calls
    )
    if sql_executed:
        st.markdown("**📊 최종 실행 결과** — Critic이 해석한 원천 데이터")
        with st.container(border=True):
            render_execution_result(result.execution_result)
    else:
        st.caption(
            "📊 최종 실행 결과 없음 — Schema 단계에서 종료 (SQL 미실행)"
        )


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
