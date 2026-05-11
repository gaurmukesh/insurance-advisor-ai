import axios from "axios";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL,
  headers: { "Content-Type": "application/json" },
});

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

export const getAdvisors = () =>
  api.get<Advisor[]>("/api/v1/advisors").then((r) => r.data);

// --- Leads ---
export const getLeads = (advisor_id: string, status?: string) =>
  api.get<Client[]>("/api/v1/leads", { params: { advisor_id, status } }).then((r) => r.data);

export const createLead = (data: Partial<Client>) =>
  api.post<Client>("/api/v1/leads", data).then((r) => r.data);

export const updateLead = (id: string, data: Partial<Client>) =>
  api.put<Client>(`/api/v1/leads/${id}`, data).then((r) => r.data);

export const getLead = (id: string) =>
  api.get<Client>(`/api/v1/leads/${id}`).then((r) => r.data);

// --- Renewals ---
export const getUpcomingRenewals = (advisor_id: string, days = 30) =>
  api.get<Policy[]>("/api/v1/renewals/upcoming", { params: { advisor_id, days } }).then((r) => r.data);

// --- Recommendations ---
export const analyzeClient = (client_id: string, existing_policies?: string) =>
  api.post("/api/v1/analyze-client", { client_id, existing_policies }).then((r) => r.data);

export const recommendProducts = (client_id: string, need_analysis: string) =>
  api.post("/api/v1/recommend-products", { client_id, need_analysis }).then((r) => r.data);

// --- Emails ---
export const draftReminderEmail = (policy_id: string, advisor_name: string) =>
  api.post("/api/v1/draft-email/reminder", { policy_id, advisor_name }).then((r) => r.data);

export const sendReminderEmail = (policy_id: string, advisor_name: string) =>
  api.post("/api/v1/send-email/reminder", { policy_id, advisor_name }).then((r) => r.data);

// --- WhatsApp ---
export const sendWhatsAppReminder = (policy_id: string) =>
  api.post("/api/v1/send-whatsapp/reminder", { policy_id }).then((r) => r.data);

export default api;
