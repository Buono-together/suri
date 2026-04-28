"""
Data Sample 뷰 — 각 테이블/뷰 상위 10행.

- 첫 진입 탭은 customers_safe (실제 샘플 표시).
- 원본 customers 는 식별/연락성 컬럼을 포함하므로 suri_readonly ROLE 기준
  직접 조회 대상에서 제외 — 데모에서는 customers_safe 사용.
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


# 탭 순서: 첫 진입 시 customers_safe(샘플 가능) 가 기본 활성화되도록 맨 앞,
# 직접 조회 제한 대상인 customers 는 맨 뒤에 (restricted) 라벨로.
TARGETS: list[SampleTarget] = [
    SampleTarget(name="customers_safe", kind="VIEW"),
    SampleTarget(name="products", kind="TABLE"),
    SampleTarget(name="agents", kind="TABLE"),
    SampleTarget(name="policies", kind="TABLE"),
    SampleTarget(name="premium_payments", kind="TABLE"),
    SampleTarget(name="premium_payments_v", kind="VIEW"),
    SampleTarget(name="claims", kind="TABLE"),
    SampleTarget(name="monthly_ape", kind="VIEW"),
    SampleTarget(
        name="customers",
        kind="TABLE",
        blocked=True,
        blocked_reason=(
            "원본 customers 테이블은 식별/연락성 컬럼을 포함하므로 "
            "suri_readonly ROLE 기준 직접 조회 대상에서 제외했습니다. "
            "데모에서는 customers_safe VIEW 를 통해 제한된 컬럼만 확인할 수 있습니다."
        ),
    ),
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
    label_suffix = " · 조회 제한" if target.blocked else ""
    st.markdown(f"#### `{target.name}` · {kind_badge}{label_suffix}")

    if target.blocked:
        # error(빨강) → warning(amber) 로 톤 다운. "차단" 보다 "제한된 객체"
        # 라는 사실을 차분히 알리고, customers_safe 로 유도.
        # raw customers 의 샘플 row 는 표시하지 않는다 — PoC 의 조회 통제 설계.
        st.warning(
            "**🔒 조회 제한**\n\n"
            "원본 `customers` 테이블은 식별/연락성 컬럼을 포함하므로 "
            "**suri_readonly ROLE 기준 직접 조회 대상에서 제외**했습니다. "
            "데모에서는 **`customers_safe` VIEW** 를 통해 분석에 필요한 "
            "제한된 컬럼만 확인할 수 있습니다 — raw row 는 표시하지 않습니다."
        )
        st.caption("→ **customers_safe** 탭에서 샘플 데이터를 확인하세요.")
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
        f"각 오브젝트의 상위 {SAMPLE_LIMIT}행을 확인합니다. "
        "기본 조회는 suri_readonly ROLE 기준이며, "
        "원본 `customers` 대신 `customers_safe` VIEW 를 제공합니다."
    )

    # 탭 라벨: customers 만 (restricted) 표기. 첫 진입 시 customers_safe 자동 활성화.
    labels = [
        f"{t.name} (restricted)" if t.blocked else t.name
        for t in TARGETS
    ]
    sub_tabs = st.tabs(labels)
    for tab, target in zip(sub_tabs, TARGETS):
        with tab:
            _render_target(target)
