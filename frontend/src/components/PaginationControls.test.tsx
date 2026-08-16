/** نوار صفحه‌بندی، به‌ویژه انتخابگر تعداد در صفحه.
 *
 * نکتهٔ ظریفی که به‌سادگی برمی‌گردد: نوار نباید وقتی همه‌چیز در یک صفحه جا
 * می‌شود ناپدید شود. اگر بشود، کسی که تعداد را روی ۵۰ گذاشته و حالا ۲۱ مورد
 * دارد، راهی برای برگرداندنش ندارد — کنترل خودش را پنهان کرده است.
 */
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { PaginationControls } from "./PaginationControls";

function setup(props: Partial<Parameters<typeof PaginationControls>[0]> = {}) {
  const onPageChange = vi.fn();
  const onPageSizeChange = vi.fn();
  render(
    <PaginationControls
      page={0}
      totalPages={3}
      totalCount={21}
      pageSize={10}
      onPageChange={onPageChange}
      onPageSizeChange={onPageSizeChange}
      {...props}
    />,
  );
  return { onPageChange, onPageSizeChange };
}

describe("PaginationControls", () => {
  it("تعداد در صفحه را می‌شود عوض کرد", () => {
    const { onPageSizeChange } = setup();
    fireEvent.change(screen.getByLabelText("تعداد نمایش در هر صفحه"), {
      target: { value: "50" },
    });
    expect(onPageSizeChange).toHaveBeenCalledWith(50);
  });

  it("گزینه‌ها از کوچک به بزرگ‌اند و پیش‌فرض انتخاب شده است", () => {
    setup();
    const select = screen.getByLabelText("تعداد نمایش در هر صفحه") as HTMLSelectElement;
    expect([...select.options].map((o) => Number(o.value))).toEqual([10, 20, 50, 100]);
    expect(select.value).toBe("10");
  });

  it("وقتی همه‌چیز در یک صفحه جا شده، انتخابگر همچنان هست", () => {
    // ۲۱ مورد با تعداد ۵۰ = یک صفحه. بدون این، راهی برای برگشت به ۱۰ نیست.
    setup({ totalPages: 1, pageSize: 50 });
    expect(screen.getByLabelText("تعداد نمایش در هر صفحه")).toBeInTheDocument();
    expect(screen.queryByLabelText("صفحه بعد")).not.toBeInTheDocument();
  });

  it("برای فهرستی کوتاه‌تر از کوچک‌ترین گزینه، نواری نشان نمی‌دهد", () => {
    const { container } = render(
      <PaginationControls
        page={0}
        totalPages={1}
        totalCount={4}
        pageSize={10}
        onPageChange={vi.fn()}
        onPageSizeChange={vi.fn()}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("بدون onPageSizeChange، فقط ناوبری صفحه را نشان می‌دهد", () => {
    setup({ onPageSizeChange: undefined });
    expect(screen.queryByLabelText("تعداد نمایش در هر صفحه")).not.toBeInTheDocument();
    expect(screen.getByLabelText("صفحه بعد")).toBeInTheDocument();
  });

  it("تعداد کل را نشان می‌دهد", () => {
    setup();
    expect(screen.getByText(/۲۱ مورد/)).toBeInTheDocument();
  });
});
