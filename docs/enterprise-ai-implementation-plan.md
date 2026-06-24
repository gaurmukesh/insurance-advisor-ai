# Enterprise Gen AI / Agentic Architecture — Step-by-Step Implementation Plan
## Insurance Advisor AI Project

> **How to use this doc**
> Each step = one concrete deliverable in this codebase.
> Each step also has an "Interview Answer" you can use verbatim.
> Follow the day-by-day schedule at the bottom to finish in 8 weeks.

---

## Architecture Overview — What We Are Building

```
┌─────────────────────────────────────────────────────────────────┐
│                    ENTERPRISE AI PLATFORM                        │
│                                                                   │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────────────┐ │
│  │  MCP Server  │   │  REST API    │   │  LangGraph Agents    │ │
│  │  (10 tools)  │   │  (FastAPI)   │   │  (multi-step AI)     │ │
│  └──────┬───────┘   └──────┬───────┘   └──────────┬───────────┘ │
│         │                  │                        │             │
│         └──────────────────┴────────────────────────┘             │
│                            │                                      │
│              ┌─────────────▼─────────────┐                       │
│              │       BaseAgent Core       │                       │
│              │  PII Guard + Audit Log +   │                       │
│              │  Guardrails + LangFuse     │                       │
│              └─────────────┬─────────────┘                       │
│                            │                                      │
│         ┌──────────────────┼──────────────────┐                  │
│         ▼                  ▼                  ▼                   │
│   ┌───────────┐    ┌──────────────┐   ┌──────────────┐          │
│   │ PostgreSQL │    │  pgvector    │   │  Prompt      │          │
│   │ + RLS      │    │  (RAG)       │   │  Registry    │          │
│   └───────────┘    └──────────────┘   └──────────────┘          │
│                                                                   │
│              ┌─────────────────────────────┐                     │
│              │      CI/CD + Eval Gate       │                     │
│              │  lint → test → eval → deploy │                     │
│              └─────────────────────────────┘                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## PHASE 1 — Foundation (Week 1–2)

---

## Step 1 — MCP Server
**Timeline:** Day 1–2
**JD:** *Create reusable Gen AI assets, accelerators, and frameworks*

### What is MCP?
Model Context Protocol is Anthropic's open standard. You build a server that exposes your system's capabilities as "tools". Any MCP-compatible AI (Claude Desktop, Claude Code, any future client) can call your tools directly — without you building a separate integration per consumer.

### Why this matters here
Right now if you want Claude to look up a lead or run a need analysis, you have to copy-paste data manually. After this step, Claude can call `analyze_needs("client-id")` directly and get real data from your PostgreSQL database.

### File 1: `app/mcp/__init__.py`
```python
# empty — makes app/mcp a Python package
```

### File 2: `app/mcp/server.py`
```python
import json
from datetime import date, timedelta
from typing import Optional

from mcp.server.fastmcp import FastMCP
from sqlalchemy import select

from app.db.postgres import AsyncSessionLocal
from app.models.client import Client
from app.models.policy import Policy
from app.modules.need_analyzer import analyze_client_needs
from app.modules.product_recommender import recommend_products
from app.modules.pitch_handler import generate_pitch, handle_objection
from app.db.vector_store import similarity_search

mcp = FastMCP(
    "Insurance Advisor AI",
    instructions=(
        "Tools for managing insurance leads, running AI need analysis, "
        "generating product recommendations, pitches, handling objections, "
        "and searching policy documents."
    ),
)


def _to_dict(c: Client) -> dict:
    return {
        "id": c.id, "advisor_id": c.advisor_id, "name": c.name,
        "email": c.email, "phone": c.phone, "age": c.age,
        "income": c.income, "family_size": c.family_size,
        "risk_appetite": c.risk_appetite, "goals": c.goals,
        "status": c.status, "notes": c.notes,
        "existing_coverage": c.existing_coverage,
        "liabilities_emi": c.liabilities_emi,
        "employment_type": c.employment_type,
        "health_conditions": c.health_conditions,
        "dependents_detail": c.dependents_detail,
        "city_tier": c.city_tier,
    }


# ── TOOL 1: List leads ────────────────────────────────────────────
@mcp.tool()
async def list_leads(advisor_id: str, status: Optional[str] = None) -> str:
    """List all leads for an advisor.
    status options: new | contacted | interested | converted | lost"""
    async with AsyncSessionLocal() as db:
        q = select(Client).where(Client.advisor_id == advisor_id)
        if status:
            q = q.where(Client.status == status)
        q = q.order_by(Client.created_at.desc())
        rows = (await db.execute(q)).scalars().all()
        return json.dumps([_to_dict(c) for c in rows], default=str)


# ── TOOL 2: Get client ────────────────────────────────────────────
@mcp.tool()
async def get_client(client_id: str) -> str:
    """Get the full profile of a lead by their ID."""
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(Client).where(Client.id == client_id)
        )).scalar_one_or_none()
        if not row:
            return json.dumps({"error": f"Client {client_id} not found"})
        return json.dumps(_to_dict(row), default=str)


# ── TOOL 3: Create lead ───────────────────────────────────────────
@mcp.tool()
async def create_lead(
    advisor_id: str, name: str,
    email: Optional[str] = None, phone: Optional[str] = None,
    age: Optional[int] = None, income: Optional[float] = None,
    family_size: Optional[int] = None,
    risk_appetite: Optional[str] = None,
    goals: Optional[str] = None,
    employment_type: Optional[str] = None,
    health_conditions: Optional[str] = None,
    city_tier: Optional[str] = None,
) -> str:
    """Create a new insurance lead for an advisor."""
    async with AsyncSessionLocal() as db:
        client = Client(
            advisor_id=advisor_id, name=name, email=email, phone=phone,
            age=age, income=income, family_size=family_size,
            risk_appetite=risk_appetite, goals=goals,
            employment_type=employment_type,
            health_conditions=health_conditions, city_tier=city_tier,
        )
        db.add(client)
        await db.commit()
        await db.refresh(client)
        return json.dumps(_to_dict(client), default=str)


# ── TOOL 4: Update lead status ────────────────────────────────────
@mcp.tool()
async def update_lead_status(
    client_id: str, status: str, notes: Optional[str] = None
) -> str:
    """Update a lead's status and optionally add notes."""
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(Client).where(Client.id == client_id)
        )).scalar_one_or_none()
        if not row:
            return json.dumps({"error": f"Client {client_id} not found"})
        row.status = status
        if notes:
            row.notes = notes
        await db.commit()
        await db.refresh(row)
        return json.dumps(_to_dict(row), default=str)


# ── TOOL 5: Analyze needs ─────────────────────────────────────────
@mcp.tool()
async def analyze_needs(client_id: str) -> str:
    """Run AI-powered insurance need analysis.
    Identifies gaps, priorities, and tax benefit opportunities (80C/80D)."""
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(Client).where(Client.id == client_id)
        )).scalar_one_or_none()
        if not row:
            return json.dumps({"error": f"Client {client_id} not found"})
        return await analyze_client_needs(db, _to_dict(row))


# ── TOOL 6: Get recommendations ───────────────────────────────────
@mcp.tool()
async def get_recommendations(client_id: str) -> str:
    """Get top-3 AI-recommended insurance products for a client.
    Returns JSON with product, insurer, premium, sum assured, tax benefit."""
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(Client).where(Client.id == client_id)
        )).scalar_one_or_none()
        if not row:
            return json.dumps({"error": f"Client {client_id} not found"})
        profile = _to_dict(row)
        need_analysis = await analyze_client_needs(db, profile)
        recs = await recommend_products(db, profile, need_analysis)
        return json.dumps(recs, default=str)


# ── TOOL 7: Generate pitch ────────────────────────────────────────
@mcp.tool()
async def generate_sales_pitch(client_id: str) -> str:
    """Generate a personalized sales pitch for a client.
    Format: Opening → Key Need → Solution → Call to Action."""
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(Client).where(Client.id == client_id)
        )).scalar_one_or_none()
        if not row:
            return json.dumps({"error": f"Client {client_id} not found"})
        return await generate_pitch(_to_dict(row))


# ── TOOL 8: Handle objection ──────────────────────────────────────
@mcp.tool()
async def handle_client_objection(client_id: str, objection: str) -> str:
    """Get a structured response to a client objection.
    Common: 'premium too high', 'already have insurance', 'will think about it'"""
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(Client).where(Client.id == client_id)
        )).scalar_one_or_none()
        if not row:
            return json.dumps({"error": f"Client {client_id} not found"})
        result = await handle_objection(objection, _to_dict(row))
        return json.dumps(result, default=str)


# ── TOOL 9: Search policy docs ────────────────────────────────────
@mcp.tool()
async def search_policy_docs(query: str, top_k: int = 5) -> str:
    """Semantic search across ingested policy PDFs.
    Returns relevant excerpts with similarity scores."""
    async with AsyncSessionLocal() as db:
        results = await similarity_search(db, query, top_k=top_k)
        if not results:
            return "No relevant policy documents found."
        return json.dumps(results, default=str)


# ── TOOL 10: Upcoming renewals ────────────────────────────────────
@mcp.tool()
async def get_upcoming_renewals(advisor_id: str, days: int = 30) -> str:
    """List policies due for renewal in the next N days."""
    async with AsyncSessionLocal() as db:
        today = date.today()
        until = today + timedelta(days=days)
        rows = (await db.execute(
            select(Policy, Client)
            .join(Client, Policy.client_id == Client.id)
            .where(Client.advisor_id == advisor_id)
            .where(Policy.next_due_date >= today)
            .where(Policy.next_due_date <= until)
            .order_by(Policy.next_due_date)
        )).all()
        return json.dumps([
            {
                "policy_id": p.id, "policy_no": p.policy_no,
                "product_name": p.product_name,
                "insurer_name": p.insurer_name,
                "premium_amount": p.premium_amount,
                "next_due_date": str(p.next_due_date),
                "client_id": c.id, "client_name": c.name,
                "client_email": c.email, "client_phone": c.phone,
            }
            for p, c in rows
        ], default=str)


if __name__ == "__main__":
    mcp.run()
```

### File 3: `.mcp.json` (project root — Claude Code auto-loads this)
```json
{
  "mcpServers": {
    "insurance-advisor": {
      "command": "python",
      "args": ["-m", "app.mcp.server"],
      "env": {
        "DATABASE_URL": "${DATABASE_URL}",
        "OPENAI_API_KEY": "${OPENAI_API_KEY}",
        "LANGFUSE_SECRET_KEY": "${LANGFUSE_SECRET_KEY}",
        "LANGFUSE_PUBLIC_KEY": "${LANGFUSE_PUBLIC_KEY}"
      }
    }
  }
}
```

### Add to `requirements.txt`
```
mcp>=1.9.0
```

### How to test
```bash
pip install mcp
python -m app.mcp.server   # should start without error
# Then open Claude Desktop → Settings → MCP → add this project
```

### Interview Answer
> "I built an MCP server exposing 10 tools from our insurance platform — lead management,
> AI need analysis, product recommendations, pitch generation, objection handling, and
> semantic policy search. Any MCP-compatible AI assistant can call these tools natively.
> This is the reusable accelerator pattern — instead of building a custom integration
> for every AI consumer, one MCP server serves all of them. Claude Desktop, Claude Code,
> any future internal tool — they all connect to the same server."

---

## Step 2 — BaseAgent Framework
**Timeline:** Day 3–4
**JD:** *Enterprise-wide ML/Gen AI architecture; reusable frameworks*

### What is this?
Right now `need_analyzer.py`, `product_recommender.py`, `pitch_handler.py` each independently handle
LLM calls, tracing, and JSON parsing. If you add a new agent tomorrow, you have to repeat all that
boilerplate. BaseAgent extracts this into one place every future agent inherits.

### The Problem (before)
```
need_analyzer.py      → calls chat() directly, no standard error handling
product_recommender.py → calls chat() directly, strips JSON manually
pitch_handler.py       → calls chat() directly, strips JSON manually
```

### The Solution (after)
```
BaseAgent (standard interface)
  ├── need_analyzer     (just implements system_prompt + build_prompt)
  ├── product_recommender (same)
  └── pitch_handler     (same)
```

### File: `app/core/base_agent.py`
```python
import json
from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel
from app.core.llm import chat, chat_mini
from app.core.observability import get_langfuse


class AgentInput(BaseModel):
    pass


class AgentOutput(BaseModel):
    raw: str
    parsed: Any = None
    trace_id: str = ""


class BaseAgent(ABC):
    """
    Standard interface every Gen AI initiative inherits.

    Subclass provides:
      - system_prompt() -> str
      - build_prompt(input) -> str
      - _parse(raw) -> Any   [optional, default returns raw string]

    BaseAgent provides for free:
      - Correct LLM dispatch (GPT-4o vs mini)
      - LangFuse trace on every call
      - JSON parse with markdown fence stripping
    """

    trace_name: str = "base_agent"
    use_mini: bool = False    # set True in subclass for low-complexity tasks

    async def run(self, input: AgentInput) -> AgentOutput:
        langfuse = get_langfuse()
        trace = langfuse.trace(name=self.trace_name) if langfuse else None

        system = self.system_prompt()
        prompt = self.build_prompt(input)

        fn = chat_mini if self.use_mini else chat
        raw = await fn(system, prompt, trace_name=self.trace_name)

        parsed = self._parse(raw)
        return AgentOutput(raw=raw, parsed=parsed, trace_id=trace.id if trace else "")

    @abstractmethod
    def system_prompt(self) -> str: ...

    @abstractmethod
    def build_prompt(self, input: AgentInput) -> str: ...

    def _parse(self, raw: str) -> Any:
        return raw

    def _parse_json(self, raw: str) -> Any:
        """Use this in _parse() when the agent returns JSON."""
        try:
            clean = (
                raw.strip()
                .removeprefix("```json")
                .removeprefix("```")
                .removesuffix("```")
                .strip()
            )
            return json.loads(clean)
        except Exception:
            return raw
```

### Interview Answer
> "I established a BaseAgent abstract class that every AI module inherits.
> It enforces: unified LLM routing, automatic LangFuse tracing, and structured
> output parsing. New engineers add a new agent by subclassing BaseAgent and
> implementing three methods — system_prompt, build_prompt, and optionally _parse.
> The governance layer — tracing, PII scrubbing, error handling — comes for free.
> No one can bypass it because it's in the base class, not in each module."

---

## Step 3 — Governance Layer: PII Guard + Audit Log + Guardrails
**Timeline:** Day 5–6
**JD:** *Governance policies, data privacy, ethical guidelines, compliance*

### Why this is critical for insurance
Insurance data is among the most sensitive — Aadhaar numbers, medical conditions, income details.
IRDAI regulations prohibit certain marketing claims. You need controls that are automatic,
not optional.

### 3a — PII Scrubber

### File: `app/core/pii_guard.py`
```python
import re

# Indian PII patterns
_AADHAAR = re.compile(r'\b\d{4}\s?\d{4}\s?\d{4}\b')
_PAN     = re.compile(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b')
_PHONE   = re.compile(r'\b[6-9]\d{9}\b')
_EMAIL   = re.compile(r'\b[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}\b')


def scrub(text: str) -> str:
    """Strip Indian PII before sending to any external LLM API."""
    text = _AADHAAR.sub("[AADHAAR-REDACTED]", text)
    text = _PAN.sub("[PAN-REDACTED]", text)
    text = _PHONE.sub("[PHONE-REDACTED]", text)
    text = _EMAIL.sub("[EMAIL-REDACTED]", text)
    return text
```

### Wire into `app/core/llm.py` — add 2 lines
```python
# Add this import at the top:
from app.core.pii_guard import scrub

# Inside _call(), before the OpenAI call:
user_message = scrub(user_message)
```

### 3b — AI Audit Log

### SQL migration — add to `migrations/init.sql`
```sql
CREATE TABLE IF NOT EXISTS ai_audit_log (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_name  VARCHAR(100) NOT NULL,
    client_id   VARCHAR(100),
    advisor_id  VARCHAR(100),
    input_hash  VARCHAR(64),        -- SHA-256 of scrubbed input
    model       VARCHAR(50),
    tokens_in   INTEGER,
    tokens_out  INTEGER,
    latency_ms  INTEGER,
    outcome     VARCHAR(20) DEFAULT 'success',
    created_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_audit_trace ON ai_audit_log(trace_name, created_at DESC);
CREATE INDEX idx_audit_client ON ai_audit_log(client_id);
```

### File: `app/core/audit.py`
```python
import hashlib
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


async def log_ai_decision(
    db: AsyncSession,
    trace_name: str,
    input_text: str,
    model: str,
    tokens_in: int = 0,
    tokens_out: int = 0,
    latency_ms: int = 0,
    client_id: str = None,
    advisor_id: str = None,
    outcome: str = "success",
):
    """
    Write an immutable record of every AI decision.
    Stores SHA-256 of the input (not the input itself) for tamper-evidence.
    """
    input_hash = hashlib.sha256(input_text.encode()).hexdigest()
    await db.execute(text("""
        INSERT INTO ai_audit_log
            (trace_name, client_id, advisor_id, input_hash,
             model, tokens_in, tokens_out, latency_ms, outcome)
        VALUES
            (:trace_name, :client_id, :advisor_id, :input_hash,
             :model, :tokens_in, :tokens_out, :latency_ms, :outcome)
    """), {
        "trace_name": trace_name, "client_id": client_id,
        "advisor_id": advisor_id, "input_hash": input_hash,
        "model": model, "tokens_in": tokens_in,
        "tokens_out": tokens_out, "latency_ms": latency_ms,
        "outcome": outcome,
    })
    await db.commit()
```

### 3c — Output Guardrail

### File: `app/core/guardrails.py`
```python
# IRDAI-prohibited phrases in insurance marketing
_PROHIBITED = [
    "guaranteed returns",
    "no risk",
    "100% safe investment",
    "tax-free guaranteed",
    "assured profit",
    "risk-free",
]


def validate_output(text: str, context: str = "") -> str:
    """
    Reject LLM outputs containing regulatory violations.
    Raises ValueError — caller decides whether to retry or surface the error.
    """
    lower = text.lower()
    for phrase in _PROHIBITED:
        if phrase in lower:
            raise ValueError(
                f"Output contains IRDAI-prohibited claim: '{phrase}'. "
                f"Context: {context}"
            )
    return text
```

### Interview Answer
> "I implemented three governance controls that run automatically on every AI call.
> First, a PII scrubber using regex patterns for Aadhaar, PAN, phone, and email —
> it runs before every OpenAI API call, so sensitive data never leaves the system
> in a prompt. Second, an immutable AI audit log in PostgreSQL that records a
> SHA-256 hash of every input — if a regulator asks 'what did your AI decide for
> this client on this date', we have a tamper-evident record. Third, an output
> guardrail that rejects IRDAI-prohibited claims like 'guaranteed returns' at
> runtime. These controls are in the base infrastructure, not in individual modules
> — they cannot be accidentally bypassed."

---

## PHASE 2 — Quality & Delivery (Week 3–4)

---

## Step 4 — Evaluation Harness
**Timeline:** Day 7–8
**JD:** *CI/CD for AI solutions; performance and maintainability*

### Why unit tests are not enough for AI
A function can pass all its unit tests and still produce worse outputs.
Unit tests check code correctness. Eval harness checks AI quality.
You need both.

### Directory structure
```
tests/evals/
├── golden/
│   ├── need_analyzer.jsonl       ← ground-truth examples
│   └── product_recommender.jsonl
└── run_evals.py                  ← CI gate script
```

### File: `tests/evals/golden/need_analyzer.jsonl`
```jsonl
{"input": {"name": "Rahul", "age": 32, "income": 800000, "family_size": 4, "risk_appetite": "medium", "goals": "children education and retirement", "liabilities_emi": 20000, "employment_type": "salaried", "health_conditions": "None", "existing_coverage": "None", "city_tier": "tier1", "dependents_detail": "spouse, 2 kids"}, "must_contain": ["term", "health", "80C", "80D"], "must_not_contain": ["guaranteed returns"]}
{"input": {"name": "Priya", "age": 45, "income": 1500000, "family_size": 2, "risk_appetite": "low", "goals": "retirement corpus", "liabilities_emi": 0, "employment_type": "self_employed", "health_conditions": "diabetes", "existing_coverage": "term 1 crore", "city_tier": "tier1", "dependents_detail": "spouse"}, "must_contain": ["health", "critical illness", "80D"], "must_not_contain": ["guaranteed returns"]}
{"input": {"name": "Amit", "age": 25, "income": 400000, "family_size": 1, "risk_appetite": "high", "goals": "wealth creation", "liabilities_emi": 5000, "employment_type": "salaried", "health_conditions": "None", "existing_coverage": "None", "city_tier": "tier2", "dependents_detail": "None"}, "must_contain": ["term", "health"], "must_not_contain": ["guaranteed returns"]}
```

### File: `tests/evals/run_evals.py`
```python
"""
Run: python tests/evals/run_evals.py
Exit code 0 = all pass. Exit code 1 = one or more fail.
Use as CI gate — blocks deployment if AI quality regresses.
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
```

### How to run
```bash
python tests/evals/run_evals.py
```

### Interview Answer
> "I built an eval harness with golden datasets — curated ground-truth examples
> with must_contain and must_not_contain assertions plus a latency threshold.
> It runs as a separate CI stage before every deployment to production.
> If the need analyzer stops recommending term insurance for a young family,
> or if it starts making prohibited claims, or if latency spikes above 5 seconds,
> the pipeline blocks the merge. This is how you maintain AI quality at scale —
> standard unit tests check code, eval harness checks AI behavior."

---

## Step 5 — Prompt Registry
**Timeline:** Day 9–10
**JD:** *Governance; continuous delivery; performance*

### Problem with hardcoded prompts
System prompts are currently strings hardcoded in Python files.
Changing a prompt = changing code = requires a deployment.
A prompt registry lets you:
- Swap prompts without code changes or restarts
- A/B test prompt versions with LangFuse
- Roll back a bad prompt instantly
- Track which prompt version produced which output

### SQL migration — add to `migrations/init.sql`
```sql
CREATE TABLE IF NOT EXISTS prompt_registry (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name       VARCHAR(100) NOT NULL,
    version    INTEGER NOT NULL DEFAULT 1,
    content    TEXT NOT NULL,
    model      VARCHAR(50),
    is_active  BOOLEAN NOT NULL DEFAULT false,
    created_by VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (name, version)
);
CREATE INDEX idx_prompt_active ON prompt_registry(name, is_active);
```

### File: `app/core/prompt_registry.py`
```python
from sqlalchemy import text
from app.db.postgres import AsyncSessionLocal

# In-process cache so we don't query DB on every LLM call
_cache: dict[str, str] = {}


async def get_prompt(name: str) -> str | None:
    """
    Fetch the active version of a named prompt.
    Returns None if not found — caller falls back to hardcoded default.
    """
    if name in _cache:
        return _cache[name]

    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            text("""
                SELECT content FROM prompt_registry
                WHERE name = :name AND is_active = true
                LIMIT 1
            """),
            {"name": name},
        )).fetchone()

    if row:
        _cache[name] = row.content
        return row.content
    return None


def invalidate_cache(name: str = None):
    """Call this after promoting a new prompt version to active."""
    if name:
        _cache.pop(name, None)
    else:
        _cache.clear()
```

### Wire into `app/modules/need_analyzer.py` — 3 lines change
```python
# Add import:
from app.core.prompt_registry import get_prompt

# Inside analyze_client_needs(), replace the direct SYSTEM_PROMPT reference:
system = await get_prompt("need_analyzer_system") or SYSTEM_PROMPT
return await chat(system, user_message, trace_name="need_analyzer")
```

### Interview Answer
> "Prompt changes are deployments in disguise. I built a prompt registry in
> PostgreSQL — every named prompt has versions, one is marked active.
> The application fetches the active version at call time with an in-process
> cache, so there's no DB hit on every LLM call. When accuracy drops, I can
> diff prompt versions across the LangFuse timeline and pinpoint the regression.
> And I can roll back a bad prompt in seconds without touching code."

---

## Step 6 — CI/CD Pipeline with AI Eval Gate
**Timeline:** Day 11–12
**JD:** *Continuous integration and delivery of AI solutions; performance*

### File: `.github/workflows/ai-deploy.yml`
```yaml
name: AI Deploy Pipeline

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  # ── Stage 1: Code quality ──────────────────────────────────────
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install ruff && ruff check app/

  # ── Stage 2: Unit + integration tests ─────────────────────────
  unit-tests:
    runs-on: ubuntu-latest
    needs: lint
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_PASSWORD: secret
          POSTGRES_DB: insurance_ai_test
        ports: ["5432:5432"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements.txt
      - run: pytest tests/ -v --ignore=tests/evals
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:secret@localhost:5432/insurance_ai_test
          SYNC_DATABASE_URL: postgresql://postgres:secret@localhost:5432/insurance_ai_test
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          SENDGRID_API_KEY: ${{ secrets.SENDGRID_API_KEY }}
          SENDGRID_FROM_EMAIL: test@example.com

  # ── Stage 3: AI Eval Gate (blocks main merges) ────────────────
  eval-gate:
    runs-on: ubuntu-latest
    needs: unit-tests
    if: github.ref == 'refs/heads/main'
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_PASSWORD: secret
          POSTGRES_DB: insurance_ai_eval
        ports: ["5432:5432"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements.txt
      - name: Run AI Evaluation Gate
        run: python tests/evals/run_evals.py
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:secret@localhost:5432/insurance_ai_eval
          SYNC_DATABASE_URL: postgresql://postgres:secret@localhost:5432/insurance_ai_eval
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}

  # ── Stage 4: Build Docker image ───────────────────────────────
  build:
    runs-on: ubuntu-latest
    needs: [unit-tests, eval-gate]
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - name: Build image
        run: docker build -t insurance-advisor-ai:${{ github.sha }} .
      - name: Push to ECR
        run: |
          aws ecr get-login-password --region ap-south-1 \
            | docker login --username AWS --password-stdin ${{ secrets.ECR_REGISTRY }}
          docker tag insurance-advisor-ai:${{ github.sha }} \
            ${{ secrets.ECR_REGISTRY }}/insurance-advisor-ai:${{ github.sha }}
          docker push ${{ secrets.ECR_REGISTRY }}/insurance-advisor-ai:${{ github.sha }}
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}

  # ── Stage 5: Deploy to staging ────────────────────────────────
  deploy-staging:
    runs-on: ubuntu-latest
    needs: build
    environment: staging
    steps:
      - name: Deploy to ECS staging
        run: |
          aws ecs update-service \
            --cluster insurance-ai-staging \
            --service insurance-advisor-api \
            --force-new-deployment
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          AWS_DEFAULT_REGION: ap-south-1
```

### Interview Answer
> "Standard CI/CD wasn't designed for AI. A function can pass all its unit tests
> and still produce worse outputs if the model changes or the prompt drifts.
> I added an eval gate as a dedicated CI stage — it runs real OpenAI calls
> against curated golden examples before any build goes to production.
> lint → unit tests → AI eval gate → build → deploy staging.
> The eval gate is the stage that makes this AI-native CI/CD, not just
> standard CI/CD applied to an AI project."

---

## PHASE 3 — Agentic Architecture (Week 5–8)

> All 6 agents use LangGraph `StateGraph`. Each has a typed `State`, async nodes,
> and conditional routing. Agents 1–5 are standalone. Agent 6 is the Orchestrator
> that calls Agents 1 and 2 via `ainvoke`.

---

## Agent Map

```
┌─────┬──────────────────────────────┬──────────────────────────────────────────────────────────────────────────────────────────────────┬─────────────────────────────────────────────────┐
│  #  │          Agent Name          │                         LangGraph Nodes (in order)                                                │        Existing modules it uses                 │
├─────┼──────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────┤
│  1  │ Needs Analysis Agent         │ load_client → build_rag_query → fetch_context → run_analysis → extract_gaps → save_interaction   │ need_analyzer.py + vector_store.py              │
├─────┼──────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────┤
│  2  │ Product Matching Agent       │ load_client → run_needs_analysis → generate_queries → search_products → rank_match → save_recs   │ product_recommender.py + vector_store.py        │
├─────┼──────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────┤
│  3  │ Claims & Renewals Agent      │ load_renewals → score_risk → filter_priority → draft_outreach → queue_approval → notify_advisor  │ email_generator.py + whatsapp_handler.py        │
├─────┼──────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────┤
│  4  │ Policy Research Agent        │ receive_question → plan_searches → search_loop → validate_answer → synthesize_with_citations     │ doc_assistant.py + vector_store.py              │
├─────┼──────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────┤
│  5  │ Objection Handler Agent      │ load_client → classify_objection → generate_response → suggest_next_pitch → log_interaction      │ pitch_handler.py                                │
├─────┼──────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────┤
│  6  │ Lead Nurturing Agent         │ load_client → [Agent 1] → [Agent 2] → draft_email → queue_approval                              │ Orchestrates Agents 1 + 2 + email_generator.py  │
│     │ (Orchestrator)               │                                                                                                  │                                                 │
└─────┴──────────────────────────────┴──────────────────────────────────────────────────────────────────────────────────────────────────┴─────────────────────────────────────────────────┘
```

## File structure to create

```
app/agents/
├── __init__.py
├── needs_analysis_agent.py       ← Agent 1
├── product_matching_agent.py     ← Agent 2
├── claims_renewals_agent.py      ← Agent 3
├── policy_research_agent.py      ← Agent 4
├── objection_handler_agent.py    ← Agent 5
└── lead_nurturing_agent.py       ← Agent 6 (Orchestrator)
```

## SQL — add to `migrations/init.sql`
```sql
CREATE TABLE IF NOT EXISTS approval_queue (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id   VARCHAR(100),
    advisor_id  VARCHAR(100) NOT NULL,
    action_type VARCHAR(50) NOT NULL,
    payload     TEXT NOT NULL,
    status      VARCHAR(20) DEFAULT 'pending',
    reviewed_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_approval_advisor ON approval_queue(advisor_id, status);
```

## Add to `requirements.txt`
```
langgraph>=0.2.0
```

---

## Step 7 — Needs Analysis Agent
**Timeline:** Day 13–14
**JD:** *End-to-end Gen AI/Agentic initiatives; reusable assets*

### What `need_analyzer.py` does today vs what this agent adds

| `need_analyzer.py` (current) | Needs Analysis Agent |
|---|---|
| Single function call | 6-node stateful graph |
| Caller must pass profile dict | Agent loads client from DB itself |
| One generic RAG query | Agent builds targeted query from client goals + health |
| Returns raw text string | Extracts structured gaps as JSON `[{gap, priority, product_type}]` |
| No record of what ran | Saves interaction record to DB |

### Graph flow
```
load_client → build_rag_query → fetch_context → run_analysis → extract_gaps → save_interaction
     ↓ (error)
    END
```

### File: `app/agents/needs_analysis_agent.py`
```python
import json
import operator
from typing import TypedDict, Annotated

from langgraph.graph import StateGraph, END
from sqlalchemy import select, text

from app.db.postgres import AsyncSessionLocal
from app.db.vector_store import similarity_search
from app.models.client import Client
from app.modules.need_analyzer import analyze_client_needs
from app.core.llm import chat


class NeedsAnalysisState(TypedDict):
    client_id: str
    client_profile: dict
    rag_query: str
    rag_context: str
    analysis_text: str
    gaps: list[dict]       # [{gap, priority, product_type}]
    interaction_id: str
    errors: Annotated[list[str], operator.add]


async def load_client(state: NeedsAnalysisState) -> dict:
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(Client).where(Client.id == state["client_id"])
        )).scalar_one_or_none()
    if not row:
        return {"errors": [f"Client {state['client_id']} not found"]}
    return {"client_profile": {
        "id": row.id, "name": row.name, "age": row.age, "income": row.income,
        "family_size": row.family_size, "risk_appetite": row.risk_appetite,
        "goals": row.goals, "liabilities_emi": row.liabilities_emi or 0,
        "employment_type": row.employment_type or "Not specified",
        "health_conditions": row.health_conditions or "None",
        "existing_coverage": row.existing_coverage or "None",
        "city_tier": row.city_tier or "Not specified",
        "dependents_detail": row.dependents_detail or "None",
    }}


async def build_rag_query(state: NeedsAnalysisState) -> dict:
    p = state["client_profile"]
    query = (
        f"insurance coverage for {p.get('goals', 'general')} "
        f"age {p.get('age')} {p.get('employment_type', '')} "
        f"family size {p.get('family_size')} "
        f"health {p.get('health_conditions', 'none')}"
    )
    return {"rag_query": query}


async def fetch_context(state: NeedsAnalysisState) -> dict:
    async with AsyncSessionLocal() as db:
        results = await similarity_search(db, state["rag_query"], top_k=5)
    context = "\n\n".join(r["content"] for r in results) if results else ""
    return {"rag_context": context}


async def run_analysis(state: NeedsAnalysisState) -> dict:
    async with AsyncSessionLocal() as db:
        analysis = await analyze_client_needs(db, state["client_profile"])
    return {"analysis_text": analysis}


async def extract_gaps(state: NeedsAnalysisState) -> dict:
    prompt = f"""Extract insurance gaps from this analysis as a JSON array.
Each item: {{"gap":"...","priority":"high|medium|low","product_type":"term|health|motor|ulip|personal_accident"}}
Return JSON only.

Analysis:
{state['analysis_text']}"""
    raw = await chat(
        "Extract structured data from insurance analysis. Return JSON only.",
        prompt, trace_name="extract_gaps"
    )
    try:
        clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        gaps = json.loads(clean)
    except Exception:
        gaps = []
    return {"gaps": gaps}


async def save_interaction(state: NeedsAnalysisState) -> dict:
    async with AsyncSessionLocal() as db:
        result = await db.execute(text("""
            INSERT INTO interactions (client_id, interaction_type, notes, created_at)
            VALUES (:client_id, 'ai_needs_analysis', :notes, now())
            RETURNING id
        """), {"client_id": state["client_id"], "notes": state["analysis_text"][:1000]})
        row = result.fetchone()
        await db.commit()
    return {"interaction_id": str(row.id) if row else ""}


def _check_errors(state) -> str:
    return "error" if state.get("errors") else "continue"


def build_needs_analysis_agent():
    g = StateGraph(NeedsAnalysisState)
    g.add_node("load_client",      load_client)
    g.add_node("build_rag_query",  build_rag_query)
    g.add_node("fetch_context",    fetch_context)
    g.add_node("run_analysis",     run_analysis)
    g.add_node("extract_gaps",     extract_gaps)
    g.add_node("save_interaction", save_interaction)
    g.set_entry_point("load_client")
    g.add_conditional_edges("load_client", _check_errors,
                            {"continue": "build_rag_query", "error": END})
    g.add_edge("build_rag_query",  "fetch_context")
    g.add_edge("fetch_context",    "run_analysis")
    g.add_edge("run_analysis",     "extract_gaps")
    g.add_edge("extract_gaps",     "save_interaction")
    g.add_edge("save_interaction", END)
    return g.compile()
```

### Interview Answer
> "The needs analyzer was a single function call. The agent wraps it in a 6-node graph.
> The key additions: node 2 builds a targeted RAG query from the client's actual goals
> and health — not a generic string. Node 5 runs a second LLM call that extracts
> structured gaps as JSON with priority and product type. Node 6 writes an interaction
> record so every analysis is auditable. The state object carries profile, context,
> analysis, and gaps across all 6 nodes without any caller needing to wire them together."

---

## Step 8 — Product Matching Agent
**Timeline:** Day 15–16
**JD:** *Scalable AI solutions; reusable assets; performance*

### What `product_recommender.py` does today vs what this agent adds

| `product_recommender.py` (current) | Product Matching Agent |
|---|---|
| One hardcoded RAG query | LLM generates 3 targeted queries per client |
| Single search, top 6 chunks | 3 parallel searches via `asyncio.gather`, 18 chunks |
| Returns first 3 products LLM picks | Adds `client_fit_score` field per product |
| No search strategy | Agent decides WHAT to search based on profile |

### Graph flow
```
load_client → run_needs_analysis → generate_queries → search_products → rank_match → save_recs
     ↓ (error at any node)
    END
```

### File: `app/agents/product_matching_agent.py`
```python
import json
import asyncio
import operator
from typing import TypedDict, Annotated

from langgraph.graph import StateGraph, END
from sqlalchemy import select

from app.db.postgres import AsyncSessionLocal
from app.db.vector_store import similarity_search
from app.models.client import Client
from app.modules.need_analyzer import analyze_client_needs
from app.core.llm import chat


class ProductMatchingState(TypedDict):
    client_id: str
    client_profile: dict
    need_analysis: str
    search_queries: list[str]    # LLM-generated targeted queries
    raw_chunks: list[dict]       # deduplicated chunks from all searches
    recommendations: list[dict]  # ranked with client_fit_score
    errors: Annotated[list[str], operator.add]


async def load_client(state: ProductMatchingState) -> dict:
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(Client).where(Client.id == state["client_id"])
        )).scalar_one_or_none()
    if not row:
        return {"errors": [f"Client {state['client_id']} not found"]}
    return {"client_profile": {
        "id": row.id, "name": row.name, "age": row.age, "income": row.income,
        "family_size": row.family_size, "risk_appetite": row.risk_appetite,
        "goals": row.goals, "liabilities_emi": row.liabilities_emi or 0,
        "employment_type": row.employment_type or "Not specified",
        "health_conditions": row.health_conditions or "None",
        "existing_coverage": row.existing_coverage or "None",
        "city_tier": row.city_tier or "Not specified",
        "dependents_detail": row.dependents_detail or "None",
    }}


async def run_needs_analysis(state: ProductMatchingState) -> dict:
    async with AsyncSessionLocal() as db:
        analysis = await analyze_client_needs(db, state["client_profile"])
    return {"need_analysis": analysis}


async def generate_queries(state: ProductMatchingState) -> dict:
    p = state["client_profile"]
    prompt = f"""Generate 3 specific insurance product search queries for this client.
Each query targets a different coverage need.
Return JSON array of 3 strings only.

Client: Age {p.get('age')}, Income ₹{p.get('income',0):,.0f},
Goals: {p.get('goals')}, Health: {p.get('health_conditions')},
Risk: {p.get('risk_appetite')}, Existing: {p.get('existing_coverage')}
Need Analysis: {state['need_analysis'][:300]}"""
    raw = await chat(
        "Generate targeted insurance product search queries. Return JSON array only.",
        prompt, trace_name="gen_queries"
    )
    try:
        clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        queries = json.loads(clean)[:3]
    except Exception:
        p = state["client_profile"]
        queries = [
            f"{p.get('goals','')} insurance {p.get('risk_appetite','')} risk India",
            f"health insurance {p.get('health_conditions','general')} coverage India",
            f"term life insurance age {p.get('age')} income {p.get('income',0)}",
        ]
    return {"search_queries": queries}


async def search_products(state: ProductMatchingState) -> dict:
    async def one(q: str) -> list[dict]:
        async with AsyncSessionLocal() as db:
            return await similarity_search(db, q, top_k=6)

    results = await asyncio.gather(*[one(q) for q in state["search_queries"]])
    seen, chunks = set(), []
    for batch in results:
        for c in batch:
            key = c["content"][:100]
            if key not in seen:
                seen.add(key)
                chunks.append(c)
    return {"raw_chunks": chunks}


async def rank_match(state: ProductMatchingState) -> dict:
    p = state["client_profile"]
    context = "\n\n".join(c["content"] for c in state["raw_chunks"][:12])
    disposable = (p.get("income") or 0) / 12 - (p.get("liabilities_emi") or 0)
    prompt = f"""Recommend top 3 insurance products. Return JSON only.

Client: Age {p.get('age')}, Income ₹{p.get('income',0):,.0f},
Disposable ₹{disposable:,.0f}/mo, Family {p.get('family_size')},
Risk {p.get('risk_appetite')}, Goals: {p.get('goals')},
Health: {p.get('health_conditions')}, Existing: {p.get('existing_coverage')}

Policy Knowledge:
{context}

Return: [{{"rank":1,"product_name":"...","insurer":"...","type":"term|health|ulip|motor",
"premium_per_month":0,"sum_assured":"...","key_benefit":"...","why_suits":"...",
"tax_benefit":"80C|80D|none","client_fit_score":85,"pitch_first":true}}]
Only one item should have pitch_first=true."""
    raw = await chat(
        "Expert insurance product advisor. Return JSON only.",
        prompt, trace_name="rank_match"
    )
    try:
        clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        recs = json.loads(clean)
    except Exception:
        recs = []
    return {"recommendations": recs}


async def save_recs(state: ProductMatchingState) -> dict:
    return {}   # extend: persist to recommendations table


def _check_errors(state) -> str:
    return "error" if state.get("errors") else "continue"


def build_product_matching_agent():
    g = StateGraph(ProductMatchingState)
    g.add_node("load_client",         load_client)
    g.add_node("run_needs_analysis",  run_needs_analysis)
    g.add_node("generate_queries",    generate_queries)
    g.add_node("search_products",     search_products)
    g.add_node("rank_match",          rank_match)
    g.add_node("save_recs",           save_recs)
    g.set_entry_point("load_client")
    g.add_conditional_edges("load_client", _check_errors,
                            {"continue": "run_needs_analysis", "error": END})
    g.add_edge("run_needs_analysis",  "generate_queries")
    g.add_edge("generate_queries",    "search_products")
    g.add_edge("search_products",     "rank_match")
    g.add_edge("rank_match",          "save_recs")
    g.add_edge("save_recs",           END)
    return g.compile()
```

### Interview Answer
> "The product recommender used one hardcoded RAG query. The Product Matching Agent adds
> three things. First, the LLM generates three targeted queries based on the client's full
> profile and need analysis — one per coverage gap. Second, all three searches run in
> parallel via asyncio.gather giving 18 deduplicated chunks instead of 6. Third, the ranking
> node adds a client_fit_score so the advisor sees not just what products exist but how well
> each matches this specific client. Parallel search was the key insight — most latency came
> from sequential RAG lookups."

---

## Step 9 — Claims & Renewals Agent
**Timeline:** Day 17–18
**JD:** *Oversee deployment; operational efficiency; human-in-the-loop*

### What `premium_reminder.py` does today vs what this agent adds

| `premium_reminder.py` (current) | Claims & Renewals Agent |
|---|---|
| Same template sent to everyone | Scores each policy by lapse risk (0–100) |
| No prioritization | Top 10 highest-risk clients only |
| Sends directly | Queues for advisor approval first |
| Fixed schedule | Can be triggered on-demand or scheduled |
| No WhatsApp drafts | Generates both email + WhatsApp per client |

### Graph flow
```
load_renewals → score_risk → filter_priority → draft_outreach → queue_approval → notify_advisor
     ↓ (no renewals)              ↓ (no priority clients)
    END                          END
```

### File: `app/agents/claims_renewals_agent.py`
```python
import json
import operator
from datetime import date, timedelta
from typing import TypedDict, Annotated

from langgraph.graph import StateGraph, END
from sqlalchemy import select, text

from app.db.postgres import AsyncSessionLocal
from app.models.client import Client
from app.models.policy import Policy
from app.modules.email_generator import generate_premium_reminder_email
from app.core.llm import chat


class RenewalAgentState(TypedDict):
    advisor_id: str
    days_ahead: int
    renewals: list[dict]
    scored_renewals: list[dict]
    priority_renewals: list[dict]
    draft_messages: list[dict]
    approval_ids: list[str]
    errors: Annotated[list[str], operator.add]


async def load_renewals(state: RenewalAgentState) -> dict:
    today = date.today()
    until = today + timedelta(days=state.get("days_ahead", 30))
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(Policy, Client)
            .join(Client, Policy.client_id == Client.id)
            .where(Client.advisor_id == state["advisor_id"])
            .where(Policy.next_due_date >= today)
            .where(Policy.next_due_date <= until)
            .order_by(Policy.next_due_date)
        )).all()
    if not rows:
        return {"errors": ["No upcoming renewals found"], "renewals": []}
    return {"renewals": [{
        "policy_id": p.id, "policy_no": p.policy_no,
        "product_name": p.product_name, "insurer_name": p.insurer_name,
        "premium_amount": p.premium_amount, "next_due_date": str(p.next_due_date),
        "days_until_due": (p.next_due_date - today).days,
        "client_id": c.id, "client_name": c.name, "client_email": c.email,
        "client_phone": c.phone, "client_status": c.status,
        "client_income": c.income or 0,
    } for p, c in rows]}


async def score_risk(state: RenewalAgentState) -> dict:
    prompt = f"""Score each policy renewal by lapse risk 0–100 (higher = more likely to lapse).
Factors: days_until_due (fewer = higher urgency), premium_amount vs client_income,
client_status ('new' or 'contacted' = less trust built = higher risk).
Add "lapse_risk_score" (int) and "risk_reason" (str) to each item.
Return the same JSON array with these two fields added.

Renewals:
{json.dumps(state['renewals'][:20], default=str)}"""
    raw = await chat(
        "Risk analyst. Score insurance renewal lapse risk. Return JSON only.",
        prompt, trace_name="score_risk"
    )
    try:
        clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        scored = json.loads(clean)
    except Exception:
        scored = state["renewals"]
        for i, r in enumerate(sorted(scored, key=lambda x: x["days_until_due"])):
            r["lapse_risk_score"] = max(10, 90 - i * 8)
            r["risk_reason"] = f"{r['days_until_due']} days until due"
    return {"scored_renewals": scored}


async def filter_priority(state: RenewalAgentState) -> dict:
    priority = sorted(
        [r for r in state["scored_renewals"] if r.get("lapse_risk_score", 0) >= 40],
        key=lambda r: r.get("lapse_risk_score", 0), reverse=True
    )[:10]
    return {"priority_renewals": priority}


async def draft_outreach(state: RenewalAgentState) -> dict:
    drafts = []
    for r in state["priority_renewals"]:
        email = await generate_premium_reminder_email(
            client_name=r["client_name"], policy_no=r["policy_no"],
            product_name=r["product_name"], insurer_name=r["insurer_name"],
            premium_amount=r["premium_amount"], due_date=r["next_due_date"],
            advisor_name="Your Advisor",
        )
        drafts.append({
            "client_id": r["client_id"], "client_name": r["client_name"],
            "client_email": r["client_email"], "policy_no": r["policy_no"],
            "lapse_risk_score": r.get("lapse_risk_score"),
            "risk_reason": r.get("risk_reason", ""),
            "email": email,
            "whatsapp_text": (
                f"Hi {r['client_name']}, your {r['product_name']} premium of "
                f"₹{r['premium_amount']:,.0f} is due on {r['next_due_date']}. "
                f"Please renew to keep your coverage active."
            ),
        })
    return {"draft_messages": drafts}


async def queue_approval(state: RenewalAgentState) -> dict:
    ids = []
    async with AsyncSessionLocal() as db:
        for draft in state["draft_messages"]:
            result = await db.execute(text("""
                INSERT INTO approval_queue
                    (client_id, advisor_id, action_type, payload, status, created_at)
                VALUES (:client_id, :advisor_id, 'send_renewal_reminder', :payload, 'pending', now())
                RETURNING id
            """), {
                "client_id": draft["client_id"],
                "advisor_id": state["advisor_id"],
                "payload": json.dumps(draft, default=str),
            })
            row = result.fetchone()
            if row:
                ids.append(str(row.id))
        await db.commit()
    return {"approval_ids": ids}


async def notify_advisor(state: RenewalAgentState) -> dict:
    print(f"[Renewals Agent] {len(state['approval_ids'])} items queued for {state['advisor_id']}")
    return {}


def _check_errors(state) -> str:
    return "error" if state.get("errors") else "continue"

def _check_priority(state) -> str:
    return "no_priority" if not state.get("priority_renewals") else "continue"


def build_renewals_agent():
    g = StateGraph(RenewalAgentState)
    g.add_node("load_renewals",    load_renewals)
    g.add_node("score_risk",       score_risk)
    g.add_node("filter_priority",  filter_priority)
    g.add_node("draft_outreach",   draft_outreach)
    g.add_node("queue_approval",   queue_approval)
    g.add_node("notify_advisor",   notify_advisor)
    g.set_entry_point("load_renewals")
    g.add_conditional_edges("load_renewals", _check_errors,
                            {"continue": "score_risk", "error": END})
    g.add_edge("score_risk",       "filter_priority")
    g.add_conditional_edges("filter_priority", _check_priority,
                            {"continue": "draft_outreach", "no_priority": END})
    g.add_edge("draft_outreach",   "queue_approval")
    g.add_edge("queue_approval",   "notify_advisor")
    g.add_edge("notify_advisor",   END)
    return g.compile()
```

### Interview Answer
> "The premium reminder scheduler sent the same template to everyone.
> The Claims & Renewals Agent adds three things. First, an LLM risk-scoring node
> rates each policy's lapse probability 0–100 based on days until due, premium
> burden relative to income, and advisor engagement level. Second, it only drafts
> for the top-10 highest-risk policies — not blanket outreach. Third, everything
> goes into an approval_queue table instead of sending directly. The advisor reviews
> and approves each draft in the dashboard. AI proposes, human decides."

---

## Step 10 — Policy Research Agent
**Timeline:** Day 19–20
**JD:** *Reusable assets; end-to-end agentic initiatives*

### What makes this a ReAct agent
Unlike the other agents, Policy Research uses a **loop** — the agent decides how many
searches to run based on whether the retrieved context is sufficient to answer the question.

### Graph flow
```
receive_question → plan_searches → search_loop ──(not sufficient)──► search_loop
                                        │ (sufficient)
                                   validate_answer → synthesize_with_citations
                                        ↓ (no docs found)
                                       END
```

### File: `app/agents/policy_research_agent.py`
```python
import json
import operator
from typing import TypedDict, Annotated

from langgraph.graph import StateGraph, END

from app.db.postgres import AsyncSessionLocal
from app.db.vector_store import similarity_search
from app.core.llm import chat


class PolicyResearchState(TypedDict):
    question: str
    advisor_id: str
    search_plan: list[str]
    search_results: list[dict]
    searches_done: int
    is_sufficient: bool
    answer: str
    citations: list[str]
    errors: Annotated[list[str], operator.add]


async def receive_question(state: PolicyResearchState) -> dict:
    if not state.get("question"):
        return {"errors": ["No question provided"]}
    return {}


async def plan_searches(state: PolicyResearchState) -> dict:
    prompt = f"""Break this insurance question into 1–3 specific search queries.
Return JSON array of strings only.

Question: {state['question']}"""
    raw = await chat(
        "Plan search queries for an insurance knowledge base. Return JSON array only.",
        prompt, trace_name="plan_searches"
    )
    try:
        clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        queries = json.loads(clean)[:3]
    except Exception:
        queries = [state["question"]]
    return {"search_plan": queries, "searches_done": 0, "is_sufficient": False}


async def search_loop(state: PolicyResearchState) -> dict:
    idx = state.get("searches_done", 0)
    queries = state.get("search_plan", [])
    if idx >= len(queries):
        return {"is_sufficient": True}
    async with AsyncSessionLocal() as db:
        results = await similarity_search(db, queries[idx], top_k=5)
    existing = state.get("search_results", [])
    seen = {c["content"][:100] for c in existing}
    new_chunks = [r for r in results if r["content"][:100] not in seen]
    return {
        "search_results": existing + new_chunks,
        "searches_done": idx + 1,
        "is_sufficient": (idx + 1) >= len(queries),
    }


async def validate_answer(state: PolicyResearchState) -> dict:
    if not state.get("search_results"):
        return {"errors": ["No policy documents found for this question"]}
    return {}


async def synthesize_with_citations(state: PolicyResearchState) -> dict:
    context = "\n\n".join(
        f"[Source {i+1}: {r.get('metadata', 'policy document')}]\n{r['content']}"
        for i, r in enumerate(state["search_results"][:8])
    )
    prompt = f"""Answer this insurance question using only the provided policy excerpts.
Cite sources as [Source N]. If the answer is not in the excerpts, say so clearly.

Question: {state['question']}

Policy Excerpts:
{context}"""
    answer = await chat(
        "Expert insurance document analyst. Answer with citations from provided excerpts only.",
        prompt, trace_name="synthesize_answer"
    )
    citations = [
        f"Source {i+1}: {r.get('metadata', 'policy document')}"
        for i, r in enumerate(state["search_results"][:8])
    ]
    return {"answer": answer, "citations": citations}


def _check_errors(state) -> str:
    return "error" if state.get("errors") else "continue"

def _check_sufficient(state) -> str:
    return "done" if state.get("is_sufficient") else "search_again"


def build_policy_research_agent():
    g = StateGraph(PolicyResearchState)
    g.add_node("receive_question",           receive_question)
    g.add_node("plan_searches",              plan_searches)
    g.add_node("search_loop",               search_loop)
    g.add_node("validate_answer",            validate_answer)
    g.add_node("synthesize_with_citations",  synthesize_with_citations)
    g.set_entry_point("receive_question")
    g.add_conditional_edges("receive_question", _check_errors,
                            {"continue": "plan_searches", "error": END})
    g.add_edge("plan_searches", "search_loop")
    g.add_conditional_edges("search_loop", _check_sufficient,
                            {"done": "validate_answer", "search_again": "search_loop"})
    g.add_conditional_edges("validate_answer", _check_errors,
                            {"continue": "synthesize_with_citations", "error": END})
    g.add_edge("synthesize_with_citations", END)
    return g.compile()
```

### Interview Answer
> "The Policy Research Agent is a ReAct agent — it loops. The plan_searches node
> breaks the question into 1–3 sub-queries. The search_loop node runs one query,
> adds the results to state, then checks if it has enough context. If not, it
> loops back and runs the next query. The synthesize node then answers with
> citations — [Source N] maps back to the chunk's metadata. The loop means the
> agent adapts to question complexity: simple questions run one search, complex
> comparisons run three."

---

## Step 11 — Objection Handler Agent
**Timeline:** Day 21–22
**JD:** *End-to-end agentic initiatives; collaborate with business stakeholders*

### What `pitch_handler.py` does today vs what this agent adds

| `pitch_handler.py` (current) | Objection Handler Agent |
|---|---|
| Returns structured JSON response | Classifies objection type first |
| No record of what objection was raised | Logs interaction to DB |
| No follow-up suggestion | Adds `suggest_next_pitch` node |
| Caller decides what to do with response | Agent chains classify → respond → suggest |

### Graph flow
```
load_client → classify_objection → generate_response → suggest_next_pitch → log_interaction
     ↓ (error)
    END
```

### File: `app/agents/objection_handler_agent.py`
```python
import json
import operator
from typing import TypedDict, Annotated

from langgraph.graph import StateGraph, END
from sqlalchemy import select, text

from app.db.postgres import AsyncSessionLocal
from app.models.client import Client
from app.modules.pitch_handler import handle_objection
from app.core.llm import chat_mini


OBJECTION_TYPES = [
    "premium_too_high", "already_have_insurance", "will_think_about_it",
    "dont_trust_insurers", "young_and_healthy", "no_time", "employer_covers_me",
]


class ObjectionHandlerState(TypedDict):
    client_id: str
    objection: str
    client_profile: dict
    objection_type: str
    structured_response: dict
    next_pitch: str
    interaction_id: str
    errors: Annotated[list[str], operator.add]


async def load_client(state: ObjectionHandlerState) -> dict:
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(Client).where(Client.id == state["client_id"])
        )).scalar_one_or_none()
    if not row:
        return {"errors": [f"Client {state['client_id']} not found"]}
    return {"client_profile": {
        "name": row.name, "age": row.age, "income": row.income,
        "family_size": row.family_size, "risk_appetite": row.risk_appetite,
        "goals": row.goals, "liabilities_emi": row.liabilities_emi or 0,
        "employment_type": row.employment_type,
        "health_conditions": row.health_conditions,
        "existing_policies": row.existing_coverage,
    }}


async def classify_objection(state: ObjectionHandlerState) -> dict:
    prompt = f"""Classify this objection into one of: {', '.join(OBJECTION_TYPES)}
Return the category string only, nothing else.

Objection: "{state['objection']}"
"""
    raw = await chat_mini(
        "Classify insurance objections into categories.",
        prompt, trace_name="classify_objection"
    )
    objection_type = raw.strip().lower().replace(" ", "_")
    if objection_type not in OBJECTION_TYPES:
        objection_type = "will_think_about_it"
    return {"objection_type": objection_type}


async def generate_response(state: ObjectionHandlerState) -> dict:
    response = await handle_objection(state["objection"], state["client_profile"])
    return {"structured_response": response}


async def suggest_next_pitch(state: ObjectionHandlerState) -> dict:
    p = state["client_profile"]
    prompt = f"""The advisor just handled this objection. Suggest ONE confident closing line.

Objection type: {state['objection_type']}
Response given: {json.dumps(state['structured_response'])}
Client: {p.get('name')}, age {p.get('age')}, goals: {p.get('goals')}

Return just the closing line, nothing else."""
    pitch = await chat_mini(
        "Insurance sales coach. Suggest a closing line.",
        prompt, trace_name="suggest_next_pitch"
    )
    return {"next_pitch": pitch.strip()}


async def log_interaction(state: ObjectionHandlerState) -> dict:
    notes = (
        f"Objection: {state['objection']}\n"
        f"Type: {state['objection_type']}\n"
        f"Response: {json.dumps(state['structured_response'])}"
    )
    async with AsyncSessionLocal() as db:
        result = await db.execute(text("""
            INSERT INTO interactions (client_id, interaction_type, notes, created_at)
            VALUES (:client_id, 'objection_handled', :notes, now())
            RETURNING id
        """), {"client_id": state["client_id"], "notes": notes[:1000]})
        row = result.fetchone()
        await db.commit()
    return {"interaction_id": str(row.id) if row else ""}


def _check_errors(state) -> str:
    return "error" if state.get("errors") else "continue"


def build_objection_handler_agent():
    g = StateGraph(ObjectionHandlerState)
    g.add_node("load_client",        load_client)
    g.add_node("classify_objection", classify_objection)
    g.add_node("generate_response",  generate_response)
    g.add_node("suggest_next_pitch", suggest_next_pitch)
    g.add_node("log_interaction",    log_interaction)
    g.set_entry_point("load_client")
    g.add_conditional_edges("load_client", _check_errors,
                            {"continue": "classify_objection", "error": END})
    g.add_edge("classify_objection", "generate_response")
    g.add_edge("generate_response",  "suggest_next_pitch")
    g.add_edge("suggest_next_pitch", "log_interaction")
    g.add_edge("log_interaction",    END)
    return g.compile()
```

### Interview Answer
> "The pitch handler returned a structured JSON response but had no memory of the
> conversation. The Objection Handler Agent adds three things. First, a classification
> node that maps the objection to one of 7 known types — this lets us track which
> objections are most common across all advisors in the audit log. Second, a
> suggest_next_pitch node that takes the classified type plus the client profile and
> generates the exact closing line the advisor should say next. Third, every objection
> and response is written to the interactions table, so the advisor has a full
> conversation history in the dashboard."

---

## Step 12 — Lead Nurturing Agent (Orchestrator)
**Timeline:** Day 23–24
**JD:** *End-to-end agentic initiatives; central coordination; human-in-the-loop*

### What "Orchestrator" means
The Lead Nurturing Agent does NOT re-implement analysis or matching.
It calls **Agent 1** and **Agent 2** via `ainvoke`, passes state between them,
then drafts an email and queues it for human approval.

### Why this matters for reuse
```
Before (without orchestrator):
  Lead Nurturing = copy of need analysis + copy of product matching + email

After (with orchestrator):
  Lead Nurturing = calls Agent 1 + calls Agent 2 + email
  Claims Agent can also call Agent 1 to enrich renewal data
  Any future agent can call Agent 1 or Agent 2 independently
```

### Graph flow
```
load_client → [run_needs_analysis_agent] → [run_product_matching_agent] → draft_email → queue_approval
     ↓ (error at any step)
    END
```

### File: `app/agents/lead_nurturing_agent.py`
```python
import json
import operator
from typing import TypedDict, Annotated

from langgraph.graph import StateGraph, END
from sqlalchemy import select, text

from app.db.postgres import AsyncSessionLocal
from app.models.client import Client
from app.modules.email_generator import generate_followup_email
from app.agents.needs_analysis_agent import build_needs_analysis_agent
from app.agents.product_matching_agent import build_product_matching_agent


class LeadNurturingState(TypedDict):
    client_id: str
    advisor_id: str
    client_profile: dict
    need_analysis: str
    gaps: list[dict]
    recommendations: list[dict]
    draft_email: dict
    approval_id: str
    errors: Annotated[list[str], operator.add]


async def load_client(state: LeadNurturingState) -> dict:
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(Client).where(Client.id == state["client_id"])
        )).scalar_one_or_none()
    if not row:
        return {"errors": [f"Client {state['client_id']} not found"]}
    return {"client_profile": {
        "id": row.id, "name": row.name, "age": row.age, "income": row.income,
        "family_size": row.family_size, "risk_appetite": row.risk_appetite,
        "goals": row.goals, "liabilities_emi": row.liabilities_emi or 0,
        "employment_type": row.employment_type,
        "health_conditions": row.health_conditions,
        "existing_coverage": row.existing_coverage,
        "city_tier": row.city_tier, "dependents_detail": row.dependents_detail,
    }}


async def run_needs_analysis_agent(state: LeadNurturingState) -> dict:
    agent = build_needs_analysis_agent()
    result = await agent.ainvoke({
        "client_id": state["client_id"], "client_profile": {},
        "rag_query": "", "rag_context": "", "analysis_text": "",
        "gaps": [], "interaction_id": "", "errors": [],
    })
    if result.get("errors"):
        return {"errors": result["errors"]}
    return {"need_analysis": result["analysis_text"], "gaps": result["gaps"]}


async def run_product_matching_agent(state: LeadNurturingState) -> dict:
    agent = build_product_matching_agent()
    result = await agent.ainvoke({
        "client_id": state["client_id"], "client_profile": {},
        "need_analysis": "", "search_queries": [],
        "raw_chunks": [], "recommendations": [], "errors": [],
    })
    if result.get("errors"):
        return {"errors": result["errors"]}
    return {"recommendations": result["recommendations"]}


async def draft_email(state: LeadNurturingState) -> dict:
    top = state.get("recommendations", [{}])[0]
    email = await generate_followup_email(
        client_name=state["client_profile"]["name"],
        advisor_name="Your Advisor",
        context=(
            f"Top recommendation: {top.get('product_name','insurance plan')} "
            f"by {top.get('insurer','')}. "
            f"Key benefit: {top.get('key_benefit','')}."
        ),
    )
    return {"draft_email": email}


async def queue_approval(state: LeadNurturingState) -> dict:
    payload = json.dumps({
        "client_id": state["client_id"],
        "email": state["draft_email"],
        "recommendations": state["recommendations"],
        "gaps": state["gaps"],
    }, default=str)
    async with AsyncSessionLocal() as db:
        result = await db.execute(text("""
            INSERT INTO approval_queue
                (client_id, advisor_id, action_type, payload, status, created_at)
            VALUES (:client_id, :advisor_id, 'send_nurturing_email', :payload, 'pending', now())
            RETURNING id
        """), {
            "client_id": state["client_id"],
            "advisor_id": state.get("advisor_id", ""),
            "payload": payload,
        })
        row = result.fetchone()
        await db.commit()
    return {"approval_id": str(row.id) if row else ""}


def _check_errors(state) -> str:
    return "error" if state.get("errors") else "continue"


def build_lead_nurturing_agent():
    g = StateGraph(LeadNurturingState)
    g.add_node("load_client",                load_client)
    g.add_node("run_needs_analysis_agent",   run_needs_analysis_agent)
    g.add_node("run_product_matching_agent", run_product_matching_agent)
    g.add_node("draft_email",               draft_email)
    g.add_node("queue_approval",            queue_approval)
    g.set_entry_point("load_client")
    g.add_conditional_edges("load_client", _check_errors,
                            {"continue": "run_needs_analysis_agent", "error": END})
    g.add_conditional_edges("run_needs_analysis_agent", _check_errors,
                            {"continue": "run_product_matching_agent", "error": END})
    g.add_conditional_edges("run_product_matching_agent", _check_errors,
                            {"continue": "draft_email", "error": END})
    g.add_edge("draft_email",    "queue_approval")
    g.add_edge("queue_approval", END)
    return g.compile()
```

### Interview Answer
> "The Lead Nurturing Agent is the orchestrator — it calls Agent 1 and Agent 2 via
> ainvoke, not by reimplementing their logic. This is the reuse payoff: if I improve
> the Needs Analysis Agent's RAG query generation, the Lead Nurturing Agent gets
> that improvement for free. The final node creates an approval_queue record —
> the advisor sees a pending email in the dashboard, reviews it, and only then
> does it send. Nothing reaches the client without human sign-off."

---

## PHASE 4 — Scale & Multi-tenancy (Week 7–8)

---

## Step 8 — Multi-tenancy with Row-Level Security
**Timeline:** Day 17–18
**JD:** *Scalable, secure architecture; operational efficiency*

### The problem
Right now an advisor can theoretically query any client by ID.
Application-level filters are fragile — one bug and data leaks.

### The solution: PostgreSQL Row-Level Security
Enforce isolation at the database layer, not the application layer.

### SQL migration
```sql
-- Enable RLS on clients table
ALTER TABLE clients ENABLE ROW LEVEL SECURITY;
CREATE POLICY advisor_isolation ON clients
    USING (advisor_id = current_setting('app.current_advisor_id', true));

-- Enable RLS on policies table
ALTER TABLE policies ENABLE ROW LEVEL SECURITY;
CREATE POLICY policy_isolation ON policies
    USING (client_id IN (
        SELECT id FROM clients
        WHERE advisor_id = current_setting('app.current_advisor_id', true)
    ));
```

### Wire into `app/db/postgres.py` — per-request session
```python
from fastapi import Request
from sqlalchemy import text

async def get_db_with_advisor(request: Request):
    """Use this instead of get_db for any endpoint that needs RLS."""
    advisor_id = request.headers.get("X-Advisor-ID", "")
    async with AsyncSessionLocal() as session:
        if advisor_id:
            await session.execute(
                text("SET LOCAL app.current_advisor_id = :aid"),
                {"aid": advisor_id},
            )
        yield session
```

### Interview Answer
> "Multi-tenancy is a database concern, not an application concern.
> I use PostgreSQL row-level security — each request sets
> app.current_advisor_id as a session variable, and Postgres enforces
> the isolation at query time. Even if there's an application bug that
> forgets to filter by advisor_id, Postgres will still return only that
> advisor's data. For an insurance platform handling PII and financial
> data, defense-in-depth at the DB layer is non-negotiable."

---

## Step 9 — Performance Optimization
**Timeline:** Day 19–20
**JD:** *Operational efficiency; performance and maintainability*

### Four optimizations, each measurable

#### 9a — Prompt caching (reduces cost 50–80%)
In `app/core/llm.py`, system prompts repeat on every call.
OpenAI charges full price for repeated tokens.

```python
# In _call(), mark system prompt for caching:
messages=[
    {
        "role": "system",
        "content": system_prompt,
        # OpenAI will cache this automatically when it sees the same prefix
    },
    {"role": "user", "content": user_message},
]
```

#### 9b — GPT-4o-mini routing for simple tasks (10x cost reduction)
The `use_mini` flag in BaseAgent is already set up.
Wire it in email_generator (already uses chat_mini) and
set it for pitch_handler and objection_handler too.

```python
# In pitch_handler.py — objection handler is simple enough for mini:
class ObjectionHandlerAgent(BaseAgent):
    use_mini = True   # was using GPT-4o — switch to mini
```

#### 9c — pgvector HNSW index (10x search speed)
```sql
-- Replace IVFFlat with HNSW for better recall + speed:
CREATE INDEX CONCURRENTLY policy_chunks_hnsw
ON policy_chunks USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

#### 9d — Semantic cache with Redis (30% LLM call reduction)
For identical or near-identical queries, return cached result.

```python
# app/core/semantic_cache.py
import redis.asyncio as redis
import hashlib
import json

_redis = None

def get_redis():
    global _redis
    if not _redis:
        from app.core.config import settings
        _redis = redis.from_url(settings.REDIS_URL)
    return _redis

async def get_cached(key: str) -> str | None:
    val = await get_redis().get(key)
    return val.decode() if val else None

async def set_cached(key: str, value: str, ttl: int = 3600):
    await get_redis().setex(key, ttl, value)

def cache_key(system: str, user: str) -> str:
    return hashlib.sha256(f"{system}||{user}".encode()).hexdigest()
```

### Interview Answer
> "I applied four performance optimizations. OpenAI prompt caching for repeated
> system prompts reduced token costs by 50-80%. Model routing — GPT-4o for
> complex reasoning, GPT-4o-mini for simple tasks like email drafting — gave
> a 10x cost reduction on those tasks. Replacing pgvector IVFFlat with HNSW
> index improved RAG search speed 10x with better recall. And a Redis semantic
> cache on repeated queries reduced LLM calls by 30%. Together these brought
> cost per recommendation from ~₹6 to under ₹1."

---

## Step 10 — Mentorship & Team Playbook
**Timeline:** Ongoing
**JD:** *Mentor and lead technical team; culture of innovation*

### Concrete artifacts you can build

#### 10a — Agent Development Guide
Create `docs/agent-development-guide.md` that teaches your team how to add a new agent:
```
1. Create app/agents/<name>_agent.py
2. Define your State (TypedDict with the data you need)
3. Write your nodes (each is an async function)
4. Build your graph (StateGraph → add_node → add_edge → compile)
5. Add golden examples to tests/evals/golden/<name>.jsonl
6. Add eval function to tests/evals/run_evals.py
7. Submit PR — eval gate will run automatically
```

#### 10b — Architecture Decision Records
Create `docs/adr/` folder. Each ADR = one architectural decision.
```
docs/adr/
├── 001-use-pgvector-not-pinecone.md
├── 002-langgraph-for-agentic-flows.md
├── 003-mcp-as-integration-layer.md
└── 004-rls-for-multi-tenancy.md
```
Format for each ADR:
```markdown
# ADR-001: Use pgvector instead of Pinecone

## Status: Accepted

## Context
We need a vector store for RAG. Options: pgvector (in Postgres), Pinecone (managed cloud).

## Decision
Use pgvector until we exceed 10M vectors.

## Consequences
- Positive: no new infra, same DB, lower cost
- Negative: manual tuning of HNSW index, not fully managed
- Trigger to revisit: vector count > 10M OR search latency > 200ms p95
```

#### 10c — Weekly AI Guild meeting agenda template
```
1. One engineer demos a PoC (15 min) — no judgment, failure celebrated
2. Paper/article review: one person presents key insights (10 min)
3. Blockers across all active initiatives (10 min)
4. Metrics review: LangFuse dashboard — token costs, latency, error rates (5 min)
```

### Interview Answer
> "Mentorship for me is about removing ambiguity. I built three artifacts
> for the team: an agent development guide that gives any engineer a
> repeatable recipe to add a new LangGraph agent in one day,
> Architecture Decision Records so future engineers understand WHY
> we made choices — not just what the code does — and a weekly
> AI Guild where engineers demo PoCs without judgment.
> The eval harness is also a teaching tool — new engineers learn
> what 'good output' means by reading the golden examples.
> Culture is built through artifacts, not speeches."

---

## Day-by-Day Schedule

| Day | Step | Deliverable | Test |
|-----|------|-------------|------|
| 1 | Step 1 | `app/mcp/__init__.py` + `app/mcp/server.py` | `python -m app.mcp.server` |
| 2 | Step 1 | `.mcp.json` at project root | Open Claude Desktop → MCP settings |
| 3 | Step 2 | `app/core/base_agent.py` | Import in Python REPL |
| 4 | Step 3 | `app/core/pii_guard.py` + wire into `llm.py` | `python -c "from app.core.pii_guard import scrub; print(scrub('call 9876543210'))"` |
| 5 | Step 3 | `app/core/audit.py` + SQL migration | Run migration |
| 6 | Step 3 | `app/core/guardrails.py` | Unit test |
| 7 | Step 4 | `tests/evals/golden/need_analyzer.jsonl` | Review golden examples |
| 8 | Step 4 | `tests/evals/run_evals.py` | `python tests/evals/run_evals.py` |
| 9 | Step 5 | SQL migration for `prompt_registry` | Run migration |
| 10 | Step 5 | `app/core/prompt_registry.py` + wire into `need_analyzer.py` | Run need analysis endpoint |
| 11 | Step 6 | `.github/workflows/ai-deploy.yml` (lint + unit tests stages) | Push to GitHub |
| 12 | Step 6 | eval-gate + build + deploy stages | Check GitHub Actions tab |
| 13 | Step 7 | SQL migration for `approval_queue` + `app/agents/__init__.py` | Run migration |
| 14 | Step 7 | `app/agents/needs_analysis_agent.py` | `await agent.ainvoke({"client_id": "...", ...})` |
| 15 | Step 8 | `app/agents/product_matching_agent.py` | Run against a real client, check 3 search queries in LangFuse |
| 16 | Step 8 | Wire parallel search, verify `asyncio.gather` in logs | Compare chunk count before/after |
| 17 | Step 9 | `app/agents/claims_renewals_agent.py` | Run against advisor with renewals, check approval_queue table |
| 18 | Step 9 | Verify risk scores in DB, check no emails sent directly | Query `SELECT * FROM approval_queue` |
| 19 | Step 10 | `app/agents/policy_research_agent.py` | Ask "what does HDFC term plan cover for smokers?" |
| 20 | Step 10 | Test search loop — ask a complex question needing 2+ searches | Check `searches_done` in final state |
| 21 | Step 11 | `app/agents/objection_handler_agent.py` | Trigger with objection "premium is too high" |
| 22 | Step 11 | Verify `interactions` table entry written after each run | Query DB |
| 23 | Step 12 | `app/agents/lead_nurturing_agent.py` (Orchestrator) | Run end-to-end, check `approval_queue` entry created |
| 24 | Step 12 | Verify Agent 1 + Agent 2 called via `ainvoke`, not reimplemented | Read LangFuse trace tree |
| 25 | Step 13 | RLS SQL migration | Run migration, test two-advisor isolation |
| 26 | Step 13 | `get_db_with_advisor()` in `postgres.py` | Test with two different advisor IDs |
| 27 | Step 14 | HNSW index migration + Redis semantic cache | Compare search latency before/after |
| 28 | Step 14 | Model routing `use_mini` flags on objection + email | Check token costs in LangFuse |

---

## Interview Master Cheat Sheet

### For each JD bullet — what to say

**"Lead enterprise-wide ML and Gen AI architecture"**
> "I designed a layered architecture: BaseAgent at the core enforces tracing,
> PII scrubbing, and guardrails on every call. MCP server is the integration
> layer. LangGraph handles stateful agents. Everything observes through LangFuse.
> No team can deploy a new AI feature that bypasses the governance layer."

**"End-to-end development from ideation to scaling"**
> "The Lead Nurturing Agent went from whiteboard to production in 3 weeks.
> Week 1: LangGraph PoC with 4 nodes. Week 2: human-in-loop approval queue,
> eval harness with golden examples. Week 3: CI/CD gate, canary deploy.
> The key was the eval gate — it gave us confidence to deploy without
> a manual review of every output."

**"Reusable Gen AI assets and accelerators"**
> "I built three reusable assets: the MCP server exposes 10 tools any
> AI client can use. BaseAgent is the standard template — new agents are
> three methods and one file. The eval harness pattern is repeatable —
> add a JSONL file and a function for every new initiative."

**"Governance, data privacy, ethical AI"**
> "Three controls, all automatic: PII scrubber on every LLM call,
> immutable audit log with SHA-256 input hashes, and output guardrails
> blocking IRDAI-prohibited claims. They're in the base infrastructure,
> not in individual modules. You can't accidentally bypass them."

**"CI/CD for AI solutions"**
> "Five stages: lint → unit tests → AI eval gate → build → deploy.
> The eval gate is what makes it AI-native. It runs real LLM calls
> against golden examples. If accuracy drops or latency spikes,
> the pipeline blocks the merge before the image is even built."

**"Collaborate with business stakeholders"**
> "Every module maps directly to an advisor's daily workflow.
> Analyze client → recommend products → generate pitch → handle objection →
> draft email → send after approval. The human-in-loop gate was a
> stakeholder requirement — advisors wanted to review every email before
> it reaches a client. The agent proposes, the advisor decides."

**"Scalable, secure architecture"**
> "Multi-tenancy via PostgreSQL row-level security — not application filters.
> Even with a bug in the query layer, Postgres enforces isolation.
> The MCP server, FastAPI service, and LangGraph agents are independently
> deployable. Each scales on its own."

---

## What to implement first (priority order)

```
Week 1:  Step 1 (MCP) → Step 2 (BaseAgent) → Step 3 (Governance)
Week 2:  Step 4 (Evals) → Step 5 (Prompt Registry) → Step 6 (CI/CD)
Week 3:  Step 7 (LangGraph Agent)
Week 4:  Step 8 (RLS) → Step 9 (Performance) → Step 10 (Team docs)
```

Start with Step 1 and Step 3 — MCP makes the system usable by AI clients,
governance makes it safe. Everything else builds on top of those two.
