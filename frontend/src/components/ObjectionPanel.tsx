/** اعتراض ثبت‌شدهٔ کارمند و پاسخ منابع انسانی (P0-06).
 *
 * اعتراضی که کسی موظف به پاسخ‌گویی به آن نباشد تشریفات است؛ این پنل هم اعتراض را
 * جلوی چشم زنجیره می‌گذارد و هم به HR راه پاسخ می‌دهد. نتیجه و سند نهایی عوض
 * نمی‌شوند — اگر واقعاً باید امتیاز تغییر کند، مسیرش ارزیابی تازه است نه بازنویسی
 * سندی که هش و QR تأیید دارد.
 */
import { useState } from "react";
import { apiClient, extractErrorMessage } from "../api/client";
import { useToast } from "./Toast";
import { Button } from "../ui/Button";
import { formatDateTime } from "../utils/dates";
import type { EvaluationDetail } from "../types";

export function ObjectionPanel({
  evaluation,
  isHr,
  onChanged,
}: {
  evaluation: EvaluationDetail;
  isHr: boolean;
  onChanged: () => void;
}) {
  const { showSuccess, showError } = useToast();
  const [resolution, setResolution] = useState("");
  const [busy, setBusy] = useState(false);

  if (!evaluation.objection_at) return null;

  async function submit() {
    setBusy(true);
    try {
      await apiClient.post(`/evaluations/${evaluation.id}/resolve-objection`, { resolution });
      showSuccess("پاسخ شما ثبت و به کارمند اطلاع داده شد");
      setResolution("");
      onChanged();
    } catch (err) {
      showError(extractErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-2xl border border-amber-200 bg-amber-50/60 p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-bold text-amber-900">اعتراض کارمند</h2>
        <span className="text-xs text-amber-700">{formatDateTime(evaluation.objection_at)}</span>
      </div>
      <p className="mt-2 text-sm text-amber-900">{evaluation.objection_reason}</p>

      {evaluation.objection_resolved_at ? (
        <div className="mt-4 rounded-xl bg-white/80 p-3">
          <p className="text-xs font-medium text-gray-500">
            پاسخ منابع انسانی — {formatDateTime(evaluation.objection_resolved_at)}
          </p>
          <p className="mt-1 text-sm text-gray-800">{evaluation.objection_resolution}</p>
        </div>
      ) : isHr ? (
        <div className="mt-4">
          <label htmlFor="objection-resolution" className="mb-1.5 block text-sm font-medium text-amber-900">
            پاسخ شما به این اعتراض
          </label>
          <textarea
            id="objection-resolution"
            className="w-full resize-none rounded-xl border border-amber-300 bg-white px-3 py-2 text-sm outline-none"
            rows={3}
            value={resolution}
            onChange={(e) => setResolution(e.target.value)}
            placeholder="مثلاً: با مسئول واحد بررسی شد؛ شواهد تکمیلی به پرونده افزوده شد و نتیجه بدون تغییر ماند"
          />
          <Button className="mt-3" onClick={submit} loading={busy} disabled={!resolution.trim()}>
            ثبت پاسخ
          </Button>
        </div>
      ) : (
        <p className="mt-3 text-xs text-amber-700">در انتظار پاسخ منابع انسانی…</p>
      )}
    </div>
  );
}
