import { useCallback, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

/** راهنمای شناور روی هاور — برای وقتی که برچسب روی صفحه جا نمی‌شود.
 *
 *  چرا `title` بومی کافی نبود: مرورگر آن را با حدود یک ثانیه تأخیر، در گوشهٔ
 *  اشاره‌گر و با فونت سیستم نشان می‌دهد — یعنی در منوی جمع‌شده کاربر یک ثانیه
 *  روی نشانه می‌ماند تا بفهمد کدام است. این‌جا بی‌درنگ، کنارِ خود نشانه و با
 *  همان تایپوگرافی بقیهٔ سامانه ظاهر می‌شود.
 *
 *  چرا portal و مختصات ثابت: منوی جمع‌شده یک ستونِ باریکِ `overflow-y-auto`
 *  است. حبابی که داخلش بنشیند از لبه بریده می‌شود؛ پس بیرون از آن، روی
 *  `document.body` می‌نشیند و جایش از موقعیتِ واقعیِ نشانه حساب می‌شود.
 */
export function Tooltip({
  label,
  enabled = true,
  children,
  className = "",
}: {
  label: ReactNode;
  /** در منوی باز، برچسب کنار نشانه دیده می‌شود و حباب فقط تکرار است. */
  enabled?: boolean;
  children: ReactNode;
  className?: string;
}) {
  const anchor = useRef<HTMLDivElement>(null);
  const [at, setAt] = useState<{ top: number; left: number } | null>(null);

  const show = useCallback(() => {
    if (!enabled || !anchor.current) return;
    const rect = anchor.current.getBoundingClientRect();
    // سمتِ چپِ نشانه: ستون در RTL به لبهٔ راستِ صفحه چسبیده، پس تنها فضای
    // خالی سمت چپ است.
    setAt({ top: rect.top + rect.height / 2, left: rect.left - 10 });
  }, [enabled]);

  const hide = useCallback(() => setAt(null), []);

  return (
    <div
      ref={anchor}
      className={className}
      onPointerEnter={show}
      onPointerLeave={hide}
      onFocus={show}
      onBlur={hide}
    >
      {children}
      {at !== null &&
        createPortal(
          <span
            role="tooltip"
            style={{ top: at.top, left: at.left, transform: "translate(-100%, -50%)" }}
            className="pointer-events-none fixed z-[70] whitespace-nowrap rounded-xl bg-charcoal-900 px-2.5 py-1.5 text-xs font-medium text-white shadow-lg"
          >
            {label}
          </span>,
          document.body,
        )}
    </div>
  );
}
