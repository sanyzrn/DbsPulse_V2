/** پیش‌نویسِ یک فرم، در مرورگر خودِ کاربر.
 *
 * برای فرم‌هایی که پرکردنشان وقت می‌برد و ثبتشان برگشت‌ناپذیر است. تنها هدفش
 * این است که یک رفرش یا یک «بازگشت» اشتباهی، کار نیمه‌تمام را نبرد.
 *
 * عمداً روی سرور ذخیره نمی‌شود: پیش‌نویسِ خودارزیابی هنوز حرفِ کسی نیست و
 * نباید جایی برود که ارزیاب ببیندش. مرورگر خودِ فرد، دقیقاً همان‌جاست.
 */
import { useCallback, useState } from "react";

export interface FormDraft {
  scores: Record<number, number>;
  notes: Record<number, string>;
  overallNote: string;
}

const EMPTY: FormDraft = { scores: {}, notes: {}, overallNote: "" };

function read(key: string): FormDraft {
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return EMPTY;
    const parsed = JSON.parse(raw) as Partial<FormDraft>;
    // شکلِ ذخیره‌شده ممکن است از نسخهٔ قبلیِ همین فرم باشد؛ هر فیلدِ غایب یا
    // بدشکل به مقدار خالی برمی‌گردد تا یک پیش‌نویسِ کهنه صفحه را نشکند.
    return {
      scores: typeof parsed.scores === "object" && parsed.scores ? parsed.scores : {},
      notes: typeof parsed.notes === "object" && parsed.notes ? parsed.notes : {},
      overallNote: typeof parsed.overallNote === "string" ? parsed.overallNote : "",
    };
  } catch {
    // حافظهٔ پر، حالت ناشناس، یا JSON خراب — هیچ‌کدام نباید فرم را از کار بیندازند.
    return EMPTY;
  }
}

export function useLocalDraft(key: string): [FormDraft, (next: FormDraft) => void] {
  const [draft, setDraft] = useState<FormDraft>(() => read(key));

  const update = useCallback(
    (next: FormDraft) => {
      setDraft(next);
      try {
        window.localStorage.setItem(key, JSON.stringify(next));
      } catch {
        // نوشتن نشد (حافظه پر یا ذخیره‌سازی مسدود) — فرم در حافظهٔ صفحه سالم
        // می‌ماند و فقط تضمینِ «بعد از رفرش هست» را از دست می‌دهیم.
      }
    },
    [key]
  );

  return [draft, update];
}
