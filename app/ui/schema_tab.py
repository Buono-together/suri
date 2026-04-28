"""
Schema 뷰 — 9개 DB 오브젝트의 read-only 메타.

원본 customers 는 식별/연락성 컬럼(주민번호·전화·이메일 등)을 포함하므로
suri_readonly ROLE 기준 직접 조회 대상에서 제외. 데모에서는 customers_safe
VIEW 를 통해 제한된 컬럼만 확인.

UI 정적 메타 + information_schema 동적 컬럼/행수 조합.
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


# 탭 순서: 첫 진입 시 customers_safe(샘플 가능) 가 기본 활성화되도록 맨 앞,
# 직접 조회 제한 대상인 customers 는 맨 뒤에 (restricted) 라벨로.
OBJECTS: list[DBObject] = [
    DBObject(
        name="customers_safe",
        kind="VIEW",
        description=(
            "고객 정보 중 식별/연락성 컬럼을 제외한 VIEW. "
            "Agent/UI 는 이 VIEW 를 사용합니다."
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
    DBObject(
        name="customers",
        kind="TABLE",
        description=(
            "원본 고객 테이블. 식별/연락성 컬럼(주민번호·전화·이메일 등) 포함. "
            "suri_readonly ROLE 기준 직접 조회 대상에서 제외 — "
            "데모에서는 customers_safe VIEW 사용."
        ),
        pii_blocked=True,
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
        # restricted 표시 — 강한 빨강 대신 amber 톤으로 (경고이되 차단 강조 X)
        return (
            '<span style="display:inline-block; padding:2px 10px; '
            'border-radius:12px; background:#fff4e5; color:#9a3412; '
            'font-size:0.75rem; font-weight:600; margin-left:6px;">'
            '🔒 조회 제한 · suri_readonly ROLE</span>'
        )
    if obj.safe_view:
        return (
            '<span style="display:inline-block; padding:2px 10px; '
            'border-radius:12px; background:#e6f4ea; color:#137333; '
            'font-size:0.75rem; font-weight:600; margin-left:6px;">'
            '🟢 Safe VIEW · 식별 컬럼 제외</span>'
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
        st.warning(
            "**조회 제한**\n\n"
            "원본 `customers` 테이블은 식별/연락성 컬럼을 포함하므로 "
            "**suri_readonly ROLE 기준 직접 조회 대상에서 제외**했습니다. "
            "데모에서는 **`customers_safe` VIEW** 를 통해 분석에 필요한 "
            "제한된 컬럼만 확인할 수 있습니다 (raw row 는 표시하지 않습니다)."
        )
        st.caption("→ **customers_safe** 탭에서 컬럼 구조와 샘플을 확인하세요.")
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
        "PostgreSQL 15 · 9 objects · suri_readonly ROLE 기준으로 "
        "조회 가능한 테이블과 View 를 표시합니다. "
        "원본 `customers` 는 식별/연락성 컬럼을 포함하므로 "
        "`customers_safe` VIEW 를 통해 제한된 컬럼만 확인합니다."
    )

    # 탭 라벨: customers 만 (restricted) 표기. DB 객체 이름은 변경하지 않고
    # UI 라벨에서만 분기 — 첫 진입 시 customers_safe 가 자동 활성화된다.
    object_labels = [
        f"{obj.name} (restricted)" if obj.pii_blocked else obj.name
        for obj in OBJECTS
    ]
    sub_tabs = st.tabs(object_labels)
    for tab, obj in zip(sub_tabs, OBJECTS):
        with tab:
            _render_object(obj)
