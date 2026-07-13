import type { Transition } from "motion/react";

/** منحنی easeOut نرم (کمی کندتر در انتها) — استاندارد انتقال‌های ظاهری برنامه */
export const EASE_SOFT = [0.22, 1, 0.36, 1] as const;

/** ترنزیشن پیش‌فرض ظاهر/محو شدن (fade/slide) — *** نرم‌تر و با مکث بیشتر *** */
export const TRANSITION_SOFT: Transition = { 
  duration: 0.7, // (از 0.32 به 0.7) تقریبا دو برابر شد تا حس سنگینی و لطافت کامل بدهد
  ease: EASE_SOFT 
};

/** فنر نرم برای عناصر تعاملی — *** کندتر، سنگین‌تر و بدون پرش اضافه *** */
export const SPRING_SOFT: Transition = {
  type: "spring",
  stiffness: 150,   // (از 240 به 150) سفتی کمتر = کندتر و کشسان‌تر
  damping: 35,       // (از 30 به 35) میرایی بیشتر = نرم‌تر و زودتر متوقف می‌شود
  mass: 1.2,         // (از 0.7 به 1.2) جرم بیشتر = سنگین‌تر و کندتر حرکت می‌کند
};

/** انتقال ظریف محتوای تب‌ها — fade نرم با کمی حرکت عمودی و *** زمان بیشتر *** */
export const TAB_TRANSITION = {
  initial: { opacity: 0, y: 6 },
  animate: { opacity: 1, y: 0 },
  transition: { 
    duration: 0.5,  // (از 0.28 به 0.55) تقریبا دو برابر
    ease: EASE_SOFT 
  },
} as const;