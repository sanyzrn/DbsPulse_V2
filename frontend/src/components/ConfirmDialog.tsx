import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";
import { Button } from "../ui/Button";
import { Modal } from "../ui/Modal";

interface ConfirmOptions {
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  /** پیامدی که کاربر باید *قبل از* کلیک بداند — نام فرد، نمرهٔ نهایی، آنچه برنمی‌گردد. */
  consequence?: ReactNode;
  /** کارِ بازگشت‌ناپذیر: دکمهٔ متمایز، و فوکوس روی «انصراف» نه «تأیید». */
  danger?: boolean;
}

type ConfirmFn = (options: ConfirmOptions) => Promise<boolean>;

const ConfirmContext = createContext<ConfirmFn | undefined>(undefined);

export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [options, setOptions] = useState<ConfirmOptions | null>(null);
  const resolver = useRef<((value: boolean) => void) | undefined>(undefined);
  const confirmButtonRef = useRef<HTMLButtonElement>(null);
  const cancelButtonRef = useRef<HTMLButtonElement>(null);

  const confirm = useCallback<ConfirmFn>((opts) => {
    setOptions(opts);
    return new Promise<boolean>((resolve) => {
      resolver.current = resolve;
    });
  }, []);

  const respond = useCallback((value: boolean) => {
    setOptions(null);
    resolver.current?.(value);
  }, []);

  // فوکوس اولیه روی دکمه‌ای که کاربر صفحه‌کلید احتمالاً می‌خواهد — با یک استثنا.
  //
  // برای کارِ بازگشت‌ناپذیر، فوکوس روی «تأیید» یعنی یک Enter کافی است تا پروندهٔ
  // کسی لغو شود. عادت هم کار خودش را می‌کند: بعد از بیست تأییدِ بی‌ضرر،
  // بیست‌ویکمی هم خودکار زده می‌شود. پس آن یکی باید یک قدم سخت‌تر باشد.
  //
  // به Modal سپرده می‌شود نه به یک effect این‌جا: پیش از این هر دو جا focus()
  // صدا می‌زدند و برنده به ترتیب اجرای effectها بستگی داشت — که در عمل یعنی
  // فوکوس روی دکمهٔ «بستن» می‌نشست، نه روی هیچ‌کدام از آن دو.

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      {options && (
        <Modal
          title={options.title}
          size="sm"
          initialFocusRef={options.danger ? cancelButtonRef : confirmButtonRef}
          onClose={() => respond(false)}
          footer={
            <>
              <Button ref={cancelButtonRef} variant="secondary" onClick={() => respond(false)}>
                {options.cancelLabel ?? "انصراف"}
              </Button>
              <Button
                ref={confirmButtonRef}
                variant={options.danger ? "danger" : "primary"}
                onClick={() => respond(true)}
              >
                {options.confirmLabel ?? "تأیید"}
              </Button>
            </>
          }
        >
          {options.description && <p className="text-sm leading-relaxed text-gray-600">{options.description}</p>}
          {options.consequence && (
            <div
              className={`mt-3 rounded-xl px-3.5 py-3 text-sm leading-relaxed ${
                options.danger
                  ? "bg-amber-50 text-amber-900 ring-1 ring-amber-200"
                  : "bg-gray-50 text-gray-700 ring-1 ring-gray-100"
              }`}
            >
              {options.consequence}
            </div>
          )}
        </Modal>
      )}
    </ConfirmContext.Provider>
  );
}

export function useConfirm(): ConfirmFn {
  const ctx = useContext(ConfirmContext);
  if (!ctx) throw new Error("useConfirm باید داخل ConfirmProvider استفاده شود");
  return ctx;
}
