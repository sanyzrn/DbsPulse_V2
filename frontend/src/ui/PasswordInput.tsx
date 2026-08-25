/** ورودی رمز با کلید نمایش/پنهان‌کردن.
 *
 * بدون این، کاربر رمزی را که تایپ می‌کند نمی‌بیند و تنها راه اطمینانش «تکرار رمز»
 * است — که وقتی هر دو نامرئی‌اند، فقط اشتباه را دو بار تکرار می‌کند.
 */
import { useId, useState, type InputHTMLAttributes } from "react";

/** ظاهرِ پیش‌فرض. جای چشم (`pl-11`) بخشی از همین قرارداد است: هر جا که این
 *  پایه عوض می‌شود، فضای چشم هم باید در نسخهٔ تازه باشد. */
const INPUT_CLASS =
  "w-full rounded-xl border border-gray-200 bg-gray-100 px-4 py-2.5 pl-11 text-sm text-gray-900 outline-none transition-colors duration-150 focus:border-gray-900 focus:bg-white";

interface PasswordInputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  /** جایگزینِ کاملِ کلاس‌های پایه — نه افزوده به آن‌ها.
   *
   *  `className` در Tailwind نمی‌تواند کلاس پایه را «لغو» کند: `py-3` و `py-2.5`
   *  هم‌وزن‌اند و برنده به ترتیبِ فایل CSS تعیین می‌شود، نه ترتیبِ نوشتن. پس
   *  فرمی که ظاهرِ دیگری می‌خواهد (مثل صفحهٔ ورود) پایه را *عوض* می‌کند. */
  baseClassName?: string;
  /** نمایشِ کنترل‌شده — برای فرمی که خودش هم به این حالت واکنش نشان می‌دهد. */
  visible?: boolean;
  onVisibleChange?: (visible: boolean) => void;
}

export function PasswordInput({
  className = "",
  baseClassName = INPUT_CLASS,
  visible: visibleProp,
  onVisibleChange,
  ...props
}: PasswordInputProps) {
  const [visibleState, setVisibleState] = useState(false);
  const visible = visibleProp ?? visibleState;
  const hintId = useId();

  function toggle() {
    const next = !visible;
    if (visibleProp === undefined) setVisibleState(next);
    onVisibleChange?.(next);
  }

  return (
    <div className="relative">
      <input
        {...props}
        type={visible ? "text" : "password"}
        // رمزِ نمایان نباید به تصحیح خودکار/پیشنهاد سپرده شود
        autoCapitalize="off"
        autoCorrect="off"
        spellCheck={false}
        className={`${baseClassName} ${className}`}
        aria-describedby={props["aria-describedby"] ?? hintId}
      />
      <button
        type="button"
        onClick={toggle}
        // tabIndex منفی نیست: کاربر صفحه‌کلید هم باید بتواند رمزش را ببیند
        aria-pressed={visible}
        aria-label={visible ? "پنهان‌کردن رمز عبور" : "نمایش رمز عبور"}
        title={visible ? "پنهان‌کردن رمز عبور" : "نمایش رمز عبور"}
        className="absolute left-2 top-1/2 -translate-y-1/2 rounded-lg p-1.5 text-gray-400 transition-colors hover:bg-gray-200/60 hover:text-gray-600"
      >
        {visible ? (
          <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
            <path d="M3 3l14 14" />
            <path d="M8.2 8.2a2.5 2.5 0 003.6 3.5" />
            <path d="M6.1 6.2C4.4 7.2 3 8.6 2 10c1.7 2.7 4.5 5 8 5 1.3 0 2.6-.3 3.7-.9" />
            <path d="M16.5 13c.6-.6 1.1-1.3 1.5-2-1.7-2.7-4.5-5-8-5-.6 0-1.2.1-1.8.2" />
          </svg>
        ) : (
          <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
            <path d="M2 10c1.7-2.7 4.5-5 8-5s6.3 2.3 8 5c-1.7 2.7-4.5 5-8 5s-6.3-2.3-8-5z" />
            <circle cx="10" cy="10" r="2.5" />
          </svg>
        )}
      </button>
    </div>
  );
}
