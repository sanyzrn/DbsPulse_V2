import { useRef, useState, type ReactNode } from "react";
import { toPng } from "html-to-image";
import { useToast } from "./Toast";

/** ظرف نمودار با دکمهٔ دانلود PNG.
 *
 * تصویر خروجی باید **به‌تنهایی قابل فهم باشد** — چیزی که بشود در گزارش چسباند و
 * خواننده بفهمد به چه نگاه می‌کند. نسخهٔ قبلی فقط ناحیهٔ رسم را ضبط می‌کرد، پس
 * خروجی یک نوار بی‌عنوان بود: نه معلوم بود نمودارِ چیست، نه واحدش چیست، و
 * برچسب‌های دو سرِ خط‌کش هم از لبه بیرون می‌زدند و نصفه می‌شدند.
 *
 * حالا عنوان و زیرعنوان داخل ناحیهٔ ضبط‌اند و فقط دکمه‌ها بیرون می‌مانند —
 * دکمه‌ای که در تصویرِ یک گزارش چاپ شود بی‌معناست.
 */
export function ChartDownloadCard({
  title,
  subtitle,
  filename,
  actions,
  children,
}: {
  title: string;
  subtitle?: string;
  filename: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  const captureRef = useRef<HTMLDivElement>(null);
  const headingRef = useRef<HTMLDivElement>(null);
  const [busy, setBusy] = useState(false);
  const { showError } = useToast();

  async function download() {
    const node = captureRef.current;
    if (!node) return;
    setBusy(true);
    // فضایی که روی صفحه برای دکمه‌ها رزرو شده، در تصویر خروجی فقط یک شکاف خالیِ
    // ۲۰۰ پیکسلی کنار عنوان است — دکمه‌ای آن‌جا نیست. مستقیم روی DOM برداشته
    // می‌شود و نه با state، چون html-to-image همین لحظه از DOM کپی می‌گیرد و
    // منتظر رندر بعدی React نمی‌ماند.
    const heading = headingRef.current;
    const reserved = heading?.style.paddingInlineEnd ?? "";
    if (heading) heading.style.paddingInlineEnd = "0px";
    try {
      const dataUrl = await toPng(node, {
        backgroundColor: getComputedStyle(document.documentElement)
          .getPropertyValue("--chart-surface")
          .trim() || "#ffffff",
        pixelRatio: 2,
        // html-to-image دقیقاً به اندازهٔ جعبهٔ عنصر می‌بُرد. بدون این دو، سایهٔ
        // نقطه‌ها و لبهٔ ریل درست روی مرز تصویر می‌افتند.
        width: node.offsetWidth,
        height: node.offsetHeight,
      });
      const link = document.createElement("a");
      link.href = dataUrl;
      link.download = filename;
      link.click();
    } catch {
      showError("دانلود تصویر نمودار با خطا مواجه شد؛ دوباره تلاش کنید");
    } finally {
      if (heading) heading.style.paddingInlineEnd = reserved;
      setBusy(false);
    }
  }

  return (
    <div className="relative rounded-2xl border border-gray-200 bg-white shadow-card">
      {/* دکمه‌ها بیرون از ناحیهٔ ضبط‌اند تا در تصویر خروجی نیایند */}
      <div className="absolute end-5 top-5 z-10 flex min-w-0 max-w-[60%] flex-wrap items-center justify-end gap-2">
        {actions}
        <button
          type="button"
          onClick={download}
          disabled={busy}
          title="دانلود این نمودار به‌صورت تصویر PNG"
          className="inline-flex items-center gap-1.5 rounded-xl border border-gray-200 bg-white px-3 py-1.5 text-sm font-medium text-gray-600 shadow-sm transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <svg viewBox="0 0 20 20" className="h-4 w-4 text-pulse-600" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M10 3v10m0 0l-3.5-3.5M10 13l3.5-3.5M4 15v1a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1v-1" />
          </svg>
          {busy ? "در حال آماده‌سازی…" : "دانلود PNG"}
        </button>
      </div>

      {/* ناحیهٔ ضبط: عنوان + زیرعنوان + خودِ نمودار */}
      <div ref={captureRef} className="rounded-2xl bg-white p-5">
        {/* فضای دکمه‌ها رزرو می‌شود تا عنوان زیرشان نرود — هنگام ضبط برداشته می‌شود */}
        <div ref={headingRef} style={{ paddingInlineEnd: "13rem" }}>
          <h3 className="text-base font-bold text-gray-900">{title}</h3>
          {subtitle && <p className="mt-0.5 text-xs text-gray-500">{subtitle}</p>}
        </div>
        <div className="mt-4">{children}</div>
      </div>
    </div>
  );
}
