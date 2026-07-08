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
from app.modules.pitch_handler import generate_pitch, handle_objection
from app.db.postgres import AsyncSessionLocal
from app.agents.policy_research_agent import build_policy_research_agent

import tests.evals.ragas_compat  # noqa: F401 — must precede any `ragas` import

# RAGAS score thresholds — generous on purpose: this is a sanity gate against a
# handful of golden questions, not a tight quality bar tuned on a large eval set.
#
# Faithfulness blocks the gate — across every run so far (good and bad) it has
# been a stable, meaningful signal (checks the answer is actually grounded in
# the retrieved chunks, not hallucinated).
#
# Answer Relevancy does NOT block — it's reference-free and judged by an LLM,
# and in practice swings wildly run-to-run on identical, verified-good answers
# (seen scores from 0.63 to 0.99 across repeated runs of the same code). It's
# a known weakness of this metric that it penalizes longer, more detailed
# answers. Still computed and printed so regressions remain visible.
RAGAS_FAITHFULNESS_MIN = 0.7
RAGAS_ANSWER_RELEVANCY_MIN = 0.7


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


async def run_pitch_handler_evals() -> bool:
    golden = Path("tests/evals/golden/pitch_handler.jsonl")
    passed = failed = 0

    for line in golden.read_text().strip().splitlines():
        case = json.loads(line)
        case_type = case["type"]
        name = f"{case.get('profile', {}).get('name', '?')} / {case.get('objection', 'pitch')}"
        start = time.monotonic()
        ok = True

        if case_type == "pitch":
            output = await generate_pitch(case["profile"])
            elapsed_ms = int((time.monotonic() - start) * 1000)
            lower = output.lower()

            for phrase in case.get("must_contain", []):
                if phrase.lower() not in lower:
                    print(f"  FAIL [{name}] missing: '{phrase}'")
                    ok = False

            for phrase in case.get("must_not_contain", []):
                if phrase.lower() in lower:
                    print(f"  FAIL [{name}] prohibited: '{phrase}'")
                    ok = False

            if len(output) < case.get("min_length", 0):
                print(f"  FAIL [{name}] output too short: {len(output)} chars")
                ok = False

        elif case_type == "objection":
            result = await handle_objection(case["objection"], case["profile"])
            elapsed_ms = int((time.monotonic() - start) * 1000)
            all_text = " ".join(str(v) for v in result.values()).lower()

            for key in case.get("required_keys", []):
                if not result.get(key):
                    print(f"  FAIL [{name}] missing/empty key: '{key}'")
                    ok = False

            for phrase in case.get("must_not_contain", []):
                if phrase.lower() in all_text:
                    print(f"  FAIL [{name}] prohibited: '{phrase}'")
                    ok = False

        if elapsed_ms > 20000:
            print(f"  FAIL [{name}] too slow: {elapsed_ms}ms (limit 20000ms)")
            ok = False

        if ok:
            passed += 1
            print(f"  PASS [{name}] ({case_type}) {elapsed_ms}ms")
        else:
            failed += 1

    print(f"\nPitch Handler Evals: {passed} passed, {failed} failed")
    return failed == 0


async def run_ragas_evals() -> bool:
    from ragas import evaluate
    from ragas.dataset_schema import EvaluationDataset, SingleTurnSample
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import Faithfulness, ResponseRelevancy
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from app.core.config import settings

    golden = Path("tests/evals/golden/policy_research.jsonl")
    agent = build_policy_research_agent()

    samples = []
    for line in golden.read_text().strip().splitlines():
        case = json.loads(line)
        result = await agent.ainvoke({
            "question": case["question"],
            "advisor_id": "ragas-eval",
            "search_plan": [], "search_results": [],
            "searches_done": 0, "is_sufficient": False,
            "answer": "", "citations": [], "errors": [],
        })
        if result.get("errors"):
            print(f"  FAIL [{case['question']}] agent error: {result['errors'][0]}")
            return False

        samples.append(SingleTurnSample(
            user_input=case["question"],
            response=result["answer"],
            retrieved_contexts=[r["content"] for r in result["search_results"][:8]] or [""],
        ))

    judge_llm = LangchainLLMWrapper(ChatOpenAI(model="gpt-4o-mini", api_key=settings.OPENAI_API_KEY))
    judge_embeddings = LangchainEmbeddingsWrapper(OpenAIEmbeddings(api_key=settings.OPENAI_API_KEY))

    result = evaluate(
        dataset=EvaluationDataset(samples=samples),
        metrics=[Faithfulness(), ResponseRelevancy()],
        llm=judge_llm,
        embeddings=judge_embeddings,
        show_progress=False,
    )
    df = result.to_pandas()

    faithfulness_mean = df["faithfulness"].mean()
    relevancy_mean = df["answer_relevancy"].mean()

    ok = True
    print(f"  Faithfulness:     {faithfulness_mean:.2f} (min {RAGAS_FAITHFULNESS_MIN})")
    print(f"  Answer Relevancy: {relevancy_mean:.2f} (min {RAGAS_ANSWER_RELEVANCY_MIN})")
    if faithfulness_mean < RAGAS_FAITHFULNESS_MIN:
        print("  FAIL: faithfulness below threshold")
        ok = False
    if relevancy_mean < RAGAS_ANSWER_RELEVANCY_MIN:
        print("  WARN: answer relevancy below threshold (non-blocking — see comment above)")

    print(f"\nRAGAS Evals: {'passed' if ok else 'failed'}")
    return ok


async def main():
    print("=== Running AI Evaluation Gate ===\n")
    results = [
        await run_need_analyzer_evals(),
        await run_product_recommender_evals(),
        await run_email_generator_evals(),
        await run_pitch_handler_evals(),
        await run_ragas_evals(),
    ]
    all_pass = all(results)
    print("\n" + ("ALL EVALS PASSED" if all_pass else "EVAL GATE FAILED — blocking deployment"))
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    asyncio.run(main())
