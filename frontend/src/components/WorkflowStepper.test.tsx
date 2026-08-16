/** نوار زنجیرهٔ تأیید — پنجمین موردِ ممیزی تجربهٔ کاربری.
 *
 * ادعای این نوار ساده است ولی سه حالت مرزی دارد که هر کدام بی‌صدا غلط می‌شوند:
 * پروندهٔ نهایی‌شده باید کامل باشد، پروندهٔ لغوشده اصلاً نباید نواری داشته باشد،
 * و «مرحلهٔ فعلی» باید همان یکی باشد نه یکی جلوتر.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { WorkflowStepper } from "./WorkflowStepper";

/** برچسبِ مرحله‌ای که پررنگ است — یعنی «الان این‌جاست». */
function currentStep(container: HTMLElement): string | null {
  const bold = container.querySelector("span.font-bold");
  return bold?.textContent ?? null;
}

/** چند قدم سبز (تمام‌شده) است. */
function completedCount(container: HTMLElement): number {
  return container.querySelectorAll("span.bg-green-500").length;
}

describe("WorkflowStepper", () => {
  it("پروندهٔ تازه در قدم اول است و هیچ قدمی تمام نشده", () => {
    const { container } = render(<WorkflowStepper status="draft" />);

    expect(currentStep(container)).toBe("امتیازدهی");
    expect(completedCount(container)).toBe(0);
  });

  it("مرحلهٔ فعلی را جلوتر از آنچه هست نشان نمی‌دهد", () => {
    // پرونده‌ای که ثبت شده منتظر منابع انسانی است — یعنی قدم دوم، نه سوم.
    const { container } = render(<WorkflowStepper status="submitted" />);

    expect(currentStep(container)).toBe("منابع انسانی");
    expect(completedCount(container)).toBe(1);
  });

  it("پروندهٔ نهایی‌شده هر چهار قدم را تمام‌شده نشان می‌دهد", () => {
    // اگر «نهایی‌شده» را مثل «در مرحلهٔ تأیید نهایی» حساب کنیم، کارمندی که کارش
    // تمام شده هنوز یک قدم ناتمام می‌بیند.
    const { container } = render(<WorkflowStepper status="finalized" />);

    expect(completedCount(container)).toBe(4);
    expect(currentStep(container)).toBeNull();
  });

  it("برای پروندهٔ لغوشده هیچ نواری نشان نمی‌دهد", () => {
    // پروندهٔ لغوشده در هیچ مرحله‌ای «نیست»؛ نوارِ نیمه‌پر یعنی ادعای دروغ که
    // هنوز در جریان است.
    const { container } = render(<WorkflowStepper status="cancelled" />);

    expect(container).toBeEmptyDOMElement();
  });

  it("پروندهٔ برگشتی مرحلهٔ فعلی را با رنگ هشدار نشان می‌دهد", () => {
    const { container } = render(<WorkflowStepper status="draft" returned />);

    expect(container.querySelector("span.bg-amber-500")).not.toBeNull();
    expect(container.querySelector("span.bg-pulse-600")).toBeNull();
  });

  it("برای صفحه‌خوان‌ها برچسب دارد", () => {
    render(<WorkflowStepper status="hr_approved" />);

    expect(screen.getByLabelText("جایگاه پرونده در زنجیرهٔ تأیید")).toBeInTheDocument();
    expect(screen.getByText("— مرحلهٔ فعلی")).toBeInTheDocument();
  });
});
