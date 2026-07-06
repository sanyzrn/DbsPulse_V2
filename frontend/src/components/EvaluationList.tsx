import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "motion/react";
import { extractErrorMessage } from "../api/client";
import { useDebouncedValue, useEvaluations } from "../api/queries";
import { STAGE_LABELS, type EvaluationStatus } from "../types";
import { StatusBadge } from "./StatusBadge";
import { PaginationControls } from "./PaginationControls";

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
            className="w-full rounded-xl border border-gray-200 bg-white py-1.5 pr-9 pl-3 text-sm text-gray-700 outline-none transition-all duration-200 focus:border-pulse-400 sm:w-72"
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
      {data && data.items.length === 0 && (
        <div className="flex flex-col items-center justify-center py-10 text-center">
          <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-pulse-50 to-pulse-violet-50">
            <svg viewBox="0 0 24 24" className="h-6 w-6 text-pulse-400" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2" />
              <rect x="9" y="3" width="6" height="4" rx="1" />
            </svg>
          </div>
          <p className="text-sm text-gray-400">موردی یافت نشد.</p>
        </div>
      )}

      {data && data.items.length > 0 && (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 bg-gradient-to-l from-pulse-50/50 to-pulse-violet-50/50">
                  <th className="px-3 py-2.5 text-right text-xs font-semibold text-gray-600">کد ارزیابی</th>
                  <th className="px-3 py-2.5 text-right text-xs font-semibold text-gray-600">پرسنل</th>
                  <th className="px-3 py-2.5 text-right text-xs font-semibold text-gray-600">وضعیت</th>
                  <th className="px-3 py-2.5 text-right text-xs font-semibold text-gray-600">مرحله</th>
                  <th className="px-3 py-2.5 text-right text-xs font-semibold text-gray-600"></th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((e, idx) => (
                  <motion.tr
                    key={e.id}
                    className="border-b border-gray-50 transition-colors last:border-0 hover:bg-pulse-50/30"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ duration: 0.2, delay: idx * 0.03 }}
                  >
                    <td className="px-3 py-2.5 font-medium text-gray-700">{e.evaluation_code}</td>
                    <td className="px-3 py-2.5 text-gray-700">{e.subject_full_name}</td>
                    <td className="px-3 py-2.5">
                      <div className="flex flex-wrap items-center gap-1.5">
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
                      </div>
                    </td>
                    <td className="px-3 py-2.5 text-gray-500">{STAGE_LABELS[e.stage]}</td>
                    <td className="px-3 py-2.5">
                      <button
                        onClick={() => navigate(`/evaluations/${e.id}`)}
                        className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-sm font-medium text-pulse-600 transition-colors hover:bg-pulse-50 hover:text-pulse-700"
                      >
                        مشاهده
                        <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M7 5l5 5-5 5" />
                        </svg>
                      </button>
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
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
