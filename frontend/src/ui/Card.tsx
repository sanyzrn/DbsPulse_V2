import { useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "motion/react";
import { EASE_SOFT } from "./motion";

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

/** کارت تاشو با هدر کلیک‌پذیر — برای «افشای تدریجی»: فرم‌ها/بخش‌های کم‌کاربرد
 * به‌صورت پیش‌فرض جمع‌اند تا محتوای اصلی صفحه شلوغ نشود، و با یک کلیک نرم باز می‌شوند. */
export function CollapsibleCard({
  title,
  subtitle,
  defaultOpen = false,
  children,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="overflow-hidden rounded-2xl border border-gray-100 bg-white shadow-card">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-3 px-5 py-4 text-right transition-colors duration-200 hover:bg-gray-50/70"
      >
        <span className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 flex-none items-center justify-center rounded-xl bg-pulse-50 text-pulse-600">
            <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M10 4v12M4 10h12" />
            </svg>
          </span>
          <span>
            <span className="block text-base font-bold text-gray-900">{title}</span>
            {subtitle && <span className="mt-0.5 block text-xs text-gray-500">{subtitle}</span>}
          </span>
        </span>
        <motion.span
          aria-hidden
          animate={{ rotate: open ? 180 : 0 }}
          transition={{ duration: 0.3, ease: EASE_SOFT }}
          className="flex-none text-gray-400"
        >
          <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M6 8l4 4 4-4" />
          </svg>
        </motion.span>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.32, ease: EASE_SOFT }}
            className="overflow-hidden"
          >
            <div className="border-t border-gray-100 px-5 py-5">{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
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
