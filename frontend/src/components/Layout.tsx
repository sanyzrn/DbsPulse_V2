import { Navigate, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "motion/react";
import { useAuth } from "../auth/AuthContext";
import { APP_NAME, APP_NAME_FA, FEATURE_PERIODS_ENABLED } from "../appInfo";
import { BrandMark } from "./Brand";
import { ErrorBoundary } from "./ErrorBoundary";
import { Footer } from "./Footer";
import { NotificationBell } from "./NotificationBell";
import { ProfileMenu } from "./ProfileMenu";
import { EASE_SOFT } from "../ui/motion";

const NAV_BY_ROLE: Record<string, { to: string; label: string }[]> = {
  hr: [
    // داشبورد صفحهٔ فرودِ HR است (خلاصهٔ وضعیت)، پس اول فهرست می‌آید.
    { to: "/hr/dashboard", label: "داشبورد" },
    { to: "/hr/personnel", label: "پرسنل" },
    { to: "/hr/users", label: "کاربران" },
    { to: "/hr/indicators", label: "شاخص‌ها" },
    { to: "/hr/queue", label: "صف بررسی" },
    // «دوره‌های ارزیابی» پشت پرچم ویژگی — فعلاً غیرفعال (رجوع به appInfo.ts)
    ...(FEATURE_PERIODS_ENABLED
      ? [{ to: "/hr/periods", label: "دوره‌های ارزیابی" }]
      : []),
    { to: "/hr/improvement-plans", label: "برنامه‌های بهبود" },
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
    `whitespace-nowrap rounded-full px-3.5 py-1.5 text-sm transition-colors duration-150 ${
      isActive ? "bg-charcoal-900 font-semibold text-white" : "text-gray-500 hover:text-gray-900"
    }`;

  return (
    <div className="flex min-h-screen flex-col bg-cream-50">
      {/* پرش به محتوای اصلی: کاربر کیبورد/screen reader مجبور نیست هر بار کل هدر
          (برند، زنگوله، منوی کاربر، ناوبری نقش) را Tab بزند تا به محتوای صفحه برسد */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:right-2 focus:z-50 focus:rounded-xl focus:bg-pulse-600 focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-white focus:shadow-lg"
      >
        پرش به محتوای اصلی
      </a>

      <div className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-4 pt-6 pb-6 sm:px-6">
        {/* هدر شناور: کارت گرد و سایه‌دار، جدا از لبه‌های صفحه — نه نوار تمام‌عرض چسبیده به بالا */}
        <header className="sticky top-6 z-40 rounded-3xl border border-gray-100 bg-white shadow-float">
          <div className="flex items-center justify-between gap-4 px-4 py-2.5 sm:px-5">
            <NavLink
              to="/"
              className="flex items-center gap-2.5 rounded-full border border-gray-200 py-1.5 pl-4 pr-2"
              aria-label={APP_NAME}
            >
              <BrandMark className="h-7 w-7" />
              <span dir="ltr" className="text-sm font-extrabold tracking-tight text-gray-900">
                {APP_NAME_FA}
              </span>
            </NavLink>

            <div className="flex items-center gap-2">
              <NotificationBell />
              <ProfileMenu user={user} onLogout={handleLogout} />
            </div>
          </div>

          {/* ناوبری — در عرض‌های کم آیتم‌ها به خط بعد می‌شکنند (wrap) به‌جای اسکرول
              افقی؛ اسکرول افقی یک اسکرول‌بار ۶ پیکسلیِ قرمز پایین منو می‌ساخت که هم
              ارتفاع کم منو را می‌بلعید و هم زشت بود. */}
          <nav className="border-t border-gray-100 px-3 py-2 sm:px-4" aria-label="منوی اصلی">
            <ul className="flex flex-wrap gap-1">
              {links.map((link) => (
                <li key={link.to}>
                  <NavLink to={link.to} className={navLinkClass}>
                    {link.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
        </header>

        <main id="main-content" tabIndex={-1} className="flex-1 py-4 sm:py-6">
          {/* ErrorBoundary با key مسیر دوباره mount می‌شود تا خطای یک صفحه با رفتن به
              صفحهٔ دیگر خودبه‌خود پاک شود، نه اینکه کاربر برای همیشه در حالت خطا بماند */}
          <ErrorBoundary key={location.pathname} title="مشکلی در نمایش این صفحه پیش آمد">
            {/* انتقال صفحه — cross-fade نرم با خروجِ صفحهٔ قبل (mode="wait") تا تعویض
                مسیرها به‌جای پرشِ ناگهانی، یکنواخت و آرام دیده شود */}
            <AnimatePresence mode="wait">
              <motion.div
                key={location.pathname}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.24, ease: EASE_SOFT }}
              >
                <Outlet />
              </motion.div>
            </AnimatePresence>
          </ErrorBoundary>
        </main>

        <Footer />
      </div>
    </div>
  );
}
