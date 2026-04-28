"""
Scene 3 멀티턴 smoke test — T1 → T2 → T3 end-to-end.

목적: Planner가 이전 턴 맥락(채널·상품 등)을 intent·filters에 반영하는지
      육안 확인.

사용법:
    uv run python -m scripts.test_multiturn
    uv run python -m scripts.test_multiturn --no-cache
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time

from app.agents.orchestrator import run


SCENE_3 = [
    "판매채널별 25회차 유지율 어때?",
    "응, GA 중에서도 어떤 상품이 제일 심해?",
    "그 상품 언제 많이 팔렸는지 계절성도 봐줘",
]


def _extract_sql(result) -> str | None:
    """Executor가 실제 실행한 SQL을 tool_calls에서 추출."""
    for tc in result.tool_calls:
        if tc.name == "execute_readonly_sql" and not tc.is_error:
            return str(tc.input.get("query", ""))
    # 에러여도 마지막 시도 반환
    for tc in reversed(result.tool_calls):
        if tc.name == "execute_readonly_sql":
            return str(tc.input.get("query", ""))
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-cache", action="store_true",
                        help="Force fresh API calls")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.WARNING,
        format="[%(levelname)s %(name)s] %(message)s",
    )

    history: list[dict] = []
    failures: list[str] = []
    total_start = time.time()

    for i, question in enumerate(SCENE_3, 1):
        print("\n" + "▓" * 70)
        print(f"Turn {i}/{len(SCENE_3)}")
        print(f"질문: {question}")
        print(f"history turns passed: {len(history)}")
        print("▓" * 70)

        t0 = time.time()
        result = run(
            question,
            use_cache=not args.no_cache,
            history=history if history else None,
        )
        elapsed = time.time() - t0

        if result.plan is None:
            print(f"[FAIL] Planner returned None (error={result.error})")
            failures.append(f"T{i}: no plan")
            break

        print(f"\n⏱  {elapsed:.1f}s")
        print(f"📋 intent: {result.plan.intent}")
        print(f"📋 filters: {json.dumps(result.plan.filters, ensure_ascii=False)}")
        print(f"📋 tables_needed: {json.dumps(result.plan.tables_needed, ensure_ascii=False)}")

        sql = _extract_sql(result)
        if sql:
            print("📝 SQL (첫 400자):")
            print("    " + sql.replace("\n", "\n    ")[:400])

        print(f"\n💬 answer:\n{result.answer[:500]}")
        if len(result.answer) > 500:
            print(f"... (truncated, full {len(result.answer)} chars)")

        # 턴별 맥락 반영 체크 (육안 + 자동)
        intent_lower = result.plan.intent.lower()
        filters_joined = " ".join(result.plan.filters).lower()
        sql_lower = (sql or "").lower()
        combined = intent_lower + " " + filters_joined + " " + sql_lower

        if i == 2:
            # T2에서 GA 맥락이 intent/filters/SQL 어디에라도 나와야 함
            if "ga" not in combined:
                print("[WARN] T2에서 GA 맥락 미반영 (intent/filters/SQL 모두에 'ga' 없음)")
                failures.append("T2: GA 맥락 미반영")
            else:
                print("[OK] T2 GA 맥락 반영 확인")

        if i == 3 and len(history) >= 2:
            # T3는 T2에서 식별된 상품이 intent/filters에 포함되면 좋으나
            # 상품 ID는 T2 결과에 따라 가변이므로 "상품" 키워드 존재만 보수적으로 체크
            if "상품" not in intent_lower and "product" not in intent_lower:
                print("[WARN] T3 intent에서 상품 맥락 약함")
            else:
                print("[OK] T3 상품 맥락 포함 확인")

        if result.error:
            print(f"[FAIL] pipeline error: {result.error}")
            failures.append(f"T{i}: {result.error}")
            break

        # 다음 턴용 history 누적
        history.append({"question": question, "answer": result.answer})

    total = time.time() - total_start
    print("\n" + "=" * 70)
    print(f"total: {total:.1f}s · turns completed: {len(history)}/{len(SCENE_3)}")
    if failures:
        print("❌ failures:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("✅ multi-turn smoke test passed (육안 확인 필요)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
