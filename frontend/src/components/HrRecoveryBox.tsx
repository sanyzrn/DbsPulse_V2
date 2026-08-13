/** ابزارهای نجات پروندهٔ گیرکرده — فقط برای منابع انسانی، فقط روی پروندهٔ باز.
 *
 * چرا لازم است: تا پیش از این تنها راه خروج یک پرونده، رسیدن به تأیید نهایی بود.
 * اگر تأییدکننده‌ای از سازمان می‌رفت، مرحله‌اش هرگز کامل نمی‌شد و ایندکس یکتای
 * دیتابیس هم اجازهٔ ساخت پروندهٔ جایگزین نمی‌داد — آن پرسنل عملاً غیرقابل‌ارزیابی
 * می‌ماند و تنها درمانش SQL دستی روی پروداکشن بود.
 */
import { useState } from "react";
import { apiClient, extractErrorMessage } from "../api/client";
import { useUsersList } from "../api/queries";
import { useConfirm } from "./ConfirmDialog";
import { useToast } from "./Toast";
import type { EvaluationDetail, UserRole } from "../types";

type StageField = "unit_supervisor_user_id" | "deputy_user_id" | "ceo_user_id";

const STAGE_OPTIONS: { field: StageField; label: string; role: UserRole }[] = [
  { field: "unit_supervisor_user_id", label: "مسئول واحد", role: "unit_supervisor" },
  { field: "deputy_user_id", label: "معاونت", role: "deputy" },
  { field: "ceo_user_id", label: "مدیرعامل", role: "ceo" },
];

const inputClass =
  "w-full resize-none rounded-xl border border-gray-300 bg-white px-3 py-2 text-sm outline-none transition-all focus:border-pulse-400 focus:ring-2 focus:ring-pulse-100";

export function HrRecoveryBox({
  evaluation,
  onChanged,
}: {
  evaluation: EvaluationDetail;
  onChanged: () => void;
}) {
  const [panel, setPanel] = useState<"none" | "reassign" | "cancel">("none");

  return (
    <div className="rounded-2xl border border-gray-200 bg-gray-50/70 p-4">
      {panel === "none" && (
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
          <span className="text-sm font-medium text-gray-700">پروندهٔ گیرکرده؟</span>
          <button
            onClick={() => setPanel("reassign")}
            className="flex items-center gap-1.5 text-sm font-medium text-gray-700 hover:text-gray-900"
          >
            <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 7h9l-2.5-2.5M16 13H7l2.5 2.5" />
            </svg>
            تغییر مسئول یک مرحله
          </button>
          <button
            onClick={() => setPanel("cancel")}
            className="flex items-center gap-1.5 text-sm font-medium text-gray-500 hover:text-red-700"
          >
            <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="10" cy="10" r="7" />
              <path d="M6.5 6.5l7 7" />
            </svg>
            لغو پرونده
          </button>
        </div>
      )}

      {panel === "reassign" && (
        <ReassignPanel
          evaluation={evaluation}
          onDone={() => {
            setPanel("none");
            onChanged();
          }}
          onCancel={() => setPanel("none")}
        />
      )}

      {panel === "cancel" && (
        <CancelPanel
          evaluationId={evaluation.id}
          onDone={() => {
            setPanel("none");
            onChanged();
          }}
          onCancel={() => setPanel("none")}
        />
      )}
    </div>
  );
}

function ReassignPanel({
  evaluation,
  onDone,
  onCancel,
}: {
  evaluation: EvaluationDetail;
  onDone: () => void;
  onCancel: () => void;
}) {
  const { showSuccess, showError } = useToast();
  // مسیر «مدیر» مسئول واحد ندارد، پس آن گزینه اصلاً نباید نمایش داده شود
  const options = STAGE_OPTIONS.filter(
    (o) => !(o.field === "unit_supervisor_user_id" && evaluation.unit_supervisor_user_id === null),
  );
  const [stageField, setStageField] = useState<StageField>(options[0]!.field);
  const [newUserId, setNewUserId] = useState<number | "">("");
  const [reason, setReason] = useState("");
  const [sending, setSending] = useState(false);

  const stage = STAGE_OPTIONS.find((o) => o.field === stageField)!;
  const currentUserId = evaluation[stageField];
  const { data: candidates } = useUsersList({ role: stage.role, is_active: true, limit: 200 });
  // مسئول فعلی همان مرحله گزینهٔ معناداری نیست
  const selectable = (candidates?.items ?? []).filter((u) => u.id !== currentUserId);

  async function submit() {
    setSending(true);
    try {
      await apiClient.post(`/evaluations/${evaluation.id}/reassign`, {
        stage_field: stageField,
        new_user_id: newUserId,
        reason,
      });
      showSuccess(`مسئول «${stage.label}» تغییر کرد و به او اطلاع داده شد`);
      onDone();
    } catch (err) {
      showError(extractErrorMessage(err));
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="space-y-3">
      <p className="text-sm font-medium text-gray-800">تغییر مسئول یک مرحله</p>
      <p className="text-xs text-gray-500">
        امتیازها و کامنت‌های ثبت‌شده دست‌نخورده می‌مانند؛ فقط مسئول این مرحله عوض می‌شود.
      </p>

      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label htmlFor="reassign-stage" className="mb-1.5 block text-sm font-medium text-gray-700">
            کدام مرحله
          </label>
          <select
            id="reassign-stage"
            className={inputClass}
            value={stageField}
            onChange={(e) => {
              setStageField(e.target.value as StageField);
              setNewUserId("");
            }}
          >
            {options.map((o) => (
              <option key={o.field} value={o.field}>
                {o.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="reassign-user" className="mb-1.5 block text-sm font-medium text-gray-700">
            مسئول جدید
          </label>
          <select
            id="reassign-user"
            className={inputClass}
            value={newUserId}
            onChange={(e) => setNewUserId(e.target.value ? Number(e.target.value) : "")}
          >
            <option value="">— انتخاب کنید —</option>
            {selectable.map((u) => (
              <option key={u.id} value={u.id}>
                {u.username}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div>
        <label htmlFor="reassign-reason" className="mb-1.5 block text-sm font-medium text-gray-700">
          دلیل تغییر
        </label>
        <textarea
          id="reassign-reason"
          className={inputClass}
          rows={2}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="مثلاً: معاونت قبلی از سازمان خارج شد"
        />
      </div>

      <div className="flex gap-2">
        <button
          disabled={sending || !newUserId || !reason.trim()}
          onClick={submit}
          className="rounded-xl bg-pulse-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition-all duration-200 hover:bg-pulse-700 hover:shadow-md disabled:opacity-50"
        >
          ثبت تغییر مسئول
        </button>
        <button
          onClick={onCancel}
          className="rounded-xl border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-100"
        >
          انصراف
        </button>
      </div>
    </div>
  );
}

function CancelPanel({
  evaluationId,
  onDone,
  onCancel,
}: {
  evaluationId: number;
  onDone: () => void;
  onCancel: () => void;
}) {
  const { showSuccess, showError } = useToast();
  const confirm = useConfirm();
  const [reason, setReason] = useState("");
  const [sending, setSending] = useState(false);

  async function submit() {
    const ok = await confirm({
      title: "این پرونده لغو شود؟",
      description:
        "پرونده به وضعیت «لغوشده» می‌رود و دیگر قابل ادامه نیست. امتیازها و تاریخچه برای حسابرسی باقی می‌مانند و پس از آن می‌توان برای همین پرسنل پروندهٔ تازه‌ای باز کرد.",
      confirmLabel: "لغو پرونده",
    });
    if (!ok) return;
    setSending(true);
    try {
      await apiClient.post(`/evaluations/${evaluationId}/cancel`, { reason });
      showSuccess("پرونده لغو شد");
      onDone();
    } catch (err) {
      showError(extractErrorMessage(err));
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="space-y-3">
      <p className="text-sm font-medium text-gray-800">لغو پرونده</p>
      <p className="text-xs text-gray-500">
        پرونده حذف نمی‌شود — وضعیتش «لغوشده» می‌شود و دلیل شما در کامنت‌ها و گزارش رویدادها ثبت می‌ماند.
      </p>
      <div>
        <label htmlFor="cancel-reason" className="mb-1.5 block text-sm font-medium text-gray-700">
          دلیل لغو
        </label>
        <textarea
          id="cancel-reason"
          className={inputClass}
          rows={2}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="مثلاً: پرسنل پیش از پایان ارزیابی از سازمان خارج شد"
        />
      </div>
      <div className="flex gap-2">
        <button
          disabled={sending || !reason.trim()}
          onClick={submit}
          className="rounded-xl bg-red-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition-all duration-200 hover:bg-red-700 hover:shadow-md disabled:opacity-50"
        >
          لغو پرونده
        </button>
        <button
          onClick={onCancel}
          className="rounded-xl border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-100"
        >
          انصراف
        </button>
      </div>
    </div>
  );
}
