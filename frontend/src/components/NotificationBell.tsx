import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { apiClient } from "../api/client";
import { useNotifications } from "../api/queries";
import { formatDateTime } from "../utils/dates";
import type { AppNotification } from "../types";

export function NotificationBell() {
  const { data } = useNotifications();
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const containerRef = useRef<HTMLDivElement>(null);
  const bellRef = useRef<HTMLButtonElement>(null);

  const unread = data?.unread ?? 0;
  const items = data?.items ?? [];

  // بستن پنل با کلیک بیرون از آن — یا با Escape.
  //
  // تا امروز فقط راه اولی بود، یعنی کاربر صفحه‌کلید هیچ راهی برای بستنِ پنل
  // نداشت جز اینکه با Tab از تمام اعلان‌ها رد شود. فوکوس هم به خودِ زنگوله
  // برمی‌گردد، وگرنه بعد از بسته شدن، مکان‌نما روی عنصری می‌ماند که دیگر نیست.
  useEffect(() => {
    if (!open) return;
    function onClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key !== "Escape") return;
      setOpen(false);
      bellRef.current?.focus();
    }
    document.addEventListener("mousedown", onClickOutside);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onClickOutside);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  async function invalidate() {
    await queryClient.invalidateQueries({ queryKey: ["notifications"] });
  }

  async function openNotification(n: AppNotification) {
    setOpen(false);
    if (n.read_at === null) {
      apiClient.post(`/notifications/${n.id}/read`).then(invalidate).catch(() => {});
    }
    if (n.link) navigate(n.link);
  }

  async function markAllRead() {
    try {
      await apiClient.post("/notifications/read-all");
      await invalidate();
    } catch {
      /* خطای شبکه؛ در refetch بعدی جبران می‌شود */
    }
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        ref={bellRef}
        onClick={() => setOpen((v) => !v)}
        aria-label={`اعلان‌ها${unread > 0 ? ` (${unread.toLocaleString("fa-IR")} خوانده‌نشده)` : ""}`}
        aria-expanded={open}
        className={`relative flex h-9 w-9 items-center justify-center rounded-full border transition-colors sm:h-10 sm:w-10 ${
          open
            ? "border-charcoal-900 bg-charcoal-900 text-white"
            : "border-gray-200 text-gray-600 hover:bg-gray-100 hover:text-gray-900"
        }`}
      >
        <svg
          viewBox="0 0 20 20"
          className="h-4.5 w-4.5"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M10 3a4.5 4.5 0 0 0-4.5 4.5c0 3.5-1.5 5-1.5 5h12s-1.5-1.5-1.5-5A4.5 4.5 0 0 0 10 3z" />
          <path d="M8.5 15.5a1.6 1.6 0 0 0 3 0" />
        </svg>
        {unread > 0 && (
          <span className="absolute -left-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-pulse-600 px-1 text-[10px] font-bold text-white ring-2 ring-white">
            {unread.toLocaleString("fa-IR")}
          </span>
        )}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            className="absolute left-0 top-full z-40 mt-2 w-80 overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-float ring-1 ring-black/5"
            initial={{ opacity: 0, y: -8, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.97 }}
            transition={{ duration: 0.26, ease: [0.22, 1, 0.36, 1] }}
          >
            <div className="flex items-center justify-between border-b border-gray-100 px-3 py-2.5">
              <span className="text-sm font-bold text-gray-900">اعلان‌ها</span>
              {unread > 0 && (
                <button onClick={markAllRead} className="text-xs font-medium text-pulse-600 hover:underline">
                  علامت‌گذاری همه به‌عنوان خوانده‌شده
                </button>
              )}
            </div>
            <ul className="max-h-80 overflow-y-auto">
              {items.length === 0 && (
                <li className="p-4 text-center text-sm text-gray-400">اعلانی ندارید.</li>
              )}
              {items.map((n) => (
                <li key={n.id} className="border-b border-gray-50 last:border-b-0">
                  <button
                    onClick={() => openNotification(n)}
                    className={`w-full px-3 py-2.5 text-right text-sm transition-colors hover:bg-gray-50 ${
                      n.read_at === null ? "bg-pulse-50/40 font-medium" : "text-gray-600"
                    }`}
                  >
                    <span className="block">{n.message}</span>
                    <span className="mt-0.5 block text-xs text-gray-400">
                      {formatDateTime(n.created_at)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
