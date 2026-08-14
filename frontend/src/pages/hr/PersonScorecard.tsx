/** کارنامهٔ یک فرد — همهٔ چیزی که دربارهٔ یک نفر گفتنی است، در یک جا.
 *
 * پیش از این، «یک فرد» دو خانهٔ جدا داشت و هیچ‌کدام از دیگری خبر نداشت:
 *
 * ۱. زیرتب «کارنامهٔ فرد» یک انتخابگر داشت که رادار و روند را می‌ساخت.
 * ۲. زیرتب «گزارش‌های تحلیلی» یک انتخابگر دیگر در نوار فیلتر داشت که کارت
 *    «مقایسهٔ امتیاز فرد با میانگین واحد» را می‌ساخت.
 *
 * یعنی کاربر یک نفر را در یک تب انتخاب می‌کرد و تب بغلی همچنان خالی بود — و
 * کارتی که فقط دربارهٔ یک نفر حرف می‌زند، وسط گزارش‌های *سازمانی* نشسته بود.
 * حالا هر دو این‌جا هستند و یک انتخابگر دارند.
 *
 * ترتیب کارت‌ها از پاسخ به سمت تفصیل است: اول «این فرد بالاتر است یا پایین‌تر؟»
 * که سؤال اصلی است، بعد شکل شایستگی و روند که توضیحِ همان پاسخ‌اند.
 */
import { useMemo, useState } from "react";
import {
  useEmployeeVsUnit,
  usePeriods,
  usePersonRadar,
  usePersonTrend,
} from "../../api/queries";
import { ChartDownloadCard } from "../../components/ChartDownloadCard";
import { CompetencyRadar, ScoreTrend } from "../../components/PersonCharts";
import { PersonPicker } from "../../components/PersonPicker";
import { Card, EmptyState, FilterSelect } from "../../ui/Card";
import { Dumbbell } from "../../ui/plot";

const faNum = (value: number) => value.toLocaleString("fa-IR");

export function PersonScorecard() {
  const [personId, setPersonId] = useState<number | null>(null);
  const [periodId, setPeriodId] = useState<number | null>(null);

  const { data: periods = [] } = usePeriods();
  // فیلتر دوره فقط روی مقایسهٔ فرد/واحد اثر دارد؛ رادار و روند کل تاریخچه را
  // نشان می‌دهند و همین درست است — «روند» با یک دوره روند نیست.
  const comparisonFilters = useMemo(
    () => (periodId !== null ? { period_id: periodId } : {}),
    [periodId],
  );
  const { data: vsUnit } = useEmployeeVsUnit(personId, comparisonFilters);
  const { data: radar = [] } = usePersonRadar(personId);
  const { data: trend = [] } = usePersonTrend(personId);

  // یکی از دو طرف کافی است؛ Dumbbell خودش طرفِ نبود را «—» نشان می‌دهد.
  const hasComparison =
    vsUnit != null && (vsUnit.employee_avg !== null || vsUnit.unit_avg !== null);

  return (
    <div className="space-y-5">
      <Card title="انتخاب فرد">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div className="flex flex-col gap-1 text-xs font-medium text-gray-600">
            پرسنل
            <PersonPicker
              value={personId}
              onChange={setPersonId}
              placeholder="— انتخاب فرد —"
              aria-label="انتخاب فرد برای کارنامه"
            />
          </div>
          <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
            دورهٔ ارزیابی (فقط روی مقایسه با واحد)
            <FilterSelect
              aria-label="دورهٔ ارزیابی"
              value={periodId !== null ? String(periodId) : ""}
              onChange={(v) => setPeriodId(v ? Number(v) : null)}
            >
              <option value="">همهٔ دوره‌ها</option>
              {periods.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </FilterSelect>
          </label>
        </div>
      </Card>

      {personId === null ? (
        <Card>
          <EmptyState>برای دیدن کارنامه، یک فرد انتخاب کنید.</EmptyState>
        </Card>
      ) : (
        <>
          <ChartDownloadCard
            title="مقایسهٔ امتیاز فرد با میانگین واحد سازمانی"
            subtitle="امتیاز نهایی وزنی (٪) این فرد، در برابر میانگین واحد سازمانی خودش"
            filename="employee-vs-unit.png"
          >
            {!hasComparison ? (
              <EmptyState>برای این فرد و این دوره نتیجهٔ نهایی‌شده‌ای وجود ندارد.</EmptyState>
            ) : (
              /* دو میلهٔ جدا، خواننده را وادار می‌کرد ارتفاع‌ها را با چشم تفریق کند؛
                 سؤال واقعی «چقدر فاصله؟» است، پس فاصله خودش نشانهٔ اصلی شد. */
              <Dumbbell
                a={{
                  label: vsUnit?.full_name ?? "این فرد",
                  value: vsUnit?.employee_avg ?? null,
                  note: `${faNum(vsUnit?.evaluation_count ?? 0)} ارزیابی`,
                }}
                b={{
                  label: `میانگین واحد «${vsUnit?.org_unit}»`,
                  value: vsUnit?.unit_avg ?? null,
                  note: `${faNum(vsUnit?.unit_evaluation_count ?? 0)} ارزیابی`,
                }}
                ariaLabel="مقایسهٔ امتیاز فرد با میانگین واحد سازمانی"
              />
            )}
          </ChartDownloadCard>

          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            <ChartDownloadCard
              title="شایستگی به تفکیک شاخص"
              subtitle="میانگین امتیاز این فرد در هر دسته (از ۵) — همهٔ دوره‌ها"
              filename="person-radar.png"
            >
              <CompetencyRadar data={radar} gradientId="scorecard-radar" />
            </ChartDownloadCard>
            <ChartDownloadCard
              title="روند امتیاز نهایی"
              subtitle="امتیاز نهایی وزنی (٪) در ارزیابی‌های پیاپی این فرد"
              filename="person-trend.png"
            >
              <ScoreTrend data={trend} gradientId="scorecard-trend" />
            </ChartDownloadCard>
          </div>
        </>
      )}
    </div>
  );
}
