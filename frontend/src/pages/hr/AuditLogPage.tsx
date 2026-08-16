import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { extractErrorMessage } from "../../api/client";
import {
  useAuditLog,
  useOrgUnits,
  useUsersList,
} from "../../api/queries";
import { AuditIntegrityBadge } from "../../components/AuditIntegrityBadge";
import { ExcelExportButton } from "../../components/ExcelExportButton";
import { PaginationControls } from "../../components/PaginationControls";
import { Card, TableSkeleton } from "../../ui/Card";
import { JalaliDatePicker } from "../../ui/JalaliDatePicker";
import { Table } from "../../ui/Table";
import { EASE_SOFT } from "../../ui/motion";
import { formatDateTime } from "../../utils/dates";
import { AUDIT_EVENT_LABELS, ROLE_LABELS } from "../../types";
import { AuditDetails } from "../../components/AuditDetails";
import { PersonPicker } from "../../components/PersonPicker";
import { useAuth } from "../../auth/AuthContext";

/** پیش‌فرض تعداد در هر صفحه؛ کاربر می‌تواند از نوار پایین عوضش کند. */
const DEFAULT_PAGE_SIZE = 20;

const EVENT_TYPES = Object.keys(AUDIT_EVENT_LABELS);

const filterInputClass =
  "w-full appearance-none rounded-xl border border-gray-200 bg-gray-100 px-3 py-1.5 text-sm text-gray-700 outline-none transition-colors duration-150 focus:border-pulse-500 focus:bg-white";


interface Filters {
  eventType: string;
  createdFrom: string;
  createdTo: string;
  actorUserId: number | "";
  personnelId: number | "";
  orgUnit: string;
  contractEndFrom: string;
  contractEndTo: string;
}

const EMPTY_FILTERS: Filters = {
  eventType: "",
  createdFrom: "",
  createdTo: "",
  actorUserId: "",
  personnelId: "",
  orgUnit: "",
  contractEndFrom: "",
  contractEndTo: "",
};

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

/** گزارش رویدادها با فیلترهای ترکیب‌پذیر: نوع رویداد، بازهٔ تاریخ، انجام‌دهنده،
 * پرسنل مشخص و واحد سازمانی — تا HR بتواند سابقهٔ یک واحد، یک نفر یا یک کاربر خاص
 * را دقیق و جدا مرور کند، نه فقط اسکرول کل رویدادها. */
export function AuditLogPage() {
  const { user } = useAuth();
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);

  const { data: orgUnits = [] } = useOrgUnits(true);
  const { data: usersPage } = useUsersList({ limit: 200 });
  const users = usersPage?.items ?? [];

  const requestParams = {
    event_type: filters.eventType || undefined,
    created_from: filters.createdFrom || undefined,
    created_to: filters.createdTo || undefined,
    actor_user_id: filters.actorUserId || undefined,
    personnel_id: filters.personnelId || undefined,
    org_unit: filters.orgUnit || undefined,
    contract_end_from: filters.contractEndFrom || undefined,
    contract_end_to: filters.contractEndTo || undefined,
  };

  const { data, error: queryError, isPending } = useAuditLog({
    ...requestParams,
    limit: pageSize,
    offset: page * pageSize,
  });
  const error = queryError != null ? extractErrorMessage(queryError) : null;

  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const items = data?.items ?? [];

  const activeFilterCount = Object.values(filters).filter((v) => v !== "").length;

  function patch(next: Partial<Filters>) {
    setFilters((prev) => ({ ...prev, ...next }));
    setPage(0);
  }
  function resetFilters() {
    setFilters(EMPTY_FILTERS);
    setPage(0);
  }

  // پشتیبانی فنی همین صفحه را می‌بیند ولی *دامنهٔ دیدش* را سرور محدود می‌کند:
  // فقط رویدادهای سامانه‌ای، بدون هیچ ردی از محتوای پرونده. تأیید یکپارچگی و
  // خروجی اکسل کل زنجیره را لمس می‌کنند، پس همچنان مالِ منابع انسانی‌اند.
  const isHr = user?.role === "hr";

  return (
    <Card
      title="گزارش رویدادها (Audit Log)"
      actions={
        <div className="flex flex-wrap items-center gap-2">
          {isHr && <AuditIntegrityBadge />}
          {isHr && (
            <ExcelExportButton url="/audit-log/export.xlsx" filename="audit-log.xlsx" params={requestParams} />
          )}
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
      {!isHr && (
        <p className="mb-4 rounded-xl bg-gray-50 px-4 py-3 text-xs leading-relaxed text-gray-600">
          شما رویدادهای <b>سامانه‌ای</b> را می‌بینید: ورود و خروج، قفل حساب، تغییر
          مجوزها، روشن و خاموش کردن بخش‌ها، و اجرای کارهای زمان‌بندی‌شده. رویدادهای
          مربوط به پرونده‌های ارزیابی — از جمله امتیازها — در این نما نیستند.
        </p>
      )}
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
                <PersonPicker
                  value={filters.personnelId || null}
                  onChange={(id) => patch({ personnelId: id ?? "" })}
                  placeholder="همهٔ پرسنل"
                  aria-label="انتخاب پرسنل"
                />
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

              <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
                پایان قرارداد از
                <JalaliDatePicker
                  className={filterInputClass}
                  value={filters.contractEndFrom}
                  onChange={(iso) => patch({ contractEndFrom: iso })}
                />
              </label>
              <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
                پایان قرارداد تا
                <JalaliDatePicker
                  className={filterInputClass}
                  value={filters.contractEndTo}
                  onChange={(iso) => patch({ contractEndTo: iso })}
                />
              </label>

              {/* میان‌برهای «قرارداد رو به اتمام / منقضی» — همان الگوی گزارش‌های تحلیلی */}
              <div className="flex flex-col gap-1 text-xs font-medium text-gray-600 sm:col-span-2 lg:col-span-2">
                میان‌بر قرارداد
                <div className="flex flex-wrap gap-1.5">
                  {[
                    { label: "۳۰ روز آینده", days: 30 },
                    { label: "۹۰ روز آینده", days: 90 },
                  ].map((preset) => (
                    <button
                      key={preset.days}
                      type="button"
                      onClick={() => {
                        const d = new Date();
                        d.setDate(d.getDate() + preset.days);
                        patch({ contractEndFrom: todayIso(), contractEndTo: d.toISOString().slice(0, 10) });
                      }}
                      className="rounded-lg border border-gray-200 bg-white px-2 py-1 text-xs text-gray-600 hover:bg-gray-50"
                    >
                      {preset.label}
                    </button>
                  ))}
                  <button
                    type="button"
                    onClick={() => patch({ contractEndFrom: "", contractEndTo: todayIso() })}
                    className="rounded-lg border border-gray-200 bg-white px-2 py-1 text-xs text-gray-600 hover:bg-gray-50"
                  >
                    منقضی‌شده
                  </button>
                </div>
              </div>

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
                <div key="details" className="max-w-md break-words">
                  <AuditDetails oldValue={entry.old_value} newValue={entry.new_value} />
                </div>,
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
            pageSize={pageSize}
            onPageSizeChange={(size) => {
              setPageSize(size);
              setPage(0);
            }}
            onPageChange={setPage}
          />
        </>
      )}
    </Card>
  );
}
