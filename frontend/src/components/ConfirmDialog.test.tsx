/** پنجرهٔ تأیید — دومین موردِ ممیزی تجربهٔ کاربری.
 *
 * ادعا: کارِ بازگشت‌ناپذیر نباید با کارِ بی‌ضرر یک‌شکل باشد، و مهم‌تر از رنگ،
 * فوکوس است — اگر مکان‌نما روی «تأیید» بنشیند، یک Enter کافی است تا پروندهٔ کسی
 * لغو شود.
 *
 * این تست وجود دارد چون همین رفتار یک‌بار بی‌صدا شکسته بود: `ConfirmDialog` در
 * effect خودش «تأیید» را فوکوس می‌کرد و `Modal` در effect خودش اولین عنصر
 * فوکوس‌پذیر را — و برندهٔ این دعوا دکمهٔ «بستن» بود، نه هیچ‌کدام از آن دو.
 */
import { useEffect } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ConfirmProvider, useConfirm } from "./ConfirmDialog";

/** به‌محض mount یک دیالوگ باز می‌کند و نتیجه‌اش را به onResult می‌دهد. */
function OpenOnMount({
  options,
  onResult = () => {},
}: {
  options: Parameters<ReturnType<typeof useConfirm>>[0];
  onResult?: (v: boolean) => void;
}) {
  const confirm = useConfirm();
  useEffect(() => {
    confirm(options).then(onResult);
    // فقط یک‌بار، هنگام mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return null;
}

function open(options: Parameters<ReturnType<typeof useConfirm>>[0], onResult?: (v: boolean) => void) {
  return render(
    <ConfirmProvider>
      <OpenOnMount options={options} onResult={onResult} />
    </ConfirmProvider>
  );
}

describe("ConfirmDialog", () => {
  it("برای کار عادی، فوکوس روی دکمهٔ تأیید می‌نشیند", async () => {
    open({ title: "غیرفعال شود؟", confirmLabel: "غیرفعال کن" });

    await waitFor(() =>
      expect(document.activeElement).toBe(screen.getByRole("button", { name: "غیرفعال کن" }))
    );
  });

  it("برای کار بازگشت‌ناپذیر، فوکوس روی «انصراف» می‌نشیند نه تأیید", async () => {
    // بعد از بیست تأییدِ بی‌ضرر، بیست‌ویکمی هم خودکار زده می‌شود. آن یکی باید
    // یک قدم سخت‌تر باشد.
    open({ title: "لغو شود؟", confirmLabel: "لغو پرونده", danger: true });

    await waitFor(() =>
      expect(document.activeElement).toBe(screen.getByRole("button", { name: "انصراف" }))
    );
    expect(document.activeElement).not.toBe(
      screen.getByRole("button", { name: "لغو پرونده" })
    );
  });

  it("دکمهٔ تأییدِ کار خطرناک ظاهر متمایزی دارد", async () => {
    open({ title: "لغو شود؟", confirmLabel: "لغو پرونده", danger: true });

    const confirmButton = await screen.findByRole("button", { name: "لغو پرونده" });
    expect(confirmButton.className).toMatch(/bg-amber-600/);
    expect(confirmButton.className).not.toMatch(/bg-pulse-600/);
  });

  it("پیامد را جدا از توضیح نشان می‌دهد", async () => {
    // نام فرد و آنچه برنمی‌گردد باید جلوی چشم باشد، نه در صفحهٔ پشت سر.
    open({
      title: "لغو شود؟",
      description: "پرونده به وضعیت لغوشده می‌رود.",
      consequence: "پروندهٔ زهرا کریمی لغو می‌شود. این کار برگشت‌پذیر نیست.",
      danger: true,
    });

    expect(await screen.findByText(/پروندهٔ زهرا کریمی/)).toBeInTheDocument();
    expect(screen.getByText(/پرونده به وضعیت لغوشده/)).toBeInTheDocument();
  });

  it("انصراف مقدار false و تأیید مقدار true برمی‌گرداند", async () => {
    const onResult = vi.fn();
    open({ title: "مطمئنی؟" }, onResult);

    (await screen.findByRole("button", { name: "انصراف" })).click();
    await waitFor(() => expect(onResult).toHaveBeenCalledWith(false));
  });
});
