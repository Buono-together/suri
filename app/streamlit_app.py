"""
SURI — Streamlit 멀티페이지 엔트리포인트

사이드바 순서 (위 → 아래):
  🎯 SURI 브랜드 → 페이지 네비 (Agent / Glossary / Schema / Data Sample / Admin)

구현 노트:
  st.navigation(position="hidden") 으로 기본 네비 UI를 숨기고,
  st.page_link 로 수동 네비를 쌓아 브랜드를 최상단에 배치.
  캐시 제어·프리셋은 사이드바에서 제거됐고, 각각 Admin 페이지 / Agent 페이지 본문에 존재.

session_state 는 페이지 전환과 무관하게 유지되므로, Glossary/Schema 를
거쳐 Agent 로 돌아와도 대화 스택·실행 상태 그대로.

실행: streamlit run app/streamlit_app.py
"""
from __future__ import annotations

import streamlit as st

from app.ui.page_agent import render_agent_page
from app.ui.page_admin import render_admin_page
from app.ui.glossary_tab import render_glossary_tab
from app.ui.schema_tab import render_schema_tab
from app.ui.data_sample_tab import render_data_sample_tab


# =============================================================
# 페이지 설정
# =============================================================

st.set_page_config(
    page_title="SURI — Data Agent PoC",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 질문/답변 컨테이너 스타일은 rendering.py 에서 마크다운 내부에 직접
# inline style 로 주입. Streamlit 버전별 DOM 변경에 영향받지 않음.


# =============================================================
# 페이지 정의
# =============================================================

page_agent = st.Page(
    render_agent_page,
    title="Agent 대화",
    icon="🗣️",
    url_path="agent",
    default=True,
)
page_glossary = st.Page(
    render_glossary_tab, title="Glossary", icon="📖", url_path="glossary",
)
page_schema = st.Page(
    render_schema_tab, title="Schema", icon="🗄️", url_path="schema",
)
page_data_sample = st.Page(
    render_data_sample_tab, title="Data Sample", icon="📊",
    url_path="data-sample",
)
page_admin = st.Page(
    render_admin_page, title="Admin", icon="🔧", url_path="admin",
)

# position="hidden" — Streamlit 기본 네비 위젯을 끄고 수동 배치
pg = st.navigation(
    [page_agent, page_glossary, page_schema, page_data_sample, page_admin],
    position="hidden",
)


# =============================================================
# 사이드바 — 브랜드(최상단) + 네비
# 프리셋은 Agent 페이지 본문, 캐시 제어는 Admin 페이지로 이동.
# =============================================================

with st.sidebar:
    st.markdown("## 🎯 SURI")
    st.caption("자연어→SQL 분석 질의 PoC")
    st.markdown("---")

    # 사용자 페이지
    st.page_link(page_agent, label="Agent 대화", icon="🗣️")
    st.page_link(page_glossary, label="Glossary", icon="📖")
    st.page_link(page_schema, label="Schema", icon="🗄️")
    st.page_link(page_data_sample, label="Data Sample", icon="📊")

    # Admin 링크는 사용자가 /admin URL 로 직접 접근했을 때만 사이드바에 노출.
    # 면접관이 브라우징 중 실수로 누르지 못하도록 "hidden 엔드포인트" 로 운용.
    if pg.url_path == "admin":
        st.markdown("---")
        st.page_link(page_admin, label="Admin", icon="🔧")


# 선택된 페이지 실행
pg.run()
