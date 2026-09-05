import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { apiClient, extractErrorMessage } from "../../api/client";
import { useIndicators } from "../../api/queries";
import { useConfirm } from "../ConfirmDialog";
import { useToast } from "../Toast";
import { Button } from "../../ui/Button";
import { Card } from "../../ui/Card";
import { useLocalDraft } from "../../ui/useLocalDraft";
import { formatDate, formatDateTime } from "../../utils/dates";
import type { CurrentSelfAssessment } from "../../types";

const SCORE_OPTIONS = [1, 2, 3, 4, 5];

export function ContractSelfAssessmentCard({ item }: { item: CurrentSelfAssessment }) {
  const [showForm, setShowForm] = useState(false);
  const [assessment, setAssessment] = useState(item);
  const { data: allIndicators = [] } = useIndicators({ includeInactive: true });
  const byId = new Map(allIndicators.map((indicator) => [indicator.id, indicator]));

  if (!assessment.eligible) return null;

  return (
    <Card
      title="خودارزیابی قرارداد جاری"
      actions={
        <span className="rounded-full bg-gray-100 px-3 py-1 text-xs text-gray-600">
          {formatDate(assessment.contract_start_date)} تا {formatDate(assessment.contract_end_date)}
        </span>
      }
    >
      {assessment.submitted_at ? (
        <div className="rounded-xl border border-green-200 bg-green-50/60 p-3">
          <p className="text-sm font-semibold text-green-900">
            خودارزیابی شما در {formatDateTime(assessment.submitted_at)} ثبت نهایی شده است.
          </p>
          {assessment.note && <p className="mt-2 text-sm text-gray-700">{assessment.note}</p>}
          <div className="mt-3 space-y-2">
            {assessment.scores.map((row) => (
              <div key={row.indicator_id} className="flex items-start justify-between gap-3 rounded-lg bg-white px-3 py-2 text-sm">
                <div>
                  <p className="text-gray-800">
                    {byId.get(row.indicator_id)?.description ?? `شاخص ${row.indicator_id}`}
                  </p>
                  {row.note && <p className="mt-0.5 text-xs text-gray-500">{row.note}</p>}
                </div>
                <span className="shrink-0 rounded-lg bg-green-100 px-2 py-1 font-bold text-green-800">
                  {row.score.toLocaleString("fa-IR")} از ۵
                </span>
              </div>
            ))}
          </div>
          <p className="mt-3 text-xs text-gray-500">
            برای هر قرارداد فقط یک‌بار ثبت می‌شود و قابل ویرایش نیست.
          </p>
        </div>
      ) : assessment.open ? (
        showForm ? (
          <ContractSelfAssessmentForm
            item={assessment}
            onDone={(result) => {
              setAssessment(result);
              setShowForm(false);
            }}
            onCancel={() => setShowForm(false)}
          />
        ) : (
          <div className="rounded-xl border border-dashed border-gray-300 bg-gray-50/60 p-3">
            <p className="text-sm text-gray-700">
              خودارزیابی شما در تمام بازهٔ قرارداد فعال است و به شروع ارزیابی توسط مسئول واحد وابسته نیست.
            </p>
            <p className="mt-1 text-xs text-gray-500">
              فقط خودتان و منابع انسانی آن را می‌بینید. در امتیاز نهایی اثر ندارد و پس از ثبت قابل ویرایش نیست.
            </p>
            <Button className="mt-3" onClick={() => setShowForm(true)}>ثبت خودارزیابی</Button>
          </div>
        )
      ) : (
        <p className="rounded-xl bg-amber-50 px-3 py-2 text-sm text-amber-800">
          بازهٔ این قرارداد به پایان رسیده و خودارزیابی ثبت نشده است.
        </p>
      )}
    </Card>
  );
}

function ContractSelfAssessmentForm({
  item,
  onDone,
  onCancel,
}: {
  item: CurrentSelfAssessment;
  onDone: (result: CurrentSelfAssessment) => void;
  onCancel: () => void;
}) {
  const { data: allIndicators = [] } = useIndicators({ includeInactive: true });
  const { showSuccess, showError } = useToast();
  const confirm = useConfirm();
  const queryClient = useQueryClient();
  const indicators = useMemo(() => {
    const wanted = new Set(item.indicator_ids);
    return allIndicators.filter((indicator) => wanted.has(indicator.id));
  }, [allIndicators, item.indicator_ids]);

  const draftKey = `nafas-hr:self-assessment:${item.personnel_id}:${item.contract_start_date}`;
  const [draft, setDraft] = useLocalDraft(draftKey);
  const [busy, setBusy] = useState(false);
  const allScored = indicators.length > 0 && indicators.every((i) => draft.scores[i.id]);

  async function submit() {
    const ok = await confirm({
      title: "خودارزیابی ثبت شود؟",
      danger: true,
      description: "پس از ثبت، خودارزیابی این قرارداد قابل ویرایش یا ثبت دوباره نیست.",
      confirmLabel: "ثبت نهایی",
    });
    if (!ok) return;
    setBusy(true);
    try {
      const { data } = await apiClient.post<CurrentSelfAssessment>("/me/self-assessment", {
        scores: indicators.map((indicator) => ({
          indicator_id: indicator.id,
          score: draft.scores[indicator.id],
          note: draft.notes[indicator.id]?.trim() || null,
        })),
        note: draft.overallNote.trim() || null,
      });
      window.localStorage.removeItem(draftKey);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["me", "self-assessment"] }),
        queryClient.invalidateQueries({ queryKey: ["me", "self-assessments"] }),
      ]);
      showSuccess("خودارزیابی شما ثبت شد");
      onDone(data);
    } catch (error) {
      showError(extractErrorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="space-y-3">
        {indicators.map((indicator) => (
          <div key={indicator.id} className="rounded-xl border border-gray-100 bg-gray-50/50 p-3">
            <p className="text-sm text-gray-800">{indicator.description}</p>
            <p className="mt-0.5 text-xs text-gray-500">{indicator.category}</p>
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              {SCORE_OPTIONS.map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setDraft({ ...draft, scores: { ...draft.scores, [indicator.id]: value } })}
                  aria-pressed={draft.scores[indicator.id] === value}
                  className={`h-9 w-9 rounded-lg border text-sm font-medium ${
                    draft.scores[indicator.id] === value
                      ? "border-pulse-500 bg-pulse-600 text-white"
                      : "border-gray-300 bg-white text-gray-700 hover:bg-gray-100"
                  }`}
                >
                  {value.toLocaleString("fa-IR")}
                </button>
              ))}
              <input
                className="ms-2 min-w-40 flex-1 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm outline-none focus:border-gray-900"
                placeholder="توضیح یا دستاورد شما (اختیاری)"
                value={draft.notes[indicator.id] ?? ""}
                onChange={(event) => setDraft({
                  ...draft,
                  notes: { ...draft.notes, [indicator.id]: event.target.value },
                })}
              />
            </div>
          </div>
        ))}
      </div>
      <label className="block text-sm">
        <span className="mb-1.5 block font-medium text-gray-700">دستاورد کلی شما (اختیاری)</span>
        <textarea
          className="w-full resize-none rounded-xl border border-gray-300 bg-white px-3 py-2 text-sm outline-none focus:border-gray-900"
          rows={3}
          value={draft.overallNote}
          onChange={(event) => setDraft({ ...draft, overallNote: event.target.value })}
        />
      </label>
      <div className="flex flex-wrap items-center gap-2">
        <Button onClick={submit} loading={busy} disabled={!allScored}>ثبت نهایی خودارزیابی</Button>
        <button onClick={onCancel} className="rounded-xl border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100">انصراف</button>
        {!allScored && <span className="text-xs text-gray-500">به همهٔ شاخص‌ها امتیاز بدهید.</span>}
      </div>
    </div>
  );
}
