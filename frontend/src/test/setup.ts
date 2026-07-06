import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// بدون globals در vitest، پاک‌سازی خودکار testing-library فعال نمی‌شود؛
// بین تست‌ها DOM باید خالی شود تا رندرها روی هم انباشته نشوند.
afterEach(() => {
  cleanup();
});
