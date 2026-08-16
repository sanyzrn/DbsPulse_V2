import { Navigate, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "motion/react";
import { useAuth } from "../auth/AuthContext";
import { APP_NAME, APP_NAME_FA } from "../appInfo";
import { usePermissions } from "../auth/PermissionsContext";
import { BrandMark } from "./Brand";
import { ErrorBoundary } from "./ErrorBoundary";
import { Footer } from "./Footer";
import { NotificationBell } from "./NotificationBell";
import { ProfileMenu } from "./ProfileMenu";
import { EASE_SOFT } from "../ui/motion";
import { AnimatedGridBackground } from "./AnimatedGridBackground";

/** `module` اختیاری: اگر آن بخش خاموش باشد، لینک اصلاً ساخته نمی‌شود.
 *  لینکی که کلیکش به «این بخش غیرفعال است» برسد، بدتر از نبودنش است. */
const NAV_BY_ROLE: Record<string, { to: string; label: string; module?: string }[]> = {
  hr: [
    // داشبورد صفحهٔ فرودِ HR است (خلاصهٔ وضعیت)، پس اول فهرست می‌آید.
    { to: "/hr/dashboard", label: "داشبورد" },
    { to: "/hr/personnel", label: "پرسنل" },
    { to: "/hr/users", label: "کاربران" },
    { to: "/hr/indicators", label: "شاخص‌ها" },
    // کنار «شاخص‌ها» چون هر دو «فرمِ ارزیابی» را تعریف می‌کنند: یکی چه چیزی
    // سنجیده می‌شود، دیگری چطور به نتیجه تبدیل می‌شود (P1-04).
    { to: "/hr/scoring-schemes", label: "طرح نمره‌دهی" },
    { to: "/hr/queue", label: "صف بررسی" },
    { to: "/hr/periods", label: "دوره‌های ارزیابی", module: "periods" },
    { to: "/improvement-plans", label: "برنامه‌های بهبود", module: "improvement_plans" },
    { to: "/hr/audit-log", label: "گزارش رویدادها" },
  ],
  // مسئول واحد و معاونت ممکن است «مسئول پیگیریِ» یک برنامهٔ بهبود باشند (P1-10).
  // سرور فهرست را به برنامه‌های خودشان محدود می‌کند؛ بدون این لینک، تنها راه
  // رسیدن به آن، کلیک روی اعلان بود.
  unit_supervisor: [
    { to: "/supervisor", label: "افراد زیرمجموعه" },
    // P2-01: تا پیش از این، ارزیاب هیچ راهی نداشت بفهمد نمره‌دهی‌اش نسبت به
    // بقیه کجاست — و این مفیدترین بازخوردی است که یک نمره‌دهنده می‌گیرد.
    { to: "/my-scoring", label: "نمره‌دهی من", module: "role_analytics" },
    { to: "/improvement-plans", label: "برنامه‌های بهبود" },
  ],
  // معاونت هم نمره می‌دهد (مسیر «مدیر») و هم تصمیم‌گیر است، پس هر دو نما را دارد.
  deputy: [
    { to: "/deputy", label: "پرونده‌های در انتظار" },
    { to: "/my-scoring", label: "نمره‌دهی من", module: "role_analytics" },
    { to: "/executive", label: "تحلیل سازمان", module: "role_analytics" },
    { to: "/improvement-plans", label: "برنامه‌های بهبود" },
  ],
  ceo: [
    { to: "/ceo", label: "پرونده‌های در انتظار" },
    { to: "/executive", label: "تحلیل سازمان", module: "role_analytics" },
  ],
  employee: [{ to: "/me", label: "کارنامه من" }],
  // پشتیبانی فنی هیچ صف کاری‌ای ندارد. تنها لینکش («مدیریت سامانه») از روی
  // مجوز اضافه می‌شود، نه از این جدول — چون همان لینک برای HR دارای مجوز هم هست.
  support: [],
};

export function Layout() {
  const { user, logout } = useAuth();
  const { can, moduleEnabled } = usePermissions();
  const navigate = useNavigate();
  const location = useLocation();

  if (!user) return null;
  // رمز موقت (تعیین‌شده توسط HR) باید قبل از هر کار دیگری عوض شود
  if (user.must_change_password && location.pathname !== "/change-password") {
    return <Navigate to="/change-password" replace />;
  }
  const links = (NAV_BY_ROLE[user.role] ?? []).filter(
    (link) => link.module === undefined || moduleEnabled(link.module),
  );

  function handleLogout() {
    logout();
    navigate("/login");
  }

  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    `whitespace-nowrap rounded-full px-3.5 py-1.5 text-sm transition-all duration-300 ${
      isActive ? "bg-charcoal-900 font-semibold text-white" : "text-gray-500 hover:text-gray-900"
    }`;

  return (
    <div className="flex min-h-screen flex-col">
      <AnimatedGridBackground />
      <div className="pointer-events-none fixed inset-0 -z-10 bg-[radial-gradient(circle_at_top_left,rgba(191,191,191,1),transparent_20%)]" />
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
              {/* مدیریت سامانه بر پایهٔ مجوز است نه نقش — حساب پشتیبانی فنی
                  نقش hr ندارد ولی باید این‌جا را ببیند. */}
              {(can("manage_users") || can("manage_modules")) && (
                <li>
                  <NavLink to="/administration" className={navLinkClass}>
                    مدیریت سامانه
                  </NavLink>
                </li>
              )}
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
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.34, ease: EASE_SOFT }}
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
