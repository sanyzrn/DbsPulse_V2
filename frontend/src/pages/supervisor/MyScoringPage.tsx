/** آینهٔ ارزیاب (P2-01) — «من سخت‌گیرم یا آسان‌گیر، و کجا؟»
 *
 * مفیدترین بازخوردی که یک نمره‌دهنده می‌تواند بگیرد، و تا امروز هیچ نقشی جز
 * منابع انسانی به آن دسترسی نداشت. بدون این صفحه، «فلانی سخت‌گیر است» یک شایعهٔ
 * سازمانی می‌ماند به‌جای عددی که خودِ فرد ببیند و اصلاح کند.
 *
 * ترتیب صفحه از حکم به جزئیات است: اول یک جملهٔ فارسی که می‌گوید کجای طیف
 * ایستاده‌ای، بعد مقایسهٔ عددی، بعد توزیع، و آخر شاخص‌هایی که بیشترین فاصله را
 * دارند — چون همان‌ها هستند که کاری می‌شود درباره‌شان کرد.
 */
import { useQuery } from "@tanstack/react-query";
import { apiClient, extractErrorMessage } from "../../api/client";
import { Card, EmptyState, PageHeader, TableSkeleton } from "../../ui/Card";
import { DOT_COMPARE, DOT_STRONG, Dumbbell, fa1, faInt } from "../../ui/plot";

interface DistributionBucket {
  score: number;
  my_count: number;
  my_share_pct: number;
  org_share_pct: number | null;
}

interface IndicatorGap {
  indicator_id: number;
  category: string;
  description: string;
  my_avg: number | null;
  org_avg: number | null;
  my_count: number;
}

interface ScoringProfile {
  my_score_count: number;
  my_avg_score: number | null;
  org_avg_score: number | null;
  org_people_count: number;
  distribution: DistributionBucket[];
  indicator_gaps: IndicatorGap[];
  evidence_rate_pct: number | null;
  median_days_in_my_stage: number | null;
  open_with_me: number;
}

/** فاصله‌ای که «تفاوت سبک» حساب می‌شود، نه نوسان معمول.
 *
 * روی مقیاس ۱ تا ۵، اختلاف کمتر از یک‌دهم نمره عملاً نویز است؛ اسم گذاشتن رویش
 * به ارزیاب می‌گوید مشکلی هست که نیست. */
export const STYLE_THRESHOLD = 0.1;

export function verdict(mine: number | null, org: number | null): string {
  if (mine === null) return "هنوز نمرهٔ نهایی‌شده‌ای ثبت نکرده‌اید.";
  if (org === null)
    return "برای مقایسه با سازمان، هنوز به‌اندازهٔ کافی ارزیابی نهایی‌شده از دیگران وجود ندارد.";
  const gap = mine - org;
  if (Math.abs(gap) < STYLE_THRESHOLD) return "نمره‌دهی شما تقریباً هم‌تراز میانگین سازمان است.";
  return gap > 0
    ? "شما به‌طور میانگین نمره‌های بالاتری از بقیهٔ ارزیابان می‌دهید."
    : "شما به‌طور میانگین نمره‌های پایین‌تری از بقیهٔ ارزیابان می‌دهید.";
}

export function MyScoringPage() {
  const { data, isPending, error } = useQuery({
    queryKey: ["analytics", "my-scoring"],
    queryFn: async () => (await apiClient.get<ScoringProfile>("/analytics/my-scoring")).data,
  });

  if (error != null)
    return <p className="p-6 text-center text-sm text-red-600">{extractErrorMessage(error)}</p>;

  return (
    <div className="space-y-5">
      <PageHeader
        title="نمره‌دهی من"
        subtitle="نمره‌هایی که داده‌اید، در برابر نمره‌دهی بقیهٔ ارزیابان سازمان"
      />

      {isPending || !data ? (
        <Card>
          <TableSkeleton rows={5} />
        </Card>
      ) : data.my_score_count === 0 ? (
        <Card>
          <EmptyState>
            هنوز ارزیابی نهایی‌شده‌ای ندارید. این صفحه پس از نهایی‌شدن اولین پروندهٔ شما
            پر می‌شود — نمرهٔ پیش‌نویس هنوز تصمیم نیست و در آمار نمی‌آید.
          </EmptyState>
        </Card>
      ) : (
        <>
          <Card title="جایگاه شما">
            <p className="mb-4 text-sm text-gray-700">{verdict(data.my_avg_score, data.org_avg_score)}</p>
            <Dumbbell
              a={{
                label: "میانگین نمره‌های من",
                value: data.my_avg_score,
                note: `${faInt(data.my_score_count)} نمره`,
              }}
              b={{
                label: "میانگین بقیهٔ ارزیابان",
                value: data.org_avg_score,
                note: `${faInt(data.org_people_count)} نفر`,
              }}
              min={1}
              max={5}
              ticks={[1, 2, 3, 4, 5]}
              format={fa1}
              ariaLabel="میانگین نمره‌دهی من در برابر بقیهٔ ارزیابان"
            />
          </Card>

          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            <Card title="توزیع نمره‌هایی که داده‌اید">
              <p className="mb-4 text-xs text-gray-500">
                درصد است نه تعداد — تعدادِ نمره‌های شما با کل سازمان قابل مقایسه نیست.
              </p>
              <DistributionBars buckets={data.distribution} />
            </Card>

            <Card title="کیفیت و سرعت کار شما">
              <dl className="space-y-4">
                <Stat
                  label="نمره‌هایی که شواهد نوشته دارند"
                  value={data.evidence_rate_pct !== null ? `${fa1(data.evidence_rate_pct)}٪` : "—"}
                  hint="قاعدهٔ اجباری فقط نمرهٔ ۱ و ۵ را می‌گیرد؛ این عدد نشان می‌دهد فراتر از اجبار چقدر شواهد می‌نویسید."
                />
                <Stat
                  label="پرونده‌های باز روی میز شما"
                  value={faInt(data.open_with_me)}
                  hint="پیش‌نویس‌هایی که هنوز ثبت نشده‌اند و زنجیره منتظرشان است."
                />
                <Stat
                  label="میانهٔ انتظار همان پرونده‌ها"
                  value={
                    data.median_days_in_my_stage !== null
                      ? `${fa1(data.median_days_in_my_stage)} روز`
                      : "—"
                  }
                  hint="چند روز است پیش‌نویس‌های باز شما در مرحلهٔ خودتان مانده‌اند."
                />
              </dl>
            </Card>
          </div>

          <Card title="شاخص‌هایی که بیشترین فاصله را دارند">
            <p className="mb-4 text-xs text-gray-500">
              مرتب‌شده بر اساس بزرگیِ فاصله با بقیه — نه ترتیب فرم. جایی که فاصله بزرگ
              است، یا برداشت شما از آن شاخص با بقیه فرق دارد یا زیرمجموعهٔ شما واقعاً
              متفاوت است؛ هر دو ارزش گفت‌وگو دارند.
            </p>
            <GapTable gaps={data.indicator_gaps} />
          </Card>
        </>
      )}
    </div>
  );
}

function Stat({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div>
      <dt className="text-xs text-gray-500">{label}</dt>
      <dd className="mt-0.5 text-xl font-extrabold tabular-nums text-gray-900">{value}</dd>
      <p className="mt-1 text-[11px] leading-relaxed text-gray-400">{hint}</p>
    </div>
  );
}

/** دو نوار هم‌ردیف برای هر نمره: سهم من، سهم بقیه.
 *
 * این‌جا عمداً نوار است نه نقطه: سؤال «کدام بزرگ‌تر است» نیست، «شکل توزیع چطور
 * است» است — و شکل را با طول کنار هم بهتر می‌شود خواند تا با موقعیت نقطه. */
function DistributionBars({ buckets }: { buckets: DistributionBucket[] }) {
  const peak = Math.max(1, ...buckets.flatMap((b) => [b.my_share_pct, b.org_share_pct ?? 0]));
  return (
    <div className="space-y-3">
      {buckets.map((bucket) => (
        <div key={bucket.score} className="grid grid-cols-[1.5rem_minmax(0,1fr)] items-center gap-3">
          <span className="text-sm font-bold tabular-nums text-gray-600">
            {faInt(bucket.score)}
          </span>
          <span className="space-y-1">
            <Bar share={bucket.my_share_pct} peak={peak} color={DOT_STRONG} />
            <Bar share={bucket.org_share_pct} peak={peak} color={DOT_COMPARE} />
          </span>
        </div>
      ))}
      <p className="flex flex-wrap gap-x-4 gap-y-1 border-t border-gray-100 pt-3 text-[11px] text-gray-500">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full" style={{ backgroundColor: DOT_STRONG }} aria-hidden />
          من
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full" style={{ backgroundColor: DOT_COMPARE }} aria-hidden />
          بقیهٔ ارزیابان
        </span>
      </p>
    </div>
  );
}

function Bar({ share, peak, color }: { share: number | null; peak: number; color: string }) {
  if (share === null)
    return <span className="block h-2 text-[10px] leading-none text-gray-300">محرمانه</span>;
  return (
    <span className="flex items-center gap-2">
      <span className="h-2 flex-1 overflow-hidden rounded-full bg-gray-100">
        <span
          className="block h-full rounded-full"
          style={{ width: `${(share / peak) * 100}%`, backgroundColor: color }}
        />
      </span>
      <span className="w-10 shrink-0 text-left text-[10px] tabular-nums text-gray-500" dir="ltr">
        {fa1(share)}٪
      </span>
    </span>
  );
}

function GapTable({ gaps }: { gaps: IndicatorGap[] }) {
  if (gaps.length === 0) return <EmptyState>هنوز شاخصی با نمرهٔ نهایی‌شده ندارید.</EmptyState>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-100 text-xs text-gray-500">
            <th className="px-2 py-2 text-right font-semibold">شاخص</th>
            <th className="px-2 py-2 text-right font-semibold">من</th>
            <th className="px-2 py-2 text-right font-semibold">بقیه</th>
            <th className="px-2 py-2 text-right font-semibold">فاصله</th>
          </tr>
        </thead>
        <tbody>
          {gaps.map((gap) => {
            const delta = gap.my_avg !== null && gap.org_avg !== null ? gap.my_avg - gap.org_avg : null;
            return (
              <tr key={gap.indicator_id} className="border-b border-gray-50 last:border-0">
                <td className="max-w-xs px-2 py-2.5">
                  <span className="block truncate text-gray-700" title={gap.description}>
                    {gap.description}
                  </span>
                  <span className="text-[10px] text-gray-400">{gap.category}</span>
                </td>
                <td className="px-2 py-2.5 tabular-nums text-gray-900">
                  {gap.my_avg !== null ? fa1(gap.my_avg) : "—"}
                </td>
                <td className="px-2 py-2.5 tabular-nums text-gray-500">
                  {gap.org_avg !== null ? fa1(gap.org_avg) : "محرمانه"}
                </td>
                <td className="px-2 py-2.5">
                  {delta === null ? (
                    <span className="text-gray-300">—</span>
                  ) : (
                    <span
                      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium tabular-nums ${
                        Math.abs(delta) < STYLE_THRESHOLD
                          ? "bg-gray-100 text-gray-600"
                          : delta > 0
                            ? "bg-green-50 text-green-700"
                            : "bg-amber-50 text-amber-700"
                      }`}
                    >
                      {delta > 0 ? "+" : delta < 0 ? "−" : ""}
                      {fa1(Math.abs(delta))}
                    </span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
