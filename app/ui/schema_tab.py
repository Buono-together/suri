"""
Schema 뷰 — 9개 DB 오브젝트 (8 table + 1 view, 그리고 2 추가 VIEW) read-only 메타.

customers 원본은 suri_readonly로 접근 차단 (Layer 2 방어).
UI는 정적 메타만 노출하며 실제 DB 조회는 information_schema를 통해.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import streamlit as st

from app.mcp_server.db import execute_readonly, DBExecutionError


# =============================================================
# 정적 오브젝트 메타
# =============================================================

@dataclass(frozen=True)
class DBObject:
    name: str
    kind: str            # "TABLE" | "VIEW"
    description: str
    pii_blocked: bool = False
    safe_view: bool = False


OBJECTS: list[DBObject] = [
    DBObject(
        name="customers",
        kind="TABLE",
        description=(
            "원본 고객 테이블. 주민번호·전화·이메일 등 PII 포함. "
            "suri_readonly 계정은 GRANT에서 제외되어 직접 접근 불가."
        ),
        pii_blocked=True,
    ),
    DBObject(
        name="customers_safe",
        kind="VIEW",
        description=(
            "고객 정보 중 PII 컬럼을 제거한 안전 VIEW. "
            "Agent/UI에서는 반드시 이 VIEW만 사용."
        ),
        safe_view=True,
    ),
    DBObject(
        name="products",
        kind="TABLE",
        description="보험 상품 마스터 (상품코드·명·유형·측정모형 등).",
    ),
    DBObject(
        name="agents",
        kind="TABLE",
        description="설계사/채널 정보 (판매채널·지점·활동상태 등).",
    ),
    DBObject(
        name="policies",
        kind="TABLE",
        description=(
            "개별 보험계약 (신계약·유효·해지·실효 등). "
            "유지율·코호트 분석의 기준 테이블."
        ),
    ),
    DBObject(
        name="premium_payments",
        kind="TABLE",
        description="월별 보험료 납입 이력 (약 570K 행).",
    ),
    DBObject(
        name="premium_payments_v",
        kind="VIEW",
        description=(
            "premium_payments + payment_month_seq (1,2,3… 회차) 파생 컬럼. "
            "유지율 코호트 산출에 사용."
        ),
    ),
    DBObject(
        name="claims",
        kind="TABLE",
        description="보험금 청구·지급 이력.",
    ),
    DBObject(
        name="monthly_ape",
        kind="VIEW",
        description=(
            "연납화보험료(APE) 월단위 집계 VIEW. "
            "월납×12 + 연납 + 일시납×0.1 환산."
        ),
    ),
]


# =============================================================
# DB 메타 조회 (캐시)
# =============================================================

@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_columns(table_name: str) -> list[dict[str, Any]]:
    """information_schema.columns 조회. 권한 없으면 빈 리스트."""
    query = f"""
        SELECT
            column_name AS name,
            data_type AS type,
            is_nullable AS nullable,
            column_default AS default_value
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = '{table_name}'
        ORDER BY ordinal_position
    """
    try:
        result = execute_readonly(query, max_rows=200)
        return result["rows"]
    except DBExecutionError:
        return []


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_row_count(table_name: str) -> int | None:
    """COUNT(*). 권한 없으면 None."""
    try:
        result = execute_readonly(
            f"SELECT COUNT(*) AS n FROM {table_name}", max_rows=1,
        )
        if result["rows"]:
            return int(result["rows"][0]["n"])
    except DBExecutionError:
        return None
    return None


# =============================================================
# 렌더
# =============================================================

def _render_kind_badge(kind: str) -> str:
    if kind == "VIEW":
        return (
            '<span style="display:inline-block; padding:2px 10px; '
            'border-radius:12px; background:#e8f0fe; color:#1967d2; '
            'font-size:0.75rem; font-weight:600;">VIEW</span>'
        )
    return (
        '<span style="display:inline-block; padding:2px 10px; '
        'border-radius:12px; background:#e6f4ea; color:#137333; '
        'font-size:0.75rem; font-weight:600;">TABLE</span>'
    )


def _render_status_badge(obj: DBObject) -> str:
    if obj.pii_blocked:
        return (
            '<span style="display:inline-block; padding:2px 10px; '
            'border-radius:12px; background:#fce8e6; color:#c5221f; '
            'font-size:0.75rem; font-weight:600; margin-left:6px;">'
            '🚫 PII — suri_readonly 접근 차단</span>'
        )
    if obj.safe_view:
        return (
            '<span style="display:inline-block; padding:2px 10px; '
            'border-radius:12px; background:#fef7e0; color:#b06000; '
            'font-size:0.75rem; font-weight:600; margin-left:6px;">'
            '🛡️ Safe VIEW (원본 PII 제거)</span>'
        )
    return ""


def _render_object(obj: DBObject) -> None:
    """단일 오브젝트 엔트리."""
    header_html = (
        f'<span style="font-size:1.05rem; font-weight:600;">'
        f'<code>{obj.name}</code></span> '
        f'{_render_kind_badge(obj.kind)} {_render_status_badge(obj)}'
    )
    st.markdown(header_html, unsafe_allow_html=True)
    st.caption(obj.description)

    if obj.pii_blocked:
        st.info(
            "이 테이블은 Layer 2 방어(ROLE-level GRANT)에 의해 "
            "suri_readonly 계정에서 조회 불가. 컬럼·행수 조회 생략. "
            "PII 제외 데이터는 `customers_safe` VIEW 사용."
        )
        return

    # 행 수
    count = _fetch_row_count(obj.name)
    # 컬럼
    columns = _fetch_columns(obj.name)

    meta_cols = st.columns([1, 3])
    with meta_cols[0]:
        if count is None:
            st.metric("행 수", "조회 불가")
        else:
            st.metric("행 수", f"{count:,}")
    with meta_cols[1]:
        st.metric("컬럼 수", f"{len(columns)}" if columns else "조회 불가")

    if columns:
        st.dataframe(
            columns,
            use_container_width=True,
            hide_index=True,
            column_config={
                "name": st.column_config.TextColumn("컬럼", width="medium"),
                "type": st.column_config.TextColumn("타입", width="small"),
                "nullable": st.column_config.TextColumn("nullable", width="small"),
                "default_value": st.column_config.TextColumn(
                    "default", width="medium",
                ),
            },
        )
    else:
        st.caption("컬럼 메타를 가져올 수 없습니다 (권한 또는 객체 부재).")


def render_schema_tab() -> None:
    st.markdown("### 🗄️ Database Schema")
    st.caption(
        "PostgreSQL 15 · 9 오브젝트 (6 TABLE + 3 VIEW) · "
        "모든 조회는 suri_readonly ROLE 경유 (Layer 2 방어)."
    )

    # 서브-탭으로 테이블/뷰 분리
    object_labels = [f"{obj.name}" for obj in OBJECTS]
    sub_tabs = st.tabs(object_labels)
    for tab, obj in zip(sub_tabs, OBJECTS):
        with tab:
            _render_object(obj)
