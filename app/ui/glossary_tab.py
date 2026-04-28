"""
Glossary 뷰 — app/mcp_server/domain_glossary.yaml read-only 뷰어.

카테고리 6개로 그룹핑 (YAML 섹션 기준).
각 용어는 st.expander로 접힘. Tier 배지 + 정의 + SQL 힌트 + 출처 표시.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st
import yaml


_GLOSSARY_PATH = (
    Path(__file__).resolve().parent.parent / "mcp_server" / "domain_glossary.yaml"
)


# YAML 섹션 주석 (# A. 유지·해지 ...) 과 맞춘 카테고리 매핑.
# 신규 용어 추가 시 이 리스트도 갱신 필요 — 그 외에는 자동으로 이 순서로 렌더.
CATEGORIES: list[tuple[str, list[str]]] = [
    ("A. 유지·해지", ["유지율", "조기_해지율", "해지_및_실효", "해약환급금", "승환계약"]),
    ("B. 보험료", ["APE", "월초보험료", "수입보험료", "코호트"]),
    ("C. 회계 (IFRS17)", ["CSM", "BEL", "RA", "IFRS17_측정모형", "지급률_proxy"]),
    ("D. 판매채널", ["판매채널"]),
    ("E. 상품유형", ["상품유형"]),
    ("F. 기타", ["절판", "불완전판매"]),
]


# Tier → (표시 라벨, 배경색, 글자색)
TIER_STYLE: dict[str, tuple[str, str, str]] = {
    "official_definition": ("공식 정의", "#e6f4ea", "#137333"),
    "industry_convention": ("업계 관행", "#e8f0fe", "#1967d2"),
    "poc_proxy_or_assumption": ("PoC 근사치", "#fef7e0", "#b06000"),
}


# 표준 렌더링 순서 — entry dict의 키를 이 순서로 조회해 블록 생성.
# 여기 없는 키는 "기타 세부 정보" expander 로 덤프.
_RENDER_ORDER: list[tuple[str, str]] = [
    ("standard_definition", "📖 표준 정의"),
    ("official_definition", "📖 공식 정의"),
    ("definition", "📖 정의"),
    ("proxy_formula", "🧮 Proxy 공식"),
    ("formula_poc", "🧮 PoC 환산 공식"),
    ("calculation_basis", "🧮 산출 기준"),
    ("N회차별_의미", "📅 N회차별 의미"),
    ("critical_note", "⚠️ 주의"),
    ("common_mistake", "❗ 흔한 실수"),
    ("warning", "⚠️ 경고"),
    ("industry_benchmark", "📊 업계 벤치마크"),
    ("suri_schema_hint", "🗄️ SURI 스키마 힌트"),
    ("suri_스키마_매핑", "🗄️ SURI 스키마 매핑"),
    ("suri_데이터_주입_여부", "🗄️ SURI 데이터 주입 여부"),
    ("proxy_한계", "🚧 Proxy 한계"),
    ("불가_사유", "🚫 산출 불가 사유"),
    ("용도", "🎯 용도"),
    ("관련_이슈", "🔗 관련 이슈"),
    ("관계_지표", "🔗 관계 지표"),
    ("배경_지식", "📚 배경 지식"),
    ("critic_활용_힌트", "💡 Critic 활용 힌트"),
    ("권장_대응_graceful_degradation", "💡 권장 대응 (Graceful degradation)"),
    ("industry_가설", "📊 업계 가설"),
    ("감지_지표_proxy", "🔎 감지 지표 (proxy)"),
    ("불완전판매비율_공식", "🧮 불완전판매비율 공식"),
    ("페르소나_관점", "👥 페르소나 관점"),
    ("최초_측정_개념", "📖 최초 측정"),
    ("후속_측정_개념", "📖 후속 측정"),
    ("손해보험_정식_정의", "📖 손해보험 정식 정의"),
    ("생명보험_실무", "📖 생명보험 실무"),
    ("APE와의_관계", "🔗 APE와의 관계"),
    ("표준_환산_원칙", "🧮 표준 환산 원칙"),
    ("분석_패턴", "📊 분석 패턴"),
    ("활용_예시", "📊 활용 예시"),
    ("대표_시즌", "📅 대표 시즌"),
    ("대표_상품군", "📦 대표 상품군"),
    ("관련_제도", "⚖️ 관련 제도"),
    ("legal_note", "⚖️ 법적 근거"),
    ("약칭", "✍️ 약칭"),
    ("note", "📝 노트"),
    ("명시_표현_필수", "❗ 명시 표현 필수"),
    ("사용_시_경고", "⚠️ 사용 시 경고"),
]

# 내포된 사전식 서브-용어 (해지_및_실효 > 해지/실효/부활/무효 등)
# 이 키를 가진 entry는 각 서브-엔트리를 inline 렌더.
_NESTED_KEYS: set[str] = {
    "해지", "실효", "부활", "무효",        # 해지_및_실효
    "방카", "전속", "GA", "TM", "CM",     # 판매채널
    "보장성", "저축성", "변액",           # 상품유형
    "GMM", "PAA", "VFA",                 # IFRS17_측정모형
}


# =============================================================
# 유틸
# =============================================================

@st.cache_data(ttl=3600)
def _load_glossary() -> dict[str, Any]:
    """YAML을 한 번 읽고 Streamlit 캐시에 올려둔다."""
    with _GLOSSARY_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _render_tier_badge(tier: str) -> None:
    label, bg, fg = TIER_STYLE.get(tier, (tier, "#e5e7eb", "#374151"))
    st.markdown(
        f'<span style="display:inline-block; padding:2px 10px; '
        f'border-radius:12px; background:{bg}; color:{fg}; '
        f'font-size:0.8rem; font-weight:600;">{label}</span>',
        unsafe_allow_html=True,
    )


def _render_availability_badge(status: str) -> None:
    """suri_산출_가능_여부 배지."""
    status_str = str(status).strip()
    if "불가" in status_str:
        st.error(f"🚫 SURI 산출 가능 여부 — **{status_str}**")
    elif "가능" in status_str:
        st.success(f"✅ SURI 산출 가능 여부 — **{status_str}**")
    else:
        st.info(f"ℹ️ SURI 산출 가능 여부 — **{status_str}**")


def _render_value(value: Any) -> None:
    """스칼라/리스트/사전을 보기 좋게 출력."""
    if isinstance(value, str):
        st.markdown(value)
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, (str, int, float)):
                st.markdown(f"- {item}")
            else:
                st.json(item)
    elif isinstance(value, dict):
        for k, v in value.items():
            st.markdown(f"**{k}**")
            _render_value(v)
    else:
        st.write(value)


def _render_sources(sources: dict[str, Any]) -> None:
    """sources.primary / sources.secondary 렌더."""
    if not isinstance(sources, dict):
        st.write(sources)
        return
    primary = sources.get("primary") or []
    secondary = sources.get("secondary") or []
    if primary:
        st.markdown("**Primary (법령·기준서)**")
        for s in primary:
            st.markdown(f"- {s}")
    if secondary:
        st.markdown("**Secondary (리서치·공시)**")
        for s in secondary:
            st.markdown(f"- {s}")


def _render_nested_subterm(sub_name: str, sub_entry: dict[str, Any]) -> None:
    """해지/실효/부활/방카/전속 같은 서브-용어 inline 렌더."""
    en = sub_entry.get("en")
    title = f"**{sub_name}**"
    if en:
        title += f" · _{en}_"
    st.markdown(title)
    for key, value in sub_entry.items():
        if key == "en":
            continue
        st.caption(f"— {key}")
        _render_value(value)


def _render_entry(term: str, entry: dict[str, Any]) -> None:
    """단일 용어 entry 본문 렌더."""
    # 상단: 영문명 + tier 배지
    top_cols = st.columns([3, 1])
    with top_cols[0]:
        en = entry.get("en")
        if en:
            st.markdown(f"**English:** _{en}_")
    with top_cols[1]:
        tier = entry.get("tier")
        if tier:
            _render_tier_badge(tier)

    # 산출 가능 여부 (있으면 강조 배지로 먼저)
    avail = entry.get("suri_산출_가능_여부")
    if avail is not None:
        _render_availability_badge(avail)

    # 표준 블록들 (_RENDER_ORDER 순서)
    rendered_keys: set[str] = {"en", "tier", "sources", "suri_산출_가능_여부"}
    for key, label in _RENDER_ORDER:
        if key not in entry:
            continue
        rendered_keys.add(key)
        st.markdown(f"##### {label}")
        _render_value(entry[key])

    # 내포된 서브-용어 (해지_및_실효 > 해지/실효/부활/무효 등)
    nested_items = [
        (k, v) for k, v in entry.items()
        if k in _NESTED_KEYS and isinstance(v, dict)
    ]
    if nested_items:
        st.markdown("##### 🧩 세부 분류")
        for sub_name, sub_entry in nested_items:
            with st.container(border=True):
                _render_nested_subterm(sub_name, sub_entry)
        for sub_name, _ in nested_items:
            rendered_keys.add(sub_name)

    # Sources
    sources = entry.get("sources")
    if sources:
        st.markdown("##### 📚 출처")
        _render_sources(sources)
        rendered_keys.add("sources")

    # 표준 순서에 없는 기타 키 — 폴백
    leftover = {
        k: v for k, v in entry.items() if k not in rendered_keys
    }
    if leftover:
        with st.expander("기타 세부 정보"):
            for k, v in leftover.items():
                st.markdown(f"**{k}**")
                _render_value(v)


def _entry_matches_search(term: str, entry: dict[str, Any], query: str) -> bool:
    """검색어가 용어명 or 영문명 or 정의에 포함되는지."""
    if not query:
        return True
    q = query.lower().strip()
    if q in term.lower():
        return True
    en = str(entry.get("en", "")).lower()
    if q in en:
        return True
    # 주요 정의 필드만 검색 (전체 dump는 너무 느슨)
    for key in ("standard_definition", "official_definition", "definition"):
        if q in str(entry.get(key, "")).lower():
            return True
    return False


# =============================================================
# 메인 렌더
# =============================================================

def render_glossary_tab() -> None:
    """Glossary 탭 본문."""
    glossary = _load_glossary()
    meta = glossary.get("meta", {})

    st.markdown("### 📖 Domain Glossary")
    st.caption(
        f"한국 생명보험 도메인 용어 사전 · v{meta.get('version', '?')} · "
        f"{meta.get('감수', '')}"
    )

    # Tier 범례
    with st.expander("Tier 정의", expanded=False):
        tiers = meta.get("definition_tiers", {})
        for tier_key, desc in tiers.items():
            label, _, _ = TIER_STYLE.get(tier_key, (tier_key, "", ""))
            st.markdown(f"- **{label}** (`{tier_key}`) — {desc}")

    # 검색
    query = st.text_input(
        "🔍 용어 검색",
        placeholder="한글 용어, 영문명, 정의 내용으로 검색",
        key="glossary_search",
    )

    # 카테고리별 그룹 렌더
    total = 0
    shown = 0
    for category_name, term_keys in CATEGORIES:
        # 이 카테고리에서 매치되는 term만 수집
        matches = []
        for term in term_keys:
            entry = glossary.get(term)
            if entry is None:
                continue
            total += 1
            if _entry_matches_search(term, entry, query):
                matches.append((term, entry))
                shown += 1
        if not matches:
            continue

        st.markdown(f"#### {category_name}")
        for term, entry in matches:
            en = entry.get("en")
            header = term.replace("_", " ")
            if en:
                header = f"{header}  ·  _{en}_"
            with st.expander(header, expanded=False):
                _render_entry(term, entry)

    if query:
        st.caption(f"검색 결과: {shown}/{total}개")
    else:
        st.caption(f"등록 용어: {total}개")
