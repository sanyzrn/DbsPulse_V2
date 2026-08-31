import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { motion } from "motion/react";
import { apiClient, extractErrorMessage } from "../../api/client";
import { useIndicators, useMyEvaluations, useMyImprovementPlans, useMyOpenEvaluations, useMySelfAssessments } from "../../api/queries";
import { useAuth } from "../../auth/AuthContext";
import { usePermissions } from "../../auth/PermissionsContext";
import { OpenCaseCard } from "../../components/employee/OpenCaseCard";
import { useConfirm } from "../../components/ConfirmDialog";
import { PdfDownloadButton } from "../../components/PdfDownloadButton";
import { RoleOverviewCards } from "../../components/RoleOverviewCards";
import { useToast } from "../../components/Toast";
import { Button } from "../../ui/Button";
import { Card, EmptyState, PageHeader } from "../../ui/Card";
import { PctBadge, PctBar, ScoreRing } from "../../ui/Meters";
import { formatDate, formatDateTime } from "../../utils/dates";
import type { ImprovementPlanDetail, MyEvaluation, MySelfAssessment } from "../../types";

function MyEvaluationCard({
  item,
  index,
  showObjections,
  showAcknowledgement,
}: {
  item: MyEvaluation;
  index: number;
  showObjections: boolean;
  showAcknowledgement: boolean;
}) {
  const { showSuccess, showError } = useToast();
  const confirm = useConfirm();
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState(false);

  async function acknowledge() {
    // «رؤیت» در گفتار اداری یعنی «دیدم»، ولی خیلی‌ها آن را «قبول دارم»
    // می‌خوانند. سامانه این دو را عمداً از هم جدا کرده — پس خودِ دکمه هم باید
    // جدایشان کند، وگرنه کارمند یا فکر می‌کند دارد نتیجه را تأیید می‌کند، یا از
    // ترسِ از دست دادن حق اعتراض اصلاً کلیک نمی‌کند و پرونده معلق می‌ماند.
    const ok = await confirm({
      title: "ثبت مشاهدهٔ نتیجه؟",
      description:
        "ثبت می‌شود که نتیجهٔ این ارزیابی را دیده‌اید. این کار قابل بازگشت نیست.",
      consequence: (
        <>
          <b>مشاهده به معنی پذیرش نتیجه نیست.</b> اگر به نتیجه اعتراض دارید، دقیقاً
          پس از همین ثبت است که راه اعتراض برایتان باز می‌شود.
        </>
      ),
      confirmLabel: "نتیجه را دیدم",
    });
    if (!ok) return;
    setBusy(true);
    try {
      await apiClient.post(`/me/evaluations/${item.id}/acknowledge`);
      await queryClient.invalidateQueries({ queryKey: ["me", "evaluations"] });
      // کارت «در انتظار رؤیت شما» در خلاصهٔ نقش باید فوراً کم شود
      await queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      showSuccess("ثبت شد که نتیجه را دیده‌اید");
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
          showAcknowledgement && (item.acknowledged_at ? (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-green-50 px-3 py-1 text-xs font-medium text-green-700">
              <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-green-500" />
              مشاهده شد — {formatDateTime(item.acknowledged_at)}
            </span>
          ) : (
            <Button onClick={acknowledge} loading={busy}>
              نتیجه را دیدم
            </Button>
          ))
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
        {/* امتیاز ویژه، اگر گرفته باشد. عدد بدون دلیلش برای کسی که نمره‌اش را
            گرفته یک تعدیل بی‌توضیح است؛ این‌جا هر دو کنار هم می‌آیند. */}
        {item.bonus_points ? (
          <p className="mt-3 rounded-xl border border-amber-200 bg-amber-50/70 px-3 py-2 text-sm text-amber-900">
            <span className="font-semibold">
              <span aria-hidden>★</span> امتیاز ویژه: {item.bonus_points.toLocaleString("fa-IR")}{" "}
              امتیاز
            </span>
            {item.base_weighted_pct !== null && (
              <span className="text-xs text-amber-800">
                {" "}
                (امتیاز فرم {item.base_weighted_pct.toLocaleString("fa-IR")}٪ + این امتیاز)
              </span>
            )}
            {item.bonus_reason && <span className="block mt-0.5 text-xs">{item.bonus_reason}</span>}
          </p>
        ) : null}

        {/* «پیشنهاد سامانه» بود، که مثل حکمِ یک ماشین خوانده می‌شد — دربارهٔ
            آیندهٔ شغلی خودِ خواننده. در واقع خروجی جدول آستانه‌هایی است که
            سازمان تصویب کرده؛ گفتنِ همین، آن را از حکم به قاعده تبدیل می‌کند. */}
        {item.recommendation && (
          <p className="mt-3 rounded-xl bg-amber-50/70 px-3 py-2 text-sm">
            <span className="text-xs text-gray-500">
              بر اساس بازهٔ امتیاز شما در جدول مصوب سازمان، نتیجهٔ ثبت‌شده:{" "}
            </span>
            {item.recommendation}
          </p>
        )}

        {/* سندی که دربارهٔ این فرد است باید در اختیار خودش باشد — تا پیش از این
            تنها HR می‌توانست کارنامهٔ هش‌شده و قابل‌تأیید را دانلود کند. */}
        <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-gray-100 pt-3">
          <PdfDownloadButton
            evaluationId={item.id}
            filename={`${item.evaluation_code}.pdf`}
          />
        </div>

        {showObjections && <ObjectionSection item={item} />}
      </Card>
    </motion.div>
  );
}

/** مسیر اعتراض (P0-06).
 *
 * «رؤیت شد» فقط ثبت می‌کند که فرد نتیجه را *دید*، نه این‌که پذیرفت. بدون این بخش،
 * سامانه هیچ جایی برای مخالفت او ندارد و در هر بازبینی حقوقی پاسخِ «کارمند چه گفت؟»
 * می‌شود «هیچ‌چیز ثبت نشده». نتیجه و سند نهایی تغییر نمی‌کنند — اعتراض یک رکورد
 * موازی است که HR باید به آن پاسخ دهد.
 */
function ObjectionSection({ item }: { item: MyEvaluation }) {
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    try {
      await apiClient.post(`/me/evaluations/${item.id}/object`, { reason });
      await queryClient.invalidateQueries({ queryKey: ["me", "evaluations"] });
      showSuccess("اعتراض شما ثبت شد و به منابع انسانی اطلاع داده شد");
      setOpen(false);
      setReason("");
    } catch (err) {
      showError(extractErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  if (item.objection_at) {
    return (
      <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50/60 p-3 text-sm">
        <p className="font-medium text-amber-900">
          اعتراض شما ثبت شده است — {formatDateTime(item.objection_at)}
        </p>
        <p className="mt-1 text-amber-800">{item.objection_reason}</p>
        {item.objection_resolved_at ? (
          <div className="mt-3 rounded-lg bg-white/70 p-2.5">
            <p className="text-xs font-medium text-gray-500">
              پاسخ منابع انسانی — {formatDateTime(item.objection_resolved_at)}
            </p>
            <p className="mt-1 text-gray-800">{item.objection_resolution}</p>
          </div>
        ) : (
          <p className="mt-2 text-xs text-amber-700">در انتظار بررسی منابع انسانی…</p>
        )}
      </div>
    );
  }

  // اعتراض فقط پس از مشاهده معنا دارد. ولی *پنهان‌کردنِ* کامل این راه، بدترین
  // شکل اعمالش بود: کارمندی که مخالف نتیجه است هیچ نشانه‌ای نمی‌دید که اصلاً
  // راهی وجود دارد، و منطقی‌ترین کارش این بود که «دیدم» را نزند تا حقی را از
  // دست ندهد — یعنی همان گارد، پرونده را معلق می‌کرد.
  if (!item.acknowledged_at) {
    return (
      <p className="mt-3 text-xs text-gray-400">
        اگر به این نتیجه اعتراض دارید، پس از ثبت مشاهده می‌توانید اعتراضتان را
        این‌جا وارد کنید.
      </p>
    );
  }

  return (
    <div className="mt-3">
      {!open ? (
        <button
          onClick={() => setOpen(true)}
          className="text-sm font-medium text-gray-500 underline-offset-4 hover:text-amber-700 hover:underline"
        >
          به این نتیجه اعتراض دارید؟
        </button>
      ) : (
        <div className="rounded-xl border border-amber-200 bg-amber-50/60 p-3">
          <label htmlFor={`objection-${item.id}`} className="mb-1.5 block text-sm font-medium text-amber-900">
            دلیل اعتراض شما
          </label>
          <textarea
            id={`objection-${item.id}`}
            className="w-full resize-none rounded-xl border border-amber-300 bg-white px-3 py-2 text-sm outline-none"
            rows={3}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="مثلاً: شواهد ثبت‌شده برای شاخص تعهد سازمانی با گزارش حضور و غیاب هم‌خوان نیست"
          />
          <p className="mt-1.5 text-xs text-amber-700">
            نتیجه و سند رسمی تغییر نمی‌کنند؛ اعتراض شما ثبت و به منابع انسانی ارجاع می‌شود
            و پاسخ آن همین‌جا نمایش داده خواهد شد.
          </p>
          <div className="mt-3 flex gap-2">
            <Button onClick={submit} loading={busy} disabled={!reason.trim()}>
              ثبت اعتراض
            </Button>
            <button
              onClick={() => setOpen(false)}
              className="rounded-xl border border-amber-300 bg-white px-4 py-2 text-sm font-medium text-amber-800 transition-colors hover:bg-amber-100"
            >
              انصراف
            </button>
          </div>
        </div>
      )}
    </div>
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

function SelfAssessmentHistoryCard({ item }: { item: MySelfAssessment }) {
  const { data: indicators = [] } = useIndicators({ includeInactive: true });
  const byId = new Map(indicators.map((indicator) => [indicator.id, indicator]));
  return (
    <Card
      title={item.period_name ?? `پرونده ${item.evaluation_code}`}
      actions={
        <span className="rounded-full bg-green-50 px-3 py-1 text-xs font-medium text-green-700">
          ثبت نهایی — {formatDateTime(item.submitted_at)}
        </span>
      }
    >
      {item.note && <p className="mb-3 text-sm text-gray-700">{item.note}</p>}
      <div className="space-y-2">
        {item.scores.map((row) => (
          <div key={row.indicator_id} className="flex items-start justify-between gap-3 rounded-xl bg-gray-50 px-3 py-2 text-sm">
            <div>
              <p className="text-gray-800">{byId.get(row.indicator_id)?.description ?? `شاخص ${row.indicator_id}`}</p>
              {row.note && <p className="mt-0.5 text-xs text-gray-500">{row.note}</p>}
            </div>
            <span className="shrink-0 font-bold text-pulse-700">{row.score.toLocaleString("fa-IR")} از ۵</span>
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs text-gray-500">این خودارزیابی قفل شده و قابل ویرایش نیست.</p>
    </Card>
  );
}

/** خودارزیابی و کارنامهٔ خودِ فرد، بدون سربرگِ صفحه.
 *
 * جدا از `MyEvaluationsPage` است چون دو جا نشان داده می‌شود: صفحهٔ «خودارزیابی و
 * کارنامه من» برای کارمند، و تبِ «خودارزیابی من» در صفحهٔ مسئول واحد — که خودش
 * هم ارزیابی می‌شود و تا امروز هیچ راهی به این محتوا نداشت.
 *
 * سربرگ بیرون ماند چون داخلِ تب، عنوانِ دوم اضافی است.
 */
export function MyEvaluationsPanel() {
  const { user } = useAuth();
  const { moduleEnabled, loading: permissionsLoading } = usePermissions();
  // تا قبل از رسیدن تنظیمات، هیچ بخش اختیاری چشمک نمی‌زند. پیش‌فرض ماژول‌ها
  // برای این صفحه عمداً خاموش است، پس «نامعلوم» نباید به‌اشتباه «روشن» دیده شود.
  const showOverview = !permissionsLoading && moduleEnabled("employee_overview_cards");
  const showEvaluationDetails = !permissionsLoading && (
    moduleEnabled("employee_evaluation_visibility") || user?.role === "unit_supervisor"
  );
  const showSelfAssessment = !permissionsLoading && moduleEnabled("self_assessment");
  const showOpenCases = showEvaluationDetails || showSelfAssessment;
  const showAcknowledgement =
    showEvaluationDetails && moduleEnabled("employee_result_acknowledgement");
  const showObjections = showEvaluationDetails && moduleEnabled("objections");
  const { data, isPending, error } = useMyEvaluations(showEvaluationDetails);
  const { data: plans = [], error: plansError } = useMyImprovementPlans();
  const { data: openCases = [] } = useMyOpenEvaluations(showOpenCases);
  const { data: selfAssessments = [], error: selfAssessmentsError } = useMySelfAssessments(showSelfAssessment);
  const [tab, setTab] = useState<"self" | "results">("self");
  const openIds = new Set(openCases.map((item) => item.id));
  const selfHistory = selfAssessments.filter((item) => !openIds.has(item.evaluation_id));

  return (
    <div className="space-y-4">
      {showOverview && <RoleOverviewCards />}

      <div className="inline-flex rounded-xl border border-gray-200 bg-gray-100 p-1" role="tablist" aria-label="بخش‌های شخصی ارزیابی">
        <button
          type="button"
          role="tab"
          aria-selected={tab === "self"}
          onClick={() => setTab("self")}
          className={`rounded-lg px-5 py-2 text-sm font-medium ${tab === "self" ? "bg-white text-gray-900 shadow-sm" : "text-gray-500"}`}
        >
          خودارزیابی
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "results"}
          onClick={() => setTab("results")}
          className={`rounded-lg px-5 py-2 text-sm font-medium ${tab === "results" ? "bg-white text-gray-900 shadow-sm" : "text-gray-500"}`}
        >
          کارنامه من
        </button>
      </div>

      {tab === "self" && (
        <div className="space-y-4" role="tabpanel">
          {showOpenCases && openCases.map((item, i) => (
            <OpenCaseCard key={item.id} item={item} index={i} selfAssessmentEnabled={showSelfAssessment} />
          ))}
          {selfAssessmentsError != null && (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{extractErrorMessage(selfAssessmentsError)}</p>
          )}
          {selfHistory.map((item) => <SelfAssessmentHistoryCard key={item.evaluation_id} item={item} />)}
          {!permissionsLoading && openCases.length === 0 && selfHistory.length === 0 && (
            <Card><EmptyState>هنوز خودارزیابی‌ای برای شما فعال یا ثبت نشده است.</EmptyState></Card>
          )}
        </div>
      )}

      {tab === "results" && plansError != null && (
        <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">
          {extractErrorMessage(plansError)}
        </p>
      )}
      {tab === "results" && plans.map((plan, i) => (
        <MyPlanCard key={plan.id} plan={plan} index={i} />
      ))}
      {/* همهٔ بخش‌های این صفحه به ماژول‌های اختیاری گره خورده‌اند؛ وقتی هیچ‌کدام
          روشن نیست و برنامهٔ بهبودی هم وجود ندارد، صفحهٔ کاملاً خالی چیزی شبیه
          خرابیِ سامانه خوانده می‌شود — یک جملهٔ آرام بهتر از سکوت است. */}
      {tab === "results" && !permissionsLoading && !showEvaluationDetails && plans.length === 0 && plansError == null && (
        <Card>
          <EmptyState>
            نمایش جزئیات کارنامه در این سازمان فعال نشده است. اگر فکر می‌کنید باید نتیجهٔ
            ارزیابی‌تان را این‌جا ببینید، از منابع انسانی بپرسید.
          </EmptyState>
        </Card>
      )}
      {tab === "results" && showEvaluationDetails && error != null && (
        <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{extractErrorMessage(error)}</p>
      )}
      {tab === "results" && showEvaluationDetails && isPending && (
        <div className="space-y-4">
          {[0, 1].map((i) => (
            <div key={i} className="skeleton h-32" />
          ))}
        </div>
      )}
      {tab === "results" && showEvaluationDetails && data && data.items.length === 0 && (
        <Card>
          <EmptyState>هنوز ارزیابی نهایی‌شده‌ای برای شما ثبت نشده است.</EmptyState>
        </Card>
      )}
      {tab === "results" && showEvaluationDetails && data?.items.map((item, i) => (
        <MyEvaluationCard
          key={item.id}
          item={item}
          index={i}
          showObjections={showObjections}
          showAcknowledgement={showAcknowledgement}
        />
      ))}
    </div>
  );
}


export function MyEvaluationsPage() {
  return (
    <div className="space-y-4">
      <PageHeader
        title="خودارزیابی و کارنامه من"
        subtitle="دیدگاه خودتان را برای دورهٔ جاری ثبت کنید و نتایج نهایی‌شدهٔ دوره‌های گذشته را ببینید."
      />
      <MyEvaluationsPanel />
    </div>
  );
}
