import { describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, renderHook, screen } from "@testing-library/react";
import { ScoreFormTable, computePreview, scoredRows, useScoreForm } from "./ScoreForm";
import { type Indicator } from "../types";

function indicator(id: number, section: "general" | "specialized" = "general"): Indicator {
  return {
    id,
    section,
    category: `دسته ${id}`,
    description: `شرح ${id}`,
    display_order: id,
    is_active: true,
    created_at: "",
    updated_at: "",
  };
}

const INDICATORS = [indicator(1), indicator(2), indicator(3, "specialized")];

describe("useScoreForm", () => {
  it("starts every indicator UNSCORED (null) so the evaluator must touch each one", () => {
    const { result } = renderHook(() => useScoreForm(INDICATORS, []));
    expect(result.current.drafts.every((d) => d.score === null)).toBe(true);
    // با شاخص‌های بی‌امتیاز فرم معتبر نیست
    expect(result.current.isValid).toBe(false);
    expect(result.current.unscored).toHaveLength(INDICATORS.length);
  });

  it("becomes valid only once every indicator has a score", () => {
    const { result } = renderHook(() => useScoreForm(INDICATORS, []));
    act(() => {
      result.current.setScore(1, 3);
      result.current.setScore(2, 4);
    });
    expect(result.current.isValid).toBe(false); // indicator 3 still null
    act(() => {
      result.current.setScore(3, 2);
    });
    expect(result.current.unscored).toHaveLength(0);
    expect(result.current.isValid).toBe(true);
  });

  it("requires evidence only for scores 1 and 5 (min 3 words)", () => {
    const { result } = renderHook(() => useScoreForm(INDICATORS, []));
    act(() => {
      result.current.setScore(1, 5);
      result.current.setScore(2, 4);
      result.current.setScore(3, 3);
    });
    // امتیاز ۵ بدون شواهد → نقض؛ ۴ و ۳ نیازی ندارند
    expect(result.current.violations).toHaveLength(1);
    expect(result.current.isValid).toBe(false);

    act(() => {
      result.current.setEvidence(1, "یک دو سه");
    });
    expect(result.current.violations).toHaveLength(0);
    expect(result.current.isValid).toBe(true);
  });

  it("does not require evidence for middle scores 2/3/4", () => {
    const { result } = renderHook(() => useScoreForm([indicator(1)], []));
    act(() => {
      result.current.setScore(1, 2);
    });
    expect(result.current.violations).toHaveLength(0);
    expect(result.current.isValid).toBe(true);
  });

  it("hydrates existing saved scores", () => {
    const existing = [{ id: 10, indicator_id: 2, score: 4, evidence_text: "شواهد قبلی" }];
    const { result } = renderHook(() => useScoreForm(INDICATORS, existing));
    const draft = result.current.drafts.find((d) => d.indicator_id === 2);
    expect(draft?.score).toBe(4);
    expect(draft?.evidence_text).toBe("شواهد قبلی");
  });

  it("re-initialises when indicators arrive after the first render (manager-path race)", () => {
    const { result, rerender } = renderHook(
      ({ inds }) => useScoreForm(inds, []),
      { initialProps: { inds: [] as Indicator[] } }
    );
    expect(result.current.drafts).toHaveLength(0);
    expect(result.current.isValid).toBe(false);

    rerender({ inds: INDICATORS });
    expect(result.current.drafts).toHaveLength(INDICATORS.length);
    // بازسازی‌شده اما هنوز بی‌امتیاز → نامعتبر
    expect(result.current.isValid).toBe(false);
  });

  it("hydrates saved scores that arrive AFTER the first render", () => {
    // باگ واقعی: کاربر چند شاخص را امتیاز می‌داد (پیش‌نویس ذخیره می‌شد)، به داشبورد
    // می‌رفت و بدون رفرش برمی‌گشت. کش react-query هنوز نسخهٔ *پیش از ذخیره* را
    // داشت، پس فرم با آن پر می‌شد؛ refetch پس‌زمینه امتیازها را می‌آورد ولی فرم
    // فقط یک‌بار seed می‌شد و دیگر به‌روز نمی‌شد → «پیش‌نویس‌ها نیستند».
    const { result, rerender } = renderHook(
      ({ existing }) => useScoreForm(INDICATORS, existing),
      { initialProps: { existing: [] as { id: number; indicator_id: number; score: number; evidence_text: string | null }[] } }
    );
    expect(result.current.drafts.every((d) => d.score === null)).toBe(true);

    rerender({ existing: [{ id: 7, indicator_id: 2, score: 5, evidence_text: "شواهد ذخیره‌شده" }] });

    const draft = result.current.drafts.find((d) => d.indicator_id === 2);
    expect(draft?.score).toBe(5);
    expect(draft?.evidence_text).toBe("شواهد ذخیره‌شده");
  });

  it("never overwrites what the evaluator is typing with late server data", () => {
    const { result, rerender } = renderHook(
      ({ existing }) => useScoreForm(INDICATORS, existing),
      { initialProps: { existing: [] as { id: number; indicator_id: number; score: number; evidence_text: string | null }[] } }
    );
    act(() => {
      result.current.setScore(1, 4);
      result.current.setEvidence(1, "در حال تایپ");
    });

    // پاسخ کهنهٔ سرور می‌رسد — نباید ویرایش کاربر را پاک کند
    rerender({ existing: [{ id: 1, indicator_id: 1, score: 1, evidence_text: "" }] });

    const draft = result.current.drafts.find((d) => d.indicator_id === 1);
    expect(draft?.score).toBe(4);
    expect(draft?.evidence_text).toBe("در حال تایپ");
  });

  it("keeps the same drafts array when server data repeats, so autosave is not retriggered", () => {
    // یک آرایهٔ نو در هر refetch باعث می‌شد افکت autosave شلیک کند، آن هم کش را
    // به‌روز کند و دوباره همین چرخه — یک حلقهٔ ذخیرهٔ بی‌پایان.
    const existing = [{ id: 3, indicator_id: 1, score: 3, evidence_text: null }];
    const { result, rerender } = renderHook(({ e }) => useScoreForm(INDICATORS, e), {
      initialProps: { e: existing },
    });
    const first = result.current.drafts;

    rerender({ e: [{ ...existing[0] }] }); // همان محتوا، آرایه/شیء تازه

    expect(result.current.drafts).toBe(first);
  });
});

describe("scoredRows", () => {
  it("omits unscored (null) rows and nullifies empty evidence", () => {
    const rows = scoredRows([
      { indicator_id: 1, score: 4, evidence_text: "متن" },
      { indicator_id: 2, score: null, evidence_text: "" },
      { indicator_id: 3, score: 3, evidence_text: "" },
    ]);
    expect(rows).toEqual([
      { indicator_id: 1, score: 4, evidence_text: "متن" },
      { indicator_id: 3, score: 3, evidence_text: null },
    ]);
  });
});

describe("ScoreFormTable slider", () => {
  it("renders an unset slider (no default) with the 'not chosen' label", () => {
    render(
      <ScoreFormTable
        section="general"
        indicators={[indicator(1)]}
        drafts={[{ indicator_id: 1, score: null, evidence_text: "" }]}
        onScoreChange={() => {}}
        onEvidenceChange={() => {}}
      />
    );
    const slider = screen.getByRole("slider");
    expect(slider).toHaveAttribute("aria-valuetext", "امتیازی انتخاب نشده");
    expect(slider).not.toHaveAttribute("aria-valuenow");
  });

  it("reports a score via keyboard (End = 5)", () => {
    const onScoreChange = vi.fn();
    render(
      <ScoreFormTable
        section="general"
        indicators={[indicator(1)]}
        drafts={[{ indicator_id: 1, score: null, evidence_text: "" }]}
        onScoreChange={onScoreChange}
        onEvidenceChange={() => {}}
      />
    );
    const slider = screen.getByRole("slider");
    fireEvent.keyDown(slider, { key: "End" });
    expect(onScoreChange).toHaveBeenCalledWith(1, 5);
  });

  it("enables the evidence box only for scores 1/5", () => {
    const { rerender } = render(
      <ScoreFormTable
        section="general"
        indicators={[indicator(1)]}
        drafts={[{ indicator_id: 1, score: 3, evidence_text: "" }]}
        onScoreChange={() => {}}
        onEvidenceChange={() => {}}
      />
    );
    expect(screen.getByRole("textbox")).toBeDisabled();

    rerender(
      <ScoreFormTable
        section="general"
        indicators={[indicator(1)]}
        drafts={[{ indicator_id: 1, score: 5, evidence_text: "" }]}
        onScoreChange={() => {}}
        onEvidenceChange={() => {}}
      />
    );
    expect(screen.getByRole("textbox")).toBeEnabled();
  });
});

describe("computePreview", () => {
  it("returns null for an empty draft list", () => {
    expect(computePreview([], INDICATORS)).toBeNull();
  });

  it("returns null while any indicator is still unscored", () => {
    const preview = computePreview(
      [
        { indicator_id: 1, score: 5, evidence_text: "" },
        { indicator_id: 2, score: null, evidence_text: "" },
        { indicator_id: 3, score: 1, evidence_text: "" },
      ],
      INDICATORS
    );
    expect(preview).toBeNull();
  });

  it("computes weighted percentages with the server formula", () => {
    // عمومی: (5+1)/10 = 60٪ ، تخصصی: 1/5 = 20٪ ← نهایی: 60*0.6 + 20*0.4 = 44٪
    const preview = computePreview(
      [
        { indicator_id: 1, score: 5, evidence_text: "" },
        { indicator_id: 2, score: 1, evidence_text: "" },
        { indicator_id: 3, score: 1, evidence_text: "" },
      ],
      INDICATORS
    );
    expect(preview).toEqual({ general_pct: 60, specialized_pct: 20, final_pct: 44 });
  });
});
