"""
Agent 대화 페이지 — 기존 단일 페이지의 에이전트 섹션을 함수로 추출.

st.navigation() 환경에서 호출됨. 사이드바 프리셋은 이 페이지 전용이므로
함수 내부에서 `with st.sidebar:`로 추가.

세션 상태와 핸들러는 이 모듈에 locality를 맞춰 두지만, 값 자체는
st.session_state 에 저장되므로 다른 페이지로 이동했다 돌아와도 유지된다.
"""
from __future__ import annotations

import time

import streamlit as st

from app.agents.orchestrator import run, PipelineResult
from app.ui.presets import CORE_8, SCENE_3_MULTITURN, ADVANCED_3, Preset
from app.ui import rendering


# =============================================================
# 멀티턴 정책
# =============================================================

MAX_TURNS = 3  # Scene 3 시연 스코프

# 이 키들을 누르면 '현재 대화 유지' — T2·T3는 T1 위에 누적.
_CONTINUE_PRESET_KEYS = {"S3-T2", "S3-T3"}
_SCENE3_PRESET_KEYS = {"S3-T1", "S3-T2", "S3-T3"}


# =============================================================
# 세션 상태 헬퍼
# =============================================================

def _init_state() -> None:
    """페이지 진입 시 필요 키 보장. 다른 페이지에서 돌아와도 idempotent."""
    if "question_input" not in st.session_state:
        st.session_state.question_input = ""
    if "conversation" not in st.session_state:
        st.session_state.conversation = []
    if "_running" not in st.session_state:
        st.session_state._running = False
    if "_pending_run" not in st.session_state:
        # {"question": str, "use_cache": bool, "history": list|None} or None
        st.session_state._pending_run = None
    # Scene 3 프리셋을 한 번이라도 누르면 True. "새 대화" 시 False.
    # 이 플래그가 True 일 때만 T2/T3 continuation chip 을 노출.
    if "_scene3_active" not in st.session_state:
        st.session_state._scene3_active = False

    # Streamlit은 위젯이 렌더된 뒤 같은 run에서 해당 키의 session_state를
    # 쓰면 예외를 던진다. 다음 run 시작 시점(위젯 렌더 전)에 비우기 위한 플래그.
    if st.session_state.pop("_clear_question_pending", False):
        st.session_state.question_input = ""


def _reset_conversation() -> None:
    st.session_state.conversation = []
    st.session_state._scene3_active = False


def _set_question_from_preset(preset: Preset) -> None:
    """프리셋 클릭 핸들러.

    단일턴 프리셋(C1–C8, A1–A3)은 새 대화로 리셋.
    Scene 3 프리셋(T1/T2/T3): T1은 새 대화로 시작, T2·T3는 기존 대화에 이어붙임.
    어느 쪽이든 _scene3_active 를 True 로 두어 continuation 칩 노출 자격을 둔다.
    """
    st.session_state.question_input = preset.question
    if preset.key not in _CONTINUE_PRESET_KEYS:
        _reset_conversation()
    if preset.key in _SCENE3_PRESET_KEYS:
        st.session_state._scene3_active = True


def _history_for_planner() -> list[dict] | None:
    """conversation → Planner용 history 포맷."""
    if not st.session_state.conversation:
        return None
    return [
        {"question": t["question"], "answer": t["answer"]}
        for t in st.session_state.conversation
    ]


# =============================================================
# 메인 영역 — 초기 상태 프리셋 그리드 (conversation 비어있을 때)
# =============================================================

def _preset_button(preset: Preset, key_suffix: str = "") -> None:
    """공통 프리셋 버튼 렌더. key_suffix 로 위치별 고유 키 부여."""
    help_text = preset.note or ""
    if preset.scene:
        help_text = f"**{preset.scene}** · {help_text}"
    st.button(
        preset.label,
        key=f"btn_{preset.key}{key_suffix}",
        help=help_text,
        on_click=_set_question_from_preset,
        args=(preset,),
        use_container_width=True,
    )


def _render_main_presets() -> None:
    """첫 질문 전에 메인 영역에 표시되는 프리셋 카드 그리드.

    Scene 3 T2/T3 는 T1 실행 후에만 의미가 있으므로 여기서는 T1 만 노출.
    """
    st.markdown("### 🎯 시연 프리셋")

    with st.container(border=True):
        st.markdown("**Core 8** · 회귀 + 시연 시나리오")
        # 4 cols × 2 rows
        for row_start in (0, 4):
            cols = st.columns(4)
            for i, col in enumerate(cols):
                idx = row_start + i
                if idx < len(CORE_8):
                    with col:
                        _preset_button(CORE_8[idx])

    st.markdown("")

    scene_col, adv_col = st.columns([1, 2])
    with scene_col:
        with st.container(border=True):
            st.markdown("**Scene 3 멀티턴** · 최대 3턴 드릴다운")
            _preset_button(SCENE_3_MULTITURN[0])  # T1
            st.caption("T2·T3 는 T1 실행 후 상단에 표시됩니다.")
    with adv_col:
        with st.container(border=True):
            st.markdown("**Advanced Q&A** · 모호성·기준 설정")
            acols = st.columns(len(ADVANCED_3))
            for p, col in zip(ADVANCED_3, acols):
                with col:
                    _preset_button(p)


def _render_continuation_hints() -> None:
    """Scene 3 대화 진행 중에 다음 턴(T2/T3) 제안 칩.

    conv_len == 1 이면 T2·T3 모두 노출 (사용자가 점프 가능하도록).
    conv_len == 2 이면 T3 만 의미가 있지만 T2 도 여전히 클릭 가능 (새 대화 없이
    기존 턴에 이어붙는 동작은 _set_question_from_preset 정책에 따름).
    """
    t2, t3 = SCENE_3_MULTITURN[1], SCENE_3_MULTITURN[2]
    with st.container(border=True):
        hint_col, btn_col_2, btn_col_3 = st.columns([2, 2, 2])
        with hint_col:
            st.markdown("**🎬 Scene 3 다음 턴 제안**")
            st.caption("이전 턴 맥락을 이어받습니다.")
        with btn_col_2:
            _preset_button(t2, key_suffix="_cont")
        with btn_col_3:
            _preset_button(t3, key_suffix="_cont")


# =============================================================
# 메인 페이지 렌더
# =============================================================

def render_agent_page() -> None:
    """Agent 대화 페이지 전체. st.navigation 에서 호출됨."""
    _init_state()

    st.title("SURI — 보험 상품 Data Agent")
    st.caption(
        "3-Agent pipeline (Planner → Executor → Critic) · "
        "MCP stdio · PostgreSQL 15 · 3층 PII 방어"
    )

    conv_len = len(st.session_state.conversation)
    turn_cap_reached = conv_len >= MAX_TURNS
    is_running = st.session_state._running

    # 대화 진행 중: 턴 표시 + 새 대화 버튼
    if conv_len > 0:
        col_turn, col_reset = st.columns([5, 1])
        with col_turn:
            # 완료된 턴 수 기준. 첫 실행 직후엔 "1/3 완료".
            suffix = "  — 최대 턴 도달. 새 대화를 시작하세요." if turn_cap_reached else ""
            st.info(f"🗂️ 대화 진행 중 · {conv_len}/{MAX_TURNS}턴 완료{suffix}")
        with col_reset:
            if st.button("🔄 새 대화", use_container_width=True):
                _reset_conversation()
                st.session_state.pop("_last_run_error", None)
                st.session_state._clear_question_pending = True
                st.rerun()

        # Scene 3 T2/T3 continuation chips — Scene 3 프리셋을 한 번이라도
        # 누른 대화에서만 노출 (일반 Core 8/Advanced 대화에는 표시하지 않음).
        if (
            st.session_state._scene3_active
            and not turn_cap_reached
            and not is_running
        ):
            _render_continuation_hints()

    # 질문 입력 + 실행 + 캐시 토글
    col_q, col_btn, col_cache = st.columns([6, 1, 1])
    with col_q:
        question = st.text_input(
            "질문을 입력하거나 아래 프리셋 선택:",
            key="question_input",
            label_visibility="collapsed",
            placeholder="예: 판매채널별 13회차 유지율 어때?",
            disabled=turn_cap_reached or is_running,
        )
    with col_btn:
        run_clicked = st.button(
            "⏳ 실행 중..." if is_running else "▶ 실행",
            type="primary",
            use_container_width=True,
            disabled=turn_cap_reached or is_running,
        )
    with col_cache:
        use_cache = st.toggle(
            "캐시", value=True, help="OFF 시 강제 재실행", disabled=is_running,
        )

    # 첫 질문 전에만 시연 프리셋 그리드 노출. 쿼리 실행이 트리거된 순간(run_clicked)
    # 부터는 바로 숨겨서 '로딩 중' 상태에서 프리셋이 잠깐 보이는 현상을 방지.
    if conv_len == 0 and not is_running and not run_clicked:
        st.markdown("")
        _render_main_presets()


    # =============================================================
    # 실행 — Pending-run 패턴
    # =============================================================
    #
    # 1) 클릭 턴: run_clicked=True, _pending_run에 요청 저장, _running=True, rerun.
    #    (이 턴 내에서는 이미 버튼이 그려진 뒤라 라벨을 바꿀 수 없다.)
    # 2) 실행 턴: 스크립트 상단에서 _running=True로 그려져 버튼 "⏳ 실행 중..." 상태.
    #    3단계 status 컨테이너를 만들고 run()에 on_event 콜백 전달.
    #    완료 후 대화 누적 → 플래그 리셋 → rerun.
    # 3) 최종 턴: 정상 렌더.

    run_result: PipelineResult | None = None

    # Step 1: 클릭 → 실행 요청 저장 후 즉시 rerun
    if run_clicked and question.strip() and not turn_cap_reached and not is_running:
        st.session_state._pending_run = {
            "question": question,
            "use_cache": use_cache,
            "history": _history_for_planner(),
        }
        st.session_state._running = True
        st.rerun()

    # Step 2: 대기 중인 실행 처리
    if is_running and st.session_state._pending_run is not None:
        pending = st.session_state._pending_run
        st.session_state._pending_run = None  # 재진입 방지

        pending_q: str = pending["question"]
        pending_use_cache: bool = pending["use_cache"]
        pending_history: list[dict] | None = pending["history"]

        # 진행 컨테이너 — 3단계 계층
        progress_area = st.container()
        with progress_area:
            st.markdown(f"**🤖 Agent 파이프라인 실행 중** — `{pending_q[:80]}`")
            planner_status = st.status("⏸ 1️⃣ Planner 대기", state="running",
                                       expanded=True)
            executor_status = st.status("⏸ 2️⃣ Executor 대기", state="running",
                                        expanded=True)
            critic_status = st.status("⏸ 3️⃣ Critic 대기", state="running",
                                      expanded=True)

        stage_times: dict[str, float] = {}
        stage_durations: dict[str, float] = {}  # 완료된 stage의 실측 duration(s)
        tool_slots: list = []  # st.empty() FIFO — tool_start↔tool_done 매칭

        def on_event(evt: dict) -> None:
            stage = evt.get("stage")
            typ = evt.get("type")
            data = evt.get("data", {})
            now = time.monotonic()

            if stage == "planner":
                if typ == "start":
                    stage_times["planner"] = now
                    planner_status.update(
                        label="⏳ 1️⃣ Planner 실행 중…",
                        state="running", expanded=True,
                    )
                elif typ == "done":
                    dur = now - stage_times.get("planner", now)
                    stage_durations["planner"] = dur
                    with planner_status:
                        intent = str(data.get("intent", ""))[:300]
                        tables = data.get("tables_needed") or []
                        if intent:
                            st.markdown(f"**Intent:** {intent}")
                        if tables:
                            st.caption("Tables (business-level): "
                                       + ", ".join(str(t) for t in tables[:5]))
                    planner_status.update(
                        label=f"✅ 1️⃣ Planner ({dur:.1f}s)",
                        state="complete", expanded=True,
                    )
                elif typ == "error":
                    planner_status.update(
                        label=f"🔴 1️⃣ Planner 실패 — {data.get('error','')[:100]}",
                        state="error", expanded=True,
                    )

            elif stage == "executor":
                if typ == "start":
                    stage_times["executor"] = now
                    executor_status.update(
                        label="⏳ 2️⃣ Executor 실행 중…",
                        state="running", expanded=True,
                    )
                elif typ == "tool_start":
                    name = data.get("name", "?")
                    with executor_status:
                        slot = st.empty()
                    slot.markdown(f"⏳ `{name}` 호출 중…")
                    tool_slots.append(slot)
                elif typ == "tool_done":
                    name = data.get("name", "?")
                    ms = int(data.get("duration_ms", 0))
                    is_err = bool(data.get("is_error"))
                    err_type = data.get("error_type") or ""
                    icon = "🔴" if is_err else "✅"
                    tail = f" · {err_type}" if is_err and err_type else ""
                    line = f"{icon} `{name}` — {ms}ms{tail}"
                    if tool_slots:
                        slot = tool_slots.pop(0)  # FIFO — tool_use는 순차 실행
                        slot.markdown(line)
                    else:
                        with executor_status:
                            st.markdown(line)
                elif typ == "retry":
                    with executor_status:
                        attempt = data.get("attempt", "?")
                        reason = data.get("reason", "")
                        st.markdown(f"🔁 자가 교정 재시도 #{attempt} — {reason}")
                elif typ == "done":
                    dur = now - stage_times.get("executor", now)
                    stage_durations["executor"] = dur
                    tc = data.get("tool_count", 0)
                    ec = data.get("error_count", 0)
                    suffix = f" · {tc} tool" + (f" · 에러 {ec}" if ec else "")
                    executor_status.update(
                        label=f"✅ 2️⃣ Executor ({dur:.1f}s){suffix}",
                        state="complete", expanded=True,
                    )
                elif typ == "error":
                    executor_status.update(
                        label=f"🔴 2️⃣ Executor 실패 — {data.get('error','')[:100]}",
                        state="error", expanded=True,
                    )

            elif stage == "critic":
                if typ == "start":
                    stage_times["critic"] = now
                    critic_status.update(
                        label="⏳ 3️⃣ Critic 실행 중…",
                        state="running", expanded=True,
                    )
                elif typ == "done":
                    dur = now - stage_times.get("critic", now)
                    stage_durations["critic"] = dur
                    critic_status.update(
                        label=f"✅ 3️⃣ Critic ({dur:.1f}s)",
                        state="complete", expanded=True,
                    )
                elif typ == "error":
                    critic_status.update(
                        label=f"🔴 3️⃣ Critic 실패 — {data.get('error','')[:100]}",
                        state="error", expanded=True,
                    )

        # 캐시 HIT은 run() 내부에서 합성 이벤트로 흘러나온다
        run_cache_hit = False
        if pending_use_cache:
            from app.agents.cache import load_cached
            run_cache_hit = load_cached(
                pending_q, history=pending_history,
            ) is not None

        t0 = time.monotonic()
        try:
            result = run(
                pending_q,
                use_cache=pending_use_cache,
                history=pending_history,
                on_event=on_event,
            )
        finally:
            elapsed = time.monotonic() - t0

        # 남은 in-progress tool 슬롯 정리 (비정상 종료 시)
        for leftover in tool_slots:
            try:
                leftover.markdown("⚠️ 호출 중단")
            except Exception:
                pass

        # 대화 누적 — 에러 턴은 history에 남기지 않음
        if not result.error:
            st.session_state.conversation.append({
                "question": pending_q,
                "answer": result.answer,
                "result": result,
                "elapsed": elapsed,
                "cache_hit": run_cache_hit,
                "stage_durations": dict(stage_durations),
            })
            st.session_state._clear_question_pending = True
            st.session_state.pop("_last_run_error", None)
        else:
            # 에러 상세는 rerun 너머까지 보존한다 (로컬 변수로는 소실됨)
            st.session_state._last_run_error = {
                "question": pending_q,
                "answer": result.answer,
                "error": result.error,
            }

        # 플래그 해제 후 재렌더
        st.session_state._running = False
        st.rerun()


    # =============================================================
    # 결과 표시
    # =============================================================

    last_error = st.session_state.get("_last_run_error")

    if not st.session_state.conversation and last_error is None and not is_running:
        st.info("👈 왼쪽 사이드바에서 프리셋을 선택하거나 위에 질문을 입력하고 실행하세요.")
    else:
        # 최근 실행 에러는 누적되지 않고 최상단에 한 번 표시
        if last_error is not None:
            st.markdown("---")
            st.error(f"**파이프라인 에러:** {last_error['error']}")
            st.caption(f"질문: {last_error['question']}")
            st.markdown("### 💬 답변")
            st.markdown(last_error["answer"])

        # 누적된 턴들 — 최신이 위로 오도록 역순 렌더. turn_idx는 생성 순서
        # (Turn 3이 최상단이어도 번호는 "Turn 3"으로 유지).
        numbered = list(enumerate(st.session_state.conversation, 1))
        for idx, turn in reversed(numbered):
            st.markdown("---")
            rendering.render_conversation_turn(
                turn_idx=idx,
                question=turn["question"],
                result=turn["result"],
                elapsed=turn["elapsed"],
                cache_hit=turn["cache_hit"],
                stage_durations=turn.get("stage_durations"),
            )

        if turn_cap_reached:
            st.markdown("---")
            st.warning(
                f"🔁 Scene 3 멀티턴 최대 턴({MAX_TURNS})에 도달했습니다. "
                "**🔄 새 대화** 버튼으로 초기화하세요."
            )
