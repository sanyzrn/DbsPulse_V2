import type { ReactNode } from "react";
import { motion } from "motion/react";

/** جدول دادهٔ استاندارد اپ — استخراج‌شده از الگویی که پیش‌تر در چند صفحه (فهرست
 * ارزیابی‌ها، پرسنل، کاربران، داشبورد تحلیلی) عیناً کپی شده بود: هدر گرادیانتی،
 * ردیف‌های جداشونده با هاور نرم، و برای فهرست‌های زنده (نه جدول‌های خلاصهٔ ثابت)
 * انیمیشن ورود پلکانی. `bordered=false` برای وقتی که جدول از قبل داخل یک Card
 * دیگر (با عنوان/جست‌وجوی خودش) جا گرفته است. */
export function Table({
  headers,
  rows,
  rowKeys,
  title,
  bordered = true,
  animateRows = true,
  emptyMessage = "موردی یافت نشد.",
  cellAlign = "middle",
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
}) {
  const rowClass = `border-b border-gray-50 transition-colors last:border-0 hover:bg-pulse-50/30 ${cellAlign === "top" ? "align-top" : ""}`;
  const content = (
    <>
      {title && <h3 className="mb-3 text-base font-bold text-gray-900">{title}</h3>}
      {rows.length === 0 ? (
        <p className="py-6 text-center text-sm text-gray-400">{emptyMessage}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                {headers.map((h, i) => (
                  <th key={i} className="px-3 py-2.5 text-right text-xs font-semibold text-gray-600">
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
      )}
    </>
  );

  return bordered ? (
    <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-card">{content}</div>
  ) : (
    content
  );
}
