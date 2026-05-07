# Phase 1 — UI Testing Results

**Date:** 7 May 2026  
**Version:** v1.0.0  
**Tester:** Swastik  
**Environment:** Local (API: http://localhost:8000, Dashboard: http://localhost:3000)

---

## Prerequisites

1. Docker database running:
   ```bash
   docker compose up -d db
   ```

2. FastAPI backend running:
   ```bash
   source .venv/bin/activate
   uvicorn app.main:app --reload
   ```

3. Next.js dashboard running:
   ```bash
   cd dashboard
   npm run dev
   ```

4. Open browser at `http://localhost:3000`

---

## Test Results

### Screen 1 — Dashboard (`/`)

| # | Test | Steps | Expected | Result |
|---|---|---|---|---|
| 1.1 | Stats cards load | Open `http://localhost:3000` | Total Leads, New Leads, Converted, Due in 30 Days cards visible | ✅ Pass |
| 1.2 | Advisor name dynamic | Check welcome message | Shows advisor name from DB ("Welcome back, Amit Singh.") | ✅ Pass |
| 1.3 | Recent Leads list | Check leads section | Shows client name, goals, status badge | ✅ Pass |
| 1.4 | Upcoming Renewals list | Check renewals section | Shows client name, product, premium, due date | ✅ Pass |

**Observed output:**
```
Welcome back, Amit Singh.
Total Leads: 1 | New Leads: 0 | Converted: 0 | Due in 30 Days: 1
Recent Leads: Rajesh Kumar — interested
Upcoming Renewals: Rajesh Kumar — Tech Term Plan — ₹12,000 — 2026-05-13
```

---

### Screen 2 — Leads (`/leads`)

| # | Test | Steps | Expected | Result |
|---|---|---|---|---|
| 2.1 | Lead list loads | Click Leads in sidebar | Table with all clients visible | ✅ Pass |
| 2.2 | Add new lead | Click "Add Lead" → fill form → submit | New client appears in list | ✅ Pass |
| 2.3 | Status filter | Click "interested" filter tab | Only interested clients shown | ✅ Pass |
| 2.4 | Inline status update | Change status via dropdown in row | Status updates immediately in DB | ✅ Pass |
| 2.5 | Analyze link | Click "Analyze" on a client | Navigates to `/leads/{id}` | ✅ Pass |

**Add Lead test data used:**
```
Name:           Priya Sharma
Email:          priya@example.com
Phone:          9876543211
Age:            28
Annual Income:  ₹8,00,000
Family Size:    3
Risk Appetite:  medium
Goals:          health insurance and term plan
```

---

### Screen 3 — Lead Detail (`/leads/{id}`)

| # | Test | Steps | Expected | Result |
|---|---|---|---|---|
| 3.1 | Client profile displays | Open lead detail | Name, email, phone, age, income, family size, risk appetite, goals shown | ✅ Pass |
| 3.2 | Analyze Needs (AI) | Click "Analyze Needs" | LLM returns gap analysis with priorities and tax benefits | ✅ Pass |
| 3.3 | Recommend Products (AI) | Click "Recommend Products" after analysis | LLM returns top 3 products with comparison table and pitch order | ✅ Pass |

**Need Analysis output summary:**
- Identified gaps: Term Insurance, Health Insurance, Personal Accident, Motor Insurance
- High priority: Term Plan ₹80L–₹96L (₹6,000–₹10,000/yr), Health Cover ₹10L (₹12,000–₹15,000/yr)
- Tax benefits: 80C (term), 80D (health)

**Product Recommendations output summary:**
```
1. Max Life Smart Secure Plus Plan  — ₹8,500/yr  — ₹1 Crore SA
2. Star Comprehensive Health Plan   — ₹12,000/yr — ₹10 Lakh SA
3. SecureHealth Gold Plan           — ₹12,500/yr — ₹10 Lakh SA
```
- Pitch order: Term first → Star Health → SecureHealth Gold

---

### Screen 4 — Renewals (`/renewals`)

| # | Test | Steps | Expected | Result |
|---|---|---|---|---|
| 4.1 | Renewals list loads | Click Renewals in sidebar | Table with upcoming policies, due dates, and actions | ✅ Pass |
| 4.2 | Days filter | Change dropdown (7 / 15 / 30 days) | List refreshes with filtered policies | ✅ Pass |
| 4.3 | Preview email (draft) | Click "Preview & Send" | Modal opens with AI-drafted email (To, Subject, Body) | ✅ Pass |
| 4.4 | Email content correct | Check modal content | Client email, policy details, premium, due date, advisor name all correct | ✅ Pass |
| 4.5 | Send email | Click "Send Email" in modal | Send attempted, logged to DB, navigates to Email Logs | ✅ Pass |

**Email preview observed:**
```
To:      rajesh@example.com
Subject: Gentle Reminder: Upcoming Premium Due for Your LIC Policy
Body:    Dear Rajesh Kumar, ... Policy: LIC-2024-001 ... ₹12,000 ... 2026-05-13
         Regards, Amit Singh
```

> **Note:** Send status shows `failed` because `SENDGRID_API_KEY` in `.env` is a placeholder.  
> This is expected behaviour — failure is caught gracefully, logged to DB, no crash.  
> With a real SendGrid key the status will be `sent`.

---

### Screen 5 — Email Logs (`/email-logs`)

| # | Test | Steps | Expected | Result |
|---|---|---|---|---|
| 5.1 | Log list loads | Click Email Logs in sidebar | Table with subject, status, sent-at for each email | ✅ Pass |
| 5.2 | Expandable body | Click "View" on any row | Full email body expands inline | ✅ Pass |
| 5.3 | Status badge | Check status column | `failed` / `sent` badge visible per log | ✅ Pass |

---

## Summary

| Screen | Tests | Passed | Failed |
|---|---|---|---|
| Dashboard | 4 | 4 | 0 |
| Leads | 5 | 5 | 0 |
| Lead Detail (AI) | 3 | 3 | 0 |
| Renewals | 5 | 5 | 0 |
| Email Logs | 3 | 3 | 0 |
| **Total** | **20** | **20** | **0** |

**Phase 1 UI testing: PASSED ✅**

---

## Known Limitations (Not Bugs)

| Item | Reason | Fix |
|---|---|---|
| Email send status = `failed` | No real SendGrid API key in `.env` | Add real `SENDGRID_API_KEY` |
| Goals field shows "string" for Rajesh Kumar | Test data inserted with placeholder value | Update via API or psql |

---

## Phase 2 — Next Steps

- WhatsApp reminder bot (Meta Cloud API)
- Pitch & objection handler
- Policy document assistant (PDF upload + summarize)
- Human-in-loop email approval before sending
