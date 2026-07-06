import { STATUS_LABELS, type EvaluationStatus } from "../types";

const STYLE_BY_STATUS: Record<EvaluationStatus, string> = {
  draft: "bg-gray-100 text-gray-700",
  submitted: "bg-blue-50 text-blue-700",
  hr_approved: "bg-pulse-50 text-pulse-700",
  deputy_approved: "bg-amber-50 text-amber-800",
  finalized: "bg-green-50 text-green-700",
};

const DOT_BY_STATUS: Record<EvaluationStatus, string> = {
  draft: "bg-gray-400",
  submitted: "bg-blue-500",
  hr_approved: "bg-pulse-500",
  deputy_approved: "bg-amber-500",
  finalized: "bg-green-500",
};

export function StatusBadge({ status }: { status: EvaluationStatus }) {
  // برای وضعیت نهایی‌شده، نقطه به‌آرامی پالس می‌زند تا حس «موفقیت» بدهد
  const pulse = status === "finalized";
  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ${STYLE_BY_STATUS[status]}`}
    >
      <span
        aria-hidden
        className={`h-1.5 w-1.5 rounded-full ${DOT_BY_STATUS[status]}`}
        style={pulse ? { animation: "var(--animate-pulse-slow)" } : undefined}
      />
      {STATUS_LABELS[status]}
    </span>
  );
}
