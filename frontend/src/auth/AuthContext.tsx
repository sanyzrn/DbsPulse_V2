import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { apiClient, authToken, refreshAccessToken } from "../api/client";
import type { CurrentUser } from "../types";
import { clearAppCaches } from "../pwa";

interface AuthContextValue {
  user: CurrentUser | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  /** بعد از عملیاتی مثل تغییر رمز، اطلاعات کاربر را دوباره از سرور می‌خواند. */
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchMe = useCallback(async () => {
    try {
      // بعد از reload توکن دسترسی در حافظه نیست؛ با کوکی HttpOnly نشست را بازیابی می‌کنیم
      if (!authToken.get()) {
        const token = await refreshAccessToken();
        if (!token) {
          setUser(null);
          return;
        }
      }
      const { data } = await apiClient.get<CurrentUser>("/auth/me");
      setUser(data);
    } catch {
      authToken.set(null);
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMe();
  }, [fetchMe]);

  const login = useCallback(async (username: string, password: string) => {
    const { data } = await apiClient.post("/auth/login", { username, password });
    authToken.set(data.access_token);
    await fetchMe();
  }, [fetchMe]);

  const logout = useCallback(() => {
    // ابطال نشست سمت سرور (پاک‌شدن کوکی refresh)؛ خطای شبکه مانع خروج محلی نمی‌شود
    apiClient.post("/auth/logout").catch(() => {});
    authToken.set(null);
    setUser(null);
    // کش سرویس‌ورکر فقط پوستهٔ برنامه است و دادهٔ کاربر ندارد (پاسخ‌های /api اصلاً
    // کش نمی‌شوند)، ولی روی دستگاه مشترک، «هیچ ردی نماند» چیزی است که کاربر حق
    // دارد از دکمهٔ خروج انتظار داشته باشد.
    void clearAppCaches();
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, refreshUser: fetchMe }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth باید داخل AuthProvider استفاده شود");
  return ctx;
}
