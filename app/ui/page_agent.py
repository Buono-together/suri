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
    """프리셋 클릭 핸들러 — 입력창에 질문만 채움 (전체 프리셋 카드용).

    단일턴 프리셋(C1–C8, A1–A3)은 새 대화로 리셋.
    Scene 3 프리셋(T1/T2/T3): T1은 새 대화로 시작, T2·T3는 기존 대화에 이어붙임.
    어느 쪽이든 _scene3_active 를 True 로 두어 continuation 칩 노출 자격을 둔다.
    """
    st.session_state.question_input = preset.question
    if preset.key not in _CONTINUE_PRESET_KEYS:
        _reset_conversation()
    if preset.key in _SCENE3_PRESET_KEYS:
        st.session_state._scene3_active = True


def _set_question_and_run_from_preset(preset: Preset) -> None:
    """추천 카드 전용 — 입력 + 즉시 실행 예약.

    on_click 콜백 안에서 _pending_run / _running 만 세팅하면, Streamlit이
    콜백 종료 직후 자동으로 rerun 하면서 기존 'pending-run 패턴' 분기에
    진입한다. 별도 st.rerun() 호출 불필요.

    use_cache 는 admin 페이지에서 컨트롤하는 _admin_use_cache 세션 키를
    참조하며, 미설정 시 기본값 False (일반 방문자는 캐시 미사용).
    """
    _set_question_from_preset(preset)

    # 단일턴 프리셋은 위에서 _reset_conversation 됐으므로 history None.
    # T2/T3 (continue 키) 는 추천에 포함되지 않지만, 안전을 위해 분기 유지.
    if preset.key in _CONTINUE_PRESET_KEYS:
        history = _history_for_planner()
    else:
        history = None

    st.session_state._pending_run = {
        "question": preset.question,
        "use_cache": st.session_state.get("_admin_use_cache", False),
        "history": history,
    }
    st.session_state._running = True


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
    """공통 프리셋 버튼 렌더 — continuation chip(T2·T3) 전용.

    key_suffix 로 위치별 고유 키 부여.
    """
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


# 카드 우상단 배지 — 색은 의미군별로만 구분 (정보 우선, 장식 최소).
_BADGE_STYLES: dict[str, str] = {
    "추천":     "background:#fef3c7; color:#92400e; border:1px solid #fcd34d;",
    "도메인":   "background:#e0e7ff; color:#3730a3; border:1px solid #c7d2fe;",
    "조회통제": "background:#fee2e2; color:#991b1b; border:1px solid #fca5a5;",
    "멀티턴":   "background:#cffafe; color:#155e75; border:1px solid #67e8f9;",
    "기준설정": "background:#ffedd5; color:#9a3412; border:1px solid #fdba74;",
}
_BADGE_FALLBACK = "background:#f3f4f6; color:#4b5563; border:1px solid #d1d5db;"


def _badges_html(badges: tuple[str, ...]) -> str:
    if not badges:
        return ""
    parts = []
    for b in badges:
        style = _BADGE_STYLES.get(b, _BADGE_FALLBACK)
        parts.append(
            f'<span style="{style} padding:2px 8px; border-radius:10px; '
            f'font-size:0.7rem; margin-left:4px; vertical-align:middle; '
            f'white-space:nowrap;">{b}</span>'
        )
    return "".join(parts)


def _render_preset_card(
    preset: Preset,
    key_suffix: str = "",
    auto_run: bool = False,
) -> None:
    """카드 컨테이너: 코드 · 제목 + 배지 + 질문 본문 + 입력/실행 버튼.

    auto_run=True  → 추천 카드. 클릭 시 입력 + 즉시 실행. 라벨 "▶ 바로 실행".
    auto_run=False → 일반 카드. 클릭 시 입력만. 라벨 "↗ 질문 입력".
    """
    title_text = preset.title or preset.label.split(" · ", 1)[-1]
    header_html = (
        f'<div style="font-weight:600; font-size:0.95rem; line-height:1.4; '
        f'margin-bottom:8px;">'
        f'{preset.key} · {title_text}{_badges_html(preset.badges)}'
        f'</div>'
    )
    body_html = (
        f'<div style="color:#374151; font-size:0.85rem; line-height:1.5; '
        f'min-height:60px; margin-bottom:10px; word-break:keep-all;">'
        f'{preset.question}</div>'
    )
    if auto_run:
        btn_label = "▶ 바로 실행"
        on_click = _set_question_and_run_from_preset
        btn_type = "primary"
    else:
        btn_label = "↗ 질문 입력"
        on_click = _set_question_from_preset
        btn_type = "secondary"

    with st.container(border=True):
        st.markdown(header_html + body_html, unsafe_allow_html=True)
        st.button(
            btn_label,
            key=f"card_{preset.key}{key_suffix}",
            on_click=on_click,
            args=(preset,),
            use_container_width=True,
            type=btn_type,
            help=preset.note or "",
        )


# 추천 카드 — 첫 진입 면접관에게 보여주는 핵심 3개.
# 각각 다른 축(도메인 분석 / 조회 통제 / 멀티턴 드릴다운) 을 대표한다.
_RECOMMENDED_KEYS = ("C1", "C4", "S3-T1")


def _render_main_presets() -> None:
    """첫 질문 전 idle 상태 메인 영역.

    구조:
      1) 추천 시나리오 3개 (C1·C4·S3-T1)
      2) 대표 분석 질문 (Core 8) — 4×2 카드 그리드
      3) 멀티턴 드릴다운 (Scene 3) + 기준 설정이 필요한 질문 (Advanced Q&A)

    Scene 3 T2/T3 는 T1 실행 후에만 의미가 있으므로 여기서는 T1 만 노출.
    """
    # ----- 1) 추천 시나리오 (원클릭 실행)
    st.markdown("### 처음이라면 — 추천 시나리오 3개")
    st.caption(
        "추천 시나리오는 전체 프리셋 중 면접 시연에 적합한 대표 흐름입니다. "
        "**▶ 바로 실행** 클릭 시 즉시 실행되며, "
        "Planner → Executor/Tool 호출 → SQL → Critic 흐름을 확인할 수 있습니다."
    )
    rec_presets = [_find_by_key(k) for k in _RECOMMENDED_KEYS]
    rec_cols = st.columns(3)
    for p, col in zip(rec_presets, rec_cols):
        if p is None:
            continue
        with col:
            _render_preset_card(p, key_suffix="_rec", auto_run=True)

    st.markdown("")
    st.markdown("---")
    st.markdown("### 전체 시연 프리셋")
    st.caption(
        "전체 프리셋은 카드의 **↗ 질문 입력** 으로 위 입력창에 질문을 채운 뒤, "
        "**▶ 실행** 버튼으로 실행해주세요. (추천 3개와 일부 중복됩니다.)"
    )

    # ----- 2) Core 8 (질문 입력만)
    st.markdown("**대표 분석 질문 (Core 8)** · 회귀 + 시연 시나리오 (도메인 · 조회 통제 · 한계 인정)")
    for row_start in (0, 4):
        cols = st.columns(4)
        for i, col in enumerate(cols):
            idx = row_start + i
            if idx < len(CORE_8):
                with col:
                    _render_preset_card(CORE_8[idx])

    st.markdown("")

    # ----- 3) Scene 3 멀티턴 (단독 row, 좌측 1/3)
    st.markdown("**멀티턴 드릴다운 (Scene 3)**")
    scene_col, _ = st.columns([1, 2])
    with scene_col:
        _render_preset_card(SCENE_3_MULTITURN[0])
        st.caption("T2·T3 는 T1 실행 후 화면 상단에 표시됩니다.")

    st.markdown("")

    # ----- 4) Advanced Q&A — expander 로 접어 첫 화면 밀도 완화
    with st.expander(
        "**기준 설정이 필요한 질문 (Advanced Q&A)** · 모호성·기준 설정·proxy 한계 인정",
        expanded=False,
    ):
        adv_cols = st.columns(3)
        for p, col in zip(ADVANCED_3, adv_cols):
            with col:
                _render_preset_card(p)


def _find_by_key(key: str):
    """추천 카드용 헬퍼 — presets.find_by_key 와 동일 의미지만 모듈 의존 최소화."""
    for p in CORE_8 + SCENE_3_MULTITURN + ADVANCED_3:
        if p.key == key:
            return p
    return None


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

    st.title("SURI — 보험 상품 분석 질의 PoC")
    st.markdown(
        "자연어 질의 → SQL 생성·실행·해석 흐름을 확인하는 합성 데이터 기반 데모"
    )
    st.caption(
        "Planner / Executor / Critic 역할 분리 · MCP Tool 호출 · "
        "Read-only Query Controls · PostgreSQL 15"
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

    # 질문 입력 + 실행. 캐시 토글은 /admin 페이지로 이동 — 일반 방문자에게는
    # 캐시 토글이 보이지 않으며, 기본값(False)으로 항상 실제 실행 흐름을 보여준다.
    col_q, col_btn = st.columns([7, 1])
    with col_q:
        question = st.text_input(
            "질문을 입력하거나 아래 프리셋 선택:",
            key="question_input",
            label_visibility="collapsed",
            placeholder="예: 판매채널별 13회차·25회차 유지율 낙차가 어느 채널에서 가장 큰지 비교해줘",
            disabled=turn_cap_reached or is_running,
        )
    with col_btn:
        run_clicked = st.button(
            "⏳ 실행 중..." if is_running else "▶ 실행",
            type="primary",
            use_container_width=True,
            disabled=turn_cap_reached or is_running,
        )

    # 일반 방문자: 캐시 OFF 강제. Admin 토글 ON 시에만 캐시 사용.
    use_cache = bool(st.session_state.get("_admin_use_cache", False))

    # 첫 질문 전(완전한 idle)에만 안내 문구 + 시연 프리셋 노출.
    # 실행 중·실행 예약·직전 에러가 하나라도 있으면 숨김.
    # 안내 문구는 입력창 바로 아래 → 추천 카드 위에 두어, 사용자가 추천을
    # 보기 전에 실행 흐름을 먼저 이해할 수 있게 한다.
    if (
        conv_len == 0
        and not is_running
        and not run_clicked
        and st.session_state._pending_run is None
        and st.session_state.get("_last_run_error") is None
    ):
        st.info(
            "질문을 직접 입력해 실행하거나, 아래 **추천 시나리오의 ▶ 바로 실행** 을 "
            "눌러 즉시 시연할 수 있습니다.  \n"
            "실행 결과에서 Planner → Executor/Tool 호출 → SQL → Critic 흐름을 확인할 수 있습니다."
        )
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

    # idle 안내 문구는 위(입력창 바로 아래)로 이동. 여기서는 결과/에러가 있을
    # 때만 렌더한다 — idle 상태에서는 위의 안내 + 추천 카드가 이미 표시됨.
    if last_error is not None or st.session_state.conversation:
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
