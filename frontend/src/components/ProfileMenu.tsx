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
        className="flex items-center gap-2 rounded-xl p-1 transition-colors hover:bg-gray-100"
      >
        <span className="rounded-full bg-gradient-to-br from-pulse-500 to-pulse-violet-600 p-0.5">
          <span
            aria-hidden
            className="flex h-7 w-7 items-center justify-center rounded-full bg-white text-sm font-bold gradient-text"
          >
            {user.username.charAt(0).toUpperCase()}
          </span>
        </span>
        <span className="hidden leading-tight md:block">
          <span className="block text-sm font-medium text-gray-800">{user.username}</span>
          <span className="block text-[11px] text-gray-500">{ROLE_LABELS[user.role]}</span>
        </span>
        <svg
          viewBox="0 0 20 20"
          className={`h-3.5 w-3.5 text-gray-400 transition-transform duration-200 ${open ? "rotate-180" : ""}`}
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M5 7.5l5 5 5-5" />
        </svg>
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            className="absolute left-0 top-full z-40 mt-2 w-64 overflow-hidden rounded-2xl border border-gray-100 bg-white shadow-float ring-1 ring-black/5"
            initial={{ opacity: 0, y: -8, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.97 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
          >
            <div className="flex items-center gap-3 border-b border-gray-100 bg-gradient-to-l from-pulse-50/50 to-pulse-violet-50/50 px-4 py-3">
              <span className="rounded-full bg-gradient-to-br from-pulse-500 to-pulse-violet-600 p-0.5">
                <span
                  aria-hidden
                  className="flex h-9 w-9 items-center justify-center rounded-full bg-white text-base font-bold gradient-text"
                >
                  {user.username.charAt(0).toUpperCase()}
                </span>
              </span>
              <span className="min-w-0 leading-tight">
                <span className="block truncate text-sm font-bold text-gray-900">{user.username}</span>
                <span className="mt-0.5 inline-block rounded-full bg-white px-2 py-0.5 text-[11px] font-medium text-gray-600 ring-1 ring-gray-200">
                  {ROLE_LABELS[user.role]}
                </span>
              </span>
            </div>

            <div className="p-1.5">
              <NavLink
                to="/change-password"
                onClick={() => setOpen(false)}
                className="flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm text-gray-700 transition-colors hover:bg-gray-50"
              >
                <svg viewBox="0 0 20 20" className="h-4.5 w-4.5 text-gray-400" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <circle cx="7" cy="10" r="4" />
                  <path d="M11 10h6m-2 0v3m-2.5-3v2" />
                </svg>
                تغییر رمز عبور
              </NavLink>
              <button
                onClick={() => {
                  setOpen(false);
                  onLogout();
                }}
                className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-sm text-pulse-600 transition-colors hover:bg-pulse-50"
              >
                <svg viewBox="0 0 20 20" className="h-4.5 w-4.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M13 7l3 3-3 3m3-3H8m2 6H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h5" />
                </svg>
                خروج
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
