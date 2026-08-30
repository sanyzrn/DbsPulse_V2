import type { Transition } from "motion/react";

/** منحنی easeOut نرم (کمی کندتر در انتها) — استاندارد انتقال‌های ظاهری برنامه */
export const EASE_SOFT = [0.22, 1, 0.36, 1] as const;

/** ترنزیشن پیش‌فرض ظاهر/محو شدن (fade/slide).
 *
 *  قبلاً ۰٫۷ ثانیه بود — «سنگین و لطیف»، ولی در عمل یعنی هر تعویض تب یک مکثِ
 *  محسوس. رابطِ کارِ روزمره باید *سریع* حس شود: ۰٫۳ ثانیه همان نرمی را می‌دهد
 *  بدون اینکه کاربر منتظر بسپارد. */
export const TRANSITION_SOFT: Transition = {
  duration: 0.3,
  ease: EASE_SOFT,
};

/** فنر نرم برای عناصر تعاملی — پاسخ‌گو ولی نه پرشی.
 *  سفتیِ بیشتر و جرمِ کمتر یعنی عنصر همان لحظه جواب می‌دهد و لرزش اضافه ندارد. */
export const SPRING_SOFT: Transition = {
  type: "spring",
  stiffness: 320,
  damping: 32,
  mass: 0.9,
};

/** انتقال ظریف محتوای تب‌ها — fade کوتاه با کمی حرکت عمودی.
 *  تب جایی است که کاربر زیاد سوئیچ می‌کند؛ انیمیشنِ طولانی این‌جا کندیِ صفحه
 *  تلقی می‌شود، نه کیفیت. */
export const TAB_TRANSITION = {
  initial: { opacity: 0, y: 4 },
  animate: { opacity: 1, y: 0 },
  transition: {
    duration: 0.22,
    ease: EASE_SOFT,
  },
} as const;
