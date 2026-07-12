import type { ComponentPropsWithRef } from "react";

type Variant = "primary" | "secondary" | "link" | "danger" | "ghost";

const STYLES: Record<Variant, string> = {
  primary:
    "relative overflow-hidden rounded-xl bg-pulse-600 px-5 py-2.5 text-sm font-semibold text-white shadow-md shadow-pulse-500/20 transition-all duration-300 ease-out hover:bg-pulse-700 hover:shadow-lg hover:shadow-pulse-500/30 hover:-translate-y-0.5 active:translate-y-0 active:shadow-md disabled:opacity-50 disabled:hover:translate-y-0 disabled:hover:shadow-md",
  secondary:
    "rounded-xl border border-gray-200 bg-white px-5 py-2.5 text-sm font-medium text-gray-700 shadow-sm transition-all duration-300 ease-out hover:bg-gray-50 hover:shadow-md hover:-translate-y-0.5 disabled:opacity-50",
  danger:
    "rounded-xl bg-amber-600 px-5 py-2.5 text-sm font-semibold text-white shadow-md shadow-amber-500/20 transition-all duration-300 ease-out hover:bg-amber-700 hover:shadow-lg hover:-translate-y-0.5 active:translate-y-0 disabled:opacity-50",
  link: "relative text-sm font-semibold text-pulse-600 transition-colors duration-200 hover:text-pulse-700 disabled:opacity-50 underline-offset-4 hover:underline decoration-pulse-300 underline",
  ghost:
    "rounded-xl px-3 py-2 text-sm font-medium text-gray-600 transition-all duration-300 ease-out hover:bg-gray-100 hover:text-gray-900 disabled:opacity-50",
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
