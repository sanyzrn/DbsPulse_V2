/** نوار صفحه‌بندی: تعداد کل، انتخاب تعداد در هر صفحه، و رفتن به صفحهٔ بعد/قبل.
 *
 * انتخابگر تعداد کنار «۲۱ مورد» نشسته، چون همان‌جاست که کاربر می‌فهمد فهرست از
 * یک صفحه بیشتر است.
 *
 * و به همین دلیل، نوار دیگر وقتی همه‌چیز در یک صفحه جا می‌شود ناپدید نمی‌شود:
 * اگر می‌شد، کسی که تعداد را روی ۵۰ گذاشته و حالا ۲۱ مورد دارد، راهی برای
 * برگرداندنش به ۱۰ نداشت — کنترل خودش را پنهان می‌کرد.
 */
export const PAGE_SIZE_OPTIONS = [10, 20, 50, 100] as const;

export function PaginationControls({
  page,
  totalPages,
  totalCount,
  pageSize,
  onPageChange,
  onPageSizeChange,
}: {
  page: number;
  totalPages: number;
  totalCount: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  /** اگر داده نشود، انتخابگر تعداد نمایش داده نمی‌شود. */
  onPageSizeChange?: (pageSize: number) => void;
}) {
  const multiplePages = totalPages > 1;
  // فهرست کوتاه‌تر از کوچک‌ترین گزینه، انتخابگر هم لازم ندارد.
  const canResize = onPageSizeChange && totalCount > PAGE_SIZE_OPTIONS[0];
  if (!multiplePages && !canResize) return null;

  return (
    <div className="mt-3 flex flex-wrap items-center justify-between gap-3 text-sm">
      <div className="flex items-center gap-3">
        <span className="text-gray-500">{totalCount.toLocaleString("fa-IR")} مورد</span>
        {canResize && (
          <label className="flex items-center gap-1.5 text-xs text-gray-500">
            نمایش
            <select
              value={pageSize}
              onChange={(e) => onPageSizeChange(Number(e.target.value))}
              aria-label="تعداد نمایش در هر صفحه"
              className="rounded-lg border border-gray-200 bg-white px-2 py-1 text-xs text-gray-700 outline-none transition-colors focus:border-gray-900"
            >
              {PAGE_SIZE_OPTIONS.map((size) => (
                <option key={size} value={size}>
                  {size.toLocaleString("fa-IR")}
                </option>
              ))}
            </select>
            در صفحه
          </label>
        )}
      </div>

      {multiplePages && (
        <div className="flex items-center gap-2">
          <button
            disabled={page === 0}
            onClick={() => onPageChange(page - 1)}
            className="flex h-8 w-8 items-center justify-center rounded-xl border border-gray-200 bg-white font-medium text-gray-700 transition-colors duration-150 hover:bg-gray-50 disabled:pointer-events-none disabled:opacity-40"
            aria-label="صفحه قبل"
          >
            <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M7 5l5 5-5 5" />
            </svg>
          </button>
          <span className="min-w-24 text-center text-gray-500">
            صفحه {(page + 1).toLocaleString("fa-IR")} از {totalPages.toLocaleString("fa-IR")}
          </span>
          <button
            disabled={page + 1 >= totalPages}
            onClick={() => onPageChange(page + 1)}
            className="flex h-8 w-8 items-center justify-center rounded-xl border border-gray-200 bg-white font-medium text-gray-700 transition-colors duration-150 hover:bg-gray-50 disabled:pointer-events-none disabled:opacity-40"
            aria-label="صفحه بعد"
          >
            <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M13 5l-5 5 5 5" />
            </svg>
          </button>
        </div>
      )}
    </div>
  );
}
