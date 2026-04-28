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


# Tier → (표시 라벨, 배경색, 글자색).
# 라벨 톤은 의도적으로 수비적 — 공식 분류 체계가 아니라 출처 성격을 안내하는
# 보조 메타이므로 "기준" 같은 단정 표현 회피.
TIER_STYLE: dict[str, tuple[str, str, str]] = {
    "official_definition": ("공식/제도 참고", "#e6f4ea", "#137333"),
    "industry_convention": ("업계 자료 참고", "#e8f0fe", "#1967d2"),
    "poc_proxy_or_assumption": ("PoC 해석 기준", "#fef7e0", "#b06000"),
}

# Tier 색상 dot — Streamlit st.expander 라벨은 inline HTML/색상 chip 을
# 지원하지 않으므로, 이름 옆에 색상 의미만 emoji 로 노출 (접힘 상태에서도 보임).
TIER_DOT: dict[str, str] = {
    "official_definition": "🟢",
    "industry_convention": "🔵",
    "poc_proxy_or_assumption": "🟡",
}

# Tier 설명 — 코드 쪽에서 override (YAML 데이터 미수정 정책 + 표현 톤 다운).
# YAML 에 같은 tier_key 가 있어도 이 override 가 우선. 키가 없으면 YAML fallback.
_TIER_DESC_OVERRIDE: dict[str, str] = {
    "official_definition": (
        "공개된 법령·기준서·감독기관·협회 자료를 참고한 항목입니다."
    ),
    "industry_convention": (
        "보험사 공시·리서치·산업 보고서 등 공개 자료에서 "
        "사용되는 표현을 참고한 항목입니다."
    ),
    "poc_proxy_or_assumption": (
        "실제 업무 기준이 아니라, 합성 데이터 기반 PoC 에서 "
        "질의 해석을 위해 둔 제한적 기준입니다."
    ),
}


# 키 → 라벨 매핑 (전체). 카드별 그룹은 아래 _GROUP_* 에서 별도 정의.
_LABELS: dict[str, str] = {
    "standard_definition": "📖 표준 정의",
    "official_definition": "📖 공식 정의",
    "definition": "📖 정의",
    "proxy_formula": "🧮 Proxy 공식",
    "formula_poc": "🧮 PoC 환산 공식",
    "calculation_basis": "🧮 산출 기준",
    "N회차별_의미": "📅 N회차별 의미",
    "critical_note": "⚠️ 주의",
    "common_mistake": "❗ 흔한 실수",
    "warning": "⚠️ 경고",
    "industry_benchmark": "📊 업계 벤치마크",
    "suri_schema_hint": "🗄️ SURI 스키마 힌트",
    "suri_스키마_매핑": "🗄️ SURI 스키마 매핑",
    "suri_데이터_주입_여부": "🗄️ SURI 데이터 주입 여부",
    "proxy_한계": "🚧 Proxy 한계",
    "불가_사유": "🚫 산출 불가 사유",
    "용도": "🎯 용도",
    "관련_이슈": "🔗 관련 이슈",
    "관계_지표": "🔗 관계 지표",
    "배경_지식": "📚 배경 지식",
    "critic_활용_힌트": "💡 Critic 활용 힌트",
    "권장_대응_graceful_degradation": "💡 권장 대응",
    "industry_가설": "📊 업계 가설",
    "감지_지표_proxy": "🔎 감지 지표 (proxy)",
    "불완전판매비율_공식": "🧮 불완전판매비율 공식",
    "페르소나_관점": "👥 페르소나 관점",
    "최초_측정_개념": "📖 최초 측정",
    "후속_측정_개념": "📖 후속 측정",
    "손해보험_정식_정의": "📖 손해보험 정식 정의",
    "생명보험_실무": "📖 생명보험 실무",
    "APE와의_관계": "🔗 APE와의 관계",
    "표준_환산_원칙": "🧮 표준 환산 원칙",
    "분석_패턴": "📊 분석 패턴",
    "활용_예시": "📊 활용 예시",
    "대표_시즌": "📅 대표 시즌",
    "대표_상품군": "📦 대표 상품군",
    "관련_제도": "⚖️ 관련 제도",
    "legal_note": "⚖️ 법적 근거",
    "약칭": "✍️ 약칭",
    "note": "📝 노트",
    "명시_표현_필수": "❗ 명시 표현 필수",
    "사용_시_경고": "⚠️ 사용 시 경고",
}


# 좌측 카드(파랑) — "산출 기준" 그룹: 어떻게 계산하는가만
# (정의 텍스트는 한 줄 strip + 상세 popover 로 분리)
_GROUP_DEFINITION = [
    "calculation_basis",
    "proxy_formula", "formula_poc", "불완전판매비율_공식",
    "표준_환산_원칙",
    "약칭", "용도",
]

# 우측 카드(주황) — "주의 · 흔한 실수" 그룹 (벤치마크는 상세 popover 로)
_GROUP_WARNING = [
    "critical_note", "common_mistake", "warning",
    "사용_시_경고", "명시_표현_필수",
    "proxy_한계", "불가_사유",
    "감지_지표_proxy",
    "관련_이슈",
]

# 전폭 하단 카드(초록) — "SURI 힌트" 그룹: Agent가 어디를 봐야 하는가
_GROUP_HINT = [
    "suri_schema_hint", "suri_스키마_매핑", "suri_데이터_주입_여부",
    "critic_활용_힌트", "권장_대응_graceful_degradation",
    "분석_패턴", "활용_예시",
    "APE와의_관계", "관계_지표",
]

# 상세 정보 popover (기본 접힘) — 첫 화면 가독성 위해 길어지는 컨텐츠는 여기로
_GROUP_DETAIL = [
    # 전체 정의 (한 줄 strip 으로 첫 줄 노출되지만 multi-line 본문 보관)
    "standard_definition", "official_definition", "definition",
    "최초_측정_개념", "후속_측정_개념",
    "손해보험_정식_정의", "생명보험_실무",
    # 회차별/시즌/페르소나 등 길어지는 보조 정보
    "N회차별_의미",
    "industry_benchmark", "industry_가설",
    "배경_지식",
    "페르소나_관점",
    "대표_시즌", "대표_상품군",
    "관련_제도", "legal_note",
    "note",
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


# =============================================================
# 카드 헤더 inline HTML
# =============================================================

def _card_title_html(emoji_label: str, bg: str, fg: str, border: str) -> str:
    return (
        f'<div style="background:{bg}; color:{fg}; '
        f'padding:6px 10px; border-radius:6px; font-weight:600; '
        f'margin-bottom:8px; border:1px solid {border}; '
        f'font-size:0.88rem;">{emoji_label}</div>'
    )


def _render_key_block(entry: dict[str, Any], key: str) -> None:
    """카드 안에서 단일 키 블록 (라벨 + 본문). popover/상세 등 멀티-키 영역용."""
    label = _LABELS.get(key, key)
    st.markdown(f"**{label}**")
    _render_value(entry[key])


def _render_card_body(entry: dict[str, Any], keys: list[str]) -> None:
    """카드 헤더가 별도로 있을 때 본문 렌더.

    - 키가 1개면 라벨을 생략 (카드 헤더와 중복되므로).
    - 키가 2개 이상이면 식별을 위해 라벨 표시.
    """
    if len(keys) == 1:
        _render_value(entry[keys[0]])
    else:
        for k in keys:
            label = _LABELS.get(k, k)
            st.markdown(f"**{label}**")
            _render_value(entry[k])


def _extract_one_liner(entry: dict[str, Any]) -> str:
    """한 줄 정의 추출 — standard_definition / official_definition / definition
    의 첫 줄(첫 \\n 이전)을 우선순위로 사용. 없으면 빈 문자열."""
    for key in ("standard_definition", "official_definition", "definition"):
        text = entry.get(key)
        if isinstance(text, str) and text.strip():
            first = text.strip().split("\n", 1)[0].strip()
            return first
    return ""


def _render_entry(term: str, entry: dict[str, Any]) -> None:
    """단일 용어 entry 본문 렌더 — 카드 그룹 기반.

    구조:
      1) 헤더 라인 — 영문명 + tier 배지 + suri 산출 가능 여부 (있으면)
      2) 한 줄 정의 박스 — 면접관이 1초 안에 핵심을 잡도록
      3) 2열 grid — [정의 · 산출 기준] / [주의 · 벤치마크]
      4) SURI 힌트 카드 — 전폭, Agent가 어디를 봐야 하는가
      5) 내포 서브-용어 (해지/실효/방카/전속 등)
      6) 출처 popover · 기타 세부 정보 popover (캡처 시 노이즈 최소화)
    """
    rendered: set[str] = {"en", "tier", "sources", "suri_산출_가능_여부"}

    # ---------- 1) 헤더 라인 — 영문명·tier 모두 expander 라벨로 이미 노출되므로
    # 본문에서는 별도 헤더 라인을 두지 않는다 (중복 제거).

    avail = entry.get("suri_산출_가능_여부")
    if avail is not None:
        _render_availability_badge(avail)

    # ---------- 2) 한 줄 정의 박스 (회색 strip)
    one_liner = _extract_one_liner(entry)
    if one_liner:
        st.markdown(
            f'<div style="background:#f3f4f6; border-left:4px solid #6b7280; '
            f'padding:10px 14px; border-radius:6px; margin:8px 0 14px 0; '
            f'font-size:0.95rem; line-height:1.5;">'
            f'<span style="color:#6b7280; font-weight:600; '
            f'font-size:0.78rem; letter-spacing:0.04em;">한 줄 정의</span><br/>'
            f'{one_liner}</div>',
            unsafe_allow_html=True,
        )

    # ---------- 3) 2열 grid: 정의 / 주의
    left_keys = [k for k in _GROUP_DEFINITION if k in entry]
    right_keys = [k for k in _GROUP_WARNING if k in entry]

    def _render_left() -> None:
        with st.container(border=True):
            st.markdown(
                _card_title_html(
                    "🧮 산출 기준",
                    "#eef2ff", "#1e3a8a", "#c7d2fe",
                ),
                unsafe_allow_html=True,
            )
            _render_card_body(entry, left_keys)

    def _render_right() -> None:
        with st.container(border=True):
            st.markdown(
                _card_title_html(
                    "⚠️ 주의 · 흔한 실수",
                    "#fff8eb", "#9a3412", "#fde68a",
                ),
                unsafe_allow_html=True,
            )
            _render_card_body(entry, right_keys)

    if left_keys and right_keys:
        col_l, col_r = st.columns(2)
        with col_l:
            _render_left()
        with col_r:
            _render_right()
    elif left_keys:
        _render_left()
    elif right_keys:
        _render_right()
    rendered.update(left_keys)
    rendered.update(right_keys)

    # ---------- 4) SURI 힌트 카드 (전폭, 초록)
    hint_keys = [k for k in _GROUP_HINT if k in entry]
    if hint_keys:
        with st.container(border=True):
            st.markdown(
                _card_title_html(
                    "🗄️ SURI 힌트 — 어떤 테이블·뷰·상태값을 보면 되는가",
                    "#ecfdf5", "#065f46", "#a7f3d0",
                ),
                unsafe_allow_html=True,
            )
            _render_card_body(entry, hint_keys)
        rendered.update(hint_keys)

    # ---------- 5) 내포 서브-용어 (해지/실효/방카/전속 등)
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
            rendered.add(sub_name)

    # ---------- 6) 상세 정보 popover (전체 정의 / N회차별 / 벤치마크 등)
    detail_keys = [k for k in _GROUP_DETAIL if k in entry]
    if detail_keys:
        # standard_definition 등 정의 텍스트가 한 줄 strip 으로 이미 노출됐다면
        # 라벨에 "전체 정의 포함" 힌트를 안 달고도 자연스럽게 클릭하게 둠.
        with st.popover("📋 상세 보기", use_container_width=False):
            for k in detail_keys:
                label = _LABELS.get(k, k)
                st.markdown(f"##### {label}")
                _render_value(entry[k])
        rendered.update(detail_keys)

    # ---------- 7) 출처 popover (첫 화면 노이즈 최소화)
    sources = entry.get("sources")
    if sources:
        with st.popover("📚 출처·참고자료 보기", use_container_width=False):
            _render_sources(sources)
        rendered.add("sources")

    # 그룹에 안 들어간 기타 키 — 폴백
    leftover = {
        k: v for k, v in entry.items() if k not in rendered
    }
    if leftover:
        with st.popover("기타 세부 정보 보기", use_container_width=False):
            for k, v in leftover.items():
                label = _LABELS.get(k, k)
                st.markdown(f"**{label}**")
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
    st.markdown(
        "Agent 가 모호한 자연어 표현(예: *유지율*, *APE*, *GA*) 을 **질의 해석과 "
        "SQL 생성 기준으로 정리한 참조 화면**입니다. Planner 와 Critic 이 "
        "도메인 용어를 일관된 방식으로 해석하기 위한 기준점입니다."
    )
    st.caption(
        f"한국 생명보험 도메인 용어 사전 · v{meta.get('version', '?')} · "
        f"{meta.get('감수', '')}"
    )

    # Tier 범례 — 상시 표시 (Glossary 이해의 안내 성격이라 접지 않음).
    # 라벨/설명 모두 코드에서 톤 다운 (공식 분류 체계가 아니라 출처 성격 안내).
    tiers = meta.get("definition_tiers", {})
    if tiers:
        with st.container(border=True):
            st.markdown(
                '<div style="font-weight:600; font-size:0.85rem; color:#374151; '
                'margin-bottom:4px;">📌 Glossary 라벨 안내</div>'
                '<div style="font-size:0.78rem; color:#6b7280; margin-bottom:10px;">'
                '각 항목 옆 색상 dot 은 그 정의가 어떤 성격의 공개 자료 또는 '
                'PoC 가정에 기반하는지 안내하는 보조 메타입니다.</div>',
                unsafe_allow_html=True,
            )
            tier_cols = st.columns(len(tiers))
            for col, (tier_key, yaml_desc) in zip(tier_cols, tiers.items()):
                with col:
                    label, bg, fg = TIER_STYLE.get(
                        tier_key, (tier_key, "#e5e7eb", "#374151"),
                    )
                    dot = TIER_DOT.get(tier_key, "")
                    st.markdown(
                        f'<span style="margin-right:4px;">{dot}</span>'
                        f'<span style="display:inline-block; padding:2px 10px; '
                        f'border-radius:12px; background:{bg}; color:{fg}; '
                        f'font-size:0.75rem; font-weight:600;">{label}</span>',
                        unsafe_allow_html=True,
                    )
                    desc = _TIER_DESC_OVERRIDE.get(tier_key, yaml_desc)
                    st.caption(desc)

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
            tier = entry.get("tier")
            dot = TIER_DOT.get(tier, "") if tier else ""
            header = term.replace("_", " ")
            if en:
                header = f"{header}  ·  _{en}_"
            if dot:
                # 색상 dot 을 라벨 prefix 로 — expander 접힘 상태에서도 출처 성격 노출
                header = f"{dot}  {header}"
            with st.expander(header, expanded=False):
                _render_entry(term, entry)

    if query:
        st.caption(f"검색 결과: {shown}/{total}개")
    else:
        st.caption(f"등록 용어: {total}개")
