-- ============================================================
-- SURI Schema — 002: PII Governance + Analytical Views
-- ============================================================
-- 이 파일은 001 이후 실행됨 (파일명 알파벳 순)
-- 핵심 설계:
--  1. customers_safe  — PII 컬럼 차단한 고객 VIEW
--  2. premium_payments_v — 회차 계산 VIEW (일관성 보장)
--  3. monthly_ape      — 월별 APE 집계 VIEW
--  4. suri_readonly ROLE — MCP 서버 전용 read-only 계정
-- ============================================================

-- ============================================================
-- VIEW 1: customers_safe
-- PII 차단 + 분석용 파생 컬럼 제공
-- ============================================================
CREATE OR REPLACE VIEW customers_safe AS
SELECT
  customer_id,
  gender,
  -- 출생일 직접 노출 X, 연령만
  EXTRACT(YEAR FROM AGE(birth_date))::INTEGER AS age,
  -- 연령대 카테고리
  CASE
    WHEN EXTRACT(YEAR FROM AGE(birth_date)) < 20 THEN '10대'
    WHEN EXTRACT(YEAR FROM AGE(birth_date)) < 30 THEN '20대'
    WHEN EXTRACT(YEAR FROM AGE(birth_date)) < 40 THEN '30대'
    WHEN EXTRACT(YEAR FROM AGE(birth_date)) < 50 THEN '40대'
    WHEN EXTRACT(YEAR FROM AGE(birth_date)) < 60 THEN '50대'
    WHEN EXTRACT(YEAR FROM AGE(birth_date)) < 70 THEN '60대'
    ELSE '70대+'
  END AS age_group,
  EXTRACT(YEAR FROM joined_at)::INTEGER AS joined_year,
  joined_at
FROM customers;

COMMENT ON VIEW customers_safe IS
'PII-safe customer view. Excludes: full_name, resident_number, phone, address, email, birth_date raw. suri_readonly ROLE가 접근하는 유일한 customer 엔드포인트.';

-- ============================================================
-- VIEW 2: premium_payments_v
-- 회차(payment_month_seq) 동적 계산 — 데이터 무결성 보장
-- ============================================================
CREATE OR REPLACE VIEW premium_payments_v AS
SELECT
  pp.payment_id,
  pp.policy_id,
  pp.payment_date,
  pp.amount,
  pp.status,
  -- 납입 회차 (1-based)
  (EXTRACT(YEAR  FROM pp.payment_date) - EXTRACT(YEAR  FROM p.issue_date))::INTEGER * 12 +
  (EXTRACT(MONTH FROM pp.payment_date) - EXTRACT(MONTH FROM p.issue_date))::INTEGER + 1
    AS payment_month_seq,
  p.issue_date AS policy_issue_date
FROM premium_payments pp
JOIN policies p USING (policy_id);

COMMENT ON VIEW premium_payments_v IS
'Payment history with computed month_seq. 13/25회차 유지율 쿼리용. 회차는 저장 X, VIEW에서 계산하여 데이터 오염 방지.';

-- ============================================================
-- VIEW 3: monthly_ape
-- 월별 × 상품군 × 채널 APE 집계
-- APE = 연납 보험료 환산 금액 (월납×12 + 일시납×10%)
-- ============================================================
CREATE OR REPLACE VIEW monthly_ape AS
SELECT
  TO_CHAR(p.issue_date, 'YYYY-MM')         AS year_month,
  p.cohort_year,
  pr.product_type,
  pr.product_group,
  a.channel_type,
  COUNT(p.policy_id)                        AS new_contracts,
  SUM(
    CASE
      WHEN p.payment_frequency = 'monthly' THEN COALESCE(p.annual_premium, 0)
      WHEN p.payment_frequency = 'annual'  THEN COALESCE(p.annual_premium, 0)
      WHEN p.payment_frequency = 'single'  THEN COALESCE(p.annual_premium, 0) / 10
      ELSE 0
    END
  )                                         AS ape_amount
FROM policies p
JOIN products pr ON p.product_id = pr.product_id
LEFT JOIN agents a ON p.agent_id = a.agent_id
GROUP BY TO_CHAR(p.issue_date, 'YYYY-MM'), p.cohort_year, pr.product_type, pr.product_group, a.channel_type;

COMMENT ON VIEW monthly_ape IS
'Monthly APE aggregation by product_type × product_group × channel_type. APE 공식: 월납/연납 = annual_premium, 일시납 = annual_premium/10.';

-- ============================================================
-- ROLE: suri_readonly
-- MCP 서버가 쓸 읽기 전용 계정
-- ============================================================

-- 기존 ROLE이 있으면 제거 (멱등성 보장)
DROP ROLE IF EXISTS suri_readonly;

-- ROLE 생성 + 로그인 허용
CREATE ROLE suri_readonly WITH LOGIN PASSWORD 'readonly_pass';

-- 기본적으로 모든 테이블 접근 차단
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM suri_readonly;
REVOKE ALL ON SCHEMA public FROM suri_readonly;

-- 스키마 접근 + SELECT 기본 권한
GRANT USAGE ON SCHEMA public TO suri_readonly;

-- 허용 테이블 (customers 제외)
GRANT SELECT ON products          TO suri_readonly;
GRANT SELECT ON agents            TO suri_readonly;
GRANT SELECT ON policies          TO suri_readonly;
GRANT SELECT ON premium_payments  TO suri_readonly;
GRANT SELECT ON claims            TO suri_readonly;

-- 허용 VIEW
GRANT SELECT ON customers_safe        TO suri_readonly;
GRANT SELECT ON premium_payments_v    TO suri_readonly;
GRANT SELECT ON monthly_ape           TO suri_readonly;

-- 중요: customers 원본 테이블 접근 명시적으로 차단
REVOKE ALL ON customers FROM suri_readonly;

-- 추후 새로 생길 테이블에는 기본 권한 부여 안 함 (명시적 GRANT 필요)
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM suri_readonly;

-- ============================================================
-- 권한 확인 쿼리 (주석 — psql에서 테스트용)
-- ============================================================
-- SELECT * FROM information_schema.role_table_grants 
--   WHERE grantee = 'suri_readonly' ORDER BY table_name;
