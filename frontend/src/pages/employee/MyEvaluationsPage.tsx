import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { motion } from "motion/react";
import { apiClient, extractErrorMessage } from "../../api/client";
import { useMyEvaluations, useMyImprovementPlans } from "../../api/queries";
import { useConfirm } from "../../components/ConfirmDialog";
import { useToast } from "../../components/Toast";
import { Button } from "../../ui/Button";
import { Card, EmptyState, PageHeader } from "../../ui/Card";
import { PctBadge, PctBar, ScoreRing } from "../../ui/Meters";
import { formatDate, formatDateTime } from "../../utils/dates";
import type { ImprovementPlanDetail, MyEvaluation } from "../../types";

function MyEvaluationCard({ item, index }: { item: MyEvaluation; index: number }) {
  const { showSuccess, showError } = useToast();
  const confirm = useConfirm();
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState(false);

  async function acknowledge() {
    const ok = await confirm({
      title: "تأیید رؤیت نتیجه ارزیابی؟",
      description:
        "با تأیید، به‌صورت رسمی ثبت می‌شود که نتیجه این ارزیابی به شما ابلاغ شده است. این عمل قابل بازگشت نیست.",
      confirmLabel: "رؤیت شد",
    });
    if (!ok) return;
    setBusy(true);
    try {
      await apiClient.post(`/me/evaluations/${item.id}/acknowledge`);
      await queryClient.invalidateQueries({ queryKey: ["me", "evaluations"] });
      showSuccess("رؤیت شما ثبت شد");
    } catch (err) {
      showError(extractErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.05 }}
    >
      <Card
        title={`پرونده ${item.evaluation_code}`}
        actions={
          item.acknowledged_at ? (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-green-50 px-3 py-1 text-xs font-medium text-green-700">
              <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-green-500" />
              رؤیت شد — {formatDateTime(item.acknowledged_at)}
            </span>
          ) : (
            <Button onClick={acknowledge} loading={busy}>
              رؤیت شد
            </Button>
          )
        }
      >
        <div className="flex flex-wrap items-center gap-x-8 gap-y-3">
          <ScoreRing value={item.final_weighted_pct} size={72} label="نتیجه نهایی" />
          <dl className="grid flex-1 grid-cols-1 gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
            <div>
              <dt className="mb-1 text-xs text-gray-500">امتیاز عمومی</dt>
              <dd><PctBadge value={item.general_score_pct} /></dd>
            </div>
            <div>
              <dt className="mb-1 text-xs text-gray-500">امتیاز تخصصی</dt>
              <dd><PctBadge value={item.specialized_score_pct} /></dd>
            </div>
            <div>
              <dt className="mb-1 text-xs text-gray-500">تاریخ نهایی شدن</dt>
              <dd className="font-medium text-gray-800">{formatDateTime(item.finalized_at)}</dd>
            </div>
          </dl>
        </div>
        {item.recommendation && (
          <p className="mt-3 flex items-center gap-2 rounded-xl bg-amber-50/70 px-3 py-2 text-sm">
            <span aria-hidden>💡</span>
            <span><span className="text-xs text-gray-500">پیشنهاد سامانه: </span>{item.recommendation}</span>
          </p>
        )}
      </Card>
    </motion.div>
  );
}

function MyPlanCard({ plan, index }: { plan: ImprovementPlanDetail; index: number }) {
  const doneCount = plan.goals.filter((g) => g.is_done).length;
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.05 }}
    >
      <Card
        title={`برنامه بهبود: ${plan.title}`}
        actions={
          <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700">
            <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-amber-500" />
            بازنگری: {formatDate(plan.review_date)}
          </span>
        }
      >
        {plan.summary && <p className="mb-3 text-sm text-gray-600">{plan.summary}</p>}
        <p className="mb-1.5 text-xs text-gray-500">
          پیشرفت اهداف: {doneCount.toLocaleString("fa-IR")} از{" "}
          {plan.goals.length.toLocaleString("fa-IR")}
        </p>
        <PctBar
          value={plan.goals.length ? (doneCount / plan.goals.length) * 100 : 0}
          tone="green"
          className="mb-3 max-w-xs"
        />
        <ul className="space-y-1.5 text-sm">
          {plan.goals.map((goal) => (
            <li key={goal.id} className="flex items-center gap-2">
              <span
                className={`flex h-4 w-4 flex-shrink-0 items-center justify-center rounded border-2 ${
                  goal.is_done
                    ? "border-pulse-500 bg-pulse-600"
                    : "border-gray-300"
                }`}
              >
                {goal.is_done && (
                  <svg viewBox="0 0 20 20" className="h-2.5 w-2.5 text-white" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M5 10l3 3 7-7" />
                  </svg>
                )}
              </span>
              <span className={goal.is_done ? "text-gray-400 line-through" : "text-gray-700"}>
                {goal.description}
              </span>
            </li>
          ))}
        </ul>
      </Card>
    </motion.div>
  );
}

export function MyEvaluationsPage() {
  const { data, isPending, error } = useMyEvaluations();
  const { data: plans = [] } = useMyImprovementPlans();

  return (
    <div className="space-y-4">
      <PageHeader
        title="کارنامه من"
        subtitle="نتایج نهایی‌شده ارزیابی عملکرد شما. با دکمه «رؤیت شد» ابلاغ رسمی نتیجه ثبت می‌شود."
      />

      {plans.map((plan, i) => (
        <MyPlanCard key={plan.id} plan={plan} index={i} />
      ))}
      {error != null && (
        <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{extractErrorMessage(error)}</p>
      )}
      {isPending && (
        <div className="space-y-4">
          {[0, 1].map((i) => (
            <div key={i} className="skeleton h-32" />
          ))}
        </div>
      )}
      {data && data.items.length === 0 && (
        <Card>
          <EmptyState>هنوز ارزیابی نهایی‌شده‌ای برای شما ثبت نشده است.</EmptyState>
        </Card>
      )}
      {data?.items.map((item, i) => (
        <MyEvaluationCard key={item.id} item={item} index={i} />
      ))}
    </div>
  );
}
