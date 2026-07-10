import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  JALALI_MONTH_NAMES,
  JALALI_WEEKDAY_LABELS,
  isoToJalali,
  jalaliMonthLength,
  jalaliToIso,
  jalaliWeekday,
  toPersianDigits,
  todayJalali,
} from "../utils/jalali";

type PickerMode = "days" | "months" | "years";

/**
 * انتخاب‌گر تاریخ شمسی (جلالی).
 *
 * مقدار ورودی/خروجی همچنان به‌صورت رشته‌ی میلادی استاندارد ISO ("YYYY-MM-DD")
 * است — دقیقاً همان قالبی که <input type="date"> تولید می‌کرد — تا نیازی به
 * تغییر در API یا پایگاه‌داده نباشد. فقط نمایش و ورودی برای کاربر شمسی است.
 *
 * سه حالت داخلی دارد: روز / ماه / سال. با کلیک روی نام ماه یا سال در هدر، به
 * شبکهٔ انتخاب سریع می‌رود تا کاربر بدون کلیک‌های پیاپی به سال‌های دور بپرد.
 */
export function JalaliDatePicker({
  value,
  onChange,
  required,
  className,
  placeholder = "انتخاب تاریخ",
  disabled,
}: {
  value: string;
  onChange: (iso: string) => void;
  required?: boolean;
  className?: string;
  placeholder?: string;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<PickerMode>("days");
  const containerRef = useRef<HTMLDivElement>(null);

  const selectedJalali = useMemo(() => isoToJalali(value), [value]);
  const [viewYear, setViewYear] = useState(() => (selectedJalali ?? todayJalali()).jy);
  const [viewMonth, setViewMonth] = useState(() => (selectedJalali ?? todayJalali()).jm);
  // شروع پنجرهٔ ۱۲ سالهٔ حالت انتخاب سال
  const [yearWindowStart, setYearWindowStart] = useState(() => viewYear - 5);

  useEffect(() => {
    if (selectedJalali) {
      setViewYear(selectedJalali.jy);
      setViewMonth(selectedJalali.jm);
    }
  }, [selectedJalali?.jy, selectedJalali?.jm, selectedJalali?.jd]);

  useEffect(() => {
    if (!open) return;
    function onClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onClickOutside);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  // با هر بار بازشدن، از حالت روز شروع کن
  function toggleOpen() {
    setOpen((v) => {
      if (!v) setMode("days");
      return !v;
    });
  }

  const displayValue = selectedJalali
    ? toPersianDigits(
        `${selectedJalali.jy}/${String(selectedJalali.jm).padStart(2, "0")}/${String(selectedJalali.jd).padStart(2, "0")}`
      )
    : "";

  function goMonth(delta: number) {
    let m = viewMonth + delta;
    let y = viewYear;
    if (m < 1) {
      m = 12;
      y -= 1;
    } else if (m > 12) {
      m = 1;
      y += 1;
    }
    setViewYear(y);
    setViewMonth(m);
  }

  function pickDay(jd: number) {
    onChange(jalaliToIso(viewYear, viewMonth, jd));
    setOpen(false);
  }

  function openYears() {
    setYearWindowStart(viewYear - 5);
    setMode("years");
  }

  const daysInMonth = jalaliMonthLength(viewYear, viewMonth);
  const firstWeekday = jalaliWeekday(viewYear, viewMonth, 1); // 0=شنبه ... 6=جمعه
  const cells: (number | null)[] = [
    ...Array.from({ length: firstWeekday }, () => null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ];

  const today = todayJalali();
  const years = Array.from({ length: 12 }, (_, i) => yearWindowStart + i);

  const crossfade = {
    initial: { opacity: 0, y: 4 },
    animate: { opacity: 1, y: 0 },
    exit: { opacity: 0, y: -4 },
    transition: { duration: 0.15, ease: "easeOut" as const },
  };

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        disabled={disabled}
        onClick={toggleOpen}
        aria-haspopup="dialog"
        aria-expanded={open}
        className={
          className ??
          "field-trigger w-full rounded-xl border border-gray-200 bg-gray-100 px-3 py-2 text-right text-sm text-gray-900 outline-none transition-colors duration-150 focus:border-pulse-500 focus:bg-white disabled:cursor-not-allowed disabled:bg-gray-50 disabled:text-gray-400"
        }
      >
        <span className={displayValue ? "" : "text-gray-400"}>{displayValue || placeholder}</span>
      </button>
      {/* ورودی مخفی برای حفظ رفتار required در فرم‌های HTML */}
      {required && (
        <input tabIndex={-1} aria-hidden="true" className="sr-only" required value={value} onChange={() => {}} />
      )}

      <AnimatePresence>
        {open && (
          <motion.div
            role="dialog"
            aria-label="انتخاب تاریخ"
            className="absolute z-40 mt-1.5 w-72 overflow-hidden rounded-2xl border border-gray-100 bg-white shadow-float ring-1 ring-black/5"
            initial={{ opacity: 0, y: -6, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.97 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
          >
            {/* ── هدر ──
                RTL: اولین فرزند در سمت راست قرار می‌گیرد. طبق قرارداد تقویم فارسی،
                فلش سمت راست = ماه قبل و فلش سمت چپ = ماه بعد. */}
            <div className="flex items-center justify-between border-b border-gray-100 px-2 py-2">
              <button
                type="button"
                onClick={() => goMonth(-1)}
                aria-label="ماه قبل"
                className="rounded-lg p-1.5 text-gray-500 transition-colors hover:bg-gray-100 hover:text-pulse-700"
              >
                {/* فلش راست (›) — به گذشته */}
                <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M8 4l6 6-6 6" />
                </svg>
              </button>

              <div className="flex items-center gap-1 text-sm font-bold text-gray-900">
                <button
                  type="button"
                  onClick={() => setMode((m) => (m === "months" ? "days" : "months"))}
                  className="rounded-lg px-2 py-0.5 transition-colors hover:bg-pulse-50 hover:text-pulse-700"
                >
                  {JALALI_MONTH_NAMES[viewMonth - 1]}
                </button>
                <button
                  type="button"
                  onClick={() => (mode === "years" ? setMode("days") : openYears())}
                  className="rounded-lg px-2 py-0.5 transition-colors hover:bg-pulse-50 hover:text-pulse-700"
                >
                  {toPersianDigits(viewYear)}
                </button>
              </div>

              <button
                type="button"
                onClick={() => goMonth(1)}
                aria-label="ماه بعد"
                className="rounded-lg p-1.5 text-gray-500 transition-colors hover:bg-gray-100 hover:text-pulse-700"
              >
                {/* فلش چپ (‹) — به آینده */}
                <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 4l-6 6 6 6" />
                </svg>
              </button>
            </div>

            <AnimatePresence mode="wait">
              {mode === "days" && (
                <motion.div key="days" {...crossfade}>
                  <div className="grid grid-cols-7 gap-0.5 px-2 pt-2 text-center text-[11px] font-medium text-gray-400">
                    {JALALI_WEEKDAY_LABELS.map((label, i) => (
                      <div key={i}>{label}</div>
                    ))}
                  </div>
                  <div className="grid grid-cols-7 gap-0.5 px-2 pb-2 pt-1">
                    {cells.map((jd, idx) => {
                      if (jd === null) return <div key={`empty-${idx}`} />;
                      const isSelected =
                        selectedJalali && selectedJalali.jy === viewYear && selectedJalali.jm === viewMonth && selectedJalali.jd === jd;
                      const isToday = today.jy === viewYear && today.jm === viewMonth && today.jd === jd;
                      return (
                        <button
                          key={jd}
                          type="button"
                          onClick={() => pickDay(jd)}
                          className={`flex h-8 w-8 items-center justify-center rounded-lg text-xs transition-colors ${
                            isSelected
                              ? "bg-pulse-600 font-bold text-white"
                              : isToday
                                ? "font-bold text-pulse-700 ring-1 ring-inset ring-pulse-200"
                                : "text-gray-700 hover:bg-gray-100"
                          }`}
                        >
                          {toPersianDigits(jd)}
                        </button>
                      );
                    })}
                  </div>
                </motion.div>
              )}

              {mode === "months" && (
                <motion.div key="months" {...crossfade} className="grid grid-cols-3 gap-1 p-2">
                  {JALALI_MONTH_NAMES.map((name, i) => {
                    const m = i + 1;
                    const isCurrent = m === viewMonth;
                    return (
                      <button
                        key={name}
                        type="button"
                        onClick={() => {
                          setViewMonth(m);
                          setMode("days");
                        }}
                        className={`flex h-11 items-center justify-center rounded-xl text-sm transition-colors ${
                          isCurrent
                            ? "bg-pulse-600 font-bold text-white"
                            : "text-gray-700 hover:bg-gray-100"
                        }`}
                      >
                        {name}
                      </button>
                    );
                  })}
                </motion.div>
              )}

              {mode === "years" && (
                <motion.div key="years" {...crossfade} className="p-2">
                  <div className="mb-1 flex items-center justify-between px-1">
                    <button
                      type="button"
                      onClick={() => setYearWindowStart((s) => s - 12)}
                      aria-label="سال‌های قبل"
                      className="rounded-lg p-1 text-gray-500 transition-colors hover:bg-gray-100 hover:text-pulse-700"
                    >
                      <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M8 4l6 6-6 6" />
                      </svg>
                    </button>
                    <span className="text-xs font-medium text-gray-500">
                      {toPersianDigits(yearWindowStart)} – {toPersianDigits(yearWindowStart + 11)}
                    </span>
                    <button
                      type="button"
                      onClick={() => setYearWindowStart((s) => s + 12)}
                      aria-label="سال‌های بعد"
                      className="rounded-lg p-1 text-gray-500 transition-colors hover:bg-gray-100 hover:text-pulse-700"
                    >
                      <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M12 4l-6 6 6 6" />
                      </svg>
                    </button>
                  </div>
                  <div className="grid grid-cols-3 gap-1">
                    {years.map((y) => {
                      const isCurrent = y === viewYear;
                      return (
                        <button
                          key={y}
                          type="button"
                          onClick={() => {
                            setViewYear(y);
                            setMode("days");
                          }}
                          className={`flex h-11 items-center justify-center rounded-xl text-sm transition-colors ${
                            isCurrent
                              ? "bg-pulse-600 font-bold text-white"
                              : "text-gray-700 hover:bg-gray-100"
                          }`}
                        >
                          {toPersianDigits(y)}
                        </button>
                      );
                    })}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            <div className="flex justify-between border-t border-gray-100 px-3 py-2">
              <button
                type="button"
                onClick={() => {
                  const t = todayJalali();
                  onChange(jalaliToIso(t.jy, t.jm, t.jd));
                  setOpen(false);
                }}
                className="text-xs font-medium text-pulse-600 hover:underline"
              >
                امروز
              </button>
              {value && (
                <button
                  type="button"
                  onClick={() => {
                    onChange("");
                    setOpen(false);
                  }}
                  className="text-xs font-medium text-gray-400 hover:text-gray-600 hover:underline"
                >
                  پاک کردن
                </button>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
