# Phase 1 — Foundation Testing Guide

## Prerequisites

```bash
source .venv/bin/activate
```

---

## Step 1 — Governance Layer (no DB, no API key)

### PII Guard

```bash
python3 -c "
from app.core.pii_guard import scrub

print(scrub('Aadhaar: 1234 5678 9012'))      # [AADHAAR-REDACTED]
print(scrub('PAN: ABCDE1234F'))               # [PAN-REDACTED]
print(scrub('Call me on 9876543210'))         # [PHONE-REDACTED]
print(scrub('Email: rahul@hdfc.com'))         # [EMAIL-REDACTED]
print(scrub('No PII here, safe to send'))     # unchanged
"
```

### Guardrails

```bash
python3 -c "
from app.core.guardrails import validate_output

print(validate_output('Term insurance is a good choice for your family'))

try:
    validate_output('This plan offers guaranteed returns of 12%')
except ValueError as e:
    print('BLOCKED:', e)

try:
    validate_output('100% safe investment with no risk')
except ValueError as e:
    print('BLOCKED:', e)
"
```

---

## Step 2 — BaseAgent (no DB, no API key)

```bash
python3 -c "
from app.core.base_agent import BaseAgent, AgentInput

class TestInput(AgentInput):
    name: str

class EchoAgent(BaseAgent):
    trace_name = 'echo_test'
    use_mini = True
    def system_prompt(self): return 'Reply with: Hello {name}'
    def build_prompt(self, input: TestInput): return f'name={input.name}'

print('BaseAgent subclass: OK')
print('use_mini:', EchoAgent.use_mini)
print('trace_name:', EchoAgent.trace_name)
"
```

---

## Step 3 — Audit Log (needs DB)

### Run migration

```bash
psql $DATABASE_URL -f migrations/governance.sql
```

### Write a test record

```bash
python3 -c "
import asyncio
from app.core.audit import log_ai_decision
from app.db.postgres import AsyncSessionLocal

async def test():
    async with AsyncSessionLocal() as db:
        await log_ai_decision(
            db=db,
            trace_name='test_audit',
            input_text='Client Rahul age 32 needs term insurance',
            model='gpt-4o',
            tokens_in=120,
            tokens_out=400,
            latency_ms=980,
            client_id='test-client-001',
            advisor_id='test-advisor-001',
        )
        print('Audit log written OK')

asyncio.run(test())
"
```

### Verify in DB

```bash
psql $DATABASE_URL -c "
SELECT trace_name, model, tokens_in, latency_ms, outcome, created_at
FROM ai_audit_log
ORDER BY created_at DESC
LIMIT 3;
"
```

---

## Step 4 — MCP Server (needs DB + API key)

### Syntax check (no DB)

```bash
python3 -c "
import ast, pathlib
src = pathlib.Path('app/mcp/server.py').read_text()
ast.parse(src)
print('MCP server syntax: OK')
"
```

### Start the server

```bash
python -m app.mcp.server
# Expected: Starting MCP server "Insurance Advisor AI"
# Ctrl+C to stop
```

### Interactive inspector

```bash
pip install "mcp[cli]"
mcp dev app/mcp/server.py
# Opens http://localhost:5173 — lists all 10 tools, lets you call them
```

### Claude Desktop integration

1. Open Claude Desktop → Settings → Developer → Edit Config
2. Claude Code picks up `.mcp.json` automatically from the project root
3. Start a new chat — 10 tools appear in the tool picker

---

## Step 5 — PII guard wired into LLM (needs API key)

```bash
python3 -c "
import asyncio
from app.core.llm import chat

async def test():
    result = await chat(
        'You are a helpful assistant.',
        'Summarize: client Rahul, phone 9876543210, needs health insurance',
        trace_name='pii_wire_test'
    )
    print('LLM response received (phone was scrubbed before sending)')
    print(result[:200])

asyncio.run(test())
"
```

---

## Summary

| Component     | Needs DB | Needs API key |
|---------------|----------|---------------|
| PII guard     | No       | No            |
| Guardrails    | No       | No            |
| BaseAgent     | No       | No            |
| Audit log     | Yes      | No            |
| MCP server    | Yes      | Yes           |
| LLM PII wire  | No       | Yes           |
