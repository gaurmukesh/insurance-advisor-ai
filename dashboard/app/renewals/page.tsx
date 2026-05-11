"use client";
import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { getUpcomingRenewals, draftReminderEmail, sendReminderEmail, sendWhatsAppReminder } from "@/lib/api";
import { useAdvisor } from "@/lib/AdvisorContext";
import { Mail, Eye, MessageCircle } from "lucide-react";

function EmailPreviewModal({ content, onClose, onSend, sending }: {
  content: { subject: string; body: string; client_email: string };
  onClose: () => void;
  onSend: () => void;
  sending: boolean;
}) {
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl p-6 w-full max-w-lg shadow-xl space-y-4">
        <h2 className="text-base font-semibold text-gray-800">Email Preview</h2>
        <div className="space-y-2">
          <p className="text-xs text-gray-500">To: <span className="font-medium text-gray-700">{content.client_email}</span></p>
          <p className="text-xs text-gray-500">Subject: <span className="font-medium text-gray-700">{content.subject}</span></p>
          <div className="border border-gray-200 rounded-lg p-4 text-sm text-gray-700 whitespace-pre-wrap bg-gray-50 max-h-60 overflow-y-auto">
            {content.body}
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={onClose} className="flex-1 border border-gray-200 rounded-lg py-2 text-sm text-gray-600 hover:bg-gray-50">
            Close
          </button>
          <button onClick={onSend} disabled={sending}
            className="flex-1 bg-blue-600 text-white rounded-lg py-2 text-sm hover:bg-blue-700 disabled:opacity-50">
            {sending ? "Sending..." : "Send Email"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function RenewalsPage() {
  const [days, setDays] = useState(30);
  const [preview, setPreview] = useState<any>(null);
  const [selectedPolicyId, setSelectedPolicyId] = useState("");
  const { advisor } = useAdvisor();
  const advisorId = advisor?.id ?? "";
  const advisorName = advisor?.name ?? "";

  const { data: renewals = [], isLoading } = useQuery({
    queryKey: ["renewals", advisorId, days],
    queryFn: () => getUpcomingRenewals(advisorId, days),
    enabled: !!advisorId,
  });

  const draftMutation = useMutation({
    mutationFn: (policy_id: string) => draftReminderEmail(policy_id, advisorName),
    onSuccess: (data, policy_id) => { setPreview(data); setSelectedPolicyId(policy_id); },
  });

  const sendMutation = useMutation({
    mutationFn: () => sendReminderEmail(selectedPolicyId, advisorName),
    onSuccess: () => { setPreview(null); setSelectedPolicyId(""); },
  });

  const [waSending, setWaSending] = useState<string | null>(null);
  const waMutation = useMutation({
    mutationFn: (policy_id: string) => sendWhatsAppReminder(policy_id),
    onMutate: (policy_id) => setWaSending(policy_id),
    onSettled: () => setWaSending(null),
  });

  const urgencyColor = (date: string) => {
    const days = Math.ceil((new Date(date).getTime() - Date.now()) / 86400000);
    if (days <= 7) return "text-red-600 font-semibold";
    if (days <= 15) return "text-orange-500 font-medium";
    return "text-gray-600";
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-800">Upcoming Renewals</h1>
          <p className="text-sm text-gray-500 mt-0.5">{renewals.length} policies due</p>
        </div>
        <select value={days} onChange={(e) => setDays(Number(e.target.value))}
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
          <option value={7}>Next 7 days</option>
          <option value={15}>Next 15 days</option>
          <option value={30}>Next 30 days</option>
        </select>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {isLoading ? (
          <p className="text-sm text-gray-400 p-5">Loading...</p>
        ) : renewals.length === 0 ? (
          <p className="text-sm text-gray-400 p-5">No renewals in this period.</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                {["Client", "Policy", "Insurer", "Premium", "Due Date", "Actions"].map((h) => (
                  <th key={h} className="text-left px-4 py-3 text-xs text-gray-500 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {renewals.map((r) => (
                <tr key={r.policy_id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <p className="font-medium text-gray-800">{r.client_name}</p>
                    <p className="text-xs text-gray-400">{r.client_email || r.client_phone || "—"}</p>
                  </td>
                  <td className="px-4 py-3 text-gray-600">{r.product_name}</td>
                  <td className="px-4 py-3 text-gray-500">{r.insurer_name}</td>
                  <td className="px-4 py-3 font-medium text-gray-800">₹{r.premium_amount.toLocaleString()}</td>
                  <td className={`px-4 py-3 ${urgencyColor(r.next_due_date)}`}>{r.next_due_date}</td>
                  <td className="px-4 py-3">
                    <div className="flex flex-col gap-1.5">
                      <button
                        onClick={() => draftMutation.mutate(r.policy_id)}
                        disabled={draftMutation.isPending}
                        className="flex items-center gap-1 text-xs text-blue-600 hover:underline disabled:opacity-50"
                      >
                        <Eye size={13} />
                        {draftMutation.isPending && selectedPolicyId === r.policy_id ? "Drafting..." : "Preview & Send Email"}
                      </button>
                      {r.client_phone && (
                        <button
                          onClick={() => waMutation.mutate(r.policy_id)}
                          disabled={waSending === r.policy_id}
                          className="flex items-center gap-1 text-xs text-green-600 hover:underline disabled:opacity-50"
                        >
                          <MessageCircle size={13} />
                          {waSending === r.policy_id ? "Sending..." : "Send WhatsApp"}
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {preview && (
        <EmailPreviewModal
          content={preview}
          onClose={() => setPreview(null)}
          onSend={() => sendMutation.mutate()}
          sending={sendMutation.isPending}
        />
      )}
    </div>
  );
}
