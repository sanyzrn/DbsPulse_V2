import { useSyncExternalStore } from "react";

/** آیا این media query الان برقرار است.
 *
 * جایگزین الگوی رایجِ «هر دو نسخه را رندر کن و یکی را با CSS پنهان کن». آن الگو
 * برای نمایش بی‌خطر است، ولی وقتی محتوا *فرم* است دو مشکل واقعی می‌سازد: هر
 * پرسش دو کنترلِ ورودی دارد (خوانندهٔ صفحه هر شاخص را دوبار می‌خواند اگر CSS
 * نرسد)، و هر جست‌وجوی بر اساس برچسب — چه در تست، چه با ابزار کمکی — مبهم
 * می‌شود.
 *
 * با useSyncExternalStore مقدار اولیه *همزمان* از matchMedia خوانده می‌شود، پس
 * پرشِ اولین رندر (که با useEffect پیش می‌آید) وجود ندارد.
 */
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (onChange) => {
      // محیط‌های بدون matchMedia (jsdomِ بدون polyfill، رندر سمت سرور)
      if (typeof window === "undefined" || !window.matchMedia) return () => {};
      const list = window.matchMedia(query);
      list.addEventListener("change", onChange);
      return () => list.removeEventListener("change", onChange);
    },
    () => {
      if (typeof window === "undefined" || !window.matchMedia) return false;
      return window.matchMedia(query).matches;
    },
    // getServerSnapshot: در نبودِ پنجره، «باریک نیست» فرض می‌شود
    () => false,
  );
}

/** هم‌مرز با نقطهٔ شکست `md` در Tailwind — تا CSS و JS یک جا را مرز بدانند. */
export const NARROW_QUERY = "(max-width: 767px)";
