/**
 * Seeds a test advisor (if none exists), one client with a real email address,
 * and one policy due in 15 days so all Phase 1 UI flows have data to work with.
 * IDs are written to process.env so spec files can read them.
 */

const API = "http://localhost:8000";

async function post(path: string, body: object) {
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`POST ${path} failed (${res.status}): ${text}`);
  }
  return res.json();
}

async function get(path: string) {
  const res = await fetch(`${API}${path}`);
  if (!res.ok) throw new Error(`GET ${path} failed (${res.status})`);
  return res.json();
}

function dueDateIn(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().split("T")[0];
}

export default async function globalSetup() {
  // Use the first existing advisor, or create one
  const advisors: any[] = await get("/api/v1/advisors");
  let advisorId: string;

  if (advisors.length > 0) {
    advisorId = advisors[0].id;
    console.log(`[setup] Using existing advisor: ${advisors[0].name} (${advisorId})`);
  } else {
    const advisor = await post("/api/v1/advisors", {
      name: "Amit Singh",
      email: "amit.singh@insureai.com",
      phone: "9876543210",
      license_no: "IRDAI-001",
    });
    advisorId = advisor.id;
    console.log(`[setup] Created advisor: ${advisor.name} (${advisorId})`);
  }

  // Create a test client whose email is your real inbox — the email test will
  // send a reminder to this address via SendGrid
  const client = await post("/api/v1/leads", {
    advisor_id: advisorId,
    name: "Rajesh Kumar (Test)",
    email: "gaur.mukeshkumar@gmail.com",
    phone: "9988776655",
    age: 38,
    income: 1500000,
    family_size: 3,
    risk_appetite: "medium",
    goals: "retirement planning and child education",
  });
  console.log(`[setup] Created client: ${client.name} (${client.id})`);

  // Create a policy due in 15 days so it shows in the Renewals page
  const policy = await post("/api/v1/policies", {
    client_id: client.id,
    insurer_name: "LIC",
    product_name: "Tech Term Plan",
    policy_no: `UI-TEST-${Date.now()}`,
    policy_type: "term",
    premium_amount: 9500,
    sum_assured: 10000000,
    next_due_date: dueDateIn(15),
  });
  console.log(`[setup] Created policy: ${policy.policy_no} (${policy.id})`);

  // Expose IDs for spec files via env vars (available in the same process)
  process.env.E2E_ADVISOR_ID = advisorId;
  process.env.E2E_CLIENT_ID = client.id;
  process.env.E2E_POLICY_ID = policy.id;
  process.env.E2E_CLIENT_NAME = client.name;
}
