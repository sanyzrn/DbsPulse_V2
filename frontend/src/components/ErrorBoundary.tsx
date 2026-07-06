import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  /** پیام سفارشی (اختیاری) — پیش‌فرض برای خطای کل صفحه/برنامه مناسب است */
  title?: string;
}

interface State {
  hasError: boolean;
}

/** آخرین خط دفاع در برابر خطای رندر ناخواسته (مثلاً null-dereference از دادهٔ
 * غیرمنتظرهٔ API). بدون این مرزبندی، هر چنین خطایی کل درخت React را به یک
 * صفحهٔ سفید خالی و بدون توضیح می‌برد — خطاهای async داخل event handler ها را
 * نمی‌گیرد (آن‌ها همان‌جا با try/catch مدیریت می‌شوند)، فقط خطاهای رندر را.
 * خطاهای React فقط با یک کلاس‌کامپوننت قابل گرفتن‌اند، نه با hook. */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: unknown, info: ErrorInfo) {
    console.error("Unhandled render error:", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-[50vh] flex-col items-center justify-center p-6 text-center">
          <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-red-50">
            <svg
              viewBox="0 0 24 24"
              className="h-7 w-7 text-red-500"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <circle cx="12" cy="12" r="10" />
              <path d="M12 8v4m0 4h.01" />
            </svg>
          </div>
          <h1 className="mb-1.5 text-base font-bold text-gray-900">
            {this.props.title ?? "مشکلی در نمایش این صفحه پیش آمد"}
          </h1>
          <p className="mb-5 max-w-sm text-sm text-gray-500">
            لطفاً صفحه را دوباره بارگذاری کنید. اگر مشکل ادامه داشت، با پشتیبانی تماس بگیرید.
          </p>
          <button
            onClick={() => window.location.reload()}
            className="rounded-xl bg-gradient-to-bl from-pulse-500 to-pulse-violet-600 px-5 py-2.5 text-sm font-medium text-white shadow-md shadow-pulse-500/20 transition-all duration-200 hover:shadow-lg"
          >
            بارگذاری مجدد
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
