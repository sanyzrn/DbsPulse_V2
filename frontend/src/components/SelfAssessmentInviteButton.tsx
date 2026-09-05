import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { apiClient, extractErrorMessage } from "../api/client";
import { useIndicators } from "../api/queries";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "./Toast";
import { Modal } from "../ui/Modal";
import { Button } from "../ui/Button";
import { formatDateTime } from "../utils/dates";
import type { CurrentSelfAssessment, Personnel, SelfAssessmentState } from "../types";

/** برای هر وضعیت: چه بنویس، و آیا اصلاً دکمه‌ای هست.
 *
 *  حالت‌هایی که کنشی ندارند عمداً *متن* می‌شوند نه دکمهٔ خاموش: دکمهٔ خاموش
 *  می‌گوید «شاید بشود» و کاربر رویش کلیک می‌کند تا بفهمد چرا نمی‌شود.
 */
const LABEL: Record<SelfAssessmentState, { text: string; hint: string; action: boolean }> = {
  pending: {
    text: "ارسال یادآوری",
    hint: "یک یادآوری ساده برای ثبت خودارزیابی این دوره فرستاده می‌شود",
    action: true,
  },
  invited: {
    text: "ارسال مجدد یادآوری",
    hint: "این فرد هنوز ثبت نکرده است؛ می‌توانید یادآوری ساده دیگری بفرستید",
    action: true,
  },
  submitted: {
    text: "مشاهده خودارزیابی",
    hint: "مشاهدهٔ خودارزیابی همین فرد در قرارداد جاری",
    action: true,
  },
  no_case: {
    text: "—",
    hint: "وضعیت خودارزیابی این فرد مشخص نیست",
    action: false,
  },
  no_account: {
    text: "بدون حساب",
    hint: "این فرد حساب کاربری فعالی ندارد، پس اعلانی دریافت نمی‌کند",
    action: false,
  },
  not_eligible: {
    text: "مشمول نیست",
    hint: "مدیرعامل و معاونت‌ها در این دوره خودارزیابی ندارند",
    action: false,
  },
  closed: {
    text: "مهلت گذشته",
    hint: "قرارداد فعال نیست و خودارزیابی ثبت نشده است",
    action: false,
  },
};

/** دکمهٔ «دعوت به خودارزیابی» روی هر ردیف پرسنل.
 *
 *  خودارزیابی از قبل کار می‌کرد ولی هیچ‌کس خبر نداشت: کارمند فقط اگر خودش وارد
 *  سامانه می‌شد و پروندهٔ بازش را پیدا می‌کرد می‌فهمید که می‌تواند نظرش را ثبت
 *  کند. این دکمه همان خبر را می‌رساند.
 *
 *  دعوتِ دوم یادآوری است، نه خطا: اگر اعلان گم شود یا کارمند آن را ببندد،
 *  پنجرهٔ خودارزیابی کوتاه است و بدون راهِ ارسالِ دوباره فرصت از دست می‌رود.
 */
export function SelfAssessmentInviteButton({ personnel }: { personnel: Personnel }) {
  const { user } = useAuth();
  const { showSuccess, showError } = useToast();
  const queryClient = useQueryClient();
  const [sending, setSending] = useState(false);
  const [viewing, setViewing] = useState<CurrentSelfAssessment | null>(null);
  const { data: indicators = [] } = useIndicators({ includeInactive: true });
  const state = LABEL[personnel.self_assessment_state] ?? LABEL.no_case;

  async function invite() {
    setSending(true);
    try {
      await apiClient.post(`/personnel/${personnel.id}/invite-self-assessment`);
      await queryClient.invalidateQueries({ queryKey: ["personnel"], refetchType: "all" });
      showSuccess("یادآوری خودارزیابی فرستاده شد");
    } catch (err) {
      showError(extractErrorMessage(err));
    } finally {
      setSending(false);
    }
  }

  async function view() {
    setSending(true);
    try {
      const { data } = await apiClient.get<CurrentSelfAssessment>(
        `/personnel/${personnel.id}/self-assessment`,
      );
      setViewing(data);
    } catch (err) {
      showError(extractErrorMessage(err));
    } finally {
      setSending(false);
    }
  }

  const canAct = state.action && (
    personnel.self_assessment_state !== "submitted" || user?.role === "hr"
  );

  if (!canAct) {
    return (
      <span
        title={state.hint}
        className={`whitespace-nowrap text-xs ${
          personnel.self_assessment_state === "submitted" ? "text-green-700" : "text-gray-400"
        }`}
      >
        {state.text}
      </span>
    );
  }

  const byId = new Map(indicators.map((indicator) => [indicator.id, indicator]));
  return (
    <>
      <button
        onClick={personnel.self_assessment_state === "submitted" ? view : invite}
        disabled={sending}
        title={state.hint}
        className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-lg border border-gray-200 px-2.5 py-1 text-xs font-medium text-gray-600 transition-colors hover:bg-gray-50 hover:text-gray-900 disabled:opacity-50"
      >
        <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
          <path d="M2.5 5.5h15v9a1 1 0 0 1-1 1h-13a1 1 0 0 1-1-1v-9z" />
          <path d="M2.5 6l7.5 5 7.5-5" />
        </svg>
        {sending
          ? personnel.self_assessment_state === "submitted"
            ? "در حال دریافت…"
            : "در حال ارسال…"
          : state.text}
      </button>
      {viewing && (
        <Modal
          title={`خودارزیابی ${viewing.personnel_name}`}
          size="lg"
          onClose={() => setViewing(null)}
          footer={<Button onClick={() => setViewing(null)}>بستن</Button>}
        >
          <p className="mb-3 text-xs text-gray-500">
            ثبت نهایی: {viewing.submitted_at ? formatDateTime(viewing.submitted_at) : "—"}
          </p>
          {viewing.note && <p className="mb-3 rounded-lg bg-gray-50 p-3 text-sm text-gray-700">{viewing.note}</p>}
          <div className="space-y-2">
            {viewing.scores.map((row) => (
              <div key={row.indicator_id} className="flex items-start justify-between gap-3 rounded-xl border border-gray-100 px-3 py-2 text-sm">
                <div>
                  <p className="text-gray-800">{byId.get(row.indicator_id)?.description ?? `شاخص ${row.indicator_id}`}</p>
                  {row.note && <p className="mt-0.5 text-xs text-gray-500">{row.note}</p>}
                </div>
                <span className="shrink-0 font-bold text-pulse-700">{row.score.toLocaleString("fa-IR")} از ۵</span>
              </div>
            ))}
          </div>
        </Modal>
      )}
    </>
  );
}
