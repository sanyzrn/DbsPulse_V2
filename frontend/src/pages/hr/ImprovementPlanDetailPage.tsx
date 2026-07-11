import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "motion/react";
import { apiClient, extractErrorMessage } from "../../api/client";
import { useImprovementPlanDetail, useUsersList } from "../../api/queries";
import { useConfirm } from "../../components/ConfirmDialog";
import { useToast } from "../../components/Toast";
import { Button } from "../../ui/Button";
import { Card, EmptyState } from "../../ui/Card";
import { PctBar } from "../../ui/Meters";
import { JalaliDatePicker } from "../../ui/JalaliDatePicker";
import { formatDate, formatDateTime } from "../../utils/dates";
import { IMPROVEMENT_PLAN_STATUS_LABELS, type ImprovementGoal, type ImprovementPlanStatus } from "../../types";

const inputClass =
  "w-full rounded-xl border border-gray-200 bg-gray-100 px-3 py-2 text-sm text-gray-900 outline-none transition-colors duration-150 focus:border-pulse-500 focus:bg-white";

const STATUS_BADGE: Record<ImprovementPlanStatus, string> = {
  open: "bg-pulse-50 text-pulse-700",
  completed: "bg-green-50 text-green-700",
  cancelled: "bg-gray-100 text-gray-500",
};

const STATUS_DOT: Record<ImprovementPlanStatus, string> = {
  open: "bg-pulse-500",
  completed: "bg-green-500",
  cancelled: "bg-gray-400",
};

export function ImprovementPlanDetailPage() {
  const { id } = useParams();
  const planId = id ? Number(id) : null;
  const { showSuccess, showError } = useToast();
  const confirm = useConfirm();
  const queryClient = useQueryClient();
  const [newGoal, setNewGoal] = useState("");

  const { data: plan, error, isPending } = useImprovementPlanDetail(planId);
  // نامزدهای مسئول پیگیری: مسئولان واحد و معاونت‌ها
  const { data: owners } = useUsersList({ limit: 1000 });

  async function refresh() {
    await queryClient.invalidateQueries({ queryKey: ["improvement-plan", planId] });
    await queryClient.invalidateQueries({ queryKey: ["improvement-plans"] });
  }

  async function patchPlan(body: Record<string, unknown>, successMsg: string) {
    try {
      await apiClient.patch(`/improvement-plans/${planId}`, body);
      await refresh();
      showSuccess(successMsg);
    } catch (err) {
      showError(extractErrorMessage(err));
    }
  }

  async function addGoal() {
    const description = newGoal.trim();
    if (!description) return;
    try {
      await apiClient.post(`/improvement-plans/${planId}/goals`, { description });
      setNewGoal("");
      await refresh();
    } catch (err) {
      showError(extractErrorMessage(err));
    }
  }

  async function toggleGoal(goal: ImprovementGoal) {
    try {
      await apiClient.patch(`/improvement-plans/${planId}/goals/${goal.id}`, {
        is_done: !goal.is_done,
      });
      await refresh();
    } catch (err) {
      showError(extractErrorMessage(err));
    }
  }

  async function deleteGoal(goal: ImprovementGoal) {
    try {
      await apiClient.delete(`/improvement-plans/${planId}/goals/${goal.id}`);
      await refresh();
    } catch (err) {
      showError(extractErrorMessage(err));
    }
  }

  async function complete() {
    const ok = await confirm({
      title: "تکمیل برنامه بهبود؟",
      description: "پس از تکمیل، برنامه بسته می‌شود و دیگر یادآوری بازنگری نمی‌گیرد.",
      confirmLabel: "تکمیل",
    });
    if (!ok) return;
    try {
      await apiClient.post(`/improvement-plans/${planId}/complete`);
      await refresh();
      showSuccess("برنامه تکمیل شد");
    } catch (err) {
      showError(extractErrorMessage(err));
    }
  }

  async function cancel() {
    const ok = await confirm({
      title: "لغو برنامه بهبود؟",
      description: "برنامه لغو می‌شود و از فهرست فعال خارج خواهد شد.",
      confirmLabel: "لغو برنامه",
    });
    if (!ok) return;
    try {
      await apiClient.post(`/improvement-plans/${planId}/cancel`);
      await refresh();
      showSuccess("برنامه لغو شد");
    } catch (err) {
      showError(extractErrorMessage(err));
    }
  }

  if (isPending) {
    return (
      <div className="space-y-4">
        <div className="skeleton h-5 w-40" />
        <div className="skeleton h-40" />
        <div className="skeleton h-48" />
      </div>
    );
  }
  if (error != null || !plan)
    return <p className="text-sm text-red-600">{error ? extractErrorMessage(error) : "یافت نشد"}</p>;

  const doneCount = plan.goals.filter((g) => g.is_done).length;
  const isOpen = plan.status === "open";
  const progressPct = plan.goals.length ? (doneCount / plan.goals.length) * 100 : 0;

  return (
    <div className="space-y-4">
      <Link to="/hr/improvement-plans" className="inline-flex items-center gap-1 text-sm font-medium text-pulse-600 hover:text-pulse-700">
        {/* RTL: فلش «بازگشت» به سمت راست است */}
        <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M7 5l5 5-5 5" />
        </svg>
        بازگشت به فهرست
      </Link>

      <Card
        title={plan.title}
        actions={
          <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${STATUS_BADGE[plan.status]}`}>
            <span aria-hidden className={`h-1.5 w-1.5 rounded-full ${STATUS_DOT[plan.status]}`} />
            {IMPROVEMENT_PLAN_STATUS_LABELS[plan.status]}
          </span>
        }
      >
        <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
          <div>
            <dt className="text-xs text-gray-500">پرسنل</dt>
            <dd className="mt-0.5 font-medium text-gray-800">{plan.personnel_full_name}</dd>
          </div>
          <div>
            <dt className="text-xs text-gray-500">پرونده مبدأ</dt>
            <dd className="mt-0.5">
              <Link
                to={`/evaluations/${plan.evaluation_record_id}`}
                className="font-medium text-pulse-600 hover:text-pulse-700"
              >
                مشاهده ارزیابی
              </Link>
            </dd>
          </div>
          <div>
            <dt className="text-xs text-gray-500">تاریخ بازنگری</dt>
            <dd className="mt-0.5 font-medium text-gray-800">{formatDate(plan.review_date)}</dd>
          </div>
          {plan.completed_at && (
            <div>
              <dt className="text-xs text-gray-500">تاریخ بسته‌شدن</dt>
              <dd className="mt-0.5 font-medium text-gray-800">{formatDateTime(plan.completed_at)}</dd>
            </div>
          )}
        </dl>

        {isOpen && (
          <div className="mt-4 flex flex-wrap items-end gap-3 border-t border-gray-100 pt-4 text-sm">
            <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
              مسئول پیگیری
              <select
                className={`${inputClass} sm:w-48`}
                value={plan.owner_user_id ?? ""}
                onChange={(e) =>
                  patchPlan(
                    { owner_user_id: e.target.value === "" ? null : Number(e.target.value) },
                    "مسئول پیگیری به‌روزرسانی شد",
                  )
                }
              >
                <option value="">— بدون مسئول —</option>
                {owners?.items.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.username}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
              تغییر تاریخ بازنگری
              <JalaliDatePicker
                className={`${inputClass} sm:w-44`}
                value={plan.review_date}
                onChange={(iso) => iso && patchPlan({ review_date: iso }, "تاریخ بازنگری به‌روزرسانی شد")}
              />
            </label>
          </div>
        )}
      </Card>

      <Card title={`اهداف (${doneCount.toLocaleString("fa-IR")} از ${plan.goals.length.toLocaleString("fa-IR")})`}>
        {/* نوار پیشرفت کلی */}
        {plan.goals.length > 0 && (
          <div className="mb-4">
            <PctBar value={progressPct} tone="green" />
            <p className="mt-1 text-xs text-gray-500">
              {Math.round(progressPct).toLocaleString("fa-IR")}٪ تکمیل شده
            </p>
          </div>
        )}
        {plan.goals.length === 0 && <EmptyState>هنوز هدفی ثبت نشده است.</EmptyState>}
        <ul className="space-y-2">
          <AnimatePresence>
            {plan.goals.map((goal) => (
              <motion.li
                key={goal.id}
                className="flex items-center gap-3 rounded-xl border border-gray-100 px-3 py-2 text-sm transition-colors hover:bg-gray-50"
                layout
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 8 }}
              >
                <button
                  onClick={() => isOpen && toggleGoal(goal)}
                  disabled={!isOpen}
                  className={`flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-md border-2 transition-all ${
                    goal.is_done
                      ? "border-pulse-500 bg-pulse-600"
                      : "border-gray-300 hover:border-pulse-400"
                  } ${!isOpen ? "cursor-default" : "cursor-pointer"}`}
                  aria-label={`انجام‌شدن هدف: ${goal.description}`}
                >
                  {goal.is_done && (
                    <svg viewBox="0 0 20 20" className="h-3 w-3 text-white" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M5 10l3 3 7-7" />
                    </svg>
                  )}
                </button>
                <span className={`flex-1 ${goal.is_done ? "text-gray-400 line-through" : "text-gray-700"}`}>
                  {goal.description}
                </span>
                {isOpen && (
                  <button
                    onClick={() => deleteGoal(goal)}
                    className="text-gray-300 transition-colors hover:text-red-500"
                    aria-label={`حذف هدف: ${goal.description}`}
                  >
                    <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M4 6h12M8 6V4a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v2m2 0v10a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V6" />
                    </svg>
                  </button>
                )}
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
        {isOpen && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              addGoal();
            }}
            className="mt-3 flex gap-2 border-t border-gray-100 pt-3"
          >
            <input
              className={inputClass}
              placeholder="افزودن هدف جدید…"
              value={newGoal}
              onChange={(e) => setNewGoal(e.target.value)}
            />
            <Button type="submit">افزودن</Button>
          </form>
        )}
      </Card>

      {isOpen && (
        <div className="flex gap-2">
          <Button onClick={complete}>تکمیل برنامه</Button>
          <Button variant="secondary" onClick={cancel}>
            لغو برنامه
          </Button>
        </div>
      )}
    </div>
  );
}
