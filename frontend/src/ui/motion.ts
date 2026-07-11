import type { Transition } from "motion/react";

/** منحنی easeOut نرم (کمی کندتر در انتها) — استاندارد انتقال‌های ظاهری برنامه.
 * مطابق راهنما: easeOut یا spring نرم، بازهٔ ۱۵۰ تا ۳۰۰ میلی‌ثانیه. */
export const EASE_SOFT = [0.22, 1, 0.36, 1] as const;

/** ترنزیشن پیش‌فرض ظاهر/محو شدن عناصر (fade/slide) — کمی کندتر و نرم‌تر. */
export const TRANSITION_SOFT: Transition = { duration: 0.32, ease: EASE_SOFT };

/** فنر نرم برای عناصر تعاملی (مودال، تب، اسلایدر) — نرم‌تر و بدون پرشِ اضافه. */
export const SPRING_SOFT: Transition = {
  type: "spring",
  stiffness: 240,
  damping: 30,
  mass: 0.7,
};

/** انتقال ظریف محتوای تب‌ها هنگام جابه‌جایی — fade نرم با کمی حرکت عمودی. */
export const TAB_TRANSITION = {
  initial: { opacity: 0, y: 6 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.28, ease: EASE_SOFT },
} as const;
