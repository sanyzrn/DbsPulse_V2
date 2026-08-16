/** انتخاب تم — سه حالته.
 *
 * چیزی که این‌جا سنجیده می‌شود منطقِ *تصمیم* است، نه رنگ‌ها: کدام تم اعمال شود،
 * چه چیزی ذخیره شود، و اینکه یک ذخیره‌سازیِ خراب یا مسدود صفحه را نشکند.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  THEME_STORAGE_KEY,
  applyTheme,
  readStoredChoice,
  resolveTheme,
  storeChoice,
} from "./theme";

/** `prefers-color-scheme: dark` را روشن یا خاموش می‌کند. */
function setSystemDark(dark: boolean) {
  window.matchMedia = ((query: string) => ({
    matches: query.includes("dark") ? dark : false,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
}

describe("theme", () => {
  beforeEach(() => {
    window.localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
    setSystemDark(false);
  });
  afterEach(() => vi.restoreAllMocks());

  it("بدون انتخاب قبلی، «مثل سیستم» است", () => {
    expect(readStoredChoice()).toBe("system");
  });

  it("«مثل سیستم» تنظیم دستگاه را دنبال می‌کند", () => {
    setSystemDark(true);
    expect(resolveTheme("system")).toBe("dark");

    setSystemDark(false);
    expect(resolveTheme("system")).toBe("light");
  });

  it("انتخاب صریح بر تنظیم سیستم مقدم است", () => {
    // کسی که صراحتاً «روشن» را زده، انتظار ندارد چون دستگاهش شب‌مود است
    // برنامه تیره باز شود.
    setSystemDark(true);
    expect(resolveTheme("light")).toBe("light");

    setSystemDark(false);
    expect(resolveTheme("dark")).toBe("dark");
  });

  it("انتخاب صریح ذخیره می‌شود و «مثل سیستم» ذخیره‌شده را پاک می‌کند", () => {
    storeChoice("dark");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");
    expect(readStoredChoice()).toBe("dark");

    // برگشتن به «مثل سیستم» یعنی *نبودِ* انتخاب، نه ذخیرهٔ کلمهٔ "system" —
    // وگرنه دو حالتِ «انتخاب نکرده» و «سیستم را انتخاب کرده» فرق می‌کردند
    // بی‌آنکه تفاوتشان به کار کسی بیاید.
    storeChoice("system");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBeNull();
    expect(readStoredChoice()).toBe("system");
  });

  it("مقدار خراب در حافظه، به «مثل سیستم» برمی‌گردد", () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, "midnight-blue");
    expect(readStoredChoice()).toBe("system");
  });

  it("ذخیره‌سازیِ مسدود، برنامه را نمی‌شکند", () => {
    // حالت ناشناس یا حافظهٔ پر: تم همین نشست باید کار کند، فقط یادش نماند.
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });

    expect(readStoredChoice()).toBe("system");
    expect(() => storeChoice("dark")).not.toThrow();
  });

  it("تم را روی سند و روی رنگ نوار مرورگر می‌نشاند", () => {
    const meta = document.createElement("meta");
    meta.setAttribute("name", "theme-color");
    meta.setAttribute("content", "#b61615");
    document.head.appendChild(meta);

    applyTheme("dark");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    // نوار بالای مرورگر روی موبایل هم باید بچرخد، وگرنه یک نوار قرمزِ روشن
    // بالای صفحهٔ سرمه‌ای می‌ماند.
    expect(meta.getAttribute("content")).toBe("#0b0e17");

    applyTheme("light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    expect(meta.getAttribute("content")).toBe("#b61615");

    meta.remove();
  });
});
