"use client";
import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { getLead, analyzeClient, recommendProducts } from "@/lib/api";
import { use } from "react";
import { ArrowLeft, Brain, PackageSearch } from "lucide-react";
import Link from "next/link";

export default function ClientDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [analysis, setAnalysis] = useState("");
  const [recommendations, setRecommendations] = useState("");
  const [existingPolicies, setExistingPolicies] = useState("");

  const { data: client, isLoading } = useQuery({
    queryKey: ["client", id],
    queryFn: () => getLead(id),
  });

  const analyzeMutation = useMutation({
    mutationFn: () => analyzeClient(id, existingPolicies),
    onSuccess: (data) => setAnalysis(data.analysis),
  });

  const recommendMutation = useMutation({
    mutationFn: () => recommendProducts(id, analysis),
    onSuccess: (data) => setRecommendations(data.recommendations),
  });

  if (isLoading) return <p className="text-sm text-gray-400">Loading...</p>;
  if (!client) return <p className="text-sm text-red-500">Client not found.</p>;

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex items-center gap-3">
        <Link href="/leads" className="text-gray-400 hover:text-gray-600">
          <ArrowLeft size={18} />
        </Link>
        <div>
          <h1 className="text-xl font-semibold text-gray-800">{client.name}</h1>
          <p className="text-sm text-gray-500">{client.email} · {client.phone}</p>
        </div>
      </div>

      {/* Client Profile */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">Client Profile</h2>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          {[
            { label: "Age", value: client.age ? `${client.age} yrs` : "—" },
            { label: "Annual Income", value: client.income ? `₹${(client.income / 100000).toFixed(1)}L` : "—" },
            { label: "Family Size", value: client.family_size ?? "—" },
            { label: "Risk Appetite", value: client.risk_appetite ?? "—" },
            { label: "Status", value: client.status },
            { label: "Goals", value: client.goals || "—" },
          ].map(({ label, value }) => (
            <div key={label}>
              <p className="text-xs text-gray-400">{label}</p>
              <p className="text-sm font-medium text-gray-700 capitalize">{String(value)}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Need Analysis */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
        <h2 className="text-sm font-semibold text-gray-700">Insurance Need Analysis</h2>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">Existing Policies (optional)</label>
          <input
            type="text"
            placeholder="e.g. LIC term plan, HDFC health 5L"
            value={existingPolicies}
            onChange={(e) => setExistingPolicies(e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <button
          onClick={() => analyzeMutation.mutate()}
          disabled={analyzeMutation.isPending}
          className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50"
        >
          <Brain size={15} />
          {analyzeMutation.isPending ? "Analyzing..." : "Analyze Needs"}
        </button>
        {analysis && (
          <div className="bg-blue-50 rounded-lg p-4 text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
            {analysis}
          </div>
        )}
      </div>

      {/* Product Recommendations */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
        <h2 className="text-sm font-semibold text-gray-700">Product Recommendations</h2>
        <button
          onClick={() => recommendMutation.mutate()}
          disabled={!analysis || recommendMutation.isPending}
          className="flex items-center gap-2 bg-green-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-green-700 disabled:opacity-50"
        >
          <PackageSearch size={15} />
          {recommendMutation.isPending ? "Fetching..." : "Recommend Products"}
        </button>
        {!analysis && (
          <p className="text-xs text-gray-400">Run Need Analysis first to unlock recommendations.</p>
        )}
        {recommendations && (
          <div className="bg-green-50 rounded-lg p-4 text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
            {recommendations}
          </div>
        )}
      </div>
    </div>
  );
}
