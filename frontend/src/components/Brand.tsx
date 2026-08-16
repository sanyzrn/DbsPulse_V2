import { useState } from "react";
import { motion } from "motion/react";

// مسیر مطلق، نه نسبی. با `./logo/…` این نشانی از صفحه‌ای مثل `/hr/dashboard`
// به `/hr/logo/…` حل می‌شد و ۴۰۴ می‌گرفت — یعنی لوگوی واقعی هیچ‌وقت دیده نشده
// بود و همیشه نشانِ جایگزین رندر می‌شد.
const DEV_LOGO_URL = "/logo/Dbs_logo_single.png";
const DEV_LOGO_URL_DARK = "/logo/Dbs_logo_single_w.png";

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
  // دو فایل، چون لوگو تک‌رنگ نیست: نسخهٔ اصلی نیمهٔ مشکی دارد که روی تم شب
  // ناپدید می‌شود، و نسخهٔ `_w` همان شکل است با رنگ روشن.
  //
  // انتخاب با CSS انجام می‌شود نه با state: تم پیش از رندرِ React روی `<html>`
  // نشسته، پس با CSS هیچ لحظه‌ای لوگوی اشتباه دیده نمی‌شود.
  const [failed, setFailed] = useState(false);
  if (!failed) {
    return (
      <span className={`${className} inline-block`}>
        <img
          src={DEV_LOGO_URL}
          alt="DbsStudio"
          className="h-full w-full object-contain dark-hidden"
          loading="lazy"
          decoding="async"
          onError={() => setFailed(true)}
        />
        <img
          src={DEV_LOGO_URL_DARK}
          alt=""
          aria-hidden
          className="h-full w-full object-contain light-hidden"
          loading="lazy"
          decoding="async"
          onError={() => setFailed(true)}
        />
      </span>
    );
  }
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
