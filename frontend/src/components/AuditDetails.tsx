/** ستون «جزئیات» گزارش رویدادها — به زبان آدم، نه JSON.
 *
 * پیش از این محتوای ستون عیناً `JSON.stringify` بود:
 *
 *     بعد: {"ip":"127.0.0.1"}
 *     بعد: {"scored_indicators":1}
 *     بعد: {"sla_reminder":0,"orphaned_case":0,"contract_expiry":0,…}
 *
 * یعنی همان ردیفی که قرار است مدرک باشد، برای کسی که مدرک را می‌خواند ناخوانا بود.
 * این‌جا هر کلید یک برچسب فارسی و یک قالب‌بندی دارد، و وقتی رویدادی هم مقدار پیشین
 * و هم مقدار جدید دارد، به‌جای دو بلوک JSON یک «قبلی ← جدید» نشان داده می‌شود —
 * چون چیزی که خواننده دنبالش است همان تفاوت است.
 *
 * اصل مهم: کلید ناشناخته پنهان نمی‌شود. اگر رویداد تازه‌ای اضافه شود و برچسبش
 * این‌جا نباشد، خام نمایش داده می‌شود؛ نبودِ برچسب نباید به گم‌شدن مدرک منجر شود.
 */
import { ROLE_LABELS, STATUS_LABELS } from "../types";

type Json = Record<string, unknown>;

const faNum = (value: number) => value.toLocaleString("fa-IR");

const LABELS: Record<string, string> = {
  // عمومی
  id: "شناسه",
  name: "نام",
  title: "عنوان",
  description: "شرح",
  reason: "دلیل",
  status: "وضعیت",
  role: "نقش",
  username: "نام کاربری",
  is_active: "فعال",
  section: "بخش",
  category: "دسته",
  display_order: "ترتیب نمایش",
  fields: "فیلدهای تغییریافته",
  // ورود و امنیت
  ip: "نشانی IP",
  until: "تا",
  // ارزیابی
  stage: "مرحله",
  scored_indicators: "تعداد شاخص امتیازگرفته",
  implicit: "به‌صورت خودکار",
  general_score_pct: "امتیاز عمومی",
  specialized_score_pct: "امتیاز تخصصی",
  final_weighted_pct: "امتیاز نهایی وزنی",
  recommendation: "توصیه",
  acknowledged_at: "زمان رؤیت",
  objection_reason: "متن اعتراض",
  resolution: "پاسخ به اعتراض",
  by_subject: "توسط خودِ فرد",
  parent_comment_id: "در پاسخ به کامنت",
  ordered_ids: "ترتیب جدید",
  // افراد و دسترسی
  personnel_id: "پرسنل",
  personnel_code: "کد پرسنلی",
  full_name: "نام و نام خانوادگی",
  created_with_personnel: "همراه با ثبت پرسنل",
  unit_supervisor_user_id: "مسئول واحد",
  deputy_user_id: "معاونت",
  ceo_user_id: "مدیرعامل",
  hr_user_id: "کارشناس منابع انسانی",
  // برنامهٔ بهبود
  plan_id: "برنامهٔ بهبود",
  goal_id: "هدف",
  is_done: "انجام‌شده",
  // خروجی‌ها
  filters: "فیلترهای اعمال‌شده",
  row_count: "تعداد ردیف",
  // یادآوری‌های خودکار
  contract_expiry: "قرارداد رو به انقضا",
  sla_reminder: "یادآوری مهلت",
  orphaned_case: "پروندهٔ بی‌صاحب",
  improvement_review: "بازنگری برنامهٔ بهبود",
  stale_login_attempts_purged: "پاک‌سازی تلاش‌های ورود",
};

const PERCENT_KEYS = new Set([
  "general_score_pct",
  "specialized_score_pct",
  "final_weighted_pct",
]);
const USER_KEYS = new Set([
  "unit_supervisor_user_id",
  "deputy_user_id",
  "ceo_user_id",
  "hr_user_id",
]);

function formatValue(key: string, value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "بله" : "خیر";

  if (typeof value === "number") {
    if (PERCENT_KEYS.has(key)) return `${faNum(Math.round(value * 10) / 10)}٪`;
    if (USER_KEYS.has(key) || key.endsWith("_id")) return `#${faNum(value)}`;
    return faNum(value);
  }

  if (typeof value === "string") {
    if (key === "status") return STATUS_LABELS[value as keyof typeof STATUS_LABELS] ?? value;
    if (key === "role") return ROLE_LABELS[value as keyof typeof ROLE_LABELS] ?? value;
    // تاریخ‌های ISO را به شکل خواندنی درمی‌آوریم، ولی رشته‌های دیگر دست‌نخورده می‌مانند
    if (/^\d{4}-\d{2}-\d{2}(T|$)/.test(value)) {
      const parsed = new Date(value);
      if (!Number.isNaN(parsed.valueOf())) return parsed.toLocaleDateString("fa-IR");
    }
    return value;
  }

  if (Array.isArray(value)) {
    return value.length === 0 ? "—" : value.map((v) => formatValue(key, v)).join("، ");
  }

  // شیء تودرتو (مثلاً filters) — کلیدهایش را هم برچسب می‌زنیم
  if (typeof value === "object") {
    const entries = Object.entries(value as Json);
    if (entries.length === 0) return "—";
    return entries.map(([k, v]) => `${LABELS[k] ?? k}: ${formatValue(k, v)}`).join(" · ");
  }

  return String(value);
}

interface Line {
  key: string;
  label: string;
  before?: string;
  after?: string;
}

/** یک ردیف را به فهرستی از خطوط «برچسب: قبلی ← جدید» تبدیل می‌کند. */
export function auditLines(oldValue: Json | null, newValue: Json | null): Line[] {
  const keys = [
    ...new Set([...Object.keys(oldValue ?? {}), ...Object.keys(newValue ?? {})]),
  ];
  return keys.map((key) => {
    const line: Line = { key, label: LABELS[key] ?? key };
    if (oldValue && key in oldValue) line.before = formatValue(key, oldValue[key]);
    if (newValue && key in newValue) line.after = formatValue(key, newValue[key]);
    return line;
  });
}

export function AuditDetails({
  oldValue,
  newValue,
}: {
  oldValue: Json | null;
  newValue: Json | null;
}) {
  const lines = auditLines(oldValue, newValue);
  if (lines.length === 0) return <span className="text-gray-300">—</span>;

  return (
    <ul className="space-y-0.5">
      {lines.map((line) => (
        <li key={line.key} className="flex flex-wrap items-baseline gap-x-1.5 text-xs leading-5">
          <span className="text-gray-400">{line.label}:</span>
          {line.before !== undefined && line.after !== undefined ? (
            <>
              <span className="text-gray-400 line-through decoration-gray-300">{line.before}</span>
              <span className="text-gray-300" aria-label="تغییر یافت به">
                ←
              </span>
              <span className="font-medium text-gray-800">{line.after}</span>
            </>
          ) : (
            <span className="font-medium text-gray-800">
              {line.after ?? line.before}
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}
