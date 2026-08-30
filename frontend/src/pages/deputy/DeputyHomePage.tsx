import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiClient, extractConflictEvaluationId, extractErrorMessage } from "../../api/client";
import { useEvaluations, usePersonnelList } from "../../api/queries";
import { EmployeeProfileModal } from "../../components/EmployeeProfileModal";
import { EvaluationActionButton, type OpenEvaluation } from "../../components/EvaluationActionButton";
import { EvaluationList } from "../../components/EvaluationList";
import { RoleOverviewCards } from "../../components/RoleOverviewCards";
import { PageHeader } from "../../ui/Card";
import { Table } from "../../ui/Table";
import { isOpenStatus, type Personnel } from "../../types";

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

  // برای غیرفعال‌کردن «شروع ارزیابی جدید» وقتی ارزیابی باز از قبل هست
  const { data: myEvaluations } = useEvaluations({ limit: 200, offset: 0 });
  // `isOpenStatus` و نه `!== "finalized"`: پروندهٔ **لغوشده** پایان‌یافته است و
  // نباید جلوی شروع ارزیابی تازه را بگیرد.
  const openEvaluationByPersonnel = new Map<number, OpenEvaluation>();
  for (const e of myEvaluations?.items ?? []) {
    if (isOpenStatus(e.status)) {
      openEvaluationByPersonnel.set(e.subject_personnel_id, {
        id: e.id,
        code: e.evaluation_code,
        status: e.status,
      });
    }
  }

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
      <RoleOverviewCards />
      {loadError != null && (
        <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{extractErrorMessage(loadError)}</p>
      )}
      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>}
      {managers.length > 0 && (
        <div className="rounded-2xl border border-gray-200 bg-white p-4">
          <h2 className="mb-4 flex items-center gap-2 text-base font-bold text-gray-900">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-amber-50 text-amber-600">
              <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                <path d="M10 2l2.4 5 5.6.6-4 4 1.2 5.4-5.2-3-5.2 3 1.2-5.4-4-4 5.6-.6L10 2z" />
              </svg>
            </span>
            پرسنل مدیریتی (نمره‌دهی مستقیم توسط معاونت)
          </h2>
          <Table
            bordered={false}
            headers={["نام", "واحد", ""]}
            rowKeys={managers.map((p) => p.id)}
            rows={managers.map((p) => [
              <button
                key="name"
                onClick={() => setProfilePerson(p)}
                className="font-medium text-gray-900 underline-offset-4 transition-colors hover:text-pulse-700 hover:underline"
                title="مشاهده پروفایل و روند عملکرد"
              >
                {p.full_name}
              </button>,
              <span key="unit" className="text-gray-500">
                {p.org_unit}
              </span>,
              <EvaluationActionButton
                key="action"
                open={openEvaluationByPersonnel.get(p.id)}
                starting={starting}
                isStartingThis={startingId === p.id}
                onContinue={(id) => navigate(`/evaluations/${id}`)}
                onStart={() => startEvaluation(p)}
              />,
            ])}
          />
        </div>
      )}
      <EvaluationList
        title="پرونده‌های ارزیابی"
        tabs={[
          { key: "pending", label: "در انتظار بررسی معاونت", status: "hr_approved" },
          { key: "finalized", label: "نهایی‌شده", status: "finalized" },
          { key: "all", label: "همهٔ پرونده‌های من" },
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
