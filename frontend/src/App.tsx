import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth/AuthContext";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { Layout } from "./components/Layout";
import { LoginPage } from "./pages/LoginPage";
import { VerifyPage } from "./pages/VerifyPage";
import { ChangePasswordPage } from "./pages/ChangePasswordPage";
import { EvaluationDetailPage } from "./pages/EvaluationDetailPage";
import { PersonnelPage } from "./pages/hr/PersonnelPage";
import { UsersPage } from "./pages/hr/UsersPage";
import { IndicatorsPage } from "./pages/hr/IndicatorsPage";
import { QueuePage } from "./pages/hr/QueuePage";
import { PeriodsPage } from "./pages/hr/PeriodsPage";
import { DashboardPage } from "./pages/hr/DashboardPage";
import { AuditLogPage } from "./pages/hr/AuditLogPage";
import { ImprovementPlansPage } from "./pages/hr/ImprovementPlansPage";
import { ImprovementPlanDetailPage } from "./pages/hr/ImprovementPlanDetailPage";
import { SupervisorHomePage } from "./pages/supervisor/SupervisorHomePage";
import { DeputyHomePage } from "./pages/deputy/DeputyHomePage";
import { CeoHomePage } from "./pages/ceo/CeoHomePage";
import { MyEvaluationsPage } from "./pages/employee/MyEvaluationsPage";

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
            <Route path="/hr/periods" element={<PeriodsPage />} />
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
  );
}

export default App;
