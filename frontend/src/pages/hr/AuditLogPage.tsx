import { useState } from "react";
import { extractErrorMessage } from "../../api/client";
import { useAuditLog } from "../../api/queries";
import { Table } from "../../ui/Table";
import { AUDIT_EVENT_LABELS, type AuditLogEntry } from "../../types";

const PAGE_SIZE = 20;

const EVENT_TYPES = Object.keys(AUDIT_EVENT_LABELS);

function formatDetails(entry: AuditLogEntry): string {
  const parts: string[] = [];
  if (entry.old_value) parts.push(`قبل: ${JSON.stringify(entry.old_value)}`);
  if (entry.new_value) parts.push(`بعد: ${JSON.stringify(entry.new_value)}`);
  return parts.join(" — ");
}

export function AuditLogPage() {
  const [eventType, setEventType] = useState("");
  const [page, setPage] = useState(0);

  const { data, error: queryError } = useAuditLog({
    event_type: eventType,
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  });
  const error = queryError != null ? extractErrorMessage(queryError) : null;

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;
  const items = data?.items ?? [];

  return (
    <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-card">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-base font-bold text-gray-900">گزارش رویدادها (Audit Log)</h2>
        <div className="relative">
          <select
            className="appearance-none rounded-xl border border-gray-200 bg-gray-100 py-1.5 pr-3 pl-8 text-sm text-gray-700 outline-none transition-colors duration-150 focus:border-pulse-500 focus:bg-white"
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
      </div>

      {items.length > 0 && (
        <Table
          bordered={false}
          cellAlign="top"
          headers={["زمان", "رویداد", "انجام‌دهنده", "کد ارزیابی", "جزئیات"]}
          rowKeys={items.map((entry) => entry.id)}
          rows={items.map((entry) => [
            <span key="time" className="whitespace-nowrap text-gray-500">
              {new Date(entry.created_at).toLocaleString("fa-IR")}
            </span>,
            <span key="event" className="inline-flex items-center rounded-lg bg-pulse-50 px-2 py-0.5 text-xs font-medium text-pulse-700">
              {AUDIT_EVENT_LABELS[entry.event_type] ?? entry.event_type}
            </span>,
            entry.actor_username ?? `#${entry.actor_user_id}`,
            <span key="code" className="text-gray-500">
              {entry.evaluation_code ?? "—"}
            </span>,
            <span key="details" className="block max-w-md text-xs text-gray-500">
              {formatDetails(entry)}
            </span>,
          ])}
        />
      )}

      {error && <p className="mt-4 text-center text-sm text-red-600">{error}</p>}
      {!error && data && data.items.length === 0 && (
        <p className="mt-4 text-center text-sm text-gray-400">رویدادی یافت نشد.</p>
      )}

      {data && data.total > PAGE_SIZE && (
        <div className="mt-4 flex items-center justify-center gap-3 text-sm">
          <button
            disabled={page === 0}
            onClick={() => setPage((p) => p - 1)}
            className="flex h-9 w-9 items-center justify-center rounded-xl border border-gray-200 bg-white font-medium text-gray-700 shadow-sm transition-all duration-200 hover:bg-gray-50 hover:shadow-md disabled:opacity-40"
          >
            <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M7 5l5 5-5 5" />
            </svg>
          </button>
          <span className="text-gray-500">
            صفحه {(page + 1).toLocaleString("fa-IR")} از {totalPages.toLocaleString("fa-IR")}
          </span>
          <button
            disabled={page + 1 >= totalPages}
            onClick={() => setPage((p) => p + 1)}
            className="flex h-9 w-9 items-center justify-center rounded-xl border border-gray-200 bg-white font-medium text-gray-700 shadow-sm transition-all duration-200 hover:bg-gray-50 hover:shadow-md disabled:opacity-40"
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
