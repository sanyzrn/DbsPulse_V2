/** «میانگین امتیاز هر شاخص» — نمای گروهیِ دسته‌ها به‌جای فهرست تختِ بیست میله.
 *
 * چرا میله‌ی افقی این‌جا جواب نمی‌داد (سه دلیل، هیچ‌کدام سلیقه‌ای نیست):
 *
 * ۱. دامنهٔ نمره ۱ تا ۵ است، ولی میله از صفر شروع می‌شد. یعنی یک‌چهارم ابتدای هر
 *    میله سهمی بود که هر شاخصی *به‌طور قطعی* دارد، و تفاوت واقعی — مثلاً ۳٫۶ در
 *    برابر ۴٫۲ — در یک‌پنجم انتهایی فشرده می‌شد. نتیجه بیست میلهٔ تقریباً هم‌قد بود.
 *    این‌جا محور از ۱ شروع می‌شود، پس همان تفاوت کل عرض ریل را می‌گیرد.
 * ۲. شرح شاخص‌ها ۵۶ تا ۷۹ نویسه است. هیچ ستون محوری در کنار میله جای‌شان نمی‌دهد؛
 *    نسخهٔ قبلی به ~۳۳ نویسه می‌بریدشان، پس نیمی از هر برچسب گم می‌شد. حالا برچسبِ
 *    ردیف «دسته» است (کوتاه و کامل جا می‌شود) و شرحِ کامل با بازکردن دسته می‌آید.
 * ۳. بیست ردیف یک‌شکل پشت سر هم. داده خودش سلسله‌مراتب دارد — دو بخش، ده دسته،
 *    بیست شاخص — و نمودار قبلی این ساختار را دور می‌ریخت و تخت نشانش می‌داد.
 *
 * میانگین هر دسته «میانگینِ میانگین‌ها» نیست: با `count` وزن داده می‌شود، پس دقیقاً
 * میانگین همهٔ نمره‌های آن دسته است. شاخص‌های سرکوب‌شدهٔ P1-08 (avg_score = null)
 * کنار گذاشته می‌شوند و تعدادشان در همان دسته اعلام می‌شود — صفر گرفتنشان دروغ بود.
 */
import { useMemo, useState } from "react";
import type { IndicatorReportStat } from "../types";

const MIN_SCORE = 1;
const MAX_SCORE = 5;
const TICKS = [1, 2, 3, 4, 5];

const SECTION_LABEL: Record<string, string> = {
  general: "شاخص‌های عمومی",
  specialized: "شاخص‌های تخصصی",
};

/** الگوی ستون‌ها یک‌جا تعریف می‌شود تا خط‌کش بالای هر بخش و ریل همهٔ ردیف‌ها —
 * چه دسته و چه شاخص — دقیقاً هم‌تراز بمانند.
 *
 * عدد بین برچسب و ریل می‌نشیند، نه انتهای ردیف: نام دسته‌ها کوتاه است و اگر عدد
 * آن‌سوی ریل برود، وسط هر ردیف یک شکاف خالی می‌ماند.
 *
 * روی موبایل سهم ریل کمتر است، وگرنه نام دسته به «مسئولیت‌پذی…» می‌رسد و روی لمس
 * هم tooltip‌ای در کار نیست که متن کامل را نشان دهد. */
const ROW_GRID =
  "grid grid-cols-[minmax(0,1fr)_2.5rem_38%] sm:grid-cols-[minmax(0,1fr)_2.5rem_50%] items-center gap-x-2";

const RAIL = "#f1f2f4";
const LEAD_STRONG = "#f49f9f";
const LEAD_SOFT = "#facaca";
const DOT_STRONG = "#b61615";
const DOT_SOFT = "#eb4847";

const fa1 = (value: number) =>
  value.toLocaleString("fa-IR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const faInt = (value: number) => value.toLocaleString("fa-IR");

const offset = (value: number) =>
  Math.min(100, Math.max(0, ((value - MIN_SCORE) / (MAX_SCORE - MIN_SCORE)) * 100));

export type IndicatorSort = "form" | "lowest";

interface IndicatorRow {
  id: number;
  description: string;
  value: number;
  count: number;
}

interface CategoryRow {
  key: string;
  category: string;
  value: number;
  indicators: IndicatorRow[];
  hidden: number;
}

interface SectionBlock {
  key: string;
  label: string;
  value: number | null;
  indicatorCount: number;
  categories: CategoryRow[];
}

/** میانگین وزنی بر حسب تعداد نمره — نه میانگینِ میانگین‌ها. */
function weightedMean(rows: { value: number; count: number }[]): number | null {
  const weight = rows.reduce((sum, r) => sum + r.count, 0);
  if (weight === 0) return null;
  return rows.reduce((sum, r) => sum + r.value * r.count, 0) / weight;
}

function buildSections(stats: IndicatorReportStat[], sort: IndicatorSort): SectionBlock[] {
  // ترتیب درجِ Map حفظ می‌شود، و سرور از قبل بر اساس (section, display_order)
  // مرتب فرستاده — پس حالت «ترتیب فرم ارزیابی» بدون کار اضافه به‌دست می‌آید.
  const sections = new Map<string, Map<string, IndicatorReportStat[]>>();
  for (const stat of stats) {
    let categories = sections.get(stat.section);
    if (!categories) sections.set(stat.section, (categories = new Map()));
    const bucket = categories.get(stat.category);
    if (bucket) bucket.push(stat);
    else categories.set(stat.category, [stat]);
  }

  const blocks: SectionBlock[] = [];
  for (const [sectionKey, categories] of sections) {
    const rows: CategoryRow[] = [];
    for (const [category, stats_] of categories) {
      const visible = stats_.filter((s) => s.avg_score !== null);
      const indicators = visible.map((s) => ({
        id: s.indicator_id,
        description: s.description,
        value: s.avg_score!,
        count: s.count,
      }));
      const value = weightedMean(indicators);
      if (value === null) continue;
      if (sort === "lowest") indicators.sort((a, b) => a.value - b.value);
      rows.push({
        key: `${sectionKey}::${category}`,
        category,
        value,
        indicators,
        hidden: stats_.length - visible.length,
      });
    }
    if (rows.length === 0) continue;
    if (sort === "lowest") rows.sort((a, b) => a.value - b.value);
    blocks.push({
      key: sectionKey,
      label: SECTION_LABEL[sectionKey] ?? sectionKey,
      value: weightedMean(rows.flatMap((r) => r.indicators)),
      indicatorCount: rows.reduce((sum, r) => sum + r.indicators.length, 0),
      categories: rows,
    });
  }
  return blocks;
}

/** ریل ۱ تا ۵ با نقطه روی مقدار، به‌علاوهٔ نشانگر چین‌چینِ میانگین کل.
 *
 * نقطه با یک ظرفِ عرض‌صفرِ flex روی مقدار مرکز می‌شود نه با translate: ترجمه در
 * RTL باید علامتش عوض شود، ولی `justify-center` در هر دو جهت درست کار می‌کند. */
function Track({
  value,
  reference,
  strong = false,
}: {
  value: number;
  reference: number | null;
  strong?: boolean;
}) {
  const position = offset(value);
  return (
    <span className="relative block h-4">
      <span
        className="absolute inset-x-0 top-1/2 block h-[5px] -translate-y-1/2 rounded-full"
        style={{ backgroundColor: RAIL }}
      />
      <span
        className="absolute top-1/2 block h-[5px] -translate-y-1/2 rounded-full"
        style={{
          insetInlineStart: 0,
          width: `${position}%`,
          backgroundColor: strong ? LEAD_STRONG : LEAD_SOFT,
        }}
      />
      {reference !== null && (
        <span
          className="absolute inset-y-0 flex w-0 justify-center"
          style={{ insetInlineStart: `${offset(reference)}%` }}
          aria-hidden
        >
          <span className="block w-0 self-stretch border-s border-dashed border-gray-300" />
        </span>
      )}
      <span
        className="absolute top-1/2 flex w-0 -translate-y-1/2 justify-center"
        style={{ insetInlineStart: `${position}%` }}
      >
        <span
          // هندسه در تست خوانده می‌شود: نقطهٔ نمرهٔ ۱ باید روی صفر درصد بنشیند،
          // نه روی ۲۰٪ — همان اشتباهی که میلهٔ از-صفر مرتکب می‌شد.
          data-testid="score-dot"
          data-offset={position.toFixed(1)}
          // shrink-0 حیاتی است: ظرف عرض‌صفر است و بدون آن، flex نقطه را تا صفر
          // جمع می‌کند و اصلاً دیده نمی‌شود.
          className="block shrink-0 rounded-full ring-2 ring-white"
          style={{
            width: strong ? 11 : 8,
            height: strong ? 11 : 8,
            backgroundColor: strong ? DOT_STRONG : DOT_SOFT,
          }}
        />
      </span>
    </span>
  );
}

export function IndicatorScorePanel({
  stats,
  sort = "form",
}: {
  stats: IndicatorReportStat[];
  sort?: IndicatorSort;
}) {
  const sections = useMemo(() => buildSections(stats, sort), [stats, sort]);
  const reference = useMemo(
    () =>
      weightedMean(
        stats
          .filter((s) => s.avg_score !== null)
          .map((s) => ({ value: s.avg_score!, count: s.count })),
      ),
    [stats],
  );
  const [open, setOpen] = useState<ReadonlySet<string>>(new Set());

  function toggle(key: string) {
    setOpen((prev) => {
      const next = new Set(prev);
      if (!next.delete(key)) next.add(key);
      return next;
    });
  }

  return (
    // برچسب‌های ۱ و ۵ روی دو سر ریل مرکز می‌شوند، پس نیمی از هر کدام بیرون می‌زند؛
    // بدون این حاشیه، خروجی PNG (که دقیقاً به اندازهٔ همین جعبه بریده می‌شود) آن‌ها
    // را می‌بُرد.
    <div className="px-2">
      {/* دو بخش کنار هم ارتفاع را نصف می‌کند؛ ولی با یک بخش، دو ستونه یعنی نیمی از
          کارت خالی بماند. */}
      <div
        className={`grid grid-cols-1 gap-x-8 gap-y-7 ${sections.length > 1 ? "lg:grid-cols-2" : ""}`}
      >
        {sections.map((section) => (
          <section key={section.key}>
            <div className="mb-2 flex items-baseline justify-between gap-2 border-b border-gray-100 pb-1.5">
              <h4 className="text-[13px] font-bold text-gray-800">{section.label}</h4>
              <span className="text-[11px] text-gray-400">
                {faInt(section.indicatorCount)} شاخص
                {section.value !== null && <> · میانگین {fa1(section.value)}</>}
              </span>
            </div>

            {/* خط‌کش مشترک — یک بار در بالای بخش، نه یک محور زیر هر میله */}
            <div className={`${ROW_GRID} mb-2`} aria-hidden>
              <span />
              <span />
              <span className="relative block h-3">
                {TICKS.map((tick) => (
                  <span
                    key={tick}
                    className="absolute top-0 flex w-0 justify-center"
                    style={{ insetInlineStart: `${offset(tick)}%` }}
                  >
                    <span className="shrink-0 text-[9px] leading-3 text-gray-400">
                      {faInt(tick)}
                    </span>
                  </span>
                ))}
              </span>
            </div>

            <div>
              {section.categories.map((category) => {
                const isOpen = open.has(category.key);
                return (
                  <div key={category.key}>
                    <button
                      type="button"
                      onClick={() => toggle(category.key)}
                      aria-expanded={isOpen}
                      title={`${category.category} — میانگین ${fa1(category.value)} از ۵`}
                      className={`${ROW_GRID} w-full rounded-lg px-1.5 py-1.5 text-start transition-colors hover:bg-gray-50`}
                    >
                      <span className="flex min-w-0 items-center gap-1.5">
                        <svg
                          viewBox="0 0 20 20"
                          className={`h-3 w-3 shrink-0 text-gray-300 transition-transform duration-200 ${isOpen ? "" : "rotate-90"}`}
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2.4"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          aria-hidden
                        >
                          <path d="M5 8l5 5 5-5" />
                        </svg>
                        <span className="truncate text-[12px] font-medium text-gray-700">
                          {category.category}
                        </span>
                        <span
                          className="shrink-0 text-[10px] text-gray-400"
                          title={`${faInt(category.indicators.length)} شاخص در این دسته`}
                        >
                          ({faInt(category.indicators.length)})
                        </span>
                      </span>
                      <span className="text-[12px] font-bold tabular-nums text-gray-900">
                        {fa1(category.value)}
                      </span>
                      <Track value={category.value} reference={reference} strong />
                    </button>

                    {isOpen && (
                      <div className="mb-1 mt-0.5 space-y-2.5 rounded-xl bg-gray-50 px-1.5 py-2.5">
                        {category.indicators.map((indicator) => (
                          <div key={indicator.id}>
                            <p className="mb-1 ps-[1.125rem] text-[11px] leading-5 text-gray-600">
                              {indicator.description}
                            </p>
                            <div className={ROW_GRID}>
                              <span className="truncate ps-[1.125rem] text-[10px] text-gray-400">
                                {faInt(indicator.count)} نمره
                              </span>
                              <span className="text-[11px] font-semibold tabular-nums text-gray-700">
                                {fa1(indicator.value)}
                              </span>
                              <Track value={indicator.value} reference={reference} />
                            </div>
                          </div>
                        ))}
                        {category.hidden > 0 && (
                          <p className="ps-[1.125rem] text-[10px] leading-4 text-gray-400">
                            {faInt(category.hidden)} شاخص به دلیل کم‌بودن تعداد نمره نمایش داده
                            نشده است.
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </section>
        ))}
      </div>

      <p className="mt-5 flex flex-wrap items-center gap-x-5 gap-y-1.5 border-t border-gray-100 pt-3 text-[11px] text-gray-500">
        <span className="inline-flex items-center gap-1.5">
          <span
            className="inline-block h-2.5 w-2.5 rounded-full"
            style={{ backgroundColor: DOT_STRONG }}
            aria-hidden
          />
          میانگین وزنی دسته
        </span>
        {reference !== null && (
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block h-3 w-0 border-s border-dashed border-gray-400" aria-hidden />
            میانگین کل: {fa1(reference)}
          </span>
        )}
        <span>محور از ۱ شروع می‌شود (کمینهٔ نمره)، نه از صفر.</span>
      </p>
    </div>
  );
}
