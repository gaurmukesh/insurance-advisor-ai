"use client";
import { useQuery } from "@tanstack/react-query";
import { getMetrics, Metrics } from "@/lib/api";
import { useAdvisor } from "@/lib/AdvisorContext";
import { Mail, MessageCircle, TrendingUp, IndianRupee, Bell, Users } from "lucide-react";

function StatCard({
  label,
  value,
  sub,
  icon: Icon,
  color,
}: {
  label: string;
  value: string | number;
  sub?: string;
  icon: any;
  color: string;
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 flex items-start gap-4">
      <div className={`p-3 rounded-lg ${color} shrink-0`}>
        <Icon size={18} className="text-white" />
      </div>
      <div>
        <p className="text-xs text-gray-500">{label}</p>
        <p className="text-2xl font-semibold text-gray-800">{value}</p>
        {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

function PipelineBar({ data }: { data: Metrics["leads"]["by_status"] }) {
  const statuses: Array<{ key: keyof typeof data; label: string; color: string }> = [
    { key: "new", label: "New", color: "bg-yellow-400" },
    { key: "contacted", label: "Contacted", color: "bg-blue-400" },
    { key: "interested", label: "Interested", color: "bg-indigo-400" },
    { key: "converted", label: "Converted", color: "bg-green-500" },
    { key: "lost", label: "Lost", color: "bg-red-400" },
  ];
  const total = Object.values(data).reduce((a, b) => a + b, 0) || 1;

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
      <p className="text-sm font-semibold text-gray-700">Lead Pipeline</p>
      <div className="flex rounded-full overflow-hidden h-4 gap-0.5">
        {statuses.map(({ key, color }) =>
          data[key] > 0 ? (
            <div
              key={key}
              className={`${color} transition-all`}
              style={{ width: `${(data[key] / total) * 100}%` }}
              title={`${key}: ${data[key]}`}
            />
          ) : null
        )}
      </div>
      <div className="flex flex-wrap gap-3">
        {statuses.map(({ key, label, color }) => (
          <div key={key} className="flex items-center gap-1.5">
            <span className={`w-2.5 h-2.5 rounded-full ${color}`} />
            <span className="text-xs text-gray-600">
              {label} <span className="font-medium text-gray-800">{data[key]}</span>
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function StatusBreakdown({
  title,
  icon: Icon,
  iconColor,
  byStatus,
  total,
}: {
  title: string;
  icon: any;
  iconColor: string;
  byStatus: Record<string, number>;
  total: number;
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-3">
      <div className="flex items-center gap-2">
        <Icon size={16} className={iconColor} />
        <p className="text-sm font-semibold text-gray-700">{title}</p>
        <span className="ml-auto text-xs text-gray-400">{total} total</span>
      </div>
      {total === 0 ? (
        <p className="text-xs text-gray-400">No activity yet.</p>
      ) : (
        <ul className="space-y-1.5">
          {Object.entries(byStatus).map(([status, count]) => (
            <li key={status} className="flex items-center justify-between text-sm">
              <span className="text-gray-600 capitalize">{status}</span>
              <div className="flex items-center gap-2">
                <div className="w-24 bg-gray-100 rounded-full h-1.5">
                  <div
                    className="bg-blue-500 h-1.5 rounded-full"
                    style={{ width: `${(count / total) * 100}%` }}
                  />
                </div>
                <span className="text-gray-800 font-medium w-6 text-right">{count}</span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ActivityFeed({ activity }: { activity: Metrics["recent_activity"] }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-3">
      <p className="text-sm font-semibold text-gray-700">Recent Activity</p>
      {activity.length === 0 ? (
        <p className="text-xs text-gray-400">No activity yet.</p>
      ) : (
        <ul className="space-y-3">
          {activity.map((item, i) => (
            <li key={i} className="flex items-start gap-3">
              <div
                className={`mt-0.5 p-1.5 rounded-lg shrink-0 ${
                  item.type === "email" ? "bg-blue-50" : "bg-green-50"
                }`}
              >
                {item.type === "email" ? (
                  <Mail size={12} className="text-blue-500" />
                ) : (
                  <MessageCircle size={12} className="text-green-500" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-gray-700 truncate">
                  <span className="font-medium">{item.client}</span> — {item.detail}
                </p>
                <p className="text-xs text-gray-400 mt-0.5">
                  {item.status}{" "}
                  {item.time
                    ? `· ${new Date(item.time).toLocaleString("en-IN", {
                        day: "numeric",
                        month: "short",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}`
                    : ""}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function MetricsPage() {
  const { advisor } = useAdvisor();
  const advisorId = advisor?.id ?? "";

  const { data, isLoading } = useQuery({
    queryKey: ["metrics", advisorId],
    queryFn: () => getMetrics(advisorId),
    enabled: !!advisorId,
    refetchInterval: 60000,
  });

  if (isLoading || !data) {
    return (
      <div className="space-y-6">
        <h1 className="text-xl font-semibold text-gray-800">Business Metrics</h1>
        <p className="text-sm text-gray-400">Loading...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-800">Business Metrics</h1>
        <p className="text-sm text-gray-500 mt-0.5">Performance overview for your advisory practice.</p>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          label="Total Leads"
          value={data.leads.total}
          sub={`${data.leads.conversion_rate}% conversion rate`}
          icon={Users}
          color="bg-blue-500"
        />
        <StatCard
          label="Converted"
          value={data.leads.by_status.converted}
          sub={`${data.leads.by_status.interested} interested`}
          icon={TrendingUp}
          color="bg-green-500"
        />
        <StatCard
          label="Due in 30 Days"
          value={data.policies.due_in_30_days}
          sub={`${data.policies.due_in_7_days} due this week`}
          icon={Bell}
          color="bg-orange-500"
        />
        <StatCard
          label="Total Premium"
          value={`₹${(data.policies.total_premium / 1000).toFixed(0)}K`}
          sub={`across ${data.policies.total} policies`}
          icon={IndianRupee}
          color="bg-violet-500"
        />
      </div>

      <PipelineBar data={data.leads.by_status} />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <StatusBreakdown
          title="Email Activity"
          icon={Mail}
          iconColor="text-blue-500"
          byStatus={data.emails.by_status}
          total={data.emails.total}
        />
        <StatusBreakdown
          title="WhatsApp Activity"
          icon={MessageCircle}
          iconColor="text-green-500"
          byStatus={data.whatsapp.by_status}
          total={data.whatsapp.total}
        />
        <ActivityFeed activity={data.recent_activity} />
      </div>
    </div>
  );
}
