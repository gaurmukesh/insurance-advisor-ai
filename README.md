# Insurance Advisor AI

An enterprise-grade AI platform for insurance advisors — agentic lead management, AI-powered need analysis, product recommendations, pitch generation, objection handling, and automated client communications.

---

## Features

| Feature | Status |
|---|---|
| Client need analysis (AI) | ✅ |
| Product recommendations via RAG | ✅ |
| Lead management (CRUD + status tracking) | ✅ |
| Premium reminder emails (SendGrid) | ✅ |
| WhatsApp reminders (Meta Cloud API) | ✅ |
| Pitch & objection handler | ✅ |
| Policy document assistant (PDF upload + RAG) | ✅ |
| Business metrics dashboard | ✅ |
| Human-in-loop email approval queue | ✅ |
| MCP server (10 tools for Claude Desktop / Claude Code) | ✅ |
| LangGraph agentic pipeline (6 agents) | ✅ |
| Governance: PII guard + audit log + IRDAI guardrails | ✅ |
| Prompt registry (versioned prompts in Postgres) | ✅ |
| Semantic cache (Redis) | ✅ |
| Rate-limited login (brute-force protection) | ✅ |
| Product knowledge graph (coverage/exclusion overlap + gap detection) | ✅ |
| CI/CD with AI eval gate | ✅ |
| Row-level security (multi-advisor isolation) | ✅ |
| HNSW vector index (fast similarity search) | ✅ |
| Next.js advisor dashboard | ✅ |
| LangFuse + Sentry observability | ✅ |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    ENTERPRISE AI PLATFORM                        │
│                                                                   │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────────────┐ │
│  │  MCP Server  │   │  REST API    │   │  LangGraph Agents    │ │
│  │  (10 tools)  │   │  (FastAPI)   │   │  (6 agents)          │ │
│  └──────┬───────┘   └──────┬───────┘   └──────────┬───────────┘ │
│         └──────────────────┴────────────────────────┘            │
│                            │                                      │
│              ┌─────────────▼─────────────┐                       │
│              │       BaseAgent Core       │                       │
│              │  PII Guard · Audit Log ·   │                       │
│              │  Guardrails · LangFuse     │                       │
│              └─────────────┬─────────────┘                       │
│                            │                                      │
│         ┌──────────────────┼──────────────────┐                  │
│         ▼                  ▼                  ▼                   │
│   ┌───────────┐    ┌──────────────┐   ┌──────────────┐          │
│   │ PostgreSQL │    │  pgvector    │   │  Prompt      │          │
│   │   + RLS    │    │ (HNSW index) │   │  Registry    │          │
│   └───────────┘    └──────────────┘   └──────────────┘          │
│                                                                   │
│         ┌──────────────────────────────────────┐                 │
│         │       Redis Semantic Cache            │                 │
│         └──────────────────────────────────────┘                 │
│                                                                   │
│              ┌─────────────────────────────┐                     │
│              │  CI/CD: lint→test→eval→deploy│                     │
│              └─────────────────────────────┘                     │
└─────────────────────────────────────────────────────────────────┘
```

### LangGraph Agents

| Agent | Role |
|---|---|
| `NeedsAnalysisAgent` | Identifies coverage gaps and 80C/80D tax opportunities |
| `ProductMatchingAgent` | Parallel RAG search across policy docs for top-3 matches |
| `ClaimsRenewalsAgent` | Scores renewal risk; drafts reminders to approval queue |
| `PolicyResearchAgent` | Multi-hop document search for complex policy questions |
| `ObjectionHandlerAgent` | Structured rebuttal generation for common objections |
| `LeadNurturingAgent` | Orchestrator — chains agents end-to-end per lead lifecycle |

### Governance Layer

- **PII Guard** — strips Aadhaar, PAN, phone, and email before every LLM call
- **Audit Log** — immutable SHA-256-hashed record of every AI decision in Postgres
- **IRDAI Guardrails** — blocks outputs containing prohibited marketing claims ("guaranteed returns", "no risk", etc.)
- **Prompt Registry** — versioned prompts stored in Postgres; update without redeployment

### Product Knowledge Graph

Structured facts layered on top of RAG, not a replacement for it. At ingestion time, product spec PDFs (e.g. "Coverage Summary" / "Key Exclusions" templates) are parsed by an LLM into `Product` → `CoverageItem`/`ExclusionItem` rows against a closed category vocabulary (`hospitalisation`, `critical_illness`, `pre_existing_disease`, ...), so cross-insurer phrasing differences don't block matching. A PDF that looks like a named individual's *issued* policy rather than a generic product template is skipped by a doc-type gate (`app/core/rag.py::_looks_like_product_template`) — no PII reaches the extraction call.

Each client's actual `Policy` rows link to a `Product` by exact insurer/product-name match (`app/core/knowledge_graph.py::link_policy_to_product`) at creation time. `find_coverage_overlaps` and `find_coverage_gaps` then feed a "Structured Facts" section into every need-analysis/recommendation prompt — both LangGraph agents, the MCP tools, and the REST recommendation routes — so the LLM reasons over the client's real owned coverage, not just semantically-retrieved prose.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python FastAPI (async) |
| Agents | LangGraph |
| MCP | `mcp` (FastMCP server) |
| Database | PostgreSQL + pgvector (HNSW index) |
| Cache | Redis (semantic deduplication) |
| LLM | OpenAI GPT-4o / GPT-4o-mini |
| Embeddings | OpenAI text-embedding-3-small |
| Email | SendGrid |
| WhatsApp | Meta Cloud API |
| Observability | LangFuse + Sentry |
| Frontend | Next.js 15 + Tailwind CSS + React Query |
| CI/CD | GitHub Actions (lint → tests → AI eval gate → deploy) |
| Linter | Ruff |
| Container | Docker + docker-compose |

---

## Project Structure

```
insurance-advisor-ai/
├── app/
│   ├── agents/                  # LangGraph agents
│   │   ├── needs_analysis_agent.py
│   │   ├── product_matching_agent.py
│   │   ├── claims_renewals_agent.py
│   │   ├── policy_research_agent.py
│   │   ├── objection_handler_agent.py
│   │   └── lead_nurturing_agent.py  # Orchestrator
│   ├── api/routes/              # FastAPI route handlers
│   ├── core/
│   │   ├── base_agent.py        # Abstract base all agents inherit
│   │   ├── llm.py               # OpenAI client + PII scrub + semantic cache
│   │   ├── pii_guard.py         # Regex scrubber (Aadhaar/PAN/phone/email)
│   │   ├── audit.py             # Immutable AI decision log
│   │   ├── guardrails.py        # IRDAI output validation
│   │   ├── prompt_registry.py   # Versioned prompts from Postgres
│   │   ├── semantic_cache.py    # Redis-backed LLM response cache
│   │   ├── rate_limit.py        # slowapi limiter (10/min on /login)
│   │   ├── knowledge_graph.py   # Coverage overlap/gap queries, policy<->product linking
│   │   ├── product_extraction.py # LLM extraction of coverage/exclusion facts at ingest
│   │   ├── config.py
│   │   └── observability.py     # LangFuse + Sentry init
│   ├── mcp/
│   │   └── server.py            # MCP server — 10 tools for Claude Desktop
│   ├── modules/                 # Core AI modules
│   ├── models/                  # SQLAlchemy ORM models
│   │   └── product.py           # Product / CoverageItem / ExclusionItem / PolicyProductLink
│   ├── db/
│   │   ├── postgres.py          # Async engine + RLS session dependency
│   │   └── vector_store.py      # pgvector store + similarity search
│   └── scheduler/
├── dashboard/                   # Next.js frontend
│   └── app/
│       ├── leads/               # Lead list + detail + pitch
│       ├── documents/           # Policy document assistant
│       └── metrics/             # Business metrics dashboard
├── migrations/
│   ├── init.sql                 # Base schema
│   ├── agents.sql               # approval_queue + interactions tables
│   ├── governance.sql           # ai_audit_log + prompt_registry tables
│   ├── hnsw_index.sql           # HNSW index on embeddings
│   └── rls.sql                  # Row-level security policies
├── tests/
│   ├── evals/
│   │   ├── golden/              # Golden JSONL examples per agent
│   │   └── run_evals.py         # Eval scorer (accuracy + latency)
│   └── test_mcp_server.py
├── .github/workflows/
│   └── ai-deploy.yml            # CI/CD: lint → tests → eval gate → deploy
├── .mcp.json                    # MCP server config for Claude Desktop
├── ruff.toml
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

---

## Local Setup

### Prerequisites
- Docker + Docker Compose
- Python 3.11+
- Node.js 18+
- Redis (optional — semantic cache degrades gracefully without it)

### 1. Clone and configure

```bash
git clone https://github.com/gaurmukesh/insurance-advisor-ai.git
cd insurance-advisor-ai
cp .env.example .env
```

Edit `.env`:

```env
# Required
OPENAI_API_KEY=sk-...
SENDGRID_API_KEY=SG....
SENDGRID_FROM_EMAIL=you@example.com
DATABASE_URL=postgresql+asyncpg://admin:secret@localhost:5432/insurance_ai
SYNC_DATABASE_URL=postgresql://admin:secret@localhost:5432/insurance_ai

# Optional — observability
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PUBLIC_KEY=pk-lf-...

# Optional — semantic cache
REDIS_URL=redis://localhost:6379

# Optional — WhatsApp
WHATSAPP_PHONE_NUMBER_ID=...
WHATSAPP_ACCESS_TOKEN=...

# Optional — S3-backed policy PDF ingestion (falls back to local data/policies/ if unset)
AWS_REGION=ap-south-1
POLICIES_S3_BUCKET=...
POLICIES_S3_PREFIX=
POLICIES_SQS_QUEUE_URL=...   # set after running scripts/setup_s3_ingestion.py
```

### 2. Start the database

```bash
docker compose up -d db
```

### 3. Run migrations

`scripts/apply_migrations.py` records each applied file in a `schema_migrations`
ledger table and skips what's already there, so it's safe to re-run (this is
what CI/CD uses against prod — see `.github/workflows/ai-deploy.yml`):

```bash
python scripts/apply_migrations.py "$SYNC_DATABASE_URL" \
  migrations/init.sql migrations/agents.sql migrations/governance.sql \
  migrations/whatsapp_logs.sql migrations/email_logs_add_edited_body.sql \
  migrations/rls.sql migrations/hnsw_index.sql migrations/auth.sql \
  migrations/roles.sql migrations/mcp_tokens.sql
```

Note: `policies`, `clients`, `advisors`, and the product-knowledge-graph tables
(`products`, `coverage_items`, `exclusion_items`, `policy_product_link`) are
SQLAlchemy ORM models, created automatically by `init_db()` on app startup —
not part of the `migrations/` directory.

### 4. Run the API

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API: `http://localhost:8000` · Swagger: `http://localhost:8000/docs`

### 5. Run the dashboard

```bash
cd dashboard
npm install
npm run dev
```

Dashboard: `http://localhost:3000`

### 6. Ingest policy PDFs (for RAG)

```bash
curl -X POST http://localhost:8000/api/v1/ingest \
  -F "file=@data/policies/sample_policy.pdf"
```

---

## MCP Server (Claude Desktop / Claude Code)

The `.mcp.json` at the project root auto-configures Claude Code. For Claude Desktop, add to MCP settings:

```json
{
  "mcpServers": {
    "insurance-advisor": {
      "command": "python",
      "args": ["-m", "app.mcp.server"],
      "env": {
        "DATABASE_URL": "<your-db-url>",
        "OPENAI_API_KEY": "<your-key>"
      }
    }
  }
}
```

Available tools: `list_leads`, `get_client`, `create_lead`, `update_lead_status`, `analyze_needs`, `get_recommendations`, `generate_sales_pitch`, `handle_client_objection`, `search_policy_docs`, `get_upcoming_renewals`

Authorization is a declarative, IAM-style policy engine (`app/mcp/policies.py` + `app/mcp/policy_engine.py`) -- Allow/Deny statements over Action/Resource per role, default-deny, explicit-Deny-wins, evaluated by `authorize()` in `app/mcp/rbac.py`. Currently: `advisor` is Allow on 8 read/AI-assist tools scoped to `self`, Deny on `create_lead`/`update_lead_status`; `manager`/`admin` are Allow on everything (`mcp:*`) scoped to `*` (any advisor's data). Adding a role or changing a tool's access is a change to the policy document, not to a decorator argument. The stdio transport (Claude Desktop, local dev) has no auth layer and is unrestricted, same as today.

**Auth on the HTTP/SSE transport** uses opaque, revocable tokens (`app/mcp/tokens.py`) -- not JWT. Only a SHA-256 hash is stored server-side, so a leaked token can be revoked individually without invalidating every other advisor's token:

```bash
# mint a token for the mcp-remote Claude Desktop config
DATABASE_URL=<async-url> python scripts/mint_mcp_token.py --email you@example.com

# list / revoke tokens
DATABASE_URL=<async-url> python scripts/revoke_mcp_token.py --email you@example.com
DATABASE_URL=<async-url> python scripts/revoke_mcp_token.py --revoke <token-id>
```

Test that restriction end-to-end against a running server (needs one `role='advisor'` account and one `role='manager'`/`'admin'` account already created -- see the script's docstring):

```bash
DATABASE_URL=<async-url> python scripts/test_role_e2e.py \
    --advisor-email advisor@example.com --manager-email manager@example.com
```

Test the server starts cleanly:

```bash
python -m app.mcp.server
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/api/v1/advisors` | List advisors |
| POST | `/api/v1/leads` | Create a lead |
| GET | `/api/v1/leads` | List leads |
| GET | `/api/v1/leads/{id}` | Lead detail |
| PUT | `/api/v1/leads/{id}` | Update lead |
| GET | `/api/v1/renewals/upcoming` | Policies due in N days |
| POST | `/api/v1/analyze-client` | AI need analysis |
| POST | `/api/v1/recommend-products` | AI product recommendations |
| POST | `/api/v1/pitch` | Generate sales pitch |
| POST | `/api/v1/pitch/objection` | Handle client objection |
| POST | `/api/v1/draft-email/reminder` | Draft premium reminder |
| POST | `/api/v1/send-email/reminder` | Send + log reminder |
| GET | `/api/v1/email-logs` | Email activity log |
| GET | `/api/v1/approval-queue` | Human-in-loop queue |
| POST | `/api/v1/approval-queue/{id}/approve` | Approve queued action |
| POST | `/api/v1/ingest` | Ingest policy PDF |
| POST | `/api/v1/documents/search` | Semantic policy search |
| GET | `/api/v1/metrics` | Business metrics |

---

## Running Tests

```bash
# Unit + integration tests
pytest tests/ -v --ignore=tests/evals

# AI eval harness (requires live OPENAI_API_KEY)
python tests/evals/run_evals.py
```

---

## CI/CD Pipeline

Five stages run on every push to `main`:

```
lint → unit-tests → eval-gate → build → deploy-staging
```

The **eval gate** runs real LLM calls against golden examples in `tests/evals/golden/`. If accuracy drops or latency spikes, the pipeline blocks the merge before the Docker image is built.

---

## Deployment

```bash
docker build -t insurance-advisor-ai .
# Push to ECR → deploy via AWS Lightsail Container Service
```
