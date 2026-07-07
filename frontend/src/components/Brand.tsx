import { motion } from "motion/react";

/** نشان‌های موقت برنامه و توسعه‌دهنده — قرمز برند، تک‌رنگ.
 * نشان اصلی شامل موج پالس متحرک است که هویت «DbsPulse» را منتقل می‌کند. */

export function BrandMark({ className = "h-9 w-9" }: { className?: string }) {
  return (
    <motion.svg
      viewBox="0 0 32 32"
      className={className}
      aria-hidden="true"
      initial={false}
    >
      <defs>
        <filter id="brand-mark-glow">
          <feGaussianBlur stdDeviation="0.6" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      <rect width="32" height="32" rx="9" fill="#b61615" />
      {/* خط پالس متحرک — موج قلب/ضربان */}
      <motion.path
        d="M5 17h4l2-6 4.5 11 2.5-7 1.5 3.5h7"
        fill="none"
        stroke="white"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
        filter="url(#brand-mark-glow)"
        initial={{ pathLength: 0, opacity: 0 }}
        animate={{ pathLength: 1, opacity: 1 }}
        transition={{ duration: 1.2, ease: "easeInOut" }}
      />
    </motion.svg>
  );
}

export function DevMark({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" className={className} aria-hidden="true">
      <rect width="20" height="20" rx="6" fill="#b61615" />
      <text
        x="10"
        y="13.5"
        textAnchor="middle"
        fontSize="8"
        fontWeight="700"
        fill="white"
        fontFamily="Vazirmatn, Tahoma, sans-serif"
      >
        dbs
      </text>
    </svg>
  );
}
