import { motion } from "motion/react";
import { useRoleOverview } from "../api/queries";
import { EASE_SOFT } from "../ui/motion";
import type { RoleOverviewTone } from "../types";

/* چهار کاشیِ کنار هم با چهار پس‌زمینهٔ رنگی، چهار چیزِ «مهم» می‌سازند — یعنی
   هیچ‌کدام. حالا همه یک کارتِ سفیدِ یکسان‌اند و رنگ فقط در یک خطِ نازکِ کناری و
   یک نقطه می‌نشیند: ترتیبِ خواندن از عدد شروع می‌شود، نه از رنگِ زمینه. */
const ACCENT_CLASS: Record<RoleOverviewTone, string> = {
  neutral: "bg-gray-300",
  amber: "bg-amber-400",
  pulse: "bg-pulse-500",
  green: "bg-green-500",
};

/** نوار کاشی‌های خلاصهٔ داشبورد نقش — بالای صفحهٔ اصلی هر نقش قرار می‌گیرد و یک نمای
 * سریع از کارهای در انتظار و وضعیت پرونده‌ها می‌دهد. داده از یک endpoint نقش‌محور
 * می‌آید، پس هر نقش کاشی‌های متناسب خودش را می‌بیند. */
export function RoleOverviewCards() {
  const { data, isLoading } = useRoleOverview();

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="skeleton h-[86px] rounded-2xl" />
        ))}
      </div>
    );
  }

  if (!data || data.cards.length === 0) return null;

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {data.cards.map((card, i) => (
        <motion.div
          key={card.key}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25, delay: i * 0.05, ease: EASE_SOFT }}
          className="relative overflow-hidden rounded-2xl border border-gray-200 bg-white p-4"
        >
          <span
            aria-hidden
            className={`absolute inset-y-0 right-0 w-[3px] ${ACCENT_CLASS[card.tone]}`}
          />
          <p className="text-xs font-medium text-gray-500">{card.label}</p>
          <p className="mt-1.5 text-2xl font-bold tabular-nums text-gray-900">
            {card.value.toLocaleString("fa-IR")}
          </p>
          {card.hint && <p className="mt-0.5 text-[11px] text-gray-400">{card.hint}</p>}
        </motion.div>
      ))}
    </div>
  );
}
