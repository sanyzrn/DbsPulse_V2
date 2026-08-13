/** واژگان مشترک نمودارهای «بزرگی» — ریل، نقطه، خط‌کش.
 *
 * پیش از این هر نمودار میلهٔ افقیِ خودش را داشت و هر بار یک ایراد تکرار می‌شد.
 * این‌جا یک شکل واحد تعریف شده و همهٔ نمودارهای مقایسه‌ای از آن استفاده می‌کنند:
 * ریل نازکِ خنثی برای «کل دامنه»، بخش پررنگ تا مقدار، و یک نقطه روی خودِ مقدار.
 *
 * چرا نقطه به‌جای میلهٔ توپر: میله سطح رنگی بزرگی می‌سازد که با چند ردیف به بلوک
 * تبدیل می‌شود؛ چیزی که واقعاً خوانده می‌شود *موقعیت* نوک میله است. نقطه همان
 * موقعیت را با یک‌دهم جوهر می‌دهد.
 *
 * نکتهٔ RTL: مرکز‌کردن یک نشانه روی مقدار با `translateX` انجام نمی‌شود — علامتش
 * باید در RTL برعکس شود. به‌جایش یک ظرف عرض‌صفرِ flex با `justify-center` می‌گذاریم
 * که در هر دو جهت درست کار می‌کند. فرزندش حتماً `shrink-0` می‌خواهد، وگرنه در ظرف
 * صفرعرض تا صفر جمع می‌شود و اصلاً دیده نمی‌شود.
 */
import type { ReactNode } from "react";

export const RAIL = "#f1f2f4";
export const LEAD_STRONG = "#f49f9f";
export const LEAD_SOFT = "#facaca";
export const DOT_STRONG = "#b61615";
export const DOT_SOFT = "#eb4847";
/** رنگ دوم فقط برای مقایسهٔ دو مقدار روی یک ریل (فرد در برابر واحد) */
export const DOT_COMPARE = "#6b7280";

export const faInt = (value: number) => value.toLocaleString("fa-IR");
export const fa1 = (value: number) =>
  value.toLocaleString("fa-IR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
export const faPct = (value: number) => `${Math.round(value).toLocaleString("fa-IR")}٪`;

export function offsetIn(value: number, min: number, max: number): number {
  if (max === min) return 0;
  return Math.min(100, Math.max(0, ((value - min) / (max - min)) * 100));
}

/** ظرف مرکز‌شونده روی یک نقطه از ریل — پایهٔ همهٔ نشانه‌ها (نقطه، برچسب، خط راهنما). */
function AtOffset({ offset, children }: { offset: number; children: ReactNode }) {
  return (
    <span
      className="absolute inset-y-0 flex w-0 items-center justify-center"
      style={{ insetInlineStart: `${offset}%` }}
    >
      {children}
    </span>
  );
}

export interface TrackMark {
  value: number;
  color?: string;
  size?: number;
  title?: string;
}

/** ریل با یک یا چند نقطه. با دو نقطه، همان چیزی می‌شود که به آن dumbbell می‌گویند
 *  و فاصلهٔ دو مقدار را مستقیم نشان می‌دهد — کاری که دو میلهٔ جدا نمی‌کند. */
export function Track({
  marks,
  min,
  max,
  reference,
  lead = true,
}: {
  marks: TrackMark[];
  min: number;
  max: number;
  reference?: number | null;
  /** بخش پررنگ از ابتدای ریل تا مقدار. با دو نقطه، *بین* آن دو کشیده می‌شود. */
  lead?: boolean;
}) {
  const points = marks.map((m) => ({ ...m, offset: offsetIn(m.value, min, max) }));
  const from = Math.min(...points.map((p) => p.offset));
  const to = Math.max(...points.map((p) => p.offset));
  const isPair = points.length > 1;

  return (
    <span className="relative block h-4">
      <span
        className="absolute inset-x-0 top-1/2 block h-[5px] -translate-y-1/2 rounded-full"
        style={{ backgroundColor: RAIL }}
      />
      {lead && (
        <span
          className="absolute top-1/2 block h-[5px] -translate-y-1/2 rounded-full"
          style={{
            insetInlineStart: `${isPair ? from : 0}%`,
            width: `${isPair ? to - from : to}%`,
            backgroundColor: isPair ? LEAD_SOFT : LEAD_STRONG,
          }}
        />
      )}
      {reference != null && (
        <AtOffset offset={offsetIn(reference, min, max)}>
          <span className="block w-0 shrink-0 self-stretch border-s border-dashed border-gray-300" />
        </AtOffset>
      )}
      {points.map((p, i) => (
        <AtOffset key={i} offset={p.offset}>
          <span
            data-testid="plot-dot"
            data-offset={p.offset.toFixed(1)}
            title={p.title}
            className="block shrink-0 rounded-full ring-2 ring-white"
            style={{
              width: p.size ?? 11,
              height: p.size ?? 11,
              backgroundColor: p.color ?? DOT_STRONG,
            }}
          />
        </AtOffset>
      ))}
    </span>
  );
}

/** خط‌کش — یک بار بالای فهرست، نه یک محور زیر هر ردیف. */
export function ScaleTicks({
  ticks,
  min,
  max,
  format = faInt,
}: {
  ticks: number[];
  min: number;
  max: number;
  format?: (value: number) => string;
}) {
  return (
    <span className="relative block h-3" aria-hidden>
      {ticks.map((tick) => (
        <AtOffset key={tick} offset={offsetIn(tick, min, max)}>
          <span className="shrink-0 whitespace-nowrap text-[9px] leading-3 text-gray-400">
            {format(tick)}
          </span>
        </AtOffset>
      ))}
    </span>
  );
}

/** الگوی ستون‌ها: برچسب · عدد · ریل.
 *
 * عدد بین برچسب و ریل می‌نشیند نه انتهای ردیف — نام‌ها کوتاه‌اند و اگر عدد آن‌سوی
 * ریل برود، وسط هر ردیف یک شکاف خالی می‌ماند. روی موبایل سهم ریل کمتر است تا نام
 * کامل جا شود (آن‌جا tooltipای هم در کار نیست که متن بریده را نشان دهد).
 */
export const ROW_GRID =
  "grid grid-cols-[minmax(0,1fr)_2.5rem_38%] sm:grid-cols-[minmax(0,1fr)_2.5rem_50%] items-center gap-x-2";

export interface DotRow {
  key: string | number;
  label: string;
  value: number;
  /** متن کوچک زیر/کنار برچسب، مثلاً تعداد نمونه */
  note?: string;
  title?: string;
}

export interface GapSide {
  label: string;
  value: number | null;
  note?: string;
}

/** مقایسهٔ دو مقدار روی *یک* ریل مشترک.
 *
 * دو میلهٔ جدا، خواننده را وادار می‌کرد ارتفاع‌ها را با چشم تفریق کند. چیزی که
 * واقعاً پرسیده می‌شود «چقدر فاصله؟» است، پس فاصله خودش نشانهٔ اصلی می‌شود: بخش
 * پررنگ ریل *بین* دو نقطه کشیده می‌شود و مقدارش با کلمه هم نوشته می‌شود.
 */
export function Dumbbell({
  a,
  b,
  min = 0,
  max = 100,
  format = faPct,
  ticks,
  ariaLabel,
}: {
  a: GapSide;
  b: GapSide;
  min?: number;
  max?: number;
  format?: (value: number) => string;
  ticks?: number[];
  ariaLabel?: string;
}) {
  const scale = ticks ?? [0, 1, 2, 3, 4].map((i) => min + ((max - min) * i) / 4);
  const marks: TrackMark[] = [];
  if (a.value != null) marks.push({ value: a.value, color: DOT_STRONG, title: a.label });
  if (b.value != null) marks.push({ value: b.value, color: DOT_COMPARE, title: b.label });

  const gap = a.value != null && b.value != null ? a.value - b.value : null;

  return (
    <div className="px-2" role="img" aria-label={ariaLabel}>
      <ScaleTicks ticks={scale} min={min} max={max} format={format} />
      <div className="mt-1.5">
        {marks.length > 0 ? (
          <Track marks={marks} min={min} max={max} />
        ) : (
          <p className="py-3 text-center text-sm text-gray-400">مقداری برای مقایسه وجود ندارد.</p>
        )}
      </div>

      <dl className="mt-4 space-y-1.5">
        {[
          { side: a, color: DOT_STRONG },
          { side: b, color: DOT_COMPARE },
        ].map(({ side, color }) => (
          <div key={side.label} className="flex items-baseline gap-2 text-[12px]">
            <span
              className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
              style={{ backgroundColor: color }}
              aria-hidden
            />
            <dt className="min-w-0 flex-1 truncate text-gray-600">{side.label}</dt>
            {side.note && <span className="shrink-0 text-[10px] text-gray-400">{side.note}</span>}
            <dd className="shrink-0 font-bold tabular-nums text-gray-900">
              {side.value != null ? format(side.value) : "—"}
            </dd>
          </div>
        ))}
      </dl>

      {gap != null && (
        <p className="mt-3 border-t border-gray-100 pt-3 text-[12px] text-gray-600">
          {Math.abs(gap) < 0.05 ? (
            <>دقیقاً هم‌تراز {b.label} است.</>
          ) : (
            <>
              <span className="font-bold text-gray-900">{format(Math.abs(gap))}</span>{" "}
              {gap > 0 ? "بالاتر از" : "پایین‌تر از"} {b.label}
            </>
          )}
        </p>
      )}
    </div>
  );
}

/** فهرست رتبه‌ای مقادیر روی یک دامنهٔ مشترک — جایگزین نمودار میلهٔ افقی. */
export function DotPlot({
  rows,
  min = 0,
  max = 100,
  ticks,
  reference,
  format = faPct,
  ariaLabel,
  footer,
}: {
  rows: DotRow[];
  min?: number;
  max?: number;
  ticks?: number[];
  reference?: number | null;
  format?: (value: number) => string;
  ariaLabel?: string;
  footer?: ReactNode;
}) {
  const scale = ticks ?? [0, 1, 2, 3, 4].map((i) => min + ((max - min) * i) / 4);

  return (
    // برچسب دو سرِ خط‌کش روی لبه مرکز می‌شوند و نیمی‌شان بیرون می‌زند؛ بدون این
    // حاشیه، خروجی PNG که دقیقاً به اندازهٔ همین جعبه بریده می‌شود آن‌ها را می‌بُرد.
    <div className="px-2" role="img" aria-label={ariaLabel}>
      <div className={`${ROW_GRID} mb-2`}>
        <span />
        <span />
        <ScaleTicks ticks={scale} min={min} max={max} format={format} />
      </div>

      <div>
        {rows.map((row) => (
          <div key={row.key} className={`${ROW_GRID} rounded-lg px-1.5 py-1.5`} title={row.title}>
            <span className="flex min-w-0 items-baseline gap-1.5">
              <span className="truncate text-[12px] font-medium text-gray-700">{row.label}</span>
              {row.note && (
                <span className="shrink-0 text-[10px] text-gray-400">{row.note}</span>
              )}
            </span>
            <span className="text-[12px] font-bold tabular-nums text-gray-900">
              {format(row.value)}
            </span>
            <Track marks={[{ value: row.value }]} min={min} max={max} reference={reference} />
          </div>
        ))}
      </div>

      {(footer || reference != null) && (
        <p className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-1.5 border-t border-gray-100 pt-3 text-[11px] text-gray-500">
          {reference != null && (
            <span className="inline-flex items-center gap-1.5">
              <span
                className="inline-block h-3 w-0 border-s border-dashed border-gray-400"
                aria-hidden
              />
              میانگین کل: {format(reference)}
            </span>
          )}
          {footer}
        </p>
      )}
    </div>
  );
}
