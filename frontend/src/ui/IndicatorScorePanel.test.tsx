import { describe, expect, it } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { IndicatorScorePanel } from "./IndicatorScorePanel";
import type { IndicatorReportStat } from "../types";

function stat(over: Partial<IndicatorReportStat> & { indicator_id: number }): IndicatorReportStat {
  return {
    category: "تعهد سازمانی",
    description: "شرح شاخص",
    section: "general",
    avg_score: 4,
    count: 10,
    ...over,
  };
}

function categoryButton(name: string) {
  return screen.getByRole("button", { name: new RegExp(name) });
}

function offsets(container: HTMLElement): number[] {
  return Array.from(container.querySelectorAll("[data-testid='plot-dot']")).map((el) =>
    Number(el.getAttribute("data-offset")),
  );
}

describe("IndicatorScorePanel", () => {
  it("محور از ۱ شروع می‌شود نه از صفر", () => {
    // این همان ایرادی است که میله‌ها را هم‌قد می‌کرد: با شروع از صفر، نمرهٔ ۱ روی
    // ۲۰٪ می‌نشست و کل تفاوت معنادار در یک‌پنجم انتهایی فشرده می‌شد.
    const { container } = render(
      <IndicatorScorePanel
        stats={[
          stat({ indicator_id: 1, category: "کمینه", avg_score: 1 }),
          stat({ indicator_id: 2, category: "میانه", avg_score: 3 }),
          stat({ indicator_id: 3, category: "بیشینه", avg_score: 5 }),
        ]}
      />,
    );

    expect(offsets(container)).toEqual([0, 50, 100]);
  });

  it("میانگین دسته با تعداد نمره وزن می‌خورد، نه میانگینِ میانگین‌ها", () => {
    // میانگینِ میانگین‌ها ۴٫۰ می‌داد؛ میانگین واقعیِ ده نمره ۳٫۲ است.
    render(
      <IndicatorScorePanel
        stats={[
          stat({ indicator_id: 1, category: "محرمانگی", avg_score: 5, count: 1 }),
          stat({ indicator_id: 2, category: "محرمانگی", avg_score: 3, count: 9 }),
        ]}
      />,
    );

    expect(categoryButton("محرمانگی")).toHaveAttribute("title", "محرمانگی — میانگین ۳٫۲ از ۵");
  });

  it("شاخص سرکوب‌شده صفر حساب نمی‌شود؛ کنار می‌رود و تعدادش اعلام می‌شود", () => {
    render(
      <IndicatorScorePanel
        stats={[
          stat({ indicator_id: 1, category: "انضباط فردی", avg_score: 4, count: 8 }),
          stat({ indicator_id: 2, category: "انضباط فردی", avg_score: null, count: 2 }),
        ]}
      />,
    );

    // اگر سرکوب‌شده صفر حساب می‌شد، میانگین ۳٫۲ می‌شد
    expect(categoryButton("انضباط فردی")).toHaveAttribute(
      "title",
      "انضباط فردی — میانگین ۴٫۰ از ۵",
    );

    fireEvent.click(categoryButton("انضباط فردی"));
    expect(screen.getByText(/۱ شاخص به دلیل کم‌بودن تعداد نمره/)).toBeInTheDocument();
  });

  it("دسته‌ای که همهٔ شاخص‌هایش سرکوب شده‌اند اصلاً نمایش داده نمی‌شود", () => {
    render(
      <IndicatorScorePanel
        stats={[
          stat({ indicator_id: 1, category: "دیده‌می‌شود", avg_score: 4 }),
          stat({ indicator_id: 2, category: "پنهان", avg_score: null }),
        ]}
      />,
    );

    expect(categoryButton("دیده‌می‌شود")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /پنهان/ })).not.toBeInTheDocument();
  });

  it("شرح کاملِ شاخص با بازکردن دسته می‌آید — بریده نمی‌شود", () => {
    const long = "تعداد دفعات حضور/همراهی در شرایط اضطراری یا فوق‌العاده طبق درخواست ثبت‌شده واحد";
    render(
      <IndicatorScorePanel
        stats={[stat({ indicator_id: 1, category: "تعهد سازمانی", description: long })]}
      />,
    );

    expect(screen.queryByText(long)).not.toBeInTheDocument();

    fireEvent.click(categoryButton("تعهد سازمانی"));

    expect(screen.getByText(long)).toBeInTheDocument();
    expect(categoryButton("تعهد سازمانی")).toHaveAttribute("aria-expanded", "true");
  });

  it("بخش‌های عمومی و تخصصی جدا و با عنوان فارسی می‌آیند", () => {
    render(
      <IndicatorScorePanel
        stats={[
          stat({ indicator_id: 1, category: "تعهد سازمانی", section: "general" }),
          stat({ indicator_id: 2, category: "کیفیت خروجی کار", section: "specialized" }),
        ]}
      />,
    );

    expect(screen.getByRole("heading", { name: "شاخص‌های عمومی" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "شاخص‌های تخصصی" })).toBeInTheDocument();
  });

  it("ترتیب پیش‌فرض همان ترتیب سرور است و «کم‌امتیازترین» آن را بازچینی می‌کند", () => {
    const stats = [
      stat({ indicator_id: 1, category: "الف", avg_score: 4.5 }),
      stat({ indicator_id: 2, category: "ب", avg_score: 2.5 }),
      stat({ indicator_id: 3, category: "ج", avg_score: 3.5 }),
    ];
    const names = () =>
      screen.getAllByRole("button").map((b) => b.getAttribute("title")?.split(" —")[0]);

    const { rerender } = render(<IndicatorScorePanel stats={stats} />);
    expect(names()).toEqual(["الف", "ب", "ج"]);

    rerender(<IndicatorScorePanel stats={stats} sort="lowest" />);
    expect(names()).toEqual(["ب", "ج", "الف"]);
  });

  it("«کم‌امتیازترین» داخل دستهٔ بازشده هم اعمال می‌شود", () => {
    render(
      <IndicatorScorePanel
        sort="lowest"
        stats={[
          stat({ indicator_id: 1, category: "بهبود مستمر", description: "بالا", avg_score: 4.5 }),
          stat({ indicator_id: 2, category: "بهبود مستمر", description: "پایین", avg_score: 2.5 }),
        ]}
      />,
    );

    fireEvent.click(categoryButton("بهبود مستمر"));
    const region = screen.getByText("پایین").closest("div")!.parentElement!;
    const shown = within(region)
      .getAllByText(/^(بالا|پایین)$/)
      .map((el) => el.textContent);
    expect(shown).toEqual(["پایین", "بالا"]);
  });
});
