import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { Button } from "../ui/Button";
import { Modal } from "../ui/Modal";

interface ConfirmOptions {
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
}

type ConfirmFn = (options: ConfirmOptions) => Promise<boolean>;

const ConfirmContext = createContext<ConfirmFn | undefined>(undefined);

export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [options, setOptions] = useState<ConfirmOptions | null>(null);
  const resolver = useRef<((value: boolean) => void) | undefined>(undefined);
  const confirmButtonRef = useRef<HTMLButtonElement>(null);

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

  // فوکوس اولیه روی دکمه تأیید تا کاربر صفحه‌کلید سرگردان نشود
  useEffect(() => {
    if (options) confirmButtonRef.current?.focus();
  }, [options]);

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      {options && (
        <Modal
          title={options.title}
          size="sm"
          onClose={() => respond(false)}
          footer={
            <>
              <Button variant="secondary" onClick={() => respond(false)}>
                {options.cancelLabel ?? "انصراف"}
              </Button>
              <Button ref={confirmButtonRef} onClick={() => respond(true)}>
                {options.confirmLabel ?? "تأیید"}
              </Button>
            </>
          }
        >
          {options.description && <p className="text-sm text-gray-600">{options.description}</p>}
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
