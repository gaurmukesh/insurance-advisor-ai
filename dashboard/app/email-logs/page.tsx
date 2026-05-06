"use client";
import { useState } from "react";
import api from "@/lib/api";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle, XCircle, Clock } from "lucide-react";

interface EmailLog {
  id: string;
  client_id: string;
  subject: string;
  body: string;
  status: string;
  sent_at: string;
}

const statusIcon: Record<string, React.ReactNode> = {
  sent: <CheckCircle size={14} className="text-green-500" />,
  failed: <XCircle size={14} className="text-red-500" />,
  opened: <CheckCircle size={14} className="text-blue-500" />,
};

export default function EmailLogsPage() {
  const [expanded, setExpanded] = useState<string | null>(null);

  const { data: logs = [], isLoading } = useQuery({
    queryKey: ["email-logs"],
    queryFn: () => api.get<EmailLog[]>("/api/v1/email-logs").then((r) => r.data),
  });

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-gray-800">Email Logs</h1>
        <p className="text-sm text-gray-500 mt-0.5">{logs.length} emails sent</p>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {isLoading ? (
          <p className="text-sm text-gray-400 p-5">Loading...</p>
        ) : logs.length === 0 ? (
          <p className="text-sm text-gray-400 p-5">No emails sent yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                {["Subject", "Status", "Sent At", "Body"].map((h) => (
                  <th key={h} className="text-left px-4 py-3 text-xs text-gray-500 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {logs.map((log) => (
                <>
                  <tr key={log.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-gray-800 max-w-[220px] truncate">{log.subject}</td>
                    <td className="px-4 py-3">
                      <span className="flex items-center gap-1 capitalize">
                        {statusIcon[log.status] || <Clock size={14} className="text-gray-400" />}
                        {log.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-500">
                      {new Date(log.sent_at).toLocaleString("en-IN")}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => setExpanded(expanded === log.id ? null : log.id)}
                        className="text-xs text-blue-600 hover:underline"
                      >
                        {expanded === log.id ? "Hide" : "View"}
                      </button>
                    </td>
                  </tr>
                  {expanded === log.id && (
                    <tr key={`${log.id}-body`}>
                      <td colSpan={4} className="px-4 py-3 bg-gray-50">
                        <p className="text-sm text-gray-700 whitespace-pre-wrap">{log.body}</p>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
