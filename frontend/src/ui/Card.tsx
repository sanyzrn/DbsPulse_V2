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
