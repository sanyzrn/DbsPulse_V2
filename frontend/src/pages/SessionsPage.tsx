/** نشست‌های فعال کاربر (P2-06).
 *
 * تا پیش از این تنها ابزار موجود «همه‌جا خارج شو» بود (تغییر رمز). یعنی برای بستن
 * یک لپ‌تاپِ گم‌شده باید همهٔ دستگاه‌های دیگر را هم از دست می‌دادی — و پیش از آن،
 * اصلاً راهی نبود که بفهمی چیزی باز مانده است یا نه.
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient, extractErrorMessage } from "../api/client";
import { useConfirm } from "../components/ConfirmDialog";
import { useToast } from "../components/Toast";
import { Button } from "../ui/Button";
import { Card, EmptyState, TableSkeleton } from "../ui/Card";
import { formatDateTime } from "../utils/dates";

interface ActiveSession {
  id: number;
  user_agent: string | null;
  ip: string | null;
  created_at: string;
  last_used_at: string | null;
  is_current: boolean;
}

/** رشتهٔ خام user-agent را به چیزی که آدم می‌شناسد تبدیل می‌کند.
 *
 * عمداً تحلیل کاملِ user-agent نیست: هدف فقط این است که کاربر «این لپ‌تاپ خودم»
 * را از «این را نمی‌شناسم» تشخیص بدهد. رشتهٔ کامل در tooltip می‌ماند تا اگر
 * حدسِ ما غلط بود، حقیقت در دسترس باشد. */
export function describeDevice(userAgent: string | null): string {
  if (!userAgent) return "دستگاه نامشخص";

  const browser =
    /Edg\//.test(userAgent) ? "Edge"
    : /OPR\/|Opera/.test(userAgent) ? "Opera"
    : /Firefox\//.test(userAgent) ? "Firefox"
    // ترتیب مهم است: کروم هم «Safari» را در رشته‌اش دارد، پس سافاری آخر می‌آید
    : /Chrome\//.test(userAgent) ? "Chrome"
    : /Safari\//.test(userAgent) ? "Safari"
    : null;

  const platform =
    /Windows/.test(userAgent) ? "ویندوز"
    : /Android/.test(userAgent) ? "اندروید"
    : /iPhone|iPad|iOS/.test(userAgent) ? "iOS"
    : /Mac OS X|Macintosh/.test(userAgent) ? "مک"
    : /Linux/.test(userAgent) ? "لینوکس"
    : null;

  if (browser && platform) return `${browser} روی ${platform}`;
  if (browser) return browser;
  if (platform) return platform;
  // رشتهٔ ناشناخته را خودش نشان می‌دهیم، نه «نامشخص» — دیدنش بهتر از پنهان‌کردنش است
  return userAgent.slice(0, 60);
}

export function SessionsPage() {
  const { showSuccess, showError } = useToast();
  const confirm = useConfirm();
  const queryClient = useQueryClient();

  const { data: sessions = [], isPending, error } = useQuery({
    queryKey: ["auth", "sessions"],
    queryFn: async () => (await apiClient.get<ActiveSession[]>("/auth/sessions")).data,
  });

  async function revoke(session: ActiveSession) {
    const ok = await confirm({
      title: "بستن این نشست؟",
      description: `${describeDevice(session.user_agent)} بلافاصله از سامانه خارج می‌شود.`,
      confirmLabel: "بستن نشست",
    });
    if (!ok) return;
    try {
      await apiClient.delete(`/auth/sessions/${session.id}`);
      await queryClient.invalidateQueries({ queryKey: ["auth", "sessions"] });
      showSuccess("نشست بسته شد");
    } catch (err) {
      showError(extractErrorMessage(err));
    }
  }

  return (
    <div className="mx-auto max-w-2xl py-6">
      <Card title="نشست‌های فعال">
        <p className="mb-4 text-sm text-gray-500">
          هر دستگاهی که با حساب شما وارد شده، این‌جا یک ردیف است. اگر ردیفی را
          نمی‌شناسید ببندیدش و رمز عبورتان را عوض کنید.
        </p>

        {isPending ? (
          <TableSkeleton rows={3} />
        ) : error ? (
          <p className="text-sm text-red-600">{extractErrorMessage(error)}</p>
        ) : sessions.length === 0 ? (
          <EmptyState>نشست فعالی ثبت نشده است.</EmptyState>
        ) : (
          <ul className="space-y-2">
            {sessions.map((session) => (
              <li
                key={session.id}
                className={`flex flex-wrap items-center justify-between gap-3 rounded-xl border px-4 py-3 ${
                  session.is_current
                    ? "border-pulse-200 bg-pulse-50/50"
                    : "border-gray-200 bg-white"
                }`}
              >
                <div className="min-w-0">
                  <p className="flex items-center gap-2 text-sm font-medium text-gray-800">
                    <span title={session.user_agent ?? undefined}>
                      {describeDevice(session.user_agent)}
                    </span>
                    {session.is_current && (
                      <span className="rounded-full bg-pulse-600 px-2 py-0.5 text-[10px] font-bold text-white">
                        همین دستگاه
                      </span>
                    )}
                  </p>
                  <p className="mt-0.5 text-xs text-gray-400">
                    {session.ip && <span dir="ltr">{session.ip}</span>}
                    {session.ip && " · "}
                    آخرین فعالیت:{" "}
                    {session.last_used_at ? formatDateTime(session.last_used_at) : "—"}
                  </p>
                </div>
                {/* نشست جاری دکمهٔ بستن ندارد: کاربر برای خروج از همین دستگاه
                    «خروج» را دارد، و دکمه‌ای که کاربر را وسط کار بیرون بیندازد
                    فقط یک تلهٔ کلیکِ اشتباه است. */}
                {!session.is_current && (
                  <Button variant="secondary" onClick={() => revoke(session)}>
                    بستن
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
