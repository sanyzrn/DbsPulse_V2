import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiClient, extractConflictEvaluationId, extractErrorMessage } from "../../api/client";
import { useEvaluations, usePersonnelList } from "../../api/queries";
import { EmployeeProfileModal } from "../../components/EmployeeProfileModal";
import { EvaluationActionButton } from "../../components/EvaluationActionButton";
import { EvaluationList } from "../../components/EvaluationList";
import { PageHeader } from "../../ui/Card";
import { Table } from "../../ui/Table";
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

  // برای غیرفعال‌کردن «شروع ارزیابی جدید» وقتی ارزیابی باز از قبل هست (به‌جای
  // کلیک بی‌نتیجه و خطای ۴۰۹) — این فهرست از قبل توسط بک‌اند به ارزیابی‌های
  // خودِ همین مسئول واحد محدود شده است.
  const { data: myEvaluations } = useEvaluations({ limit: 200, offset: 0 });
  const openEvaluationByPersonnel = new Map<number, { id: number; code: string }>();
  for (const e of myEvaluations?.items ?? []) {
    if (e.status !== "finalized") {
      openEvaluationByPersonnel.set(e.subject_personnel_id, { id: e.id, code: e.evaluation_code });
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
      <PageHeader title="افراد زیرمجموعه" subtitle="شروع ارزیابی جدید برای افراد زیرمجموعه شما" />
      <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-card">
        <h2 className="mb-4 text-base font-bold text-gray-900">فهرست افراد</h2>
        {loadError != null && (
          <p className="mb-2 text-sm text-red-600">{extractErrorMessage(loadError)}</p>
        )}
        {error && <p className="mb-2 text-sm text-red-600">{error}</p>}
        <Table
          bordered={false}
          headers={["نام", "عنوان شغلی", "واحد", ""]}
          rowKeys={personnel.map((p) => p.id)}
          emptyMessage="فردی زیرمجموعه شما نیست."
          rows={personnel.map((p) => [
            <button
              key="name"
              onClick={() => setProfilePerson(p)}
              className="font-medium text-pulse-700 transition-colors hover:text-pulse-800 hover:underline"
              title="مشاهده پروفایل و روند عملکرد"
            >
              {p.full_name}
            </button>,
            <span key="job" className="text-gray-600">
              {p.job_title}
            </span>,
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
