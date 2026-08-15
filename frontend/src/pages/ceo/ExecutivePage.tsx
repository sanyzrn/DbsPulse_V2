/** نمای مدیریتی (P2-01) — سازمان از بالا، بدون هیچ نامی.
 *
 * تا امروز مدیرعامل یک صف داشت و نه یک نما: نمی‌دید کدام واحد عقب است، ترکیب
 * توصیه‌ها به تمدید قرارداد چه می‌گوید، یا چرخهٔ تصمیم چقدر طول می‌کشد. این سه
 * دقیقاً همان چیزهایی‌اند که بودجه و اختیار رویشان تصمیم می‌گیرد.
 *
 * قاعدهٔ سختِ این صفحه: **هیچ نام فردی این‌جا نمی‌آید.** مدیرعامل عمداً به
 * رکوردهای خارج از زنجیرهٔ خودش دسترسی ندارد؛ اگر تجمیع اسم بدهد، همان کنترل
 * دسترسی دور زده می‌شود. سرور هم همین را تضمین می‌کند (test_role_analytics.py).
 */
import { useQuery } from "@tanstack/react-query";
import { apiClient, extractErrorMessage } from "../../api/client";
import { Card, EmptyState, PageHeader, TableSkeleton } from "../../ui/Card";
import { CountUp, ScoreRing } from "../../ui/Meters";
import { DotPlot, faInt, fa1 } from "../../ui/plot";

interface UnitPerformance {
  org_unit: string;
  avg_final_pct: number | null;
  count: number;
}

interface RecommendationSlice {
  recommendation: string;
  count: number;
  share_pct: number;
}

interface ExecutiveOverview {
  total_finalized: number;
  avg_final_pct: number | null;
  by_org_unit: UnitPerformance[];
  recommendation_mix: RecommendationSlice[];
  cycle_time: {
    finalized_count: number;
    median_days: number | null;
    p90_days: number | null;
    oldest_open_stage_days: number | null;
    open_count: number;
  };
  contract_exposure: {
    horizon_days: number;
    expiring: number;
    without_finalized_evaluation: number;
  }[];
}

export function ExecutivePage() {
  const { data, isPending, error } = useQuery({
    queryKey: ["analytics", "executive"],
    queryFn: async () => (await apiClient.get<ExecutiveOverview>("/analytics/executive")).data,
  });

  if (error != null)
    return <p className="p-6 text-center text-sm text-red-600">{extractErrorMessage(error)}</p>;

  if (isPending || !data)
    return (
      <div className="space-y-5">
        <PageHeader title="تحلیل سازمان" />
        <Card>
          <TableSkeleton rows={6} />
        </Card>
      </div>
    );

  const visibleUnits = data.by_org_unit.filter((u) => u.avg_final_pct !== null);
  const hiddenUnits = data.by_org_unit.length - visibleUnits.length;

  return (
    <div className="space-y-5">
      <PageHeader
        title="تحلیل سازمان"
        subtitle="نمای تجمیعی عملکرد، ریسک تمدید قرارداد و سرعت گردش‌کار — بدون داده‌های فردی"
      />

      {/* ── سه عدد سرصفحه ── */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="flex items-center justify-between gap-4 rounded-2xl border border-gray-100 bg-white p-5 shadow-card">
          <div>
            <p className="text-xs text-gray-500">میانگین امتیاز نهایی سازمان</p>
            <p className="mt-0.5 text-sm text-gray-400">در همهٔ ارزیابی‌های نهایی‌شده</p>
          </div>
          <ScoreRing value={data.avg_final_pct} size={64} />
        </div>
        <HeadlineStat
          label="ارزیابی‌های نهایی‌شده"
          value={data.total_finalized}
          hint="پرونده‌هایی که تصمیمشان قطعی شده است"
        />
        <HeadlineStat
          label="پرونده‌های در جریان"
          value={data.cycle_time.open_count}
          hint={
            data.cycle_time.oldest_open_stage_days !== null
              ? `قدیمی‌ترین: ${fa1(data.cycle_time.oldest_open_stage_days)} روز در همان مرحله`
              : "چیزی در جریان نیست"
          }
          tone={data.cycle_time.open_count > 0 ? "amber" : "neutral"}
        />
      </div>

      {/* ── ریسک تمدید: مهم‌ترین کارت این صفحه ── */}
      <Card title="ریسک تمدید قرارداد">
        <p className="mb-4 text-xs text-gray-500">
          عدد مهم «چند نفر قراردادشان تمام می‌شود» نیست؛ «چند نفرشان بدون ارزیابی
          نهایی‌شده‌اند» است — یعنی تصمیم تمدید بدون داده گرفته می‌شود.
        </p>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {data.contract_exposure.map((horizon) => (
            <div
              key={horizon.horizon_days}
              className={`rounded-2xl border p-4 ${
                horizon.without_finalized_evaluation > 0
                  ? "border-amber-200 bg-amber-50/40"
                  : "border-gray-100 bg-white"
              }`}
            >
              <p className="text-xs text-gray-500">
                تا {faInt(horizon.horizon_days)} روز آینده
              </p>
              <p className="mt-1 text-2xl font-extrabold tabular-nums text-gray-900">
                {faInt(horizon.expiring)}
              </p>
              <p className="mt-1 text-[11px] text-gray-500">قرارداد رو به پایان</p>
              <p
                className={`mt-2 border-t pt-2 text-xs font-medium ${
                  horizon.without_finalized_evaluation > 0
                    ? "border-amber-200 text-amber-800"
                    : "border-gray-100 text-gray-500"
                }`}
              >
                {faInt(horizon.without_finalized_evaluation)} نفر بدون ارزیابی نهایی‌شده
              </p>
            </div>
          ))}
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {/* ── ترکیب توصیه‌ها ── */}
        <Card title="ترکیب نتیجهٔ پیشنهادی">
          <p className="mb-4 text-xs text-gray-500">
            همان چیزی که مستقیماً به تصمیم تمدید ترجمه می‌شود.
          </p>
          {data.recommendation_mix.length === 0 ? (
            <EmptyState>هنوز ارزیابی نهایی‌شده‌ای وجود ندارد.</EmptyState>
          ) : (
            <ul className="space-y-3">
              {data.recommendation_mix.map((slice) => (
                <li key={slice.recommendation}>
                  <div className="mb-1 flex items-baseline justify-between gap-2 text-xs">
                    <span className="min-w-0 truncate text-gray-700">{slice.recommendation}</span>
                    <span className="shrink-0 tabular-nums text-gray-500">
                      {faInt(slice.count)} نفر · {fa1(slice.share_pct)}٪
                    </span>
                  </div>
                  <span className="block h-2 overflow-hidden rounded-full bg-gray-100">
                    <span
                      className="block h-full rounded-full bg-pulse-500"
                      style={{ width: `${slice.share_pct}%` }}
                    />
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>

        {/* ── سرعت چرخه ── */}
        <Card title="سرعت چرخهٔ تصمیم">
          <dl className="space-y-4">
            <CycleStat
              label="میانهٔ زمان از آغاز تا نهایی‌شدن"
              value={
                data.cycle_time.median_days !== null
                  ? `${fa1(data.cycle_time.median_days)} روز`
                  : "—"
              }
              hint={`بر پایهٔ ${faInt(data.cycle_time.finalized_count)} پروندهٔ نهایی‌شده`}
            />
            <CycleStat
              label="۹۰ درصد پرونده‌ها زیر این زمان"
              value={
                data.cycle_time.p90_days !== null ? `${fa1(data.cycle_time.p90_days)} روز` : "—"
              }
              hint="میانه می‌گوید حالت عادی چقدر است؛ این عدد می‌گوید بدترین حالتِ معمول چقدر."
            />
            <CycleStat
              label="قدیمی‌ترین پروندهٔ باز"
              value={
                data.cycle_time.oldest_open_stage_days !== null
                  ? `${fa1(data.cycle_time.oldest_open_stage_days)} روز`
                  : "—"
              }
              hint="چند روز است در همان مرحله مانده — نه از آغاز پرونده."
            />
          </dl>
        </Card>
      </div>

      {/* ── مقایسهٔ واحدها ── */}
      <Card title="عملکرد به تفکیک واحد سازمانی">
        {visibleUnits.length === 0 ? (
          <EmptyState>
            {data.by_org_unit.length > 0
              ? "داده هست، ولی تعداد افراد هر واحد کمتر از حد لازم برای نمایش میانگین بی‌نام است."
              : "هنوز ارزیابی نهایی‌شده‌ای وجود ندارد."}
          </EmptyState>
        ) : (
          <DotPlot
            rows={visibleUnits.map((unit) => ({
              key: unit.org_unit,
              label: unit.org_unit,
              value: unit.avg_final_pct!,
              note: `${faInt(unit.count)} ارزیابی`,
            }))}
            reference={data.avg_final_pct}
            ariaLabel="میانگین امتیاز نهایی به تفکیک واحد سازمانی"
            footer={
              hiddenUnits > 0 ? (
                <span>
                  {faInt(hiddenUnits)} واحد به دلیل تعداد کم افراد نمایش داده نشده است
                  (میانگینشان عملاً امتیاز فرد است).
                </span>
              ) : undefined
            }
          />
        )}
      </Card>
    </div>
  );
}

function HeadlineStat({
  label,
  value,
  hint,
  tone = "neutral",
}: {
  label: string;
  value: number;
  hint: string;
  tone?: "neutral" | "amber";
}) {
  return (
    <div
      className={`rounded-2xl border p-5 shadow-card ${
        tone === "amber" ? "border-amber-200 bg-amber-50/40" : "border-gray-100 bg-white"
      }`}
    >
      <p className="text-xs text-gray-500">{label}</p>
      <p className="mt-0.5 text-2xl font-extrabold tabular-nums text-gray-900">
        <CountUp value={value} format="plain" />
      </p>
      <p className="mt-1 text-[11px] text-gray-400">{hint}</p>
    </div>
  );
}

function CycleStat({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div>
      <dt className="text-xs text-gray-500">{label}</dt>
      <dd className="mt-0.5 text-xl font-extrabold tabular-nums text-gray-900">{value}</dd>
      <p className="mt-1 text-[11px] leading-relaxed text-gray-400">{hint}</p>
    </div>
  );
}
