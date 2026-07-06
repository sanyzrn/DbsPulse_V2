import { Navigate, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { motion } from "motion/react";
import { useAuth } from "../auth/AuthContext";
import { APP_NAME, APP_NAME_FA } from "../appInfo";
import { BrandMark } from "./Brand";
import { ErrorBoundary } from "./ErrorBoundary";
import { Footer } from "./Footer";
import { NotificationBell } from "./NotificationBell";
import { ROLE_LABELS } from "../types";

const NAV_BY_ROLE: Record<string, { to: string; label: string }[]> = {
  hr: [
    { to: "/hr/personnel", label: "پرسنل" },
    { to: "/hr/users", label: "کاربران" },
    { to: "/hr/indicators", label: "شاخص‌ها" },
    { to: "/hr/queue", label: "صف بررسی" },
    { to: "/hr/periods", label: "دوره‌های ارزیابی" },
    { to: "/hr/improvement-plans", label: "برنامه‌های بهبود" },
    { to: "/hr/dashboard", label: "داشبورد تحلیلی" },
    { to: "/hr/audit-log", label: "گزارش رویدادها" },
  ],
  unit_supervisor: [{ to: "/supervisor", label: "افراد زیرمجموعه" }],
  deputy: [{ to: "/deputy", label: "پرونده‌های در انتظار" }],
  ceo: [{ to: "/ceo", label: "پرونده‌های در انتظار" }],
  employee: [{ to: "/me", label: "کارنامه من" }],
};

export function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  if (!user) return null;
  // رمز موقت (تعیین‌شده توسط HR) باید قبل از هر کار دیگری عوض شود
  if (user.must_change_password && location.pathname !== "/change-password") {
    return <Navigate to="/change-password" replace />;
  }
  const links = NAV_BY_ROLE[user.role] ?? [];

  function handleLogout() {
    logout();
    navigate("/login");
  }

  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    `whitespace-nowrap rounded-xl px-3.5 py-1.5 text-sm transition-all duration-200 ${
      isActive
        ? "bg-gradient-to-bl from-pulse-500/10 to-pulse-violet-500/10 font-semibold text-pulse-700"
        : "text-gray-500 hover:bg-gray-100 hover:text-gray-800"
    }`;

  return (
    <div className="flex min-h-screen flex-col bg-gray-50">
      {/* پرش به محتوای اصلی: کاربر کیبورد/screen reader مجبور نیست هر بار کل هدر
          (برند، زنگوله، منوی کاربر، ناوبری نقش) را Tab بزند تا به محتوای صفحه برسد */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:right-2 focus:z-50 focus:rounded-xl focus:bg-pulse-600 focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-white focus:shadow-lg"
      >
        پرش به محتوای اصلی
      </a>
      <header className="sticky top-0 z-40 border-b border-gray-100 bg-white/80 shadow-sm backdrop-blur-xl">
        {/* خط گرادیانت بالای هدر */}
        <div className="h-0.5 w-full bg-gradient-to-l from-pulse-500 via-pulse-violet-500 to-pulse-500" />
        {/* ردیف اول: برند + منوی کاربر */}
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-2.5">
          <NavLink to="/" className="flex items-center gap-3" aria-label={APP_NAME}>
            <BrandMark className="h-9 w-9" />
            <span className="leading-tight">
              <span dir="ltr" className="block text-sm font-extrabold tracking-tight text-gray-900">
                {APP_NAME}
              </span>
              <span className="block text-[11px] text-gray-500">{APP_NAME_FA}</span>
            </span>
          </NavLink>

          <div className="flex items-center gap-1 sm:gap-2">
            <NotificationBell />
            <span aria-hidden className="mx-1 hidden h-6 w-px bg-gray-200 sm:block" />
            <span className="flex items-center gap-2">
              <span className="rounded-full bg-gradient-to-br from-pulse-500 to-pulse-violet-600 p-0.5">
                <span
                  aria-hidden
                  className="flex h-7 w-7 items-center justify-center rounded-full bg-white text-sm font-bold gradient-text"
                >
                  {user.username.charAt(0).toUpperCase()}
                </span>
              </span>
              <span className="hidden leading-tight md:block">
                <span className="block text-sm font-medium text-gray-800">{user.username}</span>
                <span className="block text-[11px] text-gray-500">{ROLE_LABELS[user.role]}</span>
              </span>
            </span>
            <NavLink
              to="/change-password"
              title="تغییر رمز عبور"
              className="rounded-xl p-2 text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700"
            >
              <svg viewBox="0 0 20 20" className="h-4.5 w-4.5" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <circle cx="7" cy="10" r="4" />
                <path d="M11 10h6m-2 0v3m-2.5-3v2" />
              </svg>
              <span className="sr-only">تغییر رمز عبور</span>
            </NavLink>
            <button
              onClick={handleLogout}
              className="flex items-center gap-1.5 rounded-xl border border-gray-200 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 shadow-sm transition-all duration-200 hover:bg-gray-50 hover:shadow-md"
            >
              <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M13 7l3 3-3 3m3-3H8m2 6H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h5" />
              </svg>
              <span className="hidden sm:inline">خروج</span>
              <span className="sr-only sm:hidden">خروج</span>
            </button>
          </div>
        </div>

        {/* ردیف دوم: ناوبری — در عرض‌های کم به‌صورت افقی اسکرول می‌خورد */}
        <nav className="border-t border-gray-50" aria-label="منوی اصلی">
          <div className="mx-auto max-w-6xl overflow-x-auto px-4">
            <ul className="flex gap-1 py-1.5">
              {links.map((link) => (
                <li key={link.to}>
                  <NavLink to={link.to} className={navLinkClass}>
                    {link.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        </nav>
      </header>

      <main id="main-content" tabIndex={-1} className="mx-auto w-full max-w-6xl flex-1 p-4 sm:p-6">
        {/* ErrorBoundary با key مسیر دوباره mount می‌شود تا خطای یک صفحه با رفتن به
            صفحهٔ دیگر خودبه‌خود پاک شود، نه اینکه کاربر برای همیشه در حالت خطا بماند */}
        <ErrorBoundary key={location.pathname} title="مشکلی در نمایش این صفحه پیش آمد">
          {/* انیمیشن انتقال صفحه — fade + slide-up با key مسیر */}
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, ease: "easeOut" }}
          >
            <Outlet />
          </motion.div>
        </ErrorBoundary>
      </main>

      <Footer />
    </div>
  );
}
