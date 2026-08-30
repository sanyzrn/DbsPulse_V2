import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { JalaliDatePicker } from "./JalaliDatePicker";

/**
 * این تست‌ها یک اشکالِ دیده‌شده را قفل می‌کنند، نه یک جزئیاتِ پیاده‌سازی را.
 *
 * تقویم `absolute` بود، پس داخلِ همان درختی می‌ماند که دکمه در آن است. نوارِ
 * فیلترها برای انیمیشنِ باز/بستهٔ ارتفاع `overflow-hidden` دارد، و همین تقویم را
 * از لبهٔ پایینِ نوار می‌بُرید: نیمهٔ پایینش نه دیده می‌شد و نه کلیک می‌گرفت.
 *
 * چیزی که این‌جا سنجیده می‌شود «پورتال بودن» نیست؛ این است که تقویم فرزندِ آن
 * ظرفِ برش‌دهنده نباشد — یعنی همان خاصیتی که نبودش اشکال را می‌ساخت. jsdom
 * چیدمان واقعی ندارد، پس بریدگی را نمی‌شود مستقیم سنجید؛ ولی رابطهٔ درختی را
 * می‌شود، و همان علتِ ریشه‌ای است.
 */
function ClippingBar({ children }: { children: React.ReactNode }) {
  return (
    <div data-testid="clipper" className="overflow-hidden">
      {children}
    </div>
  );
}

describe("JalaliDatePicker داخل ظرفِ برش‌دهنده", () => {
  it("تقویم فرزندِ ظرفِ overflow-hidden نیست", () => {
    render(
      <ClippingBar>
        <JalaliDatePicker value="" onChange={() => {}} />
      </ClippingBar>
    );

    fireEvent.click(screen.getByRole("button", { name: /انتخاب تاریخ/ }));

    const dialog = screen.getByRole("dialog", { name: "انتخاب تاریخ" });
    const clipper = screen.getByTestId("clipper");
    expect(clipper.contains(dialog)).toBe(false);
  });

  it("انتخابِ روز کار می‌کند — کلیک داخلِ تقویم «کلیکِ بیرون» حساب نمی‌شود", () => {
    // پس از پورتال‌شدن، تقویم دیگر فرزندِ ریشهٔ کامپوننت نیست. اگر گاردِ
    // «کلیک بیرون» فقط ریشه را می‌سنجید، تقویم پیش از رسیدنِ کلیک به روز بسته
    // می‌شد و انتخاب هیچ‌وقت انجام نمی‌گرفت.
    const onChange = vi.fn();
    render(
      <ClippingBar>
        <JalaliDatePicker value="" onChange={onChange} />
      </ClippingBar>
    );

    fireEvent.click(screen.getByRole("button", { name: /انتخاب تاریخ/ }));
    const dialog = screen.getByRole("dialog", { name: "انتخاب تاریخ" });

    // ترتیبِ واقعیِ مرورگر: mousedown (گاردِ بیرون) و بعد click.
    const day = within(dialog).getDayButton();
    fireEvent.mouseDown(day);
    fireEvent.click(day);

    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith(expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/));
  });
});

/** کوچک‌ترین کمکی که «یک روزِ قابلِ کلیک» را از شبکهٔ تقویم بیرون می‌کشد. */
function within(dialog: HTMLElement) {
  return {
    getDayButton() {
      const buttons = Array.from(dialog.querySelectorAll("button"));
      // روزها یک یا دو رقمی‌اند؛ دکمهٔ سالِ هدر چهار رقمی است و نباید انتخاب شود.
      const day = buttons.find((b) => /^[۰-۹]{1,2}$/.test((b.textContent ?? "").trim()));
      if (!day) throw new Error("هیچ دکمهٔ روزی در تقویم پیدا نشد");
      return day;
    },
  };
}
