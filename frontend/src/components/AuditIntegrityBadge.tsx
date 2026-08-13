/** وضعیت یکپارچگی زنجیرهٔ لاگ حسابرسی (P1-09).
 *
 * زنجیرهٔ هش بدون راهی برای *دیدن* نتیجه‌اش، فقط چند ستون بی‌استفاده است. این نشان
 * به HR می‌گوید لاگ از ابتدا بازمحاسبه شد و با آن‌چه ذخیره شده می‌خواند — یعنی
 * می‌تواند به آن به‌عنوان مدرک استناد کند، نه صرفاً مستندات.
 */
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../api/client";

interface Integrity {
  ok: boolean;
  checked: number;
  broken_at_id: number | null;
  reason: string | null;
}

export function AuditIntegrityBadge() {
  const { data, isPending, error } = useQuery({
    queryKey: ["audit-log", "integrity"],
    queryFn: async () => (await apiClient.get<Integrity>("/audit-log/integrity")).data,
    // راستی‌آزمایی کل زنجیره ارزان نیست و پاسخش هم سریع کهنه نمی‌شود
    staleTime: 60_000,
  });

  if (isPending || error) return null;

  if (!data.ok) {
    return (
      <span
        className="inline-flex items-center gap-1.5 rounded-full bg-red-50 px-3 py-1 text-xs font-medium text-red-700"
        title={`${data.reason ?? ""} — نخستین ردیف ناسازگار: #${data.broken_at_id}`}
      >
        <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
          <path d="M10 6v5m0 3h.01" />
          <circle cx="10" cy="10" r="7.5" />
        </svg>
        زنجیرهٔ یکپارچگی شکسته است
      </span>
    );
  }

  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full bg-green-50 px-3 py-1 text-xs font-medium text-green-700"
      title={`${data.checked.toLocaleString("fa-IR")} رویداد از ابتدای زنجیره بازمحاسبه و تأیید شد`}
    >
      <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M4 10.5l3.5 3.5L16 6" />
      </svg>
      یکپارچگی تأیید شد ({data.checked.toLocaleString("fa-IR")} رویداد)
    </span>
  );
}
