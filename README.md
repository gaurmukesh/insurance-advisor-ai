# Insurance Advisor AI

An AI-powered platform for insurance advisors — lead management, intelligent product recommendations, automated premium reminders, and AI-drafted client emails.

---

## Features

| Feature | Status |
|---|---|
| Client need analysis (AI) | ✅ Phase 1 |
| Product recommendations via RAG | ✅ Phase 1 |
| Lead management (CRUD + status tracking) | ✅ Phase 1 |
| Premium reminder emails (automated + manual) | ✅ Phase 1 |
| Next.js advisor dashboard | ✅ Phase 1 |
| LangFuse + Sentry observability | ✅ Phase 1 |
| WhatsApp reminders (Meta Cloud API) | 🔜 Phase 2 |
| Pitch & objection handler | 🔜 Phase 2 |
| Policy document assistant (PDF upload) | 🔜 Phase 2 |
| Multi-advisor / team accounts | 🔜 Phase 3 |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python FastAPI (async) |
| Database | PostgreSQL + pgvector |
| LLM | OpenAI GPT-4o / GPT-4o-mini |
| Embeddings | OpenAI text-embedding-3-small |
| Email | SendGrid |
| Scheduler | APScheduler |
| Observability | LangFuse + Sentry |
| Frontend | Next.js 15 + Tailwind CSS + React Query |
| Container | Docker + docker-compose |

---

## Project Structure

```
insurance-advisor-ai/
├── app/
│   ├── api/routes/          # FastAPI route handlers
│   │   ├── advisors.py
│   │   ├── clients.py
│   │   ├── recommendations.py
│   │   ├── emails.py
│   │   └── ingest.py
│   ├── core/
│   │   ├── llm.py           # Async OpenAI client
│   │   ├── rag.py           # RAG retrieval pipeline
│   │   ├── config.py        # Settings from .env
│   │   └── observability.py # LangFuse + Sentry init
│   ├── modules/
│   │   ├── need_analyzer.py
│   │   ├── product_recommender.py
│   │   └── email_generator.py
│   ├── models/              # SQLAlchemy ORM models
│   ├── db/
│   │   ├── postgres.py      # Async engine + session
│   │   └── vector_store.py  # pgvector store + search
│   └── scheduler/
│       └── premium_reminder.py
├── dashboard/               # Next.js frontend
│   ├── app/
│   │   ├── page.tsx         # Overview dashboard
│   │   ├── leads/           # Lead list + detail
│   │   ├── renewals/        # Upcoming renewals + email
│   │   └── email-logs/      # Email activity log
│   ├── components/
│   └── lib/
│       ├── api.ts           # Axios API client
│       └── AdvisorContext.tsx
├── data/policies/           # Policy PDFs for RAG
├── tests/                   # E2E test suite (19 tests)
├── migrations/init.sql
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

### 1. Clone and configure

```bash
git clone https://github.com/gaurmukesh/insurance-advisor-ai.git
cd insurance-advisor-ai
cp .env.example .env
```

Edit `.env` and fill in your keys:

```env
OPENAI_API_KEY=sk-...
SENDGRID_API_KEY=SG....
SENDGRID_FROM_EMAIL=you@example.com
DATABASE_URL=postgresql+asyncpg://admin:secret@localhost:5432/insurance_ai
SYNC_DATABASE_URL=postgresql://admin:secret@localhost:5432/insurance_ai
```

### 2. Start the database

```bash
docker compose up -d db
```

### 3. Run the API

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API is live at `http://localhost:8000`
Swagger docs at `http://localhost:8000/docs`

### 4. Run the dashboard

```bash
cd dashboard
cp .env.local.example .env.local   # or create manually
# Add: NEXT_PUBLIC_API_URL=http://localhost:8000
npm install
npm run dev
```

Dashboard is live at `http://localhost:3000`

### 5. Ingest policy PDFs (for RAG)

```bash
curl -X POST http://localhost:8000/api/v1/ingest \
  -F "file=@data/policies/insurance_policy.pdf"
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/api/v1/advisors` | List advisors |
| POST | `/api/v1/leads` | Create a lead |
| GET | `/api/v1/leads` | List leads (filter by advisor, status) |
| GET | `/api/v1/leads/{id}` | Get lead detail |
| PUT | `/api/v1/leads/{id}` | Update lead |
| GET | `/api/v1/renewals/upcoming` | Policies due in N days |
| POST | `/api/v1/analyze-client` | AI need analysis |
| POST | `/api/v1/recommend-products` | AI product recommendations |
| POST | `/api/v1/draft-email/reminder` | Draft premium reminder email |
| POST | `/api/v1/send-email/reminder` | Send + log reminder email |
| POST | `/api/v1/draft-email/followup` | Draft follow-up email |
| GET | `/api/v1/email-logs` | Email activity log |
| POST | `/api/v1/ingest` | Ingest policy PDF into vector store |

---

## Running Tests

```bash
# Start test database
docker compose up -d db

# Run all 19 E2E tests
pytest tests/ -v
```

Tests use a separate `insurance_ai_test` database. External services (OpenAI, SendGrid) are mocked.

---

## Architecture

See [architecture.md](architecture.md) for the full system design including RAG pipeline, WhatsApp flow, deployment plan, and phased roadmap.

---

## Deployment

Designed for AWS Lightsail (~$22/month for Phase 1):

```bash
docker build -t insurance-advisor-ai .
# Push to ECR and deploy via Lightsail Container Service
```

See `architecture.md` → Section 8 for full step-by-step deployment instructions.

---

## Roadmap

- **Phase 1** ✅ — Core MVP: leads, AI advisory, email reminders, dashboard
- **Phase 2** 🔜 — WhatsApp bot, objection handler, document assistant, human-in-loop approval
- **Phase 3** 🔜 — Multi-advisor teams, mobile app, live insurer catalog, advanced analytics
