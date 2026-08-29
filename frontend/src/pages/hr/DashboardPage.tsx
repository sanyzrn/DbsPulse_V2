import { useState } from "react";
import { motion } from "motion/react";
import { useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { apiClient, extractErrorMessage } from "../../api/client";
import {
  useDashboardOverview,
  useExpiringContracts,
  usePeriodTrend,
  useSites,
} from "../../api/queries";
import { PeriodTrendChart } from "../../components/PeriodTrendChart";
import { RoleOverviewCards } from "../../components/RoleOverviewCards";
import { StageStatusCard } from "../../components/StageStatusCard";
import { PaginationControls } from "../../components/PaginationControls";
import { useToast } from "../../components/Toast";
import { PersonScorecard } from "./PersonScorecard";
import { ReportsSection } from "./ReportsSection";
import { FilterSelect, PageHeader } from "../../ui/Card";
import { PctBadge, ScoreRing, SuppressedValue } from "../../ui/Meters";
import { TAB_TRANSITION } from "../../ui/motion";
import { Table } from "../../ui/Table";
import { formatDate } from "../../utils/dates";
import type {
  DashboardOverview as DashboardOverviewData,
  UnitStat as UnitStatData,
  IndicatorStat as IndicatorStatData,
  PersonStat as PersonStatData,
} from "../../types";

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

  // فیلتر محل در نشانی صفحه زندگی می‌کند، مثل خودِ تب — تا نشانیِ فرستاده‌شده
  // همان چیزی را نشان بدهد که فرستنده می‌دید.
  const siteFilter = params.get("site") ?? "";
  const setSiteFilter = (next: string) =>
    setParams(
      (prev) => {
        const p = new URLSearchParams(prev);
        if (next) p.set("site", next);
        else p.delete("site");
        return p;
      },
      { replace: true }
    );
  const { data: overview, error: overviewError } = useDashboardOverview(siteFilter || undefined);

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
      {/* «سه کارت اولیه» این‌جا بود و برداشته شد.
          آن سه (کل ارزیابی‌های نهایی‌شده، میانگین، تعداد واحدها) اول به یک کارت
          خلاصه شدند و حالا کلاً رفته‌اند: هر سه عدد جای دیگری هستند — نوار بالای
          صفحه و «نمای سازمان» — و نمای کلی جایی است که باید بگوید *چه کاری مانده*،
          نه اینکه میانگین سازمان چند است. */}
      <StageStatusCard />

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
      <SiteFilterBar value={siteFilter} onChange={setSiteFilter} />

      {/* ── سه عددی که «سازمان چطور است» را در یک نگاه می‌گویند ── */}
      <OrgSummaryCard overview={overview} />

      {/* ── روند میانگین سازمان در طول دوره‌ها ── */}
      <PeriodTrendCard site={siteFilter} />

      {/* ── نمودار میله‌ای میانگین به تفکیک واحد ── */}
      <BarByOrgUnitCard data={overview.by_org_unit} />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <IndicatorRankCard
          title="تحلیل شایستگی‌ها"
          subtitle="شاخص‌های عمومی (رفتاری)"
          weakest={overview.lowest_by_indicator}
          strongest={overview.highest_by_indicator}
        />
        <IndicatorRankCard
          title="ارزیابی تخصصی"
          subtitle="شاخص‌های تخصصی هر شغل"
          weakest={overview.lowest_by_specialized_indicator}
          strongest={overview.highest_by_specialized_indicator}
        />
        <Table
          title="تحلیل الگوی امتیازدهی ارزیابان"
          headers={["ارزیاب", "میانگین", "زیرمجموعه", "ارزیابی"]}
          rows={overview.by_evaluator.map((e) => [
            // نامِ آدم بالا، نام کاربری زیرش. جدولی که فقط «sup_it» را نشان
            // می‌دهد، از خواننده می‌خواهد نام‌های کاربری را حفظ باشد.
            <div key="who">
              <p className="font-medium text-gray-900">{e.full_name ?? e.username}</p>
              {e.full_name && (
                <p dir="ltr" className="text-left text-[11px] text-gray-400">{e.username}</p>
              )}
            </div>,
            <PctBadge key="pct" value={e.avg_final_pct} />,
            e.subordinate_count.toLocaleString("fa-IR"),
            e.evaluation_count.toLocaleString("fa-IR"),
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
      </div>

      <PeopleNeedingAttentionCard people={overview.lowest_by_person} />
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


/** روند میانگین سازمان در طول دوره‌های ارزیابی.
 *
 *  بقیهٔ این صفحه «الان چطوریم» را می‌گوید. این یکی تنها جایی است که می‌گوید
 *  «داریم بهتر می‌شویم یا بدتر» — و همان چیزی است که از یک گزارش سالانه انتظار
 *  می‌رود.
 */
function PeriodTrendCard({ site }: { site: string }) {
  const { data = [], isPending } = usePeriodTrend(site || undefined);
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5">
      <div className="mb-3">
        <h3 className="text-base font-bold text-gray-900">روند میانگین سازمان</h3>
        <p className="mt-0.5 text-xs text-gray-400">میانگین امتیاز نهایی در هر دورهٔ ارزیابی</p>
      </div>
      {isPending ? (
        <div className="skeleton h-64" aria-hidden />
      ) : (
        <PeriodTrendChart data={data} />
      )}
    </div>
  );
}

/** فیلتر محل برای کل نمای سازمان.
 *
 *  قرص‌ها و نه یک `select`: سه گزینه‌اند و همیشه همان سه. یک منوی بازشو برای سه
 *  گزینه، یک کلیک اضافه می‌گیرد تا چیزی را نشان بدهد که جا داشت همان اول دیده
 *  شود.
 */
function SiteFilterBar({ value, onChange }: { value: string; onChange: (site: string) => void }) {
  const { data: sites = [] } = useSites(true);
  if (sites.length === 0) return null;
  const options = [{ key: "", label: "کل سازمان" }, ...sites.map((s) => ({ key: s, label: s }))];
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs font-medium text-gray-500">محل:</span>
      <div role="tablist" className="inline-flex flex-wrap gap-1 rounded-xl border border-gray-200 bg-gray-50 p-1">
        {options.map((option) => (
          <button
            key={option.key}
            role="tab"
            aria-selected={value === option.key}
            onClick={() => onChange(option.key)}
            className={`rounded-lg px-3 py-1 text-xs font-medium transition-colors ${
              value === option.key
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-500 hover:text-gray-800"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}

/** سه عددی که «سازمان چطور است» را در یک نگاه می‌گویند.
 *
 *  میانگین به‌تنهایی توزیع را پنهان می‌کند: سازمانی که نصفش عالی و نصفش ضعیف
 *  است، همان میانگینِ سازمانی را دارد که همه‌اش متوسط‌اند — و آن دو وضعیت هیچ
 *  ربطی به هم ندارند. دو درصدِ کناری همان توزیع را برمی‌گردانند.
 *
 *  مرزها از خودِ «طرح نمره‌دهی» می‌آیند و کنار عدد نوشته می‌شوند، وگرنه «مطلوب»
 *  کلمه‌ای است که هرکس معنای خودش را از آن می‌فهمد.
 */
function OrgSummaryCard({ overview }: { overview: DashboardOverviewData }) {
  const mix = overview.outcome_mix;
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      <div className="flex items-center justify-between gap-4 rounded-2xl border border-gray-200 bg-white p-5">
        <div>
          <p className="text-sm font-medium text-gray-500">میانگین امتیاز کل سازمان</p>
          <p className="mt-1 text-xs text-gray-400">
            بر پایهٔ {overview.total_evaluations.toLocaleString("fa-IR")} ارزیابی نهایی‌شده
          </p>
        </div>
        <ScoreRing value={overview.avg_final_pct} size={64} />
      </div>

      <SharePanel
        label="افراد با عملکرد مطلوب"
        value={mix.strong_pct}
        hint={`امتیاز ${mix.strong_threshold_pct.toLocaleString("fa-IR")}٪ و بالاتر`}
        people={mix.people_counted}
        bar="bg-green-500"
        text="text-green-700"
      />
      <SharePanel
        label="افراد نیازمند بهبود"
        value={mix.needs_improvement_pct}
        hint={`امتیاز ${mix.improvement_threshold_pct.toLocaleString("fa-IR")}٪ و پایین‌تر — واجد برنامهٔ بهبود`}
        people={mix.people_counted}
        bar="bg-amber-500"
        text="text-amber-700"
      />
    </div>
  );
}

function SharePanel({
  label,
  value,
  hint,
  people,
  bar,
  text,
}: {
  label: string;
  value: number | null;
  hint: string;
  people: number;
  bar: string;
  text: string;
}) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5">
      <p className="text-sm font-medium text-gray-500">{label}</p>
      <p className={`mt-1 text-3xl font-extrabold tabular-nums ${text}`}>
        {value === null ? "—" : `${value.toLocaleString("fa-IR", { maximumFractionDigits: 1 })}٪`}
      </p>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-gray-100">
        <div className={`h-full rounded-full ${bar}`} style={{ width: `${value ?? 0}%` }} />
      </div>
      <p className="mt-2 text-[11px] text-gray-400">{hint}</p>
      <p className="text-[11px] text-gray-400">
        از {people.toLocaleString("fa-IR")} نفرِ دارای ارزیابی نهایی‌شده
      </p>
    </div>
  );
}

/** ضعیف‌ترین و قوی‌ترین شاخص‌ها، در دو تب.
 *
 *  فهرستی که فقط ضعف نشان می‌دهد هر سازمانی را بیمار جلوه می‌دهد و هیچ‌وقت
 *  نمی‌گوید کجا باید همان کار را تکرار کرد. دو تب و نه دو جدولِ کنار هم: فضای
 *  یکسان، و خواننده هر بار یکی را می‌خواند نه هر دو را.
 */
function IndicatorRankCard({
  title,
  subtitle,
  weakest,
  strongest,
}: {
  title: string;
  subtitle: string;
  weakest: IndicatorStatData[];
  strongest: IndicatorStatData[];
}) {
  const [tab, setTab] = useState<"weak" | "strong">("weak");
  const rows = tab === "weak" ? weakest : strongest;

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-base font-bold text-gray-900">{title}</h3>
          <p className="mt-0.5 text-xs text-gray-400">{subtitle}</p>
        </div>
        <div role="tablist" className="inline-flex gap-1 rounded-xl border border-gray-200 bg-gray-50 p-1">
          {([
            { key: "weak", label: "ضعیف‌ترین" },
            { key: "strong", label: "قوی‌ترین" },
          ] as const).map((t) => (
            <button
              key={t.key}
              role="tab"
              aria-selected={tab === t.key}
              onClick={() => setTab(t.key)}
              className={`rounded-lg px-3 py-1 text-xs font-medium transition-colors ${
                tab === t.key ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-800"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>
      <Table
        bordered={false}
        cellAlign="top"
        headers={["شاخص", "میانگین امتیاز (از ۵)"]}
        rows={rows.map((i) => [
          // دسته بالا، شرح زیرش: دو شاخص می‌توانند یک دسته داشته باشند و
          // فهرستی که فقط دسته را نشان بدهد، دو ردیفِ کاملاً یکسان می‌سازد.
          <div key="what">
            <p className="font-medium text-gray-900">{i.category}</p>
            {i.description && (
              <p className="mt-0.5 text-xs leading-relaxed text-gray-400">{i.description}</p>
            )}
          </div>,
          <ScoreOutOfFive key="score" value={i.avg_score} />,
        ])}
        animateRows={false}
        emptyMessage="داده‌ای موجود نیست."
      />
    </div>
  );
}

/** افراد نیازمند توجه، با فیلترِ محل.
 *
 *  عنوانِ قبلی «کمترین امتیاز به تفکیک فرد» بود — که توصیفِ کوئری است، نه
 *  کاری که باید انجام شود. این فهرست برای این خوانده می‌شود که کسی سراغِ این
 *  آدم‌ها برود.
 */
function PeopleNeedingAttentionCard({ people }: { people: PersonStatData[] }) {
  const { data: sites = [] } = useSites(true);
  const [site, setSite] = useState("");
  const visible = site ? people.filter((p) => p.site === site) : people;

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-base font-bold text-gray-900">افراد نیازمند توجه</h3>
          <p className="mt-0.5 text-xs text-gray-400">
            پایین‌ترین امتیازهای نهایی‌شده — کسانی که گفت‌وگو با آن‌ها بیشترین اثر را دارد
          </p>
        </div>
        <FilterSelect value={site} onChange={setSite} aria-label="فیلتر محل">
          <option value="">همهٔ محل‌ها</option>
          {sites.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </FilterSelect>
      </div>
      <Table
        bordered={false}
        headers={["فرد", "واحد", "امتیاز نهایی"]}
        rows={visible.slice(0, 10).map((p) => [
          p.full_name,
          <span key="unit" className="text-gray-500">
            {p.org_unit}
          </span>,
          <PctBadge key="pct" value={p.final_weighted_pct} />,
        ])}
        animateRows={false}
        emptyMessage={site ? "در این محل کسی با ارزیابی نهایی‌شده نیست." : "داده‌ای موجود نیست."}
      />
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
function BarByOrgUnitCard({ data }: { data: UnitStatData[] }) {
  if (data.length === 0) return null;
  // واحدهای سرکوب‌شده از نمودار کنار گذاشته می‌شوند: میله نمی‌تواند بگوید «پنهان»،
  // و صفر نشان‌دادنشان دروغ است. تعدادشان زیر نمودار اعلام می‌شود.
  const visible = data.filter((u) => u.avg_final_pct !== null);
  const hiddenCount = data.length - visible.length;
  if (visible.length === 0) return null;

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5">
      <h2 className="mb-1 text-base font-bold text-gray-900">
        امتیاز و مقایسهٔ واحدهای سازمانی
      </h2>
      <p className="mb-4 text-xs text-gray-400">
        امتیاز کل، و تفکیکش به دو بخشِ فرم. واحدی که کلش خوب است ممکن است در یکی از دو بخش
        ضعیف باشد — و عددِ کل آن را پنهان می‌کند.
      </p>
      {hiddenCount > 0 && (
        <p className="mb-3 text-xs text-gray-500">
          {hiddenCount.toLocaleString("fa-IR")} واحد به دلیل تعداد کم افراد نمایش داده نشده است
          (میانگینشان عملاً امتیاز فرد است).
        </p>
      )}

      <ul className="space-y-3">
        {visible.map((unit) => (
          <li key={unit.org_unit} className="border-b border-gray-100 pb-3 last:border-0 last:pb-0">
            <div className="mb-1.5 flex flex-wrap items-baseline justify-between gap-2">
              <p className="text-sm font-medium text-gray-900">{unit.org_unit}</p>
              <p className="text-[11px] text-gray-400">
                {unit.count.toLocaleString("fa-IR")} ارزیابی
              </p>
            </div>
            <div className="space-y-1">
              <UnitBar label="امتیاز کل" value={unit.avg_final_pct} bar="bg-charcoal-800" bold />
              <UnitBar label="عمومی (رفتاری)" value={unit.avg_general_pct} bar="bg-blue-400" />
              <UnitBar label="تخصصی" value={unit.avg_specialized_pct} bar="bg-indigo-400" />
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function UnitBar({
  label,
  value,
  bar,
  bold,
}: {
  label: string;
  value: number | null;
  bar: string;
  bold?: boolean;
}) {
  return (
    <div className="flex items-center gap-2.5">
      <span className={`w-28 shrink-0 text-[11px] ${bold ? "font-semibold text-gray-700" : "text-gray-500"}`}>
        {label}
      </span>
      <span className="h-2 min-w-0 flex-1 overflow-hidden rounded-full bg-gray-100">
        {value !== null && (
          <span className={`block h-full rounded-full ${bar}`} style={{ width: `${value}%` }} />
        )}
      </span>
      <span
        className={`w-12 shrink-0 text-left text-xs tabular-nums ${
          bold ? "font-bold text-gray-900" : "text-gray-500"
        }`}
      >
        {value === null ? "—" : `${value.toLocaleString("fa-IR", { maximumFractionDigits: 1 })}٪`}
      </span>
    </div>
  );
}

function ExpiringContractsCard() {
  const [days, setDays] = useState(60);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(10);
  const [running, setRunning] = useState(false);
  const { data: contracts = [] } = useExpiringContracts(days);
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const totalPages = Math.max(1, Math.ceil(contracts.length / pageSize));
  const safePage = Math.min(page, totalPages - 1);
  const visibleContracts = contracts.slice(safePage * pageSize, (safePage + 1) * pageSize);

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
    <div className="rounded-2xl border-2 border-amber-100 bg-white p-5">
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
              className="appearance-none rounded-xl border border-gray-200 bg-gray-100 px-3 py-1.5 pl-8 text-sm text-gray-700 outline-none transition-colors duration-150 focus:border-gray-900 focus:bg-white"
              value={days}
              onChange={(e) => {
                setDays(Number(e.target.value));
                setPage(0);
              }}
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
      {/* همان `Table` مشترک و نه یک جدول دستی: این‌طور زیر md خودبه‌خود کارت
          می‌شود. نسخهٔ دستی روی موبایل «۱۴ شهریور ۱۴۰۵» را به سه سطر می‌شکست. */}
      <Table
        bordered={false}
        headers={["نام", "واحد", "پایان قرارداد", "باقی‌مانده", "وضعیت ارزیابی"]}
        rowKeys={visibleContracts.map((c) => c.personnel_id)}
        animateRows={false}
        emptyMessage="در این بازه قراردادی رو به انقضا نیست."
        rows={visibleContracts.map((c) => [
          c.full_name,
          <span key="unit" className="text-gray-500">
            {c.org_unit}
          </span>,
          <span key="end" className="whitespace-nowrap text-gray-500">
            {formatDate(c.contract_end_date)}
          </span>,
          <span
            key="left"
            className={`whitespace-nowrap ${
              c.days_remaining <= 15 ? "font-bold text-red-600" : "text-gray-700"
            }`}
          >
            {c.days_remaining < 0
              ? `${Math.abs(c.days_remaining).toLocaleString("fa-IR")} روز گذشته`
              : `${c.days_remaining.toLocaleString("fa-IR")} روز`}
          </span>,
          c.has_open_evaluation ? (
            <span key="state" className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-medium text-blue-700">
              <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-blue-500" />
              در جریان
            </span>
          ) : (
            <span key="state" className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-full bg-red-50 px-2.5 py-0.5 text-xs font-medium text-red-700">
              <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-red-500" />
              آغاز نشده
            </span>
          ),
        ])}
      />
      <PaginationControls
        page={safePage}
        totalPages={totalPages}
        totalCount={contracts.length}
        pageSize={pageSize}
        onPageSizeChange={(size) => {
          setPageSize(size);
          setPage(0);
        }}
        onPageChange={setPage}
      />
    </div>
  );
}

