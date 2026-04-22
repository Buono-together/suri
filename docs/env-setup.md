# SURI 환경 변수 설정 가이드

## 개요

SURI는 PostgreSQL 자격증명과 Anthropic API 키를 `.env` 파일로 관리한다.
운영 이관 시에는 secret manager(AWS Secrets Manager, Vault 등)로 대체될
레이어이지만, PoC 단계에서는 로컬 `.env`로 단순화한다.

## 빠른 시작

```bash
cp .env.example .env
# .env를 열어서 ANTHROPIC_API_KEY만 본인 키로 교체
```

나머지 값들은 `docker-compose.yml`의 기본값과 일치하도록 미리 채워져 있어
로컬 개발에서는 수정이 필요 없다.

## 환경 변수 목록

### Anthropic

| 변수 | 용도 | 기본값 |
|---|---|---|
| `ANTHROPIC_API_KEY` | Planner/Executor/Critic의 LLM 호출 | 없음 (필수) |

### PostgreSQL — Admin (데이터 로딩용)

| 변수 | 용도 | 기본값 |
|---|---|---|
| `POSTGRES_HOST` | DB 호스트 | `localhost` |
| `POSTGRES_PORT` | DB 포트 | `5432` |
| `POSTGRES_DB` | DB 이름 | `suri` |
| `POSTGRES_USER` | Admin 계정 (스키마 생성·데이터 로드) | `suri_admin` |
| `POSTGRES_PASSWORD` | Admin 비밀번호 | `changeme` |

Admin 계정은 `data/seed/load.py` 실행 시에만 사용된다.
Agent 런타임은 **절대 Admin으로 접속하지 않는다**.

### PostgreSQL — Readonly (MCP 서버용, Layer 2 방어)

| 변수 | 용도 | 기본값 |
|---|---|---|
| `POSTGRES_READONLY_USER` | MCP 서버가 DB 접근 시 사용 | `suri_readonly` |
| `POSTGRES_READONLY_PASSWORD` | Readonly 비밀번호 | `readonly_pass` |

이 계정은 `data/schema/002_pii.sql`의 `CREATE ROLE suri_readonly WITH LOGIN 
PASSWORD 'readonly_pass'` 블록에서 생성된다. `.env`의 값과 SQL의 값이 
**반드시 일치**해야 MCP 서버가 기동된다.

## 3-Layer PII 방어에서 자격증명의 역할

Layer 2 (DB ROLE)이 작동하려면 MCP 서버가 admin이 아닌 **readonly** 계정으로
접속해야 한다. 코드 흐름:

```
MCP 서버 기동 (app/mcp_server/server.py)
  → FastMCP tool 호출 시
  → app/mcp_server/db.py의 execute_readonly_json()
  → readonly_connection() 컨텍스트 매니저
  → POSTGRES_READONLY_USER / POSTGRES_READONLY_PASSWORD 사용
  → SET TRANSACTION READ ONLY 추가 적용
```

`db.py`에는 두 변수가 없을 때를 대비한 fallback 기본값이 있다:

```python
f"user={os.getenv('POSTGRES_READONLY_USER', 'suri_readonly')} "
f"password={os.getenv('POSTGRES_READONLY_PASSWORD', 'readonly_pass')}"
```

이 fallback은 **로컬 편의용**이다. `.env.example`에는 두 변수가 명시되어 
있으니, `.env`에도 명시적으로 포함시킬 것. 추후 fallback을 제거하고 
변수 누락 시 즉시 실패하도록 전환할 예정이다.

## 보안 주의사항

### PoC 단계

- `readonly_pass` 같은 약한 비밀번호는 **PoC에서만 허용**된다.
- `.env`는 `.gitignore` 처리되어 git에 커밋되지 않는다.
- `data/schema/002_pii.sql`에는 `readonly_pass`가 평문으로 들어 있는데, 
  이 역시 PoC 용이며 운영에서는 SQL 파일 대신 secret manager를 거친 
  임시 세션으로 ROLE을 생성해야 한다.

### 운영 이관 시 바뀌는 것

| 레이어 | PoC | 운영 |
|---|---|---|
| API 키 | `.env` 평문 | AWS Secrets Manager / Vault |
| Admin 비밀번호 | `.env` 평문 | IAM DB 인증 or secret rotation |
| Readonly 비밀번호 | SQL 평문 | DDL은 CI/CD 파이프라인에서 secret 주입 |
| `.env` 파일 자체 | 로컬 | 없음 (컨테이너 런타임에 주입) |

상세 계획은 `docs/future-work.md` 또는 `docs/production-migration.md`
(작성 예정)을 참조.

## 문제 해결

### MCP 서버 기동 시 인증 실패

```
psycopg.OperationalError: connection failed: FATAL: password authentication 
failed for user "suri_readonly"
```

체크리스트:
1. `data/seed/load.py`가 성공적으로 실행되었는지 (002_pii.sql 자동 실행됨)
2. `.env`의 `POSTGRES_READONLY_PASSWORD`가 `002_pii.sql`의 `PASSWORD 
   'readonly_pass'`와 일치하는지
3. Docker 컨테이너가 실행 중인지: `docker compose ps`

### `.env.example`이 없다고 나올 때

레포 루트에 `.env.example` 파일이 있는지 확인:

```bash
ls -la .env.example
```

없으면 README의 "Run" 섹션 또는 이 문서 상단의 템플릿을 참조해 생성.
