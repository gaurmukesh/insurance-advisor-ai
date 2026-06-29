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
from app.modules.product_recommender import recommend_products
from app.modules.email_generator import generate_premium_reminder_email
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

            if elapsed_ms > 20000:
                print(f"  FAIL [{case['input']['name']}] too slow: {elapsed_ms}ms (limit 20000ms)")
                ok = False

            if ok:
                passed += 1
                print(f"  PASS [{case['input']['name']}] {elapsed_ms}ms")
            else:
                failed += 1

    print(f"\nNeed Analyzer Evals: {passed} passed, {failed} failed")
    return failed == 0


async def run_product_recommender_evals() -> bool:
    golden = Path("tests/evals/golden/product_recommender.jsonl")
    passed = failed = 0

    async with AsyncSessionLocal() as db:
        for line in golden.read_text().strip().splitlines():
            case = json.loads(line)
            name = case["profile"]["name"]
            start = time.monotonic()
            recs = await recommend_products(db, case["profile"], case["need_analysis"])
            elapsed_ms = int((time.monotonic() - start) * 1000)

            ok = True

            if len(recs) < case.get("min_products", 1):
                print(f"  FAIL [{name}] too few products: {len(recs)} (min {case['min_products']})")
                ok = False

            all_text = " ".join(
                f"{r.get('product_name','')} {r.get('type','')} {r.get('key_benefit','')} {r.get('why_suits','')}"
                for r in recs
            ).lower()

            if not any(kw.lower() in all_text for kw in case.get("must_contain_any_product", [])):
                print(f"  FAIL [{name}] none of {case['must_contain_any_product']} found in output")
                ok = False

            for phrase in case.get("must_not_contain", []):
                if phrase.lower() in all_text:
                    print(f"  FAIL [{name}] prohibited phrase: '{phrase}'")
                    ok = False

            if elapsed_ms > 20000:
                print(f"  FAIL [{name}] too slow: {elapsed_ms}ms (limit 20000ms)")
                ok = False

            if ok:
                passed += 1
                print(f"  PASS [{name}] {len(recs)} products, {elapsed_ms}ms")
            else:
                failed += 1

    print(f"\nProduct Recommender Evals: {passed} passed, {failed} failed")
    return failed == 0


async def run_email_generator_evals() -> bool:
    golden = Path("tests/evals/golden/email_generator.jsonl")
    passed = failed = 0

    for line in golden.read_text().strip().splitlines():
        case = json.loads(line)
        name = case["input"]["client_name"]
        start = time.monotonic()
        result = await generate_premium_reminder_email(**case["input"])
        elapsed_ms = int((time.monotonic() - start) * 1000)

        full_text = f"{result.get('subject','')} {result.get('body','')}".lower()
        ok = True

        for phrase in case.get("must_contain", []):
            if phrase.lower() not in full_text:
                print(f"  FAIL [{name}] missing: '{phrase}'")
                ok = False

        for phrase in case.get("must_not_contain", []):
            if phrase.lower() in full_text:
                print(f"  FAIL [{name}] prohibited: '{phrase}'")
                ok = False

        if not result.get("subject"):
            print(f"  FAIL [{name}] empty subject")
            ok = False

        if not result.get("body"):
            print(f"  FAIL [{name}] empty body")
            ok = False

        if elapsed_ms > 20000:
            print(f"  FAIL [{name}] too slow: {elapsed_ms}ms (limit 20000ms)")
            ok = False

        if ok:
            passed += 1
            print(f"  PASS [{name}] {elapsed_ms}ms")
        else:
            failed += 1

    print(f"\nEmail Generator Evals: {passed} passed, {failed} failed")
    return failed == 0


async def main():
    print("=== Running AI Evaluation Gate ===\n")
    results = [
        await run_need_analyzer_evals(),
        await run_product_recommender_evals(),
        await run_email_generator_evals(),
    ]
    all_pass = all(results)
    print("\n" + ("ALL EVALS PASSED" if all_pass else "EVAL GATE FAILED — blocking deployment"))
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    asyncio.run(main())
