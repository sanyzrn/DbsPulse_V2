import { useEffect, useState } from "react";
import { Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "motion/react";
import { useAuth } from "../auth/AuthContext";
import { usePermissions } from "../auth/PermissionsContext";
import { ErrorBoundary } from "./ErrorBoundary";
import { Copilot } from "./copilot/Copilot";
import { Footer } from "./Footer";
import { NotificationBell } from "./NotificationBell";
import { ThemeToggle } from "../ui/ThemeToggle";
import { ProfileMenu } from "./ProfileMenu";
import { Sidebar } from "./Sidebar";
import { navItemsFor } from "./nav";
import { EASE_SOFT } from "../ui/motion";

const COLLAPSE_KEY = "dbspulse:sidebar-collapsed";

function readCollapsed(): boolean {
  try {
    return window.localStorage.getItem(COLLAPSE_KEY) === "1";
  } catch {
    return false;
  }
}

export function Layout() {
  const { user, logout } = useAuth();
  const { can, moduleEnabled } = usePermissions();
  const navigate = useNavigate();
  const location = useLocation();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(readCollapsed);

  // کشوی موبایل با تغییر مسیر بسته می‌شود. بدون این، کاربر روی یک لینک می‌زند،
  // صفحه عوض می‌شود و کشو باز جلوی همان صفحه می‌ماند.
  useEffect(() => setDrawerOpen(false), [location.pathname]);

  // پشتِ کشوی باز نباید صفحه اسکرول شود.
  useEffect(() => {
    if (!drawerOpen) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [drawerOpen]);

  useEffect(() => {
    function onEscape(e: KeyboardEvent) {
      if (e.key === "Escape") setDrawerOpen(false);
    }
    document.addEventListener("keydown", onEscape);
    return () => document.removeEventListener("keydown", onEscape);
  }, []);

  function toggleCollapse() {
    setCollapsed((value) => {
      const next = !value;
      try {
        window.localStorage.setItem(COLLAPSE_KEY, next ? "1" : "0");
      } catch {
        /* حالت ناشناس مرورگر — جمع‌بودنِ منو ارزش شکستنِ صفحه را ندارد */
      }
      return next;
    });
  }

  if (!user) return null;
  // رمز موقت (تعیین‌شده توسط HR) باید قبل از هر کار دیگری عوض شود
  if (user.must_change_password && location.pathname !== "/change-password") {
    return <Navigate to="/change-password" replace />;
  }

  const items = navItemsFor(user.role, can, moduleEnabled);
  const active = items.find((item) => location.pathname.startsWith(item.to));

  function handleLogout() {
    logout();
    navigate("/login");
  }

  return (
    /* پوستهٔ شناور: هیچ‌کدام از سه قاب (ناوبری، نوار بالا، پاصفحه) به لبهٔ
       پنجره نمی‌چسبند. فاصله را همین ظرف می‌دهد تا هر سه یک اندازه عقب
       بنشینند و گردیِ گوشه‌هایشان دیده شود. */
    <div className="flex min-h-screen gap-3 bg-cream-50 px-3 pb-3 lg:gap-4 lg:px-4 lg:pb-4">
      {/* پرش به محتوای اصلی: کاربر کیبورد/screen reader مجبور نیست هر بار کل
          ناوبری را Tab بزند تا به محتوای صفحه برسد */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:right-2 focus:z-50 focus:rounded-xl focus:bg-pulse-600 focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-white focus:shadow-lg"
      >
        پرش به محتوای اصلی
      </a>

      {/* ستون ثابت — از lg به بالا. `sticky` و نه `fixed` تا نیازی به جبرانِ
          دستیِ حاشیهٔ محتوا نباشد.
          ارتفاع = ارتفاع پنجره منهای فاصلهٔ بالا و پایین، تا پاصفحهٔ ستون هم
          از کفِ پنجره جدا بماند. */}
      <aside
        className={`sticky top-3 hidden h-[calc(100vh-1.5rem)] shrink-0 pt-3 transition-[width] duration-200 lg:top-4 lg:h-[calc(100vh-2rem)] lg:block lg:pt-4 ${
          collapsed ? "w-16" : "w-60"
        }`}
      >
        <Sidebar items={items} collapsed={collapsed} onToggleCollapse={toggleCollapse} />
      </aside>

      {/* کشوی موبایل */}
      <AnimatePresence>
        {drawerOpen && (
          <>
            <motion.div
              key="scrim"
              className="fixed inset-0 z-40 bg-gray-900/40 lg:hidden"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.18 }}
              onClick={() => setDrawerOpen(false)}
            />
            <motion.aside
              key="drawer"
              className="fixed inset-y-3 right-3 z-50 w-64 lg:hidden"
              initial={{ x: "100%" }}
              animate={{ x: 0 }}
              exit={{ x: "100%" }}
              transition={{ duration: 0.2, ease: EASE_SOFT }}
            >
              <Sidebar
                items={items}
                collapsed={false}
                onToggleCollapse={() => setDrawerOpen(false)}
                onNavigate={() => setDrawerOpen(false)}
              />
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* نوار بالا فقط چیزهای «همیشه در دسترس» را دارد: کجا هستم، اعلان‌ها،
            حساب من. ناوبری از این‌جا رفته، پس نوار می‌تواند نازک بماند.

            نوار هم شناور است، ولی محتوایی که هنگام اسکرول زیرش رد می‌شود نباید
            از فاصلهٔ بالای آن پیدا باشد. پس خودِ نوار گرد و جداست و یک لایهٔ
            هم‌رنگِ صفحه پشتش تا لبهٔ بالا کشیده می‌شود. */}
        <div className="sticky top-0 z-30 shrink-0 bg-cream-50 pt-3 lg:pt-4">
          <header className="flex h-14 items-center gap-3 rounded-2xl border border-gray-200 bg-white px-4 shadow-sm sm:px-6">
            <button
              type="button"
              onClick={() => setDrawerOpen(true)}
              aria-label="باز کردن منو"
              className="flex h-9 w-9 items-center justify-center rounded-xl text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-900 lg:hidden"
            >
              <svg viewBox="0 0 20 20" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
                <path d="M3 6h14M3 10h14M3 14h14" />
              </svg>
            </button>

            <p className="min-w-0 flex-1 truncate text-sm font-semibold text-gray-900">
              {active?.label ?? ""}
            </p>

            <div className="flex shrink-0 items-center gap-1">
              <span className="hidden sm:inline-flex">
                <ThemeToggle />
              </span>
              <NotificationBell />
              <ProfileMenu user={user} onLogout={handleLogout} />
            </div>
          </header>
        </div>

        <main
          id="main-content"
          tabIndex={-1}
          className="w-full flex-1 py-4 sm:py-6"
        >
          {/* ErrorBoundary با key مسیر دوباره mount می‌شود تا خطای یک صفحه با رفتن به
              صفحهٔ دیگر خودبه‌خود پاک شود، نه اینکه کاربر برای همیشه در حالت خطا بماند */}
          <ErrorBoundary key={location.pathname} title="مشکلی در نمایش این صفحه پیش آمد">
            {/* انتقال صفحه — cross-fade نرم با خروجِ صفحهٔ قبل (mode="wait") تا تعویض
                مسیرها به‌جای پرشِ ناگهانی، یکنواخت و آرام دیده شود */}
            <AnimatePresence mode="wait">
              <motion.div
                key={location.pathname}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -3 }}
                transition={{ duration: 0.18, ease: EASE_SOFT }}
              >
                <Outlet />
              </motion.div>
            </AnimatePresence>
          </ErrorBoundary>
        </main>

        <Footer />
      </div>

      {/* دستیار هوشمند — خودش تصمیم می‌گیرد دیده شود یا نه (بر پایهٔ /ai/status) */}
      <Copilot />
    </div>
  );
}
