import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { apiClient, extractErrorMessage } from "../../api/client";
import { useIndicators } from "../../api/queries";
import { useAuth } from "../../auth/AuthContext";
import { useConfirm } from "../ConfirmDialog";
import { useToast } from "../Toast";
import { Button } from "../../ui/Button";
import { Card } from "../../ui/Card";
import { useLocalDraft } from "../../ui/useLocalDraft";
import { formatDate, formatDateTime } from "../../utils/dates";
import { ASSESSMENT_SECTIONS, SelfAssessmentScores } from "./SelfAssessmentScores";
import type { CurrentSelfAssessment } from "../../types";

const SCORE_OPTIONS = [1, 2, 3, 4, 5];

export function ContractSelfAssessmentCard({ item }: { item: CurrentSelfAssessment }) {
  const [showForm, setShowForm] = useState(false);
  const assessment = item;
  const { data: allIndicators = [] } = useIndicators({ includeInactive: true }, true);

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
          <div className="mt-4"><SelfAssessmentScores scores={assessment.scores} indicators={allIndicators} /></div>
          <p className="mt-3 text-xs text-gray-500">
            برای هر قرارداد فقط یک‌بار ثبت می‌شود و قابل ویرایش نیست.
          </p>
        </div>
      ) : assessment.open ? (
        showForm ? (
          <ContractSelfAssessmentForm
            item={assessment}
            onDone={() => {
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
  const { user } = useAuth();
  const { data: allIndicators = [] } = useIndicators({ includeInactive: true }, true);
  const { showSuccess, showError } = useToast();
  const confirm = useConfirm();
  const queryClient = useQueryClient();
  const indicators = useMemo(() => {
    const wanted = new Set(item.indicator_ids);
    return allIndicators.filter((indicator) => wanted.has(indicator.id))
      .sort((a, b) => a.display_order - b.display_order || a.id - b.id);
  }, [allIndicators, item.indicator_ids]);

  const draftKey = `nafas-hr:self-assessment:${item.personnel_id}:${item.contract_start_date}`;
  const [draft, setDraft] = useLocalDraft(draftKey);
  const [busy, setBusy] = useState(false);
  const scoredCount = indicators.filter((i) => SCORE_OPTIONS.includes(draft.scores[i.id] ?? 0)).length;
  const allScored = indicators.length > 0 && indicators.length === item.indicator_ids.length && scoredCount === indicators.length;

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
      queryClient.setQueryData(["me", "self-assessment", "current", user?.id, user?.personnel_id], data);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["me", "self-assessment"] }),
        queryClient.invalidateQueries({ queryKey: ["me", "self-assessments"] }),
      ]);
      showSuccess("خودارزیابی شما ثبت شد");
      onDone(data);
    } catch (error) {
      showError(extractErrorMessage(error));
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["indicators"] }),
        queryClient.invalidateQueries({ queryKey: ["me", "self-assessment"] }),
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-gray-200 bg-gray-50 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm font-semibold text-gray-800">ارزیابی عملکرد من</p>
          <span className="text-xs text-gray-600" role="status">{scoredCount.toLocaleString("fa-IR")} از {item.indicator_ids.length.toLocaleString("fa-IR")} شاخص تکمیل شده</span>
        </div>
        <progress className="mt-3 h-2 w-full accent-pulse-600" value={scoredCount} max={item.indicator_ids.length || 1} aria-label="پیشرفت خودارزیابی" />
        <p className="mt-2 text-xs leading-6 text-gray-500">به هر شاخص از ۱ تا ۵ امتیاز بدهید. پاسخ‌های شما تا ثبت نهایی در همین مرورگر نگه داشته می‌شوند.</p>
      </div>
      {ASSESSMENT_SECTIONS.map((section) => {
        const members = indicators.filter((indicator) => indicator.section === section.key);
        if (!members.length) return null;
        const completed = members.filter((indicator) => SCORE_OPTIONS.includes(draft.scores[indicator.id] ?? 0)).length;
        return (
          <section key={section.key} aria-label={section.title} className="overflow-hidden rounded-2xl border border-gray-200">
            <div className={`flex flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-5 ${section.tone}`}>
              <div>
                <h3 className="text-base font-bold">{section.title}</h3>
                <p className="mt-1 text-xs opacity-80">{section.description}</p>
              </div>
              <span className="rounded-full bg-white/70 px-3 py-1.5 text-xs font-medium">{completed.toLocaleString("fa-IR")} از {members.length.toLocaleString("fa-IR")} پاسخ</span>
            </div>
            <div className="divide-y divide-gray-100">
              {members.map((indicator, index) => (
                <fieldset key={indicator.id} className="min-w-0 p-4 sm:p-5">
                  <legend className="sr-only">{indicator.description}</legend>
                  <div className="flex items-start gap-3">
                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-gray-100 text-xs font-bold text-gray-500" aria-hidden>{(index + 1).toLocaleString("fa-IR")}</span>
                    <div className="min-w-0">
                      <p className="text-sm font-medium leading-7 text-gray-900">{indicator.category}</p>
                      <p className="mt-1 text-xs font-medium text-gray-500">{indicator.description}</p>
                    </div>
                  </div>
                  <div className="mt-4 grid gap-4 lg:grid-cols-[220px_minmax(0,1fr)] lg:items-end">
                    <div>
                      <p className="mb-2 text-xs text-gray-500">امتیاز شما</p>
                      <div className="flex gap-2">
                        {SCORE_OPTIONS.map((value) => (
                          <button key={value} type="button" aria-label={`امتیاز ${value.toLocaleString("fa-IR")}`} aria-pressed={draft.scores[indicator.id] === value}
                            onClick={() => setDraft({ ...draft, scores: { ...draft.scores, [indicator.id]: value } })}
                            className={`h-10 w-10 rounded-xl border text-sm font-bold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-pulse-600 ${draft.scores[indicator.id] === value ? "border-pulse-600 bg-pulse-600 text-white shadow-sm" : "border-gray-200 bg-white text-gray-600 hover:border-pulse-400 hover:bg-pulse-50"}`}>
                            {value.toLocaleString("fa-IR")}
                          </button>
                        ))}
                      </div>
                    </div>
                    <label className="block min-w-0">
                      <span className="mb-2 block text-xs text-gray-500">توضیح یا دستاورد شما (اختیاری)</span>
                      <input className="w-full rounded-xl border border-gray-200 bg-gray-50/50 px-3 py-2.5 text-sm outline-none focus:border-pulse-500 focus:bg-white"
                        placeholder="نمونه‌ای از عملکرد خود بنویسید…" value={draft.notes[indicator.id] ?? ""}
                        onChange={(event) => setDraft({ ...draft, notes: { ...draft.notes, [indicator.id]: event.target.value } })} />
                    </label>
                  </div>
                </fieldset>
              ))}
            </div>
          </section>
        );
      })}
      {indicators.length < item.indicator_ids.length && <p className="text-sm text-amber-700">در حال دریافت آخرین شاخص‌ها…</p>}
      {item.indicator_ids.length === 0 && <p className="text-sm text-gray-500">هنوز شاخصی برای خودارزیابی تعریف نشده است.</p>}
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
