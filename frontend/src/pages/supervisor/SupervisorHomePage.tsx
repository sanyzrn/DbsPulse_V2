import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "motion/react";
import { apiClient, extractConflictEvaluationId, extractErrorMessage } from "../../api/client";
import { usePersonnelList } from "../../api/queries";
import { EmployeeProfileModal } from "../../components/EmployeeProfileModal";
import { EvaluationList } from "../../components/EvaluationList";
import { PageHeader } from "../../ui/Card";
import type { Personnel } from "../../types";

export function SupervisorHomePage() {
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
  const personnel = data?.items ?? [];

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
      <PageHeader title="افراد زیرمجموعه" subtitle="شروع ارزیابی جدید برای افراد زیرمجموعه شما" />
      <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-card">
        <h2 className="mb-4 text-base font-bold text-gray-900">فهرست افراد</h2>
        {loadError != null && (
          <p className="mb-2 text-sm text-red-600">{extractErrorMessage(loadError)}</p>
        )}
        {error && <p className="mb-2 text-sm text-red-600">{error}</p>}
        {personnel.length === 0 && (
          <p className="py-6 text-center text-sm text-gray-400">فردی زیرمجموعه شما نیست.</p>
        )}
        {personnel.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 bg-gradient-to-l from-pulse-50/50 to-pulse-violet-50/50">
                  <th className="px-3 py-2.5 text-right text-xs font-semibold text-gray-600">نام</th>
                  <th className="px-3 py-2.5 text-right text-xs font-semibold text-gray-600">عنوان شغلی</th>
                  <th className="px-3 py-2.5 text-right text-xs font-semibold text-gray-600">واحد</th>
                  <th className="px-3 py-2.5 text-right text-xs font-semibold text-gray-600"></th>
                </tr>
              </thead>
              <tbody>
                {personnel.map((p, idx) => (
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
                    <td className="px-3 py-2.5 text-gray-600">{p.job_title}</td>
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
        )}
      </div>

      <EvaluationList
        title="ارزیابی‌های من"
        tabs={[
          { key: "all", label: "همه" },
          { key: "draft", label: "پیش‌نویس", status: "draft" },
          { key: "submitted", label: "در انتظار بررسی", status: "submitted" },
          { key: "finalized", label: "نهایی‌شده", status: "finalized" },
        ]}
      />

      {profilePerson && (
        <EmployeeProfileModal
          personnelId={profilePerson.id}
          personName={profilePerson.full_name}
          onClose={() => setProfilePerson(null)}
        />
      )}
    </div>
  );
}
