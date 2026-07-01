"""
Generate realistic Indian insurance product brochure PDFs for RAG ingestion.
Run from project root: python scripts/generate_product_pdfs.py
"""

from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT

OUT_DIR = Path("data/policies")
OUT_DIR.mkdir(parents=True, exist_ok=True)

W, H = A4
styles = getSampleStyleSheet()

BRAND   = ParagraphStyle("brand",   parent=styles["Heading1"], fontSize=16, textColor=colors.HexColor("#1a3c6e"), spaceAfter=4)
TITLE   = ParagraphStyle("title",   parent=styles["Heading2"], fontSize=13, textColor=colors.HexColor("#1a3c6e"), spaceAfter=6)
SECTION = ParagraphStyle("section", parent=styles["Heading3"], fontSize=11, textColor=colors.HexColor("#c0392b"), spaceAfter=4, spaceBefore=10)
BODY    = ParagraphStyle("body",    parent=styles["Normal"],   fontSize=9,  leading=14, spaceAfter=3)
SMALL   = ParagraphStyle("small",   parent=styles["Normal"],   fontSize=8,  leading=12, textColor=colors.grey)

def tbl(data, col_widths=None, header_bg=colors.HexColor("#1a3c6e")):
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0),  header_bg),
        ("TEXTCOLOR",   (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",    (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f4f8")]),
        ("GRID",        (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING",     (0, 0), (-1, -1), 4),
    ]))
    return t

def doc(filename, title, content_fn):
    path = OUT_DIR / filename
    pdf  = SimpleDocTemplate(str(path), pagesize=A4,
                              leftMargin=2*cm, rightMargin=2*cm,
                              topMargin=2*cm,  bottomMargin=2*cm)
    story = []
    content_fn(story)
    pdf.build(story)
    print(f"  Created: {path}")


# ─────────────────────────────────────────────────────────────────────────────
# 1. TERM LIFE INSURANCE
# ─────────────────────────────────────────────────────────────────────────────
def term_life(story):
    story += [
        Paragraph("HDFC Life Insurance Co. Ltd.", BRAND),
        Paragraph("Click 2 Protect Super — Term Life Insurance", TITLE),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1a3c6e")),
        Spacer(1, 0.3*cm),
        Paragraph("Product Overview", SECTION),
        Paragraph(
            "HDFC Life Click 2 Protect Super is a pure term insurance plan that provides a high "
            "life cover at an affordable premium. It is a non-participating, non-linked, individual "
            "pure risk premium life insurance plan approved by IRDAI (UIN: 101N145V02).", BODY),
        Paragraph("Key Features", SECTION),
        tbl([
            ["Feature", "Details"],
            ["Product Type", "Pure Term Life Insurance (Non-ULIP, Non-Participating)"],
            ["Policy Term", "5 to 40 years (or till age 85, whichever is earlier)"],
            ["Minimum Sum Assured", "₹50 lakhs"],
            ["Maximum Sum Assured", "No limit (subject to underwriting)"],
            ["Entry Age", "18 to 65 years"],
            ["Maturity Age", "Up to 85 years"],
            ["Premium Payment Term", "Regular Pay / Limited Pay (5, 7, 10 years) / Single Pay"],
            ["Death Benefit Payout", "Lump sum / Monthly income / Lump sum + Monthly income"],
        ], col_widths=[7*cm, 11*cm]),
        Spacer(1, 0.3*cm),
        Paragraph("Indicative Annual Premiums (Non-Smoker, ₹1 Crore Cover)", SECTION),
        tbl([
            ["Age", "20-Year Term", "30-Year Term", "Till Age 85"],
            ["25 years", "₹7,800", "₹9,200", "₹11,500"],
            ["30 years", "₹9,400", "₹11,600", "₹14,200"],
            ["35 years", "₹12,500", "₹15,800", "₹19,600"],
            ["40 years", "₹17,200", "₹22,400", "₹28,900"],
            ["45 years", "₹24,800", "₹33,600", "N/A"],
        ], col_widths=[4*cm, 5*cm, 5*cm, 4*cm]),
        Spacer(1, 0.3*cm),
        Paragraph("Available Riders (Add-ons)", SECTION),
        tbl([
            ["Rider", "Benefit", "Additional Premium"],
            ["Critical Illness Rider", "Lump sum on diagnosis of 34 critical illnesses", "₹2,500–₹8,000/yr"],
            ["Accidental Death Benefit", "Additional sum assured on accidental death", "₹500–₹2,000/yr"],
            ["Waiver of Premium", "Future premiums waived on disability/CI diagnosis", "₹800–₹2,500/yr"],
            ["Income Benefit Rider", "Monthly income to family for 10 years", "₹1,200–₹3,500/yr"],
        ], col_widths=[5*cm, 8*cm, 5*cm]),
        Spacer(1, 0.3*cm),
        Paragraph("Tax Benefits", SECTION),
        Paragraph(
            "• Section 80C: Premiums paid are eligible for deduction up to ₹1,50,000 per year.\n"
            "• Section 10(10D): Death benefit received by nominees is completely tax-free.\n"
            "• Critical Illness Rider premium qualifies under Section 80D (up to ₹25,000 for self/family).", BODY),
        Paragraph("Who Should Buy", SECTION),
        Paragraph(
            "• Salaried individuals with dependents (spouse, children, parents) who rely on the income.\n"
            "• Self-employed or business owners with outstanding loans or liabilities.\n"
            "• Young earners (age 25–35): premium is lowest and cover runs for decades.\n"
            "• Recommended sum assured: 10–15× annual income to replace lost earnings.\n"
            "• For a person earning ₹8 lakh/year, minimum recommended cover is ₹80 lakh–₹1.2 crore.", BODY),
        Paragraph("Key Exclusions", SECTION),
        Paragraph(
            "• Suicide within 12 months of policy inception or revival (nominees receive 80% of premiums paid).\n"
            "• Death due to participation in hazardous activities without prior disclosure.\n"
            "• Death due to war, civil unrest, or nuclear/biological events.\n"
            "• Fraudulent misrepresentation of health or age at policy inception.", BODY),
        Paragraph("Claim Settlement", SECTION),
        Paragraph(
            "HDFC Life has a Claim Settlement Ratio (CSR) of 99.5% (FY 2023–24). Claims are settled within "
            "30 days of receiving complete documentation. For accidental death, a spot settlement of ₹5 lakh "
            "is available within 24 hours. Nominee can file claim online at hdfclife.com or via helpline 18602676006.", BODY),
        Spacer(1, 0.3*cm),
        Paragraph("IRDAI Reg. No. 101 | HDFC Life Insurance Company Limited, Lodha Excelus, 13th Floor, Apollo Mills Compound, N.M. Joshi Marg, Mahalakshmi, Mumbai 400011.", SMALL),
    ]

doc("term_life_hdfc_click2protect.pdf", "Term Life", term_life)


# ─────────────────────────────────────────────────────────────────────────────
# 2. HEALTH INSURANCE — FAMILY FLOATER
# ─────────────────────────────────────────────────────────────────────────────
def health_family(story):
    story += [
        Paragraph("Niva Bupa Health Insurance Co. Ltd.", BRAND),
        Paragraph("Reassure 2.0 — Family Floater Health Insurance Plan", TITLE),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1a3c6e")),
        Spacer(1, 0.3*cm),
        Paragraph("Product Overview", SECTION),
        Paragraph(
            "Niva Bupa Reassure 2.0 is a comprehensive family floater health insurance plan covering "
            "hospitalisation, day care, OPD, and wellness benefits. IRDAI UIN: NBUHLIP23096V012223. "
            "Available for individuals and families with sum insured options from ₹3 lakh to ₹1 crore.", BODY),
        Paragraph("Coverage Summary", SECTION),
        tbl([
            ["Benefit", "Coverage", "Sub-limit / Remarks"],
            ["In-patient Hospitalisation", "Up to Sum Insured", "Min. 24 hrs admission"],
            ["Pre-Hospitalisation", "60 days", "Related medical expenses"],
            ["Post-Hospitalisation", "180 days", "Related medical expenses"],
            ["Day Care Procedures", "All day care listed", "No 24-hr admission needed"],
            ["Room Rent", "Single Private AC Room", "No room rent capping on ₹10L+ plans"],
            ["ICU Charges", "Covered", "No sub-limit on ₹10L+ plans"],
            ["Organ Donor Expenses", "Up to ₹1,50,000", "Harvesting and transplant costs"],
            ["AYUSH Treatment", "Up to Sum Insured", "Recognised AYUSH hospitals"],
            ["Restoration of Sum Insured", "Unlimited times", "For same or unrelated illness"],
            ["No Claim Bonus", "10% per claim-free year", "Max 100% of base sum insured"],
            ["Annual Health Check-up", "Covered for all members", "From day 1, no waiting period"],
            ["OPD Consultations", "Up to ₹20,000/year", "Includes specialist and GP visits"],
            ["Mental Wellness", "Up to ₹15,000/year", "Teleconsultation and in-person"],
            ["Home Care Treatment", "Up to ₹50,000/year", "Doctor-prescribed home nursing"],
        ], col_widths=[6*cm, 5*cm, 7*cm]),
        Spacer(1, 0.3*cm),
        Paragraph("Indicative Annual Premiums (Family of 4: Self + Spouse + 2 Children)", SECTION),
        tbl([
            ["Sum Insured", "Age 28–32 (Tier 1)", "Age 35–40 (Tier 1)", "Age 40–45 (Tier 1)"],
            ["₹5 Lakhs",   "₹14,200",            "₹19,800",            "₹27,500"],
            ["₹10 Lakhs",  "₹19,600",            "₹27,400",            "₹38,200"],
            ["₹20 Lakhs",  "₹28,500",            "₹39,800",            "₹55,000"],
            ["₹50 Lakhs",  "₹48,000",            "₹67,500",            "₹94,000"],
        ], col_widths=[4*cm, 4.5*cm, 4.5*cm, 5*cm]),
        Spacer(1, 0.3*cm),
        Paragraph("Waiting Periods", SECTION),
        tbl([
            ["Condition", "Waiting Period"],
            ["Initial waiting period (all illnesses)", "30 days from policy inception"],
            ["Pre-existing diseases (PED)", "36 months (reduced to 12 months with PED waiver add-on)"],
            ["Specific listed diseases (cataract, hernia, etc.)", "24 months"],
            ["Maternity benefit (optional add-on)", "24 months from policy inception"],
            ["Accidents", "No waiting period"],
        ], col_widths=[9*cm, 9*cm]),
        Spacer(1, 0.3*cm),
        Paragraph("Key Exclusions", SECTION),
        Paragraph(
            "• Cosmetic or aesthetic procedures not caused by accident or disease.\n"
            "• Dental treatment unless due to accident requiring hospitalisation.\n"
            "• Obesity treatment and weight-loss surgery.\n"
            "• Experimental or unproven treatments.\n"
            "• Self-inflicted injury, suicide attempt, drug or alcohol abuse.\n"
            "• War, nuclear, biological, or chemical events.", BODY),
        Paragraph("Tax Benefits", SECTION),
        Paragraph(
            "• Section 80D: Premium paid for self, spouse, and children qualifies for deduction up to "
            "₹25,000/year (₹50,000 if any insured member is a senior citizen).\n"
            "• Additional deduction of up to ₹25,000 (or ₹50,000 for senior citizens) for parents' health insurance.\n"
            "• Preventive health check-up expenses up to ₹5,000 are included within the 80D limit.", BODY),
        Paragraph("Who Should Buy", SECTION),
        Paragraph(
            "• Any family without employer-provided group health cover.\n"
            "• Families with pre-existing conditions: opt for PED waiver add-on.\n"
            "• Recommended minimum: ₹10 lakh floater for a family of 4 in Tier 1 city.\n"
            "• Young families (25–35): lock in at low premium and build NCB over years.\n"
            "• Self-employed individuals whose employer does not provide group cover.", BODY),
        Paragraph("Network & Claims", SECTION),
        Paragraph(
            "9,500+ cashless network hospitals across India. Cashless approval within 30 minutes for planned "
            "hospitalisation. Reimbursement claims settled within 7 working days. "
            "24×7 helpline: 1800-200-7878 | claims@nivabupa.com", BODY),
        Spacer(1, 0.3*cm),
        Paragraph("IRDAI Reg. No. 145 | Niva Bupa Health Insurance Company Limited, D-5, Uppal's Southend, Sector 49, Gurugram 122018.", SMALL),
    ]

doc("health_niva_bupa_reassure.pdf", "Family Health", health_family)


# ─────────────────────────────────────────────────────────────────────────────
# 3. ULIP — UNIT LINKED INSURANCE PLAN
# ─────────────────────────────────────────────────────────────────────────────
def ulip(story):
    story += [
        Paragraph("HDFC Life Insurance Co. Ltd.", BRAND),
        Paragraph("Click 2 Wealth — Unit Linked Insurance Plan (ULIP)", TITLE),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1a3c6e")),
        Spacer(1, 0.3*cm),
        Paragraph("Product Overview", SECTION),
        Paragraph(
            "HDFC Life Click 2 Wealth is a unit-linked, non-participating life insurance plan that combines "
            "market-linked wealth creation with life insurance protection. IRDAI UIN: 101L133V03. "
            "Suitable for long-term financial goals such as retirement planning, children's education, and "
            "wealth accumulation over 10–30 years. Minimum lock-in period is 5 years as per IRDAI regulations.", BODY),
        Paragraph("Key Features", SECTION),
        tbl([
            ["Feature", "Details"],
            ["Policy Term", "10 to 30 years"],
            ["Premium Payment Term", "Regular Pay (equal to policy term) / Limited Pay (5, 7, 10 years)"],
            ["Minimum Annual Premium", "₹12,000 (monthly ₹1,000 via SIP)"],
            ["Sum Assured", "Higher of 10× annualised premium or 0.5× total premiums (for age <45)"],
            ["Lock-in Period", "5 years (no partial withdrawal before 5 years)"],
            ["Fund Switching", "Unlimited free switches between funds per year"],
            ["Partial Withdrawal", "Allowed after 5 years — up to 20% of fund value per year"],
        ], col_widths=[7*cm, 11*cm]),
        Spacer(1, 0.3*cm),
        Paragraph("Available Fund Options", SECTION),
        tbl([
            ["Fund Name", "Asset Allocation", "Risk Profile", "5-Year CAGR (Indicative)"],
            ["Equity Growth Fund",     "80–100% Equity",           "High",   "14–18%"],
            ["Balanced Advantage Fund","50–70% Equity, rest Debt",  "Medium", "10–13%"],
            ["Debt Plus Fund",         "80–100% Debt & Bonds",      "Low",    "7–9%"],
            ["Liquid Fund",            "100% Money Market",          "Very Low","5–6%"],
            ["Multi-Cap Fund",         "Large + Mid + Small Cap",   "High",   "15–20%"],
        ], col_widths=[5*cm, 5*cm, 3*cm, 5*cm]),
        Spacer(1, 0.3*cm),
        Paragraph("Charges", SECTION),
        tbl([
            ["Charge Type", "Amount / Rate"],
            ["Premium Allocation Charge", "NIL (0%) — 100% of premium invested"],
            ["Policy Administration Charge", "₹500/month (₹6,000/year), level throughout"],
            ["Fund Management Charge (FMC)", "1.35% p.a. for equity funds; 0.80% p.a. for debt funds"],
            ["Mortality Charge", "Age-based, deducted monthly from fund (transparent)"],
            ["Partial Withdrawal Charge", "NIL for first 4 withdrawals; ₹100 per withdrawal thereafter"],
            ["Surrender Charge", "NIL after 5-year lock-in period"],
        ], col_widths=[7*cm, 11*cm]),
        Spacer(1, 0.3*cm),
        Paragraph("Death & Maturity Benefits", SECTION),
        Paragraph(
            "• Death Benefit: Higher of (Sum Assured minus partial withdrawals) OR (Fund Value at NAV) "
            "OR (105% of total premiums paid). Paid to nominee, completely tax-free under Section 10(10D).\n"
            "• Maturity Benefit: Fund Value at prevailing NAV paid as lump sum. Tax-free under Section 10(10D) "
            "provided annual premium does not exceed 10% of sum assured.\n"
            "• Loyalty Additions: Extra units added to fund at end of years 5, 10, and every 5 years thereafter.", BODY),
        Paragraph("Tax Benefits", SECTION),
        Paragraph(
            "• Section 80C: Annual premiums up to ₹1,50,000 are eligible for deduction.\n"
            "• Section 10(10D): Death benefit and maturity proceeds are fully tax-exempt provided the annual "
            "premium is ≤10% of sum assured (for policies issued after 1 April 2012).\n"
            "• Note: Budget 2023 — If aggregate ULIP premium exceeds ₹2.5 lakh/year, maturity gains are "
            "taxable as LTCG at 10% (similar to equity mutual funds). Death benefit remains tax-free.", BODY),
        Paragraph("Who Should Buy", SECTION),
        Paragraph(
            "• Long-term investors (10+ year horizon) who want market-linked growth plus life cover.\n"
            "• Individuals planning for retirement corpus — start a ULIP at age 30 for 25-year horizon.\n"
            "• Parents planning for child's higher education (15–20 years away).\n"
            "• Minimum recommended investment: ₹3,000–₹5,000/month for meaningful wealth creation.\n"
            "• NOT recommended for short-term goals (under 7 years) due to charges and market volatility.", BODY),
        Paragraph("Comparison: ULIP vs. Term + Mutual Fund (Buy Term, Invest the Rest)", SECTION),
        Paragraph(
            "• ULIPs simplify investing — one product for both insurance and investment.\n"
            "• Post-2019 ULIP charges are highly competitive with mutual fund expense ratios.\n"
            "• However, for disciplined investors, Term + Direct Mutual Fund may offer higher net returns.\n"
            "• ULIPs have an advantage in estate planning — death benefit bypasses succession laws.", BODY),
        Spacer(1, 0.3*cm),
        Paragraph("IRDAI Reg. No. 101 | Market-linked products do not offer guaranteed returns. Past performance is not indicative of future results.", SMALL),
    ]

doc("ulip_hdfc_click2wealth.pdf", "ULIP", ulip)


# ─────────────────────────────────────────────────────────────────────────────
# 4. PERSONAL ACCIDENT INSURANCE
# ─────────────────────────────────────────────────────────────────────────────
def personal_accident(story):
    story += [
        Paragraph("Bajaj Allianz General Insurance Co. Ltd.", BRAND),
        Paragraph("Secura Personal Guard — Personal Accident Insurance", TITLE),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1a3c6e")),
        Spacer(1, 0.3*cm),
        Paragraph("Product Overview", SECTION),
        Paragraph(
            "Bajaj Allianz Secura Personal Guard provides comprehensive personal accident coverage against "
            "accidental death, permanent/temporary disability, and hospitalisation due to accidents. "
            "IRDAI UIN: IRDA/NL-HLT/BAGI/P-H/V.I/355/13-14. This is a pure general insurance product — "
            "NOT a life insurance product. Cover extends globally 24×7.", BODY),
        Paragraph("Coverage Benefits", SECTION),
        tbl([
            ["Benefit", "Sum Insured / Benefit", "Remarks"],
            ["Accidental Death (AD)", "100% of Capital Sum Insured (CSI)", "Paid to nominee"],
            ["Permanent Total Disability (PTD)", "100% of CSI", "Both hands/legs/eyes/combination"],
            ["Permanent Partial Disability (PPD)", "10%–75% of CSI", "As per disability table"],
            ["Temporary Total Disability (TTD)", "1% of CSI per week", "Max 100 weeks, after 7-day excess"],
            ["Fracture Care", "Up to ₹50,000", "Without hospitalisation"],
            ["Hospitalisation (accident-caused)", "Up to ₹1,00,000", "Over and above health insurance"],
            ["Ambulance Charges", "Up to ₹5,000 per event", "For emergency transport"],
            ["Children Education Benefit", "10% of CSI (max ₹5 lakh)", "On AD or PTD, for 2 children"],
            ["Loan Protection", "Up to ₹10 lakh outstanding loan", "On AD or PTD"],
        ], col_widths=[6*cm, 5*cm, 7*cm]),
        Spacer(1, 0.3*cm),
        Paragraph("Indicative Annual Premiums by Occupation Class", SECTION),
        tbl([
            ["Occupation Class", "Examples", "CSI ₹25L", "CSI ₹50L", "CSI ₹1Cr"],
            ["Class 1 — Low Risk", "Desk jobs, teachers, bankers", "₹1,800", "₹3,400", "₹6,500"],
            ["Class 2 — Medium Risk", "Sales, drivers, supervisors", "₹2,800", "₹5,200", "₹9,800"],
            ["Class 3 — High Risk", "Builders, machine operators", "₹4,500", "₹8,500", "₹16,000"],
            ["Class 4 — Very High Risk", "Miners, explosives handlers", "₹7,000", "₹13,000", "₹24,000"],
        ], col_widths=[4*cm, 5.5*cm, 3*cm, 3*cm, 2.5*cm]),
        Spacer(1, 0.3*cm),
        Paragraph("Key Exclusions", SECTION),
        Paragraph(
            "• Accidents under influence of alcohol, narcotics, or drugs.\n"
            "• Self-inflicted injuries, suicide, or attempted suicide.\n"
            "• Adventure/hazardous sports (mountaineering, skydiving) unless specifically endorsed.\n"
            "• War, invasion, civil commotion, nuclear/biological events.\n"
            "• Pre-existing physical defects or infirmities.\n"
            "• Pregnancy, childbirth, or related complications.\n"
            "• Accidents during criminal or unlawful acts.", BODY),
        Paragraph("Tax Benefits", SECTION),
        Paragraph(
            "• Personal accident insurance premiums do NOT qualify under Section 80C or 80D.\n"
            "• However, the policy is an essential financial planning tool — the accident benefit "
            "supplements health insurance (which only covers treatment costs, not income loss).\n"
            "• TTD benefit replaces lost income during recovery, making it critical for self-employed and "
            "business owners who have no employer sick-pay provision.", BODY),
        Paragraph("Who Should Buy", SECTION),
        Paragraph(
            "• Self-employed individuals and business owners — no employer income protection during disability.\n"
            "• Salaried employees whose EPF/ESIC does not fully cover accidental disability.\n"
            "• Two-wheeler or four-wheeler drivers with high daily road exposure.\n"
            "• Construction, manufacturing, or field-work professionals (Class 2–3).\n"
            "• Young earners with home loans — CSI should cover outstanding loan amount.\n"
            "• Recommended CSI: minimum 5× annual income to cover disability-related income loss.", BODY),
        Spacer(1, 0.3*cm),
        Paragraph("IRDAI Reg. No. 113 | Bajaj Allianz General Insurance Company Limited, GE Plaza, Airport Road, Yerwada, Pune 411006.", SMALL),
    ]

doc("personal_accident_bajaj_secura.pdf", "Personal Accident", personal_accident)


# ─────────────────────────────────────────────────────────────────────────────
# 5. CRITICAL ILLNESS INSURANCE
# ─────────────────────────────────────────────────────────────────────────────
def critical_illness(story):
    story += [
        Paragraph("Star Health and Allied Insurance Co. Ltd.", BRAND),
        Paragraph("Criticare Plus — Critical Illness Insurance Plan", TITLE),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1a3c6e")),
        Spacer(1, 0.3*cm),
        Paragraph("Product Overview", SECTION),
        Paragraph(
            "Star Health Criticare Plus is a standalone critical illness (CI) indemnity-cum-benefit plan that "
            "provides a lump-sum payout on first diagnosis of any of the 37 listed critical illnesses. "
            "IRDAI UIN: SHAHLIP22048V012122. The lump sum can be used for treatment costs, income replacement "
            "during recovery, or loan repayment — with no restrictions on usage.", BODY),
        Paragraph("37 Covered Critical Illnesses", SECTION),
        tbl([
            ["Category", "Covered Conditions"],
            ["Cardiac", "Heart Attack (Myocardial Infarction), Coronary Artery Bypass Surgery, Heart Valve Replacement, Cardiac Arrest"],
            ["Neurological", "Stroke with permanent neurological deficit, Coma, Paralysis/Paraplegia, Major Head Trauma, Alzheimer's Disease, Parkinson's Disease"],
            ["Cancer", "Cancer of Specified Severity (malignant tumours), Benign Brain Tumour"],
            ["Organ Related", "End Stage Kidney (Renal) Failure, Major Organ Transplant (heart, lung, liver, kidney, pancreas), End Stage Liver Disease, End Stage Lung Disease"],
            ["Surgical", "Aorta Graft Surgery, Coronary Artery Disease requiring Angioplasty, Surgery of Aorta"],
            ["Other", "Loss of Speech, Blindness, Deafness, Burns (severe third-degree), Muscular Dystrophy, Multiple Sclerosis, Motor Neurone Disease, Aplastic Anaemia, Systemic Lupus Erythematosus (SLE) with Lupus Nephritis"],
        ], col_widths=[4*cm, 14*cm]),
        Spacer(1, 0.3*cm),
        Paragraph("Plan Options and Sum Insured", SECTION),
        tbl([
            ["Plan Variant", "Sum Insured Options", "Key Differentiator"],
            ["Essential Plan", "₹3L, ₹5L, ₹10L", "Core 37 CI coverage, 90-day survival period"],
            ["Advantage Plan", "₹10L, ₹15L, ₹25L", "30-day survival period, income replacement add-on"],
            ["Elite Plan", "₹25L, ₹50L, ₹1Cr", "Second medical opinion, rehabilitation benefit"],
        ], col_widths=[4*cm, 6*cm, 8*cm]),
        Spacer(1, 0.3*cm),
        Paragraph("Indicative Annual Premiums (Individual, Non-Smoker)", SECTION),
        tbl([
            ["Age", "₹10 Lakhs SI", "₹25 Lakhs SI", "₹50 Lakhs SI"],
            ["25 years", "₹3,800",  "₹8,500",  "₹16,000"],
            ["30 years", "₹4,500",  "₹10,200", "₹19,500"],
            ["35 years", "₹6,200",  "₹14,000", "₹26,800"],
            ["40 years", "₹9,500",  "₹21,500", "₹41,000"],
            ["45 years", "₹14,800", "₹33,500", "₹64,000"],
        ], col_widths=[3.5*cm, 4.5*cm, 4.5*cm, 4.5*cm]),
        Spacer(1, 0.3*cm),
        Paragraph("Survival Period & Waiting Period", SECTION),
        tbl([
            ["Condition", "Period"],
            ["Initial Waiting Period (all CI)", "90 days from policy inception"],
            ["Survival Period (Essential Plan)", "90 days after CI diagnosis (must survive to claim)"],
            ["Survival Period (Advantage/Elite)", "30 days after CI diagnosis"],
            ["Pre-existing Disease Waiting Period", "48 months"],
            ["Specific CI Waiting Period (Cancer, Heart)", "90 days from policy inception"],
        ], col_widths=[9*cm, 9*cm]),
        Spacer(1, 0.3*cm),
        Paragraph("Why Critical Illness Cover is Essential", SECTION),
        Paragraph(
            "• ICMR data: 1 in 4 Indians will suffer a serious illness before age 70.\n"
            "• Cancer treatment in India: ₹5 lakh–₹25 lakh for surgery + chemotherapy + radiation.\n"
            "• Cardiac surgery (bypass): ₹3 lakh–₹8 lakh in a private hospital.\n"
            "• Health insurance covers hospitalisation — CI cover pays the income lost during 6–12 months of recovery.\n"
            "• With a ₹25 lakh CI payout: ₹5–8L for treatment, ₹10L to repay loans, rest as income buffer.\n"
            "• Especially important for: diabetics, hypertensives, those with family history of heart disease or cancer.", BODY),
        Paragraph("Tax Benefits", SECTION),
        Paragraph(
            "• Section 80D: Premiums paid for critical illness plan qualify for deduction.\n"
            "  — Self, spouse, children: up to ₹25,000/year\n"
            "  — Parents (non-senior citizen): additional ₹25,000/year\n"
            "  — Parents (senior citizen, age 60+): additional ₹50,000/year\n"
            "• Maximum total 80D deduction if all members covered: ₹75,000–₹1,00,000/year.", BODY),
        Paragraph("Key Exclusions", SECTION),
        Paragraph(
            "• Pre-existing diseases (unless 48-month waiting period completed).\n"
            "• CIs diagnosed within first 90 days of policy inception.\n"
            "• Self-inflicted injury, suicide attempt.\n"
            "• HIV/AIDS-related critical illness.\n"
            "• CIs arising from alcohol, narcotics, or substance abuse.\n"
            "• Congenital conditions present at birth.", BODY),
        Spacer(1, 0.3*cm),
        Paragraph("IRDAI Reg. No. 129 | Star Health and Allied Insurance Company Limited, No.1, New Tank Street, Valluvar Kottam High Road, Nungambakkam, Chennai 600034.", SMALL),
    ]

doc("critical_illness_star_health.pdf", "Critical Illness", critical_illness)


print("\nAll 5 product PDFs generated successfully in data/policies/")
print("\nFiles created:")
for f in sorted(OUT_DIR.glob("*.pdf")):
    size_kb = f.stat().st_size // 1024
    print(f"  {f.name} ({size_kb} KB)")
