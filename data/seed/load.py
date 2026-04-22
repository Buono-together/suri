"""
SURI 합성 데이터 로드 엔트리포인트

실행: uv run python -m data.seed.load

흐름:
1. suri_admin으로 DB 연결
2. TRUNCATE (멱등성)
3. 베이스라인 생성 (generators.py)
4. 이상 패턴 overlay (anomalies.py)
5. COPY FROM STDIN bulk insert
6. ANALYZE
7. 자동 검증 (checks.py)
"""
from __future__ import annotations

import random
import sys
import time
from datetime import date
from typing import Any

import numpy as np
import psycopg
from faker import Faker

from data.seed import config as C
from data.seed import generators as G
from data.seed import anomalies as A
from data.seed import checks as CHK


# =============================================================
# DB 연결 문자열
# =============================================================
def get_admin_dsn() -> str:
    return (
        f"host={C.DB_HOST} port={C.DB_PORT} dbname={C.DB_NAME} "
        f"user={C.DB_USER} password={C.DB_PASSWORD}"
    )


# =============================================================
# 유틸
# =============================================================
def _log(msg: str, elapsed: float | None = None) -> None:
    prefix = "[seed]"
    if elapsed is not None:
        print(f"{prefix} {msg} ({elapsed:.2f}s)")
    else:
        print(f"{prefix} {msg}")


# =============================================================
# TRUNCATE (멱등성)
# =============================================================
def truncate_all(conn: psycopg.Connection) -> None:
    """모든 테이블 비우기. FK 때문에 CASCADE + RESTART IDENTITY."""
    with conn.cursor() as cur:
        cur.execute("""
            TRUNCATE TABLE
              claims,
              premium_payments,
              policies,
              customers,
              agents,
              products
            RESTART IDENTITY CASCADE
        """)
    conn.commit()


# =============================================================
# COPY 유틸 (psycopg 3)
# =============================================================
def copy_rows(
    conn: psycopg.Connection,
    table: str,
    columns: list[str],
    rows: list[tuple],
) -> None:
    """
    COPY FROM STDIN으로 bulk insert.
    일반 INSERT 대비 10~50배 빠름.
    """
    col_list = ", ".join(columns)
    with conn.cursor() as cur:
        with cur.copy(f"COPY {table} ({col_list}) FROM STDIN") as copy:
            for row in rows:
                copy.write_row(row)


# =============================================================
# 엔티티별 로드 함수
# =============================================================
def load_products(conn: psycopg.Connection, products: list[dict]) -> None:
    rows = [
        (
            p["product_code"],
            p["product_name"],
            p["product_type"],
            p["product_group"],
            p["base_premium"],
            p["launch_date"],
        )
        for p in products
    ]
    copy_rows(
        conn, "products",
        ["product_code", "product_name", "product_type",
         "product_group", "base_premium", "launch_date"],
        rows,
    )


def load_agents(conn: psycopg.Connection, agents: list[dict]) -> None:
    rows = [
        (
            a["agent_code"],
            a["agent_name"],
            a["channel_type"],
            a["agency_name"],
            a["hire_date"],
            a["active"],
        )
        for a in agents
    ]
    copy_rows(
        conn, "agents",
        ["agent_code", "agent_name", "channel_type",
         "agency_name", "hire_date", "active"],
        rows,
    )


def load_customers(conn: psycopg.Connection, customers: list[dict]) -> None:
    rows = [
        (
            c["full_name"],
            c["resident_number"],
            c["birth_date"],
            c["gender"],
            c["phone"],
            c["address"],
            c["email"],
            c["joined_at"],
        )
        for c in customers
    ]
    copy_rows(
        conn, "customers",
        ["full_name", "resident_number", "birth_date", "gender",
         "phone", "address", "email", "joined_at"],
        rows,
    )


def load_policies(
    conn: psycopg.Connection,
    policies: list[dict],
    customer_id_map: dict[int, int],
    product_id_map: dict[int, int],
    agent_id_map: dict[int, int],
) -> None:
    """
    _customer_idx / _product_idx / _agent_idx → 실제 FK (customer_id 등)로 변환.
    """
    rows = [
        (
            p["policy_number"],
            customer_id_map[p["_customer_idx"]],
            product_id_map[p["_product_idx"]],
            agent_id_map[p["_agent_idx"]],
            p["issue_date"],
            p["maturity_date"],
            p["status"],
            p["monthly_premium"],
            p["annual_premium"],
            p["sum_insured"],
            p["payment_frequency"],
            p["cohort_year"],
            p["ifrs17_group_id"],
            p["measurement_model"],
        )
        for p in policies
    ]
    copy_rows(
        conn, "policies",
        ["policy_number", "customer_id", "product_id", "agent_id",
         "issue_date", "maturity_date", "status",
         "monthly_premium", "annual_premium", "sum_insured",
         "payment_frequency", "cohort_year",
         "ifrs17_group_id", "measurement_model"],
        rows,
    )


def load_payments(
    conn: psycopg.Connection,
    payments: list[dict],
    policy_id_map: dict[int, int],
) -> None:
    rows = [
        (
            policy_id_map[pay["_policy_idx"]],
            pay["payment_date"],
            pay["amount"],
            pay["status"],
        )
        for pay in payments
    ]
    copy_rows(
        conn, "premium_payments",
        ["policy_id", "payment_date", "amount", "status"],
        rows,
    )


def load_claims(
    conn: psycopg.Connection,
    claims: list[dict],
    policy_id_map: dict[int, int],
) -> None:
    rows = [
        (
            policy_id_map[cl["_policy_idx"]],
            cl["claim_date"],
            cl["paid_date"],
            cl["claim_type"],
            cl["amount"],
            cl["status"],
        )
        for cl in claims
    ]
    copy_rows(
        conn, "claims",
        ["policy_id", "claim_date", "paid_date",
         "claim_type", "amount", "status"],
        rows,
    )


# =============================================================
# ID 매핑 헬퍼
# =============================================================
def fetch_id_map(
    conn: psycopg.Connection,
    table: str,
    pk: str,
    natural_key_col: str,
    ordered_natural_keys: list[str],
) -> dict[int, int]:
    """
    내부 _idx (생성 순서) → DB pk 매핑.
    natural_key_col (product_code 등)를 통해 lookup.
    """
    with conn.cursor() as cur:
        cur.execute(f"SELECT {natural_key_col}, {pk} FROM {table}")
        nkey_to_pk = dict(cur.fetchall())

    return {idx: nkey_to_pk[nk] for idx, nk in enumerate(ordered_natural_keys)}


def fetch_customer_id_map(
    conn: psycopg.Connection,
    customers: list[dict],
) -> dict[int, int]:
    """
    customers는 natural key가 없으므로 INSERT 순서 = customer_id 가정.
    COPY는 순서를 보존하므로 IDENTITY는 1부터 순차 할당됨.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT customer_id FROM customers ORDER BY customer_id")
        ids = [r[0] for r in cur.fetchall()]
    assert len(ids) == len(customers), "customer count mismatch"
    return {idx: cid for idx, cid in enumerate(ids)}


def fetch_policy_id_map(
    conn: psycopg.Connection,
    policies: list[dict],
) -> dict[int, int]:
    """policy_number가 unique → 이걸로 매핑."""
    with conn.cursor() as cur:
        cur.execute("SELECT policy_number, policy_id FROM policies")
        pn_to_id = dict(cur.fetchall())
    return {p["_idx"]: pn_to_id[p["policy_number"]] for p in policies}


# =============================================================
# ANALYZE
# =============================================================
def analyze_all(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute("ANALYZE")


# =============================================================
# 메인
# =============================================================
def main() -> int:
    t0 = time.time()
    _log("Starting SURI seed pipeline")
    _log(f"  Seed: {C.SEED}")

    # 시드 고정
    rng = random.Random(C.SEED)
    fake = Faker("ko_KR")
    Faker.seed(C.SEED)
    np.random.seed(C.SEED)

    # -----------------------------------------
    # Stage 1: In-memory generation
    # -----------------------------------------
    _log("Stage 1: Generating baseline data...")
    t = time.time()

    products  = G.generate_products(rng)
    agents    = G.generate_agents(fake, rng)
    customers = G.generate_customers(fake, rng)
    policies  = G.generate_policies(customers, products, agents, rng)
    payments  = G.generate_premium_payments(policies, rng)
    claims    = G.generate_claims(policies, products, rng)

    _log(
        f"  products={len(products)}, agents={len(agents)}, "
        f"customers={len(customers)}, policies={len(policies)}, "
        f"payments={len(payments)}, claims={len(claims)}",
        time.time() - t,
    )

    # -----------------------------------------
    # Stage 2: Anomaly overlay
    # -----------------------------------------
    _log("Stage 2: Injecting anomalies...")
    t = time.time()

    r1 = A.inject_ga_retention_drop(policies, payments, agents, rng)
    payments = r1["payments_filtered"]
    _log(f"  GA retention: {r1['affected_policies']} policies, "
         f"{r1['deleted_payments']} payments removed")

    r2 = A.inject_march_surge(policies, rng)
    _log(f"  March surge: {r2['moved_to_march']} moved, "
         f"ratio→ {r2['after_march_count'] / max(r2['before_march_count'], 1):.2f}x")

    r3 = A.inject_product_outlier(policies, payments, rng)
    payments = r3["payments_filtered"]
    _log(f"  Product outlier: {r3['affected_policies']} policies affected",
         time.time() - t)

    # -----------------------------------------
    # Stage 3: Load to DB
    # -----------------------------------------
    _log("Stage 3: Loading to PostgreSQL...")
    t = time.time()

    with psycopg.connect(get_admin_dsn()) as conn:
        # TRUNCATE
        truncate_all(conn)
        _log("  TRUNCATE complete")

        # Products (no FK dependency)
        load_products(conn, products)
        conn.commit()
        _log(f"  products: {len(products)} rows")

        # Agents
        load_agents(conn, agents)
        conn.commit()
        _log(f"  agents: {len(agents)} rows")

        # Customers
        load_customers(conn, customers)
        conn.commit()
        _log(f"  customers: {len(customers)} rows")

        # ID 매핑 생성 (customers, products, agents)
        customer_id_map = fetch_customer_id_map(conn, customers)
        product_id_map = fetch_id_map(
            conn, "products", "product_id", "product_code",
            [p["product_code"] for p in products],
        )
        agent_id_map = fetch_id_map(
            conn, "agents", "agent_id", "agent_code",
            [a["agent_code"] for a in agents],
        )

        # Policies (FK: customers, products, agents)
        load_policies(conn, policies, customer_id_map, product_id_map, agent_id_map)
        conn.commit()
        _log(f"  policies: {len(policies)} rows")

        # policy_id_map 생성
        policy_id_map = fetch_policy_id_map(conn, policies)

        # Payments (FK: policies) — 대용량
        load_payments(conn, payments, policy_id_map)
        conn.commit()
        _log(f"  premium_payments: {len(payments)} rows")

        # Claims (FK: policies)
        load_claims(conn, claims, policy_id_map)
        conn.commit()
        _log(f"  claims: {len(claims)} rows")

        _log("Load complete", time.time() - t)

        # -----------------------------------------
        # Stage 4: ANALYZE
        # -----------------------------------------
        _log("Stage 4: ANALYZE...")
        t = time.time()
        analyze_all(conn)
        conn.commit()
        _log("  ANALYZE complete", time.time() - t)

        # -----------------------------------------
        # Stage 5: Auto validation
        # -----------------------------------------
        _log("Stage 5: Auto validation...")
        CHK.run_all_checks(conn)

    total = time.time() - t0
    _log(f"\n✓ Pipeline complete in {total:.2f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
