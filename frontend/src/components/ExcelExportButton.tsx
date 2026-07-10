import { useState } from "react";
import { apiClient } from "../api/client";
import { useToast } from "./Toast";

/** دکمه دانلود خروجی Excel — الگوی مشترک همه فهرست‌های HR. params همان فیلترهای
 * فعال صفحه است تا خروجی دقیقاً همان چیزی باشد که کاربر می‌بیند. */
export function ExcelExportButton({
  url,
  filename,
  params,
}: {
  url: string;
  filename: string;
  params?: Record<string, unknown>;
}) {
  const [downloading, setDownloading] = useState(false);
  const { showError } = useToast();

  async function download() {
    setDownloading(true);
    try {
      const { data } = await apiClient.get(url, { responseType: "blob", params });
      const objectUrl = URL.createObjectURL(data as Blob);
      const a = document.createElement("a");
      a.href = objectUrl;
      a.download = filename;
      a.click();
      setTimeout(() => URL.revokeObjectURL(objectUrl), 10_000);
    } catch {
      showError("دانلود خروجی Excel با خطا مواجه شد؛ دوباره تلاش کنید");
    } finally {
      setDownloading(false);
    }
  }

  return (
    <button
      type="button"
      onClick={download}
      disabled={downloading}
      title="خروجی Excel با فیلترهای فعال فعلی"
      className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-xl border border-gray-200 bg-white px-3 py-1.5 text-sm font-medium text-gray-600 shadow-sm transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
    >
      <svg viewBox="0 0 20 20" className="h-4 w-4 text-green-600" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M10 3v10m0 0l-3.5-3.5M10 13l3.5-3.5M4 15v1a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1v-1" />
      </svg>
      {downloading ? "در حال آماده‌سازی…" : "خروجی Excel"}
    </button>
  );
}
