import { EvaluationList } from "../../components/EvaluationList";
import { RoleOverviewCards } from "../../components/RoleOverviewCards";
import { PageHeader } from "../../ui/Card";

export function CeoHomePage() {
  return (
    <div className="space-y-4">
      <PageHeader title="داشبورد مدیرعامل" subtitle="نمای سریع پرونده‌های در انتظار تأیید نهایی شما" />
      <RoleOverviewCards />
      <EvaluationList
        title="پرونده‌های ارزیابی"
        tabs={[
          { key: "pending", label: "در انتظار تأیید نهایی", status: "deputy_approved" },
          { key: "finalized", label: "نهایی‌شده", status: "finalized" },
          { key: "all", label: "همهٔ پرونده‌های من" },
        ]}
      />
    </div>
  );
}
