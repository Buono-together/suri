"""
Admin 페이지 — 운영자 도구 모음.

현재는 응답 캐시 제어만. 향후 세션 리셋·로그 뷰어 등으로 확장 가능.
"""
from __future__ import annotations

import streamlit as st

from app.agents.cache import clear_cache, CACHE_DIR


def render_admin_page() -> None:
    st.title("🔧 Admin")
    st.caption("운영자 도구 · 면접관이 실수로 누르지 않도록 별도 페이지에 격리")

    st.markdown("---")

    # =============================================================
    # 응답 캐시
    # =============================================================
    st.markdown("### 📦 응답 캐시")

    cache_files = list(CACHE_DIR.glob("*.json")) if CACHE_DIR.exists() else []
    total_size = sum(f.stat().st_size for f in cache_files)

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        st.metric("저장된 응답", f"{len(cache_files)}개")
    with col2:
        kb = total_size / 1024
        st.metric("총 용량", f"{kb:,.1f} KB")
    with col3:
        st.caption(
            f"경로: `{CACHE_DIR}`\n\n"
            "질문 + 히스토리 해시 키 기반 JSON 캐시. 동일 질문 재실행 시 "
            "LLM·DB 왕복 없이 즉시 반환 → 시연·회귀 테스트 가속."
        )

    confirm = st.checkbox(
        "삭제 확인 (면접관 실수 방지용 이중 확인)",
        key="admin_cache_delete_confirm",
    )
    if st.button(
        "🗑️ 캐시 전체 삭제",
        type="secondary",
        disabled=not confirm,
        use_container_width=False,
    ):
        n = clear_cache()
        st.session_state.admin_cache_delete_confirm = False
        st.success(f"{n}개 삭제됨")
        st.rerun()
