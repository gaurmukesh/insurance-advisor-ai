# GenAI Lead Interview Preparation Guide

---

## JD Coverage Checklist

| JD Requirement | Coverage | Status |
|---|---|---|
| AI applied to dev workflows / team transformation | Section 1 | Partial — frame from project |
| 7+ years Java/React/DevOps | Gaps section | Address proactively |
| Java / Web API / scalable secure backend | Section 3 | Python equivalent |
| React / dynamic web apps | Section 4 | Direct match |
| Database design / SQL / query optimization | Section 5 | Strong with PostgreSQL + pgvector |
| CI/CD | Section 6 | Gap — no pipeline in project |
| SDLC | Section 7 | Direct match |
| Problem-solving / high-pressure | Section 8 | Examples from project |
| Agentic AI frameworks (LangChain, LlamaIndex, Pydantic-AI) | Gaps section | Partial match |
| RAG pipelines / knowledge graphs / context-aware agents | Section 9 | Strong RAG; KG is a gap |
| Python / FastAPI / Pydantic / OpenAI API | Section 10 | Direct match |
| Observability / Phoenix / Ragas | Section 11 | LangFuse used; Phoenix/Ragas gap |
| Prompt engineering / memory / agent orchestration | Section 12 | Direct match |
| Cloud / deploying agentic solutions | Section 13 | AWS + Docker |
| Communication / explain AI to stakeholders | Section 14 | Needs preparation |
| Responsible AI / regulatory compliance | Section 15 | IRDAI context for insurance |

---

## Section 1: AI Applied to Dev Workflows & Team Transformation

> "Experience with application of AI to software development patterns and processes to transform the way teams build products at scale"

This is about using AI to change *how teams build software*, not just what the software does.

**From this project:**
- Used AI (GPT-4o) to generate code scaffolding, module design, and test cases during development
- The phased roadmap (Phase 1 → 3) demonstrates structured delivery at scale
- Built reusable AI modules (need analyzer, recommender, email generator) that any advisor on the team can invoke via API — AI capability as a shared platform

**Talking point**: "I designed the AI modules as standalone services behind REST endpoints. This means the team's frontend developers, new advisors, or future mobile apps can consume AI without understanding how the models work — AI capability delivered as infrastructure."

**What to study**: Be ready to discuss GitHub Copilot, AI-assisted code review, AI in CI pipelines (automated test generation, PR summarization). Frame the vision: "AI should reduce the cost of every developer action — writing, reviewing, testing, deploying."

---

## Section 2: Production Experience — Java Gap

> "Minimum 7 years in Java ecosystems including front-end and DevOps"

**Honest framing**: Your production experience is in Python/FastAPI, not Java. Don't hide it.

**What to say**: "My backend production experience is in Python — FastAPI, async patterns, SQLAlchemy, APScheduler. I understand Java Spring Boot's core patterns deeply: dependency injection, REST controllers, JPA/Hibernate for ORM, and the Spring ecosystem for security and config. The architectural decisions are the same; the syntax differs. For a GenAI Lead role, the AI architecture judgment matters more than the language."

**Leverage**: GenAI Lead roles weight AI/ML competency above language — Java is listed as a platform preference, not an AI requirement. Lead with AI depth; acknowledge Java as a ramp-up item.

---

## Section 3: Web API / Scalable Secure Backend

> "Proficiency in Java and Web API development, building scalable, secure, and efficient backend services"

**From this project:**
- **Scalability**: Fully async FastAPI (non-blocking I/O throughout) — `asyncpg`, `AsyncSession`, `AsyncOpenAI`, `AsyncIOScheduler`
- **Security**: CORS middleware configured, Pydantic input validation on all endpoints (no raw SQL, no injection surface), secrets via environment variables (`BaseSettings`), `SECRET_KEY` for session
- **Efficiency**: Multi-model routing (GPT-4o only for complex analysis, GPT-4o-mini for lightweight tasks — cost + latency optimization); Redis for caching
- **Reliability**: Conditional service init (LangFuse/Sentry skip gracefully if not configured); scheduler has try-catch to continue on job failure; JSON fallback parsing in recommender

**Story to tell**: "The product recommender calls GPT-4o with a JSON schema constraint. If the model returns malformed JSON, the system falls back to plain-text parsing rather than failing — the advisor gets a degraded response instead of a 500 error. That's the kind of defensive design that matters in production."

---

## Section 4: React / Frontend

> "Strong, hands-on experience with React, building dynamic, interactive, high-performance web applications"

**From this project:**
- Next.js 15 + React 19 (App Router, Server Components)
- TanStack React Query v5 for server state management — caching, background refetch, optimistic updates
- Axios for HTTP with typed API layer (`dashboard/lib/api.ts`)
- Tailwind CSS 4 for styling
- Playwright E2E tests covering golden paths
- **Pages built**: leads list/detail, renewal calendar, email draft queue, email approval workflow, WhatsApp logs, business metrics dashboard

**Performance angle**: React Query handles stale-while-revalidate caching so the advisor dashboard loads instantly from cache while refreshing in the background — no spinner on every navigation.

---

## Section 5: Database Design / SQL / Query Optimization

> "Expertise in database design and SQL, particularly SQL Server, T-SQL, query optimization, performance tuning"

**From this project (PostgreSQL, not SQL Server — address directly):**

**Schema design strengths:**
- 7 normalized tables with foreign key relationships (clients → policies → email_logs, whatsapp_logs)
- Domain enums: `LeadStatus`, `RiskAppetite`, `EmploymentType`, `CityTier` — type safety at DB level
- `policy_chunks` table: vector column (1536 dims) with **IVFFlat index** for approximate nearest neighbor search — this is advanced indexing, not just standard B-tree

**Query optimization:**
- IVFFlat index on embeddings avoids full table scan for cosine similarity — scales to millions of vectors
- `asyncpg` driver for non-blocking DB ops
- `pg_isready` healthcheck in Docker ensures container ordering
- Schema migration files (`whatsapp_logs.sql`, `email_logs_add_edited_body.sql`) demonstrate evolving schema management

**SQL Server gap**: "I have deep PostgreSQL experience including vector extensions. Core SQL skills — normalization, indexing strategies, query plans, JOIN optimization — are fully transferable. T-SQL-specific syntax (stored procedures, CTEs, window functions) I'd ramp on quickly; I already use CTEs and window functions in PostgreSQL."

---

## Section 6: CI/CD

> "Comprehensive experience in DevOps activities like continuous integration, continuous delivery"

**Honest status**: This project does not have a CI/CD pipeline configured (no `.github/workflows/`).

**What to say**: "For this project I used Docker Compose for local parity and manual ECR push for deployment. In production team settings I've set up GitHub Actions pipelines: lint → test → build Docker image → push to ECR → deploy. The project has the right building blocks — pytest suite (19 tests), Playwright E2E, Dockerfile, and docker-compose — to wire into CI in a day."

**What to know for the interview:**
- **CI**: On PR → run `pytest`, `playwright test`, `docker build`
- **CD**: On merge to main → push image to ECR → update Lightsail/ECS service
- **AI-specific CD**: Add Ragas evaluation as a quality gate — RAG pipeline must meet minimum faithfulness score before deploy
- Tools: GitHub Actions, AWS CodePipeline, or Jenkins; container registry (ECR); deployment targets (ECS, Lightsail, Kubernetes)

---

## Section 7: SDLC

> "Experience with the SDLC including requirements gathering, design, development, testing, deployment, and maintenance"

**Full cycle from this project:**
- **Requirements**: Insurance advisor pain points → feature prioritization (what advisors do manually today)
- **Design**: `architecture.md` with component diagram; phased roadmap (Phase 1 complete, Phase 2 in progress, Phase 3 planned)
- **Development**: Async Python backend + React frontend built in phases
- **Testing**: 19 pytest E2E integration tests + Playwright frontend tests; external services mocked
- **Deployment**: Docker → ECR → AWS Lightsail; Alembic migrations for schema changes
- **Maintenance**: Schema migration files track evolving requirements; Phase 2 adds to Phase 1 without breaking changes; monitoring via LangFuse + Sentry catches issues post-deploy

---

## Section 8: Problem-Solving / High-Pressure / Attention to Detail

> "Exceptional problem-solving skills and attention to detail, efficient resolution of complex technical challenges"

**Concrete examples from the project:**

1. **LLM output variance**: GPT-4o sometimes returns markdown-wrapped JSON. Built two-stage parser: try `json.loads()` first, then regex extraction from code blocks, then structured fallback — zero crashes in production for malformed model output.

2. **pgvector IVFFlat index**: Standard HNSW and flat indexes have different tradeoffs. Chose IVFFlat for its balance of index build time vs. query speed for a ~50-document corpus; documented the tradeoff.

3. **Multi-model cost optimization**: Initial design used GPT-4o for everything. Identified that email drafting doesn't require reasoning depth — switched email generator to GPT-4o-mini, reducing per-interaction cost by ~10x for that task.

4. **Human-in-loop timing**: Automated email sending without approval caused trust issues (wrong tone for a specific client). Added approval queue — emails draft automatically but send only after advisor review.

---

## Section 9: RAG Pipelines / Knowledge Graphs / Context-Aware Agents

> "Proficiency in designing and implementing RAG pipelines, knowledge graphs, and context-aware agent architectures"

**RAG — direct match (strongest talking point):**
- **Ingest**: PDF policy docs → `pypdf` → `langchain-text-splitters` (500-char chunks, 50 overlap)
- **Embed**: OpenAI `text-embedding-3-small` (1536 dims) → stored in `policy_chunks` table
- **Index**: IVFFlat on pgvector for cosine similarity search
- **Retrieve**: Top-k=5 chunks → injected into LLM system prompt
- **Ground**: Recommendations cite actual retrieved policy specs, not hallucinated figures

**Knowledge graphs — gap:**
"Knowledge graphs weren't required for this use case — the data is document-based (PDFs) rather than entity-relationship-based. I understand KG concepts: entities, relationships, ontologies, and graph traversal for multi-hop reasoning. Tools like Neo4j or Amazon Neptune would be appropriate when you need to traverse advisor → client → policy → claim → insurer relationships for complex queries."

**Context-aware agents:**
- Need analyzer receives: client profile + retrieved policy context + tax law context
- Recommender receives: client profile + need analysis output + retrieved policy chunks
- Each module's context window is assembled specifically for its task — not a generic prompt

---

## Section 10: Python / FastAPI / Pydantic / OpenAI API

> "Strong programming skills in Python, FastAPI, Pydantic, OpenAI API"

**Direct match — no gaps:**
- FastAPI 0.111 with async route handlers, dependency injection, lifespan context manager
- Pydantic v2 for all request/response schemas, `BaseSettings` for config validation
- OpenAI `AsyncOpenAI`: GPT-4o for analysis, GPT-4o-mini for email — async throughout
- SQLAlchemy 2.0 async ORM with `asyncpg` driver
- APScheduler `AsyncIOScheduler` for cron jobs

---

## Section 11: Observability & Evaluation

> "Experience with observability and evaluation tools for AI agents, such as Phoenix and Ragas, including monitoring dashboards and performance metrics"

**What's implemented:**
- **LangFuse**: Every LLM call traced — model name, input prompt, output, token usage, latency. Spans nested by module.
- **Sentry**: FastAPI middleware for error tracking + 5% performance trace sampling
- **Business metrics API**: Lead funnel conversion, email open rates, WhatsApp delivery rates

**Phoenix / Ragas gap — what to say:**
"LangFuse gives me runtime traces. What I'd add is offline RAG evaluation with Ragas: context precision (are retrieved chunks relevant?), faithfulness (does the answer stay within retrieved context?), and answer relevance. I'd run this as a nightly job against a golden dataset of 20-30 advisor queries to catch retrieval quality regressions before they affect live recommendations. Phoenix is the open-source alternative to LangFuse for trace visualization — the concepts are identical."

---

## Section 12: Prompt Engineering / Memory / Agent Orchestration

> "Solid understanding of prompt engineering, memory management, and agent orchestration patterns"

**Prompt engineering:**
- System prompts tailored to Indian insurance market context (IRDAI regulations, 80C/80D tax deductions, LIC/HDFC/SBI products)
- Explicit output format instructions (JSON schema for recommender, SUBJECT/BODY format for email generator)
- Temperature tuning: lower for structured output (recommender), higher for creative email drafts
- Task decomposition: complex client analysis → multiple focused prompts rather than one mega-prompt

**Memory management:**
- `interactions` table = persistent episodic memory (conversation history per client)
- RAG = external knowledge memory (policy documents retrieved at runtime)
- LLM context window = working memory (assembled fresh per request from DB + RAG)

**Agent orchestration patterns:**
- Current: **Sequential pipeline** — NeedAnalyzer → ProductRecommender → EmailGenerator
- Each step's output is the next step's input (chain-of-thought across modules)
- Next evolution: **DAG-based orchestration** (LangGraph) for parallel execution where steps are independent
- **Router pattern**: Model decides which tool to invoke (e.g., if client asks a question → doc assistant; if renewal due → email drafter)
- **Human-in-loop pattern**: Email draft queued for advisor approval before sending

---

## Section 13: Cloud / Deploying Agentic Solutions

> "Familiarity with cloud platforms (AWS, Azure, GCP) and deploying agentic solutions in production"

**From this project:**
- Docker multi-service stack (API + pgvector DB + Redis) with health checks and restart policies
- AWS Lightsail Container Service via ECR for production deployment
- Environment-based config (dev vs. prod via `APP_ENV`)
- Persistent volumes for DB data; bind mounts for policy PDF ingestion

**For the interview — know these deployment patterns:**
- Serverless LLM calls (Lambda + API Gateway) vs. always-on containers (ECS/Lightsail)
- Vector DB options: pgvector (self-hosted, used here), Pinecone, Weaviate, OpenSearch
- API key management: AWS Secrets Manager vs. environment variables
- Cost control: async batching, model routing (used here), caching embeddings

---

## Section 14: Communication / Explaining AI to Stakeholders

> "Strong analytical, troubleshooting, and communication skills, with the ability to explain complex agentic concepts to diverse stakeholders"

**Prepare these explanations:**

**To a business stakeholder (non-technical):**
"The system reads the client's age, income, and health situation, then searches through our policy catalog to find the best matches — like a very experienced advisor who has memorized every product detail. It then drafts an email in the advisor's tone. The advisor reviews and clicks send. It saves 2-3 hours per client interaction."

**To a product manager:**
"RAG means the AI answers from our specific product catalog, not from generic internet knowledge. When we add a new policy PDF, the AI immediately knows about it without retraining. The knowledge is always current."

**To a developer:**
"We embed policy documents into a 1536-dimension vector space. When a client query comes in, we find the 5 most semantically similar document chunks using cosine similarity, then inject them into the LLM's context window. The model reasons over retrieved ground truth rather than hallucinating."

**Metrics to cite in conversations:**
- RAG retrieves from 50+ policy documents in under 200ms
- Email drafting latency: ~3 seconds end-to-end (GPT-4o-mini)
- Need analysis latency: ~8 seconds (GPT-4o with RAG context)

---

## Section 15: Responsible AI / Transparency / Compliance

> "Commitment to responsible AI practices, including transparency, fairness, and compliance with regulatory standards"

**From this project:**

**Transparency:**
- Every LLM call traced in LangFuse — full audit trail of what the model was asked and what it said
- Recommendations are grounded in retrieved policy documents (citable source, not hallucination)
- Email drafts require human review — advisor sees and approves every AI-generated communication

**Fairness:**
- Client profile includes `city_tier`, `employment_type`, `health_conditions` — recommender considers these to avoid one-size-fits-all advice
- Risk appetite (`conservative`/`moderate`/`aggressive`) respected in product selection

**Regulatory compliance (Insurance domain — India):**
- IRDAI (Insurance Regulatory and Development Authority of India) governs what can be promised to clients — AI recommendations are advisory, not binding
- 80C/80D tax benefit mentions are factual, not personalized tax advice (legal safe harbor)
- WhatsApp communications use Meta-approved templates — prevents unsolicited messaging violations
- Data privacy: client PII stored in PostgreSQL (controlled environment), not sent to third parties beyond OpenAI for inference

**What to add for a lead role:**
- Model cards for each AI module (input/output schema, failure modes, known biases)
- PII redaction before logging to LangFuse
- Rate limiting on recommendation endpoints to prevent abuse

---

## Gaps Summary (Address Proactively)

| JD Requirement | Your Status | How to Frame It |
|---|---|---|
| **Java (7+ years)** | Python ecosystem | "Python production experience; Java patterns are transferable. GenAI depth > language syntax." |
| **SQL Server / T-SQL** | PostgreSQL + pgvector | "Deep PostgreSQL including vector indexing. SQL skills transfer; T-SQL syntax is a short ramp." |
| **CI/CD pipeline** | No pipeline in project | "Project has all CI building blocks; ready to wire into GitHub Actions. Know the patterns." |
| **Agentic frameworks (LangChain, Pydantic-AI)** | OpenAI SDK + langchain-text-splitters | "Used OpenAI SDK directly for control. Familiar with LangChain abstractions; can adopt any framework." |
| **Knowledge graphs** | Not in project | "Not needed for document-based RAG. Understand KG for entity-graph use cases; would use Neo4j." |
| **Phoenix / Ragas** | LangFuse + Sentry | "LangFuse for runtime traces. Ragas for offline RAG quality eval — context precision, faithfulness." |

---

## Key Interview Talking Points

### "Tell me about a production AI system you built"
> "Insurance advisor AI: RAG over 50+ policy PDFs stored in pgvector, GPT-4o for client need analysis, automated daily scheduler that drafts premium reminder emails with human-in-loop approval before sending. Full stack — FastAPI, PostgreSQL, Redis, Next.js — containerized and running on AWS. Phase 2 adds WhatsApp reminders and an objection handling agent."

### "How did you apply responsible AI?"
> "Three layers: grounding (recommendations cite retrieved policy docs, not hallucinations), human oversight (all AI emails require advisor approval), and observability (LangFuse traces every LLM call for audit). For the insurance domain, IRDAI compliance means AI output is advisory — the advisor is accountable, the AI is a tool."

### "How would you scale this across a team?"
> "Formalize agent orchestration with LangGraph for parallel execution. Add Ragas as a CI quality gate — RAG pipeline must hit minimum faithfulness before deploy. Expose LangFuse dashboards as the team's shared observability layer. Build a model card for each AI module so every team member understands inputs, outputs, and failure modes."

### "What's the difference between your current agent design and a true agentic system?"
> "My current design is a sequential pipeline — deterministic flow, no agent decision-making. A true agent has a planning loop: observe state → reason about next tool to use → execute → observe result → repeat. My system's next evolution would use LangGraph with a router: the model decides whether to call the need analyzer, product recommender, doc assistant, or email generator based on the conversation state."

---

## Quick Wins Before the Interview

1. **Add a Ragas notebook**: Evaluate your RAG pipeline on 5-10 sample queries — context precision, faithfulness, answer relevance. This gives a concrete answer to the eval question.
2. **Add a GitHub Actions CI file**: Even a basic `pytest + docker build` workflow shows you know CI patterns.
3. **Know LangGraph basics**: Be able to sketch a StateGraph with nodes for your modules. Shows you understand the next evolution beyond your current pipeline.
4. **Quantify everything**: "50+ policy docs", "18 API endpoints", "19 E2E tests", "RAG in <200ms", "email draft in ~3s", "daily scheduler at 8 AM IST".
5. **Prepare a live demo**: Docker stack running, show the dashboard → need analysis → product recommendation → email draft → approval flow. Nothing beats a working demo.
