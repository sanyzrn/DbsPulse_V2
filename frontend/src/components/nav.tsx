import type { ReactNode } from "react";
import type { Capability } from "../auth/PermissionsContext";

/** یک آیتم ناوبری.
 *
 *  `module` اختیاری: اگر آن بخش خاموش باشد، لینک اصلاً ساخته نمی‌شود. لینکی که
 *  کلیکش به «این بخش غیرفعال است» برسد، بدتر از نبودنش است.
 *
 *  `capability` اختیاری: لینک‌هایی که به *مجوز* گره خورده‌اند نه به نقش. حساب
 *  مدیر سامانه نقشی در زنجیرهٔ ارزیابی ندارد، پس جدولِ نقش‌محور برایش خالی است —
 *  ولی مجوز ساخت حساب و تنظیم شاخص را دارد و باید به آن صفحه‌ها برسد.
 */
export interface NavItem {
  to: string;
  label: string;
  icon: ReactNode;
  module?: string;
  /** هر کدام از این مجوزها کافی است. */
  anyCapability?: Capability[];
}

const s = (d: ReactNode) => (
  <svg
    viewBox="0 0 20 20"
    className="h-[18px] w-[18px] shrink-0"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.6"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden
  >
    {d}
  </svg>
);

export const ICONS = {
  dashboard: s(
    <>
      <rect x="2.5" y="2.5" width="6" height="6" rx="1.5" />
      <rect x="11.5" y="2.5" width="6" height="6" rx="1.5" />
      <rect x="2.5" y="11.5" width="6" height="6" rx="1.5" />
      <rect x="11.5" y="11.5" width="6" height="6" rx="1.5" />
    </>
  ),
  queue: s(
    <>
      <path d="M2.5 12.5h4l1.5 2.5h4l1.5-2.5h4" />
      <path d="M4.5 3.5h11l2 9v3a1.5 1.5 0 0 1-1.5 1.5h-12A1.5 1.5 0 0 1 2.5 15.5v-3z" />
    </>
  ),
  personnel: s(
    <>
      <circle cx="7.5" cy="6.5" r="2.8" />
      <path d="M2.5 16.5c.9-2.9 2.8-4.4 5-4.4s4.1 1.5 5 4.4" />
      <path d="M13.5 4.2a2.6 2.6 0 0 1 0 5" />
      <path d="M14.5 12.4c1.5.5 2.6 1.9 3.1 4.1" />
    </>
  ),
  accounts: s(
    <>
      <rect x="2.5" y="4" width="15" height="12" rx="2" />
      <circle cx="7.5" cy="9.5" r="1.9" />
      <path d="M4.6 14c.5-1.4 1.6-2.1 2.9-2.1s2.4.7 2.9 2.1" />
      <path d="M12.8 8.5h3.2M12.8 11.5h3.2" />
    </>
  ),
  indicators: s(
    <>
      <path d="M7 5h10M7 10h10M7 15h10" />
      <path d="M3 4.6l1 1 1.6-1.9M3 9.6l1 1 1.6-1.9M3 14.6l1 1 1.6-1.9" />
    </>
  ),
  scheme: s(
    <>
      <path d="M3 6h14M3 10h14M3 14h14" />
      <circle cx="7" cy="6" r="1.8" />
      <circle cx="13" cy="10" r="1.8" />
      <circle cx="9" cy="14" r="1.8" />
    </>
  ),
  periods: s(
    <>
      <rect x="2.5" y="4" width="15" height="13" rx="2" />
      <path d="M2.5 8h15M6.5 2.5v3M13.5 2.5v3" />
    </>
  ),
  improvement: s(
    <>
      <path d="M3 13.5l4.5-4.5 3 3L17 5.5" />
      <path d="M13 5.5h4v4" />
    </>
  ),
  chart: s(
    <>
      <path d="M3 17V3" />
      <path d="M3 17h14" />
      <path d="M6.5 14V9M10 14V5.5M13.5 14v-3" />
    </>
  ),
  org: s(
    <>
      <rect x="7.5" y="2.5" width="5" height="4" rx="1" />
      <rect x="2.5" y="13.5" width="5" height="4" rx="1" />
      <rect x="12.5" y="13.5" width="5" height="4" rx="1" />
      <path d="M10 6.5v3.5M5 13.5V10h10v3.5" />
    </>
  ),
  scorecard: s(
    <>
      <path d="M5 2.5h7l3.5 3.5v11a1 1 0 0 1-1 1h-9.5a1 1 0 0 1-1-1v-13a1 1 0 0 1 1-1z" />
      <path d="M11.5 2.5V6h3.5" />
      <path d="M6.5 11l1.6 1.6 3.4-3.4" />
    </>
  ),
  audit: s(
    <>
      <path d="M10 3a7 7 0 1 1-6.8 5.4" />
      <path d="M3 3v4h4" />
      <path d="M10 6.5V10l2.5 1.6" />
    </>
  ),
  settings: s(
    <>
      <circle cx="10" cy="10" r="2.6" />
      <path d="M10 2.5v2M10 15.5v2M17.5 10h-2M4.5 10h-2M15.3 4.7l-1.4 1.4M6.1 13.9l-1.4 1.4M15.3 15.3l-1.4-1.4M6.1 6.1L4.7 4.7" />
    </>
  ),
} as const;

/** ناوبری هر نقش. ترتیب = ترتیبِ کارِ روزمرهٔ آن نقش، نه الفبا. */
export const NAV_BY_ROLE: Record<string, NavItem[]> = {
  hr: [
    { to: "/hr/dashboard", label: "داشبورد", icon: ICONS.dashboard },
    { to: "/hr/queue", label: "صف بررسی", icon: ICONS.queue },
    { to: "/me", label: "خودارزیابی من", icon: ICONS.scorecard, module: "self_assessment" },
    { to: "/hr/people", label: "مدیریت حساب و پرسنل", icon: ICONS.personnel },
    { to: "/hr/indicators", label: "شاخص‌ها", icon: ICONS.indicators },
    // کنار «شاخص‌ها» چون هر دو «فرمِ ارزیابی» را تعریف می‌کنند: یکی چه چیزی
    // سنجیده می‌شود، دیگری چطور به نتیجه تبدیل می‌شود (P1-04).
    { to: "/hr/scoring-schemes", label: "طرح نمره‌دهی", icon: ICONS.scheme },
    { to: "/hr/periods", label: "دوره‌های ارزیابی", icon: ICONS.periods, module: "periods" },
    {
      to: "/improvement-plans",
      label: "برنامه‌های بهبود",
      icon: ICONS.improvement,
      module: "improvement_plans",
    },
  ],
  // مسئول واحد و معاونت ممکن است «مسئول پیگیریِ» یک برنامهٔ بهبود باشند (P1-10).
  // سرور فهرست را به برنامه‌های خودشان محدود می‌کند؛ بدون این لینک، تنها راه
  // رسیدن به آن، کلیک روی اعلان بود.
  unit_supervisor: [
    { to: "/supervisor", label: "افراد زیرمجموعه", icon: ICONS.personnel },
    { to: "/me", label: "خودارزیابی من", icon: ICONS.scorecard, module: "self_assessment" },
    // P2-01: تا پیش از این، ارزیاب هیچ راهی نداشت بفهمد نمره‌دهی‌اش نسبت به
    // بقیه کجاست — و این مفیدترین بازخوردی است که یک نمره‌دهنده می‌گیرد.
    { to: "/my-scoring", label: "الگوی نمره‌دهی من", icon: ICONS.chart, module: "role_analytics" },
    { to: "/improvement-plans", label: "برنامه‌های بهبود", icon: ICONS.improvement },
  ],
  // معاونت هم نمره می‌دهد (مسیر «مدیر») و هم تصمیم‌گیر است، پس هر دو نما را دارد.
  deputy: [
    { to: "/deputy", label: "پرونده‌های در انتظار", icon: ICONS.queue },
    { to: "/my-scoring", label: "الگوی نمره‌دهی من", icon: ICONS.chart, module: "role_analytics" },
    { to: "/executive", label: "تحلیل سازمان", icon: ICONS.org, module: "role_analytics" },
    { to: "/improvement-plans", label: "برنامه‌های بهبود", icon: ICONS.improvement },
  ],
  ceo: [
    { to: "/ceo", label: "پرونده‌های در انتظار", icon: ICONS.queue },
    { to: "/executive", label: "تحلیل سازمان", icon: ICONS.org, module: "role_analytics" },
  ],
  employee: [{ to: "/me", label: "خودارزیابی و کارنامه من", icon: ICONS.scorecard }],
  // پشتیبانی فنی صف ارزیابی ندارد، ولی اگر حسابش به پرسنل وصل باشد مانند همهٔ
  // نقش‌های غیرِ مدیرعامل/معاونت خودارزیابی خودش را انجام می‌دهد.
  support: [
    { to: "/me", label: "خودارزیابی من", icon: ICONS.scorecard, module: "self_assessment" },
  ],
};

/** لینک‌هایی که به مجوز گره خورده‌اند، نه به نقش.
 *
 *  این فهرست تفاوتِ «مدیر سامانه» با یک نقشِ زنجیره را جبران می‌کند: حساب
 *  `support` جدولِ نقش‌محورِ خالی دارد، ولی مجوزهایش به او اجازهٔ ساخت حساب،
 *  تنظیم شاخص و مدیریت پرسنل را می‌دهند. تا امروز آن صفحه‌ها فقط از منوی نقش
 *  `hr` قابل رسیدن بودند — یعنی مجوز داشت و راه نداشت.
 */
export const NAV_BY_CAPABILITY: NavItem[] = [
  {
    to: "/hr/people",
    label: "مدیریت حساب و پرسنل",
    icon: ICONS.personnel,
    anyCapability: ["manage_personnel", "manage_users"],
  },
  { to: "/hr/indicators", label: "شاخص‌ها", icon: ICONS.indicators, anyCapability: ["manage_scoring"] },
  {
    to: "/hr/scoring-schemes",
    label: "طرح نمره‌دهی",
    icon: ICONS.scheme,
    anyCapability: ["manage_scoring"],
  },
  {
    to: "/hr/audit-log",
    label: "گزارش رویدادها",
    icon: ICONS.audit,
    anyCapability: ["view_audit_log", "view_diagnostics"],
  },
  {
    to: "/administration",
    label: "مدیریت سامانه",
    icon: ICONS.settings,
    anyCapability: ["manage_capabilities", "manage_modules", "manage_integrations"],
  },
];

/** فهرست نهاییِ لینک‌ها برای این کاربر — نقش، سپس مجوزها، بدون تکرار. */
export function navItemsFor(
  role: string,
  can: (capability: Capability) => boolean,
  moduleEnabled: (module: string) => boolean
): NavItem[] {
  const items = (NAV_BY_ROLE[role] ?? []).filter(
    (item) => item.module === undefined || moduleEnabled(item.module)
  );
  const seen = new Set(items.map((item) => item.to));
  for (const item of NAV_BY_CAPABILITY) {
    if (seen.has(item.to)) continue;
    if (!item.anyCapability?.some(can)) continue;
    items.push(item);
    seen.add(item.to);
  }
  return items;
}
