import type { EvaluationStatus } from "../types";

export interface OpenEvaluation {
  id: number;
  code: string;
  status: EvaluationStatus;
}

/** دکمهٔ اقدام روی هر ردیف پرسنل در صفحات مسئول واحد/معاونت.
 *
 *  سه حالت دارد، نه دو تا. حالت سومی که تا امروز نبود مهم‌ترینشان است: پرونده‌ای
 *  که **باز است ولی دست این کاربر نیست** — ثبت شده و رفته بالا. دکمه برایش
 *  «ادامه ارزیابی» می‌نوشت و کاربر را به صفحه‌ای می‌برد که هیچ کاری در آن
 *  نمی‌توانست بکند. حالا صریح می‌گوید پرونده در جریان است و فقط نشانش می‌دهد.
 */
export function EvaluationActionButton({
  open,
  starting,
  isStartingThis,
  onContinue,
  onStart,
}: {
  open: OpenEvaluation | undefined;
  starting: boolean;
  isStartingThis: boolean;
  onContinue: (evaluationId: number) => void;
  onStart: () => void;
}) {
  if (open) {
    const mine = open.status === "draft";
    return (
      <button
        onClick={() => onContinue(open.id)}
        title={
          mine
            ? `پیش‌نویس باز: ${open.code}`
            : `پروندهٔ در جریان: ${open.code} — در مرحله‌ای بالاتر از شماست`
        }
        className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 px-3 py-1.5 text-sm font-medium text-gray-600 transition-colors hover:bg-gray-50 hover:text-gray-900"
      >
        {mine ? (
          <>
            {/* RTL: فلش «ادامه» به سمت چپ (جهت پیشروی) است */}
            <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M16 10H4M10 4l-6 6 6 6" />
            </svg>
            ادامهٔ پیش‌نویس
          </>
        ) : (
          <>
            <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M2 10s3-5 8-5 8 5 8 5-3 5-8 5-8-5-8-5z" />
              <circle cx="10" cy="10" r="2.2" />
            </svg>
            مشاهدهٔ پروندهٔ در جریان
          </>
        )}
      </button>
    );
  }
  return (
    <button
      onClick={onStart}
      disabled={starting}
      // دکمهٔ تو‌پرِ قرمز در یک جدولِ ده‌ردیفی، ده کنشِ «اصلی» می‌سازد و صفحه را
      // به یک دیوار قرمز تبدیل می‌کند. قرمز اینجا فقط در متن و مرز می‌نشیند.
      className="inline-flex items-center gap-1.5 rounded-lg border border-pulse-200 px-3 py-1.5 text-sm font-medium text-pulse-700 transition-colors hover:bg-pulse-50 disabled:opacity-50"
    >
      {isStartingThis ? (
        <>
          <span className="h-3 w-3 animate-spin rounded-full border-2 border-pulse-200 border-t-pulse-600" />
          در حال ایجاد…
        </>
      ) : (
        <>
          <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M10 4v12M4 10h12" />
          </svg>
          شروع ارزیابی جدید
        </>
      )}
    </button>
  );
}
