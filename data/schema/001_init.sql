-- ============================================================
-- SURI Schema — 001: Core Tables (v3.2.2)
-- ============================================================
-- 변경 이력 (vs v3.2.1):
--  1. SERIAL → GENERATED ALWAYS AS IDENTITY (SQL 표준)
--  2. payment_month_seq 컬럼 제거 (VIEW로 계산, 002에서 정의)
--  3. CHECK 제약 유지 (스키마 진화 유연성)
-- ============================================================

-- 1. products — 상품 마스터
CREATE TABLE products (
  product_id      INTEGER      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  product_code    VARCHAR(20)  UNIQUE NOT NULL,
  product_name    VARCHAR(100) NOT NULL,
  product_type    VARCHAR(20)  NOT NULL CHECK (product_type IN ('보장성', '저축성', '변액')),
  product_group   VARCHAR(20)  NOT NULL CHECK (product_group IN ('건강', '종신', '연금', '저축', '정기')),
  base_premium    INTEGER,
  launch_date     DATE,
  created_at      TIMESTAMPTZ  DEFAULT NOW()
);

-- 2. customers — PII 포함 원본 (MCP 차단 대상)
CREATE TABLE customers (
  customer_id      INTEGER      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  full_name        VARCHAR(50)  NOT NULL,           -- PII
  resident_number  VARCHAR(20),                      -- PII (주민번호 해시)
  birth_date       DATE         NOT NULL,
  gender           CHAR(1)      NOT NULL CHECK (gender IN ('M', 'F')),
  phone            VARCHAR(20),                      -- PII
  address          VARCHAR(200),                     -- PII
  email            VARCHAR(100),                     -- PII
  joined_at        DATE         NOT NULL,
  created_at       TIMESTAMPTZ  DEFAULT NOW()
);

-- 3. agents — 설계사 + 채널 정보
CREATE TABLE agents (
  agent_id      INTEGER      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  agent_code    VARCHAR(20)  UNIQUE NOT NULL,
  agent_name    VARCHAR(50)  NOT NULL,
  channel_type  VARCHAR(20)  NOT NULL CHECK (channel_type IN ('전속', '방카', 'TM', 'CM', 'GA')),
  agency_name   VARCHAR(100),
  hire_date     DATE,
  active        BOOLEAN      DEFAULT TRUE
);

-- 4. policies — 계약 (+ IFRS 17 확장 포인트)
CREATE TABLE policies (
  policy_id          INTEGER      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  policy_number      VARCHAR(30)  UNIQUE NOT NULL,
  customer_id        INTEGER      NOT NULL REFERENCES customers(customer_id),
  product_id         INTEGER      NOT NULL REFERENCES products(product_id),
  agent_id           INTEGER      REFERENCES agents(agent_id),
  issue_date         DATE         NOT NULL,
  maturity_date      DATE,
  status             VARCHAR(20)  NOT NULL CHECK (status IN ('active', 'lapsed', 'terminated', 'matured')),
  monthly_premium    INTEGER,
  annual_premium     INTEGER,                         -- APE 계산 원본
  sum_insured        INTEGER,
  payment_frequency  VARCHAR(10)  CHECK (payment_frequency IN ('monthly', 'annual', 'single')),
  -- IFRS 17 확장 포인트 (Future Work)
  cohort_year        INTEGER,                         -- 자동 채움 (시드 생성 시 issue_date에서 추출)
  ifrs17_group_id    VARCHAR(20),                     -- NULL: Future Work
  measurement_model  VARCHAR(10),                     -- NULL: Future Work (GMM/PAA/VFA)
  created_at         TIMESTAMPTZ  DEFAULT NOW()
);

-- 5. premium_payments — 보험료 납입 이력 (순수 이벤트 테이블)
-- 회차(payment_month_seq)는 002의 VIEW에서 계산
CREATE TABLE premium_payments (
  payment_id    INTEGER      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  policy_id     INTEGER      NOT NULL REFERENCES policies(policy_id),
  payment_date  DATE         NOT NULL,
  amount        INTEGER      NOT NULL,
  status        VARCHAR(20)  DEFAULT 'paid' CHECK (status IN ('paid', 'overdue', 'missed'))
);

-- 6. claims — 보험금 청구
CREATE TABLE claims (
  claim_id      INTEGER      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  policy_id     INTEGER      NOT NULL REFERENCES policies(policy_id),
  claim_date    DATE         NOT NULL,
  paid_date     DATE,
  claim_type    VARCHAR(50),                           -- 사망/질병/사고/만기 등
  amount        INTEGER,
  status        VARCHAR(20)  CHECK (status IN ('pending', 'approved', 'rejected', 'paid'))
);

-- ============================================================
-- 인덱스 — 자주 쓰는 JOIN·WHERE 대상
-- ============================================================
CREATE INDEX idx_policies_customer     ON policies(customer_id);
CREATE INDEX idx_policies_product      ON policies(product_id);
CREATE INDEX idx_policies_agent        ON policies(agent_id);
CREATE INDEX idx_policies_cohort       ON policies(cohort_year);
CREATE INDEX idx_policies_status       ON policies(status);
CREATE INDEX idx_policies_issue_date   ON policies(issue_date);
CREATE INDEX idx_premium_policy_date   ON premium_payments(policy_id, payment_date);
CREATE INDEX idx_claims_policy         ON claims(policy_id);

-- ============================================================
-- 테이블/컬럼 주석 (psql \d+ 로 확인 가능)
-- ============================================================
COMMENT ON TABLE  customers                  IS 'PII 포함 원본 — MCP 차단 대상. customers_safe VIEW 통해서만 접근';
COMMENT ON TABLE  premium_payments           IS '납입 이벤트 원본. 회차는 premium_payments_v VIEW에서 계산';
COMMENT ON COLUMN policies.cohort_year       IS 'IFRS 17 연간 코호트 (issue_date 연도)';
COMMENT ON COLUMN policies.ifrs17_group_id   IS 'IFRS 17 그룹 (유리/불리/중립) — Future Work';
COMMENT ON COLUMN policies.measurement_model IS 'IFRS 17 측정 모델 (GMM/PAA/VFA) — Future Work';
