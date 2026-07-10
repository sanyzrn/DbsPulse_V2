import type { Transition } from "motion/react";

/** منحنی easeOut نرم (کمی کندتر در انتها) — استاندارد انتقال‌های ظاهری برنامه.
 * مطابق راهنما: easeOut یا spring نرم، بازهٔ ۱۵۰ تا ۳۰۰ میلی‌ثانیه. */
export const EASE_SOFT = [0.22, 1, 0.36, 1] as const;

/** ترنزیشن پیش‌فرض ظاهر/محو شدن عناصر (fade/slide). */
export const TRANSITION_SOFT: Transition = { duration: 0.24, ease: EASE_SOFT };

/** فنر نرم برای عناصر تعاملی (مودال، تب، اسلایدر) — بدون پرشِ اضافه. */
export const SPRING_SOFT: Transition = {
  type: "spring",
  stiffness: 320,
  damping: 32,
  mass: 0.6,
};
