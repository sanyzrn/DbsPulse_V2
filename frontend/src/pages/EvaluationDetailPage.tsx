import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { apiClient, extractErrorMessage } from "../api/client";
import {
  useAppConfig,
  useEvaluationDetail,
  useIndicators,
  usePersonnelDetail,
} from "../api/queries";
import { useAuth } from "../auth/AuthContext";
import { useConfirm } from "../components/ConfirmDialog";
import { ScoreFormTable, computePreview, scoredRows, useScoreForm } from "../components/ScoreForm";
import { StatusBadge } from "../components/StatusBadge";
import { useToast } from "../components/Toast";
import { Button } from "../ui/Button";
import { PctBadge, PctBar, ScoreRing } from "../ui/Meters";
import { formatDateTime } from "../utils/dates";
import {
  STAGE_LABELS,
  type AppConfig,
  type EvaluationDetail,
  type Indicator,
} from "../types";

export function EvaluationDetailPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const { showSuccess, showError } = useToast();
  const confirm = useConfirm();
  const queryClient = useQueryClient();
  const config = useAppConfig();

  const evaluationId = id ? Number(id) : null;
  const {
    data: evaluation,
    error: evaluationError,
    isPending: evaluationPending,
  } = useEvaluationDetail(evaluationId);
  const { data: personnel } = usePersonnelDetail(evaluation?.subject_personnel_id ?? null);
  const { data: indicators = [] } = useIndicators({ includeInactive: true });

  const [evaluatorComment, setEvaluatorComment] = useState("");
  const [newComment, setNewComment] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setEvaluatorComment(evaluation?.evaluator_comment ?? "");
  }, [evaluation?.id, evaluation?.evaluator_comment]);

  async function load() {
    await queryClient.invalidateQueries({ queryKey: ["evaluation", evaluationId] });
    await queryClient.invalidateQueries({ queryKey: ["evaluations"] });
    // هر اقدام گردش‌کار (تأیید/برگشت/کامنت) ممکن است اعلان جدیدی بسازد؛ زنگوله را
    // فوراً به‌روز می‌کنیم تا کاربر منتظر poll بعدی نماند.
    await queryClient.invalidateQueries({ queryKey: ["notifications"] });
  }

  const loadError = evaluationError != null ? extractErrorMessage(evaluationError) : null;

  if (evaluationPending || (evaluation && !personnel)) {
    return (
      <div className="space-y-4">
        <div className="skeleton h-5 w-24" />
        <div className="skeleton h-32" />
        <div className="skeleton h-64" />
      </div>
    );
  }
  if (loadError || !evaluation || !personnel || !user) {
    return (
      <div className="rounded-2xl border border-gray-100 bg-white p-8 text-center shadow-card">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-red-50">
          <svg viewBox="0 0 24 24" className="h-6 w-6 text-red-500" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <path d="M12 8v4m0 4h.01" />
          </svg>
        </div>
        <p className="mb-4 text-sm text-red-600">
          {loadError ?? "اطلاعات این ارزیابی در دسترس نیست."}
        </p>
        <button
          onClick={() => navigate("/")}
          className="rounded-xl border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm transition-all duration-200 hover:bg-gray-50 hover:shadow-md"
        >
          بازگشت به صفحه اصلی
        </button>
      </div>
    );
  }

  const isSupervisorDraft =
    user.role === "unit_supervisor" &&
    evaluation.status === "draft" &&
    evaluation.stage === "supervisor_scoring" &&
    evaluation.unit_supervisor_user_id === user.id;

  const isManagerInitialScoring =
    user.role === "deputy" &&
    evaluation.status === "hr_approved" &&
    evaluation.stage === "deputy_review" &&
    evaluation.unit_supervisor_user_id === null &&
    evaluation.deputy_user_id === user.id;

  const isEditableScoring = isSupervisorDraft || isManagerInitialScoring;

  const canHrApprove = user.role === "hr" && evaluation.status === "submitted";
  const canDeputyApprove =
    user.role === "deputy" &&
    evaluation.status === "hr_approved" &&
    evaluation.stage === "deputy_review" &&
    evaluation.deputy_user_id === user.id &&
    evaluation.unit_supervisor_user_id !== null;
  const canCeoFinalize =
    user.role === "ceo" &&
    evaluation.status === "deputy_approved" &&
    evaluation.stage === "ceo_final" &&
    evaluation.ceo_user_id === user.id;

  const canComment =
    (user.role === "hr" && evaluation.status === "submitted") ||
    (user.role === "deputy" && evaluation.status === "hr_approved" && evaluation.deputy_user_id === user.id) ||
    (user.role === "ceo" && evaluation.status === "deputy_approved" && evaluation.ceo_user_id === user.id);

  return (
    <div className="space-y-4">
      <button onClick={() => navigate(-1)} className="inline-flex items-center gap-1 text-sm font-medium text-gray-500 transition-colors hover:text-gray-700">
        <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M13 5l-5 5 5 5" />
        </svg>
        بازگشت
      </button>

      <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-card">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h1 className="text-xl font-bold text-gray-900">{personnel.full_name}</h1>
            <p className="mt-1 text-sm text-gray-500">
              کد پرسنلی: {personnel.personnel_code} · عنوان شغلی: {personnel.job_title} · واحد: {personnel.org_unit}
            </p>
          </div>
          <div className="text-left text-sm">
            <p className="font-medium text-gray-800">{evaluation.evaluation_code}</p>
            <p className="text-gray-500">
              <StatusBadge status={evaluation.status} /> · {STAGE_LABELS[evaluation.stage]}
            </p>
            <p className="mt-1 text-xs text-gray-400">
              شروع: {formatDateTime(evaluation.created_at)}
              {evaluation.finalized_at && <> · نهایی‌شدن: {formatDateTime(evaluation.finalized_at)}</>}
            </p>
            {evaluation.acknowledged_at && (
              <p className="mt-1 text-xs">
                <span className="rounded-full bg-green-50 px-2 py-0.5 font-medium text-green-700">
                  رؤیت کارمند: {formatDateTime(evaluation.acknowledged_at)}
                </span>
              </p>
            )}
          </div>
        </div>
        {evaluation.final_weighted_pct !== null && (
          <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="rounded-xl bg-gray-50 p-3">
              <div className="mb-2 flex items-center justify-between text-sm">
                <span className="text-gray-500">امتیاز عمومی (وزن {Math.round(config.general_section_weight * 100).toLocaleString("fa-IR")}٪)</span>
                <PctBadge value={evaluation.general_score_pct} />
              </div>
              <PctBar value={evaluation.general_score_pct ?? 0} />
            </div>
            <div className="rounded-xl bg-gray-50 p-3">
              <div className="mb-2 flex items-center justify-between text-sm">
                <span className="text-gray-500">امتیاز تخصصی (وزن {Math.round(config.specialized_section_weight * 100).toLocaleString("fa-IR")}٪)</span>
                <PctBadge value={evaluation.specialized_score_pct} />
              </div>
              <PctBar value={evaluation.specialized_score_pct ?? 0} />
            </div>
            <div className="flex items-center justify-between gap-3 rounded-xl border border-pulse-100 bg-pulse-50/50 p-3">
              <span className="text-sm font-medium text-gray-700">امتیاز نهایی وزنی</span>
              <ScoreRing value={evaluation.final_weighted_pct} size={56} />
            </div>
          </div>
        )}
        {evaluation.recommendation && (
          <p className="mt-3 flex items-center gap-2 rounded-xl border border-amber-100 bg-amber-50 px-3 py-2 text-sm text-amber-800">
            <span aria-hidden>💡</span>
            نتیجه پیشنهادی: <span className="font-semibold">{evaluation.recommendation}</span>
          </p>
        )}
      </div>

      {isEditableScoring ? (
        <EditableScoring
          key={`${evaluation.id}-${evaluation.status}`}
          config={config}
          evaluationId={evaluation.id}
          indicators={indicators.filter((i) => i.is_active)}
          existing={evaluation.scores}
          evaluatorComment={evaluatorComment}
          setEvaluatorComment={setEvaluatorComment}
          showEvaluatorComment={isSupervisorDraft || isManagerInitialScoring}
          commentLabel={isManagerInitialScoring ? "نظر کلی معاونت" : "نظر کلی مسئول واحد"}
          nextAction={isSupervisorDraft ? "submit" : "deputy_approve"}
          onSubmitted={load}
        />
      ) : (
        <ReadOnlyScoring
          config={config}
          indicators={indicators}
          scores={evaluation.scores}
          evaluatorComment={evaluation.evaluator_comment}
          commentLabel={evaluation.unit_supervisor_user_id === null ? "نظر کلی معاونت" : "نظر کلی مسئول واحد"}
        />
      )}

      <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-card">
        <h2 className="mb-3 text-base font-bold text-gray-900">کامنت‌ها</h2>
        {evaluation.comments.length === 0 && <p className="text-sm text-gray-400">کامنتی ثبت نشده است.</p>}
        <ul className="space-y-2">
          {evaluation.comments.map((c) => (
            <li key={c.id} className="rounded-xl border border-gray-100 bg-gray-50/70 p-3 text-sm">
              <p className="mb-1 flex items-center gap-2 text-xs text-gray-500">
                <span className="inline-flex items-center rounded-md bg-pulse-50 px-1.5 py-0.5 font-medium text-pulse-700">
                  {STAGE_LABELS[c.stage]}
                </span>
                <span>{c.commenter_username ?? `#${c.commenter_user_id}`}</span>
                <span>·</span>
                <span>{formatDateTime(c.created_at)}</span>
              </p>
              <p className="text-gray-700">{c.comment_text}</p>
            </li>
          ))}
        </ul>

        {canComment && (
          <div className="mt-3">
            <textarea
              className="w-full resize-none rounded-xl border border-gray-200 bg-gray-100 px-3 py-2 outline-none transition-colors duration-150 focus:border-pulse-500 focus:bg-white text-sm"
              rows={2}
              value={newComment}
              onChange={(e) => setNewComment(e.target.value)}
              placeholder="افزودن کامنت…"
            />
            <button
              disabled={busy || !newComment.trim()}
              onClick={async () => {
                setBusy(true);
                setError(null);
                try {
                  await apiClient.post(`/evaluations/${evaluation.id}/comments`, {
                    comment_text: newComment,
                  });
                  setNewComment("");
                  await load();
                  showSuccess("کامنت ثبت شد");
                } catch (err) {
                  const message = extractErrorMessage(err);
                  setError(message);
                  showError(message);
                } finally {
                  setBusy(false);
                }
              }}
              className="mt-2 rounded-xl bg-gray-800 px-4 py-2 text-sm font-medium text-white shadow-md shadow-gray-500/20 transition-all duration-200 hover:bg-gray-900 hover:shadow-lg disabled:opacity-50"
            >
              ثبت کامنت
            </button>
          </div>
        )}
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {(canHrApprove || canDeputyApprove || canCeoFinalize) && (
        <ReturnBox evaluationId={evaluation.id} onReturned={load} />
      )}

      <div className="flex justify-end gap-2">
        {canHrApprove && (
          <ActionButton
            label="تأیید (منابع انسانی)"
            busy={busy}
            onClick={async () => {
              const ok = await confirm({
                title: "تأیید این ارزیابی؟",
                description: "پرونده به مرحله بررسی معاونت منتقل می‌شود.",
              });
              if (!ok) return;
              setBusy(true);
              setError(null);
              try {
                await apiClient.post(`/evaluations/${evaluation.id}/hr-approve`);
                await load();
                showSuccess("ارزیابی تأیید شد");
              } catch (err) {
                const message = extractErrorMessage(err);
                setError(message);
                showError(message);
              } finally {
                setBusy(false);
              }
            }}
          />
        )}
        {canDeputyApprove && (
          <ActionButton
            label="تأیید (معاونت)"
            busy={busy}
            onClick={async () => {
              const ok = await confirm({
                title: "تأیید این ارزیابی؟",
                description: "پرونده به مرحله تأیید نهایی مدیرعامل منتقل می‌شود.",
              });
              if (!ok) return;
              setBusy(true);
              setError(null);
              try {
                await apiClient.post(`/evaluations/${evaluation.id}/deputy-approve`);
                await load();
                showSuccess("ارزیابی تأیید شد");
              } catch (err) {
                const message = extractErrorMessage(err);
                setError(message);
                showError(message);
              } finally {
                setBusy(false);
              }
            }}
          />
        )}
        {canCeoFinalize && (
          <ActionButton
            label="تأیید نهایی"
            busy={busy}
            onClick={async () => {
              const ok = await confirm({
                title: "تأیید نهایی این ارزیابی؟",
                description: "پس از این کار، پرونده نهایی و غیرقابل‌ویرایش می‌شود.",
                confirmLabel: "تأیید نهایی",
              });
              if (!ok) return;
              setBusy(true);
              setError(null);
              try {
                await apiClient.post(`/evaluations/${evaluation.id}/ceo-finalize`);
                await load();
                showSuccess("ارزیابی نهایی شد");
              } catch (err) {
                const message = extractErrorMessage(err);
                setError(message);
                showError(message);
              } finally {
                setBusy(false);
              }
            }}
          />
        )}
        {user.role === "hr" && evaluation.status === "finalized" && (
          <button
            onClick={async () => {
              // پنجره باید هم‌زمان با کلیک کاربر (sync) باز شود، وگرنه مرورگر (به‌خصوص
              // Safari و برخی نسخه‌های Chrome) آن را پاپ‌آپ مسدودشده تلقی می‌کند، چون
              // بعد از یک await دیگر «مستقیماً ناشی از تعامل کاربر» به‌حساب نمی‌آید.
              const printWindow = window.open("", "_blank");
              try {
                const { data } = await apiClient.get(`/evaluations/${evaluation.id}/summary.pdf`, {
                  responseType: "blob",
                });
                const url = URL.createObjectURL(new Blob([data], { type: "application/pdf" }));
                if (printWindow) {
                  printWindow.location.href = url;
                } else {
                  // اگر مرورگر حتی پنجرهٔ خالی را هم مسدود کرده، فایل را دانلود می‌کنیم
                  // تا کاربر دست‌کم به خروجی PDF دسترسی داشته باشد.
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = `${evaluation.evaluation_code}.pdf`;
                  document.body.appendChild(a);
                  a.click();
                  a.remove();
                  showError("باز کردن پنجرهٔ جدید توسط مرورگر مسدود شد؛ فایل به‌جای آن دانلود شد.");
                }
                setTimeout(() => URL.revokeObjectURL(url), 30_000);
              } catch (err) {
                printWindow?.close();
                showError(extractErrorMessage(err));
              }
            }}
            className="inline-flex items-center gap-2 rounded-xl border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm transition-all duration-200 hover:bg-gray-50 hover:shadow-md"
          >
            <svg viewBox="0 0 20 20" className="h-4 w-4 text-red-500" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M10 3v10m0 0l-3.5-3.5M10 13l3.5-3.5M4 15v1a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1v-1" />
            </svg>
            چاپ / خروجی PDF
          </button>
        )}
      </div>
    </div>
  );
}

function ActionButton({ label, busy, onClick }: { label: string; busy: boolean; onClick: () => void }) {
  return (
    <Button disabled={busy} onClick={onClick}>
      {label}
    </Button>
  );
}

function ReadOnlyScoring({
  config,
  indicators,
  scores,
  evaluatorComment,
  commentLabel,
}: {
  config: AppConfig;
  indicators: Indicator[];
  scores: EvaluationDetail["scores"];
  evaluatorComment: string | null;
  commentLabel: string;
}) {
  if (scores.length === 0) {
    return (
      <div className="rounded-2xl border border-gray-100 bg-white p-8 text-center shadow-card text-sm text-gray-400">
        هنوز امتیازی ثبت نشده است.
      </div>
    );
  }
  const drafts = scores.map((s) => ({
    indicator_id: s.indicator_id,
    score: s.score,
    evidence_text: s.evidence_text ?? "",
  }));
  return (
    <div className="space-y-4">
      <div>
        <h3 className="mb-2 text-base font-bold text-gray-900">شاخص‌های عمومی</h3>
        <ScoreFormTable
          section="general"
          indicators={indicators}
          drafts={drafts}
          onScoreChange={() => {}}
          onEvidenceChange={() => {}}
          readOnly
          config={config}
        />
      </div>
      <div>
        <h3 className="mb-2 text-base font-bold text-gray-900">شاخص‌های تخصصی</h3>
        <ScoreFormTable
          section="specialized"
          indicators={indicators}
          drafts={drafts}
          onScoreChange={() => {}}
          onEvidenceChange={() => {}}
          readOnly
          config={config}
        />
      </div>
      {evaluatorComment && (
        <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-card">
          <h3 className="mb-1 text-base font-bold text-gray-900">{commentLabel}</h3>
          <p className="text-sm text-gray-700">{evaluatorComment}</p>
        </div>
      )}
    </div>
  );
}

function EditableScoring({
  config,
  evaluationId,
  indicators,
  existing,
  evaluatorComment,
  setEvaluatorComment,
  showEvaluatorComment,
  commentLabel,
  nextAction,
  onSubmitted,
}: {
  config: AppConfig;
  evaluationId: number;
  indicators: Indicator[];
  existing: EvaluationDetail["scores"];
  evaluatorComment: string;
  setEvaluatorComment: (v: string) => void;
  showEvaluatorComment: boolean;
  commentLabel: string;
  nextAction: "submit" | "deputy_approve";
  onSubmitted: () => void;
}) {
  const { showSuccess, showError } = useToast();
  const confirm = useConfirm();
  const navigate = useNavigate();
  const { drafts, setScore, setEvidence, violations, unscored, isValid } = useScoreForm(
    indicators,
    existing,
    config
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastSavedAt, setLastSavedAt] = useState<Date | null>(null);
  const [dirty, setDirty] = useState(false);
  // اولین رندر (hydration داده‌های موجود) نباید autosave را فعال کند
  const hydratedRef = useRef(false);

  async function saveDraft(options?: { silent?: boolean }) {
    setSaving(true);
    setError(null);
    try {
      await apiClient.put(`/evaluations/${evaluationId}/scores`, {
        scores: scoredRows(drafts),
      });
      setDirty(false);
      setLastSavedAt(new Date());
      if (!options?.silent) showSuccess("پیش‌نویس ذخیره شد");
    } catch (err) {
      const message = extractErrorMessage(err);
      setError(message);
      if (!options?.silent) showError(message);
    } finally {
      setSaving(false);
    }
  }

  // ذخیره خودکار: ۲ ثانیه پس از آخرین تغییر؛ کار نیم‌ساعته ارزیاب نباید با یک
  // reload از بین برود
  useEffect(() => {
    if (!hydratedRef.current) {
      hydratedRef.current = true;
      return;
    }
    setDirty(true);
    const timer = setTimeout(() => {
      saveDraft({ silent: true });
    }, 2000);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [drafts]);

  // اگر تغییر ذخیره‌نشده هست، هنگام بستن/رفرش صفحه هشدار بده
  useEffect(() => {
    if (!dirty) return;
    function onBeforeUnload(e: BeforeUnloadEvent) {
      e.preventDefault();
    }
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [dirty]);

  const preview = computePreview(drafts, indicators, config);

  async function submit() {
    const ok = await confirm({
      title: "ثبت نهایی این ارزیابی؟",
      description: "پس از ثبت، دیگر امکان ویرایش امتیازها برای شما وجود نخواهد داشت.",
      confirmLabel: "ثبت ارزیابی",
    });
    if (!ok) return;

    setSaving(true);
    setError(null);
    try {
      await apiClient.put(`/evaluations/${evaluationId}/scores`, {
        scores: scoredRows(drafts),
      });
      if (showEvaluatorComment) {
        await apiClient.patch(`/evaluations/${evaluationId}/evaluator-comment`, {
          evaluator_comment: evaluatorComment,
        });
      }
      await apiClient.post(`/evaluations/${evaluationId}/${nextAction === "submit" ? "submit" : "deputy-approve"}`);
      showSuccess("ارزیابی با موفقیت ثبت شد");
      onSubmitted();
      // پس از ثبت نهایی، ارزیاب به صفحهٔ اصلی نقش خود بازمی‌گردد (مسیر «/» توسط
      // App.tsx بر اساس نقش هدایت می‌شود). کمی تأخیر تا توست موفقیت دیده شود.
      setTimeout(() => navigate("/"), 400);
    } catch (err) {
      const message = extractErrorMessage(err);
      setError(message);
      showError(message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-pulse-100 bg-pulse-50/50 px-4 py-3 shadow-card">
        <p className="flex items-center gap-2 text-sm text-gray-600">
          <svg viewBox="0 0 20 20" className="h-4 w-4 text-pulse-500" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="10" cy="10" r="8" />
            <path d="M10 6v4l2 2" />
          </svg>
          برای هر شاخص باید امتیازی انتخاب کنید؛ تا وقتی حتی یک شاخص بی‌امتیاز باشد، ثبت نهایی فعال نمی‌شود.
        </p>
        <p className={`flex items-center gap-1.5 text-xs font-medium ${dirty ? "text-amber-600" : "text-pulse-600"}`}>
          {saving ? (
            <>
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-amber-500" />
              در حال ذخیره…
            </>
          ) : dirty ? (
            <>
              <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
              تغییرات ذخیره‌نشده (ذخیره خودکار فعال است)
            </>
          ) : lastSavedAt ? (
            <>
              <span className="h-1.5 w-1.5 rounded-full bg-pulse-500" />
              ذخیره شد · {lastSavedAt.toLocaleTimeString("fa-IR", { hour: "2-digit", minute: "2-digit" })}
            </>
          ) : (
            ""
          )}
        </p>
      </div>

      <div>
        <h3 className="mb-2 text-base font-bold text-gray-900">شاخص‌های عمومی (وزن {Math.round(config.general_section_weight * 100).toLocaleString("fa-IR")}٪)</h3>
        <ScoreFormTable
          section="general"
          indicators={indicators}
          drafts={drafts}
          onScoreChange={setScore}
          onEvidenceChange={setEvidence}
          config={config}
        />
      </div>
      <div>
        <h3 className="mb-2 text-base font-bold text-gray-900">شاخص‌های تخصصی (وزن {Math.round(config.specialized_section_weight * 100).toLocaleString("fa-IR")}٪)</h3>
        <ScoreFormTable
          section="specialized"
          indicators={indicators}
          drafts={drafts}
          onScoreChange={setScore}
          onEvidenceChange={setEvidence}
          config={config}
        />
      </div>

      {showEvaluatorComment && (
        <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-card">
          <h3 className="mb-2 text-base font-bold text-gray-900">{commentLabel}</h3>
          <textarea
            className="w-full rounded-xl border border-gray-200 bg-gray-100 px-3 py-2 outline-none transition-colors duration-150 focus:border-pulse-500 focus:bg-white text-sm"
            rows={3}
            value={evaluatorComment}
            onChange={(e) => setEvaluatorComment(e.target.value)}
          />
        </div>
      )}

      {preview && (
        <div className="rounded-2xl border border-gray-100 bg-white p-4 shadow-card">
          <p className="mb-3 flex items-center gap-1.5 text-xs text-gray-500">
            <svg viewBox="0 0 20 20" className="h-3.5 w-3.5 text-pulse-500" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
              <path d="M10 3v14M3 10h14" />
            </svg>
            پیش‌نمایش محاسبه (نتیجه نهایی و معتبر پس از ثبت توسط سرور محاسبه می‌شود)
          </p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="rounded-xl bg-gray-50 p-3">
              <div className="mb-2 flex items-center justify-between text-sm">
                <span className="text-gray-500">امتیاز عمومی (وزن {Math.round(config.general_section_weight * 100).toLocaleString("fa-IR")}٪)</span>
                <PctBadge value={preview.general_pct} />
              </div>
              <PctBar value={preview.general_pct} />
            </div>
            <div className="rounded-xl bg-gray-50 p-3">
              <div className="mb-2 flex items-center justify-between text-sm">
                <span className="text-gray-500">امتیاز تخصصی (وزن {Math.round(config.specialized_section_weight * 100).toLocaleString("fa-IR")}٪)</span>
                <PctBadge value={preview.specialized_pct} />
              </div>
              <PctBar value={preview.specialized_pct} />
            </div>
            <div className="flex items-center justify-between gap-3 rounded-xl border border-pulse-100 bg-pulse-50/50 p-3">
              <span className="text-sm font-medium text-gray-700">امتیاز نهایی وزنی</span>
              <ScoreRing value={preview.final_pct} size={56} />
            </div>
          </div>
        </div>
      )}

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="flex justify-end gap-2">
        <Button variant="secondary" onClick={() => saveDraft()} disabled={saving}>
          ذخیره پیش‌نویس
        </Button>
        <Button
          onClick={submit}
          disabled={saving || !isValid}
          title={!isValid ? "همهٔ شاخص‌ها باید امتیاز داشته باشند و شواهد امتیازهای ۱ و ۵ کامل باشد" : undefined}
        >
          ثبت ارزیابی
        </Button>
      </div>
      {unscored.length > 0 && (
        <p className="text-left text-xs text-red-600">
          هنوز {unscored.length.toLocaleString("fa-IR")} شاخص امتیازی ندارد.
        </p>
      )}
      {unscored.length === 0 && violations.length > 0 && (
        <p className="text-left text-xs text-red-600">
          {violations.length.toLocaleString("fa-IR")} شاخص (امتیاز ۱ یا ۵) هنوز شواهد کافی ندارد.
        </p>
      )}
    </div>
  );
}

function ReturnBox({ evaluationId, onReturned }: { evaluationId: number; onReturned: () => void }) {
  const { showSuccess, showError } = useToast();
  const confirm = useConfirm();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [sending, setSending] = useState(false);

  async function submitReturn() {
    const ok = await confirm({
      title: "برگشت این پرونده به مرحله قبل؟",
      description: "پرونده یک مرحله عقب می‌رود و نمره‌دهنده/تأییدکنندهٔ آن مرحله مطلع می‌شود؛ اقدامات این مرحله باید دوباره انجام شود.",
      confirmLabel: "برگشت پرونده",
    });
    if (!ok) return;
    setSending(true);
    try {
      await apiClient.post(`/evaluations/${evaluationId}/return`, { reason });
      showSuccess("پرونده به مرحله قبل برگشت داده شد");
      setOpen(false);
      setReason("");
      onReturned();
    } catch (err) {
      showError(extractErrorMessage(err));
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="rounded-2xl border border-amber-200 bg-amber-50/60 p-4">
      {!open ? (
        <button
          onClick={() => setOpen(true)}
          className="flex items-center gap-1.5 text-sm font-medium text-amber-800 hover:text-amber-900"
        >
          <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 14l-4-4 4-4" />
            <path d="M5 10h9a2 2 0 0 1 2 2v3" />
          </svg>
          برگشت پرونده به مرحله قبل (با ذکر دلیل)
        </button>
      ) : (
        <div>
          <label htmlFor="return-reason" className="mb-1.5 block text-sm font-medium text-amber-900">
            دلیل برگشت پرونده
          </label>
          <textarea
            id="return-reason"
            className="w-full resize-none rounded-xl border border-amber-300 bg-white px-3 py-2 text-sm outline-none transition-all"
            rows={2}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="مثلاً: شواهد شاخص «تعهد سازمانی» کافی نیست…"
          />
          <div className="mt-3 flex gap-2">
            <button
              disabled={sending || !reason.trim()}
              onClick={submitReturn}
              className="rounded-xl bg-amber-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition-all duration-200 hover:bg-amber-700 hover:shadow-md disabled:opacity-50"
            >
              برگشت پرونده
            </button>
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
