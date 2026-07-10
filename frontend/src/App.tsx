import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { FEATURE_PERIODS_ENABLED } from "./appInfo";
import { useAuth } from "./auth/AuthContext";
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
    <div className="rounded-2xl border border-gray-100 bg-white p-10 text-center shadow-card">
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

function HomeRedirect() {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  const targetByRole: Record<string, string> = {
    hr: "/hr/personnel",
    unit_supervisor: "/supervisor",
    deputy: "/deputy",
    ceo: "/ceo",
    employee: "/me",
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
            <Route path="/evaluations/:id" element={<EvaluationDetailPage />} />

            <Route element={<ProtectedRoute allowedRoles={["hr"]} />}>
              <Route path="/hr/personnel" element={<PersonnelPage />} />
              <Route path="/hr/users" element={<UsersPage />} />
              <Route path="/hr/indicators" element={<IndicatorsPage />} />
              <Route path="/hr/queue" element={<QueuePage />} />
              <Route
                path="/hr/periods"
                element={
                  FEATURE_PERIODS_ENABLED ? <PeriodsPage /> : <DisabledFeature title="دوره‌های ارزیابی" />
                }
              />
              <Route path="/hr/improvement-plans" element={<ImprovementPlansPage />} />
              <Route path="/hr/improvement-plans/:id" element={<ImprovementPlanDetailPage />} />
              <Route path="/hr/dashboard" element={<DashboardPage />} />
              <Route path="/hr/audit-log" element={<AuditLogPage />} />
            </Route>

            <Route element={<ProtectedRoute allowedRoles={["unit_supervisor"]} />}>
              <Route path="/supervisor" element={<SupervisorHomePage />} />
            </Route>

            <Route element={<ProtectedRoute allowedRoles={["deputy"]} />}>
              <Route path="/deputy" element={<DeputyHomePage />} />
            </Route>

            <Route element={<ProtectedRoute allowedRoles={["ceo"]} />}>
              <Route path="/ceo" element={<CeoHomePage />} />
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
