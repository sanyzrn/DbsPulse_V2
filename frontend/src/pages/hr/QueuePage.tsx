import { EvaluationList } from "../../components/EvaluationList";

export function QueuePage() {
  return (
    <EvaluationList
      title="پرونده‌های ارزیابی"
      enableAdvancedFilters
      enableExcelExport
      tabs={[
        { key: "submitted", label: "در انتظار بررسی منابع انسانی", status: "submitted" },
        { key: "draft", label: "پیش‌نویس", status: "draft" },
        { key: "hr_approved", label: "در بررسی معاونت", status: "hr_approved" },
        { key: "deputy_approved", label: "در بررسی مدیرعامل", status: "deputy_approved" },
        { key: "finalized", label: "نهایی‌شده", status: "finalized" },
        // پروندهٔ لغوشده در قیف داشبورد نمی‌آید، پس تنها جای دیدنش همین‌جاست
        { key: "cancelled", label: "لغوشده", status: "cancelled" },
        { key: "all", label: "همه" },
      ]}
    />
  );
}
