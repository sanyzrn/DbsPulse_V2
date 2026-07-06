export function PaginationControls({
  page,
  totalPages,
  totalCount,
  pageSize,
  onPageChange,
}: {
  page: number;
  totalPages: number;
  totalCount: number;
  pageSize: number;
  onPageChange: (page: number) => void;
}) {
  if (totalCount <= pageSize) return null;

  return (
    <div className="mt-4 flex items-center justify-between text-sm">
      <span className="text-gray-500">{totalCount.toLocaleString("fa-IR")} مورد</span>
      <div className="flex items-center gap-2">
        <button
          disabled={page === 0}
          onClick={() => onPageChange(page - 1)}
          className="flex h-9 w-9 items-center justify-center rounded-xl border border-gray-200 bg-white font-medium text-gray-700 shadow-sm transition-all duration-200 hover:bg-gray-50 hover:shadow-md disabled:pointer-events-none disabled:opacity-40"
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
          className="flex h-9 w-9 items-center justify-center rounded-xl border border-gray-200 bg-white font-medium text-gray-700 shadow-sm transition-all duration-200 hover:bg-gray-50 hover:shadow-md disabled:pointer-events-none disabled:opacity-40"
          aria-label="صفحه بعد"
        >
          <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M13 5l-5 5 5 5" />
          </svg>
        </button>
      </div>
    </div>
  );
}
