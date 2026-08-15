/** فرم امتیازدهی روی صفحهٔ باریک (P2-04).
 *
 * جدول چهارستونی روی موبایل به اسکرول افقی تبدیل می‌شد: ارزیاب برای رسیدن به
 * ستون «امتیاز» باید ستون‌ها را کنار می‌زد و شرح شاخص از دید خارج می‌شد — یعنی
 * نمره‌دادن بدون دیدن چیزی که به آن نمره می‌دهد.
 *
 * این فایل سه چیز را می‌سنجد که هر کدام می‌توانند بی‌صدا برگردند: اینکه در عرض
 * کم اصلاً کارت رندر می‌شود، اینکه امتیازها دکمهٔ گسسته‌اند نه اسلایدر، و اینکه
 * هر شاخص فقط *یک* کنترل دارد نه دو تا.
 */
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { ScoreFormTable } from "./ScoreForm";
import type { Indicator } from "../types";

function indicator(id: number): Indicator {
  return {
    id,
    section: "general",
    category: `دسته ${id}`,
    description: `شرح ${id}`,
    display_order: id,
    is_active: true,
    created_at: "",
    updated_at: "",
  };
}

/** matchMedia را برای این تست «باریک» می‌کند. */
function setNarrow(narrow: boolean) {
  window.matchMedia = ((query: string) => ({
    matches: narrow,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
}

const INDICATORS = [indicator(1), indicator(2)];

function renderForm(drafts: { indicator_id: number; score: number | null; evidence_text: string }[]) {
  const onScoreChange = vi.fn();
  const onEvidenceChange = vi.fn();
  render(
    <ScoreFormTable
      section="general"
      indicators={INDICATORS}
      drafts={drafts}
      onScoreChange={onScoreChange}
      onEvidenceChange={onEvidenceChange}
    />,
  );
  return { onScoreChange, onEvidenceChange };
}

const BLANK = INDICATORS.map((i) => ({
  indicator_id: i.id,
  score: null as number | null,
  evidence_text: "",
}));

describe("فرم امتیازدهی روی صفحهٔ باریک", () => {
  it("در عرض کم جدول نمی‌سازد", () => {
    setNarrow(true);
    renderForm(BLANK);
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("شرح شاخص کنار امتیاز دیده می‌شود، نه پشت اسکرول افقی", () => {
    setNarrow(true);
    renderForm(BLANK);
    expect(screen.getByText("شرح 1")).toBeInTheDocument();
    expect(screen.getByText("دسته 1")).toBeInTheDocument();
  });

  it("امتیاز با دکمهٔ گسسته انتخاب می‌شود، نه با کشیدن اسلایدر", () => {
    // کشیدنِ یک thumb ۲۲ پیکسلی با انگشت، روی مقیاسی که فقط پنج مقدار دارد،
    // هم دقیق نیست و هم اصلاً پیوسته نیست که کشیدن معنا بدهد.
    setNarrow(true);
    const { onScoreChange } = renderForm(BLANK);

    expect(screen.queryByRole("slider")).not.toBeInTheDocument();
    // هر شاخص گروه رادیوی خودش را دارد، پس انتخاب باید درون همان گروه باشد —
    // وگرنه کلیک روی «۴» می‌توانست به شاخص دیگری برود.
    const firstGroup = screen.getByRole("radiogroup", { name: "امتیاز دسته 1" });
    fireEvent.click(within(firstGroup).getByRole("radio", { name: /۴ — فراتر از انتظار/ }));
    expect(onScoreChange).toHaveBeenCalledWith(1, 4);
  });

  it("هر شاخص دقیقاً یک کنترل امتیاز دارد", () => {
    // اگر هر دو نسخه هم‌زمان رندر شوند، هر پرسش دو ورودی دارد: خوانندهٔ صفحه
    // هر شاخص را دوبار می‌خواند و انتخابِ کاربر می‌تواند به کنترل نامرئی برود.
    setNarrow(true);
    renderForm(BLANK);
    expect(screen.getAllByRole("radiogroup")).toHaveLength(INDICATORS.length);
  });

  it("در عرض زیاد همان جدول قبلی می‌ماند", () => {
    setNarrow(false);
    renderForm(BLANK);
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.queryByRole("radiogroup")).not.toBeInTheDocument();
  });
});

describe("شمارندهٔ واژهٔ شواهد", () => {
  it("می‌گوید چند واژه کم است، پیش از اینکه ثبت رد شود", () => {
    // قاعده از قبل بود (نمرهٔ ۱ و ۵ حداقل سه واژه می‌خواهند) ولی تنها جایی که
    // دیده می‌شد پیام خطای ثبت بود — بعد از پرکردن بیست شاخص.
    setNarrow(true);
    renderForm([
      { indicator_id: 1, score: 5, evidence_text: "یک" },
      { indicator_id: 2, score: 3, evidence_text: "" },
    ]);
    expect(screen.getByText(/۲ واژهٔ دیگر لازم است/)).toBeInTheDocument();
  });

  it("پس از رسیدن به حد نصاب، شمارش را نشان می‌دهد نه هشدار", () => {
    setNarrow(true);
    renderForm([
      { indicator_id: 1, score: 5, evidence_text: "یک دو سه" },
      { indicator_id: 2, score: 3, evidence_text: "" },
    ]);
    expect(screen.queryByText(/واژهٔ دیگر لازم است/)).not.toBeInTheDocument();
    expect(screen.getByText(/۳ از ۴۰ واژه/)).toBeInTheDocument();
  });

  it("برای امتیازی که شواهد لازم ندارد، شمارنده‌ای هم نیست", () => {
    setNarrow(true);
    renderForm([
      { indicator_id: 1, score: 3, evidence_text: "" },
      { indicator_id: 2, score: 3, evidence_text: "" },
    ]);
    expect(screen.queryByText(/واژه/)).not.toBeInTheDocument();
  });
});
