import { useEffect, useMemo, useRef, useState } from "react";
import { DEFAULT_APP_CONFIG, type AppConfig, type Indicator, type EvaluationScoreRow } from "../types";
import { NARROW_QUERY, useMediaQuery } from "../ui/useMediaQuery";

function wordCount(text: string): number {
  return text.split(/\s+/).filter(Boolean).length;
}

export interface ScoreDraft {
  indicator_id: number;
  /** null یعنی هنوز امتیازی انتخاب نشده — ارزیاب باید هر شاخص را عمداً لمس کند. */
  score: number | null;
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

/** رنگ معنایی هر پله امتیاز — قرمز (ضعیف) تا سبز (عالی)، هم‌راستا با tone درصدها در Meters.tsx. */
const SCORE_TONE_COLOR: Record<number, string> = {
  1: "#ef4444", // red-500 — ضعیف
  2: "#f97316", // orange-500 — کمتر از انتظار
  3: "#f59e0b", // amber-500 — مطابق انتظار
  4: "#84cc16", // lime-500 — فراتر از انتظار
  5: "#10b981", // emerald-500 — عالی
};

const READONLY_TONE: Record<number, string> = {
  1: "bg-red-50 text-red-700 ring-1 ring-red-100",
  2: "bg-orange-50 text-orange-700 ring-1 ring-orange-100",
  3: "bg-amber-50 text-amber-700 ring-1 ring-amber-100",
  4: "bg-lime-50 text-lime-700 ring-1 ring-lime-100",
  5: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-100",
};

function evidenceIsRequired(score: number | null, config: AppConfig): boolean {
  return score !== null && (config.evidence_required_scores ?? [1, 5]).includes(score);
}

function initialDrafts(indicators: Indicator[], existing: EvaluationScoreRow[]): ScoreDraft[] {
  const byIndicator = new Map(existing.map((s) => [s.indicator_id, s]));
  return indicators.map((ind) => {
    const found = byIndicator.get(ind.id);
    return {
      indicator_id: ind.id,
      // بدون پیش‌فرض: شاخص‌های امتیازنداده null می‌مانند تا ارزیاب حتماً همه را ببیند.
      score: found?.score ?? null,
      evidence_text: found?.evidence_text ?? "",
    };
  });
}

function sameDrafts(a: ScoreDraft[], b: ScoreDraft[]): boolean {
  if (a.length !== b.length) return false;
  return a.every((draft, i) => {
    const other = b[i];
    return (
      other !== undefined &&
      draft.indicator_id === other.indicator_id &&
      draft.score === other.score &&
      draft.evidence_text === other.evidence_text
    );
  });
}

export function useScoreForm(
  indicators: Indicator[],
  existing: EvaluationScoreRow[],
  config: AppConfig = DEFAULT_APP_CONFIG
) {
  const [drafts, setDrafts] = useState<ScoreDraft[]>(() => initialDrafts(indicators, existing));

  // مقداردهی اولیهٔ useState فقط یک‌بار اجرا می‌شود، ولی داده‌های سرور ممکن است *بعد*
  // از نخستین رندر برسند:
  //
  //  • فهرست شاخص‌ها هنوز در حال بارگذاری باشد (مسیر «مدیر»، که ارزیابی بلافاصله پس
  //    از ساخت باز می‌شود)؛
  //  • یا ارزیابی از کش react-query بیاید و امتیازهای واقعی با refetch پس‌زمینه
  //    برسند — دقیقاً حالتی که «بدون رفرش برگردم، پیش‌نویس‌ها نیستند» را می‌ساخت.
  //
  // پس تا وقتی کاربر دست به فرم نزده، هر بار که دادهٔ تازه‌ای رسید دوباره مقداردهی
  // می‌کنیم. پس از نخستین ویرایش دیگر این کار را نمی‌کنیم تا تایپِ کاربر پاک نشود.
  const touchedRef = useRef(false);
  useEffect(() => {
    if (indicators.length === 0 || touchedRef.current) return;
    // اگر محتوا همان است، *همان* آرایه را برمی‌گردانیم: یک آرایهٔ نو باعث رندر
    // مجدد و شلیک autosave می‌شد، آن هم setQueryData می‌کرد و حلقه می‌ساخت.
    setDrafts((prev) => {
      const next = initialDrafts(indicators, existing);
      return sameDrafts(prev, next) ? prev : next;
    });
  }, [indicators, existing]);

  const setScore = (indicatorId: number, score: number) => {
    touchedRef.current = true;
    setDrafts((prev) => prev.map((d) => (d.indicator_id === indicatorId ? { ...d, score } : d)));
  };
  const setEvidence = (indicatorId: number, evidence_text: string) => {
    touchedRef.current = true;
    setDrafts((prev) =>
      prev.map((d) => (d.indicator_id === indicatorId ? { ...d, evidence_text } : d))
    );
  };

  // شاخص‌های بی‌امتیاز (باید همه امتیاز بگیرند)
  const unscored = useMemo(() => drafts.filter((d) => d.score === null), [drafts]);

  // نقض قانون شواهد: فقط برای امتیازهای اجباری (پیش‌فرض ۱ و ۵) و متن کوتاه‌تر از حداقل
  const violations = useMemo(() => {
    return drafts.filter(
      (d) => evidenceIsRequired(d.score, config) && wordCount(d.evidence_text) < config.evidence_min_words
    );
  }, [drafts, config]);

  // ثبت وقتی معتبر است که فهرست خالی نباشد، همهٔ شاخص‌ها امتیاز داشته باشند و قانون شواهد رعایت شود.
  const isValid = drafts.length > 0 && unscored.length === 0 && violations.length === 0;

  return { drafts, setScore, setEvidence, violations, unscored, isValid };
}

export interface ScorePreview {
  general_pct: number;
  specialized_pct: number;
  final_pct: number;
}

/** پیش‌نمایش محاسبه امتیازها با همان فرمول سرور — فقط وقتی همهٔ شاخص‌ها امتیاز گرفته باشند.
 * (محاسبه نهایی و معتبر همیشه سمت سرور انجام می‌شود.) */
export function computePreview(
  drafts: ScoreDraft[],
  indicators: Indicator[],
  config: AppConfig = DEFAULT_APP_CONFIG
): ScorePreview | null {
  if (drafts.length === 0 || drafts.some((d) => d.score === null)) return null;
  const sectionById = new Map(indicators.map((i) => [i.id, i.section]));

  let generalSum = 0;
  let generalMax = 0;
  let specializedSum = 0;
  let specializedMax = 0;
  for (const d of drafts) {
    const s = d.score as number;
    if (sectionById.get(d.indicator_id) === "general") {
      generalSum += s;
      generalMax += 5;
    } else {
      specializedSum += s;
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

/** ردیف‌های امتیاز برای ذخیره/ثبت به سرور — شاخص‌های بی‌امتیاز (null) ارسال نمی‌شوند
 * (ستون score در دیتابیس NOT NULL است؛ ذخیرهٔ پیش‌نویس فقط شاخص‌های امتیازگرفته را می‌فرستد). */
export function scoredRows(drafts: ScoreDraft[]) {
  return drafts
    .filter((d) => d.score !== null)
    .map((d) => ({
      indicator_id: d.indicator_id,
      score: d.score as number,
      evidence_text: d.evidence_text || null,
    }));
}

/** اسلایدر امتیازدهی ۱ تا ۵ — کنترل‌شده با pointer/keyboard. در RTL امتیاز ۵ سمت چپ
 * (۰٪) و امتیاز ۱ سمت راست (۱۰۰٪) است. موقعیت thumb در هر رندر به‌صورت درصدی از عرضِ
 * فعلیِ track محاسبه می‌شود (نه پیکسلِ اندازه‌گیری‌شده)، تا با تغییر عرض ستون‌های جدول
 * هرگز از روی track بیرون نزند. حالت null (بی‌امتیاز) با thumb خاکستری در وسط. */
export function SegmentedScore({
  value,
  onChange,
  label,
}: {
  value: number | null;
  onChange: (score: number) => void;
  label?: string;
}) {
  const trackRef = useRef<HTMLDivElement>(null);
  const [dragging, setDragging] = useState(false);

  // درصد موقعیت thumb از لبهٔ چپ: امتیاز ۵ → ۰٪، امتیاز ۱ → ۱۰۰٪.
  const pct = ((5 - (value ?? 3)) / 4) * 100;

  function valueFromClientX(clientX: number): number {
    const rect = trackRef.current!.getBoundingClientRect();
    const frac = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
    return Math.min(5, Math.max(1, Math.round(5 - frac * 4)));
  }

  function onPointerDown(e: React.PointerEvent) {
    e.currentTarget.setPointerCapture?.(e.pointerId);
    setDragging(true);
    onChange(valueFromClientX(e.clientX));
  }
  function onPointerMove(e: React.PointerEvent) {
    if (!dragging) return;
    onChange(valueFromClientX(e.clientX));
  }
  function endDrag(e: React.PointerEvent) {
    setDragging(false);
    e.currentTarget.releasePointerCapture?.(e.pointerId);
  }

  function onKeyDown(e: React.KeyboardEvent) {
    // فلش چپ/بالا امتیاز را زیاد و فلش راست/پایین کم می‌کند (هم‌راستا با جهت RTL track).
    const eff = value ?? 3;
    if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
      e.preventDefault();
      onChange(Math.min(5, eff + 1));
    } else if (e.key === "ArrowRight" || e.key === "ArrowDown") {
      e.preventDefault();
      onChange(Math.max(1, eff - 1));
    } else if (e.key === "Home") {
      e.preventDefault();
      onChange(1);
    } else if (e.key === "End") {
      e.preventDefault();
      onChange(5);
    }
  }

  const isSet = value !== null;
  const color = isSet ? SCORE_TONE_COLOR[value] : "#9ca3af";
  const valueText = isSet ? `${value.toLocaleString("fa-IR")} — ${SCORE_LABELS[value]}` : "امتیازی انتخاب نشده";

  return (
    <div className="w-full max-w-52">
      <div
        role="slider"
        tabIndex={0}
        aria-label={label ?? "امتیاز"}
        aria-valuemin={1}
        aria-valuemax={5}
        aria-valuenow={value ?? undefined}
        aria-valuetext={valueText}
        onKeyDown={onKeyDown}
        title={valueText}
        className="group relative rounded-lg py-2.5 outline-none focus-visible:ring-2 focus-visible:ring-pulse-300"
      >
        {/* track با گرادیانت قرمز→سبز (RTL: قرمز راست، سبز چپ) */}
        <div
          ref={trackRef}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={endDrag}
          onPointerCancel={endDrag}
          className="relative h-2 w-full cursor-pointer touch-none rounded-full"
          style={{
            background: "linear-gradient(to left, #ef4444, #f97316, #f59e0b, #84cc16, #10b981)",
            opacity: isSet ? 1 : 0.5,
          }}
        >
          {/* نقاط پله‌ها */}
          {SCORE_VALUES.map((n) => (
            <span
              key={n}
              aria-hidden
              className="absolute top-1/2 h-1 w-1 rounded-full bg-white/70"
              style={{ left: `${((5 - n) / 4) * 100}%`, transform: "translate(-50%, -50%)" }}
            />
          ))}
          {/* thumb — موقعیت درصدی، همیشه روی track */}
          <div
            aria-hidden
            className={`absolute top-1/2 flex h-[22px] w-[22px] items-center justify-center rounded-full border-[3px] bg-white shadow-md ${
              dragging ? "cursor-grabbing" : "cursor-grab"
            } ${isSet ? "" : "opacity-70"}`}
            style={{
              left: `${pct}%`,
              transform: "translate(-50%, -50%)",
              borderColor: color,
              transition: dragging ? "none" : "left 0.18s ease-out",
            }}
          >
            <span className="h-2 w-2 rounded-full" style={{ background: color }} />
          </div>
        </div>
      </div>
      <div className="mt-1 flex items-center justify-between text-[10px] text-gray-400">
        {SCORE_VALUES.map((n) => (
          <span
            key={n}
            className={isSet && n === value ? "font-bold" : undefined}
            style={isSet && n === value ? { color } : undefined}
          >
            {n.toLocaleString("fa-IR")}
          </span>
        ))}
      </div>
    </div>
  );
}

/** دکمه‌های گسستهٔ ۱ تا ۵ برای موبایل (P2-04).
 *
 * روی موبایل، اسلایدر ابزار غلطی است: کشیدنِ یک thumb ۲۲ پیکسلی با انگشت روی خطِ
 * تولید کار نمی‌کند، و مقیاسِ ۵ مقدارِ *گسسته* اصلاً پیوسته نیست که کشیدن معنا
 * بدهد. پنج دکمهٔ درشت با نامِ خودشان، هم دقیق‌ترند و هم می‌گویند هر عدد یعنی چه —
 * چیزی که اسلایدر فقط بعد از انتخاب نشان می‌دهد.
 *
 * ارتفاع ۴۴ پیکسل کمینهٔ توصیه‌شدهٔ هدف لمسی است؛ کمتر از آن یعنی انتخابِ اشتباه
 * روی نمره‌ای که به تمدید قرارداد یک نفر مربوط است.
 */
function ScoreButtons({
  value,
  onChange,
  label,
}: {
  value: number | null;
  onChange: (score: number) => void;
  label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="grid grid-cols-5 gap-1.5">
      {SCORE_VALUES.map((n) => {
        const selected = value === n;
        return (
          <button
            key={n}
            type="button"
            role="radio"
            aria-checked={selected}
            aria-label={`${n.toLocaleString("fa-IR")} — ${SCORE_LABELS[n]}`}
            onClick={() => onChange(n)}
            className={`flex min-h-11 flex-col items-center justify-center gap-0.5 rounded-xl border-2 px-1 py-1.5 transition-colors ${
              selected ? "text-white" : "border-gray-200 bg-white text-gray-600 active:bg-gray-50"
            }`}
            style={
              selected
                ? { backgroundColor: SCORE_TONE_COLOR[n], borderColor: SCORE_TONE_COLOR[n] }
                : undefined
            }
          >
            <span className="text-base font-bold tabular-nums leading-none">
              {n.toLocaleString("fa-IR")}
            </span>
            <span className="text-[9px] leading-tight opacity-90">{SCORE_LABELS[n]}</span>
          </button>
        );
      })}
    </div>
  );
}

/** شمارندهٔ واژه — قانونِ سرور را *پیش* از رد شدن نشان می‌دهد.
 *
 * قاعده از قبل وجود داشت (نمرهٔ ۱ و ۵ حداقل سه واژه شواهد می‌خواهند) ولی تنها
 * جایی که دیده می‌شد، پیام خطا هنگام ثبت بود — یعنی بعد از نوشتن بیست شاخص. */
function WordCounter({
  count,
  required,
  min,
  max,
}: {
  count: number;
  required: boolean;
  min: number;
  max: number;
}) {
  const short = required && count < min;
  return (
    <p
      className={`mt-1 text-[10px] tabular-nums ${short ? "text-red-600" : "text-gray-400"}`}
      aria-live="polite"
    >
      {short
        ? `${(min - count).toLocaleString("fa-IR")} واژهٔ دیگر لازم است`
        : `${count.toLocaleString("fa-IR")} از ${max.toLocaleString("fa-IR")} واژه`}
    </p>
  );
}

/** سقف نرم واژه‌ها: فقط وقتی از حد گذشت متن کوتاه می‌شود؛ در تایپ عادی متن خام
 *  رد می‌شود تا فاصله‌ها/تایپ مختل نشود. */
export function clampEvidence(raw: string, maxWords: number): string {
  const words = raw.trim().split(/\s+/).filter(Boolean);
  return words.length > maxWords ? words.slice(0, maxWords).join(" ") : raw;
}

interface SectionProps {
  section: "general" | "specialized";
  indicators: Indicator[];
  drafts: ScoreDraft[];
  onScoreChange: (indicatorId: number, score: number) => void;
  onEvidenceChange: (indicatorId: number, text: string) => void;
  readOnly?: boolean;
  config?: AppConfig;
}

/** فهرست کارتی — یک شاخص در هر کارت، برای صفحه‌های باریک (P2-04).
 *
 * جدول چهارستونی روی موبایل به اسکرول افقی تبدیل می‌شد: ارزیاب باید برای دیدن
 * «امتیاز» ستون‌ها را کنار می‌زد و شرح شاخص از دید خارج می‌شد. یعنی نمره‌دادن
 * بدون دیدن چیزی که به آن نمره می‌دهد. کسانی که بیشتر از همه موبایل دارند —
 * مسئول واحدِ سرِ خط تولید، مدیرِ بین دو جلسه — همان‌هایی‌اند که تأخیرشان کل
 * زنجیره را می‌خواباند.
 */
function ScoreCardList({
  section,
  indicators,
  drafts,
  onScoreChange,
  onEvidenceChange,
  readOnly = false,
  config = DEFAULT_APP_CONFIG,
}: SectionProps) {
  const sectionIndicators = indicators.filter((i) => i.section === section);
  const draftByIndicator = new Map(drafts.map((d) => [d.indicator_id, d]));
  const maxWords = config.evidence_max_words ?? 40;

  return (
    <ol className="space-y-3">
      {sectionIndicators.map((ind, index) => {
        const draft = draftByIndicator.get(ind.id);
        if (!draft) return null;
        const count = wordCount(draft.evidence_text);
        const needsEvidence = evidenceIsRequired(draft.score, config);
        const invalid = needsEvidence && count < config.evidence_min_words;
        const scoreLabel =
          draft.score !== null ? SCORE_LABELS[draft.score] : "امتیازی انتخاب نشده";

        return (
          <li
            key={ind.id}
            className={`rounded-2xl border bg-white p-4 shadow-card ${
              invalid ? "border-red-200" : draft.score === null ? "border-amber-200" : "border-gray-100"
            }`}
          >
            <div className="mb-3">
              <p className="flex items-baseline gap-2 text-sm font-bold text-gray-900">
                <span className="shrink-0 text-[11px] font-normal text-gray-400">
                  {(index + 1).toLocaleString("fa-IR")}/
                  {sectionIndicators.length.toLocaleString("fa-IR")}
                </span>
                {ind.category}
              </p>
              <p className="mt-1 text-xs leading-relaxed text-gray-600">{ind.description}</p>
            </div>

            {readOnly ? (
              <span
                className={`inline-flex items-center gap-1.5 rounded-xl px-2.5 py-1 text-sm font-bold ${
                  draft.score !== null
                    ? READONLY_TONE[draft.score] ?? "bg-gray-100 text-gray-700"
                    : "bg-gray-100 text-gray-500"
                }`}
              >
                {draft.score !== null ? draft.score.toLocaleString("fa-IR") : "—"}
                <span className="text-[11px] font-normal opacity-80">{scoreLabel}</span>
              </span>
            ) : (
              <ScoreButtons
                value={draft.score}
                onChange={(score) => onScoreChange(ind.id, score)}
                label={`امتیاز ${ind.category}`}
              />
            )}

            {readOnly ? (
              draft.evidence_text && (
                <p className="mt-3 whitespace-pre-wrap border-t border-gray-50 pt-3 text-xs text-gray-700">
                  {draft.evidence_text}
                </p>
              )
            ) : (
              <div className="mt-3">
                <label className="text-[11px] font-medium text-gray-600">
                  شواهد عینی
                  {needsEvidence && <span className="text-red-500"> *</span>}
                  <textarea
                    className={`mt-1 w-full resize-none rounded-xl border px-3 py-2 text-sm text-gray-800 outline-none transition-colors ${
                      invalid
                        ? "border-red-400 bg-red-50 focus:border-red-500"
                        : "border-gray-200 bg-gray-100 focus:border-pulse-500 focus:bg-white"
                    }`}
                    rows={3}
                    value={draft.evidence_text}
                    onChange={(e) => onEvidenceChange(ind.id, clampEvidence(e.target.value, maxWords))}
                    disabled={!needsEvidence}
                    placeholder={
                      needsEvidence ? "شرح کوتاه شواهد عینی…" : "برای این امتیاز اختیاری است"
                    }
                  />
                </label>
                {needsEvidence && (
                  <WordCounter
                    count={count}
                    required
                    min={config.evidence_min_words}
                    max={maxWords}
                  />
                )}
              </div>
            )}
          </li>
        );
      })}
    </ol>
  );
}

/** فرم امتیازدهی یک بخش — کارت روی موبایل، جدول روی صفحهٔ پهن.
 *
 * فقط *یکی* از دو نسخه رندر می‌شود، نه اینکه هر دو ساخته و یکی با CSS پنهان شود:
 * وقتی محتوا فرم است، نسخهٔ پنهان یعنی هر شاخص دو کنترلِ ورودی دارد. */
export function ScoreFormTable(props: SectionProps) {
  const narrow = useMediaQuery(NARROW_QUERY);
  return narrow ? <ScoreCardList {...props} /> : <ScoreFormTableWide {...props} />;
}

function ScoreFormTableWide({
  section,
  indicators,
  drafts,
  onScoreChange,
  onEvidenceChange,
  readOnly = false,
  config = DEFAULT_APP_CONFIG,
}: SectionProps) {
  const sectionIndicators = indicators.filter((i) => i.section === section);
  const draftByIndicator = new Map(drafts.map((d) => [d.indicator_id, d]));
  const maxWords = config.evidence_max_words ?? 40;

  function handleEvidenceChange(indicatorId: number, raw: string) {
    onEvidenceChange(indicatorId, clampEvidence(raw, maxWords));
  }

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
            const needsEvidence = evidenceIsRequired(draft.score, config);
            const invalid = needsEvidence && count < config.evidence_min_words;
            const scoreLabel = draft.score !== null ? SCORE_LABELS[draft.score] : "امتیازی انتخاب نشده";
            return (
              <tr key={ind.id} className="min-h-16 border-t border-gray-50 align-top transition-colors hover:bg-pulse-50/20">
                <td className="px-3 py-3 font-medium text-gray-800">{ind.category}</td>
                <td className="px-3 py-3 text-gray-600">{ind.description}</td>
                <td className="px-3 py-3">
                  {readOnly ? (
                    <span
                      className={`inline-flex items-center gap-1.5 rounded-xl px-2.5 py-1 text-sm font-bold ${
                        draft.score !== null ? READONLY_TONE[draft.score] ?? "bg-gray-100 text-gray-700" : "bg-gray-100 text-gray-500"
                      }`}
                      title={scoreLabel}
                    >
                      {draft.score !== null ? draft.score.toLocaleString("fa-IR") : "—"}
                      <span className="text-[11px] font-normal opacity-80">{scoreLabel}</span>
                    </span>
                  ) : (
                    <div>
                      <SegmentedScore
                        value={draft.score}
                        onChange={(score) => onScoreChange(ind.id, score)}
                        label={`امتیاز ${ind.category}`}
                      />
                      <p className={`mt-1 text-[11px] ${draft.score === null ? "text-amber-600" : "text-gray-400"}`}>
                        {scoreLabel}
                      </p>
                    </div>
                  )}
                </td>
                <td className="px-3 py-3">
                  {readOnly ? (
                    <span className="whitespace-pre-wrap text-gray-700">{draft.evidence_text || "—"}</span>
                  ) : (
                    <textarea
                      aria-label={`شواهد عینی شاخص: ${ind.category}`}
                      className={`w-full resize-none rounded-xl border px-3 py-2 text-sm text-gray-800 outline-none transition-colors duration-150 ${
                        invalid
                          ? "border-red-400 bg-red-50 focus:border-red-500"
                          : "border-gray-200 bg-gray-100 focus:border-pulse-500 focus:bg-white"
                      }`}
                      rows={2}
                      value={draft.evidence_text}
                      onChange={(e) => handleEvidenceChange(ind.id, e.target.value)}
                      disabled={!needsEvidence}
                      placeholder={
                        needsEvidence
                          ? "شرح کوتاه شواهد عینی…"
                          : "برای این امتیاز اختیاری است"
                      }
                    />
                  )}
                  {/* شمارنده قانونِ سرور را پیش از رد شدن نشان می‌دهد؛ قبلاً تنها
                      جایی که دیده می‌شد، خطای ثبت بود — بعد از نوشتن بیست شاخص. */}
                  {!readOnly && needsEvidence && (
                    <WordCounter
                      count={count}
                      required
                      min={config.evidence_min_words}
                      max={maxWords}
                    />
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
