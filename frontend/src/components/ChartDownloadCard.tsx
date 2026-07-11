import { useRef, useState, type ReactNode } from "react";
import { toPng } from "html-to-image";
import { useToast } from "./Toast";

/** ظرف نمودار با دکمهٔ دانلود PNG. کل ناحیهٔ نمودار (ref) با html-to-image به تصویر
 * تبدیل و دانلود می‌شود تا HR بتواند هر نمودار را جداگانه ذخیره کند. */
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
  const [busy, setBusy] = useState(false);
  const { showError } = useToast();

  async function download() {
    if (!captureRef.current) return;
    setBusy(true);
    try {
      const dataUrl = await toPng(captureRef.current, {
        backgroundColor: "#ffffff",
        pixelRatio: 2,
      });
      const a = document.createElement("a");
      a.href = dataUrl;
      a.download = filename;
      a.click();
    } catch {
      showError("دانلود تصویر نمودار با خطا مواجه شد؛ دوباره تلاش کنید");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-card">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-base font-bold text-gray-900">{title}</h3>
          {subtitle && <p className="mt-0.5 text-xs text-gray-500">{subtitle}</p>}
        </div>
        <div className="flex items-center gap-2">
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
      </div>
      {/* فقط ناحیهٔ نمودار (بدون دکمه‌ها) در تصویر خروجی ثبت می‌شود */}
      <div ref={captureRef} className="bg-white">
        {children}
      </div>
    </div>
  );
}
