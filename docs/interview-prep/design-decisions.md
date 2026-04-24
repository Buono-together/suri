# SURI 설계 근거 카드

각 주요 결정에 대한 **근거 1~2줄 + 반론 대처 + 대안**.
면접 전 암기용. 모든 답변은 45초 이내 가능해야 함.

---

## 1. 전체 포지셔닝

### 1.1 왜 SURI?
- **결정**: 한화생명 Data Agent Developer 포지션 전용 PoC, 9일 타임박스
- **근거**: JD 분석 결과 Multi-Agent, MCP, 거버넌스 키워드 3개가 핵심
- **반론 대처**: "왜 한화생명만 겨냥?" → 공통 포트폴리오성도 있음. Agent 포지션 전반 재사용 가능 (6~12개월)

### 1.2 왜 "PII 거버넌스 시연"을 차별화로?
- **결정**: SURI의 핵심 축을 모델 성능이 아닌 "3층 방어 구조"로 설정
- **근거**: (1) 금융권의 진짜 Pain Point는 PII 통제 (2) Agent 성능은 모델 업그레이드로 자동 개선되지만 거버넌스는 설계 주도 (3) 9일 내 시연 가능한 차별점
- **반론 대처**: "Agent 성능은 안 중요한가?" → 중요하지만 그건 모델 성숙도에 좌우. 엔지니어의 가치는 **제약 조건 하에서의 설계**에 있음

---

## 2. 데이터 설계

### 2.1 왜 완전 합성 데이터 (옵션 C)?
- **결정**: Faker 기반 100% 합성, 실데이터 부분 혼용 안 함
- **근거**: 
  1. PII 거버넌스 시연을 위해 **실재하는 한국어 PII** 구조 필요 → 공개 데이터는 이미 익명화
  2. 한국 개인정보보호위원회 2024년 합성데이터 참조모델 → PIPA 적용 제외
  3. 9일 타임박스 → 관계형 정합성 맞추기 최적
- **반론 대처**: 
  - "현실성 떨어지지 않나?" → 이상 패턴(GA 유지율, 3월 스파이크)은 KIRI 수치 기반 의도적 주입
  - "Kaggle 데이터 쓰면 안 됐나?" → 그럼 PII 거버넌스 시연이 불가능. 이 PoC의 **핵심 서사가 무너짐**
- **4개 AI 교차검증 기록**: `docs/research/dataset/`

### 2.2 왜 채널 분포를 방카 50%로?
- **결정**: 방카 50 / 전속 20 / GA 20 / TM 7 / CM 3
- **근거**: KIRI 수입보험료 기준 한국 생보 실제 분포. Perplexity + Gemini 리서치 일치
- **반론 대처**: 
  - "한화생명은 자회사 GA가 최대 규모라던데?" → 맞음. 그래서 **baseline은 시장 평균**으로, 이상 패턴(유지율 낙차)은 **GA subset에 주입**해서 한화 맥락 반영
  - "GA 20%면 샘플 너무 적지 않나?" → 30,000 × 20% = 6,000건. 통계 유의성 충분

### 2.3 왜 `payment_month_seq`를 VIEW로 계산?
- **결정**: 실 컬럼 저장 X, `premium_payments_v` VIEW에서 동적 계산
- **근거**: 
  1. `issue_date` 수정 시 자동 반영
  2. 여러 INSERT 경로에서의 데이터 오염 리스크 차단
  3. 5만 행 규모에선 JOIN 비용 무시 가능
- **반론 대처**:
  - "성능 문제 없나?" → 없음. 필요 시 Materialized VIEW로 한 글자 전환
  - "왜 처음부터 이렇게 안 하고?" → 초기 제안은 역정규화 저장이었음. 역산 불가 리스크 검토 후 VIEW로 전환

### 2.4 왜 주민번호를 `RRN-XXXXXX`로?
- **결정**: 실제 포맷(`\d{6}-\d{7}`) 모사 대신 완전 더미 포맷
- **근거**: 금융권 사내 DLP가 정규식으로 탐지. 체크디짓 오류 있어도 탐지됨. 포맷 자체를 어긋나게 해야 안전
- **반론 대처**: "Faker 기본값이 더 자연스럽지 않나?" → DLP 오탐 방지 + "의도적 더미"라는 명시성이 감사 문서에 유리
- **출처**: ChatGPT 리서치 (DLP 실무 경험 반영)

### 2.5 왜 금액 컬럼을 BIGINT?
- **결정**: `monthly_premium`, `annual_premium`, `sum_insured`, `amount` 전부 BIGINT
- **근거**: 
  1. 실제 보험 시장에 수백억 계약 존재 (INTEGER 상한 ~21억 부족)
  2. 금융 도메인 원칙: "돈은 의심 없이 BIGINT"
  3. 4바이트 절약 vs 오버플로 리스크 → 후자가 훨씬 큼
- **반론 대처**: "처음부터 BIGINT였나?" → 아님. INTEGER 오버플로 발생 후 BIGINT 전환하며 VIEW drop-recreate 패턴도 경험

---

## 3. 스키마 설계

### 3.1 왜 IDENTITY 대신 SERIAL 먼저 썼다가 바꿨나?
- **결정**: 최종 `GENERATED ALWAYS AS IDENTITY` (PostgreSQL 10+ 표준)
- **근거**: 
  1. SQL 표준 준수 (ANSI)
  2. `GENERATED ALWAYS`로 명시 INSERT 차단 → 데이터 무결성 ↑
  3. 시퀀스 별도 GRANT 불필요
- **반론 대처**: "SERIAL이 더 간결한데?" → 가독성 이점은 3초. IDENTITY의 표준성·무결성 이점이 더 큼

### 3.2 왜 CHECK 제약 (ENUM 아님)?
- **결정**: `CHECK (product_type IN ('보장성', '저축성', '변액'))`
- **근거**: 스키마 진화 유연성. ENUM은 값 삭제·변경 시 트랜잭션 제약
- **반론 대처**: 
  - "값이 고정이면 ENUM이 더 낫지 않나?" → 맞음. 우리 경우도 IFRS 17 확장 시 값 추가 가능성이 있어 CHECK로 갔지만, 완전 고정 도메인이면 ENUM도 정당
  - 이건 **취향 영역**이라 인정하는 게 시니어 신호

### 3.3 왜 IFRS 17 컬럼을 NULL로 두었나?
- **결정**: `cohort_year`만 채우고, `ifrs17_group_id`, `measurement_model`은 NULL
- **근거**: Schema Forward Compatibility 패턴. 확장 지점을 스키마 레벨에서 선언, 로직은 Future Work
- **반론 대처**: "왜 미리 안 계산해?" → CSM 분류는 예상 이익률 계산 필요 → 9일 스코프 밖. 스키마만 준비하고 ALTER 없이 UPDATE로 채울 수 있게 설계

### 3.4 왜 복합 인덱스 `(policy_id, payment_date)`?
- **결정**: 단일 인덱스 대신 복합
- **근거**: 
  1. Leftmost Prefix 규칙 활용
  2. `policy_id` 선택도 높음 (30,000종) → 좌측에 배치
  3. 주요 쿼리 패턴: "특정 계약의 납입 이력 시간순"
- **반론 대처**: "`payment_month_seq`는 왜 인덱스에 없나?" → 계산 컬럼이라 VIEW에서 생성. 인덱스는 실 컬럼 `payment_date` 기반

---

## 4. PII 거버넌스

### 4.1 왜 3층 방어?
- **결정**: Application(Guard) + DB ROLE(suri_readonly) + Schema(VIEW) 3층
- **근거**: Defense in Depth. 한 층 뚫려도 다음 층이 백업. 각 층에 과도한 책임 금지
- **반론 대처**: "Guard만 잘 만들면 되지 않나?" → 안 됨. LLM은 예측 불가. 실수 가정해야 함. 또한 Guard 버그 생기면 DB가 막는 구조 필요
- **시연 포인트**: 데모 시 의도적으로 Guard 우회 시도 → DB ROLE이 `permission denied` → 3층 구조 증명

### 4.2 왜 `customers_safe` VIEW?
- **결정**: 원본 차단 + 분석용 파생 컬럼 제공 (age, age_group)
- **근거**: 단순 차단이 아닌 **Safe Facade** 패턴. Agent가 원본 테이블 쓸 동기 자체를 제거
- **반론 대처**: "VIEW가 오버헤드 아닌가?" → 없음. VIEW는 쿼리 재작성이라 런타임 비용 0. Materialized가 아님

### 4.3 왜 `SET TRANSACTION READ ONLY` 추가?
- **결정**: `suri_readonly` ROLE 이미 읽기 전용인데 세션 레벨에도 걸음
- **근거**: Belt-and-suspenders. ROLE 권한 실수로 GRANT INSERT 되더라도 세션이 막음. 다층 안전장치
- **반론 대처**: "중복 아닌가?" → 맞음. 의도적 중복. 금융권 감사 문서에서 "다층 통제" 설명 쉬움

### 4.4 왜 GA 이상 패턴을 Overlay (2단계)로?
- **결정**: baseline 생성 후 anomalies.py가 덧씌우기
- **근거**: 
  1. 정상 분포와 이상 패턴 코드 분리 → 디버깅·토글 용이
  2. config에서 강도 조절 가능 → 면접 시 실시간 시연
  3. "이상 패턴 없는 버전"과 비교 시연 가능
- **반론 대처**: "if-else로 한 번에 생성하면 안 되나?" → 스파게티 코드. 여러 패턴 겹치면 정합성 디버깅 불가능
- **4개 AI 교차검증**: 전부 Overlay 권장

---

## 5. MCP 설계

### 5.1 왜 공식 mcp SDK의 FastMCP (A2)?
- **결정**: `from mcp.server.fastmcp import FastMCP` (옵션 A2)
- **근거**: 
  1. **단일 의존성**: 금융권 OSS 심사 1건
  2. FastMCP 1.0이 2024년 공식 SDK 편입 → 생산성 + 공식성 동시 확보
  3. Anthropic 전담 유지 → MCP 스펙 변경 즉시 대응
- **반론 대처**: 
  - "PrefectHQ의 독립 fastmcp 2.x는?" → Proxy/Composition 등 고급 기능 있으나 MVP 범위에 불필요. 의존성 2건 추가 비용 > 효용
  - "저수준 `Server` 클래스는?" → Boilerplate 30줄/tool. 1~3개 tool 규모에선 생산성 낭비
- **ADR 문서**: `docs/adr/ADR-002-mcp-library.md`

### 5.2 왜 AST 기반 파싱 (sqlglot)?
- **결정**: 정규식 대신 `sqlglot.parse()` + `find_all(exp.Table)`
- **근거**: 정규식 대비 우회 방어 4가지
  1. 별칭 우회 (`customers c`)
  2. 스키마 접두사 (`public.customers`)
  3. CTE 중첩 (`WITH c AS (SELECT * FROM customers)`)
  4. 문자열 내부 식별자 오탐 방지
- **반론 대처**: "단순 쿼리면 정규식이 빠르지 않나?" → Agent가 만드는 쿼리는 예측 불가. 한 번 뚫리면 거버넌스 서사 전체 무너짐. 성능 차이는 ms 단위

### 5.3 왜 PostgreSQL dialect 지정?
- **결정**: `sqlglot.parse(query, dialect="postgres")`
- **근거**: PostgreSQL 고유 문법(`::` 캐스트, `RETURNING` 등) 파싱 지원. dialect 없으면 legitimate 쿼리도 파싱 실패 → False Positive 증가

### 5.4 왜 multi-statement 탐지?
- **결정**: `len(non_null) > 1` 체크
- **근거**: `SELECT 1; DROP TABLE customers` 같은 SQL Injection 차단
- **반론 대처**: "psycopg도 기본 multi-statement 허용 안 하지 않나?" → 맞음. 근데 Guard에서 먼저 막으면 **에러 메시지가 명확**. Agent가 자가 교정 쉬움

### 5.5 왜 에러를 JSON으로 return?
- **결정**: `raise` 대신 `return json.dumps({"error": ..., "type": ...})`
- **근거**: Agent가 **피드백 채널**로 받음. 에러 타입으로 재시도 전략 결정. "Guard 에러면 쿼리 수정, DB 에러면 다른 접근"
- **반론 대처**: "Exception이 표준 아닌가?" → MCP tool 응답은 구조화 데이터가 원칙. Agent LLM 입장에서 예외보다 명시적 에러 객체가 처리 쉬움

### 5.6 왜 suri_readonly 접속에 `max_rows` 제한?
- **결정**: 기본 100행 + `+1`로 truncation 감지
- **근거**: Agent context window 보호. 거대한 결과가 LLM 토큰 한계 초과 방지
- **반론 대처**: "100개면 부족하지 않나?" → 분석 질의는 보통 GROUP BY 집계라 수십 행. Raw 조회 필요 시 Agent가 LIMIT 붙여서 재시도

---

## 6. 개발 방법론

### 6.1 AI 도구 활용 방식
- **결정**: Claude Code + Claude 웹 채팅 병용, 역할 분리
  - Claude: 초안 구현, 라이브러리 탐색, 반복 코드 생성
  - 본인: 설계 판단, 검증, 의사결정, 도메인 지식 주입
- **근거**: 2026년 기준 시니어 엔지니어의 실제 워크플로. 구현은 위임, **판단은 직접**
- **반론 대처**: "본인이 직접 다 짰어야 하지 않나?" → 9일 타임박스에서 효율. 중요한 건 "설계 근거 설명 가능 여부"와 "의사결정 책임"

### 6.2 ADR (Architecture Decision Records) 왜?
- **결정**: ADR-001(스택), ADR-002(MCP 라이브러리), ADR-003(Agent Framework), ADR-004(Domain Glossary) 작성
- **근거**: 
  1. 6개월 후 내가 왜 그랬는지 알 수 있게
  2. 면접에서 결정 근거 화면 공유 가능
  3. 금융권의 "변경 이력 추적" 관행
- **포맷**: Context / Decision / Rationale / Consequences / Alternatives Considered

### 6.3 4개 AI 교차검증 패턴
- **결정**: 주요 결정마다 ChatGPT, Gemini, Claude, Perplexity에 리서치 요청
- **근거**: 단일 AI 편향 방지. 시각 차이로 놓친 옵션 발견 가능 (MCP A2 케이스, ADR-004 케이스)
- **반론 대처**: "시간 낭비 아닌가?" → 리서치는 3분, 잘못된 결정 수정은 몇 시간. ROI 압도적

---

## 7. 자주 나올 질문 모음

### Q: "프로젝트의 가장 큰 기술적 도전은?"
- 답: INTEGER → BIGINT 전환. VIEW 의존성 때문에 단순 ALTER 불가능. DROP VIEW → ALTER TABLE → CREATE VIEW를 트랜잭션으로 감싸는 패턴 적용. 금융 금액은 BIGINT 필수라는 교훈.

### Q: "포기한 기능은?"
- Vector DB 기반 full RAG. 도메인 용어가 50개 수준이라 vector retrieval의 recall 이점이 없었음. 대신 `get_domain_term` MCP tool로 deterministic glossary 구현 (ADR-004). Migration Path로 pgvector 확장 경로 명시.

### Q: "개선하고 싶은 부분은?"
1. `customer_id` UUID 해시화 (현재 순차 ID → 준-PII)
2. `load.py` 상대 임포트 정리 (현재 절대 임포트로 `-m` 실행에만 동작)
3. IFRS 17 로직 구현 (`ifrs17_group_id`, `measurement_model`)
4. `checks.py` pytest로 포팅

### Q: "다시 만들면?"
- Generated Column + Foreign Key 참조 검토 (PostgreSQL 12+ 지원 여부 확인 후)
- 처음부터 상대 임포트 사용
- `dateutil.relativedelta`로 날짜 산술 (Feb 29 문제 자동 처리)

---

## 8. 실측 케이스 — Resilience 증거

골든셋 v3.1에서 C4/Scene 2를 "자가교정"에서 "거버넌스 내재화"로 재분류한 후
(`docs/golden-set.md` v3 → v3.1 변경 이력 참조), 진짜 `is_error=True` 피드백 
루프의 증거는 실측 케이스로 확보한다. 아래는 D-6 회귀 측정 중 실제 수집된 
사례.

### 8.1. DB 타입 에러 자가교정 (C3 첫 시도, 2026-04-23 11:11)

**관찰 맥락**: 골든셋 C3 — "상품 유형별 월별 APE와 보험금 청구 발생 비율을 
같이 봤을 때 손해율 관점에서 문제 있는 구간 있어?" 를 Executor가 실행하는 
중, Sonnet 4.6이 생성한 LARGE CTE 쿼리(11개 CTE)가 PostgreSQL 타입 체계와 
충돌한 실제 사례.

#### 타임라인 (로그 원문: `.tmp/core8_20260423_1109.log`)

| 시각 | 이벤트 |
|---|---|
| 11:11:06 | `list_tables` 호출 |
| 11:11:13~14 | `describe_table(monthly_ape)`, `describe_table(claims)`, `describe_table(policies)`, `describe_table(products)` 순차 호출 |
| 11:11:39.947 | `execute_readonly_sql` 호출 — 11개 CTE 체인, 마지막 SELECT에 `ROUND(...)` 사용 |
| 11:11:39.952 | Guard: `Guard passed (tables: ('active_policies', 'ape_by_type', 'avg_loss', 'claims', 'claims_by_type', 'combined', 'metrics', 'monthly_ape', 'months', 'policies', 'products'))` — 통과 |
| 11:11:39.970 | DB: `[ERROR] DB execution failed: function round(double precision, integer) does not exist` LINE 101 |
| 11:11:39.972 | Executor 레이어: `[WARNING suri.executor] Tool error: ... (DBExecutionError)` — `is_error=True` 플래그로 LLM에 반환 |
| 11:11:59.688 | **20초 후**, Executor가 **재시도** — 같은 CTE 구조 유지(쿼리 시작 `WITH -- ── 1. APE by product_type × year_month ───`), ROUND 부분만 수정 |
| 11:12:00.356 | `Query executed successfully` — 복구 완료 |

#### 핵심 메커니즘

- **에러 전달 경로**: MCP server (`db.py`) → `{"type": "DBExecutionError", "error": "..."}` JSON 반환 → Executor가 `is_error=True`로 `tool_result` block에 주입 → 다음 Anthropic API 호출의 user content로 LLM에 전달.
- **LLM의 자체 수정**: 오케스트레이터 개입 없음. Sonnet 4.6이 에러 메시지의 `HINT: You might need to add explicit type casts` 를 읽고 `CAST(... AS numeric)` 혹은 `::numeric` 추가해 재생성. 같은 CTE 11개 구조를 유지하면서 ROUND 호출부만 수정 — "전체 재작성" 아닌 "핀포인트 수정"에 해당.
- **재시도 limit**: `MAX_GUARD_RETRIES=2` 내 해결. 2회 한도 초과 시 Orchestrator가 에러를 그대로 반환하게 설계됨(executor.py 참조).

#### 이 케이스의 의미

1. **자가교정이 문서 속 주장이 아니라 실측**: 어느 다른 포트폴리오가 "로그 원문으로 증빙 가능한 자가교정 케이스" 를 제출할 수 있나. 이게 차별화.
2. **`is_error=True` 피드백 루프의 설계가 실증**: ADR-003의 설계 선택(MCP tool이 예외 raise 대신 에러 JSON return + Executor가 `is_error=True`로 LLM에 재주입)이 실제 운영에서 작동함을 보여주는 single-shot 증거.
3. **Guard와 DB Error의 layered 분업**: 같은 재시도 메커니즘이 `GuardViolation`(Layer 1 차단)과 `DBExecutionError`(Layer 3+ 실행 오류) 둘 다 커버함. 즉 자가교정 한 축이 3층 방어의 모든 층과 정합.
4. **LLM의 hint 활용**: PostgreSQL이 주는 `HINT: No function matches the given name and argument types. You might need to add explicit type casts.` 메시지를 LLM이 그대로 흡수. 이게 "에러를 숨기지 말고 구조화해서 전달하라"는 ADR-003 설계의 payoff.

#### 시연용 재현 경로

면접 시 라이브 재현이 어려우면 아래 경로로 증빙 가능:

1. `.tmp/core8_20260423_1109.log` 파일 열기 (면접 노트북에 보존)
2. `11:11:39` ~ `11:12:00` 구간 20초 (grep로 추출 가능)
3. 3줄짜리 스크린샷:
   - 에러: `[ERROR] DB execution failed: function round(double precision, integer) does not exist`
   - 재시도: `[INFO] execute_readonly_sql called: WITH -- ── 1. APE by product_type × year_month ───`
   - 성공: `[INFO] Query executed successfully`

#### 면접 Q&A 답변 템플릿

**Q**: "자가교정이 실제로 작동하는지 어떻게 증명하나요?"

**A (45초)**: 
> "D-6 회귀 측정 중 실제 발생한 사례가 있습니다. Sonnet이 손해율 proxy 쿼리를 짜면서 `ROUND(double precision, integer)`를 호출했는데, 이건 PostgreSQL에서 지원 안 되는 시그니처입니다. 우리 MCP 서버가 이 DB 에러를 JSON으로 구조화해서 `is_error=True` 플래그와 함께 LLM에 재전달하자, LLM이 PostgreSQL의 HINT 문구를 읽고 `CAST` 추가해서 20초 뒤 재시도 — 성공했습니다. 로그 원문이 `core8_20260423_1109.log` 11시 11분부터 11시 12분 구간에 남아있어 스크린샷으로도 보여드릴 수 있습니다."

**Q**: "왜 try/except로 막지 않고 LLM한테 돌려주나요?"

**A (30초)**:
> "세 가지 이유입니다. 첫째, try/except는 에러를 **감추고** 다음 쿼리에 대한 정보를 주지 않습니다. 구조화된 에러는 LLM에게 다음 행동을 결정할 정보를 줍니다. 둘째, 이런 타입 에러는 인간 DBA도 가끔 놓치는 영역입니다 — PostgreSQL만의 ROUND 시그니처 제약. LLM이 HINT 메시지 하나로 해결하는 게 오히려 빠릅니다. 셋째, 면접에서 '실측으로 증명되는 resilience'로 설명할 수 있게 됩니다."

#### 한계

- 2회 재시도 한도 내에서만 복구. 복잡한 semantics 에러(예: JOIN 조건 오류로 결과가 0건)는 재시도로 해결 안 됨 — Critic이 "결과 없음"을 설명하게 됨.
- Planner-Executor간 state 전달은 JSON Plan 뿐. Executor의 실패 정보가 Planner로 거슬러 올라가진 않음(설계 선택, ADR-003).

### 8.2. TBD — 추가 케이스 수집 시 여기에 정리

향후 candidates:
- Scene 3 멀티턴 드릴다운 중 Context 누적 관찰
- GuardViolation 후 `suggested alternative` 힌트로 쿼리 재작성 (C4 v3 버전 관찰 가능)
- 쿼리 timeout 발생 시 LIMIT 추가 재시도 (미발생)

D-4 이전까지 수집되는 실측 케이스는 이 섹션에 추가. 문서 구조 동결 이후엔 
내용만 보강 가능.

---

## 9. 프로젝트 운영 원칙 (메타)

§1~§8이 개별 결정이라면 §9는 **프로젝트 전체를 관통하는 운영 원칙**. 면접에서 *"어떻게 판단했나"*를 물을 때 이 섹션의 원칙들을 근거로 답변.

### 9.1 프롬프트 Overfitting 경계 원칙

#### 배경

D-6 C1 디버깅 중 유혹적인 해결책: *"Executor 프롬프트에 SQL 템플릿을 박으면 수치 편차가 사라진다."* 실제로 템플릿 추가하면 C1 3회 반복 시 낙차 수치가 거의 동일하게 수렴.

#### 원칙: 골든셋을 맞추기 위한 프롬프트 수정은 안티패턴

- **Glossary 역할**: 용어 **정의** 결정성 (분모 코호트 정의, APE 환산 공식)
- **프롬프트 역할**: 일반 원칙 (Tool-first, 3층 방어 준수, 답변 형식)
- **금지 영역**: 특정 질문·시나리오 전용 규칙

만약 *"GA 채널 질문이면 channel_type=GA를 먼저 WHERE 절에 넣어라"* 같은 규칙을 프롬프트에 박으면:
1. C1은 안정화되지만 C1 변형(*"방카 채널 유지율은?"*)에 대응 실패
2. 골든셋 바깥 질문에서 **Agent 자율성 급락**
3. 면접관이 골든셋 바깥 질문 즉석 테스트하면 붕괴

#### 판별 기준 ("보편 규칙 vs overfitting")

프롬프트 수정 제안이 들어왔을 때 다음 체크:

- **Q1**: 이 규칙이 특정 골든셋 ID(C1·C3 등)나 특정 엔티티(GA·P004 등)를 언급하는가? → YES면 overfitting
- **Q2**: 이 규칙이 질문의 **표면 구조**가 아닌 **도메인 원칙**에서 도출되는가? → NO면 overfitting
- **Q3**: 이 규칙을 글로벌 적용하면 다른 케이스에서 부작용이 있는가? → YES면 overfitting

**예시**:
- ✅ OK: *"유지율 계산 시 회차별로 분모가 달라지므로 코호트 기반 정의를 쓸 것"* (Glossary `critical_note`에서 도출)
- ✅ OK: *"CSM처럼 산출 불가 지표는 proxy 대안을 제시"* (graceful degradation 원칙)
- ❌ OUT: *"GA 채널 낙차가 크면 승환계약 언급"* (Glossary `승환계약.critic_활용_힌트` 레벨은 OK, 프롬프트 박기는 overfitting)
- ❌ OUT: *"질문에 \"분기 리스크\"가 있으면 6개 차원 분석하라"* (A1 전용 규칙)

#### 실제 적용 사례 (C1 6회 측정)

- **편차 수용**: 낙차 1.07%p~18.10%p 편차. 이를 프롬프트로 강제 수렴시키지 않음
- **결과**: 6/6 GA 1위 유지 + GA 25회차 71.13% 5/6 수렴 (Glossary의 진짜 기여)
- **기록**: `docs/known-limitations.md §2` 에 6회 측정 테이블로 정직 문서화

#### 면접 답변 템플릿

**Q**: *"C1 편차 왜 안 줄였어요?"*

**A (45초)**:
> "SQL 템플릿을 프롬프트에 박으면 C1은 0%p 편차로 수렴합니다. 근데 그건 **Agent가 아니라 스크립트**가 됩니다. 제가 택한 기준은 '의미론적 결정성은 Glossary로 보장하되 SQL 구조는 Agent 자율성에 맡긴다'입니다. 6회 측정에서 6/6이 GA 낙차 1위고 5/6이 25회차 71%대로 수렴합니다. 골든셋 바깥 질문 변형에 대응하려면 이 자율성이 필요합니다. 완벽한 결정성보다 **일관된 결론**이 프로덕션에 더 가깝습니다."

### 9.2 Sprint Rule 예외 허용 기준

#### 배경

9일 타임박스에서 스코프 크립 방지를 위해 Sprint Rules hard:
- D-6 이후 신규 스택 금지
- D-5 이후 신규 시나리오 금지
- D-4 이후 UI 개선 금지
- D-3 이후 문서 구조 변경 금지
- D-2 시작 = 이력서 풀데이

#### 원칙: Sprint Rule은 자기 통제 도구지 맹신할 법칙이 아님

Rule의 목적은 (1) 스코프 크립 방지 (2) 집중 강제 (3) 피로 관리. 이 목적을 **달성**하면서 예외가 가치 있다면 깨도 됨. 단 기준을 명시.

#### 예외 허용 조건 (AND, 전부 충족 필수)

1. **스코프 크립 아님**: 새 기능 추가가 아닌 기존 기능 개선
2. **시간 여유 실재**: 이력서·리허설 시간 침해 없음
3. **명확한 가치**: 면접 임팩트·시연 품질 향상에 직접 기여
4. **타임박스 설정**: 시작 전 마감 시점 명시
5. **롤백 가능**: feature branch 또는 회귀 테스트로 원복 가능
6. **기록**: 예외 사유를 문서에 남김 (이 §9에 추가 또는 ADR로)

#### D-5 실제 예외: UI 실시간 진행 표시

- **언제**: 2026-04-24 (D-5) 오후
- **무엇**: `st.status` 3단계 (Planner/Executor/Critic) + tool 호출 실시간 표시 + 버튼 비활성화
- **왜 예외 인정**:
  - 스코프 크립 아님 (기존 UI 개선)
  - 옵션 B 계층 그룹핑으로 시연 임팩트 큼 (4개 차별화 축이 화면에 실시간 증명)
  - D-5 저녁까지 완료 조건 (타임박스)
  - Core 8 8/8 회귀 즉시 검증 (롤백 가능)
- **제약**:
  - D-4 아침부터는 UI 손 안 댐
  - 다른 UI 개선은 이 예외에 해당 안 됨
  - 5시간 초과 시 Abort

#### 면접 답변 템플릿

**Q**: *"Sprint Rule 만들어놓고 깨셨네요?"*

**A (45초)**:
> "D-5 저녁에 UI 실시간 진행 표시를 추가했습니다. 의도적으로 깼습니다. Sprint Rule은 **스코프 크립을 막는 도구**지 맹신할 법칙이 아닙니다. 이번 건은 기존 기능 개선이고, 시연 임팩트가 크고, 시간 여유가 있었습니다. 단 예외 기준을 명시했습니다: 스코프 크립 아닐 것, 타임박스 설정할 것, 롤백 가능할 것, 기록할 것. 이 6가지 기준을 통과한 경우에만 허용. 덕분에 D-4부터는 UI 동결을 지켰고 D-3 이력서·D-2 풀데이는 건드리지 않았습니다. **규칙을 만들 줄 알면 깰 줄도 알아야** 시니어입니다."

### 9.3 차별화 축 5개와 각 축의 증거

면접관이 *"이 프로젝트의 차별점은?"* 물을 때 **축별로 구체 증거**로 답변. 추상적 슬로건 X.

| # | 차별화 축 | 핵심 증거 | 근거 문서 |
|---|---|---|---|
| 1 | **Governance (3층 방어)** | SQL Guard AST + suri_readonly ROLE + customers_safe VIEW + C5 시나리오 하드 블록 | §4 + ADR-001 |
| 2 | **Architecture (최소 의존성)** | 공식 mcp SDK + anthropic SDK 2개만. LangChain·chromadb 기각 | §5 + ADR-002·003·004 |
| 3 | **Behavior (Tool-first)** | list_tables → describe → SQL 패턴, 스키마 선행 탐색 | §5.2 + 실측 C3 로그 |
| 4 | **Resilience (자가 교정)** | C3 실측 로그: ROUND 타입 에러 → HINT 흡수 → 20초 후 재시도 성공 | §8.1 (실측 증거) |
| 5 | **Domain Grounding (용어 결정성)** | Glossary 20용어 + `get_domain_term` MCP tool + C1 25회차 71.13% 5/6 수렴 | ADR-004 + known-limitations §2 |

#### 축별 45초 답변 예시

**축 1 (Governance)**:
> "3층 방어 구조입니다. Application 레이어의 SQL Guard가 sqlglot AST 기반 파싱으로 `customers` 테이블 접근을 차단하고, DB 레이어에서 suri_readonly ROLE이 `SELECT` 외 권한을 원천 차단하고, Schema 레이어에서 `customers_safe` VIEW가 PII 컬럼을 필터링합니다. 시연에서 '고객 전화번호 뽑아줘' 질문 시 3층이 순차적으로 작동하는 걸 보여드립니다."

**축 4 (Resilience)**:
> "실측 증거가 있습니다. D-6 회귀 측정 중 Sonnet이 `ROUND(double precision, integer)` 호출했는데 PostgreSQL이 지원 안 하는 시그니처였습니다. 제 MCP 서버가 에러를 `is_error=True` JSON으로 LLM에 재전달했고, LLM이 PostgreSQL HINT를 읽고 CAST 추가해서 20초 후 재시도 성공했습니다. 로그 원문이 `core8_20260423_1109.log`에 남아있어 스크린샷 드립니다."

**축 5 (Domain Grounding)**:
> "도메인 용어 해석 비결정성을 Glossary MCP tool로 해결했습니다. ADR-004입니다. Vector DB 기반 RAG 대신 YAML 20용어를 `get_domain_term` tool로 조회하는 deterministic glossary. 법령·기준서 출처 기반, 자체 작성 정의 제로. 이 규모에서 vector retrieval의 recall 이점이 없어서 이 선택이 의존성 최소화 철학과 정합합니다. 확장 경로는 pgvector로 4단계 Migration Path 명시."

### 9.4 "완벽보다 증명"의 운영 원칙

SURI는 **완성 지향**이 아니라 **증명 지향**으로 설계됨. 각 결정이 "왜 이렇게 짰나"를 면접 45초 안에 증명 가능해야 채택. 증명 불가하면 쳐냄.

#### 구체 적용

- **축 선정**: 5개 축 모두 **측정 가능한 증거**로 뒷받침 (로그, 6회 측정 테이블, 시연 시나리오)
- **결정 근거**: ADR 4개가 대안 비교 + 기각 사유 명시
- **한계 기록**: `known-limitations.md`가 "모른다/못한다"를 문서로 정직 노출

#### 면접 서사 뼈대

> "9일 안에 완성한 게 아니라, 9일 안에 **어떻게 만들 것인지 설계**했습니다. 코드는 그 설계가 작동 가능함을 증명하는 최소 구현입니다."

이 한 줄이 모든 Q&A의 프레이밍. 기능 누락 질문에도 *"완성도 경쟁에 참여하지 않았다"* 로 대응 가능.

---

## References

- ADR-001 ~ ADR-004
- `docs/known-limitations.md` (§2 C1 6회 측정, §6 3턴 상한)
- `docs/glossary-draft.yaml` (20용어)
- `docs/golden-set.md` v3.1
- `.tmp/core8_20260423_1109.log` (§8.1 자가교정 증거)
- `.tmp/c1-day5/` (C1 3회 D-5 측정 로그)
