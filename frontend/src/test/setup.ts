import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// بدون globals در vitest، پاک‌سازی خودکار testing-library فعال نمی‌شود؛
// بین تست‌ها DOM باید خالی شود تا رندرها روی هم انباشته نشوند.
afterEach(() => {
  cleanup();
});

// jsdom پیاده‌سازی matchMedia ندارد. بدون این، هر کامپوننتی که به عرض صفحه واکنش
// نشان می‌دهد (فرم امتیازدهی: کارت روی موبایل، جدول روی دسکتاپ) در تست می‌ترکد.
// پیش‌فرض «برقرار نیست» یعنی تست‌ها نسخهٔ پهن را می‌بینند؛ تستِ نسخهٔ باریک خودش
// این مقدار را عوض می‌کند.
if (!window.matchMedia) {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
}
