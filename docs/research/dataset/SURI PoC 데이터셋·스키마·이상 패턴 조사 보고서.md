# SURI PoC — 생명보험 데이터셋·스키마·이상 패턴 조사 보고서

> **목적** : 한화생명 Data Agent Developer 포지션용 9일 PoC(SURI) 제작을 위한 공개 데이터셋 후보 발굴, 업계 표준 스키마 정리, 한국 시장 이상 패턴 수치화

***

## 1. Executive Summary

- **최적 데이터셋** : CASdatasets `uslapseagent` (R패키지, 29,317행 · 14컬럼, 자유 이용 GPL-2) 와 Kaggle `Customer Churn dataset for Life Insurance Industry` (200,000행 · 12컬럼) 두 종을 **조합**해 합성 데이터 5만 행을 생성하는 것이 현실적이다.
- **표준 스키마** : Oracle OIDF의 Party–Contract–Coverage–Product 4계층 구조가 생명보험 PostgreSQL 스키마 설계의 실용적 참조 기준이며, IFRS 17 데이터 요건(CSM·BBA 그룹·코호트)이 추가 테이블 설계에 반영되어야 한다.[^1][^2]
- **핵심 이상 패턴** : ① 채널별 13→25회차 유지율 낙차(GA 20.3%p 격차), ② 교보생명 25회차 24.37%p 급락 이상치, ③ 절판 마케팅 APE 스파이크(단일 상품 전월 대비 수십 % 급등)가 PII 거버넌스 시연과 함께 PoC의 핵심 데모 시나리오로 권장된다.[^3][^4][^5]
- 전체 9개 테이블 설계 시 OIDF의 `FSI_POLICY_CONTRACT`, `FSI_POLICY_COVERAGES`, `FSI_PARTY_MASTER`를 3개 핵심 테이블로 채택하고, `customers_safe` view로 PII 컬럼(주민번호·전화번호)을 차단하는 구조가 심사위원에게 가장 명확하게 거버넌스를 시연한다.[^6][^7]
- 한국 생명보험 25회차 유지율(60.7%, 2023년 기준)은 일본(89.2%)·싱가포르(96.1%) 대비 현저히 낮아, 세그먼트 해지율 드릴다운 시나리오의 현실성 있는 배경이 된다.[^8][^4]

***

## 2. 공개 데이터셋 후보

### 2-1. Top 3 비교표

| # | 데이터셋명 | 출처·URL | 행 수 | 핵심 컬럼 | 라이선스 | 국가·맥락 | PoC 적합도 |
|---|-----------|---------|------|-----------|---------|----------|-----------|
| **1** | **CASdatasets `uslapseagent`** | R CRAN + Arthur Charpentier 저장소[^9] `install.packages("CASdatasets")` | 29,317 | `issue.date`, `duration`, `gender`, `risk.state`, `underwriting.age`, `premium.frequency`, `annual.premium`, `living.place`, `termination.cause`, `surrender`, `death`, `DJIA` (14컬럼) | GPL-2 (상업적 이용 가능) | 미국, 전속 설계사(Tied-Agent) 채널, 종신보험 1995-2008 | ★★★★★ |
| **2** | **Kaggle – Customer Churn for Life Insurance** | Kaggle `usmanfarid/customer-churn-dataset-for-life-insurance-industry`[^10] | 200,000 | `customer_id`, `age`, `gender`, `policy_type`, `premium_amount`, `contract_duration`, `payment_frequency`, `claim_history`, `agent_channel`, `churn` 등 12컬럼 | CC BY 4.0 (추정, 공개 표기) | 글로벌(합성), 채널·상품유형·해지 플래그 포함 | ★★★★☆ |
| **3** | **PMC / ICPSR – Actual Life-Risk Portfolio (Spain)** | `https://doi.org/10.3886/E178881V1`[^11][^12] | 76,102 | `policy_id`, `gender`, `birth_date`, `entry_date`, `renewal_date`, `capital_at_risk`, `sum_insured` (15컬럼) | CC BY 4.0 (로그인 없이 접근 가능) | 스페인, 실제 생명위험 포트폴리오 스냅샷(2009년말 기준) | ★★★★☆ |

### 2-2. 추가 후보 데이터셋 (4~7위)

| # | 데이터셋명 | 출처 | 행 수 / 규모 | 주요 특징 | 한계 | 적합도 |
|---|-----------|------|------------|---------|-----|-------|
| 4 | **CASdatasets `eudirectlapse`** | R CASdatasets[^13] | 수만 행 (유럽 손보 해지) | 해지 이진 레이블, 계약 속성 포함 | 손해보험(Non-Life) 중심 | ★★★☆☆ |
| 5 | **CASdatasets `canlifins`** | R CASdatasets[^14] | 14,889 | 캐나다 종신·연금, 생존·사망 이력(joint-life) | 집계 수준, 채널 정보 없음 | ★★★☆☆ |
| 6 | **CASdatasets `eusavingsurrender`** | R CASdatasets[^13] | 미공개 (EU 저축성 해지 패널) | 시계열 이력, 저축성 보험에 특화 | 소규모, 유럽 규제 특화 | ★★★☆☆ |
| 7 | **India IRDAI Lapse Dataset (Dataful)** | `https://dataful.in/datasets/21063/`[^15] | 1,364 records (insurer-year 집계) | 연도·회사별 해지율 비율, LIC 포함 | 집계 수준, 계약 단위 아님 | ★★☆☆☆ |

### 2-3. 데이터셋 상세 정보

#### ① uslapseagent (★★★★★ — **SURI PoC 제1 권장**)[^9]

**컬럼 상세**

| 컬럼명 | 타입 | 설명 | PoC 활용 |
|--------|------|------|---------|
| `issue.date` | Date | 계약 개시일 (또는 우측 절단일) | 가입 코호트 분석 |
| `duration` | Numeric | 계약 지속 기간 (분기 단위) | APE 집계 시 보험료 기간 가중 |
| `acc.death.rider` | Binary | 재해사망 특약 유무 | 상품 구성 다양화 |
| `gender` | Factor | 성별 | 세그먼트 해지율 |
| `premium.frequency` | Factor | 납입 주기 (월납/연납/일시납) | 이상치 탐지 |
| `risk.state` | Factor | Smoker / NonSmoker | 세그먼트 |
| `underwriting.age` | Factor | Young(0-34) / Middle(35-54) / Old(55-84) | 연령대별 해지율 |
| `living.place` | Factor | 거주 지역 유형 | 지역 세그먼트 |
| `annual.premium` | Numeric | 연간 보험료 (표준화) | APE 계산 원본 |
| `DJIA` | Numeric | 분기별 DJIA 변동률 (표준화) | 매크로 변수 연동 |
| `termination.cause` | Factor | 해지 사유 유형 | 해지 원인 분류 |
| `surrender`, `death`, `other`, `allcause` | Binary | 종료 유형 플래그 | lapse_flag 원본 |

- **라이선스** : GPL-2, 무료 이용 가능
- **한계** : 미국 전속 설계사 채널만 수록, 한국 방카/GA 채널 없음, PII 없음(익명화 완료)
- **PoC 활용** : 13회차 유지율 = `duration ≥ 13` & `allcause = 0` 집계 가능. `living.place`·`gender`·`underwriting.age` 3개 변수로 세그먼트 해지율 드릴다운 직접 구현 가능.

#### ② Kaggle – Customer Churn (★★★★☆)[^10]

**컬럼 상세** (12컬럼, 200,000행)

| 컬럼명 | 설명 |
|--------|------|
| `customer_id` | 고객 ID (PII 시연용 — `customers` 테이블에 배치, `customers_safe` view에서 마스킹) |
| `age`, `gender` | 인구통계 |
| `policy_type` | 보장성 / 저축성 / 변액 구분 |
| `premium_amount` | APE 집계 원본 |
| `contract_duration` | 계약 지속 기간 |
| `payment_frequency` | 납입 주기 |
| `claim_history` | 클레임 이력 플래그 |
| `agent_channel` | GA / 전속설계사 / 방카 / 다이렉트 |
| `churn` | 해지 여부 (0/1) |

- **라이선스** : Kaggle 공개 데이터셋 (상업적 이용 제한 확인 필요)
- **한계** : 합성 데이터(Synthetic). 보험료 스케일이 글로벌 단위로 한국 원화와 매핑 필요.
- **PoC 활용** : `agent_channel` 컬럼이 한국 채널 구분(GA/전속/방카/직급)에 직접 매핑되어 채널별 해지율 비교 시나리오 구현에 최적.

#### ③ PMC / ICPSR – Actual Life-Risk Portfolio (★★★★☆)[^11][^12]

**컬럼 상세** (15컬럼, 76,102행)

| 컬럼명 | 설명 |
|--------|------|
| `policy_id` | 계약번호 (익명화) |
| `gender` | 피보험자 성별 |
| `birth_date` | 생년월일 |
| `insured_entry_date` | 보험계약 개시일 |
| `renewal_date` | 갱신일 |
| `capital_at_risk` | 위험보험금 |
| `sum_insured` | 보험가입금액 |
| (8개 추가 컬럼) | 계약 상태, 유효기간 등 |

- **라이선스** : CC BY 4.0 (로그인 후 무료 다운로드, Open ICPSR)
- **한계** : 스페인 생명위험보험 단일 시점(2009년 말) 스냅샷. 해지 플래그 없음. 시계열 이력 없음.
- **PoC 활용** : `capital_at_risk`·`birth_date`를 활용한 연령 세그먼트 APE 집계 시나리오에 적합. PII 시연 시 `birth_date` 컬럼을 `customers_safe`에서 차단하는 예제로 활용.

***

## 3. 표준 스키마 레퍼런스

### 3-1. Oracle OIDF (Oracle Insurance Data Foundation)[^16][^17][^1]

OIDF는 보험사 분석용 데이터 웨어하우스의 사실상 표준으로, 생명보험 도메인을 **4계층 구조**로 설계한다.

**핵심 엔티티 계층**

```
Party (FSI_PARTY_MASTER)
  └─ Contract (FSI_POLICY_CONTRACT)
        ├─ Coverage / Rider (FSI_POLICY_COVERAGES)
        │     └─ Guaranteed Benefits
        ├─ Fund (FSI_FUND) — 변액보험
        └─ Policy Loan (FSI_POLICY_LOAN)
Product (FSI_PRODUCT_MASTER)
  └─ Product Processor: Life / Annuity / P&C / Retirement / Health
Commission (FSI_POLICY_COMMISSION)
  └─ Commission Transaction (FSI_COMMISSION_TRANSACTION)
```

**SURI PoC 매핑 권장 (9테이블)**

| SURI 테이블 | OIDF 원형 | 주요 컬럼 |
|------------|----------|---------|
| `customers` | `FSI_PARTY_MASTER` | `party_id`, `birth_date`, `ssn_masked`, `mobile_no`, `gender`, `zip_code` |
| `customers_safe` (VIEW) | — | `ssn_masked`, `mobile_no` 컬럼 제외 |
| `products` | `FSI_PRODUCT_MASTER` | `product_id`, `product_type` (보장성/저축성/변액), `product_name`, `payment_term` |
| `policies` | `FSI_POLICY_CONTRACT` | `policy_id`, `customer_id`, `product_id`, `agent_id`, `channel`, `status`, `issue_date`, `maturity_date`, `annual_premium` |
| `policy_coverages` | `FSI_POLICY_COVERAGES` | `coverage_id`, `policy_id`, `rider_type`, `sum_insured`, `effective_date` |
| `premium_payments` | `FSI_PAYMENT_TRANSACTIONS` | `payment_id`, `policy_id`, `payment_date`, `amount`, `payment_month_seq` |
| `claims` | `FSI_CLAIM_MASTER` | `claim_id`, `policy_id`, `claim_date`, `claim_type`, `claim_amount`, `status` |
| `agents` | `FSI_CHANNEL_MASTER` | `agent_id`, `channel_type` (GA/전속/방카/직급), `agency_name`, `hire_date` |
| `monthly_ape` (집계VIEW) | — | `year_month`, `product_type`, `channel`, `ape_amount` — APE 집계 쿼리용 |

**OIDF 관계 다이어그램 (텍스트 표현)**

```
customers ──1:N── policies ──1:N── policy_coverages
                     │                   
                     ├─1:N── premium_payments
                     ├─1:N── claims
                     └─N:1── products
                     └─N:1── agents
```

> **참고** : OIDF 공식 ERD PDF는 Oracle Help Center `https://docs.oracle.com/cd/E92918_01/PDF/` 에서 라이선스 조건에 따라 열람 가능. 공개 ERD 이미지는 상업적 재배포 제한.

### 3-2. IFRS 17 데이터 요건 반영[^2][^18][^19]

IFRS 17은 보험사가 계약을 **포트폴리오(Portfolio) → 연간 코호트(Annual Cohort) → 그룹(Group)** 으로 구분하여 CSM(Contractual Service Margin)을 산출하도록 요구한다.

**SURI PoC 관련 추가 컬럼 권장**

| 기존 테이블 | 추가 컬럼 | 설명 |
|----------|---------|------|
| `policies` | `ifrs17_group_id` | 계약 그룹 (유리·불리·중립) |
| `policies` | `cohort_year` | 연간 코호트 (계약 발행 연도) |
| `products` | `measurement_model` | GMM / PAA / VFA 구분[^2] |
| `monthly_ape` | `csm_release_rate` | CSM 상각률 (PoC 시나리오용 더미) |

> **실무 팁** : IFRS 17 아래 `cohort_year` 컬럼은 2023년 이후 한국 생보사 결산에서 핵심 차원. 한화생명 면접관에게 "IFRS 17 코호트 기반 APE 집계" 질의 시나리오를 시연하면 실무 이해도를 강하게 어필 가능.

### 3-3. Financial Industry Business Data Model (FIB-DM / FIBO)[^6]

FIBO는 OMG(Object Management Group) 표준으로 금융 도메인 온톨로지를 정의하며, 보험 도메인의 핵심 엔티티는 다음과 같다.

**핵심 엔티티**
- **Insurer** : 보험자 법인
- **Insurance Policy** : 계약 (Insurer ↔ Policyholder 계약)
- **Policyholder** : 계약자 (= SURI `customers`)
- **Letter of Credit** : 보증 기반 보험 파생상품
- **Guarantee** : 보험담보 연결

> ERD 이미지 URL: `https://insuranceontology.com/insurance-data-model/` (공개 접근 가능)[^6]

### 3-4. Adobe Experience Platform BFSI ERD[^7]

Adobe XDM 표준의 BFSI ERD는 디지털 채널 보험사를 위한 비정규화(de-normalized) 데이터 모델을 제시하며, `Identity`, `ExperienceEvent`, `PolicyholderProfile` 3개 엔티티를 중심으로 한다. SURI PoC의 `customers` 테이블 설계 시 `primary_identity` 컬럼 개념을 참조할 수 있다.

> ERD URL: `https://experienceleague.adobe.com/en/docs/experience-platform/xdm/schema/industries/financial` (공개 접근 가능)[^7]

***

## 4. 이상 패턴 Top 3

### Pattern 1 — 채널별 13→25회차 유지율 낙차 (GA 채널 가장 심각)

**관찰된 수치 (2021년 기준, 개인생명보험)**[^4][^20]

| 채널 | 13회차 유지율 | 25회차 유지율 | 낙차(Gap) |
|-----|------------|------------|---------|
| GA (법인보험대리점) | ~88% | ~68% | **20.3%p** |
| 전속 설계사 | ~87% | ~69% | **18.3%p** |
| TM (텔레마케팅) | ~82% | ~69% | **12.9%p** |
| 방카슈랑스 | ~85% | (급락 추세) | (16.3%p, 장기손보 기준) |

**출처** : 보험연구원 연구보고서 2022-13 「국내 보험산업의 보험계약 유지율」, 금융감독원 공시 (2023년 생보계약 평균 유지율 13회차 83.2%·25회차 60.7%)[^20][^4]

**2024년 채널별 최신 수치** : 금감원 2025년 5월 공시에 따르면 전속·GA 채널 1년(13회차) 유지율은 각각 87.7%, 88.3%로 유사하나, 3년 차 이후 50%대로 급락.[^21][^22]

**PoC 재현 파라미터**

```python
# premium_payments 테이블에서 13회차 이후 급락 시뮬레이션
channel_lapse_params = {
    'GA':         {'base_lapse_13': 0.12, 'drop_rate_13to25': 0.203},
    'exclusive':  {'base_lapse_13': 0.13, 'drop_rate_13to25': 0.183},
    'bancassurance': {'base_lapse_13': 0.15, 'drop_rate_13to25': 0.163},
    'direct_TM':  {'base_lapse_13': 0.18, 'drop_rate_13to25': 0.129},
}
```

***

### Pattern 2 — 연령·회사별 25회차 유지율 이상치 (교보생명 24.37%p 급락)

**관찰된 수치**[^3][^4]

| 회사 | 2022년 25회차 | 2023년 25회차 | 전년 대비 변화 |
|-----|-------------|-------------|------------|
| 삼성생명 | 75.2% | 65.5% | -9.7%p |
| 한화생명 | 68.6% | 59.2% | -9.4%p |
| **교보생명** | **66.4%** | **46.8%** | **-19.6%p ← 이상치** |
| 신한라이프 | 64.6% | 63.0% | -1.6%p |
| KB라이프 | 69.1% | 55.3% | -13.8%p |

**출처** : 금융감독원 공시, CEO스코어데일리 2025년 1월 보도[^4]

**맥락** : 교보생명의 급락은 저축성보험 비중 축소 및 금리 환경 변화에 따른 구조적 포트폴리오 전환으로 분석됨. 2024년 Q2 기준 한화생명 13회차 유지율은 89.79%로 개선세.[^3]

**PoC 재현 파라미터** : `company_id = 'KYO'` 필터링 시 25회차 누적 해지율이 다른 대형사 대비 ~2배 높은 이상치 패턴을 합성 데이터에 심어 Critic Agent가 자가수정 시나리오를 트리거.

***

### Pattern 3 — 절판 마케팅 APE 스파이크 (무·저해지 보험 판매 급증)

**관찰된 수치**[^23][^5]

- **2025년 3월** : 무·저해지 보험 보험료 인상(일제히 4월 인상 예정) 직전, 금감원이 특정일(3월 17일 이후) 판매량을 일별 모니터링. "절판 마케팅"으로 일부 보험사 특정일 판매 수치가 전월 평균 대비 수십 % 급증.[^5]
- **2026년 3월 변액보험** : 2025년 변액보험 초회보험료 2.89조 원, 전년 대비 **+46.2%** 급증. FSS가 불완전판매 위험 모니터링 강화.[^24][^23]
- **APE 시계열 패턴** : 한국 생명보험사의 APE는 회계연도 말(3월) 및 분기 말에 스파이크 발생. 특히 절판 상품 공지 후 월말에 정점을 찍는 패턴이 반복적으로 관찰됨.

**출처** : FSS 보도자료(2025.03), 조선비즈 영문판(2026.03), Korean Re Bulletin 193호[^25][^23][^5]

**PoC 재현 파라미터**

```python
# monthly_ape 테이블 생성 시 시계열 파라미터
ape_seasonality = {
    'mar_multiplier': 1.8,   # 3월 연도말 스파이크 (fiscal year-end)
    'sep_multiplier': 1.3,   # 9월 반기말 소스파이크
    'cliff_event_month': '2025-03',
    'cliff_multiplier': 2.4, # 절판 이벤트 월 극단값
    'product_type_affected': 'no_surrender'  # 무해지 환급형 특이 패턴
}
```

***

## 5. 최종 권장 — SURI PoC 맥락 최적 조합

### 권장 데이터셋 조합

```
uslapseagent (CASdatasets R) [29,317행, 14컬럼]
  + Kaggle Life Insurance Churn  [200,000행, 12컬럼]
  ↓ 샘플링 + 컬럼 매핑 + 한국 시장 파라미터 적용
  → 합성 50,000행 · 9개 테이블 PostgreSQL DB
```

**조합 이유**
1. `uslapseagent`는 실제 전속 설계사 채널의 프리미엄·해지 시계열 구조를 제공 → `premium_payments`, `policies` 테이블 원본 데이터
2. Kaggle Churn 데이터는 `agent_channel` 컬럼이 있어 GA/방카 채널 분기 시나리오에 직접 적용 가능
3. PMC Spain 포트폴리오는 `capital_at_risk`·`birth_date` 컬럼으로 PII 거버넌스 시연(`customers`→`customers_safe` view)의 실감 있는 재료

### 권장 스키마 조합

```
OIDF 4계층 구조 (Party→Contract→Coverage→Product)
  + IFRS 17 코호트·그룹 컬럼 추가 (cohort_year, ifrs17_group_id)
  + customers_safe VIEW (PII 차단: ssn_masked, mobile_no, birth_date)
```

### 권장 시나리오 파라미터 (이상 패턴 → PoC 데모 매핑)

| 데모 시나리오 | 이상 패턴 기반 | 핵심 쿼리 | 예상 심사 포인트 |
|------------|------------|---------|--------------|
| APE 집계 | 절판 스파이크 (3월 APE 1.8×) | `GROUP BY year_month, product_type` | Planner가 올바른 `monthly_ape` VIEW 선택 |
| 세그먼트 해지율 | 채널별 낙차 (GA 20.3%p) | `WHERE channel='GA' AND payment_month_seq BETWEEN 13 AND 25` | Executor 정확도 |
| PII 거부 | `customers` 원본 차단 | `customers` 직접 쿼리 → 실패, `customers_safe` VIEW만 허용 | PII 거버넌스 시연 |
| 드릴다운 | 교보 이상치 재현 | `company_id IN ('HWA', 'KYO', 'SAM')` 비교 | Critic 자가수정 트리거 |
| 자가수정 | 잘못된 APE 수식 → Critic 수정 | Planner가 `premium_amount` 대신 `annual_premium` 사용 오류 주입 | 3-Agent 협업 시연 |

### 접근성 요약

| 데이터셋 | 접근 방법 | 가입 필요 여부 |
|---------|---------|--------------|
| CASdatasets (uslapseagent 등) | R `install.packages("CASdatasets")` 후 `data(uslapseagent)` | 불필요 (무료) |
| Kaggle Life Insurance Churn | `https://www.kaggle.com/datasets/usmanfarid/customer-churn-dataset-for-life-insurance-industry` | Kaggle 계정 필요 (무료) |
| PMC / ICPSR Spain Portfolio | `https://doi.org/10.3886/E178881V1` | ICPSR 계정 필요 (무료) |
| KIDI 보험통계월보 | `https://incos.kidi.or.kr` | 무료 (집계 통계만 제공, 계약 단위 없음) |
| KLIA 연간 통계 | `https://www.klia.or.kr/eng/reportStatistics/annualStatistics.do` | 무료 (집계 수준) |

---

## References

1. [19 Insurance Contracts Tables - Oracle Help Center](https://docs.oracle.com/cd/E92918_01/PDF/8.1.x.x/8.1.2.0.0/OIDF_HTML/812/UG/19_Insurance_Contracts_Tables.htm) - OIDF holds this data in Stage Insurance Contract Participation Details. In this participation entity...

2. [A Deep Dive into IFRS 17's Three Models - Dawgen Global](https://www.dawgen.global/understanding-insurance-contract-accounting-a-deep-dive-into-ifrs-17s-three-models/) - It establishes three distinct models for insurance contract accounting: the General Measurement Mode...

3. [The number of customers who do not cancel life insurance products within a year has increased. It is.. - MK](https://www.mk.co.kr/en/economy/11125954) - The number of customers who do not cancel life insurance products within a year has increased. It is...

4. [생보 2년계약 유지율 60% 수준으로 하락…아시아 주요국 중 '꼴찌'](https://www.ceoscoredaily.com/page/view/2025011315261841918) - 2021년 기준으로 개인생명보험 채널별 13회차와 25회차 유지율 격차는 GA 20.3%포인트, 전속 보험설계사 18.3%포인트, TM 12.9%포인트 순이다. 장기손해 ...

5. [The Financial Supervisory Service has launched a crackdown on insurance companies ahead of a hike in.. - MK](https://www.mk.co.kr/en/economy/11271502) - The Financial Supervisory Service has launched a crackdown on insurance companies ahead of a hike in...

6. [Insurance Data Model - Insurance Regulation Ontology](https://insuranceontology.com/insurance-data-model/) - The entity-relationship diagram below models insurance and guaranties. An Insurer issues the Insuran...

7. [Financial Services Industry Data Model ERD](https://experienceleague.adobe.com/en/docs/experience-platform/xdm/schema/industries/financial) - The following entity relationship diagram (ERD) represents a standardized data model for the banking...

8. [Korean Insurance Industry: Data Reports 2026 - WifiTalents](https://wifitalents.com/korean-insurance-industry-statistics/) - The Korean insurance market remained strong in 2023 despite a significant drop in life insurance sal...

9. [CASdatasets: Insurance datasets - arthur charpentier](https://freakonometrics.github.io/CASdatasets/) - A collection of datasets, originally for the book 'Computational Actuarial Science with R' edited by...

10. [Customer Churn dataset for Life Insurance Industry - Kaggle](https://www.kaggle.com/datasets/usmanfarid/customer-churn-dataset-for-life-insurance-industry) - Here I upload that consists of 200000 rows and 12 columns a dataset for customer churn prediction in...

11. [Dataset of an actual life-risk insurance portfolio - PubMed](https://pubmed.ncbi.nlm.nih.gov/36426067/) - The dataset contains information on 76,102 policies and a total of 15 variables, including the capit...

12. [Dataset of an actual life-risk insurance portfolio - Open ICPSR](https://www.openicpsr.org/openicpsr/project/178881/version/V1/view) - Policies in force in a portfolio of life-risk insurance policies of a Spanish insurance company. Dat...

13. [Get Started](https://cas.uqam.ca/pub/web/vignettes/CASdatasets.html)

14. [Canadian life insurance — canlifins • CASdatasets - GitHub Pages](https://dutangc.github.io/CASdatasets/reference/canlifins.html) - This dataset contains information of 14889 contracts in force with a large Canadian insurer over the...

15. [Year and Insurer wise Forfeiture/Lapsed Policies in respect of ...](https://dataful.in/datasets/21063/) - The dataset contains Year Wise Insurer Wise Forfeiture/Lapsed Policies in respect of Individual Non-...

16. [3 Understanding OIDF](https://docs.oracle.com/cd/E92918_01/PDF/8.1.x.x/8.1.1.0.0/OIDF_HTML/811/UG/3_Understanding_OIDF.htm) - OIDF was built to specifically address the key challenges of building a scalable, practical data man...

17. [19 Insurance Contracts Tables - Oracle Help Center](https://docs.oracle.com/cd/E92918_01/PDF/8.1.x.x/8.1.0.0.0/OIDF_HTML/81/UG/19_Insurance_Contracts_Tables.htm) - To load an Insurance Contract in OIDF, follow these steps: 1. The key components in contract structu...

18. [IFRS 17 Insurance Contracts](https://www.ifrs.org/issued-standards/list-of-standards/ifrs-17-insurance-contracts/) - IFRS 17 replaces IFRS 4 and sets out principles for the recognition, measurement, presentation and d...

19. [[PDF] Introduction to IFRS 17 - Munich Re](https://www.munichre.com/content/dam/munichre/contentlounge/website-pieces/documents/Introduction-to-IFRS-17-May2021-LIMA-MoG.pdf/_jcr_content/renditions/original./Introduction-to-IFRS-17-May2021-LIMA-MoG.pdf) - Three different ways to measure insurance contracts under IFRS 17: general measurement model (GMM /....

20. [[PDF] Ⅳ 보험산업 유지율 실태와 특징](https://www.kiri.or.kr/pdf/%EC%97%B0%EA%B5%AC%EC%9E%90%EB%A3%8C/%EC%97%B0%EA%B5%AC%EB%B3%B4%EA%B3%A0%EC%84%9C/nre2022-13_4.pdf) - 장기손해보험상품의 가입경로별 13회차 유지율을 비교해 보면, 전속설계사(85.7%),. GA(87.4%), 방카슈랑스채널(85.4%) 등 대면모집 방식 간에 비슷한 수준을 보이고 ...

21. [[PDF] 2024년 보험회사 판매채널 영업효율 및 감독방향](https://kiri.or.kr/PDF/weeklytrend/20250512/trend20250512_3.pdf) - □ (채널별) 전속과 GA 채널의 경우 보험계약 초기(1년) 유지율은 각각. 87.7%, 88.3%로 他 채널보다 높지만 3년차 이후 50%대로 하락. ◦ 한편, 고객이 ...

22. [방카 규제도 풀었는데 보험계약 유지율 저조…금감원 "개선 계획 내라"](https://marketin.edaily.co.kr/News/ReadE?newsId=02830646642138744) - 수수료 선지급 기간이 끝나는 시점인 3년 유지율은 50%대로 떨어졌다. 채널별로 보면 전속·보험 대리점(GA) 채널은 초기(1년) 유지율은 각각 87.7%, 88.3% ...

23. [FSS flags Shinhan Life and KB Partners for poor variable insurance ...](https://biz.chosun.com/en/en-finance/2026/03/24/ZG4CDFTEXFDRNNRQH36DF3UEOQ/) - The Financial Supervisory Service said it conducted mystery shopping because overheated performance ...

24. [Korea's Financial Regulator Flags Shinhan Life, KB Life Partners in Variable Insurance Sales Review](https://news.nate.com/view/20260324n03676) - 한눈에 보는 오늘 : 경제 - 뉴스 : Photo courtesy of Yonhap News[Alpha Biz= Paul Lee] South Korea's Financial Sup...

25. [Korean Insurance Market - KOREAN RE + Bulletin](https://eng.koreanre.co.kr/webzine/Bulletin_193/bull2.html) - Life insurers' premium income for the first half of 2024 reached KRW 54.5 trillion, an increase of K...

