import { describe, expect, it } from "vitest";
import { describeDevice } from "./SessionsPage";

describe("describeDevice", () => {
  it("مرورگر و سیستم‌عامل را از رشتهٔ خام بیرون می‌کشد", () => {
    expect(
      describeDevice(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36",
      ),
    ).toBe("Chrome روی ویندوز");
  });

  it("کروم را با سافاری اشتباه نمی‌گیرد", () => {
    // هر user-agent کرومی رشتهٔ «Safari» را هم دارد؛ ترتیب تشخیص باید کروم را اول بگیرد
    const chromeOnMac =
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36";
    expect(describeDevice(chromeOnMac)).toBe("Chrome روی مک");
  });

  it("سافاری واقعی را درست تشخیص می‌دهد", () => {
    const safari =
      "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/604.1";
    expect(describeDevice(safari)).toBe("Safari روی iOS");
  });

  it("اج را با کروم اشتباه نمی‌گیرد", () => {
    const edge =
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36 Edg/131.0";
    expect(describeDevice(edge)).toBe("Edge روی ویندوز");
  });

  it("نبودِ user-agent را صریح می‌گوید", () => {
    expect(describeDevice(null)).toBe("دستگاه نامشخص");
  });

  it("رشتهٔ ناشناخته را خودش نشان می‌دهد، نه «نامشخص»", () => {
    // دیدنِ رشتهٔ عجیب بهتر از پنهان‌کردنش است: همان چیزی است که کاربر باید
    // به آن مشکوک شود.
    expect(describeDevice("curl/8.4.0")).toBe("curl/8.4.0");
  });
});
