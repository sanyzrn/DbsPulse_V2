import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "motion/react";
import { apiClient, extractConflictEvaluationId, extractErrorMessage } from "../../api/client";
import { usePersonnelList } from "../../api/queries";
import { EmployeeProfileModal } from "../../components/EmployeeProfileModal";
import { EvaluationList } from "../../components/EvaluationList";
import { PageHeader } from "../../ui/Card";
import type { Personnel } from "../../types";

export function DeputyHomePage() {
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [startingId, setStartingId] = useState<number | null>(null);
  const [profilePerson, setProfilePerson] = useState<Personnel | null>(null);
  const navigate = useNavigate();
  const { data, error: loadError } = usePersonnelList({
    accessible_to_me: true,
    limit: 1000,
    offset: 0,
  });
  const managers = (data?.items ?? []).filter((p) => p.is_manager);

  async function startEvaluation(p: Personnel) {
    if (starting) return;
    setStarting(true);
    setStartingId(p.id);
    setError(null);
    try {
      const { data } = await apiClient.post("/evaluations", { subject_personnel_id: p.id });
      navigate(`/evaluations/${data.id}`);
    } catch (err) {
      // اگر ارزیابی باز از قبل وجود دارد، مستقیم به همان پرونده برو
      const existingId = extractConflictEvaluationId(err);
      if (existingId !== null) {
        navigate(`/evaluations/${existingId}`);
        return;
      }
      setError(extractErrorMessage(err));
    } finally {
      setStarting(false);
      setStartingId(null);
    }
  }

  return (
    <div className="space-y-4">
      <PageHeader title="پرونده‌های در انتظار بررسی" subtitle="بررسی ارزیابی‌های تأییدشده توسط منابع انسانی و نمره‌دهی پرسنل مدیریتی" />
      {loadError != null && (
        <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{extractErrorMessage(loadError)}</p>
      )}
      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}
      {managers.length > 0 && (
        <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-card">
          <h2 className="mb-4 flex items-center gap-2 text-base font-bold text-gray-900">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-amber-50 to-amber-100 text-amber-600">
              <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                <path d="M10 2l2.4 5 5.6.6-4 4 1.2 5.4-5.2-3-5.2 3 1.2-5.4-4-4 5.6-.6L10 2z" />
              </svg>
            </span>
            پرسنل مدیریتی (نمره‌دهی مستقیم توسط معاونت)
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <tbody>
                {managers.map((p, idx) => (
                  <motion.tr
                    key={p.id}
                    className="border-b border-gray-50 transition-colors last:border-0 hover:bg-pulse-50/30"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ duration: 0.2, delay: idx * 0.03 }}
                  >
                    <td className="px-3 py-2.5">
                      <button
                        onClick={() => setProfilePerson(p)}
                        className="font-medium text-pulse-700 transition-colors hover:text-pulse-800 hover:underline"
                        title="مشاهده پروفایل و روند عملکرد"
                      >
                        {p.full_name}
                      </button>
                    </td>
                    <td className="px-3 py-2.5 text-gray-500">{p.org_unit}</td>
                    <td className="px-3 py-2.5">
                      <button
                        onClick={() => startEvaluation(p)}
                        disabled={starting}
                        className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-bl from-pulse-50 to-pulse-violet-50 px-3 py-1.5 text-sm font-medium text-pulse-700 transition-all duration-200 hover:shadow-md disabled:opacity-50"
                      >
                        {startingId === p.id ? (
                          <>
                            <span className="h-3 w-3 animate-spin rounded-full border-2 border-pulse-300 border-t-pulse-600" />
                            در حال ایجاد…
                          </>
                        ) : (
                          <>
                            <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <path d="M10 4v12M4 10h12" />
                            </svg>
                            شروع ارزیابی جدید
                          </>
                        )}
                      </button>
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      <EvaluationList title="پرونده‌های در انتظار بررسی معاونت" statusFilter="hr_approved" />

      {profilePerson && (
        <EmployeeProfileModal personnel={profilePerson} onClose={() => setProfilePerson(null)} />
      )}
    </div>
  );
}
