import { useState } from "react";
import {
  useIndicatorBreakdown,
  useIndicators,
  useOrgUnits,
  usePeriods,
  useReportSummary,
} from "../../api/queries";
import { ChartDownloadCard } from "../../components/ChartDownloadCard";
import { ExcelExportButton } from "../../components/ExcelExportButton";
import { Card, EmptyState, FilterSelect, PageHeader, TableSkeleton } from "../../ui/Card";
import { IndicatorScorePanel, type IndicatorSort } from "../../ui/IndicatorScorePanel";
import { DotPlot, fa1 } from "../../ui/plot";
import { CountUp, ScoreRing } from "../../ui/Meters";
import { JalaliDatePicker } from "../../ui/JalaliDatePicker";
import type { ReportFilters } from "../../types";

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

const inputClass =
  "w-full rounded-xl border border-gray-200 bg-gray-100 px-3 py-1.5 text-sm text-gray-700 outline-none transition-colors duration-150 focus:border-gray-900 focus:bg-white";

/** بخش گزارش‌های تحلیلی فیلترشونده — جدا از کارت‌های خلاصهٔ همیشگیِ بالای داشبورد.
 * همهٔ فیلترها ترکیب‌پذیرند و روی همهٔ نمودارها/خروجی‌های این بخش اعمال می‌شوند.
 *
 * این بخش عمداً هیچ فیلتر «یک فردِ مشخص» ندارد: هرچه دربارهٔ یک نفر است در زیرتب
 * «کارنامهٔ فرد» جمع شده (PersonScorecard). فیلتر پرسنل این‌جا دو مشکل داشت —
 * دومین انتخابگرِ فرد در صفحه بود که با انتخابگر آن تب هماهنگ نمی‌شد، و
 * محدودکردن یک گزارشِ *سازمانی* به یک نفر، سرکوب کوهورت را هم بی‌اثر می‌کرد. */
export function ReportsSection() {
  const [filters, setFilters] = useState<ReportFilters>({});
  const [selectedIndicatorId, setSelectedIndicatorId] = useState<number | null>(null);
  const [indicatorSort, setIndicatorSort] = useState<IndicatorSort>("form");

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
  const { data: summary, isPending: summaryPending } = useReportSummary(filters);
  const { data: indicatorBreakdown, isPending: indicatorPending } = useIndicatorBreakdown(
    selectedIndicatorId,
    filters
  );

  function patch(next: Partial<ReportFilters>) {
    setFilters((prev) => ({ ...prev, ...next }));
  }
  function reset() {
    setFilters({});
    setSelectedIndicatorId(null);
  }

  const activeFilterCount = Object.values(filters).filter((v) => v !== undefined && v !== "").length;

  // ردیف‌های سرکوب‌شده (P1-08) از نمودارها کنار گذاشته می‌شوند: میله نمی‌تواند
  // «پنهان» را نشان دهد و صفر نشان‌دادنشان دروغ است. جدول‌ها نشانِ «محرمانه» دارند.
  const unitChartData = (summary?.by_org_unit ?? [])
    .filter((u) => u.avg_final_pct !== null)
    .map((u) => ({
      key: u.org_unit,
      label: u.org_unit,
      value: u.avg_final_pct!,
      note: `${faNum(u.count)} ارزیابی`,
    }));
  // شاخص‌ها دیگر میلهٔ افقی نیستند (IndicatorScorePanel دلیلش را توضیح می‌دهد)؛
  // این‌جا فقط باید بدانیم بعد از سرکوب کوهورت چیزی برای نمایش مانده یا نه.
  const visibleIndicatorCount = (summary?.by_indicator ?? []).filter(
    (i) => i.avg_score !== null,
  ).length;
  const indicatorUnitData = (indicatorBreakdown?.by_org_unit ?? [])
    .filter((u) => u.avg_score !== null)
    .map((u) => ({
      key: u.org_unit,
      label: u.org_unit,
      value: u.avg_score!,
      note: `${faNum(u.count)} نمره`,
    }));

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
          <div className="flex items-center gap-4 rounded-2xl border border-gray-200 bg-white p-5">
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
          <div className="flex items-center justify-between gap-4 rounded-2xl border border-gray-200 bg-white p-5">
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
          <DotPlot
            rows={unitChartData}
            reference={summary?.avg_final_pct ?? null}
            ariaLabel="میانگین امتیاز نهایی به تفکیک واحد سازمانی"
          />
        )}
      </ChartDownloadCard>

      {/* ── میانگین هر شاخص (بزرگ + دانلود) ── */}
      <ChartDownloadCard
        title="میانگین امتیاز هر شاخص (از ۵)"
        subtitle="میانگین نمره‌های منطبق با فیلتر، گروه‌بندی‌شده بر اساس دسته — روی هر دسته بزنید تا شرح شاخص‌هایش باز شود."
        filename="avg-by-indicator.png"
        actions={
          <FilterSelect
            aria-label="ترتیب نمایش شاخص‌ها"
            value={indicatorSort}
            onChange={(v) => setIndicatorSort(v as IndicatorSort)}
          >
            <option value="form">ترتیب فرم ارزیابی</option>
            <option value="lowest">کم‌امتیازترین در صدر</option>
          </FilterSelect>
        }
      >
        {summaryPending ? (
          <TableSkeleton rows={5} />
        ) : visibleIndicatorCount === 0 ? (
          <EmptyState>
            {chartEmptyMessage((summary?.by_indicator ?? []).length, visibleIndicatorCount, "برای فیلترهای فعلی داده‌ای وجود ندارد.")}
          </EmptyState>
        ) : (
          <IndicatorScorePanel stats={summary?.by_indicator ?? []} sort={indicatorSort} />
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
            <DotPlot
              rows={indicatorUnitData}
              min={1}
              max={5}
              ticks={[1, 2, 3, 4, 5]}
              format={fa1}
              reference={indicatorBreakdown?.overall_avg ?? null}
              ariaLabel="میانگین این شاخص به تفکیک واحد سازمانی"
            />
          </>
        )}
      </ChartDownloadCard>

    </div>
  );
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}
