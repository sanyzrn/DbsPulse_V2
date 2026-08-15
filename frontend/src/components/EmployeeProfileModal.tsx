import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import {
  useEvaluations,
  usePersonInProgress,
  usePersonRadar,
  usePersonTrend,
  usePersonnelDetail,
} from "../api/queries";
import { extractErrorMessage } from "../api/client";
import { StatusBadge } from "./StatusBadge";
import { Button } from "../ui/Button";
import { Modal } from "../ui/Modal";
import { formatDate } from "../utils/dates";
import type { EvaluationStatus } from "../types";
import { CompetencyRadar, ScoreTrend } from "./PersonCharts";

/** توضیح فارسی «مرحلهٔ فعلی» یک پروندهٔ باز بر اساس وضعیت گردش‌کار — اینکه اکنون
 * منتظر اقدام چه کسی است. */
const IN_PROGRESS_STAGE_LABEL: Record<EvaluationStatus, string> = {
  draft: "در حال نمره‌دهی توسط ارزیاب",
  submitted: "در انتظار تأیید منابع انسانی",
  hr_approved: "در انتظار تأیید معاونت",
  deputy_approved: "در انتظار تأیید نهایی مدیرعامل",
  finalized: "نهایی‌شده",
  cancelled: "لغوشده — منتظر اقدام کسی نیست",
};

// یک رنگ واحد برای هر دو نمودار (تک‌سری‌اند: امتیاز یک نفر) — قبلاً یک گرادیانت
// دو‌رنگه قرمز به طوسی تیره بود که باعث می‌شد پرشدگی رادار/ناحیه کدر و شلوغ به‌نظر
// برسد؛ یک هیوی ساده با دو سطح شفافیت، خواناتر و مینیمال‌تر است.

function InfoRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <p className="text-xs text-gray-500">{label}</p>
      <p className="mt-0.5 font-medium text-gray-800">{value}</p>
    </div>
  );
}

/** پروفایل همیشه‌دردسترس پرسنل: اطلاعات پایه + رادار شایستگی + روند امتیاز نهایی.
 * توسط HR (از فهرست پرسنل/برنامه‌های بهبود) و ارزیاب‌ها (مسئول واحد/معاونت از فهرست
 * افراد زیرمجموعه) استفاده می‌شود؛ بک‌اند دسترسی ارزیاب را به افراد حوزهٔ خودش محدود
 * می‌کند. شناسه پرسنل کافی است — خود مودال جزئیات را می‌گیرد، پس فراخوان‌ها لازم
 * نیست از قبل شیء کامل Personnel را در دست داشته باشند. */
export function EmployeeProfileModal({
  personnelId,
  personName,
  onClose,
}: {
  personnelId: number;
  /** برای نمایش عنوان مودال پیش از رسیدن پاسخ personnel detail (تجربه سریع‌تر) */
  personName?: string;
  onClose: () => void;
}) {
  const navigate = useNavigate();
  const { data: personnel, isError, error } = usePersonnelDetail(personnelId);
  const { data: radar = [] } = usePersonRadar(personnelId);
  const { data: trend = [] } = usePersonTrend(personnelId);
  const { data: inProgress } = usePersonInProgress(personnelId);
  // پرونده‌های ارزیابی این فرد که کاربر جاری اجازهٔ دیدنشان را دارد (HR همه، ارزیاب
  // فقط پرونده‌های حوزهٔ خودش) — برای دکمهٔ «مشاهدهٔ پرونده».
  const { data: evalsPage } = useEvaluations({
    subject_personnel_id: personnelId,
    limit: 20,
    offset: 0,
  });
  const evaluations = evalsPage?.items ?? [];

  function openEvaluation(evaluationId: number) {
    onClose();
    navigate(`/evaluations/${evaluationId}`);
  }

  if (!personnel) {
    return (
      <Modal
        title={`پروفایل پرسنل${personName ? `: ${personName}` : ""}`}
        onClose={onClose}
        size="lg"
        footer={<Button onClick={onClose}>بستن</Button>}
      >
        {isError ? (
          // بدون این شاخه، خطای واکشی به یک اسکلتون بی‌پایان منجر می‌شد.
          <div className="py-8 text-center">
            <p className="text-sm font-medium text-red-600">
              بارگذاری پروفایل این پرسنل ممکن نشد.
            </p>
            <p className="mt-1 text-xs text-gray-500">{extractErrorMessage(error)}</p>
          </div>
        ) : (
          <div className="space-y-3 py-4">
            <div className="skeleton h-24" />
            <div className="skeleton h-64" />
          </div>
        )}
      </Modal>
    );
  }

  return (
    <Modal title={`پروفایل پرسنل: ${personnel.full_name}`} onClose={onClose} size="lg" footer={<Button onClick={onClose}>بستن</Button>}>
      <div className="space-y-5 py-2">
        <div className="grid grid-cols-1 gap-3 rounded-2xl bg-gray-50 p-4 text-sm sm:grid-cols-2">
          <InfoRow label="کد پرسنلی" value={personnel.personnel_code} />
          <InfoRow label="عنوان شغلی" value={personnel.job_title} />
          <InfoRow label="واحد سازمانی" value={personnel.org_unit} />
          <InfoRow
            label="وضعیت"
            value={
              <span
                className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${
                  personnel.status === "active" ? "bg-green-50 text-green-700" : "bg-gray-100 text-gray-600"
                }`}
              >
                <span
                  aria-hidden
                  className={`h-1.5 w-1.5 rounded-full ${personnel.status === "active" ? "bg-green-500" : "bg-gray-400"}`}
                />
                {personnel.status === "active" ? "فعال" : "غیرفعال"}
              </span>
            }
          />
          <InfoRow label="شروع قرارداد" value={formatDate(personnel.contract_start_date)} />
          <InfoRow label="پایان قرارداد" value={formatDate(personnel.contract_end_date)} />
          {personnel.is_manager && (
            <div className="sm:col-span-2">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-700">
                پرسنل مدیریتی (ارزیابی مستقیم توسط معاونت)
              </span>
            </div>
          )}
        </div>

        {/* ارزیابی در جریان: مرحلهٔ فعلی گردش‌کار را همین‌جا نشان می‌دهد تا کاربر
            بی‌نیاز از باز کردن صف/فهرست، وضعیت پروندهٔ باز فرد را ببیند. */}
        {inProgress && (
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 rounded-2xl border border-amber-100 bg-amber-50/60 px-4 py-3">
            <span aria-hidden className="relative flex h-2.5 w-2.5">
              <span className="absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-60" style={{ animation: "var(--animate-pulse-slow)" }} />
              <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-amber-500" />
            </span>
            <span className="text-sm font-semibold text-amber-900">ارزیابی در جریان</span>
            <span className="text-xs text-amber-700">{inProgress.evaluation_code}</span>
            <span className="mr-auto rounded-full bg-white/70 px-2.5 py-0.5 text-xs font-medium text-amber-800">
              {IN_PROGRESS_STAGE_LABEL[inProgress.status]}
            </span>
            {inProgress.was_returned && (
              <span className="rounded-full bg-red-50 px-2.5 py-0.5 text-xs font-medium text-red-700">
                برگشت‌خورده
              </span>
            )}
            <Button variant="link" onClick={() => openEvaluation(inProgress.evaluation_id)}>
              مشاهدهٔ پرونده
            </Button>
          </div>
        )}

        {/* پرونده‌های ارزیابی ثبت‌شدهٔ این فرد — با دکمهٔ مشاهده برای هر پرونده */}
        {evaluations.length > 0 && (
          <div className="rounded-2xl border border-gray-100 bg-white p-4">
            <h3 className="mb-2 text-sm font-semibold text-gray-600">
              پرونده‌های ارزیابی این فرد ({evaluations.length.toLocaleString("fa-IR")})
            </h3>
            <ul className="space-y-1.5">
              {evaluations.map((e) => (
                <li
                  key={e.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-gray-50 px-3 py-2 text-sm"
                >
                  <span className="flex flex-wrap items-center gap-2">
                    <span className="font-medium text-gray-700">{e.evaluation_code}</span>
                    <StatusBadge status={e.status} />
                    <span className="text-xs text-gray-400">{formatDate(e.created_at)}</span>
                  </span>
                  <Button variant="link" onClick={() => openEvaluation(e.id)}>
                    مشاهدهٔ پرونده
                  </Button>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div>
            <h3 className="mb-3 text-sm font-semibold text-gray-600">میانگین امتیاز هر شاخص (از ۵)</h3>
            <CompetencyRadar data={radar} gradientId="profile-radar-fill" height={300} />
          </div>
          <div>
            <h3 className="mb-3 text-sm font-semibold text-gray-600">روند امتیاز نهایی (٪)</h3>
            <ScoreTrend data={trend} gradientId="profile-trend-fill" height={300} />
          </div>
        </div>
      </div>
    </Modal>
  );
}
