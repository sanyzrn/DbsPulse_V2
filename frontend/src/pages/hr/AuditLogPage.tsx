import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { extractErrorMessage } from "../../api/client";
import {
  useAuditLog,
  useDebouncedValue,
  useOrgUnits,
  usePersonnelList,
  useUsersList,
} from "../../api/queries";
import { ExcelExportButton } from "../../components/ExcelExportButton";
import { PaginationControls } from "../../components/PaginationControls";
import { Card, TableSkeleton } from "../../ui/Card";
import { JalaliDatePicker } from "../../ui/JalaliDatePicker";
import { Table } from "../../ui/Table";
import { EASE_SOFT } from "../../ui/motion";
import { formatDateTime } from "../../utils/dates";
import { AUDIT_EVENT_LABELS, ROLE_LABELS, type AuditLogEntry } from "../../types";

const PAGE_SIZE = 20;

const EVENT_TYPES = Object.keys(AUDIT_EVENT_LABELS);

const filterInputClass =
  "w-full appearance-none rounded-xl border border-gray-200 bg-gray-100 px-3 py-1.5 text-sm text-gray-700 outline-none transition-colors duration-150 focus:border-pulse-500 focus:bg-white";

function formatDetails(entry: AuditLogEntry): string {
  const parts: string[] = [];
  if (entry.old_value) parts.push(`قبل: ${JSON.stringify(entry.old_value)}`);
  if (entry.new_value) parts.push(`بعد: ${JSON.stringify(entry.new_value)}`);
  return parts.join(" — ");
}

interface Filters {
  eventType: string;
  createdFrom: string;
  createdTo: string;
  actorUserId: number | "";
  personnelId: number | "";
  orgUnit: string;
}

const EMPTY_FILTERS: Filters = {
  eventType: "",
  createdFrom: "",
  createdTo: "",
  actorUserId: "",
  personnelId: "",
  orgUnit: "",
};

/** گزارش رویدادها با فیلترهای ترکیب‌پذیر: نوع رویداد، بازهٔ تاریخ، انجام‌دهنده،
 * پرسنل مشخص و واحد سازمانی — تا HR بتواند سابقهٔ یک واحد، یک نفر یا یک کاربر خاص
 * را دقیق و جدا مرور کند، نه فقط اسکرول کل رویدادها. */
export function AuditLogPage() {
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [personnelSearch, setPersonnelSearch] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [page, setPage] = useState(0);
  const debouncedPersonnelSearch = useDebouncedValue(personnelSearch);

  const { data: orgUnits = [] } = useOrgUnits(true);
  const { data: usersPage } = useUsersList({ limit: 200 });
  const users = usersPage?.items ?? [];
  const { data: personnelResults } = usePersonnelList({
    q: debouncedPersonnelSearch,
    limit: 30,
    offset: 0,
  });
  const personnelOptions = personnelResults?.items ?? [];
  const selectedPersonName = personnelOptions.find((p) => p.id === filters.personnelId)?.full_name;

  const requestParams = {
    event_type: filters.eventType || undefined,
    created_from: filters.createdFrom || undefined,
    created_to: filters.createdTo || undefined,
    actor_user_id: filters.actorUserId || undefined,
    personnel_id: filters.personnelId || undefined,
    org_unit: filters.orgUnit || undefined,
  };

  const { data, error: queryError, isPending } = useAuditLog({
    ...requestParams,
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  });
  const error = queryError != null ? extractErrorMessage(queryError) : null;

  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const items = data?.items ?? [];

  const activeFilterCount = Object.values(filters).filter((v) => v !== "").length;

  function patch(next: Partial<Filters>) {
    setFilters((prev) => ({ ...prev, ...next }));
    setPage(0);
  }
  function resetFilters() {
    setFilters(EMPTY_FILTERS);
    setPersonnelSearch("");
    setPage(0);
  }

  return (
    <Card
      title="گزارش رویدادها (Audit Log)"
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <ExcelExportButton url="/audit-log/export.xlsx" filename="audit-log.xlsx" params={requestParams} />
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
        </div>
      }
    >
      <AnimatePresence initial={false}>
        {filtersOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2, ease: EASE_SOFT }}
            className="overflow-hidden"
          >
            <div className="mb-4 grid grid-cols-1 gap-3 rounded-xl border border-gray-100 bg-gray-50/70 p-3 text-sm sm:grid-cols-2 lg:grid-cols-6">
              <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
                نوع رویداد
                <select
                  aria-label="فیلتر نوع رویداد"
                  className={filterInputClass}
                  value={filters.eventType}
                  onChange={(e) => patch({ eventType: e.target.value })}
                >
                  <option value="">همه رویدادها</option>
                  {EVENT_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {AUDIT_EVENT_LABELS[t]}
                    </option>
                  ))}
                </select>
              </label>

              <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
                انجام‌دهنده
                <select
                  aria-label="فیلتر انجام‌دهنده"
                  className={filterInputClass}
                  value={filters.actorUserId}
                  onChange={(e) => patch({ actorUserId: e.target.value ? Number(e.target.value) : "" })}
                >
                  <option value="">همهٔ کاربران</option>
                  {users.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.username} ({ROLE_LABELS[u.role]})
                    </option>
                  ))}
                </select>
              </label>

              <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
                واحد سازمانی
                <select
                  aria-label="فیلتر واحد سازمانی"
                  className={filterInputClass}
                  value={filters.orgUnit}
                  onChange={(e) => patch({ orgUnit: e.target.value })}
                >
                  <option value="">همهٔ واحدها</option>
                  {orgUnits.map((unit) => (
                    <option key={unit} value={unit}>
                      {unit}
                    </option>
                  ))}
                </select>
              </label>

              <div className="flex flex-col gap-1 text-xs font-medium text-gray-600">
                پرسنل مشخص
                <input
                  className={filterInputClass}
                  placeholder="جست‌وجوی نام…"
                  value={personnelSearch}
                  onChange={(e) => setPersonnelSearch(e.target.value)}
                />
                <select
                  aria-label="انتخاب پرسنل"
                  className={filterInputClass}
                  value={filters.personnelId}
                  onChange={(e) => patch({ personnelId: e.target.value ? Number(e.target.value) : "" })}
                >
                  <option value="">همهٔ پرسنل</option>
                  {filters.personnelId && selectedPersonName && !personnelOptions.some((p) => p.id === filters.personnelId) && (
                    <option value={filters.personnelId}>{selectedPersonName}</option>
                  )}
                  {personnelOptions.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.full_name} ({p.org_unit})
                    </option>
                  ))}
                </select>
              </div>

              <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
                از تاریخ
                <JalaliDatePicker
                  className={filterInputClass}
                  value={filters.createdFrom}
                  onChange={(iso) => patch({ createdFrom: iso })}
                />
              </label>
              <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
                تا تاریخ
                <JalaliDatePicker
                  className={filterInputClass}
                  value={filters.createdTo}
                  onChange={(iso) => patch({ createdTo: iso })}
                />
              </label>

              {activeFilterCount > 0 && (
                <div className="flex items-end sm:col-span-2 lg:col-span-6">
                  <button
                    type="button"
                    onClick={resetFilters}
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

      {isPending ? (
        <TableSkeleton rows={8} />
      ) : (
        <>
          {items.length > 0 && (
            <Table
              bordered={false}
              cellAlign="top"
              headers={["زمان", "رویداد", "انجام‌دهنده", "کد ارزیابی", "جزئیات"]}
              rowKeys={items.map((entry) => entry.id)}
              rows={items.map((entry) => [
                <span key="time" className="whitespace-nowrap text-gray-500">
                  {formatDateTime(entry.created_at)}
                </span>,
                <span key="event" className="inline-flex items-center rounded-lg bg-pulse-50 px-2 py-0.5 text-xs font-medium text-pulse-700">
                  {AUDIT_EVENT_LABELS[entry.event_type] ?? entry.event_type}
                </span>,
                entry.actor_username ?? `#${entry.actor_user_id}`,
                <span key="code" className="text-gray-500">
                  {entry.evaluation_code ?? "—"}
                </span>,
                <span key="details" className="block max-w-md break-words text-xs text-gray-500">
                  {formatDetails(entry)}
                </span>,
              ])}
            />
          )}

          {error && <p className="mt-4 text-center text-sm text-red-600">{error}</p>}
          {!error && items.length === 0 && (
            <p className="mt-4 text-center text-sm text-gray-400">رویدادی یافت نشد.</p>
          )}

          <PaginationControls
            page={page}
            totalPages={totalPages}
            totalCount={total}
            pageSize={PAGE_SIZE}
            onPageChange={setPage}
          />
        </>
      )}
    </Card>
  );
}
