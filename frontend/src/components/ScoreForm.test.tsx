import { describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, renderHook, screen } from "@testing-library/react";
import { NEUTRAL_SCORE, ScoreFormTable, computePreview, scoredRows, useScoreForm } from "./ScoreForm";
import { DEFAULT_APP_CONFIG, type Indicator } from "../types";

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
  it("defaults every indicator to the neutral middle score (3), not the lowest option", () => {
    const { result } = renderHook(() => useScoreForm(INDICATORS, []));
    expect(result.current.drafts.every((d) => d.score === NEUTRAL_SCORE)).toBe(true);
    // امتیاز خنثی از قانون شواهد معاف است، پس فرم از ابتدا معتبر است
    expect(result.current.isValid).toBe(true);
  });

  it("requires evidence of at least the configured word count for non-exempt scores", () => {
    const { result } = renderHook(() => useScoreForm(INDICATORS, []));
    act(() => {
      result.current.setScore(1, 5);
    });
    expect(result.current.violations).toHaveLength(1);
    expect(result.current.isValid).toBe(false);

    act(() => {
      result.current.setEvidence(1, Array(DEFAULT_APP_CONFIG.evidence_min_words).fill("کلمه").join(" "));
    });
    expect(result.current.violations).toHaveLength(0);
    expect(result.current.isValid).toBe(true);
  });

  it("exempts the configured score (3) from the evidence rule", () => {
    const { result } = renderHook(() => useScoreForm(INDICATORS, []));
    act(() => {
      result.current.setScore(1, DEFAULT_APP_CONFIG.evidence_exempt_score);
    });
    expect(result.current.violations).toHaveLength(0);
  });

  it("hydrates existing saved scores", () => {
    const existing = [{ id: 10, indicator_id: 2, score: 4, evidence_text: "شواهد قبلی" }];
    const { result } = renderHook(() => useScoreForm(INDICATORS, existing));
    const draft = result.current.drafts.find((d) => d.indicator_id === 2);
    expect(draft?.score).toBe(4);
    expect(draft?.evidence_text).toBe("شواهد قبلی");
  });

  it("re-initialises when indicators arrive after the first render (manager-path race)", () => {
    // اولین رندر با فهرست خالی (شاخص‌ها هنوز در حال بارگذاری) — مانند مسیر «مدیر»
    const { result, rerender } = renderHook(
      ({ inds }) => useScoreForm(inds, []),
      { initialProps: { inds: [] as Indicator[] } }
    );
    expect(result.current.drafts).toHaveLength(0);
    // با فهرست خالی نباید معتبر باشد تا ثبت با scores خالی جلوگیری شود
    expect(result.current.isValid).toBe(false);

    // شاخص‌ها که رسیدند، drafts باید بازسازی شود
    rerender({ inds: INDICATORS });
    expect(result.current.drafts).toHaveLength(INDICATORS.length);
    expect(result.current.isValid).toBe(true);
  });
});

describe("scoredRows", () => {
  it("sends every row and nullifies empty evidence", () => {
    const rows = scoredRows([
      { indicator_id: 1, score: 4, evidence_text: "متن" },
      { indicator_id: 3, score: 3, evidence_text: "" },
    ]);
    expect(rows).toEqual([
      { indicator_id: 1, score: 4, evidence_text: "متن" },
      { indicator_id: 3, score: 3, evidence_text: null },
    ]);
  });
});

describe("ScoreFormTable", () => {
  it("renders a 1..5 range slider with the neutral score pre-selected", () => {
    render(
      <ScoreFormTable
        section="general"
        indicators={[indicator(1)]}
        drafts={[{ indicator_id: 1, score: NEUTRAL_SCORE, evidence_text: "" }]}
        onScoreChange={() => {}}
        onEvidenceChange={() => {}}
      />
    );
    const slider = screen.getByRole("slider");
    expect(slider).toHaveValue(String(NEUTRAL_SCORE));
    expect(slider).toHaveAccessibleName(/امتیاز/);
    // امتیاز خنثی از شواهد معاف است، پس textarea غیرفعال می‌ماند
    const textarea = screen.getByRole("textbox");
    expect(textarea).toBeDisabled();
  });

  it("reports the chosen score through onScoreChange", () => {
    const onScoreChange = vi.fn();
    render(
      <ScoreFormTable
        section="general"
        indicators={[indicator(1)]}
        drafts={[{ indicator_id: 1, score: NEUTRAL_SCORE, evidence_text: "" }]}
        onScoreChange={onScoreChange}
        onEvidenceChange={() => {}}
      />
    );
    const slider = screen.getByRole("slider");
    fireEvent.change(slider, { target: { value: "5" } });
    expect(onScoreChange).toHaveBeenCalledWith(1, 5);
  });

  it("shows the word-count warning for a non-exempt score without evidence", () => {
    render(
      <ScoreFormTable
        section="general"
        indicators={[indicator(1)]}
        drafts={[{ indicator_id: 1, score: 5, evidence_text: "کوتاه" }]}
        onScoreChange={() => {}}
        onEvidenceChange={() => {}}
      />
    );
    expect(screen.getByText(/حداقل 15 کلمه لازم است/)).toBeInTheDocument();
  });
});

describe("computePreview", () => {
  it("returns null for an empty draft list", () => {
    expect(computePreview([], INDICATORS)).toBeNull();
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

  it("rounds to one decimal like the backend", () => {
    // عمومی: 4/10 = 40٪ ، تخصصی: 2/5 = 40٪ ← نهایی 40٪
    const preview = computePreview(
      [
        { indicator_id: 1, score: 1, evidence_text: "" },
        { indicator_id: 2, score: 3, evidence_text: "" },
        { indicator_id: 3, score: 2, evidence_text: "" },
      ],
      INDICATORS
    );
    expect(preview?.general_pct).toBe(40);
    expect(preview?.final_pct).toBe(40);
  });
});
