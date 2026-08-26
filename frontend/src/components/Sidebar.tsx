import { NavLink } from "react-router-dom";
import { APP_NAME, APP_NAME_FA } from "../appInfo";
import { Tooltip } from "../ui/Tooltip";
import { BrandMark } from "./Brand";
import type { NavItem } from "./nav";

/** ناوبری کناری — ستونِ شناورِ سمت راست.
 *
 *  چرا کنار و نه بالا: ناوبری افقی هر آیتمی که اضافه می‌شود از عرضِ صفحه
 *  می‌دزدد، و منابع انسانی هشت تا ده آیتم دارد. در ستون، فهرست عمودی است و
 *  اضافه‌شدنِ آیتم بعدی به هیچ‌چیز فشار نمی‌آورد. مهم‌تر اینکه برچسبِ هر آیتم
 *  کنار یک نشانه می‌نشیند، پس در حالت جمع‌شده هم صفحه قابل استفاده می‌ماند.
 *
 *  در RTL این ستون اولین فرزندِ فلکس است، یعنی خودبه‌خود سمت راست می‌افتد —
 *  همان سمتی که چشمِ فارسی‌خوان از آن شروع می‌کند.
 *
 *  پنل خودش گرد و جدا از لبه‌هاست: `Layout` فاصله را می‌دهد، این‌جا فقط
 *  گردی و مرز و سایه است — در حالت باز و جمع‌شده یکسان، چون یک ستونِ جمع‌شدهٔ
 *  چهارگوش کنار یک صفحهٔ گرد، تکه‌ای از یک طرحِ دیگر به نظر می‌رسد.
 */
export function Sidebar({
  items,
  collapsed,
  onToggleCollapse,
  onNavigate,
}: {
  items: NavItem[];
  collapsed: boolean;
  onToggleCollapse: () => void;
  /** در کشوی موبایل، هر کلیک باید کشو را ببندد. */
  onNavigate?: () => void;
}) {
  return (
    <div className="flex h-full flex-col overflow-hidden rounded-3xl border border-gray-200 bg-white shadow-sm">
      <div
        className={`flex h-14 shrink-0 items-center border-b border-gray-200 ${
          collapsed ? "justify-center px-2" : "gap-2.5 px-4"
        }`}
      >
        <Tooltip label={APP_NAME_FA} enabled={collapsed}>
          <NavLink to="/" aria-label={APP_NAME} onClick={onNavigate} className="flex items-center gap-2.5">
            <BrandMark className="h-7 w-7 shrink-0" />
            {!collapsed && (
              <span className="truncate text-sm font-extrabold tracking-tight text-gray-900">
                {APP_NAME_FA}
              </span>
            )}
          </NavLink>
        </Tooltip>
      </div>

      <nav aria-label="منوی اصلی" className="min-h-0 flex-1 overflow-y-auto p-2">
        <ul className="space-y-0.5">
          {items.map((item) => (
            <li key={item.to}>
              {/* در حالت جمع‌شده، برچسب از DOM حذف نمی‌شود بلکه فقط دیده
                  نمی‌شود — متنِ در دسترس برای صفحه‌خوان می‌ماند و همان متن
                  روی هاور هم به‌صورت حباب نشان داده می‌شود. */}
              <Tooltip label={item.label} enabled={collapsed}>
                <NavLink
                  to={item.to}
                  onClick={onNavigate}
                  className={({ isActive }) =>
                    `group relative flex items-center rounded-xl text-sm transition-colors ${
                      collapsed ? "justify-center px-2 py-2.5" : "gap-3 px-3 py-2.5"
                    } ${
                      isActive
                        ? "bg-pulse-50 font-semibold text-pulse-700"
                        : "font-medium text-gray-600 hover:bg-gray-100 hover:text-gray-900"
                    }`
                  }
                >
                  {({ isActive }) => (
                    <>
                      {/* نوارِ باریکِ کنارِ آیتم فعال: در حالت جمع‌شده تنها نشانهٔ
                          «کجا هستم» است، چون برچسبی در کار نیست.
                          کمی تورفته، تا روی قابِ گردِ پنل ننشیند و شبیه خطی که
                          از لبه بیرون زده دیده نشود. */}
                      <span
                        aria-hidden
                        className={`absolute inset-y-2 right-1 w-[3px] rounded-full bg-pulse-600 transition-opacity ${
                          isActive ? "opacity-100" : "opacity-0"
                        }`}
                      />
                      {item.icon}
                      <span className={collapsed ? "sr-only" : "truncate"}>{item.label}</span>
                    </>
                  )}
                </NavLink>
              </Tooltip>
            </li>
          ))}
        </ul>
      </nav>

      <div className="shrink-0 border-t border-gray-200 p-2">
        <Tooltip label="باز کردن منو" enabled={collapsed}>
          <button
            type="button"
            onClick={onToggleCollapse}
            aria-label={collapsed ? "باز کردن منو" : "جمع کردن منو"}
            className={`flex w-full items-center rounded-xl px-3 py-2 text-sm font-medium text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-900 ${
              collapsed ? "justify-center px-2" : "gap-3"
            }`}
          >
            <svg
              viewBox="0 0 20 20"
              className={`h-[18px] w-[18px] shrink-0 transition-transform ${collapsed ? "rotate-180" : ""}`}
              fill="none"
              stroke="currentColor"
              strokeWidth="1.7"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden
            >
              <path d="M12 5l-5 5 5 5" />
              <path d="M16.5 4v12" />
            </svg>
            {!collapsed && <span>جمع کردن منو</span>}
          </button>
        </Tooltip>
      </div>
    </div>
  );
}
