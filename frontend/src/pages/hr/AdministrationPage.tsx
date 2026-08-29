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
import { useAuth } from "../../auth/AuthContext";
import { usePermissions, type Capability } from "../../auth/PermissionsContext";
import { useConfirm } from "../../components/ConfirmDialog";
import { useToast } from "../../components/Toast";
import { Button } from "../../ui/Button";
import { Card, EmptyState, FilterSelect, PageHeader, TableSkeleton } from "../../ui/Card";
import { useOrgUnitCatalogue, useSites } from "../../api/queries";
import { PasswordInput } from "../../ui/PasswordInput";
import {
  ROLE_LABELS,
  type AiSettings,
  type AiUserAccess,
  type OrgUnitCatalogueItem,
  type UserRole,
} from "../../types";

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
  manage_ai: { label: "دستیار هوشمند", scope: "کلید سرویس، نحوهٔ پاسخگویی، و اینکه چه کسی دستیار دارد" },
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
  const { can, loading } = usePermissions();
  const { user } = useAuth();
  // همان شرطی که سرور می‌گذارد (`require_role_or_capability(hr, manage_personnel)`).
  // اگر این‌جا فقط مجوز را می‌دیدیم، کاربر منابع انسانی کارتی را نمی‌دید که API
  // به او اجازه‌اش را می‌دهد.
  const canOrgUnits = user?.role === "hr" || can("manage_personnel");
  const tabs = [
    ...(canOrgUnits ? [{ id: "org-units", label: "واحدهای سازمانی", content: <OrgUnitsCard /> }] : []),
    ...(can("manage_capabilities")
      ? [
          { id: "separation", label: "تفکیک وظایف", content: <SeparationCard /> },
          { id: "capabilities", label: "مجوزهای اداری", content: <CapabilitiesCard /> },
        ]
      : []),
    ...(can("manage_integrations")
      ? [{ id: "integrations", label: "ایمیل و پیامک", content: <IntegrationsCard /> }]
      : []),
    ...(can("manage_ai")
      ? [{ id: "ai", label: "دستیار هوشمند", content: <AiCard /> }]
      : []),
    ...(can("manage_modules")
      ? [
          { id: "policy", label: "قاعده‌های سازمانی", content: <PolicyCard /> },
          { id: "modules", label: "بخش‌های سامانه", content: <ModulesCard /> },
        ]
      : []),
  ];
  const [activeTab, setActiveTab] = useState<string | null>(null);
  const selectedTab = tabs.find((tab) => tab.id === activeTab) ?? tabs[0];

  return (
    <div className="space-y-5">
      <PageHeader
        title="مدیریت سامانه"
        subtitle="چه کسی می‌تواند خودِ سامانه را عوض کند، و کدام بخش‌ها فعال‌اند"
      />
      {!loading && tabs.length > 0 && (
        <>
          <div className="overflow-x-auto">
            <div
              role="tablist"
              aria-label="بخش‌های مدیریت سامانه"
              className="inline-flex min-w-max gap-1 rounded-2xl border border-gray-200 bg-white p-1 shadow-sm"
            >
              {tabs.map((tab) => {
                const isActive = tab.id === selectedTab?.id;
                return (
                  <button
                    key={tab.id}
                    type="button"
                    role="tab"
                    aria-selected={isActive}
                    onClick={() => setActiveTab(tab.id)}
                    className={`rounded-xl px-4 py-2 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-pulse-500 focus-visible:ring-offset-1 ${
                      isActive
                        ? "bg-pulse-600 text-white shadow-sm"
                        : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
                    }`}
                  >
                    {tab.label}
                  </button>
                );
              })}
            </div>
          </div>
          <div role="tabpanel" aria-label={selectedTab?.label}>
            {selectedTab?.content}
          </div>
        </>
      )}
      {/* `loading` عمداً در شرط هست.
          `can()` تا وقتی مجوزها از سرور نیامده `false` برمی‌گرداند، پس بدون این
          شرط صفحه در همان یک لحظه با اطمینان می‌گفت «مجوز ندارید» — به مدیری که
          همهٔ مجوزها را دارد. همان سه حالتی که در کد یکی به‌نظر می‌رسند و برای
          کاربر کاملاً فرق دارند: «هنوز نمی‌دانم»، «نداری»، «داری». */}
      {loading && <Card><TableSkeleton rows={3} /></Card>}
      {!loading &&
        !can("manage_capabilities") &&
        !can("manage_modules") &&
        !can("manage_integrations") &&
        !can("manage_ai") &&
        !canOrgUnits && (
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
      <Card title="تفکیک وظایف">
        <div className="rounded-xl border border-green-200 bg-green-50/50 p-4">
          <p className="text-sm font-bold text-green-800">تفکیک وظایف برقرار است</p>
          <p className="mt-1 text-xs leading-relaxed text-green-900/70">
            هیچ حسابی هم‌زمان در زنجیرهٔ ارزیابی نیست و قواعد را عوض نمی‌کند. اگر روزی
            نتیجه‌ای زیر سؤال برود، می‌شود نشان داد کسی که تصمیم گرفته همان کسی نبوده
            که قاعده را نوشته.
          </p>
        </div>
      </Card>
    );
  }

  return (
    <Card title="تفکیک وظایف">
      <div className="rounded-xl border border-amber-200 bg-amber-50/50 p-4">
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
    </Card>
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
  minimum?: number | null;
  maximum?: number | null;
}

interface IntegrationSettings {
  fields: IntegrationField[];
  secrets: { key: string; label: string; configured: boolean }[];
  active_channels: string[];
}

const CHANNEL_LABELS: Record<string, string> = { email: "ایمیل", sms: "پیامک" };

/** قاعده‌های سازمانی.
 *
 *  «مهلت اعتراض هفت روز است یا ده روز» و «از چند نفر به بالا میانگین را نشان
 *  بده» تصمیم‌های سازمان‌اند، نه تصمیم‌های استقرار — ولی تا امروز فقط در `.env`
 *  بودند، یعنی عوض‌کردنشان به دسترسی SSH نیاز داشت.
 *
 *  کف و سقفِ هر عدد از خودِ سرور می‌آید و روی همان ورودی می‌نشیند: فرم همان
 *  قاعده‌ای را نشان می‌دهد که سرور اعمال می‌کند، به‌جای اینکه کاربر با
 *  ذخیره‌کردن کشفش کند.
 */
function PolicyCard() {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<Record<string, string | number | boolean> | null>(null);
  const [saving, setSaving] = useState(false);

  const { data, isPending } = useQuery({
    queryKey: ["administration", "policy"],
    queryFn: async () =>
      (await apiClient.get<{ fields: IntegrationField[] }>("/administration/policy")).data,
  });

  const values = draft ?? Object.fromEntries((data?.fields ?? []).map((f) => [f.key, f.value]));

  async function save() {
    setSaving(true);
    try {
      await apiClient.put("/administration/policy", { values });
      await queryClient.invalidateQueries({ queryKey: ["administration", "policy"] });
      setDraft(null);
      showSuccess("قاعده‌ها ذخیره شد");
    } catch (err) {
      showError(extractErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  if (isPending || !data) {
    return (
      <Card title="قاعده‌های سازمانی">
        <TableSkeleton rows={3} />
      </Card>
    );
  }

  return (
    <Card title="قاعده‌های سازمانی">
      <p className="mb-4 text-sm text-gray-500">
        مهلت‌ها و آستانه‌هایی که رفتار سامانه را تعیین می‌کنند. تغییرشان بی‌درنگ اثر می‌کند و در
        گزارش رویدادها ثبت می‌شود.
      </p>

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
                className={`relative h-8 w-14 rounded-full transition-colors ${
                  values[field.key] ? "bg-pulse-600" : "bg-gray-200"
                }`}
              >
                <span
                  className={`absolute top-1 h-6 w-6 rounded-full bg-white shadow-sm transition-all ${
                    values[field.key] ? "right-7" : "right-1"
                  }`}
                />
                <span className="sr-only">{values[field.key] ? "روشن" : "خاموش"}</span>
              </button>
            ) : (
              <input
                type="number"
                min={field.minimum ?? undefined}
                max={field.maximum ?? undefined}
                className={inputClass}
                value={String(values[field.key] ?? "")}
                onChange={(e) => setDraft({ ...values, [field.key]: Number(e.target.value) })}
              />
            )}
            {field.help && (
              <span className="text-[11px] font-normal text-gray-400">{field.help}</span>
            )}
          </label>
        ))}
      </div>

      <div className="mt-4 border-t border-gray-100 pt-4">
        <Button onClick={save} disabled={saving || draft === null}>
          {saving ? "در حال ذخیره…" : "ذخیرهٔ قاعده‌ها"}
        </Button>
      </div>
    </Card>
  );
}

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

  if (isPending || !data)
    return (
      <Card title="ایمیل و پیامک">
        <TableSkeleton rows={3} />
      </Card>
    );

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

/** کاتالوگ واحدهای سازمانی.
 *
 *  تا امروز فهرست واحدها *استخراج* می‌شد: هر رشته‌ای که در پروندهٔ کسی نوشته شده
 *  بود یک واحد بود. یعنی یک غلط تایپی بی‌سروصدا واحد تازه می‌ساخت، و واحدی که
 *  هنوز کسی در آن نبود اصلاً وجود نداشت — پس برای ثبتِ اولین نفرِ یک واحد تازه
 *  باید نامش را از حفظ و بی‌غلط تایپ می‌کردی.
 *
 *  حذف عمداً فقط برای واحدِ خالی است. واحدی که پرسنل دارد «غیرفعال» می‌شود: از
 *  فرم‌های تازه برداشته می‌شود و سابقهٔ گزارش‌ها دست‌نخورده می‌ماند.
 */
function OrgUnitsCard() {
  const { showSuccess, showError } = useToast();
  const confirm = useConfirm();
  const queryClient = useQueryClient();
  const { data: units = [], isPending } = useOrgUnitCatalogue();
  // فهرست محل‌ها از سرور می‌آید، نه از یک ثابت در این فایل: سرور آن را از
  // «سه محلِ شناخته‌شده + هر محلی که در داده هست» می‌سازد، و دو نسخه از این
  // فهرست یعنی روزی که یکی عوض شود و دیگری نه.
  const { data: sites = [] } = useSites(true);
  const [busy, setBusy] = useState<number | "new" | null>(null);
  // `null` یعنی «کاربر هنوز انتخاب نکرده»؛ تا آن وقت اولین محل پیشنهاد می‌شود.
  const [draft, setDraft] = useState<{ site: string | null; name: string }>({ site: null, name: "" });
  const [editing, setEditing] = useState<OrgUnitCatalogueItem | null>(null);
  const draftSite = draft.site ?? sites[0] ?? "";

  async function refresh() {
    // هم کاتالوگ و هم فهرست‌های استخراج‌شده‌ای که فیلترهای صفحات دیگر از آن
    // می‌خوانند: تغییرِ نام واحد پرسنل را هم جابه‌جا می‌کند.
    await queryClient.invalidateQueries({ queryKey: ["org-units"], refetchType: "all" });
    await queryClient.invalidateQueries({ queryKey: ["personnel"], refetchType: "all" });
  }

  async function run(key: number | "new", action: () => Promise<void>, done: string) {
    setBusy(key);
    try {
      await action();
      await refresh();
      showSuccess(done);
    } catch (err) {
      showError(extractErrorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  function create(e: React.FormEvent) {
    e.preventDefault();
    const name = draft.name.trim();
    if (!name) return;
    void run(
      "new",
      async () => {
        await apiClient.post("/org-units", { site: draftSite || null, name });
        setDraft({ site: draftSite, name: "" });
      },
      `واحد «${name}» افزوده شد`,
    );
  }

  function save(unit: OrgUnitCatalogueItem, patch: Partial<OrgUnitCatalogueItem>, done: string) {
    void run(unit.id, async () => {
      await apiClient.patch(`/org-units/${unit.id}`, patch);
      setEditing(null);
    }, done);
  }

  async function remove(unit: OrgUnitCatalogueItem) {
    const ok = await confirm({
      title: `حذف «${unit.full_name}»؟`,
      description: "این واحد از فهرستِ پیشنهادیِ فرم‌ها برداشته می‌شود.",
      confirmLabel: "حذف",
      danger: true,
    });
    if (!ok) return;
    void run(unit.id, () => apiClient.delete(`/org-units/${unit.id}`).then(), "واحد حذف شد");
  }

  return (
    <Card
      title="واحدهای سازمانی"
      actions={
        <span className="text-xs text-gray-400">
          {units.length.toLocaleString("fa-IR")} واحد تعریف‌شده
        </span>
      }
    >
      <p className="mb-4 text-sm text-gray-500">
        همین فهرست است که در فرم ثبت پرسنل و در فیلترهای گزارش‌ها پیشنهاد می‌شود. تغییر نام
        یک واحد، پرسنلِ همان واحد را هم با خودش می‌برد.
      </p>

      <form onSubmit={create} className="mb-4 flex flex-wrap items-end gap-2">
        <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
          محل
          <FilterSelect
            value={draftSite}
            onChange={(site) => setDraft({ ...draft, site })}
            aria-label="محل واحد تازه"
          >
            {sites.map((site) => (
              <option key={site} value={site}>
                {site}
              </option>
            ))}
            <option value="">بدون محل</option>
          </FilterSelect>
        </label>
        <label className="flex flex-1 flex-col gap-1 text-xs font-medium text-gray-600">
          نام واحد
          <input
            required
            value={draft.name}
            onChange={(e) => setDraft({ ...draft, name: e.target.value })}
            placeholder="مثلاً کنترل کیفیت"
            className="w-full rounded-xl border border-gray-200 bg-gray-100 px-3 py-2 text-sm text-gray-900 outline-none transition-colors duration-150 focus:border-gray-900 focus:bg-white"
          />
        </label>
        <Button type="submit" loading={busy === "new"}>
          افزودن واحد
        </Button>
      </form>

      {isPending ? (
        <TableSkeleton rows={4} />
      ) : units.length === 0 ? (
        <EmptyState>هنوز واحدی تعریف نشده است.</EmptyState>
      ) : (
        <ul className="space-y-1.5">
          {units.map((unit) => (
            <li
              key={unit.id}
              className="flex flex-wrap items-center gap-2 rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm"
            >
              {editing?.id === unit.id ? (
                <form
                  className="flex flex-1 flex-wrap items-center gap-2"
                  onSubmit={(e) => {
                    e.preventDefault();
                    save(unit, { site: editing.site || null, name: editing.name }, "واحد به‌روز شد");
                  }}
                >
                  <FilterSelect
                    value={editing.site ?? ""}
                    onChange={(site) => setEditing({ ...editing, site: site || null })}
                    aria-label="محل"
                  >
                    {sites.map((site) => (
                      <option key={site} value={site}>
                        {site}
                      </option>
                    ))}
                    <option value="">بدون محل</option>
                  </FilterSelect>
                  <input
                    required
                    autoFocus
                    value={editing.name}
                    onChange={(e) => setEditing({ ...editing, name: e.target.value })}
                    className="min-w-0 flex-1 rounded-xl border border-gray-200 bg-gray-100 px-3 py-1.5 text-sm text-gray-900 outline-none focus:border-gray-900 focus:bg-white"
                  />
                  <Button type="submit" loading={busy === unit.id}>
                    ذخیره
                  </Button>
                  <Button variant="secondary" onClick={() => setEditing(null)}>
                    انصراف
                  </Button>
                </form>
              ) : (
                <>
                  <span className="min-w-0 flex-1 truncate font-medium text-gray-800">
                    {unit.full_name}
                  </span>
                  <span className="text-xs text-gray-400">
                    {unit.personnel_count > 0
                      ? `${unit.personnel_count.toLocaleString("fa-IR")} نفر`
                      : "بدون پرسنل"}
                  </span>
                  {!unit.is_active && (
                    <span className="rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-800">
                      غیرفعال
                    </span>
                  )}
                  <button
                    type="button"
                    onClick={() => setEditing(unit)}
                    className="rounded-lg px-2 py-1 text-xs font-medium text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-900"
                  >
                    ویرایش
                  </button>
                  <button
                    type="button"
                    disabled={busy === unit.id}
                    onClick={() =>
                      save(
                        unit,
                        { is_active: !unit.is_active },
                        unit.is_active ? "واحد غیرفعال شد" : "واحد فعال شد",
                      )
                    }
                    className="rounded-lg px-2 py-1 text-xs font-medium text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-900 disabled:opacity-40"
                  >
                    {unit.is_active ? "غیرفعال" : "فعال"}
                  </button>
                  {/* حذف فقط وقتی نشان داده می‌شود که واقعاً ممکن است؛ برای واحدِ
                      پرجمعیت سرور ۴۰۹ می‌دهد و دکمه فقط یک بن‌بست بود. */}
                  {unit.personnel_count === 0 && (
                    <button
                      type="button"
                      disabled={busy === unit.id}
                      onClick={() => void remove(unit)}
                      className="rounded-lg px-2 py-1 text-xs font-medium text-red-600 transition-colors hover:bg-red-50 disabled:opacity-40"
                    >
                      حذف
                    </button>
                  )}
                </>
              )}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

/** دستیار هوشمند — تنظیمات سرویس، نحوهٔ پاسخگویی، و اینکه چه کسی دستیار دارد.
 *
 *  سه چیز عمداً از هم جدا نگه داشته شده‌اند، چون سه تصمیمِ متفاوت‌اند:
 *  «به کدام سرویس وصل شویم» (فنی)، «چطور جواب بدهد» (سازمانی)، و «چه کسی
 *  استفاده کند» (دسترسی). فقط مدیرِ دارای مجوز `manage_ai` این کارت را
 *  می‌بیند؛ کاربرِ دستیار — مثلاً معاونت — فقط پنجرهٔ گفت‌وگو را دارد.
 */
function AiCard() {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<Partial<AiSettings> & { api_key?: string }>({});
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; detail: string } | null>(null);

  const { data, isPending } = useQuery({
    queryKey: ["ai", "settings"],
    queryFn: async () => (await apiClient.get<AiSettings>("/ai/settings")).data,
  });
  const { data: access = [] } = useQuery({
    queryKey: ["ai", "access"],
    queryFn: async () => (await apiClient.get<AiUserAccess[]>("/ai/access")).data,
  });

  const value = { ...(data ?? {}), ...draft } as AiSettings & { api_key?: string };
  const dirty = Object.keys(draft).length > 0;

  function set<K extends keyof typeof value>(key: K, next: (typeof value)[K]) {
    setDraft((prev) => ({ ...prev, [key]: next }));
  }

  async function save() {
    setSaving(true);
    try {
      await apiClient.put("/ai/settings", draft);
      // `["ai"]` پیشوند است و `["ai", "status"]` را هم می‌گیرد.
      await queryClient.invalidateQueries({ queryKey: ["ai"] });
      setDraft({});
      showSuccess("تنظیمات دستیار ذخیره شد");
    } catch (err) {
      showError(extractErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function test() {
    setTesting(true);
    setTestResult(null);
    try {
      const { data: result } = await apiClient.post<{ ok: boolean; detail: string }>(
        "/ai/settings/test",
        { base_url: value.base_url, model: value.model, api_key: draft.api_key },
      );
      setTestResult(result);
    } catch (err) {
      setTestResult({ ok: false, detail: extractErrorMessage(err) });
    } finally {
      setTesting(false);
    }
  }

  async function setAccess(row: AiUserAccess, patch: Record<string, unknown>) {
    try {
      await apiClient.put(`/ai/access/${row.user_id}`, patch);
      // کلِ شاخهٔ `ai` و نه فقط `access`: اگر مدیر دستیار را برای *خودش* روشن
      // کند، وضعیتِ دکمهٔ گفت‌وگو (`["ai", "status"]`) هم همین حالا عوض شده.
      await queryClient.invalidateQueries({ queryKey: ["ai"] });
    } catch (err) {
      showError(extractErrorMessage(err));
    }
  }

  if (isPending || !data) {
    return (
      <Card title="دستیار هوشمند">
        <TableSkeleton rows={3} />
      </Card>
    );
  }

  return (
    <Card title="دستیار هوشمند">
      <p className="mb-4 text-sm text-gray-500">
        دستیار داده‌های سامانه را <b>می‌خواند</b> و برای تغییرشان <b>پیشنهاد</b> می‌دهد؛ هیچ
        تغییری بدون تأیید کاربر اجرا نمی‌شود. هر کنش هم همان محدودیتی را دارد که خودِ آن کاربر
        در رابط دارد.
      </p>

      <label className="mb-4 flex items-center gap-2 text-sm font-medium text-gray-700">
        <input
          type="checkbox"
          checked={value.enabled}
          onChange={(e) => set("enabled", e.target.checked)}
          className="h-4 w-4 cursor-pointer rounded border-gray-300 text-pulse-500"
        />
        دستیار در این سامانه فعال باشد
      </label>

      {/* انتخاب سرویس: یک کلیک، آدرس و یک مدلِ پیش‌فرضِ سالم.
          نیمی از مشکلات راه‌اندازی یک `/v1` جامانده در آدرس بود. */}
      <div className="mb-4">
        <p className="mb-2 text-xs font-medium text-gray-600">سرویس</p>
        <div className="flex flex-wrap gap-2">
          {(data.providers ?? []).map((option) => {
            const active = value.provider === option.id;
            return (
              <button
                key={option.id}
                type="button"
                onClick={() =>
                  setDraft((prev) => ({
                    ...prev,
                    provider: option.id,
                    // «سفارشی» چیزی را پاک نمی‌کند: کسی که رویش می‌زند معمولاً
                    // همان آدرسی را می‌خواهد که نوشته بود.
                    ...(option.base_url ? { base_url: option.base_url } : {}),
                    ...(option.default_model ? { model: option.default_model } : {}),
                  }))
                }
                className={`rounded-xl border px-3 py-2 text-right text-xs transition-colors ${
                  active
                    ? "border-pulse-200 bg-pulse-50 text-pulse-700"
                    : "border-gray-200 bg-white text-gray-600 hover:bg-gray-50"
                }`}
              >
                <span className="block font-semibold">{option.label}</span>
                {option.default_model && (
                  <span dir="ltr" className="mt-0.5 block text-left text-[11px] text-gray-400">
                    {option.default_model}
                  </span>
                )}
              </button>
            );
          })}
        </div>
        {(data.providers ?? []).find((o) => o.id === value.provider)?.note && (
          <p className="mt-2 text-[11px] text-gray-400">
            {(data.providers ?? []).find((o) => o.id === value.provider)?.note}
          </p>
        )}
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
          آدرس سرویس (سازگار با OpenAI)
          <input
            dir="ltr"
            value={value.base_url}
            onChange={(e) => set("base_url", e.target.value)}
            placeholder="https://api.openai.com/v1"
            className={inputClass}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
          نام مدل
          <input
            dir="ltr"
            value={value.model}
            onChange={(e) => set("model", e.target.value)}
            placeholder="gpt-4o-mini"
            className={inputClass}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-gray-600 sm:col-span-2">
          کلید API پیش‌فرض
          <PasswordInput
            value={draft.api_key ?? ""}
            onChange={(e) => set("api_key", e.target.value)}
            placeholder={
              data.api_key_configured ? `تنظیم شده (${data.api_key_hint})` : "هنوز تنظیم نشده"
            }
            baseClassName={`${inputClass} pl-11`}
          />
          <span className="text-[11px] font-normal text-gray-400">
            رمزنگاری‌شده ذخیره می‌شود و هرگز از سرور برنمی‌گردد. خالی‌گذاشتنش یعنی «دست نزن».
          </span>
        </label>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button variant="secondary" onClick={test} loading={testing}>
          آزمودن اتصال
        </Button>
        {testResult && (
          <span
            className={`text-xs ${testResult.ok ? "text-green-700" : "text-red-600"}`}
            dir="auto"
          >
            {testResult.detail}
          </span>
        )}
      </div>

      <h3 className="mt-6 mb-2 text-sm font-bold text-gray-900">نحوهٔ پاسخگویی</h3>
      <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
        دستورالعمل کلی
        <textarea
          rows={4}
          value={value.instructions}
          onChange={(e) => set("instructions", e.target.value)}
          className={`${inputClass} resize-y leading-relaxed`}
        />
      </label>

      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <label className="flex items-start gap-2 text-xs text-gray-700">
          <input
            type="checkbox"
            checked={value.restrict_to_platform}
            onChange={(e) => set("restrict_to_platform", e.target.checked)}
            className="mt-0.5 h-4 w-4 cursor-pointer rounded border-gray-300 text-pulse-500"
          />
          <span>
            فقط دربارهٔ همین سامانه پاسخ بدهد
            <span className="mt-0.5 block text-[11px] text-gray-400">
              خاموش‌کردنش یعنی به پرسش‌های بی‌ربط هم جواب می‌دهد — و مدل‌های ارزان در آن حوزه
              بدتر از هر جای دیگر جواب می‌دهند.
            </span>
          </span>
        </label>
        <label className="flex items-start gap-2 text-xs text-gray-700">
          <input
            type="checkbox"
            checked={value.allow_write_actions}
            onChange={(e) => set("allow_write_actions", e.target.checked)}
            className="mt-0.5 h-4 w-4 cursor-pointer rounded border-gray-300 text-pulse-500"
          />
          <span>
            اجازهٔ پیشنهادِ تغییر داشته باشد
            <span className="mt-0.5 block text-[11px] text-gray-400">
              حتی وقتی روشن است، اجرای هر تغییر به تأیید کاربر نیاز دارد.
            </span>
          </span>
        </label>
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <NumberField label="ردیف‌های داده در هر پرسش" hint="صفر یعنی هیچ داده‌ای فرستاده نشود" min={0} max={200} value={value.context_record_limit} onChange={(n) => set("context_record_limit", n)} />
        <NumberField label="خلاقیت (۰ تا ۱۰۰)" hint="کمتر = پاسخ‌های محتاط‌تر و یکنواخت‌تر" min={0} max={100} value={value.temperature} onChange={(n) => set("temperature", n)} />
        <NumberField label="حداکثر طول پاسخ (توکن)" min={100} max={32000} value={value.max_tokens} onChange={(n) => set("max_tokens", n)} />
        <NumberField label="مهلت پاسخ (ثانیه)" min={5} max={300} value={value.timeout_seconds} onChange={(n) => set("timeout_seconds", n)} />
        <NumberField label="حداکثر طول پیام کاربر (نویسه)" min={200} max={20000} value={value.max_user_chars} onChange={(n) => set("max_user_chars", n)} />
      </div>

      <div className="mt-4 border-t border-gray-100 pt-4">
        <Button onClick={save} disabled={saving || !dirty}>
          {saving ? "در حال ذخیره…" : "ذخیرهٔ تنظیمات دستیار"}
        </Button>
      </div>

      <h3 className="mt-6 mb-2 text-sm font-bold text-gray-900">چه کسی دستیار دارد</h3>
      <p className="mb-3 text-xs text-gray-500">
        هر حساب می‌تواند کلید و مدلِ خودش را داشته باشد، تا هزینه و سهمیه از هم جدا بماند.
        خالی‌گذاشتنِ کلید یعنی از کلید پیش‌فرضِ بالا استفاده می‌کند.
      </p>
      <ul className="space-y-1.5">
        {access.map((row) => (
          <li key={row.user_id} className="rounded-xl border border-gray-200 bg-white px-3 py-2">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={row.enabled}
                  onChange={(e) => void setAccess(row, { enabled: e.target.checked })}
                  className="h-4 w-4 cursor-pointer rounded border-gray-300 text-pulse-500"
                />
                <span className="font-medium text-gray-800">{row.display_name}</span>
              </label>
              <span dir="ltr" className="text-[11px] text-gray-400">{row.username}</span>
              <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[11px] text-gray-600">
                {ROLE_LABELS[row.role as UserRole] ?? row.role}
              </span>
              <span className="flex-1" />
              {row.enabled && (
                <>
                  <label className="flex items-center gap-1.5 text-[11px] text-gray-500">
                    <input
                      type="checkbox"
                      checked={row.allow_write_actions}
                      onChange={(e) =>
                        void setAccess(row, { allow_write_actions: e.target.checked })
                      }
                      className="h-3.5 w-3.5 cursor-pointer rounded border-gray-300 text-pulse-500"
                    />
                    اجازهٔ تغییر
                  </label>
                  <span className="text-[11px] text-gray-400">
                    {row.api_key_configured ? `کلید اختصاصی ${row.api_key_hint}` : "کلید پیش‌فرض"}
                  </span>
                  <UserKeyEditor row={row} onSave={setAccess} />
                </>
              )}
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function NumberField({
  label,
  hint,
  value,
  onChange,
  min,
  max,
}: {
  label: string;
  hint?: string;
  value: number;
  onChange: (value: number) => void;
  min: number;
  max: number;
}) {
  return (
    <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
      {label}
      <input
        type="number"
        min={min}
        max={max}
        value={String(value ?? "")}
        onChange={(e) => onChange(Number(e.target.value))}
        className={inputClass}
      />
      {hint && <span className="text-[11px] font-normal text-gray-400">{hint}</span>}
    </label>
  );
}

/** ویرایشگرِ کلید و مدلِ یک کاربر. بسته می‌ماند تا ردیف‌ها شلوغ نشوند. */
function UserKeyEditor({
  row,
  onSave,
}: {
  row: AiUserAccess;
  onSave: (row: AiUserAccess, patch: Record<string, unknown>) => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState(row.model);
  const [limit, setLimit] = useState(row.daily_message_limit);

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="rounded-lg px-2 py-1 text-[11px] font-medium text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-900"
      >
        کلید و مدل
      </button>
    );
  }

  return (
    <form
      className="mt-2 flex w-full flex-wrap items-end gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        const patch: Record<string, unknown> = { model, daily_message_limit: limit };
        // فقط وقتی کلید فرستاده می‌شود که چیزی تایپ شده باشد — وگرنه ذخیرهٔ
        // یک تغییرِ نامربوط، کلیدِ موجود را پاک می‌کرد.
        if (apiKey.trim()) patch.api_key = apiKey.trim();
        void onSave(row, patch).then(() => setOpen(false));
      }}
    >
      <label className="flex min-w-[180px] flex-1 flex-col gap-1 text-[11px] text-gray-500">
        کلید اختصاصی
        <PasswordInput
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder={row.api_key_configured ? row.api_key_hint : "از کلید پیش‌فرض"}
          baseClassName={`${inputClass} pl-11`}
        />
      </label>
      <label className="flex flex-col gap-1 text-[11px] text-gray-500">
        مدل اختصاصی
        <input dir="ltr" value={model} onChange={(e) => setModel(e.target.value)} className={inputClass} />
      </label>
      <label className="flex flex-col gap-1 text-[11px] text-gray-500">
        سقف روزانه (۰ = بی‌حد)
        <input
          type="number"
          min={0}
          value={String(limit)}
          onChange={(e) => setLimit(Number(e.target.value))}
          className={`${inputClass} w-28`}
        />
      </label>
      <Button type="submit">ذخیره</Button>
      <Button variant="secondary" onClick={() => setOpen(false)}>
        انصراف
      </Button>
    </form>
  );
}
