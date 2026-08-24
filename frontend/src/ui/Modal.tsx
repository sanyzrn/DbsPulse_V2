import { useEffect, useRef, type ReactNode, type RefObject } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "motion/react";
import { EASE_SOFT, SPRING_SOFT } from "./motion";

const SIZES = {
  sm: "max-w-sm",
  md: "max-w-md",
  lg: "max-w-2xl",
} as const;

export type ModalSize = keyof typeof SIZES;

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

/** مودال استاندارد و مشترک برنامه.
 * با createPortal روی body رندر می‌شود تا موقعیت‌دهی fixed هیچ‌وقت تحت‌تأثیر
 * transform/overflow والدها قرار نگیرد (رفع باگ باز شدن مودال خارج از مرکز).
 * Escape و کلیک روی پس‌زمینه = بستن؛ اسکرول body هنگام باز بودن قفل می‌شود.
 * فوکوس هنگام باز شدن وارد مودال می‌شود، با Tab/Shift+Tab داخل آن قفل می‌ماند
 * (کاربر کیبورد/screen reader پشت مودال گم نمی‌شود) و هنگام بسته‌شدن به عنصری
 * که مودال را باز کرده برمی‌گردد.
 * انیمیشن با Framer Motion: scale + fade + spring. */
export function Modal({
  title,
  onClose,
  size = "md",
  children,
  footer,
  initialFocusRef,
}: {
  title: ReactNode;
  onClose: () => void;
  size?: ModalSize;
  children: ReactNode;
  footer?: ReactNode;
  /** عنصری که باید هنگام باز شدن فوکوس بگیرد؛ پیش‌فرض، اولین عنصر فوکوس‌پذیر.
   *
   * بدون این، هر کسی که می‌خواست فوکوس اولیه را جای دیگری ببرد مجبور بود در
   * effect خودش دوباره focus() صدا بزند — و دو جا که سرِ فوکوس دعوا کنند،
   * برنده‌اش به ترتیب اجرای effectها بستگی دارد، نه به تصمیم کسی. */
  initialFocusRef?: RefObject<HTMLElement | null>;
}) {
  const dialogRef = useRef<HTMLDivElement>(null);
  // onClose در ref نگه داشته می‌شود تا این effect فقط یک‌بار (هنگام mount) اجرا شود.
  // اگر به onClose وابسته بود، هر re-render والد (مثلاً هر کیبردِ فرمی که state آن
  // در والد است) این effect را دوباره اجرا و فوکوس را از فیلد در حال تایپ می‌دزدید.
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    document.body.style.overflow = "hidden";

    const dialog = dialogRef.current;
    const firstFocusable = dialog?.querySelector<HTMLElement>(FOCUSABLE_SELECTOR);
    (initialFocusRef?.current ?? firstFocusable ?? dialog)?.focus();

    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        onCloseRef.current();
        return;
      }
      if (e.key !== "Tab" || !dialog) return;
      const focusable = Array.from(dialog.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR));
      if (focusable.length === 0) {
        e.preventDefault();
        return;
      }
      const first = focusable[0]!;
      const last = focusable[focusable.length - 1]!;
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", onKeyDown);
      previouslyFocused?.focus();
    };
    // فقط یک‌بار هنگام mount اجرا می‌شود (onClose از طریق ref خوانده می‌شود)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return createPortal(
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-50 flex items-center justify-center bg-gray-900/40 p-4 backdrop-blur-md"
        onMouseDown={(e) => {
          if (e.target === e.currentTarget) onClose();
        }}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.28, ease: EASE_SOFT }}
      >
        <motion.div
          ref={dialogRef}
          role="dialog"
          aria-modal="true"
          aria-label={typeof title === "string" ? title : undefined}
          tabIndex={-1}
          className={`max-h-[90vh] w-full ${SIZES[size]} overflow-y-auto rounded-3xl bg-white shadow-float outline-none`}
          initial={{ opacity: 0, scale: 0.96, y: 12 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.97, y: 8 }}
          transition={SPRING_SOFT}
        >
          {/* بالای مودال: عنوان + دکمه بستن */}
          <div className="mb-3 flex items-start justify-between gap-3 border-b border-gray-100 px-6 pt-5 pb-4">
            <h3 className="text-base font-bold text-gray-900">{title}</h3>
            <button
              onClick={onClose}
              aria-label="بستن"
              className="-ml-1 rounded-lg p-1.5 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-700"
            >
              <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <path d="M5 5l10 10M15 5L5 15" />
              </svg>
            </button>
          </div>
          {/* بدونِ footer، همین بخش کفِ مودال است — و padding پایین لازم دارد.
              وگرنه آخرین سطرِ متن به لبهٔ کارت می‌چسبد؛ جایی که footer هست،
              خودش `py-4` دارد و فاصله را می‌دهد. */}
          <div className={`px-6 ${footer ? "" : "pb-6"}`}>
            {children}
          </div>
          {footer && (
            <div className="mt-5 flex justify-end gap-2 border-t border-gray-100 px-6 py-4">
              {footer}
            </div>
          )}
        </motion.div>
      </motion.div>
    </AnimatePresence>,
    document.body
  );
}
