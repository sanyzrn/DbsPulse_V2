/** انتخاب تم: روشن، شب، یا «مثل سیستم».
 *
 * سه حالت است نه دو تا. «مثل سیستم» پیش‌فرض است چون کسی که کل دستگاهش را تیره
 * کرده، انتظار ندارد این یکی برنامه روشن باز شود — و کسی که صراحتاً انتخاب
 * کرده، انتظار دارد انتخابش بماند حتی اگر سیستم عوض شود.
 *
 * `data-theme` روی `<html>` می‌نشیند و بقیهٔ کار را CSS می‌کند (`index.css`).
 * در حالت «مثل سیستم» هم مقدار *محاسبه‌شده* نوشته می‌شود، نه اینکه خالی بماند:
 * یک منبعِ حقیقت برای CSS ساده‌تر از دو مسیر (media query و data-attribute) است
 * که باید همیشه با هم بخوانند.
 */
export type ThemeChoice = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

export const THEME_STORAGE_KEY = "nafas-hr:theme";

/** رنگ نوار مرورگر/سیستم‌عامل برای هر تم — با زمینهٔ صفحه یکی است. */
const THEME_COLOR: Record<ResolvedTheme, string> = {
  light: "#b61615",
  dark: "#0b0e17",
};

export function readStoredChoice(): ThemeChoice {
  try {
    const raw = window.localStorage.getItem(THEME_STORAGE_KEY);
    return raw === "light" || raw === "dark" ? raw : "system";
  } catch {
    return "system";
  }
}

export function systemPrefersDark(): boolean {
  return typeof window !== "undefined" && !!window.matchMedia
    ? window.matchMedia("(prefers-color-scheme: dark)").matches
    : false;
}

export function resolveTheme(choice: ThemeChoice): ResolvedTheme {
  if (choice === "system") return systemPrefersDark() ? "dark" : "light";
  return choice;
}

/** تم را روی سند اعمال می‌کند. تنها جایی که به DOM دست می‌زند. */
export function applyTheme(resolved: ResolvedTheme): void {
  document.documentElement.setAttribute("data-theme", resolved);
  // نوار بالای مرورگر روی موبایل و رنگ پنجره در حالت نصب‌شده هم باید بچرخد،
  // وگرنه یک نوار قرمزِ روشن بالای صفحهٔ سرمه‌ای می‌ماند.
  document
    .querySelector('meta[name="theme-color"]')
    ?.setAttribute("content", THEME_COLOR[resolved]);
}

export function storeChoice(choice: ThemeChoice): void {
  try {
    if (choice === "system") window.localStorage.removeItem(THEME_STORAGE_KEY);
    else window.localStorage.setItem(THEME_STORAGE_KEY, choice);
  } catch {
    // ذخیره‌سازی مسدود (حالت ناشناس) — تم همین نشست کار می‌کند و فقط یادش نمی‌ماند.
  }
}
