"""
테이블별 베이스라인 데이터 생성 함수

원칙:
- 순수 함수 (DB 접속 X, 부작용 X)
- 이상 패턴 주입 X (anomalies.py에서 overlay)
- 입력: config 파라미터 + Faker 인스턴스
- 출력: dict 리스트 (INSERT 가능한 형태)

생성 순서 (FK 의존성):
  products → agents → customers → policies → premium_payments → claims
"""
from __future__ import annotations

import random
from datetime import date, timedelta
from typing import Any

import numpy as np
from faker import Faker

from data.seed import config as C


# =============================================================
# 유틸리티
# =============================================================
def _weighted_choice(dist: dict[str, float], rng: random.Random) -> str:
    """분포 dict에서 하나 샘플링. 합이 1.0이라 가정."""
    keys = list(dist.keys())
    weights = list(dist.values())
    return rng.choices(keys, weights=weights, k=1)[0]


def _random_date(start: date, end: date, rng: random.Random) -> date:
    """start~end 사이 균일 랜덤 날짜."""
    delta_days = (end - start).days
    return start + timedelta(days=rng.randint(0, delta_days))


def _age_to_birth_year(age_group: str, rng: random.Random) -> int:
    """연령대 문자열 → 실제 출생연도 계산."""
    current_year = C.DATA_END_YEAR
    ranges = {
        "20s":  (20, 29),
        "30s":  (30, 39),
        "40s":  (40, 49),
        "50s":  (50, 59),
        "60s+": (60, 75),
    }
    low, high = ranges[age_group]
    age = rng.randint(low, high)
    return current_year - age


# =============================================================
# 1. products
# =============================================================
def generate_products(rng: random.Random) -> list[dict[str, Any]]:
    """
    상품 마스터 ~20개 생성.
    상품군 × 상품유형 조합에서 분포 비중 맞춰서 생성.
    """
    # 상품명 템플릿
    name_templates = {
        "건강": ["건강플러스", "든든암보장", "메디케어", "헬스가드"],
        "종신": ["평생사랑", "가족사랑종신", "프리미엄종신"],
        "연금": ["행복연금", "든든연금", "프리미엄연금"],
        "저축": ["목돈마련", "스마트저축", "행복저축"],
        "정기": ["심플정기", "프리미엄정기"],
    }

    products: list[dict[str, Any]] = []
    for i in range(C.N_PRODUCTS):
        group = _weighted_choice(C.PRODUCT_GROUP_DISTRIBUTION, rng)
        ptype = _weighted_choice(C.PRODUCT_TYPE_DISTRIBUTION, rng)

        # 정합성 룰 — 변액은 '건강' 같은 보장성 결합 드묾
        # 간단히: 변액이면 상품군을 '종신' 또는 '연금'으로 강제
        if ptype == "변액" and group not in ("종신", "연금"):
            group = rng.choice(["종신", "연금"])

        name_base = rng.choice(name_templates[group])
        product_code = f"P{i+1:03d}"
        product_name = f"{name_base}{rng.choice(['I', 'II', 'III', 'Plus'])}"

        base_premium_lo, base_premium_hi = C.MONTHLY_PREMIUM_BY_GROUP[group]
        base_premium = rng.randint(base_premium_lo, base_premium_hi)

        launch_date = _random_date(
            date(C.DATA_START_YEAR, 1, 1),
            date(C.DATA_END_YEAR - 1, 12, 31),
            rng,
        )

        products.append({
            "product_code": product_code,
            "product_name": product_name,
            "product_type": ptype,
            "product_group": group,
            "base_premium": base_premium,
            "launch_date":  launch_date,
        })

    return products


# =============================================================
# 2. agents
# =============================================================
def generate_agents(fake: Faker, rng: random.Random) -> list[dict[str, Any]]:
    """설계사 ~50명 생성. 채널별 분포 반영."""
    agents: list[dict[str, Any]] = []
    for i in range(C.N_AGENTS):
        channel = _weighted_choice(C.CHANNEL_DISTRIBUTION, rng)
        hire_date = _random_date(
            date(C.DATA_START_YEAR, 1, 1),
            date(C.DATA_END_YEAR, 6, 30),
            rng,
        )
        # 채널별 소속사명 템플릿
        agency_names = {
            "방카": f"{fake.company()}은행 방카영업부",
            "전속": "한화생명 전속",
            "GA":   f"{fake.company()} GA",
            "TM":   "한화생명 TM센터",
            "CM":   "한화생명 CM센터",
        }
        agents.append({
            "agent_code":  f"A{i+1:04d}",
            "agent_name":  fake.name(),
            "channel_type": channel,
            "agency_name":  agency_names[channel],
            "hire_date":    hire_date,
            "active":       rng.random() > 0.05,  # 5%는 비활성
        })
    return agents


# =============================================================
# 3. customers
# =============================================================
def generate_customers(fake: Faker, rng: random.Random) -> list[dict[str, Any]]:
    """
    고객 ~10,000명 생성.

    PII 처리 (DLP 오탐 방지):
    - 주민번호: RRN-XXXXXX 더미 포맷 (숫자만 있는 실제 포맷 회피)
    - 전화: 010-99XX-XXXX (미할당 대역)
    - 이메일: @example.com (IANA 예약 도메인)
    - 주소: 시/도 + 시군구까지만
    """
    customers: list[dict[str, Any]] = []
    for i in range(C.N_CUSTOMERS):
        age_group = _weighted_choice(C.AGE_GROUP_DISTRIBUTION, rng)
        birth_year = _age_to_birth_year(age_group, rng)
        birth_date = date(
            birth_year,
            rng.randint(1, 12),
            rng.randint(1, 28),
        )
        gender = _weighted_choice(C.GENDER_DISTRIBUTION, rng)

        # 한국어 이름
        full_name = fake.name()

        # 주민번호 더미 (DLP 회피)
        resident_number = f"RRN-{rng.randint(100000, 999999)}"

        # 전화: 010-99XX-XXXX (미할당 대역)
        phone = f"010-99{rng.randint(0, 99):02d}-{rng.randint(0, 9999):04d}"

        # 주소: 시도 + 시군구까지만
        si_do = rng.choice([
            "서울특별시", "부산광역시", "인천광역시", "대구광역시",
            "대전광역시", "광주광역시", "울산광역시",
            "경기도", "강원도", "충청남도", "충청북도",
            "전라남도", "전라북도", "경상남도", "경상북도", "제주특별자치도",
        ])
        gu = rng.choice(["중구", "동구", "서구", "남구", "북구", "수성구", "성남시 분당구"])
        address = f"{si_do} {gu}"

        # 이메일: 명백한 더미
        email = f"cust{i+1:05d}@example.com"

        # 가입일 (생일 이후, DATA_END_YEAR 이전)
        earliest_join = date(max(C.DATA_START_YEAR, birth_year + 20), 1, 1)
        latest_join = date(C.DATA_END_YEAR, 12, 31)
        if earliest_join >= latest_join:
            earliest_join = date(C.DATA_START_YEAR, 1, 1)
        joined_at = _random_date(earliest_join, latest_join, rng)

        customers.append({
            "full_name":       full_name,
            "resident_number": resident_number,
            "birth_date":      birth_date,
            "gender":          gender,
            "phone":           phone,
            "address":         address,
            "email":           email,
            "joined_at":       joined_at,
        })

    return customers


# =============================================================
# 4. policies
# =============================================================
def generate_policies(
    customers: list[dict[str, Any]],
    products: list[dict[str, Any]],
    agents: list[dict[str, Any]],
    rng: random.Random,
) -> list[dict[str, Any]]:
    """
    계약 ~30,000건 생성.

    정합성 룰:
    - issue_date >= customer.joined_at
    - 상품군 × 연령 범위 매칭 (PRODUCT_AGE_RULES)
    - 변액/정기 상품 → 일시납 금지
    - status: 대부분 'active', 일부 'lapsed' (이상 패턴은 anomalies.py에서)

    product/agent는 "인덱스 참조"로 저장. 실제 FK는 load.py에서 주입.
    """
    policies: list[dict[str, Any]] = []
    policy_counter = 0

    # 각 고객에게 몇 개 계약 줄지 (평균 3, 최대 6)
    # Poisson 분포 사용 → 자연스러운 편차
    contracts_per_customer = np.random.poisson(
        C.AVG_POLICIES_PER_CUSTOMER, len(customers)
    ).clip(1, C.POLICIES_PER_CUSTOMER_MAX)

    target_n = C.N_POLICIES

    for cust_idx, n_contracts in enumerate(contracts_per_customer):
        if policy_counter >= target_n:
            break

        customer = customers[cust_idx]
        cust_age_at_end = C.DATA_END_YEAR - customer["birth_date"].year

        for _ in range(n_contracts):
            if policy_counter >= target_n:
                break

            # 연령에 맞는 상품 후보 필터링
            age_compatible_products = [
                (i, p) for i, p in enumerate(products)
                if C.PRODUCT_AGE_RULES[p["product_group"]][0]
                <= cust_age_at_end
                <= C.PRODUCT_AGE_RULES[p["product_group"]][1]
            ]
            if not age_compatible_products:
                continue  # 연령 범위에 맞는 상품 없음 → skip

            prod_idx, product = rng.choice(age_compatible_products)
            agent_idx = rng.randint(0, len(agents) - 1)

            # 계약 체결일: customer 가입일 이후
            earliest_issue = customer["joined_at"]
            latest_issue = date(C.DATA_END_YEAR, 12, 31)
            if earliest_issue >= latest_issue:
                continue
            issue_date = _random_date(earliest_issue, latest_issue, rng)

            # 납입주기: 상품유형에 따라 제한
            if product["product_type"] in C.PRODUCT_TYPE_NO_SINGLE:
                freq_dist = {
                    k: v for k, v in C.PAYMENT_FREQUENCY_DISTRIBUTION.items()
                    if k != "single"
                }
                total = sum(freq_dist.values())
                freq_dist = {k: v / total for k, v in freq_dist.items()}
            else:
                freq_dist = C.PAYMENT_FREQUENCY_DISTRIBUTION

            payment_frequency = _weighted_choice(freq_dist, rng)

            # 월 보험료 (상품군 범위 내 + 개인 편차)
            lo, hi = C.MONTHLY_PREMIUM_BY_GROUP[product["product_group"]]
            monthly_premium = rng.randint(lo, hi)

            # annual / sum_insured
            if payment_frequency == "monthly":
                annual_premium = monthly_premium * 12
            elif payment_frequency == "annual":
                annual_premium = monthly_premium * 12
            else:  # single
                annual_premium = monthly_premium * 12 * rng.randint(5, 20)

            sum_insured = annual_premium * rng.randint(10, 100)

            # 만기일 (상품군별 default 기간)
            term_years = {
                "건강": 20, "종신": 80, "연금": 30,
                "저축": 10, "정기": 15,
            }[product["product_group"]]

            # Feb 29 -> 평년 이동 시 ValueError 방지
            maturity_year = min(issue_date.year + term_years, 2099)
            maturity_day = issue_date.day
            if issue_date.month == 2 and issue_date.day == 29:
                maturity_day = 28
            maturity_date = date(maturity_year, issue_date.month, maturity_day)


            # 상태: 일단 전부 'active'. anomalies.py가 일부 lapsed 전환
            status = "active"

            policy_counter += 1
            policies.append({
                "_idx":              policy_counter - 1,  # 내부 참조용
                "policy_number":     f"POL-{policy_counter:07d}",
                "_customer_idx":     cust_idx,
                "_product_idx":      prod_idx,
                "_agent_idx":        agent_idx,
                "issue_date":        issue_date,
                "maturity_date":     maturity_date,
                "status":            status,
                "monthly_premium":   monthly_premium,
                "annual_premium":    annual_premium,
                "sum_insured":       sum_insured,
                "payment_frequency": payment_frequency,
                "cohort_year":       issue_date.year,
                "ifrs17_group_id":   None,  # Future Work
                "measurement_model": None,  # Future Work
            })

    return policies


# =============================================================
# 5. premium_payments
# =============================================================
def generate_premium_payments(
    policies: list[dict[str, Any]],
    rng: random.Random,
) -> list[dict[str, Any]]:
    """
    납입 이력 생성.

    규칙:
    - monthly: issue_date부터 매월 1건
    - annual:  issue_date부터 매년 1건
    - single:  issue_date에 단 1건

    종료 시점: status='active'면 DATA_END_YEAR까지,
              status='lapsed'면 lapsed_date 전까지 (anomalies.py에서 잘림)
    """
    payments: list[dict[str, Any]] = []
    today = date(C.DATA_END_YEAR, 12, 31)

    for policy in policies:
        issue = policy["issue_date"]
        freq = policy["payment_frequency"]
        amount = policy["monthly_premium"]

        if freq == "single":
            payments.append({
                "_policy_idx":  policy["_idx"],
                "payment_date": issue,
                "amount":       policy["annual_premium"],  # 일시납 전액
                "status":       "paid",
            })
            continue

        # monthly or annual → 정기 납입
        step_months = 1 if freq == "monthly" else 12
        current = issue
        while current <= today:
            payments.append({
                "_policy_idx":  policy["_idx"],
                "payment_date": current,
                "amount":       amount if freq == "monthly" else amount * 12,
                "status":       "paid",
            })
            # 다음 납입일
            next_month = current.month + step_months
            next_year = current.year + (next_month - 1) // 12
            next_month = (next_month - 1) % 12 + 1
            try:
                current = current.replace(year=next_year, month=next_month)
            except ValueError:
                # 2/31 같은 경우 → 월말로 보정
                current = date(next_year, next_month, 28)

    return payments


# =============================================================
# 6. claims
# =============================================================
def generate_claims(
    policies: list[dict[str, Any]],
    products: list[dict[str, Any]],
    rng: random.Random,
) -> list[dict[str, Any]]:
    """
    보험금 청구 ~5,000건 생성.

    규칙:
    - 청약철회 기간(90일) 이후 발생
    - 건강/종신/정기 상품에 집중 (저축/연금/변액은 claim 드묾)
    """
    # claim 발생 가능성 높은 상품군
    claim_prone_groups = {"건강", "종신", "정기"}

    # 후보 policy: claim이 날 만한 상품군
    candidates = [
        p for p in policies
        if products[p["_product_idx"]]["product_group"] in claim_prone_groups
    ]

    if not candidates:
        return []

    claims: list[dict[str, Any]] = []
    target = min(C.N_CLAIMS, len(candidates))

    selected = rng.sample(candidates, target)

    claim_types = [
        "입원", "통원", "수술", "사망", "만기", "암진단",
    ]

    for policy in selected:
        issue = policy["issue_date"]
        # 청약철회 후 (90일)
        earliest = issue + timedelta(days=90)
        latest = date(C.DATA_END_YEAR, 12, 31)
        if earliest >= latest:
            continue

        claim_date = _random_date(earliest, latest, rng)
        claim_type = rng.choice(claim_types)

        # 청구 금액: 월 보험료의 10~100배
        amount = policy["monthly_premium"] * rng.randint(10, 100)

        # paid_date: 청구 후 7~30일
        paid_date = claim_date + timedelta(days=rng.randint(7, 30))
        if paid_date > latest:
            paid_date = None
            status = "pending"
        else:
            status = rng.choices(
                ["paid", "approved", "rejected"],
                weights=[0.7, 0.2, 0.1],
            )[0]

        claims.append({
            "_policy_idx": policy["_idx"],
            "claim_date":  claim_date,
            "paid_date":   paid_date,
            "claim_type":  claim_type,
            "amount":      amount,
            "status":      status,
        })

    return claims
