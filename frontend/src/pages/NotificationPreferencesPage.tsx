/** ارجحیت دریافت اعلان (P1-03).
 *
 * تا امروز اعلان‌ها فقط درون‌برنامه‌ای بودند، یعنی کل گردش‌کار به این وابسته بود
 * که تأییدکننده خودش یادش بیفتد وارد شود.
 *
 * دو تصمیم که شکل این صفحه را ساخته‌اند:
 *
 * ۱. **کانالی که سازمان تنظیم نکرده، اصلاً نشان داده نمی‌شود.** تیکی که
 *    روشن‌کردنش هیچ اثری ندارد، کاربر را منتظر پیامی می‌گذارد که هرگز قرار نبوده
 *    بیاید — بدتر از نبودن گزینه.
 * ۲. **پیش‌فرض خاموش است.** روشن‌کردن، انتخاب خودِ کاربر است؛ نه چیزی که با یک
 *    استقرار به همه تحمیل شود.
 */
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiClient, extractErrorMessage } from "../api/client";
import { useToast } from "../components/Toast";
import { Button } from "../ui/Button";
import { Card, TableSkeleton } from "../ui/Card";

interface Preferences {
  email: string | null;
  phone: string | null;
  notify_by_email: boolean;
  notify_by_sms: boolean;
  email_available: boolean;
  sms_available: boolean;
}

const inputClass =
  "w-full rounded-xl border border-gray-200 bg-gray-100 px-3 py-2 text-sm text-gray-900 outline-none transition-colors focus:border-pulse-500 focus:bg-white";

export function NotificationPreferencesPage() {
  const { showSuccess, showError } = useToast();
  const [form, setForm] = useState<Preferences | null>(null);
  const [saving, setSaving] = useState(false);

  const { data, isPending, error, refetch } = useQuery({
    queryKey: ["notifications", "preferences"],
    queryFn: async () =>
      (await apiClient.get<Preferences>("/notifications/preferences")).data,
  });

  // تا وقتی کاربر دست نزده، فرم از سرور پر می‌شود
  useEffect(() => {
    if (data && form === null) setForm(data);
  }, [data, form]);

  async function save() {
    if (!form) return;
    setSaving(true);
    try {
      await apiClient.put("/notifications/preferences", {
        email: form.email || null,
        phone: form.phone || null,
        notify_by_email: form.notify_by_email,
        notify_by_sms: form.notify_by_sms,
      });
      await refetch();
      showSuccess("تنظیمات اعلان ذخیره شد");
    } catch (err) {
      showError(extractErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  if (error != null)
    return <p className="p-6 text-center text-sm text-red-600">{extractErrorMessage(error)}</p>;

  const nothingConfigured = data && !data.email_available && !data.sms_available;

  return (
    <div className="mx-auto max-w-2xl py-6">
      <Card title="اعلان‌ها">
        <p className="mb-5 text-sm text-gray-500">
          اعلان‌ها همیشه در زنگولهٔ بالای صفحه هستند. این‌جا مشخص می‌کنید کدام‌ها را
          بیرون از سامانه هم دریافت کنید — فقط مواردی که کاری روی میز شماست یا
          نتیجه‌ای دربارهٔ شما قطعی شده.
        </p>

        {isPending || !form ? (
          <TableSkeleton rows={3} />
        ) : nothingConfigured ? (
          <div className="rounded-xl bg-gray-50 px-4 py-5 text-sm text-gray-600">
            سازمان شما هنوز هیچ سرویس ایمیل یا پیامکی را تنظیم نکرده است. تا آن زمان،
            اعلان‌ها فقط در همین سامانه دیده می‌شوند.
          </div>
        ) : (
          <div className="space-y-5">
            {data.email_available && (
              <ChannelRow
                label="ایمیل"
                placeholder="you@example.com"
                type="email"
                value={form.email ?? ""}
                enabled={form.notify_by_email}
                onValue={(email) => setForm({ ...form, email })}
                onToggle={(notify_by_email) => setForm({ ...form, notify_by_email })}
              />
            )}
            {data.sms_available && (
              <ChannelRow
                label="پیامک"
                placeholder="۰۹۱۲۰۰۰۰۰۰۰"
                type="tel"
                value={form.phone ?? ""}
                enabled={form.notify_by_sms}
                onValue={(phone) => setForm({ ...form, phone })}
                onToggle={(notify_by_sms) => setForm({ ...form, notify_by_sms })}
              />
            )}

            <div className="flex justify-end border-t border-gray-100 pt-4">
              <Button onClick={save} disabled={saving}>
                {saving ? "در حال ذخیره…" : "ذخیره"}
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}

function ChannelRow({
  label,
  placeholder,
  type,
  value,
  enabled,
  onValue,
  onToggle,
}: {
  label: string;
  placeholder: string;
  type: string;
  value: string;
  enabled: boolean;
  onValue: (value: string) => void;
  onToggle: (enabled: boolean) => void;
}) {
  return (
    <div className="rounded-2xl border border-gray-100 p-4">
      <label className="flex items-center justify-between gap-3">
        <span className="text-sm font-medium text-gray-800">دریافت با {label}</span>
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => onToggle(e.target.checked)}
          className="h-5 w-5 shrink-0 accent-pulse-600"
          aria-label={`دریافت اعلان با ${label}`}
        />
      </label>
      <label className="mt-3 block text-xs font-medium text-gray-600">
        {label === "ایمیل" ? "نشانی ایمیل" : "شمارهٔ همراه"}
        <input
          type={type}
          dir="ltr"
          className={`${inputClass} mt-1 text-left`}
          placeholder={placeholder}
          value={value}
          onChange={(e) => onValue(e.target.value)}
        />
      </label>
    </div>
  );
}
