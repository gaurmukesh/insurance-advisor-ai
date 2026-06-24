# Phase 1 Manual UI Testing Guide

**Environment:** Local  
**API:** http://localhost:8000  
**Dashboard:** http://localhost:3000

---

## Database Connection

The DB runs in Docker. Since `psql` is not installed locally, use this alias to query it:

```bash
# Shorthand — use this throughout the guide
alias db='docker exec $(docker ps -qf "ancestor=pgvector/pgvector:pg16") psql -U admin -d insurance_ai -c'

# Usage
db "SELECT * FROM advisors;"
db "SELECT * FROM clients;"
db "\dt"   # list all tables
```

**Connection details:**

| Key      | Value          |
|----------|----------------|
| Host     | localhost:5432 |
| Database | insurance_ai   |
| User     | admin          |
| Password | secret         |

**All tables:**

| Table           | Purpose                           |
|-----------------|-----------------------------------|
| `advisors`      | Insurance advisors                |
| `clients`       | Leads / clients                   |
| `policies`      | Insurance policies per client     |
| `policy_chunks` | RAG vector chunks for policy docs |
| `interactions`  | Client-advisor interaction logs   |
| `email_logs`    | Email send history                |
| `whatsapp_logs` | WhatsApp message history          |

---

## Prerequisites — Start the Stack

```bash
# Terminal 1 — Database
docker compose up -d db

# Terminal 2 — Backend
source .venv/bin/activate
uvicorn app.main:app --reload

# Terminal 3 — Frontend
cd dashboard && npm run dev
```

Open **http://localhost:3000** in Chrome.

---

## Step 1 — Create an Advisor (one-time setup)

The dashboard auto-picks the first advisor from the DB. Skip if one already exists.

**Check if advisors exist:**

```bash
curl -s http://localhost:8000/api/v1/advisors | python3 -m json.tool
```

**DB check:**

```bash
docker exec $(docker ps -qf "ancestor=pgvector/pgvector:pg16") \
  psql -U admin -d insurance_ai -c "SELECT id, name, email FROM advisors;"
```

**If empty, create one:**

```bash
curl -X POST http://localhost:8000/api/v1/advisors \
  -H "Content-Type: application/json" \
  -d '{"name":"Amit Singh","email":"amit@test.com","phone":"9876543210"}'
```

**DB verify after creation:**

```bash
docker exec $(docker ps -qf "ancestor=pgvector/pgvector:pg16") \
  psql -U admin -d insurance_ai -c "SELECT id, name, email, created_at FROM advisors;"
```

Expected: one row with `id = advisor-001` (or a UUID), `name = Amit Singh`.

---

## Step 2 — Dashboard (`/`)

- [ ] Open **http://localhost:3000**
- [ ] Page loads without errors
- [ ] Welcome message shows advisor name (`Welcome back, Amit Singh.`)
- [ ] 4 stat cards visible: **Total Leads**, **New Leads**, **Converted**, **Due in 30 Days**
- [ ] All values show `0` — no blank screen or JS error

**API calls fired on load:**

```
GET /api/v1/advisors
GET /api/v1/leads?advisor_id=<id>
GET /api/v1/renewals/upcoming?advisor_id=<id>&days=30
```

---

## Step 3 — Create a Lead (`/leads`)

- [ ] Click **Leads** in sidebar → page loads
- [ ] Click **Add Lead** → modal opens
- [ ] Fill in the form:

  | Field         | Value                       |
  |---------------|-----------------------------|
  | Name          | Rajesh Kumar                |
  | Email         | gaur.mukeshkumar@gmail.com  |
  | Phone         | 9988776655                  |
  | Age           | 38                          |
  | Annual Income | 1500000                     |
  | Family Size   | 3                           |
  | Goals         | retirement planning         |

- [ ] Click **Add Lead** → modal closes, lead appears in the table
- [ ] Dashboard **Total Leads** increments to `1`

**DB verify after creation:**

```bash
docker exec $(docker ps -qf "ancestor=pgvector/pgvector:pg16") \
  psql -U admin -d insurance_ai \
  -c "SELECT id, name, email, status, created_at FROM clients ORDER BY created_at DESC LIMIT 5;"
```

Expected: new row with `name = Rajesh Kumar`, `status = new`.

---

## Step 4 — Filter and Update Lead Status (`/leads`)

- [ ] Click the status dropdown on Rajesh → change `new` → `interested` → pill updates immediately
- [ ] Click **interested** filter pill → only Rajesh shows
- [ ] Click **All** filter → all leads show again

**DB verify after status update:**

```bash
docker exec $(docker ps -qf "ancestor=pgvector/pgvector:pg16") \
  psql -U admin -d insurance_ai \
  -c "SELECT id, name, status, updated_at FROM clients WHERE name = 'Rajesh Kumar';"
```

Expected: `status = interested`, `updated_at` shows current timestamp.

---

## Step 5 — Lead Detail and AI Advisory (`/leads/{id}`)

- [ ] Click **Analyze →** on Rajesh → navigates to `/leads/{id}`
- [ ] Client profile shows correct Age, Income, Goals, Risk Appetite
- [ ] Click **Analyze Needs** → spinner appears → analysis text loads (~5–10 s, real OpenAI call)
- [ ] Click **Recommend Products** → product list appears with names, premiums, sum assured

> **Note:** These AI calls do not write to the DB. They return the result directly to the UI.

**DB confirm no writes occurred:**

```bash
docker exec $(docker ps -qf "ancestor=pgvector/pgvector:pg16") \
  psql -U admin -d insurance_ai \
  -c "SELECT COUNT(*) AS interaction_count FROM interactions;"
```

Expected: `0` (interactions table is not used in Phase 1 AI advisory flow).

---

## Step 6 — Create a Test Policy for Renewals

Run these commands in a terminal to seed a policy due in 15 days:

```bash
# Step 6a — Get the advisor ID
ADVISOR_ID=$(curl -s "http://localhost:8000/api/v1/advisors" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")
echo "ADVISOR_ID=$ADVISOR_ID"

# Step 6b — Get the client ID (first lead for this advisor)
CLIENT_ID=$(curl -s "http://localhost:8000/api/v1/leads?advisor_id=$ADVISOR_ID" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")
echo "CLIENT_ID=$CLIENT_ID"

# Step 6c — Compute due date (15 days from today)
DUE=$(date -v+15d +%Y-%m-%d)        # macOS
# DUE=$(date -d "+15 days" +%Y-%m-%d)  # Linux
echo "DUE=$DUE"

# Step 6d — Create the policy
curl -s -X POST http://localhost:8000/api/v1/policies \
  -H "Content-Type: application/json" \
  -d "{
    \"client_id\": \"$CLIENT_ID\",
    \"insurer_name\": \"LIC\",
    \"product_name\": \"Tech Term Plan\",
    \"policy_no\": \"LIC-MANUAL-001\",
    \"policy_type\": \"term\",
    \"premium_amount\": 9500,
    \"sum_assured\": 10000000,
    \"next_due_date\": \"$DUE\"
  }" | python3 -m json.tool
```

**DB verify after policy creation:**

```bash
docker exec $(docker ps -qf "ancestor=pgvector/pgvector:pg16") \
  psql -U admin -d insurance_ai \
  -c "SELECT id, client_id, policy_no, product_name, premium_amount, next_due_date FROM policies;"
```

Expected: one row with `policy_no = LIC-MANUAL-001`, `next_due_date` = 15 days from today.

---

## Step 7 — Renewals Page (`/renewals`)

- [ ] Click **Renewals** in sidebar
- [ ] Rajesh Kumar's policy appears with due date ~15 days out (orange colour)
- [ ] Change filter to **Next 7 days** → policy disappears (it's due in 15 days)
- [ ] Change filter back to **Next 30 days** → policy reappears
- [ ] Click **Preview & Send Email** → spinner → email preview modal opens
- [ ] Modal shows correct **To**, **Subject**, and AI-drafted **Body**

---

## Step 8 — Send Email (`/renewals`)

- [ ] In the email preview modal, click **Send Email** → modal closes
- [ ] Check **gaur.mukeshkumar@gmail.com** inbox — email arrives within 1–2 minutes

**DB verify after sending:**

```bash
docker exec $(docker ps -qf "ancestor=pgvector/pgvector:pg16") \
  psql -U admin -d insurance_ai \
  -c "SELECT id, client_id, subject, status, sent_at FROM email_logs ORDER BY sent_at DESC LIMIT 5;"
```

Expected: one row with `status = sent`, `sent_at` = now, subject contains "premium" or policy name.

---

## Step 9 — Email Logs (`/email-logs`)

- [ ] Click **Email Logs** in sidebar
- [ ] Sent email appears with status `sent` (green checkmark)
- [ ] Click **View** → full email body expands inline
- [ ] Timestamp shows current date and time

**DB verify:**

```bash
docker exec $(docker ps -qf "ancestor=pgvector/pgvector:pg16") \
  psql -U admin -d insurance_ai \
  -c "SELECT subject, status, sent_at FROM email_logs ORDER BY sent_at DESC;"
```

---

## Full DB State After All Steps Pass

Run this to see the final state across all tables:

```bash
docker exec $(docker ps -qf "ancestor=pgvector/pgvector:pg16") psql -U admin -d insurance_ai -c "
SELECT 'advisors'      AS tbl, COUNT(*) FROM advisors UNION ALL
SELECT 'clients'       AS tbl, COUNT(*) FROM clients  UNION ALL
SELECT 'policies'      AS tbl, COUNT(*) FROM policies UNION ALL
SELECT 'email_logs'    AS tbl, COUNT(*) FROM email_logs UNION ALL
SELECT 'policy_chunks' AS tbl, COUNT(*) FROM policy_chunks UNION ALL
SELECT 'interactions'  AS tbl, COUNT(*) FROM interactions UNION ALL
SELECT 'whatsapp_logs' AS tbl, COUNT(*) FROM whatsapp_logs
ORDER BY tbl;
"
```

Expected counts after a single clean run:

| Table           | Count |
|-----------------|-------|
| advisors        | ≥ 1   |
| clients         | ≥ 1   |
| policies        | ≥ 1   |
| email_logs      | ≥ 1   |
| policy_chunks   | 0 (unless PDFs ingested) |
| interactions    | 0     |
| whatsapp_logs   | 0     |

---

## Pass Criteria

All checkboxes ticked = Phase 1 is working end-to-end through the UI with real AI (OpenAI) and real email delivery (SendGrid).
