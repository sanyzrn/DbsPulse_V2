import { useEffect, useRef, useState } from "react";
import { motion, useInView } from "motion/react";

/** نمایش مدرن درصدها و امتیازها: نشان درصدی، نوار پیشرفت و حلقه امتیاز.
 * رنگ‌بندی معنایی (وضعیت): سبز = مطلوب، کهربایی = میانه، قرمز = نیازمند توجه.
 * انیمیشن با Framer Motion (transform/opacity، ۶۰fps). */

type Tone = "green" | "amber" | "red" | "gray";

function toneOf(value: number): Tone {
  if (value >= 75) return "green";
  if (value >= 50) return "amber";
  return "red";
}

const BADGE_STYLES: Record<Tone, string> = {
  green: "bg-green-50 text-green-700",
  amber: "bg-amber-50 text-amber-700",
  red: "bg-red-50 text-red-700",
  gray: "bg-gray-100 text-gray-500",
};

const DOT_STYLES: Record<Tone, string> = {
  green: "bg-green-500",
  amber: "bg-amber-500",
  red: "bg-red-500",
  gray: "bg-gray-400",
};

/** رنگ حلقه بر اساس tone — اما برای tone سبز/برند از گرادیانت استفاده می‌کنیم. */
const RING_STOP_COLOR: Record<Tone, string> = {
  green: "#10b981",
  amber: "#f59e0b",
  red: "#ef4444",
  gray: "#d1d5db",
};

export function formatPct(value: number | null): string {
  return value === null ? "—" : `${Number(value).toLocaleString("fa-IR")}٪`;
}

/** عدد متحرک (count-up) — از ۰ تا مقدار نهایی با انیمیشن. */
export function CountUp({
  value,
  format = "fa-pct",
  duration = 1.2,
  prefix = "",
}: {
  value: number | null;
  format?: "fa-pct" | "plain";
  duration?: number;
  prefix?: string;
}) {
  const [display, setDisplay] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-20px" });

  useEffect(() => {
    if (!inView || value === null) return;
    const target = value;
    const start = performance.now();
    let raf = 0;
    function tick(now: number) {
      const progress = Math.min(1, (now - start) / (duration * 1000));
      // easeOutCubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(target * eased);
      if (progress < 1) raf = requestAnimationFrame(tick);
    }
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [inView, value, duration]);

  if (value === null) {
    return <span ref={ref}>—</span>;
  }

  const rounded = format === "fa-pct" ? Math.round(display) : display;
  return (
    <span ref={ref}>
      {prefix}
      {rounded.toLocaleString("fa-IR")}
      {format === "fa-pct" ? "٪" : ""}
    </span>
  );
}

/** نشان درصدی با نقطه وضعیت؛ جایگزین نمایش متنی ساده درصدها. */
export function PctBadge({ value }: { value: number | null }) {
  const tone = value === null ? "gray" : toneOf(value);
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold tabular-nums ${BADGE_STYLES[tone]}`}
    >
      <span aria-hidden className={`h-1.5 w-1.5 rounded-full ${DOT_STYLES[tone]}`} />
      {formatPct(value)}
    </span>
  );
}

/** نوار پیشرفت افقی ۰ تا ۱۰۰ با گرادیانت و انیمیشن عرض. */
export function PctBar({
  value,
  tone,
  className = "",
}: {
  value: number;
  tone?: Tone;
  className?: string;
}) {
  const clamped = Math.max(0, Math.min(100, value));
  const resolved = tone ?? toneOf(clamped);
  const isBrand = resolved === "green";
  return (
    <div className={`h-2 w-full overflow-hidden rounded-full bg-gray-100 ${className}`}>
      <motion.div
        className="h-full rounded-full"
        style={
          isBrand
            ? {
                background: "var(--gradient-pulse)",
              }
            : { backgroundColor: RING_STOP_COLOR[resolved] }
        }
        initial={{ width: 0 }}
        whileInView={{ width: `${clamped}%` }}
        viewport={{ once: true }}
        transition={{ duration: 1, ease: "easeOut" }}
      />
    </div>
  );
}

/** حلقه (گیج دایره‌ای) امتیاز ۰ تا ۱۰۰ با گرادیانت و عدد متحرک در مرکز. */
export function ScoreRing({
  value,
  size = 72,
  label,
}: {
  value: number | null;
  size?: number;
  label?: string;
}) {
  const stroke = size < 60 ? 5 : 7;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const clamped = value === null ? 0 : Math.max(0, Math.min(100, value));
  const tone: Tone = value === null ? "gray" : toneOf(clamped);
  const useGradient = tone === "green";

  return (
    <div className="inline-flex flex-col items-center gap-1">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <defs>
            <linearGradient id={`ring-grad-${size}`} x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stopColor="var(--color-pulse-500)" />
              <stop offset="1" stopColor="var(--color-pulse-violet-600)" />
            </linearGradient>
          </defs>
          {/* مسیر پس‌زمینه */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="#f1f3f6"
            strokeWidth={stroke}
          />
          {/* مسیر پیشرفت — با انیمیشن */}
          <motion.circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={useGradient ? `url(#ring-grad-${size})` : RING_STOP_COLOR[tone]}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference }}
            whileInView={{ strokeDashoffset: circumference * (1 - clamped / 100) }}
            viewport={{ once: true }}
            transition={{ duration: 1.2, ease: "easeOut" }}
          />
        </svg>
        <span
          className="absolute inset-0 flex items-center justify-center font-bold tabular-nums text-gray-800"
          style={{ fontSize: size < 60 ? "0.7rem" : "0.8rem" }}
        >
          {value === null ? (
            "—"
          ) : (
            <CountUp value={value} format="fa-pct" duration={1.2} />
          )}
        </span>
      </div>
      {label && <span className="text-xs text-gray-500">{label}</span>}
    </div>
  );
}
