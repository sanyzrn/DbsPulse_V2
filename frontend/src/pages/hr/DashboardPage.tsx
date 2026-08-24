import { useState } from "react";
import { motion } from "motion/react";
import { useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { apiClient, extractErrorMessage } from "../../api/client";
import { useDashboardOverview, useExpiringContracts, usePipeline } from "../../api/queries";
import { RoleOverviewCards } from "../../components/RoleOverviewCards";
import { StatusBadge } from "../../components/StatusBadge";
import { useToast } from "../../components/Toast";
import { PersonScorecard } from "./PersonScorecard";
import { ReportsSection } from "./ReportsSection";
import { PageHeader } from "../../ui/Card";
import { CountUp, PctBadge, ScoreRing, SuppressedValue } from "../../ui/Meters";
import { EASE_SOFT, TAB_TRANSITION } from "../../ui/motion";
import { DotPlot } from "../../ui/plot";
import { Table } from "../../ui/Table";
import { formatDate } from "../../utils/dates";
import type { EvaluationStatus } from "../../types";

/* ═══════════════════════════════════════════════════════════════════════
   نمودارهای این صفحه تک‌سری‌اند (بزرگی/magnitude) — یک هیو واحد به‌جای گرادیانت
   دورنگهٔ قبلی (قرمز به طوسی تیره) که کدر و شلوغ به‌نظر می‌رسید
   ═══════════════════════════════════════════════════════════════════════ */

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

type DashboardTab = "overview" | "analysis";
type AnalysisTab = "org" | "reports" | "person";

const IS_TAB = (v: string | null): v is DashboardTab => v === "overview" || v === "analysis";
const IS_ANALYSIS_TAB = (v: string | null): v is AnalysisTab =>
  v === "org" || v === "reports" || v === "person";

export function DashboardPage() {
  // تب در نشانی صفحه زندگی می‌کند، نه در state.
  //
  // تحلیلگری که «گزارش‌های تحلیلی» را باز کرده و نشانی را برای مدیرش می‌فرستد،
  // نباید طرف مقابل روی «نمای کلی» بیفتد. رفرش کردن صفحه هم همین‌طور.
  const [params, setParams] = useSearchParams();
  const rawTab = params.get("tab");
  const rawAnalysis = params.get("view");
  const tab: DashboardTab = IS_TAB(rawTab) ? rawTab : "overview";
  const analysisTab: AnalysisTab = IS_ANALYSIS_TAB(rawAnalysis) ? rawAnalysis : "org";

  // `replace` تا دکمهٔ «بازگشت» مرورگر پر از تب‌های میانی نشود؛ کاربر انتظار
  // دارد بازگشت او را از صفحه بیرون ببرد، نه یک تب عقب.
  const setTab = (next: DashboardTab) =>
    setParams(
      (prev) => {
        const p = new URLSearchParams(prev);
        if (next === "overview") p.delete("tab");
        else p.set("tab", next);
        return p;
      },
      { replace: true }
    );

  const setAnalysisTab = (next: AnalysisTab) =>
    setParams(
      (prev) => {
        const p = new URLSearchParams(prev);
        p.set("tab", "analysis");
        if (next === "org") p.delete("view");
        else p.set("view", next);
        return p;
      },
      { replace: true }
    );

  const { data: overview, error: overviewError } = useDashboardOverview();

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
      <div role="tablist" className="inline-flex flex-wrap gap-1 rounded-2xl border border-gray-200 bg-white p-1 shadow-sm">
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
      {/* یک جمله به‌جای سه کارت.
          «کل ارزیابی‌های نهایی‌شده» عیناً همان عددی بود که نوار بالا نشان می‌دهد،
          و «واحدهای سازمانی» یک عدد کمکی است نه یک شاخص. حالا هر سه در یک
          کارت‌اند: عدد اصلی بزرگ، بقیه به‌عنوان زمینهٔ همان عدد. */}
      <motion.div
        className="flex flex-wrap items-center justify-between gap-5 rounded-2xl border border-gray-200 bg-white p-5"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <div>
          <p className="text-sm font-medium text-gray-500">میانگین امتیاز نهایی سازمان</p>
          <p className="mt-1 text-sm text-gray-400">
            بر پایهٔ{" "}
            <span className="font-semibold tabular-nums text-gray-600">
              {overview.total_evaluations.toLocaleString("fa-IR")}
            </span>{" "}
            ارزیابی نهایی‌شده در{" "}
            <span className="font-semibold tabular-nums text-gray-600">
              {overview.by_org_unit.length.toLocaleString("fa-IR")}
            </span>{" "}
            واحد سازمانی
          </p>
        </div>
        <ScoreRing value={overview.avg_final_pct} size={72} />
      </motion.div>

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
              analysisTab === t.key ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-800"
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

      {/* ── کارنامهٔ یک فرد: مقایسه با واحد + رادار + روند، با یک انتخابگر ── */}
      {analysisTab === "person" && <PersonScorecard />}

      {/* ── گزارش‌های تحلیلی فیلترشونده ── */}
      {analysisTab === "reports" && <ReportsSection />}
      </motion.div>
      </motion.div>
      )}
    </div>
  );
}


/** نمایش امتیاز ۰ تا ۵ به‌صورت نوار کوچک تک‌رنگ + عدد. */
function ScoreOutOfFive({ value }: { value: number | null }) {
  // null = سرکوب کوهورت حداقلی (P1-08): داده هست، ولی جمعیتش برای نمایشِ بی‌نام کم است
  if (value === null) return <SuppressedValue />;
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
function BarByOrgUnitCard({
  data,
}: {
  data: { org_unit: string; avg_final_pct: number | null; count: number }[];
}) {
  if (data.length === 0) return null;
  // واحدهای سرکوب‌شده از نمودار کنار گذاشته می‌شوند: میله نمی‌تواند بگوید «پنهان»،
  // و صفر نشان‌دادنشان دروغ است. تعدادشان زیر نمودار اعلام می‌شود.
  const visible = data.filter((u) => u.avg_final_pct !== null);
  const hiddenCount = data.length - visible.length;
  if (visible.length === 0) return null;
  const chartData = visible.map((u) => ({
    key: u.org_unit,
    label: u.org_unit,
    value: u.avg_final_pct!,
    note: `${u.count.toLocaleString("fa-IR")} ارزیابی`,
  }));

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-card">
      <h2 className="mb-1 text-base font-bold text-gray-900">میانگین امتیاز به تفکیک واحد</h2>
      {hiddenCount > 0 && (
        <p className="mb-3 text-xs text-gray-500">
          {hiddenCount.toLocaleString("fa-IR")} واحد به دلیل تعداد کم افراد نمایش داده نشده است
          (میانگینشان عملاً امتیاز فرد است).
        </p>
      )}
      <DotPlot rows={chartData} ariaLabel="میانگین امتیاز به تفکیک واحد سازمانی" />
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

// قیف فقط مسیر پیشرفت است؛ «لغوشده» عمداً در آن نیست (بک‌اند هم برنمی‌گرداند) چون
// پرونده‌ای که به مرحلهٔ بعد نمی‌رود، نرخ عبور قیف را مخدوش می‌کند.
type PipelineStatus = Exclude<EvaluationStatus, "cancelled">;

const PIPELINE_ORDER: PipelineStatus[] = [
  "draft",
  "submitted",
  "hr_approved",
  "deputy_approved",
  "finalized",
];

// نوار هر مرحله. رنگ‌ها همان زنجیرهٔ StatusBadge‌اند تا کاشی و نشان یک زبان
// داشته باشند: خاکستری ← آبی ← نیلی ← کهربایی ← سبز.
const PIPELINE_BAR: Record<PipelineStatus, string> = {
  draft: "bg-gray-300",
  submitted: "bg-blue-300",
  hr_approved: "bg-indigo-300",
  deputy_approved: "bg-amber-300",
  finalized: "bg-green-400",
};

/** قیف گردش‌کار.
 *
 *  پیش از این پنج کاشیِ **هم‌اندازه** بود — یعنی دقیقاً آن چیزی را پنهان می‌کرد
 *  که قرار بود نشان بدهد: کجا پرونده تلنبار شده. حالا هر مرحله یک نوارِ افقی
 *  است که طولش با تعدادش نسبت دارد و مراحل از بالا به پایین ترتیبِ واقعیِ
 *  گردش‌کار را دارند؛ چشم در یک نگاه بلندترین نوار را پیدا می‌کند.
 *
 *  نکته: این اعداد «چند پرونده همین حالا اینجا نشسته‌اند» است، نه جریانِ تجمعی.
 *  به همین دلیل زیرعنوان این را صریح می‌گوید. */
function PipelineCard() {
  const { data: pipeline = [] } = usePipeline();
  const byStatus = new Map(pipeline.map((p) => [p.status, p]));
  const maxCount = Math.max(1, ...PIPELINE_ORDER.map((st) => byStatus.get(st)?.count ?? 0));
  const total = PIPELINE_ORDER.reduce((sum, st) => sum + (byStatus.get(st)?.count ?? 0), 0);

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5">
      <div className="mb-1 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-base font-bold text-gray-900">قیف گردش‌کار</h2>
        <p className="text-xs text-gray-400">
          مجموع <span className="tabular-nums">{total.toLocaleString("fa-IR")}</span> پرونده
        </p>
      </div>
      <p className="mb-4 text-xs text-gray-400">هر پرونده هم‌اکنون در کدام مرحله است</p>

      <ol className="space-y-2">
        {PIPELINE_ORDER.map((status, idx) => {
          const stat = byStatus.get(status);
          const count = stat?.count ?? 0;
          // نوارِ صفر هم یک ردِ نازک می‌گیرد تا مرحله از قلم نیفتد.
          const widthPct = count === 0 ? 0 : Math.max(6, (count / maxCount) * 100);
          return (
            <li key={status} className="flex items-center gap-3">
              <div className="w-32 shrink-0 sm:w-40">
                <StatusBadge status={status} />
              </div>
              <div className="h-8 min-w-0 flex-1 rounded-lg bg-gray-50">
                <motion.div
                  className={`flex h-8 items-center justify-end rounded-lg px-2 ${PIPELINE_BAR[status]}`}
                  initial={{ width: 0 }}
                  animate={{ width: `${widthPct}%` }}
                  transition={{ duration: 0.5, delay: idx * 0.06, ease: EASE_SOFT }}
                />
              </div>
              {/* text-right در RTL یعنی «چسبیده به نوار»: عددها روی یک خط عمودی
                  می‌نشینند، چه تاریخ داشته باشند چه نه. */}
              <div className="flex w-24 shrink-0 items-baseline gap-2 text-right sm:w-36">
                <span className="text-lg font-extrabold tabular-nums text-gray-900">
                  <CountUp value={count} format="plain" />
                </span>
                {stat?.oldest_created_at && status !== "finalized" && count > 0 && (
                  <span className="hidden text-[10px] text-gray-400 sm:inline">
                    از {formatDate(stat.oldest_created_at)}
                  </span>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
