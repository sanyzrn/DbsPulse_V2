import { useState } from "react";
import type { AiPendingAction } from "../../types";

/**
 * کارتِ تأیید — قلبِ قراردادِ «مدل پیشنهاد می‌دهد، کاربر تصمیم می‌گیرد».
 *
 * وضعیت‌ها از حقیقتِ سرور می‌آیند نه از عکسِ لحظهٔ چت: پیشنهادی که در تب
 * دیگری تأیید شده، این‌جا هم «انجام‌شده» دیده می‌شود. جزئیاتِ پیشنهاد
 * جمع‌شدنی است، اما هرگز پنهان نیست — تصمیمِ درست دیدنِ کامل است.
 */
export function PendingActionCard({
  action,
  busy,
  onConfirm,
  onReject,
}: {
  action: AiPendingAction;
  busy?: boolean;
  onConfirm: (id: number) => void;
  onReject: (id: number) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const decided = action.status !== "pending";

  return (
    <div
      className={`rounded-2xl border px-3.5 py-3 ${
        action.status === "pending"
          ? "border-amber-200 bg-amber-50/70"
          : action.status === "confirmed"
            ? "border-green-200 bg-green-50/60"
            : "border-gray-200 bg-gray-50"
      }`}
    >
      <div className="flex items-start gap-2">
        <span
          className={`mt-1 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] font-bold ${
            action.status === "pending"
              ? "bg-amber-500/15 text-amber-700"
              : action.status === "confirmed"
                ? "bg-green-600/15 text-green-700"
                : "bg-gray-400/15 text-gray-500"
          }`}
          aria-hidden
        >
          {action.status === "pending" ? "!" : action.status === "confirmed" ? "✓" : "×"}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold leading-relaxed text-gray-800">
            {action.summary || action.tool}
          </p>
          {action.status === "confirmed" && action.result_text && (
            <p className="mt-1 text-[11px] text-green-700">{action.result_text}</p>
          )}
          {action.status === "rejected" && (
            <p className="mt-1 text-[11px] text-gray-500">این پیشنهاد رد شد و چیزی اعمال نشد.</p>
          )}
          {action.status === "expired" && (
            <p className="mt-1 text-[11px] text-gray-500">این پیشنهاد منقضی شده است.</p>
          )}
          {action.status === "failed" && (
            <p className="mt-1 text-[11px] text-red-600">
              اجرا شکست خورد: {action.result_text || "جزئیات در گزارش رویدادها"}
            </p>
          )}

          <button
            type="button"
            onClick={() => setExpanded((prev) => !prev)}
            className="mt-1.5 text-[11px] font-medium text-gray-400 underline-offset-2 hover:text-gray-600 hover:underline"
          >
            {expanded ? "بستنِ جزئیات" : "جزئیاتِ پیشنهاد"}
          </button>
          {expanded && (
            <pre
              dir="ltr"
              className="mt-1.5 max-h-44 overflow-auto rounded-xl bg-gray-900/95 p-2.5 text-left text-[11px] leading-relaxed text-gray-100"
            >
              <code>{JSON.stringify(action.arguments, null, 2)}</code>
            </pre>
          )}
        </div>
      </div>

      {!decided && (
        <div className="mt-2.5 flex items-center gap-2 pe-7">
          <button
            type="button"
            disabled={busy}
            onClick={() => onConfirm(action.id)}
            className="rounded-xl bg-amber-600 px-3.5 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-amber-700 disabled:opacity-40"
          >
            تأیید و انجام
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => onReject(action.id)}
            className="rounded-xl border border-gray-200 bg-white px-3.5 py-1.5 text-xs font-semibold text-gray-600 transition-colors hover:bg-gray-50 disabled:opacity-40"
          >
            رد
          </button>
        </div>
      )}
    </div>
  );
}

/** ردِ کاری که همکار در این نوبت کرد — جمع‌شونده، تا نویز نسازد. */
export function StepTrace({
  steps,
}: {
  steps: { tool: string; status: string; summary: string }[];
}) {
  if (!steps.length) return null;
  return (
    <details className="group">
      <summary className="cursor-pointer select-none text-[11px] text-gray-400 transition-colors hover:text-gray-600">
        <span className="inline-flex items-center gap-1">
          <svg viewBox="0 0 16 16" className="h-3 w-3 transition-transform group-open:rotate-90" fill="none" stroke="currentColor" strokeWidth="1.8">
            <path d="M6 4l4 4-4 4" />
          </svg>
          کاری که انجام شد ({steps.length} گام)
        </span>
      </summary>
      <ul className="mt-1.5 space-y-1">
        {steps.map((step, index) => (
          <li key={index} className="flex items-start gap-1.5 text-[11px] leading-relaxed text-gray-500">
            <span
              className={`mt-1 h-1.5 w-1.5 shrink-0 rounded-full ${
                step.status === "error"
                  ? "bg-red-400"
                  : step.status === "awaiting_confirmation"
                    ? "bg-amber-400"
                    : "bg-green-500"
              }`}
              aria-hidden
            />
            <span>{step.summary || step.tool}</span>
          </li>
        ))}
      </ul>
    </details>
  );
}

/** کارتِ فایلِ بارگذاری‌شده — گزارشِ مرحله‌بندی، نه نتیجهٔ ورود. */
export function UploadCard({
  upload,
}: {
  upload: {
    filename: string;
    kind: string;
    total_rows?: number;
    valid_count?: number;
    invalid_count?: number;
    committed?: boolean;
    note?: string;
  };
}) {
  const isPersonnel = upload.kind === "personnel_import";
  return (
    <div
      className={`rounded-2xl border px-3.5 py-3 ${
        isPersonnel ? "border-pulse-100 bg-pulse-50/40" : "border-gray-200 bg-gray-50"
      }`}
    >
      <div className="flex items-center gap-2">
        <svg viewBox="0 0 20 20" className="h-4 w-4 shrink-0 text-pulse-600" fill="none" stroke="currentColor" strokeWidth="1.6">
          <path d="M6 2.5h5.5L16 7v10.5H6z" strokeLinejoin="round" />
          <path d="M11.5 2.5V7H16" strokeLinejoin="round" />
        </svg>
        <p className="min-w-0 flex-1 truncate text-xs font-semibold text-gray-800" dir="auto">
          {upload.filename}
        </p>
        {upload.committed && (
          <span className="rounded-lg bg-green-100 px-2 py-0.5 text-[10px] font-bold text-green-700">
            وارد شد
          </span>
        )}
      </div>
      {isPersonnel ? (
        <div className="mt-2 flex flex-wrap gap-1.5 text-[11px]">
          <span className="rounded-lg bg-white px-2 py-0.5 text-gray-600 ring-1 ring-gray-200">
            {upload.total_rows ?? 0} ردیف
          </span>
          <span className="rounded-lg bg-green-50 px-2 py-0.5 text-green-700 ring-1 ring-green-100">
            {upload.valid_count ?? 0} سالم
          </span>
          {(upload.invalid_count ?? 0) > 0 && (
            <span className="rounded-lg bg-red-50 px-2 py-0.5 text-red-600 ring-1 ring-red-100">
              {upload.invalid_count} خطادار
            </span>
          )}
        </div>
      ) : (
        upload.note && <p className="mt-1 text-[11px] text-gray-500">{upload.note}</p>
      )}
    </div>
  );
}
