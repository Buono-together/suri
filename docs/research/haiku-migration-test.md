# Haiku 4.5 이관 실측 테스트 (Planner/Critic)

**일자**: 2026-04-24 (D-5)
**대상**: `claude-haiku-4-5-20251001`
**대조**: `claude-sonnet-4-6` (현재 전 Agent 기본)
**Executor는 Sonnet 유지** (ADR-003 원칙)

환경변수 스위치:
```
SURI_PLANNER_MODEL=claude-haiku-4-5-20251001
SURI_CRITIC_MODEL=claude-haiku-4-5-20251001
# SURI_EXECUTOR_MODEL 미설정 → 기본 Sonnet
```

---

## 1. Core 8 회귀 (no-cache)

| ID | Sonnet | Haiku | Δ latency |
|---|---|---|---|
| C1 | ✓ 72.5s | ✓ 64.1s | -8.4s |
| C2 | ✓ 51.3s | ✓ 53.7s | +2.4s |
| C3 | ✓ 72.5s | ✓ 69.9s | -2.6s |
| C4 | ✓ 37.8s | **✗ 29.1s** | -8.7s |
| C5 | ✓ 34.6s | ✓ 20.8s | -13.8s |
| C6 | ✓ 65.1s | ✓ 49.6s | -15.5s |
| C7 | ✓ 114.9s | ✓ 72.4s | -42.5s |
| C8 | ✓ 48.8s | ✓ 29.3s | -19.5s |
| **합** | **8/8 · 497.5s** | **7/8 · 388.8s** | **-22% 시간** |

**C4 실패 원인** — Haiku Critic 답변에 assertion 키워드(`customers_safe` · `PII 거버넌스` · `뷰를 통해`) 부재. 답변 내용 자체는 정확하나 **거버넌스 경로 투명성 서술**을 생략.

Haiku C4 답변 발췌:
> "30대 남성 고객이 가장 많이 가입한 상품 유형은 **보장성(2,897건)**이며…"

Sonnet 기준 답변은 "customers_safe 뷰를 통해 조회했습니다" 전제를 먼저 밝힘 → Haiku가 일반 사용자향 요약에 더 치중해 거버넌스 전제 생략.

---

## 2. C1 재현성 (Haiku × 3, no-cache)

| Run | 낙차 1위 | GA 낙차 | GA 13회차 | GA 25회차 | latency | 업계 범위 |
|---|---|---|---|---|---|---|
| 1 | GA | 7.89%p | 79.02% | 71.13% | 46.3s | ⚠️ 하단 |
| 2 | GA | 7.89%p | 79.02% | 71.13% | 60.8s | ⚠️ 하단 |
| 3 | GA | 7.89%p | 79.02% | 71.13% | 52.7s | ⚠️ 하단 |

**Sonnet 6회 비교** (docs/known-limitations.md §2.1):

| 항목 | Sonnet 6회 | Haiku 3회 |
|---|---|---|
| GA 낙차 1위 재현 | 6/6 (100%) | 3/3 (100%) |
| GA 25회차 유지율 | 71.13~71.35% (5/6) | 71.13% (3/3) |
| GA 13회차 유지율 | 89.23% (5/6) / 79.02% (1/6) | 79.02% (3/3) |
| 낙차 절대값 | 1.07 ~ 18.10%p (넓은 편차) | 7.89%p (완전 수렴) |
| 업계 범위 ≥15%p | 3/6 | 0/3 |

**해석**:
- Haiku는 **더 결정적**. 3회 모두 동일 결과 수렴.
- 다만 **동일한 "strict cohort" 해석**으로 쏠림 → Sonnet이 여러 경로(Run 3·4·5=이상적 / 6=strict)로 분산하던 해석 폭이 사라짐.
- 즉, Haiku는 **13회차 분모를 더 엄격하게 정의**하는 SQL 패턴을 일관되게 선택. 결과적으로 13회차 수치가 낮고 낙차가 업계 범위 하단에 위치.
- 결정성 ↑, 해석 다양성 ↓ 의 트레이드오프.

---

## 3. Scene 3 멀티턴 (Haiku, no-cache)

```
T1 "판매채널별 25회차 유지율 어때?"
  intent: Compare 25-month retention rates across all sales channels
  filters: [sufficient aging, exclude unknown channel]

T2 "응, GA 중에서도 어떤 상품이 제일 심해?"
  intent: GA 채널 내에서 25회차 유지율이 가장 낮은 상품 식별
  filters: ["channel = GA", "policy milestone = 25 months"]
  → [OK] T2 GA 맥락 반영 확인

T3 "그 상품 언제 많이 팔렸는지 계절성도 봐줘"
  intent: GA 채널에서 판매된 행복연금Plus 상품의 발행 시점별 계절성 분석
  filters: ["channel = GA", "product = 행복연금Plus", "product type = 저축성"]
  → [OK] T3 상품 맥락 포함 확인
```

**판정**: **Planner의 history 기반 맥락 유지 능력이 Sonnet 동등**. T2 에서 GA, T3 에서 행복연금Plus(P004) 상품을 intent/filters 에 정확히 반영.

---

## 4. 종합 판정

| 기준 | 결과 |
|---|---|
| Core 8 PASS | 7/8 (C4 FAIL — Critic 거버넌스 전제 서술 누락) |
| Scene 3 맥락 유지 | ✓ T2·T3 모두 정상 |
| C1 재현성 | ✓ 3/3 동일 결과 (Sonnet 대비 결정성 향상) |
| Executor 동작 | ✓ Sonnet 유지 확인 (SURI_EXECUTOR_MODEL 미설정) |
| 총 latency | **-22%** (497.5s → 388.8s) |

### 사용자 판단 기준 대비

- ✓ `이관 권장` 조건: 8/8 PASS 유지 + Scene 3 정상 + C1 재현성 동등  →  **미달 (C4 FAIL)**
- ✓ `이관 보류` 조건: 7/8 이하 또는 Planner 간헐 실패  →  **해당 (7/8)**
- ✗ `이관 비추` 조건: 6/8 이하 또는 Scene 3 맥락 상실  →  해당 안 함

### 권고

> **조건부 이관 권장**: C4 실패가 Critic 프롬프트 1줄 보강(`고객 관련 질문 시 'customers_safe 뷰를 통해…' 전제 명시 필수`)으로 해결 가능해 보이고, 나머지 지표(latency -22%, C1 재현성 향상, Scene 3 정상)는 모두 우호적. 프롬프트 보강 1회 후 Core 8 재측정하여 8/8 회복되면 이관 확정, 미회복 시 보류.

### 결정 포인트가 될 수 있는 트레이드오프

1. **결정성 vs 해석 다양성**: Haiku는 C1 에서 매번 같은 SQL 구조로 수렴하므로 재현성은 좋지만, Sonnet 이 가끔 18%p 같은 더 "업계 벤치마크 근접" 답을 뽑던 경로가 사라짐. 면접 시연에서 "같은 질문 여러 번 실행"을 보여준다면 Haiku 쪽이 안정적.
2. **답변 간결성 vs 거버넌스 투명성**: Haiku Critic 은 답변을 더 짧고 비즈니스 지향으로 작성 → C4 같은 "거버넌스 경로 서술" assertion 에 취약. 명시적 프롬프트 지시가 없으면 생략 경향.

---

## 5. 측정 로그 경로

- Core 8: `.tmp/haiku-test/core8.log`
- C1 × 3: `.tmp/haiku-test/c1-reps.log`
- Scene 3: `.tmp/haiku-test/scene3.log`
