# Requirements — Claims Settlement Analysis

Functional and non-functional requirements, derived from the current codebase
(`app/agents`, `app/core`, `app/mcp`, `dashboard/`) and the scale design in
`architecture.md`.

---

## Claims Settlement Analysis — Functional Requirements

| # | Requirement | Where it lives |
|---|---|---|
| C1 | Historical claims (multiple years) can be bulk-imported from CSV, idempotently, with claimant background attached to each claim | `POST /api/v1/claims/import`, `app/core/claims_ingest.py` |
| C2 | Free-text insurer decision remarks are normalised onto a fixed rejection/approval reason taxonomy (rules first, LLM fallback constrained to the taxonomy) | `app/core/claim_reasons.py` |
| C3 | System reports the primary reason for rejecting claims over a period (default past 12 months), with full breakdown by count, share and amount | `GET /api/v1/claims/analysis/rejection-reasons`, MCP `get_rejection_reasons` |
| C4 | System reports the primary reason for approving claims (full and partial) over a period | `GET /api/v1/claims/analysis/approval-reasons`, MCP `get_approval_reasons` |
| C5 | System quantifies the association between rejection and each claimant background attribute (chi-square, Cramér's V, point-biserial, per-bucket rejection rate, lift and dominant reason) | `GET /api/v1/claims/analysis/rejection-correlation`, MCP `get_rejection_correlation` |
| C6 | Year-by-year settlement ratio (count and amount) across the full history | `GET /api/v1/claims/analysis/overview` |
| C7 | Optional plain-language explanation of any analysis, generated from aggregates only | `explain=true` on analysis endpoints |

## Claims Settlement Analysis — Non-Functional Requirements

| Category | Requirement |
|---|---|
| **Correctness** | All counts and statistics are computed deterministically in code; the LLM never decides a number |
| **Privacy** | Individual claim/claimant rows never reach an LLM; only remarks (PII-scrubbed) for classification and aggregates for explanation |
| **Fairness** | Protected attributes (gender) are reported for auditing only and flagged as not to be used in decisions; correlations are labelled as associations, not causes |
| **Statistical honesty** | Buckets under 30 claims are flagged `low_sample`; attributes with a single value or one outcome report `insufficient_data` instead of a spurious statistic |
| **Access** | Import restricted to manager/admin; analysis returns aggregates only and requires authentication |

---

## Platform Functional Requirements (inherited)

| # | Requirement | Where it lives |
|---|---|---|
| 1 | Advisor can create, list, update, and track status of leads/clients (new → contacted → interested → converted) | `app/api/routes`, `clients`/`leads` tables |
| 2 | System analyzes a client profile (age, income, family, goals, risk appetite) and produces a coverage-gap + 80C/80D tax-opportunity analysis | `NeedsAnalysisAgent` |
| 3 | System recommends top-3 matching products via RAG over policy documents, cross-checked against structured coverage/exclusion facts | `ProductMatchingAgent`, `app/core/knowledge_graph.py` |
| 4 | Advisor can upload a policy PDF and get a plain-language summary, and search across ingested policy docs semantically | `/api/v1/ingest`, `/api/v1/documents/search`, `PolicyResearchAgent` |
| 5 | System extracts structured coverage/exclusion facts from insurer product-template PDFs at ingestion time (not client policies — gated by `_looks_like_product_template`) | `app/core/product_extraction.py` |
| 6 | System generates a sales pitch and structured objection rebuttals per client profile | `ObjectionHandlerAgent` |
| 7 | System detects policies due for renewal within N days, scores renewal risk, and drafts reminder emails/WhatsApp messages | `ClaimsRenewalsAgent`, `/api/v1/renewals/upcoming` |
| 8 | AI-drafted client-facing messages (email/WhatsApp) sit in an approval queue for the advisor to edit and approve before sending — nothing goes out unreviewed | `/api/v1/approval-queue` |
| 9 | An orchestrator chains the above agents end-to-end across a lead's lifecycle | `LeadNurturingAgent` |
| 10 | External tools (Claude Desktop/Code) can call 10 scoped tools — list/create leads, analyze needs, recommend, pitch, search docs, renewals — over MCP | `app/mcp/server.py` |
| 11 | Access is role-scoped: `advisor` sees only their own clients; `manager`/`admin` see across advisors | RLS policies + `app/mcp/rbac.py` |
| 12 | Advisor logs in with rate-limited credentials; MCP HTTP/SSE clients authenticate with revocable opaque tokens | `app/core/rate_limit.py`, `app/mcp/tokens.py` |
| 13 | Every AI output is checked against IRDAI marketing-claim rules and PII is stripped before any LLM call | `app/core/guardrails.py`, `app/core/pii_guard.py` |
| 14 | Every AI decision is written to an immutable, hashed audit log | `app/core/audit.py` |
| 15 | Advisor dashboard shows lead pipeline, renewal calendar, email/WhatsApp activity, and conversion metrics | `dashboard/app`, `/api/v1/metrics` |
| 16 | Prompts can be updated by version without a redeploy | `app/core/prompt_registry.py` |

---

## Platform Non-Functional Requirements (inherited)

| Category | Requirement | Notes |
|---|---|---|
| **Performance** | CRUD/dashboard routes respond fast enough to feel interactive under load (target: sub-200ms p95) | Needs sizing once real traffic exists |
| **Scalability** | Platform holds 10,000 concurrent advisor sessions without LLM latency (2–8s/call) degrading the rest of the system | Requires moving AI-invoking routes off the request thread — see the queue-decoupled design in the Scale Blueprint |
| **Availability** | No single point of failure in data or compute — Multi-AZ DB, autoscaled pods, DLQ for failed agent/ingestion jobs | Today's single Lightsail container doesn't meet this |
| **Security** | PII (Aadhaar/PAN/phone/email) never reaches an LLM call unscrubbed; secrets aren't baked into images or committed `.env` files; MCP tokens are individually revocable | Known open gap: prod `SECRET_KEY` and exposed DB/OpenAI creds — user has deferred fixing this |
| **Data isolation** | One advisor's clients/leads are invisible to another advisor at the database level, not just the API level | Enforced via Postgres RLS, not app-layer filtering alone |
| **Compliance** | Every AI-generated recommendation or message is auditable after the fact; no output violates IRDAI's prohibited-claims list | Audit log + guardrails already exist for this reason |
| **Observability** | LLM cost/latency/token usage, application errors, and business metrics are all independently traceable | LangFuse + Sentry + structured logs |
| **Maintainability** | Schema changes are replayable and idempotent; prompt copy changes don't require a deploy | Migration ledger table, prompt registry |
| **Cost efficiency** | Duplicate LLM calls are cached; compute scales down when idle rather than running fixed-size 24/7 | Semantic cache today; HPA/KEDA in the scale design |
| **Usability** | Advisors are the audience, not engineers — AI outputs are plain-language, and nothing client-facing sends without human review | Human-in-loop approval queue is a hard requirement, not a nice-to-have |

---

## Open Gap

No documented latency/accuracy SLA for the AI eval gate exists yet — CI blocks a
merge on regression (`tests/evals/run_evals.py`), but there's no stated target
(e.g. "recommendation accuracy ≥ X% on golden set"). Worth defining once the
eval harness's actual current thresholds are confirmed.
