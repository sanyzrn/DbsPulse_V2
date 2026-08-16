import { readFileSync } from "node:fs";
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// همان `define` که `vite.config.ts` دارد.
//
// vitest پیکربندی خودش را می‌خواند، پس بدون این خط `__APP_VERSION__` در تست
// تعریف‌نشده می‌ماند و هر فایلی که `appInfo` را وارد کند اصلاً بارگذاری نمی‌شود —
// و چون آن فایل «۰ تست» گزارش می‌شود، در شمارشِ کلی به‌چشم نمی‌آید.
const pkg = JSON.parse(readFileSync(new URL("./package.json", import.meta.url), "utf8"));

export default defineConfig({
  plugins: [react()],
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
  },
});
