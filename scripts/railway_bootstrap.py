"""
Railway 1회성 부트스트랩.

컨테이너 startCommand에서 Streamlit 실행 전에 한 번 돌리는 스크립트.
세 단계가 전부 idempotent이므로 재배포·재시작에도 안전하게 재실행된다.

1. `policies` 테이블이 없으면 `001_init.sql` 적용
2. `002_pii.sql` 적용 (`suri_readonly` 롤 비밀번호를 env에서 치환)
3. `policies` 행 수가 0이면 `data.seed.load.main()` 실행 (~2~3분)

환경 변수 요구사항:
  POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
  POSTGRES_READONLY_PASSWORD  (없으면 'readonly_pass' 기본값)

실행:
  python -m scripts.railway_bootstrap
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "data" / "schema"


def _admin_dsn() -> str:
    missing = [
        k for k in ("POSTGRES_HOST", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD")
        if not os.environ.get(k)
    ]
    if missing:
        raise RuntimeError(
            f"[bootstrap] Missing required env vars: {missing}. "
            "Railway Postgres 참조 변수가 올바르게 설정됐는지 확인하세요."
        )
    return (
        f"host={os.environ['POSTGRES_HOST']} "
        f"port={os.environ.get('POSTGRES_PORT', '5432')} "
        f"dbname={os.environ['POSTGRES_DB']} "
        f"user={os.environ['POSTGRES_USER']} "
        f"password={os.environ['POSTGRES_PASSWORD']}"
    )


def _log(msg: str) -> None:
    # Railway 로그는 한 줄씩 줄바꿈 기준. 즉시 flush.
    print(f"[bootstrap] {msg}", flush=True)


def _table_exists(conn: psycopg.Connection, name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema='public' AND table_name=%s",
            (name,),
        )
        return cur.fetchone() is not None


def _count_rows(conn: psycopg.Connection, table: str) -> int:
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        row = cur.fetchone()
        return int(row[0]) if row else 0


def _apply_sql_file(conn: psycopg.Connection, path: Path) -> None:
    sql = path.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql)


def _apply_pii_sql(conn: psycopg.Connection, readonly_password: str) -> None:
    """002_pii.sql을 읽어 readonly 롤 비밀번호를 env 값으로 치환 후 적용.

    파일 내 'readonly_pass' 리터럴만 변환한다 (다른 위치의 문자열 보존).
    """
    raw = (SCHEMA_DIR / "002_pii.sql").read_text(encoding="utf-8")
    # 유일한 리터럴: CREATE ROLE suri_readonly WITH LOGIN PASSWORD 'readonly_pass';
    if "'readonly_pass'" not in raw:
        raise RuntimeError(
            "[bootstrap] 002_pii.sql에서 'readonly_pass' 리터럴을 찾을 수 없음. "
            "스키마 파일이 변경됐는지 확인."
        )
    patched = raw.replace("'readonly_pass'", f"'{readonly_password}'")
    with conn.cursor() as cur:
        cur.execute(patched)


def main() -> int:
    dsn = _admin_dsn()
    readonly_pw = os.environ.get("POSTGRES_READONLY_PASSWORD", "readonly_pass")

    _log(f"Connecting as admin: host={os.environ['POSTGRES_HOST']} "
         f"db={os.environ['POSTGRES_DB']}")
    with psycopg.connect(dsn, autocommit=True) as conn:
        # Phase 1 — 001_init.sql (테이블 생성)
        if _table_exists(conn, "policies"):
            _log("Phase 1 skip — 테이블 이미 존재.")
        else:
            _log("Phase 1 — 001_init.sql 적용 중…")
            _apply_sql_file(conn, SCHEMA_DIR / "001_init.sql")
            _log("Phase 1 done.")

        # Phase 2 — 002_pii.sql (VIEW + readonly 롤)
        # 항상 재적용 (CREATE OR REPLACE VIEW · DROP ROLE IF EXISTS 로 idempotent).
        _log(f"Phase 2 — 002_pii.sql 적용 중 (readonly pw 길이={len(readonly_pw)}).")
        _apply_pii_sql(conn, readonly_pw)
        _log("Phase 2 done.")

        # Phase 3 — seed 데이터
        existing = _count_rows(conn, "policies")
        if existing > 0:
            _log(f"Phase 3 skip — policies {existing:,}행 이미 로드됨.")
        else:
            _log("Phase 3 — 합성 데이터 생성·적재 중 (최대 3분 소요).")
            # 임포트는 이 시점에서 (env 변수 체크 후)
            from data.seed.load import main as seed_main  # noqa: PLC0415
            rc = seed_main()
            if rc != 0:
                _log(f"seed_main 실패 (rc={rc}).")
                return rc
            _log("Phase 3 done.")

    _log("Bootstrap 완료.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
