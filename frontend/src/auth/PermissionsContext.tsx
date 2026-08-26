/** مجوزهای کاربر و وضعیت ماژول‌ها، یک‌بار برای کل برنامه (نیمهٔ دوم P0-03).
 *
 * جای پرچم‌های ثابتِ کد را می‌گیرد. `FEATURE_PERIODS_ENABLED` یک `const` در
 * `appInfo.ts` بود: روشن‌کردنش یعنی تغییر کد، بیلد و استقرار — و برای محصولی که
 * قرار است به چند سازمان فروخته شود، هر «این بخش را نمی‌خواهیم» یک انشعاب.
 *
 * قاعدهٔ نمایش: **گزینه‌ای که اجازه‌اش را نداری، بهتر است اصلاً نباشد تا اینکه
 * باشد و کلیکش ۴۰۳ بگیرد.** ولی این فقط پوشش UI است — گاردِ واقعی سمت سرور
 * است و باید بماند؛ پنهان‌کردن یک دکمه هیچ‌کس را از صدا زدن مستقیم API باز
 * نمی‌دارد.
 */
import { createContext, useContext, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../api/client";
import { useAuth } from "./AuthContext";

export type Capability =
  | "manage_users"
  | "manage_personnel"
  | "manage_ai"
  | "manage_capabilities"
  | "manage_scoring"
  | "manage_integrations"
  | "manage_modules"
  | "view_audit_log"
  | "view_diagnostics";

interface Permissions {
  capabilities: Capability[];
  modules: Record<string, boolean>;
}

interface PermissionsValue {
  can: (capability: Capability) => boolean;
  moduleEnabled: (key: string) => boolean;
  /** هنوز از سرور نیامده — تا آن لحظه چیزی که مشروط است نشان داده نمی‌شود */
  loading: boolean;
}

const PermissionsContext = createContext<PermissionsValue | undefined>(undefined);

export function PermissionsProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();

  const { data, isPending } = useQuery({
    queryKey: ["administration", "my-permissions", user?.id],
    queryFn: async () =>
      (await apiClient.get<Permissions>("/administration/my-permissions")).data,
    enabled: user != null,
    staleTime: 60_000,
  });

  const value: PermissionsValue = {
    can: (capability) => data?.capabilities.includes(capability) ?? false,
    // ماژولی که سرور دربارهٔ آن چیزی نگفته، روشن فرض می‌شود. برعکسش یعنی در
    // فاصلهٔ کوتاهِ بارگذاری، منو بخش‌های سالم را پنهان می‌کند و برنامه شکسته
    // به‌نظر می‌رسد.
    moduleEnabled: (key) => data?.modules[key] ?? true,
    loading: user != null && isPending,
  };

  return (
    <PermissionsContext.Provider value={value}>{children}</PermissionsContext.Provider>
  );
}

export function usePermissions(): PermissionsValue {
  const value = useContext(PermissionsContext);
  if (value === undefined) {
    throw new Error("usePermissions باید داخل PermissionsProvider استفاده شود");
  }
  return value;
}
