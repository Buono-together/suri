"""
SURI — Streamlit 시연 UI

구성:
- 사이드바: 골든셋 Core 8 + Scene 3 + Advanced 3 프리셋 버튼 + 캐시 제어
- 메인:
  1. 질문 입력 + 실행 버튼
  2. Critic 답변 (메인 콘텐츠)
  3. 3층 방어 상태 배지
  4. Planner 플랜 (expander)
  5. Tool 호출 타임라인 (expander, SQL 원문 포함)
  6. 최종 실행 결과 테이블 (expander)
  7. 에러 발생 시 하이라이트

실행: streamlit run app/streamlit_app.py
"""
from __future__ import annotations

import time

import streamlit as st

from app.agents.orchestrator import run, PipelineResult
from app.agents.cache import clear_cache, CACHE_DIR
from app.ui.presets import CORE_8, SCENE_3_MULTITURN, ADVANCED_3, Preset
from app.ui import rendering


# =============================================================
# 페이지 설정
# =============================================================

st.set_page_config(
    page_title="SURI — Data Agent PoC",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =============================================================
# 세션 상태 초기화
# =============================================================

if "question_input" not in st.session_state:
    st.session_state.question_input = ""
if "result" not in st.session_state:
    st.session_state.result = None
if "elapsed" not in st.session_state:
    st.session_state.elapsed = None
if "cache_hit" not in st.session_state:
    st.session_state.cache_hit = False


def set_question_from_preset(preset: Preset) -> None:
    """프리셋 버튼 핸들러. 질문만 채우고 실행은 하지 않음.

    text_input의 widget key에 직접 써야 렌더 시 반영된다
    (value=와 key=를 동시에 쓰면 key 쪽 state가 우선).
    """
    st.session_state.question_input = preset.question


# =============================================================
# 사이드바: 프리셋 + 캐시 제어
# =============================================================

with st.sidebar:
    st.markdown("## 🎯 SURI")
    st.caption("Data Agent PoC · 한화생명 지원용")

    st.markdown("---")
    st.markdown("### Core 8 (회귀 + 시연)")
    for p in CORE_8:
        help_text = p.note or ""
        if p.scene:
            help_text = f"**{p.scene}** · {help_text}"
        st.button(
            p.label,
            key=f"btn_{p.key}",
            help=help_text,
            on_click=set_question_from_preset,
            args=(p,),
            use_container_width=True,
        )

    st.markdown("---")
    st.markdown("### Scene 3 멀티턴")
    st.caption("현재는 단일턴 재현만 지원")
    for p in SCENE_3_MULTITURN:
        st.button(
            p.label,
            key=f"btn_{p.key}",
            help=p.note,
            on_click=set_question_from_preset,
            args=(p,),
            use_container_width=True,
        )

    st.markdown("---")
    st.markdown("### Advanced Q&A")
    for p in ADVANCED_3:
        st.button(
            p.label,
            key=f"btn_{p.key}",
            help=p.note,
            on_click=set_question_from_preset,
            args=(p,),
            use_container_width=True,
        )

    st.markdown("---")
    st.markdown("### ⚙️ 캐시 제어")
    cache_files = list(CACHE_DIR.glob("*.json")) if CACHE_DIR.exists() else []
    st.caption(f"저장된 응답: {len(cache_files)}개")
    if st.button("🗑️ 캐시 전체 삭제", use_container_width=True):
        n = clear_cache()
        st.success(f"{n}개 삭제됨")
        st.rerun()


# =============================================================
# 메인: 제목 + 질문 입력
# =============================================================

st.title("SURI — 보험 상품 Data Agent")
st.caption(
    "3-Agent pipeline (Planner → Executor → Critic) · "
    "MCP stdio · PostgreSQL 15 · 3층 PII 방어"
)

col_q, col_btn, col_cache = st.columns([6, 1, 1])
with col_q:
    question = st.text_input(
        "질문을 입력하거나 왼쪽 프리셋 선택:",
        key="question_input",
        label_visibility="collapsed",
        placeholder="예: 판매채널별 13회차 유지율 어때?",
    )
with col_btn:
    run_clicked = st.button("▶ 실행", type="primary", use_container_width=True)
with col_cache:
    use_cache = st.toggle("캐시", value=True, help="OFF 시 강제 재실행")


# =============================================================
# 실행
# =============================================================

if run_clicked and question.strip():
    with st.status("Agent 파이프라인 실행 중…", expanded=True) as status:
        t0 = time.monotonic()

        # 캐시 hit 체크 (UI 표시용 — 실제 판정은 run() 내부)
        from app.agents.cache import load_cached
        cached = load_cached(question) if use_cache else None
        if cached:
            status.update(label="캐시에서 로드 중…", state="running")
            st.session_state.cache_hit = True
        else:
            st.session_state.cache_hit = False
            status.update(label="Planner 실행…", state="running")

        result = run(question, use_cache=use_cache)
        elapsed = time.monotonic() - t0

        st.session_state.result = result
        st.session_state.elapsed = elapsed

        if result.error:
            status.update(label=f"완료 (에러: {result.error[:50]})", state="error")
        else:
            status.update(label=f"완료 ({elapsed:.1f}s)", state="complete")


# =============================================================
# 결과 표시
# =============================================================

result: PipelineResult | None = st.session_state.result

if result is None:
    st.info("👈 왼쪽 사이드바에서 프리셋을 선택하거나 위에 질문을 입력하고 실행하세요.")
else:
    elapsed = st.session_state.elapsed or 0
    cache_hit = st.session_state.cache_hit

    # 메타 배지
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    col_m1.metric("Latency", f"{elapsed:.1f}s")
    col_m2.metric("Tool 호출", len(result.tool_calls))
    col_m3.metric(
        "에러",
        sum(1 for tc in result.tool_calls if tc.is_error),
    )
    col_m4.metric("캐시", "HIT" if cache_hit else "MISS")

    st.markdown("---")

    # 에러 케이스
    if result.error:
        st.error(f"**파이프라인 에러:** {result.error}")

    # 3층 방어 상태
    rendering.render_governance_status(result)

    st.markdown("---")

    # Critic 답변 (메인)
    st.markdown("### 💬 답변")
    st.markdown(result.answer)

    st.markdown("---")

    # Plan (expander)
    with st.expander("📋 Planner 플랜 (비즈니스 용어)", expanded=False):
        rendering.render_plan(result)

    # Tool timeline
    with st.expander("🔧 Tool 호출 타임라인 (MCP + SQL)", expanded=False):
        rendering.render_tool_timeline(result.tool_calls)

    # Execution result — execute_readonly_sql 호출이 있었던 경우에만
    # (C5 하드 블록은 Schema 단계에서 종료되므로 describe_table 결과를
    #  "최종 실행 결과"로 오해시키지 않도록 expander 자체를 숨긴다)
    sql_executed = any(
        tc.name == "execute_readonly_sql" for tc in result.tool_calls
    )
    if sql_executed:
        with st.expander("📊 최종 실행 결과", expanded=False):
            rendering.render_execution_result(result.execution_result)
    else:
        st.caption(
            "📊 최종 실행 결과 없음 — Schema 단계에서 종료 (SQL 미실행)"
        )
