"""
이상 패턴 overlay — 2단계 주입 방식

원칙:
- generators.py는 베이스라인만 (이상 패턴 없음)
- 이 파일이 베이스라인 위에 이상 패턴을 덧씌움
- 각 함수는 독립 실행 가능 (토글 가능)
- 변경 이력을 로그로 반환 (checks.py에서 검증)

주입 패턴:
1. inject_ga_retention_drop: GA 채널 13·25회차 유지율 낙차
2. inject_march_surge:       3월 절판 스파이크
3. inject_product_outlier:   특정 상품의 25회차 이상치
"""
from __future__ import annotations

import random
from datetime import date, timedelta
from typing import Any

from data.seed import config as C


# =============================================================
# 1. GA 채널 유지율 낙차
# =============================================================
def inject_ga_retention_drop(
    policies: list[dict[str, Any]],
    payments: list[dict[str, Any]],
    agents: list[dict[str, Any]],
    rng: random.Random,
) -> dict[str, Any]:
    """
    GA 채널 계약 중 일부를 13회차/25회차 이후 lapsed 전환.

    KIRI 2022 기준: GA 25회차 유지율 68% (vs 전속 69%)
    → 약 19%의 GA 계약을 target_months에서 추가 lapse

    동작:
    1. channel='GA'이면서 payment_frequency='monthly'인 월납 계약 필터
    2. 충분한 기간이 지난 계약만 (issue_date가 target_months 이전)
    3. lapse_probability 확률로 랜덤 선택
    4. 선택된 계약의 status='lapsed', lapsed_date 설정
    5. lapsed_date 이후 payment 삭제
    """
    params = C.GA_RETENTION_DROP
    today = date(C.DATA_END_YEAR, 12, 31)

    # agent_idx → channel 매핑
    agent_channel = {i: a["channel_type"] for i, a in enumerate(agents)}

    # GA 채널 월납 계약 필터
    ga_policies = [
        p for p in policies
        if agent_channel.get(p["_agent_idx"]) == params["channel"]
        and p["payment_frequency"] == "monthly"
        and p["status"] == "active"
    ]

    affected_policy_idxs = set()
    ga_lapsed_counts = {m: 0 for m in params["target_months"]}

    for policy in ga_policies:
        # target_months 중 랜덤 하나
        target_month = rng.choice(params["target_months"])

        # 해당 시점이 미래면 skip
        target_date = policy["issue_date"] + _months_to_timedelta(target_month)
        if target_date > today:
            continue

        # lapse_probability 확률로 선택
        if rng.random() >= params["lapse_probability"]:
            continue

        # 해지 처리
        grace_months = rng.randint(C.LAPSE_GRACE_MONTHS_MIN, C.LAPSE_GRACE_MONTHS_MAX)
        lapsed_date = target_date + _months_to_timedelta(grace_months)
        if lapsed_date > today:
            lapsed_date = today

        policy["status"] = "lapsed"
        policy["lapsed_date"] = lapsed_date  # 동적 컬럼 (DB에는 없음, 참조용)

        affected_policy_idxs.add(policy["_idx"])
        ga_lapsed_counts[target_month] += 1

    # payments 삭제: lapsed 계약의 lapsed_date 이후 납입 제거
    original_payment_count = len(payments)
    policy_lapsed_dates = {
        p["_idx"]: p.get("lapsed_date")
        for p in policies
        if p["status"] == "lapsed" and p["_idx"] in affected_policy_idxs
    }

    payments_filtered = [
        pay for pay in payments
        if (
            pay["_policy_idx"] not in policy_lapsed_dates
            or pay["payment_date"] <= policy_lapsed_dates[pay["_policy_idx"]]
        )
    ]
    deleted = original_payment_count - len(payments_filtered)

    return {
        "affected_policies":      len(affected_policy_idxs),
        "by_target_month":        ga_lapsed_counts,
        "deleted_payments":       deleted,
        "payments_filtered":      payments_filtered,
    }


# =============================================================
# 2. 3월 절판 스파이크
# =============================================================
def inject_march_surge(
    policies: list[dict[str, Any]],
    rng: random.Random,
) -> dict[str, Any]:
    """
    3월 issue_date 계약 비율을 평월의 1.8배로 증폭.

    방법: 3월이 아닌 달에서 랜덤 샘플링하여 3월로 issue_date 이동.
    전체 계약 수는 보존.
    """
    params = C.MARCH_SURGE
    target_month = params["target_month"]
    multiplier = params["multiplier"]

    # 현재 3월 계약 수
    march_policies = [p for p in policies if p["issue_date"].month == target_month]
    non_march_policies = [p for p in policies if p["issue_date"].month != target_month]

    current_march = len(march_policies)
    # 평균 월별 계약 수 (3월 제외한 11개월 평균)
    avg_per_month = len(non_march_policies) / 11.0
    target_march = int(avg_per_month * multiplier)

    need_to_move = max(0, target_march - current_march)
    need_to_move = min(need_to_move, len(non_march_policies))

    # 비-3월 계약 중 랜덤 샘플링 → 3월로 이동
    to_move = rng.sample(non_march_policies, need_to_move)
    for policy in to_move:
        original = policy["issue_date"]
        day = min(original.day, 28)  # 3월은 31일이지만 안전하게 28까지
        new_date = date(original.year, target_month, day)
        policy["issue_date"] = new_date
        policy["cohort_year"] = new_date.year  # cohort_year도 갱신 (이 경우 동일)

    return {
        "before_march_count": current_march,
        "moved_to_march":     need_to_move,
        "after_march_count":  current_march + need_to_move,
        "target_ratio":       multiplier,
    }


# =============================================================
# 3. 특정 상품 이상치
# =============================================================
def inject_product_outlier(
    policies: list[dict[str, Any]],
    payments: list[dict[str, Any]],
    rng: random.Random,
) -> dict[str, Any]:
    """
    특정 product_index 계약의 25회차 유지율을 업계 평균 대비 급락.

    교보생명 2023년 사례 모델링: 25회차 시점 -19.6%p 추가 lapse
    """
    params = C.PRODUCT_OUTLIER
    target_prod_idx = params["product_index"]
    target_month = params["target_month"]
    extra_rate = params["extra_lapse_rate"]
    today = date(C.DATA_END_YEAR, 12, 31)

    # 대상 상품의 월납 + active 계약
    target_policies = [
        p for p in policies
        if p["_product_idx"] == target_prod_idx
        and p["payment_frequency"] == "monthly"
        and p["status"] == "active"
    ]

    affected_idxs = set()
    for policy in target_policies:
        target_date = policy["issue_date"] + _months_to_timedelta(target_month)
        if target_date > today:
            continue

        if rng.random() >= extra_rate:
            continue

        grace_months = rng.randint(C.LAPSE_GRACE_MONTHS_MIN, C.LAPSE_GRACE_MONTHS_MAX)
        lapsed_date = target_date + _months_to_timedelta(grace_months)
        if lapsed_date > today:
            lapsed_date = today

        policy["status"] = "lapsed"
        policy["lapsed_date"] = lapsed_date
        affected_idxs.add(policy["_idx"])

    # 이번 overlay에서 영향 받은 계약의 payment 정리
    original_count = len(payments)
    policy_lapsed_dates = {
        p["_idx"]: p["lapsed_date"]
        for p in policies
        if p["_idx"] in affected_idxs and "lapsed_date" in p
    }
    payments_filtered = [
        pay for pay in payments
        if (
            pay["_policy_idx"] not in policy_lapsed_dates
            or pay["payment_date"] <= policy_lapsed_dates[pay["_policy_idx"]]
        )
    ]
    deleted = original_count - len(payments_filtered)

    return {
        "target_product_idx": target_prod_idx,
        "affected_policies": len(affected_idxs),
        "deleted_payments":  deleted,
        "payments_filtered": payments_filtered,
    }


# =============================================================
# 유틸
# =============================================================
def _months_to_timedelta(months: int) -> timedelta:
    """월 수를 대략적인 일수로 변환 (1개월 ≈ 30.44일)."""
    return timedelta(days=int(months * 30.44))
