"""
데이터 로드 후 자동 검증

각 assert:
- SQL 실행
- 기대값 ± 허용 오차 범위 내 확인
- 실패 시 상세 메시지와 함께 AssertionError

면접 하이라이트:
"데이터 생성 후 이상 패턴이 실제 DB에 반영됐는지 자동 검증합니다.
GA 25회차 유지율, 3월 스파이크 배수, PII 거버넌스 3개 축을 확인합니다."
"""
from __future__ import annotations

import psycopg

from data.seed import config as C


# =============================================================
# 검증 1: 기본 카운트
# =============================================================
def check_counts(conn: psycopg.Connection) -> dict:
    """테이블별 row 수가 합리적 범위인지 확인."""
    with conn.cursor() as cur:
        counts = {}
        for table in ["products", "agents", "customers", "policies",
                      "premium_payments", "claims"]:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            counts[table] = cur.fetchone()[0]

    # 최소 기대값 (너무 적으면 실패)
    expected_min = {
        "products":          10,
        "agents":            30,
        "customers":         9_000,
        "policies":          20_000,
        "premium_payments":  100_000,
        "claims":            3_000,
    }
    for table, minimum in expected_min.items():
        assert counts[table] >= minimum, (
            f"Row count too low: {table}={counts[table]}, expected >= {minimum}"
        )
    return counts


# =============================================================
# 검증 2: PII 거버넌스
# =============================================================
def check_pii_governance(host: str, port: int, db: str) -> dict:
    """
    suri_readonly 계정으로 접속 → customers 차단, customers_safe 접근 확인.
    """
    results = {}
    readonly_dsn = (
        f"host={host} port={port} dbname={db} "
        f"user=suri_readonly password=readonly_pass"
    )
    with psycopg.connect(readonly_dsn) as ro_conn:
        with ro_conn.cursor() as cur:
            # 1. customers 직접 접근 → 차단되어야 함
            try:
                cur.execute("SELECT * FROM customers LIMIT 1")
                results["customers_blocked"] = False  # 접근 성공 = 실패
            except psycopg.errors.InsufficientPrivilege:
                results["customers_blocked"] = True
                ro_conn.rollback()

            # 2. customers_safe → 성공해야 함
            try:
                cur.execute("SELECT COUNT(*) FROM customers_safe")
                results["customers_safe_accessible"] = True
                results["customers_safe_count"] = cur.fetchone()[0]
            except psycopg.Error:
                results["customers_safe_accessible"] = False
                ro_conn.rollback()

            # 3. UPDATE 시도 → 차단되어야 함
            try:
                cur.execute(
                    "UPDATE products SET product_name='hack' WHERE product_id=1"
                )
                results["update_blocked"] = False
            except psycopg.errors.InsufficientPrivilege:
                results["update_blocked"] = True
                ro_conn.rollback()

    assert results["customers_blocked"], "customers table NOT blocked for suri_readonly"
    assert results["customers_safe_accessible"], "customers_safe NOT accessible for suri_readonly"
    assert results["update_blocked"], "UPDATE NOT blocked for suri_readonly"

    return results


# =============================================================
# 검증 3: GA 유지율 낙차 이상 패턴
# =============================================================
def check_ga_retention_drop(conn: psycopg.Connection) -> dict:
    """
    GA 채널 25회차 유지율을 SQL로 계산.
    목표: ~68% 근처 (베이스라인 100% - 19% lapse ≈ 81%, 허용 범위)

    실제 로직:
    - GA 채널 월납 계약 중 25개월 전에 시작된 계약
    - 이 중 status='active' 비율
    """
    query = """
        SELECT
          a.channel_type,
          COUNT(*) AS total_eligible,
          SUM(CASE WHEN p.status = 'active' THEN 1 ELSE 0 END) AS still_active,
          ROUND(
            100.0 * SUM(CASE WHEN p.status = 'active' THEN 1 ELSE 0 END)
              / COUNT(*), 2
          ) AS retention_pct
        FROM policies p
        JOIN agents a ON p.agent_id = a.agent_id
        WHERE p.payment_frequency = 'monthly'
          AND p.issue_date <= CURRENT_DATE - INTERVAL '25 months'
        GROUP BY a.channel_type
        ORDER BY a.channel_type
    """
    with conn.cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()

    results = {}
    for channel, total, active, retention in rows:
        results[channel] = {
            "total_eligible": total,
            "still_active":   active,
            "retention_pct":  float(retention),
        }

    # GA 유지율이 전속보다 낮아야 이상 패턴 주입 성공
    assert "GA" in results, "GA 채널 데이터 없음"
    assert "전속" in results, "전속 채널 데이터 없음"
    assert results["GA"]["retention_pct"] < results["전속"]["retention_pct"], (
        f"GA retention ({results['GA']['retention_pct']}%) "
        f"should be lower than 전속 ({results['전속']['retention_pct']}%)"
    )

    return results


# =============================================================
# 검증 4: 3월 절판 스파이크
# =============================================================
def check_march_surge(conn: psycopg.Connection) -> dict:
    """
    월별 계약 발생 수 집계 → 3월이 평월의 1.5배 이상인지 확인.
    """
    query = """
        SELECT
          EXTRACT(MONTH FROM issue_date)::INTEGER AS issue_month,
          COUNT(*) AS policy_count
        FROM policies
        GROUP BY EXTRACT(MONTH FROM issue_date)
        ORDER BY issue_month
    """
    with conn.cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()

    by_month = {int(m): c for m, c in rows}
    march_count = by_month.get(3, 0)
    non_march_avg = sum(c for m, c in by_month.items() if m != 3) / 11.0

    ratio = march_count / non_march_avg if non_march_avg > 0 else 0

    assert ratio >= 1.5, (
        f"March surge not detected: march={march_count}, "
        f"non-march avg={non_march_avg:.0f}, ratio={ratio:.2f}"
    )

    return {
        "by_month":        by_month,
        "march_count":     march_count,
        "non_march_avg":   round(non_march_avg, 1),
        "surge_ratio":     round(ratio, 2),
    }


# =============================================================
# 검증 5: PII 포맷 (DLP 회피)
# =============================================================
def check_pii_format(conn: psycopg.Connection) -> dict:
    """
    customers 테이블의 PII 필드가 의도된 더미 포맷인지 확인.
    - resident_number: 'RRN-'으로 시작
    - phone: '010-99'로 시작
    - email: '@example.com'으로 끝남
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
              SUM(CASE WHEN resident_number LIKE 'RRN-%' THEN 1 ELSE 0 END) AS rrn_ok,
              SUM(CASE WHEN phone LIKE '010-99%' THEN 1 ELSE 0 END) AS phone_ok,
              SUM(CASE WHEN email LIKE '%@example.com' THEN 1 ELSE 0 END) AS email_ok,
              COUNT(*) AS total
            FROM customers
        """)
        rrn_ok, phone_ok, email_ok, total = cur.fetchone()

    # 모든 PII가 더미 포맷이어야 함
    assert rrn_ok == total, f"RRN format violation: {rrn_ok}/{total}"
    assert phone_ok == total, f"Phone format violation: {phone_ok}/{total}"
    assert email_ok == total, f"Email format violation: {email_ok}/{total}"

    return {
        "rrn_dummy_format":   f"{rrn_ok}/{total}",
        "phone_unassigned":   f"{phone_ok}/{total}",
        "email_reserved":     f"{email_ok}/{total}",
    }


# =============================================================
# 통합 실행
# =============================================================
def run_all_checks(conn: psycopg.Connection) -> dict:
    """모든 검증 실행 후 결과 집계."""
    print("\n" + "=" * 60)
    print("  DATA VALIDATION")
    print("=" * 60)

    all_results = {}

    print("\n[1/5] Row counts...")
    all_results["counts"] = check_counts(conn)
    for table, count in all_results["counts"].items():
        print(f"  {table:20s}: {count:>10,}")

    print("\n[2/5] PII format...")
    all_results["pii_format"] = check_pii_format(conn)
    for k, v in all_results["pii_format"].items():
        print(f"  {k:25s}: {v}")

    print("\n[3/5] GA retention drop...")
    all_results["ga_retention"] = check_ga_retention_drop(conn)
    for channel, stats in all_results["ga_retention"].items():
        print(
            f"  {channel:5s}: {stats['retention_pct']:>5.1f}% "
            f"({stats['still_active']}/{stats['total_eligible']})"
        )

    print("\n[4/5] March surge...")
    march = check_march_surge(conn)
    all_results["march_surge"] = march
    print(f"  March: {march['march_count']}, non-March avg: {march['non_march_avg']}")
    print(f"  Surge ratio: {march['surge_ratio']}x (target >= 1.5x)")

    print("\n[5/5] PII governance (3-layer defense)...")
    all_results["pii_governance"] = check_pii_governance(
        C.DB_HOST, C.DB_PORT, C.DB_NAME
    )
    for k, v in all_results["pii_governance"].items():
        print(f"  {k:30s}: {v}")

    print("\n" + "=" * 60)
    print("  ALL CHECKS PASSED ✓")
    print("=" * 60)

    return all_results
