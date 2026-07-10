import { motion } from "motion/react";
import { useRoleOverview } from "../api/queries";
import { EASE_SOFT } from "../ui/motion";
import type { RoleOverviewTone } from "../types";

const TONE_CLASS: Record<RoleOverviewTone, string> = {
  neutral: "border-gray-100 bg-white text-gray-900",
  amber: "border-amber-100 bg-amber-50/60 text-amber-900",
  pulse: "border-pulse-100 bg-pulse-50/50 text-pulse-900",
  green: "border-green-100 bg-green-50/60 text-green-900",
};

const DOT_CLASS: Record<RoleOverviewTone, string> = {
  neutral: "bg-gray-300",
  amber: "bg-amber-400",
  pulse: "bg-pulse-400",
  green: "bg-green-400",
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
          <div key={i} className="skeleton h-20 rounded-2xl" />
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
          className={`rounded-2xl border p-4 shadow-card ${TONE_CLASS[card.tone]}`}
        >
          <div className="flex items-center gap-1.5">
            <span aria-hidden className={`h-1.5 w-1.5 rounded-full ${DOT_CLASS[card.tone]}`} />
            <p className="text-xs font-medium opacity-80">{card.label}</p>
          </div>
          <p className="mt-1.5 text-2xl font-bold tabular-nums">
            {card.value.toLocaleString("fa-IR")}
          </p>
          {card.hint && <p className="mt-0.5 text-[11px] opacity-70">{card.hint}</p>}
        </motion.div>
      ))}
    </div>
  );
}
