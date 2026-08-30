import { Link, useLocation } from "react-router-dom";

/** تب‌های مسیرمحور برای صفحه‌هایی که دو جریان کاریِ هم‌خانواده دارند.
 *
 * هر تب یک نشانی واقعی دارد؛ بنابراین با بازخوانی صفحه، اشتراک لینک و دکمهٔ
 * بازگشت مرورگر، انتخاب کاربر از بین نمی‌رود.
 */
export function SectionTabs({
  label,
  tabs,
}: {
  label: string;
  tabs: { to: string; label: string }[];
}) {
  const { pathname } = useLocation();

  return (
    <nav aria-label={label} className="overflow-x-auto">
      <div
        role="tablist"
        aria-label={label}
        className="inline-flex min-w-max gap-1 rounded-2xl border border-gray-200 bg-white p-1 shadow-sm"
      >
        {tabs.map((tab) => (
          <Link
            key={tab.to}
            to={tab.to}
            role="tab"
            aria-selected={pathname === tab.to}
            className={`rounded-xl px-3.5 py-1.5 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-pulse-500 focus-visible:ring-offset-1 ${
              pathname === tab.to
                ? "bg-pulse-600 text-white shadow-sm"
                : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
            }`}
          >
            {tab.label}
          </Link>
        ))}
      </div>
    </nav>
  );
}
