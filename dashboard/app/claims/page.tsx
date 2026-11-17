"use client";
import { useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AttributeCorrelation,
  ReasonBreakdown,
  RejectionCorrelation,
  getApprovalReasons,
  getRejectionCorrelation,
  getRejectionReasons,
  getSettlementOverview,
  importClaimsCsv,
} from "@/lib/api";
import { useAdvisor } from "@/lib/AdvisorContext";
import { CheckCircle2, ChevronDown, ChevronRight, ClipboardCheck, Percent, Sparkles, Upload, XCircle, type LucideIcon } from "lucide-react";

// Every chart on this page is a single series, so one hue carries all marks.
const BAR = "#2a78d6";

const PERIODS = [
  { months: 6, label: "Past 6 months" },
  { months: 12, label: "Past 1 year" },
  { months: 24, label: "Past 2 years" },
  { months: 60, label: "Past 5 years" },
  { months: 600, label: "All history" },
];

const ATTRIBUTE_LABELS: Record<string, string> = {
  age: "Age",
  annual_income: "Annual income",
  policy_tenure_years: "Policy tenure",
  prior_claims_count: "Prior claims",
  pre_existing_conditions: "Pre-existing conditions",
  gender: "Gender",
  occupation: "Occupation",
  city_tier: "City tier",
  state: "State",
  purchase_channel: "Purchase channel",
};

// Ordinal attributes keep their natural order so a trend across bands is
// readable; nominal ones are shown highest-rejection-rate first (API order).
const ORDINAL_ORDER: Record<string, string[]> = {
  age: ["<30", "30-44", "45-59", "60+"],
  annual_income: ["<3L", "3-6L", "6-12L", "12-25L", "25L+"],
  policy_tenure_years: ["<1y", "1-2y", "2-4y", "4y+"],
  prior_claims_count: ["0", "1", "2", "3+"],
};

const humanize = (key: string | null | undefined) =>
  key ? key.charAt(0).toUpperCase() + key.slice(1).replace(/_/g, " ") : "—";

const inr = (n: number) =>
  n >= 1e7 ? `₹${(n / 1e7).toFixed(1)}Cr` : n >= 1e5 ? `₹${(n / 1e5).toFixed(1)}L` : `₹${Math.round(n).toLocaleString("en-IN")}`;

function Tooltip({ children }: { children: React.ReactNode }) {
  return (
    <div className="pointer-events-none absolute left-1/2 bottom-full z-10 mb-2 hidden w-max max-w-64 -translate-x-1/2 rounded-lg bg-gray-900 px-3 py-2 text-xs text-white shadow-lg group-hover:block">
      {children}
    </div>
  );
}

function StatCard({ label, value, sub, icon: Icon, color }: {
  label: string; value: string | number; sub?: string; icon: LucideIcon; color: string;
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 flex items-start gap-4 min-w-0">
      <div className={`p-3 rounded-lg ${color} shrink-0`}>
        <Icon size={18} className="text-white" />
      </div>
      <div className="min-w-0">
        <p className="text-xs text-gray-500">{label}</p>
        <p className="text-xl font-semibold text-gray-800 truncate">{value}</p>
        {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

function Explanation({ text }: { text: string }) {
  return (
    <div className="rounded-lg bg-blue-50/60 border border-blue-100 p-4 text-sm text-gray-700 leading-relaxed [&_strong]:font-semibold [&_ul]:list-disc [&_ul]:ml-4 [&_ol]:list-decimal [&_ol]:ml-4 [&_li]:mt-1 [&_p]:mt-2 first:[&_p]:mt-0">
      <ReactMarkdown>{text}</ReactMarkdown>
    </div>
  );
}

function ExplainButton<T extends { explanation?: string }>({ fetcher, queryKey }: {
  fetcher: () => Promise<T>; queryKey: unknown[];
}) {
  const { data, isFetching, error, refetch } = useQuery({
    queryKey: [...queryKey, "explain"],
    queryFn: fetcher,
    enabled: false,
    staleTime: Infinity,
  });
  return (
    <div className="space-y-3">
      {!data?.explanation && (
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="inline-flex items-center gap-1.5 text-xs font-medium text-blue-700 hover:text-blue-800 disabled:text-gray-400"
        >
          <Sparkles size={14} />
          {isFetching ? "Explaining..." : "Explain in plain language"}
        </button>
      )}
      {error && <p className="text-xs text-red-600">Explanation unavailable right now.</p>}
      {data?.explanation && <Explanation text={data.explanation} />}
    </div>
  );
}

function ReasonBars({ title, data, months, fetcher }: {
  title: string;
  data: ReasonBreakdown;
  months: number;
  fetcher: (months: number, explain: boolean) => Promise<ReasonBreakdown>;
}) {
  const max = Math.max(1, ...data.reasons.map((r) => r.count));
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-sm font-semibold text-gray-700">{title}</p>
        <span className="text-xs text-gray-400">{data.claims_in_outcome.toLocaleString("en-IN")} claims</span>
      </div>

      {data.primary_reason ? (
        <div>
          <p className="text-xs text-gray-500">Primary reason</p>
          <p className="text-lg font-semibold text-gray-800">{humanize(data.primary_reason.category)}</p>
          <p className="text-xs text-gray-500">
            {data.primary_reason.description} · {data.primary_reason.share_pct}% of {data.outcome} claims
          </p>
        </div>
      ) : (
        <p className="text-xs text-gray-400">No {data.outcome} claims in this period.</p>
      )}

      <ul className="space-y-1">
        {data.reasons.map((r) => (
          <li key={r.category} className="group relative grid grid-cols-[9.5rem_1fr_5.5rem] items-center gap-3 rounded-md px-1 py-1.5 hover:bg-gray-50">
            <span className={`text-sm truncate ${r.category === data.primary_reason?.category ? "font-medium text-gray-800" : "text-gray-600"}`}>
              {humanize(r.category)}
            </span>
            <div className="h-3">
              <div className="h-3 rounded-r" style={{ width: `${(r.count / max) * 100}%`, minWidth: 2, background: BAR }} />
            </div>
            <span className="text-xs text-gray-700 text-right tabular-nums">
              {r.count.toLocaleString("en-IN")} <span className="text-gray-400">· {r.share_pct}%</span>
            </span>
            <Tooltip>
              <p className="font-medium">{humanize(r.category)}</p>
              <p className="text-gray-300">{r.description}</p>
              <p className="mt-1">{r.count.toLocaleString("en-IN")} claims ({r.share_pct}%)</p>
              <p>Claimed {inr(r.total_claimed_amount)} · Settled {inr(r.total_settled_amount)}</p>
            </Tooltip>
          </li>
        ))}
      </ul>

      {data.reasons.length > 0 && (
        <ExplainButton queryKey={["claims", data.outcome, months]} fetcher={() => fetcher(months, true)} />
      )}
    </div>
  );
}

const STRENGTH_STYLE: Record<AttributeCorrelation["strength"], string> = {
  strong: "bg-gray-900 text-white",
  moderate: "bg-gray-700 text-white",
  weak: "bg-gray-200 text-gray-800",
  negligible: "bg-gray-100 text-gray-500",
  insufficient_data: "bg-gray-100 text-gray-400",
};

function AttributeRow({ attr, overallRate, defaultOpen }: {
  attr: AttributeCorrelation; overallRate: number; defaultOpen: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const order = ORDINAL_ORDER[attr.attribute];
  const buckets = order
    ? [...attr.buckets].sort((a, b) => order.indexOf(a.value) - order.indexOf(b.value))
    : attr.buckets;
  const scaleMax = Math.max(overallRate, ...buckets.map((b) => b.rejection_rate_pct), 1) * 1.1;

  return (
    <li className="border-t border-gray-100 first:border-t-0">
      <button onClick={() => setOpen(!open)} className="w-full flex items-center gap-3 py-3 text-left">
        {open ? <ChevronDown size={16} className="text-gray-400" /> : <ChevronRight size={16} className="text-gray-400" />}
        <span className="text-sm font-medium text-gray-800 flex-1">{ATTRIBUTE_LABELS[attr.attribute] ?? humanize(attr.attribute)}</span>
        <span className={`text-[11px] px-2 py-0.5 rounded-full ${STRENGTH_STYLE[attr.strength]}`}>
          {humanize(attr.strength)}
        </span>
        <span className="hidden sm:inline text-xs text-gray-500 tabular-nums w-40 text-right">
          {attr.cramers_v !== null ? `V = ${attr.cramers_v.toFixed(3)}` : "—"}
          {attr.p_value !== null && (
            <span className="text-gray-400"> · {attr.significant ? "p < 0.05" : "not significant"}</span>
          )}
        </span>
      </button>

      {open && (
        <div className="pb-4 pl-7 space-y-1">
          {buckets.map((b) => (
            <div key={b.value} className="group relative grid grid-cols-[7rem_1fr_9rem] items-center gap-3 rounded-md px-1 py-1 hover:bg-gray-50">
              <span className="text-sm text-gray-600 truncate">{b.value}</span>
              <div className="relative h-3">
                <div className="h-3 rounded-r" style={{ width: `${(b.rejection_rate_pct / scaleMax) * 100}%`, minWidth: 2, background: BAR, opacity: b.low_sample ? 0.45 : 1 }} />
                {/* Overall rejection rate reference line */}
                <div className="absolute -top-1 -bottom-1 w-px bg-gray-500" style={{ left: `${(overallRate / scaleMax) * 100}%` }} />
              </div>
              <span className="text-xs text-gray-700 text-right tabular-nums">
                {b.rejection_rate_pct}% rejected
                {b.low_sample && <span className="ml-1 text-gray-400">(low n)</span>}
              </span>
              <Tooltip>
                <p className="font-medium">{ATTRIBUTE_LABELS[attr.attribute]}: {b.value}</p>
                <p className="mt-1">{b.rejected.toLocaleString("en-IN")} of {b.claims.toLocaleString("en-IN")} claims rejected ({b.rejection_rate_pct}%)</p>
                {b.lift_vs_overall !== null && <p>{b.lift_vs_overall}× the overall rate</p>}
                {b.top_rejection_reason && <p>Top reason: {humanize(b.top_rejection_reason)}</p>}
                {b.low_sample && <p className="text-gray-300">Fewer than 30 claims: treat as tentative</p>}
              </Tooltip>
            </div>
          ))}
          <div className="flex flex-wrap gap-x-4 gap-y-1 pt-2 text-xs text-gray-500">
            <span className="flex items-center gap-1.5"><span className="inline-block h-3 w-px bg-gray-500" /> Overall {overallRate}%</span>
            {attr.point_biserial && <span>Point-biserial r = {attr.point_biserial.r}</span>}
            {attr.unknown_count > 0 && <span>{attr.unknown_count.toLocaleString("en-IN")} claims with no value</span>}
          </div>
        </div>
      )}
    </li>
  );
}

function CorrelationPanel({ data, months }: { data: RejectionCorrelation; months: number }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
      <div>
        <p className="text-sm font-semibold text-gray-700">Rejection vs claimant background</p>
        <p className="text-xs text-gray-500 mt-0.5">
          Ranked by strength of association (Cramér&apos;s V). Bars show each group&apos;s rejection rate against the
          overall rate of {data.overall_rejection_rate_pct}%.
        </p>
      </div>

      {data.strongest_factors.length > 0 ? (
        <p className="text-sm text-gray-700">
          Strongest factors:{" "}
          <span className="font-medium">
            {data.strongest_factors.map((f) => ATTRIBUTE_LABELS[f] ?? humanize(f)).join(", ")}
          </span>
        </p>
      ) : (
        <p className="text-sm text-gray-500">No background attribute shows a meaningful, significant association in this period.</p>
      )}

      <ul>
        {data.attributes.map((a, i) => (
          <AttributeRow key={a.attribute} attr={a} overallRate={data.overall_rejection_rate_pct} defaultOpen={i < 3} />
        ))}
      </ul>

      <p className="text-xs text-gray-500 border-t border-gray-100 pt-3">{data.caveat}</p>
      <ExplainButton queryKey={["claims", "correlation", months]} fetcher={() => getRejectionCorrelation(months, true)} />
    </div>
  );
}

// Always the full history (C6), independent of the period picker: a short window
// would show a clipped first year that looks like a ratio swing.
const ALL_HISTORY_MONTHS = 600;

function SettlementTrend() {
  const { data } = useQuery({
    queryKey: ["claims", "overview", ALL_HISTORY_MONTHS],
    queryFn: () => getSettlementOverview(ALL_HISTORY_MONTHS),
  });
  const years = data?.by_year ?? [];
  if (years.length < 2) return null;
  const latest = years[years.length - 1];

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-sm font-semibold text-gray-700">Settlement ratio by year</p>
        <span className="text-xs text-gray-400">share of decided claims approved</span>
      </div>
      <div className="relative h-44 border-b border-gray-200">
        {[25, 50, 75, 100].map((g) => (
          <div key={g} className="absolute inset-x-0 border-t border-gray-100" style={{ bottom: `${g}%` }}>
            <span className="absolute -top-2 left-0 bg-white pr-1 text-[10px] text-gray-400">{g}%</span>
          </div>
        ))}
        <div className="absolute inset-0 left-8 flex items-end justify-around gap-0.5">
          {years.map((y) => (
            <div key={y.year} className="group relative flex h-full flex-1 items-end justify-center">
              {y.year === latest.year && (
                <span className="absolute text-xs font-medium text-gray-700" style={{ bottom: `calc(${y.settlement_ratio_pct}% + 4px)` }}>
                  {y.settlement_ratio_pct}%
                </span>
              )}
              <div className="w-full max-w-6 rounded-t" style={{ height: `${y.settlement_ratio_pct}%`, background: BAR }} />
              <Tooltip>
                <p className="font-medium">{y.year}</p>
                <p className="mt-1">{y.settlement_ratio_pct}% of claims settled</p>
                <p>{y.amount_settlement_ratio_pct}% of claimed amount paid</p>
                <p>{y.rejected_claims.toLocaleString("en-IN")} of {y.decided_claims.toLocaleString("en-IN")} rejected</p>
              </Tooltip>
            </div>
          ))}
        </div>
      </div>
      <div className="flex justify-around pl-8 text-xs text-gray-500">
        {years.map((y) => <span key={y.year} className="flex-1 text-center">{y.year}</span>)}
      </div>
    </div>
  );
}

function ImportCard() {
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const mutation = useMutation({
    mutationFn: importClaimsCsv,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["claims"] }),
  });
  const result = mutation.data;

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-3">
      <div className="flex items-center gap-3">
        <div className="flex-1">
          <p className="text-sm font-semibold text-gray-700">Import historical claims</p>
          <p className="text-xs text-gray-500">CSV with one row per claim. Duplicate claim numbers are skipped, so re-importing is safe.</p>
        </div>
        <input
          ref={inputRef}
          type="file"
          accept=".csv,text/csv"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) mutation.mutate(file);
            e.target.value = "";
          }}
        />
        <button
          onClick={() => inputRef.current?.click()}
          disabled={mutation.isPending}
          className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:bg-gray-300"
        >
          <Upload size={15} />
          {mutation.isPending ? "Importing..." : "Upload CSV"}
        </button>
      </div>
      {mutation.isError && <p className="text-xs text-red-600">Import failed. Check the file is a UTF-8 CSV under 50 MB.</p>}
      {result && (
        <div className="text-xs text-gray-600 space-y-1">
          <p>
            Imported <span className="font-medium text-gray-800">{result.inserted.toLocaleString("en-IN")}</span> claims ·{" "}
            {result.skipped_duplicates.toLocaleString("en-IN")} duplicates skipped · {result.claimants_created.toLocaleString("en-IN")} new claimants ·
            reasons classified by rule {result.classified_by.rule ?? 0}, LLM {result.classified_by.llm ?? 0}, source {result.classified_by.source ?? 0}
          </p>
          {result.error_count > 0 && (
            <details>
              <summary className="cursor-pointer text-red-600">{result.error_count} rows rejected</summary>
              <ul className="mt-1 max-h-40 overflow-y-auto space-y-0.5">
                {result.errors.map((e) => <li key={e.row}>Row {e.row}: {e.error}</li>)}
              </ul>
            </details>
          )}
        </div>
      )}
    </div>
  );
}

export default function ClaimsAnalysisPage() {
  const [months, setMonths] = useState(12);
  const { advisor } = useAdvisor();
  const canImport = advisor?.role === "manager" || advisor?.role === "admin";

  const rejection = useQuery({ queryKey: ["claims", "rejected", months], queryFn: () => getRejectionReasons(months) });
  const approval = useQuery({ queryKey: ["claims", "approved", months], queryFn: () => getApprovalReasons(months) });
  const correlation = useQuery({ queryKey: ["claims", "correlation", months], queryFn: () => getRejectionCorrelation(months) });

  const loading = rejection.isLoading || approval.isLoading || correlation.isLoading;
  const failed = rejection.isError || approval.isError || correlation.isError;
  const empty = rejection.data && rejection.data.total_decided_claims === 0;
  const period = rejection.data?.period;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-gray-800">Claims Analysis</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Why claims were rejected or approved, and how rejection relates to claimant background.
            {period && <span className="text-gray-400"> Decisions from {period.since} to {period.until}.</span>}
          </p>
        </div>
        <select
          value={months}
          onChange={(e) => setMonths(Number(e.target.value))}
          className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700"
          aria-label="Analysis period"
        >
          {PERIODS.map((p) => <option key={p.months} value={p.months}>{p.label}</option>)}
        </select>
      </div>

      {canImport && <ImportCard />}

      {loading && <p className="text-sm text-gray-400">Loading...</p>}
      {failed && <p className="text-sm text-red-600">Could not load claims analysis.</p>}
      {empty && (
        <div className="bg-white rounded-xl border border-dashed border-gray-300 p-8 text-center text-sm text-gray-500">
          No decided claims in this period.{" "}
          {canImport ? "Upload a claims CSV above, or choose a longer period." : "Choose a longer period, or ask a manager to import claims data."}
        </div>
      )}

      {rejection.data && approval.data && correlation.data && !empty && (
        <>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <StatCard
              label="Decided claims"
              value={rejection.data.total_decided_claims.toLocaleString("en-IN")}
              sub={`${approval.data.claims_in_outcome.toLocaleString("en-IN")} approved`}
              icon={ClipboardCheck}
              color="bg-blue-500"
            />
            <StatCard
              label="Rejection rate"
              value={`${rejection.data.outcome_rate_pct}%`}
              sub={`${rejection.data.claims_in_outcome.toLocaleString("en-IN")} rejected`}
              icon={Percent}
              color="bg-slate-500"
            />
            <StatCard
              label="Top rejection reason"
              value={humanize(rejection.data.primary_reason?.category)}
              sub={rejection.data.primary_reason ? `${rejection.data.primary_reason.share_pct}% of rejections` : undefined}
              icon={XCircle}
              color="bg-slate-700"
            />
            <StatCard
              label="Top approval reason"
              value={humanize(approval.data.primary_reason?.category)}
              sub={approval.data.primary_reason ? `${approval.data.primary_reason.share_pct}% of approvals` : undefined}
              icon={CheckCircle2}
              color="bg-slate-400"
            />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <ReasonBars title="Rejection reasons" data={rejection.data} months={months} fetcher={getRejectionReasons} />
            <ReasonBars title="Approval reasons" data={approval.data} months={months} fetcher={getApprovalReasons} />
          </div>

          <CorrelationPanel data={correlation.data} months={months} />
          <SettlementTrend />
        </>
      )}
    </div>
  );
}
