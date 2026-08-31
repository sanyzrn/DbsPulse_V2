/** دیدگاه خودِ کارمند، کنار امتیاز ارزیاب (P0-06).
 *
 * هدف نمایش «اختلاف» است، نه میانگین‌گیری: جایی که فرد ۵ داده و ارزیاب ۲، همان جایی
 * است که گفت‌وگو لازم است. این عدد هیچ‌وقت وارد محاسبه نمی‌شود — در بک‌اند هم جدولش
 * جداست تا این تضمین ساختاری باشد نه یک شرطِ فراموش‌شدنی.
 */
import type { EvaluationDetail, Indicator } from "../types";
import { formatDateTime } from "../utils/dates";

export function SelfAssessmentPanel({
  evaluation,
  indicators,
}: {
  evaluation: EvaluationDetail;
  indicators: Indicator[];
}) {
  const self = evaluation.self_assessment;
  if (!self?.submitted_at) return null;

  const evaluatorByIndicator = new Map(evaluation.scores.map((s) => [s.indicator_id, s.score]));
  const indicatorById = new Map(indicators.map((i) => [i.id, i]));

  // بیشترین اختلاف‌ها بالا می‌آیند — همان‌هایی که ارزشِ حرف‌زدن دارند
  const rows = self.scores
    .map((row) => {
      const evaluatorScore = evaluatorByIndicator.get(row.indicator_id) ?? null;
      return {
        ...row,
        evaluatorScore,
        gap: evaluatorScore === null ? 0 : row.score - evaluatorScore,
        indicator: indicatorById.get(row.indicator_id),
      };
    })
    .sort((a, b) => Math.abs(b.gap) - Math.abs(a.gap));
  const comparable = rows.filter((row) => row.evaluatorScore !== null);
  const selfAverage = comparable.length
    ? comparable.reduce((sum, row) => sum + row.score, 0) / comparable.length
    : 0;
  const evaluatorAverage = comparable.length
    ? comparable.reduce((sum, row) => sum + (row.evaluatorScore ?? 0), 0) / comparable.length
    : 0;
  const averageGap = selfAverage - evaluatorAverage;
  const faScore = (value: number) =>
    value.toLocaleString("fa-IR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4">
      <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-bold text-gray-900">مقایسهٔ ارزیابی مدیر و خودارزیابی</h2>
        <span className="text-xs text-gray-500">ثبت‌شده در {formatDateTime(self.submitted_at)}</span>
      </div>
      <p className="mb-4 text-xs text-gray-500">
        این امتیازها در محاسبهٔ نتیجه وارد نمی‌شوند؛ فقط برای دیدن تفاوت دیدگاه‌ها نمایش
        داده می‌شوند. بیشترین اختلاف‌ها اول آمده‌اند.
      </p>

      {self.note && (
        <p className="mb-4 rounded-xl bg-gray-50 px-3 py-2 text-sm text-gray-700">
          <span className="text-xs text-gray-500">دستاورد کلی از نگاه خودش: </span>
          {self.note}
        </p>
      )}

      {comparable.length > 0 && (
        <div className="mb-4 grid grid-cols-3 gap-2">
          <div className="rounded-xl bg-gray-50 px-3 py-2 text-center">
            <p className="text-[11px] text-gray-500">میانگین خودارزیابی</p>
            <p className="mt-1 text-base font-bold tabular-nums text-gray-900">{faScore(selfAverage)}</p>
          </div>
          <div className="rounded-xl bg-gray-50 px-3 py-2 text-center">
            <p className="text-[11px] text-gray-500">میانگین ارزیابی مدیر</p>
            <p className="mt-1 text-base font-bold tabular-nums text-gray-900">{faScore(evaluatorAverage)}</p>
          </div>
          <div className="rounded-xl bg-gray-50 px-3 py-2 text-center">
            <p className="text-[11px] text-gray-500">فاصلهٔ میانگین</p>
            <p className="mt-1 text-base font-bold tabular-nums text-gray-900">
              {averageGap > 0 ? "+" : ""}{faScore(averageGap)}
            </p>
          </div>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 text-xs text-gray-500">
              <th className="p-2 text-start font-medium">شاخص</th>
              <th className="p-2 text-center font-medium">خودِ فرد</th>
              <th className="p-2 text-center font-medium">ارزیاب</th>
              <th className="p-2 text-center font-medium">اختلاف</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.indicator_id} className="border-b border-gray-50 last:border-0">
                <td className="p-2">
                  <span className="text-gray-800">{row.indicator?.description ?? `#${row.indicator_id}`}</span>
                  {row.note && <p className="mt-0.5 text-xs text-gray-500">{row.note}</p>}
                </td>
                <td className="p-2 text-center tabular-nums text-gray-800">
                  {row.score.toLocaleString("fa-IR")}
                </td>
                <td className="p-2 text-center tabular-nums text-gray-800">
                  {row.evaluatorScore === null ? "—" : row.evaluatorScore.toLocaleString("fa-IR")}
                </td>
                <td className="p-2 text-center">
                  <GapBadge gap={row.gap} known={row.evaluatorScore !== null} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function GapBadge({ gap, known }: { gap: number; known: boolean }) {
  if (!known) return <span className="text-xs text-gray-400">—</span>;
  if (gap === 0) return <span className="text-xs text-gray-400">هم‌نظر</span>;
  // اختلاف ۲ نمره یا بیشتر آن چیزی است که واقعاً باید دربارهٔ آن حرف زد
  const strong = Math.abs(gap) >= 2;
  const tone = strong ? "bg-amber-50 text-amber-800" : "bg-gray-100 text-gray-600";
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium tabular-nums ${tone}`}>
      {gap > 0 ? "+" : "−"}
      {Math.abs(gap).toLocaleString("fa-IR")}
    </span>
  );
}
