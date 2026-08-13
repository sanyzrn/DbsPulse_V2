import { useEffect, useState } from "react";
import { motion } from "motion/react";

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

  // انیمیشن با تغییر مقدار/mount اجرا می‌شود، نه با ورود به دید (whileInView/useInView).
  // اتکا به رویداد تقاطع دید باعث می‌شد وقتی مقدار پس از mount و بدون اسکرول تازه
  // به‌روزرسانی می‌شود (مثلاً پس از ثبت ارزیابی) عدد روی صفر گیر کند.
  useEffect(() => {
    if (value === null) return;
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
  }, [value, duration]);

  if (value === null) {
    return <span>—</span>;
  }

  const rounded = format === "fa-pct" ? Math.round(display) : display;
  return (
    <span>
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

/** نوار پیشرفت افقی ۰ تا ۱۰۰ با انیمیشن عرض. */
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
  return (
    <div className={`h-2 w-full overflow-hidden rounded-full bg-gray-100 ${className}`}>
      <motion.div
        className="h-full rounded-full"
        style={{ backgroundColor: RING_STOP_COLOR[resolved] }}
        initial={{ width: 0 }}
        animate={{ width: `${clamped}%` }}
        transition={{ duration: 1, ease: "easeOut" }}
      />
    </div>
  );
}

/** حلقه (گیج دایره‌ای) امتیاز ۰ تا ۱۰۰ با عدد متحرک در مرکز. */
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

  return (
    <div className="inline-flex flex-col items-center gap-1">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
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
            stroke={RING_STOP_COLOR[tone]}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset: circumference * (1 - clamped / 100) }}
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

/** مقدارِ سرکوب‌شده به دلیل کوهورت حداقلی (P1-08).
 *
 * عمداً با «داده نداریم» فرق دارد: داده هست، ولی جمعیتش آن‌قدر کوچک است که نمایش
 * میانگین عملاً افشای امتیاز یک نفر می‌شود. سلول خالی این تفاوت را پنهان می‌کرد. */
export function SuppressedValue() {
  return (
    <span
      className="inline-flex items-center gap-1 text-xs text-gray-400"
      title="برای حفظ حریم خصوصی نمایش داده نمی‌شود: تعداد افراد این گروه کمتر از حد لازم برای یک میانگین بی‌نام است."
    >
      <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
        <path d="M3 10s2.5-4.5 7-4.5 7 4.5 7 4.5-2.5 4.5-7 4.5S3 10 3 10z" />
        <path d="M4 4l12 12" />
      </svg>
      محرمانه
    </span>
  );
}
