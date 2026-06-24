"""
AI Evaluation Gate — blocks deployment if output quality regresses.

Run: python tests/evals/run_evals.py
Exit 0 = all pass. Exit 1 = one or more fail.
"""
import asyncio
import json
import sys
import time
from pathlib import Path

from app.modules.need_analyzer import analyze_client_needs
from app.db.postgres import AsyncSessionLocal


async def run_need_analyzer_evals() -> bool:
    golden = Path("tests/evals/golden/need_analyzer.jsonl")
    passed = failed = 0

    async with AsyncSessionLocal() as db:
        for line in golden.read_text().strip().splitlines():
            case = json.loads(line)
            start = time.monotonic()
            output = await analyze_client_needs(db, case["input"])
            elapsed_ms = int((time.monotonic() - start) * 1000)

            lower = output.lower()
            ok = True

            for phrase in case.get("must_contain", []):
                if phrase.lower() not in lower:
                    print(f"  FAIL [{case['input']['name']}] missing: '{phrase}'")
                    ok = False

            for phrase in case.get("must_not_contain", []):
                if phrase.lower() in lower:
                    print(f"  FAIL [{case['input']['name']}] prohibited: '{phrase}'")
                    ok = False

            if elapsed_ms > 5000:
                print(f"  FAIL [{case['input']['name']}] too slow: {elapsed_ms}ms (limit 5000ms)")
                ok = False

            if ok:
                passed += 1
                print(f"  PASS [{case['input']['name']}] {elapsed_ms}ms")
            else:
                failed += 1

    print(f"\nNeed Analyzer Evals: {passed} passed, {failed} failed")
    return failed == 0


async def main():
    print("=== Running AI Evaluation Gate ===\n")
    results = [
        await run_need_analyzer_evals(),
    ]
    all_pass = all(results)
    print("\n" + ("ALL EVALS PASSED" if all_pass else "EVAL GATE FAILED — blocking deployment"))
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    asyncio.run(main())
