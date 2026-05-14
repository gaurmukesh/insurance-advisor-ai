"use client";
import { useState } from "react";
import api from "@/lib/api";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle, XCircle, Edit2 } from "lucide-react";

interface EmailDraft {
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

function DraftRow({ draft }: { draft: EmailDraft }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [body, setBody] = useState(draft.edited_body || draft.body);

  const approveMutation = useMutation({
    mutationFn: () =>
      api.post(`/api/v1/email-drafts/${draft.id}/approve`, {
        edited_body: body !== draft.body ? body : null,
      }).then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["email-drafts"] }),
  });

  const rejectMutation = useMutation({
    mutationFn: () =>
      api.post(`/api/v1/email-drafts/${draft.id}/reject`).then((r) => r.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["email-drafts"] }),
  });

  const busy = approveMutation.isPending || rejectMutation.isPending;

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-3">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-medium text-gray-800">{draft.client_name}</p>
          <p className="text-xs text-gray-400">{draft.client_email}</p>
          <p className="text-sm text-gray-600 mt-1 font-medium">{draft.subject}</p>
        </div>
        <p className="text-xs text-gray-400 shrink-0">
          {new Date(draft.sent_at).toLocaleString("en-IN")}
        </p>
      </div>

      <div className="relative">
        {editing ? (
          <textarea
            className="w-full border border-blue-300 rounded-lg p-3 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
            rows={8}
            value={body}
            onChange={(e) => setBody(e.target.value)}
          />
        ) : (
          <div className="border border-gray-100 rounded-lg p-3 text-sm text-gray-700 whitespace-pre-wrap bg-gray-50 max-h-48 overflow-y-auto">
            {body}
          </div>
        )}
        <button
          onClick={() => setEditing(!editing)}
          className="absolute top-2 right-2 text-gray-400 hover:text-blue-600"
          title="Edit body"
        >
          <Edit2 size={14} />
        </button>
      </div>

      {(approveMutation.isError || rejectMutation.isError) && (
        <p className="text-xs text-red-500">Something went wrong. Please try again.</p>
      )}

      <div className="flex gap-2">
        <button
          onClick={() => rejectMutation.mutate()}
          disabled={busy}
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg border border-gray-200 text-sm text-gray-600 hover:bg-gray-50 disabled:opacity-50"
        >
          <XCircle size={15} className="text-red-400" />
          Reject
        </button>
        <button
          onClick={() => approveMutation.mutate()}
          disabled={busy}
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-blue-600 text-white text-sm hover:bg-blue-700 disabled:opacity-50"
        >
          <CheckCircle size={15} />
          {approveMutation.isPending ? "Sending..." : "Approve & Send"}
        </button>
      </div>
    </div>
  );
}

export default function EmailDraftsPage() {
  const { data: drafts = [], isLoading } = useQuery({
    queryKey: ["email-drafts"],
    queryFn: () => api.get<EmailDraft[]>("/api/v1/email-drafts").then((r) => r.data),
    refetchInterval: 30000,
  });

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-gray-800">Pending Approvals</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          {drafts.length === 0
            ? "No pending emails"
            : `${drafts.length} email${drafts.length > 1 ? "s" : ""} awaiting your approval`}
        </p>
      </div>

      {isLoading ? (
        <p className="text-sm text-gray-400">Loading...</p>
      ) : drafts.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 p-10 text-center">
          <CheckCircle size={32} className="text-green-400 mx-auto mb-2" />
          <p className="text-sm text-gray-500">All caught up — no pending emails.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {drafts.map((d) => <DraftRow key={d.id} draft={d} />)}
        </div>
      )}
    </div>
  );
}
