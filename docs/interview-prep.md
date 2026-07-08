# Insurance Advisor AI — Interview Preparation Guide

---

## How to Showcase This Project (Do This First)

Don't describe it — walk it. A live demo beats a slide every time.

**1. Open with the 30-second pitch, then stop talking.** Let them ask where to go
deeper — that's more impressive than a monologue, because it shows you're not
reciting a script.

> "I built an AI platform for insurance advisors that automates lead management,
> need analysis, product recommendations, and client outreach — using LangGraph
> agents, RAG over real policy PDFs, and MCP so Claude Desktop can operate the
> whole system through natural language."

**2. Do a live demo, in this order** (the service is deployed on Lightsail):
1. **Dashboard → Leads → click a lead → "Analyze Needs"** — shows the AI actually
   working on real data, not a slide.
2. **Approval Queue tab** — your best differentiator. Say explicitly: *"The AI
   drafts, a human approves before anything reaches a client — that's not a UX
   choice, it's an IRDAI compliance requirement."*
3. **Open Claude Desktop, ask it to look up a lead via MCP** — very few candidates
   can show an AI assistant operating their own backend live. This is the moment
   that actually lands.
4. Only *then* pull up the architecture diagram to narrate what happened
   underneath.

**3. Lead with 3 differentiators, not 10 features.** Interviewers forget feature
lists; they remember decisions. Pick:
- **Eval gate blocking deploys** — "unit tests check code, my eval gate checks AI
  behavior — it runs real LLM calls against golden profiles before every deploy."
- **Human-in-the-loop approval queue** — ties AI to a real regulatory constraint,
  not just "best practice."
- **The production migration bug** — a live, current story: *"I found that four
  of my SQL migrations — including row-level security — were never actually
  applied to prod because CI only ran three of them. I audited it, fixed the
  pipeline, and verified the fix in production the same day."* This is a stronger
  "hardest bug" story than the NOT NULL one because it's about catching a
  **silent gap between what the code claims and what's actually running** —
  exactly the instinct senior engineers want to see.

**4. Have "what I'd add next" ready without being asked** — see Section 12. Auth
is #1, and you already know it's missing. Saying that unprompted reads as
maturity, not a gap being caught.

---

## Tech Stack — What & Why (Ready to Speak)

| Layer | Choice | Why this, not the obvious alternative |
|---|---|---|
| Backend | FastAPI (async) | Native async fits I/O-bound LLM/DB calls; Pydantic gives free request validation |
| Agent orchestration | LangGraph | Insurance workflows have branching + retry + loops — plain chained LLM calls can't model conditional error routing or the iterative Policy Research agent |
| Database | PostgreSQL + pgvector | One engine for relational data *and* vector search — join client rows with similarity results in one query instead of two round trips to a separate vector DB |
| Vector index | HNSW (via pgvector) | Faster, better recall than IVFFlat at scale; `CREATE INDEX CONCURRENTLY` means it can be added with zero downtime |
| Cache | Redis (semantic cache) | Dedupes identical LLM calls — cuts OpenAI cost/latency without touching agent logic |
| LLM | GPT-4o / GPT-4o-mini | Mini for cheap, low-complexity tasks (email drafts, objection replies); full model reserved for reasoning-heavy steps — deliberate cost routing, not one model everywhere |
| Embeddings | text-embedding-3-small | 5x cheaper than ada-002 with better accuracy; `-large`'s extra dimensions buy nothing at this data scale |
| Integration layer | MCP (FastMCP, SSE transport) | One server, many clients (Claude Desktop, Claude Code, future tools) instead of a bespoke integration per AI consumer |
| Email/WhatsApp | SendGrid / Meta Cloud API | Both sit behind the approval queue — infra for outreach exists, but nothing sends without a human click |
| Observability | LangFuse + Sentry | LangFuse traces LLM-specific behavior (tokens, prompts, latency); Sentry catches everything else — you need both because they answer different questions |
| CI/CD | GitHub Actions, 5 stages | The eval-gate stage is the one that makes this AI-native CI, not generic CI applied to an AI repo |
| Frontend | Next.js 15 + React Query | Server components where they help, React Query for the polling/mutation-heavy approval queue UI |

---

## 1. Project Summary (30-second pitch)

"I built an AI-powered platform for insurance advisors in India that automates lead management, needs analysis, product recommendations, and client outreach. It uses LangGraph for multi-step agentic pipelines, RAG over real insurance PDFs via pgvector, and exposes all capabilities as MCP tools so Claude Desktop can operate the system through natural language."

---

## 2. Architecture

```
Claude Desktop (MCP via mcp-remote SSE)
        ↓
FastAPI Backend (AWS Lightsail Container)
        ↓
┌───────────────────────────────────────┐
│  LangGraph Agents                     │
│  - Needs Analysis                     │
│  - Product Matching (parallel search) │
│  - Lead Nurturing (sub-graphs)        │
│  - Objection Handler                  │
│  - Policy Research (iterative loop)   │
│  - Claims & Renewals (bulk)           │
└───────────────────────────────────────┘
        ↓
PostgreSQL + pgvector      OpenAI
(RAG + relational data)    (GPT-4 + text-embedding-3-small)
        ↓
Approval Queue → Advisor Reviews → SendGrid
```

---

## 3. RAG Pipeline — Every Detail

### Chunking Strategy

**What:** Recursive character chunking via LangChain's `RecursiveCharacterTextSplitter` — `chunk_size=500`, `chunk_overlap=50` (characters, not tokens). PyPDF extracts text from every page and concatenates it into one document string before splitting, so a chunk can span a page boundary. Metadata stored per chunk is just `{"source": "filename.pdf"}` — no page number.

**Why recursive character splitting:**
> "It cascades through separators — paragraph breaks first, then line breaks, then words — only falling back to a hard character cut when it has to, so it keeps semantically coherent text together instead of cutting mid-sentence at a fixed boundary. I considered page-level chunking, but insurance PDFs vary hugely in page density — some pages are a single table, others are dense paragraphs — so a fixed page-sized chunk is either too small or too big depending on the document. Overlap (50 chars) means a fact split across a chunk boundary still has some context on both sides."

**What I'd improve:**
> "Bring the page number back into metadata — right now a chunk only carries the source filename, not which page it came from, so a citation can't point someone to an exact page. I'd also add section headers as metadata for filtered retrieval, and move from character-based to token-based chunk sizing so it lines up with the LLM's actual context budget instead of an approximation."

### Why `text-embedding-3-small`

| Model | Dimensions | Cost/1M tokens | Notes |
|---|---|---|---|
| `ada-002` | 1536 | $0.10 | Older, baseline |
| `text-embedding-3-small` | 1536 | $0.02 | Better than ada-002, 5x cheaper |
| `text-embedding-3-large` | 3072 | $0.13 | Overkill at this scale |

**Answer:**
> "Better accuracy than ada-002 at 5x lower cost. text-embedding-3-large doubles vector dimensions to 3072 — more storage, slower search, higher cost with no measurable quality gain at ~52 chunks. I'd revisit at 100k+ vectors."

### Why pgvector over Pinecone / Weaviate / Qdrant

**Answer:**
> "Three reasons. First, we already have PostgreSQL — pgvector is one CREATE EXTENSION command, no new service to deploy or bill for. Second, at this scale (~52 vectors) even an approximate index responds in single-digit milliseconds. Third, I can JOIN vector search results with relational data in a single query — in Pinecone I'd need two round trips."

**Follow-up — What index does pgvector use?**
> "HNSW — `CREATE INDEX ... USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)`, built CONCURRENTLY so it doesn't lock the table. It replaced an earlier IVFFlat index I'd started with — I switched because HNSW gives faster queries and better recall, and at this scale the extra memory HNSW uses isn't a concern. IVFFlat also needs a representative sample of the data before its cluster lists are effective, which doesn't really suit a corpus this small anyway."

**Similarity metric:**
> "Cosine similarity (`<=>` operator) — measures angle between vectors, not magnitude. Length-invariant, so a short chunk and a long chunk on the same topic score equally regardless of length."

### Retrieval Parameters

- `top_k = 5` — empirical: k=3 sometimes missed the best chunk; k=10 introduced noise
- Query: embedded at runtime with same model as ingestion
- Result: top 5 chunks injected into LLM prompt as context

---

## 4. LangGraph Agents — Deep Dive

### Why LangGraph over plain LLM calls

**Plain approach is fragile:**
```python
result = openai.chat(prompt)  # no error handling, no state, no branching
save_to_db(result)
```

**LangGraph models it as a state machine:**
```
load_client → [client not found?] → END
     ↓
build_rag_query → fetch_context → run_analysis → extract_gaps → save → END
```

**Answer:**
> "Insurance workflows have 4–6 sequential steps with dependencies. LangGraph models this as a typed state machine — each node receives the full state, does one thing, returns updates. Conditional edges handle error branching. I can swap individual nodes without rewriting the whole flow."

### The 6 Agents — What Makes Each Unique

| Agent | Unique Characteristic |
|---|---|
| **Needs Analysis** | Combines RAG context with client profile before LLM call |
| **Product Matching** | LLM generates 3 search queries → parallel `asyncio.gather` → deduplicates → ranks with fit score |
| **Lead Nurturing** | Orchestrates 2 agents as sub-graphs, drafts email, queues for human approval |
| **Objection Handler** | Classifies into 7 objection types first, generates type-specific structured response |
| **Policy Research** | Only iterative agent — loops until sufficient context gathered (max 3 searches) |
| **Claims & Renewals** | Only bulk agent — processes multiple clients, scores lapse risk, queues outreach |

**Highlight parallel search:**
> "Product Matching runs 3 vector searches concurrently with asyncio.gather — one targeting health conditions, one financial goals, one age/income bracket. Sequential would add 3x latency. Parallel gives richer, more diverse chunks for the LLM to rank from."

### State Management

```python
class NeedsAnalysisState(TypedDict):
    client_id: str
    client_profile: dict
    rag_context: str
    analysis_text: str
    gaps: list[dict]
    interaction_id: str
    errors: Annotated[list[str], operator.add]  # accumulates, doesn't overwrite
```

> "Annotated with operator.add means errors from multiple nodes accumulate into one list rather than overwriting each other."

---

## 5. MCP — Why 10 Tools

### Framework for choosing tools

> "I mapped the advisor's daily workflow and identified every action they repeat manually, grouped into three categories."

**Category 1 — Data operations (CRUD):**
- `list_leads` — advisors check their pipeline daily
- `get_client` — needed before any AI action
- `create_lead` — capture leads from calls without opening dashboard
- `update_lead_status` — move pipeline forward after a meeting

**Category 2 — AI operations (the value):**
- `analyze_needs` — 10-minute manual process in 30 seconds
- `get_recommendations` — replaces manually comparing product brochures
- `generate_sales_pitch` — personalized per client, not a template
- `handle_client_objection` — real-time help during a call

**Category 3 — Knowledge operations:**
- `search_policy_docs` — "does this plan cover diabetes?" answered instantly
- `get_upcoming_renewals` — proactive rather than reactive

**Why not more:**
> "Claude performs better with fewer focused tools. Too many and it struggles to pick correctly. I deliberately excluded delete operations — destructive actions shouldn't be one natural language sentence away."

### MCP Transport — SSE

> "The MCP server is mounted as a Starlette SSE app at /mcp/sse inside FastAPI. The client connects via GET, receives a session ID, then POSTs requests to /mcp/messages/?session_id=... Responses stream back on the SSE connection. mcp-remote bridges this to Claude Desktop's stdio interface."

---

## 6. Human-in-the-Loop — Why It Matters

**Why not send emails automatically?**
> "Two reasons — regulatory and trust. IRDAI regulations require client communications come from a licensed advisor. An AI sending product recommendations directly is a compliance violation. Second, LLMs hallucinate — a wrongly recommended product could be a mis-selling complaint. The approval queue puts human review between AI output and client delivery. The AI does the heavy lifting, the human takes accountability."

**Approval Queue Flow:**
```
Agent runs → drafts email → INSERT into approval_queue (status=pending)
     ↓
Advisor sees card in dashboard Approvals tab
     ↓
Clicks Send → POST /api/v1/approval-queue/{id}/approve
     ↓
SendGrid sends email → status=approved
```

---

## 7. CI/CD Pipeline — 5 Stages

```
lint → unit-tests → eval-gate → build → deploy-staging
```

**The interesting stage — eval-gate:**
> "Before every deploy, I run AI evaluations against 3 synthetic client profiles — Rahul (salaried, tier-1), Priya (self-employed, health condition), Amit (retired). Each eval checks that need analyzer responds under 20 seconds and product recommender returns 3 recommendations. If any eval fails, deployment is blocked. This is AI-specific CI — you can't unit test LLM output with assertions, you test behavior."

**Why 20 seconds:**
> "P95 latency for GPT-4 on a 500-token prompt is 8–12 seconds. 20 seconds gives headroom without being so loose that degraded responses slip through."

---

## 8. Security Decisions

**PII Guard:**
> "Before client data hits the LLM, I scrub Aadhaar numbers, PAN cards, phone numbers, and email addresses with regex. The LLM sees 'client age 34, income 8L' — never the actual identity. Prevents PII leaking into OpenAI's training pipeline."

**IRDAI Guardrails:**
> "Block phrases like 'guaranteed returns', 'risk-free investment', 'double your money' from LLM output. These are prohibited under IRDAI advertising guidelines. Guardrail runs post-generation before response reaches the advisor."

---

## 9. Numbers to Remember

| Metric | Value |
|---|---|
| LangGraph agents | 6 |
| MCP tools | 10 |
| Insurance PDFs | 6 products |
| Vector chunks | ~52 |
| Embedding model | text-embedding-3-small (1536 dims) |
| Similarity metric | Cosine (`<=>`) |
| top_k retrieval | 5 chunks |
| CI/CD stages | 5 |
| Eval gate timeout | 20 seconds |
| Approval statuses | pending → approved / rejected / failed |

---

## 10. Hardest Bug — Tell This Story

> "All 6 agent endpoints were 500-ing in production. I added timing logs — responses were taking 9–22 seconds, meaning LLM calls completed fine. The crash was after the LLM call, at the DB write.
>
> The interactions table has a String PRIMARY KEY with a Python-side UUID default — `default=lambda: str(uuid.uuid4())`. That default only fires through SQLAlchemy ORM. My agents used raw SQL INSERTs for performance, bypassing the ORM entirely. PostgreSQL had no server-side DEFAULT for that column — NOT NULL constraint violation.
>
> Fix: add `gen_random_uuid()::text` directly in the INSERT. Lesson: raw SQL bypasses ORM defaults — always confirm server-side defaults exist in the DB DDL, not just the ORM model."

---

## 11. Common Interview Questions

### System Design

**Q: Walk me through the architecture end to end.**
Start from user action → FastAPI → LangGraph agent → OpenAI + pgvector → DB write → response. Draw it. Take 3 minutes.

**Q: How does RAG work in your system?**
PDF → PyPDF extracts text → chunked by page → embedded with text-embedding-3-small → stored in pgvector. Query time: user query → embed → cosine similarity → top 5 chunks → injected into LLM prompt.

**Q: How do you handle failures in a multi-step agent?**
LangGraph conditional edges. Every node that can fail returns `{"errors": [...]}`. Edge checks for errors and routes to END. Final API response checks `result.get("errors")` and returns 404/400.

**Q: What happens if OpenAI is down?**
Currently agents fail with 500. Right fix: retry with exponential backoff using tenacity, fallback to simpler prompt or cached response.

**Q: How does your system scale?**
Single Lightsail container today. Bottleneck is OpenAI latency (8–12s), not compute. Scale: more Lightsail nodes behind load balancer, PgBouncer for connection pooling, async FastAPI already handles concurrent requests well.

### AI / ML

**Q: Why cosine similarity over dot product or Euclidean?**
Cosine measures directional similarity — length-invariant. Dot product favors longer vectors. Euclidean doesn't work well in high-dimensional space (curse of dimensionality).

**Q: How do you evaluate RAG quality?**
Currently through eval gate — test right product types appear for known profiles. Proper evaluation: RAGAS metrics — context precision, context recall, faithfulness.

**Q: What is hallucination and how do you handle it?**
LLM generates confident-sounding false information. Three mitigations: RAG grounds answers in real documents, IRDAI guardrails block prohibited claims, human approval queue before anything reaches clients.

**Q: Why not fine-tune instead of RAG?**
Fine-tuning bakes knowledge into weights — can't update without retraining. Insurance products change yearly. RAG: add a PDF, knowledge is immediately available. Fine-tuning also needs thousands of labeled examples we don't have.

**Q: How did you choose top_k=5?**
Empirical. k=3 sometimes missed the best chunk. k=10 introduced noise. 5 balances coverage vs. noise. Right approach: measure answer quality across k values on a labeled test set.

### LangGraph

**Q: What is LangGraph vs LangChain?**
LangChain is for simple chains (A→B→C). LangGraph handles branching, loops, conditional routing — essential for agents that retry, short-circuit on errors, or loop until a condition is met.

**Q: What is a StateGraph?**
Takes a TypedDict as state schema. Each node receives full state, returns partial update. LangGraph merges updates. Annotated fields with operator.add accumulate rather than overwrite.

**Q: How does the iterative Policy Research agent work?**
Loop: plan searches → run one search → check if sufficient → if not, loop again (max 3 times) → synthesize. Conditional edge routes back to search or forward to synthesis based on is_sufficient flag.

### MCP

**Q: What is MCP?**
Model Context Protocol — open standard for connecting AI assistants to external tools. Define tools with schemas; AI decides when to call which tool and chains them based on user intent.

**Q: How is MCP different from OpenAI function calling?**
Conceptually similar. MCP is transport-agnostic, designed for persistent servers multiple clients connect to. OpenAI function calling is per-request, stateless, OpenAI-only. MCP works with Claude Desktop, Cursor, VS Code extensions.

**Q: What is SSE transport?**
Server-Sent Events — unidirectional HTTP stream. Client connects to /mcp/sse, gets session ID, POSTs requests to /mcp/messages/?session_id=... Responses come back on the SSE stream.

### Database

**Q: Why PostgreSQL over MongoDB?**
Insurance data is relational — policy belongs to client belongs to advisor. Joins are frequent. PostgreSQL gives ACID, foreign keys, and pgvector in one engine.

**Q: The NOT NULL bug — what's the lesson?**
ORM defaults are Python-side. Raw SQL bypasses ORM entirely. For any column raw SQL writes to, DEFAULT must exist in DB DDL. Always check `\d tablename` to confirm server-side defaults.

### DevOps

**Q: Why is the eval gate in CI?**
Without it, a bad prompt change or model behavior shift deploys silently. Unit tests can't test LLM behavior. The eval gate is AI-specific quality gate that blocks deployment on behavioral regression.

**Q: Why Lightsail over EC2 or ECS?**
Managed containers — no cluster setup, predictable pricing. ECS adds operational overhead with no benefit at this scale. Would move to ECS Fargate when needing auto-scaling or multiple services.

### Behavioural

**Q: Tell me about a difficult bug you solved.**
The NOT NULL constraint bug — agents 500-ing after 9–22 seconds. Timing analysis isolated the crash to DB write, not LLM. See Section 10.

**Q: How did you decide what to build first?**
Data (RAG + real PDFs) → agents (AI logic) → wire to API → MCP → approval queue UI. Core intelligence first, exposure layer second, human workflow third.

**Q: What would you do differently?**
Auth from day one, streaming LLM responses, overlap-based chunking, RAGAS evaluation metrics, structured logging with trace IDs across agent nodes.

**Q: How do you test AI systems?**
Three layers: unit tests for non-AI code, integration tests with real test DB, eval gate for AI behavior. I deliberately don't mock OpenAI — mocks don't catch prompt regressions.

---

## 12. What You'd Add Next

Shows maturity when asked "what's missing?":

1. **Auth** — JWT so each advisor only sees their own leads
2. **Streaming** — stream LLM responses to frontend, no 15s spinner
3. **WhatsApp** — Twilio for renewal reminders (infra already in place)
4. **Caching** — cache embeddings for repeated queries, cache needs analysis per client
5. **RAGAS eval** — proper RAG quality metrics beyond latency checks
6. **Observability** — structured logs with trace IDs across all agent nodes
