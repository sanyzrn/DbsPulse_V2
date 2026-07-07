import { useState } from "react";
import { Link } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { motion } from "motion/react";
import { apiClient, extractErrorMessage } from "../../api/client";
import {
  useEligibleEvaluations,
  useImprovementPlans,
} from "../../api/queries";
import { EmployeeProfileModal } from "../../components/EmployeeProfileModal";
import { PaginationControls } from "../../components/PaginationControls";
import { useToast } from "../../components/Toast";
import { Button } from "../../ui/Button";
import { Card, EmptyState, PageHeader, TableScroll } from "../../ui/Card";
import { PctBadge } from "../../ui/Meters";
import { Modal } from "../../ui/Modal";
import { Table } from "../../ui/Table";
import { JalaliDatePicker } from "../../ui/JalaliDatePicker";
import { formatDate } from "../../utils/dates";
import {
  IMPROVEMENT_PLAN_STATUS_LABELS,
  type EligibleEvaluation,
  type ImprovementPlanStatus,
} from "../../types";

const PAGE_SIZE = 10;
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

const inputClass =
  "w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 outline-none transition-all duration-200 focus:border-gray-400";

function CreatePlanRow({
  item,
  onCreated,
  onOpenProfile,
}: {
  item: EligibleEvaluation;
  onCreated: () => void;
  onOpenProfile: (personnelId: number, name: string) => void;
}) {
  const { showSuccess, showError } = useToast();
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState(`برنامه بهبود ${item.personnel_full_name}`);
  const [reviewDate, setReviewDate] = useState("");
  const [busy, setBusy] = useState(false);

  async function create() {
    setBusy(true);
    try {
      await apiClient.post("/improvement-plans", {
        evaluation_record_id: item.evaluation_record_id,
        title,
        review_date: reviewDate,
      });
      showSuccess("برنامه بهبود ساخته شد");
      onCreated();
    } catch (err) {
      showError(extractErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <motion.tr
      className="border-b border-gray-50 transition-colors last:border-0 hover:bg-pulse-50/30"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.2 }}
    >
      <td className="px-3 py-2.5">
        <button
          onClick={() => onOpenProfile(item.personnel_id, item.personnel_full_name)}
          className="text-right font-medium text-pulse-700 transition-colors hover:text-pulse-800 hover:underline"
        >
          {item.personnel_full_name}
        </button>
      </td>
      <td className="px-3 py-2.5 text-gray-500">{item.evaluation_code}</td>
      <td className="px-3 py-2.5"><PctBadge value={item.final_weighted_pct} /></td>
      <td className="px-3 py-2.5">
        <Button variant="link" onClick={() => setOpen(true)}>
          + ساخت برنامه بهبود
        </Button>
        {open && (
          <Modal
            title={`برنامه بهبود برای ${item.personnel_full_name}`}
            onClose={() => setOpen(false)}
            footer={
              <>
                <Button variant="secondary" onClick={() => setOpen(false)}>
                  انصراف
                </Button>
                <Button type="submit" form="create-plan-form" loading={busy}>
                  ثبت
                </Button>
              </>
            }
          >
            <form
              id="create-plan-form"
              onSubmit={(e) => {
                e.preventDefault();
                create();
              }}
              className="space-y-4 py-2"
            >
              <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
                عنوان
                <input
                  required
                  className={inputClass}
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                />
              </label>
              <label className="flex flex-col gap-1 text-xs font-medium text-gray-600">
                تاریخ بازنگری
                <JalaliDatePicker
                  required
                  className={inputClass}
                  value={reviewDate}
                  onChange={(iso) => setReviewDate(iso)}
                />
              </label>
            </form>
          </Modal>
        )}
      </td>
    </motion.tr>
  );
}

export function ImprovementPlansPage() {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<ImprovementPlanStatus | "">("");
  const [page, setPage] = useState(0);
  const [profilePerson, setProfilePerson] = useState<{ id: number; name: string } | null>(null);

  const { data: eligible = [] } = useEligibleEvaluations();
  const { data, error } = useImprovementPlans({
    status: statusFilter || undefined,
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
  });
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  function refreshAll() {
    queryClient.invalidateQueries({ queryKey: ["improvement-plans"] });
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title="برنامه‌های بهبود"
        subtitle="پیگیری برنامه بهبود مکتوب برای ارزیابی‌هایی که نتیجه‌شان «تمدید مشروط» بوده است."
      />

      <Card title={`نیازمند برنامه بهبود (${eligible.length.toLocaleString("fa-IR")})`}>
        {eligible.length === 0 ? (
          <EmptyState>ارزیابی نهایی‌شده‌ای در انتظار برنامه بهبود نیست.</EmptyState>
        ) : (
          <TableScroll>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="px-3 py-2.5 text-right text-xs font-semibold text-gray-600">پرسنل</th>
                  <th className="px-3 py-2.5 text-right text-xs font-semibold text-gray-600">پرونده</th>
                  <th className="px-3 py-2.5 text-right text-xs font-semibold text-gray-600">نتیجه</th>
                  <th className="px-3 py-2.5 text-right text-xs font-semibold text-gray-600"></th>
                </tr>
              </thead>
              <tbody>
                {eligible.map((item) => (
                  <CreatePlanRow
                    key={item.evaluation_record_id}
                    item={item}
                    onCreated={refreshAll}
                    onOpenProfile={(id, name) => setProfilePerson({ id, name })}
                  />
                ))}
              </tbody>
            </table>
          </TableScroll>
        )}
      </Card>

      <Card
        title="فهرست برنامه‌ها"
        actions={
          <div className="relative">
            <select
              className="appearance-none rounded-xl border border-gray-200 bg-white py-1.5 pr-3 pl-8 text-sm text-gray-700 outline-none transition-colors focus:border-gray-400"
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value as ImprovementPlanStatus | "");
                setPage(0);
              }}
            >
              <option value="">همه وضعیت‌ها</option>
              {(Object.keys(IMPROVEMENT_PLAN_STATUS_LABELS) as ImprovementPlanStatus[]).map((s) => (
                <option key={s} value={s}>
                  {IMPROVEMENT_PLAN_STATUS_LABELS[s]}
                </option>
              ))}
            </select>
            <svg viewBox="0 0 20 20" className="pointer-events-none absolute left-2 top-1/2 h-3 w-3 -translate-y-1/2 text-gray-400" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M6 8l4 4 4-4" />
            </svg>
          </div>
        }
      >
        {error != null && <p className="mb-2 text-sm text-red-600">{extractErrorMessage(error)}</p>}
        {data && data.items.length > 0 && (
          <Table
            bordered={false}
            headers={["عنوان", "پرسنل", "تاریخ بازنگری", "وضعیت", ""]}
            rowKeys={data.items.map((p) => p.id)}
            rows={data.items.map((p) => [
              <span key="title" className="font-medium text-gray-700">
                {p.title}
              </span>,
              <button
                key="person"
                onClick={() => setProfilePerson({ id: p.personnel_id, name: p.personnel_full_name })}
                className="text-right text-gray-600 transition-colors hover:text-pulse-700 hover:underline"
              >
                {p.personnel_full_name}
              </button>,
              <span key="date" className="text-gray-500">
                {formatDate(p.review_date)}
              </span>,
              <span key="status" className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_BADGE[p.status]}`}>
                <span aria-hidden className={`h-1.5 w-1.5 rounded-full ${STATUS_DOT[p.status]}`} />
                {IMPROVEMENT_PLAN_STATUS_LABELS[p.status]}
              </span>,
              <Link key="details" to={`/hr/improvement-plans/${p.id}`} className="inline-flex items-center gap-1 text-sm font-medium text-pulse-600 hover:text-pulse-700">
                جزئیات
                <svg viewBox="0 0 20 20" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M7 5l5 5-5 5" />
                </svg>
              </Link>,
            ])}
          />
        )}
        {data && data.items.length === 0 && <EmptyState />}
        <PaginationControls
          page={page}
          totalPages={totalPages}
          totalCount={total}
          pageSize={PAGE_SIZE}
          onPageChange={setPage}
        />
      </Card>

      {profilePerson && (
        <EmployeeProfileModal
          personnelId={profilePerson.id}
          personName={profilePerson.name}
          onClose={() => setProfilePerson(null)}
        />
      )}
    </div>
  );
}
