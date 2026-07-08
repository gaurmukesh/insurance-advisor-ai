import axios from "axios";

const TOKEN_KEY = "access_token";

export const getToken = () =>
  typeof window === "undefined" ? null : localStorage.getItem(TOKEN_KEY);

const setToken = (token: string) => localStorage.setItem(TOKEN_KEY, token);

export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && typeof window !== "undefined") {
      clearToken();
      if (window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

// --- Types ---
export interface Client {
  id: string;
  advisor_id: string;
  name: string;
  email?: string;
  phone?: string;
  age?: number;
  income?: number;
  family_size?: number;
  risk_appetite?: string;
  goals?: string;
  status: string;
  notes?: string;
  existing_coverage?: string;
  liabilities_emi?: number;
  employment_type?: string;
  health_conditions?: string;
  dependents_detail?: string;
  city_tier?: string;
  created_at: string;
}

export interface Policy {
  policy_id: string;
  policy_no: string;
  product_name: string;
  insurer_name: string;
  premium_amount: number;
  next_due_date: string;
  client_id: string;
  client_name: string;
  client_email?: string;
  client_phone?: string;
}

export interface EmailLog {
  id: string;
  client_id: string;
  policy_id?: string;
  subject: string;
  body: string;
  status: string;
  sent_at: string;
}

export interface WhatsAppLog {
  id: string;
  client_id: string;
  policy_id?: string;
  phone: string;
  template_name: string;
  message_body: string;
  wa_message_id?: string;
  status: string;
  sent_at: string;
}

// --- Advisor ---
export interface Advisor {
  id: string;
  name: string;
  email: string;
  phone: string;
  license_no?: string;
}

// --- Auth ---
export const login = (email: string, password: string) =>
  api
    .post<{ access_token: string; advisor: Advisor }>("/api/v1/auth/login", { email, password })
    .then((r) => {
      setToken(r.data.access_token);
      return r.data.advisor;
    });

export const getMe = () => api.get<Advisor>("/api/v1/auth/me").then((r) => r.data);

export const logout = () => {
  clearToken();
  if (typeof window !== "undefined") window.location.href = "/login";
};

// --- Leads ---
export const getLeads = (status?: string) =>
  api.get<Client[]>("/api/v1/leads", { params: { status } }).then((r) => r.data);

export const createLead = (data: Partial<Client>) =>
  api.post<Client>("/api/v1/leads", data).then((r) => r.data);

export const updateLead = (id: string, data: Partial<Client>) =>
  api.put<Client>(`/api/v1/leads/${id}`, data).then((r) => r.data);

export const getLead = (id: string) =>
  api.get<Client>(`/api/v1/leads/${id}`).then((r) => r.data);

// --- Renewals ---
export const getUpcomingRenewals = (days = 30) =>
  api.get<Policy[]>("/api/v1/renewals/upcoming", { params: { days } }).then((r) => r.data);

// --- Recommendations ---
export const analyzeClient = (client_id: string, existing_policies?: string) =>
  api.post("/api/v1/analyze-client", { client_id, existing_policies }).then((r) => r.data);

// Streams the needs-analysis text token-by-token via SSE instead of waiting for
// the full ~15s response. `onToken` is called with each incremental chunk.
export const streamAnalyzeLead = async (
  client_id: string,
  existingPolicies: string | undefined,
  onToken: (token: string) => void
) => {
  const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/agent/analyze-lead/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${getToken()}`,
    },
    body: JSON.stringify({ client_id }),
  });

  if (!response.ok || !response.body) {
    throw new Error(`Analyze stream failed: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let done: { gaps: unknown[]; interaction_id: string } | null = null;

  while (true) {
    const { done: streamDone, value } = await reader.read();
    if (streamDone) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const rawEvent = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);

      let eventType = "message";
      let data = "";
      for (const line of rawEvent.split("\n")) {
        if (line.startsWith("event: ")) eventType = line.slice(7);
        else if (line.startsWith("data: ")) data = line.slice(6);
      }

      if (eventType === "done") {
        done = JSON.parse(data);
      } else if (data) {
        onToken(JSON.parse(data));
      }

      boundary = buffer.indexOf("\n\n");
    }
  }

  return done;
};

export interface ProductRecommendation {
  rank: number;
  product_name: string;
  insurer: string;
  type: string;
  premium_per_month: number;
  sum_assured: string;
  key_benefit: string;
  why_suits: string;
  tax_benefit: string;
  pitch_first: boolean;
}

export const recommendProducts = (client_id: string, need_analysis: string) =>
  api.post<{ client_id: string; client_name: string; recommendations: ProductRecommendation[] }>(
    "/api/v1/recommend-products", { client_id, need_analysis }
  ).then((r) => r.data);

// --- Emails ---
export const draftReminderEmail = (policy_id: string, advisor_name: string) =>
  api.post("/api/v1/draft-email/reminder", { policy_id, advisor_name }).then((r) => r.data);

export const sendReminderEmail = (policy_id: string, advisor_name: string) =>
  api.post("/api/v1/send-email/reminder", { policy_id, advisor_name }).then((r) => r.data);

// --- WhatsApp ---
export const sendWhatsAppReminder = (policy_id: string) =>
  api.post("/api/v1/send-whatsapp/reminder", { policy_id }).then((r) => r.data);

// --- Email Drafts ---
export interface EmailDraft {
  id: string;
  client_name: string;
  client_email: string;
  policy_id?: string;
  subject: string;
  body: string;
  edited_body?: string;
  status: string;
  sent_at: string;
}

export const getEmailDrafts = () =>
  api.get<EmailDraft[]>("/api/v1/email-drafts").then((r) => r.data);

export const approveEmailDraft = (id: string, edited_body?: string) =>
  api.post(`/api/v1/email-drafts/${id}/approve`, { edited_body: edited_body ?? null }).then((r) => r.data);

export const rejectEmailDraft = (id: string) =>
  api.post(`/api/v1/email-drafts/${id}/reject`).then((r) => r.data);

// --- Pitch & Objection ---
export const getCommonObjections = () =>
  api.get<{ objections: string[] }>("/api/v1/pitch/common-objections").then((r) => r.data.objections);

export const generatePitch = (client_id: string, existing_policies?: string) =>
  api.post<{ pitch: string }>("/api/v1/generate-pitch", { client_id, existing_policies }).then((r) => r.data);

export interface ObjectionResponse {
  acknowledge: string;
  reframe: string;
  strong_reason: string;
  client_specific_impact: string;
  stat_or_fact: string;
  closing_line: string;
}

export const handleObjection = (client_id: string, objection: string, existing_policies?: string) =>
  api.post<{ objection: string; response: ObjectionResponse }>("/api/v1/handle-objection", { client_id, objection, existing_policies }).then((r) => r.data);

// --- Metrics ---
export interface Metrics {
  leads: {
    total: number;
    by_status: { new: number; contacted: number; interested: number; converted: number; lost: number };
    conversion_rate: number;
  };
  policies: {
    total: number;
    total_premium: number;
    due_in_7_days: number;
    due_in_30_days: number;
  };
  emails: { total: number; by_status: Record<string, number> };
  whatsapp: { total: number; by_status: Record<string, number> };
  recent_activity: Array<{
    type: "email" | "whatsapp";
    client: string;
    detail: string;
    status: string;
    time: string | null;
  }>;
}

export const getMetrics = () => api.get<Metrics>("/api/v1/metrics").then((r) => r.data);

// --- Document Assistant ---
export const summarizeDocument = (file: File) => {
  const form = new FormData();
  form.append("file", file);
  return axios
    .post<{ filename: string; summary: string }>(
      `${process.env.NEXT_PUBLIC_API_URL}/api/v1/document-summary`,
      form,
      { headers: { "Content-Type": "multipart/form-data" } }
    )
    .then((r) => r.data);
};

export const compareDocuments = (fileA: File, fileB: File) => {
  const form = new FormData();
  form.append("file_a", fileA);
  form.append("file_b", fileB);
  return axios
    .post<{ file_a: string; file_b: string; comparison: string }>(
      `${process.env.NEXT_PUBLIC_API_URL}/api/v1/document-compare`,
      form,
      { headers: { "Content-Type": "multipart/form-data" } }
    )
    .then((r) => r.data);
};

export default api;
