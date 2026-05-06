"use client";
import { useQuery } from "@tanstack/react-query";
import { getLeads, getUpcomingRenewals } from "@/lib/api";
import { useAdvisor } from "@/lib/AdvisorContext";
import { Users, Bell, CheckCircle, Clock } from "lucide-react";

function StatCard({ title, value, icon: Icon, color }: {
  title: string; value: number; icon: any; color: string;
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 flex items-center gap-4">
      <div className={`p-3 rounded-lg ${color}`}>
        <Icon size={20} className="text-white" />
      </div>
      <div>
        <p className="text-sm text-gray-500">{title}</p>
        <p className="text-2xl font-semibold text-gray-800">{value}</p>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { advisor } = useAdvisor();
  const advisorId = advisor?.id ?? "";

  const { data: leads = [] } = useQuery({
    queryKey: ["leads", advisorId],
    queryFn: () => getLeads(advisorId),
    enabled: !!advisorId,
  });

  const { data: renewals = [] } = useQuery({
    queryKey: ["renewals", advisorId],
    queryFn: () => getUpcomingRenewals(advisorId, 30),
    enabled: !!advisorId,
  });

  const converted = leads.filter((l) => l.status === "converted").length;
  const newLeads = leads.filter((l) => l.status === "new").length;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-800">Dashboard</h1>
        <p className="text-sm text-gray-500 mt-1">
          {advisor ? `Welcome back, ${advisor.name}.` : "Loading..."}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard title="Total Leads" value={leads.length} icon={Users} color="bg-blue-500" />
        <StatCard title="New Leads" value={newLeads} icon={Clock} color="bg-yellow-500" />
        <StatCard title="Converted" value={converted} icon={CheckCircle} color="bg-green-500" />
        <StatCard title="Due in 30 Days" value={renewals.length} icon={Bell} color="bg-red-500" />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">Recent Leads</h2>
          {leads.length === 0 ? (
            <p className="text-sm text-gray-400">No leads yet.</p>
          ) : (
            <ul className="space-y-3">
              {leads.slice(0, 5).map((client) => (
                <li key={client.id} className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-700">{client.name}</p>
                    <p className="text-xs text-gray-400">{client.goals || "No goals set"}</p>
                  </div>
                  <span className={`text-xs px-2 py-1 rounded-full font-medium ${
                    client.status === "converted" ? "bg-green-100 text-green-700" :
                    client.status === "interested" ? "bg-blue-100 text-blue-700" :
                    client.status === "new" ? "bg-yellow-100 text-yellow-700" :
                    "bg-gray-100 text-gray-600"
                  }`}>
                    {client.status}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">Upcoming Renewals</h2>
          {renewals.length === 0 ? (
            <p className="text-sm text-gray-400">No renewals due in 30 days.</p>
          ) : (
            <ul className="space-y-3">
              {renewals.slice(0, 5).map((r) => (
                <li key={r.policy_id} className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-700">{r.client_name}</p>
                    <p className="text-xs text-gray-400">{r.product_name}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-medium text-red-600">₹{r.premium_amount.toLocaleString()}</p>
                    <p className="text-xs text-gray-400">{r.next_due_date}</p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
