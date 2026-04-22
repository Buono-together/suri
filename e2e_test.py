import logging
import json

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s %(name)s] %(message)s",
)

from app.agents.orchestrator import run

print()
print("=" * 70)
print("SURI E2E TEST — 채널별 25회차 유지율")
print("=" * 70)
print()

result = run("채널별 25회차 유지율 보여줘")

print()
print("=" * 70)
print("FINAL ANSWER:")
print("=" * 70)
print(result.answer)

print()
print("=" * 70)
print("EXECUTION RESULT (rows):")
print("=" * 70)
if result.execution_result:
    print(json.dumps(result.execution_result, ensure_ascii=False, indent=2))

if result.error:
    print()
    print(f"ERROR: {result.error}")
