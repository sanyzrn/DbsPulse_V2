import { useEffect, useRef, useState } from "react";
import { NavLink } from "react-router-dom";
import { AnimatePresence, motion } from "motion/react";
import { ROLE_LABELS } from "../types";
import type { CurrentUser } from "../types";

/**
 * پاپ‌آور پروفایل کاربر — دقیقاً از همان الگوی اثبات‌شدهٔ NotificationBell پیروی
 * می‌کند (بستن با کلیک بیرون، بدون لایهٔ backdrop تمام‌صفحه) تا مشکل رایج
 * z-index در پاپ‌آورهای مشابه (که کلیک روی دکمهٔ دیگر هدر را قبل از بسته شدن
 * پاپ‌آور فعلی مسدود می‌کند) از ابتدا رخ ندهد.
 */
export function ProfileMenu({ user, onLogout }: { user: CurrentUser; onLogout: () => void }) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function onEscape(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    document.addEventListener("keydown", onEscape);
    return () => {
      document.removeEventListener("mousedown", onClickOutside);
      document.removeEventListener("keydown", onEscape);
    };
  }, [open]);

  return (
    <div ref={containerRef} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-label="منوی پروفایل"
        aria-expanded={open}
        className={`flex h-9 w-9 items-center justify-center rounded-full border transition-colors sm:h-10 sm:w-10 ${
          open
            ? "border-charcoal-900 bg-charcoal-900 text-white"
            : "border-gray-200 text-gray-600 hover:bg-gray-100 hover:text-gray-900"
        }`}
      >
        <svg viewBox="0 0 20 20" className="h-4.5 w-4.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <circle cx="10" cy="7" r="3.4" />
          <path d="M4 17c1.2-3.4 4.2-5 6-5s4.8 1.6 6 5" />
        </svg>
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            className="absolute left-0 top-full z-40 mt-2 w-64 overflow-hidden rounded-2xl border border-gray-100 bg-white shadow-float ring-1 ring-black/5"
            initial={{ opacity: 0, y: -8, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.97 }}
            transition={{ duration: 0.26, ease: [0.22, 1, 0.36, 1] }}
          >
            {/* هدر تیره — همان زبان بصری کارت‌های «hero» تیره‌ی باقی اپ */}
            <div className="flex items-center gap-3 bg-charcoal-900 px-4 py-3.5">
              <span className="flex h-11 w-11 flex-none items-center justify-center rounded-full border-2 border-white/15 bg-pulse-600 text-base font-bold text-white">
                {(user.display_name || user.username).charAt(0).toUpperCase()}
              </span>
              <span className="min-w-0 leading-tight">
                <span className="block truncate text-sm font-bold text-white">
                  {user.display_name || user.username}
                </span>
                <span className="mt-1 inline-block rounded-full bg-white/15 px-2 py-0.5 text-[11px] font-medium text-white/85">
                  {ROLE_LABELS[user.role]}
                </span>
              </span>
            </div>

            <div className="p-1.5">
              <NavLink
                to="/change-password"
                onClick={() => setOpen(false)}
                className="group flex items-center gap-2.5 rounded-xl px-2.5 py-2 text-sm text-gray-700 transition-colors hover:bg-gray-50"
              >
                <span className="flex h-8 w-8 flex-none items-center justify-center rounded-lg bg-gray-100 text-gray-600 transition-colors group-hover:bg-charcoal-900 group-hover:text-white">
                  <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <circle cx="7" cy="10" r="4" />
                    <path d="M11 10h6m-2 0v3m-2.5-3v2" />
                  </svg>
                </span>
                تغییر رمز عبور
              </NavLink>
              <NavLink
                to="/notification-preferences"
                onClick={() => setOpen(false)}
                className="group flex items-center gap-2.5 rounded-xl px-2.5 py-2 text-sm text-gray-700 transition-colors hover:bg-gray-50"
              >
                <span className="flex h-8 w-8 flex-none items-center justify-center rounded-lg bg-gray-100 text-gray-600 transition-colors group-hover:bg-charcoal-900 group-hover:text-white">
                  <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d="M10 3a4.5 4.5 0 0 0-4.5 4.5c0 3-1.5 4-1.5 4h12s-1.5-1-1.5-4A4.5 4.5 0 0 0 10 3z" />
                    <path d="M8.5 15a1.7 1.7 0 0 0 3 0" />
                  </svg>
                </span>
                اعلان‌ها
              </NavLink>
              <NavLink
                to="/sessions"
                onClick={() => setOpen(false)}
                className="group flex items-center gap-2.5 rounded-xl px-2.5 py-2 text-sm text-gray-700 transition-colors hover:bg-gray-50"
              >
                <span className="flex h-8 w-8 flex-none items-center justify-center rounded-lg bg-gray-100 text-gray-600 transition-colors group-hover:bg-charcoal-900 group-hover:text-white">
                  <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <rect x="2.5" y="4" width="15" height="9" rx="1.5" />
                    <path d="M7 16h6" />
                  </svg>
                </span>
                نشست‌های فعال
              </NavLink>
              <button
                onClick={() => {
                  setOpen(false);
                  onLogout();
                }}
                className="group flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2 text-sm text-pulse-600 transition-colors hover:bg-pulse-50"
              >
                <span className="flex h-8 w-8 flex-none items-center justify-center rounded-lg bg-pulse-50 text-pulse-600 transition-colors group-hover:bg-pulse-600 group-hover:text-white">
                  <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d="M13 7l3 3-3 3m3-3H8m2 6H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h5" />
                  </svg>
                </span>
                خروج
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
