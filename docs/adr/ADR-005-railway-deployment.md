# ADR-005: Production Deployment — Railway Single-Project Pattern

**상태**: Accepted
**작성일**: 2026-04-24 (D-5)
**컨텍스트**: SURI 포트폴리오 제출용 라이브 데모 URL 배포

---

## Context

### 제출 형태 전환

초기(D-7) 가정: GitHub 레포 + 로컬 시연. 실제 면접 단계에서만 라이브 데모.

D-5 재확인: 한화생명 지원 프로세스에서 **1차 서류 심사 시점에 라이브
URL을 이력서·포트폴리오에 첨부**. 면접관이 **독립적으로** 직접 사용 가능한
환경 필요. 이 요구는 배포 우선순위를 선택이 아닌 필수로 격상시킨다.

### 배포 제약

- **9일 타임박스 잔여 3일** (D-5→D-2): 배포 + 검증 + 리허설 + 이력서
  동시 진행. 배포 작업 자체는 4시간 이내로 마감해야 전체 일정이 안전.
- **ADR-001~003 철학 연속성**: 의존성 최소화, 동작 명시성, 변경 surface
  최소화. 인프라에도 동일 기준 적용.
- **비용**: Anthropic API 월 한도는 별도 관리 중. 인프라 월 $15 이하.
- **보안**:
  - `ANTHROPIC_API_KEY` 노출 방지
  - `suri_readonly` 비밀번호를 코드·git 히스토리에 노출 금지
  - 악의적 질의(PII 추출 시도)에 대한 방어가 공개 URL에서도 작동해야 함

### 이미 결정된 사항 (ADR-001~004)

- PostgreSQL 15 + 61만 행 합성 데이터
- 3층 PII 방어 (Application Guard + `suri_readonly` ROLE + `customers_safe` VIEW)
- MCP 서버는 stdio transport (subprocess)
- 의존성: `mcp` + `anthropic` + `streamlit` + `psycopg[binary]` + `sqlglot` + `pyyaml`
- Streamlit 멀티페이지 UI (Agent 대화 + Glossary + Schema + Data Sample + Admin)

---

## Decision

**Railway 단일 프로젝트 내 2개 서비스 구성**:

1. **Streamlit + MCP subprocess** (메인 컨테이너)
   - NIXPACKS 빌드, `startCommand`에 bootstrap + Streamlit 직렬 실행
   - MCP 서버는 Streamlit 프로세스 내부 stdio subprocess로 기동
2. **PostgreSQL** (Railway 애드온)
   - 참조 변수로 메인 컨테이너와 연결
   - 동일 프로젝트 내부망 통신

**Bootstrap 패턴**: 컨테이너 시작 시 `scripts/railway_bootstrap.py`가
3-phase idempotent 마이그레이션 수행 후 Streamlit 기동.

**비밀 관리**: Railway Variables만 사용. `.env` 파일은 git ignore.

---

## Considered Options

### Option A: Railway 단일 프로젝트 + 2개 서비스 ✅

- 구성: 메인 컨테이너(Streamlit+MCP) + PostgreSQL 애드온
- 장점:
  - Railway는 PostgreSQL 애드온을 **참조 변수(reference variables)** 로
    자동 주입 → 수동 DSN 조립 불필요
  - 같은 프로젝트 내부망 통신 → 외부 TCP 노출 없음
  - 단일 대시보드에서 두 서비스 로그·메트릭 관찰
  - NIXPACKS가 `pyproject.toml` 자동 인식 → Dockerfile 불필요
- 단점:
  - Railway lock-in (다만 Procfile 유지로 Render/Fly.io 이전 경로 확보)
  - Railway 무료 크레딧($5/월) 초과 시 유료 전환

### Option B: Render Web Service + Render PostgreSQL

- 구성: Option A와 동일하나 Render 플랫폼
- 장점: Railway와 유사. 커뮤니티 규모 비슷
- 단점:
  - 무료 티어에서 **15분 idle 후 cold start** → 면접관 접속 시 30~60초
    지연. 라이브 데모 품질 저하
  - PostgreSQL 무료 인스턴스 **90일 후 자동 삭제** → 운영 리스크
  - Railway 대비 startCommand 유연성 낮음

### Option C: Fly.io + Supabase

- 구성: Streamlit은 Fly.io, PostgreSQL은 Supabase 관리형
- 장점: 지역 선택권, Supabase 대시보드 품질
- 단점:
  - **2개 플랫폼 관리 overhead** — ADR-002·003 "단일 책임 경계" 철학 위배
  - Supabase 무료 1GB 제한 vs 합성 데이터 용량 여유 필요
  - Fly.io 설정이 docker-based → 현재 Python 네이티브 구성 대비 추가 작업

### Option D: AWS ECS + RDS

- 구성: 프로덕션 표준 구성
- 장점: 실 운영 수준 관찰성·확장성
- 단점:
  - **설정 4시간 초과 확실시** — 9일 타임박스에 비현실적
  - 월 비용 $50+ → 포트폴리오 운영에 과도
  - IAM·VPC·보안그룹 설정이 PoC 복잡도를 초과

### Option E: Streamlit Cloud + 외부 PostgreSQL

- 구성: Streamlit Cloud(무료) + 외부 DB
- 장점: Streamlit 공식 호스팅, 배포 가장 간단
- 단점:
  - **subprocess 실행 제약** — MCP stdio 서브프로세스 기동 가능 여부 미확인
  - 외부 DB 왕복 latency → 3-Agent 루프의 tool 호출 지연 누적
  - PostgreSQL 설정이 별도 플랫폼 → Option C 단점과 동일

---

## Rationale

### 1. ADR-001~003 철학 연속성

| ADR | 철학 | 본 ADR 적용 |
|---|---|---|
| 001 | 합성 데이터로 통제·재현성 우선 | bootstrap이 동일 seed로 재현성 보장 |
| 002 | 공식 MCP SDK 단일 의존성 | MCP 서버를 같은 컨테이너 stdio subprocess로 유지 |
| 003 | 순수 Python 오케스트레이션 | 별도 워커·큐 도입 없이 단일 프로세스 유지 |

Option A만 이 연속성을 깨지 않는다. Option C는 플랫폼 2개,
Option D는 의존성 폭증.

### 2. MCP stdio transport가 강제하는 공동 배포

MCP stdio는 **부모 프로세스와 자식 프로세스 간 통신**. 즉 Streamlit과
MCP 서버는 **같은 컨테이너에 공존해야** 한다. 이는:

- Option A·B에 자연스럽게 맞음 (단일 컨테이너)
- Option E에서 불확실 (subprocess 제약 불명)
- HTTP transport로 바꾸면 해결되나 ADR-002 기본 선택인 stdio를
  프로덕션용으로 변경해야 함 → 추가 ADR 필요

### 3. Bootstrap 패턴의 idempotency

`scripts/railway_bootstrap.py`는 3-phase로 구성:

1. **Schema 적용**: `policies` 테이블 존재 시 skip, 없으면 `001_init.sql`
2. **PII 레이어**: `002_pii.sql` 항상 재적용 (`CREATE OR REPLACE VIEW`,
   `DROP ROLE IF EXISTS`로 자체 idempotent)
3. **Seed 로드**: `policies` 행수 > 0이면 skip, 아니면 `data.seed.load.main()`

**재시작·재배포 시에도 안전**. Railway의 `restartPolicyType = ON_FAILURE`
정책과 정합.

이 패턴은 **수동 마이그레이션 관리 불필요**를 뜻한다. `alembic` 같은
마이그레이션 프레임워크 없이도 재현성을 보장한다 (ADR-001·002의 의존성
최소화 연속).

### 4. 3층 방어의 네트워크 레이어 검증 기회

공개 URL은 오히려 **거버넌스 실증 기회**:

- 면접관이 *"고객 전화번호 뽑아줘"* 질의 → Layer 3 하드 블록 실시간 작동
- 임의의 SQL injection 시도 → Layer 1 SQL Guard 차단
- 직접 DB 접근 시도 가능성 0 (Railway 내부망, 외부 포트 미노출)

로컬 시연으로는 이 검증이 *"나만 본 거 아니냐"* 의심을 부를 수 있다.
공개 URL은 **3층 방어를 외부 실사 환경에 노출**하여 서사를 강화한다.

### 5. 비용 현실성

| 항목 | 예상 월 비용 |
|---|---|
| Railway 무료 크레딧 | -$5 |
| Streamlit + PostgreSQL 인스턴스 | $10~15 |
| Anthropic API (월 한도로 관리) | 별도 |
| **실 부담** | $5~10 |

면접 프로세스 1~2개월 운영 = $10~20. 포트폴리오 비용으로 수용 가능.

---

## Consequences

### 긍정적 결과

- **이력서에 라이브 URL 첨부 가능** → 1차 심사 통과율 상승 기대
- 3층 방어 실사 환경 노출 → 면접 서사 실증 강화
- Railway 단일 대시보드로 배포·로그·DB 관리 통합
- Bootstrap idempotency로 무중단 재배포 가능
- 환경변수 기반 `SURI_*_MODEL` 스위치로 모델 교체 시 재빌드 불필요
  (ADR-003 Amendment 연계)

### 트레이드오프

- **Railway lock-in**: 배포 설정이 `railway.toml`에 결합. 이전 시
  `Procfile`과 순수 `startCommand`만 재사용 가능, 참조 변수 주입은
  플랫폼별 재설정 필요
- **단일 컨테이너 한계**: Streamlit과 MCP subprocess가 같은 메모리 공간.
  동시 접속자 증가 시 **순차 처리** (3-Agent 루프 중 다른 사용자 대기)
- **세션 상태 휘발성**: `st.session_state`는 컨테이너 재시작 시 손실.
  멀티턴 대화 복원 불가 (PoC 수용 범위)
- **관찰성 공백**: 로그는 Railway stdout만. APM·분산 추적 없음

### 운영 고려사항

#### 재배포

```
git push origin main → Railway 자동 빌드 → bootstrap → Streamlit 기동
```

Bootstrap 3-phase가 전부 idempotent이므로 배포 중 다운타임은 컨테이너
재시작 시간(~30~60초)만 발생.

#### 비밀 관리

- `ANTHROPIC_API_KEY`: Railway Variables
- `POSTGRES_*`: Railway PostgreSQL 애드온 참조 변수로 자동 주입
- `POSTGRES_READONLY_PASSWORD`: Railway Variables에 별도 설정
  (32자 랜덤, git에 저장 안 함)
- 로컬 개발용 `.env`는 git ignore, `.env.example`만 커밋

#### 로그 관찰

- Bootstrap 3-phase 로그는 Railway 서비스 로그에서 즉시 확인 가능
  (`flush=True` 적용)
- Streamlit 자체 로그 + MCP subprocess stderr 로그 모두 stdout으로 수집

#### 악성 트래픽 대응

- Anthropic 콘솔 월 한도 설정으로 API 비용 폭주 방어
- 3층 PII 방어는 **모든 사용자에게 동일 적용**
- Streamlit 자체 rate limiting 없음 (PoC 스코프 밖) — 프로덕션 이관 시
  CloudFlare 또는 Railway 앞단 reverse proxy 필요

---

## Migration Path (프로덕션 이관)

사내 배포 시 필요한 변경:

### 1. 플랫폼 교체 (사내 인프라)

- Railway → 사내 Kubernetes 또는 AWS ECS
- `railway.toml`은 폐기, `Procfile` 또는 신규 `Dockerfile` 작성
- Bootstrap 스크립트는 그대로 재사용 (psycopg 기반이라 이식성 높음)

### 2. MCP transport 전환

- stdio → HTTP/SSE transport
- 근거: 사내 환경에서 MCP 서버를 **별도 서비스**로 운영하는 것이
  관찰성·스케일링 면에서 유리
- 구현: `mcp.server.fastmcp.FastMCP`의 `run(transport="http")` 옵션
  (공식 SDK 지원)

### 3. PostgreSQL 이관

- 사내 DB로 이관 시 bootstrap의 Phase 1·2는 DBA 수동 수행이 표준
- Phase 3 seed 로드는 **프로덕션에서 실행 안 함** (실데이터 대상으로 변경)
- `DATABASE_URL` 환경변수만 교체

### 4. 비밀 관리 이관

- Railway Variables → 사내 Vault / AWS Secrets Manager / Azure Key Vault
- 코드 변경 없음 (env 읽기 방식 동일)

### 5. 관찰성 추가

- OpenTelemetry 도입 (ADR-003 운영 고려사항에서 이미 예고)
- Streamlit·MCP·PostgreSQL 3-layer tracing
- 에러 알람: 자가교정 실패율·GuardViolation 빈도 모니터링

### 6. 인증·권한

- 현재 공개 URL → 사내 SSO(SAML/OIDC) 연동
- 사용자별 `suri_readonly` 롤 분리 또는 row-level security 적용

---

## 면접 방어 답변

### Q: Railway 왜 선택했나요?

"세 가지 이유입니다. 첫째, MCP stdio transport가 Streamlit과 MCP 서버를
**같은 컨테이너에 배치**해야 작동하는데 Railway는 단일 컨테이너 구성이
가장 자연스러웠습니다. 둘째, PostgreSQL 애드온과 **참조 변수 자동 주입**
으로 DSN 조립 없이 연결됐습니다. 셋째, 9일 타임박스에서 AWS ECS나
Kubernetes는 비현실적이었고 Render는 무료 티어 cold start + PostgreSQL
90일 삭제 제약이 있어서 Railway가 유일하게 모든 제약을 만족했습니다.
프로덕션 이관 시엔 사내 Kubernetes로 넘기고 MCP transport를 stdio에서
HTTP으로 바꾸는 Migration Path를 ADR-005에 명시했습니다."

### Q: Bootstrap 패턴 왜 수동으로 짰나요? Alembic 안 써요?

"네 가지 판단이었습니다. 첫째, SURI는 스키마 진화가 없는 PoC라 마이그레이션
이력 관리 필요가 낮습니다. 둘째, Alembic은 SQLAlchemy 의존성을 끌어옵니다
— ADR-001~003의 의존성 최소화 철학과 충돌합니다. 셋째, bootstrap의 3-phase
가 전부 idempotent라서 프레임워크 없이도 재배포 안전성이 확보됩니다.
넷째, 사내 이관 시 **Phase 1·2는 DBA가 수동 수행**하는 것이 금융권 표준이라
Alembic이 오히려 걸림돌이 됩니다. 규모 커지면 Alembic 도입 경로는 열어둔
상태입니다."

### Q: 공개 URL인데 악성 쿼리 어떻게 방어하나요?

"세 층이 전부 공개 URL에서도 동일하게 작동합니다. **Layer 1**인 SQL Guard는
sqlglot AST로 SELECT 외 구문 전부 차단하고, `customers` 원본 테이블 접근도
블록합니다. **Layer 2**인 `suri_readonly` ROLE은 DB 레벨에서 SELECT 외 권한
자체가 없습니다 — Guard를 뚫어도 DB가 막습니다. **Layer 3**는 `customers_safe`
VIEW로 PII 컬럼(이름·주민번호·전화·이메일·주소)을 스키마 레벨에서 제거합니다.
공개 URL은 오히려 이 3층이 **실사 환경에서도 작동함을 증명하는 기회**입니다.
면접 시 직접 '고객 전화번호 뽑아줘' 질의로 Layer 3 하드 블록을 체험하시도록
설계했습니다."

### Q: 비용 폭주 리스크 없나요?

"두 가지로 방어합니다. 첫째, **Anthropic 콘솔 월 한도** 설정으로 API 비용
상한을 걸어뒀습니다. 초과 시 자동 중단되어 폭주 차단. 둘째, Railway 인프라는
무료 크레딧 $5/월 + 실 사용 $10~15 범위로 **면접 프로세스 1~2개월 총 $10~20**
수준입니다. 포트폴리오 운영 비용으로 수용 가능합니다. Rate limiting 미구현은
PoC 스코프 밖으로 판단했고, 사내 이관 시 CloudFlare나 reverse proxy로 추가
방어하는 경로는 Migration Path에 포함했습니다."

### Q: Cold start 문제는요?

"Railway는 Render와 달리 **idle sleep이 없습니다** — 무료 크레딧 범위 내에서
컨테이너가 상시 실행됩니다. 첫 접속 시 ~5~15초 지연은 Streamlit 초기 렌더링
때문이고, 2번째 접속부터는 즉시 응답합니다. 대신 **Agent 실행당 60~100초**가
Anthropic API 호출 대기 시간인데, 이건 UI 실시간 진행 표시(3단계 status + tool
호출 타임라인)로 체감 개선을 처리했습니다. 대기 시간이 블랙박스가 아니라
**Agent의 사고 과정을 노출**하는 포맷으로 바꾼 거죠."

---

## 관련 파일

- `railway.toml` — 빌드·실행 설정
- `Procfile` — 플랫폼 이식성 보존 (현재는 railway.toml이 우선)
- `scripts/railway_bootstrap.py` — 3-phase idempotent 마이그레이션
- `docker-compose.yml` — 로컬 개발 환경 (Railway 배포에는 미사용)
- `.env.example` — 환경변수 템플릿
- `pyproject.toml` — 의존성 선언

## References

- Railway Docs: https://docs.railway.app/
- Railway Reference Variables: https://docs.railway.app/guides/variables
- MCP stdio transport: https://github.com/modelcontextprotocol/python-sdk
- ADR-001: 합성 데이터 (bootstrap seed 호출 근거)
- ADR-002: MCP SDK (stdio subprocess 배치 근거)
- ADR-003: Agent Framework (+ Amendment 모델 스위치와 재배포 정합성)
- ADR-004: Domain Glossary (`.yaml` 파일 컨테이너 포함 처리)
- Live URL: https://suri-production-89db.up.railway.app
