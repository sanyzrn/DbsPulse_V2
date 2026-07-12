/** دکمهٔ اقدام روی هر ردیف پرسنل در صفحات مسئول واحد/معاونت: اگر ارزیابی بازی
 * از قبل وجود دارد به همان پرونده می‌رود، وگرنه ارزیابی جدید می‌سازد. پیش‌تر این
 * منطق در هر دو صفحه جداگانه کپی شده بود. */
export function EvaluationActionButton({
  open,
  starting,
  isStartingThis,
  onContinue,
  onStart,
}: {
  open: { id: number; code: string } | undefined;
  starting: boolean;
  isStartingThis: boolean;
  onContinue: (evaluationId: number) => void;
  onStart: () => void;
}) {
  if (open) {
    return (
      <button
        onClick={() => onContinue(open.id)}
        title={`ارزیابی باز موجود است: ${open.code}`}
        className="inline-flex items-center gap-1.5 rounded-xl bg-gray-100 px-3 py-1.5 text-sm font-medium text-gray-600 transition-all duration-300 ease-out hover:bg-gray-200"
      >
        {/* RTL: فلش «ادامه» به سمت چپ (جهت پیشروی) است */}
        <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M16 10H4M10 4l-6 6 6 6" />
        </svg>
        ادامه ارزیابی باز
      </button>
    );
  }
  return (
    <button
      onClick={onStart}
      disabled={starting}
      className="inline-flex items-center gap-1.5 rounded-xl bg-pulse-50 px-3 py-1.5 text-sm font-medium text-pulse-700 transition-all duration-300 ease-out hover:shadow-md disabled:opacity-50"
    >
      {isStartingThis ? (
        <>
          <span className="h-3 w-3 animate-spin rounded-full border-2 border-pulse-300 border-t-pulse-600" />
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
