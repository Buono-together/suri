"""
Test Agent's use of exploration tools (list_tables, describe_table).
"""
import logging
import json

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s %(name)s] %(message)s",
)

from app.agents.orchestrator import run


QUESTIONS = [
    # 1. 명시적 탐색
    "우리 DB에 어떤 테이블들이 있어?",
    
    # 2. 구조 질문
    "policies 테이블 구조 알려줘",
    
    # 3. 암시적 탐색 (Agent가 테이블 이름 모를 수 있음)
    "보험 계약 상태가 어떻게 분포되어 있어?",
]


def run_one(question: str, idx: int) -> None:
    print()
    print("▓" * 70)
    print(f"TEST {idx}: {question}")
    print("▓" * 70)
    
    result = run(question)
    
    print()
    print("─" * 70)
    print("FINAL ANSWER:")
    print("─" * 70)
    print(result.answer)
    
    if result.error:
        print(f"\nERROR: {result.error}")


for i, q in enumerate(QUESTIONS, 1):
    run_one(q, i)
