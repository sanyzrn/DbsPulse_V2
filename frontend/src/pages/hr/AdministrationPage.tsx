/** مدیریت سامانه: مجوزها و بخش‌ها (نیمهٔ دوم P0-03).
 *
 * این صفحه عمداً از «کاربران» جداست. آن‌جا دربارهٔ *چه کسی وارد سامانه می‌شود*
 * است؛ این‌جا دربارهٔ *چه کسی خودِ سامانه را عوض می‌کند*. تا امروز هر دو یکی
 * بودند: همان کاربری که پرونده‌ها را تأیید می‌کند، شاخص‌ها را هم عوض می‌کرد و
 * قواعد نمره‌دهی را فعال می‌کرد.
 */
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient, extractErrorMessage } from "../../api/client";
import { usePermissions, type Capability } from "../../auth/PermissionsContext";
import { useConfirm } from "../../components/ConfirmDialog";
import { useToast } from "../../components/Toast";
import { Card, EmptyState, PageHeader, TableSkeleton } from "../../ui/Card";
import { ROLE_LABELS, type UserRole } from "../../types";

interface CapabilityHolder {
  user_id: number;
  username: string;
  role: UserRole;
  is_active: boolean;
  capabilities: Capability[];
}

interface ModuleState {
  key: string;
  label: string;
  description: string;
  enabled: boolean;
}

/** برچسب فارسی هر مجوز، و — مهم‌تر — این‌که نداشتنش یعنی چه. */
const CAPABILITY_INFO: Record<Capability, { label: string; scope: string }> = {
  manage_users: { label: "حساب‌های کاربری", scope: "ساخت، ویرایش و غیرفعال‌کردن حساب" },
  // عمداً از «حساب‌های کاربری» جداست: تا امروز یکی بودند، یعنی هرکس می‌توانست
  // حساب بسازد می‌توانست به خودش هم هر اختیاری بدهد.
  manage_capabilities: { label: "دادن مجوز", scope: "تعیین اینکه هر حساب چه اختیاری دارد — همین جدول" },
  manage_scoring: { label: "شاخص‌ها و طرح نمره‌دهی", scope: "تغییر سؤال‌های فرم و قواعد امتیازدهی" },
  manage_integrations: { label: "ایمیل و پیامک", scope: "تنظیم سرویس‌های ارسال بیرونی" },
  manage_modules: { label: "بخش‌های سامانه", scope: "روشن و خاموش کردن بخش‌ها" },
  view_audit_log: { label: "گزارش کامل رویدادها", scope: "کل لاگ ممیزی، شامل امتیاز و نتیجهٔ پرونده‌ها" },
  view_diagnostics: { label: "سلامت سامانه", scope: "صف تحویل، اجرای زمان‌بند، وضعیت — فقط خواندنی" },
};

const CAPABILITY_ORDER = Object.keys(CAPABILITY_INFO) as Capability[];

interface SeparationStatus {
  separated: boolean;
  overlapping_users: { username: string; role: UserRole; capabilities: Capability[] }[];
  dedicated_admin_count: number;
}

export function AdministrationPage() {
  const { can } = usePermissions();

  return (
    <div className="space-y-5">
      <PageHeader
        title="مدیریت سامانه"
        subtitle="چه کسی می‌تواند خودِ سامانه را عوض کند، و کدام بخش‌ها فعال‌اند"
      />
      {can("manage_capabilities") && <SeparationCard />}
      {can("manage_capabilities") && <CapabilitiesCard />}
      {can("manage_modules") && <ModulesCard />}
      {!can("manage_users") && !can("manage_modules") && (
        <Card>
          <EmptyState>
            شما مجوز مدیریت سامانه را ندارید. اگر لازمش دارید، از مدیر سامانه بخواهید
            آن را به شما بدهد.
          </EmptyState>
        </Card>
      )}
    </div>
  );
}

/** آیا تفکیک وظایف واقعاً برقرار است، یا فقط ممکن شده؟
 *
 * این کارت وجود دارد چون سازوکارِ خاموش بدترین حالت است: از بیرون «انجام‌شده»
 * به‌نظر می‌رسد و خیال راحت می‌دهد، در حالی که هیچ چیز عوض نشده. مایگریشن عمداً
 * همهٔ مجوزها را به کاربران منابع انسانی داد تا استقراری نشکند — ولی آن حالت،
 * حالتِ *پیش‌فرض* است نه حالتِ *انتخاب‌شده*، و کسی باید بداند.
 */
function SeparationCard() {
  const { data } = useQuery({
    queryKey: ["administration", "separation"],
    queryFn: async () =>
      (await apiClient.get<SeparationStatus>("/administration/separation")).data,
  });

  if (!data) return null;

  if (data.separated) {
    return (
      <div className="rounded-2xl border border-green-200 bg-green-50/50 p-5">
        <p className="text-sm font-bold text-green-800">تفکیک وظایف برقرار است</p>
        <p className="mt-1 text-xs leading-relaxed text-green-900/70">
          هیچ حسابی هم‌زمان در زنجیرهٔ ارزیابی نیست و قواعد را عوض نمی‌کند. اگر روزی
          نتیجه‌ای زیر سؤال برود، می‌شود نشان داد کسی که تصمیم گرفته همان کسی نبوده
          که قاعده را نوشته.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-amber-200 bg-amber-50/50 p-5">
      <p className="text-sm font-bold text-amber-900">تفکیک وظایف هنوز برقرار نیست</p>
      <p className="mt-1 text-xs leading-relaxed text-amber-900/80">
        این حساب‌ها هم در زنجیرهٔ ارزیابی جایگاه دارند و هم می‌توانند قواعد را عوض
        کنند. یعنی همان کسی که پرونده‌ها را تأیید می‌کند، شاخص‌ها و قواعد نمره‌دهی را
        هم تعیین می‌کند:
      </p>
      <ul className="mt-3 flex flex-wrap gap-2">
        {data.overlapping_users.map((user) => (
          <li
            key={user.username}
            className="rounded-lg bg-white px-2.5 py-1 text-xs text-amber-900 ring-1 ring-amber-200"
          >
            {user.username}
            <span className="text-amber-900/50"> · {ROLE_LABELS[user.role] ?? user.role}</span>
          </li>
        ))}
      </ul>
      <p className="mt-3 border-t border-amber-200 pt-3 text-xs leading-relaxed text-amber-900/80">
        {data.dedicated_admin_count > 0 ? (
          <>
            حساب اختصاصی مدیریت از قبل ساخته شده است. برای کامل‌کردن تفکیک، در جدول
            پایین مجوز «کاربران و مجوزها» و «شاخص‌ها و طرح نمره‌دهی» را از حساب‌های
            بالا بردارید.
          </>
        ) : (
          <>
            برای تفکیک: یک کاربر با نقش «پشتیبانی فنی» بسازید، مجوزهای اداری را به او
            بدهید، و سپس از حساب‌های بالا بگیرید. سامانه نمی‌گذارد آخرین حسابِ
            مجوزدهنده خودش را حذف کند، پس بن‌بست پیش نمی‌آید.
          </>
        )}
      </p>
      <p className="mt-2 text-[11px] text-amber-900/60">
        این وضعیت عمدی و سازگار با گذشته است — نه خطا. ولی تا وقتی برقرار نشده،
        سامانه آن را ادعا نمی‌کند.
      </p>
    </div>
  );
}

function CapabilitiesCard() {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [saving, setSaving] = useState<number | null>(null);

  const { data: holders = [], isPending, error } = useQuery({
    queryKey: ["administration", "capabilities"],
    queryFn: async () =>
      (await apiClient.get<CapabilityHolder[]>("/administration/capabilities")).data,
  });

  async function toggle(holder: CapabilityHolder, capability: Capability) {
    const next = holder.capabilities.includes(capability)
      ? holder.capabilities.filter((c) => c !== capability)
      : [...holder.capabilities, capability];
    setSaving(holder.user_id);
    try {
      await apiClient.put(`/administration/capabilities/${holder.user_id}`, {
        capabilities: next,
      });
      await queryClient.invalidateQueries({ queryKey: ["administration"] });
      showSuccess("مجوزها به‌روز شد");
    } catch (err) {
      showError(extractErrorMessage(err));
    } finally {
      setSaving(null);
    }
  }

  if (error != null)
    return (
      <Card title="مجوزهای اداری">
        <p className="text-sm text-red-600">{extractErrorMessage(error)}</p>
      </Card>
    );

  return (
    <Card title="مجوزهای اداری">
      <p className="mb-4 text-sm text-gray-500">
        این مجوزها مستقل از نقش‌اند. نقش می‌گوید کجای زنجیرهٔ ارزیابی هستید؛ مجوز
        می‌گوید چه کار اداری‌ای می‌توانید بکنید. حساب «پشتیبانی فنی» فقط این‌ها را
        دارد و به هیچ پروندهٔ ارزیابی دسترسی ندارد.
      </p>

      {isPending ? (
        <TableSkeleton rows={4} />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 text-xs text-gray-500">
                <th className="px-3 py-2 text-right font-semibold">کاربر</th>
                {CAPABILITY_ORDER.map((capability) => (
                  <th
                    key={capability}
                    className="px-2 py-2 text-center font-semibold"
                    title={CAPABILITY_INFO[capability].scope}
                  >
                    {CAPABILITY_INFO[capability].label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {holders.map((holder) => (
                <tr
                  key={holder.user_id}
                  className={`border-b border-gray-50 last:border-0 ${
                    holder.is_active ? "" : "opacity-50"
                  }`}
                >
                  <td className="px-3 py-2.5">
                    <span className="block font-medium text-gray-800">{holder.username}</span>
                    <span className="text-[11px] text-gray-400">
                      {ROLE_LABELS[holder.role] ?? holder.role}
                      {!holder.is_active && " · غیرفعال"}
                    </span>
                  </td>
                  {CAPABILITY_ORDER.map((capability) => (
                    <td key={capability} className="px-2 py-2.5 text-center">
                      <input
                        type="checkbox"
                        checked={holder.capabilities.includes(capability)}
                        disabled={saving === holder.user_id}
                        onChange={() => toggle(holder, capability)}
                        aria-label={`${CAPABILITY_INFO[capability].label} برای ${holder.username}`}
                        className="h-4 w-4 accent-pulse-600 disabled:opacity-40"
                      />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {holders.length === 0 && <EmptyState>کاربری برای نمایش نیست.</EmptyState>}
        </div>
      )}
    </Card>
  );
}

function ModulesCard() {
  const { showSuccess, showError } = useToast();
  const confirm = useConfirm();
  const queryClient = useQueryClient();
  const [saving, setSaving] = useState<string | null>(null);

  const { data: modules = [], isPending } = useQuery({
    queryKey: ["administration", "modules"],
    queryFn: async () => (await apiClient.get<ModuleState[]>("/administration/modules")).data,
  });

  async function toggle(module: ModuleState) {
    if (module.enabled) {
      const ok = await confirm({
        title: `خاموش کردن «${module.label}»؟`,
        description:
          "هیچ داده‌ای حذف نمی‌شود — این بخش فقط از منو برداشته می‌شود و ثبت تازه در آن ممکن نخواهد بود. با روشن‌کردن دوباره، همه‌چیز برمی‌گردد.",
        confirmLabel: "خاموش کن",
      });
      if (!ok) return;
    }
    setSaving(module.key);
    try {
      await apiClient.put(`/administration/modules/${module.key}`, {
        enabled: !module.enabled,
      });
      await queryClient.invalidateQueries({ queryKey: ["administration"] });
      showSuccess(module.enabled ? `«${module.label}» خاموش شد` : `«${module.label}» روشن شد`);
    } catch (err) {
      showError(extractErrorMessage(err));
    } finally {
      setSaving(null);
    }
  }

  return (
    <Card title="بخش‌های سامانه">
      <p className="mb-4 text-sm text-gray-500">
        خاموش‌کردن یک بخش هیچ داده‌ای را پاک نمی‌کند؛ فقط از منو برداشته می‌شود و
        ثبت تازه در آن بسته می‌شود.
      </p>
      {isPending ? (
        <TableSkeleton rows={4} />
      ) : (
        <ul className="space-y-2">
          {modules.map((module) => (
            <li
              key={module.key}
              className="flex flex-wrap items-start justify-between gap-3 rounded-xl border border-gray-100 px-4 py-3"
            >
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-gray-800">{module.label}</p>
                <p className="mt-0.5 text-xs leading-relaxed text-gray-500">
                  {module.description}
                </p>
              </div>
              <label className="flex shrink-0 items-center gap-2 text-xs">
                <input
                  type="checkbox"
                  checked={module.enabled}
                  disabled={saving === module.key}
                  onChange={() => toggle(module)}
                  aria-label={`فعال بودن ${module.label}`}
                  className="h-5 w-5 accent-pulse-600 disabled:opacity-40"
                />
                <span className={module.enabled ? "text-green-700" : "text-gray-400"}>
                  {module.enabled ? "فعال" : "خاموش"}
                </span>
              </label>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
