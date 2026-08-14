import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ScoreTrend, wrapLabel } from "./PersonCharts";

describe("wrapLabel", () => {
  it("نام کوتاه را دست‌نخورده و یک‌خطی می‌گذارد", () => {
    expect(wrapLabel("محرمانگی")).toEqual(["محرمانگی"]);
  });

  it("نام بلند را روی فاصله‌ها می‌شکند — این همان چیزی بود که برچسب‌ها را روی هم می‌انداخت", () => {
    // «رعایت الزامات واحد و سازمان» ۲۷ نویسه است و در یک خطِ رادار جا نمی‌شود
    const lines = wrapLabel("رعایت الزامات واحد و سازمان");
    expect(lines.length).toBeGreaterThan(1);
    expect(lines.every((l) => l.length <= 16)).toBe(true);
  });

  it("بیش از دو خط نمی‌شود و بریدگی را با … اعلام می‌کند", () => {
    const lines = wrapLabel("یک عبارت خیلی خیلی طولانی که قطعاً در دو خط جا نمی‌شود و باید بریده شود");
    expect(lines).toHaveLength(2);
    expect(lines[1]).toMatch(/…$/);
  });

  it("کلمهٔ تنهای بلندتر از خط را هم برمی‌گرداند (بی‌نهایت حلقه نمی‌زند)", () => {
    expect(wrapLabel("یککلمهٔبسیاربسیارطولانیبدونفاصله").length).toBeGreaterThan(0);
  });
});

describe("ScoreTrend", () => {
  const point = (code: string, pct: number) => ({
    evaluation_code: code,
    finalized_at: "2026-01-01",
    final_weighted_pct: pct,
  });

  it("با یک ارزیابی، به‌جای نمودارِ تک‌نقطه‌ای همان عدد را می‌نویسد", () => {
    // یک نقطه «روند» نیست؛ نمودار قبلی یک دایرهٔ سرگردان وسط قاب نشان می‌داد.
    render(<ScoreTrend data={[point("EVL-0004", 81)]} gradientId="t1" />);

    expect(screen.getByText("۸۱٪")).toBeInTheDocument();
    expect(screen.getByText("EVL-0004")).toBeInTheDocument();
    expect(screen.getByText(/روند از دومین ارزیابی به بعد/)).toBeInTheDocument();
  });

  it("با دو ارزیابی یا بیشتر، نمودار رسم می‌شود", () => {
    const { container } = render(
      <ScoreTrend data={[point("EVL-1", 70), point("EVL-2", 80)]} gradientId="t2" />,
    );
    expect(screen.queryByText(/روند از دومین ارزیابی به بعد/)).not.toBeInTheDocument();
    expect(container.querySelector(".recharts-responsive-container")).toBeTruthy();
  });

  it("بدون داده، پیام روشن می‌دهد", () => {
    render(<ScoreTrend data={[]} gradientId="t3" />);
    expect(screen.getByText(/روندی برای این فرد ثبت نشده/)).toBeInTheDocument();
  });
});
