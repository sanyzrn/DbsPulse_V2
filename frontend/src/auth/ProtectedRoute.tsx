import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "./AuthContext";
import { usePermissions, type Capability } from "./PermissionsContext";
import type { UserRole } from "../types";

/** گاردِ مسیر: نقش، یا مجوز، یا هر دو.
 *
 *  `anyCapability` برای صفحه‌هایی است که کارِ روزمرهٔ یک نقش‌اند ولی مدیر سامانه
 *  هم باید به آن‌ها برسد. تا امروز فقط `allowedRoles` بود، و نتیجه‌اش این بود که
 *  حساب مدیر سامانه مجوزِ ساخت حساب را داشت ولی صفحهٔ «کاربران» او را به خانه
 *  برمی‌گرداند — سرور اجازه می‌داد و رابط نمی‌گذاشت.
 */
export function ProtectedRoute({
  allowedRoles,
  anyCapability,
}: {
  allowedRoles?: UserRole[];
  anyCapability?: Capability[];
}) {
  const { user, loading } = useAuth();
  const { can, loading: permissionsLoading } = usePermissions();

  if (loading) {
    return <div className="flex min-h-screen items-center justify-center">در حال بارگذاری…</div>;
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  if (allowedRoles || anyCapability) {
    const byRole = allowedRoles?.includes(user.role) ?? false;
    // تا وقتی مجوزها نرسیده‌اند نمی‌شود «ندارد» گفت؛ وگرنه یک رفرشِ ساده کاربرِ
    // مجازِ مجوزدار را به صفحهٔ خانه پرت می‌کند.
    if (!byRole && anyCapability && permissionsLoading) {
      return <div className="flex min-h-screen items-center justify-center">در حال بارگذاری…</div>;
    }
    const byCapability = anyCapability?.some(can) ?? false;
    if (!byRole && !byCapability) return <Navigate to="/" replace />;
  }
  return <Outlet />;
}
