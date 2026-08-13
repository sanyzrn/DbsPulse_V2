import { useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  useDebouncedValue,
  useEmployeeVsUnit,
  useIndicatorBreakdown,
  useIndicators,
  useOrgUnits,
  usePeriods,
  usePersonnelList,
  useReportSummary,
} from "../../api/queries";
import { ChartDownloadCard } from "../../components/ChartDownloadCard";
import { ExcelExportButton } from "../../components/ExcelExportButton";
import { Card, EmptyState, FilterSelect, PageHeader, TableSkeleton } from "../../ui/Card";
import { CountUp, ScoreRing } from "../../ui/Meters";
import { JalaliDatePicker } from "../../ui/JalaliDatePicker";
import type { ReportFilters } from "../../types";

const SERIES_COLOR = "#b61615";
const UNIT_COLOR = "#6b7280";
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
  background: "rgba(255,255,255,0.97)",
};

function faNum(value: unknown): string {
  return typeof value === "number" ? value.toLocaleString("fa-IR") : String(value);
}

/** پیام خالی‌بودن نمودار، وقتی همهٔ ردیف‌ها به‌خاطر سرکوب کوهورت حذف شده‌اند.
 *
 * «داده‌ای وجود ندارد» در این حالت دروغ است: داده هست، ولی جمعیتش برای نمایش
 * بی‌نام کوچک است. این دو حالت باید در UI از هم جدا باشند، وگرنه HR فکر می‌کند
 * فیلترش اشتباه بوده و دنبال داده‌ای می‌گردد که همان‌جاست. */
function chartEmptyMessage(totalRows: number, visibleRows: number, fallback: string): string {
  if (totalRows > 0 && visibleRows === 0)
    return "داده هست، ولی تعداد افراد هر گروه کمتر از حد لازم برای نمایش میانگین بی‌نام است.";
  return fallback;
}

/** شرح شاخص‌ها یک جملهٔ کامل است و محور نمودار جا ندارد؛ متن کامل در tooltip می‌آید. */
function truncateLabel(text: string, max = 42): string {
  return text.length <= max ? text : `${text.slice(0, max - 1).trimEnd()}…`;
}

const inputClass =
  "w-full rounded-xl border border-gray-200 bg-gray-100 px-3 py-1.5 text-sm text-gray-700 outline-none transition-colors duration-150 focus:border-pulse-500 focus:bg-white";

/** بخش گزارش‌های تحلیلی فیلترشونده — جدا از کارت‌های خلاصهٔ همیشگیِ بالای داشبورد.
 * همهٔ فیلترها ترکیب‌پذیرند و روی همهٔ نمودارها/خروجی‌های این بخش اعمال می‌شوند. */
export function ReportsSection() {
  const [filters, setFilters] = useState<ReportFilters>({});
  const [personnelSearch, setPersonnelSearch] = useState("");
  const debouncedPersonnelSearch = useDebouncedValue(personnelSearch);
  const [selectedIndicatorId, setSelectedIndicatorId] = useState<number | null>(null);

  const { data: orgUnits = [] } = useOrgUnits(true);
  const { data: periods = [] } = usePeriods();
  const { data: indicators = [] } = useIndicators({ includeInactive: true });
  // ترتیب خودِ سرور (section، سپس display_order) حفظ می‌شود؛ Map ترتیب درج را نگه می‌دارد.
  const indicatorGroups = Array.from(
    indicators
      .reduce((groups, i) => {
        const bucket = groups.get(i.category);
        if (bucket) bucket.push(i);
        else groups.set(i.category, [i]);
        return groups;
      }, new Map<string, typeof indicators>())
      .entries(),
  );
  const { data: personnelResults } = usePersonnelList({
    q: debouncedPersonnelSearch,
    limit: 30,
    offset: 0,
  });
  const personnelOptions = personnelResults?.items ?? [];

  const { data: summary, isPending: summaryPending } = useReportSummary(filters);
  const { data: indicatorBreakdown, isPending: indicatorPending } = useIndicatorBreakdown(
    selectedIndicatorId,
    filters
  );
  const employeeFilters = useMemo(
    () => ({
      period_id: filters.period_id,
      created_from: filters.created_from,
      created_to: filters.created_to,
    }),
    [filters.period_id, filters.created_from, filters.created_to]
  );
  const { data: empVsUnit } = useEmployeeVsUnit(filters.personnel_id ?? null, employeeFilters);

  const selectedPersonName =
    personnelOptions.find((p) => p.id === filters.personnel_id)?.full_name ??
    empVsUnit?.full_name ??
    null;

  function patch(next: Partial<ReportFilters>) {
    setFilters((prev) => ({ ...prev, ...next }));
  }
  function reset() {
    setFilters({});
    setPersonnelSearch("");
    setSelectedIndicatorId(null);
  }

  const activeFilterCount = Object.values(filters).filter((v) => v !== undefined && v !== "").length;

  // ردیف‌های سرکوب‌شده (P1-08) از نمودارها کنار گذاشته می‌شوند: میله نمی‌تواند
  // «پنهان» را نشان دهد و صفر نشان‌دادنشان دروغ است. جدول‌ها نشانِ «محرمانه» دارند.
  const unitChartData = (summary?.by_org_unit ?? [])
    .filter((u) => u.avg_final_pct !== null)
    .map((u) => ({ name: u.org_unit, میانگین: Math.round(u.avg_final_pct!) }));
  // برچسبِ محور، «شرح» شاخص است نه category: چند شاخصِ متفاوت یک category مشترک
  // دارند، پس با category نمودار ۲۰ میله با ۹ برچسب تکراری نشان می‌داد و معلوم
  // نبود کدام میله کدام شاخص است. متن کامل در tooltip می‌آید.
  const indicatorChartData = (summary?.by_indicator ?? [])
    .filter((i) => i.avg_score !== null)
    .map((i) => ({
      name: truncateLabel(i.description),
      fullName: `${i.category} — ${i.description}`,
      میانگین: Number(i.avg_score!.toFixed(2)),
    }));
  const indicatorUnitData = (indicatorBreakdown?.by_org_unit ?? [])
    .filter((u) => u.avg_score !== null)
    .map((u) => ({ name: u.org_unit, میانگین: Number(u.avg_score!.toFixed(2)) }));
  const empComparisonData =
    empVsUnit && (empVsUnit.employee_avg !== null || empVsUnit.unit_avg !== null)
      ? [
          { name: selectedPersonName ?? "این فرد", مقدار: empVsUnit.employee_avg ?? 0, fill: SERIES_COLOR },
          { name: `میانگین واحد (${empVsUnit.org_unit})`, مقدار: empVsUnit.unit_avg ?? 0, fill: UNIT_COLOR },
        ]
      : [];

  return (
    <div className="space-y-4">
      <div className="border-t border-gray-100 pt-6">
        <PageHeader
          title="گزارش‌های تحلیلی"
          subtitle="فیلترهای ترکیب‌پذیر روی همهٔ نمودارها و خروجی‌های این بخش اعمال می‌شوند."
        />
      </div>

      {/* ── نوار فیلترهای سراسری ── */}
      <Card
        title="فیلترها"
        actions={
          <div className="flex items-center gap-2">
            <ExcelExportButton
              url="/dashboard/report/export.xlsx"
              filename="hr-report.xlsx"
              params={filters as Record<string, unknown>}
            />
            {activeFilterCount > 0 && (
              <button
                onClick={reset}
                className="rounded-xl border border-gray-200 bg-white px-3 py-1.5 text-sm font-medium text-gray-500 transition-colors hover:bg-gray-50 hover:text-gray-700"
              >
                حذف فیلترها
              </button>
            )}
          </div>
        }
      >
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
            دورهٔ ارزیابی
            <FilterSelect
              aria-label="دوره"
              value={filters.period_id ? String(filters.period_id) : ""}
              onChange={(v) => patch({ period_id: v ? Number(v) : undefined })}
            >
              <option value="">همهٔ دوره‌ها</option>
              {periods.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </FilterSelect>
          </label>

          <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
            واحد سازمانی
            <FilterSelect
              aria-label="واحد سازمانی"
              value={filters.org_unit ?? ""}
              onChange={(v) => patch({ org_unit: v || undefined })}
            >
              <option value="">همهٔ واحدها</option>
              {orgUnits.map((u) => (
                <option key={u} value={u}>
                  {u}
                </option>
              ))}
            </FilterSelect>
          </label>

          <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
            وضعیت پرسنل
            <FilterSelect
              aria-label="وضعیت پرسنل"
              value={filters.status ?? ""}
              onChange={(v) => patch({ status: (v || undefined) as ReportFilters["status"] })}
            >
              <option value="">فعال و غیرفعال</option>
              <option value="active">فقط فعال</option>
              <option value="inactive">فقط غیرفعال</option>
            </FilterSelect>
          </label>

          {/* دراپ‌داون جست‌وجوی پرسنل */}
          <div className="flex flex-col gap-1 text-xs font-medium text-gray-600">
            پرسنل مشخص
            <input
              className={inputClass}
              placeholder="جست‌وجوی نام برای فیلتر…"
              value={personnelSearch}
              onChange={(e) => setPersonnelSearch(e.target.value)}
            />
            <FilterSelect
              aria-label="انتخاب پرسنل"
              value={filters.personnel_id ? String(filters.personnel_id) : ""}
              onChange={(v) => patch({ personnel_id: v ? Number(v) : undefined })}
            >
              <option value="">همهٔ پرسنل</option>
              {filters.personnel_id && selectedPersonName && !personnelOptions.some((p) => p.id === filters.personnel_id) && (
                <option value={filters.personnel_id}>{selectedPersonName}</option>
              )}
              {personnelOptions.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.full_name} ({p.org_unit})
                </option>
              ))}
            </FilterSelect>
          </div>

          <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
            از تاریخ شروع ارزیابی
            <JalaliDatePicker
              className={inputClass}
              value={filters.created_from ?? ""}
              onChange={(iso) => patch({ created_from: iso || undefined })}
            />
          </label>
          <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
            تا تاریخ شروع ارزیابی
            <JalaliDatePicker
              className={inputClass}
              value={filters.created_to ?? ""}
              onChange={(iso) => patch({ created_to: iso || undefined })}
            />
          </label>

          <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
            پایان قرارداد از
            <JalaliDatePicker
              className={inputClass}
              value={filters.contract_end_from ?? ""}
              onChange={(iso) => patch({ contract_end_from: iso || undefined })}
            />
          </label>
          <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
            پایان قرارداد تا
            <JalaliDatePicker
              className={inputClass}
              value={filters.contract_end_to ?? ""}
              onChange={(iso) => patch({ contract_end_to: iso || undefined })}
            />
          </label>

          {/* میان‌برهای «قرارداد رو به اتمام / منقضی» */}
          <div className="flex flex-col gap-1 text-xs font-medium text-gray-600">
            میان‌بر قرارداد
            <div className="flex flex-wrap gap-1.5">
              {[
                { label: "۳۰ روز آینده", days: 30 },
                { label: "۹۰ روز آینده", days: 90 },
              ].map((preset) => (
                <button
                  key={preset.days}
                  type="button"
                  onClick={() => {
                    const d = new Date();
                    d.setDate(d.getDate() + preset.days);
                    patch({ contract_end_from: todayIso(), contract_end_to: d.toISOString().slice(0, 10) });
                  }}
                  className="rounded-lg border border-gray-200 bg-white px-2 py-1 text-xs text-gray-600 hover:bg-gray-50"
                >
                  {preset.label}
                </button>
              ))}
              <button
                type="button"
                onClick={() => patch({ contract_end_from: undefined, contract_end_to: todayIso() })}
                className="rounded-lg border border-gray-200 bg-white px-2 py-1 text-xs text-gray-600 hover:bg-gray-50"
              >
                منقضی‌شده
              </button>
            </div>
          </div>
        </div>
      </Card>

      {/* ── خلاصهٔ فیلترشده ── */}
      {summaryPending ? (
        <Card>
          <TableSkeleton rows={3} />
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="flex items-center gap-4 rounded-2xl border border-gray-100 bg-white p-5 shadow-card">
            <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-pulse-50 text-pulse-600" aria-hidden>
              <svg viewBox="0 0 20 20" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                <path d="M7 3h6l4 4v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h3z" />
                <path d="M7 11l2 2 4-4" />
              </svg>
            </span>
            <div>
              <p className="text-xs text-gray-500">ارزیابی‌های نهایی‌شدهٔ منطبق با فیلتر</p>
              <p className="mt-0.5 text-2xl font-extrabold tabular-nums text-gray-900">
                <CountUp value={summary?.total_evaluations ?? 0} format="plain" />
              </p>
            </div>
          </div>
          <div className="flex items-center justify-between gap-4 rounded-2xl border border-gray-100 bg-white p-5 shadow-card">
            <div>
              <p className="text-xs text-gray-500">میانگین امتیاز نهایی (فیلترشده)</p>
              <p className="mt-0.5 text-sm text-gray-400">میانگین ٪ در نتایج فیلترشده</p>
            </div>
            <ScoreRing value={summary?.avg_final_pct ?? null} size={64} />
          </div>
        </div>
      )}

      {/* ── میانگین به‌تفکیک واحد (بزرگ + دانلود) ── */}
      <ChartDownloadCard
        title="میانگین امتیاز نهایی به تفکیک واحد سازمانی"
        subtitle="امتیاز نهایی وزنی (٪) — با فیلترهای فعال"
        filename="avg-by-unit.png"
      >
        {summaryPending ? (
          <TableSkeleton rows={4} />
        ) : unitChartData.length === 0 ? (
          <EmptyState>
            {chartEmptyMessage((summary?.by_org_unit ?? []).length, unitChartData.length, "برای فیلترهای فعلی داده‌ای وجود ندارد.")}
          </EmptyState>
        ) : (
          <div style={{ height: Math.max(280, unitChartData.length * 54) }}>
            <ResponsiveContainer>
              <BarChart data={unitChartData} layout="vertical" margin={{ top: 8, right: 40, bottom: 8, left: 12 }}>
                <CartesianGrid strokeDasharray="4 4" stroke={GRID_STROKE} horizontal={false} />
                <XAxis type="number" domain={[0, 100]} tick={TICK_STYLE} tickLine={false} axisLine={{ stroke: AXIS_STROKE }} />
                <YAxis type="category" dataKey="name" tick={{ ...TICK_STYLE, fontSize: 12 }} tickLine={false} axisLine={false} width={130} />
                <Tooltip contentStyle={TOOLTIP_STYLE} formatter={faNum} cursor={{ fill: "rgba(107,114,128,0.06)" }} />
                <Bar dataKey="میانگین" radius={[0, 6, 6, 0]} fill={SERIES_COLOR} animationDuration={800}>
                  {/* direction:ltr روی برچسب: تحت dir="rtl" صفحه، text-anchor="start" که
                      Recharts برای position="right" می‌سازد معکوس تفسیر می‌شود و عدد به‌جای
                      فاصله از میله، داخل خودِ میله می‌افتد (تقریباً نامرئی). */}
                  <LabelList dataKey="میانگین" position="right" formatter={(v) => (v == null ? "" : faNum(Number(v)))} style={{ fontSize: 12, fill: "#374151", fontFamily: "Vazirmatn, Tahoma, sans-serif", direction: "ltr" }} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </ChartDownloadCard>

      {/* ── میانگین هر شاخص (بزرگ + دانلود) ── */}
      <ChartDownloadCard
        title="میانگین امتیاز هر شاخص (از ۵)"
        subtitle="میانگین امتیاز هر شاخص در همهٔ پرسنل منطبق با فیلتر"
        filename="avg-by-indicator.png"
      >
        {summaryPending ? (
          <TableSkeleton rows={5} />
        ) : indicatorChartData.length === 0 ? (
          <EmptyState>
            {chartEmptyMessage((summary?.by_indicator ?? []).length, indicatorChartData.length, "برای فیلترهای فعلی داده‌ای وجود ندارد.")}
          </EmptyState>
        ) : (
          <div style={{ height: Math.max(320, indicatorChartData.length * 34) }}>
            <ResponsiveContainer>
              <BarChart data={indicatorChartData} layout="vertical" margin={{ top: 8, right: 32, bottom: 8, left: 12 }}>
                <CartesianGrid strokeDasharray="4 4" stroke={GRID_STROKE} horizontal={false} />
                <XAxis type="number" domain={[0, 5]} tick={TICK_STYLE} tickLine={false} axisLine={{ stroke: AXIS_STROKE }} />
                <YAxis type="category" dataKey="name" tick={{ ...TICK_STYLE, fontSize: 11 }} tickLine={false} axisLine={false} width={210} />
                <Tooltip
                  contentStyle={TOOLTIP_STYLE}
                  formatter={faNum}
                  labelFormatter={(_, payload) => payload?.[0]?.payload?.fullName ?? ""}
                  cursor={{ fill: "rgba(107,114,128,0.06)" }}
                />
                <Bar dataKey="میانگین" radius={[0, 6, 6, 0]} fill={SERIES_COLOR} animationDuration={800}>
                  <LabelList dataKey="میانگین" position="right" formatter={(v) => (v == null ? "" : faNum(Number(v)))} style={{ fontSize: 11, fill: "#374151", fontFamily: "Vazirmatn, Tahoma, sans-serif", direction: "ltr" }} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </ChartDownloadCard>

      {/* ── ریز یک شاخص خاص به تفکیک واحد ── */}
      <ChartDownloadCard
        title="گزارش شاخص‌به‌شاخص"
        subtitle="یک شاخص را انتخاب کنید تا میانگین آن به تفکیک واحد سازمانی (با فیلترهای فعال) دیده شود."
        filename="indicator-breakdown.png"
        actions={
          <FilterSelect
            aria-label="انتخاب شاخص"
            value={selectedIndicatorId ? String(selectedIndicatorId) : ""}
            onChange={(v) => setSelectedIndicatorId(v ? Number(v) : null)}
          >
            <option value="">— انتخاب شاخص —</option>
            {/* گروه‌بندی با optgroup و برچسب‌زدن با «شرح» شاخص.
                قبلاً هر گزینه فقط category را نشان می‌داد، ولی category یک برچسب
                گروه است نه شناسه: مثلاً سه شاخصِ کاملاً متفاوت همگی زیر «تعهد
                سازمانی» هستند. نتیجه‌اش فهرستی بود که تکراری به‌نظر می‌رسید و
                انتخاب از آن عملاً حدس زدن بود. */}
            {indicatorGroups.map(([category, items]) => (
              <optgroup key={category} label={category}>
                {items.map((i) => (
                  <option key={i.id} value={i.id}>
                    {i.description}
                  </option>
                ))}
              </optgroup>
            ))}
          </FilterSelect>
        }
      >
        {selectedIndicatorId === null ? (
          <EmptyState>برای دیدن گزارش، یک شاخص انتخاب کنید.</EmptyState>
        ) : indicatorPending ? (
          <TableSkeleton rows={4} />
        ) : indicatorUnitData.length === 0 ? (
          <EmptyState>
            {chartEmptyMessage((indicatorBreakdown?.by_org_unit ?? []).length, indicatorUnitData.length, "برای این شاخص و فیلترها داده‌ای وجود ندارد.")}
          </EmptyState>
        ) : (
          <>
            <p className="mb-3 text-sm text-gray-600">
              «{indicatorBreakdown?.category}» — میانگین کل:{" "}
              <span className="font-bold text-gray-900">
                {indicatorBreakdown?.overall_avg != null ? faNum(indicatorBreakdown.overall_avg) : "—"}
              </span>{" "}
              از ۵
            </p>
            <div style={{ height: Math.max(260, indicatorUnitData.length * 54) }}>
              <ResponsiveContainer>
                <BarChart data={indicatorUnitData} layout="vertical" margin={{ top: 8, right: 32, bottom: 8, left: 12 }}>
                  <CartesianGrid strokeDasharray="4 4" stroke={GRID_STROKE} horizontal={false} />
                  <XAxis type="number" domain={[0, 5]} tick={TICK_STYLE} tickLine={false} axisLine={{ stroke: AXIS_STROKE }} />
                  <YAxis type="category" dataKey="name" tick={{ ...TICK_STYLE, fontSize: 12 }} tickLine={false} axisLine={false} width={130} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} formatter={faNum} cursor={{ fill: "rgba(107,114,128,0.06)" }} />
                  <Bar dataKey="میانگین" radius={[0, 6, 6, 0]} fill={SERIES_COLOR} animationDuration={800}>
                    <LabelList dataKey="میانگین" position="right" formatter={(v) => (v == null ? "" : faNum(Number(v)))} style={{ fontSize: 12, fill: "#374151", fontFamily: "Vazirmatn, Tahoma, sans-serif", direction: "ltr" }} />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </>
        )}
      </ChartDownloadCard>

      {/* ── مقایسهٔ فرد با میانگین واحد ── */}
      <ChartDownloadCard
        title="مقایسهٔ امتیاز فرد با میانگین واحد سازمانی"
        subtitle="یک «پرسنل مشخص» از فیلترهای بالا انتخاب کنید تا امتیاز او در برابر میانگین واحدش دیده شود."
        filename="employee-vs-unit.png"
      >
        {!filters.personnel_id ? (
          <EmptyState>برای مقایسه، از نوار فیلتر یک «پرسنل مشخص» انتخاب کنید.</EmptyState>
        ) : empComparisonData.length === 0 ? (
          <EmptyState>برای این فرد و فیلترها نتیجهٔ نهایی‌شده‌ای وجود ندارد.</EmptyState>
        ) : (
          <>
            <div className="mb-4 flex flex-wrap gap-4 text-sm">
              <span className="rounded-lg bg-pulse-50 px-3 py-1.5 font-medium text-pulse-700">
                میانگین فرد: {empVsUnit?.employee_avg != null ? faNum(empVsUnit.employee_avg) : "—"}٪
                {" "}({faNum(empVsUnit?.evaluation_count ?? 0)} ارزیابی)
              </span>
              <span className="rounded-lg bg-gray-100 px-3 py-1.5 font-medium text-gray-700">
                میانگین واحد «{empVsUnit?.org_unit}»: {empVsUnit?.unit_avg != null ? faNum(empVsUnit.unit_avg) : "—"}٪
                {" "}({faNum(empVsUnit?.unit_evaluation_count ?? 0)} ارزیابی)
              </span>
            </div>
            <div style={{ height: 240 }}>
              <ResponsiveContainer>
                <BarChart data={empComparisonData} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
                  <CartesianGrid strokeDasharray="4 4" stroke={GRID_STROKE} vertical={false} />
                  <XAxis dataKey="name" tick={{ ...TICK_STYLE, fontSize: 12 }} tickLine={false} axisLine={{ stroke: AXIS_STROKE }} />
                  <YAxis domain={[0, 100]} tick={TICK_STYLE} tickLine={false} axisLine={false} width={36} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} formatter={faNum} cursor={{ fill: "rgba(107,114,128,0.06)" }} />
                  <Bar dataKey="مقدار" radius={[6, 6, 0, 0]} animationDuration={800}>
                    <LabelList dataKey="مقدار" position="top" formatter={(v) => (v == null ? "" : faNum(Number(v)))} style={{ fontSize: 12, fill: "#374151", fontFamily: "Vazirmatn, Tahoma, sans-serif" }} />
                    {empComparisonData.map((entry, i) => (
                      <Cell key={i} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            {(empVsUnit?.per_evaluation.length ?? 0) > 1 && (
              <div className="mt-4">
                <h4 className="mb-2 text-sm font-semibold text-gray-600">روند امتیاز نهایی این فرد</h4>
                <div style={{ height: 200 }}>
                  <ResponsiveContainer>
                    <AreaChart
                      data={empVsUnit?.per_evaluation.map((p) => ({ name: p.evaluation_code, مقدار: p.final_weighted_pct }))}
                      margin={{ top: 8, right: 16, bottom: 8, left: 0 }}
                    >
                      <CartesianGrid strokeDasharray="4 4" stroke={GRID_STROKE} vertical={false} />
                      <XAxis dataKey="name" tick={TICK_STYLE} tickLine={false} axisLine={{ stroke: AXIS_STROKE }} />
                      <YAxis domain={[0, 100]} tick={TICK_STYLE} tickLine={false} axisLine={false} width={36} />
                      <Tooltip contentStyle={TOOLTIP_STYLE} formatter={faNum} />
                      <Area type="monotone" dataKey="مقدار" stroke={SERIES_COLOR} strokeWidth={2.5} fill="rgba(182,22,21,0.12)" dot={{ r: 4, fill: "#fff", strokeWidth: 2.5, stroke: SERIES_COLOR }} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}
          </>
        )}
      </ChartDownloadCard>
    </div>
  );
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}
