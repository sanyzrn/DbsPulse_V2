/** پروندهٔ در جریانِ خود کارمند + فرم خودارزیابی (P0-06).
 *
 * تا پیش از این، فرایند از دید کارمند یک جعبهٔ سیاه بود: هیچ نمی‌دانست پرونده‌ای
 * دربارهٔ او باز است تا روزی نتیجه‌اش اعلام شود. این کارت دو چیز را می‌دهد —
 * دیدنِ وضعیت (بدون هیچ نمره‌ای، چون نمرهٔ پیش‌نویس هنوز تصمیم نیست) و امکان ثبت
 * دیدگاه خودش پیش از آن‌که ارزیاب نمره را قطعی کند.
 */
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { motion } from "motion/react";
import { apiClient, extractErrorMessage } from "../../api/client";
import { useIndicators } from "../../api/queries";
import { useToast } from "../../components/Toast";
import { WorkflowStepper } from "../WorkflowStepper";
import { Button } from "../../ui/Button";
import { Card } from "../../ui/Card";
import { formatDateTime } from "../../utils/dates";
import type { MyOpenEvaluation, SelfAssessment } from "../../types";

const SCORE_OPTIONS = [1, 2, 3, 4, 5];

// خودارزیابی فقط تا پیش از قطعی‌شدن نمرهٔ ارزیاب معنا دارد — بعد از آن دیگر دیدگاه
// مستقل نیست، واکنش به نمره است. (بک‌اند همین را اعمال می‌کند.)
const SELF_ASSESSMENT_OPEN: MyOpenEvaluation["status"][] = ["draft", "hr_approved"];

export function OpenCaseCard({ item, index }: { item: MyOpenEvaluation; index: number }) {
  const [showForm, setShowForm] = useState(false);
  const [submitted, setSubmitted] = useState<SelfAssessment | null>(null);
  const canSelfAssess = SELF_ASSESSMENT_OPEN.includes(item.status);

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.05 }}
    >
      <Card
        title={`پروندهٔ در جریان — ${item.evaluation_code}`}
        actions={
          <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700">
            <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-blue-500" />
            {item.stage_label}
          </span>
        }
      >
        {/* کارمند تا امروز فقط نام مرحله را می‌دید؛ اینکه «چند مرحله مانده»
            هیچ‌جا نبود. جعبهٔ سیاه، حتی وقتی محتوایش درست است، جعبهٔ سیاه است. */}
        <WorkflowStepper status={item.status} className="mb-4" />

        <p className="text-sm text-gray-600">
          ارزیابی شما از {formatDateTime(item.created_at)} آغاز شده و از{" "}
          {formatDateTime(item.stage_entered_at)} در مرحلهٔ فعلی است.
        </p>
        <p className="mt-1 text-xs text-gray-400">
          امتیازها تا پیش از تأیید نهایی قطعی نیستند و نمایش داده نمی‌شوند.
        </p>

        {submitted?.submitted_at ? (
          <p className="mt-3 rounded-xl bg-green-50 px-3 py-2 text-sm text-green-800">
            خودارزیابی شما ثبت شد و برای ارزیاب ارسال گردید.
          </p>
        ) : canSelfAssess && !showForm ? (
          <div className="mt-3 rounded-xl border border-dashed border-gray-300 bg-gray-50/60 p-3">
            <p className="text-sm text-gray-700">
              می‌توانید پیش از ثبت نمرهٔ ارزیاب، دیدگاه خودتان را ثبت کنید.
            </p>
            <p className="mt-1 text-xs text-gray-500">
              اختیاری است و در محاسبهٔ امتیاز نهایی وارد نمی‌شود؛ کنار نظر ارزیاب دیده
              می‌شود تا تفاوت‌ها موضوع گفت‌وگو باشد. یک‌بار ثبت می‌شود و قابل ویرایش نیست.
            </p>
            <Button className="mt-3" onClick={() => setShowForm(true)}>
              ثبت خودارزیابی
            </Button>
          </div>
        ) : null}

        {showForm && !submitted?.submitted_at && (
          <SelfAssessmentForm
            evaluationId={item.id}
            onDone={(result) => {
              setSubmitted(result);
              setShowForm(false);
            }}
            onCancel={() => setShowForm(false)}
          />
        )}
      </Card>
    </motion.div>
  );
}

function SelfAssessmentForm({
  evaluationId,
  onDone,
  onCancel,
}: {
  evaluationId: number;
  onDone: (result: SelfAssessment) => void;
  onCancel: () => void;
}) {
  const { data: indicators = [] } = useIndicators();
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [scores, setScores] = useState<Record<number, number>>({});
  const [notes, setNotes] = useState<Record<number, string>>({});
  const [overallNote, setOverallNote] = useState("");
  const [busy, setBusy] = useState(false);

  const allScored = indicators.length > 0 && indicators.every((i) => scores[i.id]);

  async function submit() {
    setBusy(true);
    try {
      const { data } = await apiClient.post<SelfAssessment>(
        `/me/evaluations/${evaluationId}/self-assessment`,
        {
          scores: indicators.map((i) => ({
            indicator_id: i.id,
            score: scores[i.id],
            note: notes[i.id]?.trim() || null,
          })),
          note: overallNote.trim() || null,
        },
      );
      await queryClient.invalidateQueries({ queryKey: ["me", "evaluations", "open"] });
      showSuccess("خودارزیابی شما ثبت شد");
      onDone(data);
    } catch (err) {
      showError(extractErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-4 space-y-4 border-t border-gray-100 pt-4">
      <p className="text-sm font-semibold text-gray-800">خودارزیابی</p>

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
                  onClick={() => setScores({ ...scores, [indicator.id]: value })}
                  aria-pressed={scores[indicator.id] === value}
                  className={`h-9 w-9 rounded-lg border text-sm font-medium transition-colors ${
                    scores[indicator.id] === value
                      ? "border-pulse-500 bg-pulse-600 text-white"
                      : "border-gray-300 bg-white text-gray-700 hover:bg-gray-100"
                  }`}
                >
                  {value.toLocaleString("fa-IR")}
                </button>
              ))}
              <input
                className="ms-2 min-w-40 flex-1 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm outline-none focus:border-pulse-400"
                placeholder="توضیح یا دستاورد شما (اختیاری)"
                value={notes[indicator.id] ?? ""}
                onChange={(e) => setNotes({ ...notes, [indicator.id]: e.target.value })}
              />
            </div>
          </div>
        ))}
      </div>

      <label className="block text-sm">
        <span className="mb-1.5 block font-medium text-gray-700">
          دستاورد کلی شما در این دوره (اختیاری)
        </span>
        <textarea
          className="w-full resize-none rounded-xl border border-gray-300 bg-white px-3 py-2 text-sm outline-none focus:border-pulse-400"
          rows={3}
          value={overallNote}
          onChange={(e) => setOverallNote(e.target.value)}
          placeholder="مثلاً: راه‌اندازی سامانهٔ گزارش‌گیری واحد و کاهش زمان تهیهٔ گزارش ماهانه"
        />
      </label>

      <div className="flex flex-wrap items-center gap-2">
        <Button onClick={submit} loading={busy} disabled={!allScored}>
          ثبت نهایی خودارزیابی
        </Button>
        <button
          onClick={onCancel}
          className="rounded-xl border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-100"
        >
          انصراف
        </button>
        {!allScored && (
          <span className="text-xs text-gray-500">به همهٔ شاخص‌ها امتیاز بدهید.</span>
        )}
      </div>
    </div>
  );
}
