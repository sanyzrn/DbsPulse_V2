import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { PeriodTrendChart } from "./PeriodTrendChart";
import type { PeriodTrendPoint } from "../types";

const point = (name: string, pct: number | null, count = 6): PeriodTrendPoint => ({
  period_id: 1,
  name,
  starts_on: "1405-01-01",
  avg_final_pct: pct,
  count,
});

describe("PeriodTrendChart", () => {
  it("بدون هیچ داده‌ای می‌گوید ارزیابی نهایی‌شده‌ای نیست", () => {
    render(<PeriodTrendChart data={[]} />);
    expect(screen.getByText(/ارزیابی نهایی‌شده‌ای ثبت نشده/)).toBeInTheDocument();
  });

  it("با یک دوره نمودار نمی‌کشد — «روند» با یک نقطه وجود ندارد", () => {
    render(<PeriodTrendChart data={[point("بهار ۱۴۰۵", 78)]} />);
    expect(screen.getByText(/از دومین دوره/)).toBeInTheDocument();
  });

  it("دوره‌های پنهان‌شده به‌خاطر کم‌بودن جمعیت شمرده می‌شوند، نه بی‌صدا حذف", () => {
    // اگر خط از رویشان بپرد، شکافِ داده شبیهِ روندِ صاف دیده می‌شود.
    render(
      <PeriodTrendChart
        data={[point("بهار", 70), point("تابستان", 74), point("پاییز", null, 2)]}
      />,
    );
    expect(screen.getByText(/۱ دوره نمایش داده نشده است/)).toBeInTheDocument();
  });

  it("با دو دورهٔ معتبر، نمودار رسم می‌شود و پیامِ جایگزین نمی‌آید", () => {
    const { container } = render(
      <PeriodTrendChart data={[point("بهار", 70), point("تابستان", 74)]} />,
    );
    expect(screen.queryByText(/از دومین دوره/)).not.toBeInTheDocument();
    expect(container.querySelector(".recharts-responsive-container")).not.toBeNull();
  });
});
