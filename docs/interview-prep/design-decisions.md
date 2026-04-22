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
- **결정**: ADR-001(스택), ADR-002(MCP 라이브러리) 작성
- **근거**: 
  1. 6개월 후 내가 왜 그랬는지 알 수 있게
  2. 면접에서 결정 근거 화면 공유 가능
  3. 금융권의 "변경 이력 추적" 관행
- **포맷**: Context / Decision / Rationale / Consequences / Alternatives Considered

### 6.3 4개 AI 교차검증 패턴
- **결정**: 주요 결정마다 ChatGPT, Gemini, Claude, Perplexity에 리서치 요청
- **근거**: 단일 AI 편향 방지. 시각 차이로 놓친 옵션 발견 가능 (MCP A2 케이스)
- **반론 대처**: "시간 낭비 아닌가?" → 리서치는 3분, 잘못된 결정 수정은 몇 시간. ROI 압도적

---

## 7. 자주 나올 질문 모음

### Q: "프로젝트의 가장 큰 기술적 도전은?"
- 답: INTEGER → BIGINT 전환. VIEW 의존성 때문에 단순 ALTER 불가능. DROP VIEW → ALTER TABLE → CREATE VIEW를 트랜잭션으로 감싸는 패턴 적용. 금융 금액은 BIGINT 필수라는 교훈.

### Q: "포기한 기능은?"
- RAG 기능. D-5 체크포인트 이후로 조건부 추가로 미뤘고, 최종적으로 Future Work. 이유: MVP 범위에서 벡터 DB 추가 의존성 vs 시나리오 재현성 확보 사이 후자가 중요했음.

### Q: "개선하고 싶은 부분은?"
1. `customer_id` UUID 해시화 (현재 순차 ID → 준-PII)
2. `load.py` 상대 임포트 정리 (현재 절대 임포트로 `-m` 실행에만 동작)
3. IFRS 17 로직 구현 (`ifrs17_group_id`, `measurement_model`)
4. `checks.py` pytest로 포팅

### Q: "다시 만들면?"
- Generated Column + Foreign Key 참조 검토 (PostgreSQL 12+ 지원 여부 확인 후)
- 처음부터 상대 임포트 사용
- `dateutil.relativedelta`로 날짜 산술 (Feb 29 문제 자동 처리)

