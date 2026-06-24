"use client";
import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { getLead, analyzeClient, recommendProducts, generatePitch, handleObjection, getCommonObjections, ProductRecommendation, ObjectionResponse } from "@/lib/api";
import { use } from "react";
import { ArrowLeft, Brain, PackageSearch, Mic, ShieldAlert, Star, ChevronDown, ChevronUp } from "lucide-react";
import Link from "next/link";

export default function ClientDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [analysis, setAnalysis] = useState("");
  const [recommendations, setRecommendations] = useState<ProductRecommendation[]>([]);
  const [activeCard, setActiveCard] = useState<number | null>(null);
  const [existingPolicies, setExistingPolicies] = useState("");
  const [pitch, setPitch] = useState("");
  const [objection, setObjection] = useState("");
  const [objectionResponse, setObjectionResponse] = useState<ObjectionResponse | null>(null);
  const [customObjection, setCustomObjection] = useState("");

  const { data: client, isLoading } = useQuery({
    queryKey: ["client", id],
    queryFn: () => getLead(id),
    onSuccess: (data) => { if (data.existing_coverage) setExistingPolicies(data.existing_coverage); },
  });

  const analyzeMutation = useMutation({
    mutationFn: () => analyzeClient(id, existingPolicies),
    onSuccess: (data) => setAnalysis(data.analysis),
  });

  const recommendMutation = useMutation({
    mutationFn: () => recommendProducts(id, analysis),
    onSuccess: (data) => {
      setRecommendations(data.recommendations);
      const pitchFirst = data.recommendations.findIndex((r) => r.pitch_first);
      setActiveCard(pitchFirst >= 0 ? pitchFirst : 0);
    },
  });

  const pitchMutation = useMutation({
    mutationFn: () => generatePitch(id, existingPolicies),
    onSuccess: (data) => setPitch(data.pitch),
  });

  const { data: commonObjections = [] } = useQuery({
    queryKey: ["common-objections"],
    queryFn: getCommonObjections,
  });

  const objectionMutation = useMutation({
    mutationFn: () => handleObjection(id, objection || customObjection, existingPolicies),
    onSuccess: (data) => { setObjectionResponse(data.response); },
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
            { label: "Monthly EMI", value: client.liabilities_emi ? `₹${client.liabilities_emi.toLocaleString("en-IN")}` : "—" },
            { label: "Employment", value: client.employment_type?.replace("_", " ") ?? "—" },
            { label: "Family Size", value: client.family_size ?? "—" },
            { label: "City Tier", value: client.city_tier?.replace("tier", "Tier ") ?? "—" },
            { label: "Risk Appetite", value: client.risk_appetite ?? "—" },
            { label: "Status", value: client.status },
            { label: "Goals", value: client.goals || "—" },
            { label: "Health Conditions", value: client.health_conditions || "—" },
            { label: "Existing Coverage", value: client.existing_coverage || "—" },
            { label: "Dependents", value: client.dependents_detail || "—" },
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
          {recommendMutation.isPending ? "Analyzing..." : "Recommend Products"}
        </button>
        {!analysis && (
          <p className="text-xs text-gray-400">Run Need Analysis first to unlock recommendations.</p>
        )}
        {recommendations.length > 0 && (
          <div className="space-y-3">
            {recommendations.map((rec, i) => (
              <div
                key={i}
                className={`rounded-xl border transition-all ${
                  rec.pitch_first
                    ? "border-green-400 bg-green-50"
                    : "border-gray-200 bg-white"
                }`}
              >
                {/* Card header — always visible */}
                <button
                  className="w-full text-left p-4"
                  onClick={() => setActiveCard(activeCard === i ? null : i)}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-3">
                      <span className={`shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                        rec.pitch_first ? "bg-green-500 text-white" : "bg-gray-100 text-gray-600"
                      }`}>
                        {rec.rank}
                      </span>
                      <div>
                        <div className="flex items-center gap-2 flex-wrap">
                          <p className="text-sm font-semibold text-gray-800">{rec.product_name}</p>
                          {rec.pitch_first && (
                            <span className="flex items-center gap-1 text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">
                              <Star size={10} /> Pitch First
                            </span>
                          )}
                          <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full capitalize">
                            {rec.type.replace("_", " ")}
                          </span>
                        </div>
                        <p className="text-xs text-gray-500 mt-0.5">{rec.insurer}</p>
                      </div>
                    </div>
                    <div className="shrink-0 text-right">
                      <p className="text-sm font-semibold text-gray-800">
                        ₹{rec.premium_per_month.toLocaleString("en-IN")}<span className="text-xs font-normal text-gray-400">/mo</span>
                      </p>
                      <p className="text-xs text-gray-400">SA: {rec.sum_assured}</p>
                    </div>
                  </div>
                  <p className="text-xs text-gray-500 mt-2 ml-9">{rec.key_benefit}</p>
                  <div className="flex justify-end mt-1">
                    {activeCard === i ? <ChevronUp size={14} className="text-gray-400" /> : <ChevronDown size={14} className="text-gray-400" />}
                  </div>
                </button>

                {/* Expanded detail */}
                {activeCard === i && (
                  <div className="px-4 pb-4 ml-9 space-y-3 border-t border-gray-100 pt-3">
                    <div>
                      <p className="text-xs font-medium text-gray-500 mb-1">Why this suits the client</p>
                      <p className="text-sm text-gray-700 leading-relaxed">{rec.why_suits}</p>
                    </div>
                    {rec.tax_benefit && rec.tax_benefit !== "none" && (
                      <div className="flex items-center gap-2 bg-blue-50 rounded-lg px-3 py-2">
                        <span className="text-xs font-medium text-blue-700">Tax Benefit:</span>
                        <span className="text-xs text-blue-600">{rec.tax_benefit}</span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Sales Pitch */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
        <h2 className="text-sm font-semibold text-gray-700">Sales Pitch</h2>
        <p className="text-xs text-gray-400">Generate a personalized pitch script for this client.</p>
        <button
          onClick={() => pitchMutation.mutate()}
          disabled={pitchMutation.isPending}
          className="flex items-center gap-2 bg-purple-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-purple-700 disabled:opacity-50"
        >
          <Mic size={15} />
          {pitchMutation.isPending ? "Generating..." : "Generate Pitch"}
        </button>
        {pitch && (
          <div className="bg-purple-50 rounded-lg p-4 text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
            {pitch}
          </div>
        )}
      </div>

      {/* Objection Handler */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
        <h2 className="text-sm font-semibold text-gray-700">Objection Handler</h2>
        <p className="text-xs text-gray-400">Select a common objection or type your own, then get a suggested response.</p>

        <div className="space-y-2">
          <label className="text-xs text-gray-500 block">Common Objections</label>
          <div className="flex flex-wrap gap-2">
            {commonObjections.map((o) => (
              <button
                key={o}
                onClick={() => { setObjection(o); setCustomObjection(""); setObjectionResponse(null); }}
                className={`px-3 py-1.5 rounded-full text-xs border transition-colors ${
                  objection === o
                    ? "bg-orange-100 border-orange-400 text-orange-700 font-medium"
                    : "border-gray-200 text-gray-600 hover:bg-gray-50"
                }`}
              >
                {o}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="text-xs text-gray-500 mb-1 block">Or type a custom objection</label>
          <input
            type="text"
            placeholder="e.g. My family doesn't support buying insurance"
            value={customObjection}
            onChange={(e) => { setCustomObjection(e.target.value); setObjection(""); setObjectionResponse(null); }}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400"
          />
        </div>

        <button
          onClick={() => objectionMutation.mutate()}
          disabled={(!objection && !customObjection) || objectionMutation.isPending}
          className="flex items-center gap-2 bg-orange-500 text-white px-4 py-2 rounded-lg text-sm hover:bg-orange-600 disabled:opacity-50"
        >
          <ShieldAlert size={15} />
          {objectionMutation.isPending ? "Thinking..." : "Handle Objection"}
        </button>

        {objectionResponse && (
          <div className="space-y-3">
            <p className="text-xs text-orange-500 font-medium">
              Client said: &quot;{objection || customObjection}&quot;
            </p>

            {[
              { label: "1. Acknowledge", text: objectionResponse.acknowledge, color: "border-l-orange-300 bg-orange-50" },
              { label: "2. Reframe", text: objectionResponse.reframe, color: "border-l-yellow-300 bg-yellow-50" },
              { label: "3. Strong Reason", text: objectionResponse.strong_reason, color: "border-l-red-400 bg-red-50" },
              { label: "4. Why It Matters for You", text: objectionResponse.client_specific_impact, color: "border-l-blue-400 bg-blue-50" },
              { label: "5. Supporting Fact", text: objectionResponse.stat_or_fact, color: "border-l-purple-400 bg-purple-50" },
              { label: "6. Closing Line", text: objectionResponse.closing_line, color: "border-l-green-400 bg-green-50" },
            ].filter(s => s.text).map(({ label, text, color }) => (
              <div key={label} className={`border-l-4 rounded-r-lg p-3 ${color}`}>
                <p className="text-xs font-semibold text-gray-500 mb-1">{label}</p>
                <p className="text-sm text-gray-700 leading-relaxed">{text}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
