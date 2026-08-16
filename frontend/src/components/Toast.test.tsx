/** پیام‌ها — چهارمین موردِ ممیزی تجربهٔ کاربری.
 *
 * ادعا: پیام موفقیت خودش می‌رود، پیام خطا نه. متن خطا معمولاً تنها جایی است که
 * می‌گوید *دقیقاً* چه چیزی غلط بود؛ چهار ثانیه برای خواندنش کافی نیست، و کاربری
 * که نتوانست بخواند همان کار را دوباره تکرار می‌کند.
 *
 * این‌جا از `fireEvent` استفاده می‌شود نه `userEvent`: دومی با تایمرِ ساختگی و
 * حلقهٔ انیمیشن `motion` قفل می‌کند، و چیزی که می‌سنجیم رفتار تایمر است نه ریزه‌کاری
 * تعامل کاربر.
 */
import type { ReactNode } from "react";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// `AnimatePresence` عنصرِ حذف‌شده را تا پایان انیمیشن خروج در DOM نگه می‌دارد و
// آن انیمیشن زیر تایمرِ ساختگی تمام نمی‌شود. چیزی که این فایل می‌سنجد منطق
// تایمرِ Toast است نه رفتار کتابخانهٔ انیمیشن، پس همان‌جا را کنار می‌گذاریم.
const ANIMATION_PROPS = ["layout", "initial", "animate", "exit", "transition"];

vi.mock("motion/react", () => ({
  AnimatePresence: ({ children }: { children: ReactNode }) => <>{children}</>,
  motion: new Proxy(
    {},
    {
      get: (_target, tag: string) => (props: Record<string, unknown>) => {
        const { children, ...rest } = props;
        for (const key of ANIMATION_PROPS) delete rest[key];
        const Tag = tag as "div";
        return <Tag {...rest}>{children as ReactNode}</Tag>;
      },
    }
  ),
}));

const { ToastProvider, useToast } = await import("./Toast");

function Harness() {
  const { showSuccess, showError } = useToast();
  return (
    <>
      <button onClick={() => showSuccess("ذخیره شد")}>موفقیت</button>
      <button onClick={() => showError("شاخص ۳ شواهد ندارد")}>خطا</button>
    </>
  );
}

function renderToasts() {
  return render(
    <ToastProvider>
      <Harness />
    </ToastProvider>
  );
}

const click = (label: string) => act(() => void fireEvent.click(screen.getByText(label)));
const tick = (ms: number) => act(() => void vi.advanceTimersByTime(ms));

describe("Toast", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("پیام موفقیت پس از چند ثانیه خودش می‌رود", () => {
    renderToasts();

    click("موفقیت");
    expect(screen.getByText("ذخیره شد")).toBeInTheDocument();

    tick(5000);
    expect(screen.queryByText("ذخیره شد")).not.toBeInTheDocument();
  });

  it("پیام خطا نمی‌رود تا کاربر ببندش", () => {
    renderToasts();

    click("خطا");
    expect(screen.getByText("شاخص ۳ شواهد ندارد")).toBeInTheDocument();

    // یک دقیقه بعد هم هنوز سر جایش است
    tick(60_000);
    expect(screen.getByText("شاخص ۳ شواهد ندارد")).toBeInTheDocument();

    act(() => void fireEvent.click(screen.getByLabelText("بستن پیام خطا")));
    expect(screen.queryByText("شاخص ۳ شواهد ندارد")).not.toBeInTheDocument();
  });

  it("خطا زمینهٔ قرمزِ برند را نمی‌گیرد", () => {
    // قرمزِ pulse رنگِ هر دکمهٔ اصلی سامانه است؛ اگر پیام خطا هم همان باشد،
    // قرمز دیگر خبری نمی‌دهد و کاربر باید متن را بخواند تا بفهمد چه شد.
    const { container } = renderToasts();

    click("خطا");

    const toast = container.querySelector('[role="alert"]');
    expect(toast?.className).not.toMatch(/bg-pulse-600/);
    expect(toast?.className).toMatch(/bg-charcoal-900/);
  });

  it("خطا role=alert و موفقیت role=status می‌گیرد", () => {
    renderToasts();

    click("خطا");
    click("موفقیت");

    expect(screen.getByRole("alert")).toHaveTextContent("شاخص ۳ شواهد ندارد");
    expect(screen.getByRole("status")).toHaveTextContent("ذخیره شد");
  });
});
