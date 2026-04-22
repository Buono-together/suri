먼저 결론부터 말하면, **이번 SURI PoC는 fastmcp로 가도 충분히 괜찮고(Go), 약간의 “공식 SDK 이해”를 곁들이는 전략이 베스트**입니다. [github](https://github.com/modelcontextprotocol/python-sdk)

***

## 1. 금융권/대기업 면접 컨텍스트

**공식 vs 래퍼가 “절대 선악”은 아닙니다.** 금융권이 보는 포인트는 보통:

- “공식 SDK 쓸 줄 안다, 스펙 이해했다”는 신호  
  → Anthropic 공식 Python SDK는 MCP 기준 구현체이고, 문서/예시도 여기에 기반합니다. [hellogithub](https://hellogithub.com/en/repository/7c8c265fdfad4269bafa68ba4172860b)
  → “MCP primitive가 뭔지, list_tools / call_tool / resources가 어떻게 생겼는지 설명할 수 있느냐”가 중요하지, `@server.list_tools()`를 직접 쳤냐는 덜 중요합니다. [youtube](https://www.youtube.com/watch?v=oq3dkNm51qc)
- “생산성 vs 안정성 트레이드오프를 의식적으로 선택했는가”  
  → 금융권도 내외부 오픈소스 적극 활용 기조입니다. 금융위도 오픈소스 AI·도구 활용을 명시적으로 지원하겠다고 발표했습니다. [fsc.go](https://www.fsc.go.kr/no010101/83594?srchCtgry=&curPage=1&srchKey=&srchText=&srchBeginDt=&srchEndDt=)
  → “코어는 공식 SDK를 이해하고, 빠른 구현엔 래퍼를 썼다”는 이야기는 오히려 **합리적 엔지니어링 결정**으로 들립니다.

**감점 포인트가 될 수 있는 경우**는 딱 하나:

- “fastmcp가 Anthropic 공식 SDK 위에서 도는지, MCP 스펙과 어떻게 연결되는지 모른다”  
  → 즉, 래퍼를 쓰면서 밑단을 전혀 이해하지 못한 상태로 보이면 감점입니다.

**요약:**  
- “공식만이 정답”이라는 분위기는 아니고,  
- **“공식 primitive 이해 + 래퍼 활용”을 설명할 수 있으면 오히려 플러스** 쪽입니다. [github](https://github.com/modelcontextprotocol/python-sdk)

***

## 2. 프로덕션 이관 가능성

**라이선스 관점에서:**  
- Anthropic MCP Python SDK: MIT 계열 허용적 라이선스. [hellogithub](https://hellogithub.com/en/repository/7c8c265fdfad4269bafa68ba4172860b)
- fastmcp: Apache 2.0, 역시 대기업·금융권에서 많이 허용하는 라이선스입니다. [github](https://github.com/AI-App/JLowin.FastMCP)

국내 금융사 오픈소스 관리 사례에서도, MIT/BSD/Apache 2.0은 일반적으로 **“사용 가능”**으로 취급되는 축이고, 문제는 대부분 GPL/LGPL 계열입니다. [nx006.tistory](https://nx006.tistory.com/26)

따라서:

- “Apache 2.0 래퍼 의존성” 자체는 라이선스 레벨에선 큰 이슈가 아닐 가능성이 높습니다.
- 다만, **실제 이관 시**에는:
  - 사내 오픈소스 심사 프로세스가 있어서 `requirements.txt` 내 의존성을 모두 검토해야 하고,  
  - fastmcp가 독립 프로젝트인 만큼, “내부 표준 프레임워크”로 삼기엔 논의가 필요할 겁니다.

**PoC용으로는**  
- “프로덕션 이관 시에는 공식 SDK로 리팩토링해도 구조가 크게 달라지지 않도록 작성했다”라고 말할 수 있으면 충분합니다.

***

## 3. 장기 유지보수 리스크

**fastmcp:**

- 초기에 1인 프로젝트로 출발했지만, 최근 버전은 PrefectHQ로 이동(3.x)하는 등 커뮤니티·회사 지원이 붙고 있습니다. [jlowin](https://jlowin.dev/blog/fastmcp-3-launch)
- 그래도 “공식 벤더가 유지하는 SDK”보다는 의존 리스크가 큰 건 사실입니다.  
  예: 버전 업이 느려진다, MCP 스펙 변경에 따라가지 못한다 등의 우려.

**공식 MCP Python SDK:**

- MCP Python 공식 라이브러리로, MCP spec 변경·확장에 가장 빨리 대응합니다. [github](https://github.com/modelcontextprotocol/python-sdk)
- 서버/클라이언트 양쪽을 제공하고 있고, 문서/튜토리얼도 공식 예시를 기준으로 합니다. [youtube](https://www.youtube.com/watch?v=oq3dkNm51qc)

**SURI 이후 재사용 관점:**

- “장기적으로 사내 표준 MCP 라이브러리로 쓰겠다”면 공식 SDK가 낫습니다.
- 하지만 이번 SURI는 **개인 포트폴리오용 PoC**이고, 실제 한화생명 내에서 MCP 서버를 운영할 때는 어차피 기존 사내 프레임워크·정책이 개입될 가능성이 높습니다.

**합리한 플랜:**  
- 지금 PoC: fastmcp 사용  
- 문서/README: “사내 이관 시 공식 MCP SDK 기반 구현도 경험/이해하고 있으며, 필요한 경우 fastmcp 없이도 같은 기능을 구현할 수 있다” 명시

***

## 4. MCP 스펙 변경 대응력

MCP 자체가 아직 빠르게 진화 중이고, 공식 Python SDK는 MCP 스펙에 맞춰 활발히 업데이트되고 있습니다. [youtube](https://www.youtube.com/watch?v=oq3dkNm51qc)

- **공식 SDK:**
  - MCP primitive, tool/resource/prompt 등의 변경이 있으면 가장 먼저 반영됩니다. [hellogithub](https://hellogithub.com/en/repository/7c8c265fdfad4269bafa68ba4172860b)
  - 마이그레이션 가이드도 공식 문서에 포함됩니다. [github](https://github.com/modelcontextprotocol/python-sdk)
- **fastmcp:**
  - 공식 SDK 위 thin wrapper라, SDK 버전만 올리면 되는 부분이 많지만,
  - 새로운 primitive나 확장 기능이 생기면 fastmcp 레벨에서 추가 작업이 필요할 수 있습니다. [github](https://github.com/itaru2622/jlowin-fastmcp)

**포트폴리오로 6~12개월 재사용 관점:**

- re-run 가능한 코드/데모를 1년 정도 유지하고 싶다면:
  - fastmcp만 쓰기보다는, **최소한 한 개 파일에서 “공식 SDK로도 같은 기능을 구현했다” 예시를 갖고 있으면** 안정적입니다.
  - README에 MCP spec 버전, 공식 SDK 버전, fastmcp 버전을 명시해 두면 나중에 설명할 때 좋습니다. [hellogithub](https://hellogithub.com/en/repository/7c8c265fdfad4269bafa68ba4172860b)

***

## 5. 디버깅·운영 투명성

금융권에서 중요하게 보는 건 “장애 시 책임 추적 가능성 = 내부에서 이해 가능한 코드인가?” 입니다.

- **공식 SDK 직접 사용:**
  - 호출 스택·로그에서 바로 `modelcontextprotocol` 쪽 API가 드러나며, 공식 문서와 1:1로 대응됩니다. [github](https://github.com/modelcontextprotocol/python-sdk)
  - “특정 tool 호출 시 JSON schema 검증 실패” 같은 문제를 공식 doc 보고 그대로 따라가며 디버깅하기 쉽습니다. [youtube](https://www.youtube.com/watch?v=oq3dkNm51qc)

- **fastmcp:**
  - 장점: tool 정의와 타입 검증이 단순해져서, 애초에 버그가 줄어듭니다. [github](https://github.com/AI-App/JLowin.FastMCP)
  - 단점: 문제가 발생했을 때, fastmcp 내부 구현과 공식 SDK 간의 매핑을 한 번 더 따라가야 합니다.

다만 SURI PoC는:

- MCP 서버는 사실상 **read-only SQL 실행 tool 1~3개**가 전부라, 디버깅 난이도가 크게 차이나는 상황이 아닙니다.
- 오히려 fastmcp의 자동 schema 생성, 간편 로깅(ctx.info 등)이 개발 속도를 높이고, PoC 디버깅엔 더 유리할 수 있습니다. [github](https://github.com/AI-App/JLowin.FastMCP)

***

## 6. 이 PoC(SURI)에서의 실용적 판단

상황 요약:

- Tool 1~3개
- 이미 3층 방어 구조·데이터·거버넌스 구현이 핵심 강점
- D-7, 9일 타임박스 PoC
- Reviewer는 “MCP를 쓸 줄 알고, 금융권 거버넌스를 어떻게 가져왔나”에 관심

**여기서는 fastmcp가 ROI 상 유리**합니다. [jlowin](https://jlowin.dev/blog/fastmcp-3-launch)

- Tool 정의에 시간을 덜 쓰고,  
  - SQL AST 파싱  
  - DB ROLE·schema 권한 분리  
  - 에이전트 프롬프트·Critic 로직  
  에 더 시간을 쓸 수 있습니다.
- 면접에서 “공식 SDK도 이해하고 있지만, PoC 생산성을 위해 fastmcp를 thin wrapper로 사용했다”고 설명하면 **합리적인 공학적 선택**으로 보입니다. [github](https://github.com/AI-App/JLowin.FastMCP)

***

## 최종 권장 옵션 & 이유

**권장:** **옵션 B — fastmcp 유지 (Go, 단 README/설명에 공식 SDK 이해를 명시)**

**근거 3줄**

1. 이번 PoC의 핵심 가치는 MCP 자체보다 **PII 거버넌스와 3-Agent/3층 방어 구조**에 있으므로, Tool 정의 생산성을 극대화하는 fastmcp가 더 큰 ROI를 줍니다. [jlowin](https://jlowin.dev/blog/fastmcp-3-launch)
2. fastmcp는 공식 MCP Python SDK 위에서 동작하는 Apache 2.0 허용 라이선스 프로젝트로, 금융권에서도 일반적으로 허용되는 라이선스 스펙입니다. [tuxcare](https://tuxcare.com/ko/blog/open-source-licensing-explained/)
3. 면접에서 “공식 SDK primitives를 이해한 상태에서, PoC 속도를 위해 래퍼를 썼다”는 설명은 오히려 **의식적인 트레이드오프 설계**로 긍정 평가 받을 가능성이 큽니다. [fsc.go](https://www.fsc.go.kr/no010101/83594?srchCtgry=&curPage=1&srchKey=&srchText=&srchBeginDt=&srchEndDt=)

***

## 면접용 답변 템플릿

### Q1. 왜 fastmcp를 선택했나요?

> “MCP 서버는 Anthropic 공식 Python SDK 위에서 동작하는 `fastmcp`를 사용했습니다. 공식 SDK의 `list_tools`, `call_tool` 구조와 JSON Schema 기반 정의는 이해하고 있지만, 이번 PoC에서는 read-only SQL tool을 1~3개 빠르게 구현하는 게 중요해서, 타입 힌트에서 schema를 자동 생성해주는 래퍼를 선택했습니다. 나중에 사내 이관이 필요하면 동일한 인터페이스를 공식 SDK로 옮기더라도 구조가 크게 달라지지 않도록, tool 시그니처와 권한 모델은 가능한 한 MCP primitive에 가깝게 설계했습니다.” [github](https://github.com/AI-App/JLowin.FastMCP)

### Q2. 공식 SDK를 써보신 적은 있나요?

> “네. 공식 MCP Python SDK로도 간단한 예제 서버를 만들어서 `@server.list_tools() / @server.call_tool()` 수준의 primitive는 직접 구현해봤습니다. 이번 SURI에서는 PoC 타임라인 때문에 공식 SDK를 thin wrapper처럼 감싸는 fastmcp를 골랐고, MCP spec 자체와 tool/resource 개념은 공식 문서를 기준으로 이해하고 있습니다.” [youtube](https://www.youtube.com/watch?v=oq3dkNm51qc)

### Q3. 금융권/프로덕션 환경에서도 fastmcp를 쓰실 건가요?

> “프로덕션에서는 사내 오픈소스 정책과 표준 프레임워크를 먼저 확인할 것 같습니다. MCP는 프로토콜이고, 공식 SDK는 기준 구현이라 장기적으로는 공식 SDK나 사내 래퍼 위에서 MCP 서버를 표준화하는 것이 맞습니다. 이번 PoC 코드는 fastmcp에 강하게 결합하지 않고, 공식 SDK로도 쉽게 옮길 수 있는 구조로 작성해서, 추후 이관이나 재사용 시 리스크를 최소화했습니다.” [osbc.co](https://osbc.co.kr/data/file/newsletter/13.%EC%9D%B4%EC%A4%80%EC%88%98%20%EC%B0%A8%EC%9E%A5_%EA%B8%88%EC%9C%B5%EA%B6%8C%20%EC%98%A4%ED%94%88%EC%86%8C%EC%8A%A4%20%EA%B4%80%EB%A6%AC%EC%8B%9C%EC%8A%A4%ED%85%9C%20%EA%B5%AC%EC%B6%95%20%EC%82%AC%EB%A1%80%20(H%EC%82%AC).pdf)

***

## 현재 계획(fastmcp 선호)에 대한 평가

- **상태:** fastmcp 사용 계획
- **평가:** **Go (소폭 보완)**

보완하면 좋은 것:

1. **코드에 주석/README:**
   - “fastmcp는 MCP 공식 Python SDK 위 thin wrapper이며, MCP spec/공식 SDK 구조를 이해한 상태에서 생산성을 위해 선택했다” 명시. [github](https://github.com/modelcontextprotocol/python-sdk)
2. **아주 작은 샘플 파일이라도 공식 SDK 버전으로 하나 만들어두기:**
   - 예를 들어 `examples/official_mcp_sample.py` 같은 곳에, 동일 `execute_readonly_sql` tool을 공식 SDK로 최소 구현해두면, 면접에서 “둘 다 써봤다”를 코드로 증명할 수 있습니다. [hellogithub](https://hellogithub.com/en/repository/7c8c265fdfad4269bafa68ba4172860b)
3. **requirements 및 라이선스 정리:**
   - `requirements.txt`에 fastmcp와 공식 SDK 버전 명시,
   - README에 사용 라이선스(MIT/Apache 2.0) 짧게 정리하면 금융권 시점에서도 좋게 보입니다. [nx006.tistory](https://nx006.tistory.com/26)

이 정도면 **fastmcp를 중심으로 하되, 언제든 공식 SDK로 돌아설 수 있는 상태**라서, PoC·면접·장기 포트폴리오 세 축을 모두 만족하는 선택이라고 봅니다.