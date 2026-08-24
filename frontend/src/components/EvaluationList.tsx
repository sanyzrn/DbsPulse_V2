import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "motion/react";
import { extractErrorMessage } from "../api/client";
import { useDebouncedValue, useEvaluations, useOrgUnits } from "../api/queries";
import { STAGE_LABELS, type EvaluationStatus } from "../types";
import { ExcelExportButton } from "./ExcelExportButton";
import { StatusBadge } from "./StatusBadge";
import { PaginationControls } from "./PaginationControls";
import { Table } from "../ui/Table";
import { EmptyState } from "../ui/Card";
import { JalaliDatePicker } from "../ui/JalaliDatePicker";
import { EASE_SOFT, TAB_TRANSITION } from "../ui/motion";
import { SearchInput } from "../ui/SearchInput";

/** پیش‌فرض تعداد در هر صفحه؛ کاربر می‌تواند از نوار پایین عوضش کند. */
const DEFAULT_PAGE_SIZE = 10;

const filterInputClass =
  "w-full rounded-xl border border-gray-200 bg-gray-100 px-3 py-1.5 text-sm text-gray-700 outline-none transition-colors duration-150 focus:border-gray-900 focus:bg-white";

export interface EvaluationListTab {
  /** کلید یکتای تب (برای state داخلی) */
  key: string;
  label: string;
  /** بدون مقدار = بدون فیلتر وضعیت (همهٔ پرونده‌های در دسترس این کاربر) */
  status?: EvaluationStatus;
}

interface AdvancedFilters {
  orgUnit: string;
  dateFrom: string;
  dateTo: string;
  minPct: string;
  maxPct: string;
  /** "" = همه، "true" = فقط برگشتی، "false" = بدون سابقهٔ برگشت */
  returned: "" | "true" | "false";
}

const EMPTY_FILTERS: AdvancedFilters = {
  orgUnit: "",
  dateFrom: "",
  dateTo: "",
  minPct: "",
  maxPct: "",
  returned: "",
};

/** فیلترها → پارامترهای درخواست (فقط مقادیر پرشده). */
function filtersToParams(filters: AdvancedFilters) {
  return {
    org_unit: filters.orgUnit || undefined,
    created_from: filters.dateFrom || undefined,
    created_to: filters.dateTo || undefined,
    min_final_pct: filters.minPct !== "" ? Number(filters.minPct) : undefined,
    max_final_pct: filters.maxPct !== "" ? Number(filters.maxPct) : undefined,
    was_returned: filters.returned === "" ? undefined : filters.returned === "true",
  };
}

/** فهرست پرونده‌های ارزیابی با جست‌وجو، صفحه‌بندی و — در صورت وجود بیش از یک تب —
 * سوییچ وضعیت به‌دست کاربر. با enableAdvancedFilters (مخصوص HR) فیلترهای ترکیبیِ
 * واحد/بازه تاریخ/بازه امتیاز و با enableExcelExport خروجی Excel از همان فیلترهای
 * فعال اضافه می‌شود. */
export function EvaluationList({
  title,
  subtitle,
  tabs,
  enableAdvancedFilters = false,
  enableExcelExport = false,
}: {
  title: string;
  /** یک خط توضیح زیر عنوان — برای وقتی که این فهرست کنار فهرست دیگری می‌نشیند و
   *  باید معلوم باشد کدام‌یک «کار» است و کدام «سابقه». */
  subtitle?: string;
  tabs: EvaluationListTab[];
  enableAdvancedFilters?: boolean;
  enableExcelExport?: boolean;
}) {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [activeTabKey, setActiveTabKey] = useState(tabs[0]!.key);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [filters, setFilters] = useState<AdvancedFilters>(EMPTY_FILTERS);
  const debouncedSearch = useDebouncedValue(search);
  const navigate = useNavigate();

  const activeTab = tabs.find((t) => t.key === activeTabKey) ?? tabs[0]!;
  const activeFilterCount = Object.values(filters).filter((v) => v !== "").length;

  const { data: orgUnits = [] } = useOrgUnits(enableAdvancedFilters);

  const { data, error, isPending } = useEvaluations({
    q: debouncedSearch,
    status: activeTab.status,
    ...filtersToParams(filters),
    limit: pageSize,
    offset: page * pageSize,
  });

  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  function patchFilters(patch: Partial<AdvancedFilters>) {
    setFilters((prev) => ({ ...prev, ...patch }));
    setPage(0);
  }

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-bold text-gray-900">{title}</h2>
          {subtitle && <p className="mt-0.5 text-xs text-gray-400">{subtitle}</p>}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <SearchInput
            widthClass="sm:w-64"
            placeholder="جست‌وجو (نام پرسنل، کد ارزیابی)…"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(0);
            }}
          />
          {enableAdvancedFilters && (
            <button
              type="button"
              onClick={() => setFiltersOpen((v) => !v)}
              className={`inline-flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-sm font-medium transition-colors ${
                filtersOpen || activeFilterCount > 0
                  ? "border-pulse-200 bg-pulse-50 text-pulse-700"
                  : "border-gray-200 bg-white text-gray-600 hover:bg-gray-50"
              }`}
            >
              <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 5h14M6 10h8M8.5 15h3" />
              </svg>
              فیلترها
              {activeFilterCount > 0 && (
                <span className="inline-flex h-4.5 min-w-4.5 items-center justify-center rounded-full bg-pulse-600 px-1 text-[10px] font-bold text-white">
                  {activeFilterCount.toLocaleString("fa-IR")}
                </span>
              )}
            </button>
          )}
          {enableExcelExport && (
            <ExcelExportButton
              url="/evaluations/export.xlsx"
              filename="evaluations.xlsx"
              params={{
                q: debouncedSearch || undefined,
                status: activeTab.status,
                ...filtersToParams(filters),
              }}
            />
          )}
        </div>
      </div>

      {/* نوار فیلترهای پیشرفته — ترکیب‌پذیر؛ خروجی Excel هم از همین‌ها پیروی می‌کند */}
      <AnimatePresence initial={false}>
        {enableAdvancedFilters && filtersOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2, ease: EASE_SOFT }}
            className="overflow-hidden"
          >
            <div className="mb-4 grid grid-cols-1 gap-3 rounded-xl border border-gray-100 bg-gray-50/70 p-3 text-sm sm:grid-cols-2 lg:grid-cols-6">
              <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
                سابقهٔ برگشت
                <select
                  className={filterInputClass}
                  value={filters.returned}
                  onChange={(e) => patchFilters({ returned: e.target.value as AdvancedFilters["returned"] })}
                >
                  <option value="">همهٔ پرونده‌ها</option>
                  <option value="true">فقط برگشتی</option>
                  <option value="false">بدون سابقهٔ برگشت</option>
                </select>
              </label>
              <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
                واحد سازمانی
                <select
                  className={filterInputClass}
                  value={filters.orgUnit}
                  onChange={(e) => patchFilters({ orgUnit: e.target.value })}
                >
                  <option value="">همهٔ واحدها</option>
                  {orgUnits.map((unit) => (
                    <option key={unit} value={unit}>
                      {unit}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
                از تاریخ شروع
                <JalaliDatePicker
                  className={filterInputClass}
                  value={filters.dateFrom}
                  onChange={(iso) => patchFilters({ dateFrom: iso })}
                />
              </label>
              <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
                تا تاریخ شروع
                <JalaliDatePicker
                  className={filterInputClass}
                  value={filters.dateTo}
                  onChange={(iso) => patchFilters({ dateTo: iso })}
                />
              </label>
              <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
                حداقل امتیاز نهایی (٪)
                <input
                  type="number"
                  min={0}
                  max={100}
                  inputMode="numeric"
                  placeholder="مثلاً ۵۰"
                  className={filterInputClass}
                  value={filters.minPct}
                  onChange={(e) => patchFilters({ minPct: e.target.value })}
                />
              </label>
              <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
                حداکثر امتیاز نهایی (٪)
                <input
                  type="number"
                  min={0}
                  max={100}
                  inputMode="numeric"
                  placeholder="مثلاً ۸۰"
                  className={filterInputClass}
                  value={filters.maxPct}
                  onChange={(e) => patchFilters({ maxPct: e.target.value })}
                />
              </label>
              {activeFilterCount > 0 && (
                <div className="flex items-end sm:col-span-2 lg:col-span-6">
                  <button
                    type="button"
                    onClick={() => {
                      setFilters(EMPTY_FILTERS);
                      setPage(0);
                    }}
                    className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700"
                  >
                    <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                      <path d="M5 5l10 10M15 5L5 15" />
                    </svg>
                    حذف همهٔ فیلترها
                  </button>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {tabs.length > 1 && (
        <div
          role="tablist"
          className="mb-4 inline-flex flex-wrap gap-1 rounded-xl border border-gray-100 bg-gray-50 p-1"
        >
          {tabs.map((tab) => (
            <button
              key={tab.key}
              type="button"
              role="tab"
              aria-selected={tab.key === activeTabKey}
              onClick={() => {
                setActiveTabKey(tab.key);
                setPage(0);
              }}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors duration-150 ${
                tab.key === activeTabKey
                  ? "bg-charcoal-900 text-white"
                  : "text-gray-500 hover:text-gray-800"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      )}

      {error != null && (
        <p className="mb-2 text-sm text-red-600">{extractErrorMessage(error)}</p>
      )}

      {/* محتوای تب با تعویض نرم (fade) هنگام جابه‌جایی بین تب‌های وضعیت */}
      <motion.div key={activeTabKey} {...TAB_TRANSITION}>
      {/* اسکلتون بارگذاری */}
      {isPending && (
        <div className="space-y-2">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="skeleton h-10" />
          ))}
        </div>
      )}

      {/* حالت خالی */}
      {data && data.items.length === 0 && <EmptyState />}

      {data && data.items.length > 0 && (
        <>
          <Table
            bordered={false}
            headers={["کد ارزیابی", "پرسنل", "وضعیت", "مرحله", ""]}
            rowKeys={data.items.map((e) => e.id)}
            rows={data.items.map((e) => [
              <span key="code" className="font-medium text-gray-700">
                {e.evaluation_code}
              </span>,
              e.subject_full_name,
              <div key="status" className="flex flex-wrap items-center gap-1.5">
                <StatusBadge status={e.status} />
                {e.was_returned && (
                  <span
                    className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700"
                    title="این پرونده قبلاً حداقل یک‌بار برگشت خورده است"
                  >
                    <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-amber-500" />
                    برگشتی
                  </span>
                )}
              </div>,
              <span key="stage" className="text-gray-500">
                {e.stage ? STAGE_LABELS[e.stage] : "—"}
              </span>,
              <button
                key="action"
                onClick={() => navigate(`/evaluations/${e.id}`)}
                className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-sm font-medium text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-900"
              >
                مشاهده
                <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M13 5l-5 5 5 5" />
                </svg>
              </button>,
            ])}
          />
          <PaginationControls
            page={page}
            totalPages={totalPages}
            totalCount={total}
            pageSize={pageSize}
            onPageSizeChange={(size) => {
              setPageSize(size);
              setPage(0);
            }}
            onPageChange={setPage}
          />
        </>
      )}
      </motion.div>
    </div>
  );
}
