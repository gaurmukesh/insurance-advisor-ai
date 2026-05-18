# Phase 1 Manual UI Testing Guide

**Environment:** Local  
**API:** http://localhost:8000  
**Dashboard:** http://localhost:3000

---

## Prerequisites

Start the database, backend, and frontend:

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

The dashboard picks the first advisor from the DB. Skip this if one already exists.

```bash
curl -X POST http://localhost:8000/api/v1/advisors \
  -H "Content-Type: application/json" \
  -d '{"name":"Amit Singh","email":"amit@test.com","phone":"9876543210"}'
```

---

## Step 2 — Dashboard (`/`)

- [ ] Page loads without errors
- [ ] Welcome message shows advisor name (`Welcome back, Amit Singh.`)
- [ ] 4 stat cards visible: **Total Leads**, **New Leads**, **Converted**, **Due in 30 Days**
- [ ] Empty state shows `0` values — no errors or blank screen

---

## Step 3 — Leads (`/leads`)

- [ ] Click **Leads** in sidebar → page loads, shows "0 clients"
- [ ] Click **Add Lead** → modal opens
- [ ] Fill in the form with this data:

  | Field         | Value                          |
  |---------------|-------------------------------|
  | Name          | Rajesh Kumar                  |
  | Email         | gaur.mukeshkumar@gmail.com    |
  | Phone         | 9988776655                    |
  | Age           | 38                            |
  | Annual Income | 1500000                       |
  | Family Size   | 3                             |
  | Goals         | retirement planning           |

- [ ] Click **Add Lead** → modal closes, lead appears in table
- [ ] Dashboard **Total Leads** stat increments to `1`
- [ ] Click the status dropdown → change `new` → `interested` → pill updates immediately
- [ ] Click **interested** filter → only Rajesh shows
- [ ] Click **All** filter → all leads show
- [ ] Click **Analyze →** on Rajesh → navigates to lead detail

---

## Step 4 — Lead Detail / AI Advisory (`/leads/{id}`)

- [ ] Client profile shows correct Age, Income, Goals, Risk Appetite
- [ ] Click **Analyze Needs** → spinner appears → analysis text loads (~5–10 s, real OpenAI call)
- [ ] Click **Recommend Products** → product list appears with names, premiums, sum assured

---

## Step 5 — Renewals + Email Send (`/renewals`)

First, create a test policy due in 15 days. Run these commands in the terminal:

```bash
# Get your advisor ID
ADVISOR_ID=$(curl -s "http://localhost:8000/api/v1/advisors" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")

# Get the client ID for Rajesh Kumar
CLIENT_ID=$(curl -s "http://localhost:8000/api/v1/leads?advisor_id=$ADVISOR_ID" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")

# Due date 15 days from today
DUE=$(date -v+15d +%Y-%m-%d)        # macOS
# DUE=$(date -d "+15 days" +%Y-%m-%d)  # Linux

# Create the policy
curl -X POST http://localhost:8000/api/v1/policies \
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
  }"
```

Now in the dashboard:

- [ ] Click **Renewals** → Rajesh Kumar's policy appears with due date ~15 days out
- [ ] Change filter to **Next 7 days** → policy disappears (it's due in 15 days)
- [ ] Change filter back to **Next 30 days** → policy reappears
- [ ] Click **Preview & Send Email** → spinner → email preview modal opens
- [ ] Modal shows correct **To**, **Subject**, and AI-drafted **Body**
- [ ] Click **Send Email** → modal closes
- [ ] Check **gaur.mukeshkumar@gmail.com** inbox — email arrives within 1–2 minutes

---

## Step 6 — Email Logs (`/email-logs`)

- [ ] Click **Email Logs** in sidebar
- [ ] Sent email appears with status `sent` (green checkmark)
- [ ] Click **View** → full email body expands inline
- [ ] Timestamp shows current date and time

---

## Pass Criteria

All checkboxes ticked = Phase 1 is working end-to-end through the UI with real AI (OpenAI) and real email delivery (SendGrid).
