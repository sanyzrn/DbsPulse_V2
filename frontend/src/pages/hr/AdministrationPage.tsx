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
import { Button } from "../../ui/Button";
import { Card, EmptyState, PageHeader, TableSkeleton } from "../../ui/Card";
import { ROLE_LABELS, type UserRole } from "../../types";

interface CapabilityHolder {
  user_id: number;
  username: string;
  display_name: string;
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
  manage_users: { label: "حساب‌های کاربری", scope: "ساخت، ویرایش، حذف و غیرفعال‌کردن حساب" },
  manage_personnel: { label: "پرسنل و زنجیرهٔ ارزیابی", scope: "ثبت و ویرایش پروندهٔ پرسنلی و تعیین ارزیاب‌های هر فرد" },
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

const inputClass =
  "w-full rounded-xl border border-gray-200 bg-gray-100 px-3 py-2 text-sm text-gray-900 outline-none transition-colors duration-150 focus:border-gray-900 focus:bg-white";

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
      {can("manage_integrations") && <IntegrationsCard />}
      {can("manage_modules") && <ModulesCard />}
      {!can("manage_capabilities") && !can("manage_modules") && !can("manage_integrations") && (
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
            حساب اختصاصی مدیریت از قبل ساخته شده است. برای کامل‌کردن تفکیک، در
            کارت‌های پایین مجوز «دادن مجوز» و «شاخص‌ها و طرح نمره‌دهی» را از
            حساب‌های بالا بردارید.
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
      ) : holders.length === 0 ? (
        <EmptyState>کاربری برای نمایش نیست.</EmptyState>
      ) : (
        /* یک کارت به‌ازای هر حساب، به‌جای جدولِ تیک.
           جدول ماتریسی برای *مقایسه* خوب است؛ کاری که این‌جا انجام می‌شود
           مقایسه نیست، «به این یک نفر چه اختیاری بدهم» است. در ماتریس، هر تیک
           یک مربع بی‌نام بود که معنایش فقط از سرستونِ دو صفحه بالاتر می‌آمد و
           روی موبایل اصلاً دیده نمی‌شد. */
        <ul className="space-y-3">
          {holders.map((holder) => (
            <li
              key={holder.user_id}
              className={`rounded-2xl border border-gray-100 p-4 transition-opacity ${
                holder.is_active ? "" : "opacity-60"
              }`}
            >
              <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
                <div>
                  <span className="font-bold text-gray-800">
                    {holder.display_name || holder.username}
                  </span>
                  {holder.display_name && holder.display_name !== holder.username && (
                    <span className="mr-2 text-xs text-gray-400">{holder.username}</span>
                  )}
                </div>
                <span className="rounded-full bg-gray-100 px-2.5 py-0.5 text-[11px] font-medium text-gray-600">
                  {ROLE_LABELS[holder.role] ?? holder.role}
                  {!holder.is_active && " · غیرفعال"}
                </span>
              </div>
              <div className="flex flex-wrap gap-2">
                {CAPABILITY_ORDER.map((capability) => {
                  const granted = holder.capabilities.includes(capability);
                  return (
                    <button
                      key={capability}
                      type="button"
                      role="switch"
                      aria-checked={granted}
                      disabled={saving === holder.user_id}
                      onClick={() => toggle(holder, capability)}
                      title={CAPABILITY_INFO[capability].scope}
                      aria-label={`${CAPABILITY_INFO[capability].label} برای ${holder.username}`}
                      className={`inline-flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
                        granted
                          ? "border-pulse-200 bg-pulse-50 text-pulse-700"
                          : "border-gray-200 bg-gray-50 text-gray-500 hover:bg-gray-100"
                      }`}
                    >
                      <span
                        aria-hidden
                        className={`h-1.5 w-1.5 rounded-full ${
                          granted ? "bg-pulse-500" : "bg-gray-300"
                        }`}
                      />
                      {CAPABILITY_INFO[capability].label}
                    </button>
                  );
                })}
              </div>
            </li>
          ))}
        </ul>
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
              {/* سوییچ به‌جای تیک: چیزی که این‌جا عوض می‌شود یک *حالت* است
                  (این بخش روشن است یا خاموش)، نه یک انتخاب از فهرست. تیک برای
                  «کدام‌ها را می‌خواهی» است و سوییچ برای «این یکی روشن باشد؟» —
                  و شکلِ کنترل باید همان را بگوید. */}
              <button
                type="button"
                role="switch"
                aria-checked={module.enabled}
                disabled={saving === module.key}
                onClick={() => toggle(module)}
                aria-label={`فعال بودن ${module.label}`}
                className={`relative flex h-6 w-11 shrink-0 items-center rounded-full transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
                  module.enabled ? "bg-pulse-600" : "bg-gray-300"
                }`}
              >
                <span
                  aria-hidden
                  className={`absolute h-5 w-5 rounded-full bg-white shadow-sm transition-all ${
                    module.enabled ? "right-0.5" : "right-[22px]"
                  }`}
                />
              </button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

interface IntegrationField {
  key: string;
  label: string;
  kind: "text" | "number" | "bool";
  help: string;
  value: string | number | boolean;
}

interface IntegrationSettings {
  fields: IntegrationField[];
  secrets: { key: string; label: string; configured: boolean }[];
  active_channels: string[];
}

const CHANNEL_LABELS: Record<string, string> = { email: "ایمیل", sms: "پیامک" };

/** تنظیمات ارسال بیرونی.
 *
 * موتور ارسال از قبل کامل بود — صف، تلاش مجدد، جداکردن خطای دائمی از گذرا —
 * ولی هیچ جایی برای وارد کردن تنظیماتش نبود جز فایل `.env` روی سرور. یعنی
 * عوض‌کردن قالب پیامک به دسترسی SSH نیاز داشت.
 *
 * رمز و کلید API عمداً این‌جا قابل ویرایش نیستند و فقط وضعیتشان دیده می‌شود:
 * چیزی که در دیتابیس بنشیند در هر بک‌آپی هم می‌نشیند.
 */
function IntegrationsCard() {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<Record<string, string | number | boolean> | null>(null);
  const [saving, setSaving] = useState(false);
  const [testTo, setTestTo] = useState("");
  const [testing, setTesting] = useState<string | null>(null);

  const { data, isPending } = useQuery({
    queryKey: ["administration", "integrations"],
    queryFn: async () =>
      (await apiClient.get<IntegrationSettings>("/administration/integrations")).data,
  });

  const values = draft ?? Object.fromEntries((data?.fields ?? []).map((f) => [f.key, f.value]));

  async function save() {
    setSaving(true);
    try {
      await apiClient.put("/administration/integrations", { values });
      await queryClient.invalidateQueries({ queryKey: ["administration", "integrations"] });
      setDraft(null);
      showSuccess("تنظیمات ذخیره شد");
    } catch (err) {
      showError(extractErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function sendTest(channel: string) {
    if (!testTo.trim()) {
      showError("نشانی یا شمارهٔ گیرندهٔ آزمایشی را وارد کنید");
      return;
    }
    setTesting(channel);
    try {
      const { data: result } = await apiClient.post<{ ok: boolean; detail: string }>(
        "/administration/integrations/test",
        { channel, recipient: testTo.trim() }
      );
      if (result.ok) showSuccess(result.detail);
      else showError(result.detail);
    } catch (err) {
      showError(extractErrorMessage(err));
    } finally {
      setTesting(null);
    }
  }

  if (isPending || !data) return <Card title="ایمیل و پیامک"><TableSkeleton rows={3} /></Card>;

  return (
    <Card title="ایمیل و پیامک">
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {["email", "sms"].map((channel) => {
          const on = data.active_channels.includes(channel);
          return (
            <span
              key={channel}
              className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${
                on ? "bg-green-50 text-green-700" : "bg-gray-100 text-gray-500"
              }`}
            >
              <span aria-hidden className={`h-1.5 w-1.5 rounded-full ${on ? "bg-green-500" : "bg-gray-400"}`} />
              {CHANNEL_LABELS[channel]} · {on ? "فعال" : "تنظیم نشده"}
            </span>
          );
        })}
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {data.fields.map((field) => (
          <label key={field.key} className="flex flex-col gap-1 text-xs font-medium text-gray-600">
            {field.label}
            {field.kind === "bool" ? (
              <button
                type="button"
                role="switch"
                aria-checked={Boolean(values[field.key])}
                onClick={() => setDraft({ ...values, [field.key]: !values[field.key] })}
                className={`self-start rounded-xl border px-3 py-1.5 text-xs font-medium transition-colors ${
                  values[field.key]
                    ? "border-pulse-200 bg-pulse-50 text-pulse-700"
                    : "border-gray-200 bg-gray-50 text-gray-500"
                }`}
              >
                {values[field.key] ? "روشن" : "خاموش"}
              </button>
            ) : (
              <input
                type={field.kind === "number" ? "number" : "text"}
                className={inputClass}
                value={String(values[field.key] ?? "")}
                onChange={(e) =>
                  setDraft({
                    ...values,
                    [field.key]:
                      field.kind === "number" ? Number(e.target.value) : e.target.value,
                  })
                }
              />
            )}
            {field.help && <span className="font-normal text-[11px] text-gray-400">{field.help}</span>}
          </label>
        ))}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-gray-100 pt-4">
        <Button onClick={save} disabled={saving || draft === null}>
          {saving ? "در حال ذخیره…" : "ذخیرهٔ تنظیمات"}
        </Button>
        {draft !== null && (
          <button
            type="button"
            onClick={() => setDraft(null)}
            className="text-xs font-medium text-gray-500 hover:text-gray-700"
          >
            بازگرداندن تغییرات
          </button>
        )}
      </div>

      {/* رمزها این‌جا فقط *وضعیت* دارند، نه مقدار. */}
      <div className="mt-5 rounded-2xl bg-gray-50 p-4">
        <p className="text-xs font-bold text-gray-700">مقادیر محرمانه</p>
        <p className="mt-1 text-[11px] leading-relaxed text-gray-500">
          این‌ها فقط از فایل <code>backend/.env</code> خوانده می‌شوند و از این‌جا قابل
          ویرایش نیستند. چیزی که در دیتابیس بنشیند، در هر بک‌آپی هم می‌نشیند — و بک‌آپ
          دیتابیس معمولاً جاهایی می‌رود که آن فایل نمی‌رود.
        </p>
        <ul className="mt-3 flex flex-wrap gap-2">
          {data.secrets.map((secret) => (
            <li
              key={secret.key}
              className={`rounded-lg px-2.5 py-1 text-[11px] ${
                secret.configured ? "bg-green-50 text-green-700" : "bg-gray-100 text-gray-500"
              }`}
            >
              {secret.label} · {secret.configured ? "تنظیم شده" : "تنظیم نشده"}
            </li>
          ))}
        </ul>
      </div>

      <div className="mt-4 flex flex-wrap items-end gap-2 border-t border-gray-100 pt-4">
        <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
          گیرندهٔ آزمایشی
          <input
            className={`${inputClass} sm:w-64`}
            placeholder="نشانی ایمیل یا شمارهٔ موبایل"
            value={testTo}
            onChange={(e) => setTestTo(e.target.value)}
          />
        </label>
        {["email", "sms"].map((channel) => (
          <Button
            key={channel}
            variant="secondary"
            disabled={testing !== null}
            onClick={() => sendTest(channel)}
          >
            {testing === channel ? "در حال ارسال…" : `ارسال آزمایشی ${CHANNEL_LABELS[channel]}`}
          </Button>
        ))}
      </div>
      <p className="mt-2 text-[11px] text-gray-400">
        پیام آزمایشی مستقیم فرستاده می‌شود و از صف رد نمی‌شود — تا اولین آزمونِ
        پیکربندی روی پیامِ کسی انجام نشود.
      </p>
    </Card>
  );
}
