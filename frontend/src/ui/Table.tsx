import type { ReactNode } from "react";
import { motion } from "motion/react";
import { NARROW_QUERY, useMediaQuery } from "./useMediaQuery";

/** جدول دادهٔ استاندارد اپ — استخراج‌شده از الگویی که پیش‌تر در چند صفحه (فهرست
 * ارزیابی‌ها، پرسنل، کاربران، داشبورد تحلیلی) عیناً کپی شده بود: هدر ساده،
 * ردیف‌های جداشونده با هاور نرم، و برای فهرست‌های زنده (نه جدول‌های خلاصهٔ ثابت)
 * انیمیشن ورود پلکانی. `bordered=false` برای وقتی که جدول از قبل داخل یک Card
 * دیگر (با عنوان/جست‌وجوی خودش) جا گرفته است.
 *
 * زیر `md` جدول به کارت تبدیل می‌شود. یک جدولِ چهارستونی در عرض ۳۹۰ پیکسل هر
 * کلمه را به سه سطر می‌شکست و ستون آخر بی‌آنکه معلوم باشد از لبه بیرون می‌زد —
 * یعنی روی موبایل هم خواندنش سخت بود، هم بخشی از داده اصلاً دیده نمی‌شد.
 */
export function Table({
  headers,
  rows,
  rowKeys,
  title,
  bordered = true,
  animateRows = true,
  emptyMessage = "موردی یافت نشد.",
  cellAlign = "middle",
  mobileCards = true,
}: {
  headers: ReactNode[];
  rows: ReactNode[][];
  rowKeys?: Array<string | number>;
  title?: string;
  bordered?: boolean;
  animateRows?: boolean;
  emptyMessage?: string;
  /** برای ردیف‌هایی با محتوای چندخطی (مثل جزئیات audit log) که باید از بالا هم‌تراز شوند. */
  cellAlign?: "middle" | "top";
  /** برای جدول‌های دوستونیِ خلاصه که در موبایل هم جا می‌شوند، می‌توان خاموشش کرد. */
  mobileCards?: boolean;
}) {
  // فقط یکی از دو نما رندر می‌شود، نه هر دو با `hidden md:block`. رندرکردنِ هر دو
  // یعنی خوانندهٔ صفحه هر ردیف را دو بار می‌خواند و هر جست‌وجوی بر اساس متن دو
  // نتیجه می‌گیرد — همان دلیلی که `useMediaQuery` برای فرم نمره‌دهی ساخته شد.
  const narrow = useMediaQuery(NARROW_QUERY);
  const asCards = mobileCards && narrow;

  const rowClass = `border-b border-gray-100 transition-colors last:border-0 hover:bg-gray-50 ${cellAlign === "top" ? "align-top" : ""}`;

  const table = (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200">
            {headers.map((h, i) => (
              <th key={i} className="px-3 py-2.5 text-right text-xs font-semibold text-gray-500">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => {
            const key = rowKeys?.[idx] ?? idx;
            const cells = row.map((cell, cIdx) => (
              <td key={cIdx} className="px-3 py-2.5 text-gray-700">
                {cell}
              </td>
            ));
            return animateRows ? (
              <motion.tr
                key={key}
                className={rowClass}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.2, delay: idx * 0.03 }}
              >
                {cells}
              </motion.tr>
            ) : (
              <tr key={key} className={rowClass}>
                {cells}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );

  const cards = (
    <ul className="space-y-2">
      {rows.map((row, idx) => (
        <li key={rowKeys?.[idx] ?? idx} className="rounded-xl border border-gray-200 bg-white p-3">
          {/* سلول اول سرِ کارت است — تقریباً همیشه «نام» یا «کد» است و همان چیزی
              که کاربر با آن ردیف را می‌شناسد. */}
          <div className="text-sm font-semibold text-gray-900">{row[0]}</div>
          <dl className="mt-2 space-y-1">
            {row.slice(1).map((cell, cIdx) => {
              const header = headers[cIdx + 1];
              // ستون بی‌عنوان = ستون کنش؛ برچسب نمی‌خواهد، تمام‌عرض می‌نشیند.
              // `mx-0` چون مرورگر به‌طور پیش‌فرض ۴۰ پیکسل حاشیهٔ ابتدایی به `dd`
              // می‌دهد و دکمه را از لبهٔ کارت جدا می‌اندازد.
              if (header === "" || header === undefined || header === null) {
                return (
                  <dd key={cIdx} className="mx-0 mt-2 border-t border-gray-100 pt-2.5">
                    {cell}
                  </dd>
                );
              }
              return (
                <div key={cIdx} className="flex items-baseline justify-between gap-3 text-sm">
                  <dt className="shrink-0 text-xs text-gray-400">{header}</dt>
                  <dd className="mx-0 min-w-0 text-left text-gray-700">{cell}</dd>
                </div>
              );
            })}
          </dl>
        </li>
      ))}
    </ul>
  );

  const content = (
    <>
      {title && <h3 className="mb-3 text-base font-bold text-gray-900">{title}</h3>}
      {rows.length === 0 ? (
        <p className="py-6 text-center text-sm text-gray-400">{emptyMessage}</p>
      ) : asCards ? (
        cards
      ) : (
        table
      )}
    </>
  );

  return bordered ? (
    <div className="rounded-2xl border border-gray-200 bg-white p-5">{content}</div>
  ) : (
    content
  );
}
