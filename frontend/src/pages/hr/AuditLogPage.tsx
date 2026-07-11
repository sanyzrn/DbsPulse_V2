import { useState } from "react";
import { extractErrorMessage } from "../../api/client";
import { useAuditLog } from "../../api/queries";
import { ExcelExportButton } from "../../components/ExcelExportButton";
import { PaginationControls } from "../../components/PaginationControls";
import { Card, TableSkeleton } from "../../ui/Card";
import { JalaliDatePicker } from "../../ui/JalaliDatePicker";
import { Table } from "../../ui/Table";
import { formatDateTime } from "../../utils/dates";
import { AUDIT_EVENT_LABELS, type AuditLogEntry } from "../../types";

const PAGE_SIZE = 20;

const EVENT_TYPES = Object.keys(AUDIT_EVENT_LABELS);

const filterSelectClass =
  "appearance-none rounded-xl border border-gray-200 bg-gray-100 py-1.5 pr-3 pl-8 text-sm text-gray-700 outline-none transition-colors duration-150 focus:border-pulse-500 focus:bg-white";

function formatDetails(entry: AuditLogEntry): string {
  const parts: string[] = [];
  if (entry.old_value) parts.push(`قبل: ${JSON.stringify(entry.old_value)}`);
  if (entry.new_value) parts.push(`بعد: ${JSON.stringify(entry.new_value)}`);
  return parts.join(" — ");
}

export function AuditLogPage() {
  const [eventType, setEventType] = useState("");
  const [createdFrom, setCreatedFrom] = useState("");
  const [createdTo, setCreatedTo] = useState("");
  const [page, setPage] = useState(0);

  const { data, error: queryError, isPending } = useAuditLog({
    event_type: eventType,
    created_from: createdFrom || undefined,
    created_to: createdTo || undefined,
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  });
  const error = queryError != null ? extractErrorMessage(queryError) : null;

  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const items = data?.items ?? [];

  const exportParams = {
    event_type: eventType || undefined,
    created_from: createdFrom || undefined,
    created_to: createdTo || undefined,
  };

  const hasActiveFilter = Boolean(eventType || createdFrom || createdTo);

  function resetFilters() {
    setEventType("");
    setCreatedFrom("");
    setCreatedTo("");
    setPage(0);
  }

  return (
    <Card
      title="گزارش رویدادها (Audit Log)"
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <ExcelExportButton url="/audit-log/export.xlsx" filename="audit-log.xlsx" params={exportParams} />
          <div className="relative">
            <select
              aria-label="فیلتر نوع رویداد"
              className={filterSelectClass}
              value={eventType}
              onChange={(e) => {
                setEventType(e.target.value);
                setPage(0);
              }}
            >
              <option value="">همه رویدادها</option>
              {EVENT_TYPES.map((t) => (
                <option key={t} value={t}>
                  {AUDIT_EVENT_LABELS[t]}
                </option>
              ))}
            </select>
            <svg viewBox="0 0 20 20" className="pointer-events-none absolute left-2 top-1/2 h-3 w-3 -translate-y-1/2 text-gray-400" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M6 8l4 4 4-4" />
            </svg>
          </div>
          <JalaliDatePicker
            className="w-36 rounded-xl border border-gray-200 bg-gray-100 px-3 py-1.5 text-sm text-gray-700 outline-none focus:border-pulse-500 focus:bg-white"
            placeholder="از تاریخ"
            value={createdFrom}
            onChange={(iso) => {
              setCreatedFrom(iso);
              setPage(0);
            }}
          />
          <JalaliDatePicker
            className="w-36 rounded-xl border border-gray-200 bg-gray-100 px-3 py-1.5 text-sm text-gray-700 outline-none focus:border-pulse-500 focus:bg-white"
            placeholder="تا تاریخ"
            value={createdTo}
            onChange={(iso) => {
              setCreatedTo(iso);
              setPage(0);
            }}
          />
          {hasActiveFilter && (
            <button
              onClick={resetFilters}
              className="rounded-xl border border-gray-200 bg-white px-3 py-1.5 text-sm font-medium text-gray-500 transition-colors hover:bg-gray-50 hover:text-gray-700"
            >
              حذف فیلترها
            </button>
          )}
        </div>
      }
    >
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
