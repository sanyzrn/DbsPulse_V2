import { lazy, Suspense } from "react";
import { Navigate, Route, Routes, useParams } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import { usePermissions } from "./auth/PermissionsContext";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { Layout } from "./components/Layout";
import { LoginPage } from "./pages/LoginPage";

// صفحه‌ها به‌صورت lazy بارگذاری می‌شوند تا باندل اولیه سبک بماند؛ به‌ویژه صفحه‌های
// نمودارمحور (داشبورد HR/پروفایل پرسنل) که Recharts سنگین را فقط هنگام نیاز می‌آورند.
// صفحهٔ ورود عمداً eager است تا اولین نمایش بدون رفت‌وبرگشت اضافه باشد.
const VerifyPage = lazy(() => import("./pages/VerifyPage").then((m) => ({ default: m.VerifyPage })));
const ChangePasswordPage = lazy(() =>
  import("./pages/ChangePasswordPage").then((m) => ({ default: m.ChangePasswordPage }))
);
const NotificationPreferencesPage = lazy(() =>
  import("./pages/NotificationPreferencesPage").then((m) => ({
    default: m.NotificationPreferencesPage,
  }))
);
const SessionsPage = lazy(() =>
  import("./pages/SessionsPage").then((m) => ({ default: m.SessionsPage }))
);
const EvaluationDetailPage = lazy(() =>
  import("./pages/EvaluationDetailPage").then((m) => ({ default: m.EvaluationDetailPage }))
);
const PersonnelPage = lazy(() =>
  import("./pages/hr/PersonnelPage").then((m) => ({ default: m.PersonnelPage }))
);
const UsersPage = lazy(() => import("./pages/hr/UsersPage").then((m) => ({ default: m.UsersPage })));
const IndicatorsPage = lazy(() =>
  import("./pages/hr/IndicatorsPage").then((m) => ({ default: m.IndicatorsPage }))
);
const QueuePage = lazy(() => import("./pages/hr/QueuePage").then((m) => ({ default: m.QueuePage })));
const PeriodsPage = lazy(() =>
  import("./pages/hr/PeriodsPage").then((m) => ({ default: m.PeriodsPage }))
);
const ScoringSchemesPage = lazy(() =>
  import("./pages/hr/ScoringSchemesPage").then((m) => ({ default: m.ScoringSchemesPage }))
);
const AdministrationPage = lazy(() =>
  import("./pages/hr/AdministrationPage").then((m) => ({ default: m.AdministrationPage }))
);
const DashboardPage = lazy(() =>
  import("./pages/hr/DashboardPage").then((m) => ({ default: m.DashboardPage }))
);
const AuditLogPage = lazy(() =>
  import("./pages/hr/AuditLogPage").then((m) => ({ default: m.AuditLogPage }))
);
const ImprovementPlansPage = lazy(() =>
  import("./pages/hr/ImprovementPlansPage").then((m) => ({ default: m.ImprovementPlansPage }))
);
const ImprovementPlanDetailPage = lazy(() =>
  import("./pages/hr/ImprovementPlanDetailPage").then((m) => ({
    default: m.ImprovementPlanDetailPage,
  }))
);
const MyScoringPage = lazy(() =>
  import("./pages/supervisor/MyScoringPage").then((m) => ({ default: m.MyScoringPage }))
);
const ExecutivePage = lazy(() =>
  import("./pages/ceo/ExecutivePage").then((m) => ({ default: m.ExecutivePage }))
);
const SupervisorHomePage = lazy(() =>
  import("./pages/supervisor/SupervisorHomePage").then((m) => ({ default: m.SupervisorHomePage }))
);
const DeputyHomePage = lazy(() =>
  import("./pages/deputy/DeputyHomePage").then((m) => ({ default: m.DeputyHomePage }))
);
const CeoHomePage = lazy(() =>
  import("./pages/ceo/CeoHomePage").then((m) => ({ default: m.CeoHomePage }))
);
const MyEvaluationsPage = lazy(() =>
  import("./pages/employee/MyEvaluationsPage").then((m) => ({ default: m.MyEvaluationsPage }))
);

/** اسکلتون سبک هنگام دانلود chunk هر صفحه — جای پرش سفید، همان زبان بصری skeleton. */
function PageFallback() {
  return (
    <div className="space-y-4">
      <div className="skeleton h-16" />
      <div className="skeleton h-64" />
    </div>
  );
}

/** جای‌گزین بخش‌های موقتاً غیرفعال — به‌جای ۴۰۴ یک پیام دوستانه نشان می‌دهد. */
function DisabledFeature({ title }: { title: string }) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-10 text-center">
      <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-gray-100 text-gray-400">
        <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="9" />
          <path d="M8 12h8" />
        </svg>
      </div>
      <h1 className="text-lg font-bold text-gray-900">{title}</h1>
      <p className="mt-1 text-sm text-gray-500">این بخش فعلاً غیرفعال است.</p>
    </div>
  );
}

/** نشانی قدیمیِ جزئیات برنامهٔ بهبود، با حفظ شناسه. */
export function LegacyImprovementPlanRedirect() {
  const { id } = useParams();
  return <Navigate to={`/improvement-plans/${id}`} replace />;
}

/** مسیری که پشت یک ماژول قابل خاموش‌شدن است.
 *
 * جای `FEATURE_PERIODS_ENABLED` را می‌گیرد: آن یک ثابت در کد بود و روشن‌کردنش
 * تغییر کد و استقرار می‌خواست. حالا از دیتابیس می‌آید (نیمهٔ دوم P0-03).
 */
function ModuleRoute({
  module,
  title,
  children,
}: {
  module: string;
  title: string;
  children: React.ReactNode;
}) {
  const { moduleEnabled, loading } = usePermissions();
  if (loading) return <PageFallback />;
  return moduleEnabled(module) ? <>{children}</> : <DisabledFeature title={title} />;
}

function HomeRedirect() {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  const targetByRole: Record<string, string> = {
    hr: "/hr/dashboard",
    unit_supervisor: "/supervisor",
    deputy: "/deputy",
    ceo: "/ceo",
    employee: "/me",
    // پشتیبانی فنی هیچ صف کاری‌ای ندارد؛ صفحهٔ فرودش همان جایی است که کار می‌کند
    support: "/administration",
  };
  return <Navigate to={targetByRole[user.role] ?? "/login"} replace />;
}

function App() {
  return (
    <Suspense fallback={<PageFallback />}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        {/* تأیید اصالت سند: عمومی و بدون احراز هویت (هدف QR نسخه چاپی).
            مقدار :token یک رشتهٔ تصادفی است، نه evaluation_code ترتیبی — عمداً، تا
            endpoint عمومی /api/verify قابل شمارش نباشد (رجوع به backend/app/api/routers/verify.py). */}
        <Route path="/verify/:token" element={<VerifyPage />} />

        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            <Route path="/" element={<HomeRedirect />} />
            <Route path="/change-password" element={<ChangePasswordPage />} />
            <Route path="/sessions" element={<SessionsPage />} />
            <Route path="/notification-preferences" element={<NotificationPreferencesPage />} />
            <Route path="/evaluations/:id" element={<EvaluationDetailPage />} />
            {/* برنامه‌های بهبود پشت گاردِ hr نیستند چون «مسئول پیگیری» هم باید
                بتواند برنامهٔ سپرده‌شده به خودش را باز کند — زمان‌بند دقیقاً همین
                لینک را برایش می‌فرستد (P1-10). محدودیت واقعی سمت سرور است: غیرِ
                HR فقط برنامه‌های خودش را می‌بیند و فقط اهداف را تیک می‌زند.
                به همین دلیل مسیر هم زیر /hr/ نیست: نشانیِ صفحه‌ای که مسئول واحد و
                معاونت هر روز باز می‌کنند نباید بگوید مالِ منابع انسانی است. */}
            <Route path="/improvement-plans" element={<ImprovementPlansPage />} />
            <Route path="/improvement-plans/:id" element={<ImprovementPlanDetailPage />} />
            {/* نشانی قدیمی: اعلان‌های ارسال‌شده و بوکمارک‌های موجود نباید بشکنند */}
            <Route path="/hr/improvement-plans" element={<Navigate to="/improvement-plans" replace />} />
            <Route
              path="/hr/improvement-plans/:id"
              element={<LegacyImprovementPlanRedirect />}
            />

            <Route element={<ProtectedRoute allowedRoles={["hr"]} />}>
              <Route path="/hr/personnel" element={<PersonnelPage />} />
              <Route path="/hr/users" element={<UsersPage />} />
              <Route path="/hr/indicators" element={<IndicatorsPage />} />
              <Route path="/hr/queue" element={<QueuePage />} />
              <Route path="/hr/periods" element={<ModuleRoute module="periods" title="دوره‌های ارزیابی"><PeriodsPage /></ModuleRoute>} />
              <Route path="/hr/scoring-schemes" element={<ScoringSchemesPage />} />
              <Route path="/hr/dashboard" element={<DashboardPage />} />
            </Route>

            {/* مدیریت سامانه پشت گاردِ hr نیست: حساب «پشتیبانی فنی» نقش hr
                ندارد و باید به این‌جا برسد. محدودیت واقعی مجوز است، که هم
                سمت سرور اعمال می‌شود و هم داخل خودِ صفحه. */}
            <Route path="/administration" element={<AdministrationPage />} />
            {/* لاگ ممیزی پشت گاردِ نقش نیست، چون دیگر به نقش گره نخورده:
                `view_audit_log` کل لاگ را می‌دهد و `view_diagnostics` فقط
                رویدادهای سامانه‌ای را. دامنهٔ دید را سرور تعیین می‌کند. */}
            <Route path="/hr/audit-log" element={<AuditLogPage />} />

            <Route element={<ProtectedRoute allowedRoles={["unit_supervisor"]} />}>
              <Route path="/supervisor" element={<SupervisorHomePage />} />
            </Route>

            <Route element={<ProtectedRoute allowedRoles={["deputy"]} />}>
              <Route path="/deputy" element={<DeputyHomePage />} />
            </Route>

            <Route element={<ProtectedRoute allowedRoles={["ceo"]} />}>
              <Route path="/ceo" element={<CeoHomePage />} />
            </Route>

            {/* P2-01 — تحلیل برای نقش‌هایی غیر از منابع انسانی.
                «آینهٔ ارزیاب» برای کسانی که نمره می‌دهند (مسئول واحد و معاونت، که
                در مسیر «مدیر» خودش نمره‌دهندهٔ اول است)؛ «تحلیل سازمان» برای
                کسانی که تصمیم می‌گیرند. معاونت در هر دو گروه است. */}
            <Route element={<ProtectedRoute allowedRoles={["unit_supervisor", "deputy"]} />}>
              <Route path="/my-scoring" element={<MyScoringPage />} />
            </Route>

            <Route element={<ProtectedRoute allowedRoles={["ceo", "deputy"]} />}>
              <Route path="/executive" element={<ExecutivePage />} />
            </Route>

            <Route element={<ProtectedRoute allowedRoles={["employee"]} />}>
              <Route path="/me" element={<MyEvaluationsPage />} />
            </Route>
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}

export default App;
