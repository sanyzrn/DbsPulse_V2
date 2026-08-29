import { describe, expect, it } from "vitest";
import pkg from "../package.json";
import { APP_VERSION } from "./appInfo";

describe("APP_VERSION", () => {
  it("با نسخهٔ package.json یکی است", () => {
    // نسخه یک‌بار در `package.json` و یک‌بار این‌جا نوشته شده. کامنتِ خودِ
    // `appInfo.ts` می‌گوید همین دوجایی‌بودن قبلاً از هم دور افتاد؛ حالا اگر
    // دوباره دور بیفتد، این تست می‌شکند نه فوترِ نسخهٔ منتشرشده.
    expect(APP_VERSION).toBe(pkg.version);
  });
});
