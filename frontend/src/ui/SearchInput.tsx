/** ورودی جست‌وجوی مشترک — یک ذره‌بین، یک اندازه، یک رفتار.
 *
 * پیش از این همین نشانه و همان رشتهٔ بلندِ کلاس در چهار فایل کپی شده بود و
 * واگرا هم شده بود: چهار عرضِ متفاوت (۵۶ و ۶۰ و ۶۴ و ۷۲) که هیچ‌کدام تصمیم
 * نبودند، فقط جا مانده بودند.
 */
import type { ComponentPropsWithRef } from "react";

export function SearchInput({
  widthClass = "sm:w-64",
  ...props
}: Omit<ComponentPropsWithRef<"input">, "type" | "className"> & {
  /** عرض روی نمایشگر پهن. عمداً یک prop جداست و نه بخشی از `className`:
   *  ترتیبِ کلاس‌های Tailwind تعیین‌کنندهٔ اولویت نیست، پس `sm:w-72`ی که بعد از
   *  `sm:w-64` بیاید لزوماً برنده نمی‌شود — دو کلاسِ عرض یعنی نتیجه به ترتیب
   *  تولید CSS بستگی دارد، نه به آنچه نوشته‌ایم. */
  widthClass?: string;
}) {
  return (
    <div className="relative">
      <svg
        viewBox="0 0 20 20"
        aria-hidden
        className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      >
        <circle cx="9" cy="9" r="6" />
        <path d="M14 14l3 3" />
      </svg>
      <input
        type="search"
        className={`w-full ${widthClass} rounded-xl border border-gray-200 bg-gray-100 py-1.5 pr-9 pl-3 text-sm text-gray-700 outline-none transition-colors duration-150 focus:border-gray-900 focus:bg-white`}
        {...props}
      />
    </div>
  );
}
