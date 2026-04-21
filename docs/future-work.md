# SURI — Future Work

> 9일 PoC 스코프 외로 의도적 제외한 항목. 각 항목은 "왜 제외했는지" + "언제/어떻게 추가할지" 기록.

## 1. `policy_coverages` 테이블 (특약·담보)

- **제외 이유**: 9일 스프린트 스코프. 핵심 차별화(PII 거버넌스·Agent 오케스트레이션·거버넌스 로그)와 직결되지 않음.
- **OIDF 표준 참조**: 정식 4계층 구조(Party → Contract → Coverage → Product)의 3계층. PoC는 Party → Contract → Product의 3계층으로 축소.
- **추가 시나리오**: 특약별 해지율·청구율 드릴다운 분석. 예) "실손 특약이 있는 종신보험 해지율이 특약 없는 종신보험 대비 X% 높음" 같은 패턴.
- **구현 시점**: Production 전환 단계 또는 시나리오 확장 단계.

## 2. IFRS 17 코호트·그룹 컬럼

- **제외 이유**: 2023년 시행된 보험 회계 신기준. 정식 구현은 CSM 상각·측정 모델(GMM/PAA/VFA) 설계를 요구하므로 9일 PoC 범위 초과. 피상적 구현 시 면접 팔로업에서 깊이 없음이 드러날 리스크.
- **추가할 컬럼**:
  - `policies.cohort_year` — 연간 코호트 (계약 발행 연도)
  - `policies.ifrs17_group_id` — 유리/불리/중립 그룹
  - `products.measurement_model` — GMM / PAA / VFA
  - `monthly_ape.csm_release_rate` — CSM 상각률
- **확장 시나리오**: "2023 코호트 vs 2024 코호트 해지율 비교", "VFA 변액보험의 CSM 런오프 예측"
- **구현 시점**: 실무 적용 단계에서 IFRS 17 전문가 협업으로 진행.

## 3. Airflow DAG 확장

- **제외 이유 (조건부)**: D-5 체크포인트 미달 시 포기 원칙. 현재 계획은 `daily_product_kpi_dag` 1개만 유지.
- **확장 방향**: CSM 일일 상각, 코호트별 유지율 일일 집계, 이상 패턴 자동 탐지 알림.

## 4. 관측 고도화 (LangSmith / Phoenix)

- **제외 이유**: JSONL + Streamlit 탭으로 JD "실행 로그 기반 최적화" 키워드 충분 커버. 9일 내 설정·학습 비용 대비 이득 작음.
- **확장 방향**: LangSmith 통합 (LangChain 자동 지원) 또는 Phoenix 관측 대시보드.

## 5. RAG 레이어 (스키마 RAG)

- **제외 이유 (조건부)**: D-5 체크포인트 이후 여유 판단. JD에 RAG 키워드 명시되어 있어 추가 시 JD 매칭률 12/12 완성.
- **구현 방향**: 테이블·컬럼 메타데이터를 벡터 DB(Chroma 로컬)에 임베딩. Executor가 SQL 쓰기 전 관련 스키마를 RAG로 조회 → "Dynamic Few-Shot Schema Retrieval" 패턴.

## 6. 멀티모델 최적화 (Phase 2)

- **제외 이유**: ADR-001 Phase 1(Sonnet 단일) 확정. 측정 후 Phase 2에서 Haiku 분리 실험 예정.
- **확장 방향**: Planner/Critic을 Haiku로, Executor만 Sonnet 유지. 비용·지연 실측 후 적용.

## 7. OpenAI/Gemini 모델 비교 (Phase 3)

- **제외 이유**: ADR-001 Phase 3로 조건부 예정. Phase 1 완료 후 여유 시.
- **확장 방향**: 골든셋 15개를 GPT-4, Gemini 2.5로 돌려 EA 비교. 모델별 강점 분석.
