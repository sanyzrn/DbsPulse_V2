import type { ReactNode } from "react";

/** ظرف استاندارد بخش‌های صفحه — مرز مشخص، پدینگِ جمع (p-4 نه p-5) تا در
 *  داشبوردها و صفحاتِ مدیریتی، محتوای بیشتری در یک نگاه جا شود. */
export function Card({
  title,
  actions,
  children,
  className = "",
}: {
  title?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-2xl border border-gray-200 bg-white p-4 ${className}`}
    >
      {(title || actions) && (
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          {title && (
            <h2 className="text-sm font-bold text-gray-900 sm:text-base">{title}</h2>
          )}
          {actions}
        </div>
      )}
      {children}
    </div>
  );
}

/** جدول‌ها باید داخل ظرف خودشان اسکرول افقی بخورند، نه کل صفحه (موبایل). */
export function TableScroll({ children }: { children: ReactNode }) {
  return <div className="overflow-x-auto">{children}</div>;
}

/** اسکلتون بارگذاری استاندارد فهرست/جدول — تا هنگام واکشی داده، صفحه به‌جای پرشِ
 * سفید یا «موردی یافت نشد» زودهنگام، چند ردیف خاکستری متحرک نشان دهد. */
export function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-2 py-1" aria-hidden>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="skeleton h-9" />
      ))}
    </div>
  );
}

export function EmptyState({ children = "موردی یافت نشد." }: { children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center py-8 text-center">
      <div className="mb-2.5 flex h-10 w-10 items-center justify-center rounded-xl bg-pulse-50">
        <svg viewBox="0 0 24 24" className="h-5 w-5 text-pulse-400" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" />
          <path d="M8 15h8" />
          <path d="M9 9h.01" />
          <path d="M15 9h.01" />
        </svg>
      </div>
      <p className="max-w-xs text-sm leading-relaxed text-gray-400">{children}</p>
    </div>
  );
}

/** دراپ‌داون فیلتر استاندارد (با کارت/فلش یکسان) — تا فیلترهای فهرست‌های HR
 * ظاهر و رفتار یکدست داشته باشند به‌جای <select>های تک‌مصرف. */
export function FilterSelect({
  value,
  onChange,
  children,
  "aria-label": ariaLabel,
}: {
  value: string;
  onChange: (value: string) => void;
  children: ReactNode;
  "aria-label"?: string;
}) {
  // یک <select> به اندازهٔ بلندترین گزینه‌اش پهن می‌شود. انتخابگر شاخص گزینه‌های
  // ۷۹ نویسه‌ای دارد، پس ۵۵۸px می‌شد و کل صفحهٔ گزارش‌ها را روی موبایل به اسکرول
  // افقی می‌انداخت. min-w-0 اجازهٔ کوچک‌شدن در ظرف flex را می‌دهد و max-w-full سقف
  // را روی عرض در دسترس می‌گذارد؛ متن گزینه خودش با … کوتاه می‌شود.
  return (
    <div className="relative min-w-0 max-w-full">
      <select
        aria-label={ariaLabel}
        className="max-w-full appearance-none truncate rounded-xl border border-gray-200 bg-gray-100 py-1.5 pr-3 pl-8 text-sm text-gray-700 outline-none transition-colors duration-150 focus:border-gray-900 focus:bg-white"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        {children}
      </select>
      <svg viewBox="0 0 20 20" className="pointer-events-none absolute left-2 top-1/2 h-3 w-3 -translate-y-1/2 text-gray-400" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M6 8l4 4 4-4" />
      </svg>
    </div>
  );
}

/** عنوان صفحه با زیرنویس اختیاری — سلسله‌مراتب تایپوگرافی یکسان در همه صفحات.
 *  یک پله جمع‌تر از قبل: عنوانِ درشتِ صفحه، با خودِ صفحه رقابت نمی‌کند. */
export function PageHeader({ title, subtitle }: { title: ReactNode; subtitle?: ReactNode }) {
  return (
    <div className="mb-1">
      <h1 className="text-xl font-extrabold text-gray-900">{title}</h1>
      {subtitle && <p className="mt-0.5 text-sm text-gray-500">{subtitle}</p>}
      <div className="mt-2 h-0.5 w-10 rounded-full bg-pulse-500" />
    </div>
  );
}
