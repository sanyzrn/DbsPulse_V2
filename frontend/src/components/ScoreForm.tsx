import { useEffect, useMemo, useRef, useState } from "react";
import { DEFAULT_APP_CONFIG, type AppConfig, type Indicator, type EvaluationScoreRow } from "../types";

function wordCount(text: string): number {
  return text.split(/\s+/).filter(Boolean).length;
}

/** مقدار پیش‌فرض هر شاخص: وسط مقیاس ۱ تا ۵ (خنثی)، نه کمترین گزینه. */
export const NEUTRAL_SCORE = 3;

export interface ScoreDraft {
  indicator_id: number;
  score: number;
  evidence_text: string;
}

const SCORE_VALUES = [1, 2, 3, 4, 5] as const;

const SCORE_LABELS: Record<number, string> = {
  1: "ضعیف",
  2: "کمتر از انتظار",
  3: "مطابق انتظار",
  4: "فراتر از انتظار",
  5: "عالی",
};

/** رنگ معنایی هر پله امتیاز — همان قرارداد سه‌رنگ قرمز/کهربایی/سبز که در Meters.tsx
 * برای درصدها استفاده می‌شود (سبز = مطلوب، قرمز = نیازمند توجه)، اینجا در ۵ پله. قبلاً
 * امتیازهای ۴ و ۵ (خوب و عالی) از طیف قرمز برند رنگ می‌گرفتند که با امتیاز ۱ (ضعیف)
 * از یک خانواده رنگ بودند و در نگاه اول گمراه‌کننده بود. */
const SCORE_TONE_COLOR: Record<number, string> = {
  1: "#ef4444", // red-500 — ضعیف
  2: "#f97316", // orange-500 — کمتر از انتظار
  3: "#f59e0b", // amber-500 — مطابق انتظار
  4: "#84cc16", // lime-500 — فراتر از انتظار
  5: "#10b981", // emerald-500 — عالی (همان سبزِ tone مطلوب در Meters.tsx)
};

const READONLY_TONE: Record<number, string> = {
  1: "bg-red-50 text-red-700 ring-1 ring-red-100",
  2: "bg-orange-50 text-orange-700 ring-1 ring-orange-100",
  3: "bg-amber-50 text-amber-700 ring-1 ring-amber-100",
  4: "bg-lime-50 text-lime-700 ring-1 ring-lime-100",
  5: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-100",
};

function initialDrafts(indicators: Indicator[], existing: EvaluationScoreRow[]): ScoreDraft[] {
  const byIndicator = new Map(existing.map((s) => [s.indicator_id, s]));
  return indicators.map((ind) => {
    const found = byIndicator.get(ind.id);
    return {
      indicator_id: ind.id,
      score: found?.score ?? NEUTRAL_SCORE,
      evidence_text: found?.evidence_text ?? "",
    };
  });
}

export function useScoreForm(
  indicators: Indicator[],
  existing: EvaluationScoreRow[],
  config: AppConfig = DEFAULT_APP_CONFIG
) {
  const [drafts, setDrafts] = useState<ScoreDraft[]>(() => initialDrafts(indicators, existing));

  // مقداردهی اولیهٔ useState فقط یک‌بار اجرا می‌شود؛ اگر در نخستین رندر فهرست شاخص‌ها
  // هنوز در حال بارگذاری (خالی) باشد — مثلاً در مسیر «مدیر» که ارزیابی بلافاصله پس از
  // ساخت باز می‌شود — drafts خالی می‌ماند و ثبت با scores خالی به سرور می‌رود. وقتی
  // شاخص‌ها رسیدند، یک‌بار دوباره مقداردهی می‌کنیم (بدون پاک‌کردن ویرایش‌های بعدی کاربر).
  const seededRef = useRef(indicators.length > 0);
  useEffect(() => {
    if (!seededRef.current && indicators.length > 0) {
      seededRef.current = true;
      setDrafts(initialDrafts(indicators, existing));
    }
  }, [indicators, existing]);

  const setScore = (indicatorId: number, score: number) => {
    setDrafts((prev) => prev.map((d) => (d.indicator_id === indicatorId ? { ...d, score } : d)));
  };
  const setEvidence = (indicatorId: number, evidence_text: string) => {
    setDrafts((prev) =>
      prev.map((d) => (d.indicator_id === indicatorId ? { ...d, evidence_text } : d))
    );
  };

  const violations = useMemo(() => {
    return drafts.filter(
      (d) =>
        d.score !== config.evidence_exempt_score && wordCount(d.evidence_text) < config.evidence_min_words
    );
  }, [drafts, config]);

  // drafts.length > 0 از ثبت با فهرست خالی (پیش از بارگذاری شاخص‌ها) جلوگیری می‌کند
  const isValid = violations.length === 0 && drafts.length > 0;

  return { drafts, setScore, setEvidence, violations, isValid };
}

export interface ScorePreview {
  general_pct: number;
  specialized_pct: number;
  final_pct: number;
}

/** پیش‌نمایش محاسبه امتیازها با همان فرمول سرور.
 * (محاسبه نهایی و معتبر همیشه سمت سرور انجام می‌شود.) */
export function computePreview(
  drafts: ScoreDraft[],
  indicators: Indicator[],
  config: AppConfig = DEFAULT_APP_CONFIG
): ScorePreview | null {
  if (drafts.length === 0) return null;
  const sectionById = new Map(indicators.map((i) => [i.id, i.section]));

  let generalSum = 0;
  let generalMax = 0;
  let specializedSum = 0;
  let specializedMax = 0;
  for (const d of drafts) {
    if (sectionById.get(d.indicator_id) === "general") {
      generalSum += d.score;
      generalMax += 5;
    } else {
      specializedSum += d.score;
      specializedMax += 5;
    }
  }
  const round1 = (v: number) => Math.round(v * 10) / 10;
  const general = generalMax ? round1((generalSum / generalMax) * 100) : 0;
  const specialized = specializedMax ? round1((specializedSum / specializedMax) * 100) : 0;
  const final = round1(
    general * config.general_section_weight + specialized * config.specialized_section_weight
  );
  return { general_pct: general, specialized_pct: specialized, final_pct: final };
}

/** ردیف‌های امتیاز برای ذخیره/ثبت به سرور. */
export function scoredRows(drafts: ScoreDraft[]) {
  return drafts.map((d) => ({
    indicator_id: d.indicator_id,
    score: d.score,
    evidence_text: d.evidence_text || null,
  }));
}

/** اسلایدر امتیازدهی ۱ تا ۵ — input[type=range] بومی (پیمایش با کیبورد/درگ/کلیک
 * روی track، معنای slider برای screen reader به‌صورت پیش‌فرض) با رنگ‌بندی معنایی
 * قرمز→سبز که با گزینه‌های دکمه‌ای گسسته قبلی هم قابل‌دسترس‌تر است و هم شسته‌رفته‌تر. */
export function SegmentedScore({
  value,
  onChange,
  label,
}: {
  value: number;
  onChange: (score: number) => void;
  label?: string;
}) {
  const color = SCORE_TONE_COLOR[value];

  return (
    <div className="w-full max-w-52">
      <input
        type="range"
        min={1}
        max={5}
        step={1}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        aria-label={label ?? "امتیاز"}
        aria-valuetext={`${value.toLocaleString("fa-IR")} — ${SCORE_LABELS[value]}`}
        className="score-slider w-full"
        style={{ "--score-color": color } as React.CSSProperties}
      />
      <div className="mt-1 flex items-center justify-between text-[10px] text-gray-400">
        {SCORE_VALUES.map((n) => (
          <span key={n} className={n === value ? "font-bold" : undefined} style={n === value ? { color } : undefined}>
            {n.toLocaleString("fa-IR")}
          </span>
        ))}
      </div>
    </div>
  );
}

export function ScoreFormTable({
  section,
  indicators,
  drafts,
  onScoreChange,
  onEvidenceChange,
  readOnly = false,
  config = DEFAULT_APP_CONFIG,
}: {
  section: "general" | "specialized";
  indicators: Indicator[];
  drafts: ScoreDraft[];
  onScoreChange: (indicatorId: number, score: number) => void;
  onEvidenceChange: (indicatorId: number, text: string) => void;
  readOnly?: boolean;
  config?: AppConfig;
}) {
  const sectionIndicators = indicators.filter((i) => i.section === section);
  const draftByIndicator = new Map(drafts.map((d) => [d.indicator_id, d]));

  return (
    <div className="overflow-x-auto rounded-2xl border border-gray-100 bg-white shadow-card">
      <table className="w-full text-sm">
        <thead className="border-b border-gray-100 text-xs text-gray-600">
          <tr>
            <th className="px-3 py-3 text-right font-semibold">شاخص کلیدی</th>
            <th className="px-3 py-3 text-right font-semibold">مصداق رفتاری/عملکردی</th>
            <th className="w-52 px-3 py-3 text-right font-semibold">امتیاز</th>
            <th className="px-3 py-3 text-right font-semibold">شواهد عینی</th>
          </tr>
        </thead>
        <tbody>
          {sectionIndicators.map((ind) => {
            const draft = draftByIndicator.get(ind.id);
            if (!draft) return null;
            const count = wordCount(draft.evidence_text);
            const needsEvidence = draft.score !== config.evidence_exempt_score;
            const invalid = needsEvidence && count < config.evidence_min_words;
            return (
              <tr key={ind.id} className="border-t border-gray-50 align-top transition-colors hover:bg-pulse-50/20">
                <td className="px-3 py-3 font-medium text-gray-800">{ind.category}</td>
                <td className="px-3 py-3 text-gray-600">{ind.description}</td>
                <td className="px-3 py-3">
                  {readOnly ? (
                    <span
                      className={`inline-flex items-center gap-1.5 rounded-xl px-2.5 py-1 text-sm font-bold ${READONLY_TONE[draft.score] ?? "bg-gray-100 text-gray-700"}`}
                      title={SCORE_LABELS[draft.score]}
                    >
                      {draft.score.toLocaleString("fa-IR")}
                      <span className="text-[11px] font-normal opacity-80">{SCORE_LABELS[draft.score]}</span>
                    </span>
                  ) : (
                    <div>
                      <SegmentedScore
                        value={draft.score}
                        onChange={(score) => onScoreChange(ind.id, score)}
                        label={`امتیاز ${ind.category}`}
                      />
                      <p className="mt-1 text-[11px] text-gray-400">{SCORE_LABELS[draft.score]}</p>
                    </div>
                  )}
                </td>
                <td className="px-3 py-3">
                  {readOnly ? (
                    <span className="whitespace-pre-wrap text-gray-700">{draft.evidence_text || "—"}</span>
                  ) : (
                    <div>
                      <textarea
                        aria-label={`شواهد عینی شاخص: ${ind.category}`}
                        className={`w-full resize-none rounded-xl border px-3 py-2 text-sm text-gray-800 outline-none transition-colors duration-150 ${
                          invalid
                            ? "border-red-400 bg-red-50 focus:border-red-500"
                            : "border-gray-200 bg-gray-100 focus:border-pulse-500 focus:bg-white"
                        }`}
                        rows={2}
                        value={draft.evidence_text}
                        onChange={(e) => onEvidenceChange(ind.id, e.target.value)}
                        disabled={!needsEvidence}
                        placeholder={
                          needsEvidence
                            ? "شرح شواهد عینی…"
                            : `برای امتیاز ${config.evidence_exempt_score.toLocaleString("fa-IR")} اختیاری است`
                        }
                      />
                      {needsEvidence && (
                        <p className={`mt-1 text-xs ${invalid ? "text-red-600" : "text-pulse-600"}`}>
                          {invalid
                            ? `حداقل ${config.evidence_min_words} کلمه لازم است (در حال حاضر: ${count} کلمه)`
                            : `${count} کلمه ثبت شد ✓`}
                        </p>
                      )}
                    </div>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
