import type { ReactNode } from "react";

/** ظرف استاندارد بخش‌های صفحه با سایه مدرن و حاشیه ظریف. */
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
      className={`rounded-2xl border border-gray-100 bg-white p-5 shadow-card transition-shadow duration-300 hover:shadow-card-hover ${className}`}
    >
      {(title || actions) && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          {title && (
            <h2 className="text-base font-bold text-gray-900">{title}</h2>
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
    <div className="space-y-2 py-2" aria-hidden>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="skeleton h-10" />
      ))}
    </div>
  );
}

export function EmptyState({ children = "موردی یافت نشد." }: { children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center py-10 text-center">
      <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-pulse-50">
        <svg viewBox="0 0 24 24" className="h-6 w-6 text-pulse-400" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" />
          <path d="M8 15h8" />
          <path d="M9 9h.01" />
          <path d="M15 9h.01" />
        </svg>
      </div>
      <p className="text-sm text-gray-400">{children}</p>
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
  return (
    <div className="relative">
      <select
        aria-label={ariaLabel}
        className="appearance-none rounded-xl border border-gray-200 bg-gray-100 py-1.5 pr-3 pl-8 text-sm text-gray-700 outline-none transition-colors duration-150 focus:border-pulse-500 focus:bg-white"
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

/** عنوان صفحه با زیرنویس اختیاری — سلسله‌مراتب تایپوگرافی یکسان در همه صفحات. */
export function PageHeader({ title, subtitle }: { title: ReactNode; subtitle?: ReactNode }) {
  return (
    <div className="mb-1">
      <h1 className="text-2xl font-extrabold text-gray-900">{title}</h1>
      {subtitle && <p className="mt-1 text-sm text-gray-500">{subtitle}</p>}
      <div className="mt-3 h-0.5 w-16 rounded-full bg-pulse-500" />
    </div>
  );
}
