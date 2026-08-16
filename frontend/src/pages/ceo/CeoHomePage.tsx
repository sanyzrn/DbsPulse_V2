import { EvaluationList } from "../../components/EvaluationList";
import { RoleOverviewCards } from "../../components/RoleOverviewCards";
import { PageHeader } from "../../ui/Card";

export function CeoHomePage() {
  return (
    <div className="space-y-4">
      {/* «داشبورد» بود، ولی این صفحه یک صف است نه داشبورد — تحلیل سازمان صفحهٔ
          جداگانهٔ خودش را دارد. یک کلمه برای دو چیز، انتظار غلط می‌سازد. */}
      <PageHeader title="صندوق تأیید نهایی" subtitle="پرونده‌هایی که منتظر امضای شما هستند" />
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
