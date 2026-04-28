"""
Data Sample 뷰 — 각 테이블/뷰 상위 10행.

- customers 원본은 Layer 2 방어로 조회 불가 (스킵).
- customers_safe / premium_payments / premium_payments_v / monthly_ape / policies /
  products / agents / claims 샘플 노출.
- 모든 쿼리는 suri_readonly 경유 + st.cache_data TTL 1h.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import streamlit as st

from app.mcp_server.db import execute_readonly, DBExecutionError


SAMPLE_LIMIT = 10


@dataclass(frozen=True)
class SampleTarget:
    name: str
    kind: str             # "TABLE" | "VIEW"
    blocked: bool = False
    blocked_reason: str = ""


TARGETS: list[SampleTarget] = [
    SampleTarget(
        name="customers",
        kind="TABLE",
        blocked=True,
        blocked_reason=(
            "원본 테이블은 PII(주민번호·전화·이메일 등)를 포함하여 "
            "suri_readonly ROLE에서 조회가 차단됩니다. "
            "PII 제거 버전은 `customers_safe` 탭을 확인하세요."
        ),
    ),
    SampleTarget(name="customers_safe", kind="VIEW"),
    SampleTarget(name="products", kind="TABLE"),
    SampleTarget(name="agents", kind="TABLE"),
    SampleTarget(name="policies", kind="TABLE"),
    SampleTarget(name="premium_payments", kind="TABLE"),
    SampleTarget(name="premium_payments_v", kind="VIEW"),
    SampleTarget(name="claims", kind="TABLE"),
    SampleTarget(name="monthly_ape", kind="VIEW"),
]


@st.cache_data(ttl=3600, show_spinner="상위 10행 조회 중…")
def _fetch_sample(table_name: str, limit: int = SAMPLE_LIMIT) -> dict[str, Any]:
    """SELECT * FROM <table> LIMIT N. 실패 시 에러 래핑."""
    query = f"SELECT * FROM {table_name} LIMIT {limit}"
    try:
        return execute_readonly(query, max_rows=limit)
    except DBExecutionError as e:
        return {"error": str(e)}


def _render_target(target: SampleTarget) -> None:
    kind_badge = "🗂️ VIEW" if target.kind == "VIEW" else "📋 TABLE"
    st.markdown(f"#### `{target.name}` · {kind_badge}")

    if target.blocked:
        st.error(f"🚫 **접근 차단** — {target.blocked_reason}")
        return

    result = _fetch_sample(target.name)

    if "error" in result:
        st.error(f"조회 실패: {result['error']}")
        return

    rows = result.get("rows", [])
    if not rows:
        st.info("데이터가 없습니다.")
        return

    st.caption(
        f"상위 {len(rows)}행 · 전체 컬럼 {len(result.get('columns', []))}개"
    )
    st.dataframe(rows, use_container_width=True, hide_index=True)


def render_data_sample_tab() -> None:
    st.markdown("### 📊 Data Sample")
    st.caption(
        f"각 오브젝트의 상위 {SAMPLE_LIMIT}행 · suri_readonly 경유 · "
        "결과 1시간 캐싱. `customers` 원본은 Layer 2 방어로 차단."
    )

    labels = [t.name for t in TARGETS]
    sub_tabs = st.tabs(labels)
    for tab, target in zip(sub_tabs, TARGETS):
        with tab:
            _render_target(target)
