# Phase 1 — Complete End-to-End Flow Walkthrough

Covers every layer with real code: UI (TSX) → lib/api.ts → FastAPI route → module → DB → external service.

---

## 0. App Startup

### Backend — `app/main.py`

```bash
uvicorn app.main:app --reload
```

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_observability()          # connects LangFuse + Sentry
    await init_db()               # creates all DB tables if missing
    scheduler.add_job(run_premium_reminder_job, "cron", hour=8, minute=0)
    scheduler.start()             # daily 8 AM automatic reminder job
    yield
    scheduler.shutdown()
```

### DB initialisation — `app/db/postgres.py`

```python
engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)  # creates all tables
```

**Tables created on startup:**

| Table | Purpose |
|---|---|
| `advisors` | Advisor accounts |
| `clients` | Leads / clients |
| `policies` | Insurance policies per client |
| `email_logs` | Every email sent or drafted |
| `interactions` | Advisor-client interaction history |
| `whatsapp_logs` | WhatsApp messages sent |
| `policy_chunks` | RAG vector store (pgvector) |

### DB session per request — `app/db/postgres.py`

Every FastAPI route receives a fresh `AsyncSession` via dependency injection:

```python
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session               # session opened before route runs
                                    # auto-closed after route returns
```

Routes declare it with `db: AsyncSession = Depends(get_db)`.

---

### Frontend — `dashboard/app/layout.tsx`

```bash
cd dashboard && npm run dev
```

```tsx
export default function RootLayout({ children }) {
  return (
    <html>
      <body>
        <Providers>              {/* wraps React Query + AdvisorContext */}
          <Sidebar />            {/* nav links */}
          <main>{children}</main>
        </Providers>
      </body>
    </html>
  );
}
```

### Providers — `dashboard/components/Providers.tsx`

```tsx
export default function Providers({ children }) {
  const [queryClient] = useState(() => new QueryClient());
  return (
    <QueryClientProvider client={queryClient}>   {/* React Query cache */}
      <AdvisorProvider>{children}</AdvisorProvider>
    </QueryClientProvider>
  );
}
```

### Advisor context — `dashboard/lib/AdvisorContext.tsx`

Fires immediately on every page load. All pages wait for `advisorId` before fetching their own data.

```tsx
export function AdvisorProvider({ children }) {
  const { data, isLoading } = useQuery({
    queryKey: ["advisors"],
    queryFn: getAdvisors,          // GET /api/v1/advisors
    staleTime: Infinity,           // never refetched unless invalidated
  });

  const advisor = data?.[0] ?? null;  // always picks the first advisor

  return (
    <AdvisorContext.Provider value={{ advisor, isLoading }}>
      {children}
    </AdvisorContext.Provider>
  );
}
```

**Call chain:**

```
AdvisorContext mounts
  → lib/api.ts: getAdvisors()
      → axios.get("/api/v1/advisors")
          → app/api/routes/advisors.py: list_advisors()
              → SELECT * FROM advisors ORDER BY created_at
          ← [{ id, name, email, phone, ... }]
      ← advisors array
  ← advisor = advisors[0]  stored in React context
```

---

## 1. Dashboard (`/`)

**File:** `dashboard/app/page.tsx`

```tsx
export default function DashboardPage() {
  const { advisor } = useAdvisor();
  const advisorId = advisor?.id ?? "";

  const { data: leads = [] } = useQuery({
    queryKey: ["leads", advisorId],
    queryFn: () => getLeads(advisorId),     // GET /api/v1/leads?advisor_id=...
    enabled: !!advisorId,                   // waits until advisor is loaded
  });

  const { data: renewals = [] } = useQuery({
    queryKey: ["renewals", advisorId],
    queryFn: () => getUpcomingRenewals(advisorId, 30),  // GET /api/v1/renewals/upcoming
    enabled: !!advisorId,
  });

  const converted = leads.filter((l) => l.status === "converted").length;
  const newLeads  = leads.filter((l) => l.status === "new").length;
  // stats computed client-side from the already-fetched leads array
}
```

**lib/api.ts:**

```typescript
export const getLeads = (advisor_id: string, status?: string) =>
  api.get<Client[]>("/api/v1/leads", { params: { advisor_id, status } })
     .then((r) => r.data);

export const getUpcomingRenewals = (advisor_id: string, days = 30) =>
  api.get<Policy[]>("/api/v1/renewals/upcoming", { params: { advisor_id, days } })
     .then((r) => r.data);
```

**Route — `app/api/routes/clients.py`:**

```python
@router.get("/leads")
async def list_leads(
    advisor_id: str,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Client).where(Client.advisor_id == advisor_id)
    if status:
        query = query.where(Client.status == status)
    query = query.order_by(Client.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/renewals/upcoming")
async def upcoming_renewals(
    advisor_id: str,
    days: int = 30,
    db: AsyncSession = Depends(get_db),
):
    today = date.today()
    until = today + timedelta(days=days)

    result = await db.execute(
        select(Policy, Client)
        .join(Client, Policy.client_id == Client.id)
        .where(Client.advisor_id == advisor_id)
        .where(Policy.next_due_date >= today)
        .where(Policy.next_due_date <= until)
        .order_by(Policy.next_due_date)
    )
    rows = result.all()
    return [
        {
            "policy_id": policy.id,
            "product_name": policy.product_name,
            "insurer_name": policy.insurer_name,
            "premium_amount": policy.premium_amount,
            "next_due_date": str(policy.next_due_date),
            "client_name": client.name,
            "client_email": client.email,
            "client_phone": client.phone,
        }
        for policy, client in rows
    ]
```

**SQL executed:**

```sql
-- leads
SELECT * FROM clients WHERE advisor_id = 'advisor-001' ORDER BY created_at DESC;

-- renewals
SELECT policies.*, clients.*
FROM policies
JOIN clients ON policies.client_id = clients.id
WHERE clients.advisor_id = 'advisor-001'
  AND policies.next_due_date >= CURRENT_DATE
  AND policies.next_due_date <= CURRENT_DATE + INTERVAL '30 days'
ORDER BY policies.next_due_date ASC;
```

**DB tables read:** `clients`, `policies`

---

## 2. Leads Page (`/leads`)

**File:** `dashboard/app/leads/page.tsx`

```tsx
export default function LeadsPage() {
  const [showModal, setShowModal]     = useState(false);
  const [filterStatus, setFilterStatus] = useState("");
  const qc       = useQueryClient();
  const { advisor } = useAdvisor();
  const advisorId   = advisor?.id ?? "";

  // fetches leads — re-runs when advisorId or filterStatus changes
  const { data: leads = [], isLoading } = useQuery({
    queryKey: ["leads", advisorId, filterStatus],
    queryFn: () => getLeads(advisorId, filterStatus || undefined),
    enabled: !!advisorId,
  });

  // inline status update
  const statusMutation = useMutation({
    mutationFn: ({ id, status }) => updateLead(id, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["leads"] }),
    // invalidate causes React Query to refetch the leads list
  });
}
```

---

### 2a. Create Lead

User fills form → clicks **Add Lead**.

**`AddLeadModal` in `dashboard/app/leads/page.tsx`:**

```tsx
const mutation = useMutation({
  mutationFn: (data: Partial<Client>) => createLead(data),
  onSuccess: () => {
    qc.invalidateQueries({ queryKey: ["leads"] });  // refresh list
    onClose();                                        // close modal
  },
});

const handle = (e: React.FormEvent) => {
  e.preventDefault();
  mutation.mutate({
    advisor_id: advisorId,
    ...form,
    age:         form.age         ? Number(form.age)         : undefined,
    income:      form.income      ? Number(form.income)      : undefined,
    family_size: form.family_size ? Number(form.family_size) : undefined,
  });
};
```

**lib/api.ts:**

```typescript
export const createLead = (data: Partial<Client>) =>
  api.post<Client>("/api/v1/leads", data).then((r) => r.data);
```

**Route — `app/api/routes/clients.py`:**

```python
class ClientCreate(BaseModel):
    advisor_id:    str
    name:          str
    email:         str | None = None
    phone:         str | None = None
    age:           int | None = None
    income:        float | None = None
    family_size:   int | None = None
    risk_appetite: str | None = None
    goals:         str | None = None
    notes:         str | None = None

@router.post("/leads")
async def create_lead(data: ClientCreate, db: AsyncSession = Depends(get_db)):
    client = Client(**data.model_dump())   # maps Pydantic fields → ORM model
    db.add(client)
    await db.commit()
    await db.refresh(client)               # reload from DB to get server defaults
    return client
```

**SQL executed:**

```sql
INSERT INTO clients (id, advisor_id, name, email, phone, age, income,
                     family_size, risk_appetite, goals, status, created_at)
VALUES (gen_random_uuid(), 'advisor-001', 'Mukesh Gaur', ..., 'new', NOW());
```

`status` defaults to `"new"` — set in the SQLAlchemy model, not by the route.

---

### 2b. Filter by Status

User clicks a status pill — updates `filterStatus` state → `useQuery` key changes → new request fires.

```tsx
{STATUS_OPTIONS.map((s) => (
  <button key={s} onClick={() => setFilterStatus(s)}>
    {s}
  </button>
))}
```

**lib/api.ts → Route:**

```
GET /api/v1/leads?advisor_id=advisor-001&status=interested

→ SELECT * FROM clients
  WHERE advisor_id = 'advisor-001' AND status = 'interested'
  ORDER BY created_at DESC;
```

---

### 2c. Update Status (inline dropdown)

User changes the dropdown in a table row.

**TSX:**

```tsx
<select
  value={client.status}
  onChange={(e) => statusMutation.mutate({ id: client.id, status: e.target.value })}
>
  {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
</select>
```

**lib/api.ts:**

```typescript
export const updateLead = (id: string, data: Partial<Client>) =>
  api.put<Client>(`/api/v1/leads/${id}`, data).then((r) => r.data);
```

**Route — `app/api/routes/clients.py`:**

```python
class ClientUpdate(BaseModel):
    status: str | None = None
    notes:  str | None = None
    goals:  str | None = None

@router.put("/leads/{client_id}")
async def update_lead(client_id: str, data: ClientUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(client, field, value)   # only updates fields that were sent

    await db.commit()
    await db.refresh(client)
    return client
```

**SQL executed:**

```sql
SELECT * FROM clients WHERE id = 'uuid';
UPDATE clients SET status = 'interested', updated_at = NOW() WHERE id = 'uuid';
```

On success → `qc.invalidateQueries(["leads"])` → list refetches.

---

## 3. Lead Detail (`/leads/{id}`)

**File:** `dashboard/app/leads/[id]/page.tsx`

```tsx
export default function ClientDetailPage({ params }) {
  const { id } = use(params);                          // Next.js 15 async params

  const { data: client, isLoading } = useQuery({
    queryKey: ["client", id],
    queryFn: () => getLead(id),                        // GET /api/v1/leads/{id}
  });
}
```

**lib/api.ts:**

```typescript
export const getLead = (id: string) =>
  api.get<Client>(`/api/v1/leads/${id}`).then((r) => r.data);
```

**Route:**

```python
@router.get("/leads/{client_id}")
async def get_lead(client_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client
```

```sql
SELECT * FROM clients WHERE id = 'uuid';
```

---

### 3a. Analyze Needs (AI)

User types existing policies (optional) → clicks **Analyze Needs**.

**TSX:**

```tsx
const analyzeMutation = useMutation({
  mutationFn: () => analyzeClient(id, existingPolicies),
  onSuccess: (data) => setAnalysis(data.analysis),
});
```

**lib/api.ts:**

```typescript
export const analyzeClient = (client_id: string, existing_policies?: string) =>
  api.post("/api/v1/analyze-client", { client_id, existing_policies })
     .then((r) => r.data);
```

**Route — `app/api/routes/recommendations.py`:**

```python
@router.post("/analyze-client")
async def analyze_client(data: AnalyzeRequest, db: AsyncSession = Depends(get_db)):
    # Step 1 — fetch client from DB
    result = await db.execute(select(Client).where(Client.id == data.client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Step 2 — build profile dict from DB row
    profile = {
        "name":              client.name,
        "age":               client.age,
        "income":            client.income,
        "family_size":       client.family_size,
        "risk_appetite":     client.risk_appetite,
        "goals":             client.goals,
        "existing_policies": data.existing_policies or "None",
    }

    # Step 3 — call analyzer module (RAG + GPT-4o)
    analysis = await analyze_client_needs(db, profile)
    return {"client_id": client.id, "client_name": client.name, "analysis": analysis}
```

**Module — `app/modules/need_analyzer.py`:**

```python
SYSTEM_PROMPT = """You are an expert insurance advisor assistant in India.
Analyze the client profile and identify insurance gaps.
Be specific, practical, and refer to Indian insurance products
(term, health, motor, ULIP, personal accident).
Always mention relevant tax benefits under 80C and 80D where applicable.
Format your response clearly with sections."""

async def analyze_client_needs(db: AsyncSession, client_profile: dict) -> str:
    # Step 1 — RAG: build query from client goals
    query = f"insurance for {client_profile.get('goals', 'general')}"

    # Step 2 — retrieve relevant policy chunks from pgvector
    context = await retrieve_context(db, query)

    # Step 3 — build user message with profile + RAG context
    user_message = f"""
Analyze this client's insurance needs and identify gaps:

Client Profile:
- Name: {client_profile.get('name')}
- Age: {client_profile.get('age')}
- Annual Income: ₹{client_profile.get('income', 0):,.0f}
- Family Size: {client_profile.get('family_size')}
- Risk Appetite: {client_profile.get('risk_appetite')}
- Goals: {client_profile.get('goals')}
- Existing Policies: {client_profile.get('existing_policies', 'None mentioned')}

Relevant Policy Context:
{context}

Provide:
1. Current coverage assessment
2. Insurance gaps identified
3. Priority recommendations (high/medium/low)
4. Estimated premium ranges
5. Tax benefit opportunities
"""
    # Step 4 — call GPT-4o
    return await chat(SYSTEM_PROMPT, user_message, trace_name="need_analyzer")
```

**RAG layer — `app/core/rag.py`:**

```python
async def retrieve_context(db: AsyncSession, query: str, top_k: int = 5) -> str:
    results = await similarity_search(db, query, top_k=top_k)
    if not results:
        return ""                                  # empty if no PDFs ingested
    return "\n\n".join(r["content"] for r in results)
```

**Vector store — `app/db/vector_store.py`:**

```python
async def similarity_search(db: AsyncSession, query: str, top_k: int = 5) -> list[dict]:
    # Call 1 — embed the query string
    query_embedding = await get_embedding(query)   # OpenAI text-embedding-3-small → 1536 floats

    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    # Call 2 — cosine similarity search in pgvector
    result = await db.execute(
        text("""
            SELECT content, metadata,
                   1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
            FROM policy_chunks
            ORDER BY embedding <=> CAST(:embedding AS vector)
            LIMIT :top_k
        """),
        {"embedding": embedding_str, "top_k": top_k},
    )
    rows = result.fetchall()
    return [{"content": r.content, "metadata": r.metadata, "similarity": r.similarity} for r in rows]
```

**LLM layer — `app/core/llm.py`:**

```python
async def chat(system_prompt: str, user_message: str, trace_name: str = "llm_call") -> str:
    return await _call("gpt-4o", system_prompt, user_message, trace_name)

async def _call(model, system_prompt, user_message, trace_name) -> str:
    langfuse = get_langfuse()
    trace = langfuse.trace(name=trace_name) if langfuse else None

    response = await client.chat.completions.create(
        model=model,               # "gpt-4o"
        max_tokens=2048,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message},
        ],
    )

    output = response.choices[0].message.content

    if trace:
        trace.generation(
            name=trace_name,
            model=model,
            input=user_message,
            output=output,
            usage={
                "input":  response.usage.prompt_tokens,
                "output": response.usage.completion_tokens,
            },
        )
    return output
```

**Full call chain for Analyze Needs:**

```
TSX: analyzeMutation.mutate()
  → lib/api.ts: analyzeClient(id, existingPolicies)
      → POST /api/v1/analyze-client
          → recommendations.py: analyze_client()
              → SELECT * FROM clients WHERE id = :id          [DB read]
              → need_analyzer.analyze_client_needs(db, profile)
                  → rag.retrieve_context(db, "insurance for retirement planning")
                      → vector_store.similarity_search(db, query)
                          → openai.embeddings.create(...)     [OpenAI API]
                          → SELECT FROM policy_chunks ORDER BY embedding <=> ... LIMIT 5  [DB read]
                      ← top 5 text chunks (or "")
                  → llm.chat(system_prompt, user_message)
                      → openai.chat.completions.create(model="gpt-4o", ...)  [OpenAI API]
                      → langfuse.trace.generation(...)         [LangFuse]
                  ← analysis text string
              ← { client_id, client_name, analysis }
  ← rendered in UI (not saved to DB)
```

**DB write:** None. Analysis is returned to UI only.

---

### 3b. Recommend Products (AI)

User clicks **Recommend Products** after analysis appears.

**TSX:**

```tsx
const recommendMutation = useMutation({
  mutationFn: () => recommendProducts(id, analysis),
  onSuccess: (data) => setRecommendations(data.recommendations),
});
```

**lib/api.ts:**

```typescript
export const recommendProducts = (client_id: string, need_analysis: string) =>
  api.post("/api/v1/recommend-products", { client_id, need_analysis })
     .then((r) => r.data);
```

**Route — `app/api/routes/recommendations.py`:**

```python
@router.post("/recommend-products")
async def recommend(data: RecommendRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Client).where(Client.id == data.client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    profile = {
        "age":               client.age,
        "income":            client.income,
        "family_size":       client.family_size,
        "risk_appetite":     client.risk_appetite,
        "goals":             client.goals,
        "existing_policies": data.existing_policies or "None",
    }

    recommendations = await recommend_products(db, profile, data.need_analysis)
    return {"client_id": client.id, "client_name": client.name, "recommendations": recommendations}
```

**Module — `app/modules/product_recommender.py`:**

```python
async def recommend_products(db, client_profile, need_analysis) -> str:
    # RAG query uses goals + risk appetite (different from analyze)
    query = f"{client_profile.get('goals', '')} insurance {client_profile.get('risk_appetite', '')} risk"
    context = await retrieve_context(db, query, top_k=6)   # 6 chunks vs 5 in analyze

    user_message = f"""
Recommend top 3 insurance products for this client:

Client Profile:
- Age: {client_profile.get('age')}
- Annual Income: ₹{client_profile.get('income', 0):,.0f}
- Family Size: {client_profile.get('family_size')}
- Risk Appetite: {client_profile.get('risk_appetite')}
- Goals: {client_profile.get('goals')}

Need Analysis Summary:
{need_analysis[:500]}          ← first 500 chars only to save tokens

Available Policy Information:
{context}

Provide:
1. Top 3 product recommendations with insurer names
2. Comparison table (product, premium, sum assured, key benefit)
3. Why each product suits this client
4. Which one to pitch first and why
"""
    return await chat(SYSTEM_PROMPT, user_message, trace_name="product_recommender")
```

**Model:** `gpt-4o`
**DB read:** `clients`, `policy_chunks` (via RAG, same flow as 3a)
**DB write:** None

---

## 4. Renewals Page (`/renewals`)

**File:** `dashboard/app/renewals/page.tsx`

```tsx
export default function RenewalsPage() {
  const [days, setDays] = useState(30);
  const { advisor } = useAdvisor();

  const { data: renewals = [], isLoading } = useQuery({
    queryKey: ["renewals", advisorId, days],
    queryFn: () => getUpcomingRenewals(advisorId, days),
    enabled: !!advisorId,
  });

  // urgency colour — computed client-side from next_due_date
  const urgencyColor = (date: string) => {
    const days = Math.ceil((new Date(date).getTime() - Date.now()) / 86400000);
    if (days <= 7)  return "text-red-600 font-semibold";
    if (days <= 15) return "text-orange-500 font-medium";
    return "text-gray-600";
  };
}
```

Changing the days dropdown updates `days` state → `queryKey` changes → React Query refetches.

**SQL executed (same route as dashboard):**

```sql
SELECT policies.*, clients.*
FROM policies
JOIN clients ON policies.client_id = clients.id
WHERE clients.advisor_id = 'advisor-001'
  AND policies.next_due_date >= CURRENT_DATE
  AND policies.next_due_date <= CURRENT_DATE + INTERVAL '30 days'
ORDER BY policies.next_due_date ASC;
```

---

### 4a. Draft Email Preview

User clicks **Preview & Send Email**.

**TSX:**

```tsx
const draftMutation = useMutation({
  mutationFn: (policy_id: string) => draftReminderEmail(policy_id, advisorName),
  onSuccess: (data, policy_id) => {
    setPreview(data);              // stores { subject, body, client_email }
    setSelectedPolicyId(policy_id);
  },
});
```

**lib/api.ts:**

```typescript
export const draftReminderEmail = (policy_id: string, advisor_name: string) =>
  api.post("/api/v1/draft-email/reminder", { policy_id, advisor_name })
     .then((r) => r.data);
```

**Route — `app/api/routes/emails.py`:**

```python
@router.post("/draft-email/reminder")
async def draft_reminder(data: ReminderEmailRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Policy, Client)
        .join(Client, Policy.client_id == Client.id)
        .where(Policy.id == data.policy_id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Policy not found")

    policy, client = row
    email_content = await generate_premium_reminder_email(
        client_name=client.name,
        policy_no=policy.policy_no,
        product_name=policy.product_name,
        insurer_name=policy.insurer_name,
        premium_amount=policy.premium_amount,
        due_date=str(policy.next_due_date),
        advisor_name=data.advisor_name,
    )
    return {"client_name": client.name, "client_email": client.email, **email_content}
```

**Module — `app/modules/email_generator.py`:**

```python
async def generate_premium_reminder_email(...) -> dict:
    user_message = f"""
Write a premium due reminder email with these details:
- Client Name: {client_name}
- Policy Number: {policy_no}
- Product: {product_name} by {insurer_name}
- Premium Amount: ₹{premium_amount:,.0f}
- Due Date: {due_date}
- Advisor Name: {advisor_name}

Return in this exact format:
SUBJECT: <subject line>
BODY:
<email body>
"""
    response = await chat_mini(SYSTEM_PROMPT, user_message, trace_name="email_generator_reminder")
    #                  ↑ gpt-4o-mini — cheaper model, email is a simpler task
    return _parse_email_response(response)

def _parse_email_response(response: str) -> dict:
    lines = response.strip().split("\n")
    subject = ""
    body_lines = []
    in_body = False
    for line in lines:
        if line.startswith("SUBJECT:"):
            subject = line.replace("SUBJECT:", "").strip()
        elif line.strip() == "BODY:":
            in_body = True
        elif in_body:
            body_lines.append(line)
    return {"subject": subject, "body": "\n".join(body_lines).strip()}
```

**DB read:** `policies` JOIN `clients`
**DB write:** None — preview only, nothing stored.

UI renders the **Email Preview modal** with `subject`, `body`, `client_email`.

---

### 4b. Send Email

User clicks **Send Email** in modal.

**TSX:**

```tsx
const sendMutation = useMutation({
  mutationFn: () => sendReminderEmail(selectedPolicyId, advisorName),
  onSuccess: () => {
    setPreview(null);           // close modal
    setSelectedPolicyId("");
  },
});
```

**lib/api.ts:**

```typescript
export const sendReminderEmail = (policy_id: string, advisor_name: string) =>
  api.post("/api/v1/send-email/reminder", { policy_id, advisor_name })
     .then((r) => r.data);
```

**Route — `app/api/routes/emails.py`:**

```python
@router.post("/send-email/reminder")
async def send_reminder(data: ReminderEmailRequest, db: AsyncSession = Depends(get_db)):
    # Step 1 — fetch policy + client
    result = await db.execute(
        select(Policy, Client)
        .join(Client, Policy.client_id == Client.id)
        .where(Policy.id == data.policy_id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Policy not found")

    policy, client = row
    if not client.email:
        raise HTTPException(status_code=400, detail="Client has no email address")

    # Step 2 — generate email via GPT-4o-mini (same as draft)
    email_content = await generate_premium_reminder_email(
        client_name=client.name,
        policy_no=policy.policy_no,
        product_name=policy.product_name,
        insurer_name=policy.insurer_name,
        premium_amount=policy.premium_amount,
        due_date=str(policy.next_due_date),
        advisor_name=data.advisor_name,
    )

    # Step 3 — send via SendGrid
    sent = send_email(client.email, email_content["subject"], email_content["body"])

    # Step 4 — write log to DB regardless of success or failure
    log = EmailLog(
        client_id=client.id,
        policy_id=policy.id,
        subject=email_content["subject"],
        body=email_content["body"],
        status="sent" if sent else "failed",
    )
    db.add(log)
    await db.commit()

    return {"status": status, "client_email": client.email, **email_content}


def send_email(to_email: str, subject: str, body: str) -> bool:
    message = Mail(
        from_email=settings.SENDGRID_FROM_EMAIL,  # from .env
        to_emails=to_email,
        subject=subject,
        plain_text_content=body,
    )
    try:
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        sg.send(message)           # real HTTP call to SendGrid API
        return True
    except Exception:
        return False               # failure caught — never crashes the route
```

**SQL executed:**

```sql
SELECT policies.*, clients.*
FROM policies JOIN clients ON policies.client_id = clients.id
WHERE policies.id = 'uuid';

INSERT INTO email_logs (id, client_id, policy_id, subject, body, status, sent_at)
VALUES (gen_random_uuid(), '...', '...', '...', '...', 'sent', NOW());
```

**Full call chain for Send Email:**

```
TSX: sendMutation.mutate()
  → lib/api.ts: sendReminderEmail(policyId, advisorName)
      → POST /api/v1/send-email/reminder
          → emails.py: send_reminder()
              → SELECT policies JOIN clients WHERE policy.id = :id    [DB read]
              → email_generator.generate_premium_reminder_email(...)
                  → llm.chat_mini(system_prompt, user_message)
                      → openai.chat.completions.create(model="gpt-4o-mini")  [OpenAI API]
                  ← { subject, body }
              → send_email(client.email, subject, body)
                  → SendGridAPIClient.send(message)                   [SendGrid API]
              ← True / False
              → INSERT INTO email_logs (status="sent"/"failed")       [DB write]
          ← { status: "sent", client_email: "..." }
  ← modal closes
```

---

## 5. Email Logs (`/email-logs`)

**File:** `dashboard/app/email-logs/page.tsx`

```tsx
const { data: logs = [], isLoading } = useQuery({
  queryKey: ["email-logs"],
  queryFn: () => api.get<EmailLog[]>("/api/v1/email-logs").then((r) => r.data),
});
```

**Route — `app/api/routes/emails.py`:**

```python
@router.get("/email-logs")
async def get_email_logs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(EmailLog).order_by(EmailLog.sent_at.desc()).limit(100)
    )
    return result.scalars().all()
```

**SQL executed:**

```sql
SELECT * FROM email_logs ORDER BY sent_at DESC LIMIT 100;
```

**DB table read:** `email_logs`

User clicks **View** → body expands inline. No additional API call — body is already in the loaded data.

---

## DB Read/Write Summary

| Action | SQL | Tables |
|---|---|---|
| App load | SELECT | `advisors` |
| Dashboard load | SELECT, SELECT + JOIN | `clients`, `policies` |
| Create lead | INSERT | `clients` |
| Filter leads | SELECT + WHERE status | `clients` |
| Update status | SELECT + UPDATE | `clients` |
| View lead detail | SELECT | `clients` |
| Analyze Needs | SELECT, vector cosine search | `clients`, `policy_chunks` |
| Recommend Products | SELECT, vector cosine search | `clients`, `policy_chunks` |
| View renewals | SELECT + JOIN | `policies`, `clients` |
| Draft email preview | SELECT + JOIN | `policies`, `clients` |
| Send email | SELECT + JOIN, INSERT | `policies`, `clients`, `email_logs` |
| View email logs | SELECT | `email_logs` |

---

## API Call Summary

| Page | Method | Endpoint | Triggered by |
|---|---|---|---|
| All pages | GET | `/api/v1/advisors` | App load (AdvisorContext) |
| Dashboard | GET | `/api/v1/leads` | Page load |
| Dashboard | GET | `/api/v1/renewals/upcoming` | Page load |
| Leads | GET | `/api/v1/leads` | Page load / filter pill click |
| Leads | POST | `/api/v1/leads` | Add Lead form submit |
| Leads | PUT | `/api/v1/leads/{id}` | Status dropdown change |
| Lead detail | GET | `/api/v1/leads/{id}` | Page load |
| Lead detail | POST | `/api/v1/analyze-client` | Analyze Needs button |
| Lead detail | POST | `/api/v1/recommend-products` | Recommend Products button |
| Renewals | GET | `/api/v1/renewals/upcoming` | Page load / days filter change |
| Renewals | POST | `/api/v1/draft-email/reminder` | Preview & Send Email click |
| Renewals | POST | `/api/v1/send-email/reminder` | Send Email in modal |
| Email Logs | GET | `/api/v1/email-logs` | Page load |

---

## External Services

| Service | Used for | Model / SDK | Configured via |
|---|---|---|---|
| OpenAI | Analyze Needs, Recommend Products | `gpt-4o` | `OPENAI_API_KEY` |
| OpenAI | Email drafting | `gpt-4o-mini` | `OPENAI_API_KEY` |
| OpenAI | RAG embeddings | `text-embedding-3-small` | `OPENAI_API_KEY` |
| SendGrid | Sending emails | `SendGridAPIClient` | `SENDGRID_API_KEY` |
| LangFuse | LLM call tracing (optional) | Python SDK | `LANGFUSE_SECRET_KEY` |
| Sentry | Error tracking (optional) | Python SDK | `SENTRY_DSN` |
