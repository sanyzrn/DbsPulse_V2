import { useState } from "react";
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Area,
  AreaChart,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Bar,
  BarChart,
  LabelList,
} from "recharts";
import { motion } from "motion/react";
import { useQueryClient } from "@tanstack/react-query";
import { apiClient, extractErrorMessage } from "../../api/client";
import {
  useDashboardOverview,
  useExpiringContracts,
  usePipeline,
  usePersonRadar,
  usePersonTrend,
  usePersonnelList,
} from "../../api/queries";
import { RoleOverviewCards } from "../../components/RoleOverviewCards";
import { StatusBadge } from "../../components/StatusBadge";
import { useToast } from "../../components/Toast";
import { ReportsSection } from "./ReportsSection";
import { PageHeader } from "../../ui/Card";
import { CountUp, PctBadge, ScoreRing } from "../../ui/Meters";
import { TAB_TRANSITION } from "../../ui/motion";
import { Table } from "../../ui/Table";
import { formatDate } from "../../utils/dates";
import type { EvaluationStatus } from "../../types";

/* ═══════════════════════════════════════════════════════════════════════
   نمودارهای این صفحه تک‌سری‌اند (بزرگی/magnitude) — یک هیو واحد به‌جای گرادیانت
   دورنگهٔ قبلی (قرمز به طوسی تیره) که کدر و شلوغ به‌نظر می‌رسید
   ═══════════════════════════════════════════════════════════════════════ */
const SERIES_COLOR = "#b61615"; // pulse-600
const GRID_STROKE = "#eef0f4";
const AXIS_STROKE = "#e5e7eb";

const TICK_STYLE = { fontSize: 11, fill: "#6b7280", fontFamily: "Vazirmatn, Tahoma, sans-serif" };
const TOOLTIP_STYLE = {
  direction: "rtl" as const,
  fontFamily: "Vazirmatn, Tahoma, sans-serif",
  fontSize: 12,
  borderRadius: 12,
  border: "1px solid #eef0f4",
  boxShadow: "0 12px 40px rgba(0,0,0,0.12)",
  background: "rgba(255,255,255,0.95)",
  backdropFilter: "blur(8px)",
};

const DASHBOARD_TABS = [
  { key: "overview" as const, label: "نمای کلی" },
  { key: "analysis" as const, label: "تحلیل و گزارش‌ها" },
];

// زیربخش‌های تب «تحلیل و گزارش‌ها» — هر بخش یک زیرتب جدا تا صفحه شلوغ نباشد.
const ANALYSIS_SUBTABS = [
  { key: "org" as const, label: "نمای سازمان" },
  { key: "reports" as const, label: "گزارش‌های تحلیلی" },
  { key: "person" as const, label: "کارنامهٔ فرد" },
];

export function DashboardPage() {
  const [selectedPersonId, setSelectedPersonId] = useState<number | null>(null);
  const [tab, setTab] = useState<"overview" | "analysis">("overview");
  const [analysisTab, setAnalysisTab] = useState<"org" | "reports" | "person">("org");

  const { data: overview, error: overviewError } = useDashboardOverview();
  const { data: personnelPage } = usePersonnelList({ limit: 1000, offset: 0 });
  // React Query خودش پاسخ‌های کهنه (تعویض سریع فرد انتخاب‌شده) را کنار می‌گذارد
  const { data: radar = [] } = usePersonRadar(selectedPersonId);
  const { data: trend = [] } = usePersonTrend(selectedPersonId);
  const personnel = personnelPage?.items ?? [];

  if (overviewError != null)
    return <p className="p-6 text-center text-sm text-red-600">{extractErrorMessage(overviewError)}</p>;
  if (!overview) return <DashboardSkeleton />;

  return (
    <div className="space-y-5">
      <PageHeader
        title="داشبورد منابع انسانی"
        subtitle="خلاصهٔ وضعیت ارزیابی‌ها و گزارش‌های تحلیلی سازمان"
      />

      {/* خلاصهٔ سریع نقش — همیشه بالای صفحه دیده می‌شود */}
      <RoleOverviewCards />

      {/* تب‌ها: نمای کلی (خلاصه) و تحلیل/گزارش‌ها — تا صفحه به‌جای یک اسکرول طولانی و
          شلوغ، به دو بخش تمیز تقسیم شود. */}
      <div role="tablist" className="inline-flex flex-wrap gap-1 rounded-2xl border border-gray-100 bg-white p-1 shadow-sm">
        {DASHBOARD_TABS.map((t) => (
          <button
            key={t.key}
            role="tab"
            aria-selected={tab === t.key}
            onClick={() => setTab(t.key)}
            className={`rounded-xl px-4 py-1.5 text-sm font-medium transition-colors ${
              tab === t.key ? "bg-charcoal-900 text-white" : "text-gray-600 hover:text-gray-900"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "overview" && (
      <motion.div key="overview-tab" {...TAB_TRANSITION} className="space-y-5">
      {/* ── کارت‌های خلاصه بالایی ── */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {/* کل ارزیابی‌ها */}
        <motion.div
          className="flex items-center gap-4 rounded-2xl border border-gray-100 bg-white p-5 shadow-card transition-shadow duration-300 hover:shadow-card-hover"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-pulse-50 text-pulse-600" aria-hidden>
            <svg viewBox="0 0 20 20" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
              <path d="M7 3h6l4 4v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h3z" />
              <path d="M7 11l2 2 4-4" />
            </svg>
          </span>
          <div>
            <p className="text-xs text-gray-500">کل ارزیابی‌های نهایی‌شده</p>
            <p className="mt-0.5 text-2xl font-extrabold tabular-nums text-gray-900">
              <CountUp value={overview.total_evaluations} format="plain" />
            </p>
          </div>
        </motion.div>

        {/* میانگین امتیاز */}
        <motion.div
          className="flex items-center justify-between gap-4 rounded-2xl border border-gray-100 bg-white p-5 shadow-card transition-shadow duration-300 hover:shadow-card-hover"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.05 }}
        >
          <div>
            <p className="text-xs text-gray-500">میانگین امتیاز نهایی</p>
            <p className="mt-0.5 text-sm text-gray-400">در همه ارزیابی‌های نهایی‌شده</p>
          </div>
          <ScoreRing value={overview.avg_final_pct} size={64} />
        </motion.div>

        {/* تعداد واحدها — از by_org_unit */}
        <motion.div
          className="flex items-center gap-4 rounded-2xl border border-gray-100 bg-white p-5 shadow-card transition-shadow duration-300 hover:shadow-card-hover"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.1 }}
        >
          <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gray-100 text-gray-600" aria-hidden>
            <svg viewBox="0 0 20 20" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 7l7-4 7 4-7 4-7-4z" />
              <path d="M3 7v6l7 4 7-4V7" />
            </svg>
          </span>
          <div>
            <p className="text-xs text-gray-500">واحدهای سازمانی</p>
            <p className="mt-0.5 text-2xl font-extrabold tabular-nums text-gray-900">
              <CountUp value={overview.by_org_unit.length} format="plain" />
            </p>
          </div>
        </motion.div>
      </div>

      <PipelineCard />

      <ExpiringContractsCard />
      </motion.div>
      )}

      {tab === "analysis" && (
      <motion.div key="analysis-tab" {...TAB_TRANSITION} className="space-y-5">
      {/* زیرتب‌های تحلیل — سبک‌تر از تب‌های اصلی تا سلسله‌مراتب مشخص باشد */}
      <div role="tablist" className="inline-flex flex-wrap gap-1 rounded-xl border border-gray-100 bg-gray-50 p-1">
        {ANALYSIS_SUBTABS.map((t) => (
          <button
            key={t.key}
            role="tab"
            aria-selected={analysisTab === t.key}
            onClick={() => setAnalysisTab(t.key)}
            className={`rounded-lg px-3.5 py-1.5 text-sm font-medium transition-all duration-300 ${
              analysisTab === t.key ? "bg-white text-pulse-700 shadow-sm" : "text-gray-500 hover:text-gray-800"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* محتوای زیرتب‌ها با تعویض نرم (fade) هنگام جابه‌جایی */}
      <motion.div key={analysisTab} {...TAB_TRANSITION} className="space-y-5">

      {analysisTab === "org" && (
      <div className="space-y-5">
      {/* ── نمودار میله‌ای میانگین به تفکیک واحد ── */}
      <BarByOrgUnitCard data={overview.by_org_unit} />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Table
          title="نمرات هر ارزیاب (مسئول واحد)"
          headers={["ارزیاب", "میانگین", "زیرمجموعه", "ارزیابی"]}
          rows={overview.by_evaluator.map((e) => [
            e.username,
            <PctBadge key="pct" value={e.avg_final_pct} />,
            e.subordinate_count.toLocaleString("fa-IR"),
            e.evaluation_count.toLocaleString("fa-IR"),
          ])}
          animateRows={false}
          emptyMessage="داده‌ای موجود نیست."
        />
        <Table
          title="کمترین میانگین به تفکیک شاخص"
          headers={["شاخص", "میانگین امتیاز (از ۵)"]}
          rows={overview.lowest_by_indicator.map((i) => [
            i.category,
            <ScoreOutOfFive key="score" value={i.avg_score} />,
          ])}
          animateRows={false}
          emptyMessage="داده‌ای موجود نیست."
        />
        <Table
          title="کمترین میانگین به تفکیک واحد"
          headers={["واحد", "میانگین"]}
          rows={overview.lowest_by_unit.map((u) => [
            u.org_unit,
            <PctBadge key="pct" value={u.avg_final_pct} />,
          ])}
          animateRows={false}
          emptyMessage="داده‌ای موجود نیست."
        />
        <Table
          title="کمترین امتیاز به تفکیک فرد"
          headers={["فرد", "امتیاز نهایی"]}
          rows={overview.lowest_by_person.map((p) => [
            p.full_name,
            <PctBadge key="pct" value={p.final_weighted_pct} />,
          ])}
          animateRows={false}
          emptyMessage="داده‌ای موجود نیست."
        />
      </div>
      </div>
      )}

      {/* ── کارت رادار + روند فرد ── */}
      {analysisTab === "person" && (
      <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-card">
        <h2 className="mb-3 text-base font-bold text-gray-900">نمودار رادار شایستگی و روند فرد</h2>
        <div className="relative mb-4">
          <select
            className="w-full appearance-none rounded-xl border border-gray-200 bg-gray-100 px-4 py-2.5 pl-10 text-sm text-gray-700 outline-none transition-colors duration-150 focus:border-pulse-500 focus:bg-white sm:w-80"
            value={selectedPersonId ?? ""}
            onChange={(e) => setSelectedPersonId(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">— انتخاب فرد —</option>
            {personnel.map((p) => (
              <option key={p.id} value={p.id}>
                {p.full_name}
              </option>
            ))}
          </select>
          <svg viewBox="0 0 20 20" className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M6 8l4 4 4-4" />
          </svg>
        </div>

        {selectedPersonId && (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div>
              <h3 className="mb-3 text-sm font-semibold text-gray-600">میانگین امتیاز هر شاخص (از ۵)</h3>
              <div style={{ height: 320 }}>
                {radar.length === 0 ? (
                  <p className="pt-20 text-center text-sm text-gray-400">داده‌ای برای این فرد یافت نشد.</p>
                ) : (
                  <ResponsiveContainer>
                    <RadarChart data={radar} margin={{ top: 12, right: 24, bottom: 12, left: 24 }}>
                      <defs>
                        <linearGradient id="radar-fill" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor={SERIES_COLOR} stopOpacity={0.28} />
                          <stop offset="100%" stopColor={SERIES_COLOR} stopOpacity={0.06} />
                        </linearGradient>
                      </defs>
                      <PolarGrid stroke={GRID_STROKE} />
                      <PolarAngleAxis dataKey="category" tick={{ ...TICK_STYLE, fontSize: 10 }} />
                      <PolarRadiusAxis domain={[0, 5]} tickCount={6} tick={TICK_STYLE} stroke={GRID_STROKE} axisLine={false} />
                      <Radar
                        dataKey="avg_score"
                        name="میانگین امتیاز"
                        stroke={SERIES_COLOR}
                        strokeWidth={2}
                        fill="url(#radar-fill)"
                        dot={{ r: 3.5, fill: SERIES_COLOR, strokeWidth: 0 }}
                      />
                      <Tooltip contentStyle={TOOLTIP_STYLE} formatter={tooltipNumber} />
                    </RadarChart>
                  </ResponsiveContainer>
                )}
              </div>
            </div>
            <div>
              <h3 className="mb-3 text-sm font-semibold text-gray-600">روند امتیاز نهایی (٪)</h3>
              <div style={{ height: 320 }}>
                {trend.length === 0 ? (
                  <p className="pt-20 text-center text-sm text-gray-400">روندی برای این فرد ثبت نشده است.</p>
                ) : (
                  <ResponsiveContainer>
                    <AreaChart data={trend} margin={{ top: 12, right: 16, bottom: 12, left: 0 }}>
                      <defs>
                        <linearGradient id="trend-fill" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor={SERIES_COLOR} stopOpacity={0.22} />
                          <stop offset="100%" stopColor={SERIES_COLOR} stopOpacity={0.02} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="4 4" stroke={GRID_STROKE} vertical={false} />
                      <XAxis dataKey="evaluation_code" tick={TICK_STYLE} tickLine={false} axisLine={{ stroke: AXIS_STROKE }} />
                      <YAxis domain={[0, 100]} tick={TICK_STYLE} tickLine={false} axisLine={false} width={36} />
                      <Tooltip contentStyle={TOOLTIP_STYLE} formatter={tooltipNumber} />
                      <Area
                        type="monotone"
                        dataKey="final_weighted_pct"
                        name="امتیاز نهایی"
                        stroke={SERIES_COLOR}
                        strokeWidth={2.5}
                        fill="url(#trend-fill)"
                        dot={{ r: 4, fill: "#fff", strokeWidth: 2.5, stroke: SERIES_COLOR }}
                        activeDot={{ r: 6, fill: SERIES_COLOR, strokeWidth: 2, stroke: "#fff" }}
                        animationDuration={1200}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
      )}

      {/* ── گزارش‌های تحلیلی فیلترشونده ── */}
      {analysisTab === "reports" && <ReportsSection />}
      </motion.div>
      </motion.div>
      )}
    </div>
  );
}

function tooltipNumber(value: unknown): string {
  return typeof value === "number" ? value.toLocaleString("fa-IR") : String(value);
}

/** نمایش امتیاز ۰ تا ۵ به‌صورت نوار کوچک تک‌رنگ + عدد. */
function ScoreOutOfFive({ value }: { value: number }) {
  const pct = Math.max(0, Math.min(100, (value / 5) * 100));
  const color = pct >= 70 ? "bg-green-500" : pct >= 50 ? "bg-amber-500" : "bg-red-500";
  return (
    <span className="inline-flex items-center gap-2">
      <span className="h-1.5 w-16 overflow-hidden rounded-full bg-gray-100">
        <motion.span
          className={`block h-full rounded-full ${color}`}
          initial={{ width: 0 }}
          whileInView={{ width: `${pct}%` }}
          viewport={{ once: true }}
          transition={{ duration: 0.8, ease: "easeOut" }}
        />
      </span>
      <span className="text-xs font-semibold tabular-nums text-gray-700">
        {value.toLocaleString("fa-IR")}
      </span>
    </span>
  );
}

/** اسکلتون بارگذاری داشبورد. */
function DashboardSkeleton() {
  return (
    <div className="space-y-5">
      <div className="skeleton h-16 w-64" />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <div key={i} className="skeleton h-24" />
        ))}
      </div>
      <div className="skeleton h-40" />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="skeleton h-48" />
        ))}
      </div>
    </div>
  );
}

/** جدول مدرن با هدر گرادیانت و هاور. */
/** نمودار میله‌ای میانگین به تفکیک واحد. */
function BarByOrgUnitCard({ data }: { data: { org_unit: string; avg_final_pct: number; count: number }[] }) {
  if (data.length === 0) return null;
  const chartData = data.map((u) => ({
    name: u.org_unit,
    میانگین: Math.round(u.avg_final_pct),
  }));

  return (
    <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-card">
      <h2 className="mb-3 text-base font-bold text-gray-900">میانگین امتیاز به تفکیک واحد</h2>
      <div style={{ height: Math.max(220, data.length * 48) }}>
        <ResponsiveContainer>
          <BarChart data={chartData} layout="vertical" margin={{ top: 4, right: 24, bottom: 4, left: 8 }}>
            <CartesianGrid strokeDasharray="4 4" stroke={GRID_STROKE} horizontal={false} />
            <XAxis type="number" domain={[0, 100]} tick={TICK_STYLE} tickLine={false} axisLine={{ stroke: AXIS_STROKE }} />
            <YAxis type="category" dataKey="name" tick={{ ...TICK_STYLE, fontSize: 11 }} tickLine={false} axisLine={false} width={90} />
            <Tooltip contentStyle={TOOLTIP_STYLE} formatter={tooltipNumber} cursor={{ fill: "rgba(107,114,128,0.06)" }} />
            <Bar dataKey="میانگین" radius={[0, 6, 6, 0]} fill={SERIES_COLOR} animationDuration={1000}>
              <LabelList
                dataKey="میانگین"
                position="right"
                formatter={(v) => (v == null ? "" : Number(v).toLocaleString("fa-IR"))}
                // باگ RTL: text-anchor="start" که Recharts برای position="right" تولید می‌کند،
                // با جهت ارثی rtl صفحه (html dir="rtl") به‌جای «شروع از x و ادامه به راست»
                // به «پایان در x» تفسیر می‌شود؛ برچسب به‌جای فاصله از میله، داخل خودِ میله
                // می‌افتد. direction:ltr فقط روی همین برچسب، بدون اثر روی برچسب‌های محور.
                style={{ fontSize: 11, fill: "#6b7280", fontFamily: "Vazirmatn, Tahoma, sans-serif", direction: "ltr" }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function ExpiringContractsCard() {
  const [days, setDays] = useState(60);
  const [running, setRunning] = useState(false);
  const { data: contracts = [] } = useExpiringContracts(days);
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();

  async function runReminders() {
    setRunning(true);
    try {
      const { data } = await apiClient.post<{
        contract_expiry: number;
        sla_reminder: number;
        improvement_review: number;
      }>("/admin/run-scheduled-jobs");
      // شمارش هر سه نوع یادآوری (قبلاً improvement_review از مجموع جا می‌افتاد)
      const total = data.contract_expiry + data.sla_reminder + data.improvement_review;
      await queryClient.invalidateQueries({ queryKey: ["notifications"] });
      showSuccess(
        total > 0
          ? `${total.toLocaleString("fa-IR")} یادآوری جدید برای کاربران ذی‌ربط ارسال شد`
          : "همه چیز به‌روز است؛ یادآوری جدیدی لازم نبود"
      );
    } catch (err) {
      showError(extractErrorMessage(err));
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="rounded-2xl border-2 border-amber-100 bg-white p-5 shadow-card">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-base font-bold text-gray-900">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-amber-50 text-amber-600">
            <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="10" cy="10" r="7" />
              <path d="M10 6v4l3 2" />
            </svg>
          </span>
          قراردادهای رو به انقضا
        </h2>
        <div className="flex items-center gap-2">
          <button
            onClick={runReminders}
            disabled={running}
            className="rounded-xl border border-gray-200 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 shadow-sm transition-all duration-200 hover:bg-gray-50 hover:shadow-md disabled:opacity-50"
          >
            {running ? "در حال بررسی…" : "بررسی و ارسال یادآوری‌ها"}
          </button>
          <div className="relative">
            <select
              className="appearance-none rounded-xl border border-gray-200 bg-gray-100 px-3 py-1.5 pl-8 text-sm text-gray-700 outline-none transition-colors duration-150 focus:border-pulse-500 focus:bg-white"
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
            >
              {[30, 60, 90, 180].map((d) => (
                <option key={d} value={d}>
                  {d.toLocaleString("fa-IR")} روز آینده
                </option>
              ))}
            </select>
            <svg viewBox="0 0 20 20" className="pointer-events-none absolute left-2 top-1/2 h-3 w-3 -translate-y-1/2 text-gray-400" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M6 8l4 4 4-4" />
            </svg>
          </div>
        </div>
      </div>
      {contracts.length === 0 ? (
        <p className="py-6 text-center text-sm text-gray-400">در این بازه قراردادی رو به انقضا نیست.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                <th className="px-3 py-2 text-right text-xs font-semibold text-gray-600">نام</th>
                <th className="px-3 py-2 text-right text-xs font-semibold text-gray-600">واحد</th>
                <th className="px-3 py-2 text-right text-xs font-semibold text-gray-600">پایان قرارداد</th>
                <th className="px-3 py-2 text-right text-xs font-semibold text-gray-600">باقی‌مانده</th>
                <th className="px-3 py-2 text-right text-xs font-semibold text-gray-600">وضعیت ارزیابی</th>
              </tr>
            </thead>
            <tbody>
              {contracts.map((c) => (
                <tr key={c.personnel_id} className="border-b border-gray-50 transition-colors last:border-0 hover:bg-amber-50/30">
                  <td className="px-3 py-2.5 text-gray-700">{c.full_name}</td>
                  <td className="px-3 py-2.5 text-gray-500">{c.org_unit}</td>
                  <td className="px-3 py-2.5 text-gray-500">{formatDate(c.contract_end_date)}</td>
                  <td className={`px-3 py-2.5 ${c.days_remaining <= 15 ? "font-bold text-red-600" : "text-gray-700"}`}>
                    {c.days_remaining < 0
                      ? `${Math.abs(c.days_remaining).toLocaleString("fa-IR")} روز گذشته`
                      : `${c.days_remaining.toLocaleString("fa-IR")} روز`}
                  </td>
                  <td className="px-3 py-2.5">
                    {c.has_open_evaluation ? (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-medium text-blue-700">
                        <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-blue-500" />
                        در جریان
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 rounded-full bg-red-50 px-2.5 py-0.5 text-xs font-medium text-red-700">
                        <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-red-500" />
                        آغاز نشده
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

const PIPELINE_ORDER: EvaluationStatus[] = [
  "draft",
  "submitted",
  "hr_approved",
  "deputy_approved",
  "finalized",
];

// رنگ هر مرحله قیف — از خاکستری به سبز
const PIPELINE_COLORS: Record<EvaluationStatus, string> = {
  draft: "from-gray-300 to-gray-400",
  submitted: "from-blue-400 to-blue-500",
  hr_approved: "from-pulse-400 to-pulse-500",
  deputy_approved: "from-pulse-violet-400 to-pulse-violet-500",
  finalized: "from-green-400 to-green-500",
};

function PipelineCard() {
  const { data: pipeline = [] } = usePipeline();
  const byStatus = new Map(pipeline.map((p) => [p.status, p]));
  const maxCount = Math.max(1, ...pipeline.map((p) => p.count));

  return (
    <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-card">
      <h2 className="mb-4 text-base font-bold text-gray-900">قیف گردش‌کار (همه پرونده‌ها)</h2>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {PIPELINE_ORDER.map((status, idx) => {
          const stat = byStatus.get(status);
          const count = stat?.count ?? 0;
          const widthPct = (count / maxCount) * 100;
          return (
            <motion.div
              key={status}
              className="relative overflow-hidden rounded-2xl border border-gray-100 bg-gray-50/50 p-3 text-center"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.3, delay: idx * 0.05 }}
            >
              {/* نوار گرادیانت پس‌زمینه بر اساس نسبت */}
              <div
                className={`absolute inset-x-0 bottom-0 bg-gradient-to-t ${PIPELINE_COLORS[status]} opacity-10`}
                style={{ height: `${widthPct}%` }}
              />
              <div className="relative">
                <StatusBadge status={status} />
                <p className="mt-2 text-2xl font-extrabold tabular-nums text-gray-900">
                  <CountUp value={count} format="plain" />
                </p>
                {stat?.oldest_created_at && status !== "finalized" && count > 0 && (
                  <p className="mt-1 text-[10px] text-gray-400">
                    قدیمی‌ترین: {formatDate(stat.oldest_created_at)}
                  </p>
                )}
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
