"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getLeads, createLead, updateLead, Client } from "@/lib/api";
import { useAdvisor } from "@/lib/AdvisorContext";
import Link from "next/link";
import { Plus, ChevronRight } from "lucide-react";

const STATUS_OPTIONS = ["new", "contacted", "interested", "converted", "lost"];

const statusColor: Record<string, string> = {
  new: "bg-yellow-100 text-yellow-700",
  contacted: "bg-blue-100 text-blue-700",
  interested: "bg-purple-100 text-purple-700",
  converted: "bg-green-100 text-green-700",
  lost: "bg-red-100 text-red-700",
};

function AddLeadModal({ onClose, advisorId }: { onClose: () => void; advisorId: string }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({
    name: "", email: "", phone: "", age: "", income: "",
    family_size: "", risk_appetite: "medium", goals: "",
    existing_coverage: "", liabilities_emi: "",
    employment_type: "salaried", health_conditions: "",
    dependents_detail: "", city_tier: "tier1",
  });

  const mutation = useMutation({
    mutationFn: (data: Partial<Client>) => createLead(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["leads"] }); onClose(); },
  });

  const handle = (e: React.FormEvent) => {
    e.preventDefault();
    mutation.mutate({
      advisor_id: advisorId,
      ...form,
      age: form.age ? Number(form.age) : undefined,
      income: form.income ? Number(form.income) : undefined,
      family_size: form.family_size ? Number(form.family_size) : undefined,
      liabilities_emi: form.liabilities_emi ? Number(form.liabilities_emi) : undefined,
    });
  };

  const inputCls = "w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500";

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl p-6 w-full max-w-lg shadow-xl max-h-[90vh] flex flex-col">
        <h2 className="text-base font-semibold text-gray-800 mb-4 shrink-0">Add New Lead</h2>
        <form onSubmit={handle} className="space-y-3 overflow-y-auto pr-1">
          {[
            { label: "Full Name *", key: "name", type: "text", required: true },
            { label: "Email", key: "email", type: "email" },
            { label: "Phone", key: "phone", type: "text" },
            { label: "Age", key: "age", type: "number" },
            { label: "Annual Income (₹)", key: "income", type: "number" },
            { label: "Monthly EMI Obligations (₹)", key: "liabilities_emi", type: "number" },
            { label: "Family Size", key: "family_size", type: "number" },
          ].map(({ label, key, type, required }) => (
            <div key={key}>
              <label className="text-xs text-gray-500 mb-1 block">{label}</label>
              <input
                type={type}
                required={required}
                value={(form as any)[key]}
                onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                className={inputCls}
              />
            </div>
          ))}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Employment Type</label>
              <select value={form.employment_type} onChange={(e) => setForm({ ...form, employment_type: e.target.value })} className={inputCls}>
                <option value="salaried">Salaried</option>
                <option value="self_employed">Self Employed</option>
                <option value="business">Business Owner</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">City Tier</label>
              <select value={form.city_tier} onChange={(e) => setForm({ ...form, city_tier: e.target.value })} className={inputCls}>
                <option value="tier1">Tier 1</option>
                <option value="tier2">Tier 2</option>
                <option value="tier3">Tier 3</option>
              </select>
            </div>
          </div>

          <div>
            <label className="text-xs text-gray-500 mb-1 block">Risk Appetite</label>
            <select value={form.risk_appetite} onChange={(e) => setForm({ ...form, risk_appetite: e.target.value })} className={inputCls}>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
          </div>

          <div>
            <label className="text-xs text-gray-500 mb-1 block">Goals</label>
            <textarea value={form.goals} onChange={(e) => setForm({ ...form, goals: e.target.value })} rows={2} className={inputCls} />
          </div>

          <div>
            <label className="text-xs text-gray-500 mb-1 block">Health Conditions</label>
            <input type="text" placeholder="e.g. smoker, diabetes, hypertension" value={form.health_conditions} onChange={(e) => setForm({ ...form, health_conditions: e.target.value })} className={inputCls} />
          </div>

          <div>
            <label className="text-xs text-gray-500 mb-1 block">Existing Coverage</label>
            <input type="text" placeholder="e.g. LIC term 50L, HDFC health 5L" value={form.existing_coverage} onChange={(e) => setForm({ ...form, existing_coverage: e.target.value })} className={inputCls} />
          </div>

          <div>
            <label className="text-xs text-gray-500 mb-1 block">Dependents</label>
            <input type="text" placeholder="e.g. spouse (32), son (5), mother (62)" value={form.dependents_detail} onChange={(e) => setForm({ ...form, dependents_detail: e.target.value })} className={inputCls} />
          </div>

          <div className="flex gap-2 pt-2 shrink-0">
            <button type="button" onClick={onClose} className="flex-1 border border-gray-200 rounded-lg py-2 text-sm text-gray-600 hover:bg-gray-50">Cancel</button>
            <button type="submit" disabled={mutation.isPending} className="flex-1 bg-blue-600 text-white rounded-lg py-2 text-sm hover:bg-blue-700 disabled:opacity-50">
              {mutation.isPending ? "Adding..." : "Add Lead"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function LeadsPage() {
  const [showModal, setShowModal] = useState(false);
  const [filterStatus, setFilterStatus] = useState("");
  const qc = useQueryClient();
  const { advisor } = useAdvisor();
  const advisorId = advisor?.id ?? "";

  const { data: leads = [], isLoading } = useQuery({
    queryKey: ["leads", advisorId, filterStatus],
    queryFn: () => getLeads(advisorId, filterStatus || undefined),
    enabled: !!advisorId,
  });

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => updateLead(id, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["leads"] }),
  });

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-800">Leads</h1>
          <p className="text-sm text-gray-500 mt-0.5">{leads.length} clients</p>
        </div>
        <button onClick={() => setShowModal(true)}
          className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700">
          <Plus size={16} /> Add Lead
        </button>
      </div>

      <div className="flex gap-2 flex-wrap">
        <button onClick={() => setFilterStatus("")}
          className={`px-3 py-1 rounded-full text-xs font-medium border ${!filterStatus ? "bg-gray-800 text-white border-gray-800" : "bg-white text-gray-600 border-gray-200 hover:bg-gray-50"}`}>
          All
        </button>
        {STATUS_OPTIONS.map((s) => (
          <button key={s} onClick={() => setFilterStatus(s)}
            className={`px-3 py-1 rounded-full text-xs font-medium border capitalize ${filterStatus === s ? "bg-gray-800 text-white border-gray-800" : "bg-white text-gray-600 border-gray-200 hover:bg-gray-50"}`}>
            {s}
          </button>
        ))}
      </div>

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {isLoading ? (
          <p className="text-sm text-gray-400 p-5">Loading...</p>
        ) : leads.length === 0 ? (
          <p className="text-sm text-gray-400 p-5">No leads found.</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                {["Name", "Phone", "Age / Income", "Goals", "Status", "Action", ""].map((h) => (
                  <th key={h} className="text-left px-4 py-3 text-xs text-gray-500 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {leads.map((client) => (
                <tr key={client.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-800">{client.name}</td>
                  <td className="px-4 py-3 text-gray-500">{client.phone || "—"}</td>
                  <td className="px-4 py-3 text-gray-500">
                    {client.age ? `${client.age} yrs` : "—"}
                    {client.income ? ` / ₹${(client.income / 100000).toFixed(1)}L` : ""}
                  </td>
                  <td className="px-4 py-3 text-gray-500 max-w-[180px] truncate">{client.goals || "—"}</td>
                  <td className="px-4 py-3">
                    <select
                      value={client.status}
                      onChange={(e) => statusMutation.mutate({ id: client.id, status: e.target.value })}
                      className={`text-xs px-2 py-1 rounded-full font-medium border-0 cursor-pointer ${statusColor[client.status] || "bg-gray-100 text-gray-600"}`}
                    >
                      {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </td>
                  <td className="px-4 py-3">
                    <Link href={`/leads/${client.id}`}
                      className="flex items-center gap-1 text-blue-600 hover:underline text-xs">
                      Analyze <ChevronRight size={13} />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showModal && <AddLeadModal onClose={() => setShowModal(false)} advisorId={advisorId} />}
    </div>
  );
}
