# SURI 확장 Q&A (D-5 기준)

**기존 `interview-answers.md` 보완용**. 오프닝·AI 활용·기술 심화·압박성 기본은 그 문서가 커버. 이 문서는 **D-6 ~ D-5에 추가된 요소** (Glossary, 멀티턴, 실시간 UI, C1 재현성, 배포 등)에 대한 예상 질문.

**원칙**:
- 1차 서류 심사 후 2차 면접관이 레포 훑고 던질 만한 질문
- 45초 이내 답변 + 구체 증거 (로그 경로, 문서 섹션)
- ADR/known-limitations/design-decisions를 근거로 인용

---

## Q1. "Domain Glossary MCP tool — 그냥 dict lookup 아닌가요? RAG 맞나요?"

**예상 상황**: 이력서·README에 RAG 언급 보고 파고드는 2차 면접관.

### 답변 (45초)

> "RAG의 본질은 Retrieval-Augmented Generation — LLM이 외부 지식을 검색해 context에 주입하는 것입니다. 제 구현은 retrieval layer를 vector 기반이 아닌 exact-match로 했습니다. 이유는 세 가지입니다.
>
> 첫째, 규모 부적합. 도메인 용어 50개 수준에서 vector retrieval의 recall 이점이 없고 오히려 latency·의존성 비용만 추가됩니다.
>
> 둘째, 철학 일관성. ADR-001, 002, 003이 모두 '의존성 최소화'인데 chromadb 추가하면 이 철학이 편의적이 됩니다.
>
> 셋째, 확장 경로 설계. ADR-004에 Migration Path 4단계를 명시했습니다. YAML → PostgreSQL dictionary table → pgvector → 사내 Data Catalog. 현재 Phase 1이 Phase 2~4를 차단하지 않도록 설계했습니다.
>
> 엄격한 vector DB 기반 RAG가 정의라면 이건 RAG가 아닙니다. 하지만 'Tool Usage 및 RAG 구현'이라는 JD 문구의 본질은 이게 만족한다고 봅니다."

### 증거
- ADR-004: `docs/adr/ADR-004-domain-glossary.md`
- Glossary 원본: `docs/glossary-draft.yaml` (20용어)

---

## Q2. "멀티턴 구현했다던데, 왜 3턴 제한인가요?"

**예상 상황**: Scene 3 시연 본 후 확장 가능성 질문.

### 답변 (45초)

> "세 가지 의도적 제약입니다.
>
> 첫째, 시연 스코프. Scene 3는 채널 → 상품 → 계절성 드릴다운 3턴으로 설계됐습니다. 더 긴 대화는 PoC 목적에 비해 오버입니다.
>
> 둘째, Context Management 단순화. 3턴 이내면 전체 history를 Planner에 그대로 주입해도 토큰 문제 없습니다. Sliding window나 요약 주입 같은 복잡도가 불필요합니다.
>
> 셋째, 확장 경로는 설계 완료. known-limitations §6.1에 Phase 1~4 명시했습니다. 현재 Phase 1(전체 history 전송, 3턴 상한), Phase 2 sliding window, Phase 3 요약 주입, Phase 4 대화 전체 벡터 DB. 10턴·100턴이 필요한 시점에 단계적으로 확장합니다.
>
> 구현 면에서는 Planner 1곳에만 history 주입했습니다. Executor·Critic·MCP 서버는 무변경. `history=None` 디폴트로 기존 단일턴 호출 100% 호환 유지해서 Core 8 회귀 없었습니다."

### 증거
- `docs/known-limitations.md §6.1`
- `app/agents/planner.py` 시그니처: `plan(question, history=None)`
- Scene 3 실측: T1 GA 71% → T2 P004 행복연금Plus → T3 3월/12월 피크

---

## Q3. "C1 측정 결과 재현성이 편차가 크다던데 — 이건 버그 아닌가요?"

**예상 상황**: known-limitations §2.1의 6회 측정 표를 본 면접관.

### 답변 (45초)

> "버그 아닙니다. 의도된 설계의 결과입니다.
>
> 6회 측정에서 GA 낙차 절대값은 1.07%p ~ 18.10%p로 편차 크지만, 세 가지는 결정적입니다:
> - 상대 순위: 6/6이 GA를 1위로 식별
> - GA 25회차 유지율: 6회 중 5회가 71.13%로 수렴
> - `payment_month_seq >= N` 분모 오류: 0건 (Glossary 효과)
>
> 편차는 13회차 코호트 정의 해석에서 나옵니다. Glossary의 critical_note가 '회차별 분모가 다름'을 명시하는데, 그 해석 폭 안에서 Agent가 자율 판단합니다.
>
> SQL 템플릿을 프롬프트에 박으면 이 편차를 0으로 만들 수 있습니다. 하지만 그건 Agent가 아니라 스크립트입니다. design-decisions §9.1에 'Prompt overfitting 경계 원칙'으로 기록했습니다. '의미론적 결정성은 Glossary가, SQL 구조는 Agent 자율성이'라는 역할 분리입니다.
>
> 완벽한 결정성보다 일관된 결론이 프로덕션에 더 가깝다고 봤습니다."

### 증거
- `docs/known-limitations.md §2.1` (6회 측정 테이블)
- `docs/interview-prep/design-decisions.md §9.1`

---

## Q4. "UI에 실시간 진행 표시 있던데 — 이건 왜 추가하셨어요?"

**예상 상황**: 데모 보고 "이건 과한 거 아니냐" 또는 "왜 추가했냐" 질문.

### 답변 (45초)

> "포트폴리오 맥락에서 필수적이라 판단했습니다.
>
> Agent가 60~100초 걸리는데 블랙박스로 두면 사용자는 '기다림'만 경험합니다. 실시간 진행 표시로 보면 Planner → Executor의 tool 호출 N회 → Critic이라는 전체 플로우가 눈에 들어옵니다. 특히 Executor의 self-correction이 실시간으로 보이는 게 중요합니다.
>
> 구현은 콜백 기반입니다. Orchestrator가 `on_event` 콜백 파라미터를 받고, 각 stage 시작·종료·tool 호출·재시도 시점에 이벤트를 쏩니다. Streamlit은 이 이벤트를 `st.status` 3단계로 계층 렌더합니다.
>
> 한 가지 투명히 말씀드리면, 이건 제 Sprint Rule 상 D-4부터 UI 동결이었는데 의도적으로 예외 처리했습니다. design-decisions §9.2에 예외 기준과 타임박스를 명시해서 이 예외가 다음 예외로 번지지 않도록 통제했습니다. Rule을 만들 줄 알면 깰 줄도 알아야 한다고 봤습니다."

### 증거
- `docs/interview-prep/design-decisions.md §9.2`
- `app/agents/orchestrator.py`: `on_event` 콜백

---

## Q5. "Railway 배포는 어떻게 하셨어요? 보안 처리는?"

**예상 상황**: 라이브 URL 누르고 들어온 면접관이 보안·비용 궁금해함.

### 답변 (45초)

> "Railway 단일 프로젝트로 PostgreSQL 애드온 + Streamlit 컨테이너 배포했습니다.
>
> 보안은 기존 3층 방어가 그대로 작동합니다. 오히려 **public 배포라 3층 방어가 실증됩니다**. 면접관이 '고객 전화번호 뽑아줘' 같은 악의적 질의를 던지면 Layer 3 하드 블록이 작동하는 걸 직접 보실 수 있습니다.
>
> API 비용은 Anthropic 콘솔에서 월 한도를 설정해서 폭주 방지했고, 합성 데이터 61만 행이라 PostgreSQL 부하도 제한적입니다. `execute_readonly_sql` tool에 기본 LIMIT 100행 + truncation 감지가 걸려있어서 거대한 SELECT도 차단됩니다.
>
> 비밀 키는 Railway 환경변수만 사용. `.env.example`만 레포에 올라가 있고 실제 키는 Railway 내부에만 있습니다.
>
> 프로덕션 이관 시 필요한 건 secret manager 연동, 인증·rate limiting 도입, APM 연결인데 이건 known-limitations §8에 기록했습니다."

### 증거
- `docker-compose.yml`, `railway.toml`, `Procfile`
- `docs/known-limitations.md §8`

---

## Q6. "Scene 3 T1 → T2 → T3 한 번 돌려주세요 (라이브)"

**예상 상황**: 데모 요청. 테크니컬 면접관이 멀티턴 자체를 검증.

### 답변 (액션 + 45초 설명)

> [T1 클릭 → 실행] 
>
> "T1은 판매채널별 25회차 유지율입니다. GA가 71.13%로 최저 채널로 나옵니다. [답변 표시]
>
> [T2 클릭 → 실행]
>
> T2는 '응, GA 중에서도 어떤 상품이 제일 심해?' 입니다. 여기서 '그 중 GA'라는 맥락 참조어가 있습니다. Planner가 T1 맥락을 받아서 intent를 'GA 채널 내 25회차 유지율 가장 낮은 상품'으로 구체화합니다. SQL에 `channel_type = 'GA'` 필터가 자동 추가됩니다. 결과는 P004 행복연금Plus(67.86%)로 나옵니다.
>
> [T3 클릭 → 실행]
>
> T3는 '그 상품 언제 많이 팔렸는지 계절성도 봐줘'. 여기서 '그 상품'이 2턴 전 T1의 엔티티가 아니라 직전 T2의 P004로 정확히 해석됩니다. 결과는 3월·12월 피크. 이건 제가 합성 데이터에 의도적으로 주입한 '3월 절판 스파이크' 패턴이 드러난 겁니다. Critic이 도메인 해석을 덧붙여서 'GA 채널 3월·12월 집중 계약건의 25회차 유지율이 특히 낮을 가능성'까지 추론합니다."

### 증거
- 실시간 화면 스크린샷 (사전 준비)
- `scripts/test_multiturn.py` e2e 스모크

---

## Q7. "차별화 축 5개 말씀하셨는데, 각 축의 가장 강한 증거 하나씩만 말씀해주세요"

**예상 상황**: 축별 실증 요청. 슬로건이 아닌 증거 검증.

### 답변 (60초, 축별 10초씩 + 오프닝)

> "5축 각각 구체 증거로 설명드리겠습니다.
>
> 1. **Governance (3층 방어)**: C5 시연에서 '고객 전화번호 뽑아줘' 질의에 Layer 3 하드 블록이 실시간 작동합니다. SQL Guard AST + `suri_readonly` ROLE + `customers_safe` VIEW가 순차 차단됩니다.
>
> 2. **Architecture (최소 의존성)**: `pyproject.toml`이 증거입니다. mcp + anthropic SDK 2개만. LangChain·chromadb·Phoenix 전부 기각했고 ADR-002·003·004에 각각 근거 기록했습니다.
>
> 3. **Behavior (Tool-first)**: 어떤 질문이든 Agent가 list_tables → describe_table → execute_readonly_sql 순서로 움직입니다. DB가 single source of truth이고 프롬프트에 하드코딩된 스키마 지식 0입니다.
>
> 4. **Resilience (자가 교정)**: D-6에 실측된 사례가 있습니다. Sonnet이 `ROUND(double precision, integer)` 호출했는데 PostgreSQL이 지원 안 하는 시그니처였습니다. `is_error=True` JSON으로 LLM에 재전달하자 20초 후 `CAST` 추가로 재시도 성공. 로그 원문이 `core8_20260423_1109.log`에 있습니다.
>
> 5. **Domain Grounding**: C1 6회 측정에서 GA 25회차 유지율이 5/6 71.13%로 수렴합니다. Glossary가 용어 정의를 결정적으로 주입한 결과입니다.
>
> design-decisions §9.3에 5축 × 증거 × 문서 참조 표로 정리했습니다."

### 증거
- `docs/interview-prep/design-decisions.md §9.3`

---

## Q8. "self-correction 실측 사례 — 코드 레벨에서 어떻게 구현되나요?"

**예상 상황**: Q7의 4축 답변에 꽂혀서 파고드는 기술 면접관.

### 답변 (60초)

> "설계 원칙은 '에러를 숨기지 말고 구조화해서 전달하라' 입니다. 구체적으로:
>
> **1단계 — MCP 서버에서 구조화된 에러 반환**: try/except로 에러를 먹어버리지 않습니다. `db.py`가 `{'type': 'DBExecutionError', 'error': '...', 'hint': '...'}` JSON을 반환합니다. Guard 에러는 `{'type': 'GuardViolation', ...}`으로 별도 타입입니다.
>
> **2단계 — Executor가 is_error 플래그로 LLM에 재주입**: Anthropic SDK의 tool_result block에 `is_error=True`로 마킹합니다. 이러면 LLM이 '이 tool 호출은 실패했다'를 명시적으로 인지합니다. 에러 메시지는 content에 그대로.
>
> **3단계 — LLM의 자체 수정**: Orchestrator는 재시도 결정을 안 합니다. LLM이 다음 행동을 결정합니다. 제가 본 사례에서는 LLM이 PostgreSQL의 `HINT: You might need to add explicit type casts`를 읽고 `CAST(... AS numeric)` 추가해서 재생성했습니다. 같은 11개 CTE 구조는 유지하면서 `ROUND` 호출부만 수정 — '핀포인트 수정'입니다.
>
> **안전장치**: `MAX_GUARD_RETRIES=2`로 무한 루프 방지. 2회 초과 시 에러를 그대로 반환하고 Critic이 '결과 없음'으로 해석합니다.
>
> try/except로 먹어버렸으면 LLM이 다음에 어떻게 할지 정보가 없습니다. 이 설계의 핵심입니다."

### 증거
- `docs/interview-prep/design-decisions.md §8.1`
- `.tmp/core8_20260423_1109.log`
- `app/agents/executor.py` MAX_GUARD_RETRIES

---

## Q9. "known-limitations 정직하게 쓴 게 오히려 마이너스 아닌가요?"

**예상 상황**: 한계를 너무 많이 노출한 것 아니냐는 압박.

### 답변 (45초)

> "반대로 생각합니다. '잘 되는 것'만 말하는 포트폴리오가 의심스럽습니다.
>
> known-limitations에 기록한 것들은 세 종류입니다:
>
> 1. **의도적 포기** — 예: CSM 정식 산출. BEL·RA·할인율 체계가 없어서 못 합니다. 이건 프로젝트 스코프 판단이지 능력 한계가 아닙니다. 대신 graceful degradation 패턴으로 proxy 대안 제시하게 설계했습니다.
>
> 2. **측정된 한계** — 예: C1 낙차 절대값 편차. 6회 측정해서 재현성을 정량화했습니다. 감으로 '잘 돌아간다'가 아니라 실측으로 '70% 재현, 나머지는 해석 편차'입니다.
>
> 3. **Production 이관 갭** — 9일 PoC라 secret manager·APM·rate limiting 미구현. 이건 prod 배포 시 필요한 작업 리스트지 현재 실패가 아닙니다.
>
> 한계를 아는 게 한계 없는 척보다 면접관에게 더 신뢰를 줍니다. 한화생명 같은 금융권은 특히 이런 투명성이 거버넌스 문화와 맞습니다."

### 증거
- `docs/known-limitations.md` 전체

---

## Q10. "9일 더 있으면 뭐 할 거예요?"

**예상 상황**: 자연스러운 확장 능력 체크.

### 답변 (45초)

> "우선순위 3개 있습니다.
>
> **1. 실시간 스트리밍 UI**: 현재는 Critic 답변이 완성된 뒤 한 번에 렌더됩니다. LLM의 토큰 스트리밍을 받아서 Answer가 한 글자씩 타이핑되는 UX로 바꾸면 시연 체감 품질이 올라갑니다. 기술적으로 Anthropic streaming API + Streamlit `st.empty` 조합인데 Pending-run 패턴과 충돌 해결이 필요합니다.
>
> **2. Query Plan 시각화**: Executor가 만든 SQL의 EXPLAIN ANALYZE 결과를 UI에 노출. 면접관이 'Agent가 만든 쿼리 품질'을 직접 평가할 수 있게 됩니다. `SELECT *` 남발을 Agent가 피하는지, JOIN 순서가 효율적인지.
>
> **3. Agent 학습 루프**: 지금은 매 세션이 독립입니다. 실측 성공·실패 케이스를 로깅해서 few-shot 프롬프트에 주입하는 피드백 루프를 만들면 시간이 지날수록 정확도가 올라갑니다. 이건 production 설계에 가까운 범위입니다.
>
> 하지만 이 세 가지 중 우선순위 판단은 실제 사용자 피드백 없이 못 합니다. 상품 기획자가 쓸 때 무엇이 가장 답답한지 관찰해야 어디에 시간 투입할지 결정할 수 있습니다."

### 증거
- known-limitations §6.2 스트리밍 UI 미구현
- 향후 확장 경로

---

## 사용법

1. 암기 X, 구조 이해 O
2. 실제 답변 시 구체 증거(파일 경로, 문서 섹션) 1개 이상 언급
3. "모르겠다"는 답이 필요한 경우는 "지금 바로 말씀드리기 어려운데, docs/ADR에 근거 문서가 있습니다. 화면 공유해도 될까요?" 패턴
4. 압박 질문 (Q3, Q9)은 감정 반응 없이 **데이터로만** 답변

## 체크리스트

- [ ] 답변 녹음해서 들어보기 (45초 넘는지)
- [ ] 각 Q별 증거 파일 경로를 바로 열 수 있게 노트북 북마크
- [ ] Q6 라이브 시연은 실패 시 녹화 백업 준비
- [ ] Q8 코드 레벨 질문은 파일 열어서 보여주는 연습
