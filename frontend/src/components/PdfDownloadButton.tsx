import { useState } from "react";
import { apiClient, extractErrorMessage } from "../api/client";
import { useToast } from "./Toast";

/** دانلود/چاپ کارنامهٔ رسمی — یک مسیر مشترک برای هرجایی که این سند گرفته می‌شود.
 *
 * قبلاً پنل کارمند یک `<a href="/api/...">` ساده بود. مرورگر روی ناوبری معمولی
 * هدر `Authorization` نمی‌فرستد — آن هدر را اینترسپتور axios اضافه می‌کند و
 * تگ لینک از آن عبور نمی‌کند — پس درخواست بدون توکن می‌رفت و کارمند به‌جای سند،
 * متن خام `{"detail":"توکن نامعتبر یا منقضی‌شده است"}` می‌دید. سندی دربارهٔ
 * خودش، با پیامی که می‌گفت اجازه ندارد.
 *
 * پس فایل از مسیر همان کلاینتِ احراز هویت‌شده گرفته می‌شود و به‌صورت blob باز
 * می‌شود.
 */
export function PdfDownloadButton({
  evaluationId,
  filename,
  label = "دریافت کارنامهٔ رسمی (PDF)",
  className,
}: {
  evaluationId: number;
  filename: string;
  label?: string;
  className?: string;
}) {
  const [busy, setBusy] = useState(false);
  const { showError } = useToast();

  async function open() {
    // پنجره باید هم‌زمان با کلیک کاربر (sync) باز شود، وگرنه مرورگر آن را
    // پاپ‌آپ مسدودشده تلقی می‌کند: بعد از یک await دیگر «مستقیماً ناشی از
    // تعامل کاربر» به‌حساب نمی‌آید.
    const printWindow = window.open("", "_blank");
    setBusy(true);
    try {
      const { data } = await apiClient.get(`/evaluations/${evaluationId}/summary.pdf`, {
        responseType: "blob",
      });
      const url = URL.createObjectURL(new Blob([data as BlobPart], { type: "application/pdf" }));
      if (printWindow) {
        printWindow.location.href = url;
      } else {
        // اگر حتی پنجرهٔ خالی هم مسدود شده، دست‌کم فایل دانلود شود.
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        showError("باز کردن پنجرهٔ جدید توسط مرورگر مسدود شد؛ فایل به‌جای آن دانلود شد.");
      }
      setTimeout(() => URL.revokeObjectURL(url), 30_000);
    } catch (err) {
      printWindow?.close();
      showError(extractErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <button
      type="button"
      onClick={open}
      disabled={busy}
      className={
        className ??
        "inline-flex items-center gap-1.5 rounded-xl border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-50"
      }
    >
      <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
        <path d="M10 3v9m0 0l-3-3m3 3l3-3M4 15v2h12v-2" />
      </svg>
      {busy ? "در حال آماده‌سازی…" : label}
    </button>
  );
}
