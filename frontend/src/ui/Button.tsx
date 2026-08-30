import type { ComponentPropsWithRef } from "react";

type Variant = "primary" | "secondary" | "link" | "danger" | "ghost";

/* دکمه‌ها دیگر با hover بالا نمی‌پرند و سایهٔ رنگی ندارند.
   `hover:-translate-y-0.5` روی هر دکمه یعنی هر بار که ماوس از روی نواری از
   دکمه‌ها رد می‌شود، رابط تکان می‌خورد؛ و سایهٔ قرمزِ زیر دکمهٔ اصلی، لبهٔ آن را
   مبهم می‌کرد. بازخوردِ hover حالا فقط تغییر رنگ است + یک فشردگیِ خیلی ریز در
   لحظهٔ کلیک (`active:scale`) که حسِ فشردنِ واقعی می‌دهد — سریع‌تر، آرام‌تر، و
   روی تم تیره هم درست کار می‌کند.
   پدینگ هم یک پله جمع‌تر شده: دکمهٔ ۴۲ پیکسلی در نوارابزارهای شلوغ، فضای
   عمودیِ بیشتری می‌خورد تا ضرورت دارد. */
const STYLES: Record<Variant, string> = {
  primary:
    "rounded-xl bg-pulse-600 px-4 py-2 text-sm font-semibold text-white transition-[background-color,scale] duration-150 hover:bg-pulse-700 active:scale-[0.98] active:bg-pulse-800 disabled:opacity-50",
  secondary:
    "rounded-xl border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-[background-color,border-color,scale] duration-150 hover:border-gray-300 hover:bg-gray-50 hover:text-gray-900 active:scale-[0.98] disabled:opacity-50",
  // کهربایی و نه قرمز: قرمزِ این سامانه رنگِ برند است و روی دکمهٔ اصلی می‌نشیند،
  // پس نمی‌تواند هم‌زمان معنای «خطرناک» را هم حمل کند.
  danger:
    "rounded-xl bg-amber-600 px-4 py-2 text-sm font-semibold text-white transition-[background-color,scale] duration-150 hover:bg-amber-700 active:scale-[0.98] active:bg-amber-800 disabled:opacity-50",
  // زیرخط فقط در hover: در جدولی که این دکمه در هر ردیف تکرار می‌شود، زیرخطِ
  // همیشگی یک ستونِ کاملاً قرمز و خط‌کشیده می‌ساخت.
  link:
    "rounded-lg text-sm font-semibold text-pulse-700 underline-offset-4 transition-colors hover:text-pulse-800 hover:underline disabled:opacity-50",
  ghost:
    "rounded-xl px-2.5 py-1.5 text-sm font-medium text-gray-600 transition-colors duration-150 hover:bg-gray-100 hover:text-gray-900 disabled:opacity-50",
};

/** دکمه استاندارد با واریانت‌های مختلف و حالت بارگذاری. */
export function Button({
  variant = "primary",
  className = "",
  type = "button",
  loading,
  children,
  ...props
}: ComponentPropsWithRef<"button"> & {
  variant?: Variant;
  loading?: boolean;
}) {
  return (
    <button
      type={type}
      className={`${STYLES[variant]} ${loading ? "pointer-events-none opacity-60" : ""} ${className}`}
      disabled={props.disabled || loading}
      {...props}
    >
      <span className="inline-flex items-center gap-2">
        {loading && <Spinner />}
        {children}
      </span>
    </button>
  );
}

/** اسپینر کوچک SVG برای حالت بارگذاری دکمه‌ها. */
function Spinner({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg
      className={`animate-spin ${className}`}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <circle
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
        className="opacity-20"
      />
      <path
        d="M12 2a10 10 0 0 1 10 10"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
      />
    </svg>
  );
}
