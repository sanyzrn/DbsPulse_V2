import { useEffect, useState } from "react";
import { Navigate, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "motion/react";
import { useAuth } from "../auth/AuthContext";
import { APP_NAME, APP_NAME_FA } from "../appInfo";
import { usePermissions } from "../auth/PermissionsContext";
import { BrandMark } from "./Brand";
import { ErrorBoundary } from "./ErrorBoundary";
import { Footer } from "./Footer";
import { NotificationBell } from "./NotificationBell";
import { ThemeToggle } from "../ui/ThemeToggle";
import { ProfileMenu } from "./ProfileMenu";
import { EASE_SOFT } from "../ui/motion";

/** `module` اختیاری: اگر آن بخش خاموش باشد، لینک اصلاً ساخته نمی‌شود.
 *  لینکی که کلیکش به «این بخش غیرفعال است» برسد، بدتر از نبودنش است. */
const NAV_BY_ROLE: Record<string, { to: string; label: string; module?: string }[]> = {
  hr: [
    // داشبورد صفحهٔ فرودِ HR است (خلاصهٔ وضعیت)، پس اول فهرست می‌آید.
    { to: "/hr/dashboard", label: "داشبورد" },
    { to: "/hr/queue", label: "صف بررسی" },
    { to: "/hr/personnel", label: "پرسنل" },
    { to: "/hr/users", label: "کاربران" },
    { to: "/hr/indicators", label: "شاخص‌ها" },
    // کنار «شاخص‌ها» چون هر دو «فرمِ ارزیابی» را تعریف می‌کنند: یکی چه چیزی
    // سنجیده می‌شود، دیگری چطور به نتیجه تبدیل می‌شود (P1-04).
    { to: "/hr/scoring-schemes", label: "طرح نمره‌دهی" },
    { to: "/hr/periods", label: "دوره‌های ارزیابی", module: "periods" },
    { to: "/improvement-plans", label: "برنامه‌های بهبود", module: "improvement_plans" },
  ],
  // مسئول واحد و معاونت ممکن است «مسئول پیگیریِ» یک برنامهٔ بهبود باشند (P1-10).
  // سرور فهرست را به برنامه‌های خودشان محدود می‌کند؛ بدون این لینک، تنها راه
  // رسیدن به آن، کلیک روی اعلان بود.
  unit_supervisor: [
    { to: "/supervisor", label: "افراد زیرمجموعه" },
    // P2-01: تا پیش از این، ارزیاب هیچ راهی نداشت بفهمد نمره‌دهی‌اش نسبت به
    // بقیه کجاست — و این مفیدترین بازخوردی است که یک نمره‌دهنده می‌گیرد.
    { to: "/my-scoring", label: "الگوی نمره‌دهی من", module: "role_analytics" },
    { to: "/improvement-plans", label: "برنامه‌های بهبود" },
  ],
  // معاونت هم نمره می‌دهد (مسیر «مدیر») و هم تصمیم‌گیر است، پس هر دو نما را دارد.
  deputy: [
    { to: "/deputy", label: "پرونده‌های در انتظار" },
    { to: "/my-scoring", label: "الگوی نمره‌دهی من", module: "role_analytics" },
    { to: "/executive", label: "تحلیل سازمان", module: "role_analytics" },
    { to: "/improvement-plans", label: "برنامه‌های بهبود" },
  ],
  ceo: [
    { to: "/ceo", label: "پرونده‌های در انتظار" },
    { to: "/executive", label: "تحلیل سازمان", module: "role_analytics" },
  ],
  employee: [{ to: "/me", label: "کارنامه من" }],
  // پشتیبانی فنی هیچ صف کاری‌ای ندارد. هر دو لینکش («گزارش رویدادها» و
  // «مدیریت سامانه») از روی مجوز اضافه می‌شوند، نه از این جدول — چون این دو
  // به نقش گره نخورده‌اند و هرکسی که مجوزش را بگیرد باید ببیندشان.
  support: [],
};

export function Layout() {
  const { user, logout } = useAuth();
  const { can, moduleEnabled } = usePermissions();
  const navigate = useNavigate();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);

  // کشوی موبایل با تغییر مسیر بسته می‌شود. بدون این، کاربر روی یک لینک می‌زند،
  // صفحه عوض می‌شود و کشو باز جلوی همان صفحه می‌ماند.
  useEffect(() => setMenuOpen(false), [location.pathname]);

  if (!user) return null;
  // رمز موقت (تعیین‌شده توسط HR) باید قبل از هر کار دیگری عوض شود
  if (user.must_change_password && location.pathname !== "/change-password") {
    return <Navigate to="/change-password" replace />;
  }
  const links = (NAV_BY_ROLE[user.role] ?? []).filter(
    (link) => link.module === undefined || moduleEnabled(link.module),
  );
  // هر دو بر پایهٔ مجوزند نه نقش. تا امروز «گزارش رویدادها» در فهرست ثابتِ HR
  // بود و «مدیریت سامانه» با `manage_users` باز می‌شد — یعنی همان کسی که در
  // زنجیره تصمیم می‌گیرد، هر دو را هم داشت.
  if (can("view_audit_log") || can("view_diagnostics")) {
    links.push({ to: "/hr/audit-log", label: "گزارش رویدادها" });
  }
  if (can("manage_capabilities") || can("manage_modules")) {
    links.push({ to: "/administration", label: "مدیریت سامانه" });
  }

  function handleLogout() {
    logout();
    navigate("/login");
  }

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

      {/* نوار برنامه: تمام‌عرض و چسبیده به بالا، با یک خط مرزی به‌جای کارتِ
          شناور. کارتِ قبلی دو ردیف ارتفاع می‌گرفت (برند بالا، ناوبری پایین) و
          از هر طرف حاشیه می‌خواست — روی صفحه‌های داده‌محور، آن فضا گران است. */}
      <header className="sticky top-0 z-40 border-b border-gray-200 bg-white/90 backdrop-blur-md">
        <div className="mx-auto flex h-14 w-full max-w-[1600px] items-center gap-3 px-4 sm:px-6">
          <NavLink to="/" className="flex shrink-0 items-center gap-2.5" aria-label={APP_NAME}>
            <BrandMark className="h-7 w-7" />
            <span className="hidden text-sm font-extrabold tracking-tight text-gray-900 sm:inline">
              {APP_NAME_FA}
            </span>
          </NavLink>

          {/* ناوبری دسکتاپ در همان ردیف برند می‌نشیند. زیر lg به کشو می‌رود،
              چون منابع انسانی تا ۱۰ آیتم دارد و ۱۰ آیتم در عرض کم یا می‌شکند
              یا اسکرول افقی می‌سازد — هر دو بدتر از یک دکمهٔ منو هستند. */}
          <nav className="hidden min-w-0 flex-1 lg:block" aria-label="منوی اصلی">
            <ul className="flex items-center gap-0.5">
              {links.map((link) => (
                <li key={link.to}>
                  <NavLink to={link.to} className={desktopLinkClass}>
                    {link.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>

          <div className="flex flex-1 items-center justify-end gap-1 lg:flex-none">
            <ThemeToggle />
            <NotificationBell />
            <ProfileMenu user={user} onLogout={handleLogout} />
            <button
              type="button"
              onClick={() => setMenuOpen((open) => !open)}
              aria-expanded={menuOpen}
              aria-label={menuOpen ? "بستن منو" : "باز کردن منو"}
              className="flex h-9 w-9 items-center justify-center rounded-xl text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-900 lg:hidden"
            >
              <svg viewBox="0 0 20 20" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
                {menuOpen ? <path d="M5 5l10 10M15 5L5 15" /> : <path d="M3 6h14M3 10h14M3 14h14" />}
              </svg>
            </button>
          </div>
        </div>

        {/* کشوی موبایل: فهرست عمودی با هدف لمسی درست، به‌جای فشرده‌کردن ۱۰
            قرص در دو خطِ شکسته. */}
        <AnimatePresence initial={false}>
          {menuOpen && (
            <motion.nav
              key="mobile-nav"
              aria-label="منوی اصلی (موبایل)"
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.22, ease: EASE_SOFT }}
              className="overflow-hidden border-t border-gray-100 lg:hidden"
            >
              <ul className="mx-auto max-w-[1600px] px-3 py-2 sm:px-5">
                {links.map((link) => (
                  <li key={link.to}>
                    <NavLink to={link.to} className={mobileLinkClass}>
                      {link.label}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </motion.nav>
          )}
        </AnimatePresence>
      </header>

      <main
        id="main-content"
        tabIndex={-1}
        className="mx-auto w-full max-w-[1600px] flex-1 px-4 py-6 sm:px-6 sm:py-8"
      >
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
              transition={{ duration: 0.28, ease: EASE_SOFT }}
            >
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </ErrorBoundary>
      </main>

      <Footer />
    </div>
  );
}

/** حالت فعال با پس‌زمینهٔ ملایم و متن پررنگ مشخص می‌شود، نه با قرصِ تیرهٔ تو‌پر.
 *  قرصِ تیره در ردیفی که کنارش برند و زنگوله و آواتار هست، سنگین‌ترین چیز نوار
 *  می‌شد و چشم را از محتوای صفحه می‌دزدید. */
const desktopLinkClass = ({ isActive }: { isActive: boolean }) =>
  `block whitespace-nowrap rounded-lg px-3 py-1.5 text-[13px] transition-colors ${
    isActive
      ? "bg-gray-100 font-semibold text-gray-900"
      : "font-medium text-gray-500 hover:bg-gray-50 hover:text-gray-900"
  }`;

const mobileLinkClass = ({ isActive }: { isActive: boolean }) =>
  `block rounded-xl px-3 py-2.5 text-sm transition-colors ${
    isActive ? "bg-gray-100 font-semibold text-gray-900" : "font-medium text-gray-600"
  }`;
