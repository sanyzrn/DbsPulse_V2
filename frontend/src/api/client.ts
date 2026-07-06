import axios from "axios";

// توکن دسترسی فقط در حافظه نگه داشته می‌شود (نه localStorage) تا در صورت XSS قابل
// سرقت نباشد؛ refresh token هم فقط به‌صورت کوکی HttpOnly سمت سرور ست می‌شود.
// بعد از reload صفحه، AuthContext با یک فراخوانی /auth/refresh نشست را بازیابی می‌کند.
let accessToken: string | null = null;

export const authToken = {
  get: () => accessToken,
  set: (token: string | null) => {
    accessToken = token;
  },
};

export const apiClient = axios.create({ baseURL: "/api", withCredentials: true });

apiClient.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

let refreshPromise: Promise<string | null> | null = null;

async function refreshAccessTokenOnce(): Promise<string | null> {
  try {
    const { data } = await axios.post("/api/auth/refresh", null, { withCredentials: true });
    accessToken = data.access_token as string;
    return accessToken;
  } catch {
    accessToken = null;
    return null;
  }
}

/** درخواست‌های هم‌زمان یک refresh مشترک انجام می‌دهند (نه چندتای موازی). */
export function refreshAccessToken(): Promise<string | null> {
  refreshPromise =
    refreshPromise ??
    refreshAccessTokenOnce().finally(() => {
      refreshPromise = null;
    });
  return refreshPromise;
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    // خطای 401 خودِ مسیرهای auth (مثلاً رمز اشتباه هنگام login) نشانه انقضای نشست
    // نیست؛ نباید باعث refresh/ریدایرکت شود وگرنه پیام خطای فرم ورود از بین می‌رود.
    const isAuthEndpoint =
      typeof original?.url === "string" && original.url.startsWith("/auth/");
    if (error.response?.status === 401 && !original._retry && !isAuthEndpoint) {
      original._retry = true;
      const newToken = await refreshAccessToken();
      if (newToken) {
        original.headers.Authorization = `Bearer ${newToken}`;
        return apiClient(original);
      }
      if (window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

export function extractErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    // بک‌اند برای برخی خطاها (مثل ۴۰۹ ارزیابی تکراری) detail ساخت‌یافته می‌فرستد
    if (detail && typeof detail === "object" && typeof detail.message === "string") {
      return detail.message;
    }
  }
  return "خطایی غیرمنتظره رخ داد";
}

/** اگر خطا ۴۰۹ «ارزیابی باز موجود» باشد، شناسه همان پرونده را برمی‌گرداند. */
export function extractConflictEvaluationId(error: unknown): number | null {
  if (axios.isAxiosError(error) && error.response?.status === 409) {
    const detail = error.response.data?.detail;
    if (detail && typeof detail === "object" && typeof detail.evaluation_id === "number") {
      return detail.evaluation_id;
    }
  }
  return null;
}
