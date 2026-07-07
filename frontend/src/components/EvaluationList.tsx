import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { extractErrorMessage } from "../api/client";
import { useDebouncedValue, useEvaluations } from "../api/queries";
import { STAGE_LABELS, type EvaluationStatus } from "../types";
import { StatusBadge } from "./StatusBadge";
import { PaginationControls } from "./PaginationControls";
import { Table } from "../ui/Table";
import { EmptyState } from "../ui/Card";

const PAGE_SIZE = 10;

export interface EvaluationListTab {
  /** کلید یکتای تب (برای state داخلی) */
  key: string;
  label: string;
  /** بدون مقدار = بدون فیلتر وضعیت (همهٔ پرونده‌های در دسترس این کاربر) */
  status?: EvaluationStatus;
}

/** فهرست پرونده‌های ارزیابی با جست‌وجو، صفحه‌بندی و — در صورت وجود بیش از یک تب —
 * سوییچ وضعیت به‌دست کاربر (نه فقط یک وضعیت ثابت تحمیل‌شده توسط صفحهٔ والد؛ این
 * دقیقاً همان محدودیتی بود که مانع می‌شد معاونت/مدیرعامل پروندهٔ خودشان را پس از
 * اقدام دوباره پیدا کنند). */
export function EvaluationList({
  title,
  tabs,
}: {
  title: string;
  tabs: EvaluationListTab[];
}) {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [activeTabKey, setActiveTabKey] = useState(tabs[0]!.key);
  const debouncedSearch = useDebouncedValue(search);
  const navigate = useNavigate();

  const activeTab = tabs.find((t) => t.key === activeTabKey) ?? tabs[0]!;

  const { data, error, isPending } = useEvaluations({
    q: debouncedSearch,
    status: activeTab.status,
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  });

  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-card">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-base font-bold text-gray-900">{title}</h2>
        <div className="relative">
          <svg viewBox="0 0 20 20" className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
            <circle cx="9" cy="9" r="6" />
            <path d="M14 14l3 3" />
          </svg>
          <input
            className="w-full rounded-xl border border-gray-200 bg-gray-100 py-1.5 pr-9 pl-3 text-sm text-gray-700 outline-none transition-colors duration-150 focus:border-pulse-500 focus:bg-white sm:w-72"
            placeholder="جست‌وجو (نام پرسنل، کد ارزیابی)…"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(0);
            }}
          />
        </div>
      </div>

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
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-all duration-200 ${
                tab.key === activeTabKey
                  ? "bg-white text-pulse-700 shadow-sm"
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
                {STAGE_LABELS[e.stage]}
              </span>,
              <button
                key="action"
                onClick={() => navigate(`/evaluations/${e.id}`)}
                className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-sm font-medium text-pulse-600 transition-colors hover:bg-pulse-50 hover:text-pulse-700"
              >
                مشاهده
                <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M7 5l5 5-5 5" />
                </svg>
              </button>,
            ])}
          />
          <PaginationControls
            page={page}
            totalPages={totalPages}
            totalCount={total}
            pageSize={PAGE_SIZE}
            onPageChange={setPage}
          />
        </>
      )}
    </div>
  );
}
