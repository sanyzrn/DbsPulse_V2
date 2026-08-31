/** مهلتِ ثبت، و تمدیدش توسط منابع انسانی.
 *
 * مهلت از تاریخِ پایانِ دورهٔ ارزیابی می‌آید و برای همه یکی است. ولی همیشه
 * پرونده‌ای هست که دلیلِ موجه دارد — فرد در مرخصی بوده، پرونده دیر باز شده،
 * ارزیاب عوض شده. بدون این نوار، تنها راهِ کمک به آن یک نفر، عقب انداختنِ مهلتِ
 * کلِ دوره بود، یعنی باز کردنِ در برای همه.
 *
 * برای همه دیده می‌شود (ارزیاب باید بداند تا کِی وقت دارد)، ولی دکمهٔ تمدید فقط
 * برای منابع انسانی است.
 */
import { useState } from "react";
import { apiClient, extractErrorMessage } from "../api/client";
import { Button } from "../ui/Button";
import { JalaliDatePicker } from "../ui/JalaliDatePicker";
import { formatDate } from "../utils/dates";
import { useToast } from "./Toast";
import type { EvaluationDetail } from "../types";

export function SubmissionDeadlineBar({
  evaluation,
  isHr,
  onChanged,
}: {
  evaluation: EvaluationDetail;
  isHr: boolean;
  onChanged: () => void;
}) {
  const { showSuccess, showError } = useToast();
  const [open, setOpen] = useState(false);
  const [until, setUntil] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  const deadline = evaluation.submission_deadline;
  // پرونده‌ای که به دوره‌ای وصل نیست مهلتی ندارد — و نوارِ خالی فقط نویز است.
  if (!deadline) return null;

  // مقایسهٔ تاریخِ محلی، نه UTC: مهلت یک *روز* است، نه یک لحظه.
  const today = new Date();
  const todayKey = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(
    today.getDate()
  ).padStart(2, "0")}`;
  const passed = todayKey > deadline;
  // تمدید فقط پرونده‌ای را باز می‌کند که هنوز در مرحلهٔ ثبت است.
  const canExtend = isHr && evaluation.status === "draft";

  async function extend() {
    if (!until || !reason.trim()) return;
    setBusy(true);
    try {
      await apiClient.post(`/evaluations/${evaluation.id}/extend-submission`, {
        until,
        reason: reason.trim(),
      });
      showSuccess(`مهلت ثبت تا ${formatDate(until)} تمدید شد`);
      setOpen(false);
      setUntil("");
      setReason("");
      onChanged();
    } catch (err) {
      showError(extractErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className={`rounded-2xl border p-4 ${
        passed ? "border-amber-200 bg-amber-50" : "border-gray-200 bg-white"
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-gray-900">
            {passed ? "مهلت ثبت گذشته است" : "مهلت ثبت"}
            {" — "}
            {formatDate(deadline)}
            {evaluation.submission_deadline_extended && (
              <span className="ms-2 rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">
                تمدیدشده
              </span>
            )}
          </p>
          <p className="mt-0.5 text-xs text-gray-500">
            {passed
              ? "تا زمانی که تمدید نشود، نه خودارزیابی ثبت می‌شود و نه نمرهٔ ارزیاب."
              : "پس از این تاریخ، ثبت خودارزیابی و نمرهٔ ارزیاب بسته می‌شود."}
          </p>
          {evaluation.submission_extension_reason && (
            <p className="mt-1 text-xs text-gray-500">
              دلیل تمدید: {evaluation.submission_extension_reason}
            </p>
          )}
        </div>
        {canExtend && !open && (
          <Button variant="secondary" onClick={() => setOpen(true)}>
            تمدید مهلت
          </Button>
        )}
      </div>

      {open && (
        <div className="mt-4 space-y-3 border-t border-gray-200 pt-4">
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-600">تا تاریخ</label>
              <JalaliDatePicker value={until} onChange={setUntil} />
            </div>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-600">
              دلیل تمدید (اجباری)
            </label>
            <textarea
              className="w-full rounded-xl border border-gray-300 px-3 py-2 text-sm"
              rows={2}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="مثلاً: فرد در مرخصی استعلاجی بود"
            />
            {/* دلیل اجباری است چون تمدیدِ بی‌دلیل، در بازبینی از تمدیدِ خودسرانه
                قابل تشخیص نیست. متن هم در پرونده می‌ماند و هم در گزارش رخدادها. */}
          </div>
          <div className="flex gap-2">
            <Button onClick={extend} disabled={busy || !until || !reason.trim()}>
              {busy ? "در حال ثبت…" : "ثبت تمدید"}
            </Button>
            <Button variant="secondary" onClick={() => setOpen(false)} disabled={busy}>
              انصراف
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
